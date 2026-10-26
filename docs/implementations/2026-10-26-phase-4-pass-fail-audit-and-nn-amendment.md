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

No source, test, plan, pre-registration or register file was touched. No new NC row. Landed as
two commits: the audit, then the correction of clause 1's null after the advisor's review.

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
measured lag-1 autocorrelation of increments (-0.49, NC-084) supports. After a disagreement of
size `|d|` the next `k` readings are the level plus fresh scatter `e_j ~ (0, sigma_q^2)`, and
`y = 1` only if their median `m` lands past the midpoint, `m > |d| / 2` in `d`'s direction. The
median of `k` draws has a standard deviation of about `1.2 sigma_q / sqrt(k)` for Gaussian
scatter, so under the null

`p_null(d) = P(y = 1 | d) ≈ 1 - Phi( |d| / (2 · 1.2 sigma_q / sqrt(k)) )`,

a steeply decreasing function of `|d|`. The null is therefore **not** a constant: `|d|` is a
feature and predicts `y` with no device pattern at all. The first draft of the rule used the
constant forecast `p_0` as the null and asserted that no feature carries information under the
null; the advisor's review caught the error and a synthetic check confirmed it (Verification).
The corrected null is the per-event conditional forecast `p_null,i = p_null(d_i)` with
`sigma_q` estimated from the qubit's own training-period increments, by Monte Carlo (or the
closed form above; the protocol records which).

**Brier scores.** With `y_i` the labels of the test events and `p_0` the training base rate:

- a model with forecasts `p_i`: `BS = mean_i (p_i - y_i)^2`;
- the conditional null: `BS_null = mean_i (p_null,i - y_i)^2`; its expected skill against itself
  is zero by construction;
- reference rows, not nulls: the constant forecast `p_0`, `BS = p_0 (1 - p_0)`; the "always
  level" rule (`p = 0` for every row), `BS = p_0`, never below the constant's;
- Brier skill score against the conditional null, `BSS_1 = 1 - BS / BS_null`.

Under the null `y = 1` is rare (a few percent of events at the archive's scatter), so the test
period's count of `y = 1` events bounds what the bootstrap can resolve; step N0 counts it and
states the minimum first.

**Clause 1 (a pattern exists).** `BSS_1(logistic) >= 0.10` on the test events, with the paired
90% block bootstrap interval of `BS_null - BS_logistic` excluding zero. AUC is reported as
description only, because the conditional null's own AUC exceeds 0.5 through `|d|`.

**Clause 2 (the network is needed).** `BSS_1(network) - BSS_1(logistic) >= 0.05` for the seed
median, the paired 90% block bootstrap interval of the difference excluding zero.

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
- **A per-event conditional null, not a constant.** The label's own arithmetic makes `|d|`
  predictive under pure noise around a level, so a constant null is clearable with no pattern
  (lesson L-029). The null forecast is computed per event from the qubit's own scatter; the
  constant and the "always level" rule are kept as reference rows. Corrected before anyone
  outside the session saw the rule, in a second commit rather than an amend, so the record
  shows the first draft was wrong and how.
- **The level excludes the event's own state.** The pre-registration's window is inclusive at
  `t_s`, right for a predictor; for a label about whether the reading moved the level, the
  reading under test must not enter its own reference.
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

- **Mutation check of clause 1's null** (synthetic, no archive data; its figures are not
  register claims). Run with any interpreter that has NumPy (the exact-pin venv was used):

  ```python
  import numpy as np
  rng = np.random.default_rng(84); k = 5
  for sigma in (0.20, 0.29):
      rows = []
      for d in (0.4, 0.6, 0.8, 1.0, 1.5):
          m = np.median(rng.normal(0.0, sigma, size=(200_000, k)), axis=1)
          rows.append((d, float(np.mean(np.abs(m - d) < np.abs(m)))))
      print(sigma, rows)
      y, pc = [], []
      for d, p in rows:
          m = np.median(rng.normal(0.0, sigma, size=(40_000, k)), axis=1)
          y.append((np.abs(m - d) < np.abs(m)).astype(float)); pc.append(np.full(40_000, p))
      y, pc = np.concatenate(y), np.concatenate(pc); p0 = y.mean()
      print("BSS of a |d|-only model vs the constant:", 1 - np.mean((pc - y) ** 2) / np.mean((p0 - y) ** 2))
  ```

  Expected shape of the output: `P(y = 1 | d)` falls by roughly an order of magnitude from
  `|d| = 0.4` to `|d| = 0.8` at both scatters (the run on 2026-10-26 gave about 0.03 to 0.0001
  at `sigma = 0.20` and 0.10 to 0.005 at `sigma = 0.29`), the base rate is a few percent, and the
  `|d|`-only model's skill against the constant is positive (about 0.02 and 0.05). A null that
  passed this check unchanged would be the constant; it does not, so the rule uses the
  conditional null. Two `sigma` values are used because the registered 0.37 log units (NC-084) is
  an 80% scatter of increments, and converting it to a per-reading standard deviation depends on
  whether the level is treated as known; the protocol's step N0 estimates `sigma_q` per qubit
  from the data and the check only needs the shape to hold at both.

- No em dash in the two new files (checked in Python, because Git Bash leaves the bash escape
  for U+2014 as six literal characters and a `grep` with it tests nothing):

  ```bash
  python -c "import pathlib,sys; print(sum(pathlib.Path(f).read_text(encoding='utf-8').count(chr(0x2014)) for f in sys.argv[1:]))" docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md
  ```

  expected `0`.

- CI runs no documentation check (`.github/workflows/ci.yml` has no markdown or link step), so
  there is nothing further to run.

## As of 2026-10-26, later: the lead's decision and what it changed

The lead adopted tasks N0 to N6 on #110 and amended the plan's §4 ("no deep-model training before
gate L1; the protocol commit may be written now"). Recorded in the audit's §4.7 with the drafted
#110 post. The §4 amendment is a dated subsection appended to
`docs/roadmap/2026-10-23-phase-4-plan.md` on PR #124's branch (`mert/predictability`), prepared as
a commit on the local branch `claude/phase-4-plan-s4-amendment` cut from `951258da` in the
throwaway worktree `C:/t124p`, **not pushed**: the branch is under review and a push changes
what its reviewers see, so it waits for the lead's word. The #110 post is likewise drafted and
not posted. A session drafting the advisor brief for Dr. Akba's ratification was started on the
lead's word the same day.

**Later on 2026-10-26, on the lead's explicit word:** `bf4c54e2` was pushed as a fast-forward
onto `mert/predictability` (PR #124's head is now `bf4c54e2`), and the #110 post went out as
comment 6412965244. The throwaway worktree `C:/t124p` and its local branch were removed after
the push.

## Related docs

- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` (this change's deliverable)
- `docs/roadmap/2026-10-23-phase-4-plan.md` (PR #124's branch)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` (`mert/issue-125-preregistration`)
- `docs/evidence/predictability/README.md` (PR #124's branch)
- `docs/findings/2026-10-23-strategy-audit.md` (PR #124's branch)
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (PR #111's branch)
- `docs/advisor/2026-09-03-decisions-from-akba.md`
- Issues #125, #110; PRs #120, #121, #123, #124, #126, #127
