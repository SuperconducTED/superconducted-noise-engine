# PR #32 verification · Burak's desktop · 2026-08-20

**Commit tested**: `f95a5b209ee4a9b19836558fc90a74996c837923`
**Branch**: `feature/mert-cycle2-reconciliation`
**Verdict**: VERIFIED

## Machine

| Field | Value |
| --- | --- |
| OS | Ubuntu WSL2 (Linux 6.18.33) |
| CPU | Desktop Processor |
| Python | Python 3.12.3 |
| Install | fresh clone, fresh venv, requirements.txt + requirements-dev.txt |

## Results

| Check | Expected | Observed | Outcome |
| --- | --- | --- | --- |
| ruff check . | All checks passed! | All checks passed! | match |
| ruff format --check . | 34 files already formatted | 34 files already formatted | match |
| mypy --strict src/superconducted | no issues in 22 source files | Success: no issues found in 22 source files | match |
| pytest tests/ -q | 152 passed *(runbook figure · wrong, see below)* | 149 passed, 149 collected | resolved · observation correct, expectation corrected to 149 |
| "mean-aggregates counts" hit count | 2, both in ADR-016 | 2, both in ADR-016 | match |
| cycle-2 plan diff versus main | additions only, no removed lines | additions only, no removed lines | match |

## Resolution of the pytest count mismatch

The runbook posted to this PR pre-filled `152 passed` as the expected
result. That figure was wrong and had no source. The suite contains
**149** tests.

Confirmed by re-running collection on both revisions:

```
git checkout main         && python -m pytest tests/ -q --collect-only   # 149 collected
git checkout 46d90bcb     && python -m pytest tests/ -q --collect-only   # 149 collected
```

Both return 149. This PR is documentation-only and adds, removes, and
modifies no test, so the count is expected to be identical on the branch
and on `main` — which is what was observed. **There is no regression.**

The row is kept rather than overwritten so the audit trail shows a wrong
expectation was issued and caught. The desktop procedure worked exactly
as intended: the runbook instructed the verifier to report any
difference without fixing it, and that is what happened. The corrected
count is now registered as `NC-021` in `docs/numerical-claims.md` so the
next runbook can cite a source instead of a recollection.

## Note on line numbers

Earlier revisions of this record cited the two surviving
`mean-aggregates counts` hits at absolute lines 290 and 301. Those
positions are branch-local: `docs/decisions.md` shifts whenever an ADR
entry is added above them, and `main` has since moved past the revision
this branch was cut from. The durable claim is the invariant — **exactly
two hits, both inside the ADR-016 entry, none inside ADR-018** — so the
absolute numbers have been dropped.

## Evidence

Ten terminal screenshots covering Steps 5 through 7 are attached to
BurakOztekin's approving review on PR #32.

No `pr32-transcript.txt` was produced; the `Start-Transcript` output
from Step 1 of the runbook was never posted. The screenshots are
therefore the primary evidence for this run. Archiving them into this
directory — as PR #36 did for `docs/evidence/adr-010-closure/` — is
tracked as a follow-up.

---

## As of 2026-09-07 · screenshots archived

The 2026-08-20 record above is left as written. This section records what
changed since.

**The ten screenshots are now in this directory.** The Evidence section above
says archiving them "is tracked as a follow-up" — that follow-up was started on
`feature/mert-cycle2-reconciliation` (commits `54f46ca`, `960289b`), which was
never merged, so the images existed only on that branch while this record
pointed at a review attachment. They are committed here byte-for-byte: every
archived file's blob hash matches the blob on that branch.

**Renamed to the step convention.** They arrived as `01. Image.png` …
`10. Image.png`. Every sibling record (`pr29-burak-desktop`,
`pr33-burak-desktop`, `pr34-burak-desktop`, `adr-010-closure`) names screenshots
by the runbook step they show, so these were renamed to match, against the step
list in the runbook posted to PR #32:

| was | now | shows |
| --- | --- | --- |
| `01. Image.png` | `Step 00 to Step 04.png` | tool versions, clean room, `script` start, clone, `git checkout f95a5b2`, `rev-parse`, venv |
| `02.`–`07.` | `Step 05 Part 1.png` … `Step 05 Part 6.png` | install and fingerprint: dependency resolution, wheel install, `pip install -e . --no-deps`, then `python3 --version`, `/etc/os-release`, `/proc/cpuinfo`, `pip freeze` |
| `08. Image.png` | `Step 05 Part 7 and Step 06 Part 1.png` | tail of `pip freeze`, then three of the four guards — `ruff check`, `ruff format --check`, `mypy --strict` — and the start of `pytest` |
| `09. Image.png` | `Step 06 Part 2 and Step 07.png` | `149 passed`, then both content checks: the `mean-aggregates counts` hit count and the cycle-2 plan diff |
| `10. Image.png` | `Step 08.png` | `Script done.` |

**Two corrections to the record above, from reading the screenshots.**

First, the Evidence section says the ten cover "Steps 5 through 7". They cover
**Steps 0 through 8**: `Step 00 to Step 04.png` shows the prerequisites, clean
room, clone, commit pin and virtual environment, and `Step 08.png` shows the
recording being stopped. Steps 5 to 7 are the bulk, not the whole.

Second, it says "No `pr32-transcript.txt` was produced". That is true of that
filename, but a transcript **was** recorded. The runbook posted to PR #32 is
PowerShell (`Start-Transcript -Path C:\scted-verify\pr32-transcript.txt`), and
the run was done on Ubuntu WSL2 using the equivalents — `script
pr32-final-transcript.txt`, visible starting in `Step 00 to Step 04.png` and
closing with `Script done.` in `Step 08.png`. So the recording exists under a
different name on the verifier's machine; what the record above gets right is
that it was never posted, which is why the screenshots remain the primary
evidence.
