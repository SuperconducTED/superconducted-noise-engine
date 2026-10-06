"""The calibration schedule: rounds, their timing on the clock, their order, their drift.

For every measured family (``device_common.FAMILIES``) this script forms rounds from the
event stamps (15 min gap) and keeps **major rounds**, those re-measuring at least half of the
family's entities (every ``lf`` event is a major round). It reports:

- round counts, coverage, inter-round gaps, short "resets" and long gaps;
- hour-of-day (UTC) and day-of-week of major-round starts, with a chi-square test of
  uniformity (one test per family and per clock; read with the multiple-testing note);
- how much later each day a daily round starts (precession), from gaps between 20 h and 30 h;
- the order of families: offset of every family's nearest major round from each ``T1``
  major round, within +-12 h, overall and by month;
- rounds per day by month (the archive's coverage changed over time);
- seasonality of the VALUES at device level: per major round, the median over re-measured
  entities of ``log10(value)``, minus a centred rolling median over +-7 rounds, grouped by
  hour-of-day (four 6 h bins) and day-of-week, Kruskal-Wallis per family.

Writes ``results/device/schedule.json``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

MAJOR_SHARE = 0.5
RESET_H = 20.0
LONG_H = 36.0
ORDER_WINDOW_H = 12.0
ROLL = 7


def month_of(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m")


def rounds_table(dd: ddload.DD, fam: dc.Family) -> dict[str, Any]:
    ev = dc.family_events(dd, fam)
    lab = dc.split_rounds(ev.t_ms)
    rows = []
    for r in np.unique(lab):
        m = lab == r
        ents = np.unique(ev.entity[m])
        z = np.log10(ev.y[m]) if fam.name != "lf" else None
        rows.append(
            {
                "start": float(ev.t_ms[m].min()),
                "end": float(ev.t_ms[m].max()),
                "entities": int(ents.size),
                "median_log10": float(np.median(z[np.isfinite(z)])) if z is not None else None,
            }
        )
    rows.sort(key=lambda x: x["start"])
    return {"rows": rows, "n_entities": ev.n_entities, "events": int(ev.t_ms.size)}


def chi2_uniform(counts: np.ndarray) -> float | None:
    if counts.sum() < 5 * counts.size:
        return None
    return dc.r6(stats.chisquare(counts).pvalue)


def main() -> int:
    dd = ddload.DD()
    tables = {f.name: rounds_table(dd, f) for f in dc.FAMILIES}
    majors: dict[str, np.ndarray] = {}
    fam_out: dict[str, Any] = {}
    seasonality: dict[str, Any] = {}
    for fam in dc.FAMILIES:
        tab = tables[fam.name]
        rows = tab["rows"]
        need = 1 if fam.name == "lf" else MAJOR_SHARE * tab["n_entities"]
        maj = [r for r in rows if r["entities"] >= need]
        starts = np.array([r["start"] for r in maj])
        majors[fam.name] = starts
        gaps = np.diff(starts) / ddload.MS_PER_HOUR
        hours = np.array([datetime.fromtimestamp(s / 1000.0, UTC).hour for s in starts])
        dows = np.array([datetime.fromtimestamp(s / 1000.0, UTC).weekday() for s in starts])
        hcount = np.bincount(hours, minlength=24)
        dcount = np.bincount(dows, minlength=7)
        daily = (gaps > RESET_H) & (gaps < 30.0)
        per_month: dict[str, Any] = {}
        for s in starts:
            mo = month_of(s)
            per_month[mo] = per_month.get(mo, 0) + 1
        cover = np.array([r["entities"] for r in maj], dtype=float) / tab["n_entities"]
        fam_out[fam.name] = {
            "field": fam.field,
            "events": tab["events"],
            "rounds_all": len(rows),
            "rounds_major": len(maj),
            "rounds_minor": len(rows) - len(maj),
            "minor_round_entities_q": dc.quantiles([r["entities"] for r in rows if r not in maj]),
            "major_coverage_share_q": dc.quantiles(cover),
            "major_duration_s_q": dc.quantiles([(r["end"] - r["start"]) / 1000.0 for r in maj]),
            "gap_h_q": dc.quantiles(gaps),
            "short_gaps_below_20h": [
                {"from": dc.iso(starts[k]), "hours": dc.r6(gaps[k])}
                for k in np.flatnonzero(gaps < RESET_H)
            ]
            if fam.name not in ("readout", "init_error")
            else int(np.sum(gaps < RESET_H)),
            "long_gaps_above_36h": [
                {"from": dc.iso(starts[k]), "to": dc.iso(starts[k + 1]), "hours": dc.r6(gaps[k])}
                for k in np.flatnonzero(gaps > LONG_H)
            ],
            "daily_shift_h_median": dc.r6(np.median(gaps[daily] - 24.0)) if daily.any() else None,
            "daily_gaps_used": int(daily.sum()),
            "hour_of_day_counts": hcount.tolist(),
            "hour_of_day_chi2_p": chi2_uniform(hcount),
            "day_of_week_counts_mon_first": dcount.tolist(),
            "day_of_week_chi2_p": chi2_uniform(dcount),
            "major_rounds_by_month": dict(sorted(per_month.items())),
            "first_major_round": dc.iso(starts[0]) if starts.size else None,
            "last_major_round": dc.iso(starts[-1]) if starts.size else None,
        }
        if fam.name != "lf":
            med = np.array([r["median_log10"] for r in maj])
            roll = np.array(
                [np.median(med[max(0, k - ROLL) : k + ROLL + 1]) for k in range(med.size)]
            )
            resid = med - roll
            hb = hours // 6
            groups_h = [resid[hb == b] for b in range(4) if np.sum(hb == b) >= 3]
            groups_d = [resid[dows == b] for b in range(7) if np.sum(dows == b) >= 3]
            seasonality[fam.name] = {
                "rounds": int(med.size),
                "hour_bin_counts": [int(np.sum(hb == b)) for b in range(4)],
                "hour_bin_median_resid_log10": [
                    dc.r6(np.median(resid[hb == b])) if np.any(hb == b) else None for b in range(4)
                ],
                "hour_kruskal_p": dc.r6(stats.kruskal(*groups_h).pvalue)
                if len(groups_h) > 1
                else None,
                "dow_median_resid_log10": [
                    dc.r6(np.median(resid[dows == b])) if np.any(dows == b) else None
                    for b in range(7)
                ],
                "dow_kruskal_p": dc.r6(stats.kruskal(*groups_d).pvalue)
                if len(groups_d) > 1
                else None,
                "resid_mad_log10": dc.r6(np.median(np.abs(resid - np.median(resid)))),
            }
    # Order of families relative to T1 major rounds.
    anchor = majors["T1"]
    order: dict[str, Any] = {}
    by_month: dict[str, dict[str, Any]] = {}
    for fam in dc.FAMILIES:
        if fam.name == "T1":
            continue
        other = majors[fam.name]
        offs, mos = [], []
        for a in anchor:
            if other.size == 0:
                break
            k = int(np.argmin(np.abs(other - a)))
            o = (other[k] - a) / ddload.MS_PER_HOUR
            if abs(o) <= ORDER_WINDOW_H:
                offs.append(o)
                mos.append(month_of(a))
        arr = np.array(offs)
        order[fam.name] = {
            "anchors_matched": int(arr.size),
            "anchors": int(anchor.size),
            "offset_h_q": dc.quantiles(arr),
            "share_after_T1": dc.r6(np.mean(arr > 0)) if arr.size else None,
        }
        for mo in sorted(set(mos)):
            sel = np.array([m == mo for m in mos])
            by_month.setdefault(mo, {})[fam.name] = {
                "n": int(sel.sum()),
                "median_offset_h": dc.r6(np.median(arr[sel])),
            }
    ranking = sorted(
        (o["offset_h_q"][3], name) for name, o in order.items() if o["offset_h_q"] is not None
    )
    payload = {
        **dc.header("schedule.py"),
        "n_files": dd.n_files,
        "round_gap_min": dc.ROUND_GAP_MIN,
        "major_share": MAJOR_SHARE,
        "families": fam_out,
        "order_relative_to_T1": order,
        "order_by_median_offset": [[dc.r6(o), n] for o, n in ranking],
        "order_by_month": by_month,
        "value_seasonality_device_median": seasonality,
        "seasonality_tests": 2 * len(seasonality),
    }
    ddload.write_json(dc.RESULTS / "schedule.json", payload)
    print("wrote", dc.RESULTS / "schedule.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
