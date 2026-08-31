# 2026-08-29: calibration yield decisions and poller defect fixes

## Problem / Motivation

Issue #45 established that the calibration dataset's phase gate is measured in a
unit that does not measure information: 894 snapshot files contain only 504
distinct device states, and the ≥630 floor is unmet under every
information-based reading. Issue #46 split out the mechanism that made the
archive misleading — `serialize_target()` emitted a non-deterministically
ordered list, so every poll rewrote its snapshot and the commit log reported 333
zero-information rewrites (479 MB) as new data.

Two things were still open when this work started. The four questions #45 poses
are product decisions and had not been taken. And nobody had determined whether
data lost to the GitHub Actions scheduler outage was recoverable — the poller
anticipates a denial it cannot actually observe, and there were **zero**
`workflow_dispatch` runs in the repository's entire history, so historical
access had never once been attempted.

Meanwhile the scheduler was, and at time of writing still is, degraded: 22–23
runs/day through 2026-08-25, then 16 / 3 / 2 / 3. Readout parameters publish
every ~4 h, so below ~6 polls/day the loss is real and unrecoverable at the time
it happens.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/calibration/poller.py` | `serialize_target()` sorts `operations` so a document always serialises to the same bytes; `fetch_snapshot()` refuses a historical response newer than the instant requested; `_coerce_utc` / `_parse_iso_utc` promoted to public `coerce_utc` / `parse_iso_utc`. |
| `src/superconducted/calibration/loader.py` | `init_error` is a first-class typed field with its own missingness counters (ADR-017 Skip pattern); `ParsedQubitCalibration` is `kw_only`. |
| `scripts/probe_historical_properties.py` | New: maps how far back historical properties can be read, and enumerates every document a window will serve. |
| `scripts/canonical_snapshot_digest.py` | New: order-insensitive snapshot digest, so a pre-fix archived file compares equal to its post-fix re-serialisation. |
| `.github/workflows/calibration-poll.yml` | Files by payload month, never overwrites an archived path, compares canonically to split `duplicate` from `collision`, appends a poll ledger, and accepts backfill inputs. |
| `.github/workflows/calibration-historical-probe.yml` | New: read-only diagnostic for retention depth and window enumeration. |
| `.github/workflows/ci.yml` | `mypy --strict` runs with no path argument so `[tool.mypy] files` is the single source of truth. |
| `pyproject.toml` | Puts the whole `scripts` directory in mypy's checked set, so a new script cannot escape it. |
| `docs/decisions.md` | Adds ADR-025 (Accepted): `ledger/` and `collisions/` on the data branch, extending ADR-020. |
| `docs/numerical-claims.md` | NC-012 gains its unit; NC-013 retired as NC-R002; NC-021 updated; NC-025..NC-030 added. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | This document. |
| `docs/evidence/pr47-outage-enumeration/` | Row-level enumeration data and its provenance, committed because Actions logs expire at ~90 days. |
| `tests/test_calibration.py` | `serialize_target` order-independence regression; two tests for the historical-response guard; one existing fixture corrected (see Design decisions). |
| `tests/test_probe_historical_properties.py` | New: the probe's verdict table, sweep stepping and dedup, retry behaviour, and `main`'s exit codes. |
| `tests/test_canonical_snapshot_digest.py` | New: reordering must not change the digest, a changed calibration value must, and an unreadable payload must be distinguishable from a differing one. |
| `scripts/__init__.py` | New: package marker so `scripts` resolves unambiguously and `[tool.mypy] files` can name the directory rather than each file — not shipped in the wheel. |
| `tests/calibration/test_loader.py` | Asserts the pre-cutover fixture reports all 156 qubits' `init_error` as absent rather than filled. |
| `tests/calibration/test_features_missing_fields.py` | Construction sites updated for the new required field. |

## Implementation approach

**Byte-stability (#46).** The root cause is that `Target.operation_names` and
`qargs_for_operation_name` have no guaranteed iteration order, and
`json.dumps(sort_keys=True)` in `storage.py` normalises *mapping* keys, not
*sequence* elements — so the one field assembled locally from an unordered
source slipped through a determinism guard that covers everything else. Sorting
the assembled list by `(name, qargs)` covers both loops at once and is stable
against future Qiskit changes to `operation_names` ordering. No workflow change
is needed for this: once the bytes are stable, the existing
`git diff --cached --quiet` guard starts working as written.

**Archive integrity (workflow).** Three independent defects in one step. The
destination month came from `date -u` (the run clock) while the filename comes
from the payload, which misfiled two June payloads under `2026-07/`; it now
derives from the payload-derived filename. `mv` overwrote archived paths
unconditionally, which is what discarded five gate-level versions; an existing
path is now left alone, restoring across the ephemeral-runner boundary the
`O_EXCL` intent that `storage.py` cannot enforce (its guard checks
`data/calibration/`, empty on every fresh runner, so it never consults the
branch). And the `echo 'No new snapshots'` branch discarded its own evidence, so
every gap was unattributable; a ledger row now records
`(poll_time, backend, observed last_update_date, decision)`.

**Backfill feasibility (#45 Phase 2).** `fetch_snapshot` catches
`NotImplementedError` and logs "historical access tier denied", but in
`qiskit-ibm-runtime==0.46.1` that exception cannot be raised. Reading the call
path — `IBMBackend.properties` → `RuntimeClient.backend_properties` →
`CloudBackend.properties` — `datetime` becomes an `updated_before` query
parameter and is sent; only the *docstrings* mention `NotImplementedError`. The
failure mode is therefore silent: if the service ignored the parameter it would
return the current document, the poller would store it under a timestamp it
already has, and a sweep would log "skipped (already archived)" at every step
while reporting green. The probe compares `last_update_date` values instead of
watching for an exception, which is the only way to distinguish "honoured" from
"ignored".

## Mathematical / Statistical details

### The 630 floor and the unit it counts

`docs/numerical-claims.md` NC-012 records the floor as ~126 trainable parameters
× 5, a samples-per-parameter rule of thumb. Such a heuristic counts
**independent** samples: a duplicated row adds nothing to the identifiability of
a parameter, because it contributes no new equation to the fit. With 894 files
carrying 504 distinct device states, the effective ratio is 504 / 126 ≈ **4.0
samples per parameter**, below the 5× the number was derived from. The gate is
not met.

### Polling sufficiency

Let λ be IBM's publish rate for a parameter family and μ the poll rate. Capture
is bounded above by min(1, μ/λ): polls beyond the publish rate return documents
already held. For the readout family (λ ≈ 1/4 h = 6 day⁻¹), μ < 6/day loses data
irrecoverably in real time, while μ > 8/day is almost pure duplication. This is
why the recommendation targets ~8 polls/day rather than restoring 24 — the
marginal value of polls 9 through 24 is approximately zero, and #45's
measurement bears this out: poll rate rose 2.7× and data rose 1.57×
(Pearson r = +0.393).

### Capture rate over the live outage

Over 2026-08-28T03:17 → 2026-08-29T14:06 (34.8 h) the poller captured 5
documents where 34.8 / 4.0 ≈ 9 were published at the median cadence — a capture
rate of 5/9 ≈ **57%**, i.e. roughly 5 readout publications lost. Two individual
gaps show the mechanism directly: a 15.19 h poll gap over which the readout
stamp advanced 15.66 h (≈3 publications never seen), and a 6.17 h gap over which
it advanced 11.67 h (≈2 never seen). The advance exceeding the gap is the
signature of publications occurring between polls.

Cadence is a **median, not a period** — the distribution is irregular (readout
p10 2.5 h, p90 9.2 h), so these are expectations, not counts. A 5.83 h gap on
2026-08-29 saw no advance at all.

### Correction, 2026-08-30: the polling-sufficiency estimate above is too generous

The section above derives a ~6/day floor and a ~8/day ceiling from the readout
family's ~4 h publish cadence. Once the probe proved historical reads work, that
model became testable against ground truth rather than assumption — and it does
not survive.

Enumerating 2026-08-27T08:18Z → 2026-08-30T08:18Z at a 1 h step
([run 33301248740](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33301248740),
73 queries, read-only; evidence in `docs/evidence/pr47-outage-enumeration/`):

| | |
| --- | ---: |
| distinct documents IBM served | 55 |
| documents on `calibration-data` in the window | 11 |
| held by us but **not** returned by the sweep | 2 |
| **documents proven to exist** | **≥ 57** |
| **capture rate** | **≤ 19.3%** |
| **recoverable today** | **46** |
| implied republication rate | ≥ 19 documents/day |
| implied mean interval | ≤ 1.26 h |

The 2 documents we hold that the sweep did not return prove the sweep
**undercounts**: a 1 h step cannot see a document superseded before the next query
lands. Aliasing does not explain all of it — a query at 22:18:47 should have
returned `22:12:34` as the newest document older than it and returned `22:04:50`
instead, so `updated_before` does not select purely on `last_update_date` and its
exact semantics are uncharacterised. The error is one-directional, which is what
makes the numbers usable: the true count is ≥ 57 and a finer step would find more,
never fewer.

**Why this does not contradict #45.** The two cadences measure different things.
#45's ~4 h is the readout *parameter family's* own `date` fields; ≤1.26 h is
*document* republication, and `last_update_date` advances whenever any part of the
document changes, gate-level data included. Both hold simultaneously.

**What it does revise.** "Above ~8 polls/day the extra polls are pure duplicates"
is false at the document level — at ≥19 republications/day, 8 polls/day still
misses most documents. The ~6/day figure survives only as a floor for catching
*readout* changes, not as a sufficiency criterion.

**What it does not establish.** These are document republications, not distinct
device states. #45 measured 43.6% of captured snapshots as byte-identical in their
qubit block to the previous one, so an unknown fraction of the 46 carries no new
qubit information — and #45's central result (2.7× polling → 1.57× data) was
measured in *states*, so the sublinearity of information yield is untouched.
Converting 46 documents into a count of new device states requires fetching them
and diffing the qubit blocks. That is the backfill, and it is the only way to know.

### Marginal information yield

Splitting the archive at the 485-file mark: the first half added 313 distinct
states over 485 files (64.5 per 100), the second 191 over 409 (46.7 per 100) — a
**28% fall** while the poll rate nearly doubled. Cost per unit of information
moved the wrong way, 2.29 → 2.58 MB per distinct state.

### `init_error`: why imputation was rejected

Let M be the missingness indicator and t\* = 2026-08-04T00:52:30. At snapshot
level P(M=1 | t) = 1 for t < t\* and 0 for t ≥ t\*. This is MAR in Rubin's sense
— missingness depends only on an observed variable — but MAR-based imputation is
identifiable only under **positivity**: 0 < P(M=1 | X) < 1. Here the propensity
is exactly 0 or 1, so there is no overlap region and P(init_error | t < t\*) is
**not identified** by this dataset. Imputation would be extrapolation under an
assumption the data cannot check across the boundary.

That assumption *is* checkable within the observed region by splitting on time.
Over 40 snapshots spanning 2026-08-04 → 08-24 (n = 4607 qubit-records), OLS of
`init_error` on the six co-observed fields gives:

| | R² |
| --- | ---: |
| in-sample, all six predictors | 0.139 |
| **out-of-sample, train 08-04→08-19, test 08-19→08-24** | **−0.585** |
| best single predictor (`readout_error`), in-sample | 0.128 |
| best single predictor, out-of-sample | −0.168 |

A **negative** out-of-sample R² means the fitted model predicts held-out data
worse than the held-out mean does. The relation does not survive 20 days forward
inside the same schema regime; extrapolating 25–110 days backwards *across* a
schema change is strictly harder than the test it already fails. Because the
imputation error would correlate perfectly with the schema boundary, it would
present as a spurious regime shift dated exactly to a schema change — the class
of artifact a drift model is built to detect.

Reproduce with `scripts/` equivalents of the two analyses recorded in the
session scratchpad, or re-derive: sample post-cutover snapshots, regress
`init_error` on `{prob_meas0_prep1, prob_meas1_prep0, readout_error,
readout_length, T1, T2}`, then refit on the earlier half and score on the later.
Note `readout_length` is constant in the sample, so it contributes nothing.

### `init_error` raggedness

#45 §6b established the cutover is clean at **snapshot** granularity ("225
snapshots, 0 missing the field"). That is a weaker claim than per-qubit
completeness, and the two come apart: 0 of 40 sampled post-cutover snapshots
carry `init_error` for all 156 qubits, and a fixed set of 40 qubits never
reports it (plus 1 intermittent). Verified end-to-end through the new loader
against the archive at `f0930b9`: 2026-05-13 parses 0 present / 156 absent,
2026-08-28 parses **116 present / 40 absent**.

Consequently "restrict training to August" would have cost ~82% of distinct
device states (≈93 of 504, derived from #45 §8's weekly cumulative table: 504 at
08-28 minus 411 at 08-04) *without* buying the field completeness that was its
only rationale.

## Design decisions

**The four #45 questions**, decided by the project owner across the 2026-08-29/30 session:

1. **The 630 floor counts distinct device states.** 504/630 — not met. Follows
   the rule of thumb's own logic, since samples-per-parameter counts independent
   samples. Rejected: snapshot files (894, but 43.6% duplicate qubit blocks);
   per-qubit coherence events (~94, unreachable this quarter since T1 publishes
   ~daily).
2. **The trainer keys rows on each parameter's own measurement `date`, with
   deduplication on the qubit block.** The only framing under which the row count
   means anything.
3. **The hour-of-day bias decision is deferred until the trainer exists**, and
   the deferral is recorded explicitly rather than left implicit. A static ANFIS
   mapping is unharmed by uneven spacing; only aggregate statistics are affected,
   so the correct treatment depends on whether the model is time-aware — which is
   not yet decided. The bias itself is measured and unchanged: 207 snapshots in
   00:00–07:00 UTC against 396 in 16:00–23:00 (1.9×; 4.1× at the extremes).
4. **`init_error` is represented and counted, not dropped, restricted, or
   imputed.** This is **ADR-017's Skip strategy applied to a new field**, not a new
   policy: that ADR (Accepted) already weighed Skip against Impute and rejected Impute
   for inventing data. What was genuinely open was whether `init_error` is different
   enough to warrant an exception, given it is absent from 75% of the archive rather
   than sporadically missing. The measurements below say no — imputation is not merely
   inelegant here, it is unidentifiable — so ADR-017 stands and this field joins it.

**The ledger commits on every poll, deliberately.** Because the ledger changes
each run, polls observing nothing still produce a commit. The cost falls from
~1.4 MB of rewritten snapshot to a ~60-byte append, and the commit message
distinguishes `calibration:` from `poll:` so the log stops claiming new data
where there is none. This reads #46's acceptance criterion as "no snapshot bytes
rewritten per publish window" rather than "one commit per publish window". The
alternative — commit only on new data — restores strict no-op behaviour but
leaves gaps unattributable once the ~90-day Actions run retention expires, which
is precisely what made #45 expensive to investigate.

**The probe uses a `push:` trigger on `probe/**`.** GitHub accepts a
`workflow_dispatch` only for a workflow already present on the default branch, so
the probe could not otherwise have been run before merge. The namespaced push
trigger also leaves it runnable by anyone without merge rights.

**`max_historical_days` stays at 30** even though the probe shows 60 works. A
conservative default should be raised deliberately per-run via the dispatch
input, not silently in code.

**Cron tuning was not attempted**, and the hypothesis is doubly falsified. The
`:05` → `:37` move landed 2026-05-17 and did not fix the rate. Independently, of
the last 40 runs **not one fired at `:37`** — observed minutes scatter across the
whole hour — so the scheduler is dispatching at an arbitrary delay and the minute
field is not the lever. The repository is public, so Actions minutes are free and
unlimited; billing is not the cause either.

## Verification

Environment note: the system Python is the broken Windows Store stub. A working
interpreter is
`C:\Users\senso\AppData\Local\Programs\Python\Python312\python.exe` (3.12.10);
the repo `.venv` is built on the broken 3.13 stub and does not run.

```bash
pytest tests/ -q          # count: see NC-021 in docs/numerical-claims.md
ruff check .              # All checks passed
ruff format --check .     # all files already formatted
mypy --strict             # no path argument: the set is [tool.mypy] files
```

Cite NC-021 for the test count rather than restating it here — a number copied
into prose is the drift Rule 6 exists to catch, and this document has already
been through one round of it.

The regression test is proven to catch the bug it guards, not merely to pass:
comment out the `out["operations"].sort(...)` line and
`tests/test_calibration.py::TestSerializeTarget::test_operations_order_independent`
fails, with the two payloads differing in `operations` order only.

Loader behaviour against real archived data — expect `0 156` for the May file
and `116 40` for the August one:

```bash
python -c "from superconducted.calibration.loader import load_snapshot; s=load_snapshot(PATH); print(sum(1 for q in s.qubits if q.init_error is not None), s.missingness.init_error.absent)"
```

Historical access, re-runnable at any time (Actions → Calibration Historical
Probe → Run workflow, or push any branch named `probe/**`):

```bash
gh workflow run calibration-historical-probe.yml --repo SuperconducTED/superconducted-noise-engine -f backend=ibm_fez -f days_back='1 7 30 60'
```

Workflow filing logic was simulated before deployment with a payload dated
2026-06-30 polled under a 2026-09-01 clock, plus a duplicate of an archived path:
the June payload filed under `snapshots/2026-06/`, the duplicate was preserved
unmodified, and both decisions appeared in the ledger.

## Results

**Historical access works.** Run
[33260786341](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33260786341),
2026-08-29, channel `ibm_quantum_platform`, plan `open`, instance
`open-instance`. Current stamp 2026-08-29T14:06:21Z.

| depth | requested | returned | lag behind request |
| ---: | --- | --- | ---: |
| 1 d | 2026-08-28T14:06:21Z | 2026-08-28T13:08:46Z | 0:57:35 |
| 3 d | 2026-08-26T14:06:21Z | 2026-08-26T13:42:53Z | 0:23:28 |
| 7 d | 2026-08-22T14:06:21Z | 2026-08-22T13:51:42Z | 0:14:39 |
| 14 d | 2026-08-15T14:06:21Z | 2026-08-14T20:18:59Z | 17:47:22 |
| 21 d | 2026-08-08T14:06:21Z | 2026-08-07T03:21:59Z | 1 d 10:44:22 |
| 28 d | 2026-08-01T14:06:21Z | 2026-08-01T13:50:00Z | 0:16:21 |
| 30 d | 2026-07-30T14:06:21Z | 2026-07-30T13:38:00Z | 0:28:21 |
| 35 d | 2026-07-25T14:06:21Z | 2026-07-25T13:36:06Z | 0:30:15 |
| 45 d | 2026-07-15T14:06:21Z | 2026-07-15T12:54:06Z | 1:12:15 |
| 60 d | 2026-06-30T14:06:21Z | 2026-06-30T06:52:21Z | 7:14:00 |

No depth was denied. The `NotImplementedError` in IBM's own API reference is
stale for this account and channel.

**The 14 d and 21 d rows independently re-confirm #45's corrected §5.** Their
returned stamps — 2026-08-14T20:18:59 and 2026-08-07T03:21:59 — are exactly the
opening boundaries of the dark windows #45 §4 reports (`2026-08-14T20:19` and
`2026-08-07T03:22`). Since `properties(datetime=T)` returns the closest document
*older than* T, a request landing inside a window returning a document from
before it proves IBM published nothing in between. The Aug 7–10 and Aug 14–17
gaps were the backend being idle, not the pipeline dropping data — now
established from IBM's own history, independently of the git-history argument
that first settled it. **There is nothing to backfill there.**

The recoverable loss is the scheduler outage from 2026-08-26 onward, where IBM
*was* publishing at ~4 h and the poller ran 2–3×/day.

## Related docs

- #45 — dataset yield analysis and the four decisions; #46 — `serialize_target` non-determinism
- **ADR-017** (`docs/decisions.md`, Accepted) — the Skip strategy this work applies to
  `init_error`. Its Decision already rejects Impute ("invents data and biases the aggregate
  toward the population") and mandates `Optional[float]` plus `FieldMissingness` counters,
  so the `init_error` treatment *follows* ADR-017 rather than deciding anything new; NC-028
  confirms the ADR's reasoning holds for this field specifically.
- **ADR-020** (`docs/decisions.md`, Accepted) — calibration snapshot schema and storage
- **ADR-025** (`docs/decisions.md`, Accepted) — `ledger/` and `collisions/` on the data
  branch; added by this work because ADR-020 fixes the layout and this extends it
- ADR-014 (`docs/decisions.md`) — TSK trainer, gated on the floor this work re-specifies
- `docs/numerical-claims.md` — NC-012 (the floor), NC-013 (superseded projection)
