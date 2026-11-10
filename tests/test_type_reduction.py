"""Tests for the Karnik-Mendel reference in ``scripts/type_reduction_discrepancy.py``.

Issue #61 Part A, FR-1 to FR-4. The reference is certified here before it is used
to judge any reducer: both endpoint routes against brute-force vertex enumeration,
the analytic invariants (sandwich, degenerate box, affine equivariance), parity
with the shipped defuzzifiers, Wu & Mendel 2019's worked example, and two
mutation checks showing the checks can fail. The sweep tests at the end pin the
survey-derived inputs to NC-041 and NC-042, the grid geometry, and the TSV's
determinism, provenance header and invariants.

Tolerance: one weighted average ``sum w c / sum w`` with ``w >= 0`` carries a
rounding error of about ``2 n eps max|c|``; ``_tolerance`` allows 32 times that.
"""

import csv
import itertools
import math
import runpy
import sys
from fractions import Fraction
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pytest
from scripts.type_reduction_discrepancy import (
    COLUMNS,
    G59_GRID_NAME,
    Survey,
    _km_endpoint,
    _measure,
    _Measurement,
    _sorted_by_value,
    _stats,
    _summary_rows,
    _switch_vertex,
    _weighted_average,
    anchor_levels,
    anchored_convention_rule_base,
    bmm_half_reduce,
    domain_box,
    exhaustive_type_reduce,
    footprint_grid,
    g59_grid,
    karnik_mendel_detailed,
    karnik_mendel_type_reduce,
    load_survey,
    main,
    nie_tan_reduce,
    parse_footprint,
    parse_point_sets,
    parse_range_source,
    unit_spread_rule_base,
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
# to values[0] or to one ulp beside it, and on the right endpoint k alternates.
# Which box cycles depends on the arithmetic, not on the problem (findings section 7):
# the box found on 2026-10-21 (lower 0x1.51d2466664a90p-11, 0x1.2978dcd7da47bp-64;
# upper 0x1.eba9da337995ap-11, 0x1.63d9374034e0ep-64; values 0x1.61261207e7cf4p-13,
# 0x1.9197bc1f2828fp-13) stopped cycling once _weighted_average rescaled by the
# largest weight (PR #143 review, item 2). This one was found by the same kind of
# seeded search under the new arithmetic on 2026-11-11 (rng 20261111, trial 21).
CYCLE_LOWER = np.array(
    [float.fromhex("0x1.2828e4bec9a52p-13"), float.fromhex("0x1.082ac8d4fd4e0p-67")]
)
CYCLE_UPPER = np.array(
    [float.fromhex("0x1.f5cf0b54ed14ep-13"), float.fromhex("0x1.4864fe3c3729cp-66")]
)
CYCLE_VALUES = np.array(
    [float.fromhex("0x1.985abef0c2c49p-13"), float.fromhex("0x1.205fba82c7984p-12")]
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


# --- The sweep (FR-3, FR-4) --------------------------------------------------

SURVEY_TSV = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "evidence"
    / "feature-distribution"
    / "2026-09-08-3d1569d.tsv"
)
SURVEY_SOURCE = f"survey:{SURVEY_TSV}"


@pytest.fixture(scope="module")
def survey() -> Survey:
    return load_survey(SURVEY_TSV)


def _sweep_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        lines = [line for line in handle if not line.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


def test_survey_spread_medians_reproduce_nc042(survey: Survey) -> None:
    # NC-042: mean_T1 45.7756 us, mean_T2 54.9084 us, mean_readout_error 0.0406946.
    assert survey.samples.shape == (975, 3)
    assert survey.spread_medians[0] == pytest.approx(45.7756, abs=5e-5)
    assert survey.spread_medians[1] == pytest.approx(54.9084, abs=5e-5)
    assert survey.spread_medians[2] == pytest.approx(0.0406946, abs=5e-8)


def test_domain_box_reproduces_nc041(survey: Survey) -> None:
    # NC-041 p1 / p99: mean_T1 98.8191 / 154.3887 us, mean_T2 67.4411 / 110.5429 us,
    # mean_readout_error 0.0171326 / 0.0374223.
    lo, hi = domain_box(survey.samples)
    assert lo[0] == pytest.approx(98.8191, abs=5e-5)
    assert hi[0] == pytest.approx(154.3887, abs=5e-5)
    assert lo[1] == pytest.approx(67.4411, abs=5e-5)
    assert hi[1] == pytest.approx(110.5429, abs=5e-5)
    assert lo[2] == pytest.approx(0.0171326, abs=5e-8)
    assert hi[2] == pytest.approx(0.0374223, abs=5e-8)


def test_footprint_grid_is_symmetric_about_the_type1_width(survey: Survey) -> None:
    grid = footprint_grid(survey.samples, 0.3)
    anchors = anchor_levels(survey.samples)
    for feature, levels in enumerate(grid.per_input_mfs):
        assert len(levels) == 3
        for level, mf in enumerate(levels):
            centre, sigma_low, sigma_high = mf.parameters()
            assert centre == anchors[feature][level]
            assert sigma_high / sigma_low == pytest.approx(1.3 / 0.7, rel=1e-12)
    for ratio in (0.0, 1.0, -0.1):
        with pytest.raises(ValueError, match="strictly between 0 and 1"):
            footprint_grid(survey.samples, ratio)


def test_g59_grid_widens_by_the_spread_in_quadrature(survey: Survey) -> None:
    grid = g59_grid(survey.samples, survey.spread_medians)
    assert grid.name == G59_GRID_NAME
    for feature, levels in enumerate(grid.per_input_mfs):
        for mf in levels:
            _, sigma_low, sigma_high = mf.parameters()
            expected = math.sqrt(sigma_low**2 + survey.spread_medians[feature] ** 2)
            assert sigma_high == pytest.approx(expected, rel=1e-12)


def test_unit_spread_rule_base_biases(survey: Survey) -> None:
    grid = footprint_grid(survey.samples, 0.3)
    rule_base = unit_spread_rule_base(grid, anchor_levels(survey.samples))
    assert rule_base.n_rules == 27
    assert rule_base.output_dim == 1
    for index, rule in enumerate(rule_base.rules):
        params = rule.consequent_params
        assert np.array_equal(params[0, :-1], np.zeros(3))
        assert params[0, -1] == index / 26


def test_anchored_consequents_carry_structural_ties(survey: Survey) -> None:
    """Gamma depends on the mean_T1 anchor only (3 values), lambda on T1 and T2 (up to 9)."""
    grid = footprint_grid(survey.samples, 0.3)
    rule_base = anchored_convention_rule_base(grid, anchor_levels(survey.samples))
    linear = np.array([rule.consequent_params[:, :-1] for rule in rule_base.rules])
    biases = np.array([rule.consequent_params[:, -1] for rule in rule_base.rules])
    assert np.all(linear == 0.0)
    assert len(set(biases[:, 0].tolist())) == 3
    assert 3 < len(set(biases[:, 1].tolist())) <= 9


def test_each_rule_fires_fully_at_its_own_lattice_point(survey: Survey) -> None:
    grid = g59_grid(survey.samples, survey.spread_medians)
    anchors = anchor_levels(survey.samples)
    rule_base = unit_spread_rule_base(grid, anchors)
    for index, point in enumerate(itertools.product(*anchors)):
        firing = rule_base.evaluate(np.array(point))
        assert firing.firing_strengths_lower is not None
        assert firing.firing_strengths_upper is not None
        assert firing.firing_strengths_lower[index] == 1.0
        assert firing.firing_strengths_upper[index] == 1.0


def test_degenerate_footprint_limit_on_the_grid(survey: Survey) -> None:
    """#61 section 9.2: with both bounds set to the grid's upper firing, all reducers agree."""
    grid = g59_grid(survey.samples, survey.spread_medians)
    rule_base = anchored_convention_rule_base(grid, anchor_levels(survey.samples))
    lo, hi = domain_box(survey.samples)
    for x in np.random.default_rng(6900).uniform(lo, hi, size=(20, 3)):
        firing = rule_base.evaluate(x)
        upper = firing.firing_strengths_upper
        assert upper is not None
        for output in range(2):
            values = firing.consequent_outputs[:, output]
            y_l, y_r = karnik_mendel_type_reduce(upper, upper, values)
            assert y_r == pytest.approx(y_l, rel=1e-12)
            assert nie_tan_reduce(upper, upper, values) == pytest.approx(y_l, rel=1e-12)
            assert bmm_half_reduce(upper, upper, values) == pytest.approx(y_l, rel=1e-12)


def test_range_source_parsing() -> None:
    assert parse_range_source("survey:some/file.tsv") == Path("some/file.tsv")
    with pytest.raises(ValueError, match="needs a path"):
        parse_range_source("survey:")
    with pytest.raises(NotImplementedError, match="stand-in"):
        parse_range_source("fixture-box")
    for text in ("scales", "survey", "", "SURVEY:x.tsv"):
        with pytest.raises(ValueError, match="unknown --range-source"):
            parse_range_source(text)


def test_footprint_and_point_set_parsing() -> None:
    assert parse_footprint("g59") == "g59"
    assert parse_footprint("0.30") == "0.3"
    for text in ("0", "1", "1.5", "-0.2", "nan", "wide"):
        with pytest.raises(ValueError):
            parse_footprint(text)
    assert parse_point_sets("uniform,lattice") == ("uniform", "lattice")
    for text in ("", "lattice,lattice", "grid"):
        with pytest.raises(ValueError):
            parse_point_sets(text)


def _run(out: Path) -> None:
    args = [
        "--range-source",
        SURVEY_SOURCE,
        "--footprint",
        "0.3",
        "--footprint",
        "g59",
        "--points",
        "25",
        "--seed",
        "84",
        "--point-sets",
        "lattice,uniform",
        "--out",
        str(out),
    ]
    assert main(args) == 0


def test_sweep_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first, second = tmp_path / "first.tsv", tmp_path / "second.tsv"
    _run(first)
    _run(second)
    assert first.read_bytes() == second.read_bytes()


def test_sweep_header_records_provenance_and_the_g59_spread(tmp_path: Path) -> None:
    out = tmp_path / "sweep.tsv"
    _run(out)
    lines = out.read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    text = "\n".join(header)
    for key in ("commit:", "range_source:", "units:", "box:", "grids:", "seed: 84", "conventions:"):
        assert key in text
    assert "mean_T1 us" in text
    assert "g59_qubit_spread: s_i = median" in text
    assert "ASSUMED" not in text
    assert "G59-assumed" not in text
    assert "np.float64" not in text
    assert tuple(lines[len(header)].split("\t")) == COLUMNS


def test_sweep_rows_hold_the_invariants(tmp_path: Path) -> None:
    """Sandwich on the grid (#61 section 9.2), no skipped points, routes agree."""
    out = tmp_path / "sweep.tsv"
    _run(out)
    rows = _sweep_rows(out)
    # 2 grids x 3 outputs (unit, gamma, lambda) x 3 point sets (with pooled) x 2 reducers.
    assert len(rows) == 36
    for row in rows:
        assert row["n_skipped"] == "0"
        assert row["n_bracket_violations"] == "0"
        # Strict: the clip at 1/2 turns a reducer just outside the band into exactly 1/2.
        assert float(row["Db_max"]) < 0.5
        # The route gap in units of each point's own tolerance, 64 R eps max|c| (PR #143
        # review, item 5: an absolute bound was about 3,000 times loose for anchored rows).
        assert float(row["km_route_gap_over_tolerance_max"]) <= 1.0
    pooled = [row for row in rows if row["point_set"] == "pooled"]
    assert {row["n_points"] for row in pooled} == {"52"}


def test_mutation_summary_counts_violations_and_degenerate_bands() -> None:
    """The invariant columns can fire: a reducer outside the band and a zero-width band."""
    inside = _Measurement(
        y_l=0.0,
        y_r=1.0,
        y_bmm=0.5,
        y_nt=0.4,
        spread=2.0,
        tolerance=1e-12,
        passes_l=2,
        passes_r=3,
        guard_stops=0,
        route_gap=0.0,
    )
    outside = _Measurement(
        y_l=0.0,
        y_r=1.0,
        y_bmm=1.1,
        y_nt=0.5,
        spread=2.0,
        tolerance=1e-12,
        passes_l=1,
        passes_r=1,
        guard_stops=1,
        route_gap=1e-17,
    )
    flat = _Measurement(
        y_l=0.25,
        y_r=0.25,
        y_bmm=0.25,
        y_nt=0.25,
        spread=2.0,
        tolerance=1e-12,
        passes_l=1,
        passes_r=1,
        guard_stops=0,
        route_gap=0.0,
    )
    bmm_row, nt_row = (
        dict(zip(COLUMNS, row, strict=True))
        for row in _summary_rows(("g", "c", "o", "s"), [inside, outside, flat, None])
    )
    assert bmm_row["n_points"] == "4"
    assert bmm_row["n_skipped"] == "1"
    assert bmm_row["n_bracket_violations"] == "1"
    assert nt_row["n_bracket_violations"] == "0"
    assert bmm_row["n_degenerate_band"] == "1"
    assert float(bmm_row["D_max"]) == pytest.approx(0.6)
    assert float(bmm_row["Dc_max"]) == pytest.approx(0.3)
    assert float(nt_row["Db_max"]) == pytest.approx(0.1)
    assert bmm_row["km_passes_max"] == "3"
    assert bmm_row["km_guard_stops"] == "1"


# --- PR #143 review fixes (2026-11-11): reviews 5828001160 and 5831798256 ---------------

# Item 1. The starting average 0.5 / (0.5 + 1e-17) rounds to exactly 1.0, the largest
# consequent, so the switch point counts that rule, the left switch vertex is `upper`, and
# its average rounds to 1.0 again: a float fixed point that is not the minimum.
COUNTEREXAMPLE_LOWER = np.array([1e-17, 1e-20])
COUNTEREXAMPLE_UPPER = np.array([1e-17, 1.0])
COUNTEREXAMPLE_VALUES = np.array([0.0, 1.0])
COUNTEREXAMPLE_Y_L = 1e-20 / (1e-17 + 1e-20)

# Item 2. Every lower weight sits near the subnormal floor, so `lower @ values` underflows
# to 0.0 while `lower.sum()` does not.
UNDERFLOW_LOWER = np.array([1e-322, 1e-322])
UNDERFLOW_UPPER = np.array([1e-3, 1e-3])
UNDERFLOW_VALUES = np.array([1e-4, 2e-4])

# A two-rule box on which the left guard stops on a strict increase, found by a seeded
# search under the rescaled arithmetic on 2026-11-11 (rng 20261111, trial 3); CYCLE_*
# exercises the right guard.
LEFT_GUARD_LOWER = np.array(
    [float.fromhex("0x1.38d9cd865d6d6p-12"), float.fromhex("0x1.fafe8735193a3p-65")]
)
LEFT_GUARD_UPPER = np.array(
    [float.fromhex("0x1.01f52ac1e271bp-11"), float.fromhex("0x1.1f8c985fe635bp-64")]
)
LEFT_GUARD_VALUES = np.array(
    [float.fromhex("0x1.b00020ed7eb4ep-14"), float.fromhex("0x1.60d13f9980ffap-13")]
)

WIDE_RANGE_RULE_COUNTS = (2, 3, 4, 5, 6)
WIDE_RANGE_BOXES_PER_COUNT = 40


def _exact_vertex_extremes(
    lower: FloatArray, upper: FloatArray, values: FloatArray
) -> tuple[Fraction, Fraction]:
    """Min and max of the weighted average over all ``2^n`` vertices, in exact rationals.

    ``Fraction`` converts every float exactly, subnormals included, so this route has no
    rounding at all. It shares no code with the script.
    """
    c = [Fraction(float(v)) for v in values]
    averages = []
    for choice in itertools.product((False, True), repeat=len(c)):
        w = [
            Fraction(float(u if pick else lo))
            for pick, lo, u in zip(choice, lower, upper, strict=True)
        ]
        averages.append(sum(wi * ci for wi, ci in zip(w, c, strict=True)) / sum(w))
    return min(averages), max(averages)


def _wide_range_boxes() -> list[tuple[FloatArray, FloatArray, FloatArray]]:
    """Boxes whose firing spans 1e-20 to 1, after the two review cases."""
    rng = np.random.default_rng(20261111)
    boxes = [
        (COUNTEREXAMPLE_LOWER, COUNTEREXAMPLE_UPPER, COUNTEREXAMPLE_VALUES),
        (UNDERFLOW_LOWER, UNDERFLOW_UPPER, UNDERFLOW_VALUES),
    ]
    for n_rules in WIDE_RANGE_RULE_COUNTS:
        for _ in range(WIDE_RANGE_BOXES_PER_COUNT):
            upper = 10.0 ** rng.uniform(-20.0, 0.0, n_rules)
            lower = upper * rng.uniform(0.0, 1.0, n_rules)
            values = rng.normal(size=n_rules) * 10.0 ** rng.uniform(-4.0, 0.0)
            boxes.append((lower, upper, values))
    return boxes


def test_iterative_route_stops_at_a_float_fixed_point_on_the_counterexample() -> None:
    """Item 1, the known failure: iterative KM's left endpoint is 1.0, the truth is 9.99e-4."""
    result = karnik_mendel_detailed(
        COUNTEREXAMPLE_LOWER, COUNTEREXAMPLE_UPPER, COUNTEREXAMPLE_VALUES
    )
    exhaustive_l, _ = exhaustive_type_reduce(
        COUNTEREXAMPLE_LOWER, COUNTEREXAMPLE_UPPER, COUNTEREXAMPLE_VALUES
    )
    assert result.y_l == 1.0
    assert exhaustive_l == pytest.approx(COUNTEREXAMPLE_Y_L, rel=1e-12)


def test_sweep_endpoints_come_from_the_exhaustive_route() -> None:
    """Item 1's fix: the sweep's band is the exhaustive one; the iterative gap is reported."""
    m = _measure(COUNTEREXAMPLE_LOWER, COUNTEREXAMPLE_UPPER, COUNTEREXAMPLE_VALUES)
    assert m is not None
    assert m.y_l == pytest.approx(COUNTEREXAMPLE_Y_L, rel=1e-12)
    assert m.route_gap == pytest.approx(1.0 - COUNTEREXAMPLE_Y_L, rel=1e-12)
    assert m.route_gap / m.tolerance > 1.0


@pytest.mark.parametrize(
    "index", range(2 + len(WIDE_RANGE_RULE_COUNTS) * WIDE_RANGE_BOXES_PER_COUNT)
)
def test_exhaustive_route_matches_exact_rational_enumeration(index: int) -> None:
    """The exhaustive route's second route, now that it decides (review items 1 and 2)."""
    lower, upper, values = _wide_range_boxes()[index]
    exact_l, exact_r = _exact_vertex_extremes(lower, upper, values)
    y_l, y_r = exhaustive_type_reduce(lower, upper, values)
    tol = _tolerance(values)
    assert abs(y_l - float(exact_l)) <= tol
    assert abs(y_r - float(exact_r)) <= tol


def test_weighted_average_survives_subnormal_weights() -> None:
    """Item 2: rescaling by the largest weight keeps the average off zero."""
    assert _weighted_average(UNDERFLOW_LOWER, UNDERFLOW_VALUES) == pytest.approx(1.5e-4, rel=1e-12)
    m = _measure(UNDERFLOW_LOWER, UNDERFLOW_UPPER, UNDERFLOW_VALUES)
    assert m is not None
    assert m.y_l >= float(UNDERFLOW_VALUES.min())
    assert m.y_l <= m.y_bmm <= m.y_r


def test_stats_are_max_mean_median_p90() -> None:
    """Item 5: the summary statistics in their column order (kills order swaps)."""
    # Eleven values, so the linear p90 sits exactly on the tenth (9.0); mean and median differ.
    values = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0])
    assert _stats(values) == [repr(100.0), repr(145.0 / 11.0), repr(5.0), repr(9.0)]
    assert _stats(np.array([], dtype=np.float64)) == ["", "", "", ""]


def _measurement(y_l: float, y_r: float, y: float, tolerance: float) -> _Measurement:
    return _Measurement(
        y_l=y_l,
        y_r=y_r,
        y_bmm=y,
        y_nt=0.5 * (y_l + y_r),
        spread=1.0,
        tolerance=tolerance,
        passes_l=1,
        passes_r=1,
        guard_stops=0,
        route_gap=0.0,
    )


def _bmm_row(measurements: list[_Measurement | None]) -> dict[str, str]:
    return dict(zip(COLUMNS, _summary_rows(("g", "c", "o", "s"), measurements)[0], strict=True))


def test_band_position_is_clipped_at_one_half() -> None:
    """Item 5: a reducer within rounding outside a narrow band scores exactly 1/2."""
    row = _bmm_row([_measurement(0.0, 1e-9, 1e-9 + 5e-13, 1e-12)])
    assert row["n_bracket_violations"] == "0"
    assert float(row["Db_max"]) == 0.5


def test_degenerate_band_uses_the_point_tolerance() -> None:
    """Item 5: a width below the tolerance is degenerate, ten tolerances is not."""
    tol = 1e-12
    row = _bmm_row(
        [
            _measurement(0.0, 0.5 * tol, 0.25 * tol, tol),
            _measurement(0.0, 10 * tol, 5 * tol, tol),
        ]
    )
    assert row["n_degenerate_band"] == "1"


def test_summary_reports_the_route_gap_over_tolerance() -> None:
    """Item 1: the gap is reported in units of each point's own tolerance."""
    m = _Measurement(
        y_l=0.0,
        y_r=1.0,
        y_bmm=0.5,
        y_nt=0.5,
        spread=1.0,
        tolerance=1e-12,
        passes_l=1,
        passes_r=1,
        guard_stops=0,
        route_gap=3e-12,
    )
    assert float(_bmm_row([m])["km_route_gap_over_tolerance_max"]) == pytest.approx(3.0)
    assert COLUMNS[-1] == "km_route_gap_over_tolerance_max"


@pytest.mark.parametrize(
    ("side", "lower", "upper", "values"),
    [
        ("left", LEFT_GUARD_LOWER, LEFT_GUARD_UPPER, LEFT_GUARD_VALUES),
        ("right", CYCLE_LOWER, CYCLE_UPPER, CYCLE_VALUES),
    ],
)
def test_guard_returns_the_better_iterate(
    side: Literal["left", "right"], lower: FloatArray, upper: FloatArray, values: FloatArray
) -> None:
    """Item 5: when the guard stops, it returns the last accepted iterate, not the rejected one.

    The iterates are replayed here, step by step, from the textbook update (start at the
    midpoint average, take the switch vertex at ``k = #{c <= y}``), so the check does not
    read the guard's own code.
    """
    lo, hi, c = _sorted_by_value(lower, upper, values)
    y, passes, stopped = _km_endpoint(lo, hi, c, side)
    assert stopped
    iterates = [_weighted_average(0.5 * (lo + hi), c)]
    for _ in range(passes):
        k = int(np.searchsorted(c, iterates[-1], side="right"))
        iterates.append(_weighted_average(_switch_vertex(lo, hi, k, side), c))
    accepted, rejected = iterates[-2], iterates[-1]
    assert y == accepted
    if side == "left":
        assert rejected > accepted
    else:
        assert rejected < accepted


def test_each_output_reads_its_own_consequent_column(tmp_path: Path) -> None:
    """Item 5: anchored gamma and lambda rows come from different consequent columns."""
    out = tmp_path / "sweep.tsv"
    _run(out)
    rows = _sweep_rows(out)
    for grid in {row["grid"] for row in rows}:
        cells = {
            row["output"]: row["D_max"]
            for row in rows
            if row["grid"] == grid
            and row["convention"] == "anchored"
            and row["point_set"] == "uniform"
            and row["reducer"] == "nie_tan"
        }
        assert set(cells) == {"gamma", "lambda"}
        assert cells["gamma"] != cells["lambda"]


def _compare_sweep(monkeypatch: pytest.MonkeyPatch, new: Path, committed: Path) -> int:
    script = Path(__file__).resolve().parents[1] / (
        "docs/evidence/adr-011-type-reduction/compare_sweep.py"
    )
    namespace = runpy.run_path(str(script), run_name="compare_sweep_under_test")
    monkeypatch.setattr(sys, "argv", [str(script), str(new), str(committed)])
    return int(namespace["main"]())


def test_compare_sweep_fails_when_a_route_gap_exceeds_its_tolerance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Burak's ask on item 1: the comparison checks the route gap against its tolerance."""
    header = "grid\tD_max\tkm_route_gap_max\tkm_route_gap_over_tolerance_max\n"
    committed = tmp_path / "committed.tsv"
    committed.write_text(header + "g\t0.1\t1e-15\t0.5\n", encoding="utf-8")
    good, bad = tmp_path / "good.tsv", tmp_path / "bad.tsv"
    good.write_text(header + "g\t0.1\t1e-15\t0.9\n", encoding="utf-8")
    bad.write_text(header + "g\t0.1\t1e-3\t3.0e9\n", encoding="utf-8")
    assert _compare_sweep(monkeypatch, good, committed) == 0
    assert _compare_sweep(monkeypatch, bad, committed) == 1
