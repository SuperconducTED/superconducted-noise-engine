"""Supervised-training data types, targets, parameter accounting, and ANFIS fitting.

``HybridANFISTrainer`` and ``evaluate_rmse`` are re-exported here so callers
use the same public ``superconducted.training`` surface as the existing target
and parameter helpers. The concrete trainer remains implemented in
``training.anfis``.
"""

from ..types import ParameterCount, TrainingDiagnostics, TrainingResult, TrainingSet
from .anfis import HybridANFISTrainer, evaluate_rmse
from .parameters import PremiseLayout, count_trainable_parameters, premise_layout
from .targets import (
    QubitTargets,
    SkipCounts,
    SnapshotTarget,
    feature_target_fn,
    gate_lengths,
    qubit_targets,
    snapshot_target,
)

__all__ = [
    "HybridANFISTrainer",
    "ParameterCount",
    "PremiseLayout",
    "QubitTargets",
    "SkipCounts",
    "SnapshotTarget",
    "TrainingDiagnostics",
    "TrainingResult",
    "TrainingSet",
    "count_trainable_parameters",
    "evaluate_rmse",
    "feature_target_fn",
    "gate_lengths",
    "premise_layout",
    "qubit_targets",
    "snapshot_target",
]
