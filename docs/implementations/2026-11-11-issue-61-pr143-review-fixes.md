# 2026-11-11: issue-61-pr143-review-fixes

PR #143 (#61 Part A) after its two reviews: @mertefesensoy's COMMENT review 5828001160 and
@BurakOztekin's CHANGES_REQUESTED 5831798256, both at `c8a1dd54`. This record is written as the plan
first, with the predictions fixed before any figure is regenerated; the Verification section is
filled after the build. Laptop, provisional; the canonical run is Burak's desktop batch.

## Problem / Motivation

The reviews found five things, none of which moves a committed figure, and two of which make claims
in the code and the findings untrue in general:

1. **Iterative KM can stop at a wrong float fixed point.** With `lower = [1e-17, 1e-20]`,
   `upper = [1e-17, 1]`, `values = [0, 1]`, `karnik_mendel_detailed` returns `y_l = 1.0` against the
   exhaustive route's 9.99e-4. The sweep takes its distances from the iterative route, so at
   `--footprint 0.8` and `0.9` it reports wrong endpoints without a warning (`unit-spread` route gap
   0.0038 and 0.0769). `compare_sweep.py` never looks at the route gap.
2. **The weighted average underflows** when every lower firing strength is near the subnormal floor:
   `lower = [1e-322, 1e-322]`, `values = [1e-4, 2e-4]` gives `Y(lower) = 0.0`, below every consequent.
   At `w = 0.99` this produces BMM's 2 and 3 bracket violations.
3. **The cost ratio measures input validation.** "About 3 times cheaper" is timed through the public
   functions, and `_validated` takes most of `nie_tan_reduce`'s time; "8 to 12" and "three runs" trace
   to no committed output.
4. **The per-output pools count `unit-spread` twice.** Its single output enters both the gamma and the
   lambda pool, as File 02's rule says, but §1 and the closure text do not say so.
5. **The tests cannot see several errors.** Reproduced on `c8a1dd54` before any change
   (`mutate.py`, below): all eight mutants survive all 46 tests, among them `route_gap = 0.0` and every
   output reading column 0. `test_sweep_rows_hold_the_invariants` has two checks that cannot fail
   (`Db_max <= 0.5` is the clip itself; `passes <= 28` raises earlier) and one absolute tolerance that
   does not scale with the consequents.

Burak also found that `km_guard_stops` and `km_passes_mean` differ on his desktop (17 against 15 at
`w = 0.3` `unit-spread`), in columns `compare_sweep.py` does not compare.

## Decisions (Bengisu, 2026-11-11, in the session's question dialog)

| Question | Answer |
| --- | --- |
| Item 1 | The exhaustive route decides. Iterative KM stays as the textbook reference, with its passes and its route gap as checked diagnostics; the counterexample becomes a test. |
| Items 2 and 4 | Both in this PR. `NieTanDefuzzifier` in `src/` has the same arithmetic as item 2; it is left for the class-switch PR and only noted here. |
| `km_*` columns | Diagnostics: printed, never compared or cited (L-025: a rounding-level count belongs to the implementation). Burak's 17 against 15 is recorded as the measured platform difference. The route gap alone is checked against a tolerance. |
| Working order | This plan, then tests, then code, then regenerated evidence, all shown before any push or comment. |

## What changes

| File | Change |
| --- | --- |
| `scripts/type_reduction_discrepancy.py` | `_measure` takes `y_l`, `y_r` from `exhaustive_type_reduce`; `_weighted_average` divides by the largest weight first; a new last column `km_route_gap_over_tolerance_max`; docstrings no longer claim the iterative route agrees "to rounding" in general. |
| `tests/test_type_reduction.py` | Tests that kill each mutant below; an exact-rational second route for the exhaustive route; the counterexample and the underflow case pinned; the two checks that cannot fail replaced, the tolerance scaled. |
| `docs/evidence/adr-011-type-reduction/compare_sweep.py` | Fails when any row's route gap exceeds its tolerance (`km_route_gap_over_tolerance_max > 1`). |
| `docs/evidence/adr-011-type-reduction/reducer_positions_and_cost.py` | Times `_validated` alone and the arithmetic alone, and prints the ratio both ways. |
| `docs/evidence/adr-011-type-reduction/file02_rule_by_point_set.py` | Prints what each pool contains and the anchored-only pools beside File 02's. |
| `docs/evidence/adr-011-type-reduction/*.out.txt` | Regenerated from the scripts at the new commit. |
| `docs/evidence/adr-011-type-reduction/2026-11-11-<sha>.tsv` | The sweep at the code commit, beside the earlier two files, which stay. |
| `docs/evidence/adr-011-type-reduction/mutate.py`, `mutate.out.txt` | The mutation check, before and after. |
| `docs/evidence/adr-011-type-reduction/README.md` | A dated section; the earlier text stays. |
| `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md` | A dated section 15 with every correction, the closure text restated in full and register row 4 restated; sections 1 to 14 are not edited. |
| `docs/implementations/2026-10-21-type-reduction-reference.md`, `2026-11-07-issue-61-part-a-closure.md` | A dated note each, pointing here. |

## Implementation approach

**Item 1.** The sweep's endpoints come from the switch-vertex enumeration of P2: for each endpoint,
all `R + 1` switch vertices are evaluated and the extreme is taken. There is no iteration and no stop
rule, so no float fixed point can form. The iterative route still runs on every point; its passes,
guard stops and its gap to the exhaustive route are reported. The gap is divided by the point's
tolerance, `64 R eps max|c|`, so one dimensionless column says whether the iterative route agreed to
rounding on that run.

**Item 2.** `Y(w) = sum w_r c_r / sum w_r` is computed as `(w / s) @ c / sum(w / s)` with `s = max w`.
In exact arithmetic the two are equal. In float64 the largest scaled weight is 1, so neither the
products nor the sum can underflow to zero together.

**Exhaustive route, second route.** Now that it decides, the iterative route can no longer serve as
its check. A test enumerates all `2^R` vertices in exact rational arithmetic (`fractions.Fraction`,
which converts a float exactly) on small boxes whose firing spans `1e-20` to `1`, including the
item 1 counterexample and the item 2 underflow case, and compares the exact minimum and maximum with
`exhaustive_type_reduce`.

**Tests against the mutants.** `mutate.py` applies each mutant to a copy of the script, runs the test
file, and restores from the copy (never from git), checking the hash between runs:

| Mutant | What it breaks |
| --- | --- |
| M1 `route_gap = 0.0` | The diagnostic §7 rests on. |
| M2 every output reads column 0 | Lambda rows silently become gamma rows. |
| M3 mean and median swapped, M4 p90 is the median | The summary statistics. |
| M5 `Db` clip removed | A reducer within rounding outside a narrow band scores above 1/2. |
| M6 degenerate tolerance 0, M7 tolerance times 1000 | The degenerate count. |
| M8 the left guard returns the worse value | The guard's contract. |
| M9 distances from the iterative route again | Item 1's fix. |
| M10 no rescale in `_weighted_average` | Item 2's fix. |

M9 and M10 exist only after the fix.

**Items 3 and 4.** Script changes as in the table; the text corrections go into findings section 15.

## Mathematical / Statistical details

- **Why the exhaustive route is exact up to rounding (P2).** For sorted consequents, the minimum of
  `Y` over the box is attained at a switch vertex `w^(l,k)` (upper bounds on the first `k` rules,
  lower on the rest) for some `k` in `0..R`. Taking the minimum over all `R + 1` computed values
  returns the computed value of the minimising vertex, or of another vertex whose computed value is
  lower by rounding only. Each value carries the rounding of one dot product and one sum.
- **Why iterative KM can fail in floats.** P3's lemma needs `y_t = Y(v)` exactly for some `v` in the
  box. In the counterexample `y_0 = 0.5 / (0.5 + 1e-17)` rounds to exactly 1.0, a consequent.
  `k = #{c <= y_0}` then counts that rule, the switch vertex is `upper`, and `Y(upper)` rounds to 1.0
  again: a fixed point that is not the minimum.
- **The rescale.** `(w / s) @ c / sum(w / s) = (w @ c) / sum(w)` for any `s > 0`. With `s = max w`,
  `sum(w / s) >= 1`, and the dot product is a sum of terms of size `c_r` times weights in `(0, 1]`.
- **The tolerance column.** `route_gap / (64 R eps max|c|)`. A value at most 1 means the routes agree
  to the rounding the tests have always allowed. Above 1 the iterative route disagreed, which is a
  property of that algorithm on that run, not of the figures, since they no longer use it.

## Predictions, fixed before any figure is regenerated

On the committed design (`--footprint 0.1 0.3 0.6 g59 --points 2000 --seed 84`, survey `3d1569d`):

1. Every figure in findings §1, §5 and §8 is unchanged at the four decimals printed, and
   `compare_sweep.py <new> 2026-11-07-10e8174.tsv` exits 0.
2. `km_route_gap_over_tolerance_max` is at most 1 in every row.
3. All ten mutants are killed.

At `--footprint 0.8`, `0.9` and `0.99`:

4. `n_bracket_violations` is 0 in every row, including the two BMM rows at `0.99` that show 2 and 3
   on `c8a1dd54`.
5. The iterative route's gap stays non-zero at `0.8` and `0.9` in `unit-spread` (0.0038 and 0.0769 on
   `c8a1dd54`), and the new ratio column there is above 1. The distances no longer depend on it.

If prediction 1 fails, the work stops and the moved figure is shown to Bengisu before anything else.

## Design decisions

- **Exhaustive over a repaired stop.** A neighbour check at the stop would also fix the
  counterexample, but it needs a new float-level argument for P3. The exhaustive route needs none, and
  it costs 28 evaluations per endpoint on 27 rules.
- **Exhaustive over raising on a large gap.** Raising keeps the committed TSV byte-identical, but it
  would make wide footprints unsweepable, and #61's decision 2 (the footprint set, @BahaJarad's) may
  add them.
- **Append-only records.** The findings, the README and the two implementation records are dated, so
  every correction goes into a dated section; the closure text and register row 4 are restated there
  in full, and sections 9 and 10 say nothing new.
- **`src/` untouched.** `NieTanDefuzzifier` shares item 2's arithmetic; it is Bengisu's module, and
  the class switch (#61, comment 6727626228) is where it changes.

## Verification

To be filled after the build.

## Related docs

- PR #143; #61 (comments 6319118939, 6665986289, 6707436941, 6727626228); reviews 5828001160 and
  5831798256.
- `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md`, `docs/evidence/adr-011-type-reduction/`.
- `docs/implementations/2026-10-21-type-reduction-reference.md`,
  `docs/implementations/2026-11-07-issue-61-part-a-closure.md`.
- ADR-011 in `docs/decisions.md`.
