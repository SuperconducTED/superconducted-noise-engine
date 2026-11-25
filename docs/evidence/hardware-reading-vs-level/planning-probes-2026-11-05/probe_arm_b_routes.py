"""Why did Arm B read almost all 000 in local mode? Compare the routes on one layout. Local only.

Run from the offline half's root:
    PYTHONPATH=.;src python probe_arm_b_routes.py

Same snapshot and same transpiled circuit through:
  1. the committed dry run's route: AerSimulator(noise_model=NoiseModel.from_backend(backend));
  2. AerSimulator.from_backend(backend) called directly;
  3. SamplerV2(mode=AerSimulator.from_backend(backend)), local testing mode;
  4. SamplerV2(mode=AerSimulator(noise_model=...)), local testing mode on the dry run's simulator;
  5. a noiseless simulator, to confirm the circuit is a GHZ at all.
Also prints what local mode does to the circuit's delays.
"""

from __future__ import annotations

import json
from pathlib import Path

from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime import SamplerV2
from scripts.hardware_reading_vs_level import (
    GHZ_IDEAL,
    _counts_vector,
    _git_json,
    archived_backend,
    ghz_idle_circuit,
    hellinger_fidelity,
    transpile_layout,
)

E = Path("docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05")
SHOTS = 4096
SEED = 125


def show(label: str, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    vector = _counts_vector(counts, 3) / total
    fidelity = hellinger_fidelity(vector, GHZ_IDEAL)
    top = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:8])
    print(f"{label:48s} F {fidelity:.3f}  {top}", flush=True)


def main() -> None:
    manifest = json.loads((E / "manifest.json").read_text(encoding="utf-8"))
    snapshot = _git_json(Path("."), manifest["ref_sha"], manifest["reading_file"])
    backend = archived_backend(snapshot, "reading_snapshot")
    dt = float(backend.dt)
    triple = tuple(manifest["layouts"][0])
    t1 = sorted(float(backend.target.qubit_properties[q].t1) for q in triple)
    idle = round(0.5 * t1[1] / dt)
    print(
        f"layout {triple}; T1 {[round(x * 1e6, 1) for x in t1]} us; "
        f"idle {idle} dt = {idle * dt * 1e6:.1f} us",
        flush=True,
    )
    circuit = transpile_layout(ghz_idle_circuit(idle), triple, backend.target, seed=SEED)
    print("ops", dict(circuit.count_ops()), "creg", [c.name for c in circuit.cregs], flush=True)
    delays = [
        (i.operation.duration, i.operation.unit)
        for i in circuit.data
        if i.operation.name == "delay"
    ]
    print("delays in the circuit (duration, unit):", delays, flush=True)

    truth = NoiseModel.from_backend(backend)
    route1 = (
        AerSimulator(noise_model=truth)
        .run(circuit, shots=SHOTS, seed_simulator=SEED)
        .result()
        .get_counts()
    )
    show("1 dry run's route, noise_model=from_backend", route1)

    sim = AerSimulator.from_backend(backend)
    print(
        "  from_backend sim dt:",
        getattr(sim, "dt", None),
        "| options noise?",
        sim.options.noise_model is not None,
        flush=True,
    )
    route2 = sim.run(circuit, shots=SHOTS, seed_simulator=SEED).result().get_counts()
    show("2 AerSimulator.from_backend, direct", route2)

    options = {"default_shots": SHOTS, "simulator": {"seed_simulator": SEED}}
    pub = SamplerV2(mode=sim, options=options).run([circuit]).result()[0]
    show("3 SamplerV2 on from_backend sim", pub.data.meas.get_counts())

    sim4 = AerSimulator(noise_model=truth)
    pub = SamplerV2(mode=sim4, options=options).run([circuit]).result()[0]
    show("4 SamplerV2 on the dry run's simulator", pub.data.meas.get_counts())

    clean = AerSimulator().run(circuit, shots=SHOTS, seed_simulator=SEED).result().get_counts()
    show("5 noiseless", clean)

    print("\ncommitted dry run, truth 1, measured fidelity per layout:", flush=True)
    print(
        (E / "arm-b-truth1.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")[:2],
        flush=True,
    )


if __name__ == "__main__":
    main()
