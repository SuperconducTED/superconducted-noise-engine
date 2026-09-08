"""Frozen-dataclass value types shared across the package.

Kept separate from :mod:`superconducted.interfaces` so that the ABC module is
purely contract — no value types, no concrete logic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from .interfaces import RuleBase


@dataclass(frozen=True, slots=True)
class MembershipDegree:
    """A fuzzy membership degree.

    Type-1 membership uses the degenerate form where ``low == high``.
    Interval Type-2 (IT2) membership uses ``low <= high`` representing a
    footprint of uncertainty.
    """

    low: float
    high: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.low <= self.high <= 1.0):
            raise ValueError(
                f"MembershipDegree requires 0 <= low <= high <= 1; got "
                f"low={self.low}, high={self.high}"
            )

    @classmethod
    def crisp(cls, value: float) -> MembershipDegree:
        """Build a degenerate (T1-style) degree where ``low == high == value``."""
        return cls(low=value, high=value)

    @property
    def is_crisp(self) -> bool:
        return self.low == self.high

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.low + self.high)

    @property
    def width(self) -> float:
        return self.high - self.low


@dataclass(frozen=True, slots=True)
class RuleFiringResult:
    """Output of evaluating a fuzzy rule base against a single input vector.

    For T1: ``firing_strengths`` (shape ``(n_rules,)``) holds per-rule
    strengths; ``firing_strengths_lower``/``firing_strengths_upper`` are
    ``None``.

    For IT2: ``firing_strengths_lower`` and ``firing_strengths_upper`` are
    populated; ``firing_strengths`` holds their midpoint as a convenience.

    ``consequent_outputs`` (shape ``(n_rules, output_dim)``) holds per-rule
    TSK linear-consequent outputs.
    """

    firing_strengths: npt.NDArray[np.float64]
    consequent_outputs: npt.NDArray[np.float64]
    firing_strengths_lower: npt.NDArray[np.float64] | None
    firing_strengths_upper: npt.NDArray[np.float64] | None

    def __post_init__(self) -> None:
        if self.firing_strengths.ndim != 1:
            raise ValueError(
                f"firing_strengths must be 1-D; got shape {self.firing_strengths.shape}"
            )
        n_rules = int(self.firing_strengths.shape[0])
        if self.consequent_outputs.ndim != 2:
            raise ValueError(
                f"consequent_outputs must be 2-D; got shape {self.consequent_outputs.shape}"
            )
        if self.consequent_outputs.shape[0] != n_rules:
            raise ValueError(
                f"consequent_outputs.shape[0] ({self.consequent_outputs.shape[0]}) "
                f"must equal n_rules ({n_rules})"
            )
        lower = self.firing_strengths_lower
        upper = self.firing_strengths_upper
        if (lower is None) != (upper is None):
            raise ValueError(
                "firing_strengths_lower and firing_strengths_upper must both be "
                "None (T1) or both be set (IT2)"
            )
        if lower is not None and upper is not None:
            if lower.shape != (n_rules,) or upper.shape != (n_rules,):
                raise ValueError(
                    f"IT2 firing-strength bounds must each have shape ({n_rules},); "
                    f"got lower={lower.shape}, upper={upper.shape}"
                )
            if not bool(np.all(lower <= upper)):
                raise ValueError("Every IT2 firing strength must satisfy lower <= upper")

    @property
    def is_interval_type2(self) -> bool:
        return self.firing_strengths_lower is not None

    @property
    def n_rules(self) -> int:
        return int(self.firing_strengths.shape[0])

    @property
    def output_dim(self) -> int:
        return int(self.consequent_outputs.shape[1])


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    """Single point-in-time record of an IBM backend's calibration.

    ``properties`` is the JSON-serialized form of
    ``BackendProperties.to_dict()``. ``target`` and ``configuration`` are
    JSON-safe reduced projections (or ``None`` for historical snapshots when
    the runtime SDK does not expose ``target_history``). ``timestamp`` MUST
    be tz-aware UTC; non-UTC tz-aware timestamps are normalized.
    """

    backend: str
    timestamp: datetime
    schema_version: str
    properties: dict[str, Any]
    target: dict[str, Any] | None
    configuration: dict[str, Any] | None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "CalibrationSnapshot.timestamp must be tz-aware; got naive "
                f"datetime {self.timestamp!r}"
            )
        if self.timestamp.tzinfo.utcoffset(self.timestamp) != UTC.utcoffset(self.timestamp):
            object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))

    def cache_key(self) -> str:
        """Stable identity for storage idempotency: ``backend:UTC-iso-timestamp``."""
        return f"{self.backend}:{self.timestamp.isoformat()}"

    def storage_filename(self) -> str:
        """Reversibly parseable, Windows-safe UTC filename.

        Format ``YYYYMMDDTHHMMSSffffff Z.json``. Decode with::

            datetime.strptime(stem, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        """
        return f"{self.timestamp.strftime('%Y%m%dT%H%M%S%f')}Z.json"


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Either counts or a density matrix from a single simulation run.

    Exactly one of ``counts`` and ``density_matrix`` must be non-``None``;
    enforced in ``__post_init__``.
    """

    shots: int
    backend_label: str
    counts: Counter[str] | None = None
    density_matrix: npt.NDArray[np.complex128] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.counts is None) == (self.density_matrix is None):
            raise ValueError(
                "SimulationResult requires exactly one of counts or density_matrix; "
                f"got counts={'set' if self.counts is not None else 'None'}, "
                f"density_matrix={'set' if self.density_matrix is not None else 'None'}"
            )
        if self.shots <= 0:
            raise ValueError(f"SimulationResult.shots must be positive; got {self.shots}")


@dataclass(frozen=True, slots=True, eq=False)
class TrainingSet:
    """A finite supervised training set with immutable archive provenance.

    Every row has a UTC timestamp and non-empty source provenance. Feature and
    target names identify vector columns, while ``archive_ref`` identifies the
    archived source revision from which the rows were derived.
    """

    features: npt.NDArray[np.float64]
    targets: npt.NDArray[np.float64]
    timestamps: tuple[datetime, ...]
    provenance: tuple[str, ...]
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]
    archive_ref: str
    weights: npt.NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        features = np.asarray(self.features, dtype=np.float64)
        targets = np.asarray(self.targets, dtype=np.float64)
        if features.ndim != 2 or targets.ndim != 2:
            raise ValueError("TrainingSet features and targets must both be 2-D")
        if features.shape[0] == 0 or targets.shape[0] != features.shape[0]:
            raise ValueError("TrainingSet features and targets must have the same non-zero rows")
        if not np.all(np.isfinite(features)) or not np.all(np.isfinite(targets)):
            raise ValueError("TrainingSet features and targets must be finite")
        n_rows = features.shape[0]
        if len(self.timestamps) != n_rows:
            raise ValueError("TrainingSet timestamps must have one value per row")
        timestamps: list[datetime] = []
        for timestamp in self.timestamps:
            if timestamp.tzinfo is None:
                raise ValueError("TrainingSet timestamps must be tz-aware")
            timestamps.append(timestamp.astimezone(UTC))
        if len(self.provenance) != n_rows or any(not value for value in self.provenance):
            raise ValueError("TrainingSet provenance must contain one non-empty value per row")
        if len(self.feature_names) != features.shape[1] or any(
            not value for value in self.feature_names
        ):
            raise ValueError(
                "TrainingSet feature_names must contain one non-empty value per feature"
            )
        if len(self.target_names) != targets.shape[1] or any(
            not value for value in self.target_names
        ):
            raise ValueError("TrainingSet target_names must contain one non-empty value per target")
        if not self.archive_ref:
            raise ValueError("TrainingSet archive_ref must be non-empty")
        feature_copy = features.copy()
        target_copy = targets.copy()
        feature_copy.flags.writeable = False
        target_copy.flags.writeable = False
        object.__setattr__(self, "features", feature_copy)
        object.__setattr__(self, "targets", target_copy)
        object.__setattr__(self, "timestamps", tuple(timestamps))
        if self.weights is not None:
            weights = np.asarray(self.weights, dtype=np.float64)
            if weights.shape != (n_rows,):
                raise ValueError("TrainingSet weights must have one value per row")
            if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
                raise ValueError("TrainingSet weights must be finite and positive")
            weight_copy = weights.copy()
            weight_copy.flags.writeable = False
            object.__setattr__(self, "weights", weight_copy)

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
        return TrainingSet(
            features=self.features[indices],
            targets=self.targets[indices],
            timestamps=tuple(self.timestamps[index] for index in indices),
            provenance=tuple(self.provenance[index] for index in indices),
            feature_names=self.feature_names,
            target_names=self.target_names,
            archive_ref=self.archive_ref,
            weights=None if self.weights is None else self.weights[indices],
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


@dataclass(frozen=True, slots=True, eq=False)
class TrainingDiagnostics:
    """Diagnostics collected during a training run.

    ``eq=False`` avoids generated equality and hashing over ndarray fields.
    """

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


@dataclass(frozen=True, slots=True, eq=False)
class TrainingResult:
    """Fitted rule base, metrics, and diagnostics.

    ``eq=False`` avoids generated equality and hashing over RMSE ndarray fields.
    """

    rule_base: RuleBase
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
