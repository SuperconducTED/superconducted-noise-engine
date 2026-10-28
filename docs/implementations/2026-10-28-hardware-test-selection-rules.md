# 2026-10-28: hardware-test selection rules (proposals A, B and D for #125)

> Status at the plan commit (`6280ac42`): **plan, no code yet**. Implemented in `cf1425bd`; the
> Verification section was filled in afterwards, in a later commit.

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
| `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` | A dated as-of section 8 pointing at the new CLI; sections 1 to 7 are left as written. |
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

Status at the plan commit: the paragraph below was the target. Filled in on 2026-10-28 after
the implementation, laptop, exact-pin interpreter (`C:/t/pin125`, Python 3.12.10, NumPy 2.4.4).

**Gates.** From the worktree root with `PYTHONPATH=src`:

- `ruff check .` and `ruff format --check .` (ruff 0.15.12): clean.
- `mypy --strict` (the `[tool.mypy] files` set, which includes `scripts/`): no issues in 48 files.
- `pytest tests/ -q`: 1,043 passed. `tests/test_hardware_test_predictors.py` went from 39
  collected tests on `main` to 63; the old tests pass with one change, the shared CLI helper
  `_run_cli` passing `--no-frozen-controls` in submission mode.

**Mutation check of the new tests.** Nine mutants of the script, each on a fresh copy restored from
a backup: dropping the control exclusion, `>=` to `>` at the floor, reversed tie order, `d == 0`
joining the lower side, no fill of the upper side, counting NaN in the window, no exclusion in
`freeze_controls`, no refusal without a controls file, and a live document accepted in controls
mode. On the first pass eight failed at least one test; the upper-side fill survived, so
`test_short_lower_side_is_filled_from_the_upper_side` was added and the mutant then failed.

**Reproduction of registered values** (NC-088; no new figure). At `calibration-data`
`5828b4a29fabc245aa096e530852249a3496dc5b`, `at = 2026-10-23T09:34:56Z`, backend `ibm_fez`, the
walk read 2,249 files and 924 states, as the NC-088 record did. Expected values from
`docs/evidence/hardware-reading-vs-level/checkup-floor-controls.json` on
`mert/issue-125-preregistration`:

| Check | Expected | Got |
| --- | --- | --- |
| `freeze_controls(k=4)` | `w15.controls_first` = 48, 112, 54, 105 | 48, 112, 54, 105 |
| `n_window_distinct` for qubits 11, 72, 108 | 3, 6, 13 | 3, 6, 13 |
| `select_discriminating` on window counts injected as `n_distinct`, floor 15 | `w15.top8` = 148, 132, 155, 10, 80, 77, 2, 40 | the same eight, same order |
| `--mode controls` through the CLI | the same four | 48, 112, 54, 105; below the floor: 11, 72, 108 |

Commands. Rows 1, 2 and 4 come from the committed CLI: `controls.json` names the four, and the
`n_window_distinct` column of the `predictors.tsv` it writes beside it carries the counts for
qubits 11, 72 and 108 (`T1` rows).

```bash
python -m scripts.hardware_test_predictors --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --at 2026-10-23T09:34:56Z --mode controls --out <scratch>/freeze-5828
```

Row 3, from the worktree root with `PYTHONPATH=.;src` (Windows) or `.:src`:

```python
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from scripts.hardware_test_predictors import collect, predictor_rows, select_discriminating
from superconducted.training.dataset import iter_archive

at = datetime(2026, 10, 23, 9, 34, 56, tzinfo=UTC)
ref = "5828b4a29fabc245aa096e530852249a3496dc5b"
col = collect(iter_archive(Path("."), ref), backend="ibm_fez", until=at)
rows = [r for r in predictor_rows(col, at=at, live=None) if r.quantity == "T1"]
injected = [replace(r, n_distinct=r.n_window_distinct) for r in rows]
print([p["qubit"] for p in select_discriminating(injected, k=8, min_distinct=15)])
# expected: [148, 132, 155, 10, 80, 77, 2, 40]
```

This is the same injection NC-088's `measure_checkup_floor.py` makes, with the window count now
computed by `predictor_rows` instead of by that script.

Each walk takes about 7 to 8 minutes on the laptop (one `git show` per file). This checkout is a
partial clone: 970 blobs at `5828b4a2` were missing and were fetched first in batches of 200
(`git rev-list --objects --missing=print <ref>` lists them).

The sign-balanced eight at that instant is a new output of a new rule. It was not computed for
this record and is not quoted. It belongs to the freezing ref's dry run (step 1c).

## Fix, 2026-10-28 (later): JSON written with LF on every platform

Found while building the offline half on top of this branch
(`docs/implementations/2026-10-28-hardware-test-offline-half.md`, on
`mert/issue-125-offline-half`, its owed item 12). The script wrote `controls.json`,
`selection.json` and `manifest.json` with Python's default newline translation, so on Windows
they carried CRLF. The repository stores them with LF (`.gitattributes`), so the controls file's
SHA-256 that `--mode submission` records in a job's manifest would be the hash of the CRLF bytes
as written on the laptop, a value no checkout reproduces (the offline half's dry run recorded
`03c199e0...` for a file whose stored blob hashes to `33682e65...`). That would make the frozen
controls file's provenance look broken on the desktop or in CI.

The fix: one helper, `_write_json`, writes every JSON output with `newline="\n"`.
`predictors.tsv` is unchanged: `csv` writes its own `\r\n` on every platform, so it is the same
bytes everywhere and no hash depends on it. The new test,
`test_json_outputs_are_written_with_lf_on_every_platform`, failed on the unfixed code on this
laptop (`controls.json` began `{\r\n`) and passes with the fix. On Linux, where Python does not
translate newlines, it passes either way: it guards against a Windows regression, which is where
the freezing run will happen. Gates after the fix: ruff, ruff format and `mypy --strict` clean;
the file's tests 64 passed; full suite 1,044 passed (1,043 before, plus this test).

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, sections 3 and 5)
- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md` (PR #126's plan)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` on `mert/issue-125-preregistration`,
  sections 3.1, 3.2, 3.4 and 3.5
- `docs/roadmap/2026-10-23-phase-4-plan.md` section 8 on PR #131 (step 1a)
- NC-087 to NC-089 (dated anchors): registered in `docs/numerical-claims.md` on
  `mert/issue-125-preregistration`, not yet on `main`; they reach `main` with step 1c
- Issue #125
