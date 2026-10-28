# 2026-10-28: the #125 hardware test, offline half (`scripts/hardware_reading_vs_level.py`)

> Status at the plan commit: **plan, no code and no dry-run number yet**. Every acceptance
> criterion of the dry run is written here before the first run. Sections marked "after the run"
> stay empty until then.

## Problem / Motivation

The #125 hardware test compares four predictors of a qubit's behaviour (`reading`, `level`,
`band`, `reading_at_execution`; design §2) on `ibm_fez`. The archive side (PR #126, and the
selection rules of PR #132) computes the predictors and picks the qubits. Nothing yet builds the
circuits, predicts their outcomes, scores the predictions, or checks the whole pipeline before
the QPU is used. Design §5 makes a dry run against Aer, committed, the pipeline's zero-cost
acceptance test, and the pre-registration's freeze waits on it (draft §6). This is step 1b of the
build order (plan §8, on PR #131); plan §8.2 is the dated note that the lead took this half from
Burak, who reproduces it on the desktop.

## What changed

Planned at the plan commit; completed after the implementation (the CLI ships the dry run only,
amendment 1).

| File | One-sentence description |
| --- | --- |
| `scripts/hardware_reading_vs_level.py` | Circuits for Arm A and Arm B, the predictions of every predictor, the scoring, the per-circuit seeds, and a CLI that runs the whole pipeline against two Aer truths built from an archived snapshot. |
| `tests/test_hardware_reading_vs_level.py` | 41 tests pinning each piece on synthetic inputs and `FakeFez`'s bundled `ibm_fez` documents, mutation-checked. |
| `docs/evidence/hardware-reading-vs-level/dry-run-2026-10-28/` | The dry run's committed output and manifest; pipeline acceptance on Aer, not a measurement. |
| `docs/implementations/2026-10-28-hardware-test-offline-half.md` | This record. |

## Implementation approach

### The invariant

The predictors' outcome predictions come from **one builder**: the same code for `reading`,
`level`, `band` and `reading_at_execution`, with only the input arrays (per-qubit `T1`, `T2`,
`prob_meas0_prep1`, `prob_meas1_prep0`) differing. The dry run's truth comes from a **different
path**, Aer's `NoiseModel.from_backend` on a backend rebuilt from the archived snapshot, as the
design says. If both used the same builder the dry run would be a tautology.

### Inputs, from the archive side

`predictor_rows`, `select_balanced`, `freeze_controls` and `load_controls` from
`scripts/hardware_test_predictors.py` (PR #132; this branch is stacked on it and its PR opens
after #132 merges). One job's inputs: the eight discriminating qubits, the four frozen controls,
and per qubit the reading, the level and the band of `T1`, `T2` and the two readout assignment
probabilities. `reading_at_execution` comes from `--mode execution` rows at `t_execute`.

### Arm A, decay (design §3, proposal C)

- **Delays.** Per qubit, seven ordered slots: `0`, `0.5, 1, 2 x T1_level`, `0.5, 1, 2 x
  T1_reading`. Each is rounded to the nearest multiple of `dt` (4 ns on `ibm_fez`: the archived
  configuration's `dt = 4.0` is in nanoseconds, matching `FakeFez.dt = 4e-9`); a non-zero delay
  below the backend's `min_length` (2 `dt`) is raised to it. A slot whose rounded delay equals an
  earlier slot of the same qubit is dropped from that qubit and marked excluded (the draft's "six
  when the two are equal"). Controls get their own union grid the same way. No cap on circuit
  duration unless the submission rejects one; the longest delay is logged.
- **Circuits.** One circuit per slot index (seven), each holding all twelve qubits: `x`,
  `delay(tau_q)`, `measure`. `ibm_fez`'s `meas_map` is one group of all 156 qubits, so every
  measurement in a circuit is simultaneous. The circuit is therefore built with each qubit's `x`
  and `delay` immediately before the common measurement, and scheduled ALAP, so no qubit idles
  between its delay and its measurement. A test reads the scheduled circuit and checks that every
  qubit's interval from the end of `x` to the start of `measure` equals its `tau_q`.
- **Prediction** (design §3, closed form, no simulation):
  `p_1 = (1 - e_10) s + e_01 (1 - s)`, `s = exp(-tau / T1)`, with `T1`, `e_10 =
  prob_meas0_prep1` and `e_01 = prob_meas1_prep0` from the predictor's own source. The band gives
  `[p_1(T1_lo), p_1(T1_hi)]` with the level's readout. The rounded `tau` is used.

### Arm B, layouts (design §4)

- **Eligible qubits** (Mert, 2026-10-28): at least 15 distinct `T1` values inside the window, the
  same floor as proposal A; the four controls may sit in a triple, since Arm B is not selected on
  disagreement. This is an amendment to the pre-registration's frozen table, owed at step 1c.
- **Triples.** Connected triples `a - b - c` from the archived `coupling_map` (a `cz` on `a-b`
  and on `b-c`), with `b` as the GHZ's control (logical qubit 0) so both `cx` act on coupled
  pairs. Every eligible triple gets a predicted fidelity under `level`; the six chosen sit at
  ranks `round(i (n - 1) / 5)`, `i = 0..5`, of the sorted list, best to worst, ties by the sorted
  qubit tuple. One circuit per triple, so triples may share qubits.
- **Circuit.** `ghz_state_circuit(3)` with its final measurements removed, then `delay` of
  `0.5 x` the median `T1_level` of the three qubits on each, then measurement; transpiled once to
  the backend's basis (`cz`, `sx`, `rz`, `x`) with a fixed layout, `optimization_level` and seed.
  The transpiled circuit is the one predicted and the one submitted.
- **Prediction, one builder.** A per-predictor Aer `NoiseModel`: per-qubit
  `thermal_relaxation_error` on `sx` and `x` from the predictor's `T1`, `T2`, with gate lengths
  from the latest snapshot; `RelaxationNoisePass` with the predictor's `T1`, `T2` arrays for the
  idle `delay`; on `cz`, a two-qubit depolarizing channel with `p = 4 r / 3` from the latest
  snapshot's `cz` `gate_error` `r` (average gate infidelity of a two-qubit depolarizing channel is
  `3p/4`) and no relaxation, the same object for every predictor because the two-qubit gates are
  not under test (design §4). `thermal_relaxation_error` is the engine's channel: ADR-027's
  equivalence tests compare it with the amplitude-plus-phase-damping construction under `SuperOp`
  (`channels/kraus.py` is LOCKED and is not touched). The exact outcome probabilities come from
  Aer's density-matrix method with the final measurements removed; readout then enters
  analytically as the product of per-qubit assignment matrices from the predictor's own `e_10`,
  `e_01`. No sampling noise in any prediction. This is how this plan reads design §4's "density
  matrix" together with "readout from the same source"; it is an amendment owed at 1c.
- **Band in Arm B.** The fidelity interval from the band's two ends (`T1_lo` with `T2_lo`, and
  `T1_hi` with `T2_hi`, level readout); it ranks layouts by the interval's midpoint and is scored
  for coverage of the measured fidelity. Owed at 1c for Bengisu's review.
- **A `T2 > 2 T1` source** (possible for the level, a geometric mean taken per quantity) is
  rejected by ADR-027's rule: that predictor gets no prediction for a triple containing the qubit,
  logged, and the triple is never silently repaired.
- **Omissions in the Arm B builder**, identical across predictors and second order: no
  single-qubit depolarizing error (`from_backend` installs one), no relaxation during `cz`, no
  relaxation during `measure`, no thermal excited-state population.
- **Figure of merit.** Hellinger fidelity to the ideal GHZ distribution
  (`qiskit.quantum_info.hellinger_fidelity`, `(1 - H^2)^2` with `H` as in
  `benchmarks/metrics.py`), for predictions and for measured counts alike.

### Scoring

- **Arm A, per (job, qubit, slot):** absolute error `|p_hat - p_pred|` for each point predictor;
  the binomial log score; band coverage of `p_hat` at its nominal 80%, and again after widening the
  band by one binomial standard error `sqrt(p_hat (1 - p_hat) / n)` on each side; band width.
  Aggregated per predictor, per stratum (discriminating, control).
- **Arm B, per job:** Spearman rank correlation between predicted and measured fidelity over the
  six layouts, per predictor; whether the predictor's top layout is the measured best; mean
  absolute fidelity error. Across jobs: the share of best-pick hits and the mean Spearman.
- **Paired bootstrap** for the decision rule's differences (`level - reading`, `level -
  reading_at_execution` in mean absolute error), 90% percentile interval. The resampling unit is a
  parameter: rows, jobs, or blocks of consecutive calendar days with empty dates kept at zero rows
  (Bengisu's PR #128 lesson). The unit is frozen at step 1c after her review, not here.

### CLI

`--mode build` (one job's circuits and predictions from the archive at `t_s`, written to a job
directory), `--mode score` (a job directory plus counts), `--mode dry-run` (both, with Aer
counts from the truth models below). Submission, `rep_delay`, `init_qubits` and the IBM token
are step 1d's; this script never imports the token and the dry run reads only the archive.

## Mathematical / Statistical details

- **Arm A closed form.** With `s = exp(-tau / T1)`, the probability of reading `1` after
  preparing `1` is `(1 - e_10) s + e_01 (1 - s)`. Omitted, identical across predictors: thermal
  excited-state population, the `x` gate's own error and relaxation during it, relaxation during
  measurement, readout-induced transitions (design §3).
- **Aer and `T2 > 2 T1`.** Checked 2026-10-28 on the pinned Aer 0.17.2: a target qubit with
  `T2 = 3 T1` passes through `from_backend` without an error or a warning, and its
  `RelaxationNoisePass` carries `T2 = 2 T1`, a silent cap. The predictor side does not cap; it
  rejects (ADR-027).
- **Why the dry-run truth and the matching predictor differ by a known offset.** Aer's
  `from_backend` (checked 2026-10-28 on the snapshot of 2026-10-23T09:34:56Z, qubit 0, density
  matrix, no shots) applies a **symmetric** readout error `r = readout_error`, which IBM reports as
  `(e_10 + e_01) / 2`, and the `x` gate's depolarizing error; it installs no relaxation on
  `measure`, and its `RelaxationNoisePass` damps the `delay`. So the truth is about
  `(1 - r) s' + r (1 - s')` with `s'` slightly below `s`, where the predictor is
  `(1 - e_10) s + e_01 (1 - s)`. The difference is `(e_10 - r) s - (e_01 - r)(1 - s)` plus the
  gate term. A scratch probe on one qubit put this at about one percentage point, mostly the
  readout term; those digits are not quoted and are superseded by the dry run's committed
  per-row offset table, which derives the offset from the truth model itself.
- **Hellinger fidelity.** `F = (sum_i sqrt(p_i q_i))^2 = (1 - H^2)^2`.
- **Binomial standard error** at `n` shots: `sqrt(p (1 - p) / n)`, 0.011 at `p = 0.5` and
  `n = 2048`, 0.0078 at `n = 4096`.
- **Spearman** on six layouts: ranks with average ties, Pearson correlation of the ranks.

## The dry run's protocol (written before any run)

- **Instant and ref.** `calibration-data` `5828b4a29fabc245aa096e530852249a3496dc5b`,
  `t_s = 2026-10-23T09:34:56Z`, the instant NC-088 and PR #132's reproduction used. Controls from
  `--mode controls` there (48, 112, 54, 105, reproduced in PR #132). The `reading_at_execution`
  row is read at `t_execute = t_s + 2 h` (a nominal queue delay) from a separate
  `--execution-ref`, `calibration-data` `84ba0230738c9ee2773616b4e4c7142ba91180e3` (the branch tip
  on 2026-10-28), as the real analysis will read it after the fact. At `5828b4a2` the latest file
  is the one at `t_s` itself, so the same ref would make the control identical to `reading` by
  construction; `84ba0230` holds later files at 10:26:53 and 11:18:49 UTC that day, so the
  control is exercised with a different reading. The flag is also what step 1d needs.
- **Shots and seeds.** 2,048 per Arm A circuit, 4,096 per Arm B circuit (design §3, §4).
  `seed_simulator = 125`, transpiler `seed = 125`, both in the manifest (per-circuit seeds
  from it: amendment 1 below).
- **Two truths** (Mert, 2026-10-28), both `NoiseModel.from_backend` on a `BackendV2` rebuilt from
  the archived `configuration` and `properties` through `qiskit_ibm_runtime`'s
  `convert_to_target` (the archived snapshots carry no qubit `frequency`, so
  `from_backend_properties` cannot read them; checked 2026-10-28):
  - **Truth 1, "the device is the reading":** the reading's snapshot (the latest file at or before
    `t_s`) as is.
  - **Truth 2, "the device is the level":** the same snapshot with every qubit's `T1`, `T2`,
    `prob_meas0_prep1` and `prob_meas1_prep0` replaced by that instant's level, and
    `readout_error` set to `(level e_10 + level e_01) / 2`, IBM's own definition, so truth 2 is
    the exact mirror of truth 1 and criterion 2's offset has the same closed form under both. A
    qubit with no level keeps its reading and is listed. Values are written back in the Nduv
    entries' own units (`T1`, `T2` in `us`); a test reads a substituted value back through
    `BackendProperties.t1` and checks it equals the level. Where the level's `T2` exceeds twice its
    `T1`, Aer caps it silently (above): the manifest counts those qubits, Arm A is unaffected
    (population decay does not read `T2`), and in Arm B a triple containing one has a truth but no
    `level` prediction, which is logged and reported under criterion 4.
- **Acceptance criteria**, each pass or fail, all written now:
  1. **Sampling.** Every Arm A row's `p_hat` lies within 4 binomial standard errors of the truth
     model's own shot-free probability (density matrix, no shots); every Arm B outcome frequency
     likewise. Aer's density matrix is taken before `measure`, so the truth's shot-free
     distribution gets the truth's own symmetric readout applied analytically, through the same
     assignment-matrix function the predictors use. A zero shot-free probability would make its
     standard error zero; with depolarizing `cz` and readout none should be, so the code asserts
     every one is positive and the manifest reports the minimum. Expected failures at 4 sigma
     over about 84 Arm A rows: well under one.
  2. **Offset.** Under each truth, the matching predictor's (truth 1: `reading`; truth 2:
     `level`) mean signed error equals the mean of the derived per-row offsets (truth's shot-free
     probability minus the predictor's closed form) within 3 standard errors of the mean.
  3. **Direction.** On the discriminating rows, truth 1 ranks `reading` first and truth 2 ranks
     `level` first on mean absolute error, each with the row-unit paired bootstrap 90% interval of
     the difference to the other excluding zero. The row unit is a smoke test of the code, not
     the decision rule's unit.
  4. **Arm B runs end to end** under both truths: six triples chosen, every predictor scored, the
     measured fidelities within criterion 1. Spearman and best-pick are reported, not judged:
     with six layouts spanning a wide fidelity range both predictors may rank them perfectly.
  5. **Circuit timing.** In every Arm A circuit, as scheduled, each qubit's interval between `x`
     and `measure` equals its rounded `tau` exactly.

  If any criterion fails, the cause is found and fixed before the result is committed, and the
  failed run is disclosed in this document.
- **What the output is.** Pipeline acceptance on Aer: not a measurement of the device, no NC row,
  no sentence about `ibm_fez`. The next free register id stays NC-095.

### Amendment 1, 2026-10-28, after a scratch smoke run (not blind), before the record run

The code was smoke-run in the session scratchpad on predictor rows rebuilt from PR #132's
`predictors.tsv` at `5828b4a2` (no archive walk; the execution rows were the same rows, so
`reading_at_execution` equalled `reading`). Disclosed here because it changed three things:

1. **One seed per circuit.** With `seed_simulator = 125` on every circuit, Aer replays the same
   random stream in each one, so a qubit's sampling errors repeat across its seven slots and the
   84 rows are not independent draws. Criterion 2 assumes they are. In that run truth 1 failed
   criterion 2 (mean signed error minus mean derived offset -0.0033 against a standard error of
   the mean of 0.00099, 3.3 of them; truth 2: -0.0009, 0.9). The record run gives Arm A's
   circuits seeds `125 + i` and Arm B's `225 + i` (`circuit_seeds`). The criterion and its
   limit are unchanged. The smoke figures are scratch and are not results.
2. **Dead `cz` pairs.** `ibm_fez` reports `gate_error = 1.0` on some pairs (32-33 in that
   snapshot), which the depolarizing form cannot carry (`4 r / 3 > 1`). A triple is formed only
   over coupled pairs whose `cz` error satisfies `0 <= 4 r / 3 <= 1`; the builder refuses any
   other. Owed at 1c as amendment 9 below.
3. **CLI scope.** This change ships the `dry-run` command only. `build_job`, `score_arm_a` and
   `score_arm_b` are the functions the `build` and `score` modes will wrap; those modes, with
   circuit serialization, land with step 1d's submission script, which is where a job directory
   first needs writing and reading back.

Also stated, not changed: Arm A's counts come from the full twelve-qubit circuits, and the
truth's shot-free probability per row from that qubit's own instructions alone
(`_single_qubit_part`), which is exact because the truth model has no term coupling qubits in
Arm A.

### Amendment 2, 2026-10-28, correcting amendment 1's first item, before the record run

Amendment 1 named the right cause and the wrong fix. A second smoke run with seeds
`125 + i` failed criterion 2 under truth 1 again, by almost the same amount (-0.0033, 3.4
standard errors). The diagnosis, all scratch, in this order:

- At 200,000 shots the full twelve-qubit circuits agree with the per-qubit shot-free truth
  row by row (36 rows, mean z -0.06): the truth and the circuits are right.
- Within one shot the twelve qubits are independent (mean pairwise correlation of the bits 0.005).
- Over 30 seed bases 1,000 apart with seeds `base + i`, criterion 2's statistic had mean z
  +0.07 but a standard deviation of 1.63, not 1: no bias, but the rows were not independent.
- Over 40 consecutive seeds on one circuit each row's z moved by a standard deviation of 0.07.
  On that circuit Aer 0.17.2 runs 20 parallel shot streams and seeds shot `j` of a run with
  seed `s` as `s + j`: seed 501's shots are seed 500's shifted by one, all 2,048 identical. A
  one-qubit circuit does not take that path, which is why a first one-qubit check missed it.

So seeds closer than the shot count replay each other's shots, and `125 + i` made the seven
Arm A circuits share almost all of their draws. The record run draws one seed per circuit
from `numpy`'s `SeedSequence(125)` (`circuit_seeds`), spread over 32 bits, and the code
refuses any pair closer than ten times the largest shot count. The criterion and its limit
are unchanged; `125` remains the one seed named in the manifest.

**Check of the fix, before the record run** (scratch, truth 1, Arm A, the same rows): over 20
seed bases `0..19`, each circuit seeded through `circuit_seeds(base, 7, 0)`, criterion 2's
statistic had mean z +0.10 and standard deviation 0.86, none beyond 3, where the old seeding
gave 1.63. The rows now behave as independent binomial draws.

Whether Aer's per-shot seeding is documented, intended or a defect is being checked separately
(its source, docs and issue tracker); this record does not classify it.

**Correction to amendment 2's mechanism, 2026-10-28, same day, from that check.** Parallel shots
are not the cause. Aer seeds shot `j` as `seed + j` whenever it simulates shots one by one, that
is whenever measure sampling is off, with any thread count (`max_parallel_threads=1` shows the
same shift): Aer 0.17.2's `src/simulators/circuit_executor.hpp` sets
`rng.set_seed(circ.seed + shot_index)`, and a maintainer describes the scheme in the open issue
Qiskit/qiskit-aer#1916 (label `bug`). The one-qubit check missed it because Aer's `automatic`
method ran that circuit as a density matrix with measure sampling, not because it was small. Aer
also offsets the circuits of one `run()` by `seed + 2113 k`, so circuits in one run share streams
once shots exceed 2,113; this script runs every circuit on its own, so that never applies here.
The fix and its check stand unchanged.

**Results: after the run.** Record run 2026-10-28 from commit `8b244bb7` (code as at
`23fd2f4b`; later commits change only comments and this document), laptop, exact-pin interpreter,
41.5 minutes. Output: `docs/evidence/hardware-reading-vs-level/dry-run-2026-10-28/`
(`manifest.json`, `criteria.json`, `selection.json`, `controls.json`, `arm-a-truth{1,2}.tsv`,
`arm-b-truth{1,2}.tsv`). Pipeline acceptance on Aer, not a measurement: no NC row, no sentence
about `ibm_fez`. All five criteria pass under both truths; no run failed and none was repeated.

| Criterion | Truth 1 (device = reading) | Truth 2 (device = level) |
| --- | --- | --- |
| 1. Sampling | pass: 84 Arm A rows, max z 2.87; 48 Arm B outcomes, max z 2.68; smallest shot-free probability 0.0113 | pass: max z 2.52 and 2.67; smallest 0.0214 |
| 2. Offset | pass: mean signed error of `reading` 0.01095 against a mean derived offset of 0.01084, difference +0.00011, standard error 0.00099 | pass: `level` 0.00344 against 0.00498, difference -0.00154, standard error 0.00098 |
| 3. Direction | pass: 56 discriminating rows; mean absolute error `reading` 0.0182, `level` 0.1594; `level - reading` 90% interval +0.123 to +0.159 (row unit) | pass: `level` 0.0092, `reading` 0.1673; `reading - level` +0.134 to +0.183 |
| 4. Arm B end to end | pass: six triples, every predictor scored, none unpredictable | pass: same six, none unpredictable |
| 5. Circuit timing | pass: 84 of 84 intervals equal their rounded `tau` | pass: the same circuits |

Inputs as logged: discriminating 148, 132, 155, 10 (below their level) and 39, 147, 35, 44
(above), no short side (admitted 62 below, 87 above); controls 48, 112, 54, 105; reading file
`20261023T093456`; longest delay 442.8 µs; 152 qubits eligible for Arm B, 221 connected triples
over usable `cz` pairs, six chosen: 85-77-86, 15-14-19, 128-127-129, 67-57-66, 135-134-139,
1-0-2.

Read with these notes:

- **The `reading_at_execution` row equals `reading` in this run, by fact, not by construction.**
  The plan expected the execution ref to carry a different reading. It did not: the latest file
  at `t_execute` (`20261023T111849`, from `84ba0230`) has the same qubit-block digest as the
  reading's file, because IBM did not recalibrate between 09:34 and 11:18 that day. The control's
  code path ran (its own ref and archive walk), but its values were not exercised against a
  different reading. A dry run that must exercise them needs a `t_execute` after a sweep.
- **Arm B is reported, not judged** (criterion 4). Spearman over the six layouts and best-pick:
  truth 1, `reading` 1.000 and hit, `level` 0.371 and miss; truth 2, `level` 0.829 and miss,
  `reading` 0.714 and hit. Mean absolute fidelity error of the matching predictor 0.010 (truth 1)
  and 0.009 (truth 2). Under truth 2 the matching predictor did not pick the measured best: the
  three best measured layouts (85-77-86, 15-14-19, 128-127-129) lie within 0.008 of each other
  (0.549, 0.557, 0.553), a gap of the size of the terms the one builder omits (single-qubit
  depolarizing, relaxation during `cz`) and of the shot noise, so best-pick among six spanning
  layouts can turn on near-ties even for the right `T1`. `level`'s six predictions span 0.42 to
  0.57. This is a property of the design's Arm B scoring worth Bengisu's attention at 1c, not a
  pipeline fault.
- **Line endings and the controls hash.** `manifest.json`'s `controls_file_sha256`
  (`03c199e0...`) is the hash of `controls.json` as Python wrote it on Windows, with CRLF line
  endings. The repository stores and checks it out with LF (`.gitattributes`, `eol: lf`), and the
  stored blob hashes to `33682e65ea8708728bb1c34ff11b55b3fc6008a7bf7ef119bf8ba1e701f88748`; a
  desktop reproduction will see that value. Both name the same content. The cause is that the
  scripts write JSON with Python's default newline translation; the fix (write with `newline="\n"`)
  touches PR #132's `--mode controls` too and is owed before the freezing run, so that the frozen
  file's recorded hash is the hash every checkout sees.
- **Flagged qubits.** Truth 2 kept qubit 72 at its reading (no level); it is in no scored row.
  Aer capped `T2` at `2 T1` for qubit 148 in both truths; it is a discriminating qubit, but Arm A's
  population decay does not read `T2`, so the cap cannot move its rows.

## Amendments owed to the pre-registration at step 1c

Each is a dated line in the frozen table, so none is decided only in code:

1. Arm B eligibility: window floor 15; the controls may sit in a triple (Mert, 2026-10-28).
2. Arm B readout: exact probabilities from the density matrix, then the predictor's own
   assignment matrices applied analytically.
3. The `cz` channel: depolarizing from the latest `gate_error`, no relaxation, identical across
   predictors.
4. The band in Arm B: interval from the band's two ends, ranked by midpoint, scored for coverage.
5. The triple-spanning rule: ranks `round(i (n - 1) / 5)` under `level`.
6. Arm A scheduling: ALAP against one simultaneous measurement.
7. Design §6's `T1` characterisation moves to step 1d (Mert, 2026-10-28), with its environment
   and version logged there; `rep_delay` and `init_qubits` are also 1d's.
8. The bootstrap's resampling unit, after Bengisu's review.
9. Arm B links: only coupled pairs whose `cz` error satisfies `0 <= 4 r / 3 <= 1` (a dead pair,
   `gate_error = 1`, is not a link); amendment 1, 2026-10-28.

## Design decisions

- **Two truths, not one** (Mert, 2026-10-28, over the design's single `from_backend` truth): under
  the reading's snapshot alone `reading` wins by construction, which cannot show that the scoring
  would detect a `level` win.
- **Stacked on PR #132** (Mert, 2026-10-28): the dry run exercises the real selection; the
  alternative, a stub on `main`, tests less of what job 1 runs.
- **Analytic readout in Arm B** rather than sampling readout inside Aer: no simulation noise in
  any prediction, and the asymmetric assignment probabilities each predictor carries actually
  enter (Aer's `from_backend` would use the symmetric `readout_error`).
- **`thermal_relaxation_error` rather than a new Kraus builder:** ADR-027 pins the equivalence, and
  the LOCKED module stays untouched.
- **Design §6 out of this script** (Mert, 2026-10-28): Qiskit Experiments is not pinned.

## Verification

Planned: gates from the exact-pin interpreter, the new tests with a mutation check, and the dry
run's five criteria above. Done 2026-10-28, laptop, provisional until Burak's desktop rerun:

- `ruff check .`, `ruff format --check .`, `mypy --strict` (49 files): clean.
- `tests/test_hardware_reading_vs_level.py`: 41 tests, offline (synthetic inputs and the
  `ibm_fez` configuration and properties bundled with `qiskit_ibm_runtime`'s `FakeFez`). Full
  suite: 1,084 passed (1,043 on the #132 branch plus these 41).
- Mutation check: 20 deliberate breaks of the script (the minimum-length rule, duplicate slots,
  the lead delay, the closed form, the readout matrix and its axis, triple enumeration, the
  layout rounding, the delay relaxation, the `cz` parameter, the `T2 <= 2 T1` rule, dead pairs,
  truth 2's readout error, the clbit order, the band widening, the group weighting, the calendar
  axis, tie averaging, the best pick, the band's readout source); every one fails at least one
  test, and the file was restored from a backup copy. Two of my own fixtures were wrong at first
  (a tie order and a coverage value) and were corrected; the code was right both times.
- The dry run: the table above. To reproduce, from the worktree root with `PYTHONPATH=.;src`:

```bash
python -m scripts.hardware_reading_vs_level --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --at 2026-10-23T09:34:56Z --execution-ref 84ba0230738c9ee2773616b4e4c7142ba91180e3 --controls docs/evidence/hardware-reading-vs-level/dry-run-2026-10-28/controls.json --out <scratch>
```

  The outputs should match the committed ones file for file (fixed seeds; Aer's per-shot seeding
  is deterministic in the seed and independent of the thread count).

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, §2 to §7)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` on `mert/issue-125-preregistration`
  (proposal C, §3.3; the freeze checklist, §6)
- `docs/implementations/2026-10-28-hardware-test-selection-rules.md` (PR #132)
- `docs/roadmap/2026-10-23-phase-4-plan.md` §8 on PR #131 (step 1b)
- ADR-027 in `docs/decisions.md`; NC-087 and NC-090 (dated anchors, on the pre-registration
  branch)
- Issue #125
