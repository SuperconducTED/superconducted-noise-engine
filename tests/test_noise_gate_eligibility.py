"""Physical-gate eligibility for fuzzy Aer noise installation (Issue #73).

Module-level imports are deliberately limited to the API that exists on the
pre-fix tree, and ``_model`` only forwards ``gate_eligibility_policy`` when one
is given. That keeps #73's first acceptance criterion honest: checked out
against the pre-fix tree this module still imports, and
``test_prepare_uses_real_gate_lengths_to_filter_physical_instructions`` fails
with ``['delay', 'rz', 'save_density_matrix', 'sx', 'x'] != ['sx', 'x']``, which
is the erroneous attachment the issue describes. The two names added by the fix
are imported inside the tests that need them.
"""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

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
from superconducted.integration.aer_factory import FuzzyNoiseModel
from superconducted.types import CalibrationSnapshot

if TYPE_CHECKING:
    from superconducted.interfaces import GateEligibilityPolicy

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
        **(
            {}
            if gate_eligibility_policy is None
            else {"gate_eligibility_policy": gate_eligibility_policy}
        ),
    )


def test_real_archive_gate_lengths_include_physical_sx_and_exclude_virtual_rz() -> None:
    from superconducted.integration.aer_factory import CalibrationGateEligibilityPolicy

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
    from superconducted.interfaces import GateEligibilityPolicy

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


def _properties_with_sx_disabled_on(qubit: int) -> dict[str, object]:
    """Real fixture properties with one qubit's ``sx`` recorded as 0 ns."""
    fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    properties: dict[str, object] = fixture["properties"]
    for entry in properties["gates"]:  # type: ignore[index]
        if entry.get("gate") == "sx" and entry.get("qubits") == [qubit]:
            for parameter in entry["parameters"]:
                if parameter["name"] == "gate_length":
                    parameter["value"] = 0
    return properties


def test_eligibility_is_qubit_aware_not_just_gate_aware() -> None:
    """A calibration on one qubit must not authorize the same gate on another.

    #73 requires the policy to be qubit-aware. Every gate in the archive
    fixture is calibrated on all 156 qubits, so only a per-qubit edit can tell
    a qubit-aware policy apart from one that matches on the gate name alone.
    """
    from superconducted.integration.aer_factory import CalibrationGateEligibilityPolicy

    eligible = CalibrationGateEligibilityPolicy().eligible_operations(
        CalibrationSnapshot(
            backend="ibm_test",
            timestamp=datetime(2026, 9, 18, tzinfo=UTC),
            schema_version="1.0",
            properties=_properties_with_sx_disabled_on(0),
            target=None,
            configuration=None,
        )
    )

    assert ("sx", (0,)) not in eligible
    assert ("sx", (1,)) in eligible
    # The edit is scoped to sx on qubit 0; x on qubit 0 is untouched.
    assert ("x", (0,)) in eligible


def test_prepare_installs_nothing_for_a_qubit_whose_gate_is_uncalibrated() -> None:
    """The qubit-aware decision reaches installation, not just the policy."""
    circuit = QuantumCircuit(1)
    circuit.sx(0)

    with pytest.warns(UserWarning, match=r"none of the circuit's instructions"):
        _, noise_model = _model(_properties_with_sx_disabled_on(0)).prepare(circuit)

    assert noise_model.noise_instructions == []


def test_a_malformed_gate_length_is_rejected_at_construction() -> None:
    """Eligibility resolves in ``__init__``, so bad calibration fails early.

    Before this was hoisted out of ``prepare()`` the same payload raised on
    whichever call happened to touch it first, which for an ensemble is the
    33rd one, long after the caller could still choose another snapshot.
    """
    from superconducted.calibration.loader import CalibrationParseError

    properties = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))["properties"]
    for entry in properties["gates"]:
        if entry.get("gate") == "sx":
            for parameter in entry["parameters"]:
                if parameter["name"] == "gate_length":
                    parameter["unit"] = "us"

    with pytest.raises(CalibrationParseError, match=r"expected gate_length unit 'ns'"):
        _model(properties)
