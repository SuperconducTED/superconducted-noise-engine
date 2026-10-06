# 2026-10-03: feature-target-fn-units

> NOTE (review round 1, 2026-10-06): the `mean_T1 < 1.0` guard described below was replaced
> by a required `coherence_unit` keyword after review. The sections below are the round-0
> record; the current contract is in "Review round 1" at the end.

## Problem / Motivation

`training/targets.py::feature_target_fn` documented its input as
`(mean_T1, mean_T2, mean_readout_error)` "where the two coherence values are in
microseconds, matching BasicCalibrationVectorizer", and its body multiplies the
two coherence values by `1e-6`. Since issue #66 (PR #99,
`docs/implementations/2026-09-14-vectorizer-si-units.md`),
`BasicCalibrationVectorizer.extract` emits SI seconds. The "matching" clause
became false, and passing `extract()` output to `feature_target_fn` scales
seconds by `1e-6` a second time. On the committed fixture the function then
returns `gamma = lambda = 1.0` exactly, with no error raised.

No production path called the function this way yet. Its callers were the
parameterization tests, which feed survey anchors in microseconds, and
`tests/training/test_targets.py`. It was a latent trap, but not a harmless one.
Two things already depended on the false clause:

1. `test_real_fixture_derives_targets_from_all_sx_gate_lengths` fed the bare
   vectorizer into `feature_target_fn` and asserted only
   `not np.allclose(target_at_mean_features, summary.mean, atol=1e-12)`. The
   assertion was meant to show the NC-039 gap of about `4e-4`. After #66 the gap
   was about `1`, which satisfies `not allclose` just as well, so the test
   stayed green while checking the wrong value. That is also why the #66 merge
   audit, which found 23 failing tests in PR #68's suite, did not list this
   consumer: nothing here failed.
2. NC-039's registered source is the same expression, so the row has not
   reproduced from its own source since #66 merged.

## Reproduction (before the fix)

On unmodified `main` @ `110cfad`, with the q72 fixture
`tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json` and
`t_seconds = 24e-9` (NC-035):

```
extract() = array([0.00015519, 0.0001096 , 0.03532605])
extract path:  gamma=np.float64(1.0) lambda=np.float64(1.0)
survey path:   gamma=np.float64(0.0001820797139959751) lambda=np.float64(0.0003125140909431279)
```

The survey path is the NC-041 median anchor `[131.7984, 97.0365, 0.0205861]` in
microseconds. Its gamma matches the `1.820797e-04` that
`docs/implementations/2026-09-08-mf-parameterization.md` reports for the same
anchor.

On the gate-bearing fixture (NC-038), the NC-039 expression gave a gap of
`(0.99982733, 0.99933698)` through the bare vectorizer. That is `1` minus
NC-040's mean target. The same expression through `ArchiveUnitFeatureExtractor`
gave NC-039's registered values, bitwise.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/targets.py` | Round 1 (current): `feature_target_fn` takes a required `coherence_unit` (`"us"` or `"s"`, no default) and the guard below is gone. Round 0: `feature_target_fn`'s docstring now says microseconds as in the survey TSV and `ArchiveUnitFeatureExtractor`, NOT `BasicCalibrationVectorizer.extract`; the function raises `ValueError` when `mean_T1 < 1.0`; the module docstring names this function as the one exception to its SI-seconds rule. |
| `tests/test_parameterization.py` | Review round 1: the five `feature_target_fn` call sites state `coherence_unit="us"`, the unit of their survey anchors; nothing else changed. |
| `tests/training/test_targets.py` | 5 new cases pin the contract (SI rejection on the real fixture, agreement of the microsecond path with the SI closed form, both sides of the `1.0` boundary), and the real-fixture test now goes through `ArchiveUnitFeatureExtractor` and pins NC-039 instead of asserting `not np.allclose`. |
| `docs/numerical-claims.md` | NC-039's source is re-pointed to `ArchiveUnitFeatureExtractor`, with the value unchanged and the history in Notes; NC-021 gains the `706` at `eb30ca7` clause. |
| `docs/decisions/drafts/ADR-027-calibration-training-target.md` | Appended an as-of note under the paragraph that describes the old input convention; the paragraph itself is unedited. |
| `docs/implementations/2026-09-05-issue-57-training-target-contract.md` | Appended a `Units, as-of 2026-10-03` section; everything above it is unedited. |
| `docs/implementations/2026-10-03-feature-target-fn-units.md` | This record. |

## Implementation approach

The function keeps its microsecond contract and gets a guard at the one place a
seconds vector can be told apart from a microseconds vector: the magnitude of
`mean_T1`.

Contract of `feature_target_fn(features, *, t_seconds)` after this change:

- **Input:** `features`, a finite float64 array of shape `(3,)` holding
  `(mean_T1, mean_T2, mean_readout_error)`, with the two coherence values in
  **microseconds**; `t_seconds`, a finite non-negative gate duration in seconds.
- **Output:** a float64 array `(gamma, lambda)`.
- **Raises `ValueError`**, in this order: wrong shape or a non-finite entry;
  invalid `t_seconds`; a non-positive coherence value; `mean_T1 < 1.0`
  (new); `mean_T2 > 2 * mean_T1`.
- **Side effects:** none.

The new check comes after the positivity check, so `0` and negative inputs still
get the "must be positive" message they had before. Its message names the fix
(wrap `BasicCalibrationVectorizer` in `ArchiveUnitFeatureExtractor`) so a
caller who trips it does not have to read this record.

The supported way to feed the function from a snapshot is
`ArchiveUnitFeatureExtractor().extract(snapshot)`, which #66 introduced as "the
single, named place" the SI-to-archive-unit conversion happens. Its factor is
`1 / UNIT_SCALE[EXPECTED_UNITS[field]]`, so it returns the microseconds the
source document carried.

## Mathematical / Statistical details

For gate duration $t$ (seconds) and relaxation times $T_1$, $T_2$ (seconds), the
target is ADR-027's

$$
\gamma = 1 - e^{-t/T_1}, \qquad \lambda = 1 - e^{-t\,(2/T_2 - 1/T_1)}.
$$

`feature_target_fn` receives $x_1, x_2$ in microseconds and computes
$T_i = 10^{-6} x_i$.

**The failure, in numbers.** Pass SI seconds instead, and $T_i = 10^{-6} \cdot
x_i^{\mathrm{SI}} = 10^{-12} x_i^{\mu s}$. On the q72 fixture,
$x_1^{\mathrm{SI}} = 1.551924205171878 \times 10^{-4}$, so the function used
$T_1 = 1.55 \times 10^{-10}$ s and

$$
t/T_1 = 154.6, \qquad e^{-154.6} = 6.9 \times 10^{-68}.
$$

Half a unit in the last place of `1.0` in float64 is $1.1 \times 10^{-16}$, so
$1 - 6.9 \times 10^{-68}$ rounds to exactly `1.0`. The lambda exponent is
$283.3$, which gives $e^{-283.3} = 9.0 \times 10^{-124}$ and again `1.0`. The
result is finite and inside $[0, 1]$, so it passes every shape and range check
downstream.

**Why the line is at 1.0.** A device-mean $T_1$ in microseconds is of order
$10^2$. Across all 975 rows of the committed survey
(`docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv`), `mean_T1` runs
from $98.26$ to $157.88$, and NC-041's 1st percentile is $98.8191$. In seconds
the same quantity is of order $10^{-4}$: the q72 fixture gives
$1.55 \times 10^{-4}$. So:

- the smallest surveyed microsecond value sits about $98\times$ above the line;
- a seconds value would have to reach $1.0$ s, about $6{,}400\times$ the
  fixture's device mean, to get past it.

Any threshold between the two populations would work. A round `1.0` leaves at
least two orders of magnitude on each side and reads correctly as "below one
microsecond", a value no device mean in the archive comes near.

**The NC-039 pin's tolerance.** The test compares the gap to NC-039 with
`rel=1e-9`. Each target component is about $10^{-4}$, computed with a relative
error of a few ulp (about $10^{-16}$), so the absolute error is about
$10^{-20}$. Against the smaller gap component, $1.8 \times 10^{-5}$, that is a
relative error of about $10^{-15}$. `rel=1e-9` absorbs any platform difference
in `exp` by six orders of magnitude, while a unit error (gap near $1$) or a
changed fixture misses it by many more.

**Reproduction commands for the survey range:**

```bash
python - <<'EOF'
import csv
rows = list(csv.DictReader(open("docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv", encoding="utf-8"), delimiter="\t"))
v = [float(r["mean_T1"]) for r in rows if r["mean_T1"]]
print(len(rows), len(v), min(v), max(v), sum(x < 1.0 for x in v))
EOF
```

prints `975 975 98.26278058936451 157.87940215127074 0`.

## Design decisions

**Microseconds plus a guard (option a) over switching to SI (option b).** Asked
on 2026-10-03, the `training/` primary owner (Mert Efe Sensoy, per
`docs/team.md`) chose (a). The reasons:

- Every current caller is in microseconds. The survey TSV, `partition_anchors`,
  the anchored rule base's anchors, the `ClampingFeatureExtractor` domain box
  and `ArchiveUnitFeatureExtractor` all work in archive units. Under (b), the
  five `tests/test_parameterization.py` call sites, which evaluate this
  function at microsecond anchors either directly or through
  `anchored_rule_base`, would each need a microseconds-to-seconds adapter.
- That adapter would be a second conversion point beside
  `ArchiveUnitFeatureExtractor`, which #66 built to be the only one.
- (a) is the smaller diff and changes no caller's behaviour except a caller
  that was already getting a wrong answer.

**Raise, do not auto-convert.** The guard could have rescaled a seconds vector
silently. It does not: guessing units hides the caller's mistake, and the next
consumer would inherit the guess. Raising also matches every other check in the
function.

**Guard on `mean_T1` only.** This is the guard the owner approved, and it
catches the actual failure mode: a whole vector in SI, which is what
`BasicCalibrationVectorizer.extract` produces. It would not catch a vector
mixing units, with `mean_T1` in microseconds and `mean_T2` in seconds. No
extractor in the repository produces one, because both values come out of one
extractor through one scale table. A matching `mean_T2 < 1.0` check would be
cheap; the survey's `mean_T2` minimum is $67.25$, so it would also leave
margin. It is left as a possible follow-up rather than added unasked.

**Pin NC-039 instead of `not np.allclose`.** The old assertion was satisfied by
both the right gap and the wrong one. An equality pin to the registered value
fails on either a unit error or a fixture change. Mutation checks confirm this
(see Verification).

**Documents left alone.** The ADR-027 draft is the promoted authoring record
(ADR-027 has a ledger entry in `docs/decisions.md`), and the 2026-09-05 record
is dated. Both sentences were true when written, so both get appended as-of
notes rather than edits. `docs/implementations/2026-09-14-vectorizer-si-units.md`
makes no claim about `feature_target_fn`, so it is not annotated; this record is
where the missed consumer is written down.

**Issue #64 not edited.** FR-3 of issue #64 (written 2026-09-03) asks for
`per_qubit_spread` to be "in the same units ... as the mean it will jitter, that
is, microseconds for T1 and T2", "with no `_UNIT_SCALE` applied". Since #66,
those two requirements contradict each other: `extract`'s mean is in SI
seconds. The issue belongs to @bengisucvd, so the PR raises it with her instead
of editing her text.

## Verification

**Local results are provisional.** They were produced on Mert's Windows laptop in
a clean Python 3.12.10 venv at `C:\pvci` whose six key packages match the pins
(`numpy==2.4.4`, `qiskit==2.4.1`, `qiskit-aer==0.17.2`, `pytest==9.0.3`,
`ruff==0.15.12`, `mypy==1.20.2`), with `PYTHONPATH=<worktree>/src`.

At `eb30ca7`:

| Gate | Result |
| --- | --- |
| `pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` | `706 tests collected` (`main` @ `110cfad`: `701`) |
| `pytest tests/ -q -p no:cacheprovider` | `706 passed` |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `68 files already formatted` |
| `mypy --strict` | `Success: no issues found in 38 source files` |
| `python scripts/check_ids.py` | `No duplicate or colliding ADR / NC identifiers.` |

**Test first.** The new tests were run against the unmodified `targets.py`
first. The three rejection cases failed with `DID NOT RAISE`, and the other
two new cases plus the NC-039 pin passed, because they describe behaviour that
was already correct.

**Mutation checks.** Each was applied, run, and restored, and the restored
files were confirmed byte-identical by SHA-256.

| Mutation | Result |
| --- | --- |
| Guard disabled (`if False:`) | 3 failed: the SI-rejection case and both boundary-rejection cases |
| Guard uses `<=` | 1 failed: the exactly-`1.0` acceptance case |
| Guard disabled and the real-fixture test fed the bare vectorizer (the pre-fix state) | 4 failed, including `test_real_fixture_derives_targets_from_all_sx_gate_lengths` on the NC-039 pin |
| Microsecond scale `1e-6` changed to `1e-3` | 4 failed, including the archive-path closed-form case |

**Desktop runbook.** The authoritative run is on Burak's desktop (bash on WSL2).
The full runbook is the second comment on this PR and pins the PR head SHA.
These are its checks, each stated so that it cannot rot:

1. Fresh `git clone --filter=blob:none --single-branch --branch
   mert/feature-target-fn-units`, then
   `git fetch origin main:refs/remotes/origin/main`. Stop unless
   `git rev-parse HEAD` equals the SHA in the comment.
2. New venv from `requirements.txt` and `requirements-dev.txt`, `pip install -e
   . --no-deps`, and a check that the six packages above match the pins.
3. The five gates.
4. NC-021 is self-consistent: the registered value equals the live
   `--collect-only` count, and the full run reports passed = collected minus 1
   with exactly `1 skipped`. The skip is the archive-backed survey test, which
   cannot reach `calibration-data` from a single-branch clone, as on CI.
5. Differential reproduction: a probe script run once against an `origin/main`
   worktree and once against the PR tree. On `main`, the extract path prints
   `[1. 1.]`; on the PR, it prints a `ValueError` naming seconds. The survey path
   prints the same pair on both trees.
6. NC-039 reproduces: the printed gap equals the register row's digits.
7. The guard mutation makes its 3 tests fail, and the tree is clean afterwards.
8. `git diff --stat origin/main -- src tests` names only `targets.py` and
   `test_targets.py`; the locked modules `fuzzy/tsk.py` and `channels/kraus.py`
   are untouched.

## Related docs

- Issue #66, PR #99, `docs/implementations/2026-09-14-vectorizer-si-units.md`
  (the change that made `extract` emit SI seconds and added
  `ArchiveUnitFeatureExtractor`)
- Issue #57, ADR-027 in `docs/decisions.md`,
  `docs/decisions/drafts/ADR-027-calibration-training-target.md`,
  `docs/implementations/2026-09-05-issue-57-training-target-contract.md`
- `docs/implementations/2026-09-08-mf-parameterization.md` (section 6.4 (c), the
  magnitude check at the survey median anchor)
- Issue #64 FR-3 (`per_qubit_spread` units, raised with its owner on the PR)
- `docs/numerical-claims.md` NC-021, NC-035, NC-038, NC-039, NC-040, NC-041
- `docs/team.md` (`training/` ownership)

## Review round 1 (2026-10-06): an explicit unit replaces the guard

Everything above records round 0 and is left as written, except the "What
changed" manifest, which describes the PR as it now stands.

### The finding

Burak's review of `b92ac96` (`CHANGES_REQUESTED`, 2026-10-04) reported a clean
desktop run: 706 passed, and Ruff, format and strict mypy all passed. His
objection was to the contract itself. `mean_T1 < 1.0` does not mean "can only
be SI seconds". The cutoff rests on the 975-row survey range, while
`feature_target_fn` accepts any positive microsecond vector. A physically valid
sub-microsecond device given in microseconds would be rejected as seconds, and
a raw float array carries no unit provenance, so no cutoff can be a unit
guarantee. He asked for either a lower-bound invariant documented with its
data scope, or an explicit unit or source contract at the call boundary. Both
were to keep the regression test and the NC-039 pin.

**Reproduced on `b92ac96` before fixing.** The original `targets.py` was put
on a copy of `src/` (the only `src` file that differs from the fix commit) and
called with Burak's case:

```
0.5 -> ValueError: mean_T1 0.5 is below 1.0 microseconds, so it can only be SI seconds; ...
0.9999999999999999 -> ValueError: mean_T1 0.9999999999999999 is below 1.0 microseconds, ...
physical gamma at 0.5 us: 0.046866212922495265
```

The round-0 sentence "which can only be SI seconds" in the docstring, the
error message and this record was an overclaim. The survey bounds what the
archive has seen, not what the API may be given.

### The decision

Asked on 2026-10-06, the `training/` owner (Mert Efe Sensoy) chose the
explicit unit over a scoped domain floor.

- **A floor can be documented but not proven.** Restated as "the validated
  domain", it would still reject a valid sub-microsecond device, by design
  rather than by accident. It would also keep a magnitude heuristic standing
  in for a fact the caller already knows.
- **An explicit unit does not depend on magnitudes.** The caller always knows
  which producer it called; the function never can.
- **Cost:** one keyword at each of the five `tests/test_parameterization.py`
  call sites, which evaluate the function at survey anchors in microseconds.

### Contract after round 1

`feature_target_fn(features, *, t_seconds, coherence_unit)`:

- `coherence_unit: Literal["us", "s"]`, keyword-only, **no default**. Omitting
  it raises `TypeError`, so the call that produced `(1.0, 1.0)` in round 0's
  reproduction can no longer be written without a unit.
- `"us"` scales by `UNIT_SCALE["us"]`, the loader's own table, so archive
  microseconds convert here exactly as they do on the way into the vectorizer.
  `"s"` scales by `1.0`.
- Any other value, including a non-string, raises `ValueError`.
- No magnitude check. `_MIN_MEAN_T1_MICROSECONDS` and its guard are gone.
- **Residual risk, stated in the docstring:** a wrong label is not detected.
  SI seconds declared as `"us"` still give a target that rounds to `(1.0, 1.0)`
  at nanosecond gate durations. What changed is that the label is written at
  every call site, where review can see it, instead of living only in a
  docstring.

**Why `"s"` is not added to `UNIT_SCALE`.** That table maps units an archive
document declares to SI, and `validate_unit_scale` accepts exactly its keys.
No archive field is published in seconds. Adding `"s"` there would widen what
the loader accepts from a document in order to serve one function's API. The
function keeps a two-entry table that reads `"us"` from the loader, so the
microsecond factor cannot drift between the two.

### Tests

`tests/training/test_targets.py` stays at 19 collected: five round-0 cases
are replaced by five round-1 cases, and the NC-039 test gains an assertion.

| Round 0 | Round 1 | What it pins now |
| --- | --- | --- |
| `test_feature_target_fn_rejects_si_seconds_from_the_vectorizer` | `test_feature_target_fn_refuses_vectorizer_output_without_a_unit` | Same q72 `extract()` input; the unlabelled call raises `TypeError` naming `coherence_unit` |
| `test_feature_target_fn_takes_archive_unit_features_for_the_same_snapshot` | `test_feature_target_fn_gives_one_target_for_both_units_of_the_same_snapshot` | `extract()` declared `"s"` and `ArchiveUnitFeatureExtractor` declared `"us"` both equal the closed form on the vectorizer's own seconds (`rel=1e-12`) |
| `test_feature_target_fn_rejects_mean_t1_below_one_microsecond` (x2) | `test_feature_target_fn_rejects_an_unknown_coherence_unit` (x2: `"ns"`, `"S"`) | Only `"us"` and `"s"` are accepted; `"ns"` is in `UNIT_SCALE` and is still refused |
| `test_feature_target_fn_accepts_mean_t1_of_exactly_one_microsecond` | `test_feature_target_fn_accepts_a_sub_microsecond_mean_t1` | Burak's counterexample: 0.5 microseconds gives `1 - exp(-0.048)` |
| `test_real_fixture_derives_targets_from_all_sx_gate_lengths` | same test | The NC-039 pin is kept on the `"us"` path and added on the `"s"` path |

The five `tests/test_parameterization.py` call sites now pass
`coherence_unit="us"`, which is what their survey anchors are. Nothing else in
that file changed.

**Mutation checks** on `targets.py`. Each mutation was applied by exact-needle
replacement, run against `tests/training/test_targets.py`, and restored; the
file was confirmed byte-identical by SHA-256 afterwards.

| Mutation | Caught by |
| --- | --- |
| M1: `coherence_unit` gets a default of `"us"` (the implicit contract again) | `refuses_vectorizer_output_without_a_unit` |
| M2: the unit is ignored, always `1e-6` | `gives_one_target_for_both_units...` and the NC-039 pin's `"s"` path |
| M3: an unknown unit falls back to microseconds instead of raising | both `rejects_an_unknown_coherence_unit` cases |
| M4: the round-0 heuristic comes back for `"us"` | `accepts_a_sub_microsecond_mean_t1` |
| M5: the `"us"` factor is off by `1e3` | 4 tests, including `agrees_with_one_qubit_target` and the NC-039 pin |

### Mathematical details

Burak's case, $T_1 = T_2 = 0.5\ \mu s$ at $t = 24$ ns:
$\gamma = 1 - e^{-t/T_1} = 1 - e^{-0.048} = 0.046866$, and because $T_2 = T_1$,
$2/T_2 - 1/T_1 = 1/T_1$ and $\lambda = \gamma$. That is a large but physical
damping; the round-0 guard refused it.

NC-039 at `4621b74`: both paths reproduce the registered gap **bitwise**,
`ArchiveUnitFeatureExtractor` output with `"us"` and
`BasicCalibrationVectorizer.extract` output with `"s"`. Bitwise equality of the
`"s"` path is measured, not guaranteed: the #66 record shows that scaling
before and after a mean can differ by about one ulp. The test pin's
`rel=1e-9` is what is guaranteed.

### Two merges of `main`

`main` moved twice while the review was open.

| Merge | `main` | What came in | Result |
| --- | --- | --- | --- |
| `e421e3c` | `e411911` (PR #98) | `docs/` only | Clean; 706 collected |
| `5517881` | `7c2d4d1` (PR #103) | `scripts/first_ensemble_run.py`, its tests, docs | One text conflict, the NC-021 row; both narratives kept, `main`'s first |

Neither merge brought a new `feature_target_fn` caller; the `+` lines of both
diffs were grepped for it. `main` @ `e411911` collects 701, a direct collection. `main` @ `7c2d4d1` was
not collected directly; PR #103 recorded 712 at its own merge `0ce3b42`.

### Verification at `5517881`

Provisional, on Mert's laptop, Python 3.12.10 venv on the pins, clean tree:

| Gate | Result |
| --- | --- |
| `pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` | `717 tests collected` |
| `pytest tests/ -q -p no:cacheprovider` | `717 passed` |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `68 files already formatted` |
| `mypy --strict` | `Success: no issues found in 38 source files` |
| `python scripts/check_ids.py` | `No duplicate or colliding ADR / NC identifiers.` |

The desktop runbook is re-pinned to the new head and posted as the last
comment on the PR. Relative to round 0, it changes three steps:

- the probe passes `coherence_unit="s"` on the PR tree;
- step 9 mutates the unit table instead of the guard;
- the scope step names `tests/test_parameterization.py` as a third file.
