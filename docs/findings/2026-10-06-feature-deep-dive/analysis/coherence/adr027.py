"""ADR-027's gamma and lambda per snapshot: rejections, and how much of the snapshot mean the
worst qubits carry.

Writes ``results/coherence/adr027.json``.

ADR-027 (docs/decisions.md; src/superconducted/training/targets.py) rejects each qubit by its
first applicable reason, in order: T1 missing, T2 missing, gate length missing, non-positive
values, T2 > 2 T1. The usable qubits give gamma = 1 - exp(-t/T1) and
lambda = 1 - exp(-t (2/T2 - 1/T1)) with t the sx length (24 ns in every file,
01-data-layer.md), and the snapshot target is the MEAN of the usable per-qubit targets.

Statistics are reported over all files and over distinct coherence states (a file whose
T1 and T2 vectors differ from the previous file's), because a state repeats in every file
until something is re-measured.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cohlib
import ddload


def summarise(x: np.ndarray) -> list[float] | None:
    return cohlib.q(x, (0.0, 0.1, 0.5, 0.9, 1.0))


def main() -> None:
    dd = ddload.DD()
    out = cohlib.header("analysis/coherence/adr027.py")
    out["n_files"] = dd.n_files
    t1 = np.array(dd.v("q.T1"), dtype=np.float64)
    t2 = np.array(dd.v("q.T2"), dtype=np.float64)
    f1 = np.isfinite(t1)
    f2 = np.isfinite(t2)
    rej_t1 = ~f1
    rej_t2 = f1 & ~f2
    nonpos = f1 & f2 & ((t1 <= 0) | (t2 <= 0))
    rej_ratio = f1 & f2 & ~nonpos & (t2 > 2 * t1)
    usable = f1 & f2 & ~nonpos & ~rej_ratio
    with np.errstate(invalid="ignore"):
        gam = np.where(usable, cohlib.adr027_gamma(t1), np.nan)
        lam = np.where(usable, cohlib.adr027_lambda(t1, t2), np.nan)
    prev = np.vstack([np.full((1, t1.shape[1]), np.nan), t1[:-1]])
    prev2 = np.vstack([np.full((1, t2.shape[1]), np.nan), t2[:-1]])
    same = (np.nan_to_num(t1, nan=-1) == np.nan_to_num(prev, nan=-1)).all(axis=1) & (
        np.nan_to_num(t2, nan=-1) == np.nan_to_num(prev2, nan=-1)
    ).all(axis=1)
    distinct = ~same
    out["rejections_per_file"] = {
        "t1_missing": summarise(rej_t1.sum(axis=1).astype(float)),
        "t2_missing": summarise(rej_t2.sum(axis=1).astype(float)),
        "nonpositive": int(nonpos.sum()),
        "t2_gt_2t1": summarise(rej_ratio.sum(axis=1).astype(float)),
        "files_with_any_t2_gt_2t1": int(np.sum(rej_ratio.any(axis=1))),
        "usable": summarise(usable.sum(axis=1).astype(float)),
        "quantile_levels": [0.0, 0.1, 0.5, 0.9, 1.0],
        "distinct_coherence_states": int(distinct.sum()),
    }

    def block(v: np.ndarray, rows: np.ndarray) -> dict[str, Any]:
        v = v[rows]
        mean = np.nanmean(v, axis=1)
        med = np.nanmedian(v, axis=1)
        srt = -np.sort(-np.nan_to_num(v, nan=-np.inf), axis=1)
        n_use = np.sum(np.isfinite(v), axis=1)
        tot = np.nansum(v, axis=1)
        top5 = np.array(
            [srt[i, : max(1, round(0.05 * n_use[i]))].sum() / tot[i] for i in range(v.shape[0])]
        )
        top10 = np.array(
            [srt[i, : max(1, round(0.10 * n_use[i]))].sum() / tot[i] for i in range(v.shape[0])]
        )
        top1 = srt[:, 0] / tot
        lm, lmed = np.log10(mean), np.log10(med)
        return {
            "rows": int(v.shape[0]),
            "snapshot_mean_quantiles": summarise(mean),
            "snapshot_median_quantiles": summarise(med),
            "mean_over_median_quantiles": summarise(mean / med),
            "share_of_sum_top_1_qubit_quantiles": summarise(top1),
            "share_of_sum_top_5pct_quantiles": summarise(top5),
            "share_of_sum_top_10pct_quantiles": summarise(top10),
            "uniform_share_top_10pct": cohlib.r(0.10),
            "sd_log10_snapshot_mean_across_rows": cohlib.r(np.std(lm, ddof=1)),
            "sd_log10_snapshot_median_across_rows": cohlib.r(np.std(lmed, ddof=1)),
            "spearman_mean_vs_max_qubit": cohlib.r(stats.spearmanr(mean, srt[:, 0]).statistic),
        }

    out["gamma"] = {
        "all_files": block(gam, np.ones(dd.n_files, dtype=bool)),
        "distinct_states": block(gam, distinct),
    }
    out["lambda"] = {
        "all_files": block(lam, np.ones(dd.n_files, dtype=bool)),
        "distinct_states": block(lam, distinct),
    }
    # How close lambda's per-qubit rows come to ADR-027's T2 = 2 T1 boundary.
    s = (t2 / (2 * t1))[usable]
    out["lambda_boundary"] = {
        "usable_records": int(usable.sum()),
        "share_s_above_0.9": cohlib.r(np.mean(s > 0.9)),
        "share_s_above_0.75": cohlib.r(np.mean(s > 0.75)),
    }
    cohlib.write("adr027.json", out)


if __name__ == "__main__":
    main()
