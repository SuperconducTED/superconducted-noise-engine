# Feature Distribution Survey

This directory contains the empirical feature distribution data extracted from the calibration archive to satisfy FR-1 through FR-4.

## Generation Command

The `survey.tsv` file was generated using the following module execution:

```bash
python -m scripts.feature_distribution --repo . --ref FETCH_HEAD --out docs/evidence/feature-distribution/survey.tsv
```

## Survey Summary

Execution yielded the following distribution statistics:

```json
{
  "file_count": 930,
  "T1_present_rows": 930,
  "T1_p1": 98.81910053692253,
  "T1_p50": 131.7984267444949,
  "T1_p99": 154.3887041695056,
  "T1_median_qubit_std": 45.77955119216398,
  "T2_present_rows": 930,
  "T2_p1": 67.4410579288897,
  "T2_p50": 97.46811101783244,
  "T2_p99": 110.54291523197335,
  "T2_median_qubit_std": 55.04588675697492,
  "readout_error_present_rows": 930,
  "readout_error_p1": 0.017128006372696316,
  "readout_error_p50": 0.020593496469350964,
  "readout_error_p99": 0.037664544521233995,
  "readout_error_median_qubit_std": 0.04144915498916178,
  "runtime_seconds": 85.60292840003967
}
```