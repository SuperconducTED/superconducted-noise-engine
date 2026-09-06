"""Value-contract tests for supervised training data and results."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from superconducted.training import ParameterCount, TrainingSet


def test_training_set_copies_and_freezes_arrays() -> None:
    features = np.array([[1.0], [2.0]])
    targets = np.array([[0.1], [0.2]])
    data = TrainingSet(features, targets)
    features[0, 0] = 99.0
    assert data.features[0, 0] == 1.0
    with pytest.raises(ValueError):
        data.targets[0, 0] = 1.0


def test_training_set_normalizes_timestamps_and_preserves_metadata_on_split() -> None:
    cut = datetime(2026, 9, 5, 12, tzinfo=UTC)
    data = TrainingSet(
        np.array([[1.0], [2.0], [3.0]]),
        np.array([[0.1], [0.2], [0.3]]),
        timestamps=(cut - timedelta(seconds=1), cut, cut),
        provenance=("a", "b", "c"),
        feature_names=("mean_T1",),
        target_names=("gamma",),
        archive_ref="origin/calibration-data",
    )
    train, validation = data.time_split(cut)
    assert train.n_rows == 1
    assert validation.n_rows == 2
    assert validation.provenance == ("b", "c")
    assert validation.archive_ref == "origin/calibration-data"


def test_training_set_rejects_naive_split_cut_and_empty_archive_reference() -> None:
    data = TrainingSet(
        np.array([[1.0], [2.0]]),
        np.array([[0.1], [0.2]]),
        timestamps=(datetime(2026, 9, 4, tzinfo=UTC), datetime(2026, 9, 5, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="tz-aware"):
        data.time_split(datetime(2026, 9, 5))
    with pytest.raises(ValueError, match="archive_ref"):
        TrainingSet(np.array([[1.0]]), np.array([[0.1]]), archive_ref="")


def test_parameter_count_requires_a_consistent_total() -> None:
    with pytest.raises(ValueError, match="total"):
        ParameterCount(premise=1, consequent=2, total=2)
