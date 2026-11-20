# 2026-11-20: defuzzification-scaling-evidence

## Problem / Motivation

`WeightedAverageDefuzzifier` and `NieTanDefuzzifier` in `src/superconducted/fuzzy/defuzzification.py` form
`(firing[:, None] * consequents).sum(axis=0) / total` with no scaling. That has two failure modes. Finite but huge
consequents overflow to `inf`. Firing strengths near the subnormal floor round every product to zero, so `Y(lower) = 0.0`,
below every consequent.

PR #143 (#61 Part A) met the same arithmetic in its reference implementation, after Burak Öztekin's desktop review
5923434762. It changed its own helper (`scripts/type_reduction_discrepancy.py::_weighted_average` at `ae8d2bf9`, findings
section 15.2) and left the shipped module for a separate issue (findings section 17.4; Bengisu's comment 7029369115). That
issue is drafted but not opened.

The evidence folder this record covers does three things:

- reproduces both failures on `main`;
- measures whether any shipped or committed configuration reaches them;
- measures what each candidate change would move: bits, the test suite and cost per call.

The issue cites the evidence by commit. It changes no source, test, register or workflow file.

## What changed

All evidence files are in `docs/evidence/defuzzification-scaling/`. Commit `1ab3af89` adds them, `4b1b6c2d` changes one
README sentence, and this record is the third commit.

| File | One-sentence description |
| --- | --- |
| `README.md` | What was measured, at which commit, how and with what expected results; `4b1b6c2d` adds that the `X12` and `X6` tracebacks' object addresses also change between runs. |
| `defuzz_min_repro.py` | The five constructed cases (O1, O2, U1 to U3), using the shipped classes and an exact reference; it exits 0 only if the shipped code fails as described. |
| `defuzz_min_repro.out.txt` | The output of `defuzz_min_repro.py`, ending `all as described`. |
| `defuzz_scaling_repro.py` | The full measurement in sections 0 to 8, with 112 named checks; it exits 1 if any check fails. |
| `defuzz_scaling_repro.out.txt` | The output of `defuzz_scaling_repro.py`, ending `112 passed, 0 failed`. |
| `defuzz_variant_plugin.py` | A pytest plugin that patches one candidate (or one control) into both classes' `defuzzify` and counts the patched calls. |
| `defuzz_suite_by_variant.sh` | Runs the full suite once per variant, in parallel, with the plugin, and writes the outputs below. |
| `defuzz_suite_shipped.out.txt` | The suite with no patch: 1203 passed. |
| `defuzz_suite_A.out.txt` | The suite with option A (PR #143's helper per output column) patched in: 1203 passed. |
| `defuzz_suite_B.out.txt` | The suite with option B (shipped bits, falling back to A only where needed) patched in: 1203 passed. |
| `defuzz_suite_C.out.txt` | The suite with option C (shipped bits, raising on the two failure inputs) patched in: 1203 passed. |
| `defuzz_suite_D.out.txt` | The suite with option D (normalise first, the trainer's route) patched in: 1203 passed. |
| `defuzz_suite_X12.out.txt` | Control: the shipped value times `1 + 1e-12`; 2 failed. |
| `defuzz_suite_X6.out.txt` | Control: the shipped value times `1 + 1e-6`; 9 failed. |
| `defuzz_suite_summary.out.txt` | One line per variant: result, wall time, patched-call counts and exit status. |
| `docs/implementations/2026-11-20-defuzzification-scaling-evidence.md` | This record. |

## Implementation approach

**The inputs are built to fail.** Each case is constructed so the shipped arithmetic must fail. Searching for failures
could miss some, and a lucky input can come out right.

- Overflow cases (O1, O2): same-sign consequents whose weighted sum passes `DBL_MAX`.
- Underflow cases (U1 to U3): `f = 1e-322` with every `|c| < 1/40`, so every product rounds to zero.
- Control (U4, `c = [0.02, 0.03]`): one product rounds up instead, and the shipped output happens to be right. It shows
  why the inputs had to be built.

**Every value has an exact reference.** Each output is compared with the exact rational value of the same formula on
the same doubles (see the next section). A hull test ("is the output inside `[min c, max c]`") is printed beside it only
to show what it misses. In `NieTanDefuzzifier` a wrong output can stay inside the hull, as case U3 does.

**The measured tree is pinned.** The scripts take the tree as their one argument and run under `python -I`, which drops
`PYTHONPATH`, so they insert `<tree>/src` themselves. They print the imported package's path. They stop unless the four
files they read (`defuzzification.py`, `training/anfis.py`, `scripts/first_ensemble_run.py` and the feature survey) have
the blob hashes they have at `58f7f63c`.

**Reach is measured where the classes are actually used.**

- `scripts/first_ensemble_run.py` is the only shipped code that builds a defuzzifier: T1, with no clamp. It is measured
  on:
  - the 975 rows of `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv`, converted from microseconds to
    seconds;
  - the fixture, through `BasicCalibrationVectorizer.extract`;
  - both MF placements;
  - all 64 consequent seeds its viability search can pick.
- `NieTanDefuzzifier` has no shipped caller. It is measured on the IT2 grids that `main` can build (G59 and the footprint
  ratios `w` of #143's `footprint_grid`), with `anchored_rule_base` consequents. The points are the survey rows and 1000
  uniform draws in the `[p1, p99]` box (seed 20261120).

**The candidates are small functions.** Each option is a few lines in the script and in the plugin:

- A: PR #143's `_weighted_average` per output column, with `0.5*a + 0.5*b` as the IT2 last line.
- B: the shipped expression, redone with A only where a numerator is subnormal or a quotient is not finite.
- C: the shipped expression, raising `ZeroDivisionError` for a subnormal largest firing strength and `OverflowError` for
  a non-finite result.
- D: `training/anfis.py::_effective_weights(firing) @ consequents`.
- E: no change, which is the shipped code.

The plugin replaces the two `defuzzify` methods at `pytest_configure` and leaves every shipped guard to the original
method, so a zero firing sum or a T1 result passed to `NieTanDefuzzifier` raises the shipped exception with the shipped
message.

**Timing.** The variants are interleaved within each pass, and the fastest of 15 passes of 2000 calls is kept.

## Mathematical / Statistical details

### Notation

| Symbol | Meaning |
| --- | --- |
| `f_r >= 0` | Firing strength of rule `r`, for `n` rules. |
| `c_rd` | Consequent output of rule `r` for output `d` at the input point (first-order TSK, so it depends on the input). |
| `Y_d = sum_r f_r c_rd / sum_r f_r` | The T1 output. |
| `Y = (Y(lower) + Y(upper)) / 2` | The IT2 class's output, which is BMM(1/2, 1/2), with each bound's `Y` formed the same way. |
| `TINY = 2**-1022` | The smallest normal double. |
| `u = 2**-1074` | The smallest subnormal double. |
| `DBL_MAX` | About `1.797693e308`. |
| `eps = 2**-52` | NumPy's `finfo(float64).eps`. |

### Exact reference

Every finite double is a rational number, and `fractions.Fraction(x)` holds it exactly. The reference takes the
firing strengths and consequent outputs as given, forms `sum_r f_r c_rd` and `sum_r f_r` in exact rationals, divides,
and converts to a double once. `float(Fraction)` rounds to nearest. For IT2 the two bounds' exact values are averaged
exactly, then rounded once.

So the reference is the correctly rounded value of the formula on the inputs it was given. Any difference from it comes
from the class's arithmetic. Rounding inside the firing strengths themselves (computed upstream in `fuzzy/tsk.py`) is
not counted against the defuzzifier.

### Rounding below the normal range

- At or above `TINY`: a product `p = f c` is rounded with relative error at most `2**-53`.
- Below `TINY`: the spacing of doubles is fixed at `u`, so the absolute error is at most `u/2 = 2**-1075`. The relative
  error therefore grows as `|p|` shrinks.
- Rounding to zero: a product becomes `0.0` exactly when `|p| <= 2**-1075`. At exactly `2**-1075` the tie goes to the
  even neighbour, which is `0`.
- The repro inputs: `1e-322` as a double is `20 u`. Every `|c| < 1/40` gives `|f c| < u/2`, so every product is `0.0`.
  A zero numerator over a nonzero total is the `Y = 0.0` of case U1.

### Thresholds as a distance

For a product of Gaussian MFs, rule `r` fires `exp(-(1/2) sum_i z_ri^2)`, with `z_ri = (x_i - m_ri) / sigma_ri`. On a
grid the largest firing is the product of the per-feature largest degrees, so `f_max = exp(-S)` with:

    S = (1/2) sum_i z_i^2

Here `z_i` is the distance, in widths, from input `i` to its nearest centre. For a consequent output of size `|c|`,
taking logarithms of the two rounding limits above gives three thresholds:

1. **Loss begins** (precision starts to degrade) once the largest product falls below `TINY`, that is for
   `S > 1022 ln 2 + ln|c|`. `1022 ln 2 = 708.3964`.
2. **The product is `0.0`** for `S >= 1075 ln 2 + ln|c|`. `1075 ln 2 = 745.1332`.
3. **The firing itself is `0.0`** for `S > 745.1332`, the point where `math.exp(-S)` returns `0.0` (found by bisection).
   This is the same number as in threshold 2, for the same reason: any result at or below `2**-1075` rounds to zero. Here
   every firing strength is zero, and the class raises the `ZeroDivisionError` it already has.

**The silent band** lies between thresholds 1 and 3: the output is finite, no warning is given, and the precision
degrades. NumPy's error state is `under='ignore'`, so underflow never warns. Section 3 prints the band at two consequent
sizes:

| `\|c\|` | Silent band (`S`) | `Y = 0.0` from | As a distance `\|\|z\|\| = sqrt(2 S)` |
| --- | --- | --- | --- |
| 0.1 | `(706.09, 745.13]` | `S >= 742.83` | `(37.58, 38.60]` widths |
| 2e-4 | `(699.88, 745.13]` | `S >= 736.62` | `(37.41, 38.60]` widths |

### Overflow

Firing strengths are products of degrees in `[0, 1]`, so `f_r <= 1` and `|sum_r f_r c_rd| <= sum_r |c_rd|`. The sum can
pass `DBL_MAX` only if some `|c_rd| > DBL_MAX / n`. Case O3 checks the edge with 27 rules at `f = 1`:

- `c = (DBL_MAX / 27)(1 + 1e-3)` gives `inf`;
- `c = (DBL_MAX / 27)(1 - 1e-3)` gives `6.651465e+306`.

The IT2 class has a third overflow site, its last line `0.5 * (y_low + y_high)`. Two finite bounds of `1e308` give
`inf` there, while `0.5*a + 0.5*b` gives `1e308`.

In the normal range the two forms are equal bit for bit:

1. Halving a normal double is exact.
2. Multiplying by a power of two commutes with rounding when nothing overflows or underflows.
3. So `fl(a/2 + b/2) = fl((a + b)/2) = fl(a + b)/2`.

This is why A and B can use `0.5*a + 0.5*b`, and why B keeps every shipped bit.

### Margins in decades

    margin = log10(max_r f_r |c_rd| / TINY)

The margin counts how many decades the largest product sits above the onset of loss, at one input point and one
output.

- **Seeds 0 to 3:** computed directly at every point and output. The smallest is 305.1 decades (endpoint placement) and
  304.1 (interior).
- **All 64 seeds:** the script prints a bound instead: `log10(min_x f_max(x) * min |c| / TINY)`. Both minima are taken
  over all 976 points (975 survey rows and the fixture). `min |c|` is also taken over the 27 rules, the 2 outputs and the
  64 seeds.

**Why the all-seed figure is a lower bound.** Let `r*` be the rule with the largest firing at `x`. For every point,
output and seed:

    max_r f_r |c_rd| >= f_r* |c_r*d| = f_max(x) |c_r*d| >= (min_x f_max(x)) (min |c|)

The two minima need not occur at the same point, rule or seed, so the true margin is at least the bound.

| Placement | `min_x f_max(x)` | `min \|c\|` | Bound |
| --- | --- | --- | --- |
| endpoint | `4.984402e-02` | `2.076015e-09` | 297.7 decades |
| interior | `4.977277e-03` | `2.076015e-09` | 296.7 decades |

**Reading section 4's `loss needs S > 707.37` line.** The script computes that figure from the largest consequent output,
`1022 ln 2 + ln(3.586805e-01)`. Its source comment calls it the latest onset. Consequent outputs depend on the input
(first-order TSK), and their range `[2.076015e-09, 3.586805e-01]` was measured at the 976 real points. For consequent
outputs within that range, the two inequalities above bracket the onset of loss:

- **Below `S = 688.40` no output loses precision.** That value is `708.3964 + ln(2.076015e-09)`.
- **Above `S = 707.37` every output's products are subnormal,** and precision degrades further with each decade.

So the printed figures (37.61 widths, and 15.4 and 11.5 times the worst point's distance) describe where loss is
certain, not the earliest it can start. The conservative figures below are derived here from printed values; the script
does not print them. They are extrapolations: they assume the consequent outputs at a far point stay within the range
seen at the real points.

- the onset distance is `sqrt(2 * 688.40) = 37.11` widths;
- that is `sqrt(688.40 / 2.999) = 15.2` times the worst point's distance under the endpoint placement;
- and `sqrt(688.40 / 5.303) = 11.4` times the worst point's distance under the interior placement.

Arithmetic check (the same relation rearranged, not an independent route): the endpoint placement's worst `S` plus the
margin bound in natural-log units, `2.999 + 297.7 * ln 10 = 688.5`, matches 688.40 to the rounding of the printed 297.7.

The claim that holds without that assumption is the margin at the real points: at least 296.7 decades. The `T1 alone`
line (1040.3 us endpoint, 1023.7 us interior, against a survey maximum of 157.9 us) uses the same largest-consequent
threshold and the same assumption.

### Error measure on ordinary inputs

For the T1 class, at output `d`:

    err = |Yhat_d - Y_d| / (eps * sum_r f_r |c_rd| / sum_r f_r)

`Yhat_d` is the computed output and `Y_d` the exact one. The figure reported is the largest over outputs. For IT2 the
scale is the BMM average of the two bounds' scales.

**Why this scale.** The rounding error of a floating-point sum is bounded by a small multiple of `eps` times the sum of
the absolute values of its terms, not times the absolute value of the result. Dividing by `sum_r f_r` gives the scale
above.

**Why not a relative error.** A relative error `|Yhat - Y| / |Y|` divides by `|Y|` instead. Random consequents (standard-normal
parameters times 0.1) have mixed signs, so `|Y|` can be far smaller than `sum f |c| / sum f`. The relative error then reports the
cancellation (the condition number `sum f |c| / |sum f c|`), not the arithmetic. The repro cases have positive
consequents, where the two measures coincide, so the repro uses the plain relative error.

**The same measure as FR-3.** `tests/test_anfis.py::test_effective_weights_match_shipped_defuzzifier` bounds
`|anfis - class|` by `8 eps * sum_r |w_r| |c_r|`, with `w` the normalised weights. For non-negative firing,
`sum_r |w_r| |c_r| = sum_r f_r |c_r| / sum_r f_r`. Section 7 computes that test's own quantity, two computed values
compared with each other, not with the exact reference. It prints no row for D, because D is the trainer's route the
test compares against.

### Results

All results come from the committed outputs: one laptop run, provisional.

**The cases.** O1 and O2 return `inf` against an exact `1e+308`; overflow warns, and `ProbabilityClip` maps `inf` to
`1.0`. U1 returns `0.0` against `0.015`. U2 returns `0.0075` against `0.015`, below every consequent. U3 returns
`0.011993006993006995` against `0.020493006993006994`, a relative error of 0.41 while inside the hull.

**Reach on IT2 grids.** No grid buildable on `main` reaches the band up to `w = 0.9`. The smallest margin there is 198.7
decades, on the survey rows at `w = 0.9`. At the stress setting `w = 0.99`:

- on the survey rows, 907 points have a zero lower firing sum (the loud `ZeroDivisionError`) and none is in the band;
- on the uniform draws, 960 points are zero and 3 are in the band. All 3 are wrong, by up to a relative 0.52, and the
  hull test flags only 1 of them.

Anchored consequent outputs are `1.683295e-04` to `3.810581e-04`.

**Bits moved against shipped on ordinary inputs.** "Outputs" counts points times outputs. The last column is the worst
error in eps of `sum f |c| / sum f`.

| Set | Outputs | A | B | C | D | Worst error, shipped -> A / D |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `first_ensemble_run`, endpoint, seeds 0 to 3 (T1) | 7808 | 5427 | 0 | 0 | 5047 | 1.77 -> 2.20 / 1.72 |
| zero consequents (T1) | 1952 | 0 | 0 | 0 | 0 | all exactly 0.0 |
| G59 anchored, survey rows (IT2) | 1950 | 1175 | 0 | 0 | 1252 | 2.30 -> 2.20 / 2.30 |
| tests' planted grid (T1) | 1024 | 784 | 0 | 0 | 700 | 3.16 -> 2.51 / 2.36 |
| tests' planted grid (IT2) | 1024 | 653 | 0 | 0 | 683 | 3.05 -> 1.91 / 2.59 |

B and C keep every shipped bit on all five sets.

**The FR-3 quantity** (section 7): T1 3.57 shipped and 3.41 under A; IT2 2.73 shipped and 3.36 under A. B and C are
unchanged. The test's own comment records 3.6 and 2.7, measured on 2026-10-15.

**The suite.** 1203 passed under shipped and under A, B, C and D. NC-021 records 1203 as the suite size. The controls:

- `X12` fails 2 tests, the `[t1]` and `[it2]` cases of `test_effective_weights_match_shipped_defuzzifier`;
- `X6` fails 9: those 2, both cases of `test_m2_planted_3x3x3_grid_recovers_each_consequent`, and 5 cases of
  `test_anchored_base_is_never_degenerate_on_the_archive`.

Patched calls per full run: 15,736 to `WeightedAverageDefuzzifier` and 2,288 to `NieTanDefuzzifier`.

**Time per call** (27 rules, 2 outputs):

| Variant | T1 | IT2 |
| --- | ---: | ---: |
| shipped | 3.72 us | 8.15 us |
| A | 6.87 us | 15.03 us |
| B | 6.85 us | 15.00 us |
| C | 6.63 us | 12.09 us |
| D | 2.43 us | 4.70 us |

As ratios to shipped, derived from these figures: A 1.85 and 1.84, D 0.65 and 0.58. B and C are Python prototypes, so
their extra cost is their checks' NumPy calls, not a property of their arithmetic.

## Design decisions

- **Written after the fact.** This record was written on 2026-11-20, after both evidence commits, at the operator's
  request. The documentation-first rule asks for the plan to be written before the work. Contrary to that rule, the plan
  was not written down before the scripts.
- **The options are left open.** The choice among A to E changes `fuzzy/defuzzification.py`. That module is Bengisu's,
  with Burak Öztekin as secondary reviewer (`docs/team.md`).
  - D would also make `defuzzification.py` use, or take over, a helper from `training/anfis.py`, which is Burak's, with
    Bengisu as secondary. So the call is theirs.
  - The evidence lays out what each option moves, and the draft issue lists them with trade-offs.
- **Nothing under `src/` changes.** No shipped or committed configuration reaches either failure: the margin is at least
  296.7 decades on the only shipped path. So nothing here is urgent, and the module's owner decides when it changes. A
  and D move bits in more than half of ordinary outputs. A change PR has to own that, together with any rounding-level
  fixture and the timing figures.
- **A plugin rather than an edit.** Patching the classes from a plugin keeps the measured tree at `58f7f63c`. One runner
  then covers every variant, and the shipped guards and messages stay in force. The call counts show that a run actually
  reached the patched methods. A run that never did could not pass for a clean one.
- **Two controls.** A pass under A or D means little unless the suite can see a change of that size. `X12` is a relative
  change of `1e-12`, which is `1e-12 / eps`, about 4500 eps, and only the FR-3 test sees it. `X6` is larger, and 9 tests see it.
  - A and D move outputs by a few eps at most. So the suite passing says only that its tolerances accept them.
  - The evidence that A and D are accurate is the exact-reference comparison above, not the suite.
- **An exact reference, not the hull test.** The hull test under-counts for `NieTanDefuzzifier` (case U3, and 2 of the 3
  band points at `w = 0.99`).
- **A branch cited by commit, with no PR.** The figures support an issue that is not yet opened. A pinned commit keeps
  every figure re-runnable without asking anyone to merge one-off scripts. The precedent is
  `docs/implementations/2026-11-07-pr135-review-evidence.md` on `bengisu/pr135-review-evidence`.
- **Only committed figures.** This record cites only figures in the committed outputs, plus the few derived above,
  each with its arithmetic shown. Timing from later runs is not cited, because it is not committed.

## Verification

Run these from the root of a checkout of `bengisu/defuzz-scaling-evidence`, with the pinned interpreter
`C:/pvci/Scripts/python.exe` (Python 3.12.10, NumPy 2.4.4). `bash` here means Git Bash: in PowerShell a plain `bash`
resolves to WSL's.

```bash
C:/pvci/Scripts/python.exe -I docs/evidence/defuzzification-scaling/defuzz_min_repro.py .
C:/pvci/Scripts/python.exe -I docs/evidence/defuzzification-scaling/defuzz_scaling_repro.py .
bash docs/evidence/defuzzification-scaling/defuzz_suite_by_variant.sh .
```

Expected results, as the README states them at `4b1b6c2d`:

- The first command prints `all as described` and exits 0.
- The second ends `112 passed, 0 failed` and exits 0.
- The third gives `1203 passed` for `shipped`, `A`, `B`, `C` and `D`. It gives `2 failed` for `X12` (both
  `test_effective_weights_match_shipped_defuzzifier` cases) and `9 failed` for `X6`.

Only these lines change between runs:

- the timing lines of section 8;
- the suites' wall times;
- the object addresses (`at 0x...`) in the `X12` and `X6` failure tracebacks.

Three practical notes:

- **The suite runner overwrites the committed outputs.** It writes `defuzz_suite_*.out.txt` next to itself. Run it in a
  throwaway worktree, compare with `git diff`, then discard the worktree. It takes about 4 minutes on the laptop.
- **Its first line names the checkout's own commit.** The runner prints the tree's `HEAD`, so from this branch it shows
  the branch tip, not the `58f7f63c` in the committed summary. The branch changes nothing under `src/` or `tests/`.
- **Compare ignoring line endings.** Output redirected on Windows has CRLF line endings, and the committed files are LF.
  Use `diff --strip-trailing-cr`.

Re-runs on 2026-11-20, on the same laptop:

- All three commands were re-run at `1ab3af89` from a fresh worktree. The outputs matched the committed ones apart from
  the timing lines, the wall times and the traceback addresses. That run is why `4b1b6c2d` changed the README sentence.
- The first two were re-run again at `4b1b6c2d` from a throwaway worktree. The minimal repro was identical. The full
  repro gave `112 passed, 0 failed`, identical apart from section 8's two timing lines.

`python scripts/check_ids.py` passes on this branch: the record allocates no ADR or NC id.

Not established:

- the open PR branches (#143, #152, #155), which were not run with the options;
- any run on Burak Öztekin's desktop;
- survey rows after 2026-09-08;
- whether A, B and D handle the failures in general: that rests on the five constructed cases, not on the graded sweep or
  the real band points;
- D's overflow safety a few ulps below `DBL_MAX`, which is argued, not tested.

`main` has moved since the measurement, to `eda10288`, with documentation-only changes. The evidence was not re-run there.

## Related docs

- `docs/evidence/defuzzification-scaling/README.md`
- PR #143 (#61 Part A): `scripts/type_reduction_discrepancy.py` at `ae8d2bf9`, findings sections 15.2 and 17.4; review
  5923434762; comment 7029369115
- `docs/team.md`: `fuzzy/defuzzification.py` (Bengisu, secondary Burak Öztekin) and `training/anfis.py` (Burak Öztekin,
  secondary Bengisu)
- `docs/numerical-claims.md`: NC-004 (per-member cost), NC-021 (suite size), NC-035 (`sx` length), NC-042 (`s_i`)
- `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv`, the survey rows
- `docs/implementations/2026-10-15-pr114-review-fixes.md`, which records the FR-3 test's 3.6 and 2.7
- `docs/implementations/2026-11-07-pr135-review-evidence.md` on `bengisu/pr135-review-evidence`, the precedent for an
  evidence folder cited by commit
