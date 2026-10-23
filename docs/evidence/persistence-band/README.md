# Persistence band, heteroscedasticity bound, homogeneity versus staleness

**Date**: 2026-10-23 · **Author**: Mert Efe Şensoy · **Protocol pre-registered before the run**
(section 2 was committed before `measure_persistence_band.py` produced a number; the
results in section 3 were appended afterwards, with the commit that produced them) ·
**Owner of the question**: Issue #64 (@bengisucvd), Issue #104 for the cadence figures ·
**Status**: laptop run, provisional; canonical verification on Burak's desktop owed (runbook
in section 5)

## 1. Why these three, and why before any model

The novelty check (`docs/findings/2026-10-23-novelty-check-q1-article.md` §4) and the gates
record (`docs/findings/2026-10-23-adr-015-what-an-interval-needs.md` §3, §5) say the engine's
headline claim is decided by one comparison: a fuzzy band must beat a non-fuzzy band over
recent snapshots on coverage and width together, on a time split, scored on rows where the
truth actually moved. That bar can be measured today on the archive, with no trained model,
and so can two facts the article cannot avoid: whether drift is state-dependent (if it is not,
no conditional band, fuzzy or otherwise, can be narrower than a constant one at equal
coverage), and whether a fresh chip-uniform channel costs more than a stale per-qubit one
(the engine's channel is spatially uniform; every competing baseline is per-qubit).

Everything here is in **target space**: the ADR-027 per-qubit pair $(\gamma, \lambda)$ from
each qubit's $T_1$, $T_2$ and its `sx` gate length, in SI units, with ADR-027's ordered skip
rules exactly as `training/targets.py::qubit_targets` applies them. No circuit, no shot, no
Aer. Outcome-space resolution is a separate question (gates record §4).

## 2. Protocol, fixed before the run

**Data.** `calibration-data` @ `5828b4a2`, `ibm_fez`, every `snapshots/**/*.json` read
through `git show` at that ref (the walk `scripts/init_error_analysis.py` provides). One row
per **distinct device state**: files are ordered by `properties.last_update_date` and a file
is kept only if its `qubit_digest` (`scripts/canonical_snapshot_digest.py`, the NC-012 unit)
differs from every earlier kept file's. The time of a state is its first file's
`last_update_date`. Expected count at this ref: 924 (NC-069's lineage; re-measured by the
script and printed).

**Targets.** Per state: the per-qubit `(gamma, lambda)` from `qubit_targets` with the `sx`
gate lengths from `gate_lengths`; the snapshot target `y(t)` is the mean over usable qubits
(`snapshot_target`). Per-qubit values are kept for measurement 3.

**Time axis and horizons.** `t` is the state time. For horizon `H` in {24 h, 168 h}, the
future value is the state **as of** `t + H`: the latest state with time `<= t + H`, accepted
only if its time is `> t + H - 6 h` (so a long outage never pairs `t` with a value older than
the horizon it claims). Pairs failing that are dropped and counted.

**Split.** Snapshot boundary at `2026-09-01T00:00:00Z`. A pair belongs to the training period
if `t < cut`, to the test period if `t >= cut`, and is **dropped** if `t < cut <= t + H` (no
pair straddles the cut). The cut date was chosen before any number was seen: it leaves about
3.5 months of training and 1.7 months of test, and it predates the 2026-09-10 cron change that
densified sampling, which is noted as a known difference between the periods.

**Scoring rows.** Three row sets, all reported:

- `change`: pairs with `y(t + H) != y(t)` in the component being scored (any usable qubit's
  re-measurement changes the mean, so exact inequality is the right test);
- `distinct`: pairs whose two states have different `qubit_digest` (a superset of `change`
  that also counts readout-only changes);
- `all`: every accepted pair, reported **only** to show how much a zero-width band scores
  when the truth has not moved.

The headline rows are `change`. A band whose coverage is reported on `all` is not comparable
to anything in this file.

**Persistence band.** `B(t) = [y(t)(1 - r), y(t)(1 + r)]`. On training `change` rows, `r` is
the smallest value with coverage `>= 0.80`: the 80th percentile of `|y(t + H) / y(t) - 1|`
(`numpy.quantile`, `method="higher"`). On test rows: coverage, mean relative width `2r`, and the
mean **interval score** at `alpha = 0.2` (Gneiting and Raftery 2007, section 6.2, eq. 43),

$$
\mathrm{IS}_\alpha(l, u; y) = (u - l) + \tfrac{2}{\alpha}(l - y)\,\mathbf{1}[y < l]
+ \tfrac{2}{\alpha}(y - u)\,\mathbf{1}[y > u],
$$

divided by `y(t)` so it is scale-free, averaged over test rows. Lower is better; it rewards
narrow bands and penalises misses in proportion to how far they miss.

**Rolling percentile band** (the novelty check's §4 item 2 literally): at `t`, the band is
`[Q_0.10, Q_0.90]` of `y` over the distinct states in the trailing window `W` in {7 d, 30 d},
requiring at least 5 states; no fitted parameter. Same test metrics, same rows.

**Heteroscedasticity bound.** On training `change` rows at each `H`, the relative drift
`d = y(t + H) / y(t) - 1` is binned three ways, each pre-fixed:

- `level`: terciles of `y(t)` (tercile edges from the training rows);
- `hour`: UTC hour of `t` in blocks 00-05, 06-11, 12-17, 18-23;
- `recal`: hours since the last chip-wide $T_1$ recalibration before `t`, in {< 12, 12 to 24,
  > 24}, where a chip-wide recalibration is a consecutive pair of states in which at least 20%
  of usable qubits' $T_1$ `calibrated_time` changed (the dataset card's own threshold, applied
  to our documents).

For each binning: the per-bin 80th percentile `r_b` on training rows; the **conditional band**
on test rows uses `r_b` of the row's bin (out of sample); the **oracle** fits `r_b` on the test
rows themselves (in sample, an upper bound on what any band conditioned on that binning can
achieve at 80%). Reported against the constant band: coverage, mean width, interval score, and
the width ratio `mean(r_b) / r`. A bootstrap over rows (1,000 resamples, `SeedSequence(84)`)
gives 90% intervals on each `r_b`, so a difference between bins can be read against sampling
noise. A conditional band that is not narrower than the constant one at equal coverage means
the archive does not reward state-conditioning at that binning.

**Homogeneity versus staleness.** On test times `t` and usable qubits `q`, truth `y_q(t)`.

- `homogeneous_fresh`: `yhat = mean_q' y_q'(t)` (what a spatially uniform channel emits);
- `stale_per_qubit(D)`: `yhat = y_q(t - D)` as of `t - D` (latest state `<= t - D`, accepted
  only if `> t - D - 6 h`), for `D` in {1, 6, 24, 48, 168} h.

Per model: median and 90th percentile of `|yhat / y_q(t) - 1|` over all `(t, q)`, and the
fraction of `(t, q)` inside `[yhat(1 - r*), yhat(1 + r*)]` with `r*` the 24 h persistence `r`
fitted above. Two row sets: `all`, and `moved`, the `(t, q)` where `y_q(t) != y_q(t - D)`.
The decisive number is the `D` at which the stale per-qubit error first exceeds the fresh
homogeneous error, if any `D` in the grid does.

**Decision rule, written before the numbers.** The fuzzy band, when it exists, is compared
on the same test rows (`change`, both `H`) by interval score first and by coverage-and-width
second. If it does not beat the constant persistence band on interval score, the article's
drift claim is withdrawn and the fuzzy contribution is framed as interpretability and the IT2
footprint. If the heteroscedasticity oracle gains less than 10% width at equal coverage on
every binning, no conditional band is expected to beat persistence on this archive and the
comparison is reported as a negative result.

**Provenance.** Script `measure_persistence_band.py` (this folder), run with the pinned
interpreter (`C:\pvci\Scripts\python.exe`, qiskit 2.4.1, numpy 2.4.4, scipy 1.17.1; only
numpy is used) and `PYTHONPATH=src` from the repository root. Outputs `results.tsv` (one row
per reported figure) and `summary.json`. Seeds: `SeedSequence(84)` for the bootstrap; nothing
else is random.

### 2.1 Amended before the run, 2026-10-23 (no number existed yet)

Four definitions above were loose enough to bias or move the result. They are corrected here
rather than edited in place, and this block was committed before the script produced
anything.

1. **As-of lookups use files, not states.** Rows remain distinct states, but the value as of
   `t + H` (and as of `t - D` in measurement 3, and the chip-wide recalibration clock) is the
   latest **file** with `last_update_date <= t + H` inside the 6 h window, mapped to its
   state. The original wording ("the latest state") would have required a new state to
   appear inside the window, dropping every pair in which the device changed earlier and then
   sat still, and emptying the `all` row set the vacuity check needs.
2. **Measurement 3 gains a co-primary in target units.** `|yhat / y - 1|` is unstable for
   `lambda`, which approaches zero when `T_2` approaches `2 T_1` (heterogeneity 177% of the
   mean in File 03). The median absolute error in target units is reported beside it, and a
   qubit enters the stale model only if it is usable at both `t` and `t - D`. The fresh model
   is also scored on each `D`'s `moved` rows so the two are compared on identical rows.
3. **Heteroscedasticity, three tightenings.** (a) The width ratio is the test-row-weighted
   mean of the applied `r_b` over the constant `r`, not a mean over bins. (b) "At equal
   coverage" compares the per-bin oracle with the constant band's **own** oracle `r` fitted on
   the test rows, since the train-fitted constant `r` is not at 80% on the test period. (c)
   `level` terciles are per component: `gamma`'s drift binned by `gamma`'s level, `lambda`'s
   by `lambda`'s. Bins with fewer than 20 training rows fall back to the constant `r` and are
   flagged.
4. **Quantile method.** "Smallest `r` with coverage `>= 0.80`" is the order statistic at
   `ceil(0.8 n)`, which is `numpy.quantile(..., method="inverted_cdf")`; `"higher"` returns one
   order statistic up on most `n`.

Also fixed before the run: the mutation check of L-009 is built in (the zero-width band's
coverage is printed on `all` and on `change` at each `H`; the first should sit near the repeat
rate, the second must be exactly 0.0, otherwise the row definition is wrong); the test pairs
(state time, as-of file time, digests, change flags) are written to `pairs.tsv` so the fuzzy
band is later scored on citable, identical rows; the script asserts the distinct-state count
against `health/state-index.tsv` at the ref and stops on a mismatch; dropped pairs are counted
per reason. The runbook's `PYTHONPATH` must include the repository root as well as `src`, since
the script imports the shared archive-walk helpers from `scripts/`.

## 3. Results

Produced by `measure_persistence_band.py` at commit `ed746536` of this branch, run 2026-10-23
on Mert's laptop with `C:\pvci` (Python 3.12.10, numpy 2.4.4) against `calibration-data` @
`5828b4a2`. Every figure is in `results.tsv`; the test rows are in `pairs.tsv`. **Laptop,
provisional.** The script's own checks passed: 924 distinct states, equal to the state index
at the ref; the zero-width band covers exactly 0.0 of the `change` rows at both horizons.

**Counts.** 2,249 files, 924 states, first 2026-05-13T12:13:22Z, last 2026-10-23T09:34:56Z;
151 chip-wide $T_1$ recalibrations detected. Pairs at 24 h: 476 train, 378 test, 68 dropped
(no file in the window), 2 straddling the cut. At 168 h: 423 train, 344 test, 138 and 19
dropped. On `all` test rows the zero-width band covers 0.135 at 24 h and 0.0 at 168 h: the
snapshot mean moves within a day in 86% of 24 h pairs and in every 168 h pair, so the
vacuity risk of L-026 is real at sub-daily horizons and vanishes by a week (per-qubit values
repeat far more; see measurement 3).

### 3.1 The bar: constant persistence band versus rolling percentile band

Test rows are `change`; `distinct` and `all` differ from them only at 24 h and are in the TSV.

| Component, horizon | n test | `r` fitted on train (90% bootstrap) | `r` the test period would have needed | Persistence: coverage, width, interval score | Rolling 7 d: coverage, width, IS | Rolling 30 d: coverage, width, IS |
| --- | --- | --- | --- | --- | --- | --- |
| gamma, 24 h | 327 | 0.1049 (0.0937 to 0.1119), n = 397 | 0.1249 | 0.716, 0.210, **0.300** | 0.728, 0.138, 0.232 | 0.780, 0.163, **0.210** |
| lambda, 24 h | 327 | 0.1140 (0.1022 to 0.1208), n = 397 | 0.0700 | 0.951, 0.228, **0.233** | 0.737, 0.103, 0.178 | 0.777, 0.116, **0.157** |
| gamma, 168 h | 344 | 0.1751 (0.1618 to 0.1989), n = 423 | 0.1119 | 0.924, 0.350, **0.356** | 0.724, 0.141, 0.209 | 0.756, 0.165, **0.207** |
| lambda, 168 h | 344 | 0.1496 (0.1347 to 0.1574), n = 423 | 0.0733 | 1.000, 0.299, **0.299** | 0.820, 0.102, 0.146 | 0.799, 0.119, **0.154** |

Three things the table says.

1. **The persistence scale is not stationary.** Fitted on May to August, `r` misses 80% on
   September to October in both directions: gamma's drift grew (72% coverage at 24 h, the
   test period would have needed 0.125) and lambda's shrank (95%, it needed 0.070). The 90%
   bootstrap intervals on `r` do not contain the test-period value in any of the four cases.
   A band whose single parameter is fitted once and frozen is therefore mis-calibrated by
   20 to 40% within two months on this device, whichever way the device moves.
2. **The rolling 30-day 10th to 90th percentile band beats the fitted persistence band on
   interval score in all four cases**, with no fitted parameter: 0.210 against 0.300 and
   0.157 against 0.233 at 24 h, 0.207 against 0.356 and 0.154 against 0.299 at 168 h. At
   24 h it is 22% narrower for gamma (0.163 against 0.210) and 49% narrower for lambda
   (0.116 against 0.228) at near-nominal coverage (0.78, 0.78); at 168 h, 53% and 60%. Its
   coverage barely moves from 24 h to 168 h (0.78 to 0.76, 0.78 to 0.80), while the
   persistence scale has to grow by two thirds for gamma (0.105 to 0.175) and by a third for
   lambda (0.114 to 0.150) to hold a week. The device's snapshot mean behaves like fluctuation
   around a slowly moving level, not like a random walk from the last value, and a band
   centred on the recent range exploits that while a band centred on the last value cannot.
3. **The bar for the fuzzy band is therefore the rolling 30-day percentile band**, not the
   persistence band: interval score 0.210 (gamma) and 0.157 (lambda) at 24 h, 0.207 and
   0.154 at 168 h, on exactly the rows in `pairs.tsv`. The pre-registered decision rule
   named the constant persistence band; the stronger non-fuzzy baseline found by the same
   protocol replaces it, and that replacement is recorded here before any fuzzy band exists.

### 3.2 Heteroscedasticity: is drift state-dependent?

Per-bin 80th percentiles of `|d|` on training `change` rows, with 90% bootstrap intervals:

| Component, horizon | `level` low / mid / high | Oracle width ratio, equal coverage: level, hour, recal | Out-of-sample conditional band (level): coverage, width ratio, IS against constant IS |
| --- | --- | --- | --- |
| gamma, 24 h | 0.113 (0.107 to 0.135) / **0.062** (0.061 to 0.070) / 0.112 (0.106 to 0.133) | **0.857**, 1.013, 0.989 | 0.593, 0.756, 0.319 against 0.300 (worse) |
| lambda, 24 h | 0.117 (0.084 to 0.124) / **0.091** (0.084 to 0.100) / 0.121 (0.113 to 0.129) | **0.894**, 0.988, 1.039 | 0.917, 0.932, 0.220 against 0.233 (better) |
| gamma, 168 h | 0.200 (0.175 to 0.222) / **0.120** (0.101 to 0.135) / 0.270 (0.196 to 0.282) | 0.980, 0.989, 1.010 | 0.959, 0.882, 0.319 against 0.356 (better) |
| lambda, 168 h | 0.182 (0.155 to 0.216) / **0.111** (0.104 to 0.117) / 0.157 (0.134 to 0.163) | 0.926, 0.984, 0.980 | 0.994, 1.101, 0.330 against 0.299 (worse) |

- **Only the level of the target carries information about drift.** Hour of day and time
  since the last chip-wide recalibration give oracle width ratios within 4% of 1 everywhere:
  nothing to find. The `level` binning shows the same shape in all four cases: the middle
  tercile drifts about half as much as the outer terciles. For gamma at 24 h the middle
  bin's bootstrap interval (0.061 to 0.070) is disjoint from both outer bins (0.106 and
  above); for lambda the low bin's interval (0.084 to 0.124) overlaps the middle's (0.084 to
  0.100), so the effect is established for gamma and suggestive for lambda. That is mean
  reversion in the snapshot mean, the same fact behind the rolling band's win in 3.1.
- **The bound is small.** Even an oracle that knows the test period's per-level scales gains
  14% width for gamma and 11% for lambda at 24 h, 2% and 7% at 168 h, at equal coverage.
  Against the pre-registered 10% threshold the 24 h `level` binning crosses it and nothing
  else does. Out of sample, the gain is realised for lambda at 24 h and gamma at 168 h, and
  lost for the other two, because the per-bin scales move between periods as much as the
  constant one does.
- **Consequence for a conditional band, the fuzzy one included.** A band whose width depends
  on the snapshot's state has at most about 10 to 15% of width to gain over a constant band
  at 24 h on this device, and the rolling percentile band already gains more than that by
  centring on the recent range rather than the last value. A fuzzy band that only modulates
  width around the current point cannot beat the rolling band here; one that also moves its
  centre toward the recent level could.

### 3.3 Homogeneity versus staleness

Test states from 2026-09-01, all usable qubits; `r*` is the 24 h persistence `r` (gamma
0.1049, lambda 0.1140). `all` rows; `moved` rows and 90th percentiles are in the TSV.

| Component | Model | Median relative error | Median absolute error (target units) | Fraction within ±`r*` | Rows |
| --- | --- | --- | --- | --- | --- |
| gamma | fresh homogeneous (chip mean at `t`) | **0.266** | 5.1e-5 | 0.217 | 62,701 |
| gamma | stale per-qubit, 1 h | 0.000 | 0.0 | 0.901 | 61,755 |
| gamma | stale per-qubit, 6 h | 0.000 | 0.0 | 0.800 | 59,889 |
| gamma | stale per-qubit, 24 h | 0.201 | 3.7e-5 | 0.328 | 60,717 |
| gamma | stale per-qubit, 48 h | 0.229 | 4.3e-5 | 0.255 | 59,915 |
| gamma | stale per-qubit, 168 h | **0.232** | 4.4e-5 | 0.243 | 59,319 |
| lambda | fresh homogeneous | 1.205 (denominator artefact) | **4.4e-4** | 0.051 | 62,701 |
| lambda | stale per-qubit, 24 h | 0.170 | 5.8e-5 | 0.397 | 60,717 |
| lambda | stale per-qubit, 168 h | 0.198 | **6.7e-5** | 0.336 | 59,319 |

- **A per-qubit channel a week stale beats a fresh chip-uniform one, for both components and
  on every metric, but the margins differ by an order of magnitude.** For gamma the fresh
  homogeneous model's median relative error is 26.6% against 23.2% for a value 168 hours
  old, and it places 21.7% of qubits inside the ±10.5% band against 24.3%: a margin of 3.4
  and 2.6 points, real on 60,000 rows but small. For lambda the gap is a factor of six to
  seven in target units (4.4e-4 against 6.7e-5) and the homogeneous band holds 5.1% of
  qubits against 33.6%: decisive. **No staleness in the grid reaches the crossover**; the
  gap narrows from 1 h to 24 h and is flat from 48 h to 168 h. The article should lead with
  lambda and with the band fraction; the gamma margin alone could be read as noise.
- **Per-qubit re-measurement jumps are large.** On `moved` rows (the qubit's own value
  changed within `D`) the stale model's median relative error is 23.3% for gamma at every
  `D` from 1 h to 168 h: when a qubit's $T_1$ is re-measured, its gamma moves by about a
  quarter, independent of how long ago the previous measurement was. The snapshot mean's
  10% drift is that jump averaged over 156 qubits. A per-qubit band therefore has a natural
  width near ±25%, and cross-qubit heterogeneity (26.6% median deviation from the mean)
  is of the same size, which is why "fresh and uniform" ties with "a week stale per qubit"
  rather than beating it.
- The two findings together answer the novelty check's spatial-uniformity risk with a
  number: on this device, replacing per-qubit structure with a fresh chip mean costs more
  than a week of not updating at all.

### 3.4 Caveats found by the run

- The constant persistence band's non-stationarity (3.1, point 1) means any single fitted
  scale, including the fuzzy arm's `r` under File 03 Q3c, will be off by tens of percent on
  the next period; the comparison in the decision rule must be made on the same test rows
  and reported with the scale each band needed, not only the one it had.
- The 168 h `all` row set has no unchanged pairs, so the vacuity check there is trivially
  passed and only the 24 h value (0.135) measures the clock.
- Target space only; the resolution question (gates record §4) is untouched.

## 4. Caveats fixed in advance

- Distinct is not independent (NC-012): consecutive states are temporally correlated, so
  bootstrap intervals over rows are optimistic.
- The 2026-09-10 cron change densified sampling, so the test period has finer time
  resolution than the training period; as-of pairing at `H` with a 6 h acceptance window
  limits, but does not remove, that difference.
- `y(t)` is a snapshot mean of a nonlinear per-qubit target (ADR-027 keeps it that way on
  purpose); the mean's drift is smaller than any one qubit's.
- Target space only. A band invisible under shot noise in outcome space (gates record §4) is
  still a band here.

## 5. Runbook for the canonical run (Burak's desktop)

```bash
git fetch origin calibration-data
```

```bash
PYTHONPATH=src:. python docs/evidence/persistence-band/measure_persistence_band.py --repo . --ref 5828b4a2 --out /tmp/persistence-band
```

On Windows the separator is `;` (`PYTHONPATH=src;.`).

Compare `/tmp/persistence-band/summary.json` with the committed one. Expected: identical
counts and identical figures to the printed precision; the only randomness is the seeded
bootstrap. Differences in the bootstrap intervals beyond the last printed digit are a finding,
not noise.

## 6. Related

Issue #64 FR-9 and NFR-8 as amended by #84 comment 5970300012 (Q3c); Issue #104; ADR-013,
ADR-016, ADR-027; NC-012, NC-041, NC-069; `docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` §4.

## 7. Appendix: the derivations behind the estimands

Written for the reviewer who re-derives every figure. Notation as in §2.

**D1, the fitted scale.** "Smallest `r` with training coverage `>= 0.80`" is the order
statistic of `|d|` at rank `ceil(0.8 n)`, which `numpy.quantile(..., method="inverted_cdf")`
returns. With `method="higher"` the returned value is the next order statistic up whenever
`0.8 n` is not an integer, a training coverage of `(ceil(0.8 n) + 1) / n`.

**D2, the interval score of a symmetric relative band.** With `l = y(1 - r)`, `u = y(1 + r)`
and realisation `y' = y(1 + d)`: `(u - l) / y = 2r`; `(l - y') / y = -r - d` when `d < -r`;
`(y' - u) / y = d - r` when `d > r`. Hence
`S(r; d) = 2r + (2 / alpha) max(0, -r - d) + (2 / alpha) max(0, d - r)`. Proper for the
central `(1 - alpha)` interval (Gneiting and Raftery 2007, Theorem 2), so a band fitted to
80% and scored at `alpha = 0.2` is scored at its own nominal level. For unequal relative
half-widths (the rolling band) the same with `r_lo` and `r_hi`. Checks: `r -> infinity` gives
`2r` (no penalty); `r = 0` gives `(2 / alpha) |d|`.

**D3, why `all` rows score a zero-width band at the repeat rate.** On `all` rows the coverage
of `r = 0` is the fraction of pairs with `d = 0`, the probability that no usable qubit's `T1`
or `T2` was re-measured inside the horizon. On `change` rows it is 0 by definition; the script
stops if it is not. Measured: 0.135 at 24 h, 0.0 at 168 h.

**D4, the oracle is a lower bound on the width ratio.** For a binning `b(t)` and per-bin
scales `r_b` fitted on the test rows themselves to 80%, the row-weighted mean width
`sum_b n_b 2 r_b / n` is the narrowest a band constant within bins can be while covering 80%
in every bin (D1 per bin). A band varying only through `b(t)` that reaches 80% overall is at
least as wide as the best reallocation across bins, which can be narrower than the
per-bin-80% band only by lowering coverage in some bins. So against the constant oracle on the
same rows, `width_oracle_conditional / width_oracle_constant` bounds from below the width
ratio any such band achieves at equal coverage. In the run every oracle ratio was at most
1.04, the excess being per-bin rank rounding on small bins.

**D5, relative error on lambda is a denominator artefact.** `lambda_q -> 0` as
`T2_q -> 2 T1_q` from below, a boundary ADR-027 admits as usable, so `|yhat / lambda_q - 1|`
is unbounded on that tail while `|yhat - lambda_q|` is bounded. Both are reported; lambda is
cited in target units.

**Cross-check.** File 03 M3 (whole archive, no split, 24 h gamma) gave ±11.2% at 80%; the
training-period fit here is 0.1049 with a 90% interval reaching 0.1119: the same size, the
difference being the split and the change-row definition.
