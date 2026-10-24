# 2026-10-23: per-qubit-predictability

## Problem / Motivation

Decision A7 of the three-engine plan (Issue #110, PR #111) makes the deep engine a forecaster
of the per-qubit target at `t + h`. The persistence-band measurements of the same day
(PR #123) showed that at the snapshot level the mean reverts toward a slow level and that
state information about drift is weak, and that per-qubit values jump by about a quarter
whenever a qubit is re-measured. Whether those jumps have memory decides whether any
forecaster, deep or otherwise, can help the article, and it had never been measured. Mert
asked for the per-qubit predictability checks before any deep-model work, as a follow-up to
PR #123.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/predictability/README.md` | Pre-registered protocol (§2, committed before the run), its pre-run amendment (§2.1, which replaced a decision rule that would have said yes for the wrong reason), results (§3), the decision rule applied (§3.4), and the desktop runbook. |
| `docs/evidence/predictability/measure_predictability.py` | Event view (increment autocorrelation, local-level cap, reversion regression) and horizon view (persistence, shrinkage, ridge, rolling band, split-conformal bands, common-mode share) in log target space; imports the archive walk and as-of lookup from the persistence-band script. Ruff-clean on 0.15.12; outside mypy's scope. |
| `docs/evidence/predictability/results.tsv`, `rows.tsv`, `summary.json` | The run's output at the pinned ref: 144 result rows, 193,754 test rows. |
| `docs/evidence/predictability/results-readout.tsv`, `rows-readout.tsv.gz`, `summary-readout.json` | The `--feature readout` run's output at the same ref (§2.2 of the README, pre-registered after the targets run and before its own). |
| `docs/numerical-claims.md` | NC-084, NC-085 and NC-086 appended, dated-anchor form. |
| `docs/implementations/2026-10-23-per-qubit-predictability.md` | This record. |

No source, test or ADR status changed. The branch stacks on `mert/persistence-band`
(PR #123), which stacks on PR #121; register ids continue from NC-083.

## Implementation approach

Protocol first (`6f582c59`), review, append-only amendment (`261d9df3` with the script), then
the run. The amendment mattered more than usual: the original decision rule asked whether a
linear model reaches `R^2 >= 0.10` on the next change, and under pure noise around a fixed
level shrinkage alone scores 0.5, so the rule would have endorsed the deep model on a series
with nothing to learn. The revised rule tests the gap above shrinkage and the band against the
better non-parametric band. The script reuses the persistence-band script's `load_files`,
`distinct_states`, `AsOf` and `recal_times` through `importlib`, so the archive walk, the
state definition and the as-of rule have one definition across both evidence folders; targets
come from `training/targets.py`; the lambda floor, single fit per model, fit-row-only
standardisation, block bootstrap and leave-one-out common mode are as the amendment states.

## Mathematical / Statistical details

All in log target space `L_q = log y_q`, so bands are relative and increments multiplicative.

- **Event view.** Per qubit, re-measurement events are files where `L_q` changes; increments
  `D_k = L_k - L_{k-1}`. The pooled lag-1 Pearson correlation of `(D_k, D_{k+1})` is the memory
  statistic. Under a Gaussian local-level model in event time, `L_k = mu_k + e_k`,
  `mu_k = mu_{k-1} + eta_k`, the lag-1 autocorrelation of increments is
  `rho = -sigma_e^2 / (sigma_eta^2 + 2 sigma_e^2)`, so `rho = -0.5` is noise around a fixed
  level and `rho = 0` a random walk. With signal ratio `q = -1 / rho - 2` and steady-state
  filter variance ratio `P / sigma_e^2 = (q + sqrt(q^2 + 4q)) / 2`, the best own-history
  `R^2` for the next increment is `1 - (1 + P / sigma_e^2)(-rho)`; it is 0.5 at `rho = -0.5`
  and 0 at `rho = 0`. The reversion regression `D_{k+1} = a + b (L_k - level_k) + e` uses the
  trailing 30-day event mean as the level.
- **Horizon view.** For state time `t` and qubit `q`, the change `D_H = L_q(t + H) - L_q(t)`
  with the as-of file rule of PR #123. Models: persistence (`0`), shrinkage (`-kappa dev`,
  `kappa` by least squares on fit rows), ridge on standardised features with an unpenalised
  intercept and `lambda = 1`, and the per-qubit rolling 30-day 10th to 90th percentile band of
  `L_q`. Out-of-sample `R^2` uses the fit rows' mean change as the reference predictor.
  Split-conformal 80% bands take the `inverted_cdf` 80th percentile of absolute residuals on
  calibration rows (2026-08-10 to 2026-08-31). Interval score as in PR #123 (D2), log units.
- **Common-mode share.** `R^2` of a qubit's change on the leave-one-out chip mean change at
  the same time, test change rows.
- **Bootstrap.** 1,000 resamples, `SeedSequence(84)`: qubits for event-view statistics,
  state times for `kappa`. Still optimistic, since qubits share every state time.

## Design decisions

- **Gap above shrinkage, not raw `R^2`.** The reason is in the approach section; the
  derivation is README §2.1 item 1. Alternative rejected: keeping the pre-registered threshold
  and noting the issue afterwards, which would have let a known-wrong rule produce the headline.
- **An analytic cap next to the empirical ladder.** The cap turns "the linear model did not
  beat shrinkage" into "nothing built on this history can", which is the statement the deep
  engine's priority depends on. It rests on a stated model and is reported with its interval.
- **Log space with a lambda floor.** Multiplicative jumps and a relative band; the floor is the
  price of lambda's boundary at `T_2 = 2 T_1`, stated in advance with the excluded count.
- **Import, do not copy, the archive walk.** One definition of states and as-of across the two
  evidence folders; a reviewer checks it once.
- **Horizon view scored on change rows** (L-026), `all` rows reported only for the vacuity
  check.

## Verification

- Reproduce from the repository root with the pinned interpreter:
  `PYTHONPATH=src:. python docs/evidence/predictability/measure_predictability.py --repo . --ref 5828b4a2 --out /tmp/pred`
  (Windows: `PYTHONPATH=src;.`). Counts and figures must match the committed `summary.json` and
  `results.tsv` to the printed precision; the interpreter and numpy fields will differ.
- The script's own gates: 924 states against the state index; zero-width coverage exactly 0.0
  on change rows (it aborts otherwise).
- Regression guard for the `--feature readout` addition: `--feature targets` re-run at
  `bcf983f7` reproduced the committed `results.tsv` byte for byte (`cmp` clean), so no gamma or
  lambda figure moved when the option was added.
- Analytic checks of the cap: `rho = -0.5` gives 0.5, `rho = 0` gives 0; shrinkage's measured
  `R^2` (0.43 to 0.45) lies inside the cap's training interval (0.34 to 0.44) or at the test
  limit (0.48 to 0.50), as the model predicts.
- Lint: `ruff check` and `ruff format --check` pass on the script with ruff 0.15.12.
- Not verified: Burak's desktop reproduction (owed); anything outside target space.

## Related docs

- `docs/evidence/predictability/README.md`; `docs/evidence/persistence-band/README.md`
- `docs/numerical-claims.md` NC-084, NC-085; NC-080 to NC-083; NC-012
- `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`;
  `docs/findings/2026-10-23-novelty-check-q1-article.md`
- Issue #110 (decision A7), Issue #64, PR #111, PR #123; ADR-013, ADR-027
