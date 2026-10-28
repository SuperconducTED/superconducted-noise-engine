# 2026-10-26: PR #121 baseline and alpha review fixes

## Problem / Motivation

The review of PR #121 at `5f7013aa` found that the PR-A' plan and the ADR-015 gates record
equated a symmetric relative-persistence band with the rolling empirical-percentile
comparator required by the novelty argument. It also found that D2 reversed the direction
of the alpha-scale relationship. Those statements could lead an implementation to omit a
required comparator or fit a different interval from the one reported.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` | Section 12 requires both baselines, specifies causal histories and common held-out rows, and corrects D2's alpha guidance. |
| `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md` | Section 9 withdraws the false equivalence and limits the provisional persistence result to the estimator actually measured. |
| `docs/findings/2026-10-23-novelty-check-q1-article.md` | Section 10 retains the empirical-percentile gate and names relative persistence as an additional comparator. |

## Implementation approach

Append dated amendments and cross-link them. This preserves the original dated records and
makes the superseding instructions explicit, following `docs/team.md`'s append-only
convention. The empirical-percentile baseline is retained rather than silently replaced by
relative persistence. Neither baseline is implemented or measured by this documentation fix.

## Mathematical / Statistical details

For target coordinate `j`, relative persistence is the interval centred on `y_j(t)` with
half-width `r_P * abs(y_j(t))`. The empirical comparator instead uses lower and upper
quantiles of the coordinate's recent history. Its midpoint need not be `y_j(t)`, so changing
the persistence scale cannot in general reproduce it.

For fixed members, increasing the lower-tail probability raises the lower quantile and
lowers the upper quantile. The central interval therefore narrows. Fix alpha before fitting
the perturbation scale; changing alpha requires a fresh training fit and evaluation. The
nonlinear TSK map provides no general inverse relationship between alpha and scale.

Hyperparameters are selected on training data and frozen before held-out scoring. Rolling
histories may advance using only observations available at each forecast origin. A common
history-ready mask keeps the two baselines and the fuzzy arm on the same scored examples;
excluded origins and row counts are reported. An empirical quantile level is not a claim of
calibrated coverage, and any scale-adjusted variant is reported separately.

## Design decisions

- Retain both baseline estimators so a persistence result cannot stand in for the required
  empirical-percentile comparison.
- Correct D2's reasoning without answering the pending modelling-choice sign-offs or changing
  ADR-015, ADR-016 or ADR-027's ledger statuses.
- Keep the comparison script, numerical-claims register and measured evidence unchanged;
  these corrections introduce no new empirical result.

## Verification

- `git diff --check`
- `python scripts/check_ids.py`
- `python -m ruff check .` and `python -m ruff format --check .`
- Check the appended sections and their relative Markdown links against the three records.
- Verify the non-equivalence of a history-quantile interval and a latest-target-centred band,
  and quantile nesting as alpha increases, with direct NumPy calculations.

All checks above passed locally. The dated records preserve their original contents as a
prefix, and the relative links resolve to existing files and headings. No new automated
test is added for this documentation-only correction; the engine and measured evidence are
unchanged.

## Related docs

- [PR #121](https://github.com/SuperconducTED/superconducted-noise-engine/pull/121)
- [PR-A plan, section 12](../roadmap/2026-10-23-issue-64-pr-a-plan.md#12-review-amendment-2026-10-26-separate-baselines-and-fix-alpha-before-fitting)
- [ADR-015 gates, section 9](../findings/2026-10-23-adr-015-what-an-interval-needs.md#9-review-amendment-2026-10-26-the-two-baseline-gates)
- [Novelty check, section 10](../findings/2026-10-23-novelty-check-q1-article.md#10-review-amendment-2026-10-26-retain-both-non-fuzzy-baselines)
- `docs/team.md`, Documentation conventions
