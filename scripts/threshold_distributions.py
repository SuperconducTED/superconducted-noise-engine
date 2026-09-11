"""Measure the distributions behind issue #48 section 7.3's alarm thresholds.

A threshold is a numerical claim: it asserts how often it will fire. Section
7.3's own decision says so, and says none of its four numbers had a register
row. This script produces the rows' source.

It reports two distributions, and keeping them apart is the point:

``ledger_hour_coverage_72h``
    The metric the coverage thresholds are applied to, recomputed exactly as
    ``pipeline_health.build_metrics`` computes it: an hour counts when at least
    one ledger row falls inside it, and the window is the 72 hours preceding a
    given hour boundary. Rolling that window one hour at a time over the ledger
    span gives the distribution. Only windows lying wholly inside the span are
    counted, because a window reaching back past the first ledger row reads low
    for a reason that has nothing to do with the scheduler.

Intervals between consecutive distinct device states
    What ``hours_since_last_new_state`` samples. First sightings are derived
    from ``last_update_date`` rather than read from ``is_new_state``, matching
    ``pipeline_health.first_sightings`` and for the same reason: that column is
    decided by append order and a sweep files documents out of order.

**The two rest on very different amounts of evidence, and a caller must not
average over that.** The ledger begins when ADR-025 landed, so the coverage
distribution covers days. The state index was backfilled over the whole archive,
so the staleness distribution covers months. Section 7.3 quoted 399 coverage
windows and "four months of history"; no poll-time record in this repository
reaches four months, so any figure of that shape came from a proxy rather than
from this metric. The report prints the span it actually measured, in hours and
in windows, next to every number, so the next reader cannot repeat that.

Percentiles are nearest-rank on the sorted sample: the p-th percentile is the
value at index ``ceil(p / 100 * n) - 1``. No interpolation, so every number
printed is a value that was actually observed.

Stdlib only, per issue #48 NFR-4.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

WINDOW_HOURS = 72
"""Width of the coverage window, fixed by FR-4's ``ledger_hour_coverage_72h``."""

COVERAGE_THRESHOLDS = (0.15, 0.50, 0.75)
"""Section 7.3's two alarm bounds and its recovery target, as fractions."""

STALENESS_THRESHOLDS = (12.0, 24.0)
"""Section 7.3's proposed amber and red staleness bounds, in hours."""


def _parse(stamp: str) -> datetime:
    """Read an ISO-8601 UTC stamp, tolerating both ``Z`` and ``+00:00``."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC)


def poll_hours(root: Path) -> set[datetime]:
    """Hour-truncated poll times from every ``ledger/*.tsv`` under ``root``.

    Truncation matches ``build_metrics``: several polls inside one hour make
    that hour covered exactly once, which is why coverage is not polls over 24.
    """
    fired: set[datetime] = set()
    for path in sorted(root.glob("ledger/*.tsv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                stamp = row.get("poll_time_utc")
                if stamp:
                    fired.add(_parse(stamp).replace(minute=0, second=0, microsecond=0))
    return fired


def coverage_windows(fired: Sequence[datetime] | set[datetime]) -> list[float]:
    """Rolling ``ledger_hour_coverage_72h`` over every window inside the span.

    Returns one fraction per hour boundary from ``first + 72 h`` through
    ``last`` inclusive. An empty or too-short ledger yields an empty list rather
    than a misleading zero.
    """
    if not fired:
        return []
    ordered = sorted(fired)
    first, last = ordered[0], ordered[-1]
    covered = set(ordered)
    windows: list[float] = []
    end = first + timedelta(hours=WINDOW_HOURS)
    while end <= last:
        start = end - timedelta(hours=WINDOW_HOURS)
        hits = sum(
            1 for offset in range(WINDOW_HOURS) if start + timedelta(hours=offset) in covered
        )
        windows.append(hits / WINDOW_HOURS)
        end += timedelta(hours=1)
    return windows


def state_intervals(root: Path) -> list[float]:
    """Hours between consecutive first sightings of a distinct device state.

    First sighting is the earliest ``last_update_date`` carrying a digest, so a
    sweep that files an older document for a long-known state does not register
    as a fresh acquisition.
    """
    index = root / "health" / "state-index.tsv"
    earliest: dict[str, datetime] = {}
    with index.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            digest, stamp = row.get("qubit_digest"), row.get("last_update_date")
            if not digest or not stamp:
                continue
            seen = earliest.get(digest)
            moment = _parse(stamp)
            if seen is None or moment < seen:
                earliest[digest] = moment
    ordered = sorted(earliest.values())
    return [(later - earlier).total_seconds() / 3600 for earlier, later in pairwise(ordered)]


def percentile(values: Sequence[float], point: float) -> float:
    """Nearest-rank percentile: an observed value, never an interpolated one."""
    if not values:
        raise ValueError("percentile of an empty sample")
    ordered = sorted(values)
    rank = max(1, math.ceil(point / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def share_below(values: Sequence[float], threshold: float) -> tuple[int, float]:
    """Count and fraction of the sample strictly below ``threshold``."""
    hits = sum(1 for value in values if value < threshold)
    return hits, (hits / len(values) if values else 0.0)


def share_above(values: Sequence[float], threshold: float) -> tuple[int, float]:
    """Count and fraction of the sample strictly above ``threshold``."""
    hits = sum(1 for value in values if value > threshold)
    return hits, (hits / len(values) if values else 0.0)


def _report_coverage(fired: set[datetime]) -> None:
    windows = coverage_windows(fired)
    print("== ledger_hour_coverage_72h ==")
    if not fired:
        print("  no ledger rows")
        return
    ordered = sorted(fired)
    span = (ordered[-1] - ordered[0]).total_seconds() / 3600
    print(f"  ledger span     {ordered[0].isoformat()} .. {ordered[-1].isoformat()}")
    print(f"  span hours      {span:.0f} ({span / 24:.1f} days), covered hours {len(fired)}")
    if not windows:
        print(f"  windows         0 (span shorter than the {WINDOW_HOURS} h window)")
        return
    print(f"  windows         {len(windows)} (one per hour, wholly inside the span)")
    for point in (0, 5, 25, 50, 75, 95, 100):
        label = {0: "min", 100: "max"}.get(point, f"p{point}")
        print(f"  {label:<15} {percentile(windows, point) * 100:.1f}%")
    for threshold in COVERAGE_THRESHOLDS:
        hits, share = share_below(windows, threshold)
        print(f"  fires below {threshold * 100:.0f}%   {hits}/{len(windows)} = {share * 100:.1f}%")


def _report_staleness(root: Path) -> None:
    intervals = state_intervals(root)
    print("== hours between consecutive distinct device states ==")
    if not intervals:
        print("  fewer than two states in the index")
        return
    print(f"  intervals       {len(intervals)}")
    for point in (0, 50, 95, 98, 99, 100):
        label = {0: "min", 100: "max"}.get(point, f"p{point}")
        print(f"  {label:<15} {percentile(intervals, point):.2f} h")
    for threshold in STALENESS_THRESHOLDS:
        hits, share = share_above(intervals, threshold)
        print(f"  exceeds {threshold:.0f} h      {hits}/{len(intervals)} = {share * 100:.1f}%")


def main(argv: Iterable[str] | None = None) -> int:
    """Print both distributions for a calibration-data checkout."""
    parser = argparse.ArgumentParser(description="Issue #48 section 7.3 threshold evidence.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Calibration-data checkout.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    _report_coverage(poll_hours(args.root))
    print()
    _report_staleness(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
