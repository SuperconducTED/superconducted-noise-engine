# 2026-08-31: adr-nc-collision-and-branch-reissue

## Problem / Motivation

Two problems, one of which only surfaced while preparing for the other.

**Identifier collision.** PR #44 landed on `main` while the #45/#46 branch was
open, and the two sides independently allocated the same identifiers to
different things:

| Id | On `main` (landed) | On this branch |
| --- | --- | --- |
| `ADR-024` | Degeneracy of random TSK consequent initialization (Open) | `calibration-data` ledger and collision trees (Accepted) |
| `NC-023` | P(identity channel) from `consequent_init="random"` = 1/4 | Distinct device states in the archive = 504 |
| `NC-024` | Consequent seed-search limit = 64 seeds | Verified historical retention depth ≥ 60 days |

Git surfaces this only as a text conflict in two files. Resolving that conflict
without noticing the semantics would leave two different `ADR-024` sections in
`docs/decisions.md` — for a register whose entire purpose is traceable claims,
a worse defect than the conflict that revealed it.

**Branch reissue.** The branch was also reissued onto fresh commit objects. The
20 commits themselves were never in question — they are unchanged in content —
but the branch tip had briefly been the parent of commits authored outside the
team, and the reissue removes that ancestry rather than leaving it implied.
This is bookkeeping, not a code change; it is recorded here because the commit
hashes in earlier rows of `docs/numerical-claims.md` moved as a result.

**Test-count drift.** `NC-021` read 204 on this branch and 187 on `main`. Both
were correct pre-merge measurements and neither describes the merged tree —
exactly the drift Rule 6 exists to catch, and the same shape as the stale-row
failures behind issues #29 and #40.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | `main`'s ADR-024 kept; this branch's renumbered to ADR-025 and placed after it in numeric order. |
| `docs/numerical-claims.md` | This branch's NC-023..NC-028 renumbered to NC-025..NC-030; NC-012 and NC-R002 citations followed; NC-021 re-measured to 225. |
| `scripts/canonical_snapshot_digest.py` | ADR reference repointed to ADR-025 (the collisions channel). |
| `tests/test_canonical_snapshot_digest.py` | Same repoint in the module docstring. |
| `tests/test_probe_historical_properties.py` | Retention-depth claim reference repointed to NC-026. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | File table, ADR-017 note, and decision list updated for the renumber and the evidence move. |
| `docs/evidence/pr47-outage-enumeration/` | Moved from `evidence/PR-47-Evidence/` to match the layout #44 established. |
| `docs/implementations/2026-05-07-repo-bootstrap.md` | Dead link to an untracked tooling file removed; template provenance reworded. |
| `src/superconducted/interfaces.py` | Docstring now names `docs/decisions.md` alone as where the open decisions are recorded. |

## Implementation approach

**Which side renumbers.** `main`'s identifiers are landed, reachable from the
default branch, and mutually consistent — its NC-023 cites its ADR-024 for the
1/4 derivation. An unlanded branch renumbers; an Accepted decision already on
the default branch does not. So `ADR-024 → ADR-025` and
`NC-023..NC-028 → NC-025..NC-030`, both on this branch only.

**Order of rewriting.** The renumber shifts ids *upward* into a range the
branch itself occupies, so a naive left-to-right pass would collide with its
own output (`NC-023 → NC-025` then `NC-025 → NC-027` would move the first row
twice). Substitutions are applied highest-first — NC-028 before NC-027 before
NC-026 — so every target is above the range still to be processed and no row
moves twice.

**Which references follow.** Not every mention of `ADR-024` in the merged tree
refers to this branch's decision. `src/superconducted/integration/aer_factory.py`,
`scripts/first_ensemble_run.py` and `tests/test_channel_viability.py` all cite
`main`'s ADR-024 — degeneracy, the 1/4 rate, the seed limit — and are correct
as they stand. Only references whose *subject* is the ledger/collisions
decision or the retention-depth claim were repointed. The two rows that cite
"distinct device states (NC-023)" — NC-012 and the retired NC-R002 — refer to
this branch's claim and were followed; they are easy to miss because they sit
outside the conflicted region and merged cleanly.

**Evidence layout.** `evidence/PR-47-Evidence/` and #44's move of everything to
`docs/evidence/<slug>/` do not overlap as paths, so git merged them without
complaint and left this PR's evidence as the only directory outside the
convention. A clean merge is not the same as a consistent tree.

## Mathematical / Statistical details

N/A — purely structural. No formula, estimator, or numeric algorithm changed.
The one number that moved, `NC-021`, is a count of collected tests, and its
composition is given below rather than asserted.

## Design decisions

**Renumber the branch, not `main`.** Renumbering `main` would invalidate
`ADR-024` citations in three source files already merged, and would rewrite an
identifier that external references (issue threads, review comments) may
already use. The unlanded side is cheaper to move and has no external
citations yet.

**Re-measure `NC-021` rather than compute it.** `204 + 21 = 225` is correct
arithmetic, and the arithmetic was *not* the source of truth: the row was
restamped from an actual `--collect-only` run on the merged tree, which then
agreed with the arithmetic. A register that exists to catch drift cannot itself
carry an inferred number — Rule 6 asks for the value, the source commit, and
the date to move in one commit.

**State `NC-021` differentially.** The row now records `166 + 38 + 21 = 225`
rather than a bare `225`. An absolute count in a runbook goes stale silently
when either side changes; a decomposition that has to add up surfaces the
staleness as a visible mismatch. This follows the same reasoning that made
issues #29 and #40 expensive.

**Do not change `python_version` to silence mypy.** `mypy --strict` currently
fails in a fresh environment on numpy 2.5.2's bundled stubs, which use the
3.12+ `type` statement while `[tool.mypy]` pins `python_version = "3.11"`. The
failure is in a third-party stub, not in this repository — the same command
with `--python-version 3.12` reports no issues in 27 source files. Raising the
pin would silently drop the 3.11 support that `requires-python = ">=3.11"`
promises, so it is left for a deliberate decision rather than folded into this
change. It affects `main` identically and is not introduced here.

## Verification

Run from the repository root. `python` must be a real 3.12 interpreter.

- `python -m pytest tests/ --collect-only -q -o addopts=""` — tail line reads
  `225 tests collected`, matching NC-021.
- `python -m pytest -p no:cacheprovider` — `225 passed`.
- `ruff check --no-cache` — `All checks passed!`.
- `ruff format --check --no-cache` — `92 files already formatted`.
- `mypy --strict --no-incremental --python-version 3.12` — `no issues found in
  27 source files`. Without the flag this fails in numpy's stubs; see Design
  decisions.

Collision resolution, which no test covers:

- `grep -c '^## ADR-024' docs/decisions.md` and `grep -c '^## ADR-025'` — each
  returns `1`.
- `grep -oE '^\| NC-[0-9R]+' docs/numerical-claims.md | sort | uniq -d` — empty;
  no duplicated row id.
- `git ls-files 'evidence/*'` — empty; nothing remains outside `docs/evidence/`.
- `git grep -c 'pr47-outage-enumeration' docs/numerical-claims.md` — `1`; NC-029
  cites the moved path. Note that a bare `git grep PR-47-Evidence` is *not* a
  useful check here: this document names the old path while explaining the move,
  so it matches itself.

## Related docs

- ADR-024 and ADR-025 in `docs/decisions.md`
- NC-021, NC-025..NC-030 in `docs/numerical-claims.md` (Rule 6)
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` —
  the work this branch carries
- `docs/implementations/2026-08-28-issue-35-consequent-degeneracy.md` — the
  `main` side of the collision
- Issues #45, #46; PRs #44, #47
