# ADR-011 type reduction: BMM(1/2, 1/2) and Nie-Tan against the Karnik-Mendel midpoint

`2026-10-21-d0f144a.tsv` is the measurement Issue #61 Part A owes ADR-011 (FR-3, FR-4).
On 3x3x3 interval type-2 Gaussian grids over the archive's feature distribution, it
measures how far two closed-form IT2 reducers sit from the midpoint of the Karnik-Mendel
type-reduced interval `[y_l, y_r]`:

- `bmm_half`: `(Y(lower) + Y(upper)) / 2`, the Biglarbegian-Melek-Mendel reducer with
  `alpha = beta = 1/2`, which is what `NieTanDefuzzifier` computes today;
- `nie_tan`: `Y(lower + upper)`, textbook Nie-Tan.

The file is evidence, not a decision. Its figures are not registered yet (see "What this
file does not establish").

## Provenance

| | |
| --- | --- |
| **Code commit** | `d0f144ad265f73b7963726ba74e6337250c98f3c`, the commit that produced the file and that its `# commit:` line names. The TSV itself is committed on top of it, in a commit that changes no behaviour; the one code edit there corrects a docstring. |
| **Survey** | `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv`, 975 snapshot rows from `calibration-data` @ `3d1569d18bcc007c35f3f628f79e678e6061bdc3` (NC-041, NC-043) |
| **Measured** | 2026-10-21 |
| **Machine** | Mert's laptop: Windows 11, Python 3.12.10, numpy 2.4.4. These figures are **provisional**; the canonical run is the next batch verification on Burak's desktop. |
| **Runtime** | 21.5 s and 33.7 s wall time for two runs of the command below (#61 NFR-4: measured, not asserted; the spread is the laptop's load, not the input) |
| **SHA-256** | `6782340a1716553f7798f4237cd2f4d96b4554e1e4968482e592061d43300cb7` |
| **Rows** | 12 `# ` provenance lines, one column row, 96 data rows |

## Command

From the repository root at the code commit (`PYTHONPATH=src` if the package is not
installed):

```bash
python -m scripts.type_reduction_discrepancy \
    --range-source survey:docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv \
    --footprint 0.1 --footprint 0.3 --footprint 0.6 --footprint g59 \
    --points 2000 --seed 84 \
    --out docs/evidence/adr-011-type-reduction/2026-10-21-d0f144a.tsv
```

**Reproducibility.**

- The two runs gave byte-identical files with the SHA-256 above (#61 NFR-1).
- `tests/test_type_reduction.py::test_sweep_is_byte_identical_across_runs` pins the same
  property on a smaller run.
- Across machines the last bits of a dot product can depend on the BLAS build, so a rerun
  elsewhere is expected to agree to rounding, not necessarily byte for byte.
- `.gitattributes` keeps the file LF on checkout.

## Units

These are the archive's own units: the survey's, `ArchiveUnitFeatureExtractor`'s, and the
units `feature_target_fn(..., coherence_unit="us")` expects. They are not
`BasicCalibrationVectorizer`'s, which has emitted SI seconds since Issue #66.

| Feature | Unit |
| --- | --- |
| `mean_T1`, `mean_T2` | microseconds |
| `mean_readout_error` | dimensionless |

Consequents:

- `unit-spread` consequents are dimensionless.
- `anchored` consequents are damping probabilities per 24 ns `sx` gate (NC-035).

All three distances (`D`, `Dc`, `Db`) are in consequent units or dimensionless, so none of
them carries a time unit.

## What was measured

**Domain box.** Per feature, `[p1, p99]` of the survey (NC-041): `mean_T1`
[98.8191, 154.3887] us, `mean_T2` [67.4411, 110.5429] us, `mean_readout_error`
[0.0171326, 0.0374223]. The exact values are in the `# box:` line.

**Grids**, each three levels per feature with centers at the survey's quantile anchors.
#61 decision 2 proposes this set, and @BahaJarad has not yet agreed to it:

| `grid` | Construction |
| --- | --- |
| `w=0.1`, `w=0.3`, `w=0.6` | `IntervalGaussianMF(c, s (1 - w), s (1 + w))` on the centers `c` and widths `s` of `grid_partition(GaussianMF, survey, k=3, placement="quantile")`. This is #61 section 6.2's symmetric footprint. |
| `G59-assumed` | `grid_partition(IntervalGaussianMF, survey, k=3, placement="quantile", qubit_spread=s_i)`: the lower MF is the type-1 Gaussian, and the upper has `s_high = sqrt(s_low^2 + s_i^2)` |

> **NOTE · `s_i` is assumed.** `s_i` is the median over the survey rows of
> `<feature>_qubit_std`, which is NC-042's statistic: 45.77560415588844 us (`mean_T1`),
> 54.90837978993332 us (`mean_T2`), 0.04069462675923896 (`mean_readout_error`). #84 File 02
> (comment 5885404218) calls this grid "#59's shipped footprint" without stating its
> `qubit_spread`, and no production caller passes one. Until @mertefesensoy confirms what
> File 02 used, the grid stays labelled `G59-assumed` and the file's
> `# g59_qubit_spread:` line says ASSUMED. That label was requested by the #61 owner,
> @bengisucvd.

**Consequent conventions** (#61 FR-4; decision 1 proposes `unit-spread` as the headline,
and @mertefesensoy has not yet confirmed it):

| `convention` | `output` | Rule base |
| --- | --- | --- |
| `unit-spread` | `unit` | Zero-order; rule `r` (in `itertools.product` order) has bias `r / 26`. Scale-free, so the raw and normalized figures coincide. |
| `anchored` | `gamma`, `lambda` | `anchored_rule_base` with `feature_target_fn(t_seconds=2.4e-08, coherence_unit="us")` at the quantile anchors. `gamma` depends only on the `mean_T1` anchor, so its 27 consequents take 3 values. |

**Point sets.**

| `point_set` | Points |
| --- | --- |
| `lattice` | 27: the anchor triples, one per rule |
| `uniform` | 2000, drawn in the domain box by `numpy.random.default_rng(84).uniform(lo, hi, size=(2000, 3))` |
| `survey` | 975: the survey rows themselves. 44 of them lie outside the box in at least one feature (16, 11 and 20 per feature), as a `[p1, p99]` box implies. |
| `pooled` | the three sets together (3002); this is pooling **within one cell**, not across grids or conventions |

**Per row**, which is one (grid, convention, output, point set, reducer) cell:

| Column | Meaning |
| --- | --- |
| `n_points`, `n_skipped` | Points evaluated. A point is skipped if a firing-bound sum is zero (`ZeroDivisionError`). |
| `n_degenerate_band` | Points where `y_r - y_l <= 64 R eps max|c|`; `Db` is set to 0 there |
| `n_bracket_violations` | Points where the reducer lies outside `[y_l, y_r]` by more than that tolerance. Both reducers are proven to lie inside, so a non-zero count is a defect. |
| `D_*` | `D = |y - (y_l + y_r)/2|`, in consequent units |
| `Dc_*` | `D / (max_r c_r - min_r c_r)`, #61 FR-3's scale-free form |
| `Db_*` | `min(D / (y_r - y_l), 1/2)`, #84 File 02's pre-registered score |
| `*_max`, `*_mean`, `*_median`, `*_p90` | Over the cell's points; median and p90 use numpy's linear interpolation |
| `km_passes_max`, `km_passes_mean` | Iterative Karnik-Mendel switch-vertex evaluations per endpoint |
| `km_guard_stops` | Endpoints whose iteration was stopped by the monotone guard |
| `km_route_gap_max` | Largest `|iterative - exhaustive|` over both endpoints |

The `_max`, `_mean`, `_median` and `_p90` columns of `D`, `Dc` and `Db` depend on the
reducer. The `km_*` columns do not, so they repeat on both reducer rows.

**Invariants in this file.** Every row has `n_skipped`, `n_degenerate_band` and
`n_bracket_violations` equal to 0. Every `km_route_gap_max` is at most 8.743e-15, and that
largest value is in a `unit-spread` cell, where the tolerance is about 3.8e-13.

## What this file does not establish

- **Bounds.** A `*_max` is a maximum over the sampled points, not a supremum over the box.
  An ADR-011 closure sentence reads "at most X over the N sampled points".
- **The cycle count.** `km_guard_stops` counts rounding-level events. How many there are
  depends on the arithmetic (summation order, the tie rule for the switch point), so it is
  not a property of the problem. Neither it nor any count of cycling points is to be
  registered as one.
- **Registered figures.**
  - Nothing here is an NC row yet. The rows are allocated at merge time, one per reported
    conclusion (#61 architect decision B8).
  - They follow agreement on decision 1 (consequent convention, @mertefesensoy) and
    decision 2 (footprint set, @BahaJarad).
  - The ADR-011 closure text is prepared in the Part A findings doc and lands after
    ADR-009, never in this PR.
- **The other range source.** #61 FR-3's `fixture-box` was not used. The script does not
  implement it, a deviation from FR-3 that has been put to the #61 owner.
- **Canonical status.** These are laptop figures. The canonical numbers are the batch
  verification on Burak's desktop.
