# 2026-11-05: aer-batching-defect

## Problem / Motivation

While planning #125 step 1d, a local rehearsal showed that one `AerSimulator.run()` could give a wrong
result without any error: an Arm B GHZ with `000` at 0.49 alone had `000` at 0.93 after an Arm A
circuit. The fidelity moved so little that a batched rehearsal or analysis would have passed unnoticed.
The defect had no minimal reproduction and no known mechanism, and whether it had already touched a
committed result had been searched only in `src/` and `scripts/`, for lists passed directly to `run`.
This work reduces it, tests a mechanism, audits the repository, and records all of it. It changes no
project code.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/aer-batching-defect/README.md` | Protocol and predictions committed before any number, two dated amendments, and the record of every run. |
| `docs/evidence/aer-batching-defect/minimal_reproduction.py` | The smallest reproduction, using only `qiskit` and `qiskit-aer`. |
| `docs/evidence/aer-batching-defect/trigger_sweep.py` | Every prediction as one printed row with its measured value, exiting 1 if any row misses. |
| `docs/evidence/aer-batching-defect/bridge_arm_b.py` | Ties the minimal defect to the probes' circuits and to a public fake backend; the only script here using project code. |
| `docs/evidence/aer-batching-defect/audit_aer_runs.py` | Static scan, standard library only, of every `run`, `execute` and `_run_circuits` call on `main` and every other branch. |
| `docs/evidence/aer-batching-defect/spy_aer_runs.py` | A pytest plugin recording how many circuits each Aer execution holds. |
| `docs/evidence/aer-batching-defect/spy_positive_control.py` | Shows the spy sees a two-circuit execution by each route, so its zero means something. |
| `docs/evidence/aer-batching-defect/compare_source.py` | Compares the functions the mechanism reading names across Aer `0.17.2`, `0.18.2` and `main`. |
| `docs/evidence/aer-batching-defect/*.out.txt` | The output of each script above, from the committed copies. |
| `docs/findings/2026-11-05-aer-batching-defect.md` | The finding: the defect, its smallest trigger, what is and is not established, and the exposure audit. |
| `docs/numerical-claims.md` | Adds NC-097 (the defect's shape) and NC-098 (the audit's counts). |

## Implementation approach

**Hypothesis before measurement.** Aer's source at the pinned tag was read first, because it was cheap
and it could produce falsifiable predictions where a blind sweep could only produce a table. The reading
went into the README as a hypothesis with its file and line references, and its predictions went in row
by row, before any script existed. Each later script then either met a row or visibly missed it. The
commits show that order: `97c6940c` (protocol), `880aa3be` and `cd7d9650` (scripts, unrun), then the runs.

**Differential checks.** Each row compares a circuit with itself: alone, reversed, batched. Sums of saved
probabilities are the main observable, because they are deterministic and because a correct channel can
only give 1. A sampled row is used only where the sampled effect is the point.

**Two independent audit looks.** The static scan finds call sites a test never reaches, and the spy finds
paths a reading of call sites would miss, such as a sampler hiding a batch inside a helper. The spy wraps
`AerBackend._execute_circuits_job`, which all routes pass, and adds a positive control. Each site is
classified by hand against a four-part exposure condition, so "not affected" names the part that fails.

**Isolation.** `python -I` makes an accidental project import fail in the scripts that claim to use
none. `bridge_arm_b.py` runs from a throwaway worktree of `e91239fd`, removed afterwards.

## Mathematical / Statistical details

**The law.** Let `S` be the superoperator of a noise channel, acting on a vectorised density matrix. A
channel preserves the trace, so `tr(S[rho]) = tr(rho)`. Suppose Aer applies `2S` at each of `k` noise
locations and ordinary gates between them, which also preserve the trace. Then the final state is
`rho' = 2^k rho`, with `rho` the correct final state, and `tr(rho') = 2^k`. The element-by-element check,
`max |rho' - 2^k rho| <= 1e-9`, is stronger than the trace: it says the state is right up to the scale.

**Why computing twice gives `2S`.** `compute_circuits_superoperator` builds
`S = sum_j p_j S_j` by adding into a matrix it expects to be zero. `matrix::initialize` zeroes only when
the dimensions change. A second call, with `S` already there, therefore ends with `S + S = 2S`.

**The sampling law.** Aer's sampler draws `r` uniform on `[0, 1)` and returns the first integer outcome
`i` with `sum_{j <= i} p_j > r`, with no renormalisation. With `p' = 2^k p` and `G` the true cumulative
distribution, the sampled cumulative distribution is `min(1, 2^k G)`.

- One location, `x` then amplitude damping `g`: `p(0) = g`, so sampled `P(0) = 2g`.
- A GHZ with `k = 3`: `8 p(000) >= 1` as long as `p(000) >= 1/8`, so every shot gives `000`.

**Readout, applied after sampling.** With symmetric error `e` per qubit, an all-`000` sample stays `000`
with probability `(1 - e)^3`, which is 0.9412 at `e = 0.02`, and becomes `111` with probability `e^3`,
about `8e-6`, or 0.016 expected counts in 2,048 shots. That is why `111` shows no counts.

**Why the fidelity barely moves.** With ideal GHZ `q` and sampled `p`, Hellinger fidelity is
`(sum_i sqrt(p_i q_i))^2`. For `p` all on `000`, that is `(sqrt(1 * 0.5))^2 = 0.5`, whatever the true state
was. A circuit whose true fidelity is near 0.5 therefore hardly changes.

**The shot window.** Aer gives a noisy, sampleable circuit `density_matrix` when `shots > 2^n`, with `n`
the active qubit count, and `statevector` otherwise, for Kraus noise. For a first circuit on `n1` and a
second on `n2`, the defect needs the first on statevector, `shots <= 2^n1`, and the second on density
matrix, `shots > 2^n2`, giving `2^n2 < shots <= 2^n1`. It is non-empty only when `n2 < n1`, unless the
first circuit is forced off the rule by not being sampleable, as a gate after a measurement does.

**Tolerances.** Sums must hold to a relative `1e-9`. A sampled row must hold within 4 binomial standard
errors, `sqrt(p (1 - p) / N)`. There are few sampled rows, so 4 keeps the chance of a false miss small
without hiding a shift: the smallest predicted shift, at `g = 0.05`, is from 0.05 to 0.10 at 2,048 shots,
far more than 4 standard errors of about 0.0048 each.

## Design decisions

- **Commit the mechanism as a prediction, not as a conclusion.** The brief warned against asserting a
  mechanism without evidence. Writing the reading down first, with rows that could fail it (B12 to B14
  above all, where two code branches predict different results), turned a plausible story into a test.
- **Still stop short of "proven".** Building a patched Aer on this machine would be the proof, and it was
  not attempted: it is expensive here and the behaviour is already pinned from outside. The doc says the
  code path and the numbers agree.
- **A tolerance miss is recorded, not relaxed.** Arm B alone missed `1e-9` by about `3e-9`. Amendment 1
  records the miss and adds a ratio, leaving the original prediction as written.
- **Two rows, not one.** NC-097 is about the library and stays true of 0.17.2 whatever happens here.
  NC-098 is about this repository at one commit, so it needs a different anchor and can go out of date.
- **No fix, no guard, no upstream report.** The repository has no exposed path, so a guard would be
  protecting nothing today, and step 1d's plan already holds its own batching test (its criterion 7).
  Reporting is the lead's call, so nothing was posted.
- **The other branch was left alone.** The 1d plan's sentence about reach, and the affected probe output,
  sit on `mert/issue-125-submission`, which belongs to other work; the finding names them and leaves the
  edit to that branch.
- **No run on Aer 0.18.x.** No venv on this machine has it, and installing one was not part of the brief.
  `compare_source.py` gives what reading can.

## Verification

From the repository root, with `C:/t/pin125/Scripts/python.exe` as `python`. Laptop results are
provisional until a desktop rerun.

```bash
python -W ignore -I docs/evidence/aer-batching-defect/minimal_reproduction.py
```

```bash
python -W ignore -I docs/evidence/aer-batching-defect/trigger_sweep.py
```

Expected: the first shows `P(0)` about 0.1 alone and about 0.2 after either first circuit, with sums 1
and 2. The second ends `missed 0` and exits 0; a missed row exits 1. Repeated on this machine, both give
output identical to the committed files.

```bash
PYTHONPATH="docs/evidence/aer-batching-defect" python -m pytest docs/evidence/aer-batching-defect/spy_positive_control.py -p spy_aer_runs -p no:cacheprovider -o addopts="--strict-markers"
```

```bash
PYTHONPATH="src;docs/evidence/aer-batching-defect" python -m pytest tests -p spy_aer_runs -p no:cacheprovider -q -o addopts="--strict-markers -v"
```

Expected: the control passes and lists three two-circuit executions; the suite's summary lists none. On
Linux the path separator in `PYTHONPATH` is `:`.

```bash
python -I docs/evidence/aer-batching-defect/audit_aer_runs.py
```

Expected: 0 unreadable and 0 unparsed; section 3 lists the probes' known batches.

The scan sees calls, not a method kept in a name for later, so this complements it. A first version of the
pattern, `\.run\b[^(]`, could not match a line ending in `.run`, and so missed the one real alias.

```bash
git grep -nE "\.run\b($|[^(])|, *[\"']run[\"']" main -- 'src/*.py' 'scripts/*.py' 'tests/*.py' 'docs/evidence/*.py'
```

Expected: a docstring in `aer_factory.py`, and `original_run` and its `monkeypatch.setattr` in
`tests/test_harness.py`, which still pass one circuit and which the spy watched.

**The NC id check.** Before writing the rows, the highest `NC-` id was read from
`docs/numerical-claims.md` on every local and origin ref. It was 096 everywhere, so 097 and 098 were free.

**Upstream search, 2026-11-05.** `gh search issues --repo Qiskit/qiskit-aer` with these terms, none
returning a matching report: "superoperator automatic method multiple circuits"; "wrong results noise
model batch circuits density_matrix statevector"; "compute_superoperator"; "density_matrix wrong results
multiple circuits noise model"; "automatic method noise model multiple circuits different qubits wrong";
"probabilities sum greater than 1 density matrix noise"; "superoperator doubled"; "trace not 1
density_matrix noise kraus"; "batch circuits fake backend wrong counts all zeros";
"enable_superop_method". Not checked: Aer's discussions, Qiskit's Slack, or the wider web.

**Not checked:** any other Aer version, GPU, MPI, Linux or Burak's desktop; a rebuilt Aer; `matrix_product_state`
or `tensor_network` as the first method; the sampling law on wide states; the estimator primitives; the
cause of Arm B's `3e-9` trace deficit; and `probe_build_time.py` itself, which was classified by its code
and output, not re-run.

## Related docs

- `docs/findings/2026-11-05-aer-batching-defect.md`
- `docs/evidence/aer-batching-defect/README.md`
- NC-097, NC-098 in `docs/numerical-claims.md`
- `docs/findings/2026-10-28-aer-per-shot-seeding-and-simulation-lessons.md`, the sibling finding
- `docs/implementations/2026-11-05-hardware-test-submission.md`, on branch `mert/issue-125-submission`
- Issue #125; Qiskit/qiskit-aer#2500
