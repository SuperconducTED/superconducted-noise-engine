# Pattern detector: does the archive say when a reading has become the level? (task N0)

**Date**: 2026-10-26 · **Author**: Mert Efe Şensoy (lead) · **Status**: **protocol, committed
before any row was counted** (`49256efe`, section 8 empty there); section 8 holds the counts of the
record run, appended in a later dated commit from the committed script; **amendment 2 in section 7
replaces the null of section 4 before N1 runs**; nothing is scored against the labels before tasks
N1 to N3; **section 12 (2026-10-27) is the amended analysis after @bengisucvd's review and
supersedes the readings of sections 10 and 11, which stay as the record** · **Ticket**: #110, tasks N0 to N6 (comment 6412965244) · **Decision that allows it**: phase-4
plan §4.1 (PR #124 at `bf4c54e2`): no deep-model **training** before gate L1, the protocol commit
may be written now · **Source of the design**: `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md`
§4.3 to §4.5 · **Reviewers**: @bengisucvd (statistics: the null's value, the thresholds, the
bootstrap unit, the minimum rule in §6); Dr. Akba (ratification of the success rule, through the
advisor brief) · **Reading of the lead's 2026-10-26 note that the neural model starts today**: the
model's code, the baselines (N1) and synthetic checks may start; N2, the network trained on the
archive, waits for gate L1 under §4.1 unless the lead amends that line.

## 1. The question

On `ibm_fez` each per-qubit calibration reading is a slowly moving level plus independent scatter
(lag-1 autocorrelation of log increments -0.49, NC-084), and the hardware test (#125) asks, on
average over eight qubits a day, whether the device follows the latest reading or the level. This
protocol asks the question the hardware test cannot: **when a reading departs from its level, do
calibration patterns at that moment say whether the next readings will follow the reading (a
shift) or return to the level (a transient)?** If they do, the design-time rule "carry the level"
has a measurable exception; if they do not, the level is the rule without exception on this
archive. Either answer is a row in the paper's ladder. The network is tested only as the second
clause: a pattern that a logistic rule prices is a pattern, not a reason for a network.

This is **not** the own-history forecaster of decision A7. That route is closed (NC-084 to
NC-086, `docs/evidence/predictability/README.md` §3.4 on PR #124's branch).

## 2. Data, unit, label

**Archive.** `calibration-data`, `ibm_fez` snapshots under `snapshots/`, read with `git show` at a
ref pinned in §8 (never a checkout, because `autocrlf` rewrites the files). Files are sorted by
`properties.last_update_date`; a **distinct state** is the first file of each `qubit_digest`
(`scripts/canonical_snapshot_digest.py`), and the count of distinct states must equal the
`is_new_state` count in `health/state-index.tsv` at the same ref, or the script stops (the
reproduction guard of 2026-10-24).

**Two event definitions, each with its source, because they differ.**

- A **re-measurement event** of qubit `q` is a change of the value of `log T1_q` between
  consecutive files, as `measure_predictability.py` defines it (NC-084's autocorrelation was
  measured on these). The label and the unit of this protocol use this definition.
- A **chip-wide sweep** is a file in which at least 20% of comparable qubits carry a new `T1`
  **date**, as `measure_persistence_band.py`'s `recal_times` defines it. Only the feature "hours
  since the last sweep" uses dates.

**Level.** For an event at time `t`, `T1_level(t)` is the geometric mean of `T1_q` over the
distinct states with time in `(t - 30 d, t)`, **strictly before `t`**, so the event's own state
is excluded (the pre-registration's window `(t_s - 30 d, t_s]` is inclusive, right for a
predictor, wrong for a label about whether the reading moved its own reference). It is
**state-weighted**, as `predictor_rows` computes it for the hardware test: a value unchanged
across many chip states counts once per state. The level exists when the window holds at least
5 states and at least 3 distinct `T1_q` values; otherwise the event is not a row.

**Disagreement.** `d(t) = log T1_reading(t) - log T1_level(t)`, with `T1_reading(t)` the new value
at the event.

**Unit.** A **row** is a re-measurement event with `|d(t)| >= delta`.

**`delta = 0.37` log units**, NC-084's 80% scatter of a qubit's log target between re-measurements
(the one scatter figure the register holds), used as given. A smaller `delta` admits rows the
scatter alone produces; a larger one leaves too few. §6 names the fallback.

**Label.** With `m` the median of the next `k = 5` re-measured values of `log T1_q` after `t`
(the next five events, about five days at the median re-measurement gap of 24.7 h, NC-091):

- `y = 1` if `|m - log T1_reading(t)| < |m - log T1_level(t)|`: the reading became the level (a
  shift);
- `y = 0` otherwise: the reading was an excursion (a transient).

**Censoring.** An event whose `k` successors fall past the archive tip has no label and is
dropped; the count of dropped events is reported per split. The test period is the one that
loses rows.

**Split.** Snapshot boundary at `2026-09-01T00:00:00Z`, as NC-080 to NC-086: an event is a
training row if `t` is before the cut and a test row otherwise; no label crosses the cut in the
training set (a training event whose successors fall after the cut is kept, its label uses them,
and the count of such events is reported; Bengisu may move them to neither set).

## 3. Features, frozen at this commit

All computable at `t` from files at or before `t`. `d` of them; `d = 14`.

| # | Feature | Definition |
| --- | --- | --- |
| 1 | `d` | the signed disagreement |
| 2 | `abs_d_rel` | `|d| / (log p90 - log p10)` of the same window's `T1_q` (the band width; 0 width gives a missing value, handled as the row's exclusion) |
| 3 | `prev_d` | the qubit's previous event's `d`, or 0 with an indicator if none |
| 4 | `n_distinct` | distinct `T1_q` values among the window's states |
| 5 | `hours_since_prev` | hours since the qubit's previous re-measurement event |
| 6 | `hours_since_sweep` | hours since the last chip-wide sweep (date definition) |
| 7 | `d_t2` | the same-window disagreement of `log T2_q` at `t` (0 with an indicator if no level) |
| 8 | `d_readout` | the same for `log readout_error_q` |
| 9 | `chip_readout` | the median over all qubits of their `d_readout` at `t` (the chip-wide readout excursion, NC-086) |
| 10 | `same_sign_share` | among qubits with a level at `t`, the share whose `d` has the same sign as this qubit's |
| 11 | `sx_log` | `log` of the qubit's `sx` gate error at `t` |
| 12 | `cz_best_log` | `log` of the smallest `cz` error on an edge touching the qubit at `t` |
| 13 | `hour_sin` | `sin(2 pi h / 24)` of `t`'s UTC hour |
| 14 | `hour_cos` | `cos(2 pi h / 24)` |

**Core list (the §6 fallback):** features 1, 2, 3, 5, 9. Named now so a reduction after the count
is a pre-stated branch, not a choice made on the data.

## 4. Models, and the null

**The null, per event.** Under the model the archive supports, `log T1_q` is a **local level seen
through noise**: `L_j = mu_j + e_j`, `mu_j = mu_{j-1} + eta_j`, `e_j ~ (0, sigma_q^2)`,
`eta_j ~ (0, q sigma_q^2)`. NC-084's pooled `rho = -0.49` gives `q = -1 / rho - 2`, about 0.04:
small, not zero, and over `k = 5` events the level moves enough to change `P(y = 1 | d)` at small
`|d|`, so the drift term stays in. For event `i`:

`p_null,i = P(y_i = 1 | d_i, sigma_q, q, k, n_i)`,

by Monte Carlo (20,000 draws, `SeedSequence(84)`): start at `mu_0 = 0`, draw the level-estimate
error `eps_L ~ (0, sigma_q^2 / n_i)` with `n_i` the number of distinct `T1_q` values in the window
(the reading is compared to an estimated level, not a true one), draw the `k` successors under the
local-level model, take their median `m`, and set `y = 1` if `|m - d_i| < |m - eps_L|`.

- `q` is fixed from the pooled lag-1 autocorrelation of **training** increments, floored at 0 when
  `rho <= -0.5`.
- `sigma_q` is per qubit, a **robust** scale of the qubit's training increments:
  `sigma_q = 1.4826 · MAD(increments) / sqrt(2)` (an increment of two independent noises has
  variance `2 sigma_q^2`; the dips this protocol labels would inflate a plain standard deviation).
- The fixed-level closed form, `P(y = 1 | d) ≈ 1 - Phi(|d| / (2 · 1.2 sigma_q / sqrt(k)))`, is
  reported as a reference row; Bengisu may collapse the two nulls into one.

Why the null is not a constant: the label is built from `d`, so under pure noise the probability
of `y = 1` falls steeply with `|d|`, and a model that knows only `|d|` beats a constant forecast with
no device pattern at all (the audit's §4.4 and its synthetic check). Scoring against the
conditional null removes that.

**Reference rows, not nulls.** The constant forecast `p_0` (training base rate; Brier
`p_0 (1 - p_0)`), and the "always level" rule `p = 0` (Brier `p_0`), the current design's implicit
answer.

**The bar.** Logistic regression on the 14 features (or the core list, §6), fitted on training
rows with an L2 penalty chosen on the last 20% of the training period in time order.

**The network (N2, not before L1).** NumPy multilayer perceptron, decision A4: 14 inputs, one
hidden layer of `h` `tanh` units, sigmoid output, `(d + 2) h + 1` parameters, trained on the log
loss by gradient descent with early stopping on the same inner slice; `h` chosen there and
recorded; five seeds from `SeedSequence`, median reported with spread; the test period is touched
once, at scoring.

**Pattern extraction (N3).** Permutation feature importance on the logistic model and on the
network, 90% intervals from the bootstrap and the seeds; then scenario enumeration over the
discretised top features, with the number of archive events in each cell.

## 5. Scoring, bootstrap, and the two clauses

**Scores**, on test rows: Brier score `BS = mean_i (p_i - y_i)^2`; log loss; AUC (description
only, because the conditional null's own AUC exceeds 0.5 through `|d|`). Brier skill against the
conditional null: `BSS_1 = 1 - BS / BS_null`.

**Bootstrap.** Blocks are calendar days of `t` (the 156 qubits of one time share one device
state, so row resampling understates the uncertainty, as the predictability README §2.1 item 5
argues); 1,000 resamples, `SeedSequence(84)`, 90% intervals; **paired**: the same days are drawn
for both models of every difference.

**Clause 1, a pattern exists.** `BSS_1(logistic) >= 0.10`, with the paired 90% interval of
`BS_null - BS_logistic` excluding zero. The 0.10 is a gap above a null whose expected skill is
zero by construction, the same 10% margin the predictability rule used above its null.

**Clause 2, the network is needed.** `BSS_1(network) - BSS_1(logistic) >= 0.05` for the seed
median, with the paired 90% interval of the difference excluding zero.

**Outcome table, in advance.**

| Clause 1 | Clause 2 | Reading | What follows |
| --- | --- | --- | --- |
| no | not scored | no calibration pattern says when a reading has become the level; the level is the rule without exception on this archive | the network item closes with a registered negative; the ladder gains the row "pattern detector: none found"; #110 stays parked |
| yes | no | a pattern exists and a linear rule prices it | the logistic rule is the interpretable exception to "carry the level", a candidate fuzzy rule (decision A6); the network closes; one NC row |
| yes | yes | the network finds structure the linear rule misses | the network is a candidate stage-1 component of the third engine (A1); the hardware sign check (N5) at L2 comes before any paper sentence; the permutation ranking is the paper's pattern table |

Thresholds are proposals for Bengisu's review and Dr. Akba's ratification; any change is a dated
amendment in §7, committed before N1 runs.

## 6. The minimum, decided before the count

Each floor comes from a stated rule, not from feel; Bengisu reviews the rules.

- **Logistic needs about ten positive rows per parameter** (a common rule for binary models; the
  parameters are `d + 1`). With `d = 14`: **150 positives in training**. With the core list,
  `d = 5`: **60 positives in training**.
- **The day bootstrap needs blocks to resample**: at least **30 distinct test days holding a
  row**, and at least **30 positives in the test period** so that a 0.10 skill gap is not decided
  by a handful of events (with a few percent base rate under the null, 30 positives means on
  the order of a thousand test rows).

**Decision tree, committed before counting.**

1. Training positives `>= 150` and the test floors met: run with the 14 features.
2. Training positives in `[60, 150)` and the test floors met: run with the **core list** (§3).
3. Training positives `< 60`, or test positives `< 30`, or fewer than 30 test days with a row:
   lower `delta` once, to **0.25**, and re-count (this admits rows the scatter alone produces,
   and the conditional null prices exactly that, which is why the null is conditional); apply 1
   or 2 to the new counts.
4. Still below: the item **stops** with a registered negative, "insufficient rows on this archive",
   and reopens only when the record is longer (about 200 new test rows a month at the archive's
   daily cadence is the expectation to check, not a claim).

The count script (§8) reports every number this tree needs and nothing scored against the
labels. The branch taken is recorded in §8 with the counts.

## 7. Amendments (dated, append-only, each before the run it affects)

**Amendment 1, 2026-10-26, before section 8 was read; citation only, no value changed.** §2 cites
`delta = 0.37` as "NC-084's 80% scatter". NC-084's 0.37 is the lambda forecasting cap (`R^2`), a
coincidence of digits. The 0.37 log-unit scatter is the **80% conformal half-width of the
shrinkage band on test change rows**, 0.375 in the predictability README's ladder table (PR #124's
branch), whose register row is **NC-085** (the cell quotes the rolling band's half-width, about
0.34 log units). Found by the session drafting the advisor brief, which checked every figure
against its row. `delta` stays 0.37; the count run already in progress used it.

**Amendment 2, 2026-10-26, after the counts of section 8 were read and before N1; it changes the
null, not the label, the features, the clauses or the floors.** Section 4's Monte Carlo starts the
simulated level at the window mean (`mu_0 = 0`) and lets it drift only over the `k` successors. That
omits the **lag of a 30-day window mean behind a drifting level**: under the local-level model with
the archive's own `q` (0.050, section 8) the reference the protocol computes is itself stale by the
drift accumulated inside the window, and the next readings are often nearer the new reading than
that stale mean with no device pattern at all. A synthetic check (implementation doc, Verification;
synthetic figures, not register claims) gives `P(y = 1 | |d| >= 0.37)` of about 0.35 under
`q = 0.05` with a 30-event window mean as the reference, against about 0.04 with a fixed level, and
the same on both signs of `d`. Section 4's sentence "`y = 1` is rare under the null (a few percent
of events ...)" and section 6's "with a few percent base rate under the null" are therefore
**superseded**: under the null as the protocol actually computes its reference, `y = 1` is common.
The observed base rates (section 8) sit at or below that figure, so **the base rate is not a
finding**. Caught before any scoring, as lesson L-029 requires.

**The null forecast, as N1 computes it.** The null is *the protocol's own label computed on
simulated series*:

- per qubit, simulate the local-level process `L_j = mu_j + e_j`, `mu_j = mu_{j-1} + eta_j`
  (`Var(e) = sigma_q^2`, `Var(eta) = q sigma_q^2`, the shared `q` of section 8 and the qubit's robust
  `sigma_q`) **at the qubit's actual re-measurement times**, over the training period plus the
  30 days before its first training event, for 2,000 replicates, `SeedSequence(84)`;
- map simulated values onto the **real states**: every state in a window takes the simulated value
  of the qubit's latest event at or before that state's time, which is exactly how the archive maps
  events to states, so the state weights come from the real state timing, not from an event-level
  approximation;
- compute the level, `d_sim` and `y_sim` for every simulated event with the protocol's own rules
  (strictly-before window, 5 states, 3 distinct values, `delta`, `k`), keeping every `(d_sim, y_sim)`
  pair with `|d_sim| >= delta`;
- estimate `p_null(d)` per qubit by binning `d_sim` in **0.05 log-unit bins**, pooled over the sign of
  `d` because the null is sign-symmetric by construction (the check gives 0.35 on both sides, so the
  **sign of `d` is a legitimate feature**, not something the null absorbs); a bin with fewer than
  200 simulated pairs borrows the pooled-over-qubits bin value;
- `p_null,i` is the bin value at the observed `d_i` for the event's qubit. `BS_null` is its Brier
  score on the test rows, as section 5 defines.

Section 4's fixed-level closed form and its `mu_0 = 0` Monte Carlo become **reference rows** that
show why the null matters; they are no longer the null. Section 6's floors stand (all are met with
room, section 8); only their rationale's base-rate sentence was wrong. Bengisu's review covers this
amendment with the rest; Dr. Akba's brief describes the null in these terms.

**Amendment 3, 2026-10-26, before N1 ran; implementation choices the protocol left open, decided
without looking at any score.** The lead asked for N1 (baselines and the amended null, nothing
deep) on 2026-10-26.

1. **Indicator columns.** Features 3, 7 and 8 say "0 with an indicator if none". The indicators are
   three extra columns of the design matrix, so the logistic model has 17 inputs (14 features, 3
   indicators) and 18 parameters; section 6's ten-per-parameter floor is 180 training positives,
   still met (714).
2. **Missing gate errors.** A row whose `sx` error or every touching `cz` error is absent or
   non-positive at `t` is excluded, with the count reported; a `cz` error recorded as 1 (a failed
   calibration) is a value, not missing, and enters the minimum as 1.
3. **Hours since the last sweep** when no sweep precedes `t`: the hours since the first file of the
   archive.
4. **The scale fallback.** A qubit without a robust `sigma_q` (fewer than 20 training increments)
   takes the median `sigma_q` over qubits for its null forecast; the count is reported.
5. **The null's bins** are over `|d|`, 0.05 log units wide from `delta` upward, the last bin
   open-ended at 1.5; the pooled-over-qubits bin is the replicate-weighted pool.
6. **The logistic bar.** Features standardised on training rows; L2 penalty `lambda` chosen on
   the inner slice (the last 20% of training rows in time order; fit on the first 80%) from the
   grid `{0.001, 0.01, 0.1, 1, 10}` by log loss, then refit on all training rows; Newton
   iterations to convergence.
7. **Rows at `t` where the qubit has no `T2` or readout level** keep their indicator; the
   chip-wide readout excursion (feature 9) is the median over the qubits that have one, and
   `same_sign_share` (feature 10) is over the qubits that have a `T1` level at `t`.
8. **The reproduction guard of N1** is the N0 record: the rows N1 rebuilds from the field
   collection must equal `rows.tsv.gz` (qubit, time, `d`, `y`) or the script stops.

**Amendment 4, 2026-10-26, before N1 scored anything; the null's noise shape.** A row is
`|d| >= delta` by construction, the tail of the scatter, and NC-089 already records that the
large disagreements are dips: real `log T1` scatter is heavy-tailed on the low side. The
local-level null of amendment 2 draws Gaussian noise, which has no tails: under it a large `|d|`
is mostly drift and `P(y = 1)` stays high, whereas under heavy-tailed noise a large `|d|` is mostly
an excursion that reverts, and more so on the dip side. Section 8's per-sign counts already have
that shape (positives 0.39 of rows above the level, 0.16 below, against a sign-symmetric Gaussian
null near 0.35). A logistic model with signed `d` would clear clause 1 against the Gaussian null on
the known shape of the scatter alone, which is not a pattern an engineer learns from calibration.
Lesson L-029, caught before the run.

1. **The primary null draws the noise from the qubit's own residual shape.** For each qubit, the
   training-period residuals `r = v - level` of every event that has a level (all events, not
   only rows) are centred on their median and rescaled so that their robust scale
   (`1.4826 · MAD`) equals the qubit's `sigma_q` of section 8 (the shape comes from the
   residuals, the scale from the increments, so the drift term is not counted twice); `e_j` is
   resampled with replacement from that set, sign preserved, so the dip skew is in the null.
   Everything else of amendment 2 is unchanged: the drift term `eta_j`, the real event times, the
   real state mapping, 2,000 replicates, the `|d|` bins. A qubit with fewer than 20 residuals
   borrows the pooled standardised residuals of all qubits.
2. **The Gaussian local-level null of amendment 2 becomes a reference row**, reported beside the
   empirical one.
3. **Clause 1 is read against whichever of the two nulls has the lower Brier score on the test
   rows** (lesson L-028, the strongest baseline the protocol produces); both are reported, and the
   pre-registered margin and interval rule are unchanged.
4. **A calibration diagnostic precedes any reading of clause 1:** for each null, its mean forecast
   on the training rows per sign of `d` beside the observed `y = 1` rate per sign, and the same on
   the test rows. If the empirical null reproduces the 0.39 and 0.16 of section 8, the sign
   asymmetry is the tail shape and the protocol says so itself.
5. **The train-to-test drop in the base rate** (0.27 to 0.12, section 8) is not explained by
   censoring alone; `k` counts events, not hours, so a change in re-measurement cadence changes how
   much drift five events span. N1 reports events per qubit per day for each period and each
   null's mean forecast on the test rows. If the nulls predict the drop, the comparison stands; if
   not, the write-up says that the logistic model and the nulls are both miscalibrated on the test
   period and the skill gap is a statement about who is less wrong.

**Amendment 5, 2026-10-26, after the first N1 run's calibration table was read and before clause 1
was read or recorded; made on seeing data, not blind.** The first run of the committed
`n1_baselines.py` (`c9b4b612`) produced the amendment 4 diagnostic and, in the same output, a
clause-1 figure. Both are disclosed here so that nothing is hidden by the amendment: the
empirical null's own simulation gave `y = 1` rates of 0.216 below the level and 0.411 above
(the Gaussian null 0.318 and 0.319), the sign asymmetry amendment 4 expected; but amendment 2's
bins pool over the sign of `d` "because the null is sign-symmetric", which the empirical null no
longer is, so its forecast (0.264 below, 0.336 above on training rows, against observed 0.162 and
0.389) discarded the very asymmetry it was introduced to carry. The first run's clause-1 figure
was a logistic Brier skill of 0.258 against the sign-pooled empirical null (90% interval 0.200 to
0.324); it is **not the record**, because the null it was measured against was mis-specified by
the protocol's own text.

1. **Bins are by signed `d`** for both nulls: `len(bins)` bins below the level and the same above,
   0.05 log units wide in `|d|` from `delta`, last bin open-ended; the pooled fallback is per
   signed bin. The Gaussian null is symmetric, so this changes only its sampling noise.
2. **The test-timing diagnostic of amendment 4 item 5 is made concrete:** each null is also
   simulated at the **test period's own event times** (events from 30 days before the cut, so the
   windows fill, counted from the cut), with the training-period `q`, `sigma_q` and residual shape;
   its per-sign simulated rates, its mean forecast on the test rows and its Brier score there are
   reported beside the training-timing null. If this null also forecasts far above the observed
   test rate, the drop is not cadence and the nulls are miscalibrated on the test period for a
   reason the archive's own statistics do not carry.
3. **Reference-row intervals.** The paired day bootstrap also reports the logistic model's Brier
   difference and skill against the "always level" rule and against the constant forecast, and the
   "always level" rule against the primary null, because the first run showed the "always level"
   rule scoring better than both nulls on the test period (Brier 0.118 against 0.134); lesson
   L-028 says the write-up must show the comparison against the strongest baseline the protocol
   produced even where the pre-registered clause names a different one. **Clause 1's rule is not
   changed** (lower-Brier null, 0.10, interval excluding zero); the extra rows are read beside it.

**Amendment 6, 2026-10-26, after the second N1 run and before section 10 was written; a feature
defect and the rule for reading clause 2.**

1. **A frozen feature was dead in the first two runs.** `hours_since_sweep` was zero on every row:
   the code took the last sweep at or before `t` with a float epsilon that vanishes at epoch scale,
   and an event's own file is usually a chip-wide sweep (IBM re-measures `T1` chip-wide), so the
   column was constant and the constant-column guard dropped it silently. Fixed to the last sweep
   **strictly before** `t` (`77e5a7d8`); the column now runs from 4.1 to 100.6 hours, median 24.7.
   The second run's figures (`6aa5b8d5`, signed bins, dead feature) were a clause-1 skill of 0.226
   (0.157 to 0.299) and are superseded by the record run of section 10, which differs from them
   in the fourth decimal: the feature carries no weight. `d_readout_missing` is constant because
   every row's qubit has a readout level; it is dropped with this sentence.
2. **A skill clause is decomposed before it is read as a pattern.** A Brier skill score can be
   earned by predicting the period's shift rate (calibration) or by ordering which disagreements
   shift (discrimination). Section 10 reports both, and **clause 2 (task N2) is read the same
   way**: the network's skill over the logistic bar must be accompanied by its AUC against the
   logistic model's and by the oracle row below, so that clause 2 cannot pass on base-rate
   anticipation alone; N3's permutation importance is scored on Brier and on AUC separately.
3. **An oracle diagnostic row**, the constant forecast at the test period's own observed base
   rate, is reported beside the scores. It is not a pre-registered baseline (it uses the test
   labels) and no clause is read against it; it bounds how much of a model's skill is the
   period's rate.

**Amendment 7, 2026-10-26, before N3 ran; the permutation protocol's open details.** The lead
asked for N3 on 2026-10-26 ("permutation importance on the logistic model, scored on Brier and on
AUC separately, archive only, nothing deep"). Section 4 names permutation importance and scenario
cells without fixing their details; fixed here before the run.

1. **Model and rows.** The record logistic model of section 10 (`lambda = 10`), refitted from the
   committed `features.tsv.gz` and checked against the recorded forecasts to 1e-6 (the N3
   reproduction guard); importance is measured on the **test rows only**, the model untouched.
2. **Groups.** A feature and its indicator are permuted together (`prev_d` with `prev_d_missing`,
   `d_t2` with `d_t2_missing`); `d_readout_missing` is constant and absent. 15 groups.
3. **Importance.** For each group, the group's test-row values are permuted jointly 20 times
   (`SeedSequence(86)`); Brier importance is the mean permuted Brier minus the record Brier
   (positive: the group helps calibration-weighted accuracy); AUC importance is the record AUC
   minus the mean permuted AUC (positive: the group helps ordering). The two are reported side by
   side and ranked separately, never combined.
4. **Intervals.** 90% from the paired day-block bootstrap of section 5 (1,000 resamples of the 46
   test days, `SeedSequence(87)`), the 20 permutations fixed inside each resample.
5. **Scenario cells.** The three groups with the largest Brier importance (features, not
   indicators), each cut at its training-row terciles; 27 cells; per cell the training and test row
   counts, the observed `y = 1` rate in each, the logistic model's and the empirical null's mean
   forecast on the test rows; cells with fewer than 20 rows in a split are flagged and not read.
6. **Registration.** N3 mints one NC row per conclusion in Rule 7 form (dated anchor at
   `calibration-data` `cf960389`, the live artifact named, not a current value), on this branch,
   from the next free id after every open branch's register (NC-092 at the time of writing).
7. **Reading rule.** A group that ranks high on Brier and low or negative on AUC moved the forecast
   level (calibration); one that ranks high on both ordered the rows (discrimination). The
   decomposition of amendment 6 is read group by group.
8. *Note, same day, before any importance was read:* item 1's guard tolerance of 1e-6 stopped the
   first run at a deviation of 1.4e-6, because `features.tsv.gz` stores the features to six
   significant digits and the forecasts to six decimals; the tolerance is 1e-5, a reading of the
   stored precision and nothing about the model.

**Amendment 8, 2026-10-27, after @bengisucvd's statistics review of PR #128 (review 5667003181 at
`6f1f4bc8`). This is analysis after the test outputs were examined, not a confirmatory test.**
Sections 8, 10 and 11 and their output files stay as the historical record of 2026-10-26; the
amended run writes to `amended-2026-10-27/` and is read in section 12. The committed pipeline of
this amendment (`n1_amended.py`, the patched `n1_baselines.py` and `n3_importance.py`) is the frozen
corrected pipeline for the next genuinely unseen temporal evaluation, which can use only rows after
the current archive tip; re-running at a later ref over the already-examined test rows is not it.

1. **Warm-up purge** (review item 2). A trailing-window reference is undefined until the window is
   complete. Rows whose event time precedes the first archived file plus 30 days
   (`2026-06-12T12:13:22Z`) leave every table: the design matrix, the null simulation's counted
   pairs (the series is still simulated from the archive start so the windows fill), and the
   residuals that give the noise shape. The review's finding that the rows before that boundary
   carry a shift rate near 0.6 against 0.14 after it, so that most of section 10's "27% to 12%" drop
   predates the test boundary, is reproduced in section 12; the regime-change reading of sections
   10 and 11 is withdrawn there.
2. **Crossing-row purge** (review item 1). Training rows whose fifth successor falls at or after
   the cut leave the training set and do not enter the test set. The inner tuning boundary falls
   on a complete timestamp (every row at one time on one side); a fitting row is kept only when its
   fifth successor precedes that boundary; standardisation is fitted on the fitting slice for the
   tuning and refitted on the purged outer training set for the final model. `lambda` is re-chosen
   on the same grid; a boundary optimum stays a limitation.
3. **Null scales made consistent** (review item 3). The residual shape is standardised to zero
   mean and unit variance, so `Var(e_sim) = sigma_e^2` exactly; `sigma_e` per qubit comes from
   training increments under the stated model, `Var(D) = sigma_e^2 (2 + q)`, with the pooled `q`;
   the Gaussian null uses the same `sigma_e`. A recovery check reports the simulated increment
   variance and lag-one autocorrelation against the observed training values, and the simulated
   signed residual quantiles and per-sign label rates against the observed full-history training
   rows. Limitation stated, not resolved: a trailing-window residual contains measurement scatter
   and the level's lag inside the window, and the simulation adds its own random walk to a shape
   that already carries some lag; no identification of the latent process is claimed. The
   empirical null stays primary and the Gaussian null a sensitivity reference; the wording is "the
   tail shape can reproduce the asymmetry", not "the asymmetry is the tail shape".
4. **Dependence-preserving bootstrap** (review item 4). Circular blocks of consecutive calendar
   days, all qubits of a day kept together; the block length is the smallest lag at which the
   autocorrelation of the daily mean Brier difference stays inside two standard errors, floored at
   six days (five successor events at about one a day, plus the event); results at 1, 3, 5, 7 and
   10 days are reported beside the chosen length.
5. **N3's claim narrowed** (review item 5). Permutation importance is model reliance: what the
   fitted model uses, exploratory, pointwise intervals across 13 groups after feature selection; it
   does not establish information beyond the null, which would need a null-based or reduced
   predictor against an augmented one on untouched time. Section 11's sentence on `abs_d_rel` is
   reversed and corrected in section 12: a negative coefficient means a larger disagreement
   relative to the qubit's band lowers the fitted shift probability. "Between-period mechanism"
   becomes "between-period association".
6. **Clause 2's discrimination requirement**, defined before N2 (review note on thresholds): the
   network passes clause 2 only if its Brier skill gain over the logistic model is at least 0.05
   **and** its AUC gain over the logistic model has a block-bootstrap 90% interval excluding zero;
   the AUC magnitude is left at zero as a design choice flagged for review.
7. **Wording.** The 0.10 and 0.05 margins are practical design choices, not detection limits; the
   minimum rule's floors are screening heuristics, not power guarantees under dependence (Riley et
   al. 2019 on events per parameter); the always-level rule's log loss is clipped at 1e-6, a literal
   `p = 0` forecast has infinite log loss; the always-level comparison stays descriptive; the
   outcome is persistence of **reported `T1` estimates**, not a physical relaxation-rate transition
   or an improved quantum-channel prediction, and the hardware check (#125) remains the arbiter.

**Amendment 9, 2026-10-28, after @bengisucvd's re-review (review 5681736384 at `c436d222`); two
follow-ups, before the pipeline is frozen for the next unseen evaluation.**

1. **The bootstrap's time axis is the calendar.** Amendment 8's block bootstrap indexed the days
   that held test rows (46 of them) and so drew blocks of six consecutive *observed* days, not six
   calendar days; the test span is 2026-09-01 to 2026-10-20, 50 calendar days, with 2026-09-10,
   2026-09-16, 2026-10-02 and 2026-10-08 empty. Blocks are now drawn on the complete calendar axis,
   empty dates kept with zero rows and zero loss, and a resample's score is the row-weighted mean
   (sampled loss sums over sampled row counts). The dependence diagnostic runs at calendar lags
   with empty dates treated as missing: the lag-`k` sum uses pairs of observed dates `k` calendar
   days apart, normalised by the variance over the observed dates (pairwise deletion); the
   standard-error bound keeps the observed-day count. A regression check with an internal calendar
   gap is in the self-test. N3's intervals use the same helper at the chosen block length; its
   2026-10-27 single-day intervals are historical and were never dependence-adjusted evidence.
2. **The warm-up explanation is an association, not an identified cause.** The purge establishes
   that most of the rate contrast predates the test boundary and is consistent with
   archive-start and window effects; it does not separate those from a contemporaneous change in
   the reported calibration process or in the device, and the collapse of the `n_distinct`
   coefficient does not resolve that confounding. Sections 12.1 and 12.6 and the implementation
   note are reworded accordingly; the purge stands without a causal claim.
3. **The next unseen evaluation's rule** keeps the paired positive Brier-difference requirement
   beside the added AUC requirement for clause 2; all choices are frozen at this amendment's commit.

## 8. Counts, at the ref of the record run

Appended 2026-10-26 from `count_events.py` (committed at `8db25e37`; the JSON writer's line ending
was fixed afterwards and the run reproduced from the pickled collection with identical content, so
the reproduction compares content, the committed blob being LF-normalised). Laptop, pinned
interpreter `C:/t/pin125` (numpy only beyond the project's code), `PYTHONPATH=src;.`. The archive
walk (2,330 `git show` calls on a OneDrive path) took about 21 minutes; the count itself seconds.
**Provisional until Burak's desktop reproduces it (N6). No figure here is a register row until N3
registers the conclusions in Rule 7 form.** Outputs: `counts.json`, `counts.tsv`, `rows.tsv.gz` (the
4,061 labelled-or-censored rows at `delta = 0.37`, N1's input).

**Ref and guard.** `calibration-data` `cf960389c672208a3952cbdf08bfd7e338ace40c`; 2,330 `ibm_fez`
files from `2026-05-13T12:13:22Z` to `2026-10-26T06:02:39Z`; **944 distinct states**, equal to the
`is_new_state` rows of `health/state-index.tsv` at that ref (guard passed); 154 chip-wide `T1`
sweeps by the date rule.

**Events.** 23,036 re-measurement events of `log T1` over 156 qubits: 14,837 before the cut,
8,199 after.

**Rows at `delta = 0.37`** (the protocol's value):

| | Train (before 2026-09-01) | Test |
| --- | --- | --- |
| rows incl. censored | 2,638 | 1,423 |
| censored (fewer than `k` successors) | 0 | 129 |
| rows | 2,638 | 1,294 |
| positives (`y = 1`) | 714 | 153 |
| base rate | 0.271 | 0.118 |
| rows below the level / positives | 1,376 / 223 | 779 / 35 |
| rows above the level / positives | 1,262 / 491 | 515 / 118 |
| distinct days with a row / with a positive | 85 / 80 | 46 / 43 |
| qubits with a row | 156 | 154 |
| rows per qubit, min / median / max | 1 / 17 / 42 | 1 / 8 / 20 |
| training rows whose `k` successors cross the cut | 175 | |

**Rows at the fallback `delta = 0.25`** (counted in the same run, not used): train 5,274 rows,
1,774 positives, 90 days; test 2,667 rows (257 censored), 462 positives, 46 days.

**The null's parameters** (training increments only, no label touched): pooled lag-1
autocorrelation `rho = -0.488` over 14,681 pairs (NC-084 gave -0.486 on `5828b4a2`), so
`q = 0.050`; robust `sigma_q` for 155 qubits: min 0.076, p10 0.160, median 0.205, p90 0.259,
max 0.341 log units.

**Section 6's branch: 1, the full 14-feature list at `delta = 0.37`** (714 training positives
against the floor of 150; 153 test positives against 30; 46 test days against 30). The fallback
was not needed.

**Two sentences of reading, and no more.** The observed base rates (0.27 train, 0.12 test) sit at
or below what the amended null of section 7 produces under no pattern (about 0.35 in the synthetic
check), so the base rate is not a finding and must not be quoted as one. The difference between
the two signs of `d` in the table is a count, reported because section 6 asked for it; what it
means is N3's permutation table, not this section.

## 10. N1 results: the nulls, the reference rows and the logistic bar

Record run of `n1_baselines.py` at `77e5a7d8` on the field collection at `calibration-data`
`cf960389` (same ref as section 8; `collect_fields.py`, walk about 20 minutes, the run 14 s), the
lead's go of 2026-10-26 ("baselines and the amended null, nothing deep"). Reproduction guard: the
3,932 labelled rows rebuilt from the field collection equal `rows.tsv.gz`. **Laptop, provisional
until N6; nothing registered until N3 mints the NC rows.** Outputs: `summary.json`, `results.tsv`,
`features.tsv.gz` (design matrix, labels, both null forecasts, the logistic forecast),
`null_bins.tsv`, `calibration.tsv`. Three runs happened, each from a committed script; the first
two are disclosed in amendments 5 and 6 and are not the record.

**Rows.** 2,636 training rows (2 excluded for a zero band width, none for missing gate errors),
1,294 test rows; positives 714 and 153 as in section 8. Design matrix 17 columns; `d_readout_missing`
constant and dropped (amendment 6). Logistic `lambda = 10`, the top of the pre-registered grid
(inner losses 0.3863 to 0.3853, monotone), inner cut `2026-08-12T05:59:18Z`.

**The nulls, as simulated** (training increments and residuals only; `rho = -0.488`, `q = 0.050`,
one qubit on the median `sigma_q`, one on the pooled residual shape; pooled standardised residual
skew -1.49, 5th and 95th percentiles -2.02 and +1.49). Simulated `y = 1` rates at training timing:
empirical null 0.216 below the level, 0.411 above; Gaussian null 0.318 and 0.319. At the test
period's own event times: empirical 0.226 and 0.418, Gaussian 0.330 and 0.329. Bin fallbacks to the
pooled bin: 322 rows (empirical), 592 (Gaussian) of 3,930.

**Calibration diagnostic (amendment 4 item 4), read first.**

| Split | Sign of `d` | Rows | Observed `y = 1` | Empirical null | Gaussian null | Logistic |
| --- | --- | --- | --- | --- | --- | --- |
| train | below | 1,374 | 0.162 | 0.198 | 0.292 | 0.167 |
| train | above | 1,262 | 0.389 | 0.413 | 0.320 | 0.383 |
| test | below | 779 | 0.045 | 0.188 | 0.287 | 0.049 |
| test | above | 515 | 0.229 | 0.418 | 0.323 | 0.187 |

Two readings the protocol fixed in advance. First, **the sign asymmetry is the tail shape**: the
empirical null reproduces it on the training rows to within 0.04 and 0.02; the Gaussian null does
not; amendment 4 was right. Second, **the nulls are miscalibrated on the test period**: both
forecast 0.28 to 0.30 where 0.118 is observed, at training timing and at the test period's own
timing (mean forecast 0.287, Brier 0.130), with 0.86 against 0.95 events per qubit per day. Cadence
does not explain the drop; the archive's May-to-August statistics do not carry whatever reduced
the shift rate in September and October. Amendment 4 item 5's sentence applies: the logistic model
and the nulls are calibrated on different things, and the skill gap against the nulls is a
statement about who is less wrong about the period's rate.

**Scores on the 1,294 test rows.**

| Forecast | Brier | Log loss | AUC | Mean forecast | Skill vs empirical null | Skill vs always-level |
| --- | --- | --- | --- | --- | --- | --- |
| empirical null (primary, lower Brier) | 0.1290 | 0.417 | 0.737 | 0.280 | 0 | -0.091 |
| Gaussian null (reference) | 0.1349 | 0.449 | 0.663 | 0.302 | -0.046 | -0.141 |
| constant `p_0` (reference) | 0.1276 | 0.433 | 0.500 | 0.271 | +0.011 | -0.079 |
| always level, `p = 0` (reference) | 0.1182 | 1.634 | 0.500 | 0 | +0.083 | 0 |
| **logistic (the bar)** | **0.0999** | **0.346** | **0.711** | **0.104** | **+0.226** | **+0.156** |
| oracle: constant at the test rate (diagnostic, amendment 6) | 0.1043 | | 0.500 | 0.118 | +0.192 | +0.118 |

Paired day-block bootstrap, 46 test days, 1,000 resamples, 90% intervals: empirical-null Brier
minus logistic Brier 0.0205 to 0.0377; logistic skill against the empirical null **0.157 to 0.299**;
against the always-level rule 0.126 to 0.178 (Brier difference 0.0129 to 0.0236); against the
constant, Brier difference 0.0228 to 0.0328. The always-level rule against the primary null:
-0.024 to +0.002, including zero. Gaussian minus empirical null: 0.0014 to 0.0105, the empirical
null is the better one, as amendment 4 predicted.

**Clause 1, as pre-registered: holds.** The logistic model's Brier skill against the lower-Brier
null is 0.226, above 0.10, with the paired interval excluding zero (and excluding 0.10). It also
clears 0.10 against the strongest reference row the protocol produced, the always-level rule
(0.156, interval 0.126 to 0.178), and against the constant (0.217).

**What the skill is, decomposed (amendment 6 item 2).** It is calibration, not discrimination.
The logistic model's mean forecast on the test rows is 0.104 against an observed 0.118, and
0.049 and 0.187 per sign against 0.045 and 0.229: it anticipated the lower shift rate of the test
period from features observable at submission time. Against the oracle constant at the test
period's own rate its skill is 0.042, below the margin. Its AUC, 0.711, is **below the empirical
null's 0.737**: which disagreements become shifts is not ordered better than signed `d` and the
qubit's own tail shape already order it. By standardised coefficient the anticipation runs
through `n_distinct` (-0.82: more distinct `T1` values in the window, fewer shifts), the sign of
`d` (+0.58), `same_sign_share` (+0.56: a disagreement shared by many qubits is more often a shift),
the indicators `prev_d_missing` (+0.31) and `d_t2_missing` (-0.29), `chip_readout` (-0.25) and
`cz_best_log` (+0.20); `hours_since_sweep` carries no weight. These are descriptions; what the
pattern is, and whether `n_distinct` is a cadence effect, is N3's permutation table, scored on
Brier and on AUC separately.

**The outcome table's row.** Clause 1 yes; clause 2 not scored (N2 waits for gate L1 under plan
§4.1). The pre-registered reading is "a pattern exists and a linear rule prices it", **with the
decomposition attached**: the pattern found is that the rate at which a departed reading becomes
the level fell in the test period and was predictable from the calibration table's own state,
not that individual shifts are identifiable. The engineer's rule "carry the level" is unchanged;
what the archive adds is a calibrated estimate of how often that rule will be wrong for a given
chip state.

**Limitations.** One test regime: the 46 test days form one period, the day bootstrap resamples
inside it, and the intervals do not carry the uncertainty of the regime change that produced most
of the skill. `lambda` sits at the top of its grid. The 175 training rows whose successors cross
the cut are in the training set (section 2). The nulls' residual shape and scale are from the
training period alone. Laptop; Burak's desktop reproduction (N6) is owed before any figure leaves
the provisional state.

## 11. N3 results: what the logistic bar's skill is made of

Record run of `n3_importance.py` at `eb9753cb` on the committed `features.tsv.gz` and `summary.json`
of section 10 (the refit reproduces the recorded forecasts to 1.4e-6; 1,294 test rows; record
Brier 0.0999, record AUC 0.711; 20 permutations per group, 1,000 day-block resamples; about four
minutes). **Laptop, provisional until N6.** Outputs: `importance.tsv`, `cells.tsv`, `n3_summary.json`.
The NC rows this task mints are NC-092 to NC-094 in `docs/numerical-claims.md` on this branch.

**First sentence.** Within the test period, the model orders the rows the way the null does: the
group that carries almost all of the importance on both metrics is `d`, the signed disagreement,
which is exactly what the empirical null's signed bins carry. Its importance is not a pattern beyond
the null.

**Permutation importance on the test rows** (Brier: permuted minus record, positive helps; AUC:
record minus permuted, positive helps; 90% paired day-block intervals; ranked by Brier).

| Group | Brier importance | 90% | AUC importance | 90% | AUC rank |
| --- | --- | --- | --- | --- | --- |
| `d` | +0.00570 | +0.00373 to +0.00765 | +0.129 | +0.104 to +0.156 | 1 |
| `same_sign_share` | +0.00114 | +0.00008 to +0.00212 | +0.011 | +0.002 to +0.021 | 2 |
| `abs_d_rel` | +0.00049 | +0.00025 to +0.00070 | +0.006 | +0.004 to +0.008 | 3 |
| `prev_d` (with indicator) | +0.00024 | -0.00004 to +0.00052 | +0.003 | -0.001 to +0.007 | 5 |
| `hour` (sin, cos) | +0.00024 | -0.00018 to +0.00067 | +0.001 | -0.004 to +0.006 | 6 |
| `hours_since_prev` | +0.00004 | +0.00001 to +0.00007 | +0.000 | -0.000 to +0.001 | 7 |
| `d_readout` | +0.00003 | -0.00007 to +0.00014 | -0.000 | -0.002 to +0.002 | 8 |
| `d_t2` (with indicator) | -0.00002 | -0.00012 to +0.00008 | -0.000 | -0.001 to +0.001 | 9 |
| `hours_since_sweep` | -0.00003 | -0.00004 to -0.00001 | -0.000 | -0.001 to -0.000 | 10 |
| `chip_readout` | -0.00008 | -0.00125 to +0.00080 | -0.001 | -0.024 to +0.017 | 12 |
| `sx_log` | -0.00025 | -0.00054 to +0.00003 | -0.001 | -0.004 to +0.003 | 11 |
| `cz_best_log` | -0.00044 | -0.00114 to +0.00022 | +0.005 | -0.001 to +0.013 | 4 |
| `n_distinct` | -0.00063 | -0.00206 to +0.00068 | -0.002 | -0.017 to +0.013 | 13 |

**Two small signals survive beyond the null**, both with intervals excluding zero on both metrics
and both a few percent of the record Brier of 0.0999: `same_sign_share` (a disagreement shared in
sign by many qubits at the same time becomes the level slightly more often) and `abs_d_rel` (a
disagreement small relative to the qubit's own 30-day band reverts slightly more often). That is the
whole within-period pattern. The co-movement effect is the candidate fuzzy rule of decision A6,
named with its size: a Brier gain of about 0.001 and an AUC gain of about 0.01.

**The between-period anticipation is invisible to permutation, by construction.** `n_distinct` had
the largest standardised coefficient in section 10 (-0.82) and has zero or negative importance here.
The reason is in the per-period distributions: on the test rows `n_distinct` is 27.7 ± 2.1 against
23.3 ± 6.0 on the training rows, and `same_sign_share` has **no test row in its training "high"
tercile** (test 90th percentile 0.647 against the tercile cut at 0.699; test mean 0.51 ± 0.10
against 0.62 ± 0.20). Permuting a feature within a period cannot credit it for having moved the
whole period's forecast level. The rule: **coefficients carry between-period information,
permutation importance carries within-period information**, and the two features that moved the
forecast level are the two whose distributions shifted between the periods. The test period
re-measured `T1` more often and had no chip-wide co-moving episodes, and its shift rate was lower;
with one regime change over 46 days, that is a hypothesis for the next regime, not a registered
pattern.

**Scenario cells** (`d`, `same_sign_share`, `abs_d_rel` at training terciles; `cells.tsv`). Two
caveats before any reading: the `d` "mid" tercile is `[-0.474, 0.409]`, which with `|d| >= 0.37`
**straddles the sign** and holds small dips and small rises together, so the three `d` cells are not
a monotone step; and 15 of the 27 cells are unreadable because the test period never reaches the
`same_sign_share` "high" tercile, not because the training data are thin. In the 12 readable cells
the test `y = 1` rate runs from 0.00 to 0.25, lowest where `d` is low (dips) and `abs_d_rel` high,
highest where `d` is high and the share is mid; the logistic model's mean forecast sits within a few
points of the observed rate in most cells, and the empirical null over-forecasts every cell by two
to four times. The latter is section 10's test-period miscalibration seen cell by cell, not cell
structure.

**The outcome table's row, with the decomposition attached.** Clause 1 yes; clause 2 not scored
(N2 waits for gate L1 under plan §4.1); the reading "a pattern exists and a linear rule prices it"
holds in this form: *within a period, nothing beyond the signed disagreement and the qubit's own
tail shape orders which departed readings become the level, plus a small chip-co-movement effect;
across the two periods the shift rate moved, and the calibration table's own state (re-measurement
count, co-movement) tracked it.* The engineer's rule "carry the level" is unchanged. What this adds
for the design-time predictor is a calibrated estimate of how often that rule will be wrong for a
given chip state, and one interpretable candidate rule for the fuzzy base.

**What N3 did not do.** No network (N2), no second target (N4), no hardware rows (N5), no desktop
reproduction (N6). Nothing in sections 8 to 11 is a current value: every figure is the state at
`calibration-data` `cf960389`, and the same scripts re-run at a later ref are the live artifact.

## 12. Amended analysis after the statistics review (2026-10-27)

Analysis after the test outputs were examined, under amendment 8; **not a confirmatory test**.
Pipeline frozen at `b1d182db` (N1) and `138ed72d` (N3); outputs in `amended-2026-10-27/`
(`summary.json`, `results.tsv`, `features.tsv.gz` with a `label_time` column and the purge labels
in `split`, `calibration.tsv`, `null_bins.tsv`, `importance.tsv`, `cells.tsv`, `n3_summary.json`).
Same archive ref `cf960389`; the N0 reproduction guard passed (3,932 rows). Laptop, provisional
until N6. The 2026-10-26 figures of sections 8, 10 and 11 stand as the historical record and are
quoted beside the amended ones.

### 12.1 The warm-up finding comes first

The review's aggregation reproduces: the rows whose 30-day window began before the archive did
(event time before `2026-06-12T12:13:22Z`, the first file plus 30 days) carry a shift rate of
**0.578** (789 rows, 456 positives, 21 days); the rows after a complete window carry **0.133** in
training (1,672 rows after the crossing purge, 222 positives, 60 days) against **0.118** in test.
Most of section 10's "0.27 to 0.12" drop therefore predates the test boundary and is consistent
with archive-start and window effects; **these observations do not identify its physical cause**
(amendment 9): the purge does not separate window-start effects from a contemporaneous change in
the reported calibration process or in the device. **The regime-change reading of sections 10
and 11 is withdrawn** as a claim about the test period. With the warm-up rows gone, `n_distinct`,
the largest standardised coefficient of section 10 (-0.82), falls to +0.02: a small count of
distinct values in the window is what an incomplete window looks like, so the "between-period
anticipation" is consistent with a warm-up proxy; the collapse of the coefficient does not by
itself resolve the time confounding. The 175 crossing rows (positive rate 0.206) leave the
training set and enter nothing.

### 12.2 Decision tree on the purged counts

16 parameters after two constant columns dropped (`prev_d_missing` now never fires on full-history
rows, `d_readout_missing` as before), floor 160 training positives; 222 training positives, 153
test positives, 46 test days: **branch 1, the full feature list.** The floors are screening
heuristics, not power guarantees under dependence.

### 12.3 The nulls, re-parameterised, and the recovery check

`q = 0.050` from the pooled training lag-one autocorrelation `-0.488` (14,681 pairs); `sigma_e` per
qubit from `Var(D) = sigma_e^2 (2 + q)` on training increments, median 0.261 (section 10's robust
scale was 0.205: the heavy tails were being discounted). Residual shape from full-history training
residuals (10,129 events, 155 qubits, skew -1.54), standardised to zero mean and unit variance.
**Recovery:** simulated increment variance 0.1496 against observed 0.1502 (ratio 0.996), simulated
lag-one autocorrelation -0.487 against -0.488, for both nulls; simulated residual skew -0.81
(empirical) and +0.01 (Gaussian) against observed -1.54; simulated residual 5th and 95th percentiles
-0.57 and +0.48 (empirical) against observed -0.59 and +0.40. The increments' second moments are
recovered exactly; the residual shape is recovered in direction and roughly in width, with the
simulated skew about half the observed, the lag-component limitation amendment 8 states.

**Calibration diagnostic, full-history rows only.**

| Split | Sign of `d` | Rows | Observed | Empirical null | Gaussian null | Logistic |
| --- | --- | --- | --- | --- | --- | --- |
| train (purged) | below | 1,073 | 0.083 | 0.230 | 0.335 | 0.085 |
| train (purged) | above | 599 | 0.222 | 0.521 | 0.379 | 0.219 |
| test | below | 779 | 0.045 | 0.247 | 0.337 | 0.079 |
| test | above | 515 | 0.229 | 0.530 | 0.373 | 0.201 |

Two readings. First, **the tail shape can reproduce the asymmetry**: the empirical null's rates
are higher above than below by about the observed ratio (2.3 against 2.7 in training); the
Gaussian null's are not. Second, **both nulls over-forecast by a factor of two to four on every row
set, warm-up excluded**, at training and test timing alike. Section 10 attributed that to a test
period the May-to-August statistics did not carry; with the warm-up rows gone the over-forecast is
there in training too, so the explanation changes: a local-level process with the archive's own
increment variance and lag-one autocorrelation makes a departed reading become the level about 35%
of the time, and the device does it about 13%. The series is more persistent in its level, and
more excursion-like in its scatter, than a Gaussian or residual-shaped local-level decomposition of
its increments allows. That is a statement about the null's family, recorded as a limitation; no
identification of the latent process is claimed.

### 12.4 Scores on the 1,294 test rows, amended

| Forecast | Brier | Log loss | AUC | Mean forecast | Skill vs Gaussian null (primary, lower Brier) | Skill vs constant on purged training |
| --- | --- | --- | --- | --- | --- | --- |
| empirical null | 0.1645 | 0.500 | 0.729 | 0.360 | -0.052 | -0.574 |
| Gaussian null | 0.1563 | 0.499 | 0.645 | 0.352 | 0 | -0.496 |
| constant on purged training, 0.1328 (the review's sensitivity) | 0.1045 | 0.364 | 0.500 | 0.133 | +0.332 | 0 |
| constant of 2026-10-26, 0.271 | 0.1276 | 0.433 | 0.500 | 0.271 | +0.184 | -0.221 |
| always level, `p = 0` (log loss clipped) | 0.1182 | 1.634 | 0.500 | 0 | +0.244 | -0.132 |
| **logistic, `lambda = 0.001`** | **0.0997** | **0.340** | **0.719** | **0.127** | **+0.362** | **+0.046** |
| oracle: constant at the test rate (diagnostic) | 0.1043 | | 0.500 | 0.118 | +0.333 | +0.002 |

`lambda = 0.001`, the bottom of the grid (inner losses 0.33856 to 0.33959, nearly flat): a
boundary optimum at the other end from section 10, a limitation, not a reason to widen the grid on
this test set. Inner boundary `2026-08-13T06:23:00Z` (complete timestamp); 1,196 fitting rows after
160 were purged by label time; 316 validation rows.

**Dependence-preserving bootstrap** (amendment 9: on the complete calendar axis). The test span
is 2026-09-01 to 2026-10-20, **50 calendar days, 46 with rows**; 2026-09-10, 2026-09-16,
2026-10-02 and 2026-10-08 are empty and stay on the axis with zero rows. Daily mean Brier
difference (null minus logistic) autocorrelation at calendar lags 1 to 5, empty dates deleted
pairwise: -0.18, +0.26, -0.23, +0.04, -0.22, all inside two standard errors (0.29, from the 46
observed days), so the floor sets the block: **6 consecutive calendar days**, circular, all qubits
of a day together, scores row-weighted. At that block, 90% intervals: Gaussian null minus logistic
Brier **+0.051 to +0.063**; logistic skill against the null 0.316 to 0.417; always-level minus
logistic +0.010 to +0.027; **constant on purged training minus logistic +0.0010 to +0.0085**;
always-level minus null -0.052 to -0.025 (both nulls score worse than the always-level rule, the
interval excluding zero). The intervals at 1, 3, 5, 7 and 10 calendar days move in the third
decimal; the sensitivity table is in `amended-2026-10-27/summary.json`. The 2026-10-27
observed-day intervals (+0.0012 to +0.0088 for the constant comparison) are superseded and
differed from these in the fourth decimal; the reviewer's independent six-calendar-day interval,
+0.0010 to +0.0087, agrees.

### 12.5 Clause 1, amended, and what the skill is

**As pre-registered, clause 1 holds** (skill 0.362 against the lower-Brier null, interval excluding
zero and the margin). **That comparison is now nearly uninformative**: the null forecasts 0.35
where 0.12 is observed, and a constant at the purged training rate beats both nulls by a third.
Against that constant, the strongest reference row the protocol produced and the one the review
asked for, the logistic model gains **4.6%** (Brier 0.0997 against 0.1045; interval +0.0012 to
+0.0088, excluding zero), **below the 0.10 margin**; against the oracle constant at the test rate
4.4%; against the always-level rule 15.7%. Its AUC, 0.719, is again **below the empirical null's
0.729**.

The amended reading of the outcome table's row: by the registered rule, "a pattern exists and a
linear rule prices it"; by the strongest baseline, a small, statistically resolvable but
practically marginal gain over knowing the full-history shift rate, with no ordering of which
disagreements shift beyond signed `d` and the tail shape. The engineer's rule "carry the level" is
unchanged and, if anything, better supported: a departed reading became the level in 13% of
full-history rows, far below what a local-level model of the archive's own increments would
predict. The outcome is persistence of **reported `T1` estimates**; it says nothing about a
physical relaxation-rate transition or about quantum-channel prediction, which only the hardware
test (#125) can address.

**Pre-registered for the next genuinely unseen evaluation** (rows with event time after
`2026-10-26T06:02:39Z`, the current archive tip, once enough of them exist for the floors): the
frozen pipeline of this amendment; clause 1 read against **the better of the primary null and the
constant at the full-history training rate**, margin 0.10, 6-day circular block interval excluding
zero; clause 2 under amendment 8 item 6. A design choice for @bengisucvd's review before that
evaluation runs.

### 12.6 N3, amended: model reliance, exploratory

`n3_importance.py` on the amended design matrix (refit reproduces the recorded forecasts; 20
permutations per group; 1,000 resamples). Permutation importance here is **what the fitted model
uses on the test rows**, exploratory, pointwise 90% intervals across 13 groups after feature
selection; it is not evidence beyond the null, which would need a null-based or reduced predictor
against an augmented one on untouched time. *Amendment 9:* the table below carries the intervals
from the **6-calendar-day circular block bootstrap** (run at the commit named in section 12.7); the
2026-10-27 single-day intervals were never dependence-adjusted evidence and are superseded; the
point importances are unchanged by the resampling unit.

| Group | Brier importance | 90% | AUC importance | 90% |
| --- | --- | --- | --- | --- |
| `abs_d_rel` | +0.00607 | +0.00422 to +0.00792 | +0.101 | +0.079 to +0.124 |
| `d` | +0.00406 | +0.00245 to +0.00576 | +0.074 | +0.060 to +0.088 |
| `hour` | +0.00037 | -0.00029 to +0.00101 | +0.000 | -0.007 to +0.008 |
| `hours_since_prev` | +0.00012 | +0.00004 to +0.00020 | +0.001 | -0.001 to +0.002 |
| `d_t2` | +0.00010 | -0.00006 to +0.00029 | +0.002 | +0.001 to +0.003 |
| `prev_d` | +0.00009 | -0.00002 to +0.00019 | +0.001 | +0.000 to +0.003 |
| `same_sign_share` | +0.00008 | -0.00005 to +0.00022 | +0.001 | +0.001 to +0.002 |
| `n_distinct` | +0.00003 | -0.00002 to +0.00008 | -0.000 | -0.001 to +0.000 |
| `d_readout` | -0.00001 | -0.00008 to +0.00006 | -0.001 | -0.002 to +0.001 |
| `hours_since_sweep` | -0.00018 | -0.00039 to +0.00003 | -0.002 | -0.006 to +0.002 |
| `chip_readout` | -0.00027 | -0.00122 to +0.00044 | -0.003 | -0.016 to +0.009 |
| `cz_best_log` | -0.00064 | -0.00220 to +0.00106 | +0.002 | -0.010 to +0.015 |
| `sx_log` | -0.00141 | -0.00265 to +0.00005 | -0.007 | -0.019 to +0.005 |

(6-calendar-day circular blocks, 1,000 resamples; the 2026-10-27 single-day intervals differed in
the fourth decimal and are in the historical `n3_summary.json` of commit `e90fdec7`.)

The model relies on two groups, both functions of the disagreement itself: `abs_d_rel` (the
disagreement relative to the qubit's own 30-day band) and signed `d`. Everything else is within
noise of zero or slightly negative (`sx_log`, the gate error the model also weights, costs it on the
test rows). Section 11's small `same_sign_share` and `abs_d_rel` effects do not survive in that form:
`same_sign_share` is now within noise, and `abs_d_rel` is the main input. Direction corrected from
section 11: the negative `abs_d_rel` coefficient (now the largest, -0.92) means a **larger**
disagreement relative to the qubit's own band lowers the fitted shift probability, holding the
other inputs fixed; readings far outside their band revert. "Between-period mechanism" is
withdrawn with the warm-up finding; the between-period reading of section 11 is an association
consistent with incomplete windows, whose cause these observations do not identify (amendment 9).

**Scenario cells** (`abs_d_rel`, `d`, `hour` at training terciles; the `d` middle tercile still
straddles the sign): 20 of 27 readable. The test shift rate runs from 0.00 to 0.41 and is ordered by
the two disagreement features alone: lowest where `abs_d_rel` is high and `d` low (readings far
below their band, 0.00 to 0.04), highest where `abs_d_rel` is low and `d` high (small rises inside
the band, 0.22 to 0.41); the logistic forecast tracks each cell within a few points; the empirical
null over-forecasts every cell by two to four times. The `hour` tercile adds nothing readable.

### 12.7 Run record of the amended analysis

| Run | Script commit | Outputs commit | Note |
| --- | --- | --- | --- |
| amended N1, observed-day blocks (2026-10-27) | `b1d182db` | `e90fdec7` | superseded by the calendar-axis run below; its intervals differed in the fourth decimal |
| amended N3, single-day intervals (2026-10-27) | `138ed72d` | `e90fdec7` | point importances stand; intervals superseded |
| amended N1, calendar-axis blocks (2026-10-28, amendment 9) | `d7087e69` | `02f86e58` | the record of sections 12.4 and 12.5 |
| amended N3, 6-calendar-day block intervals (2026-10-28) | `d7087e69` | the commit that landed this row (`git log -1 -- docs/evidence/pattern-detector/amended-2026-10-27/importance.tsv`) | the record of section 12.6 |

Frozen for the next genuinely unseen evaluation: the scripts at `d7087e69`; rows with event time
after `2026-10-26T06:02:39Z` only; clause 1 against the better of the primary null and the constant
at the full-history training rate, margin 0.10, with the paired Brier difference's 6-calendar-day
block interval excluding zero; clause 2 under amendment 8 item 6 with the paired positive Brier
difference kept beside the AUC requirement. Any change before that run is a dated amendment here.

## 9. Related

## 9. Related

- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` §4 (the design and the lead's decision)
- `docs/roadmap/2026-10-23-phase-4-plan.md` §4.1 (PR #124 at `bf4c54e2`)
- `docs/evidence/predictability/README.md` and `measure_predictability.py` (PR #124's branch;
  the event definition, the local-level cap, the split)
- `docs/evidence/persistence-band/measure_persistence_band.py` (PR #123's branch; `recal_times`)
- `scripts/hardware_test_predictors.py` (PR #126's branch; the state-weighted level)
- `scripts/canonical_snapshot_digest.py`, `scripts/init_error_analysis.py` (`main`; the digest and
  the `git show` helpers this folder's script uses)
- NC-084, NC-085, NC-086, NC-091 (`docs/numerical-claims.md` on PR #124's and the pre-registration
  branch)
- `docs/implementations/2026-10-26-pattern-detector-protocol-n0.md` (the two synthetic checks)
- Issue #110 comment 6412965244; Issue #125
