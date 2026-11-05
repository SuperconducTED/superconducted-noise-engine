# Aer batching defect: protocol and runs

Protocol written 2026-11-05, committed before any script in this folder exists and before any
number below was measured. The only measurements that exist at this commit are the two planning
probes this work starts from, `probe_batching.py` and `probe_batch_scope.py` with their outputs,
on the local branch `mert/issue-125-submission` (`e91239fd`). Corrections after this commit go in
section 8 as dated amendments; nothing in sections 1 to 6 is edited afterwards.

## 1. The question

On Qiskit Aer 0.17.2, in one `AerSimulator.run()` with a noise model and the default automatic
method, a circuit Aer simulates by density matrix gives a wrong result if a circuit it simulates
by statevector came first. The planning probes show it on this project's circuits (an Arm B GHZ
gives `000` 0.493 and `111` 0.077 alone, and `000` 0.931 and `111` 0.000 after an Arm A circuit).
Nobody has reduced it, and nobody knows why it happens.

This folder answers four things: the smallest trigger, using only `qiskit` and `qiskit-aer`; what
each ingredient (qubits, noise, first circuit, shots) contributes; whether a mechanism can be
established from outside the compiled library; and whether anything in this repository is exposed.

## 2. Hypothesis, from reading the source

This is a reading, not a finding. Aer 0.17.2, tag `0.17.2`, commit `51c67981`:

1. `src/controllers/aer_controller.hpp:804-809`, `automatic_simulation_method`: with quantum errors
   in the model, a circuit gets `density_matrix` when it has fewer than 30 qubits,
   `shots > 2^num_qubits`, and `circ.can_sample`. Otherwise `stabilizer` if valid, then
   `statevector`.
2. `src/controllers/aer_controller.hpp:751-771`, `simulation_methods`: looping over the circuits of
   one run before executing any, the first density-matrix circuit calls `enable_superop_method`,
   and a statevector circuit calls `enable_kraus_method` if the model's opset contains `kraus` or
   `superop`. The noise model is shared by the whole run.
3. `src/noise/quantum_error.hpp:422-430`, `compute_kraus`: computes the superoperator only if it is
   empty, then converts.
4. `src/noise/quantum_error.hpp:493-508`, `compute_circuits_superoperator`:
   `superoperator_.initialize(dim, dim)`, then `superoperator_ += probabilities_[j] * ...`.
5. `src/framework/matrix.hpp:441-450`, `matrix::initialize`: reallocates and zeroes only if the
   dimensions changed. With the same dimensions it keeps the old contents.
6. `src/noise/noise_model.hpp:434-470`: each `enable_*` guards on its own method only, so the Kraus
   path having computed a superoperator does not stop the superoperator path computing it again.

Read together: when the first statevector circuit precedes the first density-matrix circuit, every
circuit-form quantum error's superoperator is computed twice with no zeroing between, so it becomes
`2S` where `S` is the channel. Each noise location in a density-matrix circuit then multiplies the
state by 2. A circuit with `k` noise locations ends with trace `2^k`.

Read further: `src/simulators/statevector/qubitvector.hpp:2149-2177`, `sample_measure`, walks the
outcomes in integer order and stops when a running sum of probabilities passes a random number in
`[0, 1)`. Nothing renormalises. So with cumulative true distribution `G`, the sampled cumulative
distribution is `min(1, 2^k G)`, and once `2^k p(00...0) >= 1` every shot lands on the all-zeros
outcome. Readout error is applied to the samples afterwards, which would explain `000` at 0.93 to
0.96 and `111` at exactly 0.000 rather than `000` at 1.000.

A generator-form error (`compute_generators_superoperator`, `quantum_error.hpp:511-534`) starts
from `superoperator_ = iden` and does not accumulate, so it should not double. This is the sharpest
test of the reading, because it predicts two different results from two code branches.

The same lines are unchanged on tag `0.18.2` and on `main` as read on 2026-11-05. Reading is not
running; a run on a newer version is outside this protocol unless an amendment adds it.

## 3. Predictions

`S_k` is one qubit with `k` `x` gates and `save_probabilities` and no measurement. `F_n` is `n`
qubits with `rz(0.3)` on each and `measure_all`. The model, unless a row says otherwise, is
`amplitude_damping_error(0.1)` on `x`. Default 2,048 shots. "Sum" is the sum of `S_k`'s saved
probabilities. Sums must hold to a relative `1e-9`. "Method" is Aer's reported
`metadata['method']`: SV is `statevector`, DM is `density_matrix`. Sampled rows must hold within
four binomial standard errors.

### A. The trace law

| Row | Circuits in one run | Predicted method | Predicted |
| --- | --- | --- | --- |
| A1 | `[F_11, S_1]` | SV, DM | sum 2 |
| A2 | `[F_11, S_2]` | SV, DM | sum 4 |
| A3 | `[F_11, S_3]` | SV, DM | sum 8 |
| A4 | `[F_11, S_0]` | SV, DM | sum 1 |
| A5 | `[S_1, F_11]` | DM, SV | sum 1 |
| A6 | `S_1` alone | DM | sum 1 |
| A7 | `h(0) cx(0,1) x(0)`, `save_density_matrix`, after `F_11` against alone | SV, DM | every element is 2 times alone, to `1e-9` |
| A8 | as A7 with a second `x(0)` | SV, DM | every element is 4 times alone, to `1e-9` |
| A9 | `x`, measure, `amplitude_damping_error(g)`, `g` in 0.05, 0.1, 0.2, alone then after `F_11` | DM | `P(0)` is `g` alone and `2g` after, sampled |

### B. Which noise

Every row runs `[F_11, S_1]` with the named error on `x`. Rule: the sum is 2 exactly when an error in
the model has a `kraus` instruction (checked from `to_dict()`, printed), and 1 otherwise.

| Row | Noise | Predicted sum |
| --- | --- | --- |
| B1 | `depolarizing_error(0.1, 1)` | 1 |
| B2 | `pauli_error` X with 0.1 | 1 |
| B3 | `reset_error(0.1)` | 1 |
| B4 | `thermal_relaxation_error`, T2 below T1 (100, 80 us, 50 ns) | 1 |
| B5 | `mixed_unitary_error` | 1 |
| B6 | `coherent_unitary_error` | 1 |
| B7 | `amplitude_damping_error(0.1)` | 2 |
| B8 | `phase_damping_error(0.1)` | 2 |
| B9 | `thermal_relaxation_error`, T2 above T1 (100, 150 us, 50 ns) | 2 |
| B10 | `depolarizing_error` on `x`, and `amplitude_damping_error` on a `cz` no circuit uses | 2 |
| B11 | readout error only | 1 |
| B12 | `PauliLindbladError` X, Z on `x` only | 1 |
| B13 | `PauliLindbladError` on `x`, and `amplitude_damping_error` on an unused `cz` | 1, the generator branch |
| B14 | `amplitude_damping_error` on `x` and `PauliLindbladError` on `y`; second circuit `x y`, saved | 2, only the circuit-form error doubles |

### C. The first circuit

| Row | First circuit, then `S_1` | Predicted method of first | Predicted sum |
| --- | --- | --- | --- |
| C1 | `F_n`, `n` from 1 to 10 | DM | 1 |
| C2 | `F_n`, `n` from 11 to 13 | SV | 2 |
| C3 | 11 qubits, `measure_all` and no gates | SV | 2 |
| C4 | 11 qubits, `x` on each, `measure_all` | SV | 2 |
| C5 | width 20, `rz` on one qubit, that one measured | DM | 1 |
| C6 | width 20, `rz` on 12 qubits, those 12 measured | SV | 2 |
| C7 | width 20, `rz` on 12 qubits, one measured | DM | 1 |
| C8 | one qubit, `x`, measure, `x`, measure (so `can_sample` is false) | SV | 2 |

C8 is the predicted smallest trigger at ordinary shots: two one-qubit circuits.

### D. Shots and the second circuit

Prediction: with both circuits sampleable, the defect exists exactly when
`2^n2 < shots <= 2^n1`, where `n1` and `n2` are the two circuits' active qubit counts.

| Row | Circuits | Shots | Predicted method | Predicted sum |
| --- | --- | --- | --- | --- |
| D1 | `[F_11, S_1]` | 2,048 | SV, DM | 2 |
| D2 | `[F_11, S_1]` | 2,049 | DM, DM | 1 |
| D3 | `[F_3, S_1]` | 8 | SV, DM | 2 |
| D4 | `[F_3, S_1]` | 9 | DM, DM | 1 |
| D5 | `[F_2, S_1]` | 2 | SV, SV | 1 |
| D6 | `[F_2, S_1]` | 3 | SV, DM | 2 |
| D7 | `[F_2, S_1]` | 4 | SV, DM | 2 |
| D8 | `[F_2, S_1]` | 5 | DM, DM | 1 |
| D9 | `[F_12, ten-qubit S_1]` | 2,048 | SV, DM | 2 |
| D10 | `[F_12, eleven-qubit S_1]` | 2,048 | SV, SV | 1 |

### E. Order, scope and escapes

| Row | Setup | Predicted |
| --- | --- | --- |
| E1 | `[S_1, F_11, S_2]` | sums 1 and 1: the first DM circuit precedes the first SV one |
| E2 | `[F_11, S_1, S_2]` | sums 2 and 4 |
| E3 | `S_1` alone on the same simulator object, after a batched run | sum 1: nothing persists between runs |
| E4 | 11 qubits with noisy `x` gates and `measure_all`, alone against first in `[.., S_1]`, same seed | identical counts: the statevector circuit is unharmed |
| E5 | `[F_11, S_1]`, `method="statevector"` | methods SV, SV; sum 1 |
| E6 | `[F_11, S_1]`, `method="density_matrix"` | methods DM, DM; sum 1 |
| E7 | `[F_11, S_1]`, `method="automatic"` given explicitly | sum 2 |
| E8 | `[F_11, S_1]`, no noise model | sum 1 |
| E9 | `[F_11, S_1]`, `max_parallel_threads=1` | sum 2 |
| E10 | `[F_11, S_1]`, the error local to `x` on qubit 0 | sum 2 |
| E11 | `[F_11, S_1]`, 12 local errors, one per qubit, so Aer's conversion loop runs in parallel | sum 2 |

### F. Primitives

`S_m` is `x` then `measure_all`, with `amplitude_damping_error(0.1)`, so true `P(0)` is 0.1. Qiskit's
`BackendSamplerV2._run` groups PUBs by shot count and sends each group to one `backend.run` call
(`qiskit/primitives/backend_sampler_v2.py:165-178`).

| Row | Route | Predicted |
| --- | --- | --- |
| F1 | `BackendSamplerV2` on the simulator, PUBs `[F_11, S_m]`, same shots | `P(0)` 0.2 |
| F2 | `BackendSamplerV2`, `F_11` at 2,048 and `S_m` at 4,096 | `P(0)` 0.1: separate runs |
| F3 | `qiskit_aer.primitives.SamplerV2`, same shots | `P(0)` 0.2 |
| F4 | `qiskit_aer.primitives.SamplerV2`, 2,048 and 4,096 | `P(0)` 0.1 |

### G. The original symptom

A three-qubit GHZ, `h cx cx`, with amplitude damping 0.05 on each noisy gate (tensored on `cx`), so
`k = 3`, and symmetric readout error 0.02 on each qubit, after `F_12`.

| Row | Setup | Predicted |
| --- | --- | --- |
| G1 | alone against `method="density_matrix"` alone | identical counts: the automatic method chooses DM and is right |
| G2 | after `F_12` | `000` is `0.98^3`, sampled; `111` has no counts |
| G3 | after `F_12`, readout error removed | `000` on every shot, Hellinger fidelity to ideal GHZ exactly 0.5 |

### H. Bridge back to this project

`bridge_arm_b.py` needs `scripts/hardware_reading_vs_level.py`, so it runs from a throwaway worktree
of `mert/issue-125-submission`. It is the one script here that uses project code, and it exists only
to tie the minimal defect to the one the probes found.

| Row | Check | Predicted |
| --- | --- | --- |
| H1 | re-run `probe_batching.py` | its committed `.out.txt` to the digit |
| H2 | Arm B with `save_probabilities` after Arm A; alone; reversed | alone and reversed sum 1; after Arm A the sum is `2^k`, with `k` the count of noise locations Aer places on Arm B, an exact integer power |
| H3 | a public fake backend through `AerSimulator.from_backend`, a 12-qubit circuit then a 3-qubit GHZ | same defect: no project code needed to reach it from a fake backend |

## 4. Decision rule

**Trigger.** The script states as established only the rows that were run and met. A missed row is
reported as missed, and the claim it supported is withdrawn or restated from what was measured. The
prediction is not edited.

**Mechanism.** "The source reading agrees with the behaviour" may be written only if all of A, B, C,
D and E hold, including the `2^k` law to `1e-9` and the generator rows B12 to B14. If any of those
rows miss, the doc says the mechanism is not established and states the black-box trigger alone.

Even if every row holds, the doc does not say the cause is proven. No Aer was rebuilt with
`matrix::initialize` zeroing, so the code path and the numbers it predicts agree, and that is all.

## 5. Audit method and rule

**Exposure is a conjunction.** A run is exposed only if all of these hold:

1. one `run()`, or one group of same-shot PUBs, holds more than one circuit;
2. the method is automatic, whether by default or explicitly;
3. the noise model contains a `kraus` or `superop` instruction;
4. a circuit Aer gives `statevector` or `matrix_product_state` precedes the first circuit it gives
   `density_matrix`.

**Two independent looks.**

- `audit_aer_runs.py`, static, standard library only: walks every tracked `.py` and `.ipynb` of a git
  ref, parses it, and lists every call to a `run`, `execute` or `_run_circuits` attribute other than
  `subprocess.run`, with its first argument, plus every import of `qiskit_aer`,
  `qiskit.primitives`, `qiskit_ibm_runtime`, `qiskit_experiments` or `mthree`. It runs on `main` and on
  every other local and origin branch, except `calibration-data`; call sites are deduplicated across
  refs. Each site is then read and classified by hand in the findings doc.
- `spy_aer_runs.py`, dynamic: a pytest plugin that wraps `AerBackend._execute_circuits_job`, the
  point every execution passes, and records for each execution how many circuits it held, the method,
  and whether a noise model was present. It runs over `tests/` on `main`. Any subprocess a test starts
  is outside its reach, and those are listed from the static scan.

**Rule.** "Not affected" may be said of a result only if the row's producing script is classified and
fails at least one conjunct, and the doc names which. A site that cannot be classified is reported as
unknown.

## 6. Register plan

Decided before the numbers.

- **NC-097**, one row: the defect's shape, meaning the factor `2^k`, the shot window, and the symptom
  on the Arm B GHZ.
- **NC-098**, one row, only if the findings doc states the spy's counts as a conclusion: Aer executions
  seen in the test suite at the audited commit, and how many held more than one circuit. It is a dated
  anchor, not a current value.
- Nothing else. The next free id on every branch was NC-097 when this protocol was written (highest
  id 096, by a scan of every local and origin ref), and is rechecked before the row is written.

## 7. Commands

Interpreter `C:/t/pin125/Scripts/python.exe` (Python 3.12.10, Qiskit 2.4.1, Qiskit Aer 0.17.2, NumPy
2.4.4, qiskit-ibm-runtime 0.46.1), from the repository root. `-I` makes an accidental project import
fail rather than pass.

```bash
python -W ignore -I docs/evidence/aer-batching-defect/minimal_reproduction.py
```

```bash
python -W ignore -I docs/evidence/aer-batching-defect/trigger_sweep.py
```

Each run takes seconds to a few minutes, so no stall watchdog is planned for these two; the test-suite
run under the spy gets one if it passes 15 minutes. Laptop results are provisional until a desktop
rerun.

## 8. Amendments

### Amendment 1, 2026-11-05: H2's tolerance, after seeing data, not blind

Section 3 says sums must hold to a relative `1e-9`. The first run of `bridge_arm_b.py` (from commit
`cd7d9650`, output not kept) printed Arm B's sum alone as 0.999999997 on four of six layouts, and its
sum after Arm A as `1024` to nine figures. Read literally, H2's "alone sums 1" therefore misses that
tolerance by about `3e-9`, on a circuit that has no defect in it. The miss is recorded here and stands.

The alone state on the archived `ibm_fez` model has a trace just below 1 in any order, which is a
different quantity from the factor the law is about. So the law's check on project circuits is
restated as a new measurement: the ratio of the sum after Arm A to the sum alone, which should be
exactly `2^k`. `bridge_arm_b.py` now prints that ratio and twelve decimals; no prediction in section 3
is edited. The cause of the `3e-9` was not looked into.

## 9. Runs

None yet.
