# 2026-10-16: record-yigit-departure

## Problem / Motivation

On 2026-10-16 Mert Efe Şensoy reported that Yiğit Arda Kaderoğlu (`@yigit-arda`)
has left the team. No leaving date was given. Later the same day Mert made him an
outside collaborator (no longer an organization member; `read` permission on this
repository) and asked for two things: remove his name from the team, and divide
his work among the other team members.

Before this change `docs/team.md` listed him in the roster and as primary owner of
four modules, so the default reviewer for those modules, and the PR template's
"Tag the module owner from `docs/team.md`" line, pointed at someone no longer on
the team. Four open issues and the #57 close plan also still gave him work. The
"Updating this file" section of `docs/team.md` names "A team member joins or
leaves" and "Module ownership shifts" as reasons to update it.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/team.md` | Removes him from the roster and gives his four modules to Bengisu, Baha Jarad, Mert Efe Şensoy and Burak Öztekin, with `benchmarks/circuits.py`'s secondary reviewer moving from Burak to Bengisu. |
| `docs/implementations/2026-10-16-record-yigit-departure.md` | This record: the split, the load it was balanced against, the inventory of his open work, and the GitHub changes made on Mert's word. |

The GitHub changes outside the repository are listed under "GitHub changes made
on Mert's word" below.

## Implementation approach

The change went in two steps on one branch, both on 2026-10-16:

1. **First commit (draft).** Moved him to a "Former contributors" table, marked
   his four module rows "Owner to be decided", and inventoried every open item that
   still gave him work (the table under "Open work found" below). Nothing was
   reassigned, because the split was Mert's decision.
2. **Second commit (the split).** Mert chose the split, the flip-PR author, the
   owner of the #62 bundle and how `docs/team.md` treats Yiğit, through four
   multiple-choice questions with the options and load numbers shown to him. This
   commit applies those answers.

`docs/team.md` after the second commit:

- **Roster.** His row is gone, and each person who gains a module has it added to
  their "Primary modules" cell.
- **No former-contributor entry.** Mert chose "name him nowhere" in `docs/team.md`,
  which matches the website's Team page and `CITATION.cff`. The dated docs, past
  issues and PRs, and this record still carry `@yigit-arda`, so old mentions stay
  traceable.
- **Module ownership.** Four primary cells change. Every secondary reviewer stays
  as it was except on `benchmarks/circuits.py`, where Burak was the secondary and is
  now the primary, so the secondary moves to Bengisu.

| Module | Primary before | Primary after | Secondary after | Reason |
| --- | --- | --- | --- | --- |
| `fuzzy/membership.py` | Yiğit Arda Kaderoğlu | Bengisu | Burak Öztekin (unchanged) | #61's `training/gradients.py` derives a gradient for each of the seven shapes in this module, dispatching from outside it, so any change to a shape's formula already needs her; 391 lines. |
| `fuzzy/parameterization.py` | Yiğit Arda Kaderoğlu | Baha Jarad | Burak Öztekin (unchanged) | Its grids are built from the archive distribution that his `calibration/features.py` produces; 754 lines. |
| `fuzzy/squashing.py` | Yiğit Arda Kaderoğlu | Mert Efe Şensoy | Bengisu (unchanged) | 57 lines implementing the `SquashingStrategy` ABC from `interfaces.py`, where Mert is the secondary reviewer. |
| `benchmarks/circuits.py` | Yiğit Arda Kaderoğlu | Burak Öztekin | Bengisu (was Burak Öztekin) | His `benchmarks/harness.py` runs every circuit this module builds; 93 lines. Bengisu certifies the benchmark instruments in #58. |

Work items (Mert's choices):

| Item | Before | After |
| --- | --- | --- |
| #84 and the #57 close plan's step 4: the ADR-027 flip PR, due 2026-10-23 | Yiğit writes, Mert approves | Mert writes, @bengisucvd approves (step 5, by 2026-10-26). The ruleset bars self-approval, so the approver had to change when the author did. |
| #62, the ADR-019 ablation | Yiğit | @BahaJarad, together with #61 decision 2 (agree the footprint-ratio set with @bengisucvd) and #60's M4 hand-off and comparison document. The three share one script, `scripts/mf_ablation.py`, which does not exist on `main` yet. |
| `plan.json` on the `phase-3-dashboard` branch | Yiğit owns #84, #62 and part of M4 | Updated to match, in this session (see below). |

## Mathematical / Statistical details

N/A, purely structural. The load figures are counts, defined here so they can be
re-run:

- **Primary modules** and **secondary reviews**: of the 20 rows in the "Module
  ownership" table of `docs/team.md`, the number whose primary (or secondary) cell
  contains the person's name. `fuzzy/tsk.py`'s "Mert Efe Şensoy + Bengisu" counts
  once for each; Dr. Akba's three rows count for him only.
- **Open issues**: open issues listing the person as an assignee, from
  `gh issue list --state open --json assignees`; an issue with two assignees
  counts once for each.

| Person | Primary modules before / after | Secondary reviews before / after | Open issues on 2026-10-16, before the reassignments |
| --- | --- | --- | --- |
| Mert Efe Şensoy | 1 / 2 | 10 / 10 | 5 (#57, #93, #104, #109, #110) |
| Burak Öztekin | 5 / 6 | 6 / 5 | 4 (#57, #60, #65, #75) |
| Baha Jarad | 3 / 4 | 0 / 0 | 3 (#63, #93, #108) |
| Bengisu | 3 / 4 | 4 / 5 | 6 (#58, #61, #64, #75, #76, #92) |

The reassignments then add #84 to Mert (6) and #62 to Baha (4). Module sizes are
`wc -l` of each file at `origin/main` `89e01451`.

## Open work found (inventory before the split)

This is the first commit's inventory, kept as found. The "After" column of the
work-items table above says where each row went.

| # | Where | What it gave him |
| --- | --- | --- |
| 1 | [Issue #84](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84) | Sole assignee. Body "Owner" row: "@yigit-arda (substance and brief) · @mertefesensoy (sends it, per FR-15)". §6 is the ADR-027 flip PR. |
| 2 | [Issue #62](https://github.com/SuperconducTED/superconducted-noise-engine/issues/62) | Sole assignee: owner of the ADR-019 ablation script and its tests, and its runner. |
| 3 | [#57 close plan, comment 6140571135](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57#issuecomment-6140571135) | Decision D and step 4: author of the ADR-027 flip PR, due 2026-10-23. Steps 5 and 6 wait on that PR. |
| 4 | [Issue #60, comment 5526538935](https://github.com/SuperconducTED/superconducted-noise-engine/issues/60#issuecomment-5526538935) | Unticked box "Model JSON handed to @yigit-arda and loaded by `scripts/mf_ablation.py --rule-base` without modification"; the M4 comparison is "his document". |
| 5 | [Issue #61](https://github.com/SuperconducTED/superconducted-noise-engine/issues/61) body, decision 2 | "@yigit-arda and @bengisucvd agree the set" of footprint ratios. |
| 6 | [Issue #84, comment 5970300012](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84#issuecomment-5970300012) | Bengisu's proposal to revisit #59 decision 3, addressed to him as owner of `parameterization.py`; it now reaches Baha as that module's owner. |
| 7 | [Issue #84, comment 5885404218](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84#issuecomment-5885404218) | A request for objections on #62, not a deliverable. |
| 8 | `phase-3-dashboard` at `6d68e328` | `plan.json`: owner of tickets #84, #59 and #62 and among the owners of milestones M1, M2 and M4; `generate.py` has his handle in three person-order lists; `README.md:39` gave him "Start #84". |
| 9 | `docs/roadmap/2026-09-03-phase-3-plan.md` | The dated plan gives him #59, #62 and the M4 comparison. |

Found with: `git grep -niE "yiğit|yigit|kaderoğlu|kaderoglu"` over the tree (a
bracket class such as `yi[gğ]it` must not be used: `ğ` is two bytes in UTF-8, the
class matches one byte, and it silently misses every "Yiğit"); `gh issue list
--assignee yigit-arda`; `gh pr list --author`, `--assignee` and `--search
"review-requested:yigit-arda"`; the `requested_reviewers` of every open PR; `gh
issue list --search "involves:yigit-arda" --state open`, with the body and every
comment of each hit read in context; and `git grep` on `origin/phase-3-dashboard`.

Checked and found nothing open: no open PR authored by or assigned to him, no
pending review request, no branch on `origin` whose tip commit he authored, and no
mention in `.github/`, `scripts/`, `src/` or `tests/`. #5, #23 and #59 are closed
and still list him as assignee, which is history and was left alone. Not checked:
GitHub Projects boards, because the `gh` token lacks the `read:project` scope.

## GitHub changes made on Mert's word

Mert ticked each of these individually on 2026-10-16. Nothing else on GitHub was
changed.

- To be filled in as each change is made.

## Design decisions

- **Split by fit and size, not "promote the secondaries".** Promoting every
  secondary reviewer is the smallest table edit, but it takes Burak from 5 primary
  modules to 8 and still needs three new secondaries. The chosen split gives the
  two large modules to the people whose work already depends on them (Bengisu's
  #61 gradients mirror every shape in `membership.py`; Baha's archive features feed
  `parameterization.py`) and the two small ones to where they add the least load.
  The option shown to Mert said #61's gradients "edit" all seven shapes; they do
  not (#61 deliberately dispatches from outside the module), and the corrected
  wording is the one above.
- **Mert writes the flip PR, Bengisu approves.** Mert already holds the step-3
  register entries and wrote every correction in the close plan, and Bengisu reads
  ADR-027 for step 2 by 2026-10-20. The alternatives (Bengisu or Burak writing,
  Mert approving) kept step 5 unchanged but added a docs PR to someone already
  carrying more open work.
- **Baha takes the #62 bundle.** He had the lightest load (3 open issues, no
  secondary reviews) and now owns `parameterization.py`, whose `grid_partition`
  supplies the ablation's grids. Bengisu would have been the natural second choice
  but carries the most open issues; Burak would have held both ends of the #60 to
  #62 model hand-off, leaving nobody else to check it.
- **The three #62 items move together.** #62, #61 decision 2 and #60's M4 hand-off
  all meet in `scripts/mf_ablation.py`, so splitting them would put one script under
  several owners.
- **Name him nowhere in `docs/team.md`.** This is Mert's reading of "remove his
  name from the team". The alternative, a one-line former-contributor note, was
  offered and not chosen; this record is where the handle now resolves.
- **Not edited, on purpose:** the dated docs (`docs/roadmap/2026-09-03-phase-3-plan.md`,
  `docs/advisor/2026-09-03-decisions-from-akba.md` and the 2026-09 implementation
  records that mention him), because dated docs are append-only ("Documentation
  conventions" in `docs/team.md`) and the mentions are history; the bodies of
  issues #57, #60, #61, #62 and #84 and Mert's 2026-10-13 plan comment, which are
  amended by new comments rather than rewritten.

## Verification

Run from the repository root on this branch:

- `grep -ciE "yiğit|yigit|kaderoğlu" docs/team.md` returns 0.
- `grep -nE "membership.py|parameterization.py|squashing.py|circuits.py" docs/team.md`
  shows the four roster cells and the four ownership rows with the owners in the
  table above.
- `git diff origin/main --stat` shows only `docs/team.md` and this record.
- `git ls-files --eol docs/team.md` still reports `i/lf w/lf`.
- `git diff origin/main -U0 -- docs/team.md | grep "^+" | grep -c $'\xe2\x80\x94'`
  returns 0 in Git Bash: the change adds no em dash (U+2014, written as its UTF-8
  bytes); the file's existing ones are untouched.
- The load counts: run the row count described under "Mathematical / Statistical
  details" against `git show origin/main:docs/team.md` and against the working
  copy; the two runs give the "before" and "after" columns.

No test or script parses `docs/team.md` (`git grep -n "team.md" -- tests scripts
.github` finds only prose references), so there is no suite to run for this change.

## Related docs

- `docs/team.md`, sections "Roster", "Module ownership", "How ownership works" and
  "Updating this file"
- `.github/pull_request_template.md` ("Tag the module owner from `docs/team.md`")
- `docs/roadmap/2026-09-03-phase-3-plan.md`
- Issues [#57](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57),
  [#60](https://github.com/SuperconducTED/superconducted-noise-engine/issues/60),
  [#61](https://github.com/SuperconducTED/superconducted-noise-engine/issues/61),
  [#62](https://github.com/SuperconducTED/superconducted-noise-engine/issues/62),
  [#84](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84)
