# Evidence: calibration capture rate after the daily sweep (#54)

Measured 2026-09-28 against `calibration-data` @ `b70d7b4`. Issue #54 asked what share of
the documents IBM publishes the pipeline captures during ordinary operation. NC-032 answered
it once, at `<= 70.2%` for 2026-08-12..14, before the #53 backfill healed that very window and
made the row vacuous. Since 2026-09-11 the pipeline has two acquisition paths, the hourly
poll and the daily sweep of #49 (PR #90), so this directory answers the question for the
system as it now runs.

Committed as files rather than left in Actions logs, which expire at about 90 days.

## The two read-only enumerations

Both ran through the Calibration Historical Probe workflow (`enumerate_window` mode,
`contents: read`, commits nothing) on backend `ibm_fez`, sequentially, from `main` @
`110cfad`. Every query in both runs was honoured; none was malformed or unusable.

| Run | Window (UTC, closed) | Step | Queries | Inside window | Probe step | Actions run |
| --- | --- | ---: | ---: | ---: | --- | --- |
| A | 2026-09-13T00:00 .. 09-16T12:00 | 15 min | 337 | 127 | 6 min 28 s | [36483861337](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/36483861337) |
| B | 2026-09-16T12:00 .. 09-20T00:00 | 15 min | 337 | 100 | 5 min 37 s | [36484678556](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/36484678556) |

The two windows share the boundary instant 09-16T12:00, and `_enumerate_window` queries both
endpoints, so the halves tile without a seam.

The window was chosen so that every stamp in it had been covered by **two** daily sweeps
before the measurement (the trailing window is 48 h and the sweep fires daily), so what is
missing is what the system as designed does not capture, not what a sweep had yet to reach.
It also avoids the 09-22T14:00 .. 09-23T16:44 pause, which is IBM's: 23 hourly polls inside
it all received the same document, `20260922T140030`.

## `enumeration-2026-09-13_20.tsv`: the per-document diff

One row per document proven to exist in the window, meaning served by the probe or held in
the archive. Produced by:

```bash
python scripts/capture_rate_analysis.py --ref b70d7b4 enumeration \
  --start 2026-09-13T00:00:00Z --end 2026-09-20T00:00:00Z \
  --probe-log <run A log> <run B log> --tsv enumeration-2026-09-13_20.tsv
```

where each log is `gh run view <run id> --log`, saved to a file.

| status | rows | meaning |
| --- | ---: | --- |
| `captured` | 200 | we hold it, and the probe served it |
| `MISSED` | **27** | the probe served it, and no path on `calibration-data` holds it |
| `archived_not_served` | 0 | we hold it, and the probe did not serve it |

`first_filed_by` records which path filed each held document first (`hourly` or `sweep`, as
defined in the script's docstring): 104 hourly, 96 sweep.

- **Capture `<= 200/227 = 88.1%`** (NC-058). An upper bound: the probe's 15-minute grid can
  itself miss a document that lives less than 15 minutes, so 227 is a floor on what existed.
- **Probe recall 200/200 = 100%** (NC-059). The 15-minute grid served every document the
  archive holds for the window. Run C's 1 h grid served 87.9% (NC-031).

The 27 were checked three ways at `b70d7b4` before being called missed: no path anywhere on
the branch carries the stamp (every month directory and `collisions/`), and no ledger row
names it, so no poll or sweep ever saw them.

### Why they were missed: sub-hour lifetimes

A document's lifetime here is the time until the next document's stamp, available for the 226
documents that have a successor inside the window.

| | n | min | median | max | under 30 min | 30-60 min | 1 h or more |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `MISSED` | 27 | 0.08 h | 0.42 h | 0.75 h | 20 | 7 | 0 |
| `captured` | 199 | 0.04 h | 0.71 h | 1.84 h | 61 | 81 | 57 |

Every missed document was superseded within 45 minutes. Missed documents fall on every day of
the window (3, 3, 9, 4, 2, 3, 3 for 09-13 .. 09-19), which is a steady leak and not an
incident. That is the aliasing #54 described, now shown to survive the sweep: a sweep that
queries once an hour cannot reliably see a document that lives for twenty minutes.

## `sweep-grids.tsv`: what each daily sweep actually queried

The 18 scheduled sweeps from 2026-09-11 to 2026-09-28, each with the exact `HIST_START` and
`HIST_END` its log printed (`Backfill sweep: <start> .. <end> every 1h`). Each ledger
`poll_time_utc` is matched to the closest earlier run of `calibration-poll.yml`, 1.8 to 2.5
minutes before it. The sweep fired on all 18 days, 23.27 h to 25.02 h apart, 4.2 h to 6.6 h
after its `41 4 * * *` cron.

## A negative result: the sweep cannot yet be replayed

Before registering anything about a finer sweep step, the 1 h sweeps were replayed against
the enumeration's ground truth: a query at `T` returns the document alive at `T`, and each
replayed sweep was compared with the documents the ledger records it returning. **The replay
does not reproduce the ledger** (219 agree, 167 disagree across the 9 sweeps overlapping the
window). The disagreements are almost all the sweep returning the document *before* the one
the replay expects, which is the signature of a publication lag in IBM's history index, the
same effect #49 recorded as "`updated_before` does not select purely on `last_update_date`".
A constant lag fits best at 15 minutes but still leaves 40 disagreements, and near-equal fits
at 75 and 135 minutes (one grid step apart) show the fit cannot identify it.

So no prediction of what a 0.5 h or 0.25 h sweep would capture is registered. What stands
without a model is that the 15-minute probe, a single pass, served all 200 held documents and
all 27 missed ones.

## What these files do not show

- Nothing about device *states*. The 27 are not held, so their qubit-block digests are
  unknown until they are recovered, and until then there is no way to say whether any carries
  a state the archive lacks. NC-057 measures the state-level effect of the sweep itself.
- Nothing about a quiet period. This is ordinary operation at about 32 documents a day.
