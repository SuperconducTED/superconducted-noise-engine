# Nie-Tan, BMM and the Karnik-Mendel type-reduced set: the Part A findings

**Date**: 2026-11-07 · **Issue**: #61 Part A (FR-1 to FR-4) · **Owner**: @bengisucvd · **Measured
at**: commit `10e8174`, on `main` @ `43a2c9b0`, survey `calibration-data` @ `3d1569d` · **Status**:
laptop, provisional; canonical run owed on Burak's desktop; no register row until merge · **Evidence**:
`docs/evidence/adr-011-type-reduction/`

ADR-011 is Open and `docs/decisions.md` names what it waits on: how far the closed-form IT2 reducer
sits from Karnik-Mendel (KM), and what type reduction costs. This record answers both, prepares the
closure text the ledger needs after ADR-009, and says what was not established.

## 1. The answer

**Textbook Nie-Tan is the closer reducer, by the rule fixed before the result.** File 02 §2.4's rule,
the lower median of `Db` per output pooled over all grids and both conventions, selects Nie-Tan on
every point set:

| Point set | Output | Scores | BMM(1/2, 1/2) | Nie-Tan |
| --- | --- | ---: | ---: | ---: |
| survey (real device states) | gamma | 7,800 | 0.0940 | **0.0340** |
| survey | lambda | 7,800 | 0.0498 | **0.0322** |
| lattice | gamma | 216 | 0.0388 | **0.0292** |
| lattice | lambda | 216 | 0.0346 | **0.0295** |
| uniform | gamma | 16,000 | 0.1202 | **0.0396** |
| uniform | lambda | 16,000 | 0.0820 | **0.0368** |
| all, File 02's own pool | gamma | 24,016 | 0.1107 | **0.0378** |
| all | lambda | 24,016 | 0.0720 | **0.0349** |

The "all" rows are the deciding figures and reproduce File 02's four to four decimals. Survey rows lead
this table because they are the real device states. That is a presentation choice, made after the
result was seen (#61 comment 6665986289, decision 2); it does not change what decides.

**One cell reverses, robustly.** `G59` anchored lambda on the survey rows: BMM 0.0337, Nie-Tan 0.0483.
See section 5. So "lower in all cells" is not said anywhere here without qualification.

**Compute cost is not the reason.** Nie-Tan is about 3 times cheaper per point than guarded iterative KM
(section 6). ADR-011's Context sentence rests on cost; the measured gap is small and the reason to
prefer Nie-Tan is the rule above plus linearity in the consequents (P8).

**The two formulas are not the two names.** `NieTanDefuzzifier` computes BMM(1/2, 1/2), not textbook
Nie-Tan (File 02 §2.4, re-pinned here against Wu and Mendel 2019's worked example). Everything below names
reducers by their literature names. The class switch is a separate PR by its owner.

## 2. Notation

- `x = (mean_T1 [us], mean_T2 [us], mean_readout_error [1])`, **archive units**: the survey's and
  `ArchiveUnitFeatureExtractor`'s, not `BasicCalibrationVectorizer`'s, which emits SI seconds since #66.
- `X = prod_i [p1_i, p99_i]` (NC-041).
- Each feature has `k = 3` interval Gaussian MFs. `R = 27` rules in `itertools.product` order. Firing
  bounds `f_lo_r(x)`, `f_hi_r(x)` under the product t-norm. `B(x) = prod_r [f_lo_r, f_hi_r]`.
- `c_r`: the zero-order consequent of rule `r` for one output. `Y(w) = sum_r w_r c_r / sum_r w_r`.
- `y_l = min_{w in B} Y(w)`, `y_r = max_{w in B} Y(w)`, `m = (y_l + y_r) / 2`.
- `Y_lo = Y(f_lo)`, `Y_hi = Y(f_hi)`, `S_lo = sum f_lo`, `S_hi = sum f_hi`.
- `y_BMM = (Y_lo + Y_hi) / 2`, BMM with `alpha = beta = 1/2`: what `NieTanDefuzzifier` computes.
- `y_NT = Y(f_lo + f_hi)`, textbook Nie-Tan.
- `D = |y - m|`. `Dc = D / (max c - min c)`, FR-3's form. `Db = D / (y_r - y_l)`, File 02's score.

## 3. Assumptions

A1 product t-norm. A2 zero-order consequents in both conventions, so `c` does not depend on `x`. A3
`sum f_lo > 0` at every point: counted, and zero skipped in all 96 rows. A4 each output reduced on its
own, so `(y_l(gamma), y_l(lambda))` is generally not attained by one weight vector. A5 `f_lo <= f_hi`,
enforced by `IntervalGaussianMF`. A6 float64: the route gap (section 7) has to sit far below the
distances reported, and it does. A7 units as in section 2; anchored targets from
`feature_target_fn(..., t_seconds=24e-9, coherence_unit="us")` (NC-035).

A8: two footprint geometries, labelled separately. In `G59` the lower MF is the T1 Gaussian and the
footprint only grows outward, `s_hi = sqrt(s_lo^2 + s_i^2)`, with `s_i` NC-042's medians (confirmed in
#61 comment 6665986289). In `w` grids it is symmetric, `IntervalGaussianMF(c, s (1 - w), s (1 + w))`.

**A9, the one that limits every figure: these consequents are not trained.** `unit-spread` and `anchored`
are FR-4's conventions, chosen because no trained model exists. A trained `F` can sit elsewhere (#60).

## 4. Derivation

**P1, monotone in each weight.** `dY/dw_r = (c_r - Y(w)) / sum_s w_s`, so `Y` increases in `w_r` exactly
when `c_r > Y(w)`.

**P2, switch points make the exhaustive route exact.** Let `y* = y_l`, attained because `B` is compact and
`sum w >= sum f_lo > 0`. Put `g(w) = sum_r w_r (c_r - y*)`. Since `sum w > 0`, `Y(w) >= y*` exactly when
`g(w) >= 0`, so `min_B g = 0`. `g` is linear, so it is minimised by `w_r = f_hi_r` where `c_r < y*` and
`f_lo_r` where `c_r > y*`. Sort `c` ascending and take any `k` between `#{c_r < y*}` and `#{c_r <= y*}`:
the switch vertex `w^(l,k)` (`f_hi` on the first `k`, `f_lo` on the rest) minimises `g`, so `Y(w^(l,k)) = y*`.
Every switch vertex lies in `B`, hence `y_l = min_{k = 0..R} Y(w^(l,k))`. The mirror gives `y_r`. That is 28
evaluations per endpoint, and it proves FR-2's claim that the extremum over `2^R` vertices equals KM's.

**P3, iterative KM with a cycle-safe stop.** Start at `y_0 = Y((f_lo + f_hi) / 2)`, take
`k_t = #{c_r <= y_t}`, set `y_{t+1} = Y(w^(l, k_t))`.

*Lemma.* `y_{t+1} <= y_t`, with equality exactly when `y_t = y_l`. `y_t = Y(v)` for some `v` in `B`, so
`g_t(v) = 0` with `g_t(w) = sum w_r (c_r - y_t)`. By P2's sign rule `w^(l, k_t)` minimises `g_t` over `B`, so
`g_t(w^(l, k_t)) <= 0`. If equality holds then `min_B g_t = 0`, so `Y >= y_t` on `B`, and `y_t` is attained, so
`y_t = y_l`. Conversely `y_t > y_l` gives a negative minimum and a strict decrease.

In exact arithmetic this stops within `R + 1` evaluations on `k_{t+1} = k_t` (EKM's rule, Wu and Mendel 2009).
In float64 both `y' == y` (Karnik and Mendel 2001; ticket section 6.3) and `k' == k` can cycle, because a computed
average can land within rounding of a consequent. Ties make that likely but are not necessary: a two-rule box with
distinct consequents cycles, pinned as `CYCLE_*` in `tests/test_type_reduction.py`. So the iteration also stops when
the computed `y_{t+1} >= y_t` and returns the smaller value. Accepted steps then strictly decrease a sequence of floats, so
no vertex repeats. The exhaustive route bounds what the guard can cost (section 7).

**P4, the sandwich.** `f_lo`, `f_hi` and their midpoint lie in `B`, so `Y_lo`, `Y_hi` and `y_NT` lie in
`[y_l, y_r]`, and `y_BMM` is a convex combination of two values there. Hence `Db` lies in `[0, 1/2]`. No opened source
states this in general; it is derived here, and Wu and Mendel's worked example is consistent with it.

**P5, degenerate footprint.** `f_lo = f_hi` makes `B` a point and all four values equal.

**P6, affine equivariance.** For `c -> a c + b`, `a > 0`, all of `y_l, y_r, m, y_NT, y_BMM` transform alike, so `Dc`
and `Db` do not change. That is why `unit-spread` is scale-free.

**P7, division guards.** `y_r = y_l` gives `D = 0` by P4; `Db` is 0 and the point is counted. `max c = min c`
gives every reducer that value; `Dc` is 0 and counted.

**P8, linearity in the consequents.** `y_NT` and `y_BMM` are linear in `c` for fixed firing. `m` is not: `y_l` is a
minimum of linear functions and `y_r` a maximum. So the KM midpoint cannot be #60's single least-squares forward map.

**P9, what separates the two reducers.** Directly from the definitions,

    y_NT = (S_lo Y_lo + S_hi Y_hi) / (S_lo + S_hi),
    y_NT - y_BMM = (S_hi - S_lo)(Y_hi - Y_lo) / (2 (S_lo + S_hi)).

So BMM weights the two means equally, and Nie-Tan weights them by their firing mass. With `rho = S_hi / S_lo`, Nie-Tan puts
`rho / (1 + rho)` on `Y_hi`, which goes to 1 as the footprint widens. Checked on every survey row of every cell: largest
absolute error 3.89e-16.

## 5. The survey rows, and the reversal

Per cell, 975 survey rows (521 distinct feature vectors). "Closer" is the share of rows where BMM's `Db` is lower. The
interval is a 90% circular block bootstrap of the median difference over consecutive rows, blocks of 30, because rows are a time
series; for the first and last lambda cells below, blocks of 8 and 90 rows lead to the same reading. Output: `survey_reversal_check.out.txt`.

| Grid | Convention | Output | BMM | Nie-Tan | BMM closer | Distinct rows: BMM closer | 90% interval, BMM minus Nie-Tan |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `w=0.1` | unit-spread | unit | 0.0332 | 0.0192 | 0.242 | 0.217 | 0.0083 to 0.0188 |
| `w=0.1` | anchored | gamma | 0.0332 | 0.0275 | 0.247 | 0.236 | 0.0003 to 0.0198 |
| `w=0.1` | anchored | lambda | **0.0102** | 0.0117 | 0.469 | 0.464 | **-0.0044 to 0.0014** |
| `w=0.3` | unit-spread | unit | 0.1036 | 0.0428 | 0.097 | 0.109 | 0.0413 to 0.0711 |
| `w=0.3` | anchored | gamma | 0.1254 | 0.0425 | 0.187 | 0.177 | 0.0427 to 0.1103 |
| `w=0.3` | anchored | lambda | 0.0369 | 0.0355 | 0.389 | 0.386 | -0.0057 to 0.0136 |
| `w=0.6` | unit-spread | unit | 0.1995 | 0.0275 | 0.014 | 0.019 | 0.1553 to 0.1815 |
| `w=0.6` | anchored | gamma | 0.2606 | 0.0524 | 0.012 | 0.010 | 0.1972 to 0.2101 |
| `w=0.6` | anchored | lambda | 0.0861 | 0.0252 | 0.229 | 0.230 | 0.0473 to 0.0677 |
| `G59` | unit-spread | unit | 0.0825 | 0.0465 | 0.301 | 0.271 | 0.0159 to 0.0588 |
| `G59` | anchored | gamma | 0.0778 | 0.0316 | 0.291 | 0.238 | 0.0157 to 0.0806 |
| `G59` | anchored | lambda | **0.0337** | 0.0483 | **0.763** | **0.754** | **-0.0194 to -0.0093** |

Read cell by cell:

- **`G59` anchored lambda is a real reversal.** The interval excludes zero, BMM is closer on 744 of 975 rows and 393 of 521
  distinct rows, and it holds in both halves of the series (0.0349 against 0.0477; 0.0336 against 0.0501). A second implementation
  that shares no code with the script's KM or reducers gives the same numbers (`second_route_reducers.py`; its switch-point route is
  certified against vertex enumeration on 300 small boxes, largest gap 4.44e-16).
- **`w=0.1` anchored lambda is not separable from noise.** Its median is lower for BMM, but the interval includes zero and BMM is closer
  on only 47% of rows. It is not reported as a reversal, and the earlier "2 of 12 cells" (#61 comment 6665986289) is narrowed here.
- **`w=0.3` anchored lambda** cannot be told apart either, in Nie-Tan's favour. No claim is made for that cell.
- **Size.** At `G59` anchored lambda, `|y_BMM - y_NT|` is at most 1.508e-05 and has a median of 1.480e-06, against a median band width of
  6.104e-05. This cell's output is the anchored one, not the mean of per-qubit targets: `y_NT` has a median of 3.19e-04 and moves only 1.9% across the 975 rows. So the gap is at most 4.7% of the output and 0.46% at the median. File 02's and #61 comment 6665986289's "not a visible numerical change" holds at the median; the largest gap exceeds the output's own variation. The flat output is itself worth noting: with `G59`'s wide upper MFs, this anchored rule base barely responds to its inputs on the survey rows.

**Why that cell: described, not explained.** There, in band position (0 is `y_l`, 1 is `y_r`, 0.5 the midpoint), `Y_lo` sits at 0.518 and `Y_hi` at
0.441, the largest `Y_hi` offset of the 12 cells, with `rho` about 7.4. By P9 Nie-Tan leans on `Y_hi` and lands at 0.452; BMM lands at 0.478. A hypothesis
was tested and **rejected**: that BMM wins a cell when `Y_lo` and `Y_hi` straddle the midpoint. Across the 12 cells that share correlates with BMM being closer at only
0.27, and it straddles on 99.5% of rows at `w=0.1` unit-spread, where BMM is closer on 24%. No general mechanism is established
(`reducer_positions_and_cost.out.txt`).

## 6. Cost

Wall time per point on 27 rules, G59 anchored lambda, 975 survey points, median of 7 passes, python and numpy. Three runs of the script on this laptop, under different load,
gave the ratio below; the absolute times moved by a third, so only the ratio is quoted.

| Reducer | Relative cost | Note |
| --- | ---: | --- |
| `nie_tan_reduce` | 1 | closed form |
| `bmm_half_reduce` | about 1 | closed form |
| `karnik_mendel_detailed` | about 3 | both endpoints, guarded; passes per endpoint: mean 2.65 and 2.34, largest 4 and 3 |
| `exhaustive_type_reduce` | about 8 to 12 | 28 evaluations per endpoint |

Across the sweep, KM's largest pass count per endpoint is 6. On a hot path inside an ensemble a factor of 3 can still matter, but it is a modest gap, and an implementation in another language would move it.

## 7. KM certification, and the stop rule

- Iterative against exhaustive at every point of the sweep: largest gap 8.743e-15, in a `unit-spread` cell (tolerance about 3.8e-13).
- Vertex enumeration (FR-2), analytic invariants, agreement with the shipped defuzzifiers at 1e-12, Wu and Mendel 2019's worked example, mutation checks: `tests/test_type_reduction.py`, 46 tests.
- All 96 rows: zero skipped, zero degenerate, zero bracket violations.
- **The cycle is reported as a mechanism, not a count.** File 02's 116 points where `y' == y` never terminates does not reproduce as a number: 100, 132, 102 or 126 at `w=0.6`
  anchored gamma, depending only on the switch-point tie rule and the summation order (`km_cycle_sensitivity.py`). What does reproduce: cycles at the right endpoint only, none at the lattice points, and the guarded result equals the
  exhaustive route on every cycling point. A count of rounding-level events belongs to the implementation, not the problem.

## 8. Per-grid discrepancy over sampled points

Nie-Tan, from `2026-11-07-10e8174.tsv`; a `max` is over the sampled points, not a supremum over the box.

| Grid | Convention, output | `Db` median, survey | `Db` max, survey (975) | `Db` max, pooled (3,002) |
| --- | --- | ---: | ---: | ---: |
| `G59` | unit-spread | 0.0465 | 0.1333 | 0.1558 |
| `G59` | anchored gamma | 0.0316 | 0.1494 | 0.1824 |
| `G59` | anchored lambda | 0.0483 | 0.1540 | 0.1836 |
| `w=0.1` | unit-spread | 0.0192 | 0.1709 | 0.1709 |
| `w=0.3` | unit-spread | 0.0428 | 0.4217 | 0.4217 |
| `w=0.6` | unit-spread | 0.0275 | 0.4706 | 0.4706 |

`Db` cannot exceed 1/2 (P4). So at wide symmetric footprints a closed-form reducer can sit close to the edge of the band at some points, though its median stays near the middle. For `w=0.6` that is a warning about the footprint, not a verdict on the reducer.

## 9. Closure text, for the ledger after ADR-009

Not landed here. Under #61 architect decision B2, @mertefesensoy lands it in the same PR as ADR-009's flip. NC ids and the batch record are filled at that time. It cites no advisor answer; Dr. Akba's read arrives through the lead.

> **ADR-011, closed [date].** T1: weighted average. IT2: textbook Nie-Tan, `y = Y(f_lo + f_hi)`. At this closure's commit, the class `NieTanDefuzzifier` computes BMM(1/2, 1/2); [the switch PR] moves it to the textbook formula.
>
> Measured against the Karnik-Mendel midpoint on 3x3x3 `IntervalGaussianMF` grids at footprints `G59` and `w` in {0.1, 0.3, 0.6}, over the survey feature range in microseconds, with zero-order consequents (`unit-spread`, and `anchored` as the units-bearing companion), commit `10e8174`, NC-nnn. By File 02's pre-registered rule, the lower median of `Db = |y - m| / (y_r - y_l)` pooled over all grids and both conventions, Nie-Tan is selected on every point set: on the 975 survey rows 0.0340 against BMM's 0.0940 for gamma and 0.0322 against 0.0498 for lambda. At `G59`, `unit-spread`, Nie-Tan's `Db` has a median of 0.0465 and is at most 0.1558 over the 3,002 sampled points. These are sample maxima, not bounds.
>
> The result is not uniform. At `G59` anchored lambda on the survey rows BMM is closer, 0.0337 against 0.0483, on 744 of 975 rows, with a 90% block interval of the difference excluding zero; the two reducers differ there by at most 1.5e-05 and by 1.5e-06 at the median, on an output near 3.2e-04, against a median band width of 6.1e-05. No general mechanism was established. The consequents are not trained, and this comparison is re-measured on the first IT2 archive fit (#60).
>
> Karnik-Mendel stays the band source (File 02, File 03) and out of the training loss, because its midpoint is not linear in the consequents. Nie-Tan is about 3 times cheaper per point than guarded iterative KM on 27 rules, so compute cost is not the reason for this choice. Figures are laptop and provisional until [the batch record].

## 10. Register rows, drafted

Next free ids at merge time, one row per conclusion (architect decision B8). Each cites `10e8174`, survey `3d1569d` and the script.

1. **File 02's rule on each point set** (section 1 table). `file02_rule_by_point_set.py`.
2. **The `G59` anchored lambda reversal, and `w=0.1` not separable** (section 5). `survey_reversal_check.py`, `second_route_reducers.py`.
3. **Nie-Tan's discrepancy from the KM midpoint per grid, over sampled points** (section 8). `2026-11-07-10e8174.tsv`, SHA-256 `c61102e80ee82bb83b163748b47cabe03a2770624fac0db3cbf5861c25210b11`.
4. **Cost ratio against iterative KM, about 3** (section 6). `reducer_positions_and_cost.py`.

The cycle count is not registered (section 7). They follow agreement on the footprint set: decision 2 of #61 comment 6319118939 is still waiting on @BahaJarad, whom this PR asks for review.

## 11. Corrections to what came before

Dated documents are not edited; these are listed.

1. **File 02 §2.4's two KM implementations** were never committed and the session's folder is gone (#61 comment 6665986289). This record's scripts are now the command behind File 02's figures. Its four pooled medians reproduce to four decimals.
2. **File 02 §2.4's 116** is one arithmetic's count (section 7).
3. **#61 comment 6319118939, "Nie-Tan lower in all 12 cells"** holds for the pooled figures only.
4. **#61 comment 6665986289, "BMM lower in 2 of 12"** holds for point medians; one of the two is not separable from noise (section 5). Its "not a visible numerical change", like File 02's, holds at the median and not at the largest gap (section 5).
5. **ADR-011's Context**, "beats Karnik-Mendel iterative reduction in compute cost": measured at about a factor of 3.
6. **The ticket's §11 closure sentence**, "at most X", is a sample maximum and says so above.

## 12. Not established

- Anything about a trained model (A9). The reversal could move, in either direction, once consequents are fitted.
- Which reducer is closer on rows after `3d1569d`. The survey stops at 2026-09-08.
- A supremum over the box. Every `max` is over sampled points.
- Why `G59` anchored lambda reverses, beyond the description in section 5.
- Whether the KM midpoint is the right reference. #61 and File 02 set it. Part A does not examine it.
- Independence: the survey rows are snapshots, and only 521 of 975 feature vectors are distinct.
- Canonical status. These are laptop figures; the desktop batch is owed.

## 13. Verification

Everything in the evidence folder, from the repository root, with `PYTHONPATH=src`:

- `python -m scripts.type_reduction_discrepancy --range-source survey:docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv --footprint 0.1 --footprint 0.3 --footprint 0.6 --footprint g59 --points 2000 --seed 84 --out <path>`: byte-identical across two runs; data rows identical to `2026-10-21-d0f144a.tsv` apart from the grid's name.
- `python docs/evidence/adr-011-type-reduction/file02_rule_by_point_set.py`: the section 1 table.
- `python docs/evidence/adr-011-type-reduction/survey_reversal_check.py`: the section 5 table.
- `python docs/evidence/adr-011-type-reduction/second_route_reducers.py`: a second route for the reversal.
- `python docs/evidence/adr-011-type-reduction/reducer_positions_and_cost.py`: P9's check, the rejected hypothesis, cost. The mutation (`y_l` as the reference) moves `Db` to about 1/2.
- `python docs/evidence/adr-011-type-reduction/km_cycle_sensitivity.py`: the cycle mechanism and its range.
- `pytest tests/test_type_reduction.py`: 46 tests.

## 14. Related

#61 (comments 6319118939, 6665986289); #84 comment 5885404218 (File 02), comment 5970300012 (File 03); #60, PR #114, PR #137; #62; #109 item 4; ADR-009, ADR-011, ADR-014 in `docs/decisions.md`; NC-035, NC-041, NC-042. Sources opened on 2026-10-21: Karnik and Mendel 2001, Wu and Mendel 2009, Mendel and Liu 2007, Wu and Mendel 2019 (arXiv:1907.01697).

## 15. 2026-11-11: corrections after the PR #143 reviews

Appended after @mertefesensoy's review 5828001160 and @BurakOztekin's 5831798256, both at `c8a1dd54`. Sections 1 to 14 are not
edited; where they disagree with this section, this section is current. Measured at `35da0446`; the cost and cycle outputs at
`f6e9719b`, after their own scripts changed (the module they import is the same). Commits: the plan `d34bb16c`, the tests `fc98ed4a`,
the fix `5a5c8e3b`, the evidence scripts `35da0446` and `f6e9719b`, the outputs `8b6914c7`. Record:
`docs/implementations/2026-11-11-issue-61-pr143-review-fixes.md`. Laptop, provisional.

**What did not change.** Every figure in sections 1, 5 and 8 reproduces at the four decimals printed, from
`2026-11-11-35da0446.tsv` and the regenerated outputs. `compare_sweep.py` against `2026-11-07-10e8174.tsv` exits 0, largest
relative difference 2.809e-11. Nie-Tan is selected on every point set by File 02's rule, and `G59` anchored lambda still reverses.
Two smaller figures moved in their last digits with the arithmetic of 15.2: P9's check, largest absolute error 5.00e-16 (it was
3.89e-16), and section 7's largest route gap on the committed grids, 8.771e-15 (it was 8.743e-15). Section 6's pass counts (means
2.65 and 2.34, largest 4 and 3; largest over the sweep 6) did not move.

**15.1 The band now comes from the exhaustive route (review item 1).** P3's lemma needs `y_t = Y(v)` exactly for some `v` in
`B`. In float64 that can fail at the first step: with `f_lo = (1e-17, 1e-20)`, `f_hi = (1e-17, 1)`, `c = (0, 1)`, `y_0 = 0.5 / (0.5 + 1e-17)`
rounds to exactly 1.0, a consequent; `k_0 = 2` counts that rule, the switch vertex is `f_hi`, and `Y(f_hi)` rounds to 1.0 again. The
iteration stops there, against `y_l = 9.99e-4`. So P3's last sentence, "The exhaustive route bounds what the guard can cost", is
withdrawn: the guard does not make the iteration correct in floats. The sweep's `y_l` and `y_r`, and the evidence scripts' bands, now
come from P2's switch-vertex enumeration, which has no stop rule. The iterative route still runs and is reported as a diagnostic, now
also in units of each point's tolerance (`km_route_gap_over_tolerance_max`). Section 7's first bullet stays true of the committed grids;
at wider footprints it is not:

| Footprint | `unit-spread` iterative route gap | Over tolerance |
| --- | ---: | ---: |
| `w = 0.8` | 0.0038 | about 1e10 |
| `w = 0.9` | 0.0769 | about 2e11 |
| the committed grids (`0.1`, `0.3`, `0.6`, `G59`) | at most 8.771e-15 | at most 0.023 |

The exhaustive route, now that it decides, has its own second route: exact rational enumeration of all `2^R` vertices on 202 boxes whose
firing spans `1e-20` to `1`, the counterexample and the underflow case among them (`tests/test_type_reduction.py`).

**15.2 The weighted average no longer underflows (review item 2).** With every lower weight near the subnormal floor, `sum f_lo c` rounded
to zero before the division, so `Y(f_lo) = 0.0` sat below every consequent. `Y` is now computed on `w / max w`, equal in exact arithmetic.
At `w = 0.99` this was the source of BMM's bracket violations:

| `w = 0.99`, pooled | `c8a1dd54` | `35da0446` |
| --- | ---: | ---: |
| BMM, anchored gamma | 2 | 0 |
| BMM, anchored lambda | 3 | 0 |
| every row of the `w = 0.99` file, all point sets | 10 | 0 |

`NieTanDefuzzifier` in `src/` has the same arithmetic. It is not changed here; the class switch (#61 comment 6727626228) is where it changes.

**15.3 What the cost ratio measures (review item 3).** Section 6 timed the public functions, and input validation is most of a closed-form
reducer's time. "Three runs" and "8 to 12" in section 6 trace to no committed output and are withdrawn. From `reducer_positions_and_cost.out.txt`
at `f6e9719b`:

| Route | Per point | Ratio |
| --- | ---: | ---: |
| `nie_tan_reduce`, public | 24.3 us | 1 |
| `bmm_half_reduce`, public | 45.2 us | 1.9 |
| `karnik_mendel_detailed`, public | 120.0 us | 4.9 |
| `exhaustive_type_reduce`, public | 624.5 us | 25.7 |
| `_validated` alone | 16.9 us | 0.7 of `nie_tan_reduce` |
| Nie-Tan, arithmetic | 4.5 us | 1 |
| BMM(1/2, 1/2), arithmetic | 10.4 us | 2.3 |
| iterative KM, arithmetic, consequents sorted once | 62.7 us | 13.9 |
| iterative KM, arithmetic, sorting each point | 89.5 us | 19.9 |
| exhaustive, arithmetic, sorted once | 639.1 us | 142 |

G59 anchored lambda, 975 survey points, the fastest of 15 interleaved passes. The arithmetic includes the rescale
of 15.2 (a maximum and a division per average), which is why the exhaustive route, with 56 averages per point,
is the slowest by far. With zero-order consequents (A2) the sort can be done once per rule base.

So iterative KM costs about 5 times Nie-Tan through the public functions and about 14 times on the arithmetic
alone (about 20 when each point sorts its consequents). The gap is not the small one section 1 described, and it
points the same way as the rule. The choice still rests on File 02's pre-registered rule and on P8, not on cost. "About 3 times cheaper" in sections 1, 6 and 9, and correction 5
of section 11, are replaced by this paragraph.

**15.4 What each pool holds (review item 4).** File 02's rule pools, per output, every grid and both conventions, with `unit-spread`'s single
output entering both the gamma and the lambda pool. That is why each "all" pool has 24,016 scores. Section 1 did not say so. The same medians
on the anchored rows alone, a description beside the rule, not a second rule:

| Point set | Output | Scores | BMM(1/2, 1/2) | Nie-Tan |
| --- | --- | ---: | ---: | ---: |
| survey | gamma | 3,900 | 0.1036 | **0.0359** |
| survey | lambda | 3,900 | 0.0359 | **0.0325** |
| lattice | gamma | 108 | 0.0670 | **0.0265** |
| lattice | lambda | 108 | 0.0362 | **0.0268** |
| uniform | gamma | 8,000 | 0.1537 | **0.0460** |
| uniform | lambda | 8,000 | 0.0768 | **0.0415** |
| all | gamma | 12,008 | 0.1370 | **0.0422** |
| all | lambda | 12,008 | 0.0614 | **0.0371** |

Nie-Tan has the lower median in every anchored pool as well. On the survey rows the lambda medians are close,
0.0359 against 0.0325, far closer than the pooled 0.0498 against 0.0322: most of the pooled lambda gap comes from
`unit-spread`'s rows entering the lambda pool. `file02_rule_by_point_set.out.txt` prints both tables.

**15.5 Tests (review item 5).** On `c8a1dd54` all eight mutants the reviews named survived all 46 tests (`mutate.py`, output in this PR's
record). The tests now kill all eleven, two of them added for the fix itself (`mutate.out.txt`). `Db_max <= 0.5`, which was the clip itself, is now
`Db_max < 0.5`; `passes <= 28`, which could not fail before the `RuntimeError`, is gone; the route-gap bound is per point.

**15.6 The `km_*` columns are diagnostics.** They are printed, never compared between machines and never cited. Two measurements say why. On
@BurakOztekin's desktop `km_guard_stops` was 17 where the committed file has 15 (`w = 0.3`, `unit-spread`). And the two-rule box that cycled
under the old summation (pinned in the tests since 2026-10-21) stopped cycling once `Y` divided by `max w` first; a new one was found by the same kind of seeded
search. Which boxes cycle belongs to the arithmetic, as section 7 says of the count, and so does the count: at `w = 0.6` anchored
gamma the four variants of section 7 now give 104, 149, 102 and 126 (they gave 100, 132, 102 and 126), still at the right endpoint
only, none at the lattice points, and with the guarded result equal to the exhaustive route on every cycling point.

**15.7 Smaller text corrections (review 5828001160, item 6).**

1. Section 5's interval is of the difference of medians, not the median difference, as `block_interval` computes it.
2. Section 7: the cycle count moves with the switch-point tie rule and the summation order among the variants tried, not "only" with them; and
   "right endpoint only, none at the lattice points" was measured in one cell, `w = 0.6` anchored gamma.

**15.8 Closure text, restated.** This block replaces section 9's. The rest of section 9 (who lands it and when) stands.

> **ADR-011, closed [date].** T1: weighted average. IT2: textbook Nie-Tan, `y = Y(f_lo + f_hi)`. At this closure's commit, the class `NieTanDefuzzifier` computes BMM(1/2, 1/2); [the switch PR] moves it to the textbook formula.
>
> Measured against the Karnik-Mendel midpoint, its endpoints by exhaustive switch-vertex enumeration, on 3x3x3 `IntervalGaussianMF` grids at footprints `G59` and `w` in {0.1, 0.3, 0.6}, over the survey feature range in microseconds, with zero-order consequents (`unit-spread`, and `anchored` as the units-bearing companion), commit `35da0446`, NC-nnn. By File 02's pre-registered rule, the lower median of `Db = |y - m| / (y_r - y_l)` per output, pooled over all grids and both conventions with `unit-spread`'s single output in both pools, Nie-Tan is selected on every point set: on the 975 survey rows 0.0340 against BMM's 0.0940 for gamma and 0.0322 against 0.0498 for lambda. On the anchored rows alone the survey medians are 0.0359 against BMM's 0.1036 for gamma and 0.0325 against 0.0359 for lambda. At `G59`, `unit-spread`, Nie-Tan's `Db` has a median of 0.0465 and is at most 0.1558 over the 3,002 sampled points. These are sample maxima, not bounds.
>
> The result is not uniform. At `G59` anchored lambda on the survey rows BMM is closer, 0.0337 against 0.0483, on 744 of 975 rows, with a 90% block interval of the difference of medians excluding zero; the two reducers differ there by at most 1.5e-05 and by 1.5e-06 at the median, on an output near 3.2e-04, against a median band width of 6.1e-05. No general mechanism was established. The consequents are not trained, and this comparison is re-measured on the first IT2 archive fit (#60).
>
> Karnik-Mendel stays the band source (File 02, File 03) and out of the training loss, because its midpoint is not linear in the consequents. Per point on 27 rules, iterative Karnik-Mendel costs about 5 times Nie-Tan through the public functions and about 14 times on the arithmetic alone; the choice rests on the rule above, and cost points the same way. Figures are laptop and provisional until [the batch record].

**15.9 Register rows, restated.** Rows 1 and 2 of section 10 stand, citing `35da0446`. Row 3 cites `2026-11-11-35da0446.tsv`, SHA-256
`af97c29f24c2b660cebed91bd1d5638a96f970b71d63de529d249a7eead79d0c`. Row 4 becomes: **the cost of iterative KM against Nie-Tan, per point on 27 rules, through the public functions and on the
arithmetic alone** (section 15.3), `reducer_positions_and_cost.py`. Nothing else in section 10 changes.
