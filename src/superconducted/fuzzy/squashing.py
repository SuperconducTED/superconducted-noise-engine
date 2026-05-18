"""Concrete :class:`SquashingStrategy` implementations.

All three concretes are fully implemented at bootstrap. The TSK pipeline
output is a raw real-valued vector; squashing applies the constraint that
matches the noise-channel parameter (e.g., probabilities ∈ [0, 1] for
depolarizing strength).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from ..interfaces import SquashingStrategy


class IdentitySquashing(SquashingStrategy):
    """No-op pass-through.

    Use only when the caller guarantees the raw output already satisfies
    the downstream parameter constraints.
    """

    def squash(self, raw: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.asarray(raw, dtype=np.float64).copy()


class ProbabilityClip(SquashingStrategy):
    """Clip elementwise into ``[0, 1]``.

    Simple, non-differentiable. Suitable for inference; not ideal inside
    an SGD trainer because the gradient is zero outside the unit interval.
    """

    def squash(self, raw: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        arr = np.asarray(raw, dtype=np.float64)
        return np.clip(arr, 0.0, 1.0)


class SigmoidSquashing(SquashingStrategy):
    """Logistic sigmoid into ``(0, 1)``.

    ``sigmoid(x) = 1 / (1 + exp(-x))``. Differentiable everywhere, so
    SGD-friendly. Numerically stabilized to avoid overflow.
    """

    def squash(self, raw: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        arr = np.asarray(raw, dtype=np.float64)
        # Numerically stable form: sigmoid(x) = exp(-|x|) / (1 + exp(-|x|))
        # for x < 0, and 1 / (1 + exp(-x)) for x >= 0.
        out = np.empty_like(arr)
        positive = arr >= 0
        negative = ~positive
        out[positive] = 1.0 / (1.0 + np.exp(-arr[positive]))
        exp_x = np.exp(arr[negative])
        out[negative] = exp_x / (1.0 + exp_x)
        return out
