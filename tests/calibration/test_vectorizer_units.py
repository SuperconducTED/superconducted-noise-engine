"""Issue #66: archive units must agree with the typed loader and smoke grid."""

import json
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from scripts.first_ensemble_run import (
    DEFAULT_MF_PLACEMENT,
    _default_mfs_for_feature,
    _load_snapshot,
    _synthetic_snapshot,
    generate_safe_ensemble_with_seed,
)

from superconducted.calibration.features import (
    ArchiveUnitFeatureExtractor,
    BasicCalibrationVectorizer,
    mean_readout_error,
    mean_t1,
    mean_t2,
)
from superconducted.calibration.loader import (
    EXPECTED_UNITS,
    UNIT_SCALE,
    CalibrationParseError,
    load_snapshot,
    validate_unit_scale,
)
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.interfaces import CalibrationFeatureExtractor

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
    """Every output agrees with the typed-loader path, none re-derived here.

    Acceptance criterion 2 asks for agreement with the loader rather than
    hand-written values. The readout third used to be a local comprehension
    that filtered `None` but not NaN, so it encoded a slightly different
    skip policy than the vectorizer and `mean_t1`/`mean_t2` do.
    `mean_readout_error` removes that divergence.
    """
    actual = BasicCalibrationVectorizer().extract(_load_snapshot(FIXTURE))
    parsed = load_snapshot(FIXTURE)
    assert actual == pytest.approx([mean_t1(parsed), mean_t2(parsed), mean_readout_error(parsed)])


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


@pytest.mark.parametrize("name", [[], {}, None, 5, ("T1",)])
def test_malformed_nduv_name_is_skipped_not_raised(name: object) -> None:
    """A malformed `name` is skipped, the way any unconsumed field is.

    JSON values can be lists or dicts, which are unhashable, so testing
    membership against a dict raises `TypeError` where the tuple-membership
    guard this replaced simply did not match. Regression for `6e10825`,
    which made that swap and turned a silent skip into an uncaught
    `TypeError` that is not a `CalibrationParseError`, on a path
    `integration/aer_factory.py` reaches with poller-built snapshots.
    """
    snapshot = _synthetic_snapshot()
    snapshot.properties["qubits"][0].append({"name": name, "unit": "us", "value": 1.0})
    assert BasicCalibrationVectorizer().extract(snapshot) == pytest.approx([50e-6, 50e-6, 0.01])


def test_archive_unit_extractor_inverts_the_loader_scaling() -> None:
    """The wrapper returns the number the source document carried.

    Stated differentially against the SI vectorizer and the loader's own
    tables rather than against literals, so it cannot drift if either table
    changes. The archive declares `us` for coherence, so the factor is 1e6;
    asserting that here would restate the table instead of checking it.
    """
    snapshot = _load_snapshot(FIXTURE)
    si = BasicCalibrationVectorizer().extract(snapshot)
    archive = ArchiveUnitFeatureExtractor().extract(snapshot)
    expected = [
        value / UNIT_SCALE[EXPECTED_UNITS[nduv]]
        for value, nduv in zip(si, ("T1", "T2", "readout_error"), strict=True)
    ]
    assert archive == pytest.approx(expected)


def test_archive_unit_extractor_leaves_dimensionless_features_untouched() -> None:
    """Readout error has no unit, so wrapping must be a no-op for it."""
    snapshot = _load_snapshot(FIXTURE)
    si = BasicCalibrationVectorizer().extract(snapshot)
    archive = ArchiveUnitFeatureExtractor().extract(snapshot)
    assert archive[2] == si[2]
    assert archive[0] != si[0]


def test_archive_unit_extractor_forwards_metadata() -> None:
    inner = BasicCalibrationVectorizer()
    wrapped = ArchiveUnitFeatureExtractor(inner)
    assert wrapped.output_dim == inner.output_dim
    assert wrapped.feature_names == inner.feature_names


def test_archive_unit_extractor_rejects_a_feature_it_cannot_map() -> None:
    """An unmappable feature must fail loudly, not pass through unscaled.

    Passing an unknown feature through at 1.0 would be a silent unit error,
    which is the exact defect issue #66 exists to close, so the wrapper
    refuses to be constructed rather than producing a plausible vector.
    """

    class Extra(CalibrationFeatureExtractor):
        @property
        def output_dim(self) -> int:
            return 2

        @property
        def feature_names(self) -> tuple[str, ...]:
            return ("mean_T1", "mean_frequency")

        def extract(self, snapshot: object) -> npt.NDArray[np.float64]:
            raise AssertionError("never reached; construction must fail first")

    with pytest.raises(ValueError, match="no known archive unit"):
        ArchiveUnitFeatureExtractor(Extra())
