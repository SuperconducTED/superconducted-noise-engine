"""The size of the round-to-round change over time, and the device-wide boundary at 2026-05-29.

Writes ``results/coherence/regime.json``.

1. ``change_level``: for every pair of consecutive device-wide rounds (at least
   ``BIG_ROUND`` qubits each), the semivariance of the log10 change of the qubits measured in
   both, classical and robust (Cressie-Hawkins), and the device-wide median change. This is
   the nugget measured round by round, so its history shows whether the non-persistent
   component has a stable size. Summaries by month and a Pettitt change point.
2. ``boundary``: at ``BOUNDARY`` (the file in which ``xslow`` disappears, 01-data-layer.md
   section 5; the level shift found in temporal.json), the per-qubit level shift, the rank
   correlation of per-qubit levels across the boundary, and the per-qubit change scale before
   and after, each set against the same statistic at every other round boundary with
   ``W`` full rounds on both sides (the reference distribution).
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
W = 10
BOUNDARY = "2026-05-29T16:46:42Z"
# Regime windows read off change_level (first run of this script): the quiet stretch
# between the device-wide drop of the 2026-05-15T05 round and the jump of the
# 2026-05-28T06 round, the stretch up to the change-level Pettitt point of 2026-06-26/29,
# and the rest.
REGIMES = {
    "quiet_2026-05-15T12_to_2026-05-28T00": ("2026-05-15T12:00:00Z", "2026-05-28T00:00:00Z"),
    "2026-05-28T12_to_2026-06-28T00": ("2026-05-28T12:00:00Z", "2026-06-28T00:00:00Z"),
    "from_2026-06-28T00": ("2026-06-28T00:00:00Z", ""),
}


def ms(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp() * 1000.0


def utc(t: float) -> str:
    return datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def robust_sv(d2: np.ndarray) -> float:
    c = d2.size
    return float((np.mean(np.sqrt(np.sqrt(d2))) ** 4) / (2.0 * (0.457 + 0.494 / c)))


def round_table(
    series: list[tuple[int, np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, list[dict[int, float]]]:
    """Start stamp and {qubit: log10 value} of every device-wide round, in time order."""
    stamps = np.concatenate([t[1:] for _, t, _ in series])
    ents = np.concatenate([np.full(t.size - 1, e) for e, t, _ in series])
    zs = np.concatenate([np.log10(y[1:]) for _, _, y in series])
    starts, rid = cohlib.rounds(stamps)
    vals: dict[int, dict[int, float]] = {}
    for k, e, z in zip(rid, ents, zs, strict=True):
        if np.isfinite(z):
            vals.setdefault(int(k), {})[int(e)] = float(z)
    big = [k for k in range(starts.size) if len(vals.get(k, {})) >= BIG_ROUND]
    return starts[big], [vals[k] for k in big]


def pettitt(x: np.ndarray) -> tuple[int, float]:
    n = x.size
    rk = stats.rankdata(x)
    u = 2.0 * np.cumsum(rk)[:-1] - np.arange(1, n) * (n + 1)
    k = int(np.argmax(np.abs(u)))
    p = float(min(1.0, 2.0 * np.exp(-6.0 * u[k] ** 2 / (n**3 + n**2))))
    return k, p


def change_level(starts: np.ndarray, vals: list[dict[int, float]]) -> dict[str, Any]:
    rows = []
    for i in range(len(vals) - 1):
        common = sorted(set(vals[i]) & set(vals[i + 1]))
        d = np.array([vals[i + 1][e] - vals[i][e] for e in common])
        rows.append(
            (
                float(starts[i + 1]),
                (starts[i + 1] - starts[i]) / ddload.MS_PER_HOUR,
                len(common),
                float(np.mean(d * d) / 2.0),
                robust_sv(d * d),
                float(np.median(d)),
            )
        )
    a = np.array(rows)
    months: dict[str, list[float]] = {}
    for t, rv in zip(a[:, 0], a[:, 4], strict=True):
        months.setdefault(datetime.fromtimestamp(t / 1000.0, UTC).strftime("%Y-%m"), []).append(rv)
    k, p = pettitt(a[:, 4])
    low = np.argsort(a[:, 4])[:8]
    return {
        "round_pairs": int(a.shape[0]),
        "robust_sv_quantiles": cohlib.q(a[:, 4]),
        "classical_sv_quantiles": cohlib.q(a[:, 3]),
        "robust_sv_median_by_month": {m: cohlib.r(np.median(v)) for m, v in sorted(months.items())},
        "round_pairs_by_month": {m: len(v) for m, v in sorted(months.items())},
        "spearman_robust_sv_vs_gap": cohlib.r(stats.spearmanr(a[:, 1], a[:, 4]).statistic),
        "spearman_robust_sv_vs_gap_p": cohlib.r(stats.spearmanr(a[:, 1], a[:, 4]).pvalue),
        "pettitt_between_utc": [utc(a[k, 0]), utc(a[k + 1, 0])],
        "pettitt_p": cohlib.r(p),
        "robust_sv_median_before_pettitt": cohlib.r(np.median(a[: k + 1, 4])),
        "robust_sv_median_after_pettitt": cohlib.r(np.median(a[k + 1 :, 4])),
        "device_median_change_quantiles": cohlib.q(a[:, 5]),
        "lowest_robust_sv_round_pairs": [
            {
                "second_round_utc": utc(a[i, 0]),
                "gap_h": cohlib.r(a[i, 1], 4),
                "qubits": int(a[i, 2]),
                "robust_sv": cohlib.r(a[i, 4]),
                "classical_sv": cohlib.r(a[i, 3]),
            }
            for i in low
        ],
        "first_10_round_pairs": [
            {
                "second_round_utc": utc(a[i, 0]),
                "robust_sv": cohlib.r(a[i, 4]),
                "median_change": cohlib.r(a[i, 5]),
            }
            for i in range(min(25, a.shape[0]))
        ],
    }


def change_acf(starts: np.ndarray, vals: list[dict[int, float]]) -> dict[str, Any]:
    """Pooled lag-1 and lag-2 autocorrelation of per-qubit consecutive-round log changes,
    inside each regime window. White scatter around a level gives -0.5 at lag 1 and 0 at
    lag 2; a random walk gives 0 at both; a running average of k independent values gives 0
    at lags 1 to k-1 and -0.5/k-ish structure at lag k."""
    out: dict[str, Any] = {}
    for lab, (a, b) in REGIMES.items():
        lo, hi = ms(a), ms(b) if b else np.inf
        idx = [i for i in range(len(vals)) if lo <= starts[i] < hi]
        per: dict[int, list[float]] = {}
        for i in idx:
            for e, z in vals[i].items():
                per.setdefault(e, []).append(z)
        res = {}
        for lag in (1, 2):
            num = den = 0.0
            for zs in per.values():
                if len(zs) < 6:
                    continue
                d = np.diff(np.array(zs))
                d = d - np.mean(d)
                num += float(np.sum(d[:-lag] * d[lag:]))
                den += float(np.sum(d * d))
            res[f"lag{lag}"] = cohlib.r(num / den) if den > 0 else None
        res["rounds"] = len(idx)
        res["qubits"] = sum(1 for zs in per.values() if len(zs) >= 6)
        out[lab] = res
    return out


def comove_by_regime(
    st1: np.ndarray, v1: list[dict[int, float]], st2: np.ndarray, v2: list[dict[int, float]]
) -> dict[str, Any]:
    """Spearman of same-qubit consecutive-round changes of log T1 and log T2, per regime.
    T2 rounds are matched to the T1 round starting within an hour of them."""
    j2 = {}
    for j, t in enumerate(st2):
        i = int(np.argmin(np.abs(st1 - t)))
        if abs(st1[i] - t) <= 3.6e6:
            j2[i] = j
    out: dict[str, Any] = {"matched_rounds": len(j2)}
    for lab, (a, b) in REGIMES.items():
        lo, hi = ms(a), ms(b) if b else np.inf
        xs, ys = [], []
        for i in range(len(v1) - 1):
            if not (lo <= st1[i] < hi and lo <= st1[i + 1] < hi):
                continue
            if i not in j2 or i + 1 not in j2:
                continue
            a2, b2 = v2[j2[i]], v2[j2[i + 1]]
            for e in set(v1[i]) & set(v1[i + 1]) & set(a2) & set(b2):
                xs.append(v1[i + 1][e] - v1[i][e])
                ys.append(b2[e] - a2[e])
        out[lab] = {
            "changes": len(xs),
            "spearman": cohlib.r(stats.spearmanr(xs, ys).statistic) if len(xs) > 10 else None,
        }
    return out


def window_stats(vals: list[dict[int, float]], lo: int, hi: int) -> dict[int, tuple[float, float]]:
    """Per qubit: median log10 over rounds lo..hi-1 and robust scale of its round changes."""
    per: dict[int, list[float]] = {}
    for v in vals[lo:hi]:
        for e, z in v.items():
            per.setdefault(e, []).append(z)
    out = {}
    for e, zs in per.items():
        if len(zs) >= W - 2:
            z = np.array(zs)
            dz = np.diff(z)
            out[e] = (
                float(np.median(z)),
                float(1.4826 * np.median(np.abs(dz - np.median(dz))) / np.sqrt(2)),
            )
    return out


def boundary_stats(vals: list[dict[int, float]], b: int) -> dict[str, float]:
    pre = window_stats(vals, b - W, b)
    post = window_stats(vals, b, b + W)
    common = sorted(set(pre) & set(post))
    lv0 = np.array([pre[e][0] for e in common])
    lv1 = np.array([post[e][0] for e in common])
    sc0 = np.array([pre[e][1] for e in common])
    sc1 = np.array([post[e][1] for e in common])
    shift = lv1 - lv0
    return {
        "qubits": float(len(common)),
        "median_shift": float(np.median(shift)),
        "share_up": float(np.mean(shift > 0)),
        "spearman_levels": float(stats.spearmanr(lv0, lv1).statistic),
        "median_scale_before": float(np.median(sc0)),
        "median_scale_after": float(np.median(sc1)),
        "median_log10_scale_ratio": float(
            np.median(np.log10(np.maximum(sc1, 1e-6) / np.maximum(sc0, 1e-6)))
        ),
        "spearman_shift_vs_level_before": float(stats.spearmanr(lv0, shift).statistic),
    }


def boundary(starts: np.ndarray, vals: list[dict[int, float]]) -> dict[str, Any]:
    b = int(np.searchsorted(starts, ms(BOUNDARY)))
    at = boundary_stats(vals, b) if b - W >= 0 and b + W <= len(vals) else None
    ref = {}
    for k in range(W, len(vals) - W + 1):
        if abs(k - b) < W:
            continue  # windows overlapping the tested boundary are not reference cases
        for key, v in boundary_stats(vals, k).items():
            ref.setdefault(key, []).append(v)
    out: dict[str, Any] = {
        "boundary_utc": BOUNDARY,
        "rounds_each_side": W,
        "last_round_before_utc": utc(starts[b - 1]),
        "first_round_after_utc": utc(starts[b]),
        "reference_boundaries": len(ref.get("qubits", [])),
    }
    if at is not None:
        out["at_boundary"] = {k: cohlib.r(v) for k, v in at.items()}
        out["reference_quantiles_5_50_95"] = {
            k: [cohlib.r(x) for x in np.quantile(v, (0.05, 0.5, 0.95))] for k, v in ref.items()
        }
        out["boundary_percentile_in_reference"] = {
            k: cohlib.r(float(np.mean(np.array(v) <= at[k]))) for k, v in ref.items()
        }
    return out


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    out = cohlib.header("analysis/coherence/regime.py")
    out["n_files"] = dd.n_files
    out["thresholds"] = {
        "big_round_min_qubits": BIG_ROUND,
        "window_rounds": W,
        "boundary_utc": BOUNDARY,
        "regimes": REGIMES,
    }
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    pairs, _ = cohlib.paired(dd)
    sets = {
        "T1": [(s.entity, s.t_ms, s.y) for s in s1],
        "T2": [(s.entity, s.t_ms, s.y) for s in s2],
        "gamma_phi": [],
    }
    for p in pairs:
        g = cohlib.gamma_phi(p.t1, p.t2)
        ok = g > 0
        sets["gamma_phi"].append((p.entity, p.t_ms[ok], g[ok]))
    st1, v1 = round_table(sets["T1"])
    st2, v2 = round_table(sets["T2"])
    out["t1_t2_change_comovement_by_regime"] = comove_by_regime(st1, v1, st2, v2)
    for name, ser in sets.items():
        starts, vals = round_table(ser)
        out[name] = {
            "big_rounds": len(vals),
            "change_level": change_level(starts, vals),
            "change_acf_by_regime": change_acf(starts, vals),
            "boundary": boundary(starts, vals),
        }
    cohlib.write("regime.json", out)


if __name__ == "__main__":
    main()
