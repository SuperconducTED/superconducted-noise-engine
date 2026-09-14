"""Calibration feature extractors.

Bridge between :class:`CalibrationSnapshot` (rich JSON payload) and the
fixed-shape numeric input vector that :class:`RuleBase.evaluate` consumes.
The bootstrap ships :class:`BasicCalibrationVectorizer` only; richer
extractors (per-qubit, gate-grouped, drift-rate-aware) are deferred to
ADR-013.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import numpy.typing as npt

from ..interfaces import CalibrationFeatureExtractor
from ..types import CalibrationSnapshot
from .loader import (
    EXPECTED_UNITS,
    UNIT_SCALE,
    CalibrationParseError,
    ParsedCalibrationSnapshot,
)

_DEFAULT_SCHEMA_VERSION: str = "1.0.0"
_FEATURE_NAMES: tuple[str, ...] = ("mean_T1", "mean_T2", "mean_readout_error")


def _coerce_finite_float(value: Any) -> float | None:
    """Best-effort conversion of an Nduv-style ``value`` to a finite float.

    Returns ``None`` if the value is missing, non-numeric, NaN, or infinite.
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


class BasicCalibrationVectorizer(CalibrationFeatureExtractor):
    """Mean-aggregate three core decoherence parameters across all qubits.

    Output vector (shape ``(3,)``): ``(mean_T1, mean_T2, mean_readout_error)``,
    matching the pre-meeting 3x3x3 baseline rule grid. Missing or
    non-finite per-qubit values are dropped before averaging. Raises
    :class:`ValueError` if any of the three feature lists is empty after
    filtering — the caller can decide whether to skip the snapshot.

    Coherence outputs are SI seconds; readout error is dimensionless.
    Declared units must match the loader's expected units. Legacy entries
    without a unit are treated as already SI. Invalid declared units raise
    :class:`CalibrationParseError`, even when the value would be skipped.
    """

    @property
    def output_dim(self) -> int:
        return 3

    @property
    def feature_names(self) -> tuple[str, ...]:
        return _FEATURE_NAMES

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        qubits_section = snapshot.properties.get("qubits", [])
        t1_values: list[float] = []
        t2_values: list[float] = []
        readout_values: list[float] = []
        for qubit_index, qubit_props in enumerate(qubits_section):
            for nduv in qubit_props:
                name = nduv.get("name")
                if name not in ("T1", "T2", "readout_error"):
                    continue
                scale = 1.0
                if "unit" in nduv:
                    unit = nduv["unit"]
                    expected_unit = EXPECTED_UNITS[name]
                    if unit != expected_unit:
                        raise CalibrationParseError(
                            f"backend {snapshot.backend!r} at {snapshot.timestamp.isoformat()}: "
                            f"qubit {qubit_index} field {name!r}: expected unit "
                            f"{expected_unit!r}, got {unit!r} (value={nduv.get('value')!r})"
                        )
                    scale = UNIT_SCALE[expected_unit]
                value = _coerce_finite_float(nduv.get("value"))
                if value is None:
                    continue
                value *= scale
                if name == "T1":
                    t1_values.append(value)
                elif name == "T2":
                    t2_values.append(value)
                elif name == "readout_error":
                    readout_values.append(value)
        if not t1_values or not t2_values or not readout_values:
            raise ValueError(
                "BasicCalibrationVectorizer requires at least one finite value for each of "
                f"T1 ({len(t1_values)}), T2 ({len(t2_values)}), "
                f"readout_error ({len(readout_values)}); snapshot for backend "
                f"{snapshot.backend!r} at {snapshot.timestamp.isoformat()} is unusable."
            )
        return np.array(
            [
                float(np.mean(t1_values)),
                float(np.mean(t2_values)),
                float(np.mean(readout_values)),
            ],
            dtype=np.float64,
        )


def mean_t1(snapshot: ParsedCalibrationSnapshot) -> float | None:
    """Mean T1 (seconds) across qubits with a usable T1 value.

    Skip strategy per ADR-017: per-qubit T1 values that are ``None``
    (Nduv entry absent or explicitly null in the source JSON) or NaN
    are excluded from the average. ``snapshot.missingness`` carries the
    counts so callers can report on what was dropped. Returns ``None``
    when no qubit has a usable T1, rather than raising — let the caller
    decide whether to skip the snapshot.
    """
    values = [
        q.t1_seconds
        for q in snapshot.qubits
        if q.t1_seconds is not None and not math.isnan(q.t1_seconds)
    ]
    if not values:
        return None
    return sum(values) / len(values)


def mean_t2(snapshot: ParsedCalibrationSnapshot) -> float | None:
    """Mean T2 (seconds) across qubits with a usable T2 value.

    See :func:`mean_t1` for the skip-strategy contract; T2 mirrors it.
    """
    values = [
        q.t2_seconds
        for q in snapshot.qubits
        if q.t2_seconds is not None and not math.isnan(q.t2_seconds)
    ]
    if not values:
        return None
    return sum(values) / len(values)
