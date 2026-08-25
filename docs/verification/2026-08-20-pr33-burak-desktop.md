# PR #33 verification · Burak's desktop · 2026-08-20

**Commit tested**: `768cd86d6ccb844b329f427ee7306bfc93de02a7`
**Branch**: `feature/mert-adr-023-tanhmf-clip-exemption`
**Verdict**: VERIFIED

## Machine

| Field | Value |
| --- | --- |
| OS | Microsoft Windows 10 Home 10.0.19045 |
| CPU | AMD Ryzen 5 5500 |
| RAM | 15.9 GB |
| Python | 3.12.10 |
| Install | fresh clone, fresh venv, requirements.txt + requirements-dev.txt |

## Results

| Check | Expected | Observed |
| --- | --- | --- |
| ruff check . | All checks passed! | All checks passed! |
| ruff format --check . | 34 files already formatted | 34 files already formatted |
| mypy --strict src/superconducted | no issues in 22 source files | Success: no issues found in 22 source files |
| pytest tests/ -q | 152 passed | 152 passed |
| pytest tests/test_membership.py -v | 37 passed | 37 passed |
| raw at L=0, R=1, sL=10, sR=0.1, x=-1 | about -0.4013118 | -0.40131233782639436 |
| mutation, floor removed | 2 failed, 35 passed | 2 failed, 35 passed |
| after git checkout -- restore | 37 passed | 37 passed |

## Notes

none

## Full transcript

Transcript will be provided in the PR comment.