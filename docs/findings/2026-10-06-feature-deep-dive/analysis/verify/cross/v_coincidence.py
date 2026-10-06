"""Independent check of the same-day coincidence claim (07 section 7.4) for sx-p10, T2-RO and T1-T2.

Own definition, deliberately not the owner's: causal EWMA with a FIXED weight (0.2, no
per-family tuning), innovation scaled by 1.4826 MAD, flag at 3 sd, operational day from
16:00 UTC. Lift against (a) a qubit-permutation null among qubits observed that day and
(b) a per-qubit circular time shift. Also reports the lift when the days before
2026-08-01 (hourly-polling coverage) and from it are separated, and a sx-p10 control with
a 2 sd threshold. Writes ``results/verify/cross/coincidence_check.json``.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = (
    Path(__file__).resolve().parents[3] / "results" / "verify" / "cross" / "coincidence_check.json"
)
OFFSET = 1.0 / 8192.0
H = 3.6e6
DAY = 24 * H
FIELD = {
    "T1": "q.T1",
    "T2": "q.T2",
    "RO": "q.readout_error",
    "p10": "q.prob_meas0_prep1",
    "sx": "g1.sx.gate_error",
}
SPLIT = np.datetime64("2026-08-01T00:00:00", "ms").astype("int64").astype(float)


def load(dd, name):
    mask = ddload.placeholder_error if name == "sx" else None
    out = {}
    for s in ddload.series(dd, FIELD[name], rule=ddload.MEASURED, mask=mask):
        y = np.asarray(s.y, float)
        t = np.asarray(s.t_ms, float)
        if name == "p10":
            z = np.log10(y + OFFSET)
        else:
            k = y > 0
            y, t = y[k], t[k]
            z = np.log10(y)
        o = np.argsort(t, kind="stable")
        if z.size > 10:
            out[int(s.entity)] = (t[o], z[o])
    return out


def innov(z, alpha=0.2):
    lvl = z[0]
    out = np.full(z.size, np.nan)
    for i in range(1, z.size):
        out[i] = z[i] - lvl
        lvl = lvl + alpha * (z[i] - lvl)
    return out


def flag_matrix(fam, day0, nd, sd, adverse_up):
    obs = np.zeros((nd, 156), bool)
    big = np.zeros((nd, 156), bool)
    for q, (t, z) in fam.items():
        inn = innov(z)
        ok = np.isfinite(inn)
        s = 1.4826 * np.median(np.abs(inn[ok] - np.median(inn[ok])))
        if s <= 0:
            continue
        d = np.floor((t - day0) / DAY).astype(int)
        for k in np.flatnonzero(ok):
            if 0 <= d[k] < nd:
                obs[d[k], q] = True
                if abs(inn[k]) / s > sd:
                    big[d[k], q] = True
    return obs, big


def perm_null(fa, oa, fb, ob, rng, reps, rows=None):
    both = oa & ob
    if rows is not None:
        both = both & rows[:, None]
    obs_count = int((fa & fb & both).sum())
    nulls = []
    for _ in range(reps):
        c = 0
        for d in np.flatnonzero(both.any(axis=1)):
            cols = np.flatnonzero(ob[d])
            vals = fb[d, cols].copy()
            rng.shuffle(vals)
            perm = dict(zip(cols, vals, strict=True))
            qs = np.flatnonzero(both[d] & fa[d])
            c += sum(perm[q] for q in qs)
        nulls.append(c)
    nulls = np.array(nulls)
    return obs_count, float(nulls.mean()), float((np.sum(nulls >= obs_count) + 1) / (reps + 1))


def shift_null(fa, oa, fb, ob, rng, reps):
    nd = fa.shape[0]
    both0 = oa & ob
    obs_count = int((fa & fb & both0).sum())
    nulls = []
    for _ in range(reps):
        offs = (rng.uniform(0.1, 0.9, 156) * nd).astype(int)
        idx = (np.arange(nd)[:, None] + offs[None, :]) % nd
        cols = np.arange(156)[None, :]
        fb2, ob2 = fb[idx, cols], ob[idx, cols]
        nulls.append(int((fa & fb2 & oa & ob2).sum()))
    nulls = np.array(nulls)
    return obs_count, float(nulls.mean()), float((np.sum(nulls >= obs_count) + 1) / (reps + 1))


def main():
    dd = ddload.DD()
    rng = np.random.default_rng(3)
    fams = {k: load(dd, k) for k in FIELD}
    t0 = min(v[0][0] for f in fams.values() for v in f.values())
    first = np.floor((t0 - 16 * H) / DAY) * DAY + 16 * H
    t1 = max(v[0][-1] for f in fams.values() for v in f.values())
    nd = int((t1 - first) / DAY) + 1
    day_start = first + np.arange(nd) * DAY
    early = day_start < SPLIT
    out = {"n_days": nd, "n_days_before_0801": int(early.sum()), "pairs": {}}
    for a, b, up_a, up_b in (
        ("sx", "p10", True, True),
        ("T2", "RO", False, True),
        ("sx", "RO", True, True),
        ("T1", "T2", False, False),
    ):
        for sd in (3.0, 2.0) if (a, b) == ("sx", "p10") else (3.0,):
            oa, fa = flag_matrix(fams[a], first, nd, sd, up_a)
            ob, fb = flag_matrix(fams[b], first, nd, sd, up_b)
            c, m, p = perm_null(fa, oa, fb, ob, rng, 200)
            c2, m2, p2 = shift_null(fa, oa, fb, ob, rng, 200)
            row = {
                "qubit_days_both_observed": int((oa & ob).sum()),
                "both_flagged": c,
                "qubit_null_mean": round(m, 2),
                "qubit_null_lift": round(c / m, 3),
                "qubit_null_p": p,
                "time_null_mean": round(m2, 2),
                "time_null_lift": round(c2 / m2, 3),
                "time_null_p": p2,
            }
            for lab, rows in (("before_0801", early), ("from_0801", ~early)):
                cc, mm, _pp = perm_null(fa, oa, fb, ob, rng, 100, rows)
                row[f"qubit_null_lift_{lab}"] = round(cc / mm, 3) if mm else None
                row[f"both_flagged_{lab}"] = cc
            out["pairs"][f"{a}-{b}@{sd}sd"] = row
            print(a, b, sd, row)
    payload = ddload.result_header("verify/cross", "analysis/verify/cross/v_coincidence.py")
    payload.update(out)
    ddload.write_json(OUT, payload)


if __name__ == "__main__":
    main()
