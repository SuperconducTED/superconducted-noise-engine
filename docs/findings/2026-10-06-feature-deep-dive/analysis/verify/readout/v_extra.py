# ruff: noqa: N806
"""Refutation probes for 03-readout-measurement.md, written from ddload only.

Probes: (1) is the checkerboard of RO just the degree-2 versus degree-3 split of the heavy-hex
lattice; (2) freshness of the rotating group's P(0|1) in daily (even) versus intraday
sessions; (3) does the asymmetry A at the 2026-06-08 length change leave the placebo range,
and how does the observed change compare with the decay predicted from the full and the half
window; (4) the P(1|0) weekday test at the session level (one value per session).

Writes ``results/verify/readout/extra_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import kruskal, mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "readout" / "extra_check.json"
H = 3.6e6
DAY = 24 * H
WIN = 10 * 60e3
GAP = 15 * 60e3


def moran(x, w, rng, perms=5000):
    n = x.size
    z = x - x.mean()
    s = w.sum()

    def stat(zz):
        return (n / s) * (zz @ w @ zz) / (zz @ zz)

    obs = stat(z)
    null = np.array([stat(rng.permutation(z)) for _ in range(perms)])
    p = (1 + np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean()))) / (perms + 1)
    return float(obs), float(p)


def stamp_idx(v, d, e):
    ok = np.flatnonzero(np.isfinite(v[:, e]) & np.isfinite(d[:, e]))
    x = d[ok, e]
    return ok[np.concatenate([[True], x[1:] != x[:-1]])]


def main() -> None:
    dd = ddload.DD()
    ro = np.array(dd.v("q.readout_error"), float)
    a = np.array(dd.v("q.prob_meas0_prep1"), float)
    b = np.array(dd.v("q.prob_meas1_prep0"), float)
    dro = np.array(dd.d("q.readout_error"), float)
    da = np.array(dd.d("q.prob_meas0_prep1"), float)
    db = np.array(dd.d("q.prob_meas1_prep0"), float)
    nq = ro.shape[1]
    out: dict = ddload.result_header("verify/readout", "v_extra.py")
    rng = np.random.default_rng(5)

    # (1) degree split
    edges = sorted({tuple(sorted(e)) for e in dd.meta["coupling_map"]})
    deg = np.zeros(nq, int)
    w = np.zeros((nq, nq))
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
        w[i, j] = w[j, i] = 1
    medro = np.array([np.median(ro[stamp_idx(ro, dro, e), e]) for e in range(nq)])
    x = np.log10(medro)
    out["degree_counts"] = {str(k): int((deg == k).sum()) for k in np.unique(deg)}
    out["median_ro_by_degree"] = {
        str(k): round(float(np.median(medro[deg == k])), 5) for k in np.unique(deg)
    }
    kw = kruskal(*[x[deg == k] for k in np.unique(deg)])
    out["kruskal_ro_by_degree_p"] = float(f"{kw.pvalue:.3g}")
    mi, mp = moran(x, w, rng)
    out["moran_ro"] = {"I": round(mi, 4), "p": round(mp, 4)}
    resid = x.copy()
    for k in np.unique(deg):
        resid[deg == k] -= np.median(x[deg == k])
    mi2, mp2 = moran(resid, w, rng)
    out["moran_ro_after_removing_degree_class_median"] = {"I": round(mi2, 4), "p": round(mp2, 4)}
    # exclude the worst 10 qubits as well
    keep = medro <= np.sort(medro)[-11]
    w2 = w[np.ix_(keep, keep)]
    mi3, mp3 = moran(resid[keep], w2, rng)
    out["moran_resid_without_10_worst"] = {"I": round(mi3, 4), "p": round(mp3, 4)}

    # (2) freshness of stale-group P(0|1) by session kind
    present = np.isfinite(ro) & np.isfinite(a) & np.isfinite(b)
    afresh = np.abs(dro - da) <= WIN
    bfresh = np.abs(dro - db) <= WIN
    ev_t, ev_q, ev_f = [], [], []
    for e in range(nq):
        idx = stamp_idx(ro, dro, e)
        ev_t.append(dro[idx, e])
        ev_q.append(np.full(idx.size, e))
        ev_f.append(idx)
    T, Q, F = np.concatenate(ev_t), np.concatenate(ev_q), np.concatenate(ev_f)
    o = np.argsort(T, kind="stable")
    T, Q, F = T[o], Q[o], F[o]
    br = np.flatnonzero(np.diff(T) > GAP)
    st = np.concatenate([[0], br + 1])
    en = np.concatenate([br + 1, [T.size]])
    pa = np.where(present & afresh, a, np.nan)
    pb = np.where(present & bfresh, b, np.nan)
    kind = []
    for x0, y0 in zip(st, en, strict=True):
        k = np.concatenate([pa[F[x0:y0], Q[x0:y0]], pb[F[x0:y0], Q[x0:y0]]]) * 4096
        k = k[np.isfinite(k)]
        nqs = np.unique(Q[x0:y0]).size
        kind.append("small" if nqs < 100 else ("even" if np.all(np.round(k) % 2 == 0) else "mixed"))
    kind = np.array(kind)
    sess = np.repeat(np.arange(st.size), en - st)
    grp = np.isin(np.arange(nq) % 17, [9, 10, 16])
    # group qubits' events in their own active window only: use stale-ever qubits
    stale = present & ((dro - da) > WIN)
    stale_q = stale.any(axis=0)
    for name in ("even", "mixed"):
        m = (kind[sess] == name) & stale_q[Q]
        fr = afresh[F[m], Q[m]]
        out[f"stale_qubits_events_in_{name}_sessions"] = {
            "events": int(m.sum()),
            "p0g1_fresh": int(fr.sum()),
        }
    del grp

    # (3) A at the length change, placebo
    t1 = np.array(dd.v("q.T1"), float)
    rl = np.array(dd.v("q.readout_length"), float)
    both = present & afresh & bfresh
    A = np.where(both, a - b, np.nan)
    ch = np.flatnonzero(np.diff(np.nanmedian(rl, axis=1)) != 0) + 1
    tc1 = dd.file_ms[ch[0]]
    t_ev = [dro[stamp_idx(ro, dro, e), e] for e in range(nq)]
    A_ev = [A[stamp_idx(ro, dro, e), e] for e in range(nq)]

    def dstat(tc, wdays=7, guard=6.0):
        r = []
        for t, y in zip(t_ev, A_ev, strict=True):
            m = np.isfinite(y)
            t, y = t[m], y[m]
            bef = y[(t >= tc - wdays * DAY - guard * H) & (t < tc - guard * H)]
            aft = y[(t > tc + guard * H) & (t <= tc + wdays * DAY + guard * H)]
            if bef.size >= 3 and aft.size >= 3:
                r.append(np.median(aft) - np.median(bef))
        return float(np.median(r)) if len(r) >= 100 else None

    obs = dstat(tc1)
    first, last = float(np.nanmin(dro)), float(np.nanmax(dro))
    pl = []
    tc = first + 8 * DAY
    while tc < last - 8 * DAY:
        if abs(tc - tc1) > 15 * DAY and abs(tc - dd.file_ms[ch[1]]) > 15 * DAY:
            s = dstat(tc)
            if s is not None:
                pl.append(s)
        tc += DAY
    pl = np.array(pl)
    out["A_change_at_first_length_change_7d"] = round(obs, 5)
    out["A_placebo_7d"] = {
        "days": int(pl.size),
        "q05": round(float(np.quantile(pl, 0.05)), 5),
        "q95": round(float(np.quantile(pl, 0.95)), 5),
        "max": round(float(pl.max()), 5),
    }
    # predicted change in A from decay, T1 held at before-window median per qubit
    pre = []
    for e in range(nq):
        m = (dd.file_ms >= tc1 - 7 * DAY) & (dd.file_ms < tc1) & np.isfinite(t1[:, e])
        if m.sum() >= 3:
            T1 = np.median(t1[m, e])
            pre.append(
                (
                    np.exp(-1.560 / T1) - np.exp(-1.700 / T1),
                    np.exp(-0.780 / T1) - np.exp(-0.850 / T1),
                )
            )
    pre = np.array(pre)
    out["predicted_dA_full_window_median"] = round(float(np.median(pre[:, 0])), 5)
    out["predicted_dA_half_window_median"] = round(float(np.median(pre[:, 1])), 5)
    out["observed_over_predicted_full"] = round(obs / float(np.median(pre[:, 0])), 3)
    out["observed_over_predicted_half"] = round(obs / float(np.median(pre[:, 1])), 3)

    # (4) session-level weekday test for P(1|0): one residual per session
    resid_s = {}
    for e in range(nq):
        idx = stamp_idx(ro, dro, e)
        idx = idx[np.isfinite(b[idx, e]) & (b[idx, e] > 0)]
        if idx.size < 40:
            continue
        lv = np.log10(b[idx, e])
        k = 6
        med = np.array(
            [
                np.median(np.concatenate([lv[max(0, i - k) : i], lv[i + 1 : i + 1 + k]]))
                for i in range(lv.size)
            ]
        )
        r = lv - med
        t = dro[idx, e]
        sidx = np.searchsorted(T[st], t, side="right") - 1
        for i in range(k, lv.size - k):
            resid_s.setdefault(int(sidx[i]), []).append(r[i])
    ss = sorted(resid_s)
    sm = np.array([np.median(resid_s[s]) for s in ss])
    wd = np.array([int((T[st[s]] // DAY + 3) % 7) for s in ss])  # 1970-01-01 is Thursday
    groups = [sm[wd == d] for d in range(7)]
    kw = kruskal(*groups)
    out["p1g0_weekday_session_level"] = {
        "sessions": int(sm.size),
        "kruskal_p": float(f"{kw.pvalue:.3g}"),
        "sessions_per_weekday": [int(g.size) for g in groups],
    }
    mw = mannwhitneyu(sm[wd < 5], sm[wd >= 5])
    out["p1g0_weekday_vs_weekend_session_level_p"] = float(f"{mw.pvalue:.3g}")
    ddload.write_json(OUT, out)
    print("ok")


main()
