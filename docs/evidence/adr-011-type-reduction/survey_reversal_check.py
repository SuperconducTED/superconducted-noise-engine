"""#61: is the survey-row reversal real? The 12 cells on the 975 survey rows, read several ways.

For each (grid, convention, output): median ``Db`` for both reducers, the share of rows where BMM is
closer, the same on distinct feature vectors only, and a 90% circular block bootstrap of the median
difference over consecutive rows, because rows are a time series. Also the two halves of the series
for the cell that reverses. No hardware. Laptop figures are provisional.

Run from the repository root, with ``PYTHONPATH=src``::

    python docs/evidence/adr-011-type-reduction/survey_reversal_check.py
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
    exhaustive_type_reduce,
    load_survey,
    nie_tan_reduce,
)

SURVEY = Path("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv")
TOKENS = ("0.1", "0.3", "0.6", "g59")
EPS = float(np.finfo(np.float64).eps)
BLOCK_ROWS = 30
BLOCK_SENSITIVITY = (8, 30, 90)
RESAMPLES = 2000
SEED = 611107


def scores(token: str, convention, output_index: int, survey, anchors) -> dict[str, np.ndarray]:
    """Per survey row: ``Db`` for each reducer, the band width, and ``|y_BMM - y_NT|``."""
    rule_base = convention.build(build_grid(token, survey), anchors)
    out: dict[str, list[float]] = {"bmm": [], "nt": [], "width": [], "gap": [], "y_nt": []}
    for x in survey.samples:
        firing = rule_base.evaluate(np.asarray(x, dtype=np.float64))
        lo, hi = firing.firing_strengths_lower, firing.firing_strengths_upper
        c = firing.consequent_outputs[:, output_index]
        # The band from the exhaustive route (PR #143 review, item 1).
        y_l, y_r = exhaustive_type_reduce(lo, hi, c)
        width = y_r - y_l
        mid = 0.5 * (y_l + y_r)
        y_bmm, y_nt = bmm_half_reduce(lo, hi, c), nie_tan_reduce(lo, hi, c)
        degenerate = width <= 64 * c.size * EPS * float(np.max(np.abs(c)))
        out["bmm"].append(0.0 if degenerate else abs(y_bmm - mid) / width)
        out["nt"].append(0.0 if degenerate else abs(y_nt - mid) / width)
        out["width"].append(width)
        out["gap"].append(abs(y_bmm - y_nt))
        out["y_nt"].append(y_nt)
    return {key: np.array(values) for key, values in out.items()}


def block_interval(
    a: np.ndarray, b: np.ndarray, rng: np.random.Generator, block: int = BLOCK_ROWS
) -> np.ndarray:
    """90% circular block bootstrap of ``median(a) - median(b)``, consecutive rows, paired."""
    rows = len(a)
    n_blocks = -(-rows // block)
    diffs = []
    for _ in range(RESAMPLES):
        starts = rng.integers(0, rows, n_blocks)
        index = ((starts[:, None] + np.arange(block)[None, :]) % rows).reshape(-1)[:rows]
        diffs.append(np.median(a[index]) - np.median(b[index]))
    return np.percentile(diffs, [5, 95])


def main() -> None:
    survey = load_survey(SURVEY)
    anchors = anchor_levels(survey.samples)
    samples = np.asarray(survey.samples)
    distinct = np.sort(np.unique(samples, axis=0, return_index=True)[1])
    rng = np.random.default_rng(np.random.SeedSequence(SEED))
    print(f"survey rows {len(samples)}, distinct feature vectors {len(distinct)}")
    print(
        "\ngrid  convention  output  |  BMM     NT      BMM closer | distinct: BMM NT closer"
        " | 90% interval, BMM - NT"
    )
    results = {}
    for token in TOKENS:
        for convention in CONVENTIONS:
            for index, output in enumerate(convention.outputs):
                r = scores(token, convention, index, survey, anchors)
                results[(token, convention.name, output)] = r
                low, high = block_interval(r["bmm"], r["nt"], rng)
                d_bmm, d_nt = r["bmm"][distinct], r["nt"][distinct]
                print(
                    f"{token:5s} {convention.name:11s} {output:7s} | "
                    f"{np.median(r['bmm']):.4f}  {np.median(r['nt']):.4f}  "
                    f"{(r['bmm'] < r['nt']).mean():.3f}      | "
                    f"{np.median(d_bmm):.4f} {np.median(d_nt):.4f} {(d_bmm < d_nt).mean():.3f} | "
                    f"[{low:8.4f}, {high:8.4f}]"
                )
    print("\nThe two cells whose BMM median is lower, by block length in rows:")
    for key in (("g59", "anchored", "lambda"), ("0.1", "anchored", "lambda")):
        for block in BLOCK_SENSITIVITY:
            r = results[key]
            low, high = block_interval(r["bmm"], r["nt"], rng, block)
            print(f"  {key[0]:5s} {key[2]:7s} block {block:3d}: [{low:8.4f}, {high:8.4f}]")
    cell = results[("g59", "anchored", "lambda")]
    half = len(cell["bmm"]) // 2
    print("\nG59 anchored lambda:")
    print(f"  BMM closer on {(cell['bmm'] < cell['nt']).sum()} of {len(cell['bmm'])} rows,")
    print(
        f"  on {(cell['bmm'][distinct] < cell['nt'][distinct]).sum()} of {len(distinct)} distinct"
    )
    print(f"  first half: {np.median(cell['bmm'][:half]):.4f}, {np.median(cell['nt'][:half]):.4f}")
    print(f"  second half: {np.median(cell['bmm'][half:]):.4f}, {np.median(cell['nt'][half:]):.4f}")
    print(f"  |y_BMM - y_NT| max {cell['gap'].max():.3e}, median {np.median(cell['gap']):.3e}")
    print(f"  band width median {np.median(cell['width']):.3e}")
    level = float(np.median(cell["y_nt"]))
    spread = (cell["y_nt"].max() - cell["y_nt"].min()) / level
    print(f"  y_NT median {level:.3e}, moving {spread:.3f} of it across the rows")
    print(f"  gap over that median: max {cell['gap'].max() / level:.4f}, ")
    print(f"  median {np.median(cell['gap']) / level:.4f}")


if __name__ == "__main__":
    main()
