# Follow-Up Issues from First ADR Cycle Audit

**Date**: 2026-05-25
**Source**: `docs/audits/2026-05-25-first-cycle-audit.md`

These issue drafts are queued for filing. Each includes a title, body, and suggested labels.

---

## 1 ADR-016 text/implementation alignment

**Labels**: `area:benchmarks`, `type:docs`

ADR-016 says "mean-aggregates counts" but `harness.py:simulate_engine` does element-wise sum via `Counter.update()` with `shots = shots_per_member * len(members)`. This is probability-equivalent under normalized metrics (Hellinger, KL, fidelity, R-squared) but is not mean-aggregation of raw counts.

The smoke script `scripts/first_ensemble_run.py:run_ensemble` truly mean-aggregates via `round(v / n)`, and per-key rounding can leave `sum(returned.values())` differing from `shots` by up to one count per bin.

**Resolution options**:
- (A) Update ADR-016 text, `architecture.md` line 161, and `harness.py` docstring to describe sum-with-scaled-shots.
- (B) Refactor `harness.py:simulate_engine` to true mean-aggregation matching the smoke script.

**References**: ADR-016 in `docs/decisions.md`, `src/superconducted/benchmarks/harness.py:53-89`, `scripts/first_ensemble_run.py:73-78`, `docs/architecture.md:161`.

---

## 2 Harness module docstring drift

**Labels**: `area:benchmarks`, `type:docs`

`src/superconducted/benchmarks/harness.py` line 3 says "Mean-aggregates ensemble counts" but the function performs element-wise sum with scaled total shots. Update the docstring to match the resolution of Issue 1 above.

**References**: `src/superconducted/benchmarks/harness.py:3`.

---

## 3 Architecture.md ADR-016 table

**Labels**: `type:docs`

`docs/architecture.md` line 161 describes ADR-016 bootstrap behavior as "mean". Needs alignment with the resolution of the ADR-016 text/implementation alignment issue.

**References**: `docs/architecture.md:161`.

---

## 4 Implementation doc stale cron timing

**Labels**: `area:calibration`, `type:docs`

`docs/implementations/2026-05-13-calibration-poller-cron.md` says "Cron at minute :05" but the actual schedule is `:37` since PR #17. Implementation docs are historical records of what was true at merge time. Recommended action: add a dated addendum noting the schedule change.

**References**: `docs/implementations/2026-05-13-calibration-poller-cron.md`, PR #17.

---

## 5 ADR-018 formalization

**Labels**: `area:fuzzy`, `type:docs`

The slope > 0 convention for all tanh-based MFs needs to land as an accepted ADR after PR #14 resolves its review feedback. Draft is at `docs/decisions/drafts/ADR-018-tanh-slope-positive-convention.md`.

Acceptance criteria:
- PR #14 merged with `TanhSigmoidMF` and `TanhBellMF` enforcing positive slopes.
- ADR-018 moved from `docs/decisions/drafts/` into the main `docs/decisions.md` ledger with status Accepted.
- ADR-006 `Revisited` note updated to reference the accepted (not draft) ADR-018.

**References**: PR #14, Issue #2, ADR-006, `src/superconducted/fuzzy/membership.py:179-186`.

---

## 6 Nduv-walk convergence

**Labels**: `area:calibration`, `type:enhancement`

`BasicCalibrationVectorizer.extract` (predating ADR-017) and `loader._parse_value` (landing with ADR-017) parse the same IBM calibration JSON with different traversal logic. The vectorizer walks `properties.qubits[i]` and matches by `name`; the loader walks the same structure and matches by `name` and `unit`. Both produce correct results today but the duplicated parsing is a maintenance risk.

This falls under ADR-013 scope (calibration feature engineering). Convergence could take the form of the vectorizer consuming the typed `ParsedCalibrationSnapshot` from the loader instead of re-walking raw JSON.

**References**: ADR-013, ADR-017, `src/superconducted/calibration/vectorizer.py`, `src/superconducted/calibration/loader.py`.

---

## 7 Circuit-mutation safety documentation

**Labels**: `area:integration`, `type:docs`

`FuzzyNoiseModel.prepare()` may mutate the circuit it receives (currently for `PostGateFuzzification`; future pre-gate and between-gate strategies per ADR-007 will modify the circuit in place). All callers must pass `circuit.copy()` to maintain ensemble-member isolation.

This contract is currently enforced by code review (PR #13 blocker) but is not documented in `aer_factory.py`'s module docstring or in ADR-002. Recommended: add a Revisited note to ADR-002 or document the contract in the `FuzzyNoiseModel.prepare()` docstring.

**References**: ADR-002, ADR-007, `src/superconducted/integration/aer_factory.py`, PR #13 review.

---

## 8 Snapshot timestamp type inconsistency

**Labels**: `area:calibration`, `type:enhancement`

`ParsedCalibrationSnapshot.timestamp` is typed as plain `str` (archival form, preserving lossless round-trip). `CalibrationSnapshot.timestamp` (in `types.py`) is typed as tz-aware `datetime` with `__post_init__` enforcement. Two snapshot abstractions now disagree on timestamp semantics.

Recommended: either unify on one representation, or document the intentional divergence (archival form vs. runtime form) in ADR-020.

**References**: `src/superconducted/calibration/loader.py` (`ParsedCalibrationSnapshot`), `src/superconducted/types.py` (`CalibrationSnapshot`), PR #16 review (mertefesensoy minor).

---

## 9 Smoke script builds a 2×2×2 grid, not the ratified 3×3×3

**Labels**: `area:fuzzy`, `type:bug`

ADR-010 is now **Accepted** and ratifies a 3×3×3 (27-rule) baseline grid. The only in-repo runtime construction of that grid does not match it: `scripts/first_ensemble_run.py:_default_mfs_for_feature` (line 97) returns **two** `GaussianMF` objects per feature, so `TSKRuleBase.from_grid` receives `K_i = 2` on each of the 3 dimensions and builds `2 × 2 × 2 = 8` rules, not 27.

This is genuine drift between the ratified decision and the shipped smoke script, found while confirming ADR-010 (issue #24). It was deliberately **not** fixed in that closure, which was scoped to the ledger.

**Resolution options**:
- (A) Add a third `GaussianMF` per feature in `_default_mfs_for_feature` so the smoke script instantiates the ratified 27-rule baseline.
- (B) Keep 8 rules in the smoke script for speed and document explicitly, in both the function docstring and ADR-010, that the smoke script uses a deliberately reduced grid and is not the baseline.

Note the `from_grid` call site itself needs no change either way — `per_input_mfs` is a plain argument, so this is a configuration fix, not a change to the LOCKED `fuzzy/tsk.py`.

**References**: ADR-010 in `docs/decisions.md`, `scripts/first_ensemble_run.py:81-97` and `:123-128`, `docs/implementations/2026-08-19-adr-010-closure.md`.

---

## 10 architecture.md ADR-010 row still reads TBD

**Labels**: `type:docs`

`docs/architecture.md` line 160 reads `| ADR-010 Rule count | RuleBase | 27 (3×3×3 grid) | TBD |`. With ADR-010 now Accepted, the post-decision column should carry the ratified value (27 rules over `mean_T1`, `mean_T2`, `mean_readout_error`) rather than `TBD`.

Out of scope for the ADR-010 closure, which was restricted to `docs/decisions.md` plus its own record.

**References**: `docs/architecture.md:160`, ADR-010 in `docs/decisions.md`.

---

## 11 No regression test pins the ratified 27-rule grid

**Labels**: `area:fuzzy`, `type:test`

`tests/test_tsk.py:test_from_grid_cartesian_product` (line 67) exercises a `2 × 3 = 6` grid only. Nothing in the test suite asserts the now-ratified `3 × 3 × 3 = 27` baseline, so a future change to `from_grid` could break the ratified arity without a red test.

A test asserting `n_rules == 27`, `input_dim == 3`, and 27 pairwise-distinct antecedent tuples would pin it. Such a test lives in `tests/`, so it does **not** touch the LOCKED `fuzzy/tsk.py` and does not require the two-owner lock procedure — but it does need the test-file owner (the owner of the implementation under test, per `docs/team.md` line 32).

**References**: `tests/test_tsk.py:67`, `src/superconducted/fuzzy/tsk.py:185-224`, ADR-010 in `docs/decisions.md`.

---

## 12 Stale ADR-010 references after the closure

**Labels**: `type:docs`

Three references to ADR-010 went stale when it moved to Accepted:

- `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` line 48 still lists ADR-010 as `Open`.
- Issue #24's body cites ADR-010 at `docs/decisions.md` lines 192-205; after the ADR-006 closure (PR #26) and the ADR-009 memo (PR #27) the entry actually began at line 187. Line-number citations in issue bodies drift as the ledger grows — prefer anchoring by ADR heading.
- Item 6 above cites `src/superconducted/calibration/vectorizer.py`, a path that does not exist; the file is `src/superconducted/calibration/features.py`.

**References**: `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md:48`, `docs/decisions.md`, issue #24, item 6 of this file.
