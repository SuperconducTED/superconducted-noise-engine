# Training-set evidence

## 2026-11-08-5828b4a2-public.tsv

Archive commit: `5828b4a29fabc245aa096e530852249a3496dc5b`.

Builder source revision: `6d64f64bf29dfdb8ef984734105310ec19ac6276 + uncommitted source changes`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --weighting uniform --out docs/evidence/issue-122-training-set --backend ibm_fez --public-parquet data/issue-122-public.parquet
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 1548; documents: 2873; duplicates: 1325.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_unusable": 0}`.

Target qubit skips: `{"coherence_implausible": 3208, "gate_length_missing": 154, "nonpositive": 0, "t1_missing": 647, "t2_exceeds_2t1": 225, "t2_missing": 901}`.

Kept-document loader missingness: `{"init_error_absent": 181478, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 647, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 1548, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 60, "1": 62, "2": 60, "3": 65, "4": 55, "5": 59, "6": 63, "7": 62, "8": 65, "9": 68, "10": 68, "11": 68, "12": 61, "13": 55, "14": 63, "15": 61, "16": 64, "17": 63, "18": 69, "19": 78, "20": 74, "21": 68, "22": 75, "23": 62}`.

Measured runtime: 183 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. IBM digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, source, source_revision, source_sha256, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

Public replay audit: `{"distinct_states": 625, "incomplete_marks": 14, "marks": 2461, "overlap_states": 1, "rescaled_events": {"T1": 14606, "T2": 14946}, "revision": "0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d", "sha256": "dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73"}`.

Public source: Charles C. Norton, phanerozoic/qiskit-calibration-drift, CC-BY-4.0; SN (CC-BY-NC-4.0) never loaded. Neither party has checked IBM's redistribution terms for backend.properties() output.

Rules: T1/T2 below 0.01 us multiplied by 1e6; qubit 72 T1/T2 dropped; first observed value per stamp retained. Completeness uses all five required fields on every non-excluded qubit before state counting. Targets from both sources use the factor-10 NC-041 plausibility guard. Replay marks stop before the first IBM snapshot and never extend beyond 2026-05-13T12:13:22Z. Public rows never enter calibration-data.

## 2026-11-08-f0930b9b.tsv

Archive commit: `f0930b9b54975470a4a87866cbc691f7897295cb`.

Builder source revision: `6d64f64bf29dfdb8ef984734105310ec19ac6276 + uncommitted source changes`.

```sh
git fetch superconducted-noise-engine calibration-data
python scripts/build_training_set.py --repo . --ref f0930b9b54975470a4a87866cbc691f7897295cb --weighting uniform --out docs/evidence/issue-122-training-set --backend ibm_fez
```

NC-012's unit is distinct device states; this file has one row per state.

Measured distinct device states: 504; documents: 894; duplicates: 390.

Document skips: `{"features_unusable": 0, "parse_error": 0, "target_unusable": 0}`.

Target qubit skips: `{"coherence_implausible": 1080, "gate_length_missing": 0, "nonpositive": 0, "t1_missing": 23, "t2_exceeds_2t1": 55, "t2_missing": 481}`.

Kept-document loader missingness: `{"init_error_absent": 67331, "init_error_explicit_null": 0, "init_error_nan_present": 0, "prob_meas0_prep1_absent": 0, "prob_meas0_prep1_explicit_null": 0, "prob_meas0_prep1_nan_present": 0, "prob_meas1_prep0_absent": 0, "prob_meas1_prep0_explicit_null": 0, "prob_meas1_prep0_nan_present": 0, "readout_error_absent": 0, "readout_error_explicit_null": 0, "readout_error_nan_present": 0, "readout_length_absent": 0, "readout_length_explicit_null": 0, "readout_length_nan_present": 0, "t1_absent": 23, "t1_explicit_null": 0, "t1_nan_present": 0, "t2_absent": 504, "t2_explicit_null": 0, "t2_nan_present": 0}`.

UTC row-hour histogram: `{"0": 15, "1": 13, "2": 7, "3": 29, "4": 23, "5": 12, "6": 16, "7": 25, "8": 16, "9": 21, "10": 24, "11": 30, "12": 20, "13": 18, "14": 22, "15": 16, "16": 24, "17": 25, "18": 34, "19": 28, "20": 27, "21": 23, "22": 23, "23": 13}`.

Measured runtime: 67 seconds (machine-specific). Growth estimate: to be measured. These figures are audited by this TSV.

X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; the wrapper explicitly converts it back to the survey/quantile stack's units. Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). Feature spread uses sample standard deviation (ddof=1); a singleton has an empty std cell. Target gamma spread follows snapshot_target's population standard deviation. Both weight columns are emitted; uniform is the default. IBM digests match the dashboard: parameter dates are normalized away; measurement names, units and values remain. Parameter date bounds are retained as provenance columns.

Fixed column order: `path, source, source_revision, source_sha256, stem, qubit_digest, last_update_date, hour_utc, mean_T1, mean_T2, mean_readout_error, gamma, lambda, T1_n_usable, T1_qubit_std, T1_qubit_p10, T1_qubit_p50, T1_qubit_p90, T2_n_usable, T2_qubit_std, T2_qubit_p10, T2_qubit_p50, T2_qubit_p90, readout_error_n_usable, readout_error_qubit_std, readout_error_qubit_p10, readout_error_qubit_p50, readout_error_qubit_p90, gamma_std, gamma_p10, gamma_p50, gamma_p90, qubit_date_min, qubit_date_max, weight_uniform, weight_hour_of_day, n_usable_qubits_target`.

## Evaluation scope and acceptance, 2026-11-08

This is provisional evidence from Baha's Windows workspace (Python 3.14.5,
NumPy 2.4.4, PyArrow 26.0.1); canonical verification awaits the desktop batch.
The corrected NC-078 acceptance is reproduced: 625 complete public states,
14 incomplete hourly marks excluded, one overlap with IBM, and a 1,548-state
union. The original issue's 626 included an incomplete startup state.
The original NC-025 builder acceptance also reproduces: 504 states from 894
IBM documents at f0930b9b54975470a4a87866cbc691f7897295cb.

In a combined build, `documents` means IBM files plus non-overlapping complete
public representatives, not all hourly replay marks. Public rescale counters
cover the reader's pre-window events after qubit-72 exclusion; they therefore
differ from NC-077's whole-table defect counts. Original IBM digests are kept;
public `qubit_digest` cells carry the dataset revision and projected digest.
Neither the synthetic documents nor any other output is written to calibration-data.

The source-tagged quantile survey and both fits are under `comparison/`.
The common IBM-only holdout begins 2026-09-23T00:00:00Z, a fixed evaluation choice
for this run rather than a preregistered hardware experiment. The comparison
changes the source data and re-derives each grid from its training subset.
Public rows improve lambda error and worsen gamma error in this run; no blanket
improvement or hardware-transferability claim follows. The public reader remains
opt-in and final ADR-029 adoption awaits the lead's recorded approval.

The source-quantiles table uses one row per distinct kept state, unlike NC-041's
file-weighted survey. The original dated survey is untouched. The public source
tag counts kept non-overlapping rows, after IBM precedence. Quantiles over the
whole evidence TSV are descriptive only; fitting constructs its grids from the
training subset and never from the holdout.

`fixture-guard.json` records the new training mask and target statistics on the
unchanged NC-038 fixture. NC-038 through NC-040 track these changed target values.
New fit/survey claims are listed provisionally in the claims register, with
identifiers to be allocated at merge time.
