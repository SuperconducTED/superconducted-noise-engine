"""Aer batching defect: the smallest reproduction. Uses only qiskit and qiskit-aer.

Run with:  python -W ignore -I minimal_reproduction.py

A one-qubit circuit, `x` followed by 10% amplitude damping, has a true P(0) of 0.1. Run alone it
gives 0.1. Run in one `run()` after a circuit Aer simulates by statevector, it gives 0.2, and its
probabilities sum to 2. No error or warning is raised.

Section 3 of README.md states what each row was predicted to show before this script existed.
"""

from __future__ import annotations

import numpy as np
import qiskit
import qiskit_aer
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, amplitude_damping_error

SHOTS = 2048
SEED = 97

noise = NoiseModel()
noise.add_all_qubit_quantum_error(amplitude_damping_error(0.1), ["x"])
sim = AerSimulator(noise_model=noise)

# The circuit that comes out wrong, once sampled and once with its probabilities saved.
sampled = QuantumCircuit(1)
sampled.x(0)
sampled.measure_all()
saved = QuantumCircuit(1)
saved.x(0)
saved.save_probabilities()

# Two circuits Aer simulates by statevector at this shot count. An 11-qubit circuit gets statevector
# because shots <= 2^11. A one-qubit circuit gets it because a gate follows its measurement.
eleven_qubits = QuantumCircuit(11)
eleven_qubits.rz(0.3, range(11))
eleven_qubits.measure_all()
one_qubit = QuantumCircuit(1, 2)
one_qubit.x(0)
one_qubit.measure(0, 0)
one_qubit.x(0)
one_qubit.measure(0, 1)


def report(label: str, circuits: list[QuantumCircuit], index: int) -> None:
    """Print P(0) and the sum of probabilities for the circuit at `index`, in one run."""
    swapped = [saved if c is sampled else c for c in circuits]
    counts = sim.run(circuits, shots=SHOTS, seed_simulator=SEED).result()
    probabilities = sim.run(swapped, shots=SHOTS, seed_simulator=SEED).result()
    p0 = counts.get_counts(index).get("0", 0) / SHOTS
    total = float(np.sum(probabilities.data(index)["probabilities"]))
    methods = ", ".join(r.metadata["method"] for r in counts.results)
    print(f"{label:34s} P(0) {p0:.3f}  sum of probabilities {total:.6f}  [{methods}]")


print(f"qiskit {qiskit.__version__}, qiskit-aer {qiskit_aer.__version__}, {SHOTS} shots")
report("alone", [sampled], 0)
report("after an 11-qubit circuit", [eleven_qubits, sampled], 1)
report("before it", [sampled, eleven_qubits], 0)
report("after a one-qubit mid-circuit one", [one_qubit, sampled], 1)
report("before it", [sampled, one_qubit], 0)
