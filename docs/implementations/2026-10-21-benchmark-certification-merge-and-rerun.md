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
`7.600232779751463e-05`, re-measured by two routes (the target module and the closed form
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
ladder are 3.31, 3.55, 3.73, 3.85, 3.92, 3.96, and GHZ's run from 3.11 to 3.93. That
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
  qubits; a missing duration belongs to a `(gate, qubits)` entry. Mixing the two would make
  `qubits_used` and `skipped` stop partitioning the selection.
- **Corrupt still raises.** A null, non-numeric, non-finite or wrongly-unit gate length
  raises in the reference exactly where `training.targets.gate_lengths` raises, which is
  also where ADR-028 fails loudly. A non-list `parameters` on a one-qubit gate is a missing
  record, as `gate_lengths` reads it.
- **Dead-pair reading stays strict** (from the pre-push review). A `cz` entry with no
  `parameters` list raises in `full_device` scope, as it did on 2026-09-06. The lenient
  reading is justified for `gate_length`, which `training.targets` also reads leniently, but
  not for `gate_error`, which no target code reads; treating it as "not dead" would drop the
  pair from `dead_pairs` with no signal.
- **Stricter structure than the loader.** Duplicate fields or a non-mapping entry on a qubit
  raise in the reference, while `load_snapshot` keeps the last duplicate. Stated in the
  module docstring; the cross-module test does not exercise it.
- **The intended divergence is pinned, not hidden.** A missing `sx` length rejects the
  qubit in `qubit_targets` (`gate_length_missing`) but only the `sx` entry in the reference;
  `test_missing_sx_length_is_qubit_level_in_targets_and_gate_level_here` asserts both sides.
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
git diff origin/main -- docs/decisions.md | grep "^-" | grep -vc "^---"
```

Expected: the suite passes; the promoted-warning run passes (it had 17 failures before
these fixes); collection is `main`'s count plus this PR's differential; the last command
prints `0` (the ledger diff is additions only).

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

## Related docs

- `docs/implementations/2026-09-06-benchmark-instrument-certification.md`: the
  certification this completes.
- `docs/evidence/resolution-measurement/README.md`: both runs, commands and hashes.
- ADR-016, ADR-017, ADR-022, ADR-027 and ADR-028 in `docs/decisions.md`.
- Issue #58; PR #79 comments 5585406092 (skip rules) and 5885110245 (merge findings).
- Issues #57, #59, #62, #64 and #73; PRs #69, #96, #113 and #120.
