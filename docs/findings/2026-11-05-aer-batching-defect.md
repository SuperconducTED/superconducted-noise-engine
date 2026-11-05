# Aer multiplies a density-matrix circuit's state by 2 per noise location, after a statevector circuit

**Date**: 2026-11-05 · **Author**: Mert Efe Şensoy · **Status**: findings, laptop,
provisional until a desktop rerun · **Register**: NC-097, NC-098 · **Evidence**:
`docs/evidence/aer-batching-defect/`

## 1. Summary

On Qiskit Aer 0.17.2 with the default automatic method, one `run()` can give a silently wrong
result. If a circuit Aer simulates by statevector comes before the first circuit it simulates by
density matrix, and the noise model holds a Kraus-form error anywhere, then each noise location in
the density-matrix circuit multiplies its state by 2. A circuit with `k` noise locations ends with
trace `2^k`. Aer raises nothing. Sampling then reads the oversized state from the lowest outcome up,
so the counts pile onto `00...0`.

The smallest reproduction is a one-qubit circuit whose true `P(0)` is 0.1, which gives 0.197 after
another circuit, with its probabilities summing to exactly 2. It needs only `qiskit` and
`qiskit-aer`, and a public fake backend reaches it too.

**Nothing registered is affected and no code on `main` is exposed.** One committed output on the
local, unpushed branch `mert/issue-125-submission` is wrong because of it: the Arm B lines of
`probe_build_time.out.txt`. No document quotes them. The QPU runs no Aer, so hardware results cannot
have it. Section 5 gives the audit.

All 72 rows of the sweep, predicted in advance from Aer's source, were met. That makes the reading
below strong, and it is still a reading: nobody has rebuilt Aer with the suspected lines changed.

## 2. The finding

### What happens

Measured, each from `trigger_sweep.py`, with `amplitude_damping_error(0.1)` on `x`:

| One run holds | Sum of the second circuit's probabilities |
| --- | --- |
| an 11-qubit circuit, then one `x` | 2 |
| the same, then two `x` | 4 |
| the same, then three `x` | 8 |
| the same, then no noisy gate | 1 |
| one `x`, then the 11-qubit circuit | 1 |
| one `x` alone | 1 |

The state is otherwise right. On a two-qubit circuit with coherences, every element of the density
matrix is exactly 2 or 4 times the element from a run alone (largest gap 0, tolerance `1e-9`). The
statevector circuit is unharmed: its counts are identical alone and in a batch.

Sampled results follow `min(1, 2^k G)`, where `G` is the true cumulative distribution in integer
order. With one noise location and damping `g`, `P(0)` is `2g`: 0.1050, 0.1973 and 0.3955 for `g` of
0.05, 0.1 and 0.2. A three-qubit GHZ has `k = 3`, so `8 p(000)` passes 1 and every shot lands on
`000`. Readout error then moves some of them, which is the symptom first seen: `000` at 0.9429 (the
prediction `0.98^3` is 0.9412) and `111` with no counts. Without readout error, `000` takes all 2,048
shots.

### Why it is easy to miss

The Hellinger fidelity of a distribution that is all `000` to an ideal GHZ is exactly 0.5, whatever
the true state was. So a metric meant to catch this settles near a plausible value. On Arm B, whose
true fidelity is about 0.48, it moves only from 0.480 to 0.466. On the sweep's cleaner GHZ it falls
from 0.8488 to 0.4714, so the small change on Arm B is a coincidence of the noise level, not a
property of the defect.

### The smallest trigger

Established, by the row named, on the committed script:

| Question | Answer | Rows |
| --- | --- | --- |
| How few qubits | Two one-qubit circuits, if the first has a gate after a measurement, which forces it onto statevector at any shot count. Without that: a two-qubit circuit then a one-qubit one, at 3 or 4 shots. | C8, D6, D7 |
| Which noise | One error with a `kraus` instruction, anywhere in the model, even on a gate no circuit uses. Amplitude damping, phase damping and thermal relaxation with T2 above T1 have one. | B7 to B10 |
| Which noise does not | Depolarizing, Pauli, reset, mixed and coherent unitary, thermal relaxation with T2 below T1, readout error: none of them triggers it alone. | B1 to B6, B11 |
| Does every error double | Circuit-form errors do. Pauli-Lindblad errors, which Aer builds by a different code branch, do not, even when another error triggers the defect. | B12 to B14 |
| Does the first circuit's active qubit count matter | Only by choosing its method: it must satisfy `shots <= 2^n1`. Active means measured or feeding a measurement, not register width and not having a gate. | C1, C2, C5 to C7 |
| Does the first circuit's content matter | No. A circuit of measurements alone triggers it, and it need not contain any noisy gate. | C3, C4 |
| Does the shot count matter | Only through the window `2^n2 < shots <= 2^n1`, for two sampleable circuits. An 11-qubit and a one-qubit circuit: 2,048 shots triggers it and 2,049 does not. The size of the factor does not depend on shots. | D1 to D10 |
| Does order matter | What matters is whether the first statevector circuit precedes the first density-matrix one. `[S, F, S']` is right throughout; `[F, S, S']` is wrong for both `S`. | A5, E1, E2 |
| Does anything persist between runs | No. The same simulator object, right after a defective run, gives the right answer alone. | E3 |
| What escapes it | `method="statevector"`, `method="density_matrix"`, no noise model, or a separate `run()`. Giving `method="automatic"` explicitly does not, and neither does `max_parallel_threads=1`. | E3, E5 to E9 |
| Primitives | `BackendSamplerV2` and `qiskit_aer.primitives.SamplerV2` both show it when PUBs share a shot count, and neither does when the shots differ, because they group PUBs by shots into separate runs. | F1 to F4 |
| Outside our circuits | `FakeFez().run([big, ghz])` gives `000` 0.988 and `111` 0.000, against 0.489 and 0.469 alone. | H3 |

On this project's own circuits, the sum for Arm B after Arm A is 1,024 times its sum alone, to twelve
decimals, on all six layouts. Arm B has 7 noisy gates and 3 delay channels, so `k` is 10.

### The mechanism, as far as it can be established from outside

Read from Aer's source at tag `0.17.2`, commit `51c67981`:

1. `aer_controller.hpp:751-771`: before executing anything, Aer loops over the run's circuits. The
   first density-matrix circuit calls `enable_superop_method`. A statevector circuit calls
   `enable_kraus_method` if the model holds Kraus noise. One noise model serves the whole run.
2. `quantum_error.hpp:422-430`: `compute_kraus` computes the superoperator if it is empty, then
   converts it.
3. `quantum_error.hpp:493-508`: `compute_circuits_superoperator` calls
   `superoperator_.initialize(dim, dim)`, then adds into `superoperator_` with `+=`.
4. `matrix.hpp:441-450`: `initialize` only reallocates and zeroes when the dimensions change.
5. `noise_model.hpp:434-470`: each `enable_*` guards on its own method only, so neither knows the
   other has already computed the superoperator.

So the statevector-first order computes the superoperator twice with no zeroing between, giving `2S`
for a channel `S`. The density-matrix-first order computes it once, because `compute_kraus` then finds
it non-empty. A Pauli-Lindblad error goes through `compute_generators_superoperator`
(`quantum_error.hpp:511-534`), which starts from `superoperator_ = iden` and cannot accumulate.

**This reading was committed as a set of predictions before any run, and all 72 sweep rows were met**,
including the ones that could most easily have failed it: the exact factor `2^k`, the sharp shot
boundaries, the two different results from the two code branches in B12 to B14, and a trigger not seen
before, two one-qubit circuits. So we write that the code path and the numbers it predicts agree. We
do not write that the cause is proven, because no Aer was rebuilt with `initialize` zeroing or the
second computation skipped.

### What is not established

- **Other versions.** Nothing was run on any other version. `compare_source.py` finds all nine functions
  the reading names identical on tag `0.18.2`, and on Aer's `main` as of 2026-11-05 the only change is
  the exception index PR #2500 fixed in the two `enable_*` functions. GitHub's history shows
  `quantum_error.hpp` last changed on 2024-06-07 and `matrix.hpp` on 2023-03-13. So newer and somewhat
  older versions may carry the defect, and that is an inference from reading.
- **Other platforms and paths.** Windows laptop only. GPU, MPI, Linux, and `matrix_product_state` or
  `tensor_network` as the first circuit's method were not run, although the controller's loop names
  them.
- **Sampling on wide states.** `min(1, 2^k G)` was checked on one and three qubits. The sampler has a
  second branch for wide states, and it was not exercised for this law.
- **`BackendEstimatorV2` and the Aer estimator.** Not run.
- **A small trace deficit on the archived model.** Arm B alone sums to 0.999999997 on four of six
  layouts, in any order. It is unrelated to the factor, whose ratio to alone is exact, and its cause was
  not looked into (amendment 1 in the evidence README).

### Is it a bug

Our reading is yes. A noise channel multiplied by 2 is not a channel, the result depends on circuit
order within a run, and it raises nothing. We found no report: on 2026-11-05, ten keyword searches of
Qiskit/qiskit-aer's issues (their terms are in the implementation record) and a look at its recent
`bug` label turned up nothing matching, which is weaker than proof that none exists. PR #2500, merged
2026-10-28, fixes other defects in the same `enable_*` functions and does not touch
`quantum_error.hpp` or `matrix.hpp`.

Whether to report it upstream is the lead's decision; nothing has been posted.

## 3. What to do

- **Keep to one circuit per `run()` in anything simulated.** The per-shot seeding finding
  (`docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md`) says the same for another
  reason.
- **Treat a same-shot PUB list as one run.** `BackendSamplerV2` and the Aer sampler send those together.
  This includes `qiskit_ibm_runtime.SamplerV2` in local mode on a simulator.
- **Do not rely on a sum or a fidelity staying plausible.** When a density-matrix result matters, save
  its probabilities and check that they sum to 1, and record `metadata['method']` and `metadata['noise']`
  with the evidence. A run whose `noise` values show `kraus` before the first `superop` is the visible
  sign.
- **Forcing a method is a real escape**, but it changes what runs. A forced `density_matrix` on a
  12-qubit circuit is expensive, and a forced `statevector` samples noise per shot, which is where the
  seeding finding applies.

## 4. How we found it

A local rehearsal while planning #125 step 1d showed it. `probe_batching.py` isolated it: the batched
Arm B had `000` at 0.931 where alone it had 0.493, while the fidelity barely moved.
`probe_batch_scope.py` showed that the two circuits' methods differed. From there, reading Aer's source
gave the hypothesis, and the protocol in `docs/evidence/aer-batching-defect/README.md` was committed
before any script in that folder existed. The first run of the bridge script showed a sum alone that
missed the protocol's tolerance as written; that miss is recorded as amendment 1, not edited out.

## 5. Exposure in this repository

A run is exposed only if all four hold: (1) one `run()`, or one group of same-shot PUBs, holds more
than one circuit; (2) the method is automatic; (3) the model holds a `kraus` or `superop` instruction;
(4) a circuit given `statevector` or `matrix_product_state` precedes the first given `density_matrix`.

Two looks. `audit_aer_runs.py` parses every tracked `.py` and `.ipynb` on `main` at `5c98f264` and on
every other local and origin branch except `calibration-data`, 214 refs and 385 distinct files, none
unreadable, and lists every `run`, `execute` or `_run_circuits` call. `spy_aer_runs.py` wraps the point
every Aer execution passes and watched the whole test suite: **1,131 executions across 45 of 1,053
tests, every one holding exactly one circuit.** A positive control shows the spy does see a two-circuit
execution through `AerSimulator.run`, `BackendSamplerV2` and the Aer sampler, and the scan does list the
known batches in the probes. A search of all history for a list literal passed to `run` on a
simulator-like name finds two commits, `a917b19b` and `e91239fd`, both named below.

### On `main`: nothing exposed

| Where | Call | Why it is not exposed |
| --- | --- | --- |
| `src/superconducted/benchmarks/harness.py` (4 sites) | `sim.run(prepared_circuit)`, `sim.run(circuit.copy())`, `sim.run(state_circuit)` | Fails (1): one circuit per call, in loops. The harness has no production caller. |
| `scripts/first_ensemble_run.py` | `simulator.run(prepared_circuit)` | Fails (1). `compare_mf_placement.py` imports from it and adds no run. |
| `scripts/resolution_measurement.py` (2 sites) | `simulator.run(circuit)`, `simulator.run(state_circuit)` | Fails (1). So `docs/evidence/resolution-measurement/` is not affected. |
| `docs/evidence/aer-per-shot-seeding/seed_distance_and_jobs.py` and `within_job_overlap.py` | `run` with two circuits, on purpose | Fails (2) and (3): `method="statevector"` is forced, and the only noise is depolarizing. |
| `docs/evidence/aer-per-shot-seeding/` (other sites) | one circuit | Fails (1). |
| `tests/` | no direct `.run(` call; Aer is reached through the functions above | See the spy's result above. No test starts a Python subprocess that reaches Aer. |
| `poller.py`, `probe_historical_properties.py` | import `qiskit_ibm_runtime` for calibration reads | Execute no circuit. |

`qiskit.primitives`, `qiskit_aer.primitives`, `qiskit_experiments` and `mthree` are imported nowhere on
`main`. The remaining sites the scan lists are `con.execute` calls on DuckDB in
`docs/evidence/public-archive-overlap-2026-10/`, which involve no circuit.

### Register rows: none affected

Rows that rest on Aer-reaching code:

| Row | Producing code | Why it is not affected |
| --- | --- | --- |
| NC-001, NC-002, NC-003 | `scripts/first_ensemble_run.py` at `4006f6c` | Latencies, not counts; one circuit per `run()` at that commit, too. |
| NC-036 | `tests/training/test_aer_pin.py` | Compares `SuperOp` objects in Python; executes no circuit. |
| NC-095, NC-096 | `docs/evidence/aer-per-shot-seeding/` | Forced `statevector`, depolarizing noise only. |
| NC-021 | test collection | A count; nothing depends on simulated values. |
| NC-041 | `scripts/feature_distribution.py` | Names `first_ensemble_run.py` for its feature scales only; runs no circuit. |

Those are the rows citing Aer-reaching code, found by searching the register for each Aer-importing file
in the scan's section 1. A second keyword search of the register for simulation words lists 27 rows, and
reading those adds nothing that runs Aer: the rest match on words such as "snapshot", or describe a
statistical null simulated without Aer (NC-093).

### On other branches

| Where | Call | Finding |
| --- | --- | --- |
| `scripts/hardware_reading_vs_level.py` on `mert/issue-125-offline-half` (PR #140) and its descendants | `sim.run(c)` per circuit in `simulate_truth`; forced `density_matrix` in `shot_free_distribution` | Fails (1). So the dry run's committed outputs are not affected. |
| Older `harness.py` and `first_ensemble_run.py` on other branches | `sim.run(circuit)`, `sim.run(prepared_circ)`, `simulator.run(transpiled_circuit)` and similar | Fails (1). |
| This work's own scripts | batches, on purpose | They exist to show the defect. |
| `probe_batching.py`, `probe_batch_scope.py` on `mert/issue-125-submission` | batches, on purpose | They are the diagnosis. |
| `probe_arm_b_routes.py`, same branch | one circuit or one PUB | Fails (1). |
| `probe_local_mode.py`, same branch | `[zero, decayed]`, three active qubits each, 512 shots | Fails (4): by the rule both get `density_matrix`, and its `p_1` values near 1 confirm no pile-up on `000`. |
| **`probe_build_time.py`, same branch** | **`[arm_a[2], arm_b[0]]`, 256 shots, local mode** | **All four hold. Lines 21 and 22 of `probe_build_time.out.txt`, Arm B's counts `{'000': 242, '001': 1, '010': 12, '100': 1}` and "fidelity at 256 shots 0.473", are wrong.** |

**That one output is the only committed result this audit finds affected.** The conclusion comes from
the four conditions read off the probe's code and from the output's signature. The probe was not re-run:
its archive walk is slow, and `probe_batching.py` already measures an Arm A and an Arm B through the same
route. The probe printed those lines to show that local mode runs and what its
registers are called, and that part stands. Its timings and job metrics are unaffected. A search of
every ref finds the figures only in that probe and its output, so no document or register row quotes
them.

It does overtake one sentence. The 1d plan on that branch says no committed result is affected "as far
as that search reaches", and its search covered `src/` and `scripts/` only, not `docs/evidence/`.

### What the audit cannot see

The scan lists attribute calls named `run`, `execute` or `_run_circuits`. It would miss an alias such as
`f = sim.run` passed elsewhere; a separate search finds only `original_run = AerSimulator.run`, in a
test's spy on one call. It scans branch heads, not every historical version of a file. A result produced
by a script that was never committed is outside it.

## 6. Related

- NC-097, NC-098 in `docs/numerical-claims.md`
- `docs/evidence/aer-batching-defect/README.md` (protocol, predictions, amendments, runs)
- `docs/implementations/2026-11-05-aer-batching-defect.md`
- `docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md`, the sibling finding
- `docs/implementations/2026-11-05-hardware-test-submission.md`, on the branch
  `mert/issue-125-submission`
- Issue #125; Qiskit/qiskit-aer#2500
