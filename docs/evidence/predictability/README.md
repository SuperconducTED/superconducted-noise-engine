# How predictable is per-qubit calibration drift? The ladder below the deep model

**Date**: 2026-10-23 · **Author**: Mert Efe Şensoy · **Protocol pre-registered before the run**
(section 2 committed before `measure_predictability.py` produced a number; results appended
in section 3 with the commit that produced them) · **Follows**: PR #123
(`docs/evidence/persistence-band/`), whose rows, split and conventions this reuses ·
**Bears on**: Issue #110 (the deep engine, decision A7: forecast the target at `t + h`),
Issue #64, ADR-013 · **Status**: laptop run, provisional; canonical reproduction on Burak's
desktop owed (section 5)

## 1. Why this comes before any deep-model work

Decision A7 makes the deep engine a forecaster of the per-qubit target at `t + h`. A
forecaster earns its place only if there is predictable structure left after persistence and
shrinkage toward the recent level, and the three-engine research already recorded that linear
and shrinkage methods beat deep models on short series. PR #123 showed that at the snapshot
level the mean reverts toward a slow level, that state information about drift is weak, and
that per-qubit values jump by about a quarter whenever a qubit is re-measured. Whether those
jumps have memory is unmeasured, and it is the whole question: if the per-qubit increments
are close to white noise around each qubit's level, no model forecasts them and the deep
engine cannot help the article. This file measures that cap with no model, the way PR #123
measured the bar.

## 2. Protocol, fixed before the run

**Data, rows, split, units.** As in `docs/evidence/persistence-band/README.md` §2 and §2.1:
`calibration-data` @ `5828b4a2`, `ibm_fez`, files read through `git show`, 924 distinct
states by `qubit_digest`, state times as issue times, as-of lookups over **files** inside a
6 h window, snapshot-boundary split at `2026-09-01T00:00:00Z`, no pair straddling the cut.
Per-qubit targets `y_q(t) = (gamma_q, lambda_q)` from `training/targets.py::qubit_targets`
with ADR-027's skip rules. **Everything is in log space**, `L_q = log y_q`, because the
per-qubit jumps are multiplicative (PR #123 §3.3) and a band in log space is a relative band;
a qubit enters a row only where `y_q` is finite and positive at every time the row uses.

**Two views.**

*Event view.* Per qubit, the sequence of re-measurement events: files where `L_q` differs
from the previous file's value. Increments `D_k = L_k - L_{k-1}` between consecutive events,
event times `tau_k`. Reported on training and test events separately (an event is train if
`tau_k < cut`):

- lag-1 autocorrelation of `D` pooled over qubits (Pearson on consecutive pairs), and the
  median of per-qubit lag-1 autocorrelations over qubits with at least 20 events; a
  negative value is memory (a jump tends to be followed by a jump the other way), zero is
  white noise;
- the reversion regression `D_{k+1} = a + b (L_k - level_k) + e`, with `level_k` the mean of
  `L` over the qubit's events in the trailing 30 days before `tau_k` (at least 3 events,
  else the row is skipped); `b` fitted on training events, out-of-sample `R^2` on test
  events. `b = -1` is full reversion to level in one step, `b = 0` is none.

*Horizon view* (what A7 forecasts). For each state time `t` and qubit `q`, the change
`D_H = L_q(t + H) - L_q(t)` for `H` in {24 h, 168 h}. Scoring rows are **change** rows
(`D_H != 0`); `all` rows reported for the vacuity check only. Features at `t`, all computed
from information available at `t`:

| Feature | Definition |
| --- | --- |
| `dev` | `L_q(t) - level_q(t)`, with `level_q(t)` the mean of `L_q` over the qubit's as-of values at the distinct state times in the trailing 30 days (at least 5 states) |
| `last_inc` | the most recent event increment `D_k` at or before `t` |
| `log_age` | log of hours since the qubit's last re-measurement before `t` |
| `recal_age` | hours since the last chip-wide `T1` recalibration before `t` (PR #123's 20% rule) |
| `standing` | `level_q(t) - mean_q' level_q'(t)`, the qubit's level relative to the chip |
| `hour_sin`, `hour_cos` | UTC hour of `t` on the circle |

Models, each fitted on training rows and scored on test rows, pooled over qubits:

1. `persistence`: `D_H^ = 0`.
2. `shrinkage`: `D_H^ = -kappa * dev`, one scalar `kappa` by least squares on training
   change rows (shrink toward the qubit's own recent level).
3. `linear`: ridge regression of `D_H` on the standardised features above plus an intercept
   (`lambda_ridge = 1.0` on standardised features, fixed in advance, no tuning), fitted on
   training change rows.
4. `rolling_band`: no point forecast; the per-qubit 10th to 90th percentile band of `L_q`
   over the trailing 30 days of states, the per-qubit version of PR #123's bar.

Point metrics on test change rows: out-of-sample `R^2` of `D_H` (`1 - SSE / SST` with the
training mean of `D_H` as the reference predictor, so persistence can score below zero only
if the training mean is informative), median absolute error in log units (a relative error).

Band metrics: for models 1 to 3, a split-conformal 80% band `D_H^ ± q`, where `q` is the
80th percentile (`inverted_cdf`) of `|D_H - D_H^|` on a **calibration** set, the training
change rows with `t >= 2026-08-10T00:00:00Z`; the fit uses only training rows before that
date. For model 4 the band is the rolling band itself. On test change rows: coverage, mean
width (log units), interval score at `alpha = 0.2` (PR #123 D2, in log units). The ladder is
the four interval scores side by side.

**Common-mode share.** On test change rows at each `H`, the `R^2` of a regression of `D_H,q`
on the chip's mean `D_H` at the same `t` (over qubits with a change). Not a forecast: it says
how much of a qubit's drift is shared with the chip at the same moment, which bounds what a
model with access to other qubits' same-time measurements could use.

**Vacuity check (L-026).** The zero-width band's coverage on `all` and on `change` rows at
each `H`; the second must be exactly 0.0 or the run stops.

**Bootstrap.** 1,000 resamples of training rows, `SeedSequence(84)`, 90% intervals on the
lag-1 autocorrelation, on `b`, on `kappa`. Rows are temporally and cross-sectionally
correlated (156 qubits share each `t`), so the intervals are optimistic.

**Decision rule, written before the numbers.** Deep-model work is justified by this archive
if, at 24 h on test change rows, **both** hold: the `linear` model's out-of-sample `R^2` of
`D_H` is at least 0.10, **and** its conformal band's interval score is at least 10% below the
per-qubit rolling band's. If the first holds and the second does not, the predictable part
exists but a parameter-free band already prices it: the deep engine is a research item, not
an article item. If neither holds, drift on this device is unforecastable at the
per-qubit level with these features, and the article's framing is the measurement plus the
interpretable fuzzy engine; the deep engine is deprioritised until a richer feature set or a
longer record changes the answer.

**Provenance.** Script `measure_predictability.py` (this folder), pinned interpreter
`C:\pvci` (numpy 2.4.4; only numpy beyond the project's code), `PYTHONPATH=src:.`
(Windows `;`) from the repository root. Outputs `results.tsv`, `rows.tsv`, `summary.json`.

### 2.1 Amended before the run, 2026-10-23 (no number existed yet)

Review of §2 found that its decision rule would have said yes to the deep model in a case
where the honest answer is no, and four looser points. Corrected here, append-only, committed
before the script produced anything.

1. **The decision rule tests the gap above shrinkage, not predictability as such.** Under
   pure measurement noise around a fixed level with no memory at all, `L_k = mu + e_k`,
   the increment is `D_{k+1} = e_{k+1} - e_k`, shrinkage to level (`-dev = -e_k`) leaves the
   residual `e_{k+1}`, and `R^2 = Var(e) / Var(D) = 0.5`. A linear model whose only real
   information is `dev` would therefore clear "`R^2 >= 0.10`" with nothing a deep model could
   learn. Revised rule, at 24 h on test change rows, both clauses required:
   `R^2(linear) - R^2(shrinkage) >= 0.05`, **and** the linear conformal band's interval score
   is at least 10% below the better of the shrinkage conformal band and the per-qubit rolling
   band. The ladder reported is persistence, shrinkage, linear, rolling band; the deep model's
   room is the gap above the better of the top two.
2. **An analytic cap on any own-history forecaster, from the lag-1 autocorrelation.** Under
   a Gaussian local-level model in event time, `L_k = mu_k + e_k`, `mu_k = mu_{k-1} + eta_k`,
   the lag-1 autocorrelation of increments is `rho = -sigma_e^2 / (sigma_eta^2 + 2 sigma_e^2)`:
   `rho = -0.5` is noise around a fixed level (everything forecastable is the level),
   `rho = 0` is a random walk (nothing forecastable). The signal ratio is
   `q = -1 / rho - 2`, the steady-state filter variance ratio is
   `P / sigma_e^2 = (q + sqrt(q^2 + 4q)) / 2`, and the best `R^2` for the next increment
   attainable from the qubit's own history is `R^2_max = 1 - (1 + P / sigma_e^2)(-rho)`.
   Checks: `rho = -0.5` gives 0.5, `rho = 0` gives 0. Reported with its interval from the
   bootstrap on `rho`, under the stated assumption. Shrinkage should sit near the cap; any
   room above it can only come from cross-sectional or exogenous features.
3. **A floor on lambda.** `lambda_q` approaches zero at the `T_2 = 2 T_1` boundary ADR-027
   admits, so `log lambda` increments are unbounded on that tail. Rows where `lambda_q` at
   `t` or at `t + H` (or at either end of an event pair) is below the 5th percentile of the
   training-period lambda values are excluded from the lambda analysis, with the excluded
   count printed. Gamma is primary for the log-space view.
4. **One fit per model.** `kappa` and the ridge are fitted once, on training change rows
   with `t < 2026-08-10T00:00:00Z`; that single fit gives both the point metrics and the
   band, whose quantile comes from the calibration rows `2026-08-10 <= t < cut`, which are
   then genuinely out of fit. Feature standardisation uses the fit rows' statistics only.
5. **Block bootstrap.** 156 qubits share every `t`, so row resampling understates the
   uncertainty several-fold. Horizon-view quantities (`kappa`) resample state times; event-view
   quantities (`rho`, `b`) resample qubits. 1,000 resamples, `SeedSequence(84)`, 90% intervals.

Also fixed before the run: the common-mode regression leaves the qubit out of the chip mean it
is regressed on; the test rows (state time, qubit, as-of time, `D_H`, change flag, per
component) are written to `rows.tsv` (committed as `rows.tsv.gz`) so a later model is scored on identical, citable rows;
the effective training window is printed, since `level`, `log_age` and `last_inc` need
history and the first weeks drop out; the archive walk and as-of lookup are imported from
`../persistence-band/measure_persistence_band.py`, so there is one definition of each.

## 3. Results

Produced by `measure_predictability.py` at commit `261d9df3` of this branch, run 2026-10-23
on Mert's laptop with `C:\pvci` (Python 3.12.10, numpy 2.4.4) against `calibration-data` @
`5828b4a2`. Every figure is in `results.tsv`; the test rows (193,754) are in `rows.tsv.gz` (the script writes `rows.tsv`; it is committed gzip-compressed, SHA-256 in `summary.json`).
**Laptop, provisional.** Checks passed: 924 states equal to the state index; the zero-width
band covers exactly 0.0 of the `change` rows at both horizons and both components (0.168 and
0.141 of `all` rows at 24 h). The lambda floor is 9.59e-5 and excluded 20,885 of the lambda
qubit-rows; gamma lost none. The effective training window is 2026-05-13 to 2026-08-06 for
the fit, 2026-08-10 to 2026-08-31 for calibration.

### 3.1 Event view: the per-qubit series is noise around a level

| Component | Lag-1 autocorrelation of increments, pooled, train (90% block bootstrap over qubits) | Same, test | Median over 155 qubits | Local-level cap on own-history `R^2` (from the train interval) | Reversion slope `b` (90%) | Reversion `R^2`, test |
| --- | --- | --- | --- | --- | --- | --- |
| gamma | **-0.486** (-0.496 to -0.475), n = 14,652 pairs | -0.504, n = 7,718 | -0.494 | 0.38 (0.34 to 0.44); the test value sits at the 0.50 limit | -0.83 (-0.86 to -0.79) | 0.46 |
| lambda | **-0.483** (-0.495 to -0.471), n = 14,412 | -0.500, n = 7,492 | -0.491 | 0.37 (0.33 to 0.43); test 0.48 | -0.84 (-0.89 to -0.79) | 0.45 |

A lag-1 autocorrelation of -0.5 is the signature of independent noise around a fixed level
(§2.1 item 2). Both components sit within 0.02 of it, on every qubit (median -0.49), in both
periods. The level itself barely moves at the per-qubit scale: the signal ratio
`q = -1 / rho - 2` is 0.06 for gamma on the training period and indistinguishable from zero on
the test period. The reversion slope near -0.83 says the same thing: after a re-measurement, the
next re-measurement undoes about 83% of the deviation from the qubit's 30-day level.

### 3.2 Horizon view: the ladder

Test `change` rows, log units (a width of 0.37 is about ±37% relative). Interval score at
`alpha = 0.2`; lower is better.

| Component, horizon | Rows | Persistence: `R^2`, IS | Shrinkage: `kappa`, `R^2`, IS | Linear: `R^2`, IS | Linear minus shrinkage `R^2` | Rolling 30-day band: coverage, width, IS |
| --- | --- | --- | --- | --- | --- | --- |
| gamma, 24 h | 48,470 | 0.000, 1.495 | 0.748, 0.438, 1.090 | 0.436, 1.095 | **-0.002** | 0.763, 0.681, **1.081** |
| gamma, 168 h | 52,745 | 0.001, 1.513 | 0.790, 0.451, 1.094 | 0.451, 1.100 | **+0.001** | 0.764, 0.681, **1.091** |
| lambda, 24 h | 45,061 | 0.000, 1.852 | 0.773, 0.438, 1.336 | 0.439, 1.337 | **+0.001** | 0.751, 0.658, **1.195** |
| lambda, 168 h | 47,478 | 0.000, 1.835 | 0.828, 0.430, 1.317 | 0.431, 1.318 | **+0.001** | 0.756, 0.656, **1.183** |

Conformal 80% half-widths: persistence 0.50 (gamma, 24 h), shrinkage 0.375, linear 0.371; the
bands are wide because the per-qubit jumps are, not because the models are poor.

- **Shrinkage sits at the cap.** Shrinking 75 to 83% of the way to the qubit's own 30-day
  level explains 43 to 45% of the variance of the next change: at the upper edge of the
  training-period cap's interval (0.435) and below the test period's own cap (0.48 to 0.50),
  which is the period the `R^2` is measured on. There is no structure left for an own-history
  model to find.
- **The feature set adds nothing.** The ridge's standardised coefficients are -0.17 to -0.27
  on `dev` and below 0.06 in absolute value on everything else (`last_inc`, age since the last
  re-measurement, time since chip-wide recalibration, standing relative to the chip, hour of
  day). The gap between the linear model and shrinkage is -0.002 to +0.001 in `R^2` and under
  1% in interval score, at both horizons and both components.
- **The rolling 30-day per-qubit band is the best or tied-best band everywhere** without a
  parameter: it beats the linear conformal band by 1% (gamma) and 11% (lambda) on interval
  score, at coverage 0.75 to 0.76 against its nominal 0.80.
- **Horizon does not matter.** Every figure at 168 h is within noise of its 24 h value. Once a
  qubit has been re-measured, how long ago that happened carries no information about where
  the next value lands.

### 3.3 Common-mode share

Leave-one-out regression of a qubit's change on the chip's mean change at the same time, test
`change` rows: `R^2` = 0.020 (gamma, 24 h), 0.015 (gamma, 168 h), 0.001 and 0.001 (lambda).
Per-qubit jumps are idiosyncratic; a model that could see every other qubit's same-time
measurement would gain about 2% of variance for gamma and nothing for lambda.

### 3.4 The decision rule, applied

Pre-registered (§2.1 item 1), at 24 h on test change rows, both clauses required:

| Clause | Threshold | Measured | Holds |
| --- | --- | --- | --- |
| `R^2(linear) - R^2(shrinkage)` | at least 0.05 | -0.002 (gamma), +0.001 (lambda) | no |
| linear conformal IS below the better of shrinkage IS and rolling IS | by at least 10% | gamma: 1.095 against 1.081, 1.3% worse; lambda: 1.337 against 1.195, 12% worse | no |

**Neither clause holds. On this archive, per-qubit calibration drift is not forecastable from
calibration history beyond shrinkage toward the qubit's own recent level**, and a parameter-free
rolling band already prices what is predictable. Under the rule as written, deep-model work is
deprioritised until a richer feature set or a longer record changes the answer; the article's
framing is the measurement plus the interpretable engine, and the right per-qubit engine is a
level-tracking band.

### 3.5 What this does and does not say

- It says: with the features calibration history provides, the next per-qubit value is the
  qubit's level plus independent scatter of about 0.37 log units at 80% (about +45% and -31%
  in the target), and no model built on this history, deep or otherwise, can narrow that band
  materially. The local-level cap is a property of the series, not of a model.
- **The positive reading, as a hypothesis for the next measurement.** A lag-1 autocorrelation
  of -0.49 with `q` near 0.06 says each daily reading is a slowly moving level plus independent
  scatter. The archive cannot tell whether that scatter is the calibration measurement's own
  noise or genuine fast fluctuation of the qubit (the two-level-system picture of Carroll et al.
  2021 and Burnett et al. 2019, both in the novelty check's search), and for a noise model it
  does not need to: under either reading the quantity to put in the channel at run time is the
  qubit's **level**, not its latest reading. `NoiseModel.from_backend`, every calibration-based
  digital twin the novelty check found, and this engine all use the latest reading. A
  level-tracking per-qubit channel is therefore a simple, defensible and, as far as the search
  went, unpublished contribution that this measurement motivates directly, and the fuzzy or IT2
  band becomes the band around that level. The test is reading-versus-level against hardware
  counts; until it runs, this is a hypothesis, not a registered claim.
- It does not say the deep engine can never help. The cap is a cap on own-history and
  same-time cross-sectional information. Exogenous inputs (pulse-level calibration internals,
  the environmental covariates the public dataset carries, queue and usage state) are outside
  this measurement. A deep model fed those would have to clear the same ladder on the same rows.
- It changes decision A7's premise. "Forecast the target at `t + h`" was chosen because a
  same-snapshot target leaks; the measurement says the forecast target is also, at the
  per-qubit level, the current level plus noise. The useful forecasting object is the level,
  and shrinkage already tracks it.
- Target space, log units, one device, nine months. Nothing here is a circuit or a shot.

### 3.6 Caveats found by the run

- The test-period lag-1 autocorrelation sits exactly at the -0.5 limit for gamma (-0.504),
  where the local-level model degenerates to a fixed level; the cap there is 0.5 by convention,
  and the observed shrinkage `R^2` of 0.44 is consistent with it.
- `nanmean` warnings during the level computation come from early state times with no
  history; those rows are excluded by the five-state rule and do not enter any figure.
- The lambda floor removed 20,885 file-by-qubit cells, about 6% of the roughly 351,000 in the
  archive; in the horizon view lambda has 4% fewer fit rows than gamma (46,441 against 48,576)
  and 10% fewer test rows (52,465 against 58,244). The lambda findings are for the usable,
  non-boundary qubits only.

## 4. Caveats fixed in advance

- 156 qubits share every `t`, so pooled `R^2` and intervals overstate independent evidence.
- Nine months, about one re-measurement per qubit per day: a few hundred events per qubit.
  Short for any model; this is the point of measuring the cap first.
- The feature set is what calibration history alone provides. A richer set (pulse-level,
  environmental covariates from the public dataset) is a different study.
- Target space, log units. Nothing here is a circuit or a shot.

## 5. Runbook for the canonical run (Burak's desktop)

```bash
git fetch origin calibration-data
```

```bash
PYTHONPATH=src:. python docs/evidence/predictability/measure_predictability.py --repo . --ref 5828b4a2 --out /tmp/predictability
```

Windows separator `;`. Expected: identical counts and identical figures to the printed
precision; `summary.json` also records the interpreter and numpy versions, which differ.

## 6. Related

PR #123 and NC-080 to NC-083; Issue #110 decisions A1 to A8 and the deep-engine architecture
research on PR #111 (`docs/roadmap/2026-10-04-deep-engine-architecture-research.md` there,
not yet on `main`: the verdict that linear and shrinkage beat deep models on short series);
`docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`; ADR-013, ADR-027; NC-012.
