# PR #29 verification · Burak's desktop · 2026-08-27

**Commit tested**: `cdbcc47dc77fd0d271d319d766a9cb3f52c02e6d`
**Branch**: `feature/baha-adr-012-closure`
**Verdict**: VERIFIED
**Runbook**: second runbook posted on PR #29, after the first was withdrawn
(see "Runbook history" below)

## Machine

| Field | Value |
| --- | --- |
| Host | `DESKTOP-2CST637` |
| OS | Microsoft Windows NT 10.0.19045.0 |
| PowerShell | 5.1.19041.6456 (Desktop edition) |
| Python | 3.12.10 |
| pytest | 9.0.3 |
| Install | fresh clone, fresh venv, `requirements.txt` + `requirements-dev.txt`, `pip install -e . --no-deps` |
| Run window | 2026-08-27 20:51:27 → 21:15:03 |

CPU and RAM are not recorded here: `Start-Transcript` does not capture them and
this run did not query them. They are deliberately **not** copied from the PR #34
record, even though the OS build matches, because an unverified value in a
verification document is the exact failure mode `docs/numerical-claims.md`
exists to prevent.

## Results

All eleven rows passed. `Expected` is reproduced from the runbook as posted.

| # | Check | Expected | Observed |
| --- | --- | --- | --- |
| 1 | Step 2 commit hash | head of PR #29 | `cdbcc47` |
| 2 | `ruff check .` (branch) | identical to `main` | `All checks passed!` |
| 3 | `ruff format --check .` (branch) | identical to `main` | `35 files already formatted` |
| 4 | `mypy --strict src/superconducted` (branch) | identical to `main` | `Success: no issues found in 22 source files` |
| 5 | `pytest tests/ -q` (branch) | identical to `main` | `166 passed` |
| 6 | Steps 4 and 5 agree | yes | yes — `main` produced the same four outputs |
| 7 | 6A · locked-entry invariant | `PASS` | `PASS - no locked entry is provisional` |
| 8 | 6B · ADR-006 / 010 / 012 label | all three `**Decision**` | all three `**Decision**` |
| 9 | 6C · NC-021 vs collected count | the two numbers are equal | `166 tests collected` and NC-021 = `166` |
| 10 | 6D · removed-lines on the dated snapshot | `0` | `62  0  docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` |
| 11 | 6E · `.py` files changed vs `main` | `0` | `0` |

Rows 2–5 were confirmed against `main` in the same session; both sets of four
gate outputs are byte-identical in the transcript.

## What was merged versus what was verified

This run tested `cdbcc47`. The branch head at merge was
`adfbece993c3d549cccc2674413f2c0ad464bb58`, which adds only the screenshot files
in `docs/evidence/pr29-burak-desktop/` — `8 files changed, 0 insertions(+),
0 deletions(-)`. No tracked text differs between the verified commit and the
merged commit, so this verdict covers the merged content.

Recording the gap deliberately: a commit landing between verification and merge
is the shape by which unverified content reaches `main`, and it is worth seeing
in the record even when, as here, it is inert.

## Runbook history

The first runbook for this PR produced a `NOT VERIFIED` verdict that was a false
positive. Two of its rows could not both hold once `main` moved: one pinned an
absolute test count sourced to `NC-021`, another required parity with `main`, and
`NC-021` had gone stale by 17 tests. A third row passed while concealing a real
defect, because its `Expected` prose was wrong.

Auditing that produced issues #40 and #41, both fixed in this PR, and the
rewritten runbook used here — in which every expectation is differential,
self-consistent, or a `PASS`/`FAIL` invariant, and none can go stale.

## Notes

Two friction points in the runbook, neither affecting the result:

1. **Multi-command paste.** Pasting consecutive `python -c '...'` blocks together
   caused PowerShell to concatenate them and strip the single quotes, producing
   `SyntaxError: invalid syntax` on the first attempt. The commands were re-run
   individually and produced correct output. Future runbooks should carry one
   command per block, or ship the checks as a committed script.
2. **`SyntaxWarning: invalid escape sequence`.** The one-liners reached the PR
   body with single backslashes (`\d`, `\*`, `\s`), so Python 3.12 warned twice
   per invocation. The results are unaffected — an invalid escape falls back to a
   literal backslash, which is the intended regex — but the warnings look like
   failures to a verifier. Use raw strings or doubled backslashes next time.

Neither is a defect in PR #29.

## Full transcript

`pr29-rerun-transcript.txt`, attached to the verification comment on PR #29.
Screenshots for each step are in `docs/evidence/pr29-burak-desktop/`.
