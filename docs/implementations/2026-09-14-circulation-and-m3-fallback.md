# 2026-09-14: advisor circulation, the FR-10.4 comparison, and the M3 ledger fallback

## Problem / Motivation

Issue #56 was audited against `main` at `004e14e` on 2026-09-14. Its W1 and W2 work is
done: #51, #52 and #55 merged, #53's recovery executed and closed, #45 and #25 closed with
their mappings, the cycle-2 close record merged, the conventions and advisor record landed,
branch hygiene complete, the floor derived and registered. What remained was not evenly
distributed between "done" and "waiting for a milestone".

**One item was neither.** FR-12's batched advisor message has never been sent. The package
has been ready since 2026-09-09 and complete since 2026-09-10, and on 2026-09-14 no version
of it has reached Dr. Akba. Issue #84's definition of done still carries
`@mertefesensoy has sent it to Dr. Akba` unchecked. The register's own decision-by dates
for items 1, 2, 10 and 12 were 2026-09-16, set on the assumption of a 2026-09-09 send, so
the slip had quietly converted a seven-day window into a two-day one without anyone
recording that it had happened. That is the exact failure mode this requirement exists to
prevent: the 2026-05-25 questions went unanswered for three months the same way.

Three smaller gaps travelled with it:

1. **FR-10.4 was neither made nor deferred.** The floor landed at 1170 in PR #87, but the
   comparison against the archive's distinct-state count at the then-current ref was not
   written, and neither was the `to be measured, #63` marker FR-10.4 prescribes when #63's
   row does not exist. The floor doc compares against NC-025's 504 at `f0930b9`, which
   FR-10.4 explicitly rules out as a current-ref count.
2. **FR-13's re-check had gone stale.** Five issues filed after the 2026-09-09 check
   carried no milestone.
3. **FR-15 and FR-16 had no ledger form at all.** Both allow a fallback that can be written
   before the decision exists, and neither had been written, so ADR-009 and ADR-011 read
   `Open` on `main` with nothing saying who owed what or by when.

This PR closes every one of those that does not require a future milestone or another
person's work. It changes no executable line.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-09-14-akba-batch-cover.md` | *new* · the Turkish plain-text e-mail that **is** the batched request, verbatim: where the project stands, what is missing, what landed since 2026-05-25, and all fourteen questions as single sentences with a date each. Nothing is attached. |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | *append* · `## Circulation, as-of 2026-09-14`: the unsent-batch record, the revised dates with a reason per change, and the two-item coverage audit. Nothing above the append marker is touched. |
| `docs/numerical-claims.md` | *modify* NC-045 · re-verified at `004e14e`, plus the FR-10.4 comparison against NC-047 and the `to be measured, #63` marker. *modify* NC-021 · Rule 6 confirmation that 465 survives the merge at `004e14e`. |
| `docs/decisions.md` | *append* · a dated status block under ADR-009 (FR-15's second form) and one under ADR-011 (FR-16's second form). Neither `**Status**` line is changed. |
| `docs/implementations/2026-09-14-circulation-and-m3-fallback.md` | *new* · this document. |
| GitHub `Phase 3 · ANFIS results` milestone | #54, #66, #73, #74, #75 and #93 attached (FR-13 re-check). Every open issue is now attached except #65 and #76, both phase 4. |

## Implementation approach

**The message is one plain-text e-mail and nothing is attached.** The six HTML files of
`docs/advisor/2026-09-09-akba-brief/` stay internal. They were drafted as an attachment
cluster and that plan was dropped on 2026-09-14, before anything went out, which is the
only window in which dropping it costs nothing.

The reason is not presentation, it is the failure being fixed. Dr. Akba has never answered
a question from this project. The 2026-05-25 set failed because it was spread across
thirteen places and none of them was a message he could reply to; opening the replacement
with six styled HTML attachments repeats the shape of that failure in a tidier form, since
it asks him to open an archive before he can read a sentence. So every question is in the
body, in one sentence, with its own date, and the detail is offered on request.

The cluster is not wasted and is not deleted. It is where each question's full argument was
worked out, and that work is what makes the one-sentence form defensible rather than glib:
a question you can state in one line because you understand it reads differently from one
stated in one line because you have not thought about it. If he asks for one item's
background, that file goes out on its own as a separately dated document. The cluster is
left byte-identical, and PR #94's one-time exception for appending File 06 is not spent
again.

**The revised dates are reasoned per item, not shifted uniformly.** A uniform five-day
shift would have pushed the M3 group past M3's own gate, which converts a deadline into a
formality. The three distinct cases are in the register's table; the short form is that the
pre-M3 group moves to preserve its seven-day window, the M3 group does not move and absorbs
the cost as a shorter window, and ADR-014 moves *earlier* for a reason unrelated to the
slip.

**The two coverage gaps stopped mattering, but the audit still did its job.** Searching
every file of the cluster for each item's own identifiers found that `MembershipFunction`
appears in none of them and `ADR-014` only in `index.html`'s calendar, so items 12 and 5
carried a decision-by date that nothing argued. Once the cluster is not sent, no question
leans on an attachment and the gap closes by construction: item 12 is question 6 and item 5
is question 13, in the same one-sentence form as the other twelve. The audit is recorded
anyway, because it is the check that would have caught two unanswerable asks had the
original plan gone out, and because item 5 still needs its 2026-09-26 framing as *what will
be ready then* rather than as a ratification of a trainer that does not exist.

**The ADR blocks use the ADR-025 precedent.** PR #94 established the shape for recording an
unratified amendment in the ledger: a dated `###` sub-block under the ADR, a small table of
circulated / recorded-in / decision-by / owner, and an explicit statement of what does and
does not clear it. Both new blocks follow it, and both are careful to leave the
`**Status**` line alone, because FR-15 and FR-16 route decisions and do not take them.

**FR-15's fallback is recorded as incomplete, deliberately.** Its wording is "recorded as
still Open with the date the request went out". There is no such date. Rather than write
the preparation date in a slot that means the send date, the block carries a `NOTE` callout
saying the date does not exist, where the send will be recorded, and that the block is
unfinished until it is. A fallback that is satisfied by a request nobody sent is worse than
no fallback.

## Mathematical / Statistical details

**The floor, re-verified.** For a `from_grid` rule base with `R` rules, input dimension
`d`, output dimension `k`, and `U` unique membership-function objects of `p_j` parameters
each:

```
count = k * R * (d + 1)  +  sum_j p_j
```

Re-run at `main` @ `004e14e` on the configuration in use (`R = 27`, `d = 3`, `k = 2`,
`U = 9`, `GaussianMF` so `p = 2`):

```
count = 2 * 27 * 4 + 9 * 2 = 216 + 18 = 234
floor = 234 * 5 = 1170
```

`count_trainable_parameters` returns `ParameterCount(premise=18, consequent=216,
total=234)`, identical to the 2026-09-09 measurement at `5f935ea`. Between those two
commits `main` took **66 commits over 14 merges, 10 of them pull requests**
(`git rev-list --count 5f935ea..004e14e`, `--merges`, and the `Merge pull request` subset),
and none of them moved the count. That is the check Rule 6 asks for, and the reason
NC-045's `Last verified` advances while its value does not.

**The FR-10.4 comparison.** With the floor at 1170 and NC-047's 563 distinct device states
at `calibration-data` @ `c63ce21`:

```
563 / 1170 = 0.4812        (fraction of the floor)
563 /  234 = 2.4060        (samples per trainable parameter, against the 5 assumed)
```

The gate is not met, by roughly a factor of two. For orientation only, the same arithmetic
on NC-025's older 504 at `f0930b9` gives `0.4308` and `2.1538`, so the archive has moved
toward the floor and remains far below it. **The 504 is not used for the registered
comparison**: it predates the 2026-09-10 digest definition change and is not a current-ref
count, and substituting it would be exactly the reuse NC-R001 exists to prevent.

**Why 563 settles the direction but not the audit.** NC-047 is issue #48's measurement at a
ref chosen for the pipeline-health dashboard, not #63's at the ref its training-set builder
pins. The two questions differ: "is the archive below the floor" is answered by any honest
current count, and "which rows did the training set actually draw from, and how many
distinct states were in them" is answered only by the ref the builder reads. The first is
answered here; the second stays marked `to be measured, #63` and lands in the M4 close
record, per FR-10.4's own instruction for the case where #63's row is not yet available.

## Design decisions

**Attaching five issues to the milestone, and not a sixth.** The rule applied is the one
the phase-3 plan already uses for #65 and that #76 states in its own title: everything
filed for this phase is attached unless it is explicitly designated phase 4. #66 declares in
its own body that it blocks work "which phase 3 does throughout"; #73, #74 and #75 are
spin-offs of #58's certification, and #73 already has an open PR; #93 is a live defect
inside #49's daily sweep, which is an M2 gate item.

**#54 is attached, on the lead's call.** It was initially held back and the reasoning is
recorded here because the argument against it is real and someone will raise it again: #54
is a standing research finding about the polling design's ~70% capture rate, it appears in
no lane of the phase-3 plan's §4 table, and nobody owns it, so attaching it makes the
milestone assert work no one has undertaken. The lead weighed that and attached it anyway,
which is the right call on the criterion that actually governs: UC-13 asks for **every
filed phase-3 issue attached except #65**, and #54 is a phase-3 issue. A milestone is the
tracking object for what the phase must reckon with, not a roster of what is assigned.

It also matters more than its lack of an owner suggests. #54 measures the second binding
constraint on the dataset, and the dataset is what FR-10.4 above compares against the
floor. An unowned issue that moves the archive's growth rate belongs where the phase can
see it.

**After this, the milestone is exactly UC-13's condition.** The only open issues without it
are #65, which the phase-3 plan's §4 designates phase 4, and #76, which says "Phase 4" in
its own title.

**NC-045 is edited rather than superseded by a new row.** The value did not change, so
Rule 5's retirement path does not apply and a new id would register the same measurement
twice. Rule 3 covers re-verification directly: update the date when someone opened the
source and confirmed the value, which is what happened. The FR-10.4 comparison goes into
that row's Notes rather than into a row of its own because it is arithmetic over two
already-registered figures at named refs, which is the same form NC-025's Notes use for
`504 / 234`.

**NC-021 is annotated rather than changed.** Its 465 was measured at `d7ccb8c`, a branch
commit that PR #95 merged. The merged tree at `004e14e` collects 465 as well, so the value
stands and only the confirmation is recorded. This PR touches no test, so it had no
independent reason to open the register; it opens it anyway because a docs-only PR that
cites a count still owes the check that the count describes the tree that will be merged.

**What was considered and rejected:** flipping ADR-009's status to match the provisional
`Prefer IT2` reading in its own Decision (current) line. That would convert a provisional
preference into a ratified decision without the ablation, the memo, or the advisor, and
Issue #56 §1.2 forbids this ticket from taking the decisions it routes.

## Verification

At `main` @ `004e14e` with the working tree of this branch, in a clean Python 3.12
interpreter:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/ --collect-only -q -o addopts=""
python -m pytest tests/ -q
PYTHONPATH=. python scripts/check_ids.py
```

Expected, and measured on 2026-09-14:

| Check | Result |
| --- | --- |
| `ruff check` | `All checks passed!` |
| `ruff format --check` | `60 files already formatted` |
| `pytest --collect-only` | **465 collected**, equal to NC-021 measured at `004e14e` |
| `pytest` | **465 passed in 49.42s**, none skipped, none failed |
| `check_ids.py` | `No duplicate or colliding ADR / NC identifiers.` |

**Confirmed by CI, which is the authority.** PR #98 at `72cd567` ran all six checks green:
`test (3.11)` and `test (3.12)` on `ubuntu-latest` both report **465 passed** (`15.45s` on
3.12), alongside CodeQL and the two `Analyze` jobs. Every check run carries
`head_sha = 72cd567`, which is the check that matters here: this repository has a failure
mode where `ci.yml` does not dispatch on a conflicted PR while CodeQL keeps passing, so
green checks can mean no tests ran. They ran, on this code, and `main` was still at
`004e14e` at that moment, so the result describes the tree that will actually merge rather
than a superseded one.

The full run passing on Windows is worth one line, because the register's own NC-021 Notes
record 8 `tests/test_file_snapshots.py` failures on this platform from an earlier round.
They did not reproduce here. The interpreter is a clean CPython 3.12.10 at a short path
rather than the repository `.venv`, which is the reading those Notes already give them:
an environment artefact, not a platform one. `ubuntu-latest` remains the authority.

This PR is documentation-only and adds no test, so the collected count must be unchanged.
State it differentially: NC-021 records 465 at `d7ccb8c`, PR #95 merged that into `main` at
`004e14e`, and this branch collects 465 on top of `004e14e`.

The floor re-measurement:

```bash
PYTHONPATH=. python -c "
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.fuzzy.membership import GaussianMF
from superconducted.training.parameters import count_trainable_parameters
per_input = [[GaussianMF(center=c, sigma=0.15) for c in (0.2, 0.5, 0.8)] for _ in range(3)]
print(count_trainable_parameters(TSKRuleBase.from_grid(per_input, output_dim=2)))
"
# ParameterCount(premise=18, consequent=216, total=234)
```

> **NOTE · `mypy --strict` is not run here and the reason is environmental.**
> `pyproject.toml` pins `python_version = "3.11"`, and under a 3.12 interpreter mypy then
> rejects numpy's own stubs. This is pre-existing, unrelated to this branch, and identical
> on `main`. CI on `ubuntu-latest` is the authority.

> **NOTE · These measurements are provisional.** Per `docs/team.md`, canonical verification
> is @BurakOztekin's batched desktop record. This branch originates no new number: NC-045's
> 234 was already registered and is re-confirmed, and the FR-10.4 ratio is arithmetic over
> two existing rows.

## Related docs

- Issue #56 · FR-2, FR-10.4, FR-12, FR-13, FR-15, FR-16, NFR-2, NFR-3, NFR-4
- Issue #84 · the ADR-027 advisor loop that shares `docs/advisor/2026-09-03-decisions-from-akba.md`
- `docs/advisor/2026-09-03-decisions-from-akba.md` · `## Circulation, as-of 2026-09-14`
- `docs/advisor/2026-09-09-akba-brief/` · the six-file cluster, internal only, not sent
- `docs/decisions.md` · ADR-009 and ADR-011 status blocks; the ADR-025 amendment status block this follows
- `docs/numerical-claims.md` · NC-012, NC-021, NC-025, NC-045, NC-046, NC-047, NC-R001
- `docs/implementations/2026-09-09-training-floor-derivation.md` · the derivation FR-10.4 completes
- `docs/implementations/2026-09-10-adr-025-advisor-handoff.md` · the precedent for the ledger status block
- `docs/roadmap/2026-09-03-phase-3-plan.md` · §4 lanes and §5 M0 to M4 gate text
- Issues #60, #61, #62, #63 · the work FR-15, FR-16 and FR-10.4's canonical form wait on

## Rebase onto `125b796` · as-of 2026-09-16

Everything above describes the branch as it stood at base `004e14e` on 2026-09-14 and is
left unedited. This section records the rebase and the one place where a figure above was
superseded rather than merely re-confirmed.

### Why

The PR sat unreviewed from 2026-09-14 to 2026-09-16 while `main` took **37 commits**, one
of them a pull-request merge (#68, Issue #59's membership-function parameterization). That
made the PR `DIRTY`, and a conflicting PR does not get a fresh `ci.yml` run, so its green
checks described a base nobody would merge. The three commits were rebased onto
`main` @ `125b796`; nothing was squashed and no commit message changed.

### The conflict, and how it was resolved

`docs/numerical-claims.md`, two hunks, both created by PR #68's register work:

| Hunk | `main` side | This branch's side | Resolution |
| --- | --- | --- | --- |
| NC-021 row | `616`, measured at `7b36b8d` | `465`, plus an appended Rule 6 confirmation at `004e14e` | **`main` kept; this branch's edit dropped** |
| NC-041 .. NC-045 block | four new rows NC-041 .. NC-044, then the pre-PR NC-045 | the edited NC-045 alone | **both kept**: `main`'s four new rows, then this branch's NC-045 re-applied byte-identically |

The resolved file differs from `main` by exactly one line, the NC-045 row, which is what
this PR always intended to change.

**Why the NC-021 annotation was dropped rather than re-anchored.** The Design decisions
section above argues that a docs-only PR citing a count owes the check that the count
describes the tree that will be merged. That argument stands; its conclusion does not
survive the rebase. The 465 it confirmed at `004e14e` has since been superseded four times
over on `main` (587, 611, 616), and appending a 2026-09-14 observation of 465 to the end of
a Notes chain that already reads 616 would file an older measurement below a newer one and
read as a regression. The citation fix Rule 6 asks for on the current value is PR #101's,
which re-measures 616 at the merge commit `125b796` and touches the same row. Two open PRs
editing one row is how identifier and value collisions happen, so this branch yields the
row and keeps only NC-045.

### The values this PR consumes, re-checked at the new base

Rule 6 asks a number to name a commit it was measured at, and a rebase moves the commit the
PR will merge into. All three were re-checked at `main` @ `125b796`:

| Value | At `004e14e` | At `125b796` | Action |
| --- | --- | --- | --- |
| `count_trainable_parameters`, the configuration in use | `ParameterCount(premise=18, consequent=216, total=234)`, floor 1170 | **identical**, re-run in a clean CPython 3.12.10 | NC-045 Source cell and Notes record the third verification; value and `Last verified` moved together per Rule 3 |
| NC-047, distinct device states at `calibration-data` @ `c63ce21` | 563 | unchanged, no PR touched the row | FR-10.4's comparison stands as written |
| NC-012, the floor | 1170 | unchanged | no edit |
| NC-021, test-suite size | 465 | **616** | the two citations in the cover message corrected, below |

The parameter count is re-measured and not assumed: the only file the 37 commits add under
`src/` is `fuzzy/parameterization.py` (`git diff --stat 004e14e..125b796 -- src/`), which
`count_trainable_parameters` does not read, so the expectation was that it had not moved,
and the run is what confirms it. Canonical verification remains @BurakOztekin's batch
record; this is a laptop run and NC-045 still says provisional.

### The one edit made to a dated file, and why it is not an NFR-2 violation

`docs/advisor/2026-09-14-akba-batch-cover.md` cited NC-021 twice, once in its sourcing note
and once in the message body's own status list (`Test paketi: 465 test`). Both now read
616. That is an in-place edit of a dated document, which NFR-2 normally forbids, and it is
correct here for a reason that will not generalise: **the file has never been on `main` and
the message has never been sent.** Its own opening note states that it is the exact message
to be sent and that if what goes out differs from it in any way, the file is wrong and gets
corrected. An unsent draft is not yet a record of anything, so there is no history to
preserve; sending a message that quotes a register value the register no longer carries is
the failure NC-R001 exists to prevent. Once it is sent, the send is appended to
`docs/advisor/2026-09-03-decisions-from-akba.md` and the cover becomes append-only like any
other dated file.

### What was deliberately not re-run

Three classes of figure in the cover are anchored to a named ref or date and are therefore
still honest as written, so the rebase left them alone. They are listed here because the
send date decides whether any of them needs refreshing, and that decision is not this
rebase's to make:

1. **The archive figures** (1123 documents, 601 distinct states, 46.5% duplication, and the
   29 November projection) name `health/metrics.json` on `calibration-data` @ `272a0c5`,
   generated 2026-09-14T09:03:34Z. The archive grows hourly; the ref is what keeps the
   sentence true.
2. **The 37 / 35 merged-PR counts and the 11-of-26 Open/Deferred count** name `004e14e`.
   `main` has since merged #68, so both are one PR behind the live tree.
3. **The decision-by dates.** Items 1, 2, 10 and 12 carry 2026-09-21, calculated as seven
   days from an assumed 2026-09-14 send. Each day the message waits, that window shrinks;
   at a 2026-09-16 send it is five days. Re-dating them is a judgement about what to ask of
   Dr. Akba, not a mechanical refresh, so it belongs to the send and not to this rebase.
