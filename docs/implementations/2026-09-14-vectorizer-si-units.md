# 2026-09-14: Vectorizer SI units

## Problem / Motivation

[Issue #66](https://github.com/SuperconducTED/superconducted-noise-engine/issues/66)
identified that the vectorizer ignored IBM Nduv units, passing microseconds to
a grid defined in seconds. This corrects the claim in item 6 of the dated
`docs/audits/2026-05-25-followup-issues.md` that both parsers produced correct
results: the duplicated walk was already a defect, not merely a maintenance
risk. That historical document is unchanged.

## What changed

| File | Description |
| --- | --- |
| `src/superconducted/calibration/features.py` | Validates declared units using the loader's expected-unit table and scales to SI using its conversion table. |
| `scripts/first_ensemble_run.py` | Synthetic coherence inputs use `50e-6` in implicit SI seconds; readout error declares its dimensionless unit. |
| `tests/conftest.py` | Shared dummy snapshot drops the unit fields from T1 (`100e-6`, `110e-6`) and T2 (`80e-6`, `90e-6`), leaving them as unitless SI seconds. |
| `tests/calibration/test_vectorizer_units.py` | Checks real-fixture agreement, grid firing and viable ensembles for both placements, invalid units and preservation of synthetic SI values. |
| `src/superconducted/calibration/loader.py` | Review follow-up: `_EXPECTED_UNITS` and `_UNIT_SCALE` are renamed to public `EXPECTED_UNITS` and `UNIT_SCALE`, so the feature layer shares one table instead of importing another module's privates. Parsing behaviour is unchanged. |
| `docs/decisions.md` | Clarifies ADR-010 units and tracks parser convergence under ADR-013. |
| `docs/numerical-claims.md` | Registers the corrected reduced-fixture measurement and updates NC-021 differentially. |

## Implementation approach

Option A preserves the `CalibrationFeatureExtractor` ABC and raw snapshot
input. Only the three consumed fields are validated; unrelated vendor fields
remain ignored. Declared units must match the typed loader (`us` for T1/T2,
empty string for readout error). A mismatch raises `CalibrationParseError`
with backend, timestamp, qubit, field, unit and value, before filtering values.
Missing/non-numeric/non-finite values retain the existing skip policy.
Legacy entries with no unit key remain already-SI inputs; an explicit null
or empty coherence unit is an error. Synthetic vectorizer and smoke-test inputs use unitless SI seconds; real archive fixtures retain their explicit units.

## Mathematical / Statistical details

Each finite coherence observation in microseconds is multiplied by `1e-6`
before averaging; dimensionless readout error is unchanged. On the committed
reduced fixture, corrected means are T1 `0.0001551924205171878` seconds,
T2 `0.00010959537464376821` seconds, readout error `0.03532605293469551`.
The shipped endpoint grid's firing sum is `0.10769113232875129` (NC-052).
These are reduced-fixture measurements, not the different August snapshot
quoted in the issue.

## Design decisions

Use option A as recommended by the issue. Option B (typed snapshot consumption)
is tracked in the ADR-013 revisit note because it changes an ABC signature and
requires reconciling parsing policies. Option C would retain inconsistent unit
conventions. The loader's parsing behaviour is unchanged, as are the locked TSK and Kraus
implementations; the loader's only edit is the constant rename noted above.

## Verification

Measured on the local Windows workstation, using the repository Python 3.14
environment, on base `004e14ed153c4ea1421f801e4d3c00e26aa5ef8a` plus this patch.
Measurements are provisional; canonical verification remains the team batch record.

```powershell
.venv/Scripts/python.exe -m pytest tests/ -q -o addopts='' -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check src/superconducted/calibration/features.py scripts/first_ensemble_run.py tests/calibration/test_vectorizer_units.py
.venv/Scripts/python.exe -m mypy src/superconducted/calibration/features.py scripts/first_ensemble_run.py
.venv/Scripts/python.exe scripts/first_ensemble_run.py --snapshot tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json
```

Full suite: **483 passed**; direct collection: **483**, versus **465** on the base.
Ruff and strict mypy checks pass. The sandbox run encountered temporary-directory
permission errors; the successful full run used approved execution outside the
sandbox with `--basetemp=.pytest-tmp-issue66-final`. NC-021 and NC-052 originally identified
the base plus working-tree patch; both were re-pinned to `6394951` in the following
commit, measured there rather than carried over.

The archive-fixture smoke command completes for ensemble sizes 1, 8 and 16
with viable consequent seed 0, and completes the final sanity simulation.
To reproduce NC-052, load that fixture with the smoke script's `_load_snapshot`,
extract with `BasicCalibrationVectorizer`, and evaluate a `TSKRuleBase.from_grid`
with `_default_mfs_for_feature(name)` for each `feature_names` entry and
`output_dim=2`; sum `evaluate(features).firing_strengths`. The regression tests
compare coherence means directly to `load_snapshot` plus `mean_t1`/`mean_t2`.

### Review verification, 2026-09-14

The run above is the author's. It is recorded as measured and is not restated
here. It used Python 3.14, which is outside what this project gates on:
`.github/workflows/ci.yml` runs a 3.11 and 3.12 matrix, `pyproject.toml`
declares `requires-python = ">=3.11"` with classifiers to 3.12, and
`[tool.mypy]` pins `python_version = "3.11"`. So it is recorded as
supplementary, and CI is the authority.

Re-measured during review in a clean CPython 3.12.10 virtual environment at a
short path (not the repository `.venv`, per the NC-021 note on that
environment), running the same commands CI runs rather than per-file subsets:

```bash
ruff check .                       # All checks passed
ruff format --check .              # 3 pre-existing files, identical on main
python scripts/check_ids.py        # No duplicate or colliding ADR / NC identifiers
mypy --strict                      # Success: no issues found in 35 source files
pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider
pytest tests/ -q -o addopts="" -p no:cacheprovider
```

Collection and full run both report **483**, matching the author's figure.
`ruff format --check .` reports `docs/implementations/2026-09-06-*.md`,
`docs/implementations/2026-09-08-*.md` and `tests/fixtures/calibration/README.md`;
all three report identically at `004e14ed`, so they are pre-existing and not
introduced here. `mypy --strict` needs `--python-version 3.12` locally because
numpy 2.5.2's stubs use `type` statements that the configured 3.11 target
rejects while parsing them; that failure also reproduces at `004e14ed` and is an
environment artefact, not a finding against this branch. CI is green on both the
3.11 and 3.12 legs.

NC-052 was reproduced independently from the committed fixture and agrees to the
last digit: T1 `0.0001551924205171878` s, T2 `0.00010959537464376821` s, readout
error `0.03532605293469551`, endpoint-grid firing sum `0.10769113232875129`. The
one-argument `_default_mfs_for_feature(name)` recipe above is correct because
`DEFAULT_MF_PLACEMENT` is `endpoint`.

## Related docs

- ADR-010, ADR-013 and ADR-017 in `docs/decisions.md`.
- NC-021 and NC-052 in `docs/numerical-claims.md`.
- Issue #66 and cycle-1 follow-up audit item 6.
