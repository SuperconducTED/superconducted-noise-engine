# 2026-10-28: hardware-test selection rules (proposals A, B and D for #125)

> Status at the plan commit: **plan, no code yet**. The sections below state what will be built
> and why; the Verification section is filled in after the implementation, in a later commit.

## Problem / Motivation

The #125 pre-registration draft (branch `mert/issue-125-preregistration`, section 3.5, the lead's
decisions of 2026-10-24) accepted four proposals that change how the hardware test picks its
qubits. Three of them, A, B and D, change `scripts/hardware_test_predictors.py` (PR #126, merged
as `2e2801cd`), which still implements the design's original rules:

- the discriminating stratum admits a qubit on at least 20 distinct `T1` values over the whole
  archive up to `t_s` (qubit 72 passes with 29 although its 30-day window holds 6, NC-088);
- it takes the eight largest `|d|` regardless of sign (all eight were dips on 53 of 132 days,
  NC-089);
- the submission run proposes the four controls *after* the discriminating eight, excluding them,
  so the controls depend on that day's readings and a control can later become discriminating.

The pre-registration cannot be frozen, and job 1 cannot run, until the code applies the accepted
rules. This is step 1a of the build order in plan section 8 (on PR #131, head `e5c75c3b`, not yet
on `main`).

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/hardware_test_predictors.py` | Adds the in-window distinct count, the sign-balanced selection with a floor of 15, a `controls` mode that freezes the four controls first, and a submission mode that requires the frozen controls file (or an explicit dry-run override). |
| `tests/test_hardware_test_predictors.py` | Pins every rule above on synthetic archives, including the fill, the zero-disagreement case, tie order, control exclusion and the CLI refusal. |
| `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` | A dated as-of note pointing at the new CLI; the original text is left as written. |
| `docs/implementations/2026-10-28-hardware-test-selection-rules.md` | This record. |

## Implementation approach

Existing functions keep their behaviour; the new rules are added beside them. The reason is step
1c of the build order: the pre-registration's measurement scripts (`measure_checkup_floor.py` and
others on `mert/issue-125-preregistration`) import `select_discriminating`, `propose_controls` and
`PredictorRow` from this module and must reproduce NC-087 to NC-091 when that branch is rebuilt
onto `main`. Changing those functions' semantics would silently change a registered figure.

1. **`PredictorRow.n_window_distinct`** (new trailing field, default 0, so the positional
   constructor in `execution_rows` and any caller elsewhere still works): the number of distinct
   finite positive values of the quantity among the states inside the 30-day window. Added as the
   last column of `predictors.tsv`. `n_distinct` keeps its whole-archive meaning.
2. **`select_balanced(rows, *, k, min_window_distinct, controls)`** (new): returns the selection
   and its log as one dictionary. Candidates are `T1` rows with a finite `d`, an in-window count of
   at least the floor, and a qubit outside the frozen controls. They split into `d < 0` (below the
   level) and `d > 0` (above it), each ranked by `|d|` descending with ties broken by qubit index.
   The selection takes `k/2` from each side; if a side has fewer, its missing places go to the
   other side's next-largest `|d|` beyond its own `k/2`. The log records the admitted count per
   side, the qubits with `d == 0`, the qubits below the floor, the short side, the side the fill
   came from and how many places were filled. `k` must be even and positive.
3. **`freeze_controls(collected, rows, *, k, min_window_distinct)`** (new): computes the set of
   qubits whose in-window `T1` count is below the floor and calls the unchanged `propose_controls`
   with that set as its only exclusion. `propose_controls` keeps its own whole-archive floor of 20
   underneath, as proposal D's accepted text says. Nothing in it depends on a reading.
4. **CLI.** A third mode, `--mode controls`, writes `controls.json` (ref, ref SHA, backend, `at`,
   both floors, the qubits below the window floor, the four controls with their scatter) plus the
   manifest. It refuses `--live-properties`, since the controls come from the archive at the
   freezing ref only. `--mode submission` now needs `--controls <controls.json>`; it checks that
   the file names the same backend, excludes its qubits from the discriminating stratum, and
   records the file's SHA-256, its ref and its qubits in the manifest. Without the file it exits
   with code 2 unless `--no-frozen-controls` is passed, which is for archive dry runs only and
   records `controls: null` in the manifest and the selection (Mert's choice, 2026-10-28). Passing
   both is an error. `selection.json` no longer carries `proposed_controls`; the controls come
   from the frozen file.

## Mathematical / Statistical details

Notation, per qubit `q` at submission time `t_s`: `W_q` is the set of device states in
`(t_s - 30 d, t_s]` (states, not files: a state is the first file of a distinct qubit block),
`T1_level` the geometric mean of the finite positive `T1` values over `W_q`, `T1_reading` the value
in the latest file at or before `t_s` (or the live document), and
`d_q = log T1_reading - log T1_level`.

- **Proposal A, the window floor.** `w_q = |{ T1 value of s : s in W_q, finite, > 0 }|`, a count of
  distinct values, not of states. A qubit is admitted when `w_q >= 15`. The level is an average
  over `W_q`; when `w_q` is small the level is mostly one value carried across many states and the
  comparison is against a stale number. On the record (NC-088, dated anchor, `calibration-data`
  `5828b4a2`): 153 of 156 qubits have 28 to 31, the others 3, 6 and 13; 15 sits in that gap.
  One divergence from NC-088's own count: on job day a live document whose qubit block is new
  joins `W_q` (as it already does for `n_window` and the level), so `w_q` can be one larger than an
  archive-only count. Against a gap from 13 to 28 this cannot move a qubit across 15.
- **Proposal B, the sign split.** With `k = 8`, the four largest `|d_q|` among admitted `d_q < 0`
  and the four largest among admitted `d_q > 0`. A short side is filled from the other side by
  `|d|`; `d_q = 0` belongs to neither side and is never selected. The decision rule stays pooled
  over the eight. Why the balance matters for the score: `p_1(tau) = exp(-tau / T1)` is, in
  `u = log T1`, a Gompertz curve steepest at `T1 = tau`, so any delay grid favours the predictor
  whose `T1` the grid sits nearer. NC-087 (dated anchor) shows the seven-delay union grid leans at
  most 0.03 in tie point toward the shorter `T1`, which is the reading for a dip and the level for
  a rise; equal numbers on each side cancel that lean in the pooled mean absolute error to first
  order.
- **Proposal D, controls first.** The controls are the `k = 4` qubits whose whole-archive sample
  standard deviation of `log T1` (states up to the freezing instant, `ddof = 1`) is nearest the
  median over eligible qubits, ties by qubit index (the unchanged `propose_controls`). Eligible
  means at least 20 distinct whole-archive values and `w_q >= 15` at the freezing instant. The
  four are then excluded from every job's discriminating candidates.

No new figure is produced. The reproduction check below re-derives registered values only.

## Design decisions

- **New functions beside the old ones, not a change to `select_discriminating`.** Rejected
  alternative: change the old function's floor and ordering in place. That breaks the step-1c
  reproduction of NC-088 against `main` without any test failing in this repository.
- **A new TSV column rather than redefining `n_distinct`.** Same reason; NC-088's script injects
  window counts through `replace(r, n_distinct=...)` and relies on `n_distinct` being the
  whole-archive count.
- **Refusal without a controls file** (Mert, 2026-10-28, over "allow and mark null"): a real job
  that silently ran without the frozen four would violate proposal D, and nothing goes to the QPU
  before the freezing commit. The override exists so archive dry runs (step 1b) do not need a
  frozen file.
- **`d == 0` excluded, fewer than eight when too few are admitted.** A zero disagreement cannot
  discriminate between the predictors; selecting it would only pad the count. The fill and the
  shortfall are written into `selection.json` and printed, so a short job is visible.
- **The controls mode refuses a live document.** Proposal D fixes the controls from the archive
  at the freezing ref; a live document would make them depend on that morning's reading.
- **The reproduction is recorded here, not in the register** (Mert, 2026-10-28). NC-088 is
  re-pinned in step 1c anyway. No NC row is minted by this change; the next free id stays NC-095.

## Verification

To be filled after the implementation: the gates from the exact-pin interpreter, the new tests,
and the reproduction at `calibration-data` `5828b4a2`, `at = 2026-10-23T09:34:56Z`, which must
give controls 48, 112, 54 and 105 (NC-088, `checkup-floor-controls.json`, `w15.controls_first`),
in-window counts 3, 6 and 13 for qubits 11, 72 and 108, and `select_discriminating` on the
injected window counts at floor 15 equal to `w15.top8`.

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, sections 3 and 5)
- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` (PR #126's plan)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` on `mert/issue-125-preregistration`,
  sections 3.1, 3.2, 3.4 and 3.5
- `docs/roadmap/2026-10-23-phase-4-plan.md` section 8 on PR #131 (step 1a)
- NC-087 to NC-089 (dated anchors): registered in `docs/numerical-claims.md` on
  `mert/issue-125-preregistration`, not yet on `main`; they reach `main` with step 1c
- Issue #125
