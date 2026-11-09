"""Positive control for `spy_aer_runs.py`: three routes, each one execution of two circuits.

Run from the repository root, with this folder on the path:

    python -m pytest docs/evidence/aer-batching-defect/spy_positive_control.py -q -p spy_aer_runs

A spy that sees nothing proves nothing, so this shows it sees a two-circuit execution through
`AerSimulator.run`, `BackendSamplerV2` and `qiskit_aer.primitives.SamplerV2`, and it fails if the
spy's own record disagrees.
"""

from __future__ import annotations

import spy_aer_runs
from qiskit import QuantumCircuit
from qiskit.primitives import BackendSamplerV2
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2


def circuit(width: int) -> QuantumCircuit:
    out = QuantumCircuit(width)
    out.rz(0.3, range(width))
    out.measure_all()
    return out


def latest() -> dict:
    return spy_aer_runs.records[-1]


def test_simulator_run() -> None:
    AerSimulator().run([circuit(2), circuit(1)], shots=16).result()
    assert latest()["circuits"] == 2


def test_backend_sampler() -> None:
    sampler = BackendSamplerV2(backend=AerSimulator(), options={"default_shots": 16})
    sampler.run([circuit(2), circuit(1)]).result()
    assert latest()["circuits"] == 2


def test_backend_sampler_splits_by_shots() -> None:
    before = len(spy_aer_runs.records)
    sampler = BackendSamplerV2(backend=AerSimulator())
    sampler.run([(circuit(2), None, 16), (circuit(1), None, 32)]).result()
    seen = spy_aer_runs.records[before:]
    assert [record["circuits"] for record in seen] == [1, 1]


def test_aer_sampler() -> None:
    SamplerV2(default_shots=16).run([circuit(2), circuit(1)]).result()
    assert latest()["circuits"] == 2
