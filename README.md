# Calibration Data

![Pipeline health](health/progress.svg)

This branch is **data only**. It carries no source code, it is never merged into
`main`, and nothing here is edited by hand. GitHub Actions polls IBM Quantum for
`ibm_fez` calibration data and files each new document below; the dashboard above
is re-rendered from those committed files and refreshed daily.

## Layout

| Path | What it holds | Written by |
| --- | --- | --- |
| `snapshots/YYYY-MM/<backend>/<stamp>.json` | One archived calibration document. The filename is IBM's own `last_update_date`, never the poll clock, and an already-archived path is never overwritten. | Calibration Polling |
| `ledger/YYYY-MM.tsv` | One row per poll, including the polls that observed nothing new. This is what makes a stopped poller distinguishable from a quiet one. | Calibration Polling |
| `collisions/` | A payload that arrived under a stamp already on disk. A non-empty tree is a signal, not routine traffic. | Calibration Polling |
| `health/state-index.tsv` | One row per archived document: its qubit-block digest and whether that device state had been seen before. Append-only. | Calibration Polling |
| `health/metrics.json` | Every figure the dashboard renders, plus `generated_at` and the exact staleness in hours. | Calibration Pipeline Health |
| `health/progress.svg` | The dashboard above. | Calibration Pipeline Health |

`health/metrics.json` and `health/progress.svg` are **generated**. Editing either
by hand is pointless: the next render overwrites both. The state index is the
replayable source of truth for the state count, so it is appended to and never
rewritten, with one exception recorded in the ADR-025 amendment (a dispatched
backfill may regenerate it once, in `last_update_date` order).

## Reading the dashboard

**It counts distinct device states, not files.** That distinction is the whole
point. A document is republished whenever any part of it changes, gate data
included, so `last_update_date` advances far more often than the qubit
measurements do. Counting files is the instrument that reported healthy progress
for three months while the archive was accumulating duplicates, and the
duplication ratio is the honest read on how far apart those two numbers are.

The three panels answer three questions:

- **Progress bar.** How many distinct device states exist, against candidate
  training floors. Each floor is a labelled tick, never one authoritative line,
  because the floor is a configuration input and moves with the membership-function
  shape. The labels name the register row each value comes from.
- **Poll health, last 72 hours.** One cell per hour, filled when at least one poll
  fired in it. A scheduler that is dropping runs shows up as visible gaps within a
  day, which is the failure this branch exists to make cheap to notice.
- **New states per day, trailing 30 days.** Whether the archive is still gaining
  information or merely gaining files.

Plus the headline figures: distinct states, documents, duplication ratio, and time
since the last new state. The staleness headline is a band rather than a clock
reading so the graphic only changes when something real did.

## Provenance

Every number rendered in the SVG also appears in `health/metrics.json`, and every
figure in that file derives from committed files in this branch. Nothing on the
dashboard is a constant baked into the renderer. If a figure here is going into a
paper, a slide, or any public-facing document, it needs a row in
[`docs/numerical-claims.md`](https://github.com/SuperconducTED/superconducted-noise-engine/blob/main/docs/numerical-claims.md)
first.

## Decisions that govern this branch

- [ADR-020, calibration snapshot schema and storage](https://github.com/SuperconducTED/superconducted-noise-engine/blob/main/docs/decisions.md#adr-020--calibration-snapshot-schema-and-storage)
  fixes the `snapshots/` layout and the filename rule.
- [ADR-025, ledger and collision trees](https://github.com/SuperconducTED/superconducted-noise-engine/blob/main/docs/decisions.md#adr-025--calibration-data-branch-ledger-and-collision-trees)
  adds `ledger/` and `collisions/`, and its 2026-09-05 amendment adds `health/`.

The workflows that write here are `calibration-poll.yml` (hourly) and
`calibration-health.yml` (daily, plus `workflow_dispatch`), both on `main`.

---

> **This is a validation copy, not the live archive.** This branch is
> `calibration-data-health-validation`, a scratch copy taken from
> `calibration-data` at `1d2a9d5` to prove the health workflow end to end before
> PR #70 merges. The snapshots and ledger below are a frozen copy; the `health/`
> tree was generated here by a real Actions run. The live archive is
> [`calibration-data`](https://github.com/SuperconducTED/superconducted-noise-engine/tree/calibration-data).
> Delete this branch once PR #70 has merged and the real dashboard is published.
