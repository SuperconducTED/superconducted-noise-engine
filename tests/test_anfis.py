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
    _effective_weights,
    _ensure_finite_model,
    _predict,
    _to_raw_rule_base,
    _to_standardized_rule_base,
)
from superconducted.training.parameters import count_trainable_parameters


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
