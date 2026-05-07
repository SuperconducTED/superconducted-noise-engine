"""Benchmark harness — engine vs reference, returning a results table.

Bootstrap status: full. Mean-aggregates ensemble counts (across members)
into a single :class:`SimulationResult` per circuit. Interval-valued
aggregation across ensemble members is deferred to ADR-016.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel

from ..integration.aer_factory import FuzzyNoiseModelEnsemble
from ..interfaces import BenchmarkMetric
from ..types import SimulationResult


@dataclass(frozen=True)
class BenchmarkRow:
    """One row of the benchmark results table.

    ``engine_value`` is ``metric.compute(engine, reference)`` — the
    measured deviation between the fuzzy engine's ensemble-aggregated
    output and the reference simulation.

    ``reference_value`` is ``metric.compute(reference, reference)`` — the
    metric's self-similarity baseline (0.0 for distance metrics, 1.0 for
    fidelity / R^2 on a constant baseline).

    ``delta = engine_value - reference_value``, the actual deviation
    expressed against the metric's own baseline.
    """

    circuit_name: str
    metric_name: str
    engine_value: float
    reference_value: float
    delta: float


def _circuit_name(circuit: QuantumCircuit) -> str:
    name = getattr(circuit, "name", None)
    return str(name) if name else "circuit"


def simulate_engine(
    circuits: Sequence[QuantumCircuit],
    ensemble: FuzzyNoiseModelEnsemble,
    *,
    shots: int = 4096,
) -> list[SimulationResult]:
    """Run each circuit through every ensemble member and aggregate counts.

    Bootstrap aggregation is element-wise sum across members, retaining
    the total shot count so metric functions normalize correctly.
    """
    sim = AerSimulator()
    out: list[SimulationResult] = []
    members = list(ensemble)
    if not members:
        raise ValueError("Cannot simulate with an empty ensemble")
    for circuit in circuits:
        member_counts: list[Counter[str]] = []
        for member in members:
            prepared_circ, prepared_nm = member.prepare(circuit.copy())
            result = sim.run(prepared_circ, shots=shots, noise_model=prepared_nm).result()
            member_counts.append(Counter(result.get_counts()))
        aggregate: Counter[str] = Counter()
        for c in member_counts:
            aggregate.update(c)
        metadata: dict[str, Any] = {
            "ensemble_size": len(members),
            "circuit_name": _circuit_name(circuit),
        }
        out.append(
            SimulationResult(
                shots=shots * len(members),
                backend_label="engine",
                counts=aggregate,
                metadata=metadata,
            )
        )
    return out


def simulate_reference(
    circuits: Sequence[QuantumCircuit],
    reference_noise: NoiseModel,
    *,
    shots: int = 4096,
) -> list[SimulationResult]:
    """Run each circuit once against the reference noise model."""
    sim = AerSimulator()
    out: list[SimulationResult] = []
    for circuit in circuits:
        result = sim.run(circuit, shots=shots, noise_model=reference_noise).result()
        out.append(
            SimulationResult(
                shots=shots,
                backend_label="reference",
                counts=Counter(result.get_counts()),
                metadata={"circuit_name": _circuit_name(circuit)},
            )
        )
    return out


def run_benchmark(
    circuits: Sequence[QuantumCircuit],
    ensemble: FuzzyNoiseModelEnsemble,
    reference_noise: NoiseModel,
    metrics: Sequence[BenchmarkMetric],
    *,
    shots: int = 4096,
) -> list[BenchmarkRow]:
    """Run engine + reference simulations across the metric grid."""
    engine_results = simulate_engine(circuits, ensemble, shots=shots)
    reference_results = simulate_reference(circuits, reference_noise, shots=shots)
    rows: list[BenchmarkRow] = []
    for circuit, engine_result, reference_result in zip(
        circuits, engine_results, reference_results, strict=True
    ):
        circ_name = _circuit_name(circuit)
        for metric in metrics:
            engine_value = _try_compute(metric, engine_result, reference_result)
            reference_value = _try_compute(metric, reference_result, reference_result)
            delta = (
                float("nan")
                if math.isnan(engine_value) or math.isnan(reference_value)
                else engine_value - reference_value
            )
            rows.append(
                BenchmarkRow(
                    circuit_name=circ_name,
                    metric_name=metric.name,
                    engine_value=engine_value,
                    reference_value=reference_value,
                    delta=delta,
                )
            )
    return rows


def _try_compute(metric: BenchmarkMetric, a: SimulationResult, b: SimulationResult) -> float:
    try:
        return float(metric.compute(a, b))
    except (ValueError, ZeroDivisionError):
        return float("nan")
