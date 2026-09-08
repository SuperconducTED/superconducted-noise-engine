"""Data-driven membership-function parameterization (Issue #59, Part B).

Turns the calibration archive's own feature distribution into a `k`-level grid
partition and an anchored TSK rule base, so nothing in the untrained model is a
random draw: every membership parameter is a stated function of a quantile in
``docs/evidence/feature-distribution/``, and every consequent bias is a physics
target evaluated at a stated anchor.

Two conventions that look inconsistent until you read them together (NFR-5):

* **Parameters are rejected, never clipped.** A degenerate layout (tied
  quantiles, a non-positive reach, a zero IT2 spread) is a bug in this module,
  so :func:`grid_partition` raises ``ValueError`` at construction rather than
  nudging a value into range. That is ADR-018's convention.
* **Inputs are clamped, never rejected.** A feature vector outside the domain
  box is a legitimate archived measurement that simply sits outside the model's
  stated domain, and the ablation cannot crash mid-run on it, so
  :class:`ClampingFeatureExtractor` moves it onto the boundary and counts it.

No direct qiskit use here; qiskit arrives transitively through
``superconducted.interfaces``, which imports it at module level for the ABCs
this module implements and consumes (NFR-1).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF, TanhMF, TanhSigmoidMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.interfaces import CalibrationFeatureExtractor, MembershipFunction
from superconducted.types import CalibrationSnapshot

#: Quantiles of the snapshot values that bound the domain box ``[lo, hi]``.
#: p1/p99 rather than min/max because the archive's tails are set by outliers
#: (#45's 2026-08-28 integrity audit: per-qubit T1 from 4.8 to 409 us).
DOMAIN_LO_QUANTILE: Final[float] = 0.01
DOMAIN_HI_QUANTILE: Final[float] = 0.99

#: ``numpy.quantile`` interpolation. Named because a different method moves
#: every center, and the committed survey's quantiles would stop reproducing.
QUANTILE_METHOD: Final = "linear"

#: ``m_j = MARGIN_FRACTION * r_j`` -- how far past a bin edge a tanh shape's
#: transition point sits. A default, not a measurement (section 6.3).
MARGIN_FRACTION: Final[float] = 0.25

#: The tanh value one margin away from a transition point, so the membership
#: there is ``(1 + 0.8) / 2 = 0.9``. Also a default, not a measurement.
EDGE_TANH_VALUE: Final[float] = 0.8

PLACEMENT_QUANTILE: Final[str] = "quantile"
PLACEMENT_ENDPOINT: Final[str] = "endpoint"
PLACEMENT_INTERIOR: Final[str] = "interior"
PLACEMENTS: Final[tuple[str, ...]] = (
    PLACEMENT_QUANTILE,
    PLACEMENT_ENDPOINT,
    PLACEMENT_INTERIOR,
)

#: ``TanhMF`` slope strategies (section 7 decision 2). ``half-reach`` is the
#: default; ``equal-slope`` is the per-feature fallback, and a feature that
#: takes it has a ``TanhMF`` row identical to its ``TanhBellMF`` row until the
#: trainer runs -- state that in any results caption built from it.
TANH_SLOPES_HALF_REACH: Final[str] = "half-reach"
TANH_SLOPES_EQUAL: Final[str] = "equal-slope"

#: Shapes that architect decision C3 defers to the second commit, before M2.
_SECOND_COMMIT_SHAPES: Final[tuple[str, ...]] = (
    "TriangularMF",
    "TrapezoidalMF",
    "TanhBellMF",
)

_HALF_MAX_SIGMA: Final[float] = math.sqrt(2.0 * math.log(2.0))
_EDGE_ATANH: Final[float] = math.atanh(EDGE_TANH_VALUE)


@dataclass(frozen=True)
class QuantileLayout:
    """The bin geometry every shape's parameters are derived from.

    One layout per feature. ``edges`` has ``k + 1`` entries (``e_0..e_k``);
    ``centers``, ``reaches`` and ``margins`` have ``k`` (``j = 1..k``).
    ``lo == edges[0]`` and ``hi == edges[-1]`` for every placement.
    """

    lo: float
    hi: float
    edges: npt.NDArray[np.float64]
    centers: npt.NDArray[np.float64]
    reaches: npt.NDArray[np.float64]
    margins: npt.NDArray[np.float64]
    #: The literal ``(lo, hi)`` the caller passed under a legacy placement, which
    #: is *not* ``(self.lo, self.hi)`` for ``endpoint``: there the outer centers
    #: sit on the range ends, so the bin edges extend half a spacing beyond them.
    #: ``None`` for the quantile placement, where the range is the p1/p99 edges.
    source_range: tuple[float, float] | None = None

    @property
    def k(self) -> int:
        """Number of levels in this layout."""
        return int(self.centers.shape[0])


def _validate_placement(placement: str) -> None:
    if placement not in PLACEMENTS:
        raise ValueError(f"unknown placement {placement!r}; known: {list(PLACEMENTS)}")


def _legacy_layout(samples: npt.NDArray[np.float64], k: int, placement: str) -> QuantileLayout:
    """The two Issue #31 layouts, reproducing ``first_ensemble_run.mf_centers``.

    ``samples`` is the literal ``(lo, hi)`` range, not a distribution (FR-5).
    Centers are equally spaced; the bin edges are their midpoints, extended by
    half a spacing at each end, so ``r_j`` is the same half-spacing everywhere.
    """
    if samples.shape != (2,):
        raise ValueError(
            f"placement={placement!r} takes samples as a 2-vector (lo, hi); "
            f"got shape {samples.shape}"
        )
    lo, hi = float(samples[0]), float(samples[1])
    if not lo < hi:
        raise ValueError(f"placement={placement!r} requires lo < hi; got lo={lo}, hi={hi}")

    span = hi - lo
    j = np.arange(1, k + 1, dtype=np.float64)
    if placement == PLACEMENT_ENDPOINT:
        centers = lo + span * ((j - 1.0) / (k - 1.0))
        spacing = span / (k - 1.0)
    else:
        centers = lo + span * ((2.0 * j - 1.0) / (2.0 * k))
        spacing = span / k

    half = spacing / 2.0
    edges = np.concatenate(
        ([centers[0] - half], (centers[:-1] + centers[1:]) / 2.0, [centers[-1] + half])
    )
    reaches = np.full(k, half, dtype=np.float64)
    return QuantileLayout(
        lo=float(edges[0]),
        hi=float(edges[-1]),
        edges=edges,
        centers=centers,
        reaches=reaches,
        margins=MARGIN_FRACTION * reaches,
        source_range=(lo, hi),
    )


def _quantile_layout(samples: npt.NDArray[np.float64], k: int, placement: str) -> QuantileLayout:
    """Bin edges, centers, reaches and margins for one feature.

    For ``placement="quantile"`` (the data-driven layout) the edges are the
    ``k + 1`` equally-spaced quantiles of ``samples`` across ``[p1, p99]`` and
    the centers are the bin-mid quantiles, so every bin holds the same
    probability mass. For the two legacy placements see :func:`_legacy_layout`.

    Raises ``ValueError`` on any degenerate layout rather than adjusting it
    (NFR-5): ``k < 2``, non-1-D or non-finite samples, tied edges, or a
    non-positive reach.
    """
    _validate_placement(placement)
    if k < 2:
        raise ValueError(f"Number of partitions (k) must be at least 2, got {k}")
    if samples.ndim != 1:
        raise ValueError(f"Samples must be a 1-dimensional array, got {samples.ndim}D")
    if not np.all(np.isfinite(samples)):
        raise ValueError("Samples array must contain only finite numbers")

    if placement != PLACEMENT_QUANTILE:
        layout = _legacy_layout(samples, k, placement)
    else:
        span = DOMAIN_HI_QUANTILE - DOMAIN_LO_QUANTILE
        j_edges = np.arange(k + 1, dtype=np.float64)
        edges = np.asarray(
            np.quantile(samples, DOMAIN_LO_QUANTILE + span * j_edges / k, method=QUANTILE_METHOD),
            dtype=np.float64,
        )
        j_centers = np.arange(1, k + 1, dtype=np.float64)
        centers = np.asarray(
            np.quantile(
                samples,
                DOMAIN_LO_QUANTILE + span * (j_centers - 0.5) / k,
                method=QUANTILE_METHOD,
            ),
            dtype=np.float64,
        )
        reaches = np.maximum(centers - edges[:-1], edges[1:] - centers)
        layout = QuantileLayout(
            lo=float(edges[0]),
            hi=float(edges[-1]),
            edges=edges,
            centers=centers,
            reaches=reaches,
            margins=MARGIN_FRACTION * reaches,
        )

    if not np.all(np.diff(layout.edges) > 0):
        raise ValueError("Tied bin edges; the sample distribution is too degenerate to partition.")
    if not np.all(np.diff(layout.centers) > 0):
        raise ValueError("Bin centers are not strictly increasing.")
    if not np.all(layout.reaches > 0):
        raise ValueError("Every bin reach r_j must be strictly positive.")
    return layout


def partition_anchors(
    samples: npt.NDArray[np.float64], k: int = 3, *, placement: str = PLACEMENT_QUANTILE
) -> npt.NDArray[np.float64]:
    """Return the ``k`` anchor points ``c_1..c_k`` of one feature (FR-6).

    The anchor is a property of the layout, not of the shape, which is why this
    takes no ``shape`` argument: it consumes the identical :func:`_quantile_layout`
    output :func:`grid_partition` consumes for the same ``samples``, ``k`` and
    ``placement``, so no two callers can ever see two different layouts for one
    feature. For the peaked shapes the anchors coincide with the MF centers;
    for ``TanhSigmoidMF`` they deliberately do not (its centers are the bin
    edges, its anchor stays the bin midpoint).

    Strictly increasing. Raises ``ValueError`` on a degenerate layout.
    """
    return _quantile_layout(np.asarray(samples, dtype=np.float64), k, placement).centers


def _onsets_for_layout(layout: QuantileLayout) -> npt.NDArray[np.float64]:
    """ADR-023 onsets for an already-computed layout. See :func:`tanh_floor_onsets`."""
    u = layout.centers - layout.edges[:-1]
    v = layout.edges[1:] - layout.centers
    skewed = v != u
    onsets = np.full(layout.k, np.inf, dtype=np.float64)
    onsets[skewed] = layout.centers[skewed] - 2.5 * u[skewed] * v[skewed] / (v[skewed] - u[skewed])
    return onsets


def _strategy_for_layout(layout: QuantileLayout) -> str:
    """Slope strategy for an already-computed layout. See :func:`tanh_slope_strategy`."""
    onsets = _onsets_for_layout(layout)
    inside = (onsets >= layout.lo) & (onsets <= layout.hi)
    return TANH_SLOPES_EQUAL if bool(np.any(inside)) else TANH_SLOPES_HALF_REACH


def tanh_floor_onsets(
    samples: npt.NDArray[np.float64], k: int = 3, *, placement: str = PLACEMENT_QUANTILE
) -> npt.NDArray[np.float64]:
    """ADR-023's negative-tail onset ``x*_j`` for the half-reach ``TanhMF`` map.

    With unequal slopes the raw tanh difference goes negative beyond
    ``x* = (s_L L - s_R R) / (s_L - s_R)`` and ``TanhMF``'s floor binds, giving
    a zero-gradient tail. Substituting section 6.3's half-reach mapping and
    cancelling ``atanh(0.8)`` leaves the closed form::

        x*_j = c_j - 2.5 * u_j * v_j / (v_j - u_j),
        u_j = c_j - e_(j-1),   v_j = e_j - c_j

    Returns ``+inf`` for a level whose half-reaches are equal, where the slopes
    coincide and no floored tail exists. Measured, never assumed: on a
    right-skewed feature an onset can land inside ``[lo, hi]``.
    """
    return _onsets_for_layout(_quantile_layout(np.asarray(samples, dtype=np.float64), k, placement))


def tanh_slope_strategy(
    samples: npt.NDArray[np.float64], k: int = 3, *, placement: str = PLACEMENT_QUANTILE
) -> str:
    """Which ``TanhMF`` slope mapping this feature gets (section 7 decision 2).

    ``TANH_SLOPES_HALF_REACH`` is the default. If any level's
    :func:`tanh_floor_onsets` value lies inside the domain box, that feature
    falls back to ``TANH_SLOPES_EQUAL``, which coincides exactly with
    ``TanhBellMF``'s mapping -- so the two shapes' untrained ablation rows are
    identical for that feature and the results caption must say so.
    """
    return _strategy_for_layout(
        _quantile_layout(np.asarray(samples, dtype=np.float64), k, placement)
    )


def _gaussian_sigmas(layout: QuantileLayout, placement: str) -> npt.NDArray[np.float64]:
    """Gaussian widths: half-max on the bin's wider edge, or the shipped legacy width.

    ``sigma = r_j / sqrt(2 ln 2)`` puts ``mu(c_j +- r_j)`` at exactly 0.5, which
    is the bin-cover rule. Under the two legacy placements FR-5 pins instead the
    width ``first_ensemble_run._default_mfs_for_feature`` ships, so Issue #31's
    comparison can be reproduced by equality; that width is wider than the
    bin-cover minimum, so coverage still holds.
    """
    if placement == PLACEMENT_QUANTILE or layout.source_range is None:
        return layout.reaches / _HALF_MAX_SIGMA
    lo, hi = layout.source_range
    return np.full(layout.k, 0.25 * (hi - lo), dtype=np.float64)


def _gaussian_partition(
    layout: QuantileLayout, placement: str, qubit_spread: float | None
) -> list[MembershipFunction]:
    del qubit_spread
    sigmas = _gaussian_sigmas(layout, placement)
    return [GaussianMF(float(layout.centers[j]), float(sigmas[j])) for j in range(layout.k)]


def _interval_gaussian_partition(
    layout: QuantileLayout, placement: str, qubit_spread: float | None
) -> list[MembershipFunction]:
    if qubit_spread is None or not math.isfinite(qubit_spread) or qubit_spread <= 0:
        raise ValueError(
            "IntervalGaussianMF requires a finite, strictly positive qubit_spread; "
            f"got {qubit_spread!r}"
        )
    sigmas_low = _gaussian_sigmas(layout, placement)
    mfs: list[MembershipFunction] = []
    for j in range(layout.k):
        sigma_low = float(sigmas_low[j])
        # Convolving the lower Gaussian with the device's own per-qubit scatter
        # adds variances; strictly wider, so `sigma_low < sigma_high` holds.
        sigma_high = math.sqrt(sigma_low**2 + qubit_spread**2)
        mfs.append(IntervalGaussianMF(float(layout.centers[j]), sigma_low, sigma_high))
    return mfs


def _tanh_sigmoid_partition(
    layout: QuantileLayout, placement: str, qubit_spread: float | None
) -> list[MembershipFunction]:
    del placement, qubit_spread
    # Cumulative levels: MF j reads "at least level j" and crosses 0.5 at the
    # bin's lower edge. One common slope, because two rising sigmoids with
    # different slopes cross inside the range and the ordering invariant
    # mu_1 >= mu_2 >= ... >= mu_k would fail (section 7 decision 1).
    slope = _EDGE_ATANH / float(np.min(layout.margins))
    mfs: list[MembershipFunction] = []
    for j in range(layout.k):
        # Level 1 has no lower bin edge to sit on, so its center is offset one
        # margin below `lo`; mu_1(lo) is therefore near 1, not 0.5, by design.
        center = layout.lo - float(layout.margins[0]) if j == 0 else float(layout.edges[j])
        mfs.append(TanhSigmoidMF(center, slope))
    return mfs


def _tanh_partition(
    layout: QuantileLayout, placement: str, qubit_spread: float | None
) -> list[MembershipFunction]:
    del placement, qubit_spread
    strategy = _strategy_for_layout(layout)
    mfs: list[MembershipFunction] = []
    for j in range(layout.k):
        c = float(layout.centers[j])
        r = float(layout.reaches[j])
        m = float(layout.margins[j])
        if strategy == TANH_SLOPES_EQUAL:
            # Decision 2's fallback: the TanhBellMF mapping, whose degree
            # formula is TanhMF's with slope_left == slope_right and the floor
            # inactive, so the two shapes coincide exactly for this feature.
            left, right = c - r - m, c + r + m
            slope_left = slope_right = _EDGE_ATANH / m
        else:
            # Half-reach slopes: a skewed bin gets unequal slopes, which is the
            # one thing that distinguishes TanhMF from TanhBellMF.
            m_left = (c - float(layout.edges[j])) * MARGIN_FRACTION
            m_right = (float(layout.edges[j + 1]) - c) * MARGIN_FRACTION
            left = float(layout.edges[j]) - m_left
            right = float(layout.edges[j + 1]) + m_right
            slope_left = _EDGE_ATANH / m_left
            slope_right = _EDGE_ATANH / m_right
        mfs.append(TanhMF(left, right, slope_left, slope_right))
    return mfs


_ShapeBuilder = Callable[[QuantileLayout, str, float | None], list[MembershipFunction]]

#: The M1 shapes of architect decision C3's first commit. A shape absent from
#: this table raises ``NotImplementedError`` rather than receiving a silently
#: wrong partition (FR-5).
_SHAPE_BUILDERS: Final[dict[type[MembershipFunction], _ShapeBuilder]] = {
    GaussianMF: _gaussian_partition,
    IntervalGaussianMF: _interval_gaussian_partition,
    TanhSigmoidMF: _tanh_sigmoid_partition,
    TanhMF: _tanh_partition,
}


def grid_partition(
    shape: type[MembershipFunction],
    samples: npt.NDArray[np.float64],
    k: int = 3,
    *,
    placement: str = PLACEMENT_QUANTILE,
    qubit_spread: float | None = None,
) -> list[MembershipFunction]:
    """Build ``k`` membership functions of one shape covering one feature (FR-5).

    ``samples`` is the feature's snapshot values for ``placement="quantile"``,
    or the literal ``(lo, hi)`` 2-vector for the two legacy Issue #31 layouts.
    ``qubit_spread`` is required for ``IntervalGaussianMF`` (it sizes the
    footprint of uncertainty) and rejected for every T1 shape.

    Returns ``k`` fresh MF objects, ascending by anchor, each satisfying its own
    validation and the bin-cover rule (``max_j mu_j(x).low >= 0.5`` across
    ``[e_0, e_k]``; ``TanhSigmoidMF`` satisfies the ordering invariant instead).
    Deterministic: no RNG anywhere.

    Raises ``ValueError`` on a degenerate layout or a misused ``qubit_spread``,
    and ``NotImplementedError`` for a shape whose commit has not landed.
    """
    if shape is not IntervalGaussianMF and qubit_spread is not None:
        raise ValueError(f"qubit_spread is not supported for T1 shape {shape.__name__}.")

    builder = _SHAPE_BUILDERS.get(shape)
    if builder is None:
        if shape.__name__ in _SECOND_COMMIT_SHAPES:
            raise NotImplementedError(
                f"{shape.__name__} lands in the second commit before M2 (architect "
                f"decision C3, FR-5); the M1 commit ships "
                f"{', '.join(s.__name__ for s in _SHAPE_BUILDERS)}."
            )
        raise NotImplementedError(
            f"No grid_partition mapping for {shape.__name__}; the shipped shapes are "
            f"{', '.join(s.__name__ for s in _SHAPE_BUILDERS)} and "
            f"{', '.join(_SECOND_COMMIT_SHAPES)}."
        )

    layout = _quantile_layout(np.asarray(samples, dtype=np.float64), k, placement)
    return builder(layout, placement, qubit_spread)


def anchored_rule_base(
    per_input_mfs: Sequence[Sequence[MembershipFunction]],
    target_fn: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
    *,
    anchors: Sequence[npt.NDArray[np.float64]],
) -> TSKRuleBase:
    """Build the ``prod_i k_i``-rule TSK base whose consequents are anchored (FR-7).

    Every rule gets a zero-order consequent ``A_r = [0 | b_r]`` whose bias is
    ``target_fn`` evaluated at that rule's anchor vector, so the defuzzified
    output is a convex combination of physics targets and cannot be the identity
    channel wherever a rule fires (section 6.5). Nothing is drawn, so no seed
    appears and ADR-024's 1/4 degeneracy rate does not apply.

    ``anchors`` is keyword-only and required so no caller can silently receive a
    default layout: pass :func:`partition_anchors` on the same ``samples``,
    ``k`` and ``placement`` used for :func:`grid_partition` (FR-6).

    Rules are built over ``itertools.product`` -- the order ``TSKRuleBase.from_grid``
    uses -- referencing the caller's MF objects rather than copies, so a 3x3x3
    grid has 27 rules over 9 unique objects and the trainer's per-object
    parameter count stays 18 rather than 162 (NFR-7). Each rule gets a freshly
    allocated consequent array, because ``TSKRule`` aliases the array it is given.

    Raises ``ValueError`` on a length mismatch, a non-finite target (a NaN bias
    would install maximal damping while passing every viability check, NFR-5),
    or an inconsistent ``output_dim``.
    """
    input_dim = len(per_input_mfs)
    if input_dim == 0:
        raise ValueError("anchored_rule_base requires at least one input.")
    if len(anchors) != input_dim:
        raise ValueError(f"Expected {input_dim} anchor arrays, got {len(anchors)}")
    for i in range(input_dim):
        if len(anchors[i]) != len(per_input_mfs[i]):
            raise ValueError(
                f"Input {i}: length of anchors ({len(anchors[i])}) "
                f"must match length of MFs ({len(per_input_mfs[i])})."
            )

    combinations = list(
        zip(itertools.product(*per_input_mfs), itertools.product(*anchors), strict=True)
    )
    if not combinations:
        raise ValueError("anchored_rule_base requires at least one MF per input.")

    rules: list[TSKRule] = []
    output_dim: int | None = None
    for mf_tuple, anchor_tuple in combinations:
        x_r = np.array(anchor_tuple, dtype=np.float64)
        y_target = np.asarray(target_fn(x_r), dtype=np.float64)
        if y_target.ndim != 1:
            raise ValueError(
                f"target_fn must return a 1-D vector; got shape {y_target.shape} at anchor {x_r}"
            )
        if not np.all(np.isfinite(y_target)):
            raise ValueError(f"Target function returned non-finite values for anchor {x_r}")
        if output_dim is None:
            output_dim = int(y_target.shape[0])
        elif int(y_target.shape[0]) != output_dim:
            raise ValueError(
                f"Inconsistent output_dim. Expected {output_dim}, got {y_target.shape[0]}"
            )

        consequent = np.zeros((output_dim, input_dim + 1), dtype=np.float64)
        consequent[:, -1] = y_target
        rules.append(TSKRule(antecedent_mfs=list(mf_tuple), consequent_params=consequent))

    return TSKRuleBase(rules=rules, input_dim=input_dim, output_dim=int(output_dim or 0))


class ClampingFeatureExtractor(CalibrationFeatureExtractor):
    """Wrap an extractor so out-of-domain feature vectors are clamped, not fatal (FR-12).

    The partition is defined on the domain box ``[lo, hi]`` per feature, and
    outside it the model has no stated behaviour. Two of the seven shapes have
    compact support: beyond every level's foot all ``k`` memberships are exactly
    zero, the rule firing strengths multiply to zero across the three inputs,
    and ``WeightedAverageDefuzzifier`` raises ``ZeroDivisionError``. Clamping the
    input onto the boundary is the honest fix -- widening the feet instead would
    silently change the partition the ablation is comparing and make the widths a
    function of the archive's outliers.

    This lives here rather than in a caller because
    ``FuzzyNoiseModel._compute_crisp_params`` extracts and evaluates back to
    back with no interception point between them, and ``feature_extractor`` is a
    constructor argument of both ``FuzzyNoiseModel`` and
    ``FuzzyNoiseModelEnsemble``. Injecting this wrapper is the only way a caller
    that builds an ensemble can apply the policy at all.

    Two things the counters cannot do, which the caller must handle:

    * They count **calls**. ``FuzzyNoiseModelEnsemble`` builds one
      ``FuzzyNoiseModel`` per member from the same snapshot, so an ensemble of
      32 members over one snapshot records 32 extractions of one vector. A clamp
      *rate* over distinct snapshots must divide by the ensemble size, or
      extract once outside the ensemble.
    * They are cumulative over the wrapper's lifetime, so a runner that wants a
      per-shape clamp count builds a fresh wrapper per shape.

    Composition note: ``OffsetFeatureExtractor`` (#64) has the same wrapper
    shape; if both are ever used together the clamp must be the **outer** one,
    or a perturbation can push a clamped vector back out of the box.
    """

    def __init__(
        self,
        inner: CalibrationFeatureExtractor,
        lo: npt.NDArray[np.float64],
        hi: npt.NDArray[np.float64],
    ) -> None:
        """Hold ``inner``'s domain box.

        ``lo`` and ``hi`` must each be 1-D, finite, of length ``inner.output_dim``,
        and componentwise ``lo < hi``; anything else is a ``ValueError`` (NFR-5).
        """
        self._inner = inner
        self._lo = np.asarray(lo, dtype=np.float64)
        self._hi = np.asarray(hi, dtype=np.float64)

        if self._lo.ndim != 1 or self._hi.ndim != 1:
            raise ValueError("Bounds must be 1-dimensional arrays.")
        if self._lo.shape[0] != inner.output_dim or self._hi.shape[0] != inner.output_dim:
            raise ValueError(
                f"Bounds must have length inner.output_dim ({inner.output_dim}); "
                f"got lo={self._lo.shape[0]}, hi={self._hi.shape[0]}."
            )
        if not np.all(np.isfinite(self._lo)) or not np.all(np.isfinite(self._hi)):
            raise ValueError("Bounds must contain only finite numbers.")
        if not np.all(self._lo < self._hi):
            raise ValueError("Lower bounds (lo) must be strictly less than upper bounds (hi).")

        self._n_extractions = 0
        self._n_clamped_vectors = 0
        self._n_clamped_components = np.zeros(inner.output_dim, dtype=np.int64)

    @property
    def output_dim(self) -> int:
        """Length of the extracted feature vector; the wrapped extractor's, unchanged."""
        return self._inner.output_dim

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Feature names in vector order; the wrapped extractor's, unchanged."""
        return self._inner.feature_names

    @property
    def n_extractions(self) -> int:
        """How many times :meth:`extract` has been called."""
        return self._n_extractions

    @property
    def n_clamped_vectors(self) -> int:
        """How many of those calls moved at least one component onto the boundary."""
        return self._n_clamped_vectors

    @property
    def n_clamped_components(self) -> npt.NDArray[np.int64]:
        """Per-feature clamp counts, shape ``(output_dim,)``. A copy; safe to keep."""
        return self._n_clamped_components.copy()

    @property
    def domain_box(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """The ``(lo, hi)`` box this wrapper clamps onto. Copies; safe to keep."""
        return self._lo.copy(), self._hi.copy()

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        """Return ``inner.extract(snapshot)`` clamped onto ``[lo, hi]``, and count it.

        A fresh array: never the one ``inner`` returned, and ``inner`` and the
        snapshot are not mutated.
        """
        raw = self._inner.extract(snapshot)
        out_of_bounds = (raw < self._lo) | (raw > self._hi)

        self._n_extractions += 1
        if bool(np.any(out_of_bounds)):
            self._n_clamped_vectors += 1
        self._n_clamped_components += out_of_bounds.astype(np.int64)

        return np.clip(raw, self._lo, self._hi)
