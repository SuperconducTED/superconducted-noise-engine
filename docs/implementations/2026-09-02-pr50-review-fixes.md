# 2026-09-02: pr50-review-fixes

## Problem / Motivation

Bengisu's review of PR #50 at `a4c6568` requested changes. Every point was
reproduced locally before anything was changed, and every one held:

| # | Finding | Reproduced how | Outcome |
| --- | --- | --- | --- |
| 1 | **Blocker.** `calibration-poll.yml` checked `calibration-data` out in place and then ran `scripts/canonical_snapshot_digest.py`, which that branch does not carry. | Two-branch sandbox: after `git checkout -B calibration-data`, `scripts/` is gone, Python exits **2**, the ledger decision is `collision-unreadable`. The same payload pair compared from an intact tree exits 0 (`duplicate`). | Fixed — separate worktree, logic moved to a script, tested end to end. |
| 2 | A transient error on every historical depth made the probe print "NO HISTORICAL ACCESS … the gaps are unrecoverable" and exit **2**, which the workflow accepts as a successful negative result. | Stub backend: current document fine, historical calls raise `RuntimeError("transient HTTP 503")` → exit 2 on the old code. | Fixed — ERROR/MALFORMED are non-answers; exit 1 with an INDETERMINATE result. |
| 3 | The enumeration sweep did not check that an answer was older than its request; a service ignoring the filter produced "0 inside the window" and exit **0**. | Stub returning the current document for every step → clean exit 0 on the old code. | Fixed — dishonoured answers are excluded, counted, and fail the sweep. |
| 4 | "504 distinct states" was being read as 504 independent samples; 630 = 126 × 5 is a working threshold, not a guarantee. | Read against #45 §3 cadences: consecutive states are correlated. | Caveat added to the doc, NC-012 and NC-025. Conclusion (not met) unchanged. |
| 5 | The doc said #45's "2.7× polling → 1.57× data" was measured in states. | #45 §1: it is snapshot files per day. | Corrected in place. |
| 6 | Two depth queries cannot prove the Aug 7–17 windows are empty, and the same report shows `updated_before` does not strictly return the newest older document. | Each query bounds only up to its own instant; one window was never probed; the outage enumeration holds two archived documents the sweep never returned. | Rewritten to "consistent with, not proof of"; sweep noted as a post-merge follow-up. |
| 7 | The 40-snapshot selection rule and the regression script were not committed. | Found in a prior session's scratchpad; rule recovered. | `scripts/init_error_analysis.py`, pinned to archive commit `f0930b9`. |

The pre-deployment simulation described in the 2026-08-29 doc ran the shell
logic *without* the branch switch, which is exactly where finding 1 lived. The
lesson is the same one the numerical-claims register was built on: a check that
does not exercise the real condition reports green for the wrong reason.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/file_snapshots.sh` | New: the filing step, run from the source checkout against a separate worktree of `calibration-data`; payload-month filing, never-overwrite, canonical `duplicate`/`collision` split, poll ledger, commit and push. |
| `.github/workflows/calibration-poll.yml` | The commit step sets the bot identity and calls the script with `STAGING_DIR` and `DATA_WORKTREE` (under `$RUNNER_TEMP`); no in-place checkout. |
| `tests/test_file_snapshots.py` | New: runs the script under bash against a sandbox origin holding a real `calibration-data` branch and asserts the pushed ledger, tree, bytes, and commit subject; skipped where `git` or `bash` is absent. |
| `scripts/probe_historical_properties.py` | `Verdict` enum with a `definitive` flag and a `ProbeResult` row; a shared retry helper for both modes; the sweep excludes and counts answers newer than their request; `main` exits 1 for an undecided table instead of 2. |
| `tests/test_probe_historical_properties.py` | Verdict partition pinned; retry behaviour; the three review scenarios reproduced exactly; exit codes for every combination of served/refused/undecided. |
| `.github/workflows/calibration-historical-probe.yml` | Comment on the exit-code gate updated to say what 1 now covers. |
| `scripts/init_error_analysis.py` | New: reproduces NC-027 and NC-028 from the archive at a pinned ref via `git show`; states the sample rule; canonical split between snapshots, row-midpoint variant kept for continuity. |
| `tests/test_init_error_analysis.py` | New: the sample rule (including why the ref must be pinned), the R² arithmetic, and an end-to-end read from a synthetic git ref. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | Findings 4–7 corrected in place, each marked, with a dated corrections log listing every change. |
| `docs/numerical-claims.md` | NC-012 and NC-025 gain the independence caveat; NC-026 notes the exit-code change; NC-027 and NC-028 cite the committed script and are re-verified; NC-029/030 note why the honour check leaves them unchanged; NC-021 updated per Rule 6. |
| `docs/decisions.md` | ADR-025 gains the worktree consequence and cites the script. |
| `docs/implementations/2026-09-02-pr50-review-fixes.md` | This document. |

## Implementation approach

**Filing through a worktree.** The root cause of the blocker is structural:
the step destroyed its own working tree halfway through and then assumed it was
intact. Copying the digest somewhere safe before the checkout would fix this
call and leave the trap armed for the next one. Instead the data branch is
checked out *beside* the source tree —

```bash
git fetch "$DATA_REMOTE" "$DATA_BRANCH"
git worktree add -B "$DATA_BRANCH" "$DATA_WORKTREE" "$DATA_REMOTE/$DATA_BRANCH"
cd "$DATA_WORKTREE"
```

— so `scripts/`, the editable install, and everything else in the checkout
stay where they are. `-B` resets the local branch to the remote tip, exactly as
the old `git checkout -B` did. The script resolves `STAGING_DIR` to an absolute
path and locates the digest by its own position (`BASH_SOURCE`) before changing
directory, so neither depends on where the caller stands; a missing digest is a
hard stop before any git operation, never a silent fall-through. Everything
after the `cd` — the filing loop, the ledger, the commit subject — is the
reviewed logic moved verbatim, with `$POLL_TIME`, `$BACKEND` and `$PYTHON`
overridable so a test can pin them. The push goes to the sandbox's local bare
repository in the test and to GitHub in CI; the script cannot tell the
difference, which is the point.

**Probe verdicts as data, not strings.** `_probe_one` now returns a
`ProbeResult(verdict, detail, requested, stamp)` whose `verdict` is a `Verdict`
enum. `Verdict.definitive` is true for OK, DENIED, IGNORED, CLAMPED and
UNAVAILABLE — answers from the service — and false for ERROR and MALFORMED —
failures of the transport or of the document. `main` decides the exit code
from that partition (see the next section). Both modes call one
`_properties_with_retry` helper with the poller's backoff shape;
`NotImplementedError` is propagated immediately because a documented refusal
is not a transient.

**Sweep honour check.** The enumeration's argument — every published document
is the answer for at least one step — holds only for steps the service actually
honoured. Each answer is now compared against its own request: a stamp newer
than the request means the filter was ignored or clamped for that step, and the
answer says nothing about the window. Such answers are excluded from the served
list, counted, and reported with the first offending pair; an answer with no
usable stamp is counted separately. Either makes the sweep exit 1 with the list
marked INCOMPLETE. The served stamps are still printed before the failure line,
so a partial sweep's evidence is not wasted. This is the same rule
`fetch_snapshot` already applies to a single historical read
(`poller.py`, "Refusing to archive it").

**Pinned regression analysis.** `scripts/init_error_analysis.py` lists the
archive at `--ref` with `git ls-tree`, applies the cutover and the sample rule,
and reads each sampled snapshot with `git show`. Nothing is checked out and
nothing is written. The ref defaults to `f0930b9` because the rule
`files[::len(files) // 40][:40]` depends on how many post-cutover files exist:
one more commit on the data branch changes the step and therefore every pick.

## Mathematical / Statistical details

**Exit-code decision rule (depth probe).** For results r₁…rₙ over the probed
depths:

- exit **0** if any rᵢ is OK — access is demonstrated at that depth;
- else exit **1** if any rᵢ is ERROR or MALFORMED — no depth was served, but at
  least one could not be judged, so "denied" was not shown;
- else exit **2** — every depth was definitively refused.

The old rule was "0 if any OK, else 2", which maps a table of pure transport
failures to "the gaps are unrecoverable". The workflow gates on `rc ∈ {0, 2}`,
so that misreport would have passed as a finding.

**Honour predicate (sweep).** For a query at instant T the service's contract
is "the newest document with `last_update_date` ≤ T". An answer with stamp
S > T violates it and is discarded from the served set; S = T is honoured. The
sweep's count `honoured = queries − not_honoured − unusable − failed`, and the
exit is 1 whenever `not_honoured + unusable + failed > 0`.

**R² and the tie-order finding (NC-028).** R² = 1 − Σ(y − ŷ)² / Σ(y − ȳ)² with ȳ
the *test* mean, so a negative value means the fit predicts held-out data worse
than its own mean. Re-running the recovered analysis against `f0930b9` gave, for
the row-midpoint cut, −0.586266 where −0.585 had been recorded. The cause is
that 4607 // 2 = 2303 lands inside the 2026-08-19T12:45:23 snapshot (3 of its
115 rows train, 112 test), so the value depends on that snapshot's row order —
which the original scratchpad left to `np.argsort` on tied keys (unstable):
emulating that gives −0.584974, snapshot order gives −0.586266, and 200 random
orderings of that one snapshot span −0.610581 to −0.580685. A split *between*
snapshots (first 20 train, last 20 test; n = 2300 / 2307) cannot be moved by
any ordering and gives **−0.584865**, which is Bengisu's independent
reproduction to six decimals. That figure is now NC-028's; it rounds to the
recorded −0.585, so no public number changed. In-sample R² (0.138776) and the
best single predictor (`readout_error`, in-sample 0.1279, out-of-sample
−0.1675 on the boundary split) are unchanged at the precision recorded.

**Independence caveat (NC-012, NC-025).** A samples-per-parameter rule counts
independent samples. Distinct device states are an upper bound on that count:
consecutive states share most of their coherence values (T1/T2 recalibrate
~daily) and are correlated in readout (~4 h cadence), so the effective sample
size is below 504 and the ratio to 126 trainable parameters is below 4.0. The
630 threshold is itself a rule of thumb. Both caveats push the same way as the
existing conclusion; quantifying the dependence is deferred with the trainer.

## Design decisions

**Worktree and extracted script, not copy-to-temp or a Python rewrite.** Three
options were put to the project owner. Copying the digest to `$RUNNER_TEMP`
before the in-place checkout is a two-line change but leaves the tree
destruction in place for the next tool that assumes otherwise, and the
requested branch-switch test would have to parse the YAML `run:` block. A
Python rewrite of the filing logic would be cross-platform and mypy-checked but
moves logic three reviewers had already read. The worktree removes the whole
class of bug with a three-line change to the reviewed step, and extracting the
body to `scripts/file_snapshots.sh` makes it runnable by a test as-is. Chosen
2026-09-02.

**The branch-switch test runs bash, and skips without it.** CI is Ubuntu;
Git for Windows ships `bash` and `sha256sum`, and the test prefers Git's bash
over the WSL launcher and probes it before use. A skip on a machine without
either is visible in `-rs` output rather than a silent pass.

**UNAVAILABLE stays definitive; ERROR and MALFORMED do not.** `None` from
`properties()` is the SDK's answer (it returns `None` for simulators and for
"no properties"), not a failure to ask; the existing verdict table already
grouped it with DENIED. An exception after retries, or a document with no
stamp to judge, is a failure to ask or to judge. The reviewer named exactly
those two as the ones to separate.

**A dishonoured sweep exits 1, not 2.** In depth mode the probe fetches the
current document first, so it can tell IGNORED (equals current) from CLAMPED
(older than current, newer than requested) and call the table definitive. The
sweep makes no current fetch and only knows "newer than asked", and its
question is "which documents does the window hold", which such answers leave
open. Exit 1 says so; the depth probe is the tool for the definitive 0/2
question. Dishonoured stamps are excluded from the served list even when they
fall inside the window, because a list that mixes honoured and unhonoured
answers cannot be diffed against the archive.

**Retries in the depth probe.** The sweep already retried; the depth probe did
not, so under the new rule a single 503 would have flipped a definitive run to
exit 1. One helper now serves both, reading the same `SUPERCONDUCTED_HTTP_RETRIES`
knob as the poller.

**The snapshot-boundary split is canonical; the row-midpoint split is kept.**
The canonical figure must be one nobody can move by reordering rows the data
does not order. The original procedure is still printed so a reader of the
2026-08-30 text can see where its number came from and why it wobbles.

**Corrections in place, with a log.** The 2026-08-29 document is the durable
record NC rows point at, so a sentence known to be false was not left standing
with a footnote. Each change is marked where it sits and listed in a dated
corrections section, following the document's own 2026-08-30 precedent.

**The Aug 7–17 enumeration was not run.** It needs `workflow_dispatch` with an
`enumerate_window` input, which GitHub only accepts for a workflow already on
the default branch; the push trigger enumerates the trailing 72 h only. The
IBM token lives in repository secrets and does not move to a workstation.
Documented as the post-merge follow-up that settles the question.

**Duplicates stay in staging.** The old step left a duplicate payload in
`/tmp/staging`; the script leaves it in `STAGING_DIR`. Unchanged and asserted.

## Verification

All commands from the repository root with the working 3.12 interpreter (see
NC-021 for the test count and the commit it was measured at — cite the row,
do not restate the number).

```bash
pytest tests/ -q -rs            # count: NC-021; expect no skips on a machine with git and bash
ruff check .                    # All checks passed
ruff format --check .           # all files already formatted
mypy --strict                   # [tool.mypy] files: src/superconducted, scripts
```

The blocker, reproduced with the old step body and then with the fix, in the
same sandbox shape (bare origin with a `calibration-data` branch, source repo
with `scripts/`, one re-serialised duplicate payload):

```
--- OLD step body (PR #50 @ a4c6568) ---
before checkout: branch=main scripts/=present
after  checkout: branch=calibration-data scripts/=ABSENT
python: can't open file '.../scripts/canonical_snapshot_digest.py': [Errno 2] No such file or directory
digest exit=2  -> ledger decision=collision-unreadable
--- same payload pair, digest run from an intact tree ---
digest exit=0 -> would be: duplicate
```

`tests/test_file_snapshots.py` then asserts, on what reached origin: A is
`duplicate` and its archived bytes are untouched, B is `collision` with exactly
one file under `collisions/2026-08/ibm_fez/`, C (a June stamp polled in
September) is `new` under `snapshots/2026-06/`, the commit subject is
`calibration: <poll time> ibm_fez (+1)`, the source repo is still on `main`
with `scripts/` present, and a second run in the same month appends to the same
ledger with a `poll:` subject when nothing is new. A run without the digest
exits 1 and pushes nothing.

The two probe findings, reproduced as tests and then fixed:

```bash
pytest tests/test_probe_historical_properties.py -q -k "transient_errors_at_every_depth or current_document_for_every_query"
```

Both fail on the pre-fix script (exit 2 and exit 0 respectively) and pass now.

The regression figures, from the committed script against the pinned archive:

```bash
git fetch <remote> calibration-data          # f0930b9 must be reachable
python scripts/init_error_analysis.py --ref f0930b9
```

Expected, differentially: the NC-027 block reports 0 of 40 snapshots complete,
40 qubits always missing plus 1 intermittent; the NC-028 block reports n = 4607,
in-sample R² 0.1388, snapshot-boundary R² equal to the NC-028 value, and a
row-midpoint R² about 0.0014 lower with the "tie-order sensitive" note. The
snapshot-boundary value must match the reviewer's −0.584865.

Local runs are provisional; the authoritative run is on the designated desktop.

## Related docs

- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` —
  the work this round corrects; see its "Corrections, 2026-09-02" section
- ADR-025 in `docs/decisions.md` — ledger and collision trees; gains the
  worktree consequence here
- ADR-017 in `docs/decisions.md` — the Skip strategy NC-028 supports
- `docs/numerical-claims.md` — NC-012, NC-021, NC-025..NC-030
- `docs/evidence/pr47-outage-enumeration/README.md` — the two archived
  documents the sweep never returned, cited in the Aug 7–17 correction
- PR #50; its review thread; #45 (decisions), #46 (byte stability)
