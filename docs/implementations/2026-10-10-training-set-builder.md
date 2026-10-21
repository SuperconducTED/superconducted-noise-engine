# 2026-10-10: Training-set builder

Implements issue #63 in PR #113. Evidence was generated at builder source commit
`6143f427`; the review fixes recorded under "Review history" below change no
selection, feature, target or weight code, so that provenance still describes
every row.

## Problem / Motivation

Issue #63 needs a trainer dataset whose rows count distinct device states,
not archive files. A pinned commit, deterministic TSV and explicit exclusions
make the sample auditable without checking out calibration-data.

Review at `7d26e89` found that main's ADR-010 vectorizer emits SI seconds while
the survey and training evidence use archive microseconds. It also identified
claim-ID collisions, invalid ignore-file encoding, temporary test repositories
in commit history, missing failure-path tests and incomplete source provenance.
The implementation below incorporates those corrections.

## What changed

| File | Description |
| --- | --- |
| `src/superconducted/training/dataset.py` | Streaming pinned archive reader, earliest-state selection, archive-unit features, targets, weights and audit report; `__all__` names the public surface. |
| `src/superconducted/calibration/loader.py` | Dict-level parser shared with the existing file loader, preserving validation and missingness accounting. |
| `scripts/build_training_set.py` | Deterministic TSV and source-aware README; separate exits for no usable rows and read/schema failures. |
| `tests/training/test_dataset.py` | Synthetic archive, real fixture, unit, accounting, digest-conformance and CLI regression checks. |
| `docs/evidence/training-set/` | Historical and pinned October-tip evidence, commands, explicit source status, and the decision-5 digest comparison. |
| `.gitignore` | UTF-8/LF ignore rule covering issue-specific pytest temporary directories. |
| `docs/team.md` | Three rows in the existing ownership table, using the existing reviewer names. |
| `docs/numerical-claims.md` | NC-070 through NC-076; NC-021 updated in place. |
| `docs/decisions.md` | Descriptive ADR-013 revisit citing ADR-010, dashboard digest agreement and the lead's sign-off. |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | Appended 2026-10-21 decision entry: the lead's sign-off on the ADR-013 note (issue #63 decision 4). |

## Implementation approach

Resolve the archive ref to a full SHA, list paths once, then parse one JSON
at a time through `git show`. Retain only numeric summaries and digest keys.
Replace a representative when a document with an earlier
`(last_update_date, full archive path)` arrives. Sort summaries by that key
before constructing `TrainingSet`.

Selection precedes usability. A later usable copy cannot rescue an unusable
first representative. Every document is a row, duplicate or exactly one
counted document skip. `BuildReport` carries row metadata, qubit target skips
and kept-row loader missingness without changing shared types. Invalid JSON
is counted as a parse error; Git read failures propagate to the CLI handler.

`ArchiveUnitFeatureExtractor` is the default. The snapshot timestamp uses
`calibration/storage.py::_decode_filename_stem`; the row timestamp is UTC
`properties.last_update_date`. Distinct states sharing that timestamp raise
`ArchiveTimestampError`. Parameter-date bounds remain TSV provenance.
Injected extractors must follow the documented archive-unit contract.

The CLI returns 0 on success, 1 only for `NoUsableRowsError`, and 2 for invalid
refs, Git read failures or ambiguous timestamps. Failures include diagnostics
without a traceback and write nothing. The README records the actual builder
source revision and explicitly marks uncommitted source changes.

## Mathematical / Statistical details

The SHA-256 body is canonical bare `properties.qubits`, with sorted mapping
keys and compact JSON separators. Remove `date` only from parameter mappings
with a `value` key, matching the dashboard; preserve names, units, values and
list order. Deduplication is global, including nonconsecutive repeats.

ADR-010 governs `BasicCalibrationVectorizer`'s SI coherence outputs.
`ArchiveUnitFeatureExtractor` explicitly converts those back to the source
microseconds used by the survey/quantile stack (issue decision A15). X and
T1/T2 spread therefore use the same scale; readout error is dimensionless.
Per-field spread uses the extractor's finite-value filter, ddof=1 sample
standard deviation and p10/p50/p90. Singleton standard-deviation cells are
empty. Tests allow the rounding inherent in SI conversion and inverse scaling.

Y delegates to `gate_lengths`, `qubit_targets` and `snapshot_target` under
ADR-027. Per-qubit `sx` durations and coherence inputs use SI seconds; gamma
and lambda are dimensionless. Gamma spread follows the target helper's
population standard deviation. No independence, floor or growth-sufficiency
claim is made.

**Hour-of-day weights.** With `n` rows, `h(i)` the UTC hour of row `i`'s
timestamp, `c_h` the number of rows in hour `h`, and `H` the number of hours
with at least one row, `hour_of_day_weights` computes `r_i = 1 / c_{h(i)}` and
returns `w_i = r_i / mean(r)`. Since `sum_i r_i = H`, this is
`w_i = n / (H * c_{h(i)})`: `mean(w) = 1`, and every populated hour carries the
same total weight `n / H`. An empty hour contributes no row, so nothing
divides by zero; with all 24 hours populated this is issue #63's
`n / (24 * c_h)`. Naive timestamps are rejected rather than read in the
machine's timezone. Both weight columns are always emitted; `TrainingSet.weights`
is the uniform one unless `weighting="hour_of_day"`.

The committed-source historical reproduction yields 504 rows from 894 documents
with 390 duplicates (NC-073). The pinned October tip yields 797 rows from 1891
documents, 1094 duplicates and zero document skips (NC-070/NC-071). Its UTC 00-07
versus 16-23 counts are 230 versus 308 (NC-072). Rounded machine-specific
runtimes are NC-075. These measurements are reproduced at source commit
`6143f4279df3442fb34363934d01ef5636305fdf`.

**Digest definitions, measured on the real archive.** Let `D` be the `ibm_fez`
documents at a ref, `q(d)` the builder's digest and `q_dash(d)` the dashboard's
`qubit_digest`, and `q_incl(d)` the date-inclusive digest issue #63 originally
specified (the same body with every parameter `date` kept). Conformance is the
count of `d` in `D` with `q(d) == q_dash(d)` byte for byte (NC-074). Decision 5's
comparison is `|q(D)|` against `|q_incl(D)|`: the number of distinct states
under each definition (NC-076). Because `q_incl` only adds information, every
state under `q` splits into one or more states under `q_incl`, so
`|q_incl(D)| >= |q(D)|`. The gap is the number of extra states that differ
from another only in a parameter's `date`.

Measured: the builder digest equals `qubit_digest` on 894 of 894 documents at
`f0930b9` and 1891 of 1891 at `e5688d2` (NC-074). The two definitions both give
504 states at `f0930b9`, and 797 against 798 at `e5688d2`, where one state
splits in two on parameter dates alone (NC-076). The count is reported, not
used: the builder keeps the dashboard definition (decision 5).

## Design decisions

The implementation choices are Baha Jarad's, prepared by Codex under his
request to implement issue #63 and address the review. The six decisions issue
#63 asked to settle are recorded on the issue, with who decided each, in
[#63 (comment)](https://github.com/SuperconducTED/superconducted-noise-engine/issues/63#issuecomment-6313102883):

1. **Row timestamp:** use UTC `properties.last_update_date`, retaining parameter
   date bounds in the TSV. Confirmed by Mert Efe Şensoy on 2026-10-21.
2. **Loader boundary:** share `parse_snapshot(data, source=...)` with
   `load_snapshot`. Existing loader regression tests guard the behavior;
   extraction requires neither temporary files nor a bypass parser.
3. **Digest body and packaging:** hash the bare qubit list rather than a wrapper.
   Keep a small implementation in the installable package and test byte equality
   with the workflow's stdlib-only digest. Package code cannot import the
   unshipped `scripts/` directory.
4. **ADR-013:** append a descriptive revisit and keep richer-extractor comparison
   deferred. The advisor read is Mert Efe Şensoy's sign-off as lead in the
   advisor role, recorded on 2026-10-21 in
   `docs/advisor/2026-09-03-decisions-from-akba.md`. It covers the note only.
5. **Parameter dates:** normalize them away only on mappings carrying `value`,
   matching `scripts/canonical_snapshot_digest.py::qubit_digest`. Baha Jarad
   explicitly requested dashboard alignment, implemented by Codex. UC-6 dashboard
   agreement is the rationale; this supersedes the issue's date-inclusive
   recommendation and was confirmed by Mert Efe Şensoy on 2026-10-21. The
   date-inclusive count is kept as the measured, unused number the issue asked
   for (NC-076). TSV date bounds preserve the provenance.
6. **Spread carrier:** retain spread in the TSV and `BuildReport`, without
   adding a metadata field to the shared `TrainingSet` type.

No locked math, shared interfaces or shared types were edited by this work.
The existing gates-bearing fixture is consumed unchanged. Ownership rows
preserve main's current assignments and reviewer spelling.

## Verification

On 2026-10-17, at source commit `6143f4279df3442fb34363934d01ef5636305fdf`
based on main `6cf008da5b3dd8e25bbc20e69e96d21c4a161d15`, the full suite
collected and passed **875 tests**, including 16 builder cases, using Python
3.12.10, numpy 2.4.4, qiskit 2.4.1, aer 0.17.2, mypy 1.20.2, pytest 9.0.3 and
ruff 0.15.12, with main's Matplotlib dependency installed. CI reported 874 passed and 1 skipped on Python 3.11 and 3.12 (875 collected)
at `b447ed8` (run 39151288067) and again at `07354d3` (run 39580563318), after
the round-1 review fixes, which edit two existing tests and add none. The skip is
`test_feature_distribution.py::test_the_committed_survey_reproduces_from_the_archive`,
which skips when `calibration-data` has not been fetched.

Regression coverage includes builder/helper representative agreement,
init_error rejection and unchanged X with or without that field, invalid
T2 target skips, split-side timestamp inequalities, naive-hour rejection,
Git ls-tree/show failures that write nothing, timestamp ties and repeatable TSV
output. Fixture paths are anchored to the test module. The repeatability test
verifies that both runs produced exactly one TSV rather than silently comparing
an old file.

Both archive runs are regenerated at source commit `6143f427`, on the pinned
Python stack above. The [evidence README](../evidence/training-set/README.md)
records the full SHA, commands, row-level audit files, the repeatability check
and the digest-definition measurement.

```sh
ruff check .
ruff format --check .
mypy --strict
python scripts/check_ids.py
git diff --check
python -m pytest tests/ -q
python scripts/build_training_set.py --ref f0930b9 --backend ibm_fez --out <scratch dir>
```

The last command reproduces the committed `2026-10-17-f0930b9b.tsv` byte for
byte (SHA-256 `007c8089...`, NC-073) whenever the builder source is unchanged.

## Review history

- **2026-10-13, review at `7d26e89`** (changes requested): units after the
  ADR-010 merge, NC collisions, working-tree provenance, ruff, ignore-file
  encoding, temporary files in history, undecided issue decisions, test gaps.
  Addressed in `6143f427` and `718d77e9` by Baha Jarad.
- **2026-10-21, re-review at `b447ed8`**: code, tests and register verified
  fixed (CI green; the historical TSV reproduced byte for byte). Open items were
  publication ones: the PR description, the issue #63 decision record, unsent
  drafts in this document, the advisor handoff to closed issue #56, the dropped
  decision-5 comparison, an `__all__` for the code-quality bot, `--out` in two
  failing-path CLI tests, and labels. Fixed on the PR branch by Mert Efe Şensoy;
  the PR conversation lists each fix against its finding.
- **2026-10-21, independent review of `07354d3`** (approved, with minors and
  nits): NC-021's provenance sentence and separator, the historical ref's skip,
  missingness and histogram figures under NC-073, the ADR-013 note's evidence
  refs and row counts (amended with the lead's re-confirmation), a leftover
  to-do in the generated README text, `BuildReport` field documentation, an
  explicit raise for the FR-10 identity, the `archive_ref` test against
  `git rev-parse HEAD`, and the hour-weight notation above. Fixed on the PR
  branch in a second round.

## Related docs

- [Issue #63](https://github.com/SuperconducTED/superconducted-noise-engine/issues/63)
  and its [decision record](https://github.com/SuperconducTED/superconducted-noise-engine/issues/63#issuecomment-6313102883)
- [Evidence README](../evidence/training-set/README.md)
- [Numerical claims](../numerical-claims.md): NC-021, NC-070 through NC-076,
  and NC-025, which NC-073 reproduces
- [ADR ledger](../decisions.md): ADR-010 (SI units), ADR-013 (feature
  engineering, revisited), ADR-017 (skip strategy), ADR-027 (training target)
- [Advisor decision register](../advisor/2026-09-03-decisions-from-akba.md):
  the 2026-10-21 entry
