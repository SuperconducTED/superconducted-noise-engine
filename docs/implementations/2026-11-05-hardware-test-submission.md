# 2026-11-05: the #125 hardware test, submission and scoring (step 1d)

> Status at this commit: **built, not frozen.** Criteria 1 to 7 hold on the laptop (provisional); 8 and
> 9 are open, and "Results" below says what each rests on. The plan was written before the code, as the
> project's rule asks, and is kept as written. The planning probes and the rehearsal are about the
> pipeline, not the device. Nothing here has touched the QPU or read the IBM token.

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

Completed as the work landed, 2026-11-06. The last row is still owed.

| File | One-sentence description |
| --- | --- |
| `docs/implementations/2026-11-05-hardware-test-submission.md` | This plan, then the record. |
| `docs/evidence/hardware-reading-vs-level/planning-probes-2026-11-05/` | The five probes behind this plan and their outputs; local only, nothing about the device. |
| `scripts/hardware_reading_vs_level.py` | Splits building a job from scoring it, so circuits and sealed forecasts exist at `t_s` and the execution control is added afterwards, and lets the block bootstrap's calendar reach empty days at either end. |
| `scripts/hardware_submit.py` | New: the `build`, `score` and `report` modes, the guards and the pinned options. |
| `scripts/hardware_t1_check.py` | New: design §6's `T1` check on the first and last jobs, run from its own environment. |
| `scripts/hardware_daily.py` | New: one morning of the run in order, each step a process with a time limit. |
| `scripts/hardware_schedule.ps1` | New: prints the Windows scheduled task, and registers it only when told to. |
| `tests/test_hardware_reading_vs_level.py` | Three tests for the split. |
| `tests/test_hardware_submit.py` | New: offline tests on `FakeFez` and synthetic documents, no token and no network. |
| `tests/test_hardware_t1_check.py` | New: the check's guards and bookkeeping on the pins, and its real fits where Qiskit Experiments is installed. |
| `tests/test_hardware_daily.py` | New: the morning's order on a scripted runner, and the watchdog on real processes. |
| `docs/roadmap/2026-10-24-issue-125-preregistration.md` | **Owed:** the dated amendments listed under "Owed to the pre-registration", on PR #135 on the lead's word. |

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

## What the build added to the plan, 2026-11-06

Written as the code landed. The plan above is not edited; where the two differ, this section is the
later one.

**The morning runs `build` first, not `score`.** The plan had `score` before the next `build`. `score`
walks the archive for minutes, so that order would have pushed every capture past 03:45, and `t_s` is the
capture instant. So `scripts/hardware_daily.py` runs `build`, then the `T1` check where one is due, then
scores earlier days, then rewrites the report. One consequence: "still queued at the next day's 03:45" is
acted on when the routine reaches that job, minutes after 03:45, and a job that started in those minutes
is scored normally.

**The strict missed rule is checked twice.** The rule is on submission, and a build takes minutes, so one
that began before 04:45 and finished after it is now recorded as missed at the moment of submitting.

**A `report` mode.** The plan's "the decision rule is applied once, after job 14" had no code. The first
day is declared with `--first-day`, not read from the folders, so a first day the laptop slept through
cannot move the calendar. A job folder outside the run's 14 days is refused, because the run is never
extended and a stray folder must not be dropped or scored in silence. Before day 15 the output is marked
interim. Three things stay visibly open in it: the block length is amendment 8's proposed 3 days, both
readings of "`level` or `band`" are printed, and A3 is a comparison of paired rows, so a row one predictor
cannot predict counts for neither side.

**The `T1` check runs its circuits itself.** Qiskit Experiments builds the circuits and fits the results,
but the job goes through the same device object and the same pinned options as the main job, in place of
the library's own `run()`. As far as the code read here goes, that `run()` submits and waits in one
process and writes no job id to disk, and a job can sit in a queue for hours, while this way the fit waits
for the next morning in a new process. Each `T1` circuit
has one classical register per qubit, so counts are joined across registers, with a test pinning the order
because a swap would quietly trade two qubits' fits. The check takes no part in the decision rule.

**A short calendar gives no interval.** With three days and three-day blocks, every draw holds all three
days, so the bootstrap's interval has zero width: the rehearsal's interim report showed exactly that. Such
an interval says nothing about uncertainty, so A1 and A2 cannot pass on it. The first interim day with a
real interval is day 4. The final report is not affected.

**The rehearsal's live document must be a new state.** The first attempt took the first archived file after
each `t_s`. Both repeated a state already in the archive, with no `T1` value changed, because `T1` often
does not change until many hours after 03:45 (`20261101T050830` against `20261101T033045`, and
`20261103T070610` against `20261103T032455`). That run passed every check it had while leaving the live path
untested, so the check now requires `reading` and the execution reading to differ. Also, 15 of the archive
tip's last 40 files have no `configuration` block. A real capture always has one, so only the rehearsal has
to pick around that.

**The watchdog is the routine's own design.** Each step is a process with a time limit, killed with its
children. Its output goes to a file and never to a pipe, because the hang of 2026-11-05 was a `MemoryError`
in a pipe's reader thread. The routine also asks Windows to stay awake, because a wake timer alone does not
keep an unattended machine from going back to sleep.

### Owed to the pre-registration

Not yet written there. These go in as dated amendments on PR #135, section 3.11, on the lead's word. None
changes a threshold or a null value. Numbered from 16 because amendment 15 is the last there today; if
Bengisu's review adds one first, these numbers move, so cite them by title until they land.

16. **`rep_delay`.** 500 µs with `init_qubits` on, refused at submission if outside the live range. The
    lead's decision, 2026-11-05.
17. **Options fixed explicitly.** Dynamical decoupling off, gate and measurement twirling off, classified
    measurement. Decoupling would put pulses inside Arm A's `delay`; twirling would change the circuits the
    forecasts were computed for.
18. **Missed and failed jobs.** Missed: not submitted by 04:45 UTC, including a build that began in time
    and finished late. Failed: an IBM error or cancellation, or still queued when the next morning's routine
    reaches it, when it is cancelled. No re-runs. The day stays on the calendar with no rows (amendment 8).
    The lead's decision, 2026-11-05.
19. **Always 14 days.** The scores are computed and visible daily (the lead's decision, 2026-11-05). The
    run neither stops early nor extends on what they show. **Added by this plan, flagged for the lead to
    confirm.**
20. **A selected qubit missing from the live target.** The job is refused and the day stays empty.
    **Open for the lead:** the pre-registration has no replacement rule, and writing one means choosing
    between an empty day and a selection that no longer follows the frozen rule. Refusing is the one that
    cannot bias the result.
21. **The `T1` check's delays.** The design fixes eight delays and 1,024 shots but not their spacing: evenly
    from 1 µs to three times the qubit's `level` `T1`.
22. **The status line the guard reads.** Section 1 says the freezing commit writes "Frozen at `<commit>`",
    which cannot name its own hash. The guard requires `**Status**: **Frozen` and
    `**Controls SHA-256**: <hash>`, with the frozen commit passed as `--frozen-at`.
23. **The first day is declared.** The run's first calendar day is written in the freezing commit and passed
    to `report`. Job `n` runs on day `n`, whatever happened before it.

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

## Results

Laptop, Windows, exact pins, 2026-11-06 Istanbul time, all provisional until Burak's run. The folder is
`docs/evidence/hardware-reading-vs-level/rehearsal-2026-11-06/`. **Every figure from the rehearsal describes
Aer, built from the very reading it is compared to. None is a result about the device, and none takes an
NC row.** In particular "S1 fails" in `report.json` is the expected output when the simulator's truth is the
reading, and it shows the rule's code reaching a verdict, not the verdict.

| # | Result | Rests on |
| --- | --- | --- |
| 1 | **Holds.** Every output file byte-identical to `dry-run-2026-11-05/`, and `compare_dry_run.py` exits 0. | Run twice: at `087b9c7e` right after the split, 49 minutes in a worktree of the partial clone, and at `3f062d4f`, the final code, 15.5 minutes from the full clone. |
| 2 | **Holds.** `build` at the dry run's instant gives the same selection, controls, slots and layouts, and names the same archive commit and controls hash. | `check.out.txt`, at `9745583e`. |
| 3 | **Holds.** Days 2026-11-02, 03 and 04 read scored, empty and scored. The empty day holds no folder and no rows, and both other days' rows reach the report: 112 discriminating and 56 control. Job 1 has no Arm B and job 3 has. | `check.out.txt`, `report.json`, `status.txt`. |
| 4 | **Holds.** Live documents stamped 20:18 on 11-02 and 11:29 on 11-04, against captures at 03:45. `reading` comes from them, the manifest names their hash, and `reading` differs from the execution reading on 60 and 66 of 84 rows. | `check.out.txt`. |
| 5 | **Holds.** 74 of 74 on `hardware_submit.py` and 56 of 60 on the routine and the check at `9745583e`. The other four, a stale pattern, a test that could not fail and two missing tests, were fixed in `3f062d4f` and re-ran caught, with one new mutant for the guard that commit added. | `mutation.out.txt`. |
| 6 | **Holds.** `test_the_token_reaches_the_service_and_no_file_a_job_writes` and its counterpart for the check. | Tests, mutation-checked. |
| 7 | **Holds.** `test_pinned_options_are_the_decided_ones_and_the_sampler_accepts_them`, the fast one-circuit spy and the slow batching test. | Tests, mutation-checked. The mutation run uses the spy; the batching test ran in the gates. |
| 8 | **Open.** The scheduled run has not fired. Registering a task needs the lead's word. | See "What the laptop allows". |
| 9 | **Open.** Gates are below. Burak's desktop run and its runbook are owed. | |

**The `T1` check on Aer.** All eight fits land within 1.7 standard errors of the `T1` the simulator was built
from, across qubits from 5.9 to 272 µs, so the bits reach the right qubits. Standard errors run from 2.9% to
10.5%. The library marked one fit `bad`, on the 5.9 µs qubit, whose fit still agreed. Whether a real fit's
error stays this small is what the check is for.

**The Aer defect.** The separate session's finding, which the correction above places on a local branch, is
now PR #141 (`mert/aer-batching-defect`), with Burak's runbook posted. Nothing here depends on its merging:
the rehearsal still sends one circuit per run.

**The real path refuses.** From the full clone, with no rehearsal flags and no `.env` present: no freeze
arguments, another commit named, and this commit named with the pre-registration absent all exit 2 with
their reason. So does the check, and the whole morning reports `build` as exit 2 and exits 1. That covers the
refusals, not a submission: the guard's passing case runs only against throwaway repositories in the tests.

**Time and memory.** Rehearsal stages on the laptop: `build` with Aer 3 min 27 s; morning 1 (`build`, Arm A on
Aer, the check) 4 min 14 s; morning 3 (`build`, both arms, scoring day 1, the fit) 6 min 17 s; 16.6 minutes
whole. Committed memory peaked at 37.2 of 39.1 GB, which counts everything else on the laptop and the
simulator. A real morning runs no simulator, but anyone rehearsing on this laptop should close other work
first.

### What the laptop allows

Read from `powercfg`, 2026-11-06, with nothing changed. Wake timers are on for mains power and off for
battery, so the laptop must stay plugged in. On mains it never sleeps from idling, though closing the lid may
still put it to sleep. Its only standby is S0 low power idle ("Modern Standby"). How a wake timer behaves in
that state is what criterion 8 tests, and it may not match the plan's picture of a sleeping laptop waking.
The zone is Turkey Standard Time, UTC+3, with no daylight saving. No `.env` exists under the project folder
yet, and the lead creates one before job 1, from `.env.example`, in the run's clone. That template names the
same three variables `ibm_device` and the poller read (`IBM_QUANTUM_TOKEN`, `IBM_QUANTUM_CHANNEL`,
`IBM_QUANTUM_INSTANCE`), and git ignores the file, so it does not trip the clean-tree guard.

### Not checked by any of this

- **The data branch.** `--commit-data` and `--push-data` have only run against a scripted runner, never a real
  `git` in a real `data/hardware-125` worktree, so the plan's step of committing each job's folder there is
  untested end to end. Turning on `--push-data` also means an unattended daily push, which is the lead's call
  when the task is registered.
- **Linux.** `_kill_tree`'s process-group path and the routine as a whole have run on Windows only.
- **The guard's passing case on the real command.** It runs only against throwaway repositories in the tests,
  because no frozen commit exists yet.
- **Anything the plan already lists:** the QPU, `job.inputs`, the live `rep_delay_range`, overhead and queue time.

### Gates

At `3f062d4f`, on the exact pins, with `PYTHONPATH=.;src`: `ruff check .` and `ruff format --check .` clean
(ruff 0.15.12); `check_ids.py` finds no duplicate or colliding identifier; `mypy --strict` clean on 52 files;
`pytest tests/` 1267 passed, 2 skipped, in 6 min 58 s. The two skipped need Qiskit Experiments, so CI will skip
them too. In the check's own environment `tests/test_hardware_t1_check.py` gives 38 passed. The batching test
on the pins alone gives 1 passed, 87 deselected.

## Related docs

- `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` (the design, §5, §6, §8)
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` on PR #135 (amendments 7, 8, 14, 15; §6.2)
- `docs/implementations/2026-10-28-hardware-test-offline-half.md` on PR #140
- `docs/roadmap/2026-10-23-phase-4-plan.md` §8 on PR #131 (step 1d, gates L1 and L2)
- `docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md` (the one-circuit-per-run rule)
- NC-026 (historical properties); Issue #125

## Decisions of 2026-11-07, and amendment 20's rule changed: plan, before its code

Appended; nothing above is edited. Where this section and "Owed to the pre-registration" differ, this one is
the later.

**Amendment 19 is accepted as drafted.** The lead confirmed it on 2026-11-07: always 14 days, nothing decided
on what the daily scores show. Its "flagged for the lead to confirm" no longer applies.

**Amendment 20 is replaced.** The draft refused the job when a selected qubit was missing from the live target,
and said refusing is the one choice that cannot bias the result. The lead chose a different rule after seeing
what follows.

**What was found.** Read from every capture on `calibration-data` at `fafbc8f5` with scratch scripts, on the
laptop, provisional, and to be re-run from a committed script before any figure here is cited in the
pre-registration. 2,706 captures over 170 UTC days:

- No qubit was ever absent from the `target` field's `x`, `sx` or `measure`. The draft's guard had nothing to
  fire on.
- `ibm_fez` marks a dead qubit by leaving it in the target with `x` and `sx` `gate_error` set to 1: qubit 72 on
  every capture, qubit 17 on 208 (05-13 to 05-18 and 06-22 to 07-13), qubit 149 on 6 (05-13). The draft's guard
  does not see this.
- What keeps them out today is proposal A's window floor, indirectly. Qubit 72 is admitted on 0 of 132 days at
  `w >= 15` (NC-088). Qubit 17's `T1` date stayed at 2026-04-13 through its dead span, so its window cannot have
  held many distinct values; this is inferred from the date field, and its window count was not computed.
- A qubit that dies during the run with a fresh `T1` would stay above the floor for about 15 days (about 30
  distinct values, floor 15), and frozen controls are never re-checked. The record has no example of this, so
  it is a gap in the rule, not a measured rate.

The draft's reason also needs correcting. It said a replacement "no longer follows the frozen rule", but nothing
is frozen yet, so a rule written now is the frozen rule. It reads only the device's status at `t_s`, never a
result, and treats `level` and `reading` alike. Arm B already drops dead `cz` links the same way (amendment 9).

**The rule, as the lead decided it.** A qubit is *not operational* at `t_s` when it is absent from the live
target's `x`, `sx` or `measure`, or when its `x` or `sx` `gate_error` in the live properties document is at least
1. Such a qubit gives no rows that morning, and the job is not refused on this ground:

- It is not a candidate for the discriminating stratum, so the frozen ranking runs over the remaining candidates
  and the next qubit by the same rule takes the place.
- A frozen control that is not operational is left out that day. It is not replaced, and the frozen set still
  stays out of the discriminating stratum. A3 uses the control rows that exist; if the whole run has none, A3 is
  not met.
- It is not eligible for an Arm B triple.
- The qubits affected are logged in that job's `selection.json`.

**What it does not cover.** A qubit that dies after `t_s` while the job is queued keeps its rows. A dead `measure`
is not a signal, because the record shows none and the device's marker is on `x` and `sx`.

**The change.**

- `scripts/hardware_reading_vs_level.py`: a new function `not_operational_qubits(properties, target)`. Inputs: the
  live document's `properties` and the live `Target`. Output: a sorted list of qubit indices. No side effects. A
  missing or null `gate_error` is not a dead signal. `build_job` uses it for Arm B's eligibility and for its own
  guard, which stays as the last check and still raises if it is handed such a qubit. With no live target, as in
  the dry run, nothing changes.
- `scripts/hardware_submit.py`: `run_build` removes the not-operational qubits' rows before `select_balanced`,
  passes the frozen set as `controls` to that call, passes the running controls to `build_job`, and logs
  `not_operational` and `controls_left_out`.
- `tests/test_hardware_submit.py`: `test_a_selected_qubit_missing_from_the_live_target_refuses_the_job` pinned the
  old rule, so it changes with it.

**Expected, written before the code.** Laptop results stay provisional until Burak's run.

| # | Criterion |
| --- | --- |
| 10 | The dry run's outputs stay identical to `dry-run-2026-11-05/`, checked with `compare_dry_run.py`, because the path with no live target does not change. |
| 11 | The rehearsal's checks all hold. Criterion 2's selection, controls, slots and layouts do not change, because qubit 72 is the only not-operational qubit expected on those mornings and the floor already excludes it. |
| 12 | A dead discriminating qubit gives way to the next by the same rule; the result equals the frozen rule applied to the remaining candidates. |
| 13 | A dead control is left out, the job still runs, no circuit uses it, the other three stay out of the discriminating stratum, and a run with no control rows does not meet A3. |
| 14 | Each signal is tested alone: absent from each of `x`, `sx` and `measure`, and `gate_error` 1 on each of `x` and `sx`. A `gate_error` just under 1, or a null one, is not a signal. |
| 15 | Every new line is mutation-checked: removing it fails a test, and each mutant asserts its pattern was found. |
| 16 | Gates clean on the exact pins. |

**Results so far, 2026-11-07.** Laptop, provisional.

| # | State | Evidence |
| --- | --- | --- |
| 10 | **Not run.** The dry run waits until the lead has freed memory: 0 to 1 GB of RAM and 5 to 9 GB of commit free today. | |
| 11 | **Not run**, for the same reason. | |
| 12 | **Holds.** `test_a_dead_discriminating_qubit_gives_way_to_the_next_by_the_same_rule`. | At `ea646d3d`. |
| 13 | **Holds.** `test_a_dead_control_is_left_out_and_the_job_still_runs`, `test_a_job_with_a_control_left_out_scores_on_the_rest`, `test_a_run_with_no_control_rows_does_not_meet_a3`, `test_a3_uses_the_control_rows_that_exist`. | At `ea646d3d`. |
| 14 | **Holds.** The tests named for each signal, including just under 1, null, missing, and another gate. | At `ea646d3d`. |
| 15 | **Holds.** 25 of 25 caught, each mutant asserting its pattern was found once. | `docs/evidence/hardware-reading-vs-level/not-operational-2026-11-07/`. |
| 16 | **Holds.** At `4595f3f2`: `ruff check .` and `ruff format --check .` clean, `check_ids.py` clean, `mypy --strict` clean on 52 files, `pytest tests/` 1285 passed, 2 skipped. It took 19 min 28 s against 6 min 58 s on 2026-11-06, because the laptop was also carrying other sessions' work. | |

Amendments 16 to 23 are not on PR #135 yet: a session was analysing that PR at `51e9f425` today, and the lead asked to
hold the push until it finishes. The wake test is not registered either, until the lead has freed memory.

## Criterion 8, first attempt, 2026-11-08

Appended; nothing above is edited.

Two one-off tasks were registered on the lead's word on 2026-11-07: the morning routine at 06:45 Istanbul with
its wake flag on, replaying the archived morning of 2026-11-02 in local mode from the full clone at `fa140cda`, and a
memory logger at the same time with its wake flag off, so the logger could not wake the machine and hide whether the
routine's own timer worked. Before registering, the exact command ran once awake (exit 0, 9.9 min with the laptop
loaded), and a throwaway task proved the Task Scheduler launch (exit 0). Laptop, provisional.

| What | Result |
| --- | --- |
| The routine fired unattended | **Yes.** Both tasks started at 06:45:00 and returned 0. The routine's first output is 06:45:10 and its last 06:49:21. |
| The routine's steps | `build`, `t1 submit` and `report` each exit 0. `not_operational` is `[72]`, the four controls all ran, none left out. |
| Memory on a quiet laptop | Commit used rose from 17.94 to a peak of 27.12 GB against a 42.14 GB limit; Python's private memory peaked at 9.92 GB; free RAM stayed at or above 4.96 GB. This is a simulated morning; a real one runs no simulator. |
| The laptop was asleep | **No.** The System log has no Kernel-Power sleep or standby transition (ids 42, 107, 506, 507) between 2026-11-07 21:00 and the read at 08:46; the last ones are from 2026-11-05 21:05. `powercfg /lastwake` shows no wake source. AC idle sleep is "never" in the current scheme, and the lid action does not show there. |

**Criterion 8 stays open.** What this attempt proves: Task Scheduler fires the routine at the hour with the app closed,
and the routine completes on its own. What it does not prove: that a sleeping laptop wakes for it, which is the part only
a sleep can test. Both tasks are unregistered, and the outputs stay in `C:\t\wake1` outside the repository.

## Criterion 8, second attempt, 2026-11-08: the wake timer does not wake this laptop

Appended. The first attempt could not test the wake, because the laptop never slept. This one used a deliberate sleep:
a one-off task, wake flag on, registered for 10:04 Istanbul with the same command and a new output folder, then the lead
chose Start, Power, Sleep. Read from the System log:

| Time, Istanbul | Event |
| --- | --- |
| 09:46:14 | Kernel-Power 506: entering Modern Standby, reason Screen Off Request |
| 10:04 | the task's start time: no event, no output |
| 10:24:20 | the task starts |
| 10:24:22 | Kernel-Power 507: exiting Modern Standby, reason Input Keyboard (the lead woke it) |

No Power-Troubleshooter event, and `powercfg /lastwake` shows no wake source. The task ran only because "start as soon
as possible after a missed start" fired it on resume. **Criterion 8 as written fails on this laptop:** in Modern Standby,
its only standby state, the task's wake timer does not wake it.

What the two attempts together show: with the laptop awake on mains, idle and logged in, the routine fires at the hour and
completes (06:45:00 on 2026-11-08, about 4.5 minutes); asleep, it does not fire until someone wakes it. A late start is not
a late submission: the strict missed rule (amendment 18) refuses a build after 04:45 UTC, so a sleeping morning becomes an
empty day, not a mistimed job. The way the run is fired is now the lead's decision.

**The lead's decision, 2026-11-08: the laptop stays awake.** For the 14 nights the laptop stays on mains, logged in,
lid open, and is never put to sleep; a locked screen is fine. Its power plan already never turns the display off or
sleeps on mains. A night it sleeps through is a missed morning under amendment 18, an empty day, never a late job.

**Criterion 8, restated.** The original wording ("fires unattended at 06:45 Istanbul with the laptop asleep") tested a
wake this laptop does not do. The restated criterion is: the routine fires unattended at 06:45 with the laptop awake on
mains, logged in, lid open and the app closed, and completes. The 2026-11-08 06:45 run meets it (first attempt above;
the lead confirmed the lid was open). This restatement is written after that run, so it is disclosed as such: the run was
set up to test the wake, and it is counted for the awake case it actually exercised. Still owed in the code:
`scripts/hardware_schedule.ps1` describes the wake timer as how the job is fired, and that text is corrected in stage 2.

## Stage 2 plan, 2026-11-08, before the code: the rule of PR #135's sections 3.11 and 3.12

Appended. The lead decided four rules on 2026-11-07 and two more on 2026-11-08; PR #135 now states them as amendments 16 to
35 (`d7909de3`). This section plans the code that applies them. Nothing above is edited. Three phases, each committed with
its tests before the next starts.

**Phase 2a, the decision rule in `report`.**

- **Sign.** Every comparison uses amendment 25's `D = |p_hat - p_level| - |p_hat - p_other|`, negative favouring `level`.
  Today's `_gaps` is `other - level`, positive favouring `level`, so `mean_difference` and `execution_gap` change sign. The
  flip is deliberate, and a test pins it on a hand-made row.
- **A1 and A2** by batch means: the declared 14-day calendar in batches of days 1-4, 5-8, 9-11, 12-14; a batch's value is the
  mean of `D` over its discriminating rows; empty batches dropped while at least three remain, `t` with `q - 1` degrees of
  freedom, critical values taken from SciPy's values written in the pre-registration, `sd = 0` fails. Block 3 stays in the
  output as a sensitivity, never in the decision.
- **A3** unchanged in meaning: the controls' mean `D` below zero against both readings.
- **A4** becomes descriptive: on `tau > 0` discriminating rows, coverage, widened coverage, mean width, and the no-information
  coverage of amendment 24 (each row's band moved in `log T1` by the difference to every other discriminating qubit's `log level`
  that day, turned into `p_1` at the row's `tau` with the row's own `level` readout). It leaves the S1 decision.
- **Arm B** by a paired Spearman difference: per Arm B job `rho_level - rho_reading`, jobs 2-5, 6-8, 9-11, 12-14, the same batch
  rule with the opposite side. "Or band" and B1, B2 leave the decision; best-pick hits, regret and near ties stay descriptive.
- **Minimum completed jobs:** at least 10 days with discriminating rows and at least 10 Arm B jobs, else inconclusive.
- **The reading** is amendment 29's two tables, first match top to bottom, as an `if` chain that names the row it chose.
- **`c` and `s_res`** as amendment 30 defines them, from each day's `sealed.json` sources and the `tau > 0` rows' counts.

**Phase 2b, sealing (amendment 27).** The jobs folder is the data branch's worktree (`--commit-data` runs `git add -A` there),
so a sealed file cannot live inside it. A new required `--sealed-dir`, refused when it is inside the jobs folder or the clone,
receives everything that reads as a score: raw counts, `arm-a.tsv`, `arm-b.json`, the scores part of the daily summary, the
interim report, and the `T1` fit. The jobs folder keeps the job ids, submissions, sealed forecasts, metrics, inputs read back,
and a new `operations.json` per day: status, QPU seconds, queue delay, row counts, and whether the `T1` check ran and its fit
converged. The routine prints only operations. On day 15 the routine copies the sealed folder into the jobs folder, so the
final commit holds everything. `hardware_schedule.ps1`'s description stops calling the wake timer the mechanism.

**Phase 2c, verification.** Mutation check of every new line, gates on the exact pins, then criteria 10 and 11 once.

**Criteria, written before the code.**

| # | Criterion |
| --- | --- |
| 17 | A hand-made row where `level` is closer gives a negative `D` and a negative `mean_difference` for A1 and A2. |
| 18 | Batch means reproduce `rule_values.py`'s statistic on the same day means (a test builds the rows from a known matrix and compares `t` to a direct computation), including `V2` with one empty batch and inconclusive with two. |
| 19 | With 9 completed days the report is inconclusive; with 10 it decides; the same for Arm B jobs. |
| 20 | A4 counts no `tau = 0` row, and its no-information coverage on a hand-made day equals a direct computation. |
| 21 | Each row of amendment 29's tables is reached by a constructed report, and the report names the row. |
| 22 | `c` and `s_res` recover a planted slope and spread on synthetic counts within their tolerance. |
| 23 | No file a morning writes inside the jobs folder holds a score, a count or a `T1` fit value (a test scans every file for the planted values); `--sealed-dir` inside the jobs folder or the clone is refused. |
| 24 | Day 15 copies the sealed folder into the jobs folder, and only then. |
| 25 | Every new line mutation-checked, each mutant asserting its pattern was found. |
| 26 | Gates clean on the exact pins; then criteria 10 and 11 re-run once, the rehearsal's checks updated for the sealed folder. |

**Stage 2, phases 2a and 2b done (2026-11-08).** `21e025d5` adds the statistics helpers with
`tests/test_hardware_report_rule.py` (each value checked against a direct computation); `c083377b` rewrites `run_report`
and `_arm_b_report` to decide by amendments 25 to 29 and report A4 and `c`, `s_res` as amendments 24 and 30 say, and turns
the tests that pinned the old rule into tests of the new one. Criteria 17 to 22 hold on the laptop; 184 tests pass across the
three hardware test files; `mypy --strict` is clean; `scripts/hardware_reading_vs_level.py` is untouched. Two points the
text left open were settled in code and written back to PR #135 as amendment 36: shortfalls apply per arm (too few Arm B
jobs leaves S1 readable), and an inconclusive Arm B adds nothing. The definitions the code pins: `D` is `level`'s absolute
error minus the other's; a day's batch index is its offset from the declared first day; Arm B job `j` is batch item `j - 2`;
the no-information band moves each row's band by `level_o / level_q` and uses the row's own `level` readout.

**Stage 2, phase 2c done (2026-11-08): the scores are sealed (amendment 27).** `950eed50`, with a follow-up `92f008ce`.

| File | What changed |
| --- | --- |
| `scripts/hardware_submit.py` | `score` writes `results.json`, `arm-a.tsv`, `arm-b.json` and `daily-summary.json` to `<sealed>/<day>` and leaves `operations.json` in the job folder, written last; `report` reads the sealed folder, writes `report.json` there and prints only its path; `--sealed-dir` is required and refused inside the jobs folder or the clone before any network (`refuse_sealed_inside`). |
| `scripts/hardware_t1_check.py` | `score` writes `t1-results.json` and `t1-check.json` to the sealed folder and leaves `t1-operations.json` (qubit count and fit quality counts, no value), written last. |
| `scripts/hardware_daily.py` | `--sealed-dir` is required, refused inside the jobs folder or the clone, and passed to every score and the report; `operations.json` and `t1-operations.json` are the scored markers, so the routine never reads the sealed folder; day 15 copies the sealed folder into `jobs/sealed` after the report and before the commit. |
| `scripts/hardware_schedule.ps1` | The wake timer is no longer described as how the run is fired: the laptop stays awake (the lead's decision above). |
| `tests/test_hardware_*.py` | The sealing tests below, and the old tests moved to the sealed layout. |

How a leak was looked for (criterion 23). A planted device returns counts whose values no other file holds: 1271 of 2048
ones on every Arm A circuit, so `p_hat` is `0.6206054688` as the TSV writes it (ten significant digits) and
`0.62060546875` as JSON would, and 2939 of 4096 on Arm B. The test gathers every score-derived value the sealed day holds
(`ones`, `p_hat`, each `abs_err_` and `log_score_` cell, Arm B's measured values, each summary figure), first shows that
each one is in the sealed folder, then looks for each, as a whole number (not inside a longer one), in every file of the jobs
folder and in what `score` printed. The `T1` check's test does the same with planted fits. The routine's log is each
step's stdout and stderr, so these tests cover only the stdout part; the rehearsal checks the log itself.

What came out of the review before the mutation pass (`92f008ce`): `t1-operations.json` had been written before
`t1-check.json`, so a write failing in between would have marked a day fitted with no fit and no later morning would have
scored it; `score` and the check's `score` refused a sealed folder inside the jobs folder but not inside the clone; and no
test called a command without `--sealed-dir`. All three fixed, each with a test that fails on `950eed50`.

One edge recorded, not changed. Amendment 27 ties the unseal to the date ("committed on day 15"), and the routine does that.
If job 14 is still running on day 15's morning, or the archive has no file after its execution yet, day 15 reports and
unseals without it and day 16 does nothing, so job 14 would have to be scored by hand and copied in by hand
(`unseal` copies with `dirs_exist_ok`, so running it again adds the day). Job 14 runs at 06:45 on day 14, a day earlier, so
this needs a job to run for a day or the archive to stop for a day. The lead may want a rule for it.

237 tests pass and 2 skip across the four hardware test files at `950eed50`; ruff, `ruff format`, `check_ids.py` and
`mypy --strict` are clean on the exact pins; `scripts/hardware_reading_vs_level.py` is identical to `999acee9`.

**Stage 2, phase 2d done (2026-11-09): mutation, gates, the dry run and the sealed rehearsal.** Commits `1e434118`
(tests for what the first mutation pass found), `47acd745` (the reading texts), `2514b260` and `5bafd1ba` (two more
tests and the mutation script's fixes), `55f05ea0` (the mutation record and the rehearsal scripts, committed before they
ran) and the commit that adds this record and the rehearsal's outputs.

| Criterion | Result | Evidence |
| --- | --- | --- |
| 17 to 22 | **Hold**, as recorded for phases 2a and 2b; every test kept passing through 2c and 2d. | `tests/test_hardware_report_rule.py`, `tests/test_hardware_submit.py` |
| 23 | **Holds.** Planted values in the unit tests, and on the real path the rehearsal's scan of every file, log, record, stdout and commit before day 15 (1,288 values and 7,530 raw count entries); `--sealed-dir` inside the jobs folder or the clone is refused before any network by the routine, `score` and the check's `score`; `report`, which takes no clone, refuses one inside the jobs folder, and the routine checks the clone before calling it. | `rehearsal-2026-11-08/check.out.txt`, `check.planted.out.txt` |
| 24 | **Holds.** Day 15 unseals after the report and before the commit, no earlier day does, a second unseal adds a day, and the rehearsal's day-15 commit holds the sealed folder byte for byte. | Tests; `rehearsal-2026-11-08/check.out.txt` |
| 25 | **Holds.** 598 mutants of every added line that can be changed alone (the 58 that cannot, closing brackets, `def`, `try` and `except` lines and comprehension parts, are listed in the record): 294 caught by an assertion, 292 by a crash (224 of them deletions), 12 survive, each equivalent for a stated reason. | `docs/evidence/hardware-reading-vs-level/mutation-2026-11-08/` |
| 26 | **Holds.** Gates at `5bafd1ba`: ruff, `ruff format --check`, `check_ids.py` and `mypy --strict` on 52 files clean, `pytest tests/` 1,378 passed and 2 skipped in 7 min 37 s. Then criterion 10 (the dry run identical, 8 of 8 files) and criterion 11 (the rehearsal's 66 checks) once each, at `55f05ea0`. | `rehearsal-2026-11-08/` |

What the mutation pass changed in the code, not only in the tests: the report's reading texts were paraphrases of
amendment 29 (the S1 pass had lost "A4 reports how well the band is calibrated; c and s_res (amendment 30) say how much
of the scatter is physical", the A3 failure "with no claim about the chip"); `47acd745` makes them the amendment's
words, Markdown backticks dropped, with a test against the tables as copied from #135 at `ae2f4884`. The row names are
unchanged. One row, "neither passes", is not in amendment 29's second table; with no row that applies, Arm B adds
nothing, as amendment 36 says for an inconclusive Arm B.

What the passes showed about the tests themselves: the first no-information fixture gave every row 0.5, so a row read
against the wrong qubit went unseen; the first pass could not tell an assertion from a crash, because pytest at 80
columns drops a long summary line's message; and two guard mutants were caught only because a later `git` call
crashed. Each is fixed and recorded in the mutation folder's README.

The rehearsal's checker was changed once after its first run, and the first output is kept (`check.out.first.txt`):
values that are fractions of shots appear both in scores and in a build's calibration copy and predictions, so the
second version excuses a hit only in a file whose bytes are those its build morning committed, before that day's counts
existed, and a planted-leak run shows it still catches a leak in a log, in `operations.json` and in a changed build
file. Two observations, neither changed: the rehearsal's simulator keeps its raw counts in `jobs/local-jobs/`, which a
rehearsal's data commit includes (a real run has no such folder); and `predictors.tsv` is written with CRLF while every
other build file is LF.

Laptop, provisional: Burak's desktop is the source of truth, and his runbook for #142 is owed after #140 merges. Nothing
of stage 2 is pushed yet; that, and #142's and #135's stale PR bodies, are stage 3, on the lead's word.

**As of 2026-11-09 morning:** stage 2 is pushed to #142 at `6f745934` and its body rewritten, both on the lead's word;
CI is green there. #135's body is still stale.

## Amendment 34 plan, 2026-11-09, before the code

Appended; nothing above is edited. PR #135's section 3.13 lists amendment 34 among those still to build ("24 to 30 and
34"). Stage 2 built 24 to 30 and 36, not 34; this was found while drafting #142's body. Amendment 34 (#135 at
`ae2f4884`): "A bad live document is a missed job. It stops the run (`LiveDocumentError`, exit 2), while a bad archived
document is counted and skipped; on a job day the first is a missed morning under amendment 18."

**What happens today**, reproduced at `6f745934` by the tests below before any code change. `run_build` saves the live
capture, then `predictor_rows` raises `LiveDocumentError` when the document names another device, names none, has
neither document shape, or its qubits do not parse. `main` catches only `RefusedError`, so the build ends in a
traceback with exit 1 and no `missed.json`. The day then holds no job, so the report counts it "empty", which is the
amendment's outcome. But the routine records exit 1, nothing names the day missed, and a second `build` the same day
would be allowed, against amendment 18's "no re-runs".

**The change.**

1. `run_build` catches `LiveDocumentError` from `predictor_rows`, writes `missed.json` with the reason ("the live
   document is unusable: " and the message) and the capture's time, and raises `RefusedError`. `main` then exits 2 and
   prints "refused: ...", as it does for a closed window; the routine records the build's exit 2, submits no `T1`
   check and still scores and reports. The saved live document stays, to show what was wrong.
2. `run_build` refuses a day that already holds `missed.json` before any capture: amendment 18 allows no re-run.

Nothing else changes. The good path is the same code, so the dry run (which never calls `run_build`) and the rehearsal
(whose live documents are good) are not re-run; the existing build tests stand for that path.

| # | Criterion |
| --- | --- |
| 27 | A live document that names another device, names none, has neither shape, or does not parse makes `build` record `missed.json` with its reason and time, submit nothing, write no `job_id.txt` or `submission.json`, keep `live-properties.json`, and raise `RefusedError`; the report reads the day "missed". |
| 28 | A day recorded missed is refused by a later `build` that day, before any capture, and nothing is submitted. |
| 29 | Every new line is mutation-checked, each mutant caught (by an assertion where it can be) or shown equivalent; the four hardware test files and the gates pass on the exact pins. |

**Amendment 34 done (2026-11-09).** Plan `a1e1b22a`, code and tests `48718a91`, one test tightened `8341e32d`.

| # | Result | Evidence |
| --- | --- | --- |
| 27 | **Holds.** The four bad documents (another device named, none named, neither shape, qubits that do not parse) each record `missed.json` with the reason and the capture's time, submit nothing, write no `job_id.txt` or `submission.json`, keep `live-properties.json`, and raise `RefusedError`; `_day_status` reads the day "missed". The five tests failed at `6f745934` with `LiveDocumentError` escaping `run_build`, before the code changed. | `test_a_bad_live_document_is_a_missed_morning` |
| 28 | **Holds.** After a bad document, a good one five minutes later that day is refused before any capture (`captures == 0`), and nothing is submitted. | `test_a_day_recorded_missed_is_not_built_again` |
| 29 | **Holds.** 11 mutants of the new lines, all caught: two by an assertion, nine by the crash each mutant makes (a missing name or argument, `rows` unbound, a path multiplied). Gates at `8341e32d`: ruff, `ruff format --check`, `check_ids.py` and `mypy --strict` on 52 files clean, `pytest tests/` 1,383 passed and 2 skipped in 7 min 2 s. | `docs/evidence/hardware-reading-vs-level/missed-live-2026-11-09/` |

The dry run and the rehearsal were not re-run: the dry run never calls `run_build`, and on a good live document
`run_build` runs the same code as before (the new guard finds no `missed.json` and the new `except` is not entered),
which every existing build test still passes.
