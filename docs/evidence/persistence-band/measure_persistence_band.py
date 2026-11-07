"""Persistence band, heteroscedasticity bound, homogeneity versus staleness, in target space.

Implements the pre-registered protocol in ``README.md`` (section 2 and its 2.1 amendment)
against every ``ibm_fez`` snapshot at a pinned ``calibration-data`` ref, read through
``git show``. No model, no circuit, no Aer. NumPy only beyond the project's own loader,
target and digest code.

Run from the repository root with the pinned interpreter::

    PYTHONPATH=src:. python docs/evidence/persistence-band/measure_persistence_band.py \
        --repo . --ref 5828b4a2 --out <dir>

Outputs ``summary.json``, ``results.tsv`` (one row per reported figure) and ``pairs.tsv``
(the test rows, so a later band is scored on identical, citable rows).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scripts.canonical_snapshot_digest import qubit_digest
from scripts.init_error_analysis import _git, list_snapshots, read_snapshot

from superconducted.calibration.loader import load_snapshot
from superconducted.training.targets import gate_lengths, qubit_targets, snapshot_target

COMPONENTS = ("gamma", "lambda")
HORIZONS_H = (24.0, 168.0)
STALENESS_H = (1.0, 6.0, 24.0, 48.0, 168.0)
WINDOWS_D = (7.0, 30.0)
ACCEPT_H = 6.0
NOMINAL = 0.80
ALPHA = 0.2
MIN_BIN_ROWS = 20
MIN_WINDOW_STATES = 5
RECAL_FRACTION = 0.20
HOUR_BLOCKS = ((0, 6), (6, 12), (12, 18), (18, 24))
RECAL_EDGES_H = (12.0, 24.0)
BOOTSTRAP = 1000
SEED = 84
HOUR = 3600.0


@dataclass(frozen=True)
class FileRecord:
    path: str
    time: float  # epoch seconds of properties.last_update_date
    digest: str
    y: np.ndarray  # (2,) snapshot mean target, NaN if none usable
    per_qubit: np.ndarray  # (n_qubits, 2) with NaN where unusable
    t1_dates: tuple[str | None, ...]


def _epoch(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).timestamp()


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _quantile_80(values: np.ndarray) -> float:
    """Smallest r with coverage >= NOMINAL: the order statistic at ceil(NOMINAL * n)."""
    return float(np.quantile(values, NOMINAL, method="inverted_cdf"))


def _interval_score_rel(ratio: np.ndarray, r_lo: np.ndarray, r_hi: np.ndarray) -> np.ndarray:
    """Gneiting-Raftery interval score divided by y(t), for band [y(1 - r_lo), y(1 + r_hi)]."""
    lower = 1.0 - r_lo
    upper = 1.0 + r_hi
    return (
        (upper - lower)
        + (2.0 / ALPHA) * np.maximum(0.0, lower - ratio)
        + (2.0 / ALPHA) * np.maximum(0.0, ratio - upper)
    )


# ------------------------------------------------------------------------------- loading


def load_files(repo: Path, ref: str, backend: str) -> list[FileRecord]:
    records: list[FileRecord] = []
    paths = [p for p in list_snapshots(repo, ref, "snapshots") if f"/{backend}/" in p]
    tmpdir = Path(tempfile.gettempdir()) / "persistence-band"
    tmpdir.mkdir(exist_ok=True)
    tmp = tmpdir / "snapshot.json"
    for i, path in enumerate(paths):
        doc = read_snapshot(repo, ref, path)
        props = doc["properties"]
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        parsed = load_snapshot(tmp)
        targets = qubit_targets(parsed, gate_lengths(props))
        summary = snapshot_target(targets)
        y = np.full(2, np.nan) if summary is None else np.asarray(summary.mean, dtype=np.float64)
        per_qubit = np.where(targets.usable[:, None], targets.values, np.nan)
        t1_dates = tuple(
            next((p.get("date") for p in params if p.get("name") == "T1"), None)
            for params in props["qubits"]
        )
        records.append(
            FileRecord(
                path, _epoch(props["last_update_date"]), qubit_digest(doc), y, per_qubit, t1_dates
            )
        )
        if (i + 1) % 250 == 0:
            print(f"  read {i + 1}/{len(paths)} files", file=sys.stderr)
    records.sort(key=lambda r: (r.time, r.path))
    return records


def distinct_states(files: list[FileRecord]) -> list[int]:
    """Indices (into the time-sorted file list) of the first file of each distinct state."""
    seen: set[str] = set()
    out: list[int] = []
    for i, rec in enumerate(files):
        if rec.digest not in seen:
            seen.add(rec.digest)
            out.append(i)
    return out


def index_digests(repo: Path, ref: str) -> set[str]:
    text = _git(repo, "show", f"{ref}:health/state-index.tsv").decode("utf-8")
    return {line.split("\t")[2] for line in text.splitlines()[1:] if line.strip()}


def recal_times(files: list[FileRecord]) -> list[float]:
    """Times of chip-wide T1 recalibrations: >= RECAL_FRACTION of comparable qubits re-stamped."""
    out: list[float] = []
    for prev, cur in pairwise(files):
        pairs = [
            (a, b)
            for a, b in zip(prev.t1_dates, cur.t1_dates, strict=False)
            if a is not None and b is not None
        ]
        if not pairs:
            continue
        changed = sum(1 for a, b in pairs if a != b)
        if changed / len(pairs) >= RECAL_FRACTION:
            out.append(cur.time)
    return out


class AsOf:
    """Latest file at or before a time, accepted only inside the window."""

    def __init__(self, files: list[FileRecord]) -> None:
        self._files = files
        self._times = [f.time for f in files]

    def __call__(self, when: float, window_h: float = ACCEPT_H) -> int | None:
        i = bisect_right(self._times, when) - 1
        if i < 0 or self._times[i] <= when - window_h * HOUR:
            return None
        return i


# ------------------------------------------------------------------------------- pairs


@dataclass
class Pair:
    state: int  # file index of the state's first file
    future: int  # file index as of t + H
    train: bool
    change: np.ndarray  # (2,) bool per component
    distinct: bool
    ratio: np.ndarray  # (2,) y_future / y_state


def build_pairs(
    files: list[FileRecord], states: list[int], as_of: AsOf, horizon_h: float, cut: float
) -> tuple[list[Pair], Counter[str]]:
    pairs: list[Pair] = []
    dropped: Counter[str] = Counter()
    for s in states:
        t = files[s].time
        if not np.all(np.isfinite(files[s].y)):
            dropped["state_without_target"] += 1
            continue
        f = as_of(t + horizon_h * HOUR)
        if f is None:
            dropped["no_file_in_window"] += 1
            continue
        if t < cut <= t + horizon_h * HOUR:
            dropped["straddles_cut"] += 1
            continue
        if not np.all(np.isfinite(files[f].y)):
            dropped["future_without_target"] += 1
            continue
        y0, y1 = files[s].y, files[f].y
        pairs.append(
            Pair(
                state=s,
                future=f,
                train=t < cut,
                change=y1 != y0,
                distinct=files[f].digest != files[s].digest,
                ratio=y1 / y0,
            )
        )
    return pairs, dropped


def rows_of(pairs: list[Pair], comp: int, rowset: str, train: bool) -> list[Pair]:
    sel = [p for p in pairs if p.train == train]
    if rowset == "change":
        return [p for p in sel if bool(p.change[comp])]
    if rowset == "distinct":
        return [p for p in sel if p.distinct]
    return sel


def band_metrics(
    pairs: list[Pair], comp: int, r_lo: np.ndarray, r_hi: np.ndarray
) -> dict[str, float]:
    ratio = np.array([p.ratio[comp] for p in pairs])
    inside = (ratio >= 1.0 - r_lo) & (ratio <= 1.0 + r_hi)
    return {
        "n": float(len(pairs)),
        "coverage": float(np.mean(inside)) if len(pairs) else math.nan,
        "mean_rel_width": float(np.mean(r_lo + r_hi)) if len(pairs) else math.nan,
        "interval_score_rel": float(np.mean(_interval_score_rel(ratio, r_lo, r_hi)))
        if len(pairs)
        else math.nan,
    }


# ------------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--backend", default="ibm_fez")
    ap.add_argument("--cut", default="2026-09-01T00:00:00+00:00")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cut = _epoch(args.cut)
    rng = np.random.default_rng(np.random.SeedSequence(SEED))

    files = load_files(args.repo, args.ref, args.backend)
    states = distinct_states(files)
    expected = index_digests(args.repo, args.ref)
    got = {files[i].digest for i in states}
    if got != expected:
        raise SystemExit(
            f"distinct-state mismatch: script {len(got)} vs health/state-index.tsv "
            f"{len(expected)} at {args.ref}"
        )
    as_of = AsOf(files)
    recals = recal_times(files)
    summary: dict[str, Any] = {
        "ref": args.ref,
        "backend": args.backend,
        "files": len(files),
        "distinct_states": len(states),
        "state_index_distinct": len(expected),
        "first_file": _iso(files[0].time),
        "last_file": _iso(files[-1].time),
        "cut": _iso(cut),
        "chipwide_t1_recalibrations": len(recals),
        "horizons_h": list(HORIZONS_H),
    }
    results: list[dict[str, Any]] = []

    def emit(measurement: str, **kw: Any) -> None:
        results.append({"measurement": measurement, **kw})

    pairs_out: list[dict[str, Any]] = []
    r_star: dict[str, float] = {}

    for horizon in HORIZONS_H:
        pairs, dropped = build_pairs(files, states, as_of, horizon, cut)
        hkey = f"H{int(horizon)}h"
        summary[hkey] = {
            "pairs_train": sum(p.train for p in pairs),
            "pairs_test": sum(not p.train for p in pairs),
            "dropped": dict(dropped),
        }
        for p in pairs:
            if not p.train:
                pairs_out.append(
                    {
                        "horizon_h": int(horizon),
                        "state_time": _iso(files[p.state].time),
                        "state_file": files[p.state].path,
                        "asof_time": _iso(files[p.future].time),
                        "asof_file": files[p.future].path,
                        "distinct": int(p.distinct),
                        "change_gamma": int(p.change[0]),
                        "change_lambda": int(p.change[1]),
                    }
                )
        for ci, comp in enumerate(COMPONENTS):
            # ---- L-009 mutation check: zero-width band
            for rowset in ("all", "change"):
                test = rows_of(pairs, ci, rowset, train=False)
                zero = band_metrics(test, ci, np.zeros(len(test)), np.zeros(len(test)))
                emit(
                    "zero_width_band",
                    component=comp,
                    horizon_h=horizon,
                    rowset=rowset,
                    metric="coverage",
                    value=zero["coverage"],
                    n=zero["n"],
                )
                if rowset == "change" and len(test) and zero["coverage"] != 0.0:
                    raise SystemExit(
                        f"row definition wrong: zero-width band covers {zero['coverage']} "
                        "on change rows"
                    )
            # ---- constant persistence band
            train = rows_of(pairs, ci, "change", train=True)
            d_train = np.abs(np.array([p.ratio[ci] - 1.0 for p in train]))
            r = _quantile_80(d_train)
            boot = np.array(
                [
                    _quantile_80(rng.choice(d_train, size=d_train.size, replace=True))
                    for _ in range(BOOTSTRAP)
                ]
            )
            r_lo90, r_hi90 = (float(np.quantile(boot, q)) for q in (0.05, 0.95))
            if horizon == 24.0:
                r_star[comp] = r
            emit(
                "persistence_fit",
                component=comp,
                horizon_h=horizon,
                rowset="change",
                metric="r_train",
                value=r,
                n=float(len(train)),
                ci90_low=r_lo90,
                ci90_high=r_hi90,
            )
            test_change = rows_of(pairs, ci, "change", train=False)
            r_oracle = (
                _quantile_80(np.abs(np.array([p.ratio[ci] - 1.0 for p in test_change])))
                if test_change
                else math.nan
            )
            emit(
                "persistence_fit",
                component=comp,
                horizon_h=horizon,
                rowset="change",
                metric="r_oracle_test",
                value=r_oracle,
                n=float(len(test_change)),
            )
            for rowset in ("change", "distinct", "all"):
                test = rows_of(pairs, ci, rowset, train=False)
                m = band_metrics(test, ci, np.full(len(test), r), np.full(len(test), r))
                for k, v in m.items():
                    if k != "n":
                        emit(
                            "persistence_band",
                            component=comp,
                            horizon_h=horizon,
                            rowset=rowset,
                            metric=k,
                            value=v,
                            n=m["n"],
                            r=r,
                        )
            # ---- rolling percentile band
            state_times = np.array([files[s].time for s in states])
            state_y = np.array([files[s].y[ci] for s in states])
            for window in WINDOWS_D:
                for rowset in ("change", "all"):
                    test = rows_of(pairs, ci, rowset, train=False)
                    r_lo_list: list[float] = []
                    r_hi_list: list[float] = []
                    kept: list[Pair] = []
                    for p in test:
                        t = files[p.state].time
                        mask = (
                            (state_times > t - window * 86400.0)
                            & (state_times <= t)
                            & np.isfinite(state_y)
                        )
                        if mask.sum() < MIN_WINDOW_STATES:
                            continue
                        lo, hi = np.quantile(state_y[mask], (0.10, 0.90))
                        y0 = files[p.state].y[ci]
                        r_lo_list.append(1.0 - lo / y0)
                        r_hi_list.append(hi / y0 - 1.0)
                        kept.append(p)
                    m = band_metrics(kept, ci, np.array(r_lo_list), np.array(r_hi_list))
                    for k, v in m.items():
                        if k != "n":
                            emit(
                                "rolling_percentile_band",
                                component=comp,
                                horizon_h=horizon,
                                rowset=rowset,
                                metric=k,
                                value=v,
                                n=m["n"],
                                window_d=window,
                            )
            # ---- heteroscedasticity
            if not train or not test_change:
                continue
            level_edges = np.quantile(
                np.array([files[p.state].y[ci] for p in train]), (1 / 3, 2 / 3)
            )

            def bin_of(
                p: Pair, binning: str, ci: int = ci, level_edges: np.ndarray = level_edges
            ) -> str | None:
                t = files[p.state].time
                if binning == "level":
                    y0 = files[p.state].y[ci]
                    return (
                        "low" if y0 <= level_edges[0] else "mid" if y0 <= level_edges[1] else "high"
                    )
                if binning == "hour":
                    h = datetime.fromtimestamp(t, UTC).hour
                    return next(f"{a:02d}-{b:02d}" for a, b in HOUR_BLOCKS if a <= h < b)
                j = bisect_right(recals, t) - 1
                if j < 0:
                    return None
                since = (t - recals[j]) / HOUR
                return (
                    "<12h"
                    if since < RECAL_EDGES_H[0]
                    else "12-24h"
                    if since <= RECAL_EDGES_H[1]
                    else ">24h"
                )

            for binning in ("level", "hour", "recal"):
                r_b: dict[str, float] = {}
                r_b_ci: dict[str, tuple[float, float]] = {}
                fallback: list[str] = []
                train_bins: dict[str, list[float]] = {}
                for p in train:
                    b = bin_of(p, binning)
                    if b is not None:
                        train_bins.setdefault(b, []).append(abs(p.ratio[ci] - 1.0))
                for b, vals in sorted(train_bins.items()):
                    arr = np.array(vals)
                    if arr.size < MIN_BIN_ROWS:
                        r_b[b] = r
                        fallback.append(b)
                        continue
                    r_b[b] = _quantile_80(arr)
                    bb = np.array(
                        [
                            _quantile_80(rng.choice(arr, size=arr.size, replace=True))
                            for _ in range(BOOTSTRAP)
                        ]
                    )
                    r_b_ci[b] = (float(np.quantile(bb, 0.05)), float(np.quantile(bb, 0.95)))
                    emit(
                        "hetero_bin_fit",
                        component=comp,
                        horizon_h=horizon,
                        rowset="change",
                        binning=binning,
                        bin=b,
                        metric="r_b_train",
                        value=r_b[b],
                        n=float(arr.size),
                        ci90_low=r_b_ci[b][0],
                        ci90_high=r_b_ci[b][1],
                    )
                test_binned = [(p, bin_of(p, binning)) for p in test_change]
                test_binned = [(p, b) for p, b in test_binned if b is not None]
                kept_pairs = [p for p, _ in test_binned]
                applied = np.array([r_b.get(b, r) for _, b in test_binned])
                cond = band_metrics(kept_pairs, ci, applied, applied)
                const = band_metrics(
                    kept_pairs, ci, np.full(len(kept_pairs), r), np.full(len(kept_pairs), r)
                )
                # oracle: per-bin r fitted on the test rows themselves, against the constant
                # oracle on the same rows
                test_bins: dict[str, list[float]] = {}
                for p, b in test_binned:
                    test_bins.setdefault(b, []).append(abs(p.ratio[ci] - 1.0))
                r_b_oracle = {b: _quantile_80(np.array(v)) for b, v in test_bins.items()}
                applied_oracle = np.array([r_b_oracle[b] for _, b in test_binned])
                oracle = band_metrics(kept_pairs, ci, applied_oracle, applied_oracle)
                const_oracle_r = _quantile_80(
                    np.abs(np.array([p.ratio[ci] - 1.0 for p in kept_pairs]))
                )
                const_oracle = band_metrics(
                    kept_pairs,
                    ci,
                    np.full(len(kept_pairs), const_oracle_r),
                    np.full(len(kept_pairs), const_oracle_r),
                )
                for label, m in (
                    ("conditional", cond),
                    ("constant", const),
                    ("oracle_conditional", oracle),
                    ("oracle_constant", const_oracle),
                ):
                    for k, v in m.items():
                        if k != "n":
                            emit(
                                "hetero_band",
                                component=comp,
                                horizon_h=horizon,
                                rowset="change",
                                binning=binning,
                                variant=label,
                                metric=k,
                                value=v,
                                n=m["n"],
                            )
                emit(
                    "hetero_band",
                    component=comp,
                    horizon_h=horizon,
                    rowset="change",
                    binning=binning,
                    variant="width_ratio_conditional_over_constant",
                    metric="ratio",
                    value=cond["mean_rel_width"] / const["mean_rel_width"]
                    if const["mean_rel_width"]
                    else math.nan,
                    n=cond["n"],
                )
                emit(
                    "hetero_band",
                    component=comp,
                    horizon_h=horizon,
                    rowset="change",
                    binning=binning,
                    variant="width_ratio_oracle_conditional_over_oracle_constant",
                    metric="ratio",
                    value=oracle["mean_rel_width"] / const_oracle["mean_rel_width"]
                    if const_oracle["mean_rel_width"]
                    else math.nan,
                    n=oracle["n"],
                    fallback_bins=",".join(fallback),
                )

    # ---- homogeneity versus staleness, on test states
    test_states = [s for s in states if files[s].time >= cut and np.all(np.isfinite(files[s].y))]
    for ci, comp in enumerate(COMPONENTS):
        rstar = r_star.get(comp, math.nan)
        fresh_rel_all: list[float] = []
        fresh_abs_all: list[float] = []
        fresh_in_all: list[bool] = []
        for s in test_states:
            truth = files[s].per_qubit[:, ci]
            ok = np.isfinite(truth)
            yhat = float(np.nanmean(truth))
            rel = np.abs(yhat / truth[ok] - 1.0)
            fresh_rel_all.extend(rel.tolist())
            fresh_abs_all.extend(np.abs(yhat - truth[ok]).tolist())
            fresh_in_all.extend(
                ((truth[ok] >= yhat * (1 - rstar)) & (truth[ok] <= yhat * (1 + rstar))).tolist()
            )
        fr = np.array(fresh_rel_all)
        emit(
            "homogeneity_vs_staleness",
            component=comp,
            model="homogeneous_fresh",
            staleness_h=0.0,
            rowset="all",
            metric="median_rel_abs_err",
            value=float(np.median(fr)),
            n=float(fr.size),
        )
        emit(
            "homogeneity_vs_staleness",
            component=comp,
            model="homogeneous_fresh",
            staleness_h=0.0,
            rowset="all",
            metric="p90_rel_abs_err",
            value=float(np.quantile(fr, 0.9)),
            n=float(fr.size),
        )
        emit(
            "homogeneity_vs_staleness",
            component=comp,
            model="homogeneous_fresh",
            staleness_h=0.0,
            rowset="all",
            metric="median_abs_err",
            value=float(np.median(fresh_abs_all)),
            n=float(fr.size),
        )
        emit(
            "homogeneity_vs_staleness",
            component=comp,
            model="homogeneous_fresh",
            staleness_h=0.0,
            rowset="all",
            metric="frac_within_rstar",
            value=float(np.mean(fresh_in_all)),
            n=float(fr.size),
            r_star=rstar,
        )
        for d_h in STALENESS_H:
            rows: dict[str, dict[str, list[float]]] = {
                "all": {"rel": [], "abs": [], "in": [], "frel": [], "fabs": [], "fin": []},
                "moved": {"rel": [], "abs": [], "in": [], "frel": [], "fabs": [], "fin": []},
            }
            n_states_used = 0
            for s in test_states:
                f = as_of(files[s].time - d_h * HOUR)
                if f is None:
                    continue
                n_states_used += 1
                truth = files[s].per_qubit[:, ci]
                stale = files[f].per_qubit[:, ci]
                ok = np.isfinite(truth) & np.isfinite(stale)
                fresh_hat = float(np.nanmean(truth))
                for rowset in ("all", "moved"):
                    sel = ok if rowset == "all" else ok & (stale != truth)
                    tr, st = truth[sel], stale[sel]
                    rows[rowset]["rel"].extend(np.abs(st / tr - 1.0).tolist())
                    rows[rowset]["abs"].extend(np.abs(st - tr).tolist())
                    rows[rowset]["in"].extend(
                        ((tr >= st * (1 - rstar)) & (tr <= st * (1 + rstar))).tolist()
                    )
                    rows[rowset]["frel"].extend(np.abs(fresh_hat / tr - 1.0).tolist())
                    rows[rowset]["fabs"].extend(np.abs(fresh_hat - tr).tolist())
                    rows[rowset]["fin"].extend(
                        ((tr >= fresh_hat * (1 - rstar)) & (tr <= fresh_hat * (1 + rstar))).tolist()
                    )
            for rowset, cols in rows.items():
                n = float(len(cols["rel"]))
                if n == 0:
                    continue
                for model, rel_k, abs_k, in_k in (
                    ("stale_per_qubit", "rel", "abs", "in"),
                    ("homogeneous_fresh_same_rows", "frel", "fabs", "fin"),
                ):
                    rel_arr = np.array(cols[rel_k])
                    emit(
                        "homogeneity_vs_staleness",
                        component=comp,
                        model=model,
                        staleness_h=d_h,
                        rowset=rowset,
                        metric="median_rel_abs_err",
                        value=float(np.median(rel_arr)),
                        n=n,
                        states=n_states_used,
                    )
                    emit(
                        "homogeneity_vs_staleness",
                        component=comp,
                        model=model,
                        staleness_h=d_h,
                        rowset=rowset,
                        metric="p90_rel_abs_err",
                        value=float(np.quantile(rel_arr, 0.9)),
                        n=n,
                    )
                    emit(
                        "homogeneity_vs_staleness",
                        component=comp,
                        model=model,
                        staleness_h=d_h,
                        rowset=rowset,
                        metric="median_abs_err",
                        value=float(np.median(cols[abs_k])),
                        n=n,
                    )
                    emit(
                        "homogeneity_vs_staleness",
                        component=comp,
                        model=model,
                        staleness_h=d_h,
                        rowset=rowset,
                        metric="frac_within_rstar",
                        value=float(np.mean(cols[in_k])),
                        n=n,
                        r_star=rstar,
                    )

    # ---- write
    keys: list[str] = []
    for row in results:
        for k in row:
            if k not in keys:
                keys.append(k)
    with (args.out / "results.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, delimiter="\t")
        w.writeheader()
        w.writerows(results)
    with (args.out / "pairs.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs_out[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(pairs_out)
    summary["results_rows"] = len(results)
    summary["test_pairs_written"] = len(pairs_out)
    summary["r_star_24h"] = r_star
    summary["python"] = sys.version.split()[0]
    summary["numpy"] = np.__version__
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    # a compact view of the headline rows
    for row in results:
        if row["measurement"] in ("persistence_fit", "zero_width_band") or (
            row["measurement"] == "persistence_band" and row["rowset"] == "change"
        ):
            print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()})
    if os.environ.get("PERSISTENCE_BAND_KEEP_TMP") is None:
        (Path(tempfile.gettempdir()) / "persistence-band" / "snapshot.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
