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
`<script>.out.txt`. To be filled after the runs.
