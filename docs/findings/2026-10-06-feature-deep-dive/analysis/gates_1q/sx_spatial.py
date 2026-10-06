"""Spatial structure of the sx gate error on the device.

Writes ``results/gates_1q/sx_spatial.json``. Per qubit (MEASURED events, placeholders
masked, so q72 has no value and is listed): the median of log10(sx), the robust size of its
changes, and its spike rate (deviation from the running level above log10(2)). Positions
are the configuration ``coords`` (one version across every file that has a configuration);
the graph is the configuration coupling map (``meta.json`` ``coupling_map``).

Tests (counted in ``tests_run``): Spearman of level against column and row, Kruskal-Wallis
of level by degree, Mann-Whitney of level by row type and of degree 3 against degree 2 within
the long rows (connector rows hold only degree-2 qubits), Moran's I (permutation) of level,
robust size and spike rate on the coupling graph, and same-round spike co-occurrence on
coupled pairs against pairs at least 4 hops apart.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import g1common as g

SCRIPT = "analysis/gates_1q/sx_spatial.py"
RNG = np.random.default_rng(20261006)
N_PERM = 9999


def coords(dd: ddload.DD) -> np.ndarray:
    vals = list(dd.meta["config_values"]["coords"].values())
    if len(vals) != 1:
        raise ValueError("expected one coords version")
    v = vals[0]["value"]
    arr = np.array(ast.literal_eval(v) if isinstance(v, str) else v, dtype=np.float64)
    if arr.shape != (156, 2):
        raise ValueError(f"unexpected coords shape {arr.shape}")
    return arr


def adjacency(dd: ddload.DD) -> tuple[list[set[int]], list[tuple[int, int]]]:
    adj: list[set[int]] = [set() for _ in range(156)]
    edges = set()
    for a, b in dd.meta["coupling_map"]:
        adj[a].add(b)
        adj[b].add(a)
        edges.add((min(a, b), max(a, b)))
    return adj, sorted(edges)


def hops(adj: list[set[int]]) -> np.ndarray:
    n = len(adj)
    d = np.full((n, n), -1, dtype=np.int64)
    for s in range(n):
        d[s, s] = 0
        dq = deque([s])
        while dq:
            u = dq.popleft()
            for w in adj[u]:
                if d[s, w] < 0:
                    d[s, w] = d[s, u] + 1
                    dq.append(w)
    return d


def morans_i(x: np.ndarray, edges: list[tuple[int, int]], ok: np.ndarray) -> dict[str, Any]:
    idx = np.flatnonzero(ok)
    pos = {int(q): k for k, q in enumerate(idx)}
    e = np.array([(pos[a], pos[b]) for a, b in edges if a in pos and b in pos])
    v = x[idx]

    def stat(vals: np.ndarray) -> np.ndarray:
        z = vals - vals.mean(axis=-1, keepdims=True)
        num = np.sum(z[..., e[:, 0]] * z[..., e[:, 1]], axis=-1) * 2.0
        den = np.sum(z * z, axis=-1)
        w = 2.0 * e.shape[0]
        out: np.ndarray = (v.size / w) * num / den
        return out

    obs = float(stat(v))
    perms = np.array([RNG.permutation(v) for _ in range(N_PERM)])
    null = stat(perms)
    p = (1.0 + float(np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean())))) / (N_PERM + 1)
    return {
        "I": g.rnd(obs, 4),
        "expected_under_null": g.rnd(-1.0 / (v.size - 1), 4),
        "null_mean": g.rnd(float(null.mean()), 4),
        "null_sd": g.rnd(float(null.std()), 4),
        "p_two_sided_perm": g.rnd(p, 5),
        "n_nodes": int(v.size),
        "n_edges": int(e.shape[0]),
    }


def main() -> int:
    dd = ddload.DD()
    series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    xy = coords(dd)
    adj, edges = adjacency(dd)
    deg = np.array([len(a) for a in adj])
    level = np.full(156, np.nan)
    rsd = np.full(156, np.nan)
    srate = np.full(156, np.nan)
    spike_rounds: dict[int, set[int]] = {}
    present_rounds: dict[int, set[int]] = {}
    all_t = np.concatenate([s.t_ms for s in series])
    _, rid_all = g.rounds(all_t)
    offset = 0
    for s in series:
        z = np.log10(s.y)
        dz = np.diff(z)
        level[s.entity] = float(np.median(z))
        rsd[s.entity] = 1.4826 * float(np.median(np.abs(dz - np.median(dz)))) / np.sqrt(2.0)
        r = z - g.running_level(z)
        ok = np.isfinite(r)
        up = ok & (r > g.LOG10_2)
        srate[s.entity] = float(up.sum() / ok.sum())
        rid = rid_all[offset : offset + s.y.size]
        offset += s.y.size
        spike_rounds[s.entity] = set(rid[up].tolist())
        present_rounds[s.entity] = set(rid[ok].tolist())
    ok = np.isfinite(level)
    missing = [int(q) for q in np.flatnonzero(~ok)]
    col, row = xy[:, 0], xy[:, 1]
    rows_full = np.isin(row, [r for r in np.unique(row) if np.sum(row == r) > 8])
    tests: dict[str, Any] = {}
    tests["level_vs_column_spearman"] = g.spearman(col[ok], level[ok])
    tests["level_vs_row_spearman"] = g.spearman(row[ok], level[ok])
    groups = {int(k): level[ok & (deg == k)] for k in sorted(set(deg[ok].tolist()))}
    tests["level_by_degree_kruskal"] = g.kruskal(list(groups.values()))
    tests["level_by_degree_median"] = {
        str(k): {"n": int(v.size), "median": float(f"{10 ** np.median(v):.4g}")}
        for k, v in groups.items()
    }
    a, b = level[ok & rows_full], level[ok & ~rows_full]
    mw = stats.mannwhitneyu(a, b)
    tests["level_long_rows_vs_connector_rows_mannwhitney"] = {
        "n_long_rows": int(a.size),
        "n_connector_rows": int(b.size),
        "median_long_rows": float(f"{10 ** np.median(a):.4g}"),
        "median_connector_rows": float(f"{10 ** np.median(b):.4g}"),
        "p": float(f"{float(mw.pvalue):.3g}"),
    }
    a3 = level[ok & rows_full & (deg == 3)]
    a2 = level[ok & rows_full & (deg == 2)]
    mw3 = stats.mannwhitneyu(a3, a2)
    tests["level_degree3_vs_degree2_within_long_rows_mannwhitney"] = {
        "n_degree3": int(a3.size),
        "n_degree2": int(a2.size),
        "median_degree3": float(f"{10 ** np.median(a3):.4g}"),
        "median_degree2": float(f"{10 ** np.median(a2):.4g}"),
        "p": float(f"{float(mw3.pvalue):.3g}"),
    }
    tests["morans_i_level"] = morans_i(level, edges, ok)
    tests["morans_i_robust_change_size"] = morans_i(rsd, edges, ok)
    tests["morans_i_spike_rate"] = morans_i(srate, edges, ok)
    d = hops(adj)
    co: dict[str, Any] = {}
    for label, sel in (("coupled", lambda h: h == 1), ("ge_4_hops", lambda h: h >= 4)):
        obs, exp = 0.0, 0.0
        npairs = 0
        for i in np.flatnonzero(ok):
            for j in np.flatnonzero(ok):
                if j <= i or not sel(d[i, j]):
                    continue
                common = present_rounds[i] & present_rounds[j]
                if not common:
                    continue
                si = spike_rounds[i] & common
                sj = spike_rounds[j] & common
                obs += len(si & sj)
                exp += len(si) * len(sj) / len(common)
                npairs += 1
        co[label] = {
            "pairs": npairs,
            "observed_joint_spike_rounds": int(obs),
            "expected_if_independent": g.rnd(exp, 2),
            "ratio": g.rnd(obs / exp, 3) if exp else None,
            "poisson_p_upper": float(f"{float(stats.poisson.sf(obs - 1, exp)):.3g}"),
        }
    tests["same_round_spike_cooccurrence"] = co
    order = np.argsort(np.where(ok, -level, np.inf))
    worst = [
        {
            "qubit": int(qb),
            "median": float(f"{10 ** level[qb]:.4g}"),
            "coords": [float(col[qb]), float(row[qb])],
            "degree": int(deg[qb]),
        }
        for qb in order[:8]
    ]
    q72_nb = sorted(adj[72])
    ranks = stats.rankdata(level[ok])
    rank_of = {int(q): float(r) for q, r in zip(np.flatnonzero(ok), ranks, strict=True)}
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["field"] = g.SX_FIELD
    payload["qubits_with_level"] = int(ok.sum())
    payload["qubits_without_level"] = missing
    payload["degree_counts"] = {str(k): int(np.sum(deg == k)) for k in sorted(set(deg.tolist()))}
    payload["coords_columns_rows"] = {
        "columns": [float(col.min()), float(col.max())],
        "rows": [float(row.min()), float(row.max())],
        "long_row_qubits": int(rows_full.sum()),
        "connector_row_qubits": int((~rows_full).sum()),
        "degree_counts_connector_rows": {
            str(k): int(np.sum(~rows_full & (deg == k))) for k in sorted(set(deg.tolist()))
        },
        "degree_counts_long_rows": {
            str(k): int(np.sum(rows_full & (deg == k))) for k in sorted(set(deg.tolist()))
        },
    }
    payload["tests"] = tests
    payload["tests_run"] = 10
    payload["bonferroni_alpha"] = g.rnd(0.05 / 10, 5)
    payload["worst_qubits"] = worst
    payload["q72_neighbours"] = [
        {
            "qubit": int(nb),
            "median": float(f"{10 ** level[nb]:.4g}") if ok[nb] else None,
            "rank_of_155_low_is_best": rank_of.get(int(nb)),
        }
        for nb in q72_nb
    ]
    ddload.write_json(g.RESULTS / "sx_spatial.json", payload)
    print("wrote", g.RESULTS / "sx_spatial.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
