"""Reproduce the #54 capture-rate claims from the calibration archive at a pinned commit.

Issue #54 asked what share of the calibration documents IBM publishes the
pipeline actually captures during ordinary operation. NC-032 answered it once,
for 2026-08-12..14, before the #53 backfill healed that very window and made
the row vacuous. Since 2026-09-11 the pipeline has two acquisition paths, the
hourly poll and the daily sweep of #49, so the question now splits in three:

- **ledger** -- Of the documents the archive holds for a stamp window, which
  path filed each one first? Answers "how much does the hourly sampler catch
  on its own", which is the aliasing loss #54 described, measured without any
  IBM call because the ADR-025 ledger already records every filing.
- **ledger, state counterfactual** -- Of the distinct device states first seen
  in the window, how many are carried by *no* hourly-filed document anywhere
  in the archive? Those states exist only because the sweep ran. This is the
  unit the training floor counts (NC-012), and it is smaller than the document
  loss because about half of all documents repeat the previous state.
- **enumeration** -- Given the output of a read-only ``--enumerate`` probe
  (``calibration-historical-probe.yml``), which documents IBM serves for the
  window are absent from the archive? That is what hourly *and* sweep together
  still miss, and it is the figure #54 closes on. The same diff also measures
  the probe grid's own recall, exactly as run C measured NC-031.

How a ledger row is attributed to a path
----------------------------------------

The ledger has no mode column. ADR-025 fixes its four columns and a change to
ledger semantics needs the advisor's sign-off (``docs/team.md``), so the path
is derived instead: ``file_snapshots.sh`` writes one row per staged document
under a single ``poll_time_utc``, so a live poll writes exactly one row and a
sweep writes one per distinct document its window returned.

    poll_time with 1 row   -> hourly
    poll_time with >1 rows -> sweep   (scheduled sweep or dispatched backfill)

The rule misreads one case: a sweep whose whole window returned a single
document, which needs IBM to publish nothing for 48 h. That row is then a
``duplicate`` of a document already held, never ``new``, so it cannot move the
attribution of any document. A dispatched backfill is counted as ``sweep``;
there is none in the registered windows (every ``workflow_dispatch`` of
``calibration-poll.yml`` predates 2026-09-10).

"Sweep" means the sweep *run*, not only its historical walk: ``poll_once``
fetches the current document before any historical query
(``src/superconducted/calibration/poller.py``), so a sweep run also files the
live document under its ``poll_time``. That is one document per run at most,
and NC-056 carries the bound it implies (15 of the 16 runs in its window).

Window conventions
------------------

``ledger`` uses a half-open ``[start, end)`` so days tile without overlap.
``enumeration`` uses the probe's own closed ``[start, end]`` (its loop runs
``while t <= end`` and it lists stamps with ``start <= s <= end``), so two
probe runs sharing a boundary instant leave no seam.

Reads the archive through ``git show``, so it needs no checkout of the data
branch, only that ``--ref`` is reachable in ``--repo`` (fetch
``calibration-data`` first). Read-only; standard library only.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_REF = "b70d7b4"
DEFAULT_BACKEND = "ibm_fez"
HOURLY = "hourly"
SWEEP = "sweep"
UNLEDGERED = "unledgered"

_STEM = re.compile(r"(\d{8}T\d{12}Z)\.json$")
# One listed stamp in the probe's output, as ``_enumerate_window`` prints it:
# the filename-form stamp followed by its ISO form. Unanchored, because
# ``gh run view --log`` prefixes every line with the job, step and a timestamp.
_PROBE_STAMP = re.compile(r"(\d{8}T\d{12}Z)\s+\d{4}-\d{2}-\d{2}T")
_PROBE_SUMMARY = "distinct documents returned"
_PROBE_FAILED = "PROBE FAILED"


@dataclass(frozen=True)
class LedgerRow:
    """One ADR-025 ledger record, restricted to the columns read here."""

    poll_time: str
    backend: str
    stem: str
    decision: str


@dataclass(frozen=True)
class IndexRow:
    """One ``health/state-index.tsv`` record: a document and its qubit-block digest."""

    stem: str
    digest: str


def parse_stem(stem: str) -> datetime:
    """``20260913T012345000000Z`` -> tz-aware UTC datetime."""
    return datetime.strptime(stem.removesuffix("Z"), "%Y%m%dT%H%M%S%f").replace(tzinfo=UTC)


def parse_iso(value: str) -> datetime:
    """ISO-8601 with or without ``Z``, normalised to UTC."""
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def classify_polls(rows: Iterable[LedgerRow]) -> dict[str, str]:
    """Map each ``poll_time`` to ``hourly`` or ``sweep`` by its row count (module docstring)."""
    counts = Counter(row.poll_time for row in rows)
    return {poll: SWEEP if n > 1 else HOURLY for poll, n in counts.items()}


def first_filed_by(rows: Sequence[LedgerRow]) -> dict[str, str]:
    """Map each document stem to the path whose ``new`` row filed it first.

    Rows are taken in ledger order, which is append order and therefore poll
    order. A stem is ``new`` at most once in practice, because the filing it
    records makes every later sighting a ``duplicate``; the first one wins
    regardless, so a malformed repeat cannot re-attribute a document.
    """
    kind = classify_polls(rows)
    result: dict[str, str] = {}
    for row in rows:
        if row.decision == "new" and row.stem not in result:
            result[row.stem] = kind[row.poll_time]
    return result


def ledger_split(
    archive: Iterable[str], first: dict[str, str], start: datetime, end: datetime
) -> Counter[str]:
    """Count archived stems in ``[start, end)`` by the path that filed them first.

    A stem with no ``new`` row is ``unledgered``: it was filed before the
    ledger existed (2026-09-02) or by a path that wrote no row. A non-zero
    count inside a registered window means the attribution is incomplete and
    the figure must not be cited.
    """
    return Counter(
        first.get(stem, UNLEDGERED) for stem in archive if start <= parse_stem(stem) < end
    )


def state_counterfactual(
    index: Sequence[IndexRow], first: dict[str, str], start: datetime, end: datetime
) -> tuple[int, int, int]:
    """``(new_states, reachable_from_hourly, sweep_only)`` for states first seen in the window.

    A state is *new in the window* when the earliest document carrying its
    digest is stamped in ``[start, end)``, the same earliest-``last_update_date``
    rule as ``pipeline_health.first_sightings`` and for the same reason: the
    index's own ``is_new_state`` column is decided by append order, which a
    sweep makes non-chronological.

    A new state is *sweep-only* when no document filed by the hourly path, at
    any stamp in the archive, carries its digest. Looking beyond the window
    matters: a state the sweep recovered on Tuesday that the hourly poll saw
    again on Thursday was not lost to the sampler, only delayed.
    """
    earliest: dict[str, datetime] = {}
    for row in index:
        moment = parse_stem(row.stem)
        seen = earliest.get(row.digest)
        if seen is None or moment < seen:
            earliest[row.digest] = moment
    new_states = {digest for digest, moment in earliest.items() if start <= moment < end}
    hourly_states = {row.digest for row in index if first.get(row.stem) == HOURLY}
    reachable = new_states & hourly_states
    return len(new_states), len(reachable), len(new_states - reachable)


def parse_probe_log(text: str) -> set[str]:
    """Stamps a completed, clean ``--enumerate`` run listed for its window.

    Refuses rather than returning a partial set: a log without the summary
    line did not finish, and one carrying ``PROBE FAILED`` says in its own
    words that the list is incomplete. A partial list would read as documents
    the pipeline missed that were really documents the probe never asked for.
    """
    if _PROBE_SUMMARY not in text:
        raise ValueError("probe log has no summary line; the run did not finish")
    if _PROBE_FAILED in text:
        raise ValueError("probe log reports PROBE FAILED; its stamp list is incomplete")
    return set(_PROBE_STAMP.findall(text))


def enumeration_rows(
    served: set[str],
    archive: Iterable[str],
    first: dict[str, str],
    start: datetime,
    end: datetime,
) -> list[tuple[str, str, str, str, str]]:
    """Per-document diff of served against held over the closed window ``[start, end]``.

    Columns: stem, served, in_archive, first_filed_by, status. ``status`` uses
    run C's vocabulary (``docs/evidence/aug-gap-enumeration``): ``captured``,
    ``MISSED`` (served, not held) and ``archived_not_served`` (held, not
    served, which is the probe's own recall shortfall).
    """

    def inside(stem: str) -> bool:
        return start <= parse_stem(stem) <= end

    held = {stem for stem in archive if inside(stem)}
    shown = {stem for stem in served if inside(stem)}
    rows: list[tuple[str, str, str, str, str]] = []
    for stem in sorted(held | shown):
        is_served, is_held = stem in shown, stem in held
        if is_served and is_held:
            status = "captured"
        elif is_served:
            status = "MISSED"
        else:
            status = "archived_not_served"
        rows.append(
            (
                stem,
                "yes" if is_served else "no",
                "yes" if is_held else "no",
                first.get(stem, "none" if not is_held else UNLEDGERED),
                status,
            )
        )
    return rows


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def read_archive(repo: Path, ref: str, backend: str) -> list[str]:
    """Every snapshot stem for ``backend`` at ``ref``, across all month directories."""
    out = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", "snapshots/").decode("utf-8")
    stems: list[str] = []
    for path in out.splitlines():
        match = _STEM.search(path)
        if match and f"/{backend}/" in path:
            stems.append(match.group(1))
    return sorted(stems)


def read_ledger(repo: Path, ref: str, backend: str) -> list[LedgerRow]:
    """All monthly ledgers at ``ref`` in month order, restricted to ``backend``."""
    out = _git(repo, "ls-tree", "--name-only", ref, "--", "ledger/").decode("utf-8")
    rows: list[LedgerRow] = []
    for path in sorted(p for p in out.splitlines() if p.endswith(".tsv")):
        text = _git(repo, "show", f"{ref}:{path}").decode("utf-8")
        for record in csv.DictReader(io.StringIO(text), delimiter="\t"):
            if record["backend"] != backend:
                continue
            rows.append(
                LedgerRow(
                    record["poll_time_utc"],
                    record["backend"],
                    record["last_update_date"],
                    record["decision"],
                )
            )
    return rows


def read_index(repo: Path, ref: str) -> list[IndexRow]:
    """``health/state-index.tsv`` at ``ref``."""
    text = _git(repo, "show", f"{ref}:health/state-index.tsv").decode("utf-8")
    return [
        IndexRow(record["snapshot_filename"].removesuffix(".json"), record["qubit_digest"])
        for record in csv.DictReader(io.StringIO(text), delimiter="\t")
    ]


def _share(part: int, whole: int) -> str:
    return f"{part}/{whole} = {part / whole:.1%}" if whole else f"{part}/0"


def _run_ledger(args: argparse.Namespace, repo: Path) -> int:
    start, end = parse_iso(args.start), parse_iso(args.end)
    rows = read_ledger(repo, args.ref, args.backend)
    first = first_filed_by(rows)
    archive = read_archive(repo, args.ref, args.backend)
    split = ledger_split(archive, first, start, end)
    held = sum(split.values())
    sweeps = sorted(poll for poll, kind in classify_polls(rows).items() if kind == SWEEP)
    in_run = [p for p in sweeps if start <= parse_iso(p) < end]
    print(f"ref            : {args.ref}   backend: {args.backend}")
    print(f"stamp window   : [{start.isoformat()}, {end.isoformat()})")
    print(f"documents held : {held}")
    print(f"  first filed by hourly poll : {_share(split[HOURLY], held)}")
    print(f"  first filed by sweep       : {_share(split[SWEEP], held)}")
    print(f"  unledgered                 : {split[UNLEDGERED]}")
    print(f"sweep poll instants inside the window: {len(in_run)}")
    new_states, reachable, sweep_only = state_counterfactual(
        read_index(repo, args.ref), first, start, end
    )
    print(f"device states first seen in the window : {new_states}")
    print(f"  carried by some hourly-filed document : {_share(reachable, new_states)}")
    print(f"  carried ONLY by sweep-filed documents : {_share(sweep_only, new_states)}")
    if split[UNLEDGERED]:
        print("\nATTRIBUTION INCOMPLETE: unledgered documents inside the window.")
        return 1
    return 0


def _run_enumeration(args: argparse.Namespace, repo: Path) -> int:
    start, end = parse_iso(args.start), parse_iso(args.end)
    served: set[str] = set()
    for log in args.probe_log:
        served |= parse_probe_log(Path(log).read_text(encoding="utf-8"))
    first = first_filed_by(read_ledger(repo, args.ref, args.backend))
    archive = read_archive(repo, args.ref, args.backend)
    rows = enumeration_rows(served, archive, first, start, end)
    status = Counter(row[4] for row in rows)
    held = status["captured"] + status["archived_not_served"]
    exist = len(rows)
    print(f"ref          : {args.ref}   backend: {args.backend}")
    print(f"stamp window : [{start.isoformat()}, {end.isoformat()}]")
    print(
        f"probe logs   : {len(args.probe_log)}   stamps served inside the window: "
        f"{status['captured'] + status['MISSED']}"
    )
    for key in ("captured", "MISSED", "archived_not_served"):
        print(f"  {key:<20}: {status[key]}")
    print(f"proven to exist (served or held) : {exist}")
    print(f"capture, upper bound  held/exist : {_share(held, exist)}")
    print(f"probe recall  captured/held      : {_share(status['captured'], held)}")
    if args.tsv:
        with open(args.tsv, "w", encoding="utf-8", newline="\n") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(
                ("last_update_date", "served_by_probe", "in_archive", "first_filed_by", "status")
            )
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {args.tsv}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=".", help="repository holding --ref")
    parser.add_argument("--ref", default=DEFAULT_REF, help="calibration-data commit to read")
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    sub = parser.add_subparsers(dest="mode", required=True)
    ledger = sub.add_parser("ledger", help="hourly-vs-sweep split and state counterfactual")
    ledger.add_argument("--start", required=True, help="ISO-8601 UTC, inclusive")
    ledger.add_argument("--end", required=True, help="ISO-8601 UTC, exclusive")
    enum = sub.add_parser("enumeration", help="diff read-only probe output against the archive")
    enum.add_argument("--start", required=True, help="ISO-8601 UTC, inclusive")
    enum.add_argument("--end", required=True, help="ISO-8601 UTC, inclusive")
    enum.add_argument("--probe-log", nargs="+", required=True, help="saved probe run logs")
    enum.add_argument("--tsv", help="write the per-document diff here")
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo = Path(args.repo)
    if args.mode == "ledger":
        return _run_ledger(args, repo)
    return _run_enumeration(args, repo)


if __name__ == "__main__":
    sys.exit(main())
