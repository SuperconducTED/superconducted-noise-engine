"""Abstract base classes for SuperconducTED's swappable design axes.

Each ABC corresponds to one open decision recorded in CLAUDE.md and
``docs/decisions.md``. The TSK inference math (in
:mod:`superconducted.fuzzy.tsk`) is concrete and locked; the Aer
Factory/Ensemble integration pattern is also concrete and locked (in
:mod:`superconducted.integration.aer_factory`). Everything else swaps
through these contracts.
"""

from __future__ import annotations

import abc
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from .types import CalibrationSnapshot, MembershipDegree, RuleFiringResult, SimulationResult


class MembershipFunction(abc.ABC):
    """Fuzzy membership function over a single scalar input.

    Implementations cover the open decision on MF shape (Gaussian, triangular,
    trapezoidal, tanh-based, IT2 variants — see ADR-006). All implementations
    return :class:`MembershipDegree`: T1 implementations produce degenerate
    (``low == high``) degrees, IT2 implementations produce non-degenerate
    ones.

    Trainable parameters are exposed as a flat 1-D ``float64`` vector for the
    hybrid LSE/SGD ANFIS trainer that lives in
    :mod:`superconducted.fuzzy.tsk` (deferred to ADR-014).
    """

    @abc.abstractmethod
    def degree(self, x: float) -> MembershipDegree:
        """Return the membership degree at scalar input ``x``."""

    @abc.abstractmethod
    def parameters(self) -> npt.NDArray[np.float64]:
        """Return trainable parameters as a 1-D ``float64`` array."""

    @abc.abstractmethod
    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        """Replace trainable parameters from a 1-D ``float64`` array."""

    @property
    @abc.abstractmethod
    def parameter_count(self) -> int:
        """Length of the parameter vector."""

    @property
    @abc.abstractmethod
    def is_interval_type2(self) -> bool:
        """``True`` if this MF produces non-degenerate (IT2) degrees."""


class CalibrationFeatureExtractor(abc.ABC):
    """Convert a :class:`CalibrationSnapshot` into the numeric input vector
    that :class:`RuleBase.evaluate` consumes.

    Bridges the gap between IBM's rich JSON calibration payload and the
    fixed-shape numeric input the TSK pipeline expects. Open decision
    (ADR-013): how aggregated, how many features, drift-aware vs.
    snapshot-only.
    """

    @abc.abstractmethod
    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        """Return the numeric input vector (shape ``(output_dim,)``)."""

    @property
    @abc.abstractmethod
    def output_dim(self) -> int:
        """Length of the extracted feature vector."""

    @property
    @abc.abstractmethod
    def feature_names(self) -> tuple[str, ...]:
        """Human-readable names of the features, in vector order."""


class FuzzificationStrategy(abc.ABC):
    """Strategy for placing fuzzy-derived noise relative to gates in a circuit.

    Covers ADR-007 (pre-gate, post-gate, between-gates). Pre/Between
    strategies typically transform the circuit (inserting error-only
    instructions or decomposing gates); Post strategies typically only
    augment the noise model via Aer's ``add_quantum_error`` mechanism.
    """

    @abc.abstractmethod
    def install(
        self,
        circuit: QuantumCircuit,
        noise_model: NoiseModel,
        error_provider: Callable[[Instruction, tuple[int, ...]], QuantumError],
    ) -> tuple[QuantumCircuit, NoiseModel]:
        """Apply this fuzzification strategy.

        ``error_provider(gate, qubits) -> QuantumError`` lets the strategy
        request the right error for any gate-qubit pair without knowing
        anything about the TSK pipeline.

        Returns ``(circuit, noise_model)``: the circuit is unchanged for
        post-gate strategies and transformed for pre/between; the noise
        model is augmented for post-gate and unchanged for pre/between.
        """


class RuleBase(abc.ABC):
    """A collection of fuzzy IF-THEN rules over an input vector.

    The TSK implementation lives in
    :class:`superconducted.fuzzy.tsk.TSKRuleBase`. Alternative rule-base
    architectures (hierarchical, sparse, evolving) implement this same
    contract.
    """

    @abc.abstractmethod
    def evaluate(self, inputs: npt.NDArray[np.float64]) -> RuleFiringResult:
        """Evaluate all rules on ``inputs`` (shape ``(input_dim,)``)."""

    @property
    @abc.abstractmethod
    def n_rules(self) -> int: ...

    @property
    @abc.abstractmethod
    def input_dim(self) -> int: ...

    @property
    @abc.abstractmethod
    def output_dim(self) -> int: ...

    @property
    @abc.abstractmethod
    def is_interval_type2(self) -> bool: ...


class Defuzzifier(abc.ABC):
    """Reduce a fuzzy rule firing result to a crisp output vector.

    Covers ADR-011: weighted average for T1, Nie-Tan closed-form for IT2.
    """

    @abc.abstractmethod
    def defuzzify(self, firing: RuleFiringResult) -> npt.NDArray[np.float64]:
        """Return the crisp output (shape ``(firing.output_dim,)``)."""


class SquashingStrategy(abc.ABC):
    """Map raw defuzzified output to constraint-respecting noise parameters.

    Covers ADR-012. Concretes ship with the bootstrap: identity, probability
    clip, sigmoid. Live separately from :class:`ChannelProjector` so the
    activation function can be swapped without rewriting the channel layer.
    """

    @abc.abstractmethod
    def squash(self, raw: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Apply the squashing function elementwise."""


class ChannelProjector(abc.ABC):
    """Convert a crisp parameter vector into an Aer ``QuantumError`` for a
    target gate-qubit pair.

    Implementations encapsulate the parameterized noise channels (amplitude
    damping, phase damping, depolarizing, ...) that consume the TSK output.
    """

    @abc.abstractmethod
    def project(
        self,
        crisp_params: npt.NDArray[np.float64],
        gate_name: str,
        qubits: tuple[int, ...],
    ) -> QuantumError:
        """Build a :class:`QuantumError` for ``gate_name`` on ``qubits``."""


class NormalizationStrategy(abc.ABC):
    """Adjust a candidate Kraus operator set to satisfy CPTP (or no-op).

    Covers ADR-008: CPTP projection (SDP-based), derivative-based with
    coefficients, or no normalization at all.
    """

    @abc.abstractmethod
    def normalize(
        self,
        kraus_ops: list[npt.NDArray[np.complex128]],
    ) -> list[npt.NDArray[np.complex128]]:
        """Return a CPTP-compliant Kraus set (or pass-through)."""


class BenchmarkMetric(abc.ABC):
    """Compute a scalar comparing the engine's simulation against a reference."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def compute(self, engine: SimulationResult, reference: SimulationResult) -> float: ...
