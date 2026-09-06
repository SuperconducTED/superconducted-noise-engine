"""Thermal-relaxation reference-model certification for issue #58."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import SuperOp
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error

from superconducted.benchmarks.circuits import qft_circuit
from superconducted.benchmarks.harness import simulate_reference
from superconducted.benchmarks.reference import build_reference, build_reference_report
from superconducted.types import CalibrationSnapshot


def _nduv(name: str, value: float | None, unit: str) -> dict[str, Any]:
    return {"name": name, "value": value, "unit": unit}


def _qubit(
    *,
    t1_us: float | None = 100.0,
    t2_us: float | None = 80.0,
    p01: float | None = 0.0,
    p10: float | None = 0.0,
    t1_unit: str = "us",
    t2_unit: str = "us",
    readout_unit: str = "",
) -> list[dict[str, Any]]:
    entries = [
        _nduv("T1", t1_us, t1_unit),
        _nduv("T2", t2_us, t2_unit),
        _nduv("prob_meas0_prep1", p01, readout_unit),
        _nduv("prob_meas1_prep0", p10, readout_unit),
    ]
    return [entry for entry in entries if entry["value"] is not None]


def _gate(
    name: str,
    qubits: list[int],
    *,
    length_ns: float = 24.0,
    gate_error: float = 0.001,
    length_unit: str = "ns",
) -> dict[str, Any]:
    return {
        "gate": name,
        "name": f"{name}{'_'.join(str(q) for q in qubits)}",
        "qubits": qubits,
        "parameters": [
            _nduv("gate_error", gate_error, ""),
            _nduv("gate_length", length_ns, length_unit),
        ],
    }


def _snapshot(
    *,
    qubits: list[list[dict[str, Any]]] | None = None,
    gates: list[dict[str, Any]] | None = None,
) -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend="ibm_test",
        timestamp=datetime(2026, 9, 6, tzinfo=UTC),
        schema_version="1.0.0",
        properties={
            "qubits": qubits if qubits is not None else [_qubit()],
            "gates": gates
            if gates is not None
            else [_gate("sx", [0]), _gate("rz", [0], length_ns=0.0)],
        },
        target=None,
        configuration=None,
    )


def _quantum_error(model: NoiseModel, gate: str, qubits: tuple[int, ...]) -> Any:
    return model._local_quantum_errors[gate][qubits]


def test_reference_returns_plain_model_with_transpilable_unitary_basis() -> None:
    gates = [
        _gate("id", [0]),
        _gate("rx", [0]),
        _gate("rz", [0], length_ns=0.0),
        _gate("sx", [0]),
        _gate("x", [0]),
        _gate("cz", [0, 1], length_ns=68.0),
        _gate("measure", [0]),
        _gate("measure_2", [0, 1]),
        _gate("reset", [0]),
    ]
    model = build_reference(
        _snapshot(qubits=[_qubit(), _qubit()], gates=gates),
        scope="single_qubit_relaxation",
    )

    assert type(model) is NoiseModel
    assert set(model.basis_gates) == {"id", "rx", "rz", "sx", "x", "cz"}
    assert not ({"measure", "measure_2", "reset"} & set(model.basis_gates))
    compiled = transpile(qft_circuit(3), basis_gates=model.basis_gates)
    assert "qft" not in compiled.count_ops()


@pytest.mark.parametrize(
    ("t1_us", "t2_us"),
    [(100.0, 80.0), (100.0, 150.0), (100.0, 200.0)],
    ids=("t2-le-t1", "t1-lt-t2", "t2-equals-2t1"),
)
def test_single_qubit_channel_matches_aer_after_unit_conversion(t1_us: float, t2_us: float) -> None:
    model = build_reference(
        _snapshot(qubits=[_qubit(t1_us=t1_us, t2_us=t2_us)]),
        scope="single_qubit_relaxation",
    )
    actual = SuperOp(_quantum_error(model, "sx", (0,))).data
    expected = SuperOp(thermal_relaxation_error(t1_us * 1e-6, t2_us * 1e-6, 24.0e-9)).data

    assert np.max(np.abs(actual - expected)) <= 1e-12


@pytest.mark.parametrize(
    ("snapshot", "scope", "message"),
    [
        (_snapshot(qubits=[_qubit(t1_unit="s")]), "single_qubit_relaxation", "T1.*unit"),
        (
            _snapshot(gates=[_gate("sx", [0], length_unit="us")]),
            "single_qubit_relaxation",
            "gate_length.*unit",
        ),
        (_snapshot(qubits=[_qubit(readout_unit="percent")]), "full_device", "prob_meas"),
    ],
)
def test_reference_rejects_wrong_units(
    snapshot: CalibrationSnapshot, scope: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_reference(snapshot, scope=scope)  # type: ignore[arg-type]


def test_gate_length_override_is_verbatim_and_reported() -> None:
    snapshot = _snapshot()
    override = 48.0e-9

    model = build_reference(
        snapshot,
        scope="single_qubit_relaxation",
        gate_lengths={"sx": override},
    )
    report = build_reference_report(
        snapshot,
        scope="single_qubit_relaxation",
        gate_lengths={"sx": override},
    )

    expected = thermal_relaxation_error(100.0e-6, 80.0e-6, override)
    assert (
        np.max(np.abs(SuperOp(_quantum_error(model, "sx", (0,))).data - SuperOp(expected).data))
        <= 1e-12
    )
    assert report.gate_lengths_s[("sx", (0,))] == override
    assert report.overridden_gate_lengths == ("sx",)


def test_zero_duration_rz_is_reported_but_not_installed() -> None:
    snapshot = _snapshot()

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert "rz" not in model.noise_instructions
    assert report.gate_lengths_s[("rz", (0,))] == 0.0


def test_skip_rules_are_non_imputing_and_fully_counted() -> None:
    qubits = [
        _qubit(),
        _qubit(t1_us=None),
        _qubit(t2_us=float("inf")),
        _qubit(t1_us=40.0, t2_us=81.0),
    ]
    gates = [_gate("sx", [q]) for q in range(4)]
    snapshot = _snapshot(qubits=qubits, gates=gates)

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert report.qubits_used == (0,)
    assert report.skipped == {
        "missing_t1_t2": (1, 2),
        "t2_exceeds_2t1": (3,),
    }
    assert set(model._local_quantum_errors["sx"]) == {(0,)}


def test_full_device_expand_order_matches_declared_qubit_order() -> None:
    snapshot = _snapshot(
        qubits=[_qubit(t1_us=50.0, t2_us=40.0), _qubit(t1_us=200.0, t2_us=180.0)],
        gates=[_gate("sx", [0]), _gate("sx", [1]), _gate("cz", [0, 1], length_ns=68.0)],
    )
    model = build_reference(snapshot, scope="full_device")
    actual = SuperOp(_quantum_error(model, "cz", (0, 1))).data
    error_a = thermal_relaxation_error(50.0e-6, 40.0e-6, 68.0e-9)
    error_b = thermal_relaxation_error(200.0e-6, 180.0e-6, 68.0e-9)
    expected = SuperOp(error_a.expand(error_b)).data
    reversed_order = SuperOp(error_b.expand(error_a)).data

    assert np.max(np.abs(actual - expected)) <= 1e-12
    assert np.max(np.abs(actual - reversed_order)) > 1e-8


def test_reference_scopes_state_the_engine_gap_honestly() -> None:
    snapshot = _snapshot(
        qubits=[_qubit(p01=0.02, p10=0.03), _qubit(p01=0.04, p10=0.05)],
        gates=[_gate("sx", [0]), _gate("sx", [1]), _gate("cz", [0, 1], length_ns=68.0)],
    )

    single = build_reference(snapshot, scope="single_qubit_relaxation")
    full = build_reference(snapshot, scope="full_device")

    assert "cz" not in single.noise_instructions
    assert not single._local_readout_errors
    assert "cz" in full.noise_instructions
    assert set(full._local_readout_errors) == {(0,), (1,)}


def test_dead_pairs_are_reported_when_adr017_prevents_installation() -> None:
    """A dead pair is provenance; missing T1/T2 still forbids inventing its channel."""
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit(t1_us=None)],
        gates=[_gate("sx", [0]), _gate("sx", [1]), _gate("cz", [0, 1], gate_error=1.0)],
    )

    model = build_reference(snapshot, scope="full_device")
    report = build_reference_report(snapshot, scope="full_device")

    assert report.dead_pairs == ((0, 1),)
    assert report.skipped["missing_t1_t2"] == (1,)
    assert "cz" not in model.noise_instructions


def test_usable_dead_pair_still_receives_timed_relaxation() -> None:
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit()],
        gates=[_gate("sx", [0]), _gate("sx", [1]), _gate("cz", [0, 1], gate_error=1.0)],
    )

    model = build_reference(snapshot, scope="full_device")
    report = build_reference_report(snapshot, scope="full_device")

    assert report.dead_pairs == ((0, 1),)
    assert (0, 1) in model._local_quantum_errors["cz"]


def test_full_device_supports_fixture_independent_rzz_basis_entry() -> None:
    """Pin rzz even though #57's May fixture contains only cz two-qubit gates."""
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit()],
        gates=[_gate("sx", [0]), _gate("sx", [1]), _gate("rzz", [0, 1], length_ns=88.0)],
    )

    model = build_reference(snapshot, scope="full_device")

    assert "rzz" in model.basis_gates
    assert (0, 1) in model._local_quantum_errors["rzz"]


def test_full_device_readout_orientation_matches_ibm_probabilities() -> None:
    shots = 20_000
    snapshot = _snapshot(qubits=[_qubit(p01=0.0, p10=0.3)], gates=[_gate("sx", [0])])
    model = build_reference(snapshot, scope="full_device")
    circuit = QuantumCircuit(1)
    circuit.measure_all()

    result = simulate_reference(
        [circuit], model, basis_gates=model.basis_gates, shots=shots, seed=123
    )[0]
    assert result.counts is not None
    observed = result.counts.get("1", 0) / shots
    standard_error = math.sqrt(0.3 * 0.7 / shots)
    assert abs(observed - 0.3) <= 3.0 * standard_error


def test_report_and_model_agree_and_build_is_deterministic() -> None:
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit(t1_us=None)],
        gates=[_gate("sx", [0]), _gate("sx", [1])],
    )

    model_a = build_reference(snapshot, scope="single_qubit_relaxation")
    model_b = build_reference(snapshot, scope="single_qubit_relaxation")
    report_a = build_reference_report(snapshot, scope="single_qubit_relaxation")
    report_b = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert report_a == report_b
    assert report_a.qubits_used == (0,)
    assert set(model_a._local_quantum_errors["sx"]) == {(0,)}
    assert (1,) not in model_a._local_quantum_errors["sx"]
    assert np.array_equal(
        SuperOp(_quantum_error(model_a, "sx", (0,))).data,
        SuperOp(_quantum_error(model_b, "sx", (0,))).data,
    )


def test_report_excludes_valid_qubit_without_an_installed_error() -> None:
    """qubits_used means represented in the model, not merely valid T1/T2."""
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit()],
        gates=[_gate("sx", [0])],
    )

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert report.qubits_used == (0,)
    assert set(model._local_quantum_errors["sx"]) == {(0,)}


WITH_GATES_FIXTURE = (
    Path(__file__).parent / "fixtures" / "calibration" / "ibm_fez_20260513T121322Z_with_gates.json"
)


@pytest.mark.skipif(
    not WITH_GATES_FIXTURE.exists(),
    reason="Issue #57 has not yet landed ibm_fez_20260513T121322Z_with_gates.json",
)
def test_issue_57_fixture_reference_provenance() -> None:
    """Consume #57's sole gates fixture after it lands; never create a duplicate here."""
    data = json.loads(WITH_GATES_FIXTURE.read_text(encoding="utf-8"))
    snapshot = CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00")),
        schema_version=str(data["schema_version"]),
        properties=data["properties"],
        target=data.get("target"),
        configuration=data.get("configuration"),
    )

    model = build_reference(snapshot, scope="full_device")
    report = build_reference_report(snapshot, scope="full_device")

    assert len(report.qubits_used) == 155
    assert report.skipped["missing_t1_t2"] == (72,)
    assert len(report.dead_pairs) == 10
    assert set(model.basis_gates) == {"cz", "id", "rx", "rz", "sx", "x"}
    assert report.gate_lengths_s[("sx", (0,))] == 24e-9


@pytest.mark.skip(
    reason=(
        "Issue #57 owns test_reference_matches_training_targets_per_qubit; "
        "unskip after training/targets.py lands"
    )
)
def test_reference_matches_training_targets_per_qubit() -> None:
    """Reserved cross-module SuperOp consistency pin owned by issue #57."""
