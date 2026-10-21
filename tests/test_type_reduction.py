"""Tests for the Karnik-Mendel reference in ``scripts/type_reduction_discrepancy.py``.

Issue #61 Part A, FR-1 and FR-2. The reference is certified here before it is used
to judge any reducer: both endpoint routes against brute-force vertex enumeration,
the analytic invariants (sandwich, degenerate box, affine equivariance), parity
with the shipped defuzzifiers, Wu & Mendel 2019's worked example, and two
mutation checks showing the checks can fail.

Tolerance: one weighted average ``sum w c / sum w`` with ``w >= 0`` carries a
rounding error of about ``2 n eps max|c|``; ``_tolerance`` allows 32 times that.
"""

import itertools
import math

import numpy as np
import numpy.typing as npt
import pytest
from scripts.type_reduction_discrepancy import (
    _km_endpoint,
    _sorted_by_value,
    bmm_half_reduce,
    exhaustive_type_reduce,
    karnik_mendel_detailed,
    karnik_mendel_type_reduce,
    nie_tan_reduce,
)

from superconducted.fuzzy.defuzzification import (
    NieTanDefuzzifier,
    WeightedAverageDefuzzifier,
)
from superconducted.types import RuleFiringResult

FloatArray = npt.NDArray[np.float64]
RULE_COUNTS = (1, 2, 3, 5, 8)
BOXES_PER_COUNT = 200


def _tolerance(values: FloatArray) -> float:
    return 64 * values.size * float(np.finfo(np.float64).eps) * float(np.max(np.abs(values)))


def _vertex_extremes(
    lower: FloatArray, upper: FloatArray, values: FloatArray
) -> tuple[float, float]:
    """Min and max of the weighted average over all ``2^n`` vertices of the box (FR-2).

    Sound because the weighted average is linear-fractional in ``w``, so its
    extrema over a box sit at vertices. Every vertex dominates ``lower``, so
    ``lower.sum() > 0`` is asserted rather than vertices being skipped.
    """
    assert lower.sum() > 0.0
    averages = [
        float(np.where(choice, upper, lower) @ values) / float(np.where(choice, upper, lower).sum())
        for choice in itertools.product((False, True), repeat=values.size)
    ]
    return min(averages), max(averages)


def _random_box(
    rng: np.random.Generator, n_rules: int, tied: bool
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """A random valid box; some coordinates degenerate, consequents tied on request."""
    upper = rng.uniform(0.0, 1.0, n_rules)
    lower = upper * rng.uniform(0.0, 1.0, n_rules)
    degenerate = rng.uniform(size=n_rules) < 0.15
    lower[degenerate] = upper[degenerate]
    if lower.sum() == 0.0:
        lower[0] = upper[0] = 1.0
    if tied:
        values = rng.choice(np.array([-0.5, 0.0, 0.25, 1.0]), n_rules)
    else:
        values = rng.normal(size=n_rules)
    return lower, upper, values


def _boxes(n_rules: int, seed: int) -> list[tuple[FloatArray, FloatArray, FloatArray]]:
    rng = np.random.default_rng(seed)
    return [_random_box(rng, n_rules, tied=index % 2 == 0) for index in range(BOXES_PER_COUNT)]


# A two-rule box on which the switch-point stop alone cycles in float64. Rule 2
# fires about 1e-16 times as strongly as rule 1, so every weighted average rounds
# to values[0] or to one ulp below it, and on the right endpoint k alternates
# 1, 0, 1, 0, ... Found by a seeded search on 2026-10-21 (Issue #61 Part A plan).
CYCLE_LOWER = np.array(
    [float.fromhex("0x1.51d2466664a90p-11"), float.fromhex("0x1.2978dcd7da47bp-64")]
)
CYCLE_UPPER = np.array(
    [float.fromhex("0x1.eba9da337995ap-11"), float.fromhex("0x1.63d9374034e0ep-64")]
)
CYCLE_VALUES = np.array(
    [float.fromhex("0x1.61261207e7cf4p-13"), float.fromhex("0x1.9197bc1f2828fp-13")]
)


@pytest.mark.parametrize("n_rules", RULE_COUNTS)
def test_both_routes_match_vertex_enumeration(n_rules: int) -> None:
    for lower, upper, values in _boxes(n_rules, seed=6100 + n_rules):
        tol = _tolerance(values)
        vertex_l, vertex_r = _vertex_extremes(lower, upper, values)
        for y_l, y_r in (
            karnik_mendel_type_reduce(lower, upper, values),
            exhaustive_type_reduce(lower, upper, values),
        ):
            assert abs(y_l - vertex_l) <= tol
            assert abs(y_r - vertex_r) <= tol


@pytest.mark.parametrize("n_rules", RULE_COUNTS)
def test_iterative_route_stops_within_the_cap_and_orders_endpoints(n_rules: int) -> None:
    for lower, upper, values in _boxes(n_rules, seed=6200 + n_rules):
        result = karnik_mendel_detailed(lower, upper, values)
        assert 1 <= result.passes_l <= n_rules + 1
        assert 1 <= result.passes_r <= n_rules + 1
        assert result.y_l <= result.y_r + _tolerance(values)


def test_single_rule_returns_its_consequent_to_rounding() -> None:
    # Not exact: 0.7 * 3.5 / 0.7 is 3.4999999999999996 in float64, so a computed
    # average can sit one ulp outside [min values, max values].
    tol = _tolerance(np.array([3.5]))
    for y_l, y_r in (
        karnik_mendel_type_reduce([0.2], [0.7], [3.5]),
        exhaustive_type_reduce([0.2], [0.7], [3.5]),
    ):
        assert abs(y_l - 3.5) <= tol
        assert abs(y_r - 3.5) <= tol


def test_degenerate_box_returns_the_weighted_average_twice() -> None:
    rng = np.random.default_rng(6300)
    for _ in range(50):
        weights = rng.uniform(0.01, 1.0, 6)
        values = rng.normal(size=6)
        expected = float(weights @ values) / float(weights.sum())
        tol = _tolerance(values)
        for y_l, y_r in (
            karnik_mendel_type_reduce(weights, weights, values),
            exhaustive_type_reduce(weights, weights, values),
        ):
            assert abs(y_l - expected) <= tol
            assert abs(y_r - expected) <= tol
        assert abs(bmm_half_reduce(weights, weights, values) - expected) <= tol
        assert abs(nie_tan_reduce(weights, weights, values) - expected) <= tol


@pytest.mark.parametrize("n_rules", RULE_COUNTS)
def test_both_reducers_lie_inside_the_type_reduced_interval(n_rules: int) -> None:
    for lower, upper, values in _boxes(n_rules, seed=6400 + n_rules):
        tol = _tolerance(values)
        y_l, y_r = exhaustive_type_reduce(lower, upper, values)
        for y in (bmm_half_reduce(lower, upper, values), nie_tan_reduce(lower, upper, values)):
            assert y_l - tol <= y <= y_r + tol


def test_endpoints_and_band_position_are_affine_equivariant() -> None:
    rng = np.random.default_rng(6500)
    for _ in range(100):
        lower, upper, values = _random_box(rng, 5, tied=False)
        scale = rng.uniform(0.1, 10.0) * rng.choice(np.array([-1.0, 1.0]))
        shift = rng.normal()
        y_l, y_r = exhaustive_type_reduce(lower, upper, values)
        moved_l, moved_r = exhaustive_type_reduce(lower, upper, scale * values + shift)
        tol = _tolerance(scale * values + shift) + abs(scale) * _tolerance(values)
        if scale > 0:
            assert abs(moved_l - (scale * y_l + shift)) <= tol
            assert abs(moved_r - (scale * y_r + shift)) <= tol
        else:
            assert abs(moved_l - (scale * y_r + shift)) <= tol
            assert abs(moved_r - (scale * y_l + shift)) <= tol
        if y_r - y_l > 1e-9:
            position = (nie_tan_reduce(lower, upper, values) - 0.5 * (y_l + y_r)) / (y_r - y_l)
            moved = nie_tan_reduce(lower, upper, scale * values + shift)
            moved_position = (moved - 0.5 * (moved_l + moved_r)) / (moved_r - moved_l)
            assert abs(abs(moved_position) - abs(position)) <= 1e-9


def test_reducers_match_the_shipped_defuzzifiers() -> None:
    rng = np.random.default_rng(6600)
    for _ in range(100):
        lower, upper, values = _random_box(rng, 27, tied=False)
        firing = RuleFiringResult(
            firing_strengths=0.5 * (lower + upper),
            consequent_outputs=values[:, None],
            firing_strengths_lower=lower,
            firing_strengths_upper=upper,
        )
        shipped_bmm = float(NieTanDefuzzifier().defuzzify(firing)[0])
        shipped_midpoint = float(WeightedAverageDefuzzifier().defuzzify(firing)[0])
        assert bmm_half_reduce(lower, upper, values) == pytest.approx(shipped_bmm, rel=1e-12)
        assert nie_tan_reduce(lower, upper, values) == pytest.approx(shipped_midpoint, rel=1e-12)


def test_wu_mendel_2019_worked_example() -> None:
    """Wu & Mendel 2019 (arXiv:1907.01697 v1), section II-H, pp. 10-12.

    Input ``(-0.2, -0.3)``; Gaussian MFs centred at -1 and +1 with the standard
    deviation blurred to ``[0.5, 0.7]`` (0.5 gives the lower grade); product
    t-norm; rules (X1, X1), (X1, X2), (X2, X1), (X2, X2) with crisp consequents
    -1, -0.5, 0.5, 1 (Table IV). Printed to four decimals: ``y_l = -0.8846``,
    ``y_r = 0.0058`` (by EIASC), Nie-Tan Eq. (13) ``-0.4794``, BMM with
    ``alpha = beta = 0.5`` Eq. (14) ``-0.5665``. The firing bounds are recomputed
    from the stated MFs, because Table VI's four-decimal values move ``y_r`` by
    about 4e-4.
    """

    def grade(x: float, centre: float, sigma: float) -> float:
        return math.exp(-((x - centre) ** 2) / (2.0 * sigma**2))

    x_rate, x_error = -0.2, -0.3
    rules = ((-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0))
    lower = np.array([grade(x_rate, a, 0.5) * grade(x_error, b, 0.5) for a, b in rules])
    upper = np.array([grade(x_rate, a, 0.7) * grade(x_error, b, 0.7) for a, b in rules])
    values = np.array([-1.0, -0.5, 0.5, 1.0])
    half_unit = 5e-5

    y_l, y_r = karnik_mendel_type_reduce(lower, upper, values)
    assert (y_l, y_r) == exhaustive_type_reduce(lower, upper, values)
    assert abs(y_l - -0.8846) <= half_unit
    assert abs(y_r - 0.0058) <= half_unit
    assert abs(nie_tan_reduce(lower, upper, values) - -0.4794) <= half_unit
    assert abs(bmm_half_reduce(lower, upper, values) - -0.5665) <= half_unit


@pytest.mark.parametrize(
    ("lower", "upper", "values", "message"),
    [
        ([0.5, 0.2], [0.4, 0.3], [0.0, 1.0], "must not exceed"),
        ([-0.1, 0.2], [0.4, 0.3], [0.0, 1.0], "non-negative"),
        ([0.1, 0.2], [0.4, 0.3], [0.0, 1.0, 2.0], "equal length"),
        ([[0.1, 0.2]], [[0.4, 0.3]], [[0.0, 1.0]], "1-D"),
        ([], [], [], "at least one rule"),
        ([0.1, 0.2], [0.4, math.inf], [0.0, 1.0], "finite"),
        ([0.1, 0.2], [0.4, 0.3], [0.0, math.nan], "finite"),
    ],
)
def test_invalid_input_raises_value_error(
    lower: list[float], upper: list[float], values: list[float], message: str
) -> None:
    for function in (
        karnik_mendel_type_reduce,
        exhaustive_type_reduce,
        bmm_half_reduce,
        nie_tan_reduce,
    ):
        with pytest.raises(ValueError, match=message):
            function(lower, upper, values)


@pytest.mark.parametrize(
    ("lower", "upper", "values"),
    [
        ([0.0, 0.0], [0.0, 0.0], [0.0, 1.0]),
        # FR-1's smallest load-bearing case: the upper sum is positive, but a
        # y_r splice (lower on the small value, upper on the large) sums to zero.
        ([0.0, 0.0], [1.0, 0.0], [0.0, 1.0]),
    ],
)
def test_zero_firing_sum_raises_zero_division_error(
    lower: list[float], upper: list[float], values: list[float]
) -> None:
    for function in (
        karnik_mendel_type_reduce,
        exhaustive_type_reduce,
        bmm_half_reduce,
        nie_tan_reduce,
    ):
        with pytest.raises(ZeroDivisionError):
            function(lower, upper, values)


def test_inputs_are_not_mutated() -> None:
    lower, upper, values = _random_box(np.random.default_rng(6700), 8, tied=True)
    copies = (lower.copy(), upper.copy(), values.copy())
    karnik_mendel_detailed(lower, upper, values)
    exhaustive_type_reduce(lower, upper, values)
    bmm_half_reduce(lower, upper, values)
    nie_tan_reduce(lower, upper, values)
    for original, copy in zip((lower, upper, values), copies, strict=True):
        assert np.array_equal(original, copy)


def test_mutation_switch_point_stop_alone_cycles() -> None:
    """Without the monotone guard the switch-point stop cycles; with it, it stops.

    This is the case behind the #61 owner decision (2026-10-21) to add the guard:
    in exact arithmetic ``k' = k`` is equivalent to ``y' = y`` (Wu & Mendel 2009),
    and in float64 both fail here.
    """
    lower, upper, values = _sorted_by_value(CYCLE_LOWER, CYCLE_UPPER, CYCLE_VALUES)
    with pytest.raises(RuntimeError, match="right endpoint did not stop"):
        _km_endpoint(lower, upper, values, "right", guard=False)

    result = karnik_mendel_detailed(CYCLE_LOWER, CYCLE_UPPER, CYCLE_VALUES)
    assert result.guard_stops >= 1
    exhaustive_l, exhaustive_r = exhaustive_type_reduce(CYCLE_LOWER, CYCLE_UPPER, CYCLE_VALUES)
    tol = _tolerance(CYCLE_VALUES)
    assert abs(result.y_l - exhaustive_l) <= tol
    assert abs(result.y_r - exhaustive_r) <= tol


def test_mutation_vertex_check_detects_a_swapped_splice() -> None:
    """The vertex check can fire: a left endpoint built from the wrong splice fails it.

    The wrong family (lower bounds on the small values) shares exactly two
    vertices with the right one on a box with no degenerate coordinate: all
    lower and all upper. So the check must miss precisely the boxes whose left
    endpoint sits at one of those two, and catch every other box.
    """
    rng = np.random.default_rng(6800)
    detected = 0
    for _ in range(100):
        upper = rng.uniform(0.1, 1.0, 5)
        lower = upper * rng.uniform(0.1, 0.9, 5)
        values = rng.normal(size=5)
        order = np.argsort(values, kind="stable")
        lo, hi, c = lower[order], upper[order], values[order]
        wrong_left = min(
            float(np.concatenate((lo[:k], hi[k:])) @ c)
            / float(np.concatenate((lo[:k], hi[k:])).sum())
            for k in range(c.size + 1)
        )
        vertex_l, _ = _vertex_extremes(lower, upper, values)
        tol = _tolerance(values)
        if abs(wrong_left - vertex_l) > tol:
            detected += 1
        else:
            shared = min(float(lo @ c) / float(lo.sum()), float(hi @ c) / float(hi.sum()))
            assert abs(vertex_l - shared) <= tol
    assert detected > 0
