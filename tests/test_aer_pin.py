"""Conformance pins between derived targets, our channel, and Qiskit Aer."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from qiskit.quantum_info import SuperOp
from qiskit_aer.noise import thermal_relaxation_error
from qiskit_aer.noise.noiseerror import NoiseError

from superconducted.calibration.loader import (
    FieldMissingness,
    MissingnessStats,
    ParsedCalibrationSnapshot,
    ParsedQubitCalibration,
)
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.training.targets import qubit_targets


def _targets(t1: float, t2: float, duration: float) -> np.ndarray:
    missing = FieldMissingness(0, 0, 0)
    snapshot = ParsedCalibrationSnapshot(
        timestamp=datetime(2026, 9, 5, tzinfo=UTC),
        backend_name="test",
        qubits=(
            ParsedQubitCalibration(
                index=0,
                t1_seconds=t1,
                t2_seconds=t2,
                readout_error=0.0,
                init_error=0.0,
                prob_meas0_prep1=0.0,
                prob_meas1_prep0=0.0,
                readout_length_seconds=0.0,
            ),
        ),
        missingness=MissingnessStats(missing, missing, missing, missing, missing, missing, missing),
    )
    targets = qubit_targets(snapshot, {0: duration})
    assert targets.usable[0]
    return targets.values[0]


@pytest.mark.parametrize("duration", [24e-9, 60e-9])
@pytest.mark.parametrize(
    ("t1", "t2"),
    [(100e-6, 80e-6), (100e-6, 150e-6), (100e-6, 100e-6), (100e-6, 200e-6)],
)
def test_derived_target_superop_matches_aer(t1: float, t2: float, duration: float) -> None:
    target = _targets(t1, t2, duration)
    ours = SuperOp(KrausChannelProjector(NoOpNormalization()).project(target, "sx", (0,)))
    aer = SuperOp(thermal_relaxation_error(t1, t2, duration))
    assert np.max(np.abs(ours.data - aer.data)) <= 1e-12


def test_out_of_range_t2_is_skipped_and_rejected_by_aer() -> None:
    t1, t2, duration = 100e-6, 250e-6, 60e-9
    missing = FieldMissingness(0, 0, 0)
    snapshot = ParsedCalibrationSnapshot(
        timestamp=datetime(2026, 9, 5, tzinfo=UTC),
        backend_name="test",
        qubits=(
            ParsedQubitCalibration(
                index=0,
                t1_seconds=t1,
                t2_seconds=t2,
                readout_error=0.0,
                init_error=0.0,
                prob_meas0_prep1=0.0,
                prob_meas1_prep0=0.0,
                readout_length_seconds=0.0,
            ),
        ),
        missingness=MissingnessStats(missing, missing, missing, missing, missing, missing, missing),
    )
    targets = qubit_targets(snapshot, {0: duration})
    assert not targets.usable[0]
    assert targets.skipped.t2_exceeds_2t1 == 1
    with pytest.raises(NoiseError, match=r"T_2 greater than 2 \* T_1"):
        thermal_relaxation_error(t1, t2, duration)
