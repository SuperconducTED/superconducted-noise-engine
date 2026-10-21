"""SuperconducTED: fuzzy-logic noise engine for Qiskit Aer.

The package exposes eleven ABCs in :mod:`superconducted.interfaces` covering
every research axis still in flux (membership shape, fuzzification placement,
calibration vectorization, squashing, T1 vs IT2, normalization, defuzzification,
channel projection, gate eligibility, benchmark metrics, trainer contract) and eight
frozen-dataclass value types in :mod:`superconducted.types`. The counts are
pinned by ``tests/test_interfaces.py``, so they cannot drift silently as
research axes are added. The TSK inference math is concrete and locked
in :mod:`superconducted.fuzzy.tsk`; the Aer Factory/Ensemble integration is
concrete and locked in :mod:`superconducted.integration.aer_factory`.
"""

from __future__ import annotations

from .interfaces import (
    BenchmarkMetric,
    CalibrationFeatureExtractor,
    ChannelProjector,
    Defuzzifier,
    FuzzificationStrategy,
    GateEligibilityPolicy,
    MembershipFunction,
    NormalizationStrategy,
    RuleBase,
    SquashingStrategy,
    TSKTrainer,
)
from .types import (
    CalibrationSnapshot,
    MembershipDegree,
    ParameterCount,
    RuleFiringResult,
    SimulationResult,
    TrainingDiagnostics,
    TrainingResult,
    TrainingSet,
)

__version__ = "0.1.0"

__all__ = [
    "BenchmarkMetric",
    "CalibrationFeatureExtractor",
    "CalibrationSnapshot",
    "ChannelProjector",
    "Defuzzifier",
    "FuzzificationStrategy",
    "GateEligibilityPolicy",
    "MembershipDegree",
    "MembershipFunction",
    "NormalizationStrategy",
    "ParameterCount",
    "RuleBase",
    "RuleFiringResult",
    "SimulationResult",
    "SquashingStrategy",
    "TSKTrainer",
    "TrainingDiagnostics",
    "TrainingResult",
    "TrainingSet",
    "__version__",
]
