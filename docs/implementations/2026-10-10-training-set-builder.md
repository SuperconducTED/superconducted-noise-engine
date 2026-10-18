# 2026-10-10: Training-set builder

Updated through 2026-10-18. The published PR #113 and local branch
`feature/issue-63-training-set-builder` both point to `718d77e9`. Evidence
was generated at source commit `6143f427`; owner, advisor and consumer
confirmations remain pending. Local publication drafts and the remaining
coordination checklist are in [the publication and coordination section](#publication-and-coordination--2026-10-18).

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
changes relative to its recorded main base `6cf008da`. The former conflicted head
`106c7fb7b17a5d433768d96d5a56e68990d59609` is preserved as
`backup/issue63-before-conflict-cleanup-20261017`. The temporary-file commits
and unrelated work from main are not introduced by the new issue commits.
Unresolved merge markers were removed, and no tracked test gitlinks remain.

The code commit is followed by a documentation/evidence commit. NC-021 is
updated in place from its prior committed value of 859 to the directly
measured 875 at `6143f427`. NC-070 through NC-075 cite that source commit,
the full archive refs and their evidence files. No working-tree measurements
are presented as final committed-source evidence.

As checked on 2026-10-18, GitHub PR #113 points to local HEAD
`718d77e98498be8e071baa917ccdc762fc0abc28`, reports no merge conflicts,
and has successful Python 3.11 and 3.12 CI jobs. Those jobs include lint,
formatting, identifier uniqueness, strict typing and tests. This supersedes
this document's earlier unpublished-branch status.

A focused local rerun at that head passed 34 builder/loader tests on Python
3.14.5 after Windows sandbox restrictions on pytest temporary directories
were removed. Targeted Ruff and the identifier check also passed. This is
separate from NC-021's full-suite measurement on Python 3.12.10 at `6143f427`;
it does not replace that measurement or the desktop batch verification.

The [publication and coordination section](#publication-and-coordination--2026-10-18)
contains a replacement PR description, the issue #63 decision-comment draft,
metadata instructions and the owner/advisor/consumer requests. The issue
thread still had no comments and the PR had no labels or milestone at that
check. Posting these drafts, applying metadata and obtaining confirmations
remain external actions. Recheck NC identifiers against main before merging.

## Related docs

- [Issue #63](https://github.com/SuperconducTED/superconducted-noise-engine/issues/63)


## Publication and coordination ? 2026-10-18

Prepared for Baha Jarad. Text below is ready for publication; it has not been
posted by this cleanup. Pending requests are not recorded approvals.

PR: https://github.com/SuperconducTED/superconducted-noise-engine/pull/113

Issue: https://github.com/SuperconducTED/superconducted-noise-engine/issues/63

### Status and remaining actions

At the 2026-10-18 check, local HEAD and PR head were both
`718d77e98498be8e071baa917ccdc762fc0abc28`. GitHub reported the PR mergeable
with successful Python 3.11/3.12 CI and CodeQL checks. The issue had no
comments; PR labels and milestone were absent. These are dated observations.

- [ ] Replace the PR description with the draft below.
- [ ] Post the six-decision comment on issue #63 and link it from the PR.
- [ ] Record digest-body/date normalization agreement in issue #48, linking
      the issue #63 comment. This records the current choice; it cannot
      retroactively satisfy the original requirement to agree before coding.
- [ ] Apply `priority:high`, `area:fuzzy`, `type:feature`, `area:calibration`
      and the issue's `Phase 3 · ANFIS results` milestone to the PR.
- [ ] Obtain owner reviews from @mertefesensoy and @bengisucvd.
- [ ] Obtain @BurakOztekin's trainer-consumer confirmation.
- [ ] Ask Mert via issue #56 to obtain Dr. Akba's ADR-013 read and append the
      actual answer/date to `docs/advisor/2026-09-03-decisions-from-akba.md`.
      The handoff is prepared locally; delivery and approval are pending.
- [ ] Include NC-070–075 and the historical reproduction in the next canonical
      desktop batch verification record. Keep local measurements provisional.
- [ ] Recheck NC identifiers against current main and rerun required CI after
      subsequent changes before merging.

### Replacement PR description draft

Issue #63 needs a reproducible trainer dataset with one row per distinct device
state. This PR reads a pinned calibration archive through Git, selects the
earliest document per qubit digest, and produces a `TrainingSet` plus auditable
TSV evidence with features, physics targets, both weight columns, provenance
and skip accounting. The data branch is read-only.

The default `ArchiveUnitFeatureExtractor` explicitly converts the ADR-010 SI
vectorizer output to archive microseconds, matching T1/T2 spread columns.
Readout error and ADR-027 gamma/lambda targets are dimensionless. Uniform
weighting remains the default. Digests match the dashboard's bare qubit-list
hash with parameter dates normalized away; date bounds remain provenance.
This deliberately differs from issue #63's date-inclusive recommendation.

Review corrections include the unit boundary, NC-ID renumbering, committed
measurement provenance, UTF-8 ignore rules, cleaned temporary-file history,
ownership-table rows, shared filename decoding, naive-timestamp rejection,
CLI failure exits and the requested regression coverage.

Evidence was regenerated at builder source
`6143f4279df3442fb34363934d01ef5636305fdf`:

- Historical archive `f0930b9b54975470a4a87866cbc691f7897295cb`:
  504 states, 894 documents, 390 duplicates, zero document skips (NC-073).
- Pinned October archive `e5688d2f6a333e98bb01f1c1d81b694ff69574f5`:
  797 states, 1,891 documents, 1,094 duplicates (NC-070), with exclusions
  recorded in NC-071. This is a pinned measurement, not a live-tip count.
- UTC-hour bias, digest conformance and rounded local runtimes are NC-072,
  NC-074 and NC-075. No sample-sufficiency claim is made.

Validation: the recorded full suite passed 875 tests on Python 3.12.10 at
`6143f427` (NC-021). At published head `718d77e9`, Python 3.11/3.12 CI passed;
a separate local Python 3.14.5 builder/loader rerun passed 34 tests, and
targeted Ruff and identifier checks passed. The local evidence remains
provisional pending canonical desktop batch verification.

Before merge: publish the attributed decisions on #63 and digest agreement
on #48, apply labels/milestone, obtain owner reviews, trainer-consumer
confirmation and the advisor read via #56, and recheck claim IDs. These
confirmations have not been granted by this description.

See `docs/implementations/2026-10-10-training-set-builder.md`,
`docs/evidence/training-set/README.md`, NC-021 and NC-070–075.

### Issue #63 decision-comment draft

The following records Baha Jarad's implementation choices, prepared by Codex
under his request to implement #63 and address PR #113's review. Independent
reviewer, advisor and consumer confirmations remain pending.

1. **Row timestamp:** UTC `properties.last_update_date`; preserve parameter
   date bounds in TSV provenance. Mert's confirmation is requested.
2. **Loader boundary:** expose `parse_snapshot(data, source=...)` and share
   validation with `load_snapshot`, avoiding temporary files and bypass parsing.
3. **Digest body:** hash the canonical bare `properties.qubits` list. Keep
   package and stdlib dashboard implementations separate because `scripts/`
   is not shipped in the wheel; pin byte equality with conformance tests.
   Record this agreement on #48 as well; the original advance-agreement
   requirement was not fulfilled by a local implementation document.
4. **ADR-013 note:** retain the descriptive revisit; richer-extractor comparison
   remains deferred. The advisor-read request is prepared for #56 via Mert.
   Record Dr. Akba's actual answer and date in
   `docs/advisor/2026-09-03-decisions-from-akba.md` when received. No advisor
   approval or completed handoff is claimed here.
5. **Parameter dates:** Baha requested dashboard alignment (UC-6). Remove
   `date` only from mappings carrying `value`, matching
   `scripts/canonical_snapshot_digest.py::qubit_digest`; preserve other
   metadata and list order. This changes the issue's date-inclusive
   recommendation. Date-only republication therefore collapses to one state;
   date bounds remain in the TSV. Reviewer confirmation is requested.
6. **Spread carrier:** TSV and `BuildReport`, with the required column names
   and sample standard deviation (`ddof=1`); no shared-type metadata field.

X uses `ArchiveUnitFeatureExtractor` so T1/T2 means and spreads both use archive
microseconds; ADR-010 still governs the underlying SI vectorizer. Y delegates
to ADR-027 helpers. Evidence and claims cite source `6143f427`, not an
uncommitted tree. Historical reproduction is 504 states from 894 documents
(NC-073); the pinned October measurement is NC-070. Details and commands:
`docs/evidence/training-set/README.md`.

@mertefesensoy and @bengisucvd: please review PR #113 and the choices above,
including the timestamp and digest semantics. Mert: please route the ADR-013
read through #56 and record the advisor's response in the canonical register.
@BurakOztekin: please confirm that the emitted `TrainingSet` is consumable by
`HybridANFISTrainer.fit` and include these measurements in the next desktop
batch verification. Each request remains open until its response is recorded.

### Review follow-up note draft

The reviewed unit mismatch, claim-ID collisions, source provenance, ignore
encoding, temporary-file history and regression gaps are addressed in head
`718d77e9`. The current description and NC-021/NC-070–075 replace the old
NC-052–057 and working-tree measurements. The coordination checklist above
tracks the outstanding human confirmations and publication tasks.

The bot's unused-`SPREAD_NAMES` comment appears to be a false positive:
`scripts/build_training_set.py` imports it and expands it in the TSV column
list. The syntax-error comment refers to the earlier head; the current CLI
imports and runs in the passing builder tests. Thread resolution remains a
reviewer action.
