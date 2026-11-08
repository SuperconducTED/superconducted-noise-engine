# #125 rule revision of 2026-11-08: the values the new rules owe, before any is computed

**Date**: 2026-11-08 · **Author**: Mert Efe Şensoy · **Protocol written before the runs**: this file and the two
scripts are committed before either script has produced a committed number; results are appended in section 7 with the
commit that produced them. Two scratch computations preceded this protocol (section 2). · **Owner of the question**:
Issue #125, PR #135 · **Status**: laptop runs, provisional

## 1. What this folder is for

On 2026-11-07 @bengisucvd's statistics review of PR #135 (CHANGES_REQUESTED at `51e9f425`, posted on her behalf from her
account) led the lead to four decisions, recorded in his reply on #135 (comment 6710293101):

1. A4 becomes a calibration report, not a gate, with `tau = 0` taken out; S1 is decided on A1, A2 and A3.
2. A1 and A2 are decided by batch means with `q = 4`.
3. Arm B is decided by a paired Spearman difference with the same batch means; "or band" is dropped.
4. Each morning shows operations only; scores stay sealed until day 15.

Section 3.8 of the pre-registration requires the value a predictor with no information scores on every threshold. Decisions
2 and 3 are new thresholds, and the review left two rules unstated: what an empty batch does, and how many completed jobs a
run needs. This folder measures what those choices need. It takes no decision: the lead decides from section 7, and the
amendment text on PR #135 (sections 3.11 and 3.12) carries the result.

Two more inputs belong here because the amendments cite them: the dead-qubit counts behind amendment 20 and the peeking
ceiling behind amendment 19 and decision 4.

## 2. What preceded this protocol

- **Scratch runs on 2026-11-07, not committed.** The dead-qubit counts (2,706 captures, no qubit ever absent from the target,
  qubits 17, 72 and 149 marked dead by `gate_error` 1) and a stop-at-first-pass rate for A1 under the old block-3 rule
  (33% to 42% against 9% to 18% fixed) were computed in a session scratchpad. They informed the lead's decisions, so the
  expectations below repeat them; the committed runs in section 7 are the record, and only they are cited.
- **Bengisu's review figures.** Her scripts and outputs are on `bengisu/pr135-review-evidence` at `5a7f5c58`
  (`docs/evidence/pr135-statistics-review/`). On 2026-11-07 they were re-run from that commit in a separate folder on the
  laptop: `armb_exact`, `a1_size`, `config_scan`, `arm_a_worlds`, `a1_a3_joint`, `arm_a_fit`, `a1_empirical`, `q5_old_vs_new`
  and the 137-day `arm_b_days` with `arm_b_analysis` all gave byte-identical outputs; `harness_checks` and `astcmp2` were not
  re-run. They are seeded, so this rules out an environment or tampering problem, not a logic error. Her figures are cited
  by that commit, not copied here.

## 3. Definitions: the statistics the amendments will state

**A1 and A2, Arm A, discriminating rows.** For each row `D = |p_hat - p_level| - |p_hat - p_other|`, with `other` being
`reading` for A1 and `reading_at_execution` for A2; negative favours `level`. The 14 run days fall into four fixed batches:
days 1-4, 5-8, 9-11 and 12-14 (`np.array_split` of 14 into 4). A batch's value is the mean of `D` over every discriminating
row in it (row-pooled, as amendment 8 says scores are row-weighted). With `m_1 .. m_q` the non-empty batches' values,
`t = mean(m) / (sd(m) / sqrt(q))` with `sd` at one degree of freedom less than `q`. A1 passes when `t < -t_{0.95, q - 1}`. A
batch is empty when it holds no discriminating row. `sd(m) = 0` fails.

Her `batch_pass` uses the mean of day means; with the same number of rows each day the two are equal, and they differ only
when a day loses rows (a control left out under amendment 20, or a slot missing). The null model below has equal rows per
day, so its values hold for both definitions only in that case.

**Arm B.** For each Arm B job, `Delta = rho_level - rho_reading`, the two predictors' Spearman correlations with the measured
fidelity over the six layouts; positive favours `level`. The 13 Arm B jobs (jobs 2 to 14; job 1 is Arm A only) fall into
batches of jobs 2-5, 6-8, 9-11 and 12-14 (`np.array_split` of 13 into 4), so they are not Arm A's day batches. Each batch's
value is the mean of `Delta`; `t` as above; Arm B passes when `t > t_{0.95, q - 1}`; `sd = 0` fails.

**Two empty-batch rules, both measured.**

- `V1`: any empty batch makes the condition inconclusive (it does not pass).
- `V2`: empty batches are dropped; with `q' >= 3` non-empty batches, `t` uses `q'` batches and `q' - 1` degrees of freedom;
  with `q' < 3` the condition is inconclusive.

Critical values: `t_{0.95, 2} = 2.919985580355516`, `t_{0.95, 3} = 2.353363434801823`, checked against SciPy when it is installed.

**Block 3, as the scorer computes it.** PR #140's `calendar_block_bootstrap` (at `2aea1e18`): a calendar axis of the declared
14 days with empty days kept, `ceil(14 / 3) = 5` circular blocks of 3 days, all 15 drawn days kept (not cut to 14),
row-weighted, a draw with no rows redrawn, the 90% percentile interval. Section 3.8.1's `null_values.py` cuts each draw to
14 days. The script here re-implements the scorer's construction; a test on PR #142 in the next stage checks the two agree.

## 4. Measurements and expectations

The null model is section 3.8's: per row `D = u_day + e_row`, `u_day` a stationary AR(1) over 14 days with lag-one
correlation `phi` in {0, 0.5} carrying a share `rho` in {0, 0.3, 0.7} of the variance, 56 rows a day, mean zero (no edge).

| # | What | Expectation, written before the run |
| --- | --- | --- |
| N1 | A1's no-information pass rate, batch means, full calendar | At `phi = 0` within two Monte Carlo standard errors of 0.0505 (her `a1_size.py`, `q = 4`); at `phi = 0.5` between 0.050 and 0.084, rising with `rho` |
| N2 | The same with `k` = 1 to 4 days missed, placed at random or as one consecutive run, under `V1` and `V2`; also the share of runs with an empty batch | Random placement: an empty batch in under 2% of runs for `k <= 4`. Consecutive: exactly 2/12 = 0.167 for `k = 3` (a run equal to batch 9-11 or 12-14) and 6/11 = 0.545 for `k = 4`, as counted by hand. False-pass rates move by under 0.01 from N1 under `V1`; under `V2` they may rise, because fewer batches give a wider `t` |
| N3 | A1's pass rate with a synthetic edge, calibrated at `phi = 0.5`, `rho = 0.3` to a full-calendar pass rate of 0.976 ("strong") and 0.50 ("moderate"), under the misses of N2 | Falls as `k` grows; `V2` keeps more of it than `V1` under consecutive misses. This is a synthetic shift, not one of Bengisu's worlds |
| N4 | Arm B's paired rule under null (i), independent uniform rankings, full calendar and with `k` = 1 to 3 jobs missed | Near 0.05 at full calendar (her 0.047 used real rankings); `sd = 0` in under 1% of runs; under null (ii), identical rankings, every `Delta` is 0, so `sd = 0` and it fails by definition (stated, not simulated) |
| N5 | A table for the minimum completed jobs: N2 and N3 read side by side at each `k` | No expectation: this is the table the lead decides from |
| N6 | Block 3 at 90%, the scorer's 15 days against the 14-day cut, full calendar | The 14-day cut near section 3.8.1's values (0.088 at `phi = 0`, `rho = 0`); the scorer's 15 days about 0.01 higher (her `a1_size.py` part A: 0.099 against 0.108) |
| N7 | The peeking ceiling under the new rule: stop at the first look that passes, against looking once at day 14; first possible look day 12 under `V1`, day 9 under `V2` | Both above the fixed-look rate; `V2`'s higher than `V1`'s, because it has more looks |
| N8 | From every archived capture at `calibration-data` `fafbc8f5`: captures with a qubit absent from the target's `x`, `sx` or `measure`; qubits with `x` or `sx` `gate_error` at least 1, with their spans; the `T1` date at each span's ends | 0 absences in 2,706 captures (2,707 files, one repeated stamp) over 170 UTC days; dead-marked qubits exactly 17, 72 and 149; qubit 72 on every capture; qubit 17 on 208 captures in two spans |

N8 is pinned to `calibration-data` at `fafbc8f5afbc75abb7650d3f9356bd6b21d39421` (2026-11-05 20:42 UTC), the commit the scratch
count read; `7adda803`, which Bengisu's review read, is an ancestor of it. Blobs are read by commit, so a checkout's line
endings do not touch them.

## 5. Outputs

| File | What |
| --- | --- |
| `rule_values.py` | N1 to N7. NumPy only, no archive, no project code; seeds from `SeedSequence(20261108)`, one child per measurement and case. |
| `rule-values.json` | Its output, written with LF. |
| `dead_qubits.py` | N8. Reads the archive by commit; no project code. |
| `dead-qubits.json` | Its output, written with LF. |

## 6. Run

From the repository root, with the exact pins:

    python docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/rule_values.py
        --out docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/

    python docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/dead_qubits.py
        --repo <clone with calibration-data fetched> --ref fafbc8f5afbc75abb7650d3f9356bd6b21d39421
        --out docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/

(each one command, split here for width). Set `GIT_NO_LAZY_FETCH=1` for the second in a partial clone.

## 7. Results

Appended after the runs, with the commit that produced them.

## 8. What this does not do

- No hardware result exists, and nothing here is a claim about the device except N8, which describes the archive.
- The null model has equal rows per day, so it does not separate row-pooled batch means from her mean of day means.
- N3's edge is synthetic. Power in Bengisu's scenarios N, F, S and `M(a, s)` is in her `a1_a3_joint.py` output at full
  calendar only.
- It decides nothing. The empty-batch rule and the minimum completed jobs are the lead's, from N5.
