"""Value types used by the ANFIS training package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite

import numpy as np
import numpy.typing as npt

from ..fuzzy.tsk import TSKRuleBase


@dataclass(frozen=True, slots=True, eq=False)
class TrainingSet:
    """A finite supervised training set with immutable row metadata.

    Omitted metadata identifies synthetic data used by trainer-level tests and
    smoke runs. Archive-backed callers must supply its source provenance.
    """

    features: npt.NDArray[np.float64]
    targets: npt.NDArray[np.float64]
    weights: npt.NDArray[np.float64] | None = None
    timestamps: tuple[datetime, ...] | None = None
    provenance: tuple[str, ...] | None = None
    feature_names: tuple[str, ...] | None = None
    target_names: tuple[str, ...] | None = None
    archive_ref: str = "synthetic"

    def __post_init__(self) -> None:
        features = np.asarray(self.features, dtype=np.float64)
        targets = np.asarray(self.targets, dtype=np.float64)
        if features.ndim != 2 or targets.ndim != 2:
            raise ValueError("TrainingSet features and targets must both be 2-D")
        if features.shape[0] == 0 or targets.shape[0] != features.shape[0]:
            raise ValueError("TrainingSet features and targets must have the same non-zero rows")
        if not np.all(np.isfinite(features)) or not np.all(np.isfinite(targets)):
            raise ValueError("TrainingSet features and targets must be finite")
        feature_copy = features.copy()
        target_copy = targets.copy()
        feature_copy.flags.writeable = False
        target_copy.flags.writeable = False
        object.__setattr__(self, "features", feature_copy)
        object.__setattr__(self, "targets", target_copy)
        if self.weights is not None:
            weights = np.asarray(self.weights, dtype=np.float64)
            if weights.shape != (features.shape[0],):
                raise ValueError("TrainingSet weights must have one value per row")
            if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
                raise ValueError("TrainingSet weights must be finite and positive")
            weight_copy = weights.copy()
            weight_copy.flags.writeable = False
            object.__setattr__(self, "weights", weight_copy)
        n_rows = features.shape[0]
        if self.timestamps is not None:
            if len(self.timestamps) != n_rows:
                raise ValueError("TrainingSet timestamps must have one value per row")
            timestamps: list[datetime] = []
            for timestamp in self.timestamps:
                if timestamp.tzinfo is None:
                    raise ValueError("TrainingSet timestamps must be tz-aware")
                timestamps.append(timestamp.astimezone(UTC))
            object.__setattr__(self, "timestamps", tuple(timestamps))
        provenance = self.provenance or ("synthetic",) * n_rows
        if len(provenance) != n_rows or any(not value for value in provenance):
            raise ValueError("TrainingSet provenance must contain one non-empty value per row")
        feature_names = self.feature_names or tuple(
            f"feature_{index}" for index in range(self.input_dim)
        )
        target_names = self.target_names or tuple(
            f"target_{index}" for index in range(self.output_dim)
        )
        if len(feature_names) != self.input_dim or any(not value for value in feature_names):
            raise ValueError(
                "TrainingSet feature_names must contain one non-empty value per feature"
            )
        if len(target_names) != self.output_dim or any(not value for value in target_names):
            raise ValueError("TrainingSet target_names must contain one non-empty value per target")
        if not self.archive_ref:
            raise ValueError("TrainingSet archive_ref must be non-empty")
        object.__setattr__(self, "provenance", tuple(provenance))
        object.__setattr__(self, "feature_names", tuple(feature_names))
        object.__setattr__(self, "target_names", tuple(target_names))

    @property
    def n_rows(self) -> int:
        return int(self.features.shape[0])

    @property
    def input_dim(self) -> int:
        return int(self.features.shape[1])

    @property
    def output_dim(self) -> int:
        return int(self.targets.shape[1])

    def time_split(self, cut: datetime) -> tuple[TrainingSet, TrainingSet]:
        """Split at a timestamp boundary without splitting equal timestamps."""
        if self.timestamps is None:
            raise ValueError("time_split requires timestamps")
        if cut.tzinfo is None:
            raise ValueError("time_split cut must be tz-aware")
        normalized_cut = cut.astimezone(UTC)
        train_indices = [
            index for index, timestamp in enumerate(self.timestamps) if timestamp < normalized_cut
        ]
        validation_indices = [
            index for index, timestamp in enumerate(self.timestamps) if timestamp >= normalized_cut
        ]
        if not train_indices or not validation_indices:
            raise ValueError("time_split must leave rows on both sides of the boundary")
        return self._select(train_indices), self._select(validation_indices)

    def _select(self, indices: list[int]) -> TrainingSet:
        weights = None if self.weights is None else self.weights[indices]
        timestamps = None if self.timestamps is None else tuple(self.timestamps[i] for i in indices)
        assert self.provenance is not None
        assert self.feature_names is not None
        assert self.target_names is not None
        provenance = tuple(self.provenance[index] for index in indices)
        return TrainingSet(
            self.features[indices],
            self.targets[indices],
            weights,
            timestamps,
            provenance,
            self.feature_names,
            self.target_names,
            self.archive_ref,
        )


@dataclass(frozen=True, slots=True)
class ParameterCount:
    """Trainable premise and consequent parameter counts."""

    premise: int
    consequent: int
    total: int

    def __post_init__(self) -> None:
        if min(self.premise, self.consequent, self.total) < 0:
            raise ValueError("ParameterCount values must be non-negative")
        if self.total != self.premise + self.consequent:
            raise ValueError("ParameterCount total must equal premise plus consequent")


@dataclass(frozen=True, slots=True)
class TrainingDiagnostics:
    """Diagnostics collected during a training run."""

    clip_binding_rate: float
    zero_firing_rows_dropped: int
    nonfinite_rows_rejected: int
    lse_condition_number: float
    premise_steps_rejected: int
    epochs_run: int
    early_stopped: bool
    standardization: tuple[npt.NDArray[np.float64], ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.clip_binding_rate <= 1.0:
            raise ValueError("clip_binding_rate must be in [0, 1]")
        if (
            min(
                self.zero_firing_rows_dropped,
                self.nonfinite_rows_rejected,
                self.premise_steps_rejected,
                self.epochs_run,
            )
            < 0
        ):
            raise ValueError("TrainingDiagnostics counts must be non-negative")
        if self.lse_condition_number < 0.0 or np.isnan(self.lse_condition_number):
            raise ValueError("lse_condition_number must be non-negative and not NaN")
        if any(not np.all(np.isfinite(values)) for values in self.standardization):
            raise ValueError("standardization values must be finite")


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Fitted rule base, metrics, and diagnostics."""

    rule_base: TSKRuleBase
    train_rmse: npt.NDArray[np.float64]
    validation_rmse: npt.NDArray[np.float64] | None
    loss_history: tuple[float, ...]
    diagnostics: TrainingDiagnostics
    parameter_count: ParameterCount
    seed: int | None = None

    def __post_init__(self) -> None:
        if any(not isfinite(loss) for loss in self.loss_history):
            raise ValueError("TrainingResult loss_history must be finite")
        if not np.all(np.isfinite(self.train_rmse)):
            raise ValueError("TrainingResult train_rmse must be finite")
        if self.validation_rmse is not None and not np.all(np.isfinite(self.validation_rmse)):
            raise ValueError("TrainingResult validation_rmse must be finite")
