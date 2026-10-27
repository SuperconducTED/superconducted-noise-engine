"""Amended N1 after the statistics review of PR #128 (README section 7, amendment 8).

Analysis after the test outputs were examined, not a confirmatory test. Changes against
``n1_baselines.py``: warm-up purge (no row, null pair or residual before the first complete 30-day
window), crossing-row purge (training labels that use post-cut events leave the training set and do
not enter test), inner tuning split on a complete timestamp with the same purge and scaling fitted
on the fitting slice, null scales made consistent (residual shape at zero mean and unit variance,
noise variance from increments under the local-level model) with a recovery check, and a circular
block bootstrap over consecutive calendar days with the block length chosen from the daily
score-difference autocorrelation. The 2026-10-26 outputs are untouched; this writes a new folder.

    PYTHONPATH=src;. python docs/evidence/pattern-detector/n1_amended.py \
        --fields <scratch>/fields.pkl --ref <sha> \\
        --out docs/evidence/pattern-detector/amended-2026-10-27
"""

# ruff: noqa: N806  (matrix notation: X is the standard symbol)
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from itertools import pairwise
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


n1 = _load("n1_baselines")
ce = n1.ce

WARMUP_D = 30.0
BLOCK_LENGTHS = (1, 3, 5, 7, 10)
HORIZON_FLOOR_DAYS = 6  # five successor events at about one a day, plus the event itself
SEED_BOOT = 85
FLOOR_PER_PARAMETER = 10


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).date().isoformat()


# ------------------------------------------------------------------------------- null parameters


def increment_sigma(all_events: list[list[Any]], cut: float, q: float) -> np.ndarray:
    """sigma_e per qubit from Var(D) = sigma_e^2 (2 + q) on training increments; NaN below 20."""
    out = []
    for ev in all_events:
        inc = np.array([e.increment for e in ev if e.time < cut])
        out.append(math.sqrt(float(np.var(inc)) / (2.0 + q)) if inc.size >= 20 else math.nan)
    return np.array(out)


def increment_stats(all_events: list[list[Any]], lo: float, hi: float) -> dict[str, float]:
    """Observed variance and pooled lag-one autocorrelation of increments with lo <= time < hi."""
    incs, pairs = [], []
    for ev in all_events:
        sel = [e for e in ev if lo <= e.time < hi]
        incs.extend(e.increment for e in sel)
        pairs.extend((a.increment, b.increment) for a, b in pairwise(sel))
    arr = np.array(pairs)
    rho = float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1]) if len(pairs) > 2 else math.nan
    return {"n": len(incs), "variance": float(np.var(incs)), "rho": rho, "pairs": len(pairs)}


def full_history_residuals(data: Any, events: list[Any], q: int, t_full: float) -> np.ndarray:
    out = []
    for e in events:
        if e.time >= data.cut:
            break
        if e.time < t_full:
            continue
        lvl = ce.level_at(data.files, data.state_times, data.states, q, e.time)
        if lvl is not None:
            out.append(e.value - lvl[0])
    return np.array(out)


def diag_summary(diag: dict[str, Any], observed: dict[str, float]) -> dict[str, Any]:
    n = diag["inc_n"]
    mean = diag["inc_sum"] / n
    var = diag["inc_sum2"] / n - mean**2
    pn = diag["pair_n"]
    mx, my = diag["pair_x"] / pn, diag["pair_y"] / pn
    cov = diag["pair_xy"] / pn - mx * my
    vx = diag["pair_x2"] / pn - mx**2
    vy = diag["pair_y2"] / pn - my**2
    rho = cov / math.sqrt(vx * vy)
    d = np.array(diag["d_sample"])
    return {
        "sim_increment_variance": var,
        "observed_increment_variance": observed["variance"],
        "variance_ratio_sim_over_obs": var / observed["variance"],
        "sim_lag1_rho": rho,
        "observed_lag1_rho": observed["rho"],
        "sim_residual_quantiles": {
            k: float(np.quantile(d, p))
            for k, p in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95))
        },
        "sim_residual_skew": float(np.mean((d - d.mean()) ** 3) / np.std(d) ** 3),
        "sim_residual_n": int(d.size),
    }


# ------------------------------------------------------------------------------- block bootstrap


def circular_block_bootstrap(
    days: np.ndarray,
    y: np.ndarray,
    preds: dict[str, np.ndarray],
    block: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """Resample consecutive calendar days in circular blocks of `block` days, qubits together."""
    uniq = np.array(sorted(np.unique(days)))
    groups = {d: np.where(days == d)[0] for d in uniq}
    n_days = uniq.size
    out = {k: np.empty(n1.BOOTSTRAP) for k in preds}
    for b in range(n1.BOOTSTRAP):
        drawn: list[str] = []
        while len(drawn) < n_days:
            start = int(rng.integers(0, n_days))
            drawn.extend(uniq[(start + j) % n_days] for j in range(block))
        drawn = drawn[:n_days]
        idx = np.concatenate([groups[d] for d in drawn])
        for k, p in preds.items():
            out[k][b] = n1.brier(p[idx], y[idx])
    return out


def daily_difference_acf(
    days: np.ndarray, y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray, max_lag: int = 12
) -> list[float]:
    """Autocorrelation of the daily mean Brier difference (a minus b) over consecutive test days."""
    uniq = np.array(sorted(np.unique(days)))
    daily = np.array(
        [
            np.mean((p_a[days == d] - y[days == d]) ** 2 - (p_b[days == d] - y[days == d]) ** 2)
            for d in uniq
        ]
    )
    daily = daily - daily.mean()
    denom = float(np.sum(daily**2))
    return [float(np.sum(daily[:-lag] * daily[lag:]) / denom) for lag in range(1, max_lag + 1)]


def choose_block(acf: list[float], n_days: int) -> int:
    """Smallest lag at which the acf stays inside two standard errors, floored at the horizon."""
    bound = 2.0 / math.sqrt(n_days)
    chosen = HORIZON_FLOOR_DAYS
    for lag in range(1, len(acf) + 1):
        if all(abs(x) < bound for x in acf[lag - 1 :]):
            chosen = max(HORIZON_FLOOR_DAYS, lag)
            break
    else:
        chosen = max(HORIZON_FLOOR_DAYS, len(acf))
    return chosen


# ------------------------------------------------------------------------------- main run


def run(fields: list[Any], ref: str, out: Path, rows_record: Path) -> dict[str, Any]:
    data = n1.build_data(fields)
    built = n1.build_features(data)
    summary: dict[str, Any] = {
        "amended": (
            "2026-10-27, after the statistics review of PR #128; "
            "analysis after the test outputs were examined"
        ),
        "ref": ref,
        "files": len(fields),
        "distinct_states": len(data.states),
    }
    # guard against the N0 record
    rec = {}
    with gzip.open(rows_record, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["y"] != "":
                rec[(int(row["qubit"]), row["time"])] = (float(row["d"]), int(row["y"]))
    rows_all, _ = ce.build_rows(data.files, data.states, n1.DELTA, n1.K, data.cut)
    mine = {(r.qubit, _iso(r.time)): (round(r.d, 6), r.y) for r in rows_all if r.y is not None}
    if set(mine) != set(rec) or any(
        abs(mine[k][0] - rec[k][0]) > 1e-6 or mine[k][1] != rec[k][1] for k in mine
    ):
        raise SystemExit(
            "reproduction guard: rows rebuilt from the field collection differ from rows.tsv.gz"
        )
    summary["guard_rows"] = len(mine)
    summary["excluded_features"] = built.excluded

    # purges
    t0 = data.files[0].time
    t_full = t0 + WARMUP_D * n1.DAY
    before_cut = built.times < data.cut
    warm = built.times < t_full
    cross = before_cut & (built.label_times >= data.cut)
    assert np.array_equal(cross, built.crosses & before_cut)
    train = before_cut & ~warm & ~cross
    test = ~before_cut
    split = np.where(
        train, "train", np.where(test, "test", np.where(warm, "purged_warmup", "purged_crossing"))
    )
    summary["warmup_boundary"] = _iso(t_full)
    counts = {}
    for name, m in (
        ("train", train),
        ("test", test),
        ("purged_warmup", warm),
        ("purged_crossing", cross & ~warm),
    ):
        counts[name] = {
            "rows": int(m.sum()),
            "positives": int(built.y[m].sum()),
            "rate": float(built.y[m].mean()) if m.any() else math.nan,
            "days": len({_day(t) for t in built.times[m]}),
        }
    counts["unpurged_train_2026_10_26"] = {
        "rows": int(before_cut.sum()),
        "positives": int(built.y[before_cut].sum()),
        "rate": float(built.y[before_cut].mean()),
    }
    summary["counts"] = counts
    n_params = 1 + sum(1 for j in range(built.X.shape[1]) if np.std(built.X[train, j]) > 0)
    floor_full = FLOOR_PER_PARAMETER * n_params
    tree = {
        "parameters": n_params,
        "floor_training_positives": floor_full,
        "train_positives": counts["train"]["positives"],
        "test_positives": counts["test"]["positives"],
        "test_days": counts["test"]["days"],
    }
    tree["branch"] = (
        "1: full feature list"
        if counts["train"]["positives"] >= floor_full
        and counts["test"]["positives"] >= 30
        and counts["test"]["days"] >= 30
        else "2 or lower: see README section 6"
    )
    summary["decision_tree"] = tree

    # null parameters (increments, not labels)
    rho, n_pairs = ce.pooled_rho(built.events, data.cut)
    q = ce.q_of(rho)
    sigma = increment_sigma(built.events, data.cut, q)
    sigma_filled = np.where(np.isfinite(sigma), sigma, float(np.nanmedian(sigma)))
    obs_all = increment_stats(built.events, -math.inf, data.cut)
    obs_full = increment_stats(built.events, t_full, data.cut)
    summary["null_parameters"] = {
        "rho": rho,
        "rho_pairs": n_pairs,
        "q": q,
        "sigma_e_from_increments_median": float(np.nanmedian(sigma)),
        "sigma_fallback_qubits": int((~np.isfinite(sigma)).sum()),
        "observed_increments_train": obs_all,
        "observed_increments_full_history_train": obs_full,
    }
    residuals = [
        full_history_residuals(data, built.events[qi], qi, t_full)
        for qi in range(len(built.events))
    ]
    pooled = [
        (r - r.mean()) / r.std() for r in residuals if r.size >= n1.MIN_RESIDUALS and r.std() > 0
    ]
    pooled_std = np.concatenate(pooled)
    obs_res = np.concatenate([r for r in residuals if r.size >= n1.MIN_RESIDUALS])
    summary["residuals_full_history"] = {
        "qubits_with_shape": len(pooled),
        "n": int(obs_res.size),
        "quantiles": {
            k: float(np.quantile(obs_res, p))
            for k, p in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95))
        },
        "skew": float(np.mean((obs_res - obs_res.mean()) ** 3) / np.std(obs_res) ** 3),
        "standardised_skew": float(np.mean(pooled_std**3) / np.mean(pooled_std**2) ** 1.5),
    }
    rng = np.random.default_rng(np.random.SeedSequence(n1.SEED))
    nulls, diags = {}, {}
    for name in ("empirical", "gaussian"):
        diag: dict[str, Any] = {}
        nulls[name] = n1.simulate_null(
            data,
            built.events,
            sigma_filled,
            q,
            name,
            residuals,
            pooled_std,
            rng,
            count_from=t_full,
            standardise="variance",
            diag=diag,
        )
        diags[name] = diag_summary(diag, obs_all)
    summary["null_recovery_check"] = diags
    d_obs = built.X[:, 0]
    p_null = {}
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

    # inner tuning: complete-timestamp boundary, purge by label time, scaling on the fitting slice
    X = built.X.copy()
    keep = [j for j in range(X.shape[1]) if np.std(X[train, j]) > 0]
    dropped = [n1.COLUMNS[j] for j in range(X.shape[1]) if j not in keep]
    X = X[:, keep]
    tr_times = np.sort(built.times[train])
    t_b = float(
        tr_times[int(n1.INNER_FRACTION * tr_times.size) - 1]
    )  # all rows at this time go to fitting
    inner_fit = train & (built.times <= t_b) & (built.label_times <= t_b)
    inner_val = train & (built.times > t_b)
    m_in, s_in = X[inner_fit].mean(axis=0), X[inner_fit].std(axis=0)
    s_in[s_in == 0] = 1.0
    losses = {}
    for lam in n1.LAMBDA_GRID:
        b = n1.fit_logistic(n1.standardise(X[inner_fit], m_in, s_in), built.y[inner_fit], lam)
        losses[lam] = n1.log_loss(
            n1.predict_logistic(n1.standardise(X[inner_val], m_in, s_in), b), built.y[inner_val]
        )
    lam_best = min(losses, key=losses.get)
    mean, std = X[train].mean(axis=0), X[train].std(axis=0)
    Xs = n1.standardise(X, mean, std)
    beta = n1.fit_logistic(Xs[train], built.y[train], lam_best)
    p_log = n1.predict_logistic(Xs, beta)
    summary["logistic"] = {
        "dropped_constant_columns": dropped,
        "inner_boundary": _iso(t_b),
        "inner_fit_rows": int(inner_fit.sum()),
        "inner_fit_rows_purged_by_label_time": int(
            (train & (built.times <= t_b)).sum() - inner_fit.sum()
        ),
        "inner_val_rows": int(inner_val.sum()),
        "lambda_losses": {str(k): v for k, v in losses.items()},
        "lambda": lam_best,
        "lambda_at_grid_boundary": lam_best in (n1.LAMBDA_GRID[0], n1.LAMBDA_GRID[-1]),
        "coefficients_standardised": {
            n1.COLUMNS[j]: float(beta[1 + i]) for i, j in enumerate(keep)
        },
        "intercept": float(beta[0]),
    }

    # scores on test rows
    yt = built.y[test]
    p0 = float(built.y[train].mean())
    preds = {
        "empirical_null": p_null["empirical"],
        "gaussian_null": p_null["gaussian"],
        "constant_p0_purged_train": np.full(len(built.y), p0),
        "constant_2026_10_26": np.full(len(built.y), float(built.y[before_cut].mean())),
        "always_level": np.zeros(len(built.y)),
        "logistic": p_log,
    }
    scores = {
        name: {
            "brier": n1.brier(p[test], yt),
            "log_loss": n1.log_loss(p[test], yt),
            "auc": n1.auc(p[test], yt),
            "mean_forecast": float(p[test].mean()),
        }
        for name, p in preds.items()
    }
    scores["always_level"]["log_loss_note"] = (
        "clipped at 1e-6; a literal p = 0 forecast has infinite log loss"
    )
    p0_test = float(yt.mean())
    scores["oracle_constant_test_rate"] = {
        "brier": p0_test * (1 - p0_test),
        "auc": 0.5,
        "mean_forecast": p0_test,
    }
    primary = (
        "empirical_null"
        if scores["empirical_null"]["brier"] <= scores["gaussian_null"]["brier"]
        else "gaussian_null"
    )
    for name in scores:
        scores[name]["bss_vs_primary_null"] = 1 - scores[name]["brier"] / scores[primary]["brier"]
        scores[name]["bss_vs_always_level"] = (
            1 - scores[name]["brier"] / scores["always_level"]["brier"]
        )
        scores[name]["bss_vs_constant_purged"] = (
            1 - scores[name]["brier"] / scores["constant_p0_purged_train"]["brier"]
        )
    summary["test_scores"] = scores
    summary["primary_null"] = primary

    # calibration diagnostic per sign, with the logistic column
    calib = []
    for sname, mask in (("train", train), ("test", test)):
        for sign, smask in (("below", d_obs < 0), ("above", d_obs > 0)):
            m = mask & smask
            calib.append(
                {
                    "split": sname,
                    "sign": sign,
                    "rows": int(m.sum()),
                    "observed_rate": float(built.y[m].mean()),
                    "empirical_mean_forecast": float(p_null["empirical"][m].mean()),
                    "gaussian_mean_forecast": float(p_null["gaussian"][m].mean()),
                    "logistic_mean_forecast": float(p_log[m].mean()),
                }
            )
    summary["calibration"] = calib

    # block bootstrap over consecutive test days
    days = np.array([_day(t) for t in built.times[test]])
    acf = daily_difference_acf(days, yt, preds[primary][test], p_log[test])
    block = choose_block(acf, int(np.unique(days).size))
    boot_tables = {}
    for L in sorted(set(BLOCK_LENGTHS) | {block}):
        boot = circular_block_bootstrap(
            days,
            yt,
            {k: v[test] for k, v in preds.items()},
            L,
            np.random.default_rng(np.random.SeedSequence(SEED_BOOT + L)),
        )
        boot_tables[str(L)] = {
            "bs_null_minus_bs_logistic_90": n1.interval(boot[primary] - boot["logistic"]),
            "bss_logistic_vs_null_90": n1.interval(1 - boot["logistic"] / boot[primary]),
            "bs_always_level_minus_bs_logistic_90": n1.interval(
                boot["always_level"] - boot["logistic"]
            ),
            "bs_constant_purged_minus_bs_logistic_90": n1.interval(
                boot["constant_p0_purged_train"] - boot["logistic"]
            ),
            "bs_always_level_minus_bs_null_90": n1.interval(boot["always_level"] - boot[primary]),
        }
    summary["bootstrap"] = {
        "test_days": int(np.unique(days).size),
        "resamples": n1.BOOTSTRAP,
        "daily_difference_acf": acf,
        "two_se_bound": 2.0 / math.sqrt(int(np.unique(days).size)),
        "block_length_chosen": block,
        "by_block_length": boot_tables,
    }
    chosen = boot_tables[str(block)]
    bss = scores["logistic"]["bss_vs_primary_null"]
    summary["clause_1_amended"] = {
        "bss_logistic_vs_primary_null": bss,
        "threshold": 0.10,
        "interval_excludes_zero_at_chosen_block": bool(
            chosen["bs_null_minus_bs_logistic_90"][0] > 0
        ),
        "holds": bool(bss >= 0.10 and chosen["bs_null_minus_bs_logistic_90"][0] > 0),
        "bss_vs_always_level": scores["logistic"]["bss_vs_always_level"],
        "bss_vs_constant_purged": scores["logistic"]["bss_vs_constant_purged"],
        "bss_vs_oracle": 1
        - scores["logistic"]["brier"] / scores["oracle_constant_test_rate"]["brier"],
    }

    # outputs
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / "features.tsv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "qubit",
                "time",
                "label_time",
                "split",
                "y",
                *n1.COLUMNS,
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
                    _iso(built.label_times[i]),
                    split[i],
                    int(built.y[i]),
                    *[f"{v:.6g}" for v in built.X[i]],
                    f"{p_null['empirical'][i]:.6f}",
                    f"{p_null['gaussian'][i]:.6f}",
                    f"{p_log[i]:.6f}",
                ]
            )
    with (out / "calibration.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(calib[0].keys()), delimiter="\t", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(calib)
    with (out / "null_bins.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            ["null", "sign", "abs_bin_lo", "pooled_pairs", "pooled_positives", "pooled_rate"]
        )
        for name, tab in nulls.items():
            pp, pq = tab.pairs.sum(axis=0), tab.positives.sum(axis=0)
            for bi in range(n1.N_SIGNED_BINS):
                sign = "below" if bi < len(n1.BIN_EDGES) else "above"
                edge = n1.BIN_EDGES[bi % len(n1.BIN_EDGES)]
                w.writerow(
                    [
                        name,
                        sign,
                        f"{edge:.2f}",
                        int(pp[bi]),
                        int(pq[bi]),
                        f"{pq[bi] / pp[bi]:.4f}" if pp[bi] else "",
                    ]
                )
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
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
    return summary


def selftest() -> None:
    rng = np.random.default_rng(11)
    # the block bootstrap keeps all rows of a day together and the chosen block respects the floor
    days = np.repeat([f"d{i:02d}" for i in range(40)], 3)
    y = (rng.uniform(size=days.size) < 0.3).astype(float)
    preds = {"a": np.full(days.size, 0.3), "b": np.clip(y * 0.6 + 0.2, 0, 1)}
    boot = circular_block_bootstrap(days, y, preds, 5, rng)
    assert boot["a"].size == n1.BOOTSTRAP and np.all(boot["b"] < boot["a"])
    acf = daily_difference_acf(days, y, preds["a"], preds["b"])
    assert len(acf) == 12 and all(abs(a) <= 1.0 for a in acf)
    assert choose_block(acf, 40) >= HORIZON_FLOOR_DAYS
    # increment sigma recovers sigma_e on a synthetic local-level series
    sigma_e, q = 0.2, 0.05
    mu = np.cumsum(rng.normal(0, math.sqrt(q) * sigma_e, 20000))
    L = mu + rng.normal(0, sigma_e, 20000)
    D = np.diff(L)
    est = math.sqrt(np.var(D) / (2 + q))
    assert abs(est - sigma_e) < 0.01, est
    print(f"selftest ok: block={choose_block(acf, 40)} sigma_e est {est:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--fields", type=Path)
    ap.add_argument("--ref", type=str, default="")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--rows-record", type=Path, default=HERE / "rows.tsv.gz")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.fields or not args.out:
        ap.error("--fields and --out are required")
    fields = n1.load_fields(args.fields)
    summary = run(fields, args.ref, args.out, args.rows_record)
    keys = (
        "counts",
        "decision_tree",
        "null_recovery_check",
        "primary_null",
        "test_scores",
        "clause_1_amended",
        "calibration",
    )
    print(json.dumps({k: summary[k] for k in keys}, indent=2, default=str))
    print(
        json.dumps(
            {
                "logistic": {
                    k: summary["logistic"][k]
                    for k in (
                        "lambda",
                        "inner_boundary",
                        "inner_fit_rows",
                        "inner_fit_rows_purged_by_label_time",
                        "inner_val_rows",
                        "dropped_constant_columns",
                    )
                },
                "block": summary["bootstrap"]["block_length_chosen"],
                "acf": [round(a, 3) for a in summary["bootstrap"]["daily_difference_acf"]],
                "chosen_intervals": summary["bootstrap"]["by_block_length"][
                    str(summary["bootstrap"]["block_length_chosen"])
                ],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
