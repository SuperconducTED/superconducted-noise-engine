"""Independent re-computation of the load-bearing numbers of 04-single-qubit-gates.md.

Written from ddload only (no import of the owner's code). Every number saved here is a
field of results/verify/gates_1q/verify_core.json.
"""

import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

HOUR = 3.6e6
OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "gates_1q" / "verify_core.json"


def run_level(z, half=5):
    """Median of up to 5 neighbours each side, self excluded; NaN under 4 neighbours."""
    n = z.size
    out = np.full(n, np.nan)
    for k in range(n):
        nb = np.concatenate([z[max(0, k - half) : k], z[k + 1 : k + half + 1]])
        if nb.size >= 4:
            out[k] = np.median(nb)
    return out


def nearest(t, ref):
    """Index of nearest ref stamp for each t, and the offset in hours (t - ref)."""
    j = np.searchsorted(ref, t)
    j0 = np.clip(j - 1, 0, ref.size - 1)
    j1 = np.clip(j, 0, ref.size - 1)
    pick = np.where(np.abs(t - ref[j0]) <= np.abs(t - ref[j1]), j0, j1)
    return pick, (t - ref[pick]) / HOUR


def coh(t1, t2, t_ns):
    t = t_ns * 1e-3
    return 0.5 * (1.0 - (2.0 / 3.0) * np.exp(-t / t2) - (1.0 / 3.0) * np.exp(-t / t1))


def main():
    dd = ddload.DD()
    res = ddload.result_header("verify/gates_1q", "analysis/verify/gates_1q/verify_core.py")
    sx = ddload.series(dd, "g1.sx.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    ev = np.concatenate([s.y for s in sx])
    res["sx_events"] = {
        "n_series": len(sx),
        "n_events": int(ev.size),
        "median": float(np.median(ev)),
        "q01": float(np.quantile(ev, 0.01)),
        "q99": float(np.quantile(ev, 0.99)),
        "max": float(ev.max()),
        "share_gt_1e-3": float(np.mean(ev > 1e-3)),
        "n_gt_1e-2": int((ev > 1e-2).sum()),
    }
    # between-qubit variance share
    z_all = [np.log10(s.y) for s in sx]
    allz = np.concatenate(z_all)
    gm = allz.mean()
    ssb = sum(z.size * (z.mean() - gm) ** 2 for z in z_all)
    res["between_share"] = float(ssb / ((allz - gm) ** 2).sum())
    med = np.array([np.median(s.y) for s in sx])
    res["qubit_median_range_factor"] = float(med.max() / med.min())

    # aliases
    sxv = np.array(dd.v("g1.sx.gate_error"))
    alias = {}
    for a in ("x", "id", "rx", "xslow"):
        av = np.array(dd.v(f"g1.{a}.gate_error"))
        both = np.isfinite(av) & np.isfinite(sxv)
        alias[a] = {
            "records_both": int(both.sum()),
            "value_mismatch": int((av[both] != sxv[both]).sum()),
            "nan_pattern_differs": int((np.isfinite(av) != np.isfinite(sxv)).sum()),
        }
        if a == "xslow":
            alias[a]["nan_pattern_differs_within_xslow_files"] = int(
                (np.isfinite(av) != np.isfinite(sxv))[np.isfinite(av).any(axis=1)].sum()
            )
    res["aliases"] = alias
    res["rz_all_zero"] = bool(
        np.nanmax(np.abs(np.array(dd.v("g1.rz.gate_error")))) == 0
        and np.nanmax(np.abs(np.array(dd.v("g1.rz.gate_length")))) == 0
    )

    # lag-1 / lag-2 autocorrelation of log changes (pooled, products over pairs)
    dz_list = [np.diff(z) for z in z_all]
    num1 = num2 = den = 0.0
    n1 = n2 = 0
    allc = np.concatenate(dz_list)
    mu = allc.mean()
    for d in dz_list:
        dc = d - mu
        den += (dc * dc).sum()
        num1 += (dc[1:] * dc[:-1]).sum()
        num2 += (dc[2:] * dc[:-2]).sum()
        n1 += dc.size - 1
        n2 += max(dc.size - 2, 0)
    res["autocorr_log_changes"] = {
        "lag1": float(num1 / den),
        "lag2": float(num2 / den),
        "n_changes": int(allc.size),
    }
    res["autocorr_log_changes"]["lag1_unnormalised_pairs_form"] = float(
        (num1 / n1) / (den / allc.size)
    )

    # variogram ratio
    vg = ddload.variogram(sx)
    b = vg["bins"]

    def pooled(lo, hi):
        rows = [r for r in b if r["lag_h_lo"] >= lo and r["lag_h_hi"] <= hi and r["pairs"]]
        return sum(r["semivariance"] * r["pairs"] for r in rows) / sum(r["pairs"] for r in rows)

    res["variogram"] = {
        "daily_18_30": pooled(18, 30),
        "long_744_3624": pooled(744, 3624),
        "ratio": pooled(18, 30) / pooled(744, 3624),
        "bin_6_9": pooled(6, 9),
        "pairs_6_9": next(r["pairs"] for r in b if r["lag_h_lo"] == 6.0),
        "min_event_gap_h": float(min(np.diff(s.t_ms).min() for s in sx if s.y.size > 1) / HOUR),
    }

    # robust lag-1 check: Spearman of consecutive changes (heavy tails)
    x = np.concatenate([d[:-1] for d in dz_list])
    y = np.concatenate([d[1:] for d in dz_list])
    res["autocorr_log_changes"]["lag1_spearman"] = float(stats.spearmanr(x, y).statistic)

    # coherence matching, own implementation
    t1 = {s.entity: s for s in ddload.series(dd, "q.T1", rule=ddload.MEASURED)}
    t2 = {s.entity: s for s in ddload.series(dd, "q.T2", rule=ddload.MEASURED)}
    ratios, wsx, wt1, wt2, wec, esx_med, t1_med = [], [], [], [], [], {}, {}
    n_match = n_skip = 0
    xs = np.array(dd.v("g1.xslow.gate_error"))
    pres = np.isfinite(xs).any(axis=1)
    fm = dd.file_ms
    idx = np.flatnonzero(pres)
    br = np.flatnonzero(np.diff(idx) > 1)
    st = np.concatenate([[0], br + 1])
    en = np.concatenate([br, [idx.size - 1]])
    windows = [(fm[idx[a]], fm[idx[b2]]) for a, b2 in zip(st, en, strict=True)]
    xratio_in, xratio_t1only = [], []
    nspk = 0
    spk_t1dip = 0
    spk_n_matched = 0
    for s in sx:
        zs = np.log10(s.y)
        lv = run_level(zs)
        nspk += int(np.nansum((zs - lv) > np.log10(2.0)))
        if s.entity not in t1 or s.entity not in t2:
            n_skip += s.y.size
            continue
        a, c = t1[s.entity], t2[s.entity]
        i1, o1 = nearest(s.t_ms, a.t_ms)
        i2, o2 = nearest(s.t_ms, c.t_ms)
        ok = (np.abs(o1) <= 6) & (np.abs(o2) <= 6)
        n_skip += int((~ok).sum())
        n_match += int(ok.sum())
        if ok.sum() == 0:
            continue
        e = s.y[ok]
        ec = coh(a.y[i1[ok]], c.y[i2[ok]], 24.0)
        ratios.append(ec / e)
        t1_med[s.entity] = float(np.median(a.y[i1[ok]]))
        esx_med[s.entity] = float(np.median(e))
        # xslow
        tt = s.t_ms[ok]
        inside = np.zeros(tt.size, bool)
        for lo, hi in windows:
            inside |= (tt >= lo) & (tt <= hi)
        lim = coh(a.y[i1[ok]], c.y[i2[ok]], 1000.0)
        lim1 = coh(a.y[i1[ok]], 2 * a.y[i1[ok]], 1000.0)
        xratio_in.append((lim / e)[inside])
        xratio_t1only.append((lim1 / e)[inside])
        # within-qubit coupling: T1 deviation of the matched T1 event vs its own level
        zt1 = np.log10(a.y)
        d1 = zt1 - run_level(zt1)
        wsx.append((zs - lv)[ok])
        wt1.append(d1[i1[ok]])
        zt2 = np.log10(c.y)
        d2 = zt2 - run_level(zt2)
        wt2.append(d2[i2[ok]])
        wec.append(np.log10(ec) - run_level(np.log10(ec)))
        spk_n_matched += int(np.nansum((zs - lv)[ok] > np.log10(2.0)))
        spk_t1dip += int(np.nansum(((zs - lv)[ok] > np.log10(2.0)) & (d1[i1[ok]] < -np.log10(1.5))))
    r = np.concatenate(ratios)
    res["coherence"] = {
        "n_matched": n_match,
        "n_skipped": n_skip,
        "ratio_q": [float(v) for v in np.quantile(r, [0.1, 0.5, 0.9])],
        "share_ratio_gt_1": float(np.mean(r > 1)),
    }
    xi = np.concatenate(xratio_in)
    x1 = np.concatenate(xratio_t1only)
    res["xslow_floor"] = {
        "n": int(xi.size),
        "share_limit_above_reported": float(np.mean(xi > 1)),
        "median_ratio": float(np.median(xi)),
        "t1only_share": float(np.mean(x1 > 1)),
        "t1only_median": float(np.median(x1)),
        "windows": [[ddload.hours(w[0]) * 0 + float(w[0]), float(w[1])] for w in windows],
    }
    res["spikes"] = {
        "n_up_total": nspk,
        "n_up_total_rate": nspk / ev.size,
        "n_up_matched": spk_n_matched,
        "n_up_matched_with_T1_dip_1p5": spk_t1dip,
    }
    sxd = np.concatenate(wsx)
    t1d = np.concatenate(wt1)
    t2d = np.concatenate(wt2)
    okk = np.isfinite(sxd) & np.isfinite(t1d)
    res["within_pooled_spearman_sx_T1"] = float(stats.spearmanr(sxd[okk], t1d[okk]).statistic)
    okk = np.isfinite(sxd) & np.isfinite(t2d)
    res["within_pooled_spearman_sx_T2"] = float(stats.spearmanr(sxd[okk], t2d[okk]).statistic)
    # between qubits
    qs = sorted(set(esx_med) & set(t1_med))
    rho = stats.spearmanr([esx_med[q] for q in qs], [t1_med[q] for q in qs])
    res["between_qubit_spearman_sx_T1"] = {
        "rho": float(rho.statistic),
        "p": float(rho.pvalue),
        "n": len(qs),
    }
    ddload.write_json(OUT, res)
    print("ok", OUT)


if __name__ == "__main__":
    main()
