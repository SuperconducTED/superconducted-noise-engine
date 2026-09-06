"""Hybrid LSE/premise training for first-order TSK rule bases."""

from __future__ import annotations

import copy
from typing import cast

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
from ..interfaces import RuleBase, TSKTrainer
from ..types import RuleFiringResult
from .parameters import PremiseLayout, premise_layout
from .types import ParameterCount, TrainingDiagnostics, TrainingResult, TrainingSet


class HybridANFISTrainer(TSKTrainer):
    """Fit TSK consequents and, in later steps, premise MF parameters."""

    def __init__(
        self,
        *,
        epochs: int = 0,
        premise_lr: float = 1e-2,
        ridge: float = 0.0,
        seed: int = 0,
        validation: TrainingSet | None = None,
        gradient: str = "finite-difference",
        fd_step: float = 1e-5,
        patience: int = 5,
        max_halvings: int = 8,
    ) -> None:
        if epochs < 0 or premise_lr <= 0.0 or ridge < 0.0:
            raise ValueError("epochs must be non-negative, premise_lr positive, ridge non-negative")
        if gradient not in {"finite-difference", "analytic"}:
            raise ValueError("gradient must be 'finite-difference' or 'analytic'")
        if fd_step <= 0.0 or patience < 0 or max_halvings < 0:
            raise ValueError("fd_step must be positive and retry settings non-negative")
        self.epochs = int(epochs)
        self.premise_lr = float(premise_lr)
        self.ridge = float(ridge)
        self.seed = int(seed)
        self.validation = validation
        self.gradient = gradient
        self.fd_step = float(fd_step)
        self.patience = int(patience)
        self.max_halvings = int(max_halvings)

    def fit(self, rule_base: RuleBase, data: TrainingSet) -> TrainingResult:
        """Fit a rule base without mutating the input object."""
        if not isinstance(rule_base, TSKRuleBase):
            raise TypeError("HybridANFISTrainer requires a TSKRuleBase")
        self._validate_dimensions(rule_base, data)
        if self.validation is not None:
            self._validate_dimensions(rule_base, self.validation)
        if self.gradient == "analytic":
            raise NotImplementedError("analytic premise gradients are supplied by ADR-011")
        train_features, train_targets, feature_stats, target_stats = self._standardize(data)
        validation_features: npt.NDArray[np.float64] | None = None
        validation_targets: npt.NDArray[np.float64] | None = None
        validation_weights: npt.NDArray[np.float64] | None = None
        if self.validation is not None:
            validation_features = (self.validation.features - feature_stats[0]) / feature_stats[1]
            validation_targets = (self.validation.targets - target_stats[0]) / target_stats[1]
            validation_weights = self.validation.weights
        original = copy.deepcopy(rule_base)
        premise_layout(original)
        self._assert_finite_parameters(original)
        working = copy.deepcopy(original)
        self._standardize_memberships(working, feature_stats)
        layout = premise_layout(working)
        warm = self._standardize_consequents(original, feature_stats, target_stats)
        rejected_steps = 0
        loss_history: list[float] = []
        best_premise: npt.NDArray[np.float64] | None = None
        best_validation_loss = np.inf
        epochs_without_improvement = 0
        early_stopped = False
        epochs_run = 0
        for _ in range(self.epochs):
            phi, kept, _dropped = self._design_matrix(working, train_features)
            if not np.any(kept):
                raise ValueError("every training row has zero firing strength")
            consequents, _condition_number = self._solve_consequents(
                phi, train_targets[kept], working, data, kept, warm
            )
            loss = self._loss(
                working,
                train_features[kept],
                train_targets[kept],
                consequents,
                None if data.weights is None else data.weights[kept],
            )
            loss_history.append(loss)
            step_data = TrainingSet(
                train_features[kept],
                train_targets[kept],
                None if data.weights is None else data.weights[kept],
            )
            rejected_steps += self._premise_step(
                layout,
                working,
                train_features[kept],
                train_targets[kept],
                consequents,
                step_data,
                warm,
            )
            phi, kept, _dropped = self._design_matrix(working, train_features)
            if not np.any(kept):
                raise ValueError("every training row has zero firing strength")
            consequents, _condition_number = self._solve_consequents(
                phi, train_targets[kept], working, data, kept, warm
            )
            loss_history[-1] = self._loss(
                working,
                train_features[kept],
                train_targets[kept],
                consequents,
                None if data.weights is None else data.weights[kept],
            )
            epochs_run += 1
            if validation_features is not None and validation_targets is not None:
                _validation_phi, validation_kept, _validation_dropped = self._design_matrix(
                    working, validation_features
                )
                if not np.any(validation_kept):
                    raise ValueError("every validation row has zero firing strength")
                validation_loss = self._loss(
                    working,
                    validation_features[validation_kept],
                    validation_targets[validation_kept],
                    consequents,
                    None if validation_weights is None else validation_weights[validation_kept],
                )
                if validation_loss < best_validation_loss:
                    best_validation_loss = validation_loss
                    best_premise = layout.flatten()
                    epochs_without_improvement = 0
                else:
                    epochs_without_improvement += 1
                    if epochs_without_improvement >= self.patience:
                        early_stopped = True
                        break
        if best_premise is not None:
            layout.set_flat(best_premise)
        phi, kept, _dropped = self._design_matrix(working, train_features)
        if not np.any(kept):
            raise ValueError("every training row has zero firing strength")
        consequents, lse_condition_number = self._solve_consequents(
            phi, train_targets[kept], working, data, kept, warm
        )
        fitted = self._rebuild(working, consequents, target_stats, feature_stats)
        self._raw_memberships(fitted, feature_stats)
        self._assert_finite_parameters(fitted)
        evaluation_sets = [data] if self.validation is None else [data, self.validation]
        self._assert_finite_outputs(fitted, evaluation_sets)
        train_rmse, dropped_train = self._rmse(fitted, data)
        validation_rmse = None
        dropped_validation = 0
        if self.validation is not None:
            validation_rmse, dropped_validation = self._rmse(fitted, self.validation)
        count = self._parameter_count(fitted)
        diagnostics = TrainingDiagnostics(
            clip_binding_rate=0.0,
            zero_firing_rows_dropped=dropped_train + dropped_validation,
            nonfinite_rows_rejected=0,
            lse_condition_number=lse_condition_number,
            premise_steps_rejected=rejected_steps,
            epochs_run=epochs_run,
            early_stopped=early_stopped,
            standardization=(
                feature_stats[0].copy(),
                feature_stats[1].copy(),
                target_stats[0].copy(),
                target_stats[1].copy(),
            ),
        )
        return TrainingResult(
            fitted, train_rmse, validation_rmse, tuple(loss_history), diagnostics, count
        )

    @staticmethod
    def _validate_dimensions(rule_base: TSKRuleBase, data: TrainingSet) -> None:
        if data.input_dim != rule_base.input_dim:
            raise ValueError("training feature dimension does not match rule base")
        if data.output_dim != rule_base.output_dim:
            raise ValueError("training target dimension does not match rule base")

    @staticmethod
    def _assert_finite_parameters(rule_base: TSKRuleBase) -> None:
        """Reject a non-finite model before it can reach channel projection."""
        if not np.all(np.isfinite(premise_layout(rule_base).flatten())):
            raise ValueError("rule base contains non-finite membership parameters")
        if any(not np.all(np.isfinite(rule.consequent_params)) for rule in rule_base.rules):
            raise ValueError("rule base contains non-finite consequent parameters")

    @staticmethod
    def _assert_finite_outputs(rule_base: TSKRuleBase, datasets: list[TrainingSet]) -> None:
        """Reject a fitted rule base with non-finite raw outputs on fit rows."""
        for data in datasets:
            for feature in data.features:
                firing = rule_base.evaluate(feature)
                weights = HybridANFISTrainer._effective_weights(firing)
                if not np.any(weights):
                    continue
                output = weights @ firing.consequent_outputs
                if not np.all(np.isfinite(output)):
                    raise ValueError("fitted rule base produced a non-finite output")

    @staticmethod
    def _standardize(
        data: TrainingSet,
    ) -> tuple[
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
        tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    ]:
        feature_mean = np.mean(data.features, axis=0)
        feature_scale = np.std(data.features, axis=0)
        target_mean = np.mean(data.targets, axis=0)
        target_scale = np.std(data.targets, axis=0)
        feature_scale = np.where(feature_scale == 0.0, 1.0, feature_scale)
        target_scale = np.where(target_scale == 0.0, 1.0, target_scale)
        return (
            (data.features - feature_mean) / feature_scale,
            (data.targets - target_mean) / target_scale,
            (feature_mean, feature_scale),
            (target_mean, target_scale),
        )

    @staticmethod
    def _effective_weights(firing: RuleFiringResult) -> npt.NDArray[np.float64]:
        if firing.is_interval_type2:
            assert firing.firing_strengths_lower is not None
            assert firing.firing_strengths_upper is not None
            lower_total = float(firing.firing_strengths_lower.sum())
            upper_total = float(firing.firing_strengths_upper.sum())
            if lower_total == 0.0 or upper_total == 0.0:
                return np.zeros(firing.n_rules, dtype=np.float64)
            return 0.5 * (
                firing.firing_strengths_lower / lower_total
                + firing.firing_strengths_upper / upper_total
            )
        total = float(firing.firing_strengths.sum())
        if total == 0.0:
            return np.zeros(firing.n_rules, dtype=np.float64)
        return firing.firing_strengths / total

    @staticmethod
    def _standardize_memberships(
        rule_base: TSKRuleBase,
        feature_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    ) -> None:
        means, scales = feature_stats
        seen: set[int] = set()
        for rule in rule_base.rules:
            for index, mf in enumerate(rule.antecedent_mfs):
                if id(mf) in seen:
                    continue
                seen.add(id(mf))
                mean = float(means[index])
                scale = float(scales[index])
                params = mf.parameters()
                if isinstance(mf, GaussianMF):
                    transformed = np.array([(params[0] - mean) / scale, params[1] / scale])
                elif isinstance(mf, (TriangularMF, TrapezoidalMF)):
                    transformed = (params - mean) / scale
                elif isinstance(mf, TanhMF):
                    transformed = np.array(
                        [
                            (params[0] - mean) / scale,
                            (params[1] - mean) / scale,
                            params[2] * scale,
                            params[3] * scale,
                        ]
                    )
                elif isinstance(mf, IntervalGaussianMF):
                    transformed = np.array(
                        [(params[0] - mean) / scale, params[1] / scale, params[2] / scale]
                    )
                elif isinstance(mf, TanhSigmoidMF):
                    transformed = np.array([(params[0] - mean) / scale, params[1] * scale])
                elif isinstance(mf, TanhBellMF):
                    transformed = np.array(
                        [(params[0] - mean) / scale, (params[1] - mean) / scale, params[2] * scale]
                    )
                else:
                    raise TypeError(f"unsupported membership function: {type(mf).__name__}")
                mf.set_parameters(np.asarray(transformed, dtype=np.float64))

    @staticmethod
    def _raw_memberships(
        rule_base: TSKRuleBase,
        feature_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    ) -> None:
        means, scales = feature_stats
        layout = premise_layout(rule_base)
        for mf, index in zip(layout.mfs, layout.input_indices, strict=True):
            mean = float(means[index])
            scale = float(scales[index])
            params = mf.parameters()
            if isinstance(mf, GaussianMF):
                transformed = np.array([params[0] * scale + mean, params[1] * scale])
            elif isinstance(mf, (TriangularMF, TrapezoidalMF)):
                transformed = params * scale + mean
            elif isinstance(mf, TanhMF):
                transformed = np.array(
                    [
                        params[0] * scale + mean,
                        params[1] * scale + mean,
                        params[2] / scale,
                        params[3] / scale,
                    ]
                )
            elif isinstance(mf, IntervalGaussianMF):
                transformed = np.array(
                    [params[0] * scale + mean, params[1] * scale, params[2] * scale]
                )
            elif isinstance(mf, TanhSigmoidMF):
                transformed = np.array([params[0] * scale + mean, params[1] / scale])
            elif isinstance(mf, TanhBellMF):
                transformed = np.array(
                    [params[0] * scale + mean, params[1] * scale + mean, params[2] / scale]
                )
            else:
                raise TypeError(f"unsupported membership function: {type(mf).__name__}")
            mf.set_parameters(np.asarray(transformed, dtype=np.float64))

    def _design_matrix(
        self,
        rule_base: TSKRuleBase,
        features: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_], int]:
        blocks: list[npt.NDArray[np.float64]] = []
        kept = np.zeros(features.shape[0], dtype=bool)
        zero_rows = 0
        for row, feature in enumerate(features):
            firing = rule_base.evaluate(feature)
            weights = self._effective_weights(firing)
            if not np.any(weights):
                zero_rows += 1
                continue
            augmented = np.append(feature, 1.0)
            blocks.append(np.concatenate([weight * augmented for weight in weights]))
            kept[row] = True
        return np.asarray(blocks, dtype=np.float64), kept, zero_rows

    def _solve_consequents(
        self,
        phi: npt.NDArray[np.float64],
        targets: npt.NDArray[np.float64],
        rule_base: TSKRuleBase,
        data: TrainingSet,
        kept: npt.NDArray[np.bool_],
        warm_start: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], float]:
        columns = rule_base.n_rules * (rule_base.input_dim + 1)
        if self.ridge == 0.0:
            augmented_phi = phi.copy()
            augmented_targets = targets.copy()
        else:
            augmented_phi = np.vstack([phi, np.sqrt(self.ridge) * np.eye(columns)])
            ridge_targets = warm_start.transpose(1, 2, 0).reshape(columns, rule_base.output_dim)
            augmented_targets = np.vstack([targets, np.sqrt(self.ridge) * ridge_targets])
        if data.weights is not None:
            row_weights = np.sqrt(data.weights[kept])[:, None]
            augmented_phi[: len(targets)] *= row_weights
            augmented_targets[: len(targets)] *= row_weights
        solution, *_ = np.linalg.lstsq(augmented_phi, augmented_targets, rcond=None)
        condition_number = float(np.linalg.cond(augmented_phi))
        reshaped = solution.T.reshape(
            rule_base.output_dim, rule_base.n_rules, rule_base.input_dim + 1
        )
        return cast(npt.NDArray[np.float64], reshaped), condition_number

    @staticmethod
    def _standardize_consequents(
        rule_base: TSKRuleBase,
        feature_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
        target_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    ) -> npt.NDArray[np.float64]:
        feature_mean, feature_scale = feature_stats
        target_mean, target_scale = target_stats
        standardized = np.empty(
            (rule_base.output_dim, rule_base.n_rules, rule_base.input_dim + 1), dtype=np.float64
        )
        for index, rule in enumerate(rule_base.rules):
            raw = rule.consequent_params
            standardized[:, index, :-1] = raw[:, :-1] * feature_scale / target_scale[:, None]
            standardized[:, index, -1] = (raw[:, -1] - target_mean) / target_scale + np.sum(
                standardized[:, index, :-1] * feature_mean / feature_scale,
                axis=1,
            )
        return standardized

    def _premise_step(
        self,
        layout: PremiseLayout,
        rule_base: TSKRuleBase,
        features: npt.NDArray[np.float64],
        targets: npt.NDArray[np.float64],
        consequents: npt.NDArray[np.float64],
        data: TrainingSet,
        warm_start: npt.NDArray[np.float64],
    ) -> int:
        values = layout.flatten()
        if values.size == 0:
            return 0
        positive = self._positive_parameter_mask(layout)
        optimization_values = values.copy()
        optimization_values[positive] = np.log(optimization_values[positive])
        base_loss = self._loss(rule_base, features, targets, consequents, data.weights)
        gradient = np.zeros_like(optimization_values)
        for index in range(optimization_values.size):
            step = self.fd_step * max(1.0, abs(float(optimization_values[index])))
            plus = optimization_values.copy()
            plus[index] += step
            minus = optimization_values.copy()
            minus[index] -= step
            plus_loss = self._trial_loss(
                layout,
                self._from_optimization(plus, positive),
                rule_base,
                features,
                targets,
                consequents,
                data.weights,
            )
            minus_loss = self._trial_loss(
                layout,
                self._from_optimization(minus, positive),
                rule_base,
                features,
                targets,
                consequents,
                data.weights,
            )
            if plus_loss is not None and minus_loss is not None:
                gradient[index] = (plus_loss - minus_loss) / (2.0 * step)
            elif plus_loss is not None:
                gradient[index] = (plus_loss - base_loss) / step
            elif minus_loss is not None:
                gradient[index] = (base_loss - minus_loss) / step
        learning_rate = self.premise_lr
        for _ in range(self.max_halvings + 1):
            try:
                proposal = self._from_optimization(
                    optimization_values - learning_rate * gradient, positive
                )
                layout.set_flat(proposal)
                phi, kept, _dropped = self._design_matrix(rule_base, features)
                if not np.all(kept):
                    raise ValueError("premise proposal caused a zero-firing training row")
                trial_consequents, _condition_number = self._solve_consequents(
                    phi, targets[kept], rule_base, data, kept, warm_start
                )
                proposal_loss = self._loss(
                    rule_base,
                    features[kept],
                    targets[kept],
                    trial_consequents,
                    None if data.weights is None else data.weights[kept],
                )
                if proposal_loss < base_loss:
                    return 0
            except ValueError:
                pass
            layout.set_flat(values)
            learning_rate *= 0.5
        layout.set_flat(values)
        return 1

    @staticmethod
    def _trial_loss(
        layout: PremiseLayout,
        values: npt.NDArray[np.float64],
        rule_base: TSKRuleBase,
        features: npt.NDArray[np.float64],
        targets: npt.NDArray[np.float64],
        consequents: npt.NDArray[np.float64],
        weights: npt.NDArray[np.float64] | None,
    ) -> float | None:
        original = layout.flatten()
        try:
            layout.set_flat(values)
            return HybridANFISTrainer._loss(rule_base, features, targets, consequents, weights)
        except ValueError:
            return None
        finally:
            layout.set_flat(original)

    @staticmethod
    def _positive_parameter_mask(layout: PremiseLayout) -> npt.NDArray[np.bool_]:
        """Mark parameter entries whose MF contract requires strict positivity."""
        positive = np.zeros(layout.size, dtype=bool)
        for mf, offset in zip(layout.mfs, layout.offsets, strict=True):
            if isinstance(mf, GaussianMF):
                positive[offset + 1] = True
            elif isinstance(mf, IntervalGaussianMF):
                positive[offset + 1 : offset + 3] = True
            elif isinstance(mf, TanhMF):
                positive[offset + 2 : offset + 4] = True
            elif isinstance(mf, TanhSigmoidMF):
                positive[offset + 1] = True
            elif isinstance(mf, TanhBellMF):
                positive[offset + 2] = True
        return positive

    @staticmethod
    def _from_optimization(
        values: npt.NDArray[np.float64], positive: npt.NDArray[np.bool_]
    ) -> npt.NDArray[np.float64]:
        parameters = values.copy()
        parameters[positive] = np.exp(parameters[positive])
        return parameters

    @staticmethod
    def _loss(
        rule_base: TSKRuleBase,
        features: npt.NDArray[np.float64],
        targets: npt.NDArray[np.float64],
        consequents: npt.NDArray[np.float64],
        weights: npt.NDArray[np.float64] | None = None,
    ) -> float:
        predictions = []
        for feature in features:
            firing_weights = HybridANFISTrainer._effective_weights(rule_base.evaluate(feature))
            if not np.any(firing_weights):
                raise ValueError("cannot calculate loss with a zero-firing row")
            rule_outputs = consequents[:, :, :-1] @ feature + consequents[:, :, -1]
            predictions.append(rule_outputs @ firing_weights)
        predicted = np.asarray(predictions, dtype=np.float64)
        squared_residuals = (predicted - targets) ** 2
        if weights is None:
            return float(np.mean(squared_residuals))
        return float(np.average(squared_residuals, axis=0, weights=weights).mean())

    @staticmethod
    def _rebuild(
        rule_base: TSKRuleBase,
        standardized_consequents: npt.NDArray[np.float64],
        target_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
        feature_stats: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
    ) -> TSKRuleBase:
        target_mean, target_scale = target_stats
        feature_mean, feature_scale = feature_stats
        rules: list[TSKRule] = []
        for index, rule in enumerate(rule_base.rules):
            standardized = standardized_consequents[:, index, :]
            raw = np.empty_like(standardized)
            raw[:, :-1] = standardized[:, :-1] * target_scale[:, None] / feature_scale[None, :]
            raw[:, -1] = (
                target_scale
                * (
                    standardized[:, -1]
                    - np.sum(
                        standardized[:, :-1] * feature_mean[None, :] / feature_scale[None, :],
                        axis=1,
                    )
                )
                + target_mean
            )
            rules.append(TSKRule(rule.antecedent_mfs, raw))
        return TSKRuleBase(rules, rule_base.input_dim, rule_base.output_dim)

    @staticmethod
    def _rmse(rule_base: TSKRuleBase, data: TrainingSet) -> tuple[npt.NDArray[np.float64], int]:
        predictions: list[npt.NDArray[np.float64]] = []
        kept_targets: list[npt.NDArray[np.float64]] = []
        dropped = 0
        for feature in data.features:
            firing = rule_base.evaluate(feature)
            weights = HybridANFISTrainer._effective_weights(firing)
            if not np.any(weights):
                dropped += 1
                continue
            predictions.append(weights @ firing.consequent_outputs)
            kept_targets.append(data.targets[len(predictions) + dropped - 1])
        if not predictions:
            raise ValueError("every evaluation row has zero firing strength")
        prediction_array = np.asarray(predictions, dtype=np.float64)
        target_array = np.asarray(kept_targets, dtype=np.float64)
        residual = prediction_array - target_array
        return cast(npt.NDArray[np.float64], np.sqrt(np.mean(residual**2, axis=0))), dropped

    @staticmethod
    def _parameter_count(rule_base: TSKRuleBase) -> ParameterCount:
        premise = premise_layout(rule_base).size
        consequent = sum(rule.consequent_params.size for rule in rule_base.rules)
        return ParameterCount(int(premise), int(consequent), int(premise + consequent))
