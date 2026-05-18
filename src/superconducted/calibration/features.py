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
        for qubit_props in qubits_section:
            for nduv in qubit_props:
                name = nduv.get("name")
                value = _coerce_finite_float(nduv.get("value"))
                if value is None:
                    continue
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
