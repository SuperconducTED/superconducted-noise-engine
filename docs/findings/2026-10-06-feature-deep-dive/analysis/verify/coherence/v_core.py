# ruff: noqa: N806, RUF007, B007
"""Independent re-computation of the descriptive numbers of 02-coherence.md.

Written from ddload only (the owner's code is not imported). Recomputes: event and pair counts,
the T2-after-T1 stamp offsets, distribution quantiles, the between-qubit variance share, the
variogram nugget ratio, the lag-1 autocorrelation of log changes, the device-wide round-to-round
median steps, Moran's I of per-qubit median log T1, and an independent Fisher-information
shot-noise floor.

Writes ``results/verify/coherence/core_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import skew

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "coherence" / "core_check.json"
H = 3.6e6
SEED = 20261006


def pooled_lag1(zs):
    a, b = [], []
    for t, z in zs:
        d = np.diff(z)
        if d.size >= 2:
            a.append(d[:-1])
            b.append(d[1:])
    a, b = np.concatenate(a), np.concatenate(b)
    return float(np.corrcoef(a, b)[0, 1]), int(a.size)


def rounds_of(stamps, gap_min=15.0):
    order = np.argsort(stamps, kind="stable")
    s = stamps[order]
    new = np.r_[True, np.diff(s) > gap_min * 60_000.0]
    rid_sorted = np.cumsum(new) - 1
    rid = np.empty(s.size, dtype=np.int64)
    rid[order] = rid_sorted
    return rid


def fisher_sd_log10(a, b, n, kmax, kind):
    x = np.linspace(0, kmax, n) if kind == "lin" else np.geomspace(0.01, kmax, n)
    p = a * np.exp(-x) + b
    # parameters (A, B, T); T = 1 in units of the delay axis
    jac = np.stack([np.exp(-x), np.ones_like(x), a * x * np.exp(-x)], axis=1)
    w = 1.0 / (p * (1 - p))
    info = (jac * w[:, None]).T @ jac / n
    return float(np.sqrt(np.linalg.inv(info)[2, 2]) / np.log(10))


def main():
    dd = ddload.DD()
    out = {
        "header": ddload.result_header("verify/coherence", "analysis/verify/coherence/v_core.py")
    }
    s1 = ddload.series(dd, "q.T1", rule=ddload.MEASURED)
    s2 = ddload.series(dd, "q.T2", rule=ddload.MEASURED)
    out["events"] = {
        "T1": int(sum(s.y.size for s in s1)),
        "T2": int(sum(s.y.size for s in s2)),
        "T1_no_first": int(sum(s.y.size - 1 for s in s1)),
        "T2_no_first": int(sum(s.y.size - 1 for s in s2)),
    }

    # pairing, computed straight from the arrays
    v1, d1 = np.asarray(dd.v("q.T1")), np.asarray(dd.d("q.T1"))
    npair, off_all, outside, no_t1 = 0, [], 0, 0
    for s in s2:
        e, fi = s.entity, s.file_idx
        t1d = d1[fi, e]
        has = np.isfinite(v1[fi, e]) & np.isfinite(t1d)
        no_t1 += int((~has).sum())
        off = (s.t_ms - t1d) / 1000.0
        ok = has & (np.abs(off) <= 3600)
        npair += int(ok.sum())
        outside += int((has & ~ok).sum())
        off_all.append(off[ok])
    off_all = np.concatenate(off_all)
    out["pairing"] = {
        "paired": npair,
        "outside_1h": outside,
        "no_t1_record": no_t1,
        "offset_s_min": float(off_all.min()),
        "offset_s_max": float(off_all.max()),
        "share_within_10s": float(np.mean(np.abs(off_all) <= 10)),
        "all_offsets_positive": bool(np.all(off_all > 0)),
    }

    # distributions
    y1 = np.concatenate([s.y for s in s1])
    y2 = np.concatenate([s.y for s in s2])
    out["quantiles_us"] = {
        "T1": {
            k: float(np.quantile(y1, q)) for k, q in (("p1", 0.01), ("p50", 0.5), ("p99", 0.99))
        },
        "T2": {
            k: float(np.quantile(y2, q)) for k, q in (("p1", 0.01), ("p50", 0.5), ("p99", 0.99))
        },
        "T1_log10_sd": float(np.std(np.log10(y1))),
        "T1_log10_skew": float(skew(np.log10(y1))),
        "T2_log10_sd": float(np.std(np.log10(y2))),
    }

    def between_share(series):
        zs = [np.log10(s.y) for s in series]
        allz = np.concatenate(zs)
        gm = allz.mean()
        between = sum(z.size * (z.mean() - gm) ** 2 for z in zs)
        return float(between / ((allz - gm) ** 2).sum())

    out["between_qubit_variance_share"] = {"T1": between_share(s1), "T2": between_share(s2)}

    # T2 > 2 T1 among pairs
    n_bad, bad_q = 0, set()
    for s in s2:
        e, fi = s.entity, s.file_idx
        t1 = v1[fi, e]
        ok = np.isfinite(t1) & (np.abs(s.t_ms - d1[fi, e]) <= 3.6e6)
        bad = ok & (s.y > 2 * t1)
        n_bad += int(bad.sum())
        if bad.any():
            bad_q.add(int(e))
    out["t2_gt_2t1_paired"] = {"events": n_bad, "qubits": len(bad_q)}

    # variogram nugget and ratio (all events, and without each qubit's first event)
    def vg(series):
        v = ddload.variogram(series)["bins"]
        pick = {(b["lag_h_lo"], b["lag_h_hi"]): b for b in v}
        a, b = pick[(18.0, 30.0)], pick[(744.0, 1488.0)]
        return {
            "sv_18_30": a["semivariance"],
            "pairs_18_30": a["pairs"],
            "sv_744_1488": b["semivariance"],
            "ratio": a["semivariance"] / b["semivariance"],
            "robust_ratio": a["semivariance_robust"] / b["semivariance_robust"],
        }

    out["variogram_T1_all_events"] = vg(s1)
    out["variogram_T2_all_events"] = vg(s2)
    from scripts.feature_patterns import Series

    nf = [Series(entity=s.entity, t_ms=s.t_ms[1:], file_idx=s.file_idx[1:], y=s.y[1:]) for s in s1]
    out["variogram_T1_no_first"] = vg(nf)

    # lag-1 autocorrelation of log changes
    zs = [(s.t_ms, np.log10(s.y)) for s in s1]
    out["lag1_change_acf_T1"] = dict(zip(("r", "n"), pooled_lag1(zs), strict=True))
    zs_nf = [(s.t_ms[1:], np.log10(s.y[1:])) for s in s1]
    out["lag1_change_acf_T1_no_first"] = dict(zip(("r", "n"), pooled_lag1(zs_nf), strict=True))
    split_ms = np.datetime64("2026-05-28T06:00:00", "ms").astype("int64").astype(float)
    late = [(t[t >= split_ms], z[t >= split_ms]) for t, z in zs_nf]
    out["lag1_change_acf_T1_from_2026_05_28"] = dict(
        zip(("r", "n"), pooled_lag1(late), strict=True)
    )

    # device-wide rounds: the median step of log10 T1 between consecutive big rounds
    stamps = np.concatenate([s.t_ms for s in s1])
    ent = np.concatenate([np.full(s.y.size, s.entity) for s in s1])
    z = np.log10(y1)
    rid = rounds_of(stamps)
    nr = rid.max() + 1
    sizes = np.bincount(rid, minlength=nr)
    big = np.flatnonzero(sizes >= 78)
    per_round = {}
    for r in big:
        m = rid == r
        # one value per qubit per round (last wins; rounds are one event per qubit in practice)
        per_round[int(r)] = (ent[m], z[m], float(np.median(stamps[m])))
    steps = []
    for r0, r1 in zip(big[:-1], big[1:], strict=True):
        e0, z0, t0 = per_round[int(r0)]
        e1, z1, t1 = per_round[int(r1)]
        common, i0, i1 = np.intersect1d(e0, e1, return_indices=True)
        steps.append((float(np.median(z1[i1] - z0[i0])), t0, t1, int(common.size)))
    steps.sort(key=lambda r: -abs(r[0]))
    iso = lambda t: str(np.datetime64(int(t), "ms"))  # noqa: E731
    out["big_rounds_T1"] = int(big.size)
    out["largest_median_round_steps_T1"] = [
        {"median_step_log10": s[0], "from": iso(s[1]), "to": iso(s[2]), "qubits": s[3]}
        for s in steps[:4]
    ]

    # Moran's I of per-qubit median log10 T1 on the coupling graph
    nq = len(dd.meta["qubits"])
    med = np.full(nq, np.nan)
    for s in s1:
        med[s.entity] = np.median(np.log10(s.y))
    edges = {tuple(sorted(map(int, e))) for e in dd.meta["coupling_map"]}
    W = np.zeros((nq, nq))
    for a, b in edges:
        W[a, b] = W[b, a] = 1.0
    ok = np.isfinite(med)

    def moran(x):
        d = x - x.mean()
        return float(len(x) / W.sum() * (d @ W @ d) / (d @ d))

    Wo = W[np.ix_(ok, ok)]
    x = med[ok]
    W_full = W
    W = Wo
    obs = moran(x)
    rng = np.random.default_rng(SEED)
    perm = np.array([moran(rng.permutation(x)) for _ in range(4999)])
    p = float((1 + np.sum(np.abs(perm) >= abs(obs))) / (1 + perm.size))
    out["moran_median_log10_T1"] = {"I": obs, "p_two_sided_perm": p, "qubits": int(ok.sum())}
    # rank version, robust to q72's very low value
    from scipy.stats import rankdata

    xr = rankdata(x)
    out["moran_median_log10_T1_ranks"] = {"I": moran(xr)}
    W = W_full

    # Fisher shot-noise floor, own implementation, median readout (p10 0.0137, p01 0.0061)
    p10, p01 = 0.0137, 0.0061
    a, b = 1 - p10 - p01, p01
    floor = {}
    nug = out["variogram_T1_all_events"]["sv_18_30"]
    for name, (n, kmax, kind) in {
        "lin10_3T": (10, 3.0, "lin"),
        "lin40_3T": (40, 3.0, "lin"),
        "lin20_5T": (20, 5.0, "lin"),
        "log40_5T": (40, 5.0, "log"),
    }.items():
        c = fisher_sd_log10(a, b, n, kmax, kind)
        floor[name] = {
            "sd_log10_times_sqrt_shots": c,
            "total_shots_for_floor_eq_nugget": c * c / nug,
            "var_share_at_80000_shots": c * c / 80000.0 / nug,
        }
    out["shot_noise_floor_T1_median_readout"] = floor

    ddload.write_json(OUT, out)
    print("ok")


if __name__ == "__main__":
    main()
