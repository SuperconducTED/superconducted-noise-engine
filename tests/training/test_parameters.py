"""Tests for trainable TSK parameter accounting."""

from __future__ import annotations

import pytest

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.interfaces import RuleBase
from superconducted.training import count_trainable_parameters


def test_count_trainable_parameters_deduplicates_grid_memberships() -> None:
    rule_base = TSKRuleBase.from_grid(
        [[GaussianMF(-1.0, 1.0), GaussianMF(0.0, 1.0), GaussianMF(1.0, 1.0)] for _ in range(3)],
        output_dim=2,
    )
    count = count_trainable_parameters(rule_base)
    assert count.premise == 18
    assert count.consequent == 216
    assert count.total == 234


def test_count_trainable_parameters_rejects_non_tsk_rule_bases() -> None:
    class StubRuleBase(RuleBase):
        @property
        def n_rules(self) -> int:
            return 1

        @property
        def input_dim(self) -> int:
            return 1

        @property
        def output_dim(self) -> int:
            return 1

        @property
        def is_interval_type2(self) -> bool:
            return False

        def evaluate(self, inputs: object) -> object:
            raise NotImplementedError

    with pytest.raises(TypeError, match="TSKRuleBase"):
        count_trainable_parameters(StubRuleBase())
