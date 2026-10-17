# Training-set evidence

## 2026-10-17-f0930b9b.tsv

Archive commit: `f0930b9b54975470a4a87866cbc691f7897295cb`.

Builder source revision: `6143f4279df3442fb34363934d01ef5636305fdf`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref f0930b9b54975470a4a87866cbc691f7897295cb --weighting uniform --out docs/evidence/training-set --backend ibm_fez
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 504; documents: 894; duplicates: 390.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_unusable": 0}`.

Target qubit skips: `{"gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 55, "t2_missing": 481}`.

Kept-document loader missingness: `{"init_error_absent": 67331, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 23, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 504, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 15, "1": 13, "2": 7, "3": 29, "4": 23, "5": 12, "6": 16, "7": 25, "8": 16, "9": 21, "10": 24, "11": 30, "12": 20, "13": 18, "14": 22, "15": 16, "16": 24, "17": 25, "18": 34, "19": 28, "20": 27, "21": 23, "22": 23, "23": 13}`.

Measured runtime: 72 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV; register claim IDs at merge time.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. Digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

## 2026-10-17-e5688d2f.tsv

Archive commit: `e5688d2f6a333e98bb01f1c1d81b694ff69574f5`.

Builder source revision: `6143f4279df3442fb34363934d01ef5636305fdf`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref e5688d2f6a333e98bb01f1c1d81b694ff69574f5 --weighting uniform --out docs/evidence/training-set --backend ibm_fez
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 797; documents: 1891; duplicates: 1094.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_unusable": 0}`.

Target qubit skips: `{"gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 133, "t2_missing": 774}`.

Kept-document loader missingness: `{"init_error_absent": 79054, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 23, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 797, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 30, "1": 22, "2": 25, "3": 33, "4": 32, "5": 23, "6": 30, "7": 35, "8": 28, "9": 31, "10": 35, "11": 44, "12": 27, "13": 27, "14": 36, "15": 31, "16": 36, "17": 38, "18": 41, "19": 47, "20": 45, "21": 38, "22": 36, "23": 27}`.

Measured runtime: 151 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV; register claim IDs at merge time.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. Digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

## Verification and numerical claims

Both datasets were rebuilt on Python 3.12.10 at builder source commit
`6143f4279df3442fb34363934d01ef5636305fdf`, based on main `6cf008da`.
The complete suite directly collected and passed 875 tests at that source;
16 are builder cases (NC-021). Lint, formatting and strict typing also pass.
Stack: numpy 2.4.4, qiskit 2.4.1, aer 0.17.2, mypy 1.20.2, pytest 9.0.3,
ruff 0.15.12. This is a provisional Windows measurement pending canonical
desktop batch verification and owner/advisor/consumer confirmations.

| Conclusion | Register |
| --- | --- |
| Pinned October-tip state/document/duplicate counts | NC-070 |
| Document exclusions, target skips and loader missingness | NC-071 |
| State-level UTC hour bias: 230 rows at 00-07, 308 at 16-23; ratio 308/230 | NC-072 |
| Historical NC-025 reproduction | NC-073 |
| Dashboard digest conformance | NC-074 |
| Rounded machine-specific runtime | NC-075 |

An independent second pass at the same source and historical archive ref
produced a byte-identical TSV. SHA-256: `007c8089772bd9d143d64a6e89a4f10a8653311773bcd6747d4d8ae4bd1ad66e`.

Only this October 17 evidence pair is retained. Recheck NC identifiers before
merging; no growth, sufficiency or independence claim is made. Nothing has
been pushed by this change.
