"""sx against T1, T2 and its coherence limit (the scope's assigned cross-family link).

Writes ``results/gates_1q/sx_coherence.json``. Unit: MEASURED sx events (placeholders
masked), each matched to the nearest T1 event and the nearest T2 event of the same qubit
whose stamp lies within MATCH_H hours; unmatched sx events are counted and skipped.

Coherence limit of a gate of length t (average gate infidelity of an idle of that length
under amplitude and phase damping), as in Qiskit Experiments ``RBUtils.coherence_limit``
for one qubit and ``scripts/feature_patterns.coherence_limit_1q``:

    e_coh = 0.5 * (1 - (2/3) exp(-t/T2) - (1/3) exp(-t/T1))

with t from ``g1.sx.gate_length`` (ns) and T1, T2 in us.

Within-qubit co-movement uses deviations from a running level (median of up to 5 events
each side, self excluded) computed on each field's OWN event series; the null pairs each sx
event with the T1 (or T2) event k matches away (k = +-3 .. +-20), which keeps both marginal
distributions and breaks the same-round pairing.
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
import g1common as g

SCRIPT = "analysis/gates_1q/sx_coherence.py"
MATCH_H = 6.0
RNG = np.random.default_rng(20261006)
N_BOOT = 2000
SHIFTS = [k for k in range(-20, 21) if abs(k) >= 3]
DIP_LOG = {"factor_1.5": np.log10(1.5), "factor_2": g.LOG10_2}


def coh_limit(t1_us: np.ndarray, t2_us: np.ndarray, t_ns: float) -> np.ndarray:
    t = t_ns * 1e-3
    out: np.ndarray = 0.5 * (
        1.0 - (2.0 / 3.0) * np.exp(-t / t2_us) - (1.0 / 3.0) * np.exp(-t / t1_us)
    )
    return out


def build(dd: ddload.DD, t_ns: float) -> dict[str, Any]:
    sx = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    t1 = {s.entity: s for s in ddload.series(dd, "q.T1", rule=ddload.MEASURED)}
    t2 = {s.entity: s for s in ddload.series(dd, "q.T2", rule=ddload.MEASURED)}
    rows: list[dict[str, Any]] = []
    n_events, n_unmatched = 0, 0
    off1_all, off2_all = [], []
    for s in sx:
        n_events += s.y.size
        if s.entity not in t1 or s.entity not in t2:
            n_unmatched += s.y.size
            continue
        a, b = t1[s.entity], t2[s.entity]
        za, zb = np.log10(a.y), np.log10(b.y)
        da = za - g.running_level(za)
        db = zb - g.running_level(zb)
        i1, o1 = g.nearest(s.t_ms, a.t_ms)
        i2, o2 = g.nearest(s.t_ms, b.t_ms)
        off1_all.append(o1)
        off2_all.append(o2)
        ok = (np.abs(o1) <= MATCH_H) & (np.abs(o2) <= MATCH_H)
        n_unmatched += int((~ok).sum())
        idx = np.flatnonzero(ok)
        if idx.size < 10:
            continue
        t1m = a.y[i1[idx]]
        t2m = b.y[i2[idx]]
        e = s.y[idx]
        ec = coh_limit(t1m, t2m, t_ns)
        ze = np.log10(e)
        zc = np.log10(ec)
        rows.append(
            {
                "q": s.entity,
                "t": s.t_ms[idx],
                "e": e,
                "ec": ec,
                "T1": t1m,
                "T2": t2m,
                "d_sx": ze - g.running_level(ze),
                "d_coh": zc - g.running_level(zc),
                "lvl_sx": g.running_level(ze),
                "lvl_coh": g.running_level(zc),
                "i1": i1[idx],
                "i2": i2[idx],
                "da": da,
                "db": db,
                "d_T1": da[i1[idx]],
                "d_T2": db[i2[idx]],
                "o1": o1[idx],
                "o2": o2[idx],
            }
        )
    return {
        "rows": rows,
        "n_events": n_events,
        "n_unmatched": n_unmatched,
        "off1": np.concatenate(off1_all),
        "off2": np.concatenate(off2_all),
    }


def ratios(rows: list[dict[str, Any]], t_ns: float) -> dict[str, Any]:
    e = np.concatenate([r["e"] for r in rows])
    ec = np.concatenate([r["ec"] for r in rows])
    t1m = np.concatenate([r["T1"] for r in rows])
    t2m = np.concatenate([r["T2"] for r in rows])
    ratio = ec / e
    unphys = t2m > 2.0 * t1m
    t = t_ns * 1e-3
    first = t / (6.0 * t1m) + t / (3.0 * t2m)
    t1_term = (1.0 - np.exp(-t / t1m)) / 6.0
    per_q = np.array([float(np.median(r["ec"] / r["e"])) for r in rows])
    return {
        "matched_events": int(e.size),
        "coh_limit_q": g.q(ec, nd=8),
        "ratio_coh_over_sx_q": g.q(ratio, (0.0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0), 4),
        "share_ratio_gt_1": g.rnd(float(np.mean(ratio > 1.0)), 4),
        "share_ratio_gt_0.5": g.rnd(float(np.mean(ratio > 0.5)), 4),
        "matches_T2_gt_2T1": int(unphys.sum()),
        "share_T2_gt_2T1": g.rnd(float(np.mean(unphys)), 5),
        "ratio_q_excluding_T2_gt_2T1": g.q(ratio[~unphys], (0.1, 0.5, 0.9), 4),
        "share_ratio_gt_1_among_T2_gt_2T1": g.rnd(float(np.mean(ratio[unphys] > 1.0)), 4)
        if unphys.any()
        else None,
        "first_order_max_rel_diff": float(f"{float(np.max(np.abs(first - ec) / ec)):.3g}"),
        "t1_term_share_of_limit_q": g.q(t1_term / ec, (0.1, 0.5, 0.9), 4),
        "per_qubit_median_ratio_q": g.q(per_q, nd=4),
        "qubits": len(rows),
        "qubits_with_median_ratio_gt_1": [
            {
                "qubit": int(r["q"]),
                "median_ratio": g.rnd(float(np.median(r["ec"] / r["e"])), 3),
                "median_T1_us": g.rnd(float(np.median(r["T1"])), 2),
                "median_T2_us": g.rnd(float(np.median(r["T2"])), 2),
                "median_sx": float(f"{float(np.median(r['e'])):.4g}"),
            }
            for r in rows
            if float(np.median(r["ec"] / r["e"])) > 1.0
        ],
        "device_median_T1_us_matched": g.rnd(float(np.median(t1m)), 2),
        "device_median_T2_us_matched": g.rnd(float(np.median(t2m)), 2),
    }


def between(rows: list[dict[str, Any]]) -> dict[str, Any]:
    m = np.array(
        [
            [
                float(np.median(np.log10(r["e"]))),
                float(np.median(np.log10(r["ec"]))),
                float(np.median(np.log10(r["T1"]))),
                float(np.median(np.log10(r["T2"]))),
            ]
            for r in rows
        ]
    )
    out: dict[str, Any] = {"qubits": int(m.shape[0]), "bootstrap": f"{N_BOOT} resamples of qubits"}
    names = ("coh_limit", "T1", "T2")
    boots = np.empty((N_BOOT, 3))
    n = m.shape[0]
    for b in range(N_BOOT):
        idx = RNG.integers(0, n, n)
        mb = m[idx]
        for k in range(3):
            boots[b, k] = stats.spearmanr(mb[:, 0], mb[:, k + 1]).statistic
    for k, nm in enumerate(names):
        sp = g.spearman(m[:, 0], m[:, k + 1])
        sp["ci95"] = [g.rnd(float(v), 4) for v in np.quantile(boots[:, k], [0.025, 0.975])]
        out[f"spearman_median_log_sx_vs_{nm}"] = sp
    out["pearson_median_logs_sx_vs_coh_limit"] = g.rnd(
        float(np.corrcoef(m[:, 0], m[:, 1])[0, 1]), 4
    )
    out["theil_sen_median_log_sx_on_median_log_coh"] = g.theil_sen(m[:, 1], m[:, 0])
    return out


def pooled_spearman(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    return float(stats.spearmanr(x[ok], y[ok]).statistic)


def within(rows: list[dict[str, Any]]) -> dict[str, Any]:
    d_sx = np.concatenate([r["d_sx"] for r in rows])
    out: dict[str, Any] = {}
    for nm, key, src, idx in (("T1", "d_T1", "da", "i1"), ("T2", "d_T2", "db", "i2")):
        obs = pooled_spearman(d_sx, np.concatenate([r[key] for r in rows]))
        null = []
        for k in SHIFTS:
            xs, ys = [], []
            for r in rows:
                j = r[idx] + k
                ok = (j >= 0) & (j < r[src].size)
                xs.append(r["d_sx"][ok])
                ys.append(r[src][j[ok]])
            null.append(pooled_spearman(np.concatenate(xs), np.concatenate(ys)))
        nl = np.array(null)
        per_q = np.array([g.spearman(r["d_sx"], r[key])["rho"] or np.nan for r in rows])
        out[nm] = {
            "pooled_spearman_dev_sx_vs_dev": g.rnd(obs, 4),
            "null_shifted_mean": g.rnd(float(nl.mean()), 4),
            "null_shifted_sd": g.rnd(float(nl.std()), 4),
            "null_shifted_min_max": [g.rnd(float(nl.min()), 4), g.rnd(float(nl.max()), 4)],
            "n_shifts": len(SHIFTS),
            "per_qubit_spearman_q": g.q(per_q, (0.1, 0.25, 0.5, 0.75, 0.9), 4),
            "per_qubit_share_negative": g.rnd(float(np.mean(per_q[np.isfinite(per_q)] < 0)), 3),
        }
    d_coh = np.concatenate([r["d_coh"] for r in rows])
    out["coh_limit"] = {"pooled_spearman_dev_sx_vs_dev_coh": g.rnd(pooled_spearman(d_sx, d_coh), 4)}
    ok = np.isfinite(d_sx) & np.isfinite(d_coh)
    edges = np.quantile(d_coh[ok], np.linspace(0, 1, 11))
    b = np.clip(np.searchsorted(edges, d_coh[ok], side="right") - 1, 0, 9)
    out["coh_limit"]["median_dev_sx_by_dev_coh_decile"] = [
        {
            "dev_coh_median": g.rnd(float(np.median(d_coh[ok][b == k])), 4),
            "dev_sx_median": g.rnd(float(np.median(d_sx[ok][b == k])), 4),
            "n": int(np.sum(b == k)),
        }
        for k in range(10)
    ]
    dx, dc = [], []
    for r in rows:
        dx.append(np.diff(np.log10(r["e"])))
        dc.append(np.diff(np.log10(r["ec"])))
    out["consecutive_changes_spearman_dlog_sx_vs_dlog_coh"] = g.spearman(
        np.concatenate(dx), np.concatenate(dc)
    )
    return out


def xslow_floor(rows: list[dict[str, Any]], dd: ddload.DD) -> dict[str, Any]:
    """Coherence limit of a pulse of xslow's recorded length against the error it reports.

    xslow's error equals sx's in every record (aliases_and_schema.json), so the sx events
    stamped while xslow records exist give the xslow values.
    """
    lengths = np.array(dd.v("g1.xslow.gate_length"))
    uniq = sorted(set(lengths[np.isfinite(lengths)].tolist()))
    if len(uniq) != 1:
        raise ValueError(f"xslow length is not constant: {uniq}")
    t_x = float(uniq[0])
    xv = np.array(dd.v("g1.xslow.gate_error"))
    pres = np.isfinite(xv).any(axis=1)
    fm = dd.file_ms[pres]
    windows: list[tuple[float, float]] = []
    idx = np.flatnonzero(pres)
    br = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[0], br + 1])
    ends = np.concatenate([br, [idx.size - 1]])
    windows = [(float(fm[a]), float(fm[b])) for a, b in zip(starts, ends, strict=True)]
    ratio_all, ratio_in, t1_only_in = [], [], []
    for r in rows:
        lim = coh_limit(r["T1"], r["T2"], t_x)
        lim_t1 = coh_limit(r["T1"], 2.0 * r["T1"], t_x)  # T2 = 2 T1: no pure dephasing
        rr = lim / r["e"]
        ratio_all.append(rr)
        inside = np.zeros(r["t"].size, dtype=bool)
        for a, b in windows:
            inside |= (r["t"] >= a) & (r["t"] <= b)
        ratio_in.append(rr[inside])
        t1_only_in.append((lim_t1 / r["e"])[inside])
    ra, ri = np.concatenate(ratio_all), np.concatenate(ratio_in)
    r1 = np.concatenate(t1_only_in)
    return {
        "xslow_gate_length_ns": t_x,
        "presence_windows": [[g.iso(a), g.iso(b)] for a, b in windows],
        "all_matched_events": {
            "n": int(ra.size),
            "limit_over_reported_q": g.q(ra, (0.1, 0.5, 0.9), 3),
            "share_limit_above_reported": g.rnd(float(np.mean(ra > 1.0)), 4),
        },
        "events_inside_xslow_windows": {
            "n": int(ri.size),
            "limit_over_reported_q": g.q(ri, (0.1, 0.5, 0.9), 3),
            "share_limit_above_reported": g.rnd(float(np.mean(ri > 1.0)), 4),
            "t1_only_limit_over_reported_q": g.q(r1, (0.1, 0.5, 0.9), 3),
            "share_t1_only_limit_above_reported": g.rnd(float(np.mean(r1 > 1.0)), 4),
        },
    }


def by_offset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Same-round coupling of deviations, split by how far apart the two stamps are."""
    d_sx = np.concatenate([r["d_sx"] for r in rows])
    t_all = np.concatenate([r["t"] for r in rows])
    months = np.array(g.month_of(t_all))
    out: dict[str, Any] = {"bootstrap": f"{N_BOOT // 4} resamples of qubits"}
    for nm, key, okey in (("T1", "d_T1", "o1"), ("T2", "d_T2", "o2")):
        d = np.concatenate([r[key] for r in rows])
        o = np.abs(np.concatenate([r[okey] for r in rows]))
        res: dict[str, Any] = {}
        for lab, sel in (("abs_offset_le_1h", o <= 1.0), ("abs_offset_1_to_6h", o > 1.0)):
            res[lab] = g.spearman(d_sx[sel], d[sel])
        per = [(r["d_sx"], r[key], np.abs(r[okey]) <= 1.0) for r in rows]
        diffs, near, far = [], [], []
        for _ in range(N_BOOT // 4):
            idx = RNG.integers(0, len(per), len(per))
            xs = np.concatenate([per[i][0] for i in idx])
            ys = np.concatenate([per[i][1] for i in idx])
            ss = np.concatenate([per[i][2] for i in idx])
            a = pooled_spearman(xs[ss], ys[ss])
            b = pooled_spearman(xs[~ss], ys[~ss])
            near.append(a)
            far.append(b)
            diffs.append(a - b)
        res["near_ci95"] = [g.rnd(float(v), 4) for v in np.quantile(near, [0.025, 0.975])]
        res["far_ci95"] = [g.rnd(float(v), 4) for v in np.quantile(far, [0.025, 0.975])]
        res["near_minus_far_ci95"] = [
            g.rnd(float(v), 4) for v in np.quantile(diffs, [0.025, 0.975])
        ]
        res["share_le_1h_by_month"] = {
            m: g.rnd(float(np.mean(o[months == m] <= 1.0)), 3) for m in sorted(set(months.tolist()))
        }
        res["by_month_near_far_rho"] = {
            m: {
                "near": g.spearman(d_sx[(months == m) & (o <= 1.0)], d[(months == m) & (o <= 1.0)]),
                "far": g.spearman(d_sx[(months == m) & (o > 1.0)], d[(months == m) & (o > 1.0)]),
            }
            for m in ("2026-05", "2026-06", "2026-07", "2026-08", "2026-09")
        }
        out[nm] = res
    return out


def volatility(rows: list[dict[str, Any]], dd: ddload.DD) -> dict[str, Any]:
    """Between qubits: is a qubit's sx volatility related to its T1 or T2 volatility?"""
    t1 = {s.entity: s for s in ddload.series(dd, "q.T1", rule=ddload.MEASURED)}
    t2 = {s.entity: s for s in ddload.series(dd, "q.T2", rule=ddload.MEASURED)}

    def rsd(y: np.ndarray) -> float:
        dz = np.diff(np.log10(y))
        return 1.4826 * float(np.median(np.abs(dz - np.median(dz)))) / np.sqrt(2.0)

    def spike_rate(y: np.ndarray, sign: float) -> float:
        z = np.log10(y)
        r = sign * (z - g.running_level(z))
        ok = np.isfinite(r)
        return float(np.mean(r[ok] > g.LOG10_2))

    m = []
    for r in rows:
        q_ = r["q"]
        m.append(
            [
                rsd(r["e"]),
                rsd(t1[q_].y),
                rsd(t2[q_].y),
                spike_rate(r["e"], 1.0),
                spike_rate(t1[q_].y, -1.0),
                spike_rate(t2[q_].y, -1.0),
                float(np.median(np.log10(r["e"]))),
            ]
        )
    a = np.array(m)

    def partial(x: np.ndarray, y: np.ndarray, c: np.ndarray) -> float:
        rx, ry, rc = stats.rankdata(x), stats.rankdata(y), stats.rankdata(c)
        ex = rx - np.polyval(np.polyfit(rc, rx, 1), rc)
        ey = ry - np.polyval(np.polyfit(rc, ry, 1), rc)
        return float(np.corrcoef(ex, ey)[0, 1])

    return {
        "qubits": int(a.shape[0]),
        "robust_change_size": "1.4826 * MAD(log10 changes) / sqrt(2) on each field's own events",
        "spearman_sx_rsd_vs_T1_rsd": g.spearman(a[:, 0], a[:, 1]),
        "spearman_sx_rsd_vs_T2_rsd": g.spearman(a[:, 0], a[:, 2]),
        "partial_spearman_sx_rsd_vs_T1_rsd_given_sx_level": g.rnd(
            partial(a[:, 0], a[:, 1], a[:, 6]), 4
        ),
        "partial_spearman_sx_rsd_vs_T2_rsd_given_sx_level": g.rnd(
            partial(a[:, 0], a[:, 2], a[:, 6]), 4
        ),
        "spike_rate_definition": "sx: deviation above +log10(2); T1, T2: below -log10(2)",
        "spearman_sx_spike_rate_vs_T1_dip_rate": g.spearman(a[:, 3], a[:, 4]),
        "spearman_sx_spike_rate_vs_T2_dip_rate": g.spearman(a[:, 3], a[:, 5]),
    }


def coincidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    d_sx = np.concatenate([r["d_sx"] for r in rows])
    spike = d_sx > g.LOG10_2
    valid = np.isfinite(d_sx)
    out: dict[str, Any] = {
        "spike_definition": "sx deviation from its running level above log10(2)",
        "spikes": int(np.sum(spike & valid)),
        "events": int(valid.sum()),
    }
    for nm, key, src, idx in (("T1", "d_T1", "da", "i1"), ("T2", "d_T2", "db", "i2")):
        d = np.concatenate([r[key] for r in rows])
        ok = valid & np.isfinite(d)
        res: dict[str, Any] = {
            "median_dev_at_spikes": g.rnd(float(np.median(d[ok & spike])), 4),
            "median_dev_at_non_spikes": g.rnd(float(np.median(d[ok & ~spike])), 4),
        }
        for lab, thr in DIP_LOG.items():
            dip = d < -thr
            a = int(np.sum(ok & spike & dip))
            b_ = int(np.sum(ok & spike & ~dip))
            c = int(np.sum(ok & ~spike & dip))
            dd_ = int(np.sum(ok & ~spike & ~dip))
            fe = stats.fisher_exact([[a, b_], [c, dd_]])
            null = []
            for k in SHIFTS:
                hits, tot = 0, 0
                for r in rows:
                    j = r[idx] + k
                    sel = (j >= 0) & (j < r[src].size) & (r["d_sx"] > g.LOG10_2)
                    dn = r[src][j[sel]]
                    hits += int(np.sum(dn < -thr))
                    tot += int(np.sum(np.isfinite(dn)))
                null.append(hits / max(1, tot))
            res[lab] = {
                "p_dip_given_spike": g.rnd(a / max(1, a + b_), 4),
                "p_dip_given_no_spike": g.rnd(c / max(1, c + dd_), 4),
                "table_spike_dip": [[a, b_], [c, dd_]],
                "odds_ratio": g.rnd(float(fe.statistic), 3),
                "fisher_p": float(f"{float(fe.pvalue):.3g}"),
                "null_shifted_p_dip_given_spike_mean": g.rnd(float(np.mean(null)), 4),
                "null_shifted_p_dip_given_spike_max": g.rnd(float(np.max(null)), 4),
                "p_spike_given_dip": g.rnd(a / max(1, a + c), 4),
                "p_spike_overall": g.rnd(float(np.mean(spike[ok])), 4),
            }
        out[nm] = res
    share, share_dip = [], []
    for r in rows:
        sp = r["d_sx"] > g.LOG10_2
        ok = sp & np.isfinite(r["lvl_coh"]) & np.isfinite(r["lvl_sx"])
        d_e = r["e"][ok] - 10 ** r["lvl_sx"][ok]
        d_c = r["ec"][ok] - 10 ** r["lvl_coh"][ok]
        share.append(d_c / d_e)
        share_dip.append((d_c / d_e)[r["d_T1"][ok] < -DIP_LOG["factor_1.5"]])
    sh = np.concatenate(share)
    shd = np.concatenate(share_dip)
    out["excess_accounted_by_coh_limit"] = {
        "definition": "at sx spikes: (e_coh - 10^level_coh) / (e_sx - 10^level_sx)",
        "spikes": int(sh.size),
        "q": g.q(sh, (0.1, 0.25, 0.5, 0.75, 0.9), 4),
        "share_ge_0.5": g.rnd(float(np.mean(sh >= 0.5)), 4),
        "at_spikes_with_T1_dip_factor_1.5": {
            "spikes": int(shd.size),
            "q": g.q(shd, (0.1, 0.5, 0.9), 4),
        },
    }
    return out


def offsets(b: dict[str, Any]) -> dict[str, Any]:
    o1, o2 = b["off1"], b["off2"]
    out: dict[str, Any] = {"window_h": MATCH_H}
    for nm, o in (("T1", o1), ("T2", o2)):
        out[nm] = {
            "offset_h_q": g.q(o, (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99), 3),
            "share_abs_le_1h": g.rnd(float(np.mean(np.abs(o) <= 1.0)), 4),
            "share_abs_le_3h": g.rnd(float(np.mean(np.abs(o) <= 3.0)), 4),
            "share_abs_le_6h": g.rnd(float(np.mean(np.abs(o) <= MATCH_H)), 4),
            "share_before_sx": g.rnd(float(np.mean(o < 0)), 4),
        }
    out["sx_events"] = b["n_events"]
    out["sx_events_unmatched_skipped"] = b["n_unmatched"]
    return out


def placeholder_qubits(dd: ddload.DD) -> dict[str, Any]:
    t1v = np.array(dd.v("q.T1"))
    t2v = np.array(dd.v("q.T2"))
    sxv = np.array(dd.v(g.SX_FIELD))
    out: dict[str, Any] = {
        "q72": {
            "T1_absent_files": int(np.sum(~np.isfinite(t1v[:, 72]))),
            "T2_absent_files": int(np.sum(~np.isfinite(t2v[:, 72]))),
            "T1_median_when_present_us": g.rnd(float(np.nanmedian(t1v[:, 72])), 2),
            "device_T1_median_us": g.rnd(float(np.nanmedian(t1v)), 2),
        }
    }
    t1d = np.array(dd.d("q.T1"))
    t2d = np.array(dd.d("q.T2"))
    fm = dd.file_ms
    for qb in (17, 149):
        ph = sxv[:, qb] >= 1.0
        real = np.isfinite(sxv[:, qb]) & ~ph
        fidx = np.flatnonzero(ph)
        stale = t1d[fidx[-1], qb]
        same = np.flatnonzero(t1d[:, qb] == stale)
        out[f"q{qb}_stamps"] = {
            "T1_stamp_in_last_placeholder_file": g.iso(stale),
            "files_carrying_that_T1_stamp": int(same.size),
            "files_carrying_that_T1_stamp_first_last": [dd.stems[same[0]], dd.stems[same[-1]]],
            "placeholder_files_carrying_that_T1_stamp": int(np.sum(np.isin(fidx, same))),
            "distinct_T1_values_in_placeholder_files": int(np.unique(t1v[ph, qb]).size),
            "distinct_T1_stamps_in_placeholder_files": int(np.unique(t1d[ph, qb]).size),
            "distinct_T2_stamps_in_placeholder_files": int(np.unique(t2d[ph, qb]).size),
            "T1_stamp_age_at_file_h_in_placeholder_files_q_0_50_100": g.q(
                (fm[fidx] - t1d[fidx, qb]) / g.HOUR_MS, (0.0, 0.5, 1.0), 1
            ),
            "T2_stamp_age_at_file_h_in_placeholder_files_q_0_50_100": g.q(
                (fm[fidx] - t2d[fidx, qb]) / g.HOUR_MS, (0.0, 0.5, 1.0), 1
            ),
        }
        out[f"q{qb}"] = {
            "placeholder_files": int(ph.sum()),
            "T1_median_us_in_placeholder_files": g.rnd(float(np.nanmedian(t1v[ph, qb])), 2),
            "T1_median_us_other_files": g.rnd(float(np.nanmedian(t1v[real, qb])), 2),
            "T2_median_us_in_placeholder_files": g.rnd(float(np.nanmedian(t2v[ph, qb])), 2),
            "T2_median_us_other_files": g.rnd(float(np.nanmedian(t2v[real, qb])), 2),
            "sx_median_other_files": float(f"{float(np.nanmedian(sxv[real, qb])):.4g}"),
            "T1_files_in_placeholder_q_10_50_90": g.q(t1v[ph, qb], (0.1, 0.5, 0.9), 2),
            "T1_files_other_q_10_50_90": g.q(t1v[real, qb], (0.1, 0.5, 0.9), 2),
        }
    return out


def main() -> int:
    dd = ddload.DD()
    lengths = np.array(dd.v("g1.sx.gate_length"))
    uniq = sorted(set(lengths[np.isfinite(lengths)].tolist()))
    if len(uniq) != 1:
        raise ValueError(f"sx length is not constant: {uniq}")
    t_ns = float(uniq[0])
    b = build(dd, t_ns)
    rows = b["rows"]
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["sx_gate_length_ns"] = t_ns
    payload["formula"] = "e_coh = 0.5 * (1 - (2/3) exp(-t/T2) - (1/3) exp(-t/T1))"
    payload["matching"] = offsets(b)
    payload["ratio"] = ratios(rows, t_ns)
    payload["between_qubits"] = between(rows)
    payload["within_qubits"] = within(rows)
    payload["coincidence"] = coincidence(rows)
    payload["within_by_stamp_offset"] = by_offset(rows)
    payload["volatility_between_qubits"] = volatility(rows, dd)
    payload["xslow_coherence_floor"] = xslow_floor(rows, dd)
    payload["placeholder_qubits"] = placeholder_qubits(dd)
    ddload.write_json(g.RESULTS / "sx_coherence.json", payload)
    print("wrote", g.RESULTS / "sx_coherence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
