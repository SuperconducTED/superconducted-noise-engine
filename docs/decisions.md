# Architecture Decision Record (ADR) Ledger

We use a lightweight ADR convention here: ID, status, context, decision,
consequences. New decisions should be appended at the bottom and
referenced from the relevant code via comments and from the relevant
docs (especially `docs/architecture.md`).

**Statuses**: Accepted (locked, do not revisit), Open (in flux), Deferred
(known to be needed, not yet decided), Superseded (replaced by a later
ADR — link to its successor).

---

## ADR-001 — TSK over Mamdani

**Status**: Accepted.

**Context**: Two leading fuzzy-system architectures are TSK
(Takagi-Sugeno-Kang) with linear consequents and Mamdani with linguistic
output sets. ANFIS-style training is well-established for TSK and works
poorly for Mamdani.

**Decision**: TSK with first-order (linear) consequents, weighted-average
defuzzification (T1) or Nie-Tan closed-form (IT2). Mamdani is explicitly
out of scope.

**Consequences**: ANFIS hybrid recursive-LSE + SGD trainer is feasible
in NumPy/SciPy. No discrete output universe to maintain. Advisor
sign-off obtained.

---

## ADR-002 — Aer Factory/Ensemble pattern; no per-shot hook

**Status**: Accepted.

**Context**: Qiskit Aer's `NoiseModel.to_dict()` is called once at
submission and the C++ controller takes over. There is no callback for
per-shot Python re-entry.

**Decision**: Realize epistemic uncertainty at ensemble-construction
time. Build N distinct `FuzzyNoiseModel` instances and run AerSimulator
once per member. The Factory class is `FuzzyNoiseModelEnsemble`.

**Consequences**: Per-shot stochasticity comes from Aer's C++ engine;
fuzzy / epistemic uncertainty appears across ensemble members. Any
design that proposes per-shot Python regeneration of noise channels is
rejected on sight.

---

## ADR-003 — `qiskit-ibm-runtime` only

**Status**: Accepted.

**Context**: IBM has deprecated `qiskit-ibmq-provider` and
`qiskit-ibm-provider` in favor of `qiskit-ibm-runtime`. Mixing
deprecated SDKs invites authentication and channel-mismatch bugs.

**Decision**: Use only `qiskit-ibm-runtime`. The default channel is
`ibm_quantum_platform`; the legacy `ibm_quantum` channel is supported
as an explicit override for historical-property access tiers that
require it.

**Consequences**: Single auth flow; predictable failure modes. Future
SDK migrations are straightforward.

---

## ADR-004 — `src/` layout, hatchling, MIT

**Status**: Accepted.

**Context**: Need a dependable Python packaging story for a research
codebase that will eventually be public.

**Decision**: Standard `src/` layout, `pyproject.toml` (PEP 621) with
`hatchling` build backend, MIT license. `requirements.txt` /
`requirements-dev.txt` provide pinned development environments. No
Poetry, PDM, conda, or Docker.

**Consequences**: `pip install -e .` works on any modern Python
toolchain. Reproducible developer environments via the requirements
files; loose abstract deps in `pyproject.toml` for downstream consumers.

---

## ADR-005 — Hand-written ANFIS in NumPy/SciPy

**Status**: Accepted.

**Context**: PyTorch / TensorFlow / JAX would each pull in a heavy
dependency tree, and TSK/ANFIS training is a small bespoke algorithm
where the math is the point. The team also has limited bandwidth to
maintain a deep-learning toolchain.

**Decision**: Implement the trainer in NumPy + SciPy. No ML frameworks.

**Consequences**: Lighter deps. The trainer code itself becomes part of
the contribution rather than a thin wrapper.

---

## ADR-006 — Membership function shape

**Status**: Open.

**Context**: Gaussian and triangular MFs are baseline; trapezoidal is
common for plateau-with-uncertain-edges. The advisor recommended a
tanh-based shape for first-priority empirical testing.

**Decision (current)**: Bootstrap ships all four T1 shapes plus
`IntervalGaussianMF`. Empirical work to pick the winner is deferred.

**Consequences**: All shapes are interchangeable behind
`MembershipFunction`. The trainer (when written) operates on the flat
parameter vector.

---

## ADR-007 — Fuzzification placement

**Status**: Open.

**Context**: Aer's `NoiseModel.add_quantum_error` attaches errors *after*
the gate by default. Pre-gate and between-gate placements require
transforming the circuit (insert error-only instructions before each
target gate; or decompose the gate and interleave errors).

**Decision (current)**: Bootstrap implements `PostGateFuzzification`
fully. `PreGateFuzzification` and `BetweenGatesFuzzification` are stubs
raising `NotImplementedError`.

**Consequences**: Empirical comparisons across placements are blocked
until at least one of the deferred strategies lands.

---

## ADR-008 — Normalization strategy and SDP-solver dependency

**Status**: Open / Deferred.

**Context**: Three options: full CPTP projection (SDP), derivative-based
approximate normalization, or no-op (rely on CPTP-by-construction).
Bootstrap channels are CPTP by construction, so `NoOpNormalization`
suffices for now.

**Decision (current)**: Ship `NoOpNormalization` only.
`CPTPProjectionNormalization` and `DerivativeBasedNormalization` raise
`NotImplementedError`. The dependency choice (cvxpy vs. hand-rolled
scipy projection) is itself deferred until empirical work shows
non-CPTP candidate Kraus sets are worth the cost.

**Consequences**: No SDP-solver dependency at bootstrap. Straightforward
runtime; revisit before any non-CPTP-by-construction channel
construction lands.

---

## ADR-009 — T1 vs Interval Type-2

**Status**: Open.

**Context**: T1 fuzzy systems are simpler and cover the common case.
IT2 (Interval Type-2) carries an explicit footprint of uncertainty that
is the natural fit for "epistemic uncertainty in calibration drift."

**Decision (current)**: Both supported. Bootstrap concrete `IntervalGaussianMF`
demonstrates IT2 inference end-to-end. Empirical winner TBD.

**Consequences**: `MembershipDegree` carries low/high; `RuleFiringResult`
carries optional lower/upper bound arrays; `NieTanDefuzzifier` handles
the IT2 closed form.

---

## ADR-010 — Rule count and input variables

**Status**: Open.

**Context**: The pre-meeting baseline was a 3×3×3 grid (27 rules) over
three input dimensions. Which three is itself open.

**Decision (current)**: `BasicCalibrationVectorizer` outputs (mean_T1,
mean_T2, mean_readout_error) — the three currently most defensible
parameters per the team's domain knowledge.

**Consequences**: Adding more inputs is a `from_grid` argument away.
Adding more rules per input is the same.

---

## ADR-011 — Defuzzification method

**Status**: Open (effectively chosen for each path).

**Context**: T1 standard is weighted-average; IT2 Nie-Tan closed form
beats Karnik-Mendel iterative reduction in compute cost.

**Decision (current)**: Both implemented in
`superconducted.fuzzy.defuzzification`. Pick at config time based on
whether the rule base is IT2.

**Consequences**: No iterative numerical defuzzification at bootstrap.

---

## ADR-012 — Squashing / output activation

**Status**: Open.

**Context**: TSK output is a real-valued vector. Downstream channel
parameters often need [0, 1] (probabilities). Identity, clip, and
sigmoid each have trade-offs.

**Decision (current)**: All three implemented. `ProbabilityClip` is the
implicit default for noise-probability outputs. Sigmoid is preferred
inside an SGD trainer (differentiable).

**Consequences**: Strategy selectable per pipeline.

---

## ADR-013 — Calibration feature engineering

**Status**: Open / Deferred.

**Context**: `BasicCalibrationVectorizer` aggregates across all qubits.
Per-qubit, gate-grouped, or drift-rate-aware extractors might capture
more of the calibration drift signal.

**Decision (current)**: Bootstrap ships only `BasicCalibrationVectorizer`.
Richer extractors implement `CalibrationFeatureExtractor`.

**Consequences**: Future ADR will compare extractors empirically once
≥ 630 snapshots are accumulated.

---

## ADR-014 — TSK trainer architecture

**Status**: Deferred.

**Context**: Hybrid recursive-LSE for consequents + SGD for premise MF
parameters is the textbook ANFIS recipe. The bootstrap repository ships
`TSKRule` and `TSKRuleBase` only; the trainer lands separately.

**Decision (current)**: Defer until at least 630 calibration snapshots
are accumulated and a target-distribution definition exists.

**Consequences**: Bootstrap's `from_grid` initializes consequents to
zero. A model trained from scratch will need the trainer.

---

## ADR-015 — Ensemble sampling mechanism

**Status**: Deferred.

**Context**: `FuzzyNoiseModelEnsemble` currently yields N identical
models. Per-member perturbation could come from input-vector noise
(jiggle calibration features), premise-MF noise (perturb learned MF
parameters within their training-time variance), or IT2 footprint
sampling.

**Decision (current)**: Defer until ADR-009 is resolved (T1 vs IT2)
and ADR-014 has trained MFs whose training-variance is a meaningful
quantity.

**Consequences**: Bootstrap ensemble exists for API stability and to
let the harness exercise the full pipeline. Final epistemic-uncertainty
sampling lands later.

---

## ADR-016 — Benchmark aggregation across ensemble members

**Status**: Deferred.

**Context**: `simulate_engine` mean-aggregates counts at bootstrap.
Interval-valued predictions need a different aggregation (e.g. min/max
or quantile across members) to bracket real hardware behavior.

**Decision (current)**: Mean aggregation now; revisit once ADR-015
delivers actual per-member variation worth bracketing.

**Consequences**: Engine-vs-reference numbers at bootstrap are point
estimates, not intervals. Move past that once the ensemble is
non-trivial.

---

## ADR-017 — Missing per-qubit calibration fields: Skip strategy

**Status**: Accepted.

**Context**: Real IBM `properties()` responses occasionally omit per-qubit
`T1` and `T2` Nduv entries when the coherence measurement fails during the
calibration window. The exemplar at
`origin/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json`
shows this on qubit 72 of `ibm_fez`: the qubit is still in
`properties.qubits` with `readout_error`, `prob_meas0_prep1`,
`prob_meas1_prep0`, and `readout_length` intact, but the `T1` and `T2`
records are simply absent. Any code that does `qubit["T1"]` raises. We
considered three treatments — Skip (drop the qubit from aggregates),
Impute (fill from a population statistic), and Fuzzy (carry uncertainty
forward via a max-entropy footprint). Impute invents data and biases the
aggregate toward the population, which is wrong for the per-snapshot
view. Fuzzy is the right long-term answer but requires the
fuzzification layer (ADR-007 / ADR-009) to land first.

**Decision**: Bootstrap uses the **Skip** strategy. The typed loader
(`superconducted.calibration.loader.load_snapshot`) materializes every
per-qubit field as `Optional[float]`. A field is `None` when the Nduv
entry is absent from the raw JSON *or* present with a JSON-null value;
a field is `float('nan')` when the Nduv entry is present with a NaN
value. `MissingnessStats` on the snapshot carries one
`FieldMissingness` per tracked field; each `FieldMissingness` has
three disjoint counters (`absent`, `explicit_null`, `nan_present`) so
the distinction is preserved for diagnostics and for the eventual
migration to a fuzzy treatment. The mean-aggregate features
(`mean_t1`, `mean_t2`) exclude `None` and NaN entries from the average
and return `None` when no qubit has a usable value, rather than
raising — the caller decides whether to skip the snapshot.

**Consequences**: Aggregates are unbiased relative to the
population-impute alternative but lose statistical power proportional
to the missingness rate. Per-snapshot `MissingnessStats` are persisted
in-memory only; surfacing them through `BasicCalibrationVectorizer` and
through the eventual fuzzy layer is a follow-up. The existing
`BasicCalibrationVectorizer.extract` predates this ADR and remains
unchanged: it consumes the raw `properties` dict directly and is
unaffected as long as at least one qubit per field has a finite value.

`mean_t1` and `mean_t2` are currently free module-level functions in
`features.py`, not implementations of `CalibrationFeatureExtractor`.
This is intentional for the bootstrap: the Skip strategy reduces to a
one-liner arithmetic mean over `Optional[float]`, and wrapping it in an
ABC subclass would add layering without changing behaviour. A
follow-up will introduce
`SkipStrategyVectorizer(CalibrationFeatureExtractor)` once a second
consumer pattern emerges (e.g. when ANFIS training begins consuming
vectorized features alongside the mean aggregates).
