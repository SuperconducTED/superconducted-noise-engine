"""Calibration feature extractors.

Bridge between :class:`CalibrationSnapshot` (rich JSON payload) and the
fixed-shape numeric input vector that :class:`RuleBase.evaluate` consumes.
The bootstrap ships :class:`BasicCalibrationVectorizer` only; richer
extractors (per-qubit, gate-grouped, drift-rate-aware) are deferred to
ADR-013.
"""

from __future__ import annotations

import math
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from ..interfaces import CalibrationFeatureExtractor
from ..types import CalibrationSnapshot
from .loader import (
    EXPECTED_UNITS,
    ParsedCalibrationSnapshot,
    validate_unit_scale,
)

_DEFAULT_SCHEMA_VERSION: str = "1.0.0"

# The Nduv fields this extractor consumes, in output order, each paired with
# the feature name it aggregates into. One table rather than three parallel
# literals: the guard in `extract`, the per-field dispatch and
# `feature_names` all derive from it, so adding a feature is a single edit.
# Issue #66 was a units defect, but its shape was two copies of one fact
# drifting apart, and three copies of the field set invite the same drift.
_NDUV_TO_FEATURE: Final[tuple[tuple[str, str], ...]] = (
    ("T1", "mean_T1"),
    ("T2", "mean_T2"),
    ("readout_error", "mean_readout_error"),
)
_FEATURE_NAMES: tuple[str, ...] = tuple(feature for _, feature in _NDUV_TO_FEATURE)


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
    Units must be present and match the loader's expected units. Missing
    or invalid units raise
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
        collected: dict[str, list[float]] = {name: [] for name, _ in _NDUV_TO_FEATURE}
        for qubit_index, qubit_props in enumerate(qubits_section):
            for nduv in qubit_props:
                name = nduv.get("name")
                if name not in collected:
                    continue
                scale = validate_unit_scale(
                    nduv.get("unit"),
                    EXPECTED_UNITS[name],
                    context=f"backend {snapshot.backend!r} at {snapshot.timestamp.isoformat()}",
                    qubit_index=qubit_index,
                    field_name=name,
                    raw_value=nduv.get("value"),
                )
                value = _coerce_finite_float(nduv.get("value"))
                if value is None:
                    continue
                collected[name].append(value * scale)
        if not all(collected.values()):
            counts = ", ".join(f"{name} ({len(values)})" for name, values in collected.items())
            raise ValueError(
                "BasicCalibrationVectorizer requires at least one finite value for each of "
                f"{counts}; snapshot for backend "
                f"{snapshot.backend!r} at {snapshot.timestamp.isoformat()} is unusable."
            )
        return np.array(
            [float(np.mean(collected[name])) for name, _ in _NDUV_TO_FEATURE],
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
