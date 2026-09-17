# 2026-09-17: dashboard heartbeat and freshness alarm

## Problem / Motivation

The pipeline-health dashboard built for issue #48 could not report that it had
stopped being built.

`calibration-health.yml` renders `health/metrics.json` and `health/progress.svg`
once a day. Under FR-6 it commits only when the rendered bytes change, and the
step implemented that by staging `health/` and then, whenever `progress.svg` was
unchanged, running `git restore --staged health/metrics.json` and exiting. A
render that found nothing new therefore committed **nothing at all**, and
`generated_at` did not advance.

The consequence is that these two states left byte-identical content on
`calibration-data`:

1. the renderer ran today and correctly found nothing new;
2. the renderer has not run since some earlier date, because it is broken,
   disabled, or its schedule was dropped.

Nothing on the branch separates them. The only evidence that could is the
Actions run list, which expires at ~90 days.

This is not a new class of defect in this repository. It is the one ADR-025 was
written to fix, in ADR-025's own words:

> First, gaps were unattributable. The workflow's `git diff --cached --quiet &&
> echo 'No new snapshots'` branch discarded its own evidence: a quiet stretch
> looked identical to a stopped poller, and the run history that could have told
> them apart expires at ~90 days.

ADR-025 fixed that for the poller by writing a ledger row on **every** run,
including the ones that observed nothing. `health/` was added later, by the
2026-09-05 amendment, as the branch's second writer, and the principle was never
applied to it.

The ordering that makes it expensive is renderer-dies-first. If the poller stops,
the dashboard keeps rendering and the 72-hour strip fills with gaps, so the
failure is visible, and the graphic eventually freezes in an alarmed state, which
is honest. If the **renderer** stops while the poller is healthy, the graphic
freezes in whatever state it last held, plausibly all-green, and the archive can
then degrade behind a dashboard that still says it is fine. That is #45's failure
mode relocated into the instrument built to prevent it, and issue #48 §11 measures
its own success counterfactually against exactly that scenario.

## What changed

| File | One-sentence description |
| --- | --- |
| `.github/workflows/calibration-health.yml` | Commits `metrics.json` on every render instead of discarding it, keeps `progress.svg` behind the change guard, distinguishes the two commit messages, and reports the render gap it is closing. |
| `.github/workflows/calibration-poll.yml` | Carries `DASHBOARD_MAX_AGE_HOURS` and runs the freshness check hourly as a final step that can never fail the poll. |
| `scripts/check_dashboard_freshness.py` | New: reads `health/metrics.json`'s `generated_at`, judges it against a supplied bound, and emits a GitHub annotation. Exit 0 fresh, 1 stale, 3 undecidable. |
| `tests/test_check_dashboard_freshness.py` | New: 27 tests over the verdict, the unreadable shapes, the producer/consumer contract, the CLI exit codes, and the workflow wiring. |
| `docs/numerical-claims.md` | NC-053 registers the 48 h bound and its derivation; NC-021 moves to 643. |
| `docs/decisions.md` | ADR-025 amendment note recording that `health/metrics.json` is now written unconditionally. |

## Implementation approach

Three parts, in the order they depend on each other.

**1. Make the heartbeat truthful.** The commit step now stages `health/` and
commits whatever actually changed. This relies on a property of git that the
previous shape worked around rather than used: `git add` stages a tree, but a
commit records only files whose content differs, so an unchanged `progress.svg`
reuses its existing blob and contributes nothing. FR-6's churn budget is
therefore preserved exactly where it was aimed, at the 8.5 KB graphic, while the
2 KB `metrics.json` commits on every render.

Because every render now produces exactly one commit, `git log health/metrics.json`
is a complete, durable render log. No new file was needed to get one.

The two outcomes keep distinct commit messages, so the log stays readable and the
existing message keeps its existing meaning:

| Condition | Message |
| --- | --- |
| `progress.svg` changed | `health: refresh pipeline dashboard` (unchanged from before) |
| only `metrics.json` changed | `health: heartbeat, rendered dashboard unchanged` |

**2. Give the heartbeat a reader.** Issue #48's own summary of the problem with
#47 is that it "lands the raw instrument ... but nothing reads it". A heartbeat
nobody reads would repeat that, so `scripts/check_dashboard_freshness.py` reads
it and both workflows run it.

The placement is the load-bearing decision. **A process cannot report its own
death.** The renderer can only notice a gap once it is alive again, so it cannot
be the primary alarm. The hourly poller can: it is independently alive, it runs
24 times a day, and `file_snapshots.sh` has already materialised the data branch
in a worktree, so the check costs one file read against a path already on disk
and touches nothing in the filing path. It is the last step in the job, guarded
on the worktree existing, and terminated with `|| true` so a stale dashboard can
never cost a poll or the ledger row that makes scheduler degradation visible.

The health workflow runs the same script before rendering, against the heartbeat
the *previous* run left, so a renderer that has been down reports the gap it is
closing. That is a secondary, after-the-fact report, not the alarm.

**3. Make the bound configuration.** FR-7 requires a rendered bound to be
supplied by the workflow and to carry its source, for the same reason it requires
it of the candidate training floors. `--max-age-hours` is a required argument
with no default, so the value cannot be baked into the module, and
`test_the_bound_is_not_a_literal_in_the_checker` asserts that over the parsed
numeric constants of the script.

GitHub Actions cannot share an `env` across two workflow files, so the value
appears in both. `test_both_workflows_carry_the_same_bound` pins them together.

## Mathematical / Statistical details

The only number this change introduces is the staleness bound, and it was derived
from the observed record rather than chosen for looking reasonable.

**Population.** The eight renders `calibration-health.yml` has published to
`calibration-data`: the 2026-09-10 `workflow_dispatch` and the 2026-09-11 through
2026-09-17 scheduled runs. Their commit instants give seven consecutive intervals.

**Observed intervals**, in hours:

```
23.748  23.856  24.402  24.656  23.728  23.902  24.060
n = 7    min 23.728    max 24.656    mean 24.050
```

**Why the intervals are not exactly 24 h.** The cron asks for `17 3 * * *`, but
GitHub serves scheduled runs late under load; these eight were served between
07:59 and 09:03 UTC, a 64-minute spread. An interval is therefore
`24 h + (delay_k − delay_{k−1})`, so it inherits the *difference* of two delays
and can exceed 24 h whenever a run is served later than its predecessor.

**Firing rate of a candidate bound** against that healthy record, counting an
interval as a false alarm when it exceeds the bound:

| Bound | Fires on healthy record | Rate |
| --- | --- | --- |
| 24 h | 3 of 7 | 43% |
| 25 h | 0 of 7 | 0% |
| 26 h | 0 of 7 | 0% |
| 48 h | 0 of 7 | 0% |

A round 24 h — the obvious guess for a daily job — would have alarmed on three of
seven healthy days. That is the whole reason this was measured.

**Choosing between the survivors.** 25 h clears the observed maximum by 0.34 h,
which is less than the 64-minute delay spread already observed, so a single
later-than-usual run would trip it. GitHub additionally documents dropping
scheduled runs entirely under load; a dropped run produces a ~48 h interval. A
bound that alarms on one dropped render would alarm on a normal, non-actionable
event, and an alarm read 24 times a day must not cry wolf.

**48 h is therefore one whole missed render.** It fires on the second consecutive
miss, gives 0/7 on the healthy record, and still detects a dead renderer within
two days — against the quarter-scale blindness issue #48 exists to end, and well
inside its own "shows in a day instead of a quarter" standard.

Registered as NC-053. It is a threshold, and per this repository's convention a
threshold is a numerical claim: it is recorded with the record it was measured
against and the firing rate it produces on that record.

**Churn arithmetic.** `health/metrics.json` is 2039 B and `health/progress.svg`
is 8469 B at `calibration-data` @ `efd55e6`. In the observed regime the change
adds **zero** commits, because all 8 renders already committed. In a fully quiet
archive it adds one 2039 B blob per day, ~744 KB/year, which is 0.06% of the
1.17 GB branch per year — and it is incurred only in the regime that the heartbeat
exists to cover.

## Design decisions

**Rejected: put `generated_at` in the SVG.** This is the most direct way to show
dashboard age, and it is explicitly forbidden. NFR-3 and the ADR-025 amendment
both state that the SVG carries no clock reading, because a timestamp in the
graphic changes its bytes every run, which would make FR-6's guard unreachable
and commit 8.5 KB to a 1.17 GB branch daily forever. It also would not work:
the age rendered at render time is always zero.

**Rejected: a separate `health/render-log.tsv`.** This was the first design, by
direct analogy with ADR-025's poll ledger, and it was dropped once the first part
landed. Since `metrics.json` now commits on every render, every render already
produces exactly one commit, so `git log health/metrics.json` *is* the append-only
render log. A separate file would add a fourth entry to the `health/` contract
that the ADR-025 amendment enumerates, plus a new parse path and its tests, to
store information git already holds. The poller needed a ledger because its no-op
runs produced no commit at all; that is no longer true here.

**Rejected: alarm only inside the health workflow.** Insufficient on its own, for
the reason stated above: a dead renderer cannot run its own check. Kept as a
secondary report of a gap already closed.

**Rejected: a separate scheduled watchdog workflow.** It would be a third writer
and a third concurrency group to reason about against a branch two workflows
already race on, and it would itself need a watchdog. The poller is already
hourly, already alive, and already has the file on disk.

**Rejected: failing the poll when the dashboard is stale.** The poll job's
contract is to fetch calibration data and file it. A dashboard problem must never
cost a poll or its ledger row, which are the evidence ADR-025 exists to keep. The
step reports and yields.

**A future-dated heartbeat is treated as broken, not fresh.** A `generated_at`
ahead of now would otherwise read as fresh forever and silently disable the
alarm, which is the same class of failure this change exists to remove, so it is
not left unguarded. The tolerance is one hour; runner clocks are NTP-synced and
inter-run skew is sub-second, so a gap approaching an hour is a fault.

**Every unreadable shape is "undecidable", never "stopped".** Absent, malformed
JSON, missing field and unparseable timestamp all exit 3 with a warning. None of
them is evidence that the renderer stopped, and "the renderer stopped" is the one
conclusion this script must not reach without grounds. Exit 3 matches
`pipeline_health`'s existing "nothing to publish" convention.

## Verification

All commands run at `d119e50` in a clean Python 3.12.10 interpreter at a short
path, not the repository `.venv` (see NC-021's note on that distinction).

```bash
python -m ruff check .                       # All checks passed (66 files)
python -m ruff format --check .              # 66 files already formatted
python -m mypy --strict                      # no issues in 38 source files
python scripts/check_ids.py                  # no duplicate or colliding ids
python -m pytest tests/ --collect-only -q -o addopts=""   # 643 collected
python -m pytest tests/ -q -o addopts=""                  # 643 passed
```

**`ubuntu-latest` is the authority for the pass count**, and PR #102's CI reports
`642 passed, 1 skipped` at `f2b11b6` on both `test (3.11)` and `test (3.12)`,
which is the same 643 collected. The single skip is the `slow`
`tests/test_feature_distribution.py::test_the_committed_survey_reproduces_from_the_archive`,
which skips when the pinned `calibration-data` ref is not fetched on the runner;
the laptop run reached the archive and so passed all 643 there. CI ran at the
head SHA, not a stale one, and the PR is `MERGEABLE` rather than `DIRTY` — worth
stating because `ci.yml` does not dispatch on a conflicted PR while CodeQL keeps
passing, so a green check set can otherwise mean no tests ran at all.

**The commit step was executed, not reasoned about.** The `Commit the render`
run block was extracted from the workflow YAML and run against a throwaway git
repository, with `push_with_retry.sh` stubbed, over the three reachable cases:

| Case | Result |
| --- | --- |
| SVG unchanged, `metrics.json` moved | commits `health: heartbeat, rendered dashboard unchanged`, containing **only** `health/metrics.json` |
| both changed | commits `health: refresh pipeline dashboard`, containing both files |
| nothing changed | no commit, `::warning::nothing staged after a successful render` |

The first row is the defect: before this change that case produced no commit at
all. The second confirms FR-6 still holds for the graphic and that the existing
message keeps its existing meaning.

**The reader was run against the live branch.** `health/metrics.json` from
`calibration-data` @ `efd55e6` (`generated_at` 2026-09-17T08:45:00.574976Z):

- judged at 2026-09-17T13:45:00Z → `::notice::` ... `5.0 h ago (tolerance 48 h)`, exit 0
- judged at 2026-09-19T10:00:00Z → `::warning::` ... `49.2 h ago`, exit 1

**Workflow syntax.** Both files parse as YAML, and every `run:` block in both was
extracted and checked with `bash -n`; all nine parse.

**Not verified from a local checkout, and not verifiable from one.** No Actions
run has yet exercised the new commit step or the new poll step on the real
branch, because neither trigger fires until this merges: the poll step needs an
hourly run from the default branch, and the heartbeat-only commit path needs a
render on a day whose SVG does not move, which has not happened in the eight
renders so far. The first scheduled poll after merge is the first live evidence,
and the first heartbeat-only commit may be considerably later.

## Related docs

- Issue #48 — the pipeline-health dashboard this repairs; FR-6, FR-7, NFR-3,
  NFR-9, UC-5, UC-6 and §11's counterfactual
- ADR-025 and its 2026-09-05 amendment in `docs/decisions.md` — the ledger
  principle this applies to the branch's second writer, and the `health/` contract
- `docs/implementations/2026-09-05-pipeline-health-dashboard.md` — the original
  implementation, whose §"A quiet archive therefore reaches byte-stability"
  paragraph describes the state this change makes observable
- NC-021 (suite size), NC-050 and NC-051 (the `hours_since_last_new_state`
  bounds, which measure the *device* clock, not this one), NC-053 (this bound)
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` — #45,
  the outage whose cost motivates the whole pipeline
