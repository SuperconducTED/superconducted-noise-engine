# 2026-11-13: issue-61-pr143-second-review-gaps

PR #143 (#61 Part A) after @mertefesensoy's second review, 5854006318 (COMMENT, at `1b8f6089`). That
review found all five items of the first round closed and left three non-blocking points this change
answers (a to c), one question for decision 2 (d) and one standing request. This record is written as
the plan first, with the predictions fixed before anything is run; the results are appended below it.
Laptop, provisional; the canonical run is still Burak's desktop batch.

## Problem / Motivation

a. **The new column's "max" is not pinned.** In `_summary_rows`, replacing `max` by `min` for
   `km_route_gap_over_tolerance_max` passes all 259 tests, and the `0.8` and `0.9` sweep then passes
   `compare_sweep.py` with exit 0 although its route gap is 1e10 tolerances. The figures do not move
   (the band comes from the exhaustive route); what moves is the diagnostic the desktop run reads.
b. **A file without the column passes the check.** `compare_sweep.py` reads the column only where it
   is present and non-empty, so a sweep from the old code, which has no such column, compared with
   itself exits 0. The check the first review asked for is then silently skipped.
c. **The cost range rests on two runs.** Findings section 15.3 and the closure text in 15.8 give
   iterative KM at 3.4 to 4.9 times Nie-Tan through the public functions and 9.6 to 13.9 times on the
   arithmetic, "over two laptop runs". The reviewer's third run on the same laptop gave 2.8 and 10.3,
   outside the first range. L-070 in the math skill: two runs do not bound a ratio.

Not changed here: d (whether the comparator stays fatal on footprints where the iterative route is
known to fail, `0.8` and `0.9`) is decision 2's, which @BahaJarad has not taken; and the request that
the owner re-derive the headline figures herself, which the reply answers with a question about what
would satisfy it.

## Decisions (Bengisu, 2026-11-13, in the session's question dialog)

| Question | Answer |
| --- | --- |
| How the fixes land | Build, push, and post a dated runbook that replaces 6781261561, so Burak's one desktop run covers the final code. |
| Item c | Commit a third run of the cost script and restate the range over the committed runs, naming the run count; the desktop run gives the figure. |
| The re-derivation request | Ask the reviewer what would satisfy it (a timing ratio cannot be derived by hand; the table pools 24,016 scores). Nothing is claimed. |

## What changed

| File | One-sentence description |
| --- | --- |
| `tests/test_type_reduction.py` | Two tests: the summary reports the largest gap over tolerance of several measurements, and `compare_sweep.py` fails on a new file without the column. |
| `docs/evidence/adr-011-type-reduction/compare_sweep.py` | Fails when the new file lacks `km_route_gap_over_tolerance_max` or leaves it empty in any row. |
| `docs/evidence/adr-011-type-reduction/mutate.py` | Mutants may name their own target file; M11 (`max` to `min` in the column) and M12 (the column check skipped when absent) added. |
| `docs/evidence/adr-011-type-reduction/mutate.out.txt` | Regenerated: thirteen mutants. |
| `docs/evidence/adr-011-type-reduction/reducer_positions_and_cost.run3.out.txt` | A third committed run of the cost script. |
| `docs/evidence/adr-011-type-reduction/README.md` | A dated section: what moved and the new expectations. |
| `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md` | Section 16, appended: the cost range over three committed runs and the closure sentence restated. |
| `docs/implementations/2026-11-13-issue-61-pr143-second-review-gaps.md` | This record. |

## Implementation approach

Tests first, then the fix, then the mutants, then the regenerated outputs, as in the 2026-11-11 round:

1. **Tests (one commit).** (a) Three measurements with gap over tolerance 0, 5 and 2: the column must
   read 5. This passes on the current code; its job is to kill the `min` mutant. (b) A new file whose
   header has `km_route_gap_max` but not `km_route_gap_over_tolerance_max`, compared with a committed
   file that has neither: exit 1. This fails on the current code.
2. **Fix (one commit).** `compare_sweep.py` checks the header of the new file and every row's value
   before anything else, and prints how many rows lack it.
3. **Mutants.** `mutate.py` keeps its exact-replacement discipline (backup copy, SHA-256 check, abort on
   a replacement that does not match exactly once) and gains an optional target per mutant, so a
   mutant of `compare_sweep.py` restores that file, not the script.
4. **Cost run 3.** `reducer_positions_and_cost.py`, unchanged, run once at the new head on the same
   laptop; committed beside the two earlier outputs.
5. **Records.** Dated sections appended; nothing in a dated document is edited in place.

## Mathematical / Statistical details

**The column.** For one summary cell with kept measurements `m_1 ... m_n`, each with route gap `g_j`
and tolerance `t_j = 64 R eps max|c|`, the column is `max_j (g_j / t_j)`, with `0/0 = 0` and `g/0 = inf`
for `g > 0` (`_gap_over_tolerance`). `compare_sweep.py` requires `max_j (g_j / t_j) <= 1` in every row
of the new file. A `min` in place of the `max` reports the best point instead of the worst, so a single
bad point in a cell would pass.

**The cost range.** Each run of the cost script times both reducers on the same points and reports
the ratio of per-point times. A range over `k` runs is the smallest and largest ratio seen; it says
how far the laptop's load moved the ratio on those runs, and nothing about a run not made. It is not
a confidence interval, and the closure text says how many runs it covers.

## Predictions (fixed before running)

1. On `1b8f6089`'s code, test (a) passes and test (b) fails; after the fix both pass;
   `tests/test_type_reduction.py` goes from 259 to 261 passed.
2. `mutate.py all`: the eleven earlier mutants stay KILLED; M11 and M12 are KILLED, and each fails
   in its own test (the M11 run by test (a), the M12 run by test (b)).
3. `scripts/type_reduction_discrepancy.py` is unchanged, so the README's sweep command gives data rows
   byte-identical to `2026-11-11-35da0446.tsv`, and `compare_sweep.py` exits 0 against both committed
   TSVs with the same largest differences as before (`0.000e+00`, `2.809e-11`).
4. No prediction for the third cost run's ratios: whatever they are, the restated range covers the
   committed runs.

## Design decisions

- **Fail on a missing column rather than warn.** The comparison exists to be run on another machine
  by someone who will read only its exit code; a warning would let the old failure mode back in.
- **Restate rather than replace the closure sentence.** Section 15.8's text is dated and stays; section
  16 gives the sentence the ledger should take, as 15.8 did for section 1.
- **No new number from the reviewer's run.** His 2.8 and 10.3 are in his review, not in a committed
  output; section 16 cites them as his and bounds the range by committed runs only.

## Verification

```bash
PYTHONPATH=".;src" C:/pvci/Scripts/python.exe -m pytest tests/test_type_reduction.py -q -p no:cacheprovider
PYTHONPATH=".;src" C:/pvci/Scripts/python.exe docs/evidence/adr-011-type-reduction/mutate.py all
PYTHONPATH=".;src" C:/pvci/Scripts/python.exe -m scripts.type_reduction_discrepancy --range-source survey:docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv --footprint 0.1 --footprint 0.3 --footprint 0.6 --footprint g59 --points 2000 --seed 84 --out sweep.tsv
C:/pvci/Scripts/python.exe docs/evidence/adr-011-type-reduction/compare_sweep.py sweep.tsv docs/evidence/adr-011-type-reduction/2026-11-11-35da0446.tsv
C:/pvci/Scripts/python.exe docs/evidence/adr-011-type-reduction/compare_sweep.py sweep.tsv docs/evidence/adr-011-type-reduction/2026-11-07-10e8174.tsv
```

plus the four static checks (`ruff check .`, `ruff format --check .`, `mypy --strict`,
`scripts/check_ids.py`) and the full suite on a merge with `main` (`667972c5`). Results are appended
below.

## Related docs

- PR #143 reviews 5828001160, 5831798256, 5854006318; reply 6781158073; runbook 6781261561.
- `docs/implementations/2026-11-11-issue-61-pr143-review-fixes.md` (the first round).
- `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md`, sections 15.3 and 15.8.
- Issue #61; ADR-011 in `docs/decisions.md`.
