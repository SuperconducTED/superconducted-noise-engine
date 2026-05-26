# First ADR Cycle Audit

**Date**: 2026-05-25
**Scope**: ADR-001 through ADR-017 · 8 merged PRs + 1 open PR · 7 issues · 54 commits on `main` · 5 implementation docs.
**Baseline**: `main` at `31ce3aa`, working tree clean.

---

## 1 Per-ADR Drift Table

| ADR | Still Accurate? | Drift Summary | Action |
| --- | --- | --- | --- |
| ADR-001 | Yes | TSK only; no Mamdani code anywhere in tree | None |
| ADR-002 | Yes | `FuzzyNoiseModelEnsemble` in `integration/aer_factory.py` | None |
| ADR-003 | Yes | `pyproject.toml:33` pins `qiskit-ibm-runtime`; sole IBM import at `calibration/poller.py:283` | None |
| ADR-004 | Yes | `src/` layout, hatchling, MIT confirmed | None |
| ADR-005 | Yes | No ML framework in deps | None |
| ADR-006 | **Drift** | `TanhMF._validate` (`fuzzy/membership.py:179-186`) enforces positive slopes; constraint not mentioned in ADR text | Appended `Revisited` note; draft ADR-018 |
| ADR-007 | Yes | Pre/Between stubs raise `NotImplementedError` citing ADR-007 | None |
| ADR-008 | Yes | CPTP/Derivative stubs raise `NotImplementedError` citing ADR-008 | None |
| ADR-009 | Yes | Both T1 and IT2 paths functional; `IntervalGaussianMF` tested | None |
| ADR-010 | Yes | `BasicCalibrationVectorizer.output_dim=3`; grid parameterizable via `from_grid` | None |
| ADR-011 | Yes | Both defuzzifiers implemented | None |
| ADR-012 | Yes | Identity, ProbabilityClip, Sigmoid all present | None |
| ADR-013 | Yes | Enriched by `mean_t1`/`mean_t2` from ADR-017; no patch needed | None |
| ADR-014 | Yes | No trainer code; smoke script uses `consequent_init="random"` | None |
| ADR-015 | Yes | `FuzzyNoiseModelEnsemble.__iter__` yields identical models | None |
| ADR-016 | **Drift** | Text says "mean-aggregates counts"; harness does element-wise sum with scaled shots (probability-equivalent but not raw-count mean); smoke script truly mean-aggregates with rounding; docstring and `architecture.md` also say "mean" | Appended `Revisited` note; follow-up issues queued |
| ADR-017 | Yes | Matches shipped code in `calibration/loader.py` and `calibration/features.py` | None |

---

## 2 Per-PR Unrecorded-Decision Table

| PR | Title | Decisions Surfaced | ADR Candidate? | ADR Target or Reason Not |
| --- | --- | --- | --- | --- |
| #7 | Calibration poller cron deployment | Orphan branch for snapshots, concurrency serialization, explicit failure on zero output, timeout tightening, `contents:write` scope, SHA-pinning deferred, backend literal dedup deferred | None found | Operational deployment, CI hardening, and security posture choices; all documented in implementation doc. Orphan-branch storage pattern formalized as draft ADR-020. |
| #8 | Backend switch `ibm_brisbane` to `ibm_fez` | `ibm_fez` chosen from three available 156-qubit Heron devices; comprehensive stale-reference cleanup | None found | Operational: driven by account plan constraints, all three Heron r2 devices are equivalent |
| #10 | Harness validation tests | Real `SimulationResult` over mocks (blocker); test naming convention; template compliance (blocker); metric branch coverage; `make_state` type hint inconsistency | Testing policy | Validation property-set formalized as draft ADR-022. Real-type testing policy captured under New Threads. |
| #12 | CI snapshot commit fix | File-level `mv` instead of directory-level `mv` | None found | Bug fix for GNU `mv` behavior |
| #13 | Aer integration walkthrough | Silent exception fallbacks prohibited (blocker); circuit-mutation safety on `prepare()` (blocker); mean aggregation per ADR-016; shared `AerSimulator` instance; `crisp[:2] > 0` guard; degenerate-by-design documented; per-feature MF scaling deferred; synthetic snapshot default | Conventions (not standalone ADR) | Error-propagation and circuit-copy conventions captured under New Threads. `prepare()` mutation contract is an implementation detail of ADR-002/ADR-007. |
| #14 | TanhSigmoidMF and TanhBellMF (open) | Slope > 0 required for all tanh-based MFs | **Yes** | Draft ADR-018 at `docs/decisions/drafts/ADR-018-tanh-slope-positive-convention.md` |
| #16 | Typed calibration loader | `Optional[float]` data contract; unit validation as hard error; `FieldMissingness` NamedTuple; `Parsed` prefix naming; `mean_t1`/`mean_t2` as free functions; timestamp type inconsistency (`str` vs `datetime`) | None (covered) | All implementation details of ADR-017. Timestamp type inconsistency tracked as follow-up issue. |
| #17 | Cron :05 to :37 | Mid-hour scheduling to avoid GHA high-load window | None found | Operational tuning |
| #18 | Dependabot `python-dotenv` bump | None | None found | Automated dependency bump |

---

## 3 Per-Issue Pending-Decision Table

| Issue | Status | Decision Shape | Pending Decision | Tracking Action |
| --- | --- | --- | --- | --- |
| #2 | Open | MF parameter convention | Default slope value for `TanhSigmoidMF`/`TanhBellMF` ("discuss with Mert before hard-coding") | Blocked on PR #14 review resolution |
| #3 | Closed | None | None | Resolved via PR #7; storage pattern formalized as draft ADR-020 |
| #4 | Closed | None | None | Resolved via PR #13; Aer constraint already in ADR-002 |
| #5 | Closed | None | None | Resolved via PR #10; validation criteria formalized as draft ADR-022 |
| #6 | Open | ADR process | Four new ADR drafts requested; all four drafted (ADR-019, -020, -021, -022) | See section 6e |
| #9 | Closed | None | None | Resolved via ADR-017 (Accepted) |
| #15 | Closed | None | None | Resolved via PR #17 |

---

## 4 Commit-Cluster Themes

| Cluster | Hash Range | Date Range | Theme |
| --- | --- | --- | --- |
| Bootstrap | `8e5c045`..`6ecba5d` | 2026-05-07 | Repo scaffold, packaging, ADR-001 through ADR-015, all core interfaces and implementations |
| Calibration poller | PR #7, PR #8, PR #12, PR #17 | 2026-05-13 to 2026-05-20 | Live IBM backend integration, cron deployment, snapshot pipeline hardening |
| Testing and validation | PR #10 | 2026-05-13 | Harness metric tests, frozen dataclass fixtures, branch coverage |
| Aer integration | PR #13 | 2026-05-14 | First end-to-end ensemble run, smoke script, mean aggregation, shared simulator |
| Typed calibration | PR #16 | 2026-05-16 | Typed loader, `Optional[float]` data contract, ADR-017 formalization |

---

## 5 Implementation-Doc Cross-Reference

| Document | Date | PR | ADR References | Notes |
| --- | --- | --- | --- | --- |
| `2026-05-07-repo-bootstrap.md` | 2026-05-07 | (bootstrap) | ADR-001 through ADR-015 | Comprehensive; mentions mypy 1.20.2 pin and ruff PL exclusion |
| `2026-05-13-calibration-poller-cron.md` | 2026-05-13 | #7 | ADR-003 | Stale cron timing: says `:05` but actual is `:37` since PR #17 |
| `2026-05-13-harness-metric-sanity-checks.md` | 2026-05-13 | #10 | ADR-016 | Verification steps match current test suite |
| `2026-05-14-aer-ensemble-walkthrough.md` | 2026-05-14 | #13 | ADR-002, ADR-015, ADR-016 | Documents degenerate-by-design ensemble and mean aggregation |
| `2026-05-16-loader-missing-fields.md` | 2026-05-16 | #16 | ADR-013, ADR-017 | Documents Skip strategy, `FieldMissingness`, Nduv-walk deferred |

---

## 6 New Threads Synthesis

### 6a Aggregation semantics inconsistency

Three descriptions of ensemble aggregation exist in the codebase, and they do not agree:

- **ADR-016 text** (`docs/decisions.md`): "mean-aggregates counts"
- **`harness.py:simulate_engine`** (lines 70-89): element-wise sum via `Counter.update()`, with `shots = shots_per_member * len(members)`. Probability-equivalent to mean under normalized metrics but is not raw-count mean.
- **`scripts/first_ensemble_run.py:run_ensemble`** (line 78): true mean via `round(v / n)`. Per-key rounding can leave `sum(returned.values())` differing from `shots` by up to one count per bin.
- **`harness.py` module docstring** (line 3) and **`docs/architecture.md`** (line 161): both say "mean".

Follow-up issue queued to resolve: either update text to describe sum-with-scaled-shots, or refactor `harness.py` to true mean.

### 6b Nduv-walk duplication

`BasicCalibrationVectorizer.extract` (predating ADR-017) and `loader._parse_value` (landing with ADR-017) parse the same IBM calibration JSON with different traversal logic. The vectorizer walks `properties.qubits[i]` and matches by `name`; the loader walks the same structure and matches by `name` and `unit`. Both produce correct results but the duplicated parsing is a maintenance risk. Tracked as a follow-up issue under ADR-013 scope.

### 6c Tanh slope convention

`TanhMF._validate` (`fuzzy/membership.py:179-186`) enforces `slope_left > 0` and `slope_right > 0` at construction. Non-positive slopes invert or collapse the raw tanh window; the `clip(0, 1)` on line 194 then masks the invalid parameterization by clamping degenerate output to zero, hiding a configuration error rather than surfacing it. PR #14 proposes two new tanh-based MFs (`TanhSigmoidMF`, `TanhBellMF`) that face the same constraint. Draft ADR-018 formalizes this convention.

### 6d Project-level conventions (not ADR-worthy)

Five durable conventions emerged from review threads across multiple PRs:

1. **Real types in tests, not mocks** (PR #10, PR #13). Tests must use real `SimulationResult` frozen dataclasses, not `MagicMock`. Rationale: frozen dataclasses enforce value-object invariants; mocks hide API drift between test fixtures and production objects.

2. **No silent exception fallbacks in the integration layer** (PR #13). Errors from the fuzzy pipeline must propagate; `except: pass` or `|| true` patterns are rejected on review. Rationale: silent failures in a noise-model pipeline produce silently incorrect simulation results with no diagnostic signal.

3. **Circuit-mutation isolation on `prepare()` calls** (PR #13). Any code calling `member.prepare(circuit)` must pass `circuit.copy()` to prevent mutation leakage across ensemble members or fuzzification strategies. Rationale: future pre-gate and between-gate fuzzification (ADR-007) may modify the circuit in place; shared references would corrupt concurrent member simulations.

4. **Implementation doc template is mandatory** (PR #10). Every substantive PR must include `docs/implementations/YYYY-MM-DD-<slug>.md` following `_TEMPLATE.md` sections exactly. Missing sections or wrong file location is a merge blocker.

5. **Transpilation required before `AerSimulator.run()` with custom noise** (PR #13). High-level circuits (QFT, `efficient_su2`) require explicit `transpile(circuit, backend=sim)` before running against custom noise models. Aer raises `unknown instruction` on un-transpiled high-level gates.

### 6e Issue #6 ADR draft coverage

Issue #6 requests four new ADR drafts. This audit assessed each and produced drafts where evidence supports formalization:

| Requested ADR | Draft Produced? | Location or Reason |
| --- | --- | --- |
| MF ablation methodology | **Yes** (ADR-019, Open) | `docs/decisions/drafts/ADR-019-mf-ablation-methodology.md` |
| Calibration snapshot schema and storage | **Yes** (ADR-020, Accepted) | `docs/decisions/drafts/ADR-020-calibration-snapshot-schema-and-storage.md` |
| Aer integration constraint | **Yes** (ADR-021, Accepted/Open) | `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md` |
| Benchmark validation criteria | **Yes** (ADR-022, Accepted) | `docs/decisions/drafts/ADR-022-benchmark-validation-criteria.md` |

All four of Issue #6's requested ADR drafts are now produced. Additionally, ADR-018 (tanh slope positivity) was drafted from PR #14's review thread. This was not among Issue #6's four requests but emerged from the decision-discovery pass.

---

## 7 Ambiguities Surfaced for Human Review

1. **ADR-016 resolution direction**: Refactor `harness.py:simulate_engine` to true mean-aggregation, or update ADR-016 text (and `architecture.md`, docstring) to accurately describe sum-with-scaled-shots? The current probability-equivalence holds only under normalized metrics.

2. **`make_state` type hint inconsistency** (PR #10): The function's type hint advertises `float | complex` but only `float` values are used in all test fixtures and call sites. Bug (should accept complex), or documentation drift (should narrow the hint to `float`)?

3. **Stale cron timing in implementation doc**: `docs/implementations/2026-05-13-calibration-poller-cron.md` says "Cron at minute :05" but actual is `:37` since PR #17. Implementation docs are historical records. Add a dated addendum, or leave as-is with the follow-up issue tracking the drift?

---

## Summary

| Metric | Count |
| --- | --- |
| ADRs reviewed | 16 |
| ADRs patched in place | 2 (ADR-006, ADR-016) |
| New ADRs drafted | 6 (ADR-017, ADR-018, ADR-019, ADR-020, ADR-021, ADR-022) |
| PRs reviewed | 9 (8 merged + 1 open) |
| Issues reviewed | 7 |
| Commits surveyed | 54 |
| Implementation docs cross-referenced | 5 |
| Follow-up issues queued | 8 |
| Ambiguities surfaced for human review | 3 |
