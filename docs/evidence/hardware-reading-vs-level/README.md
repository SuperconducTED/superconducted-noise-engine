# Hardware reading-versus-level test (#125): evidence for the pre-registration

**Date**: 2026-10-24 · **Author**: Mert Efe Şensoy · **Protocol written before the runs**
(sections 2 and 3 were committed before `measure_checkup_floor.py` or
`scripts/hardware_test_grid_bias.py` produced a committed number; results are appended in
section 4 with the commit that produced them; one scratch computation preceded this protocol,
see section 3.4) · **Owner of the question**: Issue #125 (@mertefesensoy QPU side, @BurakOztekin
offline side, @bengisucvd statistics review) · **Status**: laptop runs, provisional; the
floor measurement's canonical reproduction on Burak's desktop is owed

## 1. What this folder is for

The hardware test (`docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md`) compares, on
`ibm_fez`, a qubit's latest calibration **reading** against its 30-day **level** as predictors of
what the device does. Before the first job, a pre-registration commit freezes the selection rules,
the control qubits and the delay grid. PR #126's dry run left three of those open (qubit 72, the
sign of the disagreement, the delay grid) and a fourth follows from the design's own text (the
order of control and discriminating selection). The two measurements here are inputs to those
decisions. They take no decision; the pre-registration draft
(`docs/roadmap/2026-10-24-issue-125-preregistration.md`) carries the proposals and the lead
decides.

Later, the same folder receives the hardware test's own evidence (the job logs, the archived
properties at submission and execution, the scores), as Issue #125 names it.

## 2. Measurement 1: the check-up floor, day by day over the archive

### 2.1 Reproduction guard, run first

At `t_s = 2026-10-23T09:34:56Z` on `calibration-data` @ `5828b4a29fabc245aa096e530852249a3496dc5b`
the script must reproduce PR #126's recorded dry run
(`docs/implementations/2026-10-23-hardware-test-archive-side.md`, Verification): 2,249 files and
924 states used, nothing skipped; qubit 72's `T1` with `n_distinct = 29`; the eight
discriminating qubits 148, 108, 72, 132, 155, 10, 80, 77 in that order; the proposed controls
105, 112, 48, 140. If any of these differs, the script stops, writes what differed, and no
per-day figure is read.

### 2.2 Definitions

For an evaluation instant `t` and qubit `q`, with the window `W(t)` the distinct device states
in `(t - 30 d, t]` exactly as PR #126's `predictor_rows` builds it:

- `w_q(t)`: the number of distinct finite positive `T1` values of qubit `q` among the states of
  `W(t)`. This is the count the proposed floor reads.
- `N_q(t)`: PR #126's `n_distinct`, distinct finite `T1` values over all states up to `t`. This
  is the count the approved design's floor reads.
- `modal_share_q(t)`: the fraction of the states of `W(t)` whose `T1` for qubit `q` equals the
  most frequent value in the window (a value carried across many states makes this large).
- `d_q(t)`: PR #126's `log_disagreement` for `T1`.
- The **current rule** admits `q` when `N_q(t) >= 20`; a **window rule** with floor `k` admits
  `q` when `w_q(t) >= k`. Candidate floors: `k` in {5, 10, 15, 20}. No other value is computed.
- The **top eight** under a rule: PR #126's `select_discriminating` with `k = 8` over the
  admitted qubits, largest `|d_q(t)|` first.

### 2.3 Evaluation instants

Every day at 12:00 UTC from the first such instant at least 30 days after the earliest state at
the ref, to the last such instant at or before the latest file at the ref; plus the guard instant
of section 2.1. The hour is a convention: window counts change only when a state enters or
leaves the window, and the result does not depend on the hour beyond that.

### 2.4 Outputs

`checkup-floor-days.tsv`, one row per evaluation instant:

- the number of qubits with a finite `d` (the selectable set before any floor);
- the number excluded by the current rule and by each window rule;
- qubit 72: `w_72`, `N_72`, `modal_share_72`, `d_72`, and whether each rule admits it;
- whether qubit 72 is in the top eight under the current rule and under each window rule;
- the overlap (0 to 8) between the top eight under the current rule and under each window rule;
- **sign composition, descriptive**: the number of the current rule's top eight with `d < 0`,
  and the share of all admitted qubits with `d < 0` (the base rate);
- **union-grid delay span, descriptive**: over the current rule's top eight, the shortest
  non-zero and the longest delay the union grid of section 3 would need, in microseconds
  (`0.5 x min(T1_reading, T1_level)` and `2 x max(T1_reading, T1_level)`).

`checkup-floor-qubits.tsv`, one row per qubit at the guard instant: `w_q`, `N_q`, `modal_share_q`,
`d_q`, the level and the reading in microseconds.

`checkup-floor-controls.json`: PR #126's `propose_controls` with `k = 4` at the guard instant,
once with the dry run's exclusion of the top eight (PR #126's order) and once with nothing
excluded (decision D's order), under the current floor and under each window floor.

`checkup-floor-summary.json`: the ref, the instants, the guard's outcome, and per rule the
median, minimum and maximum over days of the excluded count and of the overlap; the number of
days qubit 72 is admitted under each rule; the distribution over days of the sign composition.

### 2.5 What this measurement does not do

It does not choose `k`, and it does not decide whether to balance the sign. It reports what each
candidate does on the record we have. It reads no hardware outcome, so nothing it reports can
be fitted to the result the test will produce.

## 3. Measurement 2: which predictor a delay grid favours

### 3.1 Model

Arm A prepares `|1>`, waits `tau`, and measures. The design's first-order prediction for a
qubit with relaxation time `T1` and assignment probabilities `e10 = prob_meas0_prep1`,
`e01 = prob_meas1_prep0` is `p_1(tau) = e01 + (1 - e01 - e10) exp(-tau / T1)`. Arm A's
per-qubit score is the mean over its delays of `|p_hat - p_pred|`, for each predictor.

Two predictors, `reading` with `T1_R` and `level` with `T1_L`, disagreeing by
`d = log T1_R - log T1_L`. The truth `T1_true` is placed between them in log space:
`log T1_true = log T1_R + a (log T1_L - log T1_R)`, `a` in `[0, 1]`. This assumption is stated,
not tested: a truth outside the two predictions makes the nearer one win at any grid, and the
question is only about the cases between.

The **tie point** `a*` is where the two predictors' scores are equal. `a* = 0.5` is a neutral
grid; `a* > 0.5` means the level must be nearer the truth than halfway to win, so the grid
favours the reading; `a* < 0.5` favours the level.

### 3.2 What is computed

- Grids, per qubit: `level`, `{0, 0.5, 1, 2} x T1_L` (the design's §3 grid); `reading`,
  `{0, 0.5, 1, 2} x T1_R`; `union`, the union of the two, seven delays when `T1_R != T1_L`;
  `midpoint`, `{0, 0.5, 1, 2} x sqrt(T1_R T1_L)`.
- Disagreements: `|d|` in {0.25, 0.37, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0}, each with both
  signs. 0.37 is the design's assumed scatter (NC-084's 80% figure); the dry run's eight lay
  between 0.58 and 1.71 in size.
- Noise: noiseless (`p_hat = p_true`) and 2,048 shots (the design's Arm A count, the exact
  binomial expectation of `|k / n - p_pred|`).
- Readout: ideal (`e01 = e10 = 0`). For the noiseless score this loses nothing when both
  predictions use the same readout: the readout is the same affine map on both predictions and
  on the truth, so every absolute error is multiplied by `1 - e01 - e10` and `a*` does not move.
  The design gives each predictor its own readout source; that difference is a separate effect
  and is not modelled here.
- Every (grid, `d`, noise) combination is reported; none is dropped.

### 3.3 Outputs

`grid-bias.tsv`, one row per (grid, `d`, shots): `a*`, the number of distinct non-zero delays,
and both predictors' scores at `a = 0.5`. The log score, which the design also reports, is not
analysed here; the decision rule in §7 of the design uses the absolute error.

### 3.4 What preceded this protocol

A scratch computation on 2026-10-24, before this protocol and outside the repository, produced
the observation that motivated measurement 2: noiseless, ideal readout, reading below level,
`a*` for the level-centred grid 0.525, 0.567 and 0.648 at `|d|` = 0.58, 1.04 and 1.71, and for
the union of both grids 0.509, 0.516 and 0.526. So the grids and the question here were chosen
after seeing a result, and this measurement is **not blind**. What is fixed in advance is the
reporting: the full grid of `d`, both signs, both noise settings, every grid computed. The
committed run supersedes the scratch figures; if they differ, the committed run is the record.

## 4. Results

To be appended with the commit that produced them.

## 5. Reproduction

Measurement 1, from the repository root, with `calibration-data` @ `5828b4a2` fetched:

```bash
PYTHONPATH=src python docs/evidence/hardware-reading-vs-level/measure_checkup_floor.py --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --out docs/evidence/hardware-reading-vs-level/
```

Measurement 2, no archive needed:

```bash
PYTHONPATH=src python -m scripts.hardware_test_grid_bias --out docs/evidence/hardware-reading-vs-level/
```

## 6. Amendments

Dated, append-only.

### 6.1 2026-10-24, before the record run of measurement 1, after a scratch run of it

A scratch run of `measure_checkup_floor.py`'s functions over a cached collection (same ref, same
code, outside the repository) passed the guard and showed that the current rule's top eight is
almost always one-sided: most days all eight, or seven of the eight, read below their level,
while well under half of all admitted qubits do. That makes decision B's cost a question the
protocol did not ask: if the selection takes four from each side, how much smaller are the
disagreements on the side above the level? Added, **after seeing that scratch output and
therefore not blind**, as descriptive columns of `checkup-floor-days.tsv`, under the current
rule's admitted set:

- `n_admitted_below`, `n_admitted_above`: admitted qubits with `d < 0` and `d > 0`;
- `absd_8th_current`: the eighth-largest `|d|` overall, the weakest disagreement the design's
  rule selects;
- `absd_4th_below`, `absd_4th_above`: the fourth-largest `|d|` among `d < 0` and among `d > 0`,
  the weakest disagreement on each side that proposal B selects (empty if a side has fewer than
  four).

The summary gains their median, minimum and maximum over days. Nothing in sections 2.1 to 2.4
changes; the record run is the committed script end to end, and its other outputs must match the
scratch run's.

### 6.2 2026-10-24, before the record run of measurement 1, after a scratch probe

A scratch probe over the same cached collection named two facts the draft needed but the script
did not write: the scatter values behind the control proposals (the six qubits nearest the median
lie within about 0.002 of one another, so which four come out depends on who is eligible), and
the qubit behind the shortest union delay. Added, **after seeing that probe and therefore not
blind**, so every figure the draft cites comes from the committed script:

- `checkup-floor-controls.json`: per rule, `scatter_first` (the whole-archive `log T1` scatter of
  each control chosen first); and `nearest_median_ten`, the ten qubits nearest the median with
  nothing excluded, with their scatter and the median;
- `checkup-floor-days.tsv`: `union_shortest_qubit`, `union_longest_qubit` and their reading and
  level in microseconds;
- `checkup-floor-summary.json`: `union_shortest_extreme` and `union_longest_extreme`, the day,
  qubit, reading and level behind the extremes over all days.

The record run, of the committed script end to end, has not yet been made; section 6.1's
statement about it stands.
