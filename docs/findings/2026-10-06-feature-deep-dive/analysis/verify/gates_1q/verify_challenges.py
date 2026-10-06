"""Refutation attempts for interpretive claims of 04-single-qubit-gates.md (own code)."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

HOUR = 3.6e6
OUT = (
    Path(__file__).resolve().parents[3]
    / "results"
    / "verify"
    / "gates_1q"
    / "verify_challenges.json"
)


def run_level(z, half=5):
    n = z.size
    out = np.full(n, np.nan)
    for k in range(n):
        nb = np.concatenate([z[max(0, k - half) : k], z[k + 1 : k + half + 1]])
        if nb.size >= 4:
            out[k] = np.median(nb)
    return out


def nearest(t, ref):
    j = np.searchsorted(ref, t)
    j0 = np.clip(j - 1, 0, ref.size - 1)
    j1 = np.clip(j, 0, ref.size - 1)
    pick = np.where(np.abs(t - ref[j0]) <= np.abs(t - ref[j1]), j0, j1)
    return pick, (t - ref[pick]) / HOUR


def iso(ms):
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    dd = ddload.DD()
    res = ddload.result_header("verify/gates_1q", "analysis/verify/gates_1q/verify_challenges.py")
    sxv = np.array(dd.v("g1.sx.gate_error"))
    sxd = np.array(dd.d("g1.sx.gate_error"))
    fm = dd.file_ms[:, None]
    ph = sxv >= 1.0
    after = (sxd - fm)[ph]
    res["placeholder_stamps"] = {
        "n": int(ph.sum()),
        "n_after_file_date": int((after > 0).sum()),
        "median_s_after": float(np.median(after) / 1000.0),
        "min_s": float(after.min() / 1000.0),
        "max_s": float(after.max() / 1000.0),
    }
    meas = np.isfinite(sxv) & ~ph
    age = (np.broadcast_to(fm, sxd.shape) - sxd)[meas] / HOUR
    res["measured_stamp_age_h"] = {
        "n": int(meas.sum()),
        "n_stamp_after_file": int((age < 0).sum()),
        "median": float(np.median(age)),
        "q10_q90": [float(v) for v in np.quantile(age, [0.1, 0.9])],
        "max": float(age.max()),
    }
    # q17 frozen T1
    t1v = np.array(dd.v("q.T1"))[:, 17]
    t1d = np.array(dd.d("q.T1"))[:, 17]
    val = t1v[np.isfinite(t1v)]
    mode_val = float(stats.mode(np.round(val, 6)).mode)
    frozen = np.isfinite(t1v) & (np.abs(t1v - mode_val) < 1e-6)
    res["q17_T1"] = {
        "mode_value_us": mode_val,
        "n_files_with_mode_value": int(frozen.sum()),
        "first_file": iso(dd.file_ms[frozen][0]),
        "last_file": iso(dd.file_ms[frozen][-1]),
        "stamps_distinct": sorted({iso(x) for x in t1d[frozen]}),
        "n_sx_placeholder_files_q17": int(ph[:, 17].sum()),
        "n_placeholder_files_with_frozen_T1": int((ph[:, 17] & frozen).sum()),
    }

    sx = ddload.series(dd, "g1.sx.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    t1 = {s.entity: s for s in ddload.series(dd, "q.T1", rule=ddload.MEASURED)}
    t2 = {s.entity: s for s in ddload.series(dd, "q.T2", rule=ddload.MEASURED)}

    # robust size of changes vs plain
    dz = np.concatenate([np.diff(np.log10(s.y)) for s in sx])
    mad = 1.4826 * np.median(np.abs(dz - np.median(dz)))
    res["change_size"] = {
        "plain_sd_of_changes": float(dz.std()),
        "plain_component_sd_if_white": float(dz.std() / np.sqrt(2)),
        "robust_sd_of_changes": float(mad),
        "robust_component_sd_if_white": float(mad / np.sqrt(2)),
        "factor_plain": float(10 ** (dz.std() / np.sqrt(2))),
        "factor_robust": float(10 ** (mad / np.sqrt(2))),
    }

    # 6 to 9 h pairs: which series, which months
    pairs_series, pairs_months = {}, {}
    for s in sx:
        t = s.t_ms / HOUR
        i, j = np.triu_indices(t.size, 1)
        lag = t[j] - t[i]
        k = (lag >= 6) & (lag < 9)
        if k.any():
            pairs_series[s.entity] = int(k.sum())
            for jj in j[k]:
                m = iso(s.t_ms[jj])[:7]
                pairs_months[m] = pairs_months.get(m, 0) + 1
    res["pairs_6_9h"] = {
        "n_series": len(pairs_series),
        "n_pairs": int(sum(pairs_series.values())),
        "by_month_of_later_event": pairs_months,
        "max_pairs_one_series": int(max(pairs_series.values())),
    }
    # robust noise level at 6-9h vs 18-30h inside May only (same period)
    may = [
        ddload.Series(
            entity=s.entity,
            t_ms=s.t_ms[s.t_ms < 1.7803e12],
            file_idx=None,
            y=s.y[s.t_ms < 1.7803e12],
        )
        for s in sx
    ]
    vg = ddload.variogram(may)["bins"]
    res["variogram_may_only"] = {
        "bin_6_9": [vg[4]["semivariance"], vg[4]["pairs"]],
        "bin_18_30": [vg[7]["semivariance"], vg[7]["pairs"]],
        "bin_9_12": [vg[5]["semivariance"], vg[5]["pairs"]],
    }

    # rounds: spike dispersion with Poisson-binomial expectation
    t_all, sp_all, ent_all = [], [], []
    for s in sx:
        z = np.log10(s.y)
        lv = run_level(z)
        t_all.append(s.t_ms)
        sp_all.append(np.where(np.isfinite(lv), (z - lv) > np.log10(2.0), False))
        ent_all.append(np.full(s.y.size, s.entity))
    t_all = np.concatenate(t_all)
    sp_all = np.concatenate(sp_all)
    ent_all = np.concatenate(ent_all)
    order = np.argsort(t_all)
    ts = t_all[order]
    new = np.concatenate([[True], np.diff(ts) > 0.25 * HOUR])
    rid = np.empty(ts.size, int)
    rid[order] = np.cumsum(new) - 1
    nr = rid.max() + 1
    rate = {e: sp_all[ent_all == e].mean() for e in np.unique(ent_all)}
    p_ev = np.array([rate[e] for e in ent_all])
    cnt = np.bincount(rid, weights=sp_all.astype(float), minlength=nr)
    exp = np.bincount(rid, weights=p_ev, minlength=nr)
    var = np.bincount(rid, weights=p_ev * (1 - p_ev), minlength=nr)
    size = np.bincount(rid, minlength=nr)
    big = size >= 78
    stat = float(np.sum((cnt[big] - exp[big]) ** 2 / var[big]))
    dfree = int(big.sum())
    res["spike_round_dispersion"] = {
        "n_rounds_half_device": dfree,
        "chi2": stat,
        "df": dfree,
        "p_upper": float(stats.chi2.sf(stat, dfree)),
        "index_of_dispersion": stat / dfree,
        "se_of_index_approx": float(np.sqrt(2.0 / dfree)),
    }

    # degree vs T1, coordinates
    cm = dd.meta["coupling_map"]
    deg = {}
    edges = {tuple(sorted(e)) for e in cm}
    for a, b in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    med_sx = {s.entity: float(np.median(s.y)) for s in sx}
    med_t1 = {q: float(np.median(s.y)) for q, s in t1.items()}
    med_t2 = {q: float(np.median(s.y)) for q, s in t2.items()}
    out = {}
    for name, d in (("sx", med_sx), ("T1", med_t1), ("T2", med_t2)):
        groups = {k: [d[q] for q in d if deg.get(q) == k and q != 72] for k in (1, 2, 3)}
        kw = stats.kruskal(*groups.values())
        out[name] = {
            "n": {str(k): len(v) for k, v in groups.items()},
            "medians": {str(k): float(np.median(v)) for k, v in groups.items()},
            "kruskal_p": float(kw.pvalue),
        }
    res["degree_tests"] = out
    res["n_edges"] = len(edges)

    # split-half stability
    mid = 1.7849e12  # 2026-07-25
    a, b = [], []
    for s in sx:
        m1, m2 = s.t_ms < mid, s.t_ms >= mid
        if m1.sum() >= 5 and m2.sum() >= 5:
            a.append(np.median(s.y[m1]))
            b.append(np.median(s.y[m2]))
    res["split_half_spearman"] = {
        "rho": float(stats.spearmanr(a, b).statistic),
        "n": len(a),
        "split_ms": mid,
        "split_iso": iso(mid),
    }

    # coupling selection control: near pairs paired with the previous T1 event of that qubit
    near_cur, near_prev, near_next, far_cur = [], [], [], []
    for s in sx:
        e = s.entity
        if e not in t1:
            continue
        a_ = t1[e]
        za = np.log10(a_.y)
        da = za - run_level(za)
        zs = np.log10(s.y)
        ds = zs - run_level(zs)
        i1, o1 = nearest(s.t_ms, a_.t_ms)
        near = np.abs(o1) <= 1.0
        far = (np.abs(o1) > 1.0) & (np.abs(o1) <= 6.0)
        for k in np.flatnonzero(near):
            if i1[k] >= 1 and i1[k] + 1 < a_.y.size:
                near_cur.append((ds[k], da[i1[k]]))
                near_prev.append((ds[k], da[i1[k] - 1]))
                near_next.append((ds[k], da[i1[k] + 1]))
        for k in np.flatnonzero(far):
            far_cur.append((ds[k], da[i1[k]]))

    def rho(pairs):
        x = np.array(pairs)
        ok = np.isfinite(x).all(axis=1)
        return float(stats.spearmanr(x[ok, 0], x[ok, 1]).statistic), int(ok.sum())

    res["near_pairs_control"] = {
        "near_current_T1": rho(near_cur),
        "near_previous_T1_event": rho(near_prev),
        "near_next_T1_event": rho(near_next),
        "far_current_T1": rho(far_cur),
    }
    # dropping the largest 1% of |sx deviation| (are spikes carrying the coupling?)
    x = np.array(near_cur + far_cur)
    ok = np.isfinite(x).all(axis=1)
    x = x[ok]
    thr = np.quantile(np.abs(x[:, 0]), 0.99)
    keep = np.abs(x[:, 0]) <= thr
    res["coupling_without_top1pct_sx_dev"] = {
        "rho_all_nonshifted": float(stats.spearmanr(x[:, 0], x[:, 1]).statistic),
        "rho_trimmed": float(stats.spearmanr(x[keep, 0], x[keep, 1]).statistic),
        "n": int(keep.sum()),
    }
    ddload.write_json(OUT, res)
    print("ok")


if __name__ == "__main__":
    main()
