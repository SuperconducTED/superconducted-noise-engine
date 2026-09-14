# Issue #57 verification · Burak's desktop · 2026-09-05

**Implementation commit measured**: `37e1ba05fbe9961e1ca94bd9bb5fdbadf6c51808`
**Branch**: `feature/issue-57-training-target`
**Verdict**: VERIFIED for the implementation and numerical measurements below.

## Machine

| Field | Value |
| --- | --- |
| Host | `DESKTOP-2CST637` |
| OS | Linux 6.18.33.2-microsoft-standard-WSL2 |
| Python | 3.12.3 |
| pytest | 9.0.3 |
| Qiskit | 2.4.1 |
| Qiskit Aer | 0.17.2 |
| Calibration archive ref | `origin/calibration-data` at `1accf05c0c8ae8174c43d22c70fb46f6147ac9f9` |

## Results

| Check | Observed |
| --- | --- |
| Candidate test suite after the Issue #60 split | `356 passed in 15.19s` |
| `ruff check` | `All checks passed!` |
| `ruff format --check` | all candidate Python files already formatted |
| `mypy --strict src/superconducted` | `Success: no issues found in 25 source files` |
| Candidate test count | 356 collected and passed; direct measurement at `37e1ba0` (NC-021) |
| Aer conformance | Maximum SuperOp matrix-entry difference $9.992007221626409 \times 10^{-16}$ across 4 T1/T2 cases at 24 ns and 60 ns, below $10^{-12}$ |
| 3x3x3 Gaussian parameter accounting | 234 total: 216 consequent plus 18 premise |
| Gate-bearing fixture | SHA-256 `02d27ff1bf6af8bb06e0bce886454160926cb3adc1466e536245e03431487082`; 156 `sx` records at 24 ns; 155 usable targets; q72 `t1_missing` |
| Second gate-duration measurement | archive snapshot `20260513T143529000000Z`: 156 `sx` records, all 24 ns |
| Locked modules | no diff from `origin/main` for `src/superconducted/fuzzy/tsk.py` or `src/superconducted/channels/kraus.py` |

## Reproduction

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --collect-only -q -o addopts=''
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --strict src/superconducted
.venv/bin/python scripts/check_ids.py
git diff origin/main -- src/superconducted/fuzzy/tsk.py src/superconducted/channels/kraus.py
```

NC-035 through NC-040 contain the exact target, fixture, parameter-count, and
device-error calculations and their sources.

## Outstanding human approvals

This technical verification does not constitute required review approval.
Issue #57 remains pending approval by `@BurakOztekin` and `@bengisucvd`, plus
Dr. Akba's out-of-band read of the `interfaces.py` and `types.py` contracts.
ADR-027 remains Open until those decisions are recorded.
---

## As of 2026-09-08 · superseded in part · re-run required

The rows above are correct **as measured**, at `37e1ba0`, and are left unedited.
They no longer describe the merged tree. Four commits landed after that
measurement and before PR #69 merged:

| Commit | Change |
| --- | --- |
| `75c9daa` | `TSKTrainer` docstring gains the full FR-2 contract |
| `5397bb6` | ADR-027's three missing FR-1 clauses; `__init__.py` counts and `TSKTrainer` export; 4 new tests |
| `adc2cd3` | NC-021 356 → 360 |
| `2d66f7a` | Merge of PR #69 into `main` |

**What changed numerically**: the full suite is **360**, not 356. The delta is
`+4` — three in `tests/test_interfaces.py` (the section 9.2 immutability round
trip, the `isinstance` narrowing rule, and a pin on the package docstring's ABC
and value-type counts) and one in `tests/training/test_parameters.py` (section
9.1's unshared-membership case, `premise == 8`). NC-021 records the same figure
at `5397bb6`, and merged `main` at `2d66f7a` was re-collected at 360.

**Everything else above still holds and was not re-derived by the new commits**:
the Aer maximum SuperOp difference, the 234 parameter count, and the fixture's
SHA-256, byte size, 156 `sx` records, 352 `cz` records and 155 usable targets
are all untouched by the four commits, which added no measurement of their own.

**Why this is not a verification.** The 360 was measured on the lead's laptop.
Under the project's convention Burak's desktop is the single source of truth and
laptop results are provisional, so the four added tests have **not** been run on
the canonical machine. This section records the drift and the reason for it; it
does not certify the new figure.

**Re-run needed** on `DESKTOP-2CST637` at `2d66f7a` (or later `main`), reporting
the collected and passed counts. Expect them to match NC-021's 360 and to differ
from the 356 above by exactly the four named tests — state the difference
against NC-021's commit rather than an absolute, so a stale row surfaces as a
visible mismatch.

---

## As of 2026-09-08 · canonical desktop re-run complete

The required re-run was completed on `DESKTOP-2CST637` against the PR #69 merge
commit `2d66f7ab1d25e7852ad4807fbfdaf9f7aab0b8d1`. To ensure the command imported
that candidate's source tree rather than the editable checkout, it was run with
`PYTHONPATH` set to the candidate worktree's `src/` directory.

| Check | Observed |
| --- | --- |
| Full test suite | `360 passed in 13.12s` |
| Candidate test count | 360 collected |

The collected and passed counts match NC-021's 360 at `5397bb6`; the four-test
delta from the original 356 measurement is therefore verified on the canonical
desktop. This supersedes only the preceding **re-run needed** status. The
original measurements remain their recorded values at `37e1ba0`.
