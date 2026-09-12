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
| `src/superconducted/integration/aer_factory.py` | Derives eligible single-qubit noise operations from positive-duration calibration-target records before invoking the channel projector. |
| `scripts/first_ensemble_run.py` | Gives the synthetic smoke snapshot an explicit physical `h` target operation. |
| `tests/test_noise_gate_eligibility.py` | Covers calibrated, virtual, administrative, invalid-duration, qubit-aware, and missing-target cases. |

## Implementation approach

`FuzzyNoiseModel.prepare()` now resolves a frozen set of `(gate_name, qargs)`
pairs from `CalibrationSnapshot.target["operations"]` once per call. A record
is eligible only when it has a non-empty name, exactly one integer qubit, and
a numeric finite duration strictly greater than zero. The nested
`error_provider` returns `None` for every non-member; `PostGateFuzzification`
already treats that as "do not install an error."

The target is the authoritative source rather than an injected or hard-coded
allowlist. Invalid target shapes, absent targets, malformed records, missing
durations, and non-positive or non-finite durations are ignored, so the policy
fails closed. `channels/kraus.py` remains unchanged: it is LOCKED and owns
Kraus construction, not physical-gate eligibility.

## Mathematical / Statistical details

N/A - no channel parameters or statistical estimators changed. For a target
operation duration $t$, the eligibility predicate is $t \in \mathbb{R}$,
$\operatorname{isfinite}(t)$, and $t > 0$.

## Design decisions

Issue #73 offered calibration records or an explicit allowlist as the source
of eligible gates. We chose the serialized calibration target, the same
physical source used by the #58 reference-model work. Matching includes both
the gate name and physical qubit tuple, so a calibration on one qubit does not
implicitly authorize the same gate on another.

This change is deliberately limited to the integration policy boundary. It
does not add multi-qubit channels, change the projector, alter fuzzification
placement under ADR-007, or revise snapshot persistence.

## Verification

- `.venv/bin/python -m pytest -v tests/test_noise_gate_eligibility.py`
- `.venv/bin/python -m pytest -v tests/test_channel_viability.py tests/test_first_ensemble_run.py`
- `.venv/bin/python -m ruff check src/superconducted/integration/aer_factory.py scripts/first_ensemble_run.py tests/test_noise_gate_eligibility.py`
- `.venv/bin/python -m mypy src/superconducted/integration/aer_factory.py scripts/first_ensemble_run.py`

## Related docs

- ADR-021 in `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md`
- Issue #58 reference-model scope in `docs/roadmap/2026-09-03-phase-3-plan.md`
- Issue #73