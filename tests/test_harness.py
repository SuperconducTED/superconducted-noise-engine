"""Regression tests for the three benchmark-harness defects in issue #58."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from itertools import pairwise
from typing import Any, cast

import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerError, AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error

from superconducted.benchmarks.circuits import (
    ghz_state_circuit,
    qft_circuit,
    random_clifford_circuit,
    vqe_ansatz_circuit,
)
from superconducted.benchmarks.harness import (
    _try_compute,
    run_benchmark,
    simulate_engine,
    simulate_reference,
)
from superconducted.benchmarks.metrics import (
    HellingerDistance,
    KLDivergence,
    R2Score,
    StateFidelity,
)
from superconducted.benchmarks.reference import build_reference
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.interfaces import BenchmarkMetric
from superconducted.types import CalibrationSnapshot, SimulationResult


class _ValueErrorMetric(BenchmarkMetric):
    @property
    def name(self) -> str:
        return "value_error"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        raise ValueError("deliberate metric failure")


class _ZeroDivisionMetric(BenchmarkMetric):
    @property
    def name(self) -> str:
        return "zero_division"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        raise ZeroDivisionError("deliberate zero denominator")


class _RuntimeErrorMetric(BenchmarkMetric):
    @property
    def name(self) -> str:
        return "runtime_error"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        raise RuntimeError("deliberate runtime failure")


class _ConstantMetric(BenchmarkMetric):
    @property
    def name(self) -> str:
        return "constant"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        return 0.25


class _ShotCaptureMetric(BenchmarkMetric):
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    @property
    def name(self) -> str:
        return "shot_capture"

    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
        self.calls.append((engine.shots, reference.shots))
        return 0.0


class _StaticMember:
    def __init__(self, noise_model: NoiseModel) -> None:
        self._noise_model = noise_model

    def prepare(self, circuit: QuantumCircuit) -> tuple[QuantumCircuit, NoiseModel]:
        return circuit, self._noise_model


class _StaticEnsemble:
    def __init__(self, *noise_models: NoiseModel) -> None:
        self._members = tuple(_StaticMember(model) for model in noise_models)

    def __iter__(self) -> Iterator[_StaticMember]:
        return iter(self._members)

    def __len__(self) -> int:
        return len(self._members)


def _as_ensemble(*noise_models: NoiseModel) -> FuzzyNoiseModelEnsemble:
    return cast(FuzzyNoiseModelEnsemble, _StaticEnsemble(*noise_models))


DEVICE_BASIS = ("cz", "id", "rx", "rz", "sx", "x")


def test_state_fidelity_rows_are_nan_without_density_mode(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    """Fix 7d39a2b: the state path returns finite fidelity rather than three silent NaNs."""
    rows = run_benchmark(
        [ghz_state_circuit(2)],
        benchmark_ensemble,
        NoiseModel(),
        [StateFidelity()],
        mode="density_matrix",
        shots=64,
    )

    assert len(rows) == 1
    assert math.isfinite(rows[0].engine_value)
    assert rows[0].reference_value == pytest.approx(1.0)
    assert math.isfinite(rows[0].delta)
    assert rows[0].failure is None


def test_qft_crashes_untranspiled() -> None:
    """Fix 7d39a2b: the harness decomposes QFT before submitting it to Aer."""
    noise_model = NoiseModel()

    try:
        results = simulate_reference(
            [qft_circuit(3)], noise_model, basis_gates=noise_model.basis_gates, shots=64
        )
    except AerError as exc:  # pragma: no cover - regression diagnostic
        pytest.fail(f"issue #58: QFT was not transpiled to the explicit basis: {exc}")

    assert len(results) == 1
    assert results[0].counts is not None


def test_try_compute_swallows_errors_silently() -> None:
    """Fix 7d39a2b: a metric ValueError raises by default or has an explicit record."""
    result = SimulationResult(shots=1, backend_label="test", counts={"0": 1})

    with pytest.raises(ValueError, match="deliberate metric failure"):
        _try_compute(_ValueErrorMetric(), result, result)

    value, failure = _try_compute(_ValueErrorMetric(), result, result, on_error="record")

    assert math.isnan(value)
    assert failure == "ValueError: deliberate metric failure"


@pytest.mark.parametrize(
    ("metric", "message"),
    [
        (_ValueErrorMetric(), "deliberate metric failure"),
        (_ZeroDivisionMetric(), "deliberate zero denominator"),
    ],
    ids=("value-error", "zero-division"),
)
def test_try_compute_raise_and_record_branches(metric: BenchmarkMetric, message: str) -> None:
    result = SimulationResult(shots=1, backend_label="test", counts={"0": 1})

    with pytest.raises((ValueError, ZeroDivisionError), match=message):
        _try_compute(metric, result, result)

    value, failure = _try_compute(metric, result, result, on_error="record")
    assert math.isnan(value)
    assert failure is not None and message in failure


def test_try_compute_propagates_unhandled_exceptions() -> None:
    result = SimulationResult(shots=1, backend_label="test", counts={"0": 1})

    with pytest.raises(RuntimeError, match="deliberate runtime failure"):
        _try_compute(_RuntimeErrorMetric(), result, result, on_error="record")


def test_record_mode_marks_the_entire_row_and_continues(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    rows = run_benchmark(
        [ghz_state_circuit(2)],
        benchmark_ensemble,
        NoiseModel(basis_gates=list(DEVICE_BASIS)),
        [_ValueErrorMetric(), _ConstantMetric()],
        shots=32,
        seed=7,
        on_error="record",
    )

    assert len(rows) == 2
    failed, succeeded = rows
    assert all(
        math.isnan(value) for value in (failed.engine_value, failed.reference_value, failed.delta)
    )
    assert failed.failure is not None
    assert "engine: ValueError: deliberate metric failure" in failed.failure
    assert "reference: ValueError: deliberate metric failure" in failed.failure
    assert succeeded.failure is None
    assert succeeded.engine_value == succeeded.reference_value == 0.25
    assert succeeded.delta == 0.0


def test_run_benchmark_transpiles_once_and_defaults_to_reference_basis(
    monkeypatch: pytest.MonkeyPatch,
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    calls: list[dict[str, Any]] = []
    original_transpile = transpile

    def spy_transpile(circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        calls.append(kwargs)
        return original_transpile(circuit, **kwargs)

    monkeypatch.setattr("superconducted.benchmarks.harness.transpile", spy_transpile)
    reference = NoiseModel(basis_gates=list(DEVICE_BASIS))

    run_benchmark(
        [ghz_state_circuit(2)],
        benchmark_ensemble,
        reference,
        [HellingerDistance()],
        shots=32,
        seed=5,
    )

    assert len(calls) == 1
    assert calls[0]["basis_gates"] == reference.basis_gates
    assert calls[0]["optimization_level"] == 1
    assert calls[0]["seed_transpiler"] == 0
    assert "backend" not in calls[0]
    assert "coupling_map" not in calls[0]


def test_public_simulators_require_an_explicit_basis(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    circuit = ghz_state_circuit(2)

    with pytest.raises(TypeError, match="basis_gates"):
        simulate_engine([circuit], benchmark_ensemble)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="basis_gates"):
        simulate_reference([circuit], NoiseModel())  # type: ignore[call-arg]


@pytest.mark.parametrize("mode", ["counts", "density_matrix"])
@pytest.mark.parametrize("circuit_name", ["qft", "vqe"])
def test_qft_and_vqe_run_in_both_modes(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
    mode: str,
    circuit_name: str,
) -> None:
    circuit = (
        qft_circuit(3)
        if circuit_name == "qft"
        else vqe_ansatz_circuit(3, rng=np.random.default_rng(0))
    )
    reference = NoiseModel(basis_gates=list(DEVICE_BASIS))

    engine_result = simulate_engine(
        [circuit],
        benchmark_ensemble,
        basis_gates=DEVICE_BASIS,
        mode=mode,  # type: ignore[arg-type]
        shots=32,
        seed=11,
    )[0]
    reference_result = simulate_reference(
        [circuit],
        reference,
        basis_gates=DEVICE_BASIS,
        mode=mode,  # type: ignore[arg-type]
        shots=32,
        seed=11,
    )[0]

    if mode == "counts":
        assert engine_result.counts is not None
        assert reference_result.counts is not None
    else:
        assert engine_result.density_matrix is not None
        assert reference_result.density_matrix is not None


def test_transpiled_qft_installs_only_executed_noise_instructions(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    circuit = qft_circuit(3)
    compiled = transpile(
        circuit,
        basis_gates=list(DEVICE_BASIS),
        optimization_level=1,
        seed_transpiler=0,
    )
    result = simulate_engine(
        [circuit], benchmark_ensemble, basis_gates=DEVICE_BASIS, shots=32, seed=17
    )[0]

    assert result.metadata is not None
    per_member = result.metadata["noise_instructions"]
    assert len(per_member) == 1
    assert per_member[0]
    assert set(per_member[0]) <= set(compiled.count_ops())
    assert per_member[0] == sorted(per_member[0])


def test_density_mode_prepares_before_save_instruction(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    # On one qubit the current projector would accept save_density_matrix if
    # the harness appended it before prepare(), so this is a causal ordering
    # pin rather than merely an assertion that also passes on a 3-qubit save.
    result = simulate_engine(
        [qft_circuit(1)],
        benchmark_ensemble,
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]

    assert result.metadata is not None
    assert all(
        "save_density_matrix" not in instructions
        for instructions in result.metadata["noise_instructions"]
    )


def test_sx_only_noise_fires_through_explicit_basis() -> None:
    """Certify issue #58 step 6: a registered sx error changes executed QFT counts."""
    strong_error = thermal_relaxation_error(1e-6, 2e-6, 24e-9)
    noisy = NoiseModel(basis_gates=list(DEVICE_BASIS))
    for q in range(3):
        noisy.add_quantum_error(strong_error, "sx", [q])
    noiseless = NoiseModel(basis_gates=list(DEVICE_BASIS))
    circuit = qft_circuit(3)

    baseline = simulate_reference(
        [circuit], noiseless, basis_gates=DEVICE_BASIS, shots=8192, seed=123
    )[0]
    perturbed = simulate_reference(
        [circuit], noisy, basis_gates=DEVICE_BASIS, shots=8192, seed=123
    )[0]

    assert baseline.counts is not None and perturbed.counts is not None
    assert baseline.counts != perturbed.counts
    support = set(baseline.counts) | set(perturbed.counts)
    assert sum(abs(baseline.counts[key] - perturbed.counts[key]) for key in support) > 0


def test_density_result_is_physical_and_uses_one_semantic_shot(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    result = simulate_engine(
        [qft_circuit(3)],
        benchmark_ensemble,
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]
    rho = result.density_matrix

    assert rho is not None
    assert result.counts is None
    assert result.shots == 1
    assert np.trace(rho) == pytest.approx(1.0, abs=1e-12)
    assert np.max(np.abs(rho - rho.conj().T)) <= 1e-12
    assert np.min(np.linalg.eigvalsh(rho)) >= -1e-12


def test_identical_members_preserve_density_matrix_exactly() -> None:
    model = NoiseModel(basis_gates=list(DEVICE_BASIS))
    circuit = ghz_state_circuit(2)
    single = simulate_engine(
        [circuit],
        _as_ensemble(model),
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]
    mixture = simulate_engine(
        [circuit],
        _as_ensemble(model, model, model),
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]

    assert single.density_matrix is not None and mixture.density_matrix is not None
    assert np.array_equal(mixture.density_matrix, single.density_matrix)
    assert mixture.shots == 1


def test_distinct_members_form_arithmetic_density_mixture() -> None:
    noiseless = NoiseModel(basis_gates=["x"])
    noisy = NoiseModel(basis_gates=["x"])
    noisy.add_quantum_error(depolarizing_error(0.4, 1), "x", [0])
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()

    rho_a = simulate_reference([circuit], noiseless, basis_gates=["x"], mode="density_matrix")[
        0
    ].density_matrix
    rho_b = simulate_reference([circuit], noisy, basis_gates=["x"], mode="density_matrix")[
        0
    ].density_matrix
    mixture = simulate_engine(
        [circuit],
        _as_ensemble(noiseless, noisy),
        basis_gates=["x"],
        mode="density_matrix",
    )[0].density_matrix

    assert rho_a is not None and rho_b is not None and mixture is not None
    assert np.array_equal(mixture, (rho_a + rho_b) / 2.0)


def test_density_mode_is_bit_deterministic_on_one_machine(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    kwargs = {
        "basis_gates": DEVICE_BASIS,
        "mode": "density_matrix",
        "shots": 32,
        "seed": 1,
    }
    first = simulate_engine([qft_circuit(3)], benchmark_ensemble, **kwargs)[0]  # type: ignore[arg-type]
    second = simulate_engine([qft_circuit(3)], benchmark_ensemble, **kwargs)[0]  # type: ignore[arg-type]

    assert first.density_matrix is not None and second.density_matrix is not None
    assert np.array_equal(first.density_matrix, second.density_matrix)


def test_counts_seed_derivation_and_none_semantics(
    monkeypatch: pytest.MonkeyPatch,
    make_benchmark_ensemble: Callable[[int], FuzzyNoiseModelEnsemble],
) -> None:
    calls: list[dict[str, Any]] = []
    original_run = AerSimulator.run

    def spy_run(self: AerSimulator, *args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return original_run(self, *args, **kwargs)

    monkeypatch.setattr(AerSimulator, "run", spy_run)
    ensemble = make_benchmark_ensemble(3)
    reference = NoiseModel(basis_gates=list(DEVICE_BASIS))

    run_benchmark(
        [ghz_state_circuit(2)],
        ensemble,
        reference,
        [HellingerDistance()],
        shots=16,
        seed=40,
    )
    assert [call["seed_simulator"] for call in calls] == [40, 41, 42, 40]

    calls.clear()
    run_benchmark(
        [ghz_state_circuit(2)],
        ensemble,
        reference,
        [HellingerDistance()],
        shots=16,
        seed=None,
    )
    assert all("seed_simulator" not in call for call in calls)


def test_same_seed_repeats_counts_exactly(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    first = simulate_engine(
        [qft_circuit(3)], benchmark_ensemble, basis_gates=DEVICE_BASIS, shots=128, seed=91
    )[0]
    second = simulate_engine(
        [qft_circuit(3)], benchmark_ensemble, basis_gates=DEVICE_BASIS, shots=128, seed=91
    )[0]

    assert first.counts == second.counts


def test_reference_shots_override_changes_only_reference_total(
    make_benchmark_ensemble: Callable[[int], FuzzyNoiseModelEnsemble],
) -> None:
    metric = _ShotCaptureMetric()
    run_benchmark(
        [ghz_state_circuit(2)],
        make_benchmark_ensemble(3),
        NoiseModel(basis_gates=list(DEVICE_BASIS)),
        [metric],
        shots=32,
        reference_shots=17,
        seed=3,
    )

    assert metric.calls == [(96, 17), (17, 17)]


def test_noise_instruction_metadata_shape_in_both_modes(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    reference = NoiseModel(basis_gates=list(DEVICE_BASIS))
    reference.add_quantum_error(depolarizing_error(0.1, 1), "sx", [0])
    for mode in ("counts", "density_matrix"):
        engine = simulate_engine(
            [qft_circuit(2)],
            benchmark_ensemble,
            basis_gates=DEVICE_BASIS,
            mode=mode,
            shots=16,
            seed=2,
        )[0]
        ref = simulate_reference(
            [qft_circuit(2)],
            reference,
            basis_gates=DEVICE_BASIS,
            mode=mode,
            shots=16,
            seed=2,
        )[0]

        assert engine.metadata is not None and ref.metadata is not None
        assert engine.metadata["mode"] == ref.metadata["mode"] == mode
        assert isinstance(engine.metadata["noise_instructions"], list)
        assert isinstance(engine.metadata["noise_instructions"][0], list)
        assert ref.metadata["noise_instructions"] == ["sx"]
        assert engine.metadata["basis_gates"] == ref.metadata["basis_gates"] == DEVICE_BASIS


def _depolarizing_fidelity(p: float) -> float:
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    noisy = NoiseModel(basis_gates=["x"])
    noisy.add_quantum_error(depolarizing_error(p, 1), "x", [0])
    rows = run_benchmark(
        [circuit],
        _as_ensemble(noisy),
        NoiseModel(basis_gates=["x"]),
        [StateFidelity()],
        mode="density_matrix",
    )
    return rows[0].engine_value


def test_density_adr022_identity() -> None:
    assert _depolarizing_fidelity(0.0) == pytest.approx(1.0, abs=1e-12)


def test_density_adr022_symmetry() -> None:
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    model_a = NoiseModel(basis_gates=["x"])
    model_b = NoiseModel(basis_gates=["x"])
    model_b.add_quantum_error(depolarizing_error(0.4, 1), "x", [0])

    ab = run_benchmark(
        [circuit], _as_ensemble(model_a), model_b, [StateFidelity()], mode="density_matrix"
    )[0].engine_value
    ba = run_benchmark(
        [circuit], _as_ensemble(model_b), model_a, [StateFidelity()], mode="density_matrix"
    )[0].engine_value
    assert ab == pytest.approx(ba, abs=1e-12)


def test_density_adr022_bounds() -> None:
    for p in (0.0, 0.2, 0.7, 1.0):
        assert 0.0 <= _depolarizing_fidelity(p) <= 1.0


def test_density_adr022_monotonicity() -> None:
    fidelities = [_depolarizing_fidelity(p) for p in (0.0, 0.2, 0.7, 1.0)]
    assert all(left >= right for left, right in pairwise(fidelities))


def test_density_adr022_determinism() -> None:
    assert _depolarizing_fidelity(0.37) == _depolarizing_fidelity(0.37)


def test_density_adr022_reference_value() -> None:
    p = 0.37
    assert _depolarizing_fidelity(p) == pytest.approx(1.0 - p / 2.0, abs=1e-12)


def test_counts_adr022_monotonicity() -> None:
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    distances: list[float] = []
    for p in (0.0, 0.3, 0.8):
        model = NoiseModel(basis_gates=["x"])
        if p:
            model.add_quantum_error(depolarizing_error(p, 1), "x", [0])
        row = run_benchmark(
            [circuit],
            _as_ensemble(model),
            NoiseModel(basis_gates=["x"]),
            [HellingerDistance()],
            shots=20_000,
            seed=13,
        )[0]
        distances.append(row.engine_value)
    assert distances[0] <= distances[1] <= distances[2]


def test_counts_adr022_determinism() -> None:
    model = NoiseModel(basis_gates=["x"])
    model.add_quantum_error(depolarizing_error(0.4, 1), "x", [0])
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    kwargs = {"shots": 1024, "seed": 77}

    first = run_benchmark(
        [circuit],
        _as_ensemble(model),
        NoiseModel(basis_gates=["x"]),
        [HellingerDistance()],
        **kwargs,
    )[0]
    second = run_benchmark(
        [circuit],
        _as_ensemble(model),
        NoiseModel(basis_gates=["x"]),
        [HellingerDistance()],
        **kwargs,
    )[0]
    assert first == second


def test_counts_adr022_reference_value() -> None:
    p = 0.4
    model = NoiseModel(basis_gates=["x"])
    model.add_quantum_error(depolarizing_error(p, 1), "x", [0])
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    row = run_benchmark(
        [circuit],
        _as_ensemble(model),
        NoiseModel(basis_gates=["x"]),
        [HellingerDistance()],
        shots=100_000,
        seed=101,
    )[0]

    expected = math.sqrt(1.0 - math.sqrt(1.0 - p / 2.0))
    assert row.engine_value == pytest.approx(expected, abs=0.01)


@pytest.mark.slow
def test_all_four_circuits_produce_finite_mode_appropriate_rows(
    benchmark_ensemble: FuzzyNoiseModelEnsemble,
) -> None:
    circuits = [
        random_clifford_circuit(3, 2, rng=np.random.default_rng(0)),
        ghz_state_circuit(3),
        qft_circuit(3),
        vqe_ansatz_circuit(3, rng=np.random.default_rng(0)),
    ]
    reference = NoiseModel(basis_gates=list(DEVICE_BASIS))
    counts_rows = run_benchmark(
        circuits,
        benchmark_ensemble,
        reference,
        [HellingerDistance(), KLDivergence(), R2Score()],
        shots=128,
        seed=29,
    )
    state_rows = run_benchmark(
        circuits,
        benchmark_ensemble,
        reference,
        [StateFidelity()],
        mode="density_matrix",
    )

    assert len(counts_rows) == 12
    assert len(state_rows) == 4
    assert all(row.failure is None for row in [*counts_rows, *state_rows])
    assert all(
        math.isfinite(value)
        for row in [*counts_rows, *state_rows]
        for value in (row.engine_value, row.reference_value, row.delta)
    )
    assert [row.reference_value for row in counts_rows] == pytest.approx([0.0, 0.0, 1.0] * 4)
    assert [row.reference_value for row in state_rows] == pytest.approx([1.0] * 4)


@pytest.mark.slow
def test_issue_57_fixture_four_circuit_reference_integration(
    issue_57_gates_snapshot: CalibrationSnapshot,
    make_benchmark_ensemble: Callable[..., FuzzyNoiseModelEnsemble],
) -> None:
    """Run the required 12+4 rows against #57's physical reference after it lands."""
    circuits = [
        random_clifford_circuit(3, 2, rng=np.random.default_rng(0)),
        ghz_state_circuit(3),
        qft_circuit(3),
        vqe_ansatz_circuit(3, rng=np.random.default_rng(0)),
    ]
    ensemble = make_benchmark_ensemble(1, snapshot=issue_57_gates_snapshot)
    reference = build_reference(
        issue_57_gates_snapshot,
        scope="single_qubit_relaxation",
        qubits=range(3),
    )

    counts_rows = run_benchmark(
        circuits,
        ensemble,
        reference,
        [HellingerDistance(), KLDivergence(), R2Score()],
        shots=128,
        seed=29,
    )
    state_rows = run_benchmark(
        circuits,
        ensemble,
        reference,
        [StateFidelity()],
        mode="density_matrix",
    )

    assert len(counts_rows) == 12
    assert len(state_rows) == 4
    assert all(row.failure is None for row in [*counts_rows, *state_rows])
    assert all(
        math.isfinite(value)
        for row in [*counts_rows, *state_rows]
        for value in (row.engine_value, row.reference_value, row.delta)
    )
    assert [row.reference_value for row in counts_rows] == pytest.approx([0.0, 0.0, 1.0] * 4)
    assert [row.reference_value for row in state_rows] == pytest.approx([1.0] * 4)


def test_issue_57_fixture_like_for_like_noise_instruction_scope(
    issue_57_gates_snapshot: CalibrationSnapshot,
    make_benchmark_ensemble: Callable[..., FuzzyNoiseModelEnsemble],
) -> None:
    """Engine-installed names are covered by the one-qubit reference, except virtual rz."""
    ensemble = make_benchmark_ensemble(1, snapshot=issue_57_gates_snapshot)
    reference = build_reference(
        issue_57_gates_snapshot,
        scope="single_qubit_relaxation",
        qubits=range(3),
    )
    engine_results = simulate_engine(
        [qft_circuit(3), ghz_state_circuit(3)],
        ensemble,
        basis_gates=reference.basis_gates,
        shots=32,
        seed=41,
    )
    reference_names = set(reference.noise_instructions)

    for result in engine_results:
        assert result.metadata is not None
        for member_names in result.metadata["noise_instructions"]:
            assert set(member_names) - {"rz"} <= reference_names
