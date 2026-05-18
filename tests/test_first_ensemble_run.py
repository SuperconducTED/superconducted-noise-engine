import json
from pathlib import Path
from typing import Any

import pytest
from qiskit import QuantumCircuit
from scripts.first_ensemble_run import _load_snapshot, run_ensemble


class DummyMember:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def prepare(self, circuit: QuantumCircuit) -> tuple[QuantumCircuit, Any]:
        return circuit, object()


class DummyResult:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def result(self) -> "DummyResult":
        return self

    def get_counts(self) -> dict[str, int]:
        return self._counts


class DummySimulator:
    def __init__(self, responses: list[dict[str, int]]) -> None:
        self._responses = responses
        self.calls: list[tuple[int, Any]] = []

    def run(self, circuit: QuantumCircuit, shots: int, noise_model: Any) -> DummyResult:
        self.calls.append((shots, noise_model))
        return DummyResult(self._responses.pop(0))


def test_run_ensemble_aggregates_counts(monkeypatch: Any) -> None:
    expected_counts = [{"0": 9, "1": 6}, {"0": 3, "1": 0}]
    monkeypatch.setattr(
        "scripts.first_ensemble_run.transpile", lambda circuit, backend=None: circuit
    )

    sim = DummySimulator(list(expected_counts))
    members = [DummyMember({}), DummyMember({})]
    actual = run_ensemble(members, QuantumCircuit(1), shots=1024, simulator=sim)

    assert actual == {"0": 6, "1": 3}


def test_default_mfs_for_feature_raises_on_unknown() -> None:
    from scripts.first_ensemble_run import _default_mfs_for_feature

    with pytest.raises(ValueError, match="unknown feature"):
        _default_mfs_for_feature("not_a_feature")


@pytest.mark.slow
def test_run_ensemble_real_aer_one_qubit() -> None:
    """End-to-end pipeline: fuzzy snapshot -> FuzzyNoiseModel -> Aer.

    Closes the gap left by test_run_ensemble_aggregates_counts, which
    only verifies aggregation via DummySimulator monkeypatching.
    """
    from qiskit_aer import AerSimulator
    from scripts.first_ensemble_run import (
        _synthetic_snapshot,
        generate_safe_ensemble,
    )

    snapshot = _synthetic_snapshot()
    members = generate_safe_ensemble(snapshot, n=1)
    assert len(members) == 1

    qc = QuantumCircuit(1)
    qc.h(0)
    qc.measure_all()

    _, prepared_nm = members[0].prepare(qc.copy())
    assert prepared_nm.noise_instructions, (
        "expected non-empty noise_instructions on prepared NoiseModel"
    )

    sim = AerSimulator()
    counts = run_ensemble(members, qc, shots=256, simulator=sim)
    assert sum(counts.values()) > 0


def test_load_snapshot(tmp_path: Path) -> None:
    data = {
        "backend": "ibm_fez",
        "timestamp": "2026-05-01T00:00:00Z",
        "schema_version": "1.0",
        "properties": {"qubits": [[{"name": "T1", "value": 50e-6}]]},
        "target": None,
        "configuration": None,
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    snapshot = _load_snapshot(path)

    assert snapshot.backend == "ibm_fez"
    assert snapshot.timestamp.isoformat() == "2026-05-01T00:00:00+00:00"
    assert snapshot.schema_version == "1.0"
    assert snapshot.properties == data["properties"]
    assert snapshot.target is None
    assert snapshot.configuration is None
