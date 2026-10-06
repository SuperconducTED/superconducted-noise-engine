"""The non-persistent component of readout: shot noise, the excess over it, and its structure.

Writes ``results/readout/noise.json``:

1. ``old_method``: the 2026-10-05 P5 figure re-computed at this ref with the same code path
   (measured-rule events of ``readout_error``, 4,096 shots everywhere, published P(0|1)).
2. ``consecutive``: standardized changes ``z = (y_j - y_i) / sqrt(var_i + var_j)`` between
   consecutive readout-session events, with the variance from the session's own shots (2,048
   in ``even`` sessions, 4,096 in ``mixed``) and the fresh P(0|1). Under pure binomial noise
   around a fixed level, ``z`` has unit variance and 95.45% of ``|z|`` fall below 2.
3. ``variograms``: ``ddload.variogram`` with ``noise_var`` (log10 and linear), pooled and by
   session kind, plus a standardized variogram (mean and median of ``z^2`` per lag bin; under
   pure noise the robust ratio ``median(z^2) / 0.4549`` is 1 at every lag).
4. ``shots_test``: whether the ``even`` sessions behave as 2,048-shot estimates, by comparing
   the excess over noise of ``even`` and ``mixed`` pairs at the same lag under both readings.
5. ``threshold_test``: are changes larger across a discriminator-threshold change?
6. ``common_mode`` and ``neighbours``: is part of the change device-wide or shared by
   coupled qubits?
"""

from __future__ import annotations

import itertools
import sys
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc

MEDIAN_CHI2_1 = 0.454936  # median of a chi-square with one degree of freedom
REPORT_BINS = ((2.0, 4.0), (4.0, 6.0), (18.0, 30.0), (744.0, 1488.0), (1488.0, 3624.0))


def old_method(dd: ddload.DD, r: rc.Readout) -> dict[str, Any]:
    """P5's shot-noise check, as written in scripts/feature_patterns.py, at this ref."""
    series = ddload.series(dd, "q.readout_error", rule=ddload.MEASURED)
    ratio: list[np.ndarray] = []
    sd_single: list[np.ndarray] = []
    for s in series:
        a = r.p0g1[s.file_idx, s.entity]
        b = r.p1g0[s.file_idx, s.entity]
        var = (a * (1 - a) + b * (1 - b)) / (4.0 * rc.SHOTS)
        sd_log = 0.4343 * np.sqrt(var) / s.y
        sd_single.append(sd_log)
        sd_diff = np.sqrt(sd_log[1:] ** 2 + sd_log[:-1] ** 2)
        ratio.append(np.abs(np.diff(np.log10(s.y))) / sd_diff)
    rr = np.concatenate(ratio)
    rr = rr[np.isfinite(rr)]
    return {
        "events_rule": "measured (value and stamp new)",
        "changes": int(rr.size),
        "sd_log10_single_estimate_q": rc.quantiles(np.concatenate(sd_single)),
        "share_changes_within_2sd": round(float(np.mean(rr < 2.0)), 4),
        "abs_change_over_noise_sd_q": rc.quantiles(rr),
    }


def pairs_consecutive(ns: rc.NoiseSeries, log: bool) -> dict[str, np.ndarray]:
    zs, lags, kinds, ent, f_i, f_j, dz = [], [], [], [], [], [], []
    for s, var, kind in zip(ns.series, ns.var, ns.kind, strict=True):
        y = np.asarray(s.y)
        ok = np.isfinite(y) & np.isfinite(var)
        if log:
            ok &= y > 0
        idx = np.flatnonzero(ok)
        if idx.size < 2:
            continue
        yy = np.log10(y[idx]) if log else y[idx]
        vv = rc.log10_var(y[idx], var[idx]) if log else var[idx]
        d = np.diff(yy)
        s2 = vv[1:] + vv[:-1]
        z = np.where(s2 > 0, d / np.sqrt(np.where(s2 > 0, s2, 1.0)), np.nan)
        zs.append(z)
        dz.append(d)
        lags.append(np.diff(s.t_ms[idx]) / 3.6e6)
        k = kind[idx]
        kinds.append(np.array([f"{min(a, b)}-{max(a, b)}" for a, b in itertools.pairwise(k)]))
        ent.append(np.full(d.size, s.entity))
        f_i.append(s.file_idx[idx][:-1])
        f_j.append(s.file_idx[idx][1:])
    return {
        "z": np.concatenate(zs),
        "d": np.concatenate(dz),
        "lag_h": np.concatenate(lags),
        "kind": np.concatenate(kinds),
        "entity": np.concatenate(ent),
        "file_i": np.concatenate(f_i),
        "file_j": np.concatenate(f_j),
    }


def z_summary(z: np.ndarray) -> dict[str, Any]:
    z = z[np.isfinite(z)]
    if z.size == 0:
        return {"n": 0}
    mad = float(np.median(np.abs(z - np.median(z))))
    return {
        "n": int(z.size),
        "share_abs_z_lt_2": round(float(np.mean(np.abs(z) < 2.0)), 4),
        "robust_variance_ratio_median_z2": round(float(np.median(z * z) / MEDIAN_CHI2_1), 3),
        "robust_variance_ratio_mad": round((1.4826 * mad) ** 2, 3),
        "mean_z2": round(float(np.mean(z * z)), 3),
        "abs_z_q": rc.quantiles(np.abs(z)),
    }


def std_variogram(ns: rc.NoiseSeries, edges: tuple[float, ...], log: bool) -> list[dict[str, Any]]:
    e = np.asarray(edges)
    nb = e.size - 1
    buckets: list[list[np.ndarray]] = [[] for _ in range(nb)]
    for s, var in zip(ns.series, ns.var, strict=True):
        y = np.asarray(s.y)
        ok = np.isfinite(y) & np.isfinite(var)
        if log:
            ok &= y > 0
        idx = np.flatnonzero(ok)
        if idx.size < 2:
            continue
        yy = np.log10(y[idx]) if log else y[idx]
        vv = rc.log10_var(y[idx], var[idx]) if log else var[idx]
        t = s.t_ms[idx] / 3.6e6
        iu, ju = np.triu_indices(idx.size, k=1)
        s2 = vv[iu] + vv[ju]
        good = s2 > 0
        z2 = (yy[ju] - yy[iu])[good] ** 2 / s2[good]
        b = np.searchsorted(e, (t[ju] - t[iu])[good], side="right") - 1
        inside = (b >= 0) & (b < nb)
        for k in np.unique(b[inside]):
            buckets[k].append(z2[inside & (b == k)])
    out = []
    for k in range(nb):
        z2 = np.concatenate(buckets[k]) if buckets[k] else np.empty(0)
        out.append(
            {
                "lag_h_lo": float(e[k]),
                "lag_h_hi": float(e[k + 1]),
                "pairs": int(z2.size),
                "mean_z2": round(float(np.mean(z2)), 3) if z2.size else None,
                "robust_ratio": round(float(np.median(z2) / MEDIAN_CHI2_1), 3) if z2.size else None,
            }
        )
    return out


def restrict(ns: rc.NoiseSeries, kind: str) -> rc.NoiseSeries:
    out = rc.NoiseSeries([], [], [])
    for s, var, k in zip(ns.series, ns.var, ns.kind, strict=True):
        keep = k == kind
        out.series.append(
            ddload.Series(
                entity=s.entity, t_ms=s.t_ms, file_idx=s.file_idx, y=np.where(keep, s.y, np.nan)
            )
        )
        out.var.append(np.where(keep, var, np.nan))
        out.kind.append(k)
    return out


def vario(ns: rc.NoiseSeries, log: bool) -> dict[str, Any]:
    if log:
        nv = [rc.log10_var(np.asarray(s.y), v) for s, v in zip(ns.series, ns.var, strict=True)]
        series = [
            ddload.Series(
                entity=s.entity,
                t_ms=s.t_ms,
                file_idx=s.file_idx,
                y=np.where(np.isfinite(v), s.y, np.nan),
            )
            for s, v in zip(ns.series, nv, strict=True)
        ]
        res = ddload.variogram(series, transform="log10", noise_var=nv)
    else:
        series = [
            ddload.Series(
                entity=s.entity,
                t_ms=s.t_ms,
                file_idx=s.file_idx,
                y=np.where(np.isfinite(v), s.y, np.nan),
            )
            for s, v in zip(ns.series, ns.var, strict=True)
        ]
        res = ddload.variogram(series, transform="none", noise_var=ns.var)
    return res


def decompose(v: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for lo, hi in REPORT_BINS:
        for b in v["bins"]:
            if b["lag_h_lo"] == lo and b["lag_h_hi"] == hi and b["pairs"]:
                sv, nz = b["semivariance"], b["noise_part"]
                rows.append(
                    {
                        "lag_h": f"{lo:g}-{hi:g}",
                        "pairs": b["pairs"],
                        "semivariance": sv,
                        "noise_part": nz,
                        "excess": round(sv - nz, 8),
                        "noise_share": round(nz / sv, 4) if sv else None,
                        "semivariance_robust": b["semivariance_robust"],
                    }
                )
    return rows


def hop_matrix(dd: ddload.DD) -> np.ndarray:
    n = len(dd.meta["qubits"])
    adj: list[set[int]] = [set() for _ in range(n)]
    for a, b in dd.meta["coupling_map"]:
        adj[a].add(b)
        adj[b].add(a)
    dist = np.full((n, n), -1, dtype=np.int64)
    for s in range(n):
        dist[s, s] = 0
        dq = deque([s])
        while dq:
            u = dq.popleft()
            for w in adj[u]:
                if dist[s, w] < 0:
                    dist[s, w] = dist[s, u] + 1
                    dq.append(w)
    return dist


def main() -> None:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    ns = rc.noise_series(r, c, s)
    out: dict[str, Any] = {"n_files": dd.n_files, "old_method": old_method(dd, r)}

    # Coverage of the noise series: what was dropped and why.
    tot = sum(x.y.size for x in ns["ro"].series)
    kept = sum(int(np.sum(np.isfinite(x.y))) for x in ns["ro"].series)
    kinds_all = np.concatenate(ns["ro"].kind)
    out["coverage"] = {
        "ro_stamp_events": int(tot),
        "kept_with_noise_variance": int(kept),
        "dropped": int(tot - kept),
        "events_by_session_kind": {
            k: int(np.sum(kinds_all == k)) for k in ("even", "mixed", "small", "none")
        },
        "restamps_within_session_dropped": ns["ro"].restamps_within_session,
        "p1g0_zero_events_dropped_from_log": int(
            sum(int(np.sum(np.asarray(x.y) == 0)) for x in ns["p1g0"].series)
        ),
    }

    # Consecutive standardized changes.
    cons: dict[str, Any] = {}
    pair_cache: dict[str, dict[str, np.ndarray]] = {}
    for field in ("ro", "p0g1_fresh", "p1g0"):
        for log in (False, True):
            key = f"{field}_{'log10' if log else 'linear'}"
            p = pairs_consecutive(ns[field], log)
            pair_cache[key] = p
            entry: dict[str, Any] = {"all": z_summary(p["z"])}
            for kk in ("even-even", "even-mixed", "mixed-mixed"):
                entry[kk] = z_summary(p["z"][p["kind"] == kk])
            for lo, hi in ((0.0, 6.0), (6.0, 30.0), (30.0, 1e9)):
                sel = (p["lag_h"] > lo) & (p["lag_h"] <= hi) & (p["kind"] == "mixed-mixed")
                entry[f"mixed-mixed_lag_{lo:g}_{hi:g}h"] = z_summary(p["z"][sel])
            cons[key] = entry
    out["consecutive"] = cons

    # Variograms (shared function) with the shot-noise part, pooled and by session kind.
    varios: dict[str, Any] = {}
    for field in ("ro", "p0g1_fresh", "p1g0"):
        for log in (True, False):
            tag = "log10" if log else "linear"
            v_all = vario(ns[field], log)
            v_mix = vario(restrict(ns[field], "mixed"), log)
            v_even = vario(restrict(ns[field], "even"), log)
            varios[f"{field}_{tag}"] = {
                "all": {"bins": v_all["bins"], "decomposition": decompose(v_all)},
                "mixed_only": {"decomposition": decompose(v_mix)},
                "even_only": {"decomposition": decompose(v_even)},
            }
    out["variograms"] = varios

    # Standardized variograms (per-pair z^2), robust to the mix of qubit levels.
    edges = ddload.VARIOGRAM_EDGES_H
    out["standardized_variograms"] = {
        "ro_linear": std_variogram(ns["ro"], edges, log=False),
        "p0g1_fresh_linear": std_variogram(ns["p0g1_fresh"], edges, log=False),
        "p1g0_linear": std_variogram(ns["p1g0"], edges, log=False),
        "ro_linear_mixed_only": std_variogram(restrict(ns["ro"], "mixed"), edges, log=False),
        "ro_linear_even_only": std_variogram(restrict(ns["ro"], "even"), edges, log=False),
        "p0g1_fresh_linear_mixed_only": std_variogram(
            restrict(ns["p0g1_fresh"], "mixed"), edges, log=False
        ),
        "p1g0_linear_mixed_only": std_variogram(restrict(ns["p1g0"], "mixed"), edges, log=False),
    }

    # Shots test (log10, where the noise part is a visible share): the semivariance of
    # even-only pairs minus that of mixed-only pairs at the same lag, against the difference
    # each reading predicts (2,048 shots: the even noise part as computed; 4,096 shots: half
    # of it). Also on the qubits whose median value is at least 0.01, where the delta method
    # holds for P(1|0) too (at least about 20 counts in an even session).
    shots: dict[str, Any] = {}
    for field in ("ro", "p0g1_fresh", "p1g0"):
        meds = np.array([np.nanmedian(np.asarray(x.y)) for x in ns[field].series])
        for subset, keep_q in (("all_qubits", meds > -1.0), ("median_ge_0.01", meds >= 0.01)):
            sub = rc.NoiseSeries(
                [x for x, k in zip(ns[field].series, keep_q, strict=True) if k],
                [v for v, k in zip(ns[field].var, keep_q, strict=True) if k],
                [kk for kk, k in zip(ns[field].kind, keep_q, strict=True) if k],
            )
            d_mix = decompose(vario(restrict(sub, "mixed"), log=True))
            d_even = decompose(vario(restrict(sub, "even"), log=True))
            rows = []
            for a in d_mix:
                for b in d_even:
                    if a["lag_h"] == b["lag_h"] and a["lag_h"] in (
                        "18-30",
                        "744-1488",
                        "1488-3624",
                    ):
                        obs = b["semivariance"] - a["semivariance"]
                        pred_2048 = b["noise_part"] - a["noise_part"]
                        pred_4096 = b["noise_part"] / 2.0 - a["noise_part"]
                        rows.append(
                            {
                                "lag_h": a["lag_h"],
                                "qubits": int(keep_q.sum()),
                                "even_minus_mixed_semivariance": round(obs, 6),
                                "predicted_if_2048": round(pred_2048, 6),
                                "predicted_if_4096": round(pred_4096, 6),
                                "even_pairs": b["pairs"],
                                "mixed_pairs": a["pairs"],
                            }
                        )
            shots[f"{field}_{subset}"] = rows
    out["shots_test"] = shots

    # Zero-count test of the shot reading, on P(1|0): per qubit, the share of exact zeros in
    # mixed sessions fixes the Poisson mean lam = -ln(P0) of the 4,096-shot count. Predicted
    # zeros in even sessions: sqrt(P0) under 2,048 shots; exp(-lam) (1 + lam) if 4,096-shot
    # counts were rounded half-to-even (or floored) onto the 1/2048 grid; P0 if rounded up.
    obs_z, pred_sqrt, pred_floor, pred_same, n_even_tot, q_used = 0, 0.0, 0.0, 0.0, 0, 0
    pooled_set: set[int] = set()
    for x, kind in zip(ns["p1g0"].series, ns["p1g0"].kind, strict=True):
        y = np.asarray(x.y)
        mm = (kind == "mixed") & np.isfinite(y)
        me = (kind == "even") & np.isfinite(y)
        if mm.sum() < 50 or me.sum() < 20:
            continue
        p0 = float(np.mean(y[mm] == 0))
        if not 0.0 < p0 < 1.0:
            continue
        lam = -np.log(p0)
        q_used += 1
        pooled_set.add(x.entity)
        n_e = int(me.sum())
        n_even_tot += n_e
        obs_z += int(np.sum(y[me] == 0))
        pred_sqrt += n_e * float(np.sqrt(p0))
        pred_floor += n_e * float(np.exp(-lam) * (1.0 + lam))
        pred_same += n_e * p0
    # Second estimate: the local Poisson mean from the mixed sessions within 12 h of each even
    # event (mean of their P(1|0) times 4,096). Pooling P0 over time over-predicts sqrt(P0)
    # (Jensen), while a local mean under-predicts every convex zero probability, so the two
    # estimates bracket each reading's prediction.
    loc = {k: np.zeros(5) for k in ("all", "pooled_set")}  # n, observed, 2048, floor, up
    for x, kind in zip(ns["p1g0"].series, ns["p1g0"].kind, strict=True):
        y = np.asarray(x.y)
        t = x.t_ms / 3.6e6
        mm = np.flatnonzero((kind == "mixed") & np.isfinite(y))
        if mm.size == 0:
            continue
        for i in np.flatnonzero((kind == "even") & np.isfinite(y)):
            near = mm[np.abs(t[mm] - t[i]) <= 12.0]
            if near.size == 0:
                continue
            lam_l = float(np.mean(y[near])) * rc.SHOTS
            row = np.array(
                [
                    1.0,
                    float(y[i] == 0),
                    float(np.exp(-lam_l / 2.0)),
                    float(np.exp(-lam_l) * (1.0 + lam_l)),
                    float(np.exp(-lam_l)),
                ]
            )
            loc["all"] += row
            if x.entity in pooled_set:
                loc["pooled_set"] += row
    out["zero_count_test_p1g0_local"] = {
        k: {
            "even_events": int(v[0]),
            "observed_zeros_even": int(v[1]),
            "predicted_if_2048_shots": round(float(v[2]), 1),
            "predicted_if_4096_rounded_half_even_or_floor": round(float(v[3]), 1),
            "predicted_if_4096_rounded_up": round(float(v[4]), 1),
        }
        for k, v in loc.items()
    }
    out["zero_count_test_p1g0_local"]["rule"] = (
        "every even event with at least one mixed event of the qubit within 12 h; "
        "pooled_set = the qubits of the pooled test"
    )
    out["zero_count_test_p1g0"] = {
        "qubits_used": q_used,
        "even_events": n_even_tot,
        "observed_zeros_even": obs_z,
        "predicted_if_2048_shots": round(pred_sqrt, 1),
        "predicted_if_4096_rounded_half_even_or_floor": round(pred_floor, 1),
        "predicted_if_4096_rounded_up": round(pred_same, 1),
        "rule": "qubits with >= 50 mixed and >= 20 even events and 0 < P0_mixed < 1",
    }

    # Session pairs: the robust ratio of the standardized change between two whole sessions,
    # one value per session pair, so that a few sessions cannot weigh as many qubit pairs.
    n_s = s.start_ms.size
    sp: dict[str, Any] = {}
    for field in ("ro", "p0g1_fresh", "p1g0"):
        yv = np.full((n_s, 156), np.nan)
        vv = np.full((n_s, 156), np.nan)
        for x, var in zip(ns[field].series, ns[field].var, strict=True):
            si = s.index(x.t_ms)
            okk = (si >= 0) & np.isfinite(np.asarray(x.y)) & np.isfinite(var)
            yv[si[okk], x.entity] = np.asarray(x.y)[okk]
            vv[si[okk], x.entity] = var[okk]
        recs = []
        for a in range(n_s):
            for b in range(a + 1, n_s):
                lag = (s.start_ms[b] - s.start_ms[a]) / 3.6e6
                if lag > 12.0:
                    break
                okk = np.isfinite(yv[a]) & np.isfinite(yv[b]) & ((vv[a] + vv[b]) > 0)
                if okk.sum() < rc.MIN_SESSION_QUBITS:
                    continue
                z2 = (yv[b, okk] - yv[a, okk]) ** 2 / (vv[a, okk] + vv[b, okk])
                kinds = "-".join(sorted((str(s.kind[a]), str(s.kind[b]))))
                recs.append((lag, float(np.median(z2) / MEDIAN_CHI2_1), kinds, s.start_ms[a]))
        lags = np.array([x[0] for x in recs])
        ratios = np.array([x[1] for x in recs])
        kinds_a = np.array([x[2] for x in recs])
        t0 = np.array([x[3] for x in recs])
        rows = []
        for lo, hi in ((0, 0.5), (0.5, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 9), (9, 12)):
            for label, km in (
                ("all", np.ones(lags.size, bool)),
                ("mixed-mixed", kinds_a == "mixed-mixed"),
            ):
                sel = (lags > lo) & (lags <= hi) & km
                if not sel.any():
                    continue
                rows.append(
                    {
                        "lag_h": f"{lo:g}-{hi:g}",
                        "pairs_of": label,
                        "session_pairs": int(sel.sum()),
                        "robust_ratio_median_over_session_pairs": round(
                            float(np.median(ratios[sel])), 3
                        ),
                        "robust_ratio_q25_q75": [
                            round(float(np.quantile(ratios[sel], 0.25)), 3),
                            round(float(np.quantile(ratios[sel], 0.75)), 3),
                        ],
                        "first_last_session": [
                            rc.iso(float(t0[sel].min())),
                            rc.iso(float(t0[sel].max())),
                        ],
                    }
                )
        sp[field] = rows
    out["session_pairs"] = sp

    # Threshold test: are consecutive ro changes larger across a threshold change?
    th = np.array(dd.v("g1.measure.threshold"))
    first_th = int(np.flatnonzero(np.isfinite(th).any(axis=1))[0])
    chg = np.zeros(th.shape[0], dtype=bool)
    chg[1:] = np.any((th[1:] != th[:-1]) & np.isfinite(th[1:]) & np.isfinite(th[:-1]), axis=1)
    cum = np.cumsum(chg)
    p = pair_cache["ro_linear"]
    life = p["file_i"] >= first_th
    across = (cum[p["file_j"]] - cum[p["file_i"]]) > 0
    thr: dict[str, Any] = {
        "threshold_change_files": int(chg.sum()),
        "first_threshold_file": dd.stems[first_th][:15],
    }
    for label, sel in (
        ("all_pairs", life),
        ("mixed-mixed", life & (p["kind"] == "mixed-mixed")),
        (
            "mixed-mixed_lag_2_6h",
            life & (p["kind"] == "mixed-mixed") & (p["lag_h"] > 2) & (p["lag_h"] <= 6),
        ),
    ):
        za = np.abs(p["z"][sel & across])
        zb = np.abs(p["z"][sel & ~across])
        za, zb = za[np.isfinite(za)], zb[np.isfinite(zb)]
        mw = stats.mannwhitneyu(za, zb, alternative="two-sided") if za.size and zb.size else None
        thr[label] = {
            "across_change": z_summary(p["z"][sel & across]),
            "no_change": z_summary(p["z"][sel & ~across]),
            "mannwhitney_p_abs_z": float(f"{mw.pvalue:.3g}") if mw is not None else None,
            "median_abs_z_ratio": round(float(np.median(za) / np.median(zb)), 4)
            if za.size and zb.size
            else None,
        }
    out["threshold_test"] = thr

    # Common mode: share of the variance of log10 ro changes explained by the session mean.
    pl = pair_cache["ro_log10"]
    # Map each consecutive pair to the session of its later event.
    later_t = []
    for x in ns["ro"].series:
        y = np.asarray(x.y)
        idx = np.flatnonzero(np.isfinite(y) & (y > 0))
        later_t.append(x.t_ms[idx][1:])
    later_s = s.index(np.concatenate(later_t))
    cm: dict[str, Any] = {}
    for label, sel in (
        ("mixed-mixed", pl["kind"] == "mixed-mixed"),
        ("even-even", pl["kind"] == "even-even"),
        ("all", np.ones(pl["d"].size, dtype=bool)),
    ):
        d = pl["d"][sel]
        g = later_s[sel]
        okk = np.isfinite(d) & (g >= 0)
        d, g = d[okk], g[okk]
        uniq, inv = np.unique(g, return_inverse=True)
        means = np.bincount(inv, weights=d) / np.bincount(inv)
        ss_between = float(np.sum((means[inv] - d.mean()) ** 2))
        ss_total = float(np.sum((d - d.mean()) ** 2))
        cm[label] = {
            "changes": int(d.size),
            "sessions": int(uniq.size),
            "share_variance_session_mean": round(ss_between / ss_total, 4),
            "expected_share_if_independent": round(uniq.size / d.size, 4),
            "session_mean_change_q": rc.quantiles(means),
        }
    out["common_mode"] = cm

    # Neighbours: correlation of session-demeaned log10 ro changes, coupled vs far qubits.
    n_s = s.start_ms.size
    m = np.full((n_s, 156), np.nan)
    sel = (pl["kind"] == "mixed-mixed") & (later_s >= 0)
    m[later_s[sel], pl["entity"][sel]] = pl["d"][sel]
    rows_ok = np.sum(np.isfinite(m), axis=1) >= rc.MIN_SESSION_QUBITS
    m = m[rows_ok]
    m = m - np.nanmean(m, axis=1, keepdims=True)
    dist = hop_matrix(dd)
    iu, ju = np.triu_indices(156, k=1)
    corr = np.full(iu.size, np.nan)
    for k, (a, b) in enumerate(zip(iu, ju, strict=True)):
        okk = np.isfinite(m[:, a]) & np.isfinite(m[:, b])
        if okk.sum() > 30:
            corr[k] = np.corrcoef(m[okk, a], m[okk, b])[0, 1]
    hops = dist[iu, ju]
    nb: dict[str, Any] = {"sessions_used": int(rows_ok.sum())}
    for label, mask in (("1_hop", hops == 1), ("2_hops", hops == 2), ("ge_4_hops", hops >= 4)):
        cc = corr[mask & np.isfinite(corr)]
        nb[label] = {
            "pairs": int(cc.size),
            "median_corr": round(float(np.median(cc)), 4),
            "mean_corr": round(float(np.mean(cc)), 4),
            "q": rc.quantiles(cc),
        }
    a1 = corr[(hops == 1) & np.isfinite(corr)]
    a4 = corr[(hops >= 4) & np.isfinite(corr)]
    nb["mannwhitney_p_1hop_vs_ge4"] = float(f"{stats.mannwhitneyu(a1, a4).pvalue:.3g}")
    nb["top_1hop_pairs"] = [
        {"pair": [int(iu[k]), int(ju[k])], "corr": round(float(corr[k]), 4)}
        for k in np.argsort(-np.where((hops == 1) & np.isfinite(corr), corr, -9))[:5]
    ]
    out["neighbours"] = nb
    # Summary of the root-question numbers, derived here so that every figure the document
    # quotes is a stored field.
    summary: dict[str, Any] = {}
    for field in ("ro", "p0g1_fresh", "p1g0"):
        sv = {
            b["lag_h_lo"]: b for b in out["standardized_variograms"][f"{field}_linear_mixed_only"]
        }
        dec = {
            row["lag_h"]: row
            for row in out["variograms"][f"{field}_log10"]["mixed_only"]["decomposition"]
        }
        nug, long_, longest = (
            sv[2.0]["robust_ratio"],
            sv[744.0]["robust_ratio"],
            sv[1488.0]["robust_ratio"],
        )
        summary[field] = {
            "standardized_robust_ratio_2_4h_mixed": nug,
            "standardized_robust_ratio_18_30h_mixed": sv[18.0]["robust_ratio"],
            "standardized_robust_ratio_744_1488h_mixed": long_,
            "standardized_robust_ratio_1488_3624h_mixed": longest,
            "shot_noise_share_of_2_4h_robust_semivariance": round(1.0 / nug, 3),
            "excess_over_shot_noise_2_4h_in_noise_units": round(nug - 1.0, 3),
            "nugget_over_744_1488h_robust": round(nug / long_, 3),
            "log10_semivariance_2_4h_mixed": dec["2-4"]["semivariance"],
            "log10_noise_part_2_4h_mixed": dec["2-4"]["noise_part"],
            "log10_noise_share_2_4h_mixed": dec["2-4"]["noise_share"],
            "log10_semivariance_744_1488h_mixed": dec["744-1488"]["semivariance"],
            "log10_nugget_over_744_1488h": round(
                dec["2-4"]["semivariance"] / dec["744-1488"]["semivariance"], 3
            ),
            "log10_excess_2_4h_over_744_1488h_semivariance": round(
                dec["2-4"]["excess"] / dec["744-1488"]["semivariance"], 3
            ),
        }
    summary["share_changes_within_2sd_old_method"] = out["old_method"]["share_changes_within_2sd"]
    summary["share_changes_within_2sd_mixed_mixed_ro_linear"] = out["consecutive"]["ro_linear"][
        "mixed-mixed"
    ]["share_abs_z_lt_2"]
    out["summary"] = summary
    out["notes"] = {
        "median_chi2_1": MEDIAN_CHI2_1,
        "pure_noise_share_abs_z_lt_2": 0.9545,
        "log_scale_caveat": "delta method; unreliable for P(1|0) counts near 0",
    }
    rc.write("noise.json", "noise.py", out)


if __name__ == "__main__":
    main()
