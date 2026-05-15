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
For the 1-qubit QFT benchmark circuit (shots=1024 per member), the wall-clock execution times are as follows. *(Note: This run is degenerate-by-design per ADR-015, using real concrete components but identical models for sanity-check timing)*:
* **N=1:** 6.84s
* **N=8:** 0.64s
* **N=16:** 1.31s
* **Sanity Check (Single Member, 8192 shots):** 0.08s

*Observation:* The extremely high latency for N=1 (6.84s) is due to the initialization and compilation (transpile) overhead of Qiskit Aer on the first run. Once the backend is initialized, the scaling from N=8 (0.64s) to N=16 (1.31s) shows almost perfectly linear scaling, indicating that Aer does not internally parallelize across different noise model instances and the Python-level iteration dominates the elapsed time.

## 4. Surprises and Risks
* **Strict Dependency Injection:** The most significant surprise was the `FuzzyNoiseModelEnsemble.__init__` signature. It requires 7 injected components—`calibration`, `feature_extractor`, `rule_base`, `defuzzifier`, `squashing`, `channel_projector`, and `fuzzification_strategy`—with an optional `ensemble_size` and `rng` parameters. The pre-meeting architecture document implied a simpler factory method. This strict DI means any downstream benchmarking script must instantiate and pass all fuzzy components, which adds significant boilerplate, and readers should use `ensemble_size` (rather than a required positional `n`) to control N.
* **Transpilation Requirement:** When passing high-level circuits (like QFT) to the `AerSimulator` equipped with our custom noise models, an explicit `transpile(circuit, backend=sim)` step is mandatory before `sim.run()`, otherwise Aer throws an `unknown instruction` error.