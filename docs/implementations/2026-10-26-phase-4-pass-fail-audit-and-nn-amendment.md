# 2026-10-26: phase-4 pass/fail audit and the neural-network amendment

## Problem / Motivation

The phase-4 plan (`docs/roadmap/2026-10-23-phase-4-plan.md`, on PR #124's branch) was written
on 2026-10-23 and has had no pass/fail reading since; its first "one thing per person" week ends
on 2026-10-30 and lane 3's closing week ends with the phase-3 milestone on 2026-10-31. The lead
asked for an amended pass/fail audit of the plan on 2026-10-26, and reported that Dr. Fırat Akba
had suggested designing a neural network to detect patterns that would help the Q1 paper. The
plan's §4 forbids new deep-model work until #125 reports, on the strength of NC-084 to NC-086, so
the suggestion needed to be reconciled with the plan rather than bolted on: either the evidence
leaves a target open for a network or it does not, and the audit had to say which.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` | New: every plan item (lanes 1 to 3, parked table, §4 stop rules, §5 and §5.1 assignments, §7 risks, gates L1 to L5, the pre-registration's freeze preconditions) judged against GitHub and branch state read on 2026-10-26, with a fixed verdict vocabulary; section 4 adds the neural-network pattern detector as a pre-registrable proposal with a two-clause pass/fail rule and an outcome table. |
| `docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md` | This record. |

No source, test, plan, pre-registration or register file was touched. No new NC row.

## Implementation approach

**Audit.** The baseline is pinned first (`main` `a0ea1161`; the plan's branches `951258da` and
`821f6781`; `calibration-data` `cf960389`; the dashboard record of 2026-10-26; the `gh` read at
09:27 UTC), so every verdict is a dated statement. Each row carries the plan's own "what done
looks like" text as the criterion and the evidence checked as a separate column; the verdict
vocabulary (PASS, FAIL, IN PROGRESS, NOT STARTED, BLOCKED on X, AT RISK by date) is defined once
and nothing else is used. The audit measures nothing new and cites register rows only in Rule 7
form.

**Amendment.** The network is scoped by subtraction: the records on PR #124's branch
(predictability README §3.4 to §3.6a, strategy audit S5 and S6) name what the 2026-10-23
measurements closed (own-history forecasting of per-qubit T1, T2 and readout) and what they left
open. Of the open targets, the one nearest the engineer's design-time decision is chosen as
primary: when the latest reading departs from the qubit's 30-day level, do the next readings
follow the reading (a shift) or return to the level (a transient), and do calibration patterns
at that moment say which. The network is a NumPy multilayer perceptron (decision A4) scored
against a null, the design's implicit "always level" rule and a logistic regression on the same
inputs, on a time split, with block-bootstrap intervals, under a rule written before any row is
counted. It is filed as gated tasks on #110, the ticket the plan already reframed, not as a new
lane; its success rule is routed to Dr. Akba because the 2026-10-13 delegation keeps the
deep-learning model with him.

## Mathematical / Statistical details

**Label.** For a disagreement event `(q, t)` with `d(t) = log T1_reading(t) - log T1_level(t)`
and `|d(t)| >= delta`, let `m` be the median of the next `k` re-measured values of `log T1_q`.
Then `y = 1` if `|m - log T1_reading(t)| < |m - log T1_level(t)|` (the reading became the level),
else `y = 0`. Events, not files, are the unit, so the repeated no-change files of the archive
cannot inflate either class (lesson L-027 in the skill's `LESSONS.md`).

**Null model.** Each reading is the level plus independent scatter with no memory, the model the
measured lag-1 autocorrelation of increments (-0.49, NC-084) supports. Then the next `k` readings
are the level plus fresh scatter and no feature observable at `t` carries information about `y`.
Under that null the expected out-of-sample Brier skill score of any model against the constant
forecast is zero (slightly negative in a finite sample, from estimation noise) and the expected
AUC is 0.5. These are the values every threshold is set as a gap above.

**Brier scores.** With base rate `p_0 = P(y = 1)` on the training events:

- constant forecast `p_0`: `BS_null = p_0 (1 - p_0)`;
- the "always level" rule (`p = 0` for every row): `BS = p_0`, which is never below `BS_null`,
  so the constant forecast is the stricter null and is the one used;
- a model with forecasts `p_i`: `BS = mean_i (p_i - y_i)^2`;
- Brier skill score `BSS = 1 - BS / BS_null`, zero for no skill, one for perfect.

**Clause 1 (a pattern exists).** `BSS_logistic >= 0.10` on the test events, the paired 90% block
bootstrap interval of `BS_null - BS_logistic` excluding zero, and the 90% interval of the
logistic AUC excluding 0.5.

**Clause 2 (the network is needed).** `BSS_network - BSS_logistic >= 0.05` for the seed median,
the paired 90% block bootstrap interval of the difference excluding zero.

**Bootstrap.** Blocks are calendar days, because the 156 qubits of one `t` share the device
state and row resampling understates the uncertainty (the same argument as the predictability
README §2.1 item 5); 1,000 resamples from a `SeedSequence`, 90% intervals, paired across models
by resampling the same days for both.

**Network.** Inputs `d`, one hidden layer of `h` `tanh` units, sigmoid output; parameter count
`d h + h + h + 1 = (d + 2) h + 1`. Trained on the log loss by gradient descent; early stopping and
the choice of `h` on the last 20% of the training period in time order; five seeds; the test
period is touched once, at scoring.

**Split.** `2026-09-01T00:00:00Z`, snapshot boundary, as NC-080 to NC-086; no event straddles it.

**Thresholds' provenance.** 0.10 is the same 10% margin the predictability rule used above its
null; 0.05 is half of it, chosen so that the network must show a gap of the same order the
pattern itself must show. Both are proposals for Bengisu's statistics review and Dr. Akba's
ratification; any change is recorded in the protocol README before the run, dated.

## Design decisions

- **An audit, not an amendment to an existing audit.** `docs/audits/` had no phase-4 audit;
  "amend" is read as "amended with the new item". Stated in the audit's §0.
- **One primary target, not a menu.** Four open targets were found; the one nearest the
  engineer's decision is primary and the others are deferred with a one-line reason each, so the
  lead decides one thing.
- **Logistic regression as the bar, not the null.** Lesson L-028: the pre-registered baseline
  must be the strongest cheap model the protocol produces. A network that only beats a constant
  forecast has not shown it is needed.
- **Hardware rows as a check, never a training set.** #125 yields eight discriminating rows a
  job; a sign-agreement count is all they can support.
- **Gated tasks on #110, not a fourth lane.** The plan's §3 reframed #110 and parked it with its
  reason; the amendment re-opens that park for a decision rather than contradicting the plan's
  structure. Follows the standing rule that "plan ahead" means gated tasks in the doc and the
  issue, not runs.
- **The §4 stop rule is the lead's to change.** The audit recommends allowing the protocol commit
  now and no training before L1, and records the alternative (everything at L1).
- **Dr. Akba's ratification through the advisor channel.** The deep-learning model is his by the
  2026-10-13 delegation; the brief is triaged and self-contained in the project's form and is a
  follow-up, not part of this change.
- **No em dashes** in either file (checked with a grep before the commit).

## Verification

- The audit's baseline SHAs resolve and match the branches named:

  ```bash
  git rev-parse --short origin/main origin/mert/predictability origin/mert/issue-125-preregistration origin/calibration-data
  ```

  expected `a0ea1161`, `951258da`, `821f6781`, `cf960389` (the `calibration-data` tip moves
  hourly; a later value means the poller ran since).

- The live-state claims re-check in one call (all six PRs open with zero reviews at the audit's
  time; later output that differs means the team moved):

  ```bash
  for n in 120 121 123 124 126 127; do gh pr view $n --json number,state,reviews --jq '"\(.number) \(.state) reviews=\(.reviews|length)"'; done
  ```

- The Brier identities in the mathematical section are checked by hand: for the constant
  forecast `p_0`, `p_0 (1 - p_0)^2 + (1 - p_0) p_0^2 = p_0 (1 - p_0)`; for the zero forecast,
  `p_0 * 1 + (1 - p_0) * 0 = p_0`; and `p_0 >= p_0 (1 - p_0)` for all `p_0` in `[0, 1]`.

- No em dash in the two new files:

  ```bash
  grep -c $'—' docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md
  ```

  expected `0` for both.

- CI runs no documentation check (`.github/workflows/ci.yml` has no markdown or link step), so
  there is nothing further to run.

## Related docs

- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` (this change's deliverable)
- `docs/roadmap/2026-10-23-phase-4-plan.md` (PR #124's branch)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` (`mert/issue-125-preregistration`)
- `docs/evidence/predictability/README.md` (PR #124's branch)
- `docs/findings/2026-10-23-strategy-audit.md` (PR #124's branch)
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (PR #111's branch)
- `docs/advisor/2026-09-03-decisions-from-akba.md`
- Issues #125, #110; PRs #120, #121, #123, #124, #126, #127
