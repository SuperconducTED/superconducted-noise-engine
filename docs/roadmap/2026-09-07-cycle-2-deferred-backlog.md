# 2026-09-07 · Cycle-2 deferred backlog

Everything the cycle-2 opening batch surfaced and deliberately did not action,
catalogued so none of it is lost. Issue #25 Part 4.

This is a dated snapshot. Per the dated-doc convention, it is reconciled by
appending a new as-of section (or a new dated file), never by editing the rows
below in place.

Dates carried from `docs/roadmap/2026-05-25-cycle-2-plan.md` are **the plan's
estimates, not measured figures**, and are labelled as such throughout. Where an
item said "re-verify before carrying", the re-verification was run against `main`
@ `dd27e3e` on 2026-09-07 and its result is recorded rather than assumed.

---

## 1 · ADR-016 · mean-to-interval aggregation upgrade

**Status**: deferred, gated on ADR-015.

Issue #25 Part 2 aligned the *description* of current bootstrap aggregation
across `docs/decisions.md`, `src/superconducted/benchmarks/harness.py` and
`docs/architecture.md` — all three now read "sum (probability-equivalent to mean
under normalized metrics)", matching what `simulate_engine` actually does
(`Counter.update()` element-wise, with `shots = shots * len(members)`).

That was a truth fix, not a decision. The substantive upgrade — moving bootstrap
aggregation from a point estimate to an interval-valued aggregation (min/max or
quantile across members) — remains open and is **not** decided here. The plan's
ADR Unblock Graph gates it on ADR-015 delivering per-member variation actually
worth bracketing, estimated ~2026-07-24 (plan estimate).

---

## 2 · P2 · duplicate IBM-calibration JSON value coercion

**Status**: open. Confirmed present on `main` @ `dd27e3e` on 2026-09-07.

Two functions coerce values out of IBM calibration JSON with different logic:

| | location | on failure |
| --- | --- | --- |
| `_parse_value` | `src/superconducted/calibration/loader.py:200` | raises `CalibrationParseError`, and applies unit scaling |
| `_coerce_finite_float` | `src/superconducted/calibration/features.py:26` | returns `None` silently |

Listed only. The dedup is a P2 refactor tied to ADR-013 / ADR-017 and is not
actioned here — the two call sites want different failure semantics, so merging
them is a design question, not a mechanical extraction.

---

## 3 · P2 · snapshot timestamp type — **RESOLVED**

The cycle-2 plan carried this as a possible type mismatch between
`ParsedCalibrationSnapshot.timestamp` and `CalibrationSnapshot.timestamp`.

Re-verified on 2026-09-07 with `git log -S "timestamp: datetime" --
src/superconducted/calibration/loader.py`, as the ticket requires rather than
carrying it blindly:

- `src/superconducted/calibration/loader.py:177` declares `timestamp: datetime`.
- The class docstring states it is a tz-aware UTC `datetime`, explicitly matching
  `superconducted.types.CalibrationSnapshot`.
- Fixed by **`7e1021e`** (2026-05-17, "calibration: address PR #16 review
  feedback"), i.e. it was already resolved when the cycle-2 plan was written and
  the plan's snapshot simply predated the check.

Recorded Resolved rather than dropped silently, so a future reader can see the
item was checked and not merely forgotten.

---

## 4 · Data-gated Phase 1 / 2 work

Listed only. Every date is **the plan's estimate**, not a measured figure; the
630-snapshot floor in particular was a projection, and NC-R002 retired the
projected date rather than confirming it.

| ADR | Work | Gated on | Plan's estimate |
| --- | --- | --- | --- |
| ADR-019 | MF-shape ablation execution | ADR-018 (merged) + trained or manual parameters | ~2026-06-01 manual path, ~2026-07-17 trainer path |
| ADR-009 | T1 vs IT2 resolution | ADR-006 (closed) + ADR-019 ablation results | ~2026-06-01 decision, ~2026-07-19 empirical |
| ADR-011 | Defuzzification | follows ADR-009 | — |
| ADR-007 | Fuzzification-placement comparison | empirical comparison infrastructure | ~2026-06-08 |
| ADR-014 | TSK trainer | 630-snapshot floor + target-distribution definition | ~2026-07-10 |
| ADR-013 | Vectorizer comparison | — | — |
| ADR-015 | Per-member perturbation | ADR-009 + ADR-014 | ~2026-07-17 |
| ADR-021 | Variance injection | follows ADR-015 | — |

The ADR-019 protocol is drafted at
`docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` and has **not** been
run.

---

## 5 · ADR-008 · normalization — event-driven, no sequencing slot

Monitor passively. The plan classifies this as event-driven with an indeterminate
date: it activates only if a channel is observed to violate CPTP-by-construction,
which would trigger the normalization need. It is deliberately **not** a dated
item and should not be scheduled.

---

## Not carried, and why

- **Cron timing** · the plan's P2 "stale `:05` cron" item was already fixed by
  `490d47e` (2026-05-26), one day after the plan's 2026-05-25 snapshot.
  `docs/implementations/2026-05-13-calibration-poller-cron.md` was re-read on
  2026-09-07 and already documents the `:37` timing with its rationale. Confirmed
  resolved, no edit made, and deliberately not carried here.

## Related

- `docs/roadmap/2026-05-25-cycle-2-plan.md` — Engineering Follow-Ups table, Risk
  Register, ADR Unblock Graph and Sequencing Recommendation.
- `docs/decisions.md` — ADR-016's dated alignment note, 2026-09-07.
- Issue #25 — the closeout sweep this backlog belongs to.
