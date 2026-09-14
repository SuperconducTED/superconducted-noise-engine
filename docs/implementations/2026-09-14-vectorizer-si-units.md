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
| `tests/conftest.py` | Shared dummy snapshot uses `XXXe-6` SI coherence values without unit fields. |
| `tests/calibration/test_vectorizer_units.py` | Checks real-fixture agreement, grid firing and viable ensembles for both placements, invalid units and preservation of synthetic SI values. |
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
conventions. The loader, locked TSK and Kraus implementations are unchanged.

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
sandbox with `--basetemp=.pytest-tmp-issue66-final`. NC-021 and NC-052 identify
the base plus working-tree patch and must be pinned to the implementation commit
before merge.

The archive-fixture smoke command completes for ensemble sizes 1, 8 and 16
with viable consequent seed 0, and completes the final sanity simulation.
To reproduce NC-052, load that fixture with the smoke script's `_load_snapshot`,
extract with `BasicCalibrationVectorizer`, and evaluate a `TSKRuleBase.from_grid`
with `_default_mfs_for_feature(name)` for each `feature_names` entry and
`output_dim=2`; sum `evaluate(features).firing_strengths`. The regression tests
compare coherence means directly to `load_snapshot` plus `mean_t1`/`mean_t2`.

## Related docs

- ADR-010, ADR-013 and ADR-017 in `docs/decisions.md`.
- NC-021 and NC-052 in `docs/numerical-claims.md`.
- Issue #66 and cycle-1 follow-up audit item 6.
