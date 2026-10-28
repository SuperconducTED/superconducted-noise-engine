"""Within-job overlap: does the 2113 per-circuit offset create shared per-shot
streams (a) without any seed_simulator and (b) between non-identical circuits?"""

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

nm = NoiseModel()
nm.add_all_qubit_quantum_error(depolarizing_error(0.05, 1), ["h", "ry"])
sim = AerSimulator(method="statevector", noise_model=nm)


def hcirc(n, name):
    qc = QuantumCircuit(n, n, name=name)
    qc.h(range(n))
    qc.measure(range(n), range(n))
    return qc


def frac(a, b, d):
    n = len(a) - d
    return sum(b[j] == a[j + d] for j in range(n)) / n, n


# (a) Unseeded, two identical 8-qubit circuits in one job, 2500 shots.
print("== a. unseeded job, two identical circuits, 2500 shots")
r = sim.run([hcirc(8, "c0"), hcirc(8, "c1")], shots=2500, memory=True).result()
s0, s1 = r.results[0].seed_simulator, r.results[1].seed_simulator
m0, m1 = r.get_memory(0), r.get_memory(1)
f, n = frac(m0, m1, 2113)
print(f"reported seeds {s0}, {s1}, difference {s1 - s0}")
print(
    f"circuit1 shot j == circuit0 shot j+2113: {f:.3f} over {n} shots; "
    f"aligned {sum(x == y for x, y in zip(m0, m1, strict=True)) / 2500:.3f}"
)

# (b) Two different circuits: ry(1.0) and ry(1.3), one qubit, seed 11, 4000 shots.
print("== b. ry(1.0) and ry(1.3) in one job, seed 11, 4000 shots")
cs = []
for k, th in enumerate((1.0, 1.3)):
    qc = QuantumCircuit(1, 1, name=f"ry{k}")
    qc.ry(th, 0)
    qc.measure(0, 0)
    cs.append(qc)
r = sim.run(cs, shots=4000, memory=True, seed_simulator=11).result()
a = np.array([int(x) for x in r.get_memory(0)])
b = np.array([int(x) for x in r.get_memory(1)])
d = 2113
n = 4000 - d
corr_shift = np.corrcoef(a[d : d + n], b[:n])[0, 1]
corr_aligned = np.corrcoef(a, b)[0, 1]
print(f"P(1): {a.mean():.3f}, {b.mean():.3f}")
print(f"corr(c0 shot j+2113, c1 shot j) over {n} shots: {corr_shift:.3f}")
print(f"corr(c0 shot j, c1 shot j) over 4000 shots: {corr_aligned:.3f}")

# (c) Null check for 1.d=600: aligned agreement between far-apart seeds, 10 pairs.
print("== c. aligned agreement, 8 qubits, 512 shots, seeds 10**6*k vs 10**6*k + 600")
vals = []
q8 = hcirc(8, "c")
for k in range(1, 11):
    x = sim.run(q8, shots=512, memory=True, seed_simulator=10**6 * k).result().get_memory(0)
    y = sim.run(q8, shots=512, memory=True, seed_simulator=10**6 * k + 600).result().get_memory(0)
    vals.append(sum(u == v for u, v in zip(x, y, strict=True)) / 512)
print(
    "per pair:",
    [round(v, 3) for v in vals],
    "mean",
    round(float(np.mean(vals)), 4),
    "(2^-8 = 0.0039)",
)
