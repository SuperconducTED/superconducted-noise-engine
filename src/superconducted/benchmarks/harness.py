"""Certified benchmark harness for engine-versus-reference comparisons.

Bootstrap status: full. Every circuit is transpiled once to an explicit
device basis before either the fuzzy engine or the reference model sees
it. Aggregates ensemble counts (across members) by element-wise sum,
retaining the total shot count so metric functions normalize correctly,
into a single :class:`SimulationResult` per circuit
— probability-equivalent to a mean of per-member distributions under
those normalized metrics. Density matrices are mixed with the arithmetic
mean, ``rho_ens = (1 / N) sum_m rho_m``. Interval-valued aggregation
across ensemble members is deferred to ADR-016.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import CONTROL_FLOW_OP_NAMES
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel

from ..integration.aer_factory import FuzzyNoiseModelEnsemble
from ..interfaces import BenchmarkMetric
from ..types import SimulationResult

SimulationMode = Literal["counts", "density_matrix"]
ErrorMode = Literal["raise", "record"]

_TRANSPILE_OPTIMIZATION_LEVEL = 1
_TRANSPILE_SEED = 0
# Operations that make a density-matrix run a sampled branch rather than the
# exact state: a measurement that is not final collapses it, and control flow
# can branch on that outcome.
_NOT_EXACT_IN_DENSITY_MODE = frozenset({"measure", *CONTROL_FLOW_OP_NAMES})


@dataclass(frozen=True)
class BenchmarkRow:
    """One row of the benchmark results table.

    ``engine_value`` is ``metric.compute(engine, reference)`` and
    ``reference_value`` is the metric's self-similarity baseline. ``delta``
    is their difference. With ``on_error="record"``, a handled metric error
    makes all three numeric fields NaN and ``failure`` records its origin and
    exception text. The default ``on_error="raise"`` never emits such a row.
    """

    circuit_name: str
    metric_name: str
    engine_value: float
    reference_value: float
    delta: float
    failure: str | None = None


def _circuit_name(circuit: QuantumCircuit) -> str:
    name = getattr(circuit, "name", None)
    return str(name) if name else "circuit"


def _validate_mode(mode: str) -> SimulationMode:
    if mode not in ("counts", "density_matrix"):
        raise ValueError(f"mode must be 'counts' or 'density_matrix'; got {mode!r}")
    return mode  # type: ignore[return-value]


def _validate_error_mode(on_error: str) -> ErrorMode:
    if on_error not in ("raise", "record"):
        raise ValueError(f"on_error must be 'raise' or 'record'; got {on_error!r}")
    return on_error  # type: ignore[return-value]


def _validate_basis(basis_gates: Sequence[str]) -> tuple[str, ...]:
    basis = tuple(basis_gates)
    if not basis:
        raise ValueError("basis_gates must contain at least one gate name")
    if any(not isinstance(name, str) or not name for name in basis):
        raise ValueError("basis_gates must contain only non-empty strings")
    return basis


def _validate_shots(shots: int, *, name: str = "shots") -> int:
    if shots <= 0:
        raise ValueError(f"{name} must be positive; got {shots}")
    return shots


def _transpile_circuits(
    circuits: Sequence[QuantumCircuit], basis_gates: Sequence[str]
) -> tuple[list[QuantumCircuit], tuple[str, ...]]:
    basis = _validate_basis(basis_gates)
    compiled = [
        transpile(
            circuit,
            basis_gates=list(basis),
            optimization_level=_TRANSPILE_OPTIMIZATION_LEVEL,
            seed_transpiler=_TRANSPILE_SEED,
        )
        for circuit in circuits
    ]
    return compiled, basis


def _state_circuit(circuit: QuantumCircuit) -> QuantumCircuit:
    """Drop final measurements, refusing what density mode cannot evolve exactly."""
    state_circuit = circuit.remove_final_measurements(inplace=False)
    left = sorted(
        {instruction.operation.name for instruction in state_circuit.data}
        & _NOT_EXACT_IN_DENSITY_MODE
    )
    if left:
        raise ValueError(
            f"density_matrix mode needs a circuit whose only measurements are final; "
            f"{_circuit_name(circuit)!r} still contains {left}"
        )
    return state_circuit


def _density_matrix(result: Any) -> npt.NDArray[np.complex128]:
    raw = result.data(0)["density_matrix"]
    data = raw.data if hasattr(raw, "data") else raw
    return np.asarray(data, dtype=np.complex128)


def _run_engine_transpiled(
    circuits: Sequence[QuantumCircuit],
    ensemble: FuzzyNoiseModelEnsemble,
    *,
    basis: tuple[str, ...],
    mode: SimulationMode,
    shots: int,
    seed: int | None,
) -> list[SimulationResult]:
    members = list(ensemble)
    if not members:
        raise ValueError("Cannot simulate with an empty ensemble")

    sim = AerSimulator(method="density_matrix") if mode == "density_matrix" else AerSimulator()
    out: list[SimulationResult] = []
    for circuit in circuits:
        noise_instructions: list[list[str]] = []
        if mode == "counts":
            member_counts: list[Counter[str]] = []
            for member_index, member in enumerate(members):
                prepared_circuit, prepared_noise = member.prepare(circuit.copy())
                noise_instructions.append(sorted(prepared_noise.noise_instructions))
                run_options: dict[str, Any] = {
                    "shots": shots,
                    "noise_model": prepared_noise,
                }
                if seed is not None:
                    run_options["seed_simulator"] = seed + member_index
                result = sim.run(prepared_circuit, **run_options).result()
                member_counts.append(Counter(result.get_counts()))

            aggregate: Counter[str] = Counter()
            for counts in member_counts:
                aggregate.update(counts)
            out.append(
                SimulationResult(
                    shots=shots * len(members),
                    backend_label="engine",
                    counts=aggregate,
                    metadata={
                        "mode": mode,
                        "ensemble_size": len(members),
                        "circuit_name": _circuit_name(circuit),
                        "basis_gates": basis,
                        "noise_instructions": noise_instructions,
                    },
                )
            )
            continue

        state_circuit = _state_circuit(circuit)
        member_states: list[npt.NDArray[np.complex128]] = []
        for member in members:
            prepared_circuit, prepared_noise = member.prepare(state_circuit.copy())
            noise_instructions.append(sorted(prepared_noise.noise_instructions))
            prepared_circuit.save_density_matrix()
            result = sim.run(prepared_circuit, shots=1, noise_model=prepared_noise).result()
            member_states.append(_density_matrix(result))
        first_state = member_states[0]
        if all(np.array_equal(first_state, state) for state in member_states[1:]):
            aggregate_state = first_state.copy()
        else:
            aggregate_state = np.asarray(
                np.mean(np.stack(member_states, axis=0), axis=0, dtype=np.complex128),
                dtype=np.complex128,
            )
        out.append(
            SimulationResult(
                shots=1,
                backend_label="engine",
                density_matrix=aggregate_state,
                metadata={
                    "mode": mode,
                    "ensemble_size": len(members),
                    "circuit_name": _circuit_name(circuit),
                    "basis_gates": basis,
                    "noise_instructions": noise_instructions,
                },
            )
        )
    return out


def _run_reference_transpiled(
    circuits: Sequence[QuantumCircuit],
    reference_noise: NoiseModel,
    *,
    basis: tuple[str, ...],
    mode: SimulationMode,
    shots: int,
    seed: int | None,
) -> list[SimulationResult]:
    sim = AerSimulator(method="density_matrix") if mode == "density_matrix" else AerSimulator()
    noise_instructions = sorted(reference_noise.noise_instructions)
    out: list[SimulationResult] = []
    for circuit in circuits:
        metadata: dict[str, Any] = {
            "mode": mode,
            "ensemble_size": 1,
            "circuit_name": _circuit_name(circuit),
            "basis_gates": basis,
            # A copy per circuit, so a caller editing one result's metadata
            # cannot change another's.
            "noise_instructions": list(noise_instructions),
        }
        if mode == "counts":
            run_options: dict[str, Any] = {
                "shots": shots,
                "noise_model": reference_noise,
            }
            if seed is not None:
                run_options["seed_simulator"] = seed
            result = sim.run(circuit.copy(), **run_options).result()
            out.append(
                SimulationResult(
                    shots=shots,
                    backend_label="reference",
                    counts=Counter(result.get_counts()),
                    metadata=metadata,
                )
            )
            continue

        state_circuit = _state_circuit(circuit)
        state_circuit.save_density_matrix()
        result = sim.run(state_circuit, shots=1, noise_model=reference_noise).result()
        out.append(
            SimulationResult(
                shots=1,
                backend_label="reference",
                density_matrix=_density_matrix(result),
                metadata=metadata,
            )
        )
    return out


def simulate_engine(
    circuits: Sequence[QuantumCircuit],
    ensemble: FuzzyNoiseModelEnsemble,
    *,
    basis_gates: Sequence[str],
    mode: SimulationMode = "counts",
    shots: int = 4096,
    seed: int | None = None,
) -> list[SimulationResult]:
    """Simulate every circuit through every engine member.

    Circuits are transpiled once to ``basis_gates`` before ``prepare``. Counts
    are summed and carry ``shots * ensemble_size`` total shots. Density
    matrices are prepared before the save instruction is appended, averaged
    as a convex mixture, and carry ``shots=1`` because no sampling occurred.
    Density mode raises ``ValueError`` for a circuit with a measurement that is
    not final or with control flow, since its state would be a sampled branch.

    Seeds: in counts mode member ``i`` runs at ``seed_simulator = seed + i``;
    ``seed=None`` leaves every member unseeded. Density mode does not sample, so
    ``seed`` has no effect there. The transpiler seed is fixed separately.

    Each result's ``metadata`` holds ``mode``, ``ensemble_size``,
    ``circuit_name``, ``basis_gates`` (the compiled basis) and
    ``noise_instructions``: one sorted list per member of the gate names that
    member's prepared ``NoiseModel`` carries.
    """
    checked_mode = _validate_mode(mode)
    checked_shots = _validate_shots(shots)
    compiled, basis = _transpile_circuits(circuits, basis_gates)
    return _run_engine_transpiled(
        compiled,
        ensemble,
        basis=basis,
        mode=checked_mode,
        shots=checked_shots,
        seed=seed,
    )


def simulate_reference(
    circuits: Sequence[QuantumCircuit],
    reference_noise: NoiseModel,
    *,
    basis_gates: Sequence[str],
    mode: SimulationMode = "counts",
    shots: int = 4096,
    seed: int | None = None,
) -> list[SimulationResult]:
    """Simulate every circuit once against ``reference_noise``.

    The explicit basis prevents Aer defaults from silently selecting a gate
    set on which the supplied noise model has no effect. Density mode removes
    final measurements and therefore does not apply readout errors; it raises
    ``ValueError`` for a measurement that is not final or for control flow.

    Seeds: counts mode runs at ``seed_simulator = seed`` (so a one-member
    engine and the reference share a seed); ``seed=None`` is unseeded; density
    mode ignores ``seed``.

    Each result's ``metadata`` holds the same keys as :func:`simulate_engine`,
    with ``ensemble_size`` 1 and ``noise_instructions`` a single sorted list of
    the gate names ``reference_noise`` carries, copied per circuit.
    """
    checked_mode = _validate_mode(mode)
    checked_shots = _validate_shots(shots)
    compiled, basis = _transpile_circuits(circuits, basis_gates)
    return _run_reference_transpiled(
        compiled,
        reference_noise,
        basis=basis,
        mode=checked_mode,
        shots=checked_shots,
        seed=seed,
    )


def run_benchmark(
    circuits: Sequence[QuantumCircuit],
    ensemble: FuzzyNoiseModelEnsemble,
    reference_noise: NoiseModel,
    metrics: Sequence[BenchmarkMetric],
    *,
    basis_gates: Sequence[str] | None = None,
    mode: SimulationMode = "counts",
    shots: int = 4096,
    seed: int | None = None,
    reference_shots: int | None = None,
    on_error: ErrorMode = "raise",
) -> list[BenchmarkRow]:
    """Run the engine and reference over one shared transpilation.

    ``basis_gates`` defaults to the reference model's device basis. Counts
    mode optionally gives the reference a distinct per-run shot count through
    ``reference_shots``. ``seed`` follows :func:`simulate_engine` for the
    engine and :func:`simulate_reference` for the reference.

    ``on_error`` covers only ``ValueError`` and ``ZeroDivisionError`` from a
    metric: ``"raise"`` (the default) propagates them, ``"record"`` returns a
    row whose three values are NaN and whose ``failure`` names the side and the
    exception, instead of a silent NaN. Any other exception propagates, and an
    unknown ``on_error`` raises ``ValueError``.
    """
    checked_mode = _validate_mode(mode)
    checked_error_mode = _validate_error_mode(on_error)
    checked_shots = _validate_shots(shots)
    checked_reference_shots = _validate_shots(
        shots if reference_shots is None else reference_shots,
        name="reference_shots",
    )
    target_basis = reference_noise.basis_gates if basis_gates is None else basis_gates
    compiled, basis = _transpile_circuits(circuits, target_basis)
    engine_results = _run_engine_transpiled(
        compiled,
        ensemble,
        basis=basis,
        mode=checked_mode,
        shots=checked_shots,
        seed=seed,
    )
    reference_results = _run_reference_transpiled(
        compiled,
        reference_noise,
        basis=basis,
        mode=checked_mode,
        shots=checked_reference_shots,
        seed=seed,
    )

    rows: list[BenchmarkRow] = []
    for circuit, engine_result, reference_result in zip(
        circuits, engine_results, reference_results, strict=True
    ):
        circ_name = _circuit_name(circuit)
        for metric in metrics:
            engine_value, engine_failure = _try_compute(
                metric,
                engine_result,
                reference_result,
                on_error=checked_error_mode,
            )
            reference_value, reference_failure = _try_compute(
                metric,
                reference_result,
                reference_result,
                on_error=checked_error_mode,
            )
            failures = [
                f"{label}: {failure}"
                for label, failure in (
                    ("engine", engine_failure),
                    ("reference", reference_failure),
                )
                if failure is not None
            ]
            if failures:
                engine_value = reference_value = delta = float("nan")
            else:
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
                    failure="; ".join(failures) if failures else None,
                )
            )
    return rows


def _try_compute(
    metric: BenchmarkMetric,
    a: SimulationResult,
    b: SimulationResult,
    *,
    on_error: ErrorMode = "raise",
) -> tuple[float, str | None]:
    """Compute one metric, raising or recording only its declared data errors."""
    checked_error_mode = _validate_error_mode(on_error)
    try:
        return float(metric.compute(a, b)), None
    except (ValueError, ZeroDivisionError) as exc:
        if checked_error_mode == "raise":
            raise
        return float("nan"), f"{type(exc).__name__}: {exc}"
