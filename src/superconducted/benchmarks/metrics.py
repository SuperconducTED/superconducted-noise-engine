"""Benchmark metric implementations.

Distance metrics on count distributions: Hellinger, KL. Quantum-state
metrics: state fidelity. Regression-style metrics: R^2.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import numpy.typing as npt

from ..interfaces import BenchmarkMetric
from ..types import SimulationResult


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
