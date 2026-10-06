# 2026-10-05: feature-pattern-analysis

## Problem / Motivation

On 2026-10-05 the lead asked for a model that forecasts the error values IBM publishes for
`ibm_fez`, starting from the feature patterns in the calibration archive and the most
successful method in the literature, with the model-building steps to be walked through
together afterwards. He chose two targets (decision A9, appended to
`docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md`): the gate errors themselves
and ADR-027's `(gamma, lambda)`. The plan of 2026-10-04 (Issue #110, PR #111) had only
provisional observations from 60 sampled files and no measurement of whether any field
carries signal about another field's next value. Without that, neither the choice of model
nor the baseline it must beat can be argued from data.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/feature_patterns.py` | New two-stage script: `extract` reads every snapshot blob at a pinned `calibration-data` ref into a value-and-date cache, `analyze` turns the cache into a JSON report of re-measurement events, cadence, temporal memory, horizon skill, cross-field signal, coherence-limit share, readout noise floor, faults and neighbour correlation. |
| `tests/test_feature_patterns.py` | Pins the event rule and its placeholder mask, the local-level algebra (round trip of `q`, the Riccati condition, recovery of a simulated `q`), the coherence-limit formula, `extract` and the cache round trip on a fake archive, and the blob reader against the request volume that deadlocked the first version. |
| `docs/roadmap/2026-10-05-feature-patterns-and-method.md` | The findings, the literature verdict and the recommended method for both targets, with the model-building steps as gated tasks. |
| `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` | Appended a dated as-of section recording decision A9 and the A1 to A8 assumption; the original text is untouched. |
| `docs/implementations/2026-10-05-feature-pattern-analysis.md` | This record. |

## Implementation approach

**Reading the archive.** `extract` lists the snapshot blobs of one backend at a pinned ref
with `git ls-tree` and streams them through a single `git cat-file --batch` process, one
request at a time (writing all requests first deadlocks once both pipe buffers fill, which
the first run did). It never checks the archive out, so `core.autocrlf` cannot touch it, and
never uses the network. For every file it stores, per qubit, `T1`, `T2`, `readout_error`,
`prob_meas0_prep1`, `prob_meas1_prep0`, `readout_length`, `init_error`, the `sx`, `measure`
and `measure_2` gate errors and the `sx` gate length; per coupler, the `cz` and `rzz` gate
errors and lengths. Each value is stored with the date IBM stamped on it. Files are ordered
by `last_update_date`.

**Duplicates are checked, then collapsed.** While reading, `extract` compares the `id`, `rx`,
`x` and `xslow` gate errors with `sx` on every qubit of every file, and the two directions
of every coupler. Only after those checks pass are the aliases dropped and the two
directions merged into one unordered pair (keeping the later stamp).

**The unit is the re-measurement event.** For one series (one field on one qubit or
coupler), an event is a file where both the value and the stamped date differ from the
series' previous record. `gate_error >= 1` is IBM's "not calibrated" placeholder; the
history endpoint re-stamps its date whenever it assembles a document
(`docs/implementations/2026-09-07-payload-digest-parameter-dates.md`), so placeholder
records are masked before events are counted. The two mismatch cases (value moved with the
date kept, date moved with the value kept) and any date regression are counted and
reported per family.

**What `analyze` measures,** all pooled over the series of a family:

- cadence: events per series, the gap between events, and device-wide rounds (event stamps
  split wherever two consecutive stamps are more than 15 minutes apart);
- memory: the lag-1 autocorrelation of changes in `log10` value, and one-step forecast
  error of persistence, the expanding mean and EWMA at fixed weights, scored from the fifth
  event on;
- horizon skill at `h = 1, 2, 4, 8, 16` events for persistence, the expanding mean and EWMA
  at the local-level weight;
- cross-field signal: a least-squares model of the next deviation from the target's own EWMA
  level, with and without the deviations of the other fields at time `t`, fitted before a
  70% time cut and scored after it;
- the coherence-limit share of each gate error, the readout decomposition and shot-noise
  floor, placeholder episodes, field ages, and the correlation of `sx` changes between
  coupled and distant qubits after removing the device-wide mean change;
- the device-wide mean of each family (stage A's view) with the same memory statistics.

## Mathematical / Statistical details

**Local-level model.** Write `z_k = log10 y_k` for the `k`-th event of one series and model
it as a level observed through noise: `z_k = mu_k + eps_k`, `mu_k = mu_{k-1} + eta_k`, with
`eps` and `eta` independent, zero-mean, variances `s_eps^2` and `s_eta^2`. The change
`dz_k = eta_k + eps_k - eps_{k-1}` has lag-1 autocorrelation

```
rho_1 = -s_eps^2 / (s_eta^2 + 2 s_eps^2) = -1 / (q + 2),   q = s_eta^2 / s_eps^2.
```

So `q = -1/rho_1 - 2`, defined for `-0.5 < rho_1 < 0`. A pure random walk has `rho_1 = 0`;
noise around a fixed level has `rho_1 = -0.5`. The minimum-mean-square one-step forecast of
this model is EWMA with the steady-state Kalman gain

```
alpha = (-q + sqrt(q^2 + 4 q)) / 2.
```

The script estimates `rho_1` pooled over a family, derives `q` and `alpha`, and uses that
`alpha` for the horizon and cross-field measurements. Because `rho_1` is estimated on the
whole archive, this is one scalar of look-ahead per family; the fixed weights 0.1, 0.3 and
0.5 are reported alongside, and they bracket the same skill.

**Skill.** Mean absolute error in `log10` units, divided by persistence's on the same
events (1.0 = persistence, below 1 is better). In the horizon test the forecast of `z_k` uses
only events up to `k - h`.

**Cross-field test.** With `L_{k-1}` the EWMA level after event `k - 1`, the response is
`r_k = z_k - L_{k-1}` and the predictors are the target's own deviation `z_{k-1} - L_{k-1}`
and, for each other field on the same qubit (both qubits averaged for a coupler), its latest
value minus its own EWMA level, read from the last file before event `k`. Ordinary least
squares on events stamped before the 70% quantile of event time; mean absolute error after
it. Persistence's error on the same rows is `|r_k - (z_{k-1} - L_{k-1})|`, and the level-only
error is `|r_k|`.

**Coherence limit.** For a single-qubit idle of length `t` under amplitude damping and pure
dephasing, the process fidelity is `F_pro = (1 + e^{-t/T1} + 2 e^{-t/T2}) / 4` and the
average gate fidelity `F = (2 F_pro + 1) / 3 = (3 + e^{-t/T1} + 2 e^{-t/T2}) / 6`, so the
coherence-limited error is `1 - F`. For a two-qubit gate the two qubits' process fidelities
multiply and `F = (4 F_pro + 1) / 5`. Each gate uses its own published length. The script
reports the ratio limit / measured error and correlations of the logs: within one file
across entities (Spearman), between entities on their time means, and within an entity
after removing its time mean.

**Readout shot noise.** `prob_meas0_prep1` and `prob_meas1_prep0` are each a fraction of
4096 shots and `readout_error = (p01 + p10) / 2`, so one estimate has variance
`(p01 (1 - p01) + p10 (1 - p10)) / (4 * 4096)`. By the delta method its standard deviation in
`log10` units is `0.4343 * sd / readout_error`, and the difference of two independent
estimates has `sqrt(2)` times that in the equal-variance case (the script uses both events'
own values). Under pure shot noise 95.45% of changes would fall within two standard
deviations.

**ADR-027 target.** `gamma = 1 - exp(-t/T1)`, `lambda = 1 - exp(-t (2/T2 - 1/T1))`, with `t`
the `sx` gate length and the `T2 <= 2 T1` rule of `training/targets.py`. The script computes
it on the cache in microseconds; its values were checked against `qubit_targets` (see
Verification). The `lambda` event stamp is the later of the `T1` and `T2` dates.

## Design decisions

- **Events, not files or states, as rows.** Of the 1,753 files most repeat the previous
  value of any one field; counting files would weight a value by how often it was polled.
  Distinct states (the health index's unit) are distinct over the whole per-qubit block, so
  they mix fields re-measured on different clocks. A per-series event is the unit at which a
  forecast can be right or wrong.
- **`log10` space.** Measured errors in the archive run from 7.2e-5 (`sx`) to 0.57
  (`measure_2`), almost four decades, and their changes are
  multiplicative, so absolute errors in linear units would be dominated by a few bad
  entities.
- **A cache and a separate `analyze`.** Parsing 3 GB of JSON takes about half a minute and is
  the step that touches the archive; every later question re-reads a compressed cache of
  about 2.4 MB.
- **Linear cross-field test, not a network.** The question here is whether any field carries
  out-of-time signal at all, and a linear model answers it cheaply and without tuning. A
  nonlinear screen is stage 1's job (plan T5) and is listed as a gated task, not run here.
- **No numerical-claims rows.** Every figure is orientation data (memory rule: plan ahead
  means tasks, not runs); the registered measurements are the plan's T1, T12 and T13 on the
  verification desktop.

## Verification

In a Python 3.12 venv built from `requirements.txt` (numpy 2.4.4, scipy 1.17.1):

```bash
git fetch origin calibration-data
python -m scripts.feature_patterns extract --repo . --ref 09fcc4561e74d7ca619f738cbb3370eeced5ee89 --out fp_cache.npz
python -m scripts.feature_patterns analyze --cache fp_cache.npz --out fp_report.json
python -m pytest tests/test_feature_patterns.py -q
ruff check scripts/feature_patterns.py tests/test_feature_patterns.py
ruff format --check scripts/feature_patterns.py tests/test_feature_patterns.py
mypy scripts/feature_patterns.py
```

The deadlock test was mutation-checked on 2026-10-05: with the previous reader (write every
request, then read) it hangs; with the current one it reads all 2,000 blobs. The full suite
passed (721 tests) with `PYTHONPATH=src` in that venv.

Expected, self-consistent rather than absolute: `extract` prints `1753 files, 176 edges`;
in `fp_report.json`, `extract_checks.alias_value_mismatch` and
`extract_checks.edge_direction_value_mismatch` are 0, `readout.measure_eq_readout_error` is
1.0, and `readout.readout_eq_mean_when_dates_equal` is at least 0.9999. Running `analyze`
twice on one cache gives byte-identical reports (checked on 2026-10-05 after a refactor).

The ADR-027 values were cross-checked on 2026-10-05 against
`superconducted.training.targets.qubit_targets` on five files spread over the archive
(indices 0, 400, 900, 1300, 1752): the usable masks were identical and the largest relative
difference over 775 qubits was 8.1e-14.

## Related docs

- `docs/roadmap/2026-10-05-feature-patterns-and-method.md` (the findings)
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (A1 to A9, tasks T1, T12, T13)
- `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` (the 2026-10-04 survey)
- ADR-027 in `docs/decisions.md`; `src/superconducted/training/targets.py`
- `docs/implementations/2026-09-07-payload-digest-parameter-dates.md` (the placeholder date)
- Issue #110, PR #111
