"""#61: compare a sweep's rows with a committed TSV, to rounding, for another machine's run.

The ``#`` provenance lines are ignored: they name the commit. Text columns must match exactly and
numeric columns to the printed relative tolerance, because the last bits of a dot product can depend
on the BLAS build. The ``km_*`` columns count rounding-level events or measure rounding itself, so
they belong to the arithmetic: they are not compared between the two files. One of them is checked
on the new file alone: ``km_route_gap_over_tolerance_max`` must be at most 1 in every row, that is,
the iterative route agreed with the exhaustive one to each point's tolerance (PR #143 review,
item 1). Exits 1 on a difference or on a gap above tolerance.

Usage::

    python docs/evidence/adr-011-type-reduction/compare_sweep.py <new.tsv> <committed.tsv>
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

TOLERANCE = 1e-9
FLOOR = 1e-15
GAP_OVER_TOLERANCE = "km_route_gap_over_tolerance_max"
ARITHMETIC_COLUMNS = (
    "km_passes_max",
    "km_passes_mean",
    "km_guard_stops",
    "km_route_gap_max",
    GAP_OVER_TOLERANCE,
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        body = (line for line in handle if not line.startswith("#"))
        return list(csv.DictReader(body, delimiter="\t"))


def main() -> int:
    new, committed = rows(Path(sys.argv[1])), rows(Path(sys.argv[2]))
    if len(new) != len(committed):
        print(f"FAIL: {len(new)} rows against {len(committed)}")
        return 1
    over = [float(a[GAP_OVER_TOLERANCE]) for a in new if a.get(GAP_OVER_TOLERANCE, "") != ""]
    if any(not v <= 1.0 for v in over):
        bad = sum(not v <= 1.0 for v in over)
        print(f"FAIL: {bad} rows where the iterative route misses the exhaustive one by more than")
        print(f"their tolerance; largest {max(over):.3g} tolerances")
        return 1
    worst = 0.0
    arithmetic = dict.fromkeys(ARITHMETIC_COLUMNS, 0)
    for a, b in zip(new, committed, strict=True):
        for key in b:
            if key in arithmetic:
                arithmetic[key] += a[key] != b[key]
                continue
            try:
                u, v = float(a[key]), float(b[key])
            except ValueError:
                if a[key] != b[key]:
                    print(f"FAIL: text column {key}: {a[key]!r} against {b[key]!r}")
                    return 1
                continue
            if math.isfinite(u) and math.isfinite(v):
                worst = max(worst, abs(u - v) / max(abs(v), FLOOR))
            elif str(u) != str(v):
                print(f"FAIL: column {key}: {a[key]} against {b[key]}")
                return 1
    print(f"{len(new)} rows, largest relative difference {worst:.3e}")
    print(f"rows differing in columns not compared: {arithmetic}")
    return 0 if worst < TOLERANCE else 1


if __name__ == "__main__":
    raise SystemExit(main())
