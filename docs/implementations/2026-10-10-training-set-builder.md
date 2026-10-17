# 2026-10-10: Training-set builder

Updated through 2026-10-17 to include the PR #113 review fixes. The changes are
committed locally on `feature/issue-63-training-set-builder`. Evidence is
regenerated from the source commit; publication and owner confirmations remain
pending.

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
| `src/superconducted/training/dataset.py` | Streaming pinned archive reader, earliest-state selection, archive-unit features, targets, weights and audit report. |
| `src/superconducted/calibration/loader.py` | Dict-level parser shared with the existing file loader, preserving validation and missingness accounting. |
| `scripts/build_training_set.py` | Deterministic TSV and source-aware README; separate exits for no usable rows and read/schema failures. |
| `tests/training/test_dataset.py` | Synthetic archive, real fixture, unit, accounting, digest-conformance and CLI regression checks. |
| `docs/evidence/training-set/` | Historical and pinned October-tip evidence, including commands and explicit source status. |
| `.gitignore` | UTF-8/LF ignore rules without NUL bytes, covering issue-specific pytest temporary directories. |
| `docs/team.md` | Three rows in the existing ownership table, using the existing reviewer names. |
| `docs/numerical-claims.md` | Provisional NC-070 through NC-075; existing main claims and NC-021's committed primary measurement remain intact. |
| `docs/decisions.md` | Descriptive ADR-013 revisit citing ADR-010 and dashboard digest agreement. |

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
without a traceback. The README records the actual builder source revision
and explicitly marks uncommitted source changes.

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
population standard deviation. Inverse UTC-hour row frequencies are normalized
to mean one; naive weighting timestamps are rejected. Both weight columns
are always emitted. No independence, floor or growth-sufficiency claim is made.

The committed-source historical reproduction yields 504 rows from 894 documents
with 390 duplicates (NC-073). The pinned October tip yields 797 rows from 1891
documents, 1094 duplicates and zero document skips (NC-070/NC-071). Its UTC 00-07
versus 16-23 counts are 230 versus 308 (NC-072). Digest conformance is covered
by NC-074; rounded machine-specific runtimes by NC-075. These measurements
are reproduced at source commit `6143f4279df3442fb34363934d01ef5636305fdf`.
The evidence README records rounded runtimes and deterministic-output checks.

## Design decisions

These are Baha Jarad's implementation choices, prepared by Codex under his
request to implement issue #63 and address the review. They do not claim
independent owner, consumer or advisor approval.

1. **Row timestamp:** use UTC `properties.last_update_date`, retaining parameter
   date bounds in the TSV. Mert Efe Şensoy's confirmation remains pending.
2. **Loader boundary:** share `parse_snapshot(data, source=...)` with
   `load_snapshot`. Existing loader regression tests guard the behavior;
   extraction requires neither temporary files nor a bypass parser.
3. **Digest body and packaging:** hash the bare qubit list rather than a wrapper.
   Keep a small implementation in the installable package and test byte equality
   with the workflow's stdlib-only digest. Package code cannot import the
   unshipped `scripts/` directory.
4. **ADR-013:** append a descriptive revisit and keep richer-extractor comparison
   deferred. Hand the advisor read to issue #56; Mert must obtain and record
   Dr. Akba's out-of-band response in
   `docs/advisor/2026-09-03-decisions-from-akba.md`. No approval is claimed.
5. **Parameter dates:** normalize them away only on mappings carrying `value`,
   matching `scripts/canonical_snapshot_digest.py::qubit_digest`. Baha Jarad
   explicitly requested dashboard alignment, implemented by Codex. UC-6 dashboard
   agreement is the rationale; this supersedes the issue's date-inclusive
   recommendation. TSV date bounds preserve the provenance.
6. **Spread carrier:** retain spread in the TSV and `BuildReport`, without
   adding a metadata field to the shared `TrainingSet` type.

No locked math, shared interfaces or shared types were edited by this work.
The existing gates-bearing fixture is consumed unchanged. Ownership rows
preserve main's current assignments and reviewer spelling.

## Verification

The current local branch is based on main
`6cf008da5b3dd8e25bbc20e69e96d21c4a161d15`, with source committed at
`6143f4279df3442fb34363934d01ef5636305fdf`. On 2026-10-17, the full suite directly
collected and passed **875 tests**, including 16 builder cases, using Python
3.12.10, numpy 2.4.4, qiskit 2.4.1, aer 0.17.2, mypy 1.20.2, pytest 9.0.3 and
ruff 0.15.12. Main's added Matplotlib dependency was installed in the isolated
environment. This supersedes the earlier local 825-test run against main
`fec055c`, before the figure tests were added.

Regression coverage includes builder/helper representative agreement,
init_error rejection and unchanged X with or without that field, invalid
T2 target skips, split-side timestamp inequalities, naive-hour rejection,
Git ls-tree/show failures, timestamp ties and repeatable TSV output. Fixture
paths are anchored to the test module. The repeatability test verifies that
both runs produced exactly one TSV rather than silently comparing an old file.

Both archive runs are regenerated at source commit `6143f427`, on the pinned
Python stack above. The [evidence README](../evidence/training-set/README.md)
records the full SHA, commands, row-level audit files and repeatability check.
Only the October 17 evidence pair is retained; earlier duplicate output sets
are excluded from this branch.

Lint, formatting, strict typing, identifier uniqueness, whitespace, ignore
encoding and absence of unmerged entries or tracked test gitlinks pass:

```sh
ruff check .
ruff format --check .
mypy --strict
python scripts/check_ids.py
git diff --check
git check-ignore -v .pytest-issue-probe/x .pytest-tmp-probe/x
python -m pytest tests/ -q
```

## Branch state and remaining publication steps

The branch contains only issue #63 code, tests, evidence and documentation
changes relative to live main `6cf008da`. The former conflicted head
`106c7fb7b17a5d433768d96d5a56e68990d59609` is preserved as
`backup/issue63-before-conflict-cleanup-20261017`. The temporary-file commits
and unrelated work from main are not introduced by the new issue commits.
Unresolved merge markers were removed, and no tracked test gitlinks remain.

The code commit is followed by a documentation/evidence commit. NC-021 is
updated in place from its prior committed value of 859 to the directly
measured 875 at `6143f427`. NC-070 through NC-075 cite that source commit,
the full archive refs and their evidence files. No working-tree measurements
are presented as final committed-source evidence.

Nothing has been pushed, so GitHub PR #113 will update only when the cleaned
branch is published. Before merging:

1. Recheck NC identifiers against main and update citations if concurrent
   changes have claimed the same IDs.
2. Publish decisions 1 through 6 from this document on issue #63 with their
   attribution and outstanding confirmations. No decision comment or advisor
   sign-off is implied by the local commits.
3. Apply the issue's PR labels: `priority:high`, `area:fuzzy`, `type:feature`,
   `area:calibration`; use its Phase 3 ANFIS results milestone.
4. Obtain owner, advisor and trainer-consumer confirmations and include the
   measurements in the canonical desktop batch verification record.

## Related docs

- [Issue #63](https://github.com/SuperconducTED/superconducted-noise-engine/issues/63)

