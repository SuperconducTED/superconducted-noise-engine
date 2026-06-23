# ADR-022 — Benchmark validation criteria

**Status**: Accepted.

**Context**: The benchmark harness computes four metrics (Hellinger
distance, KL divergence, state fidelity, R-squared) to compare the
fuzzy noise engine's output against a reference simulation. Every later
result the team produces rests on these numbers being correct. A
function that silently mis-computes Hellinger distance would invalidate
every comparison run by every teammate and every plot in the paper.

Issue #5 established that the harness needed validation tests that check
the numbers themselves, not just that the code runs without crashing.

**Decision**: Every metric in the benchmark harness must be validated
against the following standing property set:

1. **Identity**: `metric(P, P)` returns the metric's self-similarity
   baseline (0 for distance metrics, 1 for fidelity/R-squared).
2. **Symmetry or asymmetry**: Symmetric metrics (Hellinger) must satisfy
   `metric(P, Q) == metric(Q, P)`. Asymmetric metrics (KL) must have a
   test asserting `metric(P, Q) != metric(Q, P)` on a non-trivial
   example.
3. **Bounds**: Hellinger and fidelity output in [0, 1]. KL output >= 0.
4. **Monotonicity**: With Aer's depolarizing noise model, increasing
   depolarizing probability p must monotonically increase distance
   metrics and monotonically decrease fidelity.
5. **Determinism**: Same circuit + same noise model + same seed + same
   shot count produces identical metric values across runs.
6. **Reference value**: At least one hand-derivable scenario (e.g.,
   single-qubit depolarizing channel with known p) verified within
   shot-noise tolerance (3-sigma).

Tests must use real `SimulationResult` frozen dataclasses, not
`MagicMock`. This enforces value-object invariants and detects API drift
between test fixtures and production objects.

Any new metric added to the harness must satisfy all six properties
before merge.

**Consequences**:

- The property set is the minimum bar. Additional tests (e.g., triangle
  inequality for Hellinger) are encouraged but not required.
- Probabilistic tests are inherently shot-based. Fixed seeds and
  generous tolerances (3-sigma) prevent CI flakiness.
- If a property test fails on first run and the cause is a real harness
  bug, the bug is filed as a separate issue (not fixed in the validation
  PR).
- Real-hardware comparison tests are deferred until IBM backend access
  is available for benchmarking.

**Source**: Issue #5 (benchmark validation scope), PR #10
(implementation), `docs/implementations/2026-05-13-harness-metric-sanity-checks.md`.
