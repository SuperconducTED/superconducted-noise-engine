"""Property suite for ``superconducted.fuzzy.parameterization`` (Issue #59 section 9).

The suite is organised the way the ticket is: unit properties per shape, then
the anchored rule base's structural contract, then the clamp, then the
conformance checks that run on the **committed survey's real quantiles** rather
than on synthetic samples. Nothing here touches the network or the archive; the
committed TSV is the durable record.
"""

from __future__ import annotations

import csv
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from scripts.first_ensemble_run import mf_centers

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.fuzzy.defuzzification import NieTanDefuzzifier, WeightedAverageDefuzzifier
from superconducted.fuzzy.membership import (
    GaussianMF,
    IntervalGaussianMF,
    TanhBellMF,
    TanhMF,
    TanhSigmoidMF,
    TrapezoidalMF,
    TriangularMF,
)
from superconducted.fuzzy.parameterization import (
    EDGE_TANH_VALUE,
    MARGIN_FRACTION,
    PLACEMENT_ENDPOINT,
    PLACEMENT_INTERIOR,
    PLACEMENT_QUANTILE,
    TANH_SLOPES_EQUAL,
    TANH_SLOPES_HALF_REACH,
    ClampingFeatureExtractor,
    QuantileLayout,
    _quantile_layout,
    anchored_rule_base,
    grid_partition,
    partition_anchors,
    tanh_floor_onsets,
    tanh_slope_strategy,
)
from superconducted.integration.aer_factory import is_identity_damping
from superconducted.types import CalibrationSnapshot

M1_SHAPES = (GaussianMF, TanhMF, TanhSigmoidMF, IntervalGaussianMF)
SECOND_COMMIT_SHAPES = (TriangularMF, TrapezoidalMF, TanhBellMF)

#: A right-skewed sample, so the quantile bins are genuinely unequal and the
#: half-reach TanhMF mapping is exercised rather than collapsing to symmetry.
_RNG_FREE_SKEWED = np.concatenate(
    [
        np.linspace(60.0, 130.0, 400),
        np.linspace(130.0, 175.0, 300),
        np.linspace(175.0, 330.0, 60),
    ]
)

SURVEY_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "feature-distribution"
FEATURE_COLUMNS = ("mean_T1", "mean_T2", "mean_readout_error")
SPREAD_COLUMNS = ("T1_qubit_std", "T2_qubit_std", "readout_error_qubit_std")


def _spread_for(shape: type, samples: npt.NDArray[np.float64]) -> dict[str, float]:
    """The ``qubit_spread`` keyword ``shape`` needs, if any."""
    if shape is not IntervalGaussianMF:
        return {}
    return {"qubit_spread": float(np.std(samples, ddof=1)) / 4.0}


def _synthetic_snapshot(t1: float, t2: float, readout: float) -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend="ibm_fez",
        timestamp=datetime(2026, 9, 8, tzinfo=UTC),
        schema_version="1.0.0",
        properties={
            "qubits": [
                [
                    {"name": "T1", "value": t1},
                    {"name": "T2", "value": t2},
                    {"name": "readout_error", "value": readout},
                ]
            ]
        },
        target=None,
        configuration=None,
    )


def _synthetic_target(x: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """A stand-in for ``training.targets.feature_target_fn`` while #57 is unmerged.

    Monotone in T1 and strictly inside ``(0, 1)`` for every anchor this suite
    builds, which is all section 6.5's convexity argument needs.
    """
    return np.array([1.0e-4 * (1.0 + x[0] / 500.0), 2.0e-4 * (1.0 + x[2])], dtype=np.float64)


# --------------------------------------------------------------------------
# _quantile_layout (section 9.1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("k", [2, 3, 5])
def test_quantile_layout_is_strictly_ordered(k: int) -> None:
    """e_0 < c_1 < e_1 < ... < e_k, with every reach strictly positive."""
    layout = _quantile_layout(_RNG_FREE_SKEWED, k, PLACEMENT_QUANTILE)

    assert layout.k == k
    assert layout.edges.shape == (k + 1,)
    assert layout.centers.shape == (k,)
    interleaved = np.empty(2 * k + 1)
    interleaved[0::2] = layout.edges
    interleaved[1::2] = layout.centers
    assert np.all(np.diff(interleaved) > 0)
    assert np.all(layout.reaches > 0)
    assert layout.margins == pytest.approx(MARGIN_FRACTION * layout.reaches)


def test_quantile_layout_lo_hi_are_the_p1_p99_edges() -> None:
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)

    assert layout.lo == pytest.approx(float(np.quantile(_RNG_FREE_SKEWED, 0.01)))
    assert layout.hi == pytest.approx(float(np.quantile(_RNG_FREE_SKEWED, 0.99)))
    assert layout.lo == layout.edges[0]
    assert layout.hi == layout.edges[-1]


def test_quantile_layout_rejects_tied_edges() -> None:
    """A constant feature is rejected, not nudged into range (NFR-5)."""
    with pytest.raises(ValueError, match="Tied bin edges"):
        _quantile_layout(np.full(50, 7.0), 3, PLACEMENT_QUANTILE)


@pytest.mark.parametrize(
    ("samples", "k", "match"),
    [
        (_RNG_FREE_SKEWED, 1, "at least 2"),
        (np.ones((4, 2)), 3, "1-dimensional"),
        (np.array([1.0, np.nan, 3.0]), 3, "finite"),
    ],
)
def test_quantile_layout_rejects_degenerate_input(
    samples: npt.NDArray[np.float64], k: int, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        _quantile_layout(samples, k, PLACEMENT_QUANTILE)


def test_unknown_placement_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown placement"):
        grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3, placement="midpoint")


# --------------------------------------------------------------------------
# grid_partition, per shape (section 9.1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shape", M1_SHAPES)
def test_partition_round_trips_its_own_validation(shape: type) -> None:
    """FR-8: every MF survives reconstruction and set_parameters from its own vector.

    The testable form of "passes its own validation": six of the seven classes
    expose ``_validate``, but ``GaussianMF`` checks inline, so the round trip is
    the only check that covers all seven uniformly.
    """
    mfs = grid_partition(shape, _RNG_FREE_SKEWED, 3, **_spread_for(shape, _RNG_FREE_SKEWED))

    assert len(mfs) == 3
    for mf in mfs:
        params = mf.parameters()
        rebuilt = type(mf)(*params)
        assert np.array_equal(rebuilt.parameters(), params)
        mf.set_parameters(params)


@pytest.mark.parametrize("shape", [GaussianMF, TanhMF, IntervalGaussianMF])
def test_bin_cover_rule_holds_on_a_dense_grid(shape: type) -> None:
    """FR-9: the best MF at any x in [e_0, e_k] has degree.low >= 0.5.

    ``.low`` rather than ``.midpoint``, so the IT2 lower bound is what is tested
    -- stricter than ``test_first_ensemble_run.test_upper_range_is_covered``.
    """
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    mfs = grid_partition(shape, _RNG_FREE_SKEWED, 3, **_spread_for(shape, _RNG_FREE_SKEWED))

    xs = np.linspace(layout.edges[0], layout.edges[-1], 1001)
    worst = min(max(mf.degree(float(x)).low for mf in mfs) for x in xs)
    assert worst >= 0.5


@pytest.mark.parametrize("shape", M1_SHAPES)
def test_partition_is_deterministic(shape: type) -> None:
    """FR-10: no RNG anywhere; two calls give identical parameter vectors."""
    kwargs = _spread_for(shape, _RNG_FREE_SKEWED)
    first = [mf.parameters() for mf in grid_partition(shape, _RNG_FREE_SKEWED, 3, **kwargs)]
    second = [mf.parameters() for mf in grid_partition(shape, _RNG_FREE_SKEWED, 3, **kwargs)]

    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))


def test_anchors_are_ascending_and_match_the_layout() -> None:
    """FR-6: anchors are the layout centers, from the same _quantile_layout call."""
    anchors = partition_anchors(_RNG_FREE_SKEWED, 3)
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)

    assert np.all(np.diff(anchors) > 0)
    assert np.array_equal(anchors, layout.centers)


def test_gaussian_centers_are_the_anchors() -> None:
    mfs = grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3)
    centers = np.array([mf.parameters()[0] for mf in mfs])

    assert np.array_equal(centers, partition_anchors(_RNG_FREE_SKEWED, 3))


def test_gaussian_sigma_puts_half_max_on_the_bin_edge() -> None:
    """sigma = r / sqrt(2 ln 2) makes mu(c +- r) exactly 0.5."""
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    mfs = grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3)

    for j, mf in enumerate(mfs):
        edge = float(layout.centers[j] + layout.reaches[j])
        assert mf.degree(edge).low == pytest.approx(0.5)


def test_interval_gaussian_footprint_is_the_lower_gaussian_blurred_by_the_spread() -> None:
    """sigma_high^2 = sigma_low^2 + s_q^2, strictly wider, and .low is the T1 width."""
    spread = 9.0
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    it2 = grid_partition(IntervalGaussianMF, _RNG_FREE_SKEWED, 3, qubit_spread=spread)
    t1 = grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3)

    for j, (mf, plain) in enumerate(zip(it2, t1, strict=True)):
        center, sigma_low, sigma_high = mf.parameters()
        assert center == pytest.approx(layout.centers[j])
        assert sigma_low == pytest.approx(plain.parameters()[1])
        assert sigma_high == pytest.approx(math.hypot(sigma_low, spread))
        assert sigma_low < sigma_high


@pytest.mark.parametrize("spread", [None, 0.0, -1.0, float("nan"), float("inf")])
def test_interval_gaussian_requires_a_finite_positive_spread(spread: float | None) -> None:
    with pytest.raises(ValueError, match="qubit_spread"):
        grid_partition(IntervalGaussianMF, _RNG_FREE_SKEWED, 3, qubit_spread=spread)


@pytest.mark.parametrize("shape", [GaussianMF, TanhMF, TanhSigmoidMF])
def test_qubit_spread_is_rejected_for_t1_shapes(shape: type) -> None:
    with pytest.raises(ValueError, match="not supported for T1 shape"):
        grid_partition(shape, _RNG_FREE_SKEWED, 3, qubit_spread=1.0)


@pytest.mark.parametrize("shape", SECOND_COMMIT_SHAPES)
def test_second_commit_shapes_raise_not_implemented(shape: type) -> None:
    """FR-5: a caller never receives a silently wrong partition for a late shape."""
    with pytest.raises(NotImplementedError, match="second commit before M2"):
        grid_partition(shape, _RNG_FREE_SKEWED, 3)


# --------------------------------------------------------------------------
# TanhSigmoidMF: cumulative levels (section 7 decision 1, section 9.3)
# --------------------------------------------------------------------------


def test_tanh_sigmoid_levels_are_ordered_and_cross_at_the_bin_edges() -> None:
    """mu_1 >= mu_2 >= mu_3 everywhere, and mu_j(e_(j-1)) == 0.5 for j >= 2.

    Level 1's center is deliberately offset to ``lo - m_1``, so asserting 0.5 at
    ``lo`` would contradict the ticket's own construction; what is pinned there
    is the constructed value ``(tanh(slope * m_1) + 1) / 2``.
    """
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    mfs = grid_partition(TanhSigmoidMF, _RNG_FREE_SKEWED, 3)

    xs = np.linspace(layout.edges[0], layout.edges[-1], 501)
    for x in xs:
        degrees = [mf.degree(float(x)).low for mf in mfs]
        assert degrees == sorted(degrees, reverse=True)

    for j in (1, 2):
        assert mfs[j].degree(float(layout.edges[j])).low == pytest.approx(0.5, abs=1e-12)

    slope = float(mfs[0].parameters()[1])
    expected_at_lo = (math.tanh(slope * float(layout.margins[0])) + 1.0) / 2.0
    assert mfs[0].degree(layout.lo).low == pytest.approx(expected_at_lo, abs=1e-12)
    assert expected_at_lo > 0.5


def test_tanh_sigmoid_shares_one_slope_across_levels() -> None:
    """Two rising sigmoids with different slopes cross inside the range."""
    slopes = {
        float(mf.parameters()[1]) for mf in grid_partition(TanhSigmoidMF, _RNG_FREE_SKEWED, 3)
    }

    assert len(slopes) == 1


# --------------------------------------------------------------------------
# TanhMF: ADR-023 floor onset, measured not assumed (section 7 decision 2)
# --------------------------------------------------------------------------


def test_tanh_floor_onset_matches_the_adr_023_closed_form() -> None:
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    u = layout.centers - layout.edges[:-1]
    v = layout.edges[1:] - layout.centers
    expected = layout.centers - 2.5 * u * v / (v - u)

    assert tanh_floor_onsets(_RNG_FREE_SKEWED, 3) == pytest.approx(expected)


def test_a_skewed_feature_takes_the_equal_slope_fallback() -> None:
    """An onset inside [lo, hi] switches that feature, and the switch is visible."""
    onsets = tanh_floor_onsets(_RNG_FREE_SKEWED, 3)
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    assert np.any((onsets >= layout.lo) & (onsets <= layout.hi))

    assert tanh_slope_strategy(_RNG_FREE_SKEWED, 3) == TANH_SLOPES_EQUAL
    for mf in grid_partition(TanhMF, _RNG_FREE_SKEWED, 3):
        _, _, slope_left, slope_right = mf.parameters()
        assert slope_left == pytest.approx(slope_right)


def test_the_equal_slope_fallback_coincides_with_tanh_bell() -> None:
    """Decision 2's consequence, pinned: the untrained rows are identical.

    ``TanhBellMF`` is a second-commit shape, so this compares against the bell's
    section 6.3 mapping constructed by hand rather than through
    ``grid_partition``, which is exactly what the ticket says must be stated in
    words until the second commit lands.
    """
    layout = _quantile_layout(_RNG_FREE_SKEWED, 3, PLACEMENT_QUANTILE)
    assert tanh_slope_strategy(_RNG_FREE_SKEWED, 3) == TANH_SLOPES_EQUAL

    for j, mf in enumerate(grid_partition(TanhMF, _RNG_FREE_SKEWED, 3)):
        c = float(layout.centers[j])
        r = float(layout.reaches[j])
        m = float(layout.margins[j])
        bell = TanhBellMF(c - r - m, c + r + m, math.atanh(EDGE_TANH_VALUE) / m)
        left, right, slope_left, slope_right = mf.parameters()
        assert (left, right) == pytest.approx(tuple(bell.parameters()[:2]))
        assert slope_left == pytest.approx(bell.parameters()[2])
        assert slope_right == pytest.approx(bell.parameters()[2])
        for x in np.linspace(layout.lo, layout.hi, 101):
            assert mf.degree(float(x)).low == pytest.approx(bell.degree(float(x)).low)


def test_an_unskewed_feature_keeps_the_half_reach_slopes() -> None:
    """A symmetric distribution puts every onset far outside the range, so no fallback.

    "Far outside" rather than "infinite": a uniform sample's half-reaches agree
    only to floating-point rounding, so ``u != v`` by a few ULPs and the closed
    form returns a huge finite number rather than ``inf``. Either way the floor
    never binds inside the domain box, which is the property that matters.
    """
    symmetric = np.linspace(0.0, 100.0, 1001)
    layout = _quantile_layout(symmetric, 3, PLACEMENT_QUANTILE)

    onsets = tanh_floor_onsets(symmetric, 3)
    assert not np.any((onsets >= layout.lo) & (onsets <= layout.hi))
    assert tanh_slope_strategy(symmetric, 3) == TANH_SLOPES_HALF_REACH


def test_half_reach_slopes_follow_the_section_6_3_mapping() -> None:
    """On a feature that keeps the default, each side's slope is atanh(0.8) / its margin."""
    left_skewed = np.concatenate([np.linspace(0.0, 20.0, 60), np.linspace(20.0, 100.0, 900)])
    if tanh_slope_strategy(left_skewed, 3) != TANH_SLOPES_HALF_REACH:
        pytest.skip("fixture is not in the half-reach branch")

    layout = _quantile_layout(left_skewed, 3, PLACEMENT_QUANTILE)
    for j, mf in enumerate(grid_partition(TanhMF, left_skewed, 3)):
        m_left = (float(layout.centers[j]) - float(layout.edges[j])) * MARGIN_FRACTION
        m_right = (float(layout.edges[j + 1]) - float(layout.centers[j])) * MARGIN_FRACTION
        left, right, slope_left, slope_right = mf.parameters()
        assert left == pytest.approx(float(layout.edges[j]) - m_left)
        assert right == pytest.approx(float(layout.edges[j + 1]) + m_right)
        assert slope_left == pytest.approx(math.atanh(EDGE_TANH_VALUE) / m_left)
        assert slope_right == pytest.approx(math.atanh(EDGE_TANH_VALUE) / m_right)


# --------------------------------------------------------------------------
# Legacy placements: Issue #31's comparison stays reproducible (FR-5, UC-4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("placement", [PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR])
def test_legacy_centers_equal_mf_centers_exactly(placement: str) -> None:
    """Equality against the shipped smoke script, not approximation."""
    lo, hi = 0.0, 100e-6
    mfs = grid_partition(GaussianMF, np.array([lo, hi]), 3, placement=placement)
    centers = tuple(float(mf.parameters()[0]) for mf in mfs)

    assert centers == pytest.approx(mf_centers(lo, hi, placement), abs=0.0, rel=1e-15)
    assert partition_anchors(np.array([lo, hi]), 3, placement=placement) == pytest.approx(
        np.array(mf_centers(lo, hi, placement))
    )


@pytest.mark.parametrize("placement", [PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR])
def test_legacy_gaussian_sigma_is_the_shipped_width(placement: str) -> None:
    """FR-5 pins ``sigma = 0.25 * (hi - lo)``, the width _default_mfs_for_feature ships."""
    lo, hi = 0.0, 100e-6
    mfs = grid_partition(GaussianMF, np.array([lo, hi]), 3, placement=placement)

    for mf in mfs:
        assert float(mf.parameters()[1]) == pytest.approx(0.25 * (hi - lo))


@pytest.mark.parametrize("placement", [PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR])
def test_legacy_placements_still_cover_their_range(placement: str) -> None:
    """The shipped sigma is wider than the bin-cover minimum, so FR-9 still holds."""
    lo, hi = 0.0, 100e-6
    layout = _quantile_layout(np.array([lo, hi]), 3, placement)
    mfs = grid_partition(GaussianMF, np.array([lo, hi]), 3, placement=placement)

    xs = np.linspace(layout.edges[0], layout.edges[-1], 501)
    assert min(max(mf.degree(float(x)).low for mf in mfs) for x in xs) >= 0.5


@pytest.mark.parametrize("placement", [PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR])
def test_legacy_placements_require_a_two_vector(placement: str) -> None:
    with pytest.raises(ValueError, match="2-vector"):
        grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3, placement=placement)


@pytest.mark.parametrize("placement", [PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR])
def test_legacy_placements_require_lo_below_hi(placement: str) -> None:
    with pytest.raises(ValueError, match="requires lo < hi"):
        grid_partition(GaussianMF, np.array([1.0, 1.0]), 3, placement=placement)


# --------------------------------------------------------------------------
# anchored_rule_base (FR-7, NFR-7, section 9.1)
# --------------------------------------------------------------------------


def _three_feature_grid() -> tuple[
    list[list[Any]], list[npt.NDArray[np.float64]], list[npt.NDArray[np.float64]]
]:
    samples = [_RNG_FREE_SKEWED, _RNG_FREE_SKEWED * 0.7, _RNG_FREE_SKEWED / 5000.0]
    mfs = [grid_partition(GaussianMF, s, 3) for s in samples]
    anchors = [partition_anchors(s, 3) for s in samples]
    return mfs, anchors, samples


def test_anchored_rule_base_builds_the_27_rule_grid() -> None:
    mfs, anchors, _ = _three_feature_grid()

    rb = anchored_rule_base(mfs, _synthetic_target, anchors=anchors)

    assert len(rb.rules) == 27
    assert rb.input_dim == 3
    assert rb.output_dim == 2


def test_rules_share_the_nine_membership_objects() -> None:
    """NFR-7: 81 antecedent references over 9 unique objects, as ``from_grid`` does.

    Copies here would silently inflate the trainable premise count from 18 to
    162 on the Gaussian grid.
    """
    mfs, anchors, _ = _three_feature_grid()

    rb = anchored_rule_base(mfs, _synthetic_target, anchors=anchors)

    assert len({id(mf) for rule in rb.rules for mf in rule.antecedent_mfs}) == 9
    assert sum(len(rule.antecedent_mfs) for rule in rb.rules) == 81


def test_rule_order_and_antecedent_identity_follow_the_anchor_product() -> None:
    """Rule r's antecedents are, by identity, the MFs whose anchors formed x_r."""
    mfs, anchors, _ = _three_feature_grid()

    rb = anchored_rule_base(mfs, _synthetic_target, anchors=anchors)

    index = 0
    for i in range(3):
        for j in range(3):
            for k in range(3):
                rule = rb.rules[index]
                assert [id(m) for m in rule.antecedent_mfs] == [
                    id(mfs[0][i]),
                    id(mfs[1][j]),
                    id(mfs[2][k]),
                ]
                x_r = np.array([anchors[0][i], anchors[1][j], anchors[2][k]])
                assert rule.consequent_params[:, -1] == pytest.approx(_synthetic_target(x_r))
                index += 1


def test_consequents_are_zero_order_and_separately_allocated() -> None:
    """Input columns exactly zero; a fresh array per rule, because TSKRule aliases."""
    mfs, anchors, _ = _three_feature_grid()

    rb = anchored_rule_base(mfs, _synthetic_target, anchors=anchors)

    assert all(np.all(rule.consequent_params[:, :-1] == 0.0) for rule in rb.rules)
    assert len({id(rule.consequent_params) for rule in rb.rules}) == 27


def test_anchors_are_keyword_only_and_required() -> None:
    mfs, anchors, _ = _three_feature_grid()

    with pytest.raises(TypeError):
        anchored_rule_base(mfs, _synthetic_target)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        anchored_rule_base(mfs, _synthetic_target, anchors)  # type: ignore[misc]


def test_anchor_length_mismatch_is_rejected() -> None:
    mfs, anchors, _ = _three_feature_grid()

    with pytest.raises(ValueError, match="Expected 3 anchor arrays"):
        anchored_rule_base(mfs, _synthetic_target, anchors=anchors[:2])
    with pytest.raises(ValueError, match="must match length of MFs"):
        anchored_rule_base(mfs, _synthetic_target, anchors=[anchors[0][:2], *anchors[1:]])


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_non_finite_target_is_rejected(bad: float) -> None:
    """NFR-5: a NaN bias would install maximal damping and still pass every check."""
    mfs, anchors, _ = _three_feature_grid()

    with pytest.raises(ValueError, match="non-finite"):
        anchored_rule_base(mfs, lambda _x: np.array([bad, 1e-4]), anchors=anchors)


def test_inconsistent_output_dim_is_rejected() -> None:
    mfs, anchors, _ = _three_feature_grid()
    calls: list[int] = []

    def wobbling(x: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        calls.append(1)
        return np.ones(2 if len(calls) == 1 else 3)

    with pytest.raises(ValueError, match="Inconsistent output_dim"):
        anchored_rule_base(mfs, wobbling, anchors=anchors)


def test_non_vector_target_is_rejected() -> None:
    mfs, anchors, _ = _three_feature_grid()

    with pytest.raises(ValueError, match="1-D vector"):
        anchored_rule_base(mfs, lambda _x: np.ones((2, 2)), anchors=anchors)


# --------------------------------------------------------------------------
# ClampingFeatureExtractor (FR-12, section 9.1)
# --------------------------------------------------------------------------


@pytest.fixture
def clamp() -> ClampingFeatureExtractor:
    return ClampingFeatureExtractor(
        BasicCalibrationVectorizer(),
        np.array([100.0, 80.0, 0.01]),
        np.array([200.0, 120.0, 0.05]),
    )


def test_clamp_forwards_metadata(clamp: ClampingFeatureExtractor) -> None:
    inner = BasicCalibrationVectorizer()

    assert clamp.output_dim == inner.output_dim
    assert clamp.feature_names == inner.feature_names


def test_in_range_vector_passes_through_uncounted(clamp: ClampingFeatureExtractor) -> None:
    out = clamp.extract(_synthetic_snapshot(150.0, 100.0, 0.02))

    assert out == pytest.approx(np.array([150.0, 100.0, 0.02]))
    assert clamp.n_extractions == 1
    assert clamp.n_clamped_vectors == 0
    assert np.array_equal(clamp.n_clamped_components, np.zeros(3, dtype=np.int64))


def test_clamped_components_are_attributed_to_the_right_feature(
    clamp: ClampingFeatureExtractor,
) -> None:
    """The ablation needs to know *which* feature left the box, not just that one did."""
    out = clamp.extract(_synthetic_snapshot(5000.0, 100.0, 0.001))

    assert out == pytest.approx(np.array([200.0, 100.0, 0.01]))
    assert clamp.n_extractions == 1
    assert clamp.n_clamped_vectors == 1
    assert np.array_equal(clamp.n_clamped_components, np.array([1, 0, 1], dtype=np.int64))


def test_counters_are_cumulative_and_vectors_count_calls(clamp: ClampingFeatureExtractor) -> None:
    clamp.extract(_synthetic_snapshot(150.0, 100.0, 0.02))
    clamp.extract(_synthetic_snapshot(5000.0, 100.0, 0.02))
    clamp.extract(_synthetic_snapshot(150.0, 1.0, 0.02))

    assert clamp.n_extractions == 3
    assert clamp.n_clamped_vectors == 2
    assert np.array_equal(clamp.n_clamped_components, np.array([1, 1, 0], dtype=np.int64))


def test_clamp_counter_arrays_are_copies(clamp: ClampingFeatureExtractor) -> None:
    clamp.extract(_synthetic_snapshot(5000.0, 100.0, 0.02))
    snapshot_of_counter = clamp.n_clamped_components
    snapshot_of_counter[:] = 99

    assert np.array_equal(clamp.n_clamped_components, np.array([1, 0, 0], dtype=np.int64))


def test_clamp_returns_a_fresh_array_and_does_not_mutate_inner() -> None:
    class Recording(BasicCalibrationVectorizer):
        def __init__(self) -> None:
            self.last: npt.NDArray[np.float64] | None = None

        def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
            self.last = super().extract(snapshot)
            return self.last

    inner = Recording()
    wrapper = ClampingFeatureExtractor(
        inner, np.array([100.0, 80.0, 0.01]), np.array([200.0, 120.0, 0.05])
    )

    out = wrapper.extract(_synthetic_snapshot(150.0, 100.0, 0.02))

    assert inner.last is not None
    assert out is not inner.last
    assert inner.last == pytest.approx(np.array([150.0, 100.0, 0.02]))


@pytest.mark.parametrize(
    ("lo", "hi", "match"),
    [
        (np.array([1.0, 2.0]), np.array([3.0, 4.0, 5.0]), "length inner.output_dim"),
        (np.array([1.0, 2.0, 3.0]), np.array([3.0, 4.0]), "length inner.output_dim"),
        (np.zeros((3, 1)), np.ones((3, 1)), "1-dimensional"),
        (np.array([1.0, 2.0, 3.0]), np.array([1.0, 4.0, 5.0]), "strictly less than"),
        (np.array([1.0, 2.0, 3.0]), np.array([np.inf, 4.0, 5.0]), "finite"),
    ],
)
def test_clamp_constructor_rejects_bad_bounds(
    lo: npt.NDArray[np.float64], hi: npt.NDArray[np.float64], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ClampingFeatureExtractor(BasicCalibrationVectorizer(), lo, hi)


# --------------------------------------------------------------------------
# Conformance on the committed survey's real quantiles (section 9.3)
# --------------------------------------------------------------------------


def _committed_survey() -> tuple[dict[str, npt.NDArray[np.float64]], dict[str, float]]:
    matches = sorted(SURVEY_DIR.glob("*.tsv"))
    if not matches:
        pytest.skip("no committed feature-distribution survey")

    with matches[-1].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    samples = {
        name: np.array([float(r[name]) for r in rows if r[name]], dtype=np.float64)
        for name in FEATURE_COLUMNS
    }
    spreads = {
        name: float(np.median([float(r[col]) for r in rows if r[col]]))
        for name, col in zip(FEATURE_COLUMNS, SPREAD_COLUMNS, strict=True)
    }
    return samples, spreads


@pytest.mark.parametrize("shape", [GaussianMF, TanhMF, IntervalGaussianMF])
def test_bin_cover_holds_on_the_real_quantiles(shape: type) -> None:
    """Section 9.3: the Issue #31 property, asserted on the archive rather than a range."""
    samples, spreads = _committed_survey()

    for name, values in samples.items():
        kwargs = {"qubit_spread": spreads[name]} if shape is IntervalGaussianMF else {}
        layout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        mfs = grid_partition(shape, values, 3, **kwargs)
        xs = np.linspace(layout.edges[0], layout.edges[-1], 601)
        assert min(max(mf.degree(float(x)).low for mf in mfs) for x in xs) >= 0.5


def test_tanh_branch_taken_on_the_real_quantiles_is_pinned() -> None:
    """Step 5b: the nine x*_j are computed, and the shipped slopes match the branch.

    Deliberately not asserted to lie outside ``[lo, hi]`` -- on a right-skewed
    feature that assertion is false by construction.
    """
    samples, _ = _committed_survey()

    for name, values in samples.items():
        onsets = tanh_floor_onsets(values, 3)
        layout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        inside = bool(np.any((onsets >= layout.lo) & (onsets <= layout.hi)))
        strategy = tanh_slope_strategy(values, 3)
        assert strategy == (TANH_SLOPES_EQUAL if inside else TANH_SLOPES_HALF_REACH)

        for mf in grid_partition(TanhMF, values, 3):
            _, _, slope_left, slope_right = mf.parameters()
            if strategy == TANH_SLOPES_EQUAL:
                assert slope_left == pytest.approx(slope_right)
        assert onsets.shape == (3,), f"{name} must report one onset per level"


def test_sigmoid_ordering_holds_on_the_real_quantiles() -> None:
    samples, _ = _committed_survey()

    for values in samples.values():
        layout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        mfs = grid_partition(TanhSigmoidMF, values, 3)
        for x in np.linspace(layout.lo, layout.hi, 301):
            degrees = [mf.degree(float(x)).low for mf in mfs]
            assert degrees == sorted(degrees, reverse=True)
        for j in (1, 2):
            assert mfs[j].degree(float(layout.edges[j])).low == pytest.approx(0.5, abs=1e-12)


@pytest.mark.parametrize(
    ("shape", "defuzzifier"),
    [
        (GaussianMF, WeightedAverageDefuzzifier),
        (TanhMF, WeightedAverageDefuzzifier),
        (TanhSigmoidMF, WeightedAverageDefuzzifier),
        (IntervalGaussianMF, NieTanDefuzzifier),
    ],
)
def test_anchored_base_is_never_degenerate_on_the_archive(shape: type, defuzzifier: type) -> None:
    """FR-11, step 9: every surveyed feature vector, through the clamp, every M1 shape.

    Not luck but a theorem (section 6.5): with zero-order consequents the
    defuzzified output is a convex combination of the anchor targets, so it
    stays inside their range and ``is_identity_damping`` is False wherever some
    rule fires -- which the bin-cover rule guarantees inside ``[lo, hi]``.
    """
    samples, spreads = _committed_survey()
    values = [samples[name] for name in FEATURE_COLUMNS]

    mfs = [
        grid_partition(
            shape,
            v,
            3,
            **({"qubit_spread": spreads[name]} if shape is IntervalGaussianMF else {}),
        )
        for name, v in zip(FEATURE_COLUMNS, values, strict=True)
    ]
    anchors = [partition_anchors(v, 3) for v in values]
    rb = anchored_rule_base(mfs, _synthetic_target, anchors=anchors)

    lo = np.array([_quantile_layout(v, 3, PLACEMENT_QUANTILE).lo for v in values])
    hi = np.array([_quantile_layout(v, 3, PLACEMENT_QUANTILE).hi for v in values])
    vectors = np.clip(np.column_stack(values), lo, hi)

    biases = np.array([rule.consequent_params[:, -1] for rule in rb.rules])
    engine = defuzzifier()
    for x in vectors:
        crisp = np.asarray(engine.defuzzify(rb.evaluate(x))).reshape(-1)
        assert not is_identity_damping(crisp)
        assert np.all(crisp >= biases.min(axis=0) - 1e-12)
        assert np.all(crisp <= biases.max(axis=0) + 1e-12)


def test_layout_is_shared_between_partition_and_anchors_on_the_real_quantiles() -> None:
    """FR-6's real invariant: no two callers ever see two different layouts."""
    samples, _ = _committed_survey()

    for values in samples.values():
        layout: QuantileLayout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        assert np.array_equal(partition_anchors(values, 3), layout.centers)
        centers = np.array([mf.parameters()[0] for mf in grid_partition(GaussianMF, values, 3)])
        assert np.array_equal(centers, layout.centers)
