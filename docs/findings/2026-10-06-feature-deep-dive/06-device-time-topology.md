# 06 · Device, time and topology: schedule, documents, states, change points, faults, layout and layer fidelity

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: reconcile it
later by appending an as-of section, never by editing the text below.

**Every figure here is provisional.** Ref: `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`. Basis: all 1,760 `ibm_fez` snapshot files
(2026-05-13T12:13:22Z to 2026-10-06T02:57:42Z), 156 qubits, 176 undirected couplers, 97
`lf_<N>` names, read only through `analysis/ddload.py`; re-measurement events per family,
after dropping values carried into the first document from before the archive starts:
readout 90,252, `init_error` 23,952, `measure_2` 7,925, `T1` 19,908, `T2` 20,471, `sx`
20,054, `xslow` 6,532, `cz` 21,921, `rzz` 18,043 (couplers counted once), `lf` 7,954 (82 lf
events times 97 names). Measured on 2026-10-06 on the lead's laptop (Windows 11, CPython
3.12). Nothing here is registered in `docs/numerical-claims.md`. Scripts are in
`analysis/device/`, results in `results/device/`; every number below is a field of one of
those results files, of `results/data-layer/*.json`, or is quoted from a named repository
document. Section 10 maps them.

This document owns the file-level arrays, the `meta.json` structure and `gen.lf`. It reads
the stamped dates and values of every family only to study the schedule, change points and
the fault map; per-family statistics belong to documents 02 to 05. No model, strategy or
decision is proposed here, and nothing here records an approval of A1 to A9.

## 0. Summary

- **The calibration cycle is slightly longer than a day and walks around the clock.** Daily
  major rounds start later each day by a median 0.73 h (`T1`, `T2`), 0.89 h (`sx`), 1.11 h
  (`cz`), 1.16 h (`rzz`) and 2.43 h (`lf`), with median gaps of 24.7 h, 24.9 h, 25.1 h,
  25.3 h and 26.5 h; short gaps (restarts) pull the cycle back. Day of week is uniform for
  every family (chi-square p from 0.22 to 0.98); hour of day is not uniform for `T1`/`T2`
  (p = 0.0026, the same rounds), `sx` (0.024) and `cz` (0.019), with counts peaking at
  20 to 23 UTC. Basis: `schedule.json`, 43 to 588 major rounds per family.
- **Order within a cycle.** Relative to each `T1` major round, the nearest major round of
  each family starts at a median of -1.71 h (`init_error`), -0.74 h (readout), -0.59 h
  (`measure_2`), +3 s (`T2`), +0.93 h (`sx`), +3.14 h (`cz`) and +4.25 h (`rzz`). `lf` is not
  locked to the cycle (median +3.05 h, interquartile range -4.93 h to +6.93 h). The cycle
  stretched over the months: the `cz` offset grew from 1.99 h (May) to 3.47 h (September).
- **A round is a few seconds of stamps in batches, and the batches have structure.** `sx`,
  `T2` and `xslow` batches never contain two coupled qubits (0 within-batch neighbour pairs
  against a permutation null mean of 5,657 for `sx`, 132 rounds); readout, `init_error`,
  `measure_2` and `T1` batches follow qubit index order (133 of 133 `T1` rounds); `cz` and
  `rzz` stamp groups contain couplers sharing a qubit (554 `cz` batches), so they are not
  IBM's documented isolation batches. Basis: `batches.json`.
- **Coverage changed, and so did the visible readout cadence.** Files per day rose from 9.2 (May) to 22.8
  (September); historical files start 2026-08-05 (443 in all). Over the same months readout
  major rounds per day fell from 5.62 to 3.67. Any event-rate comparison across months is
  confounded by both. Basis: `documents.json`.
- **`last_update_date` is not, in general, a measurement time.** It equals the newest measured stamp in
  only 0.195 of files (median 0.98 h later), while every `zz` and `measure.threshold` stamp
  equals it in every file. `lf` stamps are later than it in 217 of 1,760 files, and in 49 of
  the 60 live late files that the ledger can check, the `lf` stamp is later than the poll
  that filed the document (by up to 3.49 h). Basis: `documents.json`, `layer_fidelity.json`.
- **States are qubit-record states, and `is_new_state` marks filing order.** 760 states;
  0 of 998 consecutive same-state file pairs differ in any qubit value, 0 of 759 different-
  state pairs lack a difference; 314 same-state pairs change a gate, `lf`, `zz` or threshold
  value. In 79 states the flag sits on a later, mostly live file while the first file in
  time is historical. Basis: `states.json`.
- **Configuration and target.** `backend_version` is `1.3.37` in all files; four target
  sets. 31 historical files dated 2026-09-09T08:43 to 09-10T18:33 already carry the
  2,224-operation target that live files show only from 09-10T19:20, 27 of them without any
  `xslow` record, so a historical file's target is not a reliably dated event. The key
  `mcps` appears on 2026-07-16 (absent from 496 earlier live files). Basis: `documents.json`.
- **Change points line up with known events about as often as chance predicts, with one
  clear exception.** PELT at the most conservative penalty finds 17 points in 9 device-median
  series; 5 fall within 36 h of a known event against 3.29 expected by chance. The exception:
  readout's device median drops 0.138 decades 2.6 h after the 2026-06-08 readout-length
  change. An unexplained episode lifts `init_error` (+0.225 decades) from 2026-08-21 to
  08-31, with readout points on the same dates. `sx`, `cz` and `measure_2` have no point at
  that penalty. Basis: `changepoints.json`. **[Verification 2026-10-06: "clear exception"
  is too strong. The step reproduces (own device-median series: -0.105 to -0.116 decades,
  windows of 5 to 20 rounds), and T1, T2 and sx show no step there, but readout's largest
  10-round-window drop is -0.20 decades on 2026-05-17 with no known event, and 06-08/09 is
  also one of the schedule's restart dates; the 2.6 h proximity is suggestive, n = 1 event,
  and the second length change (07-30) shows no matching response.]**
- **No time-of-day or day-of-week seasonality in device medians.** Hour-of-day Kruskal-Wallis
  p is at least 0.196 for all 9 families; day of week has one p = 0.021 (`cz`) among the 18
  tests. Basis: `schedule.json`.
- **Permanent faults are qubit-centred and spatially concentrated.** The 6 permanently faulty couplers include 2 adjacent
  pairs (through `q72` and `q99`) against a null mean of 0.24 (p = 0.018); their 10-qubit
  footprint has a mean hop distance of 7.73 against a null median of 12.76, all at
  coordinate x of 8 or more. `measure_2`'s device-wide placeholder is its first two files,
  not a later glitch. Basis: `layout_faults.json`. **[Verification 2026-10-06: the adjacency
  result reproduces (exact null 0.238, p = 0.018), but the footprint null draws 10 random
  qubits, whereas the faults are 6 couplers whose endpoints are adjacent by construction. Drawing 6 random
  couplers gives a null median of 11.4 and p = 0.042 (one test, uncorrected); among draws
  that already have 2 adjacent pairs, p = 0.16. "Spatially concentrated" is weakened to
  suggestive; "the smallest of 2,000 draws" also did not reproduce with another seed (min
  7.62).]**
- **Layout: a heavy-hexagon graph.** 156 qubits, 176 couplers, degree 1/2/3 on 8/100/48
  qubits, bipartite (92 and 64, all 48 degree-3 qubits in one class), girth 12, cycle rank
  21, diameter 32, every coupler of coordinate length 1. Basis: `layout_faults.json`.
- **Layer fidelity.** 83 lf events (the first stamped 2026-05-10 and carried until the first
  in-archive event on 2026-07-01), median gap 26.5 h. `lf_100` median 0.545; EPLG(100) in
  IBM's average-gate form median 0.00489, rising with time (Spearman 0.456, p = 1.5e-5).
  59 distinct `lf_100` chains in 83 events; all 8,051 chains are simple paths of the
  coupling graph. Chains never use the four permanently `cz`-faulty couplers or `q72`, but
  use `102-103` while its `cz` error is a placeholder (278 chain instances) and the 88 ns
  coupler `146-147` (3,918). Basis: `layer_fidelity.json`.
- **Layered error exceeds the isolated-gate prediction by a factor of about 1.4.** `ln(lf_N)` over the
  sum of the chain's `ln(1 - 5/4 cz)` has medians from 1.36 to 1.41 across chain-length
  groups, flat in N; EPLG(100) over the chain's median `cz` error is 1.83. Over events,
  `lf_100` follows the prediction only weakly (Spearman 0.269, p = 0.019, n = 76). Basis:
  `layer_fidelity.json`.
- **`lf` has the same large non-persistent component as every family, and part of it is
  chain re-selection.** Lag-1 autocorrelation of log EPLG changes is -0.36 to -0.56 across
  N; the robust semivariance at about one day is 0.58 of the 744 to 1,488 h value for
  `lf_100` and 0.91 for `lf_10`; day-to-day changes of `ln(lf_100)` have a robust SD of 0.058
  when the chain changed and 0.030 when it did not. None of this attributes the component to
  estimation noise or to real fluctuations (section 4). **[Verification 2026-10-06: "part of
  it is chain re-selection" rests on 16 same-chain pairs; own recomputation gives 0.061 vs
  0.030, permutation p = 0.015 but Levene p = 0.070, so it is suggestive, not established.]**

## 1. The fields and how IBM produces them

### 1.1 What this scope owns

| Field or structure | Content | Where |
| --- | --- | --- |
| `file.last_update_ms` | `properties.last_update_date`; the files' order | cache |
| `file.timestamp_ms` | top-level `timestamp`; equal to `last_update_date` in all 1,760 files | cache |
| `file.has_configuration` | 1 for a live fetch, 0 for a historical fetch (`configuration: null`) | cache |
| `file.target_ops_id`, `file.n_target_ops` | which of the 4 target operation sets the file carries | cache, `meta.target_sets` |
| `file.config.<key>` | digest id of each of 43 configuration keys | cache, `meta.config_values` |
| `file.state_id`, `file.is_new_state` | qubit digest and flag from `health/state-index.tsv` | cache, `meta.state_digests` |
| `file.n_qubit_records`, `n_gate_records`, `n_general_records` | record counts per file | cache |
| `file.backend_version_id` | backend version | cache, `meta.backend_versions` |
| `meta.ledger` | 1,981 poll rows from 2026-09-02 (`poll_time_utc`, `last_update_date`, `decision`) | `meta.json` |
| `meta.collisions` | 2 collision files | `meta.json` |
| `meta.coupling_map`, `config_values.coords` | 352 directed edges; one coordinate pair per qubit | `meta.json` |
| `gen.lf`, `gen.lf_chain`, `meta.lf_chains` | `lf_4` to `lf_100`, the qubit chain of each, 6,524 distinct chains | cache |

### 1.2 How IBM describes its procedure

IBM's QPU information page (fetched 2026-10-06; vendor documentation that describes the
procedure as of that date, which may differ from May 2026) says, in paraphrase:

- the one-qubit errors (`id`, `sx`, `x`, `rx`) come from randomized benchmarking and are
  assumed equal, which matches the archive's identities (`results/data-layer/identities.json`);
- the two-qubit error is an average gate fidelity from randomized benchmarking measured in
  isolation, in batches whose edges are separated by at least two qubits; the `rzz` error is
  averaged over angles with a benchmarking variant for arbitrary unitaries;
- `T2` comes from a Hahn echo; readout error is the mean of the two assignment errors;
  initialization error is the excited population after the default repetition delay;
- properties update after the calibration sequence completes;
- layer fidelity is the process fidelity of a layered chain of N qubits; six 100-qubit chains,
  pre-selected for expected performance, are measured, and the value reported for N is the
  lowest error over the length-N sub-chains of those six; EPLG for N = 100 is
  `4/5 (1 - LF^(1/99))`.

McKay et al. 2023 (arXiv:2311.05933, in the 2026-10-05 survey §2.2; re-read in full on
2026-10-06) define the protocol behind `lf_N`: a chain's two-qubit gates are split into two
disjoint layers (even and odd edges), each layer is measured by simultaneous direct
randomized benchmarking, every component's decay is converted to a process fidelity
`F = (1 + (d^2 - 1) alpha) / d^2`, and LF is the product over all components of both layers
(their eqs. 1 to 2). `EPLG = 1 - LF^(1/n_2q)` with `n_2q = N - 1` for a linear chain (their
eq. 3); this is a process-error form, and IBM's page multiplies it by `d/(d+1) = 4/5` to
reach the average-gate-error form. LF of a sub-chain is computed from the measured
components, a gate that straddles the sub-chain boundary contributing `F^(1/2)`; `LF_N` is
defined as the maximum over N-qubit subsets, found in practice by a heuristic that seeds
candidate chains from isolated gate errors. Process error and average gate error are related
by `e_p = (d + 1)/d * e_g` (their Fig. 2 caption). Both definitions are used in section 7.

Nothing in a fetched source describes when IBM runs each experiment, how rounds are batched,
or what the per-record `date` stamps mean; every statement on those points below is an
inference from the data and is labelled so.

## 2. Profiles

### 2.1 Documents: cadence and provenance

| Month | Files | Live | Historical | Days covered | Files per day | Median gap (h) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05 | 171 | 171 | 0 | 18.5 | 9.25 | 2.25 |
| 2026-06 | 194 | 194 | 0 | 30 | 6.47 | 2.88 |
| 2026-07 | 270 | 270 | 0 | 31 | 8.71 | 2.17 |
| 2026-08 | 304 | 275 | 29 | 31 | 9.81 | 1.41 |
| 2026-09 | 683 | 334 | 349 | 30 | 22.77 | 0.77 |
| 2026-10 | 138 | 73 | 65 | 5.1 | 26.94 | 0.84 |

The consecutive-file gap has median 1.26 h over all files and 1.81 h between two live files;
the first historical file is `20260805T234531000000Z`. Fourteen gaps exceed 12 h, all between
two live files; the longest are 82.7 h (2026-08-07T03:21 to 08-10T14:02), 61.8 h (06-27 to
06-29), 58.6 h (08-14 to 08-17), 39.9 h (08-10 to 08-12) and 39.6 h (07-16 to 07-17). The
August ones fall inside the windows that `docs/implementations/2026-09-02-aug-gap-enumeration.md`
attributes to a stall in IBM's publication while the device kept recalibrating; this
document does not re-test that attribution.

**Ledger (from 2026-09-02T16:49:30Z only).** 1,981 rows at 629 distinct poll times. Decisions:
September `new` 685, `duplicate-partial` 535, `duplicate` 425, `collision` 9; October `new`
159, `duplicate-partial` 102, `duplicate` 65, `collision` 1. Polls per full day: median 21
(10% 6, 90% 26); poll interval median 0.57 h. A live file is first polled a median 0.61 h
after its `last_update_date` (max 1.89 h); a historical file a median 20.6 h after (max
765 h). All 814 files dated after the first poll have a `new` row. The workflow's own header
(`.github/workflows/calibration-poll.yml`) records why the poll rate before the four-cron
mitigation was lower (6.13 runs per day measured over the 15 days to 2026-09-10).

### 2.2 What the stamps are

| Check over all 1,760 files | Result |
| --- | --- |
| `last_update_date` equals the newest measured stamp (14 measured fields, placeholders masked) | 0.195 of files |
| `last_update_date` earlier than the newest measured stamp | 0 files |
| `last_update_date` minus the newest measured stamp | median 0.98 h, 90% 3.75 h, max 19.3 h |
| Placeholder stamp (`q72`'s `sx`, present in every file) later than `last_update_date` | every file; live median 0.083 h, 90% 0.19 h, max 12.4 h; historical median 0.063 h, max 0.42 h |
| Every `zz` stamp equals `last_update_date` | every file |
| Every `measure.threshold` stamp equals `last_update_date` | all 1,533 files that carry it |
| `lf` stamp later than `last_update_date` | 217 files (section 6.2) |

Reading (interpretation): `last_update_date` behaves like the time a document version was
assembled, which the assembly-stamped fields copy; it coincides with the newest measurement in
the file in only 0.195 of files. The placeholder records carry a second, slightly later
assembly-like stamp. What
`last_update_date` is internally is not identified by these checks.

### 2.3 Configuration, target and record counts as dated events

| Date (first file) | Event | Files |
| --- | --- | --- |
| 2026-05-13 | `backend_version` `1.3.37`, `schema_version` `1.0.0` | all 1,760 |
| 2026-05-13 | `coords`, `coupling_map` one distinct value | all 1,317 live |
| 2026-06-08T18:56:28Z | `readout_length` 1,560 to 1,700 ns and `reset` 1,584 to 1,724 ns on all 156 qubits | value event |
| 2026-06-24T16:36:39Z | `clops_v` serialised as JSON null instead of the string `"None"` | 333 before, 984 after |
| 2026-07-16T03:00:13Z | key `mcps` (value 3,864) appears | absent from 496 earlier live files |
| 2026-07-30T21:09:17Z | `readout_length` 1,700 to 1,660 ns, `reset` 1,724 to 1,684 ns, all 156 qubits | value event |
| 2026-08-07T03:21:59Z | target set 1 (1,600 ops, `+ measure_2`); `instruction_signatures` names `measure_2` | 222 live, 19 historical |
| 2026-09-02T04:56:24Z | target set 2 (2,068 ops, `+ measure_reset`, `measure_reset_2`, `reset_2`) | 53 live, 0 historical |
| 2026-09-03T19:41:06Z | `instruction_signatures` version 4 (same four names, new content) | 393 live |
| 2026-09-05T17:51:36Z | `cz` length 68 to 84 ns on `71-72` and `72-73` (4 directed columns) | value event |
| 2026-09-10T16:56:21Z | `xslow` records return (`n_gate_records` 2,576) | from this file |
| 2026-09-10T19:20:51Z | `basis_gates` gains `xslow`; first live file with target set 3 (2,224 ops) | 350 live |

Target sets by provenance: set 0 live 692 files (05-13 to 08-06), historical 10 (08-05 to
08-06); set 1 live 222 (08-07 to 09-01), historical 19 (08-12 to 08-17); set 2 live 53, no
historical file; set 3 live 350 (from 09-10T19:20), historical 414 (from 09-09T08:43). Record
counts per file follow the schema: `n_qubit_records` 934 (36 files, to 05-16), 935 (633, to
08-03), 1,050 (194, 08-04 to 08-22) and 1,051 (897); `n_gate_records` 1,796, 1,952, 2,420 and
2,576; `n_general_records` 449 in every file (176 `jq`, 176 `zz`, 97 `lf`).

### 2.4 States

| Item | Value |
| --- | --- |
| Distinct states | 760, in 760 runs; no state recurs after another state |
| Files per state | median 2 (min 1, 90% 5, max 14); 366 states have one file |
| `is_new_state = 1` | 760 files, one per state |
| File without a state row | `20260630T214008000000Z`: its qubit values equal both neighbours', which are in state 251 |

### 2.5 Layer fidelity

`gen.lf` is present for all 97 names in every file, with one stamp shared by all names in a
file and no value or chain change without a stamp change (`layer_fidelity.json` cadence).

| N | `lf_N` median (10%, 90%) | EPLG average form, median (10%, 90%) |
| --- | --- | --- |
| 4 | 0.9876 (0.9862, 0.9893) | 0.00332 (0.00286, 0.00369) |
| 10 | 0.9624 (0.9587, 0.9660) | 0.00340 (0.00307, 0.00374) |
| 20 | 0.9152 (0.9072, 0.9218) | 0.00372 (0.00342, 0.00409) |
| 50 | 0.7692 (0.7524, 0.7925) | 0.00427 (0.00379, 0.00463) |
| 80 | 0.6295 (0.5973, 0.6614) | 0.00467 (0.00418, 0.00520) |
| 100 | 0.5449 (0.5069, 0.5809) | 0.00489 (0.00438, 0.00547) |

Over 83 events. `lf_N` never increases with N inside an event (83 of 83), as a maximum over
sub-chains must. EPLG grows with N, as McKay et al. also report; a plausible reading is that
the best short chains can avoid the worse gates, which long chains cannot (interpretation).
The `lf_100` range is 0.432 to 0.606; EPLG(100) average form 0.00404 to 0.00675.
For scale only: McKay et al. report a process-form EPLG(100) of 1.2e-2 on a different Heron
device in 2023 (existing survey §2.2); the forms differ by the factor 5/4.

## 3. Temporal structure

### 3.1 The schedule

A round is a maximal run of a family's event stamps with no gap above 15 min; a **major
round** re-measures at least half of the family's entities. Minor rounds are few and small
(`T1` 5 rounds of at most 12 qubits, `sx` 3 of at most 4, `cz` 2 of at most 2 couplers);
`init_error`'s 66 minor rounds reach 70 qubits because its major rounds cover only about
0.62 of the device.

| Family | Major rounds | Coverage, median | Duration (s), median | Gap (h), median (10%, 90%) | Daily shift (h) | Hour-of-day p | Day-of-week p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| readout | 588 of 597 | 0.987 | 0 (90%: 32) | 4.44 (2.54, 10.18) | n/a | 0.523 | 0.224 |
| `init_error` | 236 of 302 | 0.622 | 0 | 4.73 (1.62, 11.23) | n/a | 0.132 | 0.785 |
| `measure_2` | 52 | 0.978 | 3 | 24.66 (21.06, 28.15) | 0.67 | not tested | 0.984 |
| `T1` | 133 of 138 | 0.962 | 3 | 24.71 (19.21, 30.52) | 0.73 | 0.0026 | 0.866 |
| `T2` | 133 of 135 | 0.987 | 3 | 24.71 (19.21, 30.52) | 0.73 | 0.0026 | 0.866 |
| `sx` | 132 of 135 | 0.974 | 4 | 24.90 (19.95, 30.55) | 0.89 | 0.024 | 0.820 |
| `xslow` | 43 of 45 | 0.974 | 3 | 25.03 (19.27, 27.06) | 1.07 | not tested | 0.800 |
| `cz` | 130 of 132 | 0.960 | 4 | 25.13 (19.01, 35.79) | 1.11 | 0.019 | 0.795 |
| `rzz` | 109 of 110 | 0.938 | 4 | 25.30 (20.64, 49.71) | 1.16 | not tested | 0.980 |
| `lf` | 82 | 1 | 0 | 26.53 (26.06, 31.50) | 2.43 | not tested | 0.979 |

"Daily shift" is the median of (gap minus 24 h) over gaps between 20 h and 30 h; "not tested"
means fewer than five rounds expected per hour bin. `T1` and `T2` share their rounds (`T2`
stamps follow `T1`'s by seconds, section 3.3), so their tests are one test.

**Reading.** The daily families run on a cycle of about 24.7 to 25.3 h, so a round starts
0.7 to 1.2 h later each day and drifts through every hour. Restarts bring it back: `T1`, `sx`
and `cz` all have a gap below 20 h on or about 2026-05-13/14, 05-15, 05-16/17, 05-19, 05-29,
06-08/09, 07-24, 08-28, 09-15 and 09-22 (lists in `schedule.json`
`short_gaps_below_20h`). The hour-of-day counts of `T1` major rounds peak in the 20 to 23 UTC
bins (12, 14, 9 and 11 of 133), which is where the cycle sits after several restarts; that is
the most likely source of the non-uniform hour p-values (interpretation). `lf` runs on its own
longer cycle (26.5 h, 2.43 h later per day) and is not part of the daily sequence.

Long gaps (above 36 h) in the daily families are dated in `schedule.json`. Most coincide with
file gaps (2026-06-26 to 06-29, 08-06 to 08-10, 08-14 to 08-16); two do not: `rzz` was not
re-measured device-wide from 2026-08-19T23:02 to 08-31T14:50 (279.8 h) while the other
families were, and `xslow` was absent from 2026-05-29 to 09-09 (2,477.8 h, a schema gap).

### 3.2 Order of families within the cycle

| Family | Anchors matched (of 133 `T1` rounds) | Offset from `T1` (h): median (25%, 75%) | Share after `T1` | May median | September median |
| --- | --- | --- | --- | --- | --- |
| `init_error` | 56 | -1.71 (-2.71, +1.47) | 0.43 | n/a | -2.07 |
| readout | 132 | -0.74 (-1.10, -0.41) | 0.14 | -0.40 | -1.10 |
| `measure_2` | 51 | -0.59 (-0.68, -0.51) | 0 | n/a | -0.64 |
| `T2` | 133 | +0.0008 (3 s) | 1 | +0.0008 | +0.0008 |
| `sx` | 129 | +0.93 (+0.76, +1.77) | 0.95 | +0.68 | +0.98 |
| `xslow` | 45 | +0.93 (+0.68, +1.78) | 0.98 | +0.68 | +0.98 |
| `lf` | 80 | +3.05 (-4.93, +6.93) | 0.56 | n/a | +4.10 |
| `cz` | 120 | +3.14 (+1.95, +4.17) | 0.88 | +1.99 | +3.47 |
| `rzz` | 107 | +4.25 (+3.00, +6.19) | 0.88 | +3.08 | +5.06 |

Matching: the nearest major round of the family within 12 h of each `T1` major round.
Readout and `init_error` run several times a day, so their "nearest round" is a looser
notion; the tight readout spread (25% to 75%: -1.10 h to -0.41 h) is still consistent with one
readout round belonging to the daily sequence just before `measure_2` and `T1`
(interpretation). The sequence lengthened from May to September for every family behind
`T1` (`sx`, `cz`, `rzz`), which is a schedule change over the five months. The order
(readout and `measure_2`, then `T1`/`T2`, then `sx`, then two-qubit gates) resembles a
dependency order of the kind Kelly et al. 2018 describe for calibration graphs (architecture
survey §8, arXiv:1803.03226), but nothing here shows that IBM uses such a graph.

### 3.3 Batches inside a round

| Family | Batches per round, median (90%) | Entities per batch, median | Spacing between batches (s), median | Rounds whose batches follow index order | Within-batch coupled pairs: observed / null mean |
| --- | --- | --- | --- | --- | --- |
| readout | 1 (32.4) | 4 | 1 | 120 of 122 | 12,427 / 1,436 |
| `init_error` | 1 (9.6) | 6 | 1 | 97 of 97 | 4,514 / 873 |
| `measure_2` | 4 (5) | 40 | 1 | 52 of 52 | 8,003 / 2,247 |
| `T1` | 4 (5) | 38 | 1 | 133 of 133 | 19,602 / 5,494 |
| `T2` | 4 (5) | 41 | 1 | 0 of 133 | **0** / 5,852 |
| `sx` | 5 (5) | 40.5 | 1 | 0 of 132 | **0** / 5,657 |
| `xslow` | 4 (5) | 41 | 1 | 0 of 43 | **0** / 1,865 |
| `cz` | 5 (6) | 36 | 1 | 0 of 130 | sharing a qubit 4,847 / 5,988 |
| `rzz` | 5 (6) | 35 | 1 | 0 of 109 | sharing a qubit 3,810 / 4,826 |

A batch is the set of entities sharing one exact stamp inside a round. The null permutes batch
labels inside each round with batch sizes kept, 200 permutations (seed 20261006), over rounds
with at least 20 entities, at least 2 batches and one event per entity. For couplers, the
distance is between nearest endpoints (0 = share a qubit).

- **`sx`, `T2`, `xslow`: independent sets.** No batch ever holds two coupled qubits; the
  smallest within-batch distance is exactly 2 in every one of the 606 `sx` batches tested.
  Most batches lie inside one class of the graph's 2-colouring (median purity 1.0, 10%
  0.72). The partition changes between rounds (median Rand index 0.77 for `sx`, never
  identical).
- **Readout, `init_error`, `measure_2`, `T1`: index order.** Their batches are consecutive
  runs of qubit indices, about 40 per second, so their apparent spatial clustering is only
  index order (neighbouring indices are mostly coupled along a row). At least three quarters
  of readout rounds carry a single stamp for all qubits (75% quantile of batches per round
  is 1).
- **`cz`, `rzz`: not isolation batches.** Stamp groups contain fewer close pairs than chance
  (p = 0.005 at distances 0 to 2) but still hundreds of qubit-sharing pairs, and the minimum
  within-batch distance is 0 in 554 `cz` batches. IBM's isolation batches (section 1.2)
  would contain none, so a stamp group is not one isolation batch; whether it is a union of
  several cannot be told from the stamps.
- **`T1` and `T2`.** In all 19,747 same-qubit pairs inside one round, the `T2` stamp is later
  than the `T1` stamp (median 4 s, max 112 s); 132 stamps are shared by both families.

Interpretation, labelled: a whole device's batches are stamped within 3 to 5 s, which is
short for a device-wide benchmarking experiment, so the stamps look like the times results
were written rather than the times qubits were measured. The independent-set structure of `sx`
and `T2` is what one would expect if those experiments run simultaneously on non-adjacent
qubits, the arrangement simultaneous randomized benchmarking uses to avoid crosstalk between
neighbours (Gambetta et al. 2012, fetched 2026-10-06); this is not confirmed by any IBM
source.

### 3.4 Coverage and visible event rates

| Month | Readout major rounds per day | Readout gaps above 6.5 h | `T1` rounds per day | `rzz` rounds per day |
| --- | --- | --- | --- | --- |
| 2026-05 | 5.62 | 0.155 | 1.14 | 1.08 |
| 2026-06 | 4.43 | 0.212 | 0.93 | 0.80 |
| 2026-07 | 4.16 | 0.211 | 0.81 | 0.74 |
| 2026-08 | 3.06 | 0.340 | 0.81 | 0.48 |
| 2026-09 | 3.67 | 0.376 | 1.00 | 0.77 |
| 2026-10 | 3.32 | 0.500 | 0.78 | 0.78 |

Readout is the family most exposed to lost rounds (it can change between two captured
documents), yet its visible rate fell while files per day more than doubled. The
fall is therefore at least partly a change in what IBM runs or publishes, not only coverage
(interpretation). The consequences for every event-rate statistic: (a) a readout rate or gap
distribution differs by month for two reasons that the archive cannot fully separate before
September; (b) the daily families lose a round only when no document is captured for a whole
cycle, which happens in the long gaps of section 2.1; (c) August mixes the publication stall
with the start of historical files.

### 3.5 Device-wide change points

**Method.** One point per major round: the median over re-measured entities of
`log10(value)`; for `lf`, `log10` of the process-form EPLG(100) per in-archive event. PELT
(Killick, Fearnhead and Eckley 2012, fetched 2026-10-06) for changes in the mean, squared-error
cost, minimum segment of 3 points, penalty `c sigma^2 ln n` with `sigma` the robust noise scale
from first differences, `c` = 2, 4 and 8; binary segmentation with the same cost and penalty
as a check. A point is "matched" if within 36 h of one of ten known events (readout-length
changes, schema starts, `mcps`, `clops_v`, first historical file, the `q72` length change,
the `xslow` gaps); 0.193 of the archive's 145.6-day span lies within 36 h of some known
event, which gives the number expected by chance.

| Penalty | Points (9 value series) | Matched | Expected by chance |
| --- | --- | --- | --- |
| c = 2 | 46 | 11 | 8.89 |
| c = 4 | 26 | 9 | 5.03 |
| c = 8 | 17 | 5 | 3.29 |

Points at c = 8:

| Series | Point | Shift (decades) | Nearest known event |
| --- | --- | --- | --- |
| readout | 2026-05-17T13:53 | -0.187 | none within 36 h |
| readout | 2026-05-27T15:37 | -0.068 | none within 36 h |
| readout | **2026-06-08T21:31** | **-0.138** | readout length 1,560 to 1,700 ns, 2.6 h earlier |
| readout | 2026-08-21T06:06 | +0.051 | none within 36 h |
| `init_error` | 2026-08-21T06:06 | +0.225 | none within 36 h |
| `init_error` | 2026-08-26T18:37 | +0.078 | none within 36 h |
| `init_error` | 2026-08-31T16:56 | -0.300 | none within 36 h (36.0 h from 09-02) |
| `T1` | 2026-05-15T22:25 | -0.164 | none within 36 h |
| `T1` | 2026-05-28T06:03 | +0.145 | `xslow` disappears, 34.7 h later (matched by the rule) |
| `T1` | 2026-06-29T14:55 | -0.043 | none within 36 h |
| `T2` | 2026-05-19T02:22 | -0.107 | none within 36 h |
| `T2` | 2026-05-23T23:59 | +0.153 | none within 36 h |
| `T2` | 2026-07-17T18:33 | -0.028 | none within 36 h |
| `rzz` | 2026-05-30, 07-15, 08-01 | -0.027, +0.037, -0.025 | each within 36 h of an event; binary segmentation finds none at c = 8 |
| `lf` EPLG(100) | 2026-07-11T18:19 | +0.056 | none within 36 h |

`sx`, `cz` and `measure_2` have no point at c = 8 (`sx` one at c = 4, `cz` two). Readout's
segment medians at c = 8 are -1.663, -1.850, -1.918, -2.056 and -2.005 decades: most of the
fall happened in May and June. The second readout-length change (2026-07-30) has no point even
at c = 2.

**Reading.** Overall, alignment with known events is close to chance at every penalty. The
readout drop after the 2026-06-08 length change is the one specific coincidence (a longer
readout pulse and a lower readout error in the same hours); it is consistent with a physical
link but is one event. The late-August episode is real in the device medians (`init_error`
up by 0.225 then down by 0.300 decades at c = 8; at c = 2 readout has points on 08-21, 08-27
and 08-31 too) and matches no event in the archive. The many points in the first two weeks
of the archive (May) coincide with the schedule's most frequent restarts (section 3.1), which
is a coincidence in time, not a demonstrated cause. On the coverage series, files per day
change on 2026-08-07, 08-12, 08-27, 09-10, 09-22, 09-25 and 10-04 and readout rounds per day
on 2026-06-15 (from 6 to 4 per day, segment medians). One value-series point at c = 8 lies
within a day of a coverage change point (`init_error` 2026-08-26T18:37 against files per day
from 2026-08-27); the others do not.

### 3.6 Seasonality of the values

Per major round, the device median minus a centred rolling median over plus or minus 7
rounds, grouped into four 6 h bins of the round's start hour and into days of the week
(Kruskal-Wallis):

| Family | Rounds | Hour p | Day-of-week p | Residual MAD (decades) |
| --- | --- | --- | --- | --- |
| readout | 588 | 0.505 | 0.404 | 0.0123 |
| `init_error` | 236 | 0.499 | 0.257 | 0.0307 |
| `measure_2` | 52 | 0.457 | 0.863 | 0.0187 |
| `T1` | 133 | 0.578 | 0.958 | 0.0184 |
| `T2` | 133 | 0.196 | 0.666 | 0.0180 |
| `sx` | 132 | 0.940 | 0.749 | 0.0107 |
| `xslow` | 43 | 0.333 | 0.857 | 0.0145 |
| `cz` | 130 | 0.818 | 0.021 | 0.0056 |
| `rzz` | 109 | 0.476 | 0.544 | 0.0070 |

Eighteen tests; one p below 0.05, about what chance gives. The rolling median removes the
slow level, and the cycle's walk around the clock spreads each hour bin over many dates, so an
hour-of-day effect would not be a disguised slow drift (an argument from the design, not a
measured property). There is no evidence of a time-of-day or day-of-week
pattern in device-wide values. This is a device-median test: it cannot see a pattern local
to a few entities.

### 3.7 Layer fidelity over time

EPLG(100) rises over the in-archive period: Spearman with time 0.456 (p = 1.5e-5, n = 83), **[Verification 2026-10-06: n = 83 includes the carried-in 2026-05-10 event; the in-archive 82 events give 0.463, p = 1.2e-5; the conclusion is unchanged]**
first-half median 0.00481 and second-half median 0.00509 (average form). PELT at c = 8 places
one step, +0.056 decades on 2026-07-11; at c = 2 and 4 it finds four points instead,
2026-07-07 (+0.054), 08-06 (+0.080), 08-13 (-0.083) and 08-31 (+0.033). The cadence gaps above 48 h are the carried-in start
(1,239 h, from the 2026-05-10 stamp to 2026-07-01), 2026-07-19 to 07-21 (52.8 h), 08-06 to
08-10 (83.2 h) and 08-14 to 08-17 (57.0 h).

## 4. The non-persistent component: what the schedule and `lf` can and cannot tell

**What the schedule sets.** The shortest lag any variogram can show is the cycle of the
family: about one day for the daily families (median gaps 24.7 to 25.3 h) and about 4.4 h for
readout. Within a round the stamps are seconds apart and arranged by write order or
independent sets (section 3.3), so they carry no timing information below the round. Any
real fluctuation faster than one cycle is therefore aliased into the nugget, exactly as
`01-data-layer.md` §7 states. The cycle's walk around the clock is useful here: a diurnal
driver common to the device (temperature, building load) would appear as an hour-of-day
dependence of device medians, and none appears (section 3.6). That is evidence against a
strong device-wide diurnal component; it says nothing about local, unsynchronised fluctuations
such as TLS switching, which the 2026-10-05 findings (P6) also found no device-wide trace of.

**`lf` variograms** (`log10` of the process-form EPLG per name, all 83 events, pairs binned by
the time between lf stamps):

| Lag bin (h) | Pairs | `lf_100` classical | `lf_100` robust | `lf_50` robust | `lf_10` robust |
| --- | --- | --- | --- | --- | --- |
| 18 to 30 | 71 | 0.00138 | 0.00096 | 0.00065 | 0.00114 |
| 30 to 42 | 6 | 0.00091 | 0.00052 | 0.00046 | 0.00047 |
| 42 to 54 | 49 | 0.00112 | 0.00072 | 0.00113 | 0.00099 |
| 54 to 84 | 85 | 0.00115 | 0.00091 | 0.00086 | 0.00098 |
| 84 to 132 | 114 | 0.00100 | 0.00098 | 0.00071 | 0.00113 |
| 132 to 204 | 192 | 0.00147 | 0.00131 | 0.00083 | 0.00113 |
| 204 to 372 | 416 | 0.00157 | 0.00136 | 0.00102 | 0.00125 |
| 372 to 744 | 793 | 0.00159 | 0.00135 | 0.00093 | 0.00117 |
| 744 to 1,488 | 1,115 | 0.00169 | 0.00166 | 0.00117 | 0.00126 |
| 1,488 to 3,624 | 562 | 0.00218 | 0.00236 | 0.00177 | 0.00136 |

Nugget ratio (18 to 30 h bin over 744 to 1,488 h bin): `lf_100` 0.82 classical and 0.58
robust; `lf_50` 0.65 and 0.55; `lf_10` 0.94 and 0.91; all 97 names pooled 0.78 and 0.68 (the
pooled curve over-counts, since names share events and overlapping chains). The last bin
includes the pairs with the carried-in 2026-05-10 event. Lag-1 autocorrelation of changes of
log EPLG: -0.49 (`lf_4`), -0.54 (`lf_10`), -0.48 (`lf_20`), -0.41 (`lf_50`), -0.44 (`lf_80`),
-0.56 (`lf_100`), inside the -0.42 to -0.50 range of the gate and coherence families
reported in the 2026-10-05 findings (P2), given 83 events per series.

**What these show.** `lf_10` is close to a flat curve: a fixed level plus a component that is
as large at one day as at a month. `lf_100` adds a part that grows over weeks to months, the
upward trend of section 3.7, on top of a nugget that is still more than half of the month-scale
semivariance. A pure estimation-noise model and a model of real fluctuations faster than one
day both predict this flat nugget; the variogram cannot tell them apart.

**What is specific to `lf`.** An `lf_N` value is a product of many fitted decays (for a
measured linear chain, N - 1 gate pairs and two idle end qubits), and its chain is
re-selected at nearly every event (59 distinct `lf_100` chains in 83 events, section 7.1).
Re-selection adds variance that is neither
estimation noise nor fluctuation of a fixed set of gates: the robust SD of day-to-day changes
in `ln(lf_100)` is 0.058 when the chain changed (66 consecutive pairs) and 0.030 when it did
not (16 pairs). On the 15 same-chain pairs, the absolute change of `ln(lf_100)` and of the isolated
prediction `ln(pred_100)` do not differ (Wilcoxon p = 0.52; 8 of 15 smaller for `lf`), so
this archive cannot say whether isolated `cz` estimates are noisier than the layered
measurement of the same gates.

**What would settle it.** Repeated layer-fidelity measurements of one fixed chain at short
intervals (minutes to hours), with the per-component fit uncertainties, would separate fit
variance (which shrinks with more sequences) from gate fluctuations (which do not); IBM does
not publish either. The per-edge layered fidelities, if published, would allow the same test
per coupler.

## 5. Spatial structure

### 5.1 The frame

| Property | Value |
| --- | --- |
| Qubits, couplers, directed edges | 156, 176, 352 |
| Degree 1 / 2 / 3 | 8 / 100 / 48 |
| Connected; diameter; mean hop distance | yes; 32; 12.64 (median 12) |
| Bipartite; class sizes | yes; 92 and 64, with all 48 degree-3 qubits in the class of 64 |
| Girth (shortest cycle); cycle rank (couplers minus qubits plus one) | 12; 21 |
| Coordinates | x from 1 to 16, 15 rows alternating 16 and 4 qubits; every coupler has coordinate length 1 |
| Degree-3 qubits per row | 3, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 3 |
| `coords` and `coupling_map` | one distinct value each over all live files |

This is consistent with a heavy-hexagon lattice in the sense of Chamberland et al. 2020
(fetched 2026-10-06):
qubits of degree two and three, chosen to limit frequency collisions and crosstalk. Girth 12
with 21 independent cycles is consistent with a patch of twelve-qubit rings (the ring count
itself was not enumerated). Every spatial statement in this
deep dive should use these hop distances (`device_common.distances`) and the bipartition.

### 5.2 Faults on the map

The permanently faulty couplers (`cz` or `rzz` at the placeholder in every file) are 27-28,
32-33, 71-72, 72-73, 95-99 and 99-115. Two pairs among them share a qubit (`q72`, `q99`)
against a null mean of 0.24 adjacent pairs for 6 couplers drawn at random from the 176
(p = 0.018, 20,000 draws). For all 16 couplers ever at a placeholder or at `zz = 0`, 6
adjacent pairs against 1.91 (p = 0.0069). The footprint of the permanent faults (qubits 27,
28, 32, 33, 71, 72, 73, 95, 99, 115) has a mean hop distance of 7.73, below the smallest of
2,000 random 10-qubit draws (null median 12.76, minimum 7.8); its coordinates all have x of
8 or more, in rows 3, 7 and 9 to 11. **[Verification 2026-10-06: wrong null for the footprint (random qubits instead of random couplers); coupler-based p = 0.042, and 0.16 given the adjacent pairs; see the Verification section.]** Reading (interpretation): faults are centred on qubits
(`q72`: its `sx`, both couplers, `T2`; `q99`: both `rzz` couplers) and on one half of the
chip. With 6 to 16 entities the tests have little power and the p-values are only
indicative.

### 5.3 Where `lf` chains go

Each qubit's share of the 83 `lf_100` chains: median 0.729 for degree-2 qubits, 0.880 for
degree-3 qubits (Mann-Whitney p = 2.7e-7) and 0.048 for degree-1 qubits (a path can only end
there). By coordinate half, x of 8 or less 0.570, x above 8 0.712; by row, from 0.465 (row 3)
to 0.825 (row 14). Four qubits are never in an `lf_100` chain, `q28`, `q32`, `q64` and `q72`
(all degree 2): three sit on permanently faulty couplers; `q64`'s two couplers (63-64,
64-65) are never used by any `lf_100` chain, for no reason visible in the placeholder data.
Eight couplers are never used: 72-73, 71-72, 31-32, 27-28, 64-65, 28-29, 63-64, 32-33.

### 5.4 Batches as spatial structure

The `sx`, `T2` and `xslow` batch structure of section 3.3 is spatial: each batch is an
independent set of the graph, mostly inside one bipartition class. This matters for any
analysis that compares entities by stamp: same-stamp qubits are never neighbours.

## 6. Faults and data quality

### 6.1 The fault map across families

| Family | Ever at fault | In every file | Entries (real to fault) | Notes |
| --- | --- | --- | --- | --- |
| `sx` (placeholder) | 3 | `q72` | 1 (`q17`, 2026-06-22) | `q17` 0.119 of files, last 2026-07-13; `q149` only in the first files (to 2026-05-13T21:57) |
| `xslow` | 2 | `q72` | 0 | `q17` 0.049 of files |
| `measure_2` | 156 | none | 0 | all 156 at the placeholder in its first two files only (2026-08-07T03:21 and 08-10T14:02, the two ends of the 82.7 h gap); none after |
| `cz` | 7 | 27-28, 32-33, 71-72, 72-73 | 2 | `102-103` 0.888 of files from the start to 2026-09-29; `149-150` 05-19 to 05-27; `148-149` 05-28 to 05-29 |
| `rzz` | 13 | 32-33, 71-72, 72-73, 95-99, 99-115 | 13 | `27-28` 0.956, `102-103` 0.339, `17-27` 0.276, `7-17` 0.236; five couplers enter in one file (`20260903T004128000000Z`); at most 11 at fault at once (files of 2026-09-03 and 09-04) |
| `zz = 0` | 4 | 32-33 | 0 | 39-53, 13-14 and 109-118 exactly 0 from the first file to 2026-07-10T05:17, then real |
| `T1` absent | 1 qubit | none | | `q72` in 36 files (to 2026-05-16) |
| `T2` absent | 1 qubit | `q72` | | all 1,760 files |

The 2026-10-05 findings (P7) counted `measure_2`'s 156 entries as one device-wide glitch; at
this ref and with entries counted only after a real value, it is the field's schema start in
the placeholder state. Per-family consequences belong to documents 04 and 05.

### 6.2 Data-quality findings of this scope

1. **`lf` stamps and poll times disagree.** `lf` stamps are later than `last_update_date`
   in 217 files (156 live, 61 historical; July 51, August 48, September 98, October 20), by a
   median 1.96 h and at most 6.43 h; 73 of the 83 events appear first in such a file, and
   206 of the 217 stamps are also later than the file's placeholder stamp. For the 60 live
   late files filed after the ledger began, the poll that filed the document (`new` row)
   precedes the `lf` stamp in 49, by up to 3.49 h (median -1.34 h). An archived live copy is
   never overwritten (ADR-025 in `docs/decisions.md`), so either the `lf` stamp is not a UTC
   time at or before the measurement (for example an offset error in the source string; **[Verification 2026-10-06: a constant offset is not supported, since `lf` stamp minus `last_update_date` has median -13.0 h over all files and is positive only in 217, with lag from 0.01 h to 6.4 h; the example is speculation]**), or
   the archived copy is not the payload of that poll. This cannot be settled from the cache:
   the raw `date` strings are not stored. Until it is, an `lf` stamp should not be used to
   order `lf` against other fields at the hour scale.
2. **`last_update_date` is not, in general, a measurement time** (section 2.2). Ordering
   files by it is safe; using it as "the time of the features" is not.
3. **`is_new_state` marks filing order, not document time.** In 79 states the flag is not on
   the first file in time; in all 79 the first file is historical and the flagged file is
   later (73 live), by a median 0.69 h and at most 4.63 h. No state has zero or two flags.
4. **`state_id` numbering follows the state index's row order**, which has 38 inversions
   against time; only equality of ids is meaningful.
5. **A historical file's target is not dated at day resolution** (section 2.3): 31
   historical files precede the first live 2,224-operation file by up to 1.5 days, and 27 of
   them carry `xslow` operations with no `xslow` record.
6. **A configuration key appears mid-archive.** `mcps` is absent from 496 live files before
   2026-07-16T03:00:13Z; `01-data-layer.md` §6 lists the other 38 keys as constant and does
   not name it.
7. **Carried-in values.** Every family's first event per entity can be a value measured
   before the archive starts (`lf`: 2026-05-10); the
   schedule, batch and change-point scripts drop events stamped before the first file (156
   readout, 155 `T1`, 155 `T2`, 153 `sx`, 171 `cz`, 167 `rzz`, 97 `lf` records).
8. **Coupler directions.** For non-placeholder records the two directions of a coupler carry
   identical values and dates in all 301,078 `cz` and 297,365 `rzz` record pairs; the 8,682
   and 12,395 direction date mismatches of `01-data-layer.md` §5 are all placeholder records.
   One direction per coupler is therefore lossless for events.

## 7. Relationships

### 7.1 Inside the scope

- **Schedule, coverage and event rates** (section 3.4): the visible cadence of readout is a
  product of IBM's schedule and the archive's capture, and both moved.
- **States and qubit fields** (section 2.4): a state change is exactly a change of at least
  one qubit-record value; gate, `lf`, `zz` and threshold changes inside a state are invisible
  to the digest (63 `sx`, 78 `cz`, 55 `rzz`, 17 `measure_2`, 28 `xslow`, 34 `lf`, 59 `zz`,
  60 threshold changes among the 998 same-state pairs).
- **Target, records and configuration**: the target sets, `n_gate_records` and
  `instruction_signatures` change together at the schema starts of 2026-08-07 and 09-02 in
  live files (section 2.3), with two exceptions: `instruction_signatures` changes content
  again on 09-03 with no target change, and on 09-10 the `xslow` records (16:56:21Z) precede
  `basis_gates` and the live target (19:20:51Z).
- **`lf` chains and faults**: chains avoid the faulty qubit and the four permanently
  `cz`-faulty couplers, but not `102-103` (its `cz` error was a placeholder in the event file
  in all 278 chain instances that use it), and not the `rzz`-faulty 95-99 and 99-115 (4,548
  and 4,588 instances). So layer fidelity uses
  `cz`, not `rzz` (interpretation consistent with `cz` being Heron's basis gate), and a `cz`
  placeholder on `102-103` does not stop IBM from using that gate in a layer.
- **Chain structure.** All 8,051 chains are valid simple paths; 6,485 of 7,968 are subsets of
  the next longer chain of the same event; 3,920 of 8,051 are contiguous sub-paths of that
  event's `lf_100` chain. The number of maximal chains per event (chains not contained in a
  longer one) is 1 to 9, most often 3 (22 events) or 4 (19). Consecutive `lf_100` chains
  share a median Jaccard overlap of 0.639 of their qubits, and 16 consecutive pairs are
  identical. This is
  consistent with IBM's description (best sub-chains of several pre-selected 100-qubit chains)
  if the six chains are re-chosen at most runs; the six parent chains cannot be reconstructed
  from the reported maxima.

### 7.2 Assigned link: `lf_N` against its own chain's gate errors

For each lf event and name, `pred_N = prod_e (1 - 5/4 cz_e)` over the chain's N - 1 couplers,
with each coupler's latest `cz` re-measurement stamped at or before the lf stamp (age at the
lf stamp: median 10.9 h, 10% 1.8 h, 90% 26.7 h). 278 event-name pairs that include `102-103`
in placeholder state have no prediction and are skipped.

| Chain length N | `ln(lf_N) / ln(pred_N)`: median (25%, 75%) | Per-gate residual `(ln lf - ln pred)/(N - 1)`, median |
| --- | --- | --- |
| 4 to 10 | 1.39 (1.27, 1.52) | -0.00115 |
| 11 to 30 | 1.36 (1.25, 1.46) | -0.00121 |
| 31 to 60 | 1.39 (1.27, 1.49) | -0.00144 |
| 61 to 90 | 1.38 (1.28, 1.52) | -0.00161 |
| 91 to 100 | 1.41 (1.29, 1.50) | -0.00177 |

| Variant for `lf_100` | Median ratio (25%, 75%) | Spearman over events with `ln(lf_100)` |
| --- | --- | --- |
| `cz` before the lf stamp | 1.42 (1.31, 1.50) | 0.269 (p = 0.019, n = 76) |
| plus `1 - 3/2 sx` for the two end qubits | 1.42 (1.31, 1.49) | |
| first `cz` after the lf stamp | 1.39 (1.27, 1.49) | 0.355 (p = 0.0018, n = 75) |
| `rzz` instead of `cz` | 1.53 (1.32, 1.63) | 0.257 (p = 0.37, n = 14) |
| EPLG(100) over predicted EPLG(100), both average form | 1.42 (1.31, 1.50) | |
| EPLG(100) over the chain's median `cz` error | 1.83 (1.74, 1.94) | |

Shorter chains: Spearman 0.194 for `lf_50` (p = 0.085, n = 80) and 0.195 for `lf_10`
(p = 0.077, n = 83). The `rzz` variant has only 14 usable events because chains cross the
`rzz`-faulty couplers.

**Chain selection against isolated errors.** At each lf stamp, the `lf_100` chain's couplers
sit at a median percentile of 0.48 of all real couplers' current `cz` errors (25% 0.25, 75%
0.70); the chain's median `cz` is below the rest's in 72 of 83 events; a coupler's share of
`lf_100` chains correlates with its time-median `cz` error at Spearman -0.18 (p = 0.017,
n = 172). A 100-qubit path must use 100 of the 156 qubits, so it cannot consist of the best
couplers only.

**Reading.** In process-error terms (to first order, `-ln(1 - e)` is about `e`), a gate in a
layered chain fails about 1.4 times as often as its isolated benchmark predicts, and the ratio does not depend on chain length (N from 4
to 100). The excess combines crosstalk inside simultaneous layers, the idle errors of
qubits not in a gate in a layer (only the two chain ends here), any difference between the
layered and isolated fits, and the 10.9 h median age of the isolated value; the published
data cannot separate them. McKay et al. found the layered-minus-isolated gap much smaller on
a tunable-coupler Heron device than on a fixed-coupler Eagle device (existing survey §2.2;
paper Fig. 2), which is a qualitative statement about another device, not a prediction of
1.4. Over time the two only weakly co-move (0.27 to 0.36); with about 75 events the
difference between the "before" and "after" correlations is not tested here. That the ratio
is flat in N is mildly unexpected: a maximum over many short sub-chains should favour short
chains whose measured LF happened to come out high (a selection effect), which would lower
the ratio at small N; no such drop is visible.

## 8. Use cases and why each field matters

| Field or structure | In this project | In the literature | Why it matters |
| --- | --- | --- | --- |
| Record stamps and the schedule | Aligning "features at t" with a target at t + h (the M1 event table in `docs/roadmap/2026-10-05-feature-patterns-and-method.md` §6); horizons counted in rounds | Drift and variability studies use daily calibration records (survey §2.1) | `last_update_date` is not a measurement time, and the cycle is not 24 h, so "daily" and "hourly" are approximations whose error is measured here |
| `has_configuration`, ledger, `duplicate-partial` | Provenance of every file; coverage by month | n/a | Event rates and cadences differ by month for reasons of capture as well as physics |
| `state_id`, `is_new_state` | The 760-state count is a qubit-record count, not a calibration count | n/a | Any "per state" sampling ignores gate-only re-calibrations (314 same-state pairs) |
| Target and configuration | Which operations exist when (schema starts) | n/a | Schema starts are not missingness; historical targets lead live ones |
| Fault map | Exclusion lists for every family | Placeholders documented on `ibm_fez` (Hassan and Kaabouch 2026, survey §2.3) | Faults are qubit-centred and spatially concentrated; `102-103`'s placeholder does not mean "unusable" for layers |
| Layout | Hop distances for every neighbour analysis (P6), the bipartition | Heavy-hex as a low-crosstalk layout (Chamberland et al. 2020) | Same-stamp qubits are never neighbours for `sx`/`T2`; spatial tests need graph distances, not index differences |
| `lf_N`, EPLG | A device-level, crosstalk-including quantity that the per-gate fields do not contain; a check on how far a model built from isolated errors under-predicts layered circuits | Benchmark at scale and link to error-mitigation overhead, `gamma` about `1/LF^2` (McKay et al. 2023, eq. 7); chain optimisation lowers EPLG(100) by 40% to 70% against random chains and makes LF a monitoring tool (Lozano Palacio et al. 2025, fetched 2026-10-06) | The 1.4 layered-to-isolated ratio and its spread are measured, provisional numbers that any noise model of layered circuits on this device can be checked against |

## 9. Open questions, and what measurement would settle each

1. **Are `lf` stamps UTC measurement times?** Read the raw `date` string of the `lf_*`
   records in `20260903T104949000000Z.json` (the first live late file whose filing poll,
   2026-09-03T11:38:53Z, precedes its `lf` stamp, 13:43:35Z) and compare its offset
   with the other records' strings; check the poller's run log for that poll.
2. **Are per-record stamps write times?** Only IBM job metadata or documentation could
   confirm it; within the archive, the 1 s batch spacing is the evidence and it is indirect.
3. **Does a historical fetch return the target at document time or at fetch time?** Fetch
   one historical document dated 2026-09-08 (before the 2,224-op target) today and compare
   its target with the archived live copy of the same date.
4. **What caused the 2026-08-21 to 08-31 `init_error` and readout episode?** IBM's status
   history for those dates, and the per-qubit share of the shift (document 03's scope).
5. **Why did the readout cadence fall from 5.62 to 3.67 rounds per day?** Continued
   complete coverage (September onward) will show whether the lower rate is stable.
6. **Does IBM pick the six 100-qubit chains from current isolated errors?** Compute, at each
   lf event, the best 100-qubit paths by predicted LF from the current `cz` values and
   compare them with the reported chains (a path search on 156 nodes; not attempted here).
7. **Why is `q64` never in an `lf_100` chain?** Its couplers carry no placeholder; a
   per-coupler comparison of the `cz` and `rzz` levels of 63-64 and 64-65 against the rest
   (document 05's scope) would show whether they are simply poor.
8. **Is the layered-to-isolated ratio stable in time and across the chip?** It needs the
   per-component layered fidelities, which IBM does not publish; with them the ratio could be
   measured per coupler.
9. **The non-persistent component of `lf`**: see section 4 (repeated fixed-chain
   measurements with fit uncertainties).

## 10. Reproduce (exact commands) and results files

From the repository root, with the cache built as in `01-data-layer.md` §1:

```bash
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/batches.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/schedule.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/documents.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/states.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/changepoints.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/layout_faults.py
C:/t/venv/Scripts/python.exe docs/findings/2026-10-06-feature-deep-dive/analysis/device/layer_fidelity.py
```

`batches.py` takes about 2 minutes on the laptop (200 permutations per family); the others
take seconds. `device_common.py` holds the shared helpers (family list, event extraction,
rounds, graph distances).

| Results file | Sections |
| --- | --- |
| `results/device/batches.json` | header basis (events per family), 3.3, 5.4, 6.2 items 7 and 8 |
| `results/device/schedule.json` | 0, 3.1, 3.2, 3.6 |
| `results/device/documents.json` | 2.1, 2.2, 2.3, 3.4, 6.2 items 5 and 6 |
| `results/device/states.json` | 2.4, 6.2 items 3 and 4, 7.1 |
| `results/device/changepoints.json` | 3.5, 3.7 |
| `results/device/layout_faults.json` | 5.1, 5.2, 6.1 |
| `results/device/layer_fidelity.json` | 2.5, 3.7, 4, 5.3, 6.2 item 1, 7.1, 7.2 |

**Sampled, truncated or skipped, logged.** Permutation nulls use 200 permutations
(`batches.py`), the clustering tests 20,000 Monte Carlo draws and the footprint null 2,000
(`layout_faults.py`). The spatial batch test uses only rounds with at least 20 entities, at
least two batches and one event per entity (122 readout, 97 `init_error`, 52 `measure_2`,
133 `T1`, 133 `T2`, 132 `sx`, 43 `xslow`, 130 `cz`, 109 `rzz` rounds). Schedule statistics use
major rounds only; minor rounds are counted but not timed. The order table matches within
12 h and leaves unmatched anchors out (counts in the table). Seasonality bins with fewer
than 3 rounds are left out of the test, and chi-square tests with fewer than five expected
rounds per bin are not run. Results files list at most 6 entry files per faulty entity, at
most 20 entities per family (3 of 156 for `measure_2`, whose entities are identical), and
at most 5 example files elsewhere. `lf` predictions skip 278 event-name pairs (the
`102-103` placeholder), and the `rzz` variant is usable for 14 `lf_100` events. The `lf`
variograms include the carried-in 2026-05-10 event; the `lf` change points exclude it.
Events stamped before the first file are dropped as listed in section 6.2 item 7.
`xslow` is left out of the change-point series (two separate lifetimes). Nothing else was
sampled or capped.

## 11. Sources

Five sources were fetched new in this session; one existing survey source was re-read in
full.

| Source | Identifier | Where verified | Used for |
| --- | --- | --- | --- |
| IBM Quantum, QPU information (view backend details) | quantum.cloud.ibm.com/docs/en/guides/qpu-information (vendor documentation, no DOI) | fetched 2026-10-06 | How each property is measured; isolation batches; six 100-qubit chains; EPLG(100) formula |
| Killick, Fearnhead, Eckley, Optimal detection of changepoints with a linear computational cost (2012) | arXiv:1101.1438 | fetched 2026-10-06 | PELT |
| Chamberland, Zhu, Yoder, Hertzberg, Cross, Topological and subsystem codes on low-degree graphs with flag qubits (2020) | arXiv:1907.09528 | fetched 2026-10-06 | Heavy-hexagon lattice, degree two and three |
| Lozano Palacio, Nayfeh, Ware, McKay, Parameter Analysis and Optimization of Layer Fidelity for Quantum Processor Benchmarking at Scale (2025) | arXiv:2510.16915 | fetched 2026-10-06 | Chain selection and EPLG; LF as a monitoring tool |
| Gambetta et al., Characterization of addressability by simultaneous randomized benchmarking (2012) | arXiv:1204.6308 | fetched 2026-10-06 | Simultaneous RB and neighbour crosstalk (reading of the batch structure) |
| McKay, Hincks, Pritchett, Carroll, Govia, Merkel, Benchmarking Quantum Processor Performance at Scale (2023) | arXiv:2311.05933 | existing survey (2026-10-05) §2.2 and §3; full text re-read 2026-10-06 | Layer fidelity, EPLG, sub-chain rule, process versus average error, Heron comparison, `gamma` |
| Kelly et al., Physical qubit calibration on a directed acyclic graph (2018) | arXiv:1803.03226 | existing survey (2026-10-04) §8 | Calibration dependency order (comparison only) |
| Hassan and Kaabouch, A Physics-Informed Neuro-Fuzzy Framework for Quantum Error Attribution (2026) | arXiv:2602.21253 | existing survey (2026-10-05) §2.3 | The placeholder on `ibm_fez` |
| Project: `01-data-layer.md` | this folder | read 2026-10-06 | Field semantics, identities, coverage caveats |
| Project: feature patterns P1 to P8 | `docs/roadmap/2026-10-05-feature-patterns-and-method.md` | read 2026-10-06 | Lag-1 range, P6, P7 |
| Project: August gap enumeration | `docs/implementations/2026-09-02-aug-gap-enumeration.md` | read 2026-10-06 | Attribution of the August file gaps |
| Project: ADR-025 ledger and collisions | `docs/decisions.md` (ADR-025) | read 2026-10-06 | Ledger vocabulary; archived copies never overwritten |
| Project: polling workflow | `.github/workflows/calibration-poll.yml` | read 2026-10-06 | Cron entries and the measured 6.13 runs per day |

## Verification (2026-10-06)

Verifier: an independent agent that did not write this document. Machine: the lead's laptop;
all figures remain provisional.

**Re-run.** All seven owner scripts (`batches`, `schedule`, `documents`, `states`,
`changepoints`, `layout_faults`, `layer_fidelity`) were re-run from the cache; every results
JSON reproduces field for field except `measured_utc` (the original files were restored
afterwards). The results files are newer than their scripts (no stale file). Independent
recomputation used new scripts written from `ddload` only: `analysis/verify/device/v1_basics.py`
to `v7_lf_late.py`, results in `results/verify/device/` (`v1_basics.json`, `v2_schedule.json`,
`v3_lf_ratio.json`, `v4_faults.json`, `v5_changepoint.json`, `v6_readout_cadence.json`,
`v7_lf_late.json`).

### Numbers checked

| Claim | Document value | Recomputed | Match |
| --- | --- | --- | --- |
| Files; live; historical | 1,760; 1,317; 443 | 1,760; 1,317; 443 | yes |
| Files per month (May to Oct) | 171, 194, 270, 304, 683, 138 | same | yes |
| Gaps above 12 h, all live to live; longest | 14; 82.7 h | 14 (14 live-live); 82.68 h | yes |
| Graph: degrees 1/2/3; diameter; girth; cycle rank; classes | 8/100/48; 32; 12; 21; 92 and 64 | same | yes |
| `last_update_date` equals newest measured stamp | 0.195; median 0.98 h; 0 earlier | 0.1949; 0.980 h; 0 | yes |
| `zz` stamps equal `last_update_date` | every file | every file | yes |
| `T1` major rounds; median gap; daily shift; hour p; day p | 133; 24.71 h; 0.73 h; 0.0026; 0.866 | 133; 24.71; 0.726; 0.00255; 0.866 | yes |
| `cz` rounds; gap; shift; hour p | 130; 25.13; 1.11; 0.019 | 130; 25.13; 1.111; 0.0193 | yes |
| Readout rounds 588, gap 4.44 h, offset from `T1` | -0.74 h (-1.10, -0.41) | -0.741 h (-1.097, -0.414), n = 132 | yes |
| Readout rounds per day, May and Sep | 5.62; 3.67 | 5.64; 3.67 (round gap 15 min); 5.59 and 3.64 at 60 min | yes (my day count differs slightly) |
| `lf_100` median; range | 0.5449; 0.432 to 0.606 | 0.5449; 0.4319 to 0.6056 | yes |
| EPLG(100) average-form median | 0.00489 | 0.004891 | yes |
| EPLG(100) Spearman with time | 0.456, p = 1.5e-5, n = 83 | 0.456, p = 1.5e-5 (n = 83); 0.463 for the 82 in-archive events | yes (n note marked inline) |
| `lf_N` monotone in N inside every event | 83 of 83 | 83 of 83 | yes |
| Lag-1 ACF of dlog EPLG, `lf_100` | -0.56 | -0.565 | yes |
| `lf` late files; live; historical | 217; 156; 61 | 217; 156; 61 | yes |
| Live late files with poll before lf stamp; max; median | 49 of 60; 3.49 h; -1.34 h | 49 of 60; 3.49 h; -1.34 h | yes |
| States; flag not on first file | 760; 79 (all first-file historical) | 760; 79 (79) | yes |
| lf_100 / cz-prediction ratio, median (25%, 75%) | 1.42 (1.31, 1.50) | 1.420 (1.312, 1.499), n = 76 | yes |
| Spearman `ln(lf_100)` vs `ln(pred_100)` | 0.269, p = 0.019, n = 76 | 0.2685, p = 0.019, n = 76 | yes |
| Distinct `lf_100` chains | 59 | 59 | yes |
| Robust SD of day-to-day `ln(lf_100)` change, chain same / changed | 0.030 (16) / 0.058 (66) | 0.030 (16) / 0.061 (65, in-archive pairs only) | yes, within counting difference |
| Permanent faulty couplers | 27-28, 32-33, 71-72, 72-73, 95-99, 99-115 | same | yes |
| Adjacent pairs null mean, 6 and 16 couplers | 0.24; 1.91 | exact 0.2377; 1.9013; MC p = 0.0176 | yes |
| Footprint mean hop; null median (random qubits) | 7.73; 12.76 | 7.733; 12.67 | yes |
| Footprint "below smallest of 2,000 draws" | min 7.8 | min 7.62, p = 0.001 | no (seed dependent, minor) |
| Readout step after 2026-06-08 length change | -0.138 decades (PELT segment medians) | -0.105 to -0.116 (window medians) | yes in sign and size order |

### Claims challenged

| Claim | Verdict | Why |
| --- | --- | --- |
| Faults are spatially concentrated (footprint hop distance, "below the smallest of 2,000") | weakened | The null uses 10 random qubits; the faults are couplers, whose endpoints are adjacent by construction. Random-coupler null: p = 0.042 uncorrected; with 2 adjacent pairs already present, p = 0.16. The adjacency test itself (p = 0.018) holds. Marked inline. |
| Readout drop at 2026-06-08 is "one clear exception" to chance alignment | weakened | Reproduces and controls (T1, T2, sx) show no step, but readout's biggest drop is 05-17 (-0.20 decades) with no known event, 06-08/09 is also a schedule restart date, and the second length change has no response. Marked inline. |
| Part of the `lf` non-persistent component is chain re-selection | weakened | 16 same-chain pairs; permutation p = 0.015, Levene p = 0.070. Marked inline. The document's own stance (no attribution to noise or to fluctuations) is upheld. |
| `lf` stamp lateness could be an offset error in the source string | weakened | A constant offset is not what the data show (median lf minus `last_update_date` is -13.0 h; only 217 files positive; lag 0.01 to 6.4 h). The measured facts (49 of 60) are upheld. Marked inline. |
| Readout visible cadence fell for reasons beyond coverage | upheld | Same fall at round gaps of 15 and 60 min; the live-only May to July months (files per day 9.25, 6.47, 8.71) already show 5.64, 4.47, 4.23 rounds per day, and lost captures can only lower a count, so the true May rate was at least as high. At 180 min the fall persists (4.66 to 3.34). |
| No time-of-day or day-of-week pattern in device medians | upheld, with a wording caveat | Not rejecting uniformity is not evidence of uniformity, and the test sees only device medians (the document says so). The non-uniform hour of round starts (own p = 0.0026 for T1) is reproduced; its restart explanation is labelled interpretation and was not tested. |
| Change-point alignment with known events is near chance | upheld | Method reproduces; the match window covers 0.193 of the span, so 5 of 17 against 3.29 expected is not significant. |
| `lf_100` is about 1.4 times the isolated-gate prediction, flat in N | upheld as measured | Recomputed independently for N = 10, 50, 100 (1.37, 1.42, 1.42). The cause is correctly left open; the 10.9 h age of the `cz` value is one unseparated factor. |
| States are qubit-record states (0 of 998 same-state pairs differ) | upheld, but near-tautological | The digest is of qubit values, so equal ids implying equal values is expected; the informative part is the 314 gate-only changes inside states. |

### Sources spot-checked (fetched 2026-10-06)

| Source | Result |
| --- | --- |
| arXiv:2510.16915 (Lozano Palacio et al.) | Title matches; abstract states EPLG 40% to 70% lower than random chains for N = 100 and layer fidelity as a monitoring tool. Supported. |
| arXiv:1204.6308 (Gambetta et al.) | Title matches; simultaneous randomized benchmarking and crosstalk. Supported; the document correctly says the batch reading is not confirmed by IBM. |
| arXiv:1101.1438 (Killick, Fearnhead, Eckley) | Title matches; linear-cost optimal changepoint detection. The abstract does not use the name PELT; the document's use of the name is the usual one, but the page does not state it. |

### Rule check

- Em dashes (U+2014): none in the document or in `analysis/verify/device/` (count 0).
- Provisional banner, ref, basis and machine: present in the header paragraph.
- Traceability: every number checked above is in an owner results field or was recomputed.
  The header's re-measurement event counts per family were not independently recounted.
- `docs/numerical-claims.md`: not edited; the document states it registers nothing there.
- Pinned ruff `check` and `format --check` pass on `analysis/verify/device/`.
