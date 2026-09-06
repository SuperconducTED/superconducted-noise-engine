"""Regression tests for the three benchmark-harness defects in issue #58."""

from __future__ import annotations

import math

import pytest
from qiskit_aer import AerError
from qiskit_aer.noise import NoiseModel

from superconducted.benchmarks.circuits import ghz_state_circuit, qft_circuit
from superconducted.benchmarks.harness import (
    _try_compute,
    run_benchmark,
    simulate_reference,
)
from superconducted.benchmarks.metrics import StateFidelity
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.interfaces import BenchmarkMetric
from superconducted.types import SimulationResult


class _ValueErrorMetric(BenchmarkMetric):
    @property
    def name(self) -> str:
        return "value_error"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        raise ValueError("deliberate metric failure")


def test_state_fidelity_rows_are_nan_without_density_mode(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    """Reproduce 7d39a2b: fidelity silently becomes three NaNs instead of a state result."""
    rows = run_benchmark(
        [ghz_state_circuit(2)],
        benchmark_ensemble,
        NoiseModel(),
        [StateFidelity()],
        shots=64,
    )

    assert len(rows) == 1
    assert math.isnan(rows[0].engine_value)
    assert math.isnan(rows[0].reference_value)
    assert math.isnan(rows[0].delta)
    pytest.fail("issue #58: the harness has no density-matrix mode")


def test_qft_crashes_untranspiled() -> None:
    """Reproduce 7d39a2b: Aer rejects the undecomposed QFTGate as unknown."""
    try:
        simulate_reference([qft_circuit(3)], NoiseModel(), shots=64)
    except AerError as exc:
        assert "unknown instruction" in str(exc)
        pytest.fail(f"issue #58: the harness submitted QFT without transpiling: {exc}")


def test_try_compute_swallows_errors_silently() -> None:
    """Reproduce 7d39a2b: a metric ValueError is converted to NaN with no record."""
    result = SimulationResult(shots=1, backend_label="test", counts={"0": 1})

    value = _try_compute(_ValueErrorMetric(), result, result)

    assert math.isnan(value)
    pytest.fail("issue #58: _try_compute swallowed ValueError without a failure record")
