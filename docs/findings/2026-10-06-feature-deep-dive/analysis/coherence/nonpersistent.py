"""The non-persistent component of log T1, log T2 and log pure-dephasing rate.

Writes ``results/coherence/nonpersistent.json``. Six blocks:

1. ``variograms``: ``ddload.variogram`` (classical and robust) of log10 T1, T2, pure-dephasing
   rate and T2/(2 T1), whole record and in three time windows; the dephasing rate also by
   tertile of the qubit's median T2/(2 T1), because propagated T1/T2 scatter is amplified
   in log Gamma_phi when T2 is close to 2 T1.
2. ``short_lag_audit``: are the shortest-lag pairs device-wide rounds (schedule) or isolated
   re-runs (possible selection after a bad value)?
3. ``t1_t2_comovement``: same-round deviations of log T1 and log T2 from their running
   levels. Independent fit errors of two separate experiments cannot correlate, so, under
   that assumption, rho^2 is a lower bound on the share of each deviation variance that is
   a real (shared) change. The regression slope is compared with T2/(2 T1), the slope that
   propagation of a pure T1 change into T2 predicts.
4. ``heterogeneity``: per-qubit scale and skew of the deviations, a bootstrap null for the
   spread of per-qubit scales, and the scale against the qubit's level.
5. ``shot_noise_floor``: Cramer-Rao floor of an exponential-decay fit with free amplitude
   and offset under binomial shots, for several delay designs, as total shots at which the
   floor would equal the observed short-lag semivariance. IBM's delays and shot counts are
   not published, so the floor is reported as a function of total shots.
6. ``literature_benchmark``: the log-space variance implied by published single-qubit T1
   scatter (Burnett et al. 2019, Fig. 1), for comparison with the nugget.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cohlib
import ddload

RNG_SEED = 20261006
N_BOOT = 300
SHORT_LAG_H = 6.0
SUBDAY_H = 18.0
BIG_ROUND = 78
SMALL_ROUND = 10
TRIM = 0.5
WINDOWS = {
    "before_2026-05-30": (-np.inf, 1780099200000.0),
    "2026-05-30_to_split": (1780099200000.0, cohlib.PERIOD_SPLIT_MS),
    "after_split": (cohlib.PERIOD_SPLIT_MS, np.inf),
}
# Burnett et al. 2019 (arXiv:1901.04417), Fig. 1b legend: Gaussian fits to 2,000
# consecutive T1 values over about 65 h, qubit A mean 46.18 us, sd 10.24 us; qubit B mean
# 70.72 us, sd 14.31 us.
BURNETT = {"qubit_A": (46.18, 10.24), "qubit_B": (70.72, 14.31)}
# Literature inputs, each read in this session from the fetched source:
# Burnett et al. 2019 (arXiv:1901.04417), section II.C: dwell time at one T1 value typically
# 2 to 12.5 h, telegraph switching rates 20 to 140 uHz; section II.D: switching rates across
# thermal cycles 71.4 uHz to 1.9 mHz. Klimov et al. 2018 (arXiv:1809.01043), main text: one T1
# curve is 2,000 repeats at each of 40 log-spaced delays (0.01 to 100 us), about 2 s; T1 can
# vary by up to an order of magnitude, abruptly on 15-minute timescales; average telegraphic
# jump rates about 50 uHz to 5 mHz. Qiskit Experiments manuals (simulated examples): T1
# (5.86 +/- 0.28)e-05 s; T2 Hahn (2.11 +/- 0.16)e-05 s with 2,000 shots at 11 delays.
RATES_UHZ = {
    "burnett_2019_switching": (20.0, 140.0),
    "burnett_2019_across_cooldowns": (71.4, 1900.0),
    "klimov_2018_jump_rates": (50.0, 5000.0),
}
BURNETT_DWELL_H = (2.0, 12.5)
KLIMOV_SHOTS = 2000 * 40
QISKIT_T2HAHN_SHOTS = 2000 * 11
QISKIT_EXAMPLES = {
    "qiskit_t1_example": (5.86e-05, 0.28e-05),
    "qiskit_t2hahn_example": (2.11e-05, 0.16e-05),
}
DESIGNS = {
    "uniform_10_to_3T": (10, "lin", 3.0),
    "uniform_20_to_3T": (20, "lin", 3.0),
    "uniform_40_to_3T": (40, "lin", 3.0),
    "uniform_20_to_5T": (20, "lin", 5.0),
    "log_40_0.01T_to_5T": (40, "log", 5.0),
}


def sub(series: list[Any], lo: float, hi: float) -> list[Any]:
    out = []
    for s in series:
        m = (s.t_ms >= lo) & (s.t_ms < hi)
        if m.sum() >= 2:
            out.append(
                ddload.Series(entity=s.entity, t_ms=s.t_ms[m], file_idx=s.file_idx[m], y=s.y[m])
            )
    return out


def summarise(vg: dict[str, Any]) -> dict[str, Any]:
    bins = vg["bins"]

    def pick(lo: float) -> dict[str, Any] | None:
        for b in bins:
            if b["lag_h_lo"] == lo:
                return {
                    k: b[k]
                    for k in (
                        "pairs",
                        "series",
                        "mean_lag_h",
                        "semivariance",
                        "semivariance_robust",
                    )
                }
        return None

    shortest = next((b for b in bins if b["pairs"] >= 200 and b["series"] >= 10), None)
    day = pick(18.0)
    long1, long2 = pick(744.0), pick(1488.0)
    out: dict[str, Any] = {
        "shortest_bin_with_200_pairs": None
        if shortest is None
        else {
            k: shortest[k]
            for k in (
                "lag_h_lo",
                "lag_h_hi",
                "pairs",
                "series",
                "semivariance",
                "semivariance_robust",
            )
        },
        "bin_18_30h": day,
        "bin_744_1488h": long1,
        "bin_1488_3624h": long2,
    }
    if day and long1 and day["semivariance"] and long1["semivariance"]:
        out["ratio_18_30h_over_744_1488h"] = cohlib.r(day["semivariance"] / long1["semivariance"])
        out["ratio_18_30h_over_744_1488h_robust"] = cohlib.r(
            day["semivariance_robust"] / long1["semivariance_robust"]
        )
    return out


def vg_block(series: list[Any]) -> dict[str, Any]:
    vg = ddload.variogram(series)
    return {"summary": summarise(vg), "bins": vg["bins"]}


def deviations(z: np.ndarray) -> np.ndarray:
    out: np.ndarray = z - cohlib.rolling_level(z)
    return out


def robust_sv(d2: np.ndarray) -> float:
    """Cressie-Hawkins semivariance from squared differences (same form as ddload)."""
    c = d2.size
    return float((np.mean(np.sqrt(np.sqrt(d2))) ** 4) / (2.0 * (0.457 + 0.494 / c)))


def subday_matched(series: list[Any]) -> dict[str, Any]:
    """Consecutive device-wide rounds less than SUBDAY_H apart, each against the nearest
    preceding and following consecutive-round pairs 18 to 30 h apart (same qubits' changes)."""
    stamps = np.concatenate([s.t_ms[1:] for s in series])
    ents = np.concatenate([np.full(s.t_ms.size - 1, s.entity) for s in series])
    zs = np.concatenate([np.log10(s.y[1:]) for s in series])
    starts, rid = cohlib.rounds(stamps)
    vals: dict[int, dict[int, float]] = {}
    for k, e, z in zip(rid, ents, zs, strict=True):
        vals.setdefault(int(k), {})[int(e)] = float(z)
    big = [k for k in range(starts.size) if len(vals.get(k, {})) >= BIG_ROUND]
    rows = []
    for a, b in pairwise(big):
        common = sorted(set(vals[a]) & set(vals[b]))
        d2 = np.array([(vals[b][e] - vals[a][e]) ** 2 for e in common])
        rows.append(((starts[b] - starts[a]) / ddload.MS_PER_HOUR, float(starts[a]), d2))
    occ = []
    for i, (gap, t0, d2) in enumerate(rows):
        if gap >= SUBDAY_H:
            continue
        ref = []
        for j in range(i - 1, -1, -1):
            if 18.0 <= rows[j][0] < 30.0:
                ref.append(rows[j][2])
                break
        for j in range(i + 1, len(rows)):
            if 18.0 <= rows[j][0] < 30.0:
                ref.append(rows[j][2])
                break
        r2 = np.concatenate(ref) if ref else np.array([])
        occ.append(
            {
                "first_round_utc": ddload_utc(t0),
                "gap_h": cohlib.r(gap, 4),
                "qubits": int(d2.size),
                "semivariance": cohlib.r(np.mean(d2) / 2.0),
                "semivariance_robust": cohlib.r(robust_sv(d2)),
                "ref_pairs": int(r2.size),
                "ref_semivariance": cohlib.r(np.mean(r2) / 2.0) if r2.size else None,
                "ref_semivariance_robust": cohlib.r(robust_sv(r2)) if r2.size else None,
            }
        )
    ok = [o for o in occ if o["ref_semivariance_robust"]]
    ratio = np.array([o["semivariance_robust"] / o["ref_semivariance_robust"] for o in ok])
    w = (
        stats.wilcoxon([o["semivariance_robust"] - o["ref_semivariance_robust"] for o in ok])
        if len(ok) >= 6
        else None
    )
    return {
        "occasions": occ,
        "n_occasions": len(occ),
        "robust_ratio_subday_over_ref_quantiles": cohlib.q(ratio),
        "wilcoxon_p_robust_difference": cohlib.r(w.pvalue) if w is not None else None,
        "subday_h": SUBDAY_H,
    }


def ddload_utc(t: float) -> str:
    return datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fisher_floor(n: int, kind: str, kmax: float, a: float, b: float) -> float:
    """sigma(log10 T) * sqrt(total shots) for p(x) = a exp(-x) + b at the given delays."""
    x = np.linspace(0.0, kmax, n) if kind == "lin" else np.geomspace(0.01, kmax, n)
    p = a * np.exp(-x) + b
    # gradient w.r.t. (a, b, T) at T = 1: dp/dT = a x exp(-x)
    g = np.stack([np.exp(-x), np.ones_like(x), a * x * np.exp(-x)], axis=1)
    w = 1.0 / (p * (1.0 - p))
    info = (g * w[:, None]).T @ g / n  # per shot, shots spread evenly over the n delays
    cov = np.linalg.inv(info)
    rel_sd_one_shot = float(np.sqrt(cov[2, 2]))
    return rel_sd_one_shot / np.log(10.0)


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    rng = np.random.default_rng(RNG_SEED)
    out = cohlib.header("analysis/coherence/nonpersistent.py")
    out["n_files"] = dd.n_files
    out["thresholds"] = {
        "short_lag_h": SHORT_LAG_H,
        "big_round_min_qubits": BIG_ROUND,
        "small_round_max_qubits": SMALL_ROUND,
        "trim_abs_dev_decades": TRIM,
        "bootstrap_reps": N_BOOT,
        "seed": RNG_SEED,
        "windows_ms": {k: [float(a), float(b)] for k, (a, b) in WINDOWS.items()},
    }
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    pairs, _ = cohlib.paired(dd)
    s_med = {p.entity: float(np.median(p.t2 / (2 * p.t1))) for p in pairs}
    gphi = [
        ddload.Series(
            entity=p.entity, t_ms=p.t_ms, file_idx=p.file_idx, y=cohlib.gamma_phi(p.t1, p.t2)
        )
        for p in pairs
    ]
    sser = [
        ddload.Series(entity=p.entity, t_ms=p.t_ms, file_idx=p.file_idx, y=p.t2 / (2 * p.t1))
        for p in pairs
    ]

    # ---- 1. variograms
    vgs: dict[str, Any] = {}
    for name, ss in (
        ("log10_T1", s1),
        ("log10_T2", s2),
        ("log10_gamma_phi", gphi),
        ("log10_T2_over_2T1", sser),
    ):
        vgs[name] = {"all": vg_block(ss)}
        for w, (lo, hi) in WINDOWS.items():
            vgs[name][w] = {"summary": summarise(ddload.variogram(sub(ss, lo, hi)))}
    vgs["log10_T1"]["excluding_q11_q17_q72"] = vg_block(
        [s for s in s1 if s.entity not in (11, 17, 72)]
    )
    terc = np.quantile(list(s_med.values()), (1 / 3, 2 / 3))
    vgs["log10_gamma_phi_by_s_tertile"] = {
        "tertile_edges_s": [cohlib.r(terc[0]), cohlib.r(terc[1])]
    }
    for k, (lo, hi) in enumerate(((-np.inf, terc[0]), (terc[0], terc[1]), (terc[1], np.inf))):
        part = [s for s in gphi if lo <= s_med[s.entity] < hi]
        vgs["log10_gamma_phi_by_s_tertile"][f"tertile_{k + 1}"] = {
            "qubits": len(part),
            "nonpositive_values_dropped": int(sum(np.sum(s.y <= 0) for s in part)),
            "summary": summarise(ddload.variogram(part)),
        }
    vgs["log10_gamma_phi_nonpositive_dropped"] = int(sum(np.sum(s.y <= 0) for s in gphi))
    out["variograms"] = vgs

    # ---- 2. short-lag audit (consecutive events less than SHORT_LAG_H apart)
    audit: dict[str, Any] = {}
    for name, ss in (("T1", s1), ("T2", s2)):
        stamps = np.concatenate([s.t_ms[1:] for s in ss])
        ents = np.concatenate([np.full(s.t_ms.size - 1, s.entity) for s in ss])
        _, rid = cohlib.rounds(stamps)
        size = np.bincount(rid, minlength=rid.max() + 1)
        # distinct qubits per round
        nq = np.array([np.unique(ents[rid == k]).size for k in range(rid.max() + 1)])
        del size
        pos = 0
        dz_big, dz_small, dz_mid, firstdev, alldev, qubits = [], [], [], [], [], set()
        for s in ss:
            z = np.log10(s.y)
            dev = deviations(z)
            alldev.append(np.abs(dev[np.isfinite(dev)]))
            r_ids = rid[pos : pos + s.t_ms.size - 1]
            pos += s.t_ms.size - 1
            lag = np.diff(s.t_ms) / ddload.MS_PER_HOUR
            for i in np.flatnonzero(lag < SHORT_LAG_H):
                if i == 0:
                    continue  # the first event's stamp predates the archive
                rq = nq[r_ids[i]]  # round of the second event (event i + 1 is index i in r_ids)
                d = 0.5 * (z[i + 1] - z[i]) ** 2
                (dz_big if rq >= BIG_ROUND else dz_small if rq <= SMALL_ROUND else dz_mid).append(d)
                if np.isfinite(dev[i]):
                    firstdev.append(abs(dev[i]))
                qubits.add(s.entity)
        audit[name] = {
            "pairs_in_big_rounds": len(dz_big),
            "pairs_in_small_rounds": len(dz_small),
            "pairs_in_mid_rounds": len(dz_mid),
            "qubits": len(qubits),
            "semivariance_big_rounds": cohlib.r(np.mean(dz_big)) if dz_big else None,
            "semivariance_small_rounds": cohlib.r(np.mean(dz_small)) if dz_small else None,
            "median_abs_dev_first_event_of_short_pair": cohlib.r(np.median(firstdev))
            if firstdev
            else None,
            "median_abs_dev_all_events": cohlib.r(np.median(np.concatenate(alldev))),
        }
    out["short_lag_audit"] = audit
    out["subday_matched"] = {name: subday_matched(ss) for name, ss in (("T1", s1), ("T2", s2))}

    # ---- 3. same-round co-movement of T1 and T2 (paired events)
    xs, ys, ss_, ents, ts = [], [], [], [], []
    per_q = []
    for p in pairs:
        x = deviations(np.log10(p.t1))
        y = deviations(np.log10(p.t2))
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 20:
            continue
        xs.append(x[ok])
        ys.append(y[ok])
        ss_.append(np.full(ok.sum(), s_med[p.entity]))
        ents.append(np.full(ok.sum(), p.entity))
        ts.append(p.t_ms[ok])
        xo, yo = x[ok], y[ok]
        slope = float(np.polyfit(xo, yo, 1)[0])
        per_q.append((p.entity, s_med[p.entity], slope, float(stats.spearmanr(xo, yo).statistic)))
    x = np.concatenate(xs)
    y = np.concatenate(ys)
    sm = np.concatenate(ss_)
    tt = np.concatenate(ts)
    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    trim = (np.abs(x) < TRIM) & (np.abs(y) < TRIM)
    pq = np.array([(a, b, c, d) for a, b, c, d in per_q])
    rho_slope_s = stats.spearmanr(pq[:, 1], pq[:, 2])
    terc_rows = []
    for lo, hi in ((-np.inf, terc[0]), (terc[0], terc[1]), (terc[1], np.inf)):
        m = (sm >= lo) & (sm < hi)
        sl = float(np.polyfit(x[m], y[m], 1)[0])
        s_mid = float(np.median(sm[m]))
        terc_rows.append(
            {
                "events": int(m.sum()),
                "median_s": cohlib.r(s_mid),
                "ols_slope": cohlib.r(sl),
                "slope_over_s": cohlib.r(sl / s_mid),
                "pearson": cohlib.r(stats.pearsonr(x[m], y[m]).statistic),
                "spearman": cohlib.r(stats.spearmanr(x[m], y[m]).statistic),
            }
        )
    win_rows = {}
    for w, (lo, hi) in WINDOWS.items():
        m = (tt >= lo) & (tt < hi)
        win_rows[w] = {
            "events": int(m.sum()),
            "pearson": cohlib.r(stats.pearsonr(x[m], y[m]).statistic),
            "spearman": cohlib.r(stats.spearmanr(x[m], y[m]).statistic),
        }
    # Same-round deviations of log T1 against log Gamma_phi. An independent error in T1 alone
    # moves Gamma_phi = 1/T2 - 1/(2 T1) in the SAME direction as T1 (positive correlation);
    # a real T1 drop that comes with extra dephasing moves them in opposite directions.
    gx, gy, gs = [], [], []
    for p in pairs:
        g = cohlib.gamma_phi(p.t1, p.t2)
        ok0 = g > 0
        if ok0.sum() < 20:
            continue
        a = deviations(np.log10(p.t1[ok0]))
        b = deviations(np.log10(g[ok0]))
        ok = np.isfinite(a) & np.isfinite(b)
        gx.append(a[ok])
        gy.append(b[ok])
        gs.append(np.full(ok.sum(), s_med[p.entity]))
    gxa, gya, gsa = np.concatenate(gx), np.concatenate(gy), np.concatenate(gs)
    t1_gphi = {
        "events": int(gxa.size),
        "spearman": cohlib.r(stats.spearmanr(gxa, gya).statistic),
        "by_s_tertile_spearman": [
            cohlib.r(
                stats.spearmanr(
                    gxa[(gsa >= lo) & (gsa < hi)], gya[(gsa >= lo) & (gsa < hi)]
                ).statistic
            )
            for lo, hi in ((-np.inf, terc[0]), (terc[0], terc[1]), (terc[1], np.inf))
        ],
    }
    out["t1_t2_comovement"] = {
        "t1_vs_gamma_phi": t1_gphi,
        "events": int(x.size),
        "qubits": int(pq.shape[0]),
        "pearson": cohlib.r(pear.statistic),
        "pearson_sq": cohlib.r(pear.statistic**2),
        "spearman": cohlib.r(spear.statistic),
        "spearman_sq": cohlib.r(spear.statistic**2),
        "pearson_trimmed": cohlib.r(stats.pearsonr(x[trim], y[trim]).statistic),
        "trimmed_events": int(trim.sum()),
        "ols_slope_pooled": cohlib.r(np.polyfit(x, y, 1)[0]),
        "per_qubit_spearman_quantiles": cohlib.q(pq[:, 3]),
        "per_qubit_spearman_positive_share": cohlib.r(np.mean(pq[:, 3] > 0)),
        "per_qubit_slope_quantiles": cohlib.q(pq[:, 2]),
        "spearman_slope_vs_median_s_across_qubits": cohlib.r(rho_slope_s.statistic),
        "spearman_slope_vs_median_s_p": cohlib.r(rho_slope_s.pvalue),
        "by_s_tertile": terc_rows,
        "by_window": win_rows,
        "dev_scale_mad_T1": cohlib.r(1.4826 * np.median(np.abs(x))),
        "dev_scale_mad_T2": cohlib.r(1.4826 * np.median(np.abs(y))),
        "note": "deviations from the centred running median (event left out) of each paired series",
    }

    # ---- 4. heterogeneity of the deviation scale and skew across qubits
    het: dict[str, Any] = {}
    for name, ss in (("T1", s1), ("T2", s2), ("gamma_phi", gphi)):
        devs, levels, ents_h = [], [], []
        for s in ss:
            yv = s.y[s.y > 0]
            if yv.size < 30:
                continue
            z = np.log10(yv)
            dv = deviations(z)
            dv = dv[np.isfinite(dv)]
            devs.append(dv)
            levels.append(float(np.median(z)))
            ents_h.append(s.entity)
        scale = np.array([1.4826 * np.median(np.abs(d - np.median(d))) for d in devs])
        qskew = np.array(
            [
                (np.quantile(d, 0.95) + np.quantile(d, 0.05) - 2 * np.median(d))
                / (np.quantile(d, 0.95) - np.quantile(d, 0.05))
                for d in devs
            ]
        )
        pooled = np.concatenate(devs)
        sizes = [d.size for d in devs]
        boot = []
        for _ in range(N_BOOT):
            sc = [
                1.4826 * np.median(np.abs(v - np.median(v)))
                for v in (rng.choice(pooled, n) for n in sizes)
            ]
            boot.append(np.quantile(sc, 0.9) / np.quantile(sc, 0.1))
        lv = stats.spearmanr(levels, scale)
        fl = stats.fligner(*devs)
        order = np.argsort(-scale)
        het[name] = {
            "qubits": len(devs),
            "scale_mad_quantiles": cohlib.q(scale),
            "scale_p90_over_p10": cohlib.r(np.quantile(scale, 0.9) / np.quantile(scale, 0.1)),
            "bootstrap_null_p90_over_p10_quantiles_5_50_95": [
                cohlib.r(v) for v in np.quantile(boot, (0.05, 0.5, 0.95))
            ],
            "fligner_p": cohlib.r(fl.pvalue),
            "spearman_level_vs_scale": cohlib.r(lv.statistic),
            "spearman_level_vs_scale_p": cohlib.r(lv.pvalue),
            "quantile_skew_quantiles": cohlib.q(qskew),
            "quantile_skew_negative_share": cohlib.r(np.mean(qskew < 0)),
            "pooled_share_dev_below_minus_0.301": cohlib.r(np.mean(pooled < -np.log10(2))),
            "pooled_share_dev_above_plus_0.301": cohlib.r(np.mean(pooled > np.log10(2))),
            "pooled_share_dev_below_minus_0.176": cohlib.r(np.mean(pooled < -np.log10(1.5))),
            "pooled_share_dev_above_plus_0.176": cohlib.r(np.mean(pooled > np.log10(1.5))),
            "pooled_dev_quantiles": cohlib.q(pooled),
            "most_volatile_qubits": [
                {
                    "qubit": ents_h[i],
                    "scale": cohlib.r(scale[i]),
                    "level_log10": cohlib.r(levels[i]),
                }
                for i in order[:6]
            ],
        }
    out["heterogeneity"] = het

    # ---- 5. shot-noise floor
    nug = {
        "T1": vgs["log10_T1"]["all"]["summary"]["bin_18_30h"]["semivariance"],
        "T2": vgs["log10_T2"]["all"]["summary"]["bin_18_30h"]["semivariance"],
        "T1_robust": vgs["log10_T1"]["all"]["summary"]["bin_18_30h"]["semivariance_robust"],
        "T2_robust": vgs["log10_T2"]["all"]["summary"]["bin_18_30h"]["semivariance_robust"],
    }
    readout = {
        "median": (1.0 - cohlib.P10_MEDIAN - cohlib.P01_MEDIAN, cohlib.P01_MEDIAN),
        "p99": (1.0 - cohlib.P10_P99 - cohlib.P01_P99, cohlib.P01_P99),
    }
    floor: dict[str, Any] = {
        "model": (
            "p(x) = a exp(-x) + b, x = delay / T, free (a, b, T), "
            "binomial shots spread evenly over the delays"
        ),
        "t1_signal": "a = 1 - p10 - p01, b = p01",
        "t2_echo_signal": "a = (1 - p10 - p01) / 2, b = p01 + a",
        "observed_semivariance_18_30h": {k: cohlib.r(v) for k, v in nug.items()},
        "designs": {},
    }
    for dname, (n, kind, kmax) in DESIGNS.items():
        row: dict[str, Any] = {}
        for rname, (amp, off) in readout.items():
            c1 = fisher_floor(n, kind, kmax, amp, off)
            c2 = fisher_floor(n, kind, kmax, amp / 2.0, off + amp / 2.0)
            row[rname] = {
                "T1_sd_log10_times_sqrt_shots": cohlib.r(c1),
                "T2echo_sd_log10_times_sqrt_shots": cohlib.r(c2),
                "T1_sd_log10_at_1000_shots": cohlib.r(c1 / np.sqrt(1000)),
                "T1_sd_log10_at_10000_shots": cohlib.r(c1 / np.sqrt(10000)),
                "T2_sd_log10_at_10000_shots": cohlib.r(c2 / np.sqrt(10000)),
                "T1_total_shots_floor_equals_nugget": cohlib.r(c1**2 / nug["T1"]),
                "T2_total_shots_floor_equals_nugget": cohlib.r(c2**2 / nug["T2"]),
                "T1_total_shots_floor_equals_robust_nugget": cohlib.r(c1**2 / nug["T1_robust"]),
            }
        floor["designs"][dname] = row
    # Published shot budgets, evaluated on the log-spaced design of this block with the
    # median readout (neither is IBM's production setting, which is not published).
    c_log1 = fisher_floor(40, "log", 5.0, *readout["median"])
    a_med, b_med = readout["median"]
    c_lin2 = fisher_floor(11, "lin", 3.0, a_med / 2.0, b_med + a_med / 2.0)
    floor["published_budgets"] = {
        "klimov_2018_google_80000_shots": {
            "shots": KLIMOV_SHOTS,
            "T1_sd_log10": cohlib.r(c_log1 / np.sqrt(KLIMOV_SHOTS)),
            "T1_var_log10_over_nugget": cohlib.r((c_log1**2 / KLIMOV_SHOTS) / nug["T1"]),
        },
        "qiskit_t2hahn_example_22000_shots": {
            "shots": QISKIT_T2HAHN_SHOTS,
            "T2_sd_log10_11_uniform_delays_to_3T": cohlib.r(c_lin2 / np.sqrt(QISKIT_T2HAHN_SHOTS)),
            "T2_var_log10_over_nugget": cohlib.r((c_lin2**2 / QISKIT_T2HAHN_SHOTS) / nug["T2"]),
        },
    }
    out["shot_noise_floor"] = floor

    # ---- 6. literature benchmark (delta method: sd(log10 T1) ~ sd / (mean ln 10))
    lit = {}
    for k, (mu, sd) in BURNETT.items():
        v = (sd / (mu * np.log(10.0))) ** 2
        lit[k] = {
            "mean_us": mu,
            "sd_us": sd,
            "implied_var_log10": cohlib.r(v),
            "implied_sd_log10": cohlib.r(np.sqrt(v)),
        }
    out["literature_benchmark"] = {
        "source": (
            "Burnett et al. 2019, arXiv:1901.04417, Fig. 1b "
            "(about 65 h, 2,000 consecutive T1 values)"
        ),
        "values": lit,
    }
    lit_in: dict[str, Any] = {}
    for k, (lo_uhz, hi_uhz) in RATES_UHZ.items():
        lit_in[k] = {
            "rate_uhz": [lo_uhz, hi_uhz],
            "one_over_rate_h": [
                cohlib.r(1.0 / (hi_uhz * 1e-6) / 3600.0, 4),
                cohlib.r(1.0 / (lo_uhz * 1e-6) / 3600.0, 4),
            ],
        }
    lit_in["burnett_2019_dwell_h"] = list(BURNETT_DWELL_H)
    lit_in["klimov_2018_design"] = {
        "repeats_per_delay": 2000,
        "delays": 40,
        "delay_range_us": [0.01, 100],
        "seconds_per_t1_curve": 2,
        "t1_variation_up_to_factor": 10,
        "abrupt_changes_on_minutes": 15,
    }
    for k, (val, err) in QISKIT_EXAMPLES.items():
        lit_in[k] = {
            "value_s": val,
            "stderr_s": err,
            "relative": cohlib.r(err / val, 4),
            "sd_log10": cohlib.r(err / val / np.log(10.0), 4),
        }
    out["literature_inputs"] = lit_in
    cohlib.write("nonpersistent.json", out)


if __name__ == "__main__":
    main()
