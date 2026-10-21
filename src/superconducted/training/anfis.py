"""Hybrid ANFIS trainer core.

The M2 core fits consequent parameters with batch ridge least squares while
leaving premise membership functions fixed. It standardizes internally and
returns a rule base that evaluates raw feature vectors.
"""

from __future__ import annotations

import copy
import math
from typing import Literal

import numpy as np
import numpy.typing as npt

from ..fuzzy.membership import (
    GaussianMF,
    IntervalGaussianMF,
    TanhBellMF,
    TanhMF,
    TanhSigmoidMF,
    TrapezoidalMF,
    TriangularMF,
)
from ..fuzzy.tsk import TSKRule, TSKRuleBase
from ..interfaces import MembershipFunction, RuleBase, TSKTrainer
from ..types import RuleFiringResult, TrainingDiagnostics, TrainingResult, TrainingSet
from .parameters import count_trainable_parameters, premise_layout

_MF_TYPES = (
    GaussianMF,
    TriangularMF,
    TrapezoidalMF,
    TanhMF,
    IntervalGaussianMF,
    TanhSigmoidMF,
    TanhBellMF,
)


def evaluate_rmse(rule_base: TSKRuleBase, data: TrainingSet) -> npt.NDArray[np.float64]:
    """Return per-target raw-unit RMSE, excluding zero-firing rows.

    This follows the trainer's FR-12 policy: rows for which the T1 total or
    either IT2 bound is zero have no defined defuzzified output and are not
    scored. Raises ``ValueError`` when every row is excluded.
    """
    predictions, kept = _predictions_with_mask(rule_base, data.features)
    return _rmse(predictions[kept], data.targets[kept])


class HybridANFISTrainer(TSKTrainer):
    """Fit a ``TSKRuleBase`` with batch ridge least squares in standardized space.

    Args:
        epochs: Must be zero in the M2 core; positive values reserve the
            finite-difference premise stage.
        premise_lr: Positive future premise-step learning rate.
        ridge: Non-negative L2 penalty around the mapped warm-start
            consequents.
        seed: Recorded in the result for reproducibility.
        gradient: Reserved premise-gradient strategy.
        validation: Optional compatible raw-unit validation set.
        fd_step: Positive future finite-difference step.
        patience: Positive future early-stopping patience.
        max_halvings: Non-negative future premise-step retry count.

    ``fit`` returns a new rule base, never mutates caller-owned membership
    functions or consequent arrays, and excludes zero-firing training rows
    from the solve and reported training metrics. ``TypeError`` is raised for
    another ``RuleBase`` implementation, ``ValueError`` for incompatible data,
    invalid warm starts, or non-finite fitted outputs, and
    ``NotImplementedError`` for a positive ``epochs`` value.

    The standardization and exact raw-unit map-back implement the M2 portion
    of ADR-014 while it remains Deferred; T1 and IT2 weights respectively
    match ADR-011's shipped weighted-average and Nie-Tan paths without
    deciding ADR-009.
    """

    def __init__(
        self,
        *,
        epochs: int = 0,
        premise_lr: float = 1e-2,
        ridge: float = 1e-6,
        seed: int = 0,
        gradient: Literal["finite-difference", "analytic"] = "finite-difference",
        validation: TrainingSet | None = None,
        fd_step: float = 6e-6,
        patience: int = 10,
        max_halvings: int = 5,
    ) -> None:
        if epochs < 0:
            raise ValueError("epochs must be non-negative")
        if not math.isfinite(premise_lr) or premise_lr <= 0.0:
            raise ValueError("premise_lr must be finite and positive")
        if not math.isfinite(ridge) or ridge < 0.0:
            raise ValueError("ridge must be finite and non-negative")
        if gradient not in {"finite-difference", "analytic"}:
            raise ValueError("gradient must be 'finite-difference' or 'analytic'")
        if not math.isfinite(fd_step) or fd_step <= 0.0:
            raise ValueError("fd_step must be finite and positive")
        if patience <= 0:
            raise ValueError("patience must be positive")
        if max_halvings < 0:
            raise ValueError("max_halvings must be non-negative")
        self._epochs = epochs
        self._premise_lr = premise_lr
        self._ridge = ridge
        self._seed = seed
        self._gradient = gradient
        self._validation = validation
        self._fd_step = fd_step
        self._patience = patience
        self._max_halvings = max_halvings

    def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
        """Fit immutable caller state and return raw-unit metrics and diagnostics.

        Before fitting, every warm-start parameter must be finite, and the warm
        start must not be identity damping on every training row (FR-9). A warm
        start that is identity damping on some rows but not all is accepted.
        Together with a deterministic anchored warm start (Issue #59), this
        degeneracy check is the third mechanism Issue #60 records for ADR-024
        clause 5: it meets the clause's intent without claiming either of the
        two mechanisms the clause enumerates.
        """
        if not isinstance(rule_base, TSKRuleBase):
            raise TypeError("HybridANFISTrainer requires a TSKRuleBase")
        if self._epochs != 0:
            raise NotImplementedError(
                "premise optimization is not part of the M2 trainer core; use epochs=0"
            )
        if data.input_dim != rule_base.input_dim:
            raise ValueError(
                f"TrainingSet input_dim {data.input_dim} does not match rule base "
                f"input_dim {rule_base.input_dim}"
            )
        if data.output_dim != rule_base.output_dim:
            raise ValueError(
                f"TrainingSet output_dim {data.output_dim} does not match rule base "
                f"output_dim {rule_base.output_dim}"
            )
        if self._validation is not None:
            _validate_validation(self._validation, data)

        _reject_nonfinite_warm_start(rule_base)
        _reject_identity_warm_start(rule_base, data.features)
        feature_mean, feature_scale = _standardization(data.features)
        target_mean, target_scale = _standardization(data.targets)
        standardized = _to_standardized_rule_base(
            rule_base, feature_mean, feature_scale, target_mean, target_scale
        )
        features = (data.features - feature_mean) / feature_scale
        targets = (data.targets - target_mean) / target_scale
        design, kept = _design_matrix(standardized, features)
        if not np.any(kept):
            raise ValueError("all training rows have zero firing strength")

        fitted, condition_number = _fit_consequents(
            standardized,
            design,
            targets[kept],
            None if data.weights is None else data.weights[kept],
            self._ridge,
        )
        raw_rule_base = _to_raw_rule_base(
            fitted, feature_mean, feature_scale, target_mean, target_scale
        )
        raw_predictions = _predict(raw_rule_base, data.features[kept])
        validation_predictions: npt.NDArray[np.float64] | None = None
        validation_kept: npt.NDArray[np.bool_] | None = None
        if self._validation is not None:
            validation_predictions, validation_kept = _predictions_with_mask(
                raw_rule_base, self._validation.features
            )
        _ensure_finite_model(
            raw_rule_base,
            ((raw_predictions, np.ones(raw_predictions.shape[0], dtype=np.bool_)),)
            if validation_predictions is None or validation_kept is None
            else (
                (raw_predictions, np.ones(raw_predictions.shape[0], dtype=np.bool_)),
                (validation_predictions, validation_kept),
            ),
        )

        fitted_predictions = _predict(fitted, features[kept])
        train_loss = float(np.mean(np.sum((fitted_predictions - targets[kept]) ** 2, axis=1)))
        validation_rmse = None
        if self._validation is not None:
            assert validation_predictions is not None
            assert validation_kept is not None
            validation_rmse = _rmse(
                validation_predictions[validation_kept],
                self._validation.targets[validation_kept],
            )
        diagnostics = TrainingDiagnostics(
            clip_binding_rate=float(np.mean((raw_predictions < 0.0) | (raw_predictions > 1.0))),
            zero_firing_rows_dropped=int(np.count_nonzero(~kept)),
            nonfinite_rows_rejected=0,
            lse_condition_number=condition_number,
            premise_steps_rejected=0,
            epochs_run=0,
            early_stopped=False,
            standardization=(feature_mean, feature_scale, target_mean, target_scale),
        )
        return TrainingResult(
            rule_base=raw_rule_base,
            train_rmse=_rmse(raw_predictions, data.targets[kept]),
            validation_rmse=validation_rmse,
            loss_history=(train_loss,),
            diagnostics=diagnostics,
            parameter_count=count_trainable_parameters(raw_rule_base),
            seed=self._seed,
        )


def _validate_validation(validation: TrainingSet, training: TrainingSet) -> None:
    if validation.input_dim != training.input_dim:
        raise ValueError("validation input_dim must match training data")
    if validation.output_dim != training.output_dim:
        raise ValueError("validation output_dim must match training data")
    if validation.feature_names != training.feature_names:
        raise ValueError("validation feature_names must match training data")
    if validation.target_names != training.target_names:
        raise ValueError("validation target_names must match training data")


def _standardization(
    values: npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    mean = np.mean(values, axis=0)
    scale = np.std(values, axis=0)
    scale = np.where(scale == 0.0, 1.0, scale)
    return np.asarray(mean, dtype=np.float64), np.asarray(scale, dtype=np.float64)


def _effective_weights(firing: RuleFiringResult) -> npt.NDArray[np.float64] | None:
    """Return defuzzifier-equivalent T1 or Nie-Tan rule weights."""
    strengths = firing.firing_strengths
    lower = firing.firing_strengths_lower
    upper = firing.firing_strengths_upper
    if lower is None or upper is None:
        total = float(strengths.sum())
        if total == 0.0:
            return None
        return np.asarray(strengths / total, dtype=np.float64)
    total_low = float(lower.sum())
    total_high = float(upper.sum())
    if total_low == 0.0 or total_high == 0.0:
        return None
    return np.asarray(0.5 * (lower / total_low + upper / total_high), dtype=np.float64)


def _predict(rule_base: TSKRuleBase, features: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    predictions, kept = _predictions_with_mask(rule_base, features)
    if not np.all(kept):
        first_dropped = int(np.flatnonzero(~kept)[0])
        raise ZeroDivisionError(f"rule base has zero firing strength for row {first_dropped}")
    return predictions


def _predictions_with_mask(
    rule_base: TSKRuleBase, features: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_]]:
    predictions = np.empty((features.shape[0], rule_base.output_dim), dtype=np.float64)
    kept = np.zeros(features.shape[0], dtype=np.bool_)
    for row, values in enumerate(features):
        firing = rule_base.evaluate(values)
        weights = _effective_weights(firing)
        if weights is None:
            continue
        predictions[row] = weights @ firing.consequent_outputs
        kept[row] = True
    return predictions, kept


def _rmse(
    predictions: npt.NDArray[np.float64], targets: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    if predictions.shape[0] == 0:
        raise ValueError("all rows have zero firing strength")
    return np.asarray(np.sqrt(np.mean((predictions - targets) ** 2, axis=0)), dtype=np.float64)


def _design_matrix(
    rule_base: TSKRuleBase, features: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_]]:
    width = rule_base.n_rules * (rule_base.input_dim + 1)
    matrix = np.empty((features.shape[0], width), dtype=np.float64)
    kept = np.zeros(features.shape[0], dtype=np.bool_)
    for row, values in enumerate(features):
        weights = _effective_weights(rule_base.evaluate(values))
        if weights is None:
            continue
        augmented = np.append(values, 1.0)
        matrix[row] = (weights[:, None] * augmented).reshape(-1)
        kept[row] = True
    return matrix[kept], kept


def _fit_consequents(
    rule_base: TSKRuleBase,
    design: npt.NDArray[np.float64],
    targets: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64] | None,
    ridge: float,
) -> tuple[TSKRuleBase, float]:
    prior = np.transpose(
        np.stack([rule.consequent_params for rule in rule_base.rules]),
        (0, 2, 1),
    ).reshape(rule_base.n_rules * (rule_base.input_dim + 1), rule_base.output_dim)
    row_scale = np.ones(design.shape[0], dtype=np.float64)
    if weights is not None:
        normalized_weights = weights / np.mean(weights)
        row_scale = np.sqrt(normalized_weights)
    weighted_design = design * row_scale[:, None]
    residual = (targets - design @ prior) * row_scale[:, None]
    if ridge == 0.0:
        delta, _, _, _ = np.linalg.lstsq(weighted_design, residual, rcond=None)
        augmented = weighted_design
    else:
        identity = np.sqrt(ridge) * np.eye(design.shape[1], dtype=np.float64)
        augmented = np.vstack((weighted_design, identity))
        augmented_residual = np.vstack(
            (residual, np.zeros((design.shape[1], rule_base.output_dim), dtype=np.float64))
        )
        delta, _, _, _ = np.linalg.lstsq(augmented, augmented_residual, rcond=None)
    fitted = prior + delta
    rules = [
        TSKRule(
            rule.antecedent_mfs,
            np.asarray(
                fitted[
                    index * (rule_base.input_dim + 1) : (index + 1) * (rule_base.input_dim + 1)
                ].T,
                dtype=np.float64,
            ).copy(),
        )
        for index, rule in enumerate(rule_base.rules)
    ]
    return (
        TSKRuleBase(rules, rule_base.input_dim, rule_base.output_dim),
        float(np.linalg.cond(augmented)),
    )


def _to_standardized_rule_base(
    rule_base: TSKRuleBase,
    feature_mean: npt.NDArray[np.float64],
    feature_scale: npt.NDArray[np.float64],
    target_mean: npt.NDArray[np.float64],
    target_scale: npt.NDArray[np.float64],
) -> TSKRuleBase:
    copied = copy.deepcopy(rule_base)
    layout = premise_layout(copied)
    for membership, input_index in zip(layout.mfs, layout.input_indices, strict=True):
        membership.set_parameters(
            _transform_membership(
                membership,
                float(feature_mean[input_index]),
                float(feature_scale[input_index]),
                to_standardized=True,
            )
        )
    rules = [
        TSKRule(
            rule.antecedent_mfs,
            _consequents_to_standardized(
                original.consequent_params,
                feature_mean,
                feature_scale,
                target_mean,
                target_scale,
            ),
        )
        for original, rule in zip(rule_base.rules, copied.rules, strict=True)
    ]
    return TSKRuleBase(rules, copied.input_dim, copied.output_dim)


def _to_raw_rule_base(
    rule_base: TSKRuleBase,
    feature_mean: npt.NDArray[np.float64],
    feature_scale: npt.NDArray[np.float64],
    target_mean: npt.NDArray[np.float64],
    target_scale: npt.NDArray[np.float64],
) -> TSKRuleBase:
    copied = copy.deepcopy(rule_base)
    layout = premise_layout(copied)
    for membership, input_index in zip(layout.mfs, layout.input_indices, strict=True):
        membership.set_parameters(
            _transform_membership(
                membership,
                float(feature_mean[input_index]),
                float(feature_scale[input_index]),
                to_standardized=False,
            )
        )
    rules = [
        TSKRule(
            rule.antecedent_mfs,
            _consequents_to_raw(
                original.consequent_params,
                feature_mean,
                feature_scale,
                target_mean,
                target_scale,
            ),
        )
        for original, rule in zip(rule_base.rules, copied.rules, strict=True)
    ]
    return TSKRuleBase(rules, copied.input_dim, copied.output_dim)


def _consequents_to_standardized(
    raw: npt.NDArray[np.float64],
    feature_mean: npt.NDArray[np.float64],
    feature_scale: npt.NDArray[np.float64],
    target_mean: npt.NDArray[np.float64],
    target_scale: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    standardized = np.empty_like(raw)
    standardized[:, :-1] = raw[:, :-1] * feature_scale / target_scale[:, None]
    standardized[:, -1] = (raw[:, -1] + raw[:, :-1] @ feature_mean - target_mean) / target_scale
    return standardized


def _consequents_to_raw(
    standardized: npt.NDArray[np.float64],
    feature_mean: npt.NDArray[np.float64],
    feature_scale: npt.NDArray[np.float64],
    target_mean: npt.NDArray[np.float64],
    target_scale: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    raw = np.empty_like(standardized)
    raw[:, :-1] = standardized[:, :-1] * target_scale[:, None] / feature_scale
    raw[:, -1] = (
        target_scale * (standardized[:, -1] - standardized[:, :-1] @ (feature_mean / feature_scale))
        + target_mean
    )
    return raw


def _transform_membership(
    membership: MembershipFunction, mean: float, scale: float, *, to_standardized: bool
) -> npt.NDArray[np.float64]:
    if not isinstance(membership, _MF_TYPES):
        raise TypeError(f"unsupported membership function {type(membership).__name__}")
    params = membership.parameters()
    if to_standardized:
        transformed = _location_scale_to_standardized(membership, params, mean, scale)
    else:
        transformed = _location_scale_to_raw(membership, params, mean, scale)
    return np.asarray(transformed, dtype=np.float64)


def _location_scale_to_standardized(
    membership: MembershipFunction,
    params: npt.NDArray[np.float64],
    mean: float,
    scale: float,
) -> npt.NDArray[np.float64]:
    transformed = params.copy()
    if isinstance(membership, (GaussianMF, IntervalGaussianMF)):
        transformed[0] = (params[0] - mean) / scale
        transformed[1:] = params[1:] / scale
    elif isinstance(membership, (TriangularMF, TrapezoidalMF)):
        transformed = (params - mean) / scale
    elif isinstance(membership, TanhMF):
        transformed[:2] = (params[:2] - mean) / scale
        transformed[2:] = params[2:] * scale
    elif isinstance(membership, TanhSigmoidMF):
        transformed[0] = (params[0] - mean) / scale
        transformed[1] = params[1] * scale
    elif isinstance(membership, TanhBellMF):
        transformed[:2] = (params[:2] - mean) / scale
        transformed[2] = params[2] * scale
    return transformed


def _location_scale_to_raw(
    membership: MembershipFunction,
    params: npt.NDArray[np.float64],
    mean: float,
    scale: float,
) -> npt.NDArray[np.float64]:
    transformed = params.copy()
    if isinstance(membership, (GaussianMF, IntervalGaussianMF)):
        transformed[0] = params[0] * scale + mean
        transformed[1:] = params[1:] * scale
    elif isinstance(membership, (TriangularMF, TrapezoidalMF)):
        transformed = params * scale + mean
    elif isinstance(membership, TanhMF):
        transformed[:2] = params[:2] * scale + mean
        transformed[2:] = params[2:] / scale
    elif isinstance(membership, TanhSigmoidMF):
        transformed[0] = params[0] * scale + mean
        transformed[1] = params[1] / scale
    elif isinstance(membership, TanhBellMF):
        transformed[:2] = params[:2] * scale + mean
        transformed[2] = params[2] / scale
    return transformed


def _reject_nonfinite_warm_start(rule_base: TSKRuleBase) -> None:
    # Neither TSKRule nor GaussianMF rejects NaN, and without this check a NaN
    # warm start surfaces later under a message that names the fit or the
    # membership degree rather than the caller's input.
    for index, rule in enumerate(rule_base.rules):
        if not np.all(np.isfinite(rule.consequent_params)):
            raise ValueError(f"warm-start rule {index} has non-finite consequent parameters")
        if any(not np.all(np.isfinite(mf.parameters())) for mf in rule.antecedent_mfs):
            raise ValueError(
                f"warm-start rule {index} has a membership function with non-finite parameters"
            )


def _reject_identity_warm_start(rule_base: TSKRuleBase, features: npt.NDArray[np.float64]) -> None:
    predictions, kept = _predictions_with_mask(rule_base, features)
    if not np.any(kept):
        return
    relevant = predictions[kept, : min(2, rule_base.output_dim)]
    # This mirrors aer_factory.is_identity_damping on finite outputs without
    # importing qiskit_aer into the training core; only the first two damping
    # outputs define the channel identity predicate. The two differ on NaN:
    # is_identity_damping reports a NaN vector as identity and this check does
    # not, which is the safer reading (Issue #60 decision 5), and fit refuses
    # non-finite warm-start parameters before reaching this point.
    if np.all(relevant <= 0.0):
        raise ValueError(
            "warm-start rule base is identity damping on every training row; "
            "use an anchored baseline or a viable random seed"
        )


def _ensure_finite_model(
    rule_base: TSKRuleBase,
    evaluated_sets: tuple[tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_]], ...],
) -> None:
    for rule in rule_base.rules:
        if not np.all(np.isfinite(rule.consequent_params)):
            raise ValueError("fitted consequent parameters must be finite")
    layout = premise_layout(rule_base)
    if any(not np.all(np.isfinite(membership.parameters())) for membership in layout.mfs):
        raise ValueError("fitted membership parameters must be finite")
    for predictions, kept in evaluated_sets:
        if not np.any(kept):
            raise ValueError("all rows have zero firing strength")
        if not np.all(np.isfinite(predictions[kept])):
            raise ValueError("fitted rule base produced non-finite outputs")
