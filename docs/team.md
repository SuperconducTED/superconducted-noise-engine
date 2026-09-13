# Team

## Roster

| Name | GitHub | Role | Primary modules |
| --- | --- | --- | --- |
| Dr. Fırat Akba | **none — reviews out-of-band; sign-off recorded in `docs/advisor/2026-09-03-decisions-from-akba.md`** | Faculty advisor | Reviews `docs/architecture.md` and architectural ADRs |
| Mert Efe Şensoy | `@mertefesensoy` | CS junior | `interfaces.py`, `types.py`, CI / pyproject, ADR ledger |
| Burak Öztekin | `@BurakOztekin` | CS&EE senior | `fuzzy/tsk.py` (LOCKED), `fuzzy/fuzzification.py`, `integration/aer_factory.py`, `benchmarks/harness.py` |
| Baha Jarad | `@BahaJarad` | CS&EE junior | `calibration/poller.py`, `calibration/storage.py`, `calibration/features.py` |
| Yiğit Arda Kaderoğlu | `@yigit-arda` | CS sophomore | `fuzzy/membership.py`, `fuzzy/squashing.py`, `benchmarks/circuits.py` |
| Bengisu | `@bengisucvd` | Math junior | `fuzzy/defuzzification.py`, `channels/kraus.py` (LOCKED, co-owned), `benchmarks/metrics.py` |

Handles are from `gh api repos/SuperconducTED/superconducted-noise-engine/collaborators`,
run 2026-09-07. A blank cell would be ambiguous, so an absent account is stated
outright: **Dr. Akba has no GitHub account** and is not a repository
collaborator — see "Reviews from outside GitHub" below.

> **NOTE · Bengisu is `@bengisucvd`, not `@bengisu`.** `@bengisu` is a real
> GitHub account belonging to someone unconnected to this project. Mentioning it
> notifies a stranger and silently fails to notify her; this has already happened
> three times. Copy the handle from this table rather than guessing it from a
> first name.

## Module ownership

| Module | Primary owner | Secondary reviewer |
| --- | --- | --- |
| `interfaces.py`, `types.py` | Dr. Fırat Akba | Mert Efe Şensoy |
| `calibration/poller.py` | Baha Jarad | Mert Efe Şensoy |
| `calibration/storage.py` | Baha Jarad | Mert Efe Şensoy |
| `calibration/features.py` | Baha Jarad | Bengisu |
| `training/` (`__init__.py`, `parameters.py`, `targets.py`) | Mert Efe Şensoy | Burak Öztekin |
| `fuzzy/membership.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `fuzzy/tsk.py` (LOCKED) | Burak Öztekin | Mert Efe Şensoy + Bengisu |
| `fuzzy/defuzzification.py` | Bengisu | Burak Öztekin |
| `fuzzy/fuzzification.py` | Burak Öztekin | Mert Efe Şensoy |
| `fuzzy/squashing.py` | Yiğit Arda Kaderoğlu | Bengisu |
| `channels/kraus.py` (LOCKED) | Bengisu | Burak Öztekin |
| `integration/aer_factory.py` | Burak Öztekin | Mert Efe Şensoy |
| `benchmarks/circuits.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `benchmarks/metrics.py` | Bengisu | Mert Efe Şensoy |
| `benchmarks/harness.py` | Burak Öztekin | Mert Efe Şensoy |
| `tests/*` | Owner of the implementation under test | — |
| `docs/architecture.md` | Dr. Fırat Akba | Mert Efe Şensoy |
| `docs/decisions.md` (ADR ledger) | Dr. Fırat Akba | Mert Efe Şensoy |

## How ownership works

- **Primary owner** reviews every PR that touches their files. They are
  the default reviewer requested on a draft PR.
- **Secondary reviewer** stands in when the primary owner is unavailable.
- **Locked modules** (`fuzzy/tsk.py`, `channels/kraus.py`) require BOTH
  the primary owner and the secondary reviewer to sign off, plus a
  reference to an ADR in `docs/decisions.md` if the change touches the
  locked math.
- **Cross-cutting changes** (CI, pyproject, requirements, ABCs in interfaces.py) need Mert Efe Şensoy's approval plus one additional contributor/reviewer (Burak or Bengisu). Architectural changes that touch ADR ledger semantics additionally need Dr. Fırat Akba's sign-off, obtained out-of-band — see below.
- **Reviews from outside GitHub.** Dr. Akba has no GitHub account, so his
  sign-off cannot be a review request and must not be written as one: a PR
  waiting on him will never show a pending reviewer, and `--add-reviewer` on his
  name simply fails. Circulate the change to him directly (email, or a thesis
  meeting), then record the outcome **in the PR** as a comment stating what was
  circulated, when, and the verdict. The GitHub approval that merges the PR still
  comes from a collaborator; his sign-off is a precondition recorded in writing,
  not a substitute for one.
- If you're unsure who owns a file, look in this table or ask in chat
  before opening a PR.

## Documentation conventions

Five house rules. The first three were surfaced by the cycle-2 opening batch; the
last two were added by Issue #56 FR-6 Part 3, which the phase-3 tickets cite. All
are ratified here so they are enforceable in review rather than re-litigated per PR.

- **Dated docs are append-only.** A dated document under `docs/roadmap/` or
  `docs/state-of-the-project/` is updated by appending a new as-of-stamped
  section that reconciles the prior content, or by adding a new dated file —
  never by editing the original in place. The filename's date is a
  point-in-time claim about when the content was true, and editing the body
  silently falsifies it. Reconciling in an appended section keeps both the
  original reading and the correction auditable.

- **Use the repository's real labels.** The live set, from `gh label list` run
  2026-09-07:

  | Group | Labels |
  | --- | --- |
  | Area | `area:benchmarks`, `area:calibration`, `area:fuzzy`, `area:integration` |
  | Type | `type:coordination`, `type:devops`, `type:feature`, `type:research`, `type:testing` |
  | Priority | `priority:critical`, `priority:high`, `priority:medium-high`, `priority:low` |
  | Other | `bug`, `coordination`, `dependencies`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `python`, `question`, `wontfix` |

  Re-run `gh label list` rather than trusting this table if it looks stale, and
  update it here when it has drifted. An earlier audit claimed no `priority:*`
  or `type:research` labels existed; issue #4 visibly carries both, so that
  audit was wrong and is superseded by the live list above.

- **Callouts are text labels, never emoji.** Write `> **CRITICAL · …**` and
  `> **NOTE · …**` in issues, PRs and docs. This matches the ASCII-only style
  used across the cycle-2 openers, and keeps callouts greppable and legible in
  terminals and diffs where emoji render inconsistently or not at all.

- **Allocate ADR and NC identifiers at merge time, never in a draft.** Write
  "the next free ADR id at merge time" in a branch and pick the actual number
  when the PR is about to merge, renumbering if a concurrent branch took it
  first. Two branches that each append "the next id" to a different decision
  produce the same number against different content, and git shows only a text
  conflict, so the collision survives a clean merge. This happened on
  2026-08-31; the incident and the branch reissue it forced are written up in
  `docs/implementations/2026-08-31-adr-nc-collision-and-branch-reissue.md`.
  `scripts/check_ids.py` runs in CI and fails on a duplicate or colliding
  identifier, but it cannot tell you which of two claimants should renumber, so
  the rule still has to be followed by hand.

- **Verification is batched on Burak's desktop, not filed per PR.** Canonical
  verification runs on @BurakOztekin's desktop in two batches per phase, one
  after M2 and one after M3. Each batch produces a single
  `docs/verification/2026-09-XX-phase-3-batch-N-burak-desktop.md` covering every
  PR merged since the previous batch. **A PR's numbers are verified when they
  appear in the next batch record**, not when a per-PR record exists; there is
  no per-PR verification record any more. The three
  `docs/verification/2026-08-*-burak-desktop.md` files are the per-PR shape this
  convention replaces, and they are kept as the file-shape precedent. Runs on any
  other machine, the lead's laptop included, stay **provisional** and are cited
  as such with the machine named; the batch record is the source of truth. Do not
  claim a number is canonically verified before its batch record merges.

## Updating this file

Update this file when:
- A team member joins or leaves.
- Module ownership shifts (record the date in the PR description).
- A new module appears in the source tree — add a row before merging.

**Package `__init__.py` files** (Issue #57 FR-14, settled 2026-09-08). The rule
above says "a new module", and until Issue #57 the table listed no `__init__.py`
at all although six package files existed, so "every module" and the practice
disagreed. The settled reading is **(a)**: a package gets **one row naming the
package**, which covers its `__init__.py` along with the modules listed beside
it — as the `training/` row does. Reading (b), declaring docstring-only
`__init__.py` files out of scope, was rejected because it leaves the ownership
of a re-export surface unstated, and a package root that re-exports the ABCs is
exactly where a cross-cutting change can hide. The six pre-existing package
files are covered by their directory's row where one exists; adding rows for
the rest is housekeeping, not a blocker on any ticket.
