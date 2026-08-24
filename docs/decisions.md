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

**Status**: Accepted.

**Context**: Gaussian and triangular MFs are baseline; trapezoidal is
common for plateau-with-uncertain-edges. The advisor recommended a
tanh-based shape for first-priority empirical testing.

**Decision (current)**: Bootstrap ships the T1 shapes Gaussian,
triangular, trapezoidal, and `TanhMF`, plus `IntervalGaussianMF`,
`TanhSigmoidMF`, and `TanhBellMF`. Empirical-winner selection among these shapes is handed off to ADR-019 (MF-shape ablation).

**Consequences**: All shapes are interchangeable behind
`MembershipFunction`. The trainer (when written) operates on the flat
parameter vector.

> Revisited · 2026-05-25 · Tanh slope positivity is governed by ADR-018, which is Accepted in the ledger.

> See ADR-018 for the slope-positivity convention that extends this
> decision for `TanhSigmoidMF` and `TanhBellMF`.
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

**Decision (current)**: Prefer IT2 provisionally while keeping T1 supported.
Bootstrap concrete `IntervalGaussianMF` already demonstrates IT2 inference end-to-end, and
this direction aligns with uncertainty being realized at ensemble construction time in
`src/superconducted/integration/aer_factory.py` (see module docstring; per-member sampling is deferred to ADR-015).
This direction is provisional pending the ADR-019 MF-shape ablation; empirical confirmation is planned (target ~2026-07-19), not yet measured.
Confirm if ADR-019 shows IT2's explicit uncertainty envelope materially improves calibration-drift robustness versus T1; overturn if the ablation shows no such benefit or if T1 simplicity is more defensible.
Downstream: ADR-011, ADR-015, and ADR-021 follow once this direction reaches Accepted and are out of scope here.

**Consequences**: `MembershipDegree` carries low/high; `RuleFiringResult`
carries optional lower/upper bound arrays; `NieTanDefuzzifier` handles
the IT2 closed form.

---

## ADR-010 — Rule count and input variables

**Status**: Accepted.

**Context**: The pre-meeting baseline was a 3×3×3 grid (27 rules) over
three input dimensions. Which three those are is now settled: `mean_T1`,
`mean_T2`, and `mean_readout_error`.

**Decision (current)**: The baseline rule grid is 3×3×3 — 27 rules, one
per Cartesian-product combination as built by `TSKRuleBase.from_grid`
(`prod_i K_i` rules for `K_i` MFs on input `i`; `K_i = 3` on each of the
3 dimensions gives 3 × 3 × 3 = 27). The three input dimensions are
`mean_T1`, `mean_T2`, and `mean_readout_error`, as produced by
`BasicCalibrationVectorizer` (`output_dim` 3) — the three currently most
defensible parameters per the team's domain knowledge. `from_grid` is
already parameterized per dimension, so a different arity is a
configuration change at the call site, not a code change to the LOCKED
`fuzzy/tsk.py`. This ADR ratifies the baseline only; ADR-013 remains free
to propose and compare alternative dimension sets against it.

**Consequences**: Adding more inputs is a `from_grid` argument away.
Adding more rules per input is the same.

> Ratified · 2026-08-19 · Both halves confirmed by reading the shipped
> code: `_FEATURE_NAMES` (`calibration/features.py:23`) for the three
> dimensions, and the `itertools.product` construction in `from_grid`
> (`fuzzy/tsk.py:185-224`) for the 27-rule arity. The LOCKED `tsk.py` was
> read, not modified; Burak Öztekin signed off as its primary owner. See
> `docs/implementations/2026-08-19-adr-010-closure.md`.

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

> Revisited · 2026-05-25 · The text above says "mean-aggregates counts."
> The canonical harness (`benchmarks/harness.py:simulate_engine`) does
> element-wise sum via `Counter.update()` with
> `shots = shots_per_member * len(members)`. This is
> probability-equivalent to mean-aggregation under current normalized
> metrics (Hellinger, KL, fidelity, R-squared), which divide by total
> counts. It is not mean-aggregation of raw counts. The smoke script
> (`scripts/first_ensemble_run.py:run_ensemble`) truly mean-aggregates
> via `round(v / n)`, and per-key rounding can leave
> `sum(returned.values())` differing from `shots` by up to one count
> per bin. The `harness.py` module docstring (line 3) and
> `docs/architecture.md` (line 161) also describe the behavior as
> "mean" — these are tracked as follow-up issues since they are outside
> `docs/decisions.md`. Status remains Deferred.

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

---

## ADR-018 — Tanh membership-function slope positivity convention

**Status**: Accepted.

**Context**: PR #14 added `TanhSigmoidMF` (`center`, `slope`) and
`TanhBellMF` (`left`, `right`, `slope`) to
`src/superconducted/fuzzy/membership.py`, extending the tanh-based MF
family enumerated in ADR-006. Both shapes are parameterized so that
`slope <= 0` is degenerate or actively dangerous:

- `TanhSigmoidMF.degree`: `mu(x) = (tanh(slope * (x - center)) + 1) / 2`.
  At `slope = 0` this collapses to the constant `0.5` everywhere — the
  shape carries no information. A negative slope flips the monotonic
  direction of the sigmoid silently.
- `TanhBellMF.degree`: `mu(x) = (tanh(slope * (x - left)) - tanh(slope
  * (x - right))) / 2`. With `left < right`, a non-positive slope
  inverts the bell and drives the raw value toward `-1`, which violates
  `MembershipDegree`'s `0 <= low <= high <= 1` invariant — this is not
  a cosmetic issue, it raises downstream.

An earlier draft of this ADR (`docs/decisions/drafts/ADR-018-tanh-slope-positive-convention.md`,
status Draft, written against the proposed PR #14 design) framed the
risk as `clip(0, 1)` silently masking an invalid configuration. The
merged implementation took the stronger position: reject at
construction time rather than clip and mask.

**Decision**: Both `TanhSigmoidMF` and `TanhBellMF` require strictly
positive slope — `slope > 0`, not `slope >= 0` — because zero is
exactly as degenerate as negative (it destroys the shape rather than
inverting it) and is rejected by the same check, not a separate one.
`_validate` raises `ValueError` on `slope <= 0` and `TanhBellMF._validate`
additionally rejects `left >= right`. Both checks run again inside
`set_parameters`, so a valid MF cannot be mutated into an invalid one
after construction. No clipping is implemented anywhere in either
class; out-of-domain parameters are a construction-time error, not a
runtime silent clamp. Pinning the sign also keeps gradient direction
well-defined for the future ANFIS trainer (ADR-014) — a parameter
whose sign can flip the shape's orientation has no consistent gradient
semantics.

Neither shape has a plateau parameter. Unlike `TrapezoidalMF`, which
encodes "plateau with uncertain edges" via an explicit flat-top region
(ADR-006), `TanhSigmoidMF` and `TanhBellMF` are smooth single-valued
tanh curves with no flat segment — saturation is asymptotic, not a
hard plateau. `TanhBellMF`'s peak at band center is therefore strictly
below `1.0` for any finite slope: at `slope = 2.0` and a span
(`right - left`) of `6`, the closed-form peak is
`(tanh(6) - tanh(-6)) / 2 ≈ 0.99998771`, and the gap from `1.0` grows
as `slope * (right - left)` shrinks. This sub-unit-peak behavior is
documented and tested at the `slope = 2.0` case
(`tests/test_membership.py:194-200`); no test exercises a small-slope
case where the gap from `1.0` is large, which is a gap in coverage, not
in the decision.

Both classes report `is_interval_type2 -> False`. They are Type-1 MFs
only — neither exposes an upper/lower footprint-of-uncertainty pair or
an `is_upper`-style parameter, in contrast to `IntervalGaussianMF`.
Whether either tanh shape gets an IT2 variant is unresolved and tracked
under ADR-009 (T1 vs IT2), not here.

**Consequences**: The ANFIS trainer (ADR-014), when implemented, must
constrain the premise-parameter search space for any tanh-based MF to
positive slopes — a log-space or exponentiated reparameterization keeps
gradient-based optimization inside the valid domain during training,
rather than relying on post-hoc clamping. Any future tanh-based MF
subclass is expected to follow the same strict-positive convention and
to re-validate in `set_parameters`. The rule base (`TSKRuleBase`)
itself is unaffected — this is a premise-parameter constraint, not a
consequent or rule-structure change.

**Source**: PR #14 (merged to `main`; commits `ccdade0`, `07ee487`),
review thread on `membership.py` (Copilot flagged the `set_parameters`
validation gap; human review identified the `MembershipDegree`
invariant violation as a blocker, resolved by adding the strict checks
above), `tests/test_membership.py` (`test_tanh_sigmoid_invalid_slope`,
`test_tanh_sigmoid_set_parameters_validates`,
`test_tanh_bell_invalid_params`), Issue #2. Supersedes the Draft-status
text in `docs/decisions/drafts/ADR-018-tanh-slope-positive-convention.md`.

> See ADR-006 for the broader MF-shape enumeration this ADR extends.
