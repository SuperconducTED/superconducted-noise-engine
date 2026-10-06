"""Profile of the sx gate error: distribution, tails, per-qubit levels, cadence, changes.

Writes ``results/gates_1q/sx_profile.json``. Unit: re-measurement events under the MEASURED
rule with placeholders (``gate_error >= 1``) masked before events are formed, so ``q72``
(placeholder in every file) has no series. The aliases ``x``, ``id``, ``rx`` and ``xslow``
are copies of ``sx`` (``aliases_and_schema.json``) and are not profiled separately.
"""

from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import g1common as g

SCRIPT = "analysis/gates_1q/sx_profile.py"
SPLIT_MS = g.ms_of("2026-07-25T00:00:00Z")  # calendar midpoint of 2026-05-13 .. 2026-10-06
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def distribution(series: list[Any]) -> dict[str, Any]:
    y = np.concatenate([s.y for s in series])
    z = np.log10(y)
    med = {s.entity: float(np.median(np.log10(s.y))) for s in series}
    resid = np.concatenate([np.log10(s.y) - med[s.entity] for s in series])
    ent_mean = np.array([np.mean(np.log10(s.y)) for s in series])
    ent_var = np.array([np.var(np.log10(s.y)) for s in series])
    n_e = np.array([s.y.size for s in series], dtype=np.float64)
    total_var = float(np.var(z))
    between = float(np.sum(n_e * (ent_mean - z.mean()) ** 2) / n_e.sum())
    within = float(np.sum(n_e * ent_var) / n_e.sum())
    medians = np.array(list(med.values()))
    ents = np.array(list(med.keys()))
    order = np.argsort(medians)
    iqr = np.array(
        [np.subtract(*np.quantile(np.log10(s.y), [0.75, 0.25])) for s in series], dtype=np.float64
    )
    qs = (0.0, 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999, 1.0)
    return {
        "events": int(y.size),
        "entities": len(series),
        "value_q": dict(zip([str(x) for x in qs], g.q(y, qs, nd=8), strict=True)),
        "log10_q": dict(zip([str(x) for x in qs], g.q(z, qs, nd=4), strict=True)),
        "share_above": {
            str(t): g.rnd(float(np.mean(y > t)), 5) for t in (1e-3, 2e-3, 5e-3, 1e-2, 0.1)
        },
        "count_above": {str(t): int(np.sum(y > t)) for t in (1e-3, 1e-2, 0.1)},
        "max_event_value": float(y.max()),
        "max_event_entity": int(next(s.entity for s in series if s.y.max() == y.max())),
        "log10_variance_total": g.rnd(total_var, 5),
        "log10_variance_between_entity_means": g.rnd(between, 5),
        "log10_variance_within_entities": g.rnd(within, 5),
        "between_share": g.rnd(between / total_var, 4),
        "residual_from_entity_median_log10_q": dict(
            zip([str(x) for x in qs], g.q(resid, qs, nd=4), strict=True)
        ),
        "residual_share_above_plus_log2": g.rnd(float(np.mean(resid > g.LOG10_2)), 5),
        "residual_share_below_minus_log2": g.rnd(float(np.mean(resid < -g.LOG10_2)), 5),
        "residual_share_above_plus_1_decade": g.rnd(float(np.mean(resid > 1.0)), 5),
        "residual_share_below_minus_1_decade": g.rnd(float(np.mean(resid < -1.0)), 5),
        "entity_median_value_q": g.q(10**medians, nd=8),
        "entity_median_log10_mad": g.rnd(float(np.median(np.abs(medians - np.median(medians)))), 4),
        "entity_median_max_over_min": g.rnd(float(10 ** (medians.max() - medians.min())), 2),
        "best5_entities_median": [
            {"qubit": int(ents[i]), "median": float(f"{10 ** medians[i]:.4g}")} for i in order[:5]
        ],
        "worst5_entities_median": [
            {"qubit": int(ents[i]), "median": float(f"{10 ** medians[i]:.4g}")}
            for i in order[::-1][:5]
        ],
        "entity_iqr_log10_q": g.q(iqr, nd=4),
    }


def stability(series: list[Any]) -> dict[str, Any]:
    first, second = [], []
    for s in series:
        z = np.log10(s.y)
        a, b = z[s.t_ms < SPLIT_MS], z[s.t_ms >= SPLIT_MS]
        first.append(float(np.median(a)) if a.size >= 5 else math.nan)
        second.append(float(np.median(b)) if b.size >= 5 else math.nan)
    f, sec = np.array(first), np.array(second)
    ok = np.isfinite(f) & np.isfinite(sec)
    terc_f = np.digitize(f[ok], np.quantile(f[ok], [1 / 3, 2 / 3]))
    terc_s = np.digitize(sec[ok], np.quantile(sec[ok], [1 / 3, 2 / 3]))
    months = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    mmed = np.full((len(series), len(months)), np.nan)
    mcount = np.zeros((len(series), len(months)), dtype=np.int64)
    for i, s in enumerate(series):
        lab = np.array(g.month_of(s.t_ms))
        z = np.log10(s.y)
        for j, m in enumerate(months):
            sel = lab == m
            mcount[i, j] = int(sel.sum())
            if sel.sum() >= 5:
                mmed[i, j] = float(np.median(z[sel]))
    consecutive = {
        f"{months[j]}_vs_{months[j + 1]}": g.spearman(mmed[:, j], mmed[:, j + 1])
        for j in range(len(months) - 1)
    }
    device_month = {
        m: g.rnd(float(10 ** np.nanmedian(mmed[:, j])), 8)
        if np.isfinite(mmed[:, j]).any()
        else None
        for j, m in enumerate(months)
    }
    return {
        "split": g.iso(SPLIT_MS),
        "halves_spearman_of_entity_medians": g.spearman(f, sec),
        "halves_same_tercile_share": g.rnd(float(np.mean(terc_f == terc_s)), 4),
        "halves_median_abs_shift_log10": g.rnd(float(np.median(np.abs(f[ok] - sec[ok]))), 4),
        "monthly_min_events_for_median": 5,
        "monthly_consecutive_spearman": consecutive,
        "may_vs_september_spearman": g.spearman(mmed[:, 0], mmed[:, 4]),
        "device_median_of_entity_monthly_medians": device_month,
        "events_per_entity_by_month_median": {
            m: float(np.median(mcount[:, j])) for j, m in enumerate(months)
        },
    }


def cadence(series: list[Any]) -> dict[str, Any]:
    gaps = np.concatenate([np.diff(s.t_ms) / g.HOUR_MS for s in series])
    later = np.concatenate([s.t_ms[1:] for s in series])
    lab = np.array(g.month_of(later))
    by_month = {
        m: {
            "gaps": int(np.sum(lab == m)),
            "gap_h_q_10_50_90": g.q(gaps[lab == m], (0.1, 0.5, 0.9), 2),
        }
        for m in sorted(set(lab.tolist()))
    }
    stamps = np.concatenate([s.t_ms[1:] for s in series])
    starts, rid = g.rounds(stamps)
    sizes = np.bincount(rid)
    gap_rounds = np.diff(starts) / g.HOUR_MS
    hours = ((stamps / g.HOUR_MS) % 24).astype(np.int64)
    start_hours = ((starts / g.HOUR_MS) % 24).astype(np.int64)
    wd = np.array([datetime.fromtimestamp(t / 1000, tz=UTC).weekday() for t in stamps])
    start_wd = np.array([datetime.fromtimestamp(t / 1000, tz=UTC).weekday() for t in starts])
    half = 0.5 * len(series)
    fewest = sorted(series, key=lambda s: s.y.size)[:6]
    longest = sorted(series, key=lambda s: -float(np.max(np.diff(s.t_ms))))[:6]
    return {
        "events_per_series_q": g.q(np.array([s.y.size for s in series]), nd=1),
        "fewest_events": [
            {
                "qubit": int(s.entity),
                "events": int(s.y.size),
                "max_gap_h": g.rnd(float(np.max(np.diff(s.t_ms)) / g.HOUR_MS), 1),
                "max_gap_from": g.iso(float(s.t_ms[int(np.argmax(np.diff(s.t_ms)))])),
            }
            for s in fewest
        ],
        "longest_gaps": [
            {
                "qubit": int(s.entity),
                "max_gap_h": g.rnd(float(np.max(np.diff(s.t_ms)) / g.HOUR_MS), 1),
                "from": g.iso(float(s.t_ms[int(np.argmax(np.diff(s.t_ms)))])),
            }
            for s in longest
        ],
        "gap_h_q": g.q(gaps, nd=3),
        "gap_h_by_month_of_later_event": by_month,
        "rounds": {
            "definition": "event stamps (first event of each series excluded) split where "
            "consecutive stamps are more than 15 minutes apart",
            "n_rounds": int(starts.size),
            "entities_per_round_q": g.q(sizes.astype(np.float64), nd=1),
            "rounds_with_ge_half_device": int(np.sum(sizes >= half)),
            "events_in_rounds_with_ge_half_device_share": g.rnd(
                float(sizes[sizes >= half].sum() / sizes.sum()), 4
            ),
            "gap_between_round_starts_h_q": g.q(gap_rounds, nd=2),
            "round_starts_by_utc_hour": np.bincount(start_hours, minlength=24).tolist(),
            "round_starts_by_weekday": dict(
                zip(WEEKDAYS, np.bincount(start_wd, minlength=7).tolist(), strict=True)
            ),
        },
        "event_stamps_by_utc_hour": np.bincount(hours, minlength=24).tolist(),
        "event_stamps_by_weekday": dict(
            zip(WEEKDAYS, np.bincount(wd, minlength=7).tolist(), strict=True)
        ),
    }


def changes(series: list[Any]) -> dict[str, Any]:
    d_all, a1, b1, a2, b2 = [], [], [], [], []
    for s in series:
        z = np.log10(s.y)
        dz = np.diff(z)
        d_all.append(dz)
        a1.append(dz[:-1])
        b1.append(dz[1:])
        a2.append(dz[:-2])
        b2.append(dz[2:])
    d = np.concatenate(d_all)
    x1, y1 = np.concatenate(a1), np.concatenate(b1)
    x2, y2 = np.concatenate(a2), np.concatenate(b2)
    rho1 = float(np.corrcoef(x1, y1)[0, 1])
    rho2 = float(np.corrcoef(x2, y2)[0, 1])
    resid = []
    for s in series:
        z = np.log10(s.y)
        lvl = g.running_level(z)
        resid.append(z - lvl)
    r = np.concatenate(resid)
    r = r[np.isfinite(r)]
    q1, q2, q3 = np.quantile(r, [0.25, 0.5, 0.75])
    o1, o7 = np.quantile(r, [0.125, 0.875])
    return {
        "transitions": int(d.size),
        "abs_change_log10_q": g.q(np.abs(d), nd=4),
        "share_changes_gt_factor2": g.rnd(float(np.mean(np.abs(d) > g.LOG10_2)), 4),
        "lag1_autocorr_of_change_pearson": g.rnd(rho1, 4),
        "lag1_autocorr_of_change_spearman": g.spearman(x1, y1),
        "lag2_autocorr_of_change_pearson": g.rnd(rho2, 4),
        "local_level_q_from_lag1": g.rnd(-1.0 / rho1 - 2.0, 4),
        "residual_from_running_level": {
            "definition": "log10 value minus the median of up to 5 events each side "
            "(self excluded, at least 4 neighbours)",
            "n": int(r.size),
            "q": g.q(r, (0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999), nd=4),
            "share_above_plus_log2": g.rnd(float(np.mean(r > g.LOG10_2)), 5),
            "share_below_minus_log2": g.rnd(float(np.mean(r < -g.LOG10_2)), 5),
            "share_above_plus_half_decade": g.rnd(float(np.mean(r > 0.5)), 5),
            "share_below_minus_half_decade": g.rnd(float(np.mean(r < -0.5)), 5),
            "bowley_skew": g.rnd(float((q3 + q1 - 2 * q2) / (q3 - q1)), 4),
            "octile_skew": g.rnd(float((o7 + o1 - 2 * q2) / (o7 - o1)), 4),
        },
    }


def main() -> int:
    dd = ddload.DD()
    series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["field"] = g.SX_FIELD
    payload["rule"] = "measured, placeholders masked before events"
    payload["distribution"] = distribution(series)
    payload["stability"] = stability(series)
    payload["cadence"] = cadence(series)
    payload["changes"] = changes(series)
    ddload.write_json(g.RESULTS / "sx_profile.json", payload)
    print("wrote", g.RESULTS / "sx_profile.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
