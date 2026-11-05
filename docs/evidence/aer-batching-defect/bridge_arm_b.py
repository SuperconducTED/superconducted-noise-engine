"""Tie the minimal defect back to this project's circuits, and to a public fake backend.

The one script in this folder that uses project code. Run from the root of a checkout of
`mert/issue-125-submission`, with `PYTHONPATH=.;src`:

    python -W ignore <this file>

Row H1 is a separate rerun of `probe_batching.py` against its committed output; see README
section 9.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import qiskit_aer
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_aer.noise.errors.quantum_error import QuantumError
from qiskit_ibm_runtime.fake_provider import FakeFez
from scripts.hardware_reading_vs_level import (
    _git_json,
    archived_backend,
    arm_a_circuit,
    ghz_idle_circuit,
    transpile_layout,
)

E = Path("docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05")
SHOTS = 2048
SEED = 125


def saved_probabilities(circuit: QuantumCircuit, qubits: list[int]) -> QuantumCircuit:
    """The same circuit with its probabilities saved in place of its final measurement."""
    out = circuit.remove_final_measurements(inplace=False)
    out.save_probabilities(qubits)
    return out


def noise_locations(circuit: QuantumCircuit, noise: NoiseModel) -> tuple[int, int]:
    """Noisy gates on the circuit, and channels the model's delay pass adds to it."""
    gates = 0
    local = noise._local_quantum_errors
    default = noise._default_quantum_errors
    for item in circuit.data:
        name = item.operation.name
        qubits = tuple(circuit.find_bit(q).index for q in item.qubits)
        if name in default or qubits in local.get(name, {}):
            gates += 1
    passes = noise._pass_manager()
    channels = 0
    if passes is not None:
        for item in passes.run(circuit).data:
            operation = item.operation
            if isinstance(operation, QuantumError) or operation.name == "quantum_channel":
                channels += 1
    return gates, channels


def line(label: str, result, index: int, reference: float | None = None) -> float:
    """Print one row; `reference` adds the sum's ratio to the same circuit run alone."""
    metadata = result.results[index].metadata
    total = float(np.sum(result.data(index)["probabilities"]))
    power = math.log2(total) if total > 0 else float("nan")
    ratio = "" if reference is None else f"  ratio to alone {total / reference:.12f}"
    print(
        f"  {label:18s} sum of probabilities {total:.12f}  log2 {power:.9f}  "
        f"method {metadata['method']}  noise {metadata.get('noise')}{ratio}",
        flush=True,
    )
    return total


def counts_line(label: str, counts: dict[str, int], shots: int) -> None:
    zeros = counts.get("000", 0) / shots
    ones = counts.get("111", 0) / shots
    print(f"  {label:28s} 000 {zeros:.3f}  111 {ones:.3f}", flush=True)


def h2() -> None:
    print("H2. Arm B after Arm A on the archived ibm_fez model", flush=True)
    manifest = json.loads((E / "manifest.json").read_text(encoding="utf-8"))
    snapshot = _git_json(Path("."), manifest["ref_sha"], manifest["reading_file"])
    backend = archived_backend(snapshot, "reading_snapshot")
    dt, target = float(backend.dt), backend.target
    sim = AerSimulator.from_backend(backend)
    noise = sim.options.noise_model

    slots = {int(q): s for q, s in manifest["slots_dt"].items()}
    x_len = {q: round(float(target["x"][(q,)].duration) / dt) for q in slots}
    arm_a = arm_a_circuit(2, {q: slots[q][2] for q in slots}, x_len, backend.num_qubits)
    for triple in manifest["layouts"]:
        t1 = sorted(float(target.qubit_properties[q].t1) for q in triple)
        arm_b = transpile_layout(
            ghz_idle_circuit(round(0.5 * t1[1] / dt)), tuple(triple), target, seed=SEED
        )
        saved = saved_probabilities(arm_b, list(triple))
        gates, channels = noise_locations(arm_b, noise)
        print(f" layout {triple}: noisy gates {gates}, delay channels {channels}", flush=True)
        alone = line("alone", sim.run(saved, shots=SHOTS, seed_simulator=SEED).result(), 0)
        before = sim.run([saved, arm_a], shots=SHOTS, seed_simulator=SEED).result()
        line("before Arm A", before, 0, alone)
        after = sim.run([arm_a, saved], shots=SHOTS, seed_simulator=SEED).result()
        line("after Arm A", after, 1, alone)


def h3() -> None:
    print("H3. A public fake backend, no project circuits", flush=True)
    fake = FakeFez()
    ghz = QuantumCircuit(3)
    ghz.h(0)
    ghz.cx(0, 1)
    ghz.cx(1, 2)
    ghz.measure_all()
    big = QuantumCircuit(12)
    big.h(0)
    for q in range(11):
        big.cx(q, q + 1)
    big.measure_all()
    ghz_t = transpile(ghz, fake, optimization_level=1, seed_transpiler=SEED)
    big_t = transpile(big, fake, optimization_level=1, seed_transpiler=SEED)

    sim = AerSimulator.from_backend(fake)
    print(f" from_backend, {SHOTS} shots", flush=True)
    alone = sim.run(ghz_t, shots=SHOTS, seed_simulator=SEED).result()
    after = sim.run([big_t, ghz_t], shots=SHOTS, seed_simulator=SEED).result()
    counts_line("alone", alone.get_counts(0), SHOTS)
    counts_line("after a 12-qubit circuit", after.get_counts(1), SHOTS)
    print(
        "  methods",
        alone.results[0].metadata["method"],
        "|",
        after.results[0].metadata["method"],
        after.results[1].metadata["method"],
        flush=True,
    )
    print(f" FakeFez().run, {SHOTS} shots", flush=True)
    alone = fake.run(ghz_t, shots=SHOTS, seed_simulator=SEED).result()
    after = fake.run([big_t, ghz_t], shots=SHOTS, seed_simulator=SEED).result()
    counts_line("alone", alone.get_counts(0), SHOTS)
    counts_line("after a 12-qubit circuit", after.get_counts(1), SHOTS)


def main() -> int:
    print(f"qiskit-aer {qiskit_aer.__version__}", flush=True)
    h2()
    h3()
    return 0


if __name__ == "__main__":
    sys.exit(main())
