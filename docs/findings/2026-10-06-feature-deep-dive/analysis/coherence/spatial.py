"""Spatial structure of coherence on the device: per-qubit levels on the map, neighbour
similarity, position effects, and same-round co-movement of deviations between qubits.

Writes ``results/coherence/spatial.json`` (including a 156-row per-qubit table).

Positions are the configuration ``coords`` (one version in all 1,317 files with a
configuration section; ``[x, y]`` per qubit index) and neighbours the undirected coupling map
(176 edges from the 352 directed ones). Per-qubit statistics are medians over the qubit's
events (first event excluded). Same-round co-movement uses device-wide rounds with at
least ``BIG_ROUND`` qubits and deviations from each qubit's running level.
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cohlib
import ddload

N_PERM = 9999
BIG_ROUND = 78
FAR_HOPS = 4
SEED = 20261006
REGIME3 = 1782604800000.0  # 2026-06-28T00:00:00Z


def graph(n: int, edges: set[tuple[int, int]]) -> tuple[list[list[int]], np.ndarray]:
    adj: list[list[int]] = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    dist = np.full((n, n), -1, dtype=int)
    for s in range(n):
        dist[s, s] = 0
        dq = deque([s])
        while dq:
            u = dq.popleft()
            for v in adj[u]:
                if dist[s, v] < 0:
                    dist[s, v] = dist[s, u] + 1
                    dq.append(v)
    return adj, dist


def morans_i(x: np.ndarray, w: np.ndarray, rng: np.random.Generator) -> dict[str, Any]:
    ok = np.isfinite(x)
    x = x[ok]
    w = w[np.ix_(ok, ok)]
    z = x - x.mean()
    s0 = w.sum()

    def stat(v: np.ndarray) -> float:
        return float(v.size / s0 * (v @ w @ v) / (v @ v))

    obs = stat(z)
    perm = np.array([stat(rng.permutation(z)) for _ in range(N_PERM)])
    return {
        "n": int(x.size),
        "morans_i": cohlib.r(obs),
        "expected_under_null": cohlib.r(-1.0 / (x.size - 1)),
        "perm_p_two_sided": cohlib.r(
            (np.sum(np.abs(perm - perm.mean()) >= abs(obs - perm.mean())) + 1) / (N_PERM + 1)
        ),
    }


def comovement(
    per: dict[int, tuple[np.ndarray, np.ndarray]], t_lo: float, dist: np.ndarray, n_q: int
) -> dict[str, Any]:
    stamps = np.concatenate([t for t, _ in per.values()])
    ents = np.concatenate([np.full(t.size, e) for e, (t, _) in per.items()])
    devs = np.concatenate([d for _, d in per.values()])
    keep = np.isfinite(devs) & (stamps >= t_lo)
    _, rid = cohlib.rounds(stamps)
    rounds = [
        k for k in np.unique(rid[keep]) if np.unique(ents[keep & (rid == k)]).size >= BIG_ROUND
    ]
    x = np.full((len(rounds), n_q), np.nan)
    for i, k in enumerate(rounds):
        m = keep & (rid == k)
        x[i, ents[m]] = devs[m]
    tot = np.nansum(x**2)
    rm = np.nanmedian(x, axis=1, keepdims=True)
    resid = x - rm
    r2 = 1.0 - np.nansum(resid**2) / tot
    msk = np.isfinite(resid)
    colmean = np.array(
        [np.mean(resid[msk[:, j], j]) if msk[:, j].any() else 0.0 for j in range(n_q)]
    )
    rc = np.where(msk, resid - colmean, 0.0)
    nn = msk.T.astype(float) @ msk.astype(float)
    cov = rc.T @ rc / np.maximum(nn, 1)
    sd = np.sqrt(np.diag(cov))
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = cov / np.outer(sd, sd)
    iu = np.triu_indices(n_q, 1)
    valid = (sd[iu[0]] > 0) & (sd[iu[1]] > 0) & (nn[iu] >= 20)
    dd_ = dist[iu]
    c = corr[iu]
    near = valid & (dd_ == 1)
    far = valid & (dd_ >= FAR_HOPS)
    mw = stats.mannwhitneyu(c[near], c[far])
    return {
        "rounds": len(rounds),
        "round_median_share_of_dev_variance": cohlib.r(r2),
        "coupled_pairs": int(near.sum()),
        "coupled_corr_median": cohlib.r(np.median(c[near])),
        "coupled_corr_mean": cohlib.r(np.mean(c[near])),
        "far_pairs": int(far.sum()),
        "far_corr_median": cohlib.r(np.median(c[far])),
        "far_corr_mean": cohlib.r(np.mean(c[far])),
        "mannwhitney_p_coupled_vs_far": cohlib.r(mw.pvalue),
        "corr_mean_by_hops_1_to_6": [cohlib.r(np.mean(c[valid & (dd_ == h)])) for h in range(1, 7)],
    }


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    rng = np.random.default_rng(SEED)
    out = cohlib.header("analysis/coherence/spatial.py")
    out["n_files"] = dd.n_files
    out["thresholds"] = {
        "permutations": N_PERM,
        "big_round_min_qubits": BIG_ROUND,
        "far_hops": FAR_HOPS,
        "seed": SEED,
    }
    n_q = len(dd.meta["qubits"])
    cv = dd.meta["config_values"]["coords"]
    versions = list(cv.values())
    coords = np.array(versions[0]["value"], dtype=float)
    edges = {(min(a, b), max(a, b)) for a, b in dd.meta["coupling_map"]}
    adj, dist = graph(n_q, edges)
    w = np.zeros((n_q, n_q))
    for a, b in edges:
        w[a, b] = w[b, a] = 1.0
    ed = np.array([np.hypot(*(coords[a] - coords[b])) for a, b in edges])
    deg = np.array([len(adj[q]) for q in range(n_q)])
    out["layout"] = {
        "coords_versions": len(versions),
        "coords_files": versions[0].get("files"),
        "undirected_edges": len(edges),
        "coupled_pair_euclidean_distance_quantiles": cohlib.q(ed),
        "degree_counts_1_2_3": [int(np.sum(deg == k)) for k in (1, 2, 3)],
        "x_range": [cohlib.r(coords[:, 0].min()), cohlib.r(coords[:, 0].max())],
        "y_range": [cohlib.r(coords[:, 1].min()), cohlib.r(coords[:, 1].max())],
        "graph_diameter": int(dist.max()),
    }

    # ---- per-qubit statistics
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    pairs, _ = cohlib.paired(dd)
    stat = {
        k: np.full(n_q, np.nan) for k in ("T1", "T2", "gphi", "s", "scale_T1", "dip_rate", "n_T1")
    }
    dev1: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    dev2: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for s in s1:
        z = np.log10(s.y[1:])
        stat["T1"][s.entity] = np.median(z)
        stat["n_T1"][s.entity] = z.size
        if z.size >= 20:
            dv = z - cohlib.rolling_level(z)
            f = np.isfinite(dv)
            stat["scale_T1"][s.entity] = 1.4826 * np.median(np.abs(dv[f] - np.median(dv[f])))
            stat["dip_rate"][s.entity] = np.mean(dv[f] <= -np.log10(2.0))
            dev1[s.entity] = (s.t_ms[1:], dv)
    for s in s2:
        z = np.log10(s.y[1:])
        stat["T2"][s.entity] = np.median(z)
        if z.size >= 20:
            dev2[s.entity] = (s.t_ms[1:], z - cohlib.rolling_level(z))
    for p in pairs:
        g = cohlib.gamma_phi(p.t1, p.t2)
        stat["gphi"][p.entity] = np.median(np.log10(g[g > 0])) if np.any(g > 0) else np.nan
        stat["s"][p.entity] = np.median(np.log10(p.t2 / (2 * p.t1)))

    sp: dict[str, Any] = {}
    centre = coords.mean(axis=0)
    rad = np.hypot(*(coords - centre).T)
    rows_y = coords[:, 1]
    for k in ("T1", "T2", "gphi", "s", "scale_T1", "dip_rate"):
        x = stat[k]
        ok = np.isfinite(x)
        ys = np.unique(rows_y[ok])
        kw_rows = stats.kruskal(
            *[x[ok & (rows_y == y)] for y in ys if np.sum(ok & (rows_y == y)) >= 3]
        )
        kw_deg = stats.kruskal(
            *[x[ok & (deg == d)] for d in (1, 2, 3) if np.sum(ok & (deg == d)) >= 3]
        )
        rr = stats.spearmanr(rad[ok], x[ok])
        rx = stats.spearmanr(coords[ok, 0], x[ok])
        ry = stats.spearmanr(coords[ok, 1], x[ok])
        hop = []
        for h in (1, 2, 3, 4):
            iu = np.argwhere((dist == h) & np.triu(np.ones_like(dist, dtype=bool), 1))
            dv = [0.5 * (x[a] - x[b]) ** 2 for a, b in iu if ok[a] and ok[b]]
            hop.append(cohlib.r(np.mean(dv)))
        iu = np.argwhere((dist >= 5) & np.triu(np.ones_like(dist, dtype=bool), 1))
        far = [0.5 * (x[a] - x[b]) ** 2 for a, b in iu if ok[a] and ok[b]]
        sp[k] = {
            "moran": morans_i(x, w, rng),
            "graph_semivariance_hops_1_2_3_4": hop,
            "graph_semivariance_hops_5plus": cohlib.r(np.mean(far)),
            "kruskal_rows_p": cohlib.r(kw_rows.pvalue),
            "rows_tested": len(ys),
            "kruskal_degree_p": cohlib.r(kw_deg.pvalue),
            "median_by_degree_1_2_3": [
                cohlib.r(np.median(x[ok & (deg == d)])) if np.any(ok & (deg == d)) else None
                for d in (1, 2, 3)
            ],
            "spearman_vs_distance_from_centre": cohlib.r(rr.statistic),
            "spearman_vs_distance_from_centre_p": cohlib.r(rr.pvalue),
            "spearman_vs_x": cohlib.r(rx.statistic),
            "spearman_vs_x_p": cohlib.r(rx.pvalue),
            "spearman_vs_y": cohlib.r(ry.statistic),
            "spearman_vs_y_p": cohlib.r(ry.pvalue),
        }
    out["per_qubit_stats"] = sp
    n_tests = 6 * len(sp)
    out["position_tests"] = {
        "tests": n_tests,
        "note": "rows, degree, distance from centre, x, y and Moran per statistic",
        "bonferroni_threshold_at_0.05": cohlib.r(0.05 / n_tests),
    }

    # ---- across qubits: T1 against T2, dephasing and s
    def sr(a: str, b: str) -> dict[str, Any]:
        ok = np.isfinite(stat[a]) & np.isfinite(stat[b])
        r_ = stats.spearmanr(stat[a][ok], stat[b][ok])
        return {"n": int(ok.sum()), "spearman": cohlib.r(r_.statistic), "p": cohlib.r(r_.pvalue)}

    out["across_qubits"] = {
        "T1_vs_T2": sr("T1", "T2"),
        "T1_vs_gamma_phi": sr("T1", "gphi"),
        "T2_vs_gamma_phi": sr("T2", "gphi"),
        "T1_vs_scale_T1": sr("T1", "scale_T1"),
        "T1_vs_dip_rate": sr("T1", "dip_rate"),
        "s_vs_T2": sr("s", "T2"),
    }

    # ---- same-round co-movement between qubits
    out["comovement"] = {
        "T1_all": comovement(dev1, -np.inf, dist, n_q),
        "T1_from_2026-06-28": comovement(dev1, REGIME3, dist, n_q),
        "T2_all": comovement(dev2, -np.inf, dist, n_q),
        "T2_from_2026-06-28": comovement(dev2, REGIME3, dist, n_q),
    }

    # ---- per-qubit table
    table = []
    for q in range(n_q):
        table.append(
            {
                "q": q,
                "x": cohlib.r(coords[q, 0], 4),
                "y": cohlib.r(coords[q, 1], 4),
                "deg": int(deg[q]),
                "n_T1": None if not np.isfinite(stat["n_T1"][q]) else int(stat["n_T1"][q]),
                "T1_us": None
                if not np.isfinite(stat["T1"][q])
                else cohlib.r(10 ** stat["T1"][q], 4),
                "T2_us": None
                if not np.isfinite(stat["T2"][q])
                else cohlib.r(10 ** stat["T2"][q], 4),
                "gphi_per_ms": None
                if not np.isfinite(stat["gphi"][q])
                else cohlib.r(1000 * 10 ** stat["gphi"][q], 4),
                "s": None if not np.isfinite(stat["s"][q]) else cohlib.r(10 ** stat["s"][q], 4),
                "scale_T1": cohlib.r(stat["scale_T1"][q], 4),
                "dip_rate": cohlib.r(stat["dip_rate"][q], 4),
            }
        )
    out["per_qubit_table"] = table
    t1 = np.array([np.nan if r_["T1_us"] is None else r_["T1_us"] for r_ in table], dtype=float)
    order = np.argsort(t1)
    out["lowest_T1_qubits"] = [{"q": int(i), "T1_us": cohlib.r(t1[i], 4)} for i in order[:8]]
    out["highest_T1_qubits"] = [
        {"q": int(i), "T1_us": cohlib.r(t1[i], 4)} for i in order[np.isfinite(t1[order])][-5:]
    ]
    cohlib.write("spatial.json", out)


if __name__ == "__main__":
    main()
