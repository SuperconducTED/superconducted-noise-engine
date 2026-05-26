# ❯ Questions for Dr. Akba · Cycle 1 Review

## ❯ Preface

Since our April presentation, the team has built the SuperconducTED noise engine from scratch: nine swappable interface contracts, a full TSK fuzzy inference pipeline, an hourly calibration data poller accumulating IBM Quantum snapshots, a benchmark harness with four validated metrics, a typed calibration loader that handles missing qubit data, and a complete Aer integration walkthrough that confirmed the simulator's constraints and characterized latency scaling. We audited all sixteen original architecture decisions against the running code, found two drifts, surfaced three ambiguities, and drafted six new decision records.

We are now at a transition point. The architecture is validated but the membership functions are untrained (waiting on calibration data accumulation), the ensemble produces identical members (no per-member variance yet), and several interconnected design decisions need resolution before empirical results can feed into a paper. This document asks concrete questions where your input changes the engineering path. Each question includes what we built, what we learned, and what the options are.

## ❯ Quick Status

The pipeline runs end-to-end from IBM Quantum calibration data through fuzzy inference to Aer noise model construction and benchmarking. All core components are implemented with bootstrap defaults. The system is in a research preview state where the architecture is validated but the membership functions are not yet trained and ensemble members are identical.

| Capability | Status |
|------------|--------|
| Calibration data polling (ibm_fez, hourly) | Running since 2026-05-13 |
| Fuzzy noise model construction | Working end-to-end |
| Ensemble simulation through Aer | Working · latency characterized |
| Benchmark metrics (Hellinger, KL, fidelity, R²) | Validated with property tests |
| Missing calibration data handling | Implemented (skip strategy) |
| Per-member ensemble variance | Not yet implemented |
| Trained membership functions | Waiting on dataset (~2026-07-10) |
| Membership function shape comparison | Protocol defined · execution pending |

## ❯ Questions

### ❯ 1. Is the ensemble-of-noise-models approach architecturally sufficient as the permanent variance mechanism, or should we plan an escape hatch?

We confirmed through Qiskit Aer source inspection that the simulator serializes the entire noise model to a C++ dictionary once at submission time and runs all shots in C++ with no Python callback. There is no per-shot hook, no re-entry point, and no way to regenerate noise parameters between shots. The only way to express fuzzy or epistemic uncertainty across simulation runs is to construct N distinct noise model instances (the "ensemble"), each with slightly different noise channels, and run Aer once per member. Latency scales linearly at roughly 0.12 seconds per additional member after warmup. We built the full dependency-injection factory around this constraint.

**Decision space** · Option A: Accept the ensemble as the permanent, sole variance mechanism and optimize around it (parallelization, caching). Option B: Maintain a research branch exploring a custom simulator backend that could reintroduce per-shot callbacks. Option C: Treat the ensemble as permanent for the paper but preserve the abstract interface so a future custom backend could slot in. We lean toward Option A for the paper, noting that Option C's interface is already in place via the abstract base class design.

**What changes** · If per-shot variance is scientifically necessary for the contribution to be credible, we would need to scope a custom Aer backend or an alternative simulator · a major scope expansion. If ensemble-level variance is sufficient, we finalize the architecture and focus on making the members meaningfully different.

### ❯ 2. For making ensemble members non-identical, which variance injection mechanism should we prioritize?

At bootstrap, all ensemble members are identical because no trained membership functions exist and no perturbation logic is wired. We identified three plug-in points where per-member variance can be injected without restructuring the factory. First, input-vector perturbation: jiggle the extracted calibration features (mean T1, mean T2, mean readout error) before feeding them to the rule base, simulating measurement uncertainty in the calibration data itself. Second, premise-MF perturbation: draw each member's membership function parameters from the training-time parameter variance once the trainer delivers fitted parameters. Third, Interval Type-2 footprint sampling: sample a crisp Type-1 slice from within the Type-2 uncertainty envelope for each member.

**Decision space** · Option 1 (input-vector perturbation) is implementable immediately with no dependency on the trainer. Option 2 (premise-MF perturbation) requires the trainer to deliver parameter distributions and is the most principled from a fuzzy-systems standpoint. Option 3 (IT2 footprint sampling) subsumes Option 2 if we commit to Interval Type-2 but is blocked on the type-system resolution. We lean toward Option 1 as an interim mechanism with Option 2 or 3 replacing it after training.

**What changes** · If Option 1 is prioritized, we implement calibration-feature jittering immediately and begin generating non-degenerate ensemble results for the paper draft. If Option 3 is prioritized, we must resolve the Type-1 vs Type-2 question first, delaying non-degenerate runs. If a combination is desired, we need to define how multiple perturbation sources compose without double-counting uncertainty.

### ❯ 3. For the membership function shape comparison, is Hellinger distance as the primary metric and fidelity as secondary the right ordering, and are the four benchmark circuits the right test suite?

We have four Type-1 shapes implemented (Gaussian, triangular, trapezoidal, tanh) plus two additional tanh variants in progress (tanh-sigmoid, tanh-bell) and an Interval Gaussian for the Type-2 path. We drafted an ablation protocol: fix a single calibration snapshot, run each shape through the same pipeline, collect four metrics (Hellinger distance, KL divergence, state fidelity, R²) across four benchmark circuits (random Clifford, GHZ, QFT, and an efficient-SU2 ansatz), with ensemble size 8, 4096 shots, and a fixed random seed. The protocol defines the "winner" as the shape that minimizes Hellinger (primary) and maximizes fidelity (secondary).

**Decision space** · Hellinger is a proper metric (symmetric, bounded, satisfies the triangle inequality) and is common in quantum information. Fidelity is the standard in quantum computing papers. KL divergence is asymmetric and unbounded, making it harder to use for ranking. R² is included for regression-style fit quality. Our current ordering is Hellinger primary, fidelity secondary, with KL and R² as supplementary. The circuit suite covers structured entanglement (GHZ), algorithmic depth (QFT), random structure (Clifford), and variational workloads (ansatz). Whether these four are sufficient or whether a circuit with specific error sensitivity (e.g., surface code syndrome extraction) would be more informative is an open question.

**What changes** · If the metric ordering changes (e.g., fidelity primary because reviewers expect it), we update the ablation protocol and all downstream comparison tables. If additional circuits are needed (e.g., QAOA or error-correction primitives), we add them before running the ablation.

### ❯ 4. The benchmark harness and the ensemble smoke script disagree on how to aggregate shot counts across ensemble members. Which is correct for the paper?

We found an inconsistency across three locations. The canonical benchmark harness sums shot counts across all ensemble members and records total shots as shots-per-member times the number of members. Under our current normalized metrics (Hellinger, KL, fidelity, R²), which all divide by total counts, this sum-and-scale approach is probability-equivalent to mean aggregation. However, a separate smoke-test script truly mean-aggregates by dividing each bin count by the number of members and rounding, which can cause the total to differ from the shot count by up to one per bin. The architecture documentation and the harness docstring both describe the behavior as "mean aggregation." The three descriptions are not wrong under normalized metrics today, but they would diverge if we ever report raw counts, add unnormalized metrics, or if a reviewer inspects the aggregation contract closely.

**Decision space** · Option A: Standardize on sum-with-scaled-shots (current harness behavior) and update all documentation to say "sum." Option B: Standardize on true per-bin mean (current smoke script behavior) and accept the rounding artifact. Option C: Report both · the mean as the point estimate and a confidence interval derived from per-member distributions. We lean toward Option A for simplicity, with Option C as the eventual target once the ensemble is non-degenerate.

**What changes** · If Option A is confirmed, we update the docstrings and architecture documentation to say "sum with total shots = N × shots_per_member" and align the smoke script. If Option C is desired, we need to design the per-member distribution reporting before the ablation runs.

### ❯ 5. For qubits with missing calibration data, should we stay with the skip strategy for the paper or invest in a fuzzy maximum-entropy treatment?

Real IBM calibration responses occasionally omit T1 and T2 entries for individual qubits when the coherence measurement fails during the calibration window. We observed this on qubit 72 of ibm_fez, where T1 and T2 are absent but readout calibration is intact (about 0.64% missingness rate). We implemented a skip strategy: the typed loader marks absent fields, and the mean aggregators exclude those qubits. This is unbiased relative to imputation (which would pull the mean toward the population) but loses statistical power proportional to the missingness rate. The alternative is a fuzzy maximum-entropy treatment, where the missing field is represented as a wide, maximum-entropy membership function interval that carries the uncertainty forward through the fuzzification layer · the theoretically correct approach for a fuzzy system but requiring the Type-2 infrastructure to be wired end-to-end.

**Decision space** · Option A: Keep the skip strategy for the paper. The missingness rate is low (under 1%) and documenting the rate transparently is sufficient for a conference submission. Option B: Implement the fuzzy maximum-entropy treatment as a contribution point, arguing that fuzzy handling of missing calibration data is a novel aspect of the system. Option C: Implement both and compare their effect on output distributions as part of the ablation. We lean toward Option A for schedule reasons, with Option B as a follow-up contribution.

**What changes** · If Option B is desired for the paper, the fuzzy maximum-entropy treatment becomes a priority, which means resolving the Type-1 vs Type-2 question and landing the fuzzification layer before the ablation. If Option A is acceptable, we proceed with skip and document the missingness rates transparently.

### ❯ 6. Given the dataset accumulation curve, what is the realistic paper submission target?

The ANFIS trainer requires a sufficient corpus of time-series calibration snapshots to learn meaningful membership function parameters. We are polling ibm_fez hourly and have accumulated 127 snapshots since 2026-05-13. Sustained cadence is ~11.1 snapshots per day · approximately 46% of the theoretical hourly maximum, because GitHub Actions scheduler drops are frequent (cron ticks are not guaranteed). At sustained cadence, the 630-snapshot floor is projected for ~2026-07-10. After reaching the floor, we still need to implement the trainer, run the MF ablation, generate paper-quality results, and write the paper.

**Decision space** · Option A: Target IEEE QCE 2026 if the timeline permits · requires trainer implementation to begin in parallel with accumulation, ablation running immediately after the floor is reached, and paper writing beginning by early July. Option B: Target a later venue (e.g., a fuzzy systems journal or quantum computing workshop) to allow time for the Type-2 comparison and a second engineering cycle. Option C: Submit a shorter workshop paper or poster with preliminary results (ensemble architecture and MF shape comparison) and follow up with a full paper later. We need your guidance on venue selection and timeline feasibility.

**What changes** · If QCE is the target, we need a hard schedule: trainer implementation starts now (even on a smaller snapshot set for debugging), ablation protocol finalized before ~2026-07-10, paper writing begins late July. If a later venue is chosen, we can afford a second engineering cycle. If a workshop paper, we define which results are sufficient for a credible short submission.

### ❯ 7. Should we resolve the Type-1 vs Interval Type-2 question before or after the trainer is built?

The bootstrap supports both Type-1 and Interval Type-2 inference paths. Type-1 is simpler: standard membership functions, weighted-average defuzzification, straightforward ANFIS training. Interval Type-2 carries an explicit footprint of uncertainty · each membership function has upper and lower bounds, and the system produces an interval-valued output reduced via the Nie-Tan closed-form method. IT2 is theoretically stronger for representing epistemic uncertainty in calibration drift and directly provides the uncertainty envelope that ensemble members could sample from. However, the IT2 trainer is more complex (it must learn both upper and lower bounds), and the comparison between the two is itself a research contribution.

**Decision space** · Option A: Build the trainer for Type-1 first (simpler, well-understood ANFIS recipe), get results, then extend to Type-2 as a comparison. Option B: Build the trainer for Type-2 directly, since the uncertainty envelope is the core scientific claim. Option C: Build a trainer that supports both (parameterize upper=lower for Type-1 as a special case of Type-2) and compare them in the same ablation. We lean toward Option A for schedule safety, with the IT2 extension as a second contribution.

**What changes** · If Option B is chosen, the trainer architecture changes significantly: the parameter space doubles, the Nie-Tan defuzzifier must be in the training loop, and training data requirements may increase. If Option A, we ship results sooner but risk the reviewer question "why not IT2?" If Option C, the trainer is more complex upfront but the comparison is cleaner. This decision also directly affects Question 2 (which variance injection mechanism to use) since footprint sampling is only available under Type-2.

### ❯ 8. Should we expand beyond a single backend for calibration data collection before the paper?

We currently poll only ibm_fez (a 156-qubit Eagle r3 processor). A single-backend dataset means our trained model and all experimental results are specific to one processor's noise characteristics and qubit topology. This is defensible for a first paper · it controls for hardware variability · but a reviewer could ask whether the approach generalizes.

**Decision space** · Option A: Single backend for the paper · argue controlled-variable design and leave multi-backend as future work. Option B: Add a second backend now · the poller infrastructure supports a matrix strategy. Option C: Poll a second backend but use it only for a brief generalizability section ("we verified the trained model transfers to backend X with Y% fidelity degradation") rather than training on it. We lean toward Option A for simplicity.

**What changes** · If Option B is chosen, we modify the cron workflow to poll two backends. Neither will reach 630 snapshots as quickly in isolation. If Option C, we need to define what "transfer verification" means concretely (same membership functions applied to a different backend, or re-fitted consequents with frozen premises).

### ❯ 9. What level of real-hardware validation does the paper need?

Our current benchmark harness compares the fuzzy noise engine's output distributions against an Aer simulation with a known noise model · a simulator-vs-simulator comparison. The stronger validation would be to compare against real IBM hardware execution results: run the same circuits on the actual ibm_fez backend and compare the fuzzy engine's output against the real device's output distributions. The property tests we have validate the metrics themselves, not the end-to-end fidelity claim.

**Decision space** · Option A: Simulator-vs-simulator is sufficient for the first paper · frame the contribution as "noise model inference architecture" rather than "hardware prediction." Option B: Real-hardware validation is essential for credibility · allocate credits and queue time for at least the four benchmark circuits on ibm_fez. Option C: Use publicly available IBM hardware result datasets as a proxy. We need your assessment of what reviewers will expect.

**What changes** · If real-hardware runs are required, we need to budget IBM credits, handle queue latency, and build a real-hardware comparison pipeline. The benchmark harness can plug in real counts as a reference distribution, but the data collection and statistical analysis (accounting for hardware shot noise, drift between calibration time and execution time) are new work. If simulator-vs-simulator is sufficient, we can run the full ablation without hardware access constraints.

### ❯ 10. How should we divide the Cycle 2 work across the team?

Cycle 1 was primarily driven by one engineer with one additional contributor on the Aer integration. The upcoming cycle has three parallel workstreams: (a) the ANFIS trainer implementation (hybrid recursive least squares plus stochastic gradient descent, backpropagation through the fuzzification layer), which is the most mathematically intensive component; (b) the MF ablation experiments, which require systematic benchmark harness runs and publication-quality result tables; and (c) the paper itself (introduction, related work, methodology, experiments, discussion). The trainer cannot begin producing results until ~2026-07-10 (snapshot floor), so the assigned team member should be implementing and debugging on smaller datasets before then.

**Decision space** · This is an open question for your guidance, based on your assessment of each team member's strengths and the academic credit structure. The key constraint is the trainer schedule: if assigned to someone who needs mathematical ramp-up time, the timeline extends.

**What changes** · The assignment directly determines the project schedule and the parallelism achievable in Cycle 2. Paper writing (related work, methodology sections) can begin in parallel regardless of who is assigned to the trainer and ablation.

## ❯ Closing

Thank you for reviewing these questions. The team's next concrete milestone is the 630-snapshot calibration data floor, projected for ~2026-07-10, at which point the TSK trainer implementation can begin producing trained membership functions. Your input on the questions above · especially the variance injection mechanism, the Type-1 vs Type-2 resolution order, and the paper submission target · will determine the engineering sequence for the next cycle. We will update you when the snapshot floor is reached and the trainer work begins.
