# 2026-10-06: pr103-final-review-fixes

## Problem / Motivation

The 2026-10-06 re-review of PR #103 (Issue #74) at `1662ddb` found the code
correct and verified three ways: a local run of every gate, CI on `1662ddb`, and
Burak's desktop run of `9e18067`, whose code tree is the same. Every finding of
the 2026-09-28 review was closed and nothing in the hard-constraint list was hit.
It left one minor and five nit findings, all in records rather than behaviour,
and three of the nits sat in text written by the reviewer's own 2026-10-03
commits. They were fixed on the branch before approval rather than sent back for
another round. Each was reproduced first:

| # | Severity | Finding | Reproduced how | Outcome |
| --- | --- | --- | --- | --- |
| 1 | minor | Burak's evidence record says the runbook's third mutation "still names `member.prepare(...)`" and that "its literal command made no diff". | The runbook comment (`issuecomment-5969089080`) has `created_at` equal to `updated_at`; line 198 of its body is `sed -i 's/nm.prepare(transpiled_circuit.copy())/nm.prepare(circuit.copy())/' ...`; applied to `9e18067`'s script it changes line 171. | A dated, attributed correction is appended to the record. Burak's text and verdict are unchanged. |
| 2 | nit | The `docs/decisions.md` as-of note said "Measured on the PR #103 review-fix commit" without naming it, under a heading dated before the measurement. | The measurement is from `dd1ad56`, committed 2026-10-03; the heading says 2026-10-02. | The note names `dd1ad56` and its date. |
| 3 | nit | NC-021's runner clause stopped at `b6693ce`, although the row names `ubuntu-latest` as the pass-count authority. | CI run `37209627083` on `1662ddb`: `711 passed, 1 skipped` on both legs. | The figure joins the Notes chain. |
| 4 | nit | The evidence record was named in neither implementation doc. | The runbook's step 9 loop returned `0` for it at `1662ddb`. | The 2026-09-22 manifest gains a row for it and one for this document. |
| 5 | nit | `run_ensemble`'s docstring restated `optimization_level=1` and `seed_transpiler=0` although the module now holds them in constants. | Docstring line 145 against lines 76-77 at `1662ddb`. | The docstring names `_TRANSPILE_OPTIMIZATION_LEVEL` and `_TRANSPILE_SEED`. |
| 6 | nit | The runbook's final step asked for four deliverables; the raw transcript and the `uname -a` / `pip freeze` fingerprint did not arrive, and steps 2, 7, 8, 9, 10a and 13 were not reported. | Read the PR thread and the record. The reviewer ran steps 7, 8, 9 and 13 at `1662ddb`; each matched its expectation, step 9 apart from finding 4. | **Waived in the approval**, not fixed: only Burak can produce them. See Design decisions. |

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/first_ensemble_run.py` | `run_ensemble`'s docstring names the transpile constants instead of restating their values; no behaviour change. |
| `docs/evidence/pr103-burak-desktop/2026-10-04-verification.md` | A dated reviewer correction is appended after Burak's unchanged record. |
| `docs/decisions.md` | The ADR-021 amendment's as-of note names `dd1ad56` and the date it was measured. |
| `docs/numerical-claims.md` | NC-021 is re-pinned to the docstring commit with a fresh direct collection, and its chain gains the CI figure at `1662ddb`. |
| `docs/implementations/2026-09-22-issue-74-smoke-transpilation.md` | The manifest gains rows for the evidence record and this document. |
| `docs/implementations/2026-10-06-pr103-final-review-fixes.md` | This document. |

## Implementation approach

**Two commits, the shape Rule 6 needs.** The docstring change is committed
alone as `3d76d00`. The NC-021 entry for `dd1ad56` says "only `docs/` changes
after that commit", which a change to a `.py` file makes false even though no
test moves. So every gate and the full suite were run at `3d76d00`, and this
docs-only commit records that collection and names the commit, rather than
carrying `712` across.

**The register row.** NC-021 is a single line several thousand characters long.
It was edited by a script that asserts each replacement target occurs exactly
once and that the row still has six cells with its closing `|`, the defect the
2026-10-03 round fixed.

**The correction.** It cites only what was measured: the comment's timestamps,
its body line 198, and the one line the command changes in `9e18067`. It also
names where `member.prepare(...)` does appear in the runbook (the Step 11 and
Step 12 Python snippets, body lines 238 and 285), without guessing why the
mismatch was reported.

## Mathematical / Statistical details

N/A: purely structural. No channel parameter, estimator, threshold or behaviour
changed.

## Design decisions

**Appended to Burak's record rather than edited.** The file is his account of
his run, and its verdict is right: the mutation was killed either way. Editing
his sentence would make the record say something he did not write. The
alternative, asking him to correct it, would cost a round trip for a
mechanical correction. The appended section is dated and names who wrote it.

**No new desktop run for this round.** This departs from the project's practice
of having Burak's desktop verify each review round, so it is stated rather than
left silent. The only executable-file change is a docstring, the collected count
is unchanged, and `git diff 9e18067 HEAD -- . ':!docs'` is that one docstring
hunk, so Burak's run of `9e18067` still covers the behaviour that merges. CI on
the new head is the gate for this commit.

**Transcript and fingerprint waived.** Burak's comment and record state his
platform, Python version and the six pinned packages, and the record-finding
steps he did not report were run by the reviewer and matched. Those are the
reviewer's checks of the reviewer's own 2026-10-03 commits, so they are not
independent; the independent review of that work is Baha's approval of
2026-10-05.

**Fixed before approval, not sent back.** All six findings are records, three of
them in the reviewer's own text, and the code was already verified. This follows
the 2026-10-03 round: a fast-forward on top of the author's tip, none of his
commits rewritten.

## Verification

Run from a checkout of `feature/issue-74-smoke-transpilation`:

- `git diff 9e18067 HEAD -- . ':!docs'`: one hunk, the `run_ensemble` docstring.
- `ruff check .`, `ruff format --check .`, `mypy --strict`,
  `mypy --strict src/superconducted`, `python scripts/check_ids.py` and
  `git diff --check origin/main HEAD`: clean.
- `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider`
  equals NC-021's value, and `python -m pytest tests/ -q` passes; on a clone
  without the `calibration-data` ref, exactly one archive-backed test skips.
- `grep -E "^[|] NC-[0-9]+ " docs/numerical-claims.md | grep -cv "[|] *$"`
  prints `0`.
- The runbook's step 9 loop prints no line starting with `0`, now that this
  document is listed:
  `for f in $(git diff --name-only origin/main...HEAD); do echo "$(grep -lF "$f" docs/implementations/2026-09-22-issue-74-smoke-transpilation.md docs/implementations/2026-10-03-pr103-review-fixes.md docs/implementations/2026-10-06-pr103-final-review-fixes.md | wc -l) $f"; done`
- `gh api repos/SuperconducTED/superconducted-noise-engine/issues/comments/5969089080 --jq .body | sed -n 198p`
  prints the `nm.prepare` mutation the correction quotes.

## Related docs

- `docs/implementations/2026-09-22-issue-74-smoke-transpilation.md`, the change
- `docs/implementations/2026-10-03-pr103-review-fixes.md`, the previous round
- `docs/evidence/pr103-burak-desktop/2026-10-04-verification.md`, Burak's run
- ADR-021 amendment (2026-09-18) and ADR-028 in `docs/decisions.md`
- `docs/numerical-claims.md`, NC-021 and Rule 6
- Issue #74, PR #103 and its review thread; Issue #58 and PR #79

---

## Merge with `main` after PR #98, as-of 2026-10-06

Everything above this heading is left unedited. PR #98 merged into `main` as
`e411911` after this PR was approved at `82dfe3e`, and GitHub reported the PR
as conflicting. `main` was merged into this branch as `0ce3b42` (a merge, not a
rebase: NC-021, the evidence record and the runbook pin this branch's SHAs).

**What conflicted, and how it was resolved.** One textual conflict:
`docs/advisor/2026-09-03-decisions-from-akba.md`, where #98 and this branch
each appended after the same line (171). The file is append-only, and #98's
own "Merge reconciliation, as-of 2026-09-29" section sets the rule for this
case: order is merge order, not date order, so text already on `main` is never
displaced. Main's 184 appended lines are therefore kept byte for byte, and this
branch's "Outstanding items, as of 2026-10-02" section follows them. That
section, which had never reached `main`, gained two things: one sentence saying
why a 2026-10-02 entry follows 2026-10-03 ones, and a clause pointing its
"Outstanding" at the lead's approval session (Issue #109), which is how #98's
2026-10-03 decision entry says every tabled item now closes. A script asserted
that the resolved file starts with `main`'s file exactly; `git diff -U0
origin/main` shows one hunk at its tail and no removed line.

`docs/decisions.md` and `docs/numerical-claims.md` merged without conflict. #98
touched ADR sections far from ADR-021 and only the NC-045 row, so the ADR-021
as-of note and the NC-021 row arrive as this branch wrote them. Checked after
the merge: one "ADR-021 amendment as of 2026-10-02" heading, one NC-021 row
with 7 pipes, no `NC-` row missing its closing pipe, and `scripts/check_ids.py`
clean.

**Nothing executable moved.** PR #98 changes only `docs/`, so no test of this
branch can be un-skipped or broken by the merge, and no runbook step changes.

**NC-021, per Rule 6.** Re-measured at the merge `0ce3b42` and recorded by the
following docs-only commit. `main`'s own tip was collected first, because a
merged count that disagrees with `main`'s row plus the branch delta usually
means `main`'s row is stale: it collects `701` at `e411911`, matching its row.

**Verification at `0ce3b42`** (Mert's laptop, Windows 11, Python 3.12.10, the
six key packages at the pinned versions; provisional, as before): `ruff check
.`, `ruff format --check .` (68 files), `mypy --strict` (38 source files),
`mypy --strict src/superconducted` (26) and `scripts/check_ids.py` clean; the
suite count is NC-021's, every collected test passing. The desktop run at
`9e18067` (`docs/evidence/pr103-burak-desktop/2026-10-04-verification.md`) is
not repeated, because the merge brings in no code; CI on the pushed head is the
check that it did not.
