"""Record calibration capture per settled day in ``health/capture.tsv`` (#54).

The ADR-025 ledger records every document the pipeline *fetched*, so it cannot
see a document it never fetched: that document is absent from both sides of any
ratio built from it (#54 section 2). Capture is therefore measured against IBM's
own history, by a read-only ``--enumerate`` of one UTC day at a grid finer than
the sweep's, diffed against what the pipeline retrieved for that day. NC-058 is
the first such measurement; this module makes it a daily one.

What counts as captured
-----------------------

The question is what the **unattended** pipeline, the scheduled hourly polls and
the scheduled daily sweep, retrieves. The archive is not the answer to it: a
manual backfill dispatched before this job runs files the very documents the
pipeline missed, and an archive-based diff would then record them as captured,
permanently, in an append-only file (PR #105 review). So a document is
*retrieved* when a ledger row from a **scheduled** run names it, with any
decision: a ``duplicate`` row is as much a retrieval as a ``new`` one, because a
scheduled run that found a document already filed would have filed it otherwise
(PR #105 review, the same correction applied to NC-057's counterfactual).

A row comes from a dispatch when its ``poll_time_utc`` falls inside the
execution interval of a job of a ``workflow_dispatch`` run of
``calibration-poll.yml``, read from the Actions jobs API. Job intervals, not run
windows: a queued run's run-level start is its creation time, so a run window
would claim the scheduled run it was queued behind (``read_dispatch_windows``).
The mapping is exact because the workflow's concurrency group serialises its
runs, so jobs never overlap: at ``calibration-data`` @ ``0c798dc``, the 600 job
intervals of the poll runs since 2026-09-02 do not overlap, and 596 of 596
ledger poll times fall inside exactly one of them.

Contract
--------

``health/capture.tsv`` is written **only** by the ``capture`` job of
``calibration-health.yml``, which is what lets ``push_with_retry.sh`` replay it
over a concurrent poll without a conflict (ADR-025 amendment, 2026-09-29). It is
append-only and holds one row per document proven to exist on an enumerated day:

    day  last_update_date  served  held  retrieved  status  step_hours  run_id

``status`` is run C's vocabulary plus two:

- ``captured``: served by IBM and retrieved by the pipeline.
- ``archived_not_served``: retrieved, but the enumeration did not serve it, the
  enumeration's own recall shortfall.
- ``MISSED``: served, and the archive does not hold it.
- ``backfilled``: the archive holds it only because a dispatch filed it. Missed
  by the pipeline, and counted as missed.
- ``no_documents``: a single sentinel row for a day on which nothing existed, so
  an empty day is recorded rather than enumerated again every run.

Every write replaces the file atomically, so a job killed mid-write leaves the
previous record whole rather than a truncated row ``read_capture`` would reject.

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
document (1,507 of 1,507 at ``calibration-data`` @ ``b70d7b4``), and retrievals
from ``ledger/``, so the job needs the sparse ``health/`` and ``ledger/``
checkout and never the 1.3 GB snapshot tree.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

CAPTURE_FIELDS = (
    "day",
    "last_update_date",
    "served",
    "held",
    "retrieved",
    "status",
    "step_hours",
    "run_id",
)
HELD = ("captured", "archived_not_served")
MISSED_BY_PIPELINE = ("MISSED", "backfilled")
NO_DOCUMENTS = "no_documents"
STATUSES = frozenset((*HELD, *MISSED_BY_PIPELINE, NO_DOCUMENTS))
SETTLE_DAYS = 3
"""The newest enumerated day is ``today - SETTLE_DAYS``; see the module docstring."""
SPAN_DAYS = 7
"""Days in the rolling capture figure, and the most a run will look back to catch up."""
MAX_DAYS_PER_RUN = 3
"""About 97 queries a day at 15 min, 1.0-1.2 s each: three days fit the step timeout."""

_INDEX_HEADER = ("snapshot_filename", "last_update_date", "qubit_digest", "is_new_state")
_YES_NO = {"yes": True, "no": False}


@dataclass(frozen=True)
class CaptureRow:
    """One ``health/capture.tsv`` record."""

    day: date
    stem: str
    served: bool
    held: bool
    retrieved: bool
    status: str
    step_hours: str
    run_id: str

    def fields(self) -> tuple[str, ...]:
        return (
            self.day.isoformat(),
            self.stem,
            "yes" if self.served else "no",
            "yes" if self.held else "no",
            "yes" if self.retrieved else "no",
            self.status,
            self.step_hours,
            self.run_id,
        )


def stem_time(stem: str) -> datetime:
    """``20260913T012345000000Z`` -> tz-aware UTC datetime."""
    return datetime.strptime(stem.removesuffix("Z"), "%Y%m%dT%H%M%S%f").replace(tzinfo=UTC)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


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
            if len(record) != len(CAPTURE_FIELDS) or not all(record[:6]):
                raise ValueError(f"{path}:{number}: malformed capture row")
            day, stem, served, held, retrieved, status, step, run_id = record
            flags = (served, held, retrieved)
            if status not in STATUSES or any(flag not in _YES_NO for flag in flags):
                raise ValueError(f"{path}:{number}: unknown value in capture row")
            rows.append(
                CaptureRow(
                    date.fromisoformat(day),
                    stem,
                    _YES_NO[served],
                    _YES_NO[held],
                    _YES_NO[retrieved],
                    status,
                    step,
                    run_id,
                )
            )
    return rows


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def held_stems(index_path: Path, day: date) -> set[str]:
    """Archived document stems stamped on ``day`` (UTC, half-open), from the state index."""
    start, end = _day_bounds(day)
    with index_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != _INDEX_HEADER:
            raise ValueError(f"{index_path} has an unexpected header")
        stems = {row["snapshot_filename"].removesuffix(".json") for row in reader}
    return {stem for stem in stems if start <= stem_time(stem) < end}


def read_ledger_polls(directory: Path) -> list[tuple[datetime, str]]:
    """``(poll_time, document stem)`` for every row of every monthly ledger."""
    polls: list[tuple[datetime, str]] = []
    for path in sorted(directory.glob("*.tsv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for number, row in enumerate(csv.DictReader(handle, delimiter="\t"), 2):
                if not row.get("poll_time_utc") or not row.get("last_update_date"):
                    raise ValueError(f"{path}:{number}: malformed ledger row")
                polls.append((_utc(row["poll_time_utc"]), row["last_update_date"]))
    return polls


def read_dispatch_windows(path: Path) -> list[tuple[datetime, datetime | None]]:
    """Execution intervals of ``calibration-poll.yml`` dispatches, one per job attempt.

    The input is the jobs API (``actions/runs/{id}/jobs?filter=all``) for every
    dispatch run: ``run_id``, ``started_at``, ``completed_at`` and ``conclusion``
    per job. A row's ``poll_time_utc`` is stamped while the job runs, so the
    job's ``started_at .. completed_at`` brackets every row the dispatch filed.

    Job times, never run times (PR #105 review, round 2). A run created while
    another poll run holds the concurrency group waits; its run-level
    ``created_at`` and ``run_started_at`` both stay at the moment it was queued
    (observed: run 37199708102 queued 11:43:39, ``run_started_at`` 11:43:39,
    job started 11:47:03), so a window built from them claims the rows of the
    scheduled run it was waiting behind. A run still waiting has no jobs at all,
    so it owns nothing; a skipped job never ran; a job still running owns
    everything after its start.
    """
    windows: list[tuple[datetime, datetime | None]] = []
    for job in json.loads(path.read_text(encoding="utf-8")):
        if not job.get("started_at") or job.get("conclusion") == "skipped":
            continue
        end = _utc(job["completed_at"]) if job.get("completed_at") else None
        windows.append((_utc(job["started_at"]), end))
    return windows


def scheduled_retrievals(
    polls: Iterable[tuple[datetime, str]],
    dispatches: Sequence[tuple[datetime, datetime | None]],
) -> set[str]:
    """Stems some scheduled run retrieved, with any ledger decision."""

    def by_dispatch(moment: datetime) -> bool:
        return any(start <= moment and (end is None or moment <= end) for start, end in dispatches)

    return {stem for moment, stem in polls if not by_dispatch(moment)}


def read_served(path: Path) -> set[str]:
    """Stamps the probe wrote with ``--served-out``, one per line."""
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _status(served: bool, held: bool, retrieved: bool) -> str:
    if held and not retrieved:
        return "backfilled"
    if held:
        return "captured" if served else "archived_not_served"
    return "MISSED"


def day_rows(
    day: date,
    served: set[str],
    held: set[str],
    retrieved: set[str],
    step_hours: str,
    run_id: str,
) -> list[CaptureRow]:
    """Classify every document proven to exist on ``day``.

    Served stamps outside ``day`` are dropped: the probe's window is closed at
    both ends, so the query at the following midnight can return a document of
    the previous day and nothing else, but the two windows must tile exactly.
    """
    start, end = _day_bounds(day)
    shown = {stem for stem in served if start <= stem_time(stem) < end}
    rows = []
    for stem in sorted(shown | held):
        flags = (stem in shown, stem in held, stem in retrieved)
        rows.append(CaptureRow(day, stem, *flags, _status(*flags), step_hours, run_id))
    if not rows:
        rows.append(CaptureRow(day, "-", False, False, False, NO_DOCUMENTS, step_hours, run_id))
    return rows


@dataclass(frozen=True)
class CaptureSummary:
    """The rolling capture figure over the settled span."""

    days: int
    exist: int
    held: int
    missed: int
    backfilled: int

    @property
    def rate(self) -> float | None:
        return self.held / self.exist if self.exist else None


def summarise(rows: Sequence[CaptureRow], today: date) -> CaptureSummary:
    """Capture over the settled span ending ``today - SETTLE_DAYS``.

    ``held`` counts what the pipeline retrieved (``captured``,
    ``archived_not_served``); ``missed`` counts what it did not (``MISSED``, and
    ``backfilled``, which only a person recovered). The rate is an **upper**
    bound, like NC-058, because a document living less than one grid step can
    escape the enumeration too.
    """
    span = set(settled_span(today))
    inside = [row for row in rows if row.day in span]
    status = [row.status for row in inside]
    held = sum(status.count(name) for name in HELD)
    missed = sum(status.count(name) for name in MISSED_BY_PIPELINE)
    backfilled = status.count("backfilled")
    return CaptureSummary(len({row.day for row in inside}), held + missed, held, missed, backfilled)


def append_rows(path: Path, rows: Sequence[CaptureRow]) -> None:
    """Append ``rows`` by replacing the file atomically. LF on every platform.

    The new content goes to a sibling temporary file first and is moved over the
    record with ``os.replace``, so a job killed at any instant leaves either the
    old record or the new one, never a truncated row.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    if not path.exists():
        writer.writerow(CAPTURE_FIELDS)
    writer.writerows(row.fields() for row in rows)
    existing = path.read_bytes() if path.exists() else b""
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(existing + buffer.getvalue().encode("utf-8"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    retrieved = scheduled_retrievals(
        read_ledger_polls(args.root / "ledger"), read_dispatch_windows(args.dispatches)
    )
    rows = day_rows(day, read_served(args.served), held, retrieved, args.step, args.run_id)
    append_rows(capture, rows)
    status = [row.status for row in rows]
    print(
        f"{day}: captured {status.count('captured')}, MISSED {status.count('MISSED')}, "
        f"backfilled {status.count('backfilled')}, "
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
    record.add_argument(
        "--dispatches",
        type=Path,
        required=True,
        help="JSON array of the jobs (`actions/runs/{id}/jobs?filter=all`: run_id, "
        "started_at, completed_at, conclusion) of every calibration-poll.yml dispatch",
    )
    record.add_argument("--step", required=True, help="enumeration step in hours, recorded")
    record.add_argument("--run-id", required=True, help="Actions run id, recorded")
    args = parser.parse_args(list(argv) if argv is not None else None)
    return _pending(args) if args.mode == "pending" else _record(args)


if __name__ == "__main__":
    sys.exit(main())
