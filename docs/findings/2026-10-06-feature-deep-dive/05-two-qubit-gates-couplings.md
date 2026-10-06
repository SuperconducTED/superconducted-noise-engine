# 05 · Two-qubit gates and couplings: `cz`, `rzz`, `jq`, `zz`

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: reconcile it
later by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Basis: all 1,760 `ibm_fez` snapshot files at
`calibration-data` `7b84b506ef77beb6e6c1b25a7357c574cfaf5117` (2026-05-13T12:13:22Z to
2026-10-06T02:57:42Z); 176 undirected couplers (352 directed `g2` columns, one canonical column
per coupler, see §1.3); 22,092 `cz` and 18,210 `rzz` re-measurement events (measured rule,
placeholders masked); 83,440 value events of `|zz|`; measured on 2026-10-06 on the lead's laptop
(Windows 11, CPython 3.12). Nothing here is registered in `docs/numerical-claims.md`. The
scripts are in `analysis/gates_2q/` and every number below is a field of a JSON in
`results/gates_2q/` (or of `results/data-layer/*.json`, or is quoted from a repository document
named next to it). Field references use these short names:

| Short name | File |
| --- | --- |
| P | `results/gates_2q/profile.json` |
| R | `results/gates_2q/cz_vs_rzz.json` |
| T | `results/gates_2q/temporal.json` |
| V | `results/gates_2q/variograms.json` |
| Z | `results/gates_2q/zz.json` |
| S | `results/gates_2q/spatial.json` |
| L | `results/gates_2q/link.json` |
| DL | `results/data-layer/profile.json` and `results/data-layer/identities.json` |

Decisions A1 to A9 and the advisor's answers are open; nothing here records or implies an
approval, and nothing here is a modelling or strategic decision.

## 0. Summary

1. **The direction "identity" is a placeholder artefact.** The two directions of a coupler
   carry the same value in all 309,760 comparisons for each gate, and the date mismatches
   (8,682 for `cz`, 12,395 for `rzz`) are all in placeholder records, 0 outside them; there the
   two stamps differ by about 6 microseconds (median 6.10 us for `cz`, 7.08 us for `rzz`). Outside
   placeholders the directions are exact duplicates in value and date (P `*.direction_identity`).
2. **IBM's documentation says what the numbers are.** The per-edge 2Q error comes from
   randomized benchmarking measured in isolation batches; the `rzz` error is "averaged over the
   RZZ angles" with an RB variant for arbitrary unitaries; a value of 1 means benchmarking has
   not succeeded for several days (IBM "View backend details", fetched 2026-10-06). That the
   archive's `gate_error` is exactly that per-edge quantity is an inference.
3. **Levels.** Median `cz` error per event 2.75e-3 and `rzz` 2.66e-3; coupler medians span a
   factor 42.5 (`cz`) and 99.6 (`rzz`) from best to worst, a factor 3.5 and 3.3 between the 10th
   and 90th percentiles (P `*.values`).
4. **Cadence.** 132 `cz` rounds and 110 `rzz` rounds in 5 months, median gap between rounds
   25.1 h and 25.3 h; within a round all couplers are stamped within 0.067 minutes (median).
   `rzz` follows `cz` by a median 1.15 h. The `rzz` event rate fell from 0.81 to 0.61 per coupler
   per day after the coverage split (2026-08-05T23:45:31Z), with a 279.8 h device-wide `rzz` pause
   from 2026-08-19 to 2026-08-31, while `cz` stayed at 0.88 and 0.87 (P, R).
5. **No memory beyond one round.** Lag-1 autocorrelation of log changes is -0.448 (`cz`) and
   -0.425 (`rzz`); lags 2 to 4 are all within 0.06 of zero, in both coverage periods (T).
6. **Variograms.** At one round (18 to 30 h) the semivariance of log error is already 0.64
   (`cz`) and 0.54 (`rzz`) of its level at lags of 744 h and more; the rest grows slowly over
   weeks, far more slowly than a random walk would (V).
7. **A shared, hour-scale part of the non-persistent component exists, and it is small.** The
   local deviations of two couplers that share a qubit correlate at Spearman 0.22 (`cz`) and 0.23
   (`rzz`) in the same round (-0.008 for couplers four or more hops apart; 90.9% of the 230 `cz`
   pairs positive); `cz` and `rzz` on one coupler correlate at 0.20 when measured within 1 h and
   at 0.10 or less beyond 2 h. So that component is not wholly independent per-experiment
   estimation noise; most of it is unshared, and what the unshared part is stays open (§4).
8. **Second calibrations within a day** (11 `cz` and 6 `rzz` device-wide occasions 3 to 16 h after
   a round) change by 0.727 (`cz`) and 0.783 (`rzz`) of the one-round semivariance (V).
   **[Verification 2026-10-06: weakened. "Second calibrations" asserts a recalibration that 4.2
   itself says the document cannot show; the 0.727 and 0.783 are averages over gaps of 3 to 16 h
   and the fraction rises with the gap (0.33 of one round at 2 to 4 h, 0.73 at 9 to 12 h, 0.89 at
   12 to 18 h; see Verification section).]**
9. **Coherence limit.** At the device-median `T1` (125.9 us) and `T2` (92.44 us) a 68 ns gate has a
   coherence limit of 8.04e-4; the median `cz` error is 3.41 times that. Per event, the limit is a
   median 0.333 (`cz`) and 0.351 (`rzz`) of the reported error (L).
10. **Single-qubit gates explain more than coherence.** Across couplers, `cz` error follows the sum
    of its two qubits' `sx` errors (Spearman 0.58) more than its coherence limit (0.33); `sx`
    keeps 0.54 given the limit, readout adds nothing (-0.01) given both (L).
11. **Faults are states.** `cz`: 7 couplers ever at the placeholder, 4 always, 2 entries; `rzz`:
    13 ever, 5 always, 13 entries. `cz` on 102-103, at the placeholder in 88.8% of files, left it
    on 2026-09-29. 32-33 is permanently faulty for both gates although none of its two qubits'
    reported medians is extreme (P, L, §6.2).
12. **`zz` is static ZZ in GHz (median 6.18 kHz), refreshed device-wide about every 5 h.** 484 of
    486 value bursts change at least 170 of 176 couplers; median burst gap 5.16 h; changes do not
    persist (lag-1 -0.513, lag-2 0.016); it is unrelated to `cz` and `rzz` error (between-coupler
    Spearman 0.010 and -0.027). It behaves as a re-determined quantity, not a constant and not a
    by-product of the daily gate rounds; whether IBM measures it directly or computes it is not
    decidable from the document. Three couplers (13-14, 39-53, 109-118) have been frozen at one
    value since 2026-07-10 (Z, §1.4).
13. **`jq` is 0 in all 309,760 records**: no information (P `jq`, DL).
14. **Spatial.** Coupler levels cluster on the graph (Moran's I 0.26 for `cz`, 0.38 for `rzz`,
    permutation p 0.0006 and 0.0001); `|zz|` does not (I -0.002, p 0.47) but is larger on bridge
    couplers (factor 1.42, p 0.0013) (S).
15. **Exploratory:** the five couplers with a non-68 ns length (88 ns or 116 ns) all have low
    `|zz|` (Mann-Whitney p 1.1e-4); found by inspection, so hypothesis-generating only (Z).

## 1. The fields and how IBM produces them

### 1.1 What IBM's documentation says

| Field | IBM's description (fetched 2026-10-06) | What the archive shows |
| --- | --- | --- |
| `cz.gate_error` | "2Q error (CZ/ECR): the two-qubit error per edge from the same batch of measurements used to calculate the 2Q median error"; the median 2Q error is the average gate fidelity "from randomized benchmarking", "measured in 'isolation': batches with a minimum separation of two qubits between edges" ("View backend details") | A per-coupler value in (0, 1) or the placeholder 1; one value per undirected coupler |
| `rzz.gate_error` | "Error in the RZZ gate averaged over the RZZ angles using a variant of randomized benchmarking for arbitrary unitaries" ("View backend details"); RZZ(theta) is allowed for 0 < theta <= pi/2 ("Fractional gates") | A per-coupler value, never equal to `cz` outside placeholders (R `levels.same_file_share_exactly_equal` 0.0 over 296,321 records) |
| placeholder `1` | "If the benchmarking of a qubit or edge does not succeed over the course of several days, whether due to poor data quality or other internal factors, the reported error value is considered stale and will be reported as 1" | Exactly 1, stamped at document assembly (§1.3) |
| `gate_length` | "Duration of a single-qubit or two-qubit gate operation" | 68, 84, 88 or 116 ns; one value per coupler, no angle |
| EPLG ("2Q error (layered)") | Average error per layered gate in a 100-qubit chain, `EPLG_100 = 4/5 (1 - LF^(1/99))` from the layer fidelity LF | Not one of these fields; the `lf_<N>` values in `general` belong to 06 |
| `jq_<ab>`, `zz_<ab>` | Not documented in any fetched source. The `BackendProperties` API page says only that it "holds backend properties measured by the provider" and that `general` is a list of `Nduv` objects | `jq` = 0 everywhere; `zz` in GHz, refreshed about every 5 h |

Two contrasts between documentation and data:

- The fractional-gates guide says the error reported in the **Target** of a backend with
  fractional gates enabled "is just a copy of the non-fractional gate's counterpart (which may
  not be the same)". In the **properties document** this holds for `rx` (equal to `sx` in all
  274,560 records, DL `identities.json` `sx_vs_rx_error`) but not for `rzz`: `rzz` equals `cz` in
  0 of 296,321 same-file valid records (R). The archive's `rzz` error is its own measurement.
- `rzz` (and `rx`) appear in `properties.gates` of every file but in none of the four
  `target.operations` sets: the union of target operations lists `cz` 352 times and `rzz` 0 times
  (P `target_operations_union_counts`, `rzz_in_target_union`). The guide says fractional gates are
  included in a backend's `Target` only when it is loaded with `use_fractional_gates=True`, so
  this is consistent with the archive fetching the non-fractional view (an inference; the
  poller's flag is not recorded in the document).

### 1.2 Physical meaning

- **`cz`** is the native entangling gate of Heron r2 (`basis_gates` contains `cz` throughout,
  01-data-layer.md §6); its error is an average gate infidelity from RB. RB averages over all
  error sources during the gate: decoherence of both qubits, control errors, leakage, and
  coupling to TLS defects. The coherence limit (§7.2) is the part that `T1` and `T2` alone would
  produce.
- **`rzz`** is the fractional ZZ rotation, executed directly instead of as a decomposition into
  `cz` gates, which IBM says reduces a circuit's duration and error ("Fractional gates"). The
  reported error is an average over angles, not the error at a specific angle; the reported
  length is one number per coupler, and the guide does not say whether duration depends on the
  angle. So a coherence limit computed from the reported `rzz` length is a proxy.
- **Static ZZ (`zz`)** is the always-on conditional frequency shift between two coupled
  transmons: the frequency of one qubit depends on the state of the other. Qiskit Experiments
  defines it through the Hamiltonian term `h f_ZZ / 4 ZZ` and measures it with `ZZRamsey` as the
  difference between a qubit's Ramsey frequency with its partner in 1 and in 0 ("ZZRamsey",
  fetched 2026-10-06). That page shows how ZZ can be measured, not that IBM measures `zz_<ab>`
  this way; IBM's sign and factor convention for `zz_<ab>` is not documented. Mundada et al.
  call parasitic crosstalk "a leading limitation for quantum gates" and show that a tunable
  coupler can be set so that the ZZ interactions of different couplers interfere destructively
  (arXiv:1810.04182, fetched 2026-10-06). The `zz` unit is GHz, so the median 6.18e-6 GHz is 6.18 kHz (Z
  `record_khz_q`).
- **`jq`** reads like a qubit-qubit coupling strength `J` per coupler in GHz. That meaning is an
  inference from the name and the unit; no fetched source defines it. A value of exactly 0 on
  all 176 couplers, including the 171 or more on which `cz` and `rzz` are calibrated, is
  consistent with an unpopulated field, not with a measured zero coupling.

### 1.3 The direction identity, corrected

01-data-layer.md §5 records that the two directions of a coupler always carry the same value
and that dates differ in 8,682 (`cz`) and 12,395 (`rzz`) comparisons. Re-measured per record
(P `cz.direction_identity`, `rzz.direction_identity`):

| Item | `cz` | `rzz` |
| --- | --- | --- |
| Records compared per direction pair | 309,760 | 309,760 |
| Value mismatches | 0 | 0 |
| Date mismatches | 8,682 | 12,395 |
| of which in placeholder records | 8,682 | 12,395 |
| of which outside placeholders | 0 | 0 |
| Placeholder records per direction | 8,682 | 12,395 |
| Stamp offset between directions in mismatches, microseconds (min, median, max) | 4.64, 6.10, 31.0 | 5.86, 7.08, 27.3 |
| Non-placeholder stamps that are whole seconds | 1.0 of 301,078 | 1.0 of 297,365 |
| Placeholder stamps that are whole milliseconds | 0.00104 | 0.00105 |
| Placeholder stamp minus file date, h (median, max) | 0.078, 12.4 | 0.080, 12.4 |

What this reveals: every placeholder record carries its own write-time stamp with sub-
millisecond resolution, generated a few microseconds apart for the two directions and minutes
after the document's `last_update_date`; every real measurement carries a whole-second stamp
shared by both directions. The inference is that IBM produces one value per undirected coupler
and writes it under both directed names, and that placeholders are generated at assembly. After
masking, one canonical column per coupler (`[a, b]` with `a < b`) loses nothing, and every
statistic below uses it.

### 1.4 Is `zz` measured or derived? What the in-scope data say

The date of `zz` is the assembly time in every record (DL `date_equals_file_date_share` 1.0), so
only its values carry timing. From the in-scope evidence (Z):

- **Device-wide bursts.** 486 files change at least one coupler's `zz`; 484 of them change at
  least 170 of the 176 couplers, and the median burst changes 172, which is every coupler except
  32-33 and the three frozen couplers below (Z `bursts.couplers_changing_per_burst_q`). Couplers
  are refreshed together.
- **Cadence.** Median gap between bursts 5.16 h (quartiles 3.66 and 8.14 h), against 25.1 h for
  the `cz` rounds. 38.5% of the 130 files in which `cz` events appear are bursts, against 27.6%
  of all files (39.4% of 109 `rzz` event files): bursts are not tied to the gate rounds.
- **The changes do not persist.** Lag-1 autocorrelation of `log10 |zz|` changes -0.513 and
  lag-2 0.016 (83,096 pairs): the signature of independent scatter around a stable level. The
  variogram is flat from 2 to 372 h (§4.3). A typical burst moves `|zz|` by 0.031 decades or
  less (quartiles of the log ratio -0.031 and +0.031); 3.2% of burst changes exceed a factor 1.5.
- **Resolution.** 83,444 distinct values; the shortest exact decimal form of a value has a
  median of 16 significant digits: unrounded floating-point output of a computation.
- **Zeros as a missing marker, and three frozen couplers.** `zz` is exactly 0 on 32-33 in every
  file (both gates permanently faulty there) and on 13-14, 39-53 and 109-118 in the same 429 files,
  from the first file to `20260710T051721000000Z`, while both gates on those couplers were never
  at the placeholder (Z `zero_couplers`). In file `20260710T093926000000Z` those three received
  one value each (7.447, 2.892 and 6.345 kHz) and never changed again: one value change each in
  the whole archive, against a median of 485 over all 176 couplers (Z
  `couplers_with_at_most_one_value_change`, `bursts.value_changes_per_coupler_q`). Whatever
  refreshes `zz` every 5 h does not reach these three couplers.

Conclusion, labelled as inference: `zz` is re-determined about every 5 h for the whole device,
each time with scatter that does not carry over to the next determination; it is neither a
configuration constant nor a by-product of the daily `cz`/`rzz` calibration. The document cannot
decide whether the immediate source is a direct ZZ experiment or a formula applied to other
frequently re-measured quantities (qubit frequencies, anharmonicities, coupler bias), since none
of these inputs is in the file and no fetched IBM source documents `zz_<ab>`. The readout family
is re-measured with a median gap of 4.47 h (01-data-layer.md §3); whether `zz` bursts coincide
with qubit-level rounds is a cross-family question handed to 06 and 07 and not computed here.

## 2. Profiles

### 2.1 Units, ranges, distribution and tails

| Item | `cz.gate_error` | `rzz.gate_error` | Source |
| --- | --- | --- | --- |
| Valid records (canonical column) | 301,078 | 297,365 | P `*.values.records_nonplaceholder` |
| Placeholder records (canonical column) | 8,682 | 12,395 | P `*.values.records_placeholder` |
| Events (measured rule) | 22,092 | 18,210 | P `*.values.events_total` |
| Event values: min, 1%, 10%, median, 90%, 99%, max | 1.15e-3, 1.59e-3, 1.96e-3, 2.75e-3, 7.54e-3, 4.54e-2, 0.117 | 1.09e-3, 1.53e-3, 1.89e-3, 2.66e-3, 7.02e-3, 4.61e-2, 0.260 | P `*.values.event_weighted_q` |
| Event mean | 4.79e-3 | 4.71e-3 | P `*.values.event_weighted_mean` |
| Skewness of `log10` record values | 2.11 | 2.43 | P `*.values.record_log10_skew` |
| Coupler medians: min, 10%, median, 90%, max | 1.57e-3, 2.04e-3, 2.72e-3, 7.05e-3, 6.69e-2 | 1.62e-3, 1.99e-3, 2.61e-3, 6.63e-3, 0.161 | P `*.values.per_coupler_median_q` |
| Worst / best coupler median | 42.5 | 99.6 | P `best_to_worst_coupler_median_ratio` |
| 90th / 10th percentile of coupler medians | 3.46 | 3.33 | P `p90_to_p10_coupler_median_ratio` |
| Deviation from own coupler median, decades: 1%, 99% | -0.360, +0.656 | -0.306, +0.728 | P `deviation_from_coupler_median_log10_q` |
| Events above 2x / below 0.5x / above 10x their coupler median | 3.35% / 1.28% / 0.22% | 4.15% / 1.03% / 0.27% | P `deviation_share_*` |

The mean (4.79e-3 for `cz`) lies far above the median (2.75e-3), which is why every statistic in
this document is a median, a rank correlation or a `log10` quantity. The tails are
**one-sided**: excursions upward from a coupler's level are more frequent and larger than
excursions downward (3.35% of `cz` events above twice the coupler median against 1.28% below
half of it; 99th percentile +0.66 decades against 1st percentile -0.36), as expected for an
error that something can make worse much more easily than better.

`gate_length` (ns): 68 on most couplers; P `*.lengths`:

| Length | `cz` records | `rzz` records | Couplers |
| --- | --- | --- | --- |
| 68 ns | 304,652 | 299,372 | all others |
| 84 ns | 1,588 | 1,588 | 71-72, 72-73 from file `20260905T175136000000Z` (both gates; were 68 ns) |
| 88 ns | 3,520 | 3,520 | 102-103, 146-147, both gates, throughout |
| 116 ns | 0 | 5,280 | `rzz` on 68-69, 80-81, 106-107, throughout |

The 84 ns change happened on two couplers that were at the placeholder in every file for both
gates, so a gate length is a configuration value that can change without any successful
calibration. **Length against error:** median record error at 68 ns 2.75e-3 (`cz`) and 2.64e-3
(`rzz`); 146-147 (88 ns) 2.71e-3 and 2.58e-3; 102-103 (88 ns) 7.41e-2 and 9.19e-2; the 116 ns
`rzz` couplers 3.81e-3 (68-69), 2.94e-3 (80-81), 3.65e-3 (106-107). With two and three couplers per
group no test is meaningful; the 116 ns couplers' `rzz/cz` median ratios (1.15, 1.44, 1.62)
all sit above the 68 ns couplers' median ratio 0.967 (R `ratio_by_rzz_length_ns_last_file`),
which fits a longer gate accumulating more error, but three couplers do not establish it.

### 2.2 Missingness inside the lifetime

Every one of the six fields is present for every coupler in every file (DL
`present_share_within_lifetime` 1.0, `entities_never_present` 0). The only gaps are placeholder
states (§6) and, for `zz`, the zeros of §1.4. There are no schema starts in this scope.

### 2.3 Cadence

| Item | `cz` | `rzz` | Source |
| --- | --- | --- | --- |
| Events per coupler: 1%, median, max | 57.1, 131, 131 | 24.2, 110, 110 | P `events_per_coupler_q` |
| Event gap, h: 1%, 10%, median, 90%, 99% | 6.30, 19.0, 25.1, 36.9, 77.3 | 6.27, 19.5, 25.3, 51.2, 260 | P `event_gap_h_q` |
| Rounds (15-minute clustering of stamps) | 132 | 110 | P `rounds.n_rounds` |
| Rounds with at least half of the couplers | 130 | 109 | P `rounds_with_ge_half_of_couplers` |
| Couplers per round, median | 169 | 165 | P `couplers_per_round_q` |
| Gap between round starts, h: 10%, median, 90%, max | 19.0, 25.1, 31.8, 77.3 | 20.8, 25.3, 49.7, 280 | P `gap_between_round_starts_h_q` |
| Span of a round's stamps, minutes: median, max | 0.067, 0.37 | 0.067, 1.18 | P `round_span_minutes_q` |
| Distinct stamps per round, median | 5 | 5 | P `distinct_stamps_per_round_q` |
| Rounds before / from the coverage split | 77 / 55 | 72 / 38 | P `rounds_before_split`, `rounds_from_split` |
| Events per coupler per day before / from the split | 0.880 / 0.869 | 0.809 / 0.607 | P `events_per_coupler_per_day_*` |
| Gaps over 48 h before / from the split | 1,086 / 557 | 1,544 / 1,199 | P `gaps_over_48h_*` |

The coverage split is the first historical fetch, file `20260805T234531000000Z` (687 files
before it over 84.5 days, 1,073 from it over 61.1 days; P `coverage_split`). Before it, the
archive holds only documents the poller saw; a missed document can hide intermediate events, so
pre-split event rates are lower bounds. The `cz` rate is the same in both periods, so the poller
probably missed few `cz` rounds (an inference). The `rzz` rate is lower **after** the split, when coverage is better,
so the drop reflects how often IBM refreshed `rzz`, not coverage (an inference: better coverage
can only reveal more events under the measured rule). **[Verification 2026-10-06: overstated as
a cadence statement. The 279.8 h pause alone accounts for most of it: excluding it, the rate from
the split is 0.729 per coupler per day (re-computed) against 0.607 with it and 0.809 before.]** Device-wide gaps between round starts over
40 h occur 16 times for `rzz` and 9 times for `cz` (P `*.values.rounds.n_round_start_gaps_over_40h`,
listed in `round_start_gaps_over_40h`); the longest `rzz` gap runs from 2026-08-19T23:02:17Z to
2026-08-31T14:50:23Z (279.8 h), during which `cz` rounds continued (the longest `cz` round gap is
77.3 h).

Rounds are not tied to a clock time: round starts fall in every UTC hour (P
`round_start_utc_hour_counts`), and the median round gap of 25.1 h makes the cycle drift
through the day. Within a round every coupler is stamped within seconds, in about five distinct
stamps; these are write times, and §5.4 shows that they do not identify the isolation batches.

## 3. Temporal structure

### 3.1 Memory of changes

Autocorrelation of `log10` changes between consecutive events of a coupler, pooled (T
`*.autocorrelation_of_log_changes`, Pearson):

| Lag | `cz` all | `cz` before split | `cz` from split | `rzz` all | `rzz` before | `rzz` from |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | -0.448 | -0.450 | -0.441 | -0.425 | -0.421 | -0.436 |
| 2 | -0.030 | -0.011 | -0.059 | -0.034 | -0.023 | -0.045 |
| 3 | 0.010 | 0.004 | 0.023 | -0.004 | -0.001 | -0.013 |
| 4 | -0.022 | -0.033 | -0.008 | 0.000 | -0.022 | 0.047 |
| pairs at lag 1 | 21,748 | 12,612 | 8,965 | 17,869 | 11,519 | 6,180 |

Spearman values agree (lag 1: -0.434 and -0.435). A local level plus independent scatter gives
`rho_1 = -1/(2 + q)` and zero at lag 2 and beyond; the implied `q` is 0.233 (`cz`) and 0.354
(`rzz`), matching P2 of `docs/roadmap/2026-10-05-feature-patterns-and-method.md` at the older ref
(-0.45 and -0.42 there). If the non-persistent component had memory at the round scale (an
autoregressive part with coefficient phi), lag 2 would be negative in proportion to phi. All
lags 2 to 4 are within 0.06 of zero in both periods: **whatever the non-persistent component
is, it does not carry over from one daily round to the next.**

### 3.2 Device level, drift and change points

The device median per round (rounds covering at least half the couplers; 131 for `cz`, 110 for
`rzz`, T `device_rounds_ge_half`; this count includes each series' first event, hence 131 here
against 130 in §2.3) stays between 2.46e-3 and 2.97e-3 for `cz` and between 2.41e-3 and 2.90e-3 for `rzz`
(T `device_round_median_q`, min and max). Theil-Sen trend per 30 days in `log10`: -0.00086 for
`cz` (95% interval -0.0029 to 0.0011) and -0.00060 for `rzz` (-0.0033 to 0.0018), both intervals
containing zero. Monthly event medians (T `monthly_event_median`):

| Month | `cz` events | `cz` median | `rzz` events | `rzz` median |
| --- | --- | --- | --- | --- |
| 2026-05 | 3,365 | 2.79e-3 | 3,468 | 2.71e-3 |
| 2026-06 | 4,355 | 2.71e-3 | 3,947 | 2.59e-3 |
| 2026-07 | 4,388 | 2.75e-3 | 3,780 | 2.73e-3 |
| 2026-08 | 4,240 | 2.76e-3 | 2,509 | 2.65e-3 |
| 2026-09 | 4,892 | 2.74e-3 | 3,834 | 2.64e-3 |
| 2026-10 | 852 | 2.68e-3 | 671 | 2.60e-3 |

(One `rzz` event stamped 2026-04 is the first value of a series measured before the archive
began.) Binary segmentation of the device series (permutation p below 0.01, 999 shuffles, at most
three levels) finds four `cz` splits, all in May and June 2026, with shifts of factor 0.955 to
1.10 (T `cz.device_change_points`), and none for `rzz`. The deeper splits carry no multiplicity
correction, and shuffling treats rounds as exchangeable, so a slow wander also counts as "not
exchangeable": these are small, early wobbles, not regime shifts. **The device-wide two-qubit
error level has not moved materially in five months.**

Per coupler, a single best split (max standardized CUSUM, 499 shuffles, Benjamini-Hochberg at
5% over couplers) is a discovery for 37 of 171 `cz` couplers (20 up, 17 down) and 46 of 168 `rzz`
couplers (25 up, 21 down); the shift factors of the `cz` discoveries run from 0.117 to 5.09
(median 1.13), and 25 of the 37 `cz` and 32 of the 46 `rzz` discoveries fall before the split (T
`*.per_coupler_change_points`). The same exchangeability caveat applies: a discovery means the
coupler's level moved during the five months (step or drift), not necessarily one abrupt event.
Examples: 83-96 up by 3.23 and 96-103 up by 2.26 at the same `cz` round 2026-09-20T10:56Z; 49-50
up by 4.10 (2026-08-30); 47-57 down to 0.117 of its level (2026-05-19); `rzz` 48-49 up by 6.26
(2026-09-12). So 37 of 171 `cz` and 46 of 168 `rzz` couplers carry a level change that persists
for weeks, which is the slowly moving level of the local-level picture.

### 3.3 Seasonality of the values

Each event's deviation from the median of its 3 + 3 neighbouring events, grouped by the UTC
hour and the weekday of its stamp (Kruskal-Wallis, groups with at least 200 events; T
`*.value_seasonality`):

| Grouping | `cz` p | `cz` epsilon squared | `rzz` p | `rzz` epsilon squared |
| --- | --- | --- | --- | --- |
| UTC hour (23 and 21 groups) | 4.7e-8 | 0.0025 | 3.7e-15 | 0.0053 |
| 4-hour block (6 groups) | 0.944 | -0.0002 | 3.5e-6 | 0.0016 |
| Weekday (7 groups) | 1.6e-5 | 0.0012 | 4.9e-4 | 0.0010 |

The group medians stay within 0.016 decades of zero in every grouping. Rank-based effect sizes
are below 0.006 everywhere: statistically detectable with 17,708 to 22,086 events, practically
negligible. Two cautions: the round cycle drifts through the clock (§2.3), so an hour bin samples
particular calendar stretches and inherits their level; and these are several tests on correlated
events. **There is no usable time-of-day or day-of-week pattern in the values.** `zz` shows none
either (4-hour block p 0.437, weekday p 0.887; Z `value_seasonality_log_abs`).

## 4. The non-persistent component

### 4.1 Variograms of log `cz` and log `rzz`

`ddload.variogram` on the measured-rule events (V `cz.variogram`, `rzz.variogram`; semivariance in
`log10` squared; robust = Cressie-Hawkins):

| Lag bin (h) | `cz` pairs | `cz` semivariance | `cz` robust | `rzz` pairs | `rzz` semivariance | `rzz` robust |
| --- | --- | --- | --- | --- | --- | --- |
| 2 to 4 | 163 | 0.00447 | 0.00321 | 165 | 0.00388 | 0.00266 |
| 6 to 9 | 500 | 0.00855 | 0.00374 | 328 | 0.00940 | 0.00437 |
| 9 to 12 | 503 | 0.00985 | 0.00466 | 0 | | |
| 12 to 18 | 669 | 0.0119 | 0.00410 | 497 | 0.0129 | 0.00448 |
| 18 to 30 | 16,737 | 0.0134 | 0.00526 | 12,815 | 0.0131 | 0.00554 |
| 42 to 54 | 13,361 | 0.0145 | 0.00581 | 10,494 | 0.0144 | 0.00576 |
| 84 to 132 | 35,089 | 0.0162 | 0.00628 | 25,897 | 0.0169 | 0.00672 |
| 204 to 372 | 119,500 | 0.0183 | 0.00716 | 81,662 | 0.0213 | 0.00843 |
| 744 to 1,488 | 393,129 | 0.0204 | 0.00803 | 269,305 | 0.0255 | 0.0104 |
| 1,488 to 3,624 | 512,230 | 0.0215 | 0.00902 | 358,977 | 0.0229 | 0.0101 |

Summary (V `*.summary`): the first bin with at least 1,000 pairs is 18 to 30 h (one round), at
0.0134 (`cz`) and 0.0131 (`rzz`), against a mean of 0.0209 and 0.0242 at lags of 744 h and more;
the one-round value is 0.64 and 0.54 of the long-lag level (robust 0.62 and 0.54). Per coupler the
same ratio has a median of 0.82 (`cz`, 171 couplers) and 0.73 (`rzz`, 169), with 10th to 90th
percentiles 0.46 to 1.14 and 0.33 to 1.11 (V `*.per_coupler`). By coverage period the ratio is
0.65 before and 0.71 from the split for `cz`, 0.52 and 0.63 for `rzz`.

Reading with the rules of 01-data-layer.md §7:

- The curve is **not flat**, so the series are not estimation noise around a fixed level.
- It is **not a random walk**: from a mean lag of 25.1 h (18 to 30 h bin) to 2,213 h (last bin)
  the semivariance grows only from 0.0134 to 0.0215 (V `cz.variogram`, `mean_lag_h`), whereas a
  random-walk part would grow in proportion to the lag. The slow part keeps growing over weeks to
  months at a decelerating rate, the slowly moving level of P2.
- The **one-round value is the nugget at the observable lag**: everything faster than a day
  (estimation noise, fluctuations faster than a round, and any change a recalibration makes)
  appears there undistinguished. On its own the variogram cannot split it.

### 4.2 What the sub-day lags add: second calibrations within a day

The 2 to 18 h bins are filled only by 11 `cz` and 6 `rzz` occasions on which the whole device was
calibrated a second time 3 to 16 h after a round (V `*.short_gap_occasions`). Calling them
"re-measurements without recalibration" would claim more than the document shows: nothing in it
distinguishes a repeated benchmark of the same tuned gate from a fresh tune-up.

| Item | `cz` | `rzz` |
| --- | --- | --- |
| Occasions; coupler pairs | 11; 1,835 | 6; 990 |
| Short gap, median per occasion (h) | 3.77 to 16.2 | 3.09 to 16.2 |
| Mean half squared change across the short gap | 0.00975 | 0.0102 |
| Same couplers across the preceding gap | 0.0131 | 0.0123 |
| Ratio short / preceding | 0.747 | 0.832 |
| Ratio short / variogram 18 to 30 h bin | 0.727 | 0.783 |
| Occasions with the short change below the preceding | 9 of 11 | 4 of 6 |
| Wilcoxon signed-rank p, short against preceding | 0.0011 | 2.9e-6 |

**[Verification 2026-10-06: refuted as evidence. These p-values treat the 1,835 and 990 coupler
pairs as independent, but couplers of one occasion share the device-wide round and there are only
11 and 6 occasions. At occasion level the sign test gives p 0.065 (`cz`) and 0.69 (`rzz`), and the
signed-rank test 0.10 and 0.56. "Short change below the preceding" is not established for `rzz`
and is marginal for `cz`.]**

A quarter of the preceding `cz` gaps exceed 51.7 h (V `cz.short_gap_occasions.preceding_gap_h_q`,
75th percentile) and carry some level drift, so the comparison with the 18 to 30 h bin is the
cleaner one. The single shortest occasion
(2026-07-27, 163 couplers, 3.77 h) changed by 0.00447 against 0.0117 before it, but it is one
occasion. **About three quarters of the one-round nugget is already present between two
calibrations a few hours apart; about a quarter builds up between a few hours and a day.**
**[Verification 2026-10-06: weakened. The pooled bins give 0.33 of the one-round value at 2 to 4 h,
0.64 at 6 to 9 h, 0.73 at 9 to 12 h, 0.89 at 12 to 18 h; "three quarters" holds only for gaps near
10 h. The occasions' gaps run 3 to 16 h, so the average hides a lag dependence, and the shortest
(3.77 h) occasion is at 0.33 of the one-round value (0.00447 against 0.0134).]**

### 4.3 Variogram of `zz`

`|zz|` value events with exact zeros dropped (V `abs_zz`: 172 series; 32-33 has no nonzero
value and the three frozen couplers of §1.4 have only one, so none of the four forms a pair):

| Lag bin (h) | Pairs | Semivariance | Robust |
| --- | --- | --- | --- |
| 0 to 2 | 2,404 | 0.00371 | 0.00143 |
| 2 to 4 | 24,508 | 0.00488 | 0.00155 |
| 18 to 30 | 163,723 | 0.00500 | 0.00156 |
| 204 to 372 | 1,796,710 | 0.00545 | 0.00164 |
| 744 to 1,488 | 5,705,967 | 0.00581 | 0.00169 |
| 1,488 to 3,624 | 6,755,920 | 0.00652 | 0.00176 |

The curve rises from the 0 to 2 h bin to the 2 to 4 h bin, then stays roughly flat to about
372 h before a slight rise; nugget over long-lag level 0.60 (robust 0.83). The signed series in
kHz (`transform="none"`) is dominated by the extreme couplers of §6.3 (non-robust bins between
38.5 and 83.5 kHz squared; robust 0.29 to 0.35). For `zz` the non-persistent part dominates,
reaches its full size within a few hours (the 0 to 2 h bin holds pairs from consecutive bursts
only 0.5 to 2 h apart), and a small slow part appears only beyond weeks.

### 4.4 Is part of the component shared? Two tests

1. **Couplers that share a qubit** (S `*_deviation_correlation_in_space`; deviations from each
   coupler's 3 + 3 neighbour median, matched by round, round medians removed):

   | Pairs | `cz` Spearman (n) | `rzz` Spearman (n) |
   | --- | --- | --- |
   | Share a qubit (244 coupler pairs) | 0.220 (29,513) | 0.226 (24,229) |
   | Same, without couplers above the 90th percentile of levels | 0.230 (25,300) | 0.225 (21,351) |
   | Four or more hops apart (13,886 pairs) | -0.008 (1,668,789) | -0.008 (1,349,430) |
   | Per coupler pair with at least 30 rounds: median rho; share positive | 0.209; 0.909 (230 pairs) | 0.228; 0.907 (225 pairs) |

   The effect is broad, not driven by a few bad couplers. It is not explained by the shared
   qubit's reported state: given the shared qubit's current `sx`, `T1` and readout deviations
   the partial correlation is 0.219 (`cz`) and 0.225 (`rzz`); each of those deviations correlates
   with a coupler's deviation at 0.032 or less (L `*.shared_qubit_pairs`). Those qubit values
   were measured in other rounds (median 3.5 h away, 90% within 16 h; L
   `abs_hours_gate_stamp_to_T1_T2_stamps_q`), so "not explained by the reported values" is
   supported; "not a single-qubit effect" is not.
2. **`cz` against `rzz` on one coupler, by the time between them** (R
   `local_deviation_spearman_by_abs_offset`; same local deviations, nearest `rzz` event):

   | Offset (h) | 0 to 1 | 1 to 2 | 2 to 4 | 4 to 6 | 6 to 12 | 12 to 24 | 24 to 48 |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | Spearman | 0.205 | 0.172 | 0.078 | 0.044 | 0.059 | 0.099 | -0.016 |
   | n | 5,424 | 5,261 | 5,268 | 1,152 | 832 | 1,691 | 897 |
   | before split | 0.190 | 0.211 | 0.056 | 0.082 | 0.059 | 0.135 | -0.073 |
   | from split | 0.323 | 0.077 | 0.090 | 0.019 | 0.062 | 0.062 | 0.008 |

   In both periods the shared deviation is largest when the two gates are measured within an
   hour or two and lower at 2 to 12 h. The decline is not monotone: the 12 to 24 h bin (an `rzz`
   event of a neighbouring round) rises again to 0.099 (0.135 before the split), which a single
   decaying factor would not produce. Different offset bins come from different rounds and
   couplers, so this is not a controlled decay: it would be falsified if the decline vanished
   when the comparison is stratified by round (not run here). Changes tell the same story at
   lower strength: consecutive matched changes correlate at 0.137 (14,557 pairs; 0.127 after
   removing each round's median), against a null of other couplers in the same round centred at
   0.012 (2.5% to 97.5%: -0.005 to 0.026) (R `changes`).

For context, the component has no memory across rounds (§3.1), and three quarters of the
one-round nugget is present within hours (§4.2).

### 4.5 What the evidence does and does not show on the root question

Three candidates can produce a large non-persistent component in a daily series:

- **(a) estimation noise**: the finite-sample scatter of each RB fit around the true error;
- **(b) real fluctuations faster than the sampling**, for example TLS defects drifting through
  resonance, aliased by daily sampling into independent draws (the physics prior of
  `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` §3; TLS dynamics on hour
  timescales, Thorbeck et al. 2023, and step changes lasting minutes, Hirasaki et al. 2023, both
  in the 2026-10-05 survey §2.1 and §2.3);
- **(c) recalibration variability**: each round may re-tune the gate itself, so consecutive
  rounds report differently calibrated gates. No fetched source says whether IBM re-tunes the
  two-qubit pulses each round, so this is a hypothesis, but nothing in the document rules it out.

What the data show:

- **The component is not wholly (a).** Independent estimation noise in separate experiments
  cannot correlate between two couplers that share a qubit, nor between `cz` and `rzz` measured
  an hour apart. Both correlate (0.22 and 0.20), and only close in space or time (-0.008 at four
  hops; 0.10 or less beyond 2 h). Something time-varying and local is shared: a physical state of
  the shared qubit or coupler region (b), or a calibration input common to both experiments (c),
  or a protocol effect such as crosstalk during simultaneous benchmarking (Gambetta et al.,
  arXiv:1204.6308, fetched 2026-10-06). IBM's documentation says the 2Q benchmarks run in
  isolation batches with at least two qubits between edges, which would keep two couplers that
  share a qubit out of the same batch and argues against the crosstalk reading, but the document
  cannot confirm the batching (§5.4).
- **The shared part is small.** A rank correlation near 0.2 means most of each coupler's
  deviation is not shared with its neighbours or with the other gate. That unshared majority is
  where (a), (b) with sub-hour time scales, and (c) all remain possible.
- **It has no memory at the round scale** (§3.1), and about three quarters of it is present
  between calibrations a few hours apart (§4.2).

What the data do not show: the split of the unshared part between (a), (b) and (c). Wallman and
Flammia show that RB estimates can be precise under Markovian noise, with confidence set by the
number and length of sequences, and IBM's production RB settings are not published (2026-10-05
survey §2.1), so the estimation-noise floor cannot be computed from the document; it carries no
per-value uncertainty for `cz`, `rzz` or `zz`. **This document therefore does not call the
component "measurement noise" or "estimation noise".**

## 5. Spatial structure

### 5.1 The graph

From `meta.json`: 176 couplers, 120 horizontal (both qubits on one long row of the heavy-hex
lattice) and 56 bridges; qubit degrees 1 (8 qubits), 2 (100) and 3 (48); 244 pairs of couplers
share a qubit (S).

### 5.2 Levels on the device

Per-coupler median of `log10` error (events) and of `log10 |zz|` (files) (S `cz`, `rzz`, `abs_zz`):

| Test | `cz` | `rzz` | `|zz|` |
| --- | --- | --- | --- |
| Couplers | 172 | 171 | 175 |
| Median, horizontal / bridge | 2.74e-3 / 2.71e-3 | 2.63e-3 / 2.54e-3 | 5.64 / 7.99 kHz |
| Bridge over horizontal; Mann-Whitney p | 0.989; 0.68 | 0.965; 0.36 | 1.42; 0.0013 |
| Spearman with distance from lattice centre (p) | -0.166 (0.030) | -0.120 (0.12) | -0.020 (0.80) |
| Spearman with row (p) | -0.118 (0.12) | -0.153 (0.046) | 0.050 (0.51) |
| Spearman with column (p) | -0.007 (0.93) | -0.021 (0.78) | 0.240 (0.0014) |
| Spearman with degree sum of the two qubits (p) | 0.160 (0.036) | 0.105 (0.17) | -0.045 (0.56) |
| Moran's I on the line graph, log levels (p, 9,999 shuffles) | 0.263 (0.0006) | 0.383 (0.0001) | -0.002 (0.47) |
| Moran's I on ranks (p) | 0.210 (0.0004) | 0.192 (0.0016) | 0.033 (0.27) |

The table holds 21 tests (seven rows, three fields); with a Bonferroni correction for 21 tests
only the Moran's I values for `cz` and `rzz` (p 0.0016 or below) and the orientation and column
effects for `|zz|` (p 0.0014 or below) survive. So: **gate error
clusters on the graph** (couplers next to a bad coupler tend to be bad; the null 97.5% points
are 0.13 and 0.14), with no orientation, row or centre effect that survives correction; **`|zz|` has
no neighbourhood clustering but depends on the coupler's geometry**, bridges carrying about 1.4
times the ZZ of row couplers, and a gradient along the columns. The geometric `zz` effect is
consistent with static ZZ being set by fixed design parameters (detunings and coupler design)
that differ systematically between coupler types; that is an interpretation, falsified if a
second Heron r2 device shows no orientation effect.

### 5.3 Faulty couplers on the graph

The couplers ever at the placeholder (S `faulty_positions`): `cz` 27-28, 32-33, 71-72, 72-73,
102-103, 148-149, 149-150; `rzz` adds 7-17, 17-27, 38-49, 49-50, 95-99, 99-115. Qubits 17, 27, 49,
72, 99 and 149 each touch two of these couplers (for q49 both belong to the one shared `rzz`
episode of 2026-09-03, §6.1). Faults concentrate around particular qubits, which
the per-qubit check of §6.2 examines.

### 5.4 Stamp groups are not isolation batches

Within a round, couplers sharing the identical stamp form groups of median 36 (`cz`, 709 groups
with at least two couplers) and 35 (`rzz`, 601). In 78% (`cz`) and 77% (`rzz`) of groups, two
members share a qubit (S `*_batches`). Under IBM's description, couplers that share a qubit cannot
be in one isolation batch, so the stamp marks when results were written, not which edges were
benchmarked together. The document cannot verify IBM's batching.

### 5.5 The non-persistent component in space

§4.4 item 1: deviations are shared between couplers that share a qubit (0.22) and not beyond
(-0.008 at four or more hops). This differs from P6 of the 2026-10-05 document, which found no
neighbour signal in `sx` **changes** of coupled qubit pairs. The two do not conflict: P6 tested
qubit-level `sx` between neighbouring qubits; here two couplers that literally contain the same
qubit are compared.

## 6. Faults and data quality

### 6.1 Placeholder states per coupler

| Item | `cz` | `rzz` |
| --- | --- | --- |
| Couplers ever at the placeholder | 7 | 13 |
| Always at the placeholder | 27-28, 32-33, 71-72, 72-73 | 32-33, 71-72, 72-73, 95-99, 99-115 |
| Entries / exits over the archive | 2 / 3 | 13 / 16 |
| Placeholder couplers per file: min, median, max | 4, 5, 6 | 6, 6, 11 |
| Placeholder records, both gates / `cz` only / `rzz` only | 7,638 / 1,044 / 4,757 | (same) |

Episodes that are not permanent (P `*.placeholders.couplers`; a run open at the first file has a
lower-bound duration):

| Gate | Coupler | Share of files | Runs (first file to last placeholder file, files, hours) |
| --- | --- | --- | --- |
| `cz` | 102-103 | 0.888 | from the first file to `20260929T022626`, 1,563 files, 3,327 h; it then left the placeholder |
| `cz` | 149-150 | 0.040 | `20260519T153114` to `20260527T053937`, 71 files, 186 h |
| `cz` | 148-149 | 0.005 | `20260528T033226` to `20260529T082836`, 8 files, 32 h |
| `rzz` | 27-28 | 0.956 | to `20260616T230742` (288 files), then from `20260701T120353` to the end (1,395 files): valid for about two weeks only |
| `rzz` | 102-103 | 0.339 | four runs, the last `20260903T004128` to `20260907T094653` |
| `rzz` | 17-27 | 0.276 | `20260514T165538` to `20260716T030013`, 485 files, 1,538 h |
| `rzz` | 7-17 | 0.236 | `20260605T043513` to `20260729T191446`, 416 files, 1,312 h |
| `rzz` | 149-150, 148-149 | 0.120, 0.107 | three and four runs |
| `rzz` | 38-49, 49-50 (with 148-149, 149-150) | 0.005 | one shared episode `20260903T004128` to `20260904T051420`, 8 files, 34.3 h |

The shared `rzz` episode of 2026-09-03 on four couplers at once looks like a calibration-side
event rather than four independent faults (an inference). For `cz` on 102-103, P7 of
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` reported 89% of files at the placeholder
at `09fcc45`; at `7b84b50` the share is 88.8% (P), and what is new is that the coupler left the
placeholder after file `20260929T022626`, with a median record error of 7.41e-2 since (P
`cz.lengths`).

### 6.2 Are the qubits of faulty couplers healthy?

Per-qubit medians and their percentile among the 156 qubits (L `faulty_coupler_qubits`; the
percentile is the share of qubits at or below):

| Coupler (fault) | Qubit | `sx` median (percentile) | `T1` us (pct) | `T2` us (pct) | Readout (pct) |
| --- | --- | --- | --- | --- | --- |
| 27-28 (`cz` always, `rzz` 96%) | 27 | 5.43e-3 (1.00) | 103 (0.14) | 106 (0.50) | 0.0109 (0.58) |
| | 28 | 2.48e-4 (0.27) | 157 (0.87) | 149 (0.85) | 0.0066 (0.30) |
| 32-33 (both always) | 32 | 2.82e-4 (0.42) | 116 (0.24) | 126 (0.68) | 0.0284 (0.87) |
| | 33 | 2.42e-4 (0.23) | 123 (0.36) | 125 (0.68) | 0.0183 (0.80) |
| 71-72, 72-73 (both always) | 72 | placeholder in every file | 21.5 (0.006) | absent | 0.332 (1.00) |
| 95-99, 99-115 (`rzz` always) | 99 | 2.70e-4 (0.34) | 111 (0.19) | 35.7 (0.14) | 0.0249 (0.84) |
| 102-103 (`cz` 89%) | 102 | 1.80e-3 (0.98) | 124 (0.37) | 82.2 (0.36) | 0.0935 (0.99) |
| | 103 | 2.65e-4 (0.30) | 98.5 (0.10) | 104 (0.48) | 0.0115 (0.61) |

So 71-72 and 72-73 sit on a dead qubit; 27-28 and 102-103 each have a candidate qubit-side cause
(q27 has the worst `sx` on the device, q102 sits at the 98th percentile on `sx` and the 99th on
readout); 95-99 and 99-115 share q99, whose `T2` median is at the 13.5th percentile. **32-33 has
two qubits none of whose reported medians is extreme (all between the 23rd and the 87th
percentile), so its permanent fault on both gates is unexplained by the document.** (Qubits 71,
73, 95 and 115 are also in L; on `sx` and `T1` all sit between the 14th and the 86th percentile.)

### 6.3 `zz` anomalies

13 couplers are ever negative, one (68-69) in every file (median -4.33 kHz, range -5.43 to -3.11,
no sign change; it is also one of the three 116 ns `rzz` couplers). Extreme values occur on the
couplers of dead or poor qubits: 72-73 swings between -729 and +615 kHz with 104 sign changes,
71-72 has 92 sign changes, 11-12 reaches -735 and +770 kHz, 11-18 -938 kHz (Z `negative_couplers`).
Record quantiles are 3.05 kHz (10%) to 13.8 kHz (90%), 25.2 kHz at 99% (Z `record_khz_q`). Per
coupler, the interquartile range over time is a median 0.108 of the coupler's median (Z
`per_coupler_iqr_over_median_q`). Zeros are a missing marker, and 13-14, 39-53 and 109-118 have
been frozen at a single value since 2026-07-10 (§1.4): a model that uses `zz` must treat those
three as unrefreshed, not as perfectly stable.

### 6.4 Data-quality notes

- The placeholder stamp is written at assembly (§1.3); always mask before forming events, as
  01-data-layer.md §4 requires. Without masking, `cz` placeholder couplers would produce a
  "re-measurement" in almost every file.
- Before the split the archive misses documents; event rates there are lower bounds (§2.3).
- The first event of a series can predate the archive (stamps from 2026-05-05 and one in
  2026-04), so a first gap is a gap in IBM's schedule only from the second event on.
- Shared-layer note: `results/data-layer/profile.json` labels `g2.cz.gate_length` and
  `g2.rzz.gate_length` with `event_rule` "measured", while 01-data-layer.md §4 assigns every
  `gate_length` to the value-only rule. For these two fields both rules give the same events
  (one per coupler, two on 71-72 and 72-73), so no number changes; the label is inconsistent.
- 01-data-layer.md §5 says that the event counts of one direction of a coupler can differ from
  the other's because dates differ. After placeholder masking that cannot happen for `cz` or
  `rzz` (§1.3).

## 7. Relationships

### 7.1 `cz` against `rzz` on the same coupler

| Item | Value | Source |
| --- | --- | --- |
| Couplers with both series | 170 | R |
| Per-coupler median ratio `rzz/cz`: min, 10%, median, 90%, max | 0.217, 0.812, 0.968, 1.170, 1.720 | R `levels` |
| Couplers with `rzz` median below `cz` | 60.6% | R |
| Spearman of coupler medians | 0.896 (n 170) | R |
| Same-file `log10(rzz/cz)` median; share `rzz < cz` | -0.0196; 57.2% (296,321 records) | R |
| Offset of the nearest `rzz` event from each `cz` event, h: 10%, 25%, median, 75%, 90% | -5.68, +0.89, +1.15, +2.67, +12.8 | R `timing` |
| Median offset before / from the split (h) | +1.01 / +2.06 | R |
| `cz` events with an `rzz` event 0 to 3 h later | 61.8% | R |
| Matched changes: Spearman (pairs); after removing round medians | 0.137 (14,557); 0.127 | R `changes` |
| Null (other couplers, same round): median, 97.5% | 0.012, 0.026 | R |
| Per coupler change Spearman: median (167 couplers) | 0.134 | R |
| Within-coupler level co-movement (demeaned), Spearman | 0.293 (17,110) | R |

Extremes: on 31-32, `rzz` is 0.217 of `cz` (`cz` median 4.01e-2, `rzz` 8.71e-3); on 148-149,
149-150 and 102-103, `rzz` is 1.64 to 1.72 times `cz`. **`cz` and `rzz` measure the same
coupler's quality** (between-coupler 0.90): they are separate calibrations run in separate
rounds, `rzz` typically about an hour after `cz`, sharing the coupler's level and a small part of
their fluctuation (§4.4). Neither is a copy of the other, and the `rzz` level is not
systematically higher, even though the averaged-angle `rzz` gate is a different operation.

### 7.2 Coherence limit (assigned link)

Formula, from P4 and imported from `scripts/feature_patterns.py` (`process_fidelity_1q`): each
qubit's process fidelity under amplitude and phase damping over the gate length `t` is
`F_k = (1 + exp(-t/T1_k) + 2 exp(-t/T2_k)) / 4`; for independent channels the two-qubit process
fidelity is `F_1 F_2`, and the average infidelity is `e_coh = 1 - (4 F_1 F_2 + 1) / 5` (`d = 4`).
The pieces are cited in the 2026-10-05 survey §2.2 (Ghosh, Fowler and Geller 2012; Nielsen 2002;
Abad et al. 2022). Qiskit Experiments ships `RBUtils.coherence_limit(nQ=2, T1_list, T2_list,
gatelen)`, documented as "the error per gate (1-average_gate_fidelity) given by the T1,T2 limit"
(fetched 2026-10-06; this closes the 2026-10-05 survey's unverified lead in §4 as to its
existence, but its formula was not printed and the package is not installed, so no numerical
cross-check was run).

| Item | Value | Source |
| --- | --- | --- |
| Limit of a 68 ns gate at the median `T1` 125.9 us and `T2` 92.44 us (all records) | 8.04e-4 | L `reference_limits` |
| First-order check, `(2/5) t sum_k (1/T1_k + Gamma_phi_k)` (Abad et al. eq. 12) | 8.05e-4 | L |
| At 84, 88, 116 ns | 9.93e-4, 1.04e-3, 1.37e-3 | L |
| At the 10th-percentile `T1` (75.6 us) and `T2` (28.6 us) on both qubits, 68 ns | 2.26e-3 | L |
| Median `cz` event error over the 68 ns limit at the medians | 3.41 (`rzz` 3.30) | L |
| Per event, limit / error: 10%, median, 90% (`cz`) | 0.138, 0.333, 0.711 | L `cz.limit_over_error_q` |
| Per event, limit / error: 10%, median, 90% (`rzz`) | 0.150, 0.351, 0.727 | L |
| Events where the limit exceeds the error | 2.6% (`cz`), 3.4% (`rzz`) | L |
| Events with `T2 > 2 T1` on either qubit | 43 (`cz`), 34 (`rzz`) | L |
| Hours between the gate stamp and its qubits' `T1`/`T2` stamps: median, 90% | 3.5, 15.9 (`cz`) | L |
| Within-file Spearman of log error and log limit across couplers: median (352 files) | 0.237 (`cz`), 0.296 (`rzz`) | L |

The limit uses the `T1` and `T2` current in the gate's file, measured hours earlier or later, so
it is a proxy, not a bound (2.6% of events exceed it). In the median the reported error is about
three times the coherence limit; for comparison, the 2026-10-05 survey §2.2 derived a median of
2.67 from eleven 2021 IBM test pairs (Stehlik et al., not re-derived here, and a different device
and definition), and non-IBM tunable-coupler CZ gates are reported "close to their T1 limits"
(Sung et al., same section). **Decoherence during the gate accounts for a median of about a
third of a Heron r2 two-qubit error (0.333 for `cz`, 0.351 for `rzz`)**, consistent with P4 at
the older ref (0.33 and 0.35 there).

### 7.3 `sx` and readout of the two qubits (assigned link)

| Correlation (Spearman) | `cz` | `rzz` |
| --- | --- | --- |
| Between couplers (medians, n 172 / 171): error vs limit | 0.334 | 0.391 |
| error vs `sx_a + sx_b` | 0.577 | 0.579 |
| error vs `ro_a + ro_b`; vs `max(ro_a, ro_b)` | 0.171; 0.164 | 0.192; 0.187 |
| limit vs `sx` sum | 0.256 | 0.249 |
| partial: error vs `sx` given limit | 0.539 | 0.540 |
| partial: error vs limit given `sx` | 0.236 | 0.312 |
| partial: error vs readout given limit and `sx` | -0.012 | 0.021 |
| Within couplers, consecutive changes: vs limit | 0.025 | 0.008 |
| vs `sx` sum; vs readout sum | 0.048; 0.007 | 0.025; 0.016 |
| Within couplers, demeaned levels: vs limit; vs `sx` sum; vs readout sum; vs `T1_a T1_b` | 0.078; 0.158; 0.041; -0.079 | 0.082; 0.137; 0.035; -0.086 |

(L `*.between_coupler`, `within_coupler_changes`, `within_coupler_demeaned_levels`; within-coupler
n between 18,034 and 22,092. The p-values in L treat events as independent and overstate
significance.)

Reading:

- **Which couplers are bad is predicted best by their qubits' single-qubit gate errors**, much
  more than by coherence, and readout adds nothing once both are known. Two mechanisms fit,
  both interpretations: (i) two-qubit RB sequences contain single-qubit Cliffords, so the
  reported error includes a share of single-qubit error unless it is corrected out; the Qiskit
  Experiments RB manual describes such a correction for two-qubit RB ("composite depolarization
  from both single-qubit and two-qubit gates", fetched 2026-10-06), and whether IBM applies one is
  not documented; (ii) a qubit with a nearby TLS or a frequency crowding problem degrades
  everything it takes part in. (i) is falsified if IBM's per-edge value is shown to be corrected
  for single-qubit contributions; (ii) predicts that the shared-qubit correlation of §4.4 is
  strongest around qubits with poor `sx`, which is testable.
- **When a coupler changes, its qubits' reported values hardly move with it** (0.05 or less for
  changes, at most 0.16 for demeaned levels), the same answer as P3 and P4 at the older ref.

### 7.4 `zz` against `cz` and `rzz`

Between couplers, median `|zz|` is unrelated to the median error (Spearman 0.010, p 0.89, n 172
for `cz`; -0.027, p 0.72, n 171 for `rzz`); within couplers, the current `|zz|` at each gate event
co-moves at -0.020 (`cz`, n 21,700) and -0.014 (`rzz`, n 17,880) (Z `relations`). At the kHz level
reported here, static ZZ is not what makes a two-qubit gate good or bad on this device.

The exploratory observation: the five couplers with a non-68 ns length (102-103 and 146-147 at
88 ns; 68-69, 80-81 and 106-107 at 116 ns for `rzz`) have median `|zz|` of 2.85, 3.06, 4.33, 3.04
and 1.47 kHz against a median of 6.35 kHz for the other 168 (71-72, 72-73 and 32-33 left out),
Mann-Whitney p 1.1e-4; in only 7.6% of the (one of the five, one of the others) pairs is the
first `|zz|` the larger (Z `non_68ns_length_vs_abs_zz`). One physical story (interpretation): a weak effective coupling gives
both a small static ZZ and a slower entangling interaction, so IBM lengthens the gate there. The
observation was found by looking at the ranks, so the p-value is not a test of a prior
hypothesis. It is falsified if the same comparison on another Heron r2 backend shows no
difference.

## 8. Use cases and why each field matters

| Field | In this project | In the literature | Why it matters |
| --- | --- | --- | --- |
| `cz.gate_error` | Not yet used by the engine: under ADR-028 every multi-qubit gate is categorically ineligible for a noise channel, and a multi-qubit channel under ADR-008 must change that policy as well (`docs/decisions.md`, ADR-028 Consequences). Listed as a candidate forecasting target in the 2026-10-05 recommendation for A9 (open) | Noise-aware qubit mapping uses per-link errors and their variation (Tannu and Qureshi 2018; Murali et al. 2019); fresh 2Q error measurements improve circuit accuracy over daily data (Wilson et al. 2020); calibration-built digital twins (Bautra et al. 2026) (all 2026-10-05 survey §2.1, §2.5) | The largest per-gate error the document reports for a basis gate: the `cz` event median (2.75e-3) is an order of magnitude above the median `sx` error (3.12e-4, 01-data-layer.md §3); its level is a stable per-coupler property with a slowly moving level and a large non-persistent part |
| `rzz.gate_error` | Same as `cz`; not in the archive's `target.operations` | Fractional RZZ executes ZZ rotations without `cz` decomposition, reducing duration and error ("Fractional gates", fetched 2026-10-06); the 2026-10-05 survey §1 found nothing on its temporal behaviour | A separate calibration with its own cadence, faults and a cadence change after August; using `cz` in its place would miss 13 fault entries and the different schedule |
| `gate_length` | Needed for any coherence floor (P4; the R3 reference of the 2026-10-05 document, a recommendation) | Duration enters every decoherence bound (2026-10-05 survey §2.2) | A configuration value, constant except for one change on two dead couplers; the non-68 ns couplers are where `rzz/cz` and `|zz|` differ |
| `zz` | Unused | Parasitic crosstalk limits gates, and static ZZ is engineered down with tunable couplers (Mundada et al., fetched); measured in Qiskit by `ZZRamsey` (fetched) | A spectator and idle-error quantity for circuit-level noise models; unrelated to the gate errors at this level; behaves as a 5-hourly re-determined value |
| `jq` | Unused | none found | Carries no information (0 everywhere) |
| Placeholders | Masked before events; faulty couplers excluded and listed (P7) | The 1.0 sentinel on `ibm_fez` inflates means (Hassan and Kaabouch 2026, 2026-10-05 survey §2.3); IBM's definition (fetched) | A state lasting days to months, not a value; entries are rare (2 and 13) |

## 9. Open questions, and what measurement would settle each

1. **What is the unshared part of the non-persistent component: (a), (b) or (c)?** Settled by
   per-value RB uncertainties from IBM (not in the document), by a statement from IBM on whether
   two-qubit gates are re-tuned in each round, or by repeated two-qubit RB on a few couplers
   minutes apart with and without recalibration (QPU time; the team decides).
2. **What is the shared qubit-level component?** Stratify the shared-qubit correlation by the
   shared qubit's `sx` level (prediction of mechanism (ii) in §7.3) and, for 07, against
   qubit-level families beyond this link. A frequency record would settle a TLS reading, but the
   document carries none.
3. **Does the `cz`-`rzz` decline with offset survive stratification by round?** Recompute §4.4
   item 2 within rounds (falsification test stated there).
4. **Is `zz` measured or computed, and on which loop?** 06 can test the alignment of `zz` bursts
   with readout and `T1` rounds; an IBM source documenting `zz_<ab>` would settle it.
5. **Why did the `rzz` cadence fall after August, and what was the 279.8 h `rzz` pause?** 06 owns
   the calibration schedule across families; a matching change in other families would point to
   a procedure change.
6. **Why is 32-33 permanently faulty?** Nothing reported on its qubits explains it; an IBM
   fault record or a second backend's history would.
7. **Does a non-68 ns length go with low `|zz|` elsewhere?** Repeat the comparison on another
   Heron r2 archive (out-of-sample test of an exploratory finding).
8. **Which angle and length does the reported `rzz` represent?** The error is averaged over
   angles (IBM); whether the single reported length is the `pi/2` duration would be settled by
   reading the fractional `Target` (`use_fractional_gates=True`) of the same backend, a
   project-side check not run here.
9. **Does the project's coherence limit equal `RBUtils.coherence_limit`?** Run both on the same
   inputs in an environment with Qiskit Experiments installed.

## 10. Reproduce, results files, and what was sampled or capped

From the repository root, with the cache of 01-data-layer.md §1 built (about 15 to 25 s each on
the laptop):

```bash
PY=C:/t/venv/Scripts/python.exe
A=docs/findings/2026-10-06-feature-deep-dive/analysis/gates_2q
$PY $A/profile_2q.py      # results/gates_2q/profile.json
$PY $A/cz_vs_rzz.py       # results/gates_2q/cz_vs_rzz.json
$PY $A/temporal_2q.py     # results/gates_2q/temporal.json
$PY $A/variograms_2q.py   # results/gates_2q/variograms.json
$PY $A/zz_2q.py           # results/gates_2q/zz.json
$PY $A/spatial_2q.py      # results/gates_2q/spatial.json
$PY $A/link_qubits.py     # results/gates_2q/link.json
C:/t/ruffpin/Scripts/ruff.exe check $A
C:/t/ruffpin/Scripts/ruff.exe format --check $A
```

`common2q.py` holds the shared helpers (canonical coupler, coverage split, rounds, Spearman,
Benjamini-Hochberg, Kruskal-Wallis with epsilon squared, local detrend). Permutation tests use the
fixed seed 20261006, so reruns reproduce the p-values.

Fields loaded: `g2.cz.*`, `g2.rzz.*`, `gen.jq`, `gen.zz`, and for the link only `q.T1`, `q.T2`,
`g1.sx.gate_error`, `q.readout_error`; per-file `last_update_ms` and `has_configuration` (coverage
split); `meta.json` coordinates, coupling map and target union.

Sampled, capped, excluded (nothing else is):

- Canonical column `[a, b]` with `a < b` for every `g2` statistic (§1.3 shows no loss).
- Permanently faulty couplers have no events and drop out of event statistics: `cz` 27-28, 32-33,
  71-72, 72-73; `rzz` 32-33, 71-72, 72-73, 95-99, 99-115.
- `log10 |zz|` statistics exclude the four couplers with zeros (13-14, 32-33, 39-53, 109-118; the
  three other than 32-33 have also been frozen since 2026-07-10); the within-coupler `zz` relation
  tests skip couplers with a zero at any of their gate events.
- Lists in the JSONs are capped: `rzz` gaps over 168 h (193) listed to 60; placeholder runs to 12
  per coupler; negative `zz` couplers to 20 (13 exist, so none cut); per-coupler change-point
  discoveries listed to the top 12.
- Within-file Spearman of error against limit uses every 5th file (352 files).
- `cz`-`rzz` matching uses the nearest `rzz` event within 6 h for changes and levels; 4,720 of
  21,830 `cz` events had none and are left out of those two statistics (the offset table uses all).
- Per-coupler change points need at least 30 events (171 `cz`, 168 `rzz` couplers tested);
  per-pair spatial correlations need at least 30 common rounds (230 and 225 pairs).
- Seasonality and burst tests drop groups below 200 events (counted in T and Z).
- Local deviations (moving median of 3 + 3 neighbours) are formed only for series with at least
  8 events (spatial, link, `cz`-`rzz` offset and seasonality statistics).
- The null for the `cz`-`rzz` change correlation uses 200 within-round reshuffles; device change
  points 999 shuffles; per-coupler change points 499; Moran's I 9,999.

## 11. Sources

Fetched 2026-10-06 in this session: 9 new sources (rows marked "new") and 1 existing source
re-fetched; one fetch of arXiv:1808.00290 returned an unrelated paper (title did not match) and
was discarded. Everything else is cited from the two existing surveys by section.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum documentation, "View backend details" (new) | https://quantum.cloud.ibm.com/docs/en/guides/qpu-information | fetched 2026-10-06 | 2Q error from RB in isolation batches; `rzz` error averaged over angles; placeholder 1 after several days; EPLG formula; gate length; "Backend properties update after the calibration sequence completes" |
| IBM Quantum documentation, "Fractional gates" (new) | https://quantum.cloud.ibm.com/docs/en/guides/fractional-gates | fetched 2026-10-06 | RZZ angle range; Heron support; `use_fractional_gates`; Target error "a copy of the non-fractional gate's counterpart" |
| IBM Quantum documentation, "Processor types" (new) | https://quantum.cloud.ibm.com/docs/en/guides/processor-types | fetched 2026-10-06 | Heron r2: 156 qubits, heavy-hex, TLS mitigation feature (background) |
| Qiskit Experiments 0.14.2, "Randomized Benchmarking" manual (new) | https://qiskit-community.github.io/qiskit-experiments/manuals/verification/randomized_benchmarking.html | fetched 2026-10-06 | Two-qubit RB includes single-qubit gates; correction formula exists |
| Qiskit Experiments 0.14.2, "RBUtils" API (new) | https://qiskit-community.github.io/qiskit-experiments/stubs/qiskit_experiments.library.randomized_benchmarking.RBUtils.html | fetched 2026-10-06 | `coherence_limit(nQ, T1_list, T2_list, gatelen)` exists, returns 1 minus average gate fidelity |
| Qiskit Experiments 0.14.2, "ZZRamsey" API (new) | https://qiskit-community.github.io/qiskit-experiments/stubs/qiskit_experiments.library.characterization.ZZRamsey.html | fetched 2026-10-06 | ZZ Hamiltonian term and Ramsey measurement |
| qiskit-ibm-runtime, "BackendProperties (latest version)" (new) | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/models-backend-properties | fetched 2026-10-06 | `general` is a list of `Nduv`; no definition of `jq` or `zz` |
| Mundada, Zhang, Hazard, Houck, Suppression of Qubit Crosstalk in a Tunable Coupling Superconducting Circuit (2018) (new) | arXiv:1810.04182 | fetched 2026-10-06 | Parasitic crosstalk limits gates; a tunable coupler can make ZZ contributions interfere destructively |
| Gambetta, Córcoles, Merkel et al., Characterization of addressability by simultaneous randomized benchmarking (2012) (new) | arXiv:1204.6308 | fetched 2026-10-06 | Simultaneous RB reveals crosstalk; alternative reading of shared deviations |
| Stehlik, Zajac, Underwood et al., Tunable Coupling Architecture for Fixed-frequency Transmons (2021) | arXiv:2101.07746 | existing survey 2026-10-05 §2.1, §2.2; abstract re-fetched 2026-10-06 (it does not mention ZZ, so it is not cited for ZZ) | Tunable-bus two-qubit gates on fixed-frequency transmons; derived EPG/limit 2.67 (survey's arithmetic) |
| McKay et al., Benchmarking Quantum Processor Performance at Scale (2023) | arXiv:2311.05933 | existing survey 2026-10-05 §2.2 | Layer fidelity and EPLG on Heron |
| Ghosh, Fowler, Geller (2012); Nielsen (2002); Abad et al. (2022) | arXiv:1210.5799; arXiv:quant-ph/0205035; arXiv:2110.15883 | existing survey 2026-10-05 §2.2 | Coherence-limit formula and its first-order check |
| Sung et al. (2021) | arXiv:2011.01261 | existing survey 2026-10-05 §2.2 | Non-IBM tunable-coupler CZ close to its T1 limit |
| Wallman and Flammia, Randomized Benchmarking with Confidence (2014) | arXiv:1404.6025 | existing survey 2026-10-05 §2.1 | RB precision depends on unpublished settings |
| Thorbeck et al. (2023); Hirasaki et al. (2023) | arXiv:2210.04780; arXiv:2307.04337 | existing survey 2026-10-05 §2.3, §2.1 | Hour-scale TLS dynamics; minute-scale step changes |
| Klimov et al. 2018; Burnett et al. 2019 | arXiv:1809.01043; arXiv:1901.04417 | existing survey 2026-10-04 §3 | TLS-driven, qubit-local fluctuations (physics prior) |
| Tannu and Qureshi (2018); Murali et al. (2019); Wilson et al. (2020) | arXiv:1805.10224; arXiv:1901.11054; arXiv:2005.12820 | existing survey 2026-10-05 §2.1 | Uses of per-link errors and their variation |
| Bautra, Dimitrijevs, Yakaryilmaz (2026) | arXiv:2603.14607 | existing survey 2026-10-05 §2.5 | Calibration-based digital twins |
| Hassan and Kaabouch (2026) | arXiv:2602.21253 | existing survey 2026-10-05 §2.3 | The 1.0 sentinel on `ibm_fez` |

Project sources: `01-data-layer.md` (field semantics, readout cadence 4.47 h, identities);
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P2, P3, P4, P6, P7 at `09fcc45`);
`docs/decisions.md` (ADR-028 Consequences); `scripts/feature_patterns.py` (event rule and
`process_fidelity_1q`).

## Verification (2026-10-06)

Verifier note, appended under the append-only rule; the body above is unchanged except for the
inline **[Verification 2026-10-06: ...]** markers. Same provisional basis (ref `7b84b50`, 1,760
files, lead's laptop). Verifier scripts: `analysis/verify/gates_2q/` (`compare_reruns.py`,
`v_core.py`, `v_challenge.py`, `v_link.py`, written from `ddload` without importing the owner's
code); results: `results/verify/gates_2q/` (`compare_reruns.json`, `core_check.json`,
`challenge_check.json`, `link_check.json`).

### What was re-run

1. All seven owner scripts (`profile_2q`, `cz_vs_rzz`, `temporal_2q`, `variograms_2q`, `zz_2q`,
   `spatial_2q`, `link_qubits`) were re-run; every results JSON reproduces leaf for leaf
   (4,527 numeric leaves compared, 0 differences apart from `measured_utc`; `compare_reruns.json`).
   Every JSON the document cites exists and is current.
2. Independent recomputation of the numbers below, from the cache through `ddload`.

### Numbers checked

| Claim | Document value | Recomputed | Match |
| --- | --- | --- | --- |
| Direction identity: value mismatches (`cz`, `rzz`) | 0, 0 of 309,760 | 0, 0 of 309,760 | yes |
| Date mismatches, all in placeholders | 8,682, 12,395 | 8,682, 12,395 (all in placeholders) | yes |
| Median stamp offset in mismatches (us) | 6.10, 7.08 | 6.10, 7.08 | yes |
| Events, measured rule | 22,092; 18,210 | 22,092; 18,210 | yes |
| Median event error | 2.75e-3; 2.66e-3 | 2.75e-3; 2.66e-3 | yes |
| Lag-1 autocorrelation of log changes | -0.448; -0.425 | -0.448; -0.425 | yes |
| One-round semivariance over long-lag level | 0.64; 0.54 | 0.638; 0.544 | yes |
| Coupler-median Spearman `cz` vs `rzz`; median ratio | 0.896; 0.968 | 0.896; 0.968 | yes |
| Shared-qubit deviation Spearman (`cz`, `rzz`) | 0.220; 0.226 | 0.220; 0.225 (own local-deviation code) | yes |
| Four or more hops apart | -0.008 | -0.008 | yes |
| Coherence limit of 68 ns at median `T1` 125.9, `T2` 92.44 | 8.04e-4 | 8.04e-4 | yes |
| Between-coupler Spearman: error vs `sx` sum; vs readout sum | 0.577; 0.171 | 0.577; 0.171 | yes |
| Error vs limit (per-qubit medians, own construction) | 0.334 | 0.318 | approximately (different qubit-level reduction; ordering unchanged) |
| Partial: error vs `sx` given limit; limit given `sx`; readout given both | 0.539; 0.236; -0.012 | 0.542; 0.217; -0.004 | approximately |
| Moran's I of `cz` levels | 0.263 | 0.263 (binary weights; 0.282 row-standardized; p 0.0004 vs 0.0006) | yes |
| `zz`: files changing any coupler; bursts changing 170 or more | 486; 484 | 486; 484 | yes |
| `zz`: median burst gap (h); median couplers changed | 5.16; 172 | 5.16; 172 | yes |
| `abs(zz)` value events; lag-1 of changes | 83,440; -0.513 | 83,440; -0.513 | yes |
| Median `abs(zz)` of records (kHz) | 6.18 | 6.23 (all nonzero records, my filter) | approximately |
| Non-68 ns couplers vs `abs(zz)`, Mann-Whitney p | 1.1e-4 | 1.09e-4 | yes |
| Events per coupler per day, `cz` before / from split | 0.880 / 0.869 | 0.871 / 0.849 | approximately (my denominator is calendar time over all couplers; same conclusion) |
| Same for `rzz` | 0.809 / 0.607 | 0.798 / 0.590 | approximately |
| Non-placeholder `cz` stamps that are whole seconds | 1.0 | 1.0 | yes |

### Claims challenged

| Claim | Verdict | Why |
| --- | --- | --- |
| A shared part of the non-persistent component exists (summary 7, 4.4, 4.5) | upheld | Hop 1: 0.220 (`cz`), 0.225 (`rzz`); hop 2: -0.008, -0.019; hop 3: -0.010, -0.020, so the effect is confined to couplers sharing a qubit. Cross-round correlations (lag 1, lag 2) of the same deviations are -0.035 and -0.050 (`cz`), so it is not a slow shared shift leaking through the detrending. Per shared qubit the median rho is 0.186 (`cz`) and 0.20 (`rzz`), positive for 95% of 43 and 42 qubits. Stronger for shared qubits with high `sx` (0.228 against 0.186 `cz`; 0.262 against 0.150 `rzz`), in line with the document's testable prediction of mechanism (ii), but it is a tercile split of 14 to 15 qubits. The text does not say what the unshared part is. |
| `cz`-`rzz` shared deviation falls with offset (4.4 item 2) | upheld, with a changed test | The proposed stratification by round is not feasible as written (the offset is nearly constant within a round pair). Per cz round with at least 60 matched couplers (104 rounds), the across-coupler Spearman has median 0.159 at offset up to 2 h and 0.055 beyond, and correlates with offset at -0.393 (p 3.8e-5). The non-monotone 12 to 24 h bump remains unexplained. |
| About three quarters of the one-round nugget is present within hours (4.2, summary 8) | weakened | The fraction depends on the gap: 0.33, 0.64, 0.73, 0.89 of the one-round value at 2 to 4, 6 to 9, 9 to 12, 12 to 18 h. Short-gap occasion semivariance rises with the gap (Spearman 0.36 `cz`, 0.37 `rzz`); mean 0.0079 for gaps under 8 h against 0.0104 for longer (`cz`), 0.0076 against 0.0130 (`rzz`). Marked inline. |
| Short change below the preceding, Wilcoxon p 0.0011 and 2.9e-6 (4.2) | refuted as stated | Pseudo-replication over coupler pairs; 11 and 6 independent occasions give sign-test p 0.065 (`cz`) and 0.69 (`rzz`), signed-rank 0.10 and 0.56. Marked inline. |
| `rzz` cadence fell after the coverage split (summary 4, 2.3) | weakened | Excluding the 279.8 h pause the post-split rate is 0.729 against 0.809 before; most of the fall is one pause. Marked inline. |
| Gate error clusters on the graph (5.2) | upheld | Moran's I reproduced with an independent implementation; consistent with the qubit-sharing effect, so probably one phenomenon (interpretation). |
| `sx` explains more than coherence (summary 10, 7.3) | weakened in wording | Rank correlations reproduce (0.577 against 0.318 to 0.334), but "explains" is causal. The limit is a proxy from `T1` and `T2` stamped hours apart, so its weaker correlation is partly proxy noise, and mechanism (i) (IBM's page, re-fetched, says the 2Q benchmark alternates single-qubit Clifford sequences with two-qubit gates) would give the same pattern with no physical coupling. The body hedges both mechanisms; only the summary verb is strong. |
| Non-68 ns length goes with low `abs(zz)` (7.4) | upheld as exploratory | p reproduced; on the three `rzz` 116 ns couplers alone p is 0.0055. The number of comparisons scanned before finding it is unknown, as the document says. |
| The component is not called estimation or measurement noise (4.5) | upheld | No unsupported attribution found. |

### Sources spot-checked (fetched 2026-10-06)

| Source | Result |
| --- | --- |
| arXiv:1810.04182, Mundada et al. | Title "Suppression of Qubit Crosstalk in a Tunable Coupling Superconducting Circuit" matches; the abstract says parasitic crosstalk is a leading limitation for quantum gates and that a coupler frequency can be set so ZZ interactions interfere destructively. Supported. |
| arXiv:1204.6308, Gambetta et al. | Title "Characterization of addressability by simultaneous randomized benchmarking" matches; the abstract describes individual then simultaneous RB, addressability from the fidelity difference, and two samples with different cross-talk. Supported as a protocol-effect alternative. |
| IBM "View backend details" | An error of 1 means benchmarking has not succeeded for several days ("stale", "undefined"); 2Q error from isolation batches with at least two qubits between edges, with single-qubit Cliffords alternating with two-qubit gates; RZZ error averaged over angles with an RB variant for arbitrary unitaries. Supported. |

No new sources were added by the verifier.

### Rule check

- No em dashes (U+2014) in the document or the verifier scripts (0 found).
- Provisional banner, ref, basis and machine present in the header; verifier JSONs carry `ddload.result_header`.
- Every body number traces to a results field of the owner's JSONs, which reproduce. The 4.2 Wilcoxon p-values trace but are invalid (marked). Inconsistent label: the summary says "Second calibrations" while 4.2 says recalibration cannot be distinguished from re-measurement.
- No rows added to `docs/numerical-claims.md` by this verification (not touched; no git command was run to confirm the whole tree).
- Pinned ruff `check` and `format --check` pass on `analysis/verify/gates_2q/`.
