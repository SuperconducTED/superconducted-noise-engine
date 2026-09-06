"""Value-contract tests for supervised training data and results."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.training import ParameterCount, TrainingDiagnostics, TrainingResult, TrainingSet
from superconducted.training.targets import QubitTargets, SkipCounts, SnapshotTarget


def _training_set(
    features: np.ndarray,
    targets: np.ndarray,
    **overrides: object,
) -> TrainingSet:
    """Build a valid archive-backed TrainingSet, with one field replaced per call."""
    n_rows, input_dim = features.shape
    fields: dict[str, object] = {
        "features": features,
        "targets": targets,
        "timestamps": tuple(datetime(2026, 9, 5, tzinfo=UTC) for _ in range(n_rows)),
        "provenance": tuple(f"snapshot-{index}" for index in range(n_rows)),
        "feature_names": tuple(f"feature-{index}" for index in range(input_dim)),
        "target_names": tuple(f"target-{index}" for index in range(targets.shape[1])),
        "archive_ref": "origin/calibration-data",
    }
    fields.update(overrides)
    return TrainingSet(**fields)  # type: ignore[arg-type]


def _diagnostics(**overrides: object) -> TrainingDiagnostics:
    fields: dict[str, object] = {
        "clip_binding_rate": 0.0,
        "zero_firing_rows_dropped": 0,
        "nonfinite_rows_rejected": 0,
        "lse_condition_number": 1.0,
        "premise_steps_rejected": 0,
        "epochs_run": 0,
        "early_stopped": False,
        "standardization": (np.zeros(1), np.ones(1)),
    }
    fields.update(overrides)
    return TrainingDiagnostics(**fields)  # type: ignore[arg-type]


def _result(**overrides: object) -> TrainingResult:
    fields: dict[str, object] = {
        "rule_base": TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1),
        "train_rmse": np.zeros(1),
        "validation_rmse": None,
        "loss_history": (),
        "diagnostics": _diagnostics(),
        "parameter_count": ParameterCount(2, 2, 4),
    }
    fields.update(overrides)
    return TrainingResult(**fields)  # type: ignore[arg-type]


def test_training_set_copies_and_freezes_arrays() -> None:
    features = np.array([[1.0], [2.0]])
    targets = np.array([[0.1], [0.2]])
    data = _training_set(features, targets)
    features[0, 0] = 99.0
    assert data.features[0, 0] == 1.0
    with pytest.raises(ValueError):
        data.targets[0, 0] = 1.0


def test_training_set_normalizes_timestamps_and_preserves_metadata_on_split() -> None:
    cut = datetime(2026, 9, 5, 12, tzinfo=UTC)
    data = _training_set(
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
    data = _training_set(
        np.array([[1.0], [2.0]]),
        np.array([[0.1], [0.2]]),
        timestamps=(datetime(2026, 9, 4, tzinfo=UTC), datetime(2026, 9, 5, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="tz-aware"):
        data.time_split(datetime(2026, 9, 5))
    with pytest.raises(ValueError, match="archive_ref"):
        _training_set(np.array([[1.0]]), np.array([[0.1]]), archive_ref="")


def test_training_set_requires_archive_metadata() -> None:
    with pytest.raises(TypeError, match="timestamps"):
        TrainingSet(np.array([[1.0]]), np.array([[0.1]]))  # type: ignore[call-arg]


def test_parameter_count_requires_a_consistent_total() -> None:
    with pytest.raises(ValueError, match="total"):
        ParameterCount(premise=1, consequent=2, total=2)


@pytest.mark.parametrize("rate", [-0.01, 1.01, float("nan")])
def test_diagnostics_rejects_invalid_clip_binding_rate(rate: float) -> None:
    with pytest.raises(ValueError, match="clip_binding_rate"):
        _diagnostics(clip_binding_rate=rate)


@pytest.mark.parametrize(
    "field",
    [
        "zero_firing_rows_dropped",
        "nonfinite_rows_rejected",
        "premise_steps_rejected",
        "epochs_run",
    ],
)
def test_diagnostics_rejects_negative_counts(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _diagnostics(**{field: -1})


@pytest.mark.parametrize("value", [float("nan"), -1.0])
def test_diagnostics_rejects_nan_or_negative_condition_number(value: float) -> None:
    with pytest.raises(ValueError, match="lse_condition_number"):
        _diagnostics(lse_condition_number=value)


def test_diagnostics_accepts_infinite_condition_number() -> None:
    assert _diagnostics(lse_condition_number=float("inf")).lse_condition_number == float("inf")


def test_diagnostics_rejects_nonfinite_standardization() -> None:
    with pytest.raises(ValueError, match="standardization"):
        _diagnostics(standardization=(np.array([np.nan]),))


def test_diagnostics_accepts_clip_binding_rate_endpoints() -> None:
    assert _diagnostics(clip_binding_rate=0.0).clip_binding_rate == 0.0
    assert _diagnostics(clip_binding_rate=1.0).clip_binding_rate == 1.0


@pytest.mark.parametrize("loss", [float("nan"), float("inf")])
def test_result_rejects_nonfinite_loss_history(loss: float) -> None:
    with pytest.raises(ValueError, match="loss_history"):
        _result(loss_history=(loss,))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_result_rejects_nonfinite_rmse(value: float) -> None:
    with pytest.raises(ValueError, match="train_rmse"):
        _result(train_rmse=np.array([value]))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_result_rejects_nonfinite_validation_rmse(value: float) -> None:
    with pytest.raises(ValueError, match="validation_rmse"):
        _result(validation_rmse=np.array([value]))


def test_result_accepts_absent_validation_rmse() -> None:
    assert _result(validation_rmse=None).validation_rmse is None


def test_parameter_count_rejects_negative_components() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ParameterCount(premise=-1, consequent=2, total=1)


def test_array_bearing_value_types_use_identity_equality() -> None:
    skipped = SkipCounts()
    left = QubitTargets(np.zeros((1, 2)), np.ones(1, dtype=bool), skipped)
    right = QubitTargets(np.zeros((1, 2)), np.ones(1, dtype=bool), skipped)
    assert left != right
    assert left == left
    hash(left)

    target_left = SnapshotTarget(np.zeros(2), np.zeros(2), np.zeros((3, 2)), 1, skipped)
    target_right = SnapshotTarget(np.zeros(2), np.zeros(2), np.zeros((3, 2)), 1, skipped)
    assert target_left != target_right
    hash(_training_set(np.zeros((1, 1)), np.zeros((1, 1))))
    hash(_diagnostics())
    hash(_result())
