"""Verifier: permanent faults, adjacency null, and footprint null drawn from couplers."""

import sys
from collections import deque
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v4_faults.json"


def main() -> None:
    dd = ddload.DD()
    edges_dir = [tuple(int(x) for x in e) for e in dd.meta["directed_edges"]]
    und = sorted({tuple(sorted(e)) for e in edges_dir})
    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v4_faults.py")
    }
    perm = set()
    ever = set()
    for fld in ("g2.cz.gate_error", "g2.rzz.gate_error"):
        v = np.array(dd.v(fld))
        for k, (a, b) in enumerate(edges_dir):
            if a < b:
                col = v[:, k]
                if np.all(col >= 1.0):
                    perm.add((a, b))
                if np.any(col >= 1.0):
                    ever.add((a, b))
    zz = np.array(dd.v("gen.zz"))
    couplers = dd.meta["couplers"]
    res["permanent_couplers"] = sorted(perm)
    res["ever_placeholder_couplers_count"] = len(ever)
    # adjacency
    deg = {}
    for a, b in und:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    shared_pairs = sum(comb(d, 2) for d in deg.values())
    p_adj = shared_pairs / comb(len(und), 2)
    res["coupler_pairs_sharing_a_qubit"] = shared_pairs
    res["exact_null_mean_adjacent_pairs_6"] = comb(6, 2) * p_adj
    res["exact_null_mean_adjacent_pairs_16"] = comb(16, 2) * p_adj

    def adj_pairs(es):
        return sum(1 for e, f in combinations(es, 2) if set(e) & set(f))

    res["observed_adjacent_pairs_perm"] = adj_pairs(sorted(perm))
    rng = np.random.default_rng(7)
    draws = np.array(
        [adj_pairs([und[i] for i in rng.choice(len(und), 6, replace=False)]) for _ in range(20000)]
    )
    res["mc_p_adjacent_ge_obs"] = float(np.mean(draws >= res["observed_adjacent_pairs_perm"]))
    # distances
    nq = len(dd.meta["qubits"])
    adj = [[] for _ in range(nq)]
    for a, b in und:
        adj[a].append(b)
        adj[b].append(a)
    dist = np.full((nq, nq), -1)
    for s in range(nq):
        dist[s, s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for w in adj[u]:
                if dist[s, w] < 0:
                    dist[s, w] = dist[s, u] + 1
                    q.append(w)

    def foot_mean(es):
        qs = sorted({x for e in es for x in e})
        sub = dist[np.ix_(qs, qs)]
        iu = np.triu_indices(len(qs), k=1)
        return float(sub[iu].mean()), len(qs)

    obs, nfoot = foot_mean(sorted(perm))
    res["footprint_mean_hop_couplers_only"] = obs
    res["footprint_qubits_from_couplers"] = nfoot
    # null A: random qubits of the same count (the document's null)
    null_a = []
    for _ in range(2000):
        pick = rng.choice(nq, nfoot, replace=False)
        sub = dist[np.ix_(pick, pick)]
        null_a.append(sub[np.triu_indices(nfoot, k=1)].mean())
    res["null_a_random_qubits"] = {
        "median": float(np.median(null_a)),
        "min": float(np.min(null_a)),
        "p_le_obs": float(np.mean(np.array(null_a) <= obs)),
    }
    # null B: 6 random couplers, footprint of the endpoints (right unit of randomisation)
    null_b = []
    for _ in range(20000):
        es = [und[i] for i in rng.choice(len(und), 6, replace=False)]
        null_b.append(foot_mean(es)[0])
    null_b = np.array(null_b)
    res["null_b_random_couplers"] = {
        "median": float(np.median(null_b)),
        "q05": float(np.quantile(null_b, 0.05)),
        "min": float(null_b.min()),
        "p_le_obs": float((np.sum(null_b <= obs) + 1) / (null_b.size + 1)),
    }
    # null C: same but conditioning on 2 adjacent pairs present (the observed structure) is hard;
    # instead report p for draws with exactly the observed adjacent-pair count
    null_c = []
    for _ in range(60000):
        es = [und[i] for i in rng.choice(len(und), 6, replace=False)]
        if adj_pairs(es) >= 2:
            null_c.append(foot_mean(es)[0])
    null_c = np.array(null_c)
    res["null_c_random_couplers_with_ge2_adjacent"] = {
        "n": int(null_c.size),
        "median": float(np.median(null_c)),
        "p_le_obs": float((np.sum(null_c <= obs) + 1) / (null_c.size + 1)),
    }
    del zz, couplers
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
