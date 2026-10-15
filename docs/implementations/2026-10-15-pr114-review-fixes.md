# 2026-10-15: pr114-review-fixes

## Problem / Motivation

Mert's round-2 review of PR #114 (Issue #60, the M2 ANFIS ridge-LSE core) at
`ce6b112` found that every round-1 major was resolved. Three minors and five
nits remained:

1. The `fit` docstring said every training row must give a non-identity
   prediction, while the code (correctly, per FR-9) refuses only when every
   row is identity damping. It also attributed the anchored-baseline
   mechanism to ADR-024 clause 5, which Issue #60's settled reading forbids.
2. Row weights and the finite-ridge solve were not pinned. Two seeded bugs
   survived the tests: ignoring the weights, and penalizing with `ridge**2`.
3. The planted-grid allowance (`2048 * cond * eps` in raw units) was this
   fixture's readout-slope amplification, not a derived bound. IT2 had 1.6x
   headroom.
4. Nits: FR-3 checked at one feature vector; the midpoint test compared
   against the trainer's own weights; `pytest.approx` where FR-8 and FR-14 ask
   for exact equality; a loss test that could not see the round-1
   normalization (one output); a condition-number check of `> 0`; a comment
   that claimed to mirror `is_identity_damping` although the two differ on
   NaN; the planting box stated without its source.

Mert chose to land the fixes himself, as a fast-forward on Burak's branch,
and approve. Burak's two commits are untouched.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/training/anfis.py` | Rewords the `fit` docstring, refuses non-finite warm-start parameters with a message naming the input, and corrects the identity-predicate comment. |
| `tests/test_anfis.py` | Moves the planted-grid comparison to standardized units, checks FR-3 over the grid, and adds the closed-form, two-output loss, condition-number and non-finite warm-start tests. |
| `docs/implementations/2026-10-11-anfis-trainer-m2-core.md` | Cites NC-041 for the box, records the standardized-unit bound and its measured values, and updates the warm-start decisions. |
| `docs/implementations/2026-10-15-pr114-review-fixes.md` | This record. |

## Implementation approach

Each fix maps to one review finding.

- **Minor 1, `fit` docstring.** It now says the warm start must be finite and
  must not be identity damping on every training row; partial identity is
  accepted. It calls the degeneracy check plus #59's anchored warm start the
  third mechanism for ADR-024 clause 5, not one of the clause's two.
- **Minor 2, ridge and weights.**
  `test_weighted_finite_ridge_fit_matches_closed_form` fits with
  non-uniform weights at `ridge=0.3`. It compares the standardized
  consequents with a closed form computed in the test from the T1 firing
  strengths, independently of the trainer's helpers.
- **Minor 3, planted tolerance.** The planted-grid test maps both the fitted
  and the planted rule bases into the fit's standardized units, using
  `diagnostics.standardization`. It bounds the difference by
  `8 * cond * eps * max|B_planted|`, and also checks that the raw-unit
  predictions reproduce the targets to `1e-9` of `max|y|`.
- **Nit, FR-3.** `test_effective_weights_match_shipped_defuzzifier` loops all
  512 grid rows at the same 8 eps scale-aware bound.
- **Nit, midpoint.** The midpoint test compares against
  `NieTanDefuzzifier().defuzzify(firing)` and requires a gap above `1e-4` of
  `max|y|`.
- **Nit, exact equality.** The immutability test now uses `np.array_equal` on
  MF parameters and consequents. The determinism test uses `np.array_equal`
  on `train_rmse` and `==` on `loss_history`.
- **Nit, loss and condition number.**
  `test_loss_history_and_condition_number_are_pinned_for_two_outputs` uses
  two outputs. It pins `lse_condition_number` to `np.linalg.cond` of a
  test-built design, and `loss_history[0]` to the section 6.4 definition.
- **Nit, NaN.** `_reject_nonfinite_warm_start` runs before the identity check
  and names the rule. Neither `TSKRule` nor `GaussianMF` rejects NaN. At
  `ce6b112` a NaN consequent surfaced as "fitted consequent parameters must
  be finite", and a NaN MF centre as a `MembershipDegree` range error. The
  identity-check comment now states the NaN difference from
  `is_identity_damping`.
- **Nit, box.** The M2 doc cites NC-041 (`3d1569d`, [p1, p99]).

## Mathematical / Statistical details

**Planted-grid bound.**
- `numpy.linalg.lstsq` is backward stable, so in the standardized
  coordinates the solve runs in, the consequent error is of order
  `cond(Phi_aug) * eps * max|B|`.
- Mapping to raw units multiplies slope `j` of output `l` by `sy[l] / s[j]`.
- With the readout-error spread `s = 0.0066` on this box, the raw-unit error
  of the readout slope was 700x (T1) and 1200x (IT2) of `cond * eps`, against
  at most 0.1x for the T1 and T2 slopes. That is the amplification the 2048
  allowance was absorbing.
- In standardized units the measured worst error is 0.17x (T1, `cond`
  1.0e6) and 0.18x (IT2, `cond` 6.1e3) of `cond * eps * max|B|`. The 8x bound
  therefore leaves about 44x headroom, and it does not depend on the
  planting box.

**FR-3.**
- The trainer's forward pass `w @ c` and the defuzzifiers' `sum(f c) / sum(f)`
  differ only in summation order, so their difference is a few eps of the
  term scale `sum_r |w_r| |c_r|`.
- **On the committed fixture** (`_planted_grid`, coefficients drawn from
  `uniform(0.05, 0.2)`, over the 512-row box), measured at `45d8278`:
  - the worst gap is 3.6 eps (T1) and 2.7 eps (IT2) of the term scale, inside
    the test's 8 eps bound;
  - relative to the output itself, the gap is 7.9e-16 (T1) and 6.1e-16 (IT2);
  - every output is positive (the minimum is 17.5), so nothing cancels.
- **On a separate probe fixture** (not in the repo; Mert's round-1 review
  probe at `fe5daf2`, re-measured at `45d8278`), the gap behaves differently:
  - setup: a 3x3x3 `GaussianMF` grid from `grid_partition` on the survey
    `3d1569d`; consequent slopes `N(0, 1) * 1e-4 / p99`; bias
    `1e-4 + |N(0, 1)| * 1e-4`; rng seed 7; the same 512-row box;
  - relative to the term scale the gap is still only 3.7 eps (T1) and 2.5 eps
    (IT2);
  - relative to the output it reaches 1.2e-14 (T1) and 5.6e-14 (IT2), because
    mixed-sign slopes make some outputs cancel.
- The probe case is why the issue's literal "1e-15 relative" cannot hold in
  general, and why Mert ratified the scale-aware bound on #60.

**Midpoint gap.** Over the IT2 grid the midpoint-weight output misses Nie-Tan
by 7.8e-4 to 3.3e-2 of `max|y|`. At the tested point the gap is 1.2e-3, so the
`1e-4` threshold sits 12x below it.

**Closed form.** With standardized design `Phi`, normalized row weights
`W = diag(w / mean(w))`, prior `theta0` and residual `r = yt - Phi theta0`:

```text
theta = theta0 + (Phi^T W Phi + ridge I)^-1 Phi^T W r
```

This is the minimizer of `||W^(1/2) (Phi theta - yt)||^2 + ridge ||theta -
theta0||^2`, which the trainer solves through the augmented least-squares
system instead.

**Loss.** Section 6.4 defines `L = (1 / n_kept) sum_i ||yhat_i - yt_i||^2`:
the mean over rows of the squared norm over outputs. With two outputs, the
round-1 form (the mean over all `n * k` entries) is exactly half of it, which
the new test detects.

## Design decisions

- **Standardized-unit comparison over per-column raw scaling.** Scaling raw
  column `j` by `s[j] / sy[l]` reproduces the slopes but not the bias, whose
  map-back also involves the means. Comparing through
  `_to_standardized_rule_base` reuses the transform that the forward-identity
  test already pins.
- **Normal equations in the test only.** The test problem has 4 unknowns and
  `ridge = 0.3`, so squaring the conditioning costs nothing measurable. The
  trainer keeps the augmented `lstsq` solve.
- **Refuse non-finite warm starts rather than tolerate them.** NaN can enter
  through either `TSKRule` or `GaussianMF`, and both earlier failure messages
  named the wrong layer. A refusal before any arithmetic names the rule.
- **Keep the inline identity predicate.** Importing `aer_factory` would pull
  `qiskit_aer` into the training core. The agreement test (two outputs) and
  the comment cover the duplication.

## Verification

Provisional run on Mert's laptop with the pinned stack (Python 3.12.10,
numpy 2.4.4, mypy 1.20.2, ruff 0.15.12), at this commit on top of
`ce6b112`:

- `ruff check .`
- `ruff format --check .`
- `mypy --strict`
- `python scripts/check_ids.py`
- `pytest -q tests/test_anfis.py`: 38 passed
- `pytest -q`: 809 collected, 809 passed at `45d8278`. NC-021 is
  re-measured at the real merge commit (Rule 6), not here.

**Seeded-bug check.** Each line is a one-line edit of `anfis.py`, run against
`tests/test_anfis.py` and then reverted. All 23 are caught at this commit.

| Seeded bug | Caught by |
| --- | --- |
| no `deepcopy` before standardizing | immutability and map-back tests |
| MF location sign flipped both ways | forward-identity and planted tests |
| Tanh-family slope scaling inverted both ways | forward-identity test |
| ridge shrinks toward zero | ridge warm-start test |
| row weights ignored | closed-form test (new) |
| weight normalization removed | weight-scale test |
| IT2 midpoint weights; IT2 lower bound only; T1 weights off by 1e-12 | FR-3 grid test |
| consequent mean term flipped both ways | forward-identity and planted tests |
| Interval Gaussian `sigma_high` untransformed | forward-identity test |
| non-finite output guard disabled | guard test |
| `clip_binding_rate` always 0 | diagnostics test |
| condition number 0; condition number 10x | condition-number test (new) |
| validation RMSE on training rows | diagnostics test |
| identity warm-start guard disabled; zero treated as non-identity | warm-start tests |
| `zero_firing_rows_dropped` always 0 | zero-firing tests |
| loss averaged over `n * k` | two-output loss test (new) |
| `evaluate_rmse` scores dropped rows | zero-firing test |
| ridge penalty `ridge**2` | closed-form test (new) |
| non-finite warm-start check disabled | non-finite warm-start test (new) |

## Corrections after Bengisu's review

Bengisu approved `45d8278` (PR #114 review 5532835004) and raised three
non-blocking notes. All three were verified and corrected in a follow-up
docs-only commit:

1. **Units label.** The planting box was called "vectorizer units", but
   `BasicCalibrationVectorizer` has emitted SI seconds since #66. The box is
   in archive units, those of `ArchiveUnitFeatureExtractor` and the survey.
   The test docstring and the M2 doc now say so. Issue #60's section 2
   "Feature units" row predates #66, which is where the label came from.
2. **FR-3 provenance.** The 1.2e-14 / 5.6e-14 output-relative gaps were
   measured on Mert's probe fixture, not on the committed one, whose gap is
   7.9e-16 / 6.1e-16 with no cancellation. The FR-3 paragraph above now names
   both fixtures. Mert's #60 comment 6191368826 carried the same unattributed
   figures and is corrected by a follow-up comment there.
3. **Test count.** PR #114's description reported 805 passed (Burak's run at
   `ce6b112`); at `45d8278` the count is 809. A dated note was appended to
   the description.

Bengisu also confirmed Issue #60 decisions 1 and 6 in that review.

## Related docs

- `docs/implementations/2026-10-11-anfis-trainer-m2-core.md`
- Issue #60 (sections 6.3, 6.4, 7 and 9.1), and the M2 decision record in its
  thread
- ADR-024 clause 5 and ADR-014 in `docs/decisions.md`
- NC-041 and NC-021 in `docs/numerical-claims.md`
