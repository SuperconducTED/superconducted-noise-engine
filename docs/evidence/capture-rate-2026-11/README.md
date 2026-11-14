# Issue #104: capture by document lifetime, 2026-09-30 to 2026-11-11

Laptop, provisional: run on the lead's laptop, not yet on Burak's desktop.

## What this folder answers

Issue #104 asks whether the daily sweep's 1 h step should be finer. The capture job has written one
row per document to `health/capture.tsv` on `calibration-data` since 2026-09-30, from a 0.25 h
enumeration of every settled day. `capture_lifetimes.py` reads that record and asks which of the
missed documents a finer sweep grid would always sample: a grid of step `s` lands inside every
document that IBM served for `s` or longer. The decision and its prediction are in
`docs/implementations/2026-11-15-issue-104-sweep-half-hour-step.md`.

## The run

The script was committed at `f40e3d27` with no output beside it; the output here comes from that
committed copy. Interpreter: Python 3.12.10 from the pins, run from the repository root.

```bash
PYTHONPATH=. python docs/evidence/capture-rate-2026-11/capture_lifetimes.py --ref d08263a97a7524f49f9fe2841584188aa408d443 > docs/evidence/capture-rate-2026-11/baseline-2026-09-30_11-11.out.txt
```

The anchor is `calibration-data` @ `d08263a9`, the branch tip on 2026-11-14; the record's blob there is
`7613927f` (SHA-256 in the output's first lines). Run it again at that commit and the output is the same.

## Results (`baseline-2026-09-30_11-11.out.txt`)

| Figure | Value |
| --- | --- |
| Recorded days | 42, 2026-09-30 to 2026-11-11; 2026-11-01 missing from the record |
| Documents IBM served or the archive holds | 1,684, each on one row |
| Capture | 75.5% (1,271 of 1,684); 413 missed |
| Capture by ISO week | 86.0% (first week, 5 days), 81.0%, 82.2%, 74.4%, 69.5% (6 days), 68.6%, 71.8% (3 days) |
| Lifetimes known | 1,682 (one successor falls on the missing day; the last document has none) |
| Missed documents that lived 1 h or more | 0 of 250 |
| Missed documents that lived 0.5 h or more (the P1 baseline) | 44 of 789 |
| Missed documents that lived 0.25 h or more | 247 of 1,326 |
| Missed lifetimes | median 0.286 h, longest 0.914 h |
| Capture runs recorded | 38 distinct run ids (a run catches up to three days) |

**What it says.** Every missed document lived under an hour, and none of the 250 that lived an hour or
more was missed: the 1 h grid's guarantee held throughout, so IBM's history index has not cost the
sweep a long-lived document in the live window over these six weeks. A 0.5 h grid would always sample
44 of the 413 misses and a 0.25 h grid 247; no step under discussion guarantees the 166 that lived under
0.25 h.

## Limits

- "Sample" is not "retrieve": the figures assume the history index returns at sweep time what it
  returned to the capture job days later. The 1 h result supports that assumption for documents living
  an hour or more; P1 tests it at 0.5 h.
- Capture is an upper bound, as for NC-058: a document living less than 0.25 h can escape the capture
  enumeration and the archive alike, and then appears nowhere in the record.
- Documents only, not device states: whether a missed document carried a new state needs its content,
  which the record does not hold (NC-060's method needs a backfill from IBM's history first).
- The weekly rate falls by about 3 points a week on its own, so it is reported and not used as a test.
