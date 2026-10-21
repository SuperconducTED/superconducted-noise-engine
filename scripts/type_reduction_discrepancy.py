"""Karnik-Mendel reference type reducer for Issue #61 Part A (FR-1, FR-2).

Everything here works on one output dimension of one interval type-2 TSK
evaluation: per-rule firing bounds ``lower`` and ``upper`` (``0 <= lower <=
upper``) and crisp consequent values ``values``. The type-reduced set is the
interval ``[y_l, y_r]`` of every weighted average

    Y(w) = sum_r w_r values_r / sum_r w_r,   w_r free in [lower_r, upper_r],

and its midpoint ``(y_l + y_r) / 2`` is what the two closed-form reducers are
measured against.

The module lives in ``scripts/`` and never in ``src/``: ADR-011's "no iterative
numerical defuzzification at bootstrap" stands, and this is a reference that
judges the shipped reducer, not a replacement for it. The FR-3 sweep that uses it
is at the end of the module (see "The sweep" below).

Two independent routes to the endpoints
---------------------------------------

Sort the rules by ``values`` ascending (a stable sort). For the left endpoint, a
*switch vertex* ``w(l, k)`` puts ``upper`` on the first ``k`` sorted rules and
``lower`` on the rest; ``w(r, k)`` is the mirror image. Then, exactly,

    y_l = min over k = 0..R of Y(w(l, k)),   y_r = max over k = 0..R of Y(w(r, k)).

Why: let ``y* = y_l``. ``Y(w) >= y*`` holds exactly when the linear function
``g(w) = sum_r w_r (values_r - y*)`` is non-negative, so ``min g = 0`` over the
box. ``g`` is minimised by the upper bound where ``values_r < y*`` and the lower
bound where ``values_r > y*``, which is a switch vertex, so that vertex attains
``y*``. The sources opened for #61 (Karnik & Mendel 2001, section 3.1; Wu & Mendel
2009) state the one-switch sign rule but not this minimum over switch points, so
it is derived here and in the #61 Part A findings. :func:`exhaustive_type_reduce`
evaluates it directly: ``R + 1`` weighted averages per endpoint.

:func:`karnik_mendel_type_reduce` is the iterative route (#61 section 6.3). From
``y`` it takes ``k = #{r : values_r <= y}``, evaluates the switch vertex, and
repeats. In exact arithmetic each step moves ``y`` monotonically towards the
endpoint and stops at it (``y' = y``, Karnik & Mendel 2001, step 4; equivalently
``k' = k``, Wu & Mendel 2009, EKM step 4).

The stop rule, and why it has a guard
-------------------------------------

Neither exact-arithmetic stop terminates reliably in float64. When firing is
concentrated on rules sharing (or nearly sharing) one consequent value, every
computed average rounds to that value or to one ulp beside it, ``k`` flips back
and forth, and the iteration cycles. The smallest case found has two rules and
two distinct values; ``tests/test_type_reduction.py`` pins it. So the iteration
here stops on whichever comes first:

1. ``k`` unchanged (the switch point, not float equality);
2. a step that fails to strictly improve ``y`` (the monotone guard). The better
   of the two values is returned.

Both are #61 owner decisions of 2026-10-21, recorded in
``docs/implementations/2026-10-21-type-reduction-reference.md``.

With the guard, accepted steps strictly improve ``y``, so ``k`` moves strictly
in one direction between evaluations (``k`` is a monotone function of ``y``),
and an endpoint takes at most ``R + 1`` evaluations. The FR-1 cap of
``R + 1`` passes therefore cannot be hit; it still raises ``RuntimeError``
rather than looping, in case that argument is ever broken by an edit. A guarded
stop can land within rounding of the endpoint rather than on the exact
minimiser; :func:`exhaustive_type_reduce` is the check on that.

The two closed-form reducers
----------------------------

- :func:`bmm_half_reduce` is the Biglarbegian-Melek-Mendel reducer with
  ``alpha = beta = 1/2``, ``(Y(lower) + Y(upper)) / 2``. It is what
  ``superconducted.fuzzy.defuzzification.NieTanDefuzzifier`` computes today.
- :func:`nie_tan_reduce` is textbook Nie-Tan, ``Y(lower + upper)`` (Wu & Mendel
  2019, Eq. 10). It is what ``WeightedAverageDefuzzifier`` computes on an IT2
  firing result, because ``TSKRuleBase.evaluate`` stores the midpoint firing.

Both lie in ``[y_l, y_r]``: ``lower``, ``upper`` and ``lower + upper`` (scaled)
are points of the box, and BMM averages two values that lie in the interval.

Contract shared by every public function
----------------------------------------

Inputs are 1-D, equal-length, finite arrays with at least one rule and
``0 <= lower <= upper`` elementwise; anything else raises ``ValueError``. A zero
``lower.sum()`` or ``upper.sum()`` raises ``ZeroDivisionError``, mirroring
``NieTanDefuzzifier.defuzzify``. The lower guard is load-bearing: every switch
vertex dominates ``lower`` elementwise, so ``lower.sum() > 0`` is exactly what
makes every evaluated average well defined. Every function is pure, allocates its
own arrays, and never returns NaN or inf for valid input.

The sweep (FR-3, FR-4)
----------------------

Usage::

    python -m scripts.type_reduction_discrepancy \\
        --range-source survey:docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv \\
        --footprint 0.1 --footprint 0.3 --footprint 0.6 --footprint g59 \\
        --points 2000 --seed 84 --out <tsv> [--point-sets lattice,uniform,survey]

Units are the archive's own throughout: ``mean_T1`` and ``mean_T2`` in
microseconds, ``mean_readout_error`` dimensionless. These are the survey's units
and ``ArchiveUnitFeatureExtractor``'s, not ``BasicCalibrationVectorizer``'s, which
has emitted SI seconds since Issue #66. The grids, the anchors, the box and every
point share them.

- **Range source.** ``survey:<tsv>`` is the only one implemented: the
  feature-distribution survey supplies the samples the grids are partitioned
  from, the domain box ``[p1, p99]`` (the quantiles ``fuzzy.parameterization``
  uses), and the per-qubit spreads. #61's ``fixture-box`` was a stand-in for
  before that survey existed, and it supplies none of the three; it raises
  ``NotImplementedError``. Anything else raises ``ValueError``.
- **Grids**, one per ``--footprint``. A ratio ``w`` in ``(0, 1)`` builds
  ``IntervalGaussianMF(c, s (1 - w), s (1 + w))`` on the centres and widths of
  ``grid_partition(GaussianMF, ..., k=3)`` (#61 section 6.2's fallback geometry).
  ``g59`` builds ``grid_partition(IntervalGaussianMF, ..., k=3,
  qubit_spread=s_i)`` with ``s_i`` the median of the survey's
  ``<feature>_qubit_std`` column, NC-042's statistic. That choice of ``s_i`` is
  an **assumption**: #84 File 02 called this grid "#59's shipped footprint"
  without stating its ``qubit_spread``, and no production caller passes one.
  The grid is labelled ``G59-assumed`` and the TSV header says so until it is
  confirmed.
- **Consequent conventions** (FR-4). ``unit-spread``: zero-order, rule ``r``
  gets bias ``r / (R - 1)``, one output. ``anchored``: ``anchored_rule_base``
  with ``feature_target_fn`` at the quantile anchors, ``t_seconds = 24e-9``
  (NC-035's ``sx`` length), outputs ``gamma`` and ``lambda`` per ``sx`` gate.
- **Point sets.** ``lattice``: the 27 anchor triples. ``uniform``: ``--points``
  draws in the box from ``numpy.random.default_rng(seed)``. ``survey``: the
  survey rows themselves, which is where the archive sits (on the ``3d1569d``
  survey, 44 of 975 lie outside the ``[p1, p99]`` box in at least one feature).
  ``pooled``: all requested sets together.
- **Distances.** ``D = |y - (y_l + y_r) / 2|`` with the Karnik-Mendel endpoints;
  ``Dc = D / (max c - min c)`` (#61 FR-3); ``Db = D / (y_r - y_l)`` (#84 File 02's
  pre-registered score), set to 0 and counted where the band width is within
  rounding (``64 R eps max|c|``) and capped at ``1/2`` elsewhere, so a reducer
  within rounding outside a narrow band cannot score above it.

The output TSV starts with ``# key: value`` lines (commit, range source, units,
box, grids, the ``s_i`` assumption, conventions, point sets, seed, reducers and
distance definitions), then one header row and one row per (grid, convention,
output, point set, reducer). Floats are written with ``repr``, and nothing
time-dependent is written, so two runs with the same arguments on the same
machine and commit give byte-identical files (NFR-1). Wall-clock time goes to
stderr.
"""

import argparse
import csv
import itertools
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt

from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF
from superconducted.fuzzy.parameterization import (
    DOMAIN_HI_QUANTILE,
    DOMAIN_LO_QUANTILE,
    QUANTILE_METHOD,
    anchored_rule_base,
    grid_partition,
    partition_anchors,
)
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.interfaces import MembershipFunction
from superconducted.training.targets import feature_target_fn

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class KarnikMendelResult:
    """Endpoints of the type-reduced interval with the iteration's diagnostics.

    ``passes_l`` and ``passes_r`` count switch-vertex evaluations per endpoint
    (the midpoint start is not counted); each is at most ``n_rules + 1``.
    ``guard_stops`` counts the endpoints (0, 1 or 2) whose iteration ended
    because a step moved ``y`` the wrong way, which can only happen through
    rounding.
    """

    y_l: float
    y_r: float
    passes_l: int
    passes_r: int
    guard_stops: int


def _validated(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Return float64 copies of the inputs after checking the shared contract."""
    lo = np.array(lower, dtype=np.float64)
    hi = np.array(upper, dtype=np.float64)
    c = np.array(values, dtype=np.float64)
    if lo.ndim != 1 or hi.ndim != 1 or c.ndim != 1:
        raise ValueError(
            f"lower, upper and values must be 1-D; got shapes {lo.shape}, {hi.shape}, {c.shape}"
        )
    if not lo.shape == hi.shape == c.shape:
        raise ValueError(
            f"lower, upper and values must have equal length; got {lo.size}, {hi.size}, {c.size}"
        )
    if lo.size == 0:
        raise ValueError("at least one rule is required")
    if not (np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)) and np.all(np.isfinite(c))):
        raise ValueError("lower, upper and values must be finite")
    if np.any(lo < 0.0):
        raise ValueError("lower firing bounds must be non-negative")
    if np.any(lo > hi):
        raise ValueError("lower firing bounds must not exceed upper firing bounds")
    sum_low = float(lo.sum())
    sum_high = float(hi.sum())
    if sum_low == 0.0 or sum_high == 0.0:
        raise ZeroDivisionError(
            f"type reduction received a zero firing-strength sum (lower={sum_low}, "
            f"upper={sum_high})"
        )
    return lo, hi, c


def _sorted_by_value(
    lower: FloatArray, upper: FloatArray, values: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Reorder all three arrays so ``values`` ascends; stable, so ties keep rule order."""
    order = np.argsort(values, kind="stable")
    return lower[order], upper[order], values[order]


def _weighted_average(weights: FloatArray, values: FloatArray) -> float:
    """``sum w c / sum w``; every caller guarantees ``sum w > 0``."""
    return float(weights @ values) / float(weights.sum())


def _switch_vertex(
    lower: FloatArray, upper: FloatArray, k: int, side: Literal["left", "right"]
) -> FloatArray:
    """The switch vertex for sorted rules: the first ``k`` get one bound, the rest the other."""
    if side == "left":
        return np.concatenate((upper[:k], lower[k:]))
    return np.concatenate((lower[:k], upper[k:]))


def _km_endpoint(
    lower: FloatArray,
    upper: FloatArray,
    values: FloatArray,
    side: Literal["left", "right"],
    *,
    guard: bool = True,
) -> tuple[float, int, bool]:
    """Iterate to one endpoint on rules already sorted by ``values``.

    Returns ``(y, passes, guard_stopped)``. ``guard=False`` exists only so the
    tests can show that the switch-point stop alone cycles (a mutation check); no
    production path passes it.
    """
    n_rules = int(values.size)
    y = _weighted_average(0.5 * (lower + upper), values)
    k_prev: int | None = None
    passes = 0
    while True:
        k = int(np.searchsorted(values, y, side="right"))
        if k == k_prev:
            return y, passes, False
        if passes == n_rules + 1:
            raise RuntimeError(
                f"Karnik-Mendel {side} endpoint did not stop within {n_rules + 1} passes"
            )
        y_next = _weighted_average(_switch_vertex(lower, upper, k, side), values)
        passes += 1
        if guard:
            if side == "left" and y_next >= y:
                return y, passes, y_next > y
            if side == "right" and y_next <= y:
                return y, passes, y_next < y
        y, k_prev = y_next, k


def karnik_mendel_detailed(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> KarnikMendelResult:
    """Iterative Karnik-Mendel endpoints with pass counts and guard stops.

    Inputs follow the module contract. Output satisfies ``y_l <= y_r`` up to
    rounding and agrees with :func:`exhaustive_type_reduce` to rounding. Pure.
    """
    lo, hi, c = _sorted_by_value(*_validated(lower, upper, values))
    y_l, passes_l, guard_l = _km_endpoint(lo, hi, c, "left")
    y_r, passes_r, guard_r = _km_endpoint(lo, hi, c, "right")
    return KarnikMendelResult(
        y_l=y_l,
        y_r=y_r,
        passes_l=passes_l,
        passes_r=passes_r,
        guard_stops=int(guard_l) + int(guard_r),
    )


def karnik_mendel_type_reduce(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[float, float]:
    """Return ``(y_l, y_r)`` by the guarded iterative Karnik-Mendel method (FR-1).

    Raises ``ValueError`` or ``ZeroDivisionError`` per the module contract and
    ``RuntimeError`` if an endpoint exceeds ``n_rules + 1`` passes, which the
    monotone guard makes unreachable. Pure.
    """
    result = karnik_mendel_detailed(lower, upper, values)
    return result.y_l, result.y_r


def exhaustive_type_reduce(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[float, float]:
    """Return ``(y_l, y_r)`` by evaluating all ``n_rules + 1`` switch vertices per endpoint.

    Exact up to the rounding of each weighted average (module docstring), with
    no iteration and no stop rule, so it is the independent check on
    :func:`karnik_mendel_type_reduce`. Same contract and errors. Pure.
    """
    lo, hi, c = _sorted_by_value(*_validated(lower, upper, values))
    switch_points = range(c.size + 1)
    y_l = min(_weighted_average(_switch_vertex(lo, hi, k, "left"), c) for k in switch_points)
    y_r = max(_weighted_average(_switch_vertex(lo, hi, k, "right"), c) for k in switch_points)
    return y_l, y_r


def bmm_half_reduce(lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike) -> float:
    """BMM with ``alpha = beta = 1/2``: ``(Y(lower) + Y(upper)) / 2``.

    The formula ``NieTanDefuzzifier.defuzzify`` computes today (Wu & Mendel
    2019, Eq. 11). Linear in ``values`` for fixed firing. Same contract. Pure.
    """
    lo, hi, c = _validated(lower, upper, values)
    return 0.5 * _weighted_average(lo, c) + 0.5 * _weighted_average(hi, c)


def nie_tan_reduce(lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike) -> float:
    """Textbook Nie-Tan: ``Y(lower + upper)`` (Wu & Mendel 2019, Eq. 10).

    Equal to ``WeightedAverageDefuzzifier`` on an IT2 firing result, whose
    ``firing_strengths`` is the midpoint. Linear in ``values`` for fixed
    firing. Same contract, including the ``ZeroDivisionError`` on a zero lower
    sum, even though this formula alone would be defined there. Pure.
    """
    lo, hi, c = _validated(lower, upper, values)
    return _weighted_average(lo + hi, c)


# ---------------------------------------------------------------------------
# The sweep (FR-3, FR-4). See "The sweep" in the module docstring.
# ---------------------------------------------------------------------------

FEATURES: tuple[str, ...] = ("mean_T1", "mean_T2", "mean_readout_error")
FEATURE_UNITS: tuple[str, ...] = ("us", "us", "dimensionless")
SPREAD_COLUMNS: tuple[str, ...] = ("T1_qubit_std", "T2_qubit_std", "readout_error_qubit_std")
LEVELS_PER_FEATURE = 3
#: ``ibm_fez``'s single-qubit ``sx`` length, NC-035.
SX_GATE_SECONDS = 24e-9
G59_TOKEN = "g59"
G59_GRID_NAME = "G59-assumed"
POINT_SETS: tuple[str, ...] = ("lattice", "uniform", "survey")
POOLED = "pooled"
SURVEY_PREFIX = "survey:"
COLUMNS: tuple[str, ...] = (
    "grid",
    "convention",
    "output",
    "point_set",
    "reducer",
    "n_points",
    "n_skipped",
    "n_degenerate_band",
    "n_bracket_violations",
    "D_max",
    "D_mean",
    "D_median",
    "D_p90",
    "Dc_max",
    "Dc_mean",
    "Dc_median",
    "Dc_p90",
    "Db_max",
    "Db_mean",
    "Db_median",
    "Db_p90",
    "km_passes_max",
    "km_passes_mean",
    "km_guard_stops",
    "km_route_gap_max",
)


@dataclass(frozen=True)
class Survey:
    """Feature samples and per-qubit spread medians from the survey TSV, archive units.

    ``samples`` is ``(n_rows, 3)`` in ``FEATURES`` order; ``spread_medians`` is
    the median over rows of each ``SPREAD_COLUMNS`` entry (NC-042's statistic).
    """

    samples: FloatArray
    spread_medians: FloatArray


@dataclass(frozen=True)
class Grid:
    """One 3x3x3 interval type-2 grid: three MF levels per feature, in ``FEATURES`` order."""

    name: str
    description: str
    per_input_mfs: tuple[tuple[MembershipFunction, ...], ...]


@dataclass(frozen=True)
class Convention:
    """A consequent convention (FR-4): how to build the rule base and its output names."""

    name: str
    outputs: tuple[str, ...]
    build: Callable[[Grid, Sequence[FloatArray]], TSKRuleBase]


@dataclass(frozen=True)
class _Measurement:
    """Everything the summary needs from one (point, output) evaluation."""

    y_l: float
    y_r: float
    y_bmm: float
    y_nt: float
    spread: float
    tolerance: float
    passes_l: int
    passes_r: int
    guard_stops: int
    route_gap: float


def load_survey(path: Path) -> Survey:
    """Read the feature-distribution survey TSV (``scripts/feature_distribution.py``).

    Rows with a ``rejection_reason`` or a missing feature are dropped; a spread
    cell left empty (fewer than two usable qubits) is left out of that column's
    median. Raises ``ValueError`` on an empty table, a non-finite feature, or a
    spread column with no values. Reads only ``path``.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    usable = [
        row
        for row in rows
        if not row.get("rejection_reason") and all(row.get(feature) for feature in FEATURES)
    ]
    if not usable:
        raise ValueError(f"survey {path} has no usable rows")
    samples = np.array([[float(row[f]) for f in FEATURES] for row in usable], dtype=np.float64)
    if not np.all(np.isfinite(samples)):
        raise ValueError(f"survey {path} has a non-finite feature value")
    medians = []
    for column in SPREAD_COLUMNS:
        spreads = np.array([float(row[column]) for row in usable if row.get(column)])
        if spreads.size == 0:
            raise ValueError(f"survey {path} has no values in {column}")
        medians.append(float(np.median(spreads)))
    return Survey(samples=samples, spread_medians=np.array(medians, dtype=np.float64))


def domain_box(samples: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Per-feature ``[p1, p99]`` with ``fuzzy.parameterization``'s quantile settings."""
    lo = np.quantile(samples, DOMAIN_LO_QUANTILE, axis=0, method=QUANTILE_METHOD)
    hi = np.quantile(samples, DOMAIN_HI_QUANTILE, axis=0, method=QUANTILE_METHOD)
    return np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)


def anchor_levels(samples: FloatArray) -> tuple[FloatArray, ...]:
    """The three quantile anchors per feature, the MF centres of every grid here."""
    return tuple(partition_anchors(samples[:, i], LEVELS_PER_FEATURE) for i in range(len(FEATURES)))


def footprint_grid(samples: FloatArray, ratio: float) -> Grid:
    """``IntervalGaussianMF(c, s (1 - w), s (1 + w))`` on ``grid_partition(GaussianMF)``.

    #61 section 6.2's fallback geometry: symmetric about the T1 width ``s``.
    ``ratio`` must lie strictly inside ``(0, 1)`` (``IntervalGaussianMF`` rejects
    a zero-width footprint), else ``ValueError``.
    """
    if not 0.0 < ratio < 1.0:
        raise ValueError(f"footprint ratio must lie strictly between 0 and 1; got {ratio!r}")
    per_input: list[tuple[MembershipFunction, ...]] = []
    for i in range(len(FEATURES)):
        levels: list[MembershipFunction] = []
        for base in grid_partition(GaussianMF, samples[:, i], LEVELS_PER_FEATURE):
            centre, sigma = (float(value) for value in base.parameters())
            levels.append(IntervalGaussianMF(centre, sigma * (1.0 - ratio), sigma * (1.0 + ratio)))
        per_input.append(tuple(levels))
    return Grid(
        name=f"w={ratio!r}",
        description=(
            f"IntervalGaussianMF(c, s*(1-{ratio!r}), s*(1+{ratio!r})) on "
            "grid_partition(GaussianMF, survey, k=3, placement=quantile)"
        ),
        per_input_mfs=tuple(per_input),
    )


def g59_grid(samples: FloatArray, spreads: FloatArray) -> Grid:
    """``grid_partition(IntervalGaussianMF, qubit_spread=s_i)`` with ``s_i = spreads[i]``.

    The lower MF is the T1 bin-cover Gaussian and ``s_high = sqrt(s_low^2 +
    s_i^2)``. Which ``s_i`` #84 File 02 used is unconfirmed; see the module
    docstring.
    """
    per_input = tuple(
        tuple(
            grid_partition(
                IntervalGaussianMF,
                samples[:, i],
                LEVELS_PER_FEATURE,
                qubit_spread=float(spreads[i]),
            )
        )
        for i in range(len(FEATURES))
    )
    return Grid(
        name=G59_GRID_NAME,
        description=(
            "grid_partition(IntervalGaussianMF, survey, k=3, placement=quantile, "
            "qubit_spread=s_i), s_i ASSUMED (see g59_qubit_spread)"
        ),
        per_input_mfs=per_input,
    )


def unit_spread_rule_base(grid: Grid, anchors: Sequence[FloatArray]) -> TSKRuleBase:
    """Zero-order rules over the grid's Cartesian product; rule ``r`` has bias ``r / (R - 1)``.

    ``anchors`` is unused and accepted only so both conventions share one
    signature. Rules follow ``itertools.product`` order, as ``from_grid`` and
    ``anchored_rule_base`` do. One output.
    """
    del anchors
    combinations = list(itertools.product(*grid.per_input_mfs))
    n_rules = len(combinations)
    input_dim = len(grid.per_input_mfs)
    rules = []
    for index, mfs in enumerate(combinations):
        consequent = np.zeros((1, input_dim + 1), dtype=np.float64)
        consequent[0, -1] = index / (n_rules - 1)
        rules.append(TSKRule(antecedent_mfs=list(mfs), consequent_params=consequent))
    return TSKRuleBase(rules=rules, input_dim=input_dim, output_dim=1)


def anchored_target(anchor: FloatArray) -> FloatArray:
    """ADR-027 ``(gamma, lambda)`` per 24 ns ``sx`` gate at an anchor in archive microseconds."""
    return feature_target_fn(anchor, t_seconds=SX_GATE_SECONDS, coherence_unit="us")


def anchored_convention_rule_base(grid: Grid, anchors: Sequence[FloatArray]) -> TSKRuleBase:
    """``anchored_rule_base`` with :func:`anchored_target` at the quantile anchors."""
    return anchored_rule_base(grid.per_input_mfs, anchored_target, anchors=anchors)


CONVENTIONS: tuple[Convention, ...] = (
    Convention(name="unit-spread", outputs=("unit",), build=unit_spread_rule_base),
    Convention(name="anchored", outputs=("gamma", "lambda"), build=anchored_convention_rule_base),
)


def parse_range_source(text: str) -> Path:
    """Return the survey path from ``survey:<tsv>``.

    ``fixture-box`` raises ``NotImplementedError`` (module docstring); any
    other text raises ``ValueError``, never a default (FR-3).
    """
    if text.startswith(SURVEY_PREFIX):
        path = text[len(SURVEY_PREFIX) :]
        if not path:
            raise ValueError("--range-source survey: needs a path, e.g. survey:<survey.tsv>")
        return Path(path)
    if text == "fixture-box":
        raise NotImplementedError(
            "fixture-box was #61's stand-in for before the feature-distribution survey "
            "existed; it supplies no samples for the grid and no per-qubit spreads. "
            "Use survey:<tsv>."
        )
    raise ValueError(f"unknown --range-source {text!r}; accepted: survey:<tsv>")


def parse_footprint(text: str) -> str:
    """Canonical footprint token: ``g59`` or ``repr`` of a ratio in ``(0, 1)``."""
    if text == G59_TOKEN:
        return G59_TOKEN
    try:
        ratio = float(text)
    except ValueError:
        raise ValueError(f"--footprint must be a ratio in (0, 1) or {G59_TOKEN!r}") from None
    if not 0.0 < ratio < 1.0:
        raise ValueError(f"footprint ratio must lie strictly between 0 and 1; got {text!r}")
    return repr(ratio)


def parse_point_sets(text: str) -> tuple[str, ...]:
    """Comma-separated, non-empty, duplicate-free subset of ``POINT_SETS``, in given order."""
    names = tuple(name.strip() for name in text.split(","))
    unknown = [name for name in names if name not in POINT_SETS]
    if unknown or len(set(names)) != len(names):
        raise ValueError(f"--point-sets must be distinct names from {POINT_SETS}; got {text!r}")
    return names


def _measure(lower: FloatArray, upper: FloatArray, values: FloatArray) -> _Measurement | None:
    """Every reducer and both KM routes at one (point, output); ``None`` on a zero sum."""
    try:
        km = karnik_mendel_detailed(lower, upper, values)
        exhaustive_l, exhaustive_r = exhaustive_type_reduce(lower, upper, values)
        y_bmm = bmm_half_reduce(lower, upper, values)
        y_nt = nie_tan_reduce(lower, upper, values)
    except ZeroDivisionError:
        return None
    eps = float(np.finfo(np.float64).eps)
    return _Measurement(
        y_l=km.y_l,
        y_r=km.y_r,
        y_bmm=y_bmm,
        y_nt=y_nt,
        spread=float(values.max() - values.min()),
        tolerance=64 * values.size * eps * float(np.max(np.abs(values))),
        passes_l=km.passes_l,
        passes_r=km.passes_r,
        guard_stops=km.guard_stops,
        route_gap=max(abs(km.y_l - exhaustive_l), abs(km.y_r - exhaustive_r)),
    )


def _stats(values: FloatArray) -> list[str]:
    """Max, mean, median, p90 (linear) as ``repr`` strings; empty strings for no values."""
    if values.size == 0:
        return ["", "", "", ""]
    return [
        repr(float(values.max())),
        repr(float(values.mean())),
        repr(float(np.median(values))),
        repr(float(np.percentile(values, 90))),
    ]


def _summary_rows(
    key: tuple[str, str, str, str], measurements: Sequence[_Measurement | None]
) -> list[list[str]]:
    """One row per reducer for one (grid, convention, output, point set) cell."""
    kept = [m for m in measurements if m is not None]
    n_skipped = len(measurements) - len(kept)
    passes = np.array([p for m in kept for p in (m.passes_l, m.passes_r)], dtype=np.float64)
    km_columns = [
        str(int(passes.max())) if passes.size else "",
        repr(float(passes.mean())) if passes.size else "",
        str(sum(m.guard_stops for m in kept)),
        repr(max((m.route_gap for m in kept), default=0.0)),
    ]
    rows = []
    for reducer in ("bmm_half", "nie_tan"):
        distance, by_spread, by_band = [], [], []
        degenerate = violations = 0
        for m in kept:
            y = m.y_bmm if reducer == "bmm_half" else m.y_nt
            if y < m.y_l - m.tolerance or y > m.y_r + m.tolerance:
                violations += 1
            d = abs(y - 0.5 * (m.y_l + m.y_r))
            distance.append(d)
            by_spread.append(d / m.spread if m.spread > 0.0 else 0.0)
            width = m.y_r - m.y_l
            if width <= m.tolerance:
                degenerate += 1
                by_band.append(0.0)
            else:
                # Clipped at 1/2: a reducer within rounding outside a band barely wider
                # than the tolerance would otherwise score 1/2 + ulp/width. A real
                # excursion is still counted in n_bracket_violations.
                by_band.append(min(d / width, 0.5))
        rows.append(
            [
                *key,
                reducer,
                str(len(measurements)),
                str(n_skipped),
                str(degenerate),
                str(violations),
                *_stats(np.array(distance, dtype=np.float64)),
                *_stats(np.array(by_spread, dtype=np.float64)),
                *_stats(np.array(by_band, dtype=np.float64)),
                *km_columns,
            ]
        )
    return rows


def build_grid(token: str, survey: Survey) -> Grid:
    """The grid for one canonical ``--footprint`` token."""
    if token == G59_TOKEN:
        return g59_grid(survey.samples, survey.spread_medians)
    return footprint_grid(survey.samples, float(token))


def point_sets(
    names: Sequence[str], survey: Survey, n_points: int, seed: int
) -> dict[str, FloatArray]:
    """The requested point sets, in archive units; the uniform draw uses ``default_rng(seed)``."""
    lo, hi = domain_box(survey.samples)
    sets: dict[str, FloatArray] = {}
    for name in names:
        if name == "lattice":
            sets[name] = np.array(list(itertools.product(*anchor_levels(survey.samples))))
        elif name == "uniform":
            rng = np.random.default_rng(seed)
            sets[name] = rng.uniform(lo, hi, size=(n_points, len(FEATURES)))
        else:
            sets[name] = survey.samples.copy()
    return sets


def run_sweep(
    survey: Survey, grids: Sequence[Grid], sets: dict[str, FloatArray]
) -> list[list[str]]:
    """Measure every (grid, convention, output, point set, reducer) cell; one row each.

    ``pooled`` follows the individual sets when more than one is given and
    reuses their measurements. Pure.
    """
    anchors = anchor_levels(survey.samples)
    rows: list[list[str]] = []
    for grid in grids:
        for convention in CONVENTIONS:
            rule_base = convention.build(grid, anchors)
            per_set: dict[str, list[list[_Measurement | None]]] = {}
            for set_name, points in sets.items():
                by_output: list[list[_Measurement | None]] = [[] for _ in convention.outputs]
                for x in points:
                    firing = rule_base.evaluate(np.asarray(x, dtype=np.float64))
                    lower = firing.firing_strengths_lower
                    upper = firing.firing_strengths_upper
                    if lower is None or upper is None:
                        raise RuntimeError("an interval type-2 grid returned a type-1 firing")
                    for o in range(len(convention.outputs)):
                        values = firing.consequent_outputs[:, o]
                        by_output[o].append(_measure(lower, upper, values))
                per_set[set_name] = by_output
            for o, output in enumerate(convention.outputs):
                for set_name in sets:
                    key = (grid.name, convention.name, output, set_name)
                    rows.extend(_summary_rows(key, per_set[set_name][o]))
                if len(sets) > 1:
                    pooled = [m for set_name in sets for m in per_set[set_name][o]]
                    key = (grid.name, convention.name, output, POOLED)
                    rows.extend(_summary_rows(key, pooled))
    return rows


def _source_commit() -> str:
    """``HEAD`` of the checkout holding this script, ``+dirty`` if tracked files changed."""
    root = Path(__file__).resolve().parent.parent
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown (git unavailable)"
    return f"{sha}+dirty" if status else sha


def header_lines(
    range_source: str,
    survey: Survey,
    grids: Sequence[Grid],
    sets: dict[str, FloatArray],
    seed: int,
) -> list[str]:
    """The provenance lines FR-3 requires, without the leading ``# ``."""
    lo, hi = (bound.tolist() for bound in domain_box(survey.samples))
    medians = survey.spread_medians.tolist()
    units = list(zip(FEATURES, FEATURE_UNITS, strict=True))
    box = "; ".join(f"{f} [{lo[i]!r}, {hi[i]!r}] {u}" for i, (f, u) in enumerate(units))
    spreads = "; ".join(f"{f} {medians[i]!r} {u}" for i, (f, u) in enumerate(units))
    grid_text = " | ".join(f"{grid.name}: {grid.description}" for grid in grids)
    set_sizes = "; ".join(f"{name} {len(points)}" for name, points in sets.items())
    return [
        "script: scripts/type_reduction_discrepancy.py (Issue #61 Part A, FR-3)",
        f"commit: {_source_commit()}",
        f"range_source: {range_source} (box = per-feature [p1, p99], numpy.quantile linear)",
        "units: mean_T1 us; mean_T2 us; mean_readout_error dimensionless (archive units, "
        "not BasicCalibrationVectorizer's SI seconds)",
        f"box: {box}",
        f"grids: {grid_text}",
        "g59_qubit_spread: ASSUMED, pending confirmation by @mertefesensoy. s_i = median over "
        f"survey rows of <feature>_qubit_std (NC-042's statistic) = {spreads}. #84 File 02 "
        "called this grid #59's shipped footprint without stating its qubit_spread",
        "conventions: unit-spread = zero-order, rule r bias r/(R-1), one output 'unit'; "
        "anchored = anchored_rule_base with feature_target_fn("
        f"t_seconds={SX_GATE_SECONDS!r}, coherence_unit='us') at the quantile anchors, "
        "outputs gamma and lambda per sx gate",
        f"point_sets: {set_sizes}"
        + (
            "; uniform drawn in the box by numpy.random.default_rng(seed)"
            if "uniform" in sets
            else ""
        )
        + ("; pooled = all listed sets" if len(sets) > 1 else ""),
        f"seed: {seed}",
        "reducers: bmm_half = (Y(lower) + Y(upper))/2, what NieTanDefuzzifier computes; "
        "nie_tan = Y(lower + upper), textbook Nie-Tan",
        "distances: D = |y - (y_l + y_r)/2| with Karnik-Mendel endpoints; "
        "Dc = D/(max c - min c); Db = min(D/(y_r - y_l), 1/2), 0 and counted in "
        "n_degenerate_band where y_r - y_l <= 64 R eps max|c|; a reducer outside "
        "[y_l, y_r] by more than that tolerance is counted in n_bracket_violations; "
        "km_route_gap_max = max |iterative - exhaustive|",
    ]


def write_tsv(path: Path, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    """Write ``# `` provenance lines, the column row, then ``rows``, with LF line endings."""
    lines = [f"# {line}" for line in header]
    lines.append("\t".join(COLUMNS))
    lines.extend("\t".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.type_reduction_discrepancy",
        description=(
            "Measure BMM(1/2, 1/2) and Nie-Tan against the Karnik-Mendel midpoint "
            "(Issue #61 Part A, FR-3)."
        ),
    )
    parser.add_argument("--range-source", required=True, help="survey:<survey.tsv>")
    parser.add_argument(
        "--footprint",
        action="append",
        required=True,
        help=f"a ratio w in (0, 1), or {G59_TOKEN!r}; repeat for several grids",
    )
    parser.add_argument("--points", type=int, required=True, help="uniform points in the box")
    parser.add_argument("--seed", type=int, required=True, help="seed for the uniform draw")
    parser.add_argument("--out", type=Path, required=True, help="output TSV path")
    parser.add_argument(
        "--point-sets",
        default=",".join(POINT_SETS),
        help=f"comma-separated subset of {','.join(POINT_SETS)} (default: all)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sweep and write the TSV. Returns 0; raises on invalid arguments."""
    args = _parse_args(argv)
    survey_path = parse_range_source(args.range_source)
    tokens = [parse_footprint(text) for text in args.footprint]
    if len(set(tokens)) != len(tokens):
        raise ValueError(f"--footprint values must be distinct; got {args.footprint}")
    names = parse_point_sets(args.point_sets)
    if "uniform" in names and args.points < 1:
        raise ValueError("--points must be at least 1 when the uniform point set is requested")
    survey = load_survey(survey_path)
    grids = [build_grid(token, survey) for token in tokens]
    sets = point_sets(names, survey, args.points, args.seed)
    started = time.perf_counter()
    rows = run_sweep(survey, grids, sets)
    write_tsv(args.out, header_lines(args.range_source, survey, grids, sets, args.seed), rows)
    elapsed = time.perf_counter() - started
    print(f"wrote {len(rows)} rows to {args.out} in {elapsed:.1f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
