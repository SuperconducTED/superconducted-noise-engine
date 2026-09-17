"""Calibration feature extractors.

Bridge between :class:`CalibrationSnapshot` (rich JSON payload) and the
fixed-shape numeric input vector that :class:`RuleBase.evaluate` consumes.
The bootstrap ships :class:`BasicCalibrationVectorizer` only; richer
extractors (per-qubit, gate-grouped, drift-rate-aware) are deferred to
ADR-013.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from ..interfaces import CalibrationFeatureExtractor
from ..types import CalibrationSnapshot
from .loader import (
    EXPECTED_UNITS,
    UNIT_SCALE,
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

#: Feature name -> the unit the archive declares for the Nduv field it
#: aggregates over. Derived from the two tables `extract` already validates
#: against rather than restated, so it cannot drift from them on its own.
_FEATURE_ARCHIVE_UNIT: Final[Mapping[str, str]] = {
    feature: EXPECTED_UNITS[nduv] for nduv, feature in _NDUV_TO_FEATURE
}


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
                # `isinstance` before the membership test, not decoration: a
                # JSON value may be a list or dict, and those are unhashable,
                # so `name not in collected` raises TypeError on a dict where
                # the previous tuple-membership guard simply did not match.
                # A malformed entry has to be skipped like any other field
                # this extractor does not consume, not crash the caller.
                if not isinstance(name, str) or name not in collected:
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


class ArchiveUnitFeatureExtractor(CalibrationFeatureExtractor):
    """Re-express an SI feature vector in the units the archive declares.

    :class:`BasicCalibrationVectorizer` emits SI seconds for the coherence
    features, which ADR-010 ratifies and which issue #66 exists to make true.
    Not every consumer wants SI. The archive survey
    (``scripts/feature_distribution.py``) and the quantile layout built from
    it (``fuzzy/parameterization.py``) are calibrated in the archive's own
    declared units, microseconds for T1 and T2, and the figures registered as
    NC-041 and NC-042 are in those units. This wrapper is the single, named
    place that conversion happens, so the two conventions meet at one
    boundary instead of each layer guessing.

    The factor is not a hardcoded ``1e6``. It is
    ``1 / UNIT_SCALE[EXPECTED_UNITS[field]]`` per feature, which is exactly
    the scaling :func:`validate_unit_scale` applied on the way in, inverted.
    So this returns the number the source document carried, and a change to
    either table moves both directions together. A dimensionless feature has
    an empty expected unit, scale ``1.0``, and is passed through untouched.

    Wrapping rather than a flag on the vectorizer, and behind the
    :class:`CalibrationFeatureExtractor` ABC, mirrors
    :class:`~superconducted.fuzzy.parameterization.ClampingFeatureExtractor`:
    the composition is visible at the call site, and a caller that wants SI
    simply does not wrap.

    Raises :class:`ValueError` at construction if the wrapped extractor
    reports a feature this module cannot map back to an archive field, since
    silently passing such a feature through at scale ``1.0`` would be a unit
    error of exactly the kind issue #66 was filed for.
    """

    def __init__(self, inner: CalibrationFeatureExtractor | None = None) -> None:
        self._inner: CalibrationFeatureExtractor = (
            BasicCalibrationVectorizer() if inner is None else inner
        )
        unknown = [n for n in self._inner.feature_names if n not in _FEATURE_ARCHIVE_UNIT]
        if unknown:
            raise ValueError(
                f"{type(self._inner).__name__} reports features with no known archive unit: "
                f"{unknown}; add them to _FEATURE_ARCHIVE_UNIT rather than letting them "
                "through unscaled."
            )
        self._scales: npt.NDArray[np.float64] = np.array(
            [1.0 / UNIT_SCALE[_FEATURE_ARCHIVE_UNIT[n]] for n in self._inner.feature_names],
            dtype=np.float64,
        )

    @property
    def output_dim(self) -> int:
        """The wrapped extractor's, unchanged; this rescales, it does not reshape."""
        return self._inner.output_dim

    @property
    def feature_names(self) -> tuple[str, ...]:
        """The wrapped extractor's, unchanged; only the units differ."""
        return self._inner.feature_names

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        """Extract through the wrapped extractor, then convert out of SI."""
        return np.asarray(self._inner.extract(snapshot), dtype=np.float64) * self._scales


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


def mean_readout_error(snapshot: ParsedCalibrationSnapshot) -> float | None:
    """Mean readout error (dimensionless) across qubits with a usable value.

    See :func:`mean_t1` for the skip-strategy contract; readout error
    mirrors it. Unlike T1 and T2 there is no unit conversion involved, only
    the same exclusion of ``None`` and NaN, because the value is a
    probability and :data:`~superconducted.calibration.loader.EXPECTED_UNITS`
    records it as dimensionless.

    This exists so that all three of the vectorizer's outputs can be checked
    against the typed-loader path rather than two of them being checked and
    the third re-derived by hand, which is what issue #66's second acceptance
    criterion asks for.
    """
    values = [
        q.readout_error
        for q in snapshot.qubits
        if q.readout_error is not None and not math.isnan(q.readout_error)
    ]
    if not values:
        return None
    return sum(values) / len(values)
