"""Aer Factory/Ensemble integration.

ARCHITECTURAL INVARIANT: Aer has no per-shot Python hook. ``NoiseModel``'s
``to_dict()`` is called once at submission time and the C++ controller
takes over (see ``qiskit_aer/backends/backend_utils.py:cpp_execute_circuits``).
We realize sample-level uncertainty *at ensemble construction time* — by
building N distinct :class:`FuzzyNoiseModel` instances drawn from the
fuzzy uncertainty envelope and running :class:`AerSimulator` once per
member.

That invariant, and the Factory/Ensemble response to it, is ADR-002; any
design proposing per-shot Python regeneration of noise channels is
rejected on sight. ADR-021 extends ADR-002 with the dependency-injection
contract this module implements — the six injected ABCs, the
:meth:`FuzzyNoiseModel.prepare` contract, and the plug-in points where
per-member variance will attach once ADR-015 resolves.

Bootstrap status:

- :class:`FuzzyNoiseModel.__init__` — full. Runs the pipeline
  (features → firing → defuzz → squash → crisp params) once and stashes
  the result. Errors are NOT pre-attached; they are produced on demand
  by :meth:`prepare`.
- :class:`FuzzyNoiseModel.prepare` — full. Returns a
  ``(transformed_circuit, fresh_NoiseModel)`` tuple suitable for
  :class:`AerSimulator.run`. Builds a fresh ``NoiseModel`` each call so
  repeated invocations are idempotent.
- :class:`FuzzyNoiseModelEnsemble` — partial. Yields ``ensemble_size``
  identical models at bootstrap. Per-member sampling (input perturbation,
  premise-MF perturbation, IT2 footprint sampling) is deferred to ADR-015.
- :func:`is_identity_damping` / :attr:`FuzzyNoiseModel.is_degenerate` /
  :func:`first_viable_seed` — full. Channel viability under a randomly
  initialized rule base, per ADR-024. Viability is a property of the
  assembled pipeline, not of the rule base, so it is checked here rather
  than in ``fuzzy.tsk.TSKRuleBase.from_grid``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator, Sequence
from math import isfinite

import numpy as np
import numpy.typing as npt
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from ..interfaces import (
    CalibrationFeatureExtractor,
    ChannelProjector,
    Defuzzifier,
    FuzzificationStrategy,
    GateEligibilityPolicy,
    RuleBase,
    SquashingStrategy,
)
from ..training.targets import gate_lengths
from ..types import CalibrationSnapshot

# Upper bound on the deterministic seed search in :func:`first_viable_seed`.
# A random consequent draw is degenerate with probability 1/4 (ADR-024), so
# the chance that every seed below this limit fails is 4**-64 — far below any
# rate worth engineering for. A limit this generous therefore fails fast only
# when the degeneracy is structural rather than an unlucky draw.
DEFAULT_SEED_SEARCH_LIMIT: int = 64


class CalibrationGateEligibilityPolicy(GateEligibilityPolicy):
    """Derive physical noise eligibility from archived gate-length records.

    A physical single-qubit gate is eligible exactly when its calibration
    ``properties.gates`` record supplies a finite, strictly positive
    ``gate_length``. Gates absent from those records, including administrative
    instructions such as ``delay`` and Aer save instructions, remain
    noise-free. A virtual ``rz`` whose recorded length is zero is explicitly
    ineligible rather than rejected due to missing metadata.
    """

    def eligible_operations(
        self,
        snapshot: CalibrationSnapshot,
    ) -> frozenset[tuple[str, tuple[int, ...]]]:
        entries = snapshot.properties.get("gates")
        if not isinstance(entries, list):
            return frozenset()

        gate_names: set[str] = set()
        for entry in entries:
            if isinstance(entry, dict):
                gate_name = entry.get("gate")
                if isinstance(gate_name, str):
                    gate_names.add(gate_name)
        eligible: set[tuple[str, tuple[int, ...]]] = set()
        for gate_name in gate_names:
            for qubit, duration in gate_lengths(snapshot.properties, gate_name).items():
                if isfinite(duration) and duration > 0.0:
                    eligible.add((gate_name, (qubit,)))
        return frozenset(eligible)


def warn_if_nothing_was_installed(
    circuit: QuantumCircuit,
    eligible_operations: frozenset[tuple[str, tuple[int, ...]]],
) -> None:
    """Warn when :meth:`FuzzyNoiseModel.prepare` installed no error at all.

    Two distinct configuration mistakes both land as an empty ``NoiseModel``,
    and both were previously silent:

    - the calibration snapshot carries no positive-duration single-qubit gate
      record, so nothing is eligible against any circuit; or
    - the snapshot is fine, but the circuit was never compiled to the
      calibrated physical basis, so no instruction name can match.

    Either way the engine returns a model that installs nothing, the caller
    simulates a noiseless circuit, and the run still looks successful. That is
    how a benchmark row can report a number measured from an engine that was
    switched off. This warns instead of raising: ADR-021 fixes ``prepare``'s
    return contract, and a circuit really can be legitimately noise-free (an
    ``rz``-only or measure-only circuit is the honest example), so the
    diagnostic is informational and a caller may filter it.

    ``eligible_operations`` is the policy's decision for this snapshot;
    ``circuit`` is the caller's input, because that is the thing they can fix.
    No warning is emitted for an empty circuit, which has nothing to noise.
    """
    present = sorted({instruction.operation.name for instruction in circuit.data})
    if not present:
        return
    if not eligible_operations:
        warnings.warn(
            "FuzzyNoiseModel.prepare installed no error: this calibration "
            f"snapshot yields no eligible gate at all. Circuit instructions: {present}.",
            stacklevel=3,
        )
        return
    eligible_names = sorted({name for name, _ in eligible_operations})
    warnings.warn(
        "FuzzyNoiseModel.prepare installed no error: none of the circuit's "
        f"instructions {present} is eligible under this calibration "
        f"{eligible_names}. Compile the circuit to the calibrated physical "
        "basis before calling prepare().",
        stacklevel=3,
    )


def is_identity_damping(crisp_params: npt.NDArray[np.float64]) -> bool:
    """True if ``crisp_params`` projects to the identity (no-op) channel.

    Contract (ADR-024). This encodes the parameter reading used by
    :class:`superconducted.channels.kraus.KrausChannelProjector`: entry 0 is
    the amplitude-damping rate ``gamma`` and entry 1 the phase-damping rate
    ``lambda``. Amplitude damping at ``gamma = 0`` is the identity, phase
    damping at ``lambda = 0`` is the identity, and the composition of two
    identities is the identity — so the projected channel is exactly the
    identity iff both entries are zero. A model in that state installs a
    noise model that measures nothing.

    The predicate lives here, not in :mod:`superconducted.channels.kraus`,
    because ``channels/`` is a LOCKED zone; it is written against that
    module's published parameter contract and moves next to the projector
    if the ``ChannelProjector`` ABC ever grows a viability method.

    Only meaningful for a squashing strategy whose non-positive image is
    exactly zero — :class:`~superconducted.fuzzy.squashing.ProbabilityClip`
    (the bootstrap default) and
    :class:`~superconducted.fuzzy.squashing.IdentitySquashing` qualify.
    Under :class:`~superconducted.fuzzy.squashing.SigmoidSquashing` nothing
    is ever exactly zero, so this returns ``False`` for every draw; that is
    correct but uninformative, and such a pipeline needs its own viability
    definition rather than this one.

    Raises ``ValueError`` for a vector shorter than two entries, mirroring
    ``KrausChannelProjector.project``. Such a vector is not an identity
    channel — it is one the projector cannot read at all, and reporting it
    as degenerate would name the wrong defect.
    """
    params = np.asarray(crisp_params, dtype=np.float64)
    if params.size < 2:
        raise ValueError(
            f"crisp_params must contain at least 2 entries (p_amp, p_phase) to "
            f"decide channel viability; got shape {params.shape}"
        )
    return not bool(np.any(params.flat[:2] > 0.0))


class FuzzyNoiseModel(NoiseModel):  # type: ignore[misc]
    """A NoiseModel built from a fuzzy pipeline against a calibration sample.

    Construction runs the pipeline once::

        features = feature_extractor.extract(calibration)
        firing   = rule_base.evaluate(features)
        raw      = defuzzifier.defuzzify(firing)
        crisp    = squashing.squash(raw)

    Errors are NOT pre-attached to ``self``; they are produced on demand
    by :meth:`prepare`, which the harness (or any caller) must invoke
    before passing the resulting NoiseModel to ``AerSimulator``.

    Subclassing :class:`NoiseModel` is a typing convenience: callers can
    treat instances as NoiseModels for static analysis, but should always
    go through :meth:`prepare` rather than passing ``self`` directly to
    Aer (which would have no errors attached).

    ADR-021 specifies this construction contract: the six injected
    dependencies above and optional :class:`GateEligibilityPolicy` are the
    swappable research axes. The strict DI surface is deliberate — it is what
    makes each axis independently testable, at the cost of non-trivial factory
    construction.
    """

    def __init__(
        self,
        calibration: CalibrationSnapshot,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
        squashing: SquashingStrategy,
        channel_projector: ChannelProjector,
        fuzzification_strategy: FuzzificationStrategy,
        gate_eligibility_policy: GateEligibilityPolicy | None = None,
    ) -> None:
        super().__init__()
        self._calibration = calibration
        self._feature_extractor = feature_extractor
        self._rule_base = rule_base
        self._defuzzifier = defuzzifier
        self._squashing = squashing
        self._channel_projector = channel_projector
        self._fuzzification_strategy = fuzzification_strategy
        self._gate_eligibility_policy = (
            gate_eligibility_policy
            if gate_eligibility_policy is not None
            else CalibrationGateEligibilityPolicy()
        )
        self._crisp_params: npt.NDArray[np.float64] = self._compute_crisp_params()

    def _compute_crisp_params(self) -> npt.NDArray[np.float64]:
        features = self._feature_extractor.extract(self._calibration)
        firing = self._rule_base.evaluate(features)
        raw = self._defuzzifier.defuzzify(firing)
        return self._squashing.squash(raw)

    @property
    def crisp_params(self) -> npt.NDArray[np.float64]:
        """Read-only view of the crisp noise parameters (post-squashing)."""
        return self._crisp_params

    @property
    def is_degenerate(self) -> bool:
        """True if this model's channel is the identity, so it adds no noise.

        Reachable whenever the rule base was built with
        ``consequent_init="random"``: those consequents are zero-mean, so
        one draw in four lands here (ADR-024). Check it before trusting a
        run, and see :func:`first_viable_seed` for the standard remedy.
        """
        return is_identity_damping(self._crisp_params)

    @property
    def calibration(self) -> CalibrationSnapshot:
        return self._calibration

    def prepare(self, circuit: QuantumCircuit) -> tuple[QuantumCircuit, NoiseModel]:
        """Build a fresh ``NoiseModel`` for ``circuit`` via the fuzzification strategy.

        ``circuit`` must already be compiled to the physical basis represented
        by the calibration's gate-length records. The returned circuit may
        differ from the input (pre/between
        strategies transform the circuit; post-gate leaves it untouched).
        The returned NoiseModel is fresh — repeated calls do not
        accumulate errors.

        ADR-021 fixes this contract. Two parts of it are worth stating
        explicitly:

        - **Idempotency.** A fresh ``NoiseModel`` is built per call and no
          state accumulates on ``self``, so repeated calls with the same
          circuit are interchangeable.
        - **Caller-side isolation.** Callers that reuse one circuit across
          ensemble members should pass ``circuit.copy()``. Today this is a
          forward-looking requirement rather than a live hazard: the only
          implemented strategy, :class:`PostGateFuzzification`, returns the
          *same* circuit object unmutated, and the pre/between strategies
          that will transform it are still stubs pending ADR-007. Copying
          now keeps callers correct when those land.

        A circuit that is not compiled to the calibrated physical basis
        matches no eligible operation, so nothing is installed and the
        caller silently simulates a noiseless circuit. That case warns via
        :func:`warn_if_nothing_was_installed` rather than raising, because
        a noise-free circuit is legal; see that function for the trade-off.
        """

        eligible_operations = self._gate_eligibility_policy.eligible_operations(self._calibration)

        def error_provider(gate: Instruction, qubits: tuple[int, ...]) -> QuantumError | None:
            if (gate.name, qubits) not in eligible_operations:
                return None
            try:
                return self._channel_projector.project(self._crisp_params, gate.name, qubits)
            except (NotImplementedError, ValueError):
                return None

        fresh_noise_model: NoiseModel = NoiseModel()
        prepared_circuit, prepared_noise_model = self._fuzzification_strategy.install(
            circuit, fresh_noise_model, error_provider
        )
        if not prepared_noise_model.noise_instructions:
            warn_if_nothing_was_installed(circuit, eligible_operations)
        return prepared_circuit, prepared_noise_model


class FuzzyNoiseModelEnsemble:
    """Factory yielding an ensemble of :class:`FuzzyNoiseModel` instances.

    Bootstrap status: yields ``ensemble_size`` *identical* models. Per-member
    sampling — input-vector perturbation, premise-MF perturbation, IT2
    footprint sampling — is deferred to ADR-015. Until that ADR lands the
    ensemble exists for API stability and to validate the
    aggregate-then-compare workflow.

    ADR-021 records those three mechanisms as the plug-in points inside
    :meth:`__iter__`, so ADR-015 can choose among them without refactoring
    this factory. The choice additionally depends on ADR-009 (T1 vs IT2)
    and ADR-014 (trained MFs with meaningful variance).
    """

    def __init__(
        self,
        calibration: CalibrationSnapshot,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
        squashing: SquashingStrategy,
        channel_projector: ChannelProjector,
        fuzzification_strategy: FuzzificationStrategy,
        gate_eligibility_policy: GateEligibilityPolicy | None = None,
        ensemble_size: int = 32,
        rng: np.random.Generator | None = None,
    ) -> None:
        if ensemble_size <= 0:
            raise ValueError(f"ensemble_size must be positive; got {ensemble_size}")
        self._size = int(ensemble_size)
        self._rng = rng if rng is not None else np.random.default_rng()
        self._calibration = calibration
        self._feature_extractor = feature_extractor
        self._rule_base = rule_base
        self._defuzzifier = defuzzifier
        self._squashing = squashing
        self._channel_projector = channel_projector
        self._fuzzification_strategy = fuzzification_strategy
        self._gate_eligibility_policy = gate_eligibility_policy

    def __iter__(self) -> Iterator[FuzzyNoiseModel]:
        for _ in range(self._size):
            yield FuzzyNoiseModel(
                calibration=self._calibration,
                feature_extractor=self._feature_extractor,
                rule_base=self._rule_base,
                defuzzifier=self._defuzzifier,
                squashing=self._squashing,
                channel_projector=self._channel_projector,
                fuzzification_strategy=self._fuzzification_strategy,
                gate_eligibility_policy=self._gate_eligibility_policy,
            )

    def __len__(self) -> int:
        return self._size


def first_viable_seed(
    build: Callable[[int], Sequence[FuzzyNoiseModel]],
    seed_limit: int = DEFAULT_SEED_SEARCH_LIMIT,
    context: str = "",
) -> tuple[list[FuzzyNoiseModel], int]:
    """Return the first non-degenerate ensemble and the seed that produced it.

    ``build(seed)`` must construct an ensemble whose rule base is seeded by
    ``seed`` and nothing else, so that the search is a pure function of the
    seed. Seeds are tried in the order ``0, 1, 2, ...``, which makes the
    chosen seed reproducible on any machine.

    This is rejection sampling, not error recovery, and the distinction is
    the point of ADR-024. A zero-mean random consequent draw is degenerate
    with probability exactly 1/4 regardless of rule count, membership-function
    placement, or input vector — so a caller that hard-codes a seed is not
    picking a robust default, it is taking a 3-in-4 bet that happens to have
    paid off at the moment it was written. That bet was silently lost in
    Issue #31 when the grid grew from 8 rules to the ratified 27 and a
    previously fine ``default_rng(0)`` started producing an identity channel.

    Raises ``ValueError`` if no seed below ``seed_limit`` is viable. At a 1/4
    per-draw failure rate the default limit makes that outcome effectively
    impossible by chance, so it indicates a structural problem — consequents
    that are identically zero (the ``consequent_init="zeros"`` bootstrap
    default, per ADR-014), a feature vector that fires no rule, or a
    squashing strategy this predicate does not describe.

    ``context`` is prepended to that message. Pass the grid or configuration
    the caller assembled; the search sees only an opaque ``build`` callable
    and cannot describe it, and a caller that has to re-raise just to add
    that detail ends up matching on message text to tell the failure modes
    apart.
    """
    if seed_limit <= 0:
        raise ValueError(f"seed_limit must be positive; got {seed_limit}")

    for seed in range(seed_limit):
        members = list(build(seed))
        if not members:
            raise ValueError(f"build({seed}) returned an empty ensemble")
        if not any(member.is_degenerate for member in members):
            return members, seed

    detail = f" {context}" if context else ""
    raise ValueError(
        f"No seed below {seed_limit} produced a non-degenerate channel.{detail} At the "
        "1/4 per-draw degeneracy rate of ADR-024 this is not an unlucky run; it "
        "points at zero consequents (ADR-014), a feature vector that fires no "
        "rule, or a squashing strategy whose non-positive image is not exactly "
        "zero."
    )
