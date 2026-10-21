"""Karnik-Mendel reference type reducer for Issue #61 Part A (FR-1, FR-2).

Everything here works on one output dimension of one interval type-2 TSK
evaluation: per-rule firing bounds ``lower`` and ``upper`` (``0 <= lower <=
upper``) and crisp consequent values ``values``. The type-reduced set is the
interval ``[y_l, y_r]`` of every weighted average

    Y(w) = sum_r w_r values_r / sum_r w_r,   w_r free in [lower_r, upper_r],

and its midpoint ``(y_l + y_r) / 2`` is what the two closed-form reducers are
measured against.

The module lives in ``scripts/`` and never in ``src/``: ADR-011's "no iterative
numerical defuzzification at bootstrap" stands, and this is a reference that
judges the shipped reducer, not a replacement for it. The FR-3 sweep that uses it
lands in a later commit.

Two independent routes to the endpoints
---------------------------------------

Sort the rules by ``values`` ascending (a stable sort). For the left endpoint, a
*switch vertex* ``w(l, k)`` puts ``upper`` on the first ``k`` sorted rules and
``lower`` on the rest; ``w(r, k)`` is the mirror image. Then, exactly,

    y_l = min over k = 0..R of Y(w(l, k)),   y_r = max over k = 0..R of Y(w(r, k)).

Why: let ``y* = y_l``. ``Y(w) >= y*`` holds exactly when the linear function
``g(w) = sum_r w_r (values_r - y*)`` is non-negative, so ``min g = 0`` over the
box. ``g`` is minimised by the upper bound where ``values_r < y*`` and the lower
bound where ``values_r > y*``, which is a switch vertex, so that vertex attains
``y*``. The sources opened for #61 (Karnik & Mendel 2001, section 3.1; Wu & Mendel
2009) state the one-switch sign rule but not this minimum over switch points, so
it is derived here and in the #61 Part A findings. :func:`exhaustive_type_reduce`
evaluates it directly: ``R + 1`` weighted averages per endpoint.

:func:`karnik_mendel_type_reduce` is the iterative route (#61 section 6.3). From
``y`` it takes ``k = #{r : values_r <= y}``, evaluates the switch vertex, and
repeats. In exact arithmetic each step moves ``y`` monotonically towards the
endpoint and stops at it (``y' = y``, Karnik & Mendel 2001, step 4; equivalently
``k' = k``, Wu & Mendel 2009, EKM step 4).

The stop rule, and why it has a guard
-------------------------------------

Neither exact-arithmetic stop terminates reliably in float64. When firing is
concentrated on rules sharing (or nearly sharing) one consequent value, every
computed average rounds to that value or to one ulp beside it, ``k`` flips back
and forth, and the iteration cycles. The smallest case found has two rules and
two distinct values; ``tests/test_type_reduction.py`` pins it. So the iteration
here stops on whichever comes first:

1. ``k`` unchanged (the switch point, not float equality);
2. a step that fails to strictly improve ``y`` (the monotone guard). The better
   of the two values is returned.

Both are #61 owner decisions of 2026-10-21, recorded in
``docs/implementations/2026-10-21-type-reduction-reference.md``.

With the guard, accepted steps strictly improve ``y``, so ``k`` moves strictly
in one direction between evaluations (``k`` is a monotone function of ``y``),
and an endpoint takes at most ``R + 1`` evaluations. The FR-1 cap of
``R + 1`` passes therefore cannot be hit; it still raises ``RuntimeError``
rather than looping, in case that argument is ever broken by an edit. A guarded
stop can land within rounding of the endpoint rather than on the exact
minimiser; :func:`exhaustive_type_reduce` is the check on that.

The two closed-form reducers
----------------------------

- :func:`bmm_half_reduce` is the Biglarbegian-Melek-Mendel reducer with
  ``alpha = beta = 1/2``, ``(Y(lower) + Y(upper)) / 2``. It is what
  ``superconducted.fuzzy.defuzzification.NieTanDefuzzifier`` computes today.
- :func:`nie_tan_reduce` is textbook Nie-Tan, ``Y(lower + upper)`` (Wu & Mendel
  2019, Eq. 10). It is what ``WeightedAverageDefuzzifier`` computes on an IT2
  firing result, because ``TSKRuleBase.evaluate`` stores the midpoint firing.

Both lie in ``[y_l, y_r]``: ``lower``, ``upper`` and ``lower + upper`` (scaled)
are points of the box, and BMM averages two values that lie in the interval.

Contract shared by every public function
----------------------------------------

Inputs are 1-D, equal-length, finite arrays with at least one rule and
``0 <= lower <= upper`` elementwise; anything else raises ``ValueError``. A zero
``lower.sum()`` or ``upper.sum()`` raises ``ZeroDivisionError``, mirroring
``NieTanDefuzzifier.defuzzify``. The lower guard is load-bearing: every switch
vertex dominates ``lower`` elementwise, so ``lower.sum() > 0`` is exactly what
makes every evaluated average well defined. Every function is pure, allocates its
own arrays, and never returns NaN or inf for valid input.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class KarnikMendelResult:
    """Endpoints of the type-reduced interval with the iteration's diagnostics.

    ``passes_l`` and ``passes_r`` count switch-vertex evaluations per endpoint
    (the midpoint start is not counted); each is at most ``n_rules + 1``.
    ``guard_stops`` counts the endpoints (0, 1 or 2) whose iteration ended
    because a step moved ``y`` the wrong way, which can only happen through
    rounding.
    """

    y_l: float
    y_r: float
    passes_l: int
    passes_r: int
    guard_stops: int


def _validated(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Return float64 copies of the inputs after checking the shared contract."""
    lo = np.array(lower, dtype=np.float64)
    hi = np.array(upper, dtype=np.float64)
    c = np.array(values, dtype=np.float64)
    if lo.ndim != 1 or hi.ndim != 1 or c.ndim != 1:
        raise ValueError(
            f"lower, upper and values must be 1-D; got shapes {lo.shape}, {hi.shape}, {c.shape}"
        )
    if not lo.shape == hi.shape == c.shape:
        raise ValueError(
            f"lower, upper and values must have equal length; got {lo.size}, {hi.size}, {c.size}"
        )
    if lo.size == 0:
        raise ValueError("at least one rule is required")
    if not (np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)) and np.all(np.isfinite(c))):
        raise ValueError("lower, upper and values must be finite")
    if np.any(lo < 0.0):
        raise ValueError("lower firing bounds must be non-negative")
    if np.any(lo > hi):
        raise ValueError("lower firing bounds must not exceed upper firing bounds")
    sum_low = float(lo.sum())
    sum_high = float(hi.sum())
    if sum_low == 0.0 or sum_high == 0.0:
        raise ZeroDivisionError(
            f"type reduction received a zero firing-strength sum (lower={sum_low}, "
            f"upper={sum_high})"
        )
    return lo, hi, c


def _sorted_by_value(
    lower: FloatArray, upper: FloatArray, values: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Reorder all three arrays so ``values`` ascends; stable, so ties keep rule order."""
    order = np.argsort(values, kind="stable")
    return lower[order], upper[order], values[order]


def _weighted_average(weights: FloatArray, values: FloatArray) -> float:
    """``sum w c / sum w``; every caller guarantees ``sum w > 0``."""
    return float(weights @ values) / float(weights.sum())


def _switch_vertex(
    lower: FloatArray, upper: FloatArray, k: int, side: Literal["left", "right"]
) -> FloatArray:
    """The switch vertex for sorted rules: the first ``k`` get one bound, the rest the other."""
    if side == "left":
        return np.concatenate((upper[:k], lower[k:]))
    return np.concatenate((lower[:k], upper[k:]))


def _km_endpoint(
    lower: FloatArray,
    upper: FloatArray,
    values: FloatArray,
    side: Literal["left", "right"],
    *,
    guard: bool = True,
) -> tuple[float, int, bool]:
    """Iterate to one endpoint on rules already sorted by ``values``.

    Returns ``(y, passes, guard_stopped)``. ``guard=False`` exists only so the
    tests can show that the switch-point stop alone cycles (a mutation check); no
    production path passes it.
    """
    n_rules = int(values.size)
    y = _weighted_average(0.5 * (lower + upper), values)
    k_prev: int | None = None
    passes = 0
    while True:
        k = int(np.searchsorted(values, y, side="right"))
        if k == k_prev:
            return y, passes, False
        if passes == n_rules + 1:
            raise RuntimeError(
                f"Karnik-Mendel {side} endpoint did not stop within {n_rules + 1} passes"
            )
        y_next = _weighted_average(_switch_vertex(lower, upper, k, side), values)
        passes += 1
        if guard:
            if side == "left" and y_next >= y:
                return y, passes, y_next > y
            if side == "right" and y_next <= y:
                return y, passes, y_next < y
        y, k_prev = y_next, k


def karnik_mendel_detailed(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> KarnikMendelResult:
    """Iterative Karnik-Mendel endpoints with pass counts and guard stops.

    Inputs follow the module contract. Output satisfies ``y_l <= y_r`` up to
    rounding and agrees with :func:`exhaustive_type_reduce` to rounding. Pure.
    """
    lo, hi, c = _sorted_by_value(*_validated(lower, upper, values))
    y_l, passes_l, guard_l = _km_endpoint(lo, hi, c, "left")
    y_r, passes_r, guard_r = _km_endpoint(lo, hi, c, "right")
    return KarnikMendelResult(
        y_l=y_l,
        y_r=y_r,
        passes_l=passes_l,
        passes_r=passes_r,
        guard_stops=int(guard_l) + int(guard_r),
    )


def karnik_mendel_type_reduce(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[float, float]:
    """Return ``(y_l, y_r)`` by the guarded iterative Karnik-Mendel method (FR-1).

    Raises ``ValueError`` or ``ZeroDivisionError`` per the module contract and
    ``RuntimeError`` if an endpoint exceeds ``n_rules + 1`` passes, which the
    monotone guard makes unreachable. Pure.
    """
    result = karnik_mendel_detailed(lower, upper, values)
    return result.y_l, result.y_r


def exhaustive_type_reduce(
    lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike
) -> tuple[float, float]:
    """Return ``(y_l, y_r)`` by evaluating all ``n_rules + 1`` switch vertices per endpoint.

    Exact up to the rounding of each weighted average (module docstring), with
    no iteration and no stop rule, so it is the independent check on
    :func:`karnik_mendel_type_reduce`. Same contract and errors. Pure.
    """
    lo, hi, c = _sorted_by_value(*_validated(lower, upper, values))
    switch_points = range(c.size + 1)
    y_l = min(_weighted_average(_switch_vertex(lo, hi, k, "left"), c) for k in switch_points)
    y_r = max(_weighted_average(_switch_vertex(lo, hi, k, "right"), c) for k in switch_points)
    return y_l, y_r


def bmm_half_reduce(lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike) -> float:
    """BMM with ``alpha = beta = 1/2``: ``(Y(lower) + Y(upper)) / 2``.

    The formula ``NieTanDefuzzifier.defuzzify`` computes today (Wu & Mendel
    2019, Eq. 11). Linear in ``values`` for fixed firing. Same contract. Pure.
    """
    lo, hi, c = _validated(lower, upper, values)
    return 0.5 * _weighted_average(lo, c) + 0.5 * _weighted_average(hi, c)


def nie_tan_reduce(lower: npt.ArrayLike, upper: npt.ArrayLike, values: npt.ArrayLike) -> float:
    """Textbook Nie-Tan: ``Y(lower + upper)`` (Wu & Mendel 2019, Eq. 10).

    Equal to ``WeightedAverageDefuzzifier`` on an IT2 firing result, whose
    ``firing_strengths`` is the midpoint. Linear in ``values`` for fixed
    firing. Same contract, including the ``ZeroDivisionError`` on a zero lower
    sum, even though this formula alone would be defined there. Pure.
    """
    lo, hi, c = _validated(lower, upper, values)
    return _weighted_average(lo + hi, c)
