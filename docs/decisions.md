# Architecture Decision Record (ADR) Ledger

We use a lightweight ADR convention here: ID, status, context, decision,
consequences. New decisions should be appended at the bottom and
referenced from the relevant code via comments and from the relevant
docs (especially `docs/architecture.md`).

**Statuses**: Accepted (locked, do not revisit), Open (in flux), Deferred
(known to be needed, not yet decided), Superseded (replaced by a later
ADR — link to its successor).

An ADR that settles one half of a question while leaving another half in
flux carries a **split status** naming both halves (see ADR-021), and
splits its decision text into a `**Decision (Accepted)**` part and a
`**Decision (Open)**` part so the locked half is unambiguous.

Some ADRs are authored as standalone files under `docs/decisions/drafts/`
before landing here. **This ledger is canonical.** A draft that has been
promoted stays in `drafts/` as the authoring record, and the promoted
entry says so. An ID that appears only in `drafts/` has not been decided
and must not be cited elsewhere as though it carried a status.

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
> See ADR-023 for the output-range convention and `TanhMF`'s floor
> exemption. The 2026-05-25 revisit note removed by PR #26 had two
> halves: the slope half is governed by ADR-018 as the line above says,
> and the clip half is resolved in ADR-023.
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

---

## ADR-019 — Membership function ablation methodology

**Status**: Open.

**Context**: The advisor (Dr. Akba) recommended a tanh-based MF shape
as first-priority empirical test against the Gaussian baseline. Four T1
shapes are implemented at bootstrap (Gaussian, Triangular, Trapezoidal,
Tanh) plus `IntervalGaussianMF` for the IT2 path. ADR-006 defers the
empirical winner selection.

Issue #2 specifies `TanhSigmoidMF` and `TanhBellMF` as additional
candidates. The full ablation requires a comparison protocol that is
reproducible and covers the metrics formalized in the benchmark harness
(Hellinger distance, KL divergence, state fidelity, R-squared).

No ablation protocol is currently documented. Without one, each
contributor would run ad-hoc comparisons with different circuits, shot
counts, and noise configurations, producing non-comparable results.

**Decision (current)**: The ablation protocol for MF shape selection is:

1. **Fixed benchmark suite**: Use the four existing benchmark circuits
   (random Clifford, GHZ, QFT, `efficient_su2` ansatz).
2. **Fixed calibration snapshot**: Use a single representative snapshot
   from the `calibration-data` branch (timestamp and backend recorded
   in the results table).
3. **Fixed shot count**: 4096 shots per ensemble member, ensemble
   size N = 8, chosen for runtime.
4. **All four metrics**: Report Hellinger, KL, fidelity, and R-squared
   for each (MF shape, circuit) pair.
5. **Baseline**: Gaussian MF with the bootstrap `from_grid` default
   parameterization.
6. **Reproducibility**: Fixed random seed. Script committed to
   `scripts/`. Results table committed to `docs/findings/`.

The winner is the shape that minimizes Hellinger distance (primary) and
maximizes fidelity (secondary) across the benchmark suite relative to a
real-hardware reference distribution. If no real-hardware reference is
available at comparison time, the comparison is against an Aer
simulation with the same circuit and a known-good noise model.

**Consequences**: The ablation is blocked until (a) PR #14 lands
`TanhSigmoidMF` and `TanhBellMF`, and (b) the trainer (ADR-014) or a
manual parameterization provides non-trivial MF parameters for each
candidate shape. The protocol must be re-evaluated if the metric set
changes (e.g., if trace distance or diamond norm is added).

> Gate status · as-of 2026-08-20 · Prerequisite (a) is CLEARED: PR #14
> merged to `main` (commits `ccdade0`, `07ee487`), landing
> `TanhSigmoidMF` and `TanhBellMF`; ADR-018 is Accepted in
> `docs/decisions.md`. Prerequisite (b) is PENDING: neither the ADR-014
> trainer nor a manual parameterization has yet produced non-trivial MF
> parameters for the candidate shapes, so the manual path is not open.
> The two prerequisites are conjunctive — with (b) outstanding the
> ablation remains blocked and this ADR stays Open.

**Source**: Issue #2 (tanh MF implementation), Issue #6 (ADR curation
scope), Dr. Akba's recommendation recorded in Issue #2 body.

> Promoted from draft to the ledger · 2026-08-24 · issue #37. The draft at
> `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` is retained as the
> authoring record; this ledger entry is canonical.

---

## ADR-020 — Calibration snapshot schema and storage

**Status**: Accepted.

**Context**: ANFIS training requires at least 630 historical IBM Quantum
calibration snapshots. No public bulk archive exists. The team must
accumulate snapshots from a live backend at hourly cadence, starting
from zero. Every day of delay is a day of dataset that cannot be
recovered before paper submission (Issue #3).

The snapshot storage must satisfy three constraints: (1) it must not
bloat the main branch's git history, (2) it must be relocatable to S3 or
a separate repository pre-submission without breaking consumers, and
(3) it must preserve the full IBM `properties()` JSON for future schema
evolution.

**Decision**: Snapshots are stored on an orphan branch
`calibration-data` in the same repository. The branch has no common
ancestor with `main`. Directory layout:

    calibration-data/
      snapshots/
        YYYY-MM/
          <backend>/
            <ISO8601-timestamp>.json

Each snapshot file is the raw JSON returned by
`QiskitRuntimeService().backend(name).properties()`, written atomically
via `O_CREAT|O_EXCL` by `calibration/storage.py`. The poller runs as a
GitHub Actions cron workflow (`.github/workflows/calibration-poll.yml`)
on a mid-hour schedule (currently `:37`, per Issue #15).

The workflow authenticates via `IBM_QUANTUM_TOKEN` in GitHub Secrets,
uses `GITHUB_TOKEN` with `contents:write` scope (no PAT), and serializes
concurrent runs via a `concurrency` group with `cancel-in-progress:
false`.

**Consequences**:

- Main-branch `git clone --single-branch` is unaffected by snapshot
  accumulation.
- Consumers that need snapshots must fetch the `calibration-data` branch
  explicitly or read from a future S3 mirror.
- The JSON schema is IBM-defined and may change without notice. The
  typed loader (ADR-017) validates units at parse time and raises
  `CalibrationParseError` on schema drift.
- Multi-backend support is deferred. The current workflow polls a single
  backend (currently `ibm_fez`, switched from `ibm_brisbane` in PR #8).

**Source**: Issue #3 (deployment scope), PR #7 (implementation),
PR #8 (backend switch), Issue #15 / PR #17 (cron timing).

> Promoted from draft to the ledger · 2026-08-24 · issue #37. The draft at
> `docs/decisions/drafts/ADR-020-calibration-snapshot-schema-and-storage.md` is retained as the
> authoring record; this ledger entry is canonical.

---

## ADR-021 — Aer integration constraint and Factory/Ensemble pattern

**Status**: Accepted on the constraint · Open on variance-injection design.

**Context**: Qiskit Aer's `NoiseModel.to_dict()` is called once during
`AerSimulator.run()` and the C++ controller takes over
(`qiskit_aer/backends/backend_utils.py:cpp_execute_circuits()`). Once
the payload is handed to C++, Python execution halts until the entire
batch of shots completes. There is no per-shot Python callback, no
`_quantum_error_for_instruction` hook, no `_sample_noise` re-entry
point.

ADR-002 establishes the Factory/Ensemble pattern as the only correct
response to this constraint. This ADR extends ADR-002 by documenting
the implementation contract, the dependency-injection architecture, and
the variance-injection plug-in points that Burak's integration
walkthrough (PR #13, `docs/findings/aer-integration-walkthrough.md`)
identified.

**Decision (Accepted) · Integration contract**:

`FuzzyNoiseModel` is constructed with six injected dependencies:

1. `feature_extractor: CalibrationFeatureExtractor`
2. `rule_base: RuleBase`
3. `defuzzifier: Defuzzifier`
4. `squashing: SquashingStrategy`
5. `channel_projector: ChannelProjector`
6. `fuzzification_strategy: FuzzificationStrategy`

It also receives a `CalibrationSnapshot`.
 `FuzzyNoiseModelEnsemble` (the factory) takes the optional
 `ensemble_size` (default 32) and `rng` used to create multiple
 `FuzzyNoiseModel` instances.

The inference pipeline executed at construction is:

    features = feature_extractor.extract(calibration)
    firing   = rule_base.evaluate(features)
    raw      = defuzzifier.defuzzify(firing)
    crisp    = squashing.squash(raw)

The resulting `crisp_params` are stashed and reused by every
`prepare()` call.

`FuzzyNoiseModel.prepare(circuit)` contract:
- **Input**: `QuantumCircuit`
- **Output**: `tuple[QuantumCircuit, NoiseModel]` (fresh noise model
  with errors installed via `channel_projector.project(crisp_params,
  gate_name, qubits)`)
- **Idempotency**: Repeated calls return fresh `NoiseModel` instances;
  no state accumulation on `self`
- **Circuit mutation**: The returned circuit may differ from input
  (pre/between-gate fuzzification per ADR-007 transforms the circuit).
  Callers MUST pass `circuit.copy()` to maintain ensemble-member
  isolation.

`FuzzyNoiseModelEnsemble.__iter__` yields `ensemble_size` instances of
`FuzzyNoiseModel`, each constructed with the same shared dependencies.
At bootstrap, all members are identical (degenerate ensemble per
ADR-015).

**Decision (Open) · Variance-injection plug-in points**:

When ADR-015 resolves, per-member variance will plug in at one or more
of these locations inside `FuzzyNoiseModelEnsemble.__iter__`:

1. **Input-vector perturbation**: Perturb the
   `feature_extractor.extract(calibration)` output before passing to
   `rule_base.evaluate()`. Jiggle calibration features per member.

2. **Premise-MF perturbation**: Construct a per-member `RuleBase` with
   perturbed MF parameters (drawn from training-time variance, once
   ADR-014 delivers trained MFs).

3. **IT2 footprint sampling**: Sample from the IT2 uncertainty envelope
   within `RuleBase.evaluate()` or at member construction time,
   depending on whether the sampled MF is a property of the per-member
   rule base or computed on demand (depends on ADR-009 resolution).

The choice among these mechanisms is deferred until ADR-009 (T1 vs IT2)
and ADR-014 (trained MFs with meaningful variance) resolve. This ADR
records the plug-in architecture so the decision can be made without
refactoring the ensemble factory.

**Consequences**:

- Ensemble construction requires wiring six ABC implementations. This
  strict DI surface is intentional for testability but makes factory
  construction non-trivial.
- Callers of `prepare()` must pass `circuit.copy()` to prevent mutation
  leakage. This convention is enforced by code review (PR #13 blocker).
- High-level circuits (QFT, `efficient_su2`) require explicit
  `transpile(circuit, backend=sim)` before `AerSimulator.run()` with
  custom noise models. Aer raises `unknown instruction` on
  un-transpiled high-level gates.
- Ensemble latency scales O(N) in members (per-member transpile plus
  fresh `NoiseModel` install). Simulator hoisting amortizes cold-start.
- Bootstrap measurements require non-zero consequent initialization
  (`consequent_init="random"`) to exercise real pipeline work. Zero
  consequents produce identity channels that mask pipeline latency.

**Source**: Issue #4 (Aer walkthrough scope), PR #13 (implementation),
`docs/findings/aer-integration-walkthrough.md` (findings),
`src/superconducted/integration/aer_factory.py` (code).

> Promoted from draft to the ledger · 2026-08-24 · issue #37. The draft at
> `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md` is retained as the
> authoring record; this ledger entry is canonical.

---

## ADR-022 — Benchmark validation criteria

**Status**: Accepted.

**Context**: The benchmark harness computes four metrics (Hellinger
distance, KL divergence, state fidelity, R-squared) to compare the
fuzzy noise engine's output against a reference simulation. Every later
result the team produces rests on these numbers being correct. A
function that silently mis-computes Hellinger distance would invalidate
every comparison run by every teammate and every plot in the paper.

Issue #5 established that the harness needed validation tests that check
the numbers themselves, not just that the code runs without crashing.

**Decision**: Every metric in the benchmark harness must be validated
against the following standing property set:

1. **Identity**: `metric(P, P)` returns the metric's self-similarity
   baseline (0 for distance metrics, 1 for fidelity/R-squared).
2. **Symmetry or asymmetry**: Symmetric metrics (Hellinger) must satisfy
   `metric(P, Q) == metric(Q, P)`. Asymmetric metrics (KL) must have a
   test asserting `metric(P, Q) != metric(Q, P)` on a non-trivial
   example.
3. **Bounds**: Hellinger and fidelity output in [0, 1]. KL output >= 0.
4. **Monotonicity**: With Aer's depolarizing noise model, increasing
   depolarizing probability p must monotonically increase distance
   metrics and monotonically decrease fidelity.
5. **Determinism**: Same circuit + same noise model + same seed + same
   shot count produces identical metric values across runs.
6. **Reference value**: At least one hand-derivable scenario (e.g.,
   single-qubit depolarizing channel with known p) verified within
   shot-noise tolerance (3-sigma).

Tests must use real `SimulationResult` frozen dataclasses, not
`MagicMock`. This enforces value-object invariants and detects API drift
between test fixtures and production objects.

Any new metric added to the harness must satisfy all six properties
before merge.

**Consequences**:

- The property set is the minimum bar. Additional tests (e.g., triangle
  inequality for Hellinger) are encouraged but not required.
- Probabilistic tests are inherently shot-based. Fixed seeds and
  generous tolerances (3-sigma) prevent CI flakiness.
- If a property test fails on first run and the cause is a real harness
  bug, the bug is filed as a separate issue (not fixed in the validation
  PR).
- Real-hardware comparison tests are deferred until IBM backend access
  is available for benchmarking.

**Source**: Issue #5 (benchmark validation scope), PR #10
(implementation), `docs/implementations/2026-05-13-harness-metric-sanity-checks.md`.

> Promoted from draft to the ledger · 2026-08-24 · issue #37. The draft at
> `docs/decisions/drafts/ADR-022-benchmark-validation-criteria.md` is retained as the
> authoring record; this ledger entry is canonical.
> See ADR-023 for how the reject-don't-clip convention applies to
> `TanhMF`, the one MF that is a documented exemption from it.

---

## ADR-023 — Membership-function output range: floor exemption for `TanhMF`

**Status**: Accepted.

**Context**: ADR-018 states that for the tanh shapes it governs, "no
clipping is implemented anywhere in either class" and out-of-domain
parameters are a construction-time error. `TanhMF` — the bootstrap tanh
shape enumerated in ADR-006, a different class from `TanhSigmoidMF` and
`TanhBellMF` — clamped its `degree()` output into `[0, 1]`. It was the
only MF in `src/superconducted/fuzzy/membership.py` that clamped at all.

Until PR #26 (`049b336`) the ADR-006 entry carried a revisit note
flagging this. That note was replaced with a one-line handoff to
ADR-018, but ADR-018 governs only `TanhSigmoidMF` and `TanhBellMF` and
says nothing about `TanhMF` or about clamping inside `degree()`. The
slope half of the deleted note was genuinely delegated; the clip half
was dropped. This entry resolves the dropped half.

The deleted note's stated rationale was that the clip "masks the invalid
parameterization by clamping degenerate output to zero, hiding a
configuration error." That rationale does not survive checking.
`TanhMF._validate` already rejects `left >= right` and non-positive
slopes, so invalid parameterizations never reach `degree()`. What the
clamp actually handles is the analytic range of the shape itself under
*valid* parameters.

**Mathematics**: For `raw(x) = 0.5 * (tanh(s_L * (x - L)) - tanh(s_R * (x - R)))`,
`_validate` requires `L < R`, `s_L > 0`, and `s_R > 0`. It does not
require `s_L == s_R`, and unequal slopes make the raw value negative on
one tail:

```
raw(x) < 0  <=>  s_L * (x - L) < s_R * (x - R)
            <=>  x beyond  x* = (s_L * L - s_R * R) / (s_L - s_R)
```

- `s_L > s_R` gives `x* < L`: negative on the far-left tail.
- `s_L < s_R` gives `x* > R`: negative on the far-right tail.
- `s_L == s_R` is the only safe case — `x - L > x - R` and `tanh` is
  monotone, so `raw >= 0` everywhere.

The infimum is `-0.5`, approached as `s_L / s_R -> infinity` with `x`
just below `L`; it is not attained. Measured worst case over 400,000
randomized `_validate`-passing parameterizations: `-0.4996`. A concrete
case: `L=0, R=1, s_L=10, s_R=0.1` at `x = -1` gives `raw = -0.4013`.

The upper bound needs no clamp. `raw = 0.5 * (a - b)` with `a < 1` and
`b > -1` gives `raw < 1` strictly; in float64 it saturates at exactly
`1.0` once `|arg| >= ~20` rounds `tanh` to `±1`, but it never exceeds
`1.0`. A `min(1.0, ...)` term is therefore provably dead code.

**Decision**: `TanhMF.degree()` keeps a floor, `max(0.0, raw)`, and is a
documented exemption from ADR-018's reject-don't-clip convention. The
dead upper clamp is removed and the class docstring's formula is
corrected from `clip(..., 0, 1)` to `max(..., 0)`.

The convention is scoped precisely: **reject-don't-clip governs
parameters, not a shape's analytic range.** Invalid parameters must
raise at construction, and `TanhMF._validate` already does that.
Projecting a valid shape's tail back onto `[0, 1]` is a different
operation and is permitted.

The two alternatives were rejected on their consequences:

- *Remove the floor and let `MembershipDegree` raise.* `degree()` would
  then raise `ValueError` in the tails for any asymmetric-slope MF the
  class itself accepts. That is a live defect, not a cleanup.
- *Keep the floor but tighten `_validate` to require `s_L == s_R`.*
  This deletes the asymmetric-edge shape family that ADR-006 ships and
  that the ADR-019 ablation is meant to compare.

**Consequences**: The floor introduces a zero-gradient region wherever
`raw < 0` — beyond `x*`, in one tail. The ADR-014 trainer must treat
this the same way ADR-018 already requires for slope sign: keep the
premise-parameter search inside the region where the shape is
informative, rather than relying on gradient signal from a saturated
tail. This is the pathology ADR-012 names for `ProbabilityClip` one
layer down, and ratifying `SigmoidSquashing` as the differentiable
output path does not remove it upstream.

If an end-to-end differentiable pipeline later makes the floor
unacceptable, the correct fix is to change the shape, not to delete the
floor: a product of sigmoids, `sigma(s_L * (x - L)) * sigma(-s_R * (x - R))`,
is bounded in `(0, 1)` by construction and needs no projection. That
would be an ADR-006 shape change with ablation consequences, so it is
not taken here.

Any future MF whose analytic range can leave `[0, 1]` under parameters
its own `_validate` accepts must either be reshaped or receive an
explicit exemption in this entry. Silent clamping in a new shape is not
covered by this decision.

**Source**: Issue #28 (surfaced while confirming ADR-018 against `main`
for Issue #20), PR #26 (`049b336`) which removed the clip half of
ADR-006's revisit note, ADR-018 (the convention this exempts from),
ADR-012 (`ProbabilityClip`'s zero-gradient note),
`tests/test_membership.py`
(`test_asymmetric_slopes_floor_negative_tail`,
`test_in_domain_value_is_not_floored`,
`test_degree_in_unit_interval_for_valid_params`).

> See ADR-006 for the shape enumeration and ADR-018 for the
> construction-time convention this entry scopes.
