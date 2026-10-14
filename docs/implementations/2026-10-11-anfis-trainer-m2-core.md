# 2026-10-11: ANFIS trainer M2 core

## Problem / Motivation

Issue #60 needs a trained first-order TSK model rather than the bootstrap
zero-consequent or random rule bases. This M2 slice implements only the fixed
premise stage: it fits consequents with batch ridge least squares, preserves
the caller's rule-base values, and returns a raw-unit model. It is
type-agnostic over the T1 weighted-average and IT2 Nie-Tan paths, so it does
not decide ADR-009 or ADR-011.

ADR-014 remains **Deferred** until Issue #60 step 11, when the complete M3
evidence can support its status change. This M2 implementation records the
trainer contract without changing the ledger. The raw-space training choice is
also evidence for proposed ADR-027, not a status change under that ADR.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/anfis.py` | Adds the immutable, fixed-premise ANFIS ridge-LSE trainer and raw-unit RMSE helper. |
| `src/superconducted/training/__init__.py` | Re-exports the trainer through the existing public training package. |
| `tests/test_anfis.py` | Pins T1/IT2 fitting, standardization, weight, diagnostics, and immutability contracts. |
| `docs/team.md` | Records `training/anfis.py` ownership: Burak primary, Bengisu secondary. |

## Implementation approach

`HybridANFISTrainer` implements `TSKTrainer.fit`. It rejects non-TSK rule
bases, deep-copies unique shared membership functions, transforms that copied
base to standardized training units, fits only rule consequents, then maps MFs
and consequents back to raw units. The source `TSKRuleBase.evaluate` remains
the sole implementation of product firing and consequent evaluation.

The M2 contract requires `epochs=0`. A positive value raises
`NotImplementedError` rather than pretending a premise update happened. The
next Issue #60 slice owns finite-difference premise updates, reject-and-halve,
and early stopping.

`evaluate_rmse` follows the FR-12 skip policy: a row with a zero T1 firing
total or zero IT2 bound is excluded; it raises if every row is excluded.
`zero_firing_rows_dropped` counts only training rows dropped from the LSE and
loss, not validation scoring rows.

## Mathematical / Statistical details

For `n` retained rows, `R` rules, `d` inputs and `k` targets, define
`z = (x - m) / s`, with population standard deviation and `s = 1` for a
constant feature column. Targets are similarly standardized as
`yt = (y - my) / sy`.

For each rule, the T1 effective weight is `f_r / sum(f)`. The IT2 Nie-Tan
weight is `0.5 * (f_low_r / sum(f_low) + f_high_r / sum(f_high))`. A design
row concatenates `w_r * [z; 1]` for every rule. Per output:

```text
theta = theta0 + argmin_delta ||Phi delta - (yt - Phi theta0)||^2
                          + ridge * ||delta||^2
```

The implementation solves the augmented system
`[Phi; sqrt(ridge) I] delta = [residual; 0]` with `numpy.linalg.lstsq`;
it never forms normal equations. Batch ridge LSE is the offline form of the
recursive LSE named by ADR-001 and ADR-014: processing the same rows
sequentially yields the same estimator up to floating-point order.

Weights supplied by `TrainingSet` are normalized to mean one before their
square roots scale rows, so their common scale does not change ridge strength.
The standardized loss history is the unweighted
`mean_i ||prediction_i - target_i||^2` over retained rows. Reported RMSEs are
in raw target units.

Map-back preserves every output exactly because effective weights sum to one:

```text
A_raw[l, j] = sy[l] * A_std[l, j] / s[j]
A_raw[l, d] = sy[l] * (A_std[l, d] - sum_j(A_std[l, j] * m[j] / s[j])) + my[l]
```

The seven shipped membership shapes use their exact location-scale mappings:

| Shape | Standardized parameters |
| --- | --- |
| Gaussian | `[(c-m)/s, sigma/s]` |
| Triangular | each point `(p-m)/s` |
| Trapezoidal | each point `(p-m)/s` |
| Tanh | endpoints `(p-m)/s`; slopes `slope*s` |
| Interval Gaussian | `[(c-m)/s, sigma_low/s, sigma_high/s]` |
| Tanh sigmoid | `[(c-m)/s, slope*s]` |
| Tanh bell | endpoints `(p-m)/s`; slope `slope*s` |

The planted M2 gate samples the vectorizer-unit box
`T1=[98.8, 154.4] us`, `T2=[67.4, 110.5] us`, and
`readout=[0.0171, 0.0374]` on an 8x8x8 grid. It recovers the T1 and IT2
3x3x3 Gaussian-grid consequents using an absolute allowance of
`2048 * cond(Phi_augmented) * eps * max(abs(expected_consequents))`; the
multiplier covers the raw-space consequent map-back after the least-squares
solve and remains conditioning-dependent.

## Design decisions

- **T1/IT2 weights:** The private effective-weight helper is pinned against
  `WeightedAverageDefuzzifier` and `NieTanDefuzzifier`; it will move to
  Issue #61's shared gradients helper without changing this contract. This
  follows ADR-009/ADR-011's still-open choice without pre-judging it.
- **Warm start:** Ridge regularizes toward the input consequents, including
  biases. The implementation rejects identity damping on every training row,
  recording the deterministic anchored-baseline mechanism required by
  ADR-024 clause 5 without claiming that clause's two enumerated mechanisms.
- **No runtime Aer dependency:** The trainer mirrors the first-two-output
  identity predicate instead of importing `aer_factory.is_identity_damping`,
  because importing Aer is outside the numerical training core. A two-output
  agreement test pins this narrow duplication.
- **Defaults:** `epochs=0` makes the M2 boundary explicit; `ridge=1e-6`
  regularizes rank-deficient archive fits without changing the `ridge=0`
  ordinary-LSE path; `fd_step=6e-6` is the cube root of float64 epsilon for
  the later central-difference stage; `premise_lr=1e-2`, `patience=10`, and
  `max_halvings=5` reserve conservative M3 controls; `seed=0` records a
  stable default although M2 is deterministic.

## Verification

- `ruff check .`
- `ruff format --check .`
- `mypy --strict`
- `pytest -q tests/test_anfis.py`
- `pytest -q`

The full-suite count must be measured on the actual merge commit and recorded
against NC-021 then; it is intentionally not inferred from this branch's test
delta.

## Related docs

- Issue #60, especially sections 6, 7, and 9.1
- ADR-001, ADR-009, ADR-011, ADR-014, ADR-024 clause 5, and proposed ADR-027
  in `docs/decisions.md`
- `docs/implementations/_TEMPLATE.md`
- `docs/team.md`
