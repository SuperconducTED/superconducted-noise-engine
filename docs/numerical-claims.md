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

6. **Claims measured from this repository move with this repository.**
   A claim whose source is a command run against this repo — test counts,
   file counts, rule arities — is invalidated by any PR that changes what
   that command returns. The PR that changes it updates the row's value,
   source commit, and `Last verified` date in the same commit. Rule 3
   already implies this; it is stated separately because NC-021 drifted by
   17 across two PRs that had no reason to open this file, and a
   verification runbook citing the stale row reported a regression that did
   not exist (issues #40, #29). Runbooks citing a row of this kind must also
   name the commit it was measured at, so a stale row surfaces as a visible
   mismatch instead of a silent contradiction.

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
| NC-012 | ANFIS training snapshot floor | ≥ 630 | `docs/decisions.md` ADR-014 context | 2026-08-30 | Working minimum · roughly 126 trainable parameters × 5 rule of thumb per `docs/architecture.md` · **the unit was ambiguous until 2026-08-30 and is now decided: distinct device states, not snapshot files** (#45; `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md`) · a samples-per-parameter heuristic counts independent samples, so duplicate rows do not count toward it · see NC-023 |
| NC-014 | T1 missingness rate on qubit 72 of ibm_fez | ~0.64% | `tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json` (1 of 156 qubits affected) | 2026-05-25 | Single snapshot · not a population rate |
| NC-015 | ADR count at end of cycle 1 | 22 | `docs/decisions.md` plus `docs/decisions/drafts/` | 2026-05-25 | ADR-001 through ADR-022 |
| NC-016 | ADR cycle 1 drift count | 2 | `docs/audits/2026-05-25-first-cycle-audit.md` | 2026-05-25 | ADR-006 and ADR-016 |
| NC-017 | Follow-up issues from cycle 1 audit | 8 | `docs/audits/2026-05-25-followup-issues.md` | 2026-05-25 | |
| NC-018 | Default ensemble size | 32 | `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md` | 2026-05-25 | Configurable · 8 used in ADR-019 ablation protocol |
| NC-019 | Default shot count per ensemble member, ablation protocol | 4096 | `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | 2026-05-25 | |
| NC-020 | Benchmark circuits in ablation suite | 4 | `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` | 2026-05-25 | Random Clifford · GHZ · QFT · efficient_su2 |
| NC-021 | Full test-suite size | 168 | `python -m pytest tests/ --collect-only -q -o addopts=""` (tail line), run at `c6231bf` on `mert/calibration-yield-issue-45` | 2026-08-30 | Was `149` at `981f324`, then `166` at `1873625` · +2 from this branch: `test_operations_order_independent` (#46 regression) and `test_init_error_absent_before_the_schema_cutover` (#45) · see Rule 6 · cite this row in verification runbooks rather than recalling a count, and state the commit it was measured at |
| NC-022 | ADR statuses drifted from the 2026-05-25 snapshot table | 4 | Each `ADR Cycle Summary` row in `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` compared against its `**Status**` line in `docs/decisions.md` at `dfee09c` | 2026-08-24 | ADR-006, ADR-010, ADR-012, ADR-018 · excludes ADR-019 through ADR-022, which had no ledger entry to drift from at that commit · they were promoted into the ledger by `d7ee18b` and issue #37 is closed; the value stands as measured at `dfee09c` and is not restated for later commits |
| NC-023 | Distinct device states in the calibration archive | 504 | #45 §7, measured against `calibration-data` @ `f0930b9` (894 snapshot files, 43.6% byte-identical in their qubit block to the previous one) | 2026-08-30 | The unit NC-012 counts as of the 2026-08-30 decision · 504/126 ≈ 4.0 samples per trainable parameter, below the 5× the floor was derived from · the gate is **not** met |
| NC-024 | Historical calibration properties, verified retention depth | ≥ 60 days | Actions run [33260786341](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33260786341) via `scripts/probe_historical_properties.py`, channel `ibm_quantum_platform`, plan `open` | 2026-08-30 | Ten depths from 1 to 60 days all returned older documents; none denied · lower bound only, 60 d was the deepest probed · IBM's own API reference claims `NotImplementedError` on this channel and is stale · re-runnable any time via the Calibration Historical Probe workflow |
| NC-025 | `init_error` per-qubit coverage after the schema cutover | 116 of 156 qubits | `load_snapshot` on `snapshots/2026-08/ibm_fez/20260828T031723000000Z.json` at `f0930b9`; 0 of 40 sampled post-cutover snapshots carry the field for all 156 qubits | 2026-08-30 | Refines #45 §6b, which established the cutover is clean at *snapshot* granularity — a weaker claim than per-qubit completeness · a fixed set of 40 qubits never reports it, plus 1 intermittent |
| NC-026 | `init_error` out-of-sample R² across a 20-day time split | −0.585 | OLS of `init_error` on the six co-observed per-qubit fields, 40 snapshots spanning 2026-08-04..08-24, n = 4607 qubit-records; train 08-04→08-19, test 08-19→08-24 | 2026-08-30 | In-sample R² is 0.139 · negative out-of-sample R² means the fit predicts worse than the held-out mean · this is the evidence that eliminated imputing `init_error` for the 669 pre-cutover snapshots |
| NC-027 | Calibration capture rate over the 2026-08-27..30 scheduler outage | ≤ 19.3% (11 of ≥57) | `evidence/PR-47-Evidence/enumeration-2026-08-30.tsv`; Actions run [33301248740](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33301248740) diffed against `origin/calibration-data` filenames | 2026-08-30 | Upper bound on capture, because the 1 h sweep provably undercounts: 2 documents we hold were not returned by it · 46 of those documents were recoverable at measurement time |
| NC-028 | IBM document republication rate, `ibm_fez` | ≥ 19 documents/day (mean interval ≤ 1.26 h) | Same enumeration as NC-027: ≥57 distinct `last_update_date` values in a 72 h window | 2026-08-30 | **Not** the same quantity as the ~4.0 h readout-parameter cadence in #45 §3 — `last_update_date` advances whenever any part of the document changes, gate data included · lower bound · this figure refutes "above ~8 polls/day the extra polls are pure duplicates" at the document level, but says nothing about distinct device states (NC-023) |

## Retired claims

| ID | Claim | Value | Retired | Reason |
|----|-------|-------|---------|--------|
| NC-R001 | Bautra et al. 2026 fidelity deviation vs. real hardware | ~0.686% | 2026-05-25 | Fabricated number. Bautra et al. 2026 (arXiv:2603.14607) uses Weighted Jaccard Similarity in the 43-97% range, not fidelity deviation. No source ever existed. Removed from flagship README, org profile, and `docs/architecture.md`. |
| NC-R002 | 630-snapshot floor projected date | ~2026-07-10 | 2026-08-30 | Superseded twice over. The projected date passed without the gate being met in any information-based unit, and the projection was built on the snapshot-count unit that #45 argues against and that NC-012 has now replaced with distinct device states (NC-023). Its inputs NC-009 and NC-011 are both 2026-05-25 measurements long overtaken. Re-derive from NC-023 if a projection is needed. The three documents still carrying `~2026-07-10` — `docs/advisor/2026-05-25-questions-for-akba.md`, `docs/findings/2026-05-25-empirical-synthesis.md`, `docs/roadmap/2026-05-25-cycle-2-plan.md` — are dated snapshots and are deliberately **left unedited**: they were accurate on 2026-05-25, and dated docs are reconciled by appending an as-of section, never by rewriting rows in place. |

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
