# 2026-09-22: issue-74-smoke-transpilation

## Problem / Motivation

Issue #74 found that `scripts/first_ensemble_run.py` called
`FuzzyNoiseModel.prepare()` before transpiling the circuit against
`AerSimulator`. `prepare()` attaches errors to the instruction names it receives,
but a later Aer-default transpilation can replace those instructions. In
particular, a strong error installed only on `sx` did not change the smoke
result, so the script could report a successful run while exercising no fuzzy
noise. ADR-021's 2026-09-18 amendment requires the opposite order: compile once
to the calibrated device basis, prepare the compiled circuit, then run it
without another transpilation.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/first_ensemble_run.py` | Derives a unitary basis from calibration gate records, rejects circuits wider than their calibration, compiles before preparation with fixed controls, and uses that ordering in ensemble, warm-up, and sanity paths. |
| `tests/test_first_ensemble_run.py` | Adds the `sx`-only regression reproduction and pins one transpilation per ensemble call, explicit controls, copy isolation, non-unitary basis exclusion, synthetic per-qubit coverage, and the calibration-width guard. |

## Implementation approach

`_calibration_basis_gates()` reads the snapshot's `properties.gates` entries,
deduplicates gate names, and excludes `measure`, `measure_2`, and `reset` because
they are not unitary transpiler basis operations. It deliberately does not use
the positive-duration eligibility predicate: virtual `rz` remains a valid
transpilation target even though ADR-028 correctly prevents it from receiving a
thermal-noise error.

`run_ensemble()` receives this explicit basis, calls `transpile()` once before
the member loop with `optimization_level=1` and `seed_transpiler=0`, and passes a
copy of that one compiled circuit to each `prepare()` call. The circuit returned
by `prepare()` goes directly to `AerSimulator.run()`. The warm-up and
single-member sanity paths use the same compile-then-prepare order. No coupling
map is supplied, retaining the project convention that circuit qubit $i$ maps to
physical qubit $i$.

The smoke CLI validates that the requested circuit width does not exceed the
snapshot's `properties.qubits` length before compilation. The synthetic snapshot
supplies every single-qubit basis gate for both of its calibrated qubits, so its
default two-qubit QFT cannot silently apply fuzzy noise to only one qubit.

The regression test compares a fixed-seed, noiseless QFT run against one with a
maximal amplitude-damping error installed only on `sx`. It failed before this
change because Aer-default transpilation left no executed `sx` for the error to
match; it passes once the source circuit is compiled to the explicit physical
basis before preparation.

## Mathematical / Statistical details

N/A — purely structural. Channel parameters and aggregation semantics are
unchanged.

## Design decisions

The basis is derived from all unitary gate names in calibration, rather than
from the smaller set of positive-duration noise-eligible gates. Using the latter
would incorrectly omit virtual `rz` from the compiler's target basis. Aer
defaults are intentionally not used because they are not the calibrated device
basis and can leave an `sx` error with no matching instruction.

This change is confined to the smoke script. `benchmarks/harness.py` remains
Issue #58's scope, while `channels/kraus.py`, `fuzzy/tsk.py`, `types.py`, and
`interfaces.py` remain untouched.

An explicit `initial_layout` was not added: the documented convention for this
path is identity mapping without a coupling map. Instead, the width guard makes
that assumption valid for the smoke script's positional-qubit matching.

## Verification

- `.venv/bin/python -m pytest tests/test_first_ensemble_run.py -q`
- `.venv/bin/python -m ruff check scripts/first_ensemble_run.py tests/test_first_ensemble_run.py`
- `.venv/bin/python -m ruff format --check scripts/first_ensemble_run.py tests/test_first_ensemble_run.py`
- `.venv/bin/python scripts/first_ensemble_run.py --qubits 2`
- `.venv/bin/python scripts/first_ensemble_run.py --qubits 3` (fails before simulation)

The smoke command completed its warm-up/scaling paths for ensemble sizes 1, 8,
and 16, followed by the 8192-shot sanity run.

## Related docs

- ADR-021 amendment and ADR-028 in `docs/decisions.md`
- `docs/implementations/2026-09-12-issue-73-physical-gate-noise-filter.md`
- Issues #58, #73, and #74