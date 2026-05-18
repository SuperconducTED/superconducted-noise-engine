"""ABC instantiation + minimal-stub satisfaction tests."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import pytest
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

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
)
from superconducted.types import (
    CalibrationSnapshot,
    MembershipDegree,
    RuleFiringResult,
    SimulationResult,
)

ABCS = [
    MembershipFunction,
    CalibrationFeatureExtractor,
    FuzzificationStrategy,
    RuleBase,
    Defuzzifier,
    SquashingStrategy,
    ChannelProjector,
    NormalizationStrategy,
    BenchmarkMetric,
]


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
