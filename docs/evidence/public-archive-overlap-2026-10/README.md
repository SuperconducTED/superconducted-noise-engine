# Public calibration archive vs this project's `ibm_fez` archive, 2026-10-23

Evidence for NC-077, NC-078 and NC-079 and for the ADR-029 draft. Everything here is a dated
anchor at the refs below. None of it is a current value: the dataset gains rows every 30
minutes and `calibration-data` every hour.

## What was compared

| Side | Pinned at | What |
| --- | --- | --- |
| Ours | `calibration-data` @ `5828b4a2` | 2,249 `ibm_fez` snapshot documents, 2026-05-13T12:13:22Z to 2026-10-23T09:34:56Z, plus `health/state-index.tsv` (924 distinct `qubit_digest` values) |
| Theirs | Hugging Face `phanerozoic/qiskit-calibration-drift`, revision `0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d` (last modified 2026-10-23T11:42:05Z) | `data/train-00000-of-00001.parquet`, 98,141,114 bytes, SHA-256 `dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73`, 28,945,985 rows; `ibm_fez` rows only were read (9,898,149) |
| Script | `compare_public_archive.py` in this folder, at PR #121 commit `11e2b471` (see Corrections below; the 2026-10-23 row named `main` @ `6cf008da`, which is the base the digest module was imported from and holds no copy of the script) | Read-only; writes `summary.json` and `overlap-by-property.tsv` here |
| Digest | `scripts/canonical_snapshot_digest.py`, unchanged since `b4043e69` (2026-09-10), identical at `main` @ `6cf008da` and on this branch | `qubit_digest`, the NC-012 unit |

The dataset is CC-BY-4.0 except its `SN` column (CC-BY-NC-4.0, WDC-SILSO), which this script
never reads. Author: Charles C. Norton (GitHub `CharlesCNorton/qiskit-calibration-drift`).
Neither party has checked IBM's redistribution terms for `backend.properties()` output.

## Results, as `summary.json` prints them

**Overlap (NC-077).** 4,363,658 unique calibration events in our documents (every
`properties.qubits` and `properties.gates[].parameters` entry, keyed on property, qubits and
`calibrated_time`). 4,178,551 are present in the public table with the identical double.
184,327 are absent from it. 780 are present with a different value, all in `readout_length`
(312) and in `measure_threshold`, `measure_2_threshold` and `measure_reset_2_threshold` (156
each). Zero in T1, T2, readout error, any gate error or any gate length. Per-property counts
are in `overlap-by-property.tsv`.

**Document reproduction.** Replaying the public table as of `calibrated_time` and digesting
the seven qubit-scope properties (projection `all7`, qubit 72's T1 and T2 dropped on both
sides) gives exactly our 924 distinct states on our 2,249 files, with 924 (official,
projected) digest pairs, so it partitions our files as `qubit_digest` does. At our documents'
own timestamps the replayed block equals ours in 2,145 of 2,249 cases. (Corrected 2026-10-26;
the 2026-10-23 text attributed every mismatch to rounds the public poller missed and said no
shared event conflicts, and both statements were wrong.) The 104 mismatching documents,
classified key by key on the two sides' `calibrated_time` stamps (`mismatch_docs_by_kind_set`
and `mismatch_causes` in `summary.json`):

| Kind | Documents | Meaning |
| --- | --- | --- |
| public table ahead | 67 (+6 mixed with the next kind) | at or before the document's `last_update_date` the table holds a readout or `init_error` event stamped later than the one the document carries; the 4 T1 mismatches are of this kind |
| public table lacks our event | 2 | a round its poller missed |
| document lacks `init_error` | 24 (+1 mixed) | the table holds an `init_error` event the document has no field for |
| **same-stamp value conflict** | **4** | all 156 qubits' `readout_length`: `20260608T185628000000Z.json` holds 1,700 ns where the table holds 1,560 ns at stamp 2026-06-08T15:56:55Z; `20260730T210917000000Z.json`, `20260731T001407000000Z.json` and `20260731T034603000000Z.json` hold 1,660 ns where the table holds 1,700 ns at 2026-07-30T14:55:15Z. These two republished stamps are the source of NC-077's 312 differing `readout_length` events |

A scratch probe of the first kind (not committed): of 21,422 such instances over all 2,249
documents, 18,956 (88%) are events a later document of ours carries verbatim; the median lag
between the event's stamp and the document's `last_update_date` is 191 s and 94% are under
one hour. IBM stamps a readout calibration minutes before the served document carries it,
and our hourly poll caught the earlier document; this is a property of comparing an as-of
replay with served documents, not a defect of either table. No shared event in T1, T2,
readout error, any gate error or any gate length conflicts.

**Added states before our first snapshot (NC-078).** 2026-01-31 to 2026-05-13, `ibm_fez`:

| Marks | Incomplete marks excluded | Distinct states | Already in ours | Union with our 924 |
| --- | --- | --- | --- | --- |
| hourly (2,461 marks) | 14 | 625 | 1 | 1,548 |
| half-hourly (4,921 marks) | 28 | 664 | 1 | 1,587 |

(Corrected 2026-10-26 under the completeness rule below; the 2026-10-23 run reported 626, 666,
1,549 and 1,589, counting the startup state that holds T1 and T2 only.) The first complete
mark is 2026-01-31T14:00:00Z; no in-window mark is incomplete. The hourly figure is the one
comparable to our ledger, which samples documents at roughly hourly polls. Half-hourly is the
upper bound. The NC-012 floor is 1,170. Distinct is not independent; the NC-012 caveat carries
over unchanged.

**Completeness rule (added 2026-10-26).** A replayed state is counted only when every
non-excluded qubit holds a value for each of T1, T2, `readout_error`, `prob_meas0_prep1` and
`prob_meas1_prep0` (778 keys for 156 qubits), the fields the training set reads. The table's
first `ibm_fez` events for the three readout quantities are at 2026-01-31T13:18:13Z to
13:19:17Z, so the marks from 00:00Z to 13:00Z hold T1 and T2 only: a startup artefact of the
replay, not a state IBM ever published. `readout_length` is not required because the builder
does not read it; `init_error` is not required because it has no event before 2026-08-01 in
the table or in our documents, so requiring it would exclude every pre-window mark. This is an
initialisation check, not the training-admissibility check (ADR-029's plausibility guard on
T1 and T2 is a separate, still unspecified step), and the builder's acceptance test for this
count applies the same rule and reports the excluded marks.

**Inside our own window (NC-079).** At half-hourly marks the replay yields 1,221 distinct
states against our 924: 843 shared, 378 we never captured, 81 of ours between marks. The public
table holds 13,442 `readout_error` events and 2,721 `sx` gate events in our window that we do
not. Under the `core5` projection (no `readout_length`, no `init_error`): 954, 759, 195, 22.

## Three defects in the public table, and the rule applied to each

1. **Seconds under the label `us`.** T1 and T2 rows the public poller observed live before
   2026-05-07T08:27:06Z hold SI seconds while `unit` says `us`: 14,609 T1 and 14,947 T2 rows
   for `ibm_fez`, none in the ambiguous zone between 0.01 and 1, and no key with two
   representations. Rows the poller later backfilled from IBM's history (half-hour-mark
   `observed_time`) are in microseconds. The dataset's own `2026-05-20-report.md` documents the
   two conventions as `unit IS NULL` versus `us`; the poller rewrite of 2026-05-20 (`7572634c`)
   moved to the 31-column schema, and the current parquet carries `us` on the old rows without
   rescaling them. Rule: a T1 or T2 value below 0.01 `us` is multiplied by 1e6. The script
   reports the rule's reach. Our loader would not have caught this: it validates the unit label
   and scales by 1e-6, and the target code rejects only non-finite and non-positive values.
2. **Omission blindness.** IBM omits qubit 72's T1 and T2 from live `ibm_fez` documents
   (NC-027's lineage). An event table cannot express a field that stopped being published, so a
   replay carries a stale February value forever. Rule: `(72, T1)` and `(72, T2)` are dropped
   on both sides before digesting.
3. **First value per stamp.** The table keys on `(property, qubits, calibrated_time)` and
   keeps the first value seen. IBM republished `readout_length` 1560 to 1700 ns under the same
   stamp in June 2026 and 1700 to 1660 ns in July 2026, and three threshold properties once
   each. Rule (corrected 2026-10-26; the 2026-10-23 text said "ours wins", a rule the replay
   never applied): the replay is **not** modified and carries the public table's value; the
   validation classifies every differing key by stamp and names the documents with a
   same-stamp conflict (the four above). Inside our window our documents are authoritative and
   the public rows are not merged into them (ADR-029 decision 2), so no preference between the
   two values is ever exercised. No training field is affected.

Also observed: `rz_gate_error` and `rz_gate_length` appear under two `property_family` names;
`observed_time` and `calibration_age_seconds` are unreliable for the backfilled period (a
2026-04-30 calibration was first observed on 2026-05-16), which is why the replay is as of
`calibrated_time` and a first attempt keyed on `observed_time` was abandoned.

## Reproduce

Windows refuses paths over 260 characters, so export to a short directory.

```bash
git fetch origin calibration-data
mkdir -p /c/t-hf/ours && git archive --format=tar 5828b4a2 snapshots health | tar -x -C /c/t-hf/ours
```

```bash
mkdir -p /c/t-hf/hfdata && curl -L "https://huggingface.co/datasets/phanerozoic/qiskit-calibration-drift/resolve/0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d/data/train-00000-of-00001.parquet" -o /c/t-hf/hfdata/train-00000-of-00001.parquet && sha256sum /c/t-hf/hfdata/train-00000-of-00001.parquet
```

The readers are not in the project's pins and are installed into a separate target directory,
never into the project environment:

```bash
python -X utf8 -m pip install --target /c/t-hf/pylib duckdb==2.0.0 pyarrow==26.0.0 pytz==2026.5
```

```bash
python -X utf8 -I docs/evidence/public-archive-overlap-2026-10/compare_public_archive.py --parquet /c/t-hf/hfdata/train-00000-of-00001.parquet --ours /c/t-hf/ours --repo . --pylib /c/t-hf/pylib --out /c/t-hf/out
```

`/c/t-hf/out/summary.json` must equal the committed `summary.json`. The run reads a downloaded
file, so the interpreter is isolated (`-I`) and the script directory holds nothing else. The
runs of 2026-10-23 and 2026-10-26 used Python 3.13.14; the digest function is imported from
`scripts/canonical_snapshot_digest.py` so the state definition cannot drift from the ledger's.

## Corrections on review, 2026-10-26

Bengisu's review of PR #121 (review 5651478555, at `04361fe6`) reproduced the committed
outputs and found three faults in this record. The script was changed, re-run at the same two
refs, and the blocks the review did not question came back identical: `ours`,
`overlap_totals`, every `overlap_by_property` row, `unit_defect`,
`theirs_only_in_window_training_fields`, `validation_docs_equal` 2,145 and 2,200, every
in-window figure, and `overlap-by-property.tsv` byte for byte.

| Item | 2026-10-23 | 2026-10-26 |
| --- | --- | --- |
| Pre-window distinct states, hourly / half-hourly | 626 / 666 | 625 / 664 (14 / 28 incomplete marks excluded) |
| Union with our 924, hourly / half-hourly | 1,549 / 1,589 | 1,548 / 1,587 |
| Union of ours with every half-hourly mark, `all7` / `core5` | 1,967 / 1,641 | 1,965 / 1,639 |
| Mismatch attribution | "the public table lacks the event we hold; not one value conflict" | four kinds by stamp, four documents with a same-stamp `readout_length` conflict (table above) |
| Defect 3 rule | "ours wins" (not implemented) | replay unmodified, conflicts classified and named |
| Script revision in the source cells | `main` @ `6cf008da` (a base with no copy of the script) | PR #121 commit `11e2b471`; digest module unchanged since `b4043e69` |

Register rows NC-077 to NC-079 carry the same corrections; the hourly count in Issue #122's
body and checklist (626) is owed a correcting comment by the lead.

## Related

`docs/decisions/drafts/ADR-029-public-calibration-archive-as-training-source.md` ·
`docs/findings/2026-10-23-novelty-check-q1-article.md` §6 ·
`docs/numerical-claims.md` NC-012, NC-025, NC-027, NC-041, NC-069, NC-077 to NC-079 ·
Issues #63 (builder), #92 (Rule 7), #104 (sweep step).
