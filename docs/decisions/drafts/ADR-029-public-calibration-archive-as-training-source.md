# ADR-029: Public calibration archive as a training-set source, not an archive source

**Status**: Proposed (draft, 2026-10-23). Not yet in `docs/decisions.md`; the ledger entry
lands with the pull request that adopts or rejects this. On 2026-10-23 the lead accepted the
three provenance rules of decision 3 as the basis for this draft, chose `ibm_fez` only, and
chose evaluate-then-adopt over adopt-now; the data-track owner's read (open question 1) and
the plausibility-box factor (open question 2) are still owed.

**Deciders**: Mert Efe Şensoy (lead; advisor role since 2026-10-03), Baha Jarad (data track,
owner of `calibration/` and of Issue #63's builder), Bengisu Cıvdı (reviewer who reproduced
NC-028).

## Context

The training floor is 1,170 distinct device states (NC-012, from NC-045's 234 parameters).
The project's own `calibration-data` branch holds 924 at `5828b4a2` (2026-10-23, `ibm_fez`
only, hourly polling since 2026-05-13). Every phase-3 plan has treated reaching the floor as a
calendar problem.

A public dataset, `phanerozoic/qiskit-calibration-drift` on Hugging Face (code at GitHub
`CharlesCNorton/qiskit-calibration-drift`, CC-BY-4.0 except its `SN` column, CC-BY-NC-4.0),
polls `backend.properties()` on every IBM Heron device every 30 minutes with historical
backfill and has held `ibm_fez` since 2026-01-31. It is an *event table*, one row per
`(backend, property, qubit_a, qubit_b, calibrated_time)`, not a store of IBM documents.

The 2026-10-23 cross-check (`docs/evidence/public-archive-overlap-2026-10/`, rows NC-077 to
NC-079) established:

- **Values agree.** Of 4,363,658 calibration events in our archive, 4,178,551 are present in the
  public table with the identical double. Zero disagreements in T1, T2, readout error, gate
  error or gate length. The 780 matched-but-different events are confined to `readout_length`
  and three `measure*_threshold` properties and are explained by the public table keeping the
  first value seen per stamp.
- **Documents reproduce.** Replaying the public table as of `calibrated_time` reproduces our
  qubit block bit for bit at 2,145 of 2,249 document timestamps; every mismatch is a round their
  poller missed, never a value conflict.
- **The gap closes.** For `ibm_fez` from 2026-01-31 to 2026-05-13, the replay yields 626 distinct
  device states at hourly marks (666 at half-hourly), one already in ours. The union with our
  924 is 1,549 (1,589), above the 1,170 floor. NC-078. Distinct is not independent (NC-012).
- **Three defects, each handled by a stated rule.** (1) T1 and T2 rows observed live before
  2026-05-07 hold seconds under the label `us`: 14,609 T1 and 14,947 T2 rows, none in the
  ambiguous zone between 0.01 and 1, no key with two representations. The dataset's own
  2026-05-20 report acknowledges the two conventions; the poller's rewrite on 2026-05-20
  (`7572634c`) fixed the forward path, and a later relabelling put `us` on the old rows without
  rescaling them. (2) IBM omits qubit 72's T1 and T2 from live documents and an event table
  cannot express omission, so a replay carries a stale February value forever unless the two
  keys are dropped. (3) First value per stamp, above.
- **Our loader would not catch defect 1.** `calibration/loader.py` validates the unit *label*
  against `EXPECTED_UNITS` and scales by 1e-6; a seconds value labelled `us` passes, becomes
  4.8e-11 s, and `training/targets.py` rejects only non-finite and non-positive values, so
  $\gamma = 1 - e^{-t/T_1}$ saturates at 1 silently.

## Decision (proposed)

1. **The `calibration-data` archive stays IBM-only.** ADR-020 stores `BackendProperties`
   documents as IBM served them, with `target` and `configuration` projections. A snapshot
   reconstructed from the public event table has no `target`, `configuration`, `general` or
   `backend_version`, carries a synthetic `last_update_date`, and cannot express a field IBM
   stopped publishing. It is not admissible to the archive or to ADR-025's ledger.
2. **The public table is admissible as a second `TrainingSet` source,** for `ibm_fez` only and
   for the window before 2026-05-13 only, through Issue #63's builder (Baha's module), behind a
   source tag on every row so a fit can be reported with and without it. Inside our own window
   our documents are authoritative; the public table is not merged into them.
3. **Three rules travel with the source and are recorded in the builder, the evidence README and
   the results doc:** scale T1/T2 below 0.01 `us` by 1e6; drop qubit 72's T1 and T2; where a
   stamp carries two values prefer ours (none occur in T1, T2, readout error, gate error or gate
   length).
4. **A plausibility guard on T1 and T2 enters the loader path** before any public row is fit:
   values outside NC-041's `[p1, p99]` box, widened by a stated factor, are rejected with their
   own skip reason in `training/targets.py`, so defect 1 is defended against rather than merely
   found. This guard applies to our own archive too.
5. **Provenance is pinned the way the data branch is**: Hugging Face revision
   `0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d`, parquet SHA-256
   `dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73`, both named in the evidence
   README and in any NC row that consumes them (the Rule 7 form Issue #92 proposes).
6. **Attribution and licence**: cite the dataset and its author under CC-BY-4.0; never load the
   `SN` column (CC-BY-NC-4.0); state in the results doc that neither party has checked IBM's
   redistribution terms for `backend.properties()` output.
7. **Backend scope stays `ibm_fez`** for the first article (lead's decision of 2026-10-23,
   consistent with advisor question Q8 left closed).

## Consequences

- The data floor stops being the schedule driver. The schedule drivers become the trainer
  (#60), the ensemble perturbation and interval aggregation (#64) and the baselines the novelty
  check names (`docs/findings/2026-10-23-novelty-check-q1-article.md` §4).
- #63's builder gains a second reader and a source column; its acceptance test (reproduce
  NC-025 at `f0930b9`) is unchanged and a second acceptance test is added: reproduce NC-078's
  626 at the pinned revision.
- The feature distribution the 27-rule grid was partitioned on (NC-041, measured on our files
  from 2026-05-13) widens by three and a half months of the same device; the quantile survey is
  re-run with the source tag before training, and ADR-010's grid is re-derived only if the box
  moves.
- Any paper sentence about the dataset says what was measured: value agreement, document
  reproduction, state count at a pinned revision. "Closes the gap" stays out of the paper until
  #63 reproduces the count.

## Alternatives considered

- **Wait for our own poller to reach 1,170.** `health/metrics.json` at `5828b4a2` projects
  late November 2026 and ADR-025 makes that projection non-registrable. It also leaves the
  training set at one poller's capture rate when a 30-minute record of the same device exists.
- **Adopt the public table as the archive.** Rejected: it is not IBM documents (decision 1),
  and the ledger's distinct-state unit is defined on documents.
- **Adopt three backends.** Rejected for the first article: reopens Q8, changes the feature
  distribution, and makes claim 3 a multi-device claim before it is a single-device result.
- **Re-fetch the pre-May history from IBM ourselves.** NC-026 verified historical reads to 60
  days only; 2026-01-31 is nine months back. Not available.

## Evidence

- `docs/evidence/public-archive-overlap-2026-10/README.md`, `compare_public_archive.py`,
  `summary.json`, `overlap-by-property.tsv`
- `docs/numerical-claims.md` NC-077, NC-078, NC-079
- `docs/findings/2026-10-23-novelty-check-q1-article.md` §6 item 1
- Dataset card and `2026-05-20-report.md` at the pinned revision; poller commit `7572634c`

## Open questions for the deciders

1. Is decision 2's split (archive IBM-only, training set may read the public table) acceptable to
   the data-track owner, given it adds a reader to #63?
2. The widening factor for decision 4's plausibility box.
3. Whether the results doc reports fits with and without the public rows as its primary table,
   or only the combined fit with the source column in the evidence TSV.
