"""Issue #104, amendment 2: which UTC days had a scheduled sweep run, read from the ledger.

    PYTHONPATH=. python docs/evidence/capture-rate-2026-11/sweep_days.py --ref <commit>
        --runs docs/evidence/capture-rate-2026-11/scheduled-runs-2026-09-27_11-15.tsv
        --from YYYY-MM-DD --to YYYY-MM-DD                              (cwd: the repository root)

A sweep run is a ledger poll time with more than one row, the rule of
``scripts.capture_rate_analysis.classify_polls`` (a sweep files one row per distinct document its
window returned; an hourly poll files one). A dispatched backfill makes the same shape, so a sweep
poll time counts as **scheduled** only when it falls inside a scheduled run of
``calibration-poll.yml``, between that run's ``run_started_at`` and ``updated_at`` in ``--runs``
(the Actions runs API with ``event=schedule``, saved as a file so the reading can be repeated after
GitHub expires the history). The workflow's concurrency group serialises its runs, so a dispatch
cannot run inside a scheduled run's interval.

Amendment 2's rule reads this for E: day D is uncovered when the day after it, D+1, had no
scheduled sweep, because only D+1's 48 h window covers D entirely. Prints one line per day and the
days with none. Reads only; exits 0.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts.capture_rate_analysis import SWEEP, classify_polls, parse_iso, read_ledger


def scheduled_intervals(path: Path) -> list[tuple[datetime, datetime]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            (parse_iso(row["run_started_at"]), parse_iso(row["updated_at"]))
            for row in csv.DictReader(handle, delimiter="\t")
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", required=True, help="a calibration-data commit")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--from", dest="first", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="last", type=date.fromisoformat, required=True)
    parser.add_argument("--backend", default="ibm_fez")
    args = parser.parse_args()

    rows = read_ledger(Path("."), args.ref, args.backend)
    sizes: dict[str, int] = defaultdict(int)
    for row in rows:
        sizes[row.poll_time] += 1
    intervals = scheduled_intervals(args.runs)
    by_day: dict[date, list[tuple[str, int]]] = defaultdict(list)
    for poll, kind in classify_polls(rows).items():
        when = parse_iso(poll)
        if kind == SWEEP and any(start <= when <= end for start, end in intervals):
            by_day[when.date()].append((when.strftime("%H:%M:%S"), sizes[poll]))
    print(f"calibration-data {args.ref}; {len(rows)} ledger rows; {len(intervals)} scheduled runs")
    days = [args.first + timedelta(days=k) for k in range((args.last - args.first).days + 1)]
    for day in days:
        found = sorted(by_day.get(day, []))
        text = ", ".join(f"{t} ({n} rows)" for t, n in found) or "none"
        print(f"{day}  scheduled sweep: {text}")
    without = [str(d) for d in days if d not in by_day]
    print(f"days with a scheduled sweep: {len(days) - len(without)} of {len(days)}")
    print(f"days without one: {', '.join(without) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
