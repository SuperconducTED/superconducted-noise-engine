# Numerical Claims Register

## Purpose

Every specific number in public-facing SuperconducTED documentation
(flagship `README.md`, org profile, `docs/architecture.md`, `docs/findings/`,
`docs/state-of-the-project/`, paper drafts, presentation slides) must
trace to a row in this file. Numbers without a row here either get a
row before merge, or get removed.

This file exists because the project shipped a fabricated benchmark
figure (`~0.686% fidelity deviation` attributed to Bautra et al. 2026)
that propagated across four documents over multiple weeks before
verification surfaced the fabrication. The discipline below is designed
to make that failure mode structurally hard to repeat.

## Rules

1. **Every claim has a verifiable source.** Either a published paper
   with arXiv ID / DOI, a file in this repository with a path (and
   line number where useful), a script committed to `scripts/` with a
   recorded output, or a measurement procedure documented enough that
   a reader can rerun it.

2. **"It sounds right" is not a source.** If a number cannot be traced
   to one of the four categories above, it does not belong in a
   public-facing document. Hedged language ("on the order of",
   "roughly") does not exempt a claim from needing a source · it just
   means the source itself was approximate.

3. **`Last verified` is a real date.** Set when someone opened the
   source and confirmed the value. Update when re-verified. If the
   underlying source changes (new measurement supersedes old, paper
   retraction, code refactor changes a calculation), update the value
   and the date together · do not silently keep the old value.

4. **Stale claims get flagged.** Anything not re-verified within
   90 days carries a `STALE` flag in the Notes column. Stale flags
   do not block use of the number, but they require the next person
   touching the claim to re-verify before propagating.

5. **Claims removed from public docs are not removed from this file.**
   They move to the `Retired` section at the bottom with the reason
   recorded. This is the audit trail.

## Active claims

| ID | Claim | Value | Source | Last verified | Notes |
|----|-------|-------|--------|---------------|-------|
| NC-001 | Aer ensemble latency, N=1, shared simulator hoisted, 1024 shots | 0.07s | `docs/findings/aer-integration-walkthrough.md`, commit `4006f6c` | 2026-05-25 | Includes warmup amortization · per-member cost on subsequent members is higher |
| NC-002 | Aer ensemble latency, N=8 | 0.91s | `docs/findings/aer-integration-walkthrough.md`, commit `4006f6c` | 2026-05-25 | |
| NC-003 | Aer ensemble latency, N=16 | 1.89s | `docs/findings/aer-integration-walkthrough.md`, commit `4006f6c` | 2026-05-25 | |
| NC-004 | Per-member cost after warmup amortization | ~0.12s | Derived from NC-002, NC-003 | 2026-05-25 | (0.91 − 0.07) / 7 ≈ 0.12 · (1.89 − 0.07) / 15 ≈ 0.121 |
| NC-005 | Harness validation test count | 15 | `tests/test_metrics.py` | 2026-05-25 | All 15 tests pass · property categories per ADR-022 |
| NC-006 | Harness validated metric properties | 6 | `docs/decisions/drafts/ADR-022-benchmark-validation-criteria.md` | 2026-05-25 | Identity · symmetry/asymmetry · bounds · monotonicity · determinism · reference value |
| NC-007 | KL divergence smoothing epsilon | 1e-12 | `docs/implementations/2026-05-13-harness-metric-sanity-checks.md` | 2026-05-25 | |
| NC-008 | Calibration polling cadence, target | hourly at `:37` | `.github/workflows/calibration-poll.yml`, `docs/implementations/2026-05-13-calibration-poller-cron.md` | 2026-05-25 | Target schedule · not the realized cadence (see NC-009) |
| NC-009 | Calibration polling cadence, sustained measured | ~11.1 snapshots/day | `git ls-tree -r origin/calibration-data` count divided by days since first snapshot, measured 2026-05-25 | 2026-05-25 | Below theoretical max of 24/day due to GitHub Actions scheduler drops |
| NC-010 | Calibration polling cadence, theoretical max | 24 snapshots/day | One snapshot per hour, 24 hours per day | 2026-05-25 | Never observed in practice |
| NC-011 | Snapshot count, measured | 127 | `git ls-tree -r origin/calibration-data` filtered to `snapshots/*.json`, 2026-05-25 | 2026-05-25 | |
| NC-012 | ANFIS training snapshot floor | ≥ 630 | `docs/decisions.md` ADR-014 context | 2026-05-25 | Working minimum · roughly 126 trainable parameters × 5 rule of thumb per `docs/architecture.md` |
| NC-013 | 630-snapshot floor projected date | ~2026-07-10 | Derived from NC-009 and NC-011: (630 − 127) / 11.1 ≈ 45 days from 2026-05-25 | 2026-05-25 | Sensitive to scheduler drop rate · re-verify monthly |
| NC-014 | T1 missingness rate on qubit 72 of ibm_fez | ~0.64% | `tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json` (1 of 156 qubits affected) | 2026-05-25 | Single snapshot · not a population rate |
| NC-015 | ADR count at end of cycle 1 | 22 | `docs/decisions.md` plus `docs/decisions/drafts/` | 2026-05-25 | ADR-001 through ADR-022 |
| NC-016 | ADR cycle 1 drift count | 2 | `docs/audits/2026-05-25-first-cycle-audit.md` | 2026-05-25 | ADR-006 and ADR-016 |
| NC-017 | Follow-up issues from cycle 1 audit | 8 | `docs/audits/2026-05-25-followup-issues.md` | 2026-05-25 | |
| NC-018 | Default ensemble size | 32 | `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md` | 2026-05-25 | Configurable · 8 used in ADR-019 ablation protocol |
| NC-019 | Default shot count per ensemble member, ablation protocol | 4096 | `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | 2026-05-25 | |
| NC-020 | Benchmark circuits in ablation suite | 4 | `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | 2026-05-25 | Random Clifford · GHZ · QFT · efficient_su2 |

## Retired claims

| ID | Claim | Value | Retired | Reason |
|----|-------|-------|---------|--------|
| NC-R001 | Bautra et al. 2026 fidelity deviation vs. real hardware | ~0.686% | 2026-05-25 | Fabricated number. Bautra et al. 2026 (arXiv:2603.14607) uses Weighted Jaccard Similarity in the 43-97% range, not fidelity deviation. No source ever existed. Removed from flagship README, org profile, and `docs/architecture.md`. |

## Adding a claim

1. Find or open a verifiable source.
2. Pick the next available `NC-NNN` ID.
3. Add a row in `Active claims` with claim, value, source path, today's
   date, and any necessary notes.
4. The claim is now safe to cite in public-facing documentation.

## Retiring a claim

1. Move the row to `Retired claims`.
2. Add the retirement date and the reason (`superseded`, `fabricated`,
   `source no longer accessible`, `claim restructured into NC-XXX`).
3. Grep public-facing documentation for the value and citations of the
   retired claim. Remove or replace.

## Re-verification

A reasonable rhythm: re-verify the table at the start of every
development cycle. Update `Last verified` dates for claims that still
hold against current sources. Move stale or superseded claims to
`Retired`. This becomes part of the cycle-open process the same way
the cycle-1-close audit was.