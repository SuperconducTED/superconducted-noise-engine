import json
from pathlib import Path
from typing import Any

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
    expected_counts = [{"0": 10, "1": 5}, {"0": 3, "1": 2, "2": 1}]
    monkeypatch.setattr(
        "scripts.first_ensemble_run.AerSimulator", lambda: DummySimulator(list(expected_counts))
    )
    monkeypatch.setattr(
        "scripts.first_ensemble_run.transpile", lambda circuit, backend=None: circuit
    )

    members = [DummyMember({}), DummyMember({})]
    actual = run_ensemble(QuantumCircuit(1), members, shots=1024)

    assert actual == {"0": 13, "1": 7, "2": 1}


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
