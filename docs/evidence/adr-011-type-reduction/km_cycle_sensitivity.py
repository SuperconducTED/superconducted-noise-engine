"""#61: how File 02's cycle count moves with the arithmetic, on anchored w=0.6 gamma.

File 02 (#84 comment 5885404218) reports 116 (point, gamma) pairs on which the y' == y stop never
terminates. This counts, per switch-point tie convention and per summation order, the points whose
left, right, either or both endpoints hit the n + 1 cap, split by point set, and checks the guarded
result on every cycling point against the exhaustive route. The count belongs to the
implementation: the mechanism is what to report. Since 2026-11-11 (PR #143 review, item 2) the
script's ``Y`` divides the weights by their largest before ``w @ c``, which moves the counts again.

Run from the repository root, with ``PYTHONPATH=src``::

    python docs/evidence/adr-011-type-reduction/km_cycle_sensitivity.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from scripts.type_reduction_discrepancy import (
    CONVENTIONS,
    _sorted_by_value,
    _switch_vertex,
    _weighted_average,
    anchor_levels,
    build_grid,
    exhaustive_type_reduce,
    karnik_mendel_detailed,
    load_survey,
    point_sets,
)

EPS = float(np.finfo(np.float64).eps)


def _sum_then_divide(w, c):
    """The same average with another summation order: ``np.sum(w * c) / np.sum(w)``."""
    return float(np.sum(w * c) / np.sum(w))


def cycles(lo, hi, c, side, k_side, average=_weighted_average):
    y = average(0.5 * (lo + hi), c)
    for _ in range(c.size + 1):
        k = int(np.searchsorted(c, y, side=k_side))
        y_next = average(_switch_vertex(lo, hi, k, side), c)
        if y_next == y:
            return False
        y = y_next
    return True


def main() -> None:
    survey = load_survey(Path("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv"))
    sets = point_sets(("lattice", "uniform", "survey"), survey, 2000, 84)
    grid = build_grid("0.6", survey)
    anchored = next(conv for conv in CONVENTIONS if conv.name == "anchored")
    rule_base = anchored.build(grid, anchor_levels(survey.samples))
    for k_side in ("right", "left"):
        print(f"k tie convention searchsorted(side={k_side!r}):")
        total = {"left": 0, "right": 0, "either": 0, "both": 0}
        guard_bad = 0
        other_order = 0
        for set_name, points in sets.items():
            counts = {"left": 0, "right": 0, "either": 0, "both": 0}
            for x in points:
                firing = rule_base.evaluate(np.asarray(x, dtype=np.float64))
                lo, hi = firing.firing_strengths_lower, firing.firing_strengths_upper
                c = firing.consequent_outputs[:, 0]
                s_lo, s_hi, s_c = _sorted_by_value(lo, hi, c)
                left = cycles(s_lo, s_hi, s_c, "left", k_side)
                right = cycles(s_lo, s_hi, s_c, "right", k_side)
                counts["left"] += left
                counts["right"] += right
                counts["either"] += left or right
                counts["both"] += left and right
                other_order += cycles(s_lo, s_hi, s_c, "left", k_side, _sum_then_divide) or cycles(
                    s_lo, s_hi, s_c, "right", k_side, _sum_then_divide
                )
                if left or right:
                    km = karnik_mendel_detailed(lo, hi, c)
                    ex_l, ex_r = exhaustive_type_reduce(lo, hi, c)
                    tol = 64 * c.size * EPS * float(np.max(np.abs(c)))
                    guard_bad += max(abs(km.y_l - ex_l), abs(km.y_r - ex_r)) > tol
            print(f"  {set_name:8s} {counts}")
            for key in total:
                total[key] += counts[key]
        print(f"  total    {total}")
        print(f"  guarded result off the exhaustive route on cycling points: {guard_bad}")
        print(
            f"  points cycling with np.sum(w * c) / np.sum(w) in place of the script's Y: "
            f"{other_order}"
        )


if __name__ == "__main__":
    main()
