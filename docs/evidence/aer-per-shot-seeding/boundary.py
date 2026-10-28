"""Boundary: same circuits, only the execution path changes.
The shift appears iff the run takes the per-shot path (measure_sampling False)."""

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error

KEYS = ("method", "noise", "measure_sampling", "parallel_shots")


def h_circ():
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)
    return qc


def x_circ():
    qc = QuantumCircuit(1, 1)
    qc.x(0)
    qc.measure(0, 0)
    return qc


depol = NoiseModel()
depol.add_all_qubit_quantum_error(depolarizing_error(0.05, 1), ["h"])
# x with strong amplitude damping so the outcome is near 50/50 (like the user's case)
thermal = NoiseModel()
thermal.add_all_qubit_quantum_error(thermal_relaxation_error(100e-6, 100e-6, 70e-6), ["x"])


def check(label, qc, nm, shots=2048, s=125, **opts):
    sim = AerSimulator(noise_model=nm, **opts)
    ra = sim.run(qc, shots=shots, memory=True, seed_simulator=s).result()
    rb = sim.run(qc, shots=shots, memory=True, seed_simulator=s + 1).result()
    a, b = ra.get_memory(0), rb.get_memory(0)
    shift = sum(b[j] == a[j + 1] for j in range(shots - 1)) / (shots - 1)
    aligned = sum(b[j] == a[j] for j in range(shots)) / shots
    p1 = sum(x == "1" for x in a) / shots
    md = ra.results[0].metadata
    print(
        f"{label:<42} shift={shift:.3f} aligned={aligned:.3f} P(1)={p1:.3f} "
        f"{ {k: md.get(k) for k in KEYS} }"
    )


check("h + depol, automatic", h_circ(), depol)
check("h + depol, statevector", h_circ(), depol, method="statevector")
check("h, no noise, statevector", h_circ(), None, method="statevector")
check("x + thermal (user case 3), automatic", x_circ(), thermal)
check("x + thermal (user case 3), statevector", x_circ(), thermal, method="statevector")
check("x + thermal, density_matrix", x_circ(), thermal, method="density_matrix")
