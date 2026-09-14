"""Property suite for ``superconducted.fuzzy.parameterization`` (Issue #59 section 9).

The suite is organised the way the ticket is: unit properties per shape, then
the anchored rule base's structural contract, then the clamp, then the
conformance checks that run on the **committed survey's real quantiles** rather
than on synthetic samples. Nothing here touches the network or the archive; the
committed TSV is the durable record.
"""

from __future__ import annotations

import csv
import functools
import itertools
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from scripts.compare_mf_placement import main as compare_mf_placement_main
from scripts.compare_mf_placement import rule_count
from scripts.first_ensemble_run import mf_centers

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import NieTanDefuzzifier, WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
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
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble, is_identity_damping
from superconducted.training.targets import feature_target_fn
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

#: The reference gate the physics target is evaluated at: `ibm_fez`'s `sx`
#: length, 24 ns (NC-035).
SX_SECONDS = 24e-9

#: The archive ref the pinned conformance numbers below were measured at. The
#: shape properties (coverage, ordering, non-degeneracy) hold for any survey;
#: the *values* -- which ADR-023 branch each feature takes, how many rows the
#: clamp moved -- are properties of this one, so the tests that pin them skip
#: rather than fail when a later survey at a new ref becomes the newest TSV.
SURVEY_REF = "3d1569d"

#: Step 5b's nine `x*_j`, measured on the `SURVEY_REF` survey, and which of
#: them land inside their feature's domain box. Pinned as literals on purpose:
#: recomputing `inside` from the module's own onset formula and asserting the
#: module agrees with itself is not a test, and that is what this file did
#: before -- a layout regression that flipped every feature to half-reach would
#: have gone green. The implementation doc's step-5b table carries the same
#: numbers, so a genuine change fails here and there together.
EXPECTED_ONSETS: dict[str, tuple[float, float, float]] = {
    "mean_T1": (149.15620978103783, 159.64859067441097, 100.09407855131994),
    "mean_T2": (116.1544000691872, 3.658257158133736, 81.97290471387986),
    "mean_readout_error": (0.030559118805391992, 0.013965141538381243, -0.03160349544324337),
}
EXPECTED_ONSET_INSIDE: dict[str, tuple[bool, bool, bool]] = {
    "mean_T1": (True, False, True),
    "mean_T2": (False, False, True),
    "mean_readout_error": (True, False, False),
}

#: The measured clamp rate of Issue #59 step 9, which the ablation (#62) has to
#: report per run: 44 of 975 surveyed vectors leave the domain box, attributed
#: 16 / 11 / 20 across the three features. Measured, never derived -- a
#: per-feature 2% tail only bounds the vector rate between 2% and about 6%.
EXPECTED_CLAMPED_VECTORS = 44
EXPECTED_CLAMPED_COMPONENTS = (16, 11, 20)


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
    """A cheap stand-in for the real target, used by the structural unit tests.

    Monotone in T1 and strictly inside ``(0, 1)`` for every anchor this suite
    builds, which is all the rule-base contract tests need. The conformance
    tests use the real ``training.targets.feature_target_fn`` -- a synthetic
    target cannot catch a unit error, and section 6.4 (c) says so explicitly.
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
def test_legacy_pin_is_for_the_gaussian_only(placement: str) -> None:
    """FR-5 pins ``0.25 * (hi - lo)`` for ``GaussianMF``; the other shapes take r_j.

    The pin exists so ``first_ensemble_run``'s own numbers reproduce by
    equality, and that script builds Gaussians and nothing else. FR-5 gives
    every other shape "the same centers and the section 6.3 widths with ``r_j``
    derived from the equal spacing", so an IT2 footprint built on the legacy
    width would be a third parameterization nobody asked for -- and it is not
    the same number: 25.0 against 21.233 at endpoint on a span of 100.
    """
    lo, hi = 0.0, 100e-6
    samples = np.array([lo, hi])
    layout = _quantile_layout(samples, 3, placement)
    expected = layout.reaches / math.sqrt(2.0 * math.log(2.0))

    mfs = grid_partition(IntervalGaussianMF, samples, 3, placement=placement, qubit_spread=1e-6)

    for j, mf in enumerate(mfs):
        center, sigma_low, sigma_high = mf.parameters()
        assert center == pytest.approx(layout.centers[j])
        assert sigma_low == pytest.approx(expected[j])
        assert sigma_low != pytest.approx(0.25 * (hi - lo))
        assert sigma_high > sigma_low


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


def test_zero_length_target_is_rejected() -> None:
    """A zero-length target is a contract violation, not an ``output_dim`` default.

    It is 1-D and finite, so it passes both of the other guards; without this
    one it built a rule base with no output columns, which defuzzifies to
    nothing and fails somewhere far from the cause.
    """
    mfs, anchors, _ = _three_feature_grid()

    with pytest.raises(ValueError, match="zero-length vector"):
        anchored_rule_base(mfs, lambda _x: np.zeros(0), anchors=anchors)


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


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_a_non_finite_feature_is_rejected_rather_than_clamped(bad: float) -> None:
    """The one input the clamp does not absorb, and the reason it must not.

    ``np.clip`` preserves NaN, so passing it through makes every firing strength
    NaN; the defuzzifier does not raise (the sum is NaN, not zero),
    ``KrausChannelProjector`` maps NaN to maximal damping, and
    ``is_identity_damping`` simultaneously reports the vector as the identity
    channel. Wrong in both directions with every check green -- exactly the
    failure mode NFR-5 exists to kill.
    """

    class NonFinite(BasicCalibrationVectorizer):
        def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
            return np.array([bad, 100.0, 0.02])

    wrapper = ClampingFeatureExtractor(
        NonFinite(), np.array([100.0, 80.0, 0.01]), np.array([200.0, 120.0, 0.05])
    )

    with pytest.raises(ValueError, match="non-finite feature"):
        wrapper.extract(_synthetic_snapshot(150.0, 100.0, 0.02))

    # Raised before the counters moved, so they only describe successful calls.
    assert wrapper.n_extractions == 0
    assert wrapper.n_clamped_vectors == 0


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


def _committed_survey_path() -> Path:
    matches = sorted(SURVEY_DIR.glob("*.tsv"))
    if not matches:
        pytest.skip("no committed feature-distribution survey")
    return matches[-1]


def _require_pinned_survey() -> None:
    """Skip when the newest survey is not the one the pinned values were measured at."""
    stem = _committed_survey_path().stem
    if SURVEY_REF not in stem:
        pytest.skip(f"pinned values were measured on {SURVEY_REF}, newest survey is {stem}")


def _committed_survey() -> tuple[dict[str, npt.NDArray[np.float64]], dict[str, float]]:
    with _committed_survey_path().open(newline="", encoding="utf-8") as handle:
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


def _committed_feature_vectors() -> npt.NDArray[np.float64]:
    """The surveyed feature vectors, one row per snapshot, kept row-aligned.

    Built in one pass over the rows that carry all three means, not by stacking
    the three independently filtered per-feature arrays: those happen to be
    equal-length only because no row in this survey was rejected, and one
    rejected row would silently pair a snapshot's T1 with a different
    snapshot's T2 (or raise on a length mismatch, if you were lucky).
    """
    with _committed_survey_path().open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return np.array(
        [
            [float(row[name]) for name in FEATURE_COLUMNS]
            for row in rows
            if all(row[name] for name in FEATURE_COLUMNS)
        ],
        dtype=np.float64,
    )


def _domain_box(
    samples: dict[str, npt.NDArray[np.float64]],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """The per-feature ``[p1, p99]`` box the partition is defined on."""
    layouts = [_quantile_layout(samples[name], 3, PLACEMENT_QUANTILE) for name in FEATURE_COLUMNS]
    return (
        np.array([layout.lo for layout in layouts]),
        np.array([layout.hi for layout in layouts]),
    )


def _archive_partition(
    shape: type, samples: dict[str, npt.NDArray[np.float64]], spreads: dict[str, float]
) -> tuple[list[list[Any]], list[npt.NDArray[np.float64]]]:
    """The per-feature MFs and anchors for one shape on the committed survey."""
    mfs = [
        grid_partition(
            shape,
            samples[name],
            3,
            **({"qubit_spread": spreads[name]} if shape is IntervalGaussianMF else {}),
        )
        for name in FEATURE_COLUMNS
    ]
    anchors = [partition_anchors(samples[name], 3) for name in FEATURE_COLUMNS]
    return mfs, anchors


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
    """Step 5b: the nine x*_j are pinned as values, and the shipped slopes match.

    Deliberately not asserted to lie outside ``[lo, hi]`` -- on a right-skewed
    feature that assertion is false by construction, and four of these nine do
    land inside. What is asserted instead is the measurement itself, so this
    fails if the layout moves rather than agreeing with whatever the module
    currently computes.
    """
    _require_pinned_survey()
    samples, _ = _committed_survey()

    for name, values in samples.items():
        layout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        onsets = tanh_floor_onsets(values, 3)

        assert onsets.shape == (3,), f"{name} must report one onset per level"
        assert onsets == pytest.approx(EXPECTED_ONSETS[name], rel=1e-12)
        inside = tuple(bool(b) for b in (onsets >= layout.lo) & (onsets <= layout.hi))
        assert inside == EXPECTED_ONSET_INSIDE[name]

        # Every feature has at least one floored tail inside its box, so every
        # feature takes decision 2's fallback -- which means each TanhMF row
        # coincides with its TanhBellMF row until the trainer runs. That
        # consequence belongs in the ablation caption, not a footnote.
        assert tanh_slope_strategy(values, 3) == TANH_SLOPES_EQUAL
        for mf in grid_partition(TanhMF, values, 3):
            _, _, slope_left, slope_right = mf.parameters()
            assert slope_left == pytest.approx(slope_right)


def test_forcing_half_reach_slopes_reinstates_the_unequal_mapping() -> None:
    """The decision-2 counterfactual is reachable, and only through the override.

    Every surveyed feature measures ``equal-slope``, so without an explicit
    ``tanh_slopes`` nothing in the suite can exercise the half-reach branch on
    real data or show what the fallback bought.
    """
    _require_pinned_survey()
    samples, _ = _committed_survey()
    values = samples["mean_T1"]

    forced = np.array(
        [
            mf.parameters()
            for mf in grid_partition(TanhMF, values, 3, tanh_slopes=TANH_SLOPES_HALF_REACH)
        ]
    )
    default = np.array([mf.parameters() for mf in grid_partition(TanhMF, values, 3)])
    explicit_fallback = np.array(
        [mf.parameters() for mf in grid_partition(TanhMF, values, 3, tanh_slopes=TANH_SLOPES_EQUAL)]
    )

    assert np.any(forced[:, 2] != forced[:, 3]), "half-reach must give a skewed bin two slopes"
    assert not np.allclose(forced, default)
    # The explicit fallback reproduces the measured default exactly.
    assert np.array_equal(explicit_fallback, default)


def test_tanh_slopes_is_rejected_for_other_shapes_and_unknown_values() -> None:
    with pytest.raises(ValueError, match="only meaningful for TanhMF"):
        grid_partition(GaussianMF, _RNG_FREE_SKEWED, 3, tanh_slopes=TANH_SLOPES_EQUAL)

    with pytest.raises(ValueError, match="unknown tanh_slopes"):
        grid_partition(TanhMF, _RNG_FREE_SKEWED, 3, tanh_slopes="steepest")


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


def test_the_target_magnitude_at_the_median_anchor_catches_a_unit_error() -> None:
    """Section 6.4 (c): the only check in this suite that can see a unit error.

    Feeding 131.8 (microseconds, read as if seconds) to ``1 - exp(-t/T1)`` with
    ``t = 24 ns`` gives a gamma around 1e-10 where the physics gives 1e-4. That
    wrong value is finite, strictly positive and inside ``(0, 1)``, so
    ``is_identity_damping`` stays False, the convexity bound holds, and every
    other check in this file goes green on a model wrong by six orders of
    magnitude. Only the magnitude catches it.
    """
    samples, _ = _committed_survey()
    median_anchor = np.array([partition_anchors(samples[name], 3)[1] for name in FEATURE_COLUMNS])

    gamma, lam = feature_target_fn(median_anchor, t_seconds=SX_SECONDS)

    assert 1e-5 < gamma < 1e-3, f"gamma {gamma:.3e} is not of order 1e-4"
    assert 1e-5 < lam < 1e-3, f"lambda {lam:.3e} is not of order 1e-4"


def test_every_anchor_is_accepted_by_the_real_target() -> None:
    """All 27 anchor combinations satisfy ``feature_target_fn``'s own guards.

    It rejects ``mean_T2 > 2 * mean_T1``, and the grid pairs each feature's
    levels independently -- the lowest T1 anchor meets the highest T2 anchor --
    so this is not automatic from the per-feature quantiles.
    """
    samples, _ = _committed_survey()
    anchors = [partition_anchors(samples[name], 3) for name in FEATURE_COLUMNS]

    targets = np.array(
        [
            feature_target_fn(np.array(combo), t_seconds=SX_SECONDS)
            for combo in itertools.product(*anchors)
        ]
    )

    assert targets.shape == (27, 2)
    assert np.all((targets > 0.0) & (targets < 1.0))


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
    """FR-11, step 9: every surveyed vector, through the clamp, real target, every M1 shape.

    The clamp here is the real ``ClampingFeatureExtractor``, not a bare
    ``np.clip``: step 9 says this is "the exact object the ablation will hand to
    the harness, evaluated on the exact inputs the archive produces", and an
    inlined clip would leave FR-12's wrapper -- the only place the out-of-range
    policy is applied -- unexercised on the archive.

    Not luck but a theorem (section 6.5): with zero-order consequents the
    defuzzified output is a convex combination of the anchor targets, so it
    stays inside their range and ``is_identity_damping`` is False wherever some
    rule fires -- which the bin-cover rule guarantees inside ``[lo, hi]``.
    """
    samples, spreads = _committed_survey()
    mfs, anchors = _archive_partition(shape, samples, spreads)
    target = functools.partial(feature_target_fn, t_seconds=SX_SECONDS)
    rb = anchored_rule_base(mfs, target, anchors=anchors)

    lo, hi = _domain_box(samples)
    clamp = ClampingFeatureExtractor(BasicCalibrationVectorizer(), lo, hi)
    raw_vectors = _committed_feature_vectors()

    biases = np.array([rule.consequent_params[:, -1] for rule in rb.rules])
    engine = defuzzifier()
    for row in raw_vectors:
        x = clamp.extract(_synthetic_snapshot(*row))
        crisp = np.asarray(engine.defuzzify(rb.evaluate(x))).reshape(-1)
        assert not is_identity_damping(crisp)
        assert np.all(crisp >= biases.min(axis=0) - 1e-12)
        assert np.all(crisp <= biases.max(axis=0) + 1e-12)

    assert clamp.n_extractions == len(raw_vectors)


def test_the_measured_clamp_rate_is_pinned() -> None:
    """Step 9's "measure the clamp rate; do not derive it", pinned in the suite.

    The ablation (#62) has to report this per run, and the implementation doc
    and the evidence README both quote it, so it needs one place that fails when
    it moves.
    """
    _require_pinned_survey()
    samples, _ = _committed_survey()
    lo, hi = _domain_box(samples)
    clamp = ClampingFeatureExtractor(BasicCalibrationVectorizer(), lo, hi)

    vectors = _committed_feature_vectors()
    for row in vectors:
        clamp.extract(_synthetic_snapshot(*row))

    assert clamp.n_extractions == len(vectors)
    assert clamp.n_clamped_vectors == EXPECTED_CLAMPED_VECTORS
    assert tuple(clamp.n_clamped_components) == EXPECTED_CLAMPED_COMPONENTS


def test_the_ensemble_evaluates_an_out_of_range_snapshot_through_the_clamp() -> None:
    """UC-7 and FR-12's reason for existing: the ablation's real injection path.

    ``FuzzyNoiseModel._compute_crisp_params`` extracts and evaluates back to
    back with no interception point, so injecting this wrapper as
    ``feature_extractor`` is the only way a caller that builds an ensemble can
    apply the out-of-range policy at all (architect decision B6).

    The unwrapped contrast section 9.2 asks for -- the same snapshot raising for
    ``TriangularMF`` and ``TrapezoidalMF`` -- cannot be asserted yet: those two
    are the only compact-support shapes and they land in the second commit
    (architect decision C3), while all four M1 shapes have unbounded support and
    fire something everywhere. Step 5c adds it.
    """
    samples, spreads = _committed_survey()
    mfs, anchors = _archive_partition(GaussianMF, samples, spreads)
    rb = anchored_rule_base(
        mfs, functools.partial(feature_target_fn, t_seconds=SX_SECONDS), anchors=anchors
    )

    lo, hi = _domain_box(samples)
    clamp = ClampingFeatureExtractor(BasicCalibrationVectorizer(), lo, hi)

    # Well outside the box on all three features, in both directions.
    outside = _synthetic_snapshot(5000.0, 1.0, 0.9)
    ensemble = FuzzyNoiseModelEnsemble(
        calibration=outside,
        feature_extractor=clamp,
        rule_base=rb,
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        ensemble_size=4,
    )

    members = list(ensemble)
    assert len(members) == 4
    for member in members:
        assert np.all(np.isfinite(member.crisp_params))
        assert not member.is_degenerate

    # Section 6.4 (a): the counters count *calls*, so four members built from
    # one snapshot record four extractions of one vector. A clamp rate over
    # distinct snapshots must divide by the ensemble size.
    assert clamp.n_extractions == 4
    assert clamp.n_clamped_vectors == 4
    assert tuple(clamp.n_clamped_components) == (4, 4, 4)


def test_compare_mf_placement_still_runs_and_still_reports_27_rules(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """UC-4: Issue #31's comparison stays reproducible while this module lands."""
    for placement in (PLACEMENT_ENDPOINT, PLACEMENT_INTERIOR):
        assert rule_count(placement) == 27

    compare_mf_placement_main()
    printed = capsys.readouterr().out

    assert "n_rules" in printed
    assert "MISMATCH" not in printed


def test_layout_is_shared_between_partition_and_anchors_on_the_real_quantiles() -> None:
    """FR-6's real invariant: no two callers ever see two different layouts."""
    samples, _ = _committed_survey()

    for values in samples.values():
        layout: QuantileLayout = _quantile_layout(values, 3, PLACEMENT_QUANTILE)
        assert np.array_equal(partition_anchors(values, 3), layout.centers)
        centers = np.array([mf.parameters()[0] for mf in grid_partition(GaussianMF, values, 3)])
        assert np.array_equal(centers, layout.centers)
