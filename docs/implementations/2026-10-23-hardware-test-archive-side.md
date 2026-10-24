# 2026-10-23: hardware-test-archive-side

## Problem / Motivation

Issue #125 tests, on `ibm_fez`, whether a noise model should carry each qubit's calibration
**level** or its latest **reading**. The test compares four predictors fixed at submission
time; nothing in the repository could produce them. The archive-side half (Mert's, per the
design's ownership split) turns a pinned `calibration-data` ref into those predictors per
qubit and quantity, and proposes the qubit selection the pre-registration commit will freeze.
Plan: `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` (committed before the
code). Design: `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` on PR #124's
branch, approved by the lead on 2026-10-23.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/hardware_test_predictors.py` | New. Pure functions over an iterable of archive documents (`collect`, `predictor_rows`, `execution_rows`, `select_discriminating`, `propose_controls`, `write_outputs`) and a CLI that wires `training.dataset.iter_archive`; writes `predictors.tsv`, `selection.json`, `manifest.json`, and copies a supplied live document with its SHA-256. |
| `tests/test_hardware_test_predictors.py` | New. Eleven tests on synthetic documents in the archive schema: geometric-mean level and band bracketing, window edges, file-versus-state reading, the minimum-states rule, missing `T1`, the live override, execution mode, backend and time filters, malformed documents, the selection floor and ordering, the writer. |
| `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` | New. The plan, with its post-review amendments in place before the code. |
| `docs/implementations/2026-10-23-hardware-test-archive-side.md` | This record. |

Not touched: `src/`, LOCKED modules, the harness, the data branch, the offline half (Burak's).

## Implementation approach

One definition of each thing, reused from `main`: the archive walk and ref resolution from
`training.dataset` (PR #113), the distinct-state digest `qubit_block_digest` (the NC-012
unit), parsing and unit conversion from `calibration.loader.parse_snapshot`. Documents are
filtered on backend, parsed (failures counted, never fatal), dropped if later than `t_s`
(counted), sorted by `(last_update_date, path)`, and deduplicated into states in that order.
The `reading` is taken from the latest **file** at or before `t_s`; the level and band from
the **states** in the trailing 30 days; the two are different lookups on purpose (lesson
L-027 of the persistence protocol). A live `backend.properties()` document, when supplied,
replaces the reading, joins the window as a new state at `t_s`, and is copied to the output
with its hash so the reading can be re-derived later. `--mode execution` emits readings only,
for the `reading_at_execution` control.

Contract of `predictor_rows`: input a `Collected` archive, a tz-aware `at`, an optional live
document; output one `PredictorRow` per (qubit, quantity) with SI seconds for `T1` and `T2`
and dimensionless readout quantities; no I/O, no mutation of its inputs; `NaN` wherever a
value is missing or a rule is not met, never a silent number.

## Mathematical / Statistical details

For qubit `q`, quantity `x`, window `W = {states s : t_s - 30 d < time(s) <= t_s}`, and the
positive finite values `x_q(s)` over `W`:

- `level = exp( mean_{s in W} log x_q(s) )`, the geometric mean, defined only when at least 5
  values exist;
- `band = [exp(Q_0.10), exp(Q_0.90)]` of `{log x_q(s)}`, NumPy's default linear interpolation:
  this is NC-081's rolling band, not a fitted scale (which used `inverted_cdf`);
- `reading = x_q(latest file at or before t_s)`, or the live value;
- `log_disagreement = log(reading) - log(level)`, `NaN` if either is missing or non-positive;
- `n_distinct` = number of distinct finite values of `x_q` over all states at the ref up to
  `t_s`; the selection floor of 20 reads it.

Selection: the `k` qubits with the largest `|log_disagreement|` for `T1` among those with
`n_distinct >= 20`. Controls proposal: among qubits not selected and above the floor, the `k`
whose whole-archive sample standard deviation of `log T1` is nearest the median over qubits;
ties broken by qubit index. Geometric mean and log-space percentiles are used because the
per-qubit jumps are multiplicative (NC-084, NC-085) and the band must be a relative band.

## Design decisions

- **Pure functions, CLI as a thin wrapper.** The tests need no git; the offline half can
  import the functions; the CLI's only job is `iter_archive` and files.
- **Files for the reading, states for the window.** The L-027 lesson, written into both the
  plan and the docstring.
- **No channel here.** ADR-027's amplitude damping and the readout matrix are built once, in
  the offline half, from these raw quantities, so Arm A and Arm B share one noise model.
- **`scripts/`, not `src/`.** Nothing imports it yet; if the offline half wants it from the
  package, the move is a one-line follow-up under `training/`.
- **The script proposes the controls, the pre-registration commit decides them.** Proposals
  are a command the pre-registration can cite; the frozen list is a human decision.

## Verification

- `pytest tests/test_hardware_test_predictors.py -v`: 11 passed (pinned interpreter,
  Python 3.12.10).
- `ruff check` and `ruff format --check` on both files: clean (ruff 0.15.12).
- `mypy --strict` with no path argument (CI's invocation): no issues in 46 source files.
- Dry run against `calibration-data` @ `5828b4a29fabc245aa096e530852249a3496dc5b` with
  `--at 2026-10-23T09:34:56Z` (the archive's last timestamp), output to a scratch directory,
  not committed: 2,249 files used, 924 states, nothing skipped. The plan's three checks:
  1. `n_window` for `T1` is 264 for all 156 qubits, one value, as a state is a whole qubit
     block; the plan's "except qubit 72" did not apply because IBM has published qubit 72's
     `T1` again inside the window (29 distinct values over the archive, against 130 to 150 for
     the others).
  2. No `T1` row has its level outside its own band (zero violations over 156 qubits).
  3. The eight discriminating qubits all have `n_distinct >= 20`: 148 (`log_disagreement`
     -1.71), 108 (-1.11), 72 (-1.04, with only 29 distinct values), 132 (-0.87), 155 (-0.77),
     10 (-0.69), 80 (-0.67), 77 (-0.58). All eight disagree in the same direction: the current
     reading is below the 30-day level, so on this day the discriminating stratum is a set of
     qubits in a low excursion. Proposed controls at the median `log T1` scatter (0.293 to
     0.294): 105, 112, 48, 140.
  Three things for the pre-registration to decide, not this record: whether qubit 72 is
  admitted to the discriminating set given its history of omission (ADR-017, NC-027's lineage)
  and its thin `n_distinct`; whether a day on which every discriminating qubit sits below its
  level is representative, or whether the selection should balance the sign of the
  disagreement; and the delay grid, because disagreements of 0.6 to 1.7 log units are two to
  five times the 0.37 the design's Arm A sensitivity argument assumed, so delays centred on
  `T1_level` at `{0, 0.5, 1, 2}` sit at up to `{0, 1.5, 3, 6}` times `T1_reading` on the worst
  qubit: the `reading` predictor forecasts near-complete decay where `level` forecasts half.
  That is maximal power but a grid centred on one predictor favours it by construction; the
  pre-registration either adds the `reading`-centred delays (eight delays, roughly double Arm
  A's cost) or states the asymmetry and keeps four.
  Qubit 0 for scale: reading 52.96 µs, level 50.74 µs, band 44.95 to 56.49 µs, disagreement
  +0.043; its readout error 0.0215 against a level of 0.0255 in a band 0.0204 to 0.0316.

### Correction, 2026-10-24

Appended rather than edited in place, so the dry run's text above stays as it was first
recorded. Three statements in it are wrong:

- **Check 1, "130 to 150 for the others".** At the same ref and instant, `n_distinct` for `T1`
  (the column this script writes to `predictors.tsv`) is 29 for qubit 72, **52 for qubit 11, 89
  for qubit 17**, and 130 to 152 for the other 153 qubits. The range given above leaves out
  qubits 11 and 17 and understates the top by two. Rerunning the dry-run command above and
  reading the `T1` rows of `predictors.tsv` reproduces these; they were recomputed with this
  branch's own `predictor_rows` on 2026-10-24 over the same 2,249 files and 924 states.
- **Check 3, qubit 155's disagreement.** It is -0.7647, which rounds to -0.76, not -0.77. The
  selection and its order are unaffected.
- **The delay-grid sentence, "a grid centred on one predictor favours it by construction".**
  Under the design's own Arm A score (mean absolute error in `p_1` over the delays, the truth
  between the two predictions), a grid centred on one predictor favours the **other** one: the
  centred prediction sits on the steepest part of the decay curve, where the same miss in
  `log T1` costs it the most. The design's level-centred grid therefore favours `reading`, not
  `level`, at both signs of the disagreement. The computation, with tests, is
  `scripts/hardware_test_grid_bias.py` on the local pre-registration branch
  `mert/issue-125-preregistration` (register row NC-087 there), which is not yet pushed; until it
  lands, that branch is the source. The pre-registration's delay-grid decision was taken on the
  corrected reading.

## Related docs

- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md`
- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (PR #124's branch)
- `docs/evidence/persistence-band/README.md` §2.1 item 1 and lesson L-027;
  `docs/evidence/predictability/README.md` §3.5
- `docs/numerical-claims.md` NC-012, NC-081, NC-084, NC-085
- Issue #125; PR #113 (`training/dataset.py`)
