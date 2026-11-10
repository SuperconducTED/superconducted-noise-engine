# 2026-10-05: the meeting deck for Dr. Akba

## Problem / Motivation

Dr. Akba asked the lead to meet on 2026-10-05 and to show, visually:

- how all three engines' pipelines work;
- for the deep-learning engine, why the proposed architecture was proposed, the method
  chosen, and the alternatives examined.

He wanted to discuss the pipeline the team will build. The plan and the research (PR #111)
held the content but not in a form for a meeting. The lead asked for a slide deck in English
and Turkish, presenting both deep-engine designs for Dr. Akba to choose: the decided plan
(Option A) and the research recommendation (Option B, not adopted).

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-10-05-akba-meeting-deck/README.md` | What the deck is, where its facts come from, and where the answers it asks for get recorded. |
| `docs/advisor/2026-10-05-akba-meeting-deck/en/deck.json`, `en/slides/*.html` | The English deck as published: index plus 18 slides. |
| `docs/advisor/2026-10-05-akba-meeting-deck/tr/deck.json`, `tr/slides/*.html` | The Turkish deck as published: index plus 18 slides. |
| `docs/implementations/2026-10-05-akba-meeting-deck.md` | This record. |

## Implementation approach

**One brief, disjoint builders.** The lead's assistant wrote a single brief: the audience,
a visual system (fonts, palette, type scale, templates, one colour per engine), the only
facts and numbers allowed, each with its source, a slide-by-slide specification and a
Turkish glossary.

A read-only agent first produced a code-verified fact sheet of the fuzzy pipelines, with
file and line references. Its load-bearing claims were then spot-checked in the source:

- the product t-norm;
- the shipped Nie-Tan formula;
- that no Karnik-Mendel code exists;
- which gates receive the channel;
- that the harness does not transpile.

Five builder agents then each wrote a disjoint set of slides in both languages, so no two
agents touched the same file.

**Two reviews, then fixes, then measurement.** A facts-and-parity reviewer checked every
claim against the brief and code facts, decided-versus-recommended labelling, English and
Turkish parity, and Turkish quality (36 findings). A format-and-layout reviewer checked the
Slides subset and measured every slide rendered with the real fonts (16 findings).

Five fixer agents applied the findings, again on disjoint file sets. The lead's assistant
then re-ran the static subset check over all 36 files and a headless-Chrome measurement of
every slide, and fixed the last two problems it found: a wrapping footer, and an
over-full box in the Turkish Option B diagram.

**Late correction from review.** @BurakOztekin's commit `8d7965e` on PR #111 changed two
research verdicts from "Adopt for version 1" to "Recommended for version-1 evaluation".
The deck's alternatives slide was aligned to it before this commit ("Linear on lags":
"first version" became "recommended (Option B, v1)").

## Mathematical / Statistical details

N/A — purely structural. The deck restates formulas recorded in the plan, the research
document and ADR-027; it derives nothing new.

## Design decisions

1. **Both deep-engine designs, labelled.** Option A is shown as "Decided (A1 to A8)" and
   Option B as "Recommended, not adopted", because the lead kept A1 to A6 as written until
   this meeting.
2. **Two decks, not a language toggle.** The Slides format allows no scripts, so a TR/EN
   switch was impossible inside one deck. The lead chose two separate decks.
3. **No speaker notes.** The slides had to stand on their own for Dr. Akba.
4. **Protocol pills.** The time split, metrics and Wilcoxon test are labelled "Approved as
   presented", because they come from the File 02 and File 05 decisions Dr. Akba approved
   as presented. The horizon stays "Planned".
5. **30px card titles on the dense diagram slides**, kept as a deliberate exception to the
   40px card-title size so the slides stay within their height budget.

## Verification

- Static subset check over all 36 slide files: allowed tags and CSS only, no text under
  24px, at most 73 elements and 4 nested divs per slide, at most 20 pinned children per
  host.
- Headless Chrome with the deck fonts:
  - no text below the 920px footer line on any slide;
  - no footer wraps;
  - no box overflows its content.

  The remaining flags are glyph ascenders past tight line-heights on headings and big
  numbers, a font-metric effect rather than a layout fault.
- Repository gates (laptop, provisional), on the commit's tree:
  - `ruff check`: all checks passed;
  - `ruff format --check`: 68 files already formatted;
  - `scripts/check_ids.py`: no duplicate or colliding ids;
  - `pytest --collect-only`: 701, unchanged against NC-021.

  This change adds documentation only, and no file under `src/`, `tests/` or `scripts/`
  changed.

## Related docs

- PR #111, Issue #110
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md`
- `docs/roadmap/2026-10-04-deep-engine-architecture-research.md`
- `docs/advisor/2026-09-03-decisions-from-akba.md`
