# 2026-05-13: calibration-poller-cron

**Date:** 2026-05-13
**Ticket:** #002
**Branch:** `feature/bengisu-calibration-poller-cron`

## Problem / Motivation

ANFIS training requires at least 630 historical IBM Quantum calibration snapshots, and no public bulk archive of these snapshots exists. The project must therefore accumulate its own dataset. At one snapshot per hour from a single backend, reaching the floor takes roughly 26 days of continuous polling, and accumulation cannot start until the polling loop is running in CI rather than on a developer workstation. This change deploys the existing `superconducted-poll` CLI as an hourly GitHub Actions workflow that commits each new snapshot to a long-lived orphan `calibration-data` branch. The poller and storage code in `src/superconducted/calibration/` are unchanged and locked; this PR is the deployment wrapper only. See ticket #002.

## What changed

| File | One-sentence description |
| --- | --- |
| `.github/workflows/calibration-poll.yml` | Hourly cron workflow that runs `superconducted-poll --backend ibm_fez` and pushes the produced snapshot to the orphan `calibration-data` branch. |
| `docs/implementations/2026-05-13-calibration-poller-cron.md` | This file. |

## Implementation approach

The workflow runs on `ubuntu-latest`, installs the package with `pip install -e .`, invokes the console-script entry point registered in `pyproject.toml`, and then commits whatever the poller produced to a dedicated orphan branch. No code in `src/superconducted/calibration/` is touched.

**Storage layout.** The poller writes to `data/calibration/{backend}/{stem}Z.json`, where `stem` is a UTC timestamp formatted as `YYYYMMDDTHHMMSSffffff`. The filename format constant lives at `src/superconducted/calibration/storage.py:30`, and the env-overridable default output directory comes from `src/superconducted/calibration/poller.py:473` (`SUPERCONDUCTED_DATA_DIR`, defaulting to `data/calibration`). The workflow re-organizes these files into `snapshots/YYYY-MM/{backend}/{stem}Z.json` on the `calibration-data` branch so that month-bucketed directories stay manageable as the dataset grows past the 630-snapshot floor.

**Concurrency and atomicity.** Snapshot writes use `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)` at `src/superconducted/calibration/storage.py:94`. A second writer landing on the same `(backend, microsecond-precision timestamp)` key receives `FileExistsError`; `save_if_new` catches that and returns `False`, leaving the original file untouched. The workflow therefore exits 0 on the rare hourly collision case rather than corrupting either snapshot. No tmp-write-then-rename pattern is involved; the open-or-fail semantic is guaranteed by the OS on both POSIX and Windows.

**Security posture.**

- `IBM_QUANTUM_TOKEN` is the only secret consumed. It lives in the repository secret store and is automatically masked in workflow logs by GitHub Actions.
- The `Run poller` step is the only place the secret is injected into the environment. No other step receives it.
- No `echo`, `set-output`, `env`, or `printenv` step exists that could format around the GitHub Actions log mask.
- The workflow declares `permissions: contents: write` and nothing else. No personal access token is configured; the snapshot push uses the workflow-scoped `GITHUB_TOKEN`.

## Mathematical / Statistical details

N/A: purely structural deployment wrapper. No formulas, statistical tests, or numeric algorithms are introduced.

## Design decisions

**Cron at minute :05, not :00.** GitHub Actions cron is best-effort, and the minute-zero slot is heavily oversubscribed across the GitHub fleet. Schedules at :00 carry a noticeably higher skip probability. Shifting to :05 puts this workflow into a quieter slot at negligible cost to data freshness.

**Orphan branch over a directory in `main`.** Snapshots are research data, not source code. Committing them on `main` would balloon the working repository, pollute `git log` for code reviewers, and make a future migration to a dedicated data repository or S3 strictly harder. The orphan `calibration-data` branch keeps the snapshot history cleanly separated and easy to relocate later.

**`contents: write` on the workflow-scoped `GITHUB_TOKEN`, no PAT.** This is the minimum permission needed to push to the same repository from within Actions. A personal access token would expand scope without buying anything and would tie token rotation to a specific maintainer.

**Single backend (`ibm_fez`) at launch.** Ticket #002 explicitly defers multi-backend polling to a follow-up. Starting with one backend keeps the first 24 hours of operation easy to verify, and any schema or rate-limit surprises surface against a single, well-understood device.

## Verification

The full 24-hour verification plan lives in ticket #002. Summary of the checks that gate this change:

- `workflow_dispatch` manual smoke test triggers one run, which produces one snapshot on the `calibration-data` branch.
- Smoke-test run logs contain zero unmasked `IBM_QUANTUM_TOKEN` strings. The check is `gh run view <run-id> --log > smoke-log.txt` followed by `Select-String -Pattern IBM_QUANTUM_TOKEN smoke-log.txt`; only the masked env declaration line should match.
- Post-merge 24-hour window: snapshot count on `calibration-data` between 22 and 25 (cron skips tolerated up to 2), no gap between consecutive snapshots larger than 7200 seconds, three randomly selected snapshot JSON files each contain `timestamp`, `backend`, and a non-empty `properties` payload, and a token-leak spot-check on three random workflow runs is clean.

Escalation thresholds:

- More than 6 consecutive missed hours: escalate to the lead. The poller already retries transient `RuntimeError` with exponential backoff, so a sustained gap implies an IBM-side outage or token expiration rather than a transient flake.
- Any unmasked token observed in any log: rotate the token in GitHub Secrets immediately, before any other action. Do not delete the offending log; it is needed for the rotation post-mortem.

## Out of scope

The following are explicitly deferred to separate tickets per ticket #002:

- Multi-backend polling. Start with `ibm_fez`; add other devices once the pipeline is proven stable.
- Old-snapshot rotation or cleanup. The dataset is the deliverable; every snapshot is retained.
- Migration to S3 or a separate data repository. The orphan branch is sufficient through paper submission.
- Slack or Discord notifications on workflow failure. GitHub's built-in failure notifications cover the early monitoring need.
- Snapshot analysis, feature engineering, or ANFIS training preparation. Separate research workstream.
- Any modification to `src/superconducted/calibration/poller.py`, `src/superconducted/calibration/storage.py`, or related interfaces. Locked; surface real bugs as new tickets rather than fixing them here.

## Open follow-ups

From ticket #002's "Open Questions / Discussion Points":

1. Multiple backends from day one, or `ibm_fez` only until the pipeline is stable? Current decision: start with one. Revisit after the 24-hour verification window.
2. Should snapshots eventually move to a separate private repository for reproducibility-artifact reasons before paper submission? Probably yes, but not now.
3. Slack or Discord notification on workflow failure? Not yet. Add only if cron skips become a real operational pain point.
4. Should the poller also ingest the arXiv:2410.00916 calibration tables as a cold-start corpus? Flagged as a follow-up research task; out of scope for ticket #002.

## Related docs

- Ticket #002, tracked as issue #3 on the SuperconducTED GitHub repository.
- `docs/team.md` for the module ownership table covering the calibration files this change deploys.
- `src/superconducted/calibration/poller.py` and `src/superconducted/calibration/storage.py` (locked; this change does not touch them).
- `CLAUDE.md` in the repository root for coding conventions, do-not-modify zones, and secret-hygiene rules.

## Review follow-ups

- PR #7 review: added a `Verify poller produced snapshots` step (fails loudly on zero-file runs, drops `|| true` from `cp`/`mv` so I/O errors surface) and tightened `timeout-minutes` from 55 to 10 to prevent a hang from starving the next scheduled tick through the `concurrency` group.
