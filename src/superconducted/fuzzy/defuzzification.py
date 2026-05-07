"""Defuzzification strategies.

Both shipped concretes use closed-form formulas:

- :class:`WeightedAverageDefuzzifier` for Type-1 fuzzy results.
- :class:`NieTanDefuzzifier` for Interval Type-2 fuzzy results.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from ..interfaces import Defuzzifier
from ..types import RuleFiringResult


class WeightedAverageDefuzzifier(Defuzzifier):
    """T1 weighted-average defuzzification.

    For each output dimension ``d``::

        y_d = sum_k(firing_k * consequent_kd) / sum_k(firing_k)

    Raises :class:`ZeroDivisionError` if every firing strength is zero —
    the caller must decide what to do (typically: skip the snapshot or
    fall back to the nearest non-zero firing).
    """

    def defuzzify(self, firing: RuleFiringResult) -> npt.NDArray[np.float64]:
        firing_strengths = firing.firing_strengths
        consequents = firing.consequent_outputs
        total = float(firing_strengths.sum())
        if total == 0.0:
            raise ZeroDivisionError("WeightedAverageDefuzzifier received all-zero firing strengths")
        weighted = firing_strengths[:, None] * consequents
        return np.asarray(weighted.sum(axis=0) / total, dtype=np.float64)


class NieTanDefuzzifier(Defuzzifier):
    """IT2 Nie-Tan closed-form defuzzification.

    Average of the lower-bound and upper-bound T1 weighted averages::

        y = 0.5 * (sum_k(f_low_k * c_kd) / sum(f_low) +
                   sum_k(f_high_k * c_kd) / sum(f_high))

    Raises :class:`ValueError` if the firing result is not IT2; raises
    :class:`ZeroDivisionError` if either bound has all-zero firing.
    """

    def defuzzify(self, firing: RuleFiringResult) -> npt.NDArray[np.float64]:
        if not firing.is_interval_type2:
            raise ValueError("NieTanDefuzzifier requires an IT2 RuleFiringResult; got T1")
        lower = firing.firing_strengths_lower
        upper = firing.firing_strengths_upper
        assert lower is not None and upper is not None  # narrowed by is_interval_type2
        consequents = firing.consequent_outputs
        sum_low = float(lower.sum())
        sum_high = float(upper.sum())
        if sum_low == 0.0 or sum_high == 0.0:
            raise ZeroDivisionError(
                f"NieTanDefuzzifier received zero firing-strength sum "
                f"(lower={sum_low}, upper={sum_high})"
            )
        y_low = (lower[:, None] * consequents).sum(axis=0) / sum_low
        y_high = (upper[:, None] * consequents).sum(axis=0) / sum_high
        return np.asarray(0.5 * (y_low + y_high), dtype=np.float64)
