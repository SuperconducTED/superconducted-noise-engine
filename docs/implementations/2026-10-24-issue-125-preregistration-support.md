# 2026-10-24: issue-125-preregistration-support

## Problem / Motivation

Issue #125's hardware test may not submit a job before a pre-registration commit freezes its
selection rules, control qubits and delay grid (design
`docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` §8). PR #126's dry run left three
questions open: whether qubit 72 enters the discriminating stratum, whether the selection
balances the sign of the reading-versus-level disagreement, and the delay grid. A scratch check
on 2026-10-24 then found that the third question's premise in PR #126's record ("a level-centred
grid favours the level by construction") is backwards under the design's own score. The lead
asked for three things on 2026-10-24: measure a check-up floor on the archive, save the grid
check as a tested script with a plan first, and draft the pre-registration on a local branch,
with nothing pushed or posted. The lead also stated that the QPU budget is not a constraint.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-24-hardware-test-preregistration-support-plan.md` | New. The plan, committed before any code: the three pieces, the four decisions they feed, the script's contract and tests, the order of work. |
| `docs/evidence/hardware-reading-vs-level/README.md` | New. The protocol of both measurements, committed before either produced a committed number, with the disclosure that a scratch computation preceded it; results appended in §4. |
| `scripts/hardware_test_grid_bias.py` | New. Pure functions for the Arm A first-order `p_1`, the four candidate grids, the exact binomial expected absolute error, and the tie point by bisection; a CLI that writes `grid-bias.tsv`. |
| `tests/test_hardware_test_grid_bias.py` | New. 56 cases: endpoints, readout invariance, the union grid's mirror symmetry, Jensen's inequality for shot noise, the directional finding, grid shapes, the design's `p_1` form, input validation, the writer. |
| `docs/evidence/hardware-reading-vs-level/measure_checkup_floor.py` | New. The floor measurement: reuses PR #126's `collect`, `predictor_rows`, `select_discriminating` and `propose_controls` unchanged, runs a reproduction guard against PR #126's recorded dry run first, then evaluates every day of the archive. |
| `docs/evidence/hardware-reading-vs-level/grid-bias.tsv`, `grid-bias-manifest.json` | New. Measurement 2's 144 rows and its parameters. |
| `docs/evidence/hardware-reading-vs-level/checkup-floor-*.tsv`, `checkup-floor-*.json` | New. Measurement 1's per-day and per-qubit tables, the control check, and the summary with the guard's outcome. |
| `docs/roadmap/2026-10-24-issue-125-preregistration.md` | New. The pre-registration **draft**, status not frozen: what the design fixes, restated; proposals A to D for the lead; the budget note; what the freezing commit waits on. |
| `docs/numerical-claims.md` | Four rows appended after NC-086: NC-087 (grid bias, a computation, no archive ref) and NC-088 to NC-090 (the check-up floor and controls, the sign composition and proposal B's cost, the union grid's delay span; archive measurements in the Rule 7 form). The plan named two rows; the measurement produced three distinct conclusions, and the register's rule is one row per conclusion. |
| `docs/implementations/2026-10-24-issue-125-preregistration-support.md` | This record. |

Not touched: `src/`, the LOCKED modules, `benchmarks/harness.py`, the `calibration-data` branch,
`scripts/hardware_test_predictors.py` (PR #126's file, imported, not changed), the offline half.

**The branch.** `mert/issue-125-preregistration` is local and unpushed. It starts at PR #126's
head `d62928fa` and merges PR #121's head `04361fe6` and PR #124's head `951258da` (merge commits
`f04398d7`, `f53ecdb1`), only so the design, the register rows up to NC-086 and the predictor
script are in one tree. Those two merges are scaffolding: when #121, #123, #124 and #126 have
merged, this work is rebuilt onto `main` and every commit named in NC-087 to NC-090 is re-pinned.

## Implementation approach

**Plan, protocol, code, run, record, in that order**, the shape the 2026-10-23 measurements
used: the plan and the evidence README's protocol were one commit (`f3a5b627`) before any code;
the grid script and tests were the next (`d6ed7885`); its output came after (`d75de42d`). The
floor script was committed (`be2f8e52`) and run first as a scratch run over a cached collection,
to protect a ten-minute archive walk from a late crash. That scratch output prompted two dated
amendments to the protocol (README §6.1, columns for proposal B's cost, `e2c38721`; §6.2, the
control scatter and the extreme-delay qubits, `b6852203`), each disclosed as added after seeing
data and therefore not blind. The record run of the committed script came last (`dfaf0cd7`) and
matched the scratch output file for file.

**The grid script** computes, for a signed disagreement `d` and a grid, the difference between
the level's and the reading's expected Arm A score as a function of the truth's position `a`, and
finds its zero by bisection after checking the sign at both ends; a 21-point scan counts sign
changes so a second crossing would be visible (none occurs). Everything is in units of
`T1_level`, since the score depends on `tau / T1` only.

**The floor script** collects the archive once (about nine minutes on the laptop, one `git show`
per file), then evaluates each day by slicing the collected states, which reproduces exactly what
`collect(..., until=t)` would return because states are first occurrences in time order. The
window count is the only new quantity; the selection itself is PR #126's function, fed the window
count in place of `n_distinct` through `dataclasses.replace`, so a window rule and the current rule
run through the same selection code.

## Mathematical / Statistical details

**Arm A prediction** (design §3): `p_1(tau) = e01 + (1 - e01 - e10) exp(-tau / T1)`, with
`e10 = prob_meas0_prep1`, `e01 = prob_meas1_prep0`.

**Score**: for predictor `P` on one qubit, `S_P = (1 / |G|) sum_{tau in G} E | p_hat(tau) - p_1(tau; T1_P) |`.
Noiseless, `p_hat = p_1(tau; T1_true)`. With `n` shots, `p_hat = K / n` with
`K ~ Binomial(n, p_1(tau; T1_true))`, and the expectation is the exact finite sum over `k`, the
probabilities computed in log space from cumulative log factorials.

**Truth position**: `log T1_true = log T1_R + a (log T1_L - log T1_R)`. The tie point `a*` solves
`S_L(a) = S_R(a)`. At `a = 0` the reading scores zero noiseless error and the level does not, so
`S_L - S_R > 0`; at `a = 1` the reverse.

**Why a centred grid favours the other predictor.** As a function of `u = log T1`, `p_1` at fixed
`tau` is `exp(-tau e^{-u})`, a Gompertz curve steepest at `T1 = tau`. Centring the grid on `T1_L`
puts the level's predictions at the steep points, so a given miss in `log T1` costs the level more
`p_1` error than the same miss costs the reading, whose predictions sit on the flatter tail.

**Readout invariance.** With a readout common to the prediction and the truth,
`p_1 = e01 + c s` with `c = 1 - e01 - e10` for both, so every noiseless absolute error is `c`
times its ideal value and `a*` is unchanged.

**Union mirror.** The union grid is symmetric under exchanging the two `T1` values; exchanging
them maps `d` to `-d` and `a` to `1 - a`, so `a*(d) = 1 - a*(-d)`.

**Window count** (measurement 1): `w_q(t)` = the number of distinct finite positive `T1` values
of qubit `q` over the states in `(t - 30 d, t]`; the modal share is the largest count of one value
over the number of window states.

## Design decisions

- **A script and tests for the grid check, not a notebook cell**, because its result reverses a
  premise written into PR #126's record and becomes a register row; it has to be rerunnable and
  guarded. The directional test and the mirror test were mutation-checked (the level grid built
  on the reading, the union made asymmetric, the readout applied to one side only): each mutant
  failed its guard, and the file was restored from a backup copy and compared byte for byte.
- **The floor script reuses PR #126's selection instead of reimplementing it**, so what is
  measured is what the test will run, and a guard against PR #126's recorded dry run runs first.
- **The window rule is offered as an amendment**, not applied: the design's floor is approved and
  PR #126 implements it faithfully. The draft carries every decision as a proposal, because the
  lead had not answered the three questions when the work was asked for.
- **Ideal readout in the grid computation**: the noiseless tie point is invariant to a shared
  readout (proved above, pinned by a test). The design gives each predictor its own readout source;
  that separate effect is named in the README and not modelled.
- **Union over midpoint as the proposal**: equal residual lean (within 0.0003), but the union gives
  each predictor its own most sensitive delays, and the budget is not a constraint.

## Verification

Run from the repository root with a venv built from the exact pins (`requirements.txt` plus
`requirements-dev.txt`, then `pip install -e . --no-deps`, as CI does):

- `pytest tests/test_hardware_test_grid_bias.py tests/test_hardware_test_predictors.py -v`
- `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider`
- `ruff check .` and `ruff format --check .` (ruff 0.15.12)
- `mypy --strict` (no path argument; scope `src/superconducted` and `scripts`)
- `python scripts/check_ids.py`
- `PYTHONPATH=src python -m scripts.hardware_test_grid_bias --out <dir>` reproduces
  `grid-bias.tsv` byte for byte
- the floor command in the evidence README §5 passes its guard and reproduces the committed
  `checkup-floor-*` files

**Results, 2026-10-24, laptop, on a venv built from the exact pins** (`C:/t/pin125`: Python
3.12.10, NumPy 2.4.4, Qiskit 2.4.1, pytest 9.0.3, mypy 1.20.2; ruff 0.15.12 from its own pinned
venv):

- the new and PR #126's tests: 67 passed;
- the full suite: **942 collected, 942 passed** at `be2f8e52` (main's 875 at `88fa6a40`, plus PR
  #126's 11, plus this work's 56). This is a local tree, not `main`; NC-021 is re-measured at the
  merge commit when this lands (Rule 6), not edited now;
- `mypy --strict` (CI's invocation): no issues in 47 source files;
- `ruff check .` and `ruff format --check .`: clean;
- `scripts/check_ids.py`: no duplicate or colliding ADR or NC identifiers (NC-087 to NC-090 were
  also checked free on every remote branch and every local worktree before use);
- mutation checks: three mutants (level grid built on the reading; union made asymmetric;
  readout applied to the prediction only) each failed their guard tests (6, 6 and 12 failures);
  the file was restored from a backup copy and compared identical, and the suite passed again;
- `grid-bias.tsv`: a second run on the pinned venv reproduces the committed file byte for byte
  after line-ending normalisation;
- the floor measurement: the guard passed; the record run of the committed script (`b6852203`,
  outputs at `dfaf0cd7`) gives the same per-day, per-qubit and control outputs as the scratch runs
  that preceded it, file for file.

**What was not verified.** The canonical reproduction of the floor measurement on Burak's
desktop. CI, since nothing is pushed. Whether the union grid's 0.84 µs to 799 µs delays fit the
backend's `dt` and circuit-duration limits (the offline half's construction, not checked here).

**A finding about PR #126's record.** Its Verification section gives the whole-archive distinct
counts as "130 to 150 for the others" beside qubit 72's 29; at the same instant qubit 11 has 52
and qubit 17 has 89 (`checkup-floor-qubits.tsv`). That record is a dated document on another
branch and is not edited here; the pre-registration draft cites the measured figures.

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, PR #124)
- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md`,
  `docs/implementations/2026-10-23-hardware-test-archive-side.md` (PR #126)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` (the draft)
- `docs/evidence/hardware-reading-vs-level/README.md`
- `docs/numerical-claims.md` NC-084, NC-085, NC-087 to NC-090
- Issue #125
