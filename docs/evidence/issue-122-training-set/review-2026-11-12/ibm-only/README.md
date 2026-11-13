# Training-set evidence

## 2026-11-12-f0930b9b.tsv

Archive commit: `f0930b9b54975470a4a87866cbc691f7897295cb`.

Builder source revision: `cd20cc3788539cba04870bf6e26bbd5f3e9fed6c`.

Python: `3.12.10`. Pinned environment: `requirements-dev.txt`, SHA-256 `98dbf3d0ce12ac3842307e6fd91cb079f5a66a7d5d771bbf671a2d8460a17dcd`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref f0930b9b54975470a4a87866cbc691f7897295cb --weighting uniform --out docs/evidence/issue-122-training-set/review-2026-11-12/ibm-only --backend ibm_fez
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 504; documents: 894; duplicates: 390.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_coverage_insufficient": 0, "target_unusable": 0}`.

Target qubit skips: `{"coherence_implausible": 0, "gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 55, "t2_missing": 481}`.

Target qubit skips by source: `{"calibration-data": {"coherence_implausible": 0, "gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 55, "t2_missing": 481}}`.

Kept-document loader missingness: `{"init_error_absent": 67331, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 23, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 504, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 15, "1": 13, "2": 7, "3": 29, "4": 23, "5": 12, "6": 16, "7": 25, "8": 16, "9": 21, "10": 24, "11": 30, "12": 20, "13": 18, "14": 22, "15": 16, "16": 24, "17": 25, "18": 34, "19": 28, "20": 27, "21": 23, "22": 23, "23": 13}`.

Measured runtime: 90 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. IBM digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, source, source_revision, source_sha256, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

