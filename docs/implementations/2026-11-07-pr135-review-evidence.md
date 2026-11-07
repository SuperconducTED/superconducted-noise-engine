# 2026-11-07: pr135-review-evidence

## Problem / Motivation

PR #135 pre-registers the decision rule of the #125 hardware test and asks for a statistics review before the rule
freezes. Section 3.8 of the pre-registration reads each threshold against no-information nulls. That shows what a
threshold is worth, but not what the rule separates. Design section 1 says only the hardware can tell whether a reading's
scatter is measurement noise or fast physical fluctuation, so the review needed the rule's pass rates in those scenarios.
The review's numbers need a script behind them, and they are too large to paste into a post (about 94,000 characters
against GitHub's 65,536), so they live here and the review cites this commit.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pr135-statistics-review/README.md` | What was measured, at which commits, the scenarios, set-up and run order. |
| `docs/evidence/pr135-statistics-review/cache_build.py` | Reads `ibm_fez` at a pinned `calibration-data` ref, without lazy fetch, into the pinned code's `Collected`. |
| `docs/evidence/pr135-statistics-review/arch_days.py` | Runs the pinned selection and predictors at 03:45 UTC on each of 137 days and records each qubit's next changed reading. |
| `docs/evidence/pr135-statistics-review/config_scan.py` | Counts archived files whose `configuration` is null and the job days that would meet one. |
| `docs/evidence/pr135-statistics-review/arm_a_worlds.py` | Scores Arm A in each scenario: A1 under each interval, A3, A4 with and without `tau = 0`, S1, power against position. |
| `docs/evidence/pr135-statistics-review/a1_a3_joint.py` | S1 with and without A4 as a gate. |
| `docs/evidence/pr135-statistics-review/arm_a_fit.py` | Fits `log T1` per qubit-day from Arm A's rows and reports `c` and `s_res` per scenario. |
| `docs/evidence/pr135-statistics-review/a1_empirical.py` | A1's false-pass rate on the real day series with its mean removed, and the dependence's mechanism. |
| `docs/evidence/pr135-statistics-review/a1_size.py` | A1's size under AR(1): closed form, block lengths, interval levels, batch means, non-Gaussian days. |
| `docs/evidence/pr135-statistics-review/armb_exact.py` | Arm B's null (i) in exact integer arithmetic, an independent route to the committed figures. |
| `docs/evidence/pr135-statistics-review/arm_b_days.py` | Runs PR #140's `build_job` on archive days, with shot-free truth distributions per scenario. |
| `docs/evidence/pr135-statistics-review/arm_b_analysis.py` | Arm B's conditions on real rankings, with a random truth and in each scenario. |
| `docs/evidence/pr135-statistics-review/harness_checks.py` | Checks the cache against committed rows, that no future file reaches a day, and the live path. |
| `docs/evidence/pr135-statistics-review/q5_old_vs_new.py` | Amendment 14's claim: old and new `predictor_rows` on the same records. |
| `docs/evidence/pr135-statistics-review/astcmp2.py` | Amendment 14's definition counts, by AST comparison. |
| `docs/evidence/pr135-statistics-review/*.out.txt` | Each script's output at the commits named in the README. |
| `docs/implementations/2026-11-07-pr135-review-evidence.md` | This record. |

No source, test, register or workflow file changes.

## Implementation approach

The pre-registered code decides everything it can: `predictor_rows` and `select_balanced` at `5c98f264` choose the qubits
on real archive days, and `build_job` at PR #140's `2aea1e18` chooses the layouts. On those real rows, a scenario supplies
`T1` at execution, binomial shot noise is added, and rows are scored as `score_arm_a` scores them. Each condition is then
evaluated on overlapping windows, so the rule's pass rate can be read per scenario.

Every result has a second route where one exists: a closed form, exact arithmetic, a register row, or a mutation that must
fire. One mutation first reported 0 because the mutated record shared its array with the baseline; it now copies, and exactly
one cell differs.

## Mathematical / Statistical details

**Notation.** `r = log T1_reading`, `l = log T1_level`, `d = r - l`, `x*` the unknown `log T1` at execution.
`p(tau; x) = (1 - e10) s + e01 (1 - s)`, `s = exp(-tau e^{-x})`. Row score
`D = |p_hat - p(tau; l)| - |p_hat - p(tau; r)|`, so `D < 0` means the level is closer. `p_hat ~ Binomial(2048, p(tau; x*)) / 2048`.

**The estimand under A1.** Write `x* = l + c d + eta`. NC-087 puts the pooled tie near `c = 0.49` on the union grid, so A1
asks whether `c` is credibly below about one half: whether most of a selected reading's deviation is gone by execution.

**A percentile bootstrap's size at `n` days.** The bootstrap mean has variance about `s^2 (n - 1) / n^2`, so the upper 95% point
is below zero when `t < -z_0.95 sqrt((n - 1) / n)`. For `n = 14`: `P(t_13 > 1.585) = 0.0685`, against the PR's Monte Carlo 0.0675.

**Batch means.** Split the days into `q` consecutive batches and run a one-sided Student `t` on the `q` batch means, df `q - 1`
(Ibragimov and Müller 2010, doi:10.1198/jbes.2009.08046; abstract read, full text not). Its size is exact at independence.

**The band at `tau = 0`.** `sources_from_rows` gives both band ends the level's readout, so at `tau = 0` the band is a point.
With a one-standard-error widening, `p_hat` lands in it at most `P(|Z| <= 1) = 0.683` of the time.

**Interval score.** `(hi - lo) + (2 / alpha) (lo - x)_+ + (2 / alpha) (x - hi)_+`, with `alpha = 0.2` (Gneiting and Raftery 2007).

**Direct fit.** Per qubit-day, `log T1` by binomial maximum likelihood from the six `tau > 0` rows with the level's readout.
`c` is the slope of `x_fit - l` on `d`. `s_res` is the residual's robust spread: the 10th-to-90th percentile range over `2 z_0.9`.

**Results, laptop, provisional.**

| Scenario | A1 (block 3, 90%) | A3 | A4, all rows | A4, `tau > 0` | S1 as written | `s_res`, 14-day median |
| --- | --- | --- | --- | --- | --- | --- |
| N | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.013 |
| F | 1.000 | 1.000 | 0.005 | 0.475 | 0.005 | 0.324 |
| S | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.025 |
| `M(0.5, 0.289)` | 0.068 | 0.529 | 0.000 | 0.000 | 0.000 | |

The other figures are in the `*.out.txt` files, named per use in the README.

## Design decisions

- **Scenarios as well as nulls.** A null says what a threshold is worth; only the scenarios show that A1 to A3 pass in both N
  and F, so that A4 alone separates them.
- **F is named as a proxy everywhere.** The archive's next reading carries calibration noise and is not the device.
- **A branch cited by commit, with no PR.** The numbers belong to a review of someone else's PR. A pinned commit keeps every
  figure re-runnable without asking anyone to merge one-off scripts, and CI does not run on a branch push.
- **Not pasted in full.** The two scripts that need no archive are pasted in the review; the rest would have needed a
  55,000-character comment that adds nothing over this folder.
- **Hard-coded paths and remaining lint items left in.** These are pinned one-off scripts; the README says so. If they are ever
  merged, they need a lint pass and a configurable root.

## Verification

Each script was re-run from this folder and compared with its earlier output. Run order: the README.

- `python armb_exact.py <null-values.json at 51e9f425>`: largest difference 3.3e-16 from the committed figures.
- `python a1_size.py`: closed form 0.0685 against the committed 0.0675.
- `python harness_checks.py <clone> <M>`: 780 rows match the committed `predictors.tsv` exactly; future-file mutations change 448
  and 308 rows.
- `python q5_old_vs_new.py`: 0 differing cells across 780 rows and 10 columns at two instants; one doubled reading changes exactly 1 cell.
- `python arm_b_analysis.py`: on independent rankings, 0.508, 0.611, 0.376 against the committed 0.505, 0.606, 0.375.
- `null_values.py` at `51e9f425`, unchanged: byte-identical to the committed `null-values.json`.

No `pytest` run: nothing here is imported by the package or tests.

## Related docs

- PR #135 and `docs/roadmap/2026-10-24-issue-125-preregistration.md` on its branch
- PR #140, `scripts/hardware_reading_vs_level.py`
- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md`
- `docs/numerical-claims.md`: NC-081, NC-084, NC-085, NC-087, NC-091
- Issue #125
