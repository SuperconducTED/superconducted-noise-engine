"""Minimal reproduction: seed s+1 replays seed s shifted by one shot."""

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

qc = QuantumCircuit(1, 1)
qc.h(0)
qc.measure(0, 0)
nm = NoiseModel()
nm.add_all_qubit_quantum_error(depolarizing_error(0.05, 1), ["h"])
sim = AerSimulator(method="statevector", noise_model=nm)


def mem(seed):
    r = sim.run(qc, shots=512, memory=True, seed_simulator=seed).result()
    return r.get_memory(0), r.results[0].metadata


a, md = mem(500)
b, _ = mem(501)
print("metadata:", {k: md[k] for k in ("method", "noise", "measure_sampling", "parallel_shots")})
print("shot j of 501 == shot j+1 of 500:", sum(b[j] == a[j + 1] for j in range(511)), "/ 511")
print("shot j of 501 == shot j   of 500:", sum(b[j] == a[j] for j in range(512)), "/ 512")
