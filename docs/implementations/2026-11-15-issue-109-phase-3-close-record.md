# 2026-11-15: issue-109-phase-3-close-record

The plan is written first; the results are appended below it in later commits. Docs only: nothing
under `src`, `scripts` or `tests` changes.

## Problem / Motivation

Issue #109 carries the residue of Issue #56: the ADR-025 answers, the register entries, the ADR
flips, and the phase-3 close record (M4). The phase-4 plan (`docs/roadmap/2026-10-23-phase-4-plan.md`,
lane 3) scopes it as "the register entries, the phase-3 close record; the ADR-025 amendments answered
or explicitly carried", and gate L5 closes phase 3 when every milestone-1 issue is done or moved to
phase 4 with a reason. Three of #109's items (the ADR-009 and ADR-011 flips, the ADR-014 approval and
the floor comparison at #63's ref) wait on phase-4 tickets (#60, #61, #62, #63), so #109 cannot finish
inside phase 3. This PR delivers what can be done now. After it merges, #109 moves to the phase-4
milestone carrying the rest.

## Decisions this PR records (@mertefesensoy, 2026-11-15, in this session's question dialogs)

1. **Dr. Akba's delegation extends to the pipeline ADRs.** Asked on what basis his answers to the
   ADR-025 amendments go into the register, given `docs/team.md`'s rule that changes touching ADR
   ledger semantics need Dr. Akba's out-of-band sign-off and that the 2026-10-21 delegation covers only
   the two fuzzy engines, the lead answered: Dr. Akba extended the delegation. Scope, as chosen: every
   ADR about the calibration pipeline and the `calibration-data` branch (ADR-020 and ADR-025, with their
   amendments). Date: given together with the 2026-10-21 fuzzy-engine delegation; the exact day was not
   recorded. Medium: in person. #57's comment 6140571135, where the fuzzy-engine delegation was first
   stated, names only the fuzzy engines, so this extension is first stated on the record here.
2. **Register items 2 and 14 accepted**, item 14 with File 06's corrected wording (Issue #84,
   comment 5885407524, section 1): a distinct `qubit_digest` is a device state, and a row of
   `health/state-index.tsv` is one filed snapshot path.
3. **The 2026-09-17 heartbeat amendment and the 2026-09-29 capture amendment accepted as written.**
   They have no register items yet and get items 16 and 17 here.
4. **#109 moves to the phase-4 milestone** once the close record merges, carrying the ADR-009 and
   ADR-011 flips, the ADR-014 approval, the floor comparison at #63's ref, the remaining register
   entries, and File 06's follow-up parts 2 and 3.

## What changed (planned)

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | The delegation-extension entry; items 16 and 17 added; one decision entry each for items 2, 14, 16 and 17, each naming the extension. |
| `docs/decisions.md` | Inside ADR-025: the fifth amendment (File 06's primary/derived rule, Q3's rebuild rule and the corrected state wording), and a dated status note pointing at the four register entries. |
| `docs/state-of-the-project/2026-11-15-phase-3-close.md` | The phase-3 close record: one row per M-gate item citing the plan, the milestone's issues, and every carried item with its phase-4 ticket and reason. |
| `docs/roadmap/2026-09-03-phase-3-plan.md` | The M4 as-of section, appended, pointing at the close record. |
| This file | The plan, then the results. |

## Implementation approach

Every edit is an append. The register gains entries below its last one. ADR-025's existing text,
including its 2026-09-10 status note ("Its status is Open"), stays exactly as written: that note says
it is "removed only by appending the answer to the decisions register", so the new status note says
where the answer now is and leaves the old one standing. The phase-3 plan gains one section after its
2026-10-03 reconciliation. The close record is a new file.

Each register entry follows the 2026-10-21 entries' form (Question, Answer, Approver, Date given,
Medium, Unblocks) and names the delegation it rests on, the decision, and the ADR it lands in, as
#109's box 2 asks.

## Mathematical / Statistical details

N/A: records only. The close record cites counts already in the register (NC-045, NC-047) and
counts of gate items in its own table; it introduces no new measured figure.

## Design decisions

- **Item 14's answer covers File 06's three questions.** Item 14 asks the three questions of File 06's
  brief; File 06's team decision answers all three (Q1 the state, Q2 the one rule for the branch, Q3
  `is_new_state` as an observation). The entry records the answer as File 06 states it. The fifth
  amendment writes Q1's wording and Q2's rule into ADR-025, plus Q3's rebuild limit, because Q2's rule
  for derived views and Q3's limit on `--rebuild` are one rule about `health/`. The PR description
  points at Q3's sentence so a reviewer can strike it.
- **File 06 part 1 lands here; parts 2 and 3 are carried.** Part 1 is the amendment above. Part 2 (a
  merge counter in `health/metrics.json`) is code, and part 3 (NC-060's dependency on the stripped state
  definition) edits the NC-060 row that open PR #152 also edits; both go with #109 to phase 4.
- **Items 16 and 17 are new numbers.** The register's last number is 15, and no open PR touches the file
  (checked on 2026-11-15 against PRs #140 to #156).
- **No ADR `**Status**` line changes.** ADR-025's top line reads `Accepted.`; what was Open is the
  2026-09-05 amendment's ratification, and that is what the new status note answers.

## Verification

```bash
python scripts/check_ids.py
git diff --stat origin/main -- src scripts tests          # empty
git diff origin/main -- docs/decisions.md docs/advisor docs/roadmap | grep -c '^-[^-]'   # 0: appends only
```

## Related docs

- Issue #109 (its body and the 2026-11-09 File 06 comment), Issue #84 comment 5885407524 (File 06),
  Issue #57 comment 6140571135, Issue #56.
- `docs/advisor/2026-09-03-decisions-from-akba.md`, ADR-025 in `docs/decisions.md`,
  `docs/roadmap/2026-09-03-phase-3-plan.md`, `docs/roadmap/2026-10-23-phase-4-plan.md`, `docs/team.md`.

## Results, 2026-11-15

The sections above are left as written at `d7415002`.

| Commit | What it holds |
| --- | --- |
| `d7415002` | This plan, before anything below. |
| `ec8bf85d` | The register: items 16 and 17 added; the delegation-extension entry; items 2, 14, 16 and 17 answered under it. |
| `ff103ef6` | ADR-025: the 2026-11-15 amendment (File 06's Q1 wording, Q2 rule and Q3 rebuild limit) and the status note for the four amendments. |
| `65c7eb7f` | `docs/state-of-the-project/2026-11-15-phase-3-close.md`. |
| `32ba26a2` | The phase-3 plan's M4 as-of section. |
| the next commit | This section. |

**What the close record found**, read against `main` @ `667972c5` and GitHub on 2026-11-15:

- **Exit criteria:** three of the plan's eight met, one partly.
- **Gates:** M0 five of six (counting the ADR-025 row this PR lands), M1 five of five, M2 two of five
  with one partly, M3 two of six, M4 one of four.
- **The milestone:** five of its fourteen issues open, and four open PRs.
- **Record gaps:** #65 and #76 carry no milestone, although #109's body calls them phase 4; none of
  the 15 checkboxes in #63's body is ticked, although PR #113 delivered its builder. The M2 row
  "trainer LSE stage passing on synthetic and anchored-baseline data" is met only on synthetic data
  (`tests/test_anfis.py`): a search of `tests/`, `scripts/`, `src/` and `docs/` for "anchored" finds no
  anchored-baseline run, only `training/anfis.py`'s advice to warm-start from one.
- **Re-read for this record** rather than carried from older text: the closing dates of #25, #45 and #53,
  PR #81 closing #25, every PR merge date cited, and #63's checkboxes. The first draft said "#63 stays
  open for one unticked ask", which came from the phase-4 dashboard's summary; the body has 15 unticked.
- **Trial merges** (`git merge-tree`) against the heads of PR #145 and PR #150, which also append to
  `docs/decisions.md`: both clean.

**Confirmed by the lead before the push** (2026-11-15, in this session's dialog):

- The delegation entry's Answer, Date given, Medium and "Against the 2026-10-21 entry" rows were shown
  to @mertefesensoy verbatim, and he approved them as written.
- Asked separately whether Q3 belongs in item 14's answer and the amendment, he chose to keep it. Q3
  replaces the 2026-09-05 rule that `--rebuild` may regenerate the index once, as the only permitted
  rewrite. The amendment's Q3 paragraph now quotes File 06 word for word and names the sentence it
  replaces.

**Checks:**

- Nothing under `src`, `scripts` or `tests` changed (`git diff --stat origin/main -- src scripts tests`
  is empty).
- The branch diff removes no line (`git diff origin/main | grep -c '^-[^-]'` is 0), so every edit is
  an append or a new file.
- `scripts/check_ids.py`: no duplicate or colliding identifiers. `tests/test_check_ids.py`, the one test
  that reads `docs/decisions.md`: 22 passed.
- `ruff check .` and `ruff format --check .` (0.15.12) are clean.
- No em dash added: `docs/decisions.md` has 76 on `main` and 76 here, and the phase-3 plan 2 and 2, all
  in text above the appended sections.
- NC-021 is not touched, since no test changed; the full suite was not run (CI runs it).

**Not done here, on purpose** (each needs the lead's word after merge): the PR #55 comment referencing
item 2's entry, ticking #109's box 3, and moving #109 to the phase-4 milestone with a dated comment
listing what it carries.
