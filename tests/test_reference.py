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
from superconducted.calibration.loader import load_snapshot
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.training.targets import SkipCounts, gate_lengths, qubit_targets
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
    """Each qubit is rejected by its first applicable reason, in ADR-027's order."""
    qubits = [
        _qubit(),
        _qubit(t1_us=None),
        _qubit(t2_us=float("inf")),
        _qubit(t1_us=40.0, t2_us=81.0),
        _qubit(t1_us=0.0),
        _qubit(t1_us=None, t2_us=None),
        _qubit(t1_us=-1.0, t2_us=-1.0),
    ]
    gates = [_gate("sx", [q]) for q in range(len(qubits))]
    snapshot = _snapshot(qubits=qubits, gates=gates)

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert report.qubits_used == (0,)
    assert report.skipped == {
        "t1_missing": (1, 5),
        "t2_missing": (2,),
        "nonpositive": (4, 6),
        "t2_exceeds_2t1": (3,),
    }
    assert list(report.skipped) == ["t1_missing", "t2_missing", "nonpositive", "t2_exceeds_2t1"]
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
    assert report.skipped["t1_missing"] == (1,)
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


def test_full_device_readout_orientation_for_a_prepared_one() -> None:
    """The prepared-|1> row: P(read 0 | prepared 1) is ``prob_meas0_prep1``.

    The ``x`` gate's own relaxation at T1 = 100 us and 24 ns moves P(0) by about
    2.4e-4, far inside the 3-sigma band of about 9.7e-3 at 20 000 shots.
    """
    shots = 20_000
    model = build_reference(
        _snapshot(qubits=[_qubit(p01=0.3, p10=0.0)], gates=[_gate("x", [0])]),
        scope="full_device",
    )
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()

    result = simulate_reference(
        [circuit], model, basis_gates=model.basis_gates, shots=shots, seed=321
    )[0]
    assert result.counts is not None
    observed = result.counts.get("0", 0) / shots
    standard_error = math.sqrt(0.3 * 0.7 / shots)
    assert abs(observed - 0.3) <= 3.0 * standard_error


def test_no_timed_gate_raises_unless_readout_makes_the_model_non_ideal() -> None:
    """Usable qubits but only zero-length gates: the model would be ideal."""
    only_rz = [_gate("rz", [0], length_ns=0.0)]
    snapshot = _snapshot(gates=only_rz)

    with pytest.raises(ValueError, match="installs no error"):
        build_reference(snapshot, scope="single_qubit_relaxation")
    # Aer drops an ideal ReadoutError, so p01 = p10 = 0 leaves full_device ideal too.
    with pytest.raises(ValueError, match="installs no error"):
        build_reference(snapshot, scope="full_device")

    noisy_readout = _snapshot(qubits=[_qubit(p01=0.02, p10=0.03)], gates=only_rz)
    model = build_reference(noisy_readout, scope="full_device")
    report = build_reference_report(noisy_readout, scope="full_device")
    assert set(model._local_readout_errors) == {(0,)}
    assert report.qubits_used == (0,)


def test_ideal_readout_does_not_count_a_qubit_as_used() -> None:
    """``qubits_used`` means represented in the model; Aer drops an ideal readout error."""
    snapshot = _snapshot(
        qubits=[_qubit(p01=0.02, p10=0.03), _qubit(p01=0.0, p10=0.0)],
        gates=[_gate("sx", [0])],
    )

    report = build_reference_report(snapshot, scope="full_device")

    assert report.qubits_used == (0,)


@pytest.mark.parametrize(
    "parameters",
    [[], [_nduv("gate_length", 68.0, "ns")], [_nduv("gate_error", None, "")]],
    ids=("empty", "no-gate-error", "null-gate-error"),
)
def test_cz_without_a_finite_gate_error_raises_in_full_device(
    parameters: list[dict[str, Any]],
) -> None:
    """A cz entry that does not state its gate_error cannot be classified dead or alive."""
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit()],
        gates=[
            _gate("sx", [0]),
            _gate("sx", [1]),
            {"gate": "cz", "qubits": [0, 1], "parameters": parameters},
        ],
    )

    with pytest.raises(ValueError, match="gate_error"):
        build_reference(snapshot, scope="full_device")


def test_cz_with_a_nan_gate_error_raises_in_full_device() -> None:
    entry = _gate("cz", [0, 1], length_ns=68.0)
    entry["parameters"][0]["value"] = float("nan")
    snapshot = _snapshot(qubits=[_qubit(), _qubit()], gates=[_gate("sx", [0]), entry])

    with pytest.raises(ValueError, match="gate_error"):
        build_reference(snapshot, scope="full_device")


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


def _calibration_snapshot(data: dict[str, Any]) -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00")),
        schema_version=str(data["schema_version"]),
        properties=data["properties"],
        target=data.get("target"),
        configuration=data.get("configuration"),
    )


def test_issue_57_fixture_reference_provenance() -> None:
    """Consume #57's sole gates fixture; never create a duplicate here."""
    data = json.loads(WITH_GATES_FIXTURE.read_text(encoding="utf-8"))
    snapshot = _calibration_snapshot(data)

    model = build_reference(snapshot, scope="full_device")
    report = build_reference_report(snapshot, scope="full_device")

    assert len(report.qubits_used) == 155
    assert report.skipped == {
        "t1_missing": (72,),
        "t2_missing": (),
        "nonpositive": (),
        "t2_exceeds_2t1": (),
    }
    assert report.skipped_gates == {"gate_length_missing": (), "nonpositive": ()}
    assert len(report.dead_pairs) == 10
    assert set(model.basis_gates) == {"cz", "id", "rx", "rz", "sx", "x"}
    # 24 ns read through the ns -> s boundary: 24 * 1e-9 is one ulp above the
    # literal 24e-9, so the pin is to rounding, not to bit equality (NC-035).
    assert report.gate_lengths_s[("sx", (0,))] == pytest.approx(24e-9, rel=1e-15)


def test_missing_or_negative_gate_length_installs_nothing_and_is_recorded() -> None:
    """ADR-028's fail-closed rule: no usable duration means no channel, recorded."""
    no_length = {"gate": "x", "name": "x0", "qubits": [0], "parameters": []}
    no_parameters = {"gate": "rx", "name": "rx0", "qubits": [0]}
    snapshot = _snapshot(
        gates=[_gate("sx", [0]), no_length, no_parameters, _gate("id", [0], length_ns=-1.0)]
    )

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert set(model.noise_instructions) == {"sx"}
    assert report.skipped_gates == {
        "gate_length_missing": (("x", (0,)), ("rx", (0,))),
        "nonpositive": (("id", (0,)),),
    }
    assert ("x", (0,)) not in report.gate_lengths_s
    assert ("id", (0,)) not in report.gate_lengths_s


def test_non_list_parameters_on_a_one_qubit_gate_is_a_missing_record() -> None:
    """Same reading as ``training.targets.gate_lengths``, which skips such an entry."""
    snapshot = _snapshot(
        gates=[_gate("sx", [0]), {"gate": "x", "qubits": [0], "parameters": "oops"}]
    )

    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    assert set(model.noise_instructions) == {"sx"}
    assert report.skipped_gates["gate_length_missing"] == (("x", (0,)),)


def test_cz_without_parameters_raises_in_full_device_scope() -> None:
    """A cz entry that cannot say whether the pair is dead is corrupt, not missing."""
    snapshot = _snapshot(
        qubits=[_qubit(), _qubit()],
        gates=[_gate("sx", [0]), _gate("sx", [1]), {"gate": "cz", "qubits": [0, 1]}],
    )

    with pytest.raises(ValueError, match="parameters must be a list"):
        build_reference(snapshot, scope="full_device")
    # The one-qubit scope never reads two-qubit entries, so it is unaffected.
    assert "cz" not in build_reference(snapshot, scope="single_qubit_relaxation").noise_instructions


@pytest.mark.parametrize("value", [None, [24e-9], "fast"], ids=("none", "list", "text"))
def test_malformed_gate_length_override_raises_value_error(value: object) -> None:
    with pytest.raises(ValueError, match="gate_lengths"):
        build_reference(
            _snapshot(),
            scope="single_qubit_relaxation",
            gate_lengths={"sx": value},  # type: ignore[dict-item]
        )


@pytest.mark.parametrize("sx_length", ["missing", "negative"])
def test_sx_length_gaps_are_qubit_level_in_targets_and_gate_level_here(
    sx_length: str, tmp_path: Path
) -> None:
    """The two intended divergences from ``training.targets``, pinned rather than hidden.

    The target needs one ``sx`` duration per qubit and rejects the qubit, as
    ``gate_length_missing`` or ``nonpositive``; the reference times each gate
    separately, so it keeps the qubit for its other gates and records only the
    ``sx`` entry, under the same reason name.
    """
    data = json.loads(WITH_GATES_FIXTURE.read_text(encoding="utf-8"))
    for entry in data["properties"]["gates"]:
        if entry["gate"] == "sx" and entry["qubits"] == [0]:
            if sx_length == "missing":
                entry["parameters"] = [p for p in entry["parameters"] if p["name"] != "gate_length"]
            else:
                for parameter in entry["parameters"]:
                    if parameter["name"] == "gate_length":
                        parameter["value"] = -1.0
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    reason = "gate_length_missing" if sx_length == "missing" else "nonpositive"

    targets = qubit_targets(load_snapshot(path), gate_lengths(data["properties"], "sx"))
    report = build_reference_report(_calibration_snapshot(data), scope="single_qubit_relaxation")

    assert not targets.usable[0]
    assert getattr(targets.skipped, reason) == 1
    assert 0 in report.qubits_used
    assert 0 not in {q for qubits in report.skipped.values() for q in qubits}
    assert report.skipped_gates[reason] == (("sx", (0,)),)


@pytest.mark.parametrize(
    "value",
    [None, "fast", float("nan"), float("inf")],
    ids=("null", "non-numeric", "nan", "inf"),
)
def test_corrupt_gate_length_raises(value: object) -> None:
    """A record that exists but cannot be read is corrupt, not missing."""
    entry = _gate("sx", [0])
    entry["parameters"][1]["value"] = value

    with pytest.raises(ValueError, match="gate_length"):
        build_reference(_snapshot(gates=[entry]), scope="single_qubit_relaxation")


def test_no_usable_qubit_raises_instead_of_returning_a_noise_free_model() -> None:
    snapshot = _snapshot(
        qubits=[_qubit(t1_us=None), _qubit(t1_us=40.0, t2_us=81.0)],
        gates=[_gate("sx", [0]), _gate("sx", [1])],
    )

    with pytest.raises(ValueError, match="no selected qubit has usable"):
        build_reference(snapshot, scope="single_qubit_relaxation")
    with pytest.raises(ValueError, match="no selected qubit has usable"):
        build_reference(
            _snapshot(qubits=[_qubit(), _qubit(t1_us=None)]), scope="full_device", qubits=[1]
        )


def _set_nduv(qubit: list[dict[str, Any]], name: str, value: float | None) -> None:
    for entry in qubit:
        if entry["name"] == name:
            entry["value"] = value
            return
    raise AssertionError(f"fixture qubit has no {name} entry")


def _nduv_value(qubit: list[dict[str, Any]], name: str) -> float:
    return float(next(entry["value"] for entry in qubit if entry["name"] == name))


def _fixture_with_every_skip_reason() -> dict[str, Any]:
    """The real fixture with qubits 0-5 edited to hit each ADR-027 reason once."""
    data = json.loads(WITH_GATES_FIXTURE.read_text(encoding="utf-8"))
    qubits = data["properties"]["qubits"]
    _set_nduv(qubits[0], "T1", None)  # t1_missing
    _set_nduv(qubits[1], "T2", float("nan"))  # t2_missing, through the non-finite path
    _set_nduv(qubits[2], "T1", -5.0)  # nonpositive
    _set_nduv(qubits[3], "T2", 2.0 * _nduv_value(qubits[3], "T1") + 1.0)  # t2_exceeds_2t1
    _set_nduv(qubits[4], "T1", None)  # both missing: the first reason wins
    _set_nduv(qubits[4], "T2", None)
    _set_nduv(qubits[5], "T2", 2.0 * _nduv_value(qubits[5], "T1"))  # boundary, usable
    return data


@pytest.mark.parametrize("variant", ["fixture", "every_skip_reason"])
def test_reference_matches_training_targets_per_qubit(variant: str, tmp_path: Path) -> None:
    """Cross-module pin (#58 FR-5, #57 section 7 item 3): one skip rule, one channel.

    On the same snapshot, ``build_reference`` and ``training.targets.qubit_targets``
    reject exactly the same qubits, with the same count per ADR-027 reason, and on
    every usable qubit the reference's ``sx`` channel equals the engine's projector
    applied to that qubit's ``(gamma, lambda)`` target, under ``SuperOp``.
    """
    if variant == "fixture":
        data = json.loads(WITH_GATES_FIXTURE.read_text(encoding="utf-8"))
    else:
        data = _fixture_with_every_skip_reason()
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    targets = qubit_targets(load_snapshot(path), gate_lengths(data["properties"], "sx"))
    snapshot = _calibration_snapshot(data)
    model = build_reference(snapshot, scope="single_qubit_relaxation")
    report = build_reference_report(snapshot, scope="single_qubit_relaxation")

    rejected = {q for qubits in report.skipped.values() for q in qubits}
    assert {q for q in range(len(targets.usable)) if targets.usable[q]} == (
        set(range(len(targets.usable))) - rejected
    )
    assert targets.skipped == SkipCounts(
        t1_missing=len(report.skipped["t1_missing"]),
        t2_missing=len(report.skipped["t2_missing"]),
        gate_length_missing=0,
        nonpositive=len(report.skipped["nonpositive"]),
        t2_exceeds_2t1=len(report.skipped["t2_exceeds_2t1"]),
    )
    if variant == "every_skip_reason":
        assert report.skipped == {
            "t1_missing": (0, 4, 72),
            "t2_missing": (1,),
            "nonpositive": (2,),
            "t2_exceeds_2t1": (3,),
        }

    projector = KrausChannelProjector(NoOpNormalization())
    worst = 0.0
    for q in np.flatnonzero(targets.usable):
        engine_channel = projector.project(targets.values[q], "sx", (int(q),))
        reference_channel = _quantum_error(model, "sx", (int(q),))
        worst = max(
            worst,
            float(np.max(np.abs(SuperOp(reference_channel).data - SuperOp(engine_channel).data))),
        )
    assert worst <= 1e-12
