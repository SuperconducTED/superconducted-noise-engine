"""Typed loader for archived IBM calibration snapshots.

The archival path (``poller.py`` + ``storage.py``) writes the raw
``BackendProperties.to_dict()`` JSON to disk. That representation is
intentionally lossless but inconvenient for downstream consumers: every
per-qubit value is buried in a list of ``{name, unit, value, date}``
dicts (the "Nduv" shape) and there is no guarantee that every standard
entry is present. In particular, real ``properties()`` responses
occasionally omit per-qubit ``T1`` and ``T2`` when the coherence
measurement fails during the calibration window — the qubit's entry in
``properties.qubits`` is otherwise intact but those two Nduv records are
simply absent.

This module materializes a *typed* view of one snapshot file:

- :class:`ParsedCalibrationSnapshot` carries one
  :class:`ParsedQubitCalibration` per physical qubit, with every
  per-qubit field typed ``float | None`` so absence is first-class.
- :class:`MissingnessStats` records, per field, how many qubits had the
  Nduv entry **absent** vs. how many had it present but
  **explicitly null** vs. present but **NaN**. ADR-017 ("Skip" strategy)
  collapses absent and explicit-null into ``None`` for the typed field,
  because downstream aggregators treat them identically — but the
  counters in :class:`MissingnessStats` preserve the distinction for
  diagnostics and for future fuzzification work.
- :func:`load_snapshot` is the single entry point. It validates units
  against a fixed expected-unit table and raises
  :class:`CalibrationParseError` (with snapshot path, qubit index, field
  name, and offending unit/value in the message) on schema violations.

Naming note: the existing :class:`superconducted.types.CalibrationSnapshot`
represents the raw archive form (``properties: dict[str, Any]``). The
types here are prefixed ``Parsed`` to make the distinction obvious to
both readers and the type-checker.
"""

from __future__ import annotations

import json
import math
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final


class CalibrationParseError(ValueError):
    """Raised when a snapshot file violates the loader's schema.

    Schema violations are limited to *units that disagree with the
    expected-unit table*. Missing fields and explicit-null values are
    NOT schema violations — they are tracked in
    :class:`MissingnessStats` and surfaced as ``None`` on the typed
    dataclass.

    Every message carries the snapshot path, the offending qubit index,
    the field name, and (where applicable) the offending unit or value.
    """


# Sentinel for "the Nduv entry was not present at all in the raw list".
# Distinct from ``None`` so the loader can distinguish *absent* from
# *present-with-explicit-null*.
class _AbsentType:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return "<ABSENT>"


_ABSENT: Final[_AbsentType] = _AbsentType()


# Map of expected Nduv name -> expected unit string. Anything outside
# this mapping is currently ignored (e.g. vendor-extension fields). For
# fields *in* this mapping, a unit mismatch is a hard parse error: the
# loader scales by a fixed factor and a wrong unit silently corrupts
# every downstream computation.
_EXPECTED_UNITS: Final[Mapping[str, str]] = {
    "T1": "us",
    "T2": "us",
    "readout_length": "ns",
    "readout_error": "",
    "prob_meas0_prep1": "",
    "prob_meas1_prep0": "",
}

# Conversion factors from the source unit to SI (seconds) for time
# fields. Dimensionless fields are stored as-is.
_UNIT_SCALE: Final[Mapping[str, float]] = {
    "us": 1e-6,
    "ns": 1e-9,
    "": 1.0,
}


@dataclass(frozen=True)
class ParsedQubitCalibration:
    """Typed view of one qubit's calibration entries.

    All numeric fields are ``float | None``. A field is ``None`` when
    the Nduv entry was absent from the raw JSON *or* present with an
    explicit JSON-null value — the distinction is preserved in
    :class:`MissingnessStats` on the parent snapshot. A field carrying
    ``float('nan')`` indicates the Nduv entry was present with a NaN
    value; this is also counted in :class:`MissingnessStats` so
    downstream skip-strategy aggregators can report on it.

    Time fields are stored in SI seconds; ``readout_error``,
    ``prob_meas0_prep1``, and ``prob_meas1_prep0`` are dimensionless
    probabilities in ``[0, 1]``.
    """

    index: int
    t1_seconds: float | None
    t2_seconds: float | None
    readout_error: float | None
    prob_meas0_prep1: float | None
    prob_meas1_prep0: float | None
    readout_length_seconds: float | None


@dataclass(frozen=True)
class MissingnessStats:
    """Per-field counters describing why values are missing.

    ``*_absent``: the Nduv entry for this field was not present at all
    in the qubit's Nduv list. ``explicit_null[field]``: the Nduv entry
    was present but its ``value`` was JSON-null. ``nan_present[field]``:
    the Nduv entry was present with a NaN value. The three counters are
    disjoint per qubit per field.
    """

    t1_absent: int
    t2_absent: int
    readout_error_absent: int
    readout_length_absent: int
    prob_meas0_prep1_absent: int
    prob_meas1_prep0_absent: int
    explicit_null: Mapping[str, int] = field(default_factory=dict)
    nan_present: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedCalibrationSnapshot:
    """One archived calibration snapshot, typed.

    ``qubits`` is a ``tuple`` so the snapshot is hashable in principle;
    NaN-containing instances will not compare equal to themselves by
    field-equality, so tests that need equality should construct
    snapshots without NaN.
    """

    timestamp: str
    backend_name: str
    qubits: tuple[ParsedQubitCalibration, ...]
    missingness: MissingnessStats


def _format_error(
    path: pathlib.Path,
    qubit_index: int,
    field_name: str,
    detail: str,
) -> str:
    return (
        f"{path}: qubit {qubit_index} field {field_name!r}: {detail}"
    )


def _parse_value(
    raw_value: Any,
    expected_unit: str,
    actual_unit: Any,
    *,
    path: pathlib.Path,
    qubit_index: int,
    field_name: str,
) -> tuple[float | None, bool, bool]:
    """Validate unit and coerce ``raw_value`` to a float in SI units.

    Returns ``(value, was_explicit_null, was_nan)``. ``value`` is
    ``None`` for explicit-null inputs, ``float('nan')`` for NaN inputs,
    and otherwise a finite float scaled by :data:`_UNIT_SCALE`.
    """
    if actual_unit != expected_unit:
        raise CalibrationParseError(
            _format_error(
                path,
                qubit_index,
                field_name,
                f"expected unit {expected_unit!r}, got {actual_unit!r} "
                f"(value={raw_value!r})",
            )
        )

    if raw_value is None:
        return None, True, False

    try:
        as_float = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise CalibrationParseError(
            _format_error(
                path,
                qubit_index,
                field_name,
                f"value {raw_value!r} is not numeric ({exc})",
            )
        ) from exc

    if math.isnan(as_float):
        return float("nan"), False, True

    return as_float * _UNIT_SCALE[expected_unit], False, False


def load_snapshot(path: str | pathlib.Path) -> ParsedCalibrationSnapshot:
    """Parse one archived calibration JSON file into a typed snapshot.

    The file is expected to be in the shape produced by ``poller.py``:
    top-level keys include ``backend``, ``timestamp``, and ``properties``;
    ``properties.qubits`` is a list of per-qubit Nduv lists. Per-qubit
    fields that are missing from the raw list, present with an
    explicit JSON-null value, or present with a NaN value are tracked
    in :class:`MissingnessStats` and surfaced as ``None`` or NaN on
    :class:`ParsedQubitCalibration` per ADR-017.

    Raises :class:`CalibrationParseError` on any unit mismatch or
    non-numeric value for a known field. Raises :class:`OSError` if the
    file cannot be opened and :class:`json.JSONDecodeError` if the file
    is not valid JSON.
    """
    snapshot_path = pathlib.Path(path)
    with snapshot_path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    properties = data.get("properties") or {}
    qubits_section = properties.get("qubits") or []
    timestamp = str(data.get("timestamp") or properties.get("last_update_date") or "")
    backend_name = str(data.get("backend") or properties.get("backend_name") or "")

    absent_counts: dict[str, int] = dict.fromkeys(_EXPECTED_UNITS, 0)
    explicit_null_counts: dict[str, int] = {}
    nan_counts: dict[str, int] = {}

    parsed_qubits: list[ParsedQubitCalibration] = []
    for qubit_index, nduv_list in enumerate(qubits_section):
        by_name: dict[str, dict[str, Any]] = {}
        for entry in nduv_list:
            name = entry.get("name")
            if isinstance(name, str):
                by_name[name] = entry

        field_values: dict[str, float | None] = {}
        for field_name, expected_unit in _EXPECTED_UNITS.items():
            entry = by_name.get(field_name)
            if entry is None:
                absent_counts[field_name] += 1
                field_values[field_name] = None
                continue
            value, was_null, was_nan = _parse_value(
                entry.get("value"),
                expected_unit,
                entry.get("unit"),
                path=snapshot_path,
                qubit_index=qubit_index,
                field_name=field_name,
            )
            if was_null:
                explicit_null_counts[field_name] = (
                    explicit_null_counts.get(field_name, 0) + 1
                )
            if was_nan:
                nan_counts[field_name] = nan_counts.get(field_name, 0) + 1
            field_values[field_name] = value

        parsed_qubits.append(
            ParsedQubitCalibration(
                index=qubit_index,
                t1_seconds=field_values["T1"],
                t2_seconds=field_values["T2"],
                readout_error=field_values["readout_error"],
                prob_meas0_prep1=field_values["prob_meas0_prep1"],
                prob_meas1_prep0=field_values["prob_meas1_prep0"],
                readout_length_seconds=field_values["readout_length"],
            )
        )

    missingness = MissingnessStats(
        t1_absent=absent_counts["T1"],
        t2_absent=absent_counts["T2"],
        readout_error_absent=absent_counts["readout_error"],
        readout_length_absent=absent_counts["readout_length"],
        prob_meas0_prep1_absent=absent_counts["prob_meas0_prep1"],
        prob_meas1_prep0_absent=absent_counts["prob_meas1_prep0"],
        explicit_null=dict(explicit_null_counts),
        nan_present=dict(nan_counts),
    )

    return ParsedCalibrationSnapshot(
        timestamp=timestamp,
        backend_name=backend_name,
        qubits=tuple(parsed_qubits),
        missingness=missingness,
    )
