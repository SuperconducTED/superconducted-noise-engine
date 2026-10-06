# ruff: noqa: B905, N806, RUF059, B007, E501
"""Challenge tests for the interpretive claims of 05-two-qubit-gates-couplings.md.

Written from ddload only. Tests: (a) shared-qubit local-deviation correlation by hop distance and
by round lag; (b) the short-gap "three quarters" claim, from the pooled variogram bins and from
an occasion-level test; (c) the rzz event-rate drop with and without the 2026-08 pause; (d) the
cz-rzz correlation against offset, per round pair; (e) Moran's I of coupler levels; (f) whole-second
stamps of real records; (g) the non-68 ns versus |zz| rank test.

Writes ``results/verify/gates_2q/challenge_check.json``.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, mannwhitneyu, spearmanr, wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "verify" / "gates_2q" / "challenge_check.json"
MS_H = 3.6e6


def f(x, nd=4):
    return float(f"{x:.{nd}g}")


def canon(dd):
    edges = [tuple(int(x) for x in e) for e in dd.entities("g2.cz.gate_error")]
    return [i for i, (a, b) in enumerate(edges) if a < b], [e for e in edges if e[0] < e[1]]


def events(dd, gate, fwd):
    keep = set(fwd)
    ser = ddload.series(
        dd, f"g2.{gate}.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error
    )
    return [s for s in ser if s.entity in keep]


def local_dev(z):
    n = z.size
    out = np.full(n, np.nan)
    for i in range(n):
        nb = np.r_[z[max(0, i - 3) : i], z[i + 1 : i + 4]]
        if nb.size >= 3:
            out[i] = z[i] - np.median(nb)
    return out


def round_ids(ser):
    allt = np.sort(np.concatenate([np.asarray(s.t_ms, float) for s in ser]))
    starts = np.r_[0, np.flatnonzero(np.diff(allt) / MS_H > 0.25) + 1]
    return allt[starts]


def dev_by_round(ser, names, fwd):
    c2n = dict(zip(fwd, names))
    bounds = round_ids(ser)
    raw = {}
    for s in ser:
        y = np.asarray(s.y, float)
        t = np.asarray(s.t_ms, float)
        k = y > 0
        y, t = y[k], t[k]
        if y.size < 8:
            continue
        dv = local_dev(np.log10(y))
        rid = np.searchsorted(bounds, t, side="right") - 1
        raw[c2n[s.entity]] = (rid, dv, t)
    bucket = {}
    for rid, dv, _ in raw.values():
        for r, v in zip(rid, dv):
            if np.isfinite(v):
                bucket.setdefault(int(r), []).append(v)
    rmed = {r: float(np.median(v)) for r, v in bucket.items()}
    out = {}
    for n, (rid, dv, t) in raw.items():
        m = {}
        for r, v, tt in zip(rid, dv, t):
            r = int(r)
            if np.isfinite(v) and r not in m:
                m[r] = (v - rmed[r], tt)
        out[n] = m
    return out, bounds


def hops(names):
    adj = {n: set() for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if set(a) & set(b):
                adj[a].add(b)
                adj[b].add(a)
    H = {}
    for a in names:
        d = {a: 0}
        fr = [a]
        while fr:
            nx = []
            for u in fr:
                for w in adj[u]:
                    if w not in d:
                        d[w] = d[u] + 1
                        nx.append(w)
            fr = nx
        H[a] = d
    return adj, H


def pair_corr(mapped, pairs, lag=0):
    x, y = [], []
    for a, b in pairs:
        ma, mb = mapped[a], mapped[b]
        for r, (v, _) in ma.items():
            if (r + lag) in mb:
                x.append(v)
                y.append(mb[r + lag][0])
    return {"n": len(x), "spearman": f(float(spearmanr(x, y)[0]), 3) if len(x) > 10 else None}


def morans(values, names):
    n = len(names)
    W = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j and set(names[i]) & set(names[j]):
                W[i, j] = 1
    z = values - values.mean()
    num = (W * np.outer(z, z)).sum()
    binary = n / W.sum() * num / (z * z).sum()
    Wr = W / np.maximum(W.sum(1, keepdims=True), 1)
    row = n / Wr.sum() * (Wr * np.outer(z, z)).sum() / (z * z).sum()
    rng = np.random.default_rng(11)
    cnt = 0
    for _ in range(4999):
        zp = rng.permutation(z)
        if (W * np.outer(zp, zp)).sum() * n / W.sum() / (z * z).sum() >= binary:
            cnt += 1
    return {
        "I_binary": f(float(binary), 3),
        "I_rowstd": f(float(row), 3),
        "p_binary": (cnt + 1) / 5000,
    }


def main():
    dd = ddload.DD()
    fwd, names = canon(dd)
    out = {"header": ddload.result_header("verify/gates_2q", "v_challenge.py")}
    ev = {g: events(dd, g, fwd) for g in ("cz", "rzz")}

    # (a) shared-qubit correlation by hop and by round lag
    a_res = {}
    for g in ("cz", "rzz"):
        mapped, bounds = dev_by_round(ev[g], names, fwd)
        nm = sorted(mapped)
        adj, H = hops(nm)
        by_hop = {}
        for h in (1, 2, 3):
            pairs = [(a, b) for i, a in enumerate(nm) for b in nm[i + 1 :] if H[a].get(b, 99) == h]
            by_hop[str(h)] = {"coupler_pairs": len(pairs), **pair_corr(mapped, pairs)}
        share = [(a, b) for i, a in enumerate(nm) for b in nm[i + 1 :] if H[a].get(b, 99) == 1]
        both_dir = {}
        for lag in (1, 2):
            xs, ys = [], []
            for a, b in share:
                for u, v in ((a, b), (b, a)):
                    for r, (val, ta) in mapped[u].items():
                        if (r + lag) in mapped[v]:
                            xs.append(val)
                            ys.append(mapped[v][r + lag][0])
            both_dir[f"round_lag_{lag}"] = {
                "n": len(xs),
                "spearman": f(float(spearmanr(xs, ys)[0]), 3),
            }
        # leave-one-qubit-out robustness: drop all pairs touching each shared qubit, report range
        shared_q = {}
        for a, b in share:
            q = (set(a) & set(b)).pop()
            shared_q.setdefault(q, []).append((a, b))
        rho_by_q = {}
        for q, pairs in shared_q.items():
            c = pair_corr(mapped, pairs)
            if c["n"] >= 200:
                rho_by_q[q] = c["spearman"]
        vals = np.array(list(rho_by_q.values()), float)
        # by sx level of the shared qubit
        sx = np.asarray(dd.v("g1.sx.gate_error"), float)
        sx_med = np.nanmedian(np.where(sx >= 1, np.nan, sx), axis=0)
        qs = dd.meta["qubits"]
        qpos = {int(q): i for i, q in enumerate(qs)}
        qlist = sorted(rho_by_q)
        sxv = np.array([sx_med[qpos[q]] for q in qlist])
        tercile = np.quantile(sxv, [1 / 3, 2 / 3])
        strata = {}
        for lab, sel in (
            ("low_sx", sxv <= tercile[0]),
            ("mid_sx", (sxv > tercile[0]) & (sxv <= tercile[1])),
            ("high_sx", sxv > tercile[1]),
        ):
            pairs = [p for q, ok in zip(qlist, sel) if ok for p in shared_q[q]]
            strata[lab] = {"shared_qubits": int(sel.sum()), **pair_corr(mapped, pairs)}
        a_res[g] = {
            "by_hop": by_hop,
            "cross_round": both_dir,
            "per_shared_qubit_rho": {
                "n_qubits": int(vals.size),
                "min": f(float(vals.min()), 3),
                "median": f(float(np.median(vals)), 3),
                "max": f(float(vals.max()), 3),
                "share_positive": f(float((vals > 0).mean()), 3),
            },
            "by_sx_tercile_of_shared_qubit": strata,
        }
    out["a_shared_qubit_correlation"] = a_res

    # (b) short-gap claim
    vg = ddload.variogram(ev["cz"])
    bins = {(b["lag_h_lo"], b["lag_h_hi"]): b for b in vg["bins"]}
    ref = bins[(18.0, 30.0)]["semivariance"]
    out["b_short_gap_fraction_of_one_round_cz"] = {
        f"{k[0]:g}-{k[1]:g}h": {"pairs": b["pairs"], "frac": f(b["semivariance"] / ref, 3)}
        for k, b in bins.items()
        if b["pairs"] and k[1] <= 30
    }
    own = json.loads(
        (ROOT / "results" / "gates_2q" / "variograms.json").read_text(encoding="utf-8")
    )
    occ = {}
    for g in ("cz", "rzz"):
        lst = own[g]["short_gap_occasions"]["occasion_list"]
        s = np.array([o["semivar_short"] for o in lst])
        p = np.array([o["semivar_preceding"] for o in lst])
        gaps = np.array([o["short_gap_h_median"] for o in lst])
        occ[g] = {
            "n_occasions": len(lst),
            "input_note": "occasion means read from the owner's variograms.json (occasion-level units)",
            "sign_test_short_below_preceding_p": f(
                float(binomtest(int((s < p).sum()), len(s), 0.5).pvalue), 3
            ),
            "wilcoxon_occasion_level_p": f(float(wilcoxon(s, p).pvalue), 3),
            "spearman_short_semivar_vs_gap_h": f(float(spearmanr(gaps, s)[0]), 3),
            "occasions_with_gap_below_8h": int((gaps < 8).sum()),
            "mean_short_semivar_gap_below_8h": f(float(s[gaps < 8].mean())),
            "mean_short_semivar_gap_at_least_8h": f(float(s[gaps >= 8].mean())),
        }
    out["b_occasion_level"] = occ

    # (c) rzz rate with and without the pause
    t = np.concatenate([np.asarray(s.t_ms, float) for s in ev["rzz"]])
    stems = dd.meta["stems"]
    split = dd.file_ms[next(i for i, s in enumerate(stems) if str(s).startswith("20260805T234531"))]
    end = dd.file_ms[-1]
    # pause: longest gap between consecutive rzz event stamps pooled over rounds
    ts = np.sort(t)
    gaps = np.diff(ts) / MS_H
    k = int(np.argmax(gaps))
    pause_h = float(gaps[k])
    post = (ts >= split).sum()
    days = (end - split) / MS_H / 24
    out["c_rzz_rate"] = {
        "longest_pooled_gap_h": f(pause_h),
        "pause_start_utc": str(np.datetime64(int(ts[k]), "ms")),
        "post_split_days": f(days),
        "post_split_rate_per_coupler_day_all": f(post / len(names) / days),
        "post_split_rate_per_coupler_day_excluding_pause": f(
            post / len(names) / (days - pause_h / 24)
        ),
    }

    # (d) cz-rzz correlation by offset, per cz round
    mc, bc = dev_by_round(ev["cz"], names, fwd)
    mr, br = dev_by_round(ev["rzz"], names, fwd)
    per_round = {}
    for n in set(mc) & set(mr):
        tr = np.array([tt for (_, tt) in mr[n].values()])
        for r, (v, tt) in mc[n].items():
            if tr.size == 0:
                continue
            j = int(np.argmin(np.abs(tr - tt)))
            off = (tr[j] - tt) / MS_H
            if abs(off) > 6:
                continue
            vr = list(mr[n].values())[j][0]
            per_round.setdefault(r, []).append((v, vr, off))
    rhos, offs, ns = [], [], []
    for r, lst in per_round.items():
        if len(lst) >= 60:
            a = np.array(lst)
            rhos.append(float(spearmanr(a[:, 0], a[:, 1])[0]))
            offs.append(float(np.median(np.abs(a[:, 2]))))
            ns.append(len(lst))
    rhos, offs = np.array(rhos), np.array(offs)
    r_o = spearmanr(offs, rhos)
    near = offs <= 2
    out["d_cz_rzz_offset_per_round"] = {
        "round_pairs": int(rhos.size),
        "median_round_rho_offset_le_2h": f(float(np.median(rhos[near])), 3),
        "n_offset_le_2h": int(near.sum()),
        "median_round_rho_offset_gt_2h": f(float(np.median(rhos[~near])), 3),
        "n_offset_gt_2h": int((~near).sum()),
        "spearman_round_rho_vs_offset": f(float(r_o[0]), 3),
        "p": f(float(r_o[1]), 3),
        "median_round_rho_all": f(float(np.median(rhos)), 3),
    }

    # (e) Moran
    med = {}
    for s in ev["cz"]:
        med[s.entity] = float(np.median(np.log10(np.asarray(s.y, float))))
    cols = sorted(med)
    c2n = dict(zip(fwd, names))
    nm = [c2n[c] for c in cols]
    out["e_moran_cz"] = {"n": len(cols), **morans(np.array([med[c] for c in cols]), nm)}

    # (f) whole-second stamps of non-placeholder cz records
    v = np.asarray(dd.v("g2.cz.gate_error"))[:, fwd]
    d = np.asarray(dd.d("g2.cz.gate_error"))[:, fwd]
    ok = v < 1
    out["f_whole_second_share_nonplaceholder_cz"] = f(float(np.mean(d[ok] % 1000 == 0)), 5)

    # (g) non-68 ns vs |zz|
    zz = np.abs(np.asarray(dd.v("gen.zz"), float)) * 1e6
    cp = [tuple(int(x) for x in c) for c in dd.meta["couplers"]]
    med_zz = {}
    for i, c in enumerate(cp):
        col = zz[:, i]
        col = col[col > 0]
        if col.size:
            med_zz[c] = float(np.median(col))
    odd = [(102, 103), (146, 147), (68, 69), (80, 81), (106, 107)]
    skip = set(odd) | {(71, 72), (72, 73), (32, 33)}
    rest = [m for c, m in med_zz.items() if c not in skip]
    mw = mannwhitneyu([med_zz[c] for c in odd], rest, alternative="less")
    # leave out the two couplers on poor qubits (102-103 touches q102, 146-147)
    sub = [(68, 69), (80, 81), (106, 107)]
    mw3 = mannwhitneyu([med_zz[c] for c in sub], rest, alternative="less")
    # all pairs of qubits' lengths: how many couplers in total have a nonstandard length is 5 of 176
    out["g_non68_vs_abs_zz"] = {
        "odd_medians_khz": [f(med_zz[c]) for c in odd],
        "rest_n": len(rest),
        "rest_median_khz": f(float(np.median(rest))),
        "mw_p_five": f(float(mw.pvalue), 3),
        "mw_p_three_116ns_rzz_only": f(float(mw3.pvalue), 3),
        "bonferroni_note": "found by inspection; the number of comparisons scanned is unknown",
    }
    ddload.write_json(OUT, out)
    print(OUT)


if __name__ == "__main__":
    main()
