"""Second route for the survey-only reversal at G59, anchored lambda.

From the 2026-11-05 work behind #61 comment 6665986289. Run from the repository root, with
``PYTHONPATH=src``::

    python docs/evidence/adr-011-type-reduction/second_route_reducers.py

Takes firing bounds and consequents from the rule base, then computes everything else here, sharing
no code with scripts/type_reduction_discrepancy.py's reducers or Karnik-Mendel:

- bmm = (Y(lower) + Y(upper)) / 2
- nt = Y(lower + upper)
- [y_l, y_r] by brute force over all 28 switch points (sorted consequents)

The switch-point route is certified on small random boxes against full vertex enumeration, the check
#61 FR-2 names.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from scripts.type_reduction_discrepancy import (
    CONVENTIONS,
    anchor_levels,
    build_grid,
    load_survey,
)

SURVEY = Path("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv")


def wavg(w: np.ndarray, c: np.ndarray) -> float:
    return float(np.dot(w, c) / w.sum())


def endpoints_by_switch(lo: np.ndarray, hi: np.ndarray, c: np.ndarray) -> tuple[float, float]:
    order = np.argsort(c, kind="stable")
    lo, hi, c = lo[order], hi[order], c[order]
    n = c.size
    left = [wavg(np.concatenate([hi[:k], lo[k:]]), c) for k in range(n + 1)]
    right = [wavg(np.concatenate([lo[:k], hi[k:]]), c) for k in range(n + 1)]
    return min(left), max(right)


def endpoints_by_vertices(lo: np.ndarray, hi: np.ndarray, c: np.ndarray) -> tuple[float, float]:
    values = [wavg(np.array(v), c) for v in itertools.product(*zip(lo, hi, strict=True))]
    return min(values), max(values)


def score(y: float, y_l: float, y_r: float) -> float:
    return abs(y - 0.5 * (y_l + y_r)) / (y_r - y_l)


def main() -> None:
    rng = np.random.default_rng(61)
    worst = 0.0
    for _ in range(300):
        n = int(rng.integers(2, 9))
        lo = rng.uniform(0.01, 0.5, n)
        hi = lo + rng.uniform(0.0, 0.5, n)
        c = rng.normal(0.0, 1.0, n)
        a, b = endpoints_by_switch(lo, hi, c), endpoints_by_vertices(lo, hi, c)
        worst = max(worst, abs(a[0] - b[0]), abs(a[1] - b[1]))
    print(
        "switch-point route against vertex enumeration, 300 random boxes n<=8: "
        f"worst gap {worst:.2e}"
    )
    assert worst < 1e-12

    survey = load_survey(SURVEY)
    anchors = anchor_levels(survey.samples)
    points = survey.samples
    assert len(points) == 975, len(points)
    grid = build_grid("g59", survey)
    convention = next(c for c in CONVENTIONS if c.name == "anchored")
    rule_base = convention.build(grid, anchors)
    index = convention.outputs.index("lambda")

    bmm, nt, widths, gaps = [], [], [], []
    for x in points:
        firing = rule_base.evaluate(np.asarray(x, dtype=np.float64))
        lo, hi = firing.firing_strengths_lower, firing.firing_strengths_upper
        c = firing.consequent_outputs[:, index]
        y_l, y_r = endpoints_by_switch(lo, hi, c)
        y_bmm = 0.5 * (wavg(lo, c) + wavg(hi, c))
        y_nt = wavg(lo + hi, c)
        assert y_l - 1e-15 <= y_bmm <= y_r + 1e-15 and y_l - 1e-15 <= y_nt <= y_r + 1e-15
        bmm.append(score(y_bmm, y_l, y_r))
        nt.append(score(y_nt, y_l, y_r))
        widths.append(y_r - y_l)
        gaps.append(abs(y_bmm - y_nt))
    bmm_a, nt_a = np.array(bmm), np.array(nt)

    print(f"G59 anchored lambda, survey rows: n={len(bmm_a)}")
    print(f"median score: BMM {np.median(bmm_a):.4f}, Nie-Tan {np.median(nt_a):.4f}")
    print(
        f"closer: Nie-Tan {(nt_a < bmm_a).sum()}, BMM {(bmm_a < nt_a).sum()}, "
        f"tie {(nt_a == bmm_a).sum()}"
    )
    print(f"band width y_r - y_l: median {np.median(widths):.3e}, max {np.max(widths):.3e}")
    print(f"|y_BMM - y_NT|: median {np.median(gaps):.3e}, max {np.max(gaps):.3e}")
    print(f"distinct feature vectors among the 975 survey rows: {len(np.unique(points, axis=0))}")


if __name__ == "__main__":
    main()
