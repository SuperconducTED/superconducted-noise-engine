# 2026-09-15: pr68-m2-mapping-and-coverage

## Problem / Motivation

PR #68 was approved by @BurakOztekin and @mertefesensoy on 2026-09-08 at
`3f5e0f9`. Eleven commits landed after those approvals, and because `main`'s
merge ruleset does not dismiss stale reviews on push, the approvals still stood.
Among those commits was `e503e1e`, which added the three M2 shapes
(`TriangularMF`, `TrapezoidalMF`, `TanhBellMF`) that architect decision C3 had
deferred to a second commit, and `afe4d58`, which fixed a `ZeroDivisionError` in
them. A convention review of the PR head `8ec7d897` found that the fix at
`afe4d58` closed the crash but not the defect underneath it, and that the three
shapes had landed with no test coverage at all.

Three things were wrong at `8ec7d897`:

1. `_trapezoidal_partition` placed the plateau at `c_j - u_j/4` and
   `c_j + v_j/4` instead of section 6.3's `c_j -+ 0.5 r_j`. FR-9's bin-cover
   rule failed on all three real features.
2. `_tanh_bell_partition` used an edge-anchored mapping instead of section 6.3's
   center-anchored one. This falsified the exact consequence the PR was asking
   @BurakOztekin to ratify as section 7 decision 2: that under the equal-slope
   fallback every `TanhMF` row is pointwise identical to its `TanhBellMF` row.
3. No test in the suite called `grid_partition` with any of the three shapes, so
   FR-8 validity, FR-9 coverage and FR-10 determinism were all unasserted for
   them, and step 5c's section 9.1 compact-support cases and section 9.2
   unwrapped-raises contrast were absent. The one test that did mention
   `TanhBellMF` compared `TanhMF` against a hand-written copy of section 6.3's
   bell mapping rather than against `grid_partition`, so it stayed green while
   the shipped bell diverged from it.

Defect 2 is the one that mattered most for the merge gate. @bengisucvd ratified
decisions 1 and 3 on 2026-09-13 and put decision 2 back to @BurakOztekin as its
owner. The measurement that request rests on was wrong, so the gate could not
have been closed honestly on the tree as it stood.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/parameterization.py` | `_trapezoidal_partition` and `_tanh_bell_partition` now implement section 6.3's mappings; the skew test behind `tanh_floor_onsets` is relative (`SKEW_RTOL`) rather than exact; the dead `_SECOND_COMMIT_SHAPES` dispatch branch is removed. |
| `tests/test_parameterization.py` | Every shape-parametrized test runs over all seven shapes; the bell-identity test compares two `grid_partition` results; step 5c's compact-support and unwrapped-raises cases are added; FR-6's anchor-equals-center equality is asserted for all six peaked shapes rather than the Gaussian alone. |
| `docs/implementations/2026-09-08-mf-parameterization.md` | `## As of 2026-09-15` section correcting the two claims that went stale when the M2 shapes landed. |
| `docs/implementations/2026-09-14-recover-pr68-approved-tip.md` | `## As of 2026-09-15` section recording that the M2 shapes did land and that the deviation the recovery predicted survived the crash fix. |
| `docs/numerical-claims.md` | NC-021 re-measured, in the docs-only commit following this one, per Rule 6. |

## Implementation approach

No new abstraction. `grid_partition` already dispatches per shape through
`_SHAPE_BUILDERS`, and the fix is confined to two builder functions, each of
which now reads its parameters off `QuantileLayout.centers`, `.reaches` and
`.margins` rather than off `.edges`. That is the same source the other five
builders use, and using it is what makes the bell coincide with the `TanhMF`
equal-slope branch by construction rather than by coincidence.

The test change is a widening, not a rewrite. The suite already had the right
properties (FR-8 round trip, FR-9 cover, FR-10 determinism, step 9 acceptance);
they were parametrized over `M1_SHAPES` or over three hard-coded classes. They
now run over named tuples derived from one `ALL_SHAPES` constant, so a shape
added later cannot be silently skipped:

- `ALL_SHAPES` for validity and determinism,
- `COVERED_SHAPES` (all but the one monotone shape) for the bin-cover rule,
- `T1_SHAPES` (all but the one IT2 shape) for the `qubit_spread` rejection,
- `COMPACT_SUPPORT_SHAPES` for the two shapes with bounded support,
- `ARCHIVE_ACCEPTANCE_CASES` for step 9, pairing `NieTanDefuzzifier` with the IT2
  shape and `WeightedAverageDefuzzifier` with the other six.

## Mathematical / Statistical details

Write `c_j` for a bin's center, `e_(j-1)` and `e_j` for its edges,
`u_j = c_j - e_(j-1)`, `v_j = e_j - c_j`, `r_j = max(u_j, v_j)` for the reach and
`m_j = r_j / 4` for the margin.

**The bin-cover rule.** Each MF must read at least 0.5 across the whole of its
own bin. Since `c_j - r_j <= e_(j-1)` and `c_j + r_j >= e_j` by the definition of
`r_j`, it is enough for MF `j` to read at least 0.5 on `[c_j - r_j, c_j + r_j]`.
The bins tile `[lo, hi]`, so `max_j mu_j(x) >= 0.5` everywhere on the box. Note
that the bound is *attained*, not exceeded: three of the shapes read exactly 0.5
at `c_j +- r_j`, which is why the tests compare against `0.5 - 1e-12`.

**Trapezoid.** Section 6.3 gives `(a, b, c, d) = (c_j - 1.5 r_j, c_j - 0.5 r_j,
c_j + 0.5 r_j, c_j + 1.5 r_j)`. The left ramp is linear from `mu(a) = 0` to
`mu(b) = 1`, so

    mu(c_j - r_j) = (r_j / 2) / (b - a) = (r_j / 2) / r_j = 1/2

exactly, which is the bin-cover bound. The mapping that shipped at `8ec7d897`
used `b = c_j - u_j/4`, giving

    mu(c_j - r_j) = (r_j / 2) / (1.5 r_j - u_j / 4)

which at `u_j = r_j` is `0.5 / 1.25 = 0.4`. That is the 0.400 measured on all
three features: the plateau was roughly a quarter of the bin instead of half, so
the ramps were longer and the edge value fell below the bound.

**Bell.** Section 6.3 gives `left = c_j - r_j - m_j`, `right = c_j + r_j + m_j`
and `slope = atanh(0.8) / m_j`. At the bin edge `x = c_j + r_j`:

    x - right = -m_j,                  so tanh(slope * (x - right)) = -0.8
    x - left  = 2 r_j + m_j = 9 m_j,   so tanh(9 * atanh(0.8)) is about 1

and `mu = (1 + 0.8) / 2 = 0.9`, comfortably above the bound. The mapping that
shipped anchored `left` and `right` on the bin edges and took the slope from
`min(u_j, v_j) / 4`, which is a different shape on any skewed bin.

**Why the bell and `TanhMF` now coincide exactly.** `TanhBellMF.degree` is

    mu(x) = (tanh(s * (x - L)) - tanh(s * (x - R))) / 2

and `TanhMF.degree` is

    mu(x) = max(0, (tanh(s_L * (x - L)) - tanh(s_R * (x - R))) / 2).

Decision 2's equal-slope fallback sets `s_L = s_R = atanh(0.8) / m_j` and
`(L, R) = (c_j - r_j - m_j, c_j + r_j + m_j)`, which is now literally what
`_tanh_bell_partition` builds. With `L < R` and `s > 0`, `tanh` is strictly
increasing, so `tanh(s * (x - L)) > tanh(s * (x - R))` for every `x`; the
difference is strictly positive and the `max(0, .)` floor is inactive. The two
functions are therefore identical pointwise, not merely close, which is what
makes decision 2's stated cost real: until the trainer runs, a feature on the
fallback branch gives the same untrained ablation row for both shapes.

**When two half-reaches count as equal.** `tanh_floor_onsets` returns `+inf` for
a level whose bin is symmetric, because equal half-reaches give equal slopes and
`TanhMF` then has no floored tail. The test for that was `v != u`, exact. A
symmetric bin reaches `u_j` and `v_j` through different floating-point paths, so
they differ by a few ULPs, and the exact test therefore called such a level
skewed and evaluated `c_j - 2.5 u_j v_j / (v_j - u_j)` with a denominator of
about 1e-15: a huge finite number where the contract promises `inf`. It sits
outside the domain box either way, so no strategy decision ever changed, but the
function contradicted its own docstring and two of the suite's three fixtures
were on that path without saying so.

The comparison is now relative, against `SKEW_RTOL = 1e-9`. The threshold is not
tuned. Measured across every fixture and all three real features:

| Fixture | Relative skew `|v_j - u_j| / max(|u_j|, |v_j|)` per level |
| --- | --- |
| `_RNG_FREE_SKEWED` | 9.8e-16, 1.3e-01, 8.7e-01 |
| symmetric `linspace(0, 100, 1001)` | 0, 8.7e-16, 1.7e-15 |
| `left_skewed` | 4.7e-01, 5.1e-16, 2.0e-15 |
| `mean_T1` | 6.2e-01, 3.4e-01, 4.1e-01 |
| `mean_T2` | 6.3e-01, 6.4e-02, 4.5e-01 |
| `mean_readout_error` | 2.3e-01, 3.4e-01, 2.7e-01 |

A genuine skew is at least 6.4e-02 and a numerical tie at most 2.1e-15. Nothing
lies between, so the split is unambiguous by eleven orders of magnitude in both
directions. All three real features are far above the threshold, so the nine
pinned `x*_j`, the `equal-slope` branch each feature takes, NC-041 through
NC-044 and the test count are all unchanged.

**Measured, before and after**, on the 975-row committed survey at
`calibration-data@3d1569d`, over a 3001-point grid across each feature's
`[p1, p99]` box:

| Quantity | At `8ec7d897` | After this change |
| --- | --- | --- |
| Bin cover, `TrapezoidalMF`, all three features | 0.400 | 0.500 |
| Bin cover, `TanhBellMF`, T1 / T2 / readout | 0.901 / 0.900 / 0.902 | 0.900 |
| Largest membership gap between `TanhMF` and `TanhBellMF`, `mean_T1` | 0.9865 | 0.0 |
| Largest membership gap between `TanhMF` and `TanhBellMF`, `mean_T2` | 0.9891 | 0.0 |
| Largest membership gap between `TanhMF` and `TanhBellMF`, `mean_readout_error` | 0.8098 | 0.0 |

"Bin cover" is `min over x of max over j of mu_j(x).low`, the FR-9 quantity.
The "after" column is what the suite now pins:
`test_bin_cover_holds_on_the_real_quantiles` for the first two rows and
`test_the_equal_slope_fallback_coincides_with_tanh_bell` for the last three. The
"before" column is not pinned anywhere and is not registered as a claim; it is
the measurement that motivated the change, reproducible by reverting the two
builder functions.

**Unchanged by this change.** FR-11 non-degeneracy holds for all seven shapes on
all 975 surveyed vectors with no `ZeroDivisionError`, and the clamp counters
still report 44 clamped vectors attributed 16 / 11 / 20 across the three
features. Those were already correct at `8ec7d897` and are still pinned by
`test_the_measured_clamp_rate_is_pinned`. The layout itself is untouched, so
NC-041 through NC-044 are unaffected, and the nine `x*_j` onsets and the
`equal-slope` branch each feature takes are unchanged.

### FR-6 closed for all six peaked shapes

The definition of done asks for the layout-identity test to pass "for all landed
shapes", and FR-6 asks for a test pinning that the anchors are also the MF
centers for the six peaked shapes. Only `GaussianMF` was pinned, both on the
synthetic fixture and on the real quantiles. `test_peaked_shape_centers_are_the_anchors`
now covers all six, and the real-quantile layout-identity test loops over them
across all three features.

Writing it surfaced two things worth recording rather than smoothing over.

**`TanhMF` sits on its anchor only under the equal-slope branch.** Under
half-reach its parameters are `left = e_(j-1) - u_j/4` and `right = e_j + v_j/4`,
whose midpoint is

    (left + right) / 2 = c_j + 0.625 * (v_j - u_j)

which is the anchor only for a symmetric bin. FR-6's "for the six peaked shapes
these are also the MF centers" is therefore true of the shipped partition
because all three real features take decision 2's equal-slope fallback, not
because it holds for `TanhMF` unconditionally. The test asserts the branch
before it asserts the equality, so if decision 2 is answered the other way the
test says so instead of silently changing meaning.

**Three of the six agree only to rounding.** `GaussianMF`, `IntervalGaussianMF`
and `TriangularMF` store the anchor as a parameter, so the equality is
bit-exact. `TrapezoidalMF`, `TanhMF` and `TanhBellMF` reconstruct it as the
midpoint of two symmetric endpoints, and `(c - h) + (c + h)` does not always
round to exactly `2 c`: measured at exactly 1 ULP for `TanhMF` and `TanhBellMF`
on `mean_T1` (1.4e-14) and `mean_readout_error` (3.5e-18), and exact elsewhere.
The test splits the two cases rather than loosening both to a tolerance, so the
shapes that can be exact are still held to it. The reconstructed ones use
`rel=1e-12`, four orders above the observed rounding and many orders below a bin
width.

## Design decisions

**Fix the bell, not the `TanhMF` fallback.** The two disagreed, so one of them
had to move. Section 6.3's table specifies the bell as `c_j +- (r_j + m_j)` with
`slope = atanh(0.8) / m_j`, and specifies decision 2's fallback as "equal slopes,
coincides exactly with `TanhBellMF`". `_tanh_partition` already matched the
ticket; `_tanh_bell_partition` did not. Moving the bell is therefore the fix that
makes the code match the specification, and moving `TanhMF` instead would have
silently redefined the thing @BurakOztekin is being asked to ratify.

**Keep the M2 shapes rather than reverting them.** The alternative was to drop
`e503e1e` and its descendants and let M2 land as its own PR, which is what
`docs/implementations/2026-09-14-recover-pr68-approved-tip.md` planned. That was
the right call on 2026-09-14, when the shapes carried a crash. It is the wrong
call now: the crash was fixed at `afe4d58`, the remaining deviation is two
builder functions, and reverting would discard @yigit-arda's work and the
`ZeroDivisionError` fix only to re-land them a week later. Keeping them means
step 5c lands here, so step 5c's test obligations land here too, which is the
substance of this change.

**A tolerance on the bin-cover assertion, not a strict comparison.** Three shapes
attain 0.5 exactly at `c_j +- r_j`, so a dense grid that samples that point
computes it one ULP low; `TrapezoidalMF` on the synthetic fixture did exactly
that. The assertion is now against `0.5 - 1e-12`. That absorbs a ULP and nothing
else: the defect this test was widened to catch read 0.400, four orders of
magnitude outside the tolerance. Rounding the computed value instead would have
hidden which side of the bound the shape was on, which is the thing worth
knowing.

**A relative tolerance for the skew test, not a looser docstring.** The
alternative was to leave `v != u` alone and reword the docstring to describe
what it actually did. That trades a correct contract for a description of an
accident: the suite had two fixtures sitting on the huge-finite path and a
docstring promising `inf`, which is exactly how the mismatch stayed invisible.
Making the comparison relative makes the docstring true and lets
`test_an_unskewed_feature_keeps_the_half_reach_slopes` assert `isinf`, which is
strictly stronger than the old "not inside the box".

**Removing `_SECOND_COMMIT_SHAPES` is adjacent scope, and is flagged as such.**
With all seven shapes shipped the tuple is empty, which made its dispatch branch
unreachable and rendered the unknown-shape error with a trailing empty join, as
"the shipped shapes are GaussianMF, ..., TanhBellMF and .". It is three lines and
it sits in the function this change already edits, so it is fixed here rather
than filed.

## Verification

Run from a checkout of this commit. The `PYTHONPATH` prefix matters on a machine
with an editable install pointing at another checkout.

```
python -m ruff check .
python -m ruff format --check .
python -m mypy --strict
python -m pytest tests/ -q
python -m pytest tests/ --collect-only -q -o addopts=""
python scripts/check_ids.py
```

| Check | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 3 files would be reformatted, all pre-existing on `main` at `004e14e` and none touched here |
| `mypy --strict` | Success, 37 source files |
| `pytest tests/ -q` | 616 passed |
| `pytest --collect-only` | 616 collected |
| `scripts/check_ids.py` | No duplicate or colliding ADR / NC identifiers |

`tests/test_parameterization.py` goes from 94 to 123 collected, so this work
adds 29 tests and the suite moves 587 to 616, across three commits: the mapping
and coverage fixes, the `SKEW_RTOL` fix, and FR-6's anchor equality. NC-021 is
re-measured on a clean tree and moved in the docs-only commit that follows the
last of them, so the row can name the commit it was measured at, per
`docs/numerical-claims.md` Rule 6.

One environment note carried over from the review: `mypy --strict` as configured
(`python_version = "3.11"`) aborts on a `numpy` 2.4.4 stub before checking
anything, identically at `main` @ `004e14e`. The run above used
`--python-version 3.12`. That is a pre-existing condition of the repository and
is not addressed here.

The bin-cover and identity figures in the mathematics section reproduce with:

```
python -m pytest tests/test_parameterization.py -q -k "bin_cover or coincides_with_tanh_bell"
```

These runs are **provisional, laptop** (Mert's). Under architect decision C2 this
PR does not get its own desktop record; the numbers are included in the next
batch record `docs/verification/2026-09-XX-phase-3-batch-N-burak-desktop.md`.

## Related docs

- Issue #59 sections 6.3 (the per-shape mapping table), 7 (decision 2), 8 step
  5c, 9.1 and 9.2 (the compact-support and unwrapped-raises obligations)
- `docs/implementations/2026-09-08-mf-parameterization.md` and its
  `## As of 2026-09-15` section
- `docs/implementations/2026-09-14-recover-pr68-approved-tip.md` and its
  `## As of 2026-09-15` section
- PR #68, and the convention review of `8ec7d897` that found these
- The decision record of @bengisucvd of 2026-09-13, which ratifies decisions 1
  and 3 and puts decision 2 to @BurakOztekin
- ADR-006, ADR-018, ADR-019, ADR-023 in `docs/decisions.md`
- NC-021, NC-041, NC-042, NC-043, NC-044 in `docs/numerical-claims.md`
