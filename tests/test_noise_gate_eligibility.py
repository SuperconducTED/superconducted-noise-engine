"""Physical-gate eligibility for fuzzy Aer noise installation (Issue #73)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer.library import SaveStatevector

from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import FuzzyNoiseModel
from superconducted.types import CalibrationSnapshot


def _model(target: dict[str, object] | None) -> FuzzyNoiseModel:
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
            properties={},
            target=target,
            configuration=None,
        ),
        feature_extractor=ConstantExtractor(),  # type: ignore[arg-type]
        rule_base=rule_base,
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
    )


def test_prepare_attaches_noise_only_to_positive_duration_calibrated_gate() -> None:
    model = _model(
        {
            "operations": [
                {"name": "sx", "qargs": [0], "duration": 24e-9},
                {"name": "sx", "qargs": [1], "duration": 0.0},
                {"name": "rz", "qargs": [0], "duration": 0.0},
                {"name": "x", "qargs": [0]},
                {"name": "y", "qargs": [0], "duration": float("nan")},
                {"name": "z", "qargs": [0], "duration": -1.0},
            ]
        }
    )
    circuit = QuantumCircuit(2)
    circuit.sx(0)
    circuit.sx(1)
    circuit.rz(0.5, 0)
    circuit.x(0)
    circuit.y(0)
    circuit.z(0)
    circuit.delay(10, 0, unit="ns")
    circuit.append(SaveStatevector(2), [0, 1])

    _, noise_model = model.prepare(circuit)

    assert noise_model.noise_instructions == ["sx"]
    errors = noise_model.to_dict()["errors"]
    assert len(errors) == 1
    assert errors[0]["operations"] == ["sx"]
    assert errors[0]["gate_qubits"] == [(0,)]


def test_prepare_without_target_fails_closed() -> None:
    circuit = QuantumCircuit(1)
    circuit.sx(0)

    _, first = _model(None).prepare(circuit)
    _, second = _model(None).prepare(circuit)

    assert first.noise_instructions == []
    assert second.noise_instructions == []
