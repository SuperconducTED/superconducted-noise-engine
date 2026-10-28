# 2026-10-28: akba-phase-4-experiment-deck

## Problem / Motivation

Phase 4's direction (the design-time predictor, decided 2026-10-23) and its decisive
experiment, the #125 hardware reading-versus-level test, had never been put in front of the
advisor, Dr. Fırat Akba. The phase-4 plan §7 names that gap ("Dr. Akba's double-check of the
direction change ... has not been sought"), and the advisor register holds no phase-4 entry.
The lead asked for a mid-work deck that answers why, what the problem is, the method, the
data, the evidence so far, the approach, reproducibility, the Q1 relevance and the asks,
written for a reader who skims: one takeaway line per slide, short bullets, drawn figures, and
every number traced to a register row. The deck records what was shown; it records no
approval.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/README.md` | The record: what was built, the artifact links, sources, every cited register row, the number policy and the known gaps. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/tr/deck.json` | The Turkish deck's index (title, order of 20 slides, sections, the two Google Fonts faces). |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/tr/slides/*.html` | The 20 Turkish slides, one `<section>` each, with speaker notes in `<aside>`. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/en/deck.json` | The English twin's index, same order and sections. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/en/slides/*.html` | The 20 English slides, identical in layout and numerals to the Turkish ones. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/speaker-notes.md` | Turkish presenter notes per slide, the English note in a collapsed block, taken verbatim from the slides' `<aside>` text. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/render_ladder_chart.py` | Renders NC-085's gamma 24 h interval-score ladder from the committed `results.tsv` in the brand style and checks each value against the register row. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/chart-labels.json` | The chart's English and Turkish labels, kept out of the script so it stays ASCII. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/chart-ladder-{en,tr}.png` | The rendered charts, uploaded to the two decks as assets. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/check_numbers.py` | Checks every numeral on every slide against the cited register rows and the pinned protocol documents, plus Turkish-English parity. |
| `docs/advisor/2026-10-28-akba-phase-4-experiment-deck/check_numbers.txt` | The committed output of that check: 294 pass, 0 fail, 0 parity differences. |
| `docs/implementations/2026-10-28-akba-phase-4-experiment-deck.md` | This record. |

## Implementation approach

**Deck format.** The decks are Claude Slides artifacts, the format of the 2026-10-05 deck: one
`deck.json` index plus one `slides/<id>.html` per slide, each a single `<section>` on a
1920 by 1080 canvas with inline styles from the Slides subset and no scripts. The record
folder keeps the `tr/` and `en/` shape of the 2026-10-05 folder; the artifacts were published
from a scratch copy in the type's `project/` layout, diffed against the record folder first
(no differences).

**Look.** The brand's Cryostat palette (`src/superconducted/figures/roles.json`): ink
`#0A1B24`, ground `#EEF3F5`, accent `#0A6C7C`, with an orange `#A34A12` for the latest
reading and for warnings, and the brand faces Space Grotesk and Space Mono. Each content slide
has the same skeleton: eyebrow, title, one bold takeaway line, then a figure or a table, then
short bullets, and a pinned footer naming its sources and register rows.

**Figures.** Figures that encode data come only from committed outputs: the slide-3 bar chart
reads the four gamma 24 h interval scores from `docs/evidence/predictability/results.tsv`.
Every other figure is a diagram that encodes no data: HTML box-and-arrow flows (the problem,
the two arms, the selection funnel, the data pipeline, the reproducibility chain), a decision
diagram for the pass/fail rule, a grid timeline for the build order, and two inline SVG
schematics (level plus scatter, a decay curve with the two delay grids), each labelled
"schematic, not data". Text stays in HTML outside the SVGs, so it is checkable and
translatable.

**Number check.** `check_numbers.py` parses each slide into body, footer and notes, removes
structural numerals (dates, issue and section numbers, register and decision ids, hashes,
review ids, years, identifiers such as `T1` or `p_1`, the page number), and looks each
remaining numeral up in order: the register rows the slide cites (NC-087 to NC-091 from the
pre-registration branch's register at `821f6781`, every other row from `main`), then the three
protocol documents at pinned commits (the design, the pre-registration draft, the plan's §8 at
`e5c75c3b`), then the whole register. A numeral found only in an uncited row, or nowhere,
fails. Sources pass through the same structural blanking, so a slide numeral meets only a
source numeral, never a digit inside a date or an id. The report lists every cited row that
holds a numeral, with context, so a hit on the wrong quantity is visible.

## Mathematical / Statistical details

N/A, purely structural. The deck restates registered values and the design's decision rule;
it computes no statistic. The chart script reads four committed values and compares each with
the value NC-085 writes, tolerating the register's three-decimal rounding (difference at most
0.001); it reports where the two roundings differ (ridge: 1.09446 in the TSV, 1.095 in the
row).

## Design decisions

- **Takeaway line, bullets and figures over prose**, on the lead's guidance for this mid-work
  deck. The cost: slide 6 condenses design §7 into its three outcomes instead of quoting it;
  the footer states that §7 governs.
- **A second data slide** ("Eight numbers behind the experiment") instead of more text on the
  archive slide, so each figure stands with its row id; the two appendix slides of the first
  draft were merged into one to keep the deck at 20.
- **0.34, not 0.37, for the scatter.** The design's "0.37 log units" is not written in NC-085's
  row; the row's own figure, the rolling band's half-width of about 0.34, is used.
- **Protocol values may come from documents, not rows.** Shots, delays, job count and the
  submission hour are decisions, not measurements; they are checked against the pinned design
  and pre-registration text and marked `PROTOCOL` in the output. Single digits found only that
  way are marked weak.
- **Turkish numerals in the register's notation** (decimal point, narrow no-break space for
  thousands) so that the two decks carry identical, checkable values; the Turkish cover says
  so.
- **One chart only.** The pre-registration branch's `grid-bias.tsv` and `recal-hours.tsv`
  could be plotted, but their per-row values are not register rows; the delay-grid finding is
  shown as a table of NC-087's values and the hour choice as a schematic day bar with NC-091's
  figures.

## Verification

From the worktree root, with `origin` fetched:

- `python docs/advisor/2026-10-28-akba-phase-4-experiment-deck/check_numbers.py`: exit 0,
  "294 numerals pass, 0 fail; 0 parity differences" (the committed `check_numbers.txt`).
- `PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/advisor/2026-10-28-akba-phase-4-experiment-deck/render_ladder_chart.py`:
  writes both PNGs and prints the ridge rounding note.
- `C:/t/ruffpin/Scripts/ruff.exe check .` and `ruff format --check` on the folder: clean.
- Em dashes: `text.count(chr(0x2014))` is 0 for every new file.
- Render check (laptop, Chrome headless, Google Fonts loaded): every slide of both decks placed
  on a 1920 by 1080 canvas, measured for text below the footer line (920 px, 952 px on the
  cover, which has no footer), overflow past the right margin, boxes whose content overflows
  them, footer wraps and text under 24 px. Result: 0 slides with issues in either language;
  the remaining notes are glyph ascenders past tight line boxes on headings and big numbers
  (at most 20% of the line box), the font-metric effect the 2026-10-05 deck recorded. The
  measuring harness lives in the session scratchpad, not in the repository.

## Related docs

- `docs/advisor/2026-10-05-akba-meeting-deck/` on `mert/three-engine-deep-model-plan` (the
  format copied)
- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md`;
  `docs/roadmap/2026-10-24-issue-125-preregistration.md` on `mert/issue-125-preregistration`
- `docs/roadmap/2026-10-23-phase-4-plan.md` (§8 on `mert/phase-4-builder-order`)
- `docs/advisor/2026-09-03-decisions-from-akba.md`
- `docs/implementations/2026-10-16-brand-chart-style.md`
- `docs/numerical-claims.md`; Issues #92, #110, #125; PR #128
