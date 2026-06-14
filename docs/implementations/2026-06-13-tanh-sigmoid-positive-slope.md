# 2026-06-13: tanh-sigmoid-positive-slope

## Problem / Motivation

`TanhBellMF` already required `slope > 0` (a non-positive slope inverts
the bell and produces degrees near `-1`, violating the `[0, 1]`
invariant — see `2026-06-13-tanhbell-positive-slope.md`), but the guard
was duplicated inline in both `__init__` and `set_parameters`, and the
sibling `TanhSigmoidMF` enforced only `slope != 0`. That left the two
tanh primitives inconsistent: the sigmoid accepted a negative slope,
which silently flips its orientation to monotonically *decreasing*. While
that does not breach `[0, 1]`, it makes the parameter sign ambiguous for
the ANFIS trainer (two parameterizations describe mirror-image curves)
and diverges from the positive-orientation convention every other tanh
shape follows. This change makes the precondition uniform — `slope > 0`
on both classes — and centralizes each class's checks in a `_validate`
helper so the constructor and `set_parameters` cannot drift apart.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/membership.py` | `TanhSigmoidMF` now requires `slope > 0` (was `!= 0`); both `TanhSigmoidMF` and `TanhBellMF` route constructor + `set_parameters` validation through a single `_validate` static method (mirrors `TanhMF`/`TriangularMF`). |
| `tests/test_membership.py` | `test_tanh_sigmoid_invalid_slope` and `..._set_parameters_validates` now assert negative slope is rejected; removed the obsolete `test_tanh_sigmoid_negative_slope_decreasing` (it asserted the old accept-and-decrease behavior). |
| `docs/implementations/2026-05-19-tanh-membership-functions.md` | Corrected the now-stale claims that the sigmoid admits either slope sign. |

## Implementation approach

Extracted the per-class precondition into a `_validate` static method on
each concrete `MembershipFunction`, following the established pattern in
`TanhMF`, `TriangularMF`, and `TrapezoidalMF`:

- `TanhSigmoidMF._validate(slope)` raises `ValueError` unless `slope > 0`.
- `TanhBellMF._validate(left, right, slope)` raises unless `slope > 0`
  **and** `left < right`.

Both `__init__` and `set_parameters` now call `_validate` before
assigning, eliminating the two duplicated copies of the check in each
class — a copy that could (and in the sigmoid's case did) fall out of
sync. No change to `degree`, parameter layout, or `parameter_count`.

## Mathematical / Statistical details

`TanhSigmoidMF`: `mu(x) = (tanh(s·(x − c)) + 1) / 2`.

- `s > 0` ⇒ strictly increasing, `mu(c) = 0.5`, saturating to `1` as
  `x → +∞` and `0` as `x → −∞`.
- `s < 0` ⇒ strictly *decreasing* — still inside `[0, 1]` (so, unlike the
  bell, no invariant is violated), but the orientation is flipped. The
  pair `(c, s)` and `(c, −s)` then describe mirror-image curves, so the
  sign of `s` is not uniquely determined by the shape. Requiring `s > 0`
  removes that degeneracy and fixes "membership increases with the
  argument" as the canonical reading.
- `s = 0` ⇒ `mu ≡ 0.5`, a constant carrying no discriminative
  information.

`TanhBellMF`: `mu(x) = (tanh(s·(x − L)) − tanh(s·(x − R))) / 2`, `L < R`.
For `s > 0`, `mu ≈ 1` on the plateau `L < x < R` and decays to `0`
outside; for `s ≤ 0` the bell inverts toward `-1` between `L` and `R`,
which `degree` does not clip — a genuine `[0, 1]` violation. The math is
unchanged here; this change only relocates the existing guard into
`_validate`.

## Design decisions

- **Sigmoid: convention, not correctness.** A negative-slope sigmoid is
  numerically in range, so this is a deliberate API-consistency choice,
  not a crash fix. It was made because (a) the trainer benefits from an
  unambiguous parameter sign and (b) a single `slope > 0` rule across all
  tanh shapes is easier to reason about than per-class exceptions. The
  prior session had flagged the asymmetry and tested the accept-behavior;
  this change reverses that decision per explicit request and replaces
  the test accordingly.
- **`_validate` extraction over inline checks.** Chosen to match the rest
  of the module and to guarantee the constructor and `set_parameters`
  enforce identical preconditions — the inline duplication was the
  mechanism by which the sigmoid's two sites could have diverged.
- **Alternative rejected: clip in `degree`.** Same rationale as the bell
  doc — masking an out-of-orientation parameterization hides a meaningless
  input instead of rejecting it up front.

## Verification

- `python -m pytest tests/test_membership.py -q` → 34 passed.
- `python -m mypy --strict src/superconducted/fuzzy/membership.py`
  → Success.

## Related docs

- `2026-06-13-tanhbell-positive-slope.md` — the prior tightening of the
  bell's slope guard from `== 0` to `<= 0`.
- `2026-05-19-tanh-membership-functions.md` — original introduction of
  both tanh primitives (corrected by this change re: sigmoid slope sign).
- ADR-006 (membership function shape, **Open**) in `docs/decisions.md`.
  The `slope > 0` convention this doc enforces is not yet recorded in an
  ADR; it is being filed as ADR-018 (new ADR enumerating the two shapes
  and locking the convention) in a separate PR, rather than by amending
  the Open ADR-006.
