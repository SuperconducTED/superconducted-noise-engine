# 2026-09-12: issue-73-physical-gate-noise-filter

## Problem / Motivation

Issue #73 found that `FuzzyNoiseModel.prepare()` sent every single-qubit
instruction to the Kraus projector. The projector intentionally ignores
`gate_name`, so this attached the same damping channel to virtual `rz` gates
and could attach it to administrative instructions such as `delay` and Aer
save/snapshot operations. That is inconsistent with Issue #58's physical
reference-noise semantics: a zero-duration virtual `rz` has no thermal
relaxation interval.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/integration/aer_factory.py` | Derives eligible single-qubit noise operations from positive-duration archived calibration gate-length records before invoking the channel projector. |
| `scripts/first_ensemble_run.py` | Makes the synthetic calibration describe positive physical `sx` and zero-duration virtual `rz` gate-length records. |
| `tests/test_noise_gate_eligibility.py` | Covers real calibrated, virtual, administrative, qubit-aware, missing-gate-length, and injected-policy cases. |

## Implementation approach

`FuzzyNoiseModel.prepare()` delegates to an injected `GateEligibilityPolicy`.
The default `CalibrationGateEligibilityPolicy` resolves a frozen set of
`(gate_name, qargs)` pairs from archived `properties.gates` records via
`training.targets.gate_lengths()`, the same parser used for #58's
thermal-relaxation targets. A record is eligible only when its single-qubit
`gate_length` is finite and strictly positive. The nested `error_provider`
returns `None` for every non-member; `PostGateFuzzification` already treats
that as "do not install an error."

The calibration gate-length record is authoritative rather than an injected or
hard-coded allowlist. Gates absent from those records and non-positive durations
are ignored, so the policy fails closed. Invalid gate-length schemas retain the
existing `gate_lengths()` behavior and raise `CalibrationParseError` rather
than silently treating potentially corrupt calibration data as physical.
In particular, virtual `rz` is excluded because its archived `gate_length` is
zero, while `delay` and save/snapshot instructions are absent from the physical
gate records. `channels/kraus.py` remains unchanged: it is LOCKED and owns
Kraus construction, not physical-gate eligibility.

`prepare()` receives a circuit compiled to this physical basis. This is the
canonical ADR-021 contract: errors are registered against physical names and
the returned circuit is run without another transpilation. Issue #74 applies
that ordering to `first_ensemble_run.py`.

## Mathematical / Statistical details

N/A - no channel parameters or statistical estimators changed. For a calibrated
gate length $t$, the eligibility predicate is $t \in \mathbb{R}$,
$\operatorname{isfinite}(t)$, and $t > 0$.

## Design decisions

Issue #73 offered calibration records or an explicit allowlist as the source
of eligible gates. We chose archived calibration gate-length records, the same
physical source parsed by #58's reference-model work. Matching includes both
the gate name and physical qubit tuple, so a calibration on one qubit does not
implicitly authorize the same gate on another. `GateEligibilityPolicy` keeps
this decision injectable without making `ChannelProjector` responsible for it.

This change is deliberately limited to the integration policy boundary. It
does not add multi-qubit channels, change the projector, alter fuzzification
placement under ADR-007, or revise snapshot persistence.

## Verification

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m ruff format --check .`
- `.venv/bin/python -m mypy`

## Related docs

- ADR-021 in `docs/decisions.md`
- Issue #58 reference-model scope in `docs/roadmap/2026-09-03-phase-3-plan.md`
- Issue #73