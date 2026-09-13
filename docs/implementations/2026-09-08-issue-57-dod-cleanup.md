# 2026-09-08: Issue #57 definition-of-done cleanup

## Problem / Motivation

An audit of Issue #57's fifteen definition-of-done checkboxes against merged
`main` at `2d66f7a` found eleven met and four not. Three of the four are
documentation defects fixable without a decision; this change closes them. The
fourth — reviews and the advisor loop — needs people, not commits, and is left
open deliberately.

1. **The fixture regeneration snippet does not run.**
   `tests/fixtures/calibration/README.md` told the reader to
   `git fetch origin calibration-data` and then read
   `origin/calibration-data:snapshots/...`. This repository's only remote is
   named `superconducted-noise-engine`, so that ref does not exist. The DoD
   names this item explicitly ("the correct remote name") and §6.1 lists a
   "remote-name fix"; it was the one part of the README task not done.
2. **The Burak-desktop verification record is stale.** It certifies `356
   passed` at `37e1ba0`, but four commits landed after that measurement and
   before PR #69 merged, taking the suite to 360.
3. **FR-14's `__init__.py` ownership question was never answered.** It required
   choosing reading (a) or (b) *and recording which in the PR*. The
   `docs/team.md` row implies (a) by naming `__init__.py`, but the choice was
   never written down, so the next package meets the same open question.

## What changed

| File | One-sentence description |
| --- | --- |
| `tests/fixtures/calibration/README.md` | Regeneration snippet and provenance ref now name the `superconducted-noise-engine` remote, with a note that the name is checkout-local. |
| `docs/verification/2026-09-05-issue-57-burak-desktop.md` | Gains a dated "as of 2026-09-08" section recording the 356 → 360 drift, what caused it, what it does *not* invalidate, and that a canonical re-run is still owed. |
| `docs/team.md` | Records the FR-14 reading (a) decision and why (b) was rejected. |

Documentation only. The suite is unchanged at 360, so NC-021 needs no update.

## Implementation approach

**The remote name.** Both the runnable `git fetch` line and the `git show` ref
inside the snippet were changed; the provenance line was changed with them
because the snippet consumes it as `src`. A clause was added noting the remote
name is whatever the local checkout calls this repository, since a plain
`git clone` names it `origin` — the fix should not simply move the breakage to
a differently configured clone.

**The verification record** was extended by appending a dated section, never by
editing the existing rows. Those rows are correct *as measured* at `37e1ba0`;
rewriting them would destroy the audit trail and misrepresent what was run on
which machine. This follows the project's append-only convention for dated
snapshots.

## Mathematical / Statistical details

N/A — purely structural. One numeric reconciliation is recorded rather than
derived: the suite moved 356 → 360, a `+4` delta attributable to three tests in
`tests/test_interfaces.py` and one in `tests/training/test_parameters.py`. The
merged tree at `2d66f7a` was re-collected at 360, matching NC-021.

## Design decisions

**Why the as-of section refuses to certify the new number.** The 360 was
measured on the lead's laptop. The project's convention is that Burak's desktop
is the single source of truth and laptop results are provisional, so the four
added tests have not run on the canonical machine. Writing "verified: 360" would
have been the easy edit and the wrong one — it would launder a provisional
figure into a certification. The section instead records the drift, states
explicitly that it is not a verification, and asks for a re-run stated
*differentially against NC-021's commit* rather than as an absolute, so a stale
row surfaces as a visible mismatch instead of a silent contradiction.

It also records what the four commits did **not** touch — the Aer SuperOp
maximum, the 234 parameter count, and the fixture's SHA-256, size and record
counts — so the re-run does not have to re-derive figures nothing disturbed.

**Why FR-14 reading (a) rather than (b).** Reading (b) would declare
docstring-only `__init__.py` files outside the ownership table. That was
rejected because `src/superconducted/__init__.py` is not docstring-only: it
re-exports the ten ABCs and eight value types, which is precisely the surface a
cross-cutting change can alter unnoticed — as it was when `TSKTrainer` went
unexported and the docstring counts drifted. A package root with an unstated
owner is the wrong place to economise. Reading (a) — one row naming the package
— also makes the existing rule ("a new module appears in the source tree") and
the table's actual practice agree, which they did not before.

## Verification

```bash
ruff check . && ruff format --check .    # clean
mypy --strict                            # no issues in 32 source files
python scripts/check_ids.py              # no colliding identifiers
pytest tests/ --collect-only -q          # 360, unchanged
```

The README fix was verified by running the corrected snippet rather than by
reading it:

```
$ git show 'superconducted-noise-engine/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json'
{ "backend": "ibm_fez", ...

$ git show 'origin/calibration-data:snapshots/...'
fatal: invalid object name 'origin/calibration-data'.
```

## Still open on Issue #57

Not addressed here, because none of it is a commit:

- **Reviews.** The DoD requires `@BurakOztekin` and `@bengisucvd` to have
  approved. Burak authored PR #69 and could not approve it; `@bengisucvd` was a
  requested reviewer who never submitted, and #69 has merged, so that checkbox
  can no longer be satisfied in its original form. Her PR #79 (#58) consumes
  this target and is where §7 decision 3 wanted her to confirm `build_reference`
  applies the identical Skip rule in the same order.
- **Dr. Akba's decisions** on the four §7 items, and his module-owner read of
  `interfaces.py` and `types.py`.
- **`docs/advisor/2026-09-03-decisions-from-akba.md`** does not exist; Issue #56
  owns creating it.
- **The decision-5 follow-up PR** — ADR-027 Open → Accepted, the advisor-file
  entry, and an `> Advisor decision · <date>` line — is neither opened nor
  scheduled.

## Related docs

- Issue #57 §10 (definition of done), FR-11 and §6.1 (the README task), FR-14
  (the `__init__.py` question)
- `docs/verification/2026-09-05-issue-57-burak-desktop.md`
- `docs/implementations/2026-09-08-issue-57-review-follow-ups.md` and
  `2026-09-08-tsk-trainer-contract-docstring.md` — the earlier two rounds
