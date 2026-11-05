"""Does batching circuits into one run change an Arm B result? Local only.

Run from the offline half's root:
    PYTHONPATH=.;src python probe_batching.py

The same Arm B circuit: alone, after a 12-qubit Arm A circuit in one Aer run, and after it in one
SamplerV2 run. Then the order reversed. A real job sends up to 13 circuits in one submission, while
the
committed dry run sends one circuit per run, so this has never been exercised.
"""

from __future__ import annotations

import json
from pathlib import Path

from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2
from scripts.hardware_reading_vs_level import (
    GHZ_IDEAL,
    _counts_vector,
    _git_json,
    archived_backend,
    arm_a_circuit,
    ghz_idle_circuit,
    hellinger_fidelity,
    transpile_layout,
)

E = Path("docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05")
SHOTS = 2048
SEED = 125


def line(label: str, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    vector = _counts_vector(counts, 3) / total
    print(
        f"{label:44s} F {hellinger_fidelity(vector, GHZ_IDEAL):.3f}  "
        f"000 {counts.get('000', 0) / total:.3f}  111 {counts.get('111', 0) / total:.3f}  "
        f"shots {total}",
        flush=True,
    )


def main() -> None:
    manifest = json.loads((E / "manifest.json").read_text(encoding="utf-8"))
    snapshot = _git_json(Path("."), manifest["ref_sha"], manifest["reading_file"])
    backend = archived_backend(snapshot, "reading_snapshot")
    dt = float(backend.dt)
    target = backend.target
    triple = tuple(manifest["layouts"][0])
    t1 = sorted(float(target.qubit_properties[q].t1) for q in triple)
    idle = round(0.5 * t1[1] / dt)
    arm_b = transpile_layout(ghz_idle_circuit(idle), triple, target, seed=SEED)

    slots = {int(q): s for q, s in manifest["slots_dt"].items()}
    x_len = {q: round(float(target["x"][(q,)].duration) / dt) for q in slots}
    k = 2
    arm_a = arm_a_circuit(k, {q: slots[q][k] for q in slots}, x_len, backend.num_qubits)
    print(
        "arm A qubits", arm_a.metadata["qubits"], "creg", [c.name for c in arm_a.cregs], flush=True
    )

    sim = AerSimulator.from_backend(backend)
    line("Aer, alone", sim.run(arm_b, shots=SHOTS, seed_simulator=SEED).result().get_counts())
    together = sim.run([arm_a, arm_b], shots=SHOTS, seed_simulator=SEED).result()
    line("Aer, [A, B] in one run", together.get_counts(1))
    together = sim.run([arm_b, arm_a], shots=SHOTS, seed_simulator=SEED).result()
    line("Aer, [B, A] in one run", together.get_counts(0))

    options = {"default_shots": SHOTS, "simulator": {"seed_simulator": SEED}}
    alone = SamplerV2(mode=sim, options=options).run([arm_b]).result()[0]
    line("Sampler, alone", alone.data.meas.get_counts())
    both = SamplerV2(mode=sim, options=options).run([arm_a, arm_b]).result()
    line("Sampler, [A, B] in one job", both[1].data.meas.get_counts())
    both = SamplerV2(mode=sim, options=options).run([arm_b, arm_a]).result()
    line("Sampler, [B, A] in one job", both[0].data.meas.get_counts())

    print("\nsame with job-style shots per pub, Arm A 2048 and Arm B 4096", flush=True)
    both = (
        SamplerV2(mode=sim, options={"simulator": {"seed_simulator": SEED}})
        .run([(arm_a, None, 2048), (arm_b, None, 4096)])
        .result()
    )
    line("Sampler, per-pub shots", both[1].data.meas.get_counts())

    print("\nArm A's own rates in the batched job against alone (first 4 qubits)", flush=True)
    a_alone = SamplerV2(mode=sim, options=options).run([arm_a]).result()[0].data.c.get_counts()
    a_batch = (
        SamplerV2(mode=sim, options=options).run([arm_a, arm_b]).result()[0].data.c.get_counts()
    )
    n = len(arm_a.metadata["qubits"])
    for label, counts in (("alone", a_alone), ("batched", a_batch)):
        vector = _counts_vector(counts, n)
        rates = [
            round(sum(v for idx, v in enumerate(vector) if (idx >> i) & 1) / SHOTS, 3)
            for i in range(4)
        ]
        print(f"  {label:8s} {rates}", flush=True)


if __name__ == "__main__":
    main()
