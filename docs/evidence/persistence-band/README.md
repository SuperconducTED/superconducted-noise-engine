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

## 3. Results

To be appended by the run, with the commit that produced them. Until then this section is
empty on purpose.

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
PYTHONPATH=src python docs/evidence/persistence-band/measure_persistence_band.py --repo . --ref 5828b4a2 --out /tmp/persistence-band
```

Compare `/tmp/persistence-band/summary.json` with the committed one. Expected: identical
counts and identical figures to the printed precision; the only randomness is the seeded
bootstrap. Differences in the bootstrap intervals beyond the last printed digit are a finding,
not noise.

## 6. Related

Issue #64 FR-9 and NFR-8 as amended by #84 comment 5970300012 (Q3c); Issue #104; ADR-013,
ADR-016, ADR-027; NC-012, NC-041, NC-069; `docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` §4.
