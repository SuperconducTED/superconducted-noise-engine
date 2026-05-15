# Aer Integration Walkthrough and First Ensemble Run Findings

## 1. Aer's Serialization Model & No-Per-Shot-Hook Constraint
After reviewing the Qiskit Aer source code, I can confirm the architectural constraint: Aer does not support per-shot Python callbacks. 
* The translation happens in `qiskit_aer/backends/aer_simulator.py` during the `run()` method execution.
* The noise model is serialized to a C++ compatible format via `NoiseModel.to_dict()`.
* Once the `assemble_circuits` process completes and the payload is handed over to the C++ controller, Python execution halts until the entire batch of shots is completed. Therefore, the Factory/Ensemble pattern we are using is indeed the only viable integration path for per-model variance.

## 2. Current Ensemble Architecture & Variance Injection Point
The architecture has evolved significantly from the initial skeleton. The ensemble generation is no longer a simple `FuzzyNoiseModel.ensemble(snapshot, n)` method.
* **Current State:** It is now a dedicated class `FuzzyNoiseModelEnsemble` that relies heavily on strict Dependency Injection.
* **Variance Injection Point:** To inject variance (e.g., IT2 envelope sampling), the changes must be plugged into the injected dependencies of `FuzzyNoiseModelEnsemble` (such as `rule_base`, `fuzzification_strategy`, or the `feature_extractor`). 
* **Expected Hook Signature:** The hook will likely reside in the injected fuzzy modules, expecting a method signature similar to `def extract(self, snapshot: CalibrationSnapshot) -> np.ndarray:` where the variance sampling math will occur before yielding the concrete `FuzzyNoiseModel`.

## 3. Latency Observations (Wall-Clock Scaling)
The latency table that was previously published in this section was produced by a degenerate run that exercised empty `NoiseModel()` instances rather than the full fuzzy-noise pipeline. That happened because the harness substituted mocked/stubbed components and a pair of broad except/fallbacks allowed execution to continue with empty models. Those measured numbers are therefore invalid for drawing architectural conclusions about the ensemble.

Action: re-run the scaling measurements with the real bootstrap components wired (see the verification steps in the implementation record). Only measurements obtained after wiring the real `BasicCalibrationVectorizer`, `TSKRuleBase.from_grid(...)`, `WeightedAverageDefuzzifier`, `ProbabilityClip`, `KrausChannelProjector`, and `PostGateFuzzification` should be used to inform latency claims.

## 4. Surprises and Risks
* **Strict Dependency Injection:** The `FuzzyNoiseModelEnsemble.__init__` takes the `calibration` plus six fuzzy components (`feature_extractor`, `rule_base`, `defuzzifier`, `squashing`, `channel_projector`, `fuzzification_strategy`) as its required injected dependencies. In addition it exposes optional parameters `ensemble_size` (defaults to 32) and `rng` (defaults to None). Note: earlier text misstated the positional argument count; the correct surprise for readers is the strict DI surface and the presence of optional sizing/rng parameters rather than an always-positional `n`.
* **Transpilation Requirement:** When passing high-level circuits (like QFT) to the `AerSimulator` equipped with our custom noise models, an explicit `transpile(circuit, backend=sim)` step is mandatory before `sim.run()`, otherwise Aer throws an `unknown instruction` error.
