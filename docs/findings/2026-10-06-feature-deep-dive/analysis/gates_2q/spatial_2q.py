"""Spatial structure of cz, rzz and zz on the coupling graph.

Writes ``results/gates_2q/spatial.json``. Loads ``g2.cz.gate_error``, ``g2.rzz.gate_error``,
``gen.zz``, the configuration coordinates and the coupling map from ``meta.json``.

Per-coupler level: the median over events of log10 error (measured rule, placeholders
masked) and the median over files of log10 |zz|. Tests:

- orientation: a coupler is "horizontal" when both qubits share the second coordinate (a
  long row of the heavy-hex lattice) and a "bridge" otherwise; Mann-Whitney U;
- position: Spearman against the distance of the coupler midpoint from the lattice centre,
  against the row and against the column; degree: Spearman against the sum of the two
  qubits' degrees (the number of spectator couplings);
- Moran's I on the line graph (couplers adjacent when they share a qubit), with a
  permutation p-value (9,999 shuffles), on log levels and on ranks;
- the non-persistent component in space: each event's deviation from the median of its
  3 + 3 neighbouring events, matched by round, correlated between couplers that share a qubit
  and between couplers at least 4 hops apart (round medians removed first);
- batches: couplers carrying the identical stamp within a round, and the smallest qubit
  distance between any two couplers of one batch (IBM's documentation describes 2Q
  benchmarking in batches separated by at least two qubits).
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/spatial_2q.py"
RNG = np.random.default_rng(20261006)


def hop_matrix(n: int, edges: list[tuple[int, int]]) -> np.ndarray:
    adj: dict[int, list[int]] = collections.defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    dist = np.full((n, n), -1, dtype=np.int64)
    for s in range(n):
        dist[s, s] = 0
        frontier = [s]
        while frontier:
            nxt = []
            for u in frontier:
                for v in adj[u]:
                    if dist[s, v] < 0:
                        dist[s, v] = dist[s, u] + 1
                        nxt.append(v)
            frontier = nxt
    return dist


def morans_i(x: np.ndarray, w: np.ndarray, n_perm: int = 9999) -> dict[str, Any]:
    ok = np.isfinite(x)
    x = x[ok]
    w = w[np.ix_(ok, ok)]
    n = x.size
    z = x - x.mean()
    s0 = w.sum()

    def stat(v: np.ndarray) -> float:
        return float((n / s0) * (v @ w @ v) / (v @ v))

    obs = stat(z)
    null = np.array([stat(RNG.permutation(z)) for _ in range(n_perm)])
    p = (np.sum(null >= obs) + 1) / (n_perm + 1)
    return {
        "n": int(n),
        "I": c.rnd(obs),
        "expected_under_null": c.rnd(-1.0 / (n - 1)),
        "null_q_2p5_50_97p5": c.q(null, (0.025, 0.5, 0.975)),
        "p_one_sided": c.rnd(float(p), 3),
    }


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    lab = [c.label(p) for p in pairs]
    coords_entry = next(iter(dd.meta["config_values"]["coords"].values()))
    coords = np.array(coords_entry["value"], dtype=np.float64)  # qubit -> [x, y]
    nq = coords.shape[0]
    hop = hop_matrix(nq, pairs)
    deg = np.bincount(np.array(pairs).ravel(), minlength=nq)
    a = np.array([p[0] for p in pairs])
    b = np.array([p[1] for p in pairs])
    horizontal = coords[a, 1] == coords[b, 1]
    mid = (coords[a] + coords[b]) / 2.0
    centre = (coords.min(axis=0) + coords.max(axis=0)) / 2.0
    dist_c = np.sqrt(((mid - centre) ** 2).sum(axis=1))
    degsum = deg[a] + deg[b]
    n_c = len(pairs)
    # coupler-to-coupler distance: smallest qubit hop distance between their endpoints
    cdist = np.minimum.reduce(
        [hop[np.ix_(a, a)], hop[np.ix_(a, b)], hop[np.ix_(b, a)], hop[np.ix_(b, b)]]
    )
    w = (cdist == 0).astype(np.float64)
    np.fill_diagonal(w, 0.0)

    levels: dict[str, np.ndarray] = {}
    series_by_gate: dict[str, dict[int, Any]] = {}
    for gate in c.GATES:
        ser = c.gate_series(dd, gate, fwd)
        series_by_gate[gate] = ser
        levels[gate] = np.array(
            [np.median(np.log10(ser[col].y)) if col in ser else np.nan for col in fwd]
        )
    gcol = c.gen_columns(dd, pairs)
    zz = np.abs(np.array(dd.v("gen.zz"))[:, gcol])
    with np.errstate(divide="ignore"):
        lzz = np.log10(np.median(zz, axis=0))
    lzz[~np.isfinite(lzz)] = np.nan
    levels["abs_zz"] = lzz

    out: dict[str, Any] = {
        "n_files": dd.n_files,
        "couplers": n_c,
        "horizontal_couplers": int(horizontal.sum()),
        "bridge_couplers": int((~horizontal).sum()),
        "qubit_degree_counts": {str(k): int(v) for k, v in collections.Counter(deg).items()},
        "line_graph_edges": int(w.sum() / 2),
    }
    for name, x in levels.items():
        ok = np.isfinite(x)
        h, v = x[ok & horizontal], x[ok & ~horizontal]
        mw = stats.mannwhitneyu(h, v)
        ranks = np.full(x.shape, np.nan)
        ranks[ok] = stats.rankdata(x[ok])
        res: dict[str, Any] = {
            "couplers": int(ok.sum()),
            "horizontal_median": c.rnd(float(10 ** np.median(h))),
            "bridge_median": c.rnd(float(10 ** np.median(v))),
            "bridge_over_horizontal": c.rnd(float(10 ** (np.median(v) - np.median(h)))),
            "mannwhitney_p": c.rnd(float(mw.pvalue), 3),
            "spearman_vs_distance_from_centre": c.spearman(x, dist_c),
            "spearman_vs_row_y": c.spearman(x, mid[:, 1]),
            "spearman_vs_column_x": c.spearman(x, mid[:, 0]),
            "spearman_vs_degree_sum": c.spearman(x, degsum),
            "morans_i_log": morans_i(x, w),
            "morans_i_rank": morans_i(ranks, w),
        }
        out[name] = res

    # Faulty couplers and their positions.
    faulty: dict[str, Any] = {}
    for gate in c.GATES:
        v = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
        share = np.mean(v >= 1.0, axis=0)
        faulty[gate] = [
            {
                "coupler": lab[i],
                "placeholder_share": c.rnd(float(share[i])),
                "midpoint": [float(mid[i, 0]), float(mid[i, 1])],
                "orientation": "horizontal" if horizontal[i] else "bridge",
            }
            for i in np.flatnonzero(share > 0)
        ]
    out["faulty_positions"] = faulty

    # Non-persistent component in space.
    far = cdist >= 4
    for gate in c.GATES:
        ser = series_by_gate[gate]
        stamps = np.concatenate([s.t_ms for s in ser.values()])
        rd = c.rounds(stamps)
        starts = np.array([r[0] for r in rd])
        dev = np.full((len(rd), n_c), np.nan)
        pos = {col: i for i, col in enumerate(fwd)}
        for col, s in ser.items():
            if s.y.size < 8:
                continue
            d = c.moving_median_deviation(np.log10(s.y))
            rid = np.searchsorted(starts, s.t_ms, side="right") - 1
            dev[rid, pos[col]] = d
        dev = dev - np.nanmedian(dev, axis=1, keepdims=True)
        iu, ju = np.triu_indices(n_c, k=1)
        res: dict[str, Any] = {}
        for nm, sel in (("share_a_qubit", cdist[iu, ju] == 0), ("four_or_more_hops", far[iu, ju])):
            ii, jj = iu[sel], ju[sel]
            x = dev[:, ii].ravel()
            y = dev[:, jj].ravel()
            res[nm] = {"pairs_of_couplers": int(ii.size), **c.spearman(x, y)}
        # How broad is the shared-qubit correlation? One Spearman per coupler pair (pairs
        # with at least 30 common rounds), and the pooled value without the couplers whose
        # level is above the 90th percentile of coupler levels.
        sel = cdist[iu, ju] == 0
        per_pair = []
        for i, j in zip(iu[sel], ju[sel], strict=True):
            ok = np.isfinite(dev[:, i]) & np.isfinite(dev[:, j])
            if ok.sum() >= 30:
                per_pair.append(c.spearman(dev[ok, i], dev[ok, j])["rho"])
        pp = np.array([r for r in per_pair if r is not None])
        lvl = levels[gate]
        cut = np.nanquantile(lvl, 0.9)
        good = np.isfinite(lvl) & (lvl <= cut)
        sel_g = sel & good[iu] & good[ju]
        res["share_a_qubit_per_pair"] = {
            "pairs": int(pp.size),
            "rho_q": c.q(pp),
            "share_positive": c.rnd(float(np.mean(pp > 0))),
        }
        res["share_a_qubit_without_top_decile_couplers"] = {
            "pairs_of_couplers": int(sel_g.sum()),
            **c.spearman(dev[:, iu[sel_g]].ravel(), dev[:, ju[sel_g]].ravel()),
        }
        out[f"{gate}_deviation_correlation_in_space"] = res

    # Batches: identical stamps within a cz or rzz round.
    for gate in c.GATES:
        ser = series_by_gate[gate]
        by_stamp: dict[float, list[int]] = collections.defaultdict(list)
        pos = {col: i for i, col in enumerate(fwd)}
        for col, s in ser.items():
            for t in s.t_ms[1:]:
                by_stamp[float(t)].append(pos[col])
        sizes = []
        min_sep = []
        for members in by_stamp.values():
            if len(members) < 2:
                continue
            m = np.array(members)
            sub = cdist[np.ix_(m, m)].astype(np.float64)
            np.fill_diagonal(sub, np.inf)
            sizes.append(len(members))
            min_sep.append(float(sub.min()))
        ms = np.array(min_sep)
        out[f"{gate}_batches"] = {
            "stamps_with_ge_2_couplers": len(sizes),
            "couplers_per_stamp_q": c.q(sizes),
            "min_qubit_distance_within_stamp_q": c.q(ms),
            "share_stamps_min_distance_ge_2": c.rnd(float(np.mean(ms >= 2))),
            "share_stamps_min_distance_eq_0": c.rnd(float(np.mean(ms == 0))),
            "distance_note": "0 = the two couplers share a qubit; 1 = adjacent qubits",
        }

    path = c.write("spatial.json", SCRIPT, out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
