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

## 2026-09-06 — one file removed, spurious

The backfill sweep of issue #53 §1 (window `2026-08-12T06:00Z..2026-08-14T20:00Z`,
step 0.5 h, Actions run 34058863047) recorded 18 new / 33 duplicate-partial /
1 collision. The collision was a false positive and its file is removed:

```
20260813T220506000000Z.d6f9532e37a0da84.json
```

The ledger row `2026-09-06T20:46:55Z ibm_fez 20260813T220506000000Z collision`
still reads `collision` and is left alone, on the same reasoning as the
2026-09-02 rows above: that is genuinely what the workflow decided at the time,
and the ledger records observations rather than conclusions.

This one is a different defect from the seven above, and survived their fix.
The structural guard added after 2026-09-02 worked — the incoming payload was
correctly recognised as a lossy historical re-read — but the payload
comparison it gates normalised nothing inside `properties`. Both copies carry
the same `last_update_date` (`2026-08-13T22:05:06+00:00`), the same 156 qubit /
1952 gate / 449 general shape, and byte-identical `qubits` and `general`
blocks. Twenty-six of the 1952 gate entries differ, and in every one the values
are identical (`gate_error = 1`, `gate_length = 24`); only the per-parameter
`date` moved, by about 11 minutes — `22:14:31` from the historical fetch
against `22:25:32` from the live poll that archived the copy we hold.

Those 26 entries are **exactly** the 26 carrying the `gate_error = 1`
placeholder that means "not calibrated". No entry holding a real measurement
differed. The live properties endpoint returns IBM's stored document; the
history endpoint reassembles one and re-stamps the entries it synthesises. That
stamp is provenance — it records which endpoint answered, not when anything was
measured — so hashing it made a re-read of a document this branch already holds
look like divergence.

Nothing was lost. The archived copy was never touched, the removed file carried
no measurement the archive did not already hold, and it remains in this
branch's git history.

The comparison is fixed in the main repository (issue #53): the payload digest
now drops each parameter's own `date` before hashing, so a re-read of this kind
records `duplicate-partial` and leaves this tree untouched. The normalisation
is confined to that cross-fetch-path comparison — `last_update_date` still
counts, a changed value or unit is still a `collision`, and two live payloads
are still compared in full.
