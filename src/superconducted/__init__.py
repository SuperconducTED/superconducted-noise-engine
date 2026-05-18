"""SuperconducTED: fuzzy-logic noise engine for Qiskit Aer.

The package exposes nine ABCs in :mod:`superconducted.interfaces` covering
every research axis still in flux (membership shape, fuzzification placement,
calibration vectorization, squashing, T1 vs IT2, normalization, defuzzification,
channel projection, benchmark metrics) and four frozen-dataclass value types
in :mod:`superconducted.types`. The TSK inference math is concrete and locked
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
    MembershipFunction,
    NormalizationStrategy,
    RuleBase,
    SquashingStrategy,
)
from .types import (
    CalibrationSnapshot,
    MembershipDegree,
    RuleFiringResult,
    SimulationResult,
)

__version__ = "0.1.0"

__all__ = [
    "BenchmarkMetric",
    "CalibrationFeatureExtractor",
    "CalibrationSnapshot",
    "ChannelProjector",
    "Defuzzifier",
    "FuzzificationStrategy",
    "MembershipDegree",
    "MembershipFunction",
    "NormalizationStrategy",
    "RuleBase",
    "RuleFiringResult",
    "SimulationResult",
    "SquashingStrategy",
    "__version__",
]
