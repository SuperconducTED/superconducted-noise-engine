# Three engines and the deep model · plan as of 2026-10-04

Written 2026-10-04 against `main` at `110cfad` and `calibration-data` at `43607a2`. This is
a dated planning document: reconcile it later by appending an as-of section, never by
editing the text below (`docs/team.md` documentation conventions). Every figure here
either cites a row in `docs/numerical-claims.md`, names the file and ref it was read from,
or is labelled **provisional** with its sample basis. A provisional figure is a planning
observation, not a result, and the task that re-measures it is named next to it.

Tracking issue: Issue #110.

## 0. Where this comes from

**Dr. Akba's direction.** Between 2026-09-29 and 2026-10-02 Dr. Akba approved, in person,
the team-decides process and the decisions of all six 2026-09-09 brief files as
@mertefesensoy presented them (recorded in `docs/advisor/2026-09-03-decisions-from-akba.md`
by PR #98, which is open at the time of writing). He set a direction: **three engine
modes**, Type-1 fuzzy, Interval Type-2 fuzzy and a deep-learning model, with the deep model
to be planned in detail with him in the week of 2026-10-05. That much is in the register.

**The method, as the lead reported the conversation on 2026-10-04.** The register does not
hold this detail; @mertefesensoy's account of the conversation does, and task T0 records
that account in the register alongside Dr. Akba's answers to §9. In that account, Dr. Akba
asked how many parameters and features we have, said the combinations of those features
should be enumerated to see how many scenarios can occur, and that the deep model is then
run according to that. After that, the important features are separated from the
unimportant ones, feature engineering follows, and the model is built on top of that as a
second layer. Also by that account, Dr. Akba leaves the model architecture to the lead.

**The architecture decisions.** The lead took these on 2026-10-04, and this plan is built
on them:

| # | Decision | Taken |
| --- | --- | --- |
| A1 | **Two-stage deep model.** Stage 1 is trained on all candidate features and ranks them; stage 2, the third engine, is trained on the engineered subset. The T1 and IT2 fuzzy engines keep their own inputs. | 2026-10-04 |
| A2 | **"Permutation" means both steps, in order:** first enumerate scenarios (combinations of discretized feature levels) and measure how many the archive occupies; then, on the trained stage-1 model, permutation feature importance. | 2026-10-04 |
| A3 | **Sample unit, staged.** Stage A works per snapshot (one row per distinct device state), comparable with today's fuzzy engines. Stage B moves to per-qubit rows once the engine can emit per-qubit noise. | 2026-10-04 |
| A4 | **NumPy by hand.** No new dependency; the deep engine stays inside ADR-005's spirit, as File 02 Q1d proposed. | 2026-10-04 |
| A5 | **Band by split conformal prediction**, because the comparison's primary metric is the band (File 05 Q1a on Issue #84). | 2026-10-04 |
| A6 | **Future work, recorded and not built:** (a) the stage-1 ranking selects the inputs of all three engines; (b) a stacked neuro-fuzzy model, where the deep network's hidden layer feeds the fuzzy rule base. | 2026-10-04 |

## 1. The three engines

| | E1 · Type-1 fuzzy | E2 · Interval Type-2 fuzzy | E3 · Deep model |
| --- | --- | --- | --- |
| Role | Control arm, parameter-matched (File 02 Q1b) | The thesis: the claim is the uncertainty band (File 02 Q1) | Third engine mode (Dr. Akba's direction) |
| Model | TSK grid; `TriangularMF` or `TanhBellMF` | TSK grid; `IntervalGaussianMF` | Two-stage NumPy MLP (§2) |
| Parameters | 243 (NC-046) | 243 (NC-046) | Matched by hidden width (§4) |
| Point output | Weighted average | Textbook Nie-Tan (File 02 Q2) | Network output |
| Band | Open (see §1.1) | Karnik-Mendel interval (File 02 Q2) | Split conformal (§2.4) |
| Inputs | Today's three features | Today's three features | All candidates (stage 1), engineered subset (stage 2) |
| Tickets | #60 trainer, #62 ablation | #60, #61, #64 | Issue #110 |

**What all three share, so the comparison isolates the engine.** The same training target
(ADR-027: the snapshot target in stage A, the per-qubit target in stage B), the same
time split, the same downstream layers (squashing, Kraus projection, Aer), the same
circuits and metrics (band coverage and width first, Hellinger as the point metric; File
05 Q1a and Q1b), and the same test: paired Wilcoxon signed-rank at alpha = 0.05 over
snapshots x circuits (File 02 Q1b).

### 1.1 One band question this plan raises and does not settle

Split conformal works on any point predictor, so the same few lines can give E1 a band,
which would close File 02's open "comparable band" item. But a conformal band is
calibrated on exchangeable data by construction, while E2's Karnik-Mendel band is not. If
E1 and E3 are conformalized and E2 is not, the comparison partly measures calibration
method rather than engine. Two consistent options: conformalize all three, or compare all
three raw and report coverage. This goes to the 2026-10-05 week meeting (§9).

## 2. The deep model, stage by stage

### 2.1 Stage 0: inventory and scenarios (Dr. Akba's first question)

**Feature inventory (task T1).** List every scalar the IBM properties document carries,
and for each: whether it varies over time, which date it first appears, and whether it
duplicates another field. Register the result.

What planning already saw, **provisional**: 60 snapshot files taken by position from the
1,697 `ibm_fez` files at `calibration-data` `43607a2`. They are files, not distinct states,
and several may be one state. T1 replaces this with a registered measurement.

| Group | Observation (provisional) |
| --- | --- |
| Per-qubit, time-varying, full history | `T1`, `T2`, `readout_error`, `prob_meas0_prep1`, `prob_meas1_prep0`, and one single-qubit gate error (`sx`) |
| Duplicates | `id`, `rx`, `x` and `xslow` gate errors equal `sx`'s on every compared qubit; `measure` gate error equals `readout_error` |
| Partial history | `init_error` from 2026-08-04; `measure_2` fields from 2026-08-13; `measure_reset` fields from 2026-09-03 |
| Step-like (few distinct values) | `readout_length`, `measure` and `reset` gate lengths |
| Constant | most gate lengths; `rz` error; `jq` couplings |
| Per edge, time-varying | `cz` and `rzz` gate errors; `zz` terms; `lf` terms (field not yet identified) |

Partial-history fields need a missing-data rule before they enter any model. That is ADR-017's
skip strategy, and old 2026-05-25 question Q5 (skip versus fuzzy maximum entropy).

**Scenario enumeration (task T2).** For a feature set of size `n`, discretize each feature
into `L` levels and count:

- theoretical cells, `L^n`;
- occupied cells, the number of distinct level-combinations present in the archive;
- samples per occupied cell (minimum, median, maximum).

Level edges are tertiles (`L = 3`) computed on the training portion of the time split
only, so no information leaks from later snapshots. Run it per snapshot in stage A and
per qubit in stage B. Two reasons it matters. It bounds what any engine can learn: an
engine evaluated in an empty cell is extrapolating, and the band should be read with that
in mind. And at `L = 3` the cell count is exactly the rule count a grid fuzzy engine would
need on those features (today's 3 features give 27 cells and 27 rules).

### 2.2 Stage 1: the screening model

| | |
| --- | --- |
| Rows | Stage A: one per distinct device state, from Issue #63's training-set builder at its pinned archive ref. 740 distinct states exist at `43607a2` (`health/metrics.json`, `states_total`, generated 2026-10-03T09:15Z; provisional until #63 registers its own count). |
| Inputs | Every candidate from T1 that has full history, aggregated over usable qubits (mean, and a spread statistic to be chosen in T1). Standardized with training-portion statistics only. |
| Target | ADR-027's snapshot target, `(gamma, lambda)`: `SnapshotTarget.mean` |
| Model | NumPy MLP, one or two hidden layers, `tanh` or ReLU; Adam; early stopping on a validation slice of the training portion |
| Output | A ranked list of features by permutation importance (§2.3). Stage 1 is not an engine and is never compared. |

### 2.3 Permutation feature importance

For a trained model `f`, a held-out set `(X, y)` and loss `L`, the importance of feature `j`
is the mean rise in loss when column `j` is shuffled, over `R` independent shuffles:

```
I_j = (1/R) * sum_{r=1..R} [ L(f, X with column j permuted by shuffle r) - L(f, X) ]
```

It is computed on held-out data, never on the training rows, and reported with its spread
over the `R` shuffles. **Known weakness, planned for:** when two features are correlated
(`T1` and `T2` are the obvious pair), shuffling one leaves its information in the other,
and both look unimportant. T5 therefore also runs **grouped** permutation, shuffling a
correlated group together, with groups set by a correlation threshold chosen before the
run.

### 2.4 Feature engineering, then stage 2: the third engine

**Feature engineering (task T6).** From the ranking: drop what does not matter, keep what
does, and test a short list of transforms decided before looking at stage-2 results, such
as logarithms of coherence times, rates `1/T1` and `1/T2`, and the ratio `T2/T1`. Each
choice is written down with the ranking that justified it. The result is the engineered
set `F*`.

**Stage 2 (task T7).** A NumPy MLP on `F*`, parameter-matched to the fuzzy arms (§4),
trained on the same split. Its output `(gamma, lambda)` goes through the same squashing,
Kraus and Aer layers as E1 and E2.

**The band: split conformal prediction.** Hold out a calibration slice `C` of the training
portion, `|C| = n`. For each output separately, compute residual scores
`s_i = |y_i - f(x_i)|` on `C` and take

```
q_hat = the ceil((n + 1)(1 - alpha))-th smallest of s_1 .. s_n
band(x) = [ f(x) - q_hat , f(x) + q_hat ]
```

On exchangeable data this covers the true value with probability at least `1 - alpha`. The
time split deliberately breaks exchangeability. Whether coverage holds on later snapshots
is exactly the drift question File 02 Q1a makes primary, so the measured coverage is a
result, not a formality.

## 3. Sample unit: stage A, then stage B

| | Stage A · per snapshot | Stage B · per qubit |
| --- | --- | --- |
| Row | One distinct device state | One qubit in one distinct state |
| Rows available | 740 at `43607a2` (provisional, see §2.2) | About 740 x 156 = 115,440, **not independent**: the 156 rows of one state share a calibration run |
| Target | `SnapshotTarget.mean` | `QubitTargets` (already in `training/targets.py`) |
| Features | Aggregates over qubits | Each qubit's own values, plus its incident-edge `cz` / `rzz` errors |
| Splits | By time | By time, and never splitting one state's qubits across train and test |
| Precondition | Issue #63's builder | The engine emits per-qubit noise, which it does not today (§5) |

Stage A comes first because it is comparable with E1 and E2 as they exist. Stage B is where
a deep model has room to learn, and where most of the inventory exists at all.

## 4. The parameter budget

Fuzzy arms (NC-045, NC-046): 234 for `GaussianMF`, 243 for `TriangularMF`, `TanhBellMF`
and `IntervalGaussianMF`. A one-hidden-layer MLP with `d` inputs, `h` hidden units and 2
outputs has

```
params = (d + 1) * h + (h + 1) * 2 = (d + 3) * h + 2
```

With today's `d = 3` that is `6h + 2`: `h = 39` gives 236 (File 02 Q1d), `h = 40` gives 242.
At `d = 3` no integer `h` gives exactly 234 or 243. Other widths can hit 234 (`d = 5`,
`h = 29`), but 243 needs `(d + 3)h = 241`, and 241 is prime, so no network with a real
hidden layer reaches it. **The matching rule, fixed now:** choose `h` so the count is the
nearest to 243 without exceeding it, and report both counts. Stage 2's `d` is `|F*|`, so
its `h` is set after T6.

**Why the fuzzy arms cannot simply take every feature.** A grid rule base on `d` features
at 3 membership functions has `R = 3^d` rules and `count = 2 * R * (d + 1) + sum_j p_j`
parameters (the NC-045 formula). On the 6 full-history per-qubit features of §2.1 that is
729 rules and `2 * 729 * 7 = 10,206` consequent parameters, a floor near 51,000 states by
NC-012's five-per-parameter rule. The archive holds 740. This is arithmetic on the
registered formula, not a measurement, and it is why future-work item A6(a) needs the
stage-1 ranking first.

**The floor applies to every engine.** NC-012's rule is five samples per trainable
parameter. At stage A, 740 states are below the 1,170 floor of a 234-parameter model, and
below the 1,215 floor of a 243-parameter one. The dashboard projects the 1,170 crossing on
2026-11-25 (`health/metrics.json` at `43607a2`; a projection, not a measurement). Every
engine's result carries the same claim gate. The gate does not stop the work.

## 5. The architecture seam

Today `FuzzyNoiseModel` hard-wires the fuzzy path:
`features -> rule_base.evaluate -> defuzzifier.defuzzify -> squashing.squash`
(`FuzzyNoiseModel._compute_crisp_params` in `integration/aer_factory.py`, lines 269-273 at
`110cfad`).
A deep model has no rule base and no defuzzifier, so it cannot be plugged in without a new
interface.

**Proposed (task T8, needs its own ADR, id assigned at merge):** a parameter-model ABC in
`interfaces.py` with one job, `features -> raw (gamma, lambda)`. The TSK path, rule base
plus defuzzifier, becomes one implementation and the MLP another. The noise model takes a
parameter model and a squashing strategy, so everything downstream is shared by
construction. Constraints:

- `interfaces.py`'s primary owner is Dr. Akba and the secondary is @mertefesensoy
  (`docs/team.md`). A new ABC is a cross-cutting change, so it needs the lead's approval
  plus Burak or Bengisu.
- `integration/aer_factory.py` is @BurakOztekin's module.
- `fuzzy/tsk.py` and `channels/kraus.py` stay LOCKED and untouched.
- The MLP and its trainer are a new module under `training/`. A new module needs an
  ownership row in `docs/team.md`.

Stage B additionally needs the noise model to attach per-qubit channels, which ADR-021's
factory does not do today. That is a second, later ADR.

## 6. The ledger, as tasks (no ADR is edited by this plan)

| Record | Change | Task |
| --- | --- | --- |
| ADR-005 | Append a dated scoping note: the decision text binds the trainer; the deep engine is also hand-written NumPy by the lead's decision A4, so no ML framework enters | T9 |
| ADR-013 | Append a revisit note: feature engineering moves from "deferred until the floor" to stage-1-driven, citing Dr. Akba's direction and decisions A1 to A3 | T9 |
| New ADR | The three engine modes and the parameter-model seam (§5) | T8 |
| New ADR (later) | Per-qubit noise emission for stage B | T10 |
| `docs/numerical-claims.md` | One row per reported conclusion (the granularity rule): the inventory, the scenario counts, the importance ranking, stage-2 results | T1, T2, T5, T7 |

## 7. Tasks, in order, with gates

Gates are artifacts or decisions; dates are the ambition (the phase-3 plan's §5 rule). The
`Phase 3 · ANFIS results` milestone ends 2026-10-31.

| Task | What | Gate (done when) | Needs |
| --- | --- | --- | --- |
| T0 | Plan review with Dr. Akba | His answers to §9, and the lead's account of the method (§0), recorded in the decisions register in a PR after #98 merges | This plan |
| T1 | Feature inventory, registered | NC row; the §2.1 table re-measured over distinct states at a pinned ref | T0 |
| T2 | Scenario enumeration, stage A | NC row: theoretical, occupied, samples per cell | T1 |
| T3 | NumPy MLP core: forward, backprop, Adam, early stopping | Tests, including a finite-difference gradient check in the style of #61 | T0 |
| T4 | Stage-A dataset | #63's builder at its pinned ref, extended with T1's features | #63, T1 |
| T5 | Stage 1 training and permutation importance, single and grouped | NC row for the ranking, with its spread | T3, T4 |
| T6 | Feature engineering, `F*` | Each kept, dropped or transformed feature justified in writing | T5 |
| T7 | Stage 2 and its split-conformal band | Trained engine; band coverage on the calibration slice | T6 |
| T8 | Seam ADR and parameter-model ABC; MLP as an implementation | ADR merged; all three engines run through one noise-model path | T3 |
| T9 | ADR-005 scoping note and ADR-013 revisit note | Both appended, with the lead's recorded approval | T0 |
| T10 | Stage B: per-qubit inventory, scenarios and noise emission | Its own ADR and tasks, planned after stage A | T7, T8 |
| T11 | Three-engine comparison | Band interval score and Hellinger, paired Wilcoxon, on the time split, in `docs/findings/` with NC rows | T7, T8, #58, #62, #64 |

Verification is batched on @BurakOztekin's desktop (`docs/team.md`): every number above is
provisional until it appears in a batch record.

## 8. Risks

| Risk | Why it bites | Mitigation |
| --- | --- | --- |
| Too little data at stage A | 740 rows for a ~240-parameter model, below every floor | Report at the measured count; the claim gate is stated, the work proceeds; stage B adds rows |
| Correlated per-qubit rows | 156 rows per state are not 156 samples | Split by state and time; count states, not rows, for any floor |
| Correlated features fool permutation importance | `T1` and `T2` share information | Grouped permutation, groups fixed before the run |
| Conformal coverage under drift | Exchangeability fails on a time split | That failure is the measurement; report coverage per horizon |
| Hand-written backprop bugs | No autograd | Finite-difference gradient check as a gate on T3 |
| Unfair band comparison | Conformal versus Karnik-Mendel calibration | §1.1, decided with Dr. Akba |
| Inexact parameter matching | `(d + 3)h + 2` rarely hits 243 | The matching rule in §4, both counts reported |
| Phase 3 ends 2026-10-31 | T5 to T11 depend on #58, #62, #63 and #64 | The milestone records late as late; gates do not move |

## 9. Questions for Dr. Akba (week of 2026-10-05)

The architecture is the lead's. These are the questions that are his:

1. Is permutation importance, single and grouped, the importance method he intends, or did
   he have another in mind?
2. The band comparison (§1.1): conformalize all three engines, or compare all three raw
   and report coverage?
3. Is the deep model a co-equal engine in the paper's claim, or the baseline the thesis
   must beat?
4. Stage B: inside this paper, or future work?
5. The missing-data rule for partial-history fields: skip, or fuzzy maximum entropy (old
   question Q5)?
6. The two future-work proposals (A6): worth naming in the paper?

## 10. Future work (A6), recorded and not built

- **(a) The stage-1 ranking selects the inputs of all three engines.** Fairer inputs, and
  the only way a grid fuzzy engine reaches beyond three features (§4).
- **(b) Stacked neuro-fuzzy.** The deep network's hidden layer is the input to the fuzzy
  rule base: one hybrid model.

## 11. Sources

`docs/decisions.md` at `110cfad` (ADR-005, ADR-013, ADR-017, ADR-021, ADR-027);
`docs/numerical-claims.md` (NC-012, NC-045, NC-046);
`docs/implementations/2026-09-09-training-floor-derivation.md` (the per-shape table);
`docs/team.md` (ownership); Issue #84's File 02 and File 05 team decisions;
`calibration-data` `43607a2` (`health/metrics.json`, snapshot files);
`src/superconducted/integration/aer_factory.py`, `src/superconducted/training/targets.py`
and `src/superconducted/calibration/features.py` at `110cfad`; PR #98 (Dr. Akba's
approval and direction in the decisions register).
