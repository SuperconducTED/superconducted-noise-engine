# PR #140 desktop verification (Issue #125, offline half)

Tree tested: `2aea1e1850de98b673e1b6c60bd0a5ac5c7d9aa6` (merge-base `5c98f264`), as the runbook requires.
Machine: WSL2 (kernel 6.18.54.1-microsoft-standard-WSL2), AMD Ryzen 5 5500, 12 threads, Python 3.12.3, 6.0 GiB available (7.7 GiB total). Full `pip freeze` and `lscpu` are in `steps4-7.log`.

## Results

| Step | Expected | Observed |
| --- | --- | --- |
| 0 | `safe.bareRepository` = `command explicit` | **Not set** (no output); `free` available 6.0 GiB, below the ~8 GB guide. Reported, not stopped. |
| 2 | SHA `2aea1e1`, merge-base `5c98f264` | match |
| 3 | six pins identical | match |
| 5 | ruff, format, `mypy --strict`, `check_ids` clean | all clean (103 files formatted, 49 source files) |
| 6 | collected - 1 passed, 1 skipped, 0 failed | 1095 collected, 1094 passed, 1 skipped (`calibration-data ref 3d1569d is unreachable`) |
| 7 | both commits exist | `commit`, `commit` |
| 8 | controls exit 0; dry run exit 0; truth1 and truth2 true | controls exit 0 (1m14s); dry run exit 0 (18m05s real); `truth1: true`, `truth2: true`. No hang, no `MemoryError`. |
| 9 | every MUST MATCH row same/pass; exit 0 | all 15 rows hold; `RESULT: all must-match rows hold`; exit 0 |
| 10 | `src` diff and `git status` empty | both empty |

## REPORTED (no expectation)

- The four TSVs and `selection.json` are byte-identical to the laptop reference: Aer samples identically on Windows and on WSL2 for this run.
- `criteria.json` differs in 13 lines, all in the last 1-3 digits of floats (for example `arm_b_max_z` 2.682505763104636 vs 2.682505763104673; `mean_abs_error` 0.010234712281432959 vs 0.010234712281432995). No boolean, count or pass/fail value differs. Likely summation order in the numpy build; not tested further.
- `manifest.json` keys that differ: `versions`. `controls.json` keys that differ: none.

No row failed; nothing was corrected.
