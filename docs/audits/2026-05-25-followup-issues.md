# ❯ Follow-Up Issues from First ADR Cycle Audit

**Date**: 2026-05-25
**Source**: `docs/audits/2026-05-25-first-cycle-audit.md`

These issue drafts are queued for filing. Each includes a title, body, and suggested labels.

---

## ❯ 1 ADR-016 text/implementation alignment

**Labels**: `area:benchmarks`, `type:docs`

ADR-016 says "mean-aggregates counts" but `harness.py:simulate_engine` does element-wise sum via `Counter.update()` with `shots = shots_per_member * len(members)`. This is probability-equivalent under normalized metrics (Hellinger, KL, fidelity, R-squared) but is not mean-aggregation of raw counts.

The smoke script `scripts/first_ensemble_run.py:run_ensemble` truly mean-aggregates via `round(v / n)`, and per-key rounding can leave `sum(returned.values())` differing from `shots` by up to one count per bin.

**Resolution options**:
- (A) Update ADR-016 text, `architecture.md` line 161, and `harness.py` docstring to describe sum-with-scaled-shots.
- (B) Refactor `harness.py:simulate_engine` to true mean-aggregation matching the smoke script.

**References**: ADR-016 in `docs/decisions.md`, `src/superconducted/benchmarks/harness.py:53-89`, `scripts/first_ensemble_run.py:73-78`, `docs/architecture.md:161`.

---

## ❯ 2 Harness module docstring drift

**Labels**: `area:benchmarks`, `type:docs`

`src/superconducted/benchmarks/harness.py` line 3 says "Mean-aggregates ensemble counts" but the function performs element-wise sum with scaled total shots. Update the docstring to match the resolution of Issue 1 above.

**References**: `src/superconducted/benchmarks/harness.py:3`.

---

## ❯ 3 Architecture.md ADR-016 table

**Labels**: `type:docs`

`docs/architecture.md` line 161 describes ADR-016 bootstrap behavior as "mean". Needs alignment with the resolution of the ADR-016 text/implementation alignment issue.

**References**: `docs/architecture.md:161`.

---

## ❯ 4 Implementation doc stale cron timing

**Labels**: `area:calibration`, `type:docs`

`docs/implementations/2026-05-13-calibration-poller-cron.md` says "Cron at minute :05" but the actual schedule is `:37` since PR #17. Implementation docs are historical records of what was true at merge time. Recommended action: add a dated addendum noting the schedule change.

**References**: `docs/implementations/2026-05-13-calibration-poller-cron.md`, PR #17.

---

## ❯ 5 ADR-018 formalization

**Labels**: `area:fuzzy`, `type:docs`

The slope > 0 convention for all tanh-based MFs needs to land as an accepted ADR after PR #14 resolves its review feedback. Draft is at `docs/decisions/drafts/ADR-018-tanh-slope-positive-convention.md`.

Acceptance criteria:
- PR #14 merged with `TanhSigmoidMF` and `TanhBellMF` enforcing positive slopes.
- ADR-018 moved from `docs/decisions/drafts/` into the main `docs/decisions.md` ledger with status Accepted.
- ADR-006 `Revisited` note updated to reference the accepted (not draft) ADR-018.

**References**: PR #14, Issue #2, ADR-006, `src/superconducted/fuzzy/membership.py:179-186`.

---

## ❯ 6 Nduv-walk convergence

**Labels**: `area:calibration`, `type:enhancement`

`BasicCalibrationVectorizer.extract` (predating ADR-017) and `loader._parse_value` (landing with ADR-017) parse the same IBM calibration JSON with different traversal logic. The vectorizer walks `properties.qubits[i]` and matches by `name`; the loader walks the same structure and matches by `name` and `unit`. Both produce correct results today but the duplicated parsing is a maintenance risk.

This falls under ADR-013 scope (calibration feature engineering). Convergence could take the form of the vectorizer consuming the typed `ParsedCalibrationSnapshot` from the loader instead of re-walking raw JSON.

**References**: ADR-013, ADR-017, `src/superconducted/calibration/vectorizer.py`, `src/superconducted/calibration/loader.py`.

---

## ❯ 7 Circuit-mutation safety documentation

**Labels**: `area:integration`, `type:docs`

`FuzzyNoiseModel.prepare()` may mutate the circuit it receives (currently for `PostGateFuzzification`; future pre-gate and between-gate strategies per ADR-007 will modify the circuit in place). All callers must pass `circuit.copy()` to maintain ensemble-member isolation.

This contract is currently enforced by code review (PR #13 blocker) but is not documented in `aer_factory.py`'s module docstring or in ADR-002. Recommended: add a Revisited note to ADR-002 or document the contract in the `FuzzyNoiseModel.prepare()` docstring.

**References**: ADR-002, ADR-007, `src/superconducted/integration/aer_factory.py`, PR #13 review.

---

## ❯ 8 Snapshot timestamp type inconsistency

**Labels**: `area:calibration`, `type:enhancement`

`ParsedCalibrationSnapshot.timestamp` is typed as plain `str` (archival form, preserving lossless round-trip). `CalibrationSnapshot.timestamp` (in `types.py`) is typed as tz-aware `datetime` with `__post_init__` enforcement. Two snapshot abstractions now disagree on timestamp semantics.

Recommended: either unify on one representation, or document the intentional divergence (archival form vs. runtime form) in ADR-020.

**References**: `src/superconducted/calibration/loader.py` (`ParsedCalibrationSnapshot`), `src/superconducted/types.py` (`CalibrationSnapshot`), PR #16 review (mertefesensoy minor).
