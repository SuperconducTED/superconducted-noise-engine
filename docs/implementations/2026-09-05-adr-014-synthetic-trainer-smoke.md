# 2026-09-05: ADR-014 synthetic trainer smoke run

## Problem / Motivation

ADR-014's trainer needs a reproducible end-to-end validation source while the
official calibration target-distribution contract remains owned by Issue #57.
Using a heuristic target from archived calibration snapshots would silently
create a competing target definition.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/train_anfis.py` | Generates labels from a seeded planted TSK model, fits a fresh rule base, and emits a JSON report. |
| `tests/test_train_anfis_script.py` | Runs the script in T1 and IT2 modes and verifies planted-model recovery. |
| `README.md` | Documents the synthetic-only smoke command and its Issue #57 boundary. |

## Implementation approach

The script builds a four-rule, two-input TSK model with Gaussian MFs for T1 or
IntervalGaussianMFs for IT2. It draws seeded consequent parameters, samples
finite input rows, then uses the existing T1 weighted-average or IT2 Nie-Tan
defuzzifier to produce labels. A separate zero-consequent rule base with the
same premise topology is fitted by `HybridANFISTrainer`.

No calibration snapshot loader, target generator, model artifact format, or
second serializer is introduced. Those surfaces depend on the Issue #57 target
contract and are intentionally not inferred from this synthetic smoke run.

## Mathematical / Statistical details

For each sampled feature vector $x$, the planted model produces a target
$y(x)$ using the production defuzzifier. The trainer minimizes residuals
against exactly those labels. With `--epochs 0`, this isolates fixed-premise
least-squares recovery; `--it2` uses the average of the normalized lower and
upper firing-weighted consequents required by Nie-Tan defuzzification.

## Design decisions

Synthetic planted labels were selected rather than derived calibration labels.
They give a deterministic ground truth for ADR-014 implementation validation
without making a scientific claim about calibration-to-noise supervision. The
real target definition remains an explicit Issue #57 responsibility.

## Verification

- `.venv/bin/python scripts/train_anfis.py --rows 96 --seed 7`
- `.venv/bin/python scripts/train_anfis.py --rows 96 --seed 7 --it2`
- `.venv/bin/python -m pytest tests/test_train_anfis_script.py -q`

## Related docs

- ADR-014 in `docs/decisions.md`
- Issue #57 target-distribution definition