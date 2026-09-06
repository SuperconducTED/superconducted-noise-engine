# 2026-09-05: Issue #57 training target contract

## Problem / Motivation

The trainer needs one explicit supervised target for the single-qubit channel,
rather than independently remembered calibration, channel, and reference-model
formulas. Issue #57 defines that target as the amplitude-plus-phase-damping
parameter pair derived from calibration T1, T2, and the relevant gate duration.
The target ADR remains subject to advisor/lead sign-off; this record documents
the implemented proposal without changing its ledger status.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/targets.py` | Derives gate durations and per-qubit or feature-space `(gamma, lambda)` targets with explicit skip rules. |
| `src/superconducted/training/types.py` | Makes training arrays immutable and records timestamps, feature/target names, row provenance, and archive identity. |
| `src/superconducted/interfaces.py` | Defines the non-mutating `TSKTrainer` contract. |
| `src/superconducted/training/parameters.py` | Counts shared membership functions once when reporting trainable parameters. |
| `tests/test_targets.py`, `tests/test_aer_pin.py` | Pin target derivation on synthetic inputs, the calibration fixture, and Qiskit Aer SuperOps. |
| `tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json` | Adds the gate-bearing projection of the q72-missing-T1/T2 source snapshot. |

## Implementation approach

`gate_lengths` reads a raw `properties.gates` envelope and accepts only the
requested single-qubit gate's `gate_length` in nanoseconds. A missing gate list
produces no durations with a warning; an unexpected duration unit is a
`CalibrationParseError`.

`qubit_targets` retains qubit-index alignment: unusable rows contain NaNs and
are marked by a boolean mask. It counts only the first applicable skip reason,
in this order: missing/non-finite T1, missing/non-finite T2, absent/non-finite
gate duration, non-positive physical values, then `T2 > 2*T1`. `snapshot_target`
summarizes only usable rows and returns `None` if none remain.

`feature_target_fn` is provided for rule-centre consumers. It expects the
three-element `BasicCalibrationVectorizer` output, whose coherence values are
currently in microseconds, and explicitly converts them to seconds. Its target
at mean calibration features is not generally the mean per-qubit target.

## Mathematical / Statistical details

For gate duration $t$, relaxation times $T_1$ and $T_2$, amplitude damping is
matched by:

$$
\gamma = 1 - \exp(-t/T_1).
$$

The channel's coherence multiplier gives the matching phase-damping parameter:

$$
\lambda = 1 - \exp\left[-t\left(2/T_2 - 1/T_1\right)\right].
$$

The second formula is non-negative precisely when $T_2 \le 2T_1$, which is also
the boundary accepted by Qiskit Aer's `thermal_relaxation_error`. The conformance
tests compare `SuperOp` objects, not `QuantumError` representations, across the
`T2 <= T1` and `T1 < T2 <= 2*T1` Aer branches. The maximum absolute difference
measured across four $(T_1,T_2)$ cases at 24 ns and 60 ns was
$9.992007221626409 \times 10^{-16}$, below the $10^{-12}$ acceptance tolerance.

## Design decisions

The implementation follows the raw-space target proposal: the trainer fits
finite unbounded outputs, while existing channel projection remains responsible
for inference-time probability clipping. No target is fabricated for unusable
qubits, and no multi-qubit target is derived because the current channel
projector is intentionally single-qubit only.

The target ADR and its raw-versus-logit, gate-parser ownership, skip-policy, and
snapshot-aggregation sign-offs remain Open in Issue #57. This implementation
record is not an acceptance of those pending architectural decisions.

## Verification

- `.venv/bin/python -m pytest tests/test_targets.py tests/test_aer_pin.py -q`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check src/superconducted/training tests/test_targets.py tests/test_aer_pin.py`
- `.venv/bin/mypy --no-incremental src/superconducted/training src/superconducted/interfaces.py`

## Related docs

- Issue #57
- ADR-014 in `docs/decisions.md`
- `tests/fixtures/calibration/README.md`
