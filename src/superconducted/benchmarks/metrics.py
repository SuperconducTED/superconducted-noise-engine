"""Benchmark metric implementations.

Distance metrics on count distributions: Hellinger, KL. Quantum-state
metrics: state fidelity. Regression-style metrics: R^2. Ensemble metrics
(Issue #64): the per-outcome interval band of an ensemble's members and the
share of a reference distribution's mass that lies inside it.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from ..interfaces import BenchmarkMetric
from ..types import SimulationResult

# Largest excursion of a density matrix's diagonal outside [0, 1], of its
# imaginary part away from 0, that is treated as rounding and clamped. A
# simulator can return -1e-17 for an exact zero; anything larger is not a
# state and is refused. Dimensionless (a probability).
_DIAGONAL_TOLERANCE: float = 1e-12

# Largest departure of a density matrix's trace from 1 that is accepted.
_TRACE_TOLERANCE: float = 1e-9


def _normalized_probabilities(
    counts: Counter[str], support: list[str]
) -> tuple[npt.NDArray[np.float64], int]:
    total = sum(counts.values())
    if total == 0:
        raise ValueError("Cannot normalize an empty counts distribution")
    p = np.array([counts.get(k, 0) for k in support], dtype=np.float64) / float(total)
    return p, total


def _aligned_counts(
    engine: SimulationResult, reference: SimulationResult
) -> tuple[Counter[str], Counter[str]]:
    if engine.counts is None or reference.counts is None:
        raise ValueError("Count-based metric requires both SimulationResults to carry counts")
    return engine.counts, reference.counts


class HellingerDistance(BenchmarkMetric):
    """Hellinger distance between count distributions.

    ``H(P, Q) = (1/sqrt(2)) * sqrt(sum_i (sqrt(p_i) - sqrt(q_i))^2)``.
    Symmetric, in ``[0, 1]``.
    """

    @property
    def name(self) -> str:
        return "hellinger"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        c_eng, c_ref = _aligned_counts(engine, reference)
        support = sorted(set(c_eng) | set(c_ref))
        p, _ = _normalized_probabilities(c_eng, support)
        q, _ = _normalized_probabilities(c_ref, support)
        return float(math.sqrt(np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)) / math.sqrt(2.0))


class KLDivergence(BenchmarkMetric):
    """``KL(engine || reference)`` on smoothed count distributions.

    Adds ``epsilon`` to zero bins to avoid ``log(0)``. Asymmetric;
    swap operands for ``KL(reference || engine)``.
    """

    def __init__(self, epsilon: float = 1e-12) -> None:
        if epsilon <= 0:
            raise ValueError(f"epsilon must be positive; got {epsilon}")
        self._epsilon = float(epsilon)

    @property
    def name(self) -> str:
        return "kl_divergence"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        c_eng, c_ref = _aligned_counts(engine, reference)
        support = sorted(set(c_eng) | set(c_ref))
        p, _ = _normalized_probabilities(c_eng, support)
        q, _ = _normalized_probabilities(c_ref, support)
        p_smoothed = np.maximum(p, self._epsilon)
        q_smoothed = np.maximum(q, self._epsilon)
        return float(np.sum(p_smoothed * np.log(p_smoothed / q_smoothed)))


class StateFidelity(BenchmarkMetric):
    """State fidelity between density matrices.

    ``F(rho, sigma) = (Tr sqrt(sqrt(rho) sigma sqrt(rho)))^2``. Uses
    :func:`qiskit.quantum_info.state_fidelity` for numerical stability.
    """

    @property
    def name(self) -> str:
        return "state_fidelity"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        if engine.density_matrix is None or reference.density_matrix is None:
            raise ValueError(
                "StateFidelity requires both SimulationResults to carry density_matrix"
            )
        from qiskit.quantum_info import DensityMatrix, state_fidelity

        return float(
            state_fidelity(
                DensityMatrix(engine.density_matrix),
                DensityMatrix(reference.density_matrix),
            )
        )


class R2Score(BenchmarkMetric):
    """Coefficient of determination on per-bin probability deviations.

    Mirrors the metric reported in arXiv:2503.06693 for cross-comparison.
    Treats reference probabilities as the "true" series and engine
    probabilities as predictions::

        R^2 = 1 - sum((p_ref - p_eng)^2) / sum((p_ref - mean(p_ref))^2)

    Returns 1.0 if reference is constant *and* engine matches; 0.0 if
    constant and mismatched; otherwise the standard formula.
    """

    @property
    def name(self) -> str:
        return "r2_score"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        c_eng, c_ref = _aligned_counts(engine, reference)
        support = sorted(set(c_eng) | set(c_ref))
        p_eng, _ = _normalized_probabilities(c_eng, support)
        p_ref, _ = _normalized_probabilities(c_ref, support)
        ss_res = float(np.sum((p_ref - p_eng) ** 2))
        ss_tot = float(np.sum((p_ref - p_ref.mean()) ** 2))
        if ss_tot == 0.0:
            return 1.0 if ss_res == 0.0 else 0.0
        return 1.0 - ss_res / ss_tot


def _outcome_probabilities(
    result: SimulationResult,
) -> tuple[tuple[str, ...], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Outcomes of one result with their probabilities and their unnormalised masses.

    Returns ``(keys, probabilities, masses)``, aligned. A key is a Qiskit
    bitstring: the rightmost character is qubit 0.

    - Counts: ``masses`` are the counts and ``probabilities`` are the counts
      divided by the result's own total, the same division the count metrics
      above use.
    - Density matrix: both are the diagonal, read in Qiskit's order (index
      ``i`` is the outcome whose bitstring is ``i`` in binary), clamped to
      ``[0, 1]`` at rounding level.

    The two arrays differ on purpose. Whether a reference outcome is inside a
    band is decided on ``probabilities``, which are computed the same way for
    members and reference, so an identical member and reference compare equal
    bit for bit. How much mass is covered is a ratio of sums of ``masses``,
    which is exactly 1 when everything is covered even where the
    probabilities themselves do not sum to 1.0 in floating point.

    Raises ``ValueError`` for an empty counts distribution, for a negative
    count (a ``Counter`` can hold one, and the coverage ratio is bounded by 1
    only for non-negative masses), and for a density matrix that is not
    square with a power-of-two dimension, whose diagonal leaves ``[0, 1]`` or
    the real axis by more than ``_DIAGONAL_TOLERANCE``, or whose trace is
    further than ``_TRACE_TOLERANCE`` from 1.
    """
    if result.counts is not None:
        keys = tuple(sorted(result.counts))
        masses = np.array([result.counts[key] for key in keys], dtype=np.float64)
        if masses.size and masses.min() < 0.0:
            raise ValueError(f"Counts must be non-negative; got a minimum of {masses.min()}")
        total = float(masses.sum())
        if total <= 0.0:
            raise ValueError("Cannot normalize an empty counts distribution")
        return keys, masses / total, masses

    matrix = np.asarray(result.density_matrix)
    dim = matrix.shape[0] if matrix.ndim == 2 else 0
    if matrix.ndim != 2 or matrix.shape[1] != dim or dim < 2 or dim & (dim - 1):
        raise ValueError(
            "A density matrix must be square with a power of two dimension; "
            f"got shape {matrix.shape}"
        )
    diagonal = np.diagonal(matrix)
    real = np.real(diagonal).astype(np.float64)
    if (
        np.max(np.abs(np.imag(diagonal))) > _DIAGONAL_TOLERANCE
        or real.min() < -_DIAGONAL_TOLERANCE
        or real.max() > 1.0 + _DIAGONAL_TOLERANCE
    ):
        raise ValueError(
            "A density matrix's diagonal must be real and in [0, 1] to within "
            f"{_DIAGONAL_TOLERANCE}; got minimum {real.min()}, maximum {real.max()}"
        )
    if abs(math.fsum(real.tolist()) - 1.0) > _TRACE_TOLERANCE:
        raise ValueError(f"A density matrix must have trace 1; got {math.fsum(real.tolist())}")
    probabilities = np.clip(real, 0.0, 1.0)
    width = dim.bit_length() - 1
    keys = tuple(format(index, f"0{width}b") for index in range(dim))
    return keys, probabilities, probabilities


def _check_alpha(alpha: float) -> None:
    """Raise ``ValueError`` unless ``0 <= alpha < 0.5`` (NaN and infinities fail)."""
    if not 0.0 <= alpha < 0.5:
        raise ValueError(f"alpha must satisfy 0 <= alpha < 0.5; got {alpha}")


@dataclass(frozen=True, slots=True, eq=False)
class IntervalBand:
    """A per-outcome band built from the members of an ensemble.

    For every outcome ``b`` in ``support``, ``lower[b]`` and ``upper[b]`` are
    the ``alpha`` and ``1 - alpha`` sample quantiles of the members'
    probabilities of ``b`` under the named NumPy ``method``. ``alpha = 0`` is
    the min/max band. All values are dimensionless probabilities.

    Fields:

    - ``support``: the outcomes, as Qiskit bitstrings (rightmost character is
      qubit 0), distinct, in the order of ``lower`` and ``upper``.
    - ``lower``, ``upper``: float64 arrays of ``len(support)``. They are
      copied on construction and made read-only, so a band cannot change
      after it is built and never aliases the caller's arrays.
    - ``alpha``: the tail probability cut from each side, ``0 <= alpha < 0.5``.
      It is half of a pair with the jitter scale ``r`` (Issue #64 D2), which
      is why it is stored on every band.
    - ``method``: the ``numpy.quantile`` method, stored so the band can be
      reproduced.
    - ``n_members``: how many members the quantiles were taken over.

    What a band is not: a calibrated predictive interval. ``alpha = 0.1``
    cuts the central 80% of *these members*; whether 80% of anything else
    falls inside is a property of how the members were made.

    Raises ``ValueError`` when the arrays are not one-dimensional, when their
    lengths differ from ``support``'s, when outcomes repeat, when a value is
    not finite or lies outside ``[0, 1]``, when ``lower > upper`` anywhere,
    when ``alpha`` is outside ``[0, 0.5)``, when ``n_members < 2`` (a band of
    one member is a point) or when ``method`` is empty.
    """

    support: tuple[str, ...]
    lower: npt.NDArray[np.float64]
    upper: npt.NDArray[np.float64]
    alpha: float
    method: str
    n_members: int

    def __post_init__(self) -> None:
        support = tuple(self.support)
        lower = np.array(self.lower, dtype=np.float64)
        upper = np.array(self.upper, dtype=np.float64)
        if lower.ndim != 1 or upper.ndim != 1:
            raise ValueError("IntervalBand lower and upper must be one-dimensional")
        if not len(support) == lower.size == upper.size:
            raise ValueError(
                "IntervalBand support, lower and upper must have the same length; "
                f"got {len(support)}, {lower.size}, {upper.size}"
            )
        if len(set(support)) != len(support):
            raise ValueError("IntervalBand support outcomes must be distinct")
        if not (np.all(np.isfinite(lower)) and np.all(np.isfinite(upper))):
            raise ValueError("IntervalBand lower and upper must be finite")
        if lower.size and (lower.min() < 0.0 or upper.max() > 1.0 or upper.min() < 0.0):
            raise ValueError("IntervalBand lower and upper must lie in [0, 1]")
        if np.any(lower > upper):
            raise ValueError("IntervalBand requires lower <= upper for every outcome")
        _check_alpha(self.alpha)
        if self.n_members < 2:
            raise ValueError(
                f"IntervalBand needs at least two members; got {self.n_members} "
                "(a band of one member is a point)"
            )
        if not self.method:
            raise ValueError("IntervalBand method must name a numpy.quantile method")
        lower.setflags(write=False)
        upper.setflags(write=False)
        object.__setattr__(self, "support", support)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "alpha", float(self.alpha))
        object.__setattr__(self, "n_members", int(self.n_members))


def interval_band(
    members: Sequence[SimulationResult], *, alpha: float, method: str = "linear"
) -> IntervalBand:
    """Build the per-outcome quantile band of an ensemble's members.

    Inputs: ``members`` are the results of the ensemble's members for one
    circuit, all in counts mode or all in density-matrix mode. ``alpha`` is
    the tail probability cut from each side and has no default: Issue #64 D2
    fixes it together with the jitter scale, so a band is never built without
    naming it. ``method`` is passed to ``numpy.quantile``.

    Output: an :class:`IntervalBand` over the union of the members' outcomes,
    sorted. A member that never saw an outcome has probability 0 there. With
    ``alpha = 0`` the edges are exactly the members' per-outcome minimum and
    maximum.

    No side effects. Raises ``ValueError`` for fewer than two members, for
    members in mixed modes, for density matrices of different shapes, for
    ``alpha`` outside ``[0, 0.5)``, for an unknown ``method``, and for any
    member :func:`_outcome_probabilities` refuses.
    """
    members = list(members)
    if len(members) < 2:
        raise ValueError(
            f"interval_band needs at least two members; got {len(members)} "
            "(a band of one member is a point)"
        )
    _check_alpha(alpha)
    if len({member.counts is not None for member in members}) != 1:
        raise ValueError(
            "interval_band got members in mixed modes; pass all counts or all density matrices"
        )
    shapes = {
        np.shape(member.density_matrix) for member in members if member.density_matrix is not None
    }
    if len(shapes) > 1:
        raise ValueError(
            f"interval_band's density matrices must have the same shape; got {sorted(shapes)}"
        )
    per_member = []
    for member in members:
        keys, probabilities, _ = _outcome_probabilities(member)
        per_member.append(dict(zip(keys, probabilities.tolist(), strict=True)))
    support = tuple(sorted(set().union(*per_member)))
    table = np.array(
        [[outcomes.get(key, 0.0) for key in support] for outcomes in per_member],
        dtype=np.float64,
    )
    lower, upper = np.quantile(table, [alpha, 1.0 - alpha], axis=0, method=method)  # type: ignore[call-overload]
    return IntervalBand(
        support=support,
        lower=lower,
        upper=upper,
        alpha=alpha,
        method=method,
        n_members=len(members),
    )


class IntervalCoverage:
    """The share of a reference distribution's mass that lies inside a band.

    ``C(B, q) = sum over outcomes b of q(b) * 1[L(b) <= q(b) <= U(b)]``,
    with both edges inclusive (Issue #64 section 6.3). Weighting by the
    reference's mass makes empty outcomes contribute nothing, so a circuit
    whose reference lives on two of eight outcomes is not scored 6/8 for
    free. An outcome the band has never seen has the band ``[0, 0]``: any
    reference mass there is uncovered. ``C`` is dimensionless and in
    ``[0, 1]``; its self-similarity value is
    ``compute(interval_band([q, q], alpha=0), q) == 1.0`` exactly.

    This is not a :class:`~superconducted.interfaces.BenchmarkMetric`: that
    ABC's ``compute`` takes two ``SimulationResult`` objects, and a band is a
    different kind of object (Issue #64 FR-9). It clears ADR-022's six
    properties in ``tests/test_interval_band.py``.
    """

    @property
    def name(self) -> str:
        return "interval_coverage"

    def compute(self, band: IntervalBand, reference: SimulationResult) -> float:
        """Return the covered share of ``reference``'s mass, in ``[0, 1]``.

        ``reference`` may be in counts or density-matrix mode, whichever mode
        the band's members were in. The value is the sum of the covered
        outcomes' masses divided by the sum of all masses (counts, or the
        diagonal), both taken with ``math.fsum``, so full coverage returns
        exactly 1.0 and the result never exceeds 1.

        No side effects. Raises ``ValueError`` for a reference
        :func:`_outcome_probabilities` refuses (an empty distribution, a
        malformed density matrix), and when the reference's outcome keys and
        the band's are not all of one length, which means the two come from
        different registers and would otherwise score a silent zero.
        """
        keys, probabilities, masses = _outcome_probabilities(reference)
        if len({len(key) for key in (*band.support, *keys)}) > 1:
            raise ValueError(
                "The reference's outcome keys and the band's must have one length; "
                f"got band {band.support[:2]} and reference {keys[:2]}"
            )
        index = {key: position for position, key in enumerate(band.support)}
        covered = []
        for key, probability, mass in zip(
            keys, probabilities.tolist(), masses.tolist(), strict=True
        ):
            position = index.get(key)
            lower = float(band.lower[position]) if position is not None else 0.0
            upper = float(band.upper[position]) if position is not None else 0.0
            if lower <= probability <= upper:
                covered.append(mass)
        return math.fsum(covered) / math.fsum(masses.tolist())
