# Issue #57 follow-up verification · Burak desktop · 2026-11-09

**Measured source tree**: `main` at `d929424a` plus the documentation-only PR #147 changes
**Scope**: Follow-up verification of issue #57 contract surfaces after PR #69 merge and ADR-027 acceptance.

## Machine and toolchain

| Field | Value |
| --- | --- |
| Host OS | Linux 6.18.54.1-microsoft-standard-WSL2 |
| Python | 3.12.3 |
| pytest | 9.0.3 |
| Qiskit | 2.4.1 |
| Qiskit Aer | 0.17.2 |

## Commands and outcomes

| Command | Outcome |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/training/test_targets.py tests/training/test_aer_pin.py tests/training/test_parameters.py tests/training/test_types.py tests/test_interfaces.py` | `93 passed in 0.91s` |
| `.venv/bin/ruff check src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py tests/training tests/test_interfaces.py` | All checks passed |
| `.venv/bin/ruff format --check src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py tests/training tests/test_interfaces.py` | 13 files already formatted |
| `.venv/bin/mypy --strict src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py` | Success, no issues in 7 source files |

## Full-suite status

A full run (`.venv/bin/python -m pytest -q`) collected and passed all `1,138` tests in `176.66s`.

## Conclusion

Issue #57's contract-related repository surfaces passed targeted verification. ADR-027 is already Accepted on `main`, and the 2026-10-21 advisor record includes the D1/D3/D4 ratification and `TSKTrainer`/value-type owner read. This verification does not claim that every Issue #57 checkbox was met without deviation; the [closure audit](https://github.com/SuperconducTED/superconducted-noise-engine/issues/57#issuecomment-6750630369) assesses them and tracks the `types.py` fix in #148.

## Follow-up verification, 2026-11-12

The original run did not record the host name, NumPy, Ruff or mypy versions, or how the environment was installed. The repository's `requirements.txt` and `requirements-dev.txt` specify pinned dependencies; installation from those files for the original run has not been verified.

The targeted checks were re-run at PR #147 head `6fca3ffb` on host `DESKTOP-2CST637`, Linux `6.18.58.1-microsoft-standard-WSL2`, using the existing repository `.venv`. Its observed versions were Python 3.12.3, NumPy 2.4.4, pytest 9.0.3, Qiskit 2.4.1, Qiskit Aer 0.17.2, Ruff 0.15.12 and mypy 1.20.2; the listed package versions match the requirements pins. These observations do not establish the original run's missing provenance.

From the PR worktree root, with `VENV` set to the existing repository `.venv`:

```bash
PYTHONPATH=src "$VENV/bin/python" -m pytest -q -p no:cacheprovider tests/training/test_targets.py tests/training/test_aer_pin.py tests/training/test_parameters.py tests/training/test_types.py tests/test_interfaces.py
"$VENV/bin/ruff" check src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py tests/training tests/test_interfaces.py
"$VENV/bin/ruff" format --check src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py tests/training tests/test_interfaces.py
"$VENV/bin/mypy" --strict src/superconducted/training src/superconducted/interfaces.py src/superconducted/types.py
```

Results: 93 passed in 2.03s; Ruff check passed; 13 files already formatted; mypy found no issues in 7 source files. The full suite was not re-run for this follow-up.