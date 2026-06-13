# 2026-05-19: tanh-membership-functions

## Problem / Motivation

The membership-function library shipped Gaussian, Triangular, Trapezoidal,
the difference-of-tanh `TanhMF`, and the IT2 `IntervalGaussianMF`, but it
lacked the two elementary tanh primitives the advisor flagged as
first-priority benchmarking shapes: a monotonic *sigmoid* edge and a
*bell* (plateau with smooth shoulders). Without them the fuzzy front-end
could not express "everything above a soft threshold" (sigmoid) or "a
band of acceptable values with uncertain edges" (bell) as single
parameterized units suitable for the future ANFIS trainer. This change
adds `TanhSigmoidMF` and `TanhBellMF` as concrete
`MembershipFunction` implementations with unit tests.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/membership.py` | Added `TanhSigmoidMF` (monotonic tanh sigmoid, params `[center, slope]`) and `TanhBellMF` (difference-of-tanh bell, params `[left, right, slope]`). |
| `tests/test_membership.py` | Added `TestTanhSigmoidMF` (range/center, monotonicity, asymptotes, invalid slope) and `TestTanhBellMF` (range/peak, symmetry, decay, invalid params), later hardened — see Verification. |

## Implementation approach

Both classes are concrete subclasses of the `MembershipFunction` ABC in
`interfaces.py` and follow the same flat `parameters()` /
`set_parameters()` contract every other MF exposes, so the ANFIS
optimizer can read and write premise parameters generically without
knowing the shape. Each validates its preconditions identically in the
constructor and in `set_parameters`, raising `ValueError` on violation,
and reports `is_interval_type2 == False` (both are Type-1).

- `TanhSigmoidMF` rescales a single `tanh` into `[0, 1]`. Parameter
  vector `[center, slope]`, `parameter_count == 2`. At introduction it
  required only `slope != 0` (a zero slope collapses the function to the
  constant `0.5`); a negative slope was accepted because the output stays
  in range. This was later tightened to `slope > 0` for orientation
  consistency with the other tanh shapes — see
  `2026-06-13-tanh-sigmoid-positive-slope.md`.
- `TanhBellMF` subtracts two `tanh` edges sharing one slope to form a
  bell. Parameter vector `[left, right, slope]`, `parameter_count == 3`.
  It requires `left < right`. At introduction it validated `slope == 0`
  only; the strict `slope > 0` precondition was tightened later — see
  `2026-06-13-tanhbell-positive-slope.md`.

Neither shape clips its output (unlike `TanhMF`), so correctness rests
entirely on the validated preconditions keeping the raw expression in
`[0, 1]`.

## Mathematical / Statistical details

**Sigmoid.** `TanhSigmoidMF` maps the symmetric `tanh ∈ (−1, 1)` onto
the membership range `(0, 1)`:

```
mu(x) = (tanh(s · (x − c)) + 1) / 2
```

with center `c` and slope `s`. Because `tanh` is bounded and strictly
monotone in its argument:

- `mu(c) = (0 + 1)/2 = 0.5` exactly — the center is the half-membership
  crossover.
- `s > 0` ⇒ `mu` strictly increasing; `s < 0` ⇒ strictly decreasing.
  Either way the range is `(0, 1)`, so no clipping is needed.
- Saturation: as `x → +∞`, `tanh → +1` and `mu → 1`; as `x → −∞`,
  `tanh → −1` and `mu → 0`. The transition width is set by `|s|` (larger
  `|s|` ⇒ sharper step). `s = 0` would pin `mu ≡ 0.5`, hence the slope
  guard — later tightened from `!= 0` to `> 0`
  (`2026-06-13-tanh-sigmoid-positive-slope.md`).

**Bell.** `TanhBellMF` is the difference of a rising and a falling tanh
edge, scaled by one half:

```
mu(x) = (tanh(s · (x − L)) − tanh(s · (x − R))) / 2,   L < R
```

For `s > 0`:

- Inside the band, `L < x < R`: the left term saturates toward `+1`
  (argument positive) while the right term saturates toward `−1`
  (argument negative), so `mu ≈ (1 − (−1))/2 = 1` — a **plateau near 1**.
- Outside the band both tanh terms share a sign and nearly cancel, so
  `mu` **decays to 0** as `|x| → ∞`.
- The function is symmetric about the band midpoint `(L + R)/2`, since
  the two edges are mirror images about that point.

The **plateau-with-uncertain-edges** rationale: the flat top encodes a
core region of *full* membership — values unambiguously "in" the
concept — while the two tanh shoulders are deliberately *soft* rather
than vertical, modeling genuine measurement/decision uncertainty about
where the concept's boundary lies. The slope `s` is the single knob for
that edge uncertainty: large `s` approaches a crisp interval (sharp,
near-rectangular boundaries), small `s` widens the fuzzy shoulders. One
shared slope keeps the bell symmetric and the parameter count minimal
(3), which matters for ANFIS gradient updates. The `s > 0` orientation
is what makes the inside-the-band sign pattern produce `+1` rather than
`−1`; a non-positive slope inverts the bell and breaks the `[0, 1]`
invariant (the later doc tightens the guard to enforce this).

## Design decisions

- **Two primitives, not one.** `TanhMF` already provides a
  per-edge-slope bell; `TanhSigmoidMF` and `TanhBellMF` were added as the
  minimal, advisor-requested shapes — a pure monotonic edge and a
  single-slope symmetric bell — that are cheaper to parameterize and
  easier to interpret for benchmarking. The single shared slope in
  `TanhBellMF` (vs. `TanhMF`'s two) is the deliberate distinction:
  fewer parameters, guaranteed symmetry.
- **No clipping in `degree`.** Following the rest of the module's
  "validate preconditions up front" style rather than `TanhMF`'s
  defensive `clip`, so an out-of-range output signals a programming
  error instead of being silently masked. The cost is that the slope
  precondition must be correct — which is exactly the gap closed by the
  follow-up `2026-06-13-tanhbell-positive-slope.md`.
- **Sigmoid slope sign (superseded).** This suite originally allowed
  either slope sign — the sigmoid stays in range for `s < 0` (it just
  decreases), so only `s == 0` was rejected. That was reversed to
  `s > 0` for orientation consistency across the tanh shapes; see
  `2026-06-13-tanh-sigmoid-positive-slope.md` for the rationale.

## Verification

- `python -m pytest tests/test_membership.py -q -k "TanhSigmoid or TanhBell"`
  → 15 passed.
- `mypy --strict src/superconducted/fuzzy/membership.py`

The suites were hardened after the initial commit to close coverage gaps
that mirrored the parity the Gaussian/IT2 suites already had:

- **Round-trip** (`parameters()` ↔ `set_parameters()`) for both classes,
  asserting shape and value equality after a write — previously untested
  for the tanh shapes.
- **`is_interval_type2` / `is_crisp`** assertions confirming both are
  Type-1 crisp MFs.
- **`set_parameters` validation** — the bell re-rejects `slope <= 0` and
  `left >= right`; the sigmoid re-rejects an invalid slope (originally
  `== 0`, now `<= 0`).
- **Sigmoid slope sign** — at the time of this suite the sigmoid accepted
  a negative slope (decreasing but in range), rejecting only `slope == 0`.
  That contract was later changed to `slope > 0`; the corresponding test
  now asserts negative-slope *rejection* — see
  `2026-06-13-tanh-sigmoid-positive-slope.md`.
- **Tightened bell peak tolerance** `abs=1e-2 → 1e-4`. The closed form at
  the band center is `(tanh(6) − tanh(−6))/2 = 0.99998771…`, a gap to 1
  of `≈1.23e-5`, so `1e-4` is a meaningful bound (the old `1e-2` would
  have passed values far from the true peak).

## Related docs

- `2026-06-13-tanhbell-positive-slope.md` — tightens `TanhBellMF` slope
  validation from `== 0` to `<= 0`.
- `2026-06-13-tanh-sigmoid-positive-slope.md` — tightens `TanhSigmoidMF`
  to `slope > 0` and centralizes both classes' checks in `_validate`.
- ADR-006 (membership function shape, **Open**) in `docs/decisions.md`
  — enumerates both tanh shapes but does not lock the `slope > 0`
  convention; that convention is being recorded separately as ADR-018
  (new ADR, separate PR) rather than by amending the Open ADR-006.
