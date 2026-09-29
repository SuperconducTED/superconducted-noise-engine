# PR #96 verification - Burak's desktop - 2026-09-18

**Implementation commit measured**: `8eaf17f9325620339d99631b306fb5417ea63578`
**Branch**: `feature/issue-73-physical-gate-noise-filter`
**Verdict**: VERIFIED at the PR head for the checks below.

## Scope

PR #96 closes Issue #73 by making fuzzy noise eligibility an injected
physical-gate policy. The default policy derives eligible single-qubit
`(gate_name, physical_qubits)` pairs from positive `gate_length` records in
archived calibration `properties.gates`. Virtual zero-duration `rz`,
administrative instructions, and absent gate records receive no channel.

The PR also makes an empty installation audible: `FuzzyNoiseModel.prepare()`
emits a caller-attributed warning when a logical circuit does not intersect the
calibrated physical basis, while preserving a valid noise-free result.

## Results

| Check | Observed |
| --- | --- |
| Test suite | `478 passed` |
| `ruff check .` | passed |
| `ruff format --check .` | passed; 61 files formatted |
| `python scripts/check_ids.py` | passed |
| `mypy --strict src/superconducted` | passed; 25 source files |
| `git diff --check` | passed |

## Coverage Confirmed

- A real archived gate-bearing fixture supplies an eligible `("sx", (0,))`
  pair and excludes virtual `("rz", (0,))`.
- A physical-basis circuit installs noise only for positive-duration calibrated
  instructions; `delay` and one-qubit `SaveDensityMatrix` remain noise-free.
- Eligibility is deterministic, qubit-aware, resolved once during model
  construction, and injectable through `GateEligibilityPolicy`.
- A test-only reproduction remains runnable on `main`: the eligibility-policy
  imports are local to the tests that require them, so the pre-policy branch
  collects the reproduction and fails its erroneous-attachment assertion.
- The logical/physical basis mismatch produces a warning rather than a silent
  empty `NoiseModel`; a correctly compiled physical-basis circuit does not
  warn.

## Merge Context

At verification time, `origin/main` was `125b7962`, while the PR head was nine
commits ahead and 38 commits behind that base. A three-way merge was checked
and produced no conflict markers. This record certifies the independently tested
PR head; it does not replace a fresh merge-commit verification if the base moves
before merge.

## Remaining Review Preconditions

This technical record is not a GitHub approval. Per `docs/team.md`, the new
ABC and ADR-ledger amendment still require Dr. Akba's out-of-band
sign-off to be recorded on PR #96, plus an approving contributor who is not an
author on this branch. Phase-3 measurement runs must wait for PR #79 (or its
FR-3 harness change), which compiles benchmark circuits to the calibrated
physical basis before calling `prepare()`.

## Reproduction

```bash
python -m pytest tests/ -q
ruff check .
ruff format --check .
python scripts/check_ids.py
mypy --strict src/superconducted
git diff --check
```
