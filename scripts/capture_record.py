"""Record calibration capture per settled day in ``health/capture.tsv`` (#54).

The ADR-025 ledger records every document the pipeline *fetched*, so it cannot
see a document it never fetched: that document is absent from both sides of any
ratio built from it (#54 section 2). Capture is therefore measured against IBM's
own history, by a read-only ``--enumerate`` of one UTC day at a grid finer than
the sweep's, diffed against the documents the archive holds for that day. NC-058
is the first such measurement; this module makes it a daily one.

Contract
--------

``health/capture.tsv`` is written **only** by the ``capture`` job of
``calibration-health.yml``, which is what lets ``push_with_retry.sh`` replay it
over a concurrent poll without a conflict (ADR-025 amendment, 2026-09-29). It is
append-only and holds one row per document proven to exist on an enumerated day:

    day  last_update_date  served  held  status  step_hours  run_id

``status`` is run C's vocabulary (``captured``, ``MISSED``,
``archived_not_served``) plus ``no_documents``, a single sentinel row for a day
on which IBM published nothing and the archive holds nothing. Without it an
empty day would have no row, would be pending forever, and would be enumerated
again every run.

When a day is settled
---------------------

The sweep reads a trailing 48 h window once a day, dispatched around 09:00-11:15
UTC. The part of day ``D`` after the sweep's dispatch time is covered by the
sweeps of ``D+1`` and ``D+2``, so ``D`` has had both of its sweeps only once
``D+2``'s has run. The capture job runs on ``D+3`` (the health cron, 03:17, is
served around 08:00-09:00), so it enumerates ``D = today - 3``, the newest day
that is certainly settled. Enumerating a fresher day would count documents the
next sweep is still going to recover as missed.

Held documents come from ``health/state-index.tsv``, which lists every archived
document (1,507 of 1,507 at ``calibration-data`` @ ``b70d7b4``), so the job needs
the sparse ``health/`` checkout and never the 1.3 GB snapshot tree.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

CAPTURE_FIELDS = ("day", "last_update_date", "served", "held", "status", "step_hours", "run_id")
PROVEN = ("captured", "MISSED", "archived_not_served")
NO_DOCUMENTS = "no_documents"
STATUSES = frozenset((*PROVEN, NO_DOCUMENTS))
SETTLE_DAYS = 3
"""The newest enumerated day is ``today - SETTLE_DAYS``; see the module docstring."""
SPAN_DAYS = 7
"""Days in the rolling capture figure, and the most a run will look back to catch up."""
MAX_DAYS_PER_RUN = 3
"""About 97 queries a day at 15 min, 1.0-1.2 s each: three days fit the job timeout."""

_INDEX_HEADER = ("snapshot_filename", "last_update_date", "qubit_digest", "is_new_state")


@dataclass(frozen=True)
class CaptureRow:
    """One ``health/capture.tsv`` record."""

    day: date
    stem: str
    served: bool
    held: bool
    status: str
    step_hours: str
    run_id: str

    def fields(self) -> tuple[str, ...]:
        return (
            self.day.isoformat(),
            self.stem,
            "yes" if self.served else "no",
            "yes" if self.held else "no",
            self.status,
            self.step_hours,
            self.run_id,
        )


def stem_time(stem: str) -> datetime:
    """``20260913T012345000000Z`` -> tz-aware UTC datetime."""
    return datetime.strptime(stem.removesuffix("Z"), "%Y%m%dT%H%M%S%f").replace(tzinfo=UTC)


def settled_span(today: date) -> list[date]:
    """The ``SPAN_DAYS`` settled days ending ``today - SETTLE_DAYS``, newest first."""
    return [today - timedelta(days=SETTLE_DAYS + offset) for offset in range(SPAN_DAYS)]


def pending_days(
    today: date, recorded: Iterable[date], limit: int = MAX_DAYS_PER_RUN
) -> list[date]:
    """Settled days not yet recorded, newest first, at most ``limit``.

    Newest first so the day that keeps the figure current always lands, and a
    run that loses its budget part-way loses the oldest catch-up instead. A day
    that falls out of the span unrecorded is not chased: it is still inside the
    60-day retention (NC-026) for a manual dispatch, but the rolling figure no
    longer reads it, and ``capture_days_7d`` shows the hole.
    """
    done = set(recorded)
    return [day for day in settled_span(today) if day not in done][:limit]


def read_capture(path: Path) -> list[CaptureRow]:
    """Read ``health/capture.tsv``, rejecting anything it cannot vouch for.

    A missing file is an empty record: the capture job has not run yet, which the
    dashboard renders as "not yet measured" rather than as zero capture.
    """
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if header is None or tuple(header) != CAPTURE_FIELDS:
            raise ValueError(f"{path} has an unexpected header")
        rows: list[CaptureRow] = []
        for number, record in enumerate(reader, 2):
            if len(record) != len(CAPTURE_FIELDS) or not all(record[:5]):
                raise ValueError(f"{path}:{number}: malformed capture row")
            day, stem, served, held, status, step, run_id = record
            if status not in STATUSES or served not in {"yes", "no"} or held not in {"yes", "no"}:
                raise ValueError(f"{path}:{number}: unknown value in capture row")
            rows.append(
                CaptureRow(
                    date.fromisoformat(day),
                    stem,
                    served == "yes",
                    held == "yes",
                    status,
                    step,
                    run_id,
                )
            )
    return rows


def held_stems(index_path: Path, day: date) -> set[str]:
    """Archived document stems stamped on ``day`` (UTC, half-open), from the state index."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    with index_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != _INDEX_HEADER:
            raise ValueError(f"{index_path} has an unexpected header")
        stems = {row["snapshot_filename"].removesuffix(".json") for row in reader}
    return {stem for stem in stems if start <= stem_time(stem) < end}


def read_served(path: Path) -> set[str]:
    """Stamps the probe wrote with ``--served-out``, one per line."""
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def day_rows(
    day: date, served: set[str], held: set[str], step_hours: str, run_id: str
) -> list[CaptureRow]:
    """Diff one day's served stamps against its held stamps.

    Served stamps outside ``day`` are dropped: the probe's window is closed at
    both ends, so the query at the following midnight can return a document of
    the previous day and nothing else, but the two windows must tile exactly.
    """
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    shown = {stem for stem in served if start <= stem_time(stem) < end}
    rows = []
    for stem in sorted(shown | held):
        is_served, is_held = stem in shown, stem in held
        status = (
            "captured"
            if is_served and is_held
            else "MISSED"
            if is_served
            else "archived_not_served"
        )
        rows.append(CaptureRow(day, stem, is_served, is_held, status, step_hours, run_id))
    if not rows:
        rows.append(CaptureRow(day, "-", False, False, NO_DOCUMENTS, step_hours, run_id))
    return rows


@dataclass(frozen=True)
class CaptureSummary:
    """The rolling capture figure over the settled span."""

    days: int
    exist: int
    held: int
    missed: int

    @property
    def rate(self) -> float | None:
        return self.held / self.exist if self.exist else None


def summarise(rows: Sequence[CaptureRow], today: date) -> CaptureSummary:
    """Capture over the settled span ending ``today - SETTLE_DAYS``.

    ``held`` counts ``captured`` and ``archived_not_served`` (the archive has
    both); ``exist`` adds ``MISSED``. The rate is an **upper** bound, like
    NC-058, because a document living less than one grid step can escape the
    enumeration too.
    """
    span = set(settled_span(today))
    inside = [row for row in rows if row.day in span]
    status = [row.status for row in inside]
    held = status.count("captured") + status.count("archived_not_served")
    missed = status.count("MISSED")
    return CaptureSummary(len({row.day for row in inside}), held + missed, held, missed)


def append_rows(path: Path, rows: Sequence[CaptureRow]) -> None:
    """Append ``rows``, writing the header first if the file is new. LF on every platform."""
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        if new:
            writer.writerow(CAPTURE_FIELDS)
        writer.writerows(row.fields() for row in rows)


def _pending(args: argparse.Namespace) -> int:
    recorded = {row.day for row in read_capture(args.root / "health" / "capture.tsv")}
    for day in pending_days(date.fromisoformat(args.today), recorded):
        print(day.isoformat())
    return 0


def _record(args: argparse.Namespace) -> int:
    capture = args.root / "health" / "capture.tsv"
    day = date.fromisoformat(args.day)
    if day in {row.day for row in read_capture(capture)}:
        print(f"{day} is already recorded; nothing appended")
        return 0
    held = held_stems(args.root / "health" / "state-index.tsv", day)
    rows = day_rows(day, read_served(args.served), held, args.step, args.run_id)
    append_rows(capture, rows)
    status = [row.status for row in rows]
    print(
        f"{day}: captured {status.count('captured')}, MISSED {status.count('MISSED')}, "
        f"archived_not_served {status.count('archived_not_served')}"
    )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    pending = sub.add_parser("pending", help="print the settled days still to enumerate")
    pending.add_argument("--root", type=Path, required=True, help="calibration-data checkout")
    pending.add_argument("--today", required=True, help="UTC date, YYYY-MM-DD")
    record = sub.add_parser("record", help="append one enumerated day")
    record.add_argument("--root", type=Path, required=True, help="calibration-data checkout")
    record.add_argument("--day", required=True, help="UTC date, YYYY-MM-DD")
    record.add_argument("--served", type=Path, required=True, help="probe --served-out file")
    record.add_argument("--step", required=True, help="enumeration step in hours, recorded")
    record.add_argument("--run-id", required=True, help="Actions run id, recorded")
    args = parser.parse_args(list(argv) if argv is not None else None)
    return _pending(args) if args.mode == "pending" else _record(args)


if __name__ == "__main__":
    sys.exit(main())
