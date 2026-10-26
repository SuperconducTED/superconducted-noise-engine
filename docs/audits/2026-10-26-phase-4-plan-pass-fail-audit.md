# Phase 4 plan: pass/fail audit, amended with the neural-network item

**Date**: 2026-10-26 · **Requested by**: Mert Efe Şensoy (lead) · **Audits**:
`docs/roadmap/2026-10-23-phase-4-plan.md` (on PR #124's branch `mert/predictability` at
`951258da` and on `mert/issue-125-preregistration` at `821f6781`; not yet on `main`) ·
**Status**: audit. Section 4 is a **proposal**, not an adopted plan item; nothing in it is in
force until the lead says so, and its success rule needs Dr. Akba's word (section 4.1).

## 0. Baseline and reading of the request

| What | Value at audit time |
| --- | --- |
| `main` | `a0ea1161` (merge of PR #79, 2026-10-24) |
| `mert/issue-125-preregistration` | `821f6781` (pushed 2026-10-24, draft not frozen, no PR) |
| `mert/predictability` (PR #124) | `951258da` |
| `mert/persistence-band` (PR #123) | `07156cc9` |
| `mert/issue-125-archive-side` (PR #126) | `6f458867` |
| `calibration-data` tip | `cf960389` (poller still running, 2026-10-26) |
| Phase-4 dashboard record | `history/phase-4/2026-10-26.json` on `phase-4-dashboard` (`c06c09e0`): gates 0 of 5, freeze conditions 0 of 7, tickets 2 done, 3 in review, 9 ready, 1 blocked |
| GitHub state read | 2026-10-26 09:27 UTC with `gh` (PRs #120, #121, #123, #124, #126, #127; Issues #57, #60 to #64, #75, #84, #92, #104, #108, #109, #110, #122, #125) |

**Reading of "amend pass/fail audit".** `docs/audits/` holds no phase-4 audit to append to, so
this file is read as *an amended audit*: the plan's items judged pass or fail against live
state (sections 1 to 3), amended with the neural-network item Dr. Fırat Akba suggested
(section 4). If the lead meant an amendment to an audit that exists elsewhere, this file is the
candidate text for it.

**Verdict vocabulary**, used and nothing else:

| Verdict | Meaning |
| --- | --- |
| PASS | the plan's own "what done looks like" is met, with the evidence named |
| FAIL | the criterion was due and is not met, or the plan's premise is contradicted |
| IN PROGRESS | work exists on a branch or in a thread and the criterion is not yet met |
| NOT STARTED | no branch, no thread, no comment |
| BLOCKED on X | cannot move until X, named |
| AT RISK by date | not failed yet, but the date the plan names is within reach and nothing has moved |

No new number is measured in this audit; every figure cited is a register row (NC-077 to
NC-091) on the branches named above, laptop, provisional, in Rule 7 form (dated anchors, not
current values).

## 1. Headline findings

1. **Nothing has moved on GitHub since the evening of 2026-10-24.** All six open PRs (#120,
   #121, #123, #124, #126, #127) have zero reviews, and no comment since 2026-10-24 (the one
   comment on #123 is the lead's own review note of 2026-10-23); `main` is unchanged. Every
   precondition of the pre-registration freeze (its section 6) is therefore where it was.
2. **The critical path is Burak's offline half, and it is NOT STARTED.** No branch exists for
   `scripts/hardware_reading_vs_level.py`'s selection, circuits, scoring or the dry run against
   Aer. The pre-registration cannot freeze without it (its section 6), and job 1 cannot be
   submitted before the freeze.
3. **Baha gates his own next step.** He is a requested reviewer on PR #121, and #122 (ADR-029,
   his lane-1 item) is BLOCKED on #121 merging. #122 has no comment.
4. **Bengisu's D1 to D5 on #64 are NOT STARTED.** The lead's 2026-10-23 comment on #64 asking
   for them has no reply; lane 2's first item (PR-A1) waits on it.
5. **Lane 3's "one batched week" is AT RISK by 2026-10-31.** #92, #104, #108 and #109 have zero
   comments; PR #120, the closing ritual's first step, has no review. Five days remain.
6. **Three items PASS**: PR #113 merged (lane 1 item 2), PR #79 merged (lane 2 item 2), and the
   issue-board triage of Appendix A applied (A.6).
7. **The plan's stop rule on deep-model work (§4) now meets a request from the advisor.** The
   evidence that produced the stop rule (NC-084 to NC-086) stands; section 4 turns Dr. Akba's
   suggestion into a pre-registrable item that the evidence allows, and names the decision the
   lead has to take on §4.

## 2. Pass/fail by plan item

### 2.1 Lane 1, the quantum-venue result

| Order | Item | Criterion (plan's text) | Evidence checked | Verdict |
| --- | --- | --- | --- | --- |
| 1 | #125 hardware test | job 1 usage report read; 14 daily jobs; pre-registered decision applied; NC rows | design approved 2026-10-23; proposals A to D and the hour decided 2026-10-24 (pre-registration §3.5, §3.6); draft **not frozen**; PR #126 (archive side) open, unreviewed; offline half: no branch; no job submitted | IN PROGRESS (QPU side); NOT STARTED (offline half); BLOCKED on the freeze for job 1 |
| 2 | #63 training-set builder | PR #113 merged | merged 2026-10-23 as `88fa6a40`; #63 still open with its decisions 1 to 6 recorded by the lead on 2026-10-21; whether it closes is the lead's call (dashboard: done) | PASS |
| 3 | #122 public archive, ADR-029 | ADR-029 accepted or rejected; builder reads the pinned revision; NC-078's 626 reproduced | Issue open, 0 comments; the ADR draft is on PR #121, unreviewed; Baha is #121's requested reviewer | BLOCKED on PR #121 (Baha's own review) |
| 4 | per-qubit extractor and channel (ADR-013) | opened after #125's job 1 | not opened, by design | NOT STARTED, correctly: waits on gate L1 |
| 5 | cross-device tables (S4), optional | NC-080 to NC-086 on two more backends under ADR-029 | nothing | NOT STARTED; optional, behind item 3 |

**Gate L1** (job 1's report): NOT STARTED. **Gate L2** (#125 complete): NOT STARTED. The
dashboard's L2 "partial" reflects #125 being in review, not any hardware result.

### 2.2 Lane 2, the fuzzy-systems paper

| Order | Item | Criterion | Evidence | Verdict |
| --- | --- | --- | --- | --- |
| 1 | #64 PR-A | D1 to D5 answered; PR-A1 merged | plan posted on #64 2026-10-23 (lead); no reply from Bengisu; no PR-A1 branch | NOT STARTED (her answers); BLOCKED on them (PR-A1) |
| 2 | #58 harness certification, PR #79 | merged | merged 2026-10-24 as `a0ea1161`; #58 closed by its "Closes" line; NC-021 re-measure in PR #127, unreviewed | PASS (the register row IN PROGRESS) |
| 3 | #60 first archive fit | fitted model at a pinned ref, snapshot-boundary split; ADR-014 off Deferred | last comment 2026-10-16; no branch | NOT STARTED, correctly: lane 2 resumes at L1 |
| 4 | #62 ADR-019 ablation | the table, both modes | last comment 2026-10-16 | NOT STARTED, correctly: behind #63 and #122 for Baha |
| 5 | #61 Nie-Tan vs Karnik-Mendel | the number ADR-011 needs | Bengisu's branch `bengisu/issue-61-part-a-type-reduction` (2026-10-21), her comment 2026-10-21 | IN PROGRESS |
| 6 | the ladder on the fuzzy band | persistence, shrinkage, rolling band, IT2 band scored on change events | rows and bar exist (`pairs.tsv`, `rows.tsv.gz`, NC-081, NC-085); no fuzzy-band row | NOT STARTED, correctly: needs items 1 and 3 |

**Gate L3** (PR-A1 and the first fit merged): NOT STARTED. **Gate L4** (ladder with the fuzzy
band's row): NOT STARTED; the paper's draft starts here, so nothing of the draft exists yet.

### 2.3 Lane 3, housekeeping, "one batched week, then closed"

| Item | Owner | Criterion | Evidence | Verdict |
| --- | --- | --- | --- | --- |
| #57, #84, #109 | Mert | ADR-027 accepted (PR #120), register entries, phase-3 close record | PR #120 open (main merged in `4d5c37a2`, PR #79 recorded `eb7d01f8`), requested reviewers Bengisu and Burak, 0 reviews; #109 0 comments; #57 and #84 last touched 2026-10-21 | IN PROGRESS; AT RISK by 2026-10-31 (PR #120 unreviewed) |
| #92 Rule 7 | Bengisu | adopt as written | 0 comments | NOT STARTED; AT RISK by 2026-10-31 |
| #104 sweep step | Mert | decide with NC-079's figures; close | 0 comments | NOT STARTED; AT RISK by 2026-10-31 |
| #108 owner read of #55 | Baha | the read; close | 0 comments | NOT STARTED; AT RISK by 2026-10-31 |
| #75 Kraus projector boundary | Bengisu, Burak | allowlist and clipping decided before the per-qubit channel opens | 0 comments | NOT STARTED; not yet due (due before lane 1 item 4) |
| #93 rebuild | Baha | park unless #122 needs it | parked, `priority:low` | PASS (parked as planned) |

**Gate L5** (phase-3 milestone closed with every item done or moved with a reason): NOT
STARTED; AT RISK by 2026-10-31.

### 2.4 Parked, with the reason written down

| Ticket | Plan's reason | Still true? | Verdict |
| --- | --- | --- | --- |
| #110 deep engine | the pre-registered rule for deep-model work failed on T1, T2, readout (NC-085, NC-086); one target left, the chip-level readout series; A7 note drafted, not posted | the evidence stands; the A7 note is still not posted; **the advisor has now asked for a neural-network item** (section 4) | PASS as a record; the park is **re-opened for decision** by section 4 |
| #65 fuzzification placement | phase-4 stretch | unchanged | PASS |
| #76 shot-free Hellinger | after L4 | unchanged | PASS |
| #93 | see lane 3 | unchanged | PASS |

### 2.5 The four stop rules of §4

| Rule | Held since 2026-10-23? | Verdict |
| --- | --- | --- |
| No new deep-model work until #125 reports and the chip-level readout series is measured | no deep-model code or run since; the request in section 4 is a *proposal* and trains nothing | PASS so far; a decision is now owed (section 4.6) |
| No new measurements beyond #125 and lane 1 item 5 | NC-087 to NC-091 (2026-10-24) are #125 pre-registration measurements, inside the rule | PASS |
| No new ADRs until #109 flips the waiting ones | ADR-029 is a draft from 2026-10-23, before the rule; nothing new since | PASS |
| No paper sentence about drift bracketing | no draft exists | PASS (vacuously) |

### 2.6 "One thing per person, this week" (§5, week of 2026-10-23) and §5.1

| Person | This week (plan) | Evidence | Verdict |
| --- | --- | --- | --- |
| Mert | usage-page check; pre-registration commit; lane-3 closing ritual | usage-page check superseded by the lead's 2026-10-24 budget decision (pre-registration §4); pre-registration drafted and pushed, decisions A to D taken, not frozen; closing ritual: PR #120 waits on reviewers | PASS (budget decision replaces the check); IN PROGRESS (pre-registration); IN PROGRESS, AT RISK (ritual) |
| Burak | offline half; dry run against Aer, zero QPU cost | no branch; no comment on #125 since the 2026-10-24 merge-order post | NOT STARTED, **critical path** |
| Baha | merge #63; start #122 | #113 merged; #122 untouched; #121 (his review) unreviewed | PASS (#63); BLOCKED on his own review of #121 (#122) |
| Bengisu | D1 to D5 on #64; PR #79 toward merge | #79 merged; no D1 to D5 reply | PASS (#79); NOT STARTED (D1 to D5) |

§5.1's reviews owed, from the merge order the lead posted on #125 (comment 6388147313): wave 1
#126 (Burak), #121 (Baha), #120 (Bengisu); wave 2 #123 then #124 (Bengisu and Burak). None has
a review. **Every wave-1 review is NOT STARTED.**

### 2.7 Risks named in §7

| Risk | State today | Verdict |
| --- | --- | --- |
| daily cadence rests on one account; a second named before job 2 | no second account named (pre-registration §5) | NOT STARTED; not yet due (before job 2) |
| Baha carries #63, #122, #62 | #63 done; #122 blocked on his own review; #62 untouched | materialising: the block is on his review queue, not on his bandwidth |
| PR #79 in review since September | merged 2026-10-24 | PASS (risk retired) |
| every number is a laptop measurement; Burak's desktop batch owed | nothing from the desktop since | NOT STARTED |
| Dr. Akba's double-check of the direction change not sought | the advisor has sent a suggestion (section 4), which is evidence of contact, **not** of ratifying the direction change; the register line or the ask is still not written | NOT STARTED; see section 4.1 |

### 2.8 The pre-registration's freeze preconditions (its §6), the gate behind L1

| Item | Owner | State 2026-10-24 | State 2026-10-26 |
| --- | --- | --- | --- |
| A to D answered | Mert | done | done |
| submission hour | Mert | done | done |
| statistics review of the decision rule (null-model value of each threshold; bootstrap unit) | Bengisu | open, requested on PR #124 | unchanged, no review |
| offline half and its dry run, committed | Burak | open, no branch | unchanged, no branch |
| PR #120 merged | reviewers | open | unchanged |
| PR #124 and PR #126 merged | reviewers | open | unchanged |
| controls re-run at the freezing ref | Mert | after the above | waiting |

Seven items, zero moved in two days, matching the dashboard's "conditions 0 of 7".

## 3. What the audit changes, and what it owes

- **No plan text is edited here.** The plan lives on PR #124's branch; an as-of pointer to this
  audit belongs there once #124 merges, or in a later as-of section of the plan. Owed, lead.
- **The dates in §6 hold as targets.** L1 "within two weeks of job 1's submission" has no
  submission yet; the realistic clock starts at the freezing commit, which starts at Burak's dry
  run. The audit records the dependency chain once, plainly: *dry run → Bengisu's review →
  freeze → job 1 → L1 → lane 2 resumes and the per-qubit extractor opens.*
- **Three posts drafted on 2026-10-24 are still not posted** (A.4): the A7 note on #110, the
  review note to Bengisu on PR #124, the register line on whether the 2026-10-03 arrangement
  covers the direction change. The lead's word is still required for each; section 4 makes the
  A7 note more urgent, since it is the ticket the neural-network item would land on.

## 4. Amendment: the neural-network pattern detector Dr. Akba suggested

### 4.1 Provenance, ownership, and what this section is

The lead reported on 2026-10-26, in the session that produced this audit, that Dr. Fırat Akba
suggested the team "also design a neural network to detect necessary patterns that will help
the Q1 paper goal", with his view that it would improve the paper's chances. The medium and the
exact words are not recorded; this is the lead's account, as the register's entries attribute
Dr. Akba's method guidance (see `docs/advisor/2026-09-03-decisions-from-akba.md`). It is
**not** a ratification of the 2026-10-23 direction change (§7's last risk), and the audit infers
nothing about that from it.

Ownership follows the lead's 2026-10-13 delegation (posted on #84 as comment 6312713600 on
2026-10-21; its register entry lands with PR #120): the lead's signature is Dr. Akba's approval
for fuzzy-engine items; **the deep-learning model stays with Dr. Akba**.
So the success rule below is a proposal that goes to him for ratification, through the advisor
channel in the project's form (a triaged, self-contained Turkish cluster under `docs/advisor/`,
with the "why him and why not measure it ourselves" paragraph each question carries). That brief
is **not** written here; it is the follow-up this section creates.

The plan's §4 forbids new deep-model work until #125 reports. This section designs and
pre-registers; it trains nothing. Whether training may start before L1 is the lead's call
(section 4.6).

### 4.2 What the evidence leaves open, and therefore what the network may be

The 2026-10-23 measurements closed one route and left three open. The closed route is the
network as a **forecaster of a qubit's own T1, T2 or readout from its own history**: the
pre-registered two-clause rule failed for all three (predictability README §3.4, §3.6a; NC-085,
NC-086), and the local-level cap says no model on that history narrows the rolling band
materially. A network built there would be built to fail its own test, and the audit does not
propose one.

What the same records leave open, in the order of their distance from the design-time decision
an engineer makes:

| Open target | Where the record leaves it | Rows to train on | Distance from the design-time decision |
| --- | --- | --- | --- |
| **(T-a) When a reading departs from the level, does the device follow the reading or the level?** The hardware test answers this *on average* over eight qubits a day. Whether calibration **patterns** say *when* each answer holds is unmeasured. | predictability README §3.5 ("the two-level-system picture ... the archive cannot tell"); hardware test design §1; NC-089 (the largest disagreements are dips) | the archive: every re-measurement event where reading and level disagree, labelled by what the next readings did; the hardware rows (8 per job, 14 jobs) as a check, far too few to train on | **closest**: it is the engineer's exact question at submission time, "carry the level or the reading for this qubit, this job" |
| (T-b) The chip-level readout series, the one calibration-table target with large same-time cross-sectional information (common-mode share 0.50) | predictability README §3.6a; strategy audit S5 and the appended note | one series of states; readout events every ~4.4 h | one step removed: it refines the readout source of every predictor, not the choice between them |
| (T-c) Exogenous covariates from the public archive (S6) | strategy audit S6: common-mode share 2% for gamma argues against an environmental driver | the public dataset's covariate columns, after ADR-029 | two steps removed, and the evidence leans against |
| (T-d) Arm B layout fidelity from per-qubit features | hardware test design §4, strategy audit §3.1 | six layouts a day for 13 days: tens of rows | a validation set for the fuzzy channel, not a training set for a network |

**The amendment proposes T-a as the primary target** and lists T-b as the second run under the
same protocol if T-a's step 0 shows the rows exist. T-c stays the hedge the strategy audit
called it; T-d is where the fuzzy channel is scored, not where a network is trained. Decision
A8's supervised-contrastive test (T14 on #110) is not a separate item: its labels are already
"classes of the change in the target", so if T-a passes clause 1 below, T14 reuses T-a's rows
and split, and if T-a fails clause 1 there is no class structure for T14 to contrast.

Why T-a is also the right "pattern" for the paper: if the hardware test passes S1, the paper's
engineering sentence is "carry the level"; T-a asks whether that sentence has a measurable
exception. If the hardware test fails S1 (the device does move between readings), T-a asks
whether the archive can tell a transient excursion from a real move, which is exactly what a
range-centred product would need to narrow. Either way the pattern detector adds a row to the
ladder the paper already reports, and the fuzzy rule base can absorb an interpretable pattern as
a rule (decision A6's neuro-fuzzy direction, kept as future work).

### 4.3 The pattern detector, defined

**Unit and label.** A row is a disagreement event: qubit `q`, re-measurement time `t`, with
`d(t) = log T1_reading(t) - log T1_level(t)` and `|d(t)| >= delta`, where `T1_level` is the
30-day geometric mean over distinct states (the pre-registration's definition) and `delta` is
fixed in step 0 from the archive's own scatter (the natural candidate is the 80% scatter already
registered, 0.37 log units, NC-084; step 0 records the choice and its row count before any model
output). *Correction, 2026-10-26, found by the advisor-brief session: the 0.37 in NC-084 is the
lambda forecasting cap, not a scatter. The 0.37 log-unit scatter is the 80% conformal half-width
of the shrinkage band on test change rows, 0.375 in the predictability README's ladder table, whose
register row is NC-085 (its cell quotes the rolling band's half-width, about 0.34). The hardware
test design §1 carries the same loose "NC-084, NC-085" citation and is owed the same note. The
value is unchanged; N0's README records the corrected source in its §7.* The label is

`y = 1` if the median of the next `k` re-measured values of `log T1_q` lies nearer
`log T1_reading(t)` than `log T1_level(t)` ("the reading became the level", a shift);
`y = 0` otherwise ("the reading was an excursion", a transient).

`k` is fixed in step 0; the candidate is `k = 5` (about five days of daily rounds, NC-091's
median gap 24.7 h), and the label uses re-measurement events, never files, so no-change rows
cannot inflate it (lesson L-027, in the skill's `LESSONS.md`). The level in `d(t)` is computed
from the window's states **excluding the event's own state**: the pre-registration's window
`(t_s - 30 d, t_s]` is inclusive at `t_s`, which is right for a predictor but would let the
reading under test pull its own reference; step 0 records this choice.

**Inputs** (all computable at `t` from the archive and nothing after): `d(t)` and its sign;
`|d(t)|` relative to the qubit's 30-day band width; the previous event's `d`; the qubit's
distinct-value count in the window; hours since the qubit's previous re-measurement; hours since
the last chip-wide `T1` sweep (PR #123's definition); the same-time `d` of `T2` and of readout
error for the qubit; the chip's same-time readout excursion (median `d_readout` over all qubits,
the common-mode signal of NC-086); the share of qubits with the same sign of `d` at `t`; the
qubit's `sx` and best `cz` error at `t`; hour of day. About a dozen features, `d` of them; the
list is frozen in step 0.

**Model.** A NumPy multilayer perceptron (decision A4, no new dependency): `d` inputs, one
hidden layer of `h` units with `tanh`, one sigmoid output, `(d + 2) h + 1` parameters, trained by
gradient descent on the log loss with early stopping on the last 20% of the training period in
time order; five seeds from `SeedSequence`, the median reported with the spread. `h` is chosen on
the same inner slice and recorded; nothing is tuned on the test period.

**Baselines**, all on the same rows and features:

- the **null**: the per-event conditional forecast under noise-around-a-level (section 4.4);
- two reference rows: the constant forecast `p_0` (the training base rate of `y = 1`) and the
  **"always level" rule**, `p = 0` for every row, the current design's implicit answer;
- **logistic regression** on the same `d` features, the strongest cheap baseline (lesson L-028:
  the bar is the best non-deep model the protocol produces, not the first one written down).

**Pattern extraction** (decision A2): permutation feature importance on the trained network and
on the logistic model, with 90% intervals from the seeds and the bootstrap; then scenario
enumeration over the discretised top features, reporting how many archive events each cell holds.
The output the paper can use is the ranked list and the cells, not the weights.

**Split and scoring.** The snapshot-boundary split at `2026-09-01T00:00:00Z`, as NC-080 to
NC-086, no event straddling it; training on events before, scoring on events after. Scores on
the test events: Brier score, log loss, AUC. Intervals by **block bootstrap over days** (156
qubits share each `t`, so row resampling understates the uncertainty; the predictability README
§2.1 item 5 has the same argument), 1,000 resamples, `SeedSequence`, 90% intervals, paired for
every difference between two models.

**Hardware check, descriptive only, after L2.** For each of #125's discriminating rows (eight
qubits a job), the detector's class at `t_s` against which predictor won on hardware for that
qubit. Reported as a sign-agreement count beside the archive result; never a training set, never
a second test.

### 4.4 Pass/fail rule, written before any row is counted

The rule has the shape the predictability README used, two clauses, both derived against the
null first (lesson L-029: a threshold a no-information model clears endorses the wrong
conclusion).

**The null, and why it is not a constant.** Under the model the archive supports so far, each
reading is the level plus independent scatter with no memory (lag-1 autocorrelation of
increments -0.49, NC-084). After a disagreement of size `|d|` the next `k` readings are the level
plus fresh scatter, and `y = 1` happens only when their median lands past the midpoint between
level and reading. That probability **falls with `|d|`**: with the qubit's scatter `sigma_q`, the
median of `k` draws has a spread of about `1.2 sigma_q / sqrt(k)`, so
`P(y = 1 | d) ≈ P(Z > |d| / (2 · 1.2 sigma_q / sqrt(k)))`. Two consequences the rule has to
absorb. First, `y = 1` is **rare under the null** (a few percent of events at the scatter the
archive shows), so the classes are heavily imbalanced and step 0 must count the `y = 1` events in
the test period before anything is scored. Second, and this is the trap, **`|d|` is on the feature
list and predicts `y` under the pure null**: a logistic model that knows only `|d|` posts a
positive Brier skill score against the constant forecast `p_0` with no pattern in the device at
all. A synthetic mutation check of the rule (no archive data; implementation doc, Verification)
confirmed both: the conditional probability drops by an order of magnitude between `|d| = 0.4`
and `|d| = 0.8`, and the `|d|`-only model's skill against the constant is positive. A constant
null would therefore have endorsed a "pattern" that is the label's own arithmetic (lesson L-029,
the exact failure the predictability rule's first draft had).

**The null forecast is per event.** For every event `i`, `p_null,i = P(y_i = 1 | d_i, sigma_q, k)`
under noise-around-a-level, by Monte Carlo from the qubit's own scatter `sigma_q` estimated on
its training-period increments (or the closed form above if Bengisu prefers it; both are
recorded). Its Brier score `BS_null = mean_i (p_null,i - y_i)^2` is what a model must beat. The
constant forecast `p_0` (Brier `p_0 (1 - p_0)`) and the "always level" rule (`p = 0`, Brier
`p_0`) are reported as reference rows, not as the null.

**Clause 1, a pattern exists.** The logistic model's Brier skill score against the conditional
null, `BSS_1 = 1 - BS_logistic / BS_null`, is at least **0.10** on the test events, with the paired
90% block bootstrap interval of `BS_null - BS_logistic` excluding zero. The 0.10 is a gap above a
null whose expected skill is exactly zero by construction, the same 10% margin the predictability
rule used; Bengisu's review may move it and the move is recorded before the run. (AUC is reported
beside it as description; it is not a clause, because the conditional null itself has an AUC
above 0.5 through `|d|`.)

**Clause 2, the network is needed.** The network's `BSS_1` exceeds the logistic model's by at
least **0.05**, with the paired 90% block bootstrap interval of the difference excluding zero,
for the seed median.

**Outcome table, in advance.**

| Clause 1 | Clause 2 | Reading | What the plan does |
| --- | --- | --- | --- |
| no | (not scored) | no calibration pattern says when a reading has become the level; the level is the rule without exception on this archive | the network item closes with a registered negative; the paper's ladder gains the row "pattern detector: none found"; #110 stays parked |
| yes | no | a pattern exists and a linear rule prices it | the logistic rule is adopted as an interpretable exception to "carry the level", a candidate fuzzy rule (A6); the network closes; one NC row |
| yes | yes | the network finds structure the linear rule misses | the network becomes a candidate stage-1 component of the third engine (A1); the hardware sign check at L2 comes before any paper sentence; the permutation ranking is the paper's pattern table |

**What "improves the paper's chances" means on the plan's clock.** The archive-only result (any
row of the table) can be in the ladder by gate L4, where the paper's draft starts, at zero QPU
cost. Anything hardware-grounded about the pattern is after L2. The audit cannot confirm Dr.
Akba's expectation; it makes it testable at a known cost, with the negative outcome written down
as a result the paper reports.

### 4.5 The steps, as gated tasks (to land on #110, the ticket the plan already reframed)

| Step | What | Owner (proposed) | Gate |
| --- | --- | --- | --- |
| N0 | protocol README in `docs/evidence/pattern-detector/`: rows, `delta`, `k`, the own-state exclusion in the level, features, split, the per-event null forecast and how `sigma_q` is estimated, both clauses, outcome table; committed before any model output; **count the rows** (events per split, `y = 1` events per split, base rate, events per qubit) and stop if the test period holds too few `y = 1` events for the bootstrap to resolve a 0.10 gap (the README states the minimum before counting) | Mert (protocol); Bengisu (statistics review, the same two questions as #125's: null value of each threshold, bootstrap unit) | the lead's go; Dr. Akba's ratification of the success rule through the advisor brief |
| N1 | baselines: null, "always level", logistic; results and rows committed | owner named at N0 | N0 |
| N2 | the network, five seeds, early stopping on the inner slice; results committed | same | N1 |
| N3 | the rule applied; permutation importance and scenario cells; one NC row per conclusion, Rule 7 form, laptop provisional | same | N2 |
| N4 | T-b (chip-level readout) under the same protocol, if N0 found rows and the lead says so | same | N3 |
| N5 | hardware sign check on #125's discriminating rows | Burak (scoring side) | L2 |
| N6 | desktop reproduction of N1 to N3 | Burak | N3 |

Cost, from the record: an archive collection costs about ten minutes on the laptop and one
`predictor_rows` call about a second (pre-registration support plan, 2026-10-24); a
`(d + 2) h + 1` parameter network on tens of thousands of events trains in minutes in NumPy.
The person-time is the protocol, its review and the write-up: one to two weeks of one person,
zero QPU. The scarce resource it spends is Dr. Akba's attention for the ratification, which is
why the brief must be triaged.

### 4.6 What the lead decides

1. **Adopt T-a as gated tasks N0 to N6 on #110**, or decline. Not a fourth lane: the plan's §3
   already reframed #110 and the A7 note (drafted, unposted) is where the team learns why the
   own-history route closed.
2. **The §4 stop rule.** Either amend it to "no deep-model *training* before L1; the protocol
   commit (N0) may be written now", or keep it as written and start N0 at L1. The audit
   recommends the amendment: N0 trains nothing, and writing it now means Dr. Akba's ratification
   can run in parallel with the hardware test instead of after it.
3. **The brief to Dr. Akba**: one Turkish cluster carrying the success rule for ratification and
   the A7 finding for information, triaged in the project's form. Drafted only on the lead's
   word; sent only by him.
4. **Who trains.** The plan's §7 already names Baha as overloaded and Burak owns the critical
   path; the audit proposes naming the owner at N0, not now.

### 4.7 The lead's decision, 2026-10-26

Mert Efe Şensoy, as the lead, in the session that produced this audit, after reading sections 1
to 4.6: "Yes, adopt tasks N0 to N6 on #110 and amend §4 so the protocol commit may be written now
with no training before L1." Recorded as given:

| Decision | Effect |
| --- | --- |
| N0 to N6 adopted as gated tasks on #110 | the pattern detector lands on #110 beside T0 to T14; #110 stays `priority:low` and parked for everything else; the post below carries the tasks to the ticket |
| §4 amended | the plan's first stop rule reads, from this date: no deep-model **training** before gate L1; the pattern detector's protocol commit (N0) may be written now. The amendment is a dated subsection appended to the plan on PR #124's branch, append-only, the rule's original text untouched |
| still open | the §4 stop rule's change is the lead's; the success rule's ratification is Dr. Akba's and goes through the advisor brief (section 4.6 item 3, drafting started on the lead's word 2026-10-26); the training owner is named at N0 |

**Done on the lead's word, later on 2026-10-26:** the §4.1 amendment was pushed as a fast-forward
onto PR #124's branch `mert/predictability` (`951258da..bf4c54e2`, the remote tip re-checked first),
and the post below went onto #110 as comment 6412965244 with the branch and commit named.

**The post for #110** (English, the ticket's language, with the Türkçe özet the ticket uses;
posted as drafted, plus the PR #124 commit reference):

> ## Pattern detector adopted as gated tasks N0 to N6 (2026-10-26)
>
> The phase-4 audit of 2026-10-26 (`docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md`,
> section 4) turns Dr. Akba's suggestion of a neural network for pattern detection into a
> pre-registrable item on this ticket. It is **not** the own-history forecaster of A7: that route
> is closed by NC-084 to NC-086 (PR #124). The target is "dip or shift": when a qubit's latest
> `T1` reading departs from its 30-day level by at least `delta`, do the next `k` re-measured
> values follow the reading or return to the level, and do calibration patterns at that moment
> say which. NumPy MLP (A4) against a per-event conditional null, the "always level" rule and a
> logistic regression on the same inputs; split `2026-09-01`; block bootstrap over days; two
> clauses written before any row is counted; the outcome table is in the audit.
>
> The lead's decisions, 2026-10-26: tasks adopted here; phase-4 plan §4 amended to "no
> deep-model training before gate L1; the protocol commit may be written now". The success rule
> goes to Dr. Akba for ratification (the deep-learning model is his under the 2026-10-13
> delegation).
>
> - [ ] **N0** protocol README in `docs/evidence/pattern-detector/` (rows, `delta`, `k`, own-state
>   exclusion in the level, features, per-event null forecast, both clauses, outcome table),
>   committed before any model output; the row and `y = 1` counts per split, with the minimum
>   stated first; statistics review by @bengisucvd (null value of each threshold, bootstrap
>   unit); Dr. Akba's ratification of the rule through the advisor brief. Owner: @mertefesensoy
> - [ ] **N1** baselines on the same rows and features: conditional null, constant `p_0`,
>   "always level", logistic; results and rows committed. Owner named at N0. Gate: N0
> - [ ] **N2** the network, five seeds, early stopping on the inner time slice. Gate: N1, and
>   **not before L1**
> - [ ] **N3** the rule applied; permutation importance and scenario cells; one NC row per
>   conclusion, Rule 7 form, laptop provisional. Gate: N2
> - [ ] **N4** the chip-level readout series under the same protocol, if N0 found rows and the
>   lead says so. Gate: N3
> - [ ] **N5** hardware sign check on #125's discriminating rows, descriptive only. Owner:
>   @BurakOztekin. Gate: L2
> - [ ] **N6** desktop reproduction of N1 to N3. Owner: @BurakOztekin. Gate: N3
>
> T14 (supervised contrastive learning) reuses N0's rows and split if N0 passes clause 1; if
> clause 1 fails there is no class structure for it to contrast.
>
> <details>
> <summary>Türkçe özet</summary>
>
> Dr. Akba'nın örüntü tespiti için sinir ağı önerisi, 2026-10-26 denetiminin 4. bölümünde
> ön-kayıtlı bir maddeye dönüştü ve bu bilete N0'dan N6'ya kadar kapılı görevler olarak eklendi.
> A7'nin kendi geçmişinden tahmin yolu değil (NC-084'ten NC-086'ya kapandı); hedef "düşüş mü,
> kayma mı": okuma seviyeden `delta` kadar ayrıldığında sonraki `k` ölçüm okumayı mı izliyor,
> seviyeye mi dönüyor, ve kalibrasyon örüntüleri bunu o anda söylüyor mu. NumPy MLP; olay
> başına koşullu boş model, "hep seviye" kuralı ve aynı girdilerle lojistik regresyon; bölme
> `2026-09-01`; gün blokları ile bootstrap; iki madde satırlar sayılmadan önce yazıldı. Liderin
> kararları: görevler kabul; plan §4 "L1'den önce eğitim yok, protokol commit'i şimdi yazılabilir"
> olarak değiştirildi. Başarı kuralının onayı Dr. Akba'nın.
>
> </details>

### 4.8 The lead's direction after the adoption, 2026-10-26

Given in the same session, after the §4.1 push and the #110 post, recorded as given: "to speed up
things I will do the tests that Burak needs to do first as well. We will start the neural model
and the fuzzy system later today. Then the rest of the team will do the housekeeping and make sure
everything I did is reproduced and reproducible at the end. Next session we will start building
so we are on builder mode."

What this changes in the tables above:

| Item | Before | After the lead's word |
| --- | --- | --- |
| #125 offline half (section 2.1 row 1, section 2.6 Burak) | Burak, NOT STARTED, the critical path | **Mert first**; Burak's part becomes the reproduction at the end. The design's ownership table (hardware test design §8) and the pre-registration's §6 row name Burak; both are owed a dated note when the lead's half lands |
| lane 3 housekeeping (section 2.3) | owners as planned | the team, after the lead's build; the 2026-10-31 date is unchanged and still AT RISK |
| the pattern detector (section 4.5) | N0 now; N1 and the network's code allowed by §4.1 | starts "later today": read as N0 (done 2026-10-26, protocol then counts), N1 and the network's code with synthetic checks; **N2 on the archive still waits for L1 under §4.1** unless the lead amends that line |
| the fuzzy system (lane 2) | resumes at L1 | starts "later today": PR-A1's mechanism can be built now (its plan is approved); its scoring row on the ladder still needs #64's D1 to D5 from Bengisu |
| verification | Burak's desktop batch owed (section 2.7) | the team reproduces everything the lead built, at the end; the same laptop-provisional rule applies until then |

The audit's headline 2 (the offline half is the critical path) stands; its owner changed.

## 5. What this audit did not do

- No new measurement on the archive, no new NC row, no edit to the plan or the pre-registration.
  The only computation run was the synthetic mutation check of clause 1's null (section 4.4),
  which touched no archive data and whose figures are not register claims.
- No post to GitHub, no push; this file and its implementation doc are on the session branch
  `claude/phase-4-audit-neural-network-526358` for the lead to review.
- The advisor brief of section 4.6 item 3 is not drafted.
- Lessons L-026 to L-031 cited above live in the `bengisu-quantum-math` skill's `LESSONS.md`,
  outside this repository; they are paraphrased where cited.

## 6. Related

- `docs/roadmap/2026-10-23-phase-4-plan.md` (PR #124's branch; the audited plan)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` (`mert/issue-125-preregistration`)
- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (PR #124's branch)
- `docs/findings/2026-10-23-strategy-audit.md` (PR #124's branch; S1 to S7, §3.1)
- `docs/evidence/predictability/README.md` (PR #124's branch; §2.1 the two-clause rule, §3.4
  applied, §3.5 and §3.6a what stays open)
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (PR #111's branch; decisions
  A1 to A9, task T14)
- `docs/advisor/2026-09-03-decisions-from-akba.md` (the 2026-10-03 arrangement and the
  2026-10-13 delegation)
- `docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md`
- Issues #125, #110, #122, #64; PRs #120, #121, #123, #124, #126, #127
