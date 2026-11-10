"""Survey source-tagged state rows, then fit with/without public rows on one holdout.

This is a provisional calibration-target fit, not hardware validation or an
ADR-009 winner selection. All quantile grids are measured on training rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.parameterization import grid_partition
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.training.anfis import HybridANFISTrainer
from superconducted.training.public_archive import PUBLIC_REVISION, PUBLIC_SHA256, PUBLIC_SOURCE
from superconducted.types import TrainingSet

FEATURES = ("mean_T1", "mean_T2", "mean_readout_error")
TARGETS = ("gamma", "lambda")


def _data(rows: list[dict[str, str]]) -> TrainingSet:
    refs = sorted({row["source_revision"] for row in rows})
    return TrainingSet(
        features=np.array([[float(row[name]) for name in FEATURES] for row in rows]),
        targets=np.array([[float(row[name]) for name in TARGETS] for row in rows]),
        timestamps=tuple(datetime.fromisoformat(row["last_update_date"]) for row in rows),
        provenance=tuple(row["qubit_digest"] for row in rows),
        feature_names=FEATURES,
        target_names=TARGETS,
        archive_ref=";".join(refs),
    )


def survey(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Source-tagged p1/p50/p99, equal mass per kept distinct state, linear method."""
    result = []
    for source in ("calibration-data", PUBLIC_SOURCE, "combined"):
        selected = [r for r in rows if source == "combined" or r["source"] == source]
        if not selected:
            continue
        values = _data(selected).features
        for index, name in enumerate(FEATURES):
            quantiles = np.quantile(values[:, index], (0.01, 0.5, 0.99), method="linear")
            result.append(
                dict(
                    source=source,
                    feature=name,
                    n=len(selected),
                    p1=float(quantiles[0]),
                    p50=float(quantiles[1]),
                    p99=float(quantiles[2]),
                )
            )
    return result


def compare(rows: list[dict[str, str]], cut: datetime) -> list[dict[str, Any]]:
    """Both fits score the same IBM-only chronological holdout, never public rows."""
    if cut.tzinfo is None:
        raise ValueError("cut must be timezone aware")
    for row in rows:
        if row["source"] not in ("calibration-data", PUBLIC_SOURCE):
            raise ValueError(f"Unknown source: {row['source']!r}")
        if row["source"] == PUBLIC_SOURCE and (
            row["source_revision"] != PUBLIC_REVISION or row["source_sha256"] != PUBLIC_SHA256
        ):
            raise ValueError("Public provenance does not match ADR-029's pin")
        if (
            row["source"] == PUBLIC_SOURCE
            and datetime.fromisoformat(row["last_update_date"]) >= cut
        ):
            raise ValueError("Public rows must precede the holdout")
    validation_rows = [
        r
        for r in rows
        if r["source"] == "calibration-data"
        and datetime.fromisoformat(r["last_update_date"]) >= cut
    ]
    if not validation_rows:
        raise ValueError("cut leaves no IBM holdout")
    validation = _data(validation_rows)
    result = []
    for label, include_public in (("IBM only", False), ("IBM + public", True)):
        selected = [
            r
            for r in rows
            if datetime.fromisoformat(r["last_update_date"]) < cut
            and (include_public or r["source"] == "calibration-data")
        ]
        if not selected:
            raise ValueError("cut leaves no training rows")
        data = _data(selected)
        # Each fit gets a grid derived from its own training distribution.
        mfs = [grid_partition(GaussianMF, data.features[:, i]) for i in range(3)]
        model = TSKRuleBase.from_grid(mfs, output_dim=2)
        # A constant training-target mean is a deterministic viable warm start;
        # an all-zero model is identity damping and the trainer rejects it.
        for rule in model.rules:
            rule.consequent_params[:, -1] = data.targets.mean(axis=0)
        fit = HybridANFISTrainer(epochs=0, ridge=1e-6, seed=0, validation=validation).fit(
            model, data
        )
        if fit.validation_rmse is None:
            raise RuntimeError("Missing validation metrics")
        result.append(
            dict(
                fit=label,
                n_train=data.n_rows,
                n_validation=validation.n_rows,
                train_rmse=fit.train_rmse.tolist(),
                validation_rmse=fit.validation_rmse.tolist(),
                parameters=asdict(fit.parameter_count),
                diagnostics=asdict(fit.diagnostics),
            )
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-tsv", required=True, type=Path)
    parser.add_argument("--cut", required=True, help="Aware ISO timestamp; fixed IBM-only holdout")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    with args.training_tsv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    args.out.mkdir(parents=True, exist_ok=True)
    # Emit the quantile survey before any fit, as issue #122 requires.
    quantiles = survey(rows)
    with (args.out / "source-quantiles.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["source", "feature", "n", "p1", "p50", "p99"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(quantiles)
    results = compare(rows, datetime.fromisoformat(args.cut.replace("Z", "+00:00")))
    record = dict(
        input=args.training_tsv.as_posix(),
        input_sha256=hashlib.sha256(args.training_tsv.read_bytes()).hexdigest(),
        cut=args.cut,
        quantile_weighting="one row per distinct kept state",
        quantile_method="linear",
        shape="GaussianMF",
        levels=3,
        epochs=0,
        ridge=1e-6,
        seed=0,
        results=results,
    )
    (args.out / "fit-comparison.json").write_text(
        json.dumps(record, indent=2, default=lambda value: value.tolist()) + "\n",
        encoding="utf-8",
    )
    table = [
        "# Source comparison (provisional)",
        "",
        "Derived calibration targets only; this does not measure hardware transferability.",
        "Both fits score the same IBM-only chronological holdout. Each fit's Gaussian grid",
        "is re-derived from its training rows; no holdout data sets membership parameters.",
        "The comparison therefore changes both the training source and its grid.",
        "",
        f"Input TSV SHA-256: `{record['input_sha256']}`. Cut: `{args.cut}`.",
        "",
        "| Fit | Training states | Holdout states | Gamma RMSE | Lambda RMSE |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        table.append(
            f"| {r['fit']} | {r['n_train']} | {r['n_validation']} | "
            f"{r['validation_rmse'][0]:.10g} | {r['validation_rmse'][1]:.10g} |"
        )
    table += [
        "",
        "The source-tagged survey is source-quantiles.tsv; its unit is a distinct kept",
        "state, whereas NC-041 was file-weighted. It supersedes no dated NC-041 evidence.",
        "",
        "Public data: Charles C. Norton, phanerozoic/qiskit-calibration-drift, CC-BY-4.0.",
        "SN was never loaded. Neither party has checked IBM's redistribution terms for",
        "backend.properties() output. This machine's results await the canonical desktop batch.",
        "",
    ]
    (args.out / "results.md").write_text("\n".join(table), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
