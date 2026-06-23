# ADR-020 — Calibration snapshot schema and storage

**Status**: Accepted.

**Context**: ANFIS training requires at least 630 historical IBM Quantum
calibration snapshots. No public bulk archive exists. The team must
accumulate snapshots from a live backend at hourly cadence, starting
from zero. Every day of delay is a day of dataset that cannot be
recovered before paper submission (Issue #3).

The snapshot storage must satisfy three constraints: (1) it must not
bloat the main branch's git history, (2) it must be relocatable to S3 or
a separate repository pre-submission without breaking consumers, and
(3) it must preserve the full IBM `properties()` JSON for future schema
evolution.

**Decision**: Snapshots are stored on an orphan branch
`calibration-data` in the same repository. The branch has no common
ancestor with `main`. Directory layout:

    calibration-data/
      snapshots/
        YYYY-MM/
          <backend>/
            <ISO8601-timestamp>.json

Each snapshot file is the raw JSON returned by
`QiskitRuntimeService().backend(name).properties()`, written atomically
via `O_CREAT|O_EXCL` by `calibration/storage.py`. The poller runs as a
GitHub Actions cron workflow (`.github/workflows/calibration-poll.yml`)
on a mid-hour schedule (currently `:37`, per Issue #15).

The workflow authenticates via `IBM_QUANTUM_TOKEN` in GitHub Secrets,
uses `GITHUB_TOKEN` with `contents:write` scope (no PAT), and serializes
concurrent runs via a `concurrency` group with `cancel-in-progress:
false`.

**Consequences**:

- Main-branch `git clone --single-branch` is unaffected by snapshot
  accumulation.
- Consumers that need snapshots must fetch the `calibration-data` branch
  explicitly or read from a future S3 mirror.
- The JSON schema is IBM-defined and may change without notice. The
  typed loader (ADR-017) validates units at parse time and raises
  `CalibrationParseError` on schema drift.
- Multi-backend support is deferred. The current workflow polls a single
  backend (currently `ibm_fez`, switched from `ibm_brisbane` in PR #8).

**Source**: Issue #3 (deployment scope), PR #7 (implementation),
PR #8 (backend switch), Issue #15 / PR #17 (cron timing).
