# Public calibration archive vs this project's `ibm_fez` archive, 2026-10-23

Evidence for NC-077, NC-078 and NC-079 and for the ADR-029 draft. Everything here is a dated
anchor at the refs below. None of it is a current value: the dataset gains rows every 30
minutes and `calibration-data` every hour.

## What was compared

| Side | Pinned at | What |
| --- | --- | --- |
| Ours | `calibration-data` @ `5828b4a2` | 2,249 `ibm_fez` snapshot documents, 2026-05-13T12:13:22Z to 2026-10-23T09:34:56Z, plus `health/state-index.tsv` (924 distinct `qubit_digest` values) |
| Theirs | Hugging Face `phanerozoic/qiskit-calibration-drift`, revision `0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d` (last modified 2026-10-23T11:42:05Z) | `data/train-00000-of-00001.parquet`, 98,141,114 bytes, SHA-256 `dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73`, 28,945,985 rows; `ibm_fez` rows only were read (9,898,149) |
| Script | `compare_public_archive.py` in this folder, at `main` @ `6cf008da` | Read-only; writes `summary.json` and `overlap-by-property.tsv` here |

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
own timestamps the replayed block equals ours in 2,145 of 2,249 cases. The 104 mismatches are
readout, `init_error` and `readout_length` values where the public table lacks the event we
hold (its poller missed the round) and 4 T1 values of the same kind. Not one is a value
conflict on a shared event.

**Added states before our first snapshot (NC-078).** 2026-01-31 to 2026-05-13, `ibm_fez`:

| Marks | Distinct states | Already in ours | Union with our 924 |
| --- | --- | --- | --- |
| hourly (2,461 marks) | 626 | 1 | 1,549 |
| half-hourly (4,921 marks) | 666 | 1 | 1,589 |

The hourly figure is the one comparable to our ledger, which samples documents at roughly
hourly polls. Half-hourly is the upper bound. The NC-012 floor is 1,170. Distinct is not
independent; the NC-012 caveat carries over unchanged.

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
   stamp in June 2026, and three threshold properties once each. Rule: where a stamp carries
   two values, ours wins. No training field is affected.

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
run of 2026-10-23 used Python 3.13.14; the digest function is imported from
`scripts/canonical_snapshot_digest.py` so the state definition cannot drift from the ledger's.

## Related

`docs/decisions/drafts/ADR-029-public-calibration-archive-as-training-source.md` ·
`docs/findings/2026-10-23-novelty-check-q1-article.md` §6 ·
`docs/numerical-claims.md` NC-012, NC-025, NC-027, NC-041, NC-069, NC-077 to NC-079 ·
Issues #63 (builder), #92 (Rule 7), #104 (sweep step).
