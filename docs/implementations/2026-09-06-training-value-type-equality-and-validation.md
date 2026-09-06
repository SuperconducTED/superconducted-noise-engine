# 2026-09-06: Training value-type equality and validation coverage

## Problem / Motivation

Two of the mechanical findings from the PR #69 review of Issue #57, plus a
correction to a third that turned out to be wrong.

**Equality and hashing raise.** Issue #57 FR-4 requires `eq=False` on frozen
dataclasses holding ndarray fields, and explains why: a generated `__eq__`
compares the fields as a tuple, and tuple comparison falls back to `==` on an
ndarray element, which returns an array and then raises
`ValueError: The truth value of an array with more than one element is
ambiguous`. The generated `__hash__` raises `TypeError: unhashable type` for
the same reason. `TrainingSet` received the fix; `TrainingDiagnostics`,
`TrainingResult`, `QubitTargets` and `SnapshotTarget` did not.

**No validation coverage.** Issue #57 §9.1 requires rejection tests for
`TrainingResult` and `TrainingDiagnostics` — non-finite loss and RMSE, a
`clip_binding_rate` outside `[0, 1]`, negative counts, a bad condition number.
Before this change no test referenced either type outside a stub signature, so
every `__post_init__` rejection branch was unexercised.

**A correction.** The review also claimed `lse_condition_number` should reject
`inf` as well as NaN. That finding was wrong and this change does not make it;
see Design decisions.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/types.py` | `eq=False` on `TrainingDiagnostics` and `TrainingResult`, each docstring saying why; a comment recording why `inf` is deliberately accepted for `lse_condition_number`. |
| `src/superconducted/training/targets.py` | `eq=False` on `QubitTargets` and `SnapshotTarget`, with the same reasoning in their docstrings. |
| `tests/test_training_types.py` | Adds the §9.1 rejection table for both result types, pins `inf` acceptance for the condition number, and pins that the four array-bearing types compare and hash without raising. |

Deliberately **not** changed here: `TrainingSet`'s optional-metadata contract
(FR-4 requires `timestamps`, `provenance` and `archive_ref`; the shipped type
makes them optional) and the hardcoded `clip_binding_rate = 0.0`. Both are
design questions for the module owner rather than mechanical fixes, and remain
open on PR #69.

## Implementation approach

`eq=False` on a frozen dataclass suppresses generation of both `__eq__` and
`__hash__`, so both fall back to `object`'s identity-based versions. Two
distinct instances with equal contents therefore compare unequal. That is the
behaviour FR-4 prescribes, and it is strictly better than raising: callers that
need value equality compare the fields they care about with `np.array_equal`,
which `tests/test_anfis.py::test_fit_is_deterministic_for_identical_inputs_and_configuration`
already does.

`ParameterCount` and `SkipCounts` are left with generated equality on purpose.
They hold only integers, so their `__eq__` is well defined and useful.

## Mathematical / Statistical details

N/A — purely structural, apart from one numerical-linear-algebra fact that
drives a decision below: `numpy.linalg.cond(A)` is the ratio of the largest to
the smallest singular value of `A`, so it is `+inf` whenever `A` is rank
deficient. Rank deficiency does not prevent `numpy.linalg.lstsq` from returning
a solution; `lstsq` returns the minimum-norm least-squares solution, which is
well defined and unique even when the normal equations are not.

## Design decisions

**Why the `inf` condition-number finding was withdrawn.** The review argued
that `lse_condition_number` should reject `inf`, on the grounds that
`numpy.linalg.cond` returns `inf` for a singular design matrix and that is "the
exact case the diagnostic exists to surface". The second half of that sentence
refutes the first: rejecting the value does not surface the case, it replaces a
successful fit with a crash and discards the signal.

The existing suite proved it concretely. Making `__post_init__` reject `inf`
broke `tests/test_anfis.py::test_observation_weights_change_the_lse_optimum`,
which fits `features = [[0.0], [0.0]]` against a single rule. Its design matrix
is `[[0, 1], [0, 1]]` — rank 1, so `cond` is `inf` — yet the fit is entirely
meaningful: the intercept is identifiable, the slope is not, and `lstsq`
returns the minimum-norm answer the test asserts (`5.0` unweighted, `9.0` at
weights `1:9`). A rank-deficient design is a normal outcome with few training
rows, not an error.

So the rule stays as shipped: reject NaN, which means the computation itself
broke and carries no information, and reject negatives, which are impossible;
accept `inf`, which is the honest report that the design was rank deficient.
Issue #57 FR-6's phrase "rejects ... a non-finite condition number" is
under-specified on this point, and the code is right where the ticket is not.
The acceptance is now pinned by a test with the reasoning in its docstring, so
the next reader does not re-make the same mistake.

**Why the equality tests compare separately constructed objects.** The first
draft of `test_array_bearing_types_compare_by_identity_without_raising` asserted
`value == value`, and it passed against the *unfixed* code — proving nothing.
Python's tuple comparison checks identity element-wise before falling back to
`==`, so comparing an object with itself short-circuits and never reaches the
ndarray field. The test now builds two independent instances and compares
those, which is the case that actually raises. Verified by running the new
tests against the pre-fix source: 3 failed, then 2 after the condition-number
finding was withdrawn, and 0 after the fix.

## Verification

```bash
pytest tests/test_training_types.py -q     # 26 passed
pytest tests/ -q                           # 396 passed
ruff check . && ruff format --check .
mypy --strict
python scripts/check_ids.py
```

Before/after evidence, which is the point of the exercise — the new tests were
run against the source at the parent commit and fail there:

```
FAILED tests/test_training_types.py::test_array_bearing_types_compare_by_identity_without_raising
FAILED tests/test_training_types.py::test_array_bearing_types_are_hashable
2 failed, 24 passed
```

## Related docs

- Issue #57 FR-4 (`eq=False` and why), FR-6 (`TrainingDiagnostics` fields and
  their validation), §9.1 (the rejection table)
- PR #69 review — the findings this implements, and the one it withdraws
- `docs/implementations/2026-09-06-duplicate-id-ci-check.md` — the parent PR in
  this stack
