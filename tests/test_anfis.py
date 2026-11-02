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
from superconducted.integration.aer_factory import is_identity_damping
from superconducted.training import HybridANFISTrainer, TrainingSet, evaluate_rmse
from superconducted.training.anfis import (
    _ConsequentSolver,
    _effective_weights,
    _ensure_finite_model,
    _finite_difference_gradient,
    _log_space_mask,
    _predict,
    _premise_step,
    _PremiseObjective,
    _standardization,
    _to_raw_rule_base,
    _to_standardized_rule_base,
)
from superconducted.training.parameters import count_trainable_parameters, premise_layout


def _data(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    weights: np.ndarray | None = None,
) -> TrainingSet:
    start = datetime(2026, 10, 11, tzinfo=UTC)
    return TrainingSet(
        features=features,
        targets=targets,
        timestamps=tuple(start + timedelta(minutes=index) for index in range(features.shape[0])),
        provenance=tuple(f"row-{index}" for index in range(features.shape[0])),
        feature_names=tuple(f"feature-{index}" for index in range(features.shape[1])),
        target_names=tuple(f"target-{index}" for index in range(targets.shape[1])),
        archive_ref="synthetic",
        weights=weights,
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


@pytest.mark.parametrize(
    ("consequents", "identity"),
    [
        (np.array([[0.0, 0.0], [0.0, 0.0]]), True),
        (np.array([[0.1, 0.2], [0.0, 0.3]]), False),
    ],
)
def test_trainer_identity_predicate_agrees_with_channel_predicate(
    consequents: np.ndarray,
    identity: bool,
) -> None:
    rule_base = TSKRuleBase(
        [TSKRule((GaussianMF(0.0, 1.0),), consequents)],
        input_dim=1,
        output_dim=2,
    )
    data = _data(np.array([[0.0], [0.5]]), np.array([[0.1, 0.1], [0.2, 0.2]]))

    assert (
        is_identity_damping(rule_base.evaluate(np.array([0.0])).consequent_outputs[0]) is identity
    )
    if identity:
        with pytest.raises(ValueError, match="identity damping"):
            HybridANFISTrainer().fit(rule_base, data)
    else:
        HybridANFISTrainer().fit(rule_base, data)


def test_analytic_gradient_is_reserved_for_issue_61() -> None:
    data = _data(np.array([[-1.0], [1.0]]), np.array([[0.1], [0.2]]))
    with pytest.raises(NotImplementedError, match="Issue #61"):
        HybridANFISTrainer(epochs=1, gradient="analytic").fit(_rule_base(False, fitted=False), data)
    # With no premise epochs no gradient is taken, so the LSE-only fit still runs.
    result = HybridANFISTrainer(epochs=0, gradient="analytic").fit(
        _rule_base(False, fitted=False), data
    )
    assert result.diagnostics.epochs_run == 0


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
    assert isinstance(result.rule_base, TSKRuleBase)
    assert evaluate_rmse(result.rule_base, data) == pytest.approx(np.zeros(1), abs=1e-12)


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


@pytest.mark.parametrize(
    "membership",
    [
        GaussianMF(5.0, 2.0),
        TriangularMF(2.0, 5.0, 8.0),
        TrapezoidalMF(2.0, 4.0, 6.0, 8.0),
        TanhMF(4.0, 6.0, 0.8, 1.2),
        IntervalGaussianMF(5.0, 1.0, 2.0),
        TanhSigmoidMF(5.0, 0.7),
        TanhBellMF(4.0, 6.0, 0.9),
    ],
)
def test_standardization_forward_identity_and_consequent_map_back(
    membership: object,
) -> None:
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
    raw = TSKRuleBase(
        [TSKRule((membership,), np.array([[0.3, 1.2], [-0.2, 0.7]]))],
        input_dim=1,
        output_dim=2,
    )
    feature_mean = np.array([7.0])
    feature_scale = np.array([3.0])
    target_mean = np.array([0.2, -0.1])
    target_scale = np.array([2.0, 4.0])
    standardized = _to_standardized_rule_base(
        raw, feature_mean, feature_scale, target_mean, target_scale
    )
    mapped = _to_raw_rule_base(standardized, feature_mean, feature_scale, target_mean, target_scale)

    for value in (2.5, 5.0, 7.5):
        raw_degree = membership.degree(value)
        standardized_degree = (
            standardized.rules[0]
            .antecedent_mfs[0]
            .degree((value - feature_mean[0]) / feature_scale[0])
        )
        assert standardized_degree.low == pytest.approx(raw_degree.low, abs=1e-12)
        assert standardized_degree.high == pytest.approx(raw_degree.high, abs=1e-12)

        raw_output = raw.evaluate(np.array([value])).consequent_outputs[0]
        standardized_output = standardized.evaluate(
            np.array([(value - feature_mean[0]) / feature_scale[0]])
        ).consequent_outputs[0]
        assert target_scale * standardized_output + target_mean == pytest.approx(
            raw_output, abs=1e-12
        )
        assert mapped.rules[0].consequent_params == pytest.approx(
            raw.rules[0].consequent_params, abs=1e-12
        )


def _planted_grid(interval: bool, *, warm: bool) -> TSKRuleBase:
    centers = (
        np.array([98.8, 126.6, 154.4]),
        np.array([67.4, 88.95, 110.5]),
        np.array([0.0171, 0.02725, 0.0374]),
    )
    per_input_mfs = [
        [
            (
                IntervalGaussianMF(float(center), width * 0.65, width)
                if interval
                else GaussianMF(float(center), width)
            )
            for center in dimension
        ]
        for dimension, width in zip(centers, (20.0, 16.0, 0.012), strict=True)
    ]
    base = TSKRuleBase.from_grid(per_input_mfs, output_dim=2)
    generator = np.random.default_rng(42 if warm else 7)
    return TSKRuleBase(
        [
            TSKRule(
                rule.antecedent_mfs,
                generator.uniform(0.05, 0.2, size=(2, 4)).astype(np.float64),
            )
            for rule in base.rules
        ],
        input_dim=3,
        output_dim=2,
    )


def _planted_box_features() -> np.ndarray:
    """8x8x8 grid over the NC-041 [p1, p99] box, in archive units.

    Archive units are microseconds for T1 and T2 and dimensionless readout error, as
    emitted by ``ArchiveUnitFeatureExtractor`` and the feature survey. Since #66,
    ``BasicCalibrationVectorizer`` emits SI seconds instead; the trainer standardizes,
    so recovery does not depend on the unit.
    """
    coordinates = np.meshgrid(
        np.linspace(98.8, 154.4, 8),
        np.linspace(67.4, 110.5, 8),
        np.linspace(0.0171, 0.0374, 8),
        indexing="ij",
    )
    return np.column_stack([axis.ravel() for axis in coordinates])


@pytest.mark.parametrize("interval", [False, True], ids=("t1", "it2"))
def test_m2_planted_3x3x3_grid_recovers_each_consequent(interval: bool) -> None:
    planted = _planted_grid(interval, warm=False)
    warm = _planted_grid(interval, warm=True)
    defuzzifier = NieTanDefuzzifier() if interval else WeightedAverageDefuzzifier()
    features = _planted_box_features()
    data = _data(
        features,
        np.array([defuzzifier.defuzzify(planted.evaluate(row)) for row in features]),
    )

    result = HybridANFISTrainer(ridge=0.0).fit(warm, data)

    assert isinstance(result.rule_base, TSKRuleBase)
    # Compare in the standardized units the solve runs in, where a backward-stable
    # least-squares solve bounds the error by a small multiple of cond * eps. Raw units
    # divide each slope by its feature spread (0.0066 for readout error here), so a
    # raw-unit bound would depend on the planting box. Measured worst error on
    # 2026-10-15: 0.17 (T1) and 0.18 (IT2) of cond * eps * max|B|.
    feature_mean, feature_scale, target_mean, target_scale = result.diagnostics.standardization
    fitted_std = _to_standardized_rule_base(
        result.rule_base, feature_mean, feature_scale, target_mean, target_scale
    )
    planted_std = _to_standardized_rule_base(
        planted, feature_mean, feature_scale, target_mean, target_scale
    )
    got = np.stack([rule.consequent_params for rule in fitted_std.rules])
    expected = np.stack([rule.consequent_params for rule in planted_std.rules])
    bound = 8.0 * result.diagnostics.lse_condition_number * np.finfo(np.float64).eps
    assert np.max(np.abs(got - expected)) <= bound * np.max(np.abs(expected))
    assert np.max(np.abs(_predict(result.rule_base, features) - data.targets)) <= 1e-9 * np.max(
        np.abs(data.targets)
    )


@pytest.mark.parametrize("interval", [False, True], ids=("t1", "it2"))
def test_effective_weights_match_shipped_defuzzifier(interval: bool) -> None:
    rule_base = _planted_grid(interval, warm=False)
    defuzzifier = NieTanDefuzzifier() if interval else WeightedAverageDefuzzifier()

    # FR-3's bound is scale-aware: 8 eps of sum_r |w_r| |c_r|. Measured worst over this
    # grid on 2026-10-15: 3.6 eps (T1) and 2.7 eps (IT2).
    for row in _planted_box_features():
        firing = rule_base.evaluate(row)
        weights = _effective_weights(firing)
        assert weights is not None
        prediction = weights @ firing.consequent_outputs
        expected = defuzzifier.defuzzify(firing)
        scale = np.sum(np.abs(weights)[:, None] * np.abs(firing.consequent_outputs), axis=0)
        assert np.all(np.abs(prediction - expected) <= np.finfo(np.float64).eps * 8.0 * scale)


def test_it2_effective_weights_are_not_midpoint_firing_strengths() -> None:
    rule_base = _planted_grid(True, warm=False)
    firing = rule_base.evaluate(np.array([128.0, 90.0, 0.028]))
    nie_tan = NieTanDefuzzifier().defuzzify(firing)
    midpoint = (firing.firing_strengths / firing.firing_strengths.sum()) @ firing.consequent_outputs

    # The midpoint misses Nie-Tan by 1.2e-3 of max|y| at this point (measured
    # 2026-10-15); the bound sits 12x below that gap.
    assert np.max(np.abs(midpoint - nie_tan)) > 1e-4 * np.max(np.abs(nie_tan))


def test_ridge_targets_warm_start_and_weight_scale_is_invariant() -> None:
    warm = _rule_base(False, fitted=False)
    planted = _rule_base(False, fitted=True)
    features = np.linspace(-1.5, 1.5, 21, dtype=np.float64)[:, None]
    target_data = _data(
        features,
        np.array(
            [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(row)) for row in features]
        ),
    )
    near_prior = HybridANFISTrainer(ridge=1e12).fit(warm, target_data)
    weighted_one = HybridANFISTrainer(ridge=1e-2).fit(
        warm, _data(features, target_data.targets, weights=np.ones(features.shape[0]))
    )
    weighted_hundred = HybridANFISTrainer(ridge=1e-2).fit(
        warm, _data(features, target_data.targets, weights=np.full(features.shape[0], 100.0))
    )

    assert isinstance(near_prior.rule_base, TSKRuleBase)
    assert isinstance(weighted_one.rule_base, TSKRuleBase)
    assert isinstance(weighted_hundred.rule_base, TSKRuleBase)
    for fitted, prior in zip(near_prior.rule_base.rules, warm.rules, strict=True):
        assert fitted.consequent_params == pytest.approx(prior.consequent_params, abs=1e-10)
    for one, hundred in zip(
        weighted_one.rule_base.rules, weighted_hundred.rule_base.rules, strict=True
    ):
        assert one.consequent_params == pytest.approx(hundred.consequent_params, abs=1e-12)


def test_trainer_preserves_mf_sharing_values_and_parameter_count() -> None:
    rule_base = _planted_grid(False, warm=True)
    features = np.array([[110.0, 75.0, 0.02], [140.0, 103.0, 0.035]])
    data = _data(features, np.array([[0.1, 0.2], [0.2, 0.3]]))
    before = [
        membership.parameters().copy()
        for rule in rule_base.rules
        for membership in rule.antecedent_mfs
    ]
    before_consequents = [rule.consequent_params.copy() for rule in rule_base.rules]

    result = HybridANFISTrainer().fit(rule_base, data)

    assert isinstance(result.rule_base, TSKRuleBase)
    assert result.parameter_count == count_trainable_parameters(result.rule_base)
    assert result.parameter_count.premise == 18
    assert result.parameter_count.consequent == 216
    assert len({id(mf) for rule in result.rule_base.rules for mf in rule.antecedent_mfs}) == 9
    after = [
        membership.parameters() for rule in rule_base.rules for membership in rule.antecedent_mfs
    ]
    # FR-8 is by value, so exact equality, not a tolerance.
    for original, current in zip(before, after, strict=True):
        assert np.array_equal(current, original)
    for original, rule in zip(before_consequents, rule_base.rules, strict=True):
        assert np.array_equal(rule.consequent_params, original)


def test_trainer_rejects_shared_membership_at_two_input_indices() -> None:
    shared = GaussianMF(0.0, 1.0)
    rule_base = TSKRuleBase(
        [TSKRule((shared, shared), np.array([[0.1, 0.1, 0.2]]))],
        input_dim=2,
        output_dim=1,
    )
    with pytest.raises(ValueError, match="multiple input indices"):
        HybridANFISTrainer().fit(
            rule_base,
            _data(np.array([[0.0, 0.0], [0.5, 0.5]]), np.array([[0.1], [0.2]])),
        )


def test_trainer_is_deterministic_and_accepts_constant_feature_columns() -> None:
    rule_base = TSKRuleBase(
        [
            TSKRule(
                (GaussianMF(-1.0, 1.0), GaussianMF(4.0, 1.0)),
                np.array([[0.1, 0.0, 0.2]]),
            ),
            TSKRule(
                (GaussianMF(1.0, 1.0), GaussianMF(4.0, 1.0)),
                np.array([[0.05, 0.0, 0.25]]),
            ),
        ],
        input_dim=2,
        output_dim=1,
    )
    data = _data(
        np.array([[-1.0, 4.0], [0.0, 4.0], [1.0, 4.0]]),
        np.array([[0.1], [0.2], [0.3]]),
    )

    first = HybridANFISTrainer(ridge=0.0).fit(rule_base, data)
    second = HybridANFISTrainer(ridge=0.0).fit(rule_base, data)

    # FR-14 asks for bit-identical results, so exact equality throughout.
    assert np.array_equal(first.train_rmse, second.train_rmse)
    assert first.loss_history == second.loss_history
    assert isinstance(first.rule_base, TSKRuleBase)
    assert isinstance(second.rule_base, TSKRuleBase)
    for left, right in zip(first.rule_base.rules, second.rule_base.rules, strict=True):
        assert np.array_equal(left.consequent_params, right.consequent_params)


def test_it2_zero_firing_is_dropped_and_all_dropped_raises() -> None:
    rule_base = TSKRuleBase(
        [
            TSKRule(
                (IntervalGaussianMF(0.0, 0.2, 0.4),),
                np.array([[0.1, 0.2]]),
            )
        ],
        input_dim=1,
        output_dim=1,
    )
    data = _data(
        np.array([[0.0], [20.0]]),
        np.array([[0.2], [0.9]]),
    )
    result = HybridANFISTrainer().fit(rule_base, data)
    assert result.diagnostics.zero_firing_rows_dropped == 1
    with pytest.raises(ValueError, match="all training rows have zero firing strength"):
        HybridANFISTrainer().fit(
            rule_base,
            _data(np.array([[20.0], [21.0]]), np.array([[0.9], [0.8]])),
        )


def test_diagnostics_report_clip_condition_and_validation_metrics() -> None:
    rule_base = _rule_base(False, fitted=False)
    train = _data(np.array([[-1.0], [1.0]]), np.array([[1.5], [1.7]]))
    validation = _data(np.array([[-0.5], [0.5]]), np.array([[1.6], [1.8]]))

    result = HybridANFISTrainer(ridge=0.0, validation=validation).fit(rule_base, train)

    assert result.diagnostics.clip_binding_rate == 1.0
    assert result.diagnostics.lse_condition_number > 0.0
    assert result.validation_rmse is not None
    assert result.validation_rmse == pytest.approx(evaluate_rmse(result.rule_base, validation))
    feature_mean, feature_scale, target_mean, target_scale = result.diagnostics.standardization
    standardized = _to_standardized_rule_base(
        result.rule_base, feature_mean, feature_scale, target_mean, target_scale
    )
    standardized_features = (train.features - feature_mean) / feature_scale
    standardized_targets = (train.targets - target_mean) / target_scale
    expected_loss = np.mean(
        np.sum((_predict(standardized, standardized_features) - standardized_targets) ** 2, axis=1)
    )
    assert result.loss_history[0] == pytest.approx(expected_loss)


def _standardized_design(
    standardized: TSKRuleBase, standardized_features: np.ndarray
) -> np.ndarray:
    """T1 design matrix built from firing strengths, independent of the trainer's helpers."""
    rows = []
    for row in standardized_features:
        strengths = standardized.evaluate(row).firing_strengths
        rows.append(np.kron(strengths / strengths.sum(), np.append(row, 1.0)))
    return np.array(rows)


def test_weighted_finite_ridge_fit_matches_closed_form() -> None:
    warm = _rule_base(False, fitted=False)
    planted = _rule_base(False, fitted=True)
    features = np.linspace(-1.5, 1.5, 21, dtype=np.float64)[:, None]
    targets = np.array(
        [WeightedAverageDefuzzifier().defuzzify(planted.evaluate(row)) for row in features]
    ) + 0.01 * np.sin(7.0 * features)
    weights = np.random.default_rng(3).uniform(0.2, 3.0, size=features.shape[0])
    ridge = 0.3

    result = HybridANFISTrainer(ridge=ridge).fit(warm, _data(features, targets, weights=weights))

    feature_mean, feature_scale = features.mean(axis=0), features.std(axis=0)
    target_mean, target_scale = targets.mean(axis=0), targets.std(axis=0)
    standardized_warm = _to_standardized_rule_base(
        warm, feature_mean, feature_scale, target_mean, target_scale
    )
    design = _standardized_design(standardized_warm, (features - feature_mean) / feature_scale)
    prior = np.concatenate([rule.consequent_params.T for rule in standardized_warm.rules])
    row_weights = np.diag(weights / weights.mean())
    residual = (targets - target_mean) / target_scale - design @ prior
    closed_form = prior + np.linalg.solve(
        design.T @ row_weights @ design + ridge * np.eye(design.shape[1]),
        design.T @ row_weights @ residual,
    )
    assert isinstance(result.rule_base, TSKRuleBase)
    fitted = _to_standardized_rule_base(
        result.rule_base, feature_mean, feature_scale, target_mean, target_scale
    )
    got = np.concatenate([rule.consequent_params.T for rule in fitted.rules])
    assert got == pytest.approx(closed_form, abs=1e-10)


def test_loss_history_and_condition_number_are_pinned_for_two_outputs() -> None:
    memberships = (GaussianMF(-1.0, 0.8), GaussianMF(1.0, 0.8))
    rule_base = TSKRuleBase(
        [
            TSKRule((memberships[0],), np.array([[0.01, 0.12], [0.01, 0.08]])),
            TSKRule((memberships[1],), np.array([[0.01, 0.12], [0.01, 0.08]])),
        ],
        input_dim=1,
        output_dim=2,
    )
    features = np.linspace(-1.5, 1.5, 9, dtype=np.float64)[:, None]
    targets = np.column_stack(
        [0.1 + 0.05 * np.sin(3.0 * features[:, 0]), 0.2 + 0.08 * np.cos(2.0 * features[:, 0])]
    )

    result = HybridANFISTrainer(ridge=0.0).fit(rule_base, _data(features, targets))

    feature_mean, feature_scale = features.mean(axis=0), features.std(axis=0)
    target_mean, target_scale = targets.mean(axis=0), targets.std(axis=0)
    assert isinstance(result.rule_base, TSKRuleBase)
    standardized = _to_standardized_rule_base(
        result.rule_base, feature_mean, feature_scale, target_mean, target_scale
    )
    standardized_features = (features - feature_mean) / feature_scale
    design = _standardized_design(standardized, standardized_features)
    assert result.diagnostics.lse_condition_number == pytest.approx(
        np.linalg.cond(design), rel=1e-6
    )
    residual = (
        _predict(standardized, standardized_features) - (targets - target_mean) / target_scale
    )
    # Section 6.4: mean over rows of the squared norm over outputs (not over rows * outputs).
    expected_loss = np.mean(np.sum(residual**2, axis=1))
    assert expected_loss > 0.0
    assert result.loss_history[0] == pytest.approx(expected_loss, rel=1e-9)


@pytest.mark.parametrize(
    ("membership", "consequent", "message"),
    [
        (GaussianMF(0.0, 1.0), np.array([[np.nan, 0.1]]), "non-finite consequent"),
        (GaussianMF(float("nan"), 1.0), np.array([[0.1, 0.2]]), "non-finite parameters"),
    ],
    ids=("consequent", "membership"),
)
def test_nonfinite_warm_start_is_refused_naming_the_input(
    membership: GaussianMF, consequent: np.ndarray, message: str
) -> None:
    rule_base = TSKRuleBase([TSKRule((membership,), consequent)], input_dim=1, output_dim=1)
    with pytest.raises(ValueError, match=f"warm-start rule 0 has .*{message}"):
        HybridANFISTrainer().fit(
            rule_base, _data(np.array([[0.0], [0.5]]), np.array([[0.1], [0.2]]))
        )


def test_nonfinite_prediction_guard_raises_before_result_construction() -> None:
    rule_base = _rule_base(False, fitted=False)
    with pytest.raises(ValueError, match="non-finite outputs"):
        _ensure_finite_model(
            rule_base,
            ((np.array([[np.nan]]), np.array([True])),),
        )


# --- M3: premise stage, alternation and early stopping (Issue #60 FR-5, FR-6) ---

_LINE_CENTERS = (-1.0, 0.0, 1.0)
_LINE_WIDTHS = (0.45, 0.45, 0.45)
# The warm start shifts each centre by (0.12, -0.10, 0.08) and scales each width by
# (1.2, 0.85, 1.15): the perturbation pattern of Issue #60 step 6(b).
_LINE_WARM_CENTERS = (-0.88, -0.10, 1.08)
_LINE_WARM_WIDTHS = (0.54, 0.3825, 0.5175)
_LINE_CONSEQUENTS = (((0.6, -0.4),), ((-0.8, 0.3),), ((0.5, 0.9),))


def _line(
    interval: bool,
    centers: tuple[float, ...],
    widths: tuple[float, ...],
    consequents: tuple[tuple[tuple[float, float]], ...],
) -> TSKRuleBase:
    """Three rules on one input; an IT2 lower width is 0.65 of the upper, as in _planted_grid."""
    return TSKRuleBase(
        [
            TSKRule(
                (IntervalGaussianMF(c, 0.65 * w, w) if interval else GaussianMF(c, w),),
                np.array(consequent, dtype=np.float64),
            )
            for c, w, consequent in zip(centers, widths, consequents, strict=True)
        ],
        input_dim=1,
        output_dim=1,
    )


def _planted_line(interval: bool) -> TSKRuleBase:
    return _line(interval, _LINE_CENTERS, _LINE_WIDTHS, _LINE_CONSEQUENTS)


def _warm_line(interval: bool) -> TSKRuleBase:
    return _line(interval, _LINE_WARM_CENTERS, _LINE_WARM_WIDTHS, (((0.1, 0.1),),) * 3)


def _targets_of(rule_base: TSKRuleBase, features: np.ndarray) -> np.ndarray:
    defuzzifier = (
        NieTanDefuzzifier() if rule_base.is_interval_type2 else WeightedAverageDefuzzifier()
    )
    return np.array([defuzzifier.defuzzify(rule_base.evaluate(row)) for row in features])


def _line_data(rule_base: TSKRuleBase, rows: int = 41, span: float = 1.5) -> TrainingSet:
    features = np.linspace(-span, span, rows, dtype=np.float64)[:, None]
    return _data(features, _targets_of(rule_base, features))


def _standardized_premise(result_rule_base: object, standardization: tuple) -> np.ndarray:
    assert isinstance(result_rule_base, TSKRuleBase)
    return premise_layout(_to_standardized_rule_base(result_rule_base, *standardization)).flatten()


def _consequents(rule_base: object) -> np.ndarray:
    assert isinstance(rule_base, TSKRuleBase)
    return np.stack([rule.consequent_params for rule in rule_base.rules])


def test_log_space_mask_marks_exactly_each_shapes_positive_entries() -> None:
    rule_base = TSKRuleBase(
        [
            TSKRule(
                (
                    GaussianMF(0.0, 1.0),
                    TriangularMF(-2.0, 0.0, 2.0),
                    TrapezoidalMF(-2.0, -1.0, 1.0, 2.0),
                    TanhMF(-1.0, 1.0, 1.0, 1.0),
                    IntervalGaussianMF(0.0, 0.5, 1.0),
                    TanhSigmoidMF(0.0, 1.0),
                    TanhBellMF(-1.0, 1.0, 1.0),
                ),
                np.full((1, 8), 0.1),
            )
        ],
        input_dim=7,
        output_dim=1,
    )

    mask = _log_space_mask(premise_layout(rule_base))

    expected = [
        *(False, True),  # Gaussian: sigma
        *(False, False, False),  # Triangular: ordering only
        *(False, False, False, False),  # Trapezoidal: ordering only
        *(False, False, True, True),  # Tanh: both slopes
        *(False, True, True),  # Interval Gaussian: both sigmas
        *(False, True),  # Tanh sigmoid: slope
        *(False, False, True),  # Tanh bell: slope
    ]
    assert mask.tolist() == expected


@pytest.mark.parametrize("interval", [False, True], ids=("t1", "it2"))
@pytest.mark.parametrize("weighted_ridge", [False, True], ids=("plain", "weighted-ridge"))
def test_premise_gradient_is_the_gradient_of_the_resolved_loss(
    interval: bool, weighted_ridge: bool
) -> None:
    """The fixed-consequent gradient equals the re-solved loss's gradient (envelope theorem).

    The reference differentiates in raw parameter space, re-solving the consequents at
    every point, and applies the log-space chain rule itself, so it checks the
    reparameterization as well as the difference quotient. The ridge penalty does not
    depend on the premise, so the identity holds with row weights and ridge as well.
    """
    data = _line_data(_planted_line(interval))
    feature_mean, feature_scale = _standardization(data.features)
    target_mean, target_scale = _standardization(data.targets)
    standardized = _to_standardized_rule_base(
        _warm_line(interval), feature_mean, feature_scale, target_mean, target_scale
    )
    features = (data.features - feature_mean) / feature_scale
    targets = (data.targets - target_mean) / target_scale
    layout = premise_layout(standardized)
    weights = (
        np.random.default_rng(3).uniform(0.2, 3.0, size=features.shape[0])
        if weighted_ridge
        else None
    )
    ridge = 0.3 if weighted_ridge else 0.0
    solve = _ConsequentSolver(standardized, layout, features, targets, weights, ridge)
    solved = solve(layout.flatten())
    assert solved is not None
    current, _ = solved
    log_mask = _log_space_mask(layout)
    objective = _PremiseObjective(
        layout,
        features,
        targets,
        np.ones(features.shape[0]) if weights is None else weights / weights.mean(),
    )

    gradient = _finite_difference_gradient(
        objective, current.rule_base, current.premise, log_mask, 6e-6
    )
    # The perturbations are undone: the live MFs hold the premise again, exactly.
    assert np.array_equal(layout.flatten(), current.premise)

    def resolved_loss(premise: np.ndarray) -> float:
        result = solve(premise)
        assert result is not None
        # The score sums over rows where the objective averages, hence the division.
        return result[1] / features.shape[0]

    expected = np.empty_like(gradient)
    for index, value in enumerate(current.premise):
        step = 1e-6 * max(1.0, abs(value))
        plus, minus = current.premise.copy(), current.premise.copy()
        plus[index] += step
        minus[index] -= step
        slope = (resolved_loss(plus) - resolved_loss(minus)) / (plus[index] - minus[index])
        expected[index] = slope * value if log_mask[index] else slope
    assert np.all(expected != 0.0)
    # Measured on 2026-10-18: 4.1e-9 (T1) and 8.3e-10 (IT2) of max|grad|.
    assert np.max(np.abs(gradient - expected)) <= 1e-6 * np.max(np.abs(expected))


def test_consequent_solver_score_is_the_ridge_objective_it_minimizes() -> None:
    data = _line_data(_planted_line(False))
    weights = np.random.default_rng(5).uniform(0.2, 3.0, size=data.features.shape[0])
    standardized = _warm_line(False)
    layout = premise_layout(standardized)
    ridge = 0.7

    solved = _ConsequentSolver(standardized, layout, data.features, data.targets, weights, ridge)(
        layout.flatten()
    )

    assert solved is not None
    candidate, score = solved
    design = _standardized_design(standardized, data.features)
    theta = np.concatenate([rule.consequent_params.T for rule in candidate.rule_base.rules])
    prior = np.concatenate([rule.consequent_params.T for rule in standardized.rules])
    normalized = weights / weights.mean()
    expected = float(
        np.sum(normalized * np.sum((design @ theta - data.targets) ** 2, axis=1))
        + ridge * np.sum((theta - prior) ** 2)
    )
    assert score == pytest.approx(expected, rel=1e-12)
    assert np.array_equal(candidate.premise, layout.flatten())


def test_premise_step_halves_past_an_ordering_constraint_and_counts_exhaustion() -> None:
    membership = TriangularMF(0.0, 1.0, 2.0)
    attempts: list[np.ndarray] = []

    def solve(candidate: np.ndarray) -> tuple[str, float] | None:
        attempts.append(candidate.copy())
        try:
            membership.set_parameters(candidate[:3])
        except ValueError:
            return None
        return "solved", -float(candidate[1])  # every valid move of b to the right descends

    # The fourth entry is a log-space parameter with a zero gradient. exp(log(0.1)) is
    # not exactly 0.1 in float64, so it also shows the entry skips the round trip.
    premise = np.array([0.0, 1.0, 2.0, 0.1])
    gradient = np.array([0.0, -1.0, 0.0, 0.0])
    log_mask = np.array([False, False, False, True])
    assert np.exp(np.log(0.1)) != 0.1

    step = _premise_step(solve, premise, -1.0, gradient, log_mask, 2.0, 2)  # type: ignore[arg-type]

    # b = 3 and b = 2 break a < b < c; the second halving lands inside the domain.
    assert [float(attempt[1]) for attempt in attempts] == [3.0, 2.0, 1.5]
    assert step is not None
    assert step[1] == -1.5
    # Entries with a zero gradient keep their exact values on every attempt.
    assert all(
        attempt[0] == 0.0 and attempt[2] == 2.0 and attempt[3] == 0.1 for attempt in attempts
    )

    attempts.clear()
    assert _premise_step(solve, premise, -1.0, gradient, log_mask, 2.0, 1) is None  # type: ignore[arg-type]
    assert [float(attempt[1]) for attempt in attempts] == [3.0, 2.0]


def test_premise_step_rejects_a_step_that_does_not_lower_the_resolved_loss() -> None:
    attempts: list[float] = []

    def solve(candidate: np.ndarray) -> tuple[str, float]:
        attempts.append(float(candidate[0]))
        return "solved", 1.0  # valid, but never below the current score

    step = _premise_step(
        solve,  # type: ignore[arg-type]
        np.array([0.0]),
        1.0,
        np.array([-1.0]),
        np.zeros(1, dtype=np.bool_),
        4.0,
        3,
    )

    assert step is None
    assert attempts == [4.0, 2.0, 1.0, 0.5]


def test_consequent_solver_refuses_premises_outside_the_losss_domain() -> None:
    rule_base = TSKRuleBase(
        [
            TSKRule((TriangularMF(-1.0, 0.0, 1.0),), np.array([[0.1, 0.2]])),
            TSKRule((TriangularMF(0.0, 1.0, 2.0),), np.array([[0.0, 0.3]])),
        ],
        input_dim=1,
        output_dim=1,
    )
    layout = premise_layout(rule_base)
    features = np.array([[-0.5], [0.5], [1.5]])
    solve = _ConsequentSolver(
        rule_base, layout, features, np.array([[0.1], [0.3], [0.2]]), None, 0.0
    )
    premise = layout.flatten()
    assert solve(premise) is not None

    unfired = premise.copy()
    unfired[3:] = [0.0, 1.0, 1.2]  # the row at 1.5 now lies outside both supports
    misordered = premise.copy()
    misordered[:3] = [0.0, 2.0, 1.0]
    nonfinite = premise.copy()
    nonfinite[1] = np.nan
    for candidate in (unfired, misordered, nonfinite):
        assert solve(candidate) is None


@pytest.mark.parametrize("interval", [False, True], ids=("t1", "it2"))
def test_planted_line_premise_training_descends_and_improves_out_of_sample(
    interval: bool,
) -> None:
    """Issue #60 step 6(b) on one input: what plain gradient descent recovers in 60 epochs.

    The planted premise is identifiable but ill-conditioned (normalized Gaussian weights
    let the consequents absorb most premise error), so the soft directions move slowly;
    the 3x3x3 recorded run in the implementation doc measures the same effect.
    """
    planted = _planted_line(interval)
    warm = _warm_line(interval)
    data = _line_data(planted)
    held_out = np.linspace(-1.45, 1.45, 30)[:, None]
    held_out_targets = _targets_of(planted, held_out)

    lse_only = HybridANFISTrainer(ridge=0.0).fit(warm, data)
    result = HybridANFISTrainer(epochs=60, premise_lr=50.0, ridge=0.0).fit(warm, data)

    history = np.array(result.loss_history)
    assert history.shape == (61,)
    assert history[0] == lse_only.loss_history[0]
    assert np.all(np.diff(history) < 0.0)
    assert result.diagnostics.epochs_run == 60
    assert not result.diagnostics.early_stopped
    assert result.diagnostics.premise_steps_rejected == 0
    standardization = result.diagnostics.standardization
    truth = _standardized_premise(planted, standardization)
    start = _standardized_premise(warm, standardization)
    trained = _standardized_premise(result.rule_base, standardization)
    assert isinstance(lse_only.rule_base, TSKRuleBase)
    assert isinstance(result.rule_base, TSKRuleBase)
    lse_error = np.max(np.abs(_predict(lse_only.rule_base, held_out) - held_out_targets))
    trained_error = np.max(np.abs(_predict(result.rule_base, held_out) - held_out_targets))
    # Measured on 2026-10-18 (T1 / IT2): final over initial loss 4.9e-3 / 1.9e-3; premise
    # distance to the planted one 0.65 / 0.75 of the warm start's (standardized units);
    # held-out max error 0.060 / 0.033 of the LSE-only fit's. Single soft entries can
    # still drift away (one T1 width goes from 0.076 to 0.112), so only the norm is pinned.
    assert history[-1] <= 1e-2 * history[0]
    assert np.linalg.norm(trained - truth) <= 0.9 * np.linalg.norm(start - truth)
    assert trained_error <= 0.2 * lse_error


@pytest.mark.parametrize("interval", [False, True], ids=("t1", "it2"))
@pytest.mark.parametrize("validation_premise", ["halfway", "warm"])
def test_early_stopping_returns_the_best_validation_state(
    interval: bool, validation_premise: str
) -> None:
    """The returned state is the one ``patience`` epochs before the stop, bit for bit.

    The validation targets come from a model whose premise is halfway between the warm
    start and the planted one (best epoch mid-run) or equal to the warm start (best
    epoch 0); in both cases training on planted targets eventually moves away from it.
    """
    if validation_premise == "halfway":
        centers = tuple(
            0.5 * (a + b) for a, b in zip(_LINE_CENTERS, _LINE_WARM_CENTERS, strict=True)
        )
        widths = tuple(0.5 * (a + b) for a, b in zip(_LINE_WIDTHS, _LINE_WARM_WIDTHS, strict=True))
    else:
        centers, widths = _LINE_WARM_CENTERS, _LINE_WARM_WIDTHS
    validation = _line_data(_line(interval, centers, widths, _LINE_CONSEQUENTS), rows=15, span=1.4)
    data = _line_data(_planted_line(interval))
    warm = _warm_line(interval)
    patience = 3

    result = HybridANFISTrainer(
        epochs=60, premise_lr=50.0, ridge=0.0, validation=validation, patience=patience
    ).fit(warm, data)

    assert result.diagnostics.early_stopped
    best_epoch = result.diagnostics.epochs_run - patience
    assert len(result.loss_history) == result.diagnostics.epochs_run + 1
    if validation_premise == "halfway":
        assert best_epoch > 0
    else:
        assert best_epoch == 0
    replay = HybridANFISTrainer(epochs=best_epoch, premise_lr=50.0, ridge=0.0).fit(warm, data)
    standardization = result.diagnostics.standardization
    assert np.array_equal(
        _standardized_premise(result.rule_base, standardization),
        _standardized_premise(replay.rule_base, standardization),
    )
    assert np.array_equal(_consequents(result.rule_base), _consequents(replay.rule_base))
    assert np.array_equal(result.train_rmse, replay.train_rmse)
    assert result.loss_history[: best_epoch + 1] == replay.loss_history
    assert result.validation_rmse is not None
    assert result.validation_rmse == pytest.approx(
        evaluate_rmse(result.rule_base, validation), rel=1e-12
    )


def test_training_without_validation_runs_every_epoch_deterministically() -> None:
    data = _line_data(_planted_line(False))
    warm = _warm_line(False)

    three = HybridANFISTrainer(epochs=3, premise_lr=50.0).fit(warm, data)
    three_again = HybridANFISTrainer(epochs=3, premise_lr=50.0).fit(warm, data)
    five = HybridANFISTrainer(epochs=5, premise_lr=50.0).fit(warm, data)

    assert three.diagnostics.epochs_run == 3
    assert not three.diagnostics.early_stopped
    assert len(three.loss_history) == 4
    # FR-14: bit-identical, so exact equality throughout.
    assert three.loss_history == three_again.loss_history
    assert np.array_equal(_consequents(three.rule_base), _consequents(three_again.rule_base))
    assert np.array_equal(
        premise_layout(three.rule_base).flatten(),  # type: ignore[arg-type]
        premise_layout(three_again.rule_base).flatten(),  # type: ignore[arg-type]
    )
    # The loop is a deterministic sequence, so a shorter run is a prefix of a longer one.
    assert five.loss_history[:4] == three.loss_history


def test_premise_training_keeps_grid_sharing_and_the_callers_values() -> None:
    planted = _planted_grid(False, warm=False)
    warm = _planted_grid(False, warm=True)
    coordinates = np.meshgrid(
        np.linspace(98.8, 154.4, 3),
        np.linspace(67.4, 110.5, 3),
        np.linspace(0.0171, 0.0374, 3),
        indexing="ij",
    )
    features = np.column_stack([axis.ravel() for axis in coordinates])
    data = _data(features, _targets_of(planted, features))
    before_mfs = [mf.parameters().copy() for mf in premise_layout(warm).mfs]
    before_consequents = _consequents(warm).copy()

    result = HybridANFISTrainer(epochs=1, premise_lr=1.0).fit(warm, data)

    assert isinstance(result.rule_base, TSKRuleBase)
    for mf, original in zip(premise_layout(warm).mfs, before_mfs, strict=True):
        assert np.array_equal(mf.parameters(), original)
    assert np.array_equal(_consequents(warm), before_consequents)
    layout = premise_layout(result.rule_base)
    assert len(layout.mfs) == 9
    assert result.parameter_count == count_trainable_parameters(result.rule_base)
    assert result.parameter_count.premise == layout.size == 18
    assert not {id(mf) for mf in layout.mfs} & {id(mf) for mf in premise_layout(warm).mfs}
    standardization = result.diagnostics.standardization
    assert not np.array_equal(
        _standardized_premise(result.rule_base, standardization),
        _standardized_premise(warm, standardization),
    )


def test_premise_free_rule_base_takes_no_step_and_counts_no_rejection() -> None:
    # With one rule the normalized weight is exactly 1, so the loss does not depend on
    # the premise and every finite difference is exactly zero.
    rule_base = TSKRuleBase(
        [TSKRule((GaussianMF(0.0, 1.0),), np.array([[0.1, 0.2]]))], input_dim=1, output_dim=1
    )
    data = _data(np.linspace(-1.0, 1.0, 5)[:, None], np.linspace(0.1, 0.3, 5)[:, None] ** 2)

    result = HybridANFISTrainer(epochs=3, premise_lr=1.0).fit(rule_base, data)

    assert result.diagnostics.premise_steps_rejected == 0
    assert result.diagnostics.epochs_run == 3
    assert len(set(result.loss_history)) == 1
    assert isinstance(result.rule_base, TSKRuleBase)
    assert result.rule_base.rules[0].antecedent_mfs[0].parameters() == pytest.approx(
        [0.0, 1.0], abs=1e-15
    )


def test_oversized_learning_rate_is_halved_or_counted_never_diverges() -> None:
    data = _line_data(_planted_line(False))
    warm = _warm_line(False)

    lse_only = HybridANFISTrainer().fit(warm, data)
    exhausted = HybridANFISTrainer(epochs=2, premise_lr=1e9, max_halvings=2).fit(warm, data)
    uphill = HybridANFISTrainer(epochs=1, premise_lr=1e3, max_halvings=0).fit(warm, data)
    halved = HybridANFISTrainer(epochs=2, premise_lr=1e9, max_halvings=40).fit(warm, data)

    # Two halvings leave the rate near 2.5e8: every attempt is rejected, the state stays
    # at the LSE-only fit, and the exhaustion is counted rather than raised.
    assert exhausted.diagnostics.premise_steps_rejected == 2
    assert exhausted.loss_history == (lse_only.loss_history[0],) * 3
    # At 1e3 the trial premise is valid but raises the re-solved loss, so the step is
    # rejected after the trial was written into the MFs; the state must still be the
    # LSE-only fit, bit for bit.
    assert uphill.diagnostics.premise_steps_rejected == 1
    assert uphill.loss_history == (lse_only.loss_history[0],) * 2
    assert np.array_equal(_consequents(uphill.rule_base), _consequents(lse_only.rule_base))
    assert halved.diagnostics.premise_steps_rejected == 0
    assert halved.loss_history[2] < halved.loss_history[1] < halved.loss_history[0]


def test_rows_dropped_at_the_warm_start_stay_dropped_through_premise_epochs() -> None:
    rule_base = TSKRuleBase(
        [
            TSKRule((TriangularMF(-1.0, 0.0, 1.0),), np.array([[0.1, 0.2]])),
            TSKRule((TriangularMF(-0.2, 0.6, 1.4),), np.array([[0.05, 0.25]])),
        ],
        input_dim=1,
        output_dim=1,
    )
    features = np.array([[-0.6], [-0.3], [0.0], [0.3], [0.6], [0.9], [3.0]])
    data = _data(features, 0.2 + 0.1 * np.sin(2.0 * features))

    result = HybridANFISTrainer(epochs=3, premise_lr=0.1).fit(rule_base, data)

    assert result.diagnostics.zero_firing_rows_dropped == 1
    assert result.diagnostics.epochs_run == 3
    assert result.train_rmse == pytest.approx(
        evaluate_rmse(result.rule_base, _data(features[:-1], data.targets[:-1])), rel=1e-12
    )
