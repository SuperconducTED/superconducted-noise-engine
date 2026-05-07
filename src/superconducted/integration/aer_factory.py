"""Aer Factory/Ensemble integration.

ARCHITECTURAL INVARIANT: Aer has no per-shot Python hook. ``NoiseModel``'s
``to_dict()`` is called once at submission time and the C++ controller
takes over (see ``qiskit_aer/backends/backend_utils.py:cpp_execute_circuits``).
We realize sample-level uncertainty *at ensemble construction time* — by
building N distinct :class:`FuzzyNoiseModel` instances drawn from the
fuzzy uncertainty envelope and running :class:`AerSimulator` once per
member.

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
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import numpy.typing as npt
from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from ..interfaces import (
    CalibrationFeatureExtractor,
    ChannelProjector,
    Defuzzifier,
    FuzzificationStrategy,
    RuleBase,
    SquashingStrategy,
)
from ..types import CalibrationSnapshot


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
    ) -> None:
        super().__init__()
        self._calibration = calibration
        self._feature_extractor = feature_extractor
        self._rule_base = rule_base
        self._defuzzifier = defuzzifier
        self._squashing = squashing
        self._channel_projector = channel_projector
        self._fuzzification_strategy = fuzzification_strategy
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
    def calibration(self) -> CalibrationSnapshot:
        return self._calibration

    def prepare(self, circuit: QuantumCircuit) -> tuple[QuantumCircuit, NoiseModel]:
        """Build a fresh ``NoiseModel`` for ``circuit`` via the fuzzification strategy.

        The returned circuit may differ from the input (pre/between
        strategies transform the circuit; post-gate leaves it untouched).
        The returned NoiseModel is fresh — repeated calls do not
        accumulate errors.
        """

        def error_provider(gate: Instruction, qubits: tuple[int, ...]) -> QuantumError | None:
            try:
                return self._channel_projector.project(self._crisp_params, gate.name, qubits)
            except (NotImplementedError, ValueError):
                return None

        fresh_noise_model: NoiseModel = NoiseModel()
        return self._fuzzification_strategy.install(circuit, fresh_noise_model, error_provider)


class FuzzyNoiseModelEnsemble:
    """Factory yielding an ensemble of :class:`FuzzyNoiseModel` instances.

    Bootstrap status: yields ``ensemble_size`` *identical* models. Per-member
    sampling — input-vector perturbation, premise-MF perturbation, IT2
    footprint sampling — is deferred to ADR-015. Until that ADR lands the
    ensemble exists for API stability and to validate the
    aggregate-then-compare workflow.
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
            )

    def __len__(self) -> int:
        return self._size
