# 2026-11-07: issue-61-part-a-closure

Issue #61 Part A, the rest of PR-A: `main` merged in, the `G59` label confirmed, the sweep re-run, the
evidence scripts committed, and the findings doc with the closure text. Earlier commits are recorded in
`2026-10-21-type-reduction-reference.md`. Measured at `10e8174` on Mert's laptop, provisional; the canonical
run is Burak's desktop batch.

## Problem / Motivation

ADR-011 is Open, and #109 item 4 says its closure waits on #61's measurement. @mertefesensoy's reply on
#61 (comment 6665986289) answered the open questions of comment 6319118939 and reported that "Nie-Tan lower
in all 12 cells" holds for pooled figures only. Three things were left: the `s_i` assumption label could go;
File 02's scripts were lost, so its figures had no command behind them; and the findings doc with the closure
text was still owed. ADR-011's status block also names the type-reduction cost as owed, and nothing had measured it.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/type_reduction_discrepancy.py` | The grid is named `G59` and the TSV header says where `s_i` comes from, instead of `ASSUMED`; no computed value changes. |
| `tests/test_type_reduction.py` | The header test pins the new wording and that `ASSUMED` and `G59-assumed` are gone. |
| `docs/evidence/adr-011-type-reduction/2026-11-07-10e8174.tsv` | The sweep at that commit; data rows identical to the earlier file apart from the grid's name. |
| `docs/evidence/adr-011-type-reduction/README.md` | A dated section for the new file and the scripts; the earlier text stays. |
| `docs/evidence/adr-011-type-reduction/file02_rule_by_point_set.py`, `.out.txt` | Mert's script from comment 6665986289: File 02's rule on each point set. |
| `docs/evidence/adr-011-type-reduction/second_route_reducers.py`, `.out.txt` | The same 2026-11-05 work's second implementation, sharing no reducer or KM code with the script. |
| `docs/evidence/adr-011-type-reduction/survey_reversal_check.py`, `.out.txt` | The 12 cells on survey rows, on distinct rows, with a block interval. |
| `docs/evidence/adr-011-type-reduction/reducer_positions_and_cost.py`, `.out.txt` | P9's identity, the rejected straddling hypothesis, and the cost ratio. |
| `docs/evidence/adr-011-type-reduction/km_cycle_sensitivity.py`, `.out.txt` | The cycle mechanism and how its count moves with the arithmetic. |
| `docs/evidence/adr-011-type-reduction/compare_sweep.py` | Compares another machine's sweep with the committed TSV to rounding, for the desktop batch. |
| `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md` | The Part A findings doc: derivations, tables, closure text, register drafts. |
| `docs/implementations/2026-11-07-issue-61-part-a-closure.md` | This record. |

Nothing in `src/` changes. No ADR-011 ledger edit (architect decision B2). No register row yet.

## Implementation approach

`main` was merged rather than rebased, because the branch is shared and cited by commit. The sweep was re-run on the merged tree first, with the old label, to show the merge moves nothing, and again after the label change for the committed file. The evidence scripts import the sweep's own functions, except the second route, which takes only firing bounds and consequents from the rule base.

## Mathematical / Statistical details

Definitions are in the findings doc, sections 2 to 4. New here: P9, `y_NT = (S_lo Y_lo + S_hi Y_hi) / (S_lo + S_hi)`, so `y_NT - y_BMM = (S_hi - S_lo)(Y_hi - Y_lo) / (2 (S_lo + S_hi))`. BMM weights the two means equally and Nie-Tan weights them by firing mass. The score is `Db = |y - m| / (y_r - y_l)`, in `[0, 1/2]` by the sandwich (P4). The interval in section 5 of the findings is a 90% circular block bootstrap of `median(Db_BMM) - median(Db_NT)`, paired, over consecutive survey rows, blocks of 30, 2,000 resamples. Block length 30, about four days of snapshots at the survey's cadence, is a judgment; `survey_reversal_check.py` also prints blocks of 8 and 90 rows for the two cells whose BMM median is lower.

## Design decisions

- **Survey rows first, pooled figures deciding.** The lead's decision (comment 6665986289, decision 2), and the record says it was made after the result.
- **The earlier TSV stays.** Dated evidence is append-only, and its data rows are identical.
- **`w=0.1` is not called a reversal.** Its median favours BMM, but the interval includes zero.
- **The failed mechanism is reported.** The straddling hypothesis is in the record as rejected, so it is not tried again as if new.
- **The footprint set is marked pending.** @BahaJarad has not answered decision 2, so the PR asks for his review and the register rows wait.
- **Scripts committed rather than left in `_taslaklar`.** File 02's numbers lost their command exactly that way.

## Verification

- `pytest tests/test_type_reduction.py -q`: 46 passed. Full suite and `mypy --strict`: see the PR.
- `ruff check .` and `ruff format --check` on the changed files: clean.
- The sweep twice at `10e8174`: byte-identical, SHA-256 `c61102e80ee82bb83b163748b47cabe03a2770624fac0db3cbf5861c25210b11`.
- `file02_rule_by_point_set.py`: the same output at `aa6d807` and on the merged tree.
- Each evidence script, from the repository root with `PYTHONPATH=src`: output committed beside it.

## Related docs

- `docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md`
- `docs/implementations/2026-10-21-type-reduction-reference.md`
- ADR-009, ADR-011 in `docs/decisions.md`
- #61 comments 6319118939, 6665986289; #84 comment 5885404218; #109 item 4

## Update, 2026-11-11: after the PR #143 reviews

Appended; the text above is not edited. The review fixes are recorded in
`docs/implementations/2026-11-11-issue-61-pr143-review-fixes.md`, and the corrections to the findings in their section 15:
the band from the exhaustive route, the rescaled average, the cost measured three ways (iterative KM 3.4 to 4.9 times
Nie-Tan through the public functions and 9.6 to 13.9 times on the arithmetic alone over two runs, where this record's
findings said about 3), the pool
contents with the anchored-only medians, and the tests that now kill eleven mutants. The sweep file is
`2026-11-11-35da0446.tsv`; the five outputs were regenerated. No headline figure moved.
