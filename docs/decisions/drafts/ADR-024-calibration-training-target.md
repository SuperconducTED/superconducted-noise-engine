# ADR-024: Calibration training target

**Status**: Open.

## Context

The TSK trainer requires one supervised target that connects archived IBM
calibration data to the existing single-qubit amplitude-plus-phase-damping
channel. Without a named derivation, the trainer, an anchored-consequent model,
and a thermal-relaxation reference can silently use different remembered
formulas or different missing-data rules.

`KrausChannelProjector` consumes crisp `(gamma, lambda)` parameters for
amplitude damping and phase damping. IBM calibration snapshots provide per-qubit
`T1`, `T2`, and gate duration. This ADR proposes the derived channel target and
the data-handling rules implemented for Issue #57.

## Proposed decision

For one qubit with relaxation times $T_1$, $T_2$ and target-gate duration $t$,
use the raw-space target:

$$
\gamma = 1 - \exp(-t/T_1)
$$

and

$$
\lambda = 1 - \exp\left[-t\left(2/T_2 - 1/T_1\right)\right].
$$

These equations match amplitude damping's population multiplier and the
composed amplitude-plus-phase-damping channel's coherence multiplier to Aer's
zero-temperature `thermal_relaxation_error`.

At $T_2 = T_1$, $\lambda = \gamma$. At $T_2 = 2T_1$, $\lambda = 0$. For
$T_2 > 2T_1$, $\lambda$ is negative and Aer rejects the relaxation channel;
such a qubit is not assigned a target.

Per-qubit derivation checks, in order, for missing/non-finite `T1`,
missing/non-finite `T2`, a missing/non-finite gate duration, non-positive
physical values, and $T_2 > 2T_1$. Only the first failure is counted. Targets
retain qubit alignment with a NaN row and a false usable mask for rejected
qubits.

A snapshot target is the mean of usable per-qubit targets. Standard deviation
and the 10th, 50th, and 90th percentiles are retained. The mean is intentionally
not evaluated from mean `T1`/`T2`, because the map is nonlinear. For rule-centre
consumers, `feature_target_fn` separately evaluates the proposed target from
`BasicCalibrationVectorizer`'s mean features and states its current
microsecond input convention.

Gate durations are currently parsed from the raw `properties.gates` envelope in
`training/targets.py`. Only a requested single-qubit gate is accepted; a
gate-length unit other than nanoseconds is a parse error.

## Evidence

`tests/test_aer_pin.py` compares channel `SuperOp` matrices for $(T_1, T_2)$
pairs spanning both Aer branches at 24 ns and 60 ns. The largest measured
absolute matrix-entry difference was $9.992007221626409 \times 10^{-16}$,
below the $10^{-12}$ acceptance tolerance.

The gate-bearing `ibm_fez` fixture contains 156 single-qubit `sx` gate records,
each with a 24 ns duration. It produces 155 usable targets; qubit 72 is skipped
as `t1_missing`.

## Decisions awaiting sign-off

1. Confirm raw-space targets during training with identity squashing, and
   probability clipping only at inference; `SigmoidSquashing` remains the
   differentiable alternative if optimization requires it.
2. Confirm raw `properties.gates` parsing is the phase-3 location before a
   typed gate parser is introduced in `calibration/loader.py`.
3. Confirm the ordered five-reason skip policy and require the reference-model
   builder to use the same policy.
4. Confirm mean-of-per-qubit-targets as the phase-3 supervised target while
   retaining distribution spread for later target-side upgrades.

Advisor responses are recorded append-only in
`docs/advisor/2026-09-03-decisions-from-akba.md` when that file is created by
its owning issue. This ADR moves to Accepted only after the listed decisions
receive their required sign-off.

## Consequences

Training and reference-model work share a single, testable channel target.
No multi-qubit, readout-error, or non-zero-excited-population thermal target is
introduced. Those effects are outside the present single-qubit channel model
and require separate architecture decisions.

## Source

Issue #57; `src/superconducted/training/targets.py`;
`tests/test_targets.py`; `tests/test_aer_pin.py`; ADR-014; ADR-020.
