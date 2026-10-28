"""Task N3 of the pattern detector: permutation importance of the logistic bar, Brier and AUC apart.

Implements README section 4's pattern extraction under amendment 7: the record logistic model is
refitted from the committed ``features.tsv.gz`` and checked against the recorded forecasts; each
feature group's test-row values are permuted jointly; Brier importance and AUC importance are
ranked separately with paired day-block bootstrap intervals; the top three groups by Brier
importance define the scenario cells. No network, no new data.

    PYTHONPATH=src;. python docs/evidence/pattern-detector/n3_importance.py \
        --features docs/evidence/pattern-detector/features.tsv.gz \
        --summary docs/evidence/pattern-detector/summary.json --out docs/evidence/pattern-detector

Outputs: ``importance.tsv``, ``cells.tsv``, ``n3_summary.json``.
"""

# ruff: noqa: N803, N806  (matrix notation: X is the standard symbol)
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import sys
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


n1 = _load("n1_baselines")
n1a = _load("n1_amended")

PERMUTATIONS = 20
BOOTSTRAP = 1000
SEED_PERM = 86
SEED_BOOT = 87
MIN_CELL_ROWS = 20
TOP_GROUPS = 3
GUARD_TOLERANCE = 1e-5  # features.tsv.gz holds six significant digits (amendment 7 note 8)
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("d", ("d",)),
    ("abs_d_rel", ("abs_d_rel",)),
    ("prev_d", ("prev_d", "prev_d_missing")),
    ("n_distinct", ("n_distinct",)),
    ("hours_since_prev", ("hours_since_prev",)),
    ("hours_since_sweep", ("hours_since_sweep",)),
    ("d_t2", ("d_t2", "d_t2_missing")),
    ("d_readout", ("d_readout", "d_readout_missing")),
    ("chip_readout", ("chip_readout",)),
    ("same_sign_share", ("same_sign_share",)),
    ("sx_log", ("sx_log",)),
    ("cz_best_log", ("cz_best_log",)),
    ("hour", ("hour_sin", "hour_cos")),
)


def _day(stamp: str) -> str:
    return datetime.fromisoformat(stamp).astimezone(UTC).date().isoformat()


def load_features(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter="\t") if r["split"] in ("train", "test")]
    cols = list(n1.COLUMNS)
    X = np.array([[float(r[c]) for c in cols] for r in rows])
    return {
        "X": X,
        "y": np.array([float(r["y"]) for r in rows]),
        "train": np.array([r["split"] == "train" for r in rows]),
        "days": np.array([_day(r["time"]) for r in rows]),
        "p_logistic": np.array([float(r["p_logistic"]) for r in rows]),
        "p_null": np.array([float(r["p_null_empirical"]) for r in rows]),
        "cols": cols,
    }


def refit(data: dict[str, Any], lam: float) -> tuple[Any, list[int], np.ndarray, np.ndarray]:
    X, train = data["X"], data["train"]
    keep = [j for j in range(X.shape[1]) if np.std(X[train, j]) > 0]
    Xk = X[:, keep]
    mean, std = Xk[train].mean(axis=0), Xk[train].std(axis=0)
    beta = n1.fit_logistic(n1.standardise(Xk[train], mean, std), data["y"][train], lam)
    return beta, keep, mean, std


def predict(
    data: dict[str, Any],
    X: np.ndarray,
    beta: np.ndarray,
    keep: list[int],
    mean: np.ndarray,
    std: np.ndarray,
) -> np.ndarray:
    return n1.predict_logistic(n1.standardise(X[:, keep], mean, std), beta)


def permutation_predictions(
    data: dict[str, Any],
    beta: np.ndarray,
    keep: list[int],
    mean: np.ndarray,
    std: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """For each group: (PERMUTATIONS, n_test) predictions with the group's test columns permuted."""
    test = ~data["train"]
    Xt = data["X"][test]
    n = Xt.shape[0]
    out: dict[str, np.ndarray] = {}
    col_idx = {c: i for i, c in enumerate(data["cols"])}
    for name, members in GROUPS:
        js = [col_idx[m] for m in members if col_idx[m] in keep]
        if not js:
            continue
        preds = np.empty((PERMUTATIONS, n))
        for k in range(PERMUTATIONS):
            perm = rng.permutation(n)
            Xp = Xt.copy()
            Xp[:, js] = Xt[perm][:, js]
            preds[k] = predict(data, Xp, beta, keep, mean, std)
        out[name] = preds
    return out


def importances(
    y: np.ndarray,
    p_rec: np.ndarray,
    perm_preds: dict[str, np.ndarray],
    idx: np.ndarray | None = None,
) -> dict[str, tuple[float, float]]:
    if idx is None:
        idx = np.arange(y.size)
    bs_rec = n1.brier(p_rec[idx], y[idx])
    auc_rec = n1.auc(p_rec[idx], y[idx])
    out = {}
    for name, preds in perm_preds.items():
        bs = np.mean([n1.brier(preds[k][idx], y[idx]) for k in range(preds.shape[0])])
        au = np.mean([n1.auc(preds[k][idx], y[idx]) for k in range(preds.shape[0])])
        out[name] = (float(bs - bs_rec), float(auc_rec - au))
    return out


def bootstrap_importances(
    y: np.ndarray,
    p_rec: np.ndarray,
    perm_preds: dict[str, np.ndarray],
    days: np.ndarray,
    rng: np.random.Generator,
    block: int = 1,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Amendment 9: circular blocks of `block` consecutive calendar days (block 1 = single days)."""
    axis = n1a.calendar_axis(days)
    pos = {d: i for i, d in enumerate(axis)}
    groups = {i: np.where(days == d)[0] for d, i in pos.items()}
    n = len(axis)
    acc: dict[str, list[list[float]]] = {name: [[], []] for name in perm_preds}
    for _ in range(BOOTSTRAP):
        drawn: list[int] = []
        while len(drawn) < n:
            start = int(rng.integers(0, n))
            drawn.extend((start + j) % n for j in range(block))
        idx = np.concatenate([groups[i] for i in drawn[:n]])
        imp = importances(y, p_rec, perm_preds, idx)
        for name, (b, a) in imp.items():
            acc[name][0].append(b)
            acc[name][1].append(a)
    return {
        name: {"brier_90": n1.interval(np.array(v[0])), "auc_90": n1.interval(np.array(v[1]))}
        for name, v in acc.items()
    }


def scenario_cells(data: dict[str, Any], top: list[str], p_log: np.ndarray) -> list[dict[str, Any]]:
    X, y, train = data["X"], data["y"], data["train"]
    col_idx = {c: i for i, c in enumerate(data["cols"])}
    members = dict(GROUPS)
    feats = [col_idx[members[g][0]] for g in top]  # a multi-column group is cut on its first column
    edges = [np.quantile(X[train, j], [1 / 3, 2 / 3]) for j in feats]
    code = np.zeros((X.shape[0], len(feats)), dtype=int)
    for k, j in enumerate(feats):
        code[:, k] = np.searchsorted(edges[k], X[:, j], side="right")
    cells = []
    for c0 in range(3):
        for c1 in range(3):
            for c2 in range(3):
                m = (code[:, 0] == c0) & (code[:, 1] == c1) & (code[:, 2] == c2)
                mt, ms = m & train, m & ~train
                cells.append(
                    {
                        top[0]: ("low", "mid", "high")[c0],
                        top[1]: ("low", "mid", "high")[c1],
                        top[2]: ("low", "mid", "high")[c2],
                        "train_rows": int(mt.sum()),
                        "train_rate": float(y[mt].mean()) if mt.any() else float("nan"),
                        "test_rows": int(ms.sum()),
                        "test_rate": float(y[ms].mean()) if ms.any() else float("nan"),
                        "test_logistic_mean": float(p_log[ms].mean()) if ms.any() else float("nan"),
                        "test_null_mean": float(data["p_null"][ms].mean())
                        if ms.any()
                        else float("nan"),
                        "readable": bool(mt.sum() >= MIN_CELL_ROWS and ms.sum() >= MIN_CELL_ROWS),
                    }
                )
    return cells


def run(features: Path, summary_path: Path, out: Path) -> dict[str, Any]:
    data = load_features(features)
    rec = json.loads(summary_path.read_text(encoding="utf-8"))
    lam = float(rec["logistic"]["lambda"])
    beta, keep, mean, std = refit(data, lam)
    p_fit = predict(data, data["X"], beta, keep, mean, std)
    max_dev = float(np.max(np.abs(p_fit - data["p_logistic"])))
    if max_dev > GUARD_TOLERANCE:
        raise SystemExit(
            f"reproduction guard: refitted forecasts deviate from the record by {max_dev}"
        )
    test = ~data["train"]
    y_t, p_t, days_t = data["y"][test], data["p_logistic"][test], data["days"][test]
    perm_preds = permutation_predictions(
        data, beta, keep, mean, std, np.random.default_rng(np.random.SeedSequence(SEED_PERM))
    )
    point = importances(y_t, p_t, perm_preds)
    block = int(rec.get("bootstrap", {}).get("block_length_chosen_calendar_days", 1))
    boots = bootstrap_importances(
        y_t,
        p_t,
        perm_preds,
        days_t,
        np.random.default_rng(np.random.SeedSequence(SEED_BOOT)),
        block,
    )
    table = []
    for name, (b, a) in point.items():
        table.append({"group": name, "brier_importance": b, "auc_importance": a, **boots[name]})
    by_brier = sorted(table, key=lambda r: -r["brier_importance"])
    by_auc = sorted(table, key=lambda r: -r["auc_importance"])
    for rank, r in enumerate(by_brier, 1):
        r["rank_brier"] = rank
    for rank, r in enumerate(by_auc, 1):
        r["rank_auc"] = rank
    top = [r["group"] for r in by_brier[:TOP_GROUPS]]
    cells = scenario_cells(data, top, data["p_logistic"])
    summary = {
        "features": str(features),
        "lambda": lam,
        "guard_max_deviation": max_dev,
        "test_rows": int(test.sum()),
        "record_brier": n1.brier(p_t, y_t),
        "record_auc": n1.auc(p_t, y_t),
        "permutations": PERMUTATIONS,
        "bootstrap": BOOTSTRAP,
        "bootstrap_block_calendar_days": block,
        "groups": table,
        "top_by_brier": top,
        "top_by_auc": [r["group"] for r in by_auc[:TOP_GROUPS]],
        "cells_readable": sum(1 for c in cells if c["readable"]),
    }
    out.mkdir(parents=True, exist_ok=True)
    with (out / "importance.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "group",
                "rank_brier",
                "brier_importance",
                "brier_90_lo",
                "brier_90_hi",
                "rank_auc",
                "auc_importance",
                "auc_90_lo",
                "auc_90_hi",
            ]
        )
        for r in by_brier:
            w.writerow(
                [
                    r["group"],
                    r["rank_brier"],
                    f"{r['brier_importance']:.5f}",
                    f"{r['brier_90'][0]:.5f}",
                    f"{r['brier_90'][1]:.5f}",
                    r["rank_auc"],
                    f"{r['auc_importance']:.4f}",
                    f"{r['auc_90'][0]:.4f}",
                    f"{r['auc_90'][1]:.4f}",
                ]
            )
    with (out / "cells.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(cells[0].keys()), delimiter="\t", lineterminator="\n"
        )
        w.writeheader()
        for c in cells:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in c.items()})
    (out / "n3_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def selftest() -> None:
    rng = np.random.default_rng(3)
    n = 4000
    X = rng.normal(size=(n, len(n1.COLUMNS)))
    X[:, n1.COLUMNS.index("prev_d_missing")] = (rng.uniform(size=n) < 0.2).astype(float)
    X[:, n1.COLUMNS.index("d_t2_missing")] = (rng.uniform(size=n) < 0.2).astype(float)
    X[:, n1.COLUMNS.index("d_readout_missing")] = 0.0
    j_d, j_n = n1.COLUMNS.index("d"), n1.COLUMNS.index("n_distinct")
    logit = 1.5 * X[:, j_d] - 1.0 * X[:, j_n] - 0.5
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(float)
    train = np.arange(n) < n // 2
    data = {
        "X": X,
        "y": y,
        "train": train,
        "days": np.array([f"d{i % 40}" for i in range(n)]),
        "cols": list(n1.COLUMNS),
        "p_null": np.full(n, y[train].mean()),
    }
    beta, keep, mean, std = refit(data, 0.01)
    data["p_logistic"] = predict(data, X, beta, keep, mean, std)
    test = ~train
    perm = permutation_predictions(data, beta, keep, mean, std, rng)
    imp = importances(y[test], data["p_logistic"][test], perm)
    ranked = sorted(imp, key=lambda k: -imp[k][0])
    assert ranked[:2] == ["d", "n_distinct"], ranked[:4]
    assert imp["d"][1] > 0.05 and imp["n_distinct"][1] > 0.02, (imp["d"], imp["n_distinct"])
    assert abs(imp["sx_log"][0]) < 0.003 and abs(imp["sx_log"][1]) < 0.01
    cells = scenario_cells(data, ranked[:3], data["p_logistic"])
    assert len(cells) == 27 and sum(c["train_rows"] for c in cells) == int(train.sum())
    print(f"selftest ok: ranking {ranked[:3]} d=({imp['d'][0]:.4f}, {imp['d'][1]:.3f})")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--features", type=Path, default=HERE / "features.tsv.gz")
    ap.add_argument("--summary", type=Path, default=HERE / "summary.json")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.out:
        ap.error("--out is required")
    summary = run(args.features, args.summary, args.out)
    keys = ("guard_max_deviation", "record_brier", "record_auc", "top_by_brier", "top_by_auc")
    print(json.dumps({k: summary[k] for k in keys}, indent=2))
    for r in sorted(summary["groups"], key=lambda r: r["rank_brier"]):
        b_lo, b_hi = r["brier_90"]
        a_lo, a_hi = r["auc_90"]
        print(
            f"  {r['group']:18s} brier {r['brier_importance']:+.5f} [{b_lo:+.5f}, {b_hi:+.5f}]"
            f"  auc {r['auc_importance']:+.4f} [{a_lo:+.4f}, {a_hi:+.4f}]  rank_auc {r['rank_auc']}"
        )


if __name__ == "__main__":
    main()
