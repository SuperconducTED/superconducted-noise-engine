# 2026-11-09: phase-4-records-and-redate

## Problem / Motivation

Four records fell behind on 2026-11-09. NC-021, the test-suite size, still read 1053 after PRs #133 and #135 merged
with new test files; Rule 6 requires a measurement at each merge commit, recorded in a following docs-only change. The
status snapshots of 2026-11-04, 11-07 and 11-09 existed only in session worktrees, so the next status run had nothing
on `main` to diff against. Plan section 8.4 still put L1 (job 1 of #125) in the week of 2026-11-04, which passed with
the freeze still blocked. Phase 3's milestone, due 2026-10-31, still had seven open issues and PR #111 with no
decision recorded on any of them.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | NC-021 becomes 1138 at `d929424a` (PR #135's merge), with 1082 at `3e5703b4` (PR #133's merge) and the 1053 that held through PR #141's merge recorded in its narrative. |
| `docs/status/2026-11-04-status.md`, `2026-11-07-status.md`, `2026-11-09-status.md` | The three snapshots, unchanged from the sessions that wrote them. |
| `docs/roadmap/2026-10-23-phase-4-plan.md` | A dated note under section 8.4 that ties L1 to the freezing commit instead of a week, and a new Appendix A.7 with the phase-3 triage for the lead's approval. |
| This document | The record. |

## Implementation approach

**NC-021.** Both counts were measured directly at their merge commits in throwaway trees from the exact-pin
interpreter, `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` and `python -m pytest
tests/ -q -p no:cacheprovider`, and CI's figures on the same commits were read from their runs. The row's value
column, command column and date move to the newest merge; the older values go into the narrative, as earlier entries
did. `6d64f64b` and `19cbe70f` were collected as well, to show the 1053 still held until PR #133.

**The snapshots** were copied byte for byte. They are dated documents and are not edited.

**Section 8.4** gets an appended "as of" note. The table above it is not edited.

**A.7** comes from a read-only audit of each phase-3 issue against `main` at `d929424a`. Its load-bearing claims were
re-checked before writing: the three ADR statuses, the workflow and script lines, the comment counts on #104 and #108,
the two comments it cites (6140571135, decision B; 5885407524, section 4), and the register's rule list.

## Mathematical / Statistical details

N/A: purely records. No figure here is derived; each count is a direct collection at a named commit, and the sums
written beside them say so.

## Design decisions

- **L1 as an event, not a week** (the lead's choice): a new fixed week would go stale like the last one, because the
  freeze waits on reviews and a desktop run whose dates nobody controls.
- **Both NC-021 values in one PR**: the two merges came hours apart, and the lead chose to batch them; each value names
  its own commit, which is what Rule 6 requires.
- **The triage is a table, not actions**: closing an issue is an outward step; A.7 proposes, and the lead decides.
- **PR #111 is not triaged here**: a separate session prepares its merge, close or split recommendation.

## Verification

```bash
git show d929424a:docs/numerical-claims.md >/dev/null   # the base this edits
grep -n "^| NC-021 | Full test-suite size | 1138 |" docs/numerical-claims.md
python scripts/check_ids.py
ruff format --check .
```

To reproduce the counts: check out `3e5703b4` and `d929424a` in throwaway trees and run the two pytest commands
above with `PYTHONPATH=src` on the exact pins; CI runs 42577736972 and 42607022579 hold the runner's figures.

## Related docs

- `docs/roadmap/2026-10-23-phase-4-plan.md`, sections 8.4 and Appendix A.
- `docs/status/2026-10-28-status.md` (the previous snapshot on `main`).
- PRs #133, #135, #141, #144; issue #125.
