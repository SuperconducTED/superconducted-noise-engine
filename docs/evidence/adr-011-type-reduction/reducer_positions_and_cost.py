"""#61: where the reducers sit in the Karnik-Mendel band, and what type reduction costs.

The identity: ``y_NT = (S_lo Y_lo + S_hi Y_hi) / (S_lo + S_hi)``, ``y_BMM = (Y_lo + Y_hi) / 2``,
so ``y_NT - y_BMM = (S_hi - S_lo)(Y_hi - Y_lo) / (2 (S_lo + S_hi))``. It is checked on every
survey row.

A hypothesis tested and rejected here: that BMM wins a cell when ``Y_lo`` and ``Y_hi`` straddle the
midpoint. The correlation across the 12 cells is printed. The mutation uses ``y_l`` as the reference
in place of the midpoint, which must break the score: it moves ``Db`` to about 1/2.

Cost: wall time per point on 27 rules, laptop, provisional, and only meaningful as a ratio. Since
2026-11-11 (PR #143 review, item 3) it is printed three ways: through the public functions, input
validation alone, and the arithmetic alone on validated arrays, because validation is most of a
closed-form reducer's time. The band comes from ``exhaustive_type_reduce`` (item 1).

Run from the repository root, with ``PYTHONPATH=src``::

    python docs/evidence/adr-011-type-reduction/reducer_positions_and_cost.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from scripts.type_reduction_discrepancy import (
    CONVENTIONS,
    _km_endpoint,
    _sorted_by_value,
    _switch_vertex,
    _validated,
    _weighted_average,
    anchor_levels,
    bmm_half_reduce,
    build_grid,
    exhaustive_type_reduce,
    karnik_mendel_detailed,
    load_survey,
    nie_tan_reduce,
)

SURVEY = Path("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv")
TOKENS = ("0.1", "0.3", "0.6", "g59")
COST_PASSES = 7


def positions(firings, output_index: int) -> dict[str, np.ndarray]:
    """Per row: position in the band (0 is ``y_l``, 1 is ``y_r``) and the identity's error."""
    out: dict[str, list[float]] = {
        "y_lo": [],
        "y_hi": [],
        "bmm": [],
        "nt": [],
        "rho": [],
        "wrong_reference": [],
        "identity_error": [],
    }
    for firing in firings:
        lo, hi = firing.firing_strengths_lower, firing.firing_strengths_upper
        c = firing.consequent_outputs[:, output_index]
        # The band from the exhaustive route (PR #143 review, item 1).
        y_l, y_r = exhaustive_type_reduce(lo, hi, c)
        width = y_r - y_l
        s_lo, s_hi = lo.sum(), hi.sum()
        y_lo, y_hi = (lo * c).sum() / s_lo, (hi * c).sum() / s_hi
        y_bmm, y_nt = bmm_half_reduce(lo, hi, c), nie_tan_reduce(lo, hi, c)
        predicted = (s_hi - s_lo) * (y_hi - y_lo) / (2 * (s_lo + s_hi))
        out["y_lo"].append((y_lo - y_l) / width)
        out["y_hi"].append((y_hi - y_l) / width)
        out["bmm"].append((y_bmm - y_l) / width)
        out["nt"].append((y_nt - y_l) / width)
        out["rho"].append(s_hi / s_lo)
        out["wrong_reference"].append(abs(y_nt - y_l) / width)
        out["identity_error"].append(abs((y_nt - y_bmm) - predicted))
    return {key: np.array(values) for key, values in out.items()}


def _timed(function, arguments) -> float:
    """Median over ``COST_PASSES`` passes of the mean wall time per call."""
    times = []
    for _ in range(COST_PASSES):
        start = time.perf_counter()
        for args in arguments:
            function(*args)
        times.append((time.perf_counter() - start) / len(arguments))
    return float(np.median(times))


def report(rows, base: float | None = None) -> float:
    """Print each row's time per point and its ratio to ``base`` (the first row by default)."""
    for name, function, arguments in rows:
        value = _timed(function, arguments)
        base = base or value
        print(f"  {name:32s} {value * 1e6:8.1f} us  {value / base:6.1f} x")
    assert base is not None
    return base


def _bmm_arithmetic(lo, hi, c) -> float:
    return 0.5 * _weighted_average(lo, c) + 0.5 * _weighted_average(hi, c)


def _km_arithmetic(lo, hi, c) -> tuple:
    return _km_endpoint(lo, hi, c, "left"), _km_endpoint(lo, hi, c, "right")


def _km_with_sort(lo, hi, c) -> tuple:
    return _km_arithmetic(*_sorted_by_value(lo, hi, c))


def _exhaustive_arithmetic(lo, hi, c) -> tuple[float, float]:
    points = range(c.size + 1)
    y_l = min(_weighted_average(_switch_vertex(lo, hi, k, "left"), c) for k in points)
    y_r = max(_weighted_average(_switch_vertex(lo, hi, k, "right"), c) for k in points)
    return y_l, y_r


def main() -> None:
    survey = load_survey(SURVEY)
    anchors = anchor_levels(survey.samples)
    samples = np.asarray(survey.samples, dtype=np.float64)
    print("Median position in the band, survey rows; 0.5 is the Karnik-Mendel midpoint")
    print(
        "grid  convention  output  |  rho  | Y_lo    Y_hi    BMM     NT     | straddle"
        " | Db BMM  Db NT   BMM closer | mutated"
    )
    straddle, closer, worst = [], [], 0.0
    for token in TOKENS:
        for convention in CONVENTIONS:
            rule_base = convention.build(build_grid(token, survey), anchors)
            firings = [rule_base.evaluate(x) for x in samples]
            for index, output in enumerate(convention.outputs):
                p = positions(firings, index)
                d_bmm, d_nt = np.abs(p["bmm"] - 0.5), np.abs(p["nt"] - 0.5)
                across = (p["y_lo"] - 0.5) * (p["y_hi"] - 0.5) < 0
                straddle.append(across.mean())
                closer.append((d_bmm < d_nt).mean())
                worst = max(worst, float(p["identity_error"].max()))
                print(
                    f"{token:5s} {convention.name:11s} {output:7s} | {np.median(p['rho']):5.1f} | "
                    f"{np.median(p['y_lo']):.4f}  {np.median(p['y_hi']):.4f}  "
                    f"{np.median(p['bmm']):.4f}  {np.median(p['nt']):.4f} | {across.mean():.3f}"
                    f"    | {np.median(d_bmm):.4f}  {np.median(d_nt):.4f}  "
                    f"{(d_bmm < d_nt).mean():.3f}      | {np.median(p['wrong_reference']):.3f}"
                )
    print(f"\nIdentity, largest absolute error over all cells: {worst:.2e}")
    correlation = np.corrcoef(straddle, closer)[0, 1]
    print(f"Correlation across 12 cells, share straddling, share BMM closer: {correlation:.3f}")

    anchored = next(c for c in CONVENTIONS if c.name == "anchored")
    rule_base = anchored.build(build_grid("g59", survey), anchors)
    lambda_index = anchored.outputs.index("lambda")
    items = []
    for x in samples:
        firing = rule_base.evaluate(x)
        c = firing.consequent_outputs[:, lambda_index]
        items.append((firing.firing_strengths_lower, firing.firing_strengths_upper, c))
    print(f"\nCost per point, 27 rules, median of {COST_PASSES} passes over {len(items)} points")
    print("G59 anchored lambda; python and numpy; laptop, provisional")
    validated = [_validated(lo, hi, c) for lo, hi, c in items]
    ordered = [_sorted_by_value(*v) for v in validated]
    print("Through the public functions, each validating its input (ratio to nie_tan_reduce):")
    public = (
        ("nie_tan_reduce", nie_tan_reduce, items),
        ("bmm_half_reduce", bmm_half_reduce, items),
        ("karnik_mendel_detailed", karnik_mendel_detailed, items),
        ("exhaustive_type_reduce", exhaustive_type_reduce, items),
    )
    base = report(public)
    print("Input validation alone, the part every public function shares:")
    report((("_validated", _validated, items),), base)
    print("Arithmetic alone, on validated arrays (ratio to Nie-Tan's arithmetic):")
    arithmetic = (
        ("Nie-Tan", lambda lo, hi, c: _weighted_average(lo + hi, c), validated),
        ("BMM(1/2, 1/2)", _bmm_arithmetic, validated),
        ("iterative KM, sorted once", _km_arithmetic, ordered),
        ("iterative KM, sorting each point", _km_with_sort, validated),
        ("exhaustive, sorted once", _exhaustive_arithmetic, ordered),
    )
    report(arithmetic)
    results = [karnik_mendel_detailed(lo, hi, c) for lo, hi, c in items]
    for field in ("passes_l", "passes_r", "guard_stops"):
        values = np.array([getattr(r, field) for r in results], dtype=np.float64)
        print(f"  {field}: mean {values.mean():.2f}, max {values.max():.0f}")


if __name__ == "__main__":
    main()
