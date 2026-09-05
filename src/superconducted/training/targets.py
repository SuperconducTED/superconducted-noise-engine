"""Derived thermal-relaxation targets for supervised TSK training.

The target is the ``(gamma, lambda)`` pair consumed by the single-qubit
amplitude-plus-phase-damping channel. Inputs and outputs use SI seconds and
dimensionless probabilities respectively.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import numpy.typing as npt

from ..calibration.loader import CalibrationParseError, ParsedCalibrationSnapshot


@dataclass(frozen=True, slots=True)
class SkipCounts:
    """Numbers of qubits rejected by the first matching target rule."""

    t1_missing: int = 0
    t2_missing: int = 0
    gate_length_missing: int = 0
    nonpositive: int = 0
    t2_exceeds_2t1: int = 0

    def __post_init__(self) -> None:
        if (
            min(
                self.t1_missing,
                self.t2_missing,
                self.gate_length_missing,
                self.nonpositive,
                self.t2_exceeds_2t1,
            )
            < 0
        ):
            raise ValueError("SkipCounts values must be non-negative")


@dataclass(frozen=True, slots=True)
class QubitTargets:
    """Per-qubit targets, an aligned usable mask, and rejection counts."""

    values: npt.NDArray[np.float64]
    usable: npt.NDArray[np.bool_]
    skipped: SkipCounts

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=np.float64)
        usable = np.asarray(self.usable, dtype=np.bool_)
        if values.ndim != 2 or values.shape[1:] != (2,):
            raise ValueError("QubitTargets.values must have shape (n_qubits, 2)")
        if usable.shape != (values.shape[0],):
            raise ValueError("QubitTargets.usable must have one value per qubit")
        if not np.all(np.isfinite(values[usable])):
            raise ValueError("Usable QubitTargets values must be finite")
        values = values.copy()
        usable = usable.copy()
        values.flags.writeable = False
        usable.flags.writeable = False
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "usable", usable)


@dataclass(frozen=True, slots=True)
class SnapshotTarget:
    """Distribution summary of usable per-qubit channel targets."""

    mean: npt.NDArray[np.float64]
    std: npt.NDArray[np.float64]
    quantiles: npt.NDArray[np.float64]
    n_usable: int
    skipped: SkipCounts

    def __post_init__(self) -> None:
        mean = np.asarray(self.mean, dtype=np.float64)
        std = np.asarray(self.std, dtype=np.float64)
        quantiles = np.asarray(self.quantiles, dtype=np.float64)
        if mean.shape != (2,) or std.shape != (2,) or quantiles.shape != (3, 2):
            raise ValueError("SnapshotTarget arrays must have shapes (2,), (2,), and (3, 2)")
        if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):
            raise ValueError("SnapshotTarget mean and std must be finite")
        if not np.all(np.isfinite(quantiles)) or self.n_usable <= 0:
            raise ValueError("SnapshotTarget requires finite quantiles and usable rows")
        for name, value in (("mean", mean), ("std", std), ("quantiles", quantiles)):
            copy = value.copy()
            copy.flags.writeable = False
            object.__setattr__(self, name, copy)


def _parse_gate_length(value: object, gate: str, qubit: int) -> float:
    """Validate one JSON gate-length value and convert nanoseconds to seconds."""
    if not isinstance(value, (str, int, float)):
        raise CalibrationParseError(f"gate {gate!r} on qubit {qubit}: gate_length is not numeric")
    try:
        length = float(value)
    except ValueError as exc:
        raise CalibrationParseError(
            f"gate {gate!r} on qubit {qubit}: gate_length is not numeric"
        ) from exc
    if not math.isfinite(length):
        raise CalibrationParseError(f"gate {gate!r} on qubit {qubit}: gate_length must be finite")
    return length * 1e-9


def gate_lengths(properties: Mapping[str, Any], gate: str = "sx") -> dict[int, float]:
    """Return single-qubit gate durations in seconds, keyed by qubit index."""
    entries = properties.get("gates")
    if not isinstance(entries, list):
        warnings.warn("Calibration properties has no usable 'gates' list", stacklevel=2)
        return {}

    lengths: dict[int, float] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("gate") != gate:
            continue
        qubits = entry.get("qubits")
        if not isinstance(qubits, list) or len(qubits) != 1 or not isinstance(qubits[0], int):
            continue
        parameters = entry.get("parameters")
        if not isinstance(parameters, list):
            continue
        for parameter in parameters:
            if not isinstance(parameter, Mapping) or parameter.get("name") != "gate_length":
                continue
            if parameter.get("unit") != "ns":
                raise CalibrationParseError(
                    f"gate {gate!r} on qubit {qubits[0]}: expected gate_length unit 'ns', "
                    f"got {parameter.get('unit')!r}"
                )
            lengths[qubits[0]] = _parse_gate_length(parameter.get("value"), gate, qubits[0])
            break
    return lengths


def qubit_targets(
    snapshot: ParsedCalibrationSnapshot,
    lengths: Mapping[int, float],
) -> QubitTargets:
    """Derive aligned ``(gamma, lambda)`` targets from a parsed snapshot."""
    values = np.full((len(snapshot.qubits), 2), np.nan, dtype=np.float64)
    usable = np.zeros(len(snapshot.qubits), dtype=np.bool_)
    counts = SkipCounts()
    for qubit in snapshot.qubits:
        t1, t2, gate_length = qubit.t1_seconds, qubit.t2_seconds, lengths.get(qubit.index)
        if t1 is None or not math.isfinite(t1):
            counts = replace(counts, t1_missing=counts.t1_missing + 1)
        elif t2 is None or not math.isfinite(t2):
            counts = replace(counts, t2_missing=counts.t2_missing + 1)
        elif gate_length is None or not math.isfinite(gate_length):
            counts = replace(counts, gate_length_missing=counts.gate_length_missing + 1)
        elif t1 <= 0.0 or t2 <= 0.0 or gate_length < 0.0:
            counts = replace(counts, nonpositive=counts.nonpositive + 1)
        elif t2 > 2.0 * t1:
            counts = replace(counts, t2_exceeds_2t1=counts.t2_exceeds_2t1 + 1)
        else:
            values[qubit.index] = (
                1.0 - math.exp(-gate_length / t1),
                1.0 - math.exp(-gate_length * (2.0 / t2 - 1.0 / t1)),
            )
            usable[qubit.index] = True
    return QubitTargets(values=values, usable=usable, skipped=counts)


def snapshot_target(targets: QubitTargets) -> SnapshotTarget | None:
    """Summarize usable rows, or return ``None`` when none are usable."""
    values = targets.values[targets.usable]
    if values.size == 0:
        return None
    return SnapshotTarget(
        mean=np.mean(values, axis=0),
        std=np.std(values, axis=0),
        quantiles=np.quantile(values, (0.1, 0.5, 0.9), axis=0),
        n_usable=int(values.shape[0]),
        skipped=targets.skipped,
    )


def feature_target_fn(
    features: npt.NDArray[np.float64], *, t_seconds: float
) -> npt.NDArray[np.float64]:
    """Map BasicCalibrationVectorizer features to a ``(gamma, lambda)`` target.

    ``features`` is ``(mean_T1, mean_T2, mean_readout_error)`` where the two
    coherence values are in microseconds, matching BasicCalibrationVectorizer.
    ``t_seconds`` is the reference gate duration in seconds. This map evaluated
    at mean features is not, in general, the mean of per-qubit targets.
    """
    values = np.asarray(features, dtype=np.float64)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise ValueError("features must be a finite float64 array with shape (3,)")
    if not math.isfinite(t_seconds) or t_seconds < 0.0:
        raise ValueError("t_seconds must be finite and non-negative")
    t1_seconds, t2_seconds = values[:2] * 1e-6
    if t1_seconds <= 0.0 or t2_seconds <= 0.0:
        raise ValueError("mean_T1 and mean_T2 must be positive")
    if t2_seconds > 2.0 * t1_seconds:
        raise ValueError("mean_T2 must not exceed twice mean_T1")
    return np.asarray(
        [
            1.0 - math.exp(-t_seconds / t1_seconds),
            1.0 - math.exp(-t_seconds * (2.0 / t2_seconds - 1.0 / t1_seconds)),
        ],
        dtype=np.float64,
    )
