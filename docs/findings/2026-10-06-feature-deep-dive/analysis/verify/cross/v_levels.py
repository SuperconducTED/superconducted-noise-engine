"""Independent re-computation of the between-qubit numbers of 07-cross-feature-dependency.md.

Written from ddload only (the owner's code is not imported). Recomputes: event counts and
series counts per family, the T1-T2 same-stamp gap, the 23 level pairs (Spearman, permutation
p, Benjamini-Hochberg q), and the two leading eigenvalues of the 10-field normal-score
correlation matrix (set A), plus a parallel-analysis threshold.

Writes ``results/verify/cross/levels_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, rankdata, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "cross" / "levels_check.json"
OFFSET = 1.0 / 8192.0
RNG = np.random.default_rng(7)

QFIELDS = {
    "T1": "q.T1",
    "T2": "q.T2",
    "RO": "q.readout_error",
    "p01": "q.prob_meas1_prep0",
    "p10": "q.prob_meas0_prep1",
    "init": "q.init_error",
    "m2": "g1.measure_2.gate_error",
    "sx": "g1.sx.gate_error",
}
GATE_MASK = {"m2", "sx"}


def events(dd, field, mask, log_offset=False):
    out = ddload.series(dd, field, rule=ddload.MEASURED, mask=mask)
    res = {}
    for s in out:
        y = np.asarray(s.y, float)
        t = np.asarray(s.t_ms, float)
        if log_offset:
            z = np.log10(y + OFFSET)
        else:
            keep = y > 0
            y, t = y[keep], t[keep]
            z = np.log10(y)
        if z.size:
            res[int(s.entity)] = (t, z)
    return res


def bh(p):
    p = np.asarray(p)
    n = p.size
    o = np.argsort(p)
    q = np.empty(n)
    run = 1.0
    for rank in range(n, 0, -1):
        i = o[rank - 1]
        run = min(run, p[i] * n / rank)
        q[i] = run
    return q


def main():
    dd = ddload.DD()
    fams = {}
    info = {}
    for k, f in QFIELDS.items():
        mask = ddload.placeholder_error if k in GATE_MASK else None
        fams[k] = events(dd, f, mask, log_offset=k in ("p01", "p10"))
        n_ev = sum(v[1].size for v in fams[k].values())
        info[k] = {"series": len(fams[k]), "events": int(n_ev)}
        info[k]["events_per_series_median"] = float(
            np.median([v[1].size for v in fams[k].values()])
        )

    # same-stamp T1/T2 gap on one qubit
    gaps = []
    for q, (t1, _) in fams["T1"].items():
        if q in fams["T2"]:
            t2 = fams["T2"][q][0]
            i = np.clip(np.searchsorted(t2, t1), 1, t2.size - 1)
            d = np.minimum(np.abs(t2[i] - t1), np.abs(t2[i - 1] - t1)) / 3.6e6
            gaps.append(d)
    g = np.concatenate(gaps)
    info["T1_T2_gap"] = {
        "n": int(g.size),
        "median_h": float(np.median(g)),
        "within_0.25h": float(np.mean(g <= 0.25)),
    }

    # coupler families
    couplers = {}
    for fam, field, rule, mask in (
        ("cz", "g2.cz.gate_error", ddload.MEASURED, ddload.placeholder_error),
        ("rzz", "g2.rzz.gate_error", ddload.MEASURED, ddload.placeholder_error),
        ("zz", "gen.zz", ddload.ASSEMBLY, ddload.zero_value),
    ):
        ents = dd.entities(field)
        ser = ddload.series(dd, field, rule=rule, mask=mask)
        lev = {}
        nev = 0
        for s in ser:
            a, b = ents[int(s.entity)]
            if fam != "zz" and a > b:
                continue
            y = np.abs(np.asarray(s.y, float))
            y = y[y > 0]
            if y.size == 0:
                continue
            nev += y.size
            lev[(int(a), int(b))] = float(np.median(np.log10(y)))
        couplers[fam] = lev
        info[fam] = {"series": len(lev), "events": int(nev)}

    levels = {k: {q: float(np.median(v[1])) for q, v in fams[k].items()} for k in fams}
    for fam in ("cz", "rzz", "zz"):
        adj = {}
        for (a, b), lv in couplers[fam].items():
            for q in (a, b):
                adj.setdefault(q, []).append(lv)
        levels["adj_" + fam] = {q: float(np.mean(v)) for q, v in adj.items()}

    pairs = [
        ("T1", "init"),
        ("T1", "adj_zz"),
        ("T2", "RO"),
        ("T2", "p01"),
        ("T2", "p10"),
        ("T2", "init"),
        ("T2", "m2"),
        ("T2", "adj_zz"),
        ("sx", "RO"),
        ("RO", "adj_zz"),
        ("sx", "p01"),
        ("p01", "adj_zz"),
        ("sx", "p10"),
        ("p10", "adj_zz"),
        ("init", "sx"),
        ("init", "adj_cz"),
        ("init", "adj_rzz"),
        ("init", "adj_zz"),
        ("m2", "sx"),
        ("m2", "adj_cz"),
        ("m2", "adj_rzz"),
        ("m2", "adj_zz"),
        ("sx", "adj_zz"),
    ]
    rows = []
    for a, b in pairs:
        common = sorted(set(levels[a]) & set(levels[b]))
        x = np.array([levels[a][q] for q in common])
        y = np.array([levels[b][q] for q in common])
        r = float(spearmanr(x, y)[0])
        rx = rankdata(x)
        ry = rankdata(y)
        cnt = 0
        nperm = 4000
        for _ in range(nperm):
            rr = np.corrcoef(rx, RNG.permutation(ry))[0, 1]
            cnt += abs(rr) >= abs(r) - 1e-12
        rows.append(
            {"a": a, "b": b, "n": len(common), "rho": round(r, 3), "p": (cnt + 1) / (nperm + 1)}
        )
    q = bh([r["p"] for r in rows])
    for r, qq in zip(rows, q, strict=True):
        r["q"] = round(float(qq), 3)
    summary = {
        "n_pairs": len(rows),
        "n_bh_survivors_0.05": int(np.sum(q < 0.05)),
        "min_q": round(float(q.min()), 3),
        "min_rho": min(r["rho"] for r in rows),
        "max_rho": max(r["rho"] for r in rows),
    }

    # PCA set A
    fa = ["T1", "T2", "RO", "p01", "p10", "m2", "sx", "adj_cz", "adj_rzz", "adj_zz"]
    qs = sorted(set.intersection(*[set(levels[f]) for f in fa]))
    xm = np.array([[levels[f][q] for f in fa] for q in qs])
    ns = np.column_stack(
        [norm.ppf(rankdata(xm[:, j]) / (xm.shape[0] + 1.0)) for j in range(xm.shape[1])]
    )
    ev = np.linalg.eigvalsh(np.corrcoef(ns, rowvar=False))[::-1]
    nulls = []
    for _ in range(1000):
        xp = np.column_stack([RNG.permutation(ns[:, j]) for j in range(ns.shape[1])])
        nulls.append(np.linalg.eigvalsh(np.corrcoef(xp, rowvar=False))[::-1])
    nulls = np.array(nulls)
    pca = {
        "n_qubits": len(qs),
        "eigenvalues_top4": [round(float(e), 3) for e in ev[:4]],
        "shares_top2": [round(float(e / ev.sum()), 3) for e in ev[:2]],
        "parallel_95_top3": [round(float(np.percentile(nulls[:, k], 95)), 3) for k in range(3)],
    }
    payload = ddload.result_header("verify/cross", "analysis/verify/cross/v_levels.py")
    payload.update(
        {"family_counts": info, "level_pairs": rows, "level_summary": summary, "pca_set_A": pca}
    )
    ddload.write_json(OUT, payload)
    print(info)
    print(summary)
    print(pca)


if __name__ == "__main__":
    main()
