# Empirical Synthesis · End of Cycle 1

## Preface

This document consolidates all empirical measurements and findings accumulated during cycle 1 of the SuperconducTED noise engine (2026-05-07 through 2026-05-25). The project has measured Aer simulator latency scaling, validated benchmark metric correctness against six properties, begun accumulating calibration snapshots toward the ANFIS training floor, characterized missing-field handling via the Skip strategy, and observed degenerate-ensemble aggregation behavior. The project has not yet measured per-member variance, MF shape comparison fidelity, real-hardware reference deviations, or trained MF performance. This document is the empirical reference the team cites when writing the IEEE QCE article.

## What Is Measured

### Aer Latency Scaling

Post-simulator-hoist measurements from `docs/findings/aer-integration-walkthrough.md`, taken at commit `4006f6c` with one shared `AerSimulator` instance warmed with 1 shot before the timed loop. Each member runs 1024 shots.

| Ensemble Size (N) | Latency | Per-Member Cost |
|--------------------|---------|-----------------|
| 1 | 0.07s | 0.07s (includes warmup) |
| 8 | 0.91s | ~0.12s |
| 16 | 1.89s | ~0.118s |

Latency scales O(N) in ensemble members. Each additional member pays the cost of transpilation plus a fresh `NoiseModel` install on the shared simulator instance. These measurements are from the corrected harness that uses real bootstrap concretes with feature-specific MF scaling · prior measurements using mocked components were discarded as synthetic microbenchmarks.

The per-member cost (~0.12s) consists of `transpile(circuit, backend=sim)` plus `NoiseModel` serialization to C++ via `NoiseModel.to_dict()`. The `AerSimulator` is hoisted and reused across members · constructing a new simulator per member would add additional overhead.

### Harness Metric Correctness

The benchmark harness exposes four metrics: Hellinger distance, KL divergence, state fidelity, and R² score. PR #10 added 15 boundary and property tests validating six properties defined in ADR-022:

| Property | What It Tests |
|----------|---------------|
| Identity | Metric returns its identity value (0.0 or 1.0) when comparing a distribution to itself |
| Symmetry / Asymmetry | Hellinger and fidelity are symmetric · KL divergence is asymmetric |
| Bounds | Every metric output falls within its documented range |
| Monotonicity | Metric moves in the expected direction as distributions diverge |
| Determinism | Identical inputs produce identical outputs across repeated calls |
| Reference Value | Maximally divergent distributions produce the expected extreme value |

All 15 tests pass. Tests use real `SimulationResult` frozen dataclasses with fixed seeds and 3-sigma tolerances · no mocks. KL divergence uses additive smoothing with epsilon = 1e-12. The R² implementation returns 0.0 when `ss_tot = 0` (constant-mismatch fallback).

### Calibration Snapshot Ingestion

The calibration poller runs hourly at minute `:37` on a single backend (`ibm_fez`). Snapshots are stored on the orphan `calibration-data` branch with path `snapshots/YYYY-MM/<backend>/<ISO8601-timestamp>.json`. Authentication uses `IBM_QUANTUM_TOKEN` stored in GitHub Secrets.

As of 2026-05-25, the `calibration-data` branch holds 127 snapshots accumulated since 2026-05-13T12:13:22Z. Sustained cadence is ~11.1 snapshots per day · approximately 46% of the theoretical hourly maximum. The shortfall is documented in the open GitHub Actions scheduler issue (cron tick drop rate). At sustained cadence, the 630-snapshot ANFIS training floor (ADR-014) is projected for ~2026-07-10. The workflow timeout is 10 minutes per run; no operational gap larger than 7200 seconds is expected under normal operation.

### Missing-Field Handling

The typed calibration loader validates missing-field behavior via the `ibm_fez` qubit-72 exemplar, where T1 and T2 are absent. The observed missingness rate for T1 on this snapshot is 1 out of 156 qubits (~0.64%).

The Skip strategy produces correct arithmetic means by excluding missing and NaN entries from the denominator. `MissingnessStats` distinguishes three categories:

| Category | JSON Representation | Typed Field Value |
|----------|--------------------|--------------------|
| Absent | Key does not appear | `None` |
| Explicit null | Key exists with `null` | `None` |
| NaN | Key exists with `NaN` float | `float('nan')` |

Absent and explicit-null values collapse to `None` on the typed field, while `NaN` is preserved as `float('nan')`; the distinction among all three categories is also preserved in `MissingnessStats` for downstream analysis. Time fields are scaled to SI seconds at load time (1e-6 for microsecond sources, 1e-9 for nanosecond sources). Unit mismatches raise `CalibrationParseError` rather than silently drifting.

### Mean Aggregation Under Degenerate Ensemble

At bootstrap, `FuzzyNoiseModelEnsemble` yields N identical members (ADR-015 defers per-member perturbation). Under this degenerate ensemble, mean aggregation produces output equivalent to a single member.

Two aggregation implementations exist:

| Implementation | Location | Method | Artifact |
|---------------|----------|--------|----------|
| Canonical harness | `benchmarks/harness.py` | Element-wise sum via `Counter.update()` with `shots = shots_per_member * len(members)` | Probability-equivalent to mean under normalized metrics |
| Smoke script | `scripts/first_ensemble_run.py` | True mean via `round(v/n)` with per-key rounding | `sum(returned.values())` can differ from total shots by at most 1 count per bin |

Under normalized metrics (Hellinger, KL divergence, fidelity, R²), the harness's element-wise-sum approach and the smoke script's true-mean approach produce identical results. Under raw-count comparison, the two approaches diverge due to the rounding artifact.

## What Is Not Measured Yet

### Per-Member Variance

The degenerate ensemble produces identical members · there is no per-member variance to measure. ADR-015 identifies three candidate perturbation mechanisms: input-vector noise injection, premise-MF parameter perturbation, and IT2 footprint sampling. Measurement of per-member variance is blocked until ADR-015 resolves, which is gated by ADR-009 (T1 vs IT2 winner) and ADR-014 (trained MFs with meaningful parameter variance).

### MF Shape Comparison

No empirical comparison of MF shapes (Gaussian, triangular, trapezoidal, tanh-based) has been conducted. ADR-019 defines the ablation protocol (four benchmark circuits, single snapshot, 4096 shots, ensemble size 8, Gaussian baseline) but execution is blocked until PR #14 merges (adding `TanhSigmoidMF` and `TanhBellMF`) and non-trivial MF parameters are available from the trainer (ADR-014) or manual parameterization.

### Real-Hardware Reference

No real-hardware quantum circuit executions have been run to compare against the fuzzy noise model's predictions. ADR-022 acknowledges this deferral. Validation against real hardware requires IBM backend access for executing the same benchmark circuits that the harness runs in simulation.

### Trained Membership Functions

No MFs have been trained via ANFIS. The trainer is deferred (ADR-014) until the 630-snapshot floor is reached (~2026-07-10) and a target-distribution definition exists. All current MF parameters are bootstrap defaults (from-grid initialization with zero consequents).

## Known Ambiguities

### Mean-vs-Sum Aggregation

ADR-016 text, `benchmarks/harness.py` code, the smoke script, and module docstrings give three different descriptions of ensemble aggregation semantics. The harness performs element-wise sum with scaled total shots · probability-equivalent to mean under normalized metrics but not raw-count mean. The smoke script performs true mean via `round(v/n)` with per-key rounding artifact. The `harness.py` module docstring (line 3) and `docs/architecture.md` (line 161) describe the behavior as "mean." These are tracked as follow-up issues: P0 for ADR-016 text/implementation alignment, P1 for docstring and architecture doc updates.

### `make_state` Type Hint

The `make_state` function's type hint advertises `float | complex` return type, but only `float` values appear in all test fixtures and call sites. Whether the function should accept complex amplitudes or the type hint should narrow to `float` is unresolved.

### Stale Cron Timing in Implementation Doc

`docs/implementations/2026-05-13-calibration-poller-cron.md` records the cron schedule as minute `:05`, but the actual schedule is `:37` since PR #17. Whether to add a dated addendum or leave the document as a historical record of the original deployment is undecided.

## Implications for the IEEE QCE Article Track

### What We Can Claim Today

The project can claim a working end-to-end pipeline from IBM Quantum calibration data through TSK fuzzy inference to Aer noise model construction and benchmark comparison. The claims are supported by:

- Pipeline architecture with nine swappable research axes, documented in 22 ADRs
- Benchmark metrics validated against six properties with 15 tests
- Aer integration constraint (no per-shot callbacks · ensemble is load-bearing) empirically confirmed
- Latency scaling characterized as O(N) with ~0.12s per additional ensemble member
- Missing-field robustness demonstrated via Skip strategy on real calibration data

### What We Cannot Claim Yet

- Noise model accuracy · the ensemble is degenerate, MFs are untrained, no real-hardware reference exists
- Preferred MF shape · the ablation protocol is defined (ADR-019) but unexecuted
- Uncertainty quantification · ADR-015 (per-member perturbation) is deferred
- Superiority over competing approaches · no comparative evaluation against published baselines has been conducted

### Dataset Accumulation Curve

At ~11.1 snapshots per day from a single backend (`ibm_fez`) · 46% of the theoretical hourly maximum due to GitHub Actions scheduler drops · the 630-snapshot ANFIS training floor is projected for ~2026-07-10. The critical path to article-ready results:

1. 630-snapshot floor reached · ~2026-07-10
2. TSK trainer implementation (ADR-014) · unblocked after step 1
3. MF ablation execution (ADR-019) · unblocked after PR #14 merge plus step 2
4. Per-member perturbation resolution (ADR-015) · unblocked after ADR-009 plus step 2
5. Non-degenerate ensemble measurements · unblocked after step 4
6. Real-hardware reference comparison · unblocked by IBM backend access (independent of steps 1-5)
