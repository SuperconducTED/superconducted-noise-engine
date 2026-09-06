# 2026-09-06: issue-53-deadline-and-recovery

## Problem / Motivation

Issue #53 §3 published a deadline table whose first row read
`2026-08-06 gaps | 30-day guard bites 2026-09-05`. That date passed before the
recovery ran, which raised the question this work answers: **was anything lost?**

No. 2026-09-05 is when the poller's *default* `max_historical_days=30` begins
rejecting the 2026-08-06 material. That guard is soft and uncapped — #53 itself
prescribes `max_historical_days=60` — so the binding deadline was never
2026-09-05 but retention, which NC-026 verified at **≥ 60 days** and which does
not reach the 2026-08-06 material until 2026-10-05.

The real defect was not the date. It was **drift**: PR #55 unblocked this
recovery on 2026-09-02 and no `workflow_dispatch` ran against the poller in the
four days since, while the whole recovery sat one dispatch away from done.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/implementations/2026-09-06-issue-53-deadline-and-recovery.md` | This record — the only file this change adds to the code repository. |

No source, workflow, or test file was modified. #53 is a DevOps ticket ("two
`workflow_dispatch` runs, no new Python") and that scope held. The substantive
change landed on the `calibration-data` branch, which the poll workflow writes
via `scripts/file_snapshots.sh`:

| `calibration-data` | Change |
| --- | --- |
| `snapshots/2026-08/ibm_fez/` | 277 → **304** documents (+27), at `bfeaab9` → `7139138`. |
| `ledger/2026-09.tsv` | 28 `new`, 38 `duplicate-partial`, 3 `duplicate`, 1 `collision` appended across four runs. |
| `collisions/2026-08/ibm_fez/` | One file written, `20260813T220506000000Z.d6f9532e37a0da84.json`. It is spurious — see Design decisions. |

## Implementation approach

Four dispatches in two phases, each measured against a **differential** baseline
captured before anything ran (`calibration-data` @ `bfeaab9`: 946 snapshots
total, 277 under `snapshots/2026-08/ibm_fez/`, `collisions/` holding only its
`README.md`).

Absolute expectations were deliberately avoided. The `snapshots/` total is a
moving target — the scheduled poll writes to `2026-09/` throughout — so every
expectation below is stated over `snapshots/2026-08/ibm_fez/`, a directory the
scheduled poll cannot touch and which therefore changes only under backfill.

**Phase 1 — recover the 14, and enumerate 2026-08-06.** Run
[34058863047](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/34058863047)
swept `2026-08-12T06:00Z .. 2026-08-14T20:00Z` at `0.5` h with
`max_historical_days=60`. Run
[34058879214](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/34058879214)
enumerated `2026-08-06T00:00Z .. 2026-08-07T03:21Z` at `0.5` h, read-only.

**Phase 2 — act on what the enumeration returned.** Run
[34059354135](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/34059354135)
backfilled `2026-08-06T00:00Z .. 2026-08-06T12:30Z`, and run
[34059504421](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/34059504421)
swept `11:30Z .. 13:30Z` to close a one-document shortfall the first sweep left.

## Mathematical / Statistical details

**The guard predicate.** `src/superconducted/calibration/poller.py:361` rejects a
historical window up-front, before any API call, if *any* requested instant is
too old. Over a window `W`:

```
reject  <=>  there exists t in W such that (now - t) > max_historical_days
```

The quantifier is existential over the whole window, so the **oldest** instant
binds, and one out-of-range step fails the entire run rather than degrading it.
Measured at 2026-09-06T20:39Z:

| window start | age | vs. default 30 | vs. 60 |
| --- | ---: | --- | --- |
| `2026-08-06T00:00Z` | 31 d 20 h | rejected | accepted |
| `2026-08-12T06:00Z` | 25 d 14 h | accepted | accepted |
| `2026-08-14T20:00Z` | 23 d 0 h | accepted | accepted |

So on 2026-09-06 the *only* material the default would refuse is the 2026-08-06
set, and `max_historical_days=60` — uncapped in both `calibration-poll.yml` and
the `--max-historical-days` CLI argument — clears it with 28 days of verified
retention still in hand.

**Recall is not monotone in the query instant.** The historical endpoint does not
reliably answer a query at time *q* with the newest document at or before *q*.
In run 34059354135 the query at `12:00` returned the document stamped `11:11:50`,
silently passing over `11:48:21`, which exists and is older than the request. The
enumeration, whose window extended past noon, asked at `12:30` and was served
`11:48:21`.

This is the mechanism behind NC-031's 87.9% recall figure, and it has a practical
consequence: **the sweep interval is half-open**. A window `[start, end)` at step
*h* issues queries at `start + k*h` for `k = 0 .. ceil((end-start)/h) - 1` and
never asks at `end`. Any document recoverable only by a query at or beyond `end`
is missed. That is precisely what cost `20260806T114821000000Z` in the first
2026-08-06 sweep, and why the corrective sweep extended the end to `13:30`.

**Yield against prediction.** #53 predicted "at least 14 new snapshot files; more
is the good outcome, fewer means something regressed." Observed **+27**, of which
the 14 named documents and the 9 newly enumerated ones account for 23; the
remaining 4 were returned by the 0.5 h grid and appear in no enumeration.

## Design decisions

**Overriding the guard rather than treating 2026-09-05 as a loss.** The
alternative reading — that the passed date meant the 2026-08-06 material was gone
— was checked and rejected against the code, not against the issue text. Nothing
in `poller.py` or `calibration-poll.yml` caps `max_historical_days`.

**Enumerating 2026-08-06 before backfilling it.** #53 §2 asks for this because
the 14.87 h gap might be a publication stall rather than lost data. The
enumeration settled it: 55 queries, **55 honoured, 0 unusable**, 14 distinct
documents inside the window — and *nothing served after* `12:29:47`. The 14.87 h
gap contains no documents to recover; it is a publication stall, and the three
shorter gaps hold the recoverable material. Of the 14 served, 5 were already held
(the gap-boundary documents) and 9 were not.

**Ending the 2026-08-06 sweep at 12:30 rather than 08-07T03:21.** Sweeping the
stalled 14.87 h would have issued ~30 further queries, every one answered with
the `12:29:47` document already held, producing only `duplicate-partial` ledger
rows and further exposure to the false-collision defect below. The enumeration
had already proved the region empty.

**The collision was investigated, not accepted.** #53's acceptance criteria state
that a collision "would mean the canonical comparison is wrong, not that IBM
republished". That is exactly what it turned out to mean, and the criterion
earned its place. Reproduced locally on the two committed copies:

- `is_lossy_reread(new, archived)` → **True**; PR #55's structural guard works.
- `_payload_digest(new) != _payload_digest(archived)` → this arm refused.
- `properties.qubits` and `properties.general` are **exactly equal**; 156 qubits,
  1952 gates, 449 general on both sides; same `last_update_date`
  (`2026-08-13T22:05:06+00:00`).
- `properties.gates` differs in **26 entries across qubits 27, 28, 32, 33, 71,
  72, 73, 95, 99, 102, 103, 115** — and in every one the `value` fields are
  identical (`gate_error=1`, `gate_length=24`). Only the per-parameter `date`
  differs, by about 11 minutes (`22:14:31` historical vs `22:25:32` live).
- Strip the per-parameter `date` fields and the two `gates` multisets are equal.

So the payload comparison is sensitive to a provenance-dependent field. This is
the same family of defect PR #55 fixed one level up: `canonical_digest` already
normalises `target.operations` ordering for this very reason, while
`_payload_digest` normalises nothing. **Not fixed here** — #53's scope is two
dispatches and no new Python, and a change to the duplicate-vs-collision decision
needs its own tests and its own review. Filed as follow-up work.

**No new NC row was added.** #53's acceptance criteria ask for NC-032's capture
figure to be recomputed. NC-032 does not exist on `main`; it is on PR #52, still
open, which also carries `docs/evidence/aug-gap-enumeration/` and NC-031 — so
#53's stated dependency ("Depends on #52 for the evidence") is unsatisfied on
`main` today. Worse, **three open PRs each define NC-031 and NC-032 as different
claims**: #52 (enumeration recall / capture rate), #72 (`sx` gate length / Aer
SuperOp difference), and #70 (pipeline-health backfill figures). Adding a fourth
claimant from this branch would deepen a collision that PR #71 — "fail on
duplicate or colliding ADR / NC identifiers" — exists to police. The numbers
measured here are recorded in this document and in the four linked run logs
instead, and the NC row should be written once #52 merges and the id space is
settled.

## Verification

Re-runnable against the `calibration-data` branch. `R` is the remote holding it:

```bash
R=superconducted-noise-engine/calibration-data
git fetch superconducted-noise-engine calibration-data
git ls-tree -r --name-only $R -- snapshots/2026-08/ibm_fez/ | wc -l
git ls-tree -r --name-only $R -- collisions/ | grep -v README | wc -l
```

Expected at `calibration-data` @ `7139138`: **304** and **1**. Per Rule 6 both
counts name the commit they were measured at; the scheduled poll does not write
to `snapshots/2026-08/`, so 304 is stable under anything but a further backfill.

Ledger decisions written by these four runs:

```bash
git show $R:ledger/2026-09.tsv | awk -F'\t' '$1 ~ /2026-09-06T2[01]:/ {print $4}' | sort | uniq -c
```

Expected: 1 `collision`, 3 `duplicate`, 38 `duplicate-partial`, 28 `new`.

All 23 named documents present — the 14 from §1 and the 9 enumerated in §2:

```bash
for s in 20260812T063125000000Z 20260812T183732000000Z 20260812T204040000000Z \
         20260813T000909000000Z 20260813T071739000000Z 20260813T083510000000Z \
         20260813T092813000000Z 20260813T103541000000Z 20260813T234620000000Z \
         20260814T064606000000Z 20260814T084517000000Z 20260814T112250000000Z \
         20260814T152518000000Z 20260814T173710000000Z \
         20260806T000534000000Z 20260806T011540000000Z 20260806T021325000000Z \
         20260806T030218000000Z 20260806T084023000000Z 20260806T084740000000Z \
         20260806T092941000000Z 20260806T111150000000Z 20260806T114821000000Z; do
  git ls-tree -r --name-only $R -- snapshots/2026-08/ibm_fez/ | grep -q "$s" \
    && echo "ok   $s" || echo "MISS $s"
done
```

Reproducing the false collision needs a working Python 3.12 — not the Windows
Store stub on `PATH`, and not `.venv`:

```bash
git show $R:snapshots/2026-08/ibm_fez/20260813T220506000000Z.json > archived.json
git show $R:collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json > backfilled.json
python scripts/canonical_snapshot_digest.py --compare-reread backfilled.json archived.json
```

Exits `1`. Strip every `parameters[].date` from `properties.gates` on both sides
and compare as multisets — they are equal, which is the finding.

## Related docs

- Issue #53 — the recovery ticket this executes.
- PR #52 — the enumeration evidence, NC-031 and NC-032. **Still open**; #53
  depends on it.
- PR #55 (merged `7d39a2b`) — fractional steps and the gated re-read comparison
  that made this recovery runnable.
- PR #71 — CI for duplicate or colliding ADR and NC identifiers.
- ADR-025 in `docs/decisions.md` — the ledger and collision trees, and the `new` /
  `duplicate` / `duplicate-partial` / `collision` / `collision-unreadable`
  vocabulary.
- NC-026 in `docs/numerical-claims.md` — retention depth ≥ 60 days, re-confirmed
  incidentally here: all 55 enumeration queries at ~32 days depth were honoured.

---

## As of 2026-09-07 — the collision is fixed, and one claim above was wrong

The sections above are the record as measured on 2026-09-06 and are left
unedited. Two things changed the next day.

**The comparator was fixed.** `_strip_parameter_dates` now drops `date` from any
dict that also carries `value`, scoped to the cross-fetch-path comparison only;
the full digest behind `--compare` still hashes dates, because that is the
live-vs-live decision where `collision` is the safe answer. On
`mert/payload-digest-parameter-dates` (`1e7c0eb`), 290 tests passing, 10 added. Comparing
values alone was considered and rejected: it would call a T1 in µs equal to one
in ns.

A sharper root cause than the one recorded above: the 26 differing gate entries
are **exactly** the 26 carrying the `gate_error = 1` "not calibrated"
placeholder, and no measured entry differed at all. The history endpoint
reassembles a document and re-stamps the entries it synthesises, so that `date`
is provenance rather than measurement.

**The spurious file is gone.** `calibration-data` @ `1996bf6` — `collisions/`
holds only its `README.md`, which records why, following the precedent set for
#55's seven files in `40a1ff4`. `snapshots/2026-08/ibm_fez/` is unchanged at 304.
The ledger row `2026-09-06T20:46:55Z ... collision` is deliberately left in
place; the ledger records observations, not conclusions. So #53's "`collisions/`
still empty" criterion now holds.

**What the false collision actually cost, since it is easy to get wrong.** It did
not cost a recovery. The collision branch in `scripts/file_snapshots.sh` sits in
the `else` of `if [ ! -e "$dest/$base" ]`, so it is reached *only* when the stamp
is already archived, and the archived copy is never overwritten (#46 §3c) —
nothing was ever missing from `snapshots/`. The cost was a spurious file on
ADR-025's divergence channel, plus a failed acceptance criterion pointing at the
archive when the fault was in the comparator. An earlier draft of the #53 comment
claimed a lost recovery; that was corrected before posting, and this note records
the mechanism so the mistake is not made again.

**Sequencing risk while the fix is unmerged.** The comparator fix is not on
`main` and has no PR open, so a manual `workflow_dispatch` backfill run before it
merges would write another spurious file. Scheduled polls cannot: they run with
`IS_BACKFILL=0` and never reach that branch.

Detail in `docs/implementations/2026-09-07-payload-digest-parameter-dates.md` on
that branch.

### NC-032 restated per Rule 6

#52 merged as `c9fd441`, so NC-031, NC-032 and `docs/evidence/aug-gap-enumeration/`
reached `main` and this issue's last acceptance criterion became actionable. The
control set reproduces the original figure exactly: `control-2026-08-12_14.tsv`
has 47 rows — 29 `captured`, 14 `MISSED`, 4 `archived_not_served` — giving 43
served by the 1 h sweep, 33 archived, 47 proven to exist, 70.2%.

After the backfill all **47 of 47** control rows are archived, plus 3 documents
inside the same span that the 1 h sweep never served (`20260812T081604000000Z`,
`20260812T104835000000Z`, `20260812T183935000000Z`). Measured over
`20260812T063125Z .. 20260814T174409Z` at `calibration-data` `3d1569d`, the
window holds **50 of ≥ 50 proven**. The 2026-08 directory is stable under
scheduled polling — it read 304 at both `1996bf6` and `3d1569d` — so the figure
does not drift between backfills.

The `≥ 47` denominator was therefore itself an undercount, which is NC-031
arriving from an independent direction: the 1 h sweep served 43 of the 50 now
known to exist, 86.0% against its measured 87.9%.

**The row was restated, not merely annotated.** Rule 6 requires the PR that
changes what a command returns to update the row's value, source commit and
`Last verified` date in the same commit, and the backfill changed exactly what
this row's `git ls-tree` returns. So value moves to `≤ 100% (50 of ≥ 50)`, the
source names `3d1569d` and the span it was measured over, and `Last verified`
moves to 2026-09-07. The prior value is preserved in the Notes column following
the pattern NC-021 already uses for its own history, so the restatement does not
cost the audit trail.

An earlier revision of this section recorded the opposite decision — annotate and
leave the value alone, on the argument that the row measures poller behaviour
rather than archive contents. That argument is not wrong, but it is not Rule 6,
and the rule is the one the acceptance criterion cites. It survives as the
Notes' central warning instead: **the new bound is vacuous and must not be read
as "capture is fine"**, because holding everything you can prove exists gives
100% by construction, and this window is complete only because #53 backfilled
the very window the row measures. A capture rate describing ordinary operation
now needs a window that has not been backfilled, which is #54's territory.
