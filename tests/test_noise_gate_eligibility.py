"""Physical-gate eligibility for fuzzy Aer noise installation (Issue #73)."""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit_aer.library import SaveDensityMatrix

from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    CalibrationGateEligibilityPolicy,
    FuzzyNoiseModel,
)
from superconducted.interfaces import GateEligibilityPolicy
from superconducted.types import CalibrationSnapshot

GATE_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "calibration"
    / "ibm_fez_20260513T121322Z_with_gates.json"
)


def _model(
    properties: dict[str, object],
    gate_eligibility_policy: GateEligibilityPolicy | None = None,
) -> FuzzyNoiseModel:
    rule_base = TSKRuleBase.from_grid(
        per_input_mfs=[[GaussianMF(center=0.0, sigma=1.0)]],
        output_dim=2,
        consequent_init="random",
        rng=np.random.default_rng(0),
    )

    class ConstantExtractor:
        def extract(self, calibration: CalibrationSnapshot) -> np.ndarray:
            return np.array([0.0])

    return FuzzyNoiseModel(
        calibration=CalibrationSnapshot(
            backend="ibm_test",
            timestamp=datetime(2026, 9, 12, tzinfo=UTC),
            schema_version="1.0",
            properties=properties,
            target=None,
            configuration=None,
        ),
        feature_extractor=ConstantExtractor(),  # type: ignore[arg-type]
        rule_base=rule_base,
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        gate_eligibility_policy=gate_eligibility_policy,
    )


def test_real_archive_gate_lengths_include_physical_sx_and_exclude_virtual_rz() -> None:
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    eligible = CalibrationGateEligibilityPolicy().eligible_operations(
        CalibrationSnapshot(
            backend=fixture["backend"],
            timestamp=datetime.fromisoformat(fixture["timestamp"]),
            schema_version=fixture["schema_version"],
            properties=fixture["properties"],
            target=fixture.get("target"),
            configuration=fixture.get("configuration"),
        )
    )

    assert ("sx", (0,)) in eligible
    assert ("rz", (0,)) not in eligible


def test_prepare_uses_real_gate_lengths_to_filter_physical_instructions() -> None:
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    model = _model(fixture["properties"])
    circuit = QuantumCircuit(1)
    circuit.sx(0)
    circuit.x(0)
    circuit.rz(0.5, 0)
    circuit.delay(10, 0, unit="ns")
    circuit.append(SaveDensityMatrix(1), [0])

    _, noise_model = model.prepare(circuit)

    assert noise_model.noise_instructions == ["sx", "x"]
    errors = noise_model.to_dict()["errors"]
    assert len(errors) == 2
    assert {(error["operations"][0], error["gate_qubits"][0]) for error in errors} == {
        ("sx", (0,)),
        ("x", (0,)),
    }


def test_prepare_without_gate_lengths_fails_closed_and_is_idempotent() -> None:
    circuit = QuantumCircuit(1)
    circuit.sx(0)

    model = _model({})
    _, first = model.prepare(circuit)
    _, second = model.prepare(circuit)

    assert first.noise_instructions == []
    assert second.noise_instructions == []


def test_prepare_uses_an_injected_gate_eligibility_policy() -> None:
    class NoGateIsEligible(GateEligibilityPolicy):
        def eligible_operations(
            self,
            snapshot: CalibrationSnapshot,
        ) -> frozenset[tuple[str, tuple[int, ...]]]:
            return frozenset()

    circuit = QuantumCircuit(1)
    circuit.sx(0)
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))

    _, noise_model = _model(fixture["properties"], NoGateIsEligible()).prepare(circuit)

    assert noise_model.noise_instructions == []


def test_prepare_warns_when_the_circuit_is_not_compiled_to_the_calibrated_basis() -> None:
    """A logical circuit matches no physical gate name, so nothing installs.

    This is the silent-no-op guard. `benchmarks/harness.py` hands `prepare()`
    an untranspiled circuit and never transpiles, so without this warning the
    engine measures a noiseless circuit and the run still looks successful.
    The transpile itself belongs to #58; this only makes its absence audible.
    """
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    with pytest.warns(UserWarning, match=r"none of the circuit's instructions"):
        _, noise_model = _model(fixture["properties"]).prepare(circuit)

    assert noise_model.noise_instructions == []


def test_prepare_warns_when_the_calibration_yields_no_eligible_gate() -> None:
    """A snapshot with no usable gate record disables the engine entirely."""
    circuit = QuantumCircuit(1)
    circuit.sx(0)

    with pytest.warns(UserWarning, match=r"yields no eligible gate at all"):
        _, noise_model = _model({}).prepare(circuit)

    assert noise_model.noise_instructions == []


def test_prepare_is_silent_on_a_circuit_compiled_to_the_calibrated_basis() -> None:
    """The guard must not fire on the path it is meant to protect."""
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    circuit = QuantumCircuit(2)
    circuit.sx(0)
    circuit.rz(0.5, 0)
    circuit.cz(0, 1)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _, noise_model = _model(fixture["properties"]).prepare(circuit)

    assert noise_model.noise_instructions == ["sx"]
    assert [w for w in caught if "installed no error" in str(w.message)] == []
