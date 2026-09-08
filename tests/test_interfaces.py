"""ABC instantiation + minimal-stub satisfaction tests."""

from __future__ import annotations

import abc
import copy
import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt
import pytest
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.interfaces import (
    BenchmarkMetric,
    CalibrationFeatureExtractor,
    ChannelProjector,
    Defuzzifier,
    FuzzificationStrategy,
    MembershipFunction,
    NormalizationStrategy,
    RuleBase,
    SquashingStrategy,
    TSKTrainer,
)
from superconducted.training import TrainingResult, TrainingSet
from superconducted.training.parameters import count_trainable_parameters
from superconducted.types import (
    CalibrationSnapshot,
    MembershipDegree,
    RuleFiringResult,
    SimulationResult,
    TrainingDiagnostics,
)

ABCS = [
    MembershipFunction,
    CalibrationFeatureExtractor,
    FuzzificationStrategy,
    RuleBase,
    TSKTrainer,
    Defuzzifier,
    SquashingStrategy,
    ChannelProjector,
    NormalizationStrategy,
    BenchmarkMetric,
]


def _training_set() -> TrainingSet:
    """A minimal valid TrainingSet for trainer-contract tests."""
    stamp = datetime(2026, 9, 8, tzinfo=UTC)
    return TrainingSet(
        features=np.zeros((2, 2)),
        targets=np.zeros((2, 2)),
        timestamps=(stamp, stamp),
        provenance=("a", "b"),
        feature_names=("f0", "f1"),
        target_names=("gamma", "lambda"),
        archive_ref="test",
    )


@pytest.mark.parametrize("abc_class", ABCS)
def test_abc_cannot_be_instantiated(abc_class: type) -> None:
    with pytest.raises(TypeError):
        abc_class()  # type: ignore[abstract]


@pytest.mark.parametrize("abc_class", ABCS)
def test_abc_has_abstract_methods(abc_class: type) -> None:
    abstracts = getattr(abc_class, "__abstractmethods__", frozenset())
    assert abstracts, f"{abc_class.__name__} should declare at least one abstract method"


def test_minimal_membership_function_stub() -> None:
    class StubMF(MembershipFunction):
        def degree(self, x: float) -> MembershipDegree:
            return MembershipDegree.crisp(0.5)

        def parameters(self) -> npt.NDArray[np.float64]:
            return np.zeros(0, dtype=np.float64)

        def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
            pass

        @property
        def parameter_count(self) -> int:
            return 0

        @property
        def is_interval_type2(self) -> bool:
            return False

    instance = StubMF()
    assert instance.degree(0.0).midpoint == 0.5
    assert instance.parameter_count == 0
    assert not instance.is_interval_type2


def test_minimal_feature_extractor_stub() -> None:
    class StubExtractor(CalibrationFeatureExtractor):
        def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
            return np.zeros(1, dtype=np.float64)

        @property
        def output_dim(self) -> int:
            return 1

        @property
        def feature_names(self) -> tuple[str, ...]:
            return ("zero",)

    assert StubExtractor().output_dim == 1


def test_minimal_fuzzification_stub() -> None:
    class StubFuzz(FuzzificationStrategy):
        def install(
            self,
            circuit: QuantumCircuit,
            noise_model: NoiseModel,
            error_provider: Callable[[Instruction, tuple[int, ...]], QuantumError],
        ) -> tuple[QuantumCircuit, NoiseModel]:
            return circuit, noise_model

    StubFuzz()  # should not raise


def test_minimal_rule_base_stub() -> None:
    class StubRB(RuleBase):
        def evaluate(self, inputs: npt.NDArray[np.float64]) -> RuleFiringResult:
            return RuleFiringResult(
                firing_strengths=np.array([1.0]),
                consequent_outputs=np.array([[0.0]]),
                firing_strengths_lower=None,
                firing_strengths_upper=None,
            )

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

    StubRB()


def test_minimal_tsk_trainer_stub() -> None:
    class StubTrainer(TSKTrainer):
        def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
            raise NotImplementedError

    StubTrainer()


def test_minimal_defuzzifier_stub() -> None:
    class StubDefuzz(Defuzzifier):
        def defuzzify(self, firing: RuleFiringResult) -> npt.NDArray[np.float64]:
            return np.zeros(firing.output_dim, dtype=np.float64)

    StubDefuzz()


def test_minimal_squashing_stub() -> None:
    class StubSquash(SquashingStrategy):
        def squash(self, raw: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
            return raw

    StubSquash()


def test_minimal_channel_projector_stub() -> None:
    class StubChannel(ChannelProjector):
        def project(
            self,
            crisp_params: npt.NDArray[np.float64],
            gate_name: str,
            qubits: tuple[int, ...],
        ) -> QuantumError:
            raise NotImplementedError

    StubChannel()


def test_minimal_normalization_stub() -> None:
    class StubNorm(NormalizationStrategy):
        def normalize(
            self, kraus_ops: list[npt.NDArray[np.complex128]]
        ) -> list[npt.NDArray[np.complex128]]:
            return list(kraus_ops)

    StubNorm()


def test_minimal_benchmark_metric_stub() -> None:
    class StubMetric(BenchmarkMetric):
        @property
        def name(self) -> str:
            return "stub"

        def compute(self, engine: SimulationResult, reference: SimulationResult) -> float:
            return 0.0

    StubMetric()


def test_package_docstring_counts_match_the_exported_surface() -> None:
    """`superconducted/__init__.py` states an ABC and value-type count.

    Pinned because both drifted silently: the docstring still read "nine ABCs"
    and "four frozen-dataclass value types" after `TSKTrainer` and the four
    training types landed.
    """
    import superconducted
    from superconducted import interfaces, types

    exported_abcs = [
        getattr(interfaces, name)
        for name in dir(interfaces)
        if isinstance(getattr(interfaces, name), abc.ABCMeta)
        and getattr(interfaces, name).__module__ == interfaces.__name__
    ]
    value_types = [
        getattr(types, name)
        for name in dir(types)
        if dataclasses.is_dataclass(getattr(types, name))
        and getattr(types, name).__module__ == types.__name__
    ]
    assert len(exported_abcs) == 10
    assert len(value_types) == 8
    doc = superconducted.__doc__ or ""
    assert "ten ABCs" in doc
    assert "eight" in doc
    # Every ABC is re-exported from the package root; TSKTrainer was the one
    # that was not, while the other nine were.
    for declared in exported_abcs:
        assert declared.__name__ in superconducted.__all__
        assert getattr(superconducted, declared.__name__) is declared


def test_trainer_contract_leaves_the_caller_rule_base_unchanged_by_value() -> None:
    """Issue #57 section 9.2: the immutability round trip, compared by value.

    Identity is not the assertion. `TSKRule.consequent_params` returns the live
    internal array and `from_grid` shares one MF object across every rule that
    names it, so a mutating trainer would leave the same objects in place while
    changing what they hold. This is the template Issue #60's real trainer test
    reuses.
    """
    rule_base = TSKRuleBase.from_grid(
        [[GaussianMF(-1.0, 1.0), GaussianMF(1.0, 1.0)] for _ in range(2)], output_dim=2
    )
    consequents_before = [rule.consequent_params.copy() for rule in rule_base.rules]
    premises_before = [
        [mf.parameters().copy() for mf in rule.antecedent_mfs] for rule in rule_base.rules
    ]

    class RebuildingTrainer(TSKTrainer):
        """Minimal conforming implementation: deep-copies, never writes through."""

        def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
            if not isinstance(rule_base, TSKRuleBase):
                raise TypeError("RebuildingTrainer requires a TSKRuleBase")
            rules = [
                TSKRule(
                    copy.deepcopy(rule.antecedent_mfs),
                    np.zeros_like(rule.consequent_params),
                )
                for rule in rule_base.rules
            ]
            rebuilt = TSKRuleBase(rules, rule_base.input_dim, rule_base.output_dim)
            for rule in rebuilt.rules:
                for mf in rule.antecedent_mfs:
                    mf.set_parameters(mf.parameters() * 2.0)
            return TrainingResult(
                rule_base=rebuilt,
                train_rmse=np.zeros(rule_base.output_dim),
                validation_rmse=None,
                loss_history=(),
                diagnostics=TrainingDiagnostics(
                    clip_binding_rate=0.0,
                    zero_firing_rows_dropped=0,
                    nonfinite_rows_rejected=0,
                    lse_condition_number=1.0,
                    premise_steps_rejected=0,
                    epochs_run=0,
                    early_stopped=False,
                    standardization=(),
                ),
                parameter_count=count_trainable_parameters(rebuilt),
            )

    result = RebuildingTrainer().fit(rule_base, _training_set())

    for rule, before in zip(rule_base.rules, consequents_before, strict=True):
        assert np.array_equal(rule.consequent_params, before)
    for rule, before_row in zip(rule_base.rules, premises_before, strict=True):
        for mf, before in zip(rule.antecedent_mfs, before_row, strict=True):
            assert np.array_equal(mf.parameters(), before)

    assert result.rule_base is not rule_base
    assert result.rule_base.n_rules == rule_base.n_rules
    assert result.rule_base.input_dim == rule_base.input_dim
    assert result.rule_base.output_dim == rule_base.output_dim
    assert result.rule_base.is_interval_type2 == rule_base.is_interval_type2


def test_trainer_contract_rejects_a_non_tsk_rule_base() -> None:
    """The annotation is the ABC, so implementations narrow at runtime."""

    class RejectingTrainer(TSKTrainer):
        def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
            if not isinstance(rule_base, TSKRuleBase):
                raise TypeError("RejectingTrainer requires a TSKRuleBase")
            raise AssertionError("unreachable in this test")

    class StubRuleBase(RuleBase):
        def evaluate(self, inputs: npt.NDArray[np.float64]) -> RuleFiringResult:
            raise NotImplementedError

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

    with pytest.raises(TypeError, match="TSKRuleBase"):
        RejectingTrainer().fit(StubRuleBase(), _training_set())
