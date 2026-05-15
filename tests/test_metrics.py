"""Sanity-check tests for benchmark metrics: Hellinger, KL, state fidelity, R²."""

from collections import Counter

import numpy as np
import pytest

from superconducted.benchmarks.metrics import (
    HellingerDistance,
    KLDivergence,
    R2Score,
    StateFidelity,
)
from superconducted.types import SimulationResult

# shots is meaningless in state-vector mode, but SimulationResult.__post_init__
# requires shots > 0.
SHOTS_FOR_STATE_MODE = 1


# --- HELPER FUNCTIONS ---


def make_counts(counts_dict: dict[str, int]) -> SimulationResult:
    """Builds a real SimulationResult instance from a counts dictionary."""
    return SimulationResult(
        shots=sum(counts_dict.values()), backend_label="test", counts=Counter(counts_dict)
    )


def make_state(matrix: list[list[float | complex]]) -> SimulationResult:
    """Builds a real SimulationResult instance from a density matrix."""
    m = np.array(matrix, dtype=np.complex128)
    return SimulationResult(shots=SHOTS_FOR_STATE_MODE, backend_label="test", density_matrix=m)


# --- 1. IDENTITY TESTS ---


def test_hellinger_identity() -> None:
    """Hellinger distance between identical distributions must be exactly 0.0."""
    metric = HellingerDistance()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_kl_identity() -> None:
    """KL divergence between identical distributions must be exactly 0.0."""
    metric = KLDivergence()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_fidelity_identity() -> None:
    """State fidelity of a density matrix with itself must be exactly 1.0."""
    metric = StateFidelity()
    rho = [[1.0, 0.0], [0.0, 0.0]]
    res = make_state(rho)
    assert metric.compute(res, res) == pytest.approx(1.0, abs=1e-10)


# --- 2. SYMMETRY TESTS ---


def test_hellinger_symmetry() -> None:
    """Hellinger distance must be symmetric: H(P, Q) == H(Q, P)."""
    metric = HellingerDistance()
    res1 = make_counts({"00": 80, "11": 20})
    res2 = make_counts({"00": 20, "11": 80})
    assert metric.compute(res1, res2) == metric.compute(res2, res1)


def test_fidelity_symmetry() -> None:
    """State fidelity must be symmetric: F(rho, sigma) == F(sigma, rho)."""
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]
    rho2 = [[0.5, 0.5], [0.5, 0.5]]
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(metric.compute(res2, res1), abs=1e-10)


# --- 3. BOUNDS & REFERENCE TESTS ---


def test_hellinger_disjoint() -> None:
    """Hellinger distance should be maximum (1.0) for completely disjoint datasets."""
    metric = HellingerDistance()
    res1 = make_counts({"00": 100})
    res2 = make_counts({"11": 100})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_fidelity_orthogonal() -> None:
    """Fidelity of completely orthogonal quantum states should be 0.0."""
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]
    rho2 = [[0.0, 0.0], [0.0, 1.0]]
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(0.0, abs=1e-10)


def test_r2_score_perfect() -> None:
    """R2 score should return 1.0 when datasets match perfectly (non-uniform reference)."""
    metric = R2Score()
    res1 = make_counts({"00": 70, "11": 30})
    res2 = make_counts({"00": 70, "11": 30})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_r2_score_constant_reference_fallback() -> None:
    """Returns 0.0 when the reference probability is constant on the joint support (ss_tot = 0) but engine differs."""
    metric = R2Score()
    res_eng = make_counts({"00": 100})
    res_ref = make_counts({"00": 50, "11": 50})
    assert metric.compute(res_eng, res_ref) == pytest.approx(0.0, abs=1e-10)


# --- 4. ASYMMETRY TESTS ---


def test_kl_asymmetry() -> None:
    """KL Divergence is directional; opposite directions must differ by a non-trivial margin."""
    metric = KLDivergence()
    res1 = make_counts({"00": 90, "11": 10})
    res2 = make_counts({"00": 50, "11": 50})
    kl_12 = metric.compute(res1, res2)
    kl_21 = metric.compute(res2, res1)

    assert abs(kl_12 - kl_21) > 1e-3


# --- 5. BRANCH-COVERAGE TESTS ---


def test_kl_smoothing_no_log_zero() -> None:
    """KL divergence with a zero bin must stay finite via epsilon smoothing."""
    metric = KLDivergence()
    engine = make_counts({"00": 100})  # zero bin at "11"
    reference = make_counts({"00": 50, "11": 50})
    value = metric.compute(engine, reference)
    assert np.isfinite(value)


def test_r2_score_partial_match() -> None:
    """R² standard formula with non-zero ss_res and non-zero ss_tot.

    engine [0.6, 0.4] vs reference [0.7, 0.3]:
        ss_res = (0.7 - 0.6)^2 + (0.3 - 0.4)^2 = 0.02
        ss_tot = (0.7 - 0.5)^2 + (0.3 - 0.5)^2 = 0.08
        R^2    = 1 - 0.02 / 0.08 = 0.75
    """
    metric = R2Score()
    engine = make_counts({"00": 60, "11": 40})
    reference = make_counts({"00": 70, "11": 30})
    assert metric.compute(engine, reference) == pytest.approx(0.75, abs=1e-10)


def test_count_metric_rejects_state_mode() -> None:
    """Count-based metrics must raise when handed a density-matrix-only result."""
    metric = HellingerDistance()
    counts_res = make_counts({"00": 50, "11": 50})
    state_res = make_state([[1.0, 0.0], [0.0, 0.0]])
    with pytest.raises(ValueError, match="Count-based metric"):
        metric.compute(counts_res, state_res)


def test_state_metric_rejects_counts_mode() -> None:
    """StateFidelity must raise when handed a counts-only SimulationResult."""
    metric = StateFidelity()
    state_res = make_state([[1.0, 0.0], [0.0, 0.0]])
    counts_res = make_counts({"00": 50, "11": 50})
    with pytest.raises(ValueError, match="density_matrix"):
        metric.compute(state_res, counts_res)


def test_normalize_rejects_empty_distribution() -> None:
    """_normalized_probabilities must raise when both counts distributions are empty."""
    metric = HellingerDistance()
    empty = SimulationResult(shots=1, backend_label="test", counts=Counter())
    with pytest.raises(ValueError, match="empty counts distribution"):
        metric.compute(empty, empty)
