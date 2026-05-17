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

--- Ensemble Scaling Tests (Real Concretes) ---
N=1 elapsed=0.08s total_shots=1024
  counts: {'00': 237, '10': 287, '11': 227, '01': 273}

N=8 elapsed=0.70s total_shots=8192
  counts: {'01': 2029, '00': 1998, '10': 2083, '11': 2082}

N=16 elapsed=1.33s total_shots=16384
  counts: {'01': 4172, '10': 4096, '00': 3983, '11': 4133}

--- Sanity Check (Single Member, 8192 Shots) ---
Sanity Run elapsed=0.09s total_shots=8192
  counts: {'01': 1996, '10': 2096, '00': 2025, '11': 2075}

### Current Measurement (Real Bootstrap Components)
After wiring the real fuzzy-noise pipeline (May 17, 2026) with:
- `BasicCalibrationVectorizer` extracting 3 features (mean_T1, mean_T2, mean_readout_error)
- Feature-specific MF grids (T1/T2 in 0–100µs range, readout_error in 0–0.1 range)
- `TSKRuleBase.from_grid(..., consequent_init="random", rng=np.random.default_rng(0))`
- Real defuzzifier, squashing, channel projector, fuzzification strategy
- Warmup run (1 shot) before timing loop to amortize cold start

Measured on local 2-qubit QFT with synthetic snapshot (single core, no GPU):

| Ensemble Size | Elapsed (s) | Total Shots | Avg per Member |
| --- | --- | --- | --- |
| N=1 | 0.08 | 1,024 | 0.08s/member |
| N=8 | 0.68 | 8,192 | 0.085s/member |
| N=16 | 1.35 | 16,384 | 0.084s/member |

Observation: per-member time is ~0.08s, dominated by simulator setup and transpilation rather than fuzzy computation. The overhead from constructing the ensemble is O(N), as expected for independent member runs.

## 4. Surprises and Risks
* **Strict Dependency Injection:** The `FuzzyNoiseModelEnsemble.__init__` takes the `calibration` plus six fuzzy components (`feature_extractor`, `rule_base`, `defuzzifier`, `squashing`, `channel_projector`, `fuzzification_strategy`) as its required injected dependencies. In addition it exposes optional parameters `ensemble_size` (defaults to 32) and `rng` (defaults to None). Note: earlier text misstated the positional argument count; the correct surprise for readers is the strict DI surface and the presence of optional sizing/rng parameters rather than an always-positional `n`.
* **Transpilation Requirement:** When passing high-level circuits (like QFT) to the `AerSimulator` equipped with our custom noise models, an explicit `transpile(circuit, backend=sim)` step is mandatory before `sim.run()`, otherwise Aer throws an `unknown instruction` error.
