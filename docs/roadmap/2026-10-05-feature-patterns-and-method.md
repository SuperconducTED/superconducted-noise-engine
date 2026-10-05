# Feature patterns and the forecasting method for both targets · as of 2026-10-05

Written 2026-10-05 on the PR #111 branch (`a2f9a0a`, plan of 2026-10-04 plus its A9 as-of
section) against `calibration-data` `09fcc45`. This is a dated document: reconcile it later
by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Basis, unless a row says otherwise: all 1,753
`ibm_fez` snapshot files at `calibration-data` `09fcc45` (2026-05-13 to 2026-10-05), measured
on 2026-10-05 with `scripts/feature_patterns.py` on the lead's laptop. None is registered in
`docs/numerical-claims.md`; the registered measurements are the plan's tasks T1, T12 and T13
on the verification desktop. The method and its formulas are in
`docs/implementations/2026-10-05-feature-pattern-analysis.md`.

Tracking issue: Issue #110. Decision A9 (two targets) is in the plan's 2026-10-05 as-of
section.

## 0. The answer in one paragraph

Every calibrated quantity in the archive, gate errors and `T1`/`T2` alike, behaves as a
slowly drifting level per qubit or coupler, observed through measurement noise that is
large next to the drift. Shrinking the last value toward that level (an EWMA at the gain a
local-level model implies) beats persistence by 12% to 26% in log error at every horizon
from 1 to 16 calibration rounds. In a linear, out-of-time test, no other field (`T1`, `T2`,
readout, `sx`, the other two-qubit gate on the same coupler) and not even the series' own
latest deviation adds anything beyond that level. `T1`/`T2` explain a third to two fifths of how
bad a gate is, and almost nothing of when it changes, so the two targets carry independent
signal. No published paper reports forecast skill against persistence for any of these
quantities, so "the most successful method in the literature" cannot be read off a
leaderboard. Assembled from the forecasting literature, the physics and these
measurements, the method to build is the same for both targets: a global local-level
forecaster in log space with online conformal bands, which every learned model must beat,
and a learned residual on top of it whose value is the open question that stage 1 settles.

## 1. Data and unit

- **Unit: the re-measurement event.** For one series (one field on one qubit or coupler), an
  event is a file in which both the value and the date IBM stamped on it are new. Files that
  only repeat the previous value are not rows.
- **Placeholders are masked.** `gate_error = 1` is IBM's "not calibrated" marker and its
  date is re-stamped when a document is assembled, so it would otherwise count as an event in
  every file.
- **Duplicates were checked over the whole archive before being collapsed.** The `id`, `rx`,
  `x` and `xslow` errors equal `sx` in all 955,344 comparisons; the two directions of a
  coupler carry the same `cz` or `rzz` error in all 617,056 comparisons; `measure` equals
  `readout_error` in all 273,468 qubit records.
- **The event rule was clean.** No stamped date ever went backwards. The only mismatches were
  readout re-measurements that returned the identical value (1,742 for `readout_error`, 187
  for `measure_2`), which are possible because readout is quantized (P7).
- **Missing fields.** `q72`'s `T2` is missing in every file and its `T1` in 36; `T2 > 2 T1`
  in 0.16% of qubit records. `init_error` starts 2026-08-04, `measure_2` 2026-08-07,
  `measure_reset` and `reset_2` 2026-09-02.

## 2. The patterns

### P1. Two clocks: daily rounds, and readout every four hours

| Family | Series | Rounds | Median gap between events (h) | Events per series (median) | Transitions, pooled |
| --- | --- | --- | --- | --- | --- |
| sx | 155 | 135 | 24.9 | 132 | 20,052 |
| cz | 172 | 132 | 25.1 | 131 | 21,920 |
| rzz | 171 | 110 | 25.3 | 110 | 18,039 |
| readout (= measure) | 156 | 596 | 4.5 | 579 | 90,099 |
| measure_2 | 156 | 51 | 24.7 | 51 | 7,769 |
| T1 | 156 | 138 | 24.8 | 130 | 19,907 |
| T2 | 155 | 135 | 24.7 | 134 | 20,471 |
| gamma (ADR-027) | 155 | follows T1 | 24.8 | 130 | 19,862 |
| lambda (ADR-027) | 155 | follows T1, T2 | 24.7 | 134 | 20,554 |

A round is a device-wide burst of events (stamps split where two are more than 15 minutes
apart); in 132 of 135 `sx` rounds at least half the device was re-measured. Gate errors do
**not** have more transitions than `T1`/`T2`: per entity both are about 130 over five months.
Readout is the exception, with about 580. At the moment of a file, the median field is about
12 hours old, and readout about 2.5 hours.

### P2. Every series is a level seen through noise

| Family | Lag-1 autocorrelation of change | q | Kalman EWMA weight | EWMA / persistence, h = 1 | h = 4 | h = 16 | Expanding mean / persistence, h = 1 | Changes larger than 2x |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sx | -0.49 | 0.043 | 0.19 | 0.76 | 0.77 | 0.77 | 0.76 | 5.0% |
| cz | -0.45 | 0.233 | 0.38 | 0.85 | 0.84 | 0.85 | 0.90 | 5.6% |
| rzz | -0.42 | 0.353 | 0.44 | 0.86 | 0.87 | 0.88 | 0.94 | 6.2% |
| readout (= measure) | -0.45 | 0.226 | 0.38 | 0.82 | 0.81 | 0.83 | 1.16 | 9.3% |
| measure_2 | -0.50 | about 0 | n/a | 0.75 | 0.77 | 0.79 | 0.75 | 13.2% |
| T1 | -0.50 | 0.018 | 0.12 | 0.80 | 0.80 | 0.75 | 0.80 | 7.9% |
| T2 | -0.50 | 0.002 | 0.04 | 0.82 | 0.80 | 0.74 | 0.83 | 7.5% |
| gamma | -0.49 | | | | | | 0.80 | 7.8% |
| lambda | -0.50 | | | | | | 0.81 | 11.9% |

All in `log10` units; skill is mean absolute error relative to persistence (below 1 is
better); `q` is the variance of the level's step over the variance of the noise, read from
the lag-1 autocorrelation as `q = -1/rho_1 - 2`; `measure_2`'s `rho_1` is just below -0.5,
which is pure noise around a fixed level. `gamma` and `lambda` move with `T1` and `T2`, as
their formula requires.

What this says:

- **No family is a random walk.** A random walk has `rho_1 = 0`; every family sits between
  -0.42 and -0.50. Most of each change is undone by the next one.
- **The level is very stable for `T1`, `T2` and `sx`** (`q` below 0.05): the expanding mean of
  the whole history is as good as anything simple. **`cz`, `rzz` and readout drift more**
  (`q` about 0.2 to 0.35): a local level (EWMA at weight 0.38 to 0.44) beats the full-history
  mean, and for readout the full-history mean is worse than persistence because the level
  wanders over months.
- **Skill hardly decays with horizon.** Persistence's own error grows slowly (for `sx` from
  0.111 to 0.118 decades between `h = 1` and `h = 16`), so the choice of `h` is about the use
  case, not about where forecasting stops working.
- **Tails are real.** 5% to 13% of changes exceed a factor of two, the largest about two
  decades. Bands must be asymmetric and the point loss robust.

### P3. Nothing else moves the next value (linear, out of time)

Response: the next value's deviation from the target's own EWMA level. Fitted before the 70%
time cut, scored after it.

| Target | Other fields at `t` | Test events | EWMA level / persistence | + own deviation / EWMA level | + other fields / EWMA level |
| --- | --- | --- | --- | --- | --- |
| sx | readout, T1, T2 | 5,823 | 0.757 | 0.999 | 0.999 |
| readout | sx, T1, T2 | 26,659 | 0.817 | 0.994 | 0.994 |
| T1 | sx, readout, T2 | 5,750 | 0.731 | 1.013 | 1.014 |
| T2 | sx, readout, T1 | 5,947 | 0.734 | 1.050 | 1.050 |
| cz | sx, readout, T1, T2 (both qubits), rzz | 6,266 | 0.843 | 0.997 | 1.000 |
| rzz | sx, readout, T1, T2 (both qubits), cz | 5,205 | 0.845 | 0.995 | 1.001 |

The EWMA level alone gets 15% to 27% below persistence on the held-out last 30%; nothing
linear adds more than 0.6%. A separate test on `sx` gave the same answer for the change in
the coherence limit between two `sx` rounds (pull toward the mean alone 0.747 of
persistence, with the coherence change 0.748). This is a linear screen: nonlinear
interactions and rare-event structure are untested, and testing them is stage 1's job (§6).

### P4. T1 and T2 explain which gates are bad, a little, and not when they change

The coherence limit of a gate is the error its own duration would cause under `T1` and `T2`
alone (formula in the implementation doc).

| Gate | Limit / measured error (10%, median, 90%) | Spearman across entities in one file (median) | Pearson of entities' time-mean logs | Pearson within an entity, time means removed |
| --- | --- | --- | --- | --- |
| sx | 0.18, 0.40, 1.02 | 0.16 | 0.32 | 0.09 |
| cz | 0.13, 0.33, 0.71 | 0.24 | 0.35 | 0.05 |
| rzz | 0.15, 0.35, 0.72 | 0.30 | 0.34 | 0.06 |

In the median the limit is a third to two fifths of the reported error, so most of the error
is not decoherence during the gate. Entities with poor coherence tend to have worse gates
(about 0.3 to 0.35 between entities), but an entity's gate error does not follow its own
`T1`/`T2` over time (0.05 to 0.09). Ratios above 1 for `sx` mean the limit is computed from `T1`/`T2` stamped in a different round, so it is a proxy, not a
bound (10.5% of `sx` records sit above 1). **Consequence for A9:** the gate-error target is not the ADR-027 target in disguise;
the two carry largely independent temporal signal.

### P5. Readout is partly shot noise, with a known noise level

`prob_meas0_prep1` and `prob_meas1_prep0` are each a fraction of 4,096 shots (100% of
records), and `readout_error` is their mean whenever both were stamped in the same round
(99.999%). That makes the measurement noise of every readout value computable: the median
standard deviation of one estimate is 0.047 decades. 64% of readout changes are within two
standard deviations of pure shot noise (95% would be under pure noise); the rest are real
movements, up to 48 standard deviations. `prob_meas0_prep1` is the larger of the two in most
records (median ratio 2.1), but it is barely related to the decay expected during readout
(Spearman 0.06).

### P6. No neighbour signal, no device-wide common mode (sx)

Over 132 rounds in which at least 20 qubits were re-measured, the round's mean change explains
1.6% of the variance of `sx` changes. After removing it, the median correlation of changes is
-0.008 for the 176 coupled pairs and -0.008 for 11,364 pairs at least four hops apart. This
matches the physics prior of local, TLS-driven fluctuations in the 2026-10-04 survey (§3
there), and it removes the case for graph models at this stage.

### P7. Faults are states, not events

| Family | Entities ever at `gate_error = 1` | Entries into the placeholder over five months | Entities at 1 in every file |
| --- | --- | --- | --- |
| sx | 3 | 1 | q72 |
| measure | 0 | 0 | |
| measure_2 | 156 | 156 (one device-wide glitch) | |
| cz | 7 | 2 | q27-28, q32-33, q71-72, q72-73 |
| rzz | 13 | 13 | q32-33, q71-72, q72-73, q95-99, q99-115 |

`q102-103` (`cz`) is at 1 in 89% of files. With at most 13 entries per family there is
nothing to learn about when a gate fails; faulty entities are excluded by rule and listed,
and a fault channel is not part of version 1.

### P8. Stage A's device mean drifts

| Device mean | Events | Lag-1 | Expanding mean / persistence | EWMA 0.1 | EWMA 0.3 | EWMA 0.5 |
| --- | --- | --- | --- | --- | --- | --- |
| gamma | 134 | -0.34 | 1.21 | 1.19 | 0.99 | 0.93 |
| lambda | 134 | -0.48 | 0.98 | 0.92 | 0.87 | 0.86 |
| sx | 134 | -0.40 | 1.38 | 1.14 | 0.93 | 0.89 |
| cz | 133 | -0.41 | 0.97 | 0.92 | 0.89 | 0.87 |
| rzz | 116 | -0.11 | 1.87 | 1.46 | 1.17 | 1.05 |
| readout | 601 | -0.42 | 2.23 | 0.85 | 0.85 | 0.87 |

Averaged over the device, the noise partly cancels and what remains is a level that moves
over months (the full-history mean is worse than persistence for four of six). With about
130 scored events, differences of 10% are within noise. The structure a model can use lives
per qubit and per coupler (stage B), as the 2026-10-04 survey predicted.

## 3. What the literature supports

A second survey pass (2026-10-05, 52 sources) looked for what the 2026-10-04 survey did not
cover: forecasting gate and readout errors, the coherence limit, fault events, and 2023 to
2026 methods for short related series. Its identifiers were fetched in that pass; the 16
that carry the recommendation below were resolved again against the arXiv API on 2026-10-05
and every title matched, and the one claim this document takes from beyond an abstract (Hassan and Kaabouch) was
checked against the paper's text.

- **No published result answers "most successful" here.** No paper forecasts gate errors,
  readout errors, `T1` or `T2` of a superconducting cloud device on a time split and reports
  skill against persistence. The closest work evaluates calibration-data policies by
  compiled-circuit fidelity, and its main finding is that pre-processing historical
  calibration data improves fidelity when real-time data is not available (Kurniawan et al.
  2024). That is indirect support for shrinkage, and P2 measures it directly.
- **Correction to the 2026-10-04 survey,** recorded here because that document is append-only:
  the survey pass read Baheri et al. 2022 in full and found MAPE reported on series labelled
  "Fits" with no held-out split, horizon or naive baseline described. It is evidence about the
  data, not of forecast skill. (This reading was not re-done on 2026-10-05; the paper is not
  open access.)
- **Simple global models.** Several popular linear forecasting variants are equivalent to
  unconstrained linear regression, and the closed-form solutions forecast better in 72% of
  test settings (Toner and Darlow 2024). Models trained across many related series are the
  direction the forecasting archive literature points to (Godahewa et al. 2021). Together
  with the 2026-10-04 survey's Zeng et al., Makridakis et al. and Montero-Manso and Hyndman,
  that is the evidence for one shared model across the 155 to 172 series of a family.
- **Foundation models are references, not the engine.** TabPFN-TS (11M parameters) is state
  of the art on covariate-informed benchmarks (Hoo et al. 2025); on cloud data, zero-shot
  foundation models were consistently beaten by simple linear baselines (Toner et al. 2025);
  across 30 datasets they won on 15 and lost to classical methods on others with as few as 21
  to 2,768 training samples (Tan Jerome and Simon 2026). Which regime this archive is in is an
  empirical question, and they need a framework (A4), so they may only appear as external
  references.
- **Bands for a series of about 130 rounds.** Online conformal prediction with decaying step
  sizes keeps a retrospective coverage guarantee for arbitrary sequences and, when the
  distribution is stable, coverage close to the target at every time point (Angelopoulos,
  Barber and Bates 2024). Conformal inference by betting removes the step-size choice
  (Podkopaev et al. 2024). For `h > 1`, optimal `h`-step errors are serially correlated up to
  lag `h - 1` and AcMCP uses that (Wang and Hyndman 2024). All are NumPy-feasible.
- **The coherence limit is citable in pieces.** The amplitude-plus-phase-damping channel in
  `T1`, `T2` and its Pauli form give the process fidelity (Ghosh, Fowler and Geller 2012);
  average from process fidelity is the Horodecki formula Nielsen re-proves (Nielsen 2002);
  Abad et al. 2022 give the first-order multi-qubit form. No source prints the closed form
  verbatim, and no source measures how far Heron-class gates sit above it; P4 now does.
- **Physics of the noise.** TLS dynamics destabilize qubit lifetimes on hour timescales, and
  a radiation impact can make several TLSs jump at once (Thorbeck et al. 2023). At a daily
  re-measurement this aliases into noise around a level, which is what P2 shows.
- **Related work the project should know.** Hassan and Kaabouch 2026 is an ANFIS framework
  validated on `ibm_fez` (and a second Heron r2). Their text notes that one non-operational
  qubit reported the 1.0 sentinel and inflated the mean single-qubit gate error by about 25
  times, so they report medians. It is a bug-versus-noise classifier, not a noise forecaster,
  but it is an ANFIS paper on the same backend.

## 4. The recommended method, for both targets

This is a recommendation. Decisions A1 to A9 stand as written in the plan until the lead
decides otherwise.

**The forecaster every model must beat (references R0 to R3).**

| Ref | Forecast of `z_{k+h}` (`log10` of the target) | Parameters |
| --- | --- | --- |
| R0 | Persistence, `z_k` | 0 |
| R1 | Expanding mean of the entity's history | 0 |
| R2 | **Global local-level (Kalman) forecaster**: EWMA with one gain per family, shared by every qubit or coupler, gain fitted on the training portion | 1 per family |
| R3 | For `sx`, `cz`, `rzz`: R2 plus the coherence limit at `t` as a covariate (between-entity information, P4) | 2 to 3 per family |

R2 is the core. P2 says it is the model the data look like, and it costs one parameter. Two
refinements are cheap and grounded in measured facts:

- **Readout with a known noise variance.** For readout the observation noise of each value is
  computable from `p01`, `p10` and 4,096 shots (P5), so the Kalman filter can use that
  variance per event instead of a constant. This is the one place where a physics fact gives
  a model something the data alone do not.
- **Robust updates.** With 5% to 13% of changes above a factor of two (P2), a Huber or
  Student-t observation step keeps one outlier from dragging the level.

**Target 1, gate errors.** `log10` of `sx`, `cz`, `rzz`, readout and `measure_2` errors,
per entity, placeholders masked and permanently faulty entities excluded (P7), forecast `h`
rounds of that family ahead.

**Target 2, ADR-027.** Forecast the entity's `log` rates `log(1/T1)` and `log(1/T2)` with
the same machinery, then apply ADR-027's formula, with the `T2 <= 2 T1` parameterization the
2026-10-04 survey recommends (§2.4 there). `gamma` and `lambda` then inherit the band through
the monotone map.

**The learned part (the third engine, A1 and A7).** A NumPy MLP that predicts the
**deviation from R2's level**, `z_{k+h} - L_k`, not the raw value. Candidate inputs at `t`:
the entity's level and deviation, its recent volatility, the age of every field, the
levels and deviations of the other families on the same qubit or both qubits of a coupler,
and the coherence-limit ratio. Stage 1's permutation importance (single and grouped) on this
residual target is the decisive experiment: P3 found no linear signal, so either stage 1
finds a nonlinear one, or the engine reduces to R2 with a band. Both are results, and the
second is what the 2026-10-04 survey predicted for stage A.

**Bands.** Asymmetric scores in `log10` space; split conformal as the control, online
conformal with decaying step sizes and conformal by betting as the candidates, AcMCP when
`h > 1`. One wrapper for every engine, which also settles the plan's §1.1 fairness question.

**Sample unit.** Per entity (stage B) carries the structure (P2, P8); a device-wide number
for stage A can be produced by averaging per-entity forecasts. Changing the order of stages
is A3's to decide.

## 5. One evaluation protocol for both targets

Written once so that the performance comparison the lead asked for is like for like.

1. **Rows:** re-measurement events of the target family, per entity, placeholders masked,
   permanently faulty entities (P7) excluded and listed.
2. **Split by time, with cut dates written down before any run:** training, then a
   calibration slice for the bands, then test. No entity's future enters its own past.
3. **Horizons in rounds of the target family:** `h = 1, 4, 16` for the daily families. For
   readout, `h = 6` is about one day, so it is reported alongside.
4. **Point error:** mean absolute error in `log10`, reported against R0 and against R2.
5. **Band:** coverage on test with its binomial interval, the interval score, and the median
   width, per family; coverage also on change events only (the 2026-10-04 survey's
   zero-width warning).
6. **Test:** paired Wilcoxon signed-rank over entities (each entity's mean error), at
   alpha = 0.05, since events of one entity are not independent.

## 6. The model-building steps, to walk through together

These are tasks with gates, not runs (lead's rule of 2026-10-04). Each starts when the lead
says so.

| Step | What | Gate (done when) |
| --- | --- | --- |
| M0 | Ratify the protocol (§5): cut dates, horizons, alpha, which references are mandatory | Written in the decisions register by the lead |
| M1 | Event-table builder from the cache: one row per event with the features at `t` and the target at `t + h`, both targets | Tests pinning the event rule and the no-leak alignment; table hash recorded |
| M2 | References R0 to R3, including the readout Kalman with shot-noise variance | Table of point errors under §5 |
| M3 | Bands on R2: split, decaying-step, betting, AcMCP | Coverage and interval-score table under §5 |
| M4 | Stage 1 (plan T3 and T5): NumPy MLP on the residual target with all candidates; permutation importance, single and grouped | Ranking with its spread over shuffles |
| M5 | Feature engineering `F*` (plan T6) | Every kept, dropped or transformed feature justified by M4 |
| M6 | Stage 2 (plan T7): residual MLP within the parameter budget | Point and band results against R2, both targets |
| M7 | The performance comparison across targets and engines | Findings document with the paired tests |
| M8 | Re-run on the verification desktop | Numerical-claims rows |

## 7. This recommendation is wrong if

- stage 1 finds features with out-of-time skill beyond R2 (then the learned residual earns
  its place, which is the good outcome for the third engine);
- the local-level gain fitted on the training portion differs materially from the one on the
  whole archive (then the level dynamics are not stationary and the gain must adapt);
- conformal coverage on change events falls well below target (then the band is covering
  repeats, not changes);
- a device-wide regime change appears in the test period, such as a change in IBM's
  calibration procedure (P8's drift is the warning sign).

## 8. Sources

Resolved against the arXiv API on 2026-10-05 (title matched):

| Source | Identifier | Used for |
| --- | --- | --- |
| Kurniawan et al., On the use of calibration data in error-aware compilation (2024) | arXiv:2407.21462 | Historical calibration data beats latest for compilation |
| Toner and Darlow, An Analysis of Linear Time Series Forecasting Models (2024) | arXiv:2403.14587 | Linear variants equal OLS; closed form better in 72% |
| Godahewa et al., Monash Time Series Forecasting Archive (2021) | arXiv:2105.06643 | Global models across related series |
| Hoo et al., From Tables to Time: TabPFN-TS (2025) | arXiv:2501.02945 | External reference only |
| Toner et al., Zero-Shot Time Series Foundation Models on Cloud Data (2025) | arXiv:2502.12944 | Foundation models beaten by linear baselines |
| Tan Jerome and Simon, When Do Foundation Models Pay Off? (2026) | arXiv:2607.04919 | Foundation models win on 15 of 30 datasets |
| Angelopoulos, Barber and Bates, Online Conformal Prediction with Decaying Step Sizes (2024) | arXiv:2402.01139 | Band candidate |
| Podkopaev, Xu and Lee, Adaptive Conformal Inference by Betting (2024) | arXiv:2412.19318 | Band candidate, no step size |
| Wang and Hyndman, Online Conformal Inference for Multi-Step Forecasting (2024) | arXiv:2410.13115 | Bands for `h > 1` |
| Ghosh, Fowler and Geller, Surface Code with Decoherence (2012) | arXiv:1210.5799 | Damping channel and its process fidelity |
| Nielsen, A Simple Formula for the Average Gate Fidelity (2002) | arXiv:quant-ph/0205035 | Average fidelity from entanglement fidelity |
| Abad et al., Universal Fidelity Reduction from Weak Dissipation (2022) | arXiv:2110.15883 | First-order multi-qubit coherence limit |
| Thorbeck et al., TLS Dynamics Due to Background Ionizing Radiation (2023) | arXiv:2210.04780 | Hour-scale TLS dynamics |
| Klimov et al., Optimizing Quantum Gates towards the Scale of Logical Qubits (2024) | arXiv:2308.02321 | Physics error model with few weights (structure only) |
| Smith et al., Fast Fingerprinting of Cloud-based NISQ Quantum Computers (2022) | arXiv:2211.07880 | Gate and readout errors noisier than frequency |
| Hassan and Kaabouch, Physics-Informed Neuro-Fuzzy Framework for Quantum Error Attribution (2026) | arXiv:2602.21253 | Related ANFIS work on `ibm_fez`; the 1.0 sentinel |

Cited from the survey pass without re-resolution: Baheri et al., Quantum Noise in the Flow of
Time (IOLTS 2022), doi:10.1109/IOLTS56730.2022.9897404. Everything else rests on the
2026-10-04 survey (`docs/roadmap/2026-10-04-deep-engine-architecture-research.md`, §8).
Project sources: the plan of 2026-10-04 with its A9 section; ADR-027 and
`src/superconducted/training/targets.py`; `scripts/feature_patterns.py`.
