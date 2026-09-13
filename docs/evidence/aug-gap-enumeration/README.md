# Evidence — what the 2026-08-07..17 polling gaps actually were

Five read-only enumeration sweeps run 2026-09-02, plus two analyses of the archive's own
payloads. Together they settle the question #45's proposed-work checklist left open:
*"Reconcile the Aug 7-17 windows … to settle (a) vs (b)."*

**Answer: neither (a) nor (b) as posed.** The device was recalibrating throughout the
gaps, so it was not idle. Our pipeline received and committed the same document
throughout, so it dropped nothing. What stopped was IBM's *publication* of new properties
documents — a third state the (a)/(b) dichotomy did not contain. Nothing in these three
windows is recoverable, because the documents never existed to fetch.

Committed as files rather than left in Actions logs, which expire at ~90 days.

## The sweeps

All five ran through the Calibration Historical Probe workflow on backend `ibm_fez`,
channel `ibm_quantum_platform`. Every query in every run was honoured — no answer came
back newer than the instant requested, and none was malformed.

| # | Window (UTC) | Step | Queries | Distinct docs | Inside window | Actions run |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 2026-08-07T03:22 .. 08-10T14:02 | 1 h | 83 | 2 | **0** | [33666244026](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33666244026) |
| 2 | 2026-08-10T14:03 .. 08-12T05:59 | 1 h | 40 | 2 | **0** | [33666576364](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33666576364) |
| 3 | 2026-08-14T20:19 .. 08-17T06:57 | 1 h | 59 | 2 | **0** | [33666752223](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33666752223) |
| C | 2026-08-12T06:00 .. 08-14T20:00 | 1 h | 63 | 45 | 43 | [33669739561](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33669739561) |
| F | 2026-08-09T15:39 .. 08-09T23:30 | 15 min | 32 | 1 | **0** | [33670030401](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33670030401) |

Runs 1-3 are the three dark windows. **Run C is the positive control** and is what makes
the others readable: without it, a sweep that always returned a stale document would have
produced byte-identical output to runs 1-3. Run F re-probes the interior of window 1 at
four times the resolution, sitting directly on three bulk calibration rounds.

## `control-2026-08-12_14.tsv` — the instrument's recall

Run C swept a stretch where the archive holds documents, so the sweep's output can be
differenced against ground truth. One row per document known to exist.

| status | rows | meaning |
| --- | ---: | --- |
| `captured` | 29 | we hold it, and the sweep returned it |
| `MISSED` | **14** | the sweep returned it, we never polled it — **recoverable today** |
| `archived_not_served` | 4 | we hold it, the sweep did not return it |

Two figures come out of this, and they point in opposite directions:

- **Recall 29/33 = 87.9%** (NC-031). The sweep returns most but not all of what exists.
  So "0 returned" is an upper bound on what the sweep can *see*, not a proof of absence.
  This is why runs 1-3 alone were not treated as conclusive.
- **Capture ≤ 33/47 = 70.2%** (NC-032). At least 47 documents existed in a 62-hour
  stretch that nobody had flagged as a problem. We hold 33. The 14 in `MISSED` are absent
  from the entire `calibration-data` branch, checked across every month directory.

The 14 are spread across **13 distinct archive gaps of 1.1 h to 3.2 h**, at most two to a
gap. That distribution matters: it is the signature of ordinary polling missing
short-lived documents, not of a single outage. Twelve of the 13 gaps are shorter than the
82-hour dark windows by two orders of magnitude and were never flagged as anomalies.

The 4 `archived_not_served` rows are the same phenomenon `pr47-outage-enumeration`
recorded: a 1 h step cannot see a document superseded before the next query lands, and
`updated_before` does not select purely on `last_update_date`.

## `calibration-rounds.tsv` — the device was not idle

Every parameter in a properties document carries its own measurement `date`. Clustering
those (gap > 20 min, keeping rounds of ≥ 300 parameters) recovers the bulk calibration
rounds the backend actually ran, including rounds that happened *before* the document was
published.

Applied to the three gap-closing snapshots: **13 rounds fall strictly inside the three
windows, totalling 9,807 parameter measurements** (NC-033).

The control that makes this binding is in the same file's method: on five normal-period
snapshots, **25 of 25** comparable rounds are matched by an archived document within 75
minutes, usually to the second. In normal operation a calibration round is followed by a
published document almost immediately. Inside the gaps, 12 of the 13 rounds have no
document within 75 minutes and none has one inside the window at all.

## `live-path-stability.tsv` — the pipeline dropped nothing

The poller's live call is `backend.properties()` with no `datetime`, so it never builds an
`updated_before` query and shares none of the historical index's selection behaviour. It
is therefore an independent witness.

| window | commits in window | edge-file revisions | distinct `properties` hashes | distinct `last_update_date` |
| --- | ---: | ---: | ---: | ---: |
| 1 | 70 | 69 | **1** | **1** |
| 2 | 30 | 30 | **1** | **1** |
| 3 | 55 | 55 | **1** | **1** |

154 revisions of the edge snapshot across the three windows, each hashing to exactly one
`properties` block per window with a frozen `last_update_date` (NC-034). Every live poll
during the gaps fetched the identical document. Explanation (b) — fresh documents received
and lost — is refuted by first-party evidence, not merely unsupported. Only `target`
churned between those commits, which is the ordering defect #46 fixed.

## How to reproduce

```bash
gh workflow run calibration-historical-probe.yml \
  --repo SuperconducTED/superconducted-noise-engine \
  -f enumerate_window='2026-08-12T06:00:00Z 2026-08-14T20:00:00Z 1'
```

The archive analyses read `calibration-data` through `git show` and need no checkout of
the branch. Method and code are described in
`docs/implementations/2026-09-02-aug-gap-enumeration.md`.

## What this does not establish

- **Not "IBM published nothing", as a proof.** The sweep undercounts by a measured 12%
  (NC-031), so its error direction is wrong for certifying a zero. The conclusion rests on
  the *combination* of the sweep, the frozen live-path document, and the calibration
  rounds — no one of them alone.
- **Not the whole of Aug 6-18.** Differencing every archive gap over 3 h in that span
  against the four sweep windows leaves **four gaps, all on 2026-08-06, totalling 24.5 h**,
  unswept: 00:26:59 (+3.1 h), 03:30:34 (+3.6 h), 07:05:02 (+3.0 h) and 12:29:47 (+14.9 h),
  the last running up to window 1's opening snapshot. Nothing later than 2026-08-06T12:29
  is unenumerated in this span.

  The 6.4 h gap at 08-13T14:11:42 and the 3.2 h gap at 08-14T03:36:55 **were** swept, at
  100% coverage, by run C. The first came back empty; the second holds one of the 14
  recoverable documents.
- **The final minutes of each window.** The sweep's loop stops one step short of the
  requested end (`while t <= end`), so the last 40m35s, 56m18s and 38m40s before each
  closing snapshot were never queried. Intersecting the poller's own last unchanged-document
  observations leaves roughly 1 h 25 m of stamp-time across the three windows covered by
  neither channel, sitting exactly where a backend resuming publication would burst.
- **The two out-of-window documents per run.** `_enumerate_window` prints only in-window
  stamps, so their identities were computed and discarded. Under strict "newest older than
  T" semantics a silent window should yield exactly one distinct answer; runs 1-3 each
  returned two. Run F, at a finer step, returned one. The anomaly is unexplained and the
  script should print all of `seen`.
