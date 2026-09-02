# 2026-09-02: aug-gap-enumeration

## Problem / Motivation

Issue #45's proposed-work checklist has one item left open: *"Reconcile the Aug 7-17
windows against IBM's backend status history to settle (a) vs (b) while it is still
recoverable."* Its §5 posed exactly two explanations for three multi-day windows in which
the poller ran repeatedly and created no new snapshot:

- **(a)** `ibm_fez` was paused or under maintenance and kept returning a stale properties
  document, so deduplication correctly suppressed everything; or
- **(b)** the poller received fresh documents and the pipeline failed to persist them.

The question could not be answered before now. `workflow_dispatch` on the historical probe
requires the workflow to exist on the default branch, which happened when PR #50 merged
today, and PR #50 also added the guard that makes a negative sweep result trustworthy: an
answer stamped newer than its request now fails the sweep instead of being silently
counted. Without that guard, a service ignoring the date filter would have reported a
clean "0 documents inside the window".

**The answer is neither (a) nor (b).** The device recalibrated 13 times inside the windows,
so it was not idle. The pipeline fetched and committed the same document 154 times, so it
dropped nothing. IBM's *publication* stalled while the machine kept running. That is a
third state the dichotomy did not contain, and it is why the windows hold nothing to
recover: the documents never existed to fetch.

## What changed

No source code changed. This work is measurement and its record.

| File | One-sentence description |
| --- | --- |
| `docs/evidence/aug-gap-enumeration/README.md` | New: the five sweeps, what each file shows, and an explicit list of what the evidence does *not* establish. |
| `docs/evidence/aug-gap-enumeration/control-2026-08-12_14.tsv` | New: one row per document known to exist in the control window, with whether the sweep served it and whether we hold it. |
| `docs/evidence/aug-gap-enumeration/calibration-rounds.tsv` | New: bulk calibration rounds recovered from per-parameter `date` fields in the gap-closing snapshots. |
| `docs/evidence/aug-gap-enumeration/live-path-stability.tsv` | New: per-window commit counts and the `properties`-block hash across every revision of each window's edge snapshot. |
| `docs/numerical-claims.md` | NC-031..NC-034 added; NC-029 gains a cross-reference to the measured recall that bounds it. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | Its Aug 7-17 status is corrected from "probably nothing to backfill; not yet enumerated" to the measured result, with the correction logged. |
| `docs/implementations/2026-09-02-aug-gap-enumeration.md` | This document. |

## Implementation approach

Three independent instruments, deliberately chosen so that no conclusion rests on one.

**1. Enumeration sweeps (the historical index).** `properties(datetime=T)` returns the
newest document older than `T`, so stepping through a window at a fixed interval
enumerates what the service will serve for it. Three sweeps covered the dark windows at a
1 h step; each returned no document stamped inside its window, with every query honoured.

That result alone is weak, and was treated as such. All three windows were drawn to start
1-25 s after an archived stamp and end 18-40 s before the next, so **by construction they
contain no document known to exist**. A completely broken sweep would produce identical
output. Two further runs fix that:

- **A positive control** over 2026-08-12T06:00..08-14T20:00, a stretch where the archive
  holds 33 documents. This measures the instrument's recall directly on the same backend
  at the same age.
- **A fine probe** at a 15-minute step across the interior of window 1, sitting on three
  bulk calibration rounds, to test whether a coarser grid had aliased something away.

**2. Per-parameter dates (the device).** Each entry in `properties.qubits[*][*]` and
`properties.gates[*].parameters[*]` carries its own measurement `date`. Because the
document is cumulative, the *first document after a gap* records when the measurements
inside that gap were taken. Clustering those timestamps recovers the calibration rounds
the backend ran while nothing was being published.

**3. Commit history of the data branch (the pipeline).** The poller's live call is
`backend.properties()` with **no** `datetime` argument (`poller.py`), so it never builds an
`updated_before` query parameter and shares none of the historical index's selection
behaviour. Every commit to `calibration-data` during a window is therefore an independent
record of what IBM's live endpoint served at that instant.

## Mathematical / Statistical details

**Recall of the sweep (NC-031).** Let `S` be the set of stamps the control sweep returned
inside its window and `H` the set the archive holds there. Recall is `|S ∩ H| / |H|` =
29/33 = **0.879**. The complement matters: 4 documents we provably hold were not returned,
so the instrument's error direction is *under*-reporting, which is precisely the wrong
direction for certifying a zero. This is why the three dark-window sweeps are reported as
corroboration rather than proof.

**Capture rate outside a known outage (NC-032).** `|S ∪ H|` = 47 documents are proven to
have existed in 62 hours; we hold 33. Capture ≤ 33/47 = **70.2%**, an upper bound because
`S` itself undercounts. The 14 documents in `S \ H` are absent from every month directory
on `calibration-data`. This is a normal-operation stretch, not an outage window, so it
generalises the concern NC-029 raised for the 2026-08-27..30 collapse.

**Calibration rounds inside the gaps (NC-033).** Sort all parameter `date` values in a
document; split wherever consecutive values differ by more than 20 minutes; keep clusters
of ≥ 300 parameters. Applied to the three gap-closing snapshots this yields 16 rounds, of
which **13 fall strictly inside the windows, totalling 9,807 parameter measurements**.

The threshold choices are not load-bearing, but the control is. Running the identical
procedure on five normal-period snapshots yields 25 rounds, and **25 of 25** are matched by
an archived document within [−5, +75] minutes — most to the second (a round at 16:27
against a document at 16:27:35; 20:18 against 20:18:59). So in normal operation a bulk
round is followed by a published document essentially immediately. Inside the gaps, no
in-window round has a document at all. The count is a **floor**: a cumulative document
keeps only the newest measurement per parameter, so any round fully overwritten by a later
one is invisible.

**Live-path document stability (NC-034).** For each window, take every commit to
`calibration-data` inside it and hash the `properties` block of that window's edge
snapshot at each revision, `sha256(json.dumps(properties, sort_keys=True))`. Across
69 + 30 + 55 = **154 revisions the result is exactly one hash per window** with
`last_update_date` frozen. Only `target` differs between revisions, which is the ordering
instability #46 fixed and the reason the file was rewritten at all.

Under (b) the poller would have received documents with advancing `last_update_date` and
failed to persist them. It instead received one document per window, repeatedly, at a mean
interval near the poll cadence. (b) is refuted.

## Design decisions

**Three instruments, not one, and they were required.** Eight independent adversarial
verifiers were run against the initial reading of the three sweeps, and **all eight
refused it**. Their decisive objection was the missing positive control, which is what
prompted the control and fine runs. Their second was that "0 returned" cannot certify a
zero from an instrument that provably undercounts. Both objections are answered by moving
the weight of the conclusion onto the live-path and calibration-round evidence, which do
not depend on the historical index at all.

**The (a)/(b) dichotomy is reported as incomplete rather than resolved in favour of one
side.** (a) bundles two states with opposite consequences — an idle backend (nothing to
recover) and a stale-serving endpoint (documents exist and backfill matters). The measured
state is a third: an active backend with stalled publication. Recording it as "(a)
confirmed" would preserve a false premise about the machine.

**Some of #45's own §4 statements are corrected here rather than repeated.** It reports
"snapshots: 0" for each window, which reads as though nothing was written; the poller made
155 commits and created zero new snapshot *filenames*. It attributes the suppression to
deduplication, but the August workflow did an unconditional `mv` with no comparison — the
`git diff --cached --quiet` guard suppressed the commit only when bytes were identical,
which #46 showed they were not. Its run counts (58/35/46) do not match the commit counts
measured here (70/30/55); the two count different things and neither should be cited as
the other.

**No backfill was run.** These three windows have nothing to recover. The 14 documents the
control surfaced *are* recoverable, and four unswept gaps on 2026-08-06 totalling 24.5 h
may hold more, but both are new scope rather than this checklist item. The
`max_historical_days` guard defaults to 30, which the 2026-08-06 material crosses on
2026-09-05; the hard limit is the ≥60-day retention of NC-026, on 2026-10-05.

**Coverage was computed, not assumed.** Every archive gap over 3 h in 2026-08-06..18 was
differenced against the four sweep windows. Two gaps initially believed unswept — 6.4 h at
08-13T14:11:42 and 3.2 h at 08-14T03:36:55 — turned out to sit **inside the control
window** at 100% coverage; the first is empty and the second holds one recoverable
document. Only the four 2026-08-06 gaps remain unenumerated. This is recorded because the
earlier claim was repeated from an analysis rather than derived, and it was wrong.

**The sweep's own reporting gaps are recorded, not fixed here.** `_enumerate_window` prints
only in-window stamps, so the two out-of-window documents each dark-window run returned
were computed and discarded; under strict semantics a silent window should yield exactly
one. Its loop also stops one step short of the requested end. Both are noted in the
evidence README as open items so the next change to that script has the reasons in hand.

## Verification

Re-run any sweep (read-only, one API call per step, commits nothing):

```bash
gh workflow run calibration-historical-probe.yml --repo SuperconducTED/superconducted-noise-engine -f enumerate_window='2026-08-12T06:00:00Z 2026-08-14T20:00:00Z 1'
```

Expected differentially rather than absolutely: the control window must return **more**
in-window documents than the archive holds for it, and the three dark windows must return
**none**. Exact figures are in the evidence README and NC-031..NC-034.

The two archive analyses need only a fetched `calibration-data`; they read through
`git show` and check out nothing. The live-path result is the cheapest to confirm:

```bash
git log --format=%H --since=2026-08-07T03:22:00Z --until=2026-08-10T14:02:00Z superconducted-noise-engine/calibration-data | wc -l
```

Expect 70 commits, and every revision of
`snapshots/2026-08/ibm_fez/20260807T032159000000Z.json` across them to carry
`properties.last_update_date == 2026-08-07T03:21:59+00:00`.

Repository gates are unaffected — this change adds documentation and data only, no Python:

```bash
pytest tests/ -q          # count: NC-021
ruff check .              # All checks passed
ruff format --check .     # count moves by the files added here under ruff >= 0.16 only
mypy --strict             # no issues
```

Local runs are provisional; the authoritative run is on the designated desktop.

## Related docs

- #45 — the dataset-yield issue whose checklist item this closes; its §4 and §5 are the
  subject, and three of its statements are corrected above
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` — carried the
  "not yet enumerated" status this replaces; corrected in the same commit
- `docs/evidence/aug-gap-enumeration/` — the row-level data behind every figure here
- `docs/evidence/pr47-outage-enumeration/` — the 2026-08-27..30 enumeration, whose method
  this reuses and whose undercount NC-031 now quantifies
- ADR-025 (`docs/decisions.md`) — the ledger that would have made this reconstruction
  unnecessary had it existed in August; `calibration-data` carries no `ledger/` for that month
- `docs/numerical-claims.md` — NC-021, NC-029, NC-030, NC-031..NC-034
