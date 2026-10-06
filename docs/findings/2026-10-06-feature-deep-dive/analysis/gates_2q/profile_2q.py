"""Profile the two-qubit fields: direction identity, distributions, cadence, faults, lengths.

Writes ``results/gates_2q/profile.json``. Loads only ``g2.cz.*``, ``g2.rzz.*``, ``gen.jq``
and the per-file arrays ``last_update_ms`` and ``has_configuration`` (for the coverage split).
"""

from __future__ import annotations

import collections
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/profile_2q.py"
LOG2 = math.log10(2.0)


def direction_identity(dd: ddload.DD, gate: str, fwd: list[int], rev: list[int]) -> dict:
    """Compare the two directions of every coupler, separating placeholder records."""
    v = np.array(dd.v(f"g2.{gate}.gate_error"))
    d = np.array(dd.d(f"g2.{gate}.gate_error"))
    vf, vr, df, dr = v[:, fwd], v[:, rev], d[:, fwd], d[:, rev]
    both = np.isfinite(vf) & np.isfinite(vr)
    ph_f, ph_r = vf >= 1.0, vr >= 1.0
    mism = (df != dr) & both
    off_us = np.abs(df - dr)[mism] * 1000.0
    file_ms = dd.file_ms[:, None]
    nonph = both & ~ph_f
    d_nonph = df[nonph]
    d_ph = df[ph_f & both]
    return {
        "records_compared": int(both.sum()),
        "value_mismatch": int(np.sum((vf != vr) & both)),
        "placeholder_flag_mismatch": int(np.sum((ph_f != ph_r) & both)),
        "date_mismatch": int(mism.sum()),
        "date_mismatch_in_placeholder_records": int(np.sum(mism & ph_f)),
        "date_mismatch_outside_placeholders": int(np.sum(mism & ~ph_f)),
        "placeholder_records_per_direction": int(np.sum(ph_f & both)),
        "mismatch_offset_microseconds_q": c.q(off_us),
        "nonplaceholder_stamps": int(d_nonph.size),
        "nonplaceholder_stamps_whole_second_share": c.rnd(
            float(np.mean(np.mod(d_nonph, 1000.0) == 0.0)), 6
        ),
        "placeholder_stamps_whole_millisecond_share": c.rnd(
            float(np.mean(np.mod(d_ph, 1.0) == 0.0)), 6
        )
        if d_ph.size
        else None,
        "placeholder_stamp_minus_file_date_h_q": c.q(
            ((df - file_ms)[ph_f & both]) / ddload.MS_PER_HOUR
        ),
        "nonplaceholder_stamp_minus_file_date_h_q": c.q(
            ((df - file_ms)[nonph]) / ddload.MS_PER_HOUR
        ),
    }


def value_profile(
    dd: ddload.DD, gate: str, fwd: list[int], pairs: list[tuple[int, int]], split: float
) -> dict[str, Any]:
    v = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
    ok = np.isfinite(v) & (v < 1.0)
    series = c.gate_series(dd, gate, fwd)
    col_pos = {col: i for i, col in enumerate(fwd)}
    ev_vals = np.concatenate([s.y for s in series.values()])
    per_coupler_median = np.array([np.median(np.log10(s.y)) for s in series.values()])
    dev = np.concatenate([np.log10(s.y) - np.median(np.log10(s.y)) for s in series.values()])
    n_events = np.array([s.y.size for s in series.values()], dtype=np.float64)
    gaps_all: list[float] = []
    gaps_p1: list[float] = []
    gaps_p2: list[float] = []
    long_gaps: list[dict[str, Any]] = []
    stamps: list[float] = []
    for col, s in series.items():
        t = s.t_ms
        stamps.extend(t[1:].tolist())
        g = np.diff(t) / ddload.MS_PER_HOUR
        gaps_all.extend(g.tolist())
        for k, gk in enumerate(g):
            (gaps_p1 if t[k + 1] < split else gaps_p2).append(float(gk))
            if gk > 168.0:
                long_gaps.append(
                    {
                        "coupler": c.label(pairs[col_pos[col]]),
                        "from": c.iso(t[k]),
                        "to": c.iso(t[k + 1]),
                        "hours": c.rnd(float(gk)),
                    }
                )
    st = np.array(stamps)
    rds = c.rounds(st)
    sizes = np.array([r.size for r in rds], dtype=np.float64)
    starts = np.array([r[0] for r in rds])
    n_series = len(series)
    hour, weekday = c.hour_weekday(st)
    start_hour, _ = c.hour_weekday(starts)
    days_p1 = (split - dd.file_ms[0]) / (24 * ddload.MS_PER_HOUR)
    days_p2 = (dd.file_ms[-1] - split) / (24 * ddload.MS_PER_HOUR)
    p1_events = int(np.sum(st < split))
    p2_events = int(np.sum(st >= split))
    lz = np.log10(v[ok])
    return {
        "records_nonplaceholder": int(ok.sum()),
        "records_placeholder": int(np.sum(np.isfinite(v) & (v >= 1.0))),
        "record_weighted_q": c.q(v[ok]),
        "event_weighted_q": c.q(ev_vals),
        "event_weighted_mean": c.rnd(float(np.mean(ev_vals))),
        "record_log10_skew": c.rnd(float(((lz - lz.mean()) ** 3).mean() / lz.std() ** 3)),
        "couplers_with_events": n_series,
        "couplers_without_events_permanently_faulty": [
            c.label(pairs[i]) for i, col in enumerate(fwd) if col not in series
        ],
        "per_coupler_median_log10_q": c.q(per_coupler_median),
        "per_coupler_median_q": c.q(10.0**per_coupler_median),
        "best_to_worst_coupler_median_ratio": c.rnd(
            float(10.0 ** (per_coupler_median.max() - per_coupler_median.min()))
        ),
        "p90_to_p10_coupler_median_ratio": c.rnd(
            float(
                10.0
                ** (np.quantile(per_coupler_median, 0.9) - np.quantile(per_coupler_median, 0.1))
            )
        ),
        "deviation_from_coupler_median_log10_q": c.q(dev),
        "deviation_share_above_factor2": c.rnd(float(np.mean(dev > LOG2))),
        "deviation_share_below_half": c.rnd(float(np.mean(dev < -LOG2))),
        "deviation_share_above_10x": c.rnd(float(np.mean(dev > 1.0))),
        "events_total": int(ev_vals.size),
        "events_per_coupler_q": c.q(n_events),
        "event_gap_h_q": c.q(gaps_all),
        "event_gap_h_q_before_split": c.q(gaps_p1),
        "event_gap_h_q_after_split": c.q(gaps_p2),
        "gaps_over_168h": len(long_gaps),
        "gaps_over_48h": int(np.sum(np.array(gaps_all) > 48.0)),
        "gaps_over_48h_before_split": int(np.sum(np.array(gaps_p1) > 48.0)),
        "gaps_over_48h_after_split": int(np.sum(np.array(gaps_p2) > 48.0)),
        "long_gaps_over_168h": long_gaps[:60],
        "long_gaps_listed_cap": 60,
        "events_after_first_before_split": p1_events,
        "events_after_first_after_split": p2_events,
        "events_per_coupler_per_day_before_split": c.rnd(p1_events / n_series / days_p1),
        "events_per_coupler_per_day_after_split": c.rnd(p2_events / n_series / days_p2),
        "rounds": {
            "n_rounds": len(rds),
            "couplers_per_round_q": c.q(sizes),
            "rounds_with_ge_half_of_couplers": int(np.sum(sizes >= 0.5 * n_series)),
            "rounds_with_lt_10_couplers": int(np.sum(sizes < 10)),
            "gap_between_round_starts_h_q": c.q(np.diff(starts) / ddload.MS_PER_HOUR),
            "round_span_minutes_q": c.q(
                np.array([(r[-1] - r[0]) / 60000.0 for r in rds], dtype=np.float64)
            ),
            "distinct_stamps_per_round_q": c.q(
                np.array([np.unique(r).size for r in rds], dtype=np.float64)
            ),
            "round_start_utc_hour_counts": np.bincount(start_hour, minlength=24).tolist(),
            "round_start_gaps_over_40h": [
                {
                    "from": c.iso(starts[k]),
                    "to": c.iso(starts[k + 1]),
                    "hours": c.rnd(float((starts[k + 1] - starts[k]) / ddload.MS_PER_HOUR)),
                }
                for k in range(starts.size - 1)
                if starts[k + 1] - starts[k] > 40.0 * ddload.MS_PER_HOUR
            ],
            "n_round_start_gaps_over_40h": int(np.sum(np.diff(starts) > 40.0 * ddload.MS_PER_HOUR)),
            "rounds_before_split": int(np.sum(starts < split)),
            "rounds_from_split": int(np.sum(starts >= split)),
            "split_days_before": c.rnd(float(days_p1)),
            "split_days_from": c.rnd(float(days_p2)),
        },
        "event_utc_hour_counts": np.bincount(hour, minlength=24).tolist(),
        "event_weekday_counts_mon_first": np.bincount(weekday, minlength=7).tolist(),
    }


def placeholder_states(
    dd: ddload.DD, gate: str, fwd: list[int], pairs: list[tuple[int, int]]
) -> dict[str, Any]:
    v = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
    fm = dd.file_ms
    ph = v >= 1.0
    out: list[dict[str, Any]] = []
    entries = exits = 0
    for i, pair in enumerate(pairs):
        col = ph[:, i]
        if not col.any():
            continue
        runs = []
        k = 0
        n = col.size
        while k < n:
            if col[k]:
                j = k
                while j + 1 < n and col[j + 1]:
                    j += 1
                ends_open = j == n - 1
                starts_open = k == 0
                end_ms = fm[j + 1] if not ends_open else fm[j]
                runs.append(
                    {
                        "first_file": dd.stems[k],
                        "last_file": dd.stems[j],
                        "files": int(j - k + 1),
                        "hours": c.rnd(float((end_ms - fm[k]) / ddload.MS_PER_HOUR)),
                        "open_at_start": bool(starts_open),
                        "open_at_end": bool(ends_open),
                    }
                )
                entries += 0 if starts_open else 1
                exits += 0 if ends_open else 1
                k = j + 1
            else:
                k += 1
        out.append(
            {
                "coupler": c.label(pair),
                "share_of_files": c.rnd(float(col.mean())),
                "runs": len(runs),
                "run_list": runs[:12],
                "runs_listed_cap": 12,
            }
        )
    out.sort(key=lambda r: -r["share_of_files"])
    always = [r["coupler"] for r in out if r["share_of_files"] == 1.0]
    per_file = ph.sum(axis=1)
    return {
        "couplers_ever_placeholder": len(out),
        "couplers_always_placeholder": always,
        "entries_into_placeholder": entries,
        "exits_from_placeholder": exits,
        "placeholder_couplers_per_file_q": c.q(per_file.astype(np.float64)),
        "couplers": out,
    }


def lengths(dd: ddload.DD, gate: str, fwd: list[int], pairs: list[tuple[int, int]]) -> dict:
    v = np.array(dd.v(f"g2.{gate}.gate_length"))[:, fwd]
    err = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
    counts = collections.Counter(float(x) for x in v[np.isfinite(v)].ravel())
    special = []
    for i, pair in enumerate(pairs):
        col = v[:, i]
        vals = np.unique(col[np.isfinite(col)])
        if vals.size == 1 and vals[0] == 68.0:
            continue
        changes = [
            {"file": dd.stems[k], "from": float(col[k - 1]), "to": float(col[k])}
            for k in range(1, col.size)
            if col[k] != col[k - 1]
        ]
        e = err[:, i]
        e = e[np.isfinite(e) & (e < 1.0)]
        special.append(
            {
                "coupler": c.label(pair),
                "values_ns": [float(x) for x in vals],
                "changes": changes,
                "placeholder_share": c.rnd(float(np.mean(err[:, i] >= 1.0))),
                "record_median_error": c.rnd(float(np.median(e))) if e.size else None,
            }
        )
    e68 = err[(v == 68.0) & (err < 1.0)]
    return {
        "record_counts_by_length_ns": {str(k): int(n) for k, n in sorted(counts.items())},
        "non_68ns_couplers": special,
        "record_median_error_at_68ns": c.rnd(float(np.median(e68))),
    }


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, rev = c.canonical(dd)
    split = c.split_ms(dd)
    payload: dict[str, Any] = {
        "n_files": dd.n_files,
        "n_couplers": len(pairs),
        "canonical_direction": "column [a, b] with a < b",
        "coverage_split": {
            "rule": "first file with configuration null (first historical fetch)",
            "split_utc": c.iso(split),
            "split_file": c.stem_at(dd, split),
            "files_before": int(np.sum(dd.file_ms < split)),
            "files_from": int(np.sum(dd.file_ms >= split)),
        },
    }
    for gate in c.GATES:
        payload[gate] = {
            "direction_identity": direction_identity(dd, gate, fwd, rev),
            "values": value_profile(dd, gate, fwd, pairs, split),
            "placeholders": placeholder_states(dd, gate, fwd, pairs),
            "lengths": lengths(dd, gate, fwd, pairs),
        }
    jq = np.array(dd.v("gen.jq"))
    payload["jq"] = {
        "records": int(np.isfinite(jq).sum()),
        "zero_records": int(np.sum(jq == 0.0)),
        "distinct_values": int(np.unique(jq[np.isfinite(jq)]).size),
    }
    ops = collections.Counter(op for op, _ in dd.meta["target_union"])
    payload["target_operations_union_counts"] = dict(sorted(ops.items()))
    payload["rzz_in_target_union"] = int(ops.get("rzz", 0))
    path = c.write("profile.json", SCRIPT, payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
