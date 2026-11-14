# 2026-11-09: phase-4-records-and-redate

## Problem / Motivation

Four records fell behind on 2026-11-09. NC-021, the test-suite size, still read 1053 after PRs #133 and #135 merged
with new test files; Rule 6 requires a measurement at each merge commit, recorded in a following docs-only change. The
status snapshots of 2026-11-04, 11-07 and 11-09 existed only in session worktrees, so the next status run had nothing
on `main` to diff against. Plan section 8.4 still put L1 (job 1 of #125) in the week of 2026-11-04, which passed with
the freeze still blocked. Phase 3's milestone, due 2026-10-31, still had seven open issues and PR #111 with no
decision recorded on any of them.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | NC-021 becomes 1138 at `d929424a` (PR #135's merge), with 1082 at `3e5703b4` (PR #133's merge) and the 1053 that held through PR #141's merge recorded in its narrative. |
| `docs/status/2026-11-04-status.md`, `2026-11-07-status.md`, `2026-11-09-status.md` | The three snapshots, unchanged from the sessions that wrote them. |
| `docs/roadmap/2026-10-23-phase-4-plan.md` | A dated note under section 8.4 that ties L1 to the freezing commit instead of a week, and a new Appendix A.7 with the phase-3 triage for the lead's approval. |
| This document | The record. |

## Implementation approach

**NC-021.** Both counts were measured directly at their merge commits in throwaway trees from the exact-pin
interpreter, `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` and `python -m pytest
tests/ -q -p no:cacheprovider`, and CI's figures on the same commits were read from their runs. The row's value
column, command column and date move to the newest merge; the older values go into the narrative, as earlier entries
did. `6d64f64b` and `19cbe70f` were collected as well, to show the 1053 still held until PR #133.

**The snapshots** were copied byte for byte. They are dated documents and are not edited.

**Section 8.4** gets an appended "as of" note. The table above it is not edited.

**A.7** comes from a read-only audit of each phase-3 issue against `main` at `d929424a`. Its load-bearing claims were
re-checked before writing: the three ADR statuses, the workflow and script lines, the comment counts on #104 and #108,
the two comments it cites (6140571135, decision B; 5885407524, section 4), and the register's rule list.

## Mathematical / Statistical details

N/A: purely records. No figure here is derived; each count is a direct collection at a named commit, and the sums
written beside them say so.

## Design decisions

- **L1 as an event, not a week** (the lead's choice): a new fixed week would go stale like the last one, because the
  freeze waits on reviews and a desktop run whose dates nobody controls.
- **Both NC-021 values in one PR**: the two merges came hours apart, and the lead chose to batch them; each value names
  its own commit, which is what Rule 6 requires.
- **The triage is a table, not actions**: closing an issue is an outward step; A.7 proposes, and the lead decides.
- **PR #111 is not triaged here**: a separate session prepares its merge, close or split recommendation.

## Verification

```bash
git show d929424a:docs/numerical-claims.md >/dev/null   # the base this edits
grep -n "^| NC-021 | Full test-suite size | 1138 |" docs/numerical-claims.md
python scripts/check_ids.py
ruff format --check .
```

To reproduce the counts: check out `3e5703b4` and `d929424a` in throwaway trees and run the two pytest commands
above with `PYTHONPATH=src` on the exact pins; CI runs 42577736972 and 42607022579 hold the runner's figures.

## Related docs

- `docs/roadmap/2026-10-23-phase-4-plan.md`, sections 8.4 and Appendix A.
- `docs/status/2026-10-28-status.md` (the previous snapshot on `main`).
- PRs #133, #135, #141, #144; issue #125.

## Update, 2026-11-11: three more merges, and ADR-030 enters the ledger

Everything above is left as written on 2026-11-09. This section records what the branch gained before its
review.

### Problem / Motivation

`main` moved three times within 45 minutes on 2026-11-10 UTC, after this PR was opened: PR #144 merged as
`2dd78b15`, PR #146 as `21b2f172` and PR #136 as `cd277a64`. Two records fell behind again.

- **NC-021.** This branch said 1138 at `d929424a`. PR #136 adds tests, so `main` now collects 1177, and Rule 6
  wants each merge measured at its own commit.
- **ADR-030.** PR #136 closed Issue #75, whose sixth acceptance criterion asks for the decision to be recorded.
  The decision existed only as `docs/decisions/drafts/ADR-030-kraus-projector-boundary.md`, still reading
  "Draft. Requires approval from both owners", and `docs/decisions.md` had no ADR-030. The primary owner's review
  of PR #136 (5849593436) asked two things that no merged file answered: one consequence the draft does not list,
  and where the ADR moves.

The lead chose to put ADR-030's promotion in this PR instead of a PR of its own.

### What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | NC-021 becomes 1177 at `cd277a64` (PR #136's merge); the narrative gains the 1138 that held through `2dd78b15` and `21b2f172`, and the list of open PRs that add tests as of `cd277a64`. |
| `docs/decisions.md` | A new entry, ADR-030, Status Accepted: the draft's Context, Decision and Consequences copied as written, a note giving the basis of the acceptance, a note on the missing ADR-029, one added Consequences bullet marked as added, and a Source paragraph. |
| `docs/decisions/drafts/ADR-030-kraus-projector-boundary.md` | A dated status line appended; the draft's text is untouched. |
| This document | This section. |

The branch also carries a merge of `main` at `cd277a64` (`34d96513`), needed because the ADR-030 draft arrived
with PR #136.

### Implementation approach

**NC-021.** The row's own two commands were run at the merge commits in a throwaway tree from the exact-pin
interpreter (Python 3.12.10, NumPy 2.4.4, Qiskit 2.4.1, Aer 0.17.2, pytest 9.0.3, `PYTHONPATH=src`):

| Commit | What merged | Collected | Passed (laptop) | CI on that commit |
| --- | --- | --- | --- | --- |
| `2dd78b15` | PR #144, two docs files | 1138 | not run | run 42919239934: 1137 passed, 1 skipped, both legs |
| `21b2f172` | PR #146, 45 docs files | 1138 | not run | run 42924410277: 1137 passed, 1 skipped, both legs |
| `cd277a64` | PR #136, three test files touched | 1177 | 1177, no skip, 458 s | run 42925361559: 1176 passed, 1 skipped, both legs |

The value column, the commit in the command column and the date move to `cd277a64`. The older values stay in
the narrative, as before. The clause listing the open PRs that add tests was written on 2026-11-09 and names
PR #136; it is left as written and a new clause after it gives the list as of `cd277a64`.

**ADR-030.** The ledger entry was assembled by a short script and not typed. The script copies the draft from
its `**Context**` line to its end byte for byte, and adds only the `##` heading, the status block, one bullet
and the Source paragraph. A check after the run confirmed that the draft's body is a substring of the ledger.

The added bullet is the primary owner's first note, checked in the code before it was written:

- `KrausChannelProjector.project()` raised `ValueError` for a vector shorter than two entries before PR #136
  (`kraus.py` line 129 at `21b2f172`) and still does (line 121 at `cd277a64`).
- `FuzzyNoiseModel.prepare()` caught `(NotImplementedError, ValueError)` at `21b2f172`
  (`aer_factory.py` line 349) and catches only `NotImplementedError` at `cd277a64` (line 357).
- `test_prepare_propagates_invalid_projector_parameters` has the `[0.1]` case
  (`tests/test_noise_gate_eligibility.py` line 111 at `cd277a64`).

Her second note, where the ADR moves, is answered by this entry. The ledger's precedent is ADR-027: its entry
became Accepted in PR #120 and its draft file stayed in `drafts/`. The same is done here, with a dated line
appended to the draft so that it no longer reads as awaiting approval.

### Mathematical / Statistical details

N/A: records. No count is derived. 1138 + 39 = 1177 is written beside the value as a cross-check and the row
says the value is the direct collection.

### Design decisions

- **"Accepted", on the draft's own condition.** The draft names its condition: approval from both owners of
  the LOCKED module. The primary owner approved PR #136 at `76ab3950` (review 5849593436) and the secondary
  owner wrote the draft and the change. The status block states that basis as facts with their ids. Leaving the
  entry "Open", as ADR-028 still reads after its own merge, was the alternative; it was not taken because the
  condition is met and Issue #75 is closed on it.
- **The draft's text is copied, not rewritten.** Its author is the secondary owner, and a reworded decision
  would be a different decision from the one both owners approved. The one addition is marked as added, with the
  review it came from.
- **ADR-030 lands before ADR-029.** ADR-029 is a draft on `main` and PR #150 proposes its ledger entry. Ids are
  claimed at merge time (`docs/team.md`), and PR #136 merged first. A note in the entry says so. PR #150 also
  appends to the end of `docs/decisions.md`, so whichever of the two PRs merges second resolves that by hand.
- **Issue #75's criterion 6 also names "the target ADR where applicable".** ADR-030's text cites ADR-012 and
  ADR-008 and does not mention ADR-027. This record does not add such a sentence: whether the training target is
  affected is the owners' statement to make.
- **One heading keeps the ledger's dash.** Every `## ADR-NNN` heading in the ledger uses the same separator and
  `scripts/check_ids.py` parses the heading; the new one follows them.

### Verification

```bash
grep -c "^| NC-021 | Full test-suite size | 1177 |" docs/numerical-claims.md
```

Expected: `1`. This replaces the `1138` grep in the Verification above, which described the branch before this
update.

```bash
python scripts/check_ids.py
```

Expected: `No duplicate or colliding ADR / NC identifiers.`

```bash
git diff cd277a64 -- docs/decisions.md | grep -c "^-[^-]"
```

Expected: `0`. The ledger only gains lines.

```bash
diff <(sed -n '/^\*\*Context\*\*/,$p' docs/decisions/drafts/ADR-030-kraus-projector-boundary.md | head -n 34) \
     <(sed -n '/^## ADR-030/,$p' docs/decisions.md | sed -n '/^\*\*Context\*\*/,$p' | head -n 34)
```

Expected: no output. The 34 lines of the draft's body, from its Context to its last Consequences bullet, are
the same 34 lines in the ledger entry.

To reproduce the counts: check out `2dd78b15`, `21b2f172` and `cd277a64` in throwaway trees and run the row's
two pytest commands with `PYTHONPATH=src` on the exact pins. The full run was made only at `cd277a64`.

### Related docs

- PRs #136, #144, #146, #150; Issues #75 and #58.
- Reviews 5849593436 (the primary owner, PR #136) and 5822740472 (the lead, PR #136).
- `docs/decisions/drafts/ADR-030-kraus-projector-boundary.md`; `docs/team.md` (ids are claimed at merge time).

## Update, 2026-11-14: PR #137's merge, and the reviews that asked for it

Everything above is left as written on 2026-11-09 and 2026-11-11. This section records the one change made
after the first reviews.

### Problem / Motivation

PR #137 merged as `667972c5` on 2026-11-11 at 22:25 UTC, after the 2026-11-11 update above was pushed. It adds
cases to `tests/test_anfis.py`, so `main` collects more tests than the 1177 this branch recorded at `cd277a64`.
Both reviews asked for the row to follow: Burak Öztekin's CHANGES_REQUESTED (5866804903) asks for NC-021 to be
re-measured at the latest merge commit, with 1177 kept as a past measurement and CI's skip stated apart from the
local run; Bengisu Cıvdı's COMMENT (5903195666) agrees and finds nothing to change in ADR-030.

### What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | NC-021 becomes 1203 at `667972c5` (PR #137's merge), with one clause appended to its Notes; the 1177 clause stays as the measurement of `cd277a64`. |
| This document | This section. |

The branch also carries a merge of `main` at `667972c5` (`a50be41d`). The merge was clean; its `src` and
`tests` trees are the same objects as `667972c5`'s.

### Implementation approach

The row's own two commands were run at `667972c5` in a throwaway tree (`git worktree add --detach`) from the
exact-pin interpreter (Python 3.12.10, NumPy 2.4.4, Qiskit 2.4.1, Aer 0.17.2, pytest 9.0.3, `PYTHONPATH=src`,
`superconducted.__file__` checked to resolve inside the throwaway tree):

| Commit | What merged | Collected | Passed (laptop) | CI on that commit |
| --- | --- | --- | --- | --- |
| `667972c5` | PR #137, `tests/test_anfis.py` | 1203 | 1203, 567 s | run 43111626183: 1202 passed, 1 skipped, both legs |

The skip on CI is the archive-backed survey test, whose skip message asks for the `calibration-data` ref to be
fetched first; the laptop run could read that ref, so the test ran. The value column, the commit in the command
column and the Last verified date move to `667972c5` and 2026-11-14. The clause that listed the open PRs adding
tests as of `cd277a64` names PR #137; it is left as written, and the new clause gives the list as of `667972c5`.

### Mathematical / Statistical details

N/A: records. No count is derived. 1177 + 26 = 1203 is written beside the value as a cross-check, and the row
says the value is the direct collection.

### Design decisions

- **Measure `667972c5`, not this branch's merge.** NC-021 describes `main`. This branch changes only `docs/`, and
  its merge `a50be41d` has the same `src` and `tests` trees as `667972c5`, so the two collect the same suite. The
  row names `main`'s commit, which stays meaningful after this PR merges, as the earlier entries do.
- **CI is cited, not adopted.** The row's value is the collected size. CI's 1202 passed and 1 skipped is written
  as CI's, beside the laptop's run, as the review asked; neither replaces the other.

### Verification

```bash
grep -c "^| NC-021 | Full test-suite size | 1203 |" docs/numerical-claims.md
```

Expected: `1`. This replaces the `1177` grep in the 2026-11-11 Verification above.

```bash
git rev-parse a50be41d:tests 667972c5:tests
git rev-parse a50be41d:src 667972c5:src
```

Expected: each pair prints the same object id twice.

```bash
python scripts/check_ids.py
```

Expected: `No duplicate or colliding ADR / NC identifiers.`

To reproduce the count: check out `667972c5` in a throwaway tree and run the row's two pytest commands with
`PYTHONPATH=src` on the exact pins.

### Related docs

- PRs #137 and #145; Issue #60.
- Reviews 5866804903 (Burak Öztekin) and 5903195666 (Bengisu Cıvdı) on PR #145.
