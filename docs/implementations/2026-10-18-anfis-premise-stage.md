# 2026-10-18: ANFIS premise stage and early stopping

## Problem / Motivation

The M2 core of Issue #60 (PR #114) fits consequents by ridge least squares at a
fixed premise and refuses `epochs > 0`. Phase 3 needs the premise stage too: the
hybrid recipe ADR-014 names alternates the consequent solve with gradient steps
on the membership-function parameters. This slice adds Issue #60 FR-5 (premise
stage), FR-6 (alternation and early stopping), the FR-11 diagnostics the M2 core
left at zero, FR-14 determinism with premise epochs, and the
`gradient="analytic"` reservation of section 6.4. It also covers step 6(b) of
the issue's section 8, the planted-premise recovery measurement, which PR #114
did not include.

Out of this slice, and blocked elsewhere: `scripts/train_anfis.py` and the JSON
round trip (FR-15, FR-16; they need #62's `dump_rule_base` / `load_rule_base`),
the archive fit (step 9; it needs #63's training set), the import of #61's
`effective_weights` and its analytic gradient, and the ADR-014 / ADR-024
ledger notes (step 11). ADR-014 stays **Deferred**; ADR-009 and ADR-011 stay
Open.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/anfis.py` | Adds the finite-difference premise stage, reject-and-halve with a descent condition, the epoch loop, early stopping and the remaining diagnostics. |
| `tests/test_anfis.py` | Replaces the M2 test that `epochs > 0` raises with 20 tests for the premise stage, early stopping and their contracts. |
| `docs/evidence/anfis-premise-stage/` | Holds the script, the TSVs and the README for the planted 3x3x3 recovery and conditioning measurements below. |
| `docs/implementations/2026-10-18-anfis-premise-stage.md` | This record. |
| `docs/numerical-claims.md` | Updates NC-021 to the direct collection at this branch's code commit (Rule 6). |

`fuzzy/tsk.py`, `channels/kraus.py`, `interfaces.py`, `types.py` and
`pyproject.toml` are unchanged.

## Implementation approach

`HybridANFISTrainer.fit` keeps the M2 path up to the first consequent solve:
it validates the inputs, refuses a non-finite or all-identity warm start,
standardizes, deep-copies the membership functions and solves the consequents.
With `epochs=0` it returns that state, bit-identical to the M2 core. With
`epochs > 0` it hands the state to `_alternate`, which runs the epochs on the
deep-copied ("live") membership functions:

1. `_finite_difference_gradient` differentiates the training loss with respect
   to the premise vector, at the consequents solved for the current premise
   (`_PremiseObjective`). Every evaluation goes through `TSKRuleBase.evaluate`
   (FR-3); the trainer never re-implements the t-norm.
2. `_premise_step` steps against that gradient. Each trial premise gets its
   own consequent solve (`_ConsequentSolver`). The trial is accepted only if it
   is inside the loss's domain and its solved objective is lower than the
   current state's. Otherwise the rate is halved and the step retried, up to
   `max_halvings` times. An accepted trial's solve is the epoch's consequent
   stage, so every candidate state has consequents solved at its own premise.
3. The epoch's training loss is appended to `loss_history`. With a validation
   set, the validation loss is compared with the best so far. After `patience`
   epochs without a strict improvement the loop stops and returns the best
   state.

The premise vector is laid out by `training.parameters.premise_layout` and
written through `PremiseLayout.set_flat`, which reverts on a `ValueError`, so
the trainer has no private unique-MF walk (FR-8). Sharing is preserved: the
3x3x3 grid trains 9 shared objects (18 Gaussian parameters), never 81.

The live membership functions are copies made by the M2 standardization, so
nothing the loop does can reach the caller's rule base. The returned rule base
is mapped back to raw units by the M2 code, which copies again.

## Mathematical / Statistical details

**Search space.** The premise vector `theta` concatenates the unique MFs'
parameters. The search vector `phi` is `theta` with every positive-only entry
replaced by its logarithm (ADR-018). The positive-only entries are:

| Shape | Log-space entries |
| --- | --- |
| `GaussianMF` | `sigma` |
| `IntervalGaussianMF` | `sigma_low`, `sigma_high` |
| `TanhMF` | `slope_left`, `slope_right` |
| `TanhSigmoidMF` | `slope` |
| `TanhBellMF` | `slope` |
| `TriangularMF`, `TrapezoidalMF` | none (ordering constraints only) |

Ordering constraints (`a < b < c`, `a < b <= c < d`, `left < right`,
`sigma_low < sigma_high`) are not reparameterized. A step that breaks one is
rejected by the shape's own `set_parameters` and retried at half the rate.
Nothing is clamped (ADR-018, ADR-023).

**Objectives.** On the `n` training rows kept at the warm start (FR-12), with
standardized features `z_i`, targets `yt_i`, and mean-one row weights `w_i`
(all 1 without `TrainingSet.weights`):

```text
J(phi, B) = (1/n) * sum_i w_i * ||yhat(z_i; phi, B) - yt_i||^2
S(phi)    = min_B [ n * J(phi, B) + ridge * ||B - B0||^2 ]
```

`J` is section 6.4's loss, which the premise gradient differentiates. Row
weights enter it the way they enter the M2 solve, so without weights it is
section 6.4's `L` exactly. `S` is the objective the ridge solve minimizes, with
`B0` the warm-start consequents in standardized units (decision 2). `S` is
evaluated at the solved `B`, the "re-solved" objective. `_ConsequentSolver`
returns `S` as its score.

**Gradient.** Because the penalty does not depend on `phi`, the envelope
theorem gives `grad S(phi) = n * grad_phi J(phi, B*(phi))`. The gradient at the
consequents solved for the current premise is therefore the gradient of the
re-solved objective, which is why the alternation is gradient descent on `S`.
It is computed by central differences in search space:

```text
g_p = (J(phi + h_p e_p) - J(phi - h_p e_p)) / ((phi_p + h_p) - (phi_p - h_p))
h_p = fd_step * max(1, |phi_p|)
```

The denominator is the step as represented in floating point. Only entry `p`
leaves the current vector, so log-space round trips never touch the other
entries. If one side is outside the domain, the one-sided difference on the
other side is used. If both are, `g_p = 0`. The domain is: a finite vector, one
every shape's `set_parameters` accepts, at which every kept training row still
fires.

`test_premise_gradient_is_the_gradient_of_the_resolved_loss` pins the envelope
identity. It differentiates `S / n` in raw parameter space, re-solving at every
point, and applies the log-space chain rule itself. Worst relative disagreement
on the one-input fixture: 4.1e-9 (T1) and 8.3e-10 (IT2), against a 1e-6 bound.
The test also has a variant with row weights and `ridge = 0.3`.

**Step.** `phi' = phi - rate * g`, with entries where `g_p = 0` left exactly as
they were. A trial is accepted iff it is in the domain and `S(phi') < S(phi)`;
otherwise `rate` halves, up to `max_halvings` times. If every trial is
rejected, the state is unchanged and `premise_steps_rejected` counts the
epoch. An all-zero gradient takes no step and is not counted. `S` therefore
strictly decreases at every accepted step. With `ridge = 0` and no weights,
`loss_history` equals `S / n` up to rounding, so it falls with `S`. Otherwise
`loss_history` reports only the unweighted data term, as in M2.

**Early stopping (FR-6).** The validation loss is the unweighted section 6.4
loss over the validation rows that fire, in the training standardization. A
state improves on the best only if its validation loss is strictly lower.
After `patience` epochs without improvement the loop stops; `early_stopped` is
true exactly when fewer than `epochs` epochs ran. The returned state is the
best-validation one. `loss_history` covers every epoch run, `epochs_run + 1`
entries with entry 0 the M2 state, so the returned state is
`loss_history[epochs_run - patience]` when the run stopped early. Without a
validation set every epoch runs and the last state is returned. It is also the
state with the lowest `S`.

**Identifiability and conditioning.** With the product t-norm and normalized
weights, a rule's weight depends on its Gaussian MFs only through
`log mu = -(x - c)^2 / (2 sigma^2)`, a quadratic in each input. Adding the same
quadratic in `x_j` to every MF on input `j` leaves every normalized weight
unchanged. With two MFs per input, one direction of that shift keeps both MFs
Gaussian with unit peak. Distinct premises then give identical outputs, a flat
direction no data can resolve. With three MFs per input, the ratified grid's
layout, the premise is locally identifiable but ill-conditioned: the
consequents absorb most of a premise error. Plain gradient descent (FR-5)
needs on the order of the condition number of `S`'s Hessian in epochs to close
the softest direction. The Hessian of `S / n` at the planted 3x3x3 premise
(search space, standardized units, `ridge = 0`, second differences with step
`1e-3`; `docs/evidence/anfis-premise-stage/hessian-*.tsv`):

- **T1, 18 directions.** The largest eigenvalue is 8.4e-5. Sixteen lie between
  8.4e-5 and 1.1e-9, a ratio of 7.7e4. The two smallest, 1.6e-12 and 1.9e-13,
  are near what a step of `1e-3` resolves, so the condition number is at least
  7.7e4 and may be far larger.
- **IT2, 27 directions.** The eigenvalues run from 1.8e-3 down to 4.5e-8, all
  well above that resolution, for a condition number of 4.1e4.

Even at the full `premise_lr = 1e4`, a direction with curvature 1e-9 shrinks
by at most a factor of `1 - 1e-5` per epoch, so closing it takes on the order
of 1e5 epochs.

**Planted recovery (step 6(b)).** Two measurements:

- **CI test, one input, three MFs, 41 rows, 60 epochs at
  `premise_lr = 50`.** The final loss is 4.9e-3 (T1) and 1.9e-3 (IT2) of the
  initial. The premise distance to the planted one, in standardized units, is
  0.65 (T1) and 0.75 (IT2) of the warm start's. The held-out max error is
  0.060 (T1) and 0.033 (IT2) of the LSE-only fit's. Single soft entries can
  drift away: one T1 width goes from 0.076 to 0.112 while the norm shrinks.
- **Recorded run, the M2 3x3x3 fixture.** Planted grid of
  `tests/test_anfis.py::_planted_grid` on the NC-041 [p1, p99] box in archive
  units (microseconds for T1 and T2, dimensionless readout error); 512
  training rows; a 125-row held-out lattice interleaved with them. Warm start:
  each centre shifted by `(0.12, -0.10, 0.08)` of the centre spacing, each
  width scaled by `(1.2, 0.85, 1.15)`. 40 epochs at `ridge = 0`; standardized
  units:

| Type | `premise_lr` | Final / initial loss | Premise L2 error | Premise max error | Held-out max error, LSE-only to trained | Rejected steps | s / epoch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | 100 | 0.56 | 0.840 to 0.774 | 0.361 to 0.357 | 1.22e-2 to 9.12e-3 | 0 | 9.9 |
| T1 | 1000 | 0.023 | 0.840 to 0.658 | 0.361 to 0.343 | 1.22e-2 to 2.98e-3 | 0 | 9.7 |
| T1 | 10000 | 0.0052 | 0.840 to 0.551 | 0.361 to 0.289 | 1.22e-2 to 1.18e-3 | 0 | 9.3 |
| IT2 | 100 | 0.10 | 0.955 to 0.881 | 0.361 to 0.359 | 3.64e-2 to 1.18e-2 | 0 | 14.1 |
| IT2 | 1000 | 0.035 | 0.955 to 0.734 | 0.361 to 0.326 | 3.64e-2 to 7.39e-3 | 0 | 13.2 |
| IT2 | 10000 | 0.014 | 0.955 to 0.578 | 0.361 to 0.290 | 3.64e-2 to 4.24e-3 | 0 | 12.2 |

The held-out targets reach 35.6 (T1) and 36.4 (IT2) in magnitude, because the
planted consequents act on raw microsecond features, so the held-out errors are
3e-5 to 1e-3 of the target scale. No step was rejected at any rate. That
counter counts only steps that failed after every halving, so a zero says every
epoch moved, not that it moved at the full rate. Source:
`docs/evidence/anfis-premise-stage/recovery-*.tsv`, with the per-epoch losses in
`loss-history-*.tsv`.

Recovery of the premise parameters is therefore slow and partial with plain
gradient descent, as the conditioning predicts. The training and held-out
fits improve much faster than the parameters do. For the archive fit (step 9)
this means more epochs and a premise rate tuned on the validation split. It
also makes #61's analytic gradient a speed path worth having: each finite-
difference epoch costs `2P` forward passes over all rows.

**Cost per epoch.** `2P` forward passes for the gradient, one forward pass and
one solve per trial step, one forward pass for `loss_history`, and one over
the validation rows. `P = 18` (T1) and `27` (IT2) on the 3x3x3 Gaussian grid.
The recorded run's seconds per epoch are in the TSVs. They are this cloud
sandbox's, with four measurements sharing four vCPUs, and are not NFR-5's
desktop figure, which step 9 records.

## Design decisions

1. **Descent condition on the re-solved objective.** Section 6.4 rejects a
   step only when `set_parameters` raises. This slice also rejects a step that
   does not lower `S`. Without it, a too-large `premise_lr` diverges. On the
   one-input test fixture at `premise_lr = 200`, 150 epochs move the premise
   from 0.25 to 29.3 (standardized distance to the planted one) and raise the
   loss 137-fold. Without a validation set that state would be returned. This
   reproduces with the "descent condition removed" edit of the seeded-bug check
   below. The condition costs nothing on accepted trials, because the
   accepted trial's solve is the epoch's consequent stage. When steps already
   descend, the trajectory is identical to plain gradient descent. A first
   version compared the loss at the *old* consequents. It was dropped because
   that loss is much more curved than `S`, so it halved steps `S` accepts. This
   is the one behaviour beyond the issue's text, and it is listed for sign-off
   with decision 4.
2. **Every candidate state is LSE-consistent.** The operations run in the
   order the issue gives: solve, step, solve, step. Each epoch is scored after
   its solve, so the state compared on validation, and possibly returned, has
   consequents solved at its own premise. Epoch 0 is the M2 state.
3. **Training rows are fixed at the warm start.** Rows dropped by FR-12 at the
   warm start stay dropped, and a step that would stop a kept row from firing
   is rejected. Otherwise a step could lower the loss by pushing hard rows out
   of every support, which matters for compact shapes such as the triangle.
4. **Row weights.** The premise stage descends the same weighted data term
   the solve minimizes. Without weights this is section 6.4's `L`.
   `loss_history` keeps the M2 unweighted definition.
5. **Without validation, the last state.** With decision 1 it is also the
   state with the lowest `S`.
6. **Defaults are unchanged from M2.** `fd_step = 6e-6` (the cube root of
   float64 epsilon), `patience = 10`, `max_halvings = 5`,
   `premise_lr = 1e-2`. The planted fixtures need rates of 50 to 1e4, because
   their residual is near zero and the gradients are tiny. A real archive fit
   has a larger residual, so a default tuned on planted data would be wrong
   there. The archive fit sets `premise_lr` from its validation split, and the
   default is part of decision 4.
7. **One-sided differences and zero gradients are not reported.**
   `TrainingDiagnostics` has no field for them, and its field list is fixed by
   #57 (FR-11), which this slice does not reopen. The M3 findings doc wants
   "how many parameters had identically-zero gradient at the returned epoch"
   (section 6.4). The proposal on #60 is a small public helper here, added in
   step 9, that evaluates the premise gradient of a returned model for
   `scripts/train_anfis.py` to write into the metrics JSON.
8. **IT2 differentiates the Nie-Tan output (decision 6).** The finite
   differences go through the trainer's forward pass, whose IT2 weights use
   both firing bounds, so `gradients.py` and this stage differentiate the
   same function.

## Verification

At `6d98f0d` (code and tests) on the pinned stack (numpy 2.4.4, scipy
1.17.1, ruff 0.15.12, mypy 1.20.2, pytest 9.0.3) under Python 3.13.16, in a
Linux cloud sandbox. Provisional: NFR-8's canonical record is the batch
desktop run.

- `python -m ruff check .`: passed
- `python -m ruff format --check .`: passed
- `python scripts/check_ids.py`: passed
- `python -m mypy --strict`: passed (43 source files)
- `python -m pytest tests/test_anfis.py -q`: 58 passed
- `python -m pytest tests/ -q -p no:cacheprovider`: 878 passed, 1 skipped.
  The skip is `test_the_committed_survey_reproduces_from_the_archive`, which
  needs the `calibration-data` ref that a shallow clone lacks.
- `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider`:
  879 collected; NC-021.
- `git diff main -- src/superconducted/fuzzy/tsk.py src/superconducted/channels/kraus.py src/superconducted/interfaces.py src/superconducted/types.py pyproject.toml`:
  empty.

**Seeded-bug check.** Each line is a one-line edit of `anfis.py`, run against
`tests/test_anfis.py` and then reverted. All 23 are caught at `6d98f0d`.

| Seeded bug | Caught by |
| --- | --- |
| Gaussian `sigma`, IT2 `sigma_high`, or tanh slopes not in log space | log-space mask test |
| log entry perturbed linearly in the difference | gradient test |
| central difference off by a factor of 2 | gradient test |
| perturbed MFs not restored after the gradient | gradient test |
| step taken uphill | ordering-constraint step test |
| no halving | ordering-constraint step test |
| zero-gradient entries sent through `exp(log(.))` | ordering-constraint step test |
| descent condition removed | descent-condition step test |
| current premise not restored after rejected trials | oversized-rate test |
| rejections not counted | oversized-rate test |
| zero gradient counted as a rejection | premise-free rule base test |
| solver accepts a premise that stops a kept row firing | solver-domain test |
| premise objective ignores row weights | weighted-ridge gradient test |
| solver score drops the ridge term, or ignores weights | weighted-ridge gradient test |
| last state returned instead of best; best premise not written back | early-stopping test |
| patience off by one; `early_stopped` always false | early-stopping test |
| validation selection on training loss | early-stopping test |
| `gradient="analytic"` not refused | analytic-gradient test |

The recorded 3x3x3 measurements reproduce with the commands in
`docs/evidence/anfis-premise-stage/README.md`, at `f5cdfb3`, which adds only
the script to `6d98f0d`.

## Related docs

- Issue #60, sections 6.4, 7 (decisions 4 and 6) and 9; the M2 decision
  record in its thread
- `docs/implementations/2026-10-11-anfis-trainer-m2-core.md` and
  `docs/implementations/2026-10-15-pr114-review-fixes.md`
- ADR-014, ADR-018, ADR-023 and ADR-024 in `docs/decisions.md`
- NC-021 and NC-041 in `docs/numerical-claims.md`
- `docs/evidence/anfis-premise-stage/README.md`
