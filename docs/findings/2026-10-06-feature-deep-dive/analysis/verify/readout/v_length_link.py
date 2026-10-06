"""Independent re-computation of the length experiment, the T1 link, Moran's I and init_error.

Written from ddload only. Recomputes: per-qubit RO before/after the 2026-06-08 readout length
change (7 d windows, 6 h guard) with a placebo over other days AND over the three weeks before
the change (a trend check), the across-qubit Spearman of asymmetry against the expected decay,
Moran's I of per-qubit median log10 RO on the coupling graph, and the init_error link.

Writes ``results/verify/readout/length_link_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = (
    Path(__file__).resolve().parents[3]
    / "results"
    / "verify"
    / "readout"
    / "length_link_check.json"
)
H = 3.6e6
DAY = 24 * H


def stamp_events(v, d):
    out = []
    for e in range(v.shape[1]):
        ok = np.flatnonzero(np.isfinite(v[:, e]) & np.isfinite(d[:, e]))
        dd_ = d[ok, e]
        keep = np.concatenate([[True], dd_[1:] != dd_[:-1]])
        out.append(ok[keep])
    return out


def window_stat(t_ev, y_ev, tc, w_days, guard_h=6.0, min_ev=3):
    """Median over qubits of log10(median after / median before) around time tc."""
    res = []
    up = 0
    for t, y in zip(t_ev, y_ev, strict=True):
        before = y[(t >= tc - w_days * DAY - guard_h * H) & (t < tc - guard_h * H)]
        after = y[(t > tc + guard_h * H) & (t <= tc + w_days * DAY + guard_h * H)]
        if before.size < min_ev or after.size < min_ev:
            continue
        mb, ma = np.median(before), np.median(after)
        if mb > 0 and ma > 0:
            res.append(np.log10(ma / mb))
            up += ma > mb
    if not res:
        return None, 0, None
    return float(np.median(res)), len(res), up / len(res)


def moran(x, edges, n, rng, perms=5000):
    z = x - x.mean()
    w = np.zeros((n, n))
    for i, j in edges:
        w[i, j] = w[j, i] = 1
    s = w.sum()

    def stat(zz):
        return (n / s) * (zz @ w @ zz) / (zz @ zz)

    obs = stat(z)
    null = np.array([stat(rng.permutation(z)) for _ in range(perms)])
    p = (1 + np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean()))) / (perms + 1)
    return float(obs), float(p)


def main() -> None:
    dd = ddload.DD()
    ro = np.array(dd.v("q.readout_error"), float)
    dro = np.array(dd.d("q.readout_error"), float)
    ev = stamp_events(ro, dro)
    t_ev = [dro[i, e] for e, i in enumerate(ev)]
    y_ev = [ro[i, e] for e, i in enumerate(ev)]
    out: dict = ddload.result_header("verify/readout", "v_length_link.py")

    rl = np.array(dd.v("q.readout_length"), float)
    med_len = np.nanmedian(rl, axis=1)
    ch = np.flatnonzero(np.diff(med_len) != 0) + 1
    out["length_change_files"] = [dd.stems[i] for i in ch]
    tc1, tc2 = dd.file_ms[ch[0]], dd.file_ms[ch[1]]
    for w in (7, 14):
        s, n, up = window_stat(t_ev, y_ev, tc1, w)
        out[f"change1_{w}d"] = {"median_log10": round(s, 4), "qubits": n, "share_up": round(up, 4)}
        s2, n2, up2 = window_stat(t_ev, y_ev, tc2, w)
        out[f"change2_{w}d"] = {
            "median_log10": round(s2, 4),
            "qubits": n2,
            "share_up": round(up2, 4),
        }
    # placebo over other days
    first, last = float(np.nanmin(dro)), float(np.nanmax(dro))
    w = 7
    plac = []
    tc = first + (w + 1) * DAY
    while tc < last - (w + 1) * DAY:
        if abs(tc - tc1) > (2 * w + 1) * DAY and abs(tc - tc2) > (2 * w + 1) * DAY:
            s, n, _ = window_stat(t_ev, y_ev, tc, w)
            if s is not None and n >= 100:
                plac.append(s)
        tc += DAY
    plac = np.array(plac)
    out["placebo7"] = {
        "days": int(plac.size),
        "q05": round(float(np.quantile(plac, 0.05)), 4),
        "q95": round(float(np.quantile(plac, 0.95)), 4),
        "min": round(float(plac.min()), 4),
        "share_at_least_as_negative": round(
            float(np.mean(plac <= out["change1_7d"]["median_log10"])), 4
        ),
    }
    # trend check: same statistic centred at 7..21 days before the change (excluded from placebo)
    pre = {}
    for k in (8, 10, 12, 14, 16):
        s, n, _ = window_stat(t_ev, y_ev, tc1 - k * DAY, 7)
        pre[str(k)] = None if s is None else {"median_log10": round(s, 4), "qubits": n}
    out["pre_change_same_statistic_centred_k_days_before"] = pre

    # decay link
    a = np.array(dd.v("q.prob_meas0_prep1"), float)
    b = np.array(dd.v("q.prob_meas1_prep0"), float)
    da = np.array(dd.d("q.prob_meas0_prep1"), float)
    db = np.array(dd.d("q.prob_meas1_prep0"), float)
    t1 = np.array(dd.v("q.T1"), float)
    win = 10 * 60e3
    fresh = (np.abs(dro - da) <= win) & (np.abs(dro - db) <= win)
    fresh &= np.isfinite(ro) & np.isfinite(t1)
    asym = np.where(fresh, a - b, np.nan)
    tro = rl[:, :]
    dfull = 1 - np.exp(-(tro / 1000.0) / t1)  # ns to us
    nq = ro.shape[1]
    ma = np.array([np.nanmedian(asym[:, e]) for e in range(nq)])
    md = np.array([np.nanmedian(np.where(fresh[:, e], dfull[:, e], np.nan)) for e in range(nq)])
    mpa = np.array([np.nanmedian(np.where(fresh[:, e], a[:, e], np.nan)) for e in range(nq)])
    mpb = np.array([np.nanmedian(np.where(fresh[:, e], b[:, e], np.nan)) for e in range(nq)])
    ok = np.isfinite(ma) & np.isfinite(md)
    r = spearmanr(ma[ok], md[ok])
    out["asym_vs_dfull_across_qubits"] = {
        "n": int(ok.sum()),
        "spearman": round(float(r.statistic), 4),
        "p": float(f"{r.pvalue:.2g}"),
    }
    ok2 = np.isfinite(mpa) & np.isfinite(md)
    r2 = spearmanr(mpa[ok2], md[ok2])
    out["p0g1_vs_dfull_across_qubits"] = {
        "spearman": round(float(r2.statistic), 4),
        "p": float(f"{r2.pvalue:.2g}"),
    }
    r3 = spearmanr(mpa[ok2 & np.isfinite(mpb)], mpb[ok2 & np.isfinite(mpb)])
    out["p0g1_vs_p1g0_across_qubits"] = round(float(r3.statistic), 4)
    out["median_dfull_per_qubit"] = round(float(np.nanmedian(md)), 5)
    # sensitivity: drop the 20 qubits with the largest median RO
    medro = np.array([np.nanmedian(y) for y in y_ev])
    keep = ok & (medro <= np.quantile(medro, 0.9))
    r4 = spearmanr(ma[keep], md[keep])
    out["asym_vs_dfull_without_worst_10pct_ro_qubits"] = {
        "n": int(keep.sum()),
        "spearman": round(float(r4.statistic), 4),
        "p": float(f"{r4.pvalue:.2g}"),
    }
    # asymmetry vs plain level (A could track overall error level, not decay)
    r5 = spearmanr(ma[ok], medro[ok])
    out["asym_vs_median_ro_across_qubits"] = round(float(r5.statistic), 4)
    # partial: A vs dfull controlling for ro rank via residual ranks
    from scipy.stats import rankdata

    def resid(x, z):
        x, z = rankdata(x), rankdata(z)
        k = np.polyfit(z, x, 1)
        return x - np.polyval(k, z)

    r6 = spearmanr(resid(ma[ok], medro[ok]), resid(md[ok], medro[ok]))
    out["asym_vs_dfull_partial_on_ro_rank"] = round(float(r6.statistic), 4)

    # Moran's I of per-qubit median log10 RO
    x = np.log10(medro)
    edges = sorted({tuple(sorted(e)) for e in dd.meta["coupling_map"]})
    rng = np.random.default_rng(20261006)
    mi, mp = moran(x, edges, nq, rng)
    out["moran_ro"] = {"edges": len(edges), "I": round(mi, 4), "p": round(mp, 4)}
    # degree/frequency-like explanation: Moran's I with a distance-2 graph (same sublattice)
    nbrs = {i: set() for i in range(nq)}
    for i, j in edges:
        nbrs[i].add(j)
        nbrs[j].add(i)
    e2 = set()
    for i in range(nq):
        for j in nbrs[i]:
            for k in nbrs[j]:
                if k != i and k not in nbrs[i]:
                    e2.add(tuple(sorted((i, k))))
    mi2, mp2 = moran(x, sorted(e2), nq, rng)
    out["moran_ro_two_hop_only"] = {"edges": len(e2), "I": round(mi2, 4), "p": round(mp2, 4)}

    # init_error
    ie = np.array(dd.v("q.init_error"), float)
    never = ~np.isfinite(ie).any(axis=0)
    out["init_never_present_qubits"] = int(never.sum())
    mw = mannwhitneyu(medro[never], medro[~never])
    out["init_never_vs_others_median_ro"] = {
        "never": round(float(np.median(medro[never])), 5),
        "others": round(float(np.median(medro[~never])), 5),
        "p": float(f"{mw.pvalue:.2g}"),
    }
    mie = np.array(
        [np.nanmedian(ie[:, e]) if np.isfinite(ie[:, e]).any() else np.nan for e in range(nq)]
    )
    g = ~never & np.isfinite(mpb)
    r7 = spearmanr(mie[g], mpb[g])
    out["init_vs_p1g0_across_qubits"] = {
        "n": int(g.sum()),
        "spearman": round(float(r7.statistic), 4),
    }
    first_ie = int(np.flatnonzero(np.isfinite(ie).any(axis=1))[0])
    out["init_first_file"] = dd.stems[first_ie]
    # the never-present set vs the placeholder/zero p1g0 qubits: is absence tied to level only?
    thr = np.quantile(medro, 0.75)
    out["never_present_among_top25pct_ro"] = int((never & (medro >= thr)).sum())
    out["top25pct_ro_qubits"] = int((medro >= thr).sum())
    ddload.write_json(OUT, out)
    print("ok")


main()
