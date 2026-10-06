"""Temporal structure of log T1, log T2 and log pure-dephasing rate: level, drift, change points,
memory and value seasonality.

Writes ``results/coherence/temporal.json``.

Units of analysis:

- per qubit: the qubit's event series (first event excluded everywhere, because its stamp
  predates the archive), deviations ``dev = log10(y) - median(log10(y))`` over the qubit's
  whole history;
- per round: device-wide rounds (``cohlib.rounds``) with at least ``BIG_ROUND`` qubits; the
  round statistic is the median ``dev`` over the qubits measured in it. Seasonality and
  device-wide change points are tested on rounds, never on records, because the records of
  one round are not independent.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cohlib
import ddload

BIG_ROUND = 78
MIN_SEG = 8
SEG_P = 0.01
KNOWN_WINDOW_ROUNDS = 10
NEAR_DAYS = 3.0
MAX_LAG = 20
HOUR_BINS = (0, 4, 8, 12, 16, 20, 24)
# The device-wide level shift found at 2026-05-29 (section "known_dates") splits the
# record; per-qubit trends are also measured after it, and the ACF in three windows.
POST_MAY = "2026-05-30T00:00:00Z"
ACF_WINDOWS = {
    "all": ("", ""),
    "2026-05-30_to_split": (POST_MAY, "2026-08-05T23:45:31Z"),
    "after_split": ("2026-08-05T23:45:31Z", ""),
    "before_2026-05-30": ("", POST_MAY),
}
# Device-wide dates from 01-data-layer.md (sections 3 and 5); day-only entries are midnight.
KNOWN_DATES = {
    "xslow_appears_2026-05-14": "2026-05-14T12:32:42Z",
    "xslow_absent_2026-05-29": "2026-05-29T16:46:42Z",
    "readout_length_1700_2026-06-08": "2026-06-08T18:56:28Z",
    "readout_length_1660_2026-07-30": "2026-07-30T21:09:17Z",
    "init_error_starts_2026-08-04": "2026-08-04T00:00:00Z",
    "measure_2_starts_2026-08-07": "2026-08-07T00:00:00Z",
    "measure_reset_starts_2026-09-02": "2026-09-02T00:00:00Z",
    "q72_coupler_length_2026-09-05": "2026-09-05T17:51:36Z",
    "xslow_present_2026-09-10": "2026-09-10T16:56:21Z",
}


def ms(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp() * 1000.0


def utc(t: float) -> str:
    return datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def pettitt(x: np.ndarray) -> tuple[int, float, float]:
    """Pettitt's rank change-point test: (index of the last point before the change, K, p)."""
    n = x.size
    rk = stats.rankdata(x)
    t = np.arange(1, n)
    u = 2.0 * np.cumsum(rk)[:-1] - t * (n + 1)
    k_idx = int(np.argmax(np.abs(u)))
    k = float(np.abs(u[k_idx]))
    p = float(min(1.0, 2.0 * np.exp(-6.0 * k * k / (n**3 + n**2))))
    return k_idx, k, p


def segment(x: np.ndarray, lo: int, hi: int, found: list[tuple[int, float]]) -> None:
    """Binary segmentation with Pettitt's test on x[lo:hi]."""
    if hi - lo < 2 * MIN_SEG:
        return
    k, _, p = pettitt(x[lo:hi])
    cut = lo + k + 1
    if p < SEG_P and cut - lo >= MIN_SEG and hi - cut >= MIN_SEG:
        found.append((cut, p))
        segment(x, lo, cut, found)
        segment(x, cut, hi, found)


def build(series: list[tuple[int, np.ndarray, np.ndarray]]) -> dict[str, np.ndarray]:
    ent, tt, zz, dev = [], [], [], []
    for e, t, y in series:
        z = np.log10(y)
        ok = np.isfinite(z)
        t, z = t[ok], z[ok]
        if z.size < 3:
            continue
        t, z = t[1:], z[1:]
        ent.append(np.full(z.size, e))
        tt.append(t)
        zz.append(z)
        dev.append(z - np.median(z))
    return {
        "e": np.concatenate(ent),
        "t": np.concatenate(tt),
        "z": np.concatenate(zz),
        "dev": np.concatenate(dev),
    }


def round_series(d: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    starts, rid = cohlib.rounds(d["t"])
    rows = []
    for k in range(starts.size):
        m = rid == k
        nq = np.unique(d["e"][m]).size
        if nq >= BIG_ROUND:
            rows.append(
                (
                    float(np.median(d["t"][m])),
                    float(np.median(d["dev"][m])),
                    float(np.median(d["z"][m])),
                    nq,
                )
            )
    a = np.array(rows)
    return {"t": a[:, 0], "dev": a[:, 1], "z": a[:, 2], "n": a[:, 3]}


def acf_pooled(series_dev: list[np.ndarray], max_lag: int) -> list[float | None]:
    out: list[float | None] = []
    for lag in range(1, max_lag + 1):
        num = den = 0.0
        for x in series_dev:
            x = x - np.mean(x)
            if x.size <= lag:
                continue
            num += float(np.sum(x[:-lag] * x[lag:]))
            den += float(np.sum(x * x)) * (x.size - lag) / x.size
        out.append(cohlib.r(num / den) if den > 0 else None)
    return out


def per_qubit_block(d: dict[str, np.ndarray], t_lo: float, t_hi: float) -> dict[str, Any]:
    """Theil-Sen trend (Kendall p) and Pettitt change point per qubit, BH across qubits."""
    slopes, kp, pk, shifts, cp_t = [], [], [], [], []
    for e in np.unique(d["e"]):
        m = (d["e"] == e) & (d["t"] >= t_lo) & (d["t"] < t_hi)
        t, z = d["t"][m], d["z"][m]
        if z.size < 2 * MIN_SEG:
            continue
        days = (t - t[0]) / 86_400_000.0
        slopes.append(stats.theilslopes(z, days).slope * 30.0)
        kp.append(stats.kendalltau(days, z).pvalue)
        k, _, p = pettitt(z)
        pk.append(p)
        shifts.append(float(np.median(z[k + 1 :]) - np.median(z[: k + 1])))
        cp_t.append(float(t[k + 1]))
    slopes_a, kp_a, pk_a = np.array(slopes), np.array(kp), np.array(pk)
    shifts_a, cp_a = np.array(shifts), np.array(cp_t)
    sig_t = cohlib.bh(kp_a)
    sig_c = cohlib.bh(pk_a)
    lo = max(t_lo, float(d["t"].min()))
    span = (min(t_hi, float(d["t"].max())) - lo) / 86_400_000.0
    near = np.zeros(cp_a.size, dtype=bool)
    n_dates = 0
    for iso in KNOWN_DATES.values():
        if lo <= ms(iso) < t_hi:
            n_dates += 1
            near |= np.abs(cp_a - ms(iso)) <= NEAR_DAYS * 86_400_000.0
    cp_months: dict[str, int] = {}
    for t in cp_a[sig_c]:
        lab = datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m")
        cp_months[lab] = cp_months.get(lab, 0) + 1
    return {
        "window_start_utc": utc(lo),
        "qubits_tested": int(slopes_a.size),
        "theil_sen_slope_decades_per_30d_quantiles": cohlib.q(slopes_a),
        "trend_bh_significant": int(sig_t.sum()),
        "trend_bh_significant_up": int(np.sum(sig_t & (slopes_a > 0))),
        "trend_bh_significant_down": int(np.sum(sig_t & (slopes_a < 0))),
        "pettitt_bh_significant": int(sig_c.sum()),
        "pettitt_abs_shift_quantiles_significant": cohlib.q(np.abs(shifts_a[sig_c])),
        "pettitt_shift_up_significant": int(np.sum(sig_c & (shifts_a > 0))),
        "pettitt_shift_down_significant": int(np.sum(sig_c & (shifts_a < 0))),
        "pettitt_significant_by_month": dict(sorted(cp_months.items())),
        "pettitt_significant_within_3d_of_known_date": int(np.sum(near & sig_c)),
        "known_dates_in_window": n_dates,
        "known_date_window_share_of_span": cohlib.r(min(1.0, n_dates * 2 * NEAR_DAYS / span)),
        "bh_alpha": 0.05,
    }


def memory_block(d: dict[str, np.ndarray]) -> dict[str, Any]:
    """Pooled ACF of per-qubit deviations, the qubit's mean removed inside each window."""
    out: dict[str, Any] = {
        "note": "deviations from each qubit's mean inside the window; slow drift raises every lag"
    }
    num = den = 0.0
    for lab, (a, b) in ACF_WINDOWS.items():
        lo, hi = ms(a) if a else -np.inf, ms(b) if b else np.inf
        devs = []
        for e in np.unique(d["e"]):
            m = (d["e"] == e) & (d["t"] >= lo) & (d["t"] < hi)
            if m.sum() > 10:
                devs.append(d["z"][m] - np.median(d["z"][m]))
        out[f"acf_dev_{lab}"] = acf_pooled(devs, MAX_LAG if lab == "all" else 5)
        out[f"qubits_{lab}"] = len(devs)
    for e in np.unique(d["e"]):
        dz = np.diff(d["z"][d["e"] == e])
        dz = dz - np.mean(dz)
        num += float(np.sum(dz[:-1] * dz[1:]))
        den += float(np.sum(dz * dz))
    out["lag1_autocorr_of_log_changes_pooled"] = cohlib.r(num / den)
    return out


def analyse(name: str, series: list[tuple[int, np.ndarray, np.ndarray]]) -> dict[str, Any]:
    d = build(series)
    rs = round_series(d)
    res: dict[str, Any] = {"events_used": int(d["z"].size), "qubits": int(np.unique(d["e"]).size)}

    # ---- device-wide round series
    lag1 = stats.spearmanr(rs["dev"][:-1], rs["dev"][1:])
    trend = stats.spearmanr(rs["t"], rs["dev"])
    months: dict[str, list[float]] = {}
    for t, z in zip(rs["t"], rs["z"], strict=True):
        months.setdefault(datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m"), []).append(z)
    gaps = np.diff(rs["t"]) / ddload.MS_PER_HOUR
    gap_rho = stats.spearmanr(gaps, rs["dev"][1:])
    i_min, i_max = int(np.argmin(rs["dev"])), int(np.argmax(rs["dev"]))
    res["rounds"] = {
        "big_rounds": int(rs["t"].size),
        "device_dev_quantiles": cohlib.q(rs["dev"]),
        "device_dev_min": {"utc": utc(rs["t"][i_min]), "dev": cohlib.r(rs["dev"][i_min])},
        "device_dev_max": {"utc": utc(rs["t"][i_max]), "dev": cohlib.r(rs["dev"][i_max])},
        "lag1_spearman": cohlib.r(lag1.statistic),
        "lag1_p": cohlib.r(lag1.pvalue),
        "trend_spearman_vs_time": cohlib.r(trend.statistic),
        "trend_p": cohlib.r(trend.pvalue),
        "device_median_log10_by_month": {
            m: cohlib.r(np.median(v)) for m, v in sorted(months.items())
        },
        "device_median_value_by_month": {
            m: cohlib.r(10 ** np.median(v), 4) for m, v in sorted(months.items())
        },
        "rounds_by_month": {m: len(v) for m, v in sorted(months.items())},
        "dev_vs_preceding_gap_spearman": cohlib.r(gap_rho.statistic),
        "dev_vs_preceding_gap_p": cohlib.r(gap_rho.pvalue),
    }

    # ---- device-wide change points (binary segmentation on the round series)
    found: list[tuple[int, float]] = []
    segment(rs["dev"], 0, rs["dev"].size, found)
    found.sort()
    cps = []
    bounds = [0] + [c for c, _ in found] + [rs["dev"].size]
    for (c, p), lo, hi in zip(found, bounds[:-2], bounds[2:], strict=True):
        cps.append(
            {
                "between_utc": [utc(rs["t"][c - 1]), utc(rs["t"][c])],
                "p_approx": cohlib.r(p),
                "median_before": cohlib.r(np.median(rs["dev"][lo:c])),
                "median_after": cohlib.r(np.median(rs["dev"][c:hi])),
                "rounds_before": c - lo,
                "rounds_after": hi - c,
            }
        )
    res["device_change_points"] = cps

    # ---- known device-wide dates: 10 big rounds before against 10 after
    known = {}
    for lab, iso in KNOWN_DATES.items():
        t0 = ms(iso)
        before = rs["dev"][rs["t"] < t0][-KNOWN_WINDOW_ROUNDS:]
        after = rs["dev"][rs["t"] >= t0][:KNOWN_WINDOW_ROUNDS]
        if before.size < 5 or after.size < 5:
            known[lab] = {
                "rounds_before": int(before.size),
                "rounds_after": int(after.size),
                "tested": False,
            }
            continue
        mw = stats.mannwhitneyu(before, after)
        known[lab] = {
            "rounds_before": int(before.size),
            "rounds_after": int(after.size),
            "shift_median_after_minus_before": cohlib.r(np.median(after) - np.median(before)),
            "mannwhitney_p": cohlib.r(mw.pvalue),
            "tested": True,
        }
    res["known_dates"] = known

    # ---- value seasonality on rounds
    hours = np.array([datetime.fromtimestamp(t / 1000.0, UTC).hour for t in rs["t"]])
    wd = np.array([datetime.fromtimestamp(t / 1000.0, UTC).weekday() for t in rs["t"]])
    hb = np.digitize(hours, HOUR_BINS[1:-1])
    groups_h = [rs["dev"][hb == k] for k in range(len(HOUR_BINS) - 1)]
    groups_w = [rs["dev"][wd == k] for k in range(7)]
    kw_h = stats.kruskal(*[g for g in groups_h if g.size >= 3])
    kw_w = stats.kruskal(*[g for g in groups_w if g.size >= 3])
    res["seasonality_rounds"] = {
        "hour_bins_utc": list(HOUR_BINS),
        "rounds_per_hour_bin": [int(g.size) for g in groups_h],
        "median_dev_per_hour_bin": [cohlib.r(np.median(g)) if g.size else None for g in groups_h],
        "kruskal_hour_p": cohlib.r(kw_h.pvalue),
        "rounds_per_weekday_mon_first": [int(g.size) for g in groups_w],
        "median_dev_per_weekday": [cohlib.r(np.median(g)) if g.size else None for g in groups_w],
        "kruskal_weekday_p": cohlib.r(kw_w.pvalue),
    }
    ev_h = np.array([datetime.fromtimestamp(t / 1000.0, UTC).hour for t in d["t"]])
    ev_hb = np.digitize(ev_h, HOUR_BINS[1:-1])
    res["seasonality_events_descriptive"] = {
        "events_per_hour_bin": [int(np.sum(ev_hb == k)) for k in range(len(HOUR_BINS) - 1)],
        "median_dev_per_hour_bin": [
            cohlib.r(np.median(d["dev"][ev_hb == k])) if np.any(ev_hb == k) else None
            for k in range(len(HOUR_BINS) - 1)
        ],
    }

    res["per_qubit"] = per_qubit_block(d, -np.inf, np.inf)
    res["per_qubit_from_2026_05_30"] = per_qubit_block(d, ms(POST_MAY), np.inf)
    res["memory"] = memory_block(d)
    return res


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    out = cohlib.header("analysis/coherence/temporal.py")
    out["n_files"] = dd.n_files
    out["thresholds"] = {
        "big_round_min_qubits": BIG_ROUND,
        "segmentation_min_rounds": MIN_SEG,
        "segmentation_p": SEG_P,
        "known_date_window_rounds": KNOWN_WINDOW_ROUNDS,
        "near_known_date_days": NEAR_DAYS,
        "known_dates": KNOWN_DATES,
        "post_may_start": POST_MAY,
        "acf_windows": ACF_WINDOWS,
    }
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    pairs, _ = cohlib.paired(dd)
    gp = []
    for p in pairs:
        g = cohlib.gamma_phi(p.t1, p.t2)
        ok = g > 0
        gp.append((p.entity, p.t_ms[ok], g[ok]))
    out["T1"] = analyse("T1", [(s.entity, s.t_ms, s.y) for s in s1])
    out["T2"] = analyse("T2", [(s.entity, s.t_ms, s.y) for s in s2])
    out["gamma_phi"] = analyse("gamma_phi", gp)
    out["T2_over_2T1"] = analyse("s", [(p.entity, p.t_ms, p.t2 / (2.0 * p.t1)) for p in pairs])
    names = ("T1", "T2", "gamma_phi", "T2_over_2T1")
    n_season = 2 * len(names)
    n_known = sum(1 for n in names for v in out[n]["known_dates"].values() if v["tested"])
    out["multiple_testing"] = {
        "seasonality_tests": n_season,
        "seasonality_bonferroni_at_0.05": cohlib.r(0.05 / n_season),
        "known_date_tests": n_known,
        "known_date_bonferroni_at_0.05": cohlib.r(0.05 / n_known),
    }
    cohlib.write("temporal.json", out)


if __name__ == "__main__":
    main()
