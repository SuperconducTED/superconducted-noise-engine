"""Tests for calibration-derived supervised training targets."""

from __future__ import annotations

import json
import math
import pathlib
from datetime import UTC, datetime

import numpy as np
import pytest

from superconducted.calibration.features import (
    ArchiveUnitFeatureExtractor,
    BasicCalibrationVectorizer,
)
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
    pathlib.Path(__file__).resolve().parent.parent
    / "fixtures"
    / "calibration"
    / "ibm_fez_20260513T121322Z_with_gates.json"
)
Q72_FIXTURE = GATE_FIXTURE.parent / "ibm_fez_20260513T121322Z_q72_missing_t1t2.json"
SX_SECONDS = 24e-9

#: NC-039: target at mean features minus mean of per-qubit targets, on the
#: gate-bearing fixture at 24 ns.
NC_039_GAP = (-1.8032599909555808e-05, -3.7973319935037924e-04)


def _calibration_snapshot(path: pathlib.Path) -> CalibrationSnapshot:
    """Build the raw envelope the feature extractors take from a fixture file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return CalibrationSnapshot(
        backend=raw["backend"],
        timestamp=datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00")),
        schema_version=raw["schema_version"],
        properties=raw["properties"],
        target=raw.get("target"),
        configuration=raw.get("configuration"),
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
    actual = feature_target_fn(
        np.array([100.0, 150.0, 0.01]), t_seconds=duration, coherence_unit="us"
    )
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
        feature_target_fn(features, t_seconds=duration, coherence_unit="us")


def test_feature_target_fn_refuses_vectorizer_output_without_a_unit() -> None:
    """The trap the explicit unit closes: ``extract`` emits SI seconds since issue #66.

    When the function assumed microseconds, these features were scaled by
    ``1e-6`` a second time, T1 became about ``1.6e-10`` s, and gamma and lambda
    both came back as exactly ``1.0`` with no error raised. That call can no
    longer be written without stating a unit.
    """
    features = BasicCalibrationVectorizer().extract(_calibration_snapshot(Q72_FIXTURE))
    assert 0.0 < features[0] < 1.0, "precondition: the vectorizer emits seconds"
    with pytest.raises(TypeError, match="coherence_unit"):
        feature_target_fn(features, t_seconds=SX_SECONDS)  # type: ignore[call-arg]


def test_feature_target_fn_gives_one_target_for_both_units_of_the_same_snapshot() -> None:
    """``extract`` declared as seconds and its archive-unit wrapper agree.

    Both have to equal the closed form evaluated on the vectorizer's own SI
    seconds, so the ``"s"`` path, the conversion out of SI, and the ``1e-6``
    back into it are checked against each other rather than against a
    remembered magnitude.
    """
    snapshot = _calibration_snapshot(Q72_FIXTURE)
    seconds = BasicCalibrationVectorizer().extract(snapshot)
    t1, t2, _ = seconds
    expected = [
        1.0 - math.exp(-SX_SECONDS / t1),
        1.0 - math.exp(-SX_SECONDS * (2.0 / t2 - 1.0 / t1)),
    ]
    from_seconds = feature_target_fn(seconds, t_seconds=SX_SECONDS, coherence_unit="s")
    from_microseconds = feature_target_fn(
        ArchiveUnitFeatureExtractor().extract(snapshot), t_seconds=SX_SECONDS, coherence_unit="us"
    )
    assert from_seconds == pytest.approx(expected, rel=1e-12)
    assert from_microseconds == pytest.approx(expected, rel=1e-12)
    assert 1e-5 < from_seconds[0] < 1e-3, f"gamma {from_seconds[0]:.3e} is not of order 1e-4"


@pytest.mark.parametrize("unit", ["ns", "S"])
def test_feature_target_fn_rejects_an_unknown_coherence_unit(unit: str) -> None:
    with pytest.raises(ValueError, match="coherence_unit"):
        feature_target_fn(
            np.array([100.0, 150.0, 0.01]),
            t_seconds=SX_SECONDS,
            coherence_unit=unit,  # type: ignore[arg-type]
        )


def test_feature_target_fn_accepts_a_sub_microsecond_mean_t1() -> None:
    """A physically valid device below one microsecond is not mistaken for seconds.

    The first version of this contract guessed the unit from ``mean_T1 < 1.0``
    and rejected this input as SI seconds (PR #107 review).
    """
    gamma, lam = feature_target_fn(
        np.array([0.5, 0.5, 0.01]), t_seconds=SX_SECONDS, coherence_unit="us"
    )
    assert gamma == pytest.approx(1.0 - math.exp(-SX_SECONDS / 0.5e-6), rel=1e-12)
    assert lam == pytest.approx(gamma, rel=1e-12)


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

    snapshot = _calibration_snapshot(GATE_FIXTURE)
    target_at_mean_features = feature_target_fn(
        ArchiveUnitFeatureExtractor().extract(snapshot),
        t_seconds=SX_SECONDS,
        coherence_unit="us",
    )
    # Pinned to NC-039 rather than asserted unequal: once issue #66 made the
    # bare vectorizer emit seconds, the gap here became about 1 instead of
    # about 4e-4, and `not np.allclose(...)` kept passing on the wrong value.
    assert target_at_mean_features - summary.mean == pytest.approx(NC_039_GAP, rel=1e-9)
    # The SI path reaches the same registered gap when it says it is seconds.
    target_from_seconds = feature_target_fn(
        BasicCalibrationVectorizer().extract(snapshot),
        t_seconds=SX_SECONDS,
        coherence_unit="s",
    )
    assert target_from_seconds - summary.mean == pytest.approx(NC_039_GAP, rel=1e-9)
