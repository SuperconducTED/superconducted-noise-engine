"""Tests for calibration-derived supervised training targets."""

from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime

import numpy as np
import pytest

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.loader import (
    FieldMissingness,
    MissingnessStats,
    ParsedCalibrationSnapshot,
    ParsedQubitCalibration,
    load_snapshot,
)
from superconducted.training.targets import (
    feature_target_fn,
    gate_lengths,
    qubit_targets,
    snapshot_target,
)
from superconducted.types import CalibrationSnapshot

GATE_FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures"
    / "calibration"
    / "ibm_fez_20260513T121322Z_with_gates.json"
)


def _snapshot(*qubits: ParsedQubitCalibration) -> ParsedCalibrationSnapshot:
    missing = FieldMissingness(0, 0, 0)
    return ParsedCalibrationSnapshot(
        timestamp=datetime(2026, 9, 5, tzinfo=UTC),
        backend_name="test",
        qubits=qubits,
        missingness=MissingnessStats(missing, missing, missing, missing, missing, missing, missing),
    )


def _qubit(index: int, t1: float | None, t2: float | None) -> ParsedQubitCalibration:
    return ParsedQubitCalibration(
        index=index,
        t1_seconds=t1,
        t2_seconds=t2,
        readout_error=0.0,
        init_error=0.0,
        prob_meas0_prep1=0.0,
        prob_meas1_prep0=0.0,
        readout_length_seconds=0.0,
    )


def test_gate_lengths_reads_single_qubit_sx_entries_in_nanoseconds() -> None:
    properties = {
        "gates": [
            {
                "gate": "sx",
                "qubits": [2],
                "parameters": [{"name": "gate_length", "unit": "ns", "value": 24}],
            },
            {
                "gate": "cz",
                "qubits": [0, 1],
                "parameters": [{"name": "gate_length", "unit": "ns", "value": 99}],
            },
        ]
    }
    assert gate_lengths(properties) == {2: pytest.approx(24e-9)}


def test_gate_lengths_rejects_wrong_unit() -> None:
    properties = {
        "gates": [
            {
                "gate": "sx",
                "qubits": [0],
                "parameters": [{"name": "gate_length", "unit": "us", "value": 1}],
            }
        ]
    }
    with pytest.raises(ValueError, match="qubit 0"):
        gate_lengths(properties)


def test_gate_lengths_returns_empty_mapping_when_gate_list_is_missing() -> None:
    with pytest.warns(UserWarning, match="gates"):
        assert gate_lengths({}) == {}


def test_qubit_targets_match_degenerate_closed_form_points() -> None:
    t1, duration = 100e-6, 60e-9
    targets = qubit_targets(
        _snapshot(_qubit(0, t1, t1), _qubit(1, t1, 2.0 * t1)), {0: duration, 1: duration}
    )
    gamma = 1.0 - np.exp(-duration / t1)
    assert targets.values[0] == pytest.approx([gamma, gamma])
    assert targets.values[1] == pytest.approx([gamma, 0.0])
    assert targets.usable.tolist() == [True, True]


def test_qubit_targets_allow_zero_gate_duration() -> None:
    targets = qubit_targets(_snapshot(_qubit(0, 100e-6, 150e-6)), {0: 0.0})
    assert targets.usable.tolist() == [True]
    assert targets.values[0] == pytest.approx([0.0, 0.0])


def test_qubit_targets_counts_first_skip_reason_and_keeps_nan_rows() -> None:
    targets = qubit_targets(
        _snapshot(
            _qubit(0, None, None),
            _qubit(1, 1.0, None),
            _qubit(2, 0.0, 1.0),
            _qubit(3, 1.0, 3.0),
            _qubit(4, 1.0, 1.0),
        ),
        {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0},
    )
    assert targets.skipped.t1_missing == 1
    assert targets.skipped.t2_missing == 1
    assert targets.skipped.gate_length_missing == 1
    assert targets.skipped.nonpositive == 1
    assert targets.skipped.t2_exceeds_2t1 == 1
    assert not np.any(targets.usable)
    assert np.all(np.isnan(targets.values))
    assert snapshot_target(targets) is None


def test_snapshot_target_uses_only_usable_rows() -> None:
    targets = qubit_targets(_snapshot(_qubit(0, 2.0, 2.0), _qubit(1, None, None)), {0: 1.0})
    summary = snapshot_target(targets)
    assert summary is not None
    assert summary.n_usable == 1
    assert summary.mean == pytest.approx(targets.values[0])


def test_feature_target_fn_agrees_with_one_qubit_target() -> None:
    duration = 60e-9
    expected = qubit_targets(_snapshot(_qubit(0, 100e-6, 150e-6)), {0: duration}).values[0]
    actual = feature_target_fn(np.array([100.0, 150.0, 0.01]), t_seconds=duration)
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize(
    ("features", "duration"),
    [
        (np.array([100.0, 150.0]), 60e-9),
        (np.array([100.0, np.nan, 0.01]), 60e-9),
        (np.array([0.0, 100.0, 0.01]), 60e-9),
        (np.array([100.0, 250.0, 0.01]), 60e-9),
        (np.array([100.0, 150.0, 0.01]), -1.0),
    ],
)
def test_feature_target_fn_rejects_invalid_inputs(features: np.ndarray, duration: float) -> None:
    with pytest.raises(ValueError):
        feature_target_fn(features, t_seconds=duration)


def test_real_fixture_derives_targets_from_all_sx_gate_lengths() -> None:
    raw = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    parsed = load_snapshot(GATE_FIXTURE)
    properties = raw["properties"]
    lengths = gate_lengths(properties)
    targets = qubit_targets(parsed, lengths)
    summary = snapshot_target(targets)

    assert len(lengths) == 156
    assert all(length == pytest.approx(24e-9) for length in lengths.values())
    assert not targets.usable[72]
    assert targets.skipped.t1_missing == 1
    assert targets.skipped.t2_missing == 0
    assert targets.skipped.gate_length_missing == 0
    assert targets.skipped.t2_exceeds_2t1 == 0
    assert summary is not None
    assert summary.n_usable == 155

    raw_snapshot = CalibrationSnapshot(
        backend=raw["backend"],
        timestamp=datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00")),
        schema_version=raw["schema_version"],
        properties=properties,
        target=raw.get("target"),
        configuration=raw.get("configuration"),
    )
    target_at_mean_features = feature_target_fn(
        BasicCalibrationVectorizer().extract(raw_snapshot), t_seconds=24e-9
    )
    assert not np.allclose(target_at_mean_features, summary.mean, rtol=0.0, atol=1e-12)
