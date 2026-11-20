# Defuzzification scaling: evidence behind the issue on unscaled weighted sums

Scripts and outputs behind the issue about `src/superconducted/fuzzy/defuzzification.py`
(`WeightedAverageDefuzzifier`, `NieTanDefuzzifier`). Measured at `main` @ `58f7f63c`, whose `src/`,
`tests/` and `scripts/` are identical to `667972c5`. Nothing under `src/` is changed by this folder.
Laptop figures (Windows 11, Python 3.12.10, NumPy 2.4.4, the pinned `C:/pvci` interpreter), provisional;
canonical verification is on Burak's desktop.

## Problem / Motivation

Both classes form `(firing[:, None] * consequents).sum(axis=0) / total` with no scaling. Finite but huge
consequents overflow to `inf`, and firing strengths near the subnormal floor make every product round to
zero, so `Y(lower) = 0.0`, below every consequent. PR #143 fixed the same arithmetic in its reference
implementation (`scripts/type_reduction_discrepancy.py::_weighted_average` at `ae8d2bf9`, findings
section 15.2) and left the shipped module for a separate issue (findings section 17.4, comment 7029369115).
This folder reproduces both defects on `main`, measures whether any shipped configuration reaches them,
and measures what each candidate fix would move.

## What changed

| File | What it is |
| --- | --- |
| `README.md` | This file. |
| `defuzz_min_repro.py`, `.out.txt` | Five cases (O1, O2, U1 to U3), each built so the shipped code must fail; exits 0 only if it does. Pasted in the issue. |
| `defuzz_scaling_repro.py`, `.out.txt` | The full measurement: sections 0 to 8 and 112 named checks (exit 1 if any fails). |
| `defuzz_variant_plugin.py` | pytest plugin that patches one option into both classes, keeping their guards and messages. |
| `defuzz_suite_by_variant.sh` | Runs the full suite once per variant, in parallel, and writes the outputs below. |
| `defuzz_suite_<variant>.out.txt`, `defuzz_suite_summary.out.txt` | Suite results for `shipped`, `A`, `B`, `C`, `D` and the controls `X12`, `X6`. |

## Implementation approach

Every value is compared with an exact reference: `fractions.Fraction` of the same doubles, rounded once.
A hull test (output inside `[min c, max c]`) is printed beside it only to show that it misses errors in
`NieTanDefuzzifier` (case U3, and 2 of the 3 band points at `w = 0.99`). Repro inputs are constructed so
the failure is guaranteed: same-sign consequents whose products sum past `DBL_MAX`, and `f = 1e-322`
(`20 x 2**-1074`) with every `|c| < 1/40`, so every product is at most `2**-1075`. A control (U4,
`c = [0.02, 0.03]`) shows an unbuilt input can come out right by accident.

Reach is measured on the one shipped builder of a defuzzifier (`scripts/first_ensemble_run.py`, T1,
no clamp) over the 975 rows of `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv` (microseconds
converted to seconds) plus the fixture through `BasicCalibrationVectorizer.extract`, for both MF
placements and all 64 consequent seeds the viability search can pick; and on IT2 grids buildable on
`main` (G59, footprint ratios `w` as in #143's `footprint_grid`) with `anchored_rule_base` consequents,
over the survey rows and 1000 uniform draws in the `[p1, p99]` box (seed 20261120).

The five options are implemented as small functions in the script and the plugin: A (#143's helper per
output, `0.5*a + 0.5*b` for IT2), B (shipped bits unless a numerator is subnormal or a quotient is not
finite), C (shipped, but raise for a subnormal largest firing strength or a non-finite result), D
(`training/anfis.py::_effective_weights(firing) @ consequents`), E (no change, so the shipped code).

## Mathematical / Statistical details

With `f_max = exp(-S)` the largest firing strength and, for a product of Gaussian MFs,
`S = (1/2) sum_i z_i^2` (`z_i` the distance of input `i` to its nearest centre in widths):

- products stay at rounding level while `max_r f_r |c_r| >= 2**-1022`, i.e. `S <= 1022 ln 2 + ln|c|`
  (`1022 ln 2 = 708.3964`);
- a product rounds to `0.0` when `f_r |c_r| <= 2**-1075`, i.e. `S >= 1075 ln 2 + ln|c|`
  (`1075 ln 2 = 745.1332`);
- the firing itself is `0.0` for `S > 745.1332` (measured on `math.exp` by bisection), where the class
  already raises `ZeroDivisionError`.

The silent band is between the first and the last: for `|c| = 0.1`, `S` in `(706.09, 745.13]`,
distance `sqrt(2 S)` in `(37.58, 38.60]` widths. Margins are reported as
`log10(max_r f_r |c_r| / 2**-1022)` in decades; the all-seed figure pairs the smallest `max_r f_r` with
the smallest `|c|`, so it is a lower bound. Ordinary-input errors are in eps of `sum f |c| / sum f`
(the measure of `tests/test_anfis.py::test_effective_weights_match_shipped_defuzzifier`), because random
consequents of mixed sign cancel and a relative error would measure the cancellation.

## Design decisions

- Exact reference instead of the hull test: the hull test under-counts (above).
- Tree passed as an argument and blob hashes pinned: `-I` drops `PYTHONPATH`, and a copy run from another
  folder could otherwise import another checkout through the interpreter's own install; the script stops
  unless the four files it reads match `58f7f63c`.
- Suite runs patch the classes from a plugin instead of editing `src/`, so the tree measured is `main`.
  The two controls calibrate what the suite can see: a pass under A or D means little without them.
- Timing interleaves the variants within each pass and keeps the fastest pass; it is one run on one
  laptop, and B and C are Python prototypes whose extra cost is their checks' NumPy calls.

## Verification

```
C:/pvci/Scripts/python.exe -I docs/evidence/defuzzification-scaling/defuzz_min_repro.py .
C:/pvci/Scripts/python.exe -I docs/evidence/defuzzification-scaling/defuzz_scaling_repro.py .
bash docs/evidence/defuzzification-scaling/defuzz_suite_by_variant.sh .
```

Expected: the first prints `all as described` and exits 0; the second ends `112 passed, 0 failed` and
exits 0; the third gives `1203 passed` for `shipped`, `A`, `B`, `C` and `D`, `2 failed` for `X12` (both
`test_effective_weights_match_shipped_defuzzifier` cases) and `9 failed` for `X6`. Only the timing lines
of section 8 and the suites' wall times change between runs. Not measured: open PR branches (#143, #152,
#155) and Burak's desktop.

## Related docs

- PR #143 (#61 Part A): `scripts/type_reduction_discrepancy.py` at `ae8d2bf9`, findings sections 15.2 and 17.4
- `docs/team.md`: `fuzzy/defuzzification.py` (primary Bengisu, secondary Burak)
- `docs/numerical-claims.md`: NC-004 (per-member cost), NC-021 (suite size), NC-035 (`sx` length), NC-042 (`s_i`)
