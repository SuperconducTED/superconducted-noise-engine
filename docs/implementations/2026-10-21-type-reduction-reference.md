# 2026-10-21: type-reduction-reference

Issue #61 Part A, commit 1 of PR-A: the Karnik-Mendel reference and its certification
(FR-1, FR-2). The sweep (FR-3, FR-4), the findings doc and the NC rows follow in later
commits on the same branch. Measured on top of `main` @ `6cf008d` on Mert's laptop
(provisional; the canonical run is Burak's desktop batch). Python 3.12.10, numpy 2.4.4.

## Problem / Motivation

ADR-011 is Open. #109 item 4 says its closure waits on #61's measurement of the closed-form
IT2 reducer against the Karnik-Mendel (KM) type-reduced interval. #84 File 02 section 2.4
asked for that measurement to become the registered version of its own spike. A reference
that judges a reducer has to be certified first, and File 02 found that #61 section 6.3's
stop rule (`y' == y`) never terminates on some inputs. This commit provides the reference,
a second independent route to the same endpoints, and the tests that certify both before
anything is measured with them.

Decisions behind it, taken by the #61 owner (@bengisucvd) on 2026-10-21 when she
reviewed and approved the Part A plan. This document is their written record until they
are posted in the #61 thread.

- measure both BMM(1/2, 1/2), which is what `NieTanDefuzzifier` computes today, and
  textbook Nie-Tan, named by their literature names;
- do Part A before Part B;
- stop the iteration on the switch-point index, plus an exhaustive switch-point route;
- add a monotone guard to the stop.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/type_reduction_discrepancy.py` | New. Contains the guarded iterative KM (`karnik_mendel_type_reduce`, and `karnik_mendel_detailed` with pass counts), the exhaustive switch-point route (`exhaustive_type_reduce`), and the two closed-form reducers (`bmm_half_reduce`, `nie_tan_reduce`), all sharing one input contract. |
| `tests/test_type_reduction.py` | New, 32 tests. They check both routes against brute-force vertex enumeration, the analytic invariants, parity with the shipped defuzzifiers, Wu & Mendel 2019's worked example, the error contract and two mutation checks. |
| `docs/implementations/2026-10-21-type-reduction-reference.md` | This file. |

Nothing in `src/` changes: ADR-011's "no iterative numerical defuzzification at bootstrap"
stands, and #61 NFR-3 keeps `fuzzy/defuzzification.py` untouched.

## Implementation approach

All functions take one output dimension:

- per-rule firing bounds `lower`, `upper` with `0 <= lower <= upper`;
- crisp consequents `values`.

They sort the rules by `values` (a stable sort) and evaluate weighted averages
`Y(w) = sum w c / sum w` with one shared helper. The shared helper means the iterative and
exhaustive routes produce bitwise-identical numbers whenever they land on the same
vertex.

**Iterative KM (FR-1).**

1. Start from the midpoint weights.
2. Take the switch point `k = #{r : c_r <= y}` (`searchsorted(..., side="right")`).
3. Evaluate the switch vertex and repeat from step 2.

For `y_l`, the switch vertex puts the upper bound on the first `k` sorted rules and the
lower bound on the rest; `y_r` is the mirror image.

The iteration stops on whichever comes first:

- `k` is unchanged;
- a step fails to strictly improve `y` (the guard). The better of the two values is
  returned.

A cap of `n_rules + 1` passes raises `RuntimeError`.

**Exhaustive route.** Evaluate all `n_rules + 1` switch vertices for each endpoint and take
the min and the max. There is no iteration and no stop rule.

**Shared contract.**

- Inputs must be 1-D, equal-length, finite, non-empty, with `0 <= lower <= upper`;
  otherwise `ValueError`.
- A zero `lower.sum()` or `upper.sum()` raises `ZeroDivisionError`, mirroring
  `NieTanDefuzzifier.defuzzify`.
- Every function is pure.

## Mathematical / Statistical details

Notation. Sorted consequents `c_1 <= ... <= c_R`. The box
`B = prod_r [f_lo_r, f_hi_r]`. `Y(w) = sum_r w_r c_r / sum_r w_r`, with `y_l = min_B Y` and
`y_r = max_B Y`. The switch vertices are `w(l, k) = (f_hi_1..f_hi_k, f_lo_{k+1}..f_lo_R)`
and `w(r, k) = (f_lo_1..f_lo_k, f_hi_{k+1}..f_hi_R)`, for `k = 0..R`.

**Exhaustive route is exact.** `y_l = min_k Y(w(l, k))`.

1. Let `y* = y_l`, which exists because `B` is compact and `sum w >= sum f_lo > 0`.
2. Since `sum w > 0`, `Y(w) >= y*` holds exactly when
   `g(w) = sum_r w_r (c_r - y*) >= 0`. A minimizer gives `g = 0`, so `min_B g = 0`.
3. `g` is linear, so it is minimized by the upper bound where `c_r < y*` and the lower
   bound where `c_r > y*`. That is a switch vertex, which therefore attains `y*`.
4. Every switch vertex is in `B`, so none does better. This proves the claim.

The mirror argument gives `y_r`. The opened sources (Karnik & Mendel 2001 section 3.1; Wu
& Mendel 2009) state the one-switch sign rule of step 3 but not this minimum over switch
points, so it is derived here. The sources restrict `k` to `1..R-1`; `k = 0..R` is a
superset, and the two extra vertices are harmless.

**The iteration is monotone and stops at the endpoint, in exact arithmetic.** Write
`g_t(w) = sum_r w_r (c_r - y_t)`.

1. `y_t = Y(v)` for some `v` in `B` (the midpoint, or the previous vertex), so
   `g_t(v) = 0`.
2. The next vertex minimizes `g_t` over `B` (the sign rule), so `g_t <= 0` there, which
   means `y_{t+1} <= y_t`.
3. Equality holds exactly when `min_B g_t = 0`, that is, when `y_t = y_l`.
4. A repeated `k` means a repeated vertex, so the value is a fixed point and equals `y_l`.

**In float64 it can cycle, and the guard is what makes it terminate.**

- When firing is concentrated on rules whose consequents equal or nearly equal one value,
  every computed average rounds to that value or to one ulp beside it. `k` then flips
  between two values and neither `y' == y` nor `k' == k` ever holds.
- The smallest case found has **two rules with distinct consequents**. It is pinned as
  `CYCLE_*` in the tests: rule 2 fires about 1e-16 times as strongly as rule 1, and on the
  right endpoint `k` alternates 1, 0, 1, 0.
- With the guard, every accepted step strictly improves `y`. Since `k(y)` is monotone in
  `y`, `k` then moves strictly in one direction between evaluations. So an endpoint takes
  at most `R + 1` evaluations (in fact at most `k_0 + 1` on the left), and the cap cannot
  fire.
- The guard can stop within rounding of the endpoint rather than at the exact minimizer.
  The exhaustive route bounds that, and every test compares the two.

**Both reducers lie inside the band.**

- `f_lo`, `f_hi` and the midpoint are points of `B`, so `Y(f_lo)`, `Y(f_hi)` and
  `y_NT = Y(f_lo + f_hi)` all lie in `[y_l, y_r]`.
- `y_BMM = (Y(f_lo) + Y(f_hi)) / 2` is a convex combination of two of these, so it does
  too.
- Wu & Mendel 2019 make no general statement about this; it is derived here.

**Tolerance.**

- A weighted average with `w >= 0` carries about `2 R eps max|c|` of rounding error, and
  the tests allow `64 R eps max|c|`, 32 times that.
- A computed average can sit one ulp outside `[c_1, c_R]` (for example,
  `0.7 * 3.5 / 0.7 = 3.4999999999999996`). So endpoints are compared to tolerance, never
  for equality.

## Design decisions

- **Guard plus switch-point stop, rather than a tolerance stop `|y' - y| <= tol`.** A
  tolerance needs its own justified value and still does not exclude a cycle larger than
  `tol`. The guard needs no constant and comes with a termination argument.
- **Exhaustive route as the second implementation, rather than a vectorized prefix-sum
  version.** With `R = 27`, 28 evaluations per endpoint are cheap. Reusing the same
  `Y(w)` helper keeps the two routes bitwise comparable on a shared vertex, so any
  disagreement means a different vertex, not different arithmetic.
- **Kept in `scripts/`, imported by the tests.** This follows the FR-1 precedent
  (`tests/test_first_ensemble_run.py` imports `scripts.first_ensemble_run`).
  `mypy --strict` covers `scripts/` through `pyproject.toml`.
- **`nie_tan_reduce` raises on a zero lower sum, even though `Y(lower + upper)` alone would
  be defined there.** One contract for every function means the sweep never measures one
  reducer at a point where it has silently skipped the other.
- **`guard=False` on the private `_km_endpoint`.** It exists only so a test can show the
  switch-point stop alone cycles (a mutation check). No public path exposes it.
- **Reducer names.** `bmm_half_reduce` and `nie_tan_reduce` follow the literature (Wu &
  Mendel 2019, Eqs. 10 and 11), per the first decision above. Switching or renaming
  `NieTanDefuzzifier` is a separate PR, outside #61.

## Verification

Run from the repository root, in an environment with `requirements.txt` installed
(`PYTHONPATH=src` when the package is not installed in editable mode):

```bash
PYTHONPATH=src C:/pvci/Scripts/python.exe -m pytest tests/test_type_reduction.py -v
C:/pvci/Scripts/python.exe -m ruff check .
C:/pvci/Scripts/python.exe -m ruff format --check .
PYTHONPATH=src C:/pvci/Scripts/python.exe -m mypy
```

Results at this commit (laptop, provisional): 32 passed; ruff check and format clean;
`mypy --strict`: no issues in 44 source files. Full suite
(`pytest -q -x`): 891 passed in 219 s, which is `main`'s 859 plus the 32 new tests.

What the 32 tests establish:

- **Both routes against brute-force vertex enumeration** (`2^n` vertices). 200 random boxes
  for each `n` in `{1, 2, 3, 5, 8}`, half with tied consequents, about 15% of coordinates
  degenerate. Seed `6100 + n`.
- **Pass counts and ordering.** Pass counts stay within `n + 1`, and `y_l <= y_r`.
- **Analytic invariants.**
  - A degenerate box returns the weighted average for every function.
  - Both reducers lie inside `[y_l, y_r]`.
  - Endpoints are affine-equivariant, with `l` and `r` swapping when the scale is
    negative, and the band position is affine-invariant.
- **Parity with the shipped code.** `bmm_half_reduce` matches `NieTanDefuzzifier`, and
  `nie_tan_reduce` matches `WeightedAverageDefuzzifier` on an IT2 firing result, to 1e-12
  relative over 100 random 27-rule boxes.
- **Wu & Mendel 2019 (arXiv:1907.01697 v1) worked example, section II-H.** The firing
  bounds are recomputed from the stated Gaussians: centers +-1, `sigma` in `[0.5, 0.7]`,
  product t-norm, input `(-0.2, -0.3)`, consequents -1, -0.5, 0.5, 1. The computed values
  match the printed ones within half a unit in the fourth decimal: `y_l = -0.8846`,
  `y_r = 0.0058`, Nie-Tan -0.4794, BMM(0.5, 0.5) -0.5665. Table VI's four-decimal firing
  values would move `y_r` by about 4e-4, which is why the test recomputes them.
- **Mutation checks.**
  - The unguarded switch-point stop raises at the cap on the `CYCLE_*` box, while the
    guarded one stops and agrees with the exhaustive route.
  - A left endpoint built from the wrong splice is caught on every box except those whose
    endpoint sits at the all-lower or all-upper vertex, which the two families share. The
    test asserts both halves; on non-degenerate boxes the catch rate measured 100 of 100.
- **Error contract.** `ValueError` for each malformed input. `ZeroDivisionError` on a zero
  sum, including FR-1's smallest load-bearing case `lower=[0,0], upper=[1,0],
  values=[0,1]`.
- **Purity.** No input array is mutated.

New tests for NC-021: +32 at this commit, counted differentially (#61 NFR-7).

## Related docs

- Issue #61 (Part A, FR-1, FR-2, section 6.3), #84 File 02 section 2.4 (comment
  5885404218), #109 item 4, #60 decision 6.
- ADR-011 in `docs/decisions.md` (Open; closure lands after ADR-009, not in this PR).
- Karnik & Mendel 2001, *Inf. Sci.* 132, section 3.1; Wu & Mendel 2009, "Enhanced
  Karnik-Mendel algorithms", *IEEE TFS* 17(4); Mendel & Liu 2007, *IEEE TFS* 15(2); Wu &
  Mendel 2019, arXiv:1907.01697 v1, Eqs. (9) to (11) and section II-H.
