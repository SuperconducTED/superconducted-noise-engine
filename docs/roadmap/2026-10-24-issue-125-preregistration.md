# Pre-registration: hardware reading-versus-level test (#125)

**Date**: 2026-10-24 · **Author**: Mert Efe Şensoy · **Status**: **DRAFT, not frozen. Nothing
here is in force.** The commit that freezes it changes this line to "Frozen at `<commit>`" and is
made only after all of section 6 is done · **Design it freezes**:
`docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (approved by the lead 2026-10-23) ·
**Issue**: #125 · **Evidence**: `docs/evidence/hardware-reading-vs-level/` (NC-087 to NC-090)

## 1. What this document does

A pre-registration writes down, before any hardware result exists, exactly which qubits are
measured, how, and what result counts as a pass or a fail. Once frozen it is not edited; a change
after job 1 is a dated amendment that says what it changes and why, and the analysis reports both
the frozen rule and the amended one.

Most of the test is fixed by the approved design and is restated here unchanged. Four items are
**proposals** for the lead (section 3); they come from PR #126's dry run and from today's two
measurements. The lead's answers, Bengisu's statistics review and Burak's dry run are what turn
this draft into the frozen record. **The lead accepted all four on 2026-10-24** (section 3.5); the
draft stays unfrozen until the rest of section 6 is done.

## 2. What is frozen

| Item | Frozen value | Source | State |
| --- | --- | --- | --- |
| Backend | `ibm_fez` | design §1 | unchanged |
| Predictors | `reading` (latest file at or before `t_s`, or the live `backend.properties()` captured at `t_s`); `level` (geometric mean over the distinct states in `(t_s - 30 d, t_s]`, at least 5); `band` (10th to 90th percentile of the same window, NumPy linear interpolation); `reading_at_execution` (latest reading at `t_execute`, after the fact, the control) | design §2; implemented by `scripts/hardware_test_predictors.py` at `d62928fa` (PR #126) | unchanged |
| Archive ref per job | the `calibration-data` commit current at `t_s`, named in that job's manifest with the live document's SHA-256 | design §5; PR #126's manifest | unchanged |
| Arm A circuit | `X` on each selected qubit, `delay(tau)`, measure; all selected qubits in parallel in one circuit per delay; 2,048 shots | design §3 | unchanged |
| Arm A delays | **proposal C**: per qubit, `{0} ∪ {0.5, 1, 2} x T1_level ∪ {0.5, 1, 2} x T1_reading`, seven delays (six when the two are equal), rounded to the backend's `dt` | section 3.3, NC-087 | **accepted by the lead 2026-10-24** (section 3.5); replaces design §3's `{0, 0.5, 1, 2} x T1_level` |
| Discriminating stratum | **proposals A and B**: eight qubits, re-selected at every job's `t_s` (section 3.1, 3.2) | NC-088, NC-089 | **accepted by the lead 2026-10-24** (section 3.5); amends design §3 |
| Control stratum | **proposal D**: four qubits chosen once, before job 1, excluding only qubits below the floor and nothing that depends on a reading; never eligible for the discriminating stratum (section 3.4) | design §3's text; NC-088's control check | **accepted by the lead 2026-10-24** (section 3.5); changes PR #126's order |
| Arm B | six connected triples spanning `level`'s predicted fidelity, `ghz_state_circuit(3)` plus an idle block of `0.5 x` the layout's median `T1_level`, 4,096 shots | design §4 | unchanged |
| Schedule | one job per day for 14 consecutive days at a fixed UTC hour (**the lead names the hour**); job 1 is Arm A only | design §5 | unchanged |
| Budget | not a constraint (the lead, 2026-10-24); QPU time and queue delay are still logged per job | section 4 | replaces design §5's 25-second gate |
| Decision rule | design §7, verbatim: on Arm A's discriminating rows `level` beats both `reading` and `reading_at_execution` on mean absolute error, each with a paired bootstrap 90% interval excluding zero, the ordering holds in sign on the control stratum, and `band` covers its nominal 80% within a one-binomial-standard-error widening; Arm B passes if `level` or `band` ranks layouts at least as well as `reading` (Spearman) and picks the measured best at least as often | design §7 | unchanged; **under Bengisu's review** (section 6) |

## 3. The four proposals

### 3.1 A: which qubits may be discriminating, a floor inside the window

**Question.** The design admits a qubit to the discriminating stratum when it has "at least 20
re-measurement events in the archive"; PR #126 implements that as at least 20 distinct `T1` values
over all states up to `t_s`. At the dry run's instant qubit 72 passes that floor with 29;
qubits 11 and 17 have 52 and 89, and the other 153 between 130 and 152 (NC-088). PR #126's
record first gave "130 to 150 for the others"; a dated correction on its branch fixes that. Qubit 72's `T1` has
a history of omission from IBM's published calibration (ADR-017, NC-014) and has been published
again inside the dry run's window.

**Proposal.** Count distinct `T1` values **inside the 30-day window** the level is computed
from, and admit a qubit when that count reaches `k`. The reason is that the level is an average
over that window: a qubit whose `T1` was re-measured only a few times inside it has a level that
is mostly one value carried across many states, and the comparison would be against a stale
number, not against a level. A rule, not a name, so it applies the same way at every one of the
14 jobs.

**The floor's value: `k = 15`, proposed.** With a qubit's `T1` re-measured about daily, a
30-day window normally holds about 30 distinct values, and on the record it does: at the dry
run's instant 153 of the 156 qubits have 28 to 31 (NC-088). The other three are qubit 11 with 3,
qubit 72 with 6 and qubit 108 with 13 (half of qubit 108's window carries one value). A floor of
15 sits in that gap, at half the normal count.

**What it does on the record** (NC-088, every day at 12:00 UTC from 2026-06-13 to 2026-10-22,
132 days):

| Rule | Qubits excluded per day, median (range) | Days qubit 72 is admitted | Top-eight overlap with the current rule, median (minimum) |
| --- | --- | --- | --- |
| current, `N >= 20` | 1 (0 to 3) | 55 | 8 |
| window, `w >= 10` | 2 (1 to 3) | 14 | 8 (7) |
| window, `w >= 15` | 2 (1 to 3) | 0 | 8 (6) |
| window, `w >= 20` | 2 (2 to 7) | 0 | 8 (6) |

So the floor changes almost nothing except the qubits whose level is mostly one carried value:
qubit 72 never qualifies at 15, and at the dry run's instant qubit 108 (ranked second there) drops
out with it. `k = 20` does the same on most days but excludes up to 7 on some; `k = 10` still
admits qubit 72 on 14 days.

**Alternative the lead can choose instead.** Keep the design's floor (whole-archive, 20) and
admit qubit 72 when it qualifies; or keep it and exclude qubit 72 by name, recorded as a
judgement, not a rule.

### 3.2 B: balance the sign of the disagreement

**Question.** On 2026-10-23 every one of the eight selected qubits read below its level, by 0.58
to 1.71 log units. The design ranks by the size of the disagreement only.

**Proposal.** At each job, among the admitted qubits outside the control set: the four with the
largest `|d|` among `d < 0` and the four with the largest `|d|` among `d > 0`
(`d = log T1_reading - log T1_level`). If one side has fewer than four admitted qubits, the
remaining places go to the other side by `|d|`, and the job's log records it. The decision rule
stays pooled over the eight; a per-sign table is reported beside it as description, not as a
second test.

**Why.** Two reasons. Readings below and above the level need not behave alike: a dip can come
from a defect that couples to the qubit for a while, the record shows the two sides differ in
size (below), and a one-sided selection would answer the question for dips only. Second, the
residual lean of the near-neutral grids (proposal C, NC-087) runs toward the predictor with the
shorter `T1`, which is the reading on one side and the level on the other, so a balanced
selection cancels it in the pooled score to first order.

**How one-sided the design's rule is on the record** (NC-089, same 132 days). The largest
disagreements are dips: all eight selected qubits read below their level on 53 days and seven of
the eight on 40 more, although the share of admitted qubits (design's floor) below their level
has a median of 0.43 (0.22 to 0.75). On a pure `|d|` rule the test is a test of dips on most days.

**Cost.** No extra circuits: still eight qubits, still one circuit per delay. The price is
smaller disagreements on the upper side: among the qubits admitted under the design's
whole-archive floor (not proposal A's), the fourth-largest `|d|` above the level has a median of
0.44 log units (0.28 to 0.60) over the 132 days, against 0.57 for the eighth-largest overall,
the weakest the design's rule selects. Every day had at least four admitted qubits on each side.
0.44 is above the 0.37 the design's sensitivity argument assumes (§3, shots), so the upper side
keeps a gap of roughly the size the shot budget was sized for.

**Alternative.** The design's rule (largest `|d|` overall), with the sign composition of each
job reported.

### 3.3 C: the delay grid

**Question.** PR #126's record says the design's level-centred grid `{0, 0.5, 1, 2} x T1_level`
favours the level by construction. Measured, it is the other way round.

**What NC-087 shows.** Under the design's score (mean absolute error in `p_1` over the delays),
with the truth between the two predictions, a grid centred on one predictor favours the **other**
one, because the centred prediction sits on the steepest part of the decay curve, where the same
miss in `log T1` costs it the most. For the level-centred grid the tie point `a*` (0.5 is neutral,
above 0.5 favours the reading) is 0.539, 0.562 and 0.653 at a reading below the level by 0.75,
1.0 and 1.75 log units, and 0.513, 0.527 and 0.582 at a reading above it by the same amounts: it
favours the reading on both sides, so balancing (B) does not cancel it. The union of a
level-centred and a reading-centred grid gives 0.512, 0.515 and 0.526 below and the mirror image
(0.488, 0.485, 0.474) above. The midpoint grid `{0, 0.5, 1, 2} x sqrt(T1_reading T1_level)`
comes within 0.0003 of the union's tie point at every disagreement, with four delays. Shot
noise at 2,048 shots moves no tie point by more than 0.000004.

**Proposal.** The union grid, seven delays per qubit. With the budget not a constraint, the three
extra delays buy each predictor its own most sensitive points, and the residual lean is small and
cancels across signs under B. The bias against S1 that the design's grid would have carried
(a test that makes the level win only if it is clearly nearer the truth) is removed.

**Alternative.** The midpoint grid, which has the same residual lean with four delays; or the
design's grid kept, with its lean toward the reading stated in the results as a conservative
bias against S1.

**Input to the offline half.** The union grid's delays per qubit run from
`0.5 x min(T1_reading, T1_level)` to `2 x max(T1_reading, T1_level)`. Over the design rule's
eight on each of the 132 days (NC-090), the shortest non-zero delay had a median of 15 µs and went
as low as 0.84 µs (qubit 49 on 2026-09-18, a reading of 1.7 µs against a level of 116 µs), and
the longest had a median of 420 µs and reached 799 µs. Under proposal B the upper side's long end is
`2 x T1_reading` and can only be longer; that case was not measured. Rounding to `dt` and any
limit on circuit duration are Burak's to apply in the circuit builder; this document fixes the
grid, not its construction.

### 3.4 D: controls first, then the discriminating selection

**Question.** The design chooses the four controls "once, before the first job, as the
median-scatter qubits of the archive, without reference to any current reading". PR #126's CLI
chooses them after the discriminating eight and excludes those eight, which makes the controls
depend on that day's readings. And because the discriminating set is re-selected at every job,
a control could later become discriminating.

**Proposal.** Freeze the four controls first, at the `calibration-data` ref of the freezing
commit, with `propose_controls` excluding only the qubits below the discriminating stratum's floor
(and nothing reading-dependent; `propose_controls` keeps its own whole-archive floor of 20
underneath); exclude the four from the discriminating stratum at every job.

**What it does on the record** (NC-088, at the dry run's instant on `5828b4a2`,
`checkup-floor-controls.json`). Under the current floor the two orders give the same four, 105,
112, 48 and 140. Under a window floor of 15 both orders give the same four, in a different rank
order, with qubit 54 in place of 140: 48, 112, 54 and 105. The six qubits nearest the
median whole-archive scatter of `log T1` (0.2937) lie between 0.292 and 0.294, so which four come
out moves with who is eligible; any of them serves the control's purpose. With A and D both
accepted, the four at `5828b4a2` would be 48, 112, 54 and 105; the frozen four are whatever the
re-run at the freezing ref names.

### 3.5 The lead's decisions, 2026-10-24

Mert Efe Şensoy, as the lead and the owner of the QPU side, in this session on 2026-10-24: "I
accept proposals A to D as drafted (window floor 15, four below plus four above, the seven-delay
union grid, controls first)." Recorded as given:

| Proposal | Accepted as |
| --- | --- |
| A | the discriminating stratum admits a qubit when it has at least 15 distinct `T1` values among the states of its 30-day window, replacing the design's whole-archive floor of 20 (section 3.1) |
| B | at each job, the four admitted qubits with the largest `|d|` below the level and the four with the largest above it, a short side filled from the other and logged; the decision rule stays pooled (section 3.2) |
| C | the union grid, `{0} ∪ {0.5, 1, 2} x T1_level ∪ {0.5, 1, 2} x T1_reading`, seven delays per qubit (section 3.3) |
| D | the four controls frozen first at the freezing ref, excluding only qubits below the floor, and never eligible for the discriminating stratum (section 3.4) |

Accepting them does not freeze anything. The submission hour is still open, and the freezing
commit still waits on the rest of section 6. If Bengisu's review or Burak's dry run finds a
problem with any of the four, the change is recorded here as a dated note beside this one, not
by editing this table.

## 4. The budget

The lead stated on 2026-10-24 that the QPU budget is covered. The design's usage-page check of
the Open Plan allowance (§8) is no longer blocking, and the 25-second gate after job 1 (§5) is no
longer a gate. Job 1 is still Arm A only, as the first contact between the pipeline and the
hardware, and each job's QPU time and queue delay are still logged, because an engineer reading
the result needs to know what the measurement cost.

## 5. What is not decided here

- The fixed UTC submission hour (the lead).
- The second account named as the fallback for the daily cadence (design §8: a team member other
  than Mert, before job 2).
- Whether the S5 readout result changes the readout source of §2 (design §8, not blocking).

## 6. What the freezing commit waits on

| Item | Owner | State on 2026-10-24 |
| --- | --- | --- |
| Answers on proposals A, B, C and D | Mert | **done 2026-10-24**: all four accepted as drafted (section 3.5) |
| The fixed UTC submission hour | Mert | open |
| Statistics review of the decision rule (design §7) and of this draft; in particular the null-model value of each threshold (lesson L-029: derive what a no-information predictor scores before trusting a threshold), and the bootstrap's resampling unit (by job, since the qubits of one job share one device state, or by row) | Bengisu | open; review requested on PR #124 |
| The offline half of `scripts/hardware_reading_vs_level.py` (selection, circuits for both arms, scoring) and its dry run against Aer, committed | Burak | open; no branch yet |
| PR #120 merged | Bengisu or Burak to review | open, no review yet |
| PR #124 and PR #126 merged, so this document and its evidence land on `main` | reviews | open, no review yet |
| The controls re-run at the freezing ref (proposal D) | Mert | after the above |

## 7. Related

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design)
- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md`,
  `docs/implementations/2026-10-23-hardware-test-archive-side.md` (PR #126, the dry run)
- `docs/roadmap/2026-10-24-hardware-test-preregistration-support-plan.md` (this work's plan)
- `docs/evidence/hardware-reading-vs-level/README.md` (the two measurements' protocol and results)
- `docs/numerical-claims.md` NC-084, NC-085 (the scatter), NC-087 to NC-090
- Issue #125; the phase-4 plan `docs/roadmap/2026-10-23-phase-4-plan.md` lane 1
