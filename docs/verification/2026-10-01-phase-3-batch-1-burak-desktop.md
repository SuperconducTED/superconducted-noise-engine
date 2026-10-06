# Phase 3 batch 1 verification · Burak's desktop · 2026-10-01

**Implementation commit measured**: `110cfad87a11fe2dcf99daf0ccec8b5f82712238`
**Branch**: `origin/main`, detached clean clone
**Verdict**: The four #100 claim measurements are verified on the canonical
desktop. All repository gates passed with the dependency pins at the measured
commit. The smoke-path observation below records the state of that commit.

## Machine

| Field | Value |
| --- | --- |
| Host | `DESKTOP-2CST637` |
| OS | Linux 6.18.40.1-microsoft-standard-WSL2 |
| Python | 3.12.3 |
| NumPy | 2.4.4 |
| pytest | 9.0.3 |
| Ruff | 0.15.12 |
| mypy | 1.20.2 |
| Qiskit | 2.4.1 |
| Qiskit Aer | 0.17.2 |
| Calibration archive tip fetched | `196b80a7ad3da5570013a9b359459aac4cc6abd1` |
| NC-044 pinned archive ref | `3d1569d18bcc007c35f3f628f79e678e6061bdc3` |
| NC-047 pinned archive ref | `c63ce21c9cfdef6790a8ba572081d5cad154953c` |

The run used a fresh clone and a fresh `.venv-pinned`. Dependencies came from
`requirements.txt` and `requirements-dev.txt`, followed by `pip install -e .
--no-deps`; the installed Qiskit, Qiskit Aer, NumPy, Ruff, mypy, and pytest
versions matched those pins.

## Repository Gates

| Check | Observed |
| --- | --- |
| Test collection | 701 collected |
| Full test suite | 701 passed in 30.67 s |
| `ruff check .` | Passed |
| `python scripts/check_ids.py` | Passed |
| `ruff format --check .` | Passed: 68 files already formatted |
| `python -m mypy --strict` | Passed: no issues in 38 source files |

NC-021 at the measured commit records 701, so collection and execution agree
with the register. A first run in an unpinned `.venv-verify` (Ruff 0.16.8,
NumPy 2.5.3) reported four Markdown format differences and a mypy stub error;
both gates pass on the pinned stack recorded above.

## Claim Measurements

| Claim | Command / reference | Desktop result | Verdict |
| --- | --- | --- | --- |
| NC-044 | `python -m scripts.feature_distribution --repo . --ref 3d1569d18bcc007c35f3f628f79e678e6061bdc3 --out /tmp/issue-100-survey.tsv` | 975 rows; `runtime_seconds=70.72`; wall time 76.95 s | Supersedes the provisional laptop range |
| NC-045 | Seven-shape parameter-count procedure in `docs/implementations/2026-09-09-training-floor-derivation.md` | Gaussian: 18 premise + 216 consequent = 234; floor 1170 | Verified |
| NC-046 | Same procedure | `GaussianMF` and `TanhSigmoidMF`: 234 / 1170; `TriangularMF`, `TanhBellMF`, and `IntervalGaussianMF`: 243 / 1215; `TrapezoidalMF` and `TanhMF`: 252 / 1260 | Verified |
| NC-047 | `backfill_state_index.py` then `pipeline_health.py --floor NC-012=1170` at `c63ce21` | 563 distinct states, 994 documents, 43.36016096579477% duplication, 607 states remaining | Verified |

The NC-044 TSV has the same header and 975 paths as the committed evidence but
is not byte-identical after Issue #66: 733 rows differ only in `mean_T1` or
`mean_T2`, with maximum relative difference $4.3300028370468066 \times 10^{-16}$.
This is the already-registered NC-054 floating-point drift, not a changed
feature-distribution claim.

## #59 Acceptance and Smoke Path

`python -m pytest tests/test_parameterization.py -q -k "never_degenerate or
clamp_rate_is_pinned or bin_cover_holds_on_the_real"` passed 14 selected tests
(109 deselected), satisfying #59 step 9's acceptance checks.

`python scripts/first_ensemble_run.py --qubits 2` completed ensemble sizes 1,
8, and 16 plus the 8192-shot sanity run. It also emitted four warnings that
`qft` was not eligible because this measured `main` prepares before transpiling.
That is the #74 defect at the measured commit, not a clean smoke result. As of
2026-10-06, PR #103 has merged the compile-before-prepare repair; that later
state is outside this batch's measured commit.

## Reproduction

```bash
python3 -m venv .venv-pinned
source .venv-pinned/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e . --no-deps
python -m pytest tests/ --collect-only -q -o addopts='' -p no:cacheprovider
python -m pytest tests/ -q
ruff check .
ruff format --check .
python -m mypy --strict
python scripts/check_ids.py
python -m scripts.feature_distribution --repo . --ref 3d1569d18bcc007c35f3f628f79e678e6061bdc3 --out /tmp/issue-100-survey.tsv
python -m pytest tests/test_parameterization.py -q -k "never_degenerate or clamp_rate_is_pinned or bin_cover_holds_on_the_real"
```

For NC-047, check out `c63ce21c9cfdef6790a8ba572081d5cad154953c` from
`origin/calibration-data`, then run `backfill_state_index.py --root .` and
`pipeline_health.py --root . --floor NC-012=1170` with this repository's source
on `PYTHONPATH`.

## Covered PRs and deferrals

This batch covers the 21 PRs merged after the 2026-09-05 batch record and
through the measured commit: #67, #82, #69, #81, #78, #80, #83, #85, #86, #87,
#88, #70, #91, #89, #90, #94, #95, #68, #96, #99, and #102. PR #96 has its own
record at `docs/verification/2026-09-18-pr96-burak-desktop.md`.

NC-052 and NC-055 are deferred to batch 2. Their provisional measurements are
not promoted by this record.

## Scope

This is the required canonical desktop batch record for Issue #100. It changes
no implementation and does not claim that the later #74 smoke-path repair was
measured on `main`.