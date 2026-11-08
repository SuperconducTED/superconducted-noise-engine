# Issue #57 retroactive read · @BurakOztekin · 2026-11-02

**Read at**: `origin/main` `695c90ca`
**Scope** (close plan step 1, due 2026-10-20, delivered late): `TSKTrainer`, the `MembershipFunction` docstring correction, and the four `types.py` value types (`TrainingSet`, `TrainingResult`, `TrainingDiagnostics`, `ParameterCount`).
**Verdict**: `Retroactive read of #57 @ 695c90ca: approve`, with two non-blocking findings.

This read is of the merged state, not a PR review, and it is late: the plan's deadline was 2026-10-20. The close comment should name that deviation.

## Drift since the plan's `c33e438e`

`git log c33e438e..695c90ca -- src/superconducted/types.py src/superconducted/interfaces.py` is empty, so the plan's description of what moved still holds. Later commits touched only `src/superconducted/training/` (#60, #63).

## What was read

| Item | Location | Result |
| --- | --- | --- |
| `TSKTrainer` | `src/superconducted/interfaces.py:179` | Contract is complete: `TypeError` for a foreign `RuleBase`, a new `rule_base` in the result, invariants (a) to (c), and the three shallow-read-only hazards of `fuzzy/tsk.py` named as the trainer's obligation. The warm-start paragraph records the anchored-consequent third mechanism as ADR-024 clause 5 requires. |
| `MembershipFunction` docstring | `src/superconducted/interfaces.py:38` | Now points at `superconducted.training`, consistent with `fuzzy/tsk.py`'s "intentionally NOT in this module". The correction is in. |
| `TrainingSet` | `src/superconducted/types.py:190` | Validates 2-D shapes, non-zero rows, finiteness, tz-aware timestamps (normalized to UTC), non-empty provenance, name counts, positive weights. Arrays are copied and set read-only. `time_split` cuts at a timestamp so equal timestamps stay together (NC-028). |
| `ParameterCount` | `src/superconducted/types.py:296` | Non-negative, `total == premise + consequent`. |
| `TrainingDiagnostics` | `src/superconducted/types.py:311` | Rate in `[0, 1]`, counts non-negative, condition number not negative or NaN, `standardization` finite. |
| `TrainingResult` | `src/superconducted/types.py:346` | `loss_history`, `train_rmse` and `validation_rmse` finite. |

## Findings

Neither blocks the close; both are for whoever next touches `types.py` (Dr. Akba's module).

1. **`TrainingDiagnostics.standardization` aliases caller arrays.** `__post_init__` checks finiteness but does not copy or freeze the arrays, unlike `TrainingSet`. Probed at `695c90ca`: after constructing with `(a,)`, setting `a[0] = np.nan` changes `diagnostics.standardization[0]` to `[nan, 1.]`. The post-construction value can therefore violate the finiteness check that was just enforced.
2. **`TrainingResult.train_rmse` / `validation_rmse` are likewise not copied or frozen.** Same class of defect as 1, same fix: copy and set `writeable = False`, as `TrainingSet` does.

## Checks run

Run from a worktree at `695c90ca` with the repository `.venv`:

| Check | Observed |
| --- | --- |
| `pytest -q tests/training tests/test_interfaces.py` | `109 passed in 2.24s` |
| `mypy --strict src/superconducted` | `Success: no issues found in 31 source files` |
| `ruff check src tests` | `All checks passed!` |

The full suite was not re-run for this record.
