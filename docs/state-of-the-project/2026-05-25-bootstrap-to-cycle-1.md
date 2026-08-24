# State of the Project · Bootstrap to Cycle 1

## Preface

This document summarizes the state of the SuperconducTED noise engine at the close of development cycle 1 (2026-05-07 through 2026-05-25). It is written for internal team members and covers what has been built, what decisions have been recorded, and where the project stands. Three companion documents complete the synthesis: an empirical findings consolidation at `docs/findings/2026-05-25-empirical-synthesis.md`, a forward-looking cycle 2 plan at `docs/roadmap/2026-05-25-cycle-2-plan.md`, and a standalone questions document for Dr. Akba at `docs/advisor/2026-05-25-questions-for-akba.md`.

## Bootstrap

The repository was created from scratch on 2026-05-07. The bootstrap delivered nine abstract base classes defining swappable research axes across calibration ingestion, feature extraction, fuzzification, TSK inference, defuzzification, squashing, channel projection, benchmarking, and Aer integration. Two modules were locked from the start: `fuzzy/tsk.py` (TSK rule firing) and `channels/kraus.py` (Kraus operator channel construction). The calibration polling script shipped on day one to begin accumulating the 630+ snapshots needed for ANFIS training.

Sixteen architecture decision records (ADR-001 through ADR-016) were created during bootstrap, covering the TSK architecture choice, the ensemble uncertainty model, the IBM provider dependency, packaging, MF shapes, fuzzification placement, normalization, defuzzification methods, squashing, feature extraction, and the trainer and aggregation deferrals. A full CI pipeline (ruff, mypy, pytest) was configured. For detail, see `docs/implementations/2026-05-07-repo-bootstrap.md`.

## Cycle 1 Engineering Arcs

### Calibration Poller Cron Deployment

PRs #7, #8, #12, and #17 deployed the existing `superconducted-poll` CLI as an hourly GitHub Actions cron workflow. The workflow polls the `ibm_fez` backend at minute `:37` past the hour, commits each new calibration snapshot to the long-lived orphan `calibration-data` branch, and fails loudly on zero-file runs. The timeout was tightened from 55 to 10 minutes. Multi-backend polling is deferred. See `docs/implementations/2026-05-13-calibration-poller-cron.md`.

### Harness Validation

PR #10 added 15 boundary and property tests for the four core benchmark metrics (Hellinger distance, KL divergence, state fidelity, R² score). The tests validate six properties defined in ADR-022: identity, symmetry or asymmetry, bounds, monotonicity, determinism, and reference-value correctness. This was additive test coverage only with no production code changes. See `docs/implementations/2026-05-13-harness-metric-sanity-checks.md`.

### Aer Integration Walkthrough and First Ensemble Run

PR #13 rewrote the ensemble smoke harness to use real bootstrap concretes with feature-specific MF scaling, replacing prior mock-based runs that had produced invalid latency measurements. The walkthrough confirmed that Aer does not support per-shot Python callbacks · the noise model is serialized to C++ once and the Factory/Ensemble pattern is the only viable integration path for per-model variance. Post-simulator-hoist latency: N=1 at 0.07s, N=8 at 0.91s, N=16 at 1.89s. See `docs/implementations/2026-05-14-aer-ensemble-walkthrough.md` and `docs/findings/aer-integration-walkthrough.md`.

### Typed Calibration Loader with Skip Strategy

PR #16 added a typed calibration snapshot loader (`load_snapshot`) with `ParsedCalibrationSnapshot`, `ParsedQubitCalibration`, and `MissingnessStats` dataclasses that distinguish absent, explicit-null, and NaN calibration fields. The Skip strategy drops missing values from the arithmetic mean rather than imputing or raising. The strategy was validated on the `ibm_fez` qubit-72 exemplar where T1 and T2 are absent. ADR-017 documents the decision. See `docs/implementations/2026-05-16-loader-missing-fields.md`.

### First ADR Cycle Audit

The audit reviewed all 16 original ADRs against current code and documentation. It found two drifts (ADR-006 tanh slope enforcement present in code but absent from ADR text · ADR-016 mean-vs-sum aggregation semantics diverging across harness, smoke script, and documentation), surfaced three ambiguities, and proposed six new draft ADRs (ADR-017 through ADR-022). Eight follow-up issues were drafted with priority assignments. See `docs/audits/2026-05-25-first-cycle-audit.md` and `docs/audits/2026-05-25-followup-issues.md`.

## ADR Cycle Summary

| ADR | Status | Summary |
|-----|--------|---------|
| ADR-001 | Accepted | TSK fuzzy system architecture for ANFIS-compatible training |
| ADR-002 | Accepted | Ensemble-level epistemic uncertainty via multiple FuzzyNoiseModel instances |
| ADR-003 | Accepted | qiskit-ibm-runtime as sole IBM provider dependency |
| ADR-004 | Accepted | Standard src/ layout with hatchling build backend and MIT license |
| ADR-005 | Accepted | Hand-written ANFIS trainer in NumPy and SciPy only |
| ADR-006 | Open | Bootstrap MF shapes shipped · empirical winner selection deferred |
| ADR-007 | Open | PostGateFuzzification implemented · pre-gate and between-gates stubs |
| ADR-008 | Deferred | NoOpNormalization only · CPTP projection and SDP solver deferred |
| ADR-009 | Open | T1 and IT2 both supported · empirical winner TBD |
| ADR-010 | Open | BasicCalibrationVectorizer with three-input 3×3×3 rule grid baseline |
| ADR-011 | Open | Weighted-average defuzzification (T1) and Nie-Tan closed form (IT2) |
| ADR-012 | Accepted | Three squashing strategies · ProbabilityClip is the noise probability default by the pipeline convention|
| ADR-013 | Deferred | BasicCalibrationVectorizer only · richer extractors need 630+ snapshots |
| ADR-014 | Deferred | TSK trainer deferred until 630-snapshot floor and target-distribution definition |
| ADR-015 | Deferred | Ensemble per-member perturbation deferred · three candidate approaches identified |
| ADR-016 | Deferred | Mean aggregation at bootstrap · interval-valued aggregation deferred |
| ADR-017 | Accepted | Skip strategy for missing per-qubit calibration fields |
| ADR-018 | Draft | Tanh slope positivity convention for all tanh-based MFs |
| ADR-019 | Open | MF ablation methodology with reproducible benchmark protocol |
| ADR-020 | Accepted | Calibration snapshot schema and orphan-branch storage layout |
| ADR-021 | Accepted (constraint) / Open (variance-injection) | Aer integration constraint and Factory/Ensemble dependency-injection pattern |
| ADR-022 | Accepted | Benchmark validation criteria with six mandatory metric properties |

Two ADRs were revisited during the audit: ADR-006 (tanh slope enforcement found in code but not in ADR text · draft ADR-018 created for formalization) and ADR-016 (implementation uses element-wise sum with scaled shots, probability-equivalent to mean under normalized metrics but not raw-count mean). See the audit report for drift details.

## Where We Are Now

### Capabilities

| Capability | Status |
|------------|--------|
| Hourly IBM Quantum calibration polling from `ibm_fez` | Operational |
| Calibration snapshot storage on orphan `calibration-data` branch | Operational |
| CI pipeline (ruff, mypy, pytest) | Operational |
| Typed calibration snapshot loading with absent/null/NaN distinction | Implemented |
| Mean calibration feature extraction (T1, T2, readout_error) | Implemented |
| Skip strategy for missing calibration fields | Implemented |
| Full TSK inference pipeline (fuzzification, rule firing, defuzzification, squashing, channel projection) | Implemented |
| FuzzyNoiseModel construction from calibration data via dependency injection | Implemented |
| Degenerate ensemble execution through AerSimulator | Implemented |
| Benchmark comparison with four validated metrics (Hellinger, KL, fidelity, R²) | Implemented |
| Metric validation against six property tests (15 tests total) | Tested |

### Gaps

| Gap | Gating Decision |
|-----|-----------------|
| Per-member ensemble variance (non-degenerate ensemble) | ADR-015 |
| Trained membership functions via ANFIS | ADR-014 |
| MF shape empirical comparison and winner selection | ADR-019 |
| T1 vs IT2 empirical winner | ADR-009 |
| Real-hardware reference comparisons | Hardware access |
| CPTP normalization and projection | ADR-008 |
| Pre-gate and between-gates fuzzification strategies | ADR-007 |
| Multi-backend calibration polling | ADR-020 scope extension |
| Richer calibration feature extractors | ADR-013 |

## Team and Ownership

See `docs/team.md` for the full contributor list and module ownership map.

## Companion Documents

- Empirical findings synthesis · `docs/findings/2026-05-25-empirical-synthesis.md`
- Cycle 2 plan and roadmap · `docs/roadmap/2026-05-25-cycle-2-plan.md`
- Questions for Dr. Akba · `docs/advisor/2026-05-25-questions-for-akba.md`
