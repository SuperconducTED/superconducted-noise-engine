# Architecture

This is the canonical reference for how SuperconducTED is put together.
If a code change conflicts with this document, either the code is wrong
or this document needs an update — propose the update via PR alongside
the code change.

## Goal

Bracket real IBM-hardware behavior across calibration cycles with
interval-valued predictions. The competing benchmark is Bautra et al.
2026 (~0.686% fidelity deviation vs. real hardware on a fixed
calibration). SuperconducTED's distinctive contribution is
*transferability* across calibration cycles — Bautra and SimDisQ do not
address calibration drift, which is exactly what an Interval Type-2
fuzzy framing handles natively.

## The 6-stage pipeline

The TSK fuzzy pipeline takes one calibration snapshot in and produces
one set of `qiskit_aer.noise.QuantumError` instances out (one per
gate-qubit pair the target circuit uses).

```
+-----------------------------------------------------------------------+
|  Stage 1: Calibration ingestion                                       |
|    - IBM `BackendProperties` snapshot from `qiskit-ibm-runtime`       |
|    - Persisted as `CalibrationSnapshot` JSON via `CalibrationStorage` |
+--------------------------------+--------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------+
|  Stage 2: Feature extraction                                          |
|    - `CalibrationFeatureExtractor.extract(snapshot) -> ndarray`       |
|    - Bootstrap concrete: `BasicCalibrationVectorizer`                 |
|      → (mean_T1, mean_T2, mean_readout_error)                         |
+--------------------------------+--------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------+
|  Stage 3: Fuzzification + TSK rule firing                             |
|    - `MembershipFunction.degree(x)` per (rule, input dimension)       |
|    - `RuleBase.evaluate(inputs) -> RuleFiringResult`                  |
|    - LOCKED math in `fuzzy.tsk.TSKRuleBase`                           |
+--------------------------------+--------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------+
|  Stage 4: Defuzzification                                             |
|    - T1: `WeightedAverageDefuzzifier`                                 |
|    - IT2: `NieTanDefuzzifier` (closed-form)                           |
+--------------------------------+--------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------+
|  Stage 5: Squashing                                                   |
|    - `SquashingStrategy.squash(raw) -> crisp params`                  |
|    - Bootstrap concretes: Identity, ProbabilityClip, Sigmoid          |
+--------------------------------+--------------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------------+
|  Stage 6: Channel projection                                          |
|    - `ChannelProjector.project(crisp, gate_name, qubits)`             |
|      → `qiskit_aer.noise.QuantumError`                                |
|    - LOCKED CPTP math in `channels.kraus`                             |
+-----------------------------------------------------------------------+
```

## Aer integration: Factory + Ensemble

```
                  +-------------------------+
                  |  CalibrationSnapshot    |
                  |  (one per polling tick) |
                  +-----------+-------------+
                              |
                              v
        +------------------+  |  +-------------------------+
        |  Pipeline above  | -+  |  Sampling perturbations |  (ADR-015)
        +------------------+  |  +-------------+-----------+
                              |                |
                              v                v
                +---------------------------------------+
                | FuzzyNoiseModelEnsemble (size N)      |
                |   yields N × FuzzyNoiseModel          |
                +-----+----------+-------+--------------+
                      |          |       |
                      v          v       v
          AerSimulator.run()  ...  ...  AerSimulator.run()
                      |          |       |
                      v          v       v
                  counts_1   counts_2   counts_N
                              |
                              v
                +-----------------------------+
                | Interval-valued aggregation |  (ADR-016)
                +-----------------------------+
```

## The no-per-shot-hook invariant

Aer's `AerSimulator` calls `NoiseModel.to_dict()` exactly once at
submission time
([`qiskit_aer/backends/backend_utils.py:cpp_execute_circuits`](https://github.com/Qiskit/qiskit-aer/blob/main/qiskit_aer/backends/backend_utils.py))
and the C++ controller takes over. There is no callback, generator, or
hook for per-shot Python re-entry into the noise model.

**Consequence.** Sample-level (epistemic) uncertainty must be realized
*at ensemble construction time*, not *at simulation time*. Any proposed
architecture that intercepts individual shots in Python is wrong by
construction. If a future contributor reaches for one, stop and re-read
this section.

This is the architectural reason `FuzzyNoiseModelEnsemble` exists at all:
each ensemble member is a regular `NoiseModel` that Aer can serialize
once; per-shot stochasticity comes from Aer's own C++ engine, while
fuzzy / epistemic uncertainty manifests across ensemble members.

## Calibration polling

The `superconducted-poll` console script archives `BackendProperties`
snapshots so the team accumulates the ≥630 historical records needed
for ANFIS training (≈ 126 trainable parameters × 5× rule of thumb).

- **Cadence**: cron-driven; one invocation per polling round. The
  script does NOT schedule itself. Recommended bootstrap cadence: every
  4 hours per backend. IBM updates calibration tables roughly that
  often.
- **Idempotency**: filename-based via UTC ISO-compact timestamps.
  `O_CREAT|O_EXCL` makes the write race-safe across concurrent cron
  invocations.
- **Failure handling**:
  - `NotImplementedError` (historical access tier denied): log + skip,
    exit 0.
  - `properties()` returns `None`: log + skip, exit 0.
  - Transient `RuntimeError`: exponential-backoff retry up to
    `SUPERCONDUCTED_HTTP_RETRIES` (default 3).
  - Auth errors: exit 1.
- **Schema**: `CalibrationSnapshot` carries `properties` (the JSON of
  `BackendProperties.to_dict()`), plus reduced JSON projections of the
  current `target` and `configuration`. For historical snapshots,
  `target_history(datetime=...)` is used when the SDK exposes it;
  otherwise `target` and `configuration` are stored as `None` to avoid
  pairing the current target with historical properties.

## Open decisions cross-reference

| Decision | ABC | Bootstrap default | Alternatives |
| --- | --- | --- | --- |
| ADR-006 MF shape | `MembershipFunction` | Tanh | Gaussian, Triangular, Trapezoidal, IntervalGaussian |
| ADR-007 Fuzzification placement | `FuzzificationStrategy` | PostGate (Aer default) | Pre / Between (deferred) |
| ADR-008 Normalization | `NormalizationStrategy` | NoOp (CPTP-by-construction) | CPTPProjection (SDP), DerivativeBased (deferred) |
| ADR-009 T1 vs IT2 | `MembershipFunction.is_interval_type2` | T1 | IT2 (`IntervalGaussianMF`) |
| ADR-010 Rule count | `RuleBase` | 27 (3×3×3 grid) | TBD |
| ADR-011 Defuzzification | `Defuzzifier` | T1 weighted average / IT2 Nie-Tan | TBD |
| ADR-012 Squashing | `SquashingStrategy` | ProbabilityClip | Identity, Sigmoid |
| ADR-013 Calibration features | `CalibrationFeatureExtractor` | BasicCalibrationVectorizer | per-qubit, drift-aware (deferred) |
| ADR-014 TSK trainer | (in `fuzzy.tsk`) | none — manual params | hybrid LSE + SGD ANFIS |
| ADR-015 Ensemble sampling | (in `integration.aer_factory`) | identical (no perturbation) | input-vector / MF / IT2 perturbation |
| ADR-016 Benchmark aggregation | (in `benchmarks.harness`) | mean | interval-valued |
