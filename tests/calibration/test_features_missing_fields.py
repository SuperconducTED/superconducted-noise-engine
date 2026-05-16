"""Skip-strategy aggregator tests for ``mean_t1`` and ``mean_t2``.

Mirrors the contract in ADR-017: missing (``None``) and NaN per-qubit
values are excluded from the mean and counted separately in
:class:`MissingnessStats`. When every qubit lacks a usable value the
aggregate returns ``None`` rather than raising.
"""

from __future__ import annotations

import math
import pathlib

import pytest

from superconducted.calibration.features import mean_t1, mean_t2
from superconducted.calibration.loader import (
    MissingnessStats,
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


def _qubit(
    index: int,
    *,
    t1: float | None,
    t2: float | None = 1e-4,
) -> ParsedQubitCalibration:
    return ParsedQubitCalibration(
        index=index,
        t1_seconds=t1,
        t2_seconds=t2,
        readout_error=0.01,
        prob_meas0_prep1=0.02,
        prob_meas1_prep0=0.015,
        readout_length_seconds=1e-6,
    )


def _snapshot(
    qubits: list[ParsedQubitCalibration],
    *,
    missingness: MissingnessStats | None = None,
) -> ParsedCalibrationSnapshot:
    if missingness is None:
        missingness = MissingnessStats(
            t1_absent=0,
            t2_absent=0,
            readout_error_absent=0,
            readout_length_absent=0,
            prob_meas0_prep1_absent=0,
            prob_meas1_prep0_absent=0,
        )
    return ParsedCalibrationSnapshot(
        timestamp="2026-05-13T12:13:22+00:00",
        backend_name="fake",
        qubits=tuple(qubits),
        missingness=missingness,
    )


def test_mean_t1_skips_missing_qubits() -> None:
    snapshot = _snapshot(
        [
            _qubit(0, t1=None),
            _qubit(1, t1=100e-6),
            _qubit(2, t1=200e-6),
        ]
    )
    result = mean_t1(snapshot)
    assert result == pytest.approx(150e-6)


def test_mean_t1_returns_none_when_all_missing() -> None:
    snapshot = _snapshot([_qubit(0, t1=None), _qubit(1, t1=None)])
    assert mean_t1(snapshot) is None


def test_mean_t1_skips_nan_with_separate_accounting() -> None:
    snapshot = _snapshot(
        [
            _qubit(0, t1=float("nan")),
            _qubit(1, t1=100e-6),
            _qubit(2, t1=200e-6),
        ],
        missingness=MissingnessStats(
            t1_absent=0,
            t2_absent=0,
            readout_error_absent=0,
            readout_length_absent=0,
            prob_meas0_prep1_absent=0,
            prob_meas1_prep0_absent=0,
            nan_present={"T1": 1},
        ),
    )
    result = mean_t1(snapshot)
    assert result == pytest.approx(150e-6)
    assert snapshot.missingness.nan_present.get("T1") == 1


def test_mean_t2_skips_missing_qubits() -> None:
    snapshot = _snapshot(
        [
            _qubit(0, t1=100e-6, t2=None),
            _qubit(1, t1=100e-6, t2=80e-6),
            _qubit(2, t1=100e-6, t2=120e-6),
        ]
    )
    assert mean_t2(snapshot) == pytest.approx(100e-6)


def test_mean_t1_on_exemplar_uses_155_qubits() -> None:
    """Sanity-check the loader+aggregator end-to-end on the real exemplar."""
    snapshot = load_snapshot(FIXTURE)
    values = [
        q.t1_seconds
        for q in snapshot.qubits
        if q.t1_seconds is not None and not math.isnan(q.t1_seconds)
    ]
    assert len(values) == 155
    expected = sum(values) / len(values)
    result = mean_t1(snapshot)
    assert result is not None
    assert result == pytest.approx(expected)


def test_mean_t2_on_exemplar_uses_155_qubits() -> None:
    snapshot = load_snapshot(FIXTURE)
    values = [
        q.t2_seconds
        for q in snapshot.qubits
        if q.t2_seconds is not None and not math.isnan(q.t2_seconds)
    ]
    assert len(values) == 155
    result = mean_t2(snapshot)
    assert result is not None
    assert result == pytest.approx(sum(values) / len(values))
