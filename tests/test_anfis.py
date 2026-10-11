"""M2 trainer-core tests for Issue #60."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from superconducted.fuzzy.defuzzification import NieTanDefuzzifier, WeightedAverageDefuzzifier
from superconducted.fuzzy.membership import (
    GaussianMF,
    IntervalGaussianMF,
    TanhBellMF,
    TanhMF,
    TanhSigmoidMF,
    TrapezoidalMF,
    TriangularMF,
)
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.training import HybridANFISTrainer, TrainingSet, evaluate_rmse


def _data(features: np.ndarray, targets: np.ndarray) -> TrainingSet:
    start = datetime(2026, 10, 11, tzinfo=UTC)
    return TrainingSet(
        features=features,
        targets=targets,
        timestamps=tuple(start + timedelta(minutes=index) for index in range(features.shape[0])),
        provenance=tuple(f"row-{index}" for index in range(features.shape[0])),
        feature_names=("x0",),
        target_names=tuple(f"target-{index}" for index in range(targets.shape[1])),
        archive_ref="synthetic",
    )


def _rule_base(interval: bool, *, fitted: bool) -> TSKRuleBase:
    memberships = (
        (IntervalGaussianMF(-1.0, 0.6, 1.0) if interval else GaussianMF(-1.0, 0.8)),
        (IntervalGaussianMF(1.0, 0.6, 1.0) if interval else GaussianMF(1.0, 0.8)),
    )
    consequents = (
        np.array([[0.08, 0.20]], dtype=np.float64),
        np.array([[-0.05, 0.35]], dtype=np.float64),
    )
    if not fitted:
        consequents = (
            np.array([[0.01, 0.12]], dtype=np.float64),
            np.array([[0.01, 0.12]], dtype=np.float64),
        )
    return TSKRuleBase(
        [
            TSKRule((membership,), consequent)
            for membership, consequent in zip(memberships, consequents, strict=True)
        ],
        input_dim=1,
        output_dim=1,
    )


@pytest.mark.parametrize("interval", [False, True], ids=["t1", "it2"])
def test_lse_core_recovers_planted_targets_without_mutating_input(interval: bool) -> None:
    planted = _rule_base(interval, fitted=True)
    features = np.linspace(-1.5, 1.5, 21, dtype=np.float64)[:, None]
    defuzzifier = NieTanDefuzzifier() if interval else WeightedAverageDefuzzifier()
    targets = np.array(
        [defuzzifier.defuzzify(planted.evaluate(row)) for row in features],
        dtype=np.float64,
    )
    data = _data(features, targets)
    warm = _rule_base(interval, fitted=False)
    before = [rule.consequent_params.copy() for rule in warm.rules]
    result = HybridANFISTrainer(epochs=0, ridge=0.0).fit(warm, data)

    assert isinstance(result.rule_base, TSKRuleBase)
    assert evaluate_rmse(result.rule_base, data) == pytest.approx(np.zeros(1), abs=1e-11)
    assert result.diagnostics.zero_firing_rows_dropped == 0
    assert result.diagnostics.epochs_run == 0
    assert result.rule_base is not warm
    for rule, original in zip(warm.rules, before, strict=True):
        assert np.array_equal(rule.consequent_params, original)


def test_lse_core_rejects_an_identity_warm_start() -> None:
    rule_base = TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1)
    data = _data(np.array([[-1.0], [1.0]]), np.array([[0.1], [0.2]]))
    with pytest.raises(ValueError, match="identity damping"):
        HybridANFISTrainer().fit(rule_base, data)


def test_lse_core_reserves_positive_epochs_for_the_premise_stage() -> None:
    data = _data(np.array([[-1.0], [1.0]]), np.array([[0.1], [0.2]]))
    with pytest.raises(NotImplementedError, match="M2 trainer core"):
        HybridANFISTrainer(epochs=1).fit(_rule_base(False, fitted=False), data)


def test_lse_core_drops_zero_firing_rows_from_fit_and_metrics() -> None:
    rule_base = TSKRuleBase(
        [TSKRule((TriangularMF(-1.0, 0.0, 1.0),), np.array([[0.1, 0.2]]))],
        input_dim=1,
        output_dim=1,
    )
    data = _data(
        np.array([[-0.5], [0.0], [0.5], [2.0]]),
        np.array([[0.15], [0.2], [0.25], [0.9]]),
    )

    result = HybridANFISTrainer(ridge=0.0).fit(rule_base, data)

    assert result.diagnostics.zero_firing_rows_dropped == 1
    assert result.train_rmse == pytest.approx(np.zeros(1), abs=1e-12)


def test_lse_core_preserves_coefficient_output_layout_for_multiple_targets() -> None:
    memberships = (GaussianMF(-1.0, 0.8), GaussianMF(1.0, 0.8))
    planted = TSKRuleBase(
        [
            TSKRule((memberships[0],), np.array([[0.08, 0.20], [0.03, 0.10]])),
            TSKRule((memberships[1],), np.array([[-0.05, 0.35], [0.04, 0.15]])),
        ],
        input_dim=1,
        output_dim=2,
    )
    warm = TSKRuleBase(
        [
            TSKRule((memberships[0],), np.array([[0.01, 0.12], [0.01, 0.08]])),
            TSKRule((memberships[1],), np.array([[0.01, 0.12], [0.01, 0.08]])),
        ],
        input_dim=1,
        output_dim=2,
    )
    features = np.linspace(-1.5, 1.5, 21, dtype=np.float64)[:, None]
    defuzzifier = WeightedAverageDefuzzifier()
    data = _data(
        features,
        np.array([defuzzifier.defuzzify(planted.evaluate(row)) for row in features]),
    )

    result = HybridANFISTrainer(ridge=0.0).fit(warm, data)

    assert isinstance(result.rule_base, TSKRuleBase)
    assert evaluate_rmse(result.rule_base, data) == pytest.approx(np.zeros(2), abs=1e-11)


@pytest.mark.parametrize(
    "membership",
    [
        GaussianMF(0.0, 1.0),
        TriangularMF(-2.0, 0.0, 2.0),
        TrapezoidalMF(-2.0, -1.0, 1.0, 2.0),
        TanhMF(-1.0, 1.0, 1.0, 1.0),
        IntervalGaussianMF(0.0, 0.5, 1.0),
        TanhSigmoidMF(0.0, 1.0),
        TanhBellMF(-1.0, 1.0, 1.0),
    ],
    ids=(
        "gaussian",
        "triangular",
        "trapezoidal",
        "tanh",
        "interval-gaussian",
        "tanh-sigmoid",
        "tanh-bell",
    ),
)
def test_lse_core_maps_each_shipped_membership_shape_back_to_raw_units(membership: object) -> None:
    assert isinstance(
        membership,
        (
            GaussianMF,
            TriangularMF,
            TrapezoidalMF,
            TanhMF,
            IntervalGaussianMF,
            TanhSigmoidMF,
            TanhBellMF,
        ),
    )
    rule_base = TSKRuleBase(
        [TSKRule((membership,), np.array([[0.02, 0.2]]))],
        input_dim=1,
        output_dim=1,
    )
    features = np.array([[-0.5], [0.0], [0.5]], dtype=np.float64)
    result = HybridANFISTrainer(ridge=1e-3).fit(
        rule_base,
        _data(features, np.array([[0.15], [0.2], [0.25]])),
    )

    assert isinstance(result.rule_base, TSKRuleBase)
    mapped_membership = result.rule_base.rules[0].antecedent_mfs[0]
    for value in (-0.75, 0.0, 0.75):
        original_degree = membership.degree(value)
        mapped_degree = mapped_membership.degree(value)
        assert mapped_degree.low == pytest.approx(original_degree.low, rel=1e-9)
        assert mapped_degree.high == pytest.approx(original_degree.high, rel=1e-9)
