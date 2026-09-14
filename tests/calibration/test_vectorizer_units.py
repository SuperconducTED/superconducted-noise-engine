"""Issue #66: archive units must agree with the typed loader and smoke grid."""

from pathlib import Path

import numpy as np
import pytest
from scripts.first_ensemble_run import (
    _default_mfs_for_feature,
    _load_snapshot,
    _synthetic_snapshot,
    generate_safe_ensemble_with_seed,
)

from superconducted.calibration.features import BasicCalibrationVectorizer, mean_t1, mean_t2
from superconducted.calibration.loader import CalibrationParseError, load_snapshot
from superconducted.fuzzy.tsk import TSKRuleBase

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json"
)


def test_real_fixture_matches_loader_seconds() -> None:
    actual = BasicCalibrationVectorizer().extract(_load_snapshot(FIXTURE))
    parsed = load_snapshot(FIXTURE)
    assert actual[:2] == pytest.approx([mean_t1(parsed), mean_t2(parsed)])
    errors = [q.readout_error for q in parsed.qubits if q.readout_error is not None]
    assert actual[2] == pytest.approx(np.mean(errors))


@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_real_fixture_fires_shipped_grid(placement: str) -> None:
    vectorizer = BasicCalibrationVectorizer()
    snapshot = _load_snapshot(FIXTURE)
    grid = TSKRuleBase.from_grid(
        per_input_mfs=[
            _default_mfs_for_feature(name, placement) for name in vectorizer.feature_names
        ],
        output_dim=2,
    )
    strengths = grid.evaluate(vectorizer.extract(snapshot)).firing_strengths
    assert np.isfinite(strengths).all()
    assert strengths.sum() > 0
    members, _ = generate_safe_ensemble_with_seed(snapshot, 1, placement)
    assert len(members) == 1


@pytest.mark.parametrize(
    ("name", "unit"),
    [(name, unit) for name in ("T1", "T2", "readout_error") for unit in ("ms", "ns", None, [])]
    + [("T1", ""), ("T2", "")],
)
def test_invalid_declared_units_raise(name: str, unit: object) -> None:
    snapshot = _synthetic_snapshot()
    entry = next(item for item in snapshot.properties["qubits"][0] if item["name"] == name)
    entry["unit"] = unit
    entry["value"] = None  # Unit validation precedes missing-value filtering.
    with pytest.raises(CalibrationParseError, match=f"qubit 0 field '{name}'.*expected unit"):
        BasicCalibrationVectorizer().extract(snapshot)


def test_synthetic_snapshot_preserves_unitless_si_values() -> None:
    assert BasicCalibrationVectorizer().extract(_synthetic_snapshot()) == pytest.approx(
        [50e-6, 50e-6, 0.01]
    )
