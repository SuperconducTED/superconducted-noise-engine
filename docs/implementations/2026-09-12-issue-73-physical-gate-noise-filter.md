# 2026-09-12: issue-73-physical-gate-noise-filter

## Problem / Motivation

Issue #73 found that `FuzzyNoiseModel.prepare()` sent every single-qubit
instruction to the Kraus projector. The projector intentionally ignores
`gate_name`, so this attached the same damping channel to virtual `rz` gates
and could attach it to administrative instructions such as `delay` and Aer
save/snapshot operations. That is inconsistent with Issue #58's physical
reference-noise semantics: a zero-duration virtual `rz` has no thermal
relaxation interval.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/integration/aer_factory.py` | Derives eligible single-qubit noise operations from positive-duration archived calibration gate-length records before invoking the channel projector. |
| `scripts/first_ensemble_run.py` | Makes the synthetic calibration describe positive physical `sx` and zero-duration virtual `rz` gate-length records. |
| `tests/test_noise_gate_eligibility.py` | Covers real calibrated, virtual, administrative, qubit-aware, missing-gate-length, and injected-policy cases. |

## Implementation approach

`FuzzyNoiseModel.prepare()` delegates to an injected `GateEligibilityPolicy`.
The default `CalibrationGateEligibilityPolicy` resolves a frozen set of
`(gate_name, qargs)` pairs from archived `properties.gates` records via
`training.targets.gate_lengths()`, the same parser used for #58's
thermal-relaxation targets. A record is eligible only when its single-qubit
`gate_length` is finite and strictly positive. The nested `error_provider`
returns `None` for every non-member; `PostGateFuzzification` already treats
that as "do not install an error."

The calibration gate-length record is authoritative rather than an injected or
hard-coded allowlist. Gates absent from those records and non-positive durations
are ignored, so the policy fails closed. Invalid gate-length schemas retain the
existing `gate_lengths()` behavior and raise `CalibrationParseError` rather
than silently treating potentially corrupt calibration data as physical.
In particular, virtual `rz` is excluded because its archived `gate_length` is
zero, while `delay` and save/snapshot instructions are absent from the physical
gate records. `channels/kraus.py` remains unchanged: it is LOCKED and owns
Kraus construction, not physical-gate eligibility.

`prepare()` receives a circuit compiled to this physical basis. This is the
canonical ADR-021 contract: errors are registered against physical names and
the returned circuit is run without another transpilation. Issue #74 applies
that ordering to `first_ensemble_run.py`.

## Mathematical / Statistical details

N/A - no channel parameters or statistical estimators changed. For a calibrated
gate length $t$, the eligibility predicate is $t \in \mathbb{R}$,
$\operatorname{isfinite}(t)$, and $t > 0$.

## Design decisions

Issue #73 offered calibration records or an explicit allowlist as the source
of eligible gates. We chose archived calibration gate-length records, the same
physical source parsed by #58's reference-model work. Matching includes both
the gate name and physical qubit tuple, so a calibration on one qubit does not
implicitly authorize the same gate on another. `GateEligibilityPolicy` keeps
this decision injectable without making `ChannelProjector` responsible for it.

This change is deliberately limited to the integration policy boundary. It
does not add multi-qubit channels, change the projector, alter fuzzification
placement under ADR-007, or revise snapshot persistence.

## Verification

Run from the repository root against the pins in `requirements*.txt`, which is
what CI installs. All five gates, in the order `.github/workflows/ci.yml` runs
them:

- `ruff check .`
- `ruff format --check .`
- `python scripts/check_ids.py`
- `mypy --strict`
- `pytest tests/ -q`

## Related docs

- ADR-021 in `docs/decisions.md`
- Issue #58 reference-model scope in `docs/roadmap/2026-09-03-phase-3-plan.md`
- Issue #73

---

## 2026-09-18 follow-up: make an empty noise model audible

Added by @mertefesensoy during review of PR #96. Scope: `aer_factory.py` and
`tests/test_noise_gate_eligibility.py` only.

### Problem

The eligibility filter keys on physical basis names (`id`, `rx`, `sx`, `x` on
`ibm_fez`), but `benchmarks/harness.py:75` calls `prepare()` on untranspiled
logical circuits and never transpiles at all. The filter is correct; the caller
is wrong. The consequence is that `prepare()` returns a `NoiseModel` with no
errors, the caller simulates a noiseless circuit, and the run still succeeds.

Measured against `tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json`,
`main` (125b796) versus this branch, installed errors per circuit:

| Circuit | `main` | this branch |
| --- | --- | --- |
| `ghz_state_circuit(3)` | `['h']`, 1 error | `[]`, 0 errors |
| `qft_circuit(3)` | `[]`, 0 errors | `[]`, 0 errors |
| `vqe_ansatz_circuit(3)` | `['ry', 'rz']`, 6 errors | `[]`, 0 errors |
| `random_clifford_circuit(3, 3)` | `['h','s','sdg','x','z']`, 14 errors | `['x']`, 1 error |

The same filter is correct once the circuit is compiled:
`transpile(ghz_state_circuit(3), basis_gates=['id','rz','sx','x','cz'],
optimization_level=1, seed_transpiler=0)` then `prepare()` installs `['sx']`,
3 errors, with `rz` and `cz` correctly excluded.

### What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/integration/aer_factory.py` | `prepare()` warns through `warn_if_nothing_was_installed` when it installs no error, distinguishing "this snapshot has no eligible gate" from "this circuit is not in the calibrated basis". |
| `tests/test_noise_gate_eligibility.py` | Pins both warning messages and pins silence on a circuit already in the calibrated basis. |

### Implementation approach

The transpile fix belongs to Issue #58 and is already written on PR #79
(`bengisu/issue-58-benchmark-certification`), which rewrites `simulate_engine`
to `simulate_engine(circuits, ensemble, *, basis_gates, ...)` with
`_transpile_circuits` before `prepare()`. Duplicating that here would collide
with 312 lines of in-flight work on another author's branch, so this change
does not touch `harness.py`.

What it does instead is remove the silence. `prepare()` inspects the
`NoiseModel` it is about to return; if nothing was installed it warns, naming
the circuit's instruction names and the calibration's eligible gate names side
by side, so the mismatch is readable at a glance:

    FuzzyNoiseModel.prepare installed no error: none of the circuit's
    instructions ['barrier', 'cx', 'h', 'measure'] is eligible under this
    calibration ['id', 'rx', 'sx', 'x']. Compile the circuit to the
    calibrated physical basis before calling prepare().

`stacklevel=3` attributes the warning to the caller, so the harness path
reports it at `harness.py:75` rather than inside the library.

### Design decisions

**Warn, not raise.** ADR-021 fixes `prepare()`'s return contract as
`tuple[QuantumCircuit, NoiseModel]`, and a circuit can be legitimately
noise-free: an `rz`-only or measure-only circuit installs nothing for a correct
physical reason. Raising would break those callers to catch a caller mistake.
The accepted cost is that such a circuit also warns; the message says what was
present and what was eligible, so a reader can dismiss it in one line.

**A bare `warnings.warn`, not a new warning class.** `training/targets.py`
already reports an unusable calibration this way. A new public exception type
would be a new public API surface on a PR that is already adding an ABC.

**No new ABC method.** Deciding "is this circuit in the right basis" from
`eligible_operations` alone keeps `GateEligibilityPolicy` at one method and
keeps `aer_factory` from assuming a calibration payload shape that an injected
policy may not use.

### Mathematical / statistical details

N/A. No channel parameter, estimator or threshold is introduced; the guard is
a set-intersection test on instruction names.

### Verification

Run from the repository root against the pins in `requirements*.txt`
(`qiskit 2.4.1`, `qiskit-aer 0.17.2`, `numpy 2.4.4`, `pytest 9.0.3`,
`ruff 0.15.12`, `mypy 1.20.2`):

- `pytest tests/ -q` — 475 passed (472 before this section, 3 added here)
- `ruff check .` — passed
- `ruff format --check .` — passed, 61 files
- `python scripts/check_ids.py` — passed
- `mypy --strict` — passed, 35 source files

To see the guard fire on the real harness path, build a
`FuzzyNoiseModelEnsemble` from the fixture above and call
`simulate_engine([ghz_state_circuit(3)], ensemble, shots=64)` under
`warnings.catch_warnings(record=True)` with `simplefilter("always")`; the
warning is attributed to `harness.py:75`.

### Known gaps left open

- `benchmarks/harness.py` still never transpiles. This change makes that
  audible, not fixed. The fix is #58 FR-3, written on PR #79, which is a
  CONFLICTING draft last updated 2026-09-08. **#96 should not merge into a
  phase-3 measurement run before #79 lands.**
- `scripts/first_ensemble_run.py` prepares before transpiling; that ordering
  is #74, which explicitly excludes `harness.py`.

### Related docs

- ADR-021 in `docs/decisions.md`
- Issues #58, #73, #74; PR #79

---

## 2026-09-18 follow-up 2: close the two open acceptance criteria

Added by @mertefesensoy. Scope: `aer_factory.py`, `interfaces.py` and
`tests/test_noise_gate_eligibility.py`.

### Problem

Two of #73's eight acceptance criteria were not met at `f690652`, and two
review findings shared a single fix.

1. **Criterion 1, the test-only reproduction, had regressed.** It held at
   `bbdd456`, whose test module imported only pre-fix API. The `940f2b7`
   rewrite added `CalibrationGateEligibilityPolicy` and `GateEligibilityPolicy`
   to the module's top-level imports, so against the pre-fix tree the file
   raised `ImportError` at collection instead of failing on the bug.
2. **Criterion 5, qubit-aware, had no test.** Every gate in the archive fixture
   is calibrated on all 156 qubits, so no existing assertion could tell a
   qubit-aware policy from one matching on gate name alone. The doc's "What
   changed" table nonetheless claimed the case was covered.
3. `eligible_operations` was re-resolved on every `prepare()` call from a
   snapshot that cannot change: 2.52 ms per call, 80.7 ms per 32-member
   ensemble pass on the 1132-record fixture, and a malformed `gate_length`
   unit raised `CalibrationParseError` out of `prepare()` rather than at
   construction, untested.
4. The policy returns **physical** qubit indices while `PostGateFuzzification`
   matches them against an instruction's **positional** index in
   `circuit.qubits`. Nothing said so.

### What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/integration/aer_factory.py` | Resolves eligibility once in `__init__` beside `_crisp_params`, and documents the positional-versus-physical qubit contract on `prepare()`. |
| `src/superconducted/interfaces.py` | States on `GateEligibilityPolicy` that its qubit tuples are physical indices and that implementations must be pure in the snapshot. |
| `tests/test_noise_gate_eligibility.py` | Restores the pre-fix reproduction, and adds qubit-aware, qubit-aware-through-installation, and construction-time-rejection cases. |

### Implementation approach

**Reproduction.** Module-level imports are held to the API that exists on the
pre-fix tree, the two new names are imported inside the three tests that need
them, and `_model` forwards `gate_eligibility_policy` only when one is given so
the call does not hit an unknown keyword. Verified against `main` (`125b796`):
the module collects, and
`test_prepare_uses_real_gate_lengths_to_filter_physical_instructions` fails with

    assert ['delay', 'rz', 'save_density_matrix', 'sx', 'x'] == ['sx', 'x']

which is exactly the erroneous attachment #73 describes: `rz`, `delay` and
`save_density_matrix` all receiving the damping channel.

**Qubit-awareness.** `_properties_with_sx_disabled_on(qubit)` takes the real
fixture and records one qubit's `sx` as 0 ns, which is the only way to
distinguish the two policies on a device calibrated uniformly. Asserted at the
policy (`("sx", (0,))` out, `("sx", (1,))` in, `("x", (0,))` untouched) and
again through `prepare()`.

**Hoisting.** Eligibility moves next to `_crisp_params`, which is the module's
existing pattern for "resolve the pipeline once at construction". This is sound
because `eligible_operations` is pure in the snapshot and `CalibrationSnapshot`
is a frozen point-in-time record; that requirement is now written into the ABC
rather than assumed.

### Mathematical / statistical details

N/A. No channel parameter, estimator or threshold changed. The 0 ns edit uses
the same eligibility predicate as before: finite and strictly positive.

### Design decisions

**Local imports in tests over a second test module.** Splitting the pre-fix
reproduction into its own file would have kept top-level imports clean, but it
separates the assertion from the fixture helper and `_model` that give it
meaning, and it leaves two files to keep in step. Three local imports are the
smaller cost, and the module docstring says why they are there so nobody
"tidies" them back up.

**A per-qubit fixture edit over a synthetic snapshot.** A hand-written snapshot
would have made the qubit-aware test trivial to write and worthless to read,
which is the failure mode the first review round already caught once. Editing
one record of the real archive fixture keeps every other field physical.

### Verification

Run from the repository root against the pins in `requirements*.txt`:

- `pytest tests/ -q` gives 478 passed, up from 475
- `ruff check .`, `ruff format --check .` (61 files), `python scripts/check_ids.py`
- `mypy --strict` (35 source files)

To confirm the reproduction still reproduces, copy
`tests/test_noise_gate_eligibility.py` onto a checkout of `main` and run it:
all 10 tests fail, and the one named above fails on the assertion quoted there
rather than on an import.

### Related docs

- ADR-021 in `docs/decisions.md`
- Issues #58, #73, #74; PR #79
