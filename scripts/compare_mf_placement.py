"""Compare the two candidate Gaussian-MF center layouts from Issue #31.

Both layouts put ``MFS_PER_FEATURE`` (3) membership functions on each
feature range with the same sigma, so the only difference is where the
centers sit:

    endpoint · lo, lo + span/2, hi
    interior · lo + span/6, lo + span/2, lo + 5*span/6

This script reports four deterministic metrics per layout and prints the
decision rule. It runs no simulation and draws no random numbers, so the
output is bit-identical on any machine — a differing number means a
genuine environment problem, not hardware variation.

Metrics (all computed on the normalized range, which makes them
identical across the three features since every layout scales with span):

``n_rules``
    Rules produced by ``TSKRuleBase.from_grid``. Must be 27 (ADR-010).

``min_coverage``
    ``min_x max_j mu_j(x)`` over the range. The weakest point in the
    feature range: how well the best-matching MF covers the input that
    is worst-covered. Low values mean a dead zone where no rule fires
    strongly. Higher is better.

``coverage_at_lo`` / ``coverage_at_hi``
    ``max_j mu_j(x)`` at the two range extremes. These are the states
    Issue #31 singles out — long T1/T2 and high readout error are what
    the noise model most needs to tell apart. Higher is better.

``mean_separation``
    Mean over the range of ``top1 - top2`` membership. How decisively a
    single MF wins at a typical input. High separation means crisp rule
    selection; low separation means several rules fire near-equally and
    the defuzzified output is a blur of them. Higher is crisper, which
    is not automatically better — it trades against coverage.

Run from the repository root (as a module, so ``scripts`` is importable):

    python -m scripts.compare_mf_placement
"""

from __future__ import annotations

import math
from typing import Final

from scripts.first_ensemble_run import (
    FEATURE_SCALES,
    MF_PLACEMENTS,
    MFS_PER_FEATURE,
    _default_mfs_for_feature,
    mf_centers,
)
from superconducted.fuzzy.tsk import TSKRuleBase

# Dense enough that the reported minima are stable to ~1e-6, small enough
# to run instantly. Deterministic: no RNG anywhere in this script.
_GRID_POINTS: Final[int] = 20001


def _gaussian(x: float, center: float, sigma: float) -> float:
    return math.exp(-((x - center) ** 2) / (2.0 * sigma**2))


def _memberships(x: float, centers: tuple[float, ...], sigma: float) -> list[float]:
    return sorted((_gaussian(x, c, sigma) for c in centers), reverse=True)


def placement_metrics(placement: str) -> dict[str, float]:
    """Coverage and separation metrics for one layout, on ``[0, 1]``."""
    lo, hi = 0.0, 1.0
    sigma = (hi - lo) * 0.25
    centers = mf_centers(lo, hi, placement)

    min_coverage = math.inf
    separation_total = 0.0
    for i in range(_GRID_POINTS):
        x = lo + (hi - lo) * i / (_GRID_POINTS - 1)
        ranked = _memberships(x, centers, sigma)
        min_coverage = min(min_coverage, ranked[0])
        separation_total += ranked[0] - ranked[1]

    return {
        "min_coverage": min_coverage,
        "coverage_at_lo": _memberships(lo, centers, sigma)[0],
        "coverage_at_hi": _memberships(hi, centers, sigma)[0],
        "mean_separation": separation_total / _GRID_POINTS,
    }


def rule_count(placement: str) -> int:
    """Rules the smoke script's grid actually produces under ``placement``."""
    per_input_mfs = [_default_mfs_for_feature(name, placement) for name in FEATURE_SCALES]
    return TSKRuleBase.from_grid(per_input_mfs=per_input_mfs, output_dim=2).n_rules


def main() -> None:
    print("MF placement comparison - Issue #31")
    print(f"{MFS_PER_FEATURE} MFs per feature, sigma = span * 0.25, {_GRID_POINTS} grid points")
    print()

    results: dict[str, dict[str, float]] = {}
    for placement in MF_PLACEMENTS:
        results[placement] = placement_metrics(placement)
        results[placement]["n_rules"] = float(rule_count(placement))
        centers = mf_centers(0.0, 1.0, placement)
        print(f"{placement:9s} centers (normalized): {[round(c, 5) for c in centers]}")
    print()

    header = f"{'metric':18s} {'endpoint':>12s} {'interior':>12s}   winner"
    print(header)
    print("-" * len(header))
    for metric in (
        "n_rules",
        "min_coverage",
        "coverage_at_lo",
        "coverage_at_hi",
        "mean_separation",
    ):
        a = results["endpoint"][metric]
        b = results["interior"][metric]
        if metric == "n_rules":
            winner = "tie (both must be 27)" if a == b else "MISMATCH"
            print(f"{metric:18s} {a:12.0f} {b:12.0f}   {winner}")
            continue
        winner = "tie" if abs(a - b) < 1e-9 else ("endpoint" if a > b else "interior")
        print(f"{metric:18s} {a:12.6f} {b:12.6f}   {winner}")

    print()
    print("Decision rule")
    print("-------------")
    print("1. REJECT any layout whose n_rules != 27. ADR-010 ratifies 27; a layout")
    print("   that does not produce it is not a candidate regardless of coverage.")
    print("2. REJECT any layout with min_coverage < 0.5. Below that, some input in")
    print("   the feature range fires no rule above half strength, which is a dead")
    print("   zone: the noise model cannot respond to calibration states in it.")
    print("3. Among survivors, the choice is a stated trade-off, not a computed one:")
    print("   - Prioritize min_coverage when the concern is that no calibration")
    print("     state goes unrepresented. That favors the INTERIOR layout.")
    print("   - Prioritize coverage_at_lo / coverage_at_hi when the concern is")
    print("     sharp discrimination of extreme states - the exact worry that")
    print("     opened Issue #31. That favors the ENDPOINT layout, which peaks at")
    print("     mu = 1 there.")
    print("4. mean_separation is reported as context, not as a tiebreak. Higher")
    print("   separation means crisper single-rule selection; lower means more")
    print("   rules blend. Neither is right without a stated goal.")
    print()
    print("Until the team or the advisor rules on 3, the default stays as shipped")
    print("(scripts/first_ensemble_run.py :: DEFAULT_MF_PLACEMENT). Changing it is a")
    print("one-line edit to that constant.")


if __name__ == "__main__":
    main()
