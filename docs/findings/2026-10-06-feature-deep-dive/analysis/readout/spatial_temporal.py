"""Spatial structure on the device map, and temporal structure (levels, change points, season).

Writes ``results/readout/spatial_temporal.json``.

Spatial: per-qubit medians of ``log10`` values over each field's lifetime, against the
configuration coordinates and the coupling graph (Moran's I with a permutation test,
row/bridge membership, degree, and the stability of the ranking between the first and last
full month).

Temporal: the device median per readout session; descriptive change points by binary
segmentation (Gaussian mean-shift cost on ``log10`` values, penalty ``3 sigma^2 ln n``, sigma
from the MAD of first differences, minimum segment length given per series); per-qubit
change points of ``ro``; value seasonality by UTC hour and weekday on residuals from each
qubit's centred running median (6 events each side, the event itself excluded), with
Kruskal-Wallis tests and the epsilon-squared effect size. These are descriptive: the
penalty and the minimum segment length are choices, not estimates.
"""

from __future__ import annotations

import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc

RNG = np.random.default_rng(20261006)
N_PERM = 5000


def morans_i(x: np.ndarray, edges: list[tuple[int, int]]) -> dict[str, Any]:
    ok = np.isfinite(x)
    e = [(a, b) for a, b in edges if ok[a] and ok[b]]
    idx = np.flatnonzero(ok)
    pos = {q: i for i, q in enumerate(idx)}
    z = x[idx] - x[idx].mean()
    ea = np.array([pos[a] for a, _ in e])
    eb = np.array([pos[b] for _, b in e])

    def stat(zz: np.ndarray) -> float:
        return float(idx.size / ea.size * np.sum(zz[ea] * zz[eb]) / np.sum(zz * zz))

    obs = stat(z)
    perm = np.array([stat(RNG.permutation(z)) for _ in range(N_PERM)])
    return {
        "qubits": int(idx.size),
        "edges": int(ea.size),
        "morans_i": round(obs, 4),
        "expected_under_null": round(-1.0 / (idx.size - 1), 4),
        "permutation_p_two_sided": round(
            float((np.sum(np.abs(perm) >= abs(obs)) + 1) / (N_PERM + 1)), 5
        ),
    }


def binseg(x: np.ndarray, min_seg: int, max_cp: int = 8) -> list[int]:
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n < 2 * min_seg:
        return []
    sig = 1.4826 * np.median(np.abs(np.diff(x) - np.median(np.diff(x)))) / np.sqrt(2.0)
    if sig <= 0:
        return []
    pen = 3.0 * sig * sig * np.log(n)
    cps: list[int] = []
    segs = [(0, n)]
    while len(cps) < max_cp:
        best = (0.0, -1, -1)
        for a, b in segs:
            if b - a < 2 * min_seg:
                continue
            seg = x[a:b]
            cs = np.cumsum(seg)
            tot = cs[-1]
            k = np.arange(min_seg, b - a - min_seg + 1)
            left = cs[k - 1]
            m = b - a
            gain = left**2 / k + (tot - left) ** 2 / (m - k) - tot**2 / m
            j = int(np.argmax(gain))
            if gain[j] > best[0]:
                best = (float(gain[j]), a, a + int(k[j]))
        if best[1] < 0 or best[0] <= pen:
            break
        cps.append(best[2])
        new = []
        for a, b in segs:
            if a <= best[2] < b:
                new += [(a, best[2]), (best[2], b)]
            else:
                new.append((a, b))
        segs = new
    return sorted(cps)


def per_qubit_median(ns: rc.NoiseSeries) -> np.ndarray:
    out = np.full(156, np.nan)
    for x in ns.series:
        y = np.asarray(x.y)
        y = y[np.isfinite(y) & (y > 0)]
        if y.size:
            out[x.entity] = float(np.median(np.log10(y)))
    return out


def field_median(dd: ddload.DD, field: str, mask_ge1: bool, floor: float = 0.0) -> np.ndarray:
    v = np.array(dd.v(field), dtype=np.float64)
    if mask_ge1:
        v = np.where(v >= 1.0, np.nan, v)
    v = np.where(v > floor, v, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out: np.ndarray = np.nanmedian(np.log10(v), axis=0)
    return out


def seasonality(ns: rc.NoiseSeries, kinds: tuple[str, ...]) -> dict[str, Any]:
    res, hrs, wds = [], [], []
    for x, kind in zip(ns.series, ns.kind, strict=True):
        y = np.asarray(x.y)
        ok = np.isfinite(y) & (y > 0) & np.isin(kind, kinds)
        idx = np.flatnonzero(ok)
        if idx.size < 20:
            continue
        z = np.log10(y[idx])
        t = x.t_ms[idx]
        for i in range(6, z.size - 6):
            nb = np.concatenate([z[i - 6 : i], z[i + 1 : i + 7]])
            res.append(z[i] - np.median(nb))
            dt = datetime.fromtimestamp(t[i] / 1000.0, UTC)
            hrs.append(dt.hour // 4)
            wds.append(dt.weekday())
    r = np.array(res)
    h = np.array(hrs)
    w = np.array(wds)
    out: dict[str, Any] = {"residuals": int(r.size)}
    for label, g, k in (("utc_hour_bin_4h", h, 6), ("weekday_mon0", w, 7)):
        groups = [r[g == i] for i in range(k)]
        kw = stats.kruskal(*groups)
        out[label] = {
            "median_residual_by_bin": [round(float(np.median(x)), 4) for x in groups],
            "n_by_bin": [int(x.size) for x in groups],
            "kruskal_p": float(f"{kw.pvalue:.3g}"),
            "epsilon_squared": round(float(kw.statistic / (r.size - 1)), 5),
        }
    return out


def main() -> None:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    ns = rc.noise_series(r, c, s)
    coords = np.array(
        next(iter(dd.meta["config_values"]["coords"].values()))["value"], dtype=np.float64
    )
    edges_dir = [tuple(e) for e in dd.meta["coupling_map"]]
    edges = sorted({(min(a, b), max(a, b)) for a, b in edges_dir})
    deg = np.zeros(156, dtype=np.int64)
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    is_bridge = (coords[:, 1] % 2) == 0

    meds = {
        "ro": per_qubit_median(ns["ro"]),
        "p0g1_fresh": per_qubit_median(ns["p0g1_fresh"]),
        "p1g0": per_qubit_median(ns["p1g0"]),
        "init_error": field_median(dd, "q.init_error", False, floor=1e-6),
        "measure_2": field_median(dd, "g1.measure_2.gate_error", True),
    }
    spatial: dict[str, Any] = {
        "coords_distinct_sets": len(dd.meta["config_values"]["coords"]),
        "rows_y_values": sorted({int(v) for v in coords[:, 1]}),
        "bridge_qubits": int(is_bridge.sum()),
        "degree_counts": {str(k): int(np.sum(deg == k)) for k in (1, 2, 3)},
    }
    for name, m in meds.items():
        ok = np.isfinite(m)
        kw_rows = stats.kruskal(*[m[ok & (coords[:, 1] == y)] for y in sorted(set(coords[ok, 1]))])
        spatial[name] = {
            "qubits": int(ok.sum()),
            "median_of_medians": float(f"{10 ** np.median(m[ok]):.5g}"),
            "q10_q90_of_medians": [float(f"{10**v:.5g}") for v in np.quantile(m[ok], [0.1, 0.9])],
            "moran_coupling_graph": morans_i(m, edges),
            "moran_coupling_graph_ranks": morans_i(
                np.where(ok, stats.rankdata(np.where(ok, m, np.inf)), np.nan), edges
            ),
            "moran_coupling_graph_excluding_q72": morans_i(
                np.where(np.arange(156) == 72, np.nan, m), edges
            ),
            "spearman_vs_x": rc.spearman(coords[ok, 0], m[ok]),
            "spearman_vs_y": rc.spearman(coords[ok, 1], m[ok]),
            "kruskal_by_row_p": float(f"{kw_rows.pvalue:.3g}"),
            "bridge_vs_row_median": [
                float(f"{10 ** np.median(m[ok & is_bridge]):.5g}"),
                float(f"{10 ** np.median(m[ok & ~is_bridge]):.5g}"),
                float(f"{stats.mannwhitneyu(m[ok & is_bridge], m[ok & ~is_bridge]).pvalue:.3g}"),
            ],
            "worst_10": [
                {
                    "qubit": int(q),
                    "median": float(f"{10 ** m[q]:.4g}"),
                    "xy": [int(coords[q, 0]), int(coords[q, 1])],
                }
                for q in np.argsort(-np.where(ok, m, -99))[:10]
            ],
        }
    # Ranking stability: per-qubit median of log10 ro in June against September.
    months = {}
    for mo in ("2026-06", "2026-09"):
        lo = rc.iso_ms(mo + "-01T00:00:00Z")
        hi = rc.iso_ms(("2026-07" if mo == "2026-06" else "2026-10") + "-01T00:00:00Z")
        mm = np.full(156, np.nan)
        for x in ns["ro"].series:
            y = np.asarray(x.y)
            sel = np.isfinite(y) & (x.t_ms >= lo) & (x.t_ms < hi)
            if sel.sum() >= 10:
                mm[x.entity] = float(np.median(np.log10(y[sel])))
        months[mo] = mm
    spatial["ro_rank_stability_june_vs_september"] = rc.spearman(
        months["2026-06"], months["2026-09"]
    )
    spatial["cross_field_spearman_of_medians"] = {
        f"{a}_vs_{b}": rc.spearman(meds[a], meds[b])
        for a, b in (("ro", "measure_2"), ("p0g1_fresh", "p1g0"), ("ro", "init_error"))
    }

    # Temporal: device median per session, change points.
    temporal: dict[str, Any] = {}
    big = np.flatnonzero(s.kind != "small")
    for name in ("ro", "p0g1_fresh", "p1g0"):
        mat = np.full((s.start_ms.size, 156), np.nan)
        for x in ns[name].series:
            y = np.asarray(x.y)
            si = s.index(x.t_ms)
            okk = (si >= 0) & np.isfinite(y) & (y > 0)
            mat[si[okk], x.entity] = np.log10(y[okk])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            dev = np.nanmedian(mat[big], axis=1)
        okd = np.isfinite(dev)
        dev, tt = dev[okd], s.start_ms[big][okd]
        cps = binseg(dev, min_seg=15)  # cap of 8 change points; the count is stored below
        bounds = [0, *cps, dev.size]
        temporal[f"{name}_device_median_per_session"] = {
            "sessions": int(dev.size),
            "change_point_cap": 8,
            "q": [float(f"{10**v:.5g}") for v in np.quantile(dev, [0.0, 0.1, 0.5, 0.9, 1.0])],
            "change_points": [
                {
                    "session_start": rc.iso(float(tt[k])),
                    "level_before": float(f"{10 ** np.median(dev[bounds[i] : k]):.5g}"),
                    "level_after": float(f"{10 ** np.median(dev[k : bounds[i + 2]]):.5g}"),
                }
                for i, k in enumerate(cps)
            ],
        }
    # Monthly device medians (median over qubits of each qubit's monthly median).
    monthly: dict[str, Any] = {}
    for name in ("ro", "p0g1_fresh", "p1g0"):
        rows = {}
        for mo in ("2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"):
            lo = rc.iso_ms(mo + "-01T00:00:00Z")
            y_, m_ = int(mo[:4]), int(mo[5:])
            hi = rc.iso_ms(f"{y_ + (m_ == 12)}-{m_ % 12 + 1:02d}-01T00:00:00Z")
            qm = []
            for x in ns[name].series:
                y = np.asarray(x.y)
                sel = np.isfinite(y) & (x.t_ms >= lo) & (x.t_ms < hi)
                if sel.sum() >= 5:
                    qm.append(float(np.median(y[sel])))
            rows[mo] = float(f"{np.median(qm):.5g}") if qm else None
        monthly[name] = rows
    temporal["monthly_device_median_of_qubit_medians"] = monthly
    # Per-qubit change points of log10 ro.
    n_cp, cp_times = [], []
    for x in ns["ro"].series:
        y = np.asarray(x.y)
        okk = np.isfinite(y) & (y > 0)
        z, t = np.log10(y[okk]), x.t_ms[okk]
        cps = binseg(z, min_seg=30)
        n_cp.append(len(cps))
        cp_times.extend(t[k] for k in cps)
    cpt = np.array(cp_times)
    c1 = rc.iso_ms(rc.CHANGE_1)
    c2 = rc.iso_ms(rc.CHANGE_2)
    weeks = np.array([datetime.fromtimestamp(v / 1000.0, UTC).strftime("%G-W%V") for v in cpt])
    wk, wc = np.unique(weeks, return_counts=True)
    temporal["per_qubit_ro_change_points"] = {
        "rule": "binary segmentation, min segment 30 events, penalty 3 sigma^2 ln n",
        "change_points_per_qubit_q": rc.quantiles(np.array(n_cp, dtype=np.float64)),
        "qubits_with_none": int(np.sum(np.array(n_cp) == 0)),
        "cap_per_series": 8,
        "qubits_at_cap": int(np.sum(np.array(n_cp) == 8)),
        "total": int(cpt.size),
        "within_1_day_of_change_1": int(np.sum(np.abs(cpt - c1) <= 8.64e7)),
        "within_1_day_of_change_2": int(np.sum(np.abs(cpt - c2) <= 8.64e7)),
        "top_weeks": [
            {"week": str(a), "change_points": int(b)}
            for a, b in sorted(zip(wk, wc, strict=True), key=lambda z: -z[1])[:6]
        ],
    }
    # Level wander: per qubit, the 10-90% range of a 42-event running median (about a week).
    wander = []
    for x in ns["ro"].series:
        y = np.asarray(x.y)
        z = np.log10(y[np.isfinite(y) & (y > 0)])
        if z.size < 84:
            continue
        rm = np.array([np.median(z[i : i + 42]) for i in range(0, z.size - 42, 6)])
        wander.append(float(np.quantile(rm, 0.9) - np.quantile(rm, 0.1)))
    temporal["ro_weekly_level_range_decades_q"] = rc.quantiles(np.array(wander))
    # Seasonality of values.
    temporal["seasonality"] = {
        f"{name}_{label}": seasonality(ns[name], kinds)
        for name in ("ro", "p0g1_fresh", "p1g0")
        for label, kinds in (("all", ("even", "mixed")), ("mixed_only", ("mixed",)))
    }
    rc.write(
        "spatial_temporal.json",
        "spatial_temporal.py",
        {"n_files": dd.n_files, "spatial": spatial, "temporal": temporal},
    )


if __name__ == "__main__":
    main()
