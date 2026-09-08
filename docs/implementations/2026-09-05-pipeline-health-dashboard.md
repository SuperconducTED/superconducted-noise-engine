# 2026-09-05: Pipeline health dashboard

## Problem / Motivation

Issue #48 adds a continuous, auditable health signal to the `calibration-data`
archive. File count is not the training-data unit: repeated documents can have
the same `properties.qubits` measurements. The dashboard therefore reports
distinct qubit-block states, polling coverage, and visible scheduler gaps
without scanning the snapshot archive. It extends ADR-025's ledger layout while
leaving the IBM fetch path, snapshot schema, and ADR-020 `snapshots/` layout
unchanged.

The dashboard separates documents filed, distinct device states acquired, and
poll events observed. This reveals both a stopped scheduler and a healthy
scheduler that is only collecting repeated qubit states.


## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/canonical_snapshot_digest.py` | Adds the importable `qubit_digest()` API and `--scope qubits` while preserving document-digest defaults. |
| `scripts/file_snapshots.sh` | Appends one qubit-digest state-index row for each newly archived document, and pushes through the retry helper. |
| `scripts/push_with_retry.sh` | Replays a data-branch commit onto the tip and retries, so the poll and health pushes can race safely. |
| `scripts/backfill_state_index.py` | Idempotently appends existing snapshots in timestamp order, with a `--rebuild` mode that regenerates the whole index once the poller has started appending. |
| `scripts/pipeline_health.py` | Reads compact health inputs, writes metrics JSON, and renders a deterministic self-contained SVG. |
| `.github/workflows/calibration-health.yml` | Daily sparse-checkout renderer with an optional one-time backfill and commit-on-change behaviour. |
| `.github/workflows/calibration-poll.yml` | Keeps hourly polls isolated from health-render cancellation. |
| `.gitignore` | Ignores generic pytest scratch paths created during local verification. |
| `docs/decisions.md` | Adds the ADR-025 health-tree amendment. |
| `docs/numerical-claims.md` | Registers the dashboard's test-count and backfill measurements. |
| `tests/test_canonical_snapshot_digest.py` | Pins qubit-scope behaviour and the public digest API. |
| `tests/test_backfill_state_index.py` | Tests timestamp ordering, idempotency, and unsafe partial-index refusal. |
| `tests/test_pipeline_health.py` | Tests state metrics, poll-hour boundaries, deterministic SVG output, and basic SVG safety. |
| `tests/test_file_snapshots.py` | Exercises per-poll index appends and undecidable digest handling end to end. |

## Implementation approach

The poll path calculates a sha-256 digest of qubit only for exactly the new snapshot being filed. It compares that digest with the append-only index to set `is_new_state` so the hourly job never re-parses historical snapshots.

The health job only checks `health/`, `ledger/` and the branch README in a sparse manner. It produces all the dashboard figures from the index and ADR-025 ledger, staging `health/` but committing only if the bytes changed. `generated_at` only exists in JSON; the SVG has no clock value, external resource, script, or theme-dependent foreground color.

The only archive-walking operation is the optional workflow-dispatch backfill.
It is safe to repeat only after a complete backfill: it refuses an incomplete
existing index, rather than appending historical rows after poll-side rows and
permanently corrupting `is_new_state` chronology.

### Data contracts

The append-only `health/state-index.tsv` has this fixed header:

```text
snapshot_filename<TAB>last_update_date<TAB>qubit_digest<TAB>is_new_state
```

`filename` is the archived document's name; `last_update_date` is its ISO-8601 UTC timestamp. `qubit_digest` is SHA-256 over the canonical compact JSON of `properties.qubits` only. `is_new_state` is `1` only if that digest has not been seen in a prior row. This makes the index the small, replayable source of truth for state counts without the need of scheduled jobs reading snapshots.

The renderer generates `health/metrics.json` and `health/progress.svg`. `generated_at` and the exact `hours_since_last_new_state` are present in JSON only, for provenance. The SVG carries no clock reading, so its bytes are a function of the committed index and ledger plus the position of the two rolling windows FR-5 mandates. A quiet archive therefore reaches byte-stability within 30 days of its last new state, after which repeated renders commit nothing; `tests/test_pipeline_health.py::TestCommitOnChange` pins both halves of that.

### Workflow lifecycle

1. The hourly poll files a payload through `file_snapshots.sh`.
2. Each `decision=new` appends exactly one state-index row; every poll outcome
   remains in ADR-025's monthly ledger.
3. The daily health workflow sparsely checks out only `health/` and `ledger/`,
   renders the two health artifacts, and commits material output only.
4. A manual `backfill=true` job checks out `snapshots/`, builds the complete
   index, commits it, then lets the render job consume that committed input.
   Normal scheduled runs never traverse snapshots.
5. Poll and health workflows use separate concurrency groups so a health render
   cannot cancel an hourly poll and erase its ledger evidence.

### Publishing constraints

The SVG has an explicit background and fixed palette for GitHub light and dark
contexts. It is self-contained: no script, `foreignObject`, remote font,
external image, or URL is emitted. Candidate floor marks are labelled by source
rather than asserting one authoritative training floor.

## Issue #48 decisions and external review

The implementation adopts the issue's recommended daily render cadence. Hourly
measurement remains in the poll-side index and ledger, while daily rendering
avoids roughly 8,760 SVG commits per year. The ADR-025 amendment records the
new `health/` tree and is intentionally pending Mert Efe Şensoy's review and
out-of-band routing to Dr. Fırat Akba before workflow enablement.

Alarm thresholds remain presentation-independent configuration, not hard-coded
colours. The proposed operational starting points for the issue thread are
72-hour ledger coverage below 75% (the observed collapse began at 16 polls/day,
below the normal 22–23/day) and 24 hours without a new state. These are
proposals based on measured scheduler history; adoption requires the issue
discussion and review.

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
`--floor` is **required**: `pipeline_health.py` holds no floor value at all, and
`tests/test_pipeline_health.py` asserts that neither `630` nor `675` appears in
its source. The values live in the health workflow's `HEALTH_FLOORS` env block
and can be overridden per dispatch. The default readout shows the documented
`NC-012=630` candidate and the `TanhBellMF=675` alternative together, labelled
by source. The implementation does not decide the true training floor.

The staleness headline is rendered as a **band** (`under 24 h`, `24 h to 3
days`, `3 to 7 days`, `over 7 days`, `never`), not as an elapsed-hours figure.
The exact hours stay in `metrics.json`. This is not cosmetic: a rendered clock
reading advances on every run, so the rendered bytes would differ every time and
FR-6's commit-on-change guard could never fire, putting 8.3 KB on a 1.17 GB
branch daily forever. The band bounds are the two thresholds the dashboard
already reasons in, 24 h being the proposed staleness alarm and 72 h the
poll-coverage window.

The renderer runs daily rather than every poll to limit branch churn while the
index and ledger retain hourly measurement. The poller and renderer use
**separate** concurrency groups: sharing one would let a health render cancel a
queued poll, and a cancelled poll writes no ledger row, which is invisible in
exactly the instrument this dashboard exists to provide. The cost of that choice
is that the two pushes to `calibration-data` can race, so both go through
`scripts/push_with_retry.sh`, which replays the commit onto the branch tip and
retries. Replay rather than merge: each workflow writes a tree only it touches,
so a textual conflict means something unmodelled happened and the run must fail
loudly instead of guessing.

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
2. Merge the source and workflow changes. **The poller starts appending index
   rows on its next run** (`cron: 37 * * * *`), and at NC-030's republication
   rate the first `decision=new` typically lands within an hour or two.
3. Dispatch **Calibration Pipeline Health** with `backfill=true`. If the poller
   has already appended a row, the append path refuses to run rather than mark
   long-known states as new; dispatch with `rebuild=true` as well, which
   regenerates the index in `last_update_date` order. Record the indexed
   calibration-data ref and reconcile its result with NC-025's historical
   504-state result at `f0930b9`; investigate a mismatch.
4. Dispatch it again without backfill. Unchanged inputs must result in no commit.
5. Update the calibration-data README to embed
   `![Pipeline health](health/progress.svg)` and link ADR-020 and ADR-025.
6. Verify the committed SVG on GitHub in both themes and retain PR evidence.

For a local render against a calibration-data checkout:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/pipeline_health.py --root path\to\calibration-data `
  --floor NC-012=630 --floor TanhBellMF=675
```

`--floor` is required (FR-7). The workflow supplies it from `HEALTH_FLOORS`; a
local run must state the candidates it is rendering against.

For the idempotent local backfill:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/backfill_state_index.py --root path\to\calibration-data
# add --rebuild to regenerate a skewed or partially poll-written index
```

The second backfill run should append zero rows, and a second `--rebuild` run
should leave the index byte-identical. Neither command makes a network
request; both use committed files in the supplied checkout.

## Verification

Executed on 2026-09-05:

- `.\\.venv\\Scripts\\python.exe -m pytest --basetemp .pytest-tmp tests/test_canonical_snapshot_digest.py tests/test_pipeline_health.py tests/test_backfill_state_index.py tests/test_file_snapshots.py -q` — 47 passed.
- `.\\.venv\\Scripts\\python.exe -m pytest --basetemp .pytest-tmp tests/ -q` — 290 passed in 32.87s at `039afdc`.
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
