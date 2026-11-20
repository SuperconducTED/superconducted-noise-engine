"""Issue #104: capture by week and by document lifetime, read from the capture record.

    PYTHONPATH=. python docs/evidence/capture-rate-2026-11/capture_lifetimes.py --ref <commit>
        [--from YYYY-MM-DD] [--to YYYY-MM-DD]                      (cwd: the repository root)

Reads ``health/capture.tsv`` from the given ``calibration-data`` commit by blob, never from a
checkout, and parses it with ``scripts.capture_record.read_capture``, so "held" and "missed" mean
what the dashboard's ``capture_7d`` means (held: ``captured``, ``archived_not_served``; missed:
``MISSED``, ``backfilled``).

A document's lifetime is the time until the next document in the record (a historical query at
instant q returns the latest document stamped at or before q). It is unknown when any UTC day from
the document's date to its successor's date is missing from the record, or when it has no
successor; those documents are counted and left out of every lifetime figure.

``--from`` and ``--to`` select documents by the UTC date of their stamp (default: the whole
record); lifetimes always use the successor in the whole record. ``--exclude-day``, repeatable,
drops a day of that selection whose covering sweep was skipped (amendment 2: the scheduled sweep
dated the day after it did not run, read by ``sweep_days.py``): its documents leave the selection
and the weekly table, but stay successors for lifetimes. An excluded day outside the selection, or
given twice, is refused. The line starting ``P1`` is the count the prediction in
``docs/implementations/2026-11-15-issue-104-sweep-half-hour-step.md`` reads. Prints only; exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from scripts.capture_record import HELD, MISSED_BY_PIPELINE, NO_DOCUMENTS, read_capture

RECORD = "health/capture.tsv"
BUCKETS = (
    (0.0, 0.25, "under 0.25 h"),
    (0.25, 0.5, "0.25 to 0.5 h"),
    (0.5, 1.0, "0.5 to 1 h"),
    (1.0, 2.0, "1 to 2 h"),
    (2.0, 6.0, "2 to 6 h"),
    (6.0, float("inf"), "6 h or more"),
)
STEPS = (1.0, 0.5, 0.25)
P1_STEP = 0.5


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def stamp(stem: str) -> datetime:
    return datetime.strptime(stem, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)


def days_between(first: date, last: date) -> list[date]:
    return [first + timedelta(days=k) for k in range((last - first).days + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", required=True, help="a calibration-data commit")
    parser.add_argument("--from", dest="first", type=date.fromisoformat, default=None)
    parser.add_argument("--to", dest="last", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--exclude-day", dest="exclude", type=date.fromisoformat, action="append", default=[]
    )
    args = parser.parse_args()

    commit = git("rev-parse", "--verify", f"{args.ref}^{{commit}}").decode().strip()
    blob = git("rev-parse", f"{commit}:{RECORD}").decode().strip()
    data = git("cat-file", "blob", blob)
    print(f"calibration-data {commit}  {RECORD}")
    print(f"  blob {blob}; sha256 {hashlib.sha256(data).hexdigest()}; {len(data)} bytes")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "capture.tsv"
        path.write_bytes(data)
        rows = read_capture(path)

    known_status = set(HELD) | set(MISSED_BY_PIPELINE) | {NO_DOCUMENTS}
    unknown_status = sorted({row.status for row in rows} - known_status)
    if unknown_status:
        raise SystemExit(f"unexpected status values: {unknown_status}")
    recorded = {row.day for row in rows}
    docs_rows = [row for row in rows if row.status != NO_DOCUMENTS]
    by_stem: dict[str, list[str]] = defaultdict(list)
    for row in docs_rows:
        by_stem[row.stem].append(row.status)
    held = {stem: any(s in HELD for s in statuses) for stem, statuses in by_stem.items()}
    when = {stem: stamp(stem) for stem in by_stem}
    order = sorted(by_stem, key=lambda stem: when[stem])

    first_day, last_day = min(recorded), max(recorded)
    missing = [d for d in days_between(first_day, last_day) if d not in recorded]
    print("\nrecord")
    print(f"  rows {len(rows)}; document rows {len(docs_rows)}; documents {len(by_stem)}")
    print(f"  documents listed on more than one row: {sum(len(s) > 1 for s in by_stem.values())}")
    print(f"  no_documents rows: {len(rows) - len(docs_rows)}")
    print(f"  status: {dict(sorted(Counter(row.status for row in rows).items()))}")
    print(f"  step_hours: {dict(sorted(Counter(row.step_hours for row in rows).items()))}")
    print(f"  capture runs (distinct run_id): {len({row.run_id for row in rows})}")
    print(
        f"  recorded days {len(recorded)}, {first_day} to {last_day}; missing: "
        f"{', '.join(map(str, missing)) or 'none'}"
    )
    off_day = sum(when[row.stem].date() != row.day for row in docs_rows)
    print(f"  document rows whose stamp date differs from their day: {off_day}")

    lifetime: dict[str, float | None] = {}
    for current, successor in zip(order, [*order[1:], None], strict=True):
        if successor is None:
            lifetime[current] = None
            continue
        span = days_between(when[current].date(), when[successor].date())
        ok = all(d in recorded for d in span)
        hours = (when[successor] - when[current]).total_seconds() / 3600
        lifetime[current] = hours if ok else None

    lo = args.first or first_day
    hi = args.last or last_day
    excluded = sorted(set(args.exclude))
    if len(excluded) != len(args.exclude):
        raise SystemExit("an --exclude-day is given twice")
    outside = [d for d in excluded if not lo <= d <= hi]
    if outside:
        raise SystemExit(f"--exclude-day outside {lo} to {hi}: {', '.join(map(str, outside))}")
    chosen = [
        stem
        for stem in order
        if lo <= when[stem].date() <= hi and when[stem].date() not in excluded
    ]
    print(f"\nselected documents stamped {lo} to {hi}: {len(chosen)}")
    if excluded:
        kept = sum(lo <= d <= hi and d not in excluded for d in recorded)
        print(
            f"excluded days (amendment 2, the D+1 sweep skipped): "
            f"{', '.join(map(str, excluded))}; recorded days left: {kept}"
        )

    weeks: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    week_days: dict[tuple[int, int], set[date]] = defaultdict(set)
    for stem in chosen:
        iso = when[stem].date().isocalendar()
        weeks[(iso[0], iso[1])][0] += held[stem]
        weeks[(iso[0], iso[1])][1] += 1
    for d in recorded:
        if lo <= d <= hi and d not in excluded:
            iso = d.isocalendar()
            week_days[(iso[0], iso[1])].add(d)
    print("\nweek       recorded days   held / exist   capture")
    for key in sorted(weeks):
        h, e = weeks[key]
        span_days = sorted(week_days[key])
        label = f"{span_days[0]}..{span_days[-1]}" if span_days else "-"
        week = f"{key[0]}-W{key[1]:02d}"
        print(f"{week}   {len(span_days)} ({label})   {h:4d} / {e:4d}   {h / e:.1%}")
    total_held = sum(held[stem] for stem in chosen)
    total = len(chosen)
    print(
        f"total      {total_held} / {total}   capture {total_held / total:.1%}; "
        f"missed {total - total_held}"
    )

    known = [stem for stem in chosen if lifetime[stem] is not None]
    print(
        f"\nlifetimes known for {len(known)} of {len(chosen)} documents "
        f"({len(chosen) - len(known)} unknown: successor on a missing day, or none)"
    )
    print("lifetime          held   missed")
    for low, high, label in BUCKETS:
        inside = [stem for stem in known if low <= (lifetime[stem] or 0.0) < high]
        n_held = sum(held[stem] for stem in inside)
        print(f"{label:15} {n_held:6d} {len(inside) - n_held:8d}")
    missed_life = sorted(lifetime[stem] or 0.0 for stem in known if not held[stem])
    if missed_life:
        print(
            f"missed lifetimes: median {statistics.median(missed_life):.3f} h, "
            f"longest {missed_life[-1]:.3f} h"
        )
    for step in STEPS:
        long_lived = [stem for stem in known if (lifetime[stem] or 0.0) >= step]
        n_missed = sum(not held[stem] for stem in long_lived)
        print(f"lived {step} h or more: {len(long_lived)} documents, {n_missed} missed")
    p1 = [stem for stem in known if (lifetime[stem] or 0.0) >= P1_STEP and not held[stem]]
    p1_all = sum((lifetime[stem] or 0.0) >= P1_STEP for stem in known)
    print(
        f"P1: missed among documents with a known lifetime of {P1_STEP} h or more: "
        f"{len(p1)} of {p1_all}"
    )
    for stem in p1:
        print(f"  {stem}  lifetime {lifetime[stem]:.3f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
