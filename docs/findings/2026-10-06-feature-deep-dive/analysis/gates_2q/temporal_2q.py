"""Temporal structure of cz and rzz errors: memory, device level, change points, seasonality.

Writes ``results/gates_2q/temporal.json``. Canonical direction, placeholders masked,
measured-rule events, log10 values. Loads only ``g2.cz.gate_error``, ``g2.rzz.gate_error``
and the per-file arrays used for the coverage split.

Methods (all in log10 units):

- Autocorrelation of changes at lags 1 to 4, pooled over couplers (Pearson, as P2 did, and
  Spearman). A local level plus independent noise gives a lag-1 value of ``-1 / (2 + q)``
  and zero at lags 2 and more; memory in the non-persistent component shows at lag 2.
- Device level per round: the median over couplers of the events in each device-wide round.
- Change points on that device series: binary segmentation, each split the argmax of the
  absolute standardized CUSUM, kept when a permutation p-value (999 shuffles) is below
  0.01, at most 3 levels deep. Shuffling assumes exchangeable rounds under the null, so a
  slow drift also counts as "not exchangeable".
- Per-coupler single change point: the same statistic per coupler series, permutation
  p-values (499 shuffles), Benjamini-Hochberg at a 5% false-discovery rate across couplers.
- Seasonality of values: each event's deviation from the median of its 3 + 3 neighbours,
  grouped by the UTC hour and the weekday of its stamp; Kruskal-Wallis with epsilon squared.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/temporal_2q.py"
RNG = np.random.default_rng(20261006)


def autocorr(series: dict[int, Any], split: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, sel in (("all", None), ("before_split", True), ("after_split", False)):
        res: dict[str, Any] = {}
        for lag in (1, 2, 3, 4):
            x: list[float] = []
            y: list[float] = []
            for s in series.values():
                z = np.log10(s.y)
                dz = np.diff(z)
                t = s.t_ms[1:]
                for k in range(dz.size - lag):
                    if sel is not None and ((t[k + lag] < split) != sel or (t[k] < split) != sel):
                        continue
                    x.append(float(dz[k]))
                    y.append(float(dz[k + lag]))
            xa, ya = np.array(x), np.array(y)
            res[f"lag{lag}"] = {
                "pearson": c.rnd(float(np.corrcoef(xa, ya)[0, 1])) if xa.size > 3 else None,
                "spearman": c.spearman(xa, ya)["rho"],
                "pairs": int(xa.size),
            }
        out[name] = res
    r1 = out["all"]["lag1"]["pearson"]
    out["implied_q_from_lag1"] = c.rnd(-1.0 / r1 - 2.0) if r1 and r1 < 0 else None
    return out


def cusum_split(z: np.ndarray) -> tuple[int, float]:
    """Index and value of the max absolute standardized CUSUM of ``z`` (split before index)."""
    n = z.size
    s = np.cumsum(z - z.mean())[:-1]
    k = np.arange(1, n)
    scale = np.sqrt(k * (n - k) / n)
    stat = np.abs(s) / scale
    j = int(np.argmax(stat))
    return j + 1, float(stat[j])


def perm_p(z: np.ndarray, n_perm: int) -> tuple[int, float, float]:
    idx, stat = cusum_split(z)
    hits = 0
    for _ in range(n_perm):
        if cusum_split(RNG.permutation(z))[1] >= stat:
            hits += 1
    return idx, stat, (hits + 1) / (n_perm + 1)


def binseg(z: np.ndarray, t: np.ndarray, depth: int = 0, lo: int = 0) -> list[dict[str, Any]]:
    if depth >= 3 or z.size < 12:
        return []
    idx, _stat, p = perm_p(z, 999)
    if p >= 0.01:
        return []
    left, right = z[:idx], z[idx:]
    found = [
        {
            "at_round_start": c.iso(t[idx]),
            "depth": depth,
            "p": c.rnd(p, 3),
            "median_before_log10": c.rnd(float(np.median(left))),
            "median_after_log10": c.rnd(float(np.median(right))),
            "shift_factor": c.rnd(float(10 ** (np.median(right) - np.median(left)))),
            "rounds_before": int(left.size),
            "rounds_after": int(right.size),
        }
    ]
    found += binseg(left, t[:idx], depth + 1, lo)
    found += binseg(right, t[idx:], depth + 1, lo + idx)
    return found


def device_series(series: dict[int, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    stamps = np.concatenate([s.t_ms for s in series.values()])
    vals = np.concatenate([np.log10(s.y) for s in series.values()])
    order = np.argsort(stamps)
    stamps, vals = stamps[order], vals[order]
    rds = c.rounds(stamps)
    meds, starts, sizes = [], [], []
    k = 0
    for r in rds:
        seg = vals[k : k + r.size]
        k += r.size
        if r.size >= 0.5 * len(series):
            meds.append(float(np.median(seg)))
            starts.append(float(r[0]))
            sizes.append(r.size)
    return np.array(starts), np.array(meds), np.array(sizes)


def monthly(series: dict[int, Any]) -> dict[str, Any]:
    stamps = np.concatenate([s.t_ms for s in series.values()])
    vals = np.concatenate([np.log10(s.y) for s in series.values()])
    months = stamps.astype("datetime64[ms]").astype("datetime64[M]").astype(str)
    out = {}
    for m in np.unique(months):
        sel = months == m
        out[str(m)] = {"events": int(sel.sum()), "median": c.rnd(float(10 ** np.median(vals[sel])))}
    return out


def per_coupler_changepoints(
    series: dict[int, Any], lab: dict[int, str], split: float
) -> dict[str, Any]:
    rows = []
    for col, s in series.items():
        z = np.log10(s.y)
        if z.size < 30:
            continue
        idx, _stat, p = perm_p(z, 499)
        rows.append(
            {
                "coupler": lab[col],
                "p": p,
                "at": c.iso(s.t_ms[idx]),
                "at_ms": float(s.t_ms[idx]),
                "shift_factor": float(10 ** (np.median(z[idx:]) - np.median(z[:idx]))),
            }
        )
    disc = c.bh([r["p"] for r in rows])
    hits = [r for r, d in zip(rows, disc, strict=True) if d]
    hits.sort(key=lambda r: r["p"])
    shifts = np.array([r["shift_factor"] for r in hits])
    months = (
        np.array([r["at_ms"] for r in hits])
        .astype("datetime64[ms]")
        .astype("datetime64[M]")
        .astype(str)
    )
    return {
        "couplers_tested_ge_30_events": len(rows),
        "discoveries_bh_5pct": len(hits),
        "discovery_shift_factor_q": c.q(shifts),
        "discoveries_up": int(np.sum(shifts > 1)) if shifts.size else 0,
        "discoveries_down": int(np.sum(shifts < 1)) if shifts.size else 0,
        "discoveries_by_month": {str(m): int(np.sum(months == m)) for m in np.unique(months)},
        "discoveries_before_split": int(sum(r["at_ms"] < split for r in hits)),
        "top": [
            {k: (c.rnd(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "at_ms"}
            for r in hits[:12]
        ],
    }


def seasonality(series: dict[int, Any]) -> dict[str, Any]:
    dev_all: list[np.ndarray] = []
    t_all: list[np.ndarray] = []
    for s in series.values():
        if s.y.size < 8:
            continue
        dev_all.append(c.moving_median_deviation(np.log10(s.y)))
        t_all.append(s.t_ms)
    dev = np.concatenate(dev_all)
    t = np.concatenate(t_all)
    ok = np.isfinite(dev)
    dev, t = dev[ok], t[ok]
    hour, weekday = c.hour_weekday(t)
    hour4 = hour // 4
    return {
        "events": int(dev.size),
        "by_utc_hour": c.kruskal_groups(dev, hour, min_n=200),
        "by_utc_4h_block": c.kruskal_groups(dev, hour4, min_n=200),
        "by_weekday_mon0": c.kruskal_groups(dev, weekday, min_n=200),
    }


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    lab = {col: c.label(pairs[i]) for i, col in enumerate(fwd)}
    split = c.split_ms(dd)
    payload: dict[str, Any] = {"n_files": dd.n_files, "coverage_split_utc": c.iso(split)}
    for gate in c.GATES:
        series = c.gate_series(dd, gate, fwd)
        starts, meds, _sizes = device_series(series)
        trend = np.polyfit((starts - starts[0]) / (24 * ddload.MS_PER_HOUR), meds, 1)[0]
        ts = stats.theilslopes(meds, (starts - starts[0]) / (24 * ddload.MS_PER_HOUR))
        dmed = np.diff(meds)
        payload[gate] = {
            "autocorrelation_of_log_changes": autocorr(series, split),
            "device_rounds_ge_half": int(meds.size),
            "device_round_median_q": c.q(10.0**meds),
            "device_round_median_log10_series": [round(float(x), 4) for x in meds],
            "device_round_start_series": [c.iso(x) for x in starts],
            "device_round_lag1_of_change": c.rnd(float(np.corrcoef(dmed[:-1], dmed[1:])[0, 1])),
            "device_trend_log10_per_30d_ols": c.rnd(float(trend * 30)),
            "device_trend_log10_per_30d_theil_sen": c.rnd(float(ts.slope * 30)),
            "device_trend_theil_sen_95ci_per_30d": [
                c.rnd(float(ts.low_slope * 30)),
                c.rnd(float(ts.high_slope * 30)),
            ],
            "device_change_points": binseg(meds, starts),
            "monthly_event_median": monthly(series),
            "per_coupler_change_points": per_coupler_changepoints(series, lab, split),
            "value_seasonality": seasonality(series),
        }
    path = c.write("temporal.json", SCRIPT, payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
