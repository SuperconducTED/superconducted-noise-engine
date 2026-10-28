# 2026-10-28: the #125 pre-registration rebuilt onto `main` (step 1c)

**Status**: plan written first (`73dd87ae`); steps 2 to 9 done on 2026-10-28, step 10 (the PR) waits on the lead.
The "Plan" section is as committed before any step; the sections after it record what happened.

## Problem / Motivation

The #125 pre-registration (`docs/roadmap/2026-10-24-issue-125-preregistration.md`) was drafted on
2026-10-24 on a branch that merged PR #121's, #124's and #126's branches locally. All three have
since merged into `main`, along with #127 and #128, so the branch is 93 commits behind `main` and
its register rows NC-087 to NC-091 still say "measured outside the merge graph, re-pinned when this
branch is rebuilt onto `main`". The offline half (step 1b, branch `mert/issue-125-offline-half`)
found twelve places where the draft is silent or now wrong; its record lists them as amendments
owed here. Bengisu's review of PR #128 left two statistics lessons the draft should apply before
she reviews it. Plan §8 (PR #131) names this step 1c: rebuild, re-pin, re-run the controls, write
the amendments, open the PR for her statistics review. Nothing goes to the QPU until the freezing
commit, which is step 1d and is not part of this change.

## Plan

The lead chose on 2026-10-28 (this session) to **stack this branch on PR #132** (the selection
rules, head `4746be56`, not yet reviewed), as step 1b is stacked, so that `--mode controls` exists
on the branch and the controls can be run now. Bengisu's review will therefore show #132's diff
until #132 merges. He also chose to put Bengisu's first lesson (labels whose horizon crosses a
boundary) to her as an open question in the PR rather than decide it here.

Steps, in order, each its own commit:

1. **This plan**, first commit.
2. **Merge `origin/main`** (`695c90ca`) into the branch with a merge commit, never a rebase, so the
   commits NC-087 to NC-091 cite (`d6ed7885`, `d75de42d`, `b6852203`, `dfaf0cd7` and the NC-091
   run) stay reachable and become ancestors of `main` when this PR merges. A trial `git merge-tree`
   shows two conflicts:
   - `docs/numerical-claims.md`: keep both sides; NC-087 to NC-091 sit between NC-086 and NC-092.
   - `docs/roadmap/2026-10-23-phase-4-plan.md` (add/add): `main`'s version wins. Checked before
     this plan: the branch has zero lines that `main` lacks in this file.
   Sanity check after the merge: `git diff --stat origin/main` shows only additions (the evidence
   folder, the two roadmap docs, the support record, the grid-bias script and its test, the five
   register rows). Any deletion means the merge dropped content and stops the work.
3. **Merge PR #132's tip** (`4746be56`) with a merge commit. The branch keeps its own upstream
   (`origin/mert/issue-125-preregistration`), never #132's.
4. **The amendments**, in the pre-registration, append-only:
   - New rows at the foot of section 2's table, each dated, for the twelve items the offline-half
     record owes (listed below), and a row that replaces the `d62928fa` source pin with "#132's
     merge commit, named at the freezing commit". Existing rows are not edited.
   - A new section 3.7 with each amendment's text and reason.
   - Section 6 gets a dated "as of 2026-10-28" table below the 2026-10-24 one (the old rows stay).
   - The twelve: (1) Arm B eligibility, window floor 15, controls allowed in triples; (2) Arm B
     readout, exact density-matrix probabilities then each predictor's own assignment matrices
     applied analytically; (3) the `cz` channel, depolarizing from the latest `gate_error`, no
     relaxation, identical across predictors; (4) the band in Arm B, interval from its two ends,
     ranked by midpoint, scored for coverage; (5) the triple rule, ranks `round(i (n - 1) / 5)`
     under `level`; (6) Arm A scheduled ALAP against one simultaneous measurement; (7) design §6's
     `T1` characterisation, `rep_delay` and `init_qubits` move to step 1d; (8) the bootstrap's
     resampling unit, proposed below, frozen after Bengisu's review; (9) dead `cz` pairs
     (`gate_error = 1`) are not links; (10) a dry run meant to exercise `reading_at_execution`
     needs a `t_execute` after a sweep; (11) Arm B's best-pick near-tie, for her review of how Arm B
     is scored; (12) every JSON either script writes uses LF (done on #132 as `bbde9522`; recorded
     here).
5. **Bengisu's lessons.** Second lesson (resampling in blocks of consecutive calendar days, with
   empty dates kept at zero rows): proposed as amendment 8's unit, a day being the job's
   submission date in UTC, so a missed job is an empty block, not a dropped one. First lesson
   (purge labels whose horizon crosses a boundary): stated in section 3.7 as an open question for
   her, with what this test has in its place (nothing is fitted; the level's 30-day window must be
   complete at every `t_s`; `reading_at_execution` is read after the fact).
6. **The null-model value of every threshold** (plan §8's done line for 1c, lesson L-029). A new
   section in the pre-registration, written before any computation, naming each threshold in the
   decision rule and how its value under a no-information predictor is obtained: the paired
   bootstrap interval excluding zero (about 5% one-sided per comparison when the two predictors are
   equally good, before the multiple comparisons the rule chains); the control stratum's sign
   condition (about one half); the band's coverage within one binomial standard error; and Arm B's
   "at least as well" and "at least as often", which pass on ties, so their null value is above
   one half. Where a value is not closed-form it comes from a small committed script under its own
   protocol paragraph, run after that paragraph is committed.
7. **The controls run**: `python scripts/hardware_test_predictors.py --mode controls` at the current
   `calibration-data` tip, recorded as a **rehearsal at that ref, not the frozen controls**. The
   frozen four come from the same command at the freezing commit's ref (step 1d); this run shows the
   command works on the stacked tree and names what it would choose today. Output written with LF,
   blob hash recorded.
8. **The re-pin of NC-087 to NC-091**: re-run the three committed scripts (`hardware_test_grid_bias.py`,
   `measure_checkup_floor.py`, `measure_recal_hours.py`) on the merged tree at the rows' own inputs
   (`calibration-data` `5828b4a2`, already local), and compare every output by blob hash with the
   committed one. Identical: a dated note on each row naming the merged-tree commit it reproduced
   at and saying the cited commits are now in the merge graph. Different: stop and report; nothing
   is re-registered without the lead's word. Two archive walks, about 10 minutes each.
9. **Gates** with `C:/t/pin125/Scripts/python.exe`, `PYTHONPATH=src`: ruff, mypy (including
   `scripts/`), the full suite. This PR adds `tests/test_hardware_test_grid_bias.py`, so NC-021 is
   re-measured at its merge commit, in a docs-only commit after the merge.
10. **PR body drafted**, Turkish with a collapsed English summary, reviewer @bengisucvd, #125's
    labels, the Phase 4 milestone, no closing keywords; push and PR only on the lead's word.

## What changed

Commits on `mert/issue-125-preregistration` after `821f6781`, 2026-10-28:

| Commit | What |
| --- | --- |
| `73dd87ae` | this plan |
| `c6550787` | merge of `main` `695c90ca`; register keeps both sides, the phase-4 plan takes `main`'s version |
| `f352889a` | merge of PR #132's tip `4746be56` (stacked) |
| `7217966a` | the pre-registration's amendments and the null-value protocol, before its script |
| `aa5dca1f` | the null-value script, before its run |
| `2b7c98f7` | the null-value output, one run |
| `fc904655` | the pre-registration's section 3.8.1, the values |
| `5e8b4354` | the controls rehearsal (pre-registration 3.9), the NC-087 to NC-091 notes |
| later | this record, and the review-point fixes (band-independence caveat in 3.8.1, TSV note in amendment 12) |

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-24-issue-125-preregistration.md` | Gains twelve dated rows at the foot of section 2, sections 3.7 (the amendments and the open label-horizon question), 3.8 (the null-value protocol), 3.8.1 (the values) and 6.1 (state as of 2026-10-28); no earlier row is edited. |
| `docs/evidence/hardware-reading-vs-level/null_values.py` | New: what a no-information predictor scores on each decision-rule threshold, Arm B exactly and A1 by simulation. |
| `docs/evidence/hardware-reading-vs-level/null-values.json` | New: that script's one run. |
| `docs/evidence/hardware-reading-vs-level/controls-rehearsal-2026-10-28/` | New: `--mode controls` at the current archive tip, a rehearsal, not the frozen controls. |
| `docs/numerical-claims.md` | NC-087 to NC-091 enter `main`'s register order (after NC-086, before NC-092) and each gains a dated reproduction note; no value changes. |
| `docs/implementations/2026-10-28-issue-125-preregistration-rebuild.md` | This record. |

## Implementation approach

**Rebuild by merge.** `main` and then #132's tip were merged in with merge commits. Before the
first merge a `git merge-tree` trial named the two conflicts; after it `git diff --stat origin/main`
showed 20 files, 3,191 insertions and no deletion, so nothing on `main` was dropped. After #132's
merge the only deletions are #132's own edits (15 lines in `scripts/hardware_test_predictors.py`
and the archive-side plan).

**Amendments, append-only.** The draft's own rule (section 3.5: changes are dated notes beside the
old ones) and the repository's rule for dated documents both forbid editing the 2026-10-24 rows.
Each value an amendment fixes became a new row at the foot of section 2 with its amendment number
and date; the reasons are in section 3.7, numbered as the offline-half record numbers them, plus
amendment 13 (the predictor-code pin). Section 6's 2026-10-24 table stays; section 6.1 below it
gives the 2026-10-28 state.

**Null values, protocol first.** Section 3.8 (committed `7217966a`) named every threshold, its null
model and how its value would be obtained before the script existed; the script (`aa5dca1f`) was
committed before it ran; it ran once (`2b7c98f7`); section 3.8.1 reports all of it.

**Re-pin by reproduction, not by re-registration.** The rows cite commits on this branch, which the
merge keeps reachable; at this PR's merge they become ancestors of `main`. The three committed
scripts were re-run on the merged tree at the rows' own inputs and every output compared by blob
hash. All five rows reproduce: every output has its committed blob hash except
`checkup-floor-summary.json`, which differs only in `collect_seconds` and `total_seconds`
(wall-clock). Each row got a dated note; no value changed. The first floor re-run crashed writing
`checkup-floor-controls.json` into the session scratchpad: the path was 261 characters, past
Windows' 260 limit (the two shorter outputs written before it matched). It was re-run into
`C:/t/r1c/floor` and completed. A path-length crash, not a code change, and disclosed here.

**Controls rehearsal.** `--mode controls` at `calibration-data` `7adda803` with
`--at 2026-10-28T18:40:46Z` (the latest `ibm_fez` file) names 144, 110, 140 and 77; NC-088's
instant on `5828b4a2` named 48, 112, 54 and 105. Recorded as a rehearsal in the pre-registration's
section 3.9, output committed. 213 blobs of the new archive tip were missing from this partial
clone and were fetched in one batch before the run. `predictors.tsv` is written by the script with
CRLF on Windows (amendment 12 covers JSON only); it was stored with LF, and no hash of it is
recorded anywhere.

## Mathematical / Statistical details

**Arm B, exact.** Six layouts; the measured order fixed as `0..5`. A ranking `p` (a permutation)
has `sum d^2 = sum_i (p_i - i)^2`, always even, from 0 to 70, and Spearman's
`rho_S = 1 - 6 sum d^2 / (6 (36 - 1)) = 1 - sum d^2 / 35`; its top pick is right when `p_0 = 0`.
Enumerating the 720 permutations gives the one-job joint pmf of `(sum d^2 / 2, hit)`; a 2-D
convolution over the 13 Arm B jobs gives the pmf `P(S, H)` of the totals. "At least as well on mean
Spearman" is `S_pred <= S_reading`; "at least as often" is `H_pred >= H_reading`. With the three
predictors independent and identically distributed under null (i), conditioning on `reading`'s
outcome `(s, h)`: `q1 = P(S <= s)`, `q2 = P(H >= h)`, `qj = P(S <= s, H >= h)`; `level` alone passes
with `E[q1]`, `E[q2]`, `E[qj]`; "`level` or `band`" with `E[1 - (1 - q)^2]`; "each condition by
either" with `E[1 - (1 - q1)^2 - (1 - q2)^2 + (1 - q1 - q2 + qj)^2]`. A 200,000-draw Monte Carlo
agreed with every exact figure (largest `|z|` 1.40).

**A1, simulated.** Per-row difference in absolute error `D = u_t + e`, `t` the day, mean zero
(no edge either way). `u_t` stationary AR(1): `u_0 ~ N(0, rho)`,
`u_t = phi u_{t-1} + sqrt(rho (1 - phi^2)) z_t`; `e ~ N(0, 1 - rho)` per row, 56 rows a day, so the
day mean is `u_t + N(0, (1 - rho) / 56)`. With equal rows per day the row-weighted mean is the mean
of the 14 day means. Circular block bootstrap: `ceil(14 / L)` blocks of `L` consecutive days, start
days uniform, wrapped, truncated to 14; 2,000 resamples; the 90% percentile interval is the 5th to
95th percentile of the resampled means; a run "passes" when the 95th lies below zero. Rate over
2,000 runs per case, standard error `sqrt(r (1 - r) / 2000)`. Seeds: `SeedSequence(1251028)`
spawned, one child per `(phi, rho)` case and one for the Arm B check; both block lengths read the
same simulated runs, so they are compared on paired data.

**Why the percentile interval is too narrow here.** With `n` independent blocks the bootstrap
variance of a mean is the plug-in `(n - 1) / n` of the sample variance, and the percentile
interval uses normal-like quantiles where a `t` with `n - 1` degrees of freedom would be right;
both shrink the interval when `n` is 14 or, at block 3, about 5. Correlated days add the usual
effect of a block shorter than the dependence. The simulation measures the sum; it does not
separate them.

## Design decisions

- **Merge, not rebase.** The register cites commits on this branch; a rebase would orphan them and
  turn five rows' sources into dead SHAs. A merge keeps them and puts them on `main` at this PR's
  merge.
- **Stacked on #132** (the lead, 2026-10-28): the controls command exists only there. Cost:
  Bengisu's review shows #132's diff until it merges, and a change on #132 is merged in again here.
- **Controls as a rehearsal.** Proposal D freezes the controls "at the freezing ref"; the freezing
  ref does not exist yet. Running the command now and calling it frozen would freeze controls a
  week or more before job 1, at a ref the freezing commit does not name.
- **Append-only edits.** The draft's own rule (section 3.5) and the repository's rule for dated
  docs: changes go in as dated rows and sections; earlier rows stay as written.

## Verification

Run on this laptop, 2026-10-28, `C:/t/pin125/Scripts/python.exe` (the exact pins), `PYTHONPATH=src`:

- `ruff check .` and `ruff format --check .` (ruff 0.15.12): clean, 101 files formatted.
- `mypy --strict` (the `[tool.mypy]` file set, `scripts/` included): no issues in 49 files.
- `pytest -q`: **1,100 passed** at `fc904655`. Not a register value: NC-021 is measured at this
  PR's merge commit.
- `git diff --stat origin/main` after the `main` merge: 20 files, 3,191 insertions, 0 deletions.
- The null values: `python docs/evidence/hardware-reading-vs-level/null_values.py --out <dir>`,
  about 10 s; its built-in Monte Carlo check exits 1 if any exact Arm B figure is off by more
  than 4 standard errors.
- The re-pin, from the repository root (outputs compared by `git hash-object` against
  `git rev-parse HEAD:<path>`):
  - `python -m scripts.hardware_test_grid_bias --out <dir>`
  - `python docs/evidence/hardware-reading-vs-level/measure_checkup_floor.py --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --out <short dir>`
  - `python docs/evidence/hardware-reading-vs-level/measure_recal_hours.py --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b --out <dir>`
- The rehearsal: `python scripts/hardware_test_predictors.py --repo . --ref 7adda8035a5a76b93147ffc3171975a7684d239d --mode controls --at 2026-10-28T18:40:46Z --out <dir>`.

Not checked: any of this on Linux or Burak's desktop; Bengisu's review.

## Related docs

- `docs/roadmap/2026-10-24-issue-125-preregistration.md` (the draft this changes)
- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design)
- `docs/implementations/2026-10-28-hardware-test-offline-half.md` on `mert/issue-125-offline-half`
  (the twelve owed amendments)
- `docs/roadmap/2026-10-23-phase-4-plan.md` §8 on PR #131 (step 1c)
- PR #132 (selection rules, step 1a); PR #128's review (Bengisu's lessons)
- Issue #125
