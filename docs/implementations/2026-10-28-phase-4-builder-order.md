# 2026-10-28: the phase-4 builder-mode order (plan section 8 and the team timeline)

## Problem / Motivation

The phase-4 evidence stack merged on 2026-10-26 to 2026-10-28 (PRs #120, #121, #123, #124, #126,
#127, #128). The plan of 2026-10-23 described lanes and gates but its "this week" table (section
5) and the 2026-10-24 merge order were spent; the lead asked, in builder mode, what is ahead. The
plan is a dated document, so the answer is a dated as-of section appended to it, not an edit of
its lanes, plus a step-by-step timeline the team can read without the repository's context (the
form that landed well on 2026-10-24).

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-23-phase-4-plan.md` | Section 8 appended: what phase 4 holds and lacks, the decisions since 5.1, the build order in six blocks with owners and gates, the weeks as targets, and what the section does not change. |
| `docs/roadmap/2026-10-28-phase-4-builder-timeline/index.html` | New: a self-contained HTML timeline of the same order (inline CSS, light and dark, phone width), owner chips, "now" against "waits", one plain reason per step, the weeks table, a Türkçe özet. |
| `docs/implementations/2026-10-28-phase-4-builder-order.md` | This record. |

No source, test, register or evidence file changed.

## Implementation approach

The order was derived from live state read on 2026-10-28 (`main` `695c90ca`; the open PR list,
the two milestones' issue lists, #125's and #110's threads, the branches touched since
2026-10-26, the phase-4 dashboard record of 2026-10-27) and from the lead's decisions of 2026-10-26
(the offline half is his first; the neural model and the fuzzy system start in parallel; the team
reproduces at the end) and the statistics review's conclusion on the pattern detector. Six blocks:
the hardware test as the critical path to L1 and L2; the per-qubit channel that opens at L1; the
fuzzy system and the paper to L3 and L4; the neural model behind L1 and behind unseen data; the
overdue phase-3 housekeeping to L5; verification on Burak's desktop. The weeks table gives one
thing per person per week; dates are targets, as the plan's section 6 requires.

The timeline is plain HTML so that it travels as one file (the advisor-brief convention) and
renders on GitHub's preview tools without a build step.

## Mathematical / Statistical details

N/A, purely structural.

## Design decisions

- **Append, do not rewrite.** Sections 1 to 7 and 5.1 stay; section 8 says what changed since them.
- **The neural model stays behind two gates.** The review's conclusion that a miscalibrated null
  establishes no need for a network is adopted as plan text; N2 waits for L1 and for an unseen
  evaluation clearing the strengthened rule.
- **Ownership note.** The lead's taking of the offline half is recorded here as the dated note the
  design's and the pre-registration's ownership rows owed.
- **Overdue is said plainly.** The phase-3 milestone's date passed; the section lists the eight
  issues and the one PR that stand between the team and L5.

## Verification

- The HTML has no external resource and no script; open it in a browser or on GitHub's rendered
  view; it reads at 375 px width without horizontal scroll.
- No em dash in the three files (Python count of `chr(0x2014)` returns 0).
- Issue and PR states quoted in section 8 are those of 2026-10-28 and can be re-read with
  `gh issue list --milestone "Phase 4 · Design-time predictor" --state all` and
  `gh pr list --state open`.

## Related docs

- `docs/roadmap/2026-10-23-phase-4-plan.md` (sections 1 to 8)
- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md`
- `docs/evidence/pattern-detector/README.md` section 12
- Issues #125, #110, #122, #130, #64, #60, #61, #62, #75; PR #111
