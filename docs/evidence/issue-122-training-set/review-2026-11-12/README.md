# Training-set evidence

This review rebuild uses committed source and the pinned Python 3.12 environment.
It supersedes the November 8 factor-10 evaluation; all runs remain provisional
until canonical desktop verification.

NC-078's count is unchanged: 625 complete public states from 2,461 hourly marks,
14 incomplete marks excluded, and one state overlapping the 924 IBM states.
The complete-state union is therefore 1,548. After the separate target-coverage
check, one public representative (`2026-01-31T14:00:00Z`, one usable target qubit)
is skipped. The kept training set has 1,547 rows: 924 IBM and 623 public rows.
No kept public row has fewer than 100 usable target qubits.

The factor-1000 guard rejects no qubits in either source, as the per-source
`coherence_implausible` audit below records. The IBM-only acceptance rebuild
under `ibm-only/` matches the original unguarded 504-state targets and features
exactly when joined by `qubit_digest`.

The missing three T1 and one T2 rescale events are exactly qubit 72's excluded
events: 14,606 + 3 = 14,609 T1 and 14,946 + 1 = 14,947 T2, matching the draft's
whole-table defect counts. The explicit `excluded_rescale_events` audit makes
this reconciliation reproducible.

The corrected fits and their constant baselines are in
[`comparison/results.md`](comparison/results.md). Both fitted models lose to
their training-target-mean baselines for both outputs. These fits are not
informative evidence of a source improvement; no source-fit claim is registered.
The source survey uses distinct kept states, unlike NC-041's file weighting.

## 2026-11-12-5828b4a2-public.tsv

Archive commit: `5828b4a29fabc245aa096e530852249a3496dc5b`.

Builder source revision: `cd20cc3788539cba04870bf6e26bbd5f3e9fed6c`.

Python: `3.12.10`. Pinned environment: `requirements-dev.txt`, SHA-256 `98dbf3d0ce12ac3842307e6fd91cb079f5a66a7d5d771bbf671a2d8460a17dcd`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --weighting uniform --out docs/evidence/issue-122-training-set/review-2026-11-12 --backend ibm_fez --public-parquet data/issue-122-public.parquet
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 1547; documents: 2873; duplicates: 1325.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_coverage_insufficient": 1, "target_unusable": 0}`.

Target qubit skips: `{"coherence_implausible": 0, "gate_length_missing": 154, "nonpositive": 0, "t1_missing": 647, "t2_exceeds_2t1": 324, "t2_missing": 901}`.

Target qubit skips by source: `{"calibration-data": {"coherence_implausible": 0, "gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 285, "t2_missing": 901}, "phanerozoic/qiskit-calibration-drift": {"coherence_implausible": 0, "gate_length_missing": 154, "nonpositive": 0, "t1_missing": 624, "t2_exceeds_2t1": 39, "t2_missing": 0}}`.

Kept-document loader missingness: `{"init_error_absent": 181322, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 646, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 1547, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 60, "1": 62, "2": 60, "3": 65, "4": 55, "5": 59, "6": 63, "7": 62, "8": 65, "9": 68, "10": 68, "11": 68, "12": 61, "13": 55, "14": 62, "15": 61, "16": 64, "17": 63, "18": 69, "19": 78, "20": 74, "21": 68, "22": 75, "23": 62}`.

Measured runtime: 200 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. IBM digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, source, source_revision, source_sha256, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

Public replay audit: `{"distinct_states": 625, "excluded_rescale_events": {"T1": 3, "T2": 1}, "incomplete_marks": 14, "marks": 2461, "minimum_target_qubits": 100, "overlap_states": 1, "rescaled_events": {"T1": 14606, "T2": 14946}, "revision": "0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d", "sha256": "dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73", "target_coverage_skips": 1}`.

Public source: Charles C. Norton, phanerozoic/qiskit-calibration-drift, CC-BY-4.0; SN (CC-BY-NC-4.0) never loaded. Neither party has checked IBM's redistribution terms for backend.properties() output.

Rules: T1/T2 below 0.01 us multiplied by 1e6; qubit 72 T1/T2 dropped; first observed value per stamp retained. Completeness uses all five required fields on every non-excluded qubit before state counting. Targets from both sources use the factor-1000 NC-041 unit-error guard. Public states need at least 100 usable target qubits; insufficient coverage is a separate target_coverage_insufficient skip after NC-078 state counting. Replay marks stop before the first IBM snapshot and never extend beyond 2026-05-13T12:13:22Z. Public rows never enter calibration-data.

