"""Planning probes for #125 step 1d: no network, no token. Run from the offline half's root.

    PYTHONPATH=.;src python probe_local_mode.py <dry-run manifest.json>

A. Does IBM's local testing mode run an Arm A circuit from the offline half, under explicit options?
B. Does the Runtime's own ISA check accept it? Does the clbit order survive SamplerV2's BitArray?
C. What does one job cost in shot time, from a committed dry run's real delays?
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

from qiskit_ibm_runtime import SamplerV2
from qiskit_ibm_runtime.fake_provider import FakeFez
from qiskit_ibm_runtime.options import SamplerOptions
from qiskit_ibm_runtime.utils.validations import validate_isa_circuits
from scripts.hardware_reading_vs_level import (
    ARM_A_SHOTS,
    ARM_B_SHOTS,
    SLOTS,
    _counts_vector,
    arm_a_circuit,
)


def main(manifest_path: str) -> None:
    backend = FakeFez()
    dt = float(backend.dt)
    qubits = [3, 17, 40]
    x_len = {q: round(float(backend.target["x"][(q,)].duration) / dt) for q in qubits}
    # Slot 0 is the zero delay; qubit 40 is left out by giving it a long decay in a second circuit.
    zero = arm_a_circuit(0, dict.fromkeys(qubits, 0), x_len, backend.num_qubits)
    long_tau = round(600e-6 / dt)
    decayed = arm_a_circuit(5, {3: 0, 17: 0, 40: long_tau}, x_len, backend.num_qubits)

    print("A. ISA check")
    try:
        validate_isa_circuits([zero, decayed], backend.target)
        print("   validate_isa_circuits accepted both")
    except Exception as exc:
        print("   REFUSED:", type(exc).__name__, str(exc)[:220])

    print("B. local testing mode, explicit options")
    options = SamplerOptions()
    options.default_shots = 512
    options.execution.init_qubits = True
    options.execution.rep_delay = 0.00025
    options.execution.meas_type = "classified"
    options.dynamical_decoupling.enable = False
    options.twirling.enable_gates = False
    options.twirling.enable_measure = False
    options.simulator.seed_simulator = 125
    options.environment.job_tags = ["probe-1d"]
    start = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sampler = SamplerV2(mode=backend, options=options)
        job = sampler.run([zero, decayed])
        result = job.result()
    print(f"   ran in {time.perf_counter() - start:.1f} s; job id {job.job_id()!r}")
    for w in caught[:4]:
        print("   warning:", str(w.message)[:150])
    for label, circuit, pub in zip(("zero", "decayed"), (zero, decayed), result, strict=True):
        names = [c.name for c in circuit.cregs]
        registers = list(pub.data.keys())
        counts = getattr(pub.data, registers[0]).get_counts()
        vector = _counts_vector(counts, len(circuit.metadata["qubits"]))
        total = int(vector.sum())
        rates = {
            q: round(sum(v for idx, v in enumerate(vector) if (idx >> i) & 1) / total, 3)
            for i, q in enumerate(circuit.metadata["qubits"])
        }
        print(
            f"   {label}: cregs {names}, data keys {registers}, shots {total}, p_1 by qubit {rates}"
        )
    print("   expected: every p_1 near 1 at zero; only qubit 40 lower in 'decayed'")

    print("C. shot time per job, from", Path(manifest_path).parent.name)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    slots = {int(q): s for q, s in manifest["slots_dt"].items()}
    measure_s = float(backend.target["measure"][(0,)].duration)
    x_s = float(backend.target["x"][(0,)].duration)
    print(
        f"   dt {dt:g} s; measure {measure_s * 1e6:.2f} us; x {x_s * 1e9:.0f} ns; "
        f"qubits {len(slots)}"
    )
    horizons = []
    for k, (name, _source, _factor) in enumerate(SLOTS):
        longest = max((s[k] or 0) for s in slots.values()) * dt
        horizons.append(longest + x_s + measure_s)
        print(f"   slot {k} {name:14s} longest delay {longest * 1e6:8.1f} us")
    for rep_delay in (0.00025, 0.0005):
        a = sum(ARM_A_SHOTS * (h + rep_delay) for h in horizons)
        # Arm B: six layouts, idle about half a typical level T1 plus gates and measure; rough.
        b = 6 * ARM_B_SHOTS * (100e-6 + measure_s + rep_delay)
        print(
            f"   rep_delay {rep_delay * 1e6:.0f} us: Arm A {a:5.1f} s, Arm B about {b:5.1f} s, "
            f"job with both about {a + b:5.1f} s; 14 jobs (job 1 Arm A only) about "
            f"{(a + 13 * (a + b)) / 60:4.1f} min"
        )
    print("   shot time only: per-circuit and per-job overhead is unmeasured until job 1")


if __name__ == "__main__":
    main(sys.argv[1])
