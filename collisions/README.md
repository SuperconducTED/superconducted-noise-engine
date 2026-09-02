# collisions/

Per ADR-025 in the main repository, a file lands here when a freshly fetched
payload carries a stamp this branch already holds **and** its calibration
payload differs from the archived copy. The archived copy is never overwritten;
the divergent payload is preserved beside it as
`collisions/YYYY-MM/<backend>/<stamp>.<sha8>.json`.

**This tree is expected to be empty.** Anything in it is a signal worth
investigating, not routine churn.

## 2026-09-02 — seven files removed, all spurious

The first production backfill run wrote 7 files here, and every one was a false
positive. They are removed; the record of what happened is below and in the
`ledger/2026-09.tsv` rows dated `2026-09-02T19:26:58Z`, which still read
`collision` because that is genuinely what the workflow decided at the time.

```
20260817T174011000000Z   20260817T205744000000Z   20260818T012157000000Z
20260817T180058000000Z   20260817T224957000000Z   20260818T023034000000Z
20260817T193520000000Z
```

A backfill sweep necessarily re-reads stamps the archive already holds: a query
placed inside a gap is answered with the document at the gap's opening. A
historical fetch leaves `configuration` as `None` and sources `target` from
`target_history` rather than the live backend, so that re-read is **never**
byte-equal to the live copy that archived it — even when every measurement
matches. Compared whole-document, all 7 looked divergent. Compared on
`properties`, all 7 were byte-identical to their archived counterparts.

Nothing was lost. The archived copies were never touched, and the removed files
carried no measurement the archive did not already hold. They remain in this
branch's git history.

The comparison was fixed in the main repository so a re-read of this kind
records `duplicate-partial` instead, leaving this tree untouched. A payload
difference is still a `collision` — that is the case ADR-025 reserves this tree
for, and the five versions lost in issue #46 were gate-level data, which lives
inside `properties`.
