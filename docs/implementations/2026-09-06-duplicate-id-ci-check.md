# 2026-09-06: Duplicate ADR / NC identifier CI check

## Problem / Motivation

Identifier collisions in this repository do not surface as merge conflicts, so
nothing catches them. Two branches that each append "the next free id" to a
*different* decision edit different regions of the same file; git merges both
cleanly and the duplicate is found later by a reader.

Three instances were live on 2026-09-06, all in PR #69's review:

1. PR #69 added a **second `NC-021` row** rather than updating the existing
   one, leaving the stale `280` reading as current. The register's Rule 6 says
   the PR that changes a repo-measured claim updates the row's value, source
   commit and date in the same commit.
2. PR #52 and PR #69 both claimed **`NC-031` through `NC-034`** for unrelated
   claims (enumeration-sweep recall vs. `sx` gate length; capture rate vs. Aer
   SuperOp difference). This was measured, not assumed:
   `git merge-tree $(git merge-base pr-52 pr-69) pr-52 pr-69` reports **zero**
   conflict markers, and merging the two branches produced four duplicated ids.
3. PR #69 added `docs/decisions/drafts/ADR-024-calibration-training-target.md`
   while `docs/decisions.md` already used ADR-024 for "Degeneracy of random TSK
   consequent initialization" — the ADR whose clause 5 Issue #57 itself depends
   on. Because the draft is a *new file*, there was not even a text conflict.

Issue #57's NFR-8 predicted the second case in writing and it still happened,
which is the evidence that a written convention alone is not sufficient here.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/check_ids.py` | Collects ADR and NC *definitions* from the ledger, `drafts/` and the claims register, and reports duplicates and cross-file collisions; `--next` prints the next free id in each sequence. |
| `tests/test_check_ids.py` | Exercises each rule on a synthetic repository under `tmp_path`, pins the three 2026-09-06 collisions in the shape they took, and asserts this repository is currently clean. |
| `.github/workflows/ci.yml` | Runs the check before the slower lint/type/test steps so a collision is reported in seconds. |
| `docs/decisions.md` | Adds the promoted-draft note ADR-017's ledger entry was missing, so the repository satisfies the convention rule A4 enforces. |

## Implementation approach

The script parses three sources and treats only **definitions** as claims on an
id — never citations:

| Source | Definition is |
| --- | --- |
| `docs/decisions.md` | a line matching `^## ADR-NNN` |
| `docs/decisions/drafts/ADR-NNN-*.md` | the file's `^# ADR-NNN` heading, falling back to its filename when the heading is absent |
| `docs/numerical-claims.md` | the **first cell** of a table row, `^\| NC-R?NNN \|`, within the `## Active claims` or `## Retired claims` section |

Anchoring the claims regex at the start of a row is what keeps `see NC-021` in
a Notes cell from registering as a second definition.

Six rules run over those definitions:

- **A1** each ledger heading id appears once
- **A2** a draft's filename id matches its heading id
- **A3** no two drafts claim the same id
- **A4** an id in both the ledger and `drafts/` is legal only if the ledger's
  section for that id references the draft's path
- **N1 / N2** each `NC-NNN` (Active) and `NC-RNNN` (Retired) appears once in
  its own section
- **N3** no id appears in both sections, which would be a retirement that
  copied the row instead of moving it

Each violation renders as `path:line: [rule] message`, so CI output is
click-through and names both the offending line and the one it collides with.

Exit status is 0 when clean, 1 otherwise. `--next` reports the next free ADR
and NC id and exits 0 — this is the affordance that makes the script worth
running locally, and it answers the "next free id at merge time" instruction
that Issue #57's NFR-8 and the register's "Adding a claim" step 2 both give
without providing a way to compute it.

## Mathematical / Statistical details

N/A — purely structural. The check is line-oriented text parsing with no
formula, statistic, threshold or fitted constant. That absence is deliberate;
see the first design decision below.

## Design decisions

**How to distinguish a promoted draft from a collision — the decision this
check turns on.** Six draft files legitimately share an id with a ledger entry
today, because a promoted draft stays in `drafts/` as the authoring record. So
"id in both places" cannot itself be the rule. Three options were considered:

- *Compare titles.* Rejected on evidence: ADR-018's draft is titled "Tanh-based
  MF slope positivity convention" and its ledger entry "Tanh membership-function
  slope positivity convention" — one decision, two wordings. Exact matching
  gives a false positive today, and fuzzy matching would need a similarity
  threshold. A fitted constant would also sit badly in a repository whose own
  register records "Analytic, not fitted" (NC-023) and "thresholds are
  descriptive, not fitted" (NC-033).
- *Allowlist the six known promotions.* Rejected: it needs an edit on every
  future promotion, and a stale allowlist fails open.
- **Chosen: require the ledger entry to reference the draft path.** This is not
  a new invention — it is the convention `docs/decisions.md` already states:
  "A draft that has been promoted stays in `drafts/` as the authoring record,
  **and the promoted entry says so**." Rule A4 enforces the sentence as
  written. It is deterministic, needs no constant, and self-documents: a
  promotion is recorded where a reader of the ledger will see it.

Enforcing that rule revealed that ADR-017 never received the note, unlike
ADR-018 through ADR-022. That is a real pre-existing gap rather than a false
positive, so it was fixed rather than exempted — a check that is red on `main`
from day one gets ignored. The note cites commit `105cf6c` (2026-06-19), found
with `git log -S`, because that commit names no issue and one was not invented.

**Scope: definitions only, not citations.** Prose and Notes cells reference ids
constantly (`see ADR-014`, `derived from NC-023`). Treating a reference as a
claim would make the check unusably noisy, so only the three definition sites
above are collected.

**Not checked: gaps in a sequence.** Ids are claimed and then abandoned when a
PR closes, so a gap is normal and flagging it would train people to ignore the
output.

**Known limitation, stated rather than worked around.** A repo-local check sees
only what is on the branch. It cannot see an unmerged sibling branch, so it
catches a cross-PR collision at the moment the *second* PR merges, not when the
second PR is opened. For the #52 / #69 case that converts "merges silently,
discovered months later" into "the second PR's CI goes red" — the realistic
ceiling here. Reading open PRs through the API was rejected: it needs a token,
it fails on forks, and it makes CI depend on GitHub availability.

## Verification

```bash
python scripts/check_ids.py                    # exit 0, "No duplicate or colliding..."
python scripts/check_ids.py --next             # ADR-026 / NC-031 on this branch
pytest tests/test_check_ids.py -q              # 22 passed
pytest tests/ -q                               # 302 passed
ruff check . && ruff format --check .
mypy --strict
```

Confirmed against the real failures rather than only synthetic ones. Copying
the script into a worktree of PR #69 and running it there reports all three
live collisions:

```
docs/decisions/drafts/ADR-024-calibration-training-target.md:1: [A4] ...
docs/numerical-claims.md:82: [N1] NC-021 is already defined ... at :81 ...
```

and merging PR #52 into that worktree (which succeeds with no conflicts) adds
four more: `NC-031`, `NC-032`, `NC-033`, `NC-034`.

## Related docs

- `docs/decisions.md` — the drafts paragraph rule A4 enforces; ADR-017's new
  promoted-draft note
- `docs/numerical-claims.md` — Rule 6 (a repo-measured claim is updated in
  place), "Adding a claim" step 2 (pick the next available id), "Retiring a
  claim" step 1 (move the row)
- Issue #57 NFR-8 — "the next free ADR id / NC id at merge time"; the
  prediction this check turns into a gate
- PR #69, PR #52 — the three collisions the regression tests pin
