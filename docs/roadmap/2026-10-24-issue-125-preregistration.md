# Pre-registration: hardware reading-versus-level test (#125)

**Date**: 2026-10-24 · **Author**: Mert Efe Şensoy · **Status**: **DRAFT, not frozen. Nothing
here is in force.** The commit that freezes it changes this line to "Frozen at `<commit>`" and is
made only after all of section 6 is done · **Design it freezes**:
`docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (approved by the lead 2026-10-23) ·
**Issue**: #125 · **Evidence**: `docs/evidence/hardware-reading-vs-level/` (NC-087 to NC-091)

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
| Schedule | one job per day for 14 consecutive days, submitted at **03:45 UTC (06:45 Istanbul)**; job 1 is Arm A only | design §5; section 3.6, NC-091 | hour **set by the lead 2026-10-24** (section 3.6) |
| Budget | not a constraint (the lead, 2026-10-24); QPU time and queue delay are still logged per job | section 4 | replaces design §5's 25-second gate |
| Decision rule | design §7, verbatim: on Arm A's discriminating rows `level` beats both `reading` and `reading_at_execution` on mean absolute error, each with a paired bootstrap 90% interval excluding zero, the ordering holds in sign on the control stratum, and `band` covers its nominal 80% within a one-binomial-standard-error widening; Arm B passes if `level` or `band` ranks layouts at least as well as `reading` (Spearman) and picks the measured best at least as often | design §7 | unchanged; **under Bengisu's review** (section 6) |
| Predictor implementation | the predictors' code at PR #132's merge commit (selection rules A, B and D added beside PR #126's functions, which are unchanged); the commit is named in the freezing commit | PR #132; section 3.7 | **amendment 13, 2026-10-28** (step 1c); replaces the `d62928fa` pin in the Predictors row, which predates #132 |
| Arm B eligibility | a qubit enters a triple when it has at least 15 distinct `T1` values inside its 30-day window (proposal A's floor); the four controls may sit in a triple | offline-half record; section 3.7 | **amendment 1, 2026-10-28**, decided by the lead; replaces design §4's "at least 20 events" |
| Arm B links | a coupled pair is a link only when its latest `cz` `gate_error` `r` gives `0 <= 4 r / 3 <= 1`; a dead pair (`gate_error = 1`) is not a link | offline-half record; section 3.7 | **amendment 9, 2026-10-28** |
| Arm B triples | connected triples `a - b - c` over the links, `b` the GHZ's control; every eligible triple predicted under `level`; the six chosen at ranks `round(i (n - 1) / 5)`, `i = 0..5`, of that list sorted best to worst, ties by the sorted qubit tuple | offline-half record; section 3.7 | **amendment 5, 2026-10-28**; fills design §4's "span the predicted fidelity" |
| Arm B prediction | per predictor, an Aer `NoiseModel`: `thermal_relaxation_error` on `sx` and `x` from that predictor's `T1`, `T2`; `RelaxationNoisePass` with the same arrays for the idle `delay`; exact probabilities from Aer's density-matrix method with final measurements removed; readout applied analytically as the product of per-qubit assignment matrices from the predictor's own `e_10`, `e_01`; no sampling in any prediction | offline-half record; section 3.7 | **amendment 2, 2026-10-28**; reads design §4's "density matrix" with "readout from the same source" |
| Arm B `cz` channel | a two-qubit depolarizing channel with `p = 4 r / 3` from the latest snapshot's `cz` `gate_error` `r`, no relaxation during `cz`, the same object for every predictor | offline-half record; section 3.7 | **amendment 3, 2026-10-28** |
| Band in Arm B | the fidelity interval from the band's two ends (`T1_lo` with `T2_lo`, `T1_hi` with `T2_hi`, level readout); layouts ranked by its midpoint; scored for coverage of the measured fidelity | offline-half record; section 3.7 | **amendment 4, 2026-10-28**; **under Bengisu's review** |
| Arm A schedule | each qubit's `x` and `delay` placed immediately before the one simultaneous measurement (`ibm_fez`'s `meas_map` is one group of 156), scheduled ALAP, so no qubit idles between its delay and its measurement | offline-half record; section 3.7 | **amendment 6, 2026-10-28** |
| Bootstrap unit | proposed: circular blocks of 3 consecutive UTC calendar days of submission, a missed job kept as an empty day (zero rows, zero loss), scores row-weighted; frozen after Bengisu's review | section 3.7 | **amendment 8, 2026-10-28, proposed, not frozen** |
| Written files | every JSON the selection and job scripts write uses LF line endings, so a hash recorded at write time is the hash every checkout sees | PR #132 (`bbde9522`); section 3.7 | **amendment 12, 2026-10-28**, done |
| Design §6, `rep_delay`, `init_qubits` | the `T1` characterisation on the first and last jobs, its environment and version, and the two submission options are step 1d's (the submission script), not this document's | section 3.7 | **amendment 7, 2026-10-28**, decided by the lead |
| Predictor implementation, the commit | `scripts/hardware_test_predictors.py` at `5c98f264dee8292e4b07de4e9074e833c487d9cb`, PR #132's merge commit | PR #132; section 3.10 | **amendment 14, 2026-11-05**; gives amendment 13's row its commit and corrects its "unchanged" |
| Controls file | `--mode controls` writes `requested_controls` and refuses to freeze fewer controls than requested; `load_controls` refuses a file without it, with a different number of controls, or with a duplicate or negative qubit; `--mode submission` refuses a control outside the pinned archive's qubit range | PR #132 (`3ed0728d`); section 3.10 | **amendment 15, 2026-11-05** |
| `rep_delay`, `init_qubits`, options | 500 µs with `init_qubits` on; dynamical decoupling and twirling off; classified measurement | section 3.11 | **amendments 16, 17, 2026-11-08** |
| Missed and failed jobs; how the job is fired | missed: not submitted by 04:45 UTC; failed: an IBM error, a cancellation, or still queued the next morning (the queue cap); no re-runs; an empty day. The laptop stays awake on mains every night | section 3.11 | **amendment 18, 2026-11-08** |
| Length of the run | always 14 days; nothing decided on what the scores show | section 3.11 | **amendment 19, 2026-11-08** |
| A qubit not operational at `t_s` | absent from the live target's `x`, `sx` or `measure`, or `x` or `sx` `gate_error` at least 1: no rows that morning; the next by the same rule in the discriminating stratum; left out of the control stratum; not eligible for Arm B; the job is not refused | section 3.11 | **amendment 20, 2026-11-08** |
| `T1` check delays; freeze guard; first day | eight delays evenly from 1 µs to three times `level` `T1`; `**Status**: **Frozen` and `**Controls SHA-256**` with `--frozen-at`; the first day declared in the freezing commit | section 3.11 | **amendments 21 to 23, 2026-11-08** |
| A4 | a calibration report on `tau > 0` discriminating rows with a same-width no-information band beside it; **not part of S1** | section 3.12 | **amendment 24, 2026-11-08**; replaces A4 in the "Decision rule" row |
| A1, A2 | batch means over days 1-4, 5-8, 9-11, 12-14, one-sided `t` at 5% with `q - 1` degrees of freedom; empty batches dropped while at least three remain; `sd = 0` fails; block 3 reported as a sensitivity | section 3.12 | **amendment 25, 2026-11-08**; replaces the paired bootstrap 90% interval |
| Arm B | paired Spearman difference over jobs 2-5, 6-8, 9-11, 12-14, batch means as for A1; "or band" dropped; best-pick, regret and near ties descriptive | section 3.12 | **amendment 26, 2026-11-08**; replaces B1 and B2 |
| Scores during the run | operations visible daily; scores, the interim report and the `T1` fit sealed until day 15; the data branch gets job ids and operations daily, the rest on day 15 | section 3.12 | **amendment 27, 2026-11-08** |
| Minimum completed jobs | at least 10 of 14 Arm A days and 10 of 13 Arm B jobs, and three non-empty batches per arm; otherwise inconclusive | section 3.12 | **amendment 28, 2026-11-08** |
| Readings, descriptive estimates | every outcome combination read in section 3.12's table; `c` and `s_res` registered as descriptive | section 3.12 | **amendments 29, 30, 2026-11-08** |

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

Accepting them does not freeze anything. The submission hour was set afterwards (section 3.6),
and the freezing commit still waits on the rest of section 6. If Bengisu's review or Burak's dry run finds a
problem with any of the four, the change is recorded here as a dated note beside this one, not
by editing this table.

### 3.6 The submission hour, 2026-10-24

The lead asked, on 2026-10-24 in this session, for a submission hour between 00:00 and 07:00
Istanbul time. Turkey keeps UTC+3 all year, so that window is 21:00 to 04:00 UTC every day of the
run. The jobs go out at minute :45, after the hourly poll at :37 (NC-008). Over the 162 days of
NC-091 (`recal-hours.tsv`), the seven hours in the window:

| Submit (Istanbul) | Submit (UTC) | Median hours since the last sweep | Sweep within 1 h | Within 3 h | Within 6 h |
| --- | --- | --- | --- | --- | --- |
| 00:45 | 21:45 | 14.6 | 8.6% | 18.5% | 30.9% |
| 01:45 | 22:45 | 12.8 | 6.2% | 13.6% | 25.3% |
| 02:45 | 23:45 | 12.9 | 3.7% | 12.3% | 22.2% |
| 03:45 | 00:45 | 13.0 | 3.7% | 12.3% | 21.6% |
| 04:45 | 01:45 | 12.6 | 4.9% | 11.7% | 20.4% |
| 05:45 | 02:45 | 10.7 | 3.7% | 9.9% | 16.7% |
| **06:45** | **03:45** | **10.0** | **3.1%** | **9.3%** | **16.7%** |

06:45 Istanbul is the best of the seven in every column (tied with 05:45 within 6 h), so the
draft records **03:45 UTC (06:45
Istanbul)** as the submission hour. In October most sweeps were published between 21:00 and 03:00
UTC (NC-091), which puts 03:45 UTC just after the usual sweep, if November keeps that pattern. It
is not guaranteed to: the sweep time moved between months. A queued job that runs after a new
sweep is still scored, and the `reading_at_execution` control shows how much that mattered.

### 3.7 Amendments of 2026-10-28 (step 1c), from the offline half and the #128 review

Appended 2026-10-28, before the freezing commit and before any QPU job. Building the offline half
(`scripts/hardware_reading_vs_level.py`, branch `mert/issue-125-offline-half`, record
`docs/implementations/2026-10-28-hardware-test-offline-half.md`) and dry-running it against Aer
showed where this draft and the design were silent or no longer exact. Each item is numbered as
that record numbers it; items that fix a value are also rows at the foot of section 2. The rows
above them are not edited.

1. **Arm B eligibility** (the lead, 2026-10-28). The design's "at least 20 events" was the
   whole-archive count NC-088 showed admits qubit 72 on stale values. Arm B uses proposal A's floor
   instead: at least 15 distinct `T1` values inside the 30-day window. The controls may sit in a
   triple, because Arm B is not selected on disagreement.
2. **Arm B readout.** The design says "density matrix" and "readout from the same source". The
   offline half reads both together: exact outcome probabilities from Aer's density-matrix method
   with the final measurements removed, then the predictor's own assignment matrices (`e_10 =
   prob_meas0_prep1`, `e_01 = prob_meas1_prep0`, per qubit) applied analytically. No prediction
   samples shots.
3. **The `cz` channel.** Two-qubit depolarizing with `p = 4 r / 3` from the latest snapshot's `cz`
   `gate_error` `r` (a two-qubit depolarizing channel's average gate infidelity is `3p/4`), no
   relaxation during the gate, the same object for every predictor, because the two-qubit gates are
   not under test (design §4).
4. **The band in Arm B.** The design scores the band in Arm A only. In Arm B it gets the fidelity
   interval from its two ends, is ranked by the interval's midpoint and is scored for coverage of
   the measured fidelity. For Bengisu's review.
5. **The triple rule.** "Span the predicted fidelity" is made exact: ranks `round(i (n - 1) / 5)`,
   `i = 0..5`, of all eligible triples sorted by `level`'s predicted fidelity, best to worst, ties
   by the sorted qubit tuple. One circuit per triple, so triples may share qubits.
6. **Arm A scheduling.** `ibm_fez` measures all 156 qubits in one group, so every measurement in an
   Arm A circuit is simultaneous. Each qubit's `x` and `delay` sit immediately before it, scheduled
   ALAP, so no qubit idles between its delay and its measurement; a test checks every scheduled
   interval equals the rounded `tau`.
7. **Design §6 moves to step 1d** (the lead, 2026-10-28): the `T1` characterisation on the first
   and last jobs, with its separate environment and version, belongs to the submission script, as
   do `rep_delay` and `init_qubits`. They are fixed in the freezing commit, not here.
8. **The bootstrap's resampling unit.** Section 6 left "by job or by row" open. Rows are not
   independent: the qubits of one job share one device state, and the levels of consecutive days
   share 29 of their 30 window days. Proposed, following Bengisu's lesson from PR #128 (resample
   blocks of consecutive calendar days, with empty dates kept): circular blocks of 3 consecutive
   UTC calendar days of submission; a missed or failed job is an empty day with zero rows and zero
   loss, never dropped; scores row-weighted. The block length 3 is a judgment, not derived; 1 (by
   job) is the alternative. Section 3.8 states what each choice does under a no-information null.
   Frozen after her review.
9. **Dead `cz` pairs.** Some couplings report `gate_error = 1.0`, which makes `4 r / 3` exceed 1. A
   pair is a link only when `0 <= 4 r / 3 <= 1`.
10. **Exercising the `reading_at_execution` control.** In the dry run the file at `t_execute` held
    the same calibration as the one at `t_s` (no sweep between 09:34 and 11:18 UTC), so the control
    equalled `reading` by fact and was not exercised. On hardware the control is what it is; a dry
    run meant to test it needs a `t_execute` after a sweep.
11. **Arm B's best-pick near-tie.** Under truth 2 the top three measured layouts were within 0.008
    of each other in fidelity, so the best-pick outcome turned on shot noise. For Bengisu's review
    of how Arm B is scored; section 3.8 states the null value of the best-pick condition.
12. **LF writes.** Every JSON the two scripts write uses `newline="\n"`, so a recorded hash is the
    hash every checkout sees (PR #132 `bbde9522`; the offline half's `write_json_lf`). Done.
    TSV outputs (`predictors.tsv`, the grid-bias files) are not covered and are written with CRLF
    on Windows; no hash of any of them is recorded.
13. **The predictor implementation pin.** Section 2's Predictors row names `d62928fa` (PR #126).
    The freezing commit names PR #132's merge commit instead, which adds proposals A, B and D beside
    PR #126's functions and leaves those unchanged.

**Bengisu's first #128 lesson, an open question for her.** On PR #128 she required that training
labels whose horizon crosses a split boundary be purged. This test fits nothing and has no split:
every prediction is computed from the archive at `t_s`, and the outcome is measured after it. What
it has in that lesson's place: the level's 30-day window must be complete at every `t_s` (the
`ibm_fez` archive starts 2026-05-13, so it is, by five months), and `reading_at_execution` is read after the fact and used
only as a comparison, never as an input. Whether that is a full answer is hers to rule on; it is
asked in the PR and not decided here.

### 3.8 What a no-information predictor scores on each threshold (protocol, 2026-10-28)

Written 2026-10-28 before any computation of it, as plan §8 requires for step 1c and as lesson
L-029 requires of any threshold: a threshold is read against what a predictor with no information
scores on it. The decision rule (section 2, design §7) has seven conditions. For each, the null
model and how its value is obtained:

| Condition | Null model | Value from |
| --- | --- | --- |
| A1: `level` beats `reading` on mean absolute error, discriminating rows, paired bootstrap 90% interval of the difference excluding zero | the two predictors equally accurate: the per-row error difference has mean zero | nominal 5% (one side of a 90% interval); the actual rate of the percentile bootstrap with 14 days in blocks is computed (below) |
| A2: the same against `reading_at_execution` | as A1 | the joint rate with A1 lies between 0.25% (independent) and the A1 rate (identical, when no sweep falls between `t_s` and `t_execute`); closed form |
| A3: the ordering holds in sign on the control stratum | `level` and each reading equally accurate on the controls | one half per comparison, between one quarter and one half for both; closed form |
| A4: `band` covers its nominal 80% within a one-binomial-standard-error widening | a band carrying no information about where `p_1` is | a band wide enough covers every row, so a no-information band passes with probability 1; coverage alone does not test the band, and the width scored beside it is not part of the condition; closed form, raised for Bengisu's review |
| B1: `level` or `band` ranks layouts at least as well as `reading` (mean Spearman over the 13 Arm B jobs) | (i) each predictor's ranking of the six layouts an independent uniform random permutation; (ii) all three rankings identical | (i) computed exactly (below); (ii) passes with probability 1, because "at least as well" passes on a tie |
| B2: picks the measured best at least as often | (i) each predictor's top layout right with probability 1/6, independently; (ii) identical picks | (i) computed exactly; (ii) probability 1 |
| B1 and B2 together | as B1 and B2 | computed exactly under (i), under both readings of "level or band": one predictor meeting both conditions, or each condition met by either |

**Computation.** A script, `docs/evidence/hardware-reading-vs-level/null_values.py`, committed
after this section and run once; output committed beside it.

- **B1, B2 and their joint, exactly.** For six layouts, enumerate all 720 rankings against a fixed
  measured order: each gives the sum of squared rank differences (`Spearman = 1 - 6 sum d^2 / 210`)
  and whether its top layout is the measured best. Convolve that joint distribution over 13
  independent jobs. A higher mean Spearman is a lower total `sum d^2`, so "at least as well" is
  `total_level <= total_reading`. With `reading`, `level` and `band` independent under (i), the
  pass probability is a sum over `reading`'s joint outcome. Reported: B1, B2 and the joint under
  both readings, for `level` alone and for "`level` or `band`".
- **A1's actual rate, by simulation.** Per-row error differences `D = u_day + e_row`, mean zero,
  with `u_day` an AR(1) series over 14 days (lag-one correlation `phi` in {0, 0.5}) and a share
  `rho` in {0, 0.3, 0.7} of the variance at day level; 56 discriminating rows a day (eight qubits,
  seven delays). For each case, 2,000 simulated runs, each with 2,000 circular block bootstrap
  resamples at block length 1 and at 3; reported: the share of runs whose 90% percentile interval
  lies wholly on `level`'s side, with its Monte Carlo standard error. Seeds from
  `numpy.random.SeedSequence(1251028)`, one child per case.

**What these values change.** Nothing by themselves: they are the reference Bengisu's review reads
the rule against. A condition whose null value is near 1 (A4 and B1, B2 under (ii)) cannot by
itself support a claim, and the rule is changed only by the lead after her review, as a dated
amendment here, before the freezing commit.

#### 3.8.1 The values, 2026-10-28

Appended after one run of `null_values.py` at `aa5dca1f` (exit 0; the Monte Carlo check of the
exact Arm B figures passed, every `|z|` under 4); output `null-values.json` committed at
`2b7c98f7`. Laptop, NumPy from the project's pins.

**A1, the share of no-information runs whose 90% interval clears zero on `level`'s side** (nominal
5%; Monte Carlo standard error 0.006 to 0.009):

| Day effects | Day share of variance `rho` | Block 1 (by job) | Block 3 |
| --- | --- | --- | --- |
| none | 0 | 0.068 (0.072 in the `phi` 0.5 case, the same model) | 0.088 (0.089) |
| independent days (`phi` 0) | 0.3 | 0.074 | 0.099 |
| independent days (`phi` 0) | 0.7 | 0.066 | 0.095 |
| AR(1), `phi` 0.5 | 0.3 | 0.186 | 0.156 |
| AR(1), `phi` 0.5 | 0.7 | 0.193 | 0.164 |

With 14 days the percentile interval is too narrow: a predictor with no edge clears it in 7% to
10% of runs when days are independent, and in 16% to 19% when consecutive days are correlated,
which consecutive 30-day levels make likely. Blocks of 3 cost size when days are independent
(fewer blocks) and help when they are correlated, without reaching 5%. So A1's real bar is about
two to four times looser than "90%" reads. A correction to section 3.8's A2 row: its 0.25% assumed
the nominal 5%; with A1's actual rate `r`, two independent comparisons both pass at about `r^2`
(0.4% to 3.7%), identical ones at `r`.

**Arm B under null (i), independent random rankings over 13 jobs:**

| Condition | `level` alone | `level` or `band` |
| --- | --- | --- |
| B1, mean Spearman at least `reading`'s | 0.505 (tie 0.010) | 0.672 |
| B2, best-pick at least as often | 0.606 (tie 0.212) | 0.758 |
| B1 and B2, one predictor meets both | 0.375 | 0.536 |
| B1 and B2, each by either | | 0.560 |

The "`level` or `band`" column treats `band` as independent of `level`; the band's midpoint comes
from the same 30-day window, so for that pair the realistic value lies between the `level`-alone
column and null (ii), not in the independent column. Under null (ii), identical rankings, every
row is 1. A predictor with no information passes Arm
B's condition as written more often than not, mostly because "at least as often" passes on ties
and best-pick counts over 13 jobs tie about one time in five. As written, Arm B cannot support a
claim on its own; with A4 (a wide band passes by construction), this is what Bengisu's review is
asked to rule on. The rule is not changed here.

### 3.9 The controls rehearsal, 2026-10-28 (not the frozen controls)

Proposal D freezes the four controls at the freezing commit's `calibration-data` ref, which does
not exist yet. To show the command works on this branch, `scripts/hardware_test_predictors.py
--mode controls` (PR #132's code, merged here) ran at `calibration-data` `7adda803` (the tip on
2026-10-28, 19:09 UTC) with `--at 2026-10-28T18:40:46Z`, the latest `ibm_fez` file there: 958
states, exit 0. Output in `docs/evidence/hardware-reading-vs-level/controls-rehearsal-2026-10-28/`
(`controls.json` blob `b75a92f7`, SHA-256 prefix `a48a8c99`).

It names **144, 110, 140 and 77**, with qubits 11, 72 and 108 below the window floor. At NC-088's
instant on `5828b4a2` the same rule named 48, 112, 54 and 105. That the four move is what section
3.4 expected: the candidates nearest the median scatter lie within a few thousandths of each other
(here 0.2909 to 0.2917 around a median of 0.2913), so any change in the archive reorders them. It
is why the controls are frozen once, at the freezing ref, and never re-chosen. These four are not
frozen and are not used by any job.

### 3.10 Amendments of 2026-11-05, after PR #132's merge

Appended 2026-11-05, before the freezing commit and before any QPU job. PR #132 merged as
`5c98f264` and `main` was merged into this branch as `a433e66b`. Neither amendment below changes a
decision rule, a threshold or a null value of section 3.8.1. The rows and sections above are not
edited.

14. **The code pin, and a correction to amendment 13.** PR #132's merge commit, which amendment 13
    said the freezing commit would name, is `5c98f264dee8292e4b07de4e9074e833c487d9cb`. The foot of
    section 2 now carries it; the freezing commit restates it, and moving it takes another dated
    amendment. The pin covers `scripts/hardware_test_predictors.py`. The offline half is not in that
    commit, so its own commit is named at the freezing commit, after PR #140 merges.

    Amendment 13 says #132 leaves PR #126's functions unchanged. That was not exact. Compared
    definition by definition from `d62928fa` to `5c98f264`, 14 of the 24 top-level definitions are
    unchanged and 10 changed, for two reasons this document had not named:

    - **The fix Mert made for Bengisu's review of PR #126** (`22495d97`, on `main` through #126's
      merge `2e2801cd`), which `d62928fa` predates. A live document must name `ibm_fez` and may arrive as a raw
      `to_dict()` body. A snapshot whose qubit entries are not lists of objects is a parse error. A
      live document whose qubit block was already seen at any time up to `t_s` adds no state, where
      before it was checked against the window only. That last change can move `level` and `band`,
      only on the live path, and only when the live block repeats a state older than the window.
    - **PR #132 itself.** `predictor_rows` counts `n_window_distinct`, a new column that proposal A's
      floor reads and no predictor value is computed from; `write_outputs` writes JSON with LF
      (amendment 12); `main` gains the new modes.

    The expressions that compute `reading`, `level` and `band` are the same at both commits, and
    with no live document the values cannot differ.
15. **The controls file.** Burak's review commit `3ed0728d`, part of #132's merge, tightens the file
    that decides the control stratum (section 3.4). `--mode controls` writes `requested_controls`
    and refuses to freeze fewer controls than requested. `load_controls` refuses a file with no
    `requested_controls`, a non-positive one, a number of controls that differs from it, or a
    duplicate or negative qubit. `--mode submission` refuses a control outside the pinned archive's
    qubit range. So a freeze that cannot find four controls stops, where before it would have run
    with a short stratum. The rule that chooses the controls does not change.

    The section 3.9 rehearsal's `controls.json` predates that commit, has no such field and is
    refused by today's code. It stays as committed, because it is not frozen and no job uses it. The
    frozen file is written by the pinned code, so it has the field.

### 3.11 Amendments of 2026-11-08, from the submission script (step 1d)

Appended 2026-11-08, before the freezing commit and before any QPU job. The code is PR #142
(`mert/issue-125-submission`), named at the freezing commit. None of these changes a threshold or a null value; section
3.12 does that. The rows and sections above are not edited; section 2's foot gains a row for each. Amendment 7 gave
`rep_delay`, `init_qubits` and the `T1` characterisation to step 1d, and 16, 17 and 21 are what step 1d fixed.

16. **`rep_delay`.** 500 µs with `init_qubits` on, refused at submission if outside the live `rep_delay_range`. The lead's
    decision, 2026-11-05.
17. **Options fixed explicitly.** Dynamical decoupling off, gate and measurement twirling off, classified measurement.
    Decoupling would put pulses inside Arm A's `delay`; twirling would change the circuits the forecasts were computed for.
    Local testing mode ignores these, so job 1's `job.inputs` is their first real check.
18. **Missed and failed jobs.** Missed: not submitted by 04:45 UTC, including a build that began in time and finished late.
    Failed: an IBM error or cancellation, or still queued when the next morning's routine reaches it, when it is cancelled;
    this is also the queue cap. No re-runs. The day stays on the calendar with no rows (amendment 8). The lead's decision,
    2026-11-05. **How the job is fired** (the lead's decision, 2026-11-08): the laptop stays awake on mains every night of
    the run, logged in, lid open, never put to sleep. On 2026-11-08 a deliberate sleep showed that the task's wake timer
    does not wake this laptop from Modern Standby (the job ran only when the laptop was woken by hand), while an awake,
    idle laptop fired the routine at 06:45:00 and it completed. A night the laptop sleeps through is therefore a missed day
    under this amendment, never a late job. The submission script's record (PR #142) holds both attempts; its criterion 8
    was restated for the awake case after the first attempt, and says so.
19. **Always 14 days.** The run neither stops early nor extends on what the scores show; an outside reason, such as
    `ibm_fez` being retired, is not covered by this rule and is reported as what it is. Amendment 27 seals the scores until
    day 15. What the rule protects, under the batch-means rule of amendment 25 and section 3.8's null model
    (`docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/`, N7, at `1a220220`): looking once at day 14 passes
    A1 for a predictor with no information 0.047 to 0.080 of the time across the six cases; stopping at the first look that
    passes gives 0.114 to 0.152 when looks start at day 9.
20. **A qubit that is not operational at `t_s`.** A qubit is not operational when it is absent from the live target's `x`,
    `sx` or `measure`, or when its `x` or `sx` `gate_error` in the live properties document is at least 1. It gives no rows
    that morning, and the job is not refused on this ground:

    - It is not a candidate for the discriminating stratum, so proposals A and B rank the remaining candidates and the next
      qubit by the same rule takes the place.
    - A frozen control that is not operational is left out that day. It is not replaced, and the frozen set still stays out
      of the discriminating stratum. A3 uses the control rows that exist; if the whole run has none, A3 is not met.
    - It is not eligible for an Arm B triple, as a dead `cz` is not a link (amendment 9).
    - The qubits affected are logged in that job's `selection.json`.

    **Why this rule.** On every archived capture up to `calibration-data` `fafbc8f5` (2,706 captures over 170 UTC days; N8, run at
    `315ecdc9`, output committed at `1a220220`), no qubit was ever absent from the target, while `ibm_fez` marked qubits 17, 72 and 149 dead by `x` and `sx`
    `gate_error` 1 and left them in it: qubit 72 on every capture, 17 on 208 in two spans, 149 on 6. A check of the target
    alone would have nothing to fire on. What keeps such qubits out today is proposal A's floor, indirectly: a qubit that
    dies during the run with a fresh `T1` would stay above the floor for about 15 days (about 30 distinct values, floor 15),
    and frozen controls are never re-checked. The record has no such case, so this closes a gap in the rule rather than a
    measured rate. A register row for these counts is drafted below; its id is allocated at merge.

    **Why it cannot favour a predictor.** It reads only the device's status at `t_s`, never a result, and treats `level`
    and `reading` alike. Refusing the job instead would be just as blind, but one death could empty the rest of the run,
    and amendment 19 forbids extending it. **Not covered:** a qubit that dies after `t_s` while the job is queued keeps
    its rows. An earlier draft of this amendment refused the job when a selected qubit was missing from the target, and said
    refusing was the one choice that could not bias the result; the lead replaced it on 2026-11-07, because nothing is frozen
    yet, so a rule written now is the frozen rule.
21. **The `T1` check's delays.** The design fixes eight delays and 1,024 shots but not their spacing: evenly from 1 µs to
    three times the qubit's `level` `T1`.
22. **The status line the guard reads.** Section 1 says the freezing commit writes "Frozen at `<commit>`", which cannot name
    its own hash. The guard requires `**Status**: **Frozen` and `**Controls SHA-256**: <hash>`, with the frozen commit passed
    as `--frozen-at`.
23. **The first day is declared.** The run's first calendar day is written in the freezing commit and passed to `report`.
    Job `n` runs on day `n`, whatever happened before it. The report's calendar is the declared 14 days, so a missed first
    or last day stays on it.

**Drafted register row (id allocated at merge).** "`ibm_fez` reports a dead qubit by leaving it in the target with `x` and
`sx` `gate_error` 1: on 2,706 captures to `calibration-data` `fafbc8f5`, no qubit absent from the target; qubits 17, 72, 149
marked dead (72 on every capture). Source: `rule-revision-2026-11-08/dead_qubits.py`, run at `315ecdc9`; `dead-qubits.json` at `1a220220`.
Laptop, provisional."

### 3.12 Amendments of 2026-11-08, from the statistics review

Appended 2026-11-08, before the freezing commit and before any QPU job. @bengisucvd's statistics review of this branch at
`51e9f425` (CHANGES_REQUESTED, 2026-11-07, posted on her behalf from her account) led to the lead's decisions of
2026-11-07 and 2026-11-08, stated in his reply on this PR (comment 6710293101). Her figures are cited by her commit,
`bengisu/pr135-review-evidence` at `5a7f5c58` (`docs/evidence/pr135-statistics-review/`), whose outputs were re-run in a
separate folder on 2026-11-07 and matched byte for byte, except `harness_checks` and `astcmp2`, which were not re-run; they
are seeded, so this rules out an environment problem, not a logic error. The values the new rules owe are in
`docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/` (protocol `315ecdc9`, results `1a220220`). The rows and
sections above are not edited. **These amendments change the decision rule** and replace the corresponding parts of section
2's "Decision rule" row and of design §7 as this document restates them; the design file itself is not edited.

24. **A4 becomes a calibration report, not a gate.** Both ends of the band take `level`'s readout (`sources_from_rows`), so
    at `tau = 0` the band has zero width, and a one-standard-error widening covers that point at most `P(|Z| <= 1) = 0.683`
    of the time; design §3 calls `tau = 0` "the readout-only control". In her scenario F, where `T1` at execution is the next
    changed archived reading, A4 as written passed 0.005 of 14-day windows with those rows and 0.475 without them. On
    `tau > 0` rows the band was well calibrated, so a pass-or-fail threshold at 80% flips a coin in the world where the band is
    the honest product. **From now:** `tau = 0` rows leave A4; A4 reports, on the discriminating stratum, the band's coverage
    with and without the one-standard-error widening and its mean width; beside it, the coverage of a band with no information,
    proposed here for her review: for each row, the row's own band is moved in `log T1` by the difference between another
    discriminating qubit's `log level` and the row's own, so its width and its place relative to `level` are kept, and is
    turned into `p_1` at the row's own `tau` with the row's own `level` readout; the row's no-information coverage is the
    share of the other discriminating qubits of that day for which this moved band covers `p_hat`. Her simulation instead
    centred a band of the same `log T1` width on one random other qubit's `level`, which gave 0.821, 0.653 and 0.270 in her
    scenarios N, F and S; this version is deterministic and keeps the band's asymmetry. The band's calibration is its own registered finding at L2. **S1 is decided on A1, A2 and A3**, and a pass
    reads "most of the deviation from the level is gone by execution", not "the truth sits near the level".
25. **A1 and A2 are decided by batch means.** For each discriminating row `D = |p_hat - p_level| - |p_hat - p_other|`, with
    `other` being `reading` for A1 and `reading_at_execution` for A2; negative favours `level`. The 14 run days form four fixed
    batches: days 1-4, 5-8, 9-11 and 12-14. A batch's value is the mean of `D` over its discriminating rows (row-pooled, as
    amendment 8 says). With `q` non-empty batches, `t = mean / (sd / sqrt(q))`, `sd` with `q - 1` degrees of freedom. The
    condition passes when `t < -t_{0.95, q - 1}` (`t_{0.95, 3} = 2.3533634348018233`, `t_{0.95, 2} = 2.9199855803537242`);
    `sd = 0` fails. **Empty batches (the lead's decision, 2026-11-08):** a batch with no discriminating row is dropped, and
    with at least three non-empty batches the test uses them with `q - 1` degrees of freedom; with fewer, the condition is
    inconclusive. Ibragimov and Müller 2010 (doi:10.1198/jbes.2009.08046) give the construction. **What a predictor with no
    information scores** (section 3.8's model, N1 and N2 at `1a220220`): 0.050 to 0.052 with independent days and 0.049 to
    0.081 with correlated days at full calendar; with up to four missed days, random or consecutive, 0.045 to 0.081, never
    above the full-calendar value of its case by more than Monte Carlo noise, and never inconclusive. Her review measured the
    real series too: 0.083 and 0.108 in her scenarios N and F with the mean removed, against 0.169 and 0.196 for block 3 at 90%.
    **What it costs** (her `a1_a3_joint`, full calendar): S1 passes 0.472 at `a = 0.6`, against 0.660 for block 3 at 90%,
    and 0.976 in F. The block 3 bootstrap stays as a reported sensitivity, not a decision.
26. **Arm B is decided by a paired Spearman difference.** For each Arm B job, `Delta = rho_level - rho_reading`, each
    predictor's Spearman correlation with the measured fidelity over the six layouts; positive favours `level`. The 13 Arm B
    jobs form batches of jobs 2-5, 6-8, 9-11 and 12-14, which are not Arm A's day batches. Batch means and the empty-batch
    rule as in amendment 25; the condition passes when `t > t_{0.95, q - 1}`; `sd = 0` fails, so identical rankings
    (null (ii)) fail by definition. "Or band" is dropped: the band's midpoint and `level` picked the same top layout 0.992 of
    the time in her review. Best-pick, regret and the number of near ties (a best-to-second gap under two shot standard
    deviations) are descriptive. The band is reported in Arm B with its coverage (amendment 4). **No information:** 0.0505
    under null (i) (N4 at `1a220220`), 0.047 under her realistic null; 0.047 to 0.052 with up to three missed jobs. **Cost:**
    0.709 in her scenario F, against 0.937 for the rule as written ("`level` or `band`"), which a predictor with no
    information passed about 0.42 of the time.
27. **Operations visible, scores sealed until day 15** (the lead's decision, 2026-11-07, partly reversing his 2026-11-05
    "visible every day"). Each morning shows job status, QPU seconds, queue delay, row counts, and whether the `T1` check ran
    and its fit converged. The scores, the interim report and the `T1` fit's values are written to a sealed folder that is
    not opened until day 15. The data branch receives, daily, only job ids and that operational summary; raw results, scores
    and the `T1` fit are committed on day 15 (the lead's decision, 2026-11-08), so the team cannot read scores early either.
    Gate L1 reads job 1's QPU cost from the operational summary. Amendment 19 stands.
28. **Minimum completed jobs** (the lead's decision, 2026-11-08). The run counts as a test only with at least 10 of the 14
    Arm A days and at least 10 of the 13 Arm B jobs completed, and at least three non-empty batches in each arm; otherwise the
    result is inconclusive and nothing is read. This is exactly the measured range (N2 to N4 at `1a220220`: up to four missed
    days, up to three missed jobs).
29. **The section 7 reading of every outcome.** S1 is read from A1, A2, A3 and the sign of A2's mean `D` (amendment 25:
    negative favours `level`). The rows are read top to bottom, and the first row that applies is the reading:

    | Outcome | S1 reading |
    | --- | --- |
    | Fewer completed jobs than amendment 28 asks | Inconclusive: nothing is read. |
    | A1, A2 and A3 pass | S1 passes: `level` beats both readings, and most of the deviation is gone by execution. A4 reports how well the band is calibrated; `c` and `s_res` (amendment 30) say how much of the scatter is physical. |
    | A1 and A2 pass, A3 fails | S1 not supported: the controls disagree in sign. The discriminating result is reported as specific to the selected qubits, with no claim about the chip. |
    | A2's mean `D` at or above zero | S1 fails: `reading_at_execution` is at least as good as `level`, so the scatter is what the device does between readings (design §7). |
    | A1 passes, A2 does not | Staleness: `level` beats the submission-time reading but not, by the rule, the execution-time one (design §7). |
    | A1 and A2 both fail, both mean `D` below zero | No claim: the data do not separate the predictors. The estimates are reported, not read. |
    | Anything else | Reported as observed, with no S1 reading. |

    Arm B adds to the S1 reading and never changes it:

    | Outcome | Added reading |
    | --- | --- |
    | S1 passes and Arm B passes | S1 passes for the engineer's purpose too: `level` ranks layouts better than `reading` (design §7). |
    | S1 passes and Arm B does not | S1 holds for decay prediction, not for ranking layouts: the engineer's-purpose claim is not made. |
    | Arm B passes and S1 does not | No claim from Arm B alone. |
    | Arm B inconclusive under amendment 28 | Nothing is added. |

    The likeliest non-pass in her scenarios, A1 to A3 passing with the band not covering 80%, is now an S1 pass whose band
    finding is reported separately.
30. **`c` and `s_res`, registered descriptive estimates.** From the same rows and no new circuits: per qubit and day, `log T1`
    is fitted by binomial maximum likelihood from the six `tau > 0` rows with `level`'s readout (her `arm_a_fit.py`: a grid of
    1,201 values of `log(T1 / level)` from -3 to 3). `c` is the slope through the origin of `log T1_fit - log level` on
    `d = log reading - log level`, on the discriminating stratum; `s_res` is the robust spread of the residual, the 10th to
    90th percentile range divided by `2 z_0.9`. Named readings: `c` near 0 and `s_res` near the fit noise is her scenario N;
    `c` near 1 is S; `s_res` well above the fit noise is physical scatter. In her simulation, `c` over the whole 137-day series is 0.000 in N,
    0.141 in F and 0.979 in S; the median `s_res` over 14-day windows is 0.013 in N and 0.324 in F. On hardware `s_res` will sit above the simulated fit
    noise, which has no non-exponential decay or readout-induced transition. They are not part of the decision rule.
31. **The block length's reason.** Amendment 8 called block length 3 "a judgment, not derived". Her review measured the
    dependence it guards against on the real selected rows: a lag-one correlation of the daily score difference of 0.33 and
    0.34 in scenarios F and N, from qubits re-selected when no sweep arrived. Block 3 is now a sensitivity report (amendment
    25), and this is its reason.
32. **Section 3.8.1's block 3 values understate the scorer.** `null_values.py` cuts each bootstrap draw to 14 days, while
    PR #140's `calendar_block_bootstrap` keeps all 15 drawn days. On the same draws (N6 at `1a220220`), the scorer's version
    passes a predictor with no information 0.006 to 0.011 more often in every case (0.107 against 0.099 with no day effects).
    The scorer is unchanged and section 3.8.1 is not edited; its block 3 rows should be read with this correction.
33. **Amendment 14's wording.** Where it says the old logic "can move `level` and `band`", it should read "can move `level`,
    `band`, the window counts and `log_disagreement`, and so eligibility and the discriminating selection": her review found
    that on a live document repeating a state older than the window, the old logic changed `level` in 778 of 780 rows,
    `n_window_distinct` in 438 and `log_disagreement` in 770.
34. **A bad live document is a missed job.** It stops the run (`LiveDocumentError`, exit 2), while a bad archived document is
    counted and skipped; on a job day the first is a missed morning under amendment 18.
35. **A null `configuration` reaches the dry run, not a real morning.** 788 of 2,398 archived files have `configuration` null
    (backfilled documents, by design), and `archived_backend` raises on them. A real morning's `build` reads the configuration
    from its own live capture, and nothing on `score`'s path reads it (from reading PR #142's code; not run against IBM). The
    rehearsal already picks a file with a configuration, and says so.

### 3.13 What this branch still owes before the freezing commit

The code for these amendments belongs on PR #142, not here: amendment 20's is built there; 24 to 30 and 34 are still to build. The lead asks @bengisucvd to read sections 3.11 and 3.12
before the freezing commit: they are the rule the two of them agree, and her review's proposals are now written in his words.

## 4. The budget

The lead stated on 2026-10-24 that the QPU budget is covered. The design's usage-page check of
the Open Plan allowance (§8) is no longer blocking, and the 25-second gate after job 1 (§5) is no
longer a gate. Job 1 is still Arm A only, as the first contact between the pipeline and the
hardware, and each job's QPU time and queue delay are still logged, because an engineer reading
the result needs to know what the measurement cost.

## 5. What is not decided here

- The submission hour is set: 03:45 UTC, 06:45 Istanbul (section 3.6).
- The second account named as the fallback for the daily cadence (design §8: a team member other
  than Mert, before job 2).
- Whether the S5 readout result changes the readout source of §2 (design §8, not blocking).

## 6. What the freezing commit waits on

| Item | Owner | State on 2026-10-24 |
| --- | --- | --- |
| Answers on proposals A, B, C and D | Mert | **done 2026-10-24**: all four accepted as drafted (section 3.5) |
| The fixed UTC submission hour | Mert | **done 2026-10-24**: 03:45 UTC, 06:45 Istanbul (section 3.6) |
| Statistics review of the decision rule (design §7) and of this draft; in particular the null-model value of each threshold (lesson L-029: derive what a no-information predictor scores before trusting a threshold), and the bootstrap's resampling unit (by job, since the qubits of one job share one device state, or by row) | Bengisu | open; review requested on PR #124 |
| The offline half of `scripts/hardware_reading_vs_level.py` (selection, circuits for both arms, scoring) and its dry run against Aer, committed | Burak | open; no branch yet |
| PR #120 merged | Bengisu or Burak to review | open, no review yet |
| PR #124 and PR #126 merged, so this document and its evidence land on `main` | reviews | open, no review yet |
| The controls re-run at the freezing ref (proposal D) | Mert | after the above |

### 6.1 As of 2026-10-28 (step 1c)

Appended; the table above is the 2026-10-24 state and is not edited.

| Item | Owner | State on 2026-10-28 |
| --- | --- | --- |
| Proposals A to D, the submission hour | Mert | done 2026-10-24 (unchanged) |
| PR #120, #124, #126 merged; this document on a branch rebuilt onto `main` | reviews | **done**: all three merged; `main` (`695c90ca`) merged into this branch 2026-10-28 |
| Selection rules A, B and D in code (PR #132) | Mert; Burak reviews | open, CI green, not reviewed; merged into this branch so the controls command exists here (stacked); the freezing commit names #132's merge commit (amendment 13) |
| The offline half and its Aer dry run | Mert (the lead took it over on 2026-10-26, plan §8.2); Burak reproduces on his desktop | built on `mert/issue-125-offline-half`; dry run passes its five criteria under both truths; PR after #132 merges; desktop reproduction owed |
| The twelve offline-half amendments and the pin | Mert | written in section 3.7 and section 2's foot |
| Null-model value of every threshold | Mert computes; Bengisu reviews | protocol in section 3.8; values after its script runs |
| Statistics review of the decision rule, the amendments, the bootstrap unit (amendment 8) and the open label-horizon question | Bengisu | to be requested on this branch's PR |
| The controls re-run at the freezing ref (proposal D) | Mert | a rehearsal at the current `calibration-data` tip on this branch (not frozen); the frozen run is in the freezing commit |
| The submission script: `build` and `score` modes, `rep_delay`, `init_qubits`, design §6's `T1` characterisation | Mert | step 1d (amendment 7) |
| The second account for the daily cadence | Mert names it | before job 2 (section 5) |

### 6.2 As of 2026-11-05

Appended; the tables above are not edited.

| Item | Owner | State on 2026-11-05 |
| --- | --- | --- |
| Selection rules A, B and D in code (PR #132) | Mert; Burak reviewed | **done**: approved by Burak, merged as `5c98f264`, on this branch through `a433e66b` |
| The offline half and its Aer dry run (PR #140) | Mert; Burak reviews and reproduces on his desktop | the re-run after #132's merge passes its five criteria under both truths (laptop, provisional); review and desktop reproduction owed; its commit is named at the freezing commit |
| Amendments 1 to 15 and the pin | Mert | written in sections 3.7 and 3.10 and section 2's foot |
| Null-model value of every threshold | Mert computes; Bengisu reviews | computed (section 3.8.1); review owed |
| Statistics review of the decision rule, the amendments, the bootstrap unit (amendment 8) and the open label-horizon question | Bengisu | requested on this branch's PR, opened 2026-10-28 UTC; no review yet |
| The controls re-run at the freezing ref (proposal D) | Mert | the frozen run is in the freezing commit; the section 3.9 rehearsal stays a rehearsal |
| The submission script: `build` and `score` modes, `rep_delay`, `init_qubits`, design §6's `T1` characterisation | Mert | step 1d (amendment 7), not built |
| The second account for the daily cadence | Mert names it | before job 2 (section 5) |

### 6.3 As of 2026-11-08

Appended; the tables above are not edited.

| Item | Owner | State on 2026-11-08 |
| --- | --- | --- |
| The offline half (PR #140) | Mert; Burak reviews and reproduces | review found no code error and holds for his desktop dry run; not merged |
| The submission script (PR #142) | Mert; Burak reproduces | draft; amendment 20's rule built; amendments 24 to 30 and 34 still to build there; criteria 10 and 11 re-run after that; criterion 8 met for the awake laptop |
| Amendments 16 to 35 | Mert | sections 3.11 and 3.12; the lead's decisions of 2026-11-07 and 2026-11-08 |
| Values the new rules owe | Mert | measured: `rule-revision-2026-11-08/` at `1a220220` |
| Statistics review | Bengisu | done 2026-11-07 (CHANGES_REQUESTED); her reading of sections 3.11 and 3.12 is owed |
| The controls re-run at the freezing ref (proposal D) | Mert | after the above |
| The second account for the daily cadence | Mert names it | before job 2 (section 5) |

## 7. Related

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design)
- `docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md`,
  `docs/implementations/2026-10-23-hardware-test-archive-side.md` (PR #126, the dry run)
- `docs/roadmap/2026-10-24-hardware-test-preregistration-support-plan.md` (this work's plan)
- `docs/evidence/hardware-reading-vs-level/README.md` (the two measurements' protocol and results)
- `docs/numerical-claims.md` NC-084, NC-085 (the scatter), NC-087 to NC-091
- Issue #125; the phase-4 plan `docs/roadmap/2026-10-23-phase-4-plan.md` lane 1
