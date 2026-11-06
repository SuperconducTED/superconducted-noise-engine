# ADR-030 — Kraus projector boundary: gate-name agnostic, parameters rejected not clipped

**Status**: Draft. Requires approval from both owners of the LOCKED module
`channels/kraus.py` (@bengisucvd primary, @BurakOztekin secondary). Issue #75.

**Context**: Issue #58 found two unresolved contracts in
`KrausChannelProjector`:

1. `_SINGLE_QUBIT_GATES` was declared but never consulted; `project()` took
   `gate_name` and behaved identically for every name.
2. `_amplitude_damping_kraus` / `_phase_damping_kraus` clamped `gamma` and
   `lambda` into `[0, 1]`. That duplicates ADR-012's pipeline-level
   `ProbabilityClip`, changes values when a caller deliberately chooses
   `IdentitySquashing`, and mapped NaN to `1.0` (maximal damping) while
   `integration.aer_factory.is_identity_damping` classifies the same NaN vector
   as degenerate.

**Decision**:

- *Gate names*: the unused constant is deleted. The projector is documented as
  name-agnostic. Gate eligibility lives exclusively in
  `FuzzyNoiseModel.prepare()` through the injected policy (#73, ADR-028), so
  there is one filter, not two.
- *Parameter domain*: `gamma` and `lambda` must be finite and in `[0, 1]`;
  anything else raises `ValueError`. The channel boundary never repairs input.
  Clipping remains the squashing stage's responsibility (ADR-012).

**Consequences**:

- Every in-range channel is unchanged (SuperOp difference < `1e-12`, pinned in
  `tests/test_kraus_boundary.py`).
- A pipeline using `IdentitySquashing` that emits values outside `[0, 1]` now
  fails loudly at `project()` instead of silently clipping.
- ADR-008's normalization strategies still see only valid CPTP-by-construction
  candidate sets.
- `is_identity_damping` still reports a NaN vector as identity; with the
  projector now raising, that vector can no longer be installed as damping.
