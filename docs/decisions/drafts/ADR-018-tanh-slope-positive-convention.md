# ADR-018 — Tanh-based MF slope positivity convention

**Status**: Draft.

**Context**: All tanh-based membership functions in this project use a
parameterization of the form:

    mu(x) = clip(0.5 * (tanh(s_L * (x - L)) - tanh(s_R * (x - R))), 0, 1)

where `s_L` and `s_R` are slope parameters and `L < R` are the left and
right center points. When a slope is zero, the corresponding `tanh` term
collapses to zero, destroying the window shape. When a slope is negative,
the `tanh` term inverts, and the `clip(0, 1)` masks the invalid
parameterization by clamping degenerate output to zero · hiding a
configuration error rather than surfacing it.

The bootstrap `TanhMF` implementation (`fuzzy/membership.py:179-186`)
already enforces `slope > 0` via `_validate`. PR #14 proposes
`TanhSigmoidMF` and `TanhBellMF`, which face the same constraint. This
ADR formalizes the convention across all tanh-based MFs.

**Decision**: All tanh-based membership functions require strictly
positive slope parameters. Constructors must reject `slope <= 0` with
`ValueError`. This applies to:

- `TanhMF` (bootstrap, `fuzzy/membership.py`)
- `TanhSigmoidMF` (PR #14)
- `TanhBellMF` (PR #14)
- Any future tanh-based MF subclass

**Consequences**:

- The ANFIS trainer (ADR-014), when implemented, must constrain the
  premise-parameter search space to positive slopes. Gradient-based
  optimization should use a log-space parameterization or an
  exponentiated reparameterization to keep slopes in the valid domain
  during training.
- `set_parameters` on any tanh-based MF must re-validate after parameter
  updates.
- The `IntervalGaussianMF` and other non-tanh MFs are unaffected.

**Source**: PR #14 review thread (mertefesensoy); existing enforcement at
`fuzzy/membership.py:182`; Issue #2.
