"""Benchmark circuit library.

Bootstrap ships four standard circuits used across the literature:
random Clifford (Bautra-style fidelity benchmark), GHZ (entanglement
distribution), QFT (algorithmic primitive), and a VQE EfficientSU2
ansatz (variational workload).

All circuits include ``measure_all()`` so that count-based metrics
(Hellinger, KL, R²) work without additional setup.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFTGate, efficient_su2
from qiskit.quantum_info import random_clifford


def random_clifford_circuit(
    n_qubits: int,
    depth: int,
    *,
    rng: np.random.Generator | None = None,
) -> QuantumCircuit:
    """Random Clifford circuit of ``depth`` layers.

    Each layer samples an independent Clifford on ``n_qubits`` and
    composes its synthesized circuit. Includes ``measure_all`` at the end.
    """
    if n_qubits <= 0:
        raise ValueError(f"n_qubits must be positive; got {n_qubits}")
    if depth <= 0:
        raise ValueError(f"depth must be positive; got {depth}")
    rng = rng if rng is not None else np.random.default_rng()
    qc = QuantumCircuit(n_qubits, name=f"random_clifford_n{n_qubits}_d{depth}")
    for _ in range(depth):
        seed = int(rng.integers(0, 2**31 - 1))
        cliff = random_clifford(n_qubits, seed=seed)
        qc.compose(cliff.to_circuit(), inplace=True)
    qc.measure_all()
    return qc


def ghz_state_circuit(n_qubits: int) -> QuantumCircuit:
    """GHZ-state preparation: H on q0 then CX cascade to q1..q_{n-1}."""
    if n_qubits < 2:
        raise ValueError(f"GHZ requires n_qubits >= 2; got {n_qubits}")
    qc = QuantumCircuit(n_qubits, name=f"ghz_n{n_qubits}")
    qc.h(0)
    for i in range(1, n_qubits):
        qc.cx(0, i)
    qc.measure_all()
    return qc


def qft_circuit(n_qubits: int) -> QuantumCircuit:
    """Quantum Fourier Transform on ``n_qubits``.

    Uses :class:`qiskit.circuit.library.QFTGate` (the function/gate form;
    the deprecated ``QFT`` *class* must NOT be used per ADR / Codex review).
    """
    if n_qubits <= 0:
        raise ValueError(f"n_qubits must be positive; got {n_qubits}")
    qc = QuantumCircuit(n_qubits, name=f"qft_n{n_qubits}")
    qc.append(QFTGate(n_qubits), range(n_qubits))
    qc.measure_all()
    return qc


def vqe_ansatz_circuit(
    n_qubits: int,
    reps: int = 2,
    *,
    rng: np.random.Generator | None = None,
) -> QuantumCircuit:
    """Random-parameterized EfficientSU2 ansatz.

    Uses :func:`qiskit.circuit.library.efficient_su2` (the function form;
    the deprecated ``EfficientSU2`` *class* must NOT be used per ADR /
    Codex review). Parameters drawn from ``rng.normal``.
    """
    if n_qubits <= 0:
        raise ValueError(f"n_qubits must be positive; got {n_qubits}")
    if reps <= 0:
        raise ValueError(f"reps must be positive; got {reps}")
    rng = rng if rng is not None else np.random.default_rng()
    ansatz = efficient_su2(n_qubits, reps=reps)
    params = rng.normal(size=ansatz.num_parameters)
    bound = ansatz.assign_parameters(params)
    bound.measure_all()
    bound.name = f"vqe_su2_n{n_qubits}_r{reps}"
    return bound
