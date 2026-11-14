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

> **NOTE · 2026-11-07.** The text above describes the 2026-10-21 file and stays as written. Where it
> disagrees with the last section of this README, the last section is current.

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

## 2026-11-07: the sweep re-run, and the scripts behind the findings

`2026-11-07-10e8174.tsv` is the current file. Its 96 data rows are identical to
`2026-10-21-d0f144a.tsv` apart from the grid's name. The findings are in
`docs/findings/2026-11-07-nie-tan-vs-karnik-mendel.md`.

| | |
| --- | --- |
| **Code commit** | `10e8174bc26f921a7dfc79f49a0dfd32b70de8ce`, on `main` @ `43a2c9b0` |
| **Survey** | as above, `calibration-data` @ `3d1569d` |
| **Machine** | Mert's laptop: Windows 11, Python 3.12.10, numpy 2.4.4. **Provisional**; the canonical run is the batch on Burak's desktop. |
| **Runtime** | 15.2 s and 14.8 s for two runs |
| **SHA-256** | `c61102e80ee82bb83b163748b47cabe03a2770624fac0db3cbf5861c25210b11`; the two runs were byte-identical |

What changed since 2026-10-21:

- **`s_i` is confirmed.** @mertefesensoy confirmed on #61 (comment 6665986289) that File 02's
  `qubit_spread` is NC-042's medians (`tests/test_parameterization.py::_committed_survey` at `110cfad`). The
  grid is now `G59`, and the `# g59_qubit_spread:` line says where `s_i` comes from.
- **Decision 1 is confirmed** in the same comment: `unit-spread` is the headline, `anchored` the units-bearing
  companion. Reporting is approved: File 02's pooled `Db` decides, and survey rows are shown first, a choice made after
  the result was seen.
- **Decision 2 is still pending.** @BahaJarad has not answered on the footprint set. Register rows wait for it.
- **`fixture-box` stays retired**, the #61 owner's recorded decision (comment 6319118939, stale-text item 8).

Scripts, each run from the repository root with `PYTHONPATH=src`, output beside it as `<name>.out.txt`:

| Script | What it answers |
| --- | --- |
| `file02_rule_by_point_set.py` | File 02's rule on each point set, and the closer-row tally. By @mertefesensoy, from #61 comment 6665986289. |
| `second_route_reducers.py` | The `G59` anchored lambda figures from code sharing nothing with the sweep's KM or reducers, certified against vertex enumeration. From the same 2026-11-05 work. |
| `survey_reversal_check.py` | All 12 cells on survey rows and on distinct rows, with a 90% block interval. Seeded (`SeedSequence(611107)`). |
| `reducer_positions_and_cost.py` | The identity for `y_NT - y_BMM`, the rejected straddling hypothesis, and the cost per point. Its times move with laptop load; only the ratio is quoted. |
| `km_cycle_sensitivity.py` | How File 02's cycle count moves with the switch-point tie rule and the summation order, and that the guarded result matches the exhaustive route on every cycling point. |
| `compare_sweep.py` | Compares another machine's sweep with the committed TSV to rounding, for the desktop batch. |

## 2026-11-11: after the PR #143 reviews

`2026-11-11-35da0446.tsv` is the current file. The sections above describe the earlier files and stay as written; where they
disagree with this one, this one is current. The findings' section 15 has the corrections in full, and
`docs/implementations/2026-11-11-issue-61-pr143-review-fixes.md` the record.

| | |
| --- | --- |
| **Code commit** | `35da0446020c26775a059a901bf0ce42d8c24f67` |
| **Survey** | as above, `calibration-data` @ `3d1569d` |
| **Machine** | Mert's laptop: Windows 11, Python 3.12.10, numpy 2.4.4. **Provisional**; the canonical run is the batch on Burak's desktop. |
| **Runtime** | 62.5 s and 60.7 s for two runs. The rescale costs a maximum and a division per average: on the same laptop the same night, one footprint took 10.7, 9.2 and 3.6 s before the fix (`w` = 0.8, 0.9, 0.99) and 21.2, 12.0 and 4.2 s after. |
| **SHA-256** | `af97c29f24c2b660cebed91bd1d5638a96f970b71d63de529d249a7eead79d0c`; the two runs were byte-identical |

What changed, and what did not:

- **The band is the exhaustive route's.** `y_l` and `y_r` come from evaluating every switch vertex, not from the iteration,
  which can stop at a float fixed point (the reviews' counterexample, findings 15.1). On the committed grids the two routes
  agree to rounding, so every compared column matches `2026-11-07-10e8174.tsv`: `compare_sweep.py` exits 0, largest relative
  difference 2.809e-11.
- **`Y` is computed on `w / max w`**, so lower weights near the subnormal floor no longer round the average to zero
  (findings 15.2). Every reducer's last bits move with it, which is why the file is new.
- **A new last column**, `km_route_gap_over_tolerance_max`: the largest `|iterative - exhaustive|` over the cell's points, each
  divided by its own tolerance `64 R eps max|c|`. At most 1 in every row of this file (largest 0.023). `compare_sweep.py`
  now fails a run where it exceeds 1.
- **The `km_*` columns are diagnostics of the iterative route.** They are not compared between machines and are never cited.
  @BurakOztekin's desktop run at `c8a1dd54` gave `km_guard_stops` 17 where the committed file has 15 (`w = 0.3`, `unit-spread`),
  and `km_passes_mean` also differed; that is the platform difference these columns carry.

Invariants in this file: every row has `n_skipped`, `n_degenerate_band` and `n_bracket_violations` equal to 0, and
`Db_max < 0.5`.

The evidence scripts take their bands from the exhaustive route too, `reducer_positions_and_cost.py` prints the cost three
ways (findings 15.3), and `file02_rule_by_point_set.py` prints the anchored-only pools (findings 15.4). New:

| Script | What it answers |
| --- | --- |
| `mutate.py` | Applies each of eleven mutants to the script in turn, runs `tests/test_type_reduction.py`, restores from a copy. All eleven are killed at this commit (`mutate.out.txt`). |
| `reducer_positions_and_cost.run2.out.txt` | A second run of the cost script at the same commit. Its timings differ from the first by up to a half, so the findings quote the ratios as ranges over the two. |

## 2026-11-13: after the second review of PR #143

`2026-11-11-35da0446.tsv` stays the current file: the sweep script is unchanged, so the README's command gives the same data
rows. What changed is the checking around it (findings section 16, record
`docs/implementations/2026-11-13-issue-61-pr143-second-review-gaps.md`):

- **`compare_sweep.py` fails on a new file without `km_route_gap_over_tolerance_max`**, or with it empty in any row, instead of
  skipping the check. A sweep made by code that predates the column (`c8a1dd54` and earlier) no longer passes. The committed
  file may still predate the column.
- **`tests/test_type_reduction.py` has 261 tests**, two more: the column is the cell's largest gap, and the comparison fails
  without it.
- **`mutate.py` runs thirteen mutants** and may target `compare_sweep.py` as well as the script; each killed mutant's line names
  the first failing test. All thirteen are killed (`mutate.out.txt`). Its docstring said a non-matching replacement "aborts
  the run"; the code reports it as NOT APPLIED and goes on, and the docstring now says so.

| Script or output | What it answers |
| --- | --- |
| `reducer_positions_and_cost.run3.out.txt` | A third run of the cost script, unchanged since `1b8f6089`, on the same laptop. Ratios 3.1 (public), below the two earlier runs and widening their range, and 11.5 (arithmetic), inside theirs; the findings quote the range over the three committed runs, 3.1 to 4.9 and 9.6 to 13.9. |
