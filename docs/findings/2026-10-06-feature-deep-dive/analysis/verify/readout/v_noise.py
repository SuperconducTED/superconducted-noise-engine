# ruff: noqa: N806
"""Independent re-computation of the session kinds and the shot-noise comparison of 03.

Written from ddload only. Recomputes: readout sessions (15 min gap) and their parity kinds,
the share of even sessions near a T1 round, the standardized change statistics of RO for
intraday session pairs (consecutive and 2 to 4 h), and a simulation placebo: iid binomial
counts at each qubit's own median error, run through the same plug-in standardization, to
measure how far the statistic sits above 1 when there is NO excess.

Writes ``results/verify/readout/noise_check.json``.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "readout" / "noise_check.json"
WIN = 10 * 60e3
GAP = 15 * 60e3
N = 4096
H = 3.6e6
C = 0.4549  # median of chi-square(1)


def stamp_events(v, d):
    out = []
    for e in range(v.shape[1]):
        ok = np.flatnonzero(np.isfinite(v[:, e]) & np.isfinite(d[:, e]))
        dd_ = d[ok, e]
        keep = np.concatenate([[True], dd_[1:] != dd_[:-1]])
        out.append(ok[keep])
    return out


def main() -> None:
    dd = ddload.DD()
    ro = np.array(dd.v("q.readout_error"), float)
    a = np.array(dd.v("q.prob_meas0_prep1"), float)
    b = np.array(dd.v("q.prob_meas1_prep0"), float)
    dro = np.array(dd.d("q.readout_error"), float)
    da = np.array(dd.d("q.prob_meas0_prep1"), float)
    db = np.array(dd.d("q.prob_meas1_prep0"), float)
    a_fresh = np.abs(dro - da) <= WIN
    b_fresh = np.abs(dro - db) <= WIN
    present = np.isfinite(ro) & np.isfinite(a) & np.isfinite(b)
    # fresh P(0|1): published if fresh, else 2 RO - P(1|0) when P(1|0) is fresh
    pa = np.full(ro.shape, np.nan)
    pa[present & a_fresh] = a[present & a_fresh]
    imp = present & ~a_fresh & b_fresh
    pa[imp] = 2 * ro[imp] - b[imp]
    pb = np.where(present & b_fresh, b, np.nan)

    ev = stamp_events(ro, dro)
    T, Q, F = [], [], []
    for e, idx in enumerate(ev):
        T.append(dro[idx, e])
        Q.append(np.full(idx.size, e))
        F.append(idx)
    T, Q, F = np.concatenate(T), np.concatenate(Q), np.concatenate(F)
    o = np.argsort(T, kind="stable")
    T, Q, F = T[o], Q[o], F[o]
    br = np.flatnonzero(np.diff(T) > GAP)
    starts = np.concatenate([[0], br + 1])
    ends = np.concatenate([br + 1, [T.size]])
    sess_of = np.empty(T.size, int)
    kinds = []
    nq_list = []
    start_t = []
    for s, (x, y) in enumerate(zip(starts, ends, strict=True)):
        sess_of[x:y] = s
        k = np.concatenate([pa[F[x:y], Q[x:y]], pb[F[x:y], Q[x:y]]]) * N
        k = k[np.isfinite(k)]
        nq = np.unique(Q[x:y]).size
        nq_list.append(nq)
        start_t.append(T[x])
        if nq < 100:
            kinds.append("small")
        elif k.size and np.all(np.round(k) % 2 == 0):
            kinds.append("even")
        else:
            kinds.append("mixed")
    kinds = np.array(kinds)
    out: dict = ddload.result_header("verify/readout", "v_noise.py")
    out["sessions_total"] = len(kinds)
    out["sessions_ge100_qubits"] = int((np.array(nq_list) >= 100).sum())
    out["sessions_even"] = int((kinds == "even").sum())
    out["sessions_mixed"] = int((kinds == "mixed").sum())
    out["sessions_small"] = int((kinds == "small").sum())

    # T1 rounds: stamp-change times of T1 (any qubit)
    t1v = np.array(dd.v("q.T1"), float)
    t1d = np.array(dd.d("q.T1"), float)
    t1_times = np.unique(t1d[np.isfinite(t1d)])
    # keep one time per cluster at 15 min gaps
    t1_times = np.sort(t1_times)
    br1 = np.flatnonzero(np.diff(t1_times) > GAP)
    round_t = t1_times[np.concatenate([[0], br1 + 1])]
    st = np.array(start_t)
    near = np.array([np.min(np.abs(round_t - t)) <= 3 * H for t in st])
    out["t1_rounds"] = int(round_t.size)
    out["even_near_t1_round_share"] = round(float(near[kinds == "even"].mean()), 4)
    out["mixed_near_t1_round_share"] = round(float(near[kinds == "mixed"].mean()), 4)
    del t1v

    # RO events in mixed sessions, standardized pairs
    ro_var = (pa * (1 - pa) + pb * (1 - pb)) / (4 * N)
    zs_cons, zs_24 = [], []
    n_qubits_used = 0
    for e in range(ro.shape[1]):
        m = (e == Q) & (kinds[sess_of] == "mixed")
        if m.sum() < 3:
            continue
        f = F[m]
        # collapse re-stamps inside a session: keep last per session
        s_ids = sess_of[m]
        keep = np.concatenate([s_ids[1:] != s_ids[:-1], [True]])
        f, s_ids = f[keep], s_ids[keep]
        y = ro[f, e]
        v = ro_var[f, e]
        t = dro[f, e] / H
        good = np.isfinite(v)
        y, v, t = y[good], v[good], t[good]
        if y.size < 3:
            continue
        n_qubits_used += 1
        zs_cons.append((y[1:] - y[:-1]) / np.sqrt(v[1:] + v[:-1]))
        iu, ju = np.triu_indices(y.size, 1)
        lag = t[ju] - t[iu]
        sel = (lag >= 2) & (lag < 4)
        zs_24.append((y[ju] - y[iu])[sel] / np.sqrt((v[ju] + v[iu])[sel]))
    zc = np.concatenate(zs_cons)
    z2 = np.concatenate(zs_24)
    out["qubits_used"] = n_qubits_used
    out["consecutive_mixed_pairs_n"] = int(zc.size)
    out["consecutive_mixed_share_abs_z_lt2"] = round(float((np.abs(zc) < 2).mean()), 4)
    out["consecutive_mixed_robust_ratio"] = round(float(np.median(zc**2) / C), 3)
    out["pairs_2to4h_n"] = int(z2.size)
    out["pairs_2to4h_robust_ratio"] = round(float(np.median(z2**2) / C), 3)
    out["pairs_2to4h_mean_z2"] = round(float(np.mean(z2**2)), 3)

    # placebo: iid binomial counts at each qubit's own median (pa, pb), same plug-in rule
    rng = np.random.default_rng(11)
    sim = []
    for e in range(ro.shape[1]):
        m = (e == Q) & (kinds[sess_of] == "mixed")
        n = int(m.sum())
        if n < 3:
            continue
        mp_a = np.nanmedian(pa[F[m], e])
        mp_b = np.nanmedian(pb[F[m], e])
        if not (np.isfinite(mp_a) and np.isfinite(mp_b)):
            continue
        ka = rng.binomial(N, mp_a, size=n) / N
        kb = rng.binomial(N, mp_b, size=n) / N
        y = (ka + kb) / 2
        v = (ka * (1 - ka) + kb * (1 - kb)) / (4 * N)
        den = np.sqrt(v[1:] + v[:-1])
        ok = den > 0
        sim.append((y[1:] - y[:-1])[ok] / den[ok])
    zsim = np.concatenate(sim)
    out["placebo_iid_binomial_pairs_n"] = int(zsim.size)
    out["placebo_iid_share_abs_z_lt2"] = round(float((np.abs(zsim) < 2).mean()), 4)
    out["placebo_iid_robust_ratio"] = round(float(np.median(zsim**2) / C), 3)
    # placebo with the TRUE variance (no plug-in) for reference
    sim2 = []
    for e in range(ro.shape[1]):
        m = (e == Q) & (kinds[sess_of] == "mixed")
        n = int(m.sum())
        if n < 3:
            continue
        mp_a = np.nanmedian(pa[F[m], e])
        mp_b = np.nanmedian(pb[F[m], e])
        if not (np.isfinite(mp_a) and np.isfinite(mp_b)):
            continue
        ka = rng.binomial(N, mp_a, size=n) / N
        kb = rng.binomial(N, mp_b, size=n) / N
        y = (ka + kb) / 2
        tv = (mp_a * (1 - mp_a) + mp_b * (1 - mp_b)) / (4 * N)
        if tv <= 0:
            continue
        sim2.append((y[1:] - y[:-1]) / np.sqrt(2 * tv))
    zs2 = np.concatenate(sim2)
    out["placebo_iid_true_var_robust_ratio"] = round(float(np.median(zs2**2) / C), 3)
    ddload.write_json(OUT, out)
    print("ok")


main()
