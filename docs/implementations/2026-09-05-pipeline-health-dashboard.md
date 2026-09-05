# 2026-09-05: Pipeline health dashboard

## Problem / Motivation

Issue #48 adds a continuous auditable health signal to the `calibration-data` archive. File count is not the training-data unit: repeated documents can have the same `properties.measurements on qubits. So, the dashboard measures distinct qubit-block states, shows polling coverage and makes visible a scheduler gap without scanning the snapshot archive. This builds on the ledger layout of ADR-025. The creation of the `health/` tree requires the ADR amendment and review listed in the issue before deployment.

The dashboard separates three operational signals that the archive previously combined: documents filed, separate device states captured, and polling events seen. That distinction finds both a stopped scheduler that is no longer firing, and a healthy scheduler that is simply collecting repeated qubit states.
It does not change the IBM fetch path, json schema or ADR-020.

The dashboard shows three operational signals that the archive used to blend: documents filed, distinct device states taken, and polling events seen. This distinction detects a healthy scheduler collecting only repeated qubit states as well as stopped scheduler
This does not alter the IBM fetch path, JSON schema, or ADR-020 `snapshots/` layout.


## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/canonical_snapshot_digest.py` | Adds the importable `qubit_digest()` API and `--scope qubits` while preserving document-digest defaults. |
| `scripts/file_snapshots.sh` | Appends one qubit-digest state-index row for each newly archived document. |
| `scripts/backfill_state_index.py` | Idempotently appends existing snapshots to the state index in timestamp order. |
| `scripts/pipeline_health.py` | Reads compact health inputs, writes metrics JSON, and renders a deterministic self-contained SVG. |
| `.github/workflows/calibration-health.yml` | Daily sparse-checkout renderer with an optional one-time backfill and commit-on-change behaviour. |
| `.github/workflows/calibration-poll.yml` | Shares the calibration-data writer concurrency group with the health workflow. |
| `tests/test_canonical_snapshot_digest.py` | Pins qubit-scope behaviour and the public digest API. |
| `tests/test_pipeline_health.py` | Tests state metrics, poll-hour boundaries, deterministic SVG output, and basic SVG safety. |

## Implementation approach

The poll path calculates a sha-256 digest of qubit only for exactly the new snapshot being filed. It compares that digest with the append-only index to set `is_new_state` so the hourly job never re-parses historical snapshots.

The health job only checks `health/`, `ledger/` and the branch README in a sparse manner. It produces all the dashboard figures from the index and ADR-025 ledger, staging `health/` but committing only if the bytes changed. `generated_at` only exists in JSON; the SVG has no clock value, external resource, script, or theme-dependent foreground color.

The only archive walking operation is the optional workflow-dispatch backfill.
It does not touch existing index rows and ignores filenames that it already has indexed, so it is safe to run again after an interruption.

### Data contracts

The append-only `health/state-index.tsv` has this fixed header:

```text
snapshot_filename<TAB>last_update_date<TAB>qubit_digest<TAB>is_new_state
```

`filename` is the archived document's name; `last_update_date` is its ISO-8601 UTC timestamp. `qubit_digest` is SHA-256 over the canonical compact JSON of `properties.qubits` only. `is_new_state` is `1` only if that digest has not been seen in a prior row. This makes the index the small, replayable source of truth for state counts without the need of scheduled jobs reading snapshots.

The renderer generates `health/metrics.json` and `health/progress.svg`. `generated_at` should be present in JSON only for provenance; the SVG has no timestamp, so the same committed inputs produce byte-identical rendered output.

### Workflow lifecycle

1. The hourly poll files a payload through `file_snapshots.sh`.
2. Each `decision=new` appends exactly one state-index row; every poll outcome
   remains in ADR-025's monthly ledger.
3. The daily health workflow sparsely checks out only `health/`, `ledger/`, and
   `README.md`, renders the two health artifacts, and commits only a diff.
4. A manual run with `backfill=true` first adds `snapshots/` to sparse checkout
   and performs the sole archive-wide scan. Normal scheduled runs never do so.
5. Both workflows use `calibration-data-write` concurrency, preventing a push
   race between an hourly poll and a health render.

### Publishing constraints

The SVG has an explicit background and fixed palette for GitHub light and dark
contexts. It is self-contained: no script, `foreignObject`, remote font,
external image, or URL is emitted. Candidate floor marks are labelled by source
rather than asserting one authoritative training floor.

## Mathematical / Statistical details

`states_total` is the cardinality of distinct canonical digests of
`properties.qubits`; it is not the number of documents. With `D` indexed
documents and `S` distinct states, duplication ratio is `1 - S / D` (zero for
an empty index). The seven-day acquisition rate is new states in the preceding
seven days divided by seven. A candidate floor `F` has remaining states
`max(F - S, 0)` and projected days `remaining / rate`; the projection is null
when the rate is zero.

The poll-health strip comprises the 72 UTC hour buckets ending with the current
hour. Its coverage is the fraction of those buckets containing at least one
ledger record. Only ADR-025 decision `new` contributes to
`polls_yielding_new_state_24h`; `duplicate-partial` remains health evidence but
is not a new state.

The SVG presents these values as a progress bar with candidate-floor ticks, a
trailing 30-day acquisition-rate display, and a 72-cell UTC poll strip. A
filled strip cell means one or more ledger records in that hour. Backfill never
fabricates ledger rows, so intervals before ledger history correctly appear as
empty cells. `hours_since_last_new_state` is null when there has never been a
new state; it is a raw staleness signal, not an unapproved alarm threshold.

## Design decisions

Candidate floors are workflow configuration, not a training assertion in code.
The default readout shows the documented `NC-012=630` candidate and the
`TanhBellMF=675` alternative together, labelled by source. The implementation
does not decide the true training floor.

The renderer runs daily rather than every poll to limit branch churn while the
index and ledger retain hourly measurement. The poller and renderer share one
GitHub Actions concurrency group, preventing concurrent writes to
`calibration-data` from causing a non-fast-forward push failure.

Before the workflow is enabled, ADR-025 must be amended to include the
`health/` tree and receive the out-of-band architectural review required by
issue #48.

The document digest remains the default interface, so the existing
duplicate/collision decision path is unchanged. Qubit scope is additive and is
available through both `--scope qubits` and the importable `qubit_digest()`
function, allowing future archive consumers to deduplicate parsed payloads
without launching one subprocess per file.

## Deployment and operating procedure

1. Obtain the ADR-025 amendment and the issue-required architectural review for
   the new `health/` tree.
2. Merge the source and workflow changes.
3. Dispatch **Calibration Pipeline Health** once with `backfill=true`. Record
   the indexed calibration-data ref and reconcile its result with NC-025's
   historical 504-state result at `f0930b9`; investigate a mismatch.
4. Dispatch it again without backfill. Unchanged inputs must result in no commit.
5. Update the calibration-data README to embed
   `![Pipeline health](health/progress.svg)` and link ADR-020 and ADR-025.
6. Verify the committed SVG on GitHub in both themes and retain PR evidence.

For a local render against a calibration-data checkout:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/pipeline_health.py --root path\to\calibration-data
```

For the idempotent local backfill:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/backfill_state_index.py --root path\to\calibration-data
```

The second backfill run should append zero rows. Neither command makes a network
request; both use committed files in the supplied checkout.

## Verification

Executed on 2026-09-05:

- `.\\.venv\\Scripts\\python.exe -m pytest --basetemp .pytest-tmp tests/test_canonical_snapshot_digest.py tests/test_pipeline_health.py tests/test_backfill_state_index.py -v` — 35 passed.
- `.\\.venv\\Scripts\\python.exe -m pytest --basetemp .pytest-tmp tests/ -q` — 287 passed in 27.50s at `04fa8d1`.
- `.\\.venv\\Scripts\\ruff.exe check scripts tests/test_canonical_snapshot_digest.py tests/test_pipeline_health.py` — passed.
- `.\\.venv\\Scripts\\ruff.exe format --check scripts/canonical_snapshot_digest.py scripts/pipeline_health.py scripts/backfill_state_index.py tests/test_canonical_snapshot_digest.py tests/test_pipeline_health.py` — passed.
- `.\\.venv\\Scripts\\mypy.exe --strict scripts/canonical_snapshot_digest.py scripts/pipeline_health.py scripts/backfill_state_index.py` — passed.
- `git diff --check` — passed.

The initial attempt to run pytest inside the filesystem sandbox could not access
pytest's temporary-directory cleanup. The same focused suite passed when run
with the approved local test command above.

The real-archive backfill was also run locally without a push. It appended 894
rows at `calibration-data` reference `f0930b9` and reproduced NC-025's 504
distinct states; a second run appended zero rows. At `46f93c8`, it appended 936
rows and measured 537 states with a 42.6% duplication ratio. The generated
health tree and README are committed locally at `d7bdcd0` on
`local/calibration-data-health`, without a remote push. GitHub Actions
commit-on-change behaviour and visual inspection of the published SVG in both
GitHub themes still require a PR and remote push.

## Related docs

- Issue #48 — pipeline-health dashboard
- ADR-025 in `docs/decisions.md` — calibration-data ledger and collision layout
- `docs/numerical-claims.md` — NC-012 and NC-025 definitions
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md`
