# 2026-11-08: Issue #122 public training source

> **Superseded policy and results interpretation (2026-11-12).** PR #150's
> reviews found that factor 10 excludes real weak qubits and that the fitted
> models lose to constant baselines. This file records the original work;
> the correction, supported-version verification and rebuilt evidence are in
> [the review-fix record](#updates-after-pr-150-review-2026-11-12).

## Problem / Motivation

Issue #122 asks the distinct-state builder to evaluate the earlier public
`ibm_fez` event history as a second source. ADR-029 separates that evaluation
from the IBM-only archive. The issue's pasted text predates PR #121's corrections:
the applicable acceptance figures are NC-078's complete-state count and excluded
startup marks, not the original incomplete-state count.

## What changed

| File | Change |
| --- | --- |
| `training/public_archive.py` | Hash-pinned, column-allowlisted, hourly event replay and completeness audit. |
| `training/dataset.py` | Opt-in public source, source provenance, IBM precedence and overlap removal. |
| `training/targets.py` | Factor-10 NC-041 plausibility box and a distinct per-qubit skip reason. |
| `scripts/build_training_set.py` | Public-file option, source columns, replay audit, separate output filename. |
| `scripts/compare_training_sources.py` | Source quantile survey before fit and shared IBM holdout comparison. |
| `pyproject.toml` | Optional Parquet reader and Windows timezone dependency. |
| Tests | Replay, provenance, unit defect, guarded target physics and holdout isolation. |

Paths in the first column are relative to `src/superconducted/` where appropriate.

## Implementation approach

The reader verifies the registered parquet bytes before decoding a fixed list of
columns. Arrow filters to the selected backend, properties and time window. SN
is never requested. Events are ordered by calibration time and observation time;
the first observation wins a republished stamp. Replaying a mark uses no later
calibration event. Historical backfill may have been observed later, as the
existing evidence README explains; this is retrospective state reconstruction.

Each complete state is identified by the evidence script's all7 projection, with
qubit 72's T1/T2 excluded. Gate-duration changes alone do not create a device
state. The earliest hourly representative enters the existing loader/feature/
target path. Its synthetic document exists in memory only. An IBM document with
the same projection suppresses the public representative, even when IBM's target
is unusable. Original IBM document digests and deduplication stay intact.

The public audit counts hourly marks, incomplete marks, distinct complete states,
cross-source overlap and rescaled events before training-target admissibility.
`BuildReport.documents` counts IBM documents plus non-overlapping complete public
representatives; the original accounting identity still holds. The public audit
distinguishes representatives from replay marks. Kept TSV rows carry source and
revision, with the parquet hash for public rows; public `TrainingSet.provenance`
also contains the dataset revision and projected state digest.

## Mathematical / Statistical details

For each coherence field, the inclusive SI admissible interval is
`[p1 / factor * 1e-6, p99 * factor * 1e-6]`, using NC-041's registered archive
microsecond bounds. The user selected factor 10. The guard applies to both
sources after parsing and before target calculation, with its own first-match
skip reason. It intentionally excludes some physically possible short-coherence
tails; it is a training policy, not a benchmark-reference policy.

The target formulas remain ADR-027's amplitude/phase damping formulas. Feature
means still use the vectorizer's finite-value mask; the target guard acts on
per-qubit target eligibility. This does not rewrite source measurements or
silently clamp outliers.

Quantiles use NumPy's linear method and equal weight per distinct kept state,
reported separately for IBM, public and combined rows. This differs from the
file-weighted original NC-041 survey and does not silently supersede it.
The source comparison uses a fixed chronological IBM-only holdout starting
2026-09-23T00:00:00Z. Each fit re-derives its Gaussian grid from its training
features only, so the comparison changes both the data and membership grid.
The warm start uses constant training-target means; the shipped trainer fits
consequents with fixed premises and ridge regularization. Its settings and
diagnostics are stored in `fit-comparison.json`. These are derived-target
errors, not hardware validation, an ensemble decision or a claim of improved
transferability. Inspect both target errors: adding public rows need not improve
both outputs.

## Design decisions

ADR-029 is recorded **Open**, with a concrete proposed adoption decision.
The draft records the lead's approval of the three provenance rules as the
basis for evaluation. It does not record final adoption approval, which remains
owed. No external approval, canonical desktop verification or merge is claimed.
The selected source remains opt-in while that verdict is pending.

The exact public boundary follows NC-078: before the first IBM document at
2026-05-13T12:13:22Z, including that date's earlier hourly marks. Stopping at
midnight would measure a different window. If an archive starts earlier,
public replay stops earlier rather than overlapping its own window.

## Verification

Local results on Baha's Windows workspace are provisional; the canonical desktop
batch is still required by `docs/team.md`. The run used a downloaded parquet
under ignored `data/`; that temporary input was deleted during cleanup on
2026-11-11. Download it again before rebuilding. No push, archive write,
checkout, fit upload or remote change was performed.

Run the following from the repository root to reproduce the evaluation. Outputs
go to ignored `data/issue122-reproduction/` so the saved November 8 evidence
remains unchanged. The builder names its TSV with the current UTC date; the
comparison command selects the newly generated file.

```powershell
.venv/Scripts/python.exe -m pip install -e '.[dev,public-archive]'
curl.exe -f -L 'https://huggingface.co/datasets/phanerozoic/qiskit-calibration-drift/resolve/0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d/data/train-00000-of-00001.parquet' -o data/issue-122-public.parquet
# The pinned archive commit must already be available locally; see the evidence README.
.venv/Scripts/python.exe -m scripts.build_training_set --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --backend ibm_fez --public-parquet data/issue-122-public.parquet --out data/issue122-reproduction
if ($LASTEXITCODE -ne 0) { throw 'Training-set build failed' }
$trainingTsv = Get-ChildItem data/issue122-reproduction -Filter '*-5828b4a2-public.tsv' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.venv/Scripts/python.exe -m scripts.compare_training_sources --training-tsv $trainingTsv.FullName --cut 2026-09-23T00:00:00Z --out data/issue122-reproduction/comparison
.venv/Scripts/python.exe -m ruff check src scripts tests
.venv/Scripts/python.exe -m ruff format --check src scripts tests
.venv/Scripts/python.exe scripts/check_ids.py
.venv/Scripts/python.exe -m mypy --strict
.venv/Scripts/python.exe -m pytest tests/
```

Final local results: all tests collected in NC-021 pass. The targeted training
and reference suite also passes. Ruff lint and formatting over `src`, `scripts`
and `tests`, strict mypy, identifier collision checking and `git diff --check`
pass. The public build reproduces corrected NC-078; the IBM-only build at
`f0930b9b54975470a4a87866cbc691f7897295cb` reproduces NC-025. Both commands and
their audits are recorded in the new evidence README. The optional reader was
tested with PyArrow 26.0.1; this environment uses Python 3.14.5, outside the
CI matrix, so CI's supported-version runs remain a separate merge gate.

The source-data download URL and original pinned evidence reproduction remain
in `docs/evidence/public-archive-overlap-2026-10/README.md`. The generated README
records the exact replay audit and skip counts; the comparison directory records
the survey, input TSV hash and fits. The build reproduces corrected NC-078's
complete-state union; the existing NC-025 acceptance uses the same unmodified
IBM deduplication path. The test outcomes above describe the November 8 run;
the documentation review on November 11 checked the saved evidence and source
without rerunning the full suite or downloading the public input again.

## Related docs

- Issue #122; builder Issue #63; ADR-020, ADR-025, ADR-027 and Open ADR-029.
- NC-012, NC-025, NC-041 and NC-077 through NC-079.
- `docs/evidence/issue-122-training-set/comparison/results.md`.
- `docs/decisions/drafts/ADR-029-public-calibration-archive-as-training-source.md`.

## Updates after PR #150 review (2026-11-12)

Added to this document on 2026-11-13. These updates supersede the original
factor-10 policy and fit interpretation above; the original implementation
record is retained for history. Verification results and remaining actions
below describe the November 12 review-fix session.

### Problem / Motivation

The [lead's review](https://github.com/SuperconducTED/superconducted-noise-engine/pull/150#pullrequestreview-5854299784)
and [Burak's review](https://github.com/SuperconducTED/superconducted-noise-engine/pull/150#pullrequestreview-5867194376)
identified a unit-error guard that removed real weak qubits, skipped reader tests
in CI, a public target based on one qubit, and a fit comparison lacking a constant
baseline. These corrections supersede the factor-10 policy and interpretation
in the November 8 implementation record. Final ADR-029 adoption remains Open.

### What changed

| File | Change |
| --- | --- |
| `src/superconducted/training/targets.py` | Widen the unit-error guard to factor 1000 as proposed in review. |
| `tests/test_reference.py`, `tests/training/test_targets.py` | Restore reference-mask agreement and NC-039's registered gap; test weak real qubits and mislabelled seconds. |
| `requirements-dev.txt`, reader tests | Pin PyArrow and require it in reader tests instead of silently skipping them. |
| `src/superconducted/training/dataset.py` | Reject public representatives with insufficient target coverage and audit per-source target skips. |
| `src/superconducted/training/public_archive.py` | Record coverage policy/skips and excluded qubit-72 rescale events separately. |
| `scripts/build_training_set.py` | Report the coverage skip, source-specific guard effect, Python version and requirements hash. |
| `scripts/compare_training_sources.py` | Add training-mean constant baselines and feature-range diagnostics for the shared holdout. |
| Decision/evidence/claims records | Withdraw the original fit interpretation and register edits; retain historical artifacts with a supersession notice. |

### Implementation approach

The code changes are anchored in local commit
`cd20cc3788539cba04870bf6e26bbd5f3e9fed6c`. The rebuilt evidence names this
immutable commit without an uncommitted-source qualifier. Documentation-only
corrections and new evidence are recorded after that source commit.

The public completeness rule and hourly replay do not change. A complete state
is counted before checking target coverage. A public representative with fewer
than 100 usable per-qubit targets is skipped as `target_coverage_insufficient`,
including when there are no usable targets. The cutoff is a stated conservative
coverage policy, not fitted to improve a holdout score. It does not apply a new
coverage requirement to IBM documents. Boundary tests cover 0, 1, 99 and 100
usable targets; state-count and accounting assertions are retained.

The builder separates target skip counts by source. It also records the small
seconds-valued events dropped for qubit 72: these explain the difference between
the whole-table defect counts and the reader's post-exclusion rescale counts.

### Mathematical / Statistical details

NC-041 measures snapshot means; its factor-10 box was too narrow when applied to
individual qubits. The factor-1000 proposal sets each inclusive lower bound to
`p1 / 1000` and upper bound to `p99 * 1000`, converted from microseconds to SI.
This retains measured weak qubits while rejecting seconds values falsely
labelled as microseconds. The guard keeps its own `coherence_implausible` reason
and still precedes the T2 <= 2*T1 check. The ADR-027 target formulas are unchanged.

For each source choice, the baseline predicts that training set's target mean
on the same chronological IBM-only holdout. Its RMSE is the square root of the
mean squared difference from that constant. No holdout target is used to choose
the constant. The fitted model and baseline are both reported; feature-range
diagnostics count holdout points outside each training feature's min/max range.

The Gaussian grids continue to be derived independently from each training set.
Thus this comparison changes both the source rows and the membership grid.
It remains exploratory and is not informative evidence of a source improvement
yet. No source-fit claim is registered. The numerical register's NC-021 and
NC-038 through NC-040 edits from the original PR are withdrawn: the former is
owned by the merge-time count procedure; the fixture's original target and gap
checks are restored rather than redefined.

### Design decisions

Factor 1000 is the lead's review proposal, not an invented final adoption
approval. ADR-029 remains Open. The raw archive, reference-model physics,
IBM precedence, immutable public revision/hash and SN column exclusion remain
as before. PyArrow is pinned in test requirements so the CI jobs run the reader
tests on their supported versions; the runtime extra remains optional.

### Verification and reproduction

The supported-version runs use Python 3.11.15 and 3.12.10 with
`requirements-dev.txt`; PyArrow is 26.0.1 and NumPy is 2.4.4. These are local
Windows runs, not GitHub CI or canonical desktop verification. The evidence
builds use Python 3.12.10 at the source commit above.

Both full suites passed without skips: 1,069 tests on each supported version.
The final reader-only regression run also passed all nine tests. Ruff lint and
formatting, strict mypy, identifier collision checks and `git diff --check`
passed. These counts describe this branch, not the latest-main merge; NC-021
is deliberately not edited to register a branch test count.

The IBM-only acceptance rebuild keeps all 504 states. Joined by `qubit_digest`
to `docs/evidence/training-set/2026-10-17-f0930b9b.tsv`, every gamma, lambda,
usable-target-qubit count and input feature is exactly equal to the original
unguarded value. Its audit records no `coherence_implausible` skips. The fixture
again has 155 usable targets and reproduces NC-039's original gap, pinned by
the restored test.

The real-Parquet rebuild reproduces 625 complete public states and 14 incomplete
marks, with one IBM overlap. The complete-state union remains 1,548; rejecting
the single sparse-target representative leaves 1,547 usable training rows.
Neither source has any `coherence_implausible` qubit skips with factor 1000.
The new survey and comparison use those kept rows. Both fits still lose to the
constant baselines for both outputs; the comparison is therefore reported as
not informative evidence of an improvement. See the evidence README for the
count reconciliation and `comparison/results.md` for every fit and baseline.

The pinned public file must first be downloaded using the URL in the original
evidence README. From the repository root, with the pinned environment active:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python -m pytest tests/ -q -p no:cacheprovider
python -m ruff check src scripts tests
python -m ruff format --check src scripts tests
python -m mypy --strict
python scripts/check_ids.py
python -m scripts.build_training_set --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --backend ibm_fez --public-parquet data/issue-122-public.parquet --out data/pr150-reproduction
if ($LASTEXITCODE -ne 0) { throw 'Training-set build failed' }
$trainingTsv = Get-ChildItem data/pr150-reproduction -Filter '*-5828b4a2-public.tsv' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -m scripts.compare_training_sources --training-tsv $trainingTsv.FullName --cut 2026-09-23T00:00:00Z --out data/pr150-reproduction/comparison
python -m scripts.build_training_set --repo . --ref f0930b9b54975470a4a87866cbc691f7897295cb --backend ibm_fez --out data/pr150-reproduction/ibm-only
```

Use the recorded source commit to reproduce its source revision label exactly.
The builder uses the run's UTC date in filenames, so the commands select the
newly generated TSV rather than assuming the date of the original run.
Saved review artifacts are under
`docs/evidence/issue-122-training-set/review-2026-11-12/`; the November 8 outputs
remain explicitly historical.

### Remaining remote and merge actions

During the November 12 review-fix session, nothing was pushed. The PR body, labels and milestone were not modified
remotely. The updated PR summary should say that the comparison is exploratory
and not informative evidence of an improvement, and include the constant
baselines. The review requested the issue's labels (`priority:high`,
`area:calibration`, `type:research`) and milestone (`Phase 4 · Design-time predictor`).
Do not mark reviewer approval or canonical desktop verification complete.

Suggested replacement for the PR's result sentence:

> The review rebuild preserves real-qubit targets, runs the Parquet tests on
> supported Python versions, and skips insufficient public target coverage
> separately from complete-state counting. The with/without-source fits are
> exploratory and not informative evidence of an improvement: both lose to
> their training-target-mean baselines. Final adoption and canonical desktop
> verification remain pending.

The fetch of latest main was not approved during the November 12 review-fix session. Therefore this work
does not claim a merge with current main or resolution against unseen changes.
When integrating, retain main's merge-anchored NC-021 row and place ADR-029
before ADR-030 if the latter has landed. No changes to ADR-030 are proposed here.

### Related docs

- Open ADR-029 in `docs/decisions.md` and its authoring draft.
- NC-025, NC-038 through NC-041 and corrected NC-078.
- `docs/evidence/issue-122-training-set/review-2026-11-12/README.md`.
