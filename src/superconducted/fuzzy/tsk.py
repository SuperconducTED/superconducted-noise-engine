"""LOCKED. Takagi-Sugeno-Kang inference engine.

Modifying the inference math requires an ADR in ``docs/decisions.md`` and
sign-off from both leads. The trainer (hybrid recursive-LSE for
consequents + SGD for premise MF parameters, ANFIS-style) is intentionally
NOT in this module at bootstrap; it lands via ADR-014.

Math reference (also documented in ``docs/architecture.md``):

- **Firing strength** (T-norm = product): for a rule with antecedent MFs
  ``mf_1, ..., mf_d`` and inputs ``x_1, ..., x_d``::

      f = prod_i mf_i.degree(x_i).low                 # T1 OR IT2 lower bound
      f_high = prod_i mf_i.degree(x_i).high           # IT2 upper bound only

- **Linear consequent** (TSK first order): for a rule with parameter
  matrix ``A`` of shape ``(output_dim, input_dim + 1)``::

      y = A @ [x_1, ..., x_d, 1]^T

- **Defuzzification** is performed elsewhere (T1 weighted average,
  IT2 Nie-Tan); see :mod:`superconducted.fuzzy.defuzzification`.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import product

import numpy as np
import numpy.typing as npt

from ..interfaces import MembershipFunction, RuleBase
from ..types import RuleFiringResult


class TSKRule:
    """A single TSK rule.

    Antecedent: a sequence of :class:`MembershipFunction` objects, one
    per input dimension. Consequent: linear-in-input vector with bias::

        y = consequent_params @ [x_1, ..., x_d, 1]^T

    ``consequent_params`` shape: ``(output_dim, input_dim + 1)``.
    """

    def __init__(
        self,
        antecedent_mfs: Sequence[MembershipFunction],
        consequent_params: npt.NDArray[np.float64],
    ) -> None:
        if len(antecedent_mfs) == 0:
            raise ValueError("TSKRule requires at least one antecedent MF")
        params = np.asarray(consequent_params, dtype=np.float64)
        if params.ndim != 2:
            raise ValueError(f"TSKRule consequent_params must be 2-D; got shape {params.shape}")
        if params.shape[1] != len(antecedent_mfs) + 1:
            raise ValueError(
                f"TSKRule consequent_params.shape[1] ({params.shape[1]}) must equal "
                f"input_dim + 1 ({len(antecedent_mfs) + 1})"
            )
        self._antecedent_mfs = tuple(antecedent_mfs)
        self._consequent_params = params

    def firing_strength(self, inputs: npt.NDArray[np.float64]) -> tuple[float, float]:
        """Product T-norm over per-input MF degrees. Returns ``(low, high)``.

        For T1 antecedents, ``low == high``. For IT2 antecedents (any one
        IT2 MF in the rule), ``low <= high``.
        """
        low, high = 1.0, 1.0
        for mf, x in zip(self._antecedent_mfs, inputs, strict=True):
            d = mf.degree(float(x))
            low *= d.low
            high *= d.high
        return low, high

    def consequent(self, inputs: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Linear consequent ``A @ [inputs; 1]`` of shape ``(output_dim,)``."""
        x_aug = np.empty(len(self._antecedent_mfs) + 1, dtype=np.float64)
        x_aug[:-1] = inputs
        x_aug[-1] = 1.0
        return np.asarray(self._consequent_params @ x_aug, dtype=np.float64)

    @property
    def input_dim(self) -> int:
        return len(self._antecedent_mfs)

    @property
    def output_dim(self) -> int:
        return int(self._consequent_params.shape[0])

    @property
    def is_interval_type2(self) -> bool:
        return any(mf.is_interval_type2 for mf in self._antecedent_mfs)

    @property
    def antecedent_mfs(self) -> tuple[MembershipFunction, ...]:
        return self._antecedent_mfs

    @property
    def consequent_params(self) -> npt.NDArray[np.float64]:
        return self._consequent_params


class TSKRuleBase(RuleBase):
    """Concrete TSK rule base.

    Holds a fixed sequence of :class:`TSKRule` instances; ``evaluate``
    iterates them, computes firing strengths and consequent outputs, and
    returns a :class:`RuleFiringResult`. The defuzzifier (chosen
    separately) consumes that result.
    """

    def __init__(
        self,
        rules: Sequence[TSKRule],
        input_dim: int,
        output_dim: int,
    ) -> None:
        if not rules:
            raise ValueError("TSKRuleBase requires at least one rule")
        for i, r in enumerate(rules):
            if r.input_dim != input_dim:
                raise ValueError(f"Rule {i} has input_dim={r.input_dim}; expected {input_dim}")
            if r.output_dim != output_dim:
                raise ValueError(f"Rule {i} has output_dim={r.output_dim}; expected {output_dim}")
        self._rules: tuple[TSKRule, ...] = tuple(rules)
        self._input_dim = int(input_dim)
        self._output_dim = int(output_dim)
        self._is_it2 = any(r.is_interval_type2 for r in self._rules)

    def evaluate(self, inputs: npt.NDArray[np.float64]) -> RuleFiringResult:
        if inputs.shape != (self._input_dim,):
            raise ValueError(
                f"TSKRuleBase.evaluate expects inputs shape ({self._input_dim},); "
                f"got {inputs.shape}"
            )
        n = len(self._rules)
        firing_low = np.empty(n, dtype=np.float64)
        firing_high = np.empty(n, dtype=np.float64)
        consequents = np.empty((n, self._output_dim), dtype=np.float64)
        for i, rule in enumerate(self._rules):
            low, high = rule.firing_strength(inputs)
            firing_low[i] = low
            firing_high[i] = high
            consequents[i] = rule.consequent(inputs)
        if self._is_it2:
            firing_mid = 0.5 * (firing_low + firing_high)
            return RuleFiringResult(
                firing_strengths=firing_mid,
                consequent_outputs=consequents,
                firing_strengths_lower=firing_low,
                firing_strengths_upper=firing_high,
            )
        return RuleFiringResult(
            firing_strengths=firing_low,
            consequent_outputs=consequents,
            firing_strengths_lower=None,
            firing_strengths_upper=None,
        )

    @property
    def n_rules(self) -> int:
        return len(self._rules)

    @property
    def input_dim(self) -> int:
        return self._input_dim

    @property
    def output_dim(self) -> int:
        return self._output_dim

    @property
    def is_interval_type2(self) -> bool:
        return self._is_it2

    @property
    def rules(self) -> tuple[TSKRule, ...]:
        return self._rules

    @classmethod
    def from_grid(
        cls,
        per_input_mfs: Sequence[Sequence[MembershipFunction]],
        output_dim: int,
        consequent_init: str = "zeros",
        rng: np.random.Generator | None = None,
    ) -> TSKRuleBase:
        """Build a Cartesian-product rule base.

        Given ``K_i`` MFs per input variable ``i``, the resulting rule base
        contains ``prod_i K_i`` rules — one per Cartesian-product
        combination. Consequents are initialized to zeros (default) or
        small Gaussian-random values (``consequent_init="random"``) for
        SGD warm-start.
        """
        if not per_input_mfs:
            raise ValueError("from_grid requires at least one input dimension")
        for i, mfs in enumerate(per_input_mfs):
            if not mfs:
                raise ValueError(f"Input dimension {i} has no MFs")
        input_dim = len(per_input_mfs)
        if consequent_init not in {"zeros", "random"}:
            raise ValueError(
                f"consequent_init must be 'zeros' or 'random'; got {consequent_init!r}"
            )
        if consequent_init == "random" and rng is None:
            rng = np.random.default_rng()
        rules: list[TSKRule] = []
        for combo in product(*per_input_mfs):
            params: npt.NDArray[np.float64]
            if consequent_init == "zeros":
                params = np.zeros((output_dim, input_dim + 1), dtype=np.float64)
            else:
                assert rng is not None
                params = np.asarray(
                    rng.standard_normal((output_dim, input_dim + 1)) * 0.1,
                    dtype=np.float64,
                )
            rules.append(TSKRule(combo, params))
        return cls(rules=rules, input_dim=input_dim, output_dim=output_dim)
