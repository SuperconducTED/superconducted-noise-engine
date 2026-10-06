# ruff: noqa: B905, B007, E501, C416, F841
"""Independent re-computation of the load-bearing numbers of 05-two-qubit-gates-couplings.md.

Written from ddload only (the owner's code is not imported). Recomputes: direction identity,
event counts and medians, lag-1 autocorrelation of log changes, the one-round variogram ratio,
the shared-qubit local-deviation correlation, cz-vs-rzz coupler medians, the zz burst
statistics, the coherence limit at median T1 and T2, and the rzz event rate by coverage period.

Writes ``results/verify/gates_2q/core_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "verify" / "gates_2q" / "core_check.json"
MS_H = 3.6e6


def f(x, nd=4):
    return float(f"{x:.{nd}g}")


def canon_cols(dd):
    edges = [tuple(int(x) for x in e) for e in dd.entities("g2.cz.gate_error")]
    idx = {e: i for i, e in enumerate(edges)}
    fwd, rev, names = [], [], []
    for i, (a, b) in enumerate(edges):
        if a < b:
            fwd.append(i)
            rev.append(idx[(b, a)])
            names.append((a, b))
    return fwd, rev, names


def events(dd, gate, fwd):
    ser = ddload.series(
        dd, f"g2.{gate}.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error
    )
    keep = set(fwd)
    return [s for s in ser if s.entity in keep]


def lag1(series_list):
    a, b = [], []
    for s in series_list:
        y = np.asarray(s.y, float)
        y = y[y > 0]
        if y.size < 3:
            continue
        d = np.diff(np.log10(y))
        a.append(d[:-1])
        b.append(d[1:])
    a, b = np.concatenate(a), np.concatenate(b)
    return float(np.corrcoef(a, b)[0, 1]), int(a.size)


def direction_identity(dd, gate, fwd, rev):
    v = np.asarray(dd.v(f"g2.{gate}.gate_error"))
    d = np.asarray(dd.d(f"g2.{gate}.gate_error"))
    vf, vr = v[:, fwd], v[:, rev]
    df, dr = d[:, fwd], d[:, rev]
    ph = vf >= 1
    vm = int(np.sum(vf != vr))
    dm = df != dr
    return {
        "records": int(vf.size),
        "value_mismatch": vm,
        "date_mismatch": int(dm.sum()),
        "date_mismatch_in_placeholder": int((dm & ph).sum()),
        "placeholder_records": int(ph.sum()),
        "median_offset_us_in_mismatch": f(float(np.median(np.abs(df - dr)[dm]) * 1000.0)),
    }


def variogram_ratio(ser):
    vg = ddload.variogram(ser)
    bins = vg["bins"]
    one = next(
        b for b in bins if b["lag_h_lo"] == 18.0 or (b["pairs"] >= 1000 and b["lag_h_lo"] >= 12)
    )
    long = [b for b in bins if b["lag_h_lo"] >= 744 and b["pairs"]]
    num = sum(b["semivariance"] * b["pairs"] for b in long)
    den = sum(b["pairs"] for b in long)
    return {
        "first_bin_ge1000_pairs": [one["lag_h_lo"], one["lag_h_hi"], one["pairs"]],
        "one_round_semivariance": one["semivariance"],
        "long_lag_mean_ge744h": f(num / den),
        "ratio": f(one["semivariance"] / (num / den)),
    }


def local_dev(y, t):
    """Deviation of log10 y from the median of up to 3 prior + 3 following events (self excluded)."""
    z = np.log10(y)
    n = z.size
    out = np.full(n, np.nan)
    for i in range(n):
        nb = np.r_[z[max(0, i - 3) : i], z[i + 1 : i + 4]]
        if nb.size >= 3:
            out[i] = z[i] - np.median(nb)
    return out


def shared_qubit_corr(ser, names, fwd):
    col_to_name = {c: n for c, n in zip(fwd, names)}
    allt = np.sort(np.concatenate([np.asarray(s.t_ms, float) for s in ser if len(s.y) >= 8]))
    gaps = np.diff(allt) / MS_H
    starts = np.r_[0, np.flatnonzero(gaps > 0.25) + 1]
    bounds = allt[starts]
    dev = {}
    for s in ser:
        y = np.asarray(s.y, float)
        t = np.asarray(s.t_ms, float)
        ok = y > 0
        y, t = y[ok], t[ok]
        if y.size < 8:
            continue
        dv = local_dev(y, t)
        rid = np.searchsorted(bounds, t, side="right") - 1
        dev[col_to_name[s.entity]] = (rid, dv)
    # remove round medians
    rounds = {}
    for name, (rid, dv) in dev.items():
        for r, v in zip(rid, dv):
            if np.isfinite(v):
                rounds.setdefault(int(r), []).append(v)
    rmed = {r: float(np.median(v)) for r, v in rounds.items()}
    mapped = {}
    for name, (rid, dv) in dev.items():
        m = {}
        for r, v in zip(rid, dv):
            r = int(r)
            if np.isfinite(v) and r not in m:
                m[r] = v - rmed[r]
        mapped[name] = m
    names_l = sorted(mapped)
    share, far = ([], []), ([], [])
    # hop distance on line graph via shared qubits
    adj = {n: set() for n in names_l}
    for i, a in enumerate(names_l):
        for b in names_l[i + 1 :]:
            if set(a) & set(b):
                adj[a].add(b)
                adj[b].add(a)
    n_share_pairs = sum(len(v) for v in adj.values()) // 2
    for i, a in enumerate(names_l):
        for b in names_l[i + 1 :]:
            if b in adj[a]:
                dst = share
            else:
                continue
            common = set(mapped[a]) & set(mapped[b])
            for r in common:
                dst[0].append(mapped[a][r])
                dst[1].append(mapped[b][r])
    rho = spearmanr(share[0], share[1])[0]
    return (
        {
            "coupler_pairs_sharing_qubit_with_series": n_share_pairs,
            "n_matched": len(share[0]),
            "spearman": f(float(rho), 3),
        },
        mapped,
        adj,
    )


def far_corr(mapped, adj, rng, n_pairs=3000):
    names_l = sorted(mapped)
    # BFS hops
    hops = {}
    for a in names_l:
        dist = {a: 0}
        frontier = [a]
        while frontier:
            nxt = []
            for u in frontier:
                for w in adj[u]:
                    if w not in dist:
                        dist[w] = dist[u] + 1
                        nxt.append(w)
            frontier = nxt
        hops[a] = dist
    far = []
    for i, a in enumerate(names_l):
        for b in names_l[i + 1 :]:
            if hops[a].get(b, 99) >= 4:
                far.append((a, b))
    x, y = [], []
    for a, b in far:
        for r in set(mapped[a]) & set(mapped[b]):
            x.append(mapped[a][r])
            y.append(mapped[b][r])
    return {
        "far_pairs": len(far),
        "n_matched": len(x),
        "spearman": f(float(spearmanr(x, y)[0]), 3),
    }


def coherence_limit(t_ns, t1_us, t2_us):
    t = t_ns * 1e-9
    t1, t2 = t1_us * 1e-6, t2_us * 1e-6
    fk = (1 + np.exp(-t / t1) + 2 * np.exp(-t / t2)) / 4
    return float(1 - (4 * fk * fk + 1) / 5)


def zz_stats(dd):
    zz = np.asarray(dd.v("gen.zz"))
    ch = np.abs(np.diff(zz, axis=0)) > 0
    per = ch.sum(axis=1)
    burst = np.flatnonzero(per > 0) + 1
    t = dd.file_ms[burst] / MS_H
    gaps = np.diff(t)
    res = {
        "files_with_any_change": int(burst.size),
        "bursts_changing_ge170": int((per[burst - 1] >= 170).sum()),
        "median_burst_gap_h": f(float(np.median(gaps))),
        "median_changes_per_burst": float(np.median(per[burst - 1])),
        "record_abs_zz_khz_median_nonzero": f(float(np.median(np.abs(zz[zz != 0])) * 1e6)),
    }
    ser = ddload.series(dd, "gen.zz", rule=ddload.ASSEMBLY, mask=ddload.zero_value)
    ser = [s for s in ser if np.sum(np.asarray(s.y) != 0) >= 3]
    nev = sum(len(s.y) for s in ser)
    a, b = [], []
    for s in ser:
        y = np.abs(np.asarray(s.y, float))
        y = y[y > 0]
        if y.size < 3:
            continue
        d = np.diff(np.log10(y))
        a.append(d[:-1])
        b.append(d[1:])
    a, b = np.concatenate(a), np.concatenate(b)
    res["abs_zz_value_events"] = int(nev)
    res["lag1_autocorr_log10_abs_zz_changes"] = f(float(np.corrcoef(a, b)[0, 1]), 3)
    res["lag1_pairs"] = int(a.size)
    zeros_all = np.flatnonzero(np.all(zz == 0, axis=0))
    res["couplers_all_zero"] = [dd.meta["couplers"][i] for i in zeros_all]
    return res


def main():
    dd = ddload.DD()
    fwd, rev, names = canon_cols(dd)
    out = {"header": ddload.result_header("verify/gates_2q", "v_core.py")}
    out["direction_identity"] = {g: direction_identity(dd, g, fwd, rev) for g in ("cz", "rzz")}
    ev = {g: events(dd, g, fwd) for g in ("cz", "rzz")}
    out["events"] = {}
    for g in ("cz", "rzz"):
        y = np.concatenate([np.asarray(s.y, float) for s in ev[g]])
        rho, n = lag1(ev[g])
        out["events"][g] = {
            "n_events": int(y.size),
            "median": f(float(np.median(y)), 3),
            "lag1_autocorr": f(rho, 3),
            "lag1_pairs": n,
            "variogram": variogram_ratio(ev[g]),
        }
    # split-period event rate
    last = dd.file("last_update_ms")
    split_file = np.flatnonzero(dd.file("has_configuration"))
    stems = dd.meta["stems"]
    split_idx = next(i for i, s in enumerate(stems) if str(s).startswith("20260805T234531"))
    split_ms = dd.file_ms[split_idx]
    out["split_index"] = int(split_idx)
    for g in ("cz", "rzz"):
        t = np.concatenate([np.asarray(s.t_ms, float) for s in ev[g]])
        # event stamps are measurement stamps; rate = events per coupler per day by file-time of event
        start = dd.file_ms[0]
        end = dd.file_ms[-1]
        pre = (t < split_ms).sum()
        post = (t >= split_ms).sum()
        out["events"][g]["rate_per_coupler_day_before"] = f(
            pre / len(names) / ((split_ms - start) / MS_H / 24)
        )
        out["events"][g]["rate_per_coupler_day_from"] = f(
            post / len(names) / ((end - split_ms) / MS_H / 24)
        )
    # cz vs rzz coupler medians
    med = {}
    for g in ("cz", "rzz"):
        med[g] = {s.entity: float(np.median(s.y)) for s in ev[g]}
    both = sorted(set(med["cz"]) & set(med["rzz"]))
    rho = spearmanr([med["cz"][c] for c in both], [med["rzz"][c] for c in both])[0]
    ratio = np.array([med["rzz"][c] / med["cz"][c] for c in both])
    out["cz_vs_rzz_coupler_medians"] = {
        "n": len(both),
        "spearman": f(float(rho), 3),
        "median_ratio_rzz_over_cz": f(float(np.median(ratio)), 3),
    }
    # shared-qubit local deviation correlation
    for g in ("cz", "rzz"):
        res, mapped, adj = shared_qubit_corr(ev[g], names, fwd)
        res["far_4plus_hops"] = far_corr(mapped, adj, None)
        out.setdefault("shared_qubit_deviation", {})[g] = res
    # coherence limit at medians
    t1 = np.asarray(dd.v("q.T1"), float)
    t2 = np.asarray(dd.v("q.T2"), float)
    m1 = float(np.nanmedian(t1[np.isfinite(t1) & (t1 > 0)]))
    m2 = float(np.nanmedian(t2[np.isfinite(t2) & (t2 > 0)]))
    lim = coherence_limit(68, m1, m2)
    out["coherence"] = {
        "median_T1_raw_units": f(m1),
        "median_T2_raw_units": f(m2),
        "limit_68ns_if_us": f(lim),
    }
    out["zz"] = zz_stats(dd)
    ddload.write_json(OUT, out)
    print(OUT)


if __name__ == "__main__":
    main()
