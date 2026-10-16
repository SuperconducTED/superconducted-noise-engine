# 2026-10-16: record-yigit-departure

## Problem / Motivation

On 2026-10-16 Mert Efe Şensoy reported that Yiğit Arda Kaderoğlu (`@yigit-arda`)
has left the team. No leaving date was given. `docs/team.md` still listed him in
the current roster and as primary owner of four modules, so the default reviewer
for a PR touching those modules, and the PR template's "Tag the module owner from
`docs/team.md`" line, pointed at someone who is no longer on the team. Issues and
plans also still assign him work. The "Updating this file" section of
`docs/team.md` names "A team member joins or leaves" as a reason to update it.

Scope: record the departure without reassigning anything. Who owns his modules,
who takes over his issues and how the #57 close plan changes are the team's
decisions, so this change only names the open assignments (see "Open assignments
at 2026-10-16" below) and leaves them as they are.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/team.md` | Removes him from the roster, adds a "Former contributors" table, marks his four module rows "Owner to be decided (since 2026-10-16)" and adds a NOTE pointing those rows at the existing stand-in rule. |
| `docs/implementations/2026-10-16-record-yigit-departure.md` | This record, including the inventory of work still assigned to him. |

## Implementation approach

`docs/team.md`:

1. **Roster.** His row is removed from the current roster table.
2. **Former contributors.** A new `### Former contributors` table under the
   roster keeps his name, handle, role and the four modules he owned, with the
   departure stated as "reported by Mert Efe Şensoy on 2026-10-16 (leaving date
   not recorded)". One paragraph below it says that earlier issues, PRs and dated
   docs naming `@yigit-arda` describe the state when they were written and are not
   rewritten.
3. **Module ownership.** He was primary owner on exactly four rows and secondary
   reviewer on none: `fuzzy/membership.py`, `fuzzy/parameterization.py`,
   `fuzzy/squashing.py` and `benchmarks/circuits.py`. Their primary owner cell now
   reads "Owner to be decided (since 2026-10-16)". The secondary reviewer cells
   (Burak Öztekin, Burak Öztekin, Bengisu, Burak Öztekin) are unchanged.
4. **NOTE under the ownership table.** It names the four rows, states that this is
   not a reassignment, and points to the standing rule in "How ownership works"
   ("Secondary reviewer stands in when the primary owner is unavailable"): until
   the team names an owner, a PR touching one of these files, or its tests, requests
   that module's secondary reviewer, and the PR template's "Tag the module owner"
   line resolves the same way.

Inventory method (for the list below):

- `git grep -niE "yiğit|yigit|kaderoğlu|kaderoglu" -- docs .github scripts`, and the
  same pattern over the rest of the tree. A bracket class such as `yi[gğ]it` must
  not be used: `ğ` is two bytes in UTF-8, the class matches one byte, and the
  pattern silently misses every "Yiğit" (it found 1 line of `docs/team.md` instead
  of 5 on the first try).
- `gh issue list --assignee yigit-arda`, `gh pr list --author/--assignee yigit-arda`,
  `gh pr list --search "review-requested:yigit-arda"`, the `requested_reviewers` of
  every open PR from `gh api repos/.../pulls?state=open`, and
  `gh issue list --search "involves:yigit-arda" --state open`.
- The body and every comment of each open issue or PR that involves him (#57,
  #58, #60, #61, #62, #84, #79), searched for his name and read in context.
- The #57 close plan,
  [comment 6140571135](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57#issuecomment-6140571135)
  (2026-10-13).
- `git grep` on `origin/phase-3-dashboard` (tip `6d68e328`), and
  `gh api repos/.../collaborators/yigit-arda/permission` plus the org membership
  endpoint for access.

## Open assignments at 2026-10-16

Recorded for the team to decide on. Nothing in this table was edited.

| # | Where | What it gives him | Depends on it |
| --- | --- | --- | --- |
| 1 | [Issue #84](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84) | Sole assignee. Body "Owner" row: "@yigit-arda (substance and brief) · @mertefesensoy (sends it, per FR-15)". §6 is the ADR-027 flip PR. | Rows 3 and 6 below. |
| 2 | [Issue #62](https://github.com/SuperconducTED/superconducted-noise-engine/issues/62) | Sole assignee. Body "Owner" row: owner of the ADR-019 ablation script and its tests; the use-case diagram names him as the runner. | ADR-019 closure; ADR-009's T1-vs-IT2 rows; #60's FR-17 memo reads #62's "Evidence for ADR-009" section. |
| 3 | [#57 close plan, comment 6140571135](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57#issuecomment-6140571135) | Decision D and step 4: he authors the ADR-027 flip PR under #84 §6, with the plan's corrections, due 2026-10-23. | Step 5 (Mert's review and approval, 2026-10-26) and step 6 (closing #57, 2026-10-27) both wait on that PR. Step 3's four register entries "enter the file only through step 4's PR". |
| 4 | [Issue #60, comment 5526538935](https://github.com/SuperconducTED/superconducted-noise-engine/issues/60#issuecomment-5526538935) (the continuation of the body) | Unticked definition-of-done box "Model JSON handed to @yigit-arda and loaded by `scripts/mf_ablation.py --rule-base` without modification". Step 10 and the summary call the M4 comparison "his document". The body's use-case diagram names "Ablation / M4 script (Yigit)". | The M4 trained-model comparison on the four benchmark circuits. |
| 5 | [Issue #61](https://github.com/SuperconducTED/superconducted-noise-engine/issues/61) body, decision 2 | "@yigit-arda and @bengisucvd agree the set" of footprint ratios, so #62's IT2 candidate and #61's measurement share a grid. No #61 comment names him. | #61 PR-A; #62's IT2 candidate. |
| 6 | [Issue #84, comment 5970300012](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84#issuecomment-5970300012) (Bengisu, 2026-10-03) | Her recommendation to revisit #59 decision 3 (band scale from `s_q` to the drift scale) is addressed to him as owner of `parameterization.py`, together with the #62 rows. | Whether #59 decision 3 is revisited. |
| 7 | [Issue #84, comment 5885404218](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84#issuecomment-5885404218) (Mert, 2026-09-29) | Asks him (for #62) to say if a decision there lands wrong on his side. A request for objections, not a deliverable. | None. |
| 8 | `phase-3-dashboard` branch at `6d68e328` | `plan.json` makes him owner of tickets #84 (co-owner Mert), #59 and #62, and lists him among the owners of milestones M1, M2 and M4. `generate.py` has `"yigit-arda"` in three person-order lists (lines 821, 883, 1158) and a comment at line 652; `README.md:39` gives him the next action "Start #84". | The rendered status page. |
| 9 | `docs/roadmap/2026-09-03-phase-3-plan.md` | The dated phase-3 plan gives him #59, #62 and the W4 M4 comparison, and names him in the M1, M2 and M4 milestone rows and the mermaid ticket colours. | Dated, append-only: any reconciliation is an appended as-of section. |

Access, which is a decision rather than an assignment: on 2026-10-16 `@yigit-arda`
is still a repository collaborator with `write` permission and a member of the
SuperconducTED organization.

Checked and found nothing open:

- No open PR authored by or assigned to him, and no pending review request on any of
  the four open PRs (#79, #111, #113, #115).
- No branch on `origin` whose tip commit he authored.
- No mention in `.github/`, `scripts/`, `src/` or `tests/`.
- #59 is closed (completed 2026-09-16); #5 and #23 are also closed. All three are
  still assigned to him, which does no harm on a closed issue.
- Historical only, already discharged: his #58 confirmations of items 7 and 8, the
  `D_R2` orientation and the every-defined-cell quantifier (2026-09-06); the
  approvals recorded in PR #79's body; the File 06 row of
  `docs/advisor/2026-09-03-decisions-from-akba.md` (answered by him, then by Mert);
  and four implementation records:
  `docs/implementations/2026-09-06-issue-58-decisions-and-r2-orientation.md`,
  `docs/implementations/2026-09-08-mf-parameterization.md`,
  `docs/implementations/2026-09-14-recover-pr68-approved-tip.md` and
  `docs/implementations/2026-09-15-pr68-m2-mapping-and-coverage.md`.

Not checked: GitHub Projects boards, because the `gh` token lacks the
`read:project` scope; and the organization's `.github` repository (profile README,
website), which is outside this repository.

## Mathematical / Statistical details

N/A, purely structural.

## Design decisions

- **"Owner to be decided", not a new name.** Ownership routes reviews and is the
  team's decision. Writing a name, even a provisional one, would be a reassignment
  made in a docs PR.
- **The NOTE applies an existing rule; it is not a reassignment.** Without it, a
  reader following "the primary owner is the default reviewer" finds an empty cell
  and no instruction. The stand-in rule already says what happens when a primary
  owner is unavailable, so the NOTE only points to it. If the team reads this as
  choosing a reviewer, drop the NOTE and the four rows still read "Owner to be
  decided".
- **Keep the handle in "Former contributors".** Dated docs, issues and PRs cite
  `@yigit-arda` as owner, author and approver. Removing him from the file entirely
  would leave those records with no way to resolve who he was or what he owned.
  Keeping him in the current roster with a flag was rejected because readers use
  that table to pick reviewers.
- **"Reported on 2026-10-16", not "left on 2026-10-16".** Mert gave the report
  date, not a leaving date, and the record does not invent one.
- **Not edited, on purpose:**
  - the dated docs in the inventory (`docs/roadmap/2026-09-03-phase-3-plan.md`,
    `docs/advisor/2026-09-03-decisions-from-akba.md` and the four 2026-09
    implementation records), because dated docs are append-only
    ("Documentation conventions" in `docs/team.md`) and the mentions are history;
  - issues #62 and #84, the #57 close plan and the other issue text, because who
    takes over and how #57 is re-planned are the team's decisions;
  - the `phase-3-dashboard` branch, which its refresh routine maintains from live
    GitHub state and which is outside this change;
  - his repository and organization access, which is the owner's call.

## Verification

Run from the repository root on this branch:

- Before the commit, `git status --short` shows only ` M docs/team.md` and
  `?? docs/implementations/2026-10-16-record-yigit-departure.md`; after it,
  `git diff origin/main --stat` shows only those two files.
- `git ls-files --eol docs/team.md` still reports `i/lf w/lf`, so the edit kept
  the file's line endings.
- `git grep -n "yigit-arda" docs/team.md` returns two lines, both in "Former
  contributors" (the table row and the paragraph under it).
- `grep -c "Yiğit Arda Kaderoğlu" docs/team.md` returns 1 (the former-contributor
  row).
- `grep -c "| Owner to be decided (since 2026-10-16) |" docs/team.md` returns 4.
- `git diff origin/main -U0 -- docs/team.md | grep "^+" | grep -c $'\xe2\x80\x94'`
  returns 0 in Git Bash: the change adds no em dash (U+2014, written as its UTF-8
  bytes), and the file's existing ones are untouched.

No test or script parses `docs/team.md` (`git grep -n "team.md" -- tests scripts
.github` finds only prose references), so there is no suite to run for this change.

## Related docs

- `docs/team.md`, sections "Former contributors", "Module ownership", "How
  ownership works" and "Updating this file"
- `.github/pull_request_template.md` ("Tag the module owner from `docs/team.md`")
- `docs/roadmap/2026-09-03-phase-3-plan.md`
- Issues [#57](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57),
  [#60](https://github.com/SuperconducTED/superconducted-noise-engine/issues/60),
  [#61](https://github.com/SuperconducTED/superconducted-noise-engine/issues/61),
  [#62](https://github.com/SuperconducTED/superconducted-noise-engine/issues/62),
  [#84](https://github.com/SuperconducTED/superconducted-noise-engine/issues/84)
