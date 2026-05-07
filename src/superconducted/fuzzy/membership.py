"""Concrete :class:`MembershipFunction` shapes.

Bootstrap ships Gaussian, Triangular, Trapezoidal, Tanh-based (advisor's
first-priority test), and IntervalGaussian (IT2). All implementations
expose a flat ``parameters() / set_parameters()`` interface so the future
ANFIS trainer can manipulate premise parameters via a generic optimizer.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from ..interfaces import MembershipFunction
from ..types import MembershipDegree


class GaussianMF(MembershipFunction):
    """Gaussian MF parameterized by center ``c`` and width ``sigma > 0``.

    ``mu(x) = exp(-((x - c) / sigma) ** 2 / 2)``. Parameter vector
    ``[c, sigma]``.
    """

    def __init__(self, center: float, sigma: float) -> None:
        if sigma <= 0:
            raise ValueError(f"GaussianMF requires sigma > 0; got {sigma}")
        self._center = float(center)
        self._sigma = float(sigma)

    def degree(self, x: float) -> MembershipDegree:
        delta = float(x) - self._center
        value = math.exp(-0.5 * (delta / self._sigma) ** 2)
        return MembershipDegree.crisp(value)

    def parameters(self) -> npt.NDArray[np.float64]:
        return np.array([self._center, self._sigma], dtype=np.float64)

    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        if params.shape != (2,):
            raise ValueError(f"GaussianMF expects 2 params; got shape {params.shape}")
        sigma = float(params[1])
        if sigma <= 0:
            raise ValueError(f"GaussianMF requires sigma > 0; got {sigma}")
        self._center = float(params[0])
        self._sigma = sigma

    @property
    def parameter_count(self) -> int:
        return 2

    @property
    def is_interval_type2(self) -> bool:
        return False


class TriangularMF(MembershipFunction):
    """Triangular MF with feet ``a < b < c`` and peak at ``b``.

    Parameter vector ``[a, b, c]``. Returns 0 outside ``[a, c]``.
    """

    def __init__(self, a: float, b: float, c: float) -> None:
        self._validate(a, b, c)
        self._a = float(a)
        self._b = float(b)
        self._c = float(c)

    @staticmethod
    def _validate(a: float, b: float, c: float) -> None:
        if not (a < b < c):
            raise ValueError(f"TriangularMF requires a < b < c; got a={a}, b={b}, c={c}")

    def degree(self, x: float) -> MembershipDegree:
        x = float(x)
        if x <= self._a or x >= self._c:
            return MembershipDegree.crisp(0.0)
        if x <= self._b:
            return MembershipDegree.crisp((x - self._a) / (self._b - self._a))
        return MembershipDegree.crisp((self._c - x) / (self._c - self._b))

    def parameters(self) -> npt.NDArray[np.float64]:
        return np.array([self._a, self._b, self._c], dtype=np.float64)

    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        if params.shape != (3,):
            raise ValueError(f"TriangularMF expects 3 params; got shape {params.shape}")
        a, b, c = float(params[0]), float(params[1]), float(params[2])
        self._validate(a, b, c)
        self._a, self._b, self._c = a, b, c

    @property
    def parameter_count(self) -> int:
        return 3

    @property
    def is_interval_type2(self) -> bool:
        return False


class TrapezoidalMF(MembershipFunction):
    """Trapezoidal MF with feet ``a < d`` and plateau ``b <= x <= c``.

    Parameter vector ``[a, b, c, d]`` with ``a < b <= c < d``.
    """

    def __init__(self, a: float, b: float, c: float, d: float) -> None:
        self._validate(a, b, c, d)
        self._a = float(a)
        self._b = float(b)
        self._c = float(c)
        self._d = float(d)

    @staticmethod
    def _validate(a: float, b: float, c: float, d: float) -> None:
        if not (a < b <= c < d):
            raise ValueError(
                f"TrapezoidalMF requires a < b <= c < d; got a={a}, b={b}, c={c}, d={d}"
            )

    def degree(self, x: float) -> MembershipDegree:
        x = float(x)
        if x <= self._a or x >= self._d:
            return MembershipDegree.crisp(0.0)
        if x < self._b:
            return MembershipDegree.crisp((x - self._a) / (self._b - self._a))
        if x <= self._c:
            return MembershipDegree.crisp(1.0)
        return MembershipDegree.crisp((self._d - x) / (self._d - self._c))

    def parameters(self) -> npt.NDArray[np.float64]:
        return np.array([self._a, self._b, self._c, self._d], dtype=np.float64)

    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        if params.shape != (4,):
            raise ValueError(f"TrapezoidalMF expects 4 params; got shape {params.shape}")
        a, b, c, d = (float(params[i]) for i in range(4))
        self._validate(a, b, c, d)
        self._a, self._b, self._c, self._d = a, b, c, d

    @property
    def parameter_count(self) -> int:
        return 4

    @property
    def is_interval_type2(self) -> bool:
        return False


class TanhMF(MembershipFunction):
    """Tanh-based MF — the advisor's first-priority shape for benchmarking.

    Constructed from a difference of two sigmoid-like tanh functions::

        mu(x) = clip(0.5 * (tanh(s_L * (x - L)) - tanh(s_R * (x - R))), 0, 1)

    With ``L < R`` and positive slopes the result peaks near 1 between
    ``L`` and ``R`` and decays to 0 outside; large slopes approach a
    rectangular pulse, small slopes approach a smooth bump. Parameter
    vector ``[left, right, slope_left, slope_right]``.
    """

    def __init__(
        self,
        left: float,
        right: float,
        slope_left: float,
        slope_right: float,
    ) -> None:
        self._validate(left, right, slope_left, slope_right)
        self._left = float(left)
        self._right = float(right)
        self._slope_left = float(slope_left)
        self._slope_right = float(slope_right)

    @staticmethod
    def _validate(left: float, right: float, slope_left: float, slope_right: float) -> None:
        if not (left < right):
            raise ValueError(f"TanhMF requires left < right; got {left}, {right}")
        if slope_left <= 0 or slope_right <= 0:
            raise ValueError(
                f"TanhMF requires positive slopes; got slope_left={slope_left}, "
                f"slope_right={slope_right}"
            )

    def degree(self, x: float) -> MembershipDegree:
        x = float(x)
        raw = 0.5 * (
            math.tanh(self._slope_left * (x - self._left))
            - math.tanh(self._slope_right * (x - self._right))
        )
        clipped = max(0.0, min(1.0, raw))
        return MembershipDegree.crisp(clipped)

    def parameters(self) -> npt.NDArray[np.float64]:
        return np.array(
            [self._left, self._right, self._slope_left, self._slope_right],
            dtype=np.float64,
        )

    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        if params.shape != (4,):
            raise ValueError(f"TanhMF expects 4 params; got shape {params.shape}")
        left, right, sl, sr = (float(params[i]) for i in range(4))
        self._validate(left, right, sl, sr)
        self._left, self._right, self._slope_left, self._slope_right = left, right, sl, sr

    @property
    def parameter_count(self) -> int:
        return 4

    @property
    def is_interval_type2(self) -> bool:
        return False


class IntervalGaussianMF(MembershipFunction):
    """Interval Type-2 Gaussian MF with uncertain width.

    Footprint of uncertainty: lower/upper Gaussians sharing the same center
    but with ``sigma_low < sigma_high``. At the center both equal 1; off
    center the narrower sigma decays faster, so it forms the lower bound::

        mu_low(x)  = exp(-((x - c) / sigma_low) ** 2 / 2)
        mu_high(x) = exp(-((x - c) / sigma_high) ** 2 / 2)

    Parameter vector ``[c, sigma_low, sigma_high]``.
    """

    def __init__(self, center: float, sigma_low: float, sigma_high: float) -> None:
        self._validate(sigma_low, sigma_high)
        self._center = float(center)
        self._sigma_low = float(sigma_low)
        self._sigma_high = float(sigma_high)

    @staticmethod
    def _validate(sigma_low: float, sigma_high: float) -> None:
        if sigma_low <= 0:
            raise ValueError(f"IntervalGaussianMF requires sigma_low > 0; got {sigma_low}")
        if sigma_high <= sigma_low:
            raise ValueError(
                f"IntervalGaussianMF requires sigma_low < sigma_high; "
                f"got sigma_low={sigma_low}, sigma_high={sigma_high}"
            )

    def degree(self, x: float) -> MembershipDegree:
        delta = float(x) - self._center
        mu_low = math.exp(-0.5 * (delta / self._sigma_low) ** 2)
        mu_high = math.exp(-0.5 * (delta / self._sigma_high) ** 2)
        if mu_low > mu_high:
            mu_low, mu_high = mu_high, mu_low
        return MembershipDegree(low=mu_low, high=mu_high)

    def parameters(self) -> npt.NDArray[np.float64]:
        return np.array([self._center, self._sigma_low, self._sigma_high], dtype=np.float64)

    def set_parameters(self, params: npt.NDArray[np.float64]) -> None:
        if params.shape != (3,):
            raise ValueError(f"IntervalGaussianMF expects 3 params; got shape {params.shape}")
        sigma_low = float(params[1])
        sigma_high = float(params[2])
        self._validate(sigma_low, sigma_high)
        self._center = float(params[0])
        self._sigma_low = sigma_low
        self._sigma_high = sigma_high

    @property
    def parameter_count(self) -> int:
        return 3

    @property
    def is_interval_type2(self) -> bool:
        return True
