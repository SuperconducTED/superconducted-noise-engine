# 2026-09-08: manual MF parameterization from the archive's feature distribution

Issue #59 (M1), PR #68. This record covers the review round that followed the
first review of PR #68 — the module and the survey script were already on the
branch; this round fixed the mapping defects, added the test suites, re-ran the
survey at a pinned ref, and registered the claims.

## Problem / Motivation

ADR-019's shape ablation has been blocked since 2026-08-20 on prerequisite (b):
"a manual parameterization provides non-trivial MF parameters for each candidate
shape." Nothing on `main` produced such parameters. The only parameterization
that existed is `scripts/first_ensemble_run.py::_default_mfs_for_feature`, which
builds Gaussians only, from a hard-coded `FEATURE_SCALES` range in the wrong
units (NFR-8), with random consequents that are degenerate one draw in four
(ADR-024, NC-023).

The design constraint that matters most: **the parameters come from the archive
and the consequents come from a formula, so nothing in the resulting model is a
draw.** That is what makes the ADR-019 comparison measure shape interpolation
rather than a random consequent sample, removes ADR-024's 1/4 identity-channel
trap by construction, and gives the ADR-014 trainer (#60) a warm start that
needs no seed search.

Three defects in the first cut of PR #68 are what this round closes:

1. `placement="endpoint"` / `"interior"` did not reproduce
   `first_ensemble_run.mf_centers` or its shipped Gaussian width, so Issue #31's
   comparison (UC-4) was no longer reproducible.
2. `TanhMF` shipped one common slope, `atanh(0.8) / min(m_L, m_R)`, on both
   sides — neither section 6.3's half-reach default nor decision 2's
   equal-slope fallback, and step 5b's nine `x*_j` were never computed.
3. `ClampingFeatureExtractor`'s counters could not answer the question #62 has
   to ask them: there was no "how many vectors were clamped" counter, and the
   component counter was a scalar rather than a per-feature array.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/fuzzy/parameterization.py` | `_quantile_layout` now returns a typed `QuantileLayout`; the legacy placements reproduce `mf_centers` exactly; `TanhMF` measures ADR-023's onset and takes decision 2's fallback per feature; the clamp counters follow FR-12; shape dispatch is a table and the four layout constants are named. |
| `scripts/feature_distribution.py` | Writes LF-terminated TSV so its output is byte-identical to its own committed artifact; `--limit 0` writes zero rows; `--backend` filters before any `git show`; `rejection_reason` moved last so FR-2's order is a strict prefix; an unparseable timestamp is a rejection rather than an exception. |
| `tests/test_parameterization.py` | *new* — section 9's unit, property and conformance suites, including the checks that run on the committed survey's real quantiles. |
| `tests/test_feature_distribution.py` | Extended from three helper tests to the full FR-2/FR-3/FR-4 contract, a `tmp_path` git-repo integration test, a byte-identity determinism check, and a `slow` test that re-walks the real archive. |
| `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv` | *new* — the survey at a pinned `calibration-data` sha, replacing an unpinned `FETCH_HEAD` run. |
| `docs/evidence/feature-distribution/README.md` | Provenance, the file-count reconciliation, units, the `ddof=1` convention, the summary table, the measured clamp rate, and the provisional runtime. |
| `docs/numerical-claims.md` | NC-041..NC-044 for the four reported conclusions, appended after the NC-035..NC-040 block PR #69 landed. |
| `docs/team.md` | Ownership row for `fuzzy/parameterization.py`. |

`fuzzy/tsk.py`, `channels/kraus.py`, `interfaces.py` and `calibration/features.py`
are untouched (NFR-6). `ClampingFeatureExtractor` *implements*
`CalibrationFeatureExtractor`; implementing an ABC is not editing it.

## Implementation approach

**The layout is one object, computed once.** `_quantile_layout(samples, k,
placement)` returns a frozen `QuantileLayout` carrying `lo`, `hi`, `edges`,
`centers`, `reaches` and `margins`. Both `grid_partition` and
`partition_anchors` consume it, which is FR-6's real invariant: no two callers
can ever see two different layouts for one feature. It replaced a
`dict[str, np.ndarray]` that stored floats under `"lo"` and `"hi"` — a type lie
mypy could not catch, because bare `np.ndarray` resolves to `ndarray[Any, Any]`.

**Shapes dispatch through a table.** `_SHAPE_BUILDERS` maps each M1 class to its
builder; anything else raises `NotImplementedError` naming the second commit
(architect decision C3), so a caller never receives a silently wrong partition.
Adding `TriangularMF`, `TrapezoidalMF` and `TanhBellMF` before M2 is a table
entry plus a builder, not an edit to an `if shape is X` chain.

**The clamp is a wrapper, not a rule in a caller.**
`FuzzyNoiseModel._compute_crisp_params` extracts and evaluates back to back with
no interception point, and `feature_extractor` is a constructor argument of both
`FuzzyNoiseModel` and `FuzzyNoiseModelEnsemble`. Injecting the wrapper is the
only way a caller that builds an ensemble can apply the out-of-range policy at
all (FR-12, architect decision B6).

## Mathematical / statistical details

### The quantile layout

Let `S` be a feature's snapshot values and `Q(p)` the `p`-quantile computed with
`numpy.quantile(S, p, method="linear")` — the method is named because a
different interpolation moves every center. With `k` levels:

```
range        lo = Q(0.01),  hi = Q(0.99)
bin edges    e_j = Q(0.01 + 0.98 * j / k)              j = 0..k
centers      c_j = Q(0.01 + 0.98 * (j - 0.5) / k)      j = 1..k
reach        r_j = max(c_j - e_(j-1),  e_j - c_j)
margin       m_j = r_j / 4
edge slope   s_j = atanh(0.8) / m_j
```

Quantile bins rather than equal thirds of `[min, max]` because the archive's
tails are set by outliers (#45's 2026-08-28 audit found per-qubit T1 from 4.8 to
409 µs): equal thirds would leave the middle bin holding most of the mass, while
quantile bins hold equal probability mass by construction, so each rule sees a
comparable share of the archive.

The **bin-cover rule** is the placement invariant: MF `j` has membership at
least 0.5 at every point of its own bin, so the best MF at any `x` in
`[lo, hi]` is at least 0.5 and there is no dead zone the noise model cannot
respond to. Every width below puts the half-membership point at, or just
beyond, the bin edge.

The constants `1/4` and `0.8` are **defaults, not measurements**, and are now
named (`MARGIN_FRACTION`, `EDGE_TANH_VALUE`). `m_j` is how far past the bin edge
a tanh shape's transition point sits; `atanh(0.8)` makes the tanh argument equal
`atanh(0.8)` one margin from a transition, so the edge value is 0.8 in the tanh
and 0.9 in the membership. Both are shipped unchanged from the ticket.

### Measured layout, 975 rows at `3d1569d`

| Feature | lo | e₁ | e₂ | hi | c₁ | c₂ | c₃ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `mean_T1` | 98.8191 | 126.0411 | 135.5941 | 154.3887 | 118.4859 | 131.7984 | 142.5655 |
| `mean_T2` | 67.4411 | 94.6542 | 99.5810 | 110.5429 | 87.3562 | 97.0365 | 103.4633 |
| `mean_readout_error` | 0.0171326 | 0.0196933 | 0.0219329 | 0.0374223 | 0.0185807 | 0.0205861 | 0.0284604 |

Reaches `r_j`: T1 `[19.6668, 5.7573, 11.8232]`, T2 `[19.9152, 2.5446, 7.0796]`,
readout `[0.0014484, 0.0013469, 0.0089617]`.

### Per-shape mapping (the four M1 shapes)

| Shape | Parameters | Derived from the layout | Why it satisfies its constraint |
| --- | --- | --- | --- |
| `GaussianMF` | `[c, σ]` | `c = c_j`, `σ = r_j / √(2 ln 2)` | `μ(c_j ± r_j) = exp(−ln 2) = 0.5` exactly, so the half-max points sit on the bin's wider edge. `σ > 0` iff `r_j > 0`, which the layout validates. |
| `IntervalGaussianMF` | `[c, σ_lo, σ_hi]` | `c = c_j`, `σ_lo = r_j / √(2 ln 2)`, `σ_hi = √(σ_lo² + s_q²)` | Adding variances is what convolving two Gaussians does: the snapshot mean is one draw from a device whose qubits scatter with std `s_q`, so the upper Gaussian is the lower one blurred by that scatter. Strictly wider iff `s_q > 0`, so `_validate`'s `σ_lo < σ_hi` holds; the lower Gaussian alone satisfies the bin-cover rule, so FR-9 on `.low` holds. |
| `TanhSigmoidMF` | `[center, slope]` | `center₁ = lo − m₁`, `center_j = e_(j−1)` for `j ≥ 2`; **one common** `slope = atanh(0.8) / min_j m_j` | Monotone, so it cannot be a peaked "level"; the convention is **cumulative levels** — MF `j` reads "at least level `j`" and crosses 0.5 at its bin's lower edge. A common slope is required: two rising sigmoids with different slopes cross at `(s₁c₁ − s₂c₂)/(s₁ − s₂)`, which can fall inside the range and break `μ₁ ≥ μ₂ ≥ μ₃`. |
| `TanhMF` | `[L, R, s_L, s_R]` | see below | see below |

`s_q` is the survey's median per-qubit `ddof=1` std — decision 3's
recommendation (the device's own scatter), not `s_q/√n` (the standard error of
the mean), because the footprint represents uncertainty about the device state,
not about the arithmetic mean.

`μ₁(lo)` for `TanhSigmoidMF` is **not** 0.5 and must not be asserted as such:
level 1 has no lower bin edge to sit on, so its center is offset to `lo − m₁` by
construction and `μ₁(lo) = (tanh(slope · m₁) + 1)/2`. Section 9.3 predicts
"about 0.98 for any layout using these constants", which holds only when `m₁` is
`min_j m_j`. On the real quantiles it is not, and the measured values are
**0.99947 / 1.00000 / 0.90074** for T1 / T2 / readout. The suite therefore pins
the constructed expression rather than the ticket's constant.

### `TanhMF` and ADR-023's floored tail — measured, not assumed

Unequal slopes drive `TanhMF`'s raw difference negative on one tail; the
`max(..., 0)` floor projects it back, creating a zero-gradient region. ADR-023's
onset is `x* = (s_L·L − s_R·R)/(s_L − s_R)`. Substituting the half-reach mapping
and cancelling `atanh(0.8)` gives the closed form now shipped as
`tanh_floor_onsets`:

```
x*_j = c_j - 2.5 * u_j * v_j / (v_j - u_j),   u_j = c_j - e_(j-1),  v_j = e_j - c_j
```

**Step 5b, the nine values on the committed survey's real quantiles:**

| Feature | j=1 | j=2 | j=3 | inside `[lo, hi]` |
| --- | ---: | ---: | ---: | --- |
| `mean_T1` | **149.156** | 159.649 | **100.094** | j=1, j=3 |
| `mean_T2` | 116.154 | 3.65826 | **81.9729** | j=3 |
| `mean_readout_error` | **0.0305591** | 0.0139651 | −0.0316035 | j=1 |

Four of the nine onsets land inside their feature's domain box, so **all three
features take decision 2's equal-slope fallback**. Under that fallback the
mapping is `L = c_j − r_j − m_j`, `R = c_j + r_j + m_j`,
`s_L = s_R = atanh(0.8)/m_j`, which is `TanhBellMF`'s section 6.3 mapping
exactly; `TanhBellMF.degree` is `TanhMF.degree` with equal slopes and the floor
inactive, so the two coincide pointwise.

**The consequence, which the results must not hide:** every feature's `TanhMF`
partition is identical to its `TanhBellMF` partition, so the untrained ablation
rows for the two shapes will be the same and only the trainer can separate them.
`TanhBellMF` is a second-commit shape, so this cannot be *shown* until that
commit lands and has to be stated in words until then — it belongs in the
ablation caption, not a footnote. `tanh_slope_strategy` returns the branch, and
`tests/test_parameterization.py::test_tanh_branch_taken_on_the_real_quantiles_is_pinned`
pins it; the suite deliberately does **not** assert that `x*` lies outside the
range, because on a right-skewed feature that assertion is false by
construction.

### Legacy placements

FR-5 keeps Issue #31's two layouts as options, taking `samples` as the literal
`(lo, hi)` 2-vector. Generalised to `k`, and equal to `mf_centers` at `k = 3`:

```
endpoint   c_j = lo + span * (j - 1)/(k - 1)      k=3 -> lo, lo + span/2, hi
interior   c_j = lo + span * (2j - 1)/(2k)        k=3 -> lo + span/6, lo + span/2, lo + 5·span/6
```

Bin edges are the midpoints between centers, extended by half a spacing at each
end, so `r_j = spacing/2` uniformly — the ticket's "widths with `r_j` derived
from the equal spacing". `GaussianMF` is the stated exception: FR-5 pins the
shipped `σ = 0.25·(hi − lo)` so the two layouts can be compared by equality
against the smoke script. That width is wider than the bin-cover minimum
`r_j/√(2 ln 2)` (0.2123·span for endpoint, 0.1416·span for interior), so
coverage still holds and the suite asserts it.

Note that for `endpoint` the outer centers sit *on* the range ends, so the bin
edges extend half a spacing beyond `[lo, hi]`; `QuantileLayout.source_range`
carries the caller's literal `(lo, hi)` so the Gaussian width is computed from
the range the script uses rather than from the widened edges.

### Why the anchored model cannot be degenerate

`WeightedAverageDefuzzifier` computes `y(x) = Σ_r w̄_r(x)·b_r` with `w̄_r` non-negative
and summing to one, and `NieTanDefuzzifier` is the same form with effective
weights `0.5(f_low/Σf_low + f_high/Σf_high)`. With zero-order consequents `y(x)`
is therefore a **convex combination of the anchor targets**:
`min_r b_r ≤ y(x) ≤ max_r b_r` componentwise, wherever some rule fires. If every
anchor target is a valid `(γ, λ)` in `(0, 1)` then so is `y(x)`, `ProbabilityClip`
never binds, and `is_identity_damping` is `False`. The only remaining failure
mode is "no rule fires" — a `ZeroDivisionError` in the defuzzifier — which the
bin-cover rule excludes inside `[lo, hi]`, **and only inside it**, which is why
the clamp exists.

This is **not** a claim that ADR-024 clause 5 is satisfied. Clause 5 names
exactly two mechanisms for a warm start — call `first_viable_seed` at
initialization, or adopt a squashing strategy with everywhere-nonzero gradient —
and an anchored consequent is neither. The accurate statement (architect
decision A5) is that the clause's **intent**, never warm-start from an unchecked
zero-mean draw, is met **by construction**, while its **letter** is not, because
anchoring is a third mechanism the clause does not enumerate. Recording that
third mechanism in the ledger is the ADR-014 flip PR's job (#60 step 11); this
PR writes no ledger text and claims no compliance.

### The unit sanity check — the only one that can see a unit error

PR #69 merged `training/targets.py` while this round was in progress, so
section 6.6's contingency lapsed and FR-7 is wired to the real
`training.targets.feature_target_fn(features, *, t_seconds)` rather than to a
synthetic stand-in. That makes section 6.4 (c)'s magnitude check runnable, and
it is the **only** check in the suite that can catch a unit error:

At the archive's median anchor `[131.7984, 97.0365, 0.0205861]` with
`t_seconds = 24 ns` (NC-035, `ibm_fez`'s `sx` length):

```
gamma  = 1.820797e-04
lambda = 3.125143e-04
```

Order 1e-4, which is what the physics gives. Feeding the same microsecond value
to `1 - exp(-t/T1)` as if it were seconds gives about 1e-10 — a value that is
finite, strictly positive and inside `(0, 1)`, so `is_identity_damping` stays
`False`, FR-11 passes, section 6.5's convexity bound holds, and every other
check in this file goes green on a model wrong by six orders of magnitude.
Nothing but the magnitude catches it.

All 27 anchor combinations are accepted by `feature_target_fn`'s own guards and
land strictly inside `(0, 1)`: gamma in `[1.6833e-04, 2.0254e-04]`, lambda in
`[2.6134e-04, 3.8106e-04]`. That is not automatic — the callable rejects
`mean_T2 > 2·mean_T1`, and the grid pairs each feature's levels independently,
so the lowest T1 anchor meets the highest T2 anchor.

### Step 9 acceptance run

Every one of the 975 surveyed feature vectors, through
`ClampingFeatureExtractor(BasicCalibrationVectorizer(), lo, hi)`, for every M1
shape (`NieTanDefuzzifier` for the IT2 base, `WeightedAverageDefuzzifier`
otherwise), against the **real** target callable:

| Shape | rules | rows | `ZeroDivisionError` | `is_identity_damping` | gamma range | lambda range |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `GaussianMF` | 27 | 975 | 0 | 0 | `[1.7400e-04, 2.0253e-04]` | `[3.1314e-04, 3.5507e-04]` |
| `TanhMF` | 27 | 975 | 0 | 0 | `[1.6857e-04, 2.0254e-04]` | `[3.0323e-04, 3.6144e-04]` |
| `TanhSigmoidMF` | 27 | 975 | 0 | 0 | `[1.8431e-04, 2.0254e-04]` | `[3.1139e-04, 3.5662e-04]` |
| `IntervalGaussianMF` | 27 | 975 | 0 | 0 | `[1.7847e-04, 1.9443e-04]` | `[3.1548e-04, 3.3682e-04]` |

Every range sits inside the anchor-target hull above, which is section 6.5's
convexity bound holding on real data rather than in argument.

**Measured clamp rate: 44 of 975 vectors, 4.51%** — 16 on `mean_T1`, 11 on
`mean_T2`, 20 on `mean_readout_error`. Measured, not derived: a per-feature 2%
tail bounds the vector rate between 2% (perfectly correlated features) and about
6% (independent), and neither bound is the answer. #62 must inject this
extractor and record its own rate per run.

Parameter accounting on the Gaussian grid: 27 rules, **9 unique MF objects**
(81 antecedent references), 18 premise parameters, 216 consequent entries — 234
total, matching section 6.3 and independently confirming NC-037, which #57
registered from `training/parameters.py::count_trainable_parameters`. Copies instead of shared objects would have
inflated the premise count from 18 to 162 (NFR-7).

## Design decisions

**Reject parameters, clamp inputs.** ADR-018's convention is that an invalid
parameter is a construction-time error, so `grid_partition` raises on a
degenerate layout rather than nudging a value into range. A feature vector
outside the domain box is a different thing: a legitimate archived measurement
that simply sits outside the model's stated domain. The options there are to
clamp, to widen, or to crash. Widening the feet until nothing falls off the end
would silently change the partition the ablation is comparing and make the
widths a function of the archive's outliers, which is exactly the failure
quantile bins were chosen to avoid; crashing mid-ablation is not an option
(UC-7). The asymmetry is deliberate and is stated in the module docstring so it
does not read as an inconsistency.

**Decision 2's fallback applied per feature, not globally.** The alternative was
to keep half-reach slopes everywhere and accept the floored tails. That was
rejected because a zero-gradient region inside the surveyed range is a bad warm
start for the trainer, and because the ticket's own recommendation is the
fallback. The cost — `TanhMF` coinciding with `TanhBellMF` — is real and is
recorded rather than hidden.

**`_quantile_layout` returns a dataclass, not a dict.** A `dict[str, ndarray]`
holding floats typechecks under `mypy --strict` only because bare `np.ndarray`
is `ndarray[Any, Any]`; the Any then propagates into `partition_anchors`'
declared `NDArray[np.float64]` return. A frozen dataclass makes the shapes and
the float/array split explicit.

**Counters are per-feature.** A scalar clamp count cannot tell #62 which feature
left the box, and a count of extractions is not a count of clamped vectors. The
FR-12 names and semantics are restored, and the two caveats a caller must handle
(an ensemble records one extraction per member from one snapshot; the counters
are cumulative, so a per-shape rate needs a fresh wrapper) are in the class
docstring.

**FR-13 was not built, and step 10 is skipped.** `training/targets.py` merged
with PR #69 on 2026-09-08, so section 6.6's contingency never triggered:
`anchored_rule_base` consumes the real callable and `viable_seed_rule_base` is
not needed. No seed appears anywhere in the untrained baseline, so ADR-024's 1/4
rate does not apply to anything this PR produces and no caption has to carry it.

**Still open — not decided here.** Section 7 decisions 1–3 have not been
answered in the issue thread. The code implements the ticket's own
recommendations (cumulative levels with a common slope for `TanhSigmoidMF`;
half-reach slopes with the per-feature equal-slope fallback for `TanhMF`; `s_q`
rather than `s_q/√n` for the IT2 footprint), which is what @yigit-arda proposed
on 2026-09-04, but @BurakOztekin and @bengisucvd have not signed off. That
sign-off is a gate on this PR, not a follow-up.

## Verification

```bash
pytest tests/test_parameterization.py tests/test_feature_distribution.py -v
```

```bash
ruff check . && ruff format --check . && mypy --strict
```

Re-walk the archive and confirm the committed TSV reproduces (needs the
`calibration-data` ref; skipped otherwise):

```bash
git fetch superconducted-noise-engine calibration-data && pytest tests/ -m slow -v
```

```bash
python scripts/check_ids.py
```

Regenerate the survey from scratch and diff it against the committed artifact —
byte-identical, including line endings:

```bash
python -m scripts.feature_distribution --repo . --ref 3d1569d18bcc007c35f3f628f79e678e6061bdc3 --out /tmp/resurvey.tsv && diff /tmp/resurvey.tsv docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv
```

Measured on Mert's laptop 2026-09-08 (**provisional** under NFR-3 until Burak's
next batch record, architect decision C2):

- Full suite collects **469** tests, up from **360** on `main` at `2d66f7a` —
  a delta of **+109** against NC-021's current value of 360, which reproduces
  exactly at that commit.
- 13 pre-existing failures in `tests/test_probe_historical_properties.py`
  reproduce identically on `main` and are an environment gap
  (`qiskit-ibm-runtime` absent), not a regression.
- The full survey walk: 55-64 s for 975 files over three uncontended runs
  (55.08, 61.34, 63.70). A fourth run overlapping a full `pytest` took
  93.39 s, which is why NC-044 registers a range rather than a point.

## Related docs

- Issue #59 (this ticket), Issue #31 (the `endpoint`/`interior` layouts kept as
  options), Issue #45 (the archive integrity audit the quantile choice cites)
- ADR-006 (shape enumeration), ADR-009 (T1 vs IT2 — the footprint scale of
  decision 3), ADR-010 (the 3×3×3 grid and `from_grid`'s rule order), ADR-014
  (Deferred; the trainer this warm-starts), ADR-018 (slope positivity;
  reject-don't-clip for parameters), ADR-019 (the ablation this unblocks),
  ADR-023 (`TanhMF`'s floor and the `x*` formula), ADR-024 (clause 5, and why
  anchoring is a third mechanism) — all in `docs/decisions.md`
- NC-012, NC-021, NC-023, NC-025 and the new NC-041..NC-044 in
  `docs/numerical-claims.md`
- `docs/evidence/feature-distribution/README.md` — the survey and its provenance
- `docs/roadmap/2026-09-03-phase-3-plan.md` — the M1 gate this lands against
