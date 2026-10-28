# Aer per-shot seeding: reproduction scripts

Protocol written 2026-10-28 before these scripts were run from this folder. They were first
written and run by a subagent in a session scratchpad the same day; that run is not evidence.
The figures this folder supports come only from the runs recorded in section 3, made from the
committed copies.

## 1. The question

Qiskit Aer 0.17.2 seeds shot `j` of a run with seed `s` as `s + j` when it simulates shots one
by one (`src/simulators/circuit_executor.hpp`, `rng.set_seed(circ.seed + shot_index)`;
Qiskit/qiskit-aer#1916), and seeds circuit `k` of one `run()` as `seed + 2113 k`
(`src/controllers/controller_execute.hpp`). These scripts check what that does to samples.
The finding and what it means for this project are in
`docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md`.

## 2. Scripts and what each must show

Every check is differential: a shifted comparison against an aligned one and against a far
seed, never an absolute value. "Replay" means a shifted agreement of exactly 1 while the aligned
agreement sits at the chance level of the outcome distribution.

| Script | Checks | Replay looks like | No replay looks like |
| --- | --- | --- | --- |
| `reproduce.py` | one qubit, `h` with depolarizing noise, `method="statevector"`, seeds 500 and 501, 512 shots | 511 of 511 shifted matches | about half |
| `boundary.py` | the same pair of seeds (125, 126) on six configurations that differ only in the execution path; prints Aer's `measure_sampling` flag | shift 1.000 exactly when `measure_sampling` is False | shift near 0.5 when it is True |
| `seed_distance_and_jobs.py` | seed distance `d` (1, 100, 511, 600); two circuits in one job (seed 7000, 2,500 shots); unseeded runs; the same seed across thread settings; per-qubit z-score spread over 20 seeds, consecutive against spaced against `SeedSequence` | exact reuse over `512 - d` shots; circuit 1 equals circuit 0 shifted by 2,113; consecutive seeds' z spread far below 1 | spaced and `SeedSequence` spreads near 1 |
| `within_job_overlap.py` | two circuits in one unseeded job; two different circuits (`ry(1.0)`, `ry(1.3)`) in one seeded job of 4,000 shots; a null check of far-apart seed pairs | shifted correlation far above the aligned one | both near zero |

## 3. Runs

Interpreter `C:/t/pin125/Scripts/python.exe` (Python 3.12.10, Qiskit 2.4.1, Qiskit Aer 0.17.2,
NumPy 2.4.4), from the repository root, laptop, provisional. Outputs beside each script as
`<script>.out.txt`. Run 2026-10-28 from commit `a917b19b` (this protocol and the scripts), each
with `python -W ignore -I docs/evidence/aer-per-shot-seeding/<script>.py`; all four exited 0.

| Script | Result | Register |
| --- | --- | --- |
| `reproduce.py` | 511 of 511 shifted shots identical; 282 of 512 aligned (chance at p = 0.5); `measure_sampling: False`, `parallel_shots: 20` | NC-095 |
| `boundary.py` | shift 1.000 on exactly the two configurations with `measure_sampling: False` (`statevector` with `h` plus depolarizing, `statevector` with `x` plus thermal relaxation); 0.522 to 0.523 on the four with `measure_sampling: True` (`automatic`, which chose `density_matrix`; no noise; `density_matrix`) | NC-095 |
| `seed_distance_and_jobs.py` | seed distance 1, 100, 511: shifted agreement 1.000 over 511, 412 and 1 shots; 600: aligned 0.010 (chance 0.004). Two circuits in one job, seed 7000: reported seeds 7000 and 9113, circuit 1 shot `j` equals circuit 0 shot `j + 2113` on 387 of 387. Unseeded runs: random seeds, aligned 0.002, best shift 0.014. Same seed at 20, 1 and 3 parallel shot streams: memory identical. z-score spread over 20 runs (4 qubits, 2,048 shots): consecutive seeds 0.027 to 0.063, seeds 2,049 apart 0.977 to 1.203, `SeedSequence` 0.705 to 1.112 | NC-095, NC-096 |
| `within_job_overlap.py` | unseeded job: seeds differ by exactly 2113, 1.000 shifted over 387 shots; `ry(1.0)` and `ry(1.3)` in one job, seed 11, 4,000 shots: correlation 0.741 between circuit 0 shot `j + 2113` and circuit 1 shot `j` over 1,887 shots, against -0.012 aligned; null over ten far-apart pairs 0.0043 (chance 0.0039) | NC-096 |

Every seeded figure matches the subagent's scratch run; the unseeded runs drew different random
seeds, as they should, and show the same 2,113 offset.
