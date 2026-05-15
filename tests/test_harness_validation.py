from collections import Counter

import numpy as np
import pytest
from superconducted.noise_engine.results import SimulationResult

from superconducted.benchmarks.metrics import (
    HellingerDistance,
    KLDivergence,
    R2Score,
    StateFidelity,
)

# --- HELPER FUNCTIONS ---


def make_counts(counts_dict: dict[str, int]) -> SimulationResult:
    """Builds a real SimulationResult instance from a counts dictionary."""
    return SimulationResult(
        shots=sum(counts_dict.values()), backend_label="test", counts=Counter(counts_dict)
    )


def make_state(matrix: list[list[complex]]) -> SimulationResult:
    """Builds a real SimulationResult instance from a density matrix."""
    m = np.array(matrix, dtype=np.complex128)
    return SimulationResult(shots=1, backend_label="test", density_matrix=m)


# --- 1. IDENTITY TESTS ---


def test_hellinger_identity():
    """Hellinger distance between identical distributions must be exactly 0.0."""
    metric = HellingerDistance()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_kl_identity():
    """KL divergence between identical distributions must be exactly 0.0."""
    metric = KLDivergence()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_fidelity_identity():
    """State fidelity of a density matrix with itself must be exactly 1.0."""
    metric = StateFidelity()
    rho = [[1.0, 0.0], [0.0, 0.0]]
    res = make_state(rho)
    assert metric.compute(res, res) == pytest.approx(1.0, abs=1e-10)


# --- 2. SYMMETRY TESTS ---


def test_hellinger_symmetry():
    """Hellinger distance must be symmetric: H(P, Q) == H(Q, P)."""
    metric = HellingerDistance()
    res1 = make_counts({"00": 80, "11": 20})
    res2 = make_counts({"00": 20, "11": 80})
    assert metric.compute(res1, res2) == metric.compute(res2, res1)


def test_fidelity_symmetry():
    """State fidelity must be symmetric: F(rho, sigma) == F(sigma, rho)."""
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]
    rho2 = [[0.5, 0.5], [0.5, 0.5]]
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(metric.compute(res2, res1), abs=1e-10)


# --- 3. BOUNDS & REFERENCE TESTS ---


def test_hellinger_disjoint():
    """Hellinger distance should be maximum (1.0) for completely disjoint datasets."""
    metric = HellingerDistance()
    res1 = make_counts({"00": 100})
    res2 = make_counts({"11": 100})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_fidelity_orthogonal():
    """Fidelity of completely orthogonal quantum states should be 0.0."""
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]
    rho2 = [[0.0, 0.0], [0.0, 1.0]]
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(0.0, abs=1e-10)


def test_r2_score_perfect():
    """R2 score should return 1.0 when datasets match perfectly (non-uniform reference)."""
    metric = R2Score()
    res1 = make_counts({"00": 70, "11": 30})
    res2 = make_counts({"00": 70, "11": 30})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_r2_score_constant_mismatch():
    """R2 score should be 0.0 when the reference is uniformly distributed but engine deviates."""
    metric = R2Score()
    res_eng = make_counts({"00": 100})
    res_ref = make_counts({"00": 50, "11": 50})
    assert metric.compute(res_eng, res_ref) == pytest.approx(0.0, abs=1e-10)


# --- 4. ASYMMETRY TESTS ---


def test_kl_asymmetry():
    """KL Divergence is directional; opposite directions must differ by a non-trivial margin."""
    metric = KLDivergence()
    res1 = make_counts({"00": 90, "11": 10})
    res2 = make_counts({"00": 50, "11": 50})
    kl_12 = metric.compute(res1, res2)
    kl_21 = metric.compute(res2, res1)

    assert abs(kl_12 - kl_21) > 1e-3
