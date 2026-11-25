"""Tests for ``scripts/fuzzy_band_members.py``: the member (gamma, lambda) band for #161 (gate L4).

The criteria are numbered as in ``docs/implementations/2026-11-25-member-target-band.md``. Every test
reads the committed gates-bearing ``ibm_fez`` fixture of 2026-05-13 or synthetic data, never an
archive file: the ladder's test rows start at 2026-09-01, and ``_document`` asserts the fixture
predates that cut (criterion 7).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from scripts.fuzzy_band_members import (
    TARGET_NAMES,
    TargetBand,
    _dependencies,
    ensemble_for_state,
    member_targets,
    snapshot_from_document,
    target_band,
)
from superconducted.calibration.features import (
    ArchiveUnitFeatureExtractor,
    BasicCalibrationVectorizer,
)
from superconducted.calibration.loader import CalibrationParseError
from superconducted.fuzzy.defuzzification import NieTanDefuzzifier, WeightedAverageDefuzzifier
from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.integration.perturbation import InputVectorPerturbation
from superconducted.interfaces import Defuzzifier
from superconducted.training import HybridANFISTrainer, TrainingSet
from superconducted.training import anfis
from superconducted.types import CalibrationSnapshot

FIXTURE = (
    Path(__file__).parent / "fixtures" / "calibration" / "ibm_fez_20260513T121322Z_with_gates.json"
)

#: The snapshot boundary of the ladder (persistence README section 2). No test reads a document
#: at or after it.
CUT = datetime(2026, 9, 1, tzinfo=UTC)

#: Relative tolerance of criterion 1. The engine's path (defuzzifier, then ``ProbabilityClip``)
#: and the trainer's (``_effective_weights @ consequents``) are two arithmetic routes to one
#: value; the 2026-11-25 probe measured them 3.9e-15 apart, so bit equality is not the contract.
PARITY_RTOL = 1e-12


def _document() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    stamp = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
    assert stamp < CUT, f"test fixture {FIXTURE.name} is not before the ladder's cut"
    return data


@pytest.fixture(scope="module")
def snapshot() -> CalibrationSnapshot:
    return snapshot_from_document(_document(), source=FIXTURE.name)


def _archive_x(snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
    return np.asarray(ArchiveUnitFeatureExtractor().extract(snapshot), dtype=np.float64)


def _fitted(
    snapshot: CalibrationSnapshot, *, interval: bool
) -> tuple[TSKRuleBase, Defuzzifier]:
    """A rule base fitted by ``HybridANFISTrainer`` around the fixture's own vector.

    Two memberships per feature at 0.8x and 1.2x the fixture's value (archive units, the
    training TSV's), consequents fitted by least squares (``epochs=0``) to a planted linear
    target that stays inside (0, 1) over the sampled box, so neither engine nor trainer clips.
    """
    x = _archive_x(snapshot)
    per_input: list[list[GaussianMF] | list[IntervalGaussianMF]] = []
    for value in x:
        width = 0.3 * abs(float(value))
        if interval:
            per_input.append(
                [IntervalGaussianMF(float(value) * c, 0.8 * width, width) for c in (0.8, 1.2)]
            )
        else:
            per_input.append([GaussianMF(center=float(value) * c, sigma=width) for c in (0.8, 1.2)])
    grid = TSKRuleBase.from_grid(per_input_mfs=per_input, output_dim=2, consequent_init="zeros")
    # A positive intercept, because the trainer refuses a warm start that is identity damping
    # on every row (Issue #60 decision 5); zeros would be.
    warm = TSKRuleBase(
        [
            TSKRule(rule.antecedent_mfs, np.tile([0.0, 0.0, 0.0, 0.05], (2, 1)))
            for rule in grid.rules
        ],
        input_dim=x.size,
        output_dim=2,
    )
    rng = np.random.default_rng(20261125)
    features = x * (1.0 + 0.2 * rng.uniform(-1.0, 1.0, size=(60, x.size)))
    relative = features / x - 1.0
    targets = np.column_stack(
        [
            0.05 + 0.02 * relative[:, 0] - 0.01 * relative[:, 2],
            0.30 + 0.05 * relative[:, 1] + 0.02 * relative[:, 0],
        ]
    )
    start = datetime(2026, 5, 1, tzinfo=UTC)
    data = TrainingSet(
        features=features,
        targets=targets,
        timestamps=tuple(start + timedelta(hours=k) for k in range(features.shape[0])),
        provenance=tuple(f"synthetic-{k}" for k in range(features.shape[0])),
        feature_names=tuple(ArchiveUnitFeatureExtractor().feature_names),
        target_names=TARGET_NAMES,
        archive_ref="synthetic",
    )
    result = HybridANFISTrainer(epochs=0, ridge=0.0).fit(warm, data)
    assert isinstance(result.rule_base, TSKRuleBase)
    defuzzifier: Defuzzifier = NieTanDefuzzifier() if interval else WeightedAverageDefuzzifier()
    return result.rule_base, defuzzifier


@pytest.fixture(scope="module")
def fitted_t1(snapshot: CalibrationSnapshot) -> tuple[TSKRuleBase, Defuzzifier]:
    return _fitted(snapshot, interval=False)


# Criterion 1: parity with the trainer's own prediction path.


@pytest.mark.parametrize("interval", [False, True], ids=["t1", "it2"])
def test_identity_member_matches_the_trainers_prediction(
    snapshot: CalibrationSnapshot, interval: bool
) -> None:
    rule_base, defuzzifier = _fitted(snapshot, interval=interval)
    deps = _dependencies(snapshot, rule_base=rule_base, defuzzifier=defuzzifier)
    member = next(iter(FuzzyNoiseModelEnsemble(**deps, ensemble_size=1)))
    x = _archive_x(snapshot)
    expected = ProbabilityClip().squash(anfis._predict(rule_base, x[None, :])[0])

    assert member.crisp_params.shape == (2,)
    assert np.all((expected > 0.0) & (expected < 1.0)), "the parity point must not be clipped"
    np.testing.assert_allclose(member.crisp_params, expected, rtol=PARITY_RTOL, atol=0.0)


def test_a_rule_base_without_two_outputs_is_refused(snapshot: CalibrationSnapshot) -> None:
    x = _archive_x(snapshot)
    three = TSKRuleBase.from_grid(
        per_input_mfs=[[GaussianMF(center=float(v), sigma=abs(float(v)))] for v in x],
        output_dim=3,
        consequent_init="zeros",
    )
    with pytest.raises(ValueError, match="gamma, lambda"):
        ensemble_for_state(
            snapshot,
            rule_base=three,
            defuzzifier=WeightedAverageDefuzzifier(),
            r=0.05,
            size=4,
            seed=np.random.SeedSequence(161),
        )


# Criterion 2: the members are read from the ensemble, and the result is a function of the seed.


def test_member_targets_are_the_members_own_crisp_params(
    snapshot: CalibrationSnapshot, fitted_t1: tuple[TSKRuleBase, Defuzzifier]
) -> None:
    rule_base, defuzzifier = fitted_t1
    ensemble = ensemble_for_state(
        snapshot,
        rule_base=rule_base,
        defuzzifier=defuzzifier,
        r=0.05,
        size=8,
        seed=np.random.SeedSequence(161),
    )
    got = member_targets(ensemble)
    expected = np.stack([member.crisp_params[:2] for member in ensemble])

    assert got.shape == (8, 2)
    assert got.dtype == np.float64
    assert np.array_equal(got, expected)
    assert not got.flags.writeable
    assert np.unique(got[:, 0]).size == 8, "the jitter must move every member's gamma"
    assert np.unique(got[:, 1]).size == 8, "the jitter must move every member's lambda"


def test_one_seed_gives_one_ensemble_even_when_reused(
    snapshot: CalibrationSnapshot, fitted_t1: tuple[TSKRuleBase, Defuzzifier]
) -> None:
    rule_base, defuzzifier = fitted_t1
    seed = np.random.SeedSequence(161)

    def members(seed_sequence: np.random.SeedSequence) -> npt.NDArray[np.float64]:
        return member_targets(
            ensemble_for_state(
                snapshot,
                rule_base=rule_base,
                defuzzifier=defuzzifier,
                r=0.05,
                size=6,
                seed=seed_sequence,
            )
        )

    first = members(seed)
    again = members(seed)
    fresh = members(np.random.SeedSequence(161))
    other = members(np.random.SeedSequence(162))

    assert seed.n_children_spawned == 0, "the caller's seed sequence must not be advanced"
    assert np.array_equal(first, again)
    assert np.array_equal(first, fresh)
    assert not np.array_equal(first, other)


# Criterion 5: units. The centre is the archive-unit vector, end to end.


def test_a_vanishing_jitter_reproduces_the_trainers_point(
    snapshot: CalibrationSnapshot, fitted_t1: tuple[TSKRuleBase, Defuzzifier]
) -> None:
    rule_base, defuzzifier = fitted_t1
    members = member_targets(
        ensemble_for_state(
            snapshot,
            rule_base=rule_base,
            defuzzifier=defuzzifier,
            r=1e-9,
            size=4,
            seed=np.random.SeedSequence(161),
        )
    )
    x = _archive_x(snapshot)
    point = ProbabilityClip().squash(anfis._predict(rule_base, x[None, :])[0])
    si_point = ProbabilityClip().squash(
        anfis._predict(rule_base, np.asarray(BasicCalibrationVectorizer().extract(snapshot))[None, :])[0]
    )

    assert not np.allclose(point, si_point, rtol=1e-3), "SI and archive units must be told apart"
    np.testing.assert_allclose(members, np.tile(point, (4, 1)), rtol=1e-6, atol=0.0)


def test_a_centre_in_other_units_is_refused_by_the_engine(
    snapshot: CalibrationSnapshot, fitted_t1: tuple[TSKRuleBase, Defuzzifier]
) -> None:
    """Why the centre must come from the extractor the ensemble uses (documents the engine's guard)."""
    rule_base, defuzzifier = fitted_t1
    si = np.asarray(BasicCalibrationVectorizer().extract(snapshot), dtype=np.float64)
    perturbation = InputVectorPerturbation.relative(
        si, 0.05, feature_names=ArchiveUnitFeatureExtractor().feature_names
    )
    ensemble = FuzzyNoiseModelEnsemble(
        **_dependencies(snapshot, rule_base=rule_base, defuzzifier=defuzzifier),
        ensemble_size=2,
        rng=np.random.default_rng(161),
        perturbation=perturbation,
    )
    with pytest.raises(ValueError, match="offset was drawn at"):
        member_targets(ensemble)


# Criterion 6: live and backfilled documents; the parser's validation is applied.


def test_a_backfilled_document_builds_the_same_members(
    fitted_t1: tuple[TSKRuleBase, Defuzzifier],
) -> None:
    rule_base, defuzzifier = fitted_t1
    live = _document()
    assert live.get("configuration") is not None, "the fixture must be a live document"
    backfilled = copy.deepcopy(live)
    backfilled["configuration"] = None

    def members(document: dict[str, Any]) -> npt.NDArray[np.float64]:
        return member_targets(
            ensemble_for_state(
                snapshot_from_document(document, source="fixture"),
                rule_base=rule_base,
                defuzzifier=defuzzifier,
                r=0.05,
                size=4,
                seed=np.random.SeedSequence(161),
            )
        )

    assert np.array_equal(members(live), members(backfilled))


def test_snapshot_from_document_keeps_the_raw_sections(snapshot: CalibrationSnapshot) -> None:
    document = _document()
    assert snapshot.properties == document["properties"]
    assert snapshot.configuration == document["configuration"]
    assert snapshot.target == document.get("target")
    assert snapshot.backend == document["backend"]


def test_snapshot_from_document_applies_the_parsers_validation() -> None:
    document = _document()
    document["properties"] = ["not", "a", "dict"]
    with pytest.raises(CalibrationParseError):
        snapshot_from_document(document, source="malformed")


# Criteria 3 and 4: the band, and the clip counts.

#: Five members, columns (gamma, lambda), built so that the two quantile levels, the two
#: components and the two methods each give different numbers.
TABLE = np.array(
    [
        [0.00, 0.40],
        [0.01, 0.55],
        [0.03, 1.00],
        [0.07, 0.30],
        [0.20, 1.00],
    ],
    dtype=np.float64,
)


@pytest.mark.parametrize("method", ["linear", "higher"])
def test_band_edges_are_numpys_quantiles_per_component(method: str) -> None:
    band = target_band(TABLE, alpha=0.10, method=method)
    lower, upper = np.quantile(TABLE, [0.10, 0.90], axis=0, method=method)

    assert band.names == TARGET_NAMES == ("gamma", "lambda")
    assert np.array_equal(band.lower, lower)
    assert np.array_equal(band.upper, upper)
    assert band.alpha == 0.10
    assert band.method == method
    assert band.n_members == 5


def test_the_table_separates_what_the_band_could_confuse() -> None:
    """A control: without these differences the edge test above could not fail."""
    lin_lo, lin_hi = np.quantile(TABLE, [0.10, 0.90], axis=0, method="linear")
    hi_lo, hi_hi = np.quantile(TABLE, [0.10, 0.90], axis=0, method="higher")
    assert not np.array_equal(lin_lo, hi_lo)
    assert not np.array_equal(lin_lo, lin_hi)
    assert lin_lo[0] != lin_lo[1]
    assert not np.array_equal(
        np.quantile(TABLE, 0.10, axis=0), np.quantile(TABLE, 0.20, axis=0)
    )


def test_band_counts_members_at_either_clip_bound() -> None:
    band = target_band(TABLE, alpha=0.10, method="linear")
    assert band.at_lower.tolist() == [1, 0]
    assert band.at_upper.tolist() == [0, 2]


def test_band_arrays_are_read_only_copies() -> None:
    table = TABLE.copy()
    band = target_band(table, alpha=0.10, method="linear")
    table[:] = 0.5
    assert band.n_members == 5
    for array in (band.lower, band.upper, band.at_lower, band.at_upper):
        assert not array.flags.writeable
    assert band.lower[0] == np.quantile(TABLE[:, 0], 0.10)


@pytest.mark.parametrize(
    ("table", "alpha", "method", "match"),
    [
        (TABLE[:1], 0.10, "linear", "at least two members"),
        (TABLE[:, :1], 0.10, "linear", r"\(n_members, 2\)"),
        (np.vstack([TABLE, [[np.nan, 0.5]]]), 0.10, "linear", "finite"),
        (np.vstack([TABLE, [[-0.01, 0.5]]]), 0.10, "linear", r"\[0, 1\]"),
        (np.vstack([TABLE, [[0.5, 1.01]]]), 0.10, "linear", r"\[0, 1\]"),
        (TABLE, -0.1, "linear", "alpha"),
        (TABLE, 0.5, "linear", "alpha"),
        (TABLE, float("nan"), "linear", "alpha"),
        (TABLE, 0.10, "", "method"),
        (TABLE, 0.10, "no-such-method", "method"),
    ],
    ids=[
        "one-member",
        "one-column",
        "nan",
        "below-zero",
        "above-one",
        "alpha-negative",
        "alpha-half",
        "alpha-nan",
        "method-empty",
        "method-unknown",
    ],
)
def test_band_refuses_what_it_cannot_describe(
    table: npt.NDArray[np.float64], alpha: float, method: str, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        target_band(table, alpha=alpha, method=method)


def test_band_constructor_checks_its_fields() -> None:
    band = target_band(TABLE, alpha=0.10, method="linear")
    with pytest.raises(ValueError, match="lower <= upper"):
        replace(band, lower=band.upper, upper=band.lower)
    assert isinstance(band, TargetBand)
