# 2026-09-07: payload-digest-parameter-dates

## Problem / Motivation

Backfill run [34058863047](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/34058863047)
(issue #53 §1, window `2026-08-12T06:00Z..2026-08-14T20:00Z`, step 0.5 h)
recorded 18 new / 33 duplicate-partial / **1 collision**, writing
`collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json` on
`calibration-data`.

That collision was spurious. Issue #53's acceptance criteria include
"`collisions/` still empty — a backfilled document colliding with an archived
stamp would mean the canonical comparison is wrong, not that IBM republished."
This was that case: the comparison was wrong, and the criterion failed for a
reason that had nothing to do with the archive.

`_payload_digest` was a plain `sha256(json.dumps({"properties": ...},
sort_keys=True))` — it normalised nothing. `canonical_digest` already sorts
`target.operations` for precisely the "provenance-dependent field" reason, and
`is_lossy_reread` keys on `configuration` for the same reason; the payload
digest had no such treatment, and a field inside `properties` turns out to need
it.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/canonical_snapshot_digest.py` | New `_strip_parameter_dates` / `_payload_body`; the payload digest and `canonical_digest(payload_only=True)` now share one byte-string with each parameter's `date` normalised away, while the full digest stays strict. |
| `tests/test_canonical_snapshot_digest.py` | Date-bearing fixtures modelled on the reproduced pair, and 10 tests extending the PR #55 suite that pin both directions of the duplicate-vs-collision decision. |
| `docs/numerical-claims.md` | NC-021 (full test-suite size) → 370, measured at the merge `8176d79`, per Rule 6. The first pass recorded `290` at `0a4271b`, which measured this branch's pre-merge base rather than the tree that will merge; PR #80 review caught that. |

## Reproduction

Performed **before** any change, against the two documents as committed:

```bash
git fetch superconducted-noise-engine calibration-data
git show ca5b23b:snapshots/2026-08/ibm_fez/20260813T220506000000Z.json
git show ca5b23b:collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json
```

`ca5b23b` is the backfill commit that wrote the collision file, and it is the
ref both reads must name. The branch **tip** no longer serves the second path:
`1996bf6` removed the spurious file (see `## Follow-up on calibration-data`
below), so a `git show` against `calibration-data` itself now fails with
`does not exist in 'superconducted-noise-engine/calibration-data'`. The
snapshot blob is unaffected by that removal and is byte-identical at the tip
and at `ca5b23b` (`0db0b0d`); the collision blob is `234500d`.

| Fact | Observed |
| --- | --- |
| `is_lossy_reread(new, archived)` | `True` — PR #55's structural guard works |
| `_payload_digest(new) == _payload_digest(archived)` | `False` — this is the arm that refused |
| `properties.last_update_date` | identical on both: `2026-08-13T22:05:06+00:00` |
| shape | identical: 156 qubits, 1952 gates, 449 general |
| `properties.qubits`, `properties.general`, `properties.general_qlists` | exactly equal, `date` fields included |
| `properties.gates` | 26 of 1952 entries differ |
| within those 26 | every `value` identical; only per-parameter `date` differs |
| the two stamps | `22:14:31` (historical fetch) vs `22:25:32` (live poll) — ~11 min apart |
| gates with per-parameter `date` stripped | multisets **exactly** equal |

Two further facts were measured that the brief did not state, and both shaped
the fix:

1. **The 26 differing entries are exactly the 26 `gate_error = 1` entries.**
   Every placeholder differed; no measured entry did. `gate_error = 1` is IBM's
   "not calibrated" marker, so these entries carry no measurement — their
   `date` records when the response was assembled.
2. **Every `date` inside `properties` lives in a record of shape
   `{date, name, unit, value}`,** in three places: `qubits[][]`,
   `gates[].parameters[]`, `general[]`. No dict inside either document carries
   `date` without `value`. That is what makes the rule below safe to state
   structurally rather than as a hard-coded path list.

## Implementation approach

`_strip_parameter_dates(node)` walks `properties` and returns a copy with the
`date` key removed from **every dict that also carries a `value` key**. It is
pure — it builds new containers rather than mutating — because
`file_snapshots.sh` still writes out the document it just compared, and the
dates must survive into the archived file.

`_payload_body(doc)` produces the canonical byte-string
`json.dumps({"properties": _strip_parameter_dates(...)}, sort_keys=True,
separators=(",", ":"))`. Both `_payload_digest` and
`canonical_digest(..., payload_only=True)` now call it. They were two copies of
the same `json.dumps` line, which is how the field came to be normalised in
neither, and left unmerged they would now disagree on this very pair.

The `"value" in node` guard is what keeps the rule targeted:

- it matches all three parameter locations, at any nesting depth, and survives
  IBM relocating a parameter block — which a path list would not;
- it never matches `properties.last_update_date`, a different key on a dict
  with no `value`, so the document's own identity keeps participating;
- it never matches a gate's own `name` / `gate` / `qubits`.

## Mathematical / Statistical details

The comparison is an equivalence test, not a numeric one, so the content is the
equivalence relation rather than a formula.

Let *D* be a snapshot document and *P(D)* its `properties` block. Define the
normalisation *σ* recursively over JSON values:

- σ(list) = [σ(x) for x in list]
- σ(dict *d*) = { *k* : σ(*d*[*k*]) | *k* ∈ keys(*d*), ¬( "value" ∈ *d* ∧ *k* = "date" ) }
- σ(scalar) = scalar

The payload digest is then

&nbsp;&nbsp;&nbsp;&nbsp;*H(D)* = SHA-256( canonical-JSON( { "properties" : σ(*P(D)*) } ) )

where canonical-JSON is `json.dumps` with `sort_keys=True` and the compact
separators, so key order and whitespace are quotiented out already.

Two documents are judged the same calibration payload iff *H* agrees. Because σ
is a projection (idempotent: σ∘σ = σ) that only ever deletes keys, *H* induces a
**coarser** equivalence than the previous digest: every pair that compared equal
before still compares equal, and the pairs newly made equal are exactly those
differing only in deleted keys. So the change can only convert `collision` →
`duplicate-partial`, never the reverse — which is the direction that needed
justifying, and which the tests pin from both sides.

The decision the workflow makes is not *H* alone. `--compare-reread` returns 0
only under the conjunction

&nbsp;&nbsp;&nbsp;&nbsp;`is_lossy_reread(new, archived)` ∧ *H(new)* = *H(archived)*

with the first conjunct requiring `new.configuration is None` **and**
`archived.configuration is not None`. That gate is directional and unchanged;
it is what keeps the coarsening confined to backfill re-reads.

## Design decisions

**Chosen: drop per-parameter `date`. Rejected: compare `value` only.**
Comparing values alone would discard `name` and `unit`, which are measurement,
not provenance — a `T1` of 100 in `us` would compare equal to a `T1` of 100 in
`ns`, and a `T1`/`T2` relabelling would compare equal to nothing having moved.
`date` is the only field inside a parameter record whose content is decided by
which endpoint answered. Pinned by
`test_a_unit_change_still_differs`.

**Scoped to the cross-fetch-path comparison; the full digest stays strict.**
`--compare` decides `duplicate` vs `collision` for two *live* polls, where the
safe answer is `collision` and any difference belongs in front of a human. The
archive is empirically consistent with live polls being stable here: the poller
has run for months with many duplicate polls and, before this backfill,
`collisions/` held only the seven spurious files from the previous backfill —
so live re-polls of one `last_update_date` do not re-stamp these dates. Should
that ever change, it surfaces in `collisions/` where it can be adjudicated,
rather than being normalised away silently. Pinned by
`test_the_full_digest_still_sees_parameter_dates` and
`test_two_live_payloads_differing_only_in_date_still_exit_one`.

**Could this mask a genuine republication with unchanged values and a moved
measurement time?** In principle yes, and that case should be
`duplicate-partial` anyway:

- The comparison only runs when the two filenames match, i.e. when IBM gives
  both documents the same `last_update_date` — its own statement that this is
  the same document version. `last_update_date` is *not* normalised away and
  still forces a `collision` if it moves
  (`test_last_update_date_still_changes_the_payload_digest`).
- The gate fires only when the incoming side is the strictly poorer document
  (no `configuration`) and the archived side is the richer live copy. What
  would be set aside is a lossy view whose every measurement is byte-identical
  to one already held.
- Empirically the drift is confined to entries that carry no measurement at
  all: all 26 were `gate_error = 1` placeholders, and every measured entry
  agreed across both fetch paths.

**What is genuinely given up.** This is stated plainly because it is a real
cost, not a nil one. On `duplicate-partial` the incoming payload is discarded —
`file_snapshots.sh` moves a file only for `new` (into `snapshots/`) and for
`collision` / `collision-unreadable` (into `collisions/`) — so the historical
endpoint's fetch-time stamps are retained nowhere. The archived copy keeps its
own dates untouched, so no measurement and no measurement time is lost; what is
lost is one endpoint's assembly-time stamp on uncalibrated placeholder entries.
That is provenance about a fetch, not data about the device.

**A correction to the framing this work started from.** The brief said a false
collision "silently costs real recoveries, because a false collision means the
backfilled copy is NOT filed into `snapshots/`". The copy is not filed into
`snapshots/` under *either* decision: the branch is reached only when
`snapshots/<stamp>.json` already exists, and that path is never overwritten
(#46 §3c). The real cost is narrower and still worth fixing — a file on the
channel ADR-025 reserves for real divergence, a `::warning::` per occurrence,
and a failed acceptance criterion for issue #53 that points at the archive when
the fault was in the comparator.

**Vocabulary unchanged.** A third option — a distinct decision for "differs only
in parameter dates" — was rejected. ADR-025 fixes the vocabulary at `new`,
`duplicate`, `duplicate-partial`, `collision`, `collision-unreadable`;
`duplicate-partial` already names exactly "same measurements, partial incoming
document", and widening the vocabulary would need an ADR to buy nothing.

## Verification

```bash
python -m pytest tests/test_canonical_snapshot_digest.py -q
```

38 pass (28 before this change). To confirm the new tests actually pin the
defect, restore the old digest and re-run: exactly 3 fail —
`test_a_parameter_date_difference_is_not_a_divergence`,
`test_payload_only_and_compare_reread_agree_on_a_date_only_pair`,
`test_a_date_only_reread_exits_zero`. The other 7 pass against both the old and
the new digest by design: they guard against the fix over-reaching.

Against the real pair:

```bash
git fetch superconducted-noise-engine calibration-data
git show ca5b23b:snapshots/2026-08/ibm_fez/20260813T220506000000Z.json > archived.json
git show ca5b23b:collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json > new.json
python scripts/canonical_snapshot_digest.py --compare-reread new.json archived.json; echo $?
```

Read both documents at `ca5b23b`, not at the branch tip: `1996bf6` has since
removed the collision file. Read them with `git show` rather than checking the
branch out, so `core.autocrlf` cannot rewrite the bytes the digest hashes.

`0` after this change (was `1`), which `file_snapshots.sh` reads as
`duplicate-partial`. `--compare new.json archived.json` still exits `1`, and
mutating the pair still exits `1` under `--compare-reread` for each of: a `T1`
moved by 1e-9, a placeholder's `gate_length` moved 24 → 25, a `T1` unit changed
`us` → `ns`, a moved `last_update_date`, and two live copies differing only in a
date.

Full suite and static checks:

```bash
python -m pytest tests/ -q
```

370 collected and 370 pass at `8176d79` (NC-021), the merge that brings this branch
up to `main` at `645b4d1`. `ruff check .` (all checks passed), `ruff format --check .`
(53 files already formatted) and `mypy --strict src/superconducted` (25 source files,
no issues) are clean at the same commit.

The earlier figure in this document, `290` at `0a4271b`, measured the branch before
the merge. It described neither side and is superseded; see NC-021 for the chain.
Nine of the 370 (`tests/test_file_snapshots.py`) skip on a machine without `git` and
`bash`, giving 370 collected / 361 passed / 9 skipped there.

> On Windows the working interpreter is
> `C:\Users\senso\AppData\Local\Programs\Python\Python312\python.exe`; `.venv`
> and every `python` on `PATH` are the Microsoft Store stub.

## Follow-up on `calibration-data`

The spurious file is removed from the data branch and the removal recorded in
`collisions/README.md`, following the precedent of commit `40a1ff4` (PR #55's
seven spurious files). The ledger row
`2026-09-06T20:46:55Z	ibm_fez	20260813T220506000000Z	collision` is **left
alone**: the ledger records observations, not conclusions, matching the
treatment of the 2026-09-02 rows.

## Related docs

- ADR-025 in `docs/decisions.md` — the ledger and collision trees, and the
  decision vocabulary
- `docs/implementations/2026-09-02-backfill-comparison-and-step.md` — the
  `--payload-only` digest this extends
- `docs/implementations/2026-09-02-pr50-review-fixes.md` — the worktree fix that
  keeps `scripts/` on disk during a poll
- NC-021 in `docs/numerical-claims.md`
- Issue #53; PR #55; `calibration-data` commit `40a1ff4`
