"""Deterministic premise-parameter layout for TSK rule bases."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from ..fuzzy.tsk import TSKRuleBase
from ..interfaces import MembershipFunction, RuleBase
from .types import ParameterCount


@dataclass(frozen=True, slots=True)
class PremiseLayout:
    """Ordered unique MF objects and their flat-vector offsets."""

    mfs: tuple[MembershipFunction, ...]
    input_indices: tuple[int, ...]
    offsets: tuple[int, ...]
    size: int

    def flatten(self) -> npt.NDArray[np.float64]:
        """Return the current parameters in first-encounter order."""
        if not self.mfs:
            return np.empty(0, dtype=np.float64)
        return np.concatenate([mf.parameters() for mf in self.mfs]).astype(np.float64)

    def set_flat(self, values: npt.NDArray[np.float64]) -> None:
        """Set all parameters, allowing each MF to validate its own domain."""
        vector = np.asarray(values, dtype=np.float64)
        if vector.shape != (self.size,):
            raise ValueError(f"premise vector must have shape ({self.size},); got {vector.shape}")
        original = self.flatten()
        try:
            for mf, offset in zip(self.mfs, self.offsets, strict=True):
                end = offset + mf.parameter_count
                mf.set_parameters(vector[offset:end])
        except ValueError:
            for mf, offset in zip(self.mfs, self.offsets, strict=True):
                end = offset + mf.parameter_count
                mf.set_parameters(original[offset:end])
            raise


def premise_layout(rule_base: TSKRuleBase) -> PremiseLayout:
    """Enumerate unique MFs once, preserving rule and antecedent order."""
    mfs: list[MembershipFunction] = []
    input_indices: list[int] = []
    seen: dict[int, tuple[MembershipFunction, int]] = {}
    for rule in rule_base.rules:
        for input_index, mf in enumerate(rule.antecedent_mfs):
            existing = seen.get(id(mf))
            if existing is not None:
                if existing[1] != input_index:
                    raise ValueError(
                        "one MF object cannot be used at multiple input indices: "
                        f"object {id(mf)} appears at {existing[1]} and {input_index}"
                    )
                continue
            seen[id(mf)] = (mf, input_index)
            mfs.append(mf)
            input_indices.append(input_index)
    offsets: list[int] = []
    cursor = 0
    for mf in mfs:
        offsets.append(cursor)
        cursor += mf.parameter_count
    return PremiseLayout(tuple(mfs), tuple(input_indices), tuple(offsets), cursor)


def count_trainable_parameters(rule_base: RuleBase) -> ParameterCount:
    """Count unique premise and per-rule consequent parameters of a TSK model."""
    if not isinstance(rule_base, TSKRuleBase):
        raise TypeError("count_trainable_parameters requires a TSKRuleBase")
    premise = sum(membership.parameter_count for membership in premise_layout(rule_base).mfs)
    consequent = sum(rule.consequent_params.size for rule in rule_base.rules)
    return ParameterCount(premise=premise, consequent=consequent, total=premise + consequent)
