# 2026-10-23: novelty-check-q1-article

## Problem / Motivation

The team intends to write a Q1 journal article about the engine. Before a venue, a framing or
an author order is chosen, someone has to establish what in the engine is new against the
published record and what is not. No document in the repository did that: the advisor brief
File 05 asks Dr. Akba about venue and timing but contains no prior-art survey, and the
2026-05-25 empirical synthesis lists "superiority over competing approaches" under what cannot
be claimed without naming the competitors. This change adds that survey as a dated findings
record.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/findings/2026-10-23-novelty-check-q1-article.md` | New. A claim-by-claim novelty assessment with a prior-art table at stated verification levels, the gating baselines claim 3 needs, two venue framings, and the blind spots the search found. |
| `docs/implementations/2026-10-23-novelty-check-q1-article.md` | This record. |
| `docs/evidence/public-archive-overlap-2026-10/compare_public_archive.py` | New. Read-only cross-check of the public `qiskit-calibration-drift` parquet against our `ibm_fez` archive: event-level value agreement, as-of replay validated against every document, distinct-state counts at hourly and half-hourly marks. |
| `docs/evidence/public-archive-overlap-2026-10/summary.json`, `overlap-by-property.tsv` | New. The script's output at the pinned refs. |
| `docs/evidence/public-archive-overlap-2026-10/README.md` | New. Refs, hashes, out-of-pins readers, the three public-table defects and how each is handled. |
| `docs/numerical-claims.md` | Three rows appended, NC-077 to NC-079, in the dated-anchor form Issue #92 proposes. |
| `docs/decisions/drafts/ADR-029-public-calibration-archive-as-training-source.md` | New draft: the public table is admissible to the training set, not to the archive, under three stated rules and a plausibility guard. |

No source, test or ADR status changed. The ADR is a draft; its ledger entry lands with the
adopting PR.

### Second part of the session: the archive-is-scarce assumption

The novelty check found that the planning documents treat our own archive as the scarce input.
Mert asked to fix that assumption with a question-driven workflow. His answers: download the
dataset's parquet and measure; evaluate, adopt only if the overlap is clean; `ibm_fez` only;
record as an ADR draft plus a data-track issue. The measurements and their refs are in the
evidence folder; the numbers are in NC-077 to NC-079; the decision text is the ADR draft.

## Implementation approach

Desk research, organised by the five claims an article would make rather than by paper.
Search path: project documents first (README, architecture, ADR ledger, register, advisor
files, cycle-2 close) to fix what the engine actually claims and what it has measured; then web
search across five angles (fuzzy methods on quantum hardware, calibration-driven digital twins,
learned noise models, drift and stability, uncertainty intervals on noisy simulation); then
Semantic Scholar citing-paper lists for five anchor papers, which is the step that surfaced
QuBound; then full-text reads of the three load-bearing neighbours (QuBound, Ji et al. 2026,
Bautra et al. 2026) and a code check that the engine's channel is spatially uniform.

Every literature figure in the findings record carries a verification level (full text,
abstract only, repository README). Figures from abstract-level sources are quoted as the
source states them and marked as unchecked against the body.

## Mathematical / Statistical details

The novelty record itself introduces no formula. The cross-check script does two things a
reader should be able to audit without the code:

- **Event matching.** A calibration event is the triple (property name, qubit or qubit pair,
  `calibrated_time`), with its value and unit. Our events come from every `properties.qubits`
  entry and every `properties.gates[].parameters` entry of every archived document, deduplicated
  across documents (4,363,658 unique). Each is looked up in the public table on the triple. Equal
  means the IEEE doubles are identical; "equal after 1e6" would mean equal after a microsecond
  rescale (zero cases occurred); "differ" means a matched triple with a different value.
- **As-of replay and state digest.** Their table is sorted by `calibrated_time`; the state at
  mark $t$ is the latest value per (qubit, property) with `calibrated_time` $\le t$. The state is
  digested as SHA-256 of the sorted (qubit, property, value) triples over the seven qubit-scope
  properties, after dropping qubit 72's T1 and T2 on both sides. This projection is validated by
  (a) giving exactly 924 distinct digests on our 2,249 files, the same count as the official
  `qubit_digest`, with 924 (official, projected) pairs, so the two partitions coincide, and
  (b) reproducing our document's qubit block at 2,145 of 2,249 of our own timestamps. Distinct
  states are then counted over hourly marks (comparable to our document-sampled ledger) and
  half-hourly marks (upper bound). Distinct is an upper bound on independent, per NC-012.
- **Unit rule.** No physical T1 or T2 lies below 0.01 microseconds, so a coherence value below
  0.01 under the label `us` is seconds and is multiplied by 1e6. The script reports how many rows
  the rule touched (14,609 T1, 14,947 T2), how many fall in the ambiguous zone between 0.01 and 1
  (0) and how many keys carry two representations (0), so the rule's reach is measured, not
  assumed.

## Design decisions

- **By claim, not by paper.** A reviewer scores claims. A paper-ordered survey would hide that
  claim 3 (bracketing hardware across calibration cycles) has a published competitor while
  claims 1 and 2 do not.
- **Verification levels stated per row.** The register discipline (`docs/numerical-claims.md`
  Rule 1) applies to numbers the project repeats, not only numbers it measures. The alternative,
  quoting every figure as fact, was rejected.
- **Latest register value, pinned.** The archive count is cited as NC-069's 868 at
  `calibration-data` @ `d62f2cd`, not NC-025's 504, because NC-R001 forbids carrying a stale
  count where a current one is registered.
- **No venue chosen, no ADR touched.** Venue is the team's and the advisor's decision (File 05,
  Question 2). The record names what each venue class will demand and stops.
- **A findings record, not an ADR.** Nothing here is an architectural decision. The two items
  that may become ADR work (a non-fuzzy percentile baseline under ADR-016; per-qubit features
  under ADR-013) are named as blind spots for their owners.

## Verification

This is a documentation change. Checks that were run:

- No em or en dashes in the new record:
  `python -X utf8 -c "t=open('docs/findings/2026-10-23-novelty-check-q1-article.md',encoding='utf-8').read(); print(t.count(chr(8212)), t.count(chr(8211)))"` prints `0 0`.
- Spatial uniformity claim: `grep -n "crisp" src/superconducted/integration/aer_factory.py src/superconducted/channels/kraus.py` shows `_crisp_params` computed once per model and `project` reading `crisp_params.flat[0]` and `[1]` with no use of `qubits` beyond the arity check.
- Register value: `grep -n "^| NC-069" docs/numerical-claims.md` returns 868 of ≥ 1170 at `d62f2cd`.
- Every arXiv identifier in §8 of the record resolves (opened during the search on 2026-10-23).

- Cross-check reproduction: export `calibration-data` @ `5828b4a2` (`snapshots/`, `health/`) to a
  short path, download the parquet at the pinned revision into an empty directory and confirm its
  SHA-256, install the three out-of-pins readers into a separate target directory, then run the
  command in the evidence README with an isolated interpreter. `summary.json` must match the
  committed copy. Ruff passes on the script with the pinned 0.15.12 (`ruff check`, `ruff format
  --check`); mypy's configured scope excludes `docs/`.

Not verified, and said so in the record: journal quartiles; the Hugging Face dataset's coverage
of properties other than those our documents carry; any abstract-level figure. The public
table's three other backends were not measured.

## Related docs

- `docs/findings/2026-10-23-novelty-check-q1-article.md` (the record)
- `docs/findings/2026-05-25-empirical-synthesis.md` ("What we cannot claim yet")
- `docs/advisor/2026-09-09-akba-brief/05-yayin-stratejisi.html` (venue questions)
- `docs/decisions.md` ADR-009, ADR-013, ADR-015, ADR-016, ADR-027
- `docs/numerical-claims.md` NC-012, NC-045, NC-069
