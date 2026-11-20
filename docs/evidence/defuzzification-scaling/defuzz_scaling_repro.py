# ruff: noqa: E501
# (E501 only: the long lines are printed table rows and labels, kept whole so the output reads as a table.)
"""Unscaled weighted sums in ``fuzzy/defuzzification.py``: reproduce both failures, measure their reach.

Draft evidence for an issue about ``WeightedAverageDefuzzifier`` and ``NieTanDefuzzifier`` on
``main`` at ``58f7f63c`` (``src/``, ``tests/`` and ``scripts/`` are identical to ``667972c5``).
Nothing here edits the tree.

Run, with a checkout of that commit as the only argument (Git Bash or PowerShell)::

    C:/pvci/Scripts/python.exe -I <this folder>/defuzz_scaling_repro.py <tree>

``-I`` drops ``PYTHONPATH`` and the script's own directory, so the script inserts ``<tree>/src``
and ``<tree>`` (for ``scripts.first_ensemble_run`` and ``tests.test_anfis``), prints the
imported package's ``__file__``, and stops unless every file it reads has the blob hash it has
at ``58f7f63c``. Output is ASCII only (the Windows console here is cp1252).

Every figure is measured against an exact reference: ``fractions.Fraction`` of the same
float inputs, rounded once. Two error measures: ``rel_err`` (against ``|Y|``) for the repro
cases, whose consequents are positive, and ``scaled_err`` in eps of ``sum f |c| / sum f``
(the FR-3 test's measure) for ordinary inputs, where random consequents of mixed sign
cancel and a relative error says more about the cancellation than about the arithmetic.
The hull test ("is the output inside [min c, max c]") is printed next to them only to show
that it under-counts for ``NieTanDefuzzifier``.

Sections
  0  provenance
  1  overflow: finite consequents, ``inf`` result
  2  underflow: subnormal firing, ``Y(lower) = 0.0``
  3  graded loss by decade, and the thresholds as formulas
  4  reach: the one shipped builder, ``scripts/first_ensemble_run.py`` (T1)
  5  reach: IT2 grids buildable on main (no shipped caller): G59 and footprint ratios
  6  options on the repro inputs, and bit changes on ordinary inputs
  7  agreement with ``training/anfis.py::_effective_weights`` (the FR-3 test's bound)
  8  timing, one laptop run (provisional)
"""

from __future__ import annotations

import csv
import hashlib
import inspect
import math
import platform
import sys
import time
import warnings
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: python -I defuzz_scaling_repro.py <tree at 58f7f63c>")
TREE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "src"))

# Blob hashes at 58f7f63c (`git rev-parse 58f7f63c:<path>`). The tree checks out LF
# (`.gitattributes`: `* text=auto eol=lf`), so the raw bytes hash to the blob id.
PINNED_BLOBS = {
    "src/superconducted/fuzzy/defuzzification.py": "61478440631513b4fc21afb4d0a5be911a68bb6b",
    "src/superconducted/training/anfis.py": "db237241675d3d05bc4c57c8d562c86823ecf693",
    "scripts/first_ensemble_run.py": "a5fa4c3177de1631914c5ba6e1b593840df64dfa",
    "docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv": (
        "e1291ebb94897017a71881dfcf77b17ad3f9e33b"
    ),
}


def _blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


for _rel, _expected in PINNED_BLOBS.items():
    _actual = _blob_sha1(TREE / _rel)
    if _actual != _expected:
        raise SystemExit(f"{_rel}: blob {_actual} is not the 58f7f63c blob {_expected}")

import numpy as np  # noqa: E402
import scripts.first_ensemble_run as fer  # noqa: E402
from tests.test_anfis import _planted_box_features, _planted_grid  # noqa: E402

import superconducted  # noqa: E402
from superconducted.calibration.features import BasicCalibrationVectorizer  # noqa: E402
from superconducted.fuzzy.defuzzification import (  # noqa: E402
    NieTanDefuzzifier,
    WeightedAverageDefuzzifier,
)
from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF  # noqa: E402
from superconducted.fuzzy.parameterization import (  # noqa: E402
    _quantile_layout,
    anchored_rule_base,
    grid_partition,
    partition_anchors,
)
from superconducted.fuzzy.squashing import ProbabilityClip  # noqa: E402
from superconducted.fuzzy.tsk import TSKRuleBase  # noqa: E402
from superconducted.training.anfis import _effective_weights  # noqa: E402
from superconducted.training.targets import feature_target_fn  # noqa: E402
from superconducted.types import CalibrationSnapshot, RuleFiringResult  # noqa: E402

Array = np.ndarray
WA = WeightedAverageDefuzzifier()
NT = NieTanDefuzzifier()
CLIP = ProbabilityClip()
TINY = 2.0**-1022  # smallest normal double
DENORM_MIN = 2.0**-1074  # smallest subnormal
DBL_MAX = sys.float_info.max
EPS = float(np.finfo(np.float64).eps)
SURVEY = TREE / "docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv"
FEATURES = ("mean_T1", "mean_T2", "mean_readout_error")
SPREADS = ("T1_qubit_std", "T2_qubit_std", "readout_error_qubit_std")
SX_GATE_SECONDS = 24e-9  # NC-035
UNIFORM_SEED = 20261120
N_UNIFORM = 1000


def h(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def fmt(x: float) -> str:
    return f"{x:.6e}" if math.isfinite(x) else str(x)


# --------------------------------------------------------------------------------------
# Exact reference and the variants compared in section 6
# --------------------------------------------------------------------------------------


def _exact_wavg(f: Array, c: Array) -> list[Fraction]:
    """``sum f c / sum f`` per output column, in exact rational arithmetic on the given floats."""
    weights = [Fraction(float(x)) for x in f]
    total = sum(weights, Fraction(0))
    out = []
    for d in range(c.shape[1]):
        num = sum((w * Fraction(float(c[r, d])) for r, w in enumerate(weights)), Fraction(0))
        out.append(num / total)
    return out


def exact_t1(f: Array, c: Array) -> Array:
    return np.array([float(q) for q in _exact_wavg(f, c)])  # float(Fraction) rounds once


def exact_it2(lo: Array, hi: Array, c: Array) -> Array:
    pairs = zip(_exact_wavg(lo, c), _exact_wavg(hi, c), strict=True)
    return np.array([float((a + b) / 2) for a, b in pairs])


def error_scale(firing: RuleFiringResult) -> Array:
    """``sum f |c| / sum f`` per output (the BMM average of the two bounds' scales for IT2), exact."""
    c = np.abs(firing.consequent_outputs)
    if firing.is_interval_type2:
        assert firing.firing_strengths_lower is not None
        assert firing.firing_strengths_upper is not None
        return exact_it2(firing.firing_strengths_lower, firing.firing_strengths_upper, c)
    return exact_t1(firing.firing_strengths, c)


def scaled_err(y: Array, ref: Array, scale: Array) -> float:
    """Largest ``|y - ref| / (eps * scale)`` over outputs; ``inf`` for a non-finite ``y``."""
    if not np.all(np.isfinite(y)):
        return math.inf
    return float(np.max(np.abs(y - ref) / (EPS * scale)))


def rel_err(y: Array, ref: Array) -> float:
    """Largest relative error over outputs; ``inf`` for a non-finite ``y``."""
    worst = 0.0
    for a, b in zip(np.ravel(y), np.ravel(ref), strict=True):
        if not math.isfinite(a):
            return math.inf
        worst = max(worst, abs(a - b) / abs(b) if b != 0.0 else abs(a))
    return worst


CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    """Record one claim the issue cites; the script exits 1 if any is false."""
    CHECKS.append((name, bool(ok)))


def t1(f: list[float] | Array, c: list[list[float]] | Array) -> RuleFiringResult:
    fa = np.asarray(f, dtype=np.float64)
    return RuleFiringResult(fa, np.asarray(c, dtype=np.float64), None, None)


def it2(
    lo: list[float] | Array, hi: list[float] | Array, c: list[list[float]] | Array
) -> RuleFiringResult:
    la = np.asarray(lo, dtype=np.float64)
    ha = np.asarray(hi, dtype=np.float64)
    return RuleFiringResult(0.5 * (la + ha), np.asarray(c, dtype=np.float64), la, ha)


def _weighted_average_143(weights: Array, values: Array) -> float:
    """Transcribed from PR #143 at ``ae8d2bf9``, ``scripts/type_reduction_discrepancy.py``
    lines 256 to 290 (``_weighted_average``), docstring dropped. Weights rescaled by their
    max always; values shifted by a power of two only when the plain quotient is not
    finite; saturates at the largest double."""
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


def _port_columns(f: Array, c: Array) -> Array:
    return np.array([_weighted_average_143(f, c[:, d]) for d in range(c.shape[1])])


def port143(firing: RuleFiringResult) -> Array:
    """Option A: the #143 helper applied per output column (a port, so its rounding is ``@``'s).

    IT2 combines as #143's ``bmm_half_reduce`` does (``ae8d2bf9`` line 403),
    ``0.5 * a + 0.5 * b``: the class's ``0.5 * (a + b)`` overflows when both are near the
    largest double, even after each bound's quotient is finite (section 1, case O2)."""
    c = firing.consequent_outputs
    if not firing.is_interval_type2:
        return _port_columns(firing.firing_strengths, c)
    assert firing.firing_strengths_lower is not None and firing.firing_strengths_upper is not None
    return 0.5 * _port_columns(firing.firing_strengths_lower, c) + 0.5 * _port_columns(
        firing.firing_strengths_upper, c
    )


def _fallback_bound(f: Array, c: Array) -> Array:
    """The shipped expression; columns whose numerator is subnormal or whose quotient is not
    finite are recomputed with the #143 helper. Elsewhere bit for bit the shipped value."""
    total = float(f.sum())
    num = (f[:, None] * c).sum(axis=0)
    y = num / total
    redo = ~np.isfinite(y) | (np.abs(num) < TINY)
    for d in np.flatnonzero(redo):
        y[d] = _weighted_average_143(f, c[:, d])
    return y


def fallback(firing: RuleFiringResult) -> Array:
    """Option B: the same fallback, triggered only where the shipped arithmetic fails.

    ``0.5 * a + 0.5 * b`` equals the class's ``0.5 * (a + b)`` bit for bit whenever both are
    normal and the sum does not overflow (halving is exact there), so the normal path keeps
    the shipped bits."""
    c = firing.consequent_outputs
    if not firing.is_interval_type2:
        return _fallback_bound(firing.firing_strengths, c)
    assert firing.firing_strengths_lower is not None and firing.firing_strengths_upper is not None
    return 0.5 * _fallback_bound(firing.firing_strengths_lower, c) + 0.5 * _fallback_bound(
        firing.firing_strengths_upper, c
    )


def contract(firing: RuleFiringResult) -> Array:
    """Option C: the shipped value, but refuse where it is known to be wrong.

    A largest firing strength below ``2**-1022`` is treated like the all-zero sum the class
    already refuses (``ZeroDivisionError``); a non-finite result raises ``OverflowError``.
    The trigger is on the firing, not on the numerator: zero consequents give a zero
    numerator legitimately (``tests/test_channel_viability.py::test_zeros_init_is_degenerate``
    expects exactly ``[0.0, 0.0]``)."""
    bounds = (
        (firing.firing_strengths_lower, firing.firing_strengths_upper)
        if firing.is_interval_type2
        else (firing.firing_strengths,)
    )
    for f in bounds:
        assert f is not None
        if float(f.max()) < TINY:
            raise ZeroDivisionError(f"largest firing strength {float(f.max())!r} is subnormal")
    y = shipped(firing)
    if not np.all(np.isfinite(y)):
        raise OverflowError("defuzzified output is not finite")
    return y


def anfis_route(firing: RuleFiringResult) -> Array:
    """Option D / the trainer's route: ``_effective_weights(firing) @ consequents`` (normalise first)."""
    weights = _effective_weights(firing)
    if weights is None:
        raise ZeroDivisionError("_effective_weights returned None (zero firing sum)")
    return np.asarray(weights @ firing.consequent_outputs, dtype=np.float64)


def shipped(firing: RuleFiringResult) -> Array:
    return (NT if firing.is_interval_type2 else WA).defuzzify(firing)


def exact(firing: RuleFiringResult) -> Array:
    c = firing.consequent_outputs
    if firing.is_interval_type2:
        assert firing.firing_strengths_lower is not None
        assert firing.firing_strengths_upper is not None
        return exact_it2(firing.firing_strengths_lower, firing.firing_strengths_upper, c)
    return exact_t1(firing.firing_strengths, c)


def outside_hull(y: Array, c: Array) -> bool:
    return bool(np.any((y < c.min(axis=0)) | (y > c.max(axis=0))))


VARIANTS: dict[str, Callable[[RuleFiringResult], Array]] = {
    "shipped": shipped,
    "A port143": port143,
    "B fallback": fallback,
    "C contract": contract,
    "D anfis_route": anfis_route,
}


def show_case(name: str, firing: RuleFiringResult) -> dict[str, Array | str]:
    """Print every variant on one input; return each variant's output (or the exception name)."""
    ref = exact(firing)
    out: dict[str, Array | str] = {"exact": ref}
    print(f"-- {name}")
    print(
        f"   exact {[fmt(v) for v in ref]}   consequent hull per output "
        f"[{fmt(float(firing.consequent_outputs.min()))}, {fmt(float(firing.consequent_outputs.max()))}]"
    )
    for label, fn in VARIANTS.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                y = fn(firing)
            except (ZeroDivisionError, OverflowError) as exc:
                print(f"   {label:<15} raises {type(exc).__name__}: {exc}")
                out[label] = type(exc).__name__
                continue
        out[label] = y
        warned = sorted({f"{w.category.__name__}: {w.message}" for w in caught}) or ["none"]
        print(
            f"   {label:<15} {[fmt(v) for v in y]}  rel_err {fmt(rel_err(y, ref))}  "
            f"outside_hull {outside_hull(y, firing.consequent_outputs)}  "
            f"ProbabilityClip -> {[fmt(v) for v in CLIP.squash(y)]}  warnings: {'; '.join(warned)}"
        )
    return out


def fixed(result: dict[str, Array | str], label: str) -> bool:
    """The variant returned the exact value to within 1 ulp."""
    y, ref = result[label], result["exact"]
    if isinstance(y, str) or isinstance(ref, str):
        return False
    return bool(np.all(np.abs(y - ref) <= np.array([math.ulp(float(v)) for v in ref])))


# --------------------------------------------------------------------------------------
# 0 provenance
# --------------------------------------------------------------------------------------

h("0  provenance")
if not Path(superconducted.__file__).resolve().is_relative_to(TREE / "src"):
    raise SystemExit(f"superconducted was not imported from <tree>/src: {superconducted.__file__}")
# Paths are printed relative to <tree>, so the saved output carries no local user folder.
print("tree                 <tree> (the argument); imports checked to resolve inside it")
print(
    f"superconducted       <tree>/{Path(superconducted.__file__).resolve().relative_to(TREE).as_posix()}"
)
print(f"scripts module       <tree>/{Path(fer.__file__).resolve().relative_to(TREE).as_posix()}")
print(
    f"python               {platform.python_version()}  numpy {np.__version__}  {platform.platform()}"
)
print(f"numpy error state    {np.geterr()}  (underflow is ignored: it never warns)")
for _rel, _expected in PINNED_BLOBS.items():
    print(f"blob ok              {_rel} = {_expected[:8]}")

# --------------------------------------------------------------------------------------
# 1 overflow
# --------------------------------------------------------------------------------------

h("1  overflow: finite consequents give inf (inputs built so the sum must pass DBL_MAX)")
o1 = show_case(
    "O1 T1, f=[1,1], c=[1e308,1e308] (review 5923434762's values)",
    t1([1.0, 1.0], [[1e308], [1e308]]),
)
o2 = show_case(
    "O2 IT2, lower=[0.5,0.5], upper=[1,1], c=[1e308,1e308]: y_low finite, y_high inf",
    it2([0.5, 0.5], [1.0, 1.0], [[1e308], [1e308]]),
)
with np.errstate(
    over="ignore"
):  # the overflow is the point; show_case records the warnings per variant
    o2b_lo = 0.5 * np.array([1e308]) + 0.5 * np.array([1e308])
    o2b_cls = 0.5 * (np.array([1e308]) + np.array([1e308]))
print(
    f"   the class's last line on two finite bounds of 1e308: 0.5*(a+b) = {fmt(float(o2b_cls[0]))};"
    f" 0.5*a + 0.5*b = {fmt(float(o2b_lo[0]))}"
)
for _case, _name in ((o1, "O1"), (o2, "O2")):
    check(
        f"{_name}: shipped returns inf for finite inputs",
        isinstance(_case["shipped"], np.ndarray) and bool(np.isinf(_case["shipped"]).all()),
    )
    for _label in ("A port143", "B fallback", "D anfis_route"):
        check(f"{_name}: {_label} returns the exact value", fixed(_case, _label))
    check(f"{_name}: C contract raises", _case["C contract"] == "OverflowError")
check(
    "O2: 0.5*(a+b) overflows where 0.5*a + 0.5*b does not",
    bool(np.isinf(o2b_cls[0])) and bool(np.isfinite(o2b_lo[0])),
)
_n27 = 27
_c_hi = np.full((_n27, 1), DBL_MAX / _n27 * (1 + 1e-3))
_c_lo = np.full((_n27, 1), DBL_MAX / _n27 * (1 - 1e-3))
with np.errstate(over="ignore"):
    _o3_hi = float(WA.defuzzify(t1(np.ones(_n27), _c_hi))[0])
    _o3_lo = float(WA.defuzzify(t1(np.ones(_n27), _c_lo))[0])
print(
    f"-- O3 bound: 27 rules at f=1 (the largest a product of degrees in [0,1] can be):\n"
    f"   every c = DBL_MAX/27*(1+1e-3) = {fmt(float(_c_hi[0, 0]))}: shipped {fmt(_o3_hi)};"
    f"  every c = DBL_MAX/27*(1-1e-3): shipped {fmt(_o3_lo)}"
)
check("O3: 27 rules at f=1 overflow just above DBL_MAX/27", math.isinf(_o3_hi))
check("O3: and stay finite just below it", math.isfinite(_o3_lo))
print(
    "   so with firing in [0,1] overflow needs sum_r f_r |c_r| > DBL_MAX, i.e. some |c_r| > DBL_MAX/n_rules."
)

# --------------------------------------------------------------------------------------
# 2 underflow
# --------------------------------------------------------------------------------------

h("2  underflow: firing near the subnormal floor gives Y(lower) = 0.0")
_units = round(1e-322 / DENORM_MIN)
print(
    f"   1e-322 as a double = {fmt(1e-322)} = {_units} x 2**-1074, so f*|c| < 2**-1075 (rounds to 0.0) for |c| < 1/{2 * _units}"
)
print(
    "   Built so every product must round to 0.0: f = 1e-322 and every |c| < 0.025. (With c = 0.03 one product"
)
print(
    "   rounds up to 1 x 2**-1074 and the quotient happens to come out right, which is why the inputs are built.)"
)
u1 = show_case("U1 T1, f=[1e-322,1e-322], c=[0.01,0.02]", t1([1e-322, 1e-322], [[0.01], [0.02]]))
u2 = show_case(
    "U2 IT2, lower=[1e-322,1e-322], upper=[0.5,0.5], c=[0.01,0.02]: Y(lower)=0, output below every consequent",
    it2([1e-322, 1e-322], [0.5, 0.5], [[0.01], [0.02]]),
)
u3 = show_case(
    "U3 IT2, lower=[1e-322,1e-322], upper=[1e-3,1], c=[0.01,0.024]: Y(lower)=0, output wrong but INSIDE the hull",
    it2([1e-322, 1e-322], [1e-3, 1.0], [[0.01], [0.024]]),
)
u4 = show_case(
    "U4 IT2 control, c=[0.02,0.03] (one product rounds up): shipped happens to be right",
    it2([1e-322, 1e-322], [0.5, 0.5], [[0.02], [0.03]]),
)
_y_lower_u2 = (np.array([1e-322, 1e-322])[:, None] * np.array([[0.01], [0.02]])).sum(
    axis=0
) / float(np.array([1e-322, 1e-322]).sum())
print(f"   U2's Y(lower) by the class's own expression: {fmt(float(_y_lower_u2[0]))}")
check(
    "U1: shipped T1 returns exactly 0.0",
    isinstance(u1["shipped"], np.ndarray) and float(u1["shipped"][0]) == 0.0,
)
check("U2: Y(lower) is exactly 0.0 by the class's expression", float(_y_lower_u2[0]) == 0.0)
check(
    "U2: shipped IT2 output is below every consequent",
    isinstance(u2["shipped"], np.ndarray) and float(u2["shipped"][0]) < 0.01,
)
_u3s = u3["shipped"]
check(
    "U3: shipped IT2 output is inside the hull and more than 10% wrong",
    isinstance(_u3s, np.ndarray)
    and not outside_hull(_u3s, np.array([[0.01], [0.024]]))
    and rel_err(_u3s, u3["exact"]) > 0.1,  # type: ignore[arg-type]
)
check("U4: control comes out right in shipped", fixed(u4, "shipped"))
for _case, _name in ((u1, "U1"), (u2, "U2"), (u3, "U3")):
    for _label in ("A port143", "B fallback", "D anfis_route"):
        check(f"{_name}: {_label} returns the exact value", fixed(_case, _label))
    check(
        f"{_name}: C contract raises ZeroDivisionError", _case["C contract"] == "ZeroDivisionError"
    )

# --------------------------------------------------------------------------------------
# 3 graded loss and thresholds
# --------------------------------------------------------------------------------------

h("3  graded loss by decade (T1 class; f = s*[1,0.7,0.4], c = scale*[1,1.3,1.7])")
print(
    "   s        rel_err c~1e-1   rel_err c~2e-4   (0 means rounding-level is not exceeded; 1.0 means Y = 0.0)"
)
for k in range(296, 324):
    s = 10.0**-k
    f = s * np.array([1.0, 0.7, 0.4])
    row = []
    for scale in (1e-1, 2e-4):
        c = scale * np.array([[1.0], [1.3], [1.7]])
        y = WA.defuzzify(t1(f, c))
        row.append(rel_err(y, exact_t1(f, c)))
    print(f"   1e-{k:<4}  {row[0]:<16.3e} {row[1]:<16.3e}")

# The S thresholds, measured on math.exp rather than assumed: f_max = exp(-S).
_lo, _hi = 700.0, 800.0
for _ in range(200):
    _mid = 0.5 * (_lo + _hi)
    if math.exp(-_mid) > 0.0:
        _lo = _mid
    else:
        _hi = _mid
S_ZERO_FIRING = _lo  # largest S with exp(-S) > 0
S_SUBNORMAL = 1022 * math.log(2.0)  # exp(-S) < 2**-1022 beyond this
print()
print("   Thresholds for the shipped quotient sum_r f_r c_r / sum_r f_r, with f_max = exp(-S):")
print(
    "     products are rounding-level while max_r f_r |c_r| >= 2**-1022, i.e. S <= 1022 ln2 + ln|c|"
)
print("     a product rounds to 0.0 when f_r |c_r| <= 2**-1075, i.e. S >= 1075 ln2 + ln|c|")
print(
    f"     the firing itself is 0.0 (ZeroDivisionError, already caught) for S > {S_ZERO_FIRING:.4f} (math.exp)"
)
print(f"     1022 ln2 = {S_SUBNORMAL:.4f}   1075 ln2 = {1075 * math.log(2.0):.4f}")
for scale in (1e-1, 2e-4):
    s_loss = S_SUBNORMAL + math.log(scale)
    s_zero = 1075 * math.log(2.0) + math.log(scale)
    print(
        f"     |c| = {scale:g}: silent band S in ({s_loss:.2f}, {S_ZERO_FIRING:.2f}],"
        f" of which Y = 0.0 for S >= {s_zero:.2f};"
        f" as a distance ||z|| = sqrt(2 S) in widths: ({math.sqrt(2 * s_loss):.2f}, {math.sqrt(2 * S_ZERO_FIRING):.2f}]"
    )

# --------------------------------------------------------------------------------------
# 4 reach: scripts/first_ensemble_run.py
# --------------------------------------------------------------------------------------

h("4  reach: scripts/first_ensemble_run.py (the one shipped builder of a defuzzifier on main)")
src_fer = inspect.getsource(fer)
print(
    f"   defuzzifier: WeightedAverageDefuzzifier ({src_fer.count('WeightedAverageDefuzzifier()')} construction);"
    f" 'Clamp' in source: {'Clamp' in src_fer}; NieTanDefuzzifier in source: {'NieTan' in src_fer}"
)
print(f"   FEATURE_SCALES {fer.FEATURE_SCALES}  sigma = span/4; placements {fer.MF_PLACEMENTS}")

with SURVEY.open(newline="", encoding="utf-8") as handle:
    rows = [r for r in csv.DictReader(handle, delimiter="\t") if all(r[n] for n in FEATURES)]
survey_us = np.array([[float(r[n]) for n in FEATURES] for r in rows])
survey_si = survey_us * np.array([1e-6, 1e-6, 1.0])  # the survey is in microseconds (NC-042)
print(
    f"   survey rows with all three means: {len(rows)}; T1 [{survey_us[:, 0].min():.2f}, {survey_us[:, 0].max():.2f}] us,"
    f" T2 [{survey_us[:, 1].min():.2f}, {survey_us[:, 1].max():.2f}] us,"
    f" readout [{survey_us[:, 2].min():.5f}, {survey_us[:, 2].max():.5f}]"
)

# Units check: the real extraction path on the committed fixture against its survey row.
import json  # noqa: E402
from datetime import datetime  # noqa: E402

_fx = json.loads(
    (TREE / "tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json").read_text(
        "utf-8"
    )
)
_snap = CalibrationSnapshot(
    backend=str(_fx["backend"]),
    timestamp=datetime.fromisoformat(str(_fx["timestamp"]).replace("Z", "+00:00")),
    schema_version=str(_fx["schema_version"]),
    properties=_fx["properties"],
    target=_fx.get("target"),
    configuration=_fx.get("configuration"),
)
_x_fixture = BasicCalibrationVectorizer().extract(_snap)
_row = next(i for i, r in enumerate(rows) if r["stem"] == "20260513T121322000000Z")
print(
    f"   units check: extract(fixture) = {[fmt(v) for v in _x_fixture]}; survey row x 1e-6 = "
    f"{[fmt(v) for v in survey_si[_row]]}; max rel diff {fmt(float(np.max(np.abs(_x_fixture / survey_si[_row] - 1))))}"
)

points_si = np.vstack([survey_si, _x_fixture[None, :]])
for placement in fer.MF_PLACEMENTS:
    mfs = [
        fer._default_mfs_for_feature(n, placement)
        for n in BasicCalibrationVectorizer().feature_names
    ]
    sigmas = np.array([mf.parameters()[1] for mf in (m[0] for m in mfs)])
    centres = [np.array([mf.parameters()[0] for mf in m]) for m in mfs]
    z = np.column_stack(
        [
            np.min(np.abs(points_si[:, i, None] - centres[i][None, :]), axis=1) / sigmas[i]
            for i in range(3)
        ]
    )
    s_rows = 0.5 * np.sum(
        z**2, axis=1
    )  # S of the best-firing rule (grid: product of per-feature maxima)
    rb0 = TSKRuleBase.from_grid(
        per_input_mfs=mfs, output_dim=2, consequent_init="random", rng=np.random.default_rng(0)
    )
    fmax = np.array([rb0.evaluate(x).firing_strengths.max() for x in points_si])
    # consequents for every seed the viability search can pick (0..63), at every point
    cmin, cmax, margin_min = math.inf, 0.0, math.inf
    worst_scaled = 0.0
    for seed in range(fer.CONSEQUENT_SEED_SEARCH_LIMIT):
        rb = TSKRuleBase.from_grid(
            per_input_mfs=mfs,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(seed),
        )
        params = np.stack([r.consequent_params for r in rb.rules])  # (27, 2, 4)
        cons = (
            np.einsum("rdk,pk->prd", params[:, :, :3], points_si) + params[None, :, :, 3]
        )  # (P, 27, 2)
        cmin = min(cmin, float(np.min(np.abs(cons))))
        cmax = max(cmax, float(np.max(np.abs(cons))))
        if seed < 4:
            for x in points_si:
                firing = rb.evaluate(x)
                worst_scaled = max(
                    worst_scaled,
                    scaled_err(WA.defuzzify(firing), exact(firing), error_scale(firing)),
                )
                prod = np.max(
                    firing.firing_strengths[:, None] * np.abs(firing.consequent_outputs), axis=0
                )
                margin_min = min(margin_min, float(np.min(np.log10(prod / TINY))))
    s_need = S_SUBNORMAL + math.log(cmax)  # latest onset: the largest |c|
    print(
        f"   [{placement}] worst point: S = {s_rows.max():.3f} (||z|| = {math.sqrt(2 * s_rows.max()):.3f} widths),"
        f" min max_r f_r = {fmt(float(fmax.min()))} (log-space exp(-S) {fmt(math.exp(-s_rows.max()))})"
    )
    print(
        f"   [{placement}] |c| over 976 points x 27 rules x 2 outputs x seeds 0..63: [{fmt(cmin)}, {fmt(cmax)}]"
    )
    print(
        f"   [{placement}] seeds 0..3: min over points and outputs of log10(max_r f_r|c_r| / 2**-1022) = {margin_min:.1f} decades;"
        f" worst error vs exact {worst_scaled:.2f} eps of sum f|c|/sum f"
    )
    # A bound for all 64 seeds: the smallest max firing times the smallest |c| anywhere. It
    # pairs two minima that need not occur together, so it is a lower bound on the margin.
    margin_bound = math.log10(float(fmax.min())) + math.log10(cmin) - math.log10(TINY)
    print(
        f"   [{placement}] seeds 0..63, lower bound log10(min max_r f_r * min |c| / 2**-1022) = {margin_bound:.1f} decades"
    )
    check(f"4 [{placement}]: the 64-seed lower bound is above 290 decades", margin_bound > 290)
    print(
        f"   [{placement}] loss needs S > {s_need:.2f}: ||z|| > {math.sqrt(2 * s_need):.2f} widths, "
        f"{math.sqrt(s_need / s_rows.max()):.1f}x the worst point's distance"
    )
    t1_needed = centres[0].max() + math.sqrt(2 * s_need) * sigmas[0]
    ro_max_s = 0.5 * ((1.0 - centres[2].max()) / sigmas[2]) ** 2
    print(
        f"   [{placement}] T1 alone (others at their centres): loss from T1 > {t1_needed * 1e6:.1f} us"
        f" (survey max {survey_us[:, 0].max():.1f} us); readout error <= 1 can contribute at most S = {ro_max_s:.1f}"
    )
    check(
        f"4 [{placement}]: every survey point and the fixture sit more than 290 decades above the loss onset",
        margin_min > 290,
    )
    check(
        f"4 [{placement}]: the worst point's S is below the loss threshold",
        float(s_rows.max()) < s_need,
    )
    check(
        f"4 [{placement}]: evaluated max firing agrees with the log-space value",
        math.isclose(float(fmax.min()), math.exp(-float(s_rows.max())), rel_tol=1e-9),
    )
    check(
        f"4 [{placement}]: ordinary error is rounding-level (< 64 eps of sum f|c|/sum f)",
        worst_scaled < 64,
    )

# Mutation check: a constructed input in the band, through the same pipeline and detector.
mfs = [
    fer._default_mfs_for_feature(n, fer.MF_PLACEMENT_ENDPOINT)
    for n in BasicCalibrationVectorizer().feature_names
]
rb0 = TSKRuleBase.from_grid(
    per_input_mfs=mfs, output_dim=2, consequent_init="random", rng=np.random.default_rng(0)
)
print("   mutation check (endpoint, seed 0, T2 = 50 us and readout = 0.05 at centres, T1 scanned):")
first_loss = first_zero = first_raise = None
for t1_us in np.arange(1000.0, 1080.0, 0.25):
    x = np.array([t1_us * 1e-6, 50e-6, 0.05])
    firing = rb0.evaluate(x)
    try:
        y = WA.defuzzify(firing)
    except ZeroDivisionError:
        first_raise = first_raise or t1_us
        break
    err = scaled_err(y, exact(firing), error_scale(firing))
    if err > 1e4 and first_loss is None:
        first_loss = (float(t1_us), float(err))
    if np.any(y == 0.0) and first_zero is None:
        first_zero = float(t1_us)
print(
    f"     first T1 with error > 1e4 eps: {first_loss} (us, eps); first with an output exactly 0.0: {first_zero} us;"
    f" first ZeroDivisionError: {first_raise} us"
)
print(
    f"     max f at 1040 us: {fmt(float(rb0.evaluate(np.array([1040e-6, 50e-6, 0.05])).firing_strengths.max()))};"
    f" the scan's band is [{first_loss[0] if first_loss else None}, {first_raise}) us against a survey max of"
    f" {survey_us[:, 0].max():.1f} us"
)
check(
    "4 mutation: the same pipeline and detector fire inside the band",
    first_loss is not None and first_zero is not None,
)
check(
    "4 mutation: the band ends in the ZeroDivisionError the class already raises",
    first_raise is not None,
)

# --------------------------------------------------------------------------------------
# 5 reach: IT2 grids on main (no shipped caller)
# --------------------------------------------------------------------------------------

h(
    "5  reach: IT2 grids buildable on main (NieTanDefuzzifier has no shipped caller), survey units (us)"
)
samples = {n: survey_us[:, i] for i, n in enumerate(FEATURES)}
with SURVEY.open(newline="", encoding="utf-8") as handle:
    all_rows = list(csv.DictReader(handle, delimiter="\t"))
spreads = {
    n: float(np.median([float(r[s]) for r in all_rows if r[s]]))
    for n, s in zip(FEATURES, SPREADS, strict=True)
}
print(f"   s_i (NC-042 medians of *_qubit_std): {spreads}")
anchors = [partition_anchors(samples[n], 3) for n in FEATURES]
layouts = [_quantile_layout(samples[n], 3, "quantile") for n in FEATURES]
box_lo = np.array([lay.lo for lay in layouts])
box_hi = np.array([lay.hi for lay in layouts])
rng = np.random.default_rng(UNIFORM_SEED)
uniform = box_lo + (box_hi - box_lo) * rng.random((N_UNIFORM, 3))
print(
    f"   domain box [p1, p99]: lo {[fmt(v) for v in box_lo]} hi {[fmt(v) for v in box_hi]};"
    f" uniform draws: {N_UNIFORM}, seed {UNIFORM_SEED} (not #143's point set)"
)


def _target(anchor: Array) -> Array:
    return feature_target_fn(anchor, t_seconds=SX_GATE_SECONDS, coherence_unit="us")


def _grid_g59() -> list[list[IntervalGaussianMF]]:
    return [
        list(grid_partition(IntervalGaussianMF, samples[n], 3, qubit_spread=spreads[n]))
        for n in FEATURES
    ]


def _grid_ratio(w: float) -> list[list[IntervalGaussianMF]]:
    out = []
    for n in FEATURES:
        level = []
        for base in grid_partition(GaussianMF, samples[n], 3):
            centre, sigma = (float(v) for v in base.parameters())
            level.append(IntervalGaussianMF(centre, sigma * (1.0 - w), sigma * (1.0 + w)))
        out.append(level)
    return out


grids = {"g59": _grid_g59()} | {f"w={w}": _grid_ratio(w) for w in (0.1, 0.3, 0.6, 0.9, 0.99)}
it2_firings_g59: list[RuleFiringResult] = []
print(
    "   max_r f_lo is the largest lower firing strength at a point; 'zero' points raise ZeroDivisionError (loud),"
)
print(
    "   'band' points have 0 < max_r f_lo < 2**-1022 (the silent band), 'wrong' counts rel_err > 1e-9 against exact."
)
print(
    "   grid    set      n     min max_r f_lo   zero  band  wrong  outside_hull  worst rel_err   margin(decades)  |c| range"
)
for gname, per_input in grids.items():
    rb = anchored_rule_base(per_input, _target, anchors=anchors)
    for sname, pts in (("survey", survey_us), ("uniform", uniform)):
        n_zero = n_band = n_bad = n_hull = 0
        worst = 0.0
        fmin = math.inf
        fmin_nonzero = math.inf
        cons_lo, cons_hi = math.inf, 0.0
        for x in pts:
            firing = rb.evaluate(x)
            assert firing.firing_strengths_lower is not None
            fl = float(firing.firing_strengths_lower.max())
            fmin = min(fmin, fl)
            cons_lo = min(cons_lo, float(np.min(np.abs(firing.consequent_outputs))))
            cons_hi = max(cons_hi, float(np.max(np.abs(firing.consequent_outputs))))
            if gname == "g59" and sname == "survey":
                it2_firings_g59.append(firing)
            if fl == 0.0:
                n_zero += 1
            else:
                fmin_nonzero = min(fmin_nonzero, fl)
                n_band += fl < TINY
            try:
                y = NT.defuzzify(firing)
            except ZeroDivisionError:
                continue
            err = rel_err(y, exact(firing))
            worst = max(worst, err)
            n_bad += err > 1e-9
            n_hull += outside_hull(y, firing.consequent_outputs)
        # log10(min nonzero max f_lo * min |c| / 2**-1022), in log space: the product underflows in the band
        margin = math.log10(fmin_nonzero) + math.log10(cons_lo) - math.log10(TINY)
        print(
            f"   {gname:<7} {sname:<8} {len(pts):<5} {fmt(fmin):<16} {n_zero:<5} {n_band:<5} {n_bad:<6} {n_hull:<13} "
            f"{fmt(worst):<15} {margin:<16.1f} [{fmt(cons_lo)}, {fmt(cons_hi)}]"
        )
        if gname != "w=0.99":
            check(
                f"5 {gname} {sname}: no zero, band or wrong point", n_zero == n_band == n_bad == 0
            )
        elif sname == "uniform":
            check(
                "5 w=0.99 uniform: the band is reached and gives wrong values",
                n_band > 0 and n_bad > 0,
            )
            check("5 w=0.99 uniform: the hull test misses some of them", n_hull < n_bad)
        check(
            f"5 {gname} {sname}: anchored |c| is of order 1e-4", cons_lo >= 1e-4 and cons_hi < 1e-3
        )

# --------------------------------------------------------------------------------------
# 6 options
# --------------------------------------------------------------------------------------

h(
    "6  options: repro inputs (sections 1 and 2 print every variant) and bit changes on ordinary inputs"
)
print(
    "   A port143 = #143's helper per output, bmm_half_reduce's 0.5*a + 0.5*b;  B fallback = shipped bits unless"
)
print(
    "   the numerator is subnormal or the quotient is not finite, then A;  C contract = shipped, but raise for a"
)
print(
    "   subnormal largest firing strength or a non-finite result;  D anfis_route = _effective_weights(firing) @ c"
)

ordinary: dict[str, list[RuleFiringResult]] = {"first_ensemble_run endpoint seeds 0..3 (T1)": []}
mfs_end = [
    fer._default_mfs_for_feature(n, fer.MF_PLACEMENT_ENDPOINT)
    for n in BasicCalibrationVectorizer().feature_names
]
for seed in range(4):
    rb = TSKRuleBase.from_grid(
        per_input_mfs=mfs_end,
        output_dim=2,
        consequent_init="random",
        rng=np.random.default_rng(seed),
    )
    ordinary["first_ensemble_run endpoint seeds 0..3 (T1)"] += [rb.evaluate(x) for x in points_si]
rb_zero = TSKRuleBase.from_grid(per_input_mfs=mfs_end, output_dim=2, consequent_init="zeros")
ordinary["zero consequents (consequent_init='zeros', T1)"] = [
    rb_zero.evaluate(x) for x in points_si
]
ordinary["g59 anchored, survey rows (IT2)"] = it2_firings_g59
for interval in (False, True):
    rb = _planted_grid(interval, warm=False)
    ordinary[f"tests' _planted_grid {'IT2' if interval else 'T1'} on _planted_box_features"] = [
        rb.evaluate(x) for x in _planted_box_features()
    ]
print(
    "   set                                                outputs  variant         differ from shipped  raise  max error vs exact, eps of sum f|c|/sum f (shipped -> variant)"
)
for sname, firings in ordinary.items():
    ref = [exact(f) for f in firings]
    scale = [error_scale(f) for f in firings]
    zero_scale = all(np.all(s == 0.0) for s in scale)
    base = [shipped(f) for f in firings]
    base_err = (
        0.0
        if zero_scale
        else max(scaled_err(b, r, s) for b, r, s in zip(base, ref, scale, strict=True))
    )
    n_out = sum(b.size for b in base)
    for label in ("A port143", "B fallback", "C contract", "D anfis_route"):
        n_diff = n_raise = 0
        v_err = 0.0
        for f, b, r, s in zip(firings, base, ref, scale, strict=True):
            try:
                y = VARIANTS[label](f)
            except (ZeroDivisionError, OverflowError):
                n_raise += 1
                continue
            n_diff += int(np.sum(y.view(np.uint64) != b.view(np.uint64)))
            if not zero_scale:
                v_err = max(v_err, scaled_err(y, r, s))
        tail = (
            "all outputs exactly 0.0 by construction"
            if zero_scale
            else f"{base_err:.2f} -> {v_err:.2f}"
        )
        print(f"   {sname:<51} {n_out:<8} {label:<15} {n_diff:<20} {n_raise:<6} {tail}")
        if label in ("B fallback", "C contract"):
            check(
                f"6 {sname}: {label} keeps every shipped bit and raises nowhere",
                n_diff == 0 and n_raise == 0,
            )
        elif not zero_scale:
            check(f"6 {sname}: {label} moves some bits", n_diff > 0)
        check(f"6 {sname}: {label} stays rounding-level (< 64 eps)", v_err < 64)

# --------------------------------------------------------------------------------------
# 7 FR-3 bound in tests/test_anfis.py
# --------------------------------------------------------------------------------------

h(
    "7  tests/test_anfis.py::test_effective_weights_match_shipped_defuzzifier: |anfis - class| / (eps * sum|w||c|), bound 8"
)
print("   (the test's comment: measured worst 3.6 (T1) and 2.7 (IT2) on 2026-10-15)")
for interval in (False, True):
    rb = _planted_grid(interval, warm=False)
    firings = [rb.evaluate(x) for x in _planted_box_features()]
    for label in ("shipped", "A port143", "B fallback", "C contract"):
        worst = 0.0
        for firing in firings:
            weights = _effective_weights(firing)
            assert weights is not None
            pred = weights @ firing.consequent_outputs
            got = VARIANTS[label](firing)
            scale = np.sum(np.abs(weights)[:, None] * np.abs(firing.consequent_outputs), axis=0)
            worst = max(worst, float(np.max(np.abs(pred - got) / (EPS * scale))))
        print(
            f"   {'IT2' if interval else 'T1 '} class computed as {label:<11}: worst {worst:.2f} eps of sum|w||c|"
        )
        check(f"7 {'IT2' if interval else 'T1'} {label}: inside the test's 8 eps", worst <= 8.0)

# --------------------------------------------------------------------------------------
# 8 timing
# --------------------------------------------------------------------------------------

h("8  timing per call, one run on this laptop (provisional): interleaved passes, fastest pass kept")
cases = {
    "T1 27 rules, 2 outputs": ordinary["first_ensemble_run endpoint seeds 0..3 (T1)"][_row],
    "IT2 27 rules, 2 outputs": it2_firings_g59[_row],
}
CALLS, PASSES = 2000, 15
for cname, firing in cases.items():
    best = dict.fromkeys(VARIANTS, math.inf)
    for _ in range(PASSES):
        for label, fn in VARIANTS.items():
            t0 = time.perf_counter()
            for _ in range(CALLS):
                fn(firing)
            best[label] = min(best[label], (time.perf_counter() - t0) / CALLS)
    print(f"   {cname}: " + "  ".join(f"{label} {best[label] * 1e6:.2f} us" for label in VARIANTS))
print(f"   machine: {platform.processor() or platform.machine()}; {CALLS} calls x {PASSES} passes")
print(
    "   B and C are prototypes in Python around the class's expression; their extra cost is the checks'"
)
print("   numpy calls, not a property of the arithmetic.")

h("checks (every claim the draft cites)")
for _name, _ok in CHECKS:
    print(f"   [{'PASS' if _ok else 'FAIL'}] {_name}")
_failed = [n for n, ok in CHECKS if not ok]
print(f"   {len(CHECKS) - len(_failed)} passed, {len(_failed)} failed")
sys.exit(1 if _failed else 0)
