"""Profiles of T1, T2 and the derived rates: records, events, distributions, cadence, rounds.

Writes ``results/coherence/profile.json``. Unit of the distributions: the re-measurement
event (MEASURED rule), never the file record, because a value repeats in every file until
it is re-measured. Derived quantities that need both times use the paired events of
``cohlib.paired`` (a T2 event with a T1 stamped within ``SYNC_WINDOW_H``).
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

QS_FINE = (0.0, 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999, 1.0)
HALF_DEVICE = 78
STALE_H = 72.0


def utc(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_shape(x: np.ndarray) -> dict[str, Any]:
    x = x[np.isfinite(x) & (x > 0)]
    z = np.log10(x)
    q1, q2, q3 = np.quantile(z, (0.25, 0.5, 0.75))
    return {
        "n": int(z.size),
        "quantiles_linear": cohlib.q(x, QS_FINE),
        "quantile_levels": list(QS_FINE),
        "log10_mean": cohlib.r(np.mean(z)),
        "log10_median": cohlib.r(q2),
        "log10_std": cohlib.r(np.std(z, ddof=1)),
        "log10_mad_scaled": cohlib.r(1.4826 * np.median(np.abs(z - q2))),
        "log10_skew": cohlib.r(stats.skew(z)),
        "log10_excess_kurtosis": cohlib.r(stats.kurtosis(z)),
        "log10_bowley_skew": cohlib.r((q3 + q1 - 2 * q2) / (q3 - q1)),
        "median_over_p1": cohlib.r(np.median(x) / np.quantile(x, 0.01)),
        "p99_over_median": cohlib.r(np.quantile(x, 0.99) / np.median(x)),
    }


def variance_split(series: list[tuple[int, np.ndarray]]) -> dict[str, Any]:
    """Share of the pooled variance of log10 values that lies between qubit means."""
    allz = np.concatenate([np.log10(y[y > 0]) for _, y in series])
    means = np.array([np.mean(np.log10(y[y > 0])) for _, y in series])
    sizes = np.array([int(np.sum(y > 0)) for _, y in series])
    grand = np.mean(allz)
    between = float(np.sum(sizes * (means - grand) ** 2) / allz.size)
    total = float(np.var(allz))
    return {
        "series": len(series),
        "values": int(allz.size),
        "total_var_log10": cohlib.r(total),
        "between_qubit_var_log10": cohlib.r(between),
        "between_share": cohlib.r(between / total),
    }


def missing_runs(present: np.ndarray, stems: list[str]) -> list[dict[str, Any]]:
    miss = np.flatnonzero(~present)
    runs: list[dict[str, Any]] = []
    if miss.size == 0:
        return runs
    start = prev = int(miss[0])
    for i in miss[1:]:
        i = int(i)
        if i != prev + 1:
            runs.append({"first": stems[start], "last": stems[prev], "files": prev - start + 1})
            start = i
        prev = i
    runs.append({"first": stems[start], "last": stems[prev], "files": prev - start + 1})
    return runs


def cadence(series: list[Any]) -> dict[str, Any]:
    gaps_all, gaps_p1, gaps_p2 = [], [], []
    for s in series:
        g = np.diff(s.t_ms) / ddload.MS_PER_HOUR
        later = s.t_ms[1:]
        gaps_all.append(g)
        gaps_p1.append(g[later < cohlib.PERIOD_SPLIT_MS])
        gaps_p2.append(g[later >= cohlib.PERIOD_SPLIT_MS])
    out = {
        "gap_h_quantiles": cohlib.q(np.concatenate(gaps_all)),
        "gap_h_quantiles_before_split": cohlib.q(np.concatenate(gaps_p1)),
        "gap_h_quantiles_after_split": cohlib.q(np.concatenate(gaps_p2)),
        "gaps_before_split": int(sum(x.size for x in gaps_p1)),
        "gaps_after_split": int(sum(x.size for x in gaps_p2)),
        "quantile_levels": [0.0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0],
    }
    # Events per qubit per 30 days, by calendar month of the event stamp (series starts
    # excluded: the first event's stamp predates the archive).
    months: dict[str, list[float]] = {}
    for s in series:
        t = s.t_ms[1:]
        lab = [datetime.fromtimestamp(x / 1000.0, UTC).strftime("%Y-%m") for x in t]
        for m in sorted(set(lab)):
            months.setdefault(m, []).append(float(lab.count(m)))
    out["events_per_qubit_by_month_median"] = {
        m: cohlib.r(np.median(v)) for m, v in sorted(months.items())
    }
    return out


def round_profile(series: list[Any]) -> dict[str, Any]:
    stamps = np.concatenate([s.t_ms[1:] for s in series])
    ents = np.concatenate([np.full(s.t_ms.size - 1, s.entity) for s in series])
    starts, rid = cohlib.rounds(stamps)
    n_r = starts.size
    size = np.array([np.unique(ents[rid == k]).size for k in range(n_r)])
    dur = np.array(
        [(stamps[rid == k].max() - stamps[rid == k].min()) / 60000.0 for k in range(n_r)]
    )
    big = size >= HALF_DEVICE
    hours = np.array([datetime.fromtimestamp(x / 1000.0, UTC).hour for x in starts])
    wday = np.array([datetime.fromtimestamp(x / 1000.0, UTC).weekday() for x in starts])
    big_starts = starts[big]
    gaps = np.diff(big_starts) / ddload.MS_PER_HOUR
    ev_hours = np.array([datetime.fromtimestamp(x / 1000.0, UTC).hour for x in stamps])
    return {
        "events_used": int(stamps.size),
        "rounds": int(n_r),
        "rounds_half_device_or_more": int(big.sum()),
        "events_in_half_device_rounds_share": cohlib.r(np.isin(rid, np.flatnonzero(big)).mean()),
        "round_size_quantiles": cohlib.q(size.astype(float)),
        "round_duration_min_quantiles_big": cohlib.q(dur[big]),
        "big_round_start_hour_utc_counts": np.bincount(hours[big], minlength=24).tolist(),
        "big_round_weekday_counts_mon_first": np.bincount(wday[big], minlength=7).tolist(),
        "gap_between_big_rounds_h_quantiles": cohlib.q(gaps),
        "gap_between_big_rounds_h_quantiles_before_split": cohlib.q(
            gaps[big_starts[1:] < cohlib.PERIOD_SPLIT_MS]
        ),
        "gap_between_big_rounds_h_quantiles_after_split": cohlib.q(
            gaps[big_starts[1:] >= cohlib.PERIOD_SPLIT_MS]
        ),
        "event_stamp_hour_utc_counts": np.bincount(ev_hours, minlength=24).tolist(),
        "first_big_round_utc": utc(float(big_starts[0])),
        "last_big_round_utc": utc(float(big_starts[-1])),
    }


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    out = cohlib.header("analysis/coherence/profile.py")
    out["n_files"] = dd.n_files
    t1v = np.array(dd.v("q.T1"), dtype=np.float64)
    t2v = np.array(dd.v("q.T2"), dtype=np.float64)
    t1d = np.array(dd.d("q.T1"), dtype=np.float64)
    t2d = np.array(dd.d("q.T2"), dtype=np.float64)

    # ---- records and missingness
    rec: dict[str, Any] = {}
    for name, v in (("T1", t1v), ("T2", t2v)):
        pres = np.isfinite(v)
        miss_q = {
            int(e): int((~pres[:, e]).sum()) for e in range(v.shape[1]) if (~pres[:, e]).any()
        }
        rec[name] = {
            "records": int(pres.sum()),
            "cells": int(pres.size),
            "missing_by_qubit": miss_q,
            "min_value": cohlib.r(np.nanmin(v)),
            "max_value": cohlib.r(np.nanmax(v)),
        }
    rec["T1"]["q72_missing_runs"] = missing_runs(np.isfinite(t1v[:, 72]), dd.stems)
    both = np.isfinite(t1v) & np.isfinite(t2v)
    off_rec_h = (t2d - t1d)[both] / ddload.MS_PER_HOUR
    rec["stamp_offset_T2_minus_T1_records"] = {
        "records_with_both": int(both.sum()),
        "identical_stamp": int(np.sum(off_rec_h == 0)),
        "t2_before_t1": int(np.sum(off_rec_h < 0)),
        "within_10s": cohlib.r(np.mean(np.abs(off_rec_h) * 3600 <= 10)),
        "within_60s": cohlib.r(np.mean(np.abs(off_rec_h) * 3600 <= 60)),
        "within_1h": cohlib.r(np.mean(np.abs(off_rec_h) <= 1)),
        "within_24h": cohlib.r(np.mean(np.abs(off_rec_h) <= 24)),
        "offset_s_quantiles": cohlib.q(off_rec_h * 3600.0),
    }
    # Staleness: the age of the value at each file (file date minus stamp). A value older
    # than STALE_H was carried forward without re-measurement for at least three rounds.
    fms = dd.file_ms[:, None]
    stale: dict[str, Any] = {"stale_h": STALE_H}
    for name, d in (("T1", t1d), ("T2", t2d)):
        age = (fms - d) / ddload.MS_PER_HOUR
        rows = []
        for e in range(age.shape[1]):
            a = age[:, e]
            ok = np.isfinite(a)
            if not ok.any():
                continue
            st = (a > STALE_H) & ok
            if st.sum() == 0:
                continue
            rows.append(
                {
                    "qubit": e,
                    "stale_files": int(st.sum()),
                    "present_files": int(ok.sum()),
                    "max_age_h": cohlib.r(np.nanmax(a)),
                    "last_stale_file": dd.stems[int(np.flatnonzero(st)[-1])],
                }
            )
        rows.sort(key=lambda x: -x["stale_files"])
        stale[name] = {
            "qubits_ever_stale": len(rows),
            "stale_records": int(sum(x["stale_files"] for x in rows)),
            "age_h_quantiles_all_records": cohlib.q(age[np.isfinite(age)]),
            "worst": rows[:6],
        }
    rec["staleness"] = stale
    rat_rec = (t2v / t1v)[both]
    rec["T2_gt_2T1_records"] = {
        "count": int(np.sum(rat_rec > 2.0)),
        "share": cohlib.r(np.mean(rat_rec > 2.0)),
        "qubits": int(np.sum(np.any((t2v > 2 * t1v) & both, axis=0))),
    }
    out["records"] = rec

    # ---- events
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    ev: dict[str, Any] = {}
    for name, ss in (("T1", s1), ("T2", s2)):
        n_ev = np.array([s.y.size for s in ss])
        ev[name] = {
            "series": len(ss),
            "events": int(n_ev.sum()),
            "events_per_qubit_quantiles": cohlib.q(n_ev.astype(float)),
            "distribution": log_shape(np.concatenate([s.y for s in ss])),
            "variance_split": variance_split([(s.entity, s.y) for s in ss if s.y.size >= 10]),
            "cadence": cadence(ss),
            "rounds": round_profile(ss),
        }
    # T1 events with a T2 event of the same qubit within the window, and the converse.
    by_e2 = {s.entity: s.t_ms for s in s2}
    by_e1 = {s.entity: s.t_ms for s in s1}
    w = cohlib.SYNC_WINDOW_H * ddload.MS_PER_HOUR
    lone1 = tot1 = lone2 = tot2 = 0
    for s in s1:
        t2s = by_e2.get(s.entity)
        for t in s.t_ms[1:]:
            tot1 += 1
            if t2s is None or np.min(np.abs(t2s - t)) > w:
                lone1 += 1
    for s in s2:
        t1s = by_e1.get(s.entity)
        for t in s.t_ms[1:]:
            tot2 += 1
            if t1s is None or np.min(np.abs(t1s - t)) > w:
                lone2 += 1
    ev["co_measurement"] = {
        "t1_events_excl_first": tot1,
        "t1_events_without_t2_event_in_window": lone1,
        "t2_events_excl_first": tot2,
        "t2_events_without_t1_event_in_window": lone2,
    }
    out["events"] = ev

    # ---- paired events and derived quantities
    pairs, pc = cohlib.paired(dd)
    t1 = np.concatenate([p.t1 for p in pairs])
    t2 = np.concatenate([p.t2 for p in pairs])
    off = np.concatenate([p.offset_s for p in pairs])
    s = t2 / (2.0 * t1)
    gphi = cohlib.gamma_phi(t1, t2)
    # Unpaired T2 events by qubit (a T1 record exists but is stamped outside the window).
    t2_by_q = {x.entity: x.y.size for x in s2}
    paired_by_q = {p.entity: p.t1.size for p in pairs}
    unpaired = sorted(
        (
            (e, n - paired_by_q.get(e, 0))
            for e, n in t2_by_q.items()
            if n - paired_by_q.get(e, 0) > 0
        ),
        key=lambda x: -x[1],
    )
    der: dict[str, Any] = {
        "pairing_counts": pc,
        "unpaired_by_qubit_top": [{"qubit": e, "unpaired": n} for e, n in unpaired[:8]],
        "unpaired_qubits": len(unpaired),
        "paired_qubits": len(pairs),
        "pair_offset_s_quantiles": cohlib.q(off),
        "pair_offset_within_10s_share": cohlib.r(np.mean(np.abs(off) <= 10)),
        "pair_t2_before_t1": int(np.sum(off < 0)),
        "rate_1_over_T1_per_ms": log_shape(1000.0 / np.concatenate([x.y for x in s1])),
        "T2_over_T1_quantiles": cohlib.q(t2 / t1, QS_FINE),
        "s_T2_over_2T1_quantiles": cohlib.q(s, QS_FINE),
        "quantile_levels": list(QS_FINE),
        "s_bins": [0.0, 0.25, 0.5, 0.75, 0.9, 1.0, 1e9],
        "s_bin_counts": np.histogram(s, bins=[0.0, 0.25, 0.5, 0.75, 0.9, 1.0, 1e9])[0].tolist(),
        "gamma_phi_nonpositive": int(np.sum(gphi <= 0)),
        "gamma_phi_exactly_zero": int(np.sum(gphi == 0)),
        "gamma_phi_per_ms": log_shape(gphi[gphi > 0] * 1000.0),
        "T_phi_us_quantiles": cohlib.q(1.0 / gphi[gphi > 0], QS_FINE),
        "gamma_adr027_T1_events": log_shape(cohlib.adr027_gamma(np.concatenate([x.y for x in s1]))),
        "lambda_adr027_paired": log_shape(cohlib.adr027_lambda(t1, t2)),
        "lambda_rejected_T2_gt_2T1": int(np.sum(t2 > 2 * t1)),
    }
    # Variance split of the derived quantities over paired series.
    der["variance_split_gamma_phi"] = variance_split(
        [(p.entity, cohlib.gamma_phi(p.t1, p.t2)) for p in pairs if p.t1.size >= 10]
    )
    der["variance_split_s"] = variance_split(
        [(p.entity, p.t2 / (2 * p.t1)) for p in pairs if p.t1.size >= 10]
    )

    # ---- T2 > 2 T1 at the paired-event level: concentration and which side moved
    per_q = []
    dev1_all, dev2_all, flag_all = [], [], []
    for p in pairs:
        f = p.t2 > 2.0 * p.t1
        per_q.append((p.entity, int(f.sum()), int(f.size)))
        z1, z2 = np.log10(p.t1), np.log10(p.t2)
        dev1_all.append(z1 - cohlib.rolling_level(z1))
        dev2_all.append(z2 - cohlib.rolling_level(z2))
        flag_all.append(f)
    cnt = np.array([c for _, c, _ in per_q])
    order = np.argsort(-cnt)
    top10 = round(0.1 * len(per_q))
    d1 = np.concatenate(dev1_all)
    d2 = np.concatenate(dev2_all)
    fl = np.concatenate(flag_all)
    der["T2_gt_2T1_events"] = {
        "events": int(cnt.sum()),
        "share_of_paired": cohlib.r(cnt.sum() / sum(n for _, _, n in per_q)),
        "qubits_with_any": int(np.sum(cnt > 0)),
        "top_qubits": [
            {"qubit": per_q[i][0], "count": per_q[i][1], "paired_events": per_q[i][2]}
            for i in order[:8]
        ],
        "share_in_top_10pct_qubits": cohlib.r(cnt[order[:top10]].sum() / max(cnt.sum(), 1)),
        "top_10pct_qubit_count": top10,
        "s_quantiles_when_flagged": cohlib.q(s[s > 1.0]),
        "t1_dev_median_when_flagged": cohlib.r(np.nanmedian(d1[fl])),
        "t2_dev_median_when_flagged": cohlib.r(np.nanmedian(d2[fl])),
        "t1_dev_median_otherwise": cohlib.r(np.nanmedian(d1[~fl])),
        "t2_dev_median_otherwise": cohlib.r(np.nanmedian(d2[~fl])),
        "flagged_with_t1_dev_below_0": cohlib.r(np.nanmean(d1[fl] < 0)),
        "flagged_with_t2_dev_above_0": cohlib.r(np.nanmean(d2[fl] > 0)),
        "flagged_with_finite_devs": int(np.sum(fl & np.isfinite(d1) & np.isfinite(d2))),
        "deviation_note": (
            "log10 deviations from each field's centred running median over the paired series"
        ),
    }
    out["derived"] = der

    # ---- q72
    s72 = next(x for x in s1 if x.entity == 72)
    g = np.diff(s72.t_ms) / ddload.MS_PER_HOUR
    k = int(np.argmax(g))
    dev_med = float(np.median([np.median(x.y) for x in s1 if x.entity != 72]))
    out["q72"] = {
        "t1_events": int(s72.y.size),
        "t1_event_stamps_utc": [utc(float(x)) for x in s72.t_ms],
        "t1_values_us": [cohlib.r(x, 5) for x in s72.y],
        "max_gap_h": cohlib.r(g[k]),
        "max_gap_from_utc": utc(float(s72.t_ms[k])),
        "max_gap_to_utc": utc(float(s72.t_ms[k + 1])),
        "median_t1_us": cohlib.r(np.median(s72.y)),
        "median_of_other_qubit_medians_us": cohlib.r(dev_med),
        "t2_records": int(np.isfinite(t2v[:, 72]).sum()),
    }
    cohlib.write("profile.json", out)


if __name__ == "__main__":
    main()
