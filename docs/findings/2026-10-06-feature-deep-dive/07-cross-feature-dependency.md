# 07 · Cross-feature dependency: what the calibration families share, and what they do not

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: append-only
after today; reconcile it later by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Ref: `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`, all 1,760 `ibm_fez` snapshot files (2026-05-13 to
2026-10-06), read only through `analysis/ddload.py`. Basis: 156 qubits and 176 couplers, eleven
families of re-measurement events (counts in §1.1), measured on 2026-10-06 on the lead's laptop
(Windows 11, CPython 3.12 venv, numpy 2.4.4, scipy 1.17.1); provisional until re-run on the
verification desktop. Nothing here is registered in `docs/numerical-claims.md`. Every number
below is a field of a JSON in `results/cross/` written by a script in `analysis/cross/`, a field
of `results/data-layer/*.json`, or a figure quoted from a named repository document.

This scope owns no field. It reads every informative field and analyses the relationships
between families, except four links owned by other documents (§1.3). The advisor's answers and
decisions A1 to A9 are open; nothing here is a decision or records an approval.

## 0. Summary

{{SUMMARY}}

## 1. The fields and how IBM produces them

### 1.1 The families this document uses

Every family is reduced to re-measurement events by `ddload.series` under the rule the data
dictionary assigns (`01-data-layer.md` §4), placeholders (`gate_error >= 1`) masked before
events are formed, values in `log10` (`analysis/cross/xcommon.py`). Counts are
`results/cross/alignment.json` `families`.

| Family | Field | Rule | Series | Events | Events per series (median) |
| --- | --- | --- | --- | --- | --- |
| `T1` | `q.T1` | measured | 156 | 20,063 | 130 |
| `T2` | `q.T2` | measured | 155 | 20,626 | 134 |
| `RO` | `q.readout_error` | measured | 156 | 90,408 | 580 |
| `p01` | `q.prob_meas1_prep0` | measured | 156 | 88,975 | 572 |
| `p10` | `q.prob_meas0_prep1` | measured | 156 | 85,849 | 574 |
| `init` | `q.init_error` | measured | 116 | 23,952 | 241 |
| `m2` | `g1.measure_2.gate_error` | measured | 156 | 7,925 | 51 |
| `sx` | `g1.sx.gate_error` | measured | 155 | 20,207 | 132 |
| `cz` | `g2.cz.gate_error`, column `[a, b]` with `a < b` | measured | 172 | 22,092 | 131 |
| `rzz` | `g2.rzz.gate_error`, same columns | measured | 171 | 18,210 | 110 |
| `zz` | `gen.zz`, absolute value | value only | 175 | 83,443 | 486 |

Choices, each logged:

- **Duplicates are not re-used.** `x`, `id`, `rx` and `xslow` carry `sx`'s values, `measure`
  carries `readout_error`'s, and the two directions of a coupler carry the same value
  (`01-data-layer.md` §5); one copy of each enters.
- **Not used:** every `threshold` (a discriminator setting in arbitrary units, value-only),
  every length (device-wide configuration, `01-data-layer.md` §5), `gen.jq` (0 everywhere) and
  `gen.lf` (one value per qubit chain, not per qubit; its link to its chain's gate errors
  belongs to `06-device-time-topology.md`).
- **`p01` and `p10`** are multiples of 1/4,096, and `p01` is exactly 0 in 2,468 records
  (`alignment.json` `families.p01.raw_records_le_zero`), so their log uses a continuity offset
  of half a shot, `log10(p + 1/8192)`, applied to both.
- **`zz`** has 5,468 records at or below zero, 2,421 of them negative
  (`families.zz.raw_records_le_zero`, `raw_records_lt_zero`). The analysis uses `|zz|` and
  masks exact zeros as a candidate placeholder (32-33 is 0 in every file,
  `01-data-layer.md` §5). Its event time is the first file carrying the new value, not a
  measurement time, so any `zz` timing finer than about a day is not interpretable.
- **Qubit view of the coupler families.** For between-qubit work a qubit receives the mean of
  its adjacent couplers' values (`adj_cz`, `adj_rzz`, `adj_zz`); for event work a coupler event
  is attached to both of its qubits.

### 1.2 How IBM produces them, and the clock visible in the stamps

IBM's documentation page "Monitoring, calibrations, and benchmarking" (fetched 2026-10-06)
says that the reported metrics come from a daily benchmarking pass (single-qubit randomized
benchmarking in batched groups, `T1`/`T2`, readout fidelity, two-qubit gate errors by RB on the
native gates, and layer fidelity); that parameter-monitoring jobs run about once an hour and
check, among other things, readout angles, amplitudes and discriminator thresholds and
signatures of TLS activity; that single-qubit and readout calibrations are batched and run
concurrently while two-qubit calibrations run in batches of non-nearest-neighbour qubits; and
that when severe TLS activity is detected the calibration strategy for the affected qubits'
gates may be changed, including pausing calibrations. The page gives no time of day and no
order within the daily pass.

The stamps give the order on one qubit. For every event of family A, the nearest event of
family B on the same qubit (inside B's lifetime; `alignment.json`
`nearest_event_gap_same_qubit`):

| A, B | A events | Median gap (h) | Within 0.25 h | Within 3 h | B after A (share of non-zero gaps) |
| --- | --- | --- | --- | --- | --- |
| `T1`, `T2` | 19,880 | 0.00111 | 0.9933 | 0.9933 | 0.9972 |
| `T1`, `m2` | 7,602 | 0.619 | 0 | 0.9378 | 0.0359 |
| `T1`, `RO` | 19,905 | 0.828 | 0 | 0.9221 | 0.1423 |
| `T1`, `sx` | 20,034 | 1.031 | 0 | 0.8286 | 0.9157 |
| `T1`, `init` | 5,864 | 2.485 | 0 | 0.5924 | 0.4429 |
| `T1`, `cz` | 20,037 | 3.523 | 0 | 0.3128 | 0.8412 |
| `T1`, `rzz` | 19,884 | 5.878 | 0 | 0.1279 | 0.8044 |
| `RO`, `p01` | 90,405 | 0 | 0.9687 | 0.9759 | 0.0718 |
| `RO`, `p10` | 90,378 | 0 | 0.9335 | 0.9466 | 0.1371 |
| `RO`, `init` | 21,971 | 0.335 | 0.2685 | 0.8642 | 0.7497 |
| `m2`, `sx` | 7,872 | 1.645 | 0 | 0.6803 | 0.9672 |
| `sx`, `cz` | 20,060 | 2.266 | 0 | 0.7024 | 0.9223 |

**Inference from the stamps, not a documented procedure:** a daily round on one qubit
measures `measure_2` and readout first, then `T1` and `T2` within seconds of each other (one
batch), then `sx` about an hour after `T1`, then `cz` and `rzz` hours later. Readout and
`init_error` are also re-measured between daily rounds (about every 4.5 h, `01-data-layer.md`
§3). This clock decides what any cross-family test can see: two quantities measured an hour
apart cannot share a fluctuation that lasts minutes.

The daily families' event clock is quietest at 16:00 UTC
(`daily_families_quietest_hour_utc`), so "operational days" in this document start at
16:00 UTC (`xcommon.DAY_START_HOUR`).

### 1.3 The owner boundary and how this document reads it

The eleven qubit-view fields form 55 pairs: 14 inside one family (the family owner's), 18
cross-family pairs excluded by the scope brief, and 23 analysed here (`xcommon.pair_owner`).
The brief names "readout" without listing fields; this document reads it as follows, stated
once so that no reader takes a gap for an oversight or a trespass:

| Excluded link | Owner | Pairs it covers here |
| --- | --- | --- |
| Readout against `T1` decay | `03-readout-measurement.md` | `T1` with `RO`, `p01`, `p10`, `m2` |
| `sx` against `T1`/`T2` and its coherence limit | `04-single-qubit-gates.md` | `sx` with `T1`, `T2` |
| `cz`/`rzz` against their qubits' `T1`, `T2`, `sx`, readout | `05-two-qubit-gates-couplings.md` | `cz`, `rzz` with `T1`, `T2`, `sx`, `RO`, `p01`, `p10` |
| `lf` against its chain's gate errors | `06-device-time-topology.md` | (`lf` not used) |

`init_error` is a preparation error, not a readout error, so `init` against `T1`, `cz` and
`rzz` is analysed here; `measure_2` against `cz` and `rzz` likewise. The 23 pairs: `T1`-`init`,
`T1`-`zz`; `T2` with `RO`, `p01`, `p10`, `init`, `m2`, `zz`; `sx` with `RO`, `p01`, `p10`,
`init`, `m2`, `zz`; `RO`, `p01`, `p10` with `zz`; `init` with `cz`, `rzz`, `zz`; `m2` with `cz`,
`rzz`, `zz`. Every Benjamini-Hochberg family in this document is these 23 pairs (or their 46
directions for lead and lag). Two pairs owned elsewhere are run through the same machinery as
**positive controls only**, to show the instruments detect dependence when it exists: `T1`-`T2`
(owner 02; measured seconds apart) and `RO`-`p10` (owner 03; arithmetically linked). Their
interpretation belongs to their owners. Multivariate summaries (§7.5 to §7.7) include every
field, as the brief allows.

## 2. Profiles

### 2.1 The per-qubit level of each field

The level of a field on a qubit is the median of its `log10` event values over the field's
lifetime (`levels.json`, `level_definition`); `adj_*` is the mean of the adjacent couplers'
levels. Units are `log10` of microseconds (`T1`, `T2`), of a probability (errors) and of GHz
(`|zz|`).

| Field | Qubits with a level | Events per qubit (median) | Min | 10% | Median | 90% | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `T1` | 156 | 130 | 0.982 | 1.991 | 2.110 | 2.211 | 2.410 |
| `T2` | 155 | 134 | 0.716 | 1.503 | 2.027 | 2.188 | 2.314 |
| `RO` | 156 | 580 | -2.322 | -2.251 | -2.044 | -1.384 | -0.457 |
| `p01` | 156 | 572 | -2.737 | -2.591 | -2.270 | -1.468 | -0.688 |
| `p10` | 156 | 574 | -2.158 | -2.075 | -1.896 | -1.343 | -0.319 |
| `init` | 116 | 234.5 | -3.102 | -3.007 | -2.754 | -2.398 | -2.255 |
| `m2` | 156 | 51 | -2.451 | -2.334 | -1.884 | -1.159 | -0.355 |
| `sx` | 155 | 132 | -3.814 | -3.683 | -3.523 | -3.248 | -2.275 |
| `adj_cz` | 155 | 131 | -2.716 | -2.666 | -2.555 | -2.189 | -1.396 |
| `adj_rzz` | 154 | 110 | -2.769 | -2.677 | -2.567 | -2.224 | -1.226 |
| `adj_zz` | 156 | 486 | -5.572 | -5.399 | -5.221 | -4.976 | -4.660 |

Tails are one-sided for every error field: the 90% to maximum span is several times the 10%
to median span, which is why every between-qubit statistic below is rank-based (Spearman,
normal scores, rank-scaled mutual information).

### 2.2 Missingness and exclusions inside the lifetimes

- `init` exists on 116 qubits only (`qubits_with_level.init`; the other 40 never carry it), so
  every pair with `init` has 116 qubits or fewer and the multivariate work runs twice, without
  `init` on 154 qubits (set A) and with it on 116 (set B).
- `q72` has no `T2`, a permanently placeholder `sx`, and both couplers permanently faulty, so it
  has no `T2`, `sx`, `adj_cz` or `adj_rzz` level (`qubits_missing`). `q99` has no `adj_rzz`:
  both of its `rzz` couplers (95-99, 99-115) are permanently faulty (`01-data-layer.md` §5).
  Set A therefore excludes `q72` and `q99` (`multivariate.A_10_fields_no_init.qubits_excluded`).
- Schema starts (`init` 2026-08-04, `m2` 2026-08-07) are not missingness; a sensitivity run
  computes every level over the common window from 2026-08-07 (`spearman_common_window`).

### 2.3 Cadence of the event tables

The residual tables of §4 and §7.2 hold every event (`comovement.json` `families`): 141 `T1`
rounds, 598 readout rounds, 52 `m2` rounds, 487 `zz` rounds (rounds split where pooled stamps
are more than 15 minutes apart, the rule of `scripts/feature_patterns.py`), of which 134, 589,
52 and 487 re-measured at least 20 entities and so define a device common mode.

## 3. Temporal structure

### 3.1 How much of each family's movement is device-wide

The common mode of a round is the median standardized residual over the entities re-measured
in it (§4.1 defines the residual). Its share of the residual variance
(`common_mode.json` `common_mode_share`, robust form `1 - (MAD(r_cm) / MAD(r))^2`):

| `T1` | `T2` | `RO` | `p01` | `p10` | `init` | `m2` | `sx` | `cz` | `rzz` | `zz` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.130 | 0.119 | 0.082 | 0.066 | 0.059 | 0.105 | 0.039 | 0.044 | 0.031 | 0.027 | 0.012 |

The plain-variance shares are smaller (0.074 for `T1`, 0.015 for `sx`, `share_plain`). So the
device-wide part is small everywhere and largest for the coherence pair; for `sx` it agrees in
size with P6's 1.6% (`docs/roadmap/2026-10-05-feature-patterns-and-method.md` §2, P6).

### 3.2 Do device-wide changes co-move across families? (g)

Per family and operational day, the device median of the entities' daily median `log10` value,
kept when at least half of the family's entities were re-measured that day; then its
day-to-day change (`device_daily`). 114 days carry a `T1` change, 132 a readout change, 116 an
`sx` change, 108 a `cz` change, 56 an `init` change and 46 an `m2` change.

Of the 55 family pairs, 8 survive Benjamini-Hochberg at 0.05 (null: 2,000 circular shifts of one
family's day series; `bh_family_size` 55). Seven are inside a family: `T1`-`T2` (Spearman 0.660,
block-bootstrap 95% interval 0.508 to 0.775), `RO`-`p01` (0.603), `RO`-`p10` (0.603),
`p01`-`p10` (0.344), `RO`-`init` (0.385), `p01`-`init` (0.417), `cz`-`rzz` (0.422). The one
cross-family survivor is `p01`-`sx`, **-0.341** (interval -0.539 to -0.104, 113 days, BH
q 0.0039): on days when the device's typical `p01` rises, its typical `sx` error tends to fall.
This is a device-level association between two families that are not physically linked in any
obvious way; read it as a candidate shared driver (for example a change in calibration
practice that moves both), not as a mechanism. Other large values do not survive, for example
`T1`-`m2` -0.389 (43 days, q 0.156) and `init`-`m2` 0.531 (45 days, q 0.224).

**Days on which several families jump together.** A family jumps on a day when its device
median changes by more than 2.5 robust sd of its own daily changes (`joint_jumps`). Three days
have at least three families jumping, against a null mean of 0.312 (2,000 independent shifts,
p 0.0035):

| Operational day (from 16:00 UTC) | Families and signed robust z | Reading |
| --- | --- | --- |
| 2026-05-14 | `T1` -5.64, `T2` -3.33, `sx` +3.32, `cz` +2.74, `rzz` +4.40 | coherence fell and every gate error rose on the same day, device-wide; cause not identifiable from these data |
| 2026-05-17 | `RO` -6.56, `p01` -5.45, `p10` -7.98 | readout improved device-wide; cause unknown |
| 2026-06-08 | `RO` -3.96, `p01` -5.11, `p10` -3.31 | the day that contains the readout-length change and the first `measure.threshold` at 2026-06-08T18:56:28Z (`01-data-layer.md` §5) |

The readout triple jumps together partly by arithmetic (`RO = (p01 + p10) / 2`); the 2026-05-14
day is the one genuinely multi-family device event in the record.

### 3.3 Coverage periods

Archive coverage changed when historical fetches began (`01-data-layer.md` §6), so the
event-level statistics are also reported before and after 2026-08-01 (§7.2 and §7.4). The
direction of every surviving co-movement and coincidence is the same in both periods; sizes
differ (for example `sx`-`p10` matched-event correlation {{SXP10_EARLY}} before and
{{SXP10_LATE}} after).

### 3.4 What this document does not measure in time

Time-of-day and day-of-week seasonality of the values, change points and drift are
per-field properties and sit in the owner documents (02 to 06). This document asks only
whether such movements are shared across families (§3.1, §3.2, §7.2).

## 4. The non-persistent component (variograms and what they can and cannot tell)

{{SECTION4}}

## 5. Spatial structure

Per-field spatial patterns belong to the owners. This scope uses spatial statistics for two
things: to judge whether the between-qubit tests of §7.1 can treat qubits as independent, and to
place the multivariate scores of §7.5 and §7.6 on the device.

**Moran's I of each level on the coupling graph** (`levels.json` `morans_i_levels`; 999
permutations; two-sided p):

| `T1` | `T2` | `RO` | `p01` | `p10` | `init` | `m2` | `sx` | `adj_cz` | `adj_rzz` | `adj_zz` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -0.015 (0.878) | 0.115 (0.096) | -0.195 (0.015) | -0.194 (0.011) | -0.186 (0.015) | -0.035 (0.861) | -0.432 (0.001) | -0.049 (0.543) | 0.474 (0.001) | 0.573 (0.001) | 0.428 (0.001) |

The `adj_*` fields are autocorrelated by construction (neighbouring qubits share couplers). The
readout fields and `m2` are **negatively** autocorrelated: coupled qubits tend to have dissimilar
readout quality. Every between-qubit pair of §7.1 joins at most one autocorrelated field (an
`adj_*` field with a field whose I is near zero or negative), which is the case in which a naive
permutation test of correlation remains approximately valid; when both fields are positively
autocorrelated the effective sample size shrinks (Clifford, Richardson and Hemon 1989).

**The multivariate scores on the device** (set A, `pc_spatial`):

| Score | Moran's I (two-sided p) | Spearman with coordinate 1 | with coordinate 2 | with distance from centre | with qubit degree |
| --- | --- | --- | --- | --- | --- |
| PC1 (readout factor) | -0.143 (0.057) | -0.013 | -0.110 | -0.011 | **0.420** |
| PC2 (coherence and gate factor) | 0.241 (0.002) | 0.065 | -0.139 | -0.264 | -0.194 |
| PC3 | 0.184 (0.018) | 0.124 | -0.088 | 0.021 | 0.096 |

The readout factor's score rises with the number of couplers a qubit has (Spearman 0.420 with
degree, 154 qubits). On the heavy-hex lattice most couplers join a degree-3 qubit to a degree-2
qubit, so a readout level that depends on degree would make neighbours dissimilar, which is the
negative Moran's I above. **Interpretation, untested here:** readout quality is tied to a
qubit's role in the lattice (its frequency group or readout-resonator assignment). It is
falsified if, within each degree class, readout levels show no negative autocorrelation and no
degree difference; the per-field check belongs to `03-readout-measurement.md`. The coherence and
gate factor is positively autocorrelated, partly by construction (`adj_cz` and `adj_rzz` load on
it), and is higher (worse) towards the centre of the device (-0.264 with distance from centre).
The configuration coordinates (`dd.meta['config_values']['coords']`, one value for all 1,317
files that carry a configuration) are used as given; which axis is "row" is not documented in
the data.

**Archetype labels on the device** (§7.6): coupled qubits share a Ward label no more often than
under label permutation for any k from 2 to 6 (for k = 3, 0.355 of coupler edges join two
qubits with the same label against a null mean of 0.393, p 0.883; `neighbour_same_label_*`).

## 6. Faults and data quality

- **Permanently faulty entities** are excluded by the placeholder mask and listed in §2.2
  (`q72`, `q99` for `rzz`). No placeholder value enters any statistic.
- **`zz` signs and zeros** (§1.1): the analysis uses `|zz|`; whether a negative `zz` is a
  physical sign or a fit artefact is not established by any fetched source.
- **Readout stamps.** `RO`, `p01` and `p10` carry the identical stamp in only part of the records
  (`01-data-layer.md` §5, 68.5% of readout records), so the shot-noise variance of an `RO` event
  (§4.4) uses the `p01`, `p10` values of the same file, which may come from a different moment.
- **Assembly-stamped `zz`.** Its event time is a file time; every `zz` result is read at day
  resolution only.
- **A trap found and removed in the lead-and-lag test.** Against the bare EWMA level, every
  predictor of `RO` and `p10` "improved" the forecast by the same amount and every predictor of
  `p01` "worsened" it by the same amount, whatever family the predictor was. The gain came from
  the fitted intercept (a bias correction of the EWMA level in the test period), not from the
  predictor; the test now scores every model against an intercept-only reference
  (`leadlag.json` `intercept_only_vs_level`, §7.3).
- **Not scorable.** `m2` predicting `zz`: `zz`'s 70% cut (2026-08-06T10:07Z, `cuts_utc`) falls
  before `m2`'s schema start, so there is no training data; `m2` predicting `rzz` with three
  lags has too few training events. Both are reported as `None`, which is why the BH families
  hold 45 and 44 directions, not 46.
- **Sampling, truncation and caps, all logged in the JSON.** Gap bins of the dense pairs
  (readout, `zz`) are capped at a seeded random subsample of 30,000 pairs per bin
  (`comovement.json` `method.gap_bin_cap_pairs`; each bin records `pairs` and `pairs_used`).
  Lists of qubit ids in `levels.json` are truncated to 40 or 60 entries. Null and bootstrap
  replicate counts are recorded in each file. The coincidence period split has no `init` or
  `m2` data before 2026-08-01 (reported as 0 events).
- **Runtime.** `comovement.py` runs for longer than five minutes on the laptop
  (`results/cross/comovement.json` is the slowest file to rebuild); the others take under
  five.

## 7. Relationships

{{SECTION7}}

## 8. Use cases and why each finding matters

- **Per-family forecasters are justified, a shared latent driver is not.** The between-qubit
  factors (§7.5), the absence of out-of-time lead and lag (§7.3) and the family-block structure
  of the change matrix (§7.5) all say that one family's recent movement carries no usable
  information about another family's next value beyond its own level. This extends P3 (linear,
  one step; `docs/roadmap/2026-10-05-feature-patterns-and-method.md` §2) to nonlinear forms,
  three lags and seven more families, and supports building each family's reference
  forecaster separately, as that document proposes.
- **Joint bands need joint tails.** Large deviations of different families co-occur on one
  qubit more often than chance (§7.4) even though the average correlation is tiny (§7.2). A
  band that treats families as independent will under-cover days on which several quantities
  of one qubit go bad together. This matters for any use that combines families into one
  channel (ADR-027's target uses `T1` and `T2`; a circuit-level noise model uses all of them).
- **Two independent axes of qubit quality.** Readout quality and coherence-with-gate quality
  are nearly orthogonal across qubits (§7.5). A synthetic device or a qubit-selection rule
  that ranks qubits on one axis says almost nothing about the other. This is the
  between-entity counterpart of P4's finding that the two targets of decision A9 carry
  largely independent signal; the decision itself stays open.
- **The common-mode share bounds device-level forecasting.** At most about a tenth of a
  family's residual variance is device-wide (§3.1), so a stage-A device-mean model sees a
  small, slowly drifting signal, in line with P8.
- **Literature use.** The nearest published work on qubit calibration data clusters qubits by
  their metrics (Deng et al. 2025, existing survey `2026-10-04` §8, §2.1); the result here,
  that clusters do not beat a correlated-Gaussian continuum on `ibm_fez` (§7.6), is the kind of
  null such a clustering needs to report. Correlated multi-qubit error bursts from radiation are
  documented on other devices (McEwen et al. 2022; Wilen et al. 2021; Thorbeck et al. 2023 in
  the existing survey `2026-10-05` §2.3), but they last milliseconds and affect a whole chip,
  which a daily calibration cannot resolve; the qubit-local coincidence of §7.4 is a different,
  slower phenomenon.

## 9. Open questions, and what measurement would settle each

| Question | What would settle it |
| --- | --- |
| Is the shared, hour-scale part of the non-persistent component (§4.2) a physical fluctuation of the qubit, or a shared artefact of one calibration round (for example a stale frequency or readout calibration used by several experiments)? | Back-to-back repeats of two experiments on one qubit at controlled separations (minutes to hours), with and without recalibrating readout in between; a physical fluctuation decays with separation whatever the calibration, an artefact follows the calibration events. Needs hardware time, not archive data. |
| Why do device-median `p01` and `sx` changes move in opposite directions (§3.2)? | Align the days of largest joint movement with documented calibration or configuration changes (`06-device-time-topology.md`'s change points) and re-test with those days removed. |
| Does readout quality depend on a qubit's degree or frequency group (§5)? | `03-readout-measurement.md`: compare readout levels by degree class and test autocorrelation within each class. |
| Is the coherence-and-gate factor (§7.5) more than `T1`/`T2` driving gate errors? | `04` and `05` own the pairwise links; a partial-correlation run of `sx`, `adj_cz`, `adj_rzz` given `T1`, `T2` across qubits, done there, would split it. |
| Do the qubit-local coincidences (§7.4) mark TLS events? | The hourly monitoring's TLS signatures are not published in the properties document (§1.2); with them, or with own spectroscopy, coincidence days could be labelled. Without them: test whether coincidence days are followed by a lasting level shift (a TLS moving away) or a return (a transient). |
| Are the archetype nulls (§7.6) sensitive to the field set? | Repeat with set B (with `init`) and with `lf`-derived per-qubit summaries once `06` defines one. |

## 10. Reproduce, and results files

From the repository root, with the cache built (`01-data-layer.md` §1). Each script writes one
JSON in `docs/findings/2026-10-06-feature-deep-dive/results/cross/` that starts with
`ddload.result_header`.

```bash
PY=C:/t/venv/Scripts/python.exe
D=docs/findings/2026-10-06-feature-deep-dive/analysis/cross
$PY $D/alignment.py     # results/cross/alignment.json    (clock, families, gaps; seconds)
$PY $D/levels.py        # results/cross/levels.json       (between-qubit, PCA, archetypes, spatial; ~1.5 min)
$PY $D/comovement.py    # results/cross/comovement.json   (matched events, gap bins, shot noise; ~6 to 8 min)
$PY $D/common_mode.py   # results/cross/common_mode.json  (device-wide, variograms, change matrix; ~3.5 to 5 min)
$PY $D/leadlag.py       # results/cross/leadlag.json      (out-of-time lead and lag; ~1 min)
$PY $D/coincidence.py   # results/cross/coincidence.json  (large-deviation coincidence; ~4 to 5 min)
```

Helpers: `xcommon.py` (families, transforms, owner map, BH) and `xresid.py` (residuals, rounds,
common mode, matching, circular-shift nulls, cluster bootstrap). Seeds are fixed
(`xcommon.SEED` plus an offset per script). Lint: `C:/t/ruffpin/Scripts/ruff.exe check` and
`format` on `analysis/cross/` pass.

## 11. Sources

New sources: 11 fetched on 2026-10-06 (title confirmed on the arXiv abstract page, the Crossref
record, or the vendor page). The others are cited from the two existing surveys by their
identifier and section.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum documentation, "Monitoring, calibrations, and benchmarking" | https://quantum.cloud.ibm.com/docs/en/guides/calibration-jobs | fetched 2026-10-06 | What is benchmarked daily, hourly monitoring incl. readout and TLS signatures, batching (§1.2) |
| Wilen et al., Correlated charge noise and relaxation errors in superconducting qubits (Nature 2021) | arXiv:2012.06029 | fetched 2026-10-06 | Particle impacts cause spatially correlated charge jumps with transient `T1` suppression (§8) |
| McEwen et al., Resolving catastrophic error bursts from cosmic rays in large arrays of superconducting qubits (Nature Physics 2022) | arXiv:2104.05219 | fetched 2026-10-06 | Chip-wide bursts limit all qubits at once (§8) |
| Kraskov, Stoegbauer, Grassberger, Estimating mutual information (PRE 2004) | arXiv:cond-mat/0305641 | fetched 2026-10-06 | KSG k-nearest-neighbour MI estimator (§7.1) |
| Benjamini and Hochberg, Controlling the false discovery rate (JRSS B 1995) | doi:10.1111/j.2517-6161.1995.tb02031.x | fetched 2026-10-06 (Crossref) | Multiple-testing control throughout |
| Horn, A rationale and test for the number of factors in factor analysis (Psychometrika 1965) | doi:10.1007/BF02289447 | fetched 2026-10-06 (Crossref) | Parallel analysis for the PCA (§7.5) |
| Hubert and Arabie, Comparing partitions (J. Classification 1985) | doi:10.1007/BF01908075 | fetched 2026-10-06 (Crossref) | Adjusted Rand index (§7.6) |
| Rousseeuw, Silhouettes (J. Comput. Appl. Math. 1987) | doi:10.1016/0377-0427(87)90125-7 | fetched 2026-10-06 (Crossref) | Silhouette (§7.6) |
| Ward, Hierarchical grouping to optimize an objective function (JASA 1963) | doi:10.1080/01621459.1963.10500845 | fetched 2026-10-06 (Crossref) | Ward clustering (§7.6) |
| Moran, Notes on continuous stochastic phenomena (Biometrika 1950) | doi:10.1093/biomet/37.1-2.17 | fetched 2026-10-06 (Crossref) | Moran's I (§5) |
| Clifford, Richardson, Hemon, Assessing the significance of the correlation between two spatial processes (Biometrics 1989) | doi:10.2307/2532039 | fetched 2026-10-06 (Crossref) | Effective sample size under spatial autocorrelation (§5) |
| Deng et al., Qubit Health Analytics and Clustering (2025) | arXiv:2508.21231 | existing survey `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` §2.1, §8 | Nearest precedent for archetypes (§8) |
| Thorbeck et al., TLS dynamics due to background ionizing radiation (2023) | arXiv:2210.04780 | existing survey `docs/roadmap/2026-10-05-gate-error-literature-survey.md` §2.3 | Hour-scale TLS dynamics; TLS scrambling (§4.5, §8) |
| Schlör et al., Correlating decoherence in transmon qubits (PRL 2019) | arXiv:1901.05352 | existing survey `2026-10-04` §3, §8 | One fluctuator moves `T1` and `T2` together (control pair, §4.2) |
| Klimov et al., Fluctuations of energy-relaxation times (PRL 2018) | arXiv:1809.01043 | existing survey `2026-10-04` §3, §8 | TLS-driven `T1` fluctuations (§4.5) |
| Etxezarreta Martinez et al., Multi-qubit time-varying quantum channels (2023) | arXiv:2207.06838 | existing survey `2026-10-04` §3, §8 | Fluctuations local to each qubit on IBM devices (§4.5) |
| Berritta et al., Real-time adaptive tracking of fluctuating relaxation rates (2026) | arXiv:2506.09576 | existing survey `2026-10-04` §3, §8 | Millisecond `T1` switching (§4.5) |
| Hirasaki et al., Detection of temporal fluctuation in superconducting qubits (2023) | arXiv:2307.04337 | existing survey `2026-10-05` §2.1 | Step changes lasting minutes (§4.5) |
| Wallman and Flammia, Randomized benchmarking with confidence (2014) | arXiv:1404.6025 | existing survey `2026-10-05` §2.1 | IBM's production RB settings unpublished; estimation floor must be measured (§4.5) |

Project sources: `01-data-layer.md` (field semantics, identities, faults, device-wide changes);
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P1 to P8, quoted where named);
`scripts/feature_patterns.py` (the measured event rule and the round rule).
