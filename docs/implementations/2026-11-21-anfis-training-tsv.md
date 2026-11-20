# 2026-11-21: ANFIS training TSV input

## Problem / Motivation

Issue #60 FR-15 requires the ANFIS training workflow to consume the TSV written
by #63 without changing feature units, row provenance, weights, or the snapshot
boundary used for validation. The dataset builder writes a TSV but previously
provided no inverse operation.

## What changed

| File | Change |
| --- | --- |
| `src/superconducted/training/dataset.py` | Load a builder TSV into a `TrainingSet`. |
| `tests/training/test_dataset.py` | Exercise round trips, validation splits, invalid inputs, and committed evidence. |

## Implementation approach

`load_training_tsv` reads the named feature and target columns, UTC-aware
`last_update_date`, qubit digest, and selected weight column. `TrainingSet`
validates finite values, positive weights, and timestamp awareness, and its
existing `time_split` enforces nonempty training and validation sets. Features
use archive microseconds for T1 and T2, with dimensionless readout error;
targets are dimensionless. Warm starts must use the same feature units.

## Mathematical / Statistical details

N/A: this change loads and partitions existing data without computing a fit.

## Design decisions

The TSV does not contain its full archive commit. The caller must supply that
SHA from the accompanying evidence record; it is recorded but cannot be
independently verified against the TSV. The loader requires a full lowercase
SHA to prevent accidentally recording a moving branch or abbreviated ID.
Uniform and hour-of-day weights are read from the TSV, not recomputed.

This is a partial FR-15 change, not the training CLI. The future CLI must call
`time_split` before fitting and reject a missing validation set. Model JSON
serialization and FR-16 remain dependent on #62's shared writer and reader;
this change does not introduce a competing serializer or claim a model fit.

## Verification

- `PYTHONPATH=src python -m pytest tests/training/test_dataset.py -q`
- `python -m ruff check src/superconducted/training/dataset.py tests/training/test_dataset.py`
- `python -m mypy --strict src/superconducted/training/dataset.py`

## Related docs

- Issue #60, FR-15 and FR-16.
- Issue #62, model serialization.
- `docs/evidence/training-set/README.md` for archive SHA and feature units.