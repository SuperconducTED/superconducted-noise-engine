"""Device layout (the frame of every spatial analysis) and the fault map across families.

Layout, from ``meta.json``: the configuration ``coords`` (one distinct value in all live
files) and the coupling map (352 directed edges, 176 undirected couplers). Measured: degree
distribution, hop distances, bipartiteness (the 2-colouring), girth (shortest cycle), cycle
rank, coordinate rows, and the coordinate length of every coupler.

Faults: per family, entities ever at the placeholder (``gate_error >= 1``) or, for ``zz``,
exactly 0; share of the lifetime spent there, number of entries (a real value followed by the
placeholder), and dates of entries; absent ``T1``/``T2`` records per qubit; the largest
simultaneous episodes. Clustering: are faulty couplers more often adjacent (sharing a qubit)
than the same number of couplers drawn at random from the 176 (Monte Carlo, 20,000 draws)?

Writes ``results/device/layout_faults.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

N_DRAWS = 20000
MAX_LISTED = 20
SEED = 20261006


def girth(adj: list[list[int]]) -> int:
    best = 10**9
    n = len(adj)
    for s in range(n):
        dist = [-1] * n
        parent = [-1] * n
        dist[s] = 0
        queue = [s]
        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1
            for w in adj[u]:
                if dist[w] < 0:
                    dist[w] = dist[u] + 1
                    parent[w] = u
                    queue.append(w)
                elif parent[u] != w:
                    best = min(best, dist[u] + dist[w] + 1)
    return best


def layout(dd: ddload.DD, adj: list[list[int]], dist: np.ndarray) -> dict[str, Any]:
    coords_store = dd.meta["config_values"]["coords"]
    coords = np.array(next(iter(coords_store.values()))["value"], dtype=float)
    deg = np.array([len(a) for a in adj])
    und = sorted({(min(a, b), max(a, b)) for a, b in dd.meta["coupling_map"]})
    lengths = [float(np.hypot(*(coords[a] - coords[b]))) for a, b in und]
    parity = dist[0] % 2
    bip = all(parity[a] != parity[b] for a, b in und)
    iu = np.triu_indices(len(adj), k=1)
    rows = np.unique(coords[:, 1])
    return {
        "qubits": len(adj),
        "couplers": len(und),
        "directed_edges": len(dd.meta["coupling_map"]),
        "coords_distinct_values": len(coords_store),
        "coupling_map_distinct_values": len(dd.meta["config_values"]["coupling_map"]),
        "degree_counts": {str(k): int(np.sum(deg == k)) for k in np.unique(deg)},
        "degree_by_qubit": deg.tolist(),
        "connected": bool(np.all(dist >= 0)),
        "diameter": int(dist.max()),
        "mean_distance": dc.r6(dist[iu].mean()),
        "distance_q": dc.quantiles(dist[iu]),
        "bipartite": bip,
        "bipartition_sizes": [int(np.sum(parity == 0)), int(np.sum(parity == 1))],
        "degree3_in_class": [int(np.sum((deg == 3) & (parity == c))) for c in (0, 1)],
        "girth": girth(adj),
        "cycle_rank": len(und) - len(adj) + 1,
        "coupler_coordinate_length_q": dc.quantiles(lengths),
        "coord_x_range": [float(coords[:, 0].min()), float(coords[:, 0].max())],
        "coord_rows": [float(r) for r in rows],
        "qubits_per_row": [int(np.sum(coords[:, 1] == r)) for r in rows],
        "degree3_per_row": [int(np.sum((coords[:, 1] == r) & (deg == 3))) for r in rows],
    }


def placeholder_profile(
    dd: ddload.DD, field: str, labels: list[Any], cols: list[int], zero: bool = False
) -> dict[str, Any]:
    v = np.array(dd.v(field))[:, cols]
    present = np.isfinite(v)
    rows = np.flatnonzero(present.any(axis=1))
    life = slice(int(rows[0]), int(rows[-1]) + 1)
    bad = (v == 0.0) if zero else (v >= 1.0)
    bad_l = bad[life]
    pres_l = present[life]
    ents = []
    for k in np.flatnonzero(bad_l.any(axis=0)):
        b = bad_l[:, k]
        real = pres_l[:, k] & ~b
        entries = np.flatnonzero(b[1:] & real[:-1]) + 1 + life.start
        where = np.flatnonzero(b) + life.start
        ents.append(
            {
                "entity": labels[k],
                "share_of_present_files": dc.r6(b.sum() / max(pres_l[:, k].sum(), 1)),
                "entries": int(entries.size),
                "entry_files": [dd.stems[i] for i in entries[:6]],
                "first_bad_file": dd.stems[int(where[0])],
                "last_bad_file": dd.stems[int(where[-1])],
                "always": bool(np.all(b[pres_l[:, k]])),
            }
        )
    per_file = bad_l.sum(axis=1)
    top = np.argsort(per_file)[::-1][:3]
    listed = ents if len(ents) <= MAX_LISTED else ents[:3]
    return {
        "entities_listed": len(listed),
        "lifetime_files": int(bad_l.shape[0]),
        "entities_ever": len(ents),
        "entities_always": [e["entity"] for e in ents if e["always"]],
        "entries_total": int(sum(e["entries"] for e in ents)),
        "entities": listed,
        "per_file_count_q": dc.quantiles(per_file),
        "largest_episodes": [
            {"file": dd.stems[int(i) + life.start], "entities": int(per_file[i])} for i in top
        ],
    }


def adjacency_pairs(edges: list[tuple[int, int]]) -> int:
    n = 0
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            if set(edges[i]) & set(edges[j]):
                n += 1
    return n


def cluster_test(
    name: str, chosen: list[tuple[int, int]], und: list[tuple[int, int]], rng: Any
) -> dict[str, Any]:
    k = len(chosen)
    obs = adjacency_pairs(chosen)
    draws = np.empty(N_DRAWS, dtype=np.int64)
    for d in range(N_DRAWS):
        idx = rng.choice(len(und), size=k, replace=False)
        draws[d] = adjacency_pairs([und[i] for i in idx])
    return {
        "set": name,
        "couplers": ["-".join(map(str, e)) for e in chosen],
        "adjacent_pairs_observed": obs,
        "adjacent_pairs_null_mean": dc.r6(draws.mean()),
        "p_value_at_least_observed": dc.r6((1 + int(np.sum(draws >= obs))) / (1 + N_DRAWS)),
        "draws": N_DRAWS,
    }


def main() -> int:
    dd = ddload.DD()
    adj = dc.adjacency(dd)
    dist = dc.distances(adj)
    lay = layout(dd, adj, dist)
    cols, und = dc.undirected_columns(dd)
    zz_labels = [tuple(int(x) for x in c) for c in dd.meta["couplers"]]
    qubits = list(range(len(adj)))
    und_labels = ["-".join(map(str, e)) for e in und]
    faults = {
        "sx": placeholder_profile(dd, "g1.sx.gate_error", qubits, qubits),
        "measure_2": placeholder_profile(dd, "g1.measure_2.gate_error", qubits, qubits),
        "xslow": placeholder_profile(dd, "g1.xslow.gate_error", qubits, qubits),
        "cz": placeholder_profile(dd, "g2.cz.gate_error", und_labels, cols),
        "rzz": placeholder_profile(dd, "g2.rzz.gate_error", und_labels, cols),
        "zz_zero": placeholder_profile(
            dd,
            "gen.zz",
            ["-".join(map(str, sorted(e))) for e in zz_labels],
            list(range(len(zz_labels))),
            zero=True,
        ),
    }
    missing = {}
    for field in ("q.T1", "q.T2"):
        v = np.array(dd.v(field))
        miss = np.isnan(v).sum(axis=0)
        missing[field] = {
            "qubits_with_absent_records": {str(q): int(m) for q, m in enumerate(miss) if m > 0},
            "absent_records_total": int(miss.sum()),
        }
    rng = np.random.default_rng(SEED)
    perm_cz = [tuple(map(int, e.split("-"))) for e in faults["cz"]["entities_always"]]
    perm_rzz = [tuple(map(int, e.split("-"))) for e in faults["rzz"]["entities_always"]]
    ever = sorted(
        {
            tuple(map(int, e["entity"].split("-")))
            for f in ("cz", "rzz", "zz_zero")
            for e in faults[f]["entities"]
        }
    )
    permanent = sorted(set(perm_cz) | set(perm_rzz))
    clusters = [
        cluster_test("permanently faulty cz or rzz", permanent, und, rng),
        cluster_test("ever placeholder cz, rzz or zz = 0", ever, und, rng),
    ]
    footprint = sorted({q for e in permanent for q in e} | {72})
    sub = dist[np.ix_(footprint, footprint)]
    iu = np.triu_indices(len(footprint), k=1)
    null_means = []
    for _ in range(N_DRAWS // 10):
        pick = rng.choice(len(adj), size=len(footprint), replace=False)
        null_means.append(dist[np.ix_(pick, pick)][iu].mean())
    payload = {
        **dc.header("layout_faults.py"),
        "n_files": dd.n_files,
        "layout": lay,
        "faults": faults,
        "absent_coherence_records": missing,
        "clustering": clusters,
        "permanent_fault_qubit_footprint": footprint,
        "footprint_coords": [
            next(iter(dd.meta["config_values"]["coords"].values()))["value"][q] for q in footprint
        ],
        "footprint_mean_distance": dc.r6(sub[iu].mean()),
        "footprint_mean_distance_null_q": dc.quantiles(null_means),
        "footprint_null_draws": N_DRAWS // 10,
    }
    ddload.write_json(dc.RESULTS / "layout_faults.json", payload)
    print("wrote", dc.RESULTS / "layout_faults.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
