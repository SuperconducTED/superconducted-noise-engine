# 2026-09-09: the cycle-2 close record, and repairing an append-only breach

## Problem / Motivation

Issue #56's M0 records work (FR-5, FR-7.2) plus the repair FR-1 asked for and did not get.

1. **Cycle 2 closed without a scorecard.** `docs/roadmap/2026-05-25-cycle-2-plan.md` set six
   goals. The cycle-2 plan's own `## Reconciliation update · as-of 2026-09-03` section says
   the close record exists "under `docs/state-of-the-project/`" and names issue #56 as its
   owner, but `docs/state-of-the-project/` held exactly one file, the 2026-05-25 bootstrap
   record. The pointer resolved to nothing.
2. **PR #52 removed four lines from a dated document and nobody said so.** #56 FR-1 asked
   for the deleted sentence to be restored before merging, or for the exception to be
   recorded knowingly in the merge comment. Neither happened: #52 merged with **zero
   comments** on the thread, and the deletion is live on `main`.
3. **The as-of pointer had no destination.** FR-7.2 asks for the close record's path to be
   appended to the cycle-2 plan's as-of section once the record merges.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/state-of-the-project/2026-09-09-cycle-2-close.md` | *New.* The six-goal scorecard derived from quoted ADR status lines, the re-derived merged-PR list, the ledger-movement table continuing the 2026-05-25 series, the data-integrity programme, and what cycle 2 taught about gates. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | Appends a `## Record repair · as-of 2026-09-09` section quoting back the sentence PR #52 deleted. No line above it is touched. |
| `docs/roadmap/2026-05-25-cycle-2-plan.md` | Appends the close record's path and its one-line verdict to the existing `## Reconciliation update · as-of 2026-09-03` section. |

No executable line changed.

## Implementation approach

**The scorecard is derived, not transcribed.** Each of the six goals is scored from the
`**Status**` line of its governing ADR, quoted verbatim from `docs/decisions.md` at
`5f935ea` and printed in the table beside the score. Issue #56 FR-5 offers an orientation
list of expected statuses; it is explicitly not used as the source, because a scorecard
that copies its classification from the ticket it is closing verifies nothing. The command
that produced the quotes:

```bash
for a in 009 014 015 016 018 019; do
  awk -v p="^## ADR-$a " '$0~p{f=1} f&&/^\*\*Status\*\*/{print;exit}' docs/decisions.md
done
```

**Goal 6 scores "partially met" for a reason that had to be checked rather than assumed.**
The goal was to align three locations on one aggregation contract. Two were aligned by
PR #81. The third, `scripts/first_ensemble_run.py::run_ensemble`, still mean-aggregates via
`round(v / n)`, and that is a **behaviour** difference rather than a wording one, so
aligning it would be an executable change that #56 forbids itself. Scoring the goal "met"
would claim an alignment that does not exist in the code.

**The merged-PR figures are measured at execution.** `gh pr list --state merged` filtered to
`mergedAt >= 2026-05-25` returns 27 today against the 17 the ticket recorded at filing, so
the query is re-run rather than the ticket's number carried. The documentation-only count is
computed from each PR's own `files` list rather than from the title:

```bash
gh pr list --state merged --limit 100 --json number,mergedAt,files \
  -q '[.[] | select(.mergedAt >= "2026-05-25")
       | select([.files[].path] | all(startswith("docs/"))) | .number] | length'
```

PR #43 was spot-checked by hand because "renormalize tracked text files to LF" reads like a
repository-wide change that a truncated `files` list would misclassify; it touches two
files, both under `docs/`, so the classification holds.

**The repair is an append, not a revert.** The removed sentence is quoted inside a new
dated section at the end of the 2026-08-29 document, not re-inserted into the paragraph it
came from. Re-inserting it would itself be an in-place edit of a dated document, which
repeats the defect being fixed. Quoting it restores the evidence without touching a line,
so both readings survive: what we believed on 2026-08-29, and the 2026-09-02 finding that
overturned its stated reason while confirming its practical conclusion.

## Mathematical / Statistical details

No new formula. Two arithmetic statements in the close record are traceable rather than
derived here:

- **The floor arithmetic.** NC-012's `>= 630` is "roughly 126 trainable parameters x 5".
  The 126 is underived; measured from the rule base at `5f935ea`, a 3x3x3 Gaussian grid at
  `output_dim = 2` carries 234 trainable parameters, reproducing NC-037. The close record
  states this and cites NC-037, and deliberately **does not register** the derived floor:
  that row is #56 FR-10's, in the M3 PR, per the next-free-id-at-merge-time rule.
- **The IT2 parameter delta.** `IntervalGaussianMF` adds one parameter per unique
  membership-function object, and `from_grid` shares 9 unique objects across 27 rules, so
  the delta is 9 rather than a doubling. The consequent term is `k * R * (d + 1) =
  2 * 27 * 4 = 216` of the 234 and is unaffected by the type. The per-shape counts behind
  this are measured but registered by the M3 PR, so the close record states the delta
  qualitatively and cites NC-037 for the only figure it prints.

Every other number in the close record resolves to an existing NC row, and each is printed
with the commit or archive ref it was measured at, per Rule 6.

## Design decisions

**Why `docs/state-of-the-project/` rather than `docs/roadmap/`.** Issue #56 §7 raises this
as an open decision. `state-of-the-project` holds retrospectives; `roadmap` holds forward
plans. `2026-05-25-bootstrap-to-cycle-1.md` is the precedent and is the same kind of
document. The roadmap files get pointers only.

**Why the ledger-movement table lives in the close record rather than as a third
reconciliation section on the 2026-05-25 state document.** FR-5 asks for the series to be
continued "inside the close record", and that file "is not edited". Adding a third
`## Ledger reconciliation` section there would have been consistent with the two existing
ones, but it would put 2026-09 content inside a document dated 2026-05-25, which is the
same category error the append-only rule exists to prevent at a coarser grain. The close
record names the series it continues and the dates it covers.

**Why PR #81's ADR-016 exception is recorded rather than reverted.** #81 rewrote ADR-016's
Context and `Decision (current)` lines, which #56 FR-6 Part 2 forbade and which issue #25's
own Part 2 acceptance criteria required. #81 followed the ticket it was closing. Reverting
would re-edit the ledger to satisfy a rule about not editing the ledger, and would put back
wording the code contradicts. The close record documents the conflict, names the residual
artefact (the 2026-05-25 note now opens by quoting wording that no longer appears above it,
which #81's own appended note acknowledges), and leaves it.

**Why the close record says "one of six met" without softening.** The alternative
considered was to score goal 1 as partially met, since the trainer's contract landed even
though the trainer did not. It was rejected: ADR-014 reads `Deferred`, the scorecard is
derived from that line, and a scorecard that finds reasons to upgrade its own scores is not
a record anyone can audit. The contract landing is stated in the row's notes instead.

## Verification

```bash
# 1. Append-only: neither dated document lost a line.
git diff main --numstat -- \
  docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md \
  docs/roadmap/2026-05-25-cycle-2-plan.md
# Expect the deletions column (second) to read 0 for both.

git diff main -- docs/roadmap/ docs/state-of-the-project/ docs/implementations/2026-08-29-*.md \
  | grep '^-[^-]' || echo "append-only clean"

# 2. The removed sentence is quoted back into the record.
grep -n 'probably nothing to backfill' \
  docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md

# 3. Every status line the scorecard quotes matches docs/decisions.md today.
for a in 009 014 015 016 018 019; do
  printf "ADR-%s: " "$a"
  awk -v p="^## ADR-$a " '$0~p{f=1} f&&/^\*\*Status\*\*/{print;exit}' docs/decisions.md
done
# Expect: 009 Open, 014 Deferred, 015 Deferred, 016 Deferred, 018 Accepted, 019 Open.

# 4. The merged-PR figures re-derive.
gh pr list --state merged --limit 100 --json number,mergedAt,baseRefName \
  -q '[.[] | select(.mergedAt >= "2026-05-25")] | length'                       # 27
gh pr list --state merged --limit 100 --json number,mergedAt,baseRefName \
  -q '[.[] | select(.mergedAt >= "2026-05-25") | select(.baseRefName != "main") | .number]'  # [39, 71]

# 5. Goal 6's third location really is untouched.
git diff main -- scripts/first_ensemble_run.py || echo "unchanged, as the record states"
grep -n 'round(v / n)' scripts/first_ensemble_run.py

# 6. Every NC id cited by the close record exists on main.
grep -o 'NC-[0-9R]*[0-9]' docs/state-of-the-project/2026-09-09-cycle-2-close.md \
  | sort -u | while read -r id; do
      grep -q "| $id |" docs/numerical-claims.md || echo "MISSING: $id"
    done; echo "traceability check done"

# 7. Unchanged against main.
ruff check && ruff format --check
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1
```

Step 7's collection count is stated differentially against NC-021 in the PR description,
citing the row rather than recalling a number, and is a **provisional** laptop run per
`docs/team.md`. This PR originates no number.

## Related docs

- Issue #56 FR-1 (item c), FR-5, FR-7.2; NFR-2, NFR-3
- `docs/roadmap/2026-05-25-cycle-2-plan.md` — the six goals scored
- `docs/roadmap/2026-09-03-phase-3-plan.md` — the M0 to M4 gate text the record cites rather than restates
- `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` — naming precedent and the ledger reconciliation series continued
- `docs/decisions.md` — ADR-009, ADR-011, ADR-014, ADR-015, ADR-016, ADR-018, ADR-019, ADR-024, ADR-025, ADR-027
- `docs/numerical-claims.md` — NC-012, NC-021, NC-025, NC-026, NC-029 to NC-034, NC-037, NC-R002
- PR #52 (the append-only breach and its thread), PR #81 (the ADR-016 exception), PR #85 (the conventions and advisor record)
