# Aer per-shot seeding, and what else building the #125 offline half taught us

**Date**: 2026-10-28 · **Author**: Mert Efe Şensoy (with Claude) · **Status**: findings, laptop,
provisional until a desktop rerun · **Register**: NC-095, NC-096 · **Evidence**:
`docs/evidence/aer-per-shot-seeding/`

## 1. Summary

While building the offline half of the #125 hardware test, its Aer dry run failed an
acceptance criterion for a reason outside our code. Qiskit Aer seeds every shot of a run from
the run's seed plus the shot's index, so two runs with nearby seeds replay each other's shots,
and the circuits of one job replay each other once shots pass 2,113. Each run's own
distribution is right; independence between runs, or between circuits of one job, is not.
Aer's maintainers know the per-run part (an open issue since 2023, labelled `bug`) and have not
documented it; we found no report of the within-job part. Nothing registered in this project is
affected. The rest of this note records the other simulator and pipeline facts the same work
turned up, because each one would cost the next person a day.

## 2. The finding: Aer reuses random streams across nearby seeds

### What happens

When Aer simulates shots one by one, shot `j` of a run with seed `s` gets the random stream of
seed `s + j` (Aer 0.17.2, `src/simulators/circuit_executor.hpp`:
`rng.set_seed(circ.seed + shot_index)`). Runs with seeds `s` and `s + d` therefore share
`shots - d` of their shots exactly, shifted by `d`. Separately, circuit `k` of one `run()` call
gets seed `seed + 2113 k` (`src/controllers/controller_execute.hpp`), so with more than 2,113
shots neighbouring circuits of one job share streams too, whether or not a seed was given.

Measured on the laptop with the committed scripts (NC-095, NC-096):

- One qubit, seeds 500 and 501, 512 shots: 511 of 511 shifted shots identical; aligned
  agreement 282 of 512, which is chance.
- Seed distance 1, 100 and 511 at 512 shots: shifted agreement 1.000 over 511, 412 and 1 shots;
  distance 600: no overlap, chance agreement.
- Two circuits in one job at seed 7000: Aer reports seeds 7000 and 9113, and at 2,500 shots the
  second circuit replays the first from shot 2,113 on, 387 of 387. Two different circuits at
  4,000 shots: correlation 0.741 between shifted shots, -0.012 aligned.
- Twenty runs of a 4-qubit circuit with consecutive seeds: per-qubit z-scores spread by 0.03 to
  0.06 where about 1 is expected; spaced seeds and `SeedSequence` draws spread by about 1.

### When it happens, and when it does not

Only on the per-shot path, which Aer reports as `measure_sampling: False` in each result's
metadata. That covers noise sampled per shot under the `statevector`, `stabilizer` and
`matrix_product_state` methods, resets, and mid-circuit measurements. On the measure-sampling
path, where Aer evolves one state and draws every shot from it, nothing is shared. Aer's
`automatic` method often picks `density_matrix` with measure sampling for small noisy circuits,
which is why a first one-qubit check of ours saw no replay. The number of threads does not
matter: the same seed gives identical shots at 1, 3 or 20 parallel shot streams, which is the
reason Aer seeds by shot index. Unseeded separate runs draw independent random seeds and are
safe.

### Is it a bug

Our reading, with the sources:

- **The per-run reuse is intended and undocumented.** A maintainer described the scheme in the
  open issue [Qiskit/qiskit-aer#1916](https://github.com/Qiskit/qiskit-aer/issues/1916) (opened
  2023-08-24, label `bug`, no fix), said it keeps results identical across thread counts, and
  said it should be documented. Aer's API pages and release notes do not mention it as of
  2026-10-28. A user who loops `seed + i` gets correlated runs without any warning.
- **The within-job overlap is closer to a defect.** In an older issue (#585, closed) Aer's
  maintainers say circuits of one job should sample independently, which the 2,113 offset breaks
  once shots exceed 2,113. We found no report of it.
- Not checked: Aer 0.18.x (the latest release, 0.18.2, appeared 2026-10-26), the GPU and MPI
  paths, and shot branching.

Whether to report the within-job overlap upstream is the lead's decision; nothing has been
posted.

### How we found it

The offline half's dry run (branch `mert/issue-125-offline-half`, record
`docs/implementations/2026-10-28-hardware-test-offline-half.md`) simulates seven Arm A circuits
and checks, as criterion 2, that the matching predictor's mean error equals a derived offset
within three standard errors. The criterion assumes independent rows. Two scratch runs failed it
by the same amount. We named the cause wrongly twice (a shared seed, then parallel shots) before
a sweep over seed bases showed the statistic's spread was far above 1, a per-row check showed
consecutive seeds barely moved each row, and a direct comparison showed seed 501's shots were
seed 500's shifted by one. An independent check by a subagent, reproduced here from committed
scripts, found the mechanism and its boundary. The record discloses every step, in amendments
committed before the record run.

### What to do

- Draw seeds from `numpy.random.SeedSequence`, spread them across the 32-bit range, and check
  that any two are further apart than the shot span (`circuit_seeds` in
  `scripts/hardware_reading_vs_level.py` refuses pairs closer than ten times the largest shot
  count).
- Submit one circuit per `run()` when circuits must be independent, or keep shots at or below
  2,113 per circuit in one job.
- Record `results[i].seed_simulator`, `metadata['method']` and `metadata['measure_sampling']`
  with any simulated evidence, so the path taken is on file.

### Exposure in this repository

A side session audited every seeded Aer counts run on `main` on 2026-10-28 (report uncommitted,
branch `claude/suspicious-newton-b361ca`): **no registered row rests on a replayed sample.** The
benchmark harness has no production caller, and every seeded call that exists, in tests and in
`scripts/resolution_measurement.py`, runs on the measure-sampling path. It is latently exposed:
`benchmarks/harness.py` seeds ensemble member `i` at `seed + i`, which would replay at 12 qubits
and the default 4,096 shots, at very small shot counts, or with a mid-circuit measurement. The
same audit reports a separate design point: the harness runs the reference at the same seed as
member 0, which couples their samples even with measure sampling. Both fixes are proposed there,
not applied.

## 3. Other simulator facts the same work established

Each is recorded with its check in the offline-half record (branch
`mert/issue-125-offline-half`); none is a registered figure.

- **`NoiseModel.from_backend_properties` cannot read our archive.** The archived properties
  carry no qubit `frequency`, which it reads even at zero temperature. A backend rebuilt from
  the archived `configuration` and `properties` through `qiskit_ibm_runtime`'s
  `convert_to_target` works with `from_backend`.
- **`from_backend` damps `delay` only through a custom pass.** It appends a
  `RelaxationNoisePass` to the noise model's private `_custom_noise_passes` list; there is no
  public way to add one, so our builder appends to the same list on the pinned Aer.
- **`from_backend` applies a symmetric readout error**, IBM's `readout_error`, which is the mean
  of `prob_meas0_prep1` and `prob_meas1_prep0`. A prediction that uses the two assignment
  probabilities separately differs from it by a known offset, which our dry run derives per row
  instead of tolerating.
- **Aer caps `T2` at `2 T1` without a word.** A qubit whose `T2` exceeds twice its `T1` passes
  through `from_backend`, and its relaxation pass carries `T2 = 2 T1`. ADR-027 rejects such a
  qubit instead; our builder follows ADR-027 and the dry run counts the capped qubits.
- **`ibm_fez` measures all 156 qubits at once** (one `meas_map` group) and its `dt` is 4 ns.
  Circuits that end several delays at one measurement must align them so no qubit idles after
  its delay; Arm A's circuits do, and a test checks every interval on the scheduled circuit.
- **Some `ibm_fez` couplings report `cz` `gate_error = 1.0`** (dead pairs, for example 32 to 33
  in the snapshot of 2026-10-23). A depolarizing channel cannot carry them; Arm B forms its
  triples only over usable pairs.

## 4. Pipeline lessons from the same session

- **A recorded file hash must be the hash a checkout sees.** Python writes text with CRLF on
  Windows, the repository stores LF, so a hash taken at write time named bytes no clone
  reproduces. Both #125 scripts now write JSON with `newline="\n"` (PR #132, `bbde9522`).
- **A mutant that is not applied looks like a surviving mutant, or like a killed one.** A shell
  `sed` with a doubled backslash silently matched nothing; the mutation check was redone from a
  script file. Check that the pattern was found before reading the test result.
- **A test fixture can violate the rule it tests.** Two of our own fixtures were wrong (a tie
  order and a coverage value); the code was right both times. Read a failing new test's
  expectation before touching the code.
- **A control can be equal by fact, not by construction.** The dry run's execution-time reading
  came from the same calibration as the submission-time one, because IBM did not recalibrate in
  between. The control's code ran; its values were never tested against a different reading.
- **Determinism on one machine is checkable and was checked**: the dry run repeated from the
  same code gave seven identical output files. Across platforms it is not yet checked.

## 5. Related

- NC-095, NC-096 in `docs/numerical-claims.md`
- `docs/evidence/aer-per-shot-seeding/README.md` (scripts, protocol, runs)
- `docs/implementations/2026-10-28-hardware-test-offline-half.md` and
  `docs/implementations/2026-10-28-hardware-test-selection-rules.md` (on their branches)
- Qiskit/qiskit-aer#1916, #585
- Issue #125; ADR-027 in `docs/decisions.md`
