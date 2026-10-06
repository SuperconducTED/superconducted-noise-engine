"""The assigned cross-family link: cz and rzz against their two qubits.

Writes ``results/gates_2q/link.json``. Loads ``g2.cz.*``, ``g2.rzz.*``, ``q.T1``, ``q.T2``,
``g1.sx.gate_error`` and ``q.readout_error`` (the grant for this link) and nothing else.

Coherence limit of a two-qubit gate of length ``t`` (the formula of P4, imported from
``scripts/feature_patterns.py`` so the two cannot drift apart): each qubit's process
fidelity under amplitude and phase damping is ``F_k = (1 + exp(-t/T1_k) + 2 exp(-t/T2_k))/4``;
for independent channels the two-qubit process fidelity is ``F_1 F_2``, and the average gate
infidelity is ``1 - (4 F_1 F_2 + 1) / 5`` (``d = 4``). It uses the T1 and T2 current in the
file where the gate event first appears; those were usually measured in a different round,
so the limit is a proxy, not a bound.

Every qubit-level covariate is the value current in the file of the gate event.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload
from scripts.feature_patterns import process_fidelity_1q

SCRIPT = "analysis/gates_2q/link_qubits.py"


def limit_2q(t1a: Any, t2a: Any, t1b: Any, t2b: Any, t_ns: Any) -> np.ndarray:
    f = process_fidelity_1q(t1a, t2a, t_ns) * process_fidelity_1q(t1b, t2b, t_ns)
    out: np.ndarray = 1.0 - (4.0 * f + 1.0) / 5.0
    return out


def partial_multi(x: np.ndarray, y: np.ndarray, controls: list[np.ndarray]) -> dict[str, Any]:
    """Rank partial correlation of x and y given several controls (rank OLS residuals)."""
    cols = [x, y, *controls]
    ok = np.all([np.isfinite(v) for v in cols], axis=0)
    n = int(ok.sum())
    if n < len(controls) + 5:
        return {"rho": None, "n": n}
    r = [stats.rankdata(v[ok]) for v in cols]
    z = np.column_stack([np.ones(n), *r[2:]])

    def resid(u: np.ndarray) -> np.ndarray:
        beta, *_ = np.linalg.lstsq(z, u, rcond=None)
        out: np.ndarray = u - z @ beta
        return out

    rho = float(np.corrcoef(resid(r[0]), resid(r[1]))[0, 1])
    return {"rho": c.rnd(rho), "n": n}


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    lab = {col: c.label(pairs[i]) for i, col in enumerate(fwd)}
    t1 = np.array(dd.v("q.T1"))
    t2 = np.array(dd.v("q.T2"))
    t1d = np.array(dd.d("q.T1"))
    t2d = np.array(dd.d("q.T2"))
    sx = np.array(dd.v("g1.sx.gate_error"))
    sx = np.where(sx < 1.0, sx, np.nan)
    ro = np.array(dd.v("q.readout_error"))
    med_t1 = float(np.nanmedian(t1))
    med_t2 = float(np.nanmedian(t2))
    p10_t1 = float(np.nanquantile(t1, 0.1))
    p10_t2 = float(np.nanquantile(t2, 0.1))
    ref = {
        "median_T1_us_all_records": c.rnd(med_t1),
        "median_T2_us_all_records": c.rnd(med_t2),
        "p10_T1_us": c.rnd(p10_t1),
        "p10_T2_us": c.rnd(p10_t2),
        "limit_at_median_T1_T2": {
            str(int(t)): c.rnd(float(limit_2q(med_t1, med_t2, med_t1, med_t2, float(t))))
            for t in (68, 84, 88, 116)
        },
        "limit_at_p10_T1_T2_both_qubits": {
            str(int(t)): c.rnd(float(limit_2q(p10_t1, p10_t2, p10_t1, p10_t2, float(t))))
            for t in (68, 116)
        },
        "first_order_check_68ns_at_median": c.rnd(
            float(0.4 * 0.068 * 2 * (1 / med_t1 + (1 / med_t2 - 0.5 / med_t1)))
        ),
        "first_order_note": "Abad et al. eq. 12: (2/5) t sum_k (1/T1_k + Gamma_phi_k), "
        "Gamma_phi = 1/T2 - 1/(2 T1)",
    }
    out: dict[str, Any] = {"n_files": dd.n_files, "reference_limits": ref}
    for gate in c.GATES:
        ser = c.gate_series(dd, gate, fwd)
        glen = np.array(dd.v(f"g2.{gate}.gate_length"))
        rows_err, rows_lim, rows_sx, rows_ro, rows_romax = [], [], [], [], []
        stale = []
        t2_gt_2t1 = 0
        med = {k: [] for k in ("err", "lim", "sx", "ro", "romax")}
        d_err, d_lim, d_sx, d_ro = [], [], [], []
        dm_err, dm_lim, dm_sx, dm_ro, dm_t1 = [], [], [], [], []
        pos = {col: i for i, col in enumerate(fwd)}
        for col, s in ser.items():
            a, b = pairs[pos[col]]
            f = s.file_idx
            lim = limit_2q(t1[f, a], t2[f, a], t1[f, b], t2[f, b], glen[f, col])
            t2_gt_2t1 += int(np.sum((t2[f, a] > 2 * t1[f, a]) | (t2[f, b] > 2 * t1[f, b])))
            sxs = sx[f, a] + sx[f, b]
            ros = ro[f, a] + ro[f, b]
            romax = np.maximum(ro[f, a], ro[f, b])
            err = s.y
            rows_err.append(err)
            rows_lim.append(lim)
            rows_sx.append(sxs)
            rows_ro.append(ros)
            rows_romax.append(romax)
            for q_ in (a, b):
                stale.extend((np.abs(s.t_ms - t1d[f, q_]) / ddload.MS_PER_HOUR).tolist())
                stale.extend((np.abs(s.t_ms - t2d[f, q_]) / ddload.MS_PER_HOUR).tolist())
            le, ll = np.log10(err), np.log10(lim)
            ls, lr = np.log10(sxs), np.log10(ros)
            lt1 = np.log10(t1[f, a] * t1[f, b])
            med["err"].append(np.nanmedian(le))
            med["lim"].append(np.nanmedian(ll))
            med["sx"].append(np.nanmedian(ls))
            med["ro"].append(np.nanmedian(lr))
            med["romax"].append(np.nanmedian(np.log10(romax)))
            d_err.extend(np.diff(le).tolist())
            d_lim.extend(np.diff(ll).tolist())
            d_sx.extend(np.diff(ls).tolist())
            d_ro.extend(np.diff(lr).tolist())
            dm_err.extend((le - np.nanmean(le)).tolist())
            dm_lim.extend((ll - np.nanmean(ll)).tolist())
            dm_sx.extend((ls - np.nanmean(ls)).tolist())
            dm_ro.extend((lr - np.nanmean(lr)).tolist())
            dm_t1.extend((lt1 - np.nanmean(lt1)).tolist())
        err = np.concatenate(rows_err)
        lim = np.concatenate(rows_lim)
        ratio = lim / err
        m = {k: np.array(v) for k, v in med.items()}
        # within-file Spearman across couplers of log err vs log limit, at every file
        v = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
        v = np.where(v < 1.0, v, np.nan)
        aa = np.array([p[0] for p in pairs])
        bb = np.array([p[1] for p in pairs])
        lim_f = limit_2q(t1[:, aa], t2[:, aa], t1[:, bb], t2[:, bb], glen[:, fwd])
        wf = []
        for i in range(0, dd.n_files, 5):
            r = c.spearman(np.log10(v[i]), np.log10(lim_f[i]))["rho"]
            if r is not None:
                wf.append(r)
        out[gate] = {
            "events": int(err.size),
            "events_with_T2_gt_2T1_on_either_qubit": t2_gt_2t1,
            "limit_q": c.q(lim),
            "limit_over_error_q": c.q(ratio),
            "share_events_limit_above_error": c.rnd(float(np.nanmean(ratio > 1))),
            "error_over_limit_median": c.rnd(float(np.nanmedian(err / lim))),
            "event_median_error": c.rnd(float(np.median(err))),
            "event_median_error_over_68ns_limit_at_median_T1_T2": c.rnd(
                float(np.median(err)) / float(limit_2q(med_t1, med_t2, med_t1, med_t2, 68.0)), 3
            ),
            "abs_hours_gate_stamp_to_T1_T2_stamps_q": c.q(stale),
            "within_file_spearman_log_err_vs_log_limit_q": c.q(wf),
            "within_file_files_sampled_every_5th": len(wf),
            "between_coupler": {
                "couplers": int(m["err"].size),
                "spearman_err_vs_limit": c.spearman(m["err"], m["lim"]),
                "spearman_err_vs_sx_sum": c.spearman(m["err"], m["sx"]),
                "spearman_err_vs_readout_sum": c.spearman(m["err"], m["ro"]),
                "spearman_err_vs_readout_max": c.spearman(m["err"], m["romax"]),
                "spearman_limit_vs_sx_sum": c.spearman(m["lim"], m["sx"]),
                "partial_err_sx_given_limit": partial_multi(m["err"], m["sx"], [m["lim"]]),
                "partial_err_limit_given_sx": partial_multi(m["err"], m["lim"], [m["sx"]]),
                "partial_err_readout_given_limit_sx": partial_multi(
                    m["err"], m["ro"], [m["lim"], m["sx"]]
                ),
            },
            "within_coupler_changes": {
                "spearman_dlog_err_vs_dlog_limit": c.spearman(d_err, d_lim),
                "spearman_dlog_err_vs_dlog_sx_sum": c.spearman(d_err, d_sx),
                "spearman_dlog_err_vs_dlog_readout_sum": c.spearman(d_err, d_ro),
            },
            "within_coupler_demeaned_levels": {
                "spearman_err_vs_limit": c.spearman(dm_err, dm_lim),
                "spearman_err_vs_sx_sum": c.spearman(dm_err, dm_sx),
                "spearman_err_vs_readout_sum": c.spearman(dm_err, dm_ro),
                "spearman_err_vs_T1_product": c.spearman(dm_err, dm_t1),
            },
        }

        # Do the shared qubit's current sx and T1 explain the correlated deviations of two
        # couplers that share it (spatial_2q.py measured that correlation)?
        stamps = np.concatenate([s.t_ms for s in ser.values()])
        rd = c.rounds(stamps)
        starts = np.array([r[0] for r in rd])
        n_c = len(pairs)
        dev = np.full((len(rd), n_c), np.nan)
        fil = np.full((len(rd), n_c), -1, dtype=np.int64)
        for col, s in ser.items():
            if s.y.size < 8:
                continue
            rid = np.searchsorted(starts, s.t_ms, side="right") - 1
            dev[rid, pos[col]] = c.moving_median_deviation(np.log10(s.y))
            fil[rid, pos[col]] = s.file_idx
        dev = dev - np.nanmedian(dev, axis=1, keepdims=True)
        lsx = np.log10(sx)
        lt1 = np.log10(t1)
        sx_dev = lsx - np.nanmedian(lsx, axis=0)
        t1_dev = lt1 - np.nanmedian(lt1, axis=0)
        lro = np.log10(ro)
        ro_dev = lro - np.nanmedian(lro, axis=0)
        xr: list[float] = []
        xi, xj, xs, xt = [], [], [], []
        for i in range(n_c):
            for j in range(i + 1, n_c):
                shared = set(pairs[i]) & set(pairs[j])
                if not shared:
                    continue
                qq = shared.pop()
                ok = np.isfinite(dev[:, i]) & np.isfinite(dev[:, j])
                for r in np.flatnonzero(ok):
                    fi = fil[r, i]
                    xi.append(dev[r, i])
                    xj.append(dev[r, j])
                    xs.append(sx_dev[fi, qq])
                    xt.append(t1_dev[fi, qq])
                    xr.append(ro_dev[fi, qq])
        xi_a, xj_a, xs_a, xt_a = (np.array(v) for v in (xi, xj, xs, xt))
        xr_a = np.array(xr)
        out[gate]["shared_qubit_pairs"] = {
            "rows": int(xi_a.size),
            "spearman_dev_i_vs_dev_j": c.spearman(xi_a, xj_a),
            "spearman_dev_i_vs_shared_qubit_sx_dev": c.spearman(xi_a, xs_a),
            "spearman_dev_i_vs_shared_qubit_T1_dev": c.spearman(xi_a, xt_a),
            "partial_dev_i_dev_j_given_sx_T1": partial_multi(xi_a, xj_a, [xs_a, xt_a]),
            "spearman_dev_i_vs_shared_qubit_readout_dev": c.spearman(xi_a, xr_a),
            "partial_dev_i_dev_j_given_sx_T1_readout": partial_multi(
                xi_a, xj_a, [xs_a, xt_a, xr_a]
            ),
        }

    # Faulty couplers: are their qubits healthy?
    qubits = sorted({27, 28, 32, 33, 71, 72, 73, 95, 99, 115, 102, 103})
    t1_med_q = np.nanmedian(t1, axis=0)
    t2_med_q = np.nanmedian(t2, axis=0)
    sx_med_q = np.nanmedian(sx, axis=0)
    ro_med_q = np.nanmedian(ro, axis=0)
    sx_raw = np.array(dd.v("g1.sx.gate_error"))

    def pct(arr: np.ndarray, qv: int) -> float | None:
        ok = np.isfinite(arr)
        if not np.isfinite(arr[qv]):
            return None
        return c.rnd(float(np.mean(arr[ok] <= arr[qv])), 3)

    out["faulty_coupler_qubits"] = {
        str(qv): {
            "sx_placeholder_share": c.rnd(float(np.mean(sx_raw[:, qv] >= 1.0))),
            "sx_median": c.rnd(float(sx_med_q[qv])) if np.isfinite(sx_med_q[qv]) else None,
            "sx_percentile": pct(sx_med_q, qv),
            "T1_median_us": c.rnd(float(t1_med_q[qv])) if np.isfinite(t1_med_q[qv]) else None,
            "T1_percentile": pct(t1_med_q, qv),
            "T2_median_us": c.rnd(float(t2_med_q[qv])) if np.isfinite(t2_med_q[qv]) else None,
            "T2_percentile": pct(t2_med_q, qv),
            "readout_median": c.rnd(float(ro_med_q[qv])),
            "readout_percentile": pct(ro_med_q, qv),
        }
        for qv in qubits
    }
    out["percentile_note"] = "share of the 156 qubits whose median is at or below this one"
    out["labels_note"] = f"{len(lab)} canonical couplers"
    path = c.write("link.json", SCRIPT, out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
