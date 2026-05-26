# ADR-021 — Aer integration constraint and Factory/Ensemble pattern

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
