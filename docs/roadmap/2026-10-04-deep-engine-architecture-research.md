# Architecture strategy for the deep engine · research as of 2026-10-04

Written 2026-10-04 against `main` at `110cfad` and `calibration-data` at `43607a2`. This is
a dated research document: reconcile it later by appending an as-of section, never by
editing the text below. It serves the plan
`docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` and Issue #110. Every archive
figure is **provisional**, with its ref and sample basis named; the plan's tasks T12 and
T13 register them.

**Why this exists.** Dr. Akba asked the lead to research which architectural strategy the
deep model should follow, naming supervised contrastive learning and reinforcement
learning as examples, using what the lead knows about this project (the lead's account of
the 2026-10-04 conversation; plan §0). The lead set the scope on 2026-10-04: four
families (contrastive and representation learning, reinforcement learning, forecasting
with drift-robust bands, structure- and physics-aware models), judged on science first
with NumPy feasibility flagged (decision A4).

**How it was done.** Four independent research passes, one per family, each given the
same problem statement and asked to argue fit against it rather than for its family.
Every citation had to carry an arXiv ID or DOI fetched in that pass. Afterwards all 67
identifiers were resolved again on 2026-10-04: the 62 arXiv IDs against the arXiv API and
the 5 DOIs against Crossref, and every returned title matched. The load-bearing content
claims (§3) were checked against each paper's own abstract. The method-level claims in §2
and the one-line relevance notes in §8 are the research passes' reading of each paper, and
were not each re-read.

## 0. The two findings that decide everything else

**1. A same-snapshot target leaks, so the task is forecasting.** ADR-027's target is a
closed-form function of the same state's `T1`, `T2` and gate length. A model asked for a
state's own target learns a known formula. The plan's decision A7 (§2.0 there) therefore
makes the deep engine forecast: inputs at `t`, target at `t + h`.

**2. The archive re-measures `T1` and `T2` far less often than it records states.**
Measured 2026-10-04 over all 1,697 `ibm_fez` snapshot files at `calibration-data`
`43607a2` (provisional; a research pass found it, and it was re-measured independently):

| Quantity | Value |
| --- | --- |
| Distinct `T1` value-vectors across the files | 132 |
| Distinct `T2` value-vectors | 132 |
| Consecutive file pairs in which the `T1` vector changes | 131 of 1,696 |
| Distinct modal per-qubit `T1` measurement dates | 132 |
| Gap between consecutive modal dates (hours) | min 3.9, median 24.7, max 134.2 |

The `sx` gate length did not change across the files the plan's §2.1 inventory sampled (it
is 24 ns; phase-3 plan §3), so the target changes only when `T1` or `T2` is re-measured.
The archive's 740 distinct states (`health/metrics.json`) are distinct over the whole
per-qubit block, so most of them differ only in faster-updating fields such as readout
and gate errors, not in `T1` or `T2`. Three consequences follow, and every family below
has to live with them:

- **The forecasting data is about 131 transitions, not 740 rows.** A
  re-measurement period (an *epoch*) is the unit. Stage A has one series of about
  131 steps; stage B has 156 such series.
- **Within an epoch, persistence is exactly right.** Most consecutive states repeat the
  previous `(gamma, lambda)`.
- **The planned split-conformal band can pass while covering nothing.** If the fraction `f`
  of calibration residuals that are exactly zero satisfies `f >= 1 - alpha`, the conformal
  quantile is zero and the band has zero width. It then reports coverage near `f` while
  covering no change at all. Counted over files, `f` is about 0.92. The fix is the
  evaluation protocol, not a cleverer band: rows are epochs, `h` counts epochs, coverage is
  scored on change events, and the paired Wilcoxon runs over epochs x circuits.

## 1. Verdicts by family

| Family | Strongest candidate here | Verdict | The deciding reason |
| --- | --- | --- | --- |
| Contrastive and representation | Rank-N-Contrast on the *change* in `(gamma, lambda)`, as an auxiliary loss on stage 2 | Conditional | Only the change is learnable; a contrastive loss on the raw future label relearns persistence. SupCon needs class labels and would bin a continuous target. |
| Reinforcement learning | None as the engine | Does not fit | IBM publishes the next calibration whatever we predict, and the realized target scores every possible forecast. The problem is online supervised learning; RL only adds variance. |
| Forecasting with drift-robust bands | A linear forecaster on lags, shared across qubits, with adaptive conformal inference | Recommended for version-1 evaluation | Simple forecasters beat deep ones on short series, and adaptive conformal keeps long-run coverage without exchangeability |
| Structure and physics | A grey-box residual: forecast log decay rates as a baseline plus a learned correction, then apply ADR-027's formula | Recommended for version-1 evaluation | It keeps the physics fixed, learns only drift, and can guarantee `T2 <= 2 T1` by construction |

## 2. Each family in detail

### 2.1 Contrastive and representation learning

- **Supervised contrastive learning (SupCon)** pulls together samples that share a class.
  Our target is continuous, so it would have to be binned, which throws away the ordering.
  Under forecasting with the raw future label as "class", it learns persistence.
  **Poor fit on paper.** The lead decided on 2026-10-04 to test it anyway, because Dr. Akba
  raised it, and a measured answer beats an argued one. §2.1a sets out a test fair enough
  to settle it.
- **Rank-N-Contrast (and ConR, SupReMix)** contrast samples by their rank in label space,
  which suits regression. Used on the *change* `y(t + h) - y(t)` as an auxiliary loss on
  stage 2's hidden layer, a small encoder fits inside the 243-parameter budget and is
  hand-writable. Two conditions: the change must have structure above measurement noise
  (task T13), and stage-B batches must be blocked by state, because the 156 qubits of one
  calibration run are near-duplicates. **Conditional.**
- **Temporal contrastive learning (CPC, TS2Vec)** defines positives across time, which
  matches forecasting. But published encoders far exceed the budget, they assume regular
  sampling, and drift jumps create false positive pairs. **Conditional, weak.**
- **Self-supervised tabular pretraining (SCARF)** needs an unlabelled surplus, and here every
  state is labelled. Its augmentations can also build physically impossible devices (a
  swapped-in `T2` above `2 T1`). **Poor fit.**
- **An autoencoder as stage 1** mixes the named features into a latent, so stage 1 could no
  longer hand stage 2 a ranking of named features (decision A1). **Poor fit as stage 1.**
- **TabNet** offers built-in feature selection, but even its smallest reported model is far
  over budget and needs a framework, and permutation importance already gives the ranking.
  **Poor fit.**
- **On deep learning versus simpler models for small tables:** the benchmarks
  (Grinsztajn et al.; McElfresh et al.; Gorishniy et al.) are at sizes larger than ours,
  and none decides a 131-step forecasting series. What they do support is a rule: any
  representation stage must first beat a plain model on the same split.

No paper found applies contrastive or representation learning to qubit calibration drift;
the nearest is a clustering study of calibration metrics (Deng et al.).

### 2.1a A fair test of supervised contrastive learning (plan task T14)

The test is designed so that either outcome means something.

- **Same task and evaluation protocol as the engine:** forecast at `t + h` on the same time
  split, under whichever evaluation protocol the lead adopts (§5). With states as rows the
  test is exposed to the zero-width failure in §0, so that protocol decision precedes T14's
  gate.
- **Labels on the change, not on the future value.** SupCon needs classes. Classes built
  on `y(t + h)` would reward persistence, so they are built on the change
  `y(t + h) - y(t)`: per output, *decrease*, *no material change* and *increase*. The
  "no material change" threshold comes from T13's measured noise floor and is fixed before
  training.
- **Model:** the encoder (stage 2's hidden layer) plus a linear forecasting head. The loss
  is the forecast's squared error plus `beta` times the SupCon loss on the encoder's
  normalized embedding. `beta` is chosen from a small grid, fixed in advance, on the
  validation slice.
- **Arms on the same split:**
  - the same network at `beta = 0`, which isolates what the contrastive term adds;
  - Rank-N-Contrast on the change, the regression form of the same idea;
  - persistence and the linear forecaster as references.
- **Batches blocked by calibration run**, so near-duplicate rows of one run are never each
  other's negatives.
- **Budget:** deployed parameters (encoder plus head) under the plan's matching rule, with
  any projection head used only in training reported separately.
- **NumPy, with the T3 gate:** the SupCon loss and its gradient are hand-written and pass a
  finite-difference check.
- **Scale:** stage B (156 series) is where the test can show anything. Stage A, about 131
  transitions, is a feasibility run only.
- **The success rule, written before the run:** SCL helps only if `beta > 0` beats
  `beta = 0` on band score and on point error, paired over epochs x circuits. Otherwise
  the result is reported as negative, which is still an answer to Dr. Akba's question.

### 2.2 Reinforcement learning

**As the engine: does not fit.** An honest Markov decision process would take the
calibration history as the state, the forecast with its band as the action, and minus an
interval score as the reward. But IBM's next document does not depend on our forecast, so
the transitions ignore the action and the problem collapses to a contextual bandit. And
because the realized target scores every possible action, not only the one taken, it is
full-information online learning. Exploration and policy gradients add variance to a
gradient the label already gives exactly, and variance is the binding constraint at this
data size.

**Where an online decision does fit, it is not RL:**

| Possible use | Verdict |
| --- | --- |
| Keeping the band calibrated as drift changes it | **Fits, as online learning.** Adaptive conformal inference updates one scalar per step (§2.3). |
| Deciding when to refit a model | **No RL.** Refitting does not change the data, so a backtest over the archive gives every schedule's exact outcome. |
| Choosing the poll or sweep step | **No RL.** Issue #104's measurement settles it. |
| Choosing circuits for a hardware run | **Premature.** Every engine's prediction for every candidate circuit can be computed offline, which is experimental design, not a bandit. The engine also models no two-qubit or readout error yet. |
| RL for qubit calibration and control | **Real, but closed to this project.** Baum et al., Sivak et al. 2022 and Sivak et al. 2025 all need an actuator, meaning control access to the device. IBM has deprecated pulse-level control on all its processors (IBM pulse-migration guide), and this project only reads published calibration. |

### 2.3 Forecasting with bands that hold under drift

**Forecasters, for version 1:**

- **Persistence** (repeat the last epoch) is the required reference. It is what the fuzzy
  arms do in effect (plan §2.0), and errors are best reported as a ratio to it (MASE;
  Hyndman and Koehler).
- **A linear model on lags, one model shared across qubits**, is the first forecaster.
  On two lags of the six features it has about 26 parameters, fitted by least squares.
  Zeng et al. found one-layer linear models beat Transformer forecasters on every dataset
  they tested. Montero-Manso and Hyndman show one model shared across many series stays
  competitive with far fewer parameters, which suits stage B.
- **Exponential smoothing** is the second baseline. It pulls toward a long-run level, which
  is what the drift physics suggests (§3). It is also the only method found applied to
  forecasting IBM calibration data (Baheri et al. 2022; TQEA 2021). Neither of those
  reports a persistence baseline or a band.
- **An MLP on lags** is a challenger at stage B only. At stage A it would have about half a
  transition per parameter. Makridakis et al. found MLP and LSTM beaten by statistical
  methods on series of about this length.
- **LSTM/GRU, TCN, Transformer forecasters and N-BEATS** are rejected for version 1:
  - each is over budget or needs a framework;
  - hand-written backpropagation through time is the costliest NumPy item;
  - the evidence on short series favours linear models.

**Bands, for version 1:**

- **Adaptive conformal inference** (Gibbs and Candès) updates one miscoverage level per
  step. It provably keeps long-run coverage for any data process, without exchangeability.
  It is about ten lines of NumPy. Its guarantee is a long-run average, and at our length a
  single run's coverage should be reported with its binomial interval. Variants that remove
  the step-size choice exist (DtACI, AgACI).
- **Use asymmetric scores** (two one-sided quantiles). Decay-rate errors are one-sided and
  heavy-tailed (§3).
- **Conformal PID control** (Angelopoulos et al.) is the upgrade path if sudden shifts
  dominate.
- **Weighted conformal** (Barber et al.) fits if drift is slow.
- **Split conformal** stays as the control. It degrades gracefully without exchangeability
  (Oliveira et al.), but it is exposed to the zero-width failure in §0.

### 2.4 Structure- and physics-aware models

- **A grey-box residual (adopt).** Forecast each qubit's log decay rates `z = (log 1/T1,
  log 1/T2)` as a baseline plus a learned correction, then apply ADR-027's formula.
  - **Baseline:** persistence, or shrinkage toward the qubit's running mean.
  - **Correction:** learned from the features and the history window.
  - **Output parameterization:** writing `1/T2 = 1/(2 T1) + softplus(u)` guarantees
    `T2 <= 2 T1`. Separate forecasts of `T1` and `T2` can break that constraint, and the
    resulting negative `lambda` would be clipped silently downstream.
  - **Size:** a linear correction is tiny, and an MLP correction fits the budget.

  Residual modelling is a named hybrid physics-ML category (Willard et al.); no paper was
  found that applies it to qubit calibration.
- **A per-qubit temporal Gaussian process (adopt as a reference).**
  - **Kernel:** a sum of exponential (Ornstein-Uhlenbeck) kernels plus white noise on log
    rates. It handles irregular sampling natively.
  - **Size:** about ten hyperparameters shared across qubits, and cheap in NumPy.
  - **Use:** it reverts to the mean beyond its lengthscale, which makes it a principled
    shrinkage baseline. Its posterior standard deviation can normalize the conformal
    score.
  - **Not as the band:** the posterior variance does not widen after a level shift, so it
    carries no coverage guarantee under drift.

  A GP's capacity grows with its data, so a fair comparison with the 243-parameter arms is a
  learning curve: band score at several training sizes for every arm.
- **A graph-kernel GP over the coupling map (diagnostic).** Comparing its marginal likelihood
  with and without the graph kernel answers whether neighbouring qubits carry signal at all.
  It is cheaper and clearer than training a graph network.
- **Graph neural networks (defer).**
  - No paper was found that forecasts calibration drift with them. The nearest predict
    static errors or circuit outcomes (Das et al.; QuEst; Wang et al. 2026).
  - The physics evidence says fluctuations are local to each qubit (§3).
  - A minimal spatio-temporal model is several times over budget.
  - Revisit only if the graph-GP diagnostic finds neighbour signal and stage B exists.
- **Rejected:**
  - **Physics-informed neural networks:** they need a governing differential equation,
    and drift has none (Raissi et al.).
  - **Deep kernel learning:** it can overfit worse than a plain network at small data (Ober
    et al.).
  - **MC dropout and deep ensembles:** not as the band, since they carry no coverage
    guarantee, but usable as a score normalizer.

## 3. What the physics says about drift

Checked against each paper's abstract. None of these devices is `ibm_fez`, so this is a
prior to test (tasks T12 and T13), not a fact about our archive.

| Source | What it shows |
| --- | --- |
| Klimov et al. 2018 | Individual two-level-system (TLS) defects cause the largest fluctuations in `T1` |
| Burnett et al. 2019 | Relaxation fluctuations are local to the qubit and caused by near-resonant TLS instabilities |
| Etxezarreta Martinez et al. 2023 | On five IBM processors, `T1` and `T2` fluctuations are reasonably modelled as local to each qubit |
| Carroll et al. 2021 | Over nine months, `T1` fluctuations are autocorrelated and suggest ergodic-like TLS spectral diffusion |
| Berritta et al. 2026 | `T1` can switch by nearly an order of magnitude within tens of milliseconds |

**What this implies here:**

1. **Much of the switching is far faster than a daily re-measurement.** It aliases into
   near-random draws around each qubit's long-run level. What is forecastable is mainly
   that level and slow structure, so shrinkage toward a running mean is the natural
   baseline.
2. **Errors are one-sided and heavy-tailed.** The long low-`T1` tail becomes a long
   high-`gamma` tail, so bands should be asymmetric.
3. **`gamma` and `lambda` move together**, since one TLS moves `T1` and `T2` together
   (Schlör et al.). Separate bands at level `alpha` do not give joint coverage.
4. **Neighbour signal is not expected**, which is why graph models are deferred.
5. **Part of every change is noise in IBM's own estimate of `T1`.** That part is
   unforecastable and sets a floor under any band's width.

## 4. The recommended first version of the third engine

The structure and physics family and the forecasting family converged on the same design
independently, and nothing in the other two contradicts it:

- **Unit and protocol:** epochs as rows; `h` counted in epochs; coverage scored on change
  events; the Wilcoxon test paired over epochs x circuits. The same protocol applies to all
  three engines.
- **Forecaster:** a grey-box residual on log decay rates.
  - Baseline: persistence and shrinkage, both reported.
  - Correction: linear first, shared across qubits; an MLP correction as the challenger
    within the budget.
  - Output parameterized so that `T2 <= 2 T1` always holds, then ADR-027's formula applied.
- **Band:** adaptive conformal inference with asymmetric scores, optionally normalized by
  the GP's standard deviation, with split conformal run alongside as the control. Applying
  one wrapper to all three engines also settles the plan's §1.1 fairness question.
- **References every engine must beat:** persistence, exponential smoothing, and the
  per-qubit GP.
- **Stage 1 (decision A1):** permutation importance computed on the *change* in
  `(gamma, lambda)` at `t + h`.
- **Optional:** a Rank-N-Contrast auxiliary loss, only if T13 shows structure in the
  change.

**This design is wrong if:**

- the changes between epochs show no autocorrelation beyond estimation noise (then
  persistence or shrinkage wins, and the engine reduces to persistence with a band);
- `T1` stays at one level much longer than an epoch (then weighted conformal suffices);
- sudden regime shifts dominate (then conformal PID control should lead).

**What it means for "deep".** At stage A the evidence predicts that a learned deep model
will not beat a linear or shrinkage forecaster on about 131 transitions. That
is a publishable result about data scale, not a failure. The deep component earns its
place at stage B (156 series), as a correction to a physics baseline.

## 5. How this bears on the plan's decisions

These are recommendations; the decisions are the lead's. **On 2026-10-04 the lead kept the
plan's decisions as written.** Everything below stays documented as recommendation until
he decides, after the meeting with Dr. Akba. He also added the SCL test (§2.1a).

| Plan decision | Effect of this research |
| --- | --- |
| A1, two stages | Holds. Stage 1's importance is computed on the change; stage 2 becomes a residual forecaster. |
| A2, scenarios then importance | Holds. The scenario count should also be made over epochs, not states. |
| A3, snapshot then per qubit | Holds, and is sharpened: stage A is about 131 epochs, stage B is 156 series of about that length. |
| A4, NumPy by hand | Holds. Every version-1 component is NumPy-feasible; the rejected ones are the ones that would need a framework. |
| A5, split conformal | **Recommended change:** adaptive conformal inference with asymmetric scores, with split conformal kept as the control |
| A7, forecasting | Holds, and is sharpened: `h` is counted in epochs |

## 6. What must be measured before choosing (the plan's T12 and T13, extended)

1. **The epoch count, registered,** using all blobs at a pinned ref: the gap distribution,
   the mapping of epochs onto #63's distinct states, and the zero-residual fraction `f` per
   state.
2. **Drift size and memory, per qubit and for the snapshot mean:**
   - the distribution of epoch-to-epoch change in log `T1`, log `T2`, `gamma` and `lambda`;
   - the share of changes larger than a factor of two;
   - autocorrelation at several lags;
   - how stable each qubit's long-run mean is.
3. **Persistence against shrinkage**, scored on change events at a few horizons. A tie means
   there is no learnable signal.
4. **A spectral drift check** in the style of Proctor et al.
5. **Neighbour signal:** the graph-GP diagnostic, or the correlation of changes between
   coupled and uncoupled pairs at matched distance, plus the share of variance in a
   device-wide common mode.
6. **Stage-A tail share:** how much of the snapshot-mean `gamma` comes from the few qubits
   sitting on a TLS.
7. **Band settings:** `alpha`; symmetric or asymmetric scores; per output or joint; and the
   coverage unit (per qubit or per state).
8. **A rule for stale dates** on qubits whose `T1` date lags the rest of the snapshot,
   alongside the missing-data rule.
9. **The number of test epochs after the time split.** It bounds how precisely coverage can
   be measured.

## 7. Questions this adds for Dr. Akba

1. At stage A a deep model is expected to lose to a linear or shrinkage forecaster. Is a
   documented negative result at this data scale an acceptable contribution for the deep
   engine, with the deep model's case resting on stage B?
2. Should coverage be claimed for the band per output or jointly for `(gamma, lambda)`?
3. Reinforcement learning has no role in the engine itself. Should the paper say so
   explicitly, given that he raised it?
4. Which form of supervised contrastive learning did he have in mind: SupCon on classes of
   the change (§2.1a), or a regression form such as Rank-N-Contrast? The test runs both,
   but his intent decides which one the paper leads with.

## 8. Sources

All resolved on 2026-10-04: arXiv IDs against the arXiv API, DOIs against Crossref.

| Source | Identifier | Used for |
| --- | --- | --- |
| Khosla et al., Supervised Contrastive Learning (2020) | arXiv:2004.11362 | SupCon's class-label positives |
| Zha et al., Rank-N-Contrast (NeurIPS 2023) | arXiv:2210.01189 | Contrastive learning for regression |
| Keramati et al., ConR (2023) | arXiv:2309.06651 | Contrastive regularizer for continuous labels |
| Wu et al., SupReMix (2023) | arXiv:2309.16633 | Contrastive regression with mixup |
| Bahri et al., SCARF (ICLR 2022) | arXiv:2106.15147 | Tabular contrastive pretraining |
| Rubachev et al., Revisiting Pretraining Objectives for Tabular DL (2022) | arXiv:2207.03208 | Contrastive pretraining no better than alternatives on tables |
| Chen et al., SimCLR (ICML 2020) | arXiv:2002.05709 | Large batches and projection heads |
| van den Oord et al., Contrastive Predictive Coding (2018) | arXiv:1807.03748 | Temporal positives |
| Yue et al., TS2Vec (AAAI 2022) | arXiv:2106.10466 | Time-series contrastive representations |
| Arik and Pfister, TabNet (2019) | arXiv:1908.07442 | Built-in feature selection; model sizes |
| Shwartz-Ziv and Armon, Tabular Data: DL Is Not All You Need (2021) | arXiv:2106.03253 | Trees versus TabNet |
| Grinsztajn et al., Why Tree-Based Models Still Outperform DL (2022) | arXiv:2207.08815 | Deep versus trees on tables |
| Gorishniy et al., Revisiting DL Models for Tabular Data (NeurIPS 2021) | arXiv:2106.11959 | No universal winner |
| McElfresh et al., When Do Neural Nets Outperform Boosted Trees (2023) | arXiv:2305.02997 | Gap often small |
| Hollmann et al., TabPFN (2022) | arXiv:2207.01848 | Small-table classifier, pretrained |
| Deng et al., Qubit Health Analytics and Clustering (2025) | arXiv:2508.21231 | Nearest calibration-data ML work: clustering, not forecasting |
| Gibbs and Candès, Adaptive Conformal Inference Under Distribution Shift (2021) | arXiv:2106.00170 | Coverage without exchangeability |
| Gibbs and Candès, Conformal Inference for Online Prediction with Arbitrary Distribution Shifts (2022) | arXiv:2208.08401 | DtACI |
| Zaffran et al., Adaptive Conformal Predictions for Time Series (2022) | arXiv:2202.07282 | AgACI; step-size sensitivity |
| Angelopoulos et al., Conformal PID Control (2023) | arXiv:2307.16895 | Quantile tracking under shifts |
| Barber et al., Conformal Prediction Beyond Exchangeability (2022) | arXiv:2202.13415 | Weighted conformal |
| Oliveira et al., Split Conformal Prediction and Non-Exchangeable Data (JMLR 2024) | arXiv:2203.15885 | Split conformal without exchangeability |
| Xu and Xie, Conformal Prediction for Time Series (2020) | arXiv:2010.09107 | EnbPI |
| Guan, Localized Conformal Prediction (2021) | arXiv:2106.08460 | Distance-weighted local bands |
| Spencer et al., Adaptive Conformal Prediction for Quantum Machine Learning (2025) | arXiv:2511.18225 | Adaptive conformal on IBM hardware (quantum ML, not calibration) |
| Zeng et al., Are Transformers Effective for Time Series Forecasting? (2022) | arXiv:2205.13504 | Linear beats Transformers |
| Bai et al., Generic Convolutional and Recurrent Networks for Sequence Modeling (2018) | arXiv:1803.01271 | TCN versus LSTM |
| Hewamalage et al., RNNs for Time Series Forecasting (2019) | arXiv:1909.00590 | RNNs only sometimes competitive |
| Oreshkin et al., N-BEATS (2019) | arXiv:1905.10437 | Large-benchmark deep forecaster |
| Montero-Manso and Hyndman, Locality and Globality (2020) | arXiv:2008.00444 | One model across many series |
| Makridakis et al., Statistical and ML Forecasting Methods (PLOS ONE 2018) | doi:10.1371/journal.pone.0194889 | ML loses on short series |
| Hyndman and Koehler, Another Look at Measures of Forecast Accuracy (2006) | doi:10.1016/j.ijforecast.2006.03.001 | MASE, scaling by the naive forecast |
| Baheri et al., Quantum Noise in the Flow of Time (IOLTS 2022) | doi:10.1109/IOLTS56730.2022.9897404 | Statistical forecasts of IBM calibration data |
| Baheri et al., TQEA: Temporal Quantum Error Analysis (DSN-S 2021) | doi:10.1109/DSN-S52858.2021.00034 | Exponential smoothing on IBM calibration data |
| Gupta and Biercuk, ML for Predictive Estimation of Qubit Dynamics Subject to Dephasing (2018) | arXiv:1712.01291 | Near-match: forecasting simulated dephasing |
| Proctor et al., Detecting and Tracking Drift in Quantum Information Processors (2020) | arXiv:1907.13608 | Spectral drift detection |
| Klimov et al., Fluctuations of Energy-Relaxation Times in SC Qubits (PRL 2018) | arXiv:1809.01043 | TLS-driven T1 fluctuations |
| Burnett et al., Decoherence Benchmarking of SC Qubits (2019) | arXiv:1901.04417 | Local, TLS-driven fluctuations |
| Schlör et al., Correlating Decoherence in Transmon Qubits (PRL 2019) | arXiv:1901.05352 | T1 and T2 move together under one fluctuator |
| Carroll et al., Dynamics of SC Qubit Relaxation Times (2021) | arXiv:2105.15201 | Autocorrelated, ergodic-like T1 |
| Kim et al., Error Mitigation with Stabilized Noise (2024) | arXiv:2407.02467 | Large T1 fluctuation on IBM-class devices |
| Etxezarreta Martinez et al., Time-Varying Quantum Channel Models (npj QI 2021) | doi:10.1038/s41534-021-00448-5 | T1 modelled as a stochastic process |
| Etxezarreta Martinez et al., Multi-Qubit Time-Varying Quantum Channels (2023) | arXiv:2207.06838 | Fluctuations local per qubit on IBM devices |
| Berritta et al., Real-Time Adaptive Tracking of Fluctuating Relaxation Rates (2026) | arXiv:2506.09576 | Millisecond-scale T1 switching |
| Willard et al., Integrating Scientific Knowledge with ML (2022) | arXiv:2003.04919 | Residual modelling as a hybrid category |
| Raissi et al., Physics Informed Deep Learning (2017) | arXiv:1711.10561 | PINNs need a governing equation |
| Ober et al., Promises and Pitfalls of Deep Kernel Learning (2021) | arXiv:2102.12108 | DKL can overfit |
| Gal and Ghahramani, Dropout as a Bayesian Approximation (2016) | arXiv:1506.02142 | MC dropout |
| Lakshminarayanan et al., Deep Ensembles (2017) | arXiv:1612.01474 | Deep ensembles |
| Ovadia et al., Can You Trust Your Model's Uncertainty? (2019) | arXiv:1906.02530 | Uncertainty under shift |
| Borovitskiy et al., Matérn GPs on Graphs (2021) | arXiv:2010.15538 | Graph kernel |
| Álvarez et al., Kernels for Vector-Valued Functions (2011) | arXiv:1106.6251 | Coregionalization |
| Hensman et al., Gaussian Processes for Big Data (2013) | arXiv:1309.6835 | Sparse GPs |
| Li et al., DCRNN (ICLR 2018) | arXiv:1707.01926 | Reference spatio-temporal graph forecaster |
| Huang et al., Conformalized Graph Neural Networks (2023) | arXiv:2305.14535 | Node conformal needs exchangeable nodes |
| Wang et al., Error Mitigation with Physically Informed GNNs (2026) | arXiv:2604.16815 | Coupling-graph GNN predicting observables |
| Das et al., Graph-Based Forensic Framework for Hardware Noise (2025) | arXiv:2512.14541 | GNN for static error rates |
| Wang et al., QuEst (ICCAD 2022) | arXiv:2210.16724 | Graph model of circuit fidelity |
| Baum et al., Experimental Deep RL for Gateset Design (PRX Quantum 2021) | arXiv:2105.01079 | RL gate design via pulse access on IBM |
| Sivak et al., Model-Free Quantum Control with RL (PRX 2022) | arXiv:2104.14539 | RL control needs an actuator |
| Sivak et al., RL Control of Quantum Error Correction (2025) | arXiv:2511.08493 | RL counters drift with control access |
| Crosta et al., Automatic Re-Calibration by RL (2024) | arXiv:2404.10726 | RL recalibration, simulation only |
| Kelly et al., Physical Qubit Calibration on a DAG (2018) | arXiv:1803.03226 | Rule-based recalibration |
| Granade et al., Robust Online Hamiltonian Learning (2012) | arXiv:1207.1655 | Experimental design under drift |
| Upadhyay et al., Learning to Crawl (AAAI 2020) | arXiv:1905.12781 | Bandit crawling (assumptions fail here) |
| Mahadevan and Mathioudakis, Cost-Effective Retraining (2023) | arXiv:2310.04216 | Retraining cost trade-off |
| Regol et al., When to Retrain a ML Model (2025) | arXiv:2505.14903 | Retraining by forecast, not RL |
| IBM, Migrate from Qiskit Pulse to fractional gates | https://quantum.cloud.ibm.com/docs/en/guides/pulse-migration | Pulse-level control deprecated (vendor documentation, no DOI) |
