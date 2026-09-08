# Phase 3 tracker

A live status dashboard for phase 3 (*Results from ANFIS*, Sep 2 – Sep 30 2026), living
on an **orphan branch**. It shares no history with `main` and contains no project code,
so it can never conflict with, be merged into, or be picked up by anything on the
engineering branches. The only convention it follows is the one `calibration-data`
already set: data that belongs to the repo but not to the source tree lives on its own
root.

```
phase-3-dashboard   (orphan — this branch)
main                (the project; untouched by anything here)
calibration-data    (orphan — snapshots and ledger)
```

## What is here

| File | What it is |
| --- | --- |
| `plan.json` | The **static plan model**: milestones and their gates, owners, and every dependency edge — each one quoted from a ticket's own `Depends on` row on GitHub rather than inferred from the milestone table. Hand-maintained, and only when the plan or a ticket actually changes. |
| `generate.py` | Joins `plan.json` against **live GitHub state** and renders the outputs. Contains no status of its own. |
| `index.html` | The dashboard. Generated — do not edit. |
| `STATUS.md` | The same content as Markdown, for reading in a terminal or a PR. Generated. |
| `snapshot.json` | The computed model for a run, so two days can be diffed. Generated. |
| `update.sh` | Regenerate, commit if anything changed, push. What the daily routine runs. |

## Running it

```bash
./update.sh
```

or, to regenerate without committing:

```bash
python generate.py
```

It needs `gh` on `PATH`, authenticated against `SuperconducTED/superconducted-noise-engine`,
and Python 3.11+. No third-party packages: the standard library and `gh` are the whole
dependency set, so the routine cannot break on an environment drift.

## The question it exists to answer

The phase-3 plan states dependencies, and GitHub states what has merged. Neither alone
answers the question that actually governs a day's work: *given where everything is right
now, what should each person do next, and for anything not waiting on someone else — what
is actually holding it?* Those are two different questions and the plan conflates them.
The dashboard separates them into two sections deliberately.

Three derivations are where the value is, and each exists because a naive reading gets it
wrong:

- **A dependency is on an artifact, not an issue.** `#59`, `#60`, `#61` and `#63` all list
  `#57` as a prerequisite, but what they consume is the training contract, which merged in
  PR #69. `#57` itself stays open for its advisor half. Keying those edges on issue closure
  would paint the entire trainer track blocked when nothing is stopping it. So a dependency
  may name the artifact that discharges it (`satisfied_by`), and issue closure is only the
  fallback.

- **A dependency with a `part` gates that part, not the ticket.** `#60` needs `#63` for its
  first archive fit and for nothing else. Its LSE stage — the M2 gate, and the whole reason
  the trainer is called the long pole — needs nothing from `#63`. Partial dependencies
  become scope notes on a startable ticket, never a block.

- **A later `COMMENTED` review does not dismiss an earlier `CHANGES_REQUESTED`.** `main`'s
  merge gate is a ruleset requiring one approval, and it does **not** dismiss stale reviews
  on push. So "latest review" is the wrong model for who is blocking: only `APPROVED`,
  `CHANGES_REQUESTED` and `DISMISSED` move a reviewer's state. Getting this wrong hides
  exactly the reviews holding the phase up.

One more thing it refuses to do: treat a green check on a `CONFLICTING` PR as evidence.
`ci.yml` does not dispatch while a PR is dirty, so those checks describe a `main` that has
already moved. They are marked stale rather than green.

## Reading the marks

| | |
| --- | --- |
| ✅ | Met, and verified against live GitHub or the ADR ledger on `main`. |
| 🟡 | In flight — a PR exists but has not merged. |
| ❌ | Not done. |
| ⬜ | No machine-checkable source. Deliberately not amber: an unknown must never read as progress. |

## Maintaining `plan.json`

Edit it when, and only when, one of these is true:

- a milestone gate's wording or target changes in the plan document;
- a ticket's stated `Depends on` row changes on GitHub;
- a new ticket joins the phase, or an owner changes;
- a manual gate (`"kind": "manual"`) becomes machine-checkable, or its `note` goes stale.

Everything else — issue state, PR state, review decisions, CI, ADR statuses — is read live
on every run and must never be written here. If a number in the dashboard looks wrong, the
fix is almost always in `generate.py`'s derivation or in a ticket on GitHub, not in this file.

Manual gates carry a `note` explaining what was checked and when. A `note` is a claim like
any other in this project: it should name what was measured and where, so it can be
re-verified rather than trusted.

## Verification

The project convention puts an implementation record under `docs/implementations/` on
`main`. This one lives here instead, deliberately: the whole point of the orphan branch is
that phase-3 tracking never touches the engineering tree, and adding a doc to `main` to
describe a branch that must not reach `main` would defeat it. This section is that record's
verification half.

**The generator is honest about live state.** Every ✅ traces to a live read, so the check
is to move something on GitHub and confirm the mark follows:

```bash
python generate.py && grep -c '✅' STATUS.md   # baseline
gh issue close 66 && python generate.py        # then reopen it
grep -c '✅' STATUS.md                          # must have risen by one
```

**The routine does not commit noise.** Two runs in a row with nothing moving upstream must
produce a `no change` commit, never a `state moved` one:

```bash
./update.sh && ./update.sh && git log --oneline -2
```

The second subject must read `— no change`. If it reads `— state moved` with only a
timestamp in the diff, the stamp filter in `update.sh` has drifted from the format
`generate.py` emits.

**`update.sh` refuses to commit onto the wrong branch.** It `cd`s to its own directory
first, so where you invoke it from does not matter — what it guards against is *this
worktree having been switched to another branch*, which is the case where a commit would
actually land somewhere it should not. Confirm the guard fires:

```bash
git switch --detach && bash update.sh   # exits 1, writes nothing
git switch phase-3-dashboard
```

**Line endings survive a fresh checkout.** `autocrlf` is on in this repo, and a CRLF
`update.sh` fails with a bad-interpreter error. `.gitattributes` pins LF; confirm after any
fresh clone with `file update.sh`, which must not say `CRLF`.

**The derivations hold.** The three corrections in the section above are the ones a naive
implementation gets wrong, so they are the ones worth re-checking whenever `generate.py`
changes:

| Check | Expected |
| --- | --- |
| `#60` after `#57`'s contract merged | **ready**, with a scope note that the archive-fit part waits on `#63` — not blocked |
| A reviewer who follows a `CHANGES_REQUESTED` with a `COMMENTED` | still listed as the blocker, with "looked again … without lifting it" |
| A `CONFLICTING` PR with green checks | checks marked **stale**, never green |

## Sources

- `docs/roadmap/2026-09-03-phase-3-plan.md` on `main` — the plan itself, and the source of
  truth for anything the dashboard and the plan disagree about.
- `docs/decisions.md` on `main` — ADR statuses, read live.
- Issues #45–#84 and their `Depends on` rows.
