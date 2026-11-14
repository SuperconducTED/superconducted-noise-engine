"""Reproduce the Issue #60 premise-stage evidence on the planted 3x3x3 grid.

Two measurements, both on synthetic data from a planted rule base (no archive):

``recovery``
    Fit ``HybridANFISTrainer`` from a perturbed premise for a fixed number of
    epochs at one or more premise learning rates, and record the training loss,
    the distance to the planted premise and the held-out error.
``hessian``
    Eigenvalues of the Hessian of the re-solved training loss at the planted
    premise, which say how fast plain gradient descent can recover it.

Run from the repository root at the commit named in this folder's README::

    python docs/evidence/anfis-premise-stage/reproduce.py recovery t1 \
        --epochs 40 --premise-lr 100 1000 10000
    python docs/evidence/anfis-premise-stage/reproduce.py hessian t1

Each command writes TSV files next to this script. The planted grid is the
M2 test fixture's (``tests/test_anfis.py::_planted_grid``): three centres per
input spanning the NC-041 [p1, p99] box in archive units (microseconds for T1
and T2, dimensionless readout error), consequents drawn from
``uniform(0.05, 0.2)`` with seed 7. The script uses private trainer helpers, as
the tests do, so it is pinned to the commit it was run at.
"""

from __future__ import annotations

import argparse
import csv
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt

from superconducted.fuzzy.defuzzification import NieTanDefuzzifier, WeightedAverageDefuzzifier
from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.interfaces import MembershipFunction
from superconducted.training import HybridANFISTrainer, TrainingSet
from superconducted.training.anfis import (
    _ConsequentSolver,
    _log_space_mask,
    _predict,
    _standardization,
    _to_search,
    _to_standardized_rule_base,
)
from superconducted.training.parameters import premise_layout

HERE = Path(__file__).resolve().parent
Array = npt.NDArray[np.float64]

# NC-041 [p1, p99] box, archive units; three evenly spaced centres per input.
CENTERS = (
    np.array([98.8, 126.6, 154.4]),
    np.array([67.4, 88.95, 110.5]),
    np.array([0.0171, 0.02725, 0.0374]),
)
WIDTHS = (20.0, 16.0, 0.012)  # the M2 fixture's widths; IT2 lower width is 0.65 of these
CENTER_SHIFT = np.array([0.12, -0.10, 0.08])  # warm start: fraction of the centre spacing
WIDTH_FACTOR = np.array([1.20, 0.85, 1.15])  # warm start: width factors
TRAIN_POINTS = 8  # 8x8x8 training lattice over the box (the M2 fixture's 512 rows)
HELD_OUT_POINTS = 7  # interior of a 7x7x7 lattice, interleaved with the training one


def grid(
    interval: bool, centers: Sequence[Array], widths: Sequence[Array], seed: int
) -> TSKRuleBase:
    """A 3x3x3 Gaussian (T1) or interval Gaussian (IT2) grid with seeded consequents."""
    per_input: list[list[MembershipFunction]] = [
        [
            IntervalGaussianMF(float(c), 0.65 * float(w), float(w))
            if interval
            else GaussianMF(float(c), float(w))
            for c, w in zip(dimension_centers, dimension_widths, strict=True)
        ]
        for dimension_centers, dimension_widths in zip(centers, widths, strict=True)
    ]
    base = TSKRuleBase.from_grid(per_input, output_dim=2)
    consequents = np.random.default_rng(seed).uniform(0.05, 0.2, size=(base.n_rules, 2, 4))
    return TSKRuleBase(
        [TSKRule(rule.antecedent_mfs, consequents[i]) for i, rule in enumerate(base.rules)],
        input_dim=3,
        output_dim=2,
    )


def planted(interval: bool) -> TSKRuleBase:
    return grid(interval, CENTERS, [np.full(3, w) for w in WIDTHS], seed=7)


def warm(interval: bool) -> TSKRuleBase:
    spacing = [c[1] - c[0] for c in CENTERS]
    centers = [c + CENTER_SHIFT * s for c, s in zip(CENTERS, spacing, strict=True)]
    widths = [np.full(3, w) * WIDTH_FACTOR for w in WIDTHS]
    return grid(interval, centers, widths, seed=42)


def lattice(points: int) -> Array:
    axes = np.meshgrid(*(np.linspace(c[0], c[-1], points) for c in CENTERS), indexing="ij")
    return np.column_stack([axis.ravel() for axis in axes])


def targets(rule_base: TSKRuleBase, features: Array) -> Array:
    defuzzifier = (
        NieTanDefuzzifier() if rule_base.is_interval_type2 else WeightedAverageDefuzzifier()
    )
    return np.array([defuzzifier.defuzzify(rule_base.evaluate(row)) for row in features])


def training_set(features: Array, values: Array) -> TrainingSet:
    start = datetime(2026, 10, 18, tzinfo=UTC)
    return TrainingSet(
        features=features,
        targets=values,
        timestamps=tuple(start + timedelta(minutes=i) for i in range(features.shape[0])),
        provenance=tuple(f"row-{i}" for i in range(features.shape[0])),
        feature_names=("mean_T1", "mean_T2", "mean_readout_error"),
        target_names=("gamma", "lambda"),
        archive_ref="synthetic",
    )


def standardized_premise(rule_base: object, standardization: tuple[Array, ...]) -> Array:
    assert isinstance(rule_base, TSKRuleBase)
    return premise_layout(_to_standardized_rule_base(rule_base, *standardization)).flatten()


def write_tsv(path: Path, header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def recovery(kind: str, epochs: int, rates: Sequence[float]) -> None:
    interval = kind == "it2"
    truth_base, start_base = planted(interval), warm(interval)
    features = lattice(TRAIN_POINTS)
    data = training_set(features, targets(truth_base, features))
    held_out = lattice(HELD_OUT_POINTS)[1:-1]
    held_out_targets = targets(truth_base, held_out)
    lse_only = HybridANFISTrainer(ridge=0.0).fit(start_base, data)
    assert isinstance(lse_only.rule_base, TSKRuleBase)
    lse_error = float(np.max(np.abs(_predict(lse_only.rule_base, held_out) - held_out_targets)))
    summary: list[list[object]] = []
    history: list[list[object]] = []
    for rate in rates:
        began = time.perf_counter()
        result = HybridANFISTrainer(epochs=epochs, premise_lr=rate, ridge=0.0).fit(start_base, data)
        seconds = time.perf_counter() - began
        assert isinstance(result.rule_base, TSKRuleBase)
        standardization = result.diagnostics.standardization
        truth = standardized_premise(truth_base, standardization)
        start = standardized_premise(start_base, standardization)
        trained = standardized_premise(result.rule_base, standardization)
        error = float(np.max(np.abs(_predict(result.rule_base, held_out) - held_out_targets)))
        summary.append(
            [
                kind,
                rate,
                result.diagnostics.epochs_run,
                result.diagnostics.premise_steps_rejected,
                f"{seconds / max(1, result.diagnostics.epochs_run):.2f}",
                f"{result.loss_history[0]:.6e}",
                f"{result.loss_history[-1]:.6e}",
                f"{np.linalg.norm(start - truth):.6f}",
                f"{np.linalg.norm(trained - truth):.6f}",
                f"{np.max(np.abs(start - truth)):.6f}",
                f"{np.max(np.abs(trained - truth)):.6f}",
                f"{lse_error:.6e}",
                f"{error:.6e}",
                f"{np.max(np.abs(held_out_targets)):.6e}",
            ]
        )
        history.extend(
            [kind, rate, epoch, f"{loss:.9e}"] for epoch, loss in enumerate(result.loss_history)
        )
        print("\t".join(str(value) for value in summary[-1]), flush=True)
    write_tsv(
        HERE / f"recovery-{kind}.tsv",
        [
            "type",
            "premise_lr",
            "epochs_run",
            "premise_steps_rejected",
            "seconds_per_epoch",
            "loss_initial",
            "loss_final",
            "premise_l2_error_start",
            "premise_l2_error_end",
            "premise_max_error_start",
            "premise_max_error_end",
            "held_out_max_error_lse_only",
            "held_out_max_error_trained",
            "held_out_max_abs_target",
        ],
        summary,
    )
    write_tsv(
        HERE / f"loss-history-{kind}.tsv",
        ["type", "premise_lr", "epoch", "standardized_loss"],
        history,
    )


def hessian(kind: str, step: float) -> None:
    interval = kind == "it2"
    truth_base = planted(interval)
    features = lattice(TRAIN_POINTS)
    values = targets(truth_base, features)
    feature_mean, feature_scale = _standardization(features)
    target_mean, target_scale = _standardization(values)
    standardized = _to_standardized_rule_base(
        truth_base, feature_mean, feature_scale, target_mean, target_scale
    )
    layout = premise_layout(standardized)
    log_mask = _log_space_mask(layout)
    solve = _ConsequentSolver(
        standardized,
        layout,
        (features - feature_mean) / feature_scale,
        (values - target_mean) / target_scale,
        None,
        0.0,
    )
    premise = layout.flatten()
    origin = _to_search(premise, log_mask)

    def resolved_loss(search: Array) -> float:
        candidate = search.copy()
        candidate[log_mask] = np.exp(search[log_mask])
        solved = solve(candidate)
        assert solved is not None
        return solved[1] / features.shape[0]

    size = origin.size
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(i, size):
            e_i = np.zeros(size)
            e_j = np.zeros(size)
            e_i[i] = step
            e_j[j] = step
            matrix[i, j] = matrix[j, i] = (
                resolved_loss(origin + e_i + e_j)
                - resolved_loss(origin + e_i - e_j)
                - resolved_loss(origin - e_i + e_j)
                + resolved_loss(origin - e_i - e_j)
            ) / (4.0 * step * step)
    eigenvalues = np.linalg.eigvalsh(matrix)
    write_tsv(
        HERE / f"hessian-{kind}.tsv",
        ["type", "index", "eigenvalue", "loss_at_planted", "difference_step"],
        [
            [kind, index, f"{value:.6e}", f"{resolved_loss(origin):.3e}", step]
            for index, value in enumerate(eigenvalues)
        ],
    )
    print(kind, "eigenvalues", np.array2string(eigenvalues, precision=3), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("measurement", choices=("recovery", "hessian"))
    parser.add_argument("kind", choices=("t1", "it2"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--premise-lr", type=float, nargs="+", default=[100.0, 1000.0, 10000.0])
    parser.add_argument("--step", type=float, default=1e-3, help="Hessian difference step")
    arguments = parser.parse_args()
    if arguments.measurement == "recovery":
        recovery(arguments.kind, arguments.epochs, arguments.premise_lr)
    else:
        hessian(arguments.kind, arguments.step)


if __name__ == "__main__":
    main()
