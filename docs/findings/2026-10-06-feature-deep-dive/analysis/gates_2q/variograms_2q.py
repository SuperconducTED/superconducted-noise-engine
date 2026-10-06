"""Variograms of log cz, log rzz and zz (the shared instrument of 01-data-layer.md section 7).

Writes ``results/gates_2q/variograms.json``. Loads only ``g2.cz.gate_error``,
``g2.rzz.gate_error``, ``gen.zz`` and the per-file arrays used for the coverage split.

Series:

- ``cz``, ``rzz``: measured-rule events, canonical direction, placeholders masked; the
  permanently faulty couplers have no events and drop out.
- ``abs_zz``: value-only events of ``gen.zz`` (the date is assembly-stamped, so each event is
  timed at the first file showing the new value), absolute value, exact zeros dropped.
- ``zz_signed_khz``: the same events, signed, in kHz, ``transform="none"``.

There is no per-event noise variance for RB-derived errors or for ``zz`` in the document, so
``noise_var`` is not passed: the nugget cannot be split into estimation noise and dynamics
faster than the shortest lag from these data alone.

Summary per series: the nugget is the semivariance of the first bin with at least
``MIN_PAIRS`` pairs; the long-lag level is the mean semivariance of the bins whose lower edge
is at least 744 h. Their ratio is the share of the long-lag variance already present at the
shortest lag.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/variograms_2q.py"
MIN_PAIRS = 1000
ZZ_EDGES = (0.0, 2.0, 4.0, 6.0, 9.0, 12.0, 18.0, 30.0, 42.0, 54.0, 84.0, 132.0, 204.0, 372.0)
ZZ_EDGES = (*ZZ_EDGES, 744.0, 1488.0, 3624.0)


def summarize(vg: dict[str, Any], key: str = "semivariance") -> dict[str, Any]:
    bins = vg["bins"]
    nug = next((b for b in bins if b["pairs"] >= MIN_PAIRS and b[key] is not None), None)
    long = [b[key] for b in bins if b["lag_h_lo"] >= 744.0 and b[key] is not None]
    day = [b for b in bins if b["lag_h_lo"] == 18.0]
    out: dict[str, Any] = {
        "nugget_bin_h": [nug["lag_h_lo"], nug["lag_h_hi"]] if nug else None,
        "nugget": nug[key] if nug else None,
        "one_round_18_30h": day[0][key] if day else None,
        "long_lag_ge_744h_mean": c.rnd(float(np.mean(long))) if long else None,
    }
    if nug and long:
        out["nugget_over_long"] = c.rnd(nug[key] / float(np.mean(long)), 3)
    return out


def truncate(series: list[Any], before: bool, split: float) -> list[Any]:
    out = []
    for s in series:
        m = (s.t_ms < split) if before else (s.t_ms >= split)
        if m.sum() >= 2:
            out.append(
                ddload.Series(entity=s.entity, t_ms=s.t_ms[m], file_idx=s.file_idx[m], y=s.y[m])
            )
    return out


def per_entity_ratio(series: list[Any]) -> dict[str, Any]:
    """Per coupler: semivariance at 18-30 h over the mean at lags >= 744 h."""
    ratios = []
    for s in series:
        vg = ddload.variogram([s])
        day = [b["semivariance"] for b in vg["bins"] if b["lag_h_lo"] == 18.0]
        long = [
            b["semivariance"]
            for b in vg["bins"]
            if b["lag_h_lo"] >= 744.0 and b["semivariance"] is not None and b["pairs"] >= 30
        ]
        if day and day[0] is not None and long:
            ratios.append(day[0] / float(np.mean(long)))
    return {"couplers": len(ratios), "ratio_18_30h_over_ge_744h_q": c.q(ratios)}


def short_gap_occasions(series: list[Any], max_gap_h: float = 18.0) -> dict[str, Any]:
    """Consecutive events of one coupler less than ``max_gap_h`` apart, grouped by occasion.

    The sub-day bins of the variogram are filled only by these pairs. For each one, the half
    squared change across the short gap is compared with the same coupler's half squared
    change across the preceding gap (a normal round-to-round step), paired by coupler.
    """
    from scipy import stats

    rows = []
    for s in series:
        z = np.log10(s.y)
        gaps = np.diff(s.t_ms) / ddload.MS_PER_HOUR
        for k in range(1, gaps.size):
            if gaps[k] < max_gap_h and gaps[k - 1] >= max_gap_h:
                rows.append(
                    (
                        float(s.t_ms[k]),
                        float(gaps[k]),
                        0.5 * float(z[k + 1] - z[k]) ** 2,
                        0.5 * float(z[k] - z[k - 1]) ** 2,
                        float(gaps[k - 1]),
                    )
                )
    if not rows:
        return {"pairs": 0}
    a = np.array(rows)
    occ = c.rounds(a[:, 0], gap_h=1.0)
    starts = np.array([o[0] for o in occ])
    oid = np.searchsorted(starts, a[:, 0], side="right") - 1
    occasions = []
    for i, st in enumerate(starts):
        m = oid == i
        occasions.append(
            {
                "first_event_utc": c.iso(st),
                "couplers": int(m.sum()),
                "short_gap_h_median": c.rnd(float(np.median(a[m, 1]))),
                "semivar_short": c.rnd(float(np.mean(a[m, 2]))),
                "semivar_preceding": c.rnd(float(np.mean(a[m, 3]))),
            }
        )
    w = stats.wilcoxon(a[:, 2], a[:, 3])
    return {
        "pairs": int(a.shape[0]),
        "occasions": len(occasions),
        "occasion_list": occasions,
        "semivar_short_mean": c.rnd(float(np.mean(a[:, 2]))),
        "semivar_preceding_mean": c.rnd(float(np.mean(a[:, 3]))),
        "median_abs_change_short": c.rnd(float(np.median(np.sqrt(2 * a[:, 2])))),
        "median_abs_change_preceding": c.rnd(float(np.median(np.sqrt(2 * a[:, 3])))),
        "preceding_gap_h_q": c.q(a[:, 4]),
        "wilcoxon_short_vs_preceding_p": c.rnd(float(w.pvalue), 3),
    }


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    split = c.split_ms(dd)
    gcols = set(c.gen_columns(dd, pairs))
    out: dict[str, Any] = {"n_files": dd.n_files, "min_pairs_for_nugget": MIN_PAIRS}
    for gate in c.GATES:
        series = list(c.gate_series(dd, gate, fwd).values())
        vg = ddload.variogram(series)
        out[gate] = {
            "series": len(series),
            "events": int(sum(s.y.size for s in series)),
            "variogram": vg,
            "summary": summarize(vg),
            "summary_robust": summarize(vg, "semivariance_robust"),
            "per_coupler": per_entity_ratio(series),
            "short_gap_occasions": short_gap_occasions(series),
            "half_var_of_one_step_change": c.rnd(
                float(0.5 * np.var(np.concatenate([np.diff(np.log10(s.y)) for s in series])))
            ),
        }
        sg = out[gate]["short_gap_occasions"]
        day_bin = out[gate]["summary"]["one_round_18_30h"]
        sg["ratio_short_over_preceding"] = c.rnd(
            sg["semivar_short_mean"] / sg["semivar_preceding_mean"], 3
        )
        sg["ratio_short_over_variogram_18_30h"] = c.rnd(sg["semivar_short_mean"] / day_bin, 3)
        sg["occasions_short_below_preceding"] = int(
            sum(o["semivar_short"] < o["semivar_preceding"] for o in sg["occasion_list"])
        )
        for name, before in (("before_split", True), ("after_split", False)):
            sub = truncate(series, before, split)
            vgs = ddload.variogram(sub)
            out[gate][name] = {
                "series": len(sub),
                "summary": summarize(vgs),
                "summary_robust": summarize(vgs, "semivariance_robust"),
                "bins_compact": [
                    [b["lag_h_lo"], b["pairs"], b["semivariance"], b["semivariance_robust"]]
                    for b in vgs["bins"]
                ],
            }
    zz_events = [s for s in ddload.series(dd, "gen.zz", rule=ddload.ASSEMBLY) if s.entity in gcols]
    abs_series = []
    signed = []
    for s in zz_events:
        y = np.abs(s.y)
        m = y > 0
        if m.sum() >= 2:
            abs_series.append(
                ddload.Series(entity=s.entity, t_ms=s.t_ms[m], file_idx=s.file_idx[m], y=y[m])
            )
        signed.append(ddload.Series(entity=s.entity, t_ms=s.t_ms, file_idx=s.file_idx, y=s.y * 1e6))
    vg_abs = ddload.variogram(abs_series, edges_h=ZZ_EDGES)
    vg_signed = ddload.variogram(signed, transform="none", edges_h=ZZ_EDGES)
    out["abs_zz"] = {
        "series": len(abs_series),
        "events": int(sum(s.y.size for s in abs_series)),
        "zero_values_dropped": int(sum(int(np.sum(s.y == 0)) for s in zz_events)),
        "variogram": vg_abs,
        "summary": summarize(vg_abs),
        "summary_robust": summarize(vg_abs, "semivariance_robust"),
        "half_var_of_one_step_change": c.rnd(
            float(0.5 * np.var(np.concatenate([np.diff(np.log10(s.y)) for s in abs_series])))
        ),
    }
    for name, before in (("before_split", True), ("after_split", False)):
        sub = truncate(abs_series, before, split)
        vgs = ddload.variogram(sub, edges_h=ZZ_EDGES)
        out["abs_zz"][name] = {"series": len(sub), "summary": summarize(vgs)}
    out["zz_signed_khz"] = {
        "series": len(signed),
        "variogram": vg_signed,
        "summary": summarize(vg_signed),
        "summary_robust": summarize(vg_signed, "semivariance_robust"),
    }
    path = c.write("variograms.json", SCRIPT, out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
