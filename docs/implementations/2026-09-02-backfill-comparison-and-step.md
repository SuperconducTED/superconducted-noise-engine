# 2026-09-02: backfill-comparison-and-step

## Problem / Motivation

The first production backfill run exposed two defects that together made the recovery
path in #53 unusable. Both were found by running one small canary window rather than the
whole recovery, and both are in code merged earlier the same day.

**1. The backfill rejected every sub-hourly step.** `_build_historical_window` parsed
`step_hours` with `int()`, so `-f historical_step_hours='0.5'` failed with
`invalid literal for int() with base 10: '0.5'` before a single query was made
([run 33673095532](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33673095532)).
Nothing advertised that restriction: the workflow input said only "Step in hours", and
the probe's own `--enumerate` has always taken floats. It matters because a 1 h grid was
*measured* to miss documents that exist: NC-031 puts its recall at 87.9%, 29 of the 33
archived documents in one control window. A mean republication interval would not
establish that on its own — whether a document is caught depends on how long it remains
the newest one older than some query instant and on where those instants fall, not on the
mean (PR #55 review). The finest reachable grid was therefore one demonstrably lossy, and
a backfill could not reach the documents it was run for.

**2. Every re-read of an archived stamp was filed as a collision.** Retrying at a 1 h step
([run 33673272236](https://github.com/SuperconducTED/superconducted-noise-engine/actions/runs/33673272236))
recovered 2 genuinely missing documents and wrote **7 files into `collisions/`** — a tree
ADR-025 says should stay empty because anything in it signals real divergence. All 7 were
false. Their `properties` blocks are byte-identical to the archived copies; they differ
only because a historical fetch leaves `configuration` as `None` and sources `target`
from `target_history` rather than the live backend.

This is structural, not bad luck. A sweep queries instants inside a gap and the service
answers with the document at the gap's opening, which we already hold — so a re-read, and
a false collision, is the *normal* outcome for a swept gap rather than an unlucky one.

It is **not** true that every gap must yield one. A gap shorter than the step can fall
between query instants entirely, and the canary contains an example: no hourly instant
falls in 22:07:58–22:49:57 (PR #55 review). So the count scales with how many archived
stamps a sweep re-reads, which was not projected for the five remaining windows in #53 and
should not be quoted as though it were. What is measured is the canary's own rate: 13
historical query instants produced 7 false collisions. The run was stopped there.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/calibration/poller.py` | `_build_historical_window` parses the step as `float`, so sub-hourly backfill sweeps are accepted; the positivity check and error text are unchanged. |
| `scripts/canonical_snapshot_digest.py` | New `--payload-only` mode (and `canonical_digest(..., payload_only=True)`) that digests just `properties`, ignoring the provenance-dependent `target` and `configuration`. |
| `scripts/file_snapshots.sh` | Two-stage comparison: a full mismatch now asks whether the calibration payload matches before calling it divergence, and records `duplicate-partial` when it does. |
| `.github/workflows/calibration-poll.yml` | The step input documents that fractions are allowed and why 0.5 or finer is wanted for recovery. |
| `docs/decisions.md` | ADR-025 gains `duplicate-partial` in its vocabulary, with the reasoning and the consequence for `collisions/`. |
| `tests/test_calibration.py` | `TestBuildHistoricalWindow`: fractional, integer and quarter-hour steps, plus non-positive, unparseable and reversed inputs. |
| `tests/test_canonical_snapshot_digest.py` | Payload-only digest and CLI: provenance differences ignored, changed measurements still caught, degenerate documents still digestible. |
| `tests/test_file_snapshots.py` | End to end: a historical re-read of an archived stamp is `duplicate-partial` with `collisions/` untouched; the same re-read with a moved T1 is still `collision`. |
| `docs/numerical-claims.md` | NC-021 updated for the 18 tests added here. |
| `docs/implementations/2026-09-02-backfill-comparison-and-step.md` | This document. |

## Implementation approach

**The step.** One character of substance, `int` → `float`. `timedelta(hours=...)` already
accepts floats and the `step_hours <= 0` guard works unchanged, so nothing else moved. The
docstring records why the restriction was harmful rather than merely wrong, because the
value that makes it harmful (the publish cadence) lives in a register row and not in the
code.

**The comparison.** The first attempt compared in full and, on a mismatch, compared the
payload — and was withdrawn in review. It provided none of the extra strictness it
claimed: full equality implies payload equality, so *"identical in full, or else identical
in payload"* reduces to *"identical in payload"*. Two **live** payloads differing only in
`target` would have been recorded `duplicate-partial` and discarded where they were
previously preserved (PR #55 review, P1, reproduced with the real filing script).

So the narrow comparison is not reached by elimination. It is **gated on two independent
conditions, both required**, and only then applied:

1. Canonical full compare. Equal → `duplicate`. Unchanged, and still the fast path.
2. Unreadable (exit 2) → `collision-unreadable`, unchanged. No payload comparison is
   attempted; a file that cannot be parsed cannot be parsed either way.
3. Differs, **and** the run swept a historical window (`IS_BACKFILL`, passed by the
   workflow from `inputs.historical_start`), **and** the incoming payload carries the
   structural signature of the expected loss — no `configuration` of its own where the
   archived copy has one — **and** the calibration payloads match → `duplicate-partial`.
   The archived copy is kept, being the more complete of the two, and nothing is written
   to `collisions/`.
4. Anything else that differs → `collision`, exactly as before.

The signature test is directional: a *more* complete payload is never explained away, and
two live payloads both carry a configuration so they never reach it. A scheduled poll
fetches live, so it can never take branch 3 at all. Both gates live in one tested function,
`is_lossy_reread`, behind `--compare-reread`, rather than being split between shell and
Python.

## Mathematical / Statistical details

N/A — purely structural. The change alters which of two documents is preferred and how a
difference is classified; it computes no new quantity. The figures that motivate it
(NC-031's 87.9% recall) were measured elsewhere and are cited, not recomputed. NC-031 is
recall against *archived* documents in one control window, not a general capture
guarantee, and is used here only to say that a 1 h grid demonstrably misses some.

One counting note for the reader: the 7 false collisions are 7 *files*, one per distinct
archived stamp the canary re-read, not 7 documents lost. Nothing was lost — the archived
copies were never overwritten, which is the property #46 established and this change does
not touch.

## Design decisions

**Gate the narrow comparison on provenance, do not reach it by elimination.** The single
comparison right in both directions does not exist: comparing in full is correct between
two live payloads and wrong across fetch paths; comparing payload-only is correct across
fetch paths but tolerates a `target` divergence between two live ones. *Ordering* the two
questions does not resolve that, which is the mistake the first attempt made — the order
is vacuous because full equality implies payload equality. What resolves it is asking
whether this payload can be a lossy re-read **at all**, from the run's provenance and the
document's own shape, before letting a payload match excuse anything.

**One known limit, recorded rather than fixed.** `configuration is None` is a structural
signature, not proof of provenance. A *live* fetch whose `backend.configuration()` call
failed would carry the same shape, and during a backfill it could then be scored
`duplicate-partial`. The `IS_BACKFILL` gate narrows this to backfill runs only, and it has
not been observed on the pinned `qiskit-ibm-runtime`, so it is documented rather than
worked around. The clean fix is for the poller to record the fetch type in the snapshot
itself, which changes the schema and belongs with ADR-020 rather than here (PR #55 review,
nit 3).

**`duplicate-partial` rather than reusing `duplicate`.** The two are not the same
observation. `duplicate` means the poller saw exactly what the archive holds;
`duplicate-partial` means it saw the same measurements through a lossier path. Collapsing
them would make the ledger claim a byte-identical re-observation that never happened, and
the ledger exists precisely so that a future reader can tell what was observed from what
was inferred.

**The archived copy always wins.** A historical fetch is strictly less complete, so
keeping the archive is right today. It is worth noting the converse is not handled: if a
stamp were ever archived *from* a backfill and later re-observed live, the more complete
copy would be rejected as `duplicate-partial`. That cannot happen with the current archive,
all of which is live-fetched, and fixing it speculatively would add a preference rule with
no case to exercise it.

**Nothing was done about the 7 files already on the branch.** They are real artifacts of a
real defect and deleting from the audit branch is a separate decision. They are also the
only production example of the failure this change prevents, which makes them worth keeping
until #53 is closed.

**The canary stayed small on purpose.** The shortest of the six recovery windows:
12 h 40 min, which at the 1 h step it fell back to is **13 historical query instants plus
one current fetch**, not the 26 instants the intended 0.5 h step would have produced. Both defects
surfaced inside two minutes and cost 7 spurious files. Running all six windows first would
have cost more, by an amount nobody has computed — which is the argument for a canary, not
a number to quote.

## Verification

```bash
pytest tests/ -q          # count: NC-021 in docs/numerical-claims.md
ruff check .              # All checks passed
ruff format --check .     # clean
mypy --strict             # no issues
```

The two defects are each pinned by a test that fails on the pre-fix code:

- `tests/test_calibration.py::TestBuildHistoricalWindow::test_fractional_step_is_accepted`
  raises `ValueError: invalid literal for int()` before the change.
- `tests/test_file_snapshots.py::TestFileSnapshots::test_a_backfilled_re_read_is_not_a_collision`
  records `collision` and writes a `collisions/` file before the change; `duplicate-partial`
  and an empty tree after.

The protection that must not regress has its own test —
`test_a_changed_measurement_is_still_a_collision_across_fetch_paths` — which uses the same
provenance difference but a moved T1, and must still reach `collisions/`.

To confirm against production data once merged, re-run the canary window. Expect
differentially: the same 2 documents already recovered are now `duplicate` or
`duplicate-partial` rather than `new`, the previously-collided stamps come back
`duplicate-partial`, and `collisions/` gains nothing.

```bash
gh workflow run calibration-poll.yml --repo SuperconducTED/superconducted-noise-engine -f historical_start='2026-08-17T18:00:00Z' -f historical_end='2026-08-18T06:40:00Z' -f historical_step_hours='0.5' -f max_historical_days='60'
```

Local runs are provisional; the authoritative run is on the designated desktop.

## Related docs

- #53 — the recovery this unblocks; its dispatches should use a 0.5 h step once this lands
- ADR-025 (`docs/decisions.md`) — the ledger and collision trees, amended here
- `docs/implementations/2026-09-02-aug-gap-enumeration.md` — NC-030 and NC-031, the figures
  that make an integer-only step harmful
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` — #46's
  never-overwrite rule, which this change relies on and does not alter
- `docs/numerical-claims.md` — NC-021, NC-030, NC-031
