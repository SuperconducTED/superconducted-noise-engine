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
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, NamedTuple


class CalibrationParseError(ValueError):
    """Raised when a snapshot file violates the loader's schema.

    Schema violations cover unit mismatches against the expected-unit
    table, non-numeric values for known fields, missing or non-string
    timestamps, invalid timestamp strings, and non-dict ``properties`` /
    non-list ``properties.qubits`` shapes. Missing fields and
    explicit-null values are NOT schema violations — they are tracked
    in :class:`MissingnessStats` and surfaced as ``None`` on the typed
    dataclass.

    Every message carries the snapshot path; qubit index, field name,
    and the offending unit/value are included where applicable.
    """


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


class FieldMissingness(NamedTuple):
    """Per-field missingness counters. Three disjoint failure modes.

    ``absent``: the Nduv entry for this field was not present at all in
    the qubit's Nduv list. ``explicit_null``: the Nduv entry was present
    but its ``value`` was JSON-null. ``nan_present``: the Nduv entry was
    present with a NaN value.
    """

    absent: int
    explicit_null: int
    nan_present: int


@dataclass(frozen=True)
class MissingnessStats:
    """Snapshot-level missingness, one ``FieldMissingness`` per tracked field.

    Each :class:`FieldMissingness` carries three disjoint counters
    (``absent``, ``explicit_null``, ``nan_present``) describing the
    different ways a per-qubit value can fail to materialize. The
    distinction is preserved here even though the Skip strategy
    (ADR-017) collapses ``absent`` and ``explicit_null`` into ``None``
    on the typed dataclass.
    """

    t1: FieldMissingness
    t2: FieldMissingness
    readout_error: FieldMissingness
    readout_length: FieldMissingness
    prob_meas0_prep1: FieldMissingness
    prob_meas1_prep0: FieldMissingness


@dataclass(frozen=True)
class ParsedCalibrationSnapshot:
    """One archived calibration snapshot, typed.

    ``qubits`` is a ``tuple`` so the snapshot is hashable in principle;
    NaN-containing instances will not compare equal to themselves by
    field-equality, so tests that need equality should construct
    snapshots without NaN. ``timestamp`` is a tz-aware UTC
    :class:`datetime` (matches :class:`superconducted.types.CalibrationSnapshot`).
    """

    timestamp: datetime
    backend_name: str
    qubits: tuple[ParsedQubitCalibration, ...]
    missingness: MissingnessStats


def _format_error(
    path: pathlib.Path,
    qubit_index: int,
    field_name: str,
    detail: str,
) -> str:
    return f"{path}: qubit {qubit_index} field {field_name!r}: {detail}"


class ParsedFieldValue(NamedTuple):
    """Outcome of parsing one Nduv ``value``."""

    value: float | None
    was_explicit_null: bool
    was_nan: bool


def _parse_value(
    raw_value: Any,
    expected_unit: str,
    actual_unit: Any,
    *,
    path: pathlib.Path,
    qubit_index: int,
    field_name: str,
) -> ParsedFieldValue:
    """Validate unit and coerce ``raw_value`` to a float in SI units.

    Returns a :class:`ParsedFieldValue`. ``value`` is ``None`` for
    explicit-null inputs, ``float('nan')`` for NaN inputs, and otherwise
    a finite float scaled by :data:`_UNIT_SCALE`.
    """
    if actual_unit != expected_unit:
        raise CalibrationParseError(
            _format_error(
                path,
                qubit_index,
                field_name,
                f"expected unit {expected_unit!r}, got {actual_unit!r} (value={raw_value!r})",
            )
        )

    if raw_value is None:
        return ParsedFieldValue(value=None, was_explicit_null=True, was_nan=False)

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
        return ParsedFieldValue(value=float("nan"), was_explicit_null=False, was_nan=True)

    return ParsedFieldValue(
        value=as_float * _UNIT_SCALE[expected_unit],
        was_explicit_null=False,
        was_nan=False,
    )


def load_snapshot(path: str | pathlib.Path) -> ParsedCalibrationSnapshot:
    """Parse one archived calibration JSON file into a typed snapshot.

    The file is expected to be in the shape produced by ``poller.py``:
    top-level keys include ``backend``, ``timestamp``, and ``properties``;
    ``properties.qubits`` is a list of per-qubit Nduv lists. Per-qubit
    fields that are missing from the raw list, present with an
    explicit JSON-null value, or present with a NaN value are tracked
    in :class:`MissingnessStats` and surfaced as ``None`` or NaN on
    :class:`ParsedQubitCalibration` per ADR-017.

    Raises :class:`CalibrationParseError` on a unit mismatch, a
    non-numeric value for a known field, a missing/non-string or
    unparseable timestamp, or when ``properties`` is not a dict or
    ``properties.qubits`` is not a list. Raises :class:`OSError` if the
    file cannot be opened and :class:`json.JSONDecodeError` if the file
    is not valid JSON.
    """
    snapshot_path = pathlib.Path(path)
    with snapshot_path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    raw_properties = data.get("properties")
    if raw_properties is None:
        properties: dict[str, Any] = {}
    elif not isinstance(raw_properties, dict):
        raise CalibrationParseError(
            f"{snapshot_path}: 'properties' must be a dict, got {type(raw_properties).__name__}"
        )
    else:
        properties = raw_properties

    raw_qubits = properties.get("qubits")
    if raw_qubits is None:
        qubits_section: list[Any] = []
    elif not isinstance(raw_qubits, list):
        raise CalibrationParseError(
            f"{snapshot_path}: 'properties.qubits' must be a list, got {type(raw_qubits).__name__}"
        )
    else:
        qubits_section = raw_qubits

    raw_ts = data.get("timestamp")
    if not isinstance(raw_ts, str):
        raw_ts = properties.get("last_update_date")
    if not isinstance(raw_ts, str):
        raise CalibrationParseError(
            f"{snapshot_path}: snapshot timestamp missing or non-string "
            f"(checked 'timestamp' and 'properties.last_update_date')"
        )
    try:
        parsed_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalibrationParseError(
            f"{snapshot_path}: invalid timestamp {raw_ts!r}: {exc}"
        ) from exc
    if parsed_ts.tzinfo is None:
        parsed_ts = parsed_ts.replace(tzinfo=UTC)
    else:
        parsed_ts = parsed_ts.astimezone(UTC)
    timestamp = parsed_ts

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
                explicit_null_counts[field_name] = explicit_null_counts.get(field_name, 0) + 1
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

    def _bundle(name: str) -> FieldMissingness:
        return FieldMissingness(
            absent=absent_counts[name],
            explicit_null=explicit_null_counts.get(name, 0),
            nan_present=nan_counts.get(name, 0),
        )

    missingness = MissingnessStats(
        t1=_bundle("T1"),
        t2=_bundle("T2"),
        readout_error=_bundle("readout_error"),
        readout_length=_bundle("readout_length"),
        prob_meas0_prep1=_bundle("prob_meas0_prep1"),
        prob_meas1_prep0=_bundle("prob_meas1_prep0"),
    )

    return ParsedCalibrationSnapshot(
        timestamp=timestamp,
        backend_name=backend_name,
        qubits=tuple(parsed_qubits),
        missingness=missingness,
    )
