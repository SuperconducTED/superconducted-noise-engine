"""Batches inside a calibration round: how many stamps, how far apart, and who shares one.

A round (``device_common.split_rounds``, 15 min gap) of a daily family carries a handful of
distinct stamps a second or so apart; every entity re-measured in the round carries one of
them. This script calls the set of entities sharing one stamp inside a round a **batch** and
asks:

1. how many batches a round has, how many entities each holds, and how far apart in time;
2. whether entities sharing a batch are spatially separated on the coupling graph (IBM's
   documentation says two-qubit errors are measured in isolation batches), tested against a
   permutation null that shuffles batch labels inside each round with batch sizes kept;
3. whether the partition into batches repeats from round to round (Rand index between the
   partitions of two consecutive rounds, on the entities both share);
4. how ``T1`` and ``T2`` stamps of one qubit relate inside a round;
5. that the two directions of a coupler carry identical values and dates outside
   placeholders (the premise of keeping one direction).

Writes ``results/device/batches.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

N_PERM = 200
SEED = 20261006
MIN_ROUND_ENTITIES = 20
DIST_KS = (0, 1, 2, 3)


def entity_distance(
    fam: dc.Family, ents: np.ndarray, dist: np.ndarray, edges: dict[int, tuple[int, int]]
) -> np.ndarray:
    """Pairwise hop distance between entities: qubits directly, couplers by nearest ends."""
    if not fam.coupler:
        out: np.ndarray = dist[np.ix_(ents, ents)]
        return out
    a = np.array([edges[int(e)][0] for e in ents])
    b = np.array([edges[int(e)][1] for e in ents])
    stack = np.stack(
        [
            dist[np.ix_(a, a)],
            dist[np.ix_(a, b)],
            dist[np.ix_(b, a)],
            dist[np.ix_(b, b)],
        ]
    )
    mins: np.ndarray = stack.min(axis=0)
    return mins


def close_pair_counts(labels: np.ndarray, dmat: np.ndarray) -> np.ndarray:
    """Within-batch pair counts at distance <= k for every k in ``DIST_KS``."""
    same = labels[:, None] == labels[None, :]
    iu = np.triu_indices(labels.size, k=1)
    s = same[iu]
    d = dmat[iu]
    return np.array([int(np.sum(s & (d <= k))) for k in DIST_KS], dtype=np.int64)


def rand_index(p1: dict[int, int], p2: dict[int, int]) -> float | None:
    common = sorted(set(p1) & set(p2))
    if len(common) < MIN_ROUND_ENTITIES:
        return None
    a = np.array([p1[e] for e in common])
    b = np.array([p2[e] for e in common])
    iu = np.triu_indices(a.size, k=1)
    sa = (a[:, None] == a[None, :])[iu]
    sb = (b[:, None] == b[None, :])[iu]
    return float(np.mean(sa == sb))


def sort_key(fam: dc.Family, e: int, edges: dict[int, tuple[int, int]]) -> tuple[int, int]:
    """Order of an entity by index: qubit index, or a coupler's ``(a, b)`` with ``a < b``."""
    return edges[e] if fam.coupler else (e, 0)


def index_ordered(fam: dc.Family, ents: np.ndarray, inv: np.ndarray, edges: Any) -> bool:
    """True when every batch's entities all sort after every earlier batch's (by index)."""
    prev_max: tuple[int, int] | None = None
    for b in range(int(inv.max()) + 1):
        keys = sorted(sort_key(fam, int(e), edges) for e in ents[inv == b])
        if prev_max is not None and keys[0] <= prev_max:
            return False
        prev_max = keys[-1]
    return True


def analyse_family(
    dd: ddload.DD,
    fam: dc.Family,
    dist: np.ndarray,
    edges: dict[int, tuple[int, int]],
    rng: np.random.Generator,
) -> dict[str, Any]:
    ev = dc.family_events(dd, fam)
    labels = dc.split_rounds(ev.t_ms)
    rounds_out = []
    obs_total = np.zeros(len(DIST_KS), dtype=np.int64)
    perm_total = np.zeros((N_PERM, len(DIST_KS)), dtype=np.int64)
    within_min: list[float] = []
    partitions: list[dict[int, int]] = []
    tested_rounds = 0
    ordered_rounds = 0
    parity = dist[0] % 2
    purity: list[float] = []
    odd_pairs = 0
    within_pairs = 0
    for r in np.unique(labels):
        m = labels == r
        t = ev.t_ms[m]
        ents = ev.entity[m]
        stamps, inv = np.unique(t, return_inverse=True)
        n_ent = int(np.unique(ents).size)
        rounds_out.append(
            {
                "batches": int(stamps.size),
                "entities": n_ent,
                "spread_s": float((stamps[-1] - stamps[0]) / 1000.0),
                "batch_sizes": np.bincount(inv).tolist(),
                "spacing_s": (np.diff(stamps) / 1000.0).tolist(),
            }
        )
        if fam.name == "lf":
            continue
        partitions.append({int(e): int(k) for e, k in zip(ents, inv, strict=True)})
        if n_ent < MIN_ROUND_ENTITIES or stamps.size < 2 or ents.size != n_ent:
            continue
        tested_rounds += 1
        ordered_rounds += int(index_ordered(fam, ents, inv, edges))
        dmat = entity_distance(fam, ents, dist, edges)
        obs_total += close_pair_counts(inv, dmat)
        for b in range(stamps.size):
            idx = np.flatnonzero(inv == b)
            if idx.size >= 2:
                sub = dmat[np.ix_(idx, idx)]
                tri = sub[np.triu_indices(idx.size, k=1)]
                within_min.append(float(tri.min()))
                within_pairs += int(tri.size)
                odd_pairs += int(np.sum(tri % 2 == 1))
                if not fam.coupler:
                    cls = parity[ents[idx]]
                    purity.append(float(max(cls.mean(), 1.0 - cls.mean())))
        for p in range(N_PERM):
            perm_total[p] += close_pair_counts(rng.permutation(inv), dmat)
    batches = np.array([r["batches"] for r in rounds_out], dtype=float)
    sizes = np.concatenate([np.array(r["batch_sizes"], dtype=float) for r in rounds_out])
    spread = np.array([r["spread_s"] for r in rounds_out], dtype=float)
    spacing = np.concatenate([np.array(r["spacing_s"], dtype=float) for r in rounds_out])
    ents_per_round = np.array([r["entities"] for r in rounds_out], dtype=float)
    out: dict[str, Any] = {
        "field": fam.field,
        "entities": ev.n_entities,
        "events": int(ev.t_ms.size),
        "events_dropped_carried_in": ev.dropped_carried_in,
        "rounds": len(rounds_out),
        "batches_per_round_q": dc.quantiles(batches),
        "entities_per_batch_q": dc.quantiles(sizes),
        "round_spread_s_q": dc.quantiles(spread),
        "batch_spacing_s_q": dc.quantiles(spacing),
        "entities_per_round_q": dc.quantiles(ents_per_round),
        "rounds_covering_at_least_half": int(np.sum(ents_per_round >= 0.5 * ev.n_entities)),
    }
    if fam.name == "lf":
        return out
    rands = [
        x
        for x in (rand_index(partitions[k], partitions[k + 1]) for k in range(len(partitions) - 1))
        if x is not None
    ]
    null_mean = perm_total.mean(axis=0)
    p_fewer = [(1 + int(np.sum(perm_total[:, j] <= obs_total[j]))) / (1 + N_PERM) for j in range(4)]
    out["spatial_test"] = {
        "rounds_tested": tested_rounds,
        "rule": "rounds with >= 20 distinct entities, >= 2 batches, one event per entity",
        "distance": "hop distance; couplers by the nearest pair of endpoints (0 = share a qubit)",
        "within_batch_pairs_at_distance_le_k": {
            str(k): int(obs_total[j]) for j, k in enumerate(DIST_KS)
        },
        "null_mean_within_batch_pairs_le_k": {
            str(k): dc.r6(null_mean[j]) for j, k in enumerate(DIST_KS)
        },
        "p_value_fewer_close_pairs_than_null": {
            str(k): dc.r6(p_fewer[j]) for j, k in enumerate(DIST_KS)
        },
        "permutations": N_PERM,
        "within_batch_min_distance_counts": {
            str(int(k)): int(c)
            for k, c in zip(*np.unique(within_min, return_counts=True), strict=True)
        },
        "within_batch_pairs": within_pairs,
        "within_batch_pairs_at_odd_distance": odd_pairs,
        "rounds_whose_batches_follow_index_order": ordered_rounds,
        "batch_bipartition_purity_q": dc.quantiles(purity) if purity else None,
        "purity_note": "share of a batch's qubits in its majority class of the graph's 2-colouring",
    }
    out["partition_repeat"] = {
        "consecutive_round_pairs": len(rands),
        "rand_index_q": dc.quantiles(rands),
        "share_identical_partition": dc.r6(np.mean(np.array(rands) == 1.0)) if rands else None,
    }
    return out


def t1_t2_stamps(dd: ddload.DD) -> dict[str, Any]:
    """Offset of each qubit's T2 stamp from its T1 stamp, for events in the same round."""
    e1 = dc.family_events(dd, dc.FAMILIES[3])
    e2 = dc.family_events(dd, dc.FAMILIES[4])
    allt = np.concatenate([e1.t_ms, e2.t_ms])
    lab = dc.split_rounds(allt)
    l1, l2 = lab[: e1.t_ms.size], lab[e1.t_ms.size :]
    t2_by = {(int(r), int(q)): t for r, q, t in zip(l2, e2.entity, e2.t_ms, strict=True)}
    offs = []
    for r, q, t in zip(l1, e1.entity, e1.t_ms, strict=True):
        hit = t2_by.get((int(r), int(q)))
        if hit is not None:
            offs.append((hit - t) / 1000.0)
    o = np.array(offs)
    return {
        "t1_events": int(e1.t_ms.size),
        "t2_events": int(e2.t_ms.size),
        "pairs_same_round_same_qubit": int(o.size),
        "t2_minus_t1_s_q": dc.quantiles(o),
        "share_equal_stamp": dc.r6(np.mean(o == 0.0)),
        "share_t2_later": dc.r6(np.mean(o > 0.0)),
        "share_t2_earlier": dc.r6(np.mean(o < 0.0)),
        "distinct_t1_stamps": int(np.unique(e1.t_ms).size),
        "distinct_t2_stamps": int(np.unique(e2.t_ms).size),
        "stamps_shared_by_t1_and_t2": int(np.intersect1d(e1.t_ms, e2.t_ms).size),
    }


def direction_check(dd: ddload.DD) -> dict[str, Any]:
    col = {(int(a), int(b)): k for k, (a, b) in enumerate(dd.meta["directed_edges"])}
    pairs = [(k, col[(b, a)]) for (a, b), k in col.items() if a < b]
    out: dict[str, Any] = {}
    for field in ("g2.cz.gate_error", "g2.rzz.gate_error"):
        v = np.array(dd.v(field))
        d = np.array(dd.d(field))
        ka = [p[0] for p in pairs]
        kb = [p[1] for p in pairs]
        va, vb, da, db = v[:, ka], v[:, kb], d[:, ka], d[:, kb]
        real = (va < 1.0) & (vb < 1.0)
        ph = (va >= 1.0) & (vb >= 1.0)
        out[field] = {
            "undirected_couplers": len(pairs),
            "records_both_real": int(real.sum()),
            "real_value_mismatch": int(np.sum(real & (va != vb))),
            "real_date_mismatch": int(np.sum(real & (da != db))),
            "records_both_placeholder": int(ph.sum()),
            "placeholder_date_mismatch": int(np.sum(ph & (da != db))),
            "records_one_real_one_placeholder": int(np.sum((va < 1.0) != (vb < 1.0))),
        }
    return out


def main() -> int:
    dd = ddload.DD()
    adj = dc.adjacency(dd)
    dist = dc.distances(adj)
    cols, edge_list = dc.undirected_columns(dd)
    edges = dict(zip(cols, edge_list, strict=True))
    rng = np.random.default_rng(SEED)
    fams = {f.name: analyse_family(dd, f, dist, edges, rng) for f in dc.FAMILIES}
    payload = {
        **dc.header("batches.py"),
        "n_files": dd.n_files,
        "round_gap_min": dc.ROUND_GAP_MIN,
        "seed": SEED,
        "families": fams,
        "t1_t2": t1_t2_stamps(dd),
        "direction_check": direction_check(dd),
    }
    ddload.write_json(dc.RESULTS / "batches.json", payload)
    print("wrote", dc.RESULTS / "batches.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
