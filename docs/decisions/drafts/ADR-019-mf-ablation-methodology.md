# ADR-019 — Membership function ablation methodology

**Status**: Open.

**Context**: The advisor (Dr. Akba) recommended a tanh-based MF shape
as first-priority empirical test against the Gaussian baseline. Four T1
shapes are implemented at bootstrap (Gaussian, Triangular, Trapezoidal,
Tanh) plus `IntervalGaussianMF` for the IT2 path. ADR-006 defers the
empirical winner selection.

Issue #2 specifies `TanhSigmoidMF` and `TanhBellMF` as additional
candidates. The full ablation requires a comparison protocol that is
reproducible and covers the metrics formalized in the benchmark harness
(Hellinger distance, KL divergence, state fidelity, R-squared).

No ablation protocol is currently documented. Without one, each
contributor would run ad-hoc comparisons with different circuits, shot
counts, and noise configurations, producing non-comparable results.

**Decision (current)**: The ablation protocol for MF shape selection is:

1. **Fixed benchmark suite**: Use the four existing benchmark circuits
   (random Clifford, GHZ, QFT, `efficient_su2` ansatz).
2. **Fixed calibration snapshot**: Use a single representative snapshot
   from the `calibration-data` branch (timestamp and backend recorded
   in the results table).
3. **Fixed shot count**: 4096 shots per ensemble member, ensemble
   size N = 8, chosen for runtime.
4. **All four metrics**: Report Hellinger, KL, fidelity, and R-squared
   for each (MF shape, circuit) pair.
5. **Baseline**: Gaussian MF with the bootstrap `from_grid` default
   parameterization.
6. **Reproducibility**: Fixed random seed. Script committed to
   `scripts/`. Results table committed to `docs/findings/`.

The winner is the shape that minimizes Hellinger distance (primary) and
maximizes fidelity (secondary) across the benchmark suite relative to a
real-hardware reference distribution. If no real-hardware reference is
available at comparison time, the comparison is against an Aer
simulation with the same circuit and a known-good noise model.

**Consequences**: The ablation is blocked until (a) PR #14 lands
`TanhSigmoidMF` and `TanhBellMF`, and (b) the trainer (ADR-014) or a
manual parameterization provides non-trivial MF parameters for each
candidate shape. The protocol must be re-evaluated if the metric set
changes (e.g., if trace distance or diamond norm is added).

**Source**: Issue #2 (tanh MF implementation), Issue #6 (ADR curation
scope), Dr. Akba's recommendation recorded in Issue #2 body.
