# Feature-distribution survey — where the archive's features actually sit

`2026-09-08-3d1569d.tsv` is the ground truth for Issue #59's grid partition:
one row per archived snapshot file, with the three
`BasicCalibrationVectorizer` features and the per-qubit spread of the values
each feature averages over.

It exists as a committed file rather than only as a command you could re-run,
because every membership parameter in
`src/superconducted/fuzzy/parameterization.py` is a stated function of a
quantile of this table. A reviewer auditing any MF parameter should be able to
recompute it from this file without access to the 1.3 GB archive.

## Provenance

| | |
| --- | --- |
| **Ref** | `calibration-data` @ `3d1569d18bcc007c35f3f628f79e678e6061bdc3` |
| **Measured** | 2026-09-08 |
| **Rows** | 975 snapshot **files** (not samples, not distinct device states) |
| **Span** | `snapshots/2026-05/ibm_fez/20260513T121322000000Z.json` → `snapshots/2026-09/ibm_fez/20260906T205621000000Z.json` |
| **Rejected** | 0 — every file yielded all three features |

```bash
git fetch superconducted-noise-engine calibration-data
python -m scripts.feature_distribution --repo . --ref 3d1569d18bcc007c35f3f628f79e678e6061bdc3 --out docs/evidence/feature-distribution/2026-09-08-3d1569d.tsv
```

The ref is a commit sha, not `FETCH_HEAD`: the provenance has to survive the
next fetch.

**File-count reconciliation** (Issue #59 step 1). The ticket recorded 920 files
at `40a1ff4` locally on 2026-09-03 and 921 via the GitHub tree API at `43dec77`
on 2026-09-02. Both reproduce exactly at their own refs
(`git ls-tree -r --name-only <ref> -- snapshots/ | grep -c '\.json$'` gives 920
and 921 respectively). The archive has grown since; 975 is the count at the ref
this survey pins. Nothing is missing and nothing was double-counted — the
poller kept running.

## Units

The vectorizer's own, with no scaling (NFR-8):

| Feature | Unit |
| --- | --- |
| `mean_T1`, `mean_T2` | microseconds |
| `mean_readout_error` | dimensionless |

`scripts/first_ensemble_run.py::FEATURE_SCALES` is in **seconds** and is not a
source of truth for anything here or downstream.

`*_qubit_std` is the **sample** standard deviation, `numpy.std(v, ddof=1)`,
empty when fewer than two per-qubit values are usable. `ddof=1` matches
`calibration/features.py::per_qubit_spread` (#64), which becomes the single
home for this statistic. Cross-check on the committed fixture
`ibm_fez_20260513T121322Z_q72_missing_t1t2.json`, which is row 1 of this table:
`T1_qubit_std` is **45.4847** (`ddof=0` would give 45.3377), and the row's means
are `[155.1924, 109.5954, 0.035326]` — the values NFR-8 predicts.

## Summary

Snapshot-value quantiles across the 975 rows, and the median over snapshots of
the per-qubit `ddof=1` spread:

| Feature | p1 | p50 | p99 | median per-qubit std |
| --- | ---: | ---: | ---: | ---: |
| `mean_T1` (µs) | 98.8191 | 131.7984 | 154.3887 | 45.7756 |
| `mean_T2` (µs) | 67.4411 | 97.0365 | 110.5429 | 54.9084 |
| `mean_readout_error` | 0.0171326 | 0.0205861 | 0.0374223 | 0.0406946 |

`[p1, p99]` per feature is the **domain box** the partition is defined on, and
the only region where the model has stated behaviour;
`ClampingFeatureExtractor` moves anything outside it onto the boundary and
counts it. Measured over these 975 rows, **44 vectors (4.51%)** leave the box —
16 on `mean_T1`, 11 on `mean_T2`, 20 on `mean_readout_error`. That is measured,
not derived: a per-feature 2% tail bounds the vector rate between 2%
(perfectly correlated features) and about 6% (independent), and neither bound is
the answer.

Registered as NC-041 (quantiles), NC-042 (per-qubit spread), NC-043 (file
count) and NC-044 (runtime) in `docs/numerical-claims.md`. The committed TSV is
the audit trail for individual cells.

**Runtime.** 63.70 s wall clock for the full 975-file walk, measured
2026-09-08 at `3d1569d` on Mert's laptop. **Provisional** under the team's
verification convention (NFR-3) until Burak's next batch desktop record
(`docs/verification/2026-09-XX-phase-3-batch-N-burak-desktop.md`, architect
decision C2) replaces it. `--limit N` exists so smoke runs do not pay the full
cost.

## What the row count is not

975 counts **files**. The archive holds byte-identical repeats — the first five
rows of this table share a `mean_T1` of 155.1924205171878 to all sixteen digits
across an eight-hour span, because IBM republishes the document without new T1
data. NC-025 counts distinct device states (504 at `f0930b9`), and the
training-set builder (#63) is what deduplicates. Never describe this row count
as a sample count.

Because the quantiles above are computed over files, the bins hold equal mass
in *file* terms rather than in distinct-state terms. That is the ticket's
intended design — the partition is defined on what the archive contains — but
it is worth stating so nobody later reads the bins as equal-probability over
device states.

## Columns

FR-2's stated column order is a strict prefix of the header;
`rejection_reason` is appended last, so a positional reader (#63 imports
`snapshot_row`) sees the documented layout.

```
path  stem  backend  timestamp  last_update_date  n_qubits
mean_T1  mean_T2  mean_readout_error
T1_n_usable  T1_qubit_std  T1_qubit_p10  T1_qubit_p50  T1_qubit_p90
T2_n_usable  T2_qubit_std  T2_qubit_p10  T2_qubit_p50  T2_qubit_p90
readout_error_n_usable  readout_error_qubit_std  readout_error_qubit_p10  readout_error_qubit_p50  readout_error_qubit_p90
rejection_reason
```

A snapshot the vectorizer rejects keeps its per-qubit columns, gets empty
`mean_*`, and carries the reason — it is counted, never silently dropped.

## Related

- `docs/implementations/2026-09-08-mf-parameterization.md` — what consumes this
- `src/superconducted/fuzzy/parameterization.py` — the partition built from it
- Issue #59 sections 6.3 and 9.3; NC-012, NC-025
- `docs/evidence/pr47-outage-enumeration/README.md` — the format this follows
