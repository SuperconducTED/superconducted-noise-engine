"""Tests for trainable TSK parameter accounting."""

from __future__ import annotations

import numpy as np
import pytest

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
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


def test_count_trainable_parameters_counts_unshared_memberships_individually() -> None:
    """Issue #57 section 9.1: a hand-built base sharing no MF objects.

    This is the case that distinguishes dedup-by-``id()`` from a
    "references divided by rule count" shortcut: two rules over two inputs
    give four antecedent references and four distinct ``GaussianMF``, so the
    premise count is 8 rather than 4.
    """
    rules = [
        TSKRule(
            (GaussianMF(-1.0, 1.0), GaussianMF(-1.0, 1.0)),
            np.zeros((1, 3), dtype=np.float64),
        ),
        TSKRule(
            (GaussianMF(1.0, 1.0), GaussianMF(1.0, 1.0)),
            np.zeros((1, 3), dtype=np.float64),
        ),
    ]
    rule_base = TSKRuleBase(rules, input_dim=2, output_dim=1)
    assert len({id(mf) for rule in rule_base.rules for mf in rule.antecedent_mfs}) == 4

    count = count_trainable_parameters(rule_base)
    assert count.premise == 8
    assert count.consequent == 6
    assert count.total == 14
