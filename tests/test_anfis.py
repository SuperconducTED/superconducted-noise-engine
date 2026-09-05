"""Fixed-premise ANFIS/LSE acceptance tests."""

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
from superconducted.training import HybridANFISTrainer, TrainingSet, premise_layout
from superconducted.types import RuleFiringResult


def _t1_base() -> TSKRuleBase:
    return TSKRuleBase.from_grid(
        [[GaussianMF(-1.0, 1.0), GaussianMF(1.0, 1.0)]],
        output_dim=1,
        consequent_init="zeros",
    )


def test_epochs_zero_recovers_planted_t1_consequents() -> None:
    base = _t1_base()
    planted = np.array([[2.0, 0.5], [-1.0, 3.0]], dtype=np.float64)
    for rule, params in zip(base.rules, planted, strict=True):
        rule.consequent_params[:] = params
    x = np.linspace(-2.0, 2.0, 25)[:, None]
    y = []
    for row in x:
        firing = base.evaluate(row)
        y.append(
            (firing.firing_strengths @ firing.consequent_outputs) / firing.firing_strengths.sum()
        )
    y = np.asarray(y)
    result = HybridANFISTrainer(epochs=0).fit(base, TrainingSet(x, y))
    assert np.all(result.train_rmse < 1e-10)
    assert result.parameter_count.premise == 4
    assert result.parameter_count.consequent == 4


def test_epochs_zero_recovers_planted_it2_nietan_consequents() -> None:
    base = TSKRuleBase.from_grid(
        [[IntervalGaussianMF(-1.0, 0.35, 0.7), IntervalGaussianMF(1.0, 0.35, 0.7)]],
        output_dim=1,
        consequent_init="zeros",
    )
    planted = np.array([[2.0, 0.5], [-1.0, 3.0]], dtype=np.float64)
    for rule, params in zip(base.rules, planted, strict=True):
        rule.consequent_params[:] = params
    features = np.linspace(-2.0, 2.0, 25)[:, None]
    targets = np.asarray([NieTanDefuzzifier().defuzzify(base.evaluate(row)) for row in features])
    result = HybridANFISTrainer(epochs=0).fit(base, TrainingSet(features, targets))
    assert np.all(result.train_rmse < 1e-10)


def test_epochs_zero_recovers_multi_output_raw_unit_predictions() -> None:
    planted = TSKRuleBase.from_grid(
        [[GaussianMF(-1.0, 1.0), GaussianMF(1.0, 1.0)]], output_dim=2, consequent_init="zeros"
    )
    parameters = np.array(
        [
            [[2.0, 0.5], [-0.5, 1.0]],
            [[-1.0, 3.0], [1.25, -2.0]],
        ]
    )
    for rule, consequent in zip(planted.rules, parameters, strict=True):
        rule.consequent_params[:] = consequent
    features = np.linspace(-1.7, 2.3, 31)[:, None]
    targets = np.asarray(
        [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(feature)) for feature in features]
    )
    initial = TSKRuleBase.from_grid(
        [[GaussianMF(-1.0, 1.0), GaussianMF(1.0, 1.0)]], output_dim=2, consequent_init="zeros"
    )
    result = HybridANFISTrainer(epochs=0).fit(initial, TrainingSet(features, targets))
    assert np.all(result.train_rmse < 1e-10)
    predictions = np.asarray(
        [
            WeightedAverageDefuzzifier().defuzzify(result.rule_base.evaluate(feature))
            for feature in features
        ]
    )
    assert np.allclose(predictions, targets, atol=1e-10)


def test_fit_does_not_mutate_input_rule_base() -> None:
    base = _t1_base()
    before = [rule.consequent_params.copy() for rule in base.rules]
    data = TrainingSet(np.array([[-1.0], [1.0]]), np.array([[1.0], [2.0]]))
    result = HybridANFISTrainer(epochs=0).fit(base, data)
    assert all(
        np.array_equal(rule.consequent_params, old)
        for rule, old in zip(base.rules, before, strict=True)
    )
    assert result.rule_base is not base


def test_premise_optimization_does_not_mutate_input_memberships() -> None:
    planted = _t1_base()
    planted.rules[0].consequent_params[:] = np.array([[1.0, -0.5]])
    planted.rules[1].consequent_params[:] = np.array([[-0.5, 1.0]])
    features = np.linspace(-2.0, 2.0, 25)[:, None]
    targets = np.asarray(
        [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(feature)) for feature in features]
    )
    initial = TSKRuleBase.from_grid([[GaussianMF(-0.25, 1.5), GaussianMF(0.25, 1.5)]], output_dim=1)
    before = [mf.parameters().copy() for mf in premise_layout(initial).mfs]
    HybridANFISTrainer(epochs=1, premise_lr=0.1, fd_step=1e-4).fit(
        initial, TrainingSet(features, targets)
    )
    after = [mf.parameters() for mf in premise_layout(initial).mfs]
    assert all(
        np.array_equal(current, original) for current, original in zip(after, before, strict=True)
    )


@pytest.mark.parametrize(
    "membership",
    [
        GaussianMF(11.0, 0.75),
        TriangularMF(8.0, 10.0, 13.0),
        TrapezoidalMF(8.0, 9.0, 11.0, 14.0),
        TanhMF(8.0, 12.0, 0.9, 1.2),
        IntervalGaussianMF(11.0, 0.5, 1.0),
        TanhSigmoidMF(10.0, 0.8),
        TanhBellMF(8.0, 12.0, 0.8),
    ],
)
def test_membership_standardization_round_trip_preserves_degree(membership: object) -> None:
    rule_base = TSKRuleBase([TSKRule([membership], np.zeros((1, 2)))], input_dim=1, output_dim=1)
    raw_feature = 10.7
    mean = np.array([10.0])
    scale = np.array([2.5])
    raw_parameters = membership.parameters().copy()
    raw_degree = membership.degree(raw_feature)
    HybridANFISTrainer._standardize_memberships(rule_base, (mean, scale))
    standardized_degree = membership.degree((raw_feature - mean[0]) / scale[0])
    assert np.allclose(
        [standardized_degree.low, standardized_degree.high], [raw_degree.low, raw_degree.high]
    )
    HybridANFISTrainer._raw_memberships(rule_base, (mean, scale))
    restored_degree = membership.degree(raw_feature)
    assert np.allclose(membership.parameters(), raw_parameters)
    assert np.allclose(
        [restored_degree.low, restored_degree.high], [raw_degree.low, raw_degree.high]
    )


def test_premise_layout_preserves_shared_objects_and_offsets() -> None:
    shared = GaussianMF(0.0, 1.0)
    rule_base = TSKRuleBase(
        [
            TSKRule([shared], np.zeros((1, 2))),
            TSKRule([shared], np.zeros((1, 2))),
        ],
        input_dim=1,
        output_dim=1,
    )
    layout = premise_layout(rule_base)
    assert layout.mfs == (shared,)
    assert layout.offsets == (0,)
    assert layout.size == 2
    assert np.array_equal(layout.flatten(), np.array([0.0, 1.0]))


def test_premise_layout_reverts_a_partially_invalid_update() -> None:
    first = GaussianMF(0.0, 1.0)
    second = GaussianMF(2.0, 1.0)
    rule_base = TSKRuleBase(
        [TSKRule([first], np.zeros((1, 2))), TSKRule([second], np.zeros((1, 2)))],
        input_dim=1,
        output_dim=1,
    )
    layout = premise_layout(rule_base)
    with pytest.raises(ValueError, match="sigma"):
        layout.set_flat(np.array([3.0, 1.0, 4.0, -1.0]))
    assert np.array_equal(first.parameters(), np.array([0.0, 1.0]))
    assert np.array_equal(second.parameters(), np.array([2.0, 1.0]))


def test_premise_layout_rejects_cross_input_sharing() -> None:
    shared = GaussianMF(0.0, 1.0)
    rule_base = TSKRuleBase(
        [TSKRule([shared, shared], np.zeros((1, 3)))],
        input_dim=2,
        output_dim=1,
    )
    with pytest.raises(ValueError, match="multiple input indices"):
        premise_layout(rule_base)


def test_finite_difference_premise_step_reduces_training_loss() -> None:
    planted = TSKRuleBase.from_grid([[GaussianMF(-1.0, 0.35), GaussianMF(1.0, 0.35)]], output_dim=1)
    for rule, params in zip(planted.rules, [[0.0, -1.0], [0.0, 1.0]], strict=True):
        rule.consequent_params[:] = params
    features = np.linspace(-2.0, 2.0, 31)[:, None]
    targets = []
    for feature in features:
        firing = planted.evaluate(feature)
        targets.append(
            (firing.firing_strengths @ firing.consequent_outputs) / firing.firing_strengths.sum()
        )
    initial = TSKRuleBase.from_grid([[GaussianMF(-0.25, 1.5), GaussianMF(0.25, 1.5)]], output_dim=1)
    data = TrainingSet(features, np.asarray(targets))
    baseline = HybridANFISTrainer(epochs=0).fit(initial, data)
    trained = HybridANFISTrainer(epochs=1, premise_lr=0.1, fd_step=1e-4).fit(initial, data)
    assert np.all(trained.train_rmse < baseline.train_rmse)
    assert all(rule.antecedent_mfs[0].parameters()[1] > 0.0 for rule in trained.rule_base.rules)


def test_premise_optimization_supports_observation_weights_and_ridge() -> None:
    planted = TSKRuleBase.from_grid([[GaussianMF(-1.0, 0.35), GaussianMF(1.0, 0.35)]], output_dim=1)
    for rule, parameters in zip(planted.rules, [[0.0, -1.0], [0.0, 1.0]], strict=True):
        rule.consequent_params[:] = parameters
    features = np.linspace(-2.0, 2.0, 31)[:, None]
    targets = np.asarray(
        [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(feature)) for feature in features]
    )
    data = TrainingSet(features, targets, weights=np.linspace(1.0, 3.0, len(features)))
    initial = TSKRuleBase.from_grid([[GaussianMF(-0.25, 1.5), GaussianMF(0.25, 1.5)]], output_dim=1)
    result = HybridANFISTrainer(epochs=1, premise_lr=0.1, ridge=0.1, fd_step=1e-4).fit(
        initial, data
    )
    assert result.diagnostics.epochs_run == 1
    assert np.isfinite(result.diagnostics.lse_condition_number)
    assert np.all(np.isfinite(result.train_rmse))
    assert all(rule.antecedent_mfs[0].parameters()[1] > 0.0 for rule in result.rule_base.rules)


def test_fit_is_deterministic_for_identical_inputs_and_configuration() -> None:
    planted = _t1_base()
    planted.rules[0].consequent_params[:] = np.array([[1.0, -0.5]])
    planted.rules[1].consequent_params[:] = np.array([[-0.5, 1.0]])
    features = np.linspace(-2.0, 2.0, 25)[:, None]
    targets = np.asarray(
        [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(feature)) for feature in features]
    )
    data = TrainingSet(features, targets)
    config = dict(epochs=1, premise_lr=0.1, fd_step=1e-4, seed=7)
    first = HybridANFISTrainer(**config).fit(_t1_base(), data)
    second = HybridANFISTrainer(**config).fit(_t1_base(), data)
    for first_rule, second_rule in zip(first.rule_base.rules, second.rule_base.rules, strict=True):
        assert np.array_equal(first_rule.consequent_params, second_rule.consequent_params)
        assert np.array_equal(
            first_rule.antecedent_mfs[0].parameters(), second_rule.antecedent_mfs[0].parameters()
        )
    assert np.array_equal(first.train_rmse, second.train_rmse)
    assert first.loss_history == second.loss_history


def test_premise_step_rejects_valid_proposals_that_worsen_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _t1_base()
    layout = premise_layout(base)
    original = layout.flatten()

    def artificial_loss(*_args: object) -> float:
        displacement = float(layout.flatten()[0] - original[0])
        if abs(displacement) < 1e-12:
            return 0.0
        if abs(displacement) <= 1e-4:
            return displacement
        return 1.0

    monkeypatch.setattr(HybridANFISTrainer, "_loss", staticmethod(artificial_loss))
    rejected = HybridANFISTrainer(premise_lr=1.0, fd_step=1e-5, max_halvings=2)._premise_step(
        layout,
        base,
        np.array([[0.0]]),
        np.array([[0.0]]),
        np.zeros((1, 2, 2)),
        TrainingSet(np.array([[0.0]]), np.array([[0.0]])),
        np.zeros((1, 2, 2)),
    )
    assert rejected == 1
    assert np.array_equal(layout.flatten(), original)


def test_validation_early_stopping_returns_the_best_premise_state() -> None:
    features = np.array([[-1.0], [0.0], [1.0]])
    targets = np.array([[-1.0], [0.0], [1.0]])
    data = TrainingSet(features, targets)
    result = HybridANFISTrainer(
        epochs=5,
        premise_lr=1e-30,
        validation=data,
        patience=1,
    ).fit(_t1_base(), data)
    assert result.diagnostics.early_stopped
    assert result.diagnostics.epochs_run == 2
    assert len(result.loss_history) == 2


def test_early_stopping_restores_the_best_validation_premise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = np.array([[-1.0], [0.0], [1.0]])
    data = TrainingSet(features, np.zeros((3, 1)))

    def advance_premise(_trainer: HybridANFISTrainer, layout: object, *_args: object) -> int:
        assert hasattr(layout, "flatten") and hasattr(layout, "set_flat")
        values = layout.flatten()
        values[0] += 1.0
        layout.set_flat(values)
        return 0

    def validation_objective(rule_base: TSKRuleBase, *_args: object) -> float:
        return float(rule_base.rules[0].antecedent_mfs[0].parameters()[0])

    monkeypatch.setattr(HybridANFISTrainer, "_premise_step", advance_premise)
    monkeypatch.setattr(HybridANFISTrainer, "_loss", staticmethod(validation_objective))
    result = HybridANFISTrainer(epochs=3, validation=data, patience=1).fit(_t1_base(), data)
    expected_center = -1.0 + np.std(features[:, 0])
    assert result.diagnostics.early_stopped
    assert result.diagnostics.epochs_run == 2
    assert result.rule_base.rules[0].antecedent_mfs[0].parameters()[0] == pytest.approx(
        expected_center
    )


def test_zero_firing_rows_are_dropped_and_counted() -> None:
    base = TSKRuleBase.from_grid([[TriangularMF(-1.0, 0.0, 1.0)]], output_dim=1)
    result = HybridANFISTrainer(epochs=0).fit(
        base,
        TrainingSet(np.array([[0.0], [10.0]]), np.array([[1.0], [2.0]])),
    )
    assert result.diagnostics.zero_firing_rows_dropped == 1
    assert np.all(np.isfinite(result.train_rmse))


def test_it2_row_with_only_one_nonzero_firing_bound_is_dropped() -> None:
    base = TSKRuleBase.from_grid(
        [[IntervalGaussianMF(0.0, 0.5, 5.0)]], output_dim=1, consequent_init="zeros"
    )
    firing = base.evaluate(np.array([100.0]))
    assert firing.firing_strengths_lower is not None
    assert firing.firing_strengths_upper is not None
    assert firing.firing_strengths_lower.sum() == 0.0
    assert firing.firing_strengths_upper.sum() > 0.0
    result = HybridANFISTrainer(epochs=0).fit(
        base,
        TrainingSet(np.array([[0.0], [100.0]]), np.array([[1.0], [2.0]])),
    )
    assert result.diagnostics.zero_firing_rows_dropped == 1


def test_validation_zero_firing_rows_are_dropped_during_early_stopping() -> None:
    base = TSKRuleBase.from_grid([[TriangularMF(-1.0, 0.0, 1.0)]], output_dim=1)
    train = TrainingSet(np.array([[0.0]]), np.array([[1.0]]))
    validation = TrainingSet(np.array([[0.0], [10.0]]), np.array([[1.0], [2.0]]))
    result = HybridANFISTrainer(epochs=1, validation=validation).fit(base, train)
    assert result.validation_rmse is not None
    assert np.all(np.isfinite(result.validation_rmse))
    assert result.diagnostics.zero_firing_rows_dropped == 1


def test_every_zero_firing_validation_row_is_rejected() -> None:
    base = TSKRuleBase.from_grid([[TriangularMF(-1.0, 0.0, 1.0)]], output_dim=1)
    train = TrainingSet(np.array([[0.0]]), np.array([[1.0]]))
    validation = TrainingSet(np.array([[10.0]]), np.array([[2.0]]))
    with pytest.raises(ValueError, match="every validation row has zero firing strength"):
        HybridANFISTrainer(epochs=1, validation=validation).fit(base, train)


@pytest.mark.parametrize(
    ("rule_base", "data", "message"),
    [
        (
            _t1_base(),
            TrainingSet(np.array([[0.0, 1.0]]), np.array([[0.0]])),
            "training feature dimension does not match rule base",
        ),
        (
            _t1_base(),
            TrainingSet(np.array([[0.0]]), np.array([[0.0, 1.0]])),
            "training target dimension does not match rule base",
        ),
        (
            TSKRuleBase.from_grid([[TriangularMF(-1.0, 0.0, 1.0)]], output_dim=1),
            TrainingSet(np.array([[10.0]]), np.array([[0.0]])),
            "every training row has zero firing strength",
        ),
    ],
)
def test_fit_rejects_invalid_training_boundaries(
    rule_base: TSKRuleBase, data: TrainingSet, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        HybridANFISTrainer().fit(rule_base, data)


def test_time_split_keeps_equal_timestamps_on_the_validation_side() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    data = TrainingSet(
        np.arange(4.0)[:, None],
        np.arange(4.0)[:, None],
        weights=np.array([1.0, 2.0, 3.0, 4.0]),
        timestamps=(
            start,
            start + timedelta(days=1),
            start + timedelta(days=1),
            start + timedelta(days=2),
        ),
    )
    train, validation = data.time_split(start + timedelta(days=1))
    assert np.array_equal(train.features[:, 0], np.array([0.0]))
    assert np.array_equal(train.weights, np.array([1.0]))
    assert np.array_equal(validation.features[:, 0], np.array([1.0, 2.0, 3.0]))
    assert validation.timestamps == (
        start + timedelta(days=1),
        start + timedelta(days=1),
        start + timedelta(days=2),
    )


def test_ridge_shrinks_consequents_toward_the_warm_start() -> None:
    base = TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1)
    warm_start = np.array([4.0, -2.0])
    base.rules[0].consequent_params[0] = warm_start
    data = TrainingSet(np.array([[-1.0], [1.0]]), np.array([[0.0], [2.0]]))
    result = HybridANFISTrainer(epochs=0, ridge=1e12).fit(base, data)
    assert np.allclose(result.rule_base.rules[0].consequent_params[0], warm_start, atol=1e-9)


def test_observation_weights_change_the_lse_optimum() -> None:
    features = np.array([[0.0], [0.0]])
    targets = np.array([[0.0], [10.0]])
    unweighted = HybridANFISTrainer(epochs=0).fit(
        TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1),
        TrainingSet(features, targets),
    )
    weighted = HybridANFISTrainer(epochs=0).fit(
        TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1),
        TrainingSet(features, targets, weights=np.array([1.0, 9.0])),
    )
    unweighted_prediction = WeightedAverageDefuzzifier().defuzzify(
        unweighted.rule_base.evaluate(np.array([0.0]))
    )
    weighted_prediction = WeightedAverageDefuzzifier().defuzzify(
        weighted.rule_base.evaluate(np.array([0.0]))
    )
    assert np.allclose(unweighted_prediction, np.array([5.0]))
    assert np.allclose(weighted_prediction, np.array([9.0]))


def test_loss_uses_observation_weights() -> None:
    rule_base = TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1)
    consequents = np.array([[[0.0, 0.0]]])
    features = np.array([[0.0], [0.0]])
    targets = np.array([[0.0], [10.0]])
    assert HybridANFISTrainer._loss(rule_base, features, targets, consequents) == pytest.approx(
        50.0
    )
    assert HybridANFISTrainer._loss(
        rule_base, features, targets, consequents, weights=np.array([9.0, 1.0])
    ) == pytest.approx(10.0)


def test_lse_condition_number_describes_the_ridge_augmented_system() -> None:
    base = TSKRuleBase.from_grid([[GaussianMF(0.0, 1.0)]], output_dim=1)
    weights = np.array([1.0, 1.0, 100.0])
    data = TrainingSet(np.array([[0.0], [1.0], [10.0]]), np.array([[0.0], [1.0], [2.0]]), weights)
    ridge = 1.0
    result = HybridANFISTrainer(epochs=0, ridge=ridge).fit(base, data)
    standardized_features, _targets, _feature_stats, _target_stats = (
        HybridANFISTrainer._standardize(data)
    )
    phi = np.column_stack([standardized_features, np.ones(data.n_rows)]) * np.sqrt(weights)[:, None]
    expected = np.linalg.cond(np.vstack([phi, np.sqrt(ridge) * np.eye(phi.shape[1])]))
    assert np.isclose(result.diagnostics.lse_condition_number, expected)


def test_nonfinite_consequent_is_rejected_before_fitting() -> None:
    base = _t1_base()
    base.rules[0].consequent_params[0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite consequent"):
        HybridANFISTrainer().fit(base, TrainingSet(np.array([[0.0]]), np.array([[0.0]])))


def test_nonfinite_membership_parameter_is_rejected_before_fitting() -> None:
    base = _t1_base()
    base.rules[0].antecedent_mfs[0].set_parameters(np.array([np.nan, 1.0]))
    with pytest.raises(ValueError, match="non-finite membership"):
        HybridANFISTrainer().fit(base, TrainingSet(np.array([[0.0]]), np.array([[0.0]])))


def test_effective_weights_match_t1_weighted_average_defuzzification() -> None:
    firing = RuleFiringResult(
        firing_strengths=np.array([2.0, 1.0]),
        consequent_outputs=np.array([[1.0, 3.0], [7.0, 9.0]]),
        firing_strengths_lower=None,
        firing_strengths_upper=None,
    )
    trainer_prediction = HybridANFISTrainer._effective_weights(firing) @ firing.consequent_outputs
    assert np.allclose(
        trainer_prediction, WeightedAverageDefuzzifier().defuzzify(firing), rtol=1e-15
    )


def test_effective_weights_match_it2_nietan_bounds_not_midpoint() -> None:
    firing = RuleFiringResult(
        firing_strengths=np.array([0.45, 0.95]),
        consequent_outputs=np.array([[1.0], [9.0]]),
        firing_strengths_lower=np.array([0.1, 0.9]),
        firing_strengths_upper=np.array([0.8, 1.0]),
    )
    trainer_prediction = HybridANFISTrainer._effective_weights(firing) @ firing.consequent_outputs
    nie_tan_prediction = NieTanDefuzzifier().defuzzify(firing)
    midpoint_prediction = (
        firing.firing_strengths @ firing.consequent_outputs / firing.firing_strengths.sum()
    )
    assert np.allclose(trainer_prediction, nie_tan_prediction, rtol=1e-15)
    assert not np.allclose(trainer_prediction, midpoint_prediction)


def test_analytic_gradient_is_explicitly_unavailable() -> None:
    with pytest.raises(NotImplementedError, match="ADR-011"):
        HybridANFISTrainer(gradient="analytic").fit(
            _t1_base(), TrainingSet(np.array([[0.0]]), np.array([[0.0]]))
        )
