# PR #103 verification - Burak's desktop - 2026-10-04

**Implementation commit measured**: `9e180675311c354541873b6ee82b5142dedce8c2`
**Branch**: `feature/issue-74-smoke-transpilation`
**Verdict**: VERIFIED at the measured code head for the checks below.

## Environment

- Linux WSL2 on AMD Ryzen 5 5500 (12 logical CPUs)
- Python 3.12.3
- numpy 2.4.4, qiskit 2.4.1, qiskit-aer 0.17.2
- pytest 9.0.3, ruff 0.15.12, mypy 1.20.2

The run used a clean single-branch clone and a fresh virtual environment built
from `requirements.txt` and `requirements-dev.txt`.

## Results

| Check | Observed |
| --- | --- |
| Collection | `712 collected` |
| Test suite | `711 passed, 1 skipped` |
| `ruff check .` | passed |
| `ruff format --check .` | passed |
| `mypy --strict` | passed |
| `mypy --strict src/superconducted` | passed |
| `python scripts/check_ids.py` | passed |
| `git diff --check` | passed |

The sole skipped test is the expected archive test: the clean single-branch
clone does not fetch the `calibration-data` ref. The collection total matches
NC-021.

## Runtime Verification

- Before the fix, sx-only noise produced `{'0': 118, '1': 138}`, the same as
  the noiseless run.
- With the new ordering, sx-only noise produced `{'0': 256}`; the noiseless run
  remained `{'0': 118, '1': 138}`.
- `--qubits 2` completed successfully. `--qubits 3` raised the expected width
  `ValueError` before simulation.
- On the ibm_fez fixture, the new ordering installed `rx` and `sx` errors with
  4 errors for qft(2) and 6 errors for qft(3), without a warning. The old
  ordering installed no errors and warned.

## Mutation Verification

- Removing the `main()` width guard failed the selected pre-simulation test.
- Changing the width comparison from `>` to `>=` failed the selected boundary
  test.
- Replacing `nm.prepare(transpiled_circuit.copy())` with
  `nm.prepare(circuit.copy())` failed the copy-isolation test.

The runbook's third mutation still names `member.prepare(...)`, while the
measured source uses `nm.prepare(...)`; its literal command made no diff. The
equivalent current-source mutation above was used and killed. Every mutation
was restored, and the source tree was clean afterwards.

## Record Context

This evidence file is added after the measured code commit. It records the
results for `9e180675311c354541873b6ee82b5142dedce8c2` and does not claim that
the documentation-only commit containing this record was part of the measured
test tree.

## Reviewer correction, appended 2026-10-06

Appended by @mertefesensoy during the review of PR #103. Everything above is
Burak's record as committed in `1662ddb` and is left unchanged, including its
verdict.

The Mutation Verification paragraph says the runbook's third mutation "still
names `member.prepare(...)`" and that "its literal command made no diff". The
runbook does not say that. Its comment,
`https://github.com/SuperconducTED/superconducted-noise-engine/pull/103#issuecomment-5969089080`,
has never been edited (`created_at` and `updated_at` are both
`2026-10-03T12:19:04Z`), and line 198 of its body reads:

```bash
sed -i 's/nm.prepare(transpiled_circuit.copy())/nm.prepare(circuit.copy())/' scripts/first_ensemble_run.py
```

Applied to `scripts/first_ensemble_run.py` at `9e18067`, that command changes
exactly one line, line 171. The mutation recorded above as "equivalent" is
therefore the runbook's own third mutation, run as written, and the result
stands: the mutation was killed. The runbook's Step 11 and Step 12 Python
snippets are where `member.prepare(...)` appears (body lines 238 and 285).
