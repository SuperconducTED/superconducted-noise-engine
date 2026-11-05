"""How far does the batching defect reach, and what triggers it? Local only.

Run from the offline half's root:
    PYTHONPATH=.;src python probe_batch_scope.py

Compares each circuit run alone with the same circuit inside one Aer run, and reads the method and
active qubits Aer reports for each experiment.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from scripts.hardware_reading_vs_level import (
    SLOTS,
    _counts_vector,
    _git_json,
    archived_backend,
    arm_a_circuit,
    ghz_idle_circuit,
    transpile_layout,
)

E = Path("docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05")
SHOTS = 2048
SEED = 125


def rates(counts: dict[str, int], n: int) -> np.ndarray:
    vector = _counts_vector(counts, n) / sum(counts.values())
    return np.array([sum(v for idx, v in enumerate(vector) if (idx >> i) & 1) for i in range(n)])


def meta(result, i: int) -> dict:
    m = result.results[i].metadata
    return {
        k: m.get(k)
        for k in (
            "method",
            "active_input_qubits",
            "num_qubits",
            "noise",
            "batched_shots_optimization",
        )
    }


def b_line(label: str, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    print(
        f"  {label:42s} 000 {counts.get('000', 0) / total:.3f}  "
        f"111 {counts.get('111', 0) / total:.3f}",
        flush=True,
    )


def main() -> None:
    manifest = json.loads((E / "manifest.json").read_text(encoding="utf-8"))
    snapshot = _git_json(Path("."), manifest["ref_sha"], manifest["reading_file"])
    backend = archived_backend(snapshot, "reading_snapshot")
    dt, target = float(backend.dt), backend.target
    sim = AerSimulator.from_backend(backend)

    slots = {int(q): s for q, s in manifest["slots_dt"].items()}
    x_len = {q: round(float(target["x"][(q,)].duration) / dt) for q in slots}
    arm_a = [
        arm_a_circuit(k, {q: slots[q][k] for q in slots}, x_len, backend.num_qubits)
        for k in range(len(SLOTS))
    ]
    arm_b = []
    for triple in manifest["layouts"]:
        t1 = sorted(float(target.qubit_properties[q].t1) for q in triple)
        arm_b.append(
            transpile_layout(
                ghz_idle_circuit(round(0.5 * t1[1] / dt)), tuple(triple), target, seed=SEED
            )
        )

    print(
        "1. Job 1's shape: seven Arm A circuits, alone against one run "
        "(shot noise about 0.011 per rate)"
    )
    batch = sim.run(arm_a, shots=SHOTS, seed_simulator=SEED).result()
    worst = 0.0
    for k, circuit in enumerate(arm_a):
        n = len(circuit.metadata["qubits"])
        alone = rates(
            sim.run(circuit, shots=SHOTS, seed_simulator=SEED + 100000 * (k + 1))
            .result()
            .get_counts(),
            n,
        )
        together = rates(batch.get_counts(k), n)
        gap = float(np.max(np.abs(alone - together)))
        worst = max(worst, gap)
        print(f"  slot {k} {SLOTS[k][0]:14s} {n:2d} qubits, largest rate gap {gap:.3f}", flush=True)
    print(f"  worst {worst:.3f}", flush=True)

    print("2. The full job's shape, 13 circuits in one run, Arm A first: each Arm B result")
    batch = sim.run(arm_a + arm_b, shots=SHOTS, seed_simulator=SEED).result()
    for i, circuit in enumerate(arm_b):
        alone = sim.run(circuit, shots=SHOTS, seed_simulator=SEED).result().get_counts()
        print(f"  layout {manifest['layouts'][i]}", flush=True)
        b_line("alone", alone)
        b_line("after 7 Arm A in one run", batch.get_counts(len(arm_a) + i))

    print("3. Six Arm B alone against one run")
    batch = sim.run(arm_b, shots=SHOTS, seed_simulator=SEED).result()
    for i, circuit in enumerate(arm_b):
        alone = (
            sim.run(circuit, shots=SHOTS, seed_simulator=SEED + 7777 * (i + 1))
            .result()
            .get_counts()
        )
        b_line(f"layout {i} alone", alone)
        b_line(f"layout {i} batched", batch.get_counts(i))

    print("4. Trigger: what Aer reports, and does the method explain it?")
    a, b = arm_a[2], arm_b[0]
    alone = sim.run(b, shots=SHOTS, seed_simulator=SEED).result()
    print("  B alone  :", meta(alone, 0), flush=True)
    both = sim.run([a, b], shots=SHOTS, seed_simulator=SEED).result()
    print("  A then B :", meta(both, 0), flush=True)
    print("           :", meta(both, 1), flush=True)
    for method in ("density_matrix", "statevector"):
        b_line(
            f"B alone, method={method}",
            AerSimulator.from_backend(backend, method=method)
            .run(b, shots=SHOTS, seed_simulator=SEED)
            .result()
            .get_counts(),
        )
    b_line(
        "A then B, method=statevector",
        AerSimulator.from_backend(backend, method="statevector")
        .run([a, b], shots=SHOTS, seed_simulator=SEED)
        .result()
        .get_counts(1),
    )
    b_line(
        "A(zero delay) then B",
        sim.run([arm_a[0], b], shots=SHOTS, seed_simulator=SEED).result().get_counts(1),
    )
    b_line(
        "noiseless, A then B",
        AerSimulator().run([a, b], shots=SHOTS, seed_simulator=SEED).result().get_counts(1),
    )
    b_line(
        "noise_model=from_backend, A then B",
        AerSimulator(noise_model=NoiseModel.from_backend(backend))
        .run([a, b], shots=SHOTS, seed_simulator=SEED)
        .result()
        .get_counts(1),
    )


if __name__ == "__main__":
    main()
