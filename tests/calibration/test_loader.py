"""Tests for :mod:`superconducted.calibration.loader`."""

from __future__ import annotations

import json
import math
import pathlib
from typing import Any

import pytest

from superconducted.calibration.loader import (
    CalibrationParseError,
    ParsedCalibrationSnapshot,
    ParsedQubitCalibration,
    load_snapshot,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "fixtures"
    / "calibration"
    / "ibm_fez_20260513T121322Z_q72_missing_t1t2.json"
)


def _make_nduv(name: str, unit: str, value: Any) -> dict[str, Any]:
    return {"name": name, "unit": unit, "value": value, "date": "2026-05-13T12:13:22Z"}


def _full_qubit_nduvs(t1_us: float = 200.0, t2_us: float = 150.0) -> list[dict[str, Any]]:
    return [
        _make_nduv("T1", "us", t1_us),
        _make_nduv("T2", "us", t2_us),
        _make_nduv("readout_error", "", 0.01),
        _make_nduv("prob_meas0_prep1", "", 0.02),
        _make_nduv("prob_meas1_prep0", "", 0.015),
        _make_nduv("readout_length", "ns", 1000.0),
    ]


def _synth_snapshot(qubits: list[list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "backend": "fake_backend",
        "timestamp": "2026-05-13T12:13:22+00:00",
        "schema_version": "1.0.0",
        "properties": {
            "backend_name": "fake_backend",
            "last_update_date": "2026-05-13T12:13:22+00:00",
            "qubits": qubits,
        },
    }


def _write(tmp_path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_exemplar_does_not_raise() -> None:
    snapshot = load_snapshot(FIXTURE)
    assert isinstance(snapshot, ParsedCalibrationSnapshot)
    assert len(snapshot.qubits) == 156
    assert snapshot.backend_name == "ibm_fez"


def test_qubit_72_t1_and_t2_are_none() -> None:
    snapshot = load_snapshot(FIXTURE)
    q72 = snapshot.qubits[72]
    assert q72.t1_seconds is None
    assert q72.t2_seconds is None
    assert q72.readout_error is not None
    assert q72.readout_length_seconds is not None


def test_qubit_72_has_index_72() -> None:
    snapshot = load_snapshot(FIXTURE)
    assert snapshot.qubits[72].index == 72
    for i, q in enumerate(snapshot.qubits):
        assert q.index == i


def test_other_qubits_have_populated_t1_and_t2() -> None:
    snapshot = load_snapshot(FIXTURE)
    q0 = snapshot.qubits[0]
    assert q0.t1_seconds is not None and q0.t1_seconds > 0
    assert q0.t2_seconds is not None and q0.t2_seconds > 0
    # us -> seconds: T1 on superconducting hardware is on the order of
    # 1e-4 seconds (~100 us); reject anything off by orders of magnitude.
    assert 1e-6 < q0.t1_seconds < 1e-2
    assert 1e-6 < q0.t2_seconds < 1e-2


def test_missingness_stats_count_one_absent_t1_and_t2() -> None:
    snapshot = load_snapshot(FIXTURE)
    m = snapshot.missingness
    assert m.t1_absent == 1
    assert m.t2_absent == 1
    assert m.readout_error_absent == 0
    assert m.readout_length_absent == 0


def test_missingness_stats_explicit_null_is_separate_counter(
    tmp_path: pathlib.Path,
) -> None:
    """A field with a JSON-null value increments explicit_null, not *_absent."""
    qubits = [_full_qubit_nduvs()]
    # Replace T1 value with explicit null.
    for nduv in qubits[0]:
        if nduv["name"] == "T1":
            nduv["value"] = None
    path = _write(tmp_path, _synth_snapshot(qubits))

    snapshot = load_snapshot(path)
    assert snapshot.qubits[0].t1_seconds is None
    assert snapshot.missingness.t1_absent == 0
    assert snapshot.missingness.explicit_null.get("T1") == 1


def test_distinguishes_absent_null_and_nan(tmp_path: pathlib.Path) -> None:
    """Cornerstone: absent, explicit-null, and NaN are each counted separately."""
    # Qubit 0: T1 fully absent (drop the T1 entry).
    q0 = [nduv for nduv in _full_qubit_nduvs() if nduv["name"] != "T1"]
    # Qubit 1: T1 present with explicit null.
    q1 = _full_qubit_nduvs()
    for nduv in q1:
        if nduv["name"] == "T1":
            nduv["value"] = None
    # Qubit 2: T1 present with NaN value.
    q2 = _full_qubit_nduvs()
    for nduv in q2:
        if nduv["name"] == "T1":
            nduv["value"] = float("nan")
    # Qubit 3: T1 present, normal.
    q3 = _full_qubit_nduvs(t1_us=300.0)

    path = _write(tmp_path, _synth_snapshot([q0, q1, q2, q3]))
    snapshot = load_snapshot(path)

    assert snapshot.qubits[0].t1_seconds is None
    assert snapshot.qubits[1].t1_seconds is None
    assert snapshot.qubits[2].t1_seconds is not None
    assert math.isnan(snapshot.qubits[2].t1_seconds)
    assert snapshot.qubits[3].t1_seconds == pytest.approx(300.0e-6)

    m = snapshot.missingness
    assert m.t1_absent == 1
    assert m.explicit_null.get("T1") == 1
    assert m.nan_present.get("T1") == 1


def test_unit_conversion_us_to_seconds(tmp_path: pathlib.Path) -> None:
    qubits = [_full_qubit_nduvs(t1_us=123.0, t2_us=87.5)]
    path = _write(tmp_path, _synth_snapshot(qubits))
    snapshot = load_snapshot(path)
    q = snapshot.qubits[0]
    assert q.t1_seconds == pytest.approx(123.0e-6)
    assert q.t2_seconds == pytest.approx(87.5e-6)


def test_unit_conversion_ns_to_seconds(tmp_path: pathlib.Path) -> None:
    qubits = [_full_qubit_nduvs()]
    # readout_length default is 1000.0 ns -> 1.0e-6 s.
    path = _write(tmp_path, _synth_snapshot(qubits))
    snapshot = load_snapshot(path)
    assert snapshot.qubits[0].readout_length_seconds == pytest.approx(1.0e-6)


def test_unexpected_unit_raises_parse_error_with_context(
    tmp_path: pathlib.Path,
) -> None:
    qubits = [_full_qubit_nduvs()]
    for nduv in qubits[0]:
        if nduv["name"] == "T1":
            nduv["unit"] = "ms"  # wrong: expected "us"
    path = _write(tmp_path, _synth_snapshot(qubits))

    with pytest.raises(CalibrationParseError) as excinfo:
        load_snapshot(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert "qubit 0" in message
    assert "'T1'" in message
    assert "'ms'" in message
    assert "'us'" in message


def test_dimensionless_field_is_passthrough(tmp_path: pathlib.Path) -> None:
    qubits = [_full_qubit_nduvs()]
    for nduv in qubits[0]:
        if nduv["name"] == "readout_error":
            nduv["value"] = 0.0421
    path = _write(tmp_path, _synth_snapshot(qubits))
    snapshot = load_snapshot(path)
    assert snapshot.qubits[0].readout_error == pytest.approx(0.0421)


def test_typed_qubit_construction_independent_of_loader() -> None:
    """ParsedQubitCalibration is a plain frozen dataclass; tests can build one."""
    q = ParsedQubitCalibration(
        index=0,
        t1_seconds=1e-4,
        t2_seconds=8e-5,
        readout_error=0.01,
        prob_meas0_prep1=0.02,
        prob_meas1_prep0=0.015,
        readout_length_seconds=1e-6,
    )
    assert q.index == 0
    assert q.t1_seconds == pytest.approx(1e-4)
