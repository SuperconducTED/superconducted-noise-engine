# 2026-10-26: pattern-detector N3, permutation importance and the register rows (amendment 7)

## Problem / Motivation

The lead asked for task N3 of the pattern detector (#110, comment 6412965244) on 2026-10-26:
"permutation importance on the logistic model, scored on Brier and on AUC separately, archive only,
nothing deep". N1 had shown that clause 1 holds but that the skill is calibration (the model
anticipated the test period's lower shift rate) rather than discrimination (it orders the rows no
better than the null); N3 asks which features carry which part, and registers the conclusions of
N0 to N3 in the numerical-claims register in Rule 7 form.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pattern-detector/README.md` | Amendment 7 (the permutation protocol's details, with a same-day note on the guard tolerance) appended to section 7; section 11 added with the N3 record and its reading. |
| `docs/evidence/pattern-detector/n3_importance.py` | New: refits the record logistic model from `features.tsv.gz` and checks it against the recorded forecasts, permutes 13 feature groups jointly on the test rows, ranks Brier and AUC importance separately with paired day-block bootstrap intervals, builds the 27 scenario cells; synthetic self-test. |
| `docs/evidence/pattern-detector/importance.tsv`, `cells.tsv`, `n3_summary.json` | New: the record run's outputs. |
| `docs/numerical-claims.md` | NC-092 to NC-094 added after NC-076 (dated anchors at `calibration-data` `cf960389`). |
| `docs/implementations/2026-10-26-pattern-detector-n3-importance.md` | This record. |

## Implementation approach

Amendment 7 fixed, before the run: the model (the record logistic at `lambda = 10`, refitted and
checked), the groups (a feature with its indicator), 20 joint permutations per group on the test
rows only, Brier importance as permuted minus record Brier, AUC importance as record minus permuted
AUC, 90% intervals from 1,000 paired resamples of the 46 test days with the permutations fixed
inside each resample, scenario cells over the top three Brier groups at training-row terciles with
cells under 20 rows in a split flagged, and the reading rule (high Brier with low AUC importance
is calibration; high on both is discrimination). The first run stopped at the reproduction guard
(deviation 1.4e-6 against a tolerance of 1e-6, because the features are stored to six significant
digits); the tolerance became 1e-5 by a same-day note before any importance was read. The record
run is `eb9753cb`.

The script loads `n1_baselines.py` by path for the solver, the scores and the interval helper so
the three N-scripts share one definition of each.

## Mathematical / Statistical details

- **Permutation importance.** For group `g` with test-row columns `X_g`, draw a permutation
  `pi` of the test rows and replace `X_g` by `X_g[pi]` (all of the group's columns with the same
  `pi`); predict with the fixed model; `I_Brier(g) = mean_k BS(p_perm,k) - BS(p)` and
  `I_AUC(g) = AUC(p) - mean_k AUC(p_perm,k)` over `k = 1..20`. Both are differences of scores on
  the same rows, so the paired day bootstrap resamples days and recomputes both differences
  inside each resample.
- **Why a feature can have a large coefficient and zero importance.** Permutation within a
  period shuffles a feature's values among rows of that period; if the feature is nearly constant
  there, the shuffle changes nothing. `n_distinct` is 27.7 ± 2.1 on the test rows against
  23.3 ± 6.0 on the training rows; its coefficient (-0.82 standardised) lowered every test forecast
  by about the same amount, which is the between-period calibration N1 measured, and permutation
  cannot see it. Likewise `same_sign_share` has no test row in its training "high" tercile.
  Coefficients read the between-period information, permutation importance the within-period one.
- **Effect sizes.** Beyond `d` (Brier +0.0057, AUC +0.129, which is the null's own ordering), the
  surviving signals are `same_sign_share` (+0.0011, interval +0.00008 to +0.0021; AUC +0.011,
  +0.002 to +0.021) and `abs_d_rel` (+0.0005, +0.00025 to +0.0007; AUC +0.006, +0.004 to +0.008),
  against a record Brier of 0.0999 and AUC of 0.711.
- **Cells.** Terciles on training rows: `d` at -0.474 and 0.409 (the middle cell straddles the
  sign, since `|d| >= 0.37`), `same_sign_share` at 0.506 and 0.699, `abs_d_rel` at 0.669 and 0.949.
  15 cells unreadable, all for want of test rows in the share's "high" tercile.

## Design decisions

- **Brier and AUC apart, never combined**, as the lead asked and amendment 6 requires; the
  decomposition of N1 is read group by group.
- **Grouped permutation** for a feature and its indicator, so a missing-value indicator cannot be
  credited or blamed separately from the feature it qualifies.
- **The model is not refitted after permutation.** Permutation importance measures what the fitted
  model uses, not what a model could learn without the feature; the latter is a different
  question and not pre-registered.
- **Guard tolerance from stored precision.** The deviation was the file format's, not the model's;
  the note says so and the tolerance is still five orders below any reported effect.
- **Register rows after N3, not before.** The protocol said N3 mints the rows, so N0's counts and
  N1's clause-1 result waited; all three rows are written from the committed outputs with the
  script and output commits named, after re-scanning every remote branch for the next free id.

## Verification

- Self-test (synthetic: two informative features rank first on both metrics, a noise feature
  near zero, 27 cells partition the training rows):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n3_importance.py --selftest
  ```

- Reproduce the record (about four minutes; the guard stops the run if the refit deviates from the
  recorded forecasts by more than 1e-5):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n3_importance.py --out <dir>
  ```

  then compare `<dir>/importance.tsv` with `docs/evidence/pattern-detector/importance.tsv`.

- The per-period distributions quoted in README §11 come from `features.tsv.gz`: mean and standard
  deviation of `n_distinct` and `same_sign_share` by `split`, and the share of test rows above the
  training 2/3 quantile of `same_sign_share` (zero).

- Lint: `ruff check` and `ruff format --check` on the script report nothing. Em dashes: a Python
  count of `chr(0x2014)` over the new files returns 0.

## Related docs

- `docs/evidence/pattern-detector/README.md` (sections 7, 10, 11)
- `docs/implementations/2026-10-26-pattern-detector-n1-baselines.md`
- `docs/implementations/2026-10-26-pattern-detector-protocol-n0.md`
- `docs/numerical-claims.md` NC-092 to NC-094
- Issue #110 (comment 6412965244), PR #124 (`bf4c54e2`)
