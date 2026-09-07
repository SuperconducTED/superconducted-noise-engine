"""Measure the benchmark harness's provisional gamma resolution.

The experiment compares two controlled single-qubit damping models that
differ only in amplitude-damping probability.  It deliberately bypasses the
fuzzy inference pipeline: :class:`PostGateFuzzification` installs channels
projected by :class:`KrausChannelProjector` on one circuit transpiled to an
explicit basis.  The same compiled circuit is then used for both models.

Counts mode measures Hellinger distance and ``1 - R^2``.  The latter is a
discrepancy (zero for identical samples), which is the orientation required
by the issue's "larger than the noise floor" rule.  Density-matrix mode
measures ``1 - state_fidelity`` without sampling.  A protocol-level delta is
resolved only when every prescribed circuit/metric cell resolves it.  These
two corrections operationalize the recommendations recorded on issue #58;
their output remains provisional until the named owners ratify the protocol.

Run from the repository root::

    python -m scripts.resolution_measurement --help
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, cast

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit import __version__ as qiskit_version
from qiskit.circuit import Instruction
from qiskit_aer import AerSimulator
from qiskit_aer import __version__ as qiskit_aer_version
from qiskit_aer.noise import NoiseModel, QuantumError

from superconducted.benchmarks.circuits import ghz_state_circuit, qft_circuit
from superconducted.benchmarks.metrics import HellingerDistance, R2Score, StateFidelity
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.interfaces import BenchmarkMetric
from superconducted.types import SimulationResult

Mode = Literal["counts", "density_matrix"]

_TRANSPILE_OPTIMIZATION_LEVEL = 1
_TRANSPILE_SEED = 0
_DENSITY_FLOOR = 1e-10
_REQUIRED_CELLS: dict[Mode, frozenset[tuple[str, str]]] = {
    "counts": frozenset(
        {
            ("qft_n3", "hellinger"),
            ("qft_n3", "one_minus_r2"),
            ("ghz_n3", "hellinger"),
            ("ghz_n3", "one_minus_r2"),
        }
    ),
    "density_matrix": frozenset(
        {
            ("qft_n3", "one_minus_state_fidelity"),
            ("ghz_n3", "one_minus_state_fidelity"),
        }
    ),
}


@dataclass(frozen=True, slots=True)
class ResolutionRow:
    """One auditable cell of the controlled resolution experiment."""

    circuit: str
    mode: Mode
    metric: str
    gamma_a: float
    lambda_a: float
    gamma_b: float
    gamma_delta: float
    repeats: int
    shots: int
    seed: int | None
    baseline_mean: float
    baseline_sample_sd: float
    threshold: float
    between_mean: float
    margin: float
    resolved: bool
    qiskit: str
    qiskit_aer: str


@dataclass(frozen=True, slots=True)
class MeasurementResult:
    """Rows and wall-clock duration returned by :func:`measure_resolution`."""

    rows: tuple[ResolutionRow, ...]
    elapsed_seconds: float


def _checked_basis(basis_gates: Sequence[str]) -> tuple[str, ...]:
    basis = tuple(basis_gates)
    if not basis or any(not name for name in basis):
        raise ValueError("basis_gates must contain non-empty gate names")
    if len(set(basis)) != len(basis):
        raise ValueError(f"basis_gates must not contain duplicates; got {basis}")
    return basis


def _checked_inputs(
    gamma: float,
    lam: float,
    deltas: Sequence[float],
    repeats: int,
    shots: int,
) -> tuple[float, float, tuple[float, ...]]:
    gamma = float(gamma)
    lam = float(lam)
    checked_deltas = tuple(float(delta) for delta in deltas)
    if not math.isfinite(gamma) or not 0.0 <= gamma <= 1.0:
        raise ValueError(f"gamma must be finite and in [0, 1]; got {gamma}")
    if not math.isfinite(lam) or not 0.0 <= lam <= 1.0:
        raise ValueError(f"lambda must be finite and in [0, 1]; got {lam}")
    if not checked_deltas:
        raise ValueError("deltas must contain at least one value")
    if len(set(checked_deltas)) != len(checked_deltas):
        raise ValueError(f"deltas must not contain duplicates; got {checked_deltas}")
    if any(not math.isfinite(delta) or delta <= 0.0 for delta in checked_deltas):
        raise ValueError(f"every delta must be finite and positive; got {checked_deltas}")
    if gamma + max(checked_deltas) > 1.0:
        raise ValueError(
            f"gamma + max(deltas) must not exceed 1; got {gamma + max(checked_deltas)}"
        )
    if repeats < 2:
        raise ValueError(
            f"repeats must be at least 2 for a sample standard deviation; got {repeats}"
        )
    if shots <= 0:
        raise ValueError(f"shots must be positive; got {shots}")
    return gamma, lam, checked_deltas


def _controlled_model(
    circuit: QuantumCircuit,
    *,
    gamma: float,
    lam: float,
    basis: tuple[str, ...],
) -> tuple[QuantumCircuit, NoiseModel]:
    projector = KrausChannelProjector(NoOpNormalization())
    params = np.asarray([gamma, lam], dtype=np.float64)

    def provider(gate: Instruction, qubits: tuple[int, ...]) -> QuantumError | None:
        if len(qubits) != 1:
            return None
        return projector.project(params, gate.name, qubits)

    # The concrete strategy already supports ``None`` as "do not install"
    # (the production factory relies on it), while its older ABC annotation
    # still says QuantumError.  Keep that existing interface mismatch local.
    typed_provider = cast(
        Callable[[Instruction, tuple[int, ...]], QuantumError],
        provider,
    )
    return PostGateFuzzification().install(
        circuit.copy(),
        NoiseModel(basis_gates=list(basis)),
        typed_provider,
    )


def _counts_result(
    simulator: AerSimulator,
    circuit: QuantumCircuit,
    noise_model: NoiseModel,
    *,
    shots: int,
    seed: int,
    label: str,
) -> SimulationResult:
    result = simulator.run(
        circuit,
        shots=shots,
        seed_simulator=seed,
        noise_model=noise_model,
    ).result()
    return SimulationResult(
        shots=shots,
        backend_label=label,
        counts=Counter(result.get_counts()),
    )


def _density_result(
    simulator: AerSimulator,
    circuit: QuantumCircuit,
    noise_model: NoiseModel,
    *,
    label: str,
) -> SimulationResult:
    state_circuit = circuit.copy()
    state_circuit.save_density_matrix()
    result = simulator.run(state_circuit, shots=1, noise_model=noise_model).result()
    raw = result.data(0)["density_matrix"]
    data = raw.data if hasattr(raw, "data") else raw
    return SimulationResult(
        shots=1,
        backend_label=label,
        density_matrix=np.asarray(data, dtype=np.complex128),
    )


def _sample_mean_sd(values: Sequence[float]) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    return float(np.mean(array)), float(np.std(array, ddof=1))


def _counts_rows(
    circuit: QuantumCircuit,
    *,
    gamma: float,
    lam: float,
    deltas: tuple[float, ...],
    repeats: int,
    shots: int,
    seed: int,
    basis: tuple[str, ...],
) -> list[ResolutionRow]:
    simulator = AerSimulator()
    prepared_a, model_a = _controlled_model(circuit, gamma=gamma, lam=lam, basis=basis)
    sample_a: list[SimulationResult] = []
    independent_a: list[SimulationResult] = []
    for repeat in range(repeats):
        paired_seed = seed + 2 * repeat
        sample_a.append(
            _counts_result(
                simulator,
                prepared_a,
                model_a,
                shots=shots,
                seed=paired_seed,
                label="A_paired",
            )
        )
        independent_a.append(
            _counts_result(
                simulator,
                prepared_a,
                model_a,
                shots=shots,
                seed=paired_seed + 1,
                label="A_independent",
            )
        )

    metrics: tuple[tuple[str, BenchmarkMetric, Callable[[float], float]], ...] = (
        ("hellinger", HellingerDistance(), lambda value: value),
        ("one_minus_r2", R2Score(), lambda value: 1.0 - value),
    )
    baseline: dict[str, tuple[float, float]] = {}
    for name, metric, orient in metrics:
        values = [
            orient(metric.compute(a, independent))
            for a, independent in zip(sample_a, independent_a, strict=True)
        ]
        baseline[name] = _sample_mean_sd(values)

    rows: list[ResolutionRow] = []
    for delta in deltas:
        prepared_b, model_b = _controlled_model(
            circuit,
            gamma=gamma + delta,
            lam=lam,
            basis=basis,
        )
        if prepared_a != prepared_b:
            raise RuntimeError(
                "controlled A and B preparations transformed the circuit differently"
            )
        sample_b = [
            _counts_result(
                simulator,
                prepared_b,
                model_b,
                shots=shots,
                seed=seed + 2 * repeat,
                label="B_paired",
            )
            for repeat in range(repeats)
        ]
        for name, metric, orient in metrics:
            values = [orient(metric.compute(a, b)) for a, b in zip(sample_a, sample_b, strict=True)]
            between_mean, _between_sd = _sample_mean_sd(values)
            baseline_mean, baseline_sd = baseline[name]
            threshold = baseline_mean + 3.0 * baseline_sd
            rows.append(
                ResolutionRow(
                    circuit=str(circuit.name),
                    mode="counts",
                    metric=name,
                    gamma_a=gamma,
                    lambda_a=lam,
                    gamma_b=gamma + delta,
                    gamma_delta=delta,
                    repeats=repeats,
                    shots=shots,
                    seed=seed,
                    baseline_mean=baseline_mean,
                    baseline_sample_sd=baseline_sd,
                    threshold=threshold,
                    between_mean=between_mean,
                    margin=between_mean - threshold,
                    resolved=between_mean >= threshold,
                    qiskit=qiskit_version,
                    qiskit_aer=qiskit_aer_version,
                )
            )
    return rows


def _density_rows(
    circuit: QuantumCircuit,
    *,
    gamma: float,
    lam: float,
    deltas: tuple[float, ...],
    basis: tuple[str, ...],
) -> list[ResolutionRow]:
    simulator = AerSimulator(method="density_matrix")
    circuit_without_measurements = circuit.remove_final_measurements(inplace=False)
    prepared_a, model_a = _controlled_model(
        circuit_without_measurements,
        gamma=gamma,
        lam=lam,
        basis=basis,
    )
    state_a = _density_result(simulator, prepared_a, model_a, label="A")
    metric = StateFidelity()
    rows: list[ResolutionRow] = []
    for delta in deltas:
        prepared_b, model_b = _controlled_model(
            circuit_without_measurements,
            gamma=gamma + delta,
            lam=lam,
            basis=basis,
        )
        if prepared_a != prepared_b:
            raise RuntimeError(
                "controlled A and B preparations transformed the circuit differently"
            )
        state_b = _density_result(simulator, prepared_b, model_b, label="B")
        discrepancy = 1.0 - metric.compute(state_a, state_b)
        rows.append(
            ResolutionRow(
                circuit=str(circuit.name),
                mode="density_matrix",
                metric="one_minus_state_fidelity",
                gamma_a=gamma,
                lambda_a=lam,
                gamma_b=gamma + delta,
                gamma_delta=delta,
                repeats=1,
                shots=1,
                seed=None,
                baseline_mean=0.0,
                baseline_sample_sd=0.0,
                threshold=_DENSITY_FLOOR,
                between_mean=discrepancy,
                margin=discrepancy - _DENSITY_FLOOR,
                resolved=discrepancy > _DENSITY_FLOOR,
                qiskit=qiskit_version,
                qiskit_aer=qiskit_aer_version,
            )
        )
    return rows


def measure_resolution(
    *,
    gamma: float,
    lam: float,
    deltas: Sequence[float],
    repeats: int,
    shots: int,
    seed: int,
    basis_gates: Sequence[str],
) -> MeasurementResult:
    """Run the two-circuit controlled experiment and return all TSV rows.

    ``repeats`` is the number of independent counts pairs and must be at
    least two because the threshold uses the baseline's sample standard
    deviation (``ddof=1``).  The public inputs are validated without
    clipping.  The function performs local Aer simulations only and has no
    filesystem or network side effects.
    """
    checked_gamma, checked_lam, checked_deltas = _checked_inputs(gamma, lam, deltas, repeats, shots)
    basis = _checked_basis(basis_gates)
    circuits = (qft_circuit(3), ghz_state_circuit(3))
    start = time.perf_counter()
    rows: list[ResolutionRow] = []
    for source_circuit in circuits:
        compiled = transpile(
            source_circuit,
            basis_gates=list(basis),
            optimization_level=_TRANSPILE_OPTIMIZATION_LEVEL,
            seed_transpiler=_TRANSPILE_SEED,
        )
        compiled.name = source_circuit.name
        rows.extend(
            _counts_rows(
                compiled,
                gamma=checked_gamma,
                lam=checked_lam,
                deltas=checked_deltas,
                repeats=repeats,
                shots=shots,
                seed=seed,
                basis=basis,
            )
        )
        rows.extend(
            _density_rows(
                compiled,
                gamma=checked_gamma,
                lam=checked_lam,
                deltas=checked_deltas,
                basis=basis,
            )
        )
    return MeasurementResult(rows=tuple(rows), elapsed_seconds=time.perf_counter() - start)


def smallest_resolved_delta(rows: Sequence[ResolutionRow], mode: Mode) -> float | None:
    """Return the smallest delta resolved by every prescribed cell in ``mode``.

    Missing or duplicate circuit/metric cells are rejected so an incomplete
    TSV can never silently overstate protocol-level resolution.
    """
    required = _REQUIRED_CELLS[mode]
    candidates: list[float] = []
    mode_rows = [row for row in rows if row.mode == mode]
    if not mode_rows:
        raise ValueError(f"no {mode} rows were supplied")
    for delta in sorted({row.gamma_delta for row in mode_rows}):
        delta_rows = [row for row in mode_rows if row.gamma_delta == delta]
        cells = [(row.circuit, row.metric) for row in delta_rows]
        if len(cells) != len(set(cells)):
            raise ValueError(f"duplicate {mode} cells at delta {delta}")
        if set(cells) != required:
            raise ValueError(
                f"incomplete {mode} cells at delta {delta}: expected {sorted(required)}, "
                f"got {sorted(cells)}"
            )
        if all(row.resolved for row in delta_rows):
            candidates.append(delta)
    return min(candidates) if candidates else None


def _formatted_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return format(value, ".17g")
    if value is None:
        return "NA"
    return str(value)


def write_tsv(path: Path, rows: Sequence[ResolutionRow]) -> None:
    """Write ``rows`` as a deterministic UTF-8 TSV, replacing ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    field_names = [field.name for field in fields(ResolutionRow)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field_name: _formatted_value(getattr(row, field_name))
                    for field_name in field_names
                }
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gamma", type=float, required=True, help="model A amplitude damping")
    parser.add_argument("--lambda", dest="lam", type=float, required=True, help="phase damping")
    parser.add_argument(
        "--deltas", type=float, nargs="+", required=True, help="positive gamma ladder"
    )
    parser.add_argument("--repeats", type=int, required=True, help="independent counts pairs")
    parser.add_argument("--shots", type=int, required=True, help="shots per counts sample")
    parser.add_argument("--seed", type=int, required=True, help="first simulator seed")
    parser.add_argument(
        "--basis-gates",
        required=True,
        help="comma-separated explicit device basis",
    )
    parser.add_argument("--output", type=Path, required=True, help="TSV output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, run the measurement, write its TSV, and summarize."""
    args = _parser().parse_args(argv)
    basis = tuple(name.strip() for name in args.basis_gates.split(","))
    result = measure_resolution(
        gamma=args.gamma,
        lam=args.lam,
        deltas=args.deltas,
        repeats=args.repeats,
        shots=args.shots,
        seed=args.seed,
        basis_gates=basis,
    )
    write_tsv(args.output, result.rows)
    for mode in ("counts", "density_matrix"):
        resolved = smallest_resolved_delta(result.rows, mode)
        conclusion = "not resolved on ladder" if resolved is None else format(resolved, ".17g")
        print(f"{mode}: {conclusion}")
    print(f"rows: {len(result.rows)}")
    print(f"elapsed_seconds: {result.elapsed_seconds:.6f}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
