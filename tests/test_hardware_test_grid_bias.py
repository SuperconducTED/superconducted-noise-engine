"""Tests for the #125 delay-grid bias computation (scripts/hardware_test_grid_bias.py).

Pure functions; no archive, no network, no filesystem beyond ``tmp_path`` for the writer.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest
from scripts.hardware_test_grid_bias import (
    ARM_A_SHOTS,
    GRIDS,
    TSV_COLUMNS,
    bias_rows,
    decay_probability,
    delay_grid,
    expected_abs_error,
    score_difference,
    tie_point,
    write_rows,
)

# The eight discriminating disagreements of PR #126's dry run lay in this range, all negative.
DRY_RUN_RANGE = (-1.71, -1.04, -0.58)


@pytest.mark.parametrize("grid", GRIDS)
@pytest.mark.parametrize("d", [-1.04, 0.75])
@pytest.mark.parametrize("shots", [None, ARM_A_SHOTS])
def test_each_predictor_wins_when_the_truth_sits_on_it(
    grid: str, d: float, shots: int | None
) -> None:
    assert score_difference(grid, d, 0.0, shots=shots) > 0.0  # truth on the reading
    assert score_difference(grid, d, 1.0, shots=shots) < 0.0  # truth on the level


@pytest.mark.parametrize("grid", GRIDS)
@pytest.mark.parametrize("d", [-1.71, -0.58, 1.0])
def test_noiseless_tie_point_does_not_move_under_a_common_readout(grid: str, d: float) -> None:
    ideal = tie_point(grid, d)
    with_readout = tie_point(grid, d, readout=(0.02, 0.02))
    assert math.isfinite(ideal)
    assert with_readout == pytest.approx(ideal, abs=1e-6)


@pytest.mark.parametrize("size", [0.37, 1.04, 1.71])
@pytest.mark.parametrize("shots", [None, ARM_A_SHOTS])
def test_union_grid_is_symmetric_between_the_two_predictors(size: float, shots: int | None) -> None:
    below = tie_point("union", -size, shots=shots)
    above = tie_point("union", size, shots=shots)
    assert above == pytest.approx(1.0 - below, abs=1e-5)


@pytest.mark.parametrize("t1_true", [0.3, 0.6, 1.0, 1.7])
@pytest.mark.parametrize("t1_pred", [0.4, 1.0, 2.5])
def test_shot_noise_never_lowers_the_expected_error(t1_true: float, t1_pred: float) -> None:
    delays = delay_grid("union", 0.5, 1.0)
    noiseless = expected_abs_error(delays, t1_pred, t1_true)
    noisy = expected_abs_error(delays, t1_pred, t1_true, shots=ARM_A_SHOTS)
    assert noisy >= noiseless - 1e-12


@pytest.mark.parametrize("d", DRY_RUN_RANGE)
@pytest.mark.parametrize("shots", [None, ARM_A_SHOTS])
def test_the_level_centred_grid_favours_the_reading(d: float, shots: int | None) -> None:
    """The finding the pre-registration rests on: the design's grid tilts toward the reading."""
    assert tie_point("level", d, shots=shots) > 0.5
    assert tie_point("reading", d, shots=shots) < 0.5


def test_grids_start_at_zero_and_the_union_has_seven_delays() -> None:
    for grid in GRIDS:
        delays = delay_grid(grid, math.exp(-1.0), 1.0)
        assert delays[0] == 0.0
        assert np.all(np.diff(delays) > 0.0)
    assert delay_grid("union", math.exp(-1.0), 1.0).size == 7
    assert delay_grid("union", 1.0, 1.0).size == 4
    assert delay_grid("level", 0.2, 3.0).tolist() == [0.0, 1.5, 3.0, 6.0]


def test_decay_probability_matches_the_design_form() -> None:
    p = decay_probability([0.0, 1.0], 1.0, prob_meas0_prep1=0.03, prob_meas1_prep0=0.01)
    assert p[0] == pytest.approx(1.0 - 0.03)
    assert p[1] == pytest.approx(0.01 + (1.0 - 0.01 - 0.03) * math.exp(-1.0))


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        delay_grid("level", 0.0, 1.0)
    with pytest.raises(ValueError):
        delay_grid("bogus", 1.0, 1.0)
    with pytest.raises(ValueError):
        score_difference("level", 0.0, 0.5)
    with pytest.raises(ValueError):
        expected_abs_error([0.5], 1.0, 1.0, shots=0)
    with pytest.raises(ValueError):
        decay_probability([-1.0], 1.0)
    with pytest.raises(ValueError):
        decay_probability([1.0], 1.0, prob_meas0_prep1=0.6, prob_meas1_prep0=0.5)


def test_bias_rows_cover_every_combination_and_write(tmp_path: Path) -> None:
    rows = bias_rows(disagreements=(0.5,))
    assert len(rows) == len(GRIDS) * 2 * 2
    assert all(math.isfinite(r.tie_point) and r.sign_changes == 1 for r in rows)
    path = write_rows(tmp_path, rows)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        assert tuple(reader.fieldnames or ()) == TSV_COLUMNS
        assert len(list(reader)) == len(rows)
