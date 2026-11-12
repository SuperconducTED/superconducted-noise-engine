# 2026-11-08: Issue #122 public training source

> **Superseded policy and results interpretation (2026-11-12).** PR #150's
> reviews found that factor 10 excludes real weak qubits and that the fitted
> models lose to constant baselines. This file records the original work;
> the correction, supported-version verification and rebuilt evidence are in
> [the review-fix record](2026-11-12-pr150-public-source-review-fixes.md).

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
