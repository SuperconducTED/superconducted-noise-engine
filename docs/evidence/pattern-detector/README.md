# Pattern detector: does the archive say when a reading has become the level? (task N0)

**Date**: 2026-10-26 · **Author**: Mert Efe Şensoy (lead) · **Status**: **protocol, committed
before any row was counted** (`49256efe`, section 8 empty there); section 8 holds the counts of the
record run, appended in a later dated commit from the committed script; **amendment 2 in section 7
replaces the null of section 4 before N1 runs**; nothing is scored against the labels before tasks
N1 to N3 · **Ticket**: #110, tasks N0 to N6 (comment 6412965244) · **Decision that allows it**: phase-4
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
