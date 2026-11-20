"""Planning probes for #125 step 1d on the real archive. No network, no token, writes nothing.

Run from the offline half's root:
    PYTHONPATH=.;src python probe_build_time.py <controls.json>

1. How long would `build` take at 03:45 UTC? Same calls as the offline half's main, up to build_job,
   with execution rows faked from the same collection because they do not exist at t_s.
2. Does the live-properties path run end to end? The latest snapshot's properties, re-wrapped as a
   raw
   to_dict() body, go through predictor_rows(live=...).
3. Do Arm B's circuits pass the Runtime's ISA check, and does local mode run both arms on an
   AerSimulator built from the archived snapshot? Which job metrics exist in local mode?
"""

from __future__ import annotations

import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2
from qiskit_ibm_runtime.utils.validations import validate_isa_circuits
from scripts.hardware_reading_vs_level import (
    GHZ_IDEAL,
    _counts_vector,
    _git_json,
    archived_backend,
    build_job,
    hellinger_fidelity,
)
from scripts.hardware_test_predictors import (
    collect,
    execution_rows,
    load_controls,
    normalise_live,
    predictor_rows,
    select_balanced,
)

from superconducted.training.dataset import iter_archive, resolve_archive_ref

REF = "5828b4a29fabc245aa096e530852249a3496dc5b"
T_S = datetime.fromisoformat("2026-10-23T09:34:56+00:00")


def stamp(label: str, start: float) -> float:
    now = time.perf_counter()
    print(f"{label:36s} {now - start:8.1f} s", flush=True)
    return now


def main(controls_path: str) -> None:
    repo = Path(".")
    begin = time.perf_counter()
    doc, _sha = load_controls(Path(controls_path), backend="ibm_fez")
    controls = [int(c["qubit"]) for c in doc["controls"]]
    sha = resolve_archive_ref(repo, REF)
    t = stamp("controls and ref", begin)
    collected = collect(iter_archive(repo, sha), backend="ibm_fez", until=T_S)
    t = stamp("archive walk", t)
    rows = predictor_rows(collected, at=T_S, live=None)
    selection = select_balanced(rows, k=8, controls=set(controls))
    execution = execution_rows(collected, at=T_S, live=None)
    t = stamp("predictors and selection", t)
    reading_file = [f for f in collected.files if f.time <= T_S][-1]
    snapshot = _git_json(repo, sha, reading_file.path)
    t = stamp("snapshot", t)
    job = build_job(
        rows=rows,
        execution=execution,
        selection=selection,
        controls=controls,
        snapshot=snapshot,
        t_s=T_S,
    )
    t = stamp("build_job (circuits, predictions)", t)
    print(f"layout log {job.layout_log}; layouts {job.layouts}", flush=True)
    print(f"BUILD TOTAL {t - begin:.1f} s", flush=True)

    print("\n--- live path", flush=True)
    raw = dict(snapshot["properties"])
    assert "qubits" in raw and "last_update_date" in raw, sorted(raw)[:8]
    assert normalise_live(raw, backend="ibm_fez")["backend"] == "ibm_fez"
    live_rows = predictor_rows(collected, at=T_S, live=raw)
    assert live_rows, "no rows from the live path"
    diffs = 0
    for a, b in zip(rows, live_rows, strict=True):
        same = all(
            getattr(a, f) == getattr(b, f)
            or (getattr(a, f) != getattr(a, f) and getattr(b, f) != getattr(b, f))
            for f in (
                "qubit",
                "quantity",
                "reading",
                "level",
                "band_lo",
                "band_hi",
                "n_window",
                "n_distinct",
            )
        )
        diffs += not same
    print(f"rows {len(rows)}, differing with the same state fed as live: {diffs}", flush=True)
    t = stamp("live path", t)

    print("\n--- ISA, both arms, against the archived target", flush=True)
    backend = archived_backend(snapshot, "reading_snapshot")
    for label, circuits in (("arm_a", job.arm_a), ("arm_b", job.arm_b)):
        try:
            validate_isa_circuits(circuits, backend.target)
            print(f"{label}: accepted, {len(circuits)} circuits", flush=True)
        except Exception as exc:
            print(f"{label}: REFUSED {type(exc).__name__}: {str(exc)[:240]}", flush=True)
    t = stamp("ISA checks", t)

    print("\n--- local mode on AerSimulator.from_backend(archived snapshot)", flush=True)
    sim = AerSimulator.from_backend(backend)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sampler = SamplerV2(
            mode=sim, options={"default_shots": 256, "simulator": {"seed_simulator": 125}}
        )
        sampled = sampler.run([job.arm_a[2], job.arm_b[0]])
        result = sampled.result()
    for w in caught[:3]:
        print("warning:", str(w.message)[:150], flush=True)
    t = stamp("local mode run", t)
    a_pub, b_pub = result[0], result[1]
    a_counts = getattr(a_pub.data, next(iter(a_pub.data.keys()))).get_counts()
    b_counts = getattr(b_pub.data, next(iter(b_pub.data.keys()))).get_counts()
    print(
        "arm A registers", list(a_pub.data.keys()), "distinct outcomes", len(a_counts), flush=True
    )
    print(
        "arm B registers",
        list(b_pub.data.keys()),
        "counts",
        dict(sorted(b_counts.items())),
        flush=True,
    )
    vector = _counts_vector(b_counts, 3)
    print(
        f"arm B fidelity at 256 shots {hellinger_fidelity(vector / vector.sum(), GHZ_IDEAL):.3f}",
        flush=True,
    )
    print("metrics() in local mode:", end=" ", flush=True)
    try:
        print(sampled.metrics(), flush=True)
    except Exception as exc:
        print("unavailable:", type(exc).__name__, str(exc)[:120], flush=True)
    print("usage() in local mode:", end=" ", flush=True)
    try:
        print(sampled.usage(), flush=True)
    except Exception as exc:
        print("unavailable:", type(exc).__name__, str(exc)[:120], flush=True)
    print("job methods:", [m for m in dir(sampled) if not m.startswith("_")][:30], flush=True)
    print(
        f"\nTOTAL {time.perf_counter() - begin:.1f} s; numpy {np.__version__}; RUN END", flush=True
    )


if __name__ == "__main__":
    main(sys.argv[1])
