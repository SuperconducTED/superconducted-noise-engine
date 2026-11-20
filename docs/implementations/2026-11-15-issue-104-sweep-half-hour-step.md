# 2026-11-15: issue-104-sweep-half-hour-step

The plan is written first, with the prediction fixed before the change; the measured baseline and the
results are appended below it in later commits. Decision by @mertefesensoy on 2026-11-15 (option B of
issue #104).

## Problem / Motivation

Issue #104 asks whether the daily sweep's 1 h step is worth refining. The sweep (#49, PR #90) queries
the trailing 48 h of IBM's calibration history at a 1 h step, so it cannot reliably see a document that
IBM supersedes in under an hour. The issue was written on one week of September data (NC-058, capture
at most 88.1%) and left the 0.5 h option deliberately unmeasured, because a replay of real 1 h sweeps
against ground truth did not reproduce the ledger (IBM's history index lags publication).

Since 2026-09-30 the capture job (`calibration-health.yml`, ADR-025 amendment of 2026-09-29) has
enumerated every settled day at 0.25 h and written one row per document to `health/capture.tsv` on
`calibration-data`. That record answers the question the issue's proposed 30 min probe was for, over
six weeks instead of one, without a query to IBM. A scratch draft of this PR's script, run on the lead's
laptop before this plan was written, showed: capture falling from about 86% to about 70% per week, every
missed document living under one hour, and no document that lived an hour or more missed. Those scratch
runs are not evidence; the committed script's output (next commits) is.

## What changed (planned)

| File | One-sentence description |
| --- | --- |
| `.github/workflows/calibration-poll.yml` | `SWEEP_STEP_HOURS` from `'1'` to `'0.5'`, and the comment block above it restated for the new step. |
| `.github/workflows/calibration-health.yml` | The comment on `CAPTURE_STEP_HOURS` names the sweep's new step; the value stays `'0.25'`. |
| `docs/evidence/capture-rate-2026-11/capture_lifetimes.py` | Reads `health/capture.tsv` by blob at a pinned `calibration-data` commit and reports capture by week and by document lifetime. |
| `docs/evidence/capture-rate-2026-11/*.out.txt`, `README.md` | The committed script's output at the baseline anchor, and what it answers. |
| `docs/numerical-claims.md` | New rows for the baseline (ids from NC-099, see Design decisions). |
| `docs/implementations/2026-11-15-issue-104-sweep-half-hour-step.md` | This record. |

## Implementation approach

One configuration value changes. The sweep step derivation is unchanged: when the sweep cron fires,
`HIST_START` is the run's clock minus `SWEEP_WINDOW_HOURS` and the query instants are `HIST_START + k *
SWEEP_STEP_HOURS`. At 0.5 h a sweep makes 96 historical queries plus one current fetch (97), against 49
at 1 h; #104's table estimates about 3.5 minutes at the measured 2 s per historical query, inside the
job's 60 minute timeout for a sweep.

The capture job's step stays at 0.25 h, so `TestWorkflowPins.test_the_capture_grid_is_strictly_finer_than_the_sweep`
(capture strictly finer than the sweep) still holds and the instrument that measures capture does not
change. That is what lets the week after the change be read the same way as the weeks before it.

## Mathematical / Statistical details

**Which document a query returns.** Order the documents by `last_update_date` `t_1 < t_2 < ...`. A
historical query at instant `q` returns the latest document stamped at or before `q`, so document `d` is
returned exactly for `q` in `[t_d, t_{d+1})`. Its **lifetime** is `L_d = t_{d+1} - t_d`.

**The grid guarantee.** A grid `q_k = q_0 + k s` lands inside every half-open interval of length at
least `s` that lies within its window. So a sweep at step `s` samples every document with `L_d >= s`
inside its window; a document with `L_d < s` is sampled only if the grid's phase happens to fall in it.
"Samples" is not "retrieves": it assumes IBM's history index returns at sweep time the document it
returns later. The baseline tests that assumption at `s = 1 h`.

**Capture.** Over a set of days, `capture = held / exist`, with `held` the documents the scheduled
pipeline retrieved (`captured`, `archived_not_served`) and `missed` the rest (`MISSED`, `backfilled`),
`exist = held + missed`, exactly as `scripts/capture_record.py` defines it. It is an upper bound, like
NC-058: a document living less than 0.25 h can escape the capture enumeration too.

**Unknown lifetimes.** A lifetime is unknown when any UTC day from `day(t_d)` to `day(t_{d+1})` is not
in the record (the successor may be a document nobody enumerated), or when `d` is the last document.
Such documents are counted, reported, and left out of every lifetime-stratified figure.

## Prediction (fixed before the change)

**Evaluation days E.** Let `S` be the UTC date of the first scheduled sweep whose log reads `every
0.5h`. E is the 7 consecutive UTC days starting at `S - 1` (the first day a 0.5 h sweep's 48 h window
covers entirely). A day that no scheduled 0.5 h sweep window covers entirely (both covering sweeps
skipped) is reported and replaced by the next day. The capture job records a day three days after it,
so E is complete about 9 days after `S`.

**P1, the test.** Among the documents of E with a known lifetime of 0.5 h or more, **0 are missed**.
The baseline (next commits) gives the same count before the change. P1 can fail cleanly: one missed
document with `L >= 0.5 h` fails it.

- If P1 holds: the history index serves sub-hour documents inside the live 48 h window, as the 1 h
  grid's record suggests, and option C (a 0.25 h sweep with the capture step moved to 0.125 h, so the
  quarter-hour instants stay a subset) is proposed on #104 with this result as its evidence.
- If P1 fails: each missed document with `L >= 0.5 h` is listed with the sweep's query instants around
  it, read from the ledger, before any further change. The step stays at 0.5 h meanwhile: from the same start, its
  instants include every instant the 1 h grid would query, so it samples at least what 1 h did.

**Reported, no bar:** capture over E, against the baseline's last weeks; misses among documents
living 0.25 to 0.5 h and under 0.25 h; the 0.5 h sweeps' durations from the Actions runs, against the
3.5 minute estimate; `capture_7d` from the dashboard. A weekly rate gets no bar because it has fallen
on its own by about 3 points a week, so a before-and-after difference would confound the change with
the trend.

## Design decisions

| Option | Chosen? | Why |
| --- | --- | --- |
| A. Keep 1 h | No | Capture is falling, and the misses are the sub-hour documents a 1 h grid cannot see by construction. |
| **B. 0.5 h, capture stays at 0.25 h** | **Yes** | One value; the instrument is unchanged; P1 tests the one real unknown (the index in the live window) with a prediction that can fail; reversible. |
| C. 0.25 h now | Not yet | Its guaranteed gain is larger, but the pin forces the capture step finer in the same change, so the sweep and its measurement would move together. It is the proposed next step if P1 holds. |
| C with capture at 0.1 h, as #104 proposed | Replaced by 0.125 h | 0.125 h keeps today's quarter-hour instants as a subset (0.25 is a multiple of 0.125, not of 0.1), so the old capture figure stays computable from the new record. |

**Call volume.** The 2026-09-10 sweep design (`docs/implementations/2026-09-10-scheduled-calibration-sweep.md`)
rejected a scheduled 0.5 h step because "96 calls per day, sustained" was "above anything observed".
Since 2026-09-30 the capture job has enumerated one settled day at 0.25 h (96 query instants) every day it
ran, so that volume is now observed and sustained; the count of its runs goes in the baseline below.

**`docs/decisions.md` is not edited.** ADR-025's amendment of 2026-09-29 says the capture step is "finer
than the sweep's 1 h"; that was true on its date and stays true as a dated statement, and the rule it
states (capture strictly finer than the sweep) still holds and is pinned by the test. Leaving the file
alone also avoids the append conflict PR #145 and PR #150 already have there.

**NC ids.** The new rows take NC-099 onward. PR #150's pending row is written as "ID pending", taking the
next free id at its merge, so it does not collide; the PR description says so.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_calibration_poll_workflow.py tests/test_capture_record.py -q
PYTHONPATH=. python docs/evidence/capture-rate-2026-11/capture_lifetimes.py --ref d08263a97a7524f49f9fe2841584188aa408d443
ruff check . && ruff format --check . && mypy --strict && python scripts/check_ids.py
```

After the change, P1 is evaluated with the same script at a later `calibration-data` commit, `--from`
and `--to` set to E's first and last day.

## Related docs

- Issue #104; #49 and PR #90 (the sweep); PR #105 and `docs/evidence/capture-rate-2026-09/` (the
  capture measurement, NC-056 to NC-060); ADR-025's amendment of 2026-09-29 in `docs/decisions.md`.
- `docs/implementations/2026-09-10-scheduled-calibration-sweep.md` and
  `docs/implementations/2026-09-29-capture-rate-measurement-and-tracking.md`.

## Results, 2026-11-15: the baseline and the change (laptop, provisional)

The sections above are left as written at `188dd17a`. Since then:

| Commit | What it holds |
| --- | --- |
| `188dd17a` | This record's plan and prediction, before anything below. |
| `f40e3d27` | `capture_lifetimes.py`, with no output beside it. |
| `a46d7471` | Its output from the committed copy at `calibration-data` @ `d08263a9`, and the folder's README. |
| the next commit | `SWEEP_STEP_HOURS` to `'0.5'`, both workflow comments, NC-099 to NC-101, and this section. |

**The baseline** (`docs/evidence/capture-rate-2026-11/baseline-2026-09-30_11-11.out.txt`): 1,684
documents over 42 recorded days (2026-09-30 to 2026-11-11, 2026-11-01 missing), capture 75.5% (NC-099),
weekly from 86.0% down to 68.6% and 71.8%; 0 of 250 documents that lived 1 h or more missed (NC-100);
44 of 789 that lived 0.5 h or more missed (NC-101, P1's baseline); all 413 misses lived under 1 h
(longest 0.914 h). Two documents have no known lifetime and are left out. Against the scratch draft run
before the plan, every figure is the same; two that this session quoted from the scratch run, "0 of 251"
and "44 of 790", counted those two documents and are corrected here to 250 and 789.

**Call volume, now measured.** The record names 38 distinct capture runs over its 42 days (a run catches
up to three settled days), each enumerating at 0.25 h, so 96 query instants per settled day have been
sustained since 2026-09-30. That is the volume the 2026-09-10 design called "above anything observed";
a 0.5 h sweep adds 48 queries a day to the 49 the sweep makes now.

**The change.** `.github/workflows/calibration-poll.yml`: `SWEEP_STEP_HOURS` from `'1'` to `'0.5'`, and
its comment restated (the step, its call count, NC-100, NC-101, P1 and the pin). `.github/workflows/calibration-health.yml`:
the comment on `CAPTURE_STEP_HOURS` names the sweep's step; the value stays `'0.25'`. `docs/numerical-claims.md`:
NC-099 to NC-101, dated anchors on `calibration-data`.

**Checks** (Python 3.12.10, the exact pins, `PYTHONPATH=src`):

- `tests/test_calibration_poll_workflow.py` and `tests/test_capture_record.py`: 34 passed.
- The pin is live: with `SWEEP_STEP_HOURS` set to `'0.25'` (equal to the capture step) in place,
  `test_the_capture_grid_is_strictly_finer_than_the_sweep` fails; the file was restored from a backup
  copy and its SHA-256 checked.
- `ruff check .` and `ruff format --check .` (ruff 0.15.12): clean, 122 files. `mypy --strict`: clean,
  49 source files. `scripts/check_ids.py`: no duplicate or colliding identifiers.
- No test was added or removed, so NC-021 is not touched by this PR; the full suite was not run here
  (CI runs it on the PR).

**Not done here.** P1 is evaluated after the change, about 9 days after the first 0.5 h sweep. Burak's
desktop run of this PR's checks is owed. Whether the missed documents carried new device states is not
measured (it needs a backfill from IBM's history, and the oldest misses, from 2026-09-30, pass the 60-day
retention of NC-026 about 2026-11-29).

## Amendment 1, 2026-11-15: before the push, and before any data after the change

Written after a review pass on the local branch, before the branch was pushed and before any sweep ran
at 0.5 h, so no figure after the change existed. The prediction section above is left as written; this
section adds to it and corrects one sentence.

**1a. A recorded lifetime is an upper bound.** A document that escaped both the 0.25 h capture
enumeration and the archive appears nowhere in the record. If one sits between a document and its
recorded successor, the document's true lifetime is shorter than the recorded one, and a 0.5 h grid is
no longer guaranteed to land inside it. Such a document lived under 0.25 h, since the capture grid
would otherwise have served it. **P1 counts misses by recorded lifetime, and no miss is excused by a
document nobody saw.** Each miss with a recorded lifetime of 0.5 h or more counts against P1 and is
reported with this caveat. This makes P1 harder to pass, not easier.

**1b. When P1 is read, and what replaces a missing day.** A document stamped late on E's last day has
an unknown lifetime until the next day is recorded, and would otherwise drop out of the count silently.
So P1 is read at the first `calibration-data` commit whose capture record contains the day after E's
last day, and the output's count of E documents with an unknown lifetime is reported beside the P1
line. A day of E missing from the record is replaced by the next recorded day, so that E always holds
7 recorded days; the reading then waits for the day after the new last day.

**1c. A correction to the prediction section.** "As the 1 h grid's record suggests" credits the sweep.
The record shows only that the pipeline as a whole (the hourly poll and the daily sweeps) missed no
document that lived 1 h or more. It does not show which path retrieved each one. The ADR-025 ledger
holds that, and it was not read here. NC-100, the evidence README and this PR's description say it
that way.

**The window, measured.** `_build_historical_window` in `src/superconducted/calibration/poller.py`,
called with a 48 h window (`2026-11-12T07:59:13Z` to `2026-11-14T07:59:13Z`) and the step strings the
workflow passes:

| Step string | Instants | Spacing | Last instant |
| --- | ---: | --- | --- |
| `'1'` | 48 | 3,600 s | `2026-11-14T06:59:13Z` |
| `'0.5'` | 96 | 1,800 s | `2026-11-14T07:29:13Z` |

`poll_once` also fetches the current document once per backend, so a 0.5 h sweep makes 97 calls
against 49. The value reaches the builder as the string `'0.5'` (`HIST_STEP="$SWEEP_STEP_HOURS"`),
which it parses as a float; the 1 h fallback the 2026-09-02 record describes was fixed then and does
not occur here.

## Note, 2026-11-15: Rule 7's clause (b) on NC-099 to NC-101

Added after amendment 1. No data from after the change had been read. It changes no number, source,
`Last verified` date or prediction.

PR #151 adds Rule 7 to the register. A row measured from outside the merge graph must name an immutable
ref (a), name the live artifact that supersedes it (b), and say it is not the current value (c). All
three rows here are measured from `calibration-data`. Each met (a) and (c), but none met (b): each ended
"Dated anchor, not a current value." PR #152's audit of the register stopped at its own tip, so it did
not see these rows. This was found on 2026-11-15, while reading Issue #92's state.

Each row's closing sentence is now a line in the form PR #152 uses, so that Issue #153's proposed
exemption marker (`**Rule 7, YYYY-MM-DD`) finds it. NC-099's line names the live artifact, the same
command run with `--ref` at a later `calibration-data` commit, and says the capture job extends
`health/capture.tsv` each day (`calibration-health.yml`, `cron: '17 3 * * *'`). NC-100 and NC-101 say
the same in short. The lead approved the wording in the session's question dialog.

## Amendment 2, 2026-11-20: a day of E whose covering sweep was skipped (Baha's review)

Appended; nothing above is edited. Written before this PR merged, so every sweep so far ran at 1 h and no figure
after the change exists. This section is the plan; the code follows it.

**The finding.** Baha's review 5927517413 (CHANGES_REQUESTED, 2026-11-16) is about `capture_lifetimes.py`, lines 116
to 118. `chosen` keeps every document stamped in `lo..hi`. So a day of E whose sweep was skipped, but which still has
captured documents, stays in E. Yet the prediction section says such a day "is reported and replaced by the next
day". The script has no input that names such a day, and `--from` and `--to` cannot express an E with a gap in it.

**Reproduced first, on the code as it is.** The synthetic record covers 2026-11-16 to 2026-11-24, with two documents a
day, at 06:00 and 18:00. All are captured except 2026-11-21 06:00, which is missed: that day's sweep was skipped, and
the hourly poll caught only the 18:00 document. `--from 2026-11-16 --to 2026-11-24` selects all 18 documents, and P1
reads "1 of 17". So P1 fails on a day the protocol removes. The test below re-makes this record.

**The lead's decision, 2026-11-20: which skipped sweep makes a day uncovered.** Day D of E is uncovered when the
scheduled sweep dated D+1 did not run.

- Only D+1's 48 h window covers D entirely. The sweeps dated D and D+2 each cover part of D. They meet near the sweep
  hour, with a gap of up to about 2 h when their dispatch times differ (09:00 to 11:15 UTC).
- This is the prediction section's "no scheduled 0.5 h sweep window covers [it] entirely". Its bracket, "(both
  covering sweeps skipped)", is corrected: one skipped sweep, D+1's, is enough. Under the bracket's reading, a miss in
  that gap would count against P1, although no 0.5 h grid could have guaranteed it.
- An uncovered day is reported and replaced by the next day, as written. Amendment 1b still holds: E keeps 7
  recorded, covered days, and P1 is read at the first commit whose record holds the day after E's new last day.
- "Ran" is read by `sweep_days.py` (this folder). D+1 had a scheduled sweep when some ledger poll time dated D+1
  holds more than one row, which is `classify_polls`' rule in `scripts/capture_rate_analysis.py`, and falls inside a
  scheduled run of `calibration-poll.yml`. The scheduled runs are listed from the Actions runs API (`event=schedule`)
  and saved beside the script, so the reading survives GitHub's 90-day expiry.

**The script.** `capture_lifetimes.py` gains `--exclude-day YYYY-MM-DD`, repeatable, for the uncovered days found by
the rule above.

- An excluded day's documents leave `chosen`, and the day leaves the weekly table.
- Lifetimes still use the whole record: an excluded day's documents remain successors of earlier ones.
- The output names the excluded days and counts the recorded days left in `lo..hi`, so a reader can see that E holds
  7.
- An excluded day outside `lo..hi`, or the same day given twice, is refused.
- Without the flag, the output does not change.

**The baseline is checked the same way.** `sweep_days.py`, run from its committed copy, must find a scheduled sweep on
every day from 2026-09-30 to 2026-11-14. That span covers each day of the record (2026-09-30 to 2026-11-11) and the
day after it. If it does, no baseline day would be excluded, and NC-099 to NC-101 stand. A day without one is reported,
and its effect on the baseline is measured, before anything else changes.

| # | Criterion |
| --- | --- |
| A1 | Without `--exclude-day`, the baseline command at `d08263a9` gives output byte-identical to the committed `baseline-2026-09-30_11-11.out.txt`. |
| A2 | On the synthetic record, `--exclude-day 2026-11-21` leaves 16 documents selected, P1 reads "0 of 15", and the output names 2026-11-21. Without the flag: 18 documents and "1 of 17", as reproduced. |
| A3 | An excluded day outside `lo..hi`, or the same day twice, is refused with a message and a nonzero exit. |
| A4 | A test pins A2 and A3, running the script on a synthetic record in a temporary git repository. Each new line is mutation-checked, with predictions written first. |
| A5 | `sweep_days.py`, from its committed copy at `d08263a9` with the committed runs file: a scheduled sweep on every day from 2026-09-30 to 2026-11-14. |
| A6 | ruff, `ruff format --check`, `check_ids.py`, `mypy --strict` and `pytest tests/` pass on the exact head, with the exact pins. |

### Results of amendment 2, 2026-11-20 (laptop, provisional)

Run with the exact pins (`C:/t/pin125`). The code and test are at `aa044285`, and the mutation script at `8e0c7dd4`.
This results commit changes only `docs/`.

| # | Result |
| --- | --- |
| A1 | **Holds.** With the new code, the baseline command at `d08263a9` gives output identical to the committed `baseline-2026-09-30_11-11.out.txt`, line endings normalised. The committed file is LF; Windows stdout writes CRLF. |
| A2 | **Holds.** On the synthetic record, `--exclude-day 2026-11-21` selects 16 documents, P1 reads "0 of 15", and the output names 2026-11-21 with 8 recorded days left. Without the flag: 18 documents and "1 of 17", which is the reproduction on `6dcfea3d`'s code. |
| A3 | **Holds.** 2026-11-25 and 2026-11-15 are refused as outside 2026-11-16 to 2026-11-24, naming the day. 2026-11-21 given twice is refused as given twice. Each refusal exits nonzero and prints no selection. |
| A4 | **Holds.** `tests/test_capture_lifetimes.py` (6 tests) re-makes the record in a temporary git repository. The 13 mutants of the new lines were run in a `git archive` copy: 13 caught, all by an assertion, none against the prediction (`mutation-amendment-2.tsv`). N13 (`action="store"`) was expected to crash, and it does, in the subprocess; the test's exit-code assertion is what catches it. |
| A5 | **Holds.** `sweep_days.py`, run from its committed copy at `d08263a9` with the committed runs file, finds a scheduled sweep on 46 of 46 days from 2026-09-30 to 2026-11-14 (`sweep-days-2026-09-30_11-14.out.txt`). No baseline day would be excluded, so NC-099 to NC-101 stand. An earlier one-off look, before the script existed, gave the same answer over 2026-09-27 to 2026-11-14 with a stricter burst size (at least 5 rows); it is not cited as evidence. |
| A6 | **Holds**, on a throwaway merge of `8e0c7dd4` with `main` at `b9fcddea`. The merge's tree is `b0d9f5ec`, the same object as the trial merge's, and `superconducted.__file__` is the merge worktree's own `src`. ruff, `ruff format --check` and `check_ids.py` are clean, and `mypy --strict` finds no issues in 51 source files. `pytest tests/`: 1,438 passed, 0 skipped, in 5 min 50 s. |

**Not changed by this section.** NC-021: the merge measures 1,438 against `main`'s 1,432 (the 6 new tests). That is a
trial merge, not a merge commit, so the register is re-measured at this PR's merge under Rule 6. Burak's desktop run
is still owed.
