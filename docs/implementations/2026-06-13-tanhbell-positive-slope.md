# 2026-06-13: tanhbell-positive-slope

## Problem / Motivation

`TanhBellMF` validated only `slope == 0`, silently accepting a negative
slope. A negative slope inverts the bell so that the raw value falls near
`-1` between `left` and `right`; constructing the resulting
`MembershipDegree` would raise via its `0 <= low <= high <= 1` invariant
(`types.py:31`), turning a meaningless parameterization into a late,
opaque failure instead of a guard at the call site. The existing
`test_tanh_bell_invalid_params` covered
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
correctly. At the time of this change `TanhSigmoidMF` was left as
`slope != 0` — it stays in `[0, 1]` for either sign of slope, so it did
not share the bell's `[0, 1]` violation. That guard was subsequently
tightened to `slope > 0` as well, for orientation consistency rather than
correctness — see `2026-06-13-tanh-sigmoid-positive-slope.md`.

## Mathematical / Statistical details

The bell is `μ(x) = (tanh(s·(x − L)) − tanh(s·(x − R))) / 2` with `L < R`.

- For `s > 0` and `L < x < R`: `s·(x − L) > 0 → tanh ≈ +1` and
  `s·(x − R) < 0 → tanh ≈ −1`, so `μ ≈ (1 − (−1))/2 = 1`. Outside `[L, R]`
  both terms share a sign and the difference decays to `0`. Range `⊆ [0, 1]`.
- For `s < 0` and `L < x < R`: the two tanh signs flip, giving
  `μ ≈ (−1 − 1)/2 = −1`. This sub-zero value cannot form a valid
  `MembershipDegree` (it raises on the `0 <= low` bound), so `s > 0` is
  the correct precondition.

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

- `2026-06-13-tanh-sigmoid-positive-slope.md` — applies the same
  `slope > 0` convention to `TanhSigmoidMF`.
- ADR-006 (membership function shape, **Open**) in `docs/decisions.md`.
  The `slope > 0` convention enforced here is being recorded as ADR-018
  (new ADR, separate PR), not by amending the Open ADR-006.
