# 2026-10-27: pattern detector, the statistics review round (amendment 8)

## Problem / Motivation

@bengisucvd's statistics review of PR #128 (review 5667003181 at `6f1f4bc8`) requested changes on
six points: label leakage across the temporal boundaries (175 training rows whose labels use
post-cut events; an inner split that cut one snapshot's rows in two), an archive warm-up that the
2026-10-26 analysis had read as a test-period regime change, an inconsistent null parameterisation
(MAD-standardised residual shape against a variance-identified drift ratio), a bootstrap that
resampled single days despite a five-event label horizon, an N3 claim stronger than permutation
importance can carry (plus a reversed direction for `abs_d_rel`), and the need to mark the result as
an amended analysis rather than a confirmatory test. Every one of her figures reproduced from the
committed tables before anything was changed.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pattern-detector/README.md` | Amendment 8 in section 7 (the six fixes, clause 2's discrimination requirement, wording); section 12, the amended analysis; status line points to section 12. |
| `docs/evidence/pattern-detector/n1_amended.py` | New: the amended N1 pipeline (warm-up and crossing purges, complete-timestamp inner split with label-time purge and fitting-slice scaling, consistent null scales with a recovery check, circular block bootstrap with a chosen block length), writing to `amended-2026-10-27/`. |
| `docs/evidence/pattern-detector/n1_baselines.py` | `Built` carries each row's label time and crossing flag; `simulate_null` gains a unit-variance standardisation mode and recovery diagnostics (simulated increments, lag-one pairs, residual sample). |
| `docs/evidence/pattern-detector/n3_importance.py` | Reads only `train` and `test` rows; a multi-column group is cut on its first column in the scenario cells. |
| `docs/evidence/pattern-detector/amended-2026-10-27/*` | New: the amended N1 and N3 outputs; the 2026-10-26 outputs are untouched. |
| `docs/numerical-claims.md` | Dated notes appended inside the Notes cells of NC-092 to NC-094; values and the registered rule unchanged. |
| `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` | Dated as-of note under §4.9. |
| `docs/implementations/2026-10-27-pattern-detector-review-round-amendment-8.md` | This record. |

## Implementation approach

**Order.** Reproduce the reviewer's figures (memory rule: reproduce before fixing); write amendment
8 and the code in one commit (`48687e19`, imports sorted in `b1d182db`), which is the frozen
corrected pipeline for the next unseen evaluation; run N1 (`n1_amended.py`) and N3 into the new
folder; write section 12 and the register notes; push; reply.

**Purges.** `t_full = first file + 30 d`. Rows with event time before `t_full` are labelled
`purged_warmup`; training rows whose fifth successor's time is at or after the cut are labelled
`purged_crossing`; neither enters training or test. The null simulation still starts at the
archive's first file so that windows fill, but counts pairs only from `t_full`; the residual
shape uses full-history training residuals only. The inner boundary is the time of the row at the
80% quantile of training times, with every row at that time on the fitting side; a fitting row is
kept only when its label time is at or before the boundary; standardisation is fitted on the
fitting slice for the tuning and on the purged training set for the final model.

**Null scales.** Under `L_j = mu_j + e_j`, `mu_j = mu_{j-1} + eta_j`, the increment
`D = e_{j+1} - e_j + eta_{j+1}` has `Var(D) = sigma_e^2 (2 + q)` and lag-one autocorrelation
`-1 / (2 + q)`, so `q` from the pooled `rho` and `sigma_e^2 = Var(D) / (2 + q)` per qubit; the
residual shape `z` is standardised to zero mean and unit variance so that `Var(e_sim) = sigma_e^2`
exactly and the simulated variance ratio is `q`, as the reviewer required. The recovery check
compares simulated against observed increment variance and `rho`, and the simulated signed residual
quantiles and skew against the observed full-history residuals.

**Bootstrap.** Circular blocks of `L` consecutive calendar days over the 46 test days, all rows of
a day together, 1,000 resamples; `L` is the smallest lag at which the autocorrelation of the daily
mean Brier difference stays inside two standard errors, floored at six days (the five-event
horizon plus the event); results at 1, 3, 5, 7 and 10 days reported beside the chosen `L`.

## Mathematical / Statistical details

- **Warm-up.** For an event at `t < t0 + 30 d` the window `(t - 30 d, t)` is truncated at the
  archive start, so the level averages fewer, earlier states and a departed reading has fewer
  states to be compared against; the label then measures how fast a short mean catches up with the
  series, which is why the first 30 days show a shift rate of 0.578 against 0.133 afterwards.
- **Label leakage.** A training row's label uses up to five events after `t`; when those fall
  after the cut, the fitted model has seen test-period information. Purging those rows lowers the
  training positives from 714 to 222 (with the warm-up purge) and moves the clause-1 skill against
  the recorded null from 0.226 to the reviewer's 0.224 at fixed `lambda`; the headline was not
  leakage, but the purge is required for the comparison to be honest.
- **Recovery.** Simulated increment variance 0.1496 against observed 0.1502 (ratio 0.996); lag-one
  `rho` -0.487 against -0.488; simulated residual skew -0.81 against -1.54 observed. The second
  moments are recovered; the shape's skew is about half, the lag-component limitation.
- **Why the null still over-forecasts.** With `sigma_e` from the increments' full variance (median
  0.261, against the MAD-based 0.205 of 2026-10-26) the simulated series carry more scatter and
  more drift than the device's levels do: a local-level process with these moments makes a departed
  reading become the level in about 35% of rows, the device in 13%. The series is more persistent
  in level and more excursion-like in scatter than the local-level family allows.
- **The amended comparison.** Logistic Brier 0.0997; constant at the purged training rate 0.1328
  gives `0.1328 × 0.8672 = 0.1152` in expectation but scores 0.1045 on the test rows because the
  test rate is 0.118 (the oracle constant scores 0.1043); skill of the logistic model against that
  constant `1 - 0.0997 / 0.1045 = 0.046`, interval of the Brier difference at `L = 6` +0.0012 to
  +0.0088. Against the Gaussian null (Brier 0.1563) the skill is 0.362, a statement about the null.
- **Block choice.** Daily difference autocorrelation -0.18, +0.18, -0.15, -0.10 at lags 1 to 4,
  all inside `2 / sqrt(46) = 0.29`; the floor of six days binds. Intervals at 1 to 10 days differ in
  the third decimal.

## Design decisions

- **Amend, disclose, do not overwrite.** Sections 8, 10 and 11 and their files stay; section 12 and
  a new folder carry the amended analysis; the register rows keep their values and gain dated
  notes, the register's own convention. The reviewer asked for exactly this separation.
- **Keep the registered rule, add the sensitivity.** Clause 1 is still read against the null; the
  constant-on-purged-training comparison is reported beside it, and proposed as part of the rule
  only for the next unseen evaluation.
- **The frozen pipeline is a commit, not a promise.** The next evaluation uses rows after the current
  archive tip; re-running at a later ref over the examined test rows would not be unseen.
- **No grid change.** `lambda` at the grid's other end is reported as a limitation.
- **N3's claim narrowed** to model reliance; the stronger claim would need a reduced-versus-augmented
  predictor on untouched time, which does not exist yet.

## Verification

- `PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n1_amended.py --selftest`
  (block choice honours the floor; `sigma_e` recovered on a synthetic local-level series).
- Reproduce the amended run (fields pickle from `collect_fields.py` at `cf960389`, about 20 s for
  N1, about 6 min for N3):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n1_amended.py --fields <dir>/fields.pkl --ref cf960389c672208a3952cbdf08bfd7e338ace40c --out <dir>/amended
  ```

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n3_importance.py --features <dir>/amended/features.tsv.gz --summary <dir>/amended/summary.json --out <dir>/amended
  ```

  then compare `results.tsv` and `importance.tsv` with `docs/evidence/pattern-detector/amended-2026-10-27/`.

- The reviewer's figures from the committed 2026-10-26 tables (reproduced before the change):
  rows before `2026-06-12T12:13:22Z` 789 with rate 0.578 (her calendar-May subset 425 at 0.767);
  full-history training 1,847 rows at 0.140; crossing rows 175; constant on full-history purged
  training 0.1328 with Brier 0.10447 on test; inner boundary snapshot `2026-08-12T05:59:18Z` split
  22/14.
- `ruff check .` and `ruff format --check .` clean; em dashes counted in Python: 0 in the new text.

## Related docs

- `docs/evidence/pattern-detector/README.md` sections 7 (amendment 8) and 12
- `docs/implementations/2026-10-26-pattern-detector-n1-baselines.md`,
  `2026-10-26-pattern-detector-n3-importance.md`
- `docs/numerical-claims.md` NC-092 to NC-094
- PR #128, review 5667003181; Issue #110
