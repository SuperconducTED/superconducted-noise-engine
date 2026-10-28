# Phase-4 mid-work deck for Dr. Akba, 2026-10-28

The deck @mertefesensoy presents to Dr. Fırat Akba on the phase-4 hardware experiment (#125):
why it is run, the problem, the method, the data, the evidence so far, how it stays
reproducible, why it matters for a Q1 paper, and what we ask of him. Two private Claude Slides
artifacts carry it, Turkish (`tr/`, the one presented) and English (`en/`), with identical
slides and identical numerals:

- Turkish: https://claude.ai/artifact/N61iABXRypRYxaAkLkt6wc
- English: https://claude.ai/artifact/Vu4XJhdL1utU5tmL3SSBHf

Neither is shared; sharing is the lead's call.

**This folder records what was shown, never what was approved.** Dr. Akba's direction and
method claims on the slides are the lead's account. Nothing here is a decision; any answer he
gives is recorded in `docs/advisor/2026-09-03-decisions-from-akba.md` in his words. That
register holds no entry on the phase-4 direction yet (plan §7 says his double-check "has not
been sought"); this deck is where it is shown.

## What is in the folder

| Path | What it is |
| --- | --- |
| `tr/deck.json`, `en/deck.json` | Each deck's index: title, slide order, sections, fonts (the Slides `project/deck.json`) |
| `tr/slides/<id>.html`, `en/slides/<id>.html` | One slide each, a single `<section>` in the Slides format, speaker notes in its `<aside>` |
| `speaker-notes.md` | One paragraph per slide in Turkish, the English twin's note in a collapsed block; generated from the slides' `<aside>` text, so it matches them word for word |
| `render_ladder_chart.py`, `chart-labels.json` | Renders the slide-3 chart from `docs/evidence/predictability/results.tsv` in the brand chart style |
| `chart-ladder-tr.png`, `chart-ladder-en.png` | The rendered charts, uploaded to each deck as assets (`/_blob/154d0dfa...` in Turkish, `/_blob/9347f5a3...` in English) |
| `check_numbers.py`, `check_numbers.txt` | Checks every numeral on every slide against the register and the protocol documents; the committed output |

The 20 slides: cover; the engineering problem; what the archive established (the chart); the
one question only hardware can answer (a schematic); prior art; the pass/fail rule (a decision
diagram); Arm A; Arm B; qubit selection (a funnel); the delay grid (a schematic decay curve);
the schedule (a job strip and a UTC day bar); the data pipeline; eight numbers behind the
experiment; statistics; the pattern detector; reproducibility (a chain); build order (a
timeline); what the paper can and cannot claim; the asks; the register appendix. Each content
slide opens with one bold takeaway line, per the lead's guidance for this mid-work deck.

## Sources

| Slide content | Source |
| --- | --- |
| The engineering goal | `docs/findings/2026-10-23-strategy-audit.md` §3.1; `docs/roadmap/2026-10-23-phase-4-plan.md` §1 |
| Archive facts | `docs/evidence/persistence-band/`, `docs/evidence/predictability/` (NC-080, NC-081, NC-083 to NC-085) |
| The question and the rule | `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` §1, §7 (condensed on slide 6; §7's text governs) |
| Decided values (proposals A to D, union grid, 03:45 UTC, budget) | `docs/roadmap/2026-10-24-issue-125-preregistration.md` at `821f6781` on `mert/issue-125-preregistration` (draft, not frozen) and its evidence folder (NC-087 to NC-091) |
| Prior art | `docs/findings/2026-10-23-novelty-check-q1-article.md` §1, §3.4, §3.5, §9 |
| Public archive | `docs/evidence/public-archive-overlap-2026-10/README.md` (NC-077 to NC-079, ADR-029 draft) |
| Pattern detector | `docs/evidence/pattern-detector/README.md` §12 only (NC-092, NC-094); the quotation is @bengisucvd's own sentence in her PR #128 reviews 5681736384 and 5681976426 |
| Build order | `docs/roadmap/2026-10-23-phase-4-plan.md` §8 at `e5c75c3b` on `mert/phase-4-builder-order` (not on `main`) |

## Every register row cited

| Row | Where it lives | Anchor |
| --- | --- | --- |
| NC-008 | `main` | `.github/workflows/calibration-poll.yml` |
| NC-077, NC-078, NC-079 | `main` | `calibration-data` @ `5828b4a2` and the public revision `0c298c2b` |
| NC-080, NC-081, NC-083, NC-084, NC-085 | `main` | `calibration-data` @ `5828b4a2` |
| NC-092, NC-094 | `main` | `calibration-data` @ `cf960389` |
| NC-087 to NC-091 | `mert/issue-125-preregistration` @ `821f6781` only | NC-087 a computation; the rest `calibration-data` @ `5828b4a2` |

Every measured row is a dated anchor in the Rule 7 form that Issue #92 proposes (the rule
itself is still proposed), measured on the laptop and provisional until Burak's desktop
reproduces it.

## Number policy

Every numeral on a slide is either a value written in a register row that the same slide
cites, or a decided protocol value written in the design, the pre-registration draft or the
plan's §8, each read at a pinned commit. `check_numbers.py` enforces this and lists, for each
numeral, every cited row or document that holds it, so a match on the wrong quantity is
visible. Its output, `check_numbers.txt`: 296 numerals pass, 0 fail, and the Turkish and
English slide bodies carry the same numerals. Twelve single-digit protocol matches (job 1, job 2,
`ghz_state_circuit(3)`, the formula's `1`) are marked weak in the output, since any long
document contains a single digit.

The Turkish deck writes decimals with a point and thousands with a narrow no-break space, so
its numerals equal the register's values; its cover says so.

## Known gaps

- The design's "0.37 log units" scatter (§1) is not written in NC-085's row; the row writes
  the rolling band's half-width as about 0.34 log units, and the slides use that. The 0.375
  shrinkage half-width is in `docs/evidence/predictability/results.tsv` only. 0.37 appears on
  slide 15 solely as the pattern detector's departure threshold, which NC-092 writes.
- NC-085 writes the ridge interval score as 1.095; `results.tsv` holds 1.09446, which rounds
  to 1.094. The chart labels the bar with the register's 1.095 and the render script prints
  the difference.
- Slide 6 condenses design §7 into a decision diagram instead of quoting it verbatim, on the
  lead's no-paragraphs guidance; the footer says §7 governs.
