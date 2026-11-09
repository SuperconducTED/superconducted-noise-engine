# PR #141 Linux verification, 2026-11-09

## Scope

Verified PR head `6f0da61fea96d2450ef90e95515965d3f348af2b`, based on `5c98f264dee8292e4b07de4e9074e833c487d9cb`. The clone came from GitHub with `--single-branch`; only the PR branch and the pinned `main` base were present during the clean-clone suite. The `calibration-data` ref was absent. The working tree was clean before this report was added.

Environment: WSL2, Linux kernel `6.18.54.1-microsoft-standard-WSL2`, x86_64, AMD Ryzen 5 5500 (6 cores / 12 threads), Git `2.43.0`, Python `3.12.3`, NumPy `2.4.4`, Qiskit `2.4.1`, Qiskit Aer `0.17.2`, pytest `9.0.3`. `safe.bareRepository` was unset.

## Results

- Static gates: `ruff check`, `ruff format --check`, `mypy --strict`, and `scripts/check_ids.py` all passed.
- Minimal reproduction: passed. Alone and with the density-matrix circuit first, `P(0) = 0.104` and the probability sum is `1`; after a statevector circuit, `P(0) = 0.197` and the sum is `2`. Circuit order reversed restores the result. Output matches the committed reference.
- Trigger sweep: `72/72` rows met, `0` missed. Output matches the committed reference exactly after line-ending normalization.
- Spy positive control: `4/4` passed; the spy observed all three multi-circuit executions through `AerSimulator.run`, `BackendSamplerV2`, and Aer `SamplerV2`.
- Full suite on the GitHub-origin single-branch clone: `1,052 passed, 1 skipped`; the sole skip is the archive survey because `calibration-data` was not fetched. The spy saw `1,131` Aer executions across `45` tests; all had exactly one circuit and none were multi-circuit.
- Static audit on `main` at the pinned base and PR `HEAD`: `108` distinct blobs, `0` unreadable, `0` unparsed. The main call-site section matches the committed audit.
- PR #140 bridge: the batching probe reproduces the same `000`/`111` pattern and matches its committed output. On all six Arm B layouts, the ratio after Arm A is `1024 = 2^10`; before Arm A it is `1`. The public `FakeFez` route also reproduces the symptom. Across Windows and Linux, only the last few floating-point digits of the absolute probability sums differ (about `1e-12`); the ratios are identical.
- Source comparison: all nine named function bodies match between Aer `0.17.2` and `0.18.2`. On upstream `main`, seven match; the only differences are the exception-index fixes in `enable_superop_method` and `enable_kraus_method`.

## Limitations

This verifies the reported behavior and its exposure audit; it does not prove the internal cause by rebuilding Aer with the suspected initialization changed. No QPU was used. The existing code-quality note about the unused local in the verbatim copied probe is non-functional and was left untouched to preserve the recorded blob.

Raw command outputs are in `out/`. No files under `src/`, `scripts/`, or `tests/` changed.