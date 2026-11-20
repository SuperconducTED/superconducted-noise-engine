"""#61, PR #143, review 5923434762: the figures behind the overflow fix's design.

Usage, from the repository root:
    PYTHONPATH=src python docs/evidence/adr-011-type-reduction/overflow_probe.py

1. Bit identity: the final `_weighted_average` against 0d53fc60's expression, on random
   inputs whose plain quotient is finite (weights 1e-30..1e30, values 1e-150..1e150).
2. Control, to show check 1 can fire: values divided by max |values|, not a power of two.
3. The top edge: equal values at the largest double. Where the shifted quotient rounds to
   1.0 or above, multiplying back would overflow and the final form saturates; elsewhere
   the result is the ordinary rounding.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from scripts.type_reduction_discrepancy import _weighted_average


def old(weights: np.ndarray, values: np.ndarray) -> float:
    scaled = weights / float(weights.max())
    return float(scaled @ values) / float(scaled.sum())


def by_largest(weights: np.ndarray, values: np.ndarray) -> float:
    scaled = weights / float(weights.max())
    largest = float(np.max(np.abs(values)))
    return float(scaled @ (values / largest)) / float(scaled.sum()) * largest


def main() -> None:
    np.seterr(over="ignore")  # 0d53fc60's expression overflows on some inputs; those are skipped
    rng = np.random.default_rng(20261120)
    cases = same = control_differs = 0
    for _ in range(200_000):
        n_rules = int(rng.integers(1, 40))
        weights = rng.random(n_rules) * 10.0 ** int(rng.integers(-30, 30))
        if weights.max() == 0.0:
            continue
        values = rng.standard_normal(n_rules) * 10.0 ** int(rng.integers(-150, 150))
        reference = old(weights, values)
        if not math.isfinite(reference):
            continue
        cases += 1
        same += _weighted_average(weights, values) == reference
        control_differs += by_largest(weights, values) != reference
    print(f"1. bit identity with 0d53fc60's expression: {same} of {cases} identical")
    print(f"2. control, divided by max |values|: {control_differs} of {cases} differ")

    top = rounds_past = saturated = finite = 0
    worst_ulps = 0
    largest = sys.float_info.max
    exponent = math.frexp(largest)[1]
    for _ in range(200_000):
        n_rules = int(rng.integers(2, 30))
        weights = rng.random(n_rules) + 1e-3
        values = np.full(n_rules, largest)
        scaled = weights / float(weights.max())
        quotient = float(scaled @ np.ldexp(values, -exponent)) / float(scaled.sum())
        result = _weighted_average(weights, values)
        top += 1
        rounds_past += quotient >= 1.0
        saturated += result == largest and quotient >= 1.0
        finite += math.isfinite(result)
        worst_ulps = max(worst_ulps, round((largest - result) / math.ulp(largest)))
    print(f"3. equal values at the largest double, {top} cases:")
    print(f"   shifted quotient >= 1.0 (multiplying back would overflow): {rounds_past}")
    print(f"   of those, the largest double returned: {saturated}")
    print(f"   finite results: {finite} of {top}")
    print(f"   largest distance below the largest double (the true result): {worst_ulps} ulps")


if __name__ == "__main__":
    main()
