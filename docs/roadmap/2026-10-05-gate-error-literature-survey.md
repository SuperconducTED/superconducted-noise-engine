# Literature survey: forecasting gate and readout errors · as of 2026-10-05

Written 2026-10-05 for Issue #110 (decision A9, gate errors as a second target) on the PR
#111 branch. This is a dated research document: reconcile it later by appending an as-of
section, never by editing the text below. It extends
`docs/roadmap/2026-10-04-deep-engine-architecture-research.md` (called "the existing
survey" below) and feeds the verdict in
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` §3.

**How it was made.** One survey pass, delegated to a research agent on 2026-10-05, was given
the two targets, the project's constraints (hand-written NumPy, about 243 trainable
parameters, an uncertainty band, a time split, persistence as the mandatory reference), a
definition of "most successful" (beats persistence on point error and band score on a time
split, on short irregular series, NumPy-feasible within the budget), and the existing
survey's 67 sources so it would hunt the gap instead of repeating them. Its rule: every
citation carries an arXiv ID or DOI fetched in that pass; anything it could not fetch is
listed under "unverified leads" (§4). The text from §1 on is that pass's report, unchanged.

**What was checked afterwards, on 2026-10-05.**

- **Identifiers.** All 50 arXiv identifiers cited in §1 to §3 were resolved again against the
  arXiv API and all 4 DOIs against Crossref. Every one resolved, and every returned title is
  the work the text names (eight rows use a short name, such as N-HiTS, Chronos, fev-bench or
  CaliScalpel, and were matched by hand).
- **Abstracts.** The abstracts of the 16 sources the feature-patterns document relies on were
  read (its §8 lists them).
- **Beyond the abstract.** Of the claims flagged **[beyond abstract]**, one was checked against
  the paper's own text: Hassan and Kaabouch 2026 (arXiv:2602.21253) state that one
  non-operational `ibm_fez` qubit reported the 1.0 sentinel and inflated the mean single-qubit
  gate error by about 25 times. Every other beyond-abstract claim, including the correction to
  Baheri et al. 2022 (the paper is not open access), is the survey pass's reading.
- **[derived here] numbers** are the survey pass's own arithmetic, not a paper's result. The
  median EPG-to-coherence-limit ratio of 2.67 from Stehlik et al. 2021 Table I was not re-derived.

**Project-side questions in §1 that the archive has since answered** (provisional, all
1,753 `ibm_fez` files at `calibration-data` `09fcc45`, `scripts/feature_patterns.py`):

- **Per-gate-type cadence (§1, dependency (a)).** `sx`, `cz`, `rzz`, `T1` and `T2` are
  re-measured in daily rounds, about 130 events per qubit or coupler; readout about every 4.5
  hours, about 580 per qubit (feature-patterns document, P1). The zero-residual trap is
  avoided by using re-measurement events, not files, as rows.
- **`rzz` gate length (dependency (d)).** Every `rzz` record in the archive carries a
  `gate_length` (all 617,056 `rzz` records, both directions), and the coherence limit was computed with it (P4).
- **Placeholders (dependency (c)).** `gate_error = 1` is masked before any event is counted
  and handled as a state (P7): at most 13 entries into it per family over five months.
- **Autocorrelation of changes at the re-measurement cadence** (listed as missing in §1):
  measured, -0.42 to -0.50 in every family (P2).

---

## 1. Executive verdict

### Target 1: sx, cz, rzz and readout error at t+h

**What the literature supports.** No paper found forecasts single-qubit, two-qubit or
readout error of a superconducting cloud device on a time split and reports skill against
persistence. The closest temporal work either reports accuracies on plotted series labelled
"Fits" with no held-out split, horizon or naive baseline described (Baheri et al. 2022, read
in full here; that the fits are in-sample is this survey's inference), predicts circuit-level bounds rather than gate errors (QuBound, LSTM), or
evaluates calibration-data policies by compiled-circuit fidelity rather than forecast error
(Kurniawan et al. 2024). So "most successful" under this survey's definition cannot be
answered from published results. The best-supported design is assembled from indirect
evidence, and it is the same shape the existing survey recommends for target 2:

1. **Shrinkage of persistence toward a per-qubit or per-coupler running mean** (Engine). Indirect
   support: windowed means of historical calibration data beat the latest snapshot for
   compilation on two IBM devices (Kurniawan et al. 2024, beyond abstract); on 9 IBM Falcon
   machines, KPSS tests found readout error series stationary, while CNOT p-values
   fluctuated between stationary and non-stationary (Baheri et al. 2022, beyond abstract); CX and readout error vary far more over time than
   qubit frequency (Smith et al. 2022, beyond abstract).
2. **A physics floor plus a learned multiplicative residual** (Engine): forecast the
   coherence limit from forecast T1/T2 and the gate length (closed form, §2.2), and learn
   only `log(e_reported / e_coh)`, shared across qubits or couplers. Indirect support: a
   physics-structured error model with 16 trainable weights predicted benchmarked cycle errors
   on a 68-qubit Google processor within two factors of experimental uncertainty (Klimov et
   al. 2024, beyond abstract). No paper applies this to fixed-frequency IBM devices or to
   forecasting; this design is this survey's proposal, not a literature result.
3. **A global (pooled) ridge or OLS model on lags** (Engine): linear variants used in deep
   forecasting reduce to closed-form least squares, which was the better forecaster in 72% of
   test settings (Toner and Darlow 2024).
4. **Bands:** online conformal with decaying step sizes or the parameter-free betting variant,
   and AcMCP when `h > 1` (§2.4).

**References that must be beaten.** Persistence (mandatory); a windowed or exponentially
smoothed mean per qubit/coupler (the only baseline with any empirical hint of value on IBM
calibration data); for `sx` and `cz`, the coherence limit alone (zero learned parameters).
For readout error and the two `prob_meas` fields there is no physics floor: nothing fetched
derives a readout floor from the published properties, so their references are persistence
and shrinkage only, and the literature is silent on a physics baseline. External references,
never the engine: TabPFN-TS and one Chronos-family zero-shot model. These are not straw men:
one 2026 break-even study reports foundation models winning on half of 30 datasets regardless
of data volume, while another study found them consistently beaten by simple linear baselines
on cloud data (§2.4). Which regime the archive is in is an empirical question.

**Evidence that is missing (the literature is silent):**
- any skill-vs-persistence result for gate or readout error, at any horizon, on any device;
- any autocorrelation or memory statistic of gate-error or readout-error *changes* at the
  re-measurement cadence (Dasgupta and Humble's 22-month study reports Hellinger distances
  only; it reports no autocorrelation, stationarity test or distribution shape, beyond
  abstract);
- anything at all on the temporal behaviour of `rzz` (fractional) gate errors;
- a published measurement of how far Heron-class RB errors sit above the coherence limit
  (only older IBM test devices and non-IBM tunable-coupler results exist; §2.2);
- any method that forecasts discrete fault events (a qubit or coupler turning unusable)
  at the calibration cadence (§2.3).

**Project-side dependencies the literature cannot settle.** (a) Gate and readout errors are
re-measured in separate per-gate-type rounds whose cadence is still being measured, so the
existing survey's zero-residual trap (§0 there) must be re-checked per gate type before
target 1's transition count is known. (b) The target is IBM's *next reported measurement*,
taken at recalibration; drift between calibrations (Wilson et al. 2020; CaliScalpel; IBM's
own tutorial) never appears in the reported series, so it is not part of the forecast target.
(c) `gate_error = 1` placeholders must be handled as a separate event channel, not as a
regression value: on `ibm_fez` one such sentinel inflated a 156-qubit mean single-qubit gate
error by a factor of about 25 (Hassan and Kaabouch 2026, beyond abstract). (d) The
coherence floor needs each gate's duration. A fractional `rzz` gate's duration may depend on
its angle, so whether the properties document carries a usable `rzz` length is a project-side
check; until it is confirmed, `rzz` has no physics floor either.

### Target 2: per-qubit (gamma, lambda) at t+h

The existing survey's recommendation stands, and nothing found contradicts it. What this
survey adds:
- **Bands.** Online conformal with decaying step sizes (Angelopoulos, Barber, Bates 2024) is
  the natural first upgrade over plain ACI: its abstract claims coverage close to the target
  "for every time point" when the distribution is stable, which suits a series of about 131
  epochs. Betting-based ACI removes the step-size choice. AcMCP is needed as soon as `h`
  exceeds one epoch, because optimal h-step errors are serially correlated up to lag `h-1`.
  All three are NumPy-feasible (Engine).
- **Physics prior.** TLS dynamics destabilize T1 on hour timescales, and radiation impacts
  can make several TLSs jump at once (Thorbeck et al. 2023), adding to the existing survey's
  prior that daily T1 changes are largely aliased switching around a level.
- **Correction to a cited source.** Baheri et al. 2022 (already in the existing survey as
  "statistical forecasts") reports MAPE on plotted series labelled "Fits" and describes no
  held-out split, horizon or naive baseline (beyond abstract). It is not evidence of forecast
  skill.
- **Missing:** no paper forecasts T1/T2 or a function of them against persistence on a time
  split. External references: TabPFN-TS and a Chronos-family model, as for target 1.

---

## 2. Findings by gap area

### 2.1 Temporal modelling of gate and readout errors

| Finding | Source |
| --- | --- |
| **Window averages beat the latest snapshot for compilation.** Abstract: "pre-processing historical calibration data can improve fidelity when real-time calibration data is not available". Beyond abstract: four policies (latest, mean of all stored, mix, window of `nn` days); on ibm_perth an average improvement of 0.08% (up to 4.09%) over latest, on ibm_brisbane 8.32% (up to 41.76%); latest-only data let fidelity drop more than 30% on one day while a 15-day window did not. This is compiled-circuit fidelity, not forecast error, so it hints that shrinkage helps but is not skill in this survey's sense. | Kurniawan et al. 2024, arXiv:2407.21462 |
| **The existing survey's forecasting source describes no held-out evaluation.** Read in full: data from 9 IBM Falcon machines, July 2020 to April 2022; KPSS tests show T1/T2 mostly stationary, readout and CNOT "satisfy the stationary trend", CNOT p-values fluctuate between stationary and not; SES gave "23% accuracy", DES "47% to 80%", Winters' method the highest; Fig. 7 reports MAPE 27.878 for one qubit's T1 on a series labelled "Fits". No held-out split, horizon, persistence baseline or interval is described. | Baheri et al. 2022, doi:10.1109/IOLTS56730.2022.9897404 [beyond abstract] |
| **Gate and readout errors are the noisy fields; frequency is stable.** Abstract: qubit-frequency fingerprints show "excellent inter-device separation and intra-device stability" over 25 IBM machines. Beyond abstract: "qubit frequency does not fluctuate at the same extent as gate error"; CX error values "are much more noisy"; readout error shows "variation over time". Implication: frequency and anharmonicity are near-static covariates; gate errors need a noise-aware target. | Smith et al. 2022, arXiv:2211.07880 [beyond abstract] |
| **Large fluctuations, but no forecasting statistics.** Abstract: "observations collected over 22 months reveal large fluctuations in each metric". Beyond abstract: Yorktown, 673 daily records (March 2019 to December 2020); no day-to-day change, autocorrelation, stationarity test or distribution shape is reported. The 2020 and 2023 companion papers use histogram distances and an analytic stability bound, likewise without forecasts. | Dasgupta and Humble 2021, arXiv:2105.09472 [beyond abstract]; 2020, arXiv:2008.09612; 2023, arXiv:2307.05381 |
| **A tunable-coupler CZ held its calibration over a day.** Abstract: "the calibration is stable over one day". Beyond abstract: interleaved RB repeated over a 19-hour period without recalibration; excursions "at worst, 60% worse"; "no clear drift towards degraded performance". IBM test devices from 2021, not Heron r2. | Stehlik et al. 2021, arXiv:2101.07746 [beyond abstract] |
| **A conflicting drift claim.** CaliScalpel models post-calibration drift as `p(G,t) = p(G,0) 10^{t/T(G)}` with log-normal `T(G)`, mean 14.08 h, "based on our measurements of IBM's 127-qubit Eagle processor"; the measurement protocol is not documented. Treat as that paper's modelling assumption, not a validated rate. Either way it concerns drift between calibrations, which the reported series does not show. | Fang et al. 2024, arXiv:2412.02036 [beyond abstract] |
| **Fresh measurement beats daily calibration.** Abstract: measuring readout and two-qubit errors just before execution improves circuit accuracy "by 3-304% on average" over IBM's mapping with daily calibration. Same point, vendor side: IBM's tutorial says properties are "updated once a day, but the system may drift faster" (vendor documentation, no identifier; see §4). | Wilson et al. 2020, arXiv:2005.12820 |
| **Sub-calibration step changes.** Abstract: on continuously monitored qubits, "a step-like change in the error rates ... each step persists for several minutes". Such steps alias into the daily series as noise. | Hirasaki et al. 2023, arXiv:2307.04337 (doi:10.1063/5.0166739) |
| **Learned temporal model, circuit level.** Abstract: QuBound decomposes historical performance traces and uses an LSTM to predict circuit performance *bounds*; baseline is another learned single-value predictor, not persistence. Reference only (LSTM, framework). | Li et al. 2025, arXiv:2507.17043 |
| **Day-to-day variation used for decisions, not forecast.** 12 days of ibm_kyiv sx and CNOT errors drive a per-qubit code-distance choice that "reduces physical qubit overhead by over 50%" while keeping "85-100% of usable qubits". | Das and Ghosh 2025, arXiv:2505.06165 |
| **Historical variability studies.** IBM-Q20 data "gathered over 52 days" show "significant variability in the error rates of the qubits and the links"; noise-adaptive mapping exploiting "fine grained spatial and temporal variations" gives "an average 2.9x (and up to 18x) improvement". Neither reports temporal statistics usable for forecasting. | Tannu and Qureshi 2018, arXiv:1805.10224; Murali et al. 2019, arXiv:1901.11054 |
| **RB estimates are precise under Markovian noise.** Abstract: estimates from standard and interleaved RB "are remarkably precise", with confidence bounds set by the number and length of sequences. IBM's production RB settings are not published in any fetched source, so the estimation-noise floor of the archive's gate errors must be measured from the archive itself. | Wallman and Flammia 2014, arXiv:1404.6025 |

### 2.2 Cross-sectional explanation: the coherence limit

**The formula and its citable pieces.** No fetched source prints the closed form
`F_avg = (3 + e^{-t/T1} + 2 e^{-t/T2})/6` verbatim. It follows exactly from two cited results:

1. **The channel and its process fidelity.** Ghosh, Fowler and Geller write the combined
   amplitude-plus-phase-damping channel with `1 - p_AD = e^{-t/T1}` and
   `sqrt((1-p_AD)(1-p_PD)) = e^{-t/T2}` (their eqs. 5 to 7), and its Pauli expansion (eq. 9).
   The coefficient of `I rho I` in eq. 9 is the process fidelity:
   `F_pro = (2 - gamma + 2 sqrt(1-gamma-lambda))/4 = (1 + e^{-t/T1} + 2 e^{-t/T2})/4`.
   Their Pauli-twirl probabilities (eq. 10), `p_X = p_Y = (1 - e^{-t/T1})/4` and
   `p_Z = (1 - e^{-t/T2})/2 - (1 - e^{-t/T1})/4`, give the same value as `1 - p_X - p_Y - p_Z`.
   [beyond abstract; Ghosh et al. 2012, arXiv:1210.5799]
2. **Average from process fidelity.** Nielsen's abstract gives a "simplified proof of a formula
   due to Horodecki et al ... connecting average gate fidelity to entanglement fidelity",
   which is `F_avg = (d F_pro + 1)/(d + 1)` (the standard form; not printed in the abstract).
   With `d = 2` this yields the closed form above.
   Pedersen et al. give the same average-fidelity formula for multi-component systems.
   [Nielsen 2002, arXiv:quant-ph/0205035; Pedersen et al. 2007, arXiv:quant-ph/0701138]
3. **Two-qubit version.** For independent channels on the two qubits, process fidelities
   multiply, and `d = 4`: `F_avg = (4 F_pro,1 F_pro,2 + 1)/5`.
4. **First-order check, directly citable.** Abad et al. eq. 12:
   `F_avg = 1 - d/(2(d+1)) * tau * sum_k (Gamma_1^k + Gamma_phi^k)`, with `Gamma_1 = 1/T1`
   and coherence decay `1/T2 = Gamma_1/2 + Gamma_phi`. For one qubit this is
   `1 - (Gamma_1 + Gamma_phi) tau / 3`; for two, `1 - (2/5) tau sum_k(...)`. Abstract: the
   reduction "is independent of the specific operation; it depends only on the operation time
   and the dissipation". [beyond abstract for the equation; Abad et al. 2022,
   arXiv:2110.15883] **[derived here]** the exact one-qubit form and eq. 12 agree to about
   1e-8 at `t = 24 ns`, `T1 = T2 = 100 us`.

Caveat for the project: whether IBM's `gate_error` in the properties document is exactly an
average-gate infidelity (RB's standard output) is not confirmed by any fetched source.

**How far measured RB errors sit above the limit.**

| Evidence | Source |
| --- | --- |
| Transmon single-qubit RB error `(7.42 ± 0.04)e-5` against "decoherence errors lower bounded by `(4.62 ± 0.04)e-5`" plus leakage `(1.16 ± 0.04)e-5`. **[derived here]** total over decoherence bound is about 1.6. Not IBM. | Li et al. 2023, arXiv:2302.08690 |
| IBM single-qubit gates at 99.95%: fidelity is "not limited by unitary errors, but by another drive-activated source of decoherence such as amplitude fluctuations", i.e. an excess above the idle T1/T2 limit. | Sheldon et al. 2016, arXiv:1504.06597 |
| IBM 13.3 ns `X_{pi/2}` with error `1.95(3)e-4`; leakage is "two orders-of-magnitude smaller than pulse errors due to decoherence". | McKay et al. 2017, arXiv:1612.00858 |
| IBM tunable-coupler CZ, eleven 2021 test pairs (Table I: T1, T2, gate time, EPG). **[derived here]** assigning each pair's listed average T1/T2 to both qubits, tensor-product channel, `d = 4`: EPG over coherence limit has median 2.67 (range 0.96 to 5.46). Pair 11 below 1.0 shows a pair-averaged limit is not a strict bound. A proxy from test chips, not a Heron r2 measurement. | Stehlik et al. 2021, arXiv:2101.07746 [beyond abstract] |
| Non-IBM tunable-coupler CZ (99.76%) and iSWAP (99.87%) are "close to their T1 limits". | Sung et al. 2021, arXiv:2011.01261 |
| IBM fixed-coupler CNOT 99.77% by interleaved RB, with T1, T2 above 100 us; the abstract makes no coherence-limit comparison. | Kandala et al. 2021, arXiv:2011.07050 |
| Heron (ibm_montecarlo) error per layered gate `6.2e-3` (N = 80) versus `1.7e-2` on Eagle; a layered metric that includes crosstalk, so not comparable with isolated RB. | McKay et al. 2023, arXiv:2311.05933 |

**Verdict for gap 2.** The formula is citable in pieces. The excess ratio for Heron r2 is
not published in any fetched abstract. The archive can measure it directly: each snapshot
carries T1, T2 and the gate errors, and a learned residual `log(e / e_coh)` is exactly that
ratio.

### 2.3 Fault events: qubits or couplers becoming unusable

- **No paper forecasts discrete fault events** (a TLS dropout, a `faulty` flag or a
  `gate_error = 1` placeholder) at the calibration cadence. The literature is silent.
- **The `gate_error = 1` placeholder is documented on `ibm_fez`.** "One qubit was
  non-operational and reported a sentinel error value of 1.0, which inflates the mean
  single-qubit gate error by a factor of approximately 25"; the authors switched to medians.
  [Hassan and Kaabouch 2026, arXiv:2602.21253, beyond abstract]. That paper is an ANFIS
  bug-versus-noise classifier on `ibm_fez`, background only, but it is the only fetched
  document-level corroboration of the placeholder.
- **Mechanism and timescales.** TLSs "exhibit slow spectral dynamics that destabilize qubit
  lifetimes on hour timescales", and a radiation impact can make "multiple TLSs ... jump in
  frequency" ("TLS scrambling") [Thorbeck et al. 2023, arXiv:2210.04780]. On Google
  hardware, "performance outliers emerge on timescales ranging from seconds to months, with
  the most catastrophic due to TLS defects" [Klimov et al. 2024, arXiv:2308.02321, beyond
  abstract]. Frequency fluctuations at tens-of-milliseconds resolution separate into
  charge-parity and TLS switching [Agarwal et al. 2025, arXiv:2505.23622].
- **Detection needs spectroscopy we do not have.** Automated TLS detection works from
  time-resolved SWAP spectroscopy [Khalil et al. 2026, arXiv:2608.21983]; the published
  properties document carries no such data.
- **Daily-rate triage exists, forecasting does not.** Das and Ghosh identify "qubits that
  cannot be used" from each day's error rates [arXiv:2505.06165]; that is classification of
  the present, not prediction.
- **Implication.** A fault channel would be a hazard or two-state switching model on the
  archive's own event history (Engine-feasible), but its value is unestablished; the base
  rate of `gate_error = 1` events per gate type must be counted first.

### 2.4 Methods 2023-2026 for short, irregular, many-related series and small tables

**Linear and global models (Engine).**
- Toner and Darlow 2024 (arXiv:2403.14587): popular linear forecasting variants "are
  equivalent and functionally indistinguishable from standard, unconstrained linear
  regression", admit closed-form solutions, and "the simpler closed form solutions are superior
  forecasters across 72% of test settings". If DLinear and NLinear are among the variants
  analysed (the abstract names none), they are redundant with a ridge model on lags here.
- Godahewa et al. 2021, Monash archive (arXiv:2105.06643): "Global forecasting models that are
  trained across sets of time series have shown a huge potential ... compared with the
  traditional univariate forecasting models". Supports pooling across 156 qubits / couplers.
- Hewamalage et al. 2022 (arXiv:2203.10716): evaluation tutorial covering data partitioning,
  error measures and statistical testing under "non-normalities and non-stationarities"
  (Background; for protocol design).

**Neural forecasters (Reference only).** N-HiTS (arXiv:2201.12886) reports "an average accuracy
improvement of almost 20% over the latest Transformer architectures" on long-horizon
benchmarks; long horizons and large datasets, not this regime.

**Tabular and time-series foundation models (Reference only, all framework-bound).**
- TabPFN v2 (doi:10.1038/s41586-024-08328-6; abstract as returned by the Crossref fetch,
  paraphrased by the fetch tool): outperforms prior methods on datasets with up to 10,000
  samples.
- TabPFN-TS (arXiv:2501.02945): forecasting as tabular regression with "lightweight temporal
  featurization"; "11M parameters"; state of the art on covariate-informed forecasting and
  "competitive accuracy on univariate forecasting across the GIFT-Eval and fev-bench
  benchmarks". The most natural external reference, since our inputs are covariate-rich.
- Chronos (arXiv:2403.07815; 20M to 710M parameters; 42 datasets; zero-shot "comparable and
  occasionally superior"), TimesFM (arXiv:2310.10688; zero-shot "comes close to" supervised
  accuracy), Moirai (arXiv:2402.02592; "over 27B observations"), Lag-Llama
  (arXiv:2310.08278; lags as covariates).

**Benchmarks and counter-evidence.**
- GIFT-Eval (arXiv:2410.10393): 23 datasets, "over 144,000 time series", 17 baselines
  including statistical, deep and foundation models.
- fev-bench (arXiv:2509.26468): 100 tasks, 46 with covariates, bootstrapped confidence intervals
  on win rates and skill scores, for "pretrained, statistical, and baseline models".
- Toner et al. 2025 (arXiv:2502.12944): on cloud data foundation models "are outperformed
  consistently by simple linear baselines" and sometimes output "erratic, random-looking
  forecasts".
- Tan Jerome and Simon 2026 (arXiv:2607.04919; abstract as returned, closely paraphrased):
  over 30 datasets, foundation models beat classical methods (including XGBoost and ARIMA) on
  15 regardless of data volume; on the rest classical methods win with as little as 21 to
  2,768 training samples; LoRA fine-tuning sometimes hurt on short series.
- Net reading: no benchmark resembles a 100- to 750-step, irregular, heavy-tailed calibration
  series. Foundation models are a fair external reference, and whether they beat persistence
  here is unknown.

**Conformal methods newer than ACI, DtACI and PID (all Engine-feasible unless noted).**

| Method | What its abstract claims | Fit here |
| --- | --- | --- |
| Online conformal with decaying step sizes (arXiv:2402.01139) | Retrospective coverage for arbitrary sequences, and "when the distribution is stable, the coverage is close to the desired level for every time point" | First upgrade over ACI for a ~100-step series |
| Adaptive conformal inference by betting (arXiv:2412.19318) | Controls long-term miscoverage "without any need of performing cumbersome parameter tuning" | Removes ACI's step size; parameter-free |
| AcMCP, multi-step (arXiv:2410.13115) | h-step errors are "serially correlated up to lag (h-1)"; finite-sample coverage error bound "increases with the forecasting horizon" | Required once `h > 1` epoch |
| SAOCP (arXiv:2302.07869) | Near-optimal strongly adaptive regret "for all interval lengths simultaneously" | Suits regime shifts; more machinery |
| Bellman conformal inference (arXiv:2402.05203) | Long-term coverage "under arbitrary distribution shifts", shorter intervals via a 1-D dynamic program | Feasible but heavier; needs multi-step forecasts |
| SPCI (arXiv:2212.03463) | Re-estimates the conditional quantile of residuals "upon exploiting the temporal dependence" | Needs a quantile regressor on residuals; heavy at ~100 steps |

### 2.5 Physics baseline plus learned residual

- **The only close precedent is not a forecaster.** Klimov et al. 2024 (arXiv:2308.02321,
  doi:10.1038/s41467-024-46623-y): with "a comprehensive model of physical errors" the
  optimizer "suppresses physical error rates by ~3.7x". Beyond abstract: the estimator sums
  physics-based error components (dephasing, relaxation including TLS hotspots, stray coupling,
  pulse distortion) computed from characterization data, weighted by **16 trainable weights**
  for the whole 68-qubit processor, and predicts CZXEB cycle errors "in the wide range
  ~3-40e-3 within two factors of experimental uncertainty". It needs frequency-tunable qubits
  and relaxation spectra, which `ibm_fez`'s published data do not provide, so the structure
  transfers but the inputs do not. (Engine-feasible in structure.)
- **Circuit-level capability models** fit "effective error rates to individual gates" from
  benchmark data (Hothem et al. 2023, arXiv:2305.08796); Background.
- **Calibration-based digital twins** map T1/T2, gate and readout errors into noise channels;
  twins built from the downloadable calibration CSV "often achieved the closest agreement with
  hardware" on two IBM Eagle devices (Bautra et al. 2026, arXiv:2603.14607); Background.
- **Silent:** no paper learns a residual over the coherence limit for gate errors, and none
  forecasts such a residual over time.

---

## 3. Source table

All identifiers fetched 2026-10-05. "Beyond" = read past the abstract.

| Authors | Title | Year | Identifier | Claim used | Category | Beyond |
| --- | --- | --- | --- | --- | --- | --- |
| Kurniawan, Rodríguez-Soriano, Cuomo, Almudever, García Herrero | On the use of calibration data in error-aware compilation techniques for NISQ devices | 2024 | arXiv:2407.21462 | Windowed historical means beat latest calibration for compilation | Background (supports shrinkage) | Yes |
| Baheri, Guan, Chaudhary, Li | Quantum Noise in the Flow of Time | 2022 | doi:10.1109/IOLTS56730.2022.9897404 | KPSS stationarity; MAPE on series labelled "Fits", no split or naive baseline described | Background | Yes |
| Smith, Viszlai, Seifert, Baker, Szefer, Chong | Fast Fingerprinting of Cloud-based NISQ Quantum Computers | 2022 | arXiv:2211.07880 | Frequency stable; CX and readout errors noisy over time | Background | Yes |
| Dasgupta, Humble | Stability of noisy quantum computing devices | 2021 | arXiv:2105.09472 | 22 months of large fluctuations; no forecasting statistics | Background | Yes |
| Dasgupta, Humble | Characterizing the Stability of NISQ Devices | 2020 | arXiv:2008.09612 | Histogram-similarity stability metric | Background | No |
| Dasgupta, Humble | Reliable Devices Yield Stable Quantum Computations | 2023 | arXiv:2307.05381 | Hellinger bound on result stability | Background | No |
| Stehlik et al. | Tunable Coupling Architecture for Fixed-frequency Transmons | 2021 | arXiv:2101.07746 | CZ stable over 19 h; Table I used for derived coherence ratio | Background | Yes |
| Fang et al. | CaliScalpel | 2024 | arXiv:2412.02036 | Drift model assumption, mean 14.08 h, protocol undocumented | Background | Yes |
| Wilson, Singh, Mueller | Just-in-time Quantum Circuit Transpilation Reduces Noise | 2020 | arXiv:2005.12820 | Fresh measurement beats daily calibration | Background | No |
| Hirasaki, Daimon, Itoko, Kanazawa, Saitoh | Detection of temporal fluctuation in superconducting qubits for quantum error mitigation | 2023 | arXiv:2307.04337 | Step changes lasting minutes | Background | No |
| Li, Dasgupta, Song, Yang, Humble, Jiang | Computational Performance Bounds Prediction in Quantum Computing with Unstable Noise (QuBound) | 2025 | arXiv:2507.17043 | LSTM on historical traces, circuit bounds | Reference only | No |
| Das, Ghosh | Optimization of QEC Code under Temporal Variation of Qubit Quality | 2025 | arXiv:2505.06165 | Daily variation drives code distance; unusable-qubit triage | Background | No |
| Tannu, Qureshi | A Case for Variability-Aware Policies for NISQ-Era Quantum Computers | 2018 | arXiv:1805.10224 | 52-day variability on IBM-Q20 | Background | No |
| Murali et al. | Noise-Adaptive Compiler Mappings for NISQ Computers | 2019 | arXiv:1901.11054 | Temporal variation exploitable for mapping | Background | No |
| Wallman, Flammia | Randomized Benchmarking with Confidence | 2014 | arXiv:1404.6025 | RB estimates precise under Markovian noise | Background | No |
| Ghosh, Fowler, Geller | Surface code with decoherence | 2012 | arXiv:1210.5799 | AD+PD channel in T1, T2; Pauli probabilities give F_pro | Engine (physics floor) | Yes |
| Nielsen | A simple formula for the average gate fidelity of a quantum dynamical operation | 2002 | arXiv:quant-ph/0205035 | F_avg from entanglement fidelity | Engine (physics floor) | No |
| Pedersen, Møller, Mølmer | Fidelity of quantum operations | 2007 | arXiv:quant-ph/0701138 | Average fidelity, multi-component systems | Background | No |
| Abad, Fernández-Pendás, Frisk Kockum, Johansson | Universal fidelity reduction of quantum operations from weak dissipation | 2022 | arXiv:2110.15883 | First-order N-qubit coherence limit (eq. 12) | Engine (physics floor) | Yes |
| Li et al. | Error per single-qubit gate below 1e-4 in a superconducting qubit | 2023 | arXiv:2302.08690 | RB error vs decoherence lower bound | Background | No |
| Sheldon et al. | Characterizing errors on qubit operations via iterative RB | 2016 | arXiv:1504.06597 | IBM 1q error limited by drive-activated decoherence | Background | No |
| McKay, Wood, Sheldon, Chow, Gambetta | Efficient Z-Gates for Quantum Computing | 2017 | arXiv:1612.00858 | IBM 1q error dominated by decoherence, not leakage | Background | No |
| Sung et al. | Realization of high-fidelity CZ and ZZ-free iSWAP gates with a tunable coupler | 2021 | arXiv:2011.01261 | CZ close to T1 limit (non-IBM) | Background | No |
| Kandala et al. | Demonstration of a High-Fidelity CNOT for Fixed-Frequency Transmons | 2021 | arXiv:2011.07050 | IBM CNOT 99.77% IRB | Background | No |
| McKay et al. | Benchmarking Quantum Processor Performance at Scale | 2023 | arXiv:2311.05933 | Heron EPLG versus Eagle | Background | No |
| Hassan, Kaabouch | A Physics-Informed Neuro-Fuzzy Framework for Quantum Error Attribution | 2026 | arXiv:2602.21253 | Sentinel 1.0 on ibm_fez inflates mean ~25x | Background | Yes |
| Thorbeck, Eddins, Lauer, McClure, Carroll | TLS Dynamics in a Superconducting Qubit Due to Background Ionizing Radiation | 2023 | arXiv:2210.04780 | Hour-scale TLS dynamics; TLS scrambling | Background | No |
| Klimov et al. | Optimizing quantum gates towards the scale of logical qubits | 2024 | arXiv:2308.02321 | 16-weight physics error model; TLS outliers seconds to months | Engine (structure only) | Yes |
| Agarwal et al. | Fast-tracking and disentangling of qubit noise fluctuations | 2025 | arXiv:2505.23622 | Charge-parity and TLS switching | Background | No |
| Khalil et al. | Automating detection of Two-Level Systems in Superconducting Qubits | 2026 | arXiv:2608.21983 | TLS detection needs spectroscopy | Background | No |
| Hothem, Hines, Nataraj, Blume-Kohout, Proctor | Predictive Models from Quantum Computer Benchmarks | 2023 | arXiv:2305.08796 | Effective per-gate error-rate models | Background | No |
| Bautra, Dimitrijevs, Yakaryilmaz | Evaluating Calibration-Based Digital Twins for IBM Quantum Hardware Simulation | 2026 | arXiv:2603.14607 | CSV-built twins agree best with hardware | Background | No |
| Toner, Darlow | An Analysis of Linear Time Series Forecasting Models | 2024 | arXiv:2403.14587 | Linear variants equal OLS; closed form better in 72% | Engine | No |
| Godahewa, Bergmeir, Webb, Hyndman, Montero-Manso | Monash Time Series Forecasting Archive | 2021 | arXiv:2105.06643 | Global models across series | Engine (global pooling) | No |
| Hewamalage, Ackermann, Bergmeir | Forecast Evaluation for Data Scientists | 2022 | arXiv:2203.10716 | Evaluation pitfalls | Background | No |
| Challu et al. | N-HiTS | 2022 | arXiv:2201.12886 | Long-horizon neural forecaster | Reference only | No |
| Hollmann et al. | Accurate predictions on small data with a tabular foundation model (TabPFN v2) | 2025 | doi:10.1038/s41586-024-08328-6 | Up to 10,000 samples | Reference only | No |
| Hoo, Müller, Salinas, Hutter | From Tables to Time: Extending TabPFN-v2 to Time Series Forecasting | 2025 | arXiv:2501.02945 | Covariate-informed SOTA; 11M parameters | Reference only | No |
| Ansari et al. | Chronos | 2024 | arXiv:2403.07815 | Zero-shot comparable on new datasets | Reference only | No |
| Das, Kong, Sen, Zhou | A decoder-only foundation model for time-series forecasting (TimesFM) | 2023 | arXiv:2310.10688 | Zero-shot close to supervised | Reference only | No |
| Woo et al. | Unified Training of Universal Time Series Forecasting Transformers (Moirai) | 2024 | arXiv:2402.02592 | Universal forecaster | Reference only | No |
| Rasul et al. | Lag-Llama | 2023 | arXiv:2310.08278 | Lags as covariates, probabilistic | Reference only | No |
| Aksu et al. | GIFT-Eval | 2024 | arXiv:2410.10393 | 144,000 series, 17 baselines | Background | No |
| Shchur et al. | fev-bench | 2025 | arXiv:2509.26468 | 100 tasks, bootstrapped skill scores | Background | No |
| Toner, Lee, Joosen, Singh, Asenov | Performance of Zero-Shot Time Series Foundation Models on Cloud Data | 2025 | arXiv:2502.12944 | FMs beaten by simple linear baselines | Background | No |
| Tan Jerome, Simon | When Do Foundation Models Pay Off? | 2026 | arXiv:2607.04919 | FMs win on 15 of 30 datasets; classical wins with little data elsewhere | Background | No |
| Angelopoulos, Barber, Bates | Online conformal prediction with decaying step sizes | 2024 | arXiv:2402.01139 | Near-nominal coverage at every time point when stable | Engine | No |
| Podkopaev, Xu, Lee | Adaptive Conformal Inference by Betting | 2024 | arXiv:2412.19318 | Parameter-free ACI | Engine | No |
| Wang, Hyndman | Online conformal inference for multi-step time series forecasting (AcMCP) | 2024 | arXiv:2410.13115 | h-step error autocorrelation; multi-step coverage | Engine | No |
| Bhatnagar, Wang, Xiong, Bai | Improved Online Conformal Prediction via Strongly Adaptive Online Learning (SAOCP) | 2023 | arXiv:2302.07869 | Interval-wise adaptivity | Engine | No |
| Yang, Candès, Lei | Bellman Conformal Inference | 2024 | arXiv:2402.05203 | Shorter intervals, long-term coverage | Engine (heavier) | No |
| Xu, Xie | Sequential Predictive Conformal Inference (SPCI) | 2023 | arXiv:2212.03463 | Conditional quantile of residuals | Engine (heavy) | No |

---

## 4. Unverified leads (not cited above)

- **Baheri et al. "80% to 94% prediction accuracy for T1, T2, and single qubit gate error".**
  Appears in search snippets about the TAQE dataset (IEEE DataPort, Zenodo record 4898393).
  The fetched IOLTS 2022 paper does not contain this figure (it reports SES 23%, DES 47 to
  80%). Source and meaning of "accuracy" unverified.
- **M5 accuracy competition** (Makridakis, Spiliotis, Assimakopoulos 2022,
  doi:10.1016/j.ijforecast.2021.11.013): the DOI resolved and Crossref confirmed the title,
  but no abstract could be fetched, so no claim (such as gradient-boosted trees on lags
  winning) is attributed to it.
- **IBM tutorial "Real-time benchmarking for qubit selection"**
  (quantum.cloud.ibm.com/docs/en/tutorials/real-time-benchmarking-for-qubit-selection):
  fetched; states that reported properties are "updated once a day, but the system may drift
  faster". Vendor documentation with no DOI or arXiv ID.
- **QuCAD** (Hu, Lin, Guan, Jiang, arXiv:2304.04666): builds a model repository from
  historical IBM calibration data; seen in search snippets only.
- **Oda et al., sparse non-Markovian noise model, PRX Quantum** (doi:10.1103/lx8x-z29x): a
  news article claims "sevenfold" better predictive accuracy without naming the baseline; the
  paper itself was not fetched, and it concerns circuit noise models, not temporal forecasting.
- **ReloQate** (arXiv:2603.00837), **DAQEC-Benchmark** (Zenodo 18045662), **adaptive
  spectroscopy of fast TLS dynamics** (arXiv:2608.02086), **Superconducting-qubit gates robust
  to parameter fluctuations** (arXiv:2511.22580, 11-day gate-error tracking): snippets only.
- **fev-bench's Seasonal Naive normalisation** and **Chronos-2** (arXiv:2510.15821): from the
  HTML snippet only.
- **Qiskit Experiments RB `coherence_limit` utility**: vendor code that would give a
  software-checkable form of the formula; not fetched.
