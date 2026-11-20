# 2026-11-20: issue #148, training result types keep private read-only copies

Written before the code. The plan, the acceptance criteria and the mutants' predicted outcomes
below were committed first; the results are appended at the foot, dated, and nothing above them is
edited afterwards.

## Problem / Motivation

`TrainingDiagnostics` and `TrainingResult` in `src/superconducted/types.py` check their array
fields in `__post_init__` and then keep the caller's own objects. A value that passed the check can
change afterwards, without any error. @BurakOztekin found this in his retroactive read of #57
(`docs/verification/2026-11-02-issue-57-retroactive-read-burak.md`, findings 1 and 2); issue #148
records it, and #57's close names it as a deviation from that ticket's promise of read-only arrays
for all four value types. `TrainingSet`, in the same file, already copies and freezes.

Reproduced on `main` at `4f26881c` on 2026-11-20, laptop, exact-pin environment, before any change:

| Probe | Result on `main` |
| --- | --- |
| Finding 1: construct with `standardization=(a,)`, then `a[0] = nan` | `standardization[0]` reads `[nan, 1.]` and is the caller's object |
| Finding 2: construct with `train_rmse=t`, `validation_rmse=v`, then `t[0] = inf`, `v[0] = nan` | the stored values read `[inf]` and `[nan]` (issue #148 had read this from the code, not run it) |
| Write into the stored `train_rmse` and into a stored `standardization` array | both accepted |
| Pass `standardization` as a list, then append to the list | stored as that list; its length grows to 3 |
| Pass `loss_history` as a list, then append `nan` | stored as that list; it reads `[0.5, 0.4, nan]` |
| `train_rmse` given as `float32`, or as a bare number | stored as `float32`; stored as a Python `float`, not an array |

No caller writes into these fields today: a search of `src`, `scripts`, `tests` and `docs/evidence`
on `main`, and of the same paths at the heads of the open PRs #142, #143, #150, #152, #156 and
#158, finds only reads. So nothing is broken at runtime. The defect is that a passed validation can
be undone silently.

The last three rows go beyond issue #148's wording. They are the same defect in the same two
methods, and the lead chose on 2026-11-20 to fix them here ("Yes, go ahead", with the extras).

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/types.py` | `TrainingDiagnostics` and `TrainingResult` store private, read-only `float64` copies of their arrays, and tuples for `standardization` and `loss_history`. |
| `tests/training/test_types.py` | Tests for the copy, the freeze, the tuple conversion and the `float64` normalisation, per field. |
| `tests/test_anfis.py` | One test that a result returned by `HybridANFISTrainer.fit` carries read-only arrays. |
| `docs/evidence/issue-148-freeze/` | The mutation script and its output. |
| `docs/implementations/2026-11-20-issue-148-freeze-training-results.md` | This record. |

## Implementation approach

One private helper in `types.py`:

- `_frozen_copy(values) -> ndarray`. Contract: input is anything `numpy.array` accepts; output is a
  new `float64` array that owns its data, holds the same numbers, and has `flags.writeable` False.
  No side effect on the input. It never returns the caller's object.

Both `__post_init__` methods then follow one order: **copy, check the copy, store the copy**. The
array that is validated is the array that is kept, so no step sits between the check and the
storage in which the caller's object is still in play. Storage uses `object.__setattr__`, as
`TrainingSet` does, because the dataclasses are frozen and slotted.

- `TrainingDiagnostics.standardization` becomes `tuple(_frozen_copy(v) for v in ...)`. The empty
  tuple stays the empty tuple.
- `TrainingResult.train_rmse` becomes `_frozen_copy(...)`; `validation_rmse` likewise when it is
  not `None`, and `None` stays `None`.
- `TrainingResult.loss_history` becomes `tuple(...)` of the values as given.

The scalar checks (`clip_binding_rate`, the counts, `lse_condition_number`) and every error
message are unchanged. `TrainingSet` is not touched.

## Mathematical / Statistical details

None. No number is computed differently. The one numeric effect is the dtype: a `float32` or
integer input is stored as `float64`, which holds every such value exactly, and a bare number
becomes a zero-dimensional `float64` array.

## Design decisions

- **Copy first, then check.** `TrainingSet` checks `np.asarray(...)`, which may be the caller's
  object, and copies afterwards. In single-threaded code the two orders give the same result. Copy
  first is chosen here because it makes the invariant a one-line statement: what was checked is
  what is stored. Issue #148's suggested wording ("after validation, copy") is the other order; the
  difference has no observable effect, and mutant M9 below is the evidence asked of that claim.
- **`float64` normalisation, as `TrainingSet` does.** The fields are annotated
  `NDArray[np.float64]`, and `TrainingSet` already coerces. The alternative, a copy that keeps the
  input dtype, would leave the annotation untrue for `float32` input. Cost: two behaviours change
  (last row of the table above). No caller relies on either.
- **Tuples for `standardization` and `loss_history`.** A list of frozen arrays can still grow or be
  reordered. Converting the container is what makes the field's own annotation true.
- **`TrainingSet` not refactored onto the helper.** It works and is certified by its own tests;
  moving it is a second change with its own risk, and not what #148 asks.
- **What the freeze is and is not.** It is a guard against accidental writes: any in-place
  operation on a stored array raises `ValueError`. It is not a security boundary. NumPy lets the
  holder of an array that owns its data set `flags.writeable` back to True. `TrainingSet` has the
  same limit. Threat model: a later caller or a refactor that mutates a result by mistake.
- **No closing keyword.** #148's definition of done includes the NC-021 re-measure at the merge
  commit, which can only follow the merge, so the PR and its commits reference the issue and do not
  close it.

## Acceptance criteria, fixed before the code

| # | Criterion |
| --- | --- |
| 1 | For each array field (`standardization`'s elements, `train_rmse`, `validation_rmse`): after construction, a write into the caller's array leaves the stored values unchanged. |
| 2 | For each array field: a write into the stored array raises `ValueError`. |
| 3 | `standardization` and `loss_history` given as lists are stored as tuples, and a later append to the caller's list does not reach the stored value. |
| 4 | `float32` input is stored as `float64`; a bare number for `train_rmse` is stored as a `float64` array. |
| 5 | Unchanged behaviour: the empty `standardization` constructs and stays `()`; `validation_rmse=None` constructs and stays `None`; non-finite `standardization`, `train_rmse`, `validation_rmse` and `loss_history` are still rejected with the same messages (the existing tests, untouched). |
| 6 | A `TrainingResult` returned by `HybridANFISTrainer.fit` has read-only `train_rmse` and read-only `standardization` arrays. |
| 7 | Every new test fails on `main`'s `types.py`, shown by running the new tests at the commit that adds them, before the fix. |
| 8 | Each mutant below does what its prediction says. |
| 9 | `ruff check`, `ruff format --check`, `mypy --strict` and `check_ids.py` are clean, and `pytest tests/` passes, on the exact head, with the exact pins and `PYTHONPATH=src`, printing a `superconducted.__file__` inside the head's own tree. |

## Mutants and their predicted outcomes, fixed before the run

Each mutant is one textual change to the fixed `types.py`, applied to a `git archive` copy of the
head, never to the worktree.

| Mutant | Change | Prediction |
| --- | --- | --- |
| M1 | `_frozen_copy` uses `np.asarray` in place of `np.array` (no copy for `float64` input) | caught: the criterion 1 tests fail, by the test's own write into the caller's array raising, since that array is now the frozen one |
| M2 | `_frozen_copy` does not set `writeable` False | caught by an assertion: the criterion 2 tests and the criterion 6 test |
| M3 | `_frozen_copy` drops `dtype=np.float64` | caught by an assertion: the criterion 4 test |
| M4 | `standardization` is built as a list | caught by an assertion: the criterion 3 test for `standardization` |
| M5 | `standardization` is not stored (the `object.__setattr__` line removed) | caught by an assertion: criteria 1, 2 and 3 for `standardization` |
| M6 | `train_rmse` is not stored | caught by an assertion: criteria 1 and 2 for `train_rmse` |
| M7 | `validation_rmse` is not stored | caught by an assertion: criteria 1 and 2 for `validation_rmse` |
| M8 | `loss_history` is not stored as a tuple | caught by an assertion: the criterion 3 test for `loss_history` |
| M9 | finiteness is checked on the caller's values, not on the copies | **equivalent, predicted to survive**: at that instant the two hold the same numbers |

## Verification

To be appended with the results. The commands:

```bash
python -m pytest tests/training/test_types.py tests/test_anfis.py -q -o addopts='' -p no:cacheprovider
python docs/evidence/issue-148-freeze/mutate.py --python <python>
python -m ruff check . && python -m ruff format --check . && python -m mypy --strict && python scripts/check_ids.py
python -m pytest tests/ -q -p no:cacheprovider
```

## Related docs

- Issue #148; issue #57 and its close
- `docs/verification/2026-11-02-issue-57-retroactive-read-burak.md`, findings 1 and 2
- `docs/team.md`: `types.py` is Dr. Akba's module, with Mert Efe Şensoy as secondary reviewer
- `docs/numerical-claims.md`, NC-021 and Rule 6: the test count is re-measured at the merge commit
