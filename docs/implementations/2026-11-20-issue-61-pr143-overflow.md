# 2026-11-20: issue-61-pr143-overflow

PR #143 (#61 Part A) after @BurakOztekin's desktop review 5923434762 (CHANGES_REQUESTED, at `0d53fc60`). The review
reproduced the PR on his WSL2 desktop and found one defect: the reference's weighted average does not keep its
documented finite-input contract. This record is written as the plan first, with the mutation predictions fixed before
anything is run; the results are appended below it. Laptop, provisional.

## Problem / Motivation

The module contract (`_validated` in `scripts/type_reduction_discrepancy.py`) accepts any finite `lower`, `upper` and
`values` with `0 <= lower <= upper` and non-zero sums. `_weighted_average` divides the weights by their largest entry
(the 2026-11-11 underflow fix) but not the values, so `scaled @ values` can overflow although the weighted average itself
is finite. The review's example, `lower = upper = [1.0, 1.0]` and `values = [1e308, 1e308]`, should give `1e308`; the
exhaustive route, the iterative route, BMM and Nie-Tan all return `inf`. It does not touch the measured survey range. The
review asks for the contract to be handled in the reference and pinned by a regression test.

Checking the same contract found a second overflow of the same kind, which the review did not name: firing bounds near
the largest double, for example `lower = [1e308, 1e308]`, `upper = [1.7e308, 1.7e308]`. Nie-Tan forms `lower + upper`
and the iterative route's start point forms `0.5 * (lower + upper)`; both overflow, so Nie-Tan returns `nan` and the
iterative route starts from `nan` (its endpoints still come out, but after a different number of passes than the same
inputs divided by `2**1023` take).

## Decisions (Bengisu, 2026-11-20, in the session's question dialog)

| Question | Answer |
| --- | --- |
| How the contract is fixed | Power-of-two scaling of the values inside `_weighted_average`, so finite inputs give a finite result; not a narrower contract that refuses large inputs. |
| The firing-sum overflow | Fixed in the same round, by writing `0.5 * lower + 0.5 * upper`; the reply says it was found while checking. |
| The shipped `fuzzy/defuzzification.py`, which has the same unscaled sum | Not changed here (outside #143); noted in the reply, an issue drafted in a later session. |
| Mert's hand-derivation request (6877022015) | A later session; nothing in this round answers it. |

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/type_reduction_discrepancy.py` | `_weighted_average` scales the values by a power of two and saturates at the largest double; Nie-Tan and the iterative start form `0.5 * lower + 0.5 * upper`. |
| `tests/test_type_reduction.py` | Five tests: the review's example on all four routes, equal values at the largest double, value scaling by powers of two, firing scaling by powers of two, and bit identity with the old formula where it was finite. |
| `docs/evidence/adr-011-type-reduction/mutate.py` | M13 to M16 for this round; M10 retargeted at the new text of `_weighted_average` (the same mutant). |
| `docs/evidence/adr-011-type-reduction/mutate.out.txt` | The run at this round's head; the run at `0d53fc60` kept beside it as `mutate.at-0d53fc60.out.txt`. |
| `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md` | Section 17, appended. |
| `docs/evidence/adr-011-type-reduction/README.md` | A dated section, appended. |
| `docs/implementations/2026-11-20-issue-61-pr143-overflow.md` | This record. |

## Implementation approach

`_weighted_average(weights, values)` becomes, with `s = weights / max(weights)` as before:

1. `m = max |values|`. If `m == 0`, return the old expression (the average of zeros).
2. `e` from `math.frexp(m)`, so `m = f * 2**e` with `0.5 <= f < 1`; `v = numpy.ldexp(values, -e)`, so `|v| < 1`.
3. `q = (s @ v) / sum(s)`; return `math.ldexp(q, e)`. If that raises `OverflowError`, return the largest double with
   the sign of `q`.

`nie_tan_reduce` passes `0.5 * lo + 0.5 * hi` instead of `lo + hi`, and `_km_endpoint` starts from
`_weighted_average(0.5 * lower + 0.5 * upper, values)`.

## Mathematical / Statistical details

**Why nothing moves where the old formula was finite.** Multiplying a float by `2**k` is exact as long as the result
stays in the normal range, and rounding commutes with it: `fl(2**k x) = 2**k fl(x)` for every operation whose exact result
and rounded result are both normal. The new expression is the old one with every value multiplied by `2**-e`, each
product, partial sum and the quotient multiplied by the same `2**-e`, and the quotient multiplied back by `2**e`. So the
two expressions return the same double whenever no intermediate of either one is subnormal or overflows. The sweep's
inputs are firing strengths in `[0, 1]` and consequents of order 1e-2 to 1e-1, far from both edges, so the committed TSV
is expected to come out byte for byte the same. The same argument covers `0.5 * lo + 0.5 * hi`: `fl(0.5 a + 0.5 b) =
0.5 fl(a + b)`, and `_weighted_average` is invariant to scaling its weights by `0.5` exactly, since it divides by their
largest entry.

**Why the result is finite.** A weighted average with non-negative weights lies in `[min values, max values]`, so its
true value has magnitude at most `m`. With `|v| < 1` and `0 <= s <= 1`, `|s @ v| <= sum(s) <= n_rules`, so nothing
overflows before the last step. The last step can still round past the largest double when `m` is within a few ulps of
it: with `values = [DBL_MAX, DBL_MAX]` and weights `[1.0, 0.2]`, `q` rounds to `1.0` and `2**1024` is not representable
(in a seeded search, 30,037 of 200,000 cases with values at the top edge did this). The true result there is `DBL_MAX`,
so the saturation returns the nearest double to it, not a clamp of anything the old formula returned finite.

**What is not covered.** Values whose magnitudes span more than about `2**1022` lose the small ones to subnormal rounding
after the shift; the old formula did the same with weights. No value is refused for it.

## Design decisions

- **Scaling, not refusing.** A narrower contract (a `ValueError` when a weighted sum would overflow) changes no arithmetic,
  but it moves a limit of float64 into the reference's contract, and every caller would need to know it. Scaling keeps the
  contract as documented. Bengisu's choice.
- **A power of two, not `max |values|`.** Dividing by `m` itself fixes the overflow too, but it rounds every value and would
  change the sweep's figures at the last bit (in a prototype, 13,869 of 20,000 random cases differed). That is mutant M14.
- **Saturating at the top edge** rather than letting `math.ldexp` raise `OverflowError`, so finite inputs keep giving a
  finite result; the one case that reaches it is pinned by a test, so the branch is not dead (L-084 of the math skill).
- **Relational tests, not literals.** The scaling tests compare a route on scaled inputs with the same route on unscaled
  ones, bit for bit, so they hold on any IEEE-754 machine.

## Mutation predictions (written before the run)

| Mutant | Change | Predicted to be killed by |
| --- | --- | --- |
| M13 | the value scaling removed (the `0d53fc60` arithmetic) | the review's example, the value-scaling test, the top-edge test |
| M14 | values divided by `m` instead of a power of two | the bit-identity test |
| M15 | Nie-Tan back to `lo + hi` | the firing-scaling test (Nie-Tan) |
| M16 | the iterative start back to `0.5 * (lower + upper)` | the firing-scaling test (the iterative route's pass counts) |
| M17 | the top-edge saturation removed | the top-edge test (an `OverflowError`) |
| M10 | the weight rescale removed, retargeted at the new text | `test_mutation_switch_point_stop_alone_cycles`, as at `0d53fc60` |

M1 to M9, M11 and M12 do not touch `_weighted_average`, so they are predicted to be applied and killed by the same tests
as in `mutate.out.txt` at `0d53fc60`.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_type_reduction.py -q -p no:cacheprovider
# the sweep of runbook 6874400150, step 4, once at 0d53fc60 and once at this round's head, on the same machine
PYTHONPATH=src python -m scripts.type_reduction_discrepancy --range-source survey:docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv --footprint 0.1 --footprint 0.3 --footprint 0.6 --footprint g59 --points 2000 --seed 84 --out sweep.tsv
cmp sweep-at-0d53fc60.tsv sweep-at-head.tsv                      # expected: identical, byte for byte
python docs/evidence/adr-011-type-reduction/compare_sweep.py sweep-at-head.tsv docs/evidence/adr-011-type-reduction/2026-11-11-35da0446.tsv
PYTHONPATH=src python docs/evidence/adr-011-type-reduction/mutate.py all
ruff check . && ruff format --check . && mypy --strict && python scripts/check_ids.py
PYTHONPATH=src python -m pytest tests/ -q -p no:cacheprovider
```

## Related docs

- PR #143; review 5923434762 (@BurakOztekin); #61.
- `docs/implementations/2026-11-11-issue-61-pr143-review-fixes.md` (the underflow fix this extends).
- `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md`, sections 15 and 16.

## Results, 2026-11-20: the first form (laptop, provisional)

Python 3.12.10, NumPy 2.4.4, from the pinned environment (`C:/pvci`), `PYTHONPATH=src`. Nothing below has run on Burak's
desktop.

**The defect reproduced first.** The new tests were committed before the fix (`1e567cbc`); on `0d53fc60`'s code 13 of the
new cases fail and 262 pass: the review's example on all four routes, equal values at the largest double on all four, the
value-scaling test on all four, and the firing-scaling test.

**The fix** (`bede3887`) is as planned, plus one change the plan did not list: `_validated` tested for a zero firing sum by
forming `lower.sum()` and `upper.sum()`, which overflow near the largest double (harmless, since the test is `== 0`, but it
raised a `RuntimeWarning` in the firing-scaling test). It now reads the largest entry, which is zero exactly when the sum of
non-negative terms is; the sums are formed only for the error message. Under the default warning filter no test can tell
the two apart, so no mutant was added for it; with `-W error::RuntimeWarning` the firing-scaling test fails without it.

**A correction to the plan's mathematics.** "`fl(0.5 a + 0.5 b) = 0.5 fl(a + b)`" holds for bounds in the normal range;
halving a subnormal bound can drop its last bit. The sweep's bounds are normal, and the docstring of `nie_tan_reduce` says
"for bounds in the normal range".

**Tests.** `tests/test_type_reduction.py`: 275 passed (261 before, 14 new cases in five tests), also with
`-W error::RuntimeWarning`.

**The sweep is unchanged.** The runbook's step 4 sweep was run on this laptop at `47bdb0cc` (the plan commit, whose code is
`0d53fc60`'s) and at the fix: the two files are identical apart from the `# commit:` header line, including every `km_*`
column, and the first is identical, apart from the same line, to the committed `2026-11-11-35da0446.tsv`.
`compare_sweep.py` against that file: 96 rows, largest relative difference `0.000e+00`, every uncompared `km_*` column 0
rows differing, exit 0. So no figure in the findings or the closure text moves.

**Mutation.** `mutate.py all` at the fix (`mutate.out.txt`; the `0d53fc60` run kept as `mutate.at-0d53fc60.out.txt`):
18 of 18 killed. M1 to M12 by the same tests as at `0d53fc60`. M10 did not need retargeting: its text,
`scale = float(weights.max())`, still occurs exactly once. M13, M15, M16 and M17 by the predicted tests. M14's line names
`test_mutation_switch_point_stop_alone_cycles`, the first failure in file order: dividing by `max |values|` rounds every
value, and that moves the rounding-level cycle fixture (the same family as L-063 of the math skill). Applied by hand, M14
fails exactly two tests, that fixture and the predicted bit-identity test.

**Gates.** `ruff check .` clean, `ruff format --check .` 109 files, `mypy --strict` 49 source files, `scripts/check_ids.py`
clean.

**Full suite** at the first form: 1328 passed, 0 skipped (`pytest tests/ -q -rs`; 1314 at `0d53fc60` plus the 14 new
cases; this clone can read the `calibration-data` ref, so the archive test ran).

**The first form moves the cost figures.** The evidence scripts of runbook step 5 give their committed outputs at the first
form (`file02_rule_by_point_set.py` and `survey_reversal_check.py` with no diff, `second_route_reducers.py` printing
`BMM 0.0337, Nie-Tan 0.0483` and `Nie-Tan 231, BMM 744, tie 0`, `km_cycle_sensitivity.py` with no diff). But
`reducer_positions_and_cost.py` times `_weighted_average`, and the shift added work to every call. One run at the first
form (`reducer_positions_and_cost.at-bede3887.out.txt`, non-timing lines identical to run 3's):

| Ratio to Nie-Tan, per point, 27 rules | runs 1 to 3 (`0d53fc60`'s arithmetic) | first form, one run |
| --- | ---: | ---: |
| `karnik_mendel_detailed`, through the public functions | 3.1 to 4.9 | 3.7 |
| iterative KM, arithmetic, consequents sorted once | 9.6 to 13.9 | 9.0 |

Nie-Tan's arithmetic went from 3.8 us (run 3) to 6.1 us, so the arithmetic ratio fell below the committed range. The
closure text's "10 to 14 times on the arithmetic" and Burak's desktop figures (3.5 and 10.8, review 5923434762) describe
`0d53fc60`'s arithmetic, which the first form no longer runs. That led to amendment 1.

## Amendment 1, 2026-11-20, before the final form

**Decision (Bengisu, in the session's question dialog):** shift only on overflow. The arithmetic stays `0d53fc60`'s
wherever it is finite, so the cost figures and Burak's desktop run still describe the code, and the power-of-two shift is the
fallback when the plain quotient is not finite. The finite-input contract, the tests and the sweep are unchanged.

**The final form.**

1. `_weighted_average`: `s = weights / max(weights)` as before, but first, if `max(weights)` is infinite, raise
   `OverflowError` (only a sum of two firing bounds near the largest double gets there). Then the plain quotient
   `(s @ values) / sum(s)`; if it is finite, return it. Otherwise shift the values by `2**-e` and multiply back, with the
   saturation at the largest double, as in the first form.
2. `nie_tan_reduce` and the iterative start keep `lo + hi` and `0.5 * (lower + upper)`, and on `OverflowError` retry with
   `0.5 * lo + 0.5 * hi`. On the normal path that costs one comparison; on the overflow path NumPy prints its
   "overflow encountered in add" warning before the retry, so the firing-scaling test filters that one warning by name.
3. `_validated` keeps the zero-sum test on the largest entry.

**Why the result is the same double.** Where the plain quotient is finite, the code is `0d53fc60`'s, so nothing can move.
Where it is not, the first form's argument holds for the shifted path. The halves retry is reached only when `lo + hi`
overflowed, where `0d53fc60` returned `nan` or started from `nan`.

**Mutation predictions for the final form (written before it is built).**

| Mutant | Change | Predicted to be killed by |
| --- | --- | --- |
| M13 | the value fallback removed (the plain quotient always returned) | the review's example, the value-scaling test, the top-edge test |
| M14 | the fallback divides by `max |values|` instead of a power of two | the value-scaling test (its relation is bit for bit) |
| M15 | Nie-Tan's retry back to `lo + hi` | the firing-scaling test (`OverflowError`) |
| M16 | the iterative start's retry back to `0.5 * (lower + upper)` | the firing-scaling test (`OverflowError`) |
| M17 | no saturation at the largest double | the top-edge test (`OverflowError`) |
| M18 | no `OverflowError` for infinite weights | the firing-scaling test (Nie-Tan gives `nan`, the iterative passes differ) |

The bit-identity test now holds by construction; it stays as the pin against a later change to the plain path. M14 of the
first form, which changed the plain path, is no longer a mutant of this code; under the final form a change to the plain path
would be caught by that test.

**Checks for the final form:** the tests with `-W error::RuntimeWarning` apart from the one named filter; the sweep at the
final form identical to the one at `47bdb0cc`; the step 5 scripts; `mutate.py all`; the cost script, whose ratios should
fall back inside runs 1 to 3's range; the gates; the full suite.
