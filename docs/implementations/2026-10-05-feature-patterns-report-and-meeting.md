# 2026-10-05: feature-patterns-report-and-meeting

## Problem / Motivation

After the feature-pattern analysis landed on PR #111 (`bcdcf05`, `868480f`, `56aba5e`), the
lead asked on 2026-10-05 for three things: that everything produced in that working session be
documented in the repository, that the Turkish report page (a private Claude artifact) be added
to the same PR as a PDF, and that the PR's reviewer be asked again with the new developments.
He also reported that the meeting with Dr. Fırat Akba, planned in the plan's §9 for the week of
2026-10-05, took place that day while the analysis was being produced, and gave its direction:
a deeper pass over the collected feature data before any strategic decision, so that the paper
starts from the root of the problem.

An audit of the session against the repository found five gaps:

1. the report page existed only as a private artifact, with no repository copy;
2. the 52-source literature report behind the method verdict existed only in a temporary
   directory, as did the measured JSON report behind every archive figure;
3. the 20 new tests had changed the full suite size without updating NC-021, which
   `docs/numerical-claims.md` Rule 6 requires in the same PR;
4. the plan still carried the A9 section's pre-meeting assumption about the meeting;
5. PR #111's description still said "Documentation only", which stopped being true at
   `bcdcf05`.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-10-05-feature-patterns-report/ibm-fez-kapi-hatalari.pdf` | The report page printed to a 10-page PDF from artifact version `1791221881-079e`. |
| `docs/advisor/2026-10-05-feature-patterns-report/ibm-fez-kapi-hatalari.html` | The published page in the host's minimal skeleton, interactive, with its data embedded. |
| `docs/advisor/2026-10-05-feature-patterns-report/README.md` | Provenance of the page and the PDF, the source of each section, the snapshot chart's de-duplication rules, the page's pre-meeting state, and how to regenerate the PDF. |
| `docs/evidence/feature-patterns/2026-10-05-09fcc45.json` | The complete `scripts/feature_patterns.py` report over all 1,753 `ibm_fez` files at `calibration-data` `09fcc45`. |
| `docs/evidence/feature-patterns/README.md` | Its provenance, the commands that reproduce it, the self-consistent expectations for a re-run, and the map from roadmap sections to its fields. |
| `docs/roadmap/2026-10-05-gate-error-literature-survey.md` | The second survey pass's full report, under a header that states how it was made and what was checked afterwards. |
| `docs/roadmap/2026-10-05-feature-patterns-and-method.md` | Appended §9, pointing to the survey, the evidence, the report folder and the meeting record. |
| `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` | Appended the meeting record: held, what was shown, the direction in the lead's words, the open items, and what follows. |
| `docs/numerical-claims.md` | NC-021 re-measured: 721 collected at `56aba5e`, with the open PRs that also change the row named. |
| `docs/implementations/2026-10-05-feature-patterns-report-and-meeting.md` | This record. |

PR #111's description gains a dated amendment note at its top (not a file).

## Implementation approach

**The PDF is printed from the published HTML, not re-built.** The published file was wrapped in
the same skeleton the artifact host adds, and a print-only stylesheet was added to a copy of it:
a page of 1240 by 1754 CSS pixels (the A-series aspect ratio, wide enough that the snapshot
chart's natural width of about 1,120 pixels is not clipped), the section menu, scroll hint and
tooltips hidden, cards kept whole across page breaks, colours kept, each of the three new parts
starting on a new page, and a provenance line on the first page. Edge printed it headless with
the window set to the page size, because the charts measure their container when the page loads.
The repository keeps the skeleton-wrapped HTML without the print stylesheet; the README carries
the stylesheet and the command.

**The literature report was re-resolved before it was committed.** Every arXiv identifier in its
cited sections (50) was resolved against the arXiv API and every DOI (4) against Crossref. All
resolved, and each returned title is the work the text names; eight rows that use a short name
were matched by hand. The report body is committed unchanged under a header that says what was
and was not checked.

**The evidence JSON is the committed script's output.** Before copying it, `analyze` was re-run
with the script as committed in `bcdcf05` on the same cache, and its output was byte-identical.

**NC-021** was updated in place in the value, source and date columns, with the new entry
appended to the row's history, as the register's earlier entries do.

**The meeting record** quotes the lead's direction verbatim, with an English rendering, and lists
as open everything his account does not cover. On 2026-10-05 the lead was asked what came out of
the meeting and selected only that Dr. Akba saw the findings and the report page; the record says
"shown", not "approved".

## Mathematical / Statistical details

N/A: purely documentary. The figures this change carries were all measured by
`scripts/feature_patterns.py`, whose method is in
`docs/implementations/2026-10-05-feature-pattern-analysis.md`.

## Design decisions

- **PDF plus HTML, not the PDF alone.** The PDF is the durable, readable record; the HTML keeps
  the interactive scale toggle, the hover details and the 820-row table, and embeds its data, so
  nothing on the page depends on the private artifact staying available.
- **No page-building scripts in `docs/`.** CI runs `ruff check .` over every Python file in the
  repository, and the throwaway builders were not written to that standard. The README instead
  records the sources of each section and the exact print stylesheet and command.
- **The literature report kept verbatim.** Editing an agent's report into house style would make
  it impossible to tell its claims from the checks made on them afterwards; the header carries the
  checks.
- **The meeting goes in the plan, not the decisions register.** The plan's task T0 records Dr.
  Akba's answers in the register in a PR after #98 merges, and #98 is still open.

## Verification

In a Python 3.12 venv built from `requirements.txt` (`PYTHONPATH=src` if the venv's editable
install points elsewhere):

```bash
python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider | tail -1
grep -o "Full test-suite size | [0-9]*" docs/numerical-claims.md
python -m pytest tests/ -q -p no:cacheprovider | tail -1
ruff check .
ruff format --check .
mypy --strict
python scripts/check_ids.py
git check-attr -a docs/advisor/2026-10-05-feature-patterns-report/ibm-fez-kapi-hatalari.pdf
git ls-files --eol docs/advisor/2026-10-05-feature-patterns-report docs/evidence/feature-patterns
```

Expected: the first two lines give the same number; the suite passes (on a runner without the
archive, exactly one skip, the archive-backed survey test); the static gates are clean; the PDF is
stored as binary (`-text` in `ls-files --eol`) and the text files as LF. The archive
re-measurement and the comparison with the evidence JSON are in the desktop runbook posted on PR
#111.

## Related docs

- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (A1 to A9 and the meeting record)
- `docs/roadmap/2026-10-05-feature-patterns-and-method.md`
- `docs/roadmap/2026-10-05-gate-error-literature-survey.md`
- `docs/implementations/2026-10-05-feature-pattern-analysis.md`
- `docs/numerical-claims.md` (NC-021, Rule 6)
- Issue #110, PR #111, PR #98
