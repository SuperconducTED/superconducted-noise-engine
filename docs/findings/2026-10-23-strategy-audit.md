# Strategy audit: what the day's measurements leave open for a good, novel Q1 article

**Date**: 2026-10-23 · **Requested by**: Mert Efe Şensoy, after the predictability result ·
**Measured against**: the records of the same day (`2026-10-23-novelty-check-q1-article.md`,
`2026-10-23-adr-015-what-an-interval-needs.md`, `docs/evidence/public-archive-overlap-2026-10/`,
`docs/evidence/persistence-band/`, `docs/evidence/predictability/`; rows NC-077 to NC-085) ·
**Status**: assessment. No score is invented; every "for" and "against" cites a row or a
search. This file sits at the top of the PR stack and merges last.

## 0. What today changed, in order of how much it hurts

1. **The drift-bracketing claim is dead as stated.** "A fuzzy band brackets the hardware across
   calibration cycles better than a frozen model" loses to a parameter-free rolling 30-day
   percentile band on interval score in every case measured (NC-081), state-conditioning has
   at most 11 to 14% of width to gain (NC-082), and per-qubit drift is noise around a level
   with no forecastable structure above level tracking (NC-084, NC-085). No model built on
   calibration history, fuzzy or deep, changes that on this device.
2. **The engine's channel is spatially uniform, and that costs more than a week of staleness**
   (NC-083). A quantum-venue reviewer sees this before anything else. Whatever strategy wins,
   a quantum-venue paper needs per-qubit channels.
3. **The fuzzy map's novelty is untouched.** Nobody has published a fuzzy or IT2 TSK map from
   calibration to simulator channels (novelty check §3.4, §3.5). What died is the claim about
   what the band does over time, not the method or its domain.
4. **The deep model's room from calibration history is bounded at zero** (NC-084's cap,
   NC-085's gap). It returns only with inputs the archive does not carry.
5. **The measurements produced a claim the original pitch did not have.** Each per-qubit
   reading is a slowly moving level plus independent scatter of about 0.37 log units.
   Whatever that scatter is, the quantity a noise model should carry at run time is the
   qubit's level, not its latest reading. Every calibration-based model found in the search,
   and this engine, uses the latest reading. In the compilation setting, Kurniawan et al.
   (arXiv 2407.21462, IBM Perth and Brisbane) found pre-processed historical calibration more
   robust than the latest reading; a search for the same comparison on the simulator side
   found nothing. That is prior art and corroboration at once, and an open position.

## 1. The strategies

Each with the same fields: the claim, evidence for and against from today's rows, what is
still needed, cost, venue class, and what kills it.

### S1. A level-tracking per-qubit channel, with the IT2 band around the level

- **Claim.** Noise models should carry each qubit's calibration level, not its latest
  reading; a per-qubit level-tracking channel predicts hardware better than
  `NoiseModel.from_backend` and than every calibration-based twin in the literature, and the
  fuzzy or IT2 band around the level is the honest range.
- **For.** NC-083 (per-qubit beats uniform, decisively for lambda); NC-084 and NC-085 (the
  level is the only forecastable object; shrinkage reaches the cap); NC-081 (a band centred
  on the recent range beats one centred on the last value); File 03's footprint is already a
  band around a centre; the fuzzy map (claim 1 of the novelty check) survives as the
  interpretable layer. Compilation-side precedent exists, simulator-side does not.
- **Against.** Entirely target-space so far. Whether the 0.37 log-unit scatter is the
  calibration measurement's own noise or genuine fast fluctuation decides whether "level"
  predicts hardware or merely predicts the next reading; the archive cannot tell, and IBM's
  properties carry no per-fit error bars. Needs ADR-013's per-qubit extractor, which touches
  Baha's and Burak's modules and multiplies the training table by 156.
- **Still needed.** S2 as the decisive test; the per-qubit extractor; a per-qubit training
  table (#63's builder, source column from ADR-029); the band's scale per qubit from the
  rolling percentile or from the IT2 footprint sized by the measured scatter.
- **Cost.** Three to four months after S2 reports, if S2 passes.
- **Venue class.** Quantum (QST, npj QI, PR Applied) if S2 passes; fuzzy-systems otherwise.
- **What kills it.** S2 showing that the latest reading predicts hardware decay as well as or
  better than the level: the scatter would then be physics the device actually expresses,
  and the right object is the range, not the level.

### S2. The hardware reading-versus-level test

- **Claim.** None of its own: it decides S1.
- **Design.** Idle-heavy circuits (delay-based decay on chosen qubits; File 03 found only
  `sx^100` and longer resolve a drift-sized band) run on `ibm_fez` repeatedly over days;
  predicted decay from the latest reading, from the 30-day level, and from the band, scored
  against the measured counts on change events. Qiskit Experiments gives per-fit standard
  errors for a self-measured T1, which answers the noise-versus-physics question directly;
  IBM's properties do not.
- **For.** No model needed; the cheapest route to anything a quantum venue scores; it also
  measures outcome-space resolution on hardware, which gates every quantum-venue claim.
- **Against.** Hardware time. Delay circuits are tiny, but the run must repeat over days to
  catch change events, and the open plan's monthly allowance may or may not cover it; this
  is not on record and must be checked before planning. Queue delay between submission and
  execution is itself a staleness that the analysis must account for (QuBound's framing).
- **Cost.** Two to three weeks of calendar time, little engineering; Burak's track (harness,
  circuits, desktop verification).
- **What kills it.** No hardware access at the needed cadence.

### S3. The fuzzy-systems paper with the honest ladder as its evaluation

- **Claim.** First interval type-2 TSK map from calibration features to CPTP simulator
  channels, with a principled uncertainty split (epistemic across members, aleatoric in
  shots), evaluated against a ladder of non-fuzzy baselines on change events, and the measured
  negative result that state-conditioned bands have little headroom on this device.
- **For.** Claim 1 and 2 of the novelty check stand; fuzzy-systems venues accept simulator
  evidence and value clean ablations and clean uncertainty accounting; the ladder
  (persistence, shrinkage, rolling band, IT2 band) now exists with its rows (`pairs.tsv`,
  `rows.tsv.gz`); the IT2 double-count result (File 03 D3) is a genuine methods finding.
- **Against.** It is a methods paper; the IT2 band will most likely tie the rolling band, and
  the text must say so. Nie-Tan, hybrid ANFIS and the footprint must be presented as
  textbook, not new (novelty check §5.1).
- **Still needed.** #64 PR-A (plan approved, waiting on Bengisu's D1 to D5), the trainer's
  first archive fit (#60), ADR-019's ablation (#62), Karnik-Mendel for the IT2 arm (#61).
- **Cost.** About three months of the existing plan; nothing new to design.
- **Venue class.** IEEE Transactions on Fuzzy Systems, Fuzzy Sets and Systems, Applied Soft
  Computing (quartiles to be verified).
- **What kills it.** Nothing measured today. The risk is a reviewer who wants a hardware
  number; S2's result, whichever way it goes, answers that.

### S4. A device-dynamics measurement paper across the three live Heron backends

- **Claim.** On IBM Heron processors, per-qubit coherence calibrations behave as a slowly
  moving level plus independent scatter (lag-1 autocorrelation of increments near minus 0.5),
  the chip mean reverts toward a level on a 30-day scale, a single fitted drift scale is
  non-stationary within two months, and a fresh chip-uniform noise model is worse than a
  week-stale per-qubit one.
- **For.** All four results exist for `ibm_fez` (NC-080 to NC-085); the public archive under
  ADR-029's rules extends them to `ibm_kingston` and `ibm_marrakesh` with the same scripts;
  the protocols are pre-registered and the scripts committed.
- **Against.** Modest novelty: Dasgupta and Humble's stability line, the IQM 250-day
  health-analytics paper (WIHPQC 2025) and the step-fluctuation detection paper (arXiv
  2307.04337) occupy the neighbourhood. The autocorrelation result and the staleness
  comparison are, as far as the search went, new; the rest is corroboration.
- **Still needed.** ADR-029 adopted; the scripts pointed at the three backends; the unit and
  omission rules applied; cross-device tables.
- **Cost.** Two to three weeks. Nearly free relative to everything else.
- **Venue class.** IEEE TQE or QCE for the short form; a Q1 only as a section of S1 or S3.
- **What kills it.** Nothing; it can only be scooped, and the dataset's author is the likely
  scooper.

### S5. Readout-error predictability

- **Claim.** None yet. It is the one of the three features not measured, it refreshes about
  every 4.4 hours (File 03 M2), and the IQM paper reports autocorrelation in daily readout
  fidelity. If readout error carries memory, a forecaster has a target after all, and A7
  survives for that component.
- **Cost.** One day with the predictability script extended to readout error; no model.
- **What kills it.** The same minus 0.5 autocorrelation. Then the deep engine has no target
  anywhere in the calibration table.

### S6. The deep model with exogenous inputs

- **Claim.** Calibration drift is partly driven by measurable external covariates
  (temperature, pressure, geomagnetic indices, cosmic-ray flux), and a model fed those
  forecasts the level or the scatter better than own history.
- **For.** The public dataset carries those covariates already aligned to each calibration
  event, and its own 2026-05-20 report claims associations with geomagnetic indices.
- **Against.** High variance, sceptical field, the dataset's author may publish first, and the
  measured common-mode share of a qubit's change is 2% for gamma and 0.1% for lambda
  (NC-085): whatever drives drift, it does not move qubits together, which is what an
  environmental driver would do. A pre-registered test is cheap; a paper on it is a gamble.
- **Cost.** One week for the pre-registered correlation test; months for a model.
- **What kills it.** The common-mode result already nearly does.

### S7. Calibration-age-aware model selection

- **Claim.** Given the expected queue delay, which channel to carry: fresh uniform, stale
  per-qubit, level-tracking; a decision rule with measured crossover times.
- **For.** NC-083 is the first row of that table; QuBound's framing (bounds for scheduling)
  is the published neighbour; the staleness course project shows the question is live.
- **Against.** Systems venue, incremental, and S1 subsumes it if S1 passes.
- **Cost.** Two weeks on top of S4.
- **Venue class.** QCE, TQE; Q1 unlikely.

## 2. Recommendation

Not a menu. **S1 is the contribution, S2 is its decisive test, S3 is the paper that exists
in three months whatever S2 says, S4 is the cheap hedge that strengthens both, S5 runs before
A7 is revisited, S6 is a hedge and not a plan, S7 is a section of S4.**

| Piece | Owner | First step |
| --- | --- | --- |
| S2 hardware test | Burak (harness, circuits, desktop) | confirm the plan's hardware allowance and queue behaviour; design the delay circuits and the repeat schedule |
| S1 per-qubit extractor and table | Baha (`calibration/`, #63) with Burak (`aer_factory.py`) | ADR-013 decision; the per-qubit training table from #63's builder |
| S3 band and metrics | Bengisu (#64, `metrics.py`) with Mert authoring PR-A | her D1 to D5 answers |
| S4 cross-device tables | Baha (archive, ADR-029) | adopt ADR-029; point the two scripts at three backends |
| S5 readout predictability | Mert | extend `measure_predictability.py` to readout error |

The venue decision stays with Mert and Dr. Akba.

## 3. Scope statements the plan must not lose

- A quantum-venue paper is impossible without per-qubit channels (NC-083), whichever
  strategy wins.
- Everything measured today is target space. Outcome-space resolution on hardware (PR #79's
  density-matrix mode, idle-heavy circuits) is unmeasured and gates every quantum-venue
  claim; S2 is where it gets measured.
- Phase 3 ends on 2026-10-31 (phase-3 plan). Q1 review cycles are long: a submission of S3
  in early 2027 is realistic; S1 with S2 later than that.
- Decision A7 of the three-engine plan (forecast the target at `t + h`) rests on a premise
  NC-084 and NC-085 contradict for T1 and T2. That is Issue #110's decision to revisit, after
  S5 reports on readout.

## 3.1 The second goal, stated by the lead on 2026-10-23 (appended after §0 to §3 were written)

Beside the article, the engine exists for a practical reason: engineers turning digital
circuit designs into physical ones on IBM hardware are not reaching the fidelity they expect,
and Aer's stock noise model, built from the latest calibration reading, is not a useful guide
to what will happen at run time. The engine should be a materially better design-time
predictor: which physical qubits to use, how deep the circuit can be, what fidelity to expect,
with an honest range.

What this does to the audit:

- It makes S1 a product requirement, not only a paper claim. The user-facing metrics are
  fidelity prediction error and layout-ranking accuracy at run time against hardware, compared
  with `NoiseModel.from_backend` and with a stale per-qubit model (NC-083's table is the first
  row of that comparison).
- It widens S2 from decay on idle circuits to the decisions an engineer makes: for a given
  circuit, several candidate layouts, predicted fidelity from the latest reading, from the
  level and from the band, scored against the measured fidelity on each layout. The
  compilation-side precedent (arXiv 2407.21462: historical calibration more robust than the
  latest for layout choice on IBM Perth and Brisbane) says the effect is real for the choice
  itself; the engine's job is to predict the fidelity and its range, which that work did not.
- It makes the per-qubit channel non-negotiable in the same way the quantum venue does, and it
  makes staleness a first-class input: an engineer's prediction is made hours before the job
  runs.
- It does not change the order of §2. S5 and S2 remain the first two steps; S2's design gains
  the layout-ranking arm.

## 4. Related

`docs/findings/2026-10-23-novelty-check-q1-article.md` §4, §5;
`docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`;
`docs/roadmap/2026-10-23-issue-64-pr-a-plan.md`; `docs/decisions/drafts/ADR-029-*.md`;
Issues #60, #61, #62, #63, #64, #104, #110, #122; PRs #79, #111, #121, #123, #124;
arXiv 2407.21462, 2508.21231, 2307.04337, 2507.17043.
