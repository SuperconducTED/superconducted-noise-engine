# 2026-05-16
# Aer Ensemble Walkthrough

## Problem
We need to validate the end-to-end integration of the `FuzzyNoiseModelEnsemble` pipeline with Qiskit's `AerSimulator` to measure latency, architectural overhead, and verify the Dependency Injection (DI) surface. Because Aer does not support per-shot Python hooks natively, we must rely on generating an ensemble of concrete noise models and aggregating their results.

## What Changed
* Added `scripts/first_ensemble_run.py` to perform an N-member ensemble simulation and aggregate counts using basic wall-clock timing.
* Added a findings document (`docs/findings/aer-integration-walkthrough.md`) to capture Aer constraints and scaling observations.

## Approach
The script instantiates a `FuzzyNoiseModelEnsemble` using real concrete components (`BasicCalibrationVectorizer`, `TSKRuleBase`, `GaussianMF`, `KrausChannelProjector`, etc.) rather than mocks. It supplies a fabricated but strictly typed `CalibrationSnapshot` containing a single virtual qubit to satisfy hardware-extraction layers. The ensemble is generated, and each member prepares a cloned circuit before execution on a shared `AerSimulator` instance.

## Math
The ensemble execution aggregates counts across $N$ models linearly. The total shots fired is simply $N \times S_{member}$, where $S_{member} = 1024$.

## Decisions
* **Real Concretes over Mocks:** We enforce passing real fuzzy components and a valid `CalibrationSnapshot` to ensure the script accurately exercises the codebase's type strictness and extraction logic.
* **Shared Simulator & Circuit Cloning:** We reuse a single `AerSimulator()` instance to avoid backend initialization overhead per member, but we apply `nm.prepare(circuit.copy())` to prevent circuit state contamination between consecutive fuzzy transformations.

## Verification
The script acts as an empirical integration test. Run it directly from the project root:
```bash
python scripts/first_ensemble_run.py
```

Expected behavior: The script runs without TypeError or AttributeError for $N \in \{1, 8, 16\}$, outputting wall-clock latencies that demonstrate the Python-level loop overhead.

## Related
* **ADR-002:** Explains why this Factory/Ensemble generation pattern is the only viable approach (due to Qiskit Aer's lack of per-shot Python callback support).
* **ADR-015:** Outlines deferred per-member sampling. This walkthrough is degenerate-by-design (identical members) to baseline the latency without complex sampling variance.