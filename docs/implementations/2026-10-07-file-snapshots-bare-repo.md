# 2026-10-07: file-snapshots-bare-repo

## Problem / Motivation

Burak's desktop verification of PR #107 (comment `6028000419`, recorded in
`docs/evidence/pr107-burak-desktop/2026-10-07-verification.md` on
`mert/feature-target-fn-units`) expected `770 passed, 1 skipped` and observed
`760 passed, 10 failed, 1 skipped`. All ten failures were
`tests/test_file_snapshots.py` cases. His machine supplies
`safe.bareRepository=explicit` from Git's command-line configuration, and his
diagnostic rerun with the process-local override `safe.bareRepository=all`
passed. He changed no project file.

That test is the end-to-end check of `scripts/file_snapshots.sh` (PR #50's
blocker). Its `sandbox` fixture creates a bare `origin.git`, and the test then
read that bare repository with the module's `_git(...)` helper using the bare
directory as the working directory, for example
`_git("show", "calibration-data:ledger/2026-09.tsv", cwd=origin)`. There were
seven such `cwd=origin` reads. Git's own documentation (git-config(1),
`safe.bareRepository`, as shipped with Git 2.53.0.windows.2 on this machine)
says that under `explicit`, Git only works with bare repositories specified via
the top-level `--git-dir` option or the `GIT_DIR` environment variable. A bare
repository found from the working directory is refused:

```text
fatal: cannot use bare repository '.../origin.git' (safe.bareRepository is 'explicit')
```

The cost is not the ten red rows alone. Every desktop verification on a
hardened machine has to explain them away, and they sit in the one test that
guards the poller's filing step, so a real regression there would hide among
them.

**Reproduced before the fix**, on Windows at `e39af50` (main, unmodified), with
`C:\pvci\Scripts\python.exe` (Python 3.12.10) and `PYTHONPATH=<worktree>/src`:

| Run | Result |
| --- | --- |
| default git config | 10 passed |
| `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=explicit` | 10 failed, 10 "cannot use bare repository" messages |

Every one of the ten failures is a `CalledProcessError` (exit 128) at a
`cwd=origin` read: nine at `_ledger`'s `git show`, one
(`test_a_missing_digest_refuses_to_file_anything`) at `_tree`'s `git ls-tree`.
In every case the test's assertion on the script's own exit status had already
passed. See "Is the production script implicated?" below for why that matters.

## What changed

| File | One-sentence description |
| --- | --- |
| `tests/test_file_snapshots.py` | Adds `_origin_git` and `_origin_git_bytes`, which run git with `--git-dir=<origin>`, and routes the seven reads of the bare origin through them; no assertion and no other call changes. |
| `docs/implementations/2026-10-07-file-snapshots-bare-repo.md` | This document. |

The code change is commit `1748cd4`. This document is a following docs-only
commit that names it.

## Implementation approach

**Name the bare repository, never discover it.** Two thin wrappers mirror the
existing `_git` and `_git_bytes` helpers:

```python
def _origin_git(*args: str, origin: Path) -> str:
    return _git(f"--git-dir={origin}", *args, cwd=origin)

def _origin_git_bytes(*args: str, origin: Path) -> bytes:
    return _git_bytes(f"--git-dir={origin}", *args, cwd=origin)
```

Contract: `args` is a git subcommand and its arguments; `origin` is the absolute
path of a bare repository; the return value is the command's stdout (decoded as
UTF-8, or raw bytes); a non-zero exit raises `CalledProcessError`, exactly as
`_git` does. No side effects beyond the git command itself, and every command
routed through them is a read (`show`, `ls-tree`, `log`).

The seven call sites change only the function name and the keyword
(`cwd=origin` becomes `origin=origin`):

| Line (after) | Caller | Command |
| --- | --- | --- |
| 253 | `_ledger` | `show calibration-data:ledger/<month>.tsv` |
| 266 | `_state_index` | `show calibration-data:health/state-index.tsv` |
| 279 | `_tree` | `ls-tree -r --name-only calibration-data` |
| 284 | `_subject` | `log -1 --format=%s calibration-data` |
| 333 | `test_duplicate_collision_and_new_through_a_real_branch_switch` | `show` of each archived copy, as bytes |
| 386 | `test_ledger_appends_across_polls_in_the_same_month` | `show calibration-data:ledger/2026-09.tsv` |
| 412 | `test_a_backfilled_re_read_is_not_a_collision` | `show` of the archived copy, as bytes |

**What is deliberately untouched.** The fixture's `git init --bare <path>`
creates the repository rather than discovering it, and the seed and source
repositories reach it through `git remote add origin <path>` and an ordinary
push or fetch over the local transport. Both worked under the policy in every
strict run, before and after the fix, so they are left as they were.

**Is the production script implicated?** No, on two independent grounds.

*Static.* Every git invocation in `scripts/file_snapshots.sh` and the
`scripts/push_with_retry.sh` it calls, with its working directory:

| Call | Working directory |
| --- | --- |
| `file_snapshots.sh:72` `git fetch` | the caller's: the source checkout (`actions/checkout` on CI, `sandbox["src"]` in the test), a non-bare repository |
| `file_snapshots.sh:75` `git worktree add` | the same |
| `file_snapshots.sh:76` `cd "$DATA_WORKTREE"` | a linked worktree that line 75 just created, non-bare |
| `file_snapshots.sh:204-210` `git add`, `git diff --cached`, `git commit` | `$DATA_WORKTREE` |
| `push_with_retry.sh:30-41` `git push`, `rev-parse`, `fetch`, `reset`, `cherry-pick` | inherited: `$DATA_WORKTREE` |

The only bare repository involved is the remote, which the script names as
`$DATA_REMOTE` (a GitHub URL on CI, a local path in the test) and reaches by
transport. The script never runs git with its working directory inside a bare
repository.

*Empirical.* `_run` hands the script `dict(os.environ)` as its environment, so
in a strict run the three `GIT_CONFIG_*` variables reach every git command the
script and `push_with_retry.sh` execute. In the pre-fix strict run, the nine
tests that assert
`result.returncode == 0` passed that assertion before failing at a read, and
`test_a_missing_digest_refuses_to_file_anything` passed its exit-1 and
"missing" assertions first. After the fix the strict run passes every
assertion, including all of those on what reached origin: the script's fetch,
worktree, commit and push work end to end under the policy against a local bare
origin. The full suite under the policy also passes (Verification).

## Mathematical / Statistical details

N/A, purely structural. No formula, threshold or estimator is involved, and no
test is added or removed.

## Design decisions

**`--git-dir=<absolute path>` over the alternatives.** `git -C <origin>
--git-dir=.` works too but adds a token and a relative path whose meaning
depends on `-C` ordering. A `GIT_DIR` environment variable would also satisfy
the policy, but it is invisible in the argv that a `CalledProcessError` prints,
so a failing read would no longer say which repository it read.

**Two wrappers rather than a `git_dir=` keyword on `_git`.** `_git` keeps 15
direct call sites, every one with a non-bare working directory (the fixture's
`init --bare` runs from `tmp_path`). Leaving its contract alone keeps those
untouched, makes every bare read visible by name at its call site, and puts the
load-bearing token in exactly one place per helper, which is what the mutation
check below strips. `_git_bytes` is now reached only through
`_origin_git_bytes`; it stays as the bytes primitive, mirroring `_git`.

**The working directory stays at `origin`.** With `--git-dir` given, git does
no discovery, so the working directory is irrelevant to correctness. Keeping it
makes the flag the only difference from the old call: the M0 mutation (flag
removed) is byte-for-byte the pre-fix behaviour, so its result is a clean
before/after comparison. It also shows the explicit form works from inside the
bare directory, the exact place discovery used to be refused.

**No `safe.bareRepository=all` override**, in the tests or in a conftest. It
would make the ten failures disappear on Burak's desktop, and it would equally
hide a production-script change that started discovering a bare repository.
The fix has to be in how the test addresses origin.

**Not adopted, flagged for a decision: enforce the policy in the test run.** CI
on `ubuntu-latest` does not set `safe.bareRepository`, so CI cannot catch a
future `cwd=<bare repo>` read; only a hardened machine would. Setting
`explicit` in the environment `_git` and `_run` pass to git would make every
run (CI included) as strict as Burak's desktop, and would extend that strictness
to the script under test. That changes test behaviour, which this change was
scoped not to do, so it is left as a recommendation.

### Does this explain the Windows ".venv 8"?

No. NC-021's chain records that "8 `tests/test_file_snapshots.py` cases fail on
Windows" from the repository `.venv` (round 2 of PR #70, `e3c4ea8`,
`383 passed, 8 failed` of 391) and reads them as an environment artefact,
because they "did not reproduce in a clean interpreter at a short path"
(`7ec173f`, and again in `docs/implementations/2026-09-10-scheduled-calibration-sweep.md`).
`safe.bareRepository=explicit` is not that cause. Three discriminators, each
measured on 2026-10-07:

1. **Count.** The policy fails every case, because every case reads the bare
   origin. Extracted with `git archive e3c4ea8` and run with `C:\pvci`, the
   `e3c4ea8` file has 10 cases: 10 passed under default config, and 10 failed
   with 10 "cannot use bare repository" messages under `explicit`. An 8-of-10
   pattern at that commit cannot come from this policy.
2. **Symptom.** The round-2 block in
   `docs/implementations/2026-09-05-pipeline-health-dashboard.md` says "the
   sandboxed digest subprocess returns `collision-unreadable` where the
   assertion expects `collision`". Comparing a ledger decision means the
   `git show` on the bare origin had succeeded. Under the policy that read
   itself fails (exit 128) before any ledger content is compared.
3. **Environment.** `git config --show-origin --get-regexp '^safe\.'` returns
   nothing (exit 1) on this machine, and no `GIT_CONFIG_*` variable is set. The
   repository `.venv` (Microsoft Store Python 3.13.14) passes all 10 cases
   today under default config, and fails 10 with 10 refusals under `explicit`,
   the same as `C:\pvci`: the policy's effect does not depend on the
   interpreter, whereas the historical failure did.

The original cause stays unidentified. It no longer reproduces from the
repository `.venv` at `e39af50`, so it cannot be investigated further from this
machine today. NC-021's existing reading of it is neither confirmed nor
contradicted here, and the register is not edited for it.

### NC-021

This change adds no test and removes none. The registered collection command
gives `766` at `e39af50` (before) and at `1748cd4` (after), so NC-021's value
`766` needs no new value.

One clause will need a decision at merge time. The row ends "only `docs/`
changes after that commit" (`f2641ff`). That holds on `main` today; once this
branch merges, `tests/test_file_snapshots.py` has changed after `f2641ff`, so
the clause stops being literally true although the count still is. The
`2026-10-06-pr103-final-review-fixes.md` precedent handled the same situation by
re-pinning the row at the new commit in a docs-only commit. That is not done
here, because PRs #107 and #111 also rewrite NC-021 and every further edit to
that row is another conflict for them.

## Verification

Machine: Windows 11, Git 2.53.0.windows.2, `C:\pvci` Python 3.12.10 with
pytest 9.0.3, ruff 0.15.12 and mypy 1.20.2, matching `requirements-dev.txt`.
Commands run in Git Bash from the repository root with
`export PYTHONPATH="$(pwd)/src"`, and `python` meaning `C:\pvci\Scripts\python.exe`.

**The two modes.**

```bash
python -m pytest tests/test_file_snapshots.py -q -p no:cacheprovider -o addopts=""
```

```bash
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=explicit python -m pytest tests/test_file_snapshots.py -q -p no:cacheprovider -o addopts=""
```

| Commit | Default | `explicit` |
| --- | --- | --- |
| `e39af50` (before) | 10 passed | 10 failed (10 refusals) |
| `1748cd4` (after) | 10 passed | 10 passed |

**Mutation check.** A scratch script edits the committed test file, runs it,
and restores it byte for byte (it confirmed the restore).

| Mutation | Default | `explicit` |
| --- | --- | --- |
| M0: strip `--git-dir` from both helpers | 10 passed | 10 failed, 10 refusals |
| M1: revert line 253 (`_ledger`) | not run | 9 failed, 9 refusals |
| M2: revert line 266 (`_state_index`) | not run | 2 failed, 2 refusals |
| M3: revert line 279 (`_tree`) | not run | 7 failed, 7 refusals |
| M4: revert line 284 (`_subject`) | not run | 4 failed, 4 refusals |
| M5: revert line 333 (archived bytes, first test) | not run | 1 failed, 1 refusal |
| M6: revert line 386 (ledger header count) | not run | 1 failed, 1 refusal |
| M7: revert line 412 (archived bytes, backfill test) | not run | 1 failed, 1 refusal |

M1 to M7 were run under the policy only: under default config each restores one
call site to its `e39af50` form, which the "before" row already shows passing.

M0, the load-bearing one, can be reproduced from this document alone. Strip the
flag from both helpers (the diff is exactly those two lines):

```bash
sed -i 's/f"--git-dir={origin}", //' tests/test_file_snapshots.py
```

Then run the two mode commands above: expect 10 passed under default config and
10 failed under `explicit`. Restore the file afterwards:

```bash
git checkout -- tests/test_file_snapshots.py
```

M0 shows the flag is what makes the strict run pass and that the default path
is unaffected. M1 to M7 show every converted site is reached under the policy,
so none of the seven conversions is vacuous: reverting any one of them turns
red exactly the tests that reach it.

**The five gates at `1748cd4`.**

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` | 766 collected |
| pytest | `python -m pytest tests/ -q -p no:cacheprovider` | 766 passed |
| pytest, under the policy | the same with the three `GIT_CONFIG_*` variables above | 766 passed |
| ruff check | `ruff check .` | All checks passed |
| ruff format | `ruff format --check .` | 72 files already formatted |
| mypy | `mypy --strict` (configured scope: `src/superconducted`, `scripts`) | no issues in 40 source files |
| IDs | `python scripts/check_ids.py` | exit 0, no duplicate or colliding identifiers |

No case was skipped: this checkout can reach `origin/calibration-data`, so the
archive test in `tests/test_feature_distribution.py` ran rather than skipping as
it does on CI and on Burak's desktop.

`tests/` is outside mypy's configured scope. Run on the test file alone for
information, `mypy --strict` reports one error, at `_state_index`'s
`return [tuple(row.split("\t")) for row in rows]`. It is pre-existing (the same
error at line 253 of `main`'s copy) and on a line this change does not touch.

**What a hardened machine should now see.** Relative to a run with the
`safe.bareRepository=all` override, a run without it should give the same
result: the ten `tests/test_file_snapshots.py` failures disappear and nothing
else moves. That is a differential expectation; the absolute count depends on
the branch measured.

## Related docs

- `docs/numerical-claims.md`, NC-021 (unchanged; see the NC-021 section above)
- `docs/implementations/2026-09-05-pipeline-health-dashboard.md`, the PR #70
  round-2 block that recorded the 8 Windows failures, and the `7ec173f` block
  that read them as a `.venv` artefact
- `docs/implementations/2026-09-10-scheduled-calibration-sweep.md`, the same
  reading reached independently
- `docs/implementations/2026-10-06-pr103-final-review-fixes.md`, the precedent
  for re-pinning NC-021 after a code change that moves no count
- `docs/evidence/pr107-burak-desktop/2026-10-07-verification.md` on
  `mert/feature-target-fn-units`, and PR #107 comment `6028000419`
- `scripts/file_snapshots.sh` and `scripts/push_with_retry.sh`, audited above
- PR #50's review, the blocker this test was written to catch
