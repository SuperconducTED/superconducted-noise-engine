"""Source ablation keeps a common IBM holdout and surveys before fitting."""

import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from scripts.compare_training_sources import FEATURES, compare, main, survey

from superconducted.training.public_archive import PUBLIC_REVISION, PUBLIC_SHA256, PUBLIC_SOURCE


def source_rows():
    rows = []
    for index in range(36):
        public = index < 6
        rows.append(
            dict(
                source=PUBLIC_SOURCE if public else "calibration-data",
                source_revision=PUBLIC_REVISION if public else "a" * 40,
                source_sha256=PUBLIC_SHA256 if public else "",
                last_update_date=(
                    datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
                ).isoformat(),
                qubit_digest=str(index),
                mean_T1=str(100 + index),
                mean_T2=str(70 + index / 2),
                mean_readout_error=str(0.01 + index / 10000),
                gamma=str(0.0001 + index / 1e7),
                **{"lambda": str(0.0002 + index / 1e7)},
            )
        )
    return rows


def test_same_ibm_holdout_and_no_holdout_in_membership_grid(monkeypatch):
    from scripts import compare_training_sources as comparison

    rows = source_rows()
    cut = datetime.fromisoformat(rows[26]["last_update_date"])
    original = comparison.grid_partition
    seen = []

    def observed_grid(shape, samples):
        seen.append(samples.copy())
        return original(shape, samples)

    monkeypatch.setattr(comparison, "grid_partition", observed_grid)
    result = compare(rows, cut)
    assert [r["n_train"] for r in result] == [20, 26]
    assert [r["n_validation"] for r in result] == [10, 10]
    for index, samples in enumerate(seen):
        feature = FEATURES[index % 3]
        expected = [float(r[feature]) for r in rows[6:26] if index < 3]
        if index >= 3:
            expected = [float(r[feature]) for r in rows[:26]]
        np.testing.assert_array_equal(samples, expected)
    assert all(np.all(np.isfinite(r["validation_rmse"])) for r in result)
    holdout = np.array([[float(row[n]) for n in ("gamma", "lambda")] for row in rows[26:]])
    for r, start in zip(result, (6, 0), strict=True):
        train = np.array([[float(row[n]) for n in ("gamma", "lambda")] for row in rows[start:26]])
        expected = np.sqrt(np.mean((holdout - train.mean(axis=0)) ** 2, axis=0))
        np.testing.assert_allclose(r["constant_validation_rmse"], expected)


def test_source_quantiles_and_cli_provenance(tmp_path):
    rows = source_rows()
    quantiles = survey(rows)
    assert len(quantiles) == 9
    assert [q["n"] for q in quantiles] == [30] * 3 + [6] * 3 + [36] * 3
    path = tmp_path / "rows.tsv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "comparison"
    assert (
        main(
            ["--training-tsv", str(path), "--cut", rows[26]["last_update_date"], "--out", str(out)]
        )
        == 0
    )
    record = json.loads((out / "fit-comparison.json").read_text())
    assert record["input_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (out / "source-quantiles.tsv").is_file()
    assert "IBM + public" in (out / "results.md").read_text()
    assert "training-mean baseline" in (out / "results.md").read_text()
    assert "not informative evidence" in (out / "results.md").read_text()


def test_source_fit_refuses_unpinned_data_and_public_holdout():
    rows = source_rows()
    with pytest.raises(ValueError, match="timezone aware"):
        compare(rows, datetime(2026, 1, 27))
    cut = datetime.fromisoformat(rows[26]["last_update_date"])
    rows[0]["source_sha256"] = "incorrect"
    with pytest.raises(ValueError, match="provenance"):
        compare(rows, cut)
    rows[0]["source_sha256"] = PUBLIC_SHA256
    rows[0]["last_update_date"] = cut.isoformat()
    with pytest.raises(ValueError, match="precede the holdout"):
        compare(rows, cut)
