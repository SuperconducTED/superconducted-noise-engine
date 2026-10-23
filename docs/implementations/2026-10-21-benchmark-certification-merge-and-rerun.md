# 2026-10-21: benchmark-certification merge, skip-rule alignment and resolution rerun

## Problem / Motivation

PR #79 (Issue #58) sat as a draft from 2026-09-08 while `main` took 272 commits, so
it was `DIRTY` and its CI had not run since 2026-09-06. A trial merge of `main` @
`6cf008d` (measured 2026-10-21, as Mert had first measured at `110cfad` on #79,
comment 5885110245) showed what the conflict markers did not:

| # | Finding | Measured on the merged tree |
| --- | --- | --- |
| a | `test_transpiled_qft_installs_only_executed_noise_instructions` fails: the `benchmark_snapshot` fixture has no `properties.gates`, so ADR-028's `CalibrationGateEligibilityPolicy` (PR #96) admits nothing | fails |
| b | the same cause: 16 harness tests run an engine that installs no error, and 15 still pass | 17 fail with the "installed no error" warning as an error |
| c | `test_issue_57_fixture_reference_provenance` compares `24 * 1e-9` to `24e-9` with `==` | fails |
| d | `test_reference_matches_training_targets_per_qubit` has an empty body | vacuous |
| e | the test engine's MF grid is laid out in archive microseconds (T1 33 to 329) while `BasicCalibrationVectorizer.extract` emits SI seconds since issue #66 (T1 input 1.55e-4) | every T1/T2 input below the lowest centre |
| f | `scripts/resolution_measurement.py` noises every single-qubit instruction including zero-length `rz`, which the engine has not done since ADR-028 | `rz` eligible on 0 of 156 qubits |

Two owner questions were also open: Mert's 2026-09-08 comparison of the reference's skip
rules with ADR-027's (#79, comment 5585406092), and FR-7's rerun against #59's spread,
which the 2026-09-06 implementation record lists as merge-time work.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/benchmarks/harness.py` | Merge resolution only: `main`'s aggregation sentence verbatim plus this branch's transpile and density sentences. |
| `tests/fixtures/calibration/README.md` | Merge resolution only: `main`'s side, a superset of this branch's edit. |
| `tests/conftest.py` | `benchmark_snapshot` loads #57's gates fixture, the obsolete skip-until-#57 fixture is gone, and the MF grid is built in each value's declared unit. |
| `tests/test_harness.py` | A grid-units guard, the two #57-fixture tests on the single fixture, and the like-for-like pin with no `rz` exception. |
| `src/superconducted/benchmarks/reference.py` | ADR-027's ordered qubit-level skip reasons, gate-level fail-closed skips in a new `ReferenceReport.skipped_gates`, and a `ValueError` when no qubit is usable. |
| `tests/test_reference.py` | New skip-reason, gate-length and no-usable-qubit pins; the provenance test without its obsolete skip and with `pytest.approx`; the cross-module test given its body. |
| `scripts/resolution_measurement.py` | An optional `--eligibility-snapshot` (library: `eligible_operations`) that makes the controlled model follow ADR-028; the default path is unchanged. |
| `tests/test_resolution_measurement.py` | The regeneration pin parametrized over both TSVs, plus eligibility and empty-eligibility pins. |
| `docs/evidence/resolution-measurement/resolution-2026-10-21-spread-ladder.tsv` | 42 cells of the engine-true, spread-anchored rerun. |
| `docs/evidence/resolution-measurement/README.md` | An appended 2026-10-21 section: inputs, provenance, command and result. |
| `docs/decisions.md` | Append-only: the ADR-016 density-mode note and a 2026-10-21 note under ADR-022. |
| `docs/team.md` | `benchmarks/reference.py` row, Bengisu primary, Burak Öztekin secondary. |
| `docs/implementations/2026-09-06-benchmark-instrument-certification.md` | An appended as-of section pointing here. |

## Implementation approach

**Merge first, unchanged.** Commit `a56a088` is conflict resolution only, so a reviewer
can diff it against Mert's proposed resolution and see nothing else. Every behavioural
fix follows in its own commit.

**One benchmark fixture.** FR-8 step 4 says to point the loader at #57's fixture once it
is on `main`; it has been since PR #69 (2026-09-08). Loading it in `benchmark_snapshot`
gives every harness test an engine with eligible gates (`id`, `rx`, `sx`, `x` on 156
qubits) and keeps the qubit-72 missing-T1/T2 case. A second fixture that skipped until
#57 landed had become a duplicate and is removed.

**Grid units from the data's own declaration.** `_feature_range` now multiplies each
value by `UNIT_SCALE[entry["unit"]]` (the loader's public table), so the grid is in
whatever unit `extract` emits for that field. An unknown unit is a `KeyError`, which is
loud by design.

**Skip alignment as a contract, not a copy.** `build_reference` and
`training.targets.qubit_targets` now share the qubit-level reasons and their order. The
reference does not import the target's private helpers; the shared behaviour is pinned
from outside by `test_reference_matches_training_targets_per_qubit`, which builds both
from one snapshot file.

**Engine-true resolution.** The controlled model's provider declines any `(gate, qubits)`
pair outside an optional eligible set, and the CLI derives that set by calling the shipped
`CalibrationGateEligibilityPolicy` on a snapshot, so the script carries no hand-written
gate list. With no snapshot it behaves exactly as on 2026-09-06, which keeps
`resolution.tsv` regenerable at this commit.

## Mathematical / Statistical details

Conventions: SI seconds for `T1`, `T2` and gate length `t`; Qiskit little-endian ordering;
`ddof=1` for every sample standard deviation; fidelity `F` as computed by
`StateFidelity`; no logarithms are involved.

**Ordered skip rule.** For a qubit `q` with readings `T1_q`, `T2_q`, the reference assigns
the first reason that applies:

1. `t1_missing`: `T1_q` absent, null or non-finite;
2. `t2_missing`: `T2_q` absent, null or non-finite;
3. `nonpositive`: `T1_q <= 0` or `T2_q <= 0`;
4. `t2_exceeds_2t1`: `T2_q > 2 T1_q`, where `lambda_q = 1 - exp(-t (2/T2_q - 1/T1_q))`
   would be negative.

This is ADR-027's order with its third reason, `gate_length_missing`, removed from the
qubit level. The target needs one duration per qubit (`sx`), so a missing `sx` length
rejects the qubit. The reference times each gate by its own duration, so a missing or
negative length is a property of one `(gate, qubits)` entry: that entry installs nothing
and is listed under `skipped_gates`. On a qubit whose `sx` length is present the two
classifications therefore coincide reason by reason, which is what the cross-module test
asserts (it fixes `gate_length_missing = 0` on the target side). A selection with no
usable qubit raises: `snapshot_target` returns `None` there, and a reference built anyway
would be the identity channel everywhere.

**Per-qubit channel identity.** For a usable qubit the engine's channel is amplitude
damping `gamma_q = 1 - exp(-t/T1_q)` composed with phase damping `lambda_q` (the
derivation is ADR-027's and #58 section 6.3's). The reference installs Aer's
`thermal_relaxation_error(T1_q, T2_q, t)`. The test compares
`SuperOp(reference) - SuperOp(projector(gamma_q, lambda_q))` entrywise, which is
representation-independent across Aer's two internal branches. Measured worst absolute
entry over the fixture's 155 usable qubits: `1.3322676295501878e-15` (114 qubits with
`T2 <= T1`, 41 with `T1 < T2 <= 2 T1`), against the `1e-12` pin. NC-036 records the same
identity for four hand-chosen cases; this extends it to every usable fixture qubit.

**Ladder.** `s_gamma = sd_{ddof=1}(gamma_q)` over the same 155 qubits,
`7.600232779751463e-05`: one snapshot's cross-qubit spread of the target, not #59's survey
statistic `s_q` (a within-snapshot spread of the features, summarised as NC-042). Re-measured by two routes (the target module and the closed form
on the raw JSON), which give identical `(gamma_q, lambda_q)` rows. The value is
`np.std(rows, axis=0, ddof=1)[0]` over the `(155, 2)` array; a 1-D
`np.std(rows[:, 0], ddof=1)` gives `7.600232779751465e-05` because numpy reduces in a
different order, so the spread is known to 15 significant digits and the ladder fixes the
first expression's value. Rungs `delta_k = s_gamma * 2^k`, `k = 3..-3`; a
power-of-two factor is exact in binary floating point. The largest rung keeps
`gamma_0 + delta <= 1` (`7.8e-4`), so `_checked_inputs` never clips.

**Counts rule (unchanged).** For each delta, `d0_i = D(A_i, A_i')` and
`d1_i = D(A_i, B_i)` over `R = 32` seed pairs at `S = 4096` shots;
`resolved iff mean(d1) >= mean(d0) + 3 sd(d0)`, with `D` Hellinger or `1 - R^2`. A mode
resolves `delta` only if every prescribed cell does.

**Density rule (unchanged).** `resolved iff 1 - F(rho_A, rho_B) > 1e-10`. `F` is maximal
(`1`) at `delta = 0`, so if it is twice differentiable in `gamma` there, its first
derivative vanishes and `1 - F = c delta^2 + O(delta^3)`: halving `delta` should divide
`1 - F` by about 4. Smoothness is an assumption (fidelity can be non-smooth at
rank-deficient states), and the data are consistent with it: the QFT ratios down the
ladder are 3.31, 3.55, 3.73, 3.85, 3.92, 3.96, and GHZ's run from 3.11 to 3.92. That
convergence is the analytic cross-check on the density column, not a proof.

**Result (laptop, provisional).** Counts mode resolves no cell at any rung (closest: GHZ
Hellinger at `8 s_gamma`, `0.021947` against `0.034789`). Density mode resolves every rung
down to `s_gamma / 8 = 9.5e-6` (`1 - F = 2.26e-7` QFT, `1.15e-7` GHZ), so it is
ladder-limited: `<= 9.5e-6 tested`. Nothing below the ladder is inferred. Applying ADR-028
eligibility lowers `1 - F` at `delta = s_gamma` from `1.492e-5` to `1.349e-5` (QFT) and
from `1.619e-5` to `6.545e-6` (GHZ); the commands are in the evidence README.

## Design decisions

- **Align, rather than keep the reference strict** (Bengisu, 2026-10-21). FR-5 required
  identical skip rules; ADR-027 later fixed five ordered reasons. The alternative, keeping
  `ValueError` on `T1/T2 <= 0` and on a missing length and documenting the difference,
  would leave the target and the reference on different qubit sets for the same snapshot.
- **Split the merged `missing_t1_t2` key.** That literal came from FR-10's schema, written
  before ADR-027 existed. Keeping it would make the per-reason counts incomparable with
  `SkipCounts`; no caller outside this PR reads it yet.
- **Gate-level reasons go in a new field, not in `skipped`.** `skipped` maps reasons to
  qubits; a missing duration belongs to a `(gate, qubits)` entry. Recording it under
  `skipped` would mark as rejected a qubit the model still uses for its other gates.
  (`qubits_used` and `skipped` do not partition the selection in any case: a usable qubit
  with no installed error is in neither.)
- **Corrupt still raises.** A null, non-numeric, non-finite or wrongly-unit one-qubit gate
  length raises in the reference as it does in `training.targets.gate_lengths`, which is
  also where ADR-028 fails loudly. Not everywhere the target raises, though: the reference
  reads durations only on usable qubits (the target parses every `sx` entry), and it also
  reads two-qubit durations, which the target never does. A non-list `parameters` on a
  one-qubit gate is a missing record, as `gate_lengths` reads it.
- **Dead-pair reading stays strict** (from the pre-push review). A `cz` entry with no
  `parameters` list raises in `full_device` scope, as it did on 2026-09-06. The lenient
  reading is justified for `gate_length`, which `training.targets` also reads leniently, but
  not for `gate_error`, which no target code reads; treating it as "not dead" would drop the
  pair from `dead_pairs` with no signal.
- **Stricter structure than the loader.** Duplicate fields or a non-mapping entry on a qubit
  raise in the reference, while `load_snapshot` keeps the last duplicate. Stated in the
  module docstring; the cross-module test does not exercise it.
- **The intended divergences are pinned, not hidden.** There are two. A missing `sx`
  length rejects the qubit in `qubit_targets` (`gate_length_missing`), and so does a
  negative one (`nonpositive`); the reference rejects only the `sx` entry, under the same
  reason name in `skipped_gates`, and keeps the qubit for its other gates.
  `test_sx_length_gaps_are_qubit_level_in_targets_and_gate_level_here` asserts both sides
  for both cases.
- **Rerun now, engine-true** (Bengisu, 2026-10-21). The alternatives were keeping the
  2026-09-06 controlled model, which noises `rz` and so measures a noisier engine than
  ships, or deferring the rerun to a follow-up commit. The September TSV is kept and stays
  regenerable, so nothing is lost by changing the model for the new file.
- **Register plan.** NC-035 (24 ns `sx`), NC-036 (SuperOp identity) and NC-040
  (`gamma_0`, `lambda_0`) were registered by #57 and are cited, not duplicated. New rows are
  the counts and density conclusions of the 2026-10-21 run plus the NC-021 update, with
  ids taken at merge time under rule 6 (PR #113 already holds NC-070 to NC-076).
- **Like-for-like loses its `rz` exception.** #58 decision 3 accepted and disclosed an
  asymmetry (the engine noised `rz`, the reference did not). #73 closed it through ADR-028,
  so the test now asserts that the asymmetry is gone instead of tolerating it.

## Verification

Run from the repository root with the pinned stack (`requirements.txt` and
`requirements-dev.txt`):

```bash
python -m pytest tests/ -q -p no:cacheprovider
```

```bash
python -m pytest -q -p no:cacheprovider -W "error:FuzzyNoiseModel.prepare installed no error:UserWarning" tests/test_harness.py tests/test_reference.py tests/test_resolution_measurement.py tests/test_metrics.py
```

```bash
python -m pytest tests/ --collect-only -q -p no:cacheprovider -o addopts=""
```

```bash
ruff check .
```

```bash
ruff format --check .
```

```bash
mypy --strict
```

```bash
python scripts/check_ids.py
```

```bash
git diff --numstat origin/main -- docs/decisions.md
```

Expected: the suite passes; the promoted-warning run passes (it had 17 failures before
these fixes); collection is `main`'s count plus this PR's differential; the last command
prints `0` in its second (deleted lines) column, so the ledger diff is additions only.

Measured on 2026-10-21 (Mert's laptop, Python 3.12.10, pinned stack, provisional), on the
tree with the pre-push review fixes: 939 collected and 939 passed with nothing skipped;
the promoted-warning run 95 passed; `main` @ `6cf008d` collects 859 (NC-021's current
value), so the differential is +80: the 2026-09-06 branch's +63 and this round's +17.
Before these fixes the merged tree gave 2 failed, 919 passed, 1 skipped. NC-021 is
re-measured at the merge commit under rule 6, not taken from these figures.

Mutation checks run on 2026-10-21, each restored from a backup copy:

| Mutation | Tests that failed |
| --- | --- |
| MF grid from raw archive values | `test_benchmark_engine_grid_spans_the_vectorizer_inputs` only |
| `benchmark_snapshot` back to the slim fixture | 3 tests; 16 with the warning promoted |
| engine policy that also admits `rz` | the tightened like-for-like assertion |
| `T1/T2 <= 0` raises again | 2 tests |
| `T2` checked before `T1` | 4 tests |
| reference `sx` duration times `1.0001` | 6 tests |
| eligibility filter disabled in the script | 2 tests |
| `cz` without `parameters` silently "not dead" again | `test_cz_without_parameters_raises_in_full_device_scope` |
| override parsed without the `ValueError` wrap | 3 tests (`none`, `list`, `text`) |

Laptop figures here are provisional; the canonical numbers come from Burak's next
batched desktop record.

## Review round, 2026-10-23

@BurakOztekin reviewed `e7218d3` on 2026-10-21 (review 5602131046, changes requested). He
found the harness and the reference correct, and asked for changes to tests and records
that claimed more than they proved. Each finding below was reproduced on the old code
before it was fixed.

**Ratified by Burak as harness owner** (#58 section 7): items 1, 2, 3 (identity mapping;
option (a) no longer applies because ADR-028 closed the `rz` asymmetry), 4, 6, 7 and 8, and
the FR-7 baseline (`gamma_0`, `lambda_0` from NC-040, basis `cz,id,rx,rz,sx,x`).

**His two open decisions:**

- *The 12 dead one-qubit entries need no `ReferenceReport` field.* The fixture carries
  `gate_error == 1` on `id`, `rx`, `sx` and `x` at q17, q72 and q149 (re-counted
  2026-10-23). q72 is skipped (`t1_missing`); on q17 and q149 `single_qubit_relaxation`
  installs relaxation on those gates like any other, because relaxation is about time, not
  about whether the gate works. The reference never reads `gate_error` there, and the
  certified 3-qubit circuits run on q0 to q2. To be revisited if #62 places circuits on
  those qubits.
- *The QFT `1 - R²` cell stays in the protocol.* Dropping it after seeing the data would be
  a post-hoc exclusion; on the 2026-10-21 run it no longer decides the verdict. The
  disclosure now covers GHZ too (below).

**Blocking items and what changed:**

| # | Finding | Change |
| --- | --- | --- |
| 1 | The ADR-022 notes misdescribed the tests: the nine `*_adr022_*` tests use hand-built `NoiseModel`s, so the merge never affected them; the rejection pins came from `bb38152`, not `d646e07` | Both branch-only notes rewritten in place |
| 2 | The density ordering pin was no longer causal: ADR-028's default policy never admits `save_density_matrix`, so a save-before-`prepare()` mutant passed all 37 harness tests | The test engine takes a policy that also admits `("save_density_matrix", (0,))`; the test asserts `[["sx"]]`, and the mutant gives `[["save_density_matrix", "sx"]]` |
| 3 | `run_benchmark`'s default `on_error="raise"` was never tested at the public entry; an always-record mutant passed | Three new `run_benchmark` tests: default raise, both wrong-mode cases (raise by default, NaN row with a non-empty `failure` under `record`), and `on_error="bogus"` |
| 4 | `metadata["noise_instructions"]` was pinned only for shape, on one-member engines; circuit-derived and first-member-only mutants passed | A two-member static ensemble whose models (`x` only, nothing) differ from the circuit's gates, asserting `[["x"], []]` in both modes |

**Non-blocking items, all in the same push:**

- Density mode raises `ValueError` when a measurement that is not final, or a control-flow
  operation, survives `remove_final_measurements`, on both the engine and the reference
  paths. The four benchmark circuits are unaffected (checked).
- `build_reference` raises when the model it would return is ideal (`NoiseModel.is_ideal()`),
  in either scope. Aer silently drops an ideal `ReadoutError`, so a `full_device` model on a
  qubit with `p01 = p10 = 0` and no timed gate is ideal too, and such a qubit no longer counts
  in `qubits_used`.
- `_is_dead_cz` reads `gate_error` with `missing_ok=False`: an absent, null or NaN value, or
  `parameters: []`, raises in `full_device` scope. All 352 `cz` entries in the fixture carry
  a finite one.
- The reference path copies `noise_instructions` per circuit instead of sharing one list.
- `tests/test_metrics.py` restores `main`'s mixed-argument rejection pins, parametrized over
  which side is wrong, for all four metrics.
- The readout-orientation pin gains the prepared-|1> row.
- The identical-members pin compares `make_benchmark_ensemble(3)` with `(1)`, so it now
  depends on the harness's equal-states fast path (a mutant that always averages fails it),
  and says it holds only while members are identical, which after #64 means only under
  `IdentityPerturbation`.
- Records: the GHZ `1 - R²` floor disclosure, the `s_gamma` label, the "neither TSV"
  sentence and the GHZ ratio in the evidence README; the two `sx`-length divergences, the
  "raises where `training.targets` raises" and "partition" sentences, and the numstat check
  in this document; an ADR-021 as-of note (the harness conforms); an outstanding item in
  `docs/advisor/2026-09-03-decisions-from-akba.md` for the advisor read of the #58 notes;
  two corrections in the 2026-09-06 record's as-of section (the ordering claim, the
  LOCKED-check base); docstrings for the seed contract, the metadata keys, the error
  contract, the `dead_pairs` scope and the density-mode readout caveat.

**GHZ `1 - R²` floor, re-measured.** With the script's own helpers and seed schedule,
replicate `i = 29` (seeds 116 and 117) saw only `000` and `111` in both samples and gives
`0.6944444444444444`; the next largest of the 32 is `0.0027781047281375537`. The floor's
mean, SD and threshold reproduce the TSV exactly (`0.39026195729900492`); without that pair
the threshold would be `0.0028401517181451323`. GHZ's between-model `1 - R²` stays below
`7.4e-6` at every rung, so no verdict changes.

**Mutation checks added this round** (each restored from a backup copy):

| Mutation | Tests that failed |
| --- | --- |
| `save_density_matrix` appended before `prepare()` | the ordering pin |
| `run_benchmark` always records | 4 tests (default raise, both wrong-mode cases, unknown `on_error`) |
| density metadata read from the circuit's gates | 2 tests |
| counts metadata kept for the first member only | the two-member metadata pin (counts) |
| reference metadata list shared across circuits | the per-circuit copy pin |
| equal-states fast path removed | the identical-members pin |
| density-mode guard for a non-final `measure` disabled | 2 tests (engine and reference paths) |
| `build_reference`'s ideal-model guard disabled | the no-timed-gate pin |
| an ideal readout error counted as a used qubit | the `qubits_used` pin |
| `_is_dead_cz` back to `missing_ok=True` | 4 tests (empty, absent, null, NaN `gate_error`) |

Measured on 2026-10-23 (Mert's laptop, Python 3.12.10, pinned stack, provisional): 964
collected and 964 passed with nothing skipped; the promoted-warning run 120 passed; ruff,
format, `mypy --strict` and `check_ids` clean; `git diff --numstat origin/main --
docs/decisions.md` shows 0 deleted lines. The differential against `main` @ `6cf008d`'s 859
is now +105: +63 from 2026-09-06, +17 on 2026-10-21 and +25 this round.

**FYI for #62, not measured here.** Burak's quick check suggests that even 8 members with
`reference_shots=32768` only just resolves GHZ Hellinger at `8 s_gamma`, and QFT never; that
is his figure, not one this record re-measured. What this record does show is that at 4096
shots counts mode resolves no cell up to `8 s_gamma`, while density mode resolves every rung.

## Related docs

- `docs/implementations/2026-09-06-benchmark-instrument-certification.md`: the
  certification this completes.
- `docs/evidence/resolution-measurement/README.md`: both runs, commands and hashes.
- ADR-016, ADR-017, ADR-022, ADR-027 and ADR-028 in `docs/decisions.md`.
- Issue #58; PR #79 comments 5585406092 (skip rules) and 5885110245 (merge findings).
- Issues #57, #59, #62, #64 and #73; PRs #69, #96, #113 and #120.
