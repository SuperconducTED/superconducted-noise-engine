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
| `tests/fixtures/pipeline_health/` | Committed archive, ledger and golden artifacts behind the section 9.2 end-to-end check. |

## Implementation approach

The poll path calculates a sha-256 digest of qubit only for exactly the new snapshot being filed. It compares that digest with the append-only index to set `is_new_state` so the hourly job never re-parses historical snapshots.

The health job only checks `health/`, `ledger/` and the branch README in a sparse manner. It produces all the dashboard figures from the index and ADR-025 ledger, staging `health/` but committing only if the bytes changed. `generated_at` only exists in JSON; the SVG has no clock value, external resource, script, or theme-dependent foreground color.

The renderer refuses to publish from an index that names no documents. It exits
**3**, writes nothing, and emits a `::warning::`; the workflow gates its commit
step on that, so nothing is staged and nothing is pushed. This is the cold-start
case and it is not hypothetical: `calibration-data` has no `health/` tree until
the one-time backfill is dispatched, and the poll workflow creates the index with
a header row on its first run after merge. Without the guard, the first scheduled
render would publish `0 states` on a branch holding hundreds and commit it, and
the branch README embeds that graphic. A dashboard reporting a zero it cannot
justify is the failure `docs/numerical-claims.md` exists to prevent, so the
renderer declines rather than guesses. Argparse keeps exit **2** for a bad
invocation.

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
`--floor` is **required**: `pipeline_health.py` holds no floor value at all. The
values live in the health workflow's `HEALTH_FLOORS` env block and can be
overridden per dispatch, and `tests/test_pipeline_health.py` reads that block
out of the workflow and asserts none of its values appears in the renderer's
source, so the guard follows the configuration instead of pinning two literals.

The default readout shows the `NC-012=1170` candidate and the `TanhBellMF=1215`
alternative together, labelled by source. Both moved on 2026-09-09: #56 FR-10
corrected NC-012 from `630` to `1170` after NC-045 measured the rule base in use
at 234 trainable parameters, and NC-046 measures TanhBellMF at 243, so the
alternative is 1215 rather than the 675 the issue body reasoned to before the
count was taken. The implementation does not decide the true training floor, and
NC-045 is still a provisional laptop measurement.

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
   Until step 3 has run, a scheduled render exits 3 and publishes nothing, so the
   order of steps 2 and 3 cannot corrupt the branch; it only delays the dashboard.
5. Update the calibration-data README to embed
   `![Pipeline health](health/progress.svg)` and link ADR-020 and ADR-025.
6. Verify the committed SVG on GitHub in both themes and retain PR evidence.

For a local render against a calibration-data checkout:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/pipeline_health.py --root path\to\calibration-data `
  --floor NC-012=1170 --floor TanhBellMF=1215
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

### As of `e3c4ea8` (2026-09-09) — PR #70 second review round

The 2026-09-05 block above is left exactly as measured on that date. This
section records the state after the review fixes, per the convention that a
dated snapshot is reconciled by appending rather than by rewriting its rows.

- `ruff check .` and `ruff format --check .` over the whole repository — clean,
  57 files.
- `mypy --strict src/superconducted` — clean, 25 files. `mypy` with the project
  config (`src/superconducted` **and** `scripts`) — clean, 34 files.
- `python scripts/check_ids.py`: no duplicate or colliding ADR / NC identifiers.
- `python -m pytest tests/ --collect-only -q -o addopts=""` — **391 collected**,
  registered as NC-021 at this commit.
- `python -m pytest tests/ -q` — 383 passed, 8 failed. All 8 are
  `tests/test_file_snapshots.py` cases that reproduce identically at the merge
  base `645b4d1`: on Windows the sandboxed digest subprocess returns
  `collision-unreadable` where the assertion expects `collision`. They are an
  environment artifact of running the bash harness under Git Bash, not a defect
  on this branch, and CI on `ubuntu-latest` is the authority for the pass count.
- `bash -n scripts/push_with_retry.sh scripts/file_snapshots.sh` — both parse.

The FR-6 defect that opened this round was reproduced before it was fixed and
re-checked after. Rendering one fixture twice, 24 h apart, with a byte-identical
committed index and ledger:

| | Before | After |
| --- | --- | --- |
| `progress.svg` bytes | differ | identical |
| Cause | `Hours since last new state: 39.3` → `63.3` | staleness rendered as a band |
| Effect on FR-6 | guard could never fire; a commit every run | guard fires; no commit |

The exact figure is still available: `metrics.json` for that fixture carries
`hours_since_last_new_state: 1551.28` beside `staleness_band: "over 7 days"`, so
UC-6 traceability is unchanged and the section 9.3 provenance test asserts it
mechanically.

**Still not verified, and not verifiable from a local checkout.** Neither
workflow has run in GitHub Actions, `health/` does not yet exist on
`calibration-data`, and that branch's `README.md` still carries the dead
"PR ticket #002" reference FR-8 exists to remove. The section 10 evidence — a
backfill dispatch, a no-change render producing no commit, and the SVG shown in
both GitHub themes — still requires a real run and a push.

### As of `7ec173f` (2026-09-10) — PR #70 third review round

The two blocks above are left exactly as measured on their dates. This section
records the state after the round-3 fixes, per the append-not-rewrite
convention.

**The blocker: one canonicalisation for the qubit digest.**

`qubit_digest` hashed each parameter's `date`. `_payload_body`, eleven lines
above it in the same module, drops it; that is #80 (`0a4271b`), which reached
this branch through the `4bea68c` merge and never got applied to the qubits
scope, although FR-1 asks that scope to reuse the same canonicalisation. The
module therefore held two contradictory answers to one question.

The question is not a matter of taste, because the two scopes ask different
things. The full document digest drives the collision path, where two live
payloads are compared and *any* difference belongs in front of a human, so it
keeps `date`. The qubits scope counts **device states**, where a re-measurement
that reproduced the identical value is the same state and a history-endpoint
re-stamp is provenance. Counting a re-stamp as a second state inflates
`states_total` against a floor whose own caveat already says distinct is only an
upper bound on independent.

It was reachable, not theoretical: the poll workflow supports historical sweeps
(`historical_start`, `IS_BACKFILL`), the history endpoint re-stamps the
parameter records it synthesises, and `health/state-index.tsv` is append-only,
so a swept document filed as a phantom second state could not be repaired
without a full `--rebuild` that would reproduce it.

Measured before changing anything, over 60 consecutive documents at `f0930b9`:

| Definition | Distinct states | Pairs equal only after stripping |
| --- | --- | --- |
| shipped, `date` hashed | 34 | n/a |
| aligned, `date` stripped | 34 | 0 |

The sample is one contiguous run, 6.7% of the 894 documents at that ref, and it
shows 43.3% duplication against NC-025's 43.6%, so it is representative of the
thing being measured. It is an indication that the alignment does not move the
count, **not** a re-run of the issue §48 step-4 reconciliation. See the NC-025
note: that reconciliation was performed under the dates-included definition and
is re-owed under this one, from the dispatched backfill.

**The major: trailing-window metrics no longer depend on append order.**

`build_metrics` read `is_new_state` out of the index, and that column is decided
by append order, not chronology. A sweep files documents older than rows the
hourly poller already appended; each digest not yet present is recorded
`is_new_state=1` even where a later-dated row already carried that state. The
failing case is this dashboard's own headline use, issue §11 point 2: the
72-hour strip exposes a stall, the operator sweeps the gap, and the swept rows
land *inside* the trailing windows and over-report the recovery.

`first_sightings` now derives the earliest `last_update_date` per digest, so
`states_added_24h`, `states_added_7d`, `states_per_day_7d`,
`new_states_per_day_30d` and `hours_since_last_new_state` are all independent of
append order and no `--rebuild` is owed after a sweep. `index_head` is the one
field that still moves with order, which is correct: FR-4 defines it as the last
row consumed, so it is provenance for the render rather than a measurement.

One consequence worth stating plainly, because it looks like a regression and is
not: filling a gap can make the archive read *staler*. If a swept document shows
the device was already in a state six hours ago that the poller first recorded
two hours ago, `hours_since_last_new_state` becomes 6, not 2. The 2 was an
artefact of the gap. `TestHistoricalSweep` pins this alongside the guard that a
genuine acquisition still counts.

`file_snapshots.sh` warns when it appends a row older than the index maximum.
The metrics no longer depend on the column, but the column itself is still wrong
after a sweep and anything else reading the index has to know.

**Verification at `7ec173f`.**

- `ruff check .` and `ruff format --check .` over the repository: clean, 57 files.
- `mypy --strict` on the three scripts: clean.
- `python scripts/check_ids.py`: no duplicate or colliding identifiers.
- `python -m pytest tests/ --collect-only -q -o addopts=""`: **419 collected**,
  registered as NC-021 at this commit.
- `python -m pytest tests/ -q`: **419 passed**, 0 failed, 46.6 s. Note this
  differs from the round-2 block: the 8 `tests/test_file_snapshots.py` failures
  recorded there did not reproduce, in a clean interpreter at a short path
  rather than the repository `.venv`. They were an environment artefact, as that
  block said, and `ubuntu-latest` remains the authority for the pass count.
- `bash -n scripts/file_snapshots.sh scripts/push_with_retry.sh`: both parse.

**Still not verified, and still not verifiable from a local checkout.** The
section 10 evidence that was outstanding after round 2 is unchanged by this
round: `calibration-data` has no `health/` tree, its `README.md` still carries
the dead "PR ticket #002" reference FR-8 exists to remove, and no Actions run
has yet shown an *unchanged* render producing no commit; run `34404140171`
skipped its commit step through the cold-start exit-3 guard, which is a
different path. The ADR-025 amendment also still needs the out-of-band routing
`docs/team.md` requires, and that routing now has more to carry: this round
changes what a row in `health/state-index.tsv` means.

### As of `c966ba4` (2026-09-10): section 9.2 closed, and what closing it found

Appended rather than folded into the block above, so each figure keeps the
commit it was measured at.

**Section 9.2 now has the fixture it asks for.** `tests/fixtures/pipeline_health/`
holds four snapshot documents and a seven-row ledger; `TestEndToEndFixture` runs
`backfill_state_index` then `pipeline_health` over them and compares
`metrics.json` and `progress.svg` byte for byte against committed goldens. Round
2 recorded the field-and-determinism approach as a deliberate deviation, which
was defensible, but it left the one artifact the team actually reads with no
guard on its bytes. Golden files are worth their maintenance cost here precisely
because `progress.svg` is published into the branch README, and regeneration is
one documented command rather than a hand edit. The guard was checked as a
guard: changing one hex digit of one fill colour fails it, and it passes again
on revert.

The fixture is chosen rather than arbitrary. `20260901T060000000000Z` repeats the
previous document's measurements under a later parameter `date`, so the four
documents are two device states and the round-3 blocker is proven over the real
archive path. Rendered at `2026-09-02T12:00:00Z`, state B was first seen exactly
24 h earlier, which pins two strict comparisons nothing else covered:
`staleness_band` tests `hours < limit`, and the acquisition window tests
`timestamp > window24`. `tests/fixtures/pipeline_health/README.md` records both.

**Closing it found a defect nothing else could have.** `Path.write_text`
translates newlines to `os.linesep`, so the renderer wrote CRLF from Windows and
LF from the workflow's ubuntu runner for byte-identical inputs. NFR-3 is a
statement about identical inputs producing identical artifacts, and the platform
axis was the one nobody was testing, because every previous test compared one
platform against itself.

It was reachable. This document tells the reader to render locally, and
`calibration-data` carries no `.gitattributes` to normalise line endings, so two
writers alternating would rewrite all 8 KB of `progress.svg` on a 1.17 GB branch
and fire FR-6's commit-on-change guard with nothing to report. Both artifact
writes now pass `newline="\n"` explicitly.
`backfill_state_index._write` already had this right.

**Verification at `c966ba4`.**

- `ruff check .` and `ruff format --check .`: clean, 57 files.
- `mypy --strict` under the project config: clean, 34 files.
- `python scripts/check_ids.py`: no duplicate or colliding identifiers.
- `python -m pytest tests/ --collect-only -q -o addopts=""`: **423 collected**,
  registered as NC-021 at this commit.
- `python -m pytest tests/ -q`: **423 passed**, 0 failed.

The three items listed as outstanding in the block above are unchanged: an
Actions run showing an unchanged render producing no commit, FR-8 on
`calibration-data` itself with the both-themes screenshot, and the ADR-025
routing plus a second reviewer.

### As of `1309335` (2026-09-10): the second reviewer's finding, and what it measured

Appended rather than folded into the blocks above, so each figure keeps the
commit it was measured at.

**`polls_yielding_new_state_24h` counted documents, not device states.**

The field summed ledger rows carrying `decision=new`. That decision records only
that the *stamp* was not already archived, which the archive says is a different
question from whether a device state was acquired: at NC-025's duplication two
in five newly filed documents carry a state we already hold.

The `## Mathematical / Statistical details` section above states the rule that
produced this, and is superseded here rather than rewritten: "Only ADR-025
decision `new` contributes to `polls_yielding_new_state_24h`" is a necessary
condition, not a sufficient one. The document filed by that poll must also be
the **first sighting** of its qubit digest.

**Measured, not argued.** Over `calibration-data` @ `cb7a8c2`, backfilled with
this branch's own `backfill_state_index.py` and rendered at the last ledger
instant, `2026-09-10T05:08:31Z`:

| | old expression | corrected join |
| --- | --- | --- |
| `polls_fired_24h` | 6 | 6 |
| `polls_yielding_new_state_24h` | **6** | **3** |
| `states_added_24h` | 3 | 3 |

The old field reported that 100% of polls in the trailing 24 hours produced a
new device state, on an archive measured at 43.4% duplicate in the same run.
The corrected figure agrees exactly with `states_added_24h` for that window,
which is what a stretch of live polling with no sweep should produce.

The committed fixture published the same defect and is what exposed it:
`expected/metrics.json` carried `polls_yielding_new_state_24h: 2` beside
`states_added_24h: 0`, and one of those two documents is the one
`tests/fixtures/pipeline_health/README.md` calls "a plain duplicate, the
ordinary case". Two mutually inconsistent numbers, in one published document,
in the dashboard whose stated reason for existing is that a file-counting
instrument lied for three months.

**The fix.** `PollRow` now carries the ledger's `last_update_date` column, which
holds the document stem, so a poll outcome can be joined to the state index
(`stem` against the index's `stem.json`). The field counts distinct digests
whose first sighting was filed by a `decision=new` poll inside the window, and
resolves "first sighting" through `first_sightings` rather than the index's
`is_new_state` column. Counting digests rather than rows means a document
indexed twice cannot count twice; resolving through `first_sightings` means the
answer is independent of index append order, for the same reason every other
window here is.

`last_update_date` is now **required** in a ledger row rather than defaulted. A
ledger lacking the column would otherwise give every `PollRow` an empty document
and silently zero the join, which reads as a healthy poller yielding nothing.

**The two poll fields read a different clock, deliberately.** Every state window
is keyed on `last_update_date`, the device's own clock. The two poll fields
answer a question about us rather than about the device, so they are keyed on
poll time. `polls_yielding_new_state_24h` therefore spans both, and it can
legitimately exceed `states_added_24h` after a historical sweep: a poll that
recovers a state the device published a week ago did acquire something we did
not hold, while the device did not produce it today. When they disagree, the
archive gained by catching up rather than by keeping up.
`TestHistoricalSweep::test_a_recovered_state_counts_for_the_poll_but_not_for_the_device`
pins that reading.

**One correction to the block above, recorded rather than edited.** The
`## Mathematical / Statistical details` section says the poll strip "comprises
the 72 UTC hour buckets ending with the current hour". It does not, and must
not: `build_metrics` ends the window at the last **complete** hour, and
`test_zero_rate_has_no_finite_projection_and_hour_boundary_is_included` asserts
`poll_hours_72h[-1] is False` for exactly that reason. Including the current
partial hour would make a healthy poller read 71/72 for most of every hour.

**Golden regeneration.** Regenerated through the documented
`PIPELINE_HEALTH_REGOLD=1` path, never by hand. `metrics.json` moved by one
byte, `2` to `1`; `progress.svg` is byte-identical, because the field is not
rendered. That asymmetry is itself the check: the fix reached the audit surface
and left the published graphic alone, so FR-6's commit-on-change guard sees
nothing on this change.

**Verification at `1309335`.**

- `ruff check .` and `ruff format --check .`: clean, 57 files.
- `mypy --strict` under the project config: clean, 34 source files.
- `python scripts/check_ids.py`: no duplicate or colliding identifiers.
- `python -m pytest tests/ --collect-only -q -o addopts=""`: **427 collected**,
  registered as NC-021 at this commit.
- `python -m pytest tests/ -q`: **427 passed**, 0 failed.

**Issue §48 step 4 re-run under the current digest definition.** The block for
`7ec173f` records the step-4 reconciliation as re-owed after the digest change,
with a 60-document sample standing in for it. It has now been run in full, with
this branch's own scripts, and the count does not move:

| ref | documents | states, `date` hashed | states, `date` stripped | merges | duplication |
| --- | --- | --- | --- | --- | --- |
| `f0930b9` | 894 | 504 | 504 | 0 | 43.6242% |
| `46f93c8` | 936 | 537 | 537 | 0 | 42.6282% |
| `cb7a8c2` | 994 | 563 | 563 | 0 | 43.3602% |

Stripping is a function, so the new partition is a coarsening of the old one and
the count could only have fallen; it does not, at any of the three refs. The
normalisation is nonetheless doing real work rather than being a no-op: 100% of
the 861,789 qubit parameter records at `f0930b9` carry a `date`, and every one
of the 894 documents changes its qubit bytes under stripping. Wherever a
parameter's `date` moved, at least one `value` moved with it.

This is a provisional laptop measurement in the sense `docs/team.md` means. The
canonical figure remains whatever the dispatched `backfill=true` produces at a
named ref, and the NC-025 and NC-047 notes still say so.

**Still open**, unchanged by this commit: FR-8 on `calibration-data` with the
both-themes screenshot, the ADR-025 routing to Dr. Akba, and a second reviewer
approval. Also open from the second review and deliberately not fixed here: the
non-unique `snapshot_filename` underlying `_chronological_key` and the
backfill's `existing` set, the partial final bucket in
`new_states_per_day_30d`, the unqualified `projected_date`, `polls_fired_24h`
counting ledger rows rather than polls, and the missing NC-046 upper floor in
`HEALTH_FLOORS`.

### As of `2321301` (2026-09-10): the second reviewer's minors

Appended, not folded into the blocks above. Five code findings and one operating
note. None of them moves a number on the archive as it stands today, which is
why they are minors; each of them makes one wrong under a condition the archive
already contains or the runbook already invites.

**`snapshot_filename` is not unique, and two places assumed it was.** The
archive holds one `last_update_date` under two month partitions: at `f0930b9`,
`snapshots/2026-06/ibm_fez/20260630T214008000000Z.json` and its 2026-07 twin are
different blobs (`f970f706` and `8219d293`) sharing an instant, a backend and a
filename, so 894 paths carry 893 distinct names. The 2026-07 copy is misfiled
against ADR-020, since its own stem names June, but the pipeline has to be
correct over the archive as it is.

- `_chronological_key` tied on all three of its components, so `sorted` fell
  through to `Path.glob`, which reports `os.scandir` order and need not agree
  between an ext4 runner and an NTFS checkout. The month partition is now part
  of the key.
- `backfill`'s `existing` set reported the second copy as already indexed and
  dropped it, silently, because nothing downstream can miss a row it never saw.
  It is a multiset now: indexed as many times as the archive holds it, which is
  the same answer as a set wherever names are unique. A half-indexed pair now
  reaches the incompleteness refusal instead of being quietly completed wrong.

Both were latent rather than active, because the two copies happen to share a
qubit digest, so the emitted rows were byte-identical either way. Verified: the
index built at `f0930b9` is byte-identical before and after the change, sha256
`77458adec4ca56fed7afa3df57bcfa494f15f26c8a221a1d8b960b493db04068`, 894 rows,
504 distinct states, second run appends zero.

**The acquisition sparkline ended in a stub.** `new_states_per_day_30d` anchored
its thirty buckets on today, leaving a partial day in the last one. The
scheduled render fires at `cron: 17 3 * * *`, so the rightmost bar was drawn
from 3 h 17 min of data, **13.7% of a day**, on every scheduled run, in the FR-5
panel a reader consults to ask whether the archive is still accumulating. It is
now thirty *complete* days ending yesterday. Today is not lost:
`states_added_24h` and `states_per_day_7d` both cover it, on rolling windows
where a partial day is not a distortion. A side benefit for FR-6: these buckets
now change once a day rather than continuously, so a day that gained nothing has
one fewer reason to move the rendered bytes.

**`polls_fired_24h` counted ledger rows, not polls.** `file_snapshots.sh` writes
one row per staged document, so a dispatched historical sweep files an entire
gap under a single `POLL_TIME`. Measured on the live ledger at `cb7a8c2`:

| | value |
| --- | --- |
| ledger rows | 129 |
| distinct poll instants | 53 |
| rows written by the largest single poll | **52** |

Left as rows, a reader of UC-5 comparing this against #45's 22 to 23 runs/day
would have read one sweep as a poller firing twice an hour, in the panel that
exists to make scheduler health legible. FR-4's parenthetical says "ledger rows
in the trailing 24 h", which assumed one row per poll; the field name and UC-5
govern, and the row count is recoverable from the ledger itself.

**`HEALTH_FLOORS` rendered part of a measured range.** NC-046 registers 234 to
252 parameters, floor 1170 to 1260. The workflow shipped 1170 and 1215, so the
top of the bracket was invisible. That is not cosmetic: `max_floor` sets the
progress bar's full scale, so 504 states drew as 41.5% complete where the honest
worst case is 40.0%, and a bar that reads fuller when a candidate is omitted is
the failure issue §1.2 is written to prevent. All three now ship, and every
label names the register row it traces to. `TanhBellMF` alone did not: it is a
membership-function shape, not a source, so FR-7's "carry its source" was half
met and a reader could not grep it.
`TestFloorsAreConfiguration` now reads NC-046's registered range out of
`docs/numerical-claims.md` and asserts the shipped set brackets it, so the next
correction to that row fails the suite rather than quietly rescaling the bar.

**The one-time rebuild races the poller.** The `backfill=true rebuild=true`
dispatch faults in ~1.3 GB before pushing a whole-file rewrite of
`health/state-index.tsv`, and the poller appends to that same file on
`cron: 37 * * * *`, filing a new document in most hours (NC-030). A poll landing
inside the job's window leaves `push_with_retry.sh` replaying a rewrite onto an
append, which conflicts. Conflicting is the designed outcome, since a silent
merge would drop the poller's row, but it costs the dispatch. Recorded in the
`rebuild` input description, where the operator reads it at dispatch time, and
beside the job.

**`projected_days` and `projected_date` are now declared non-claims.** ADR-025's
amendment states it: they extrapolate a single seven-day count in a straight
line and must never be cited in `docs/numerical-claims.md`, quoted as a target
date, or carried into a runbook expectation. NC-R002 is retired in the register
for being exactly that, a projected floor date that arrived with the gate unmet.

*Design decision, recorded because the alternative was live.* Publishing an
interval instead was the other option. It was rejected: an exact Poisson
interval needs a quantile of the incomplete gamma function, which NFR-4's
stdlib-only rule turns into thirty lines of numerical code, and a method that
size needs its own register row and its own approximation-error statement. That
is a larger change than this finding justifies. The inputs are published beside
the projection instead, `states_added_7d` included, so a reader can see how much
evidence it rests on.

**Golden regeneration.** Through the documented `PIPELINE_HEALTH_REGOLD=1` path.
`metrics.json` moves the sparkline's `2` from index 28 to index 29, and
`progress.svg` moves one bar 25 px right. That is the bucket shift and nothing
else: no rendered text changed and the file is the same length.

**Verification at `2321301`.**

- `ruff check .` and `ruff format --check .`: clean, 57 files.
- `mypy --strict` under the project config: clean, 34 source files.
- `python scripts/check_ids.py`: no duplicate or colliding identifiers.
- `python -m pytest tests/ --collect-only -q -o addopts=""`: **438 collected**,
  registered as NC-021 at this commit.
- `python -m pytest tests/ -q`: **438 passed**, 0 failed.
- Rendered over the live archive at `cb7a8c2`, `--now 2026-09-10T05:08:31Z`,
  with the shipped floors: 994 documents, 563 states, 43.4% duplication, three
  ticks at x = 788.57, 816.79 and 845.00 on staggered baselines 207, 222 and
  237, every text node inside the canvas by the module's own estimator, XML
  well-formed, and no `<script>`, `<foreignObject>`, external `href`, `url(` or
  `@import`.

**Still open**, unchanged: FR-8 on `calibration-data` with the both-themes
screenshot, the ADR-025 routing to Dr. Akba, and a second reviewer approval. The
remaining review items are nits and are deliberately not taken here: the two
em dashes in the rendered SVG, `index_head` not identifying a row while
`snapshot_filename` stays non-unique, and the misfiled 2026-07 snapshot, which
is an ADR-020 defect predating this pipeline and wants its own issue.

## Related docs

- Issue #48 — pipeline-health dashboard
- ADR-025 in `docs/decisions.md` — calibration-data ledger and collision layout
- `docs/numerical-claims.md` — NC-012 and NC-025 definitions
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md`
