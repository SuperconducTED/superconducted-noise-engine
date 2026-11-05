"""Targeted checks of the per-shot seeding scheme seed + shot_index
(circuit_executor.hpp:908) and the per-circuit offset 2113
(controller_execute.hpp:213-223), all on the per-shot (statevector + noise) path."""

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error


def circ(n, name="c"):
    qc = QuantumCircuit(n, n, name=name)
    qc.h(range(n))
    qc.measure(range(n), range(n))
    return qc


nm = NoiseModel()
nm.add_all_qubit_quantum_error(depolarizing_error(0.05, 1), ["h"])


def sim(**o):
    return AerSimulator(method="statevector", noise_model=nm, **o)


def shifted_match(a, b, d):
    """Fraction of j where b[j] == a[j+d], over the overlapping range."""
    n = len(a) - d
    return sum(b[j] == a[j + d] for j in range(n)) / n, n


qc8 = circ(8)

# 1. Seed delta d: expect b[j] == a[j+d] for all j < shots - d.
print("== 1. seed s vs s+d, 512 shots, 8 qubits")
a = sim().run(qc8, shots=512, memory=True, seed_simulator=1000).result().get_memory(0)
for d in (1, 100, 511, 600):
    b = sim().run(qc8, shots=512, memory=True, seed_simulator=1000 + d).result().get_memory(0)
    if d < 512:
        f, n = shifted_match(a, b, d)
        print(
            f"d={d:<4} b[j]==a[j+d]: {f:.3f} over {n} shots "
            f"(shared fraction of a run = {n}/512 = {n / 512:.3f})"
        )
    else:
        same = sum(x == y for x, y in zip(a, b, strict=True)) / 512
        print(f"d={d:<4} no overlap possible; aligned agreement {same:.3f} (2^-8 = 0.004 expected)")

# 2. Two circuits in one job, one seed: circuit k gets seed + 2113*k.
print("== 2. two identical circuits in one job, seed 7000, 2500 shots")
r = sim().run([circ(8, "c0"), circ(8, "c1")], shots=2500, memory=True, seed_simulator=7000).result()
m0, m1 = r.get_memory(0), r.get_memory(1)
print("reported seeds:", r.results[0].seed_simulator, r.results[1].seed_simulator)
f, n = shifted_match(m0, m1, 2113)
print(f"circuit1 shot j == circuit0 shot j+2113: {f:.3f} over {n} shots of 2500")
print(f"aligned agreement c0 vs c1: {sum(x == y for x, y in zip(m0, m1, strict=True)) / 2500:.3f}")

# 2b. Same, but split into sub-jobs with max_job_size=1.
print("== 2b. same two circuits, max_job_size=1, seed 7000, 512 shots")
r = (
    sim(max_job_size=1)
    .run([circ(8, "c0"), circ(8, "c1")], shots=512, memory=True, seed_simulator=7000)
    .result()
)
m0, m1 = r.get_memory(0), r.get_memory(1)
print("reported seeds:", r.results[0].seed_simulator, r.results[1].seed_simulator)
print(f"aligned agreement c0 vs c1: {sum(x == y for x, y in zip(m0, m1, strict=True)) / 512:.3f}")

# 3. Unseeded runs: random seed per run, reported in the result.
print("== 3. two unseeded runs, 512 shots")
ra = sim().run(qc8, shots=512, memory=True).result()
rb = sim().run(qc8, shots=512, memory=True).result()
sa, sb = ra.results[0].seed_simulator, rb.results[0].seed_simulator
a, b = ra.get_memory(0), rb.get_memory(0)
print("reported seeds:", sa, sb, "difference:", abs(sa - sb))
best = max(
    shifted_match(a, b, d)[0] if sb > sa else shifted_match(b, a, d)[0] for d in range(0, 50)
)
print(
    f"aligned agreement {sum(x == y for x, y in zip(a, b, strict=True)) / 512:.3f}; "
    f"best shifted match over d in 0..49: {best:.3f}"
)

# 4. Reproducibility across thread settings (the reason for index-based seeding).
print("== 4. same seed, default threads vs max_parallel_threads=1 vs max_parallel_shots=3")
outs = {}
for label, o in (
    ("default", {}),
    ("threads=1", {"max_parallel_threads": 1}),
    ("shots=3", {"max_parallel_shots": 3}),
):
    r = sim(**o).run(qc8, shots=512, memory=True, seed_simulator=42).result()
    outs[label] = r.get_memory(0)
    print(label, "parallel_shots =", r.results[0].metadata["parallel_shots"])
print("memory identical default vs threads=1:", outs["default"] == outs["threads=1"])
print("memory identical default vs shots=3:  ", outs["default"] == outs["shots=3"])

# 5. Counts consequence: 20 consecutive seeds vs 20 seeds spaced by shots+1.
print("== 5. counts across 20 seeds, 4 qubits, 2048 shots: SD of per-qubit z-scores")
qc4 = circ(4)
shots = 2048


def zsd(seeds):
    zs = []
    for s in seeds:
        mem = sim().run(qc4, shots=shots, memory=True, seed_simulator=int(s)).result().get_memory(0)
        bits = np.array([[int(c) for c in m[::-1]] for m in mem])
        p = bits.mean(axis=0)
        zs.append((p - 0.5) / np.sqrt(0.25 / shots))
    return np.std(np.array(zs), axis=0, ddof=1)


print("consecutive 500..519   per-qubit SD:", np.round(zsd(range(500, 520)), 3))
print("spaced by 2049         per-qubit SD:", np.round(zsd(range(500, 500 + 20 * 2049, 2049)), 3))
ss = np.random.SeedSequence(20261028)
print(
    "SeedSequence-drawn     per-qubit SD:", np.round(zsd(ss.generate_state(20, dtype=np.uint32)), 3)
)
