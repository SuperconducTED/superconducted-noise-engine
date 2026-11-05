# 2026-11-05: the #125 hardware test, submission and scoring (step 1d)

> Status at this commit: **plan, no script code yet.** Written before the code, as the project's rule
> asks, with the lead's decisions of 2026-11-05 and the acceptance criteria fixed in advance. The
> planning probes it cites are committed beside the offline half's evidence and are not results about
> the device. Nothing here has touched the QPU or read the IBM token.

## Problem / Motivation

The hardware test (#125) has its selection rules on `main` (PR #132), its offline half and Aer dry run
in review (PR #140) and its pre-registration in review (PR #135). Nothing can yet send a job to
`ibm_fez`, read the result back or score it. Pre-registration amendment 7 assigns this step the
`build` and `score` modes, `rep_delay`, `init_qubits` and design §6's `T1` characterisation, and §6 of
that document lists it as one of the things the freezing commit waits on.

Reading the code for this plan found gaps that amendment 7 did not name:

1. `build_job` needs the execution-time rows, which cannot exist before the job runs.
2. The pre-registration never pins dynamical decoupling or twirling. Decoupling would put pulses inside
   Arm A's `delay` if it were ever on.
3. It scores "a missed or failed job" as an empty day and never says what one is.
4. The live-properties path had never run end to end: the dry run passes `live=None`. A probe has now
   run it with the latest archived state fed as the live document, and none of the 780 rows differ, but
   that state was already in the archive, so a genuinely new state is still untested (criterion 4).

## What changed

Planned. The table is completed as the work lands.

| File | One-sentence description |
| --- | --- |
| `docs/implementations/2026-11-05-hardware-test-submission.md` | This plan, then the record. |
| `docs/evidence/hardware-reading-vs-level/planning-probes-2026-11-05/` | The five probes behind this plan and their outputs; local only, nothing about the device. |
| `scripts/hardware_reading_vs_level.py` | Splits building a job from scoring it, so circuits and sealed forecasts exist at `t_s` and the execution control is added afterwards. |
| `scripts/hardware_submit.py` | New: the `build` and `score` modes, the guards and the pinned options. |
| `tests/test_hardware_submit.py` | New: offline tests on `FakeFez` and synthetic documents, no token and no network. |
| `docs/roadmap/2026-10-24-issue-125-preregistration.md` | Dated amendments for what this plan fixes, on its own PR or at the freezing commit. |

## Implementation approach

**The daily routine.** Forecasts are sealed before the job runs and opened after it.

`build`, at `t_s` = 03:45 UTC (06:45 Istanbul), in this order:

1. Fetch the `calibration-data` tip; its commit is that job's archive ref. Run from a full clone: the
   archive walk is about 97% of the work. It took 517 s and 533 s in two runs in a worktree of the
   laptop's partial clone, while the whole `--mode controls` step, which walks the same archive, took
   122 s from a full clone in the rehearsal of PR #140's runbook. Every other step together took 13 s.
2. Capture the live `backend.properties()` and the live target, and write them to the job folder with
   their SHA-256. This is the `reading` the pre-registration's §2 names.
3. Run the predictors with that document, select qubits, and build circuits against the **live** target,
   so a coupler disabled overnight cannot produce a non-ISA `cz`. Validate with the Runtime's own
   `validate_isa_circuits`.
4. Fix the Sampler options explicitly: decoupling off, gate and measurement twirling off,
   `init_qubits` on, `rep_delay` 500 µs (refused if outside the live `rep_delay_range`), classified
   measurement, a job tag. Defaults are never relied on, because they can change between versions.
5. Submit in job mode, one job, seven PUBs on job 1 (Arm A only) and thirteen after that. Write the job
   id to disk before anything else, then the manifest: archive ref, live document's hash, options, the
   live `rep_delay_range`, code commit, `t_s` and `t_submit`.

`score`, the next morning before the next `build`:

1. Fetch the job's status, results, `metrics()` (`timestamps.running` is `t_execute`, `usage` is the QPU
   time) and `job.inputs`, which on job 1 confirms the options IBM actually received.
2. Fetch `calibration-data`, refuse unless its latest file is later than `t_execute`, and compute the
   `reading_at_execution` control from the file at or before `t_execute`. Save
   `backend.properties(datetime=t_execute)` beside it as an unscored cross-check.
3. Score both arms with the offline half's existing functions. Arm A's register is `c` and Arm B's is
   `meas`, so the scorer reads each circuit's own register and a test pins it.
4. Commit the raw results and the scores to the data branch below.

**Where the outputs live.** The run's worktree stays pinned at the freezing commit, because the guard
requires it. Each job's folder is committed to a dedicated branch, `data/hardware-125`, touching nothing
else, and merges with the PR that records L2.

**Guards, in the code and not in a checklist.** Any backend other than a local simulator is refused
unless `HEAD` is the commit passed as `--frozen-at`, the tree is clean, the pre-registration's status
line at that commit reads Frozen, and the controls file's hash matches the one it names. A second
submission for one UTC day is refused. The token is read from `.env` and never logged, and a test
scans every file a job writes for a fake token's value.

**The `T1` check** (design §6) is a separate job right after the main one on the first and last jobs,
using Qiskit Experiments in its own environment with its version recorded, and the same `rep_delay`.

**Rehearsal without the QPU.** IBM's local testing mode, `SamplerV2(mode=AerSimulator.from_backend(...))`
on a backend rebuilt from an archived snapshot, runs the whole `build` and `score` cycle. A later
archived snapshot plays the live document, so the live path sees a genuinely new state. Two limits are
known from the probes and are designed around:

- **It ignores the options.** Local mode warns that decoupling, twirling, `rep_delay` and `init_qubits`
  have no effect there, so a rehearsal cannot prove they apply. A unit test pins what is sent, and job 1
  reads them back from `job.inputs`.
- **Aer can corrupt a batched run.** See "A defect in Aer" below. The rehearsal sends each PUB as its own
  local job, keeping the rule the dry run already follows, and a test compares a batched Arm B to the
  same circuit run alone, so a change in this behaviour is seen.

**Stacking and merge order.** The branch sits on `mert/issue-125-offline-half` because it imports from
it, takes `main` after #140 merges, and opens its PR then. The freezing commit cannot land before #140,
this PR and #135 have merged, and those wait on Burak and Bengisu. So section 8.4 of the phase-4 plan's
target of L1 in the week of 2026-11-04 is no longer realistic, and this plan sets the real floor.

## Mathematical / Statistical details

**Shot time per job.** With `dt` 4 ns, `measure` 1.56 µs and `x` 24 ns, and the delays of the committed
dry run (longest per slot 0, 85.3, 170.6, 341.3, 110.7, 221.4 and 442.8 µs):
`T_A = sum over the 7 slots of 2048 x (longest delay + x + measure + rep_delay)`, and
`T_B = 6 x 4096 x (idle + gates + measure + rep_delay)`, with idle and gates taken as about 100 µs.

| `rep_delay` | Arm A | Arm B | Both | 14 jobs, job 1 Arm A only |
| --- | --- | --- | --- | --- |
| 250 µs | 6.4 s | about 8.6 s | about 15.1 s | about 3.4 min |
| 500 µs | 10.0 s | about 14.8 s | about 24.8 s | about 5.5 min |

This is shot time only, an estimate from one day's delays. Per-circuit and per-job overhead is unknown
until job 1 measures it. The lead has said the budget is not a constraint, so nothing gates on it, but
the design's own figure for the Open Plan is 10 minutes per window, and overhead could make the margin
narrow. Job 1's report states it.

**Why `rep_delay` matters at all.** A shot that ends in `|1>` relaxes during `rep_delay`, then
`init_qubits` resets it. What survives is about `exp(-rep_delay / T1)` times the reset's error. It raises
`p_1` by the same amount for every predictor, and the zero-delay slot shows it directly. At 500 µs the
excited fraction before the reset is at most about 8% for `T1` up to 200 µs, against up to about 29% at
250 µs. The lead chose the cleaner start at the cost of about 65% more shot time.

**Interim looks and no early stop.** The scores are computed daily (lead's decision). The decision rule
is still applied once, after job 14, to all rows. Repeatedly testing and stopping when a result looks
good would inflate the false-positive rate beyond the null values of the pre-registration's §3.8, so the
run is always 14 days, with no early stop and no extension based on the scores. A change during the run
is a dated amendment that reports both the frozen and the amended rule, as §1 of that document requires.

## Design decisions

**The lead's decisions, 2026-11-05.** Each goes into the pre-registration as a dated amendment.

| Question | Decision | Note |
| --- | --- | --- |
| `rep_delay` | 500 µs, the bundled configuration's maximum, with `init_qubits` on | Checked against the live range at every `build`. |
| Missed or failed job | Strict, no re-runs | Missed: not submitted by 04:45 UTC. Failed: an IBM error or cancellation, or still queued at the next day's 03:45, when it is cancelled. That day stays empty under amendment 8. |
| What fires the job | The laptop, scheduled | Task Scheduler with a wake timer, a full clone and a watchdog; the token stays in `.env`. |
| Scores during the run | Computed and visible every day | The safeguard below was added by this plan, not asked for: flagged for the lead to confirm. |

**Decided by this plan, open to the lead's objection:**

- **No early stop or extension,** as above. Daily scoring without it would bias the result.
- **The control's source is the archive,** as in the dry run, with IBM's historical read saved as an
  unscored cross-check.
- **Decoupling and twirling are off,** because the test measures the bare decay and layout.
- **The `T1` check stays as the design says,** separate job and separate environment. Version 0.14.2's
  stated requirements (`qiskit>=1.3`, `qiskit-ibm-runtime>=0.34`) fit the pins; it has not been installed.

**Alternatives set aside.**

- *Starting `build` before 03:45 so the job leaves on the minute.* A full clone leaves about two minutes
  between capture and submission. `t_s` is the capture instant and `t_submit` is logged.
- *A session instead of one job.* Nothing is adaptive between circuits, so job mode is enough.
- *GitHub Actions.* No laptop needed, and the poller already uses a repo secret there, but it breaks the
  lead's rule on the token and gives CI the power to spend QPU time.

**Risks named.** The laptop must be plugged in and reachable every morning for 14 days. A hung run looks
exactly like a working one, which cost two hours on 2026-11-05, so the watchdog is part of the routine.
On that day the laptop's committed memory also reached 33.2 of 34.7 GB during an Aer dry run, though
`build` itself used about 3 GB and simulates no truth. A missed morning is an empty day by the rule above. The second account is
still to be named, before job 2.

### A defect in Aer found while planning

On Aer 0.17.2, in one `run()` with noise and the default automatic method, a circuit Aer simulates by
density matrix gives a wrong result if a circuit it simulates by statevector came first. An Arm B GHZ
that gives `000` 0.49 and `111` 0.08 alone gives `000` 0.93 to 0.96 and `111` 0.000 after an Arm A
circuit. The reverse order, Arm B alone, and six Arm B circuits together are all correct, and so are
seven Arm A circuits together within shot noise. Forcing `method="statevector"` removes it, and so does
removing the noise.

**What it does not reach.** The QPU runs no Aer. The committed dry run runs one circuit per `run()`
(`simulate_truth`). A search of `src/` and `scripts/` at `2aea1e18` finds no `run()` given a list of
circuits, and the calls read there pass one circuit each. So no committed result is affected, as far as
that search reaches. Local mode shows the defect when one job's PUBs share a shot count. A job with Arm A
at 2,048 and Arm B at 4,096 was correct, apparently because those go to separate runs, and this plan does
not rely on that. The mechanism inside Aer is not established, and no minimal reproduction outside this
project's circuits exists yet.

**Correction, later on 2026-11-05.** "No committed result is affected" above was too wide, and so was
the same claim in `e91239fd`'s message. Lines 21 and 22 of `probe_build_time.out.txt`, committed with this
plan, are the defect's own output: that probe sends `job.arm_a[2]` and `job.arm_b[0]` to one local job at
one shot count, so its `000` 242 of 256 and fidelity 0.473 are wrong. The file stays as run, because it is
how the defect was first seen, and this plan quotes neither figure. A separate session has since reduced
the defect to a small script and traced the code path. Its finding is on branch
`claude/recursing-northcutt-28be4c`, not pushed as of this note, and it supersedes the last sentence above.

## Verification

Written before the code. Step 1d is ready for the freezing commit when all of these hold. Laptop
results are provisional until Burak's run.

| # | Criterion |
| --- | --- |
| 1 | After the split, the dry run's command gives output identical to `dry-run-2026-11-05/`, checked with `compare_dry_run.py`. |
| 2 | `build` at a past instant, in local mode, gives the same selection, slots and layouts as the dry run on the same inputs. |
| 3 | The whole cycle runs on three consecutive archived days, one of them missing, and scoring keeps the missing day as an empty day. |
| 4 | With a later snapshot as the live document, `reading` comes from it, and the manifest names its hash. |
| 5 | Every guard is mutation-checked: removing each one fails a test. Includes `HEAD` not at the frozen commit, a dirty tree, the status line not reading Frozen, a second job in one day, and `rep_delay` out of range. |
| 6 | A fake token's value appears in no file a job writes. |
| 7 | The options sent are pinned by a test, and the batching guard fails if a batched Arm B stops matching the same circuit alone. |
| 8 | A scheduled local-mode run fires unattended at 06:45 Istanbul with the laptop asleep, from the full clone, with its watchdog. |
| 9 | Gates clean on the exact pins; Burak reproduces criteria 1 to 7 on the desktop with a runbook, no token needed. |

On job 1, reported at L1: QPU seconds, `job.inputs` against the options sent, the zero-delay slot's
`p_1` against the readout errors, and queue delay.

The probes, from the branch root with `PYTHONPATH=.;src`, using the folder
`docs/evidence/hardware-reading-vs-level/planning-probes-2026-11-05/`. Each `<name>.py` has its output in
`<name>.out.txt`:

- `probe_local_mode.py <manifest.json>`: Arm A through the ISA check and local mode, with the shot-time table.
- `probe_build_time.py <controls.json>`: build timing, the live path, Arm B's ISA check, and job metrics.
- `probe_arm_b_routes.py`: one Arm B circuit through five routes.
- `probe_batching.py` and `probe_batch_scope.py`: the defect and how far it reaches.

**Not checked:** anything on the QPU, what `job.inputs` holds on a real job, the live `rep_delay_range`,
real overhead and queue time, Linux or Burak's desktop.

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, §5, §6, §8)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` on PR #135 (amendments 7, 8, 14, 15; §6.2)
- `docs/implementations/2026-10-28-hardware-test-offline-half.md` on PR #140
- `docs/roadmap/2026-10-23-phase-4-plan.md` §8 on PR #131 (step 1d, gates L1 and L2)
- `docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md` (the one-circuit-per-run rule)
- NC-026 (historical properties); Issue #125
