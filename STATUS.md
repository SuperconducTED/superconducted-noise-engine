# Phase 4: Design-time predictor

_Generated 2026-10-26 05:45 UTC · main at `a0ea1161` (2026-10-24) · starts 2026-11-01 (in 6 days) · milestone 2 due 2027-02-27 (124 days), 10 open and 1 closed_

_Read against the plan of 2026-10-23 at `951258da` on `mert/predictability`, PR #124 open, not on main yet. Gates are ordered, not dated (plan §6)._


## Lanes and gates


### Lane 1 · The quantum-venue result: level beats reading, per qubit, on hardware

_Everyone starts on lane 1 (plan §5.1)._

- ❌ **L1** Job 1 reported: #125's job 1 report, with the measured QPU cost and the budget gate decision. (0/1) · **next**
  - ❌ Job 1's usage report read, QPU cost measured, budget gate decided
    - _Unticked on #125's body._
- 🟡 **L2** Hardware test complete: #125 complete, decision rule applied, the hardware numbers registered. (0/2)
  - 🟡 #125 closed
  - ⬜ The hardware numbers registered as NC rows, one per conclusion
    - _No machine-checkable source: the register carries no per-ticket marker. Read docs/numerical-claims.md on main when #125 closes._

1. 🟡 #125 Hardware test: reading versus level on ibm_fez (@mertefesensoy): in review, PR #126
2. ✅ #63 Training-set builder (training/dataset.py) (@BahaJarad): delivered by PR #113 on 2026-10-23; the issue is still open with 1 unticked ask (Burak Öztekin)
3. ❌ #122 Public archive as a second training-set source (ADR-029) (@BahaJarad): waits on PR #121
4. ⬜ new: Per-qubit extractor and channel (ADR-013) (@BahaJarad, @BurakOztekin): opens after L1, not met yet. Opened after #125's job 1, because its centre (level or range) depends on the hardware answer (plan §2 lane 1 item 4, A.3).
5. ⬜ new: Cross-device dynamics tables (strategy audit S4), optional (@BahaJarad): no issue yet. Optional, if Baha has room after #122 (plan §2 lane 1 item 5).

### Lane 2 · The fuzzy-systems paper, which exists whatever lane 1 says

_Resumes at gate L1, job 1's report, or earlier for whoever is idle on lane 1 (plan §5.1)._

- ❌ **L3** PR-A1 and the first fit: PR-A1 and the first fit merged. (0/2) · **next**
  - ⬜ #64's PR-A1 merged (mechanism, seeding, band, coverage; no harness)
    - _PR-A1 has no number yet. When it opens, this condition becomes a pr_merged check on that number._
  - ❌ #60's first archive fit merged, so ADR-014 moves off Deferred
    - _Ledger on main reads: Deferred._
- ⬜ **L4** The ladder on the fuzzy band: The ladder table with the fuzzy band's row, registered. The paper's draft starts at L4 regardless of lane 1. (0/1)
  - ⬜ The ladder (persistence, shrinkage, rolling band, IT2 band, scored on change events) with the fuzzy band's row, registered
    - _No ticket yet (lane 2 item 6), so there is nothing on GitHub to read._

1. ❌ #64 ADR-015 / ADR-016 ensemble and intervals (PR-A) (@bengisucvd): ready to start
2. ✅ #58 Certify the benchmark instruments (PR #79) (@bengisucvd): closed
3. ❌ #60 ADR-014 trainer: the first archive fit (@BurakOztekin): ready to finish
4. ❌ #62 ADR-019 ablation table, both modes (@BahaJarad): ready to start
5. ❌ #61 Nie-Tan versus Karnik-Mendel, premise gradients (@bengisucvd): ready to start
6. ⬜ new: The ladder on the fuzzy band (@mertefesensoy, @bengisucvd): no issue yet. Persistence, shrinkage, rolling band and IT2 band scored on change events on pairs.tsv and rows.tsv.gz; gate L4 (plan §2 lane 2 item 6).

### Lane 3 · Housekeeping, one batched week, then closed

_The lead's closing week, run beside lane 1 (plan §5.1)._

- ❌ **L5** Phase 3 closed: The phase-3 milestone closed with every item either done or moved to the phase-4 milestone with a reason. (0/1) · **next**
  - ❌ Milestone 1 (Phase 3) closed
    - _Milestone 1 (Phase 3 · ANFIS results) is open: 12 open and 22 closed issues._

1. 🟡 #57 Training contract: ADR-027 accepted (PR #120) (@mertefesensoy): in review, PR #120
2. 🟡 #84 Close the #57 advisor loop (@mertefesensoy): in review, PR #120
3. ❌ #109 Phase-3 close record (@mertefesensoy): ready to start
4. ❌ #92 Rule 7 for the NC register (@bengisucvd): ready to start
5. ❌ #104 Decide the sweep step (@mertefesensoy): ready to start
6. ❌ #108 Owner read of PR #55's poller change (@BahaJarad): ready to start
7. ❌ #75 Decide the LOCKED Kraus projector boundary (@bengisucvd): ready to start

## Work on this right now


**Mert Efe Şensoy** (@mertefesensoy)

1. Unstick PR #126 for #125: Hardware test: reading versus level on ibm_fez (QPU side)
   - No approving review yet: main's ruleset requires one.
1. Unstick PR #120 for #57: Training contract: ADR-027 accepted (PR #120)
   - No approving review yet: main's ruleset requires one.
1. Unstick PR #120 for #84: Close the #57 advisor loop
   - No approving review yet: main's ruleset requires one.
1. Start #109: Phase-3 close record
   - The phase-3 close record is its deliverable, with the ADR-025 amendments answered or explicitly carried (plan §2 lane 3).

**Burak Öztekin** (@BurakOztekin)

1. #125 offline half: selection rules, circuits for both arms, scoring, the dry run against Aer (#125)
   - The dry run gates the pre-registration commit, and job 1 cannot be submitted before that commit (plan §5.1).
1. Decide #75's allowlist and clipping with Bengisu (#75)
   - It touches the per-qubit channel of lane 1 item 4, so it is decided before that opens (plan §2 lane 3, §5.1).
1. Finish #60: ADR-014 trainer: the first archive fit
   - A fitted model at a pinned ref with the snapshot-boundary split, so ADR-014 moves off Deferred (plan §2 lane 2 item 3). Lane 2 resumes at gate L1 (job 1's report), or earlier if your lane 1 piece is waiting on someone (plan §5.1).

**Bengisu Cıvdı** (@bengisucvd)

1. Review PR #121: it holds #122
   - Requested since 2026-10-23. #122 (Public archive as a second training-set source (ADR-029)) waits on it for the ADR-029 draft, which lands with PR #121 (plan §5.1; #122's own Depends on row names only #63 and #92).
1. Review #125's decision rule and statistics before the pre-registration freezes them (#125)
   - The pre-registration commit waits on this review (plan §5.1).
1. Start #92: Rule 7 for the NC register
   - Adopt as written: nine rows already use its form (plan §2 lane 3).
1. Start #75: Decide the LOCKED Kraus projector boundary
   - Decide the allowlist and the clipping before the per-qubit channel opens (plan §2 lane 3).

**Baha Jarad** (@BahaJarad)

1. Review PR #121: it holds #122
   - Requested since 2026-10-23. #122 (Public archive as a second training-set source (ADR-029)) waits on it for the ADR-029 draft, which lands with PR #121 (plan §5.1; #122's own Depends on row names only #63 and #92).
1. Start #108: Owner read of PR #55's poller change
   - The read, then close (plan §2 lane 3).
1. Start #62: ADR-019 ablation table, both modes
   - Behind #63 and #122 for Baha, said out loud (plan §5). Lane 2 resumes at gate L1 (job 1's report), or earlier if your lane 1 piece is waiting on someone (plan §5.1).

## Waiting on an answer

_Review requests not yet answered with a review, and unticked checkboxes that start with the person (`- [ ] @login does X`), on every open issue and PR. Oldest first; "or earlier" marks a post edited after it was written, so the wait shown is the shortest it can be._


**Mert Efe Şensoy** (@mertefesensoy), 2 owed

- has sent it to Dr. Akba (issue #84): own checklist, since 2026-09-08 (48 days); has posted there since, on 2026-10-21
- links the verdict from PR #55's thread so the PR record is complete. (issue #108): own checklist, since 2026-10-03 (23 days); no post there since

**Burak Öztekin** (@BurakOztekin), 6 owed

- confirms the `TrainingSet` is consumable by `HybridANFISTrainer.fit` (issue #63): asked by @mertefesensoy, since 2026-09-03 (53 days); no post there since
- Re-review PR #111: you approved on 2026-10-04 and were asked again: requested by @mertefesensoy, since 2026-10-05 (21 days); no post there since
- Review PR #120: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #123: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #124: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #126: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since

**Bengisu Cıvdı** (@bengisucvd), 5 owed

- Review PR #120: requested by @mertefesensoy, since 2026-10-21 (5 days); no post there since
- Review PR #121: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #123: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #124: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #126: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since

**Baha Jarad** (@BahaJarad), 3 owed

- posts a verdict on this issue: approve, or the defects he finds. (issue #108): asked by @mertefesensoy, since 2026-10-03 (23 days); no post there since
- Review PR #121: requested by @mertefesensoy, since 2026-10-23 (3 days); no post there since
- Review PR #127: requested by @mertefesensoy, since 2026-10-24 (2 days); no post there since

## Not blocked by anything upstream, so what is holding them?


**#125: Hardware test: reading versus level on ibm_fez** (@mertefesensoy)

- [high] No approving review yet: main's ruleset requires one.

**#57: Training contract: ADR-027 accepted (PR #120)** (@mertefesensoy)

- [high] No approving review yet: main's ruleset requires one.

**#84: Close the #57 advisor loop** (@mertefesensoy)

- [high] No approving review yet: main's ruleset requires one.

**#75: Decide the LOCKED Kraus projector boundary** (@bengisucvd)

- [medium] Touches LOCKED src/superconducted/channels/kraus.py: needs a decision, not just a patch.

## Blocked upstream

- **#122** Public archive as a second training-set source (ADR-029) (@BahaJarad), waiting on PR #121 (the ADR-029 draft, which lands with PR #121 (plan §5.1; #122's own Depends on row names only #63 and #92))

## Parked

- **#110** Deep-learning engine: plan and build the third engine mode (two-stage NumPy model, conformal band) (open, milestone Phase 4 · Design-time predictor): The pre-registered rule for deep-model work failed for T1, T2 and readout (NC-085, NC-086); the one remaining target is the chip-level readout series, a small model after #125, not a lane (plan §3).
- **#65** ADR-007: implement the pre-gate and between-gates fuzzification stubs and decide placement on a measurement instead of an Aer default (stretch, starts after M3) (open, no milestone): A phase-4 stretch in the phase-3 plan already; nothing today moves it up (plan §3).
- **#76** Phase 4: promote shot-free diagonal Hellinger to a certified benchmark metric (open, no milestone): A phase-4 stretch; useful after L4, not before (plan §3).
- **#93** file_snapshots.sh prescribes a rebuild after a sweep that pipeline_health.py says is not owed (open, milestone Phase 3 · ANFIS results): Only if #122's ingest needs the rebuild; otherwise parked (plan §2 lane 3, §3).

## Day by day


| Date | Gates | Conditions | Ready | In review | Blocked | What moved |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-10-26 | 0/5 | 0/7 | 9 | 3 | 1 | nothing moved |
| 2026-10-25 | 0/5 | 0/7 | 9 | 3 | 1 | milestone 2: 10 open and 1 closed (was 10 and 0); #58 Certify the benchmark instruments (PR #79): in review to done; #62 ADR-019 ablation table, both modes: blocked upstream to ready to start; Baha Jarad owes 3 answers (was 2); Burak Öztekin owes 6 answers (was 8); Mert Efe Şensoy owes 2 answers (was 3); main moved to a0ea1161 |
| 2026-10-24 | 0/5 | 0/7 | 8 | 4 | 2 | first record |

## ADR ledger

- ❌ **ADR-027** Calibration training target, on main: _Open_ · needs: PR #120, the lane 3 closing ritual (#57, #84)
- ❌ **ADR-029** Public calibration archive as a training source, on main: _not in the ledger_ · needs: #122; the draft lands with PR #121
- ❌ **ADR-013** Calibration feature engineering, on main: _Open / Deferred_ · needs: the per-qubit extractor and channel, opened after L1
- ❌ **ADR-014** TSK trainer architecture, on main: _Deferred_ · needs: #60's first fit moves it off Deferred (L3)
- ❌ **ADR-019** Membership function ablation methodology, on main: _Open_ · needs: #62's table
- ❌ **ADR-009** T1 vs Interval Type-2, on main: _Open_ · needs: #109 flips it, on ADR-019's evidence (plan §4)
- ❌ **ADR-011** Defuzzification method, on main: _Open (effectively chosen for each path)_ · needs: #61 supplies the number; #109 flips it (plan §4)
- ❌ **ADR-015** Ensemble sampling mechanism, on main: _Deferred_ · needs: #64 (PR-A)
- ❌ **ADR-016** Benchmark aggregation across ensemble members, on main: _Deferred_ · needs: #64 (PR-A)
- ❌ **ADR-021** Aer integration constraint and Factory/Ensemble pattern, on main: _Accepted on the constraint · Open on variance-injection design_ · needs: #109 flips it (plan §4)

## Risks the plan named

- The daily cadence of #125 rests on one account; a second is to be named before job 2.
- Baha carries #63, #122 and #62; #62 slips if the first two take the month. The alternative is Burak taking #62 after #60, which moves the ablation behind the first fit.
- PR #79 has been in review since September; lane 2's bands are invisible without it. _Now: PR #79 merged on 2026-10-24._
- Every number this plan rests on is a laptop measurement; Burak's desktop batch is owed before any figure leaves the provisional state.
- Dr. Akba's double-check of the direction change (A7, the paper's focus) has not been sought; the decisions register's 2026-10-03 arrangement makes the lead the approver, and the lead should say in the register that this plan is covered by it, or ask.
