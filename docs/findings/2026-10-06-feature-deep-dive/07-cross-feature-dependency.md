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

Basis of every bullet: the ref and files of the header, all events of the eleven families of
§1.1; sample sizes in brackets. Each bullet points to the section that carries its sources.

- **The clock limits what can be shared.** On one qubit `T1` and `T2` are stamped seconds apart
  (median 0.00111 h over 19,880 `T1` events), `sx` about an hour after `T1` (median 1.03 h),
  `cz` and `rzz` hours later (3.52 h and 5.88 h), and readout is re-measured about every 4.5 h;
  a fluctuation shorter than these gaps cannot be seen as shared (`alignment.json`; §1.2).
- **No between-qubit link among this scope's 23 pairs.** 0 of 23 level correlations survive
  Benjamini-Hochberg, on Spearman and on KSG mutual information (smallest q 0.514); every 95%
  interval lies inside -0.323 to 0.291 (116 to 156 qubits; §7.1). The between-qubit structure is
  in the owners' pairs (for example `T1`-`sx` -0.430, owner 04).
- **Two nearly separate axes of qubit quality.** Across 154 qubits and 10 fields, a readout
  factor (eigenvalue 3.83, 38% of the variance) and a coherence-and-gate factor (2.58, 26%) both
  exceed parallel analysis; every readout field loads on the first with a bootstrap interval
  above 0.39 and on the second with an interval that includes 0 (§7.5).
- **No archetypes.** Ward clusters for k = 2 to 6 never beat a Gaussian null with the observed
  correlations (p 0.154 to 0.965) and are unstable (median bootstrap ARI 0.37 to 0.42); the 20
  qubits that are poor on almost everything are the tail of a continuum (154 qubits; §7.6).
- **Within-qubit co-movement is detectable and tiny.** 11 of 23 pairs survive on raw residuals
  and 10 with the round common mode removed, but the largest correlation is 0.057 (`sx`-`p10`,
  15,993 matched events), against 0.693 (`T1`-`T2`) and 0.781 (`RO`-`p10`) for the controls
  (§7.2).
- **Shared only when measured close in time.** The `sx`-`p10` residual correlation is 0.108
  within half an hour (1,530 pairs), 0.069 at 0.5 to 2 h, 0.028 at 2 to 6 h and
  indistinguishable from zero beyond 6 h; `sx`-`RO`, `m2`-`T2`, `T1`-`init`, `T2`-`init` and the
  `T2`-readout pairs show the same shape. Independent errors of separate experiments cannot do
  this; a real fluctuation of the qubit and a shared calibration input both can (§4.2).
  **[Verification 2026-10-06: the numbers reproduce, but "shared on hour scales" is weakened.
  With the level window shortened from +-7 days to +-2 days, the `sx`-`p10` correlation at 0 to
  0.5 h falls from 0.108 to 0.032 and the peak moves to 0.5 to 2 h (0.058); the "same shape"
  holds for `T1`-`init` and `T2`-`init` only at the shortest bin (p 0.03 for `T1`-`init`,
  uncorrected), and raw `T2`-`RO` has no decay shape (0.018, -0.039, then +0.020 at 6 to 30 h).
  The short-gap correlation is therefore partly a component that varies on a scale between 2
  and 7 days, which a shared level step or a slow shared calibration state would also produce.
  See Verification section, claims 1 and 2.]**
- **The device-wide part is small.** The round common mode takes 0.012 (`zz`) to 0.130 (`T1`)
  of the residual variance, and the device series at the shortest lag is 0.54 to 3.25 times
  what independent entities would give; for readout and coherence the device share grows at
  month lags, a drifting level (11 families, 14 to 111 device pairs; §3.1, §4.3).
- **Readout shot noise does not explain the small correlations.** Binomial shot noise is a
  median 0.20 (`RO`), 0.15 (`p01`) and 0.34 (`p10`) of the residual variance, which caps any
  correlation at 0.89, 0.92 and 0.82, far above what is observed (156 qubits; §4.4).
- **No lead or lag.** In three models, 0 of 45 (or 44) directions survive; the best
  out-of-time ratio of mean absolute errors is 0.99854 (`init` to `T2`), a 0.15% gain, and 19 of
  45 intervals lie entirely above 1, a sign of overfitting, not of signal (§7.3).
- **Large deviations hit one qubit together.** On the same operational day, 11 of 23 pairs
  survive both a time-shift and a qubit-permutation null (coherence with readout, `sx` with
  readout, `zz` with `T1`, `T2`, `sx` and readout), with qubit-null lifts of 1.22 to 1.63; three
  or more of seven physical groups are flagged on 309 qubit-days against 186.4 expected (lift
  1.66; adverse deviations 2.38) (22,612 qubit-days; §7.4).
- **Device-day changes move by family.** Of 55 family pairs of device-median daily changes, 8
  survive and 7 of them are inside a family; the one cross-family survivor is `p01`-`sx`
  (-0.341, 113 days), and 2026-05-14 is the only day on which coherence and every gate family
  jumped together (148 operational days; §3.2, §7.7).
- **Day-level factors are family blocks.** Four eigenvalues of the qubit-day residual matrix
  exceed a shifted null, each a family block (readout, coherence, two-qubit with `sx`) or a
  contrast inside readout; across blocks no pair exceeds 0.061 in absolute value (qubit-days of
  11 fields; §7.5).
- **A candidate: `|zz|` against readout.** `zz` residuals correlate negatively with readout
  errors (-0.043 with `RO`, 166,855 matched events), and the sign recurs at qubit-day level
  (-0.061) and, not surviving, at device-day level (-0.251); `zz` carries a file time and no
  fetched source documents its production, so mechanism and timing are open (§7.2).
- **On the root question.** Part of the non-persistent component is shared between separate
  experiments on one qubit within hours, so the component is not all independent estimation
  noise; the shared part is small, and the rest is not attributed by any cross-family test
  (§4.5). **[Verification 2026-10-06: "within hours" is overstated; the correlation depends on
  the level window (0.108 to 0.032 at 0 to 0.5 h when +-7 d becomes +-2 d for `sx`-`p10`), so the
  shared part may vary over days. "Not all independent estimation noise" survives only as: some
  co-movement exists between families; its timescale and origin are open.]**

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
| `init` | 116 | 241 | -3.102 | -3.007 | -2.754 | -2.398 | -2.255 |
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
event-level statistics are also reported before and after 2026-08-01 (§7.2 and §7.4). Among
the surviving pairs that have data in both periods, the direction of every co-movement (8 of 8,
`summary.json` `comovement.raw.survivors_same_sign_both_periods`) and every same-day
coincidence (11 of 11 qubit-null survivors with a time-null lift above 1 in both periods,
`coincidence.big_lag0.of_which_lift_time_above_1_in_both_periods`) is the same in both
periods; `init` and `m2` exist only after 2026-08-01, so the check does not reach their pairs.
Sizes differ (for example the `sx`-`p10` matched-event correlation is 0.071 before, from 9,617
pairs, and 0.038 after, from 6,369; `comovement.json` `pairs[sx-p10].raw.r_before_2026_08_01`,
`r_from_2026_08_01`).

### 3.4 What this document does not measure in time

Time-of-day and day-of-week seasonality of the values, change points and drift are
per-field properties and sit in the owner documents (02 to 06). This document asks only
whether such movements are shared across families (§3.1, §3.2, §7.2).

## 4. The non-persistent component (variograms and what they can and cannot tell)

The family variograms are the owners' (`02-coherence.md` §4.1, `03-readout-measurement.md`
§4.3, `04-single-qubit-gates.md` §4, `05-two-qubit-gates-couplings.md` §4.1 and §4.3,
`06-device-time-topology.md` §4 for `lf`) and are not repeated here. Every family carries a
large component that does not persist from one event to the next (the lag-1 autocorrelation
of changes sits between -0.42 and -0.50 in every family at the older ref,
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` §2, P2). This section asks what the
cross-family view adds: is any of that component shared between different experiments on the
same qubit, or across the device, and how large is the shared part?

### 4.1 The residual every cross-family test uses

The residual of an event is its `log10` value minus the median of the same entity's other
events within plus or minus 7 days (a centred, leave-one-out local level), divided by the
entity's robust scale (1.4826 times the median absolute deviation of its residuals;
`comovement.json` `method.residual`, `analysis/cross/xresid.py`). It isolates the
non-persistent part without a forecasting model; it is descriptive (the lead-and-lag test of
§7.3 uses a causal level instead). Residuals of a family are pooled into normal scores, so one
heavy tail cannot dominate a correlation. The round common mode is the median residual of the
entities re-measured in the same round (stamps split at gaps above 15 minutes, at least 20
entities); `r_cm` is the residual minus it. Residuals exist for 20,043 of 20,063 `T1` events,
all 90,408 `RO` events, 20,044 of 20,207 `sx` events and 83,440 of 83,443 `zz` events
(`comovement.json` `families.*.events_with_residual`); the few missing ones have fewer than
three other events in their window.

One artefact of the leave-one-out level is visible in the controls: the `T1`-`T2` residual
correlation, 0.693 for stamps seconds apart, turns slightly negative for pairs a day apart
(-0.044 raw, -0.066 with the common mode removed; `comovement.json` `pairs[T1-T2].by_gap`),
because the level window of a `T2` event contains the previous day's `T2`, which moved with
the previous day's `T1`. (That `T1` and `T2` move together at all is expected: one fluctuator
can change both, Schlör et al. 2019, existing survey `2026-10-04` §3; the pair is a control
here, and its interpretation belongs to `02-coherence.md` §4.2.) The artefact scales with the same-time correlation, so it is much
smaller for the pairs of this scope, whose correlations at the shortest gap are at most 0.124
in absolute value on raw residuals and 0.130 with the common mode removed (§4.2; `summary.json`
`comovement.shortest_bin_max_abs_r_excluding_zz_raw` and `..._cm_removed`).

### 4.2 Shared between families on one qubit, and only when measured close in time

For each pair, every event of family A is matched with every event of family B on the same
qubit within 30 h, and the residual correlation is computed per bin of the time between the
two measurements, against 200 circular shifts of B within each entity (`comovement.json`
`pairs[*].by_gap`; bins with more than 30,000 pairs use a seeded subsample of 30,000, logged
as `pairs_used`). Independent estimation errors of two separate experiments give zero at
every gap. A component shared by both experiments that lasts a time tau gives a correlation
that is largest at gaps much shorter than tau and falls towards zero beyond it.

Rows: the six pairs of this scope whose shortest populated gap bin has an uncorrected shift p
below 0.05 on raw residuals (`summary.json`
`comovement.shortest_bin_p_below_0_05_uncorrected_excluding_zz_raw`), the two `T2`-readout pairs
that reach it only with the common mode removed (`..._cm_removed`), and the two controls. The
other seven non-`zz` pairs of this scope show no signal in their shortest bin
(`comovement.shortest_populated_gap_bin`). Raw residuals unless marked, Pearson correlation of
normal scores, pairs in brackets, p from the 200-shift null; the p-values are per bin and
uncorrected (23 pairs, five bins, two residual forms), and the null's floor is 0.005:

| Pair (owner) | 0 to 0.5 h | 0.5 to 2 h | 2 to 6 h | 6 to 18 h | 18 to 30 h |
| --- | --- | --- | --- | --- | --- |
| `sx`-`p10` (07) | 0.108 (1,530; p 0.005) | 0.069 (12,154; p 0.005) | 0.028 (28,909; p 0.005) | 0.008 (30,000 of 78,035; p 0.23) | 0.008 (30,000 of 80,621; p 0.21) |
| `sx`-`RO` (07) | 0.072 (1,644; p 0.010) | 0.042 (12,287; p 0.005) | 0.014 (30,000 of 30,417; p 0.030) | 0.004 (p 0.69) | 0.007 (p 0.24) |
| `m2`-`T2` (07) | -0.081 (1,348; p 0.005) | -0.043 (5,709; p 0.005) | 0.042 (599; p 0.25) | 0.042 (754; p 0.22) | -0.003 (13,200; p 0.63) |
| `T2`-`init` (07) | -0.116 (496; p 0.005) | -0.044 (1,677; p 0.065) | -0.008 (8,211; p 0.51) | -0.021 (25,502; p 0.010) | 0.008 (19,263; p 0.40) |
| `T1`-`init` (07) | -0.124 (485; p 0.030) | -0.043 (1,618; p 0.10) | 0.000 (7,974; p 0.95) | -0.011 (24,791; p 0.14) | 0.006 (18,724; p 0.58) |
| `T2`-`p01` (07) | 0.050 (5,006; p 0.005) | -0.032 (16,147; p 0.005) | 0.009 (23,843; p 0.29) | 0.015 (30,000 of 82,160; p 0.025) | 0.019 (30,000 of 86,187; p 0.005) |
| `T2`-`p01` (07), common mode removed | 0.002 (5,006; p 0.95) | -0.029 (16,147; p 0.005) | -0.009 (p 0.080) | -0.002 (p 0.79) | 0.009 (p 0.12) |
| `T2`-`p10` (07), common mode removed | -0.065 (4,961; p 0.005) | -0.027 (16,136; p 0.005) | -0.003 (22,817; p 0.45) | 0.001 (p 0.81) | 0.006 (p 0.34) |
| `T2`-`RO` (07), common mode removed | -0.041 (5,561; p 0.005) | -0.036 (15,931; p 0.005) | -0.009 (24,210; p 0.15) | 0.012 (p 0.085) | 0.004 (p 0.45) |
| `T1`-`T2` (02, control) | 0.693 (19,899) | no pairs | -0.043 (299; p 0.55) | 0.205 (2,397; p 0.005) | -0.044 (30,000 of 32,962; p 0.005) |
| `RO`-`p10` (03, control) | 0.780 (30,000 of 84,972) | 0.150 (11,731) | 0.104 | 0.074 | 0.024 (p 0.010) |

`T2` with `RO` and `p10` is shown with the common mode removed because its raw shortest bin is
not distinguishable from zero (0.018, p 0.18, and -0.014, p 0.33), while its 0.5 to 2 h bin is
(-0.039 and -0.028); the raw `T1`-`T2` 6 to 18 h value (0.205) disappears when the common mode is
removed (-0.023, p 0.21), so it is a device-wide movement, not a qubit-local one.

What this shows, and what it does not:

- **Some of the non-persistent component is shared between different experiments on one
  qubit.** Independent estimation errors of separate experiments cannot correlate, and they
  cannot produce a correlation that depends on the time between the two measurements. Seven of
  the eight pairs of this scope in the table show the same shape (the `T2`-readout pairs with
  the common mode removed): largest within half an hour, smaller at 0.5 to 2 h,
  indistinguishable from zero by 6 to 18 h. The exception is `T2`-`p01`: raw, it is positive
  within half an hour and negative at 0.5 to 2 h; with the common mode removed its shortest bin
  is zero and its 0.5 to 2 h bin negative (-0.029), so its raw short-gap value is a device-wide
  movement and the pair does not show the decay shape. **[Verification 2026-10-06: "seven of
  the eight" is overstated. The three `T2`-readout rows are shown only after the common mode
  was removed because the raw rows did not fit (a choice made after seeing the result); raw
  `T2`-`RO` is 0.018, -0.039, 0.006, 0.020, 0.020 across the five bins, and `T1`-`init` and
  `T2`-`init` rest on 485 and 496 pairs at the shortest gap, `T2`-`init` still at -0.021
  (p 0.010) at 6 to 18 h. The window test above also shows the shape depends on the level
  window.]** The signs are those of a qubit that is
  worse on
  both quantities at once (`sx` and the readout errors up together; `T1` or `T2` down while
  `init` or `m2` is up). This agrees with the owners' own cross-experiment tests:
  `04-single-qubit-gates.md` §4 (`sx` against same-round `T1`, strongest within an hour) and
  `05-two-qubit-gates-couplings.md` §4.4 (`cz` against `rzz` on one coupler, 0.205 within an
  hour, lower beyond 2 h).
- **The shared part is small.** At the shortest gap the largest absolute correlation of this
  scope's non-`zz` pairs is 0.124 (`T1`-`init`, 485 pairs; 0.130 with the common mode removed),
  against 0.693 for `T1`-`T2`, whose experiments run seconds apart. Most of each family's
  non-persistent component is therefore not shared with any other family in the data, at any
  gap the archive offers.
- **What the decay does not settle.** A real fluctuation of the qubit (for example a defect
  near the qubit frequency that degrades relaxation, gates and readout together, and moves on
  within hours) and a shared input of one calibration round (for example a frequency or
  readout calibration that drifts and is refreshed) both predict a correlation that fades with
  the time between two experiments. The archive carries no marker that separates the two
  (§9). The decay is also not a controlled measurement: different gap bins hold different
  events (a readout event within half an hour of an `sx` event is not a random readout event),
  and the bins mix the two coverage periods.
- **The `zz` pairs are excluded from this reading.** `zz` carries a file time, not a
  measurement time (§1.1), so its gap bins are not gaps between measurements. Its nearest-event
  correlations with readout are detectable (§7.2) but cannot be placed in time.

### 4.3 Shared across the device

Two cross-family measures bound the device-wide part of the component.

**The round common mode** takes a robust share of the residual variance between 0.012 (`zz`)
and 0.130 (`T1`) (§3.1 table; `common_mode.json` `common_mode_share`).

**Device against entity variograms at the same lag** (`common_mode.json`
`variograms.*.matched_bins`; ratios over the independent prediction in `summary.json`
`common_mode.variogram_vs_independence`). The device series of a family is, per round with at
least half of its entities, the median over entities of the value minus the entity's long-run
median. If entity components were independent and Gaussian, the device series' semivariance
would be about `(pi / 2) / N` of the per-entity one (N entities per round); a component shared
by all entities would not shrink.

| Family | Shortest bin (h) | Device pairs | Device / entity | `(pi/2)/N` | Ratio over prediction | Device / entity at 744 to 1,488 h |
| --- | --- | --- | --- | --- | --- | --- |
| `T1` | 18 to 30 | 111 | 0.0340 | 0.0105 | 3.25 | 0.121 |
| `T2` | 18 to 30 | 111 | 0.0199 | 0.0102 | 1.96 | 0.054 |
| `RO` | 0.5 to 2 | 40 | 0.0106 | 0.0102 | 1.04 | 0.158 |
| `p01` | 0.5 to 2 | 40 | 0.0094 | 0.0104 | 0.91 | 0.144 |
| `p10` | 0.5 to 2 | 40 | 0.0147 | 0.0109 | 1.35 | 0.107 |
| `init` | 0.5 to 2 | 42 | 0.0277 | 0.0162 | 1.71 | 0.030 |
| `m2` | 18 to 30 | 44 | 0.0058 | 0.0103 | 0.56 | 0.006 |
| `sx` | 18 to 30 | 106 | 0.0209 | 0.0103 | 2.03 | 0.027 |
| `cz` | 18 to 30 | 100 | 0.0129 | 0.0093 | 1.39 | 0.020 |
| `rzz` | 18 to 30 | 78 | 0.0177 | 0.0095 | 1.86 | 0.022 |
| `zz` | 0.5 to 2 | 14 | 0.0049 | 0.0091 | 0.54 | 0.007 |

Reading: at the shortest lag the device series of `RO`, `p01`, `m2` and `zz` shrinks as much
as independent entities would make it (ratio over prediction 0.54 to 1.04; heavy-tailed entity
components make the median more efficient than the Gaussian `pi / 2` assumes, which lowers the
true prediction), so no device-wide nugget is detectable for them. `p10` and `cz` sit 1.35 and
1.39 times above the prediction, and `init`, `rzz`, `T2`, `sx` and `T1` 1.71 to 3.25 times: a
device-wide part exists at the shortest lag for these, but it is at most the device-to-entity
ratio itself, 0.034 of the per-entity semivariance for `T1` (the largest). For readout and
coherence the device share is larger at month lags (0.107 to 0.158 for the readout fields,
0.121 for `T1`, 0.054 for `T2`) than at the shortest lag, so their device-wide part is mainly a
slowly moving device level, in line with P8
(`docs/roadmap/2026-10-05-feature-patterns-and-method.md` §2); for `sx`, `cz`, `rzz`, `init`,
`m2` and `zz` it stays small at every lag (0.006 to 0.030 at month lags). The device pair counts
are small (14 to 111), and the `pi / 2` factor is a Gaussian approximation, so the ratios are
indicative, not tests. Whether device-wide movements are shared between families is §3.2 and §7.7.

### 4.4 Readout shot noise and the ceiling it puts on any correlation

Readout is the one family whose estimation noise is partly computable: each value is a count
out of 4,096 shots (`01-data-layer.md` §5). The binomial variance of each event's `log10`
value (delta method; for `RO` from the `p01` and `p10` of the same file, which may have been
stamped at a different moment, §6) is set against the entity's robust residual variance
(`comovement.json` `readout_shot_noise`, 156 qubits each):

| Family | Shot share of residual variance, quantiles 10%, 25%, 50%, 75%, 90% | Correlation ceiling at the median share |
| --- | --- | --- |
| `RO` | 0.101, 0.146, 0.202, 0.254, 0.298 | 0.893 |
| `p01` | 0.068, 0.104, 0.146, 0.190, 0.227 | 0.924 |
| `p10` | 0.185, 0.271, 0.335, 0.399, 0.472 | 0.815 |

Shot noise is a fifth (`RO`), a seventh (`p01`) and a third (`p10`) of the readout residual
variance at the median qubit, the same order as `03-readout-measurement.md` §4.7 finds with its
own definition. Since shot noise of a readout value cannot correlate with anything measured in
another experiment, a correlation of readout with another family can be at most the ceiling
times the correlation of the non-shot part; the ceilings (0.82 to 0.92) are far above the
observed correlations (§4.2, §7.2), so the smallness of the cross-family co-movement is not a
shot-noise artefact. The rest of the readout residual (about four fifths for `RO`) is not
attributed by this test.

### 4.5 What the cross-family view can and cannot tell about the root question

The open question is whether the non-persistent component is IBM's estimation noise or real
fast fluctuations aliased by the sampling. The cross-family evidence, taken together:

- **Against "all estimation noise":** an hour-scale component shared by separate experiments on
  one qubit (§4.2), and large deviations of different families on the same qubit-day more often
  than chance, beyond device-wide bad days (§7.4). Neither can come from independent fit errors.
  **[Verification 2026-10-06: weakened. Independent fit errors cannot produce either, but a
  shared multi-day level step or shared calibration state can (see the +-2 d window test in
  §4.2), and the coincidence lift is threshold dependent (`sx`-`p10`: 1.54 at 3 sd, 1.07 at 2 sd
  in an independent re-computation), so "beyond device-wide bad days" holds only for the
  extreme tail.]**
- **Against "mostly shared physics":** the shared part is a small fraction of each family's
  component (at most 0.130 in absolute value at the shortest gaps, below 0.06 for nearest pairs,
  §7.2), and the device-wide part is at most 0.130 of the residual variance (§3.1) and at most
  0.034 of the per-entity semivariance at the shortest lag (§4.3).
- **Undecided:** the unshared majority. It is consistent with estimation noise of each
  experiment, with fluctuations that affect only one quantity, and with fluctuations faster than
  the gap between two experiments (for every non-`zz` pair of this scope, the 10th percentile
  of the nearest-event gap on one qubit is 0.296 h or more; `comovement.json`
  `pairs[*].nearest_abs_gap_h_q10_25_50_75_90`). The literature makes the last option
  plausible, not measured
  here: TLS defects change `T1` on minutes-to-hours timescales (Klimov et al. 2018, existing
  survey `2026-10-04` §3; Thorbeck et al. 2023 on hour-scale TLS dynamics, existing survey
  `2026-10-05` §2.3), step changes in error rates persist for minutes (Hirasaki et al. 2023,
  `2026-10-05` §2.1), `T1` can switch within tens of milliseconds (Berritta et al. 2026,
  `2026-10-04` §3), and on IBM processors the fluctuations of `T1` and `T2` are well modelled as
  local to each qubit (Etxezarreta Martinez et al. 2023, `2026-10-04` §3), which matches the
  small device-wide share of §4.3. The estimation floor of the RB-based families cannot be
  computed, because IBM's production RB settings are unpublished (Wallman and Flammia 2014,
  `2026-10-05` §2.1); for readout the shot-noise part is known and is a minority (§4.4).
- **The shared, hour-scale part itself** is consistent with both a physical fluctuation of the
  qubit and a shared artefact of one calibration round (§4.2); the measurement that would
  separate them is in §9.

This document therefore does not call the non-persistent component "measurement noise" or
"estimation noise", nor does it call it physical; it records that a small part of it is shared
between experiments on one qubit within hours and that the rest is not attributed.

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
permutation test of correlation remains approximately valid; **[Verification 2026-10-06:
refuted as worded. `RO`, `p01`, `p10` and `m2` have significant negative Moran's I (p 0.001 to
0.015) and `adj_zz`, `adj_cz`, `adj_rzz` significant positive I, so six pairs (`m2` with
`adj_cz`, `adj_rzz`, `adj_zz`; `RO`, `p01`, `p10` with `adj_zz`) join two significantly
autocorrelated fields. None is significant (q 0.514 or more), so the null conclusion is
unaffected, but the validity statement does not hold for them.]** when both fields are positively
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

This scope has no assigned link of its own: its links are the 23 pairs of §1.3. The four links
assigned to other owners are in `03-readout-measurement.md` §7.2 (readout against `T1` decay),
`04-single-qubit-gates.md` §7 (`sx` against `T1`, `T2` and the coherence limit),
`05-two-qubit-gates-couplings.md` §7.2 and §7.3 (`cz`, `rzz` against their qubits) and
`06-device-time-topology.md` §7.2 (`lf` against its chain); pairs inside one family are in
`02-coherence.md` §7, `03-readout-measurement.md` §7.1 and `05-two-qubit-gates-couplings.md`
§7.1 and §7.4. Throughout, a pair "survives" when Benjamini-Hochberg rejects it at a false
discovery rate of 0.05 within this scope's family of 23 pairs (or 45 and 44 scorable
directions for lead and lag); `summary.json` tallies the survivors of every test.

### 7.1 Between qubits: do the per-qubit levels of different families go together?

Spearman correlation of the per-qubit levels (§2.1), 95% interval from 2,000 bootstrap
resamples of qubits, two-sided p from 2,000 permutations; mutual information by the KSG
estimator (k = 4, on ranks) against 1,000 permutations (`levels.json` `pairs`, owner `07`):

| Pair | Qubits | Spearman (95% interval) | BH q | MI excess over null, nats (permutation p) |
| --- | --- | --- | --- | --- |
| `T1`-`init` | 116 | -0.067 (-0.251, 0.118) | 0.872 | 0.009 (0.41) |
| `T1`-`adj_zz` | 156 | -0.005 (-0.164, 0.160) | 0.957 | -0.030 (0.73) |
| `T2`-`RO` | 155 | -0.130 (-0.289, 0.038) | 0.514 | -0.021 (0.63) |
| `T2`-`p01` | 155 | -0.110 (-0.279, 0.056) | 0.530 | -0.010 (0.57) |
| `T2`-`p10` | 155 | -0.134 (-0.288, 0.023) | 0.514 | 0.017 (0.33) |
| `T2`-`init` | 116 | -0.145 (-0.323, 0.043) | 0.514 | -0.080 (0.95) |
| `T2`-`m2` | 155 | -0.115 (-0.277, 0.046) | 0.514 | -0.012 (0.58) |
| `T2`-`adj_zz` | 155 | 0.073 (-0.082, 0.228) | 0.690 | 0.019 (0.34) |
| `RO`-`sx` | 155 | -0.010 (-0.169, 0.158) | 0.950 | -0.040 (0.80) |
| `RO`-`adj_zz` | 156 | -0.022 (-0.178, 0.133) | 0.911 | 0.018 (0.34) |
| `p01`-`sx` | 155 | -0.105 (-0.266, 0.055) | 0.530 | -0.021 (0.67) |
| `p01`-`adj_zz` | 156 | -0.023 (-0.179, 0.132) | 0.911 | -0.006 (0.53) |
| `p10`-`sx` | 155 | 0.030 (-0.136, 0.198) | 0.911 | -0.066 (0.93) |
| `p10`-`adj_zz` | 156 | -0.032 (-0.187, 0.122) | 0.911 | -0.014 (0.61) |
| `init`-`sx` | 116 | -0.034 (-0.219, 0.151) | 0.911 | -0.030 (0.68) |
| `init`-`adj_cz` | 116 | 0.101 (-0.073, 0.280) | 0.586 | 0.077 (0.083) |
| `init`-`adj_rzz` | 116 | 0.109 (-0.081, 0.291) | 0.557 | 0.022 (0.34) |
| `init`-`adj_zz` | 116 | 0.028 (-0.154, 0.220) | 0.911 | 0.046 (0.20) |
| `m2`-`sx` | 155 | -0.123 (-0.293, 0.051) | 0.514 | 0.051 (0.13) |
| `m2`-`adj_cz` | 155 | 0.118 (-0.041, 0.271) | 0.514 | 0.029 (0.26) |
| `m2`-`adj_rzz` | 154 | 0.116 (-0.050, 0.279) | 0.514 | 0.011 (0.41) |
| `m2`-`adj_zz` | 156 | -0.031 (-0.198, 0.135) | 0.911 | 0.064 (0.088) |
| `sx`-`adj_zz` | 155 | -0.015 (-0.180, 0.153) | 0.921 | 0.047 (0.17) |

- **Nothing survives.** 0 of 23 Spearman correlations and 0 of 23 mutual informations survive
  (smallest q 0.514; smallest MI permutation p 0.083); no interval excludes zero, and every
  interval lies inside -0.323 to 0.291 (`summary.json` `levels`). Partial correlations given
  all other fields (normal scores, inverse correlation matrix) give the same answer in each
  complete-case set: 0 of 17 survive in set A (154 qubits, smallest q 0.957), 0 of 23 in set B
  (116 qubits with `init`, 0.843), 0 of 14 in set C (no `init`, no `RO`, 0.201)
  (`summary.json` `levels.partial_correlations`). Mean levels and the common window from
  2026-08-07 tell the same story (for the largest pair, `T2`-`init`: -0.131 and -0.170,
  `spearman_mean_levels`, `spearman_common_window`).
- **What this excludes.** With 116 to 156 qubits the data exclude, for these pairs, a
  between-qubit rank correlation beyond about 0.3 in either direction; weaker links remain
  possible. The negative signs of `T2` against `RO`, `p01`, `p10`, `init` and `m2` (all five
  between -0.110 and -0.145) are consistent with a weak "worse coherence, worse readout"
  tendency that this sample cannot confirm.
- **Where the between-qubit structure is.** It sits in pairs owned elsewhere, quoted from the
  same file for context only (`levels.json` `pairs`, owner not `07`, not tested here): `T1`-`sx`
  -0.430 (owner 04), `sx`-`adj_cz` 0.416 and `T1`-`adj_cz` -0.265 (owner 05), `T1`-`T2` 0.305
  (owner 02), and the readout block, from 0.644 (`init`-`m2`) to 0.984 (`RO`-`p10`) (owner 03).
  §7.5 summarises that structure without re-deriving the pairs.
- **Validity of the permutation test.** Each pair joins at most one field with significant
  positive spatial autocorrelation (§5), the case in which qubits can be treated as
  exchangeable to a good approximation.

### 7.2 Within a qubit: do the non-persistent components co-move?

Each event of the sparser family is matched with the nearest event of the other family on the
same qubit within 3 h (12 h when `zz` is involved); statistic: Pearson correlation of the
normal scores of the residuals of §4.1, raw and with each family's round common mode removed;
null: 1,000 circular shifts of the second family within each entity; interval: 2,000-replicate
cluster bootstrap over qubits; nonlinear check: plug-in mutual information on 8 x 8 quantile
bins against 200 shifts (`comovement.json` `pairs`). A star marks a BH survivor.

| Pair | Matched pairs (qubits) | Median gap (h) | r raw (95% interval) | q | r, common mode removed | q | MI survives (raw, cm) | r raw before / from 2026-08-01 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `T1`-`init` | 3,478 (115) | 1.82 | -0.044 (-0.079, -0.007) * | 0.023 | -0.024 | 0.327 | no, no | no data / -0.044 |
| `T2`-`RO` | 18,889 (155) | 0.81 | -0.025 (-0.041, -0.010) * | 0.003 | -0.039 * | 0.003 | yes, yes | -0.012 / -0.042 |
| `T2`-`p01` | 18,687 (155) | 0.82 | -0.016 (-0.032, 0.000) | 0.065 | -0.023 * | 0.008 | yes, yes | 0.004 / -0.038 |
| `T2`-`p10` | 18,799 (155) | 0.83 | -0.026 (-0.042, -0.011) * | 0.003 | -0.038 * | 0.003 | no, yes | -0.026 / -0.027 |
| `T2`-`init` | 3,574 (115) | 1.82 | -0.041 (-0.075, -0.008) * | 0.033 | -0.025 | 0.314 | no, no | no data / -0.041 |
| `m2`-`T2` | 7,356 (155) | 0.59 | -0.050 (-0.072, -0.028) * | 0.003 | -0.049 * | 0.003 | no, no | no data / -0.050 |
| `sx`-`RO` | 16,206 (155) | 1.49 | 0.031 (0.012, 0.051) * | 0.003 | 0.035 * | 0.003 | no, no | 0.040 / 0.017 |
| `sx`-`p01` | 16,048 (155) | 1.49 | -0.019 (-0.035, -0.002) * | 0.023 | -0.015 | 0.142 | no, no | -0.017 / -0.020 |
| `sx`-`p10` | 15,993 (155) | 1.51 | 0.057 (0.039, 0.075) * | 0.003 | 0.058 * | 0.003 | yes, yes | 0.071 / 0.038 |
| `sx`-`init` | 2,107 (114) | 1.35 | 0.002 (-0.041, 0.046) | 0.927 | -0.008 | 0.843 | no, no | no data / 0.002 |
| `m2`-`sx` | 5,355 (155) | 1.58 | 0.027 (-0.002, 0.055) | 0.087 | 0.031 * | 0.046 | no, no | no data / 0.027 |
| `cz`-`init` | 6,458 (114) | 1.80 | 0.005 (-0.019, 0.030) | 0.826 | -0.003 | 0.964 | no, no | no data / 0.005 |
| `m2`-`cz` | 906 (155) | 2.55 | 0.026 (-0.038, 0.090) | 0.797 | 0.029 | 0.680 | no, no | no data / 0.026 |
| `rzz`-`init` | 4,948 (113) | 0.59 | -0.014 (-0.047, 0.019) | 0.581 | -0.014 | 0.628 | no, no | no data / -0.014 |
| `m2`-`rzz` | 596 (153) | 1.00 | 0.004 (-0.070, 0.079) | 0.927 | 0.003 | 0.987 | no, no | no data / 0.004 |
| `T1`-`zz` | 19,443 (156) | 2.15 | -0.003 (-0.015, 0.010) | 0.832 | -0.003 | 0.799 | no, no | -0.007 / 0.003 |
| `T2`-`zz` | 20,008 (155) | 2.15 | -0.001 (-0.015, 0.013) | 0.927 | -0.002 | 0.909 | no, no | -0.002 / 0.001 |
| `sx`-`zz` | 19,438 (155) | 2.27 | 0.003 (-0.010, 0.017) | 0.826 | 0.002 | 0.909 | no, no | -0.003 / 0.011 |
| `zz`-`RO` | 166,855 (156) | 0.81 | -0.043 (-0.051, -0.035) * | 0.003 | -0.041 * | 0.003 | yes, yes | -0.042 / -0.044 |
| `zz`-`p01` | 166,802 (156) | 0.84 | -0.037 (-0.046, -0.028) * | 0.003 | -0.035 * | 0.003 | yes, yes | -0.035 / -0.040 |
| `zz`-`p10` | 166,247 (156) | 0.87 | -0.029 (-0.036, -0.023) * | 0.003 | -0.028 * | 0.003 | yes, yes | -0.030 / -0.028 |
| `init`-`zz` | 23,743 (116) | 1.15 | -0.009 (-0.024, 0.005) | 0.300 | -0.009 | 0.405 | no, no | no data / -0.009 |
| `m2`-`zz` | 7,466 (156) | 2.34 | -0.008 (-0.029, 0.014) | 0.777 | -0.010 | 0.628 | no, no | no data / -0.008 |
| `T1`-`T2` (02, control) | 19,899 (155) | 0.0011 | 0.693 (0.665, 0.719) | not tested | 0.669 | not tested | not tested | 0.690 / 0.696 |
| `RO`-`p10` (03, control) | 84,785 (156) | 0 | 0.781 (0.754, 0.803) | not tested | 0.775 | not tested | not tested | 0.782 / 0.780 |

(q values of 0.003 are the BH-adjusted floor 0.002872 of a 1,000-shift null.)

- **Detectable, and practically negligible.** 11 of 23 pairs survive on raw residuals and 10
  of 23 with the common mode removed; 6 and 7 survive on mutual information (`summary.json`
  `comovement`). The largest absolute correlation is 0.057 (`sx`-`p10`, 0.058 with the common
  mode removed), against 0.693 and 0.781 for the controls: the instrument detects dependence
  when it is there, and the dependence between families is far weaker. Every
  mutual-information survivor also survives on the correlation in at least
  one residual form, so no purely nonlinear link appears.
- **Directions.** Where a pair survives, the two quantities tend to be worse together: `T2` low
  when readout errors are high, `m2` high when `T2` is low, `sx` high when `RO` and `p10` are
  high, `T1` and `T2` low when `init` is high. Two directions do not fit that pattern: `sx`
  against `p01` (-0.019, gone with the common mode removed) and `zz` against all three readout
  errors (-0.029 to -0.043, a larger `|zz|` with a smaller readout error).
- **Both coverage periods.** All 8 survivors that have matched events before and after
  2026-08-01 keep their sign in both periods, on raw and on common-mode-removed residuals
  (`summary.json` `comovement.*.survivors_same_sign_both_periods`); sizes differ (`sx`-`p10`
  0.071 before, 0.038 after). The `init` and `m2` pairs have no data before 2026-08-01, so this
  check does not apply to them.
- **`zz` against readout is a candidate, not a mechanism.** It is the strongest of the dense
  pairs in significance because it has the most matched events, and it appears again at the
  qubit-day level (§7.5, `RO`-`adj_zz` -0.061) and with the same sign, not surviving, at the
  device-day level (§7.7). But `zz`'s time is a file time (§1.1); its new values appear in a file
  after a readout stamp more often than before it (0.71 of non-zero gaps, median 1.02 h;
  `alignment.json` `nearest_event_gap_same_qubit.RO|zz`), and no fetched source documents how
  `zz_<ab>` is produced (`05-two-qubit-gates-couplings.md` §1.4). Whether a readout calibration
  feeds the `zz` value, or both respond to one change of the qubit, is not decidable here.

### 7.3 Lead and lag: does one family's recent movement predict another's next value?

For each of the 46 directions (23 pairs, both ways), the response is the target's deviation
from its own causal EWMA level; predictors are the other family's innovations published in a
file strictly before the target's event, in three models: every form at lag 1 (linear,
absolute value, two jump indicators, four quantile-bin dummies, plus intercept: nine columns),
linear at lags 1 to 3, and every form using only predictor events stamped at least 3 h before
the target (so not from the target's own round). Fit before each target's 70% time cut
(`leadlag.json` `cuts_utc`, from 2026-08-06 for `zz` to 2026-09-21 for `m2`), score after it;
effect size: test mean absolute error over that of the intercept-only reference (§6), with a
2,000-replicate cluster bootstrap over target entities; test: one-sided Wilcoxon over target
entities (`leadlag.json` `pairs`).

| Model | Directions scored | Survivors | Best ratio (direction) | Worst ratio (direction) | Intervals entirely below 1 | Entirely above 1 | Smallest Wilcoxon p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Every form, lag 1 | 45 | 0 | 0.99911 (`init` to `sx`) | 1.0315 (`m2` to `rzz`) | 1 | 19 | 0.026 |
| Linear, lags 1 to 3 | 44 | 0 | 0.99942 (`p10` to `T2`) | 1.0103 (`m2` to `T2`) | 0 | 8 | 0.076 |
| Every form, at least 3 h earlier | 45 | 0 | 0.99854 (`init` to `T2`) | 1.0315 (`m2` to `rzz`) | 0 | 18 | 0.042 |

(`summary.json` `leadlag`.) The one interval entirely below 1 is `init` to `sx`, 0.99911
(0.99823 to 0.99990), whose Wilcoxon p 0.026 does not survive (q 1.0). The largest absolute
test-period Spearman correlation between a predictor's lag-1 innovation and the target's
deviation is 0.038 (`summary.json` `leadlag.lag1_all.max_abs_test_spearman_lag1`).

- **No direction carries out-of-time information.** The best model improves the target's
  forecast by 0.15% (`init` to `T2`, ratio 0.99854) and does not survive. Ratios above 1 with
  intervals above 1 are overfitting: nine columns fitted on training events that do not
  generalise; the worst, `m2` to `rzz` (1.0315, interval 1.0220 to 1.0423), has only 5,679 events
  with a signal (`events_with_signal`).
- **What this extends.** P3 found no linear gain above 0.6% from the other fields at the same
  file for six targets (`docs/roadmap/2026-10-05-feature-patterns-and-method.md` §2, P3). This
  test adds nonlinear forms, three lags, strict separation from the target's round, `init`,
  `m2`, `p01`, `p10` and `zz`, and a reference that removes the free bias correction (§6).
- **What it cannot exclude.** Each target's test period is its last 30%, all after the
  coverage change of 2026-08 (§3.3); relationships that existed only earlier, or that act on
  lags beyond three events, are not tested. Pairs owned elsewhere (for example `T1` to `sx`) are
  not in this table.

### 7.4 Coincidence: do large deviations of different families hit the same qubit together?

A large deviation is an event whose innovation against its own EWMA level exceeds 3 robust sd
of the entity's innovations; "adverse" keeps the harmful direction only (`T1`, `T2` down; errors
and `|zz|` up). Events are binned into operational days (from 16:00 UTC); a coupler family flags
a qubit-day when any adjacent coupler does (`coincidence.json`). Flag rates per observed
qubit-day: `T1` 0.020, `T2` 0.035, `RO` 0.122, `p01` 0.112, `p10` 0.125, `init` 0.072, `m2`
0.038, `sx` 0.024, `cz` 0.080, `rzz` 0.084, `zz` 0.091 (`families.*.flag_rate`; the readout
rates are higher because readout is re-measured several times a day). Two nulls, 1,000
replicates each: **time** (the second family's day series circularly shifted per qubit, which
keeps each qubit's rate) and **qubit** (the second family's flags permuted among the qubits
observed that day, which keeps each day's device-wide count, so excess over it is local to a
qubit beyond device-wide bad days). Lift is the observed count over the null mean; interval
from 2,000 cluster-bootstrap resamples of qubits.

Same day, pairs that survive at least one null (star: BH survivor; `pairs[*].big_lag0`,
`adv_lag0`):

| Pair | Qubit-days both observed | Both flagged | Lift, time null (95% interval) | Lift, qubit null (95% interval) | Adverse only: lift, qubit null |
| --- | --- | --- | --- | --- | --- |
| `T2`-`RO` | 19,536 | 105 | 1.38 (1.13, 1.64) * | 1.26 (1.03, 1.51) * | 1.43 (1.15, 1.72) * |
| `T2`-`p01` | 19,517 | 95 | 1.40 (1.12, 1.69) * | 1.22 (0.99, 1.48) * | 1.29 (0.91, 1.73) |
| `T2`-`p10` | 19,512 | 107 | 1.37 (1.13, 1.62) * | 1.27 (1.02, 1.52) * | 1.43 (1.15, 1.72) * |
| `sx`-`RO` | 19,129 | 83 | 1.55 (1.25, 1.86) * | 1.50 (1.19, 1.82) * | 1.50 (1.13, 1.87) * |
| `sx`-`p10` | 19,087 | 91 | 1.63 (1.29, 1.97) * | 1.59 (1.25, 1.92) * | 1.82 (1.43, 2.22) * |
| `sx`-`m2` | 6,984 | 11 | 1.84 (0.85, 3.01) | 1.96 (0.90, 3.15) * | 2.14 (0.86, 3.42) |
| `zz`-`T1` | 18,709 | 46 | 1.38 (0.90, 1.98) * | 1.52 (0.99, 2.23) * | 1.37 (0.43, 2.22) |
| `zz`-`T2` | 19,241 | 77 | 1.33 (0.92, 1.86) * | 1.35 (0.91, 1.90) * | 1.21 (0.56, 1.96) |
| `zz`-`sx` | 18,837 | 56 | 1.38 (0.93, 1.88) * | 1.34 (0.85, 1.96) * | 1.56 (0.65, 2.64) |
| `zz`-`RO` | 21,055 | 412 | 1.81 (1.64, 1.98) * | 1.60 (1.41, 1.82) * | 1.51 (1.05, 2.03) * |
| `zz`-`p01` | 21,037 | 332 | 1.62 (1.41, 1.81) * | 1.43 (1.21, 1.65) * | 2.10 (1.25, 3.02) * |
| `zz`-`p10` | 20,959 | 427 | 1.84 (1.64, 2.06) * | 1.63 (1.41, 1.85) * | 1.52 (1.08, 1.97) * |
| `zz`-`m2` | 7,316 | 34 | 1.25 (0.83, 1.73) | 1.83 (1.20, 2.46) * | 1.48 (0.48, 2.48) |
| `T1`-`T2` (control) | 19,010 | 155 | 12.77 (10.94, 14.93) | 9.31 (8.12, 10.51) | 10.38 (9.01, 11.81) |
| `RO`-`p10` (control) | 21,540 | 1,802 | 5.60 (5.29, 5.96) | 4.63 (4.46, 4.81) | 5.81 (5.57, 6.06) |

- **Survivor counts** (`summary.json` `coincidence`): same day, 11 pairs on the time null and
  13 on the qubit null, the 11 being among the 13; adverse only, 8 and 7; next day (the first
  family on day d, the second on day d + 1), 5 and 9; adverse next day, 1 and 2. The ten pairs
  not in the table (`T1`, `T2`, `sx`, `cz`, `rzz`, `zz` with `init`; `T2`, `cz`, `rzz` with `m2`;
  `sx` with `p01`) survive neither null on the same day.
- **What is robust.** Pairs that survive both nulls cannot be explained by device-wide bad days
  (the qubit null keeps them) or by qubits that are flagged often on both families at all times
  (the time null keeps each qubit's rate). Those are the coherence-readout pairs, the
  `sx`-readout pairs and every `zz` pair with `T1`, `T2`, `sx` and readout. `sx`-`m2` and
  `zz`-`m2` survive only the qubit null, so they may reflect qubits that are flagged more often
  on both families throughout, not a shared day; and the time null for `init` and `m2` shifts
  their flags into months before their schema start, so for those pairs the qubit null is the
  test to read. For the `zz` pairs with `T1`, `T2` and `sx` the bootstrap interval includes 1
  while the permutation test rejects; read them as marginal.
- **Size.** Lifts of 1.2 to 2.1: large deviations of two different families on one qubit-day
  co-occur up to about twice as often as chance, against 4.6 to 12.8 for the controls in the
  table.
- **Next day.** The `sx`-readout pairs and the `zz` pairs keep a lift above 1 on the next day
  (for example `sx`-`p10` 1.47 on the qubit null, `big_lag1`). Whether that is one episode split
  by the 16:00 UTC day boundary or a deviation that persists into the next day is not separated
  here.
- **Both periods.** Of the 11 same-day qubit-null survivors with coincidences before
  2026-08-01, all 11 have a time-null lift above 1 in both periods (`summary.json`
  `coincidence.big_lag0.of_which_lift_time_above_1_in_both_periods`); the `init` and `m2` pairs
  have no data before 2026-08-01.

**Several families on one qubit-day** (`multi_family`; units flagged on a qubit-day, against
both nulls applied to every unit independently; 22,612 qubit-days with any observation):

| Units | Qubit-days with at least 3 units flagged | Time null mean (lift) | Qubit null mean (lift) |
| --- | --- | --- | --- |
| 7 physical groups, any deviation | 309 | 161.6 (1.91) | 186.4 (1.66) |
| 7 physical groups, adverse only | 111 | 39.2 (2.83) | 46.7 (2.38) |
| 11 families, any deviation (inflated by within-family links) | 1,629 | 550.4 (2.96) | 629.6 (2.59) |
| 11 families, adverse only (inflated) | 1,079 | 190.8 (5.66) | 214.1 (5.04) |

Each observed count exceeds all 1,000 replicates of both nulls (p 0.001, the floor). The
groups are coherence (`T1`, `T2`), readout (`RO`, `p01`, `p10`), `init`, `m2`, `sx`, two-qubit
(`cz`, `rzz`) and `zz`, a group flagged when any member is (`multi_family_groups`); grouping
removes the arithmetic and same-experiment links inside a family, which inflate the 11-family
counts. With groups, 3 or more of 7 flagged on the same qubit-day happens about twice as often
as the nulls predict (1.66 and 1.91), and adverse triples 2.38 to 2.83 times as often.

### 7.5 Latent factors: what the families share across qubits and across qubit-days

**Between qubits** (`levels.json` `multivariate`; normal scores of the per-qubit levels; PCA of
their correlation matrix; parallel analysis against 1,000 column-permuted matrices; loading
intervals from 500 bootstrap resamples of qubits; Horn 1965 for parallel analysis). Set A (10
fields without `init`, 154 qubits, `q72` and `q99` excluded):

| Component | Eigenvalue (share) | Parallel-analysis 95% | Loadings above 0.3 in absolute value (95% interval) | Loadings whose interval includes 0 |
| --- | --- | --- | --- | --- |
| PC1, readout | 3.830 (0.383) | 1.552 | `RO` 0.494 (0.444, 0.510), `p10` 0.489 (0.444, 0.499), `p01` 0.471 (0.405, 0.500), `m2` 0.458 (0.399, 0.483) | `T1` -0.031, `T2` -0.106, `sx` 0.051, `adj_cz` 0.184, `adj_rzz` 0.193, `adj_zz` -0.004 |
| PC2, coherence and gates | 2.583 (0.258) | 1.369 | `adj_cz` 0.489 (0.391, 0.564), `adj_rzz` 0.478 (0.381, 0.557), `sx` 0.457 (0.384, 0.488), `T1` -0.404 (-0.453, -0.307) | `RO` -0.111, `p01` -0.179, `p10` -0.073, `m2` -0.160, `adj_zz` 0.009 |
| PC3 | 1.043 (0.104) | 1.258 (not exceeded) | `adj_zz` 0.734 (interval -0.499 to 0.971) | |

`T2` loads on PC2 at -0.292 (-0.369, -0.145). Two components exceed parallel analysis; the
third does not, and `adj_zz` loads on neither retained component.

- **Two nearly separate axes of qubit quality.** The argument is not the orthogonality of the
  components (which PCA imposes), but the loadings: every readout field loads on PC1 with an
  interval above 0.39 and on PC2 with an interval that includes 0; `T1`, `sx`, `adj_cz` and
  `adj_rzz` load on PC2 with intervals away from 0 and on PC1 with intervals that include 0.
  The between-qubit correlations agree: `RO`, `p01`, `p10` and `m2` against `T2` and `sx`
  levels lie between -0.134 and 0.030 (§7.1), and against `T1` levels (owned by 03, quoted for
  context) between -0.028 and 0.158 (`levels.json` `pairs`). A qubit's readout quality says almost
  nothing about its coherence and gate quality, and the reverse.
- **Robust to the field set.** Set B (116 qubits, with `init`) keeps the same two components
  (eigenvalues 4.299 and 2.385 against parallel-analysis 1.666 and 1.474), with `init` on the
  readout component (0.412, interval 0.354 to 0.444). Set C (no `init`, no `RO`, 154 qubits)
  also has two components above parallel analysis (2.976 and 2.483), but their eigenvalues are
  close and the bootstrap loadings mix them (for example `p01` on PC1, 0.079 to 0.568), so its
  rotation is not stable; the two-dimensional subspace is the robust finding, not set C's axes.
- **On the device** (§5): the readout score rises with a qubit's degree (Spearman 0.420), the
  coherence-and-gate score is positively autocorrelated and higher towards the centre.

**Across qubit-days** (`common_mode.json` `change_matrix`; per qubit and operational day, the
median residual of each family, coupler families as the mean over adjacent couplers;
correlation of normal scores over qubit-days, pairwise complete; eigenvalues against 200 nulls
in which each family's day axis is shifted per qubit):

| Component | Eigenvalue (share), raw | Null 95% | Main loadings, raw | Eigenvalue, common mode removed |
| --- | --- | --- | --- | --- |
| 1 | 2.464 (0.224) | 1.076 | `RO` 0.578, `p01` 0.516, `init` 0.410, `p10` 0.391, `m2` 0.267 | 2.429 |
| 2 | 1.708 (0.155) | 1.048 | `T1` 0.693, `T2` 0.692 | 1.680 |
| 3 | 1.241 (0.113) | 1.035 | `adj_cz` 0.615, `adj_rzz` 0.596, `sx` 0.335 | 1.227 |
| 4 | 1.068 (0.097) | 1.023 | `p10` 0.584 against `init` -0.476 and `p01` -0.302 | 1.065 |

All four reported components exceed the null in both forms (`summary.json`
`common_mode.change_matrix.*.components_exceeding_null`). Each is one family block (readout,
coherence, two-qubit with `sx`) or a contrast inside the readout block. The null shifts every
family independently, so within-family links count as structure: these eigenvalues are the
family blocks, not a factor shared across blocks. Across blocks, 6 of 23 day-aligned pairs
survive on raw residuals and 7 with the common mode removed (`T2`-`m2`, `RO`-`sx`, `p10`-`sx`,
`RO`-`adj_zz`, `p01`-`adj_zz`, `p10`-`adj_zz`, plus `init`-`sx` with the common mode removed),
all with absolute correlations of 0.061 or less (`RO`-`adj_zz` -0.061;
`summary.json` `common_mode.change_matrix`). The day-level picture repeats the event-level one
of §7.2: tiny cross-family co-movement inside strong family blocks.

### 7.6 Archetypes: are there discrete kinds of qubit?

Ward clustering of the normal-score level matrix of set A (154 qubits, 10 fields) for k = 2 to
6, silhouette against two nulls of 200 draws each (column-permuted, which destroys the
correlation between fields; Gaussian with the observed correlation matrix, which keeps it), and
stability as the adjusted Rand index between the full-data labels and nearest-centroid labels
from 200 bootstrap refits (`levels.json` `multivariate.A_10_fields_no_init.archetypes_ward`;
Ward 1963, Rousseeuw 1987, Hubert and Arabie 1985):

| k | Silhouette | Column-permuted null, 95% | Correlated-Gaussian null, 95% (p) | Bootstrap ARI, median (10%, 90%) | Sizes |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.155 | 0.084 | 0.231 (0.965) | 0.368 (0.178, 0.470) | 71, 83 |
| 3 | 0.154 | 0.071 | 0.186 (0.622) | 0.423 (0.280, 0.548) | 71, 20, 63 |
| 4 | 0.139 | 0.070 | 0.167 (0.632) | 0.386 (0.281, 0.500) | 71, 20, 19, 44 |
| 5 | 0.138 | 0.072 | 0.158 (0.418) | 0.419 (0.289, 0.571) | 18, 53, 20, 19, 44 |
| 6 | 0.140 | 0.075 | 0.147 (0.154) | 0.398 (0.296, 0.520) | 18, 18, 35, 20, 19, 44 |

- **No archetypes beyond a correlated continuum.** The silhouette beats the column-permuted null
  at every k (so the fields are correlated), but never the correlated-Gaussian null (p 0.154 to
  0.965): a cloud with the observed correlations and no clusters gives silhouettes as high. The
  labels are also unstable (median ARI 0.37 to 0.42).
- **The one interpretable split.** At k = 3 (median normal scores per cluster, `profiles`): 71
  qubits with good readout (`RO` -0.680) and average coherence; 63 with poor readout (`RO`
  0.534) and good gates (`sx` -0.497, `adj_cz` -0.407); and 20 qubits poor on almost everything
  (`T1` -0.745, `T2` -0.712, `RO` 0.732, `sx` 1.113, `adj_cz` 1.361). These are regions of the
  two-axis continuum of §7.5, the 20 being its tail where both axes are bad, not discrete kinds.
- **Not spatial.** Coupled qubits share a label no more often than under permutation (§5).

### 7.7 Device-wide common mode across all families

The device-wide part of each family is small and moves on its own:

- **Size.** The round common mode takes 0.012 to 0.130 of the residual variance (robust; §3.1),
  and the device series shrinks to near the independent-entity prediction at the shortest lag
  for `RO`, `p01`, `m2` and `zz`, and to 1.35 to 3.25 times it for the others (§4.3). For readout
  and coherence the device-wide part is larger at month lags than at the shortest lag: a
  drifting device level rather than a shared fast component.
- **Across families.** Of the 55 pairs of device-day changes, 8 survive, and 7 of those are
  inside a family (`summary.json` `common_mode.device_daily_bh_survivors`; §3.2). The one
  cross-family survivor is `p01`-`sx`, -0.341. Among the non-survivors with the largest values,
  `RO`-`zz` (-0.251, q 0.058) and `p10`-`zz` (-0.236, q 0.156) have the sign of the event-level
  `zz`-readout correlation (§7.2), and `p01`-`cz` (0.284, q 0.060) is near the threshold
  (`common_mode.json` `device_daily.pairs`).
- **Joint jumps.** Three operational days have at least three families jumping (null mean
  0.312, p 0.0035), and only 2026-05-14 joins different physical families (coherence down,
  every gate error up; §3.2).

Taken with §7.2 and §7.4, the families share three things: a slowly moving device level that is
largely family-specific, a small qubit-local component shared by experiments measured within
hours (§4.2), and coincident large deviations on the same qubit-day (§7.4). They share no
detectable between-qubit level structure outside the owned links (§7.1), and no family's recent
movement forecasts another's (§7.3).

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
  documented on other devices (McEwen et al. 2022 and Wilen et al. 2021, fetched 2026-10-06;
  Thorbeck et al. 2023 in the existing survey `2026-10-05` §2.3), but those abstracts describe
  transient, chip-wide or spatially extended events (quasiparticle bursts that limit all qubits
  at once; charge jumps with a transient suppression of `T1` over hundreds of micrometres), which
  a daily calibration cannot resolve; the qubit-local, same-day coincidence of §7.4 is a
  different, slower phenomenon.

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

Then, after the six above, the tallies the text cites (reads only `results/cross/*.json`):

```bash
$PY $D/summary.py       # results/cross/summary.json      (BH survivor counts, extremes, period agreement, variogram ratios; seconds)
```

Helpers: `xcommon.py` (families, transforms, owner map, BH) and `xresid.py` (residuals, rounds,
common mode, matching, circular-shift nulls, cluster bootstrap). Seeds are fixed
(`xcommon.SEED` plus an offset per script). Lint: `C:/t/ruffpin/Scripts/ruff.exe check` and
`format` on `analysis/cross/` pass.

**Completion notes (2026-10-06, same day; completes the work-in-progress state committed as
`4a85791`).** The first analyst stopped at a usage limit with placeholders in §0, §3.3, §4 and §7; a second session
filled them from the results files. What that session ran and changed:

- **Re-runs.** `coincidence.json` predated the last edit of `coincidence.py` (its multi-family
  block lacked the grouped units), so it was re-run; its pair-level results were unchanged.
  `levels.py`, `alignment.py`, `leadlag.py` and `common_mode.py` were re-run and reproduced
  their files exactly apart from `measured_utc` (and the fix below). `comovement.json` was not
  re-run (its script and helpers predate it; it takes longer than five minutes).
- **Fix in `levels.py`.** `events_per_qubit_median` counted the qubits without the field as
  zeros, which pulled `init` down to 234.5; over the 116 qubits that carry `init` it is 241, as
  `alignment.json` also gives. The §2.1 table was corrected from 234.5 to 241.
- **New script `summary.py`** writes the counts and ratios the text cites.
- **Text corrected for contradictions.** §3.3 claimed that every surviving effect keeps its
  direction in both periods; it now states the check only for pairs with data in both periods,
  with the counts. §8 attributed McEwen et al. and Wilen et al. to the existing survey and said
  the bursts "last milliseconds"; neither is in that survey (both were fetched) and neither
  abstract gives a duration, so the sentence now says what the abstracts say. §11 records that
  Horn 1965 was confirmed on its DOI landing page, not on Crossref. All eleven fetched sources
  were re-fetched and their titles re-confirmed in the second session.

## 11. Sources

New sources: 11 fetched on 2026-10-06 (title confirmed on the arXiv abstract page, the Crossref
record, the DOI landing page, or the vendor page). The others are cited from the two existing
surveys by their
identifier and section.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum documentation, "Monitoring, calibrations, and benchmarking" | https://quantum.cloud.ibm.com/docs/en/guides/calibration-jobs | fetched 2026-10-06 | What is benchmarked daily, hourly monitoring incl. readout and TLS signatures, batching (§1.2) |
| Wilen et al., Correlated charge noise and relaxation errors in superconducting qubits (Nature 2021) | arXiv:2012.06029 | fetched 2026-10-06 | Particle impacts cause spatially correlated charge jumps with transient `T1` suppression (§8) |
| McEwen et al., Resolving catastrophic error bursts from cosmic rays in large arrays of superconducting qubits (Nature Physics 2022) | arXiv:2104.05219 | fetched 2026-10-06 | Chip-wide bursts limit all qubits at once (§8) |
| Kraskov, Stoegbauer, Grassberger, Estimating mutual information (PRE 2004) | arXiv:cond-mat/0305641 | fetched 2026-10-06 | KSG k-nearest-neighbour MI estimator (§7.1) |
| Benjamini and Hochberg, Controlling the false discovery rate (JRSS B 1995) | doi:10.1111/j.2517-6161.1995.tb02031.x | fetched 2026-10-06 (Crossref) | Multiple-testing control throughout |
| Horn, A rationale and test for the number of factors in factor analysis (Psychometrika 1965) | doi:10.1007/BF02289447 | fetched 2026-10-06 (DOI landing page) | Parallel analysis for the PCA (§7.5) |
| Hubert and Arabie, Comparing partitions (J. Classification 1985) | doi:10.1007/BF01908075 | fetched 2026-10-06 (Crossref) | Adjusted Rand index (§7.6) |
| Rousseeuw, Silhouettes (J. Comput. Appl. Math. 1987) | doi:10.1016/0377-0427(87)90125-7 | fetched 2026-10-06 (Crossref) | Silhouette (§7.6) |
| Ward, Hierarchical grouping to optimize an objective function (JASA 1963) | doi:10.1080/01621459.1963.10500845 | fetched 2026-10-06 (Crossref) | Ward clustering (§7.6) |
| Moran, Notes on continuous stochastic phenomena (Biometrika 1950) | doi:10.1093/biomet/37.1-2.17 | fetched 2026-10-06 (Crossref) | Moran's I (§5) |
| Clifford, Richardson, Hemon, Assessing the significance of the correlation between two spatial processes (Biometrics 1989) | doi:10.2307/2532039 | fetched 2026-10-06 (Crossref) | Effective sample size under spatial autocorrelation (§5) |
| Deng et al., Qubit Health Analytics and Clustering (2025) | arXiv:2508.21231 | existing survey `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` §2.1, §8 | Nearest precedent for archetypes (§8) |
| Thorbeck et al., TLS dynamics due to background ionizing radiation (2023) | arXiv:2210.04780 | existing survey `docs/roadmap/2026-10-05-gate-error-literature-survey.md` §2.3 | Hour-scale TLS dynamics; TLS scrambling (§4.5, §8) |
| Schlör et al., Correlating decoherence in transmon qubits (PRL 2019) | arXiv:1901.05352 | existing survey `2026-10-04` §3, §8 | One fluctuator moves `T1` and `T2` together (control pair, §4.1) |
| Klimov et al., Fluctuations of energy-relaxation times (PRL 2018) | arXiv:1809.01043 | existing survey `2026-10-04` §3, §8 | TLS-driven `T1` fluctuations (§4.5) |
| Etxezarreta Martinez et al., Multi-qubit time-varying quantum channels (2023) | arXiv:2207.06838 | existing survey `2026-10-04` §3, §8 | Fluctuations local to each qubit on IBM devices (§4.5) |
| Berritta et al., Real-time adaptive tracking of fluctuating relaxation rates (2026) | arXiv:2506.09576 | existing survey `2026-10-04` §3, §8 | Millisecond `T1` switching (§4.5) |
| Hirasaki et al., Detection of temporal fluctuation in superconducting qubits (2023) | arXiv:2307.04337 | existing survey `2026-10-05` §2.1 | Step changes lasting minutes (§4.5) |
| Wallman and Flammia, Randomized benchmarking with confidence (2014) | arXiv:1404.6025 | existing survey `2026-10-05` §2.1 | IBM's production RB settings unpublished; estimation floor must be measured (§4.5) |

Project sources: `01-data-layer.md` (field semantics, identities, faults, device-wide changes);
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P1 to P8, quoted where named);
`scripts/feature_patterns.py` (the measured event rule and the round rule).

## Verification (2026-10-06)

Verifier session, same day, same laptop, ref `7b84b50`. Own scripts: `analysis/verify/cross/`
(`v_levels.py`, `v_comovement.py`, `v_coincidence.py`, written from `ddload` only; pinned ruff
check and format pass); results `results/verify/cross/` (`levels_check.json`,
`comovement_check.json`, `coincidence_check.json`). Provisional like everything above.

**Re-run of the owner's scripts.** All seven (`alignment`, `levels`, `leadlag`, `common_mode`,
`coincidence`, `comovement`, `summary`) were re-run; every results JSON is identical to the
pre-run file apart from `measured_utc` (`summary.json` also differs in its stored source
timestamps). This includes `comovement.json`, which the completion notes say was not re-run.

**Numbers recomputed independently**

| Claim | Document value | Recomputed | Match |
| --- | --- | --- | --- |
| Events per family (T1, RO, sx, init) | 20,063; 90,408; 20,207; 23,952 | same four | yes |
| `init` series and events-per-qubit median | 116; 241 | 116; 241 | yes |
| `T1`-`T2` nearest gap: median, share within 0.25 h | 0.00111 h; 0.9933 | 0.00111 h; 0.9930 (n 20,039, no lifetime restriction) | yes |
| Level pairs surviving BH, of 23 | 0 (smallest q 0.514) | 0 (smallest q 0.462, 4,000 permutations) | yes |
| Level Spearman range (min, max) | -0.145 to 0.118 | -0.145 to 0.118 | yes |
| PCA set A eigenvalues, 154 qubits | 3.830, 2.583, 1.043 (shares 0.383, 0.258) | 3.830, 2.583, 1.043 (0.383, 0.258) | yes |
| Parallel analysis 95% | 1.552, 1.369, 1.258 | 1.542, 1.372, 1.256 | yes (Monte Carlo) |
| `sx`-`p10` nearest-event r, n | 0.057; 15,993 | 0.0574; 15,986 | yes |
| same, before / from 2026-08-01 | 0.071 / 0.038 | 0.0712 / 0.0378 | yes |
| `sx`-`p10` gap bins, 0 to 0.5 / 0.5 to 2 / 2 to 6 h | 0.108 (1,530); 0.069; 0.028 | 0.1083 (1,530); 0.0692; 0.0275 | yes |
| `sx`-`p10` shift null | p 0.005 | p 0.0099 (100 shifts; floor 0.0099) | yes |
| `T1`-`T2` control r | 0.693 | 0.6928 | yes |
| `T2`-`RO` nearest r | -0.025 | -0.0255 | yes |
| `zz`-`RO` nearest r, n | -0.043; 166,855 | -0.043; 166,849 | yes |
| `sx`-`p10` same-day coincidence (own EWMA 0.2, 3 sd) | 91 flagged, qubit-null lift 1.59 | 89 flagged, lift 1.54 (p 0.005) | yes (different flag definition) |
| `T1`-`T2` control qubit-null lift | 9.31 | 9.32 | yes |

Lead and lag (best ratio 0.99854, 0 survivors) and the common-mode shares were checked by
re-running the owner's scripts only, not independently.

**Claims challenged**

| # | Claim | Verdict | Why |
| --- | --- | --- | --- |
| 1 | The `sx`-`p10` correlation is shared on an hour scale (0.108, 0.069, 0.028, then 0) | weakened | Reproduces exactly at +-7 d and +-14 d windows (0.111 at 0 to 0.5 h). At +-2 d it is 0.032 at 0 to 0.5 h, 0.058 at 0.5 to 2 h, 0.005 at 2 to 6 h. A shared component that moves over 2 to 7 days (a level step, a slow calibration state) produces the same short-gap correlation, so "hour scale" is not established. Caveat: a +-2 d window is noisy for a daily family. |
| 2 | Seven of eight pairs show the same decay shape | weakened | Raw `T2`-`RO` bins are 0.018, -0.039, 0.006, 0.020, 0.020 (no decay); the table switches to the common-mode-removed form for the `T2`-readout rows after seeing the raw result. `T1`-`init` (484 pairs) and `T2`-`init` (495) are about 2.8 and 2.6 standard errors at the shortest bin among 23 pairs and five bins. |
| 3 | Large deviations coincide beyond device-wide bad days (lifts 1.2 to 1.6) | weakened | Reproduces at 3 sd (`sx`-`p10` 1.54). At 2 sd the qubit-null lift is 1.07 (p 0.040) and the shift-null lift 1.44: the effect is confined to the extreme tail and rests on 80 to 110 co-flagged qubit-days per pair. In my definition `T2`-`RO` has lift 1.49 before 2026-08-01 but 1.01 from it, so the "both periods" statement holds only for the time null the document cites. |
| 4 | Each §7.1 pair joins at most one autocorrelated field, so the permutation test is valid | refuted as worded | Six pairs join two fields with significant Moran's I (marker in §5). None is significant, so the null result stands. |
| 5 | Between-qubit levels: nothing survives, readout and coherence-gate are two axes | upheld | Spearman, BH and PCA reproduce independently. The 154-qubit PCA is descriptive; the inference "nearly separate" rests on loadings, as the text says. |
| 6 | `zz` against readout is a candidate only, not a mechanism | upheld | r -0.043 reproduces; all `zz` event stamps equal a file time (share 1.0 in `comovement_check.json`), so the document's refusal to place it in time is correct. |
| 7 | The non-persistent component is not attributed to noise | upheld | No sentence calls it measurement or estimation noise; the cross-family evidence is described as not deciding the question. (See claim 1 for the one overreach.) |

Not checked: out-of-time lead and lag (independent re-implementation), Ward archetype nulls,
and the device-day jump table.

**Sources spot-checked (fetched 2026-10-06)**

| Source | Title confirmed | Cited claim |
| --- | --- | --- |
| IBM, "Monitoring, calibrations, and benchmarking" | yes | Daily benchmarking with T1/T2, readout, RB; hourly monitoring of readout parameters and TLS signatures; batched calibrations; TLS can change strategy including pausing: supported |
| Wilen et al., arXiv:2012.06029, "Correlated charge noise and relaxation errors in superconducting qubits" | yes | Charge jumps with transient T1 suppression, correlated over more than 600 micrometres: supported |
| McEwen et al., arXiv:2104.05219, "Resolving catastrophic error bursts from cosmic rays in large arrays of superconducting qubits" | yes | Chip-wide bursts limit all qubits; abstract gives no duration, as §10 says: supported |

**Rule check.** No em dash (U+2014) in the document (0 found). Provisional banner, ref, basis
and machine are in the header. Every number checked traces to a `results/cross` field; no rows
added to `docs/numerical-claims.md` (file unchanged in the working tree). The stray "(g)" in the
§3.2 heading remains; it is the earlier analyst's leftover and is harmless. Inline markers were
added at §0 (two), §4.2, §4.5 and §5; original text is kept.
