"""Temporal structure of the sx gate error: drift, change points, spikes, value seasonality.

Writes ``results/gates_1q/sx_temporal.json``. Unit: MEASURED events, placeholders masked.

Statistics used (all rank based, because the values are heavy tailed in log space too):

- device series: per round (event stamps split at gaps above 15 minutes, rounds with at least
  half of the series), the median over qubits of ``log10(sx) - qubit median``;
- change points: the rank CUSUM statistic ``K = max_k |sum_{i<=k} (R_i - (n+1)/2)|`` (the
  statistic of Pettitt's test) with a permutation p-value; block permutations keep short-range
  dependence; a significant K means "not exchangeable" (a step OR a slow drift);
- known device-wide dates: per qubit median 14 days before against 14 days after, paired
  Wilcoxon signed-rank over qubits, and a placebo scan over every third day away from them;
- spikes: residual from a running level (median of up to 5 events each side, self excluded)
  above ``log10(2)``;
- value seasonality: that residual grouped by UTC hour bin and weekday of the stamp,
  Kruskal-Wallis with epsilon squared.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import g1common as g

SCRIPT = "analysis/gates_1q/sx_temporal.py"
RNG = np.random.default_rng(20261006)
KNOWN_DATES = {
    "readout length 1560 to 1700 ns, measure.threshold appears": "2026-06-08T18:56:28Z",
    "readout length 1700 to 1660 ns": "2026-07-30T21:09:17Z",
    "measure_2 appears (target 1,600 ops)": "2026-08-07T03:21:59Z",
    "measure_reset, reset_2 appear (target 2,068 ops)": "2026-09-02T04:56:24Z",
    "xslow records return": "2026-09-10T16:56:21Z",
}
WINDOW_D = 14.0
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def cusum_k(r: np.ndarray) -> np.ndarray:
    """Rank CUSUM statistic for each row of a (m, n) rank matrix (or a single vector)."""
    n = r.shape[-1]
    c = np.cumsum(r - (n + 1) / 2.0, axis=-1)
    out: np.ndarray = np.max(np.abs(c[..., :-1]), axis=-1)
    return out


def block_perms(n: int, block: int, m: int) -> np.ndarray:
    """``m`` permutations of range(n) that shuffle contiguous blocks of length ``block``."""
    blocks = [np.arange(i, min(i + block, n)) for i in range(0, n, block)]
    out = np.empty((m, n), dtype=np.int64)
    for k in range(m):
        order = RNG.permutation(len(blocks))
        out[k] = np.concatenate([blocks[i] for i in order])
    return out


def cusum_test(z: np.ndarray, block: int, m: int) -> dict[str, Any]:
    r = stats.rankdata(z)
    k_obs = float(cusum_k(r))
    n = r.size
    c = np.cumsum(r - (n + 1) / 2.0)[:-1]
    split = int(np.argmax(np.abs(c))) + 1
    perm = block_perms(n, block, m) if block > 1 else np.argsort(RNG.random((m, n)), axis=1)
    k_null = cusum_k(r[perm])
    p = (1.0 + float(np.sum(k_null >= k_obs))) / (m + 1.0)
    return {"K": k_obs, "p": p, "split": split}


def device_series(series: list[Any]) -> tuple[np.ndarray, np.ndarray]:
    med = {s.entity: float(np.median(np.log10(s.y))) for s in series}
    stamps = np.concatenate([s.t_ms[1:] for s in series])
    vals = np.concatenate([np.log10(s.y[1:]) - med[s.entity] for s in series])
    starts, rid = g.rounds(stamps)
    sizes = np.bincount(rid)
    keep = np.flatnonzero(sizes >= 0.5 * len(series))
    d = np.array([float(np.median(vals[rid == k])) for k in keep])
    return starts[keep], d


def device_changepoints(t: np.ndarray, d: np.ndarray) -> dict[str, Any]:
    tested: list[dict[str, Any]] = []

    def seg(lo: int, hi: int, depth: int) -> None:
        if hi - lo < 20 or depth > 3:
            return
        res = cusum_test(d[lo:hi], block=7, m=2000)
        cut = lo + res["split"]
        row = {
            "segment": [g.iso(t[lo]), g.iso(t[hi - 1])],
            "rounds": hi - lo,
            "K": round(res["K"], 1),
            "p_block7": round(res["p"], 4),
            "split_round_start": g.iso(t[cut]),
            "median_before_log10": g.rnd(float(np.median(d[lo:cut])), 4),
            "median_after_log10": g.rnd(float(np.median(d[cut:hi])), 4),
        }
        tested.append(row)
        if res["p"] < 0.01:
            seg(lo, cut, depth + 1)
            seg(cut, hi, depth + 1)

    seg(0, d.size, 0)
    days = (t - t[0]) / g.DAY_MS
    ts = g.theil_sen(days / 30.0, d)
    return {
        "rounds": int(d.size),
        "first": g.iso(t[0]),
        "last": g.iso(t[-1]),
        "device_round_median_q": g.q(d, nd=4),
        "theil_sen_slope_log10_per_30_days": ts,
        "spearman_vs_time": g.spearman(days, d),
        "binary_segmentation": {
            "rule": "rank CUSUM, block permutations of 7 rounds (2000), recurse while p < 0.01, "
            "min 20 rounds, depth <= 3",
            "tests": tested,
            "n_tests": len(tested),
        },
    }


def known_dates(series: list[Any]) -> dict[str, Any]:
    def test_at(t0: float) -> dict[str, Any]:
        before, after = [], []
        w = WINDOW_D * g.DAY_MS
        for s in series:
            z = np.log10(s.y)
            a = z[(s.t_ms >= t0 - w) & (s.t_ms < t0)]
            b = z[(s.t_ms >= t0) & (s.t_ms < t0 + w)]
            if a.size >= 3 and b.size >= 3:
                before.append(float(np.median(a)))
                after.append(float(np.median(b)))
        x, y = np.array(before), np.array(after)
        if x.size < 10:
            return {"n": int(x.size), "p": None}
        r = stats.wilcoxon(y - x)
        return {
            "n": int(x.size),
            "median_shift_log10": g.rnd(float(np.median(y - x)), 4),
            "share_up": g.rnd(float(np.mean(y > x)), 3),
            "p": float(f"{float(r.pvalue):.3g}"),
        }

    out: dict[str, Any] = {}
    known_ms = []
    for label, iso in KNOWN_DATES.items():
        t0 = g.ms_of(iso)
        known_ms.append(t0)
        out[label] = {"date": iso, **test_at(t0)}
    t_first = min(float(s.t_ms[0]) for s in series) + WINDOW_D * g.DAY_MS
    t_last = max(float(s.t_ms[-1]) for s in series) - WINDOW_D * g.DAY_MS
    grid = np.arange(t_first, t_last, g.DAY_MS)
    placebo: dict[str, Any] = {}
    for label, excl_d in (("far_14d", WINDOW_D), ("near_3d", 3.0)):
        far = [t for t in grid if min(abs(t - k) for k in known_ms) > excl_d * g.DAY_MS]
        res = [test_at(float(t)) for t in far]
        ps = np.array([r["p"] for r in res if r["p"] is not None])
        placebo[label] = {
            "rule": f"daily grid, more than {excl_d:g} days from every known date "
            "(windows overlap, so the dates are not independent)",
            "dates_tested": int(ps.size),
            "share_p_below_0.01": g.rnd(float(np.mean(ps < 0.01)), 3),
            "share_p_below_0.05": g.rnd(float(np.mean(ps < 0.05)), 3),
            "abs_median_shift_log10_q": g.q(
                [abs(r["median_shift_log10"]) for r in res if r["p"] is not None], nd=4
            ),
        }
    return {
        "window_days_each_side": WINDOW_D,
        "min_events_each_side": 3,
        "bonferroni_alpha_for_5_dates": 0.01,
        "dates": out,
        "placebo": placebo,
    }


def entity_changepoints(series: list[Any]) -> dict[str, Any]:
    rows = []
    for s in series:
        z = np.log10(s.y)
        iid = cusum_test(z, block=1, m=999)
        blk = cusum_test(z, block=5, m=999)
        cut = iid["split"]
        rows.append(
            {
                "q": s.entity,
                "n": int(z.size),
                "p_iid": iid["p"],
                "p_block5": blk["p"],
                "date": float(s.t_ms[cut]),
                "shift": float(np.median(z[cut:]) - np.median(z[:cut])),
            }
        )
    p_iid = np.array([r["p_iid"] for r in rows])
    p_blk = np.array([r["p_block5"] for r in rows])
    rej_iid = g.bh(p_iid, 0.05)
    rej_blk = g.bh(p_blk, 0.05)
    shift = np.array([r["shift"] for r in rows])
    dates = np.array([r["date"] for r in rows])
    months = np.array(g.month_of(dates))
    by_month = {m: int(np.sum(rej_blk & (months == m))) for m in sorted(set(months.tolist()))}
    near_known = {}
    for label, iso in KNOWN_DATES.items():
        t0 = g.ms_of(iso)
        near_known[label] = int(np.sum(rej_blk & (np.abs(dates - t0) <= 3 * g.DAY_MS)))
    span_d = float(
        (max(float(s.t_ms[-1]) for s in series) - min(float(s.t_ms[0]) for s in series)) / g.DAY_MS
    )
    expected_near = float(rej_blk.sum()) * 6.0 / span_d
    return {
        "entities": len(rows),
        "permutations": 999,
        "min_attainable_p": 0.001,
        "bh_fdr": 0.05,
        "significant_iid": int(rej_iid.sum()),
        "significant_block5": int(rej_blk.sum()),
        "abs_shift_log10_significant_block5_q": g.q(np.abs(shift[rej_blk]), nd=4),
        "share_up_among_significant_block5": g.rnd(float(np.mean(shift[rej_blk] > 0)), 3)
        if rej_blk.any()
        else None,
        "abs_shift_log10_all_q": g.q(np.abs(shift), nd=4),
        "split_month_of_significant_block5": by_month,
        "significant_block5_within_3_days_of_known_date": near_known,
        "expected_within_any_one_6_day_window_if_uniform": g.rnd(expected_near, 3),
        "record_span_days": g.rnd(span_d, 1),
        "largest_shifts_significant_block5": [
            {
                "qubit": int(rows[i]["q"]),
                "date": g.iso(rows[i]["date"]),
                "shift_log10": g.rnd(rows[i]["shift"], 3),
                "p_block5": rows[i]["p_block5"],
            }
            for i in np.argsort(-np.abs(shift))
            if rej_blk[i]
        ][:10],
    }


def spikes(series: list[Any]) -> dict[str, Any]:
    per_entity, per_entity_down, lengths = [], [], []
    t_all, up_all = [], []
    for s in series:
        z = np.log10(s.y)
        r = z - g.running_level(z)
        ok = np.isfinite(r)
        up = ok & (r > g.LOG10_2)
        down = ok & (r < -g.LOG10_2)
        per_entity.append(int(up.sum()))
        per_entity_down.append(int(down.sum()))
        k = 0
        while k < up.size:
            if up[k]:
                j = k
                while j + 1 < up.size and up[j + 1]:
                    j += 1
                lengths.append(j - k + 1)
                k = j + 1
            else:
                k += 1
        t_all.append(s.t_ms[ok])
        up_all.append(up[ok])
    pe = np.array(per_entity)
    srt = np.sort(pe)[::-1]
    top10 = int(np.ceil(0.1 * pe.size))
    at = np.concatenate(t_all)
    ua = np.concatenate(up_all)
    months = np.array(g.month_of(at))
    rate_by_month = {
        m: {
            "events": int(np.sum(months == m)),
            "spike_rate": g.rnd(float(ua[months == m].mean()), 5),
        }
        for m in sorted(set(months.tolist()))
    }
    _, rid = g.rounds(at)
    sizes = np.bincount(rid)
    big = np.flatnonzero(sizes >= 0.5 * len(series))
    counts = np.bincount(rid, weights=ua.astype(np.float64), minlength=sizes.size)[big]
    p_rate = float(ua.mean())
    exp_var = float(np.mean(sizes[big] * p_rate * (1 - p_rate)))
    return {
        "definition": "residual from running level (median of up to 5 events each side, self "
        "excluded) above log10(2); downward spike below -log10(2)",
        "events_with_level": int(at.size),
        "spikes_up": int(pe.sum()),
        "spikes_down": int(np.sum(per_entity_down)),
        "spike_up_rate": g.rnd(p_rate, 5),
        "entities_with_any_spike": int(np.sum(pe > 0)),
        "spikes_per_entity_q": g.q(pe.astype(np.float64), nd=1),
        "share_of_spikes_in_top_10pct_entities": g.rnd(float(srt[:top10].sum() / pe.sum()), 3),
        "top_entities": [
            {"qubit": int(series[i].entity), "spikes": int(pe[i]), "events": int(series[i].y.size)}
            for i in np.argsort(-pe)[:8]
        ],
        "episode_length_events_counts": {
            str(k): int(v) for k, v in zip(*np.unique(lengths, return_counts=True), strict=True)
        },
        "episodes": len(lengths),
        "share_of_episodes_single_event": g.rnd(float(np.mean(np.array(lengths) == 1)), 4),
        "rate_by_month": rate_by_month,
        "per_round": {
            "rounds_with_ge_half_device": int(big.size),
            "spikes_per_round_q": g.q(counts, nd=1),
            "mean": g.rnd(float(counts.mean()), 3),
            "variance": g.rnd(float(counts.var()), 3),
            "binomial_variance_if_independent": g.rnd(exp_var, 3),
            "max": int(counts.max()),
            "rounds_with_ge_5_spikes": int(np.sum(counts >= 5)),
        },
    }


def seasonality(series: list[Any]) -> dict[str, Any]:
    r_all, h_all, w_all = [], [], []
    for s in series:
        z = np.log10(s.y)
        r = z - g.running_level(z)
        ok = np.isfinite(r)
        r_all.append(r[ok])
        h_all.append(((s.t_ms[ok] / g.HOUR_MS) % 24).astype(np.int64) // 3)
        w_all.append(
            np.array([datetime.fromtimestamp(t / 1000, tz=UTC).weekday() for t in s.t_ms[ok]])
        )
    r = np.concatenate(r_all)
    hb = np.concatenate(h_all)
    wd = np.concatenate(w_all)
    hour_groups = [r[hb == k] for k in range(8)]
    wd_groups = [r[wd == k] for k in range(7)]
    up = (r > g.LOG10_2).astype(np.float64)
    return {
        "residual": "log10 value minus running level (5 each side, self excluded)",
        "by_utc_hour_bin_3h": {
            "kruskal": g.kruskal(hour_groups),
            "median_residual": [g.rnd(float(np.median(x)), 4) for x in hour_groups],
            "n": [int(x.size) for x in hour_groups],
            "spike_rate": [g.rnd(float(up[hb == k].mean()), 4) for k in range(8)],
        },
        "by_weekday": {
            "kruskal": g.kruskal(wd_groups),
            "median_residual": dict(
                zip(WEEKDAYS, [g.rnd(float(np.median(x)), 4) for x in wd_groups], strict=True)
            ),
            "n": dict(zip(WEEKDAYS, [int(x.size) for x in wd_groups], strict=True)),
            "spike_rate": dict(
                zip(WEEKDAYS, [g.rnd(float(up[wd == k].mean()), 4) for k in range(7)], strict=True)
            ),
        },
        "spike_rate_by_hour_bin_chi2": chi2(up, hb, 8),
        "spike_rate_by_weekday_chi2": chi2(up, wd, 7),
    }


def chi2(up: np.ndarray, grp: np.ndarray, k: int) -> dict[str, Any]:
    table = np.array(
        [[np.sum((grp == i) & (up == 1)), np.sum((grp == i) & (up == 0))] for i in range(k)]
    )
    r = stats.chi2_contingency(table)
    return {"chi2": g.rnd(float(r.statistic), 2), "dof": int(r.dof), "p": float(f"{r.pvalue:.3g}")}


def main() -> int:
    dd = ddload.DD()
    series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["field"] = g.SX_FIELD
    t, d = device_series(series)
    payload["device"] = device_changepoints(t, d)
    payload["known_dates"] = known_dates(series)
    payload["entity_changepoints"] = entity_changepoints(series)
    payload["spikes"] = spikes(series)
    payload["seasonality"] = seasonality(series)
    payload["tests_in_this_file"] = (
        "device binary segmentation (n_tests listed), 5 known dates (Bonferroni 0.01) plus the "
        "placebo scan, 155 per-entity CUSUM tests x 2 null types (BH 0.05 each), 2 Kruskal-Wallis "
        "and 2 chi-square seasonality tests"
    )
    ddload.write_json(g.RESULTS / "sx_temporal.json", payload)
    print("wrote", g.RESULTS / "sx_temporal.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
