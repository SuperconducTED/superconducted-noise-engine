# Phase 3 close: what the plan asked for, and what landed

The phase-3 close record that `docs/roadmap/2026-09-03-phase-3-plan.md` §5 names as an M4 item, and
Issue #109's deliverable. Every state below is read against `main` @ `667972c5` and against GitHub on
2026-11-15. It introduces no new measured figure: every number it cites is a register row or a count of
rows in its own tables.

**When the phase ended.** The plan's title says 2026-09-30. The lead moved the `Phase 3 · ANFIS
results` milestone to 2026-10-31 (the plan's 2026-10-03 reconciliation gives the reason), and the
milestone still reads that date. Phase 4 began on 2026-11-01 (`docs/roadmap/2026-10-23-phase-4-plan.md`).
Phase 3's milestone is still open, because five of its issues are; gate L5 of the phase-4 plan closes it
when each is done or moved to phase 4 with a reason (section 4).

**The one-line verdict.** Phase 3 delivered its contracts and instruments: the training target, the
training set, the floor, the certified harness, the dashboard and the sweep. It did not deliver its
results: no trained model has been fit on the archive and compared, and the three ADR decisions that
were to follow from the ablation are open. Those are phase 4's lane 2, gates L3 and L4.

## 1. The exit criteria (plan §2)

| # | Condition | State | Settled by |
| --- | --- | --- | --- |
| 1 | ADR-014 Accepted: a `TSKTrainer` implementation in a new `training` package, pinned by tests | Not met | `training/anfis.py` is on `main` (PR #114, 2026-10-15; the premise stage in PR #137, 2026-11-11), but ADR-014 reads `**Status**: Deferred.` and Issue #60 is open |
| 2 | A training target defined by an ADR, reviewed by Dr. Akba | Met | ADR-027 `**Status**: Accepted.` (PR #120, 2026-10-26), approved through the lead's signature (register entry of 2026-10-21, item 1) |
| 3 | A training set built from the archive, committed with its archive ref | Met | PR #113 (2026-10-23): `training/dataset.py` and `docs/evidence/training-set/` at two refs. Issue #63 is still open, with 0 of the 15 checkboxes in its body ticked |
| 4 | A trained model fit with a snapshot-boundary time split, its out-of-sample error registered | Not met | Issue #60: the first archive fit |
| 5 | Trained model, manual baseline and reference compared on the four circuits with all four metrics | Not met | Needs criterion 4. The instruments are certified (#58, PR #79) |
| 6 | ADR-019 executed and closed; ADR-009 decided on that evidence; ADR-011 follows | Not met | All three read `Open` on `main`. Issues #62 (the ablation) and #61 (PR #143, in review) |
| 7 | The floor derived from the rule base's parameter count and registered | Met | NC-045 and NC-046 (PR #87, 2026-09-09), reproduced on the desktop in PR #106 (2026-10-11) |
| 8 | Whether the archive has crossed that floor, stated honestly | Partly met | NC-045's FR-10.4 note states the archive below the floor at `calibration-data` @ `c63ce21` (NC-047). The canonical comparison at #63's pinned ref is still owed |

Three of eight are met, one partly. The four not met are the trained model and the decisions that
rest on it.

## 2. The gates (plan §5), one row per item

The plan's 2026-10-03 reconciliation has the same rows as of that date; this table supersedes it in
time, and both stay.

| Milestone | Gate item | State on 2026-11-15 | Settled by |
| --- | --- | --- | --- |
| M0 | #51 and #52 merged | Met, 2026-09-06 | PRs #51 and #52 |
| M0 | #55 post-merge owner read | Not met | Issue #108, open |
| M0 | ADR-025 sign-off | Met when this record's PR merges | Register items 2, 14, 16 and 17, answered on 2026-11-15 under Dr. Akba's delegation for the pipeline ADRs; ADR-025's 2026-11-15 amendment and status note |
| M0 | #53 dispatched with ledger rows | Met, a day late | Issue #53, closed 2026-09-08 |
| M0 | #45 closed | Met, 2026-09-09 | Issue #45 |
| M0 | #25 closed by the cycle-2 close record | Met, in substance | PR #81 closed #25; the cycle-2 close record merged the next day (PR #86) |
| M1 | Target ADR sent to Dr. Akba | Met late, by another route | Never e-mailed; approved in person, and ADR-027 Accepted in PR #120 |
| M1 | `TSKTrainer` ABC and types merged | Met, 2026-09-08 | PR #69 |
| M1 | Harness certified | Met, 2026-10-24 | PR #79; Issue #58 closed 2026-10-24 (on the phase-4 milestone) |
| M1 | Premise parameterization, seven shapes | Met, 2026-09-16 | PR #68 |
| M1 | Feature-survey TSV committed | Met, 2026-09-16 | `docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv` (PR #68) |
| M2 | Ablation executed with its table | Not met | Issue #62, open |
| M2 | Gradient derivations and `gradients.py` | Not met | Issue #61, open; no `training/gradients.py` on `main`. PR #143 (the Karnik-Mendel reference) is in review |
| M2 | Dashboard live | Met, 2026-09-10 | PR #70 |
| M2 | Sweep live | Met, 2026-09-10 | PR #90; its step moves to 0.5 h in PR #156 (Issue #104) |
| M2 | Trainer LSE stage passing on synthetic and anchored-baseline data | Partly met | The LSE core recovers planted targets (`tests/test_anfis.py`, PR #114). A search of `tests/`, `scripts/`, `src/` and `docs/` for "anchored" finds no run of it on the anchored baseline, only `training/anfis.py`'s advice to warm-start from one |
| M3 | ADR-019 closed with a winner | Not met | `**Status**: Open.`; Issue #62 |
| M3 | ADR-009 decided | Not met | `**Status**: Open.`; needs File 02 Q1a's time-split test with #62's table, then the lead's entry (register item 3) |
| M3 | ADR-011 follows | Not met | `**Status**: Open (effectively chosen for each path).`; Issue #61 |
| M3 | `training/dataset.py` with its evidence TSV | Met, 2026-10-23 | PR #113 |
| M3 | Floor derived and registered | Met, 2026-09-09 | NC-045 and NC-046; canonical in PR #106 |
| M3 | Trainer full loop with the first archive fit | Not met | Issue #60 |
| M4 | Trained model against baseline and reference, in `docs/findings/` with NC rows | Not met | Needs #60's first fit |
| M4 | ADR-014 Accepted | Not met | `**Status**: Deferred.`; Issue #60 |
| M4 | ADR-015 interim and ADR-016 interval aggregation merged | Not met | Both `**Status**: Deferred.`; Issue #64 (PR #155, the first of two PRs, in review) |
| M4 | Phase-3 close record | Met when this record's PR merges | This file |

M0 has five of its six items met, counting the ADR-025 sign-off this record's PR lands. M1 has five of
five, M2 two of five with one partly, M3 two of six, and M4 one of four. Against 2026-10-03, M0 gained
the ADR-025 row, M1 the harness, and M3 the training set.

## 3. The milestone's issues

Nine of the fourteen issues on the `Phase 3 · ANFIS results` milestone are closed: #54, #56, #57, #59,
#66, #73, #74, #84 and #100. Five are open:

| Issue | What it still needs |
| --- | --- |
| #92 | Rule 7 for the register: PRs #151 and #152, approved by the lead and held for independent reviews |
| #93 | The `file_snapshots.sh` warning that ADR-025's 2026-11-15 amendment (Q3) contradicts; not started |
| #104 | PR #156 (the sweep at 0.5 h), then its pre-registered test, read about nine days after the first 0.5 h sweep |
| #108 | The owner read of PR #55's poller change (M0's open row); not started |
| #109 | This record's PR; then it moves to the phase-4 milestone with what it carries (section 4) |

Open PRs on the milestone: #147, #151, #152 and #156.

**Two record gaps found here.**

- **#65 and #76.** Issue #109's body (2026-10-03) says they "are phase 4". On 2026-11-15 neither carries
  any milestone. They are not phase 3's, but no milestone records that they are phase 4's.
- **#63.** PR #113 delivered the training-set builder (exit criterion 3), but none of the 15 checkboxes in
  #63's body is ticked. That is for #63's owner to reconcile, and it does not change this record's
  reading of criterion 3.

## 4. What phase 4 carries, and why

Each item below is phase-3 work that waits on a phase-4 ticket, so it moves with that ticket rather than
holding phase 3 open. #109 carries the records; the tickets carry the work.

| Item | Carried by | Why it waits |
| --- | --- | --- |
| ADR-009's status flip (register item 3) | #109, on #62 | Needs File 02 Q1a's time-split test, with #62's ablation table supporting |
| ADR-011's closure (register item 4), in the same PR as ADR-009's flip | #109, on #61 | Needs #61's measurement (PR #143 and its successors) |
| ADR-014's flip reviewed for ledger form, and its approval (register item 5) | #109, on #60 | Needs #60's first archive fit |
| The canonical floor comparison at #63's ref | #109, on #63 | Needs the distinct-state count at the ref #63's builder pins |
| ADR-015 and ADR-016 (register items 6 and 7) | #64 | PR-A1 is PR #155, in review; PR-A2 (the harness interval mode) follows |
| ADR-019's closure (register item 8) | #62 | The ablation has not run |
| Register items 13 and 15, and the unnumbered #58 notes read | #109 | Outstanding; whether each falls under a delegation is stated in its own entry, not inferred here |
| Register item 11 (the `MemberPerturbation` owner read) | #109, on #64 | Withdrawn on 2026-09-09 because the contract did not exist; PR #155 adds it, so the item reopens when #155 merges |
| The deep-learning engine's design entry | #110, with Dr. Akba | His approvals for the deep-learning model stay his (register entries of 2026-10-21 and 2026-11-15) |
| File 06's merge counter in `health/metrics.json`, and NC-060's dependency on the stripped state definition | #109 | The first is code; the second edits the NC-060 row that PR #152 also edits |
| The M4 results: the trained model against baseline and reference | #60 and #62, gates L3 and L4 | Criteria 4 and 5 of section 1 |

## 5. Notes on this record

- It is append-only once merged: later states go in dated sections below, as for the plan.
- Nothing here was measured on a machine. Every state is a repository or GitHub fact, read on
  2026-11-15.
- The ADR-025 rows count as met only once this record's PR merges, because the register entries that
  meet them land in the same PR.
