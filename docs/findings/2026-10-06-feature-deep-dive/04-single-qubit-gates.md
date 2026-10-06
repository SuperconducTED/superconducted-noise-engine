# 04 · Single-qubit gates: sx and its aliases, xslow, rz

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: reconcile it
later by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Ref: `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`. Basis: all 1,760 `ibm_fez` snapshot files
(2026-05-13T12:13:22Z to 2026-10-06T02:57:42Z) read through the cache of `01-data-layer.md`;
156 qubits; 155 `sx` series with 20,207 re-measurement events after masking placeholders
(`q72` has none); 18,301 of those events matched to a `T1` and a `T2` event of the same qubit.
Measured on 2026-10-06 on the lead's laptop (Windows 11, CPython 3.12.10, numpy 2.4.4,
scipy 1.17.1), not on the verification desktop. Nothing here is registered in
`docs/numerical-claims.md`. This is data understanding only: it makes no modelling or
strategic decision, and decisions A1 to A9 and the advisor's answers remain open.

Scripts: `analysis/gates_1q/`. Results: `results/gates_1q/`. Every number below is a field of
one of these files, cited in brackets by a short label and the JSON path:

| Label | File |
| --- | --- |
| A | `results/gates_1q/aliases_and_schema.json` |
| P | `results/gates_1q/sx_profile.json` |
| T | `results/gates_1q/sx_temporal.json` |
| V | `results/gates_1q/sx_variogram.json` |
| C | `results/gates_1q/sx_coherence.json` |
| S | `results/gates_1q/sx_spatial.json` |
| DL | `results/data-layer/profile.json` |
| DI | `results/data-layer/identities.json` |

Figures quoted from older documents name their path and their (older) ref.

## 0. Summary

- **One measured value, five names.** `x`, `id`, `rx` and `xslow` report `sx`'s error in
  every record (0 value mismatches in 274,560 records each, 136,032 for `xslow`) [DI
  checks]. Every one of the 979, 645, 374 and 310 date mismatches sits inside a placeholder
  record of `q17`, `q72` or `q149`, and the offset is exactly one second (`id`, `rx` earlier;
  `x`, `xslow` later); outside placeholders there are 0 [A aliases.*]. After masking, all 155
  series of each alias are identical to `sx`'s [A aliases.*.series_identical_to_sx_after_masking].
  IBM's documentation says the benchmarking sequence includes SX, ID and X and their errors
  are assumed equal (§1).
- **`xslow` is a 1,000 ns instruction whose error is copied from the 24 ns `sx`.** Its
  coherence limit alone exceeds the error it reports in 99.67% of 6,033 matched events
  (median 17.2 times; with `T2 = 2 T1`, no pure dephasing at all, still 99.27% and 8.9
  times) [C xslow_coherence_floor.events_inside_xslow_windows]. It is present in 135 files
  (2026-05-14 to 05-29) and in 737 files from 2026-09-10T16:56:21Z [A xslow.presence_runs].
  No fetched source says what it is for.
- **`rz` is constant** (error 0, length 0 in all 274,560 records) [A constants], the virtual Z
  of McKay et al. 2017. **`rx`** has a record for every qubit in every file yet is absent from
  the target operations, `basis_gates`, the configuration's gate list and
  `supported_instructions` in every archived file [A rx].
- **`sx` error per event:** median 3.10e-4, 1% 1.42e-4, 99% 2.54e-3, maximum 1.71e-2; 4.9% of
  events exceed 1e-3 and 7 exceed 1e-2 (n = 20,207) [P distribution]. 74% of the variance of
  log10 error lies between qubits [P distribution.between_share].
- **Per-qubit levels span a factor of 34.5 and are stable**: the rank correlation of qubit
  medians between the record's two halves is 0.97 (n = 155), and 86% of qubits stay in the
  same tercile [P distribution, stability].
- **The non-persistent component is large and memoryless at the event spacing.** Lag-1
  autocorrelation of log changes -0.49 (95% CI -0.50 to -0.48), lag-2 -0.003 (CI -0.023 to
  0.018) [V autocorrelation]. Read as "level plus a component", the component's size is 0.111
  decades (a factor of 1.29) and it carries 98% of the variance of one-step changes.
- **Variogram nearly flat from 7 h to the longest lags (up to 3,624 h).** The daily-lag
  semivariance is 0.81 of the long-lag value (robust estimator 0.83; per-qubit median 0.96), and
  the 6 to 9 h lag is not lower than the daily lag (ratio 0.97, CI 0.73 to 1.29) [V
  bins_bootstrap, per_entity]. Whatever the component is, it decorrelates faster than the
  shortest observable lag (6.3 h) or it is not a fluctuation at all; the variogram cannot tell
  which.
- **Tails are one-sided.** 1.9% of events sit more than a factor of two above their running
  level, 0.28% more than a factor of two below; 94% of such upward episodes last one event
  [P changes.residual_from_running_level; T spikes]. Spikes do not cluster by round (variance
  3.20 against 2.90 for independence) or between coupled qubits (ratio 1.01) [T spikes.per_round;
  S tests.same_round_spike_cooccurrence].
- **Positive evidence that part of the component is a real fluctuation.** Within a qubit, the
  `sx` deviation from its level moves against the `T1` deviation measured in the same round
  (rank correlation -0.062; a null that pairs each event with a different round gives
  0.002 +- 0.008, extremes -0.0145 and 0.014) [C within_qubits.T1]. The coupling is -0.096
  when the two stamps are at most 1 h apart and -0.024 when 1 to 6 h apart (difference CI
  -0.102 to -0.046), and the near-far ordering holds in every month [C within_by_stamp_offset].
- **At `sx` spikes, `T1` dips more often than chance**: 16.7% of spikes coincide with a `T1` at
  least 1.5 times below its level, against 10.9% (at most 14.0%) under the shifted null; for
  `T2` the excess stays inside the null range [C coincidence]. Yet the coherence limit accounts
  for a median 0.5% of a spike's excess error (13.6% at spikes with a `T1` dip) [C
  coincidence.excess_accounted_by_coh_limit].
- **Coherence limit:** median 0.40 of the reported error (10% 0.18, 90% 0.99); 9.8% of
  matched events sit above 1 [C ratio]. Between qubits, `sx` follows `T1` (Spearman -0.43, CI
  -0.56 to -0.29) more than the coherence limit (0.20, CI 0.02 to 0.36) or `T2` (-0.16)
  [C between_qubits].
- **No device-wide drift or regime change**: Theil-Sen slope of the device level 0.0008
  decades per 30 days (CI -0.0016 to 0.0029), no device change point (p = 0.24); the five known
  device-wide dates do not stand out against placebo dates, 21% to 23% of which reach
  p < 0.01 in the same test [T device, known_dates]. 11 of 155 qubits show a significant
  level change (block permutation, BH 0.05) [T entity_changepoints].
- **No value seasonality**: Kruskal-Wallis by UTC hour p = 0.73 and by weekday p = 0.50,
  effect sizes below 0.0003 [T seasonality].
- **Spatial**: no autocorrelation on the coupling graph (Moran's I p = 0.56); degree-3 qubits
  have lower error (median 2.69e-4 against 3.22e-4 for degree 2; Kruskal-Wallis p = 0.003,
  under the Bonferroni level 0.005 for 10 tests; within the long rows alone p = 0.013)
  [S tests].

## 1. The fields and how IBM produces them

| Field | Entities | Unit | Values at this ref | Event rule | How it is produced |
| --- | --- | --- | --- | --- | --- |
| `g1.sx.gate_error` | 156 | none | 7.2e-5 to 1.7e-2 over events; placeholder 1 | measured, placeholders masked | randomized benchmarking (RB), simultaneous on all qubits (IBM documentation) |
| `g1.sx.gate_length` | 156 | ns | 24 in all 274,560 records [A constants] | value only | configuration-like |
| `g1.x.*`, `g1.id.*`, `g1.rx.*` | 156 | as `sx` | copies of `sx` (§0) | as `sx` | not measured separately |
| `g1.xslow.gate_error` | 156 | none | copies of `sx` in 136,032 records | measured | not measured separately |
| `g1.xslow.gate_length` | 156 | ns | 1,000 in all 136,032 records [A constants] | value only | configuration-like |
| `g1.rz.gate_error`, `g1.rz.gate_length` | 156 | none, ns | 0 and 0 in all 274,560 records [A constants] | value only | virtual gate |

**What IBM states (fetched 2026-10-06).** IBM's "View backend details" page defines the
single-qubit fields as follows (paraphrased): the SX error is derived from the average gate
fidelity of the SX gate from RB, measured simultaneously on all qubits; the ID, SX, X and RX
errors are errors of the finite-duration discrete one-qubit gates from RB; the RB sequence
contains SX, ID and X, and their errors are assumed to be the same; `T2` is reported from a
Hahn echo; properties update when the calibration sequence completes; RX is listed among the
fractional gates. So the equality of the `sx`, `id` and `x` errors is a documented convention,
which the archive confirms record by record. The equality of `rx` and `xslow` with `sx` is not
stated in any fetched source: it is an archive observation, true in every record (§0, §6).

**Randomized benchmarking.** RB applies random sequences of gates that compose to the identity
and fits the decay of the survival probability with sequence length; Magesan, Gambetta and
Emerson (2011) prove that, under conditions they state, it gives an efficient and reliable
estimate of an average error rate of a gate set under time- and gate-dependent noise.
Simultaneous RB benchmarks each qubit alone and all together, and the difference measures
cross-talk (Gambetta et al. 2012). By that construction, an error measured simultaneously on all
qubits includes any degradation from driving the neighbours at the same time; an isolated RB
would not. The documents carry no isolated single-qubit RB field, so this archive cannot
separate the two.

**From the decay to a per-gate number.** Qiskit Experiments (version 0.14.2 documentation)
fits `a alpha^m + b`, converts `alpha` to an error per Clifford of `(1 - alpha)/2` for one
qubit, and divides it among the basis gates with an assumed error ratio (by default `x` and
`sx` 1, `rz` 0); its own text warns that such an error per gate is not necessarily the true
gate error. Whether IBM's production pipeline uses this code or ratio is not stated in any
fetched source; the equality of `x` and `sx` in the archive is consistent with an equal-ratio
convention but does not prove it. Two further caveats on what the number means:
Proctor et al. (2017) show that the RB decay rate `r` is not, in general, the average gate
infidelity of any physical representation of the gates; Epstein et al. (2014) find that under
realistic error models RB still estimates the average error rate within a factor of two in
almost all cases. Read `gate_error` as an RB-derived error rate that approximates an average
gate infidelity.

**How precise is one value?** The literature shows RB can be made precise: confidence bounds
are set by the number and length of sequences (Wallman and Flammia 2014); the number of
sequences needed scales favourably with the error rate (Helsen et al. 2019); with specific
design choices RB gives multiplicative precision (Harper et al. 2019); and only a small number
of trials is needed when the fidelity measurements have small standard error (Epstein et al.
2014). None of these gives a number for IBM's production settings, because IBM's sequence
lengths, sequence counts and shots are not published in any fetched source. **A bound on the
estimation noise of an archived `sx` value therefore cannot be derived from the literature**;
§4 says what the archive itself can and cannot add.

**Stamps.** Every `sx` stamp is a whole second (100% of 272,585 measured and 1,975
placeholder records) [A stamps]. No measured stamp is later than its document's
`last_update_date` (0 records); at the document's time the median `sx` value is 12.4 h old
(10% 1.9 h, 90% 23.5 h, maximum 334.9 h) [A stamps.measured_stamp_age_at_file_h_q_...].
Placeholder records are stamped after the document's date in all 1,975 cases, by 7 s to
44,734 s (median 287 s) [A stamps.placeholder_stamp_after_file_date_*]: their stamp is the
assembly time, not a measurement time (`01-data-layer.md` §4).

**What the alias stamps reveal about assembly (an inference).** In placeholder records the
`id` stamp is 1 s earlier than `sx`'s in 49.6% of 1,975 records, `rx` 1 s earlier in 32.7%,
`x` 1 s later in 18.9%, and `xslow` 1 s later in 33.9% of its 915 [A aliases.*]; the offset is
never anything but one second. The reading that fits: when a document is assembled, each
placeholder record is written separately and stamped with the clock at one-second
resolution, and a second boundary sometimes falls between the writes of two records. If the
clock phase is uniform, each share equals the mean time between the two writes in seconds,
which would put the writes in the order `id`, `rx`, `sx`, `x`, `xslow` within about a second.
For measured records the five stamps are identical, so they are copies of one measurement
stamp, not separate writes of separate measurements. This is an inference from the data;
no fetched source describes IBM's assembly.

**`xslow` (fetched 2026-10-06).** qiskit-ibm-runtime 0.50.0 (released 2026-09-24) added
`XSlowGate`, described only as representing the hardware-native `xslow` instruction that the
transpiler passes through unchanged when the backend target includes it; the API page adds
nothing on its unitary, duration or purpose. GitHub issue Qiskit/qiskit-ibm-runtime#3311
(opened 2026-09-10, open) reports that `xslow` cannot be exported to OpenQASM 3 and loses its
class in QPY. In the archive, the configuration defines it as `gate xslow q0 {}`, an empty
body (no unitary) [A xslow.configuration_gate_versions]. **What `xslow` is for is not stated
in any fetched source**, and neither is the equality of its error with `sx`'s; this document
does not guess beyond "a 1,000 ns hardware-native single-qubit instruction whose error field
copies `sx`".

**`rz`.** McKay et al. (2017, existing survey) describe zero-duration "virtual" Z gates
generated from the phase of the drive; the archive's 0 error and 0 length are that. Its date
is re-stamped at assembly (share 1.0 of records equal to the file date, `01-data-layer.md` §3),
so it carries no information.

## 2. Profiles (units, ranges, distribution and tails, missingness, cadence)

**Units and ranges.** `gate_error` is dimensionless; lengths are in ns. Over the 20,207
masked events of `sx` [P distribution.value_q]:

| Quantile | 0 | 0.1% | 1% | 5% | 10% | 25% | 50% | 75% | 90% | 95% | 99% | 99.9% | 100% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sx` error (e-4) | 0.72 | 1.08 | 1.42 | 1.76 | 1.97 | 2.41 | 3.10 | 4.18 | 6.15 | 9.80 | 25.4 | 68.8 | 170.6 |

The record-level quantiles of `01-data-layer.md` (median 0.000312; 1% 0.000143; 99% 0.00705)
include placeholder records and repeat each value until it is re-measured, so they differ
from the event quantiles above.

**Tails.** Shares of events above 1e-3: 4.88%; above 2e-3: 1.73%; above 5e-3: 0.48%; above
1e-2: 0.035% (7 events); none above 0.1 [P distribution.share_above, count_above]. The
largest event (0.0171) belongs to `q149` [P distribution.max_event_*]. Relative to each
qubit's own median, residuals run from -0.63 to +1.50 decades; the 1% and 99% quantiles are
-0.24 and +0.42, the 0.1% and 99.9% -0.45 and +0.88 [P
distribution.residual_from_entity_median_log10_q].
The tail is a within-qubit upward tail: 2.19% of events lie more than a factor of two above
the qubit median against 0.57% more than a factor of two below, and 0.074% lie more than a
decade above while none lie a decade below.

**Between and within qubits.** Of the variance of log10 error (0.0581), 0.0432 lies between
qubit means and 0.0149 within qubits (between share 0.744) [P distribution]. Qubit medians
range from 1.54e-4 (`q131`) to 5.31e-3 (`q27`), a factor of 34.5; their median is 3.00e-4 and
the median absolute deviation of their logs 0.093 decades. Best five: `q131`, `q135`, `q132`,
`q81`, `q155` (1.54e-4 to 1.94e-4). Worst five: `q27` 5.31e-3, `q11` 1.99e-3, `q0` 1.93e-3,
`q149` 1.38e-3, `q24` 1.30e-3. A qubit's interquartile range in log10 has median 0.118
decades (10% 0.090, 90% 0.163, maximum 0.642) [P distribution].

**Stability of the levels.** Splitting at 2026-07-25 (the calendar midpoint), the Spearman
correlation of qubit medians between halves is 0.972 (n = 155), 85.8% of qubits keep their
tercile, and the median shift is 0.017 decades. Month to month the rank correlation is 0.955
(May to June), 0.967, 0.962 and 0.956 (August to September); May against September 0.930
(n = 154; October has fewer than 5 events per qubit and is not compared) [P stability]. The
device median of qubit monthly medians: 3.14e-4 (May), 2.83e-4, 2.87e-4, 2.96e-4, 3.07e-4
(September) [P stability.device_median_of_entity_monthly_medians].

**Missingness.** Inside its lifetime `sx` is present for every qubit in every file
(present share 1.0, `01-data-layer.md` §3). The only gaps are placeholders, 1,975 records:
`q72` in all 1,760 files, `q17` in 209, `q149` in 6 [A placeholders.sx]; §6 treats them.
`xslow` is present in 872 of the 1,760 files, for every qubit or for none [A xslow]; its
"present in lifetime" share of 0.498 in `01-data-layer.md` is the share of files between its
first and last appearance, so it reflects the gap between its two runs, not missing records.

**Cadence.** Events per series: minimum 68, 10% 128, median 132, maximum 133 [P
cadence.events_per_series_q]. The two low series are `q149` (68 events, longest gap 252.6 h
from 2026-07-07) and `q17` (78 events, longest gap 857.0 h from 2026-06-07, which spans its
second placeholder episode) [P cadence.fewest_events]. The gap between events: minimum 6.31
h, 10% 19.95 h, median 24.93 h, 90% 33.2 h, 99% 76.5 h [P cadence.gap_h_q]. Event stamps
cluster into 135 rounds; 132 rounds cover at least half the device and hold 99.96% of events;
round starts are a median 24.9 h apart (minimum 6.3 h, maximum 65.8 h) [P cadence.rounds].
Round starts fall at every hour of the day, most often at 22 UTC (15 of 135) and 21 UTC (11),
and on every weekday (15 to 23 per weekday) [P cadence.rounds.round_starts_by_*]. The first
event of a series can be stamped before the record starts (the first file carries values
measured days earlier, for example 2026-05-05 for `q54`) [P cadence.fewest_events,
longest_gaps].

**Does the archive's coverage change the cadence?** Barely, for this daily family. Median
events per qubit per month: 22 in May (from 05-13), 26, 27, 25, 29 in September, 4 in October
(to 10-06) [P stability.events_per_entity_by_month_median]. The median gap is 24.5 to 25.9 h
in every month; May has more short gaps (10% quantile 10.0 h against 19.7 to 24.6 h in later
months) and August more long ones (90% quantile 52.9 h) [P cadence.gap_h_by_month_of_later_event].
The historical backfill from 2026-08 (`01-data-layer.md` §6) therefore does not change the
`sx` event rate the way it would for the 4-hourly readout family.

**Changes between consecutive events.** 20,052 transitions; median absolute change 0.082
decades, 90% 0.232, 99% 0.551, maximum 1.58; 5.05% exceed a factor of two [P changes].

## 3. Temporal structure (including change points and seasonality)

**Device level.** The device series is, per round covering at least half the device, the
median over qubits of `log10(sx)` minus each qubit's median (132 rounds, 2026-05-13 to
10-05). It ranges from -0.045 to +0.067 decades (10% -0.020, 90% +0.025) [T
device.device_round_median_q]. Its Theil-Sen slope is 0.0008 decades per 30 days (95% CI
-0.0016 to 0.0029) and its Spearman correlation with time 0.026 (p = 0.77) [T device]. The CI
assumes independent rounds, which the level's slow wandering violates, so it is optimistic;
even so, a drift of the size of one qubit's typical scatter (0.11 decades, §4) over five
months is excluded.

**Device change points.** A rank CUSUM test (the statistic of Pettitt's test) with block
permutations of 7 rounds finds no change point in the whole device series (K = 675.5,
p = 0.24, best split 2026-05-30); binary segmentation therefore stopped after one test [T
device.binary_segmentation].

**Known device-wide dates.** Per qubit, median of the 14 days after against the 14 days
before, paired Wilcoxon over qubits [T known_dates]:

| Date | What changed (from `01-data-layer.md`) | Qubits | Median shift (decades) | Share up | p |
| --- | --- | --- | --- | --- | --- |
| 2026-06-08T18:56:28Z | readout length 1,560 to 1,700 ns, `measure.threshold` appears | 154 | -0.0148 | 0.344 | 6.5e-6 |
| 2026-07-30T21:09:17Z | readout length 1,700 to 1,660 ns | 155 | -0.0045 | 0.452 | 0.33 |
| 2026-08-07T03:21:59Z | `measure_2` appears | 155 | -0.0005 | 0.497 | 0.52 |
| 2026-09-02T04:56:24Z | `measure_reset`, `reset_2` appear | 155 | +0.0026 | 0.529 | 0.55 |
| 2026-09-10T16:56:21Z | `xslow` records return | 155 | +0.0093 | 0.581 | 0.0073 |

Two dates pass a Bonferroni level of 0.01. **The placebo says they should not be read as
effects**: the same test on every day of the record more than 14 days from a known date (31
dates) gives p < 0.01 on 22.6% of them, and on every day more than 3 days away (95 dates)
21.1%, with placebo shifts up to 0.034 to 0.043 decades [T known_dates.placebo]. A slowly
wandering level makes a 14-day before-and-after comparison fire often at arbitrary dates; the
known-date shifts (at most 0.015 decades) are inside the placebo range. Conclusion:
no device-wide `sx` change is attributable to these configuration events.

**Per-qubit change points.** The same rank CUSUM per qubit (999 permutations): 19 qubits
significant at BH 0.05 under an exchangeable null, 11 under block permutations of 5 events
(which keep short-range dependence) [T entity_changepoints]. Among the 11, the median absolute
shift is 0.091 decades (minimum 0.040, maximum 0.64) and 64% are upward. A significant
statistic means "not exchangeable": a step or a slow drift, which this test cannot tell
apart. The largest: `q102` +0.64 decades at 2026-07-19, `q126` +0.45 at 2026-06-07, `q43`
-0.31 at 2026-06-06, `q127` +0.25 at 2026-09-01, `q0` -0.10 at 2026-08-05. Three of the 11
fall within 3 days of 2026-06-08 (`q126`, `q43`, `q108`), where 0.43 would be expected in any
one 6-day window if change dates were uniform over the 152.6-day record [T
entity_changepoints.significant_block5_within_3_days_of_known_date,
expected_within_any_one_6_day_window_if_uniform]. This is a post hoc look at 5 windows and 3
qubits, so it is a lead for `06-device-time-topology.md` (which owns change points across
families), not a finding. `q102` is an endpoint of coupler 102-103, which `01-data-layer.md`
lists at 88 ns for both two-qubit gates; any link to that coupler belongs to
`05-two-qubit-gates-couplings.md` and `07-cross-feature-dependency.md`.

**Outlier episodes (spikes).** A spike is an event more than a factor of two above its running
level (median of up to 5 events each side, the event itself excluded) [T spikes]:

- 393 upward spikes (rate 1.95% of 20,207 events) against 56 downward ones;
- 129 of 155 qubits have at least one; per qubit median 2, 90% 5.6, maximum 13 (`q15`, `q49`,
  `q96`); the top 10% of qubits hold 35% of spikes; `q149` has 11 in only 68 events;
- 366 episodes, 343 of one event, 21 of two, 2 of four (93.7% single events): a spike is
  almost always gone at the next re-measurement, about a day later;
- the spike rate is 1.0% in May and 2.0% to 2.2% from June to September (2.8% in the six days of
  October, 606 events) [T spikes.rate_by_month]. Whether May's lower rate is real or an effect of
  May's extra short-gap rounds (§2) is open (§9);
- per round (133 rounds covering at least half the device, counting first events), spikes per
  round have mean 2.94 and variance 3.20, against 2.90 for independent qubits; the maximum is 7
  [T spikes.per_round]. There are no device-wide spike rounds.

**Seasonality of the values.** The residual from the running level, grouped by the UTC hour
(3-hour bins) and the weekday of its stamp, shows nothing: Kruskal-Wallis H = 4.43, p = 0.73,
epsilon squared 0.00022 (hours); H = 5.32, p = 0.50, epsilon squared 0.00026 (weekdays);
median residuals within +-0.004 decades in every bin; spike rate by hour chi-square p = 0.89,
by weekday p = 0.76 (n = 20,207) [T seasonality]. Hour of stamp is confounded with "which
round" (rounds start at different hours), so this tests the hour and the round together.
Stamp cadence (when IBM calibrates, §2) is a separate matter from the values: rounds peak in
the evening UTC, the values do not change with it.

## 4. The non-persistent component (variograms and what they can and cannot tell)

**The shared variogram** (`ddload.variogram`, log10 `sx`, all 155 series) [V variogram_all]:

| Lag bin (h) | 6 to 9 | 9 to 12 | 12 to 18 | 18 to 30 | 30 to 42 | 42 to 54 | 54 to 84 | 84 to 132 | 132 to 204 | 204 to 372 | 372 to 744 | 744 to 1,488 | 1,488 to 3,624 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pairs | 456 | 298 | 749 | 15,843 | 2,988 | 14,218 | 20,187 | 34,086 | 50,960 | 110,933 | 226,007 | 361,464 | 472,567 |
| Semivariance (e-3 decades^2) | 12.0 | 11.3 | 13.0 | 12.4 | 12.5 | 12.9 | 12.7 | 13.2 | 13.4 | 13.8 | 14.6 | 14.9 | 15.6 |
| Robust (e-3) | 7.6 | 8.8 | 8.1 | 8.5 | 8.8 | 8.9 | 8.8 | 9.0 | 9.3 | 9.5 | 9.9 | 10.0 | 10.5 |

No pair is closer than 6 h (the minimum event gap is 6.31 h). With a bootstrap over qubits
(2,000 resamples) [V bins_bootstrap]:

| Ratio | Plain (95% CI) | Robust (95% CI) |
| --- | --- | --- |
| 18 to 30 h over 744 to 3,624 h | 0.81 (0.70 to 0.91) | 0.83 (0.76 to 0.89) |
| 6 to 9 h over 744 to 3,624 h | 0.78 (0.58 to 1.06) | 0.74 (0.60 to 0.90) |
| 6 to 9 h over 18 to 30 h | 0.97 (0.73 to 1.29) | 0.89 (0.73 to 1.08) |

Per qubit (155 qubits, at least 20 pairs in each range) the daily over long-lag ratio has
median 0.96 (10% 0.63, 90% 1.13); 77% of qubits are at 0.8 or more [V per_entity]. The
pooled ratio is lower than the per-qubit median because pooled sums weight a few qubits with
large long-lag semivariance (up to 0.143 against a per-qubit median of 0.0104 [V
per_entity.long_semivariance_q]); these include the qubits with level changes of §3 (a
reading, not tested separately). Split at 2026-08-01, the daily over long-lag ratio
is 0.83 before and 0.85 after (robust 0.81 and 0.91) [V summary_before_split, summary_from_split]:
the coverage change of August does not alter the picture.

**Reading it with the rules of `01-data-layer.md` §7.** Most of the long-lag semivariance (81%
pooled, 96% for the median qubit) is already present at the daily lag, and nothing measurable
is added between 7 h and 25 h. A slowly drifting level adds the rest over weeks to months.
The nugget is "noise plus anything faster than the shortest lag", and the shortest lag here
is 6.3 h. So the variogram says: whatever the component is, it is either
not a fluctuation or a fluctuation with a correlation time below about 6 h. It cannot say which.

**Change autocorrelations** [V autocorrelation]. Pooled over qubits: lag-1 autocorrelation of
log10 changes -0.490 (CI -0.502 to -0.476), lag-2 -0.003 (CI -0.023 to 0.018), from 2,000
bootstrap resamples of qubits. Under a model "level plus a component with autocorrelation
`phi` from one event to the next", lag-2 over lag-1 estimates `phi`: 0.006 (CI -0.036 to
0.048). The component has no detectable memory at the event spacing (about a day). Read as
"level plus a component uncorrelated between events" (a model-based reading): the component's
variance is 0.0124 decades squared (size 0.111 decades, a factor of 1.29), the level's step per
event 0.0005, and the component carries 97.9% of the variance of one-step changes; the local
level ratio `q` is 0.043 [P changes.local_level_q_from_lag1]. The older-ref figures of
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P2, ref `09fcc45`: lag-1 -0.49,
`q` 0.043) are reproduced at this ref.

**Is its size tied to the qubit's level?** Per qubit, the robust size of changes
(`1.4826 MAD / sqrt(2)`) has median 0.085 decades (10% 0.067, 90% 0.116) [V level_dependence].
Against the qubit's level, Spearman -0.23 (p = 0.004) and a Theil-Sen slope of log size on
log level of -0.13 (CI -0.22 to -0.04); the size from the lag-1 autocovariance gives -0.19
(CI -0.29 to -0.08). The reading rule: constant relative scatter gives slope 0, constant
absolute scatter slope -1. The data sit close to 0: the component is close to multiplicative,
slightly larger in relative terms for better qubits. Both a multiplicatively precise estimate
(Harper et al. 2019 show RB can be designed for that) and a multiplicative physical
fluctuation predict a slope near 0, so this does not attribute the component either way. What
it excludes is a component of fixed absolute size.

**Is it symmetric?** The body is: the quartile (Bowley) skewness of the residual from the
running level is 0.047 and the octile skewness 0.090 [P changes.residual_from_running_level].
The tails are not: 1.95% of events are more than a factor of two above the level and 0.28%
more than a factor of two below; 0.56% are more than half a decade above and none half a
decade below; the 99.9% quantile is +0.87 decades and the 0.1% quantile -0.37. Interpretation:
a near-symmetric core with one-sided upward excursions. A symmetric fit error around a fixed
level would produce symmetric tails; one-sided excursions fit discrete events that make a gate
worse (for example a defect moving into resonance). An RB fit that occasionally fails upward
would also produce them, so this is suggestive, not decisive.

**The one positive discriminator: coupling to `T1` and `T2` in the same round** (details in
§7). `T1`, `T2` and the RB of `sx` are separate experiments. Independent estimation errors in
separate experiments do not correlate. The `sx` deviation correlates with the same-round `T1`
deviation at -0.062 and with `T2` at -0.049, against a shifted null of 0.002 +- 0.008 and
0.002 +- 0.009 [C within_qubits]; the coupling is strongest when the two stamps are within an
hour (-0.096 for `T1`) and weak beyond (-0.024), in every month [C within_by_stamp_offset];
and spikes coincide with `T1` dips beyond the shifted null [C coincidence]. Interpretation:
**at least part of the non-persistent component is a real device fluctuation that `sx` shares
with `T1` and `T2` and that changes on a timescale of hours.** It would be falsified by finding
a shared input of the two analyses (for example an upstream calibration step feeding both
experiments in the same job) that degrades both fits together; such a step would act on the
whole job, so it would not obviously weaken with the stamp separation, but whether a larger
separation also means a separate job is not visible in the data, so this alternative is not
excluded.

**What the data show and do not show about the root question.**

- Shown: a component of size about 0.11 decades that is memoryless from one daily event to the
  next and present at the shortest observable lag; a near-symmetric core with one-sided
  upward tails; no device-wide or neighbour clustering of the excursions; no hour or weekday
  pattern; a small but real same-round coupling to `T1` and `T2` that weakens with time
  between the measurements.
- Not shown: what the bulk of the component is. Its coupling to `T1`/`T2` is a rank
  correlation of -0.05 to -0.10, so most of it is not linked to the coherence fields in the
  data. It may be RB estimation noise, a real fluctuation that `T1`/`T2` do not register (for
  example one that changes the pulse calibration rather than the decay), or a real fluctuation
  that decorrelates within the median 0.9 h between the `T1` and `sx` stamps. The archive cannot
  split these, because (a) nothing faster than 6.3 h is observed; (b) the aliases are copies, so
  no document carries an independent replicate of the same measurement from which a
  within-round noise variance could be read (unlike readout, whose 4,096-shot grid gives one,
  `01-data-layer.md` §5); and (c) IBM's RB settings are unpublished, so no noise floor can be
  computed (§1). This document therefore does not call the component estimation noise.

## 5. Spatial structure

Per-qubit medians, robust change sizes and spike rates against configuration coordinates
(`coords`, one version across all 1,317 files with a configuration [DL config.coords];
columns 1 to 16, rows 1 to 15) and the coupling graph (176 undirected edges, 174 once `q72` is
excluded; degrees: 8 of 1, 100 of 2, 48 of 3) [S]. Ten tests were run; the Bonferroni level
is 0.005.

| Test | Result | p |
| --- | --- | --- |
| Level against column (Spearman) | 0.072 | 0.38 |
| Level against row (Spearman) | -0.206 | 0.010 |
| Level by degree (Kruskal-Wallis) | medians 3.28e-4 (degree 1, n = 8), 3.22e-4 (2, n = 99), 2.69e-4 (3, n = 48); epsilon squared 0.075 | 0.0030 |
| Level, long rows against connector rows (Mann-Whitney) | 2.86e-4 (127 qubits) against 3.39e-4 (28) | 0.0088 |
| Level, degree 3 against degree 2 within the long rows (Mann-Whitney) | 2.69e-4 (48) against 3.15e-4 (71) | 0.013 |
| Moran's I of level | -0.049 (null mean -0.007, sd 0.074) | 0.56 |
| Moran's I of change size | -0.074 | 0.38 |
| Moran's I of spike rate | 0.015 | 0.78 |
| Same-round spikes, coupled pairs | 9 joint spike rounds against 8.92 expected (ratio 1.01, 174 pairs) | 0.53 |
| Same-round spikes, pairs at least 4 hops apart | 559 against 529.0 (ratio 1.06, 11,219 pairs) | 0.10 |

Only the degree test passes Bonferroni: qubits with three neighbours have lower `sx` error.
All 28 connector-row qubits have degree 2 and all 48 degree-3 qubits sit on the long rows [S
coords_columns_rows.degree_counts_*], so degree and row type overlap; within the long rows
alone, degree 3 is still lower (p = 0.013, not significant after correction). Why degree
matters is not visible in this archive (frequency allocation is not published in the
documents); it is an open question (§9). There
is no spatial autocorrelation of levels, of the size of the non-persistent component, or of
spikes, and spikes on coupled qubits do not co-occur more than chance, although the RB is run
simultaneously on all qubits. This agrees with P6 of the 2026-10-05 roadmap (older ref) and
with the local, defect-driven fluctuation prior of
`docs/roadmap/2026-10-04-deep-engine-architecture-research.md` §3.

The worst qubits sit at no single place: `q27` (column 8, row 3, degree 3), `q11` (12, 1,
degree 3), `q0` (1, 1, degree 1), `q149` (10, 15), `q24` (5, 3), `q100` (1, 11, degree 1),
`q126` (7, 13), `q102` (3, 11) [S worst_qubits]. The neighbours of the permanently faulty
`q72` are unremarkable: `q71` ranks 110 and `q73` 71 of 155 [S q72_neighbours].

## 6. Faults and data quality

**`q72`.** Placeholder (`gate_error = 1`) in all 1,760 files for `sx` and its aliases, and in
all 872 `xslow` files [A placeholders]. Its `T2` is absent from all 1,760 files and its `T1`
from 36; when present, its `T1` median is 21.45 us against the device median of 125.88 us
[C placeholder_qubits.q72]. It has no `sx` series and is excluded from every statistic here.

**`q17`.** Two placeholder episodes: 2026-05-13T12:13:22Z to 05-18T05:08:26Z (53 files) and
2026-06-22T01:46:23Z to 07-13T13:52:08Z (156 files) [A placeholders.sx.q17]. During both, its
`T1` is frozen: the same value (200.93 us) with the same stamp, 2026-04-13T21:49:04Z, appears in
482 files between 2026-05-13 and 2026-07-14, including all 209 placeholder files, where that
stamp is 710 to 2,176 h old. Its `T2` kept being re-measured (26 distinct stamps in the
placeholder files, median age 11.1 h) [C placeholder_qubits.q17_stamps]. An inference: during
its placeholder episodes `q17` was left out of the RB and `T1` experiments while it remained in
the `T2` experiment, and the document kept serving its last `T1`. The frozen `T1` belongs to
`02-coherence.md` to document; it matters here because any coherence limit for `q17` in that
period would use a two-month-old `T1` (the matching in §7 skips such events, since no `T1` event
lies within 6 h).

**`q149`.** Placeholder in the first 6 files only (2026-05-13) [A placeholders.sx.q149]. It is
among the worst qubits (median 1.38e-3), carries the largest single event (0.0171), has the
fewest events (68, about half the typical count, longest gap 252.6 h from 2026-07-07) and 11
spikes [P distribution, cadence.fewest_events; T spikes.top_entities]; its `T2` median is
about 5 us [C ratio.qubits_with_median_ratio_gt_1].

**`xslow` placeholders:** `q17` in 43 files (2026-05-14 to 05-18) and `q72` in all 872 [A
placeholders.xslow], mirroring `sx`.

**Stamp facts that bear on event rules.** Placeholder stamps are assembly times (§1), which is
why they must be masked before events are formed; after masking, the aliases' event lists
equal `sx`'s exactly, so the 979 to 310 date mismatches cannot inflate any alias's event count
[A aliases]. For `xslow`, the comparison is against `sx` restricted to the files where
`xslow` exists.

**`xslow` against the target and `basis_gates`: a confound to keep in mind** [A xslow]:

| `xslow` records | Target set has `xslow` | Configuration present | `basis_gates` has `xslow` | Files |
| --- | --- | --- | --- | --- |
| no | no | no | (none) | 29 |
| no | no | yes | no | 832 |
| no | yes | no | (none) | 27 |
| yes | no | yes | no | 135 |
| yes | yes | no | (none) | 387 |
| yes | yes | yes | yes | 350 |

In May, `xslow` records exist in 135 live files whose target and `basis_gates` do not list it.
In September, 27 files carry the 2,224-operation target that lists `xslow` while their
properties have no `xslow` records; all 27 are historical fetches (no configuration), dated
2026-09-09T08:43:45Z to 09-10T15:10:16Z and interleaved with live files that carry the
target without `xslow` [A xslow.target_has_xslow_but_no_records]. The archive README (cited
in `01-data-layer.md` §6) attributes a historical file's `target` to `target_history`, so **the
target set in a historical file is not evidence of the target at the document's own time**.
The second run of `xslow` records starts in a historical file (2026-09-10T16:56:21Z), and the
first live file with records is 2026-09-10T19:20:51Z, the same file in which `basis_gates` and
the configuration's gate list first contain `xslow` [A xslow.first_*].

**`rx`.** Records for all 156 qubits in all 1,760 files (274,560), but `rx` never appears in
the target operations, in any version of `basis_gates`, in the configuration's gate list or
in `supported_instructions` [A rx]. IBM lists RX among the fractional gates (§1); that its
error equals `sx`'s in every record is an archive observation, not documented. The archive
holds an error record for an instruction that its own target does not offer; the reason (for
example documents fetched without fractional gates enabled) is not visible here and is
recorded as an open question, not a conclusion.

**Coverage.** No sampling or truncation was applied: every file, every qubit and every event is
used, except as logged here: `q72` has no series; the coherence matching skips 1,906 of 20,207
`sx` events with no `T1` or `T2` event within 6 h [C matching]; the running level is defined
only where at least 4 neighbouring events exist (all 20,207 events qualified) [P
changes.residual_from_running_level.n]; monthly medians need at least 5 events (October
excluded); per-qubit variogram ratios need at least 20 pairs per range (all 155 qualified) [V
per_entity].

## 7. Relationships (inside the scope, plus the cross-family link to T1 and T2)

**Inside the scope.** The five error fields are one series (§0). The lengths are constants.
`rz` is constant. There is therefore exactly one single-qubit error time series per qubit in
this archive, and `xslow`'s presence or absence changes no value.

**The coherence limit.** For a gate of length `t` on a qubit with relaxation time `T1` and
coherence time `T2`, the average gate infidelity of an idle of that length under amplitude and
phase damping alone is

`e_coh = 1/2 * (1 - (2/3) exp(-t/T2) - (1/3) exp(-t/T1))`,

which equals `1 - (3 + exp(-t/T1) + 2 exp(-t/T2))/6`. This is exactly the one-qubit branch of
Qiskit Experiments' `RBUtils.coherence_limit` (fetched 2026-10-06: module source and API page,
which ask for "T2 as measured, not Tphi" and assume `T2 = 2 T1` when none is given); this
closes the "unverified lead" on that utility in the 2026-10-05 survey §4. Its derivation from
the damping channel and the average-fidelity formula is in the 2026-10-05 survey §2.2 (Ghosh,
Fowler and Geller 2012; Nielsen 2002; Abad et al. 2022). Here `t` = 24 ns, read from
`g1.sx.gate_length` (one value in all records) [C sx_gate_length_ns]. Its first-order form
`t/(6 T1) + t/(3 T2)` differs from the exact form by at most 0.31% over all matched events
[C ratio.first_order_max_rel_diff]. The `T1` term is a median 29% of the limit (10% 11%, 90%
38%), so the limit is mostly the `T2` term [C ratio.t1_term_share_of_limit_q].

**Matching.** Each `sx` event is paired with the nearest `T1` event and the nearest `T2` event
of the same qubit within 6 h [C matching]. `T1` is stamped a median 0.91 h before `sx` (90.7%
of nearest `T1` stamps are earlier); 48.8% lie within 1 h, 82.2% within 3 h, 90.9% within 6 h.
For `T2`: median 0.91 h earlier, 50.2% within 1 h, 93.5% within 6 h. Matched: 18,301 events;
skipped: 1,906. The coherence limit over matched events: median 1.21e-4 (10% 7.1e-5, 90%
2.99e-4).

**Ratio of the limit to the reported error** [C ratio]: minimum 0.007, 10% 0.178, 25% 0.267,
median 0.402, 75% 0.609, 90% 0.992, 99% 2.35, maximum 9.06; 9.82% of matched events above 1
and 35.7% above 0.5. `T2 > 2 T1`, unphysical for the formula, occurs in 18 matches (0.10%); they
are kept and do not move the quantiles (median 0.402 without them). In the median, two
fifths of the reported error is what decoherence during 24 ns would cause; the rest is not
idle decoherence. The older-ref figure (P4 of the 2026-10-05 roadmap, ref `09fcc45`, a
per-file rather than per-event pairing: 0.18, 0.40, 1.02 at 10%, 50%, 90%) agrees.

**Where the "limit" exceeds the error.** 13 qubits have a median ratio above 1 (up to 2.40 for
`q155`, 2.35 for `q53`), and every one has a low `T2` (5.2 to 35.6 us against the matched device
median of 94.5 us), while their `T1` medians (48.7 to 203.9 us, all but `q149` above 98 us) are
not unusual against the matched device median of 125.4 us [C
ratio.qubits_with_median_ratio_gt_1, device_median_T*_us_matched]. Interpretation (not sourced
here): the formula assumes exponential (Markovian) dephasing at the rate `1/T2`; if a low
Hahn-echo `T2` comes from slow noise, the dephasing accumulated in 24 ns is much smaller than
the exponential extrapolation, so the formula is not a lower bound for these qubits. The "limit"
is a proxy, not a bound, and is weakest exactly where `T2` is poor.

**Between qubits** (per-qubit medians, 155 qubits, bootstrap 2,000) [C between_qubits]:

| Pair | Spearman | 95% CI | p |
| --- | --- | --- | --- |
| log `sx` against log `e_coh` | 0.199 | 0.022 to 0.355 | 0.013 |
| log `sx` against log `T1` | -0.434 | -0.558 to -0.291 | 1.7e-8 |
| log `sx` against log `T2` | -0.161 | -0.315 to 0.016 | 0.046 |

Pearson of the median logs (`sx` against `e_coh`): 0.23; Theil-Sen slope of median log `sx` on
median log `e_coh`: 0.17 (CI 0.04 to 0.30). Qubits with short `T1` have worse `sx`, much more
clearly than the coherence limit (dominated by `T2`) suggests. The older-ref P4 figure
(between-entity Pearson 0.32 of time-mean logs, ref `09fcc45`) used per-file means and is not
the same statistic.

**Within qubits** (deviations from each field's own running level, paired in the same round)
[C within_qubits]:

| Pair | Pooled Spearman | Shifted null: mean +- sd (min, max of 36 shifts) | Per-qubit median | Qubits negative |
| --- | --- | --- | --- | --- |
| `sx` against `T1` | -0.062 | 0.002 +- 0.008 (-0.0145, 0.014) | -0.059 | 77.4% |
| `sx` against `T2` | -0.049 | 0.002 +- 0.009 (-0.015, 0.016) | -0.043 | 71.0% |
| `sx` against `e_coh` | +0.054 | not computed | | |

Changes between consecutive events: Spearman of `dlog sx` against `dlog e_coh` 0.053
(n = 18,146) [C within_qubits.consecutive_changes_spearman_dlog_sx_vs_dlog_coh]. By decile of
the coherence-limit deviation, the median `sx` deviation goes from -0.011 (lowest decile,
`e_coh` 0.13 decades below its level) to +0.009 (highest decile, 0.21 above): the `sx`
response is a small fraction of the coherence-limit change, while the limit is about 0.4 of
the error, so even full transmission would give a slope near 0.4 [C
within_qubits.coh_limit.median_dev_sx_by_dev_coh_decile].

**The coupling weakens with the time between the stamps** [C within_by_stamp_offset]:

| Pair | Stamps within 1 h | Stamps 1 to 6 h apart | Near minus far (95% CI, 500 qubit resamples) |
| --- | --- | --- | --- |
| `sx` against `T1` | -0.096 (CI -0.115 to -0.076; n = 9,826) | -0.024 (CI -0.042 to -0.005; n = 8,475) | -0.102 to -0.046 |
| `sx` against `T2` | -0.086 (CI -0.106 to -0.066; n = 9,828) | -0.007 (CI -0.026 to 0.012; n = 8,473) | -0.108 to -0.050 |

The share of near pairs varies by month (72% in May, 44% in July, 52% in September), so the
split was repeated within each month: for `T1` the near coupling is -0.179, -0.122, -0.067,
-0.047, -0.078 (May to September) against far -0.097, -0.025, -0.001, -0.029, -0.006; for
`T2` near -0.159, -0.120, -0.058, -0.030, -0.065 against far -0.011, -0.006, -0.004, +0.006,
-0.020 [C within_by_stamp_offset.*.by_month_near_far_rho]. Near is stronger than far in every
month for both fields. The coupling is also strongest in May and June.

**Spikes against dips** (spike: `sx` more than a factor of two above its level; 324 spikes in
18,301 matched events) [C coincidence]:

| Dip definition | P(dip given spike) | P(dip given no spike) | Odds ratio (Fisher p) | Shifted null P(dip given spike): mean, max |
| --- | --- | --- | --- | --- |
| `T1` 1.5 times below its level | 0.167 (54 of 324) | 0.094 | 1.94 (4.8e-5) | 0.109, 0.140 |
| `T1` 2 times below | 0.083 (27) | 0.030 | 2.94 (3.4e-6) | 0.042, 0.060 |
| `T2` 1.5 times below | 0.114 (37) | 0.062 | 1.94 (4.9e-4) | 0.096, 0.138 |
| `T2` 2 times below | 0.053 (17) | 0.020 | 2.69 (4.7e-4) | 0.039, 0.065 |

The right comparison is the shifted null, not the no-spike rate: qubits that spike in `sx` also
dip more in `T1` in general (between-qubit Spearman of the two rates 0.23, p = 0.005) [C
volatility_between_qubits], which inflates any pooled odds ratio. Against the shifted null,
`T1` dips at spikes exceed all 36 shifts at both thresholds; `T2` dips do not exceed the null's
maximum at either threshold. Given a `T1` dip of 1.5 times, the chance of an `sx` spike rises
from 1.8% to 3.1%. 270 of the 324 spikes have no such `T1` dip.

**How much of a spike decoherence explains.** At each spike, the excess of the coherence limit
over its own level divided by the excess of `sx` over its level: median 0.005 (10% -0.045, 90%
0.164); at the 54 spikes with a `T1` dip, median 0.136 (10% 0.030, 90% 0.333); 0.9% of spikes
reach 0.5 [C coincidence.excess_accounted_by_coh_limit]. Interpretation: even when `T1` dips with
an `sx` spike, the idle decoherence the dip implies accounts for a minority of the extra error.
Whatever moves both is not simply "shorter `T1` means more decay during the gate"; a defect
near the qubit frequency that also disturbs the calibrated pulse would fit, and is labelled
here as a hypothesis, not a finding.

**Volatility between qubits** [C volatility_between_qubits]. The robust size of a qubit's `sx`
changes against that of its `T1` changes: Spearman 0.11 (p = 0.17); against `T2`: 0.20
(p = 0.013); controlling for the `sx` level (partial rank correlation): 0.08 and 0.20. `sx`
spike rate against `T1` dip rate 0.23 (p = 0.005), against `T2` dip rate 0.12 (p = 0.12).
Qubits whose `T2` is volatile tend to have volatile `sx` too, weakly.

**What this link does and does not say about the root question.** Does: within a round, part
of the `sx` excursion is shared with `T1` (and `T2`), beyond what any shifted pairing gives,
and the sharing decays with the hours between the two measurements. Does not: it does not say
the rest of the component is noise; a fluctuation that decorrelated within the median 0.9 h
between the stamps, or one that `T1`/`T2` do not register, would be consistent with this
pattern.
A null here would not have ruled out real fluctuations either.

## 8. Use cases and why each field matters

**In this project.**

- `g1.sx.gate_error` is the per-qubit single-qubit error and one of the gate-error series of
  "Target 1" in `docs/roadmap/2026-10-05-feature-patterns-and-method.md` §4 (a recommendation,
  not adopted). Its aliases must be collapsed to one series before any model sees them, or
  the same measurement enters five times.
- `g1.sx.gate_length` is the default gate length of `gate_lengths()` in
  `src/superconducted/training/targets.py`, which sets `t` in ADR-027's per-qubit
  `gamma = 1 - exp(-t/T1)` and `lambda = 1 - exp(-t (2/T2 - 1/T1))`; at 24 ns in every record,
  it is a constant of that target at this ref.
- The gate-eligibility policy in `src/superconducted/integration/aer_factory.py` (ADR-028 by its
  docstring) attaches noise to a single-qubit gate exactly when its record gives a positive
  `gate_length`; `rz` (0 ns) is ineligible by that rule, and `xslow` (1,000 ns) would be
  eligible whenever its record is present. Any channel built for `xslow` from its record would
  inherit an error copied from a 24 ns gate (§0); this is a fact for whoever maps records to
  channels, not a decision.
- The coherence-limit ratio is the "R3" covariate idea of the 2026-10-05 roadmap §4 (also a
  recommendation); §7 shows that between qubits `T1` alone carries more of the association.

**In the literature** (existing survey identifiers): noise-adaptive qubit mapping exploits the
spatial and temporal variation of gate errors (Tannu and Qureshi 2018; Murali et al. 2019,
2026-10-05 survey §2.1); day-to-day `sx` variation drives a per-qubit code-distance choice
(Das and Ghosh 2025, §2.1); calibration-based digital twins turn the published errors into
simulator noise (Bautra et al. 2026, §2.5); a neuro-fuzzy error-attribution framework on
`ibm_fez` itself met the `q72`-style 1.0 sentinel (Hassan and Kaabouch 2026, §2.3).

**Why it matters.** `sx` is the only measured error of a single-qubit unitary gate in the
documents, so
every single-qubit channel built from them rests on one RB number per qubit and round, and on
a convention that `x`, `id`, `rx` (and now `xslow`) share it. Its non-persistent component
(a factor of about 1.3 per round) limits how well any single value describes the next one,
and its one-sided tail makes a single snapshot a poor estimate of a qubit's typical error.

## 9. Open questions, and what measurement would settle each

| Question | What would settle it |
| --- | --- |
| What is the bulk of the non-persistent component: RB estimation noise, or real fluctuations faster than 6 h or invisible to `T1`/`T2`? | IBM's RB settings (sequence lengths, counts, shots) to compute a noise floor; or own back-to-back RB repeats on one qubit at minute spacing, interleaved with `T1` (hardware experiments, outside the documents) |
| Is the same-round coupling physical, or a shared upstream calibration step? | Whether the 1 to 6 h pairs come from separate calibration jobs (job identifiers are not in the documents); or own experiments that measure `T1` and RB with and without recalibration in between |
| Why do degree-3 qubits have lower `sx` error? | `T1` and `T2` by degree (`02-coherence.md`); qubit frequencies and anharmonicities if a source publishes them |
| Why is May's spike rate lower and its coupling stronger? | Repeat §3 and §7 with May's extra short-gap rounds removed, and compare rounds by polling regime (`06-device-time-topology.md`) |
| What is `xslow` for, and was it calibrated at all? | IBM documentation or release notes for the instruction; any `xslow` error that ever differs from `sx` |
| Why do documents carry an `rx` record that the target does not offer? | The poller's fetch options (fractional gates on or off) and an IBM statement on fractional-gate properties |
| Does IBM's pipeline use Qiskit Experiments' error-per-gate convention? | An IBM statement; the equality of `x` and `sx` is consistent with it but not proof |
| Do the 06-06 to 06-08 per-qubit level changes reflect a device event? | A cross-family change-point scan (`06-device-time-topology.md`) |
| Do `sx` spikes coincide with readout or two-qubit events? | `07-cross-feature-dependency.md` (outside this scope by assignment) |
| `q17`'s two-month frozen `T1` and `q149`'s halved event count | `02-coherence.md` for `T1`; per-round presence of `q149` in the RB rounds |

## 10. Reproduce (exact commands) and results files

From the repository root, with the cache of `01-data-layer.md` built (default
`~/.cache/superconducted-feature-deep-dive/7b84b506/`, or `DD_CACHE`):

```bash
PY=C:/t/venv/Scripts/python.exe
D=docs/findings/2026-10-06-feature-deep-dive/analysis/gates_1q
$PY $D/aliases_and_schema.py   # results/gates_1q/aliases_and_schema.json
$PY $D/sx_profile.py           # results/gates_1q/sx_profile.json
$PY $D/sx_temporal.py          # results/gates_1q/sx_temporal.json
$PY $D/sx_variogram.py         # results/gates_1q/sx_variogram.json
$PY $D/sx_coherence.py         # results/gates_1q/sx_coherence.json
$PY $D/sx_spatial.py           # results/gates_1q/sx_spatial.json
C:/t/ruffpin/Scripts/ruff.exe check $D && C:/t/ruffpin/Scripts/ruff.exe format --check $D
```

Each script takes under a minute on the laptop and loads only `g1.*` fields of this scope,
`q.T1` and `q.T2` (coherence link), and small per-file arrays and `meta.json` entries
(`target_ops_id`, `has_configuration`, `config.basis_gates`, `coords`, `coupling_map`).
Randomness (permutations, bootstraps) uses the fixed seed 20261006. `g1common.py` holds the
shared helpers (running level, rounds, BH, Spearman, Theil-Sen, Kruskal-Wallis).

## 11. Sources

New sources fetched in this session: 12 (limit 15), from 13 URLs: the `RBUtils` API page and
its module source count as one source. One existing-survey source was re-fetched to confirm a
sentence (marked) and is not counted.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum documentation, "View backend details" | https://quantum.cloud.ibm.com/docs/en/guides/qpu-information | fetched 2026-10-06 | SX error from simultaneous RB; SX, ID, X share one RB error; RX is a fractional gate; `T2` from Hahn echo |
| Qiskit Experiments 0.14.2, "Randomized Benchmarking" manual | https://qiskit-community.github.io/qiskit-experiments/manuals/verification/randomized_benchmarking.html | fetched 2026-10-06 | decay model, error per Clifford, error-per-gate ratio convention and its caveat |
| Qiskit Experiments 0.14.2, `RBUtils.coherence_limit` (API page and module source) | https://qiskit-community.github.io/qiskit-experiments/stubs/qiskit_experiments.library.randomized_benchmarking.RBUtils.html and https://qiskit-community.github.io/qiskit-experiments/_modules/qiskit_experiments/library/randomized_benchmarking/rb_utils.html | fetched 2026-10-06 | the one-qubit coherence-limit formula, verbatim in code |
| Magesan, Gambetta, Emerson, Robust randomized benchmarking of quantum processes (PRL 2011) | arXiv:1009.3639 | fetched 2026-10-06 | what RB estimates |
| Gambetta et al., Characterization of addressability by simultaneous randomized benchmarking (PRL 2012) | arXiv:1204.6308 | fetched 2026-10-06 | simultaneous against individual RB |
| Proctor et al., What randomized benchmarking actually measures (PRL 2017) | arXiv:1702.01853 | fetched 2026-10-06 | RB rate is not exactly an average gate infidelity |
| Epstein, Cross, Magesan, Gambetta, Investigating the limits of randomized benchmarking protocols (PRA 2014) | arXiv:1308.2928 | fetched 2026-10-06 | within a factor of two; few trials suffice |
| Helsen, Wallman, Flammia, Wehner, Multi-qubit randomized benchmarking using few samples (PRA 2019) | arXiv:1701.04299 | fetched 2026-10-06 | sequence count scales favourably with error rate |
| Harper, Hincks, Ferrie, Flammia, Wallman, Statistical analysis of randomized benchmarking (PRA 2019) | arXiv:1901.00535 | fetched 2026-10-06 | multiplicative precision is achievable |
| qiskit-ibm-runtime release notes, 0.50.0 (2026-09-24) | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/release-notes | fetched 2026-10-06 | `XSlowGate` added for the hardware-native `xslow` |
| qiskit-ibm-runtime API, `XSlowGate` | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/circuit-library-x-slow-gate | fetched 2026-10-06 | no purpose, unitary or duration documented |
| Qiskit/qiskit-ibm-runtime issue #3311 (opened 2026-09-10) | https://github.com/Qiskit/qiskit-ibm-runtime/issues/3311 | fetched 2026-10-06 | `xslow` export limitations; no semantics |
| Wallman and Flammia, Randomized benchmarking with confidence (2014) | arXiv:1404.6025 | existing survey (2026-10-05), §2.1 | RB precision set by sequence number and length |
| McKay et al., Efficient Z-gates for quantum computing (2017) | arXiv:1612.00858 | existing survey (2026-10-05), §2.2; abstract re-fetched 2026-10-06 | virtual, zero-duration Z gates |
| Ghosh, Fowler, Geller (2012); Nielsen (2002); Abad et al. (2022) | arXiv:1210.5799; arXiv:quant-ph/0205035; arXiv:2110.15883 | existing survey (2026-10-05), §2.2 | derivation of the coherence limit |
| Hassan and Kaabouch (2026) | arXiv:2602.21253 | existing survey (2026-10-05), §2.3 | the 1.0 sentinel on `ibm_fez` |
| Tannu and Qureshi (2018); Murali et al. (2019); Das and Ghosh (2025) | arXiv:1805.10224; arXiv:1901.11054; arXiv:2505.06165 | existing survey (2026-10-05), §2.1 | use cases of gate-error variation |
| Bautra, Dimitrijevs, Yakaryilmaz (2026) | arXiv:2603.14607 | existing survey (2026-10-05), §2.5 | calibration-based digital twins |
| Burnett et al. (2019); Thorbeck et al. (2023) | arXiv:1901.04417; arXiv:2210.04780 | existing surveys: 2026-10-04 §3 and §8; 2026-10-05 §2.3 | local, defect-driven fluctuations on hour timescales (the prior this document tests, not a fact about `ibm_fez`) |

Project sources: `01-data-layer.md` (field semantics, event rules, length changes, file
structure); `docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P2, P4, P6 at ref
`09fcc45`); `docs/roadmap/2026-10-05-gate-error-literature-survey.md` (§2.1, §2.2, §2.3,
§2.5, §4); `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` (§3, §8);
`scripts/feature_patterns.py` (the event rule and `coherence_limit_1q`, which equals the
formula above); `src/superconducted/training/targets.py` and
`src/superconducted/integration/aer_factory.py` (project use).
