# 2026-06-13: tanhbell-positive-slope

## Problem / Motivation

`TanhBellMF` validated only `slope == 0`, silently accepting a negative
slope. Because `TanhBellMF.degree` (unlike `TanhMF.degree`) does **not**
clip its output, a negative slope inverts the bell and produces membership
degrees near `-1` between `left` and `right`, violating the `[0, 1]`
membership invariant. The existing `test_tanh_bell_invalid_params` covered
`slope == 0` but not the negative case, so the gap was untested. This was
raised as review feedback on the `feature/baha-tanh-mf` branch.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/membership.py` | `TanhBellMF.__init__` and `set_parameters` now reject `slope <= 0` (was `== 0`); docstring states the `slope > 0` contract and why. |
| `tests/test_membership.py` | `test_tanh_bell_invalid_params` now also asserts a negative slope raises `ValueError`. |

## Implementation approach

Tightened the guard in both validation sites (constructor and
`set_parameters`) of the concrete `TanhBellMF` implementation of the
`MembershipFunction` ABC from `slope == 0` to `slope <= 0`, with the error
message updated to `requires slope > 0`. No change to `degree`, parameter
layout, or `parameter_count` — the contract is unchanged, only enforced
correctly. `TanhSigmoidMF` is intentionally left as `slope != 0`: it is a
monotonic sigmoid that stays in `[0, 1]` for either sign of slope, so only
`TanhBellMF` requires strict positivity.

## Mathematical / Statistical details

The bell is `μ(x) = (tanh(s·(x − L)) − tanh(s·(x − R))) / 2` with `L < R`.

- For `s > 0` and `L < x < R`: `s·(x − L) > 0 → tanh ≈ +1` and
  `s·(x − R) < 0 → tanh ≈ −1`, so `μ ≈ (1 − (−1))/2 = 1`. Outside `[L, R]`
  both terms share a sign and the difference decays to `0`. Range `⊆ [0, 1]`.
- For `s < 0` and `L < x < R`: the two tanh signs flip, giving
  `μ ≈ (−1 − 1)/2 = −1`. Since `degree` does not clip, this leaks out of
  range. Hence `s > 0` is the correct precondition.

## Design decisions

Two parts were required, not just a test: a test expecting `ValueError`
on negative slope would fail against the old code, which accepted it.
The alternative — clipping in `degree` to tolerate any slope — was
rejected because it masks a meaningless (inverted) parameterization and
diverges from validating preconditions up front, which is how every other
MF in this module behaves.

## Verification

- `python -m pytest tests/test_membership.py -q -k TanhBell` → 4 passed.

## Related docs

- `docs/decisions.md` (membership-function contracts)