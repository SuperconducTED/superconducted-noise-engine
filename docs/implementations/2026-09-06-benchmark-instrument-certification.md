# 2026-09-06: benchmark instrument certification

## Problem / Motivation

Issue #58 identified three failures at baseline `7d39a2b`: state fidelity was silently
converted to an all-NaN row because the harness produced counts only; QFT reached Aer as
an undecomposed `qft` instruction and crashed; and metric exceptions were converted to
unlabelled NaN values. The harness also accepted a physics reference but the repository
could not construct one from a calibration snapshot. Those defects made a plausible-
looking but scientifically invalid ADR-019 result possible.

This change certifies the measurement path before #62 uses it. It takes the deliberate
public signature break once, constructs a unit-checked thermal-relaxation reference,
reasserts ADR-022 in both supported modes, and records a controlled resolution experiment.
The branch is `bengisu/issue-58-benchmark-certification`; every branch commit is authored
and committed as `BENGISU CIVDI <bengisu.civdi@gmail.com>` through repository-local Git
configuration.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/benchmarks/harness.py` | Adds explicit-basis transpilation, counts/density modes, deterministic seeds, auditable metric failures, and installed-noise metadata. |
| `src/superconducted/benchmarks/reference.py` | Builds plain Aer thermal-relaxation models in like-for-like and full-device scopes and separately reports provenance. |
| `src/superconducted/benchmarks/__init__.py` | Exports the reference builder and report. |
| `scripts/resolution_measurement.py` | Runs the controlled Hellinger, corrected `1-R²`, and `1-F` resolution ladder without the fuzzy inference pipeline. |
| `tests/conftest.py` | Provides the committed snapshot and a deterministic viable benchmark ensemble. |
| `tests/test_harness.py` | Reproduces the three defects first, then pins execution, aggregation, metadata, seed, error, and ADR-022 contracts. |
| `tests/test_reference.py` | Pins units, scopes, skips, tensor order, readout orientation, basis validity, report agreement, and determinism. |
| `tests/test_metrics.py` | Pins all four wrong-mode rejections. |
| `tests/test_resolution_measurement.py` | Pins discrepancy direction, conservative aggregation, completeness, exact counts regeneration, and `1e-12` cross-machine density agreement. |
| `tests/fixtures/calibration/README.md` | Corrects only the stale remote name because #57 has not yet done so on `main`. |
| `docs/evidence/resolution-measurement/` | Records the provisional 24-cell TSV, exact command, inputs, environment, hash, and limitations. |
| `docs/decisions.md` | Appends an ADR-022 as-of note; no existing decision text or status changes. |

No second calibration fixture was created. The #57-owned
`ibm_fez_20260513T121322Z_with_gates.json` path is consumed by a test that remains skipped
until that fixture lands. The LOCKED `channels/kraus.py` and `fuzzy/tsk.py`, as well as
`types.py`, `interfaces.py`, `integration/aer_factory.py`, circuit definitions, and metric
formulas are unchanged.

## Implementation approach

### One compiled circuit, two honest paths

Each public simulation function validates an explicit device basis. `run_benchmark`
defaults that basis to `reference_noise.basis_gates`. A circuit is compiled exactly once
with `optimization_level=1`, `seed_transpiler=0`, and no backend or coupling map. The
engine and reference receive the same compiled object lineage; engine members call
`prepare()` only after compilation, and no transpilation occurs afterward.

Counts are still combined with `Counter.update`, with semantic total
`shots_per_member * ensemble_size`. Member `i` uses `seed_simulator = seed + i`; the
reference uses `seed`; `None` deliberately omits the simulator seed. A separate
`reference_shots` affects only the reference and defaults to the engine member shot count.

Density mode removes final measurements, calls `prepare()` on the measurement-free
circuit, appends `save_density_matrix()` only afterward, and runs Aer's density-matrix
method with `shots=1`. This ordering is materially tested on one qubit: if the save
instruction were appended early, the current name-agnostic projector would accept it and
the metadata pin would fail.

Every result records the mode, circuit name, explicit basis, ensemble size, and sorted
installed `noise_instructions`. The engine records one list per member. This lets #62
audit what actually fired without creating a second transpile/prepare path.

### Errors are either raised or visibly recorded

`on_error="raise"` is the default. It propagates the two declared metric data failures,
`ValueError` and `ZeroDivisionError`, instead of returning a plausible-looking partial
table. `on_error="record"` is an explicit lossy mode: all three numeric fields are NaN and
the frozen `BenchmarkRow.failure` string names the failing side, exception class, and
message. Other exception types always propagate. Tests require the record string to be
non-empty.

### Physics reference and provenance

`build_reference()` returns a plain `NoiseModel`, preserving the existing harness type.
`build_reference_report()` repeats the deterministic build and returns a separate frozen
`ReferenceReport`. The two functions share one private implementation so their filtering
cannot drift.

The boundary accepts only the units actually used here: T1/T2 in microseconds and gate
lengths in nanoseconds, converted to SI seconds by a local two-entry table. Wrong units,
negative/non-finite lengths, non-positive coherence times, malformed gate records, and
duplicate calibrations raise. Missing, null, or non-finite T1/T2 entries are skipped and
counted; no value is imputed. `T2 > 2 T1` is separately skipped because it would make the
derived phase-damping probability negative.

The two scopes are:

- `single_qubit_relaxation`: positive-duration one-qubit gate channels only; no two-qubit
  channel and no readout error. This is the present engine's like-for-like scope except
  for the disclosed `rz` asymmetry below.
- `full_device`: the same one-qubit channels, tensor-product thermal relaxation on timed
  two-qubit gates, and per-qubit readout errors.

Zero-duration gates, including the fixture's virtual `rz`, remain in the report's gate-
length map but receive no identity error. The current engine still noises `rz` because its
projector is gate-name agnostic; this accepted-and-disclosed asymmetry is filed as #73.
Circuit qubit `i` maps to device qubit `i`; no topology or remapping is inferred.

`qubits_used` contains qubits that actually carry an installed quantum or readout error,
not merely qubits with valid T1/T2. Every skipped qubit carries neither. Directed dead
`cz` pairs (`gate_error == 1`) are reported independently of installability: the #57
fixture has 10, of which six have usable endpoints and four touch missing-q72 data. The
only non-imputing implementation reports all 10, installs the six usable ones, and leaves
the other four absent under ADR-017. Burak's owner ratification remains pending. Mert also
found 12 dead one-qubit gate entries; FR-10 fixes `dead_pairs` to directed `cz` pairs, so
the branch documents that fact and awaits Burak rather than silently changing the frozen
report schema.

For IBM's names

```text
p01 = prob_meas0_prep1 = P(measure 0 | prepared 1)
p10 = prob_meas1_prep0 = P(measure 1 | prepared 0)
```

Aer receives the row-stochastic matrix

```text
[[1 - p10, p10],
 [p01, 1 - p01]].
```

A fixed-seed 20,000-shot test with `p10=0.3`, `p01=0` checks this orientation within its
predeclared 3σ binomial tolerance.

### Controlled resolution experiment

The resolution script uses public pieces only. It compiles QFT(3) and GHZ(3) once to the
explicit May basis, then calls `PostGateFuzzification.install` with a fresh `NoiseModel`
and a provider backed by `KrausChannelProjector(NoOpNormalization())`. The provider
returns a channel only for one-qubit instructions. Thus A and B reproduce the current
engine channel placement without running the fuzzy pipeline, while their only varying
quantity is `gamma_B = gamma_A + delta`.

For repeat `i`, counts use two independent A seeds for the floor and the first A seed for
the paired A/B comparison:

```text
A_i:  seed + 2i
A'_i: seed + 2i + 1
B_i:  seed + 2i
```

The committed run uses a predeclared base seed of 58, 32 repeats, 4096 shots, and the
placeholder ladder `0.1, 0.01, 0.001, 0.0001`. Its inputs, every cell, elapsed time, hash,
and exact command are in `docs/evidence/resolution-measurement/README.md` and
`resolution.tsv`.

The experiment is diagnostic, not yet an NC claim. QFT's `1-R²` cell empirically has a
shot-noise-dominated floor and resolves no ladder value, so the conservative all-cell
counts result is “not resolved on ladder.” That result has been posted to #58 for an
explicit owner decision. The density result reaches the smallest tested `0.0001`, but no
value below the ladder is inferred. The entire ladder remains
`provisional, placeholder ladder` until #59 supplies its accepted survey spread and
Burak's batch-1 desktop run becomes canonical.

## Mathematical / Statistical details

### Thermal relaxation and the engine channel

The locked projector composes amplitude damping with probability `gamma` and phase
damping with probability `lambda`. Amplitude damping maps

```text
rho_11 -> (1 - gamma) rho_11
rho_00 -> rho_00 + gamma rho_11
rho_01 -> sqrt(1 - gamma) rho_01
rho_10 -> sqrt(1 - gamma) rho_10.
```

Phase damping leaves both diagonal entries unchanged and multiplies each off-diagonal by
`sqrt(1 - lambda)`. The channels commute here: only amplitude damping changes the
diagonal, while both act on each off-diagonal through scalar multiplication. Their
composition therefore has population survival `1-gamma` and coherence multiplier
`sqrt((1-gamma)(1-lambda))`.

A qubit evolving for time `t` with relaxation times T1 and T2 has population survival
`exp(-t/T1)` and coherence survival `exp(-t/T2)`. Matching those factors gives

```text
1 - gamma = exp(-t/T1)
gamma = 1 - exp(-t/T1)

sqrt((1-gamma)(1-lambda)) = exp(-t/T2)
(1-gamma)(1-lambda) = exp(-2t/T2)
1-lambda = exp(-2t/T2 + t/T1)
lambda = 1 - exp(-t(2/T2 - 1/T1)).
```

Three boundary consequences follow directly:

1. `lambda >= 0` exactly when `T2 <= 2 T1`; this is the physical basis for the skip.
2. `lambda = 0` at `T2 = 2 T1`; the channel is pure amplitude damping.
3. `lambda = gamma` at `T2 = T1`.

The local read-only SuperOp audit used T1=100 μs, `t=24 ns`, and T2 values 80, 100,
150, and 200 μs. It covers Aer's circuit-mixture regime (`T2 <= T1`), Kraus regime
(`T1 < T2 <= 2T1`), and the boundary. Maximum elementwise differences between the locked
projector at the closed-form `(gamma, lambda)` and Aer
`thermal_relaxation_error(T1,T2,t)` were respectively `1.1102230246251565e-16`,
`2.220446049250313e-16`, `9.992007221626409e-16`, and
`8.881784197001252e-16`; the maximum is below `1e-15` and the acceptance tolerance is
`1e-12`. Comparison is by `SuperOp(...).data`, never `QuantumError ==`, because Aer uses
different internal representations across the two regimes. The eventual NC id is not
reserved in this draft.

### Why 4096-shot counts struggle at the physical scale

At `t=24 ns` and T1 of order `1e-4 s`,

```text
gamma = 1 - exp(-24e-9 / 1e-4) ≈ 2.4e-4.
```

A shallow circuit therefore moves individual probabilities on roughly the `1e-4` to
`1e-3` scale per gate. A binomial proportion at `S` shots has standard error

```text
sqrt(p(1-p)/S) <= 1/(2 sqrt(S)).
```

At `S=4096` the maximum is `1/128 = 0.0078125`, while the whole-distribution sampling
scale `1/sqrt(4096)` is `1/64 = 0.015625`. Both are one or two orders above the intended
physical effect. Density evolution has no sampling term; its floor is numerical error.

### Density-matrix aggregation

For member states `rho_1, ..., rho_N`, the certified point estimate is the arithmetic
mixture

```text
rho_ens = (1/N) sum_m rho_m.
```

It has unit trace because trace is linear, is Hermitian because Hermiticity is preserved
under real linear combinations, and is positive semidefinite because it is a convex
combination of positive semidefinite matrices. Its diagonal is the mean member outcome
probability, exactly the limit obtained by normalizing counts summed from equal-shot
members. It is not a raw sum of states and therefore carries semantic `shots=1`, not
`N`. Identical members use an exact fast path so the current ADR-015-deferred ensemble
returns `rho_ens == rho_1` byte for byte; non-identical members use `np.mean`.

This is only the point estimate. ADR-016 remains Deferred, and #64 owns interval-valued
aggregation and real per-member perturbations.

### Resolution statistics and the R² correction

For counts discrepancy `D`, repeat `i` is

```text
d0_i = D(A_seed_i, A_seed_j)      with independent seeds
d1_i = D(A_seed_i, B_seed_i)      with the same seed
threshold = mean(d0) + 3 * sd(d0), sd uses ddof=1
resolved iff mean(d1) >= threshold.
```

Hellinger is already a discrepancy with identity zero. Raw R² is a similarity with
identity one, so applying the same greater-than rule to it reverses the physics. The
corrected script-local quantity is

```text
D_R2 = 1 - R²,
```

which is zero at identity and grows as the fit worsens. Mert and Yiğit approved this
orientation. The test pins direction over a controlled sequence: raw R² strictly falls
while `D_R2` strictly rises.

There is a separate conditioning problem. Ideal QFT(3) applied to `|000>` is uniform on
eight outcomes, so the population denominator

```text
ss_tot = sum_k (p_k - mean(p))²
```

is zero. At finite shots, both `ss_tot` and the residual numerator are then driven by
sampling noise. Correcting the sign does not create information in that denominator. The
real run measures QFT's `D_R2` floor as `2.2015236552710293` with sample SD
`1.5700033940263955`, giving an unreachable-on-this-run 3σ threshold
`6.9115338373502162`; even `delta_gamma=0.1` yields only `1.0121772336223365`. These are
diagnostic TSV values, not registered claims.

Density mode uses

```text
D_F = 1 - F(rho_A, rho_B)
```

and resolves a cell only when `D_F > 1e-10`. There is no script-local diagonal-Hellinger
column in this ticket; its eventual public metric is phase-4 issue #76 and must clear all
six ADR-022 properties.

## Design decisions

| Decision | Implemented recommendation | Recorded state on #58 |
| --- | --- | --- |
| 1 | `on_error="raise"` by default; explicit auditable `record` mode | Mert confirmed as records owner and at lead level; Burak owner review pending |
| 2 | Explicit basis, compile once at optimization 1 / transpiler seed 0, no coupling map | Mert lead-level agreement; Burak pending |
| 3 | Disclose engine/reference `rz` asymmetry; identity qubit mapping | Mert lead-level agreement; Burak pending; #73 filed |
| 4 | Density results and aggregate carry `shots=1` | Mert lead-level agreement; Burak pending |
| 5 | Local strict `us`/`ns` conversion table | Mert lead-level agreement |
| 6 | Report all dead directed `cz`; install only when T1/T2 endpoints are usable | Mert verified/endorsed; Burak pending, including single-qubit dead-entry report shape |
| 7 | Member seed `seed+i`, reference seed `seed`, `None` unseeded | Yiğit confirmed as #62 caller; Mert agrees; Burak pending |
| 8 | `reference_shots` defaults to `shots` and affects only reference | Yiğit confirmed as #62 caller; Mert agrees; Burak pending |
| Resolution orientation | Use `D_R2=1-R²` | Mert and Yiğit confirmed |
| Resolution aggregation | Smallest delta for which every defined cell resolves | Yiğit confirmed; Mert proposed; Burak/QFT treatment pending |

The branch builds behind the issue's recommendations as §8 step 3 permits, but it does
not relabel pending owner decisions as signed off.

## Verification

The test-only first commit is `93e5d58`. On baseline behavior its three reproduction
tests fail; at the current head they pass. The implementation and audit commits are
`d646e07`, `bb38152`, `b62ba2a`, `1ae6c3a`, and `6119017`.

Targeted certification:

```powershell
python -m pytest tests/test_harness.py tests/test_reference.py tests/test_metrics.py tests/test_resolution_measurement.py -v
```

Full suite and collected-count differential are run at the final draft head:

```powershell
python -m pytest tests/ -v
```

```powershell
python -m pytest tests/ --collect-only -q -o addopts=""
```

The current collection is 343 tests, 63 more than NC-021's 280-test baseline at
`947fe3d`; the full run passes 339 with four explicit #57-dependent skips. The merge-ready
NC update is intentionally withheld until the ledger head is known.

Static checks:

```powershell
python -m ruff check .
```

```powershell
python -m ruff format --check .
```

```powershell
python -m mypy --strict
```

Resolution regeneration:

```powershell
python -m pytest tests/test_resolution_measurement.py::test_measurement_regenerates_committed_tsv -v
```

NFR-1 is applied at the evidence boundary: protocol, inputs, provenance, verdicts, row
order, and seeded counts cells agree exactly; density-matrix measurement fields agree
across machines to absolute `1e-12`. Repeated serialization of the same locally measured
rows remains byte-identical. This distinction was exercised by the PR's Linux 3.11/3.12
jobs, whose Aer/linear-algebra reductions differed from the Windows evidence by at most
approximately `4.44e-15`; production values are not rounded to manufacture bit identity.

The direct `sx` execution guard is:

```powershell
python -m pytest tests/test_harness.py::test_sx_only_noise_fires_through_explicit_basis -v
```

The test uses a fixed seed and asserts a differential—counts differ from a noiseless run
at the same seed—rather than freezing a host-specific absolute count.

LOCKED and cross-cutting exclusions:

```powershell
git diff --exit-code 7d39a2b -- src/superconducted/channels/kraus.py src/superconducted/fuzzy/tsk.py src/superconducted/types.py src/superconducted/interfaces.py src/superconducted/integration/aer_factory.py
```

## Merge-time and dependency work deliberately not guessed

- #56 has not delivered the restructured `docs/team.md`, the first ADR-016 phase-3
  alignment note, the advisor record, or the refined NC convention. This draft does not
  append to the obsolete team table, preempt ADR-016 ordering, or invent an advisor reply.
- #57 / PR #69 has not merged the gates-bearing fixture or target cross-check. The two
  dependent tests remain explicitly skipped; no fixture is duplicated or cherry-picked.
- #59 / PR #68 has not merged an accepted survey spread. The resolution ladder remains
  provisional and must be rerun before #62's probe.
- Numerical-claim IDs are selected as `max(active NC id)+1` immediately before merge,
  never from row count and never by reusing retired NC-013/NC-R002. Five conclusion rows
  remain to be added after rebase and decisions: SuperOp difference, fixture `sx` length,
  counts resolution, density resolution, and full-suite differential. NC-021 must also be
  updated under ledger rule 6.
- The ADR-016 as-of note must follow #56's line. The new `benchmarks/reference.py`
  ownership row must target #56's restructured table. Dr. Akba's read must be recorded in
  #56's single advisor file by Mert, not fabricated here.

These conditions make a draft PR appropriate. They do not weaken the implemented tests;
they prevent this branch from manufacturing governance state that does not yet exist.

## Related docs and issues

- #58 — source specification and decision thread
- #56 — documentation/governance prerequisites
- #57 / PR #69 — target ADR and sole gates-bearing fixture
- #59 / PR #68 — calibration survey spread for the rerun
- #62 — first consumer of the certified harness
- #64 — interval aggregation follow-up
- #73 — engine gate-name filtering
- #74 — smoke-script transpile/prepare ordering
- #75 — LOCKED projector allowlist and clipping contract
- #76 — phase-4 diagonal Hellinger metric
- ADR-016, ADR-017, ADR-019, ADR-021, ADR-022, ADR-024, and ADR-008 in
  `docs/decisions.md`
- `docs/evidence/resolution-measurement/README.md` and `resolution.tsv`
