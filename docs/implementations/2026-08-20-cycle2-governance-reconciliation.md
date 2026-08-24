# 2026-08-20: cycle2-governance-reconciliation

## Problem / Motivation

Issue #20 (cycle-2 opening, governance-reconciliation slice). Three
governance documents had drifted out of agreement with `main` after PR
#14 merged:

1. The `ADR-018` entry in `docs/decisions.md` carried a trailing
   blockquote that mixed a correct `ADR-006` cross-reference with a
   verbatim duplicate of `ADR-016`'s "mean-aggregates counts" revisit
   note. That note is about benchmark aggregation semantics and has
   nothing to do with the tanh slope convention; it already exists in
   `ADR-016`'s own entry.
2. The `ADR-019` draft still described its ablation gate as blocked on
   both `(a)` the PR #14 merge and `(b)` fitted MF parameters, with no
   record that `(a)` is now satisfied on `main`.
3. `docs/roadmap/2026-05-25-cycle-2-plan.md` predates the PR #14 merge
   and still listed the merge as a to-do, the review stall as a live
   risk, and `ADR-018` formalization as an open `P1` follow-up.

The `ADR-018` ledger text and the implementation already agree, so this
change confirms and records that agreement rather than reconciling a
divergence. No code changed.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | Removed the misplaced `ADR-016` revisit note (14 lines) from the trailing blockquote of the `ADR-018` entry; the `ADR-006` cross-reference line is retained. |
| `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | Appended a dated `Gate status · as-of 2026-08-20` blockquote after Consequences recording prerequisite `(a)` CLEARED and `(b)` PENDING; status stays Open. |
| `docs/roadmap/2026-05-25-cycle-2-plan.md` | Appended a dated `Reconciliation update · as-of 2026-08-20` section plus a `P2` follow-up row; the 2026-05-25 body is untouched. |
| `docs/implementations/2026-08-20-cycle2-governance-reconciliation.md` | This document. |
| `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md` | Burak's desktop re-run of the four guards and the two content checks; records the resolution of the pytest-count expectation. |
| `docs/numerical-claims.md` | Added `NC-021` registering the full test-suite size (149) so verification runbooks cite a source rather than a recalled figure. |

## Implementation approach

Append-and-date rather than edit-in-place, for everything except the
duplicated note.

- **`docs/decisions.md`** — a pure deletion. The duplicated note was
  identified by comparing the `ADR-018` trailing blockquote against
  `ADR-016`'s own entry; the two were byte-identical after the
  `Revisited · 2026-05-25 ·` prefix. Post-edit, `grep -n
  "mean-aggregates counts"` returns two hits, both inside the `ADR-016`
  entry (its Context line and its own revisit note), confirming the
  canonical copy survived and only the duplicate was removed.
- **`ADR-019` draft and the cycle-2 plan** — both are dated records.
  Rewriting the original prose would erase the fact that those
  documents were written before the PR #14 merge, which is exactly the
  provenance a reviewer needs to judge whether a claim was current when
  made. New status is therefore carried in an explicitly dated block
  below the preserved original.

Note on line numbers: issue #20 cites the misplaced note at
`docs/decisions.md` lines 457-470 with the `ADR-006` cross-reference at
456. On `main` at `194d050` the actual positions are 452-465 and 451 —
the file is 465 lines total, so the cited range overran the file. The
edit was made by content match, not by the cited line numbers.

## Mathematical / Statistical details

N/A — purely a documentation change. The mathematics of the tanh slope
convention itself is unchanged and remains documented in the `ADR-018`
entry (`mu(x) = (tanh(slope * (x - center)) + 1) / 2` for the sigmoid;
`mu(x) = (tanh(slope * (x - left)) - tanh(slope * (x - right))) / 2`
for the bell), including the sub-unit-peak consequence.

## Design decisions

- **`ADR-019` gate recorded as a dated append, not a prose rewrite.**
  Alternative considered: edit the `(a)`/`(b)` sentence directly.
  Rejected for the provenance reason above — the same discipline the
  issue mandates for the cycle-2 plan applies to a dated draft.
- **`ADR-019` stays Open.** Its two prerequisites are conjunctive.
  Prerequisite `(b)` — non-trivial fitted MF parameters, from the
  `ADR-014` trainer or manual parameterization — is still outstanding,
  so the manual path is *not* open. Flipping the status or describing
  the ablation as unblocked would be exactly the overclaim the
  numerical-claims discipline exists to prevent.
- **`ADR-018` not reopened.** It stays Accepted; the code matches it.
- **`ADR-016` note consolidation deferred, not actioned.** The
  underlying mean-vs-sum aggregation question is gated on `ADR-015` per
  the plan. Recorded as a `P2` row in the plan's reconciliation
  follow-up table so it survives this PR being merged and closed.

## Verification

`ADR-018` confirmation facts, checked against `main` at `194d050`:

- `TanhSigmoidMF` at `src/superconducted/fuzzy/membership.py:278`,
  `TanhBellMF` at line 326 — both present.
- `slope <= 0` rejected in `_validate` at lines 299 and 346;
  `TanhBellMF._validate` additionally rejects `left >= right` at line
  348. `_validate` is called from each constructor.
- `set_parameters` re-validates in both classes (lines 309 and 361), so
  a valid MF cannot be mutated into an invalid one.
- The `Source` line's PR #14 merge claim holds: `git merge-base
  --is-ancestor ccdade0 HEAD` and the same for `07ee487` both succeed.

Runnable checks (no code changed; these are guard re-runs):

- `ruff check .`
- `ruff format --check .`
- `mypy --strict src/superconducted`
- `pytest tests/test_membership.py` — 34 passed
- `pytest tests/ -q` — 149 passed. The count is registered as `NC-021`;
  cite that row rather than recalling a figure. An earlier runbook for
  this PR asserted 152, which had no source and was wrong.
- `grep -n "mean-aggregates counts" docs/decisions.md` — expect exactly
  two hits, both within the `ADR-016` entry. Assert the count and the
  containing entry, not absolute line numbers: `docs/decisions.md`
  shifts whenever an ADR entry is added above them.

## Related docs

- `ADR-016`, `ADR-018`, `ADR-006` in `docs/decisions.md`
- `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md`
- `docs/roadmap/2026-05-25-cycle-2-plan.md`
- `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md`
- `docs/numerical-claims.md` (`NC-021`)
- Issue #20; PR #14 (commits `ccdade0`, `07ee487`)
