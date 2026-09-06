# Issue #57 verification · Burak's desktop · 2026-09-05

**Implementation commit measured**: `fd9bb0d3116d3aa4a2f713b82e331b254b2e4520`
**Branch**: `feature/issue-57-training-target`
**Verdict**: VERIFIED for the implementation and numerical measurements below.

## Machine

| Field | Value |
| --- | --- |
| Host | `DESKTOP-2CST637` |
| OS | Linux 6.18.33.2-microsoft-standard-WSL2 |
| Python | 3.12.3 |
| pytest | 9.0.3 |
| Qiskit | 2.4.1 |
| Qiskit Aer | 0.17.2 |
| Calibration archive ref | `origin/calibration-data` at `1accf05c0c8ae8174c43d22c70fb46f6147ac9f9` |

## Results

| Check | Observed |
| --- | --- |
| Full test suite | `352 passed` |
| `ruff check` | `All checks passed!` |
| `ruff format --check` | all candidate Python files already formatted |
| `mypy --no-incremental src/superconducted/training src/superconducted/interfaces.py` | no issues found |
| Candidate test count | 352 collected; `+72` from 280 at `origin/main` `7d39a2b` |
| Aer conformance | Maximum SuperOp matrix-entry difference $9.992007221626409 \times 10^{-16}$ across 4 T1/T2 cases at 24 ns and 60 ns, below $10^{-12}$ |
| 3x3x3 Gaussian parameter accounting | 234 total: 216 consequent plus 18 premise |
| Gate-bearing fixture | SHA-256 `02d27ff1bf6af8bb06e0bce886454160926cb3adc1466e536245e03431487082`; 156 `sx` records at 24 ns; 155 usable targets; q72 `t1_missing` |
| Second gate-duration measurement | archive snapshot `20260513T143529000000Z`: 156 `sx` records, all 24 ns |
| Locked modules | no diff from `origin/main` for `src/superconducted/fuzzy/tsk.py` or `src/superconducted/channels/kraus.py` |

## Reproduction

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src/superconducted/training src/superconducted/interfaces.py tests/test_targets.py tests/test_aer_pin.py tests/test_training_types.py tests/test_training_parameters.py tests/test_anfis.py tests/test_interfaces.py tests/test_train_anfis_script.py
.venv/bin/ruff format --check src/superconducted/training tests/test_targets.py tests/test_aer_pin.py tests/test_training_types.py tests/test_training_parameters.py tests/test_anfis.py tests/test_interfaces.py tests/test_train_anfis_script.py
.venv/bin/mypy --no-incremental src/superconducted/training src/superconducted/interfaces.py
git diff origin/main -- src/superconducted/fuzzy/tsk.py src/superconducted/channels/kraus.py
```

NC-031 through NC-036 contain the exact target, fixture, parameter-count, and
device-error calculations and their sources.

## Outstanding human approvals

This technical verification does not constitute required review approval.
Issue #57 remains pending approval by `@BurakOztekin` and `@bengisucvd`, plus
Dr. Akba's out-of-band read of the `interfaces.py` and `training/types.py`
contracts. ADR-024 remains Open until those decisions are recorded.