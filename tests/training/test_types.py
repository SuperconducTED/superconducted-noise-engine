"""Value-contract tests for supervised training data and results."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.training import (
    ParameterCount,
    TrainingDiagnostics,
    TrainingResult,
    TrainingSet,
)
from superconducted.training.targets import QubitTargets, SkipCounts, SnapshotTarget


def _diagnostics(**overrides: object) -> TrainingDiagnostics:
    """Build a valid TrainingDiagnostics, with one field replaced per call."""
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
    """Build a valid TrainingResult, with one field replaced per call."""
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


# --- TrainingDiagnostics validation (Issue #57 FR-6, section 9.1). -----------


@pytest.mark.parametrize("rate", [-0.01, 1.01, float("nan")])
def test_diagnostics_reject_a_clip_binding_rate_outside_the_unit_interval(
    rate: float,
) -> None:
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
def test_diagnostics_reject_a_negative_count(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _diagnostics(**{field: -1})


@pytest.mark.parametrize("value", [float("nan"), -1.0])
def test_diagnostics_reject_a_nan_or_negative_condition_number(value: float) -> None:
    with pytest.raises(ValueError, match="lse_condition_number"):
        _diagnostics(lse_condition_number=value)


def test_diagnostics_accept_an_infinite_condition_number() -> None:
    """``inf`` is the honest report for a rank-deficient design, not an error.

    ``numpy.linalg.cond`` returns ``inf`` whenever the design matrix is rank
    deficient, including cases ``lstsq`` still solves correctly by minimum
    norm — two identical feature rows leave the intercept identifiable and the
    slope not. ``tests/test_anfis.py::test_observation_weights_change_the_lse_optimum``
    is exactly that fit, and it produces a meaningful result. Rejecting ``inf``
    here would crash a successful fit and suppress the signal the diagnostic
    exists to carry, so this test pins the acceptance deliberately.
    """
    assert _diagnostics(lse_condition_number=float("inf")).lse_condition_number == float("inf")


def test_diagnostics_reject_non_finite_standardization_constants() -> None:
    with pytest.raises(ValueError, match="standardization"):
        _diagnostics(standardization=(np.array([np.nan]),))


def test_diagnostics_accept_the_unit_interval_endpoints() -> None:
    assert _diagnostics(clip_binding_rate=0.0).clip_binding_rate == 0.0
    assert _diagnostics(clip_binding_rate=1.0).clip_binding_rate == 1.0


# --- TrainingResult validation. ---------------------------------------------


@pytest.mark.parametrize("loss", [float("nan"), float("inf")])
def test_result_rejects_a_non_finite_loss_history_entry(loss: float) -> None:
    with pytest.raises(ValueError, match="loss_history"):
        _result(loss_history=(0.5, loss))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_result_rejects_a_non_finite_train_rmse(value: float) -> None:
    with pytest.raises(ValueError, match="train_rmse"):
        _result(train_rmse=np.array([value]))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_result_rejects_a_non_finite_validation_rmse(value: float) -> None:
    with pytest.raises(ValueError, match="validation_rmse"):
        _result(validation_rmse=np.array([value]))


def test_result_accepts_an_absent_validation_rmse() -> None:
    assert _result(validation_rmse=None).validation_rmse is None


def test_parameter_count_rejects_negative_components() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ParameterCount(premise=-1, consequent=2, total=1)


# --- Array-bearing value types must not raise on == or hash(). --------------


def _array_bearing_values() -> list[object]:
    skipped = SkipCounts()
    return [
        _diagnostics(),
        _result(),
        QubitTargets(np.zeros((2, 2)), np.ones(2, dtype=bool), skipped),
        SnapshotTarget(np.zeros(2), np.zeros(2), np.zeros((3, 2)), 1, skipped),
        TrainingSet(np.zeros((2, 1)), np.zeros((2, 1))),
    ]


def test_array_bearing_types_compare_by_identity_without_raising() -> None:
    """A generated __eq__ over ndarray fields raises on two distinct instances.

    The comparison must be between *separately constructed* objects. Tuple
    equality checks identity element-wise before falling back to ``==``, so
    ``value == value`` short-circuits and passes even with a generated
    ``__eq__`` — it never reaches the ndarray field.
    """
    for left, right in zip(_array_bearing_values(), _array_bearing_values(), strict=True):
        assert left is not right
        assert left != right
        assert left == left


def test_array_bearing_types_are_hashable() -> None:
    """A generated __hash__ over ndarray fields raises TypeError."""
    assert len({id(value) for value in _array_bearing_values()}) == 5
    for value in _array_bearing_values():
        hash(value)
