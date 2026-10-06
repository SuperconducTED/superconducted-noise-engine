"""Profiles of every readout-scope field: range, distribution, tails, events, cadence, memory.

Writes ``results/readout/profiles.json``. Error-like fields are profiled under two event
rules side by side: the shared measured rule (value AND stamp new) and this scope's stamp
rule (stamp new, value may repeat), so the cost of the measured rule on quantized values is
visible. Length fields are value-only and are checked for their identities (reset = readout
length + 24 ns, and so on).
"""

from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc

ERROR_FIELDS = (
    "q.readout_error",
    "q.prob_meas0_prep1",
    "q.prob_meas1_prep0",
    "q.init_error",
    "g1.measure_2.gate_error",
)
LENGTH_FIELDS = (
    "q.readout_length",
    "g1.measure.gate_length",
    "g1.measure_2.gate_length",
    "g1.measure_reset.gate_length",
    "g1.measure_reset_2.gate_length",
    "g1.reset.gate_length",
    "g1.reset_2.gate_length",
)


def memory(series: list[ddload.Series]) -> dict[str, Any]:
    """Lag-1 autocorrelation of consecutive log10 changes, pooled; share of changes > 2x."""
    pairs: list[np.ndarray] = []
    deltas: list[np.ndarray] = []
    dropped_nonpositive = 0
    for s in series:
        y = np.asarray(s.y, dtype=np.float64)
        dropped_nonpositive += int(np.sum(y <= 0))
        z = np.log10(y[y > 0])
        if z.size < 3:
            continue
        dz = np.diff(z)
        deltas.append(dz)
        pairs.append(np.stack([dz[:-1], dz[1:]], axis=1))
    d = np.concatenate(deltas)
    p = np.concatenate(pairs)
    return {
        "transitions": int(d.size),
        "events_dropped_nonpositive": dropped_nonpositive,
        "lag1_autocorr_of_log10_change": round(float(np.corrcoef(p[:, 0], p[:, 1])[0, 1]), 4),
        "abs_log10_change_q": rc.quantiles(np.abs(d)),
        "share_change_gt_2x": round(float(np.mean(np.abs(d) > math.log10(2.0))), 4),
        "share_change_exact_zero": round(float(np.mean(d == 0.0)), 4),
    }


def event_stats(series: list[ddload.Series]) -> dict[str, Any]:
    n = np.array([s.y.size for s in series], dtype=np.float64)
    gaps = np.concatenate([np.diff(s.t_ms) / 3.6e6 for s in series if s.t_ms.size > 1])
    return {
        "series": len(series),
        "events_total": int(n.sum()),
        "events_per_entity_q": rc.quantiles(n),
        "gap_h_q": rc.quantiles(gaps),
    }


def profile_error(dd: ddload.DD, field: str) -> dict[str, Any]:
    v = np.array(dd.v(field), dtype=np.float64)
    d = np.array(dd.d(field), dtype=np.float64)
    present_files = np.flatnonzero(np.isfinite(v).any(axis=1))
    first, last = int(present_files[0]), int(present_files[-1])
    life = v[first : last + 1]
    ph = ddload.placeholder_error(np.where(np.isfinite(v), v, 0.0)) & np.isfinite(v)
    out: dict[str, Any] = {
        "first_file": dd.stems[first][:15],
        "last_file": dd.stems[last][:15],
        "files_in_lifetime": last - first + 1,
        "entities_never_present_in_lifetime": [
            int(e) for e in np.flatnonzero(~np.isfinite(life).any(axis=0))
        ],
        "present_share_in_lifetime": round(float(np.mean(np.isfinite(life))), 4),
        "present_share_in_lifetime_excluding_never_present": round(
            float(np.mean(np.isfinite(life[:, np.isfinite(life).any(axis=0)]))), 4
        ),
        "placeholder_records_ge_1": int(ph.sum()),
    }
    if ph.any():
        pf = np.flatnonzero(ph.any(axis=1))
        out["placeholder_files"] = [
            {"file": dd.stems[i][:15], "entities": int(ph[i].sum())} for i in pf
        ]
    vm = np.where(ph, np.nan, v)
    x = vm[np.isfinite(vm)]
    out["records"] = int(x.size)
    out["value_q_0_1_10_50_90_99_100"] = rc.quantiles(x)
    out["exact_zero_records"] = int(np.sum(x == 0))
    out["below_1e-6_records"] = int(np.sum(x < 1e-6))
    # Tails relative to each entity's own median (log10 decades above / below).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # entities never present: all-NaN
        med = np.nanmedian(np.where(vm > 0, vm, np.nan), axis=0)
    rel = np.log10(np.where(vm > 0, vm, np.nan) / med[None, :])
    out["log10_value_over_entity_median_q"] = rc.quantiles(rel)
    out["share_records_gt_3x_entity_median"] = round(float(np.nanmean(rel > math.log10(3.0))), 5)
    out["share_records_lt_third_entity_median"] = round(
        float(np.nanmean(rel < -math.log10(3.0))), 5
    )
    out["entity_median_q"] = rc.quantiles(med)
    out["date_equals_file_date_share"] = round(ddload.assembly_share(dd, field), 4)
    # Grids.
    grid: dict[str, float] = {}
    for den in (2048, 4096, 8192):
        k = x * den
        grid[f"on_1_over_{den}"] = round(float(np.mean(np.abs(k - np.round(k)) < 1e-6)), 5)
    out["grid_share"] = grid
    # Events under both rules (placeholders masked first).
    measured = ddload.series(dd, field, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    stamp = rc.stamp_events(vm, d)
    out["events_measured_rule"] = event_stats(measured)
    out["events_stamp_rule"] = event_stats(stamp)
    out["stamp_events_with_value_unchanged"] = int(
        sum(int(np.sum(np.diff(s.y) == 0)) for s in stamp)
    )
    out["memory_measured_rule"] = memory(measured)
    out["memory_stamp_rule"] = memory(stamp)
    if out["below_1e-6_records"]:
        # Values below 1e-6 sit many decades under the entity's level (a degenerate estimate,
        # see the document); recompute the memory with them masked so they cannot dominate.
        vm2 = np.where(vm < 1e-6, np.nan, vm)
        out["memory_stamp_rule_values_ge_1e-6"] = memory(rc.stamp_events(vm2, d))
    return out


def profile_length(dd: ddload.DD, field: str) -> dict[str, Any]:
    v = np.array(dd.v(field), dtype=np.float64)
    present_files = np.flatnonzero(np.isfinite(v).any(axis=1))
    first = int(present_files[0])
    vals, counts = np.unique(v[np.isfinite(v)], return_counts=True)
    changes = []
    for i in range(first + 1, v.shape[0]):
        a, b = v[i - 1], v[i]
        ok = np.isfinite(a) & np.isfinite(b)
        if np.any(a[ok] != b[ok]):
            changes.append(
                {
                    "file": dd.stems[i][:15],
                    "entities_changed": int(np.sum(a[ok] != b[ok])),
                    "from": sorted({float(x) for x in a[ok][a[ok] != b[ok]]}),
                    "to": sorted({float(x) for x in b[ok][a[ok] != b[ok]]}),
                }
            )
    return {
        "first_file": dd.stems[first][:15],
        "present_share_in_lifetime": round(float(np.mean(np.isfinite(v[first:]))), 4),
        "distinct_values": {str(float(a)): int(b) for a, b in zip(vals, counts, strict=True)},
        "value_changes": changes,
    }


def identity(dd: ddload.DD, a: str, b: str, offset: float) -> dict[str, int]:
    va = np.array(dd.v(a), dtype=np.float64)
    vb = np.array(dd.v(b), dtype=np.float64)
    ok = np.isfinite(va) & np.isfinite(vb)
    return {"compared": int(ok.sum()), "mismatch": int(np.sum(va[ok] + offset != vb[ok]))}


def main() -> None:
    dd = ddload.DD()
    errors = {f: profile_error(dd, f) for f in ERROR_FIELDS}
    lengths = {f: profile_length(dd, f) for f in LENGTH_FIELDS}
    ids = {
        "reset_eq_readout_length_plus_24": identity(
            dd, "q.readout_length", "g1.reset.gate_length", 24.0
        ),
        "measure_reset_eq_reset": identity(
            dd, "g1.reset.gate_length", "g1.measure_reset.gate_length", 0.0
        ),
        "reset_2_eq_measure_2_plus_24": identity(
            dd, "g1.measure_2.gate_length", "g1.reset_2.gate_length", 24.0
        ),
        "measure_reset_2_eq_reset_2": identity(
            dd, "g1.reset_2.gate_length", "g1.measure_reset_2.gate_length", 0.0
        ),
        "x_length_ns_distinct": sorted(
            {float(x) for x in np.unique(np.array(dd.v("g1.x.gate_length")))}
        ),
    }
    # Parity of the published counts (a pure 4,096-shot binomial gives about half odd).
    parity: dict[str, Any] = {}
    for f in ("q.prob_meas0_prep1", "q.prob_meas1_prep0"):
        ev = rc.stamp_events(np.array(dd.v(f)), np.array(dd.d(f)))
        k = np.round(np.concatenate([s.y for s in ev]) * rc.SHOTS).astype(np.int64)
        parity[f] = {
            "stamp_events": int(k.size),
            "odd_share": round(float(np.mean(k % 2 == 1)), 4),
            "count_mod_4": np.bincount(k % 4, minlength=4).tolist(),
        }
    m2 = np.array(dd.v("g1.measure_2.gate_error"))
    m2 = m2[np.isfinite(m2) & (m2 < 1.0)]
    k2 = np.round(m2 * rc.SHOTS).astype(np.int64)
    parity["g1.measure_2.gate_error"] = {
        "records": int(k2.size),
        "odd_share_of_4096_count": round(float(np.mean(k2 % 2 == 1)), 4),
    }
    p1g0 = np.array(dd.v("q.prob_meas1_prep0"))
    zero_per_q = np.sum(p1g0 == 0, axis=0)
    rc.write(
        "profiles.json",
        "profiles.py",
        {
            "n_files": dd.n_files,
            "error_fields": errors,
            "length_fields": lengths,
            "length_identities": ids,
            "count_parity": parity,
            "p1g0_exact_zero": {
                "records": int(np.sum(p1g0 == 0)),
                "qubits_with_any": int(np.sum(zero_per_q > 0)),
                "max_per_qubit": int(zero_per_q.max()),
            },
        },
    )


if __name__ == "__main__":
    main()
