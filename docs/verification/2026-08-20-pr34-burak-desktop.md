# PR #34 verification · Burak's desktop · 2026-08-20

**Commit tested**: `07fd9ec172a4c77b1de05d9e9362ac780cf9b73c`
**Branch**: `feature/mert-issue-31-smoke-grid-27-rules`
**Verdict**: VERIFIED
**Placement recommendation**: endpoint - It ensures coverage at the extremes, directly addressing the core concern of Issue #31.

## Machine

| Field | Value |
| --- | --- |
| OS | Microsoft Windows 10 Home 10.0.19045 |
| CPU | AMD Ryzen 5 5500 |
| RAM | 15.9 |
| Python | 3.12.10 |
| Install | fresh clone, fresh venv, requirements.txt + requirements-dev.txt |

## Results

| Check | Expected | Observed |
| --- | --- | --- |
| ruff check . | All checks passed! | All checks passed! |
| ruff format --check . | 35 files already formatted | 35 files already formatted |
| mypy --strict src/superconducted | no issues in 22 source files | Success: no issues found in 22 source files |
| pytest tests/ -q | 163 passed | 163 passed |
| pytest tests/test_first_ensemble_run.py -v | 18 passed | 18 passed |
| direct n_rules check | 27 | 27 |
| min_coverage endpoint / interior | 0.606531 / 0.800737 | 0.606531 / 0.800737 |
| coverage_at_hi endpoint / interior | 1.000000 / 0.800737 | 1.000000 / 0.800737 |
| mean_separation endpoint / interior | 0.514978 / 0.440549 | 0.514978 / 0.440549 |
| smoke run, endpoint | consequent_seed=1, no degeneracy error | consequent_seed=1, no degeneracy error |
| smoke run, interior | consequent_seed=0, no degeneracy error | consequent_seed=0, no degeneracy error |
| mutation, 2 MFs restored | 4 failed, 14 passed | 4 failed, 14 passed |
| after git checkout -- restore | 18 passed | 18 passed |

## Placement judgement

I recommend `endpoint` as the default layout. Issue #31 was specifically opened because extreme calibration states were left uncovered. By peaking exactly at the extremes, `endpoint` guarantees full coverage (`coverage_at_lo` and `coverage_at_hi` = 1.000000) and provides better `mean_separation` (0.514978). This ensures that the noise model can sharply discriminate these critical boundary states during benchmark runs.

## Notes

none

## Full transcript

Transcript will be provided in the PR comment.