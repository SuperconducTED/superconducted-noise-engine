# ruff: noqa: RUF007
"""Independent check of the matched sub-day test of 02-coherence.md (section 4.1).

Written from ddload only. Finds every pair of consecutive device-wide rounds (>= 78 qubits,
15-minute clustering) of log10 T1 that is less than 18 h apart, and compares the semivariance of
the qubits' changes with that of the nearest preceding and following round pairs 18 to 30 h
apart (classical, and a robust 4th-root estimate). Reports how many distinct occasions exist at
each lag, how many fall after 2026-05-30, and the median ratio overall and after 2026-05-30.

Writes ``results/verify/coherence/subday_check.json``.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "coherence" / "subday_check.json"
H = 3.6e6
CUT_0530 = np.datetime64("2026-05-30T00:00:00", "ms").astype("int64").astype(float)


def robust(d):
    a = np.abs(d)
    n = a.size
    return float((np.mean(np.sqrt(a)) ** 4) / (2 * (0.457 + 0.494 / n)))


def main():
    dd = ddload.DD()
    s1 = ddload.series(dd, "q.T1", rule=ddload.MEASURED)
    stamps = np.concatenate([s.t_ms for s in s1])
    ent = np.concatenate([np.full(s.y.size, s.entity) for s in s1])
    z = np.log10(np.concatenate([s.y for s in s1]))
    order = np.argsort(stamps, kind="stable")
    ss = stamps[order]
    new = np.r_[True, np.diff(ss) > 15 * 60_000.0]
    rid = np.empty(ss.size, dtype=int)
    rid[order] = np.cumsum(new) - 1
    sizes = np.bincount(rid)
    big = [int(r) for r in np.flatnonzero(sizes >= 78)]
    rd = {}
    for r in big:
        m = rid == r
        rd[r] = (ent[m], z[m], float(np.median(stamps[m])))

    def change(r0, r1):
        e0, z0, _ = rd[r0]
        e1, z1, _ = rd[r1]
        _, i0, i1 = np.intersect1d(e0, e1, return_indices=True)
        return z1[i1] - z0[i0]

    gaps = [
        (rd[a][2], (rd[b][2] - rd[a][2]) / H, a, b) for a, b in zip(big[:-1], big[1:], strict=True)
    ]
    occ = []
    for k, (t0, gap, a, b) in enumerate(gaps):
        if gap >= 18:
            continue
        d = change(a, b)
        near = []
        for kk in (k - 1, k + 1, k - 2, k + 2, k - 3, k + 3):
            if 0 <= kk < len(gaps) and 18 <= gaps[kk][1] <= 30:
                near.append(change(gaps[kk][2], gaps[kk][3]))
            if len(near) >= 2:
                break
        if not near:
            continue
        dn = np.concatenate(near)
        occ.append(
            {
                "first_round": str(np.datetime64(int(t0), "ms")),
                "gap_h": gap,
                "qubits": int(d.size),
                "robust_sv": robust(d),
                "classical_sv": float(0.5 * np.mean(d * d)),
                "neighbour_day_robust_sv": robust(dn),
                "neighbour_day_classical_sv": float(0.5 * np.mean(dn * dn)),
                "ratio_robust": robust(d) / robust(dn),
                "after_2026_05_30": bool(t0 >= CUT_0530),
            }
        )
    ratios = np.array([o["ratio_robust"] for o in occ])
    late = np.array([o["ratio_robust"] for o in occ if o["after_2026_05_30"]])
    out = {
        "header": ddload.result_header("verify/coherence", "analysis/verify/coherence/v_subday.py"),
        "occasions": occ,
        "n_occasions": len(occ),
        "n_occasions_below_6h": int(sum(o["gap_h"] < 6 for o in occ)),
        "n_occasions_below_9h": int(sum(o["gap_h"] < 9 for o in occ)),
        "n_after_0530": int(late.size),
        "median_ratio_all": float(np.median(ratios)),
        "median_ratio_after_0530": float(np.median(late)),
        "ratios_after_0530": [float(x) for x in late],
    }
    ddload.write_json(OUT, out)
    print("ok")


if __name__ == "__main__":
    main()
