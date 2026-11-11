# Issue #64 PR-A1: check scripts and their runs

These scripts were first written and run in a session scratch folder on 2026-11-11, while steps
1, 2, 4 and 5 of the plan were built. Those runs are not evidence. The scripts were committed at
`95c2d69f` with no output beside them, and every `*.out.txt` in this folder comes from a run of the
committed copy made after that commit. The plan and the results they support are in
`docs/implementations/2026-11-09-issue-64-pr-a1-perturbation-and-band.md`.

Laptop, provisional: nothing here has run on Burak's desktop.

## 1. What this folder answers

Criterion 11 of the plan: every new guard is mutation-checked, with predictions written before the
run and each mutant caught or shown equivalent. It also holds the measurements behind three choices
the code makes (numpy's quantile at `alpha = 0`, the density-matrix tolerances, how often Aer
serialises a noise model).

It does **not** yet hold the acceptance run of criterion 8. That run needs
`InputVectorPerturbation` (step 3), which waits on decision D6 (#64 comment 6789691655).

## 2. Scripts and what each must show

A mutation script applies one exact, asserted text replacement at a time to a source file, runs one
test file, and restores the source from a backup copy outside the repository, never with git. Its
predictions are in its docstring. "Killed" means the test file failed.

| Script | Step | What it checks | A pass looks like |
| --- | --- | --- | --- |
| `capture_identity_pin.py` | 1 | prints the values the identity pin holds, and that spawning seed sequences draws nothing from the caller's stream | seed 1; three identical `crisp_params`; `stream untouched by spawn: True` |
| `mutate_step1_identity_pin.py` | 1 | 2 mutants, on a checkout of `75b86dbb`: M1 scales every model's `crisp_params` in `_compute_crisp_params`; M2 scales members 1 and later inside the old `__iter__`, which step 2 replaced (the script's docstring says both edit `__iter__`; only M2 does) | M1 fails the literal pin only; M2 fails the relational, literal and density-matrix pins |
| `mutate_step2_seeding.py` | 2 | 16 mutants of the ensemble's seeding and of `IdentityPerturbation` | all killed |
| `quantile_probe.py` | 4 | 20,000 random tables: the 0 and 1 quantiles are exactly min and max under `linear`; no disorder; three summations of seven sevenths | zeros on the first line; `numpy.sum` below 1.0, `math.fsum` exactly 1.0 |
| `methods_probe.py` | 4 | the same min/max equality for each of numpy's 13 methods, 3,000 tables each | `0 of 3000` thirteen times |
| `tolerance_probe.py` | 4 | how close 10 real Aer density matrices come to the two tolerances in `metrics.py` (`1e-12`, `1e-9`) | a worst case far below both |
| `mutate_step4_band_and_coverage.py` | 4 | 32 mutants of `interval_band`, `IntervalBand` and `IntervalCoverage` | all killed |
| `mutate_step4_c05b.py` | 4 | the mutant C05 was meant to be: a plain `numpy.sum` of covered probabilities | killed by the sevenths identity case |
| `mutate_step4_negative_count.py` | 4 | the negative-count refusal removed | killed by both negative-count tests |
| `to_dict_probe.py` | 5 | how many times one Aer run calls `NoiseModel.to_dict`, over methods, shot counts and ways of passing the model | 1 everywhere with a noise model, 0 without |
| `aer_mutant_plugin.py` | 5 | not run directly: a pytest plugin that makes Aer serialise once more per run, or once more per shot, for one session | |
| `mutate_step5_guard.py` | 5 | the guard tests against those two simulated behaviours | 13 pass unchanged; 10 of 13 fail under each |
| `mutate_step5_counts.py` | 5 | that the two simulated behaviours differ: the call count in a 1024-shot run | 1, 2 and 1025 |

## 3. Runs

Interpreter `C:/t/pin125/Scripts/python.exe` (Python 3.12.10, NumPy 2.4.4, Qiskit 2.4.1, qiskit-aer
0.17.2, pytest 9.0.3), installed from the pins. Run on 2026-11-11 from commit `95c2d69f`, from the
repository root unless stated, each output redirected to `<script>.out.txt`. All exited 0, and
`git status` showed no modified source file afterwards.

```bash
E=docs/evidence/issue-64-pr-a1-acceptance
PYTHONPATH=".;src" python $E/capture_identity_pin.py
python $E/quantile_probe.py
python $E/methods_probe.py
PYTHONPATH=".;src" python $E/tolerance_probe.py
python $E/to_dict_probe.py
python $E/mutate_step2_seeding.py <python> <backup dir>
python $E/mutate_step4_band_and_coverage.py <python> <backup dir>
python $E/mutate_step4_c05b.py <python> <backup dir>
python $E/mutate_step4_negative_count.py <python> <backup dir>
python $E/mutate_step5_guard.py <python> $E
python $E/mutate_step5_counts.py <python> $E
# in a checkout of 75b86dbb, with this folder's script given by its full path:
python <repository>/$E/mutate_step1_identity_pin.py <python> <backup dir>
```

`<python>` is the interpreter's path, `<backup dir>` any directory outside the repository. On Linux
or macOS write `PYTHONPATH=".:src"`.

| Script | Result |
| --- | --- |
| `capture_identity_pin.py` | viable seed 1; three members at `(0.0010631876854835232, 0.018299147946441743)`; stream untouched |
| `mutate_step1_identity_pin.py` | baseline 5 passed; M1 killed by the literal pin only; M2 killed by the relational, literal and density-matrix pins. Both as predicted. |
| `mutate_step2_seeding.py` | baseline 32 passed; 16 of 16 killed |
| `quantile_probe.py` | 0 tables off min, 0 off max, 0 disordered; `numpy.sum` 0.9999999999999998, `math.fsum` 1.0, built-in `sum` 1.0 |
| `methods_probe.py` | `0 of 3000` for all 13 methods |
| `tolerance_probe.py` | most negative diagonal entry 0; largest imaginary part 9.4e-18; largest distance of the trace from 1, 2.4e-15 |
| `mutate_step4_band_and_coverage.py` | baseline 75 passed; 32 of 32 killed |
| `mutate_step4_c05b.py` | killed, by the sevenths identity case among others |
| `mutate_step4_negative_count.py` | baseline 75 passed; killed by both negative-count tests |
| `to_dict_probe.py` | 1 call in each of the 12 runs, in the state-mode run and in the two-circuit run; 0 without a noise model |
| `mutate_step5_guard.py` | 13 passed unchanged; 10 failed under `extra`; 10 failed under `per_shot` |
| `mutate_step5_counts.py` | 1, 2 and 1025 calls, under both methods |

The step 4 mutation run here is on the test file as it stands at `95c2d69f` (75 cases). Its first,
scratch run was on 61 cases, before a negative count was refused and before the min/max test ran
for every method.

## 4. Predictions that missed, and one check that was wrong

Recorded because each says something about the tests or about the check.

- **C05** (step 4). Predicted: summing the covered probabilities fails the seven-sevenths identity
  case. It did not: the mutant used Python's built-in `sum`, which on Python 3.12 is a compensated
  sum for floats and returns 1.0 there. The mutant died on the case whose trace is `1 + 1e-10`.
  `mutate_step4_c05b.py` is the mutant that was meant, and it fails the predicted case.
- **B05** (step 4). Predicted: removing `interval_band`'s member-count check survives for a single
  member, because `IntervalBand` repeats the check with the same message. It was killed, by the
  empty-list half of the same test. The one-member half is covered twice on purpose.
- **The per-shot simulation** (step 5). Its first version read the shot count from the assembled
  circuits, where it is 1, so it made one extra call per run and was the same mutant as `extra`.
  Both failed the same ten tests, which hid it. `mutate_step5_counts.py` was written to print the
  counts and showed 2 where 1025 was claimed. The plugin in this folder is the corrected one.

## 5. Limits

- Laptop only. The figures are provisional until the desktop repeats them.
- `tolerance_probe.py` looks at 10 matrices. It shows the two tolerances are not tight on those; it
  does not show that nothing can reach them.
- `to_dict_probe.py` counts Python-level calls of one method. It says nothing about what the C++
  controller does per shot, and would not see a future Aer that read the model another way.
- The ordering and nesting checks of `quantile_probe.py` were run for the `linear` method only.
