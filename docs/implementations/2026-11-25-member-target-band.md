# 2026-11-25: member-target-band (plan, before any code)

**Status:** plan only, waiting for Mert's go. No code is written. Measured at `main` `1869d858`.

## Problem / Motivation

Gate L4 needs the fuzzy band's row on the snapshot ladder (#161). Mert's #161 decision 1 (comment 7102611064,
2026-11-23) fixes the band's object: member quantiles of predicted (gamma, lambda), before a conformal step whose
form is still open to Bengisu.

**Correction.** The 2026-11-23 session note said nothing on `main` returns per-member (gamma, lambda), so a new
function was needed. That is wrong. Every member that `FuzzyNoiseModelEnsemble` yields exposes `crisp_params`, and
under `KrausChannelProjector`'s contract entries 0 and 1 are gamma and lambda (`is_identity_damping`'s docstring in
`integration/aer_factory.py`). Two things are actually missing:

1. A band in target space. PR-A1's `IntervalBand` is over outcome probabilities of a circuit (L-100).
2. The wiring from one archive state to one perturbed ensemble, in the training set's units.

## What changes (planned)

| File | Change |
| --- | --- |
| `scripts/fuzzy_band_members.py` (new) | `ensemble_for_state`, `member_targets`, `TargetBand`, `target_band`, the clip count |
| `tests/test_fuzzy_band_members.py` (new) | the criteria below, written to fail before the code |
| this file | the plan now; results appended after the run |

No file under `src/` changes.

## Implementation approach

Reuse, do not re-implement. For one state, `ensemble_for_state` builds the `CalibrationSnapshot` the way
`training/dataset.py::_row` does. It takes the centre `x` from `ArchiveUnitFeatureExtractor`'s own output (the
training TSV's units, microseconds), because `OffsetFeatureExtractor` refuses any vector that is not bit-equal to
its centre. It then builds `InputVectorPerturbation.relative(x, r, ...)` and a seeded `FuzzyNoiseModelEnsemble`.
`member_targets` reads `crisp_params[:2]` from each member, so no seeding logic is copied.

## Mathematical / Statistical details

| Quantity | Definition |
| --- | --- |
| Member input | `x_k = x + r|x| * z_k`, with `z_k ~ N(0, I)` redrawn at a bound (PR-A1) |
| Member output | `y_k = clip_[0,1](f(x_k))`, with `f` the defuzzified TSK output |
| Band, per component `j` (gamma, lambda) | `[Q_alpha(y_.j), Q_(1-alpha)(y_.j)]` by `numpy.quantile(method)` |
| Clip count, per component | the number of members with `y_kj` exactly 0 or 1 (L-086) |

This band is not a calibrated interval. The conformal widening (candidate `[Q_0.10 - c, Q_0.90 + c]`) is the next
step, and it waits on Bengisu's answer.

## Design decisions

- **A script, not `src`.** ADR-015 and ADR-016 are Deferred. `perturbation.py` and `metrics.py` are Bengisu's and
  `aer_factory.py` is Burak's. Promoting the band to `src` is ADR-016's decision, after L4.
- **The ensemble path, not a lean one.** The probe of 2026-11-25 (laptop, random consequents; script
  `C:/t/memprobe/probe.py`, to be committed with the evidence) measured:

  | Path | Time per member |
  | --- | --- |
  | Ensemble | 17 to 19 ms |
  | Lean (needs the private `_perturbed`) | 0.65 to 2.6 ms |

  Scoring covers 378 test origins (`pairs.tsv`) plus 95 calibration states, at 32 members. On the ensemble path that
  is about 4.5 minutes per `r` value. That is too little to justify a new public method in Burak's module.
- **No defaults.** `alpha`, `method`, `N`, `r` and each state's `SeedSequence` are required arguments. Decision 1
  already fixes the levels at 10% and 90%, so the pre-registration passes `alpha = 0.10`. It also fixes the rest,
  including how seeds are assigned across rows (shared or independent draws).
- **The posted reply needs a correction.** #161 comment 7102611064 tells Bengisu that "nothing on `main` returns
  per-member `(gamma, lambda)`". A correction is owed there, on Mert's word.

## Verification (criteria, fixed before the code)

1. **Parity.** The identity member's `crisp_params[:2]` equals `ProbabilityClip` of `anfis._predict` at the same
   `x`, within rtol 1e-12, on a rule base fitted by `HybridANFISTrainer` to a small synthetic set. The probe found a
   3.9e-15 maximum relative difference, which is not bit-equal. Also asserts `output_dim == 2`.
2. **Reuse.** `member_targets` equals `[m.crisp_params[:2] for m in ensemble]` bit for bit, and two calls agree.
3. **Band.** On a hand-built table, `target_band` equals `numpy.quantile` per component, with the method stored.
   It refuses `N < 2`, `alpha` outside `[0, 0.5)`, an empty method, non-finite values, and values outside `[0, 1]`.
4. **Clips.** Members at 0 and at 1 are both counted, per component.
5. **Units.** The centre is `ArchiveUnitFeatureExtractor`'s output bit for bit; a centre in SI seconds is refused.
6. **Both document kinds.** A live fixture and the same fixture with `configuration` null both build.
7. **No held-out data.** Tests read committed fixtures or synthetic data only. The test helper asserts that no file
   dated 2026-09-01 or later is read.
8. **Mutation run.** Predictions are committed before the run. Planned mutants: wrong quantile level, swapped
   components, method ignored, only the lower clip counted, centre from `BasicCalibrationVectorizer`, members read
   without the perturbation. Each mutant prints what it changes (L-075).
9. **Gates.** ruff, format, `mypy --strict` (scope including `scripts/`), `check_ids`, then the full suite.

## Related docs

#161 and comment 7102611064; #64 and PR #155 (`docs/implementations/2026-11-09-issue-64-pr-a1-perturbation-and-band.md`);
`docs/evidence/persistence-band/README.md` section 2; skill lessons L-042, L-086 and L-100.
