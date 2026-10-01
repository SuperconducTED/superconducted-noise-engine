# Phase 3 batch 1 verification · Burak's desktop · 2026-10-01

**Implementation commit measured**: `110cfad87a11fe2dcf99daf0ccec8b5f82712238`
**Branch**: `origin/main`, detached clean clone
**Verdict**: The four #100 claim measurements are verified on the canonical
desktop. Two pre-existing quality-gate failures and the unmerged #74 smoke-path
defect are recorded below as findings, not silently repaired in this record.

## Machine

| Field | Value |
| --- | --- |
| Host | `DESKTOP-2CST637` |
| OS | Linux 6.18.40.1-microsoft-standard-WSL2 |
| Python | 3.12.3 |
| pytest | 9.1.1 |
| Ruff | 0.16.8 |
| mypy | 1.20.2 |
| Qiskit | 2.5.2 |
| Qiskit Aer | 0.17.2 |
| Calibration archive tip fetched | `196b80a7ad3da5570013a9b359459aac4cc6abd1` |
| NC-044 pinned archive ref | `3d1569d18bcc007c35f3f628f79e678e6061bdc3` |
| NC-047 pinned archive ref | `c63ce21c9cfdef6790a8ba572081d5cad154953c` |

The run used a fresh clone and a fresh `.venv-verify`; the only worktree entry
after installation was that untracked environment directory.

## Repository Gates

| Check | Observed |
| --- | --- |
| Test collection | 701 collected |
| Full test suite | 701 passed in 104.54 s |
| `ruff check .` | Passed |
| `python scripts/check_ids.py` | Passed |
| `ruff format --check .` | Failed: four pre-existing files would be reformatted |
| `python -m mypy --strict` | Blocked before project checking by NumPy 2.5.3 stubs under the configured Python 3.11 target |
| `python -m mypy --strict --python-version 3.12` | Passed: no issues in 38 source files |

NC-021 at the measured commit records 701, so collection and execution agree
with the register. The format failure affects
`docs/implementations/2026-09-06-issue-58-decisions-and-r2-orientation.md`,
`docs/implementations/2026-09-08-tsk-trainer-contract-docstring.md`,
`docs/implementations/2026-09-14-vectorizer-si-units.md`, and
`tests/fixtures/calibration/README.md`; it also occurred at the parent commit
and is not changed here. The normal mypy command fails because `pyproject.toml`
targets Python 3.11 while NumPy 2.5.3's stubs use Python 3.12 `type` syntax.
Both are follow-up configuration/formatting findings, not #100 edits.

## Claim Measurements

| Claim | Command / reference | Desktop result | Verdict |
| --- | --- | --- | --- |
| NC-044 | `python -m scripts.feature_distribution --repo . --ref 3d1569d18bcc007c35f3f628f79e678e6061bdc3 --out /tmp/issue-100-survey.tsv` | 975 rows; `runtime_seconds=70.72`; wall time 76.95 s | Supersedes the provisional laptop range |
| NC-045 | Seven-shape parameter-count procedure in `docs/implementations/2026-09-09-training-floor-derivation.md` | Gaussian: 18 premise + 216 consequent = 234; floor 1170 | Verified |
| NC-046 | Same procedure | Totals 234, 234, 243, 243, 243, 252, 252; floors 1170 through 1260 | Verified |
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
That is the known unmerged #74 defect, not a clean smoke result; PR #103 owns
the compile-before-prepare repair and is not included in this batch base.

## Reproduction

```bash
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

## Scope

This is the required canonical desktop batch record for Issue #100. It changes
no implementation, does not repair the format/mypy baseline findings, and does
not claim that the unmerged #74 smoke-path repair was measured on `main`.