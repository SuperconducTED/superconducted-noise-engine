"""Arm B's real predictions on archive days, through PR #140's own build_job. No QPU; laptop; provisional.

For each sampled day at 03:45 UTC: build_job (every eligible triple predicted under level, six chosen),
then predicted fidelity per predictor on the six, and a shot-free truth distribution on the six under world F
(each qubit's next changed T1 with T2 and readout from that same file). Output one pickle per day, resumable.
Usage: arm_b_days.py <repo> <ref> <step> [max_days]
"""

import json
import math
import os
import pickle
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import numpy as np

sys.path.insert(0, "C:/t135/new")
from scripts.hardware_reading_vs_level import (
    QubitSource,
    UnusableSourceError,
    apply_readout,
    build_job,
    build_predictor_noise,
    gate_table,
    shot_free_distribution,
)
from scripts.hardware_test_predictors import (
    QUANTITIES,
    execution_rows,
    predictor_rows,
    select_balanced,
)

REPO, REF, STEP = sys.argv[1], sys.argv[2], int(sys.argv[3])
MAX_DAYS = int(sys.argv[4]) if len(sys.argv) > 4 else 10**6
CONTROLS = [144, 110, 140, 77]
OUT = "C:/t135/cache/armb"
os.makedirs(OUT, exist_ok=True)
env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
CONFIG = pickle.load(open("C:/t135/cache/config_scan.pkl", "rb"))
c = pickle.load(open("C:/t135/cache/collected.pkl", "rb"))
files = sorted(c.files, key=lambda r: (r.time, r.path))
ts = np.array([f.time.timestamp() for f in files])
iT1, iT2, ie10, ie01 = [
    QUANTITIES.index(x) for x in ("T1", "T2", "prob_meas0_prep1", "prob_meas1_prep0")
]
start = datetime(2026, 6, 13, 3, 45, tzinfo=UTC)
days = [start + timedelta(days=i) for i in range(0, 137, STEP)][:MAX_DAYS]
if len(sys.argv) > 5 and sys.argv[5] == "rev":
    days = days[::-1]  # a second process from the other end; a finished day is skipped by its file


def next_source(q, t_s, reading):
    lo = int(np.searchsorted(ts, t_s.timestamp(), side="right"))
    for f in files[lo:]:
        v = float(f.values[q, iT1])
        if math.isfinite(v) and v > 0 and v != reading:
            return QubitSource(
                v, float(f.values[q, iT2]), float(f.values[q, ie10]), float(f.values[q, ie01])
            )
    return None


for t_s in days:
    path = f"{OUT}/{t_s.date()}.pkl"
    if os.path.exists(path):
        continue
    t0 = time.time()
    rows = predictor_rows(c, at=t_s, live=None)
    execution = execution_rows(c, at=t_s, live=None)
    selection = select_balanced(rows, k=8, controls=set(CONTROLS))
    i = int(np.searchsorted(ts, t_s.timestamp(), side="right")) - 1
    snap = json.loads(
        subprocess.run(
            ["git", "-C", REPO, "show", f"{REF}:{files[i].path}"],
            check=True,
            capture_output=True,
            env=env,
        ).stdout
    )
    # 33 of 138 such files have configuration null (config_scan.py), and archived_backend raises on them.
    # Take the configuration only from the nearest earlier file that has one; properties stay this file's.
    if not isinstance(snap.get("configuration"), dict):
        j = next(k for k in range(i, -1, -1) if CONFIG[files[k].path])
        snap["configuration"] = json.loads(
            subprocess.run(
                ["git", "-C", REPO, "show", f"{REF}:{files[j].path}"],
                check=True,
                capture_output=True,
                env=env,
            ).stdout
        )["configuration"]
    job = build_job(
        rows=rows,
        execution=execution,
        selection=selection,
        controls=CONTROLS,
        snapshot=snap,
        t_s=t_s,
    )
    gates = gate_table(snap["properties"])
    out = {
        "t_s": t_s,
        "layouts": job.layouts,
        "predicted": job.arm_b_predicted,
        "log": job.layout_log,
        "truth_F": [],
        "truth_level": [],
        "truth_reading": [],
    }
    for triple, circuit in zip(job.layouts, job.arm_b, strict=True):
        srcs = {q: next_source(q, t_s, job.sources["reading"][q].t1) for q in triple}
        dist = None
        if all(s is not None and s.usable_for_relaxation() for s in srcs.values()):
            try:
                model = build_predictor_noise(
                    srcs, qubits=triple, gates=gates, dt=job.dt, n_qubits=job.n_qubits
                )
                dist = apply_readout(
                    shot_free_distribution(circuit, model, triple),
                    [srcs[q].e10 for q in triple],
                    [srcs[q].e01 for q in triple],
                )
            except UnusableSourceError:
                dist = None
        out["truth_F"].append(dist)
        for name in ("level", "reading"):
            try:
                model = build_predictor_noise(
                    job.sources[name], qubits=triple, gates=gates, dt=job.dt, n_qubits=job.n_qubits
                )
                d2 = apply_readout(
                    shot_free_distribution(circuit, model, triple),
                    [job.sources[name][q].e10 for q in triple],
                    [job.sources[name][q].e01 for q in triple],
                )
            except UnusableSourceError:
                d2 = None
            out[f"truth_{name}"].append(d2)
    pickle.dump(out, open(path, "wb"))
    print(t_s.date(), "triples", job.layout_log, "secs", round(time.time() - t0), flush=True)
print("done")
