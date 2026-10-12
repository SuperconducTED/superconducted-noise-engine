# PR #107 verification - Burak's desktop - 2026-10-07

**Implementation commit measured**: `462db490eb63711a30a4e74d72527088840e08b0`
**Branch**: `mert/feature-target-fn-units`
**Runbook**: PR #107 review-round-1 desktop runbook
**Verdict**: The unit-contract behavior, NC-039 reproduction, mutation check,
scope, and static gates passed. The runbook's unmodified full-suite command did
not meet its expected result because this machine supplies
`safe.bareRepository=explicit` to Git; the exact mismatch and a diagnostic
process-local rerun are recorded below without modifying project source.

## Environment

- Host: `DESKTOP-2CST637`
- OS: Linux 6.18.40.1-microsoft-standard-WSL2
- CPU: AMD Ryzen 5 5500, 6 cores / 12 logical CPUs
- Git: 2.43.0
- Python: 3.12.3
- numpy 2.4.4, qiskit 2.4.1, qiskit-aer 0.17.2
- pytest 9.0.3, ruff 0.15.12, mypy 1.20.2

The run used a fresh single-branch GitHub clone and a fresh `.venv` created
from `requirements.txt` and `requirements-dev.txt`, followed by
`pip install -e . --no-deps`. The six pinned package versions matched the
requirements files.

## Transcript

### Steps 0-2: prerequisites and tree identity

```text
git version 2.43.0
Python 3.12.3
HEAD       462db490eb63711a30a4e74d72527088840e08b0
first-parent log
462db49 docs: NC-021 to 771 at the merge 1a5839b, record the PR #105 merge
1a5839b merge: main (PR #105) into the feature_target_fn units branch, resolving NC-021
43705f9 docs: NC-021 to 717 at the merge 5517881, record PR #107 review round 1
5517881 merge: main (PR #103) into the feature_target_fn units branch, resolving NC-021
merge-base e39af5063039b5f44d3bd0af07ca50bfb17c8f60
```

All values match the runbook.

### Steps 3-5: environment and static gates

```text
ruff check .              All checks passed!
ruff format --check .     72 files already formatted
mypy --strict             Success: no issues found in 40 source files
scripts/check_ids.py      No duplicate or colliding ADR / NC identifiers.
```

The machine fingerprint is Linux WSL2 on the AMD Ryzen 5 5500 described above.
`pip freeze` included the six pinned packages and the editable package at
`462db490eb63711a30a4e74d72527088840e08b0`.

### Step 6: NC-021

```text
register:  Full test-suite size | 771
collection: 771 tests collected in 0.86s
```

The register and collection count agree. The prescribed full-suite command did
not match the runbook expectation:

| Expected | Observed |
| --- | --- |
| 770 passed, 1 skipped | 760 passed, 10 failed, 1 skipped |

The skip was the expected unreachable `calibration-data` ref. The ten failures
were all `tests/test_file_snapshots.py` cases. This machine reports
`safe.bareRepository=explicit` from Git's command-line configuration; those
tests create and read temporary bare repositories, which Git rejects under
that policy. No project file was changed.

For diagnosis only, the identical suite with the process-local compatibility
setting `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository
GIT_CONFIG_VALUE_0=all` completed as:

```text
770 passed, 1 skipped in 10.48s
```

### Step 7: before-and-after unit probe

| Probe | `main-tree` at `e39af50` | PR tree at `462db49` |
| --- | --- | --- |
| `tree:` | `main-tree` | `repo` |
| vectorizer `mean_T1` | `0.0001551924205171878` | same |
| `extract, no unit` | `[1.0, 1.0]` | `TypeError`: missing keyword-only `coherence_unit` |
| `extract, unit s` | unexpected-keyword `TypeError` | `[0.00015463477053168084, 0.0002832878265588423]` |
| `survey, no unit` | `[0.0001820797139959751, 0.0003125140909431279]` | missing-unit `TypeError` |
| `survey, unit us` | unexpected-keyword `TypeError` | `[0.0001820797139959751, 0.0003125140909431279]` |
| `0.5 us, unit us` | unexpected-keyword `TypeError` | `[0.046866212922495265, 0.046866212922495265]` |

Every observed value matches the round-1 runbook.

### Step 8: NC-039

```text
gap us: ['-1.8032599909555808e-05', '-3.7973319935037924e-04']
gap s:  ['-1.8032599909555808e-05', '-3.7973319935037924e-04']
register: (-1.8032599909555808 x 10^-5, -3.7973319935037924 x 10^-4)
```

Both paths reproduce the registered components digit for digit.

### Step 9: focused tests and mutation

```text
baseline tests/training/test_targets.py: 19 passed in 0.06s
mutation diff: 1 file changed, 1 insertion(+), 1 deletion(-)
mutated tests/training/test_targets.py: 2 failed, 17 passed in 0.12s
post-restore git status --porcelain: empty
```

The runbook's unit-ignoring mutation was applied and killed exactly two tests,
then restored.

### Steps 10-11: scope and cleanup

```text
src/superconducted/training/targets.py | 46 ++++++++++---
tests/test_parameterization.py         | 14 ++--
tests/training/test_targets.py         | 117 +++++++++++++++++++++++++++++----
3 files changed, 151 insertions(+), 26 deletions(-)
```

The locked-module diff for `fuzzy/tsk.py` and `channels/kraus.py` was empty.
The temporary `main-tree` worktree was removed; `git worktree list` retained
only the verification clone.

## Record Context

This evidence file is added after the measured implementation commit. It
records the run for `462db490eb63711a30a4e74d72527088840e08b0` and does not
claim that the documentation-only evidence commit was part of the measured
tree.
