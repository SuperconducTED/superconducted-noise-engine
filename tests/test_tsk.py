"""TSK rule firing + rule-base evaluation correctness."""

from __future__ import annotations

import numpy as np
import pytest

from superconducted.fuzzy.defuzzification import (
    NieTanDefuzzifier,
    WeightedAverageDefuzzifier,
)
from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.types import RuleFiringResult


class TestTSKRule:
    def test_firing_strength_t1_at_centers(self) -> None:
        mfs = [GaussianMF(0.0, 1.0), GaussianMF(0.0, 1.0)]
        params = np.zeros((1, 3), dtype=np.float64)
        rule = TSKRule(mfs, params)
        low, high = rule.firing_strength(np.array([0.0, 0.0]))
        assert low == pytest.approx(1.0)
        assert high == pytest.approx(1.0)
        assert low == high  # T1

    def test_firing_strength_product_tnorm(self) -> None:
        mf1 = GaussianMF(0.0, 1.0)
        mf2 = GaussianMF(0.0, 1.0)
        rule = TSKRule([mf1, mf2], np.zeros((1, 3)))
        low, _high = rule.firing_strength(np.array([1.0, 1.0]))
        expected = mf1.degree(1.0).midpoint * mf2.degree(1.0).midpoint
        assert low == pytest.approx(expected)

    def test_consequent_linear(self) -> None:
        mfs = [GaussianMF(0.0, 1.0), GaussianMF(0.0, 1.0)]
        # y = 2*x1 + 3*x2 + 5
        params = np.array([[2.0, 3.0, 5.0]], dtype=np.float64)
        rule = TSKRule(mfs, params)
        out = rule.consequent(np.array([1.0, 2.0]))
        assert out.shape == (1,)
        assert out[0] == pytest.approx(13.0)

    def test_validation_input_dim(self) -> None:
        mfs = [GaussianMF(0.0, 1.0)]
        with pytest.raises(ValueError):
            TSKRule(mfs, np.zeros((1, 3)))  # consequent expects input_dim+1=2 cols

    def test_validation_no_antecedent(self) -> None:
        with pytest.raises(ValueError):
            TSKRule([], np.zeros((1, 1)))


class TestTSKRuleBase:
    def test_evaluate_t1_shape(self) -> None:
        mf1 = GaussianMF(0.0, 1.0)
        mf2 = GaussianMF(1.0, 1.0)
        rule1 = TSKRule([mf1], np.array([[1.0, 0.0]]))
        rule2 = TSKRule([mf2], np.array([[2.0, 0.0]]))
        rb = TSKRuleBase([rule1, rule2], input_dim=1, output_dim=1)
        result = rb.evaluate(np.array([0.0]))
        assert isinstance(result, RuleFiringResult)
        assert result.n_rules == 2
        assert result.output_dim == 1
        assert not result.is_interval_type2

    def test_from_grid_cartesian_product(self) -> None:
        per_input = [
            [GaussianMF(0.0, 1.0), GaussianMF(1.0, 1.0)],
            [GaussianMF(0.0, 1.0), GaussianMF(1.0, 1.0), GaussianMF(2.0, 1.0)],
        ]
        rb = TSKRuleBase.from_grid(per_input, output_dim=2)
        assert rb.n_rules == 6
        assert rb.input_dim == 2
        assert rb.output_dim == 2

    def test_from_grid_random_init(self) -> None:
        rng = np.random.default_rng(42)
        per_input = [[GaussianMF(0.0, 1.0)] * 2]
        rb = TSKRuleBase.from_grid(per_input, output_dim=1, consequent_init="random", rng=rng)
        assert rb.n_rules == 2
        # Different rules should have different random consequents
        params0 = rb.rules[0].consequent_params
        params1 = rb.rules[1].consequent_params
        assert not np.allclose(params0, params1)

    def test_it2_path(self) -> None:
        mf = IntervalGaussianMF(center=0.0, sigma_low=0.5, sigma_high=1.0)
        rule = TSKRule([mf], np.array([[1.0, 0.0]], dtype=np.float64))
        rb = TSKRuleBase([rule], input_dim=1, output_dim=1)
        assert rb.is_interval_type2
        result = rb.evaluate(np.array([1.0]))
        assert result.is_interval_type2
        assert result.firing_strengths_lower is not None
        assert result.firing_strengths_upper is not None
        assert result.firing_strengths_lower[0] <= result.firing_strengths_upper[0]

    def test_input_shape_validation(self) -> None:
        rule = TSKRule([GaussianMF(0.0, 1.0)], np.array([[1.0, 0.0]], dtype=np.float64))
        rb = TSKRuleBase([rule], input_dim=1, output_dim=1)
        with pytest.raises(ValueError):
            rb.evaluate(np.array([1.0, 2.0]))

    def test_empty_rules_rejected(self) -> None:
        with pytest.raises(ValueError):
            TSKRuleBase([], input_dim=1, output_dim=1)


class TestDefuzzification:
    def test_weighted_average(self) -> None:
        firing = RuleFiringResult(
            firing_strengths=np.array([0.5, 0.5]),
            consequent_outputs=np.array([[1.0], [3.0]]),
            firing_strengths_lower=None,
            firing_strengths_upper=None,
        )
        result = WeightedAverageDefuzzifier().defuzzify(firing)
        assert result[0] == pytest.approx(2.0)

    def test_weighted_average_zero_firing(self) -> None:
        firing = RuleFiringResult(
            firing_strengths=np.array([0.0, 0.0]),
            consequent_outputs=np.array([[1.0], [3.0]]),
            firing_strengths_lower=None,
            firing_strengths_upper=None,
        )
        with pytest.raises(ZeroDivisionError):
            WeightedAverageDefuzzifier().defuzzify(firing)

    def test_nietan_requires_it2(self) -> None:
        firing = RuleFiringResult(
            firing_strengths=np.array([1.0]),
            consequent_outputs=np.array([[1.0]]),
            firing_strengths_lower=None,
            firing_strengths_upper=None,
        )
        with pytest.raises(ValueError):
            NieTanDefuzzifier().defuzzify(firing)

    def test_nietan_average_of_bounds(self) -> None:
        # T1-equivalent IT2 (low == high == 1) → result should be the
        # weighted average of the consequent.
        firing = RuleFiringResult(
            firing_strengths=np.array([1.0]),
            consequent_outputs=np.array([[2.5]]),
            firing_strengths_lower=np.array([1.0]),
            firing_strengths_upper=np.array([1.0]),
        )
        result = NieTanDefuzzifier().defuzzify(firing)
        assert result[0] == pytest.approx(2.5)
