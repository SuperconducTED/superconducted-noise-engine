# 02 · Coherence: T1, T2 and the rates derived from them

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: reconcile it
later by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Ref: `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`. Basis: all 1,760 `ibm_fez` snapshot files at that
ref (2026-05-13 to 2026-10-06), 156 qubits; 20,063 `T1` events and 20,626 `T2` events under
the measured rule (19,907 and 20,471 without each qubit's first event), and 19,899 paired
`T1`/`T2` events. Measured on 2026-10-06 on the lead's laptop (Windows 11, CPython 3.12,
numpy 2.4.4, scipy 1.17.1), from the cache of `01-data-layer.md` read through
`analysis/ddload.py`. Nothing here is registered in `docs/numerical-claims.md`. Every number
below is a field of a JSON file in `results/coherence/` (written by the scripts in
`analysis/coherence/`), of `results/data-layer/*.json`, or a figure quoted from a named
repository document or a fetched source. The advisor's answers and decisions A1 to A9 remain
open; nothing here records or implies an approval.

## 0. Summary

- **IBM reports `T2` from a Hahn echo** (IBM documentation, fetched 2026-10-06), so the
  derived pure-dephasing rate `Gamma_phi = 1/T2 - 1/(2 T1)` is an echo rate: quasi-static
  frequency noise is refocused before it reaches this number. The archive carries one value
  and one date per record and no fit uncertainty.
- **`T1` and `T2` of a qubit are stamped in the same round, seconds apart.** In all 19,899
  paired events the `T2` stamp follows the `T1` stamp by 1 to 112 s (98.7% within 10 s), and a
  whole device-wide round is stamped within 0.05 to 1.83 minutes. Interpretation: the stamp
  is a batch write time per round, not a per-qubit measurement time (`profile.json`).
- **Distributions are log-skewed to the low side.** `T1` per event: median 126 us, 1% 39.5 us,
  99% 261 us, log10 skew -1.13, excess kurtosis 4.8. `T2`: median 92.9 us, 1% 6.46 us. Only
  39% of the variance of log `T1` lies between qubits (82% for `T2`, 88% for `Gamma_phi`), so
  `T1` is mostly a within-qubit quantity and `T2` mostly a between-qubit one
  (`profile.json`, `variance_split`).
- **The non-persistent component is large and decorrelates faster than the shortest lag
  observed (3.86 h).** The `T1` semivariogram is 0.0146 decades² at 18 to 30 h and 0.0179 at
  744 to 1,488 h (ratio 0.82); after 2026-08-05 the autocorrelation of per-qubit deviations
  is -0.009 at lag 1 and near zero at every lag to 5 (`nonpersistent.json`, `temporal.json`).
- **That component is not independent per-experiment estimation error, for at least half of
  its variance, under one stated assumption.** Same-round deviations of log `T1` and log `T2`
  from their running levels correlate at 0.70 (Pearson; Spearman 0.69), positively in all 155
  qubits. If the two fits' errors are independent, rho² = 0.49 is a lower bound on the share
  of each deviation's variance that is a shared real change. The slope of `T2` on `T1`
  deviations rises with `T2/(2 T1)` across qubits (Spearman 0.92) and exceeds it in every
  tertile, and `T1` and `Gamma_phi` deviations correlate at -0.32, the opposite sign an
  independent `T1` error would produce (`nonpersistent.json`, `t1_t2_comovement`).
- **Low-`T1` dips are real drops that `T2` follows.** 630 of 19,595 `T1` events (3.2%), on
  151 qubits, sit at least a factor of two below the running level. In 98% of them `T2` is
  also below its level, by a median of -0.234 decades against -0.194 predicted from the `T1`
  drop alone (Spearman 0.81 between observed and predicted) (`dips.json`).
- **Dips last one round and do not persist beyond chance.** 574 of 602 episodes are a single
  event; recovery takes a median of 25.0 h (the next round). Consecutive dip pairs: 28
  observed against a shuffled mean of 21.6 (5% to 95%: 15 to 29), p = 0.10; from 2026-06-28,
  24 against 22.1, p = 0.39. Thirteen qubits show a two-level shape, without day-scale dwell
  (9 low-low pairs against 12.7 expected).
  **[Verification 2026-10-06: weakened. "Do not persist beyond chance" is absence of evidence from a test of 28 pairs: the observed excess is about 30% (28 against an analytic exchangeable expectation of 21.1, p = 0.10), and at 25 h sampling a dwell of a few hours could not produce consecutive dips anyway. Single-round dips are consistent with the data, not demonstrated.]**
- **The size of the component is not a stable property of the device.** The round-to-round
  robust semivariance of log `T1` was between 0.000404 and 0.000686 in the 13 rounds of
  2026-05-15 to 2026-05-27, rose after a device-wide jump of +0.132 decades at the
  2026-05-28T06 round, and stepped again at 2026-06-26/29 (median 0.0092 before, 0.0146 after,
  Pettitt p = 5.5e-12) (`regime.json`). Physical TLS dynamics do not pause device-wide for
  twelve days; either the device's environment or the way the values were produced changed,
  and the archive cannot tell which.
- **Shot noise cannot explain the component** unless IBM's whole `T1` fit used fewer than
  about 74 to 167 total shots (median readout; 414 to 783 with 99th-percentile readout) or
  557 to 890 for the `T2` echo. A published budget (Klimov et al. 2018, 80,000 shots, Google)
  would give a floor of 0.14% of the `T1` nugget (`nonpersistent.json`, `shot_noise_floor`).
- **`T2 > 2 T1` is rare and is a `T1` dip that `T2` did not follow.** 20 paired events (0.10%)
  on 15 qubits; at those events `T1` sits a median 0.30 decades below its level while `T2`
  sits at its level (-0.013). Record level: 424 records (0.155%) on 18 qubits
  (`profile.json`).
- **No neighbour structure and almost no device-wide common mode.** Moran's I of per-qubit
  median log `T1` on the coupling graph is -0.017 (p = 0.86); the round median explains 5.5%
  of the variance of `T1` deviations (4.3% from 2026-06-28); coupled pairs' residual
  correlation (-0.005) equals that of pairs four or more hops apart (-0.004) (`spatial.json`).
- **No value seasonality by hour or weekday.** Round-level Kruskal-Wallis p: hour 0.69
  (`T1`), 0.95 (`T2`); weekday 0.89, 0.86; none of the eight tests passes the Bonferroni
  threshold 0.00625 (`temporal.json`).
- **Stale values exist.** `q72`'s `T1` (1,126 files older than 72 h), `q11`'s `T1` (876),
  `q17`'s `T1` (482 files, at most 2,206 h old, until 2026-07-14) and `q149`'s `T2` (351)
  were carried forward without re-measurement (`profile.json`, `staleness`).
- **ADR-027's snapshot lambda is dominated by a few qubits.** The 10% most dephasing-limited
  qubits carry a median 48% of the snapshot sum of lambda (mean over median 2.30); for gamma
  the share is 20% (mean over median 1.12) (`adr027.json`).
- **Correction of an earlier wording.** `docs/roadmap/2026-10-05-feature-patterns-and-method.md`
  (§0 and P2) describes every series as a level "observed through measurement noise". For
  `T1` and `T2` that attribution is contradicted for at least half of the non-persistent
  variance under the independence assumption above; the component is better described as
  real same-round changes of the qubit, plus an unquantified remainder.
  **[Verification 2026-10-06: weakened. The 0.70 correlation is reproduced, but it shows a component SHARED by the `T1` and `T2` experiments of a round. A shared artefact of IBM's procedure is not excluded (section 4.2 says so); "contradicted" and "real" are stronger than that. Read: at least half of the variance is shared between the two fits.]**

## 1. The fields and how IBM produces them

| Field | Meaning | How it is produced (source) |
| --- | --- | --- |
| `q.T1` (us) | Energy-relaxation time: the average duration a qubit stays in its excited state before decaying to the ground state | IBM documentation "View backend details" (fetched 2026-10-06) defines it; the fitting procedure IBM runs is not published |
| `q.T2` (us) | Phase-coherence time of a superposition | IBM: "reported from a Hahn echo sequence" (same page). Properties update after the calibration sequence completes, each value paired with the timestamp of the last calibration |
| `1/T1` (1/us) | Relaxation rate `Gamma_1` | Krantz et al. 2019, eq. 41 (fetched 2026-10-06) |
| `Gamma_phi = 1/T2 - 1/(2 T1)` (1/us) | Pure-dephasing rate; `1/T2 = Gamma_1/2 + Gamma_phi` | Krantz et al. 2019, eq. 42; defined only when both decays are exponential |
| `s = T2/(2 T1)` | Fraction of the `2 T1` limit reached; `T2 <= 2 T1` always holds physically, since the energy-decay part of transverse relaxation is `exp(-t/2T1)` | Krantz et al. 2019, section III.B.2 |
| ADR-027 `gamma = 1 - exp(-t/T1)` | Amplitude-damping parameter of the single-qubit channel at gate duration `t` | `docs/decisions.md` ADR-027; `src/superconducted/training/targets.py`; `t` = the `sx` length, 24 ns in every file (`01-data-layer.md`, section 3) |
| ADR-027 `lambda = 1 - exp(-t(2/T2 - 1/T1))` | Phase-damping parameter; `2/T2 - 1/T1 = 2 Gamma_phi`, so `lambda = 1 - exp(-2 t Gamma_phi)` | Same; rows with `T2 > 2 T1` are rejected |

**What a Hahn echo changes.** A Ramsey experiment measures `T2*`, which is highly sensitive
to quasi-static, low-frequency fluctuations; the echo's refocusing pulse removes much of
that, giving a `T2` that is less sensitive to inhomogeneous broadening (Krantz et al. 2019,
section III.B.2; Qiskit Experiments "T2 Hahn Characterization", fetched 2026-10-06). So
`Gamma_phi` here is the pure dephasing that survives one echo. It is not comparable with a
Ramsey-based dephasing rate from the literature without that qualification.

**What a fit looks like.** Qiskit Experiments' `T1` analysis fits `A exp(-t/T1) + B` to the
excited-state probability against delay, and its Hahn-echo analysis fits `A exp(-t/T2) + B`;
both report a standard error. Their documented examples (simulated) give
`(5.86 +/- 0.28)e-05 s` and `(2.11 +/- 0.16)e-05 s`, a relative standard error of 0.04778 and
0.07583 (`nonpersistent.json`, `literature_inputs`). These are examples of the method, not
IBM's production settings, which no fetched source documents. **Never read IBM's internal
procedure from them.**

**Derived quantities are not new information.** Since `t = 24 ns` is constant, gamma is a
monotone function of `T1` alone and lambda of `Gamma_phi` alone: the log10 standard deviation
of gamma over `T1` events is 0.167291 against 0.167317 for `1/T1`, and lambda's 0.423187
against `Gamma_phi`'s 0.423352 (`profile.json`). Every temporal and spatial statement about
`1/T1` and `Gamma_phi` below holds for gamma and lambda.

**Event rules and pairing.** Both fields use the measured rule (`01-data-layer.md`, section
4). Quantities that need both times use a **paired event**: a `T2` event whose file carries a
`T1` stamped within 1 h of the `T2` stamp (`cohlib.SYNC_WINDOW_H`). Of 20,626 `T2` events,
19,899 pair, 727 have a `T1` stamped outside the window (71 on `q11`, 62 on `q17`, the rest
spread over 147 other qubits; 149 qubits have at least one), and none lack a `T1` record.
Every pair's `T2` stamp is after its `T1` stamp (`profile.json`, `derived`).

## 2. Profiles

### 2.1 Units, ranges, distribution and tails (one value per event)

| Quantity | n | Median | 1% | 99% | log10 sd | log10 MAD (scaled) | log10 skew | Excess kurtosis | Bowley skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `T1` (us) | 20,063 | 126 | 39.5 | 261 | 0.167 | 0.151 | -1.13 | 4.81 | -0.013 |
| `T2` (us) | 20,626 | 92.9 | 6.46 | 234 | 0.314 | 0.284 | -1.07 | 1.33 | -0.250 |
| `1/T1` (1/ms) | 20,063 | 7.94 | 3.83 | 25.3 | 0.167 | 0.151 | 1.13 | 4.81 | 0.013 |
| `Gamma_phi` (1/ms), paired, > 0 | 19,879 | 5.94 | 1.18 | 108 | 0.423 | 0.394 | 0.567 | 0.540 | 0.262 |
| `T_phi = 1/Gamma_phi` (us) | 19,879 | 168 | 9.26 | 848 | | | | | |
| `s = T2/(2 T1)`, paired | 19,899 | 0.405 | 0.0431 | 0.817 | | | | | |
| gamma (ADR-027) | 20,063 | 1.91e-4 | 9.20e-5 | 6.08e-4 | 0.167 | 0.151 | 1.13 | 4.80 | 0.013 |
| lambda (ADR-027), `T2 <= 2 T1` | 19,879 | 2.85e-4 | 5.66e-5 | 5.17e-3 | 0.423 | 0.394 | 0.566 | 0.537 | 0.262 |

Extremes: `T1` from 1.675 to 409.0 us, `T2` from 2.479 to 307.4 us over all records
(`profile.json`, `records`). The `T1` core is symmetric in log space (Bowley skew -0.013)
while the tails are not: the median is 3.19 times the 1st percentile but the 99th percentile
only 2.07 times the median. That asymmetric tail is the dips of section 3.3. `T2` is skewed in
its body too (Bowley -0.250): a group of strongly dephasing-limited qubits sits far below the
rest (section 5).

**Where the variance lives.** Pooling log10 values over events, the share of the variance
that lies between qubit means is 0.386 for `T1`, 0.817 for `T2`, 0.882 for `Gamma_phi` and
0.897 for `s` (`profile.json`, `variance_split`). Knowing which qubit it is tells most of what
`T2` and `Gamma_phi` will be, and less than half of what `T1` will be.

**`T2 > 2 T1`.** The physical bound `T2 <= 2 T1` is exceeded in 20 of 19,899 paired events
(share 0.00100508) on 15 qubits (`q140` 4, `q117` 3, thirteen others once), with `s` between
1.00009 and 1.76379. At those events the `T1` deviation from its running level has median
-0.304 (95% of them negative) and the `T2` deviation -0.0127 (40% positive). So the excess
comes from a `T1` value that dipped in a round where `T2` did not move, not from an inflated
`T2`. Statistically this is what a `T1` fit outlier would produce; physically it is also what
a `T1` change between the two experiments, or a non-exponential `T1` decay, would produce, and
these 20 events cannot separate those. At the record level (every file, including
asynchronous pairs) there are 424 such records (share 0.00155425) on 18 qubits; ADR-027
rejects them, 0 to 2 per file, in 379 files (`adr027.json`).

### 2.2 Missingness inside the lifetime

Both fields live in all 1,760 files. Every missing cell is `q72`: `T1` is absent in 36 cells
(the first 36 files, `20260513T121322000000Z` to `20260516T210531000000Z`), `T2` in all 1,760
(`profile.json`, `records`). ADR-027 therefore rejects `q72` in every file (`t2_missing` = 1
in all but the 36 files where `T1` is missing first), leaving 153 to 155 usable qubits per
file (`adr027.json`).

**Stale values** (a value older than 72 h at a file, i.e. carried forward past at least three
rounds; `profile.json`, `staleness`):

| Field, qubit | Files with a stale value | Maximum age (h) | Last stale file |
| --- | --- | --- | --- |
| `T1`, `q72` | 1,126 of 1,724 present | 695.6 | `20261006T025742000000Z` (still stale) |
| `T1`, `q11` | 876 of 1,760 | 503.2 | `20261006T025742000000Z` (still stale) |
| `T1`, `q17` | 482 of 1,760 | 2,206 | `20260714T194636000000Z` |
| `T1`, `q103` | 76 | 132.7 | `20260915T214955000000Z` |
| `T2`, `q149` | 351 of 1,760 | 219.5 | `20261006T025742000000Z` (still stale) |

Over all records the age of a `T1` value has median 12.8 h and 99th percentile 124.5 h; for
`T2`, 12.4 h and 47.2 h. `q17`'s first `T1` event is stamped 2026-04-13, before the archive
starts, and its next one 2,207.8 h later: for two months the archive shows a `T1` measured in
April (`profile.json`, `cadence`; the 2,207.8 h gap is also the data layer's maximum
`T1` gap). Any per-file target built from `T1` (ADR-027 included) silently mixes these old
values with fresh ones.

### 2.3 Cadence and rounds

| | `T1` | `T2` |
| --- | --- | --- |
| Gap between events, median (10%, 90%) h | 24.77 (19.15, 43.75) | 24.73 (19.15, 31.76) |
| Shortest gap, before / after 2026-08-05T23:45:31Z (first historical fetch) | 3.86 / 8.09 h | 3.86 / 8.09 h |
| Median gap before / after that split | 24.70 / 24.94 h | 24.70 / 24.94 h |
| Events per qubit per month (median), May to October | 21, 27, 24, 24, 29, 4 | 21, 28, 25, 25, 30, 4 |
| Rounds (15-minute split) / with at least 78 qubits | 138 / 133 | 135 / 133 |
| Share of events in those big rounds | 0.998543 | 0.999902 |
| Big-round duration (first to last stamp), median (max) | 0.05 (1.83) min | 0.05 (1.12) min |

(`profile.json`, `cadence` and `rounds`.) The calendar-month counts are counts of events,
so October holds only five days. The cadence is the same before and after the archive began
filing historical fetches, unlike the readout family (`01-data-layer.md`, section 6).

**Same round, not proven same job.** Only 160 of 19,907 `T1` events lack a `T2` event of the
same qubit within 1 h, and 724 of 20,471 `T2` events lack a `T1` event (`profile.json`,
`co_measurement`): `T2` is occasionally re-measured alone, `T1` almost never. The seconds
between the two stamps are consistent with one batch per round; whether they come from the
same job cannot be read from the archive.

**When rounds happen.** Big rounds start at every hour of the UTC day, with a concentration
from 20:00 to 24:00 (46 of 133), and on every weekday (18, 23, 18, 16, 23, 18, 17 from Monday)
(`temporal.json`, `seasonality_rounds`). Since a round is stamped within seconds, "hour of
the stamp" means the hour of the round's write, not of any one qubit's measurement.

## 3. Temporal structure

### 3.1 Device level by month (median over the qubits of each big round, then over rounds)

| Month | `T1` (us) | `T2` (us) | `Gamma_phi` (1/us) | `s` | Big rounds |
| --- | --- | --- | --- | --- | --- |
| 2026-05 | 101.8 | 89.05 | 0.00623 | 0.4124 | 21 |
| 2026-06 | 139.4 | 101.3 | 0.005565 | 0.4004 | 28 |
| 2026-07 | 131.1 | 96.12 | 0.005711 | 0.4126 | 25 |
| 2026-08 | 126.5 | 91.71 | 0.006085 | 0.4081 | 25 |
| 2026-09 | 128.0 | 93.55 | 0.005891 | 0.4024 | 30 |
| 2026-10 | 129.6 | 93.36 | 0.005952 | 0.4047 | 4 |

(`temporal.json`, `rounds`.) May is low; June is the highest month; the level then eases
back by about a tenth for `T1` and settles. The round-to-round device deviation (median over
qubits of each qubit's log deviation from its own whole-history median) ranges from -0.118
(2026-05-19) to +0.083 (2026-06-02) for `T1`, has lag-1 rank autocorrelation 0.56
(p = 1.9e-12) across rounds and no monotone trend (Spearman with time -0.053, p = 0.54).

### 3.2 Change points and regimes

**The device-wide May excursion.** The round series shows two device-wide steps in `T1`
(`regime.json`, `change_level.first_10_round_pairs`): a median change of -0.162 decades at the
2026-05-15T05 round and +0.132 at the 2026-05-28T06 round (with `T2` -0.089 and +0.070, and
`Gamma_phi` +0.066 and -0.059 at the same rounds). Tested against the 10 big rounds on each
side of the file in which `xslow` disappears (2026-05-29T16:46:42Z, `01-data-layer.md`
section 5), the per-qubit median `T1` rose by +0.167 decades, on 99.3% of 153 qubits; the
rank correlation of per-qubit levels across that boundary is 0.834, against a reference median
of 0.748 (5% to 95%: 0.701 to 0.808) over 96 other boundaries (`regime.json`, `boundary`).
Qubits kept their ranking and all moved together. The same test gives `T2` +0.122 (98.0% up)
and `Gamma_phi` -0.118 (4.6% up). With 10 rounds before and after, Mann-Whitney p for this date
is 0.00044 (`T1`), 0.00018 (`T2`, `Gamma_phi`), below the Bonferroni threshold 0.0015625 for the
32 known-date tests; no other device date passes it (`temporal.json`, `known_dates`). The `T1`
step falls at the 2026-05-28T06 round, 1.4 days before `xslow` disappears: the two are close in
time, and nothing in the archive links them causally.

**Binary segmentation** (Pettitt, p < 0.01, at least 8 rounds per segment) on the round
series finds no `T1` change point, one `T2` change between 2026-05-29T20:17 and 2026-05-30T20:27
(p = 0.0074), two `Gamma_phi` changes (2026-05-29, p = 0.00016; 2026-07-01 to 07-03,
p = 1.2e-6, median shift -0.0098 decades) and one `s` change (2026-06-26 to 06-29,
p = 1.3e-5) (`temporal.json`, `device_change_points`). Pettitt's test assumes independent
rounds; the positive lag-1 autocorrelation of the round series makes these p-values optimistic.

**The size of the round-to-round change has its own history** (`regime.json`,
`change_level`). For each pair of consecutive big rounds, the robust semivariance of the log10
change of the qubits measured in both:

| | `T1` | `T2` | `Gamma_phi` |
| --- | --- | --- | --- |
| Monthly median, May | 0.000609 | 0.00181 | 0.00394 |
| June | 0.0106 | 0.00774 | 0.00807 |
| July | 0.0146 | 0.00993 | 0.00956 |
| August | 0.0151 | 0.00999 | 0.0110 |
| September | 0.0134 | 0.00962 | 0.0112 |
| Pettitt change point of this series | 2026-06-26 to 06-29, p = 5.5e-12 | 2026-06-26 to 06-29, p = 4.4e-10 | 2026-07-15 to 07-17, p = 6.6e-14 |
| Median before / after it | 0.0092 / 0.0146 | 0.0066 / 0.0100 | 0.0077 / 0.0110 |

In the 13 rounds of the quiet window (2026-05-15T12 to 2026-05-28T00) the `T1` value of a
qubit barely changed from round to round: robust semivariance 0.000404 to 0.000686, against
0.0146 typical later. In that window the lag-1 autocorrelation of per-qubit changes is -0.33
(lag 2: -0.125), against -0.486 from 2026-05-28 to 06-28 and -0.501 after
(`change_acf_by_regime`). White scatter around a level gives -0.5, a random walk or a running
average gives about 0; -0.33 on 13 rounds is intermediate and does not decide between "the
qubits were quieter" and "the values were produced differently". The `T1`/`T2` co-movement of
round changes was weaker but present in the quiet window (Spearman 0.385, against 0.724 and
0.720 later; `t1_t2_change_comovement_by_regime`). The round-to-round semivariance also rises
with the gap between rounds (Spearman 0.30, p = 0.00044), mostly because the quiet window and
the long gaps fall in different periods.

**Per-qubit trends and change points** (Theil-Sen slope with Kendall p, and Pettitt, each with
Benjamini-Hochberg at 0.05 across qubits; `temporal.json`):

| Quantity | Window | Significant trends (up / down) | Median slope (decades per 30 days) | Significant Pettitt (up / down) | Pettitt dates by month |
| --- | --- | --- | --- | --- | --- |
| `T1` | whole record | 9 (5 / 4) | 0.0072 | 14 (7 / 7) | May 1, Jul 6, Aug 6, Sep 1 |
| `T1` | from 2026-05-30 | 23 (1 / 22) | -0.0084 | 22 (3 / 19) | Jun 2, Jul 13, Aug 6, Sep 1 |
| `T2` | whole record | 48 (41 / 7) | 0.0066 | 44 (34 / 10) | May 3, Jun 10, Jul 24, Aug 6, Sep 1 |
| `T2` | from 2026-05-30 | 40 (17 / 23) | -0.0044 | 38 (16 / 22) | Jun 3, Jul 26, Aug 8, Sep 1 |
| `Gamma_phi` | whole record | 69 (5 / 64) | -0.0108 | 74 (8 / 66) | May 4, Jun 24, Jul 40, Aug 4, Sep 2 |
| `Gamma_phi` | from 2026-05-30 | 40 (17 / 23) | 0.0001 | 37 (18 / 19) | Jun 1, Jul 24, Aug 10, Sep 2 |

The whole-record counts for `T2` and `Gamma_phi` are dominated by the May excursion; after it
the directions are mixed, `T1` drifts slightly down on a minority of qubits (23 of 156), and the
per-qubit change points cluster in July (13 of 22 for `T1`). Of the 22 post-May `T1` change
points, 7 fall within 3 days of a known device date, while those windows cover 0.33 of the span,
so they are not concentrated on known dates.

### 3.3 Memory beyond one round

Pooled autocorrelation of per-qubit log deviations from the qubit's mean inside each window
(`temporal.json`, `memory`):

| Window | `T1` lags 1, 2, 3, 5 | `T2` lags 1, 2, 3, 5 | `Gamma_phi` lag 1 |
| --- | --- | --- | --- |
| Whole record | 0.116, 0.109, 0.089, 0.062 | 0.136, 0.136, 0.108, 0.072 | 0.160 |
| Before 2026-05-30 | 0.321, 0.075, -0.022, -0.048 | 0.323, 0.140, 0.094, -0.072 | 0.404 |
| 2026-05-30 to 2026-08-05 | 0.067, 0.056, 0.039, 0.020 | 0.096, 0.108, 0.074, 0.048 | 0.106 |
| After 2026-08-05 | -0.009, 0.005, -0.004, -0.013 | 0.001, 0.012, -0.004, -0.034 | -0.015 |

The whole-record memory comes from the May steps and the June to July drift. After August
there is no memory at any lag from one to five rounds: a qubit's `T1` deviation today says
nothing about tomorrow's beyond the qubit's own mean. The lag-1 autocorrelation of log changes
is -0.493 (`T1`), -0.496 (`T2`), -0.490 (`Gamma_phi`), -0.481 (`s`), as P2 of the 2026-10-05
document found at the older ref.

### 3.4 Seasonality of the values

Round-level device deviations grouped by the round's UTC hour (six 4-hour bins) and weekday,
Kruskal-Wallis (`temporal.json`, `seasonality_rounds`):

| | Hour p | Weekday p |
| --- | --- | --- |
| `T1` | 0.689 | 0.893 |
| `T2` | 0.947 | 0.857 |
| `Gamma_phi` | 0.0451 | 0.602 |
| `s` | 0.0243 | 0.463 |

None passes the Bonferroni threshold 0.00625 for these eight tests (`multiple_testing`). The
event-level medians by hour differ by a few hundredths of a decade
(`seasonality_events_descriptive`), but events of one round are not independent, so that view is
descriptive only. No time-of-day or weekday effect on coherence values is supported.

## 4. The non-persistent component

### 4.1 Variograms

`ddload.variogram` on log10 values, all qubits (`nonpersistent.json`, `variograms`):

| Quantity | 18 to 30 h (pairs) | 744 to 1,488 h | 1,488 to 3,624 h | Ratio 18-30 h / 744-1,488 h | Robust ratio |
| --- | --- | --- | --- | --- | --- |
| log `T1` | 0.0146 (16,087) | 0.0179 | 0.0169 | 0.817 | 0.679 |
| log `T2` | 0.0151 (17,002) | 0.0191 | 0.0177 | 0.791 | 0.702 |
| log `Gamma_phi` | 0.0177 (15,884) | 0.0218 | 0.0221 | 0.813 | 0.717 |
| log `s` | 0.00727 (15,917) | 0.00903 | 0.00868 | 0.805 | 0.772 |

Read with the rules of `01-data-layer.md` section 7: most of the long-lag semivariance is
already present at one day; the remaining fifth (classical) to third (robust) rises slowly over
weeks, which is the drifting level of section 3. The same ratios by window: `T1` 0.878 from
2026-05-30 to 2026-08-05 and 0.934 after 2026-08-05 (robust 0.867 and 0.896); `T2` 0.842 and
0.884; `Gamma_phi` 0.803 and 0.987. In the last window the curve is essentially flat from one
day to a month.

**The short-lag bins are period-confounded.** The pooled variogram has 147 pairs at 2 to 4 h,
447 at 6 to 9 h and 440 at 12 to 18 h, and their robust semivariance (0.0115, 0.0050, 0.0060
for `T1`) looks lower than at one day (0.0103). But 302 of the 447 pairs at 6 to 9 h fall before
2026-05-30, where everything was quieter (that window's 18 to 30 h value is 0.0035). These bins
must not be read as sub-day memory. The matched test below replaces them.

**Matched sub-day test** (`subday_matched`). Each time two device-wide rounds came less than
18 h apart, the semivariance of the qubits' changes between them is set against the nearest
preceding and following round pairs 18 to 30 h apart. Nine occasions for `T1`:

| First round | Gap (h) | Qubits | Robust semivariance | Adjacent day-lag pairs, robust |
| --- | --- | --- | --- | --- |
| 2026-05-13T21:57 | 7.465 | 149 | 0.0109 | 0.0246 |
| 2026-05-15T05:57 | 16.46 | 153 | 0.00064 | 0.0055 |
| 2026-05-16T22:25 | 6.176 | 153 | 0.00040 | 0.00052 |
| 2026-05-29T10:13 | 10.05 | 148 | 0.0093 | 0.0089 |
| 2026-06-12T19:45 | 3.864 | 147 | 0.0115 | 0.0097 |
| 2026-06-16T02:42 | 14.64 | 144 | 0.0105 | 0.0110 |
| 2026-07-24T12:49 | 17.44 | 143 | 0.0170 | 0.0133 |
| 2026-08-25T17:37 | 8.088 | 145 | 0.0131 | 0.0144 |
| 2026-09-22T10:38 | 10.12 | 136 | 0.0180 | 0.0152 |

Median ratio 0.96; Wilcoxon p = 0.82 (`T2`: median ratio 0.89, p = 0.65). Outside the May
transitions, a pair of rounds 3.86 h apart shows the same change as a pair a day apart. The
short-lag audit confirms these are device-wide re-runs, not targeted ones: all 147 `T1` pairs
under 6 h fall in rounds of at least 78 qubits, and the first event of such a pair is no more
deviant than any event (median absolute deviation 0.0708 against 0.0686) (`short_lag_audit`).
**So the component decorrelates faster than 3.86 h**, the shortest lag the archive offers.
**[Verification 2026-10-06: weakened. Only one of the nine occasions (2026-06-12, 147 qubits,
which are not independent of each other) is shorter than 6 h and only five fall after
2026-05-30; the four May occasions are in the quiet or transition window and carry little
information. The re-computation gives median ratios 1.05 (all) and 1.19 (after 05-30) instead of
0.96. Supported: no rise of the semivariance from about 4 to 24 h. Not supported as stated: a
claim about the lag at which the component decorrelates, resting on one round pair.]**

**Log `Gamma_phi` by tertile of the qubit's median `s`** (`variograms.log10_gamma_phi_by_s_tertile`;
edges 0.307 and 0.483): 18 to 30 h semivariance 0.0052 (lowest `s`, 52 qubits), 0.0138, 0.0337
(highest `s`, 52 qubits); the 20 nonpositive `Gamma_phi` values dropped by the log transform
fall 0, 2 and 18 in those tertiles. When `T2` is close to `2 T1`, `Gamma_phi` is a small
difference of two large rates and inherits their scatter; the top tertile's larger nugget is
mainly that arithmetic, not larger dephasing fluctuations. `ddload.variogram` drops `y <= 0`
without a count; the counts here were logged separately.

### 4.2 What the component is: each test, what it shows, what it cannot exclude

| Test (result field) | Result | What it shows | What it cannot exclude |
| --- | --- | --- | --- |
| Same-round `T1`/`T2` co-movement (`t1_t2_comovement`) | Pearson 0.70 (rho² 0.49), Spearman 0.69; trimmed to deviations within 0.5 decades, 0.68; positive in 155 of 155 qubits (per-qubit median 0.75); by window 0.645, 0.721, 0.690 | Two independent fits cannot correlate. If the errors of the `T1` and `T2` fits are independent of each other and of the qubit, at least 49% of each deviation's variance is a shared real change (Cauchy-Schwarz: `Var(real)/Var(observed) >= rho²`) | A shared artefact that biases both decay constants in the same round in the same direction. None was identified: both fits have free amplitude and offset, so readout or contrast changes should not bias the decay time |
| Slope against `s` (`by_s_tertile`) | OLS slope of `T2` on `T1` deviations 0.320, 0.649, 0.807 at median `s` 0.168, 0.417, 0.562 (slope over `s` 1.90, 1.56, 1.44); across qubits Spearman(slope, `s`) 0.92, p = 6.4e-63 | A pure `T1` change with `Gamma_phi` fixed moves log `T2` by `s` times the log `T1` change, attenuated by any `T1` fit error. Observed slopes exceed `s` in every tertile: `T2` falls more than the `T1` change alone explains, so dephasing rises when `T1` falls | Which mechanism couples them (a TLS that both relaxes and dephases the qubit is the literature's candidate: Schlör et al. 2019) |
| `T1` against `Gamma_phi` deviations (`t1_vs_gamma_phi`) | Spearman -0.32 (tertiles -0.22, -0.38, -0.35) | An independent error in `T1` alone gives a positive correlation (a low `T1` lowers `Gamma_phi`); the observed sign is negative | As above |
| `T2` in `T1` dips (`dips.json`, `t2_during_t1_dips`) | 621 paired dip events: `T2` below its level in 97.9%, median -0.234 against -0.194 predicted, Spearman 0.81, observed below predicted in 73.8%; median `T2` deviation 0.008 when `T1` is not dipping | A factor-2 dip in `T1` is present in the `T2` experiment seconds later and by more than the propagation; a `T1` fit failure would leave `T2` unchanged | A shared artefact, as above |
| One-sidedness (`heterogeneity`) | Deviations below -0.301 decades: 3.19%; above +0.301: 0.106%; per-qubit quantile skew negative on 98.7% of qubits | Low-side excursions dominate, as the TLS literature describes (long low-`T1` tails: Klimov et al. 2018) | Fit failures that are themselves one-sided |
| Heterogeneity (`heterogeneity`) | Per-qubit deviation scale (MAD) p90/p10 = 1.54 against 1.32 to 1.42 (bootstrap 5% to 95% of equal-scale qubits); Fligner p = 4.5e-29; scale against level Spearman +0.18 (p = 0.024) | Qubits differ in volatility beyond sampling | The level-scale sign fits both "high-`T1` qubits fall further when a TLS arrives" and "long `T1` is fitted less precisely"; it does not discriminate |
| Shot-noise floor (`shot_noise_floor`) | For the floor to equal the 18 to 30 h semivariance, a `T1` fit would need at most 74 to 167 total shots (designs of 10 to 40 delays to 3 or 5 `T1`, median readout) or 414 to 783 (99th-percentile readout); `T2` echo 557 to 890 and 1,906 to 3,392. At 10,000 shots the `T1` floor is 0.0104 to 0.0157 decades sd | Unless IBM's fit used a few hundred shots or fewer, binomial shot noise is a small part of the nugget | Estimation error beyond shot noise: a misspecified model (non-exponential decay), or the qubit changing during the experiment, which is itself a real fluctuation |
| Memory (`temporal.json` `memory`; `dips.json` `persistence`; `subday_matched`) | No autocorrelation after 2026-08-05; dips no more consecutive than shuffles (p = 0.10 and 0.39); sub-day pairs equal to day pairs | The real part decorrelates faster than 3.86 h | Whether its timescale is minutes or hours |
| Size over time (`regime.json`) | Round-to-round robust semivariance about 0.0005 in the quiet window, about 0.009 to 2026-06-26, about 0.0146 after | The component's magnitude is not a fixed property of the device | Whether the device's environment or the production of the values changed |

**Reading.** The large non-persistent component of `T1` and `T2` is mostly real same-round
change of the qubit, under the independence assumption, and it decorrelates faster than the
archive can see. That is what published TLS dynamics predict when sampled daily: Burnett et
al. 2019 report dwell times at one `T1` value of typically 2 to 12.5 h and switching rates of
20 to 140 uHz (inverse 1.98 to 13.9 h; 0.146 to 3.89 h across thermal cycles); Klimov et al.
2018 report `T1` changes of up to an order of magnitude, abrupt on 15-minute timescales, with
jump rates of about 50 uHz to 5 mHz (inverse 0.056 to 5.6 h); Thorbeck et al. 2023 describe
TLS dynamics that destabilize lifetimes on hour timescales (`nonpersistent.json`,
`literature_inputs`). The size also matches: Burnett et al.'s two qubits scatter by a
log10 variance of 0.0093 and 0.0077 over about 65 h (delta method on their Gaussian fits; this
includes their own estimation error), against 0.0103 (robust) to 0.0146 (classical) here at one
day (`literature_benchmark`). These are other devices; they make the reading plausible, they do
not measure this one.

**What remains open.** (1) The 51% that the bound does not assign is not thereby estimation
error; the bound is a floor. (2) The quiet window shows that the size of the component can
change twenty-fold device-wide within a day, which a TLS bath alone does not explain; until its
cause is known, the post-June magnitude cannot be assumed stationary. (3) A shared artefact in
the two fits would undo the bound; the falsifier is a direct measurement (section 9).

## 5. Spatial structure

**Layout** (`spatial.json`, `layout`): one `coords` version in all 1,317 files with a
configuration; `x` from 1 to 16, `y` from 1 to 15; all 176 coupled pairs at unit distance;
degrees 1, 2, 3 on 8, 100 and 48 qubits; graph diameter 32 hops.

**Per-qubit medians against the map** (`per_qubit_stats`; Moran's I on the coupling graph with
9,999 permutations):

| Statistic | Moran's I (p) | Semivariance at 1, 2, 3, 4 hops / 5+ hops | Spearman vs distance from centre (p) | Degree 1, 2, 3 medians |
| --- | --- | --- | --- | --- |
| log `T1` | -0.017 (0.86) | 0.0169, 0.0156, 0.0169, 0.0159 / 0.0182 | +0.254 (0.0014) | 2.121, 2.098, 2.152 (Kruskal p = 0.0028) |
| log `T2` | 0.116 (0.10) | 0.0809, 0.0867, 0.0825, 0.0798 / 0.0922 | +0.207 (0.0096) | 2.108, 2.049, 1.954 (p = 0.38) |
| log `Gamma_phi` | 0.093 (0.20) | 0.149, 0.164, 0.151, 0.150 / 0.169 | -0.172 (0.032) | -2.411, -2.306, -2.147 (p = 0.20) |
| log `s` | 0.065 (0.34) | | +0.083 (0.30) | p = 0.088 |
| `T1` deviation scale | -0.073 (0.38) | | -0.012 (0.88) | p = 0.45 |
| `T1` dip rate | 0.034 (0.58) | | +0.126 (0.12) | p = 0.71 |

No statistic is more alike on coupled qubits than across the chip: the graph semivariance is
flat from one hop to five or more. Of the 36 position tests (`position_tests`), only `T1`
against distance from the centre (p = 0.00139) reaches the Bonferroni threshold (0.00138889),
and only just; the degree effect on `T1` (p = 0.0028) does not. Treat "edge qubits have longer
`T1`" as a candidate to replicate, not a finding.

**Extremes on the map** (`lowest_T1_qubits`, `highest_T1_qubits`, per-qubit median over events):
lowest `q72` 9.796 us, `q149` 48.74, `q0` 51.01, `q51` 57.45, `q12` 66.41; highest `q15`
256.7 us, `q13` 236.3, `q9` 204.9. The full 156-row table (position, degree, medians, scale,
dip rate) is `per_qubit_table`.

**Same-round co-movement between qubits** (`comovement`): the round median explains 5.5% of
the variance of `T1` deviations over 131 rounds (4.3% over 85 rounds from 2026-06-28), and 3.4%
for `T2` (2.4%). After removing it, coupled pairs correlate at a median -0.005 (mean -0.004),
pairs at least four hops apart at -0.004 (Mann-Whitney p = 0.89), and the mean correlation
stays between -0.010 and 0.008 at every distance from one to six hops. Dips agree: 32 of 2,033
co-dipping pairs are coupled, against a within-round shuffle mean of 29.9 (5% to 95%: 21 to 38)
(`dips.json`, `codipping`). The number of dips per round is over-dispersed (variance 11.6 against
4.4 to 7.5 for independent dips at each qubit's own rate, from 2026-06-28; maximum 17 against 11
to 15), consistent with the small round-level common mode. Thorbeck et al. 2023 describe
radiation impacts that make several TLSs jump at once; at daily sampling the archive shows no
neighbour-local trace of that, and a 4% to 6% common mode is all that a device-wide cause
could be contributing.

## 6. Faults and data quality

- **`q72`.** `T2` is absent from every file; `T1` is absent from the first 36 files, then
  present with 24 events (stamps from 2026-05-16 to 2026-09-13), values 6.2 to 26.3 us (median
  9.603 against 129.451 for the median qubit), a maximum gap of 698.3 h (2026-05-16 to
  2026-06-15), and stale in 1,126 files (`profile.json`, `q72`). Its `sx` and both couplers are
  permanently at the placeholder (`01-data-layer.md`, section 5). Interpretation: a qubit taken
  out of the gate calibration that is still probed for `T1` from time to time; its `T1` level
  says it would be unusable anyway.
- **Stale `T1` on `q11` and `q17`, stale `T2` on `q149`** (section 2.2). `q11` has 50 `T1`
  events and 71 unpaired `T2` events; `q17` has 71 `T1` events, one from April 2026.
- **The quiet window** (section 3.2): any model fitted across 2026-05-15 to 2026-05-27 sees
  round-to-round changes twenty times smaller than later. Mixing it with later data biases a
  noise estimate low and a persistence estimate high (the before-May autocorrelation of 0.32).
- **`T2 > 2 T1`** (section 2.1): 20 paired events, rejected by ADR-027 at the record level.
- **Deepest dip**: -1.854 decades below the running level (`dips.json`,
  `episode_depth_decades_quantiles`); the minimum `T1` of the archive is 1.675 us. Such values
  are within the dip population, not separate faults: they recover at the next round like the
  others.
- **No fit uncertainty**: nothing in the cache lets a reader weight an individual value by its
  precision.

## 7. Relationships

**`T1` and `T2` across qubits.** Per-qubit medians: Spearman 0.30 (p = 0.00013) between `T1`
and `T2`; -0.96 between `T2` and `Gamma_phi`; 0.85 between `s` and `T2`; -0.11 (p = 0.19)
between `T1` and `Gamma_phi` (`spatial.json`, `across_qubits`). A qubit's `T2` is set by its
dephasing, which is unrelated to its `T1`; long-`T2` qubits are the ones close to the `2 T1`
limit.

**`T1` and `T2` within a qubit over time.** Strongly coupled in the same round (section 4.2:
0.70), with `T2` inheriting `T1`'s dips in proportion to `s` and beyond it. 425 `T2` dips
(factor 2) occur, 127 of them while `T1` is not even mildly dipping (`dips.json`): dephasing
events of their own.

**Volatility follows the limit regime.** The per-qubit deviation scale of log `T2` rises with
the `T2` level (Spearman 0.68), because long-`T2` qubits are `T1`-limited and inherit `T1`'s
scatter; that of log `Gamma_phi` falls with the `Gamma_phi` level (-0.78), the propagation
effect of section 4.1 (`nonpersistent.json`, `heterogeneity`).

**Dip-proneness and level.** Across qubits, `T1` dip rate rises with the `T1` level (Spearman
0.23, p = 0.0042): a qubit with a high baseline has more room to fall by a factor of two.

**gamma and lambda** are monotone in `1/T1` and `Gamma_phi` (section 1); every relationship
above carries over. Cross-family links (readout, `sx`, `cz`/`rzz` against `T1`/`T2`) belong to
documents 03 to 05 and are not analysed here.

## 8. Use cases and why each field matters

| Use | Field | What this document implies |
| --- | --- | --- |
| ADR-027 training target | gamma, lambda | The snapshot target is the mean of per-qubit values. Gamma's top 10% of qubits carry a median 20% of the sum (uniform would be 10%), mean over median 1.12; lambda's top 10% carry 48%, mean over median 2.30 (`adr027.json`). A snapshot lambda is mostly a statement about the 16 most dephasing-limited qubits. **[Verification 2026-10-06: overstated. The median share of the top 10% is 48%, below half; "mostly" holds in at most about half the files. Say "close to half".]** Rejections: `q72` always, `T2 > 2 T1` in 379 files; stale `T1` values enter the mean unflagged |
| Forecasting (plan step M2 references) | `T1`, `T2` | After May, deviations have no memory: the qubit's level (median over its history) is the forecast and the scatter around it is a band, not a signal. For `T1` the level carries 39% of the variance and the rest is same-round change; for `T2` and `Gamma_phi`, over 80%. The quiet window and the 2026-06-26/29 step must be handled as regimes, not as part of a stationary noise |
| Coherence limit of gates | `T1`, `T2` | Used by documents 04 and 05. Since a `T1` dip lasts one round and the gate errors are stamped in other rounds, a limit built from `T1`/`T2` of a different round inherits the full round-to-round scatter of section 4 |
| Noise models and digital twins | `T1`, `T2` | Calibration-based digital twins map `T1`/`T2` into channels (Bautra et al. 2026, existing survey of 2026-10-05, section 2.5); the one-round dips mean a twin built from one snapshot carries that snapshot's dips |
| Qubit selection | `T1`, `T2` | The literature motivates fresh measurement because properties drift between daily updates (Wilson et al. 2020 and IBM's tutorial, survey of 2026-10-05, section 2.1). Here a qubit's level is stable and the deviations are not predictable, so a level (multi-round median) is a better selection score than the latest value |
| Device-stability assessment | all | Temporal and spatial stability of IBM devices has been framed as a distance between distributions over time and space (Dasgupta and Humble 2020, fetched 2026-10-06, abstract); the regimes of section 3.2 are exactly the kind of change such a metric should detect |
| TLS diagnostics | `T1` | Dips, their one-round duration and their absence of neighbour structure match a local TLS mechanism (Burnett et al. 2019; Etxezarreta Martinez et al. 2023, existing survey of 2026-10-04, section 3); identifying individual TLSs needs spectroscopy that the properties document does not carry (Khalil et al. 2026, survey of 2026-10-05, section 2.3) |

Why each field matters, in one line each: **`T1`** sets amplitude damping and the gamma target
and is the field whose day-to-day change is largest relative to its spread across qubits;
**`T2`** sets phase damping and is mostly a fixed property of each qubit; **`Gamma_phi`** is the
physically cleaner dephasing quantity, but unreliable on qubits near the `2 T1` limit; **`s`**
tells which regime a qubit is in and how a `T1` change will propagate into `T2`.

## 9. Open questions, and what measurement would settle each

| Question | What would settle it |
| --- | --- |
| What happened at the 2026-05-15T05 and 2026-05-28T06 rounds, and in the quiet window between them? | Document 06 checking the same rounds in every other family (a calibration-procedure change should show across families at once); IBM's release notes or backend changelog for those dates |
| Is the same-round `T1`/`T2` co-movement physical or a shared artefact? | Our own back-to-back `T1` and Hahn-echo experiments on a few `ibm_fez` qubits (Qiskit Experiments), repeated at minute spacing for a few hours: if independent repeats of the same experiment scatter far less than the archive's day-to-day nugget while `T1` and `T2` still co-move, the bound holds |
| What is the correlation time of the fast component (minutes or hours)? | The same repeated experiments give the autocorrelation directly at lags from minutes to hours; Burnett et al.'s Allan-deviation method applies |
| Are the reported values single fits or aggregates? | IBM documentation of the calibration analysis; or a comparison of our own fits with the values IBM stamps in the same hour |
| What caused the 2026-06-26/29 step in round-to-round variability? | As the first question; plus re-running `regime.py` on the next refs to see whether the step holds |
| Do edge qubits really have longer `T1`? | The same per-qubit test on another Heron r2 archive, or on later refs of this one; it sits at the Bonferroni boundary here |
| Do individual qubits switch between two `T1` states faster than a day? | Sub-hour repeated `T1` measurements on the 13 two-level candidates of `dips.json` (`two_level_list`) |

## 10. Reproduce, and results files

From the repository root, with the cache of `01-data-layer.md` built (default
`~/.cache/superconducted-feature-deep-dive/7b84b506/` or `DD_CACHE`), using CPython 3.12 with
numpy and scipy:

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/profile.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/temporal.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/nonpersistent.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/regime.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/dips.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/spatial.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/coherence/adr027.py
```

Shared rules (pairing window, round split, running level, period split, readout constants)
are in `analysis/coherence/cohlib.py`, and every results file copies them under
`constants`. Simulations use the seed 20261006.

| Results file | Contents |
| --- | --- |
| `results/coherence/profile.json` | Records, missingness, staleness, stamp offsets, event distributions, variance split, cadence, rounds, pairing, derived quantities, `T2 > 2 T1`, `q72` |
| `results/coherence/temporal.json` | Device level by month, round series, change points, known-date tests, seasonality, per-qubit trends and Pettitt (whole record and from 2026-05-30), memory, multiple-testing thresholds |
| `results/coherence/nonpersistent.json` | Variograms (all, by window, by `s` tertile), short-lag audit, matched sub-day test, `T1`/`T2` co-movement, heterogeneity, shot-noise floor, literature inputs and benchmark |
| `results/coherence/regime.json` | Round-to-round change level over time, its change point, change autocorrelation and `T1`/`T2` co-movement by regime, the 2026-05-29 boundary against 96 reference boundaries |
| `results/coherence/dips.json` | Dip frequency, depth, duration, recovery, persistence against shuffles, two-level fits, `T2` during dips, co-dipping |
| `results/coherence/spatial.json` | Layout checks, per-qubit statistics against position, Moran's I, across-qubit relations, between-qubit co-movement, the 156-row per-qubit table |
| `results/coherence/adr027.json` | ADR-027 rejections per file and the concentration of the snapshot mean of gamma and lambda |

**Sampled, truncated or skipped, all logged in the JSON thresholds:** the first event of every
qubit is excluded from temporal, regime, dips and spatial analyses (its stamp predates the
archive); 20 nonpositive `Gamma_phi` values are dropped from log analyses; qubits with fewer
than 20 events are left out of the dips and co-movement statistics, fewer than 30 of the
heterogeneity statistics and fewer than 40 of the two-level fit; per-qubit trend and Pettitt
tests need 16 events in the window; per-pair correlations need 20 shared rounds. Monte Carlo
sizes: 500 shuffles per qubit (dip persistence), 2,000 simulations (co-dipping counts), 200
shuffles (coupled co-dips), 300 bootstrap replicates (scale heterogeneity), 9,999 permutations
(Moran's I). Device-wide rounds need at least 78 qubits.

## 11. Sources

Literature count: 6 new sources fetched and verified on 2026-10-06 (title matched), 5 sources
already in the surveys re-fetched to verify what is quoted from them beyond the surveys, and
the rest cited from the surveys by section.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum documentation, "View backend details" | https://quantum.cloud.ibm.com/docs/en/guides/qpu-information | fetched 2026-10-06 | `T1` and `T2` definitions; `T2` from a Hahn echo; properties update after calibration; timestamp of last calibration |
| Qiskit Experiments, "T1 Characterization" | https://qiskit-community.github.io/qiskit-experiments/manuals/characterization/t1.html | fetched 2026-10-06 | Fit model `A exp(-t/T1) + B`, reported standard error, example value (method, not IBM's settings) |
| Qiskit Experiments, "T2 Hahn Characterization" | https://qiskit-community.github.io/qiskit-experiments/manuals/characterization/t2hahn.html | fetched 2026-10-06 | Echo sequence and fit, echo against Ramsey, example with 2,000 shots at 11 delays |
| Krantz et al., A Quantum Engineer's Guide to Superconducting Qubits (Appl. Phys. Rev. 2019) | arXiv:1904.06560 | fetched 2026-10-06 (abstract; PDF section III.B.2 read) | `Gamma_1`, `Gamma_2 = Gamma_1/2 + Gamma_phi`, `T2 <= 2 T1`, echo against Ramsey, exponential-decay assumption |
| Müller, Cole and Lisenfeld, Towards understanding two-level-systems in amorphous solids (Rep. Prog. Phys. 2019) | arXiv:1705.01108 | fetched 2026-10-06 (abstract) | Background: TLS defects in amorphous oxides as the limiting loss of superconducting circuits |
| Dasgupta and Humble, Characterizing the Stability of NISQ Devices (2020) | arXiv:2008.09612 | fetched 2026-10-06 (abstract) | Prior framing of temporal and spatial stability of an IBM device (section 8) |
| Klimov et al., Fluctuations of Energy-Relaxation Times in Superconducting Qubits (PRL 2018) | arXiv:1809.01043 | existing survey of 2026-10-04, sections 3 and 8; re-fetched 2026-10-06 (abstract; PDF pp. 1 to 4) | TLS cause the largest `T1` fluctuations; up to an order of magnitude, abrupt on 15 minutes, low-`T1` tails, jump rates; 2,000 repeats at 40 delays per curve |
| Burnett et al., Decoherence benchmarking of superconducting qubits (npj QI 2019) | arXiv:1901.04417 | existing survey of 2026-10-04, sections 3 and 8; re-fetched 2026-10-06 (abstract; PDF pp. 1 to 4) | Local TLS-driven `T1` fluctuations; dwell 2 to 12.5 h; switching rates; Gaussian fits of 65 h of `T1` |
| Carroll et al., Dynamics of superconducting qubit relaxation times (2021, revised 2022) | arXiv:2105.15201 | existing survey of 2026-10-04, sections 3 and 8; re-fetched 2026-10-06 (abstract) | Ten fixed-frequency transmons over about nine months; ergodic-like TLS spectral diffusion, so a qubit's long-run mean is a stable property |
| Thorbeck et al., TLS Dynamics in a Superconducting Qubit Due to Background Ionizing Radiation (PRX Quantum 2023) | arXiv:2210.04780 | existing survey of 2026-10-05, section 2.3; re-fetched 2026-10-06 (abstract) | Hour-scale TLS dynamics; TLS scrambling by radiation impacts on a 27-qubit processor |
| Schlör et al., Correlating Decoherence in Transmon Qubits (PRL 2019) | arXiv:1901.05352 | existing survey of 2026-10-04, sections 3 and 8; re-fetched 2026-10-06 (abstract) | Correlated relaxation and dephasing fluctuations from a few TLS |
| Etxezarreta Martinez et al., Multi-Qubit Time-Varying Quantum Channels (2023) | arXiv:2207.06838 | existing survey of 2026-10-04, sections 3 and 8 | `T1`/`T2` fluctuations local to each qubit on IBM processors |
| Wilson et al. (2020) | arXiv:2005.12820 | existing survey of 2026-10-05, section 2.1 | Fresh measurement before execution as a use case |
| Bautra, Dimitrijevs and Yakaryilmaz (2026) | arXiv:2603.14607 | existing survey of 2026-10-05, section 2.5 | Calibration-based digital twins |
| Khalil et al. (2026) | arXiv:2608.21983 | existing survey of 2026-10-05, section 2.3 | TLS detection needs spectroscopy |
| Project sources | `01-data-layer.md`; `docs/decisions.md` ADR-027; `src/superconducted/training/targets.py`; `docs/roadmap/2026-10-05-feature-patterns-and-method.md` | read 2026-10-06 | Field semantics, device dates, ADR-027 definitions, the P2 wording corrected here |

## Verification (2026-10-06)

Verifier: a second agent that did not write this document. Figures are provisional, measured on
the lead's laptop at ref `7b84b506ef77beb6e6c1b25a7357c574cfaf5117`. The analyst stopped at a
usage limit before a final self-check; this section is that check.

**Re-run.** All seven owner scripts (`profile`, `temporal`, `nonpersistent`, `regime`, `dips`,
`spatial`, `adr027`) were re-run from the same cache. Every results JSON reproduced exactly,
field by field (tolerance 1e-9 relative), the only difference being `measured_utc`. So no
number in the document is stale against its script. Whether a script's rule is right is a
separate question, tested below with fresh code.

**Independent recomputation** (new scripts written from `ddload` only, no import of the owner's
code: `analysis/verify/coherence/v_core.py`, `v_comove.py`, `v_subday.py`; results in
`results/verify/coherence/core_check.json`, `comove_check.json`, `subday_check.json`). The
comovement and dip checks use a different running level (median of the qubit's other events
within 7 days) as well as the document's (14 nearest events).

| Claim | Document value | Recomputed | Match |
| --- | --- | --- | --- |
| `T1` / `T2` events, and paired events | 20,063 / 20,626; 19,899 | 20,063 / 20,626; 19,899 | yes |
| `T2` stamp after `T1` stamp: range, share within 10 s | 1 to 112 s, 98.7% | 1 to 112 s, 98.67% | yes |
| `T1` median, 1%, 99% (us) | 126, 39.5, 261 | 125.97, 39.49, 260.89 | yes |
| Between-qubit variance share, `T1` / `T2` | 0.386 / 0.817 | 0.3865 / 0.8166 | yes |
| `T1` variogram 18 to 30 h, 744 to 1,488 h, ratio, pairs | 0.0146, 0.0179, 0.817, 16,087 | 0.014634, 0.017913, 0.817, 16,087 | yes |
| Lag-1 autocorrelation of `T1` log changes | -0.493 | -0.497 (no first events; document uses a demeaned within-qubit estimator) | yes, within 0.004 |
| Largest device-wide median steps of `T1` | -0.162 (05-15), +0.132 (05-28) | -0.1625, +0.1317 at the same round pairs | yes |
| Same-round deviation correlation `T1`/`T2` | Pearson 0.70, Spearman 0.69, 155 of 155 qubits | 0.701 / 0.691, 154 of 154 (7-day level); 0.698 / 0.689, 155 of 155 (document's level) | yes |
| First-difference correlation, 18 to 30 h, from 06-28 (no level) | not in document | Pearson 0.714, Spearman 0.719 (n = 9,948) | new, supports |
| `T1` dips (factor 2) | 630 of 19,595, 151 qubits | 630 of 19,595, 151 qubits (14-event level); 596 of 19,145, 149 qubits (7-day level) | yes |
| Consecutive dip pairs | 28 observed, 21.6 shuffled | 28 observed, 21.1 analytic; 25 against 19.5 with the 7-day level | yes |
| `T2 > 2 T1` among pairs | 20 events, 15 qubits | 20, 15 | yes |
| Moran's I of median log `T1` | -0.017 (p = 0.86) | -0.015 (p = 0.81); ranks 0.003 | yes |
| Shot-noise floor, total shots at which the floor equals the nugget | 74 to 167 | 74.0 to 167.4 (four designs) | yes |
| Klimov budget (80,000 shots) floor as share of nugget | 0.14% | 0.14% (log design); 0.09% to 0.21% across designs | yes |
| Matched sub-day test, median ratio | 0.96, 9 occasions | 1.05 (all), 1.19 (after 05-30), 9 occasions | partly (same occasions and gaps; ratio depends on the neighbour pairing, one neighbour value differs: 0.0055 against 0.0246 on 05-13) |

**Claims challenged**

| Claim | Verdict | Why |
| --- | --- | --- |
| At least half of the non-persistent variance is shared between `T1` and `T2` (rho^2 = 0.49) | Upheld, with the wording weakened to "shared" | Not an artefact of the level: 0.70 with two level definitions; 0.714 from first differences (no level, so it concerns the non-persistent part); 0.69 after removing each round's median deviation (so not a device-wide common mode); 0.64 / 0.72 / 0.69 by period; placebo `T1` against the next round's `T2` is -0.03 and against another qubit's `T2` in the same round 0.05 to 0.07. The Cauchy-Schwarz step is correct. It cannot separate a real qubit change from an artefact common to both of IBM's experiments, so "contradicted" and "real" in section 0 are marked weakened. |
| The component decorrelates faster than 3.86 h | Weakened | Rests on one round pair at 3.86 h (147 qubits of one occasion) and five occasions after 05-30; see inline marker. |
| Dips last one round and do not persist beyond chance | Weakened | 28 pairs, p = 0.10, a 30% excess; see inline marker. |
| Shot noise cannot explain the component | Upheld | Reproduced independently. It is a Cramer-Rao lower bound for a correct exponential model with median readout and assumed designs; misspecification and in-experiment change are not covered, and the document says so. |
| The size of the component is not a stable property (quiet window, 2026-05-15 to 05-27) | Upheld | Round-step medians reproduced; the document's own caveat (13 rounds; -0.33 autocorrelation is intermediate) is correct. The inference "TLS dynamics do not pause for twelve days" is interpretation, stated with an either/or. |
| ADR-027 lambda "mostly" set by 16 qubits | Weakened (overstated) | Median share 48%; see inline marker. |
| Low-`T1` dips are real drops that `T2` follows | Upheld as a shared change | Same limits as the first row. |
| No neighbour structure | Upheld | Moran's I reproduced with a different weights and permutation implementation, on raw values and on ranks. The test has 156 units and detects only large effects; "no structure" means none detected. |

Looked for and not found: placeholder leakage (neither field carries placeholders), alias or
direction duplicates (not applicable to qubit fields), assembly-stamped dates (the measured rule
applies), and period confounding of the headline correlation (the same in every period). Not
tested by anyone here: whether a round's readout or initialisation change moves both `T1` and
`T2`; this needs the cross-family document 06.

**Sources spot-checked (3), fetched 2026-10-06.** IBM "View backend details": supports the
`T1` and `T2` definitions, "`T2` is reported from a Hahn echo sequence", and the
pairing with the timestamp of the last calibration. Dasgupta and Humble, arXiv:2008.09612,
title "Characterizing the Stability of NISQ Devices": supports the stated framing (a distance
between histograms over time and across qubits, on IBM's Yorktown device). Qiskit Experiments
"T2 Hahn Characterization": supports 2,000 shots, 11 delays, `A exp(-t/T2) + B`, and
(2.11 +/- 0.16)e-05 s; it does not explicitly compare the echo with Ramsey (it says echoes
reduce frequency-inaccuracy effects), so the "echo against Ramsey" use of that row rests on
Krantz et al., which was not re-fetched here.

**Rule check.** No em dash (U+2014) in the document or the verification scripts. Provisional
banner, ref, basis and machine are present. Every number in the body is a field of a results
JSON that reproduces; the numbers added in this section come from the three verification
results files. No row was added to `docs/numerical-claims.md`. The verification scripts pass the
pinned `ruff check` and `ruff format --check`. Four inline markers were inserted (three weakened
claims and one overstated claim).
