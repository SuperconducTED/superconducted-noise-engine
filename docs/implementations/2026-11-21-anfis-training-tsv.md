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

## As of 2026-11-23: review fixes (appended; the sections above are not edited)

Added by @mertefesensoy after reading the PR at `9eb5d084`, as three commits on top of it. The sections above
describe the loader as first written; where this section differs, this section is current.

### Problem / Motivation

The review found no defect in what the loader reads. It found one test that could not fail, four guards
no test pinned, and three kinds of input the loader accepted although the builder never writes them.

| Finding | Evidence at `9eb5d084` |
| --- | --- |
| The `hour_of_day` leg of the round-trip test is vacuous | Both fixture rows sit at 12:00 UTC, so both weightings are 1.0. Reading `weight_uniform` for both weightings passed all 8 TSV tests. |
| Unpinned guards | Removing the empty-file refusal, the `archive_ref` length check, the alphabet check, or the acceptance of a 64-character ref each passed every test. `"HEAD"` trips the length and alphabet checks together, so neither was pinned alone. |
| Ragged rows accepted | A row with a surplus cell loaded (`csv.DictReader` files it under the key `None`). A row missing a cell in a column the loader does not read loaded too. |
| Rows out of time order accepted | Two rows with one `last_update_date`, the same row twice, and an earlier row after a later one each loaded as two rows. |
| A wrong ref accepted | Any 40-character lowercase hex string was recorded as `archive_ref`, including the other committed TSV's SHA. |

### What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/dataset.py` | `load_training_tsv` refuses a row without one cell per header column, refuses rows not in strictly increasing `last_update_date` order, and refuses an `archive_ref` that contradicts the short SHA in a builder-pattern file name. |
| `tests/training/test_dataset.py` | 14 more test cases: the `hour_of_day` column on the committed evidence, the five unpinned behaviours, the two ragged-row shapes, four order violations with one accepted pair, and the file-name check. |
| `docs/evidence/training-tsv-loader/mutate.py` | The mutation check: 17 mutants of the loader, judged by the loader's tests. |
| `docs/evidence/training-tsv-loader/mutate.out.txt` | Its output on the fixed loader. |

### Implementation approach

**One cell per column.** `csv.DictReader` does not fail on a ragged row: it collects surplus cells under the
key `None` and fills missing cells with the value `None`. The loader now refuses a row where either appears,
naming the line. Before, a missing cell was caught only when it fell in a column the loader reads.

**Strictly increasing timestamps.** The builder orders rows by `(last_update_date, path)` and raises
`ArchiveTimestampError` when two distinct device states share a timestamp. So in a file the builder wrote,
each row's timestamp is strictly later than the one before. The loader checks exactly that, after
`TrainingSet` has refused naive timestamps, so every pair is comparable. The comparison is on instants:
`2026-09-02T15:00:00+03:00` after `2026-09-02T12:00:00+00:00` is a tie. Both committed evidence TSVs (797 and
504 rows) satisfy it.

**The file name.** `scripts/build_training_set.py` names its output `<run date>-<archive_ref[:8]>.tsv`. A file
with that name states its ref's first eight characters, and the loader refuses an `archive_ref` that does not
start with them. A file with any other name states nothing and is not checked.

### Mathematical / Statistical details

N/A: structural checks on input. No fit, weight or statistic is computed.

### Design decisions

- **Refuse, do not repair.** A tied or repeated row could be dropped silently. But the loader cannot know
  which of two edited rows is the real one, and "one row per distinct device state" is the property the fit
  relies on. So the loader stops and the caller rebuilds the TSV from the archive.
- **The file-name check narrows a decision recorded above.** "Design decisions" above says the SHA "cannot
  be independently verified against the TSV". That still holds beyond eight characters and for any renamed
  file. The check is its own commit (`load_training_tsv checks archive_ref against a builder file name`) so
  it can be dropped without touching the other fixes, if the owner prefers the loader to stay name-agnostic.
- **Not done here: an optional SHA-256 of the file.** `docs/evidence/training-set/README.md` records each
  TSV's SHA-256. Checking it would tie the rows, not only the name, to the evidence record. It needs a new
  parameter and a decision on who supplies the digest, so it is left for the training CLI.
- **The cut date is not this PR's.** The committed-evidence test splits at `2026-09-01` only to exercise the
  boundary. That date is not a default for the fit. `time_split` gives validation the rows at or after the
  cut, and `ANFISTrainer` returns its best-validation state, so a fit cut at `2026-09-01` would let the
  ladder's test rows choose the stopping epoch. The fit's windows are set in Issue #161's pre-registration
  (lead's decision of 2026-11-23, comment 7102611064): fit before `2026-08-10`, conformal calibration from
  `2026-08-10` to `2026-09-01`, test from `2026-09-01`, with early stopping reading a slice inside the fit
  window. The committed 797-row TSV has 423, 95 and 279 rows in those windows (laptop count, not a register
  row).

### Verification

```bash
PYTHONPATH=src python -m pytest tests/training/test_dataset.py -q        # 38 passed
python docs/evidence/training-tsv-loader/mutate.py --root . --python "$(command -v python)" \
    --out docs/evidence/training-tsv-loader/mutate.out.txt               # 17 mutants: 17 killed
```

| Check | Result (laptop, exact pins, 2026-11-23) |
| --- | --- |
| `tests/training/test_dataset.py` at `9eb5d084` | 24 passed |
| The same file after the fixes | 38 passed |
| The 7 new cases for the row and file-name checks, before the loader change | 7 failed |
| Mutation check on the fixed loader | 17 of 17 killed, 0 survived, 0 harness errors |
| The same idea at `9eb5d084`, 10 comparable mutants | 5 killed, 5 survived (the hour_of_day column, the empty file, the two ref checks, the 64-character ref) |

Two limits on the mutation figures. The predictions in `mutate.py` were written with the script, after the
fixes, so they are a regression record and not a pre-registration. And the `9eb5d084` row comes from an
earlier, uncommitted version of the script; its five survivors are the five behaviours the first new commit
pins.

The mutation script counts a mutant as killed only when pytest exits 1. Any other non-zero exit is reported as
a harness error and fails the script, so a broken test run cannot pass as a kill.

Windows laptop, one machine. The desktop verification record (NFR-8) is still owed, as the PR body says.
