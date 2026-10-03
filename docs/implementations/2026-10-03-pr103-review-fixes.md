# 2026-10-03: pr103-review-fixes

## Problem / Motivation

PR #103 (Issue #74) moves `scripts/first_ensemble_run.py` to compile once to the
calibrated basis before `FuzzyNoiseModel.prepare()`. The 2026-09-28 review
requested changes at `cc46902`; Burak answered at `b6693ce`. The 2026-10-02
re-review of `b6693ce` found the code fix correct and every gate green, but left
four minor and four nit findings, mostly in the records the PR writes. These
fixes were made by the reviewer and landed on the PR branch as a fast-forward
(the project's practice for mechanical review findings), so the author re-runs
verification rather than re-implementing. Each finding was reproduced before it
was fixed:

| # | Severity | Finding | Reproduced how | Outcome |
| --- | --- | --- | --- | --- |
| 1 | minor | NC-021's new note sat after the row's closing pipe: a seventh cell under a six-column header. | The row had 7 pipes and no trailing `\|`. `gh api markdown -f mode=gfm` on a minimal table of the same shape renders the header's columns only; the extra cell is dropped. | Cell closed; value re-measured per Rule 6 at the code commit and recorded in a docs-only commit. |
| 2 | minor | The advisor as-of paragraph was inserted inside the 2026-09-18 entry, above two of its paragraphs, in a file that is append-only by its own header (lines 10-11). | `git diff origin/main` placed the hunk at line 160, not at the end. The 2026-09-28 review asked for a note "under item 15", which invited this. | Moved to a new `## Outstanding items, as of 2026-10-02` section at the end of the file. The diff against `main` is now one pure addition. |
| 3 | minor | The implementation doc's What-changed table listed 2 of the PR's files and did not record that the sanity run now honours `--mf-placement`. | Compared the table with `git diff --name-only origin/main...b6693ce`. | Table completed in place (a manifest, so corrected in place, per the PR #78 precedent); the `--mf-placement` change described. |
| 4 | minor | The PR description is stale: "669 passed", three modules, "No ADR updated", the ADR-ledger checkbox ticked, the amendment's Open status not stated. | Read against the PR's file list and ledger edits. | **Left to the author.** The description is Burak's text; the exact edits are listed in the PR comment. |
| 5 | minor | `main()`'s call to the width guard and the three new `raise` branches had no test; only the helper was tested. | At `b6693ce` no test imports `scripts.first_ensemble_run.main` (`git grep`), so deleting the call could fail nothing. | Seven new test cases (below), each mutation-checked. |
| 6 | nit | The 2026-09-22 implementation doc had no trailing newline. | `tail -c 1` showed the file ending in the `4` of `#74`, not a newline (`0a`). | Added. |
| 7 | nit | The doc said the basis rule "matches #58's `benchmarks/reference.py`" helper; it does not on malformed entries, and the path is wrong. | PR #79 at `5400702`: `_gate_entries` raises on a non-mapping entry. On `main`, `CalibrationGateEligibilityPolicy.eligible_operations` and `training.targets.gate_lengths` both skip one. | **Documented, not changed** (see Design decisions). Docstring and doc corrected; a test pins the skip. |
| 8 | nit | The copy-isolation test checked distinct objects (`is not`) but not content, so "every member sees the same compiled circuit" was half pinned. | The fake transpiler returned a copy of an empty source, so a member handed the source would still pass. | The fake now returns a distinguishable compiled circuit; the test asserts both members' circuits equal it, are separate copies, and that `transpile` received the source. |
| 9 | nit | The `docs/decisions.md` as-of note cited the test-only `sx` member, while the amendment table it updates measures installed errors from real members on the ibm_fez fixture. | The table's metric had no replacement figure. | Measured and appended (below). |

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/first_ensemble_run.py` | `_calibration_basis_gates` docstring states its correspondence with PR #79's `_basis_gates` and the one deliberate difference; no behaviour change. |
| `tests/test_first_ensemble_run.py` | Seven new cases (width boundary, missing `qubits` list, `main()` width refusal before simulation, missing or non-list `gates` twice, no unitary gate, non-mapping entry skipped) and a tightened copy-isolation test. |
| `docs/decisions.md` | The ADR-021 amendment's 2026-10-02 as-of note gains the table's own metric, measured. |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | Burak's item-15 paragraph moved from inside the 2026-09-18 entry to a new dated section at the end of the file. |
| `docs/implementations/2026-09-22-issue-74-smoke-transpilation.md` | What-changed table completed, `--mf-placement` sanity change described, PR #79 correspondence corrected, trailing newline added. |
| `docs/numerical-claims.md` | NC-021 re-measured at the code commit, its notes cell closed and its chain extended (separate docs-only commit). |
| `docs/implementations/2026-10-03-pr103-review-fixes.md` | This document. |

## Implementation approach

**The register row (finding 1).** The closing `|` that Burak's edit left in
the middle of the row is moved to its end. The note the dropped cell carried
(`705` at the merge `063c777`, measured directly) joins the Notes chain, with
the observation that `1ec7499` changed the test file without adding a case, so
`b6693ce` also collects 705. The new value is measured at this round's code
commit and recorded by a following docs-only commit that names it, the
two-commit shape Rule 6 has used since `947fe3d`.

**The advisor record (finding 2).** The paragraph is removed from inside the
2026-09-18 entry and re-appended at the end under the heading form the file
already uses twice. It keeps Burak's date, 2026-10-02, because that is when its
fact was established. Its lead changes from "As of 2026-10-02." to "Item 15,
ask 3.", because the heading now carries the date and "this ordering" had lost
its antecedent. A script asserted that, after removal, the file equals `main`
byte for byte before the section was appended.

**Tests (findings 5 and 8).** The `main()` test replaces `AerSimulator` with
a tripwire that raises `AssertionError`. That pins "rejected before
simulation" as well as "rejected": a guard moved below the simulator's
construction fails with the tripwire instead of the expected `ValueError`. The
copy-isolation test's fake transpiler returns a circuit carrying an `sx`, so a
member handed the uncompiled source fails the content check.

Every new or tightened guard was mutation-checked: the invariant was broken in
`scripts/first_ensemble_run.py`, the matching test was run, and the file was
restored and its SHA-256 compared. All nine mutations were killed: member
receives the source; members share one object; `main()` drops the guard; the
guard moves below the simulator; `>` becomes `>=`; and each of the four
`raise`/skip branches is disabled.

## Mathematical / Statistical details

N/A: purely structural. No channel parameter, estimator or threshold changed.

## Design decisions

**Fixed on the author's branch, not sent back.** Every finding was mechanical
or a record correction, and the code was already correct. A round trip would
have cost days. The commits are a fast-forward on top of `b6693ce`; none of
Burak's commits is rewritten.

**Finding 7 documented, not changed.** Making the smoke script raise on a
non-mapping gate entry, as PR #79 does, would make the script stricter than
the engine it exercises: on `main`, both `CalibrationGateEligibilityPolicy` and
`gate_lengths` skip such an entry, and ADR-028's "fail loudly" applies to a
corrupt *value* (`gate_length`), not to an unreadable entry. So the script
matches `main` and says so. The test that pins the skip names PR #79 and is to
be flipped on purpose when the script consumes #79's helper.

**The PR description is the author's.** The edits are listed in the PR comment.
Editing another author's description from this tooling was refused on PR #99
(2026-09-14), and the text is his to state.

**NC-021 is cited, not restated, here.** A number in an implementation doc
rots (PR #29, PR #32). The Verification section below compares the register
with a live count instead.

## Verification

Local results are provisional. They are from Mert's laptop (Windows 11,
Python 3.12.10, a venv whose `numpy`, `qiskit`, `qiskit-aer`, `pytest`, `ruff`
and `mypy` match `requirements*.txt` exactly). The authoritative run is Burak's.

- `ruff check .`, `ruff format --check .`, `mypy --strict` (configured scope,
  including `scripts/`), `mypy --strict src/superconducted` and
  `python scripts/check_ids.py`: clean.
- `pytest tests/ -q`: every collected test passes; the count is NC-021's.
- Mutation check: 9 of 9 killed, script restored byte-identical.
- Replay of the regression inputs: the old order gives identical counts with
  and without the `sx` error; the new order gives `{"0": 256}` with it.
- Installed errors on the ibm_fez fixture, the amendment table's metric:
  `qft_circuit(2)` 4 (`rx`, `sx` on qubits 0 and 1) and `qft_circuit(3)` 6
  under the new order with no warning; 0 with the warning under the old order.

**Authoritative run, Burak's desktop (bash on WSL2).** The full runbook, with
every command, is the second PR comment of this round; it pins the PR head SHA
and stops if the checkout differs. Its steps, each with a differential or
self-consistent expectation:

1. Fresh clone into a new directory, check out `feature/issue-74-smoke-transpilation`,
   stop unless `git rev-parse HEAD` equals the SHA in the comment.
2. New venv from `requirements.txt` and `requirements-dev.txt`, editable install,
   machine fingerprint.
3. The five gates, plus `mypy --strict src/superconducted`.
4. NC-021 against a live `--collect-only` and the full run: three equal numbers.
5. Finding 1: no `NC-` row lacks its closing `|`.
6. Finding 2: `git diff -U0 origin/main` on the advisor file is one hunk that
   starts after `main`'s last line and removes nothing.
7. Findings 3 and 6: every file the PR changes is named in one of the two
   implementation docs; the 2026-09-22 doc ends in `0a`.
8. Findings 5 and 8: the named tests pass, then three mutations applied with
   `sed` each make their test fail, and `git status --porcelain` is empty after
   restoring.
9. The #74 claim itself: the replay above, compared within the run.
10. Finding 9: the installed-error figures printed equal the ones in the
    `docs/decisions.md` note.
11. `tsk.py`, `kraus.py` and `benchmarks/harness.py` unchanged against `main`.
12. The CLI: `--qubits 2` completes; `--qubits 3` exits non-zero with
    "exceeds calibration width".

He reports four ways: the transcript as a PR comment, a committed record at
`docs/evidence/pr103-burak-desktop/`, the exact SHA tested, and the machine
fingerprint.

## Related docs

- `docs/implementations/2026-09-22-issue-74-smoke-transpilation.md`, the work
  this round corrects
- ADR-021 amendment (2026-09-18) and ADR-028 in `docs/decisions.md`
- `docs/advisor/2026-09-03-decisions-from-akba.md`, item 15
- `docs/numerical-claims.md`, NC-021 and Rule 6
- Issue #74, PR #103 and its review thread; Issue #58 and PR #79
