# Hardware test: does the calibration *level* predict the device better than the latest *reading*?

**Date**: 2026-10-23 · **Author**: Mert Efe Şensoy · **Owner of the run**: @BurakOztekin (harness,
circuits, desktop verification) · **Status**: design for approval, pre-registration to be
completed and committed before the first QPU job · **Decides**: strategy S1 of
`docs/findings/2026-10-23-strategy-audit.md`, and the engine's value for the design-time goal
stated there in §3.1

## 1. The question, and why it cannot be answered from the archive

Each per-qubit calibration reading on `ibm_fez` is a slowly moving level plus independent
scatter of about 0.37 log units at 80% (`docs/evidence/predictability/`, NC-084, NC-085). The
archive cannot say whether that scatter is the calibration measurement's own noise, in which
case the **level** is what the device actually does and a noise model should carry the level,
or genuine fast fluctuation, in which case the device at run time is somewhere in the
**range** and the level is only its centre. The two readings imply different products, and
only the hardware can tell them apart. `NoiseModel.from_backend`, every calibration-based twin
in the literature and this engine all carry the latest reading; on the compilation side,
Kurniawan et al. (arXiv 2407.21462) found historical calibration more robust than the latest
for layout choice on IBM Perth and Brisbane, but nobody has tested the prediction itself.

Two arms, one run:

- **Arm A, decay.** The quantity the reading and the level disagree about most directly:
  the excited-state survival after a delay, on single qubits.
- **Arm B, layout.** The decision an engineer makes: for one small circuit, which of several
  candidate layouts measures best, and did the predictor rank them right.

## 2. Predictors under test (all computed at submission time, nothing after)

For qubit `q` at submission time `t_s`, with `T1_q` the value in question:

| Predictor | `T1_q` used | What it stands for |
| --- | --- | --- |
| `reading` | the latest calibration reading at `t_s` | `NoiseModel.from_backend`, the digital twins, this engine today |
| `level` | the geometric mean of the qubit's readings over the trailing 30 days of distinct states | the level-tracking channel (S1) |
| `shrink` | `exp(level + (1 - kappa) (log reading - level))` with `kappa = 0.75` (NC-085's fitted value for gamma, pre-fixed) | the archive's best point forecast |
| `band` | the per-qubit 10th to 90th percentile of log readings over the same 30 days | the range (NC-081's per-qubit form) |

Readout error enters every prediction the same way, from the same source as `T1_q` in each
row (reading with reading, level with level), so the arms test the choice consistently.

## 3. Arm A: decay circuits

- **Circuit.** `X` on qubit `q`, `delay(tau)`, measure. One circuit per delay, all selected
  qubits in parallel in the same circuit (disjoint qubits, no entanglement).
- **Delays.** `tau` in `{0, 0.5, 1.0, 2.0} x T1_level,q`, per qubit, so every qubit is probed
  where the decay is most sensitive to `T1` (`d p / d log T1` is largest near `tau = T1`),
  plus `tau = 0` as the readout-only control. Rounded to the backend's `dt` granularity.
- **Prediction.** `p_1(tau) = (1 - e_10) s + e_01 (1 - s)` with `s = exp(-tau / T1_q)`,
  `e_10 = prob_meas0_prep1`, `e_01 = prob_meas1_prep0`, each from the predictor's source.
  The `band` gives `[p_1(T1_hi), p_1(T1_lo)]`.
- **Qubits.** Twelve per job: eight chosen at `t_s` as the usable qubits with the largest
  `|log reading - level|` among those with at least 20 re-measurement events in the archive
  (the test has power only where the two predictors disagree), and four fixed controls chosen
  once, before the first job, as the median-scatter qubits of the archive. The selection rule
  is pre-registered; the selected indices are logged per job.
- **Shots.** 2,048 per circuit: binomial standard error about 0.011 at `p = 0.5`, below the
  predicted reading-versus-level gap for the selected qubits (a 0.37 log-unit `T1` gap at
  `tau = T1` moves `p_1` by about 0.09).
- **Scoring, per (job, qubit, delay).** Absolute error `|p_hat - p_pred|` for each point
  predictor; log score under the binomial; band coverage of `p_hat` after widening the band by
  one binomial standard error on each side (so shot noise cannot fail a correct band);
  band width. Aggregated per predictor over all rows, and separately over rows where
  `|log reading - level| > 0.2` (the rows that discriminate).

## 4. Arm B: layouts

- **Circuit.** A three-qubit GHZ (`benchmarks/circuits.py::ghz_state_circuit(3)`) followed by
  an idle block (`delay` of `0.5 x` the median `T1_level` of the layout on all three qubits) and
  measurement in the computational basis. The idle block is what makes the layout's `T1`
  matter at all; without it the GHZ is readout- and CZ-dominated (File 03 Q3, R4).
- **Layouts.** Six connected triples per job, chosen at `t_s` to span the predicted fidelity
  under `level` from best to worst among triples whose qubits all have at least 20 events;
  the rule and the chosen triples are logged.
- **Prediction.** Each predictor gives a noise model (per-qubit amplitude and phase damping
  from its `T1`, `T2` source through the engine's ADR-027 channel; readout from the same
  source; the backend's own `cz` error for the two-qubit gates, identical across predictors
  since it is not under test) and a predicted outcome distribution from Aer in density-matrix
  mode; the figure of merit is the Hellinger fidelity to the ideal GHZ distribution.
- **Shots.** 4,096 per layout.
- **Scoring.** Spearman rank correlation between predicted and measured fidelity over the six
  layouts, per predictor, per job; the fraction of jobs in which the predictor's top-ranked
  layout is the measured best; mean absolute fidelity error.

## 5. Schedule, budget and accounts

- **Cadence.** One job per day for 14 consecutive days, submitted at a fixed UTC hour, so
  that about half of the per-qubit readings change between consecutive jobs (median
  re-measurement gap 24.7 h, File 03 M2) and the reading-versus-level disagreement is
  refreshed daily.
- **Queue delay.** Logged per job (`t_execute - t_s`). Predictions are frozen at `t_s`; the
  properties at `t_execute` are also archived so the analysis can report how much of any
  reading-versus-level difference is staleness and how much is scatter.
- **Budget, estimated, to be confirmed on the first job's usage report.** Arm A: 4 circuits
  times 2,048 shots at roughly 0.5 ms per shot including reset, about 4 s of QPU time. Arm B:
  6 circuits times 4,096 shots at roughly 0.3 ms, about 7 s. About 11 s per job, about 2.6 min
  for 14 jobs. The Open Plan gives 10 minutes of QPU execution time per rolling window (IBM's
  product page says per month; secondary sources say a 28-day window; the reset rule is
  **unverified** and must be read from the platform's usage page before the schedule is
  fixed). One account covers the run with margin; a second account is the fallback, run under
  its own token and named in the log.
- **Dry run first.** The whole pipeline (selection rule, circuit construction, prediction,
  scoring) runs against Aer with a `from_backend` model built from an archived snapshot before
  any QPU job, and its output is committed as the pipeline's zero-cost acceptance test.

## 6. The measurement-noise question, settled in the same run

On the eight selected qubits of the first and last jobs, a Qiskit Experiments `T1`
characterization (eight delays, 1,024 shots) gives a fitted `T1` with a per-fit standard
error. If the per-fit standard error is a few percent while consecutive IBM readings differ
by 0.37 log units, the scatter is not fit noise and the `band` is the honest product; if the
two are of the same size, the readings are noisy measurements of a stable level and the
`level` predictor should win Arm A outright. Budget: about 8 s per characterization, twice.

## 7. Decision rule, to be fixed before the first job

Written here as the proposal; the numbers are frozen when the pre-registration is committed.

- **S1 passes** if, over all Arm A rows, `level` has lower mean absolute error than `reading`
  with a paired bootstrap 90% interval excluding zero, **and** `band` covers at least 70% of
  rows after the shot-noise widening at a mean width no larger than `reading`'s error
  distribution would imply. **S1 passes for the engineer's purpose** if, in Arm B, `level` or
  `band` ranks layouts at least as well as `reading` on Spearman correlation and picks the
  measured-best layout at least as often.
- **S1 fails** if `reading` is at least as good as `level` on Arm A's discriminating rows.
  The range then survives as the product, and the paper is the fuzzy-systems one with this
  run as its hardware section.
- Either way the run produces the first hardware numbers for outcome-space resolution
  (gates record §4) and the first design-time comparison against `from_backend`.

## 8. What is needed before this can start

| Item | Owner | Blocking |
| --- | --- | --- |
| Approval of this design and of spending QPU time | Mert | yes |
| Usage-page check of the Open Plan allowance and reset rule | Burak | yes |
| `scripts/hardware_reading_vs_level.py`: selection, circuits, predictions, submission, archiving of properties at `t_s` and `t_execute`, scoring | Burak (circuits, harness), Mert (prediction from the archive) | yes |
| Dry run against Aer, committed | Burak | yes |
| Pre-registration commit with frozen thresholds and the four control qubits | Mert | yes, before job 1 |
| Readout-error predictability result (S5), to confirm the readout source in §2 | Mert | no; informs §2 if readout is forecastable |
| ADR-029 adoption for the 30-day level before 2026-05-13 | Baha | no; the level uses our own archive for this run |

## 9. What this test does not do

It does not train anything, use the fuzzy layer, or touch the LOCKED modules. It does not
decide the venue. It does not measure anything on a second backend. It produces, per
predictor, a small table of hardware numbers on citable rows, which is the one thing the
project has never had.

## 10. Related

`docs/findings/2026-10-23-strategy-audit.md` S1, S2, §3.1; `docs/evidence/predictability/`;
`docs/evidence/persistence-band/`; `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`
§4; NC-081, NC-083, NC-084, NC-085; arXiv 2407.21462; IBM Open Plan product page (allowance
"up to 10 minutes of runtime per month").
