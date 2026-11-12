# Source comparison (provisional)

Derived calibration targets only; this does not measure hardware transferability.
Both fits score the same IBM-only chronological holdout. Each fit's Gaussian grid
is re-derived from its training rows; no holdout data sets membership parameters.
The comparison therefore changes both the training source and its grid.
The constant baseline predicts each fit's training-target mean on the same holdout.
These exploratory fits are not informative evidence of a source improvement yet;
compare them with the constant baselines before drawing any conclusion.

Input TSV SHA-256: `4c20d6e942a2ab6375525aa13f2cf401278cba8152bef3f5c28b669b37fcb3bf`. Cut: `2026-09-23T00:00:00Z`.

| Fit | Training states | Holdout states | Gamma RMSE | Lambda RMSE |
| --- | --- | --- | --- | --- |
| IBM only (training-mean baseline) | 660 | 264 | 1.192022852e-05 | 3.453190816e-05 |
| IBM only | 660 | 264 | 2.823018232e-05 | 0.0004801973598 |
| IBM + public (training-mean baseline) | 1283 | 264 | 1.426288435e-05 | 3.253438935e-05 |
| IBM + public | 1283 | 264 | 0.001263601602 | 0.006139206218 |

The source-tagged survey is source-quantiles.tsv; its unit is a distinct kept
state, whereas NC-041 was file-weighted. It supersedes no dated NC-041 evidence.

Public data: Charles C. Norton, phanerozoic/qiskit-calibration-drift, CC-BY-4.0.
SN was never loaded. Neither party has checked IBM's redistribution terms for
backend.properties() output. This machine's results await the canonical desktop batch.
