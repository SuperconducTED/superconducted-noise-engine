# 03 · Readout and measurement: assignment errors, lengths, thresholds, initialization, reset

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: reconcile it
later by appending an as-of section, never by editing the text below. It is data
understanding only: no model, no strategic decision, no ADR change. Decisions A1 to A9 and the
advisor's answers remain open, and nothing here records or implies an approval.

**Every figure here is provisional.** Basis: all 1,760 `ibm_fez` snapshot files at
`calibration-data` `7b84b506ef77beb6e6c1b25a7357c574cfaf5117` (2026-05-13T12:13:22Z to
2026-10-06T02:57:42Z), 156 qubits, read through `analysis/ddload.py` from the cache that
`01-data-layer.md` describes; 91,896 readout stamp events in 598 readout sessions (section 1.3).
Measured on 2026-10-06 on the lead's laptop (Windows 11, CPython 3.12). Nothing here is
registered in `docs/numerical-claims.md`. Every number below is a field of a JSON file in
`results/readout/` written by a script in `analysis/readout/` (section 10), of
`results/data-layer/*.json`, or a figure quoted with its path from an existing repository
document.

**Notation.** The two earlier documents use "p01" for opposite fields
(`docs/roadmap/2026-10-05-feature-patterns-and-method.md` P5 calls `prob_meas0_prep1` "p01";
`01-data-layer.md` section 5 calls `prob_meas1_prep0` "p01"). This document avoids the name:

| Symbol | Field | Meaning |
| --- | --- | --- |
| P(0\|1) | `q.prob_meas0_prep1` | prepared in \|1>, read as 0 |
| P(1\|0) | `q.prob_meas1_prep0` | prepared in \|0>, read as 1 |
| RO | `q.readout_error` (identical to `g1.measure.gate_error` in all 274,560 records, `identities.json`) | assignment error |
| A | P(0\|1) - P(1\|0) | asymmetry |
| t_ro | `q.readout_length` (identical in value to `g1.measure.gate_length`) | readout duration |

## 0. Summary

1. **RO is the mean of P(0|1) and P(1|0) in every record whose three values come from one
   readout session.** The three stamps are identical in 188,100 records (68.51%), staggered by
   seconds to minutes within one session in 72,900 (26.55%; P(0|1) is stamped a median 81 s
   and P(1|0) 41 s before RO), and the mean rule holds in all of both. It fails in 11,263
   records, and 11,258 of those (99.956%) are records whose published P(0|1) is a median
   11.57 h older than RO (`sessions.json: record_classes, stagger, stale_p0g1`).
2. **A rotating group of 9 qubits does not get its P(0|1) published between daily
   sessions.** The group is always the 9 qubits with one index residue modulo 17: residue 10
   (q10, q27, ..., q146) from the archive's start to 2026-07-25, residue 9 to 2026-08-25,
   residue 16 since. RO is computed from a fresh P(0|1) that the document does not carry:
   `2 RO - P(1|0)` lands on the 1/4096 grid in 100% of the 11,514 recoverable records. **[Verification 2026-10-06: overstated as evidence. RO sits on the 1/8192 grid and P(1|0) on the 1/4096 grid in 100% of all records, so 2 RO - P(1|0) is on the 1/4096 grid by arithmetic; a placebo with a shuffled P(0|1) also gives 100% (`results/verify/readout/records_check.json`). The grid test cannot fail. What the data show is that the implied value is consistent with the stale one (median ratio 1.01), not that RO was computed from a fresh P(0|1) that was withheld.]** The
   group's P(0|1) is fresh in 1,086 of 1,103 daily-session events and in 9 of 4,194 intraday
   ones (`sessions.json: stale_p0g1`). `meas_map` is one group of all 156 qubits, so it does
   not explain the grouping.
3. **There are two kinds of readout session.** Of 589 sessions with at least 100 qubits, 123
   have every published count even (all values on the 1/2048 grid; by chance this has
   probability 2^-312), and 466 have about half odd (median even share 0.498). The even
   sessions run once a day: 87.0% of them start within 3 h of a `T1` round, against 15.7% of
   the others (`sessions.json: sessions`). That the even sessions used 2,048 shots per state
   is the natural reading of the grid, but two variance tests do not settle it (section 4.5).
4. **The older P5 shot-noise figure reproduces at this ref:** 64.22% of RO changes fall
   within 2 sd of pure binomial noise under P5's method, and 64.45% for consecutive changes
   between intraday sessions with this scope's per-session variance; pure noise would give
   95.45% (`noise.json: summary`).
5. **Shot noise is about a quarter of RO's shortest-lag variability.** Between intraday
   sessions 2 to 4 h apart, the robust standardized semivariance of RO is 4.252 shot-noise
   units, so binomial noise explains 0.235 of it (0.395 for P(0|1), 0.173 for P(1|0)). The
   excess of 3.252 units is already there at 2 to 4 h, grows only to 4.759 units at 18 to
   30 h, and reaches 10.745 at 744 to 1,488 h (`noise.json: summary,
   standardized_variograms`). The cadence offers 5 intraday session pairs closer than 2 h, so
   the data cannot resolve a correlation time below about 3 h.
6. **The excess is not explained by discriminator re-calibration, a device-wide common mode,
   or neighbours.** Lag- and kind-matched RO changes across a threshold change are no larger
   (ratio of median |z| 1.023, p = 0.584); the session mean explains 1.38% of the variance of
   RO changes against 0.64% expected under independence; coupled qubits correlate at a median
   0.012 against -0.008 for qubits four or more hops apart (`noise.json: threshold_test,
   common_mode, neighbours`). Whether the excess is estimation noise beyond the binomial or
   real fluctuations faster than about 3 h is **not** settled by these data (section 4.7).
7. **The 2026-06-08 change (t_ro 1,560 to 1,700 ns) is a large natural experiment.** Over
   7-day windows the per-qubit RO fell by a median 0.137 decades, only 1.9% of qubits went up,
   and no placebo day of 104 came close (5% to 95% placebo range -0.039 to +0.030). P(1|0) fell
   0.269 decades and P(0|1) 0.079, while A rose by a median 0.0016 against +0.00094 predicted
   from the longer decay window alone (`length_changes.json`). `measure.threshold` first
   appears in the same file, so the length and a change of discrimination procedure cannot be
   separated.
8. **The 2026-07-30 change (1,700 to 1,660 ns) moved nothing detectable** (RO median -0.0026
   to +0.0062 decades depending on window, inside the placebo range); the decay it predicts,
   -0.0003, is below what the data can resolve (`length_changes.json`).
9. **Decay during readout shows up between qubits, not over time.** Across qubits A rises with
   the expected decay `1 - exp(-t_ro/T1)` (Spearman 0.423, p = 3.9e-8; Theil-Sen slope 0.310,
   95% CI 0.209 to 0.437; median A over decay 0.464), while P(0|1) alone does not (0.016)
   because P(0|1) and P(1|0) share a large overlap error (0.908 across qubits). Within a qubit,
   day-to-day `T1` changes do not move P(0|1) (Spearman -0.014 to -0.049), and records where
   `T1` is below half its median leave P(0|1) unchanged (relative median 0.997, p = 0.281)
   (`t1_link.json`).
10. **`init_error` is IBM's residual |1> population after initialization** (IBM documentation,
    fetched 2026-10-06), present from 2026-08-04T00:52:30Z, never carried by 40 qubits, and
    those 40 have much worse readout (median RO 0.0331 against 0.0071, p = 1.3e-20). It tracks
    P(1|0) across qubits (Spearman 0.822) and within qubits in the same session (0.722); P(1|0)
    is below it in 14.8% of records (`thresholds_m2_init.json: init_error`).
11. **`measure_2` (1,340 ns, the default mid-circuit measurement instruction) is measured once
    a day with the daily session** (52 rounds; 90.4% within 1 h of an even session); its error
    is a median 1.25 times RO per qubit and follows RO across qubits (Spearman 0.852)
    (`thresholds_m2_init.json: measure_2`).
12. **Thresholds are device-wide, all-or-none updates** (327 change files, every one moving
    all 156 qubits), identical between `measure` and `measure_reset` (and `measure_2` and
    `measure_reset_2`) in all 127,452 shared records, and they accompany intraday sessions: 208
    of 343 intraday sessions against 20 of 97 daily ones fall in a file that changes the
    threshold (`thresholds_m2_init.json: thresholds`).
13. **Every reset and measure-reset duration is the readout duration plus 24 ns** (the `x`
    length) in all 274,560 and 127,452 records (`profiles.json: length_identities`), as a
    measurement followed by a conditional `x` (the documented reset on IBM systems) predicts.
14. **The spatial pattern is a checkerboard, not a gradient.** **[Verification 2026-10-06: weakened. RO differs by lattice degree (median 0.00757 for degree 2 against 0.01196 for degree 1 and 0.01428 for degree 3; Kruskal-Wallis p = 3.5e-7), and after removing each degree class's median Moran's I is -0.047 (p = 0.59). On heavy-hex the degree-3 and degree-2 qubits alternate, so the 'checkerboard' is largely a degree-class effect; the frequency reading in section 5 is not supported. `extra_check.json`]** Per-qubit medians are
    negatively autocorrelated on the coupling graph (Moran's I -0.196 for RO, p = 0.007;
    -0.430 for `measure_2`, p = 0.0002), with no row or column trend, and the qubit ranking is
    stable (June against September, Spearman 0.926) (`spatial_temporal.json: spatial`).
15. **No time-of-day or weekday seasonality of the values of practical size** (epsilon-squared
    at most 0.00042); the device level fell from May to June (monthly median RO 0.01416 to
    0.00854) and has drifted up slightly since (0.00928 in October)
    (`spatial_temporal.json: temporal`).

## 1. The fields and how IBM produces them

### 1.1 What IBM documents

IBM's backend-details guide (fetched 2026-10-06) defines P(0|1) and P(1|0) as the
probabilities of reading the wrong state after preparing |1> or |0>; RO as the average
probability of a wrong reading, usually computed as the mean of the two; the readout length as
the time from the start of the measurement pulse to the end of signal digitization; and
`init_error` as the share of population in |1> after the default repetition delay and the
qubit initialization procedure. **[Verification 2026-10-06: incomplete. The fetched IBM text adds the condition 'when the prior experiment prepared the qubit in the |1> state'; the direct-addition-to-P(1|0) reading in section 7.1 is an inference.]** The guide names `measure`, `measure_2` (for mid-circuit
measurement) and `reset` as supported non-unitary instructions without defining their
calibration fields. It does not say how many shots the assignment experiment uses.

IBM's monitoring and calibration guide (fetched 2026-10-06) says brief monitoring jobs run
about once an hour between user jobs and check, among other things, the readout angles,
amplitudes and **discriminator threshold**; calibrations are triggered when monitoring finds
deviations, and on Heron they take typically under two hours a day; daily benchmarking
produces the metrics sent to users, including measurement fidelity and `T1`/`T2`. The guide
does not say which job writes which property field.

The readout physics (Krantz et al. 2019, section V C to V D, read in full on 2026-10-06): each
shot's integrated readout signal is a point in the (I, Q) plane; the |0> and |1> clouds are
roughly Gaussian; a line between them (the separatrix, or threshold) assigns each shot. Two
error sources follow: overlap of the clouds (a separation error of `erfc(SNR/2)/2`, the same
for both states), and the qubit relaxing (or being excited) during the readout, which puts a
count on the wrong side of the threshold. The relaxation part is `1 - exp(-tau_ro/T1)` with
`tau_ro = tau_rd + tau_s/2`, the resonator delay plus half the integration time (their eq.
173). Walter et al. 2017 reach 99.2% readout fidelity limited mainly by the qubit lifetime.
Excitation from |0> has its own sources: residual thermal excited population (about 0.1% at
saturation on the device of Jin et al. 2015) and measurement-induced state transitions at high
resonator photon numbers (Sank et al. 2016).

### 1.2 The fields

| Field | Unit | Lifetime | Rule (`01-data-layer.md` section 4) | What it is |
| --- | --- | --- | --- | --- |
| `q.readout_error`, `g1.measure.gate_error` | none | all 1,760 files | measured | RO; the two are identical record by record |
| `q.prob_meas0_prep1` | none | all files | measured | P(0\|1) |
| `q.prob_meas1_prep0` | none | all files | measured | P(1\|0) |
| `q.readout_length`, `g1.measure.gate_length` | ns | all files | value only | 1,560, 1,700, 1,660 ns (35,412, 61,932 and 177,216 records) |
| `q.init_error` | none (IBM says "percentage"; values are fractions of order 1e-3) | from 20260804T005230 (1,091 files) | measured | residual \|1> population |
| `g1.measure_2.gate_error` | none | from 20260807T032159 (1,058 files) | measured, placeholders masked | error of the mid-circuit measurement instruction |
| `g1.measure_2.gate_length` | ns | from 2026-08-07 | value only | 1,340 ns throughout |
| `g1.measure.threshold`, `g1.measure_reset.threshold` | arbitrary IQ units | from 20260608T185628 and 20260902T045624 | value only | discriminator threshold; identical where both exist |
| `g1.measure_2.threshold`, `g1.measure_reset_2.threshold` | arbitrary IQ units | from 20260807T032159 and 20260902T045624 | value only | the same for `measure_2`; identical where both exist |
| `g1.reset.gate_length`, `g1.measure_reset.gate_length` | ns | all files; from 2026-09-02 | value only | t_ro + 24 ns |
| `g1.reset_2.gate_length`, `g1.measure_reset_2.gate_length` | ns | from 2026-09-02 | value only | 1,340 + 24 = 1,364 ns |

Sources: `profiles.json: error_fields, length_fields, length_identities`;
`thresholds_m2_init.json: thresholds`.

**`measure_2`.** IBM's runtime documentation (fetched 2026-10-06) says the `MidCircuitMeasure`
instruction maps to the `measure_2` instruction a backend reports, that it adds less overhead
than a plain `measure` used mid-circuit, and that shortening mid-circuit measurement is a
focus of improvement. Its 1,340 ns against `measure`'s 1,660 ns fits that; its calibration
procedure is not documented.

**Reset.** Qiskit's documentation (fetched 2026-10-06) states that on IBM systems a reset is a
measurement followed by an `x` gate conditioned on the outcome. The archive agrees: `reset` is
t_ro + 24 ns in all 274,560 records, `measure_reset` equals `reset` in all 127,452, and
`reset_2` and `measure_reset_2` are `measure_2` + 24 ns in all 127,452
(`profiles.json: length_identities`); 24 ns is the `x` length. Interpretation: the reported
reset duration is the nominal sum of the two operations; any classical feed-forward latency is
not represented in it.

### 1.3 How the archive shows IBM producing them (inference from the data)

None of the following is documented by IBM; each is what the data show.

- **Sessions.** Readout stamps cluster tightly: within a session the three fields of a qubit
  are stamped seconds apart and the qubits within minutes (even sessions last a median 0.53
  min, at most 15.8 min; intraday sessions a median 0.0 min, at most 8.45 min). Clustering all
  RO stamp events with a 15-minute gap gives 598 sessions: 123 even, 466 mixed, and 9 small
  sessions of 3 qubits each (`sessions.json: sessions`).
- **Two clocks.** The even sessions start mostly between 18:00 and 23:00 UTC (61 of 123), and
  87.0% start within 3 h of a `T1` round; the mixed sessions spread over the day and only 15.7%
  are near a `T1` round. Reading: the even sessions belong to the daily round in which `T1`,
  `T2` and `measure_2` are also measured, and the mixed ones are intraday re-measurements. This
  fits IBM's description of hourly monitoring plus daily benchmarking, but which job writes
  the fields is not documented.
- **Staggered stamps.** P(0|1) is stamped first, P(1|0) about 40 s later, RO about 40 s after
  that; in 473 files no record has three identical stamps (149 of them historical). Reading:
  the three values come from one session and are written one after the other.

## 2. Profiles

### 2.1 Units, ranges, distribution and tails

| Field | Records | Quantiles 0, 1, 10, 50, 90, 99, 100% | Per-qubit median, 10% / 50% / 90% | Share > 3x own qubit median | Grid |
| --- | --- | --- | --- | --- | --- |
| RO | 274,560 | 0.000977, 0.00293, 0.00464, 0.0100, 0.0461, 0.238, 0.526 | 0.00525 / 0.00891 / 0.0409 | 0.0293 | 1/8192 (100%) |
| P(0\|1) | 274,560 | 0.000244, 0.00439, 0.00708, 0.0137, 0.0518, 0.185, 0.977 | 0.00818 / 0.0122 / 0.0432 | 0.0238 | 1/4096 (100%) |
| P(1\|0) | 274,560 | 0, 0.000244, 0.00122, 0.00610, 0.0386, 0.167, 0.996 | 0.00220 / 0.00537 / 0.0333 | 0.0591 | 1/4096 (100%) |
| `init_error` | 126,362 | 1.97e-28, 0.0002, 0.000444, 0.00185, 0.00526, 0.0106, 0.0464 | 0.000846 / 0.00171 / 0.00404 | 0.0250 | none (0.375% on 1/4096) |
| `measure_2` error | 164,736 (placeholders masked) | 0.000977, 0.00220, 0.00439, 0.0139, 0.0823, 0.299, 0.570 | 0.00464 / 0.0134 / 0.0720 | 0.0125 | 1/4096 (100%) |

Source: `profiles.json: error_fields.*`. All errors are heavy-tailed to the right: the 99%
quantile of RO is about 24 times its median, and the tail is mostly a property of a few
qubits (per-qubit medians reach 0.332), not of single records (2.9% of RO records exceed three
times their own qubit's median). The worst qubit is q72 (median RO 0.350,
`spatial_temporal.json: spatial.ro.worst_10`), the qubit whose `sx` and couplers are
permanently faulty (`01-data-layer.md` section 5).

**Count parity.** A binomial count over 4,096 shots is odd about half the time. The published
counts (`4096 x p`) are odd in 38.88% of P(0|1) stamp events and 39.46% of P(1|0) ones, with
the even residues mod 4 both over-represented (`profiles.json: count_parity`). Section 1.3's
session kinds explain it: every count is even in the 123 daily sessions. `measure_2` counts
are odd in 50.75% of records, as expected for a single 4,096-denominator quantity.

**Zeros.** P(1|0) is exactly 0 in 2,468 records, on 78 qubits, at most 141 on one qubit
(`profiles.json: p1g0_exact_zero`); its log is undefined there, and every log-scale analysis
below drops those events (644 of the noise series, `noise.json: coverage`).

**`init_error` degenerate values.** 540 records on 59 qubits are below 1e-6, down to 1.97e-28,
many decades under their qubit's level (`thresholds_m2_init.json: init_error`). Reading: a fit
that returned zero population within floating-point precision; they are masked where noted.

### 2.2 Missingness inside each lifetime

RO, P(0|1), P(1|0), `measure_2` and every length and threshold are present for every qubit in
every file of their lifetime (`profiles.json`). `init_error` is present in 74.24% of qubit
records in its lifetime because 40 qubits never carry it; among the other 116 it is present in
99.85%, the gap being q40 (present in 82.22% of files)
(`thresholds_m2_init.json: init_error.qubits_partially_present`). Presence is not freshness:
q40 and q117 carry a single `init_error` stamp event over the whole lifetime, and six more
qubits have 9 to 22 (`init_error.qubits_with_lt_50_stamp_events`), so for them the value in a
file can be weeks old (the RO stamp minus the `init_error` stamp reaches 1,507 h).

### 2.3 Cadence

| Field | Stamp events | Per qubit, median (min, max) | Gap between events, h: 10% / 50% / 90% | Measured-rule events | Re-measurements with an identical value |
| --- | --- | --- | --- | --- | --- |
| RO | 92,153 | 591 (590, 597) | 0.82 / 4.42 / 10.2 | 90,408 | 1,745 |
| P(0\|1) | 87,991 | 590 (327, 596) | 0.85 / 4.45 / 10.8 | 85,849 | 2,142 |
| P(1\|0) | 92,155 | 591 (590, 597) | 0.83 / 4.42 / 10.2 | 88,975 | 3,180 |
| `init_error` | 25,158 | 252 (1, 262) | 0.33 / 4.39 / 11.5 | 23,952 | 1,206 |
| `measure_2` | 8,112 | 52 (52, 52) | 8.2 / 24.7 / 28.2 | 7,925 | 187 |

Source: `profiles.json: events_stamp_rule, events_measured_rule,
stamp_events_with_value_unchanged`. P(0|1)'s minimum of 327 events is the stale group of
section 0 item 2. The shared measured rule drops a re-measurement that returned the identical
quantized value; for P(1|0), whose counts are small, that is 3,180 events, and dropping them
removes exact zero changes from every change statistic (3.48% of P(1|0) stamp-rule changes are
exactly zero, `memory_stamp_rule.share_change_exact_zero`). This scope therefore uses stamp
events throughout, and collapses the 257 cases where one qubit was re-stamped twice inside one
session (`noise.json: coverage.restamps_within_session_dropped`).

**Coverage by period.** The archive's visible readout cadence depends on how it was filled:
hourly polling before 2026-08, historical fetches added from 2026-08 (`01-data-layer.md`
section 6). Visible sessions per day were 5.68 in May (18.5 days), 4.43 in June, 4.16 in July,
3.07 in August, 3.67 in September and 3.32 in October (5.1 days); even sessions per day stayed
between 0.71 and 1.08 (`sessions.json: sessions.by_month`). Whether the fall from May to August
is IBM measuring less often or the archive seeing fewer of the intermediate documents cannot
be told from the archive alone; any per-period rate comparison has to carry this caveat.

## 3. Temporal structure

### 3.1 Level, drift and change points of the device

The device median per session (median over qubits of RO) ranges from 0.00775 to 0.0237, median
0.00946. Binary segmentation (descriptive; penalty and minimum segment are choices, section 10)
finds six change points for RO (`spatial_temporal.json: temporal.ro_device_median_per_session`):

| Session start | RO level before | RO level after | Coincides with |
| --- | --- | --- | --- |
| 2026-05-17T13:53:44Z | 0.0216 | 0.0140 | the archive's first days |
| 2026-05-27T15:37:21Z | 0.0140 | 0.0120 | |
| 2026-06-08T21:31:37Z | 0.0120 | 0.00876 | the first readout-length change (first session after it) |
| 2026-08-21T06:06:24Z | 0.00876 | 0.00995 | |
| 2026-08-31T16:35:39Z | 0.00995 | 0.00946 | |
| 2026-09-12T21:17:23Z | 0.00946 | 0.00989 | |

P(0|1) and P(1|0) share the first three change points (P(1|0) halves at the third, 0.00903 to
0.00488). Monthly device medians of per-qubit medians: RO 0.01416, 0.00854, 0.00812, 0.00836,
0.00854, 0.00928 from May to October; P(1|0) 0.01001, 0.00500, 0.00415, 0.00488, 0.00482,
0.00488 (`temporal.monthly_device_median_of_qubit_medians`). So most of the five months' level
change in readout happened before mid-June, and the rest is a slow drift.

### 3.2 Per-qubit levels and jumps

Per-qubit binary segmentation of log10 RO (minimum segment 30 events, at most 8 change points;
5 qubits reach the cap) finds a median of 2 change points per qubit, 555 in all; 94 fall within
a day of the first length change and 4 within a day of the second; the busiest ISO weeks are
2026-W24 (123, the week of the first change), W20 (89) and W22 (71)
(`temporal.per_qubit_ro_change_points`). Between change points the level wanders: the 10% to
90% range of a qubit's week-long running median (42 events) is a median 0.231 decades (10%:
0.138, 90%: 0.483) (`temporal.ro_weekly_level_range_decades_q`). This is the slowly moving
level of the root question.

### 3.3 Seasonality of the values

Residuals from each qubit's centred running median (6 events on each side, itself excluded)
were grouped by UTC hour (six 4-hour bins) and weekday, for RO, P(0|1) and P(1|0), with all
sessions and intraday sessions only (12 tests) (`temporal.seasonality`):

- RO: hour p = 0.0885 (all) and 0.0694 (intraday), weekday p = 0.501 and 0.480; epsilon-squared
  at most 0.00014; the largest bin median is 0.0019 decades.
- P(0|1): no test below p = 0.387.
- P(1|0): weekday p = 0.00158 (all) and 4.51e-5 (intraday), with epsilon-squared 0.00024 and
  0.00042 and bin medians within 0.007 decades; hour p = 0.693 and 0.257.

The P(1|0) weekday results pass a Bonferroni threshold for 12 tests (0.0042), but the residuals
are clustered by session (every qubit of one session shares a weekday) and the session common
mode is not zero (section 4.6), so the effective sample is closer to a few hundred sessions than
to 70,510 residuals and the p-values are overstated. The effect is under 2% in level. Reading:
no seasonality of practical size; a weekly component of P(1|0) is not excluded but is not
shown either. The **cadence**, by contrast, has a clock: the daily sessions peak at 20:00 UTC
(17 of 123 start in that hour) (`sessions.json: sessions.start_hour_utc_counts`).

### 3.4 Memory of the changes

| Field | Lag-1 autocorrelation of log10 changes (stamp rule / measured rule) | Changes larger than 2x |
| --- | --- | --- |
| RO | -0.443 / -0.449 | 0.0909 |
| P(0\|1) | -0.469 / -0.474 | 0.0910 |
| P(1\|0) | -0.434 / -0.448 | 0.307 |
| `init_error` (values >= 1e-6) | -0.436 | 0.398 |
| `measure_2` | -0.496 / -0.504 | 0.129 |

Source: `profiles.json: memory_*`. With the degenerate values kept, `init_error`'s lag-1 is
-0.497, driven by changes of up to 24.9 decades. All five sit in the -0.42 to -0.50 band of
every family (feature-patterns document P2): most of each change is undone by the next one.

## 4. The non-persistent component

### 4.1 What the shot noise is

Each published probability is a count over N shots, so its binomial variance is `p (1 - p) / N`
and RO's is `(var P(0|1) + var P(1|0)) / 4`; in log10 the delta method divides by
`(y ln 10)^2`. N is 4,096 for intraday sessions and, under the grid reading, 2,048 for daily
ones (`rocommon.py`). For a record whose P(0|1) is stale, the fresh `2 RO - P(1|0)` is used.
The plug-in variance from an estimated p is nearly unbiased on average
(`E[p_hat (1 - p_hat)] = p (1 - p)(1 - 1/N)`), but the log-scale delta method fails for P(1|0)
counts near zero, so linear-scale and standardized statistics are the primary ones. Of 91,896
RO stamp events, 91,733 carry a noise variance; 163 are dropped (27 in the small sessions, the
rest with a P(1|0) not from the same session) (`noise.json: coverage`).

### 4.2 Consecutive changes against shot noise

Standardized change `z = (y_j - y_i) / sqrt(var_i + var_j)`; under pure binomial noise around
a fixed level its variance is 1 and 95.45% of |z| fall below 2. The robust variance ratio is
`median(z^2) / 0.4549` (`noise.json: consecutive`):

| Pairs | RO: share \|z\| < 2, robust ratio | P(0\|1) | P(1\|0) | n (RO) |
| --- | --- | --- | --- | --- |
| P5 method (measured rule, 4,096 shots, published P(0\|1)) | 0.6422 | | | 90,252 |
| intraday to intraday | 0.6445, 4.299 | 0.746, 2.616 | 0.593, 5.664 | 53,785 |
| intraday to intraday, lag up to 6 h | 0.6488, 4.217 | 0.751, 2.583 | 0.594, 5.664 | 38,985 |
| intraday to intraday, lag 6 to 30 h | 0.6310, 4.578 | 0.733, 2.758 | 0.587, 5.725 | 14,176 |
| daily to intraday | 0.7241, 2.876 | 0.787, 2.137 | 0.721, 3.051 | 37,480 |
| daily to daily (lag above 1 h) | 0.7596, 2.143 | 0.811, 2.532 | 0.775, 2.521 | 312 |

So the older 64% reproduces almost exactly at this ref, and it is not an artefact of the
measured rule, the stale P(0|1) or the session kinds: changes between intraday sessions vary
about 4.3 times more than shot noise allows (P(0|1) 2.6, P(1|0) 5.7).

### 4.3 Variograms

`ddload.variogram` with `noise_var` on log10 values, intraday sessions only
(`noise.json: variograms.*_log10.mixed_only, summary`):

| Field | Semivariance at 2 to 4 h | Shot-noise part | Noise share | Semivariance at 744 to 1,488 h | Nugget over long lag | Excess over long lag |
| --- | --- | --- | --- | --- | --- | --- |
| RO | 0.018524 | 0.002311 | 0.125 | 0.042786 | 0.433 | 0.379 |
| P(0\|1) | 0.017901 | 0.003330 | 0.186 | 0.034887 | 0.513 | 0.418 |
| P(1\|0) | 0.067116 | 0.012330 | 0.184 | 0.123376 | 0.544 | 0.444 |

The pooled mean is dominated by the heaviest tails, so the standardized variogram (the mean
and median of `z^2` over all pairs in a lag bin, one noise model per pair) is the robust
version. Intraday sessions only, robust ratio by lag (`standardized_variograms.*_mixed_only`):

| Lag (h) | 0.5 to 2 | 2 to 4 | 4 to 6 | 6 to 9 | 18 to 30 | 54 to 84 | 204 to 372 | 744 to 1,488 | 1,488 to 3,624 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RO | 3.467 | 4.252 | 4.165 | 4.447 | 4.759 | 5.398 | 7.650 | 10.745 | 17.561 |
| P(0\|1) | 2.558 | 2.530 | 2.669 | 2.642 | 2.795 | 3.123 | 4.255 | 5.578 | 8.903 |
| P(1\|0) | 4.323 | 5.794 | 5.371 | 5.945 | 6.494 | 7.197 | 9.111 | 11.605 | 15.714 |

The 0.5 to 2 h bin holds 933 qubit pairs, that is a handful of session pairs; the 2 to 4 h bin
24,477. Pooled over all session kinds the shortest bins look lower still (RO 1.490 at 0 to
0.5 h, 2.451 at 0.5 to 2 h, `standardized_variograms.ro_linear`), but those pairs mostly
involve a daily session, whose larger computed noise lowers the ratio by construction.

### 4.4 Session pairs

To stop a few sessions counting as hundreds of qubit pairs, the robust ratio was computed once
per pair of whole sessions and summarized over session pairs (`noise.json: session_pairs`).
For RO, intraday pairs: 1 to 2 h, 5 session pairs, median 3.367; 3 to 4 h, 156 pairs, 4.209;
4 to 6 h, 106 pairs, 4.250; 6 to 9 h, 232 pairs, 4.384; 9 to 12 h, 209 pairs, 4.493. Below 1 h
there are 2 session pairs at 0 to 0.5 h (any kind, median 1.645) and 1 intraday pair at 0.5 to
1 h. Reading: from about 3 h to 12 h the excess is flat within the spread between session
pairs (interquartile range at 3 to 4 h: 3.583 to 4.948); whether it is lower below 2 h rests on
5 session pairs and cannot be claimed.

### 4.5 Do the daily sessions use 2,048 shots?

Three tests, none decisive:

1. **Semivariance of daily-only against intraday-only pairs at the same lag** (log10). Under
   the 2,048 reading the difference should equal the difference of the noise parts; under a
   4,096-shot estimate rounded onto the 1/2048 grid it should be near zero. For RO at 744 to
   1,488 h: observed 0.002106, predicted 0.002667 (2,048) or 0.000073 (4,096); for P(0|1):
   0.003169 against 0.003790 or 0.000117. These favour 2,048. But on the qubits whose median
   is at least 0.01 (where the delta method holds), RO gives -0.000649 against 0.001286 or
   0.000014, and P(1|0) -0.000548 against 0.003061 or 0.000067, which favour 4,096
   (`noise.json: shots_test`).
2. **Zero counts of P(1|0).** The share of exact zeros in intraday sessions fixes each qubit's
   Poisson mean; the predicted number of zeros in daily sessions differs by reading. On the
   same 61 qubits and 7,451 daily events, 312 zeros were observed; the predictions are
   bracketed from above by pooling over time (Jensen) and from below by local means: 189 to
   694 under 2,048 shots, 134 to 407 under a 4,096 count rounded half-to-even or floored, 49 to
   78 under rounding up (`noise.json: zero_count_test_p1g0, zero_count_test_p1g0_local`). The
   test excludes rounding up only.
3. **The grid itself** (section 1.3), which a 2,048-shot experiment produces and a
   post-processed 4,096-shot value could also produce.

So the shot count of the daily sessions is open. The conclusions of sections 4.2 to 4.4 rest
on intraday-only pairs, which do not depend on it.

### 4.6 What the excess is not

- **Discriminator re-calibration.** Over the threshold's lifetime, RO changes that straddle a
  threshold change are larger than those that do not when all pairs are pooled (median |z|
  ratio 1.106, p = 1.1e-29), but this is a composition effect: for intraday pairs it is 1.032
  (p = 0.037), and for intraday pairs 2 to 6 h apart 1.023 (p = 0.584; robust ratios 4.425
  against 4.227) (`noise.json: threshold_test`).
- **A device-wide common mode.** Over 345 intraday sessions the session's mean change explains
  1.38% of the variance of log10 RO changes, against 0.64% expected if qubits moved
  independently; session means sit between -0.056 and +0.055 decades (10% to 90%)
  (`noise.json: common_mode`). A shared component (an amplifier gain, a common drift) exists
  but is small.
- **Neighbours.** After removing each session's mean, the median correlation of RO changes is
  0.0122 for the 176 coupled pairs, 0.0079 at two hops and -0.0076 for 11,364 pairs at four or
  more hops; the difference is significant (Mann-Whitney p = 0.000115) but tiny; the strongest
  coupled pairs reach 0.195 (q83 and q96) (`noise.json: neighbours`).
- **Daily `T1` changes** (section 7.2).

### 4.7 Reading the root question for readout

What the evidence shows:

- Readout is the one family whose estimation noise is partly known, and the known part, the
  binomial shot noise, is about a quarter of the shortest-lag variability of RO (0.235 robust;
  0.125 on the pooled log10 scale), two fifths for P(0|1) and a sixth for P(1|0).
- The excess over shot noise is about three times the shot noise for RO (3.252 noise units)
  and is present at the shortest lag the cadence resolves (2 to 4 h). From there to a day it
  grows little (4.252 to 4.759 units), so on the reading rules of `01-data-layer.md` section 7
  it behaves as a nugget: noise, or dynamics faster than about 3 h.
- It is not mainly re-discrimination, not mainly device-wide, not shared by neighbours, and
  not driven by the daily `T1` values.

What the evidence does not show:

- Whether the excess is estimation error beyond the binomial or real fluctuation. Candidate
  estimation sources that the archive cannot see: state-preparation errors that vary from
  session to session (a residual excited population, which `init_error` shows is of order
  1e-3 and varies between sessions, adds directly to P(1|0)), session-to-session changes of
  the readout pulse or amplifier between the threshold fit and the assignment experiment, and
  any non-binomial dispersion of the counts. Candidate physical sources: TLS-driven `T1`
  changes on hour scales (Thorbeck et al. 2023, gate-error survey section 2.3; Klimov et al.
  2018 and Carroll et al. 2021, deep-engine survey section 3), switching within tens of
  milliseconds (Berritta et al. 2026, deep-engine survey section 3), and changes of
  measurement-induced transitions (Sank et al. 2016). The term "measurement noise" is
  therefore not used for the excess in this document.
- A correlation time: below 2 h the archive has 5 intraday session pairs.

What would falsify the "nugget" reading: a standardized variogram that rises clearly between
0.5 h and 3 h once enough short-lag session pairs exist (that would put a correlation time in
that range and favour fast real fluctuations, or fast procedural drift, over per-session
estimation error).

## 5. Spatial structure

Per-qubit medians of log10 values against the configuration coordinates (one coordinate set in
all 1,317 configuration files; 15 rows, 28 bridge qubits; degrees 1, 2 and 3 for 8, 100 and 48
qubits) and the coupling graph (176 undirected edges), Moran's I with 5,000 seeded
permutations (`spatial_temporal.json: spatial`):

| Field | Median of qubit medians (10%, 90%) | Moran's I (p) | On ranks (p) | Without q72 (p) | Spearman with x / y | Bridge vs row median (p) |
| --- | --- | --- | --- | --- | --- | --- |
| RO | 0.00903 (0.00562, 0.0412) | -0.196 (0.007) | -0.182 (0.018) | -0.207 (0.005) | -0.009 / -0.074 | 0.00928 vs 0.00903 (0.67) |
| P(0\|1) | 0.0127 (0.0083, 0.0454) | -0.187 (0.011) | -0.197 (0.008) | -0.204 (0.006) | -0.033 / -0.056 | 0.0125 vs 0.0127 (0.76) |
| P(1\|0) | 0.00525 (0.00244, 0.0339) | -0.195 (0.010) | -0.145 (0.053) | -0.196 (0.006) | 0.011 / -0.083 | 0.00458 vs 0.00537 (0.41) |
| `init_error` (116 qubits, 85 edges) | 0.00171 (0.00092, 0.00404) | -0.055 (0.61) | -0.015 (0.90) | -0.055 (0.62) | 0.171 / -0.031 | 0.00200 vs 0.00161 (0.083) |
| `measure_2` | 0.0134 (0.0046, 0.0720) | -0.430 (0.0002) | -0.442 (0.0002) | -0.456 (0.0002) | 0.052 / -0.022 | 0.00755 vs 0.0161 (0.006) |

There is no gradient across the chip (no Spearman with x or y beyond 0.17, Kruskal-Wallis by
row p = 0.87 for RO) and no bridge effect for `measure`, but neighbouring qubits tend to be on
opposite sides of the median: a checkerboard. It survives rank transformation and the removal
of q72. For `measure_2` it is twice as strong, and bridge qubits have about half the
`measure_2` error of row qubits. Interpretation, not shown: a heavy-hex device alternates
neighbouring qubit frequencies, and readout quality could depend on a qubit's frequency or on
its readout-resonator design; testing it needs qubit and resonator frequencies, which this
archive's cache does not carry. The worst RO qubits are q72, q83, q43, q131, q113 (medians
0.350, 0.126, 0.089, 0.077, 0.074).

The pattern is stable: the June and September per-qubit medians of RO rank the qubits with
Spearman 0.926. Across qubits RO follows `measure_2` (0.864) and `init_error` (0.739), and
P(0|1) follows P(1|0) (0.907) (`spatial.cross_field_spearman_of_medians`).

## 6. Faults and data quality

| Issue | Size | Effect | Source |
| --- | --- | --- | --- |
| Stale P(0\|1) on a rotating 9-qubit group (index residue 10, then 9, then 16, mod 17) | 11,515 records on 35 qubits, 27 with at least 100; lag up to 47.8 h | P(0\|1) in those records is the last daily value; RO is not the mean of the published pair. Recover the fresh value as `2 RO - P(1\|0)` (100% on the grid) | `sessions.json: stale_p0g1` |
| Two session kinds by count parity | 123 of 589 sessions on the 1/2048 grid | the shot count, and so the noise variance, differs or is unknown for daily sessions | `sessions.json: sessions` |
| Staggered stamps | 72,900 records (26.55%) | not a fault; the three stamps differ by seconds | `sessions.json: stagger` |
| Re-stamps inside one session | 257 RO events | a qubit stamped twice minutes apart; collapse to one | `noise.json: coverage` |
| Small sessions of 3 qubits | 9 sessions, 27 events | excluded from noise analysis | `sessions.json: sessions.small_sessions` |
| `measure_2` placeholder (error >= 1) on every qubit | 312 records in 2 files: 20260807T032159 (the first file of the field) and 20260810T140235 | mask before events; the 2026-10-05 document's "one device-wide glitch" is two at this ref | `profiles.json`, `thresholds_m2_init.json: measure_2.placeholder_files` |
| `init_error` below 1e-6 | 540 records, 59 qubits | degenerate estimates; changes of up to 24.9 decades | `profiles.json`, `thresholds_m2_init.json` |
| `init_error` absent for 40 qubits, stale for others | 40 never; q40 and q117 one stamp event each | absence tracks bad readout (section 7.3) | `thresholds_m2_init.json: init_error` |
| P(1\|0) exactly 0 | 2,468 records | log undefined | `profiles.json: p1g0_exact_zero` |
| Thresholds in historical files | of 42 threshold changes in historical files, 5 coincide with a readout session; 223 of 285 in live files | a historical file's threshold may not be contemporaneous with its readout values (inference) | `thresholds_m2_init.json: thresholds.threshold_change_vs_readout_session` |
| Measured rule on quantized fields | drops 1,745 RO and 3,180 P(1\|0) re-measurements | removes exact zero changes; biases change statistics | `profiles.json` |
| Visible cadence varies by period | 5.68 to 3.07 sessions a day | rates across months are not comparable without a coverage model | `sessions.json: sessions.by_month` |

The 40 qubits without `init_error` are not a pattern of the index (residues mod 17 spread 0 to
4 per class) or of degree (1 of 8 degree-1, 18 of 100 degree-2, 21 of 48 degree-3 qubits)
(`init_error.never_present_mod_17_counts, never_present_by_degree`).

## 7. Relationships

### 7.1 Inside the scope

- **RO, P(0|1), P(1|0).** RO is their mean (section 0). Across qubits P(0|1) and P(1|0) move
  together (Spearman of medians 0.908, `t1_link.json: between_qubits`): most of each is the
  shared overlap error. P(0|1) is the larger in 87.63% of events, the median ratio is 2.0 and
  the median A is 0.00635 (`t1_link.json: pooled`).
- **Thresholds and readout sessions.** A threshold change needs no readout stamp: 99 of 327
  change files have no session in their interval, 62 of them live files. Conversely 211 files
  have a session without a change. The intraday sessions carry the threshold updates (208 of
  343 against 20 of 97 daily ones). `measure` and `measure_2` thresholds change in the same
  file 109 times out of 142 and 124 changes over `measure_2`'s lifetime; their per-qubit
  medians correlate at Spearman 0.735 and the `measure_2` threshold is a median 0.445 of the
  `measure` one (`thresholds_m2_init.json: thresholds`). The threshold's values: 84.56%
  negative, 147 of 156 qubits change sign during the lifetime, and the per-qubit standard
  deviation is a median 0.715 of the median absolute value. Reading: the number is a position
  along a projection IBM re-defines when it re-calibrates (IBM lists readout angles among the
  monitored parameters); without that projection it has no stable physical meaning on its own.
- **`measure_2` against `measure`.** Per-qubit median ratio of errors 1.25 (10%: 0.79, 90%:
  2.87); 60.3% of qubits have a worse `measure_2`; device medians 0.0139 against RO 0.00977 in
  the same files; across qubits Spearman 0.852, within a qubit (log values demeaned) 0.382
  over 8,112 events (`thresholds_m2_init.json: measure_2`). The shorter instruction is worse
  for most qubits, by a factor that varies widely between qubits.
- **`init_error` against P(1|0) and RO.** Across qubits: P(1|0) 0.822, P(0|1) 0.602, RO 0.717.
  Within a qubit, records whose `init_error` stamp is within 10 minutes of the P(1|0) stamp
  (4,938 records, 109 qubits): P(1|0) 0.722, RO 0.494. P(1|0) over `init_error` per qubit is a
  median 1.95 (10%: 1.38, 90%: 2.61); P(1|0) is below `init_error` in 14.8% of records
  (`init_error.*`). Reading: a residual |1> population adds directly to P(1|0), so the strong
  link is expected; P(1|0) below `init_error` means the two are separate estimates, possibly
  with different protocols (IBM does not document the initialization measurement). Its stamps
  are only partly tied to readout sessions: 6,028 of 25,158 stamp events fall inside a session,
  the median distance to the nearest one is 21 minutes, and the RO stamp minus the
  `init_error` stamp in the same record ranges from -9.8 h to +64 h (10% to 90%).

### 7.2 The assigned link: readout against `T1` decay during the readout

Expected decay for each readout event, from the `T1` and t_ro carried in the same file:
`d_full = 1 - exp(-t_ro/T1)`, median 0.0130; `d_half` with t_ro/2, median 0.00654. The median
P(0|1) is 0.0142, so the expected decay is of the same order as the whole of P(0|1)
(`t1_link.json: pooled`).

| Test | Result | Source |
| --- | --- | --- |
| Pooled over records: P(0\|1) against d_full | Spearman 0.059 (P5 at the older ref: 0.06) | `pooled` |
| Pooled: A against d_full | 0.158 | `pooled` |
| Across qubits (medians): P(0\|1) against d_full | 0.016 (p = 0.84) | `between_qubits` |
| Across qubits: A against d_full | 0.423 (p = 3.9e-8); Theil-Sen slope 0.310 (0.209 to 0.437) | `between_qubits` |
| Across qubits: P(1\|0) against d_full (control) | -0.087 (p = 0.28) | `between_qubits` |
| A over d_full per qubit | median 0.464 (10%: 0.094, 90%: 0.687); A below d_half for 59.0% of qubits and below d_full for 96.2% | `between_qubits` |
| Lower-error half of the qubits (80) | A against d_full 0.159 (p = 0.16), slope 0.100 (0.000 to 0.219) | `between_qubits_low_error_half` |
| Monthly, across qubits, A against d_full | between 0.330 and 0.430 in every month | `monthly` |
| Within qubit, consecutive daily sessions with a new `T1`: change of log P(0\|1) against change of log `T1` | -0.014 (p = 0.097, 14,909 changes); P(1\|0) control 0.012 | `within_qubits_even_sessions` |
| The same, `T1` stamped within 3 h of the readout | -0.049 (p = 9.4e-6, 8,247 changes) | `within_qubits_even_sessions` |
| `T1` below half its qubit median (daily sessions) | 592 records on 143 qubits; P(0\|1) relative to its qubit median 0.997 against 1.000 normally (p = 0.28), although d_full rises by a median 0.0182 | `t1_dip_event_study_even_sessions` |
| The same, `T1` within 3 h | 223 records on 111 qubits; 1.000 against 1.000 (p = 0.72) | `t1_dip_event_study_t1_within_3h` |
| t_ro 1,560 to 1,700 ns (section 7.4) | A +0.0016 (7 d) and +0.0012 (14 d); predicted from the length alone +0.00094 (full) and +0.00047 (half) | `length_changes.json` |

Reading: decay during the readout is visible where it should be, in the asymmetry and between
qubits, with about half the full-length decay showing up in A, which matches an effective
decay time of half the window (Krantz et al. eq. 173). **[Verification 2026-10-06: overstated. The length change gives A +0.0015 against +0.00093 predicted for the full window (1.6 times) and +0.00047 for the half window (3.1 times), which favours full-window decay or more, not half; the two readings in this document conflict. Residual excited population also lowers A, so A/decay of 0.46 does not identify an effective time. `extra_check.json`]** The slope weakens in the lower-error
half, so part of the cross-qubit link may come through qubits that are bad on both counts.
Over time, the daily `T1` values do not predict the next readout session's P(0|1), even when
`T1` halves. Two readings fit: the `T1` dips the daily round reports do not persist for the
hour or more until a readout session, which is what hour-scale or faster TLS switching would
produce; or a part of the `T1` dips are estimation artefacts of the `T1` fit. The archive does
not separate them; `02-coherence.md` owns `T1` itself.

### 7.3 `init_error` presence against readout quality

The 40 qubits that never carry `init_error` have a median RO of 0.0331 against 0.0071 for the
rest (Mann-Whitney p = 1.3e-20) and a median P(1|0) of 0.0272 against 0.0037 (p = 6.1e-21)
(`init_error.never_present_vs_others_*`). Reading (not documented by IBM): the value is
withheld where the assignment error is too large for the residual population to be estimated.

### 7.4 The readout-length natural experiments in full

Per-qubit medians over windows before and after each change, 6 h guard on each side; device
statistic the median over qubits of log10(after/before); placebo the same statistic on every
other day (`length_changes.json`):

| Change | Window | RO | P(0\|1) | P(1\|0) | Share of qubits up (RO) | Placebo 5% / 95% (RO) | `T1` control |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1,560 to 1,700 ns, 2026-06-08 | 7 d | -0.137 (p = 9.4e-26) | -0.079 | -0.269 | 0.019 | -0.039 / +0.030 | -0.017 (placebo -0.051 / +0.108) |
| | 14 d | -0.144 (p = 5.6e-26) | -0.093 | -0.278 | 0.019 | -0.022 / +0.036 | +0.007 |
| 1,700 to 1,660 ns, 2026-07-30 | 7 d | +0.003 (p = 0.14) | -0.004 | +0.008 | 0.539 | -0.039 / +0.030 | -0.006 |
| | 14 d | +0.006 (p = 0.053) | +0.004 | 0.000 | 0.558 | -0.022 / +0.036 | -0.009 |

At the first change the device median RO went from 0.0114 to 0.00806 (7 d), and no placebo day
reached the observed change (share of placebo days at least as large: 0.0). Intraday-only
windows give the same picture (RO -0.141, P(1|0) -0.269). Reading: a longer integration
improves the separation of the two clouds, which lowers both errors, and the longer window adds
decay, which raises A; both happened, and A rose by the predicted order. **[Verification 2026-10-06: weakened. The change in A of +0.00146 is not outside the placebo range of other days (5% to 95%: -0.00146 to +0.00129; placebo maximum +0.00153, 70 days), so the Wilcoxon p-value does not show a length effect on A; the drop in RO does stand out (observed -0.138 against placebo minimum -0.084). `extra_check.json`, `length_link_check.json`]** The same file is the
first to carry `measure.threshold`, and the reset length moved with t_ro, so a broader change
of IBM's readout procedure on that date is as consistent with the data as the length alone. At
the second change the decay prediction (-0.0003 full, -0.00015 half) is smaller than the
observed noise in A (-0.00012 and +0.00012), and nothing moved.

## 8. Use cases and why each field matters

| Field | Use in this project | Use in the literature | Why it matters |
| --- | --- | --- | --- |
| P(0\|1), P(1\|0) | the per-qubit assignment channel of the noise model; the known shot-noise variance of each value is the one physics fact a readout forecaster can use (feature-patterns document, section 4) | tensor-product and correlated readout-mitigation models are parameterized by these error rates (Bravyi et al. 2021); M3 works with assignment matrices in a subspace (Nation et al. 2021); TREX needs no model (van den Berg et al. 2022); Qiskit Aer's backend noise model includes a single-qubit readout error on every measurement (Qiskit Aer documentation) | readout is the largest single-qubit error on the device (median RO 0.0100 against `sx`'s 0.000312, `01-data-layer.md` section 3), and its asymmetry carries the decay information |
| RO | target-1 readout family (feature-patterns document, sections 4 and 5); never recompute it from the published pair without checking the stamps | noise-aware qubit mapping on IBM devices (Murali et al. 2019, Tannu and Qureshi 2018, gate-error survey section 2.1); measuring readout just before execution beats the daily calibration for mapping (Wilson et al. 2020, gate-error survey section 2.1); calibration-based digital twins (Bautra et al. 2026, gate-error survey section 2.5) | the session cadence makes it the densest series in the archive (about 590 events per qubit) |
| t_ro, reset and measure-reset lengths | the idle time a measurement or reset imposes on other qubits; the decay window for the readout link | mid-circuit measurement idling is a known cost, and IBM names shortening it as a focus (IBM documentation) | t_ro is 70 times the `sx` length; reset adds exactly one `x` |
| Thresholds | a marker of discriminator re-calibration events (device-wide) | discrimination in the IQ plane (Krantz et al. 2019) | a procedure event the archive records explicitly; no physical level on its own |
| `measure_2` | a separate readout instruction with its own error for mid-circuit use | randomized benchmarking of mid-circuit measurements, including effects on unmeasured neighbours (Govia et al. 2023) | worse than `measure` for most qubits, with a strong checkerboard |
| `init_error` | residual \|1> population, a direct part of P(1\|0); missing for 40 qubits | residual excited-state population sets a floor on state preparation (Jin et al. 2015) | missing exactly where readout is poor; usable only with the ADR-017 skip treatment already adopted for it (`docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md`) |

## 9. Open questions, and what measurement would settle each

1. **Is the excess over shot noise estimation error or fast real change?** Settled by
   back-to-back assignment experiments on our own hardware time (minutes apart, then hours
   apart) on a few qubits, which would give the standardized variogram below 2 h directly; in
   the archive, by accumulating more than a handful of intraday session pairs closer than 2 h.
2. **How many shots do the daily sessions use?** IBM documentation, or an own experiment with
   known shots compared against the published values of the same session. Until then, every
   noise statement should be made on intraday sessions, as here.
3. **Why is P(0|1) withheld intraday for one qubit in 17, and why does the group rotate?** The
   rotation dates (2026-07-25, 2026-08-25) and the residue pattern are measured; the mechanism
   needs IBM's description of how the intraday assignment experiment is batched.
4. **What is the initialization procedure behind `init_error`, why is it withheld for 40
   qubits, and why does it return values below 1e-6?** IBM documentation; the presence pattern
   (section 7.3) is the testable hint.
5. **Is the checkerboard a frequency effect?** Needs qubit and readout-resonator frequencies
   (not in this cache); if they exist in the snapshots, per-qubit RO against frequency and
   detuning would settle it.
6. **Was the 2026-06-08 drop the length or the procedure?** Not separable in the archive; an
   own experiment varying only the integration length would be needed.
7. **Do `T1` dips persist into readout?** Needs `T1` and readout measured in the same session,
   for example an own experiment interleaving `T1` and assignment measurements on a qubit with
   a known TLS.
8. **Is there a weekly component of P(1|0)?** A session-level test (one value per session, with
   the session common mode removed) would remove the clustering that inflates the present
   p-values.

## 10. Reproduce (exact commands) and results files

From the repository root, with the cache of `01-data-layer.md` built (or `DD_CACHE` set), using
a Python with numpy and scipy (on the lead's laptop `C:/t/venv/Scripts/python.exe`). Scripts are
independent; each takes under 70 s on the laptop.

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/sessions.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/profiles.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/noise.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/length_changes.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/thresholds_m2_init.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/t1_link.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/readout/spatial_temporal.py
```

| Script | Results file | Contents |
| --- | --- | --- |
| `rocommon.py` | (helper) | notation, stamp events, record classes, fresh P(0\|1), sessions and their kinds, per-event shot-noise variance |
| `sessions.py` | `results/readout/sessions.json` | stamp classes, stale P(0\|1) groups, sessions, kinds, hours, `T1`-round alignment, cadence by month |
| `profiles.py` | `results/readout/profiles.json` | ranges, tails, grids, parity, events under both rules, memory, lengths and their identities |
| `noise.py` | `results/readout/noise.json` | P5 replication, standardized changes, variograms, session pairs, shots tests, threshold test, common mode, neighbours, summary |
| `length_changes.py` | `results/readout/length_changes.json` | the two natural experiments with placebo distributions and the decay prediction |
| `thresholds_m2_init.py` | `results/readout/thresholds_m2_init.json` | thresholds, `measure_2`, `init_error` |
| `t1_link.py` | `results/readout/t1_link.json` | the readout against `T1` decay link |
| `spatial_temporal.py` | `results/readout/spatial_temporal.json` | device map, change points, monthly levels, seasonality |

**Choices, samples and exclusions (nothing else is capped or sampled):** session gap 15 min and
same-session window 10 min (sensitivity of the staggered count to the window: 16,627 records
within 60 s up to 75,096 within 3,600 s, `sessions.json: stagger.not_same3_records_by_max_gap`);
sessions with fewer than 100 qubits (9) excluded from noise work; 257 within-session re-stamps
collapsed to the last; 163 RO events without a same-session P(1|0) or in a small session
dropped; 644 zero P(1|0) events dropped from log analyses; `init_error` values below 1e-6
masked where stated; `measure_2` placeholders masked; thresholds never masked. Session pairs
only up to 12 h apart. Length windows need at least 3 events per qubit; placebo days step by
one day, skip days within one window of either change (104 placebo days at 7 d, 63 at 14 d),
and need at least 100 qubits. Moran's I uses 5,000 permutations with seed 20261006. Neighbour
correlations use intraday-to-intraday changes in sessions with at least 100 qubits (345) and
need more than 30 shared sessions per pair. Seasonality drops each qubit's first and last 6
events. The `T1` link drops 23 events without a `T1`; within-qubit statistics need at least 10
daily events per qubit; the `init_error` within-qubit test needs at least 20 same-session
records per qubit (109 qubits). Binary segmentation: penalty `3 sigma^2 ln n`, minimum segment
15 sessions (device) or 30 events (qubit), at most 8 change points (the device series did not
reach it; 5 qubits did). Display lists are the 10 worst qubits, 6 busiest weeks and 5 most
correlated coupled pairs. The shots test uses three lag bins and two qubit subsets as listed in
`noise.json`.

## 11. Sources

New sources fetched in this session: 14 (one further fetch returned an unrelated paper under a
mistyped identifier and is not cited).

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum, "View backend details" (QPU information guide) | https://quantum.cloud.ibm.com/docs/en/guides/qpu-information | fetched 2026-10-06 | definitions of P(0\|1), P(1\|0), RO, readout length, `init_error`; `measure_2` named for mid-circuit measurement |
| IBM Quantum, "Monitoring, calibrations, and benchmarking" | https://quantum.cloud.ibm.com/docs/en/guides/calibration-jobs | fetched 2026-10-06 | hourly monitoring of readout angles, amplitudes and discriminator threshold; triggered calibrations; daily benchmarking |
| IBM Quantum, ConvertToMidCircuitMeasure (qiskit-ibm-runtime API) | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/transpiler-passes-convert-to-mid-circuit-measure | fetched 2026-10-06 | `measure_2` is the default `MidCircuitMeasure` instruction |
| IBM Quantum, "Execute dynamic circuits" | https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits | fetched 2026-10-06 | `MidCircuitMeasure` maps to `measure_2`, adds less overhead; shortening it is a focus |
| Qiskit, ResetAfterMeasureSimplification | https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.transpiler.passes.ResetAfterMeasureSimplification | fetched 2026-10-06 | reset on IBM systems is a measurement followed by a conditional `x` |
| Qiskit Aer, NoiseModel (`from_backend`) | https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.NoiseModel.html | fetched 2026-10-06 | backend noise models include a single-qubit readout error on every measurement (which property fields is not stated) |
| Krantz et al., A Quantum Engineer's Guide to Superconducting Qubits (2019) | arXiv:1904.06560 | fetched 2026-10-06; section V C to V D and eq. 172 to 173 read in the full text | IQ-plane discrimination, separation error, decay during readout with `tau_ro = tau_rd + tau_s/2` |
| Walter et al., Realizing Rapid, High-Fidelity, Single-Shot Dispersive Readout of Superconducting Qubits (2017) | arXiv:1701.06933 | fetched 2026-10-06 (abstract) | readout fidelity limited mainly by the qubit lifetime |
| Sank et al., Measurement-induced state transitions in a superconducting qubit: Beyond the rotating wave approximation (2016) | arXiv:1606.05721 | fetched 2026-10-06 (abstract) | measurement-induced transitions as a source of P(1\|0) and leakage |
| Jin et al., Thermal and Residual Excited-State Population in a 3D Transmon Qubit (2015) | arXiv:1412.2772 | fetched 2026-10-06 (abstract) | residual excited population of about 0.1% at saturation on that device |
| Bravyi et al., Mitigating measurement errors in multi-qubit experiments (2021) | arXiv:2006.14044 | fetched 2026-10-06 (abstract) | readout mitigation from calibration error rates, tensor-product and correlated models |
| Nation et al., Scalable mitigation of measurement errors on quantum computers (2021) | arXiv:2108.12518 | fetched 2026-10-06 (abstract) | M3, subspace assignment-matrix mitigation |
| van den Berg, Minev and Temme, Model-free readout-error mitigation for quantum expectation values (2022) | arXiv:2012.09738 | fetched 2026-10-06 (abstract) | TREX, model-free mitigation |
| Govia et al., A randomized benchmarking suite for mid-circuit measurements (2023) | arXiv:2207.04836 | fetched 2026-10-06 (abstract) | benchmarking mid-circuit measurements and their effect on neighbours |
| Thorbeck et al., TLS Dynamics in a Superconducting Qubit Due to Background Ionizing Radiation (2023) | arXiv:2210.04780 | existing survey: `docs/roadmap/2026-10-05-gate-error-literature-survey.md` section 2.3 | hour-scale TLS dynamics as a candidate for fast change |
| Klimov et al., Fluctuations of Energy-Relaxation Times in Superconducting Qubits (2018) | arXiv:1809.01043 | existing survey: `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` section 3 | TLS-driven `T1` fluctuations |
| Carroll et al., Dynamics of Superconducting Qubit Relaxation Times (2021) | arXiv:2105.15201 | existing survey: 2026-10-04, section 3 | autocorrelated `T1` |
| Berritta et al., Real-Time Adaptive Tracking of Fluctuating Relaxation Rates (2026) | arXiv:2506.09576 | existing survey: 2026-10-04, section 3 | `T1` switching within tens of milliseconds |
| Wilson, Singh and Mueller, Just-in-time Quantum Circuit Transpilation Reduces Noise (2020) | arXiv:2005.12820 | existing survey: 2026-10-05, section 2.1 | fresh readout measurement beats daily calibration for mapping |
| Murali et al., Noise-Adaptive Compiler Mappings for NISQ Computers (2019); Tannu and Qureshi (2018) | arXiv:1901.11054; arXiv:1805.10224 | existing survey: 2026-10-05, section 2.1 | readout-aware mapping |
| Bautra, Dimitrijevs and Yakaryilmaz, Evaluating Calibration-Based Digital Twins (2026) | arXiv:2603.14607 | existing survey: 2026-10-05, section 2.5 | digital twins from calibration data, including readout errors |

Project sources: `01-data-layer.md` (field semantics, identities, coverage);
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P1, P2, P5, P7);
`docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` (the `init_error`
schema start and the ADR-017 skip treatment); `scripts/feature_patterns.py` (the measured event
rule and P5's shot-noise code, re-run in `noise.py: old_method`).

## Verification (2026-10-06)

Verifier note, appended; the text above is unchanged except for inline markers. Provisional:
same ref, same cache, lead's laptop. The analyst stopped before its own self-check.

**Re-run.** All seven owner scripts were re-run from a scratch copy (so the committed results
were not overwritten) and every results JSON reproduces field for field (0 differences
besides `measured_utc`): `sessions`, `profiles`, `noise`, `length_changes`,
`thresholds_m2_init`, `t1_link`, `spatial_temporal`. Fresh, independent scripts (ddload only)
are in `analysis/verify/readout/` (`v_records.py`, `v_noise.py`, `v_length_link.py`,
`v_extra.py`); results in `results/verify/readout/` (`records_check.json`,
`noise_check.json`, `length_link_check.json`, `extra_check.json`). Pinned ruff check and
format pass on that folder.

| Claim | Document value | Recomputed | Match |
| --- | --- | --- | --- |
| Records with three identical stamps | 188,100 (68.51%) | 188,100 (0.6851) | yes |
| Staggered records; stale P(0\|1) records | 72,900; 11,515 | 72,900; 11,515 | yes |
| Mean-rule failures, of which stale | 11,263; 11,258 | 11,263; 11,258 | yes |
| Rotating group residues and first/last files | 10, 9, 16 | 10 to 20260725, 9 to 20260825, 16 since | yes |
| Sessions (all, >= 100 qubits, even, mixed, small) | 598, 589, 123, 466, 9 | same | yes |
| Even / mixed sessions within 3 h of a T1 round | 87.0% / 15.7% | 0.8699 / 0.1567 | yes |
| RO standardized semivariance, intraday, 2 to 4 h | 4.252 (24,477 pairs) | 4.253 (24,477 pairs) | yes |
| Consecutive intraday share within 2 sd | 0.6445 | 0.6435 (n 72,525; different pairing) | approx |
| Iid-binomial placebo through the same plug-in rule | not in document | ratio 1.005, 95.2% within 2 sd | new: no plug-in bias |
| 2026-06-08 RO change, 7 d, median log10 | -0.137, 1.9% up | -0.138, 1.9% up | yes |
| Placebo range 7 d (5%/95%) | -0.039 / +0.030 (104 days) | -0.0375 / +0.0305 (70 days; stricter exclusion) | approx |
| 2026-07-30 change, 7 d | +0.003 | +0.0014 | yes (inside placebo) |
| A against decay, across qubits | Spearman 0.423 | 0.394 (fresh-only records) | approx |
| P(0\|1) against decay, across qubits | 0.016 | 0.034 | yes (null) |
| Moran's I of RO | -0.196 (p 0.007) | -0.1957 (p 0.009) | yes |
| 40 qubits without `init_error`; RO median | 0.0331 vs 0.0071 | 0.0314 vs 0.0076 | approx (median definition) |
| init_error against P(1\|0), across qubits | 0.822 | 0.850 | approx (event versus median) |
| Threshold change files, qubits moved each | 327, all 156 | 327, 156 | yes |
| Reset minus readout length; measure error = RO | 24 ns; identical | 24 ns only; identical in all 274,560 | yes |

**Claims challenged.**

| Claim | Verdict | Why |
| --- | --- | --- |
| Summary 2: RO uses a fresh P(0\|1) the document does not carry, shown by the 1/4096 grid | weakened | The grid test is satisfied by arithmetic (placebo with shuffled P(0\|1): 100%). The rotating group and its dates are real; the mechanism is an inference. |
| Summary 5 and 6, section 4.7: the excess over shot noise is not a plug-in or binomial artefact | upheld | Iid binomial counts at each qubit's own level give robust ratio 1.005; the data give 4.25. The attribution stays open, as the document says, and no "measurement noise" label is used. |
| Summary 14: checkerboard, with a frequency interpretation | weakened | Explained by degree class (Moran's I after removing it: -0.047, p 0.59); RO also differs strongly by degree. The document lists degrees but never tests RO against them. |
| Section 7.2: A matches an effective decay of half the window | weakened | The length experiment gives 1.6 times the full-window and 3.1 times the half-window prediction; the two tests disagree and excitation also enters A. |
| Summary 7: the 06-08 change is a large natural experiment; A rose as predicted | RO part upheld, A part weakened | RO drop is 3.5 times the largest pre-change drift (-0.02 to -0.04) and beyond the placebo minimum (-0.084). The A rise (+0.00146) lies inside the placebo extremes (max +0.00153). |
| Section 3.3: no seasonality of practical size; P(1\|0) weekday not excluded | upheld | At session level (585 sessions) the weekday test gives p = 0.18, so the record-level p of 4.5e-5 was clustering, as the document suspected. |
| Summary 3: even sessions have probability 2^-312 by chance | weakened (minor) | Assumes 312 independent fair-parity counts; small counts and zeros are not fair. The 123 against 466 split itself reproduces. |
| Section 7.2: T1 dips do not reach P(0\|1) | upheld as reported | Not re-run in detail; both readings given by the document are labelled and no attribution is claimed. |

Not re-verified: the stale group's freshness by session kind (1,086 of 1,103 against 9 of 4,194);
my probe used a different population and is not comparable.

**Sources spot-checked (fetched 2026-10-06).** IBM qpu-information: P(0|1), P(1|0), RO and
readout length definitions confirmed; `init_error` carries an extra condition (prior
experiment prepared |1>), marked inline. Krantz et al., arXiv:1904.06560: title and author
confirmed from the abstract page; eq. 173 and `tau_ro` were not visible in that page, so the
equation citation rests on the analyst's full-text read and is unconfirmed here. Govia et al.,
arXiv:2207.04836: title confirmed, spectator-qubit effects confirmed.

**Rule check.** No U+2014 in the document or the owner's scripts; provisional banner, ref,
basis and machine present; no `docs/numerical-claims.md` rows added by this scope. Numbers
without a results field: none found in the sections read; the section 0 figures all trace to
a named field. Section 11 says 14 new sources and lists 14, within the limit of 15.
