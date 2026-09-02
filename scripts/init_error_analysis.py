"""Reproduce NC-027 and NC-028 from the calibration archive at a pinned commit.

Two questions about ``init_error``, the per-qubit field IBM started publishing
on 2026-08-04 (#45 §6b), answered on one sample:

- **NC-027** Is the field complete *per qubit* after the cutover? (No: a fixed
  set of qubits never reports it, so "restrict training to August" would not
  have bought completeness.)
- **NC-028** Can pre-cutover values be recovered by regressing ``init_error``
  on the six fields that *are* co-observed? (No: the relation does not survive
  a 20-day time split inside the observed regime, so extrapolating it 25 to
  110 days backwards across a schema change is unfounded. This is what
  eliminated imputation; see ADR-017 and the 2026-08-29 implementation doc.)

Sample selection — the rule both claims depend on
-------------------------------------------------

    files  = snapshots/<month>/<backend>/*.json at <ref>, stem >= cutover,
             sorted by stem
    sample = files[:: max(1, len(files) // 40)][:40]

Every k-th post-cutover snapshot, with k chosen so that 40 are spread across
the whole span rather than taken as a contiguous block. At ``f0930b9`` there
are 225 such files, so k = 5 and the sample runs 2026-08-04T00:52:30 →
2026-08-24. **Any later archive commit changes len(files), hence k, hence the
sample**, which is why the ref is pinned and printed rather than defaulting
to the branch tip.

Time split (NC-028): the 40 sampled snapshots are cut in half by *snapshot*
— the first 20 train, the last 20 test — which at ``f0930b9`` is "train
08-04→08-19, test 08-19→08-24" (n = 2300 / 2307 qubit-records). This is the
figure NC-028 records, and the one PR #50's reviewer reproduced independently
(-0.584865). It cannot be moved by the order of rows within a snapshot.

The original scratchpad cut by *row count* (``len(rows) // 2``) instead. At
``f0930b9`` that cut falls inside the 2026-08-19T12:45:23 snapshot (3 of its
115 rows train, 112 test), so the result depends on how that snapshot's rows
happen to be ordered: ``np.argsort`` on tied stamps (unstable) gave -0.585,
snapshot order with qubit index ascending gives -0.586, and 200 random
orderings of that one snapshot span -0.61 to -0.58. The script still prints
this variant for continuity. Both splits are strongly negative; the
conclusion does not depend on where the cut lands.

Reads the archive through ``git show``, so it needs no checkout of the 1.3 GB
data branch — only that ``--ref`` is reachable in ``--repo`` (fetch
``calibration-data`` first). Read-only; ``numpy`` is the only dependency.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

DEFAULT_REF = "f0930b9"
DEFAULT_CUTOVER = "20260804T005230"
SAMPLE_SIZE = 40
PREDICTORS: tuple[str, ...] = (
    "prob_meas0_prep1",
    "prob_meas1_prep0",
    "readout_error",
    "readout_length",
    "T1",
    "T2",
)

Matrix = NDArray[np.float64]


def select_sample(items: Sequence[str], size: int = SAMPLE_SIZE) -> list[str]:
    """Every k-th item of the sorted sequence, k = max(1, len // size), at most ``size``."""
    ordered = sorted(items)
    step = max(1, len(ordered) // size)
    return ordered[::step][:size]


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def list_snapshots(repo: Path, ref: str, prefix: str) -> list[str]:
    """Paths of ``*.json`` under ``prefix`` at ``ref``, sorted (stem order within one dir)."""
    out = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", prefix).decode("utf-8")
    return sorted(line for line in out.splitlines() if line.endswith(".json"))


def read_snapshot(repo: Path, ref: str, path: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(_git(repo, "show", f"{ref}:{path}").decode("utf-8"))
    return doc


def qubit_rows(
    docs: Iterable[tuple[str, dict[str, Any]]],
) -> tuple[list[str], Matrix, Matrix, int]:
    """Flatten snapshots into qubit-records that carry ``init_error`` and every predictor.

    Returns ``(stems, X, y, n_without_init_error)``. Records are emitted in
    snapshot order, qubit index ascending, which is the order the time split
    relies on. A qubit missing any predictor (qubit 72 lacks ``T2``) is dropped
    silently, as in the original analysis.
    """
    stems: list[str] = []
    xs: list[list[float]] = []
    ys: list[float] = []
    without = 0
    for stem, doc in docs:
        for qubit in doc["properties"]["qubits"]:
            vals = {entry["name"]: entry["value"] for entry in qubit}
            if "init_error" not in vals:
                without += 1
                continue
            if any(name not in vals for name in PREDICTORS):
                continue
            stems.append(stem)
            ys.append(float(vals["init_error"]))
            xs.append([float(vals[name]) for name in PREDICTORS])
    return stems, np.array(xs, dtype=np.float64), np.array(ys, dtype=np.float64), without


def ols_r2(x_train: Matrix, y_train: Matrix, x_test: Matrix, y_test: Matrix) -> float:
    """Fit OLS with intercept on the training pair; return R² scored on the test pair.

    R² = 1 - Σ(y - ŷ)² / Σ(y - ȳ)², with ȳ the *test* mean, so a negative value
    means the fit predicts the held-out data worse than its own mean would.
    """
    design_train = np.hstack([np.ones((len(x_train), 1)), x_train])
    beta = np.linalg.lstsq(design_train, y_train, rcond=None)[0]
    design_test = np.hstack([np.ones((len(x_test), 1)), x_test])
    resid = y_test - design_test @ beta
    centred = y_test - y_test.mean()
    return float(1.0 - (resid @ resid) / (centred @ centred))


def missingness(docs: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """NC-027: per-snapshot and per-qubit absence of ``init_error``."""
    per_snapshot: list[int] = []
    by_qubit: Counter[int] = Counter()
    complete = 0
    n_qubits = 0
    n_docs = 0
    for _, doc in docs:
        n_docs += 1
        qubits = doc["properties"]["qubits"]
        n_qubits = max(n_qubits, len(qubits))
        missing = [i for i, q in enumerate(qubits) if not any(e["name"] == "init_error" for e in q)]
        per_snapshot.append(len(missing))
        by_qubit.update(missing)
        if not missing:
            complete += 1
    ordered = sorted(per_snapshot)
    return {
        "snapshots": n_docs,
        "n_qubits": n_qubits,
        "fully_complete": complete,
        "missing_min": ordered[0] if ordered else 0,
        "missing_median": ordered[len(ordered) // 2] if ordered else 0,
        "missing_max": ordered[-1] if ordered else 0,
        "ever_missing": len(by_qubit),
        "always_missing": sum(1 for c in by_qubit.values() if c == n_docs),
        "sometimes_missing": sum(1 for c in by_qubit.values() if c < n_docs),
    }


def main(argv: Iterable[str] | None = None) -> int:
    """Select the sample at the pinned ref, then print NC-027 and NC-028."""
    parser = argparse.ArgumentParser(
        prog="init-error-analysis",
        description="Reproduce NC-027/NC-028 from the calibration archive at a pinned commit.",
    )
    parser.add_argument("--repo", default=".", help="Repository holding the archive ref.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Archive commit (default f0930b9).")
    parser.add_argument("--backend", default="ibm_fez")
    parser.add_argument("--month", default="2026-08", help="snapshots/<month>/ to sample from.")
    parser.add_argument("--cutover", default=DEFAULT_CUTOVER, help="First stem WITH init_error.")
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo = Path(args.repo)
    prefix = f"snapshots/{args.month}/{args.backend}"
    files = list_snapshots(repo, args.ref, prefix)
    post = [p for p in files if Path(p).stem >= args.cutover]
    sample = select_sample(post, args.sample_size)
    if not sample:
        print(f"no snapshots under {prefix} at {args.ref} with stem >= {args.cutover}")
        return 1
    docs = [(Path(p).stem, read_snapshot(repo, args.ref, p)) for p in sample]

    step = max(1, len(post) // args.sample_size)
    print(f"archive ref                       : {args.ref}")
    print(f"post-cutover snapshots available  : {len(post)}   (under {prefix})")
    print(f"sample rule                       : files[::{step}][:{args.sample_size}]")
    print(f"sampled snapshots                 : {len(sample)}   ({docs[0][0]} .. {docs[-1][0]})")

    print("\n--- NC-027: per-qubit completeness of init_error after the cutover ---")
    m = missingness(docs)
    complete = f"{m['fully_complete']} of {m['snapshots']}"
    print(f"snapshots where ALL {m['n_qubits']} qubits have it : {complete}")
    print(
        f"qubits missing init_error per snapshot  : min {m['missing_min']}, "
        f"median {m['missing_median']}, max {m['missing_max']}"
    )
    print(f"distinct qubits ever missing it         : {m['ever_missing']} of {m['n_qubits']}")
    print(f"  missing in EVERY sampled snapshot     : {m['always_missing']}")
    print(f"  missing only SOMETIMES                : {m['sometimes_missing']}")

    print("\n--- NC-028: is init_error recoverable by regression from co-observed fields? ---")
    stems, x, y, without = qubit_rows(docs)
    print(f"qubit-records with init_error and all predictors : {len(y)}")
    print(f"qubit-records without init_error                 : {without}")
    print(f"init_error range : {y.min():.6f} .. {y.max():.6f}   median {np.median(y):.6f}")

    print("\nmarginal Pearson r against init_error:")
    for i, name in enumerate(PREDICTORS):
        column = x[:, i]
        if column.std() == 0:
            print(f"  {name:<18} constant in the sample; contributes nothing")
            continue
        r = float(np.corrcoef(column, y)[0, 1])
        print(f"  {name:<18} r = {r:+.4f}   r^2 = {r * r:.4f}")

    print(f"\n(1) in-sample, all predictors             : R^2 = {ols_r2(x, y, x, y):.6f}")

    # NC-028's split: between sampled snapshots, first half train, second half
    # test. No ordering of rows within a snapshot can move it.
    ordered_stems = sorted(set(stems))
    first_test = ordered_stems[len(ordered_stems) // 2]
    edge = stems.index(first_test)
    print(
        f"(2) out-of-sample, cut at the snapshot boundary [NC-028] : "
        f"train {stems[0][:8]}..{stems[edge - 1][:8]} (n={edge})   "
        f"test {stems[edge][:8]}..{stems[-1][:8]} (n={len(y) - edge})"
    )
    print(f"    R^2 = {ols_r2(x[:edge], y[:edge], x[edge:], y[edge:]):.6f}")

    # The original scratchpad's row-count cut, kept for continuity. When it
    # lands inside a snapshot the figure depends on that snapshot's row order;
    # see the module docstring.
    mid = len(y) // 2
    print(
        f"(2b) same, cut at the row midpoint (original procedure)  : "
        f"train {stems[0][:8]}..{stems[mid - 1][:8]} (n={mid})   "
        f"test {stems[mid][:8]}..{stems[-1][:8]} (n={len(y) - mid})"
    )
    print(f"    R^2 = {ols_r2(x[:mid], y[:mid], x[mid:], y[mid:]):.6f}")
    if stems[mid - 1] == stems[mid]:
        print(f"    (this cut falls inside snapshot {stems[mid]}; tie-order sensitive)")

    print("\nbest single predictor, snapshot-boundary split (2):")
    for i, name in enumerate(PREDICTORS):
        xi = x[:, [i]]
        if xi.std() == 0:
            continue
        print(
            f"  {name:<18} in-sample R^2 = {ols_r2(xi, y, xi, y):.4f}   "
            f"out-of-sample R^2 = {ols_r2(xi[:edge], y[:edge], xi[edge:], y[edge:]):+.4f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
