# 2026-08-24: pr32-review-fixes

## Problem / Motivation

Review of PR #32 found no hard-constraint violations — the PR is
documentation-only and touches no Python — but surfaced one substantive
defect and several convention gaps, all concentrated in the verification
record added by the PR's second commit (`46d90bc`).

1. **An unsourced number was recorded as a regression.** The verification
   record carried `| pytest tests/ -q | 152 passed | 149 passed |` and a
   note declining to resolve the difference, while the document
   simultaneously declared `Verdict: VERIFIED`. The 152 figure originated
   in the runbook posted to the PR, which pre-filled it into the template
   the verifier was told to complete. It has no source anywhere in the
   repository. The suite contains 149 tests.

   This is the failure mode `docs/numerical-claims.md` was written to
   prevent: the register exists because a fabricated benchmark figure
   propagated across four documents before anyone checked it. A phantom
   test-count regression entering the permanent record is the same
   mechanism at a smaller scale.

2. **The changed-files tables were incomplete.** Both the implementation
   doc's "What changed" table and the PR body listed four files; the PR
   contains five. The convention requires a row for every file modified.

3. **A second evidence tree was introduced.** The new record landed in
   `docs/verification/`, but the convention established on `main` by
   PR #36 is `docs/evidence/<slug>/`.

4. **Absolute line numbers were recorded as verification claims.** The
   grep check cited hits at lines 290 and 301. Those positions are
   branch-local — `docs/decisions.md` shifts whenever an ADR entry is
   added above them, and `main` has moved past the revision this branch
   was cut from.

5. **The `as-of` dates did not describe real events.** Two blocks were
   headed `as-of 2026-06-30` while stating that the facts were verified
   on 2026-08-20. That date appears nowhere else in the repository.
   Rule 3 of the claims register requires such dates to be real.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/verification/2026-08-20-pr32-burak-desktop.md` → `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md` | Moved onto the `docs/evidence/<slug>/` convention and rewritten: mismatch resolved, line-number claims replaced with the invariant, evidence pointer corrected. |
| `docs/numerical-claims.md` | Added `NC-021` registering the full test-suite size (149) with a rerunnable source, so runbooks cite a row instead of a recollection. |
| `docs/implementations/2026-08-20-cycle2-governance-reconciliation.md` | Added the two missing table rows, corrected the `as-of` dates, moved the git-identity note out of Design decisions, and strengthened the Verification section. |
| `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | Gate-status block re-dated `as-of 2026-08-20`. No change to the gate reasoning or the Open status. |
| `docs/roadmap/2026-05-25-cycle-2-plan.md` | Reconciliation section re-dated `as-of 2026-08-20`; oversized P2 row trimmed. The 2026-05-25 body remains untouched. |
| `docs/implementations/2026-08-24-pr32-review-fixes.md` | This document. |

## Implementation approach

**Resolve the mismatch; do not overwrite it.** The obvious fix — change
`152` to `149` and delete the note — would have erased the evidence that
a wrong expectation was issued and caught. That is the audit trail rule 5
of the claims register protects for retired claims, and the same logic
applies here. The row is therefore kept, with the 152 marked as the
runbook figure and flagged wrong, and a `Resolution` section states the
true count, how it was rechecked, and why no regression exists.

The verifier's conduct was correct, and the record now says so. The
runbook instructed him to report any difference without fixing it, and
that is exactly what he did. Framing the resolution as a verifier error
would be both wrong and corrosive to the desktop-verification process.

**Prevent recurrence structurally, not by vigilance.** 152 could be
asserted because no row existed to check it against. `NC-021` closes
that: the count now has an ID, a rerunnable command as its source, and a
verification date, so the next runbook cites `NC-021` instead of a
remembered number.

**Claim invariants, not coordinates.** The grep check now asserts
"exactly two hits, both inside the ADR-016 entry, none inside ADR-018."
That claim survives arbitrary insertions above it; 290 and 301 do not.

**Correct the dates rather than explain them.** `2026-06-30` appears
nowhere else in the repository and no recorded event falls on it. Since
2026-08-20 is the only date on which any of these facts were actually
checked, both blocks now carry it.

## Mathematical / Statistical details

N/A — documentation only. No formula, metric, or numeric algorithm is
introduced or altered. The single quantity touched is a test count, whose
derivation is a collection run recorded in `NC-021`.

## Design decisions

- **Kept the 152 row rather than deleting it.** Alternative: silently
  correct the Expected column. Rejected — a verification record whose
  history has been tidied cannot serve as an audit trail, which is its
  only purpose.
- **Registered the count in `docs/numerical-claims.md`.** The register's
  Purpose section scopes it to public-facing documents and evidence
  records are not on that list, so this is a small widening. Justified:
  the defect being fixed is precisely an unsourced number, and a fix that
  does not give the number a source only postpones the next one.
- **Moved to `docs/evidence/` rather than keeping `docs/verification/`.**
  One evidence tree, not two. The runbook that created the second one was
  written before PR #36 established the convention.
- **Left the substance of the reconciliation untouched.** The ADR-018
  confirmation, the ADR-019 gate reasoning, the conjunctive-prerequisite
  argument, and the append-and-date discipline were all independently
  re-verified during review and are correct. Nothing here revisits them.

## Verification

Every factual claim in the original PR body was independently re-run
during review against `main` at `194d050` and confirmed:

| Claim | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 34 files already formatted |
| `mypy --strict src/superconducted` | no issues in 22 source files |
| `pytest tests/test_membership.py` | 34 passed |
| `TanhSigmoidMF`:278, `TanhBellMF`:326 | confirmed |
| `slope <= 0` at 299 / 346; `left >= right` at 348 | confirmed |
| `set_parameters` re-validates at 309 / 361 | confirmed |
| `ccdade0`, `07ee487` ancestors of `main` | both confirmed |
| `decisions.md` was 465 lines; note at 452-465, xref at 451 | confirmed — issue #20's cited 457-470 did overrun the file |

Checks specific to this change:

- `python -m pytest tests/ -q --collect-only` on `main` and on `46d90bc`
  — 149 collected on both. This is the source behind `NC-021`.
- `git grep -c "mean-aggregates counts" -- docs/decisions.md` on the
  branch — 2 hits, both inside the ADR-016 entry.
- `ruff check . && ruff format --check . && mypy --strict src/superconducted`
  — unchanged, since no Python was touched.
- `git diff main -- docs/roadmap/2026-05-25-cycle-2-plan.md` — the
  2026-05-25 body still shows additions only below it.

## Related docs

- `docs/implementations/2026-08-20-cycle2-governance-reconciliation.md`
- `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md`
- `docs/numerical-claims.md` (`NC-021`)
- PR #32; Issue #20; PR #36 (`docs/evidence/` convention)
