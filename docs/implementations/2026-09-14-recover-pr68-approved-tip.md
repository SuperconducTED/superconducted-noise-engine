# 2026-09-14: recover-pr68-approved-tip

## Problem / Motivation

PR #68 (issue #59, manual membership-function parameterization) was approved by
@BurakOztekin and @mertefesensoy on 2026-09-08 at `5395e11`. On 2026-09-13 at
22:53:56Z the branch `feature/issue-59-parameterization` was force-pushed. The
push rewrote history back to `cd6421b` and dropped five review-fix commits
(`cd32c88`, `bd5f334`, `764f9c8`, `a0a13d8`, `0989949`) together with both
approved tips (`3f5e0f9`, `5395e11`).

Three things made this worse than an ordinary lost branch:

1. **Nothing was on a remote.** `git ls-remote` shows only
   `refs/heads/feature/issue-59-parameterization` at `0da080d`. `5395e11`
   survived in exactly one local object store, reachable only through a stale
   remote-tracking ref and an unrelated review worktree.
2. **The approvals survived the push.** The `main` merge gate is a ruleset that
   requires one approval and does not dismiss stale reviews on push, so GitHub
   reported `reviewDecision=APPROVED`, `mergeStateStatus=CLEAN` for a tree
   nobody had reviewed. Only the draft flag stood between that state and a merge.
3. **The PR description still described the lost tree.** Its addendum ticks
   "125 new tests", "485 collected, 485 passed", an implementation doc, four NC
   rows and a `docs/team.md` row. At `0da080d` the suite collects 468 against
   the 465 on `main`, a delta of three, and none of the documents exist.

This branch restores the approved deliverable and revalidates it against current
`main`, so the work exists somewhere other than one laptop.

## What changed

| File | One-sentence description |
| --- | --- |
| (whole tree) | Branch `mert/issue-59-recover-5395e11` created at `5395e11`, the approved tip, then merged with `main` @ `004e14e` at `e3bd6a0`. |
| `docs/numerical-claims.md` | NC-021 conflict resolved to the row from `main` in the merge, then re-measured to `590` at `e3bd6a0` in the following commit; NC-041..NC-044 kept alongside NC-045..NC-051. |
| `docs/team.md` | Auto-merged; the `fuzzy/parameterization.py` ownership row survives the #56 restructuring with the handle column intact. |
| `docs/implementations/2026-09-08-mf-parameterization.md` | An `## As of 2026-09-14` section appended; no 2026-09-08 row edited in place. |
| `docs/implementations/2026-09-14-recover-pr68-approved-tip.md` | This record. |

No source file is modified by the recovery itself. `scripts/feature_distribution.py`,
`src/superconducted/fuzzy/parameterization.py`, `tests/test_parameterization.py`
and `tests/test_feature_distribution.py` arrive from `5395e11` byte for byte.

## Implementation approach

**Merge, not rebase.** The recovered history already contains three merge
commits (`4adcea1`, `764f9c8`, `3f5e0f9`). Rebasing its 19 commits onto `main`
would rewrite the audit trail that shows which review round closed which
finding, which is the main thing worth recovering. A merge leaves `5395e11`
reachable by SHA permanently and makes the recovery itself auditable.

**No force-push over the branch of the author.**
`feature/issue-59-parameterization` belongs to @yigit-arda and keeps its
`0da080d` tip untouched. Reconciling the two branches is his call, not a call
for whoever runs the recovery.

**Conflicts, both additive.** `docs/team.md` auto-merged.
`docs/numerical-claims.md` conflicted twice:

- *NC-021.* Both sides edited the row: the branch carried `485` at `3f5e0f9`,
  `main` carried `465` at `d7ccb8c`. Resolved to the row from `main` inside the
  merge commit, then re-measured afterwards. Writing the merged value inside the
  merge commit is the specific mistake Rule 6 exists to prevent, because a value
  edited into a commit cannot name the commit it was measured at.
- *NC-041..NC-044 against NC-045..NC-051.* Disjoint id ranges, both kept. The
  ranges are disjoint because `main` renumbered its own NC-042 to NC-047 before
  merging, with a note saying it did so because PR #68 claimed NC-042. The
  resolver asserted the two id sets do not intersect rather than assuming it.

## Mathematical / Statistical details

The recovery introduces no new mathematics. It restores one measured quantity
and re-measures another.

**NC-021, re-measured at the merge.** Let `B` be the registered suite size on
`main` and `T` the tests this ticket adds. `B = 465` at `d7ccb8c`, and `T = 125`,
being 97 in `tests/test_parameterization.py` and 28 in
`tests/test_feature_distribution.py`, both files new. The merged tree collects
**590**, and `465 + 125 = 590` reconciles, but the registered value is the direct
collection at `e3bd6a0` and not that sum: the NC-021 convention forbids deriving
the count by adding branch deltas, because a delta describes a tree that may
never be merged. The previous `485` on this branch is superseded for exactly
that reason; it was measured on a tree based on `645b4d1`.

**The Decision 2 branch that ships here.** The slope strategy for `TanhMF` is
chosen by measurement, not assumed. The floor onset of ADR-023 under the
section 6.3 mapping has the closed form

```
x*_j = c_j - 2.5 * u_j * v_j / (v_j - u_j),   u_j = c_j - e_(j-1),  v_j = e_j - c_j
```

where `c_j` is the bin-mid quantile of the level and `e_(j-1)`, `e_j` its bin
edges. A level whose `x*_j` falls inside the domain box `[lo, hi]` of its feature
has a zero-gradient floored tail inside the surveyed range, which triggers the
per-feature equal-slope fallback of decision 2. Measured on the committed
975-row survey at `calibration-data@3d1569d`, reproduced at `e3bd6a0`:

| feature | `x*_1` | `x*_2` | `x*_3` | box | inside |
| --- | ---: | ---: | ---: | --- | --- |
| `mean_T1` | 149.1562 | 159.6486 | 100.0941 | [98.8191, 154.3887] | `j=1`, `j=3` |
| `mean_T2` | 116.1544 | 3.6583 | 81.9729 | [67.4411, 110.5429] | `j=3` |
| `mean_readout_error` | 0.0306 | 0.0140 | -0.0316 | [0.0171, 0.0374] | `j=1` |

Four of nine onsets land inside their box, so all three features take the
fallback and `tanh_slope_strategy` returns `equal-slope` for each. These are the
same nine values the 2026-09-08 record reports, which is the check that the
merge did not move the quantiles.

## Design decisions

**The M2 shapes are not carried over.** The commit `e503e1e` added
`TriangularMF`, `TrapezoidalMF` and `TanhBellMF` on the force-pushed head.
Re-applying it would import a measured defect: the triangular and trapezoidal
feet are placed at the bin edges `(e_(j-1), c_j, e_j)` rather than at the
`c_j +/- 2 r_j` and `c_j +/- 1.5 r_j` of section 6.3. On the committed quantiles
every level then reads exactly `0.0` at every bin edge, including `lo` and `hi`,
so the bin-cover rule of FR-9 fails and the anchored rule base raises
`ZeroDivisionError` at the clamped corner. That inverts UC-7:
`ClampingFeatureExtractor` maps an out-of-range row onto `lo` or `hi`, which are
precisely the points where nothing fires, so the wrapper that exists to prevent
the crash guarantees it. This tree keeps the M1 split of architect decision C3,
where those three shapes raise `NotImplementedError` naming the second commit.
M2 lands separately once the mapping matches section 6.3.

**Decision 2 stays open and stays reversible.** The decision record of
@bengisucvd on 2026-09-13 ratified decisions 1 and 3, and for decision 2
recommended retaining half-reach slopes for all three features, asking
@BurakOztekin to confirm or reject as the owner of that decision. This tree ships
what the ticket recommended and what the 2026-09-08 record describes: measured
onsets, the per-feature fallback, and a keyword-only `tanh_slopes` argument that
makes the counterfactual runnable in one call. Bengisu measured her comparison at
`5395e11` over the 975-row survey at `calibration-data@3d1569d`, which is exactly
this tree, so her numbers describe what is here. They did not describe
`0da080d`, where the survey is 930 rows from an unnamed ref and the override is
absent.

**The alternative considered and rejected** was to recover onto the branch of
the author by force-push, producing a single tip carrying both the approved work
and the M2 shapes. Rejected on two grounds: it would overwrite the commits of
@yigit-arda with no record, and it would fold the defective M2 mapping into the
approved deliverable rather than keeping the two separable.

## Verification

Run from a checkout of `mert/issue-59-recover-5395e11`. The `PYTHONPATH` prefix
matters on a machine with an editable install pointing at another checkout;
without it `superconducted` resolves to the other tree and
`tests/test_parameterization.py` fails to import.

```bash
PYTHONPATH=src:. python -m pytest tests/ -q
```

```bash
PYTHONPATH=src:. python -m pytest tests/ --collect-only -q -o addopts=""
```

```bash
python -m ruff check . && python -m mypy && PYTHONPATH=src:. python scripts/check_ids.py
```

Measured at `e3bd6a0` in a clean CPython 3.12.10 interpreter at a short path:

| Check | Result |
| --- | --- |
| `pytest tests/ -q` | 590 passed |
| `pytest --collect-only` | 590 collected, the registered value of NC-021 |
| `ruff check .` | All checks passed |
| `mypy` (strict, `[tool.mypy] files`) | Success, no issues in 37 source files |
| `scripts/check_ids.py` | No duplicate or colliding ADR / NC identifiers |

All 590 also pass on Windows in that interpreter. `ubuntu-latest` remains the
authority for the pass count per NC-021. These are provisional laptop
measurements; canonical verification is the next phase-3 batch record of
@BurakOztekin per architect decision C2 and `docs/team.md`.

Reproducing the two claims this record makes about the force-pushed head:

```bash
git merge-base --is-ancestor 5395e11 refs/pull/68/head; echo "exit=$?"
```

```bash
git ls-remote superconducted-noise-engine | grep issue-59
```

The first exits non-zero, which is the statement that the approved tip is not an
ancestor of the current PR head. The second lists one ref at `0da080d`, which is
the statement that no backup of the approved tip was ever pushed.

## Related docs

- `docs/implementations/2026-09-08-mf-parameterization.md`, and its
  `## As of 2026-09-14` section
- Issue #59 sections 6.3, 6.6, 7 and 10; the decision record of @bengisucvd of
  2026-09-13 ratifying decisions 1 and 3 and putting decision 2 to @BurakOztekin
- PR #68, and its reviews of 2026-09-04 and 2026-09-08
- NC-021, NC-041, NC-042, NC-043, NC-044 in `docs/numerical-claims.md`
- ADR-006, ADR-009, ADR-010, ADR-018, ADR-019, ADR-023, ADR-024 in
  `docs/decisions.md`
