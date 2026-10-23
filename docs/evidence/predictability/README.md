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
(Windows `;`) from the repository root. Outputs `results.tsv`, `summary.json`.

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
component) are written to `rows.tsv` so a later model is scored on identical, citable rows;
the effective training window is printed, since `level`, `log_age` and `last_inc` need
history and the first weeks drop out; the archive walk and as-of lookup are imported from
`../persistence-band/measure_persistence_band.py`, so there is one definition of each.

## 3. Results

To be appended by the run, with the commit that produced them. Empty on purpose until then.

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
