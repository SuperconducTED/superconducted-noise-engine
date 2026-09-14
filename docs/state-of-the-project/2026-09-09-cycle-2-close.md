# Cycle 2 close: what the plan asked for, and what actually landed

**Date**: 2026-09-09 · **Measured at**: `main` @ `5f935ea` · **Issue**: #56 FR-5

Scores the six goals of `docs/roadmap/2026-05-25-cycle-2-plan.md` (its `## Cycle 2 Goals`
list) against the ADR ledger, lists what merged, and records what cycle 2 taught about
gates. Naming and structure follow `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md`.

Every classification below is derived from the `**Status**` line quoted from
`docs/decisions.md` at `5f935ea`, not copied from any plan or ticket. Every figure resolves
to a `docs/numerical-claims.md` row or to a named file on `main`.

---

## 1. The six-goal scorecard

| # | Goal (cycle-2 plan) | Governing ADR | Status line quoted at `5f935ea` | Score |
| --- | --- | --- | --- | --- |
| 1 | Reach the 630-snapshot training floor and implement the TSK trainer | ADR-014 | `**Status**: Deferred.` | **Missed** |
| 2 | Merge PR #14 and formalize ADR-018 | ADR-018 | `**Status**: Accepted.` | **Met** |
| 3 | Execute the MF shape ablation | ADR-019 | `**Status**: Open.` | **Missed** |
| 4 | Resolve T1 vs Interval Type-2 | ADR-009 | `**Status**: Open.` | **Missed** |
| 5 | Implement per-member perturbation | ADR-015 | `**Status**: Deferred.` | **Missed** |
| 6 | Close the mean-vs-sum aggregation ambiguity | ADR-016 | `**Status**: Deferred.` | **Partially met** |

**One of six met.** That is the headline and it should not be softened.

### Notes per row

**Goal 1 · Missed, and the target itself was wrong.** ADR-014 is still `Deferred`. The
floor was never reached, and the floor figure was also incorrect. NC-012 records `>= 630`,
derived as "roughly 126 trainable parameters x 5". Nothing in the repository ever derived
the 126; `git log -S'126'` puts it into `docs/architecture.md` on 2026-05-07, before the
27-rule grid existed. Measured from the rule base at `5f935ea`, a 3x3x3 Gaussian grid at
`output_dim = 2` carries **234** trainable parameters (216 consequent, 18 unique premise),
reproducing **NC-037**. The derived floor is therefore 234 x 5, and the archive's 504
distinct states (**NC-025**, at `calibration-data` `f0930b9`) sit further below it than the
plan believed. The floor row itself is registered by #56's M3 PR; this record does not
register it, and states the arithmetic as traceable to NC-037 rather than as a new claim.

The trainer is not absent, though. Its *contract* landed in cycle 2's closing weeks: the
`TSKTrainer` ABC, `training/targets.py`, `training/parameters.py` and ADR-027 all merged in
PR #69 and PR #83. The implementation is #60's, in phase 3.

**Goal 2 · Met.** ADR-018 reads `Accepted`. PR #14 merged 2026-06-14, landing
`TanhSigmoidMF` and `TanhBellMF`.

**Goal 3 · Missed.** ADR-019 reads `Open`. The protocol is written into the ADR entry;
no ablation has been executed. It is #62 in phase 3.

**Goal 4 · Missed.** ADR-009 reads `Open` and its own text still calls the IT2 direction
provisional, pending the ADR-019 ablation that goal 3 did not run. This is the highest
fan-out decision in the graph: ADR-011, ADR-015 and ADR-021 all wait behind it. It is
routed to Dr. Akba as item 3 of the #56 FR-12 advisor batch.

One measured input that did not exist when the plan was written, and that weakens the
standard objection to IT2: moving from `GaussianMF` to `IntervalGaussianMF` costs **9**
additional trainable parameters, not a doubling, because the consequent term (216 of 234)
dominates and IT2 touches only the premise term. The per-shape counts are measured but not
registered here; they land with the floor in #56's M3 PR.

**Goal 5 · Missed.** ADR-015 reads `Deferred`, and its own Decision text defers it until
ADR-009 is resolved and ADR-014 has trained MFs whose training variance is a meaningful
quantity. Neither happened, so the deferral is consistent rather than neglected. The
consequence is live: `FuzzyNoiseModelEnsemble` still yields N identical models, so any
interval reported today would be zero-width. #64 exists to stop M4 reporting point
estimates computed from identical members.

**Goal 6 · Partially met, and the distinction matters.** ADR-016 reads `Deferred`. The goal
was to "align harness code, smoke script, and documentation to a single aggregation
contract". Two of the three locations were aligned by PR #81 on 2026-09-08:

| Location | State at `5f935ea` |
| --- | --- |
| `src/superconducted/benchmarks/harness.py` module docstring | Element-wise sum, retaining the total shot count |
| `docs/architecture.md`, ADR-016 row, bootstrap cell | `sum (probability-equivalent to mean under normalized metrics)` |
| `scripts/first_ensemble_run.py::run_ensemble` | **Still a true mean**, `round(v / n)` |

The third location is unchanged **by design**. It is a behaviour difference, not a wording
one: per-key rounding can leave `sum(returned.values())` differing from `shots` by up to one
count per bin. Changing it is an executable change, which #56 forbids itself. So the
descriptions now agree with the harness, the smoke script still means, and that is recorded
rather than papered over. Hence partially met, not met.

The mean-to-interval semantics upgrade, which is the part of ADR-016 that would move it off
`Deferred`, belongs to #64 at M4.

---

## 2. What actually landed since 2026-05-25

Re-derived at execution with `gh pr list --state merged`, filtered to `mergedAt >= 2026-05-25`.

| Measure | Value |
| --- | --- |
| Pull requests merged | **27** |
| Merged **into `main`** | **25** |
| Documentation-only | **12** |

The two not merged into `main`, with their base branches, because a merged-PR count that
does not say this overstates what reached `main`:

- **#39**, base `mert/ledger-entry`. Reissued as **#51**, which merged into `main` on
  2026-09-06 after the 2026-08-31 identifier collision forced the branch reissue.
- **#71**, base `feature/issue-57-training-target`. The duplicate-identifier CI check;
  it reached `main` through PR #69.

The documentation-only figure was **measured** from each PR's own `files` list
(`[.files[].path] | all(startswith("docs/"))`), not carried from memory: PRs #26, #27, #30,
#32, #36, #38, #42, #43, #52, #67, #78, #82.

The full list, in merge order: #14, #19, #26, #27, #29, #30, #32, #33, #34, #36, #38, #39,
#42, #43, #44, #50, #51, #52, #55, #67, #69, #71, #78, #80, #81, #82, #83.

> **NOTE · This count moves.** It is measured at 2026-09-09 and phase-3 PRs are open. Any
> later record re-runs the query rather than adding a delta to this number.

---

## 3. ADR ledger movement

Continuing the series the two `## Ledger reconciliation` tables in
`docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` started. **That file is not
edited**; this table continues it here, covering `as-of 2026-08-26` to `5f935ea`.

| Item | As-of 2026-08-26 | At `5f935ea` | Changed by |
| --- | --- | --- | --- |
| ADR-024 | Did not exist | `**Status**: Accepted.` — degeneracy of random TSK consequent initialization | PR #44 |
| ADR-025 | Did not exist | `**Status**: Accepted.` — `calibration-data` ledger and collision trees; amended 2026-09-02 with `duplicate-partial` | PR #50, amended by PR #55 |
| ADR-027 | Did not exist | `**Status**: Open.` — calibration training target | PR #69 |
| ADR-016 Context / Decision text | "mean-aggregates counts" | "sums counts element-wise (probability-equivalent to mean under normalized metrics)"; Status still `Deferred` | PR #81 (`ade4dd2`) |
| ADR-009, ADR-011, ADR-019 | `Open` | `Open` | unchanged |
| ADR-014, ADR-015, ADR-016 | `Deferred` | `Deferred` | unchanged |

There is no ADR-026. The sequence runs ADR-025 then ADR-027; recorded here so a future
reader does not go looking for a lost entry.

> **NOTE · One append-only exception, knowingly taken.** PR #81's ADR-016 change shows
> `16 insertions, 2 deletions` on `docs/decisions.md`: it rewrote the Context and
> `Decision (current)` lines rather than only appending. Issue #25's Part 2 acceptance
> criteria required exactly that ("none is left saying bare 'mean'"); #56 FR-6 Part 2
> forbade it. #81 followed the ticket it was closing, kept the mean-to-interval upgrade
> language verbatim, kept Status at `Deferred`, left the `> Revisited · 2026-05-25` note
> byte-identical, and appended a dated `> Aligned · 2026-09-07` note explaining the change.
> The residual artefact is that the 2026-05-25 note now opens by quoting wording that no
> longer appears above it. The appended note says so. Recorded, not reverted; the fuller
> account is in the #25 closing comment.

NC-022 (drift count = 4) is pinned to `dfee09c` and is not restated here.

---

## 4. The data-integrity programme

Issues #45, #46, #50, #52, #53, #54 and #55 formed an unplanned arc that consumed much of
August. It was not in the cycle-2 plan and it is the most substantial thing cycle 2
produced.

**What it found:** the dataset was smaller, slower-growing and less complete than every
figure in the plan assumed, and the pipeline could not say why.

| Finding | Row | Value, with the commit it was measured at |
| --- | --- | --- |
| The floor's unit was ambiguous, now decided as distinct device states | NC-012 | `>= 630`, unit decided 2026-08-30 |
| Distinct device states in the archive | NC-025 | 504, at `calibration-data` `f0930b9` |
| Historical calibration retention, verified depth | NC-026 | `>= 60 days`, a lower bound only |
| Capture over the 2026-08-27..30 scheduler outage | NC-029 | `<= 19.3%` (11 of at least 57) |
| IBM document republication rate | NC-030 | `>= 19 documents/day`, mean interval `<= 1.26 h` |
| Enumeration sweep recall at a 1 h step | NC-031 | 87.9% (29 of 33) |
| Capture **outside** a known outage | NC-032 | see below |
| Bulk calibration rounds inside the Aug 7-17 gaps | NC-033 | 13 rounds, 9,807 parameter measurements |
| Live-path document stability across those gaps | NC-034 | 1 distinct `properties` block per window over 154 revisions |
| Full test-suite size | NC-021 | 370 at `8176d79` |

**The finding that reframed the phase:** NC-029 said capture collapses during an outage,
which was expected. **NC-032 said it is not confined to outages.** In a 62-hour window of
ordinary operation with the scheduler behaving, capture was at most 70.2%, with 14 missed
documents in 13 gaps of 1.1 to 3.2 hours. The mechanism is aliasing between an hourly
sampler with arbitrary dispatch delay and a publisher at a mean interval of at most 1.26 h.
Volume was never the constraint that the plan thought it was.

**NC-032's current value is deliberately vacuous, and says so.** The row now reads
`<= 100% (50 of >= 50)` at `calibration-data` `3d1569d`, because #53 backfilled the very
window the row measures. Holding everything you can prove exists gives 100% by
construction. The row carries an explicit warning against reading it as "capture is fine",
and the 2026-09-02 figure of `<= 70.2% (33 of >= 47)` is preserved in its Notes as what the
poller actually captured. A capture rate describing ordinary operation now needs a window
that has not been backfilled; that is #54, which stays open.

**Two corrections the arc made to its own evidence**, worth recording because both are
cases of a measurement contradicting a prior belief:

- The `>= 47` denominator in NC-032 was itself an undercount. Three further documents inside
  the same span were recovered that the 1 h sweep never served, so that sweep served 43 of
  the 50 now known to exist, 86.0%, corroborating NC-031's 87.9% from an independent
  direction.
- The Aug 7-17 windows were neither "the backend was idle" nor "we fetched fresh documents
  and lost them". NC-033 refutes the first with 13 calibration rounds inside the gaps;
  NC-034 refutes the second with first-party evidence that the poller received the *same*
  document 154 times.

**The recovery worked.** #53 ran four dispatches at a 0.5 h step and recovered 27 documents
against the 14 it predicted, closing on 2026-09-08. The 2026-09-05 guard date passed before
the dispatches ran and cost nothing, because the 30-day limit is a default rather than a
retention boundary and `max_historical_days=60` clears it. What cost time was four days of
drift after #55 unblocked the work.

**One defect the ledger caught in itself.** The backfill wrote a `collision` file. It was
our comparator, not IBM republishing: 26 of 1952 gate entries differed in nothing but a
per-parameter `date`, and those 26 were exactly the entries carrying the `gate_error = 1`
"not calibrated" placeholder, because the history endpoint re-stamps the entries it
synthesises. Fixed by `_strip_parameter_dates` in PR #80. ADR-025's own Consequences section
predicted this reading: a non-empty `collisions/` means the comparison is wrong, not that
IBM republished. The prediction held.

---

## 5. What cycle 2 taught about gates

**Cycle 2 gated on a date, and the date passed without the gate being met.**

The plan's first goal reads "estimated ~2026-07-10 at sustained polling cadence (~11.1
snapshots per day)". That estimate was built on NC-009 and NC-011, both 2026-05-25
measurements, and on the snapshot-file unit that #45 later argued against and that NC-012
replaced with distinct device states. The projection is retired as **NC-R002**.

The failure was not that the estimate was wrong. Estimates are wrong. The failure was that
a date was allowed to stand in for an artifact. "Reach the floor by ~2026-07-10" reads like
a gate and behaves like a wish: nothing checks it, nothing fails when it passes, and work
downstream of it proceeds on the assumption that it held.

Two documents still carry `~2026-07-10` and are **deliberately left unedited**:
`docs/findings/2026-05-25-empirical-synthesis.md` and
`docs/roadmap/2026-05-25-cycle-2-plan.md`. They were accurate on 2026-05-25. Dated documents
are reconciled by appending an as-of section, never by rewriting rows, and NC-R002's
retirement note records why.

**Phase 3 gates on artifacts and decisions.** `docs/roadmap/2026-09-03-phase-3-plan.md`
carries the M0 to M4 gate text; this record cites that path rather than restating it. Each
gate is an artifact that exists or a decision that has been taken, and the dates beside them
are targets. Where a milestone has a prerequisite in another ticket, the gate is stated as
"after X merges" first and the calendar date second. The tracking object on GitHub is one
milestone, `Phase 3 · ANFIS results`, due 2026-09-30, not five milestone objects for M0
through M4.

The one date-shaped constraint that survived into phase 3 is IBM's retention on historical
calibration reads, and it is a measured lower bound (NC-026), not an ambition.

---

## 6. Where cycle 2 leaves phase 3

Stated plainly, because the phase-3 plan is built on it:

- **The trainer has a contract but no implementation.** ADR-027, the `TSKTrainer` ABC and
  the target and parameter modules are on `main`. The trainer is #60.
- **The ensemble is still degenerate.** N identical members, so no interval is meaningful
  yet. #64 owns making M4 honest about that.
- **The dataset is further from its floor than the plan said**, in both directions at once:
  the floor is higher than 630 once derived from the rule base, and the archive's growth is
  limited by IBM's publish rate rather than by our polling cadence.
- **The advisor loop has never closed.** None of the ten questions in
  `docs/advisor/2026-05-25-questions-for-akba.md` has a recorded answer. #56 FR-12 opens
  `docs/advisor/2026-09-03-decisions-from-akba.md` as the fixed location and sends one
  batched request with a decision-by date per item.

---

## Related documents

- `docs/roadmap/2026-05-25-cycle-2-plan.md` — the six goals scored here
- `docs/roadmap/2026-09-03-phase-3-plan.md` — the M0 to M4 gate text
- `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` — naming and as-of precedent; the ledger reconciliation series section 3 continues
- `docs/decisions.md` — ADR-009, ADR-011, ADR-014, ADR-015, ADR-016, ADR-018, ADR-019, ADR-024, ADR-025, ADR-027
- `docs/numerical-claims.md` — NC-012, NC-021, NC-025, NC-026, NC-029 to NC-034, NC-037, NC-R002
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` — the four #45 decisions
- `docs/advisor/2026-09-03-decisions-from-akba.md` — the advisor decision record (#56 FR-12)
- Issues #45 (closed 2026-09-09), #25 (closed 2026-09-08), #53 (closed 2026-09-08), #54 (open)
