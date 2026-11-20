"""Hour of day of ``ibm_fez``'s chip-wide T1 recalibrations, for the #125 submission hour.

Protocol: ``docs/evidence/hardware-reading-vs-level/README.md`` §7, committed before this
script. A chip-wide recalibration is the persistence run's (``measure_persistence_band.py``,
``recal_times``, imported and run unchanged): consecutive archive files in which at least 20%
of the qubits with a T1 ``date`` in both have a new one. Each event is dated by the later file's
``last_update_date`` (published) and by the median new T1 ``date`` of the changed qubits
(measured). The script reports when events land and what a daily submission at minute :45 of
each UTC hour would see. It takes no decision.

Usage, from the repository root::

    PYTHONPATH=src python docs/evidence/hardware-reading-vs-level/measure_recal_hours.py \\
        --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b \\
        --out docs/evidence/hardware-reading-vs-level/
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from bisect import bisect_right
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GUARD_FILES = 2249
GUARD_EVENTS = 151
SUBMIT_MINUTE = 45
LOOKAHEAD_H = (1, 3, 6)
WINDOW_H = 4
HOUR = 3600.0


def persistence_module() -> ModuleType:
    path = ROOT / "docs" / "evidence" / "persistence-band" / "measure_persistence_band.py"
    spec = importlib.util.spec_from_file_location("measure_persistence_band", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def recal_events(files: list[Any], fraction: float, epoch: Any) -> list[dict[str, Any]]:
    """The persistence run's events, with the measured time and the share that changed."""
    out: list[dict[str, Any]] = []
    for prev, cur in pairwise(files):
        pairs = [
            (a, b)
            for a, b in zip(prev.t1_dates, cur.t1_dates, strict=False)
            if a is not None and b is not None
        ]
        if not pairs:
            continue
        changed = [b for a, b in pairs if a != b]
        if len(changed) / len(pairs) >= fraction:
            out.append(
                {
                    "published": float(cur.time),
                    "measured": float(np.median([epoch(b) for b in changed])),
                    "share": len(changed) / len(pairs),
                    "comparable": len(pairs),
                }
            )
    return out


def _utc(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s, UTC)


def busiest_window(counts: list[int], width: int = WINDOW_H) -> tuple[int, int]:
    """Start hour and total of the busiest ``width``-hour window, wrapping past midnight."""
    totals = [sum(counts[(s + k) % 24] for k in range(width)) for s in range(24)]
    best = max(range(24), key=lambda s: (totals[s], -s))
    return best, totals[best]


def submission_table(
    published: list[float], first_day: date, last_day: date
) -> list[dict[str, Any]]:
    """For a daily submission at h:45 UTC: age of the latest event and the next-event risk."""
    rows: list[dict[str, Any]] = []
    days = [first_day + timedelta(days=k) for k in range((last_day - first_day).days + 1)]
    for h in range(24):
        ages: list[float] = []
        within = dict.fromkeys(LOOKAHEAD_H, 0)
        for day in days:
            t = datetime(day.year, day.month, day.day, h, SUBMIT_MINUTE, tzinfo=UTC).timestamp()
            i = bisect_right(published, t) - 1
            if i >= 0:
                ages.append((t - published[i]) / HOUR)
            j = bisect_right(published, t)
            if j < len(published):
                for x in LOOKAHEAD_H:
                    if published[j] - t <= x * HOUR:
                        within[x] += 1
        row: dict[str, Any] = {
            "submit_utc": f"{h:02d}:{SUBMIT_MINUTE:02d}",
            "submit_istanbul": f"{(h + 3) % 24:02d}:{SUBMIT_MINUTE:02d}",
            "days": len(days),
            "median_hours_since_event": round(float(np.median(ages)), 2) if ages else "",
        }
        for x in LOOKAHEAD_H:
            row[f"share_event_within_{x}h"] = round(within[x] / len(days), 4) if days else ""
        rows.append(row)
    return rows


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", required=True)
    parser.add_argument("--backend", default="ibm_fez")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    pb = persistence_module()
    files = pb.load_files(args.repo, args.ref, args.backend)
    reference = pb.recal_times(files)
    events = recal_events(files, pb.RECAL_FRACTION, pb._epoch)
    guard = {
        "files": {"expected": GUARD_FILES, "observed": len(files)},
        "events": {"expected": GUARD_EVENTS, "observed": len(events)},
        "identical_to_recal_times": [e["published"] for e in events] == reference,
    }
    passed = (
        len(files) == GUARD_FILES
        and len(events) == GUARD_EVENTS
        and bool(guard["identical_to_recal_times"])
    )
    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "ref": args.ref,
        "backend": args.backend,
        "guard": {"passed": passed, **guard},
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    if not passed:
        (args.out / "recal-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        print("reproduction guard failed; no figure is written", file=sys.stderr)
        return 1

    event_rows: list[dict[str, Any]] = []
    prev: float | None = None
    for e in events:
        pub, mea = _utc(e["published"]), _utc(e["measured"])
        event_rows.append(
            {
                "published_utc": pub.isoformat(),
                "published_hour": pub.hour,
                "measured_utc": mea.isoformat(),
                "measured_hour": mea.hour,
                "share_changed": round(e["share"], 4),
                "comparable": e["comparable"],
                "hours_since_previous": round((e["published"] - prev) / HOUR, 2)
                if prev is not None
                else "",
            }
        )
        prev = e["published"]
    _write_tsv(args.out / "recal-events.tsv", event_rows)

    pub_counts = [0] * 24
    mea_counts = [0] * 24
    for row in event_rows:
        pub_counts[row["published_hour"]] += 1
        mea_counts[row["measured_hour"]] += 1
    published = [e["published"] for e in events]
    first_day = _utc(published[0]).date() + timedelta(days=1)
    last_file = _utc(float(files[-1].time))
    last_day = last_file.date()
    if last_file < datetime(last_day.year, last_day.month, last_day.day, 23, 45, tzinfo=UTC):
        last_day -= timedelta(days=1)
    submissions = submission_table(published, first_day, last_day)
    hour_rows = [
        {"hour_utc": h, "events_published": pub_counts[h], "events_measured": mea_counts[h]}
        | dict(submissions[h])
        for h in range(24)
    ]
    _write_tsv(args.out / "recal-hours.tsv", hour_rows)

    by_month: Counter[tuple[str, int]] = Counter(
        (str(row["published_utc"])[:7], int(row["published_hour"])) for row in event_rows
    )
    months = sorted({m for m, _ in by_month})
    _write_tsv(
        args.out / "recal-by-month.tsv",
        [{"month": m} | {f"h{h:02d}": by_month[(m, h)] for h in range(24)} for m in months],
    )

    gaps = [float(r["hours_since_previous"]) for r in event_rows if r["hours_since_previous"] != ""]
    pub_start, pub_total = busiest_window(pub_counts)
    mea_start, mea_total = busiest_window(mea_counts)
    summary.update(
        {
            "files": len(files),
            "first_file": _utc(float(files[0].time)).isoformat(),
            "last_file": last_file.isoformat(),
            "events": len(events),
            "hours_between_events": {
                "median": float(np.median(gaps)),
                "p10": float(np.quantile(gaps, 0.10)),
                "p90": float(np.quantile(gaps, 0.90)),
            },
            "busiest_published_window": {
                "start_hour_utc": pub_start,
                "hours": WINDOW_H,
                "events": pub_total,
                "share": round(pub_total / len(events), 4),
            },
            "busiest_measured_window": {
                "start_hour_utc": mea_start,
                "hours": WINDOW_H,
                "events": mea_total,
                "share": round(mea_total / len(events), 4),
            },
            "submission_days": {"first": first_day.isoformat(), "last": last_day.isoformat()},
        }
    )
    (args.out / "recal-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "guard",
                    "events",
                    "hours_between_events",
                    "busiest_published_window",
                    "busiest_measured_window",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
