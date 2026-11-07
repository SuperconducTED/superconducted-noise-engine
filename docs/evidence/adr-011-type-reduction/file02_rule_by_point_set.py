"""#61: File 02's reducer rule on each point set, and the G59 anchored lambda reversal.

Written by @mertefesensoy, posted with #61 comment 6665986289 (2026-11-05). Committed here with
only this docstring changed and the formatter's and linter's line wrapping, so that File 02's
figures have a command behind them.

Run from the repository root, with ``PYTHONPATH=src``::

    python docs/evidence/adr-011-type-reduction/file02_rule_by_point_set.py

File 02 section 2.4's rule: per output, the lower median of Db pooled over all grids and both
conventions. As in File 02, unit-spread's one output enters both the gamma and the lambda pool,
which gives its 24016 scores per output. Uses the functions in
scripts/type_reduction_discrepancy.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from scripts.type_reduction_discrepancy import (
    CONVENTIONS,
    anchor_levels,
    bmm_half_reduce,
    build_grid,
    karnik_mendel_detailed,
    load_survey,
    nie_tan_reduce,
    point_sets,
)

SURVEY = Path("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv")
TOKENS = ("0.1", "0.3", "0.6", "g59")
EPS = float(np.finfo(np.float64).eps)
OUTPUT_POOLS = ("gamma", "lambda")


def score(y: float, y_l: float, y_r: float, tol: float) -> float:
    width = y_r - y_l
    return 0.0 if width <= tol else min(abs(y - 0.5 * (y_l + y_r)) / width, 0.5)


def main() -> None:
    survey = load_survey(SURVEY)
    sets = point_sets(("lattice", "uniform", "survey"), survey, 2000, 84)
    anchors = anchor_levels(survey.samples)
    pools = {name: {o: {"bmm": [], "nt": []} for o in OUTPUT_POOLS} for name in (*sets, "all")}
    closer: dict[tuple[str, str, str], list[int]] = {}
    gaps: list[float] = []
    widths: list[float] = []

    for token in TOKENS:
        grid = build_grid(token, survey)
        for convention in CONVENTIONS:
            rule_base = convention.build(grid, anchors)
            for set_name, points in sets.items():
                for x in points:
                    firing = rule_base.evaluate(np.asarray(x, dtype=np.float64))
                    lo, hi = firing.firing_strengths_lower, firing.firing_strengths_upper
                    for oi, output in enumerate(convention.outputs):
                        c = firing.consequent_outputs[:, oi]
                        tol = 64 * c.size * EPS * float(np.max(np.abs(c)))
                        km = karnik_mendel_detailed(lo, hi, c)
                        y_bmm, y_nt = bmm_half_reduce(lo, hi, c), nie_tan_reduce(lo, hi, c)
                        a, b = score(y_bmm, km.y_l, km.y_r, tol), score(y_nt, km.y_l, km.y_r, tol)
                        for target in OUTPUT_POOLS if output not in OUTPUT_POOLS else (output,):
                            for name in (set_name, "all"):
                                pools[name][target]["bmm"].append(a)
                                pools[name][target]["nt"].append(b)
                        if set_name == "survey":
                            tally = closer.setdefault((token, convention.name, output), [0, 0, 0])
                            tally[0 if b < a else (1 if a < b else 2)] += 1
                            if (token, convention.name, output) == ("g59", "anchored", "lambda"):
                                gaps.append(abs(y_bmm - y_nt))
                                widths.append(km.y_r - km.y_l)

    print(f"{'point set':10s} {'output':7s} {'n':>7s} {'BMM':>8s} {'Nie-Tan':>8s}  winner")
    for name in ("lattice", "uniform", "survey", "all"):
        for output in OUTPUT_POOLS:
            a, b = np.median(pools[name][output]["bmm"]), np.median(pools[name][output]["nt"])
            n = len(pools[name][output]["bmm"])
            print(
                f"{name:10s} {output:7s} {n:7d} {a:8.4f} {b:8.4f}  {'Nie-Tan' if b < a else 'BMM'}"
            )

    print(
        f"\nsurvey rows {len(survey.samples)}, distinct: {len(np.unique(survey.samples, axis=0))}"
    )
    print(
        f"{'grid':6s} {'convention':12s} {'output':7s} "
        f"{'NT closer':>10s} {'BMM closer':>11s} {'tie':>5s}"
    )
    for (token, conv, output), tally in sorted(closer.items()):
        print(f"{token:6s} {conv:12s} {output:7s} {tally[0]:10d} {tally[1]:11d} {tally[2]:5d}")

    assert gaps, "the G59 anchored lambda cell was not reached"
    print(f"\nG59 anchored lambda, survey: |y_BMM - y_NT| max {max(gaps):.3e}")
    print(f"G59 anchored lambda, survey: band width median {np.median(widths):.3e}")


if __name__ == "__main__":
    main()
