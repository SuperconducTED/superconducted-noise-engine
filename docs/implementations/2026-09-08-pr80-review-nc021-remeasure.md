# 2026-09-08: PR #80 review · re-measure NC-021 on the merged tree

## Problem / Motivation

PR #80 fixes the false `collision` that the Issue #53 backfill exposed, and
Burak's review found the code and the regression coverage sound. It requested
one change, and it is a register-discipline change rather than a code one:

> NC-021 güncel main tabanı yerine bu branch'in eski test sayımını (290)
> kaydediyor. Rule 6 gereği, branch güncel maine alındıktan sonra merge
> edilecek gerçek ağaçta test sayısını yeniden ölçüp NC-021'i commit ve
> sonuçla güncelleyebilir misin?

The branch recorded `NC-021 = 290`, measured at `0a4271b` on a base of
`7d39a2b`. While PR #80 sat open, `main` advanced four commits to `645b4d1`
and PRs #69, #81 and #82 moved NC-021 to `360`. `290` was therefore a correct
measurement of a tree nobody will ever merge: it describes this branch's
pre-merge base, not the post-merge result.

This is precisely the failure `docs/numerical-claims.md` **Rule 6** exists to
prevent. It is also the failure that already cost the project a round trip
twice: PR #32 pre-filled an unsourced `152` against a 149-test suite, and
PR #29 cited a *sourced* NC-021 that PRs #33/#34 had silently invalidated, so a
correct verification run reported a regression that did not exist (issues #40,
#29). A sourced number rots exactly as fast as a remembered one when the tree
underneath it moves.

Left as it stood, the row would have merged already stale, and the next runbook
citing it would have manufactured a phantom regression on Burak's desktop.

## What changed

| File | One-sentence description |
| --- | --- |
| *(merge commit `8176d79`)* | Merges `main` at `645b4d1` into `mert/payload-digest-parameter-dates`; the only conflict was the NC-021 row and it is resolved to a single entry. |
| `docs/numerical-claims.md` | NC-021 value `370`, source commit `8176d79`, `Last verified` 2026-09-08 — measured on the merged tree, with the superseded `290` kept in the Notes chain rather than erased. |
| `docs/implementations/2026-09-07-payload-digest-parameter-dates.md` | The two places that cited `290 pass at 0a4271b` now cite `370 at 8176d79`, and say plainly that the earlier figure measured the pre-merge base; both `calibration-data` reproduction blocks now pin `ca5b23b` instead of the branch tip, which no longer serves the collision file. |
| `docs/implementations/2026-09-08-pr80-review-nc021-remeasure.md` | This record. |

No file under `src/`, `scripts/` or `tests/` is touched by this round. The
digest fix Burak approved is byte-for-byte what it was at `14d54af`.

## Implementation approach

**Merge, not rebase.** `main` was merged into the branch, following the
precedent of `9435157`, `764f9c8` and `50ca31d`. A rebase would have produced a
linear history at the cost of rewriting all four published PR-#80 SHAs, and
this project pins SHAs in runbooks and in register rows — `0a4271b` is cited in
the register's own Notes column. Rewriting them turns every such citation into
a dangling reference. The merge leaves them resolvable.

**Two commits, because a commit cannot name its own hash.** Rule 6 asks the PR
that changes what a command returns to update the row in the same commit, but
the tree that changes the count here *is* the merge, and its SHA does not exist
until it is written. The repository already has a settled answer to this: the
code commit is the measurement point and a docs-only commit records the result
naming it — `947fe3d` then `6f8fb45` ("NC-021 to 280 at 947fe3d"), `5397bb6`
then `adc2cd3` ("NC-021 to 360 at 5397bb6"). This round follows the same shape:
`8176d79` is the merge and the measurement point, and the docs commit records
`370` against it. Only `docs/` changes after `8176d79`, so the figure still
describes the branch tip.

**One row, not two.** Both sides of the conflict had edited the same NC-021
line away from `280`. Keeping both — one row per branch — is the duplicate
identifier defect that `scripts/check_ids.py` rule N1 was written to catch, so
the conflict was resolved down to a single row carrying main's `360` at
`5397bb6`, which the follow-up commit then supersedes with the measured `370`.
`python scripts/check_ids.py` passes on the result.

**Supersede, do not overwrite.** `290` and `0a4271b` still appear in both the
register Notes and the implementation doc, labelled as measuring the pre-merge
base. Register rule 5 keeps retired claims for the audit trail; the same
reasoning applies to a superseded figure inside a live row. A reader who finds
`290` quoted somewhere else must be able to see what it measured and why it no
longer holds, rather than find it silently gone.

**Edited in place, not appended.** The append-only convention covers dated
snapshots under `docs/roadmap/` and `docs/state-of-the-project/`, whose filename
date is a claim about when the content was true.
`2026-09-07-payload-digest-parameter-dates.md` has never been on `main` — it is
an unlanded draft inside this PR, and its `What changed` manifest is a list of
what the PR touches rather than a frozen measurement, so its stale figures are
corrected in place with the supersession noted. The doc carries no "sections
above are left unedited" sentence to narrow.

## Mathematical / Statistical details

The only arithmetic is a count, but the distinction between measuring it and
deriving it is the whole point of Burak's finding.

Let `T(c)` be the number of tests `pytest` collects from `tests/` at commit `c`.
The tempting derivation is additive:

```
T(8176d79) =? T(645b4d1) + [ T(14d54af) - T(7d39a2b) ]
           =  360        + [ 290        - 280        ]
           =  370
```

This holds only if the two branches' test sets are disjoint and neither renames,
moves, parametrises or deletes a test the other also touches. That premise is
exactly what failed on `main` this cycle: #69 first measured `352` at `fd9bb0d`,
then the review fix *removed* 40 synthetic-trainer tests and *moved* the rest to
`tests/training/`, landing at `356` — a delta no addition of per-branch counts
would have predicted. Additivity is an assumption about a merge, not a property
of one.

So the row records a direct measurement. The arithmetic above is written only to
show that the measurement and the naive sum happen to agree here, which is
evidence the merge introduced no collision — not the source of the value.
NC-021's Notes carry the standing instruction "direct measurement, never a
branch-count derivation" for this reason.

Two counts are taken, not one, because they can disagree and the disagreement is
informative:

- `pytest tests/ --collect-only -q -o addopts=""` — 370, the number of tests the
  suite *contains*. `-o addopts=""` strips the repo's coverage defaults so the
  tail line is a bare count.
- `pytest tests/ -q` — 370 passed, the number that *ran and passed*.

They match here. They do not have to: `tests/test_file_snapshots.py` contributes
9 tests that `skip` when `git` or `bash` is absent, so a machine lacking either
collects 370 and reports `361 passed, 9 skipped`. That decomposition is recorded
in the row so a verifier seeing 361 can tell a skip from a regression, which is a
distinction a single number cannot carry.

## Design decisions

**Why not just take main's 360 and be done.** It is the most recent *verified*
value in the register, so it looks safe. It is not: the merged tree contains
this branch's 10 new digest tests, so `360` would be wrong at `8176d79` by
exactly the amount PR #80 adds — the same class of error as the `290`, in the
other direction. Rule 6 asks for the value the command returns on the merged
tree, and nothing else answers that.

**Why not defer the measurement to CI.** CI runs the suite on every push and
would report the count. But CI runs on GitHub's merge ref, not on the branch
tip, and its log is not a durable citation — the register needs a commit a
reader can check out. A local run at a named SHA is auditable years later; a
green check is not.

**Why the local run is still labelled provisional.** Per the team's standing
rule, no figure produced on Mert's laptop is authoritative. `370` is a laptop
measurement and is offered as such; the runbook posted to the PR asks Burak to
reproduce it on the desktop baseline, and his transcript is what makes the row
authoritative. The runbook's expected values are written to be self-consistent
(NC-021's own recorded value compared against a live `--collect-only` in the
same checkout) rather than as bare absolutes, so that if this figure is wrong
his run surfaces it as a mismatch instead of silently agreeing.

## Verification

All at `8176d79`, on `C:\sc-venv` (Python 3.12.10, pytest 9.0.3), Windows 11.
**Provisional — laptop, pending Burak's desktop run.**

```bash
python -m pytest tests/ --collect-only -q -o addopts=""   # 370 tests collected
python -m pytest tests/ -q                                # 370 passed in 43.14s
python scripts/check_ids.py                               # no duplicate or colliding identifiers
ruff check .                                              # All checks passed!
ruff format --check .                                     # 53 files already formatted
mypy --strict src/superconducted                          # no issues in 25 source files
```

The digest behaviour Burak approved is unchanged by the merge; the pair from the
run that produced the false collision still resolves the same way:

```bash
git fetch superconducted-noise-engine calibration-data
git show ca5b23b:snapshots/2026-08/ibm_fez/20260813T220506000000Z.json > archived.json
git show ca5b23b:collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json > new.json
python scripts/canonical_snapshot_digest.py --compare-reread new.json archived.json   # exit 0 - duplicate-partial
python scripts/canonical_snapshot_digest.py --compare         new.json archived.json   # exit 1 - live/live safety preserved
```

Both reads name `ca5b23b`, the backfill commit that wrote the collision file,
because the branch tip no longer serves it — see the next section.

The strongest form of this check is differential, and it needs no absolute at
all. Run the same pair through the digest as `main` ships it and as this branch
ships it:

| digest under test | `--compare-reread` | `--compare` |
| --- | --- | --- |
| `git show origin/main:scripts/canonical_snapshot_digest.py` | `1` — the false collision | `1` |
| this branch at `4486326` | `0` — `duplicate-partial` | `1` |

Reproduced end to end on 2026-09-08 in a throwaway `--filter=blob:none` clone.
Only the top-left cell may change between the two rows; a run where the branch
also returns `1` on the left means the fix did not take, and one where either
row returns `0` on the right means it over-reached.

## Defect found while testing the runbook

The Verification section of
`docs/implementations/2026-09-07-payload-digest-parameter-dates.md` told a
reader to fetch both documents from the **tip** of `calibration-data`. That was
true when it was written and is not true now: `1996bf6` removed the spurious
collision file from the branch — a removal the same PR performed and recorded —
so the second `git show` fails with

```
fatal: path 'collisions/2026-08/ibm_fez/20260813T220506000000Z.d6f9532e37a0da84.json'
does not exist in 'superconducted-noise-engine/calibration-data'
```

and the reproduction stops there. Nobody had run those lines since the data
branch was cleaned, so the PR's own headline evidence was unreproducible as
written while the PR sat open.

Both call sites in that document, and the one above, now pin `ca5b23b`. The
snapshot blob is byte-identical at the tip and at `ca5b23b` (`0db0b0d`); the
collision blob is `234500d`. They are read with `git show` rather than by
checking the branch out, because `core.autocrlf` rewrites the data branch on
checkout and the digest hashes those bytes.

The general lesson: a verification step that reads a mutable ref has a
shelf life. Pin the commit, exactly as the register requires a measurement to
name the commit it was taken at.

The self-consistency check that makes this round's finding impossible to repeat
silently — the register's recorded count against a live collection in the same
checkout:

```bash
grep -o "Full test-suite size | [0-9]*" docs/numerical-claims.md
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1
```

Both must name the same number. If they ever diverge, the row is stale and
Rule 6 has been missed again — report the mismatch, do not edit either side to
match the other.

## Related docs

- `docs/numerical-claims.md` — NC-021, and Rules 3, 5 and 6
- `docs/implementations/2026-09-07-payload-digest-parameter-dates.md` — the
  change under review; its Verification section carries the corrected figure
- `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md` — the
  `152 passed` false expectation this discipline came from
- `scripts/check_ids.py` rule N1 — the duplicate-row defect the conflict
  resolution avoids
- Issue #53; PR #55; PR #69 (`352` → `356` → `360`); PR #80
