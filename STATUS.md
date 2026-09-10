# Phase 3: Results from ANFIS

_Generated 2026-09-10 08:15 UTC · main at `d0d0b073` (2026-09-10) · 20 days to 2026-09-30_


## Milestones


### 🟡 M0 · Queue clear, target 2026-09-05 (7/8)

- ✅ #51 merged (aer_factory ADR references)
- ✅ #52 merged (Aug 7-17 polling gaps)
- ✅ #55 merged (sub-hourly backfill step)
- ⬜ #55 post-merge owner read + ADR-025 sign-off collected
  - _Owner read is on Baha (poller.py is his). No recorded sign-off found on main; tracked inside #56 FR-2._
- ✅ #53 dispatched with ledger rows
  - _Four workflow_dispatch runs executed; snapshots/2026-08/ibm_fez 277 -> 304 docs at 7139138. Record is PR #78, still unmerged._
- ✅ #53's record merged
- ✅ #45 closed (dataset-yield finding)
- ✅ #25 closed by the cycle-2 close record

### 🟡 M1 · Contracts and instruments, target 2026-09-11 (1/5)

- ❌ Target ADR sent to Dr. Akba with a decision-by date
  - _ADR-027 merged with Status: Open. docs/advisor/ holds only the unanswered 2026-05-25 questions file. Issue #84 owns the brief; its own decision-by date was 2026-09-08._
- ✅ TSKTrainer ABC and training value types merged
- 🟡 Benchmark harness certified (#58)
- 🟡 Premise parameterization for seven shapes merged (#59)
- ❌ Feature-survey TSV committed
  - _Exists as docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv inside PR #68; not on main until #68 merges._

### ❌ M2 · First measurements, target 2026-09-18 (0/5)

- ❌ ADR-019 ablation executed with its table (#62)
- ❌ Gradient derivations and training/gradients.py (#61)
- ❌ Pipeline-health dashboard live (#48)
- 🟡 Scheduled sweep live (#49)
- ❌ Trainer LSE stage passing on synthetic + anchored-baseline data
  - _#60 has no branch or PR yet. Its contract dependency (#57) merged 2026-09-08, so it is startable._

### ❌ M3 · Decisions, target 2026-09-25 (0/6)

- ❌ ADR-019 closed with a winner
  - _Ledger on main reads: Open._
- ❌ ADR-009 decided (T1 vs IT2)
  - _Ledger on main reads: Open._
- ❌ ADR-011 follows
  - _Ledger on main reads: Open (effectively chosen for each path)._
- ❌ training/dataset.py merged with its evidence TSV (#63)
- ❌ Floor derived from the actual parameter count and registered
  - _Replaces the reconstructed 126 behind NC-012. Owned by #56._
- ❌ Trainer full loop merged, first archive fit, time-split metrics

### ❌ M4 · ANFIS results, target 2026-09-30 (0/4)

- ❌ Trained vs anchored baseline vs reference, four circuits, four metrics, in docs/findings/ with NC rows
  - _The phase-3 exit artifact. Produced by #62's script re-run at M4._
- ❌ ADR-014 Accepted
  - _Ledger on main reads: Deferred._
- ❌ ADR-015 interim and ADR-016 interval aggregation merged (#64)
- ❌ Phase-3 close record written
  - _Owned by #56, mirrors the cycle-2 close record convention._

## Work on this right now


**Baha Jarad** (@BahaJarad)

1. Start #48: Pipeline-health dashboard
   - Its prerequisite merged 2026-09-02 and #63 cannot start its FR-1 half until the digest body is settled.
1. Start #66: Vectorizer returns µs where the repo assumes s
   - No dependencies in either direction, and it blocks running the shipped pipeline on real archived data, which phase 3 does throughout. On a real snapshot the ratified 3x3x3 grid fires at exactly zero and the bootstrap pipeline raises ZeroDivisionError.

**Bengisu Cıvdı** (@bengisucvd)

1. Unstick PR #79 for #58: Certify the benchmark instruments
   - Still a draft: CI and reviewers will not treat it as ready.
1. Start #61: ADR-011 evidence + premise gradients
   - Part B is unblocked (#57 merged) and the plan schedules it in W2 because the trainer's verification depends on it.
1. Start #75: Decide the LOCKED Kraus projector boundary
   - All stated upstream dependencies are met.

**Burak Öztekin** (@BurakOztekin)

1. Start #60: ADR-014 hybrid ANFIS trainer
   - The plan's named long pole: four weeks of one person's time, LSE stage due by M2 (Sep 16-18). Its contract dependency merged on 2026-09-08, so nothing stands between it and a first commit. Start the rest now: the archive fit part waits on #63.
1. Start #73: Filter noise by physical gate semantics
   - All stated upstream dependencies are met.
1. Start #74: first_ensemble_run must transpile before prepare
   - All stated upstream dependencies are met.

**Mert Efe Şensoy** (@mertefesensoy)

1. Send Dr. Akba the four ADR-027 questions (#84)
   - FR-15 routes all advisor contact through the lead, so no one else can send it. The decision-by date was 2026-09-08 and has passed. ADR-027 stays Open, ADR-014 stays Deferred, and the M3 ADR-009 memo has no answer to build on until this goes out.
1. Finish #57: Training contract: ADR-027, TSKTrainer ABC, training/targets.py
   - The contract merged; only the advisor half of its definition of done is outstanding.
1. Finish #56: Clear the queue, keep the records honest
   - It is the M0 gate and M0 is three days past its 2026-09-05 target.
1. Start #54: Capture rate ~70% during normal operation
   - All stated upstream dependencies are met.

**Yiğit Arda Kaderoğlu** (@yigit-arda)

1. Start #84: Close the #57 advisor loop
   - The only phase-3 blocker with a multi-week external latency tail, and the only M1 gate with no work in flight. Every day it waits is a day added to M3.
1. Unstick PR #68 for #59: Manual MF parameterization from the archive
   - Still a draft: CI and reviewers will not treat it as ready.

## Not blocked by anything upstream, so what is holding them?


**#84: Close the #57 advisor loop** (@yigit-arda)

- [critical] Dr. Akba must answer four ADR-027 questions. He has no GitHub account; FR-15 routes all contact through the lead.
- [critical] The FR-15 decision-by date was 2026-09-08 and has passed with the brief unsent.

**#58: Certify the benchmark instruments** (@bengisucvd)

- [high] Still a draft: CI and reviewers will not treat it as ready.
- [high] No approving review yet: main's ruleset requires one.
- [medium] Section 7 lists decisions needing sign-off before building, incl. the Aer version pin (@yigit-arda depends on the answer for reproducible ablation runs).

**#59: Manual MF parameterization from the archive** (@yigit-arda)

- [critical] Conflicts with main: needs a rebase before it can merge, and ci.yml will not re-run until it is clean.
- [high] Still a draft: CI and reviewers will not treat it as ready.
- [high] Its green checks last ran 2026-09-08T19:40 against a main that has moved since; they are not evidence about the merge result.

**#61: ADR-011 evidence + premise gradients** (@bengisucvd)

- [low] FR-4's consequent convention and the raw-space vs logit-space choice both depend on #57's decision.

**#48: Pipeline-health dashboard** (@BahaJarad)

- [high] Decision 3: the --scope qubits digest body must be locked before FR-1 is written, because #63 consumes it.

**#49: Scheduled backfill sweep** (@mertefesensoy)

- [high] No approving review yet: main's ruleset requires one.
- [low] The plan raises its priority per #54 but its own body still reads priority:low and 'pending Baha's confirmation'.

**#56: Clear the queue, keep the records honest** (@mertefesensoy)

- [critical] Every advisor item it carries (ADR-025 sign-off, ADR-009 flip, ADR-011 closure, ADR-014 read, the target ADR) needs Dr. Akba, who has no recorded answer to anything.
- [high] #45 is still open; M0 is not closable until it is.
- [high] #53's record (PR #78) is unmerged at CHANGES_REQUESTED.

**#75: Decide the LOCKED Kraus projector boundary** (@bengisucvd)

- [medium] Touches LOCKED src/superconducted/channels/kraus.py: needs a decision, not just a patch.

**#57: Training contract: ADR-027, TSKTrainer ABC, training/targets.py** (@mertefesensoy)

- [critical] Code landed in PR #69, but the ticket's own definition of done requires the ADR to be sent to Dr. Akba with a decision-by date inside W1. That has not happened; #84 owns it.

## Blocked upstream

- **#62** Run the ADR-019 ablation, publish the table (@yigit-arda), waiting on #58 (certified harness (basis_gates, mode, seed, transpile-then-prepare, no silent NaN) and benchmarks/reference.py::build_reference); #59 (the parameterized rule bases under ablation)
- **#63** Training-set builder (training/dataset.py) (@BahaJarad), waiting on #48 (FR-1's --scope qubits digest (his own ticket; the digest body must be locked before FR-1 is written))
- **#64** ADR-015 / ADR-016 ensemble + intervals (@bengisucvd), waiting on #58 (density-matrix mode, transpile-then-prepare, no silent NaN, build_reference, simulate_engine signature); M3 gate (gated on the ADR-009 decision and #60's first archive fit)
- **#65** ADR-007 pre/between-gates fuzzification (@BurakOztekin), waiting on #58 (certified harness and build_reference); M3 gate (phase 4; the M3 gate is the earliest conceivable start, not a promise)
- **#76** Promote diagonal Hellinger to a certified metric (@bengisucvd), waiting on #58 (certified density-matrix harness); #62 (the helper and evidence format must stabilise first)

## Day by day


| Date | Gates | Ready | In review | Blocked | What moved |
| --- | ---: | ---: | ---: | ---: | --- |
| 2026-09-10 | 8/28 | 11 | 3 | 5 | +1 milestone gate (7 to 8 of 28); M0 6/8 to 7/8; #45 Polling cadence no longer limits the dataset: ready to start to closed; #48 Pipeline-health dashboard: in review to ready to start; #49 Scheduled backfill sweep: ready to start to in review; main moved to d0d0b073 |
| 2026-09-09 | 7/28 | 12 | 3 | 5 | +1 milestone gate (6 to 7 of 28); M0 5/8 to 6/8; #53 Backfill 14 recoverable documents: in review to closed; #57 Training contract: ADR-027, TSKTrainer ABC, training/targets.py: in review to ready to start; main moved to 5f935ea1 |
| 2026-09-08 | 6/28 | 11 | 5 | 5 | first record |

## ADR ledger

- ❌ **ADR-027** Calibration training target, on main: _Open_ · needs: Dr. Akba's four answers (#84)
- ❌ **ADR-014** TSK trainer architecture, on main: _Deferred_ · needs: #60 + the derived floor; revisited 2026-09-07, still Deferred
- ❌ **ADR-019** MF ablation methodology, on main: _Open_ · needs: #62's table; prerequisite (b) cleared only when #59 merges
- ❌ **ADR-009** T1 vs Interval Type-2, on main: _Open_ · needs: ADR-019's evidence + the M3 memo to Dr. Akba
- ❌ **ADR-011** Defuzzification method, on main: _Open (effectively chosen for each path)_ · needs: Follows ADR-009; #61 supplies the number
- ❌ **ADR-015** Ensemble sampling mechanism, on main: _Deferred_ · needs: #64, after the M3 gate
- ❌ **ADR-016** Benchmark aggregation across members, on main: _Deferred_ · needs: #64, after the M3 gate
