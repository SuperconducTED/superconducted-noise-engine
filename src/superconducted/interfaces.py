"""Abstract base classes for SuperconducTED's swappable design axes.

Each ABC corresponds to one open decision recorded in
``docs/decisions.md``. The TSK inference math (in
:mod:`superconducted.fuzzy.tsk`) is concrete and locked; the Aer
Factory/Ensemble integration pattern is also concrete and locked (in
:mod:`superconducted.integration.aer_factory`). Everything else swaps
through these contracts.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from .types import CalibrationSnapshot, MembershipDegree, RuleFiringResult, SimulationResult

if TYPE_CHECKING:
    from .types import TrainingResult, TrainingSet


class MembershipFunction(abc.ABC):
    """Fuzzy membership function over a single scalar input.

    Implementations cover the open decision on MF shape (Gaussian, triangular,
    trapezoidal, tanh-based, IT2 variants — see ADR-006). All implementations
    return :class:`MembershipDegree`: T1 implementations produce degenerate
    (``low == high``) degrees, IT2 implementations produce non-degenerate
    ones.

    Trainable parameters are exposed as a flat 1-D ``float64`` vector for the
    hybrid LSE/SGD ANFIS trainer in :mod:`superconducted.training`.
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


class TSKTrainer(abc.ABC):
    """Fit a validated training set without mutating the caller's rule base.

    *Inputs.* A :class:`RuleBase` — concretely a
    :class:`superconducted.fuzzy.tsk.TSKRuleBase`, but annotated as the ABC
    because ``fuzzy/tsk.py`` imports this module and the reverse import would
    be circular. Implementations therefore ``isinstance``-check the argument
    and raise :class:`TypeError` for any other :class:`RuleBase`. The second
    input is a validated :class:`superconducted.types.TrainingSet`.

    *Output.* A :class:`superconducted.types.TrainingResult` whose
    ``rule_base`` is a **new** object.

    *Side effects.* None on the caller's rule base.

    *Invariants.*

    (a) The input rule base's parameter **values** are unchanged after
        ``fit`` — every ``TSKRule.consequent_params`` and every
        ``MembershipFunction.parameters()``.
    (b) Every consequent entry and MF parameter in the returned rule base is
        finite.
    (c) The returned rule base has the same ``n_rules``, ``input_dim``,
        ``output_dim`` and ``is_interval_type2``.

    Invariant (a) is the trainer's obligation rather than a property of the
    LOCKED ``fuzzy/tsk.py``, because that module is shallowly read-only in
    three ways:

    - ``TSKRule.consequent_params`` has no setter but returns the *live*
      internal ndarray, so ``rb.rules[0].consequent_params[0, -1] = 42.0``
      changes what ``consequent()`` returns.
    - ``TSKRule.__init__`` calls ``np.asarray(consequent_params,
      dtype=np.float64)``, which **aliases** a caller's float64 array rather
      than copying it.
    - ``TSKRuleBase.from_grid`` iterates ``product(*per_input_mfs)`` and
      reuses one MF object across every rule naming it, while
      ``set_parameters`` mutates in place — so a 3x3x3 grid has 27 rules and
      81 antecedent references over only 9 distinct objects.

    Implementations must therefore ``copy.deepcopy`` the membership functions
    before calling ``set_parameters``, pass freshly allocated consequent
    arrays into rebuilt ``TSKRule`` objects, and never write through
    ``rule.consequent_params[...]``.

    *Warm start.* An implementation must satisfy ADR-024 clause 5 — call
    ``first_viable_seed`` when initializing, or adopt a squashing strategy
    with everywhere-nonzero gradient (``SigmoidSquashing`` per ADR-012) and
    define its own viability predicate — **or record the mechanism it uses
    instead**. The clause is written against *drawn* initializations; an
    anchored consequent evaluated at each rule's centre is not drawn at all,
    so it meets the clause's intent while falling outside its letter, and
    such a trainer documents that third mechanism rather than claiming the
    clause.
    """

    @abc.abstractmethod
    def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
        """Fit ``rule_base`` to ``data`` and return a new training result."""


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
