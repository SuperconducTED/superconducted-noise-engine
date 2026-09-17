# 2026-09-14: Vectorizer SI units

## Problem / Motivation

[Issue #66](https://github.com/SuperconducTED/superconducted-noise-engine/issues/66)
identified that the vectorizer ignored IBM Nduv units, passing microseconds to
a grid defined in seconds. This corrects the claim in item 6 of the dated
`docs/audits/2026-05-25-followup-issues.md` that both parsers produced correct
results: the duplicated walk was already a defect, not merely a maintenance
risk. That historical document is unchanged.

## What changed

| File | Description |
| --- | --- |
| `src/superconducted/calibration/features.py` | Validates declared units using the loader's expected-unit table and scales to SI using its conversion table. |
| `scripts/first_ensemble_run.py` | Synthetic coherence inputs use `50.0` with `unit: "us"`; readout error declares its dimensionless unit. |
| `tests/conftest.py` | Shared dummy snapshot declares `us` for T1 (`100.0`, `110.0`) and T2 (`80.0`, `90.0`), preserving the physical values while exercising scaling. |
| `tests/calibration/test_vectorizer_units.py` | Checks real-fixture agreement, grid firing and viable ensembles for both placements, invalid and missing units, and synthetic archive-unit conversion. |
| `src/superconducted/calibration/loader.py` | Review follow-up: `_EXPECTED_UNITS` and `_UNIT_SCALE` are renamed to public `EXPECTED_UNITS` and `UNIT_SCALE`, so the feature layer shares one table instead of importing another module's privates. The shared `validate_unit_scale` helper now owns unit validation and returns the SI conversion factor; loader parsing behaviour is unchanged. |
| `docs/decisions.md` | Clarifies ADR-010 units and tracks parser convergence under ADR-013. |
| `docs/numerical-claims.md` | Registers the corrected reduced-fixture measurement and updates NC-021 differentially. |

## Implementation approach

Option A preserves the `CalibrationFeatureExtractor` ABC and raw snapshot
input. Only the three consumed fields are validated; unrelated vendor fields
remain ignored. Declared units must match the typed loader (`us` for T1/T2,
empty string for readout error). A mismatch raises `CalibrationParseError`
with backend, timestamp, qubit, field, unit and value, before filtering values.
Missing/non-numeric/non-finite values retain the existing skip policy.
Every consumed Nduv entry requires a unit key. Missing or explicit-null units
are errors, as are empty coherence units. Both parsers call
`validate_unit_scale` before filtering or parsing the value. Synthetic inputs
now declare archive units, with numeric coherence values expressed in microseconds.

## Mathematical / Statistical details

Each finite coherence observation in microseconds is multiplied by `1e-6`
before averaging; dimensionless readout error is unchanged. On the committed
reduced fixture, corrected means are T1 `0.0001551924205171878` seconds,
T2 `0.00010959537464376821` seconds, readout error `0.03532605293469551`.
The shipped endpoint grid's firing sum is `0.10769113232875129` (NC-052).
These are reduced-fixture measurements, not the different August snapshot
quoted in the issue.

## Design decisions

Use option A as recommended by the issue. Option B (typed snapshot consumption)
is tracked in the ADR-013 revisit note because it changes an ABC signature and
requires reconciling parsing policies. Option C would retain inconsistent unit
conventions. The loader's parsing behaviour is unchanged, as are the locked TSK and Kraus
implementations. Unit validation is extracted into one shared loader helper.

## Verification

Measured on the local Windows workstation, using the repository Python 3.14
environment, on base `004e14ed153c4ea1421f801e4d3c00e26aa5ef8a` plus this patch.
Measurements are provisional; canonical verification remains the team batch record.

```powershell
.venv/Scripts/python.exe -m pytest tests/ -q -o addopts='' -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check src/superconducted/calibration/features.py scripts/first_ensemble_run.py tests/calibration/test_vectorizer_units.py
.venv/Scripts/python.exe -m mypy src/superconducted/calibration/features.py scripts/first_ensemble_run.py
.venv/Scripts/python.exe scripts/first_ensemble_run.py --snapshot tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json
```

Full suite: **483 passed**; direct collection: **483**, versus **465** on the base.
Ruff and strict mypy checks pass. The sandbox run encountered temporary-directory
permission errors; the successful full run used approved execution outside the
sandbox with `--basetemp=.pytest-tmp-issue66-final`. NC-021 and NC-052 originally identified
the base plus working-tree patch; both were re-pinned to `6394951` in the following
commit, measured there rather than carried over.

The archive-fixture smoke command completes for ensemble sizes 1, 8 and 16
with viable consequent seed 0, and completes the final sanity simulation.
To reproduce NC-052, load that fixture with the smoke script's `_load_snapshot`,
extract with `BasicCalibrationVectorizer`, and evaluate a `TSKRuleBase.from_grid`
with `_default_mfs_for_feature(name)` for each `feature_names` entry and
`output_dim=2`; sum `evaluate(features).firing_strengths`. The regression tests
compare coherence means directly to `load_snapshot` plus `mean_t1`/`mean_t2`.

### Review verification, 2026-09-14

The run above is the author's. It is recorded as measured and is not restated
here. It used Python 3.14, which is outside what this project gates on:
`.github/workflows/ci.yml` runs a 3.11 and 3.12 matrix, `pyproject.toml`
declares `requires-python = ">=3.11"` with classifiers to 3.12, and
`[tool.mypy]` pins `python_version = "3.11"`. So it is recorded as
supplementary, and CI is the authority.

Re-measured during review in a clean CPython 3.12.10 virtual environment at a
short path (not the repository `.venv`, per the NC-021 note on that
environment), running the same commands CI runs rather than per-file subsets:

```bash
ruff check .                       # All checks passed
ruff format --check .              # 3 pre-existing files, identical on main
python scripts/check_ids.py        # No duplicate or colliding ADR / NC identifiers
mypy --strict                      # Success: no issues found in 35 source files
pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider
pytest tests/ -q -o addopts="" -p no:cacheprovider
```

Collection and full run both report **483**, matching the author's figure.
`ruff format --check .` reports `docs/implementations/2026-09-06-*.md`,
`docs/implementations/2026-09-08-*.md` and `tests/fixtures/calibration/README.md`;
all three report identically at `004e14ed`, so they are pre-existing and not
introduced here. `mypy --strict` needs `--python-version 3.12` locally because
numpy 2.5.2's stubs use `type` statements that the configured 3.11 target
rejects while parsing them; that failure also reproduces at `004e14ed` and is an
environment artefact, not a finding against this branch. CI is green on both the
3.11 and 3.12 legs.

NC-052 was reproduced independently from the committed fixture and agrees to the
last digit: T1 `0.0001551924205171878` s, T2 `0.00010959537464376821` s, readout
error `0.03532605293469551`, endpoint-grid firing sum `0.10769113232875129`. The
one-argument `_default_mfs_for_feature(name)` recipe above is correct because
`DEFAULT_MF_PLACEMENT` is `endpoint`.

## Related docs

- ADR-010, ADR-013 and ADR-017 in `docs/decisions.md`.
- NC-021 and NC-052 in `docs/numerical-claims.md`.
- Issue #66 and cycle-1 follow-up audit item 6.


## Blocker follow-up

The earlier unitless-SI fallback was incorrect: removing a unit key from real
archive data reintroduced the microseconds/seconds mismatch. Both consumers now
reject that document with `CalibrationParseError` through the same helper.
The three new regression cases remove only the unit key from T1, T2 or
readout error in the committed real fixture and verify rejection by the loader,
vectorizer and smoke ensemble construction. Existing null/invalid-unit cases
continue to check validation before missing-value filtering.

Synthetic coherence inputs are now archive microseconds with explicit `us`
units. This supersedes the earlier unitless-SI compatibility decision. The
ABC input type and the existing numeric-value skip policy remain unchanged.

These changes are an uncommitted patch on `5163db0`; the reviewer commits
`6394951` and `5163db0` are preserved. The historical verification above records
those earlier trees, not the blocker-fix test count.

Blocker-fix validation on local Windows/Python 3.14: **486 collected and 486
passed** (NC-021), using `--basetemp=.pytest-tmp-issue66-blockers` outside the
sandbox for temporary-directory access. `ruff check .`, `ruff format --check .`,
`mypy --strict` and `python scripts/check_ids.py` all pass. The real-fixture
smoke command completes for all ensemble sizes and the sanity simulation.
The numerical-claim source identifies this uncommitted patch explicitly;
pin it to the implementation commit before merge. NC-052's measurement inputs
and valid-unit calculation are unchanged, so its existing pinned source remains.

## Second review follow-up, 2026-09-15

This section is appended rather than edited into the sections above, which are
dated and describe the trees they were written against. It records what the
second PR #99 convention review found and what was done about it.

### The pin the previous section left open

The Blocker follow-up above says "These changes are an uncommitted patch on
`5163db0`" and asks that the numerical claim be pinned to the implementation
commit before merge. That commit exists: it is `9a294af`, and 486 reproduces
there (486 collected, 486 passed) in a clean CPython 3.12.10 interpreter at a
short path rather than the repository `.venv`. The TODO is therefore closed,
and NC-021 no longer names a working tree. That mattered twice over: naming an
uncommitted patch is the same failure the `370` entry in NC-021 records, and
the first re-pin at `5163db0` had just finished correcting it.

The ASCII `?` that `6394951` repaired in the ledger separator came back in
`9a294af`, in the Blocker follow-up text appended to NC-021. It is repaired
again, at byte level, and `docs/numerical-claims.md` now holds zero literal
`?`, matching `004e14ed`. The cause is a non-UTF-8 write, so it will keep
recurring until whatever writes those cells is fixed; worth knowing rather
than only worth repairing.

### Code changes, `6e10825`

| Finding | Change |
| --- | --- |
| `validate_unit_scale` ended in `UNIT_SCALE[expected_unit]` | A field added to `EXPECTED_UNITS` with a unit that has no conversion factor would have raised a bare `KeyError`, breaking the promise in `CalibrationParseError`'s docstring that parse failures arrive as that error. The note added above `EXPECTED_UNITS` in `6394951` explicitly invites that edit, so the trap was live rather than theoretical. Now guarded, naming the offending unit. |
| `actual_unit: Any`, `raw_value: Any` | Retyped to `object` on what became a public API in `6394951`. Both are only compared and repr'd in this function, so `object` is the accurate annotation and keeps `--strict` honest at the call sites. |
| Three copies of `("T1", "T2", "readout_error")` | The new guard, the `if`/`elif` dispatch and `_FEATURE_NAMES` each held the field set. One `_NDUV_TO_FEATURE` table now drives all three. Issue #66 was a units defect, but its shape was two copies of one fact drifting apart, and a third copy of the field set is the same bet. |
| Two tests for the guard above | One asserts `EXPECTED_UNITS` and `UNIT_SCALE` agree today; one asserts an unconvertible unit raises `CalibrationParseError`. |
| `assert strengths.sum() > 0` | Replaced for the endpoint placement by NC-052's registered value. See below. |

`extract` returns the same vector and raises the same unusable-snapshot
message as before the refactor. All four NC-052 figures were re-measured at
`6e10825` and are unchanged to the last digit, which is the check that the
refactor was behaviour-preserving.

### Mathematical / statistical details

The replaced guard was weaker than it reads. Firing strength on a Gaussian
grid falls off as `exp(-0.5 * d^2)` in units of sigma from the nearest
centre, and `sigma` here is a quarter of each feature's range, so a value
that is wrong by a constant factor is still strictly positive until the
exponent underflows a double. Measured on this fixture, holding readout
error fixed and scaling both coherence means:

| coherence error | firing sum | passes `> 0`? |
| --- | ---: | --- |
| 1x (correct) | 1.076911e-01 | yes |
| 2x | 6.045025e-21 | yes |
| 5x | 4.158122e-229 | yes |
| 10x | 0.000000e+00 | no |
| 1e6x (the original defect) | 0.000000e+00 | no |

So `> 0` caught the defect issue #66 was filed for and essentially nothing
milder. Pinning NC-052's registered sum, `0.10769113232875129`, is what makes
the third acceptance criterion ("a future unit change fails loudly") true for
errors below 10x. The interior placement has no register row of its own and
keeps the non-degeneracy check it was written with.

### One review finding withdrawn

The review flagged the two new tests that call
`generate_safe_ensemble_with_seed` as missing `@pytest.mark.slow`, on the
grounds that every existing caller carries it. That premise does not hold.
Timing the five marked tests in `tests/test_first_ensemble_run.py`, only
`test_run_ensemble_real_aer_one_qubit` is slow, at 6.14 s, and it is the only
one that runs a real Aer circuit; `test_consequent_seed_search_is_deterministic`
runs in 0.01 s, and `test_seed_limit_must_be_positive` calls the same function
without the mark. The new tests run 21 cases in 0.46 s and never reach
`simulator.run`, so they are not Aer-runtime tests under the project's rule.
Marking them would remove this change's main regression guard from
`-m "not slow"` runs and save 0.02 s. No change made, recorded here so the
next reviewer does not re-raise it.

Worth separating from that: the marks on
`test_consequent_seed_search_is_deterministic` and
`test_selected_seed_is_non_degenerate` are themselves over-applied relative to
what `pyproject.toml` says the marker means. That is pre-existing and out of
scope here.

### Incidental, not part of the fix

The `.pytest-tmp-*/` line added to `.gitignore` accommodates one workstation's
`--basetemp` workaround and has nothing to do with units. It is harmless and
is left in place, named here so it is not mistaken for part of the change.

### Gates at `6e10825`

Clean CPython 3.12.10 virtual environment at a short path, running the
commands CI runs:

```bash
ruff check .                       # All checks passed
ruff format --check .              # 61 files already formatted
python scripts/check_ids.py        # No duplicate or colliding ADR / NC identifiers
mypy --strict src/superconducted scripts   # Success: no issues found in 35 source files
pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider   # 488
pytest tests/ -q -o addopts="" -p no:cacheprovider                  # 488 passed
```

488 collected and 488 passed, registered as NC-021 at that commit and not
derived from 486 + 2. `main` has not moved under this branch: its tip is still
`004e14ed` and is still the merge base, so this is the tree that will merge. If
`main` lands first, re-measure at the merge rather than carrying this figure
across. CI on `ubuntu-latest` across the 3.11 and 3.12 legs remains the
authority for the pass count.

The fix was also re-verified end to end against a real archived document
rather than only the committed reduced fixture, which is what acceptance
criterion 4 asks for. Using
`snapshots/2026-08/ibm_fez/20260831T203902000000Z.json` on the
`calibration-data` branch, the document issue #66 quotes, the vectorizer
returns `[1.214277e-04, 9.147555e-05, 1.936301e-02]`, all 27 rules fire, and
`scripts/first_ensemble_run.py --snapshot` completes at ensemble sizes 1, 8
and 16 plus the final sanity simulation. That is the measurement the issue
predicted and the crash it was filed for is gone.

## Third review follow-up, 2026-09-17

Appended, not edited in, for the same reason as the section above. Two review
findings were fixed, and then `main` moved and turned a small change into the
interesting one.

### The two findings

| Finding | Change | Commit |
| --- | --- | --- |
| `extract` raised `TypeError` on a malformed `name` | `6e10825` swapped tuple membership for dict membership when it collapsed the field set onto one table. Those differ on malformed input: a JSON value can be a list or dict, and `x in some_dict` hashes `x`, so an entry carrying an unhashable name raised `TypeError: unhashable type` where the tuple form simply did not match. That is a regression against `main`, and the exception is not a `CalibrationParseError`, so callers catching this module's documented error miss it. Guarded with an `isinstance` test; reverting the guard fails the two unhashable cases. | `0625ab4` |
| Acceptance criterion 2 was two thirds satisfied | The criterion asks the regression test to assert agreement with the loader "not hand-written values". T1 and T2 did. Readout could not, because no `mean_readout_error` existed, so the test re-derived it locally with a comprehension that filtered `None` but not NaN, a different skip policy than the vectorizer and its two siblings. Added `mean_readout_error` with the same ADR-017 contract, covered in the module that already covers the other two. | `0625ab4` |

At `0625ab4` the branch collected and passed **497**.

### Then main moved, and the merge was red

`main` reached `125b7962`, landing PR #68. That made this PR `DIRTY`, which
matters more than it sounds: `ci.yml` does not dispatch on a conflicting PR
while CodeQL keeps reporting green, so the checks would have stayed green while
nothing ran.

The merge conflicted in one file, `docs/numerical-claims.md`, and it was the
NC-021 row: both sides replaced it from the same `465` base, so git saw a
one-line text conflict with no hint that the two sides count different trees.
Resolved by keeping both narratives and re-measuring at the merge.

The real problem was not the conflict. PR #68's parameterization stack is
calibrated in **microseconds**: the committed survey TSV, the quantile layout
derived from it, `EXPECTED_ONSETS`, and the pinned clamp counts. This branch
makes `BasicCalibrationVectorizer` emit **seconds**. That is issue #66's own
defect one layer up, a consumer calibrated in one unit fed by a producer in
another, and the merge proved it rather than predicted it:

| | `mean_T1` on the reduced fixture |
| --- | --- |
| Committed survey TSV, microseconds | `155.1924205171878` |
| Merged tree's `extract`, seconds | `0.0001551924205171878` |

Same significant digits, 1e6 apart. **23 tests failed at the merge commit
`0276e1f`**, every one of them PR #68's.

### Where the boundary went, and why there

Both conventions are right for their own consumer, so neither is retired. What
was missing was a named place where they meet. `ArchiveUnitFeatureExtractor`
wraps any `CalibrationFeatureExtractor` and re-expresses its output in the
units the archive declares.

The factor is deliberately not a hardcoded 1e6. It is
`1 / UNIT_SCALE[EXPECTED_UNITS[field]]` per feature, which is exactly the
scaling `validate_unit_scale` applied on the way in, inverted. So the two
directions cannot drift apart independently, a dimensionless feature passes
through at `1.0` by construction rather than by a special case, and a feature
the module cannot map back to an archive field raises at construction instead
of passing through unscaled, which would be the precise error issue #66 exists
to close. It sits behind the ABC and mirrors `ClampingFeatureExtractor`, so the
composition is visible at the call site.

`scripts/feature_distribution.py` extracts through it. Its header used to say
the units were the vectorizer's own, the raw Nduv value with no scaling, and
that `FEATURE_SCALES` was not a source of truth. That sentence was true only
while the vectorizer was wrong. It now states that the units are the archive's,
that the conversion is explicit, and what breaks if the wrapper is removed.

PR #68's tests needed two corrections: its synthetic snapshots were unitless,
which this branch now rejects, and its clamps wrapped the SI vectorizer against
microsecond domain boxes. Editing another contributor's just-merged tests is
not done lightly, and the justification is narrow: this branch changes the
contract they were written against, so the alternative is leaving `main` red.
Two bare-vectorizer uses are deliberately kept, the metadata-forwarding
assertion and `NonFinite`, which overrides `extract` and never delegates.

### Mathematical / statistical details

Converting after the mean is not bitwise the same as converting before it. The
committed evidence was produced when the mean was taken over microseconds; it
is now taken over seconds and scaled afterwards, and each per-qubit scaling
rounds before the average. Measured across the archive:

| | |
| --- | --- |
| Rows differing | 733 of 975 |
| Columns differing | `mean_T2` 551 rows, `mean_T1` 494 rows, nothing else |
| Maximum relative difference | `2.8e-16`, about one unit in the last place |

Registered as NC-054. It is worth a row only because the README beside that TSV
tells a reader to re-run the command to reproduce it, and that instruction is
now false at the byte level while remaining true at every registered digit.
**NC-041's nine quantiles and NC-042's three spreads reproduce exactly** at the
precision they are registered to, which is the claim that actually matters; the
per-qubit spread columns behind NC-042 are byte-identical because they never
went through `extract` at all. The dated evidence TSV is not regenerated, per
the append-only rule for dated artefacts, and `tests/test_parameterization.py`
reads the committed file as its durable record and passes against it.

### Design decisions

Three options were weighed. Re-running the survey in seconds and re-registering
NC-041, NC-042, `EXPECTED_ONSETS` and the clamp counts would rewrite figures a
teammate registered two days earlier and invalidate committed evidence, to no
numerical benefit. Leaving the merge unresolved would have kept the PR `DIRTY`
and CI silent. Converting at the boundary keeps every registered number intact,
keeps ADR-010's seconds, and puts the conversion somewhere a reader can find
it. The cost is one wrapper class and the one-ULP drift recorded above.

### Gates at 0b36c64

Clean CPython 3.12.10 at a short path, running what CI runs:

```bash
ruff check .
ruff format --check .
python scripts/check_ids.py
mypy --strict
pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider
pytest tests/ -q -o addopts="" -p no:cacheprovider
```

All clean: 65 files formatted, no colliding identifiers, 37 source files typed,
and **652 collected, 652 passed**, registered as NC-021 measured at that commit.
Neither `616` nor `497` survives the merge and the value is not derived from
them. `main` was `125b7962` when this was measured; if it moves again,
re-measure at the new merge.

NC-053 was **not** used for the drift row: PR #102 already claims it for the
dashboard heartbeat bound. That is the collision git cannot show, because two
branches appending the same next id to different rows is a clean merge, so the
check is `gh pr list` before claiming an id, not `check_ids.py` afterwards.
NC-054 is the first genuinely free id.

---

## Fourth review follow-up, 2026-09-17

The PR #99 convention review re-ran the measurements this document registers.
Everything reproduced except one figure, and this section records the
correction. Per the append-only rule for dated documents, the tables above are
left exactly as they were written; this section is what supersedes them.

### The drift bound did not reproduce

The "Mathematical / statistical details" table in the third review follow-up
(line 359) registers:

| | |
| --- | --- |
| Maximum relative difference | `2.8e-16`, about one unit in the last place |

Re-running NC-054's own command at its own ref, at `d5c6165`, and comparing
row-wise against the committed TSV gives:

| | measured at `d5c6165` |
| --- | --- |
| Rows differing | 733 of 975 |
| Columns differing | `mean_T2` 551 rows, `mean_T1` 494 rows, nothing else |
| Maximum relative difference | `4.3300e-16`, a distance of **3 ULP** |
| Worst row | `snapshots/2026-07/ibm_fez/20260724T124953000000Z.json`, `mean_T2` |
| Worst `mean_T1` row | `4.2735e-16`, 2 ULP |

Every count reproduces exactly. Only the magnitude bound was wrong, and it was
wrong in the direction that understates the drift: `4.33e-16` is about 1.5x the
registered figure, and three units in the last place is not one.

The conclusion the figure supports is unaffected, and that was checked rather
than assumed. NC-041's nine quantiles and NC-042's three spreads were
regenerated from a fresh survey at the same ref and agree to every digit they
are registered to, and the `*_qubit_std` columns remain byte-identical because
they never pass through `extract`. So "physically meaningless" still holds at 3
ULP exactly as it would at 1. What failed was the number itself, and a register
row whose headline value does not reproduce from the command printed beside it
is the failure mode `docs/numerical-claims.md` exists to prevent, whatever the
number's size.

NC-054 is corrected to `4.3e-16, up to 3 ULP` and re-pinned from `0b36c64` to
`d5c6165`. The two commits between them are documentation only and cannot move
a survey, but Rule 6 asks for the commit a value was measured at, so the row
names the commit the re-measurement actually ran at rather than carrying the
old pin forward. The sentence in NC-054's notes reading "one unit in the last
place" is corrected in the same way.

Correspondingly, the design-decisions line at 379 calling the cost "the one-ULP
drift recorded above" should be read as **up to three ULP**. The trade-off it
describes is unchanged.

### Two stale unit statements outside the register

`docs/evidence/feature-distribution/README.md` still carried the pre-#66 units
paragraph: that the TSV's units are "the vectorizer's own, with no scaling
(NFR-8)", and that `scripts/first_ensemble_run.py::FEATURE_SCALES` "is in
seconds and is not a source of truth for anything here or downstream". Both
sentences are precisely what this issue refutes. The same two claims were
corrected in `scripts/feature_distribution.py`'s module docstring by the third
review follow-up, and the README beside the evidence was missed, which is
awkward given NC-054's own notes name that README as the reason the row exists
at all. A dated correction is appended there, leaving the original text intact.

Its sixteen-digit claim, that the first five rows share a `mean_T1` of
`155.1924205171878`, was checked against a fresh survey and still holds
exactly, so it is left alone.

NC-041's claim column named `BasicCalibrationVectorizer` as the unit source.
After this branch that producer emits SI seconds, so the label read as seconds
while every figure in the row is microseconds, an error of 1e6 sitting in the
one column a reader scans to find out what a number means. It now names archive
units, and the row's notes carry the correction plus a retraction of the older
clause calling `FEATURE_SCALES`'s seconds "a separate defect". They were never
a defect; the vectorizer was.

### Gates at this commit

Re-run in a clean CPython 3.12.10 at a short path, not the repository `.venv`:
`ruff check .` and `ruff format --check .` clean over 65 files,
`scripts/check_ids.py` clean, `mypy --strict` clean over 37 source files, and
**652 collected, 652 passed**, matching NC-021 at `0b36c64`. These four commits
are documentation only and change no collected test.

---

## Fifth review follow-up, 2026-09-17: the error-context hoist

The one code finding left open by round 4, now fixed.

### Problem

`extract` passed `validate_unit_scale` a `context=` string built inline:

```python
context=f"backend {snapshot.backend!r} at {snapshot.timestamp.isoformat()}",
```

That expression depends only on the snapshot, never on the qubit or the field,
so it is loop-invariant. It sat in the innermost loop and was therefore
evaluated once per consumed Nduv entry: **467 times** on a 156-qubit archive
document, each one calling `datetime.isoformat()` and formatting two values, to
build a string that is discarded unless a unit is wrong. On the happy path,
which is every document the archive actually holds, all 467 were thrown away.

### Fix

Hoist it above the loop and pass the local. That is the entire change: five
lines of comment, one new line, one call-site edit.

### Mathematical / statistical details

Registered as NC-055. Measured on
`snapshots/2026-08/ibm_fez/20260831T203902000000Z.json`, 156 qubits and 467
consumed Nduv entries:

| | before | after |
| --- | ---: | ---: |
| `extract` per snapshot | `0.84`-`0.88` ms | `0.28`-`0.32` ms |
| Context strings built | 467 | 1 |
| Speedup | | `2.76`-`2.99`x |

Two things about how that was measured, both of which changed the answer.

**It is stated differentially.** The pre-hoist `features.py` is read out of
`7bfe3de` with `git show` and exec'd as a second module beside the current one,
so both halves run in one process, on one document, interleaved, and differ
only by the hoist. The absolute millisecond figures measure the laptop; the
ratio measures the change, and only the ratio is the claim.

**The first two numbers I produced were both wrong, in opposite directions.**
The round-4 review estimated `69%` of runtime by timing the f-string alone
inside a lambda; that lambda carries its own call overhead and overstated the
share. A first differential attempt then timed the two halves in *separate*
processes and reported `1.91`x, which did not reproduce. Only the interleaved
form is stable, at `2.76`-`2.99`x over five independent processes. The figure
is **provisional, laptop**, superseded by the next Burak-desktop batch record
under architect decision C2, exactly as NC-044 is.

This is a real speedup on `extract` in isolation and close to nothing in any
caller that exists today. The archive survey spends its time in 975 `git show`
subprocesses and about 1.2 GB of JSON parsing, so `extract` is well under 1% of
it and NC-044's `55`-`64` s range is unmoved. The honest summary is that the
method was spending two thirds of its time building text nobody reads, and now
it does not.

### Verification

Behaviour preservation was shown, not asserted, in the way NC-052's notes
already establish for this branch's earlier refactors. Captured either side of
the hoist and diffed:

- all four NC-052 figures, byte-identical: `T1 0.0001551924205171878`,
  `T2 0.00010959537464376821`, readout `0.03532605293469551`, firing sum
  `0.10769113232875129`;
- the exact message text of all three of `extract`'s failure paths, a wrong
  unit, a missing unit and an unusable snapshot, byte-identical including the
  backend and timestamp the context string carries.

The third of those is the one that matters: the point of the context string is
to appear in an error, so a hoist that changed the message would be a
regression no figure would catch.

Gates at this commit, clean CPython 3.12.10 at a short path: `ruff check` and
`ruff format --check` clean over 65 files, `scripts/check_ids.py` clean,
`mypy --strict` clean over 37 source files, **652 collected, 652 passed**. No
test is added: the hoist is behaviour-preserving by construction and the
existing suite already pins both the figures and the error text it could have
broken, so a new case would assert an implementation detail. NC-021 is
therefore unchanged at 652.
