"""Frozen-dataclass value types shared across the package.

Kept separate from :mod:`superconducted.interfaces` so that the ABC module is
purely contract — no value types, no concrete logic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import numpy.typing as npt


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
