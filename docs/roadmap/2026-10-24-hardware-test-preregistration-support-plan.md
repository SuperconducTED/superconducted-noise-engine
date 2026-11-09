# #125 pre-registration support: the check-up floor, the delay-grid bias, and the draft

**Date**: 2026-10-24 · **Author and owner**: Mert Efe Şensoy · **Status**: plan before code, per
the engineering standard; written on the local branch `mert/issue-125-preregistration`, not
pushed · **Supports**: the pre-registration commit of Issue #125, which the design
(`docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` §8) requires before job 1 ·
**Builds on**: PR #126 (`scripts/hardware_test_predictors.py`, the archive side) and PR #124 (the
design), both still open; this branch merges their two heads locally and is rebuilt onto `main`
once #121, #123, #124 and #126 land

## 1. What this plan covers, and what it leaves alone

PR #126's dry run left three questions the pre-registration has to answer, and a scratch check
on 2026-10-24 showed the premise of the third one was backwards. Three pieces of work prepare
the answers; none of them answers them. The decisions stay the lead's.

| Piece | What it produces | Feeds |
| --- | --- | --- |
| 1. Check-up floor measurement | how many qubits each candidate floor excludes, day by day over the archive, and what that does to qubit 72 and to the eight-qubit selection | decision A |
| 2. Delay-grid bias script | a tested, rerunnable computation of which point predictor each candidate delay grid favours under the design's scoring rule | decision C |
| 3. Pre-registration draft | the document the pre-registration commit will freeze, with A, B, C and D written as **proposals** | all four |

Measurement 1 also records two descriptive figures at no extra cost: the sign composition of
each day's eight-qubit selection (the premise of decision B) and the longest delay the union
grid would ask for (input to the offline half's circuit construction).

Not touched: `src/`, the LOCKED modules, `benchmarks/harness.py`, the `calibration-data` branch,
`scripts/hardware_test_predictors.py` (PR #126's file; this work imports it and changes
nothing in it), and the offline half (Burak's). Nothing is submitted to a QPU. Nothing is pushed
or posted.

## 2. The four decisions the draft will carry

| Id | Question | Proposal the draft will carry | Evidence it waits on |
| --- | --- | --- | --- |
| A | Which qubits may enter the discriminating stratum | replace the whole-archive "at least 20 distinct values" floor with a floor on distinct `T1` values **inside the 30-day window**, the window the level is computed from; the floor's value is chosen from measurement 1 | measurement 1 |
| B | Whether the eight discriminating qubits balance the sign of the disagreement | four with the reading below the level and four above, each ranked by the size of the disagreement; a short side is filled from the other and logged | measurement 1's sign composition |
| C | The Arm A delay grid | the union of a level-centred and a reading-centred grid, seven delays per qubit | measurement 2 |
| D | The order of control and discriminating selection | the four controls are frozen first with nothing excluded, as the design's §3 says ("without reference to any current reading"); the daily discriminating selection then excludes them. PR #126's CLI does the reverse | measurement 1's control check |

Decision A is an **amendment** to an approved design: §3 says "at least 20 re-measurement events
in the archive", and PR #126 implements that faithfully as `n_distinct` over all states up to
`t_s`. The draft presents the window rule for the lead to accept or refuse, not as the rule.

The draft also records the lead's word of 2026-10-24 that the QPU budget is covered: the
usage-page check stops being a blocker, the 25-second gate after job 1 stops being a gate, and
the per-job QPU time is still logged.

## 3. Piece 2: `scripts/hardware_test_grid_bias.py`

### 3.1 The question in one line

Under the design's Arm A score (mean absolute error between measured and predicted `p_1` over
the delays of one qubit), does the choice of delays tilt the comparison between `reading` and
`level`?

### 3.2 Contract

Pure functions, no I/O except the CLI writer:

| Function | Inputs | Output |
| --- | --- | --- |
| `decay_probability(tau, t1, *, prob_meas0_prep1=0.0, prob_meas1_prep0=0.0)` | delays (array, any unit), `T1` (same unit, positive), the two assignment probabilities in `[0, 1)` | `p_1 = e01 + (1 - e01 - e10) * exp(-tau / T1)`, the design §3 first-order form, elementwise |
| `delay_grid(name, t1_reading, t1_level)` | one of `level`, `reading`, `union`, `midpoint`; two positive `T1` values | sorted distinct delays: `{0, 0.5, 1, 2} x T1_level`; the same times `T1_reading`; the union of the two (seven delays when the two differ); `{0, 0.5, 1, 2} x sqrt(T1_reading T1_level)` |
| `expected_abs_error(delays, t1_pred, t1_true, *, shots=None, readout=(0.0, 0.0))` | the above, `shots` a positive integer or `None` | mean over delays of `E | p_hat - p_pred |`; with `shots=None`, `p_hat = p_true` (noiseless); with `shots = n`, the exact binomial expectation `sum_k Bin(k; n, p_true) | k/n - p_pred |` |
| `tie_point(grid, d, *, shots=None)` | grid name, signed disagreement `d = log T1_reading - log T1_level` (non-zero) | the truth position `a*` in `[0, 1]` at which `level` and `reading` score equally, by bisection; `NaN` with a reason if the score difference does not change sign on `[0, 1]` |

The truth position: `log T1_true = log T1_reading + a (log T1_level - log T1_reading)`, so `a = 0`
puts the truth on the reading and `a = 1` on the level. `a* = 0.5` is a neutral grid; `a* > 0.5`
means the level has to sit nearer the truth than halfway to win, so the grid favours the reading;
`a* < 0.5` favours the level. Everything depends on `tau / T1` only, so `T1_level = 1` without
loss of generality.

### 3.3 Tests, `tests/test_hardware_test_grid_bias.py`

| Test | Pins |
| --- | --- |
| endpoints | at `a = 0` the reading scores strictly better, at `a = 1` the level does, for every grid, both signs, noiseless and `shots=2048` |
| readout invariance | noiseless `a*` is unchanged by a common readout (`e01 = e10 = 0.02`): the readout is an affine map applied to both predictions and the truth, so every absolute error is multiplied by the same `1 - e01 - e10` |
| union mirror | for the union grid, `a*(+d) = 1 - a*(-d)`: the grid is symmetric under exchanging the two predictors |
| shots never help | `expected_abs_error` with `shots` is at least the noiseless value at every point (Jensen) |
| the finding | the level-centred grid gives `a* > 0.5` for every `d` in the dry run's range (`-1.71` to `-0.58`), the guard against a regression to the record's premise |
| grids | the union has seven distinct delays when the two `T1` differ and four when they are equal; every grid starts at 0 |
| input validation | non-positive `T1`, an unknown grid name, `d = 0` and non-positive `shots` raise `ValueError` |

The finding test and the mirror test are mutation-checked: each is run against a deliberately
broken copy of the function it guards (the grid swapped, the mirror broken) and must fail;
mutants are restored from a backup copy, never with `git checkout --`.

### 3.4 Run

`python -m scripts.hardware_test_grid_bias --out docs/evidence/hardware-reading-vs-level/`
writes `grid-bias.tsv`: one row per (grid, `d`, shots setting), with `a*`, the number of distinct
delays, and the mean absolute errors at `a = 0.5`. The `d` values and grids are fixed in the
evidence README §3 before the run.

## 4. Piece 1: `docs/evidence/hardware-reading-vs-level/measure_checkup_floor.py`

A measurement script in the evidence folder, the same pattern as
`docs/evidence/predictability/measure_predictability.py`. It imports PR #126's `collect`,
`predictor_rows`, `select_discriminating` and `propose_controls`, so the selection it measures is
the one the test will run; it adds only the window count. Collecting the archive takes about nine
minutes on the laptop (one `git show` per file, 2,249 files) and one `predictor_rows` call about
one second, measured on 2026-10-24 before this plan was written, so the script collects once and
loops over the days.

The protocol (definitions, evaluation instants, candidate floors, outputs and the reproduction
guard that runs first) is the evidence README §2, committed with this plan and before the
script.

## 5. Piece 3: the pre-registration draft

`docs/roadmap/2026-10-24-issue-125-preregistration.md`, status **draft, not frozen**. It names
what the commit that freezes it waits on: the lead's answers on A to D; Bengisu's statistics
review of the design's §7 decision rule; Burak's dry run of the offline half; PR #120 merging.
It freezes, once those are in: the selection rules (A, B, D), the four control qubits, the delay
grid (C), shots, the decision rule's thresholds as §7 states them (no number changed), the
budget note, and the evaluation instants of the 14 jobs (the fixed UTC hour is left for the
lead). Two register rows support it, NC-087 and NC-088 (both checked free on every remote branch
and every local worktree on 2026-10-24); their forms differ, because NC-088 is an archive
measurement and NC-087 is a computation with no archive input.

## 6. Order of work

1. This plan and the evidence README protocol, committed before any code or new number.
2. The grid-bias script and its tests; the floor measurement script.
3. Both runs; outputs committed.
4. The draft, the two register rows, the implementation record.

## 7. Verification

- `pytest tests/test_hardware_test_grid_bias.py tests/test_hardware_test_predictors.py -v`
- full collection: `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider`
- `ruff check` and `ruff format --check` with the pinned ruff 0.15.12
- `mypy --strict` with no path argument, CI's invocation, whose scope includes `scripts/`
- `python scripts/check_ids.py` (or the repository's id check) for NC-087 and NC-088
- the floor measurement's reproduction guard (README §2.1) passing before any per-day figure is
  read
