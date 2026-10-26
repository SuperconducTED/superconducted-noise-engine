"""Task N1 of the pattern detector: features, the two nulls, reference rows, the logistic bar.

Implements README sections 3 to 5 with amendments 2 to 4. Nothing deep: no network is trained
(task N2 waits for gate L1). The null forecasts are never fitted to labels: ``q`` and ``sigma_q``
come from increments, the residual shape from residuals, and the bins from simulated series.

Run from the repository root with the pinned interpreter::

    PYTHONPATH=src;. python docs/evidence/pattern-detector/n1_baselines.py \
        --fields <scratch>/fields.pkl --ref <sha> --out docs/evidence/pattern-detector

``--selftest`` checks the null machinery and the logistic solver on synthetic series and exits.

Outputs: ``results.tsv`` (one row per figure), ``summary.json``, ``features.tsv.gz`` (the design
matrix with labels and both null forecasts), ``null_bins.tsv``, ``calibration.tsv``.
"""

# ruff: noqa: N803, N806  (matrix notation: X, W, H, E are the standard symbols)
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import math
import pickle
import sys
from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ce = _load("count_events")
cf = _load("collect_fields")

CUT = ce.CUT
DELTA = ce.DELTA
K = ce.K
WINDOW_D = ce.WINDOW_D
MIN_WINDOW_STATES = ce.MIN_WINDOW_STATES
MIN_WINDOW_DISTINCT = ce.MIN_WINDOW_DISTINCT
DAY = ce.DAY
HOUR = 3600.0
REPLICATES = 2000
BIN_WIDTH = 0.05
BIN_TOP = 1.5
MIN_BIN_PAIRS = 200
MIN_RESIDUALS = 20
BOOTSTRAP = 1000
SEED = 84
LAMBDA_GRID = (0.001, 0.01, 0.1, 1.0, 10.0)
INNER_FRACTION = 0.8
FEATURES = (
    "d",
    "abs_d_rel",
    "prev_d",
    "n_distinct",
    "hours_since_prev",
    "hours_since_sweep",
    "d_t2",
    "d_readout",
    "chip_readout",
    "same_sign_share",
    "sx_log",
    "cz_best_log",
    "hour_sin",
    "hour_cos",
)
INDICATORS = ("prev_d_missing", "d_t2_missing", "d_readout_missing")
COLUMNS = FEATURES + INDICATORS
F_T1, F_T2, F_RO, F_SX, F_CZ = range(5)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).date().isoformat()


# ------------------------------------------------------------------------------- data


@dataclass
class Data:
    files: list[Any]  # count_events.FileRecord, T1 only (for the shared functions)
    fields: list[Any]  # collect_fields.Fields
    states: list[int]
    state_times: np.ndarray
    state_vals: np.ndarray  # (n_states, n_qubits, 5)
    file_vals: np.ndarray  # (n_files, n_qubits, 5)
    sweeps: list[float]
    cut: float


def to_file_records(fields: list[Any]) -> list[Any]:
    return [
        ce.FileRecord(f.path, f.time, f.digest, f.values[:, F_T1].copy(), f.t1_dates)
        for f in fields
    ]


def build_data(fields: list[Any]) -> Data:
    files = to_file_records(fields)
    states = ce.distinct_states(files)
    state_times = np.array([files[s].time for s in states])
    file_vals = np.stack([f.values for f in fields])
    state_vals = file_vals[states]
    return Data(
        files,
        fields,
        states,
        state_times,
        state_vals,
        file_vals,
        ce.recal_times(files),
        ce._epoch(CUT),
    )


def window_bounds(data: Data, t: float) -> tuple[int, int]:
    lo = int(np.searchsorted(data.state_times, t - WINDOW_D * DAY, side="right"))
    hi = int(np.searchsorted(data.state_times, t, side="left"))
    return lo, hi


def levels_all(data: Data, t: float, field: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Level, n_states, n_distinct for every qubit at t (states strictly before t), NaN if none."""
    lo, hi = window_bounds(data, t)
    block = data.state_vals[lo:hi, :, field]  # (n_states, n_qubits)
    n_q = block.shape[1]
    level = np.full(n_q, math.nan)
    n_states = np.zeros(n_q, dtype=int)
    n_distinct = np.zeros(n_q, dtype=int)
    for q in range(n_q):
        col = block[:, q]
        col = col[np.isfinite(col)]
        n_states[q] = col.size
        n_distinct[q] = np.unique(col).size if col.size else 0
        if col.size >= MIN_WINDOW_STATES and n_distinct[q] >= MIN_WINDOW_DISTINCT:
            level[q] = float(np.mean(col))
    return level, n_states, n_distinct


def band_width(data: Data, t: float, q: int) -> float:
    lo, hi = window_bounds(data, t)
    col = data.state_vals[lo:hi, q, F_T1]
    col = col[np.isfinite(col)]
    if col.size == 0:
        return math.nan
    return float(np.percentile(col, 90) - np.percentile(col, 10))


# ------------------------------------------------------------------------------- rows and features


@dataclass
class Built:
    rows: list[Any]  # count_events.Row with y not None
    events: list[list[Any]]
    X: np.ndarray
    y: np.ndarray
    times: np.ndarray
    qubits: np.ndarray
    excluded: dict[str, int]


def build_features(data: Data) -> Built:
    rows_all, events = ce.build_rows(data.files, data.states, DELTA, K, data.cut)
    rows = [r for r in rows_all if r.y is not None]
    by_file: dict[int, tuple[Any, ...]] = {}
    ev_index: dict[tuple[int, float], int] = {}
    for q, ev in enumerate(events):
        for i, e in enumerate(ev):
            ev_index[(q, e.time)] = i
    file_of_time = {f.time: i for i, f in enumerate(data.files)}
    X_rows: list[list[float]] = []
    kept: list[Any] = []
    excluded = {"band_width_zero": 0, "sx_missing": 0, "cz_missing": 0}
    for r in rows:
        f = file_of_time[r.time]
        if f not in by_file:
            lv_t1, _, _ = levels_all(data, r.time, F_T1)
            lv_t2, _, _ = levels_all(data, r.time, F_T2)
            lv_ro, _, _ = levels_all(data, r.time, F_RO)
            cur = data.file_vals[f]
            d_t1_all = cur[:, F_T1] - lv_t1
            d_ro_all = cur[:, F_RO] - lv_ro
            chip_ro = float(np.nanmedian(d_ro_all)) if np.any(np.isfinite(d_ro_all)) else math.nan
            by_file[f] = (lv_t2, lv_ro, d_t1_all, d_ro_all, chip_ro)
        lv_t2, lv_ro, d_t1_all, d_ro_all, chip_ro = by_file[f]
        q = r.qubit
        width = band_width(data, r.time, q)
        if not (math.isfinite(width) and width > 0):
            excluded["band_width_zero"] += 1
            continue
        sx = data.file_vals[f, q, F_SX]
        cz = data.file_vals[f, q, F_CZ]
        if not math.isfinite(sx):
            excluded["sx_missing"] += 1
            continue
        if not math.isfinite(cz):
            excluded["cz_missing"] += 1
            continue
        i = ev_index[(q, r.time)]
        ev = events[q]
        prev_d, prev_missing = 0.0, 1.0
        hours_since_prev = math.nan
        if i > 0:
            prev = ev[i - 1]
            hours_since_prev = (r.time - prev.time) / HOUR
            lvl = ce.level_at(data.files, data.state_times, data.states, q, prev.time)
            if lvl is not None:
                prev_d, prev_missing = prev.value - lvl[0], 0.0
        if not math.isfinite(hours_since_prev):
            hours_since_prev = (r.time - data.files[0].time) / HOUR
        # amendment 6: the last sweep STRICTLY before t. An event's own file is usually a sweep
        # (IBM re-measures T1 chip-wide), and t - 1e-9 == t in float64, so the first run's
        # bisect_right(..., t - 1e-9) returned the event's own file and the column was all zeros.
        j = bisect_left(data.sweeps, r.time)
        hours_since_sweep = (r.time - (data.sweeps[j - 1] if j > 0 else data.files[0].time)) / HOUR
        d_t2 = data.file_vals[f, q, F_T2] - lv_t2[q]
        d_t2, t2_missing = (float(d_t2), 0.0) if math.isfinite(d_t2) else (0.0, 1.0)
        d_ro = d_ro_all[q]
        d_ro, ro_missing = (float(d_ro), 0.0) if math.isfinite(d_ro) else (0.0, 1.0)
        finite = np.isfinite(d_t1_all)
        same = np.sign(d_t1_all[finite]) == np.sign(r.d)
        share = float(np.mean(same)) if finite.any() else math.nan
        hour = (
            datetime.fromtimestamp(r.time, UTC).hour
            + datetime.fromtimestamp(r.time, UTC).minute / 60
        )
        X_rows.append(
            [
                r.d,
                abs(r.d) / width,
                prev_d,
                float(r.n_window_distinct),
                hours_since_prev,
                hours_since_sweep,
                d_t2,
                d_ro,
                chip_ro if math.isfinite(chip_ro) else 0.0,
                share,
                float(sx),
                float(cz),
                math.sin(2 * math.pi * hour / 24),
                math.cos(2 * math.pi * hour / 24),
                prev_missing,
                t2_missing,
                ro_missing,
            ]
        )
        kept.append(r)
    X = np.array(X_rows)
    y = np.array([r.y for r in kept], dtype=float)
    times = np.array([r.time for r in kept])
    qubits = np.array([r.qubit for r in kept])
    return Built(kept, events, X, y, times, qubits, excluded)


# ------------------------------------------------------------------------------- the nulls


BIN_EDGES = np.arange(DELTA, BIN_TOP + 1e-9, BIN_WIDTH)


def bin_index(abs_d: np.ndarray) -> np.ndarray:
    idx = np.floor((abs_d - DELTA) / BIN_WIDTH + 1e-12).astype(int)
    return np.clip(idx, 0, len(BIN_EDGES) - 1)


def signed_bin(d: np.ndarray) -> np.ndarray:
    """Amendment 5: bins by signed d; the first len(BIN_EDGES) bins are below the level."""
    return bin_index(np.abs(d)) + len(BIN_EDGES) * (d > 0).astype(int)


N_SIGNED_BINS = 2 * len(BIN_EDGES)


@dataclass
class NullTables:
    name: str
    pairs: np.ndarray  # (n_qubits, n_bins)
    positives: np.ndarray
    sign_pairs: np.ndarray  # (n_qubits, 2) below, above
    sign_positives: np.ndarray
    fallback_qubits: int

    def forecast(self, qubits: np.ndarray, d: np.ndarray) -> tuple[np.ndarray, int]:
        b = signed_bin(d)
        pooled_pairs = self.pairs.sum(axis=0)
        pooled_pos = self.positives.sum(axis=0)
        p = np.empty(len(qubits))
        fallbacks = 0
        for i, (q, bi) in enumerate(zip(qubits, b, strict=True)):
            if self.pairs[q, bi] >= MIN_BIN_PAIRS:
                p[i] = self.positives[q, bi] / self.pairs[q, bi]
            else:
                fallbacks += 1
                p[i] = (
                    pooled_pos[bi] / pooled_pairs[bi]
                    if pooled_pairs[bi] > 0
                    else pooled_pos.sum() / max(pooled_pairs.sum(), 1)
                )
        return p, fallbacks


def qubit_residuals(data: Data, events: list[Any], q: int) -> np.ndarray:
    """Training residuals v - level for every event of q that has a level."""
    out = []
    for e in events:
        if e.time >= data.cut:
            break
        lvl = ce.level_at(data.files, data.state_times, data.states, q, e.time)
        if lvl is not None:
            out.append(e.value - lvl[0])
    return np.array(out)


def simulate_null(
    data: Data,
    events: list[list[Any]],
    sigma_q: np.ndarray,
    q_drift: float,
    noise: str,
    residuals: list[np.ndarray],
    pooled_std_res: np.ndarray,
    rng: np.random.Generator,
    t_start: float | None = None,
    t_end: float | None = None,
    count_from: float | None = None,
) -> NullTables:
    """Amendments 2, 4 and 5: the protocol's own label on simulated series at the real event times.

    Events in ``[t_start, t_end)`` are simulated; only those at or after ``count_from`` enter the
    tables, so the test-timing diagnostic can fill its windows from the 30 days before the cut.
    """
    t_start = -math.inf if t_start is None else t_start
    t_end = data.cut if t_end is None else t_end
    count_from = -math.inf if count_from is None else count_from
    n_q = len(events)
    n_bins = N_SIGNED_BINS
    pairs = np.zeros((n_q, n_bins))
    positives = np.zeros((n_q, n_bins))
    sign_pairs = np.zeros((n_q, 2))
    sign_pos = np.zeros((n_q, 2))
    fallback = 0
    t0 = data.files[0].time
    for q in range(n_q):
        ev = [e for e in events[q] if t_start <= e.time < t_end]
        if len(ev) < K + 2:
            continue
        # pseudo-event 0: the initial value, at the archive start or at the window's start
        times = np.array([t0 if t_start == -math.inf else t_start] + [e.time for e in ev])
        E = len(times)
        sig = sigma_q[q]
        # noise draws
        if noise == "gaussian":
            e_draw = rng.normal(0.0, sig, size=(REPLICATES, E))
        else:
            res = residuals[q]
            if res.size < MIN_RESIDUALS:
                std_res = pooled_std_res
                fallback += 1
            else:
                c = res - np.median(res)
                scale = 1.4826 * np.median(np.abs(c))
                std_res = c / scale if scale > 0 else c
            e_draw = sig * rng.choice(std_res, size=(REPLICATES, E), replace=True)
        eta = rng.normal(0.0, math.sqrt(q_drift) * sig, size=(REPLICATES, E))
        eta[:, 0] = 0.0
        mu = np.cumsum(eta, axis=1)
        sim = mu + e_draw  # (R, E)
        # state -> latest simulated event at or before the state's time
        state_ev = np.searchsorted(times, data.state_times, side="right") - 1  # -1 if before t0
        for i in range(1, E):
            if i + K >= E:
                break
            t = times[i]
            if t < count_from:
                continue
            lo, hi = window_bounds(data, t)
            idx = state_ev[lo:hi]
            idx = idx[idx >= 0]
            if idx.size < MIN_WINDOW_STATES or np.unique(idx).size < MIN_WINDOW_DISTINCT:
                continue
            w = np.bincount(idx, minlength=E).astype(float) / idx.size
            level = sim @ w
            d = sim[:, i] - level
            m = np.median(sim[:, i + 1 : i + 1 + K], axis=1)
            y = np.abs(m - sim[:, i]) < np.abs(m - level)
            sel = np.abs(d) >= DELTA
            if not sel.any():
                continue
            b = signed_bin(d[sel])
            np.add.at(pairs[q], b, 1.0)
            np.add.at(positives[q], b, y[sel].astype(float))
            below = d[sel] < 0
            sign_pairs[q, 0] += below.sum()
            sign_pairs[q, 1] += (~below).sum()
            sign_pos[q, 0] += y[sel][below].sum()
            sign_pos[q, 1] += y[sel][~below].sum()
    return NullTables(noise, pairs, positives, sign_pairs, sign_pos, fallback)


# ------------------------------------------------------------------------------- models and scores


def standardise(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (X - mean) / std


def fit_logistic(X: np.ndarray, y: np.ndarray, lam: float, iters: int = 100) -> np.ndarray:
    """L2-penalised logistic regression by Newton's method; X carries no intercept column."""
    n, d = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    beta = np.zeros(d + 1)
    reg = lam * np.eye(d + 1)
    reg[0, 0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Xb @ beta))
        g = Xb.T @ (p - y) + reg @ beta
        W = p * (1 - p)
        H = (Xb * W[:, None]).T @ Xb + reg
        step = np.linalg.solve(H, g)
        beta -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def predict_logistic(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(beta[0] + X @ beta[1:])))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)))


def auc(p: np.ndarray, y: np.ndarray) -> float:
    pos = p[y == 1]
    neg = p[y == 0]
    if pos.size == 0 or neg.size == 0:
        return math.nan
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]), kind="stable"), kind="stable")
    # Mann-Whitney with ties handled by average ranks
    allp = np.concatenate([pos, neg])
    order = np.argsort(allp, kind="mergesort")
    r = np.empty(allp.size)
    sorted_p = allp[order]
    i = 0
    while i < allp.size:
        j = i
        while j + 1 < allp.size and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        r[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    del ranks
    return float((r[: pos.size].sum() - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


def day_bootstrap(
    days: np.ndarray, y: np.ndarray, preds: dict[str, np.ndarray], rng: np.random.Generator
) -> dict[str, np.ndarray]:
    """Paired block bootstrap over test days; returns per-resample Brier scores per model."""
    uniq = np.unique(days)
    groups = {d: np.where(days == d)[0] for d in uniq}
    out = {k: np.empty(BOOTSTRAP) for k in preds}
    for b in range(BOOTSTRAP):
        drawn = rng.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([groups[d] for d in drawn])
        for k, p in preds.items():
            out[k][b] = brier(p[idx], y[idx])
    return out


def interval(x: np.ndarray) -> tuple[float, float]:
    return float(np.quantile(x, 0.05)), float(np.quantile(x, 0.95))


# ------------------------------------------------------------------------------- main run


def run(fields: list[Any], ref: str, out: Path, rows_record: Path | None) -> dict[str, Any]:
    data = build_data(fields)
    built = build_features(data)
    summary: dict[str, Any] = {
        "ref": ref,
        "files": len(fields),
        "distinct_states": len(data.states),
    }
    # guard: the N0 record
    if rows_record is not None:
        rec = {}
        with gzip.open(rows_record, "rt", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                if row["y"] != "":
                    rec[(int(row["qubit"]), row["time"])] = (float(row["d"]), int(row["y"]))
        rows_all, _ = ce.build_rows(data.files, data.states, DELTA, K, data.cut)
        mine = {(r.qubit, _iso(r.time)): (round(r.d, 6), r.y) for r in rows_all if r.y is not None}
        if set(mine) != set(rec) or any(
            abs(mine[k][0] - rec[k][0]) > 1e-6 or mine[k][1] != rec[k][1] for k in mine
        ):
            raise SystemExit(
                "reproduction guard: rows rebuilt from the field collection differ from rows.tsv.gz"
            )
        summary["guard_rows"] = len(mine)
    summary["excluded"] = built.excluded
    train = built.times < data.cut
    test = ~train
    summary["train_rows"], summary["test_rows"] = int(train.sum()), int(test.sum())
    summary["train_positives"], summary["test_positives"] = (
        int(built.y[train].sum()),
        int(built.y[test].sum()),
    )
    # events per qubit per day, per period
    ev_train = sum(1 for ev in built.events for e in ev if e.time < data.cut)
    ev_test = sum(1 for ev in built.events for e in ev if e.time >= data.cut)
    span_train = (data.cut - data.files[0].time) / DAY
    span_test = (data.files[-1].time - data.cut) / DAY
    summary["events_per_qubit_per_day"] = {
        "train": ev_train / 156 / span_train,
        "test": ev_test / 156 / span_test,
    }
    # null parameters (increments only)
    rho, n_pairs = ce.pooled_rho(built.events, data.cut)
    q_drift = ce.q_of(rho)
    sigma = ce.robust_sigma(built.events, data.cut)
    median_sigma = float(np.nanmedian(sigma))
    sigma_filled = np.where(np.isfinite(sigma), sigma, median_sigma)
    summary["null_parameters"] = {
        "rho": rho,
        "rho_pairs": n_pairs,
        "q": q_drift,
        "sigma_fallback_qubits": int((~np.isfinite(sigma)).sum()),
        "sigma_median": median_sigma,
    }
    residuals = [qubit_residuals(data, built.events[q], q) for q in range(len(built.events))]
    pooled = []
    for res in residuals:
        if res.size >= MIN_RESIDUALS:
            c = res - np.median(res)
            s = 1.4826 * np.median(np.abs(c))
            pooled.append(c / s if s > 0 else c)
    pooled_std = np.concatenate(pooled)
    summary["residuals"] = {
        "qubits_with_shape": len(pooled),
        "pooled_standardised": int(pooled_std.size),
        "pooled_skew": float(np.mean(pooled_std**3) / np.mean(pooled_std**2) ** 1.5),
        "pooled_p05": float(np.quantile(pooled_std, 0.05)),
        "pooled_p95": float(np.quantile(pooled_std, 0.95)),
    }
    rng = np.random.default_rng(np.random.SeedSequence(SEED))
    nulls = {
        "empirical": simulate_null(
            data, built.events, sigma_filled, q_drift, "empirical", residuals, pooled_std, rng
        ),
        "gaussian": simulate_null(
            data, built.events, sigma_filled, q_drift, "gaussian", residuals, pooled_std, rng
        ),
    }
    d_obs = built.X[:, 0]
    p_null: dict[str, np.ndarray] = {}
    for name, tab in nulls.items():
        p, fb = tab.forecast(built.qubits, d_obs)
        p_null[name] = p
        summary[f"null_{name}"] = {
            "simulated_pairs": float(tab.pairs.sum()),
            "bin_fallback_rows": fb,
            "residual_fallback_qubits": tab.fallback_qubits,
            "sim_rate_below": float(
                tab.sign_positives[:, 0].sum() / max(tab.sign_pairs[:, 0].sum(), 1)
            ),
            "sim_rate_above": float(
                tab.sign_positives[:, 1].sum() / max(tab.sign_pairs[:, 1].sum(), 1)
            ),
        }
    # amendment 4 item 5 and amendment 5 item 2: the nulls at the test period's own event times
    tt_start = data.cut - WINDOW_D * DAY
    tt_end = data.files[-1].time + 1.0
    for name in ("empirical", "gaussian"):
        tab = simulate_null(
            data,
            built.events,
            sigma_filled,
            q_drift,
            name,
            residuals,
            pooled_std,
            rng,
            t_start=tt_start,
            t_end=tt_end,
            count_from=data.cut,
        )
        p_tt, fb_tt = tab.forecast(built.qubits[test], d_obs[test])
        summary[f"null_{name}_test_timing"] = {
            "simulated_pairs": float(tab.pairs.sum()),
            "bin_fallback_rows": fb_tt,
            "sim_rate_below": float(
                tab.sign_positives[:, 0].sum() / max(tab.sign_pairs[:, 0].sum(), 1)
            ),
            "sim_rate_above": float(
                tab.sign_positives[:, 1].sum() / max(tab.sign_pairs[:, 1].sum(), 1)
            ),
            "mean_forecast_on_test_rows": float(p_tt.mean()),
            "brier_on_test_rows": brier(p_tt, built.y[test]),
        }
    # calibration diagnostic (amendment 4 item 4)
    calib = []
    for split, mask in (("train", train), ("test", test)):
        for sign, smask in (("below", built.X[:, 0] < 0), ("above", built.X[:, 0] > 0)):
            m = mask & smask
            row = {
                "split": split,
                "sign": sign,
                "rows": int(m.sum()),
                "observed_rate": float(built.y[m].mean()) if m.any() else math.nan,
            }
            for name in nulls:
                row[f"{name}_mean_forecast"] = (
                    float(p_null[name][m].mean()) if m.any() else math.nan
                )
            calib.append(row)
    calib_masks = [
        (mask & smask)
        for _, mask in (("train", train), ("test", test))
        for _, smask in (("below", built.X[:, 0] < 0), ("above", built.X[:, 0] > 0))
    ]
    summary["calibration"] = calib
    # the logistic bar
    X = built.X.copy()
    keep_cols = [j for j in range(X.shape[1]) if np.std(X[train, j]) > 0]
    dropped = [COLUMNS[j] for j in range(X.shape[1]) if j not in keep_cols]
    X = X[:, keep_cols]
    mean, std = X[train].mean(axis=0), X[train].std(axis=0)
    Xs = standardise(X, mean, std)
    order = np.argsort(built.times[train], kind="stable")
    tr_idx = np.where(train)[0][order]
    n_inner = int(INNER_FRACTION * tr_idx.size)
    inner_fit, inner_val = tr_idx[:n_inner], tr_idx[n_inner:]
    inner_cut = _iso(built.times[inner_fit[-1]])
    losses = {}
    for lam in LAMBDA_GRID:
        b = fit_logistic(Xs[inner_fit], built.y[inner_fit], lam)
        losses[lam] = log_loss(predict_logistic(Xs[inner_val], b), built.y[inner_val])
    lam_best = min(losses, key=losses.get)
    beta = fit_logistic(Xs[train], built.y[train], lam_best)
    p_log = predict_logistic(Xs, beta)
    for row, m in zip(calib, calib_masks, strict=True):
        row["logistic_mean_forecast"] = float(p_log[m].mean()) if m.any() else math.nan
    summary["logistic"] = {
        "dropped_constant_columns": dropped,
        "inner_cut": inner_cut,
        "inner_fit_rows": int(inner_fit.size),
        "inner_val_rows": int(inner_val.size),
        "lambda_losses": {str(k): v for k, v in losses.items()},
        "lambda": lam_best,
        "coefficients_standardised": {
            name: float(beta[1 + i]) for i, name in enumerate(COLUMNS[j] for j in keep_cols)
        },
        "intercept": float(beta[0]),
    }
    p0 = float(built.y[train].mean())
    preds = {
        "empirical_null": p_null["empirical"],
        "gaussian_null": p_null["gaussian"],
        "constant_p0": np.full(len(built.y), p0),
        "always_level": np.zeros(len(built.y)),
        "logistic": p_log,
    }
    yt = built.y[test]
    scores = {
        name: {
            "brier": brier(p[test], yt),
            "log_loss": log_loss(p[test], yt),
            "auc": auc(p[test], yt),
            "mean_forecast": float(p[test].mean()),
        }
        for name, p in preds.items()
    }
    p0_test = float(yt.mean())
    scores["oracle_constant_test_rate"] = {
        "brier": p0_test * (1 - p0_test),
        "log_loss": math.nan,
        "auc": 0.5,
        "mean_forecast": p0_test,
    }
    primary = (
        "empirical_null"
        if scores["empirical_null"]["brier"] <= scores["gaussian_null"]["brier"]
        else "gaussian_null"
    )
    bs_null = scores[primary]["brier"]
    for name in scores:
        scores[name]["bss_vs_primary_null"] = 1 - scores[name]["brier"] / bs_null
        scores[name]["bss_vs_constant"] = 1 - scores[name]["brier"] / scores["constant_p0"]["brier"]
    summary["test_scores"] = scores
    summary["primary_null"] = primary
    # paired day bootstrap on the test rows
    days = np.array([_day(t) for t in built.times[test]])
    boot = day_bootstrap(
        days,
        yt,
        {k: v[test] for k, v in preds.items()},
        np.random.default_rng(np.random.SeedSequence(SEED + 1)),
    )
    diff = boot[primary] - boot["logistic"]
    bss_boot = 1 - boot["logistic"] / boot[primary]
    for name in scores:
        scores[name]["bss_vs_always_level"] = (
            1 - scores[name]["brier"] / scores["always_level"]["brier"]
        )
    summary["bootstrap"] = {
        "test_days": int(np.unique(days).size),
        "resamples": BOOTSTRAP,
        "bs_null_minus_bs_logistic_90": interval(diff),
        "bss_logistic_90": interval(bss_boot),
        "bs_always_level_minus_bs_logistic_90": interval(boot["always_level"] - boot["logistic"]),
        "bss_logistic_vs_always_level_90": interval(1 - boot["logistic"] / boot["always_level"]),
        "bs_constant_minus_bs_logistic_90": interval(boot["constant_p0"] - boot["logistic"]),
        "bs_always_level_minus_bs_null_90": interval(boot["always_level"] - boot[primary]),
        "bs_gaussian_minus_bs_empirical_90": interval(
            boot["gaussian_null"] - boot["empirical_null"]
        ),
    }
    bss = scores["logistic"]["bss_vs_primary_null"]
    lo, _ = interval(diff)
    summary["clause_1"] = {
        "bss_logistic_vs_primary_null": bss,
        "threshold": 0.10,
        "interval_excludes_zero": bool(lo > 0),
        "holds": bool(bss >= 0.10 and lo > 0),
    }
    # outputs
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / "features.tsv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "qubit",
                "time",
                "split",
                "y",
                *COLUMNS,
                "p_null_empirical",
                "p_null_gaussian",
                "p_logistic",
            ]
        )
        for i in range(len(built.y)):
            w.writerow(
                [
                    built.qubits[i],
                    _iso(built.times[i]),
                    "train" if train[i] else "test",
                    int(built.y[i]),
                    *[f"{v:.6g}" for v in built.X[i]],
                    f"{p_null['empirical'][i]:.6f}",
                    f"{p_null['gaussian'][i]:.6f}",
                    f"{p_log[i]:.6f}",
                ]
            )
    with (out / "null_bins.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            ["null", "sign", "abs_bin_lo", "pooled_pairs", "pooled_positives", "pooled_rate"]
        )
        for name, tab in nulls.items():
            pp, pq = tab.pairs.sum(axis=0), tab.positives.sum(axis=0)
            for bi in range(N_SIGNED_BINS):
                sign = "below" if bi < len(BIN_EDGES) else "above"
                edge = BIN_EDGES[bi % len(BIN_EDGES)]
                rate = f"{pq[bi] / pp[bi]:.4f}" if pp[bi] else ""
                w.writerow([name, sign, f"{edge:.2f}", int(pp[bi]), int(pq[bi]), rate])
    with (out / "calibration.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(calib[0].keys()), delimiter="\t", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(calib)
    flat: list[tuple[str, Any]] = []

    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(node, list) and node and isinstance(node[0], dict):
            for i, v in enumerate(node):
                walk(f"{prefix}[{i}]", v)
        else:
            flat.append((prefix, node))

    walk("", summary)
    with (out / "results.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["figure", "value"])
        w.writerows(flat)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


# ------------------------------------------------------------------------------- self-test


def _synthetic_fields(rng: np.random.Generator, skew: bool) -> list[Any]:
    """Two qubits, hourly files for 200 days, one T1 re-measurement a day under a local level."""
    base = ce._epoch("2026-05-13T00:00:00+00:00")
    sigma, q = 0.2, 0.05
    n_days = 200
    mu = np.zeros(2)
    vals = np.full(
        (2, 5), [math.log(100e-6), math.log(90e-6), math.log(0.02), math.log(0.002), math.log(0.01)]
    )
    out = []
    for h in range(n_days * 24):
        t = base + h * HOUR
        day, hour = divmod(h, 24)
        if hour == 3 and day > 0:
            mu = mu + rng.normal(0, math.sqrt(q) * sigma, size=2)
            # skewed: a heavy low tail with mean zero; otherwise Gaussian
            e = -rng.exponential(sigma, size=2) + sigma if skew else rng.normal(0, sigma, size=2)
            vals = vals.copy()
            vals[:, F_T1] = math.log(100e-6) + mu + e
            vals[:, F_T2] = math.log(90e-6) + mu + rng.normal(0, sigma, size=2)
        if hour % 4 == 0:
            vals = vals.copy()
            vals[:, F_RO] = math.log(0.02) + rng.normal(0, 0.1, size=2)
        dates = (f"d{day}", f"d{day}")
        out.append(cf.Fields(f"f{h}", t, f"digest{h}", dates, vals.copy()))
    return out


def selftest() -> None:
    rng = np.random.default_rng(7)
    # logistic solver recovers a known sign structure
    Xs = rng.normal(size=(2000, 3))
    ys = (rng.uniform(size=2000) < 1 / (1 + np.exp(-(1.5 * Xs[:, 0] - 1.0 * Xs[:, 1])))).astype(
        float
    )
    b = fit_logistic(Xs, ys, 0.01)
    assert b[1] > 1.0 and b[2] < -0.6 and abs(b[3]) < 0.3, b
    assert 0.6 < auc(predict_logistic(Xs, b), ys) < 0.95
    # nulls on Gaussian data agree; on skewed data the Gaussian null over-predicts on the dip side
    for skew in (False, True):
        fields = _synthetic_fields(rng, skew)
        data = build_data(fields)
        data.cut = fields[-1].time + 1.0  # everything is "training" for the null machinery
        _, events = ce.build_rows(data.files, data.states, DELTA, K, data.cut)
        sigma = ce.robust_sigma(events, data.cut)
        rho, _ = ce.pooled_rho(events, data.cut)
        qd = ce.q_of(rho)
        res = [qubit_residuals(data, events[q], q) for q in range(2)]
        pooled = np.concatenate(
            [(r - np.median(r)) / (1.4826 * np.median(np.abs(r - np.median(r)))) for r in res]
        )
        emp = simulate_null(data, events, sigma, qd, "empirical", res, pooled, rng)
        gau = simulate_null(data, events, sigma, qd, "gaussian", res, pooled, rng)
        e_below = emp.sign_positives[:, 0].sum() / emp.sign_pairs[:, 0].sum()
        g_below = gau.sign_positives[:, 0].sum() / gau.sign_pairs[:, 0].sum()
        e_above = emp.sign_positives[:, 1].sum() / emp.sign_pairs[:, 1].sum()
        g_above = gau.sign_positives[:, 1].sum() / gau.sign_pairs[:, 1].sum()
        print(
            f"selftest skew={skew}: q={qd:.3f} below emp {e_below:.3f} gau {g_below:.3f}; "
            f"above emp {e_above:.3f} gau {g_above:.3f}"
        )
        if not skew:
            assert abs(e_below - g_below) < 0.08 and abs(e_above - g_above) < 0.08
        else:
            assert g_below > e_below + 0.05, (
                "Gaussian null should over-predict y=1 on the heavy-tailed side"
            )
    print("selftest ok")


class _FieldsUnpickler(pickle.Unpickler):
    """The collector pickles ``Fields`` under ``__main__`` when run as a script; map it back."""

    def find_class(self, module: str, name: str) -> Any:
        if name == "Fields" and module in ("__main__", "collect_fields"):
            return cf.Fields
        return super().find_class(module, name)


def load_fields(path: Path) -> list[Any]:
    with path.open("rb") as fh:
        fields: list[Any] = _FieldsUnpickler(fh).load()
    return fields


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--fields", type=Path)
    ap.add_argument("--ref", type=str, default="")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--rows-record", type=Path, default=HERE / "rows.tsv.gz")
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.fields or not args.out:
        ap.error("--fields and --out are required")
    fields = load_fields(args.fields)
    summary = run(fields, args.ref, args.out, None if args.no_guard else args.rows_record)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "train_rows",
                    "test_rows",
                    "primary_null",
                    "test_scores",
                    "clause_1",
                    "calibration",
                )
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
