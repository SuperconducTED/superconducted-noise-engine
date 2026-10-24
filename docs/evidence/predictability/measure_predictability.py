"""Per-qubit predictability of calibration drift: the ladder below the deep model.

Implements the pre-registered protocol in ``README.md`` (section 2 and its 2.1 amendment).
Event view (increment autocorrelation, local-level cap, reversion regression) and horizon
view (persistence, shrinkage, ridge, rolling band, split-conformal bands, common-mode share),
in log target space, on the rows and split of ``../persistence-band``.

Run from the repository root with the pinned interpreter::

    PYTHONPATH=src:. python docs/evidence/predictability/measure_predictability.py \
        --repo . --ref 5828b4a2 --out <dir>

Outputs ``summary.json``, ``results.tsv`` and ``rows.tsv``.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from bisect import bisect_right
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

COMPONENTS = ("gamma", "lambda")
READOUT_COMPONENTS = ("readout_error", "prob_meas1_prep0")
READOUT_QUANTUM = 1.0 / 8192.0
HORIZONS_H = (24.0, 168.0)
CUT = "2026-09-01T00:00:00+00:00"
FIT_CUT = "2026-08-10T00:00:00+00:00"
LEVEL_WINDOW_D = 30.0
MIN_LEVEL_STATES = 5
MIN_LEVEL_EVENTS = 3
MIN_EVENTS_PER_QUBIT = 20
LAMBDA_FLOOR_Q = 0.05
RIDGE = 1.0
ALPHA = 0.2
NOMINAL = 0.80
BOOTSTRAP = 1000
SEED = 84
HOUR = 3600.0
DAY = 86400.0


def _pb() -> ModuleType:
    """Import the persistence-band script, so the archive walk has one definition."""
    path = Path(__file__).resolve().parents[1] / "persistence-band" / "measure_persistence_band.py"
    spec = importlib.util.spec_from_file_location("measure_persistence_band", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_persistence_band"] = module
    spec.loader.exec_module(module)
    return module


def _with_readout(pb: ModuleType, repo: Path, ref: str, files: list[Any]) -> list[Any]:
    """Re-read each file and replace ``per_qubit`` with (readout_error, prob_meas1_prep0)."""
    import dataclasses
    import json
    import tempfile

    tmp = Path(tempfile.gettempdir()) / "persistence-band" / "readout.json"
    tmp.parent.mkdir(exist_ok=True)
    out = []
    for i, rec in enumerate(files):
        doc = pb.read_snapshot(repo, ref, rec.path)
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        parsed = pb.load_snapshot(tmp)
        vals = np.full((len(parsed.qubits), 2), np.nan)
        for pos, qubit in enumerate(parsed.qubits):
            vals[pos] = (
                np.nan if qubit.readout_error is None else qubit.readout_error,
                np.nan if qubit.prob_meas1_prep0 is None else qubit.prob_meas1_prep0,
            )
        out.append(dataclasses.replace(rec, per_qubit=vals))
        if (i + 1) % 250 == 0:
            print(f"  readout pass {i + 1}/{len(files)}", file=sys.stderr)
    return out


def _q(values: np.ndarray, level: float = NOMINAL) -> float:
    return float(np.quantile(values, level, method="inverted_cdf"))


def _r2(y: np.ndarray, yhat: np.ndarray, reference: float) -> float:
    sst = float(np.sum((y - reference) ** 2))
    return 1.0 - float(np.sum((y - yhat) ** 2)) / sst if sst > 0 else math.nan


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3:
        return math.nan
    return float(np.corrcoef(a, b)[0, 1])


def _local_level_cap(rho: float) -> float:
    """Best next-increment R^2 from own history under a Gaussian local-level model."""
    if not math.isfinite(rho) or rho >= 0.0:
        return 0.0
    if rho <= -0.5:
        return 0.5
    q = -1.0 / rho - 2.0
    p = (q + math.sqrt(q * q + 4.0 * q)) / 2.0
    return 1.0 - (1.0 + p) * (-rho)


def _interval_score(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return (
        (hi - lo)
        + (2.0 / ALPHA) * np.maximum(0.0, lo - x)
        + (2.0 / ALPHA) * np.maximum(0.0, x - hi)
    )


def _band_metrics(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> dict[str, float]:
    inside = (x >= lo) & (x <= hi)
    return {
        "n": float(x.size),
        "coverage": float(np.mean(inside)) if x.size else math.nan,
        "mean_width": float(np.mean(hi - lo)) if x.size else math.nan,
        "interval_score": float(np.mean(_interval_score(x, lo, hi))) if x.size else math.nan,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--backend", default="ibm_fez")
    ap.add_argument("--feature", choices=("targets", "readout"), default="targets")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pb = _pb()
    rng = np.random.default_rng(np.random.SeedSequence(SEED))
    cut, fit_cut = pb._epoch(CUT), pb._epoch(FIT_CUT)

    files = pb.load_files(args.repo, args.ref, args.backend)
    if args.feature == "readout":
        files = _with_readout(pb, args.repo, args.ref, files)
    components = COMPONENTS if args.feature == "targets" else READOUT_COMPONENTS
    quantum = None if args.feature == "targets" else READOUT_QUANTUM
    states = pb.distinct_states(files)
    expected = pb.index_digests(args.repo, args.ref)
    if {files[i].digest for i in states} != expected:
        raise SystemExit("distinct-state mismatch against health/state-index.tsv")
    as_of = pb.AsOf(files)
    recals = pb.recal_times(files)
    times = np.array([f.time for f in files])
    n_q = files[0].per_qubit.shape[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        lmat = np.log(
            np.stack([f.per_qubit for f in files])
        )  # (n_files, n_q, 2), NaN where unusable
    lmat[~np.isfinite(lmat)] = np.nan

    # floors from training-period values: lambda only for targets, both components for readout
    train_mask_files = times < cut
    floor_values: list[float] = []
    for ci in range(2):
        if args.feature == "targets" and ci == 0:
            floor_values.append(math.nan)
            continue
        vals = np.exp(lmat[train_mask_files, :, ci])
        floor_values.append(float(np.nanquantile(vals, LAMBDA_FLOOR_Q)))
    floors = tuple(-math.inf if math.isnan(v) else math.log(v) for v in floor_values)

    results: list[dict[str, Any]] = []
    rows_out: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "ref": args.ref,
        "files": len(files),
        "distinct_states": len(states),
        "cut": CUT,
        "fit_cut": FIT_CUT,
        "feature": args.feature,
        "floors": dict(zip(components, floor_values, strict=True)),
        "chipwide_t1_recalibrations": len(recals),
    }

    def emit(measurement: str, **kw: Any) -> None:
        results.append({"measurement": measurement, **kw})

    state_times = np.array([files[s].time for s in states])

    for ci, comp in enumerate(components):
        floor = floors[ci]
        lq = lmat[:, :, ci].copy()
        lq[lq < floor] = np.nan  # floor applies to every use of lambda
        excluded = int(np.sum(np.isfinite(lmat[:, :, ci]) & ~np.isfinite(lq)))
        summary[f"{comp}_rows_excluded_by_floor"] = excluded

        # ------------------------------------------------------------- event view
        events: list[list[tuple[float, float, float]]] = []  # per qubit: (tau, L, D)
        for q in range(n_q):
            prev: float | None = None
            ev: list[tuple[float, float, float]] = []
            for f in range(len(files)):
                v = lq[f, q]
                if not np.isfinite(v):
                    continue
                if prev is not None and v != prev:
                    ev.append((times[f], v, v - prev))
                prev = v
            events.append(ev)
        if quantum is not None:
            steps = np.array(
                [abs(math.exp(l1) - math.exp(l1 - d)) for ev in events for (_, l1, d) in ev]
            )
            one = (
                float(np.mean(np.isclose(steps, quantum, rtol=1e-6, atol=quantum * 1e-3)))
                if steps.size
                else math.nan
            )
            emit(
                "event_quantum_step",
                component=comp,
                metric="fraction_one_quantum",
                value=one,
                n=float(steps.size),
                quantum=quantum,
            )
        # lag-1 pairs and reversion rows
        pairs_train: list[tuple[float, float]] = []
        pairs_test: list[tuple[float, float]] = []
        per_qubit_rho: list[float] = []
        per_qubit_pairs: list[list[tuple[float, float]]] = []
        rev_train: list[tuple[float, float]] = []  # (dev_k, D_{k+1})
        rev_test: list[tuple[float, float]] = []
        for q in range(n_q):
            ev = events[q]
            qp: list[tuple[float, float]] = []
            for k in range(len(ev) - 1):
                tau_k, l_k, d_k = ev[k]
                tau_n, _, d_n = ev[k + 1]
                qp.append((d_k, d_n))
                (pairs_train if tau_n < cut else pairs_test).append((d_k, d_n))
                recent = [lv for (tau, lv, _) in ev[: k + 1] if tau > tau_k - LEVEL_WINDOW_D * DAY]
                if len(recent) >= MIN_LEVEL_EVENTS:
                    dev = l_k - float(np.mean(recent))
                    (rev_train if tau_n < cut else rev_test).append((dev, d_n))
            per_qubit_pairs.append(qp)
            if len(qp) >= MIN_EVENTS_PER_QUBIT:
                a = np.array(qp)
                per_qubit_rho.append(_pearson(a[:, 0], a[:, 1]))
        for label, pairs in (("train", pairs_train), ("test", pairs_test)):
            a = np.array(pairs)
            rho = _pearson(a[:, 0], a[:, 1]) if a.size else math.nan
            emit(
                "event_lag1_autocorr",
                component=comp,
                period=label,
                metric="rho_pooled",
                value=rho,
                n=float(len(pairs)),
            )
            emit(
                "event_lag1_autocorr",
                component=comp,
                period=label,
                metric="local_level_cap_r2",
                value=_local_level_cap(rho),
                n=float(len(pairs)),
            )
        emit(
            "event_lag1_autocorr",
            component=comp,
            period="all",
            metric="rho_per_qubit_median",
            value=float(np.median(per_qubit_rho)) if per_qubit_rho else math.nan,
            n=float(len(per_qubit_rho)),
        )
        # block bootstrap over qubits (training pairs only)
        train_by_q: list[list[tuple[float, float]]] = []
        for q in range(n_q):
            ev = events[q]
            train_by_q.append(
                [(ev[k][2], ev[k + 1][2]) for k in range(len(ev) - 1) if ev[k + 1][0] < cut]
            )
        boots = []
        for _ in range(BOOTSTRAP):
            pick = rng.integers(0, n_q, size=n_q)
            a = np.array([p for q in pick for p in train_by_q[q]])
            boots.append(_pearson(a[:, 0], a[:, 1]) if a.size else math.nan)
        b_arr = np.array(boots)
        lo_r, hi_r = (float(np.nanquantile(b_arr, q)) for q in (0.05, 0.95))
        emit(
            "event_lag1_autocorr",
            component=comp,
            period="train",
            metric="rho_ci90",
            value=lo_r,
            ci90_high=hi_r,
            n=float(len(pairs_train)),
        )
        emit(
            "event_lag1_autocorr",
            component=comp,
            period="train",
            metric="local_level_cap_r2_ci90",
            value=_local_level_cap(hi_r),
            ci90_high=_local_level_cap(lo_r),
            n=float(len(pairs_train)),
        )
        # reversion regression
        rt = np.array(rev_train)
        rs = np.array(rev_test)
        if rt.size and rs.size:
            x1 = np.column_stack([np.ones(len(rt)), rt[:, 0]])
            coef, *_ = np.linalg.lstsq(x1, rt[:, 1], rcond=None)
            pred = coef[0] + coef[1] * rs[:, 0]
            emit(
                "event_reversion",
                component=comp,
                metric="b_train",
                value=float(coef[1]),
                n=float(len(rt)),
            )
            emit(
                "event_reversion",
                component=comp,
                metric="r2_test",
                value=_r2(rs[:, 1], pred, float(np.mean(rt[:, 1]))),
                n=float(len(rs)),
            )
            # bootstrap b over qubits
            rev_by_q: list[list[tuple[float, float]]] = [[] for _ in range(n_q)]
            for q in range(n_q):
                ev = events[q]
                for k in range(len(ev) - 1):
                    tau_k, l_k, _ = ev[k]
                    tau_n, _, d_n = ev[k + 1]
                    if tau_n >= cut:
                        continue
                    recent = [
                        lv for (tau, lv, _) in ev[: k + 1] if tau > tau_k - LEVEL_WINDOW_D * DAY
                    ]
                    if len(recent) >= MIN_LEVEL_EVENTS:
                        rev_by_q[q].append((l_k - float(np.mean(recent)), d_n))
            bb = []
            for _ in range(BOOTSTRAP):
                pick = rng.integers(0, n_q, size=n_q)
                a = np.array([p for q in pick for p in rev_by_q[q]])
                if a.size:
                    c, *_ = np.linalg.lstsq(
                        np.column_stack([np.ones(len(a)), a[:, 0]]), a[:, 1], rcond=None
                    )
                    bb.append(float(c[1]))
            emit(
                "event_reversion",
                component=comp,
                metric="b_ci90",
                value=float(np.quantile(bb, 0.05)),
                ci90_high=float(np.quantile(bb, 0.95)),
                n=float(len(rt)),
            )

        # ------------------------------------------------------------- horizon view
        # per-qubit level at each state time: trailing 30 d mean of as-of values at state times
        lstate = lq[np.array(states), :]  # (n_states, n_q)
        level = np.full_like(lstate, np.nan)
        for i, t in enumerate(state_times):
            mask = (state_times > t - LEVEL_WINDOW_D * DAY) & (state_times <= t)
            block = lstate[mask, :]
            counts = np.sum(np.isfinite(block), axis=0)
            with np.errstate(invalid="ignore"):
                means = np.nanmean(np.where(np.isfinite(block), block, np.nan), axis=0)
            level[i, :] = np.where(counts >= MIN_LEVEL_STATES, means, np.nan)
        chip_level = np.nanmean(level, axis=1)
        # per-qubit event lookup for last increment and age
        ev_tau = [np.array([e[0] for e in events[q]]) for q in range(n_q)]
        ev_d = [np.array([e[2] for e in events[q]]) for q in range(n_q)]

        for horizon in HORIZONS_H:
            feats: list[list[float]] = []
            target: list[float] = []
            meta: list[tuple[float, int, float, bool]] = []  # (t, q, asof_time, train)
            lfut_list: list[float] = []
            for i, s in enumerate(states):
                t = files[s].time
                f = as_of(t + horizon * HOUR)
                if f is None or (t < cut <= t + horizon * HOUR):
                    continue
                j = bisect_right(recals, t) - 1
                if j < 0:
                    continue
                recal_age = (t - recals[j]) / HOUR
                hr = (
                    datetime.fromtimestamp(t, UTC).hour
                    + datetime.fromtimestamp(t, UTC).minute / 60.0
                )
                for q in range(n_q):
                    lnow, lfut, lev = lstate[i, q], lq[f, q], level[i, q]
                    if not (np.isfinite(lnow) and np.isfinite(lfut) and np.isfinite(lev)):
                        continue
                    k = bisect_right(ev_tau[q], t) - 1
                    if k < 0:
                        continue
                    age_h = (t - ev_tau[q][k]) / HOUR
                    feats.append(
                        [
                            lnow - lev,
                            float(ev_d[q][k]),
                            math.log(max(age_h, 1.0 / 60.0)),
                            recal_age,
                            lev - chip_level[i],
                            math.sin(2 * math.pi * hr / 24.0),
                            math.cos(2 * math.pi * hr / 24.0),
                        ]
                    )
                    target.append(lfut - lnow)
                    meta.append((t, q, files[f].time, t < cut))
                    lfut_list.append(lfut)
            x_all = np.array(feats)
            y_all = np.array(target)
            t_all = np.array([m[0] for m in meta])
            q_all = np.array([m[1] for m in meta])
            lfut_arr = np.array(lfut_list)
            is_train = t_all < cut
            is_fit = t_all < fit_cut
            is_cal = is_train & ~is_fit
            is_test = ~is_train
            change = y_all != 0.0
            hk = f"H{int(horizon)}h"
            summary[f"{comp}_{hk}"] = {
                "rows_fit": int(np.sum(is_fit & change)),
                "rows_cal": int(np.sum(is_cal & change)),
                "rows_test_change": int(np.sum(is_test & change)),
                "rows_test_all": int(np.sum(is_test)),
                "effective_training_window": [
                    pb._iso(float(t_all[is_fit].min())),
                    pb._iso(float(t_all[is_fit].max())),
                ]
                if np.any(is_fit)
                else None,
            }
            # vacuity
            for rowset, mask in (("all", is_test), ("change", is_test & change)):
                cov0 = float(np.mean(y_all[mask] == 0.0)) if mask.any() else math.nan
                emit(
                    "zero_width_band",
                    component=comp,
                    horizon_h=horizon,
                    rowset=rowset,
                    metric="coverage",
                    value=cov0,
                    n=float(mask.sum()),
                )
                if rowset == "change" and mask.any() and cov0 != 0.0:
                    raise SystemExit("row definition wrong: zero-width band covers change rows")
            fit_m, cal_m, test_m = is_fit & change, is_cal & change, is_test & change
            ref_mean = float(np.mean(y_all[fit_m]))
            # standardisation on fit rows
            mu, sd = x_all[fit_m].mean(axis=0), x_all[fit_m].std(axis=0)
            sd[sd == 0] = 1.0
            z_all = (x_all - mu) / sd
            # models
            preds: dict[str, np.ndarray] = {"persistence": np.zeros(len(y_all))}
            dev = x_all[:, 0]
            kappa = -float(np.dot(dev[fit_m], y_all[fit_m]) / np.dot(dev[fit_m], dev[fit_m]))
            preds["shrinkage"] = -kappa * dev
            xd = np.column_stack([np.ones(len(z_all)), z_all])
            pen = RIDGE * np.eye(xd.shape[1])
            pen[0, 0] = 0.0
            beta = np.linalg.solve(xd[fit_m].T @ xd[fit_m] + pen, xd[fit_m].T @ y_all[fit_m])
            preds["linear"] = xd @ beta
            emit(
                "horizon_fit",
                component=comp,
                horizon_h=horizon,
                metric="kappa",
                value=kappa,
                n=float(fit_m.sum()),
            )
            # block bootstrap of kappa over state times within fit rows
            fit_times = np.unique(t_all[fit_m])
            kb = []
            for _ in range(BOOTSTRAP):
                pick = rng.choice(fit_times, size=fit_times.size, replace=True)
                idx = np.concatenate([np.flatnonzero(fit_m & (t_all == tt)) for tt in pick])
                kb.append(-float(np.dot(dev[idx], y_all[idx]) / np.dot(dev[idx], dev[idx])))
            emit(
                "horizon_fit",
                component=comp,
                horizon_h=horizon,
                metric="kappa_ci90",
                value=float(np.quantile(kb, 0.05)),
                ci90_high=float(np.quantile(kb, 0.95)),
                n=float(fit_m.sum()),
            )
            names = ["dev", "last_inc", "log_age", "recal_age", "standing", "hour_sin", "hour_cos"]
            for nm, bval in zip(names, beta[1:], strict=True):
                emit(
                    "horizon_fit",
                    component=comp,
                    horizon_h=horizon,
                    metric=f"ridge_beta_std_{nm}",
                    value=float(bval),
                    n=float(fit_m.sum()),
                )
            r2s: dict[str, float] = {}
            for model, p in preds.items():
                r2s[model] = _r2(y_all[test_m], p[test_m], ref_mean)
                emit(
                    "horizon_point",
                    component=comp,
                    horizon_h=horizon,
                    model=model,
                    metric="r2_test_change",
                    value=r2s[model],
                    n=float(test_m.sum()),
                )
                emit(
                    "horizon_point",
                    component=comp,
                    horizon_h=horizon,
                    model=model,
                    metric="median_abs_err_log",
                    value=float(np.median(np.abs(y_all[test_m] - p[test_m]))),
                    n=float(test_m.sum()),
                )
                qc = _q(np.abs(y_all[cal_m] - p[cal_m]))
                m = _band_metrics(y_all[test_m], p[test_m] - qc, p[test_m] + qc)
                for k, v in m.items():
                    if k != "n":
                        emit(
                            "horizon_band",
                            component=comp,
                            horizon_h=horizon,
                            model=model,
                            metric=k,
                            value=v,
                            n=m["n"],
                            conformal_q=qc,
                        )
            emit(
                "horizon_point",
                component=comp,
                horizon_h=horizon,
                model="linear_minus_shrinkage",
                metric="r2_gap",
                value=r2s["linear"] - r2s["shrinkage"],
                n=float(test_m.sum()),
            )
            # rolling per-qubit band for L(t+H)
            lo_list, hi_list, x_list = [], [], []
            for idx in np.flatnonzero(test_m):
                t, q = t_all[idx], q_all[idx]
                mask = (state_times > t - LEVEL_WINDOW_D * DAY) & (state_times <= t)
                vals = lstate[mask, q]
                vals = vals[np.isfinite(vals)]
                if vals.size < MIN_LEVEL_STATES:
                    continue
                lo, hi = np.quantile(vals, (0.10, 0.90))
                lo_list.append(lo)
                hi_list.append(hi)
                x_list.append(lfut_arr[idx])
            m = _band_metrics(np.array(x_list), np.array(lo_list), np.array(hi_list))
            for k, v in m.items():
                if k != "n":
                    emit(
                        "horizon_band",
                        component=comp,
                        horizon_h=horizon,
                        model="rolling_band",
                        metric=k,
                        value=v,
                        n=m["n"],
                    )
            # common-mode share, leave-one-out, test change rows
            cm_x, cm_y = [], []
            for tt in np.unique(t_all[test_m]):
                idx = np.flatnonzero(test_m & (t_all == tt))
                if idx.size < 3:
                    continue
                tot = float(np.sum(y_all[idx]))
                for j in idx:
                    cm_x.append((tot - y_all[j]) / (idx.size - 1))
                    cm_y.append(y_all[j])
            cx, cy = np.array(cm_x), np.array(cm_y)
            c, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(cx)), cx]), cy, rcond=None)
            emit(
                "common_mode",
                component=comp,
                horizon_h=horizon,
                metric="r2_leave_one_out",
                value=_r2(cy, c[0] + c[1] * cx, float(np.mean(cy))),
                n=float(len(cy)),
                slope=float(c[1]),
            )
            # rows for later scoring
            for idx in np.flatnonzero(test_m):
                rows_out.append(
                    {
                        "component": comp,
                        "horizon_h": int(horizon),
                        "state_time": pb._iso(float(t_all[idx])),
                        "qubit": int(q_all[idx]),
                        "asof_time": pb._iso(float(meta[idx][2])),
                        "d_h_log": float(y_all[idx]),
                    }
                )

    keys: list[str] = []
    for row in results:
        for k in row:
            if k not in keys:
                keys.append(k)
    with (args.out / "results.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, delimiter="\t")
        w.writeheader()
        w.writerows(results)
    with (args.out / "rows.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(rows_out)
    summary["results_rows"] = len(results)
    summary["test_rows_written"] = len(rows_out)
    summary["python"] = sys.version.split()[0]
    summary["numpy"] = np.__version__
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for row in results:
        if row["measurement"] in (
            "event_lag1_autocorr",
            "event_reversion",
            "horizon_point",
            "common_mode",
        ) or (row["measurement"] == "horizon_band" and row["metric"] == "interval_score"):
            print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()})


if __name__ == "__main__":
    main()
