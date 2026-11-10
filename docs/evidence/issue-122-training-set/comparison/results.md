# Source comparison (provisional)

Derived calibration targets only; this does not measure hardware transferability.
Both fits score the same IBM-only chronological holdout. Each fit's Gaussian grid
is re-derived from its training rows; no holdout data sets membership parameters.
The comparison therefore changes both the training source and its grid.

Input TSV SHA-256: `8711289617fd6565e30bfa00ec0a6883297cb6b1f019f25cc9805ec144a2eedb`. Cut: `2026-09-23T00:00:00Z`.

| Fit | Training states | Holdout states | Gamma RMSE | Lambda RMSE |
| --- | --- | --- | --- | --- |
| IBM only | 660 | 264 | 6.964198333e-05 | 0.0006224284397 |
| IBM + public | 1284 | 264 | 0.000461346835 | 0.0005209823043 |

The source-tagged survey is source-quantiles.tsv; its unit is a distinct kept
state, whereas NC-041 was file-weighted. It supersedes no dated NC-041 evidence.

Public data: Charles C. Norton, phanerozoic/qiskit-calibration-drift, CC-BY-4.0.
SN was never loaded. Neither party has checked IBM's redistribution terms for
backend.properties() output. This machine's results await the canonical desktop batch.
