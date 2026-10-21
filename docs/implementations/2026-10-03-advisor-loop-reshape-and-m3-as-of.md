# 2026-10-03: the advisor-loop reshape, the first advisor decision, and the M3 as-of

## Problem / Motivation

PR #98 was opened on 2026-09-14 to circulate the batched advisor e-mail, complete Issue
#56's FR-10.4 comparison, and land the FR-15 and FR-16 ledger fallbacks. It drew no review
in nineteen days. Meanwhile the thing it was built around changed:

- **On 2026-09-29 the lead replaced the batched e-mail.** Each teammate researched their
  brief files, the team decided on evidence, and the decisions were posted on Issue #84,
  one comment per file. The lead now approves those decisions in the advisor role.
- **Between 2026-09-29 and 2026-10-02 Dr. Akba approved, in person**, that process and the
  decisions of all six brief files as the lead presented them. He also gave a direction:
  three engine modes, Type-1 fuzzy, Interval Type-2 fuzzy and a deep-learning model, the
  last to be planned in detail with him in the week of 2026-10-05.
- **The lead moved the `Phase 3 · ANFIS results` milestone** from 2026-09-30 to 2026-10-31
  around 2026-09-29 to 30, because that reshape needs more time.

None of it was in the repository. If #98 had merged as it stood, it would have landed three
records waiting on an action that will never happen. The register said the batch "has not
gone out" and promised to append a send date. The ADR-009 and ADR-011 blocks said they
would be finished when the message went out. The phase-3 plan still read 2026-09-30 and
carried no as-of section, although M3's dates (2026-09-23 to 25) had passed. That last gap
is Issue #56 FR-7.3's M3 item.

The lead decided on 2026-10-03 that Issue #56 closes on this work, and that what it cannot
finish moves to two new issues: Issue #109 for the M3 and M4 residue, and Issue
#108 for PR #55's `poller.py` owner read.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | Appends `## Advisor loop reshaped, as-of 2026-10-03`, a process record covering the unsent cover, the 2026-09-29 replacement with a #84 link per file, the lead as approver, and why no date is re-dated. Also appends the register's first decision entry, Dr. Akba's in-person approval and his three-engine direction. |
| `docs/decisions.md` | Appends a dated as-of paragraph under each of this PR's 2026-09-14 status blocks for ADR-009 and ADR-011; neither `**Status**` line changes. |
| `docs/roadmap/2026-09-03-phase-3-plan.md` | Appends `## Reconciliation update · as-of 2026-10-03`: the milestone move with the lead's reason, the advisor-loop change, and one met-or-not row per M0 to M3 gate item with what settles it. |
| `docs/implementations/2026-09-14-circulation-and-m3-fallback.md` | Appends a dated pointer to this record, so a reader of the circulation plan learns it was superseded. |
| `docs/implementations/2026-10-03-advisor-loop-reshape-and-m3-as-of.md` | This record. |

## Implementation approach

**Everything is an append.** Every file touched is dated or append-only by its own header,
so each change is a new section or paragraph below the existing text. The 2026-09-14
sections are not yet on `main`, but they are still dated snapshots, so they are kept as
written and followed by an as-of paragraph. That follows this branch's own
`## Merge reconciliation, as-of 2026-09-29` precedent, and it keeps the history readable:
what was believed on 2026-09-14, then what changed.

**Process facts and decisions are kept apart.** The register's new
`## Advisor loop reshaped` section is explicitly not a decision entry: it records what
happened to the circulation. The decision follows it as its own entry, under the contract
the file states for every entry: the question, the answer, the date it was given, the
medium, and what it unblocks. It adds one field, **Approver**, because from this point an
entry's approver can be the lead rather than Dr. Akba. A reader must never have to infer
who approved.

**No fact was supplied by inference.** Every fact came either from live state or from the
lead's answers on 2026-10-03, and the scope of each statement is set by those sources:

- The meeting date is written as the range the lead gave (2026-09-29 to 2026-10-02), not a
  chosen day.
- Files 03 and 04 were posted on #84 after or close to the meeting (2026-10-03T14:53Z and
  2026-10-02T04:02Z; the meeting's day is unknown). For those two files the entry says the
  approval covers what was presented in person, not the posted text verbatim. The lead
  chose that wording when the timing was put to him.
- No `**Status**` line moves. Dr. Akba's approval is file-level; mapping it onto the
  outstanding register items and their ADRs is the lead's approval session, which is Issue
  #109's work, and each ADR still needs its own evidence first.
- The ADR-025 amendments are stated as **not** answered, because the lead confirmed on
  2026-10-03 that they were not discussed when Dr. Akba approved. An earlier draft of this
  amendment had inferred the opposite reading from the #84 posts (that approving Files 04
  and 06 approved routing the amendments to Dr. Akba). A fact-check pass found that the
  #84 text does not settle it, so the question was put to the lead and his answer replaced
  the inference before push.

**Each gate row in the plan's as-of section was measured, not remembered.** The sources
were: merge dates from `gh pr view`; issue states from `gh issue view`; ADR status lines
quoted from `docs/decisions.md`; the absence of `training/gradients.py`, `dataset.py` and
`anfis.py` from a listing of `src/superconducted/training/` at `110cfad`; the seven
membership-function shapes from `fuzzy/parameterization.py`; and the feature-survey TSV's
arrival on `main` from `git merge-base --is-ancestor cd32c88 125b796^1`, which is false
(`cd32c88` added that TSV on 2026-09-08), so it arrived with PR #68's merge on 2026-09-16
rather than on its commit date. The dashboard
row additionally rests on `calibration-health.yml`'s scheduled runs succeeding on
2026-10-02 and 2026-10-03.

**Issue numbers were filled at filing.** The two new issues were filed after the text was
written. The placeholders were replaced with their numbers before the commit was pushed,
and a grep for the placeholders is part of the verification below.

## Mathematical / Statistical details

N/A — purely structural. The only arithmetic is the plan section's tallies of its own
table rows: M0 has four of six items met, M1 four of five, M2 two of five and M3 one of
six. Each tally is a count of the rows directly above it.

## Design decisions

1. **Close #56 now, move the residue to one issue.** The alternatives were to keep #56 open
   until M4 or to scatter its residue across the tickets that own each dependency (#60,
   #61, #63, #84) plus a new one for the close record. The lead chose one residual issue:
   M3 and M4 depend on four unfinished tickets and a milestone a month out, and one place to
   look beats five.
2. **Amend #98 rather than replace it.** A fresh PR carrying only what is still true was
   the alternative. Amending keeps the FR-10.4 note, the NC-045 `\times` repair and their
   re-verification at the 2026-09-29 merge, and it keeps the 2026-09-14 sections as an
   honest record of the plan that was superseded.
3. **Record the process now, decide the items later.** The lead's 2026-09-29 ruling kept
   the team's decision content off the repository until the advisor's check returned. That
   check has now returned, as Dr. Akba's in-person approval, so on 2026-10-03 the lead chose
   to record it and the process change now. Per-item decisions and their ledger form still
   wait for his approval session.
4. **One register, not renamed.** Issue #56 FR-12 made
   `docs/advisor/2026-09-03-decisions-from-akba.md` the single location phase-3 tickets
   cite for an advisor decision. A second file for the
   lead's approvals would split the trail, and renaming would break every citation. The new
   section tells the reader how to read the title instead.
5. **Passed decision-by dates are not re-dated.** They dated an e-mail that was never sent.
   Moving them would date an ask nobody is making. Each item closes through a register entry
   instead.
6. **The plan's title and §5 targets stay.** The milestone move is recorded with the lead's
   reason, below the original text. §5 already says dates are the ambition and gates the
   artifacts, so the record reports gate state rather than re-targeting.
7. **A new implementation record, plus a pointer from the old one.** This branch's earlier
   history appended to the 2026-09-14 record. The global convention asks for a dated record
   per meaningful change, and PR #50 added three. A dated pointer in the 2026-09-14 record
   keeps a reader of either one from missing the other.

## Verification

No number originates here and no test is added, so the suite is unchanged by construction.
The gates still run, because the docs are read by tests and by `scripts/check_ids.py`.
These are provisional laptop runs (`C:\pvci`, CPython 3.12.10, `PYTHONPATH` set to this
tree's `src`). Canonical verification is batched on @BurakOztekin's desktop per
`docs/team.md`, and this amendment adds nothing to a batch.

```bash
# Append-only: no removed line in any file this amendment touches, against the PR tip
# it started from and against main.
git diff 0acb8e0 -- docs/ | grep -E '^-[^-]' ; echo "exit=$? (1 means none)"
git diff origin/main -- docs/advisor/ docs/roadmap/ docs/decisions.md \
  | grep -E '^-[^-]' ; echo "exit=$? (1 means none)"

# No unfilled placeholder; Bengisu's handle only ever as @bengisucvd.
grep -rn -E 'ISSUE_(RESIDUAL|BAHA)' docs/ ; echo "exit=$? (1 means none)"
grep -n -E '@bengis[u]([^c]|$)' $(git diff --name-only 0acb8e0 -- docs/) \
  ; echo "exit=$? (1 means none; docs/team.md's handle warning is deliberate and untouched)"

# The five gates.
python -m ruff check
python -m ruff format --check
python scripts/check_ids.py
python -m mypy --strict
python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider
python -m pytest tests/ -q -p no:cacheprovider
```

| Check | Result at `0acb8e0` (before) | Result after |
| --- | --- | --- |
| `ruff check` | `All checks passed!` | `All checks passed!` |
| `ruff format --check` | `68 files already formatted` | `68 files already formatted` |
| `scripts/check_ids.py` | no duplicate or colliding ids | no duplicate or colliding ids |
| `mypy --strict` | `Success: no issues found in 38 source files` | `Success: no issues found in 38 source files` |
| `pytest --collect-only` | 701 | 701, equal to NC-021 |
| `pytest` | 701 passed | 701 passed |

701 is NC-021's value, measured at `6630fca`. Only `docs/` changed between that commit and
`110cfad`, which is the `main` this branch last merged, so 701 still describes the tree.

## Related docs

- Issue #56: FR-2, FR-7.3, FR-12, FR-15, FR-16, and its closing comment
- Issue #84: the six files' team decisions
- Issues #109 (the M3 and M4 residue) and #108 (PR #55's owner read)
- `docs/advisor/2026-09-03-decisions-from-akba.md`
- `docs/roadmap/2026-09-03-phase-3-plan.md`, §5 and the 2026-10-03 as-of section
- `docs/implementations/2026-09-14-circulation-and-m3-fallback.md`, the circulation plan
  this record supersedes
- ADR-005, ADR-009, ADR-011 and ADR-025 in `docs/decisions.md`
