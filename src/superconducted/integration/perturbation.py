"""Member perturbations for the Aer ensemble.

A perturbation is what makes the members of a
:class:`~superconducted.integration.aer_factory.FuzzyNoiseModelEnsemble`
differ (ADR-015, Issue #64). Each one implements
:class:`~superconducted.interfaces.MemberPerturbation`: given a member's index
and that member's own random generator, it returns the feature extractor,
rule base and defuzzifier the member is built from.

Status:

- :class:`IdentityPerturbation` — full. The default: members are identical,
  as they were before Issue #64.
"""

from __future__ import annotations

import numpy as np

from ..interfaces import (
    CalibrationFeatureExtractor,
    Defuzzifier,
    MemberPerturbation,
    RuleBase,
)


class IdentityPerturbation(MemberPerturbation):
    """Return the three dependencies unchanged, so every member is the same model.

    This is what the ensemble uses when it is given no perturbation, and it
    is the regression guard for Issue #64: under it the ensemble yields the
    members it yielded before the perturbation slot existed, and the
    density-matrix identity ``rho_ens == rho_1`` of Issue #58 still holds.
    """

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        """Return ``(feature_extractor, rule_base, defuzzifier)`` as given.

        The returned objects are the inputs themselves, not copies. ``index``
        is ignored and ``rng`` is not read, so an ensemble under this
        perturbation needs no seed. No side effects.
        """
        return feature_extractor, rule_base, defuzzifier
