# PR #47 evidence — what the scheduler outage actually cost

`enumeration-2026-08-30.tsv` is the ground truth for the 72-hour window
**2026-08-27T08:18:47Z → 2026-08-30T08:18:47Z**, measured 2026-08-30.

It exists as a committed file rather than only as an Actions log because those
logs expire at ~90 days, and this is the measurement the backfill decision rests on.

## What it is

One row per calibration document known to exist in that window, with whether IBM
served it and whether we hold it.

| status | rows | meaning |
| --- | ---: | --- |
| `captured` | 9 | IBM serves it, and it is on `calibration-data`. |
| `MISSED` | **46** | IBM serves it, we never polled it. **Recoverable today.** |
| `archived_not_served` | 2 | We hold it, but the 1 h sweep did not return it — see the caveat below. |

**≥57 documents existed; we hold 11. Capture rate ≤ 19.3%.**

## How it was produced

Served side — the probe walks the window and records every distinct
`last_update_date` the service returns:

Run [33301248740](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33301248740)
(73 queries, 1 h step) produced it. That run came from the **push trigger**, which
enumerates the trailing 72 h automatically — `workflow_dispatch` only accepts workflows
already on the default branch, so the dispatch form was not available before merge.

Once merged, the equivalent explicit form is:

```bash
gh workflow run calibration-historical-probe.yml \
  --repo SuperconducTED/superconducted-noise-engine \
  -f enumerate_window='2026-08-27T08:18:47Z 2026-08-30T08:18:47Z 1'
```

Both paths run the same `validate_window` and the same script. Read-only; neither writes.

Archive side — the filenames on the data branch, which are the payload's own
`last_update_date`:

```bash
git ls-tree -r --name-only origin/calibration-data snapshots/2026-08/ibm_fez/ \
  | sed 's|.*/||; s|\.json$||' \
  | awk '$0 >= "20260827T081847000000Z" && $0 <= "20260830T081847000000Z"'
```

## Caveat: 57 is a lower bound, not a census

Two documents we hold — `20260827T221234Z` and `20260828T182857Z` — were **not**
returned by the sweep. A 1 h step cannot see a document that is superseded before
the next query lands, so aliasing explains part of it. It does not explain all of
it: a query at 22:18:47 should have returned `22:12:34` as the newest document
older than it, and returned `22:04:50` instead. So `updated_before` does not
select purely on `last_update_date`, and the exact semantics are uncharacterised.

The consequence is one-directional and safe: the sweep **undercounts**. The true
document count is ≥ 57, capture is ≤ 19.3%, and ≥ 46 documents are recoverable.
A finer step would find more, never fewer.

## What this does not say

These are **document** republications (`last_update_date`), not distinct device
states. #45 established that 43.6% of captured snapshots are byte-identical in
their qubit block to the previous one, so an unknown fraction of the 46 carries no
new qubit information. Backfilling them and diffing the qubit blocks is what turns
this document count into an information count — and that is the only way to know.
