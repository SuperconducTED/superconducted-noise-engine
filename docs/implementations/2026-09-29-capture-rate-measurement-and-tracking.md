# 2026-09-29: capture-rate-measurement-and-tracking

## Problem / Motivation

Issue #54 (2026-09-02) argued that the pipeline loses calibration documents during ordinary
operation, not only during scheduler outages: an hourly sampler with arbitrary dispatch delay
misses documents IBM supersedes before the next poll. Its evidence, NC-032 `<= 70.2%`, became
vacuous on 2026-09-06 when #53 backfilled the very window it measured, and the fix it argued
for, #49's daily trailing-window sweep, shipped on 2026-09-10 (PR #90). The closure criterion
was written on #49 twice: **#54 closes when a post-sweep capture measurement replaces
NC-032.** Nothing measured the system as it now runs, and nothing would have noticed if its
capture degraded, because the ADR-025 ledger cannot see a document nobody fetched.

## What changed

Three commits on `mert/issue-54-capture-rate`, plus one dispatch that changed the data branch.

| File | One-sentence description |
| --- | --- |
| `docs/evidence/capture-rate-2026-09/README.md` | Method, runs and results of the 2026-09-13..20 measurement, the failed replay recorded as a negative result, and an as-of section after the backfill. |
| `docs/evidence/capture-rate-2026-09/enumeration-2026-09-13_20.tsv` | One row per document proven to exist in the window, with served/held/first-filer/status. |
| `docs/evidence/capture-rate-2026-09/sweep-grids.tsv` | The exact window each of the 18 daily sweeps queried, recovered from Actions logs that expire at about 90 days. |
| `docs/numerical-claims.md` | NC-056 to NC-060 added; NC-032 gains an as-of note naming NC-058 as its successor. |
| `scripts/capture_rate_analysis.py` | Reproduces NC-056 to NC-059 from a pinned `calibration-data` ref via `git show`. |
| `scripts/capture_record.py` | Owns `health/capture.tsv`: its format, the settled-day arithmetic, the rolling summary, and the `pending` / `record` verbs the workflow calls. |
| `scripts/probe_historical_properties.py` | `--served-out PATH`, written only when every query of an enumeration was honoured. |
| `scripts/pipeline_health.py` | Publishes `capture_7d` and the evidence behind it, and renders one line for it on `progress.svg`. |
| `scripts/push_with_retry.sh` | Header lists `health/capture.tsv` as the capture job's own tree. |
| `.github/workflows/calibration-health.yml` | New `capture` job before `render`; `render` needs it but never conditions on it. |
| `docs/decisions.md` | ADR-025 amendment, 2026-09-29: the capture record. |
| `tests/test_capture_rate_analysis.py`, `tests/test_capture_record.py` | Pin every definition the registered figures and the daily record depend on, and the workflow invariants. |
| `tests/test_probe_historical_properties.py` | `--served-out` is written for a clean sweep and never for an incomplete one. |
| `tests/test_pipeline_health.py`, `tests/fixtures/pipeline_health/expected/*` | Capture metrics and SVG line; the text-node helper fix (see Design decisions); golden artifacts regenerated. |
| `calibration-data` @ `41ebadc` | The 27 missed documents, recovered by run 36520763479. |

## Implementation approach

**Measure without healing.** The measurement used the historical probe's `enumerate_window`
mode, which has `contents: read` and commits nothing, so it could not recover the documents
it was counting. Two sequential runs of 337 queries at 15 min covered 2026-09-13T00Z..20T00Z,
sharing the boundary instant because the probe queries both endpoints. The window was chosen
so every stamp in it had been covered by two daily sweeps, and it avoids the
09-22T14:00..23T16:44 publication pause, which the ledger shows is IBM's (23 polls, one
document). The served stamps were diffed against the archive at `b70d7b4`, the evidence and
register rows were committed and pushed, and only then was the window backfilled.

**Attribute from the ledger without changing it.** The ledger has no mode column, and a new
column would touch ADR ledger semantics, which `docs/team.md` gates on the advisor. The path
is derived instead: one ledger row per `poll_time` is an hourly poll, more than one is a sweep
run (`file_snapshots.sh` writes one row per staged document under a single poll time).

**Track it daily.** The `capture` job repeats the measurement for one settled day per run,
records per document in `health/capture.tsv`, and `render` publishes the rolling figure. The
job reads the held set from `health/state-index.tsv` (1,507 of 1,507 archived documents at
`b70d7b4`), so it needs only the sparse `health/` checkout.

## Mathematical / Statistical details

Let `W` be a stamp window, `S` the stamps the probe served inside it, and `H` the stamps the
archive holds inside it.

- **Documents proven to exist**: `E = S ∪ H`. The true population is a superset of `E`,
  because a document living less than one probe step can escape the probe.
- **Capture**: `C = |H| / |E|`, an **upper** bound on true capture since `|E|` can only
  undercount. NC-058: `200 / 227 = 88.1%`.
- **Probe recall**: `r = |S ∩ H| / |H|`, recall against held documents, the only ground
  truth there is. NC-059: `200 / 200`.
- **Lifetime** of document `d_i` (stamps sorted): `L_i = t_{i+1} - t_i`. Every missed
  document had `L_i <= 0.75 h` (median 0.42 h) against a 0.71 h median for captured ones.
  A grid of step `Δ` and random phase sees a document with `L < Δ` with probability about
  `L / Δ`, which is why a 1 h sweep leaks sub-hour documents and a 15 min grid did not.
  This is an explanation of the mechanism, **not** a registered prediction; see the replay
  under Design decisions.
- **Hourly share** (NC-056): `h = |{d ∈ H_W : first(d) = hourly}| / |H_W|`, with `first(d)`
  the path of the first `new` ledger row for `d`. `214 / 436 = 49.1%`, or at most
  `229 / 436 = 52.5%` if the sweep run's own live fetch is counted as a poll.
- **New states and the sweep-only counterfactual** (NC-057): with `σ(d)` the qubit digest,
  `N = {s : min{t(d) : σ(d) = s} ∈ W}` and `R = N ∩ {σ(d) : first(d) = hourly}` over
  documents at **any** stamp; sweep-only is `|N \ R|`. `24 / 114 = 21.1%`.
- **State capture** (NC-060): `N` over the NC-058 window at `41ebadc`, and the states whose
  every carrier is one of the 27 formerly missed documents: `1 / 48`, so `<= 47/48 = 97.9%`.
- **Rolling capture** on the dashboard: over the settled span `K = {today-3, ..., today-9}`,
  `capture_7d = Σ_{k∈K} held_k / Σ_{k∈K} exist_k`, `None` when the denominator is 0, with
  `held` counting `captured` and `archived_not_served` and `exist` adding `MISSED`.
- **Settledness**: the sweep reads `[d - 48 h, d]` at dispatch time `d`, about 09:00-11:15
  UTC. The part of day `D` after that dispatch time is covered by the sweeps of `D+1` and
  `D+2`, so `D` is double-swept once `D+2`'s sweep has run; the health job runs on `D+3`,
  hence `today - 3`.

## Design decisions

Each of these was put to Mert as a question with the evidence in hand, and the answer is
recorded here with its reason.

- **Record, then backfill.** NC-032 became vacuous because the window it measured was
  healed before its value was pinned. This time the evidence and rows were pushed first
  (`aa61e5b`), the row names `b70d7b4`, and the backfill ran afterwards; the as-of section
  shows the same diff reading 227/227 at `41ebadc`, as predicted.
- **The sweep stays at 1 h (for now).** The measurement shows a 15 min grid sees what the
  1 h sweep misses, but the state-level cost is about one state a week (NC-060) and the
  change belongs to its own issue. It is recorded here, not made.
- **No finer-step prediction registered.** Replaying the 18 real 1 h grids against the
  ground truth did **not** reproduce the ledger (219 agree, 167 disagree): IBM's history
  index appears to lag publication by a variable amount (best constant fit 15 min, with
  near-equal fits one grid step apart). A model that fails its own validation cannot carry a
  registered number, so the 0.5 h and 0.25 h predictions it produced were discarded.
- **Enumeration tracking rather than a ledger metric.** A ledger-derived "hourly share" reads
  100% exactly when the sweep dies, the dangerous direction, and structurally cannot see a
  document nobody fetched. Only IBM's own history can.
- **Daily, one settled day, newest first, at most three per run.** A day newer than `today - 3`
  would count documents the next sweep will still recover as missed. Newest first keeps the
  figure current when a run's budget runs out; the cap keeps the job near six minutes.
- **15 min grid, pinned finer than the sweep.** At the sweep's own step the enumeration would
  share its blind spots and report near-full capture. `TestWorkflowPins` fails if the two
  steps ever meet, checked by mutation (setting the capture step to 1 h fails it).
- **Records, never recovers.** A job that healed what it measured would read 100% by
  construction. `MISSED` rows stay as recoverable pointers inside the 60-day retention.
- **Per-document rows, with a `no_documents` sentinel.** Missed stamps live in git rather
  than in Actions logs, and an empty day is recorded rather than re-enumerated forever.
- **Rendered exactly on the SVG, no band.** The graphic changed bytes on 19 of 19 renders from
  2026-09-10 to 09-28, so an exact figure adds no churn and needs no threshold, and so no new
  threshold claim. The span is anchored on the render instant like every other rolling window
  here, so a stopped capture job drains `capture_days_7d` instead of freezing a stale rate.
- **ADR-025 amendment without advisor sign-off**, on the 2026-09-17 amendment's reading (no
  existing row, column or vocabulary is redefined), and recorded as a question for the
  reviewer for the same reason that amendment gave.
- **Adjacent, flagged: vacuous SVG conformance tests.** `tests/test_pipeline_health.py`
  collected text with `Element.iter("{*}text")`. `iter` does not expand the `{*}` wildcard
  (only the `find` family does), so the traceability, canvas-escape and shipped-floors-fit
  tests had checked zero nodes; reproduced on an archive of `main` at 0 of 11. Fixed with the
  explicit namespace and a test that the helper sees every node. Run for real they pass on
  everything `main` renders, and they caught the new line's unlicensed numbers until the
  metrics carried them.

## Verification

```bash
# The registered figures, from pinned refs (fetch calibration-data first)
python scripts/capture_rate_analysis.py --ref b70d7b4 ledger --start 2026-09-11T00:00:00Z --end 2026-09-27T00:00:00Z
python scripts/capture_rate_analysis.py --ref b70d7b4 enumeration --start 2026-09-13T00:00:00Z --end 2026-09-20T00:00:00Z --probe-log runA.log runB.log
# runA.log / runB.log: gh run view 36483861337 --log > runA.log, and 36484678556 for B

# The same diff after the backfill reads 227/227, which is why NC-058 names b70d7b4
python scripts/capture_rate_analysis.py --ref 41ebadc enumeration --start 2026-09-13T00:00:00Z --end 2026-09-20T00:00:00Z --probe-log runA.log runB.log

# Gates, in a venv built from requirements.txt + requirements-dev.txt on Python 3.12
ruff check . && ruff format --check . && python scripts/check_ids.py && mypy --strict
python -m pytest tests/ -q      # 740 passed at 4ae436e
```

Still owed, and only possible after merge: the first scheduled `Calibration Pipeline Health`
run must show a `capture` job that records `today - 3` (plus up to two catch-up days), a
`health: record calibration capture` commit on `calibration-data`, and a `metrics.json`
whose `capture_days_7d` is non-zero. Its `capture_7d` should sit near NC-058, about 88%, while
the sweep stays at 1 h.

## Related docs

- Issue #54; #49 and PR #90 (the sweep); #53 (the backfill that made NC-032 vacuous);
  #48, PR #70 and PR #102 (the dashboard and its heartbeat)
- NC-026, NC-031, NC-032, NC-053, NC-056 to NC-060 in `docs/numerical-claims.md`
- ADR-025 and its amendments in `docs/decisions.md`
- `docs/evidence/capture-rate-2026-09/README.md`; `docs/evidence/aug-gap-enumeration/README.md`
- `docs/implementations/2026-09-17-dashboard-heartbeat-and-freshness-alarm.md`
