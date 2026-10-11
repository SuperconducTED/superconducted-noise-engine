# 2026-10-11: ANFIS trainer M2 core

## Scope

Issue #60 starts with the `epochs=0` trainer core: batch ridge least squares
fits TSK consequents while premise membership functions remain fixed. The
implementation standardizes features and targets on training rows, solves in
that space, and maps the fitted rule base back to raw feature and target units.

The constructor defaults are `epochs=0`, `premise_lr=1e-2`, `ridge=1e-6`,
`seed=0`, `gradient="finite-difference"`, `fd_step=6e-6`, `patience=10`, and
`max_halvings=5`. Premise-related values are validated now so the public
configuration remains stable, although the M2 path performs no premise step.

The core accepts both shipped defuzzification paths. It obtains firing data
only through `TSKRuleBase.evaluate`, derives T1 or Nie-Tan effective weights,
and drops zero-firing rows before the least-squares solve.

## Deliberate boundaries

- Finite-difference premise optimization (`epochs > 0`) remains deferred to
  the next Issue #60 slice; it raises `NotImplementedError` rather than
  silently ignoring the requested epochs.
- `scripts/train_anfis.py`, archive fitting, model serialization, and the M3
  findings record remain outside this slice. They consume #63's dataset and
  #62's serializer contracts.
- No LOCKED module is changed: `fuzzy/tsk.py` is read through its public
  evaluation contract, and `channels/kraus.py` is untouched.

## Numerical method

For each standardized output, the design matrix concatenates
`effective_weight * [standardized_features; 1]` for each rule. The solver uses
`numpy.linalg.lstsq` on an augmented ridge system and penalizes deviation from
the warm-start consequents. With `ridge=0`, this is ordinary batch least
squares.

The returned rule base owns fresh consequent arrays and deep-copied membership
functions. The caller's membership and consequent values are never modified.
