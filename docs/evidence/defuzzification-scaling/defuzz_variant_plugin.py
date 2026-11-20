# ruff: noqa: E501
"""pytest plugin: run the suite with one arithmetic option patched into the two defuzzifiers.

Companion to ``defuzz_scaling_repro.py`` (same variants, same names). Nothing in the tree is
edited; the classes' ``defuzzify`` methods are replaced at ``pytest_configure``. Every guard of
the shipped classes (all-zero firing sum, a T1 result passed to ``NieTanDefuzzifier``) is left
to the original method, so the exceptions and their messages are the shipped ones.

    DEFUZZ_VARIANT=A PYTHONPATH="src;<dir of this file>" C:/pvci/Scripts/python.exe -m pytest tests -q -p defuzz_variant_plugin

``DEFUZZ_VARIANT``: ``shipped`` (no patch), ``A`` (#143 helper per output, ``0.5*a + 0.5*b``),
``B`` (shipped bits unless the numerator is subnormal or the quotient is not finite),
``C`` (shipped, but raise for a subnormal largest firing or a non-finite result),
``D`` (``_effective_weights(firing) @ consequents``, the trainer's route).
Mutation controls (to calibrate what the suite can see): ``X12`` and ``X6`` return the shipped
value times ``1 + 1e-12`` and ``1 + 1e-6``. The plugin counts patched calls and prints the
count at the end, so a run that never reached the classes cannot pass for a clean one.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

TINY = 2.0**-1022


def _weighted_average_143(weights, values):  # PR #143 at ae8d2bf9, lines 256 to 290
    scale = float(weights.max())
    if scale == math.inf:
        raise OverflowError("a weight overflowed to inf; retry with halved bounds")
    scaled = weights / scale
    total = float(scaled.sum())
    plain = float(scaled @ values) / total
    if math.isfinite(plain):
        return plain
    exponent = math.frexp(float(np.max(np.abs(values))))[1]
    quotient = float(scaled @ np.ldexp(values, -exponent)) / total
    try:
        return math.ldexp(quotient, exponent)
    except OverflowError:
        return math.copysign(sys.float_info.max, quotient)


def _port(f, c):
    return np.array([_weighted_average_143(f, c[:, d]) for d in range(c.shape[1])])


def _fallback(f, c):
    total = float(f.sum())
    num = (f[:, None] * c).sum(axis=0)
    y = num / total
    redo = ~np.isfinite(y) | (np.abs(num) < TINY)
    for d in np.flatnonzero(redo):
        y[d] = _weighted_average_143(f, c[:, d])
    return y


def _bound_value(variant, f, c):
    if variant == "A":
        return _port(f, c)
    if variant == "B":
        return _fallback(f, c)
    raise AssertionError(variant)


CALLS = {"wa": 0, "nt": 0}
FACTORS = {"X12": 1.0 + 1e-12, "X6": 1.0 + 1e-6}


def pytest_unconfigure(config):
    variant = os.environ.get("DEFUZZ_VARIANT", "shipped")
    print(f"\n[defuzz_variant_plugin] variant={variant} patched calls: {CALLS}")


def pytest_configure(config):
    variant = os.environ.get("DEFUZZ_VARIANT", "shipped")
    import superconducted
    from superconducted.fuzzy import defuzzification as d

    where = Path(superconducted.__file__).resolve()
    try:
        shown = "<cwd>/" + where.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        shown = f"OUTSIDE the working tree: {where}"
    print(f"\n[defuzz_variant_plugin] variant={variant} superconducted={shown}")
    if variant not in {"shipped", "A", "B", "C", "D", "X12", "X6"}:
        raise SystemExit(f"unknown DEFUZZ_VARIANT {variant!r}")
    from superconducted.training.anfis import _effective_weights

    orig_wa = d.WeightedAverageDefuzzifier.defuzzify
    orig_nt = d.NieTanDefuzzifier.defuzzify

    def wa(self, firing):
        CALLS["wa"] += 1
        f = firing.firing_strengths
        c = firing.consequent_outputs
        if variant == "shipped":
            return orig_wa(self, firing)
        if float(f.sum()) == 0.0:
            return orig_wa(self, firing)  # the shipped ZeroDivisionError
        if variant in FACTORS:
            return orig_wa(self, firing) * FACTORS[variant]
        if variant == "C":
            if float(f.max()) < TINY:
                raise ZeroDivisionError(f"largest firing strength {float(f.max())!r} is subnormal")
            y = orig_wa(self, firing)
            if not np.all(np.isfinite(y)):
                raise OverflowError("defuzzified output is not finite")
            return y
        if variant == "D":
            return np.asarray(_effective_weights(firing) @ c, dtype=np.float64)
        return np.asarray(_bound_value(variant, f, c), dtype=np.float64)

    def nt(self, firing):
        CALLS["nt"] += 1
        lo = firing.firing_strengths_lower
        hi = firing.firing_strengths_upper
        if variant == "shipped":
            return orig_nt(self, firing)
        if not firing.is_interval_type2 or float(lo.sum()) == 0.0 or float(hi.sum()) == 0.0:
            return orig_nt(self, firing)  # the shipped ValueError / ZeroDivisionError
        if variant in FACTORS:
            return orig_nt(self, firing) * FACTORS[variant]
        c = firing.consequent_outputs
        if variant == "C":
            for f in (lo, hi):
                if float(f.max()) < TINY:
                    raise ZeroDivisionError(
                        f"largest firing strength {float(f.max())!r} is subnormal"
                    )
            y = orig_nt(self, firing)
            if not np.all(np.isfinite(y)):
                raise OverflowError("defuzzified output is not finite")
            return y
        if variant == "D":
            return np.asarray(_effective_weights(firing) @ c, dtype=np.float64)
        return np.asarray(
            0.5 * _bound_value(variant, lo, c) + 0.5 * _bound_value(variant, hi, c),
            dtype=np.float64,
        )

    d.WeightedAverageDefuzzifier.defuzzify = wa
    d.NieTanDefuzzifier.defuzzify = nt
