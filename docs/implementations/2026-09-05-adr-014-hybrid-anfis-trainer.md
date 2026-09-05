# 2026-09-05: ADR-014 hybrid ANFIS trainer

## Problem / Motivation

`TSKRuleBase` models were manually parameterized, so the project had no
reproducible route to fit consequents or membership-function premises. ADR-014
calls for an ANFIS-style trainer, while Issue #57 separately owns the official
calibration target-distribution definition.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/types.py` | Defines validated training data, results, diagnostics, and parameter counts. |
| `src/superconducted/training/parameters.py` | Enumerates shared membership functions once and applies atomic premise updates. |
| `src/superconducted/training/anfis.py` | Fits TSK consequents by weighted batch LSE and premises by finite-difference descent. |
| `tests/test_anfis.py` | Covers T1/IT2 fitting, conversion, numerical boundaries, and optimizer behavior. |

## Implementation approach

`HybridANFISTrainer.fit()` deep-copies its input rule base, standardizes the
training inputs and targets, and transforms membership-function parameters into
that coordinate system. It solves consequent coefficients for the current
premises, then optionally performs finite-difference premise steps.

Premise updates preserve positive width and slope parameters through log-space
coordinates. Each proposal is rolled back unless its re-solved LSE model
strictly lowers the training objective without losing an initially valid
training row to zero firing. Domain-invalid proposals are also rejected and
the learning rate is halved. Validation uses training statistics only, drops
individual zero-firing rows, and restores the best validation premise state.

The implementation uses batch `numpy.linalg.lstsq` on each solve, not an
online recursive-LSE state update. It is therefore an ANFIS hybrid LSE/premise
trainer, while any requirement for streaming RLS remains a future ADR/API
decision.

## Mathematical / Statistical details

For a rule $k$ and standardized input $x$, a consequent is linear:

$$c_k(x) = A_k [x; 1].$$

T1 design-matrix blocks use normalized firing weights $w_k$. IT2 blocks use
the Nie-Tan effective weight:

$$w_k = \frac{1}{2}\left(\frac{f_k^L}{\sum_j f_j^L} + \frac{f_k^U}{\sum_j f_j^U}\right).$$

Given row weights $q_i$ and ridge value $\lambda$, the consequent solve is
the augmented least-squares system:

$$
\begin{bmatrix}
\operatorname{diag}(\sqrt{q})\Phi \\
\sqrt{\lambda}I
\end{bmatrix}\theta =
\begin{bmatrix}
\operatorname{diag}(\sqrt{q})Y \\
\sqrt{\lambda}\theta_\mathrm{warm}
\end{bmatrix}.
$$

The same row weights define the premise and validation loss as the weighted
mean squared residual, $\sum_i q_i \lVert r_i \rVert^2 / \sum_i q_i$, so the
finite-difference direction, proposal acceptance, loss history, and
early-stopping comparison optimize the same observation-weighted objective as
the LSE data term.

The diagnostic condition number is calculated from this actual weighted and
ridge-augmented solve matrix. A row whose T1 firing sum, or either IT2 bound
sum, is zero is undefined for defuzzification and is excluded. An all-zero
training or validation set is rejected.

## Design decisions

The trainer reuses the locked TSK inference and existing production
defuzzification formulas rather than duplicating them. Its returned rule base
is mapped back into raw feature and target units so it remains usable by the
existing inference pipeline.

This trainer slice did not introduce a calibration snapshot-to-target builder,
target heuristic, artifact serializer, or output-squashing metric. The
subsequent Issue #57 target-contract slice is recorded in
`2026-09-05-issue-57-training-target-contract.md`. In particular,
`clip_binding_rate` cannot be measured by the trainer because squashing belongs
to `FuzzyNoiseModel` at inference time; `nonfinite_rows_rejected` is zero under
the current `TrainingSet` fail-fast finiteness contract.

## Verification

- `.venv/bin/python -m pytest tests/test_anfis.py -q`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check src/superconducted/training tests/test_anfis.py`
- `.venv/bin/mypy src/superconducted/training`

## Related docs

- ADR-014 in `docs/decisions.md`
- Issue #57 target-distribution definition
- `docs/implementations/2026-09-05-adr-014-synthetic-trainer-smoke.md`