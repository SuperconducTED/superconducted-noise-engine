# 2026-10-26: pattern-detector N1, the nulls and the logistic bar (amendments 3 to 6)

## Problem / Motivation

The lead asked for task N1 of the pattern detector (#110, comment 6412965244) on 2026-10-26:
"the baselines and the amended null forecast on the committed rows, nothing deep". N1 is where
the protocol in `docs/evidence/pattern-detector/README.md` first scores anything against the
labels, so every open implementation choice had to be fixed before the run (amendment 3), and
two defects of the pre-registered null that the counts and the first runs exposed had to be
amended, disclosed and re-run rather than patched in place (amendments 4 to 6). The question the
run answers is clause 1 of the protocol: does a logistic model on the frozen features beat the
null forecast by a Brier skill of at least 0.10 on held-out time?

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pattern-detector/README.md` | Amendments 3 to 6 appended to section 7; section 10 added with the N1 record run, the calibration diagnostic, the scores, clause 1 and its decomposition. |
| `docs/evidence/pattern-detector/collect_fields.py` | New: one archive walk at a pinned ref collecting log `T1`, `T2`, readout error, `sx` error and the best `cz` error per qubit per file into a pickle. |
| `docs/evidence/pattern-detector/n1_baselines.py` | New: the 17-column design matrix, the N0 reproduction guard, the two simulated nulls (empirical-residual primary, Gaussian reference) at the real event times mapped onto the real states with signed `|d|` bins, the test-timing diagnostic, the L2 logistic bar with `lambda` chosen on the inner time slice, scores, paired day-block bootstrap, clause 1, the calibration table and an oracle row; a synthetic self-test. |
| `docs/evidence/pattern-detector/summary.json`, `results.tsv`, `features.tsv.gz`, `null_bins.tsv`, `calibration.tsv` | New: the record run's outputs. |
| `docs/implementations/2026-10-26-pattern-detector-n1-baselines.md` | This record. |

No source, test, plan or register file touched. No NC row; N3 mints them.

## Implementation approach

**Order kept.** Amendment 3 (implementation choices) was committed before the field walk ran;
amendment 4 (the null's noise shape) before any score existed; the N1 script was committed
before each of its three runs; amendments 5 and 6 were written after a run's diagnostic was read
and before its clause was read or recorded, each disclosing the superseded run's figures. The
record run is the third (`77e5a7d8`).

**Data.** `collect_fields.py` repeats the N0 walk once with five fields per qubit (about 20
minutes, 2,330 `git show` calls). `n1_baselines.py` rebuilds the N0 rows from that collection and
stops unless they equal `rows.tsv.gz` (they did: 3,932 rows). Features follow README §3 and
amendment 3: levels for all qubits per event file (so the chip-wide readout excursion and the
same-sign share are over every qubit with a level), the band width from the same window, the
previous event's `d`, hours since the previous event and since the last sweep strictly before `t`,
`T2` and readout disagreements with indicators, `sx` and best `cz` errors, hour of day.

**The nulls** are the protocol's own label computed on simulated series. Per qubit: a local-level
process at the qubit's real re-measurement times (2,000 replicates, `SeedSequence(84)`), noise
drawn either from the qubit's centred residuals rescaled to its robust `sigma_q` (primary) or
Gaussian (reference), drift `eta ~ (0, q sigma_q^2)` with `q` from the pooled training lag-1
autocorrelation; simulated values mapped onto the real states (each state takes the latest
simulated event at or before it) so the level is computed exactly as the protocol computes it,
state weights included; `d_sim` and `y_sim` under the protocol's rules; pairs with `|d_sim| >=
delta` binned by **signed** `d` in 0.05 log-unit bins per qubit, pooled fallback below 200 pairs.
The forecast for a real row is its qubit's bin rate at its observed `d`. A second simulation at
the test period's own event times (windows filled from 30 days before the cut) is the amendment 4
item 5 diagnostic.

**The bar.** Standardised features, L2-penalised logistic regression by Newton's method, `lambda`
from `{0.001, 0.01, 0.1, 1, 10}` by log loss on the last 20% of training rows in time order, refit
on all training rows. Reference rows: constant `p_0`, always-level `p = 0`. Oracle diagnostic:
the constant at the test period's own base rate.

**Scoring.** Brier, log loss, AUC on the 1,294 test rows; paired bootstrap over the 46 test days
(1,000 resamples) for every Brier difference and skill; clause 1 against the lower-Brier null.

## Mathematical / Statistical details

- **Brier skill** against a reference forecast `r`: `BSS = 1 - BS_model / BS_r`. Against the
  empirical null 0.226 (interval 0.157 to 0.299); against the always-level rule 0.156 (0.126 to
  0.178); against the constant 0.217; against the oracle constant at the test rate 0.042.
- **Oracle bound.** A constant at the test base rate `p_t = 0.1182` scores
  `p_t (1 - p_t) = 0.1043`. The logistic model's 0.0999 is 4.2% below it: almost all of its skill
  against the nulls (which forecast 0.28 to 0.30) is the rate, not the ordering.
- **Discrimination.** AUC of the empirical null 0.737, of the logistic model 0.711: the null's
  signed-`d` bins order the rows at least as well as the model does. AUC was pre-registered as
  description only because the null's own AUC exceeds 0.5 through `|d|`; amendment 6 makes the
  Brier-and-AUC decomposition the rule for reading clause 2 as well.
- **Why the empirical null beats the Gaussian one.** The pooled standardised residuals have skew
  -1.49 and 5th and 95th percentiles -2.02 and +1.49: a heavy low tail. Under it a large negative
  `d` is more often an excursion that reverts, so `P(y = 1 | d < 0)` is lower (0.216 against the
  Gaussian 0.318) and `P(y = 1 | d > 0)` higher (0.411 against 0.319). The observed training rates
  are 0.162 and 0.389; the Gaussian minus empirical Brier difference on test rows is 0.0014 to
  0.0105 (interval excluding zero).
- **The test-period drop.** Observed 0.118 against the nulls' 0.28 to 0.30 at both the training
  and the test period's event timing; events per qubit per day 0.86 (train) and 0.95 (test). The
  simulation at test timing shows cadence cannot produce the drop; the nulls carry the May to
  August noise and drift statistics only.
- **The dead-feature defect.** `t - 1e-9 == t` in float64 for `t` about `1.79e9`, so
  `bisect_right(sweeps, t - 1e-9)` is `bisect_right(sweeps, t)` and returns the event's own file
  when that file is a sweep, which it usually is; the column was zero on all rows and dropped by
  the constant-column guard. `bisect_left(sweeps, t)` gives the last sweep strictly before `t`.
  The fix moved the clause-1 figure in the fourth decimal.

## Design decisions

- **Signed bins (amendment 5).** A null made sign-aware by its noise shape must be binned
  sign-aware, or the asymmetry it was introduced to carry is averaged out of its forecast; the
  first run's 0.258 against a sign-pooled null is disclosed and not the record.
- **Disclose superseded runs, never amend in place.** Each run's clause-1 figure is named in the
  amendment that superseded it (0.258, then 0.226 with the dead feature, then 0.226 record).
- **No new baseline mid-stream.** The always-level rule beat both nulls on the test period, and
  lesson L-028 asks for the strongest baseline; clause 1's pre-registered rule was kept and the
  always-level comparison reported beside it with its own interval. The oracle row is a
  diagnostic, not a baseline, because it uses test labels.
- **Decompose before reading.** A skill clause that can be earned by base-rate anticipation alone
  is read with its AUC and the oracle row; amendment 6 extends that to clause 2.
- **Self-contained script**, replicating rather than importing PR #123's helpers; `count_events.py`
  and `collect_fields.py` are loaded by path so the three scripts share one definition of events,
  levels and labels.
- **Pickle class mapping.** The collector pickles `Fields` under `__main__` when run as a script; a
  small `Unpickler.find_class` maps it back rather than re-running the walk.

## Verification

- Self-test (no git, no archive; checks the solver recovers a known sign structure, that the two
  nulls agree on Gaussian synthetic data, and that the Gaussian null over-predicts `y = 1` on a
  synthetic heavy-tailed side):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n1_baselines.py --selftest
  ```

- Reproduce the record (the walk about 20 minutes, the run about 15 s; the reproduction guard
  stops the run if the rebuilt rows differ from `rows.tsv.gz`):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/collect_fields.py --repo . --ref cf960389c672208a3952cbdf08bfd7e338ace40c --cache <dir>/fields.pkl
  ```

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/n1_baselines.py --fields <dir>/fields.pkl --ref cf960389c672208a3952cbdf08bfd7e338ace40c --out <dir>
  ```

  then compare `<dir>/results.tsv` with `docs/evidence/pattern-detector/results.tsv`.

- The dead-feature check that caught amendment 6, on any run's `features.tsv.gz`: the standard
  deviation of every frozen feature on training rows must be positive except `d_readout_missing`.

- Lint: `ruff check` and `ruff format --check` on the three scripts report nothing (CI runs
  `ruff check .`, which includes `docs/`; mypy's scope does not).

- Em dashes: a Python count of `chr(0x2014)` over the new files returns 0.

## Related docs

- `docs/evidence/pattern-detector/README.md` (sections 7, 8, 10)
- `docs/implementations/2026-10-26-pattern-detector-protocol-n0.md`
- `docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md`
- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` §4
- `docs/evidence/predictability/README.md` (PR #124's branch; the local-level model and the split)
- Issue #110 (comment 6412965244), Issue #125, PR #124 (`bf4c54e2`)
