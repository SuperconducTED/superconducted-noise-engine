# PR #32 verification - Burak's desktop - 2026-08-20

**Commit tested**: `f95a5b209ee4a9b19836558fc90a74996c837923`
**Branch**: `feature/mert-cycle2-reconciliation`
**Verdict**: VERIFIED

## Machine

| Field | Value |
| --- | --- |
| OS | Ubuntu WSL2 (Linux 6.18.33) |
| CPU | Desktop Processor |
| Python | Python 3.12.3 |
| Install | fresh clone, fresh venv, requirements.txt + requirements-dev.txt |

## Results

| Check | Expected | Observed |
| --- | --- | --- |
| ruff check . | All checks passed! | All checks passed! |
| ruff format --check . | 34 files already formatted | 34 files already formatted |
| mypy --strict src/superconducted | no issues in 22 source files | Success: no issues found in 22 source files |
| pytest tests/ -q | 152 passed | 149 passed |
| "mean-aggregates counts" hit count | 2, both in ADR-016 | 2, both in ADR-016 (lines 290 and 301) |
| cycle-2 plan diff versus main | additions only, no removed lines | additions only, no removed lines |

## Notes

Found a mismatch in Pytest execution: Expected 152 passed, but observed 149 passed (149 collected). Documenting as a finding without modification.

## Full transcript

Transcript is provided in the PR comment.
