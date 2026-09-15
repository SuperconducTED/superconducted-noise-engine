"""Issue #66: archive units must agree with the typed loader and smoke grid."""

import json
from pathlib import Path

import numpy as np
import pytest
from scripts.first_ensemble_run import (
    DEFAULT_MF_PLACEMENT,
    _default_mfs_for_feature,
    _load_snapshot,
    _synthetic_snapshot,
    generate_safe_ensemble_with_seed,
)

from superconducted.calibration.features import BasicCalibrationVectorizer, mean_t1, mean_t2
from superconducted.calibration.loader import (
    EXPECTED_UNITS,
    UNIT_SCALE,
    CalibrationParseError,
    load_snapshot,
    validate_unit_scale,
)
from superconducted.fuzzy.tsk import TSKRuleBase

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json"
)

# NC-052's registered endpoint firing sum, pinned here rather than checked
# with `> 0` alone. `> 0` is a far weaker guard than it looks: with the
# coherence means 2x out the sum is still 6.0e-21, and 5x out it is
# 4.2e-229, so nothing short of roughly 10x trips it. Issue #66's third
# acceptance criterion asks that a future unit change fail loudly, and only
# the registered value delivers that. NC-052 covers the endpoint placement,
# which is `DEFAULT_MF_PLACEMENT`; interior has no register row, so it keeps
# the non-degeneracy check it was written with.
NC052_ENDPOINT_FIRING_SUM: float = 0.10769113232875129


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
    if placement == DEFAULT_MF_PLACEMENT:
        assert strengths.sum() == pytest.approx(NC052_ENDPOINT_FIRING_SUM, rel=1e-9)
    else:
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


def test_synthetic_snapshot_uses_archive_units() -> None:
    assert BasicCalibrationVectorizer().extract(_synthetic_snapshot()) == pytest.approx(
        [50e-6, 50e-6, 0.01]
    )


@pytest.mark.parametrize("name", ["T1", "T2", "readout_error"])
def test_missing_unit_rejected_by_both_parsers_and_smoke(name: str, tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    entry = next(item for item in data["properties"]["qubits"][0] if item["name"] == name)
    del entry["unit"]
    path = tmp_path / "missing-unit.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    message = f"qubit 0 field '{name}': expected unit .*got None"
    with pytest.raises(CalibrationParseError, match=message):
        load_snapshot(path)
    snapshot = _load_snapshot(path)
    with pytest.raises(CalibrationParseError, match=message):
        BasicCalibrationVectorizer().extract(snapshot)
    with pytest.raises(CalibrationParseError, match=message):
        generate_safe_ensemble_with_seed(snapshot, 1)


def test_every_expected_unit_has_a_conversion_factor() -> None:
    """The loader's two tables must agree on the units they describe."""
    assert set(EXPECTED_UNITS.values()) <= set(UNIT_SCALE)


def test_unit_without_conversion_factor_raises_parse_error() -> None:
    """A unit absent from UNIT_SCALE raises this module's error, not KeyError.

    The note on EXPECTED_UNITS invites cross-module edits to that table. If
    one adds a field whose unit has no SI factor, the failure still has to
    arrive as CalibrationParseError, which is what both archive consumers
    catch and what the loader's docstring promises.
    """
    with pytest.raises(CalibrationParseError, match="no SI conversion factor"):
        validate_unit_scale(
            "GHz",
            "GHz",
            context="ctx",
            qubit_index=0,
            field_name="frequency",
            raw_value=5.0,
        )
