from collections import Counter
from unittest.mock import MagicMock

import numpy as np
import pytest

from superconducted.benchmarks.metrics import (
    HellingerDistance,
    KLDivergence,
    R2Score,
    StateFidelity,
)

# --- HELPER FUNCTIONS (Mock Objects) ---
# We mock the SimulationResult format required by the metrics without running the actual system.


def make_counts(counts_dict):
    """Mocks a result containing only 'counts' data."""
    res = MagicMock()
    res.counts = Counter(counts_dict)
    res.density_matrix = None
    return res


def make_state(matrix):
    """Mocks a result containing only 'density_matrix' data."""
    res = MagicMock()
    res.counts = None
    res.density_matrix = np.array(matrix)
    return res


# --- 1. IDENTITY TESTS ---


def test_hellinger_identity():
    metric = HellingerDistance()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_kl_identity():
    metric = KLDivergence()
    res = make_counts({"00": 50, "11": 50})
    assert metric.compute(res, res) == pytest.approx(0.0, abs=1e-10)


def test_fidelity_identity():
    metric = StateFidelity()
    # Ground state for 1 qubit: |0><0|
    rho = [[1.0, 0.0], [0.0, 0.0]]
    res = make_state(rho)
    assert metric.compute(res, res) == pytest.approx(1.0, abs=1e-10)


# --- 2. SYMMETRY TESTS ---


def test_hellinger_symmetry():
    metric = HellingerDistance()
    res1 = make_counts({"00": 80, "11": 20})
    res2 = make_counts({"00": 20, "11": 80})
    assert metric.compute(res1, res2) == metric.compute(res2, res1)


def test_fidelity_symmetry():
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]
    rho2 = [[0.5, 0.5], [0.5, 0.5]]
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(metric.compute(res2, res1), abs=1e-10)


# --- 3. BOUNDS & REFERENCE TESTS ---


def test_hellinger_disjoint():
    # Hellinger distance should be maximum (1.0) for completely disjoint datasets.
    metric = HellingerDistance()
    res1 = make_counts({"00": 100})
    res2 = make_counts({"11": 100})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_fidelity_orthogonal():
    # Fidelity of completely orthogonal quantum states should be 0.
    metric = StateFidelity()
    rho1 = [[1.0, 0.0], [0.0, 0.0]]  # |0><0|
    rho2 = [[0.0, 0.0], [0.0, 1.0]]  # |1><1|
    res1 = make_state(rho1)
    res2 = make_state(rho2)
    assert metric.compute(res1, res2) == pytest.approx(0.0, abs=1e-10)


def test_r2_score_perfect():
    # R2 score should return 1.0 when datasets match perfectly.
    metric = R2Score()
    res1 = make_counts({"00": 50, "11": 50})
    res2 = make_counts({"00": 50, "11": 50})
    assert metric.compute(res1, res2) == pytest.approx(1.0, abs=1e-10)


def test_r2_score_constant_mismatch():
    # R2 score should be 0 when the reference is uniformly distributed (constant) but the engine produces a completely different result.
    metric = R2Score()
    res_eng = make_counts({"00": 100})
    res_ref = make_counts({"00": 50, "11": 50})  # Uniformly distributed reference
    assert metric.compute(res_eng, res_ref) == pytest.approx(0.0, abs=1e-10)


# --- 4. ASYMMETRY TESTS ---


def test_kl_asymmetry():
    # KL Divergence is a directional metric; results in opposite directions should differ.
    metric = KLDivergence()
    res1 = make_counts({"00": 90, "11": 10})
    res2 = make_counts({"00": 50, "11": 50})
    kl_12 = metric.compute(res1, res2)
    kl_21 = metric.compute(res2, res1)
    assert kl_12 != kl_21
