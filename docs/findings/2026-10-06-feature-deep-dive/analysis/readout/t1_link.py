"""Assigned cross-family link: readout errors against T1 decay during the readout.

Writes ``results/readout/t1_link.json``. For every readout-session event the decay expected
over the readout is computed from the ``T1`` carried by the same file and the readout length
of that file: ``d_full = 1 - exp(-t_ro / T1)`` and ``d_half = 1 - exp(-t_ro / (2 T1))`` (the
effective time of Krantz et al. 2019, eq. 173, is the resonator delay plus half the
integration time, so the truth sits between the two when the delay is short). The asymmetry
``A = P(0|1) - P(1|0)`` removes, to first order, the symmetric overlap error both states share.

Between qubits: per-qubit medians. Within qubits: the daily ``even`` sessions only (87% of
them start within 3 h of a ``T1`` round, ``sessions.json``), so each value has a near-
contemporaneous ``T1``; changes between consecutive even sessions of the same qubit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc


def main() -> None:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    ns = rc.noise_series(r, c, s)
    t1 = np.array(dd.v("q.T1"), dtype=np.float64)
    d_t1 = np.array(dd.d("q.T1"), dtype=np.float64)
    t_ro = np.array(dd.v("q.readout_length"), dtype=np.float64)

    cols: dict[str, list[np.ndarray]] = {
        k: [] for k in ("q", "t", "kind", "p0", "p1", "ro", "t1", "t1_stamp", "tro", "file")
    }
    for a, b, x, kind in zip(
        ns["p0g1_fresh"].series,
        ns["p1g0"].series,
        ns["ro"].series,
        ns["p0g1_fresh"].kind,
        strict=True,
    ):
        y0, y1 = np.asarray(a.y), np.asarray(b.y)
        ok = np.isfinite(y0) & np.isfinite(y1)
        f = a.file_idx[ok]
        cols["q"].append(np.full(f.size, a.entity))
        cols["t"].append(a.t_ms[ok])
        cols["kind"].append(kind[ok])
        cols["p0"].append(y0[ok])
        cols["p1"].append(y1[ok])
        cols["ro"].append(np.asarray(x.y)[ok])
        cols["t1"].append(t1[f, a.entity])
        cols["t1_stamp"].append(d_t1[f, a.entity])
        cols["tro"].append(t_ro[f, a.entity])
        cols["file"].append(f)
    rec = {k: np.concatenate(v) for k, v in cols.items()}
    good = np.isfinite(rec["t1"]) & (rec["t1"] > 0)
    rec = {k: v[good] for k, v in rec.items()}
    d_full = 1.0 - np.exp(-rec["tro"] * 1e-3 / rec["t1"])
    d_half = 1.0 - np.exp(-rec["tro"] * 1e-3 / (2.0 * rec["t1"]))
    asym = rec["p0"] - rec["p1"]
    pos = rec["p1"] > 0
    out: dict[str, Any] = {
        "n_files": dd.n_files,
        "events": int(good.sum()),
        "events_dropped_no_t1": int((~good).sum()),
        "pooled": {
            "share_p0g1_gt_p1g0": round(float(np.mean(rec["p0"] > rec["p1"])), 4),
            "share_p0g1_eq_p1g0": round(float(np.mean(rec["p0"] == rec["p1"])), 4),
            "ratio_p0g1_over_p1g0_q": rc.quantiles(rec["p0"][pos] / rec["p1"][pos]),
            "asymmetry_q": rc.quantiles(asym),
            "decay_full_q": rc.quantiles(d_full),
            "decay_half_q": rc.quantiles(d_half),
            "p0g1_q": rc.quantiles(rec["p0"]),
            "spearman_p0g1_vs_decay_full_pooled": rc.spearman(rec["p0"], d_full),
            "spearman_asymmetry_vs_decay_full_pooled": rc.spearman(asym, d_full),
            "t1_age_h_at_event_q": rc.quantiles((rec["t"] - rec["t1_stamp"]) / 3.6e6),
        },
    }
    # Between qubits.
    qs = np.unique(rec["q"])
    med = {
        k: np.array([np.median(v[rec["q"] == q]) for q in qs])
        for k, v in (
            ("p0", rec["p0"]),
            ("p1", rec["p1"]),
            ("ro", rec["ro"]),
            ("asym", asym),
            ("d_full", d_full),
            ("d_half", d_half),
            ("t1", rec["t1"]),
        )
    }
    ts = stats.theilslopes(med["asym"], med["d_full"])
    out["between_qubits"] = {
        "qubits": int(qs.size),
        "spearman_p0g1_vs_decay": rc.spearman(med["p0"], med["d_full"]),
        "spearman_asymmetry_vs_decay": rc.spearman(med["asym"], med["d_full"]),
        "spearman_p1g0_vs_decay_control": rc.spearman(med["p1"], med["d_full"]),
        "spearman_p0g1_vs_p1g0": rc.spearman(med["p0"], med["p1"]),
        "theil_sen_asymmetry_on_decay_full": {
            "slope": round(float(ts.slope), 4),
            "slope_95ci": [round(float(ts.low_slope), 4), round(float(ts.high_slope), 4)],
            "intercept": float(f"{ts.intercept:.4g}"),
        },
        "per_qubit_asymmetry_over_decay_full_q": rc.quantiles(med["asym"] / med["d_full"]),
        "per_qubit_p0g1_over_decay_full_q": rc.quantiles(med["p0"] / med["d_full"]),
        "share_qubits_asymmetry_lt_decay_half": round(
            float(np.mean(med["asym"] < med["d_half"])), 4
        ),
        "share_qubits_asymmetry_lt_decay_full": round(
            float(np.mean(med["asym"] < med["d_full"])), 4
        ),
        "share_qubits_asymmetry_negative": round(float(np.mean(med["asym"] < 0)), 4),
    }
    # Low-error qubits only (median ro below the device median), where overlap is small.
    low = med["ro"] <= np.median(med["ro"])
    ts_low = stats.theilslopes(med["asym"][low], med["d_full"][low])
    out["between_qubits_low_error_half"] = {
        "qubits": int(low.sum()),
        "spearman_asymmetry_vs_decay": rc.spearman(med["asym"][low], med["d_full"][low]),
        "theil_sen_slope": round(float(ts_low.slope), 4),
        "theil_sen_95ci": [round(float(ts_low.low_slope), 4), round(float(ts_low.high_slope), 4)],
        "per_qubit_asymmetry_over_decay_full_q": rc.quantiles(
            med["asym"][low] / med["d_full"][low]
        ),
    }
    # Within qubits: even sessions, consecutive changes.
    ev = rec["kind"] == "even"
    d0, d1, dt = [], [], []
    lv0, lv1, lt = [], [], []
    for q in qs:
        m = ev & (rec["q"] == q)
        idx = np.flatnonzero(m)
        if idx.size < 10:
            continue
        order = idx[np.argsort(rec["t"][idx])]
        p0 = rec["p0"][order]
        p1 = rec["p1"][order]
        tt = rec["t1"][order]
        okk = (p0 > 0) & (p1 > 0)
        p0, p1, tt = p0[okk], p1[okk], tt[okk]
        newt = np.diff(tt) != 0
        d0.append(np.diff(np.log10(p0))[newt])
        d1.append(np.diff(np.log10(p1))[newt])
        dt.append(np.diff(np.log10(tt))[newt])
        lv0.append(np.log10(p0) - np.mean(np.log10(p0)))
        lv1.append(np.log10(p1) - np.mean(np.log10(p1)))
        lt.append(np.log10(tt) - np.mean(np.log10(tt)))
    d0c, d1c, dtc = np.concatenate(d0), np.concatenate(d1), np.concatenate(dt)
    out["within_qubits_even_sessions"] = {
        "consecutive_changes_with_new_t1": int(d0c.size),
        "spearman_dlog_p0g1_vs_dlog_t1": rc.spearman(d0c, dtc),
        "spearman_dlog_p1g0_vs_dlog_t1_control": rc.spearman(d1c, dtc),
        "levels_spearman_log_p0g1_vs_log_t1_demeaned": rc.spearman(
            np.concatenate(lv0), np.concatenate(lt)
        ),
        "levels_spearman_log_p1g0_vs_log_t1_demeaned_control": rc.spearman(
            np.concatenate(lv1), np.concatenate(lt)
        ),
    }
    # Event study: even-session records where T1 is below half of the qubit's median T1.
    rel_t1 = np.empty(rec["t1"].size)
    rel_p0 = np.empty(rec["t1"].size)
    rel_p1 = np.empty(rec["t1"].size)
    for q in qs:
        m = rec["q"] == q
        rel_t1[m] = rec["t1"][m] / np.median(rec["t1"][m & ev]) if np.any(m & ev) else np.nan
        rel_p0[m] = rec["p0"][m] / np.median(rec["p0"][m & ev]) if np.any(m & ev) else np.nan
        rel_p1[m] = (
            rec["p1"][m] / max(np.median(rec["p1"][m & ev]), 1.0 / rc.SHOTS)
            if np.any(m & ev)
            else np.nan
        )
    dip = ev & (rel_t1 < 0.5)
    norm = ev & (rel_t1 >= 0.8) & (rel_t1 <= 1.25)
    exp_dip = []
    for q in qs:
        m = dip & (rec["q"] == q)
        if m.any():
            dfull_med = np.median(d_full[ev & (rec["q"] == q)])
            exp_dip.append(np.median(d_full[m]) - dfull_med)
    dip_shift = [
        np.median(rec["p0"][dip & (rec["q"] == q)]) - np.median(rec["p0"][ev & (rec["q"] == q)])
        for q in np.unique(rec["q"][dip])
    ]
    out["t1_dip_event_study_even_sessions"] = {
        "dip_records_t1_lt_half_median": int(dip.sum()),
        "dip_qubits": int(np.unique(rec["q"][dip]).size),
        "normal_records": int(norm.sum()),
        "median_rel_p0g1_dip": round(float(np.median(rel_p0[dip])), 4),
        "median_rel_p0g1_normal": round(float(np.median(rel_p0[norm])), 4),
        "median_rel_p1g0_dip_control": round(float(np.median(rel_p1[dip])), 4),
        "median_rel_p1g0_normal_control": round(float(np.median(rel_p1[norm])), 4),
        "mannwhitney_p_rel_p0g1": float(
            f"{stats.mannwhitneyu(rel_p0[dip], rel_p0[norm]).pvalue:.3g}"
        ),
        "median_excess_decay_full_in_dip": float(f"{np.median(exp_dip):.4g}"),
        "median_abs_p0g1_change_in_dip": float(f"{np.median(dip_shift):.4g}"),
    }
    # The same, restricted to records whose T1 stamp is within 3 h of the readout stamp.
    near = np.abs(rec["t"] - rec["t1_stamp"]) <= 3.0 * 3.6e6
    dip3, norm3 = dip & near, norm & near
    out["t1_dip_event_study_t1_within_3h"] = {
        "dip_records": int(dip3.sum()),
        "dip_qubits": int(np.unique(rec["q"][dip3]).size),
        "normal_records": int(norm3.sum()),
        "median_rel_p0g1_dip": round(float(np.median(rel_p0[dip3])), 4),
        "median_rel_p0g1_normal": round(float(np.median(rel_p0[norm3])), 4),
        "median_rel_p1g0_dip_control": round(float(np.median(rel_p1[dip3])), 4),
        "mannwhitney_p_rel_p0g1": float(
            f"{stats.mannwhitneyu(rel_p0[dip3], rel_p0[norm3]).pvalue:.3g}"
        ),
        "share_even_records_with_t1_within_3h": round(float(np.mean(near[ev])), 4),
    }
    within3 = ev & near
    d0n, dtn = [], []
    for q in qs:
        idx = np.flatnonzero(within3 & (rec["q"] == q))
        if idx.size < 10:
            continue
        order = idx[np.argsort(rec["t"][idx])]
        p0 = rec["p0"][order]
        tt = rec["t1"][order]
        okk = p0 > 0
        p0, tt = p0[okk], tt[okk]
        newt = np.diff(tt) != 0
        d0n.append(np.diff(np.log10(p0))[newt])
        dtn.append(np.diff(np.log10(tt))[newt])
    out["within_qubits_even_sessions"]["t1_within_3h_spearman_dlog_p0g1_vs_dlog_t1"] = rc.spearman(
        np.concatenate(d0n), np.concatenate(dtn)
    )
    # Over time: monthly device medians.
    months = np.array([rc.iso(x)[:7] for x in rec["t"]])
    monthly = {}
    for mo in sorted(set(months)):
        m = months == mo
        mq = np.unique(rec["q"][m])
        a_med = np.array([np.median(asym[m & (rec["q"] == q)]) for q in mq])
        d_med = np.array([np.median(d_full[m & (rec["q"] == q)]) for q in mq])
        monthly[mo] = {
            "events": int(m.sum()),
            "median_asymmetry": float(f"{np.median(asym[m]):.4g}"),
            "median_decay_full": float(f"{np.median(d_full[m]):.4g}"),
            "median_p0g1": float(f"{np.median(rec['p0'][m]):.4g}"),
            "median_p1g0": float(f"{np.median(rec['p1'][m]):.4g}"),
            "between_qubit_spearman_asym_vs_decay": rc.spearman(a_med, d_med),
        }
    out["monthly"] = monthly
    rc.write("t1_link.json", "t1_link.py", out)


if __name__ == "__main__":
    main()
