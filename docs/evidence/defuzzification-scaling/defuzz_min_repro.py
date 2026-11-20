"""Both defects of the shipped defuzzifiers, each on an input built so it must fail.

    C:/pvci/Scripts/python.exe -I defuzz_min_repro.py <checkout of main>

Exit 0 only if every shipped value is wrong as described and the exact value is as printed.
"""

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))  # -I ignores PYTHONPATH

import numpy as np

import superconducted
from superconducted.fuzzy.defuzzification import (
    NieTanDefuzzifier,
    WeightedAverageDefuzzifier,
)
from superconducted.types import RuleFiringResult

TREE = Path(sys.argv[1]).resolve()
print(
    "superconducted from <tree>/"
    + Path(superconducted.__file__).resolve().relative_to(TREE).as_posix()
)


def exact(f, c):  # sum f c / sum f in rational arithmetic on the same doubles
    f = [Fraction(float(x)) for x in f]
    return sum(a * Fraction(float(b)) for a, b in zip(f, c, strict=True)) / sum(f)


def t1(f, c):
    return RuleFiringResult(np.array(f), np.array(c)[:, None], None, None)


def it2(lo, hi, c):
    lo, hi = np.array(lo), np.array(hi)
    return RuleFiringResult(0.5 * (lo + hi), np.array(c)[:, None], lo, hi)


ok = True
with np.errstate(over="ignore"):  # the overflow is the point
    # 1. Overflow: firing at most 1, every value positive, sum of products above the largest double.
    y = WeightedAverageDefuzzifier().defuzzify(t1([1.0, 1.0], [1e308, 1e308]))[0]
    print("O1 T1  f=[1,1] c=[1e308]*2", "shipped", y, "exact", float(exact([1, 1], [1e308] * 2)))
    ok &= bool(np.isinf(y))
    y = NieTanDefuzzifier().defuzzify(it2([0.5, 0.5], [1.0, 1.0], [1e308, 1e308]))[0]
    print("O2 IT2 lo=[.5,.5] hi=[1,1] c=[1e308]*2", "shipped", y, "exact 1e+308")
    ok &= bool(np.isinf(y))
    big = np.float64(1e308)
    print("   the last line alone: 0.5*(1e308 + 1e308) =", 0.5 * (big + big))

# 2. Underflow: 1e-322 is 20 x 2**-1074, so f*|c| rounds to 0.0 for every |c| < 1/40.
lo = [1e-322, 1e-322]
y = WeightedAverageDefuzzifier().defuzzify(t1(lo, [0.01, 0.02]))[0]
print("U1 T1  f=[1e-322]*2 c=[0.01,0.02]", "shipped", y, "exact", float(exact(lo, [0.01, 0.02])))
ok &= y == 0.0
y = NieTanDefuzzifier().defuzzify(it2(lo, [0.5, 0.5], [0.01, 0.02]))[0]
e = float((exact(lo, [0.01, 0.02]) + exact([0.5, 0.5], [0.01, 0.02])) / 2)
print("U2 IT2 lo=[1e-322]*2 hi=[.5,.5]", "shipped", y, "exact", e, "(below every consequent)")
ok &= y < 0.01
y = NieTanDefuzzifier().defuzzify(it2(lo, [1e-3, 1.0], [0.01, 0.024]))[0]
e = float((exact(lo, [0.01, 0.024]) + exact([1e-3, 1.0], [0.01, 0.024])) / 2)
print("U3 IT2 lo=[1e-322]*2 hi=[1e-3,1] c=[0.01,0.024]", "shipped", y, "exact", e)
print("   (inside the hull, still wrong)")
ok &= 0.01 <= y <= 0.024 and abs(y - e) / e > 0.1
print("all as described" if ok else "NOT as described")
sys.exit(0 if ok else 1)
