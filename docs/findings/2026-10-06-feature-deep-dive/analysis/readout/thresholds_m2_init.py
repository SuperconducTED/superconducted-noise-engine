"""Discriminator thresholds, the ``measure_2`` instruction, and ``init_error``.

Writes ``results/readout/thresholds_m2_init.json``.

Thresholds are value-only fields (assembly-stamped), so a threshold change is located only
between two consecutive files; the coincidence with readout re-measurement is therefore
tested at the session level: does a readout session start between the previous file's
``last_update_date`` and this one's? ``ddload.placeholder_error`` is NOT applied to
thresholds: their values are signed numbers of order 1e7, and ``>= 1`` is not a placeholder.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc

TH_FIELDS = (
    "g1.measure.threshold",
    "g1.measure_reset.threshold",
    "g1.measure_2.threshold",
    "g1.measure_reset_2.threshold",
)


def change_files(v: np.ndarray) -> np.ndarray:
    chg = np.zeros(v.shape[0], dtype=bool)
    both = np.isfinite(v[1:]) & np.isfinite(v[:-1])
    chg[1:] = np.any((v[1:] != v[:-1]) & both, axis=1)
    return chg


def thresholds(dd: ddload.DD, s: rc.Sessions) -> dict[str, Any]:
    out: dict[str, Any] = {}
    vals = {f: np.array(dd.v(f), dtype=np.float64) for f in TH_FIELDS}
    for f, v in vals.items():
        x = v[np.isfinite(v)]
        first = int(np.flatnonzero(np.isfinite(v).any(axis=1))[0])
        chg = change_files(v)
        both = np.isfinite(v[1:]) & np.isfinite(v[:-1])
        per_file = np.where(chg[1:], np.sum((v[1:] != v[:-1]) & both, axis=1), 0)
        med_abs = np.nanmedian(np.abs(v), axis=0)
        sd_rel = np.nanstd(v, axis=0) / med_abs
        out[f] = {
            "first_file": dd.stems[first][:15],
            "records": int(x.size),
            "value_q": rc.quantiles(x),
            "share_negative": round(float(np.mean(x < 0)), 4),
            "qubits_always_negative": int(np.sum(np.nanmax(v, axis=0) < 0)),
            "qubits_always_positive": int(np.sum(np.nanmin(v, axis=0) > 0)),
            "qubits_changing_sign": int(
                np.sum((np.nanmax(v, axis=0) > 0) & (np.nanmin(v, axis=0) < 0))
            ),
            "per_qubit_median_abs_q": rc.quantiles(med_abs),
            "per_qubit_sd_over_median_abs_q": rc.quantiles(sd_rel),
            "change_files": int(chg.sum()),
            "qubits_changed_in_a_change_file_q": rc.quantiles(per_file[per_file > 0]),
            "change_files_all_156": int(np.sum(per_file == 156)),
            "value_changes_per_qubit_q": rc.quantiles(
                np.array([np.sum(np.diff(c[np.isfinite(c)]) != 0) for c in v.T], dtype=np.float64)
            ),
        }
    for a, b in (
        ("g1.measure.threshold", "g1.measure_reset.threshold"),
        ("g1.measure_2.threshold", "g1.measure_reset_2.threshold"),
    ):
        ok = np.isfinite(vals[a]) & np.isfinite(vals[b])
        out[f"{a}_eq_{b}"] = {
            "compared": int(ok.sum()),
            "mismatch": int(np.sum(vals[a][ok] != vals[b][ok])),
        }
    m, m2 = vals["g1.measure.threshold"], vals["g1.measure_2.threshold"]
    ok = np.isfinite(m) & np.isfinite(m2)
    cm, cm2 = change_files(m), change_files(m2)
    life2 = np.isfinite(m2).any(axis=1)
    life2[np.flatnonzero(life2)[0]] = False
    med_m = np.nanmedian(np.where(ok, m, np.nan), axis=0)
    med_m2 = np.nanmedian(np.where(ok, m2, np.nan), axis=0)
    out["measure_vs_measure_2"] = {
        "files_in_measure_2_lifetime": int(life2.sum()),
        "measure_changes_there": int(np.sum(cm & life2)),
        "measure_2_changes_there": int(np.sum(cm2 & life2)),
        "both_change_same_file": int(np.sum(cm & cm2 & life2)),
        "per_qubit_median_ratio_m2_over_m_q": rc.quantiles(med_m2 / med_m),
        "spearman_per_qubit_medians": rc.spearman(med_m, med_m2),
        "same_sign_share_records": round(float(np.mean(np.sign(m[ok]) == np.sign(m2[ok]))), 4),
    }
    # Session-level coincidence of measure.threshold changes with readout sessions.
    fm = dd.file_ms
    first = int(np.flatnonzero(np.isfinite(m).any(axis=1))[0])
    rows_i = np.arange(first + 1, m.shape[0])
    has_any = np.zeros(m.shape[0], dtype=bool)
    has_even = np.zeros(m.shape[0], dtype=bool)
    has_mixed = np.zeros(m.shape[0], dtype=bool)
    for i in rows_i:
        sel = (s.start_ms > fm[i - 1]) & (s.start_ms <= fm[i]) & (s.kind != "small")
        has_any[i] = sel.any()
        has_even[i] = np.any(sel & (s.kind == "even"))
        has_mixed[i] = np.any(sel & (s.kind == "mixed"))
    chg = cm
    hist = ~np.array(dd.file("has_configuration")).astype(bool)

    def tab(mask: np.ndarray) -> dict[str, int]:
        r_ = mask.copy()
        r_[: first + 1] = False
        return {
            "files": int(r_.sum()),
            "change_and_session": int(np.sum(r_ & chg & has_any)),
            "change_no_session": int(np.sum(r_ & chg & ~has_any)),
            "session_no_change": int(np.sum(r_ & ~chg & has_any)),
            "neither": int(np.sum(r_ & ~chg & ~has_any)),
            "change_with_even_session": int(np.sum(r_ & chg & has_even)),
            "change_with_mixed_only": int(np.sum(r_ & chg & has_mixed & ~has_even)),
            "even_session_no_change": int(np.sum(r_ & ~chg & has_even)),
            "mixed_only_session_no_change": int(np.sum(r_ & ~chg & has_mixed & ~has_even)),
        }

    out["threshold_change_vs_readout_session"] = {
        "all_files": tab(np.ones(m.shape[0], dtype=bool)),
        "live_files": tab(~hist),
        "historical_files": tab(hist),
    }
    # Sessions per kind that are followed (in their interval file) by a threshold change.
    kinds_cnt: dict[str, list[int]] = {"even": [0, 0], "mixed": [0, 0]}
    for k in range(s.start_ms.size):
        if s.kind[k] == "small" or s.start_ms[k] <= fm[first]:
            continue
        i = int(np.searchsorted(fm, s.start_ms[k], side="left"))
        if i >= fm.size:
            continue
        kinds_cnt[str(s.kind[k])][1] += 1
        kinds_cnt[str(s.kind[k])][0] += int(chg[i])
    out["sessions_whose_interval_file_changes_threshold"] = {
        k: {"with_change": v[0], "sessions": v[1]} for k, v in kinds_cnt.items()
    }
    return out


def measure_2(dd: ddload.DD, r: rc.Readout, s: rc.Sessions) -> dict[str, Any]:
    v = np.array(dd.v("g1.measure_2.gate_error"), dtype=np.float64)
    d = np.array(dd.d("g1.measure_2.gate_error"), dtype=np.float64)
    vm = np.where(v >= 1.0, np.nan, v)
    ev = rc.stamp_events(vm, d)
    stamps = np.sort(np.concatenate([x.t_ms for x in ev]))
    br = np.flatnonzero(np.diff(stamps) > rc.SESSION_GAP_MS)
    rounds = stamps[np.concatenate([[0], br + 1])]
    even_starts = s.start_ms[s.kind == "even"]
    nearest_even_h = np.array([np.min(np.abs(even_starts - t)) / 3.6e6 for t in rounds])
    all_starts = s.start_ms[s.kind != "small"]
    nearest_any_h = np.array([np.min(np.abs(all_starts - t)) / 3.6e6 for t in rounds])
    life = np.isfinite(v).any(axis=1)
    ro_life = np.where(life[:, None], r.ro, np.nan)
    med_m2 = np.nanmedian(vm, axis=0)
    med_ro = np.nanmedian(ro_life, axis=0)
    # Within-qubit: each measure_2 event against ro in the same file, logs demeaned per qubit.
    a_all, b_all = [], []
    for x in ev:
        a = np.log10(np.asarray(x.y))
        b = np.log10(r.ro[x.file_idx, x.entity])
        a_all.append(a - np.mean(a))
        b_all.append(b - np.mean(b))
    return {
        "rounds": int(rounds.size),
        "round_gap_h_q": rc.quantiles(np.diff(rounds) / 3.6e6),
        "hours_from_round_to_nearest_even_session_q": rc.quantiles(nearest_even_h),
        "share_rounds_within_1h_of_even_session": round(float(np.mean(nearest_even_h <= 1.0)), 4),
        "share_rounds_within_1h_of_any_session": round(float(np.mean(nearest_any_h <= 1.0)), 4),
        "placeholder_files": [dd.stems[i][:15] for i in np.flatnonzero(np.any(v >= 1.0, axis=1))],
        "per_qubit_median_ratio_m2_over_ro_q": rc.quantiles(med_m2 / med_ro),
        "share_qubits_m2_above_ro": round(float(np.mean(med_m2 > med_ro)), 4),
        "spearman_per_qubit_medians_m2_vs_ro": rc.spearman(med_m2, med_ro),
        "within_qubit_spearman_demeaned_logs": rc.spearman(
            np.concatenate(a_all), np.concatenate(b_all)
        ),
        "device_median_m2": float(f"{np.nanmedian(vm):.5g}"),
        "device_median_ro_same_files": float(f"{np.nanmedian(ro_life):.5g}"),
    }


def init_error(
    dd: ddload.DD, r: rc.Readout, c: dict[str, np.ndarray], s: rc.Sessions
) -> dict[str, Any]:
    v = np.array(dd.v("q.init_error"), dtype=np.float64)
    d = np.array(dd.d("q.init_error"), dtype=np.float64)
    life = np.isfinite(v).any(axis=1)
    first = int(np.flatnonzero(life)[0])
    never = np.flatnonzero(~np.isfinite(v[first:]).any(axis=0))
    partial = [
        {"qubit": int(q), "present_share": round(float(np.mean(np.isfinite(v[first:, q]))), 4)}
        for q in range(156)
        if 0 < np.mean(np.isfinite(v[first:, q])) < 1
    ]
    ok = np.isfinite(v)
    lag_h = (r.d_ro - d)[ok] / 3.6e6
    ev = rc.stamp_events(v, d)
    stamps = np.concatenate([x.t_ms for x in ev])
    si = s.index(stamps)
    within = si >= 0
    # Distance of each init stamp to the nearest readout session (any kind).
    starts = s.start_ms[s.kind != "small"]
    pos = np.searchsorted(starts, stamps)
    dist = (
        np.minimum(
            np.abs(stamps - starts[np.clip(pos - 1, 0, starts.size - 1)]),
            np.abs(starts[np.clip(pos, 0, starts.size - 1)] - stamps),
        )
        / 6e4
    )
    tiny = ok & (v < 1e-6)
    vm = np.where(tiny, np.nan, v)
    life_rows = np.zeros(v.shape[0], dtype=bool)
    life_rows[first:] = True
    med_init = np.nanmedian(vm[first:], axis=0)
    med_p1 = np.nanmedian(np.where(life_rows[:, None], r.p1g0, np.nan), axis=0)
    med_p0 = np.nanmedian(np.where(life_rows[:, None], r.p0g1, np.nan), axis=0)
    med_ro = np.nanmedian(np.where(life_rows[:, None], r.ro, np.nan), axis=0)
    # Within-qubit, same-session records only (init stamp within 10 min of the P(1|0) stamp).
    same = ok & ~tiny & (np.abs(d - r.d_p1g0) <= rc.SAME_SESSION_MS) & (r.p1g0 > 0)
    xs, ys, xr = [], [], []
    for q in range(156):
        m_ = same[:, q]
        if m_.sum() < 20:
            continue
        # one record per init stamp
        idx = np.flatnonzero(m_)
        _, first_idx = np.unique(d[idx, q], return_index=True)
        idx = idx[first_idx]
        a = np.log10(v[idx, q])
        b = np.log10(r.p1g0[idx, q])
        e = np.log10(r.ro[idx, q])
        xs.append(a - a.mean())
        ys.append(b - b.mean())
        xr.append(e - e.mean())
    never_mask = np.zeros(156, dtype=bool)
    never_mask[never] = True
    deg = np.zeros(156, dtype=np.int64)
    for a_, _ in dd.meta["coupling_map"]:
        deg[a_] += 1
    p_ro = stats.mannwhitneyu(med_ro[never_mask], med_ro[~never_mask]).pvalue
    p_p1 = stats.mannwhitneyu(med_p1[never_mask], med_p1[~never_mask]).pvalue
    return {
        "first_file": dd.stems[first][:15],
        "qubits_never_present": [int(q) for q in never],
        "qubits_never_present_count": int(never.size),
        "qubits_partially_present": partial,
        "never_present_by_degree": {
            str(k): [int(np.sum(never_mask & (deg == k))), int(np.sum(deg == k))] for k in (1, 2, 3)
        },
        "never_present_mod_17_counts": np.bincount(never % 17, minlength=17).tolist(),
        "stamp_events": int(stamps.size),
        "qubits_with_lt_50_stamp_events": [
            {"qubit": int(x.entity), "events": int(x.y.size)} for x in ev if x.y.size < 50
        ],
        "stamp_events_inside_a_readout_session": int(within.sum()),
        "minutes_to_nearest_readout_session_q": rc.quantiles(dist),
        "ro_stamp_minus_init_stamp_h_q": rc.quantiles(lag_h),
        "records_below_1e-6": int(tiny.sum()),
        "qubits_with_values_below_1e-6": int(np.sum(tiny.any(axis=0))),
        "between_qubit_spearman_medians": {
            "init_vs_p1g0": rc.spearman(med_init, med_p1),
            "init_vs_p0g1": rc.spearman(med_init, med_p0),
            "init_vs_ro": rc.spearman(med_init, med_ro),
        },
        "within_qubit_spearman_demeaned_logs_same_session": {
            "init_vs_p1g0": rc.spearman(np.concatenate(xs), np.concatenate(ys)),
            "init_vs_ro": rc.spearman(np.concatenate(xs), np.concatenate(xr)),
            "qubits": len(xs),
        },
        "share_records_p1g0_below_init": round(float(np.mean((r.p1g0 < v)[ok & ~tiny])), 4),
        "per_qubit_median_p1g0_over_init_q": rc.quantiles(med_p1 / med_init),
        "never_present_vs_others_median_ro": [
            float(f"{np.median(med_ro[never_mask]):.5g}"),
            float(f"{np.median(med_ro[~never_mask]):.5g}"),
            float(f"{p_ro:.3g}"),
        ],
        "never_present_vs_others_median_p1g0": [
            float(f"{np.median(med_p1[never_mask]):.5g}"),
            float(f"{np.median(med_p1[~never_mask]):.5g}"),
            float(f"{p_p1:.3g}"),
        ],
    }


def main() -> None:
    warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN medians of never-present qubits
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    rc.write(
        "thresholds_m2_init.json",
        "thresholds_m2_init.py",
        {
            "n_files": dd.n_files,
            "thresholds": thresholds(dd, s),
            "measure_2": measure_2(dd, r, s),
            "init_error": init_error(dd, r, c, s),
        },
    )


if __name__ == "__main__":
    main()
