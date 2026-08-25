# 2026-08-20: adr-023-tanhmf-clip-exemption

## Problem / Motivation

Issue #28. `TanhMF.degree()` clamped its output into `[0, 1]` and was
the only membership function in `src/superconducted/fuzzy/membership.py`
that clamped at all. ADR-018 had taken the opposite position for the
tanh shapes it governs — out-of-domain parameters are a
construction-time error and "no clipping is implemented anywhere in
either class."

The divergence was previously recorded in ADR-006's revisit note. PR #26
(`049b336`) replaced that note with a one-line handoff to ADR-018, but
ADR-018 governs `TanhSigmoidMF` and `TanhBellMF` and says nothing about
`TanhMF`. The slope half of the note was delegated correctly; the clip
half was dropped. The ledger was left silent on a convention divergence
that has a gradient consequence for the ADR-014 trainer.

This is not a bug report. The clamp was not producing incorrect output.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/membership.py` | `TanhMF.degree()` keeps `max(0.0, raw)` and drops the provably-dead `min(1.0, ...)`; the class docstring's formula and range discussion are corrected. |
| `docs/decisions.md` | New ADR-023 recording the output-range convention and `TanhMF`'s floor exemption, plus cross-references from ADR-006 and ADR-018. |
| `tests/test_membership.py` | Three tests: the negative-tail regression case, an in-domain passthrough case, and a seeded randomized range property. |
| `docs/implementations/2026-08-20-adr-023-tanhmf-clip-exemption.md` | This document. |

## Implementation approach

The issue's step 2 asked whether the clamp is reachable under parameters
that pass `_validate`, noting that if it is not, removal is a no-op
cleanup. It is reachable, so the decision went the other way: keep the
floor, document the exemption, and delete only the half that is
genuinely dead.

The change to `degree()` is one line — `max(0.0, min(1.0, raw))` becomes
`max(0.0, raw)` — plus a comment recording why the floor stays and why
no ceiling is needed. The docstring formula changes from
`clip(..., 0, 1)` to `max(..., 0)` and gains a paragraph describing the
negative tail, because the previous text implied the shape is naturally
bounded in `[0, 1]`, which is what led the issue to hypothesize dead
code in the first place.

## Mathematical / Statistical details

`TanhMF` is a difference of two tanh sigmoids:

```
raw(x) = 0.5 * (tanh(s_L * (x - L)) - tanh(s_R * (x - R)))
```

`_validate` requires `L < R`, `s_L > 0`, `s_R > 0`. It does **not**
require `s_L == s_R`.

**Lower bound — the floor is load-bearing.** Because `tanh` is strictly
increasing, the sign of `raw` follows the ordering of its two arguments:

```
raw(x) < 0  <=>  s_L * (x - L) < s_R * (x - R)
```

Solving for `x` gives the sign-change point

```
x* = (s_L * L - s_R * R) / (s_L - s_R)      (s_L != s_R)
```

with two cases:

- `s_L > s_R`: then `x* - L = s_R * (L - R) / (s_L - s_R) < 0`, so
  `x* < L` and `raw < 0` on the far-left tail `x < x*`.
- `s_L < s_R`: symmetrically `x* > R` and `raw < 0` on the far-right
  tail `x > x*`.
- `s_L == s_R`: `x - L > x - R` for all `x`, so monotonicity gives
  `raw >= 0` everywhere. This is the only safe case.

The infimum is `-0.5`: as `s_L -> infinity` the first `tanh` saturates
to `-1` just below `L`, while `s_R -> 0` sends the second toward `0`,
giving `0.5 * (-1 - 0) = -0.5`. It is approached, never attained.

Verified numerically over 400,000 randomized `_validate`-passing
parameterizations (`L` uniform on `[-50, 50]`, span uniform on
`(0, 100]`, both slopes log-uniform on `[e^-8, e^8]`, `x` sampled across
and beyond the band): observed minimum `-0.4996`, consistent with the
`-0.5` infimum. Worked example: `L=0, R=1, s_L=10, s_R=0.1` at `x = -1`
gives `raw = -0.4013`. `MembershipDegree` enforces
`0 <= low <= high <= 1` and raises `ValueError` on that value, so
without the floor `degree()` raises for a parameterization the class
accepts.

**Upper bound — the ceiling is dead.** With `a = tanh(...) < 1` and
`b = tanh(...) > -1`, `raw = 0.5 * (a - b) < 1` strictly. In float64,
`tanh` rounds to exactly `±1` for `|arg| >= ~20`, so `raw` can equal
`1.0` but never exceed it; the randomized sweep confirms a maximum of
exactly `1.0`. A `min(1.0, ...)` term can therefore never bind.

**Gradient consequence.** The floor makes `d(mu)/d(theta) = 0` for every
premise parameter wherever `raw < 0` — one tail, beyond `x*`. This is
the same zero-gradient pathology ADR-012 records for `ProbabilityClip`
one layer downstream, and it is why the issue required this to close
before ADR-014 trainer work begins.

## Design decisions

Three options were considered.

1. **Keep the floor as a documented exemption, drop the dead ceiling
   (chosen).** The negative tail is a property of the difference-of-tanh
   shape under legitimately unequal slopes, not a symptom of a bad
   parameterization. The reject-don't-clip convention is therefore
   scoped in ADR-023 to *parameters*, which `_validate` already policies,
   rather than to a shape's analytic range.
2. **Remove the floor entirely.** This is the literal reading of
   reject-don't-clip and the outcome the issue leaned toward. Rejected:
   `degree()` would raise in the tails for any asymmetric-slope MF, which
   introduces a defect rather than removing one.
3. **Keep the floor and tighten `_validate` to `s_L == s_R`.** Rejected:
   it deletes the asymmetric-edge shape family that ADR-006 ships and
   that the ADR-019 ablation is meant to evaluate.

Recorded as a new ADR-023 rather than as an extension of ADR-018's
Consequences. The decision has enough mathematical content to deserve
its own auditable entry, and ADR-018 stays scoped to the two classes it
was written for. ADR-006 and ADR-018 each gained a cross-reference so no
reader lands on a stale handoff.

If a future requirement makes the zero-gradient tail unacceptable, the
recorded fix is to change the shape — a product of sigmoids
`sigma(s_L * (x - L)) * sigma(-s_R * (x - R))` is bounded in `(0, 1)` by
construction — not to delete the floor. That is an ADR-006 shape change
with ablation consequences and is out of scope here.

## Verification

```
python -m pytest tests/test_membership.py -q      # 37 passed
python -m pytest tests/ -q                        # 152 passed
python -m ruff check .                            # All checks passed
python -m ruff format --check .                   # 34 files already formatted
python -m mypy --strict src/superconducted        # no issues in 22 source files
```

**Mutation check.** Replacing `floored = max(0.0, raw)` with
`floored = raw` fails exactly the two intended tests
(`test_asymmetric_slopes_floor_negative_tail` and
`test_degree_in_unit_interval_for_valid_params`) with
`ValueError: MembershipDegree requires 0 <= low <= high <= 1; got
low=-0.40109...`. Note that the 35 pre-existing tests all pass under
that mutation — the suite before this change would not have caught
removal of the floor, which is why the regression test was added rather
than relying on existing coverage.

## Related docs

- ADR-023, ADR-018, ADR-012, ADR-006 in `docs/decisions.md`
- `src/superconducted/fuzzy/squashing.py` · `ProbabilityClip`, same
  pathology one layer down
- Issue #28; Issue #20 (where this was surfaced); PR #26 (`049b336`)
