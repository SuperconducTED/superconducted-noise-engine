# Novelty check for a Q1 article on the SuperconducTED noise engine

**Date**: 2026-10-23 · **Measured against**: `main` @ `6cf008da` and the literature as searchable on
that date · **Requested by**: Mert Efe Şensoy · **Status**: desk research, no experiment run

This record asks one question: if the team writes a journal article about this engine today,
what in it is new, what is already published, and what must be measured before the new part
is defensible. It is organised by *claim*, not by paper, because a reviewer scores claims.

The project's own documents already say the engine's outputs are point estimates (README,
"Where it stands"; ADR-015 and ADR-016 `Deferred`; ADR-009 `Open`). This record is not allowed
to be less honest than the README.

---

## 1. Verdict in one table

| # | Claim the article would make | Nearest published neighbour | Verdict today |
| --- | --- | --- | --- |
| 1 | A TSK / ANFIS fuzzy regression from calibration features (mean T1, T2, readout error) to amplitude- and phase-damping channel parameters, exported as Aer `NoiseModel`s | Hassan & Kaabouch 2026 (ANFIS on ibm_fez, but for error *attribution*, not noise synthesis); Müller et al. 2025 and Bautra et al. 2026 (calibration to channels, but crisp) | **Novel combination, textbook parts.** No published work uses a fuzzy inference system as the calibration-to-noise-model map. The fuzzy machinery itself (first-order TSK, Gaussian or IT2 sets, Nie-Tan reduction, hybrid LSE + gradient ANFIS) is standard Mendel/Jang material and must be presented as such. |
| 2 | An Interval Type-2 footprint, or an ensemble of fuzzy models, yields an *interval* over simulation output | IT2-ANFIS for prediction intervals in other domains (e.g. arXiv 2601.18897, wastewater energy) | **Method not novel, application is.** IT2 systems producing lower and upper outputs are established. The quantum-noise application has no precedent found. |
| 3 | That interval *brackets real hardware across calibration cycles* better than a single calibration-frozen model | **QuBound** (Li, Dasgupta, Humble, Jiang et al., arXiv 2507.17043, 2025): predicts fidelity *bounds* under unstable noise from calibration-derived noisy simulation, 700 days of data, bound-compliance rate and bound width as metrics [corrected 2026-10-26: bounds on per-circuit outcome probabilities and observable expectations, not on fidelity alone; §9 item 2]. Also the Dasgupta & Humble stability line (2021-2024). | **This is the scientific claim and it is unverified.** The ensemble is degenerate (N identical members), no interval has ever been produced, no hardware comparison exists. Today the novelty is architectural, and a close competitor already publishes bounds. The article does not exist as a result yet. |
| 4 | The hourly `calibration-data` archive is a research asset | `phanerozoic/qiskit-calibration-drift` (Hugging Face, CC-BY-4.0): polls `backend.properties()` on every Heron device every 30 minutes with historical backfill, four backends including `ibm_fez`, per-qubit T1, T2, readout and per-gate error and length, continuous from 2026-01-31, 28.9 million rows, plus environmental covariates. Also QuBound's own 700-day, 4-per-day dataset. | **Not a differentiator.** A single-backend archive at 868 distinct states against a 1,170 floor (NC-069 at `calibration-data` @ `d62f2cd`, 2026-10-16) is smaller and narrower than public alternatives. Flagged as a blind spot: the team's planning documents treat the archive as the scarce input. |
| 5 | The Factory / Ensemble pattern around Aer's one-shot `to_dict()` serialisation | Engineering practice | **Not a contribution.** One paragraph of methods, not a claim. |

**Bottom line.** Claim 1 plus claim 2 is enough for a *fuzzy-systems* venue if the ablation is
strong. Claim 3 is the only thing a *quantum* venue will score, and it requires the gating
test in §4, which has not been run and whose outcome is not predictable from anything in the
repository.

---

## 2. What the engine is, in the terms a reviewer will use

Seven stages from one IBM `BackendProperties` snapshot to a set of `QuantumError`s:
ingest, extract three chip-mean features, fuzzify and fire a 27-rule (3×3×3) TSK base,
defuzzify (weighted average for T1, Nie-Tan for IT2), squash, gate-eligibility, project onto
amplitude plus phase damping (`docs/architecture.md`). The training target is ADR-027's
per-qubit $(\gamma,\lambda)$ from $T_1$, $T_2$ and gate duration, averaged per snapshot.
The rule base has 234 trainable parameters (NC-045), so the five-per-parameter floor is 1,170
distinct device states (NC-012) against 868 archived at the latest registered count (NC-069,
`calibration-data` @ `d62f2cd`, 2026-10-16; the archive grows hourly, so cite the row, not the
number).

Four properties of this design matter for the novelty argument and are stated here so the
comparison below is fair to the engine:

- **Input is the calibration table, not circuit outcomes.** Most learned noise models
  (Ji et al. 2026, Zlokapa & Mitra 2020, the few-shot transfer paper, the Kraus-on-tensor-network
  paper) fit to measured circuit output distributions. The engine never sees hardware counts at
  training time; it regresses calibration features onto channel parameters. That is the same
  input class as `NoiseModel.from_backend`, QuBound and the digital-twin papers.
- **Output is a simulator-ready noise model, not a fidelity number.** QuBound and the
  reliability-analysis line predict a scalar (fidelity) with bounds. The engine emits something
  Aer can run any circuit through. This is the engine's strongest structural difference from
  QuBound and should be the centre of the framing. [Corrected 2026-10-26 on review: QuBound's
  outputs are not one fidelity number; see §9 item 2.]
- **Uncertainty is realised across ensemble members, not per shot.** Forced by Aer
  (ADR-002, ADR-021). QuBound's "NoisySim" baseline, repeated noisy simulation with min and max as
  bounds, is the nearest analogue and is the baseline QuBound beats.
- **The noise model is spatially uniform.** Stage 2 collapses the chip to three means, the rule
  base emits one $(\gamma,\lambda)$ pair, `FuzzyNoiseModel` computes `crisp_params` once, and
  `AmplitudePhaseDampingProjector.project` reads `crisp_params[0]` and `[1]` with no dependence on
  the `qubits` argument (`integration/aer_factory.py`, `channels/kraus.py`). Every eligible
  single-qubit gate on every qubit gets the same channel. ADR-013 defers per-qubit features and
  ADR-027 states the snapshot aggregate is not a per-qubit table. Every baseline in §4
  (`from_backend`, the digital twins, QuBound's per-qubit 5-tuples) is per-qubit. On any circuit
  whose qubits differ in quality, a stale per-qubit model can beat a fresh homogeneous one no
  matter how well the latter tracks time. This is a larger reviewer objection than drift and is
  not addressed by anything in the ledger today.

---

## 3. Prior art, by distance from the engine

Verification level per row: **F** = full text read (by me or via a summary of the full text),
**A** = abstract page only, **R** = repository README only. Numbers from A and R rows are
reported as the source states them and were not checked against the body.

### 3.1 Closest: bounds and intervals under drifting noise

| Work | What it does | Same as engine | Different from engine | Ver. |
| --- | --- | --- | --- | --- |
| **QuBound**, Li, Dasgupta, Song, Yang, Humble, Jiang, arXiv 2507.17043 (Jul 2025); IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems per Semantic Scholar (the arXiv body carries an IEEE copyright notice and no venue) | Predicts a circuit's fidelity as a *bound*, not a point. Per-qubit 5-tuples (gate type, gate parameter, T1, T2, gate error) per circuit stage feed an LSTM. Training traces come from noisy Aer simulation driven by IBM backend properties; 700 days at 4 samples a day (2,800 samples); devices named include ibmq_kolkata (T1 profiled at 7-minute intervals over two months), ibm_nairobi, ibmq_mumbai, ibm_hanoi. Bounds come from a trend plus a z-score interval on the residual. Quality is bound-compliance rate and bound width. Baselines: repeated noisy simulation, an analytical Hellinger approach, a graph-transformer predictor, linear regression. | Calibration data in, a *range* out, motivated by temporal instability of the same device, Aer-from-calibration as the data generator, Hellinger in the comparison set. | Predicts a scalar per circuit, not a noise model [corrected 2026-10-26: per-circuit outcome probabilities and observable expectations with bounds, not one scalar; §9 item 2]; a learned black box (LSTM), no interpretable rule base; bounds from a normality assumption on residuals, not from a fuzzy footprint; no interval type-2 or ensemble of simulators. | F (partial) |
| Dasgupta & Humble, "Stability of noisy quantum computing devices", arXiv 2105.09472 (2021); "Characterizing the reproducibility of noisy quantum circuits", Entropy 24, 244 (2022); "Impact of unreliable devices on stability of quantum computations", ACM TQC (2023) | Hellinger-distance characterisation of fluctuation over 22 months; ε-reliability; an analytic upper bound on run-to-run Hellinger from readout and gate error rates. | Hellinger as the drift metric; the thesis that a single calibration is not representative. | Characterises and bounds, does not build a simulator; no learned map from calibration to channels. | A |
| Dasgupta & Humble, "Improving PEC in the presence of non-stationary noise", arXiv 2404.13269 (2024); "Adaptive channel estimation", arXiv 2208.10263 (QCE 2022 poster) | Bayesian / adaptive estimation of channel parameters from circuit outputs because characterisation data goes stale. Reports 42% accuracy and 60% stability gains for PEC on ibm_kolkata. | Explicit premise that calibration data is stale at run time. | Infers from live outputs, not from calibration history; mitigation, not simulation. | A |
| "Staleness-aware noise modeling" (course project, GitHub `RealAradhyaGupta/staleness-project`, Aug-Oct 2026) | Merges consecutive identical calibration cards into *distinct calibration states*; simulates queue delays of 1 to 48 h with Aer from published calibration numbers; six qubit-selection strategies; Hellinger fidelity vs ideal; 120 days of history on three machines; no hardware runs; no paper. | The distinct-state deduplication is the same idea as ADR-025's ledger; Aer from archived calibration; Hellinger. | A layout-selection study, not a noise-model learner; unpublished. A reviewer who searches GitHub finds it in one query, so it belongs in related work as grey literature. | R |

### 3.2 Close: calibration-driven digital twins (crisp)

| Work | What it does | Same | Different | Ver. |
| --- | --- | --- | --- | --- |
| Bautra, Dimitrijevs, Yakaryilmaz, "Evaluating calibration-based digital twins for IBM Quantum hardware simulation", CEUR-WS Vol. 4211 paper 10, Baltic DB&IS 2026 doctoral consortium, published 2026-06-09 (arXiv 2603.14607) | Builds Aer twins from downloadable calibration CSVs (T1, T2 to thermal relaxation; gate and readout error; durations; directed coupling map). Four variants (CSV-built, backend-derived simulator, backend-derived noise model, fake backend) vs ibm_brisbane and ibm_sherbrooke, random 5-qubit circuits at depths 10/20/30, four optimisation levels; 24 hardware jobs, 96 simulator runs; weighted Jaccard similarity. Jobs were scheduled "to reduce the effect of calibration drift over time", i.e. drift is a nuisance to be controlled, not the object of study. | Same input class and same Aer channel family as the engine's stage 7. | Crisp, single snapshot, no learning, no interval. Workshop / doctoral-consortium paper, not a journal. | F |
| Müller et al., "Towards a digital twin of noisy quantum computers: calibration-driven emulation of transmon qubits", arXiv 2504.08313 (2025) | Parametric physics-based error model from calibration plus benchmarking circuits; validated on a 5-qubit QPU; mean TVD 0.15. Abstract claims it "captures real-time device fluctuations". | Calibration in, emulator out, physics-motivated channels. | Crisp; fitted with benchmark circuits; no interval. | A |
| Bravo-Montes et al., "A methodology to select and adjust quantum noise models through emulators", EPJ Quantum Technology 11 (2024) | Six noise models on Qiskit and Qaptiva vs ibm_perth; best fidelity deviation 0.686% (one circuit, Qaptiva); Qiskit deviations much larger. | Documents the gap between calibration-based Aer models and hardware, which is the engine's motivation. | Model selection, not learning; no drift. | A |
| Maschek et al., "Make some noise!", IEEE QSW 2025 (arXiv 2506.03636) | Tunable Kraus-channel model on Qaptiva calibrated to IBM measurements; GHZ and QAOA validation. | Kraus-channel family. | Not Aer, crisp, no drift. | A |
| Luo et al., "A digital twin of scalable quantum clouds", SIGSIM-PADS 2025 (cited by Bautra) | Calibration CSVs imported into a cloud-operations twin with fidelity estimation. | Calibration archive as twin input. | Systems-level twin, not a channel model. | cited only |

### 3.3 Close: learned noise models (fit to circuit outputs, not calibration)

| Work | What it does | Relevance | Ver. |
| --- | --- | --- | --- |
| Ji, Roth, Kreplin, Polian, Wilhelm, "Data-efficient quantum noise modeling via machine learning", Phys. Rev. Applied 25, 034051 (2026), arXiv 2509.12933 | 20-parameter physically motivated noise model (depolarising, amplitude, stretched dephasing, coherent angles, ZZ, correlated readout) fitted by Bayesian optimisation to existing application-circuit runs. Mean Hellinger reduction about 50% vs device-property-derived models, 65% peak for one circuit (ibmq_mumbai QAOA, Section III.1.2). Devices: ibmq_kolkata, mumbai, ehningen, ibm_kingston. States device characteristics "often vary over time" and ran QAOA at four calibration instances, but does not test parameter validity across calibrations and reports no predictive intervals. | **The strongest fitted-model baseline a quantum venue will ask for.** It beats `from_backend` by a large margin with 20 parameters; the engine has 234 and has not yet beaten anything. | F (via summary) |
| van den Berg & Wocjan, "Techniques for learning sparse Pauli-Lindblad noise models", Quantum 8, 1556 (2024); IBM `NoiseLearner` / `NoiseLearnerV3` | The production-grade learned noise model on IBM hardware. | The "why not Pauli-Lindblad" question. Answer: those models are learned per layer from twirled experiments at run time and are expensive; the engine's niche is *offline* simulation from the free calibration table. State this, do not dodge it. | A |
| van den Berg, Mitchell, Wei, Malekakhlagh, "Large-scale Lindblad learning from time-series data", arXiv 2512.08165 (2025, rev. 2026) | Learns a time-*independent* local Lindblad generator on a 156-qubit device from time-series observables. | Despite the title, not a drift model. | A |
| Zlokapa & Mitra, "A deep learning model for noise prediction on near-term quantum devices", arXiv 2005.10811 (2020) | CNN predicts output noise per circuit on one IBM device, no calibration inputs. | Early learned-model precedent. | A |
| Al Farib et al., "Few-shot cross-device transfer for quantum noise modeling", arXiv 2604.24397 (2026) | Residual network maps noisy to ideal distributions, ibm_fez to ibm_marrakesh; calibration features added to the dataset. | Shows calibration features entering a learned noise map; device specificity (KL 0.30 to 1.67 zero-shot). | A |
| "Quantum hardware noise learning via differentiable Kraus representation on tensor networks", arXiv 2604.20804 (2026) | Learns Kraus operators from device data; reproduces an ibm_fez adder distribution. | Kraus learning on the same device the engine polls. | A |

### 3.4 Fuzzy methods near quantum hardware

| Work | What it does | Relevance | Ver. |
| --- | --- | --- | --- |
| Hassan & Kaabouch, "A physics-informed neuro-fuzzy framework for quantum error attribution", arXiv 2602.21253 (Feb 2026, v4 Sep 2026) | First-order Takagi-Sugeno ANFIS, 16 rules, Gaussian memberships, product t-norm, linear consequents, over 7 output-distribution and circuit features; separates software bugs from hardware noise on ibm_fez and ibm_kingston; noise floor simulated with Aer `NoiseModel.from_backend` from ibm_fez calibration. No type-2, no drift treatment beyond naming it as a confounder. | **The only ANFIS-on-transmon paper found.** Same device, same fuzzy family, same Aer-from-calibration tooling, different task. Must be cited and differentiated in the first paragraph of related work. | F (partial) |
| Ahmad et al., "Mitigating errors on superconducting quantum processors through fuzzy clustering", arXiv 2402.01815 (2024), DOI 10.1002/qute.202300400 | Fuzzy c-means on repeated circuit runs to identify measurement-error patterns; 2-qubit proof of principle. | Fuzzy methods on transmons, but clustering for mitigation. | A |
| Schiattarella et al., "Fuzzy logic on quantum annealers", IEEE TFS (2021); Wu et al., quantum-assisted hierarchical fuzzy network, IEEE TFS (2025) | Fuzzy inference *on* quantum hardware, or quantum circuits learning memberships. | Opposite direction; shows IEEE TFS publishes quantum-adjacent fuzzy work. | A |
| IT2-ANFIS uncertainty quantification, e.g. arXiv 2601.18897 (2026, wastewater energy) | Lower and upper membership bounds yield explainable prediction intervals. | Template for how claim 2 is normally presented and evaluated (coverage, width). | A |

### 3.5 Searches that found nothing

No result for: a fuzzy or neuro-fuzzy map from calibration to Aer noise channels; interval
type-2 fuzzy systems applied to quantum noise; an ensemble of Aer noise models whose spread is
reported as an interval; per-qubit T1/T2 forecasting from calibration history to the next
calibration. Citing-paper lists were pulled from Semantic Scholar for Dasgupta & Humble 2021
(35 citing papers, which surfaced QuBound), Ji et al. 2026 (2), Müller et al. 2025 (2),
Bautra et al. 2026 (0), Hassan & Kaabouch 2026 (0). Absence here is evidence of a gap as of
2026-10-23, not proof of one.

---

## 4. The gating test: what must be measured before claim 3 can be written

The dangerous reviewer question is not "why not Pauli-Lindblad". It is:

> A percentile band over the last *k* calibration snapshots also gives an interval that
> tracks drift, and QuBound already publishes bounds. Why fuzzy?

Claim 3 is defensible only if the fuzzy interval wins, on a time-split test (train before a
cut, test after; ADR-027's snapshot-boundary rule), on coverage *and* width together, against:

1. **Crisp `NoiseModel.from_backend`** frozen at the last training snapshot (the strawman).
2. **A non-fuzzy empirical interval**: per-parameter percentiles (e.g. 10th to 90th) over the
   last *k* snapshots, projected through the same stage-7 channels. This is the baseline that
   decides whether the fuzzy layer adds anything. It costs one afternoon to build.
3. **A fitted crisp model** in the spirit of Ji et al. 2026, or at minimum a trained TSK
   type-1 point model, so that the interval's value is separated from the regression's value.
4. **A QuBound-style bound** if the comparison is on fidelity rather than distributions; at
   minimum, repeated noisy simulation with min/max bounds, which is QuBound's own weakest
   baseline. [Corrected 2026-10-26 on review: the condition is dropped, the baseline applies
   to distributions and observables too; see §9 item 2.]

Metrics: empirical coverage of the held-out reference at a nominal level, mean interval width
(or Hellinger between the band's edges), and the Hellinger / fidelity of the band's centre.
Both halves are needed: coverage alone rewards a wide band, width alone rewards a point.
[Corrected 2026-10-26 on review: "Hellinger between the band's edges" is withdrawn; see §9
item 1.]

Reference to be covered: for a fuzzy-systems venue, simulator-vs-simulator against Aer run on
the *actual later* snapshot is acceptable and is what the harness already does. For a quantum
venue, the reference is hardware counts (ADR-027's "(C)"), which do not exist yet.

Everything in this section is blocked on, in order: ADR-014 trainer producing a fit (Issue #60),
ADR-015 non-identical members (Issue #64), ADR-016 interval aggregation (Issue #64), and the
time-split protocol from the advisor File 02 decisions. Nothing here can be started from the
literature side; it is all measurement.

---

## 5. Q1 means two different articles

Journal quartiles were **not verified** in this check. The venues named below are the usual
candidates; their current SJR or JCR quartile must be confirmed before a venue is chosen, and
IEEE Transactions on Quantum Engineering in particular should be checked rather than assumed.

### 5.1 Fuzzy-systems journal (IEEE Transactions on Fuzzy Systems, Fuzzy Sets and Systems, Applied Soft Computing)

- **Scored contribution**: claims 1 and 2. A new application domain for IT2 TSK / ANFIS with a
  physically constrained output (CPTP channels, ADR-008's CPTP-by-construction) and a clean
  epistemic-vs-aleatoric split (ensemble vs Aer shots).
- **What is expected**: a thorough ablation (ADR-019's membership-function shapes; T1 vs IT2
  with a parameter-matched T1 control, as ADR-009's overturn clause already requires; Nie-Tan
  vs Karnik-Mendel, Issue #61), the interval's coverage and width, and comparison 2 of §4.
  Simulator-vs-simulator is acceptable. Hardware is a plus, not a gate.
- **What is not expected**: beating Pauli-Lindblad or Ji et al. on absolute Hellinger.
- **Risk**: IEEE TFS reviewers will know Mendel and will reject a paper that presents Nie-Tan or
  hybrid-learning ANFIS as new. The novelty sentence must be "first application of X to Y with
  constraint Z", not "we propose an IT2 TSK system".

### 5.2 Quantum journal (Quantum Science and Technology, npj Quantum Information, Phys. Rev. Applied, IEEE TQE)

- **Scored contribution**: claim 3 only. "Noise as a range, not a number" is a hardware
  prediction claim and will be read as one.
- **What is expected**: all four baselines of §4, hardware counts as the reference, more than
  one backend or an explicit single-backend defence (advisor Q8), and a head-to-head with
  QuBound's framing (bound compliance and width over a long time split).
- **Risk**: the current archive (one backend, 868 states at NC-069, 3 chip-mean features) is
  thinner than QuBound's 700-day multi-device dataset, and the public 30-minute archive removes
  the "we have the data" argument. The spatially uniform channel (§2, fourth property) will be
  the first objection from anyone who has used `from_backend`; the paper needs either a
  per-qubit extension or a measured demonstration that homogeneity costs less than staleness on
  the benchmark circuits. The fuzzy layer's interpretability (27 readable rules) is the one thing
  QuBound's LSTM cannot offer; lead with it.

Which article to write is the team's and Dr. Akba's call (advisor File 05, Question 2). This
record does not choose. It does say that §5.2 cannot be started until §4 is measured, while
§5.1 can be *drafted* now (introduction, related work, method) and finished after the ablation.

---

## 6. Blind spots this check found

1. **The public calibration archive.** `phanerozoic/qiskit-calibration-drift` on Hugging Face
   (code: GitHub `CharlesCNorton/qiskit-calibration-drift`), CC-BY-4.0. Verified from the
   README: `poll.py` runs every 30 minutes on GitHub Actions and backfills 14 days of historical
   properties on every run. Verified from the dataset card (README, read 2026-10-23): four Heron
   backends (`ibm_fez`, `ibm_kingston`, `ibm_marrakesh`, and `ibm_torino` until its retirement on
   2026-04-27); per-qubit `T1` and `T2` in microseconds; `readout_error`, `prob_meas0_prep1`,
   `prob_meas1_prep0`, `readout_length`; per-gate error and length for `sx`, `x`, `id`, `rx`,
   `rz`, `cz`, `rzz` (lengths in ns); one row per calibration event keyed on
   (backend, property, qubit_a, qubit_b, calibrated_time); an `is_new_measurement` flag for
   heartbeat replicas; continuous coverage **from 2026-01-31**, about 3.5 months before this
   project's first snapshot of 2026-05-13 (the viewer's `calibrated_time` minimum of 2025-05-15
   is a parameter that was still current at the first poll, not continuous history). 28.9 million
   rows in one 98 MB parquet file. Licence CC-BY-4.0 except the `SN` column, which is CC-BY-NC.
   **Not yet measured**: whether the rows reconstruct, bit for bit, the snapshots this project
   archived over the overlap window, and how many *distinct device states in NC-012's unit* the
   extra months add for `ibm_fez`. The dataset's `is_new_measurement` is per property; the
   ledger's `qubit_digest` is per qubit block, so the two counts are not comparable until the
   project's own digest is run over reconstructed snapshots. Whether this closes the 868-to-1,170
   gap (NC-069) is therefore to be measured, not projected. Adoption is a data-provenance
   decision (ADR-020 schema, ADR-025 ledger rules, hash-the-blob discipline, ADR-027 units) and
   is not taken here.

   **Measured later the same day** (`docs/evidence/public-archive-overlap-2026-10/`, rows
   NC-077 to NC-079, decision drafted as ADR-029): of our 4,363,658 archived calibration
   events, 4,178,551 are in the public table with the identical value and none of T1, T2,
   readout error, gate error or gate length ever disagrees; replaying the table as of
   `calibrated_time` reproduces our qubit block bit for bit at 2,145 of 2,249 document
   timestamps, the rest being rounds their poller missed. For `ibm_fez` before our first
   snapshot it adds 626 distinct device states at hourly marks (666 half-hourly), taking the
   union with our 924 to 1,549 (1,589), above the 1,170 floor. Three defects are handled by
   stated rules: T1/T2 stored in seconds under the label `us` before 2026-05-07, qubit 72's
   omitted T1/T2 that an event table cannot express, and first-value-per-stamp. Our loader
   would not have caught the first. The archive-is-scarce assumption in the planning documents
   is therefore wrong, and the gate is met only when #63's builder reproduces the count.
   [Corrected 2026-10-26 on review: the counts and the mismatch attribution in this paragraph;
   see §9 item 3.]
2. **QuBound as the named competitor.** None of the project's planning documents mention it.
   The phase-3 plan's "paper track" row and the advisor File 05 should name it before venue
   is chosen.
3. **The empirical-percentile baseline** (§4 item 2) appears nowhere in the ADR ledger. ADR-016's
   alternatives list "interval-valued" aggregation without a non-fuzzy control. It should be
   added as a required comparison when ADR-016 moves.
4. **The 65% figure** from Ji et al. is a per-circuit peak; the mean is about 50%. If the team
   cites it, cite the mean.
5. **Spatial uniformity** (§2, fourth property) is a structural gap no open ADR names as a
   paper risk. ADR-013's deferred per-qubit extractor is the natural owner.

---

## 7. What this record does not do

- It does not register any numerical claim. Literature numbers above are quoted from their
  sources at the verification level stated; none is a measurement of this project.
- It does not change any ADR status.
- It does not decide venue, framing or data-source adoption.
- It ran no code and produced no experimental result.

---

## 8. Sources

Primary (arXiv unless stated):
[2507.17043](https://arxiv.org/abs/2507.17043) QuBound ·
[2105.09472](https://arxiv.org/abs/2105.09472), [2204.01529](https://arxiv.org/abs/2204.01529),
[2307.06833](https://arxiv.org/abs/2307.06833), [2208.10263](https://arxiv.org/abs/2208.10263),
[2404.13269](https://arxiv.org/abs/2404.13269) Dasgupta & Humble ·
[CEUR Vol-4211 paper 10](https://ceur-ws.org/Vol-4211/paper10.pdf) / [2603.14607](https://arxiv.org/abs/2603.14607) Bautra et al. ·
[2504.08313](https://arxiv.org/abs/2504.08313) Müller et al. ·
[EPJ QT 11 (2024)](https://epjquantumtechnology.springeropen.com/articles/10.1140/epjqt/s40507-024-00284-4) Bravo-Montes et al. ·
[2506.03636](https://arxiv.org/abs/2506.03636) Maschek et al. ·
[2509.12933](https://arxiv.org/abs/2509.12933) Ji et al. (PR Applied 25, 034051) ·
[Quantum 8, 1556](https://quantum-journal.org/papers/q-2024-12-10-1556/) van den Berg & Wocjan ·
[2512.08165](https://arxiv.org/abs/2512.08165) Lindblad from time series ·
[2005.10811](https://arxiv.org/abs/2005.10811) Zlokapa & Mitra ·
[2604.24397](https://arxiv.org/abs/2604.24397) few-shot transfer ·
[2604.20804](https://arxiv.org/abs/2604.20804) Kraus on tensor networks ·
[2602.21253](https://arxiv.org/abs/2602.21253) Hassan & Kaabouch ·
[2402.01815](https://arxiv.org/abs/2402.01815) fuzzy clustering ·
[2601.18897](https://arxiv.org/abs/2601.18897) IT2-ANFIS UQ ·
[2109.11405](https://arxiv.org/abs/2109.11405) Martina et al. noise fingerprint ·
[2511.18225](https://arxiv.org/abs/2511.18225) adaptive conformal prediction for QML.

Grey literature: [qiskit-calibration-drift](https://github.com/CharlesCNorton/qiskit-calibration-drift) ·
[staleness-project](https://github.com/RealAradhyaGupta/staleness-project).

Citing-paper lists: Semantic Scholar Graph API, 2026-10-23.

---

## 9. Review amendments, 2026-10-26 (Bengisu's review of PR #121)

The record above is dated 2026-10-23 and is not rewritten; each correction is marked at its
original location and stated here in full.

1. **Width metric (§4).** "Hellinger between the band's edges" is withdrawn. Componentwise
   quantile endpoints are not probability distributions: for two members `(0.2, 0.8)` and
   `(0.8, 0.2)` the central 80% band has lower edge `(0.26, 0.26)` and upper edge
   `(0.74, 0.74)`, summing to 0.52 and 1.48; normalising both gives `(0.5, 0.5)` twice and a
   Hellinger distance of zero for a band of substantial width. The width metrics for the
   gating test are the explicitly defined ones the PR-A plan already names: mean band width
   per bin (mean over bins of upper minus lower, in probability) and the interval score
   (Gneiting and Raftery eq. 43 at the band's nominal level), which penalise width and
   miscoverage together. A distribution-space diameter would need an optimisation over valid
   distributions inside the band and is not proposed. The centre's Hellinger and fidelity
   stand.
2. **QuBound's output scope (§1 row 3, §2 second property, §3.1, §4 item 4).** The record
   described QuBound as predicting one fidelity number per circuit with bounds. Its evaluation
   (arXiv 2507.17043v1, Sections VI-A to VI-C, read 2026-10-26) predicts, for a fixed circuit
   and shot count, bounds and a central value on computational-basis outcome probabilities
   (per bitstring, output layer sized to the number of states, GHZ-3 states shown
   individually) and on observable expectations (`Z` tensor products, VQE Pauli terms
   bounded and summed); its Section III states that fidelity itself is not the predicted
   quantity. The paper frames the model as targeting one fixed circuit and leaves unseen
   circuits to future work; nothing it outputs can be loaded into a simulator. The defensible
   distinction is therefore **a reusable, simulator-ready channel model (this engine) versus
   circuit-conditioned performance prediction (QuBound)**, not "noise model versus fidelity
   scalar". Consequently the QuBound-style baseline of §4 item 4 applies whenever the gating
   test scores distributions or observables, which is every case in §4, not only a fidelity
   comparison; the item's condition is dropped. §1 row 3's verdict is unchanged: the
   bracketing claim still has a published competitor on bound compliance and width.
3. **Evidence figures (§6 item 1).** The comparison script was re-run at the same two refs
   after two faults the review found. (a) The pre-window replay started at
   2026-01-31T00:00Z with a state holding T1 and T2 only (the table's first readout events are
   at 13:18 to 13:19Z); a completeness rule now counts a mark only when every non-excluded
   qubit holds T1, T2 and the three readout quantities. The pre-window count is 625 hourly
   (664 half-hourly), 14 (28) marks excluded, union with our 924 1,548 (1,587); the floor
   comparison and the conclusion do not change. (b) "The rest being rounds their poller
   missed" was wrong: classified by stamp, 4 of the 104 mismatching documents carry a
   same-stamp `readout_length` conflict (IBM's June and July republications, the source of
   NC-077's 312 differing `readout_length` events) and most of the others differ because the
   public table is minutes ahead of the served document. The stated "ours wins" rule was never
   applied by the replay and is withdrawn; the replay is unmodified and the conflicts are
   named. Details and the old-to-new table: the evidence README's "Corrections on review"
   section; rows NC-077 to NC-079 carry the same corrections.

Project documents: `README.md`, `docs/architecture.md`, `docs/decisions.md` (ADR-002, -008,
-009, -013, -014, -015, -016, -019, -021, -025, -027), `docs/numerical-claims.md` (NC-012,
NC-025, NC-045, NC-047, NC-069), `src/superconducted/integration/aer_factory.py`,
`src/superconducted/channels/kraus.py`, `docs/findings/2026-05-25-empirical-synthesis.md`,
`docs/advisor/2026-05-25-questions-for-akba.md`,
`docs/advisor/2026-09-09-akba-brief/05-yayin-stratejisi.html`,
`docs/state-of-the-project/2026-09-09-cycle-2-close.md`.
