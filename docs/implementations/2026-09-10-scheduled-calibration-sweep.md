# 2026-09-10: scheduled-calibration-sweep

## Problem / Motivation

The poller **samples**: each run captures whatever document exists at that
instant, so it needs punctuality that GitHub Actions does not provide. Measured
from the Actions run history over the 15 days to 2026-09-10, the hourly cron
produced **6.13 runs/day against the 24 it asks for**, a median gap of 3.23 h and
a worst gap of 12.70 h, with only 12 of 94 gaps at or under 1.5 h. **99 of those
100 runs succeeded**, so nothing was failing: GitHub declines to dispatch about
three quarters of the schedules, which its documentation explicitly permits
("if the load is sufficiently high enough, some queued jobs may be dropped").

That measurement characterises the **single-cron** regime and nothing else. It
is history, not a prediction: PR #89 changed the configuration it describes, and
no figure for the new one exists yet.

**PR #89 landed the stopgap while this branch was open.** It replaced the single
`:37` entry with four per hour (:07, :22, :37, :52), on the reasoning that
spreading the requests across the hour makes it less likely for one load spike
to take all of them. Its own comment is explicit that this raises the odds of a
poll firing without guaranteeing one, and that the actual fix is #49's sweep.
The two are complementary and neither substitutes for the other: **#89 acts on
how often a sample is taken; this branch acts on what a missed sample costs.**
This work is rebased on top of #89, so the workflow now carries five crons.

Issue #49 is the response, and it does not try to fix the scheduler. It converts
the pipeline from sampling to **sweeping**: a daily job re-reads a trailing
window and fills whatever the hourly path missed. Because historical calibration
reads are honoured to at least 60 days (NC-026), a missed poll stops being lost
data and becomes late data. Under that design a cron firing 6 times instead of
24 costs latency, not integrity.

## What changed

| File | One-sentence description |
| --- | --- |
| `.github/workflows/calibration-poll.yml` | Adds a daily sweep cron alongside the four hourly entries #89 landed, derives its window from the clock, and fixes two expressions that silently misbehaved on a `schedule` event. |
| `src/superconducted/calibration/poller.py` | `poll_once` now returns a `SweepOutcome`, and `main` exits **2** when a sweep retrieved no document at all. |
| `tests/test_calibration.py` | Four tests pinning the sweep-outcome contract, including the idempotency case that must stay a success. |
| `tests/test_calibration_poll_workflow.py` | New: five guards on the workflow file. Four cover the sweep cron's agreement across the three places GitHub forces it to appear; the fifth also holds #89's four hourly entries and the `:37` NC-008 target in place, which #89 itself shipped without. |
| `tests/conftest.py` | Nulls `backend.target_history` on the mock backend, matching the existing `target` and `configuration`. |
| `docs/numerical-claims.md` | NC-021's chain extended to account for the 9 sweep tests, which the rebased row records the value of without explaining. |

## Implementation approach

**One workflow, five crons: four samples and a sweep.** Per #49 §2.1 the sweep is
another `schedule:` entry on the existing workflow rather than a new file,
because the commit step carries the ADR-025 ledger, the canonical duplicate
check and the collision handling. A copy would have to be kept in sync with the
ADR by hand. The step tells a sweep from a sample by comparing
`github.event.schedule` against `env.SWEEP_CRON`, so the four hourly entries #89
added are indistinguishable from each other and from the single entry that
preceded them; only the sweep cron takes the new branch.

**The window is derived, not configured per run.** On the sweep cron the step
computes `HIST_START` / `HIST_END` from `date -u`, so the existing
`if [ -n "$HIST_START" ]` branch runs unchanged (§2.3). A `workflow_dispatch`
carrying explicit dates always wins, and a dispatch with everything blank still
behaves exactly like a scheduled poll. All four paths were simulated in a shell
before deploying, per §6.

**Two expressions were wrong in the same way.** `inputs` is empty on a `schedule`
event, so `${{ inputs.historical_start && X || Y }}` always took the `Y` arm for
a scheduled run:

- `timeout-minutes` gave the sweep the **10-minute** poll bound, killing it
  mid-window. This is the defect #49 §2.2 names.
- `IS_BACKFILL` resolved to `'0'`, which the ticket does not mention. That one is
  quieter and worse: `scripts/file_snapshots.sh` uses it to decide whether a
  stamp collision may be explained as a lossy historical re-read, so every sweep
  would have filed its re-reads as `collision` instead of `duplicate-partial`,
  writing a junk payload into `collisions/` and emitting a `::warning::` every
  single day. ADR-025 treats a non-empty `collisions/` as a signal precisely
  because it is normally empty, so this would have destroyed that signal within a
  day of merging.

Both now test `inputs.historical_start || github.event.schedule == <sweep cron>`.

**A dead sweep is no longer silent.** Every failure inside `fetch_snapshot`
returns `None`: a denied historical tier, `properties()` returning `None`, a
missing `last_update_date`, or the service ignoring the `datetime` filter and
handing back the current document. The sweep loop `continue`s past each, and
`poll_once` returned `None`, so `main` exited 0 regardless. A manual backfill is
watched by whoever dispatched it; an unattended daily sweep is not, and it could
have recovered nothing for months while reporting success. That is exactly the
blind spot #45 spent a quarter finding and #48 exists to remove, so the sweep
must not reintroduce it inside its own machinery. `poll_once` now returns counts
and `main` exits **2** (distinct from 1, a crash) when a sweep requested
instants and got nothing back.

The gate is on **documents returned, never documents saved**. Re-sweeping a
window the archive already holds saves nothing and is the idempotency #49 §5
requires; gating on saved would fail every healthy second sweep.

## What `main` moved underneath this branch

This work opened against `3b949cd`. Before it landed, `main` gained PR #70's
pipeline-health work (`scripts/pipeline_health.py`,
`scripts/backfill_state_index.py`, `scripts/push_with_retry.sh`, the `health/`
tree recorded in ADR-025's 2026-09-05 amendment) and PR #89's cron entries.
Three of those interact with a daily sweep. None blocks this merge.

**A daily sweep prints an instruction that is not true. Issue #93.**
`file_snapshots.sh` now appends a row to `health/state-index.tsv` per document
it files, and warns per row when the filed document predates the newest already
indexed, telling the operator to dispatch the health workflow with
`backfill=true rebuild=true`. Every document a sweep recovers is by construction
one the hourly poller missed, so it is older than the newest indexed row, and
the warning fires for essentially every recovered document, every day.
`pipeline_health.py::first_sightings` says the opposite in its own docstring:
first sightings are derived from timestamps, which makes every trailing window
independent of append order, "so no `--rebuild` is owed after a sweep". The
dashboard is therefore correct after a sweep with no repair, the archive is
untouched, and `is_new_state` being wrong is a cost PR #70 accepted knowingly
for FR-2's schema. What is wrong is only the remedy the warning names, and the
job it names fetches ~1.3 GB and requires disabling the poller first. Left
alone, the daily instruction is either an hour wasted or a habit of ignoring
`::warning::` on the one workflow ADR-025 needs quiet. Filed rather than fixed
here: the fix belongs in the two PR #70 files this branch does not otherwise
touch, and it has four candidate shapes that deserve their own decision.

**The sweep sits in the concurrency queue longer than a poll does.** The group is
`calibration-poll` with `cancel-in-progress: false`, so a run arriving while
another is in flight waits, and a second arrival replaces the waiting one.
#89 raised arrivals to four per hour, and the sweep may run for up to its
60-minute bound, so the sweep's window can discard up to three queued hourly
polls. That displacement is absorbed rather than lost: the sweep is re-reading
that exact window as it runs, so the samples it displaces are precisely the ones
it recovers. `polls_fired_24h` counts distinct ledger timestamps rather than
workflow run records, so a displaced poll does not appear as a fired-and-failed
poll in the metrics. It does depress the count for that hour, which is honest,
because no poll ran.

**The sweep is a longer-lived writer in a race that now exists.**
`file_snapshots.sh` no longer pushes directly; it goes through
`push_with_retry.sh`, because the health workflow became a second writer to
`calibration-data`. A sweep holds that writer role for minutes rather than the
~40 seconds a poll takes, so it is exposed to the race for correspondingly
longer. The two schedules do not currently overlap: health renders at `17 3`,
the sweep starts at `41 4`, which is 84 minutes of clearance against a 60-minute
bound. That clearance is incidental to two independently chosen crons and
nothing enforces it, so moving either one is not a free change.

## Mathematical / Statistical details

N/A for the code. The parameter choice is arithmetic and is recorded under
Design decisions: a 48 h window on a 1 h grid is 48 query instants per sweep,
confirmed by `_build_historical_window` returning 48 entries.

## Design decisions

| Parameter | Chosen | Why |
| --- | --- | --- |
| Window | trailing **48 h** | §3. Overlap absorbs a skipped sweep. It does **not** improve per-instant recall: shifting a 1 h grid by 24 h realigns it on the same instants, so no compounding should be claimed. |
| Step | **1 h** | 48 IBM calls per sweep, inside the 73-call run already demonstrated. NC-031 measured 1 h recall at 87.9% (29 of 33), so a sweep is not a perfect substitute for polling and this document does not claim it is. |
| Cadence | **daily** | 60-day retention (NC-026) leaves enormous margin; more often buys little. |
| `max_historical_days` | **30**, unchanged | A 48 h window is nowhere near it. The guard raises on the whole window rather than skipping a step, so widening it later needs care. |
| Sweep exit code | **2** | Distinct from 1 so an empty sweep is distinguishable from a crash, matching how `canonical_snapshot_digest.py` keeps "differ" apart from "cannot tell". |

**Finer steps were considered and rejected for the scheduled path.** The
`historical_step_hours` input advises 0.5 or finer for recovery, and NC-031 is
why. A 0.5 h grid over 48 h is 96 calls per day, sustained, which is above
anything observed. The daily sweep is maintenance and takes 1 h; a post-outage
recovery run is dispatched by hand and should take 0.5 h or finer. That split is
what the input description already recommends.

**A paid GitHub plan was considered and rejected.** This repository is public, so
Actions minutes are already free and unmetered; the concurrency ceiling (20 to 60
jobs) is irrelevant to a single-job poller; and GitHub documents no scheduling
priority that differs by plan. The community claim that free-tier cron sits
lowest in the dispatch queue is folklore rather than documentation and carries no
SLA.

**IBM offers no push mechanism, so polling is not a choice.** Verified against
IBM's REST API reference on 2026-09-10: the Backends tag documents exactly five
endpoints, all `GET`, with no webhook, subscription, callback or event among
them. `IBMBackend.properties(refresh, datetime)` in the installed
qiskit-ibm-runtime 0.46.1 returns the document "closest to, but older than, the
specified `datetime`", which is the semantics the sweep grid depends on, and
raises `NotImplementedError` when `datetime` is used on cloud runtime, which is
one of the silent-`None` paths the new exit code now catches.

## Verification

```bash
python -m pytest tests/test_calibration.py tests/test_calibration_poll_workflow.py -q
python -m ruff check . && python -m ruff format --check .
python -m mypy --strict src/superconducted
python scripts/check_ids.py
```

Re-measured on the rebased branch, not carried over from the pre-rebase one.
`ruff check` clean, `check_ids.py` clean, **447 tests collected and all 447
passing** on Windows in a clean 3.12.10 interpreter at a short path.

Two things about that block are worth stating rather than leaving implied.

The earlier measurement on this branch recorded 379 collected and 8
`tests/test_file_snapshots.py` failures. The failures did not reproduce here.
They are an artefact of the repository `.venv` rather than of the platform,
which is the same reading NC-021's own chain reached independently at `7ec173f`.
CI on `ubuntu-latest` remains the authority for the pass count; this run agrees
with it rather than standing in for it.

`ruff format --check` and `mypy --strict` are **not** reported from this machine.
Both fail here for reasons this branch does not own: `ruff format` flags a
fenced code block in `docs/implementations/2026-09-06-issue-58-decisions-and-r2-orientation.md`,
a file that predates the merge base and that this branch never touches, and
`mypy` stops on a `type` statement inside numpy 2.5.3's shipped stubs under the
project's pinned `python_version = "3.11"`. `main`'s own CI is green at
`4355850` over that same file, so both are local resolution artefacts. CI is the
authority for those two gates.

The four shell paths were simulated before deploying:

| Trigger | Result |
| --- | --- |
| hourly cron, no inputs | single live poll, unchanged |
| sweep cron, no inputs | derived 48 h window, 1 h step |
| dispatch with explicit dates | explicit window wins |
| sweep cron plus explicit dates | dispatch still wins |

**The CI run this PR reported was not a run of this tree.** The only `CI` run on
`mert/issue-49-sweep` fired at the opening push, on `95ada98` at 05:24Z, against
a tree based on `3b949cd`: before #70, #91 and #89 reached `main`. It is where
the "CI green, 379 tests" in the PR comment comes from. Once #89 merged at
19:43Z the PR went `CONFLICTING`, and `ci.yml` does not dispatch on a conflicted
PR while CodeQL keeps running and keeps reporting success, so the checks panel
went on reading green while nothing ran the tests. The rebase onto `4355850`
is what restores a real signal, and the count to trust is the one CI reports on
the rebased head.

**Not yet verified, and it needs a real run.** #49 §5 asks for a sweep executed
over a known gap with the recovered document count reported, and for a second
consecutive sweep over the same window producing no commit. Neither can be done
from a checkout: `workflow_dispatch` reaches only workflows already on the
default branch, so the sweep path cannot be exercised until this merges. The
honest sequence is to merge, let the first scheduled sweep run, and report both
figures on the issue.

## Related docs

- Issue #49 (this work), #48 (the telemetry that makes a gap visible), #45 (the
  scheduler characterisation)
- PR #89, the four-entry hourly cron this merges on top of, and issue #93, the
  contradiction a daily sweep exposes between two files PR #70 landed
- PR #70 and `docs/implementations/2026-09-05-pipeline-health-dashboard.md`, for
  the `health/` tree and the renderer whose windows survive a sweep untouched
- ADR-020 and ADR-025 in `docs/decisions.md`, including ADR-025's 2026-09-05
  pipeline-health amendment
- NC-008 (the `:37` polling target the cron test pins), NC-026 (60-day
  retention), NC-029 (capture rate over the outage), NC-030 (republication
  rate), NC-031 (1 h sweep recall)

> **Note on #49's own references.** Its §8 cites NC-024 for the 60-day retention,
> NC-027 for the capture rate and NC-028 for the republication rate. All three
> shifted in the identifier reissue recorded in
> `docs/implementations/2026-08-31-adr-nc-collision-and-branch-reissue.md`; on
> `main` they are NC-026, NC-029 and NC-030, and NC-024 is now the consequent
> seed-search limit. The rows cited above are the current ones.
