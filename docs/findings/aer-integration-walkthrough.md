# Aer Integration Walkthrough and First Ensemble Run Findings

## 1. Aer's Serialization Model & No-Per-Shot-Hook Constraint
[cite_start]After reviewing the Qiskit Aer source code, I can confirm the architectural constraint: Aer does not support per-shot Python callbacks[cite: 9]. 
* [cite_start]The translation happens in `qiskit_aer/backends/aer_simulator.py` during the `run()` method execution[cite: 9].
* [cite_start]The noise model is serialized to a C++ compatible format via `NoiseModel.to_dict()`[cite: 9].
* [cite_start]Once the `assemble_circuits` process completes and the payload is handed over to the C++ controller, Python execution halts until the entire batch of shots is completed[cite: 9]. [cite_start]Therefore, the Factory/Ensemble pattern we are using is indeed the only viable integration path for per-model variance[cite: 11].

## 2. Current Ensemble Architecture & Variance Injection Point
The architecture has evolved significantly from the initial skeleton. The ensemble generation is no longer a simple `FuzzyNoiseModel.ensemble(snapshot, n)` method.
* **Current State:** It is now a dedicated class `FuzzyNoiseModelEnsemble` that relies heavily on strict Dependency Injection.
* [cite_start]**Variance Injection Point:** To inject variance (e.g., IT2 envelope sampling), the changes must be plugged into the injected dependencies of `FuzzyNoiseModelEnsemble` (such as `rule_base`, `fuzzification_strategy`, or the `feature_extractor`)[cite: 33, 34]. 
* **Expected Hook Signature:** The hook will likely reside in the injected fuzzy modules, expecting a method signature similar to `def extract(self, snapshot: CalibrationSnapshot) -> np.ndarray:` where the variance sampling math will occur before yielding the concrete `FuzzyNoiseModel`.

## 3. Latency Observations (Wall-Clock Scaling)
[cite_start]For the 3-qubit QFT benchmark circuit (shots=1024 per member), the wall-clock execution times are as follows[cite: 63, 71]:
* **N=1:** 5.92s
* **N=8:** 0.28s
* **N=16:** 0.52s
* **Sanity Check (Single Member, 8192 shots):** 0.03s

*Observation:* The extremely high latency for N=1 (5.92s) is due to the initialization and compilation (transpile) overhead of Qiskit Aer on the first run. [cite_start]Once the backend is initialized, the scaling from N=8 (0.28s) to N=16 (0.52s) shows almost perfectly linear scaling, indicating that Aer does not internally parallelize across different noise model instances and the Python-level iteration dominates the elapsed time[cite: 134].

## 4. Surprises and Risks
* **Strict Dependency Injection:** The most significant surprise was the `FuzzyNoiseModelEnsemble.__init__` signature. It requires 7 positional arguments (snapshot, n, and 5 fuzzy logic components). [cite_start]The pre-meeting architecture document implied a simpler factory method[cite: 136, 150]. This strict DI means any downstream benchmarking script must instantiate and pass all fuzzy components, which adds significant boilerplate. 
* **Transpilation Requirement:** When passing high-level circuits (like QFT) to the `AerSimulator` equipped with our custom noise models, an explicit `transpile(circuit, backend=sim)` step is mandatory before `sim.run()`, otherwise Aer throws an `unknown instruction` error.