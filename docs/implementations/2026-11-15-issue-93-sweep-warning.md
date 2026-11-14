# 2026-11-15: issue-93-sweep-warning

The plan is written first, with what each new test should do against the old script; the results are
appended below. Stacked on PR #157 (`mert/issue-109-phase-3-close` @ `aa3dd25a`), whose ADR-025
amendment of 2026-11-15 states the rule this change follows.

## Problem / Motivation

Issue #93. When a historical sweep files a document older than the newest row in
`health/state-index.tsv`, `scripts/file_snapshots.sh` prints, once per such document:

```
::warning::<stem> predates the newest indexed document (<max>); its is_new_state is decided against
later rows. Dispatch Calibration Pipeline Health with backfill=true rebuild=true to restore the
column's chronology.
```

Every document the daily sweep recovers is one the hourly poll missed, so it is older than the newest
indexed row: the warning fires for nearly every recovered document, every day. It tells the operator
to run a job that fetches about 1.3 GB and requires pausing the poller, while
`scripts/pipeline_health.py::first_sightings` derives first sightings from timestamps and says "no
`--rebuild` is owed after a sweep". ADR-025's 2026-11-15 amendment (File 06, Q3; PR #157) now limits
`--rebuild` to a digest-definition change or a malformed index. Reproduced on `main` @ `667972c5` on
2026-11-15: a live poll files `20260701T065221000000Z`, a sweep then files `20260630T065221000000Z`,
and the sweep prints that warning.

## Decision (@mertefesensoy, 2026-11-15, in this session's dialog)

#93's option 1 (say what is actually owed) with option 3 (once per run) for sweeps:

- **A sweep run** (`IS_BACKFILL=1`) prints no `::warning::` for out-of-order documents. It prints one
  plain line per run: how many documents were filed behind the newest indexed row, that their
  `is_new_state` is decided against later rows, and that readers derive first sightings from
  `last_update_date`, so nothing is owed.
- **A live poll** (`IS_BACKFILL=0`) filing an older document keeps a per-document `::warning::`, because
  that should not happen, with true text and no rebuild instruction.

The `calibration-data` README's sentence that `--rebuild` "exists because a historical sweep files
documents out of chronological order" is carried with Issue #109, not changed here (it is on the data
branch).

## What changed (planned)

| File | One-sentence description |
| --- | --- |
| `scripts/file_snapshots.sh` | The out-of-order message: one plain line per sweep run; a true `::warning::` on a live poll; no rebuild instruction in either. Filing and indexing are unchanged. |
| `tests/test_file_snapshots.py` | Two end-to-end tests: a sweep recovering two older documents, and a live poll filing one. |
| `docs/decisions.md` | Inside ADR-025, after the 2026-11-15 status note: a dated note recording #93's option. |
| This file | The plan, then the results. |

## Implementation approach

A counter (`behind`) and the newest indexed date it was compared against (`behind_max`) are kept
across the filing loop. Inside the existing out-of-order test, a sweep increments the counter, and a
live poll prints its `::warning::`. After the loop, if the counter is positive, the sweep prints its one
line. The `is_new_state` decision and the row written are not touched.

## Mathematical / Statistical details

N/A: a message change; no formula.

## Predictions (fixed before running the tests)

1. **The sweep test**, against the old script: fails. The old script prints two `::warning::` lines
   (one per older document), both naming `rebuild=true`, and no summary line. After the fix: no
   `::warning::`, no "rebuild", exactly one summary line naming 2 documents, and the state index rows
   identical to the old script's (same order, same `is_new_state`).
2. **The live test**, against the old script: fails, because its one `::warning::` names
   `rebuild=true` and does not say "live poll". After the fix: exactly one `::warning::`, naming the
   stem, saying "live poll", and naming no `rebuild=true`.
3. **Mutation checks** after the fix: printing the summary inside the loop fails the sweep test (two
   lines); a `::warning::` on the sweep path fails the sweep test; dropping the live warning, or putting
   `rebuild=true` back into it, fails the live test.

## Design decisions

- **Why keep a warning on live polls.** The hourly poll fetches the current document, which cannot be
  older than one already indexed unless something upstream is wrong. Silencing it there would hide a
  real anomaly behind the sweep's fix.
- **Why one line per sweep, not per document.** #93's first criterion allows one line that is true and
  actionable; a count is all a reader needs, and thirty identical lines are what trains people to
  ignore the log.
- **Why stacked on #157.** #93's third criterion asks for the option to be recorded against ADR-025,
  next to the rule it follows; that rule is in #157. Stacking keeps the note directly after it and
  avoids two PRs appending to the same spot.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_file_snapshots.py -q
ruff check . && ruff format --check . && mypy --strict && python scripts/check_ids.py
PYTHONPATH=src python -m pytest tests/ -q
```

## Related docs

- Issue #93; Issue #84 comment 5885407524 (File 06, Q3: "the 'dispatch a rebuild' warning in
  `file_snapshots.sh` is wrong and gets fixed (#93, option 1)"); PR #157 (ADR-025's 2026-11-15
  amendment); PR #70 (the pipeline-health tree); PR #90 (the daily sweep).

## Results, 2026-11-15 (laptop, provisional)

The sections above are left as written at `2d0d347c`. Python 3.12.10 with the exact pins,
`PYTHONPATH=src`.

| Commit | What it holds |
| --- | --- |
| `2d0d347c` | This plan and its predictions. |
| `0ae3acbe` | The two tests, before the fix. |
| `8b8ef72b` | The fix in `scripts/file_snapshots.sh` (mode `100755` kept). |
| `f0fe48db` | `docs/evidence/issue-93-sweep-warning/mutate.py`, with no output beside it. |
| `8a2c6906` | Its output from the committed copy. |
| `62d7f727` | The ADR-025 note. |
| the next commit | This section. |

**The predictions.**

1. **Held.** On the old script the sweep test failed: the second run printed two `::warning::` lines,
   one per older document, each naming `rebuild=true`, and no summary line. A first reading of
   pytest's assertion message suggested one warning; pytest had elided the middle of the list. The
   full output, printed separately, shows two. After the fix: no `::warning::`, no "rebuild", one
   summary line naming 2 documents, and the index rows as the old script wrote them (the July row,
   then the two June rows, `is_new_state` 1, 0, 0).
2. **Held.** On the old script the live test failed: its one `::warning::` named `rebuild=true` and
   did not say "live poll". After the fix: one `::warning::`, naming the stem, saying "live poll", and
   naming no rebuild.
3. **Held.** `mutate.py`, run from the committed copy: all four mutants killed, M1 and M2 by the sweep
   test, M3 and M4 by the live test. The script was restored from its backup each time, and its SHA-256
   matched (`mutate.out.txt`).

**Checks.**

- `tests/test_file_snapshots.py`: 12 passed, and 12 passed again with
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=explicit` (Burak's setting).
- Full suite: 1205 collected, 1205 passed, none skipped (the archive test ran; `calibration-data` is
  present here), 420 s. That is `main`'s 1203 at `667972c5` plus the two new tests; NC-021 is
  re-measured at the merge commit (Rule 6), not here.
- `ruff check .`, `ruff format --check .` (0.15.12, 122 files), `mypy --strict` (49 source files) and
  `scripts/check_ids.py`: clean.

**Not done here.** #93's first criterion is shown in a sandbox; the first scheduled sweep after merge is
where it is seen on the real workflow. The `calibration-data` README sentence is carried by #109.
Burak's desktop run of these tests is not arranged.
