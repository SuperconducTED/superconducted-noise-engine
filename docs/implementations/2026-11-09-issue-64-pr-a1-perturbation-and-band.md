# 2026-11-09: issue-64-pr-a1-perturbation-and-band

**Issue**: #64 PR-A1 · **Author**: Mert · **Owner and approver**: @bengisucvd · **Base**: `main` @ `d929424a` ·
**Status**: plan, written before any code. The results are appended below it when the work is done.

## Problem / Motivation

Today every member of `FuzzyNoiseModelEnsemble` is built from identical inputs, so an "ensemble" of N members is N
copies of one model and its spread is zero by construction (ADR-015 open, ADR-016 open). #64 adds a way to make members
differ for a measured reason and a way to report and score an interval. Its PR-A was planned on 2026-10-23
(`docs/roadmap/2026-10-23-issue-64-pr-a-plan.md`, on `main` through PR #121) and split in two: PR-A1, the mechanism,
the seeding, the band and the coverage metric, touching no harness file; PR-A2, the harness interval mode. Bengisu's
answers to D1 to D5 and her new D2b are in #64 comment 6706908485 (2026-11-07), with a dated correction in 6727434243
(2026-11-09) that changes no decision. This document plans PR-A1 under those answers.

## Decisions in force

| Decision | Value | Source |
| --- | --- | --- |
| D1, jitter form | additive Gaussian with relative scale, `x_i = x + r |x| z`, redraw on a bound violation, never clip | 6706908485 |
| D2, band | `alpha = 0.1`, `N = 32`, fixed before `r` is fitted; `alpha` is the caller's argument, never a hidden default | 6706908485; plan section 12 |
| D2b, what "80%" means | both outputs at least 80%, the smallest `r` that does it; applied in the fitting script, not in PR-A1 | 6706908485; accepted by the lead 2026-11-09 |
| D3, scoring rows | `change` primary, `distinct` beside it, `all` only as a vacuity check; the fitting script's concern, not PR-A1's | 6706908485 |
| D4, `per_qubit_spread` | out of PR-A; PR-A1 carries dated notes where the code and the register still say #64 adds it | 6706908485; the lead 2026-11-09 |
| D5, ownership of `integration/perturbation.py` | Bengisu owner, Mert secondary | 6706908485 |
| The split | kept: PR-A1 touches no harness file, although #79 merged as `a0ea1161`; PR-A2 follows | the lead 2026-11-09 |
| Units | SI seconds for `mean_T1`, `mean_T2`; `mean_readout_error` dimensionless (`BasicCalibrationVectorizer`, since #66) | `calibration/features.py` line 76 |

The ticket's FR-3 (`per_qubit_spread`) and FR-4's `from_snapshot(..., factor=1.0)` are not built: File 03 replaced the
`s_q` scale with one drift scale per arm, and D4 keeps the helper out.

## Plan: what will change

| File | Change |
| --- | --- |
| `src/superconducted/interfaces.py` | `MemberPerturbation` ABC as the ticket's FR-1: `perturb(index, rng, *, feature_extractor, rule_base, defuzzifier) -> (extractor, rule_base, defuzzifier)`, pure and non-mutating. |
| `src/superconducted/integration/perturbation.py` (new) | `IdentityPerturbation`; `OffsetFeatureExtractor`; `InputVectorPerturbation(scale, *, bounds, max_redraws=64)` with `InputVectorPerturbation.relative(x, r, *, feature_names)`. |
| `src/superconducted/integration/aer_factory.py` | `FuzzyNoiseModelEnsemble(..., perturbation=None)`: child seed sequences spawned once at construction, a fresh generator per member per iteration, `ValueError` for an unseeded non-identity perturbation, the module docstring's status line updated. |
| `src/superconducted/benchmarks/metrics.py` | `IntervalBand`, `interval_band(members, *, alpha, method="linear")`, `IntervalCoverage`. |
| `tests/test_perturbation.py`, `tests/test_interval_band.py`, `tests/test_aer_serialises_once.py` (new) | The tests below. |
| `scripts/feature_distribution.py` lines 27 to 28 and 67, `tests/test_feature_distribution.py` line 90, `docs/numerical-claims.md` NC-042's note | Dated notes (D4): #64 does not add `per_qubit_spread`; the `ddof=1` statement stays as written. |
| `docs/team.md` | One ownership row: `integration/perturbation.py`, Bengisu, Mert. |
| `docs/evidence/issue-64-pr-a1-acceptance/` (new) | The acceptance run's script, its sensitivity check and output. |
| This document | The plan now; the results appended after. |

Not touched: `fuzzy/tsk.py` and `channels/kraus.py` (LOCKED), `benchmarks/harness.py`, `benchmarks/circuits.py`,
`benchmarks/reference.py`, `types.py`, any ADR text.

## Implementation approach

Order of work, each step with its tests first:

1. **The identity pin**, captured on `main`'s code before any wiring changes: with today's ensemble, the members'
   `crisp_params` for a fixed snapshot and seed, and `rho_ens == rho_1` for identical members (the ticket's FR-2).
2. `MemberPerturbation`, `IdentityPerturbation`, and the ensemble's seeding: `self._seed_seqs =
   self._rng.bit_generator.seed_seq.spawn(n)` at construction, `np.random.default_rng(self._seed_seqs[i])` per member in
   `__iter__`, never `Generator.spawn` (the ticket's FR-6 note shows why: stored generators are consumed by drawing).
3. `OffsetFeatureExtractor` and `InputVectorPerturbation`, with the redraw tests.
4. `IntervalBand`, `interval_band`, `IntervalCoverage`, and ADR-022's six properties as named tests.
5. The `to_dict` once-per-run guard (`shots=1024`, automatic and density-matrix methods), pinning the behaviour of the
   pinned qiskit-aer 0.17.2, not the version.
6. The acceptance run (below), on the laptop, provisional.
7. D4's notes, D5's row, mutation check of every new guard, gates, this record's results.

## Mathematical / Statistical details

**Jitter.** For the extractor's output `x` in `R^d` and a member `i`, draw `z ~ N(0, I_d)` from the member's generator and
set `x_i = x + s * z` with `s = r |x|` (elementwise) for one scalar `r > 0` per arm (File 03 Q2a). Bounds per feature:
`mean_T1`, `mean_T2` in `(0, inf)`, open at 0; `mean_readout_error` in `[0, 1]`. A draw with any component outside its
bound is discarded and redrawn, up to `max_redraws`, then `ValueError`. Clipping would pile members on the boundary
and narrow the band; the redraw keeps the members a truncated Gaussian. The member's extractor returns `x_i` by adding
the fixed offset `x_i - x` to the wrapped extractor's output.

**Band.** For members' probability vectors `p_1 ... p_N` over the union support `S` (all outcomes seen by any member or
the reference), per bin `b`: `L(b) = Q_alpha({p_i(b)})`, `U(b) = Q_(1 - alpha)({p_i(b)})`, with `np.quantile(...,
method=method)` and `0 <= alpha < 0.5`; `alpha = 0` is the min/max band. `alpha` and `method` are stored on the band.

**Coverage.** `C = sum_{b in S} q(b) 1[L(b) <= q(b) <= U(b)]`, with `q` the reference probability vector: the reference
mass inside the band, inclusive at both edges (the ticket's section 6.3, mass-weighted for the GHZ argument). `C` is in
`[0, 1]`. The self-similarity value is `C(interval_band([q, q], alpha=0), q) = 1`.

**What the band is not.** Gaussian jitter pushed through a nonlinear TSK base does not make the members a calibrated
predictive sample, so `alpha = 0.1` does not make the band an 80% interval by itself; the 80% is earned by fitting `r`
(D2, D2b), which is the fitting script's job and not PR-A1's. With `N = 32` and numpy's linear quantile, a further
exchangeable draw falls inside the central band with probability about `0.8 (N - 1)/(N + 1)`, about 0.75, exact only
under the condition in 6727434243; inside the min/max band with probability exactly `(N - 1)/(N + 1)`.

## Design decisions

- **The scale is a required argument with no default** (File 03 Q2a; the plan's section 1): no code path picks `r`,
  and no record can carry a hidden one. `relative(x, r, ...)` needs `r` too.
- **`alpha` is required in `interval_band`**, where the ticket's FR-8 defaulted it to 0: D2 fixes it with `r` as one
  pair, so a default would let a band be built without saying which pair it belongs to.
- **The split is kept** although #79 merged: two small reviews, the identity pin captured on its own tree, and PR-A2's
  regression pin captured on a tree with PR-A1 merged and PR-A2 not applied.
- **`IntervalCoverage` does not subclass `BenchmarkMetric`**, whose `compute` takes two `SimulationResult`s (the ticket's
  FR-9; its section 7 decision 2, no second ABC).
- **D4's notes go in PR-A1**, because D4 is decided here and the four places point at #64.

## Acceptance criteria

| # | Criterion |
| --- | --- |
| 1 | With `perturbation=None` and with `IdentityPerturbation`, the members' `crisp_params` are bit-identical to the pin captured on `main` before the wiring changed, and `rho_ens == rho_1` holds for identical members. |
| 2 | `MemberPerturbation.perturb` does not mutate its inputs (equal before and after), and the returned objects keep `output_dim`, `feature_names` and `input_dim`. |
| 3 | Iterating one perturbed ensemble twice gives identical members; `build(seed)` in `first_viable_seed` stays a pure function of the seed; `len()` is unchanged; a non-identity perturbation with `rng=None` raises `ValueError`. |
| 4 | `InputVectorPerturbation` has no default scale and `relative` no default `r`; a generator whose first draw breaks a bound produces a redraw, not a clipped value; `max_redraws` exhausted raises `ValueError`; the offset, scale and `r` are read-only. |
| 5 | `interval_band` requires `alpha`, rejects `alpha` outside `[0, 0.5)`, fewer than two members and mixed modes; `IntervalBand` enforces `lower <= upper`, both in `[0, 1]`, and matching lengths; `alpha` and `method` are stored. |
| 6 | `IntervalCoverage` passes ADR-022's six properties as named tests (identity, symmetry or asymmetry stated, bounds, monotonicity, determinism, a hand-derived reference value), including the ticket's hand-derived 0.65 example and the self-similarity value 1. |
| 7 | The `to_dict` guard: one call per multi-shot run on qiskit-aer 0.17.2, automatic and density-matrix methods. |
| 8 | The acceptance run: the ratified 3x3x3 Gaussian grid on a real archived `ibm_fez` snapshot at a pinned `calibration-data` ref, in SI units, `N = 32`, `relative(x, r_smoke)`. The engine's sensitivity (change in `crisp_params` per unit change in each feature) is measured first and `r_smoke` chosen from it, both written down before the run; the perturbed members' `crisp_params` are not all equal, the identity ensemble's are, and two constructions with one seed agree bit for bit. `r_smoke` is labelled a smoke value. |
| 9 | `git diff --stat main` is empty for `fuzzy/tsk.py`, `channels/kraus.py`, `benchmarks/harness.py`, `benchmarks/circuits.py`, `benchmarks/reference.py` and `types.py`. |
| 10 | D4's four dated notes and D5's row are in; every new public symbol states its units and contract in its docstring. |
| 11 | Every new guard is mutation-checked, with predictions written before the run and each mutant caught or shown equivalent; ruff, `ruff format --check`, `check_ids.py`, `mypy --strict` and `pytest tests/` pass on the exact pins. |

## Owed before merge

- @bengisucvd's approval (owner of `metrics.py` and of the new module).
- Burak's read of `aer_factory.py` (his module).
- The primary owner's read of `interfaces.py`, Dr. Akba's (the ticket's FR-1: "Do not merge PR-A on @mertefesensoy +
  @BurakOztekin alone"). How it is met, by his read or by the lead's under the advisor arrangement, is the lead's
  decision, written in the PR; this plan assumes neither.
- NC-021 re-measured at the merge commit (Rule 6).

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_perturbation.py tests/test_interval_band.py tests/test_aer_serialises_once.py -v
ruff check . && ruff format --check . && mypy --strict && python scripts/check_ids.py
git diff --stat main -- src/superconducted/fuzzy/tsk.py src/superconducted/channels/kraus.py src/superconducted/benchmarks/harness.py src/superconducted/benchmarks/circuits.py src/superconducted/benchmarks/reference.py src/superconducted/types.py
```

The acceptance run's command, seed and `calibration-data` ref go in `docs/evidence/issue-64-pr-a1-acceptance/README.md`.

## Related docs

- Issue #64 (body, its first comment for sections 9 to 12), comments 6366176028, 6706908485, 6727434243.
- `docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` (sections 2, 5, 11, 12) and
  `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`.
- ADR-002, ADR-012, ADR-015, ADR-016, ADR-021, ADR-022, ADR-024, ADR-027 in `docs/decisions.md`.
- #84 comment 5970300012 (File 03); PR #121; PR #123 (the scoring-row protocol); #79 (`a0ea1161`).

## Update, 2026-11-11: the base moved before any code

The plan above was written on `main` @ `d929424a`. Before the first line of code, `main` had moved to
`cd277a64` (PR #144, PR #146 and PR #136). It was merged into this branch as `29e4b93d`, so every step
below is built and measured on `cd277a64`'s code, and that is the tree the identity pin of step 1 was
captured on. PR #136 is the one that touches a file of this plan: it changed `FuzzyNoiseModel.prepare`'s
error handling in `aer_factory.py`. It did not touch `FuzzyNoiseModelEnsemble`, which is the class step 2
changes. The plan's decisions and acceptance criteria are unchanged.

## Results, 2026-11-11: steps 1 and 2 (laptop, provisional)

Environment: Python 3.12.10, NumPy 2.4.4, Qiskit 2.4.1, qiskit-aer 0.17.2, pytest 9.0.3, ruff 0.15.12,
mypy 1.20.2, installed from the pins. Nothing below has run on Burak's desktop.

### Step 1: the identity pin (commit `75b86dbb`, tests only)

Five tests in `tests/test_perturbation.py`, section 1, written and committed before `aer_factory.py`
changed, so history shows them passing on `cd277a64`'s `__iter__`.

| Test | What it pins |
| --- | --- |
| `test_the_pinned_seed_is_the_first_viable_one` | `first_viable_seed` returns seed 1 for this grid on the gate-bearing `ibm_fez` fixture, and `build(seed)` gives the same members twice. |
| `test_every_member_equals_a_directly_built_model` | Each member's `crisp_params` is bit for bit the `crisp_params` of a `FuzzyNoiseModel` built directly from the same seven dependencies. |
| `test_members_match_the_values_captured_before_the_wiring_changed` | The members' `crisp_params` equal `(0.0010631876854835232, 0.018299147946441743)` to a relative `1e-9`. |
| `test_iterating_twice_gives_the_same_members` | Two passes over one ensemble agree bit for bit. |
| `test_identical_members_preserve_the_density_matrix_exactly` | `rho_ens == rho_1` (Issue #58 section 6.3) through `simulate_engine` in density-matrix mode. |

**A deviation from criterion 1's wording, stated here for the reviewers.** Criterion 1 says "bit-identical
to the pin captured on `main`". The bit-identical part is the relational test (the second row), which is
exact on any machine. The captured literal (the third row) is held to a relative `1e-9` and not to the
bit, because the laptop and the desktop have differed in the last digits of other quantities (PR #149's
evidence shows relative differences up to 3.7e-14 between them). The tolerance is nine orders of
magnitude tighter than a relative jitter of 1e-3 moves a member, so it cannot hide a perturbed default.

Mutation check on the unmodified tree, predictions written first: scaling every model's `crisp_params`
by `1 + 1e-6` fails the literal pin only (as predicted, the relational pin cannot see a change that hits
both sides); scaling members 1 and later by the same factor fails the relational pin, the literal pin
and the density-matrix pin.

### Step 2: the interface, the identity and the seeding

| File | Change |
| --- | --- |
| `src/superconducted/interfaces.py` | `MemberPerturbation` ABC, with FR-1's signature and its contract in the docstring. |
| `src/superconducted/integration/perturbation.py` (new) | `IdentityPerturbation`: returns its three inputs themselves, reads no randomness. |
| `src/superconducted/integration/aer_factory.py` | `FuzzyNoiseModelEnsemble(..., perturbation=None)`; child seed sequences spawned once at construction; `_perturbed(index)` builds a fresh generator per member per pass and checks the returned shapes; the module and class docstrings updated. |
| `src/superconducted/__init__.py` | `MemberPerturbation` re-exported; the docstring's count moves from eleven ABCs to twelve. |
| `tests/test_interfaces.py` | `MemberPerturbation` added to the ABC list; the count guard moves from 11 to 12. |
| `tests/test_perturbation.py` | 32 test cases, up from 5. Section 1's four parametrised tests now also run under `perturbation=None`, `IdentityPerturbation()` and a seeded `IdentityPerturbation()`, with their bodies unchanged (12 more cases); sections 2 and 3 add 15. |

**How the seeding works.** At construction the ensemble calls `rng.bit_generator.seed_seq.spawn(n)` once
and stores the `n` child `SeedSequence` objects. Each pass of `__iter__` builds
`numpy.random.default_rng(child_i)` for member `i` and hands it to `perturb`. A seed sequence is not
consumed by drawing, so a second pass rebuilds the same generators and yields the same members; a stored
`Generator` would not (the ticket's FR-6 note, and mutant W01 below). Spawning draws nothing from the
caller's stream, so the caller's generator produces the numbers it would have produced. It does advance
the seed sequence's spawn counter, so two ensembles built from the *same generator object* get different
children. Two ensembles that must match are built from two fresh `default_rng(seed)` objects, which is
what `build(seed)` in `first_viable_seed` does.

**Three things in the code that the plan did not list.** Each is small; each is for the reviewers to
accept or send back.

1. **`src/superconducted/__init__.py` and the count guard.** `tests/test_interfaces.py` pins the number of
   exported ABCs and the count written in the package docstring. A twelfth ABC fails that guard until
   both say twelve and the root re-exports it. No register row states the count.
2. **The shape check in the ensemble.** FR-1's contract says the returned extractor keeps `output_dim` and
   `feature_names` and the returned rule base keeps `input_dim` and `output_dim`. `_perturbed` checks those
   four where the tuple is consumed and raises `ValueError` naming the perturbation and the member. With
   any one check removed, the matching case (a renamed feature vector, an extractor claiming four outputs,
   a rule base with other dimensions) no longer raises that `ValueError` (mutants W08 to W11). This is in
   Burak's module and is his to read.
3. **A generator whose seed sequence cannot spawn.** `numpy.random.Generator` accepts a bit generator
   seeded with an object that has no `spawn`. The ensemble raises `ValueError` at construction for it,
   in place of an `AttributeError` from inside the constructor. This also applies with no perturbation,
   which is the one way the default path is stricter than before; every generator made with
   `default_rng` can spawn.

**Mutation check** (`tests/test_perturbation.py` only; predictions written in the script before the run;
sources restored from backup copies after each mutant). All sixteen were killed. W10 was predicted
"unknown" because `tsk.py` might have raised its own matching error; it does not.

| Mutant | Killed by |
| --- | --- |
| W01 stored `Generator.spawn` generators | the two-pass test |
| W02 the unseeded raise removed | the unseeded test |
| W03 the unseeded raise also fires for the identity | section 1 and the unseeded test (14 cases) |
| W04 member `i` perturbed from member `i - 1`'s extractor | the base-objects test and two more |
| W05 the returned tuple ignored | the members-differ test |
| W06 the caller's generator handed to `perturb` | the spawned-children and untouched-stream tests |
| W07 every member seeded from child 0 | the own-stream test |
| W08 to W11 one of the four shape checks removed | the contract test, one case each |
| W12 children spawned from an unseeded generator | the spawned-children and two-constructions tests |
| W13 index 0 passed for every member | the index test |
| W14 the identity draws once | the draws-nothing test |
| W15 one child too many spawned, the first skipped | the spawned-children test |
| W16 the no-spawn check removed | the no-spawn test |

**Gates at this point**: `ruff check .`, `ruff format --check .`, `mypy --strict` (50 source files) and
`scripts/check_ids.py` clean; the six files of criterion 9 show no difference against `origin/main`;
`python -m pytest tests/ -q -p no:cacheprovider`: 1211 passed in 540 s, which is `main`'s 1177 at
`cd277a64` plus 34 (32 in `tests/test_perturbation.py`, 2 from the new entry in `tests/test_interfaces.py`'s
ABC list).

### Open before step 3: where the unperturbed vector comes from

FR-1's `perturb` receives the extractor but no snapshot, so it cannot extract `x` itself, and the plan's
constructor `InputVectorPerturbation(scale, *, bounds, max_redraws=64)` holds no `x` either. Yet the
redraw rule tests `x + scale * z` against the bounds, and the member's offset is `x_i - x`. The ticket
(its `from_snapshot` factory had the snapshot) and its comments do not settle this for the form the plan
adopted. Step 3 waits for the owner's and the lead's answer; steps 4 and 5 do not depend on it.

**Asked, 2026-11-11.** The lead sent the question to the owner as decision D6 in #64 comment 6789691655,
with two options: the perturbation holds `x` (recommended there), or `x` is read at extraction time.
Step 3 starts when she answers.

## Results, 2026-11-11: step 4, the band and the coverage metric (laptop, provisional)

Same environment as steps 1 and 2. Nothing below has run on Burak's desktop.

| File | Change |
| --- | --- |
| `src/superconducted/benchmarks/metrics.py` | `IntervalBand` (frozen value), `interval_band(members, *, alpha, method="linear")`, `IntervalCoverage`; two private helpers, `_outcome_probabilities` and `_check_alpha`; two tolerances for density matrices. The four existing metrics are untouched. |
| `tests/test_interval_band.py` (new) | 75 test cases in four sections: the band, the value's invariants, ADR-022's six properties, edges and input checks. |

### What was built, and the mathematics behind three choices

**The band.** Members' probability vectors `p_1 ... p_N` are laid on the sorted union of their outcomes
(a member that never saw an outcome has probability 0 there), and per outcome `L = Q_alpha`,
`U = Q_(1 - alpha)` through `numpy.quantile(..., method=method)`. `alpha` is a required keyword;
`alpha`, `method` and `n_members` are stored on the band.

**Choice 1: the `alpha = 0` band is exactly min and max.** PR-A2's invariant (the sum aggregate lies inside
the `alpha = 0` band) needs the edges to be members' own values, with no interpolation residue. NumPy
gives that for the default `linear` method: over 20,000 random count tables (2 to 39 members, 1 to 5
outcomes, NumPy 2.4.4) the 0 and 1 quantiles equalled the per-outcome minimum and maximum bit for bit
every time, and no table gave `L > U` or a central band outside the min/max band (`quantile_probe.py`).
For the other twelve methods NumPy accepts, the min/max equality was checked on 3,000 tables each and
held every time (`methods_probe.py`); the `L <= U` and nesting checks were run for `linear` only. Both
probes are to be committed with the evidence in step 7, and a test pins the min/max equality on 200
tables for each of the thirteen methods.

**Choice 2: coverage is a ratio of masses, not a sum of probabilities.** The ticket's section 6.3 defines
`C = sum_b q(b) 1[L(b) <= q(b) <= U(b)]` and promises `C(interval_band([q, q]), q) == 1.0` with no tolerance.
Summing normalised probabilities cannot keep that promise: seven outcomes of probability 1/7 sum to
`0.9999999999999998` under `numpy.sum`. So the code keeps two aligned arrays per result:

- `probabilities`, on which membership in the band is decided. For counts it is `count / total`, the
  same division for members and reference, so an identical member and reference compare equal bit for
  bit and the inclusive edges need no tolerance. For a density matrix it is the diagonal itself.
- `masses`, the unnormalised weights (the counts, or the diagonal), from which
  `C = fsum(covered masses) / fsum(all masses)`.

When every outcome is covered the two sums are the same number, so `C` is exactly 1.0. `C <= 1` holds
because the masses are non-negative: the covered masses are then a subset of non-negative terms, and
`math.fsum` is correctly rounded, hence monotone under adding non-negative terms. Non-negativity is
enforced, not assumed: a density matrix's diagonal is clamped at 0, and a negative count is refused with
`ValueError` (a `Counter` can hold one; without the refusal the reference `{"0": 3, "1": 3, "2": -1}` with
both positive outcomes covered scores 1.2, which is now a test). For counts both sums are exact integers, so `C` is the correctly
rounded value of a ratio of integers; the ticket's example gives `65 / 100`, which is the float `0.65`.

**Choice 3: a density matrix's diagonal is used as it is, with two stated tolerances.** The diagonal is
read in Qiskit's order (index `i` is the outcome whose bitstring is `i` in binary; rightmost character is
qubit 0), not renormalised. A value outside `[0, 1]` or off the real axis by at most `1e-12` is clamped;
beyond that the matrix is refused. A trace further than `1e-9` from 1 is refused. Both thresholds were
checked against what Aer returns here (`tolerance_probe.py`, 10 matrices: the engine on GHZ-2, GHZ-3 and
QFT-3 with 1 and 3 members, and four depolarizing references): no negative diagonal entry, largest
imaginary part `9.4e-18`, largest distance of the trace from 1 `2.4e-15`. So neither threshold fires on
these, with five to six orders of magnitude to spare, and the non-zero imaginary part shows an exact
"imaginary part is zero" test would have refused a real result. Ten matrices is a small sample; it shows
the thresholds are not tight, not that nothing can reach them.

**An outcome the band never saw** has the band `[0, 0]`: reference mass there is uncovered, and nothing
is dropped from the sum. **A reference on another register** (outcome keys of a different length from
the band's) raises `ValueError`; it would otherwise score a silent zero.

### ADR-022's six properties (criterion 6)

| Property | Test | What it shows |
| --- | --- | --- |
| 1 Identity | `test_adr022_property_1_identity`, seven references | `C == 1.0` exactly, including sevenths, primes, and a matrix whose trace is `1 + 1e-10` |
| 2 Asymmetry | `test_adr022_property_2_asymmetry` | a wide ensemble covers a narrow one's aggregate (1.0); the reverse is 0.0 |
| 3 Bounds | `test_adr022_property_3_bounds` | 300 random cases in `[0, 1]`, reaching 0, 1 and the interior |
| 4 Monotonicity | three tests | nested bands on 300 cases; Aer's depolarizing error exactly (members at `p` in 0.1 to 0.3: coverage 1 inside the range with the edges, 0 outside); the same at 20,000 shots with references more than 3 standard errors from an edge |
| 5 Determinism | `test_adr022_property_5_determinism` | two seeded runs give the same band and the same value |
| 6 Reference value | `test_adr022_property_6_reference_value` | the ticket's hand-derived example gives `0.65` exactly, and not the `0.75` a count of outcomes would give |

`IntervalCoverage` has `name == "interval_coverage"` and does not subclass `BenchmarkMetric` (the ticket's
FR-9), which a test asserts.

### Departures from the ticket's text, for the owner

1. **`method` is a field of `IntervalBand`.** FR-8 lists `support`, `lower`, `upper`, `alpha`, `n_members` and
   says the method name "is stored"; it is stored as a sixth field.
2. **`alpha` has no default** in `interval_band` (FR-8 wrote `alpha=0.0`). This is the plan's decision under
   D2 and was announced in #64 comment 6744024748.
3. **A central band is not widened to hold the member mean.** Bengisu's counterexample of 2026-10-26 (31
   members at 0.1, one at 0.9, `alpha = 0.1`) is a test here: the band is `[0.1, 0.1]` and the mean 0.125 is
   outside it.
4. **Density-matrix handling is new text**, since the ticket does not say how a diagonal becomes outcomes:
   Qiskit's bit order (pinned against `DensityMatrix.probabilities_dict` on an asymmetric state), the two
   tolerances above, the same-shape and power-of-two checks.
5. **`IntervalBand` copies and freezes its arrays**, as `TrainingSet` does and as issue #148 asks of the
   other value types.

### Mutation check

`tests/test_interval_band.py` only; predictions written in the script before the run; the source restored
from a backup copy after each mutant. All 34 were killed.

| Mutants | What was mutated | Result |
| --- | --- | --- |
| C01 to C07 | coverage: each edge made exclusive, an unseen outcome treated as covered, outcomes counted instead of mass, probabilities summed, a density reference divided by its trace, the key-length check removed | all killed |
| B01 to B14 | the band: quantile order swapped, `alpha` ignored, 0.5 accepted, each input check removed, bit order reversed, the clamp and each density-matrix check removed | all killed |
| V01 to V11 | the value: arrays not copied, not frozen, each of nine invariants removed | all killed |
| C05b | a plain `numpy.sum` of covered probabilities | killed by the sevenths identity case |
| N01 | the negative-count refusal removed | killed by both negative-count tests |

Two predictions were off (C05 and B05) and one held in a way worth writing down (B04):

- **C05** summed the covered probabilities with Python's built-in `sum`. On Python 3.12 that is a
  compensated sum for floats, so seven sevenths still gave 1.0 and the sevenths case did not fail; the
  mutant died on the trace case instead. C05b is the mutant that was meant.
- **B05** (the member-count check in `interval_band` removed) was predicted to survive for one member,
  because `IntervalBand` repeats the check with the same message. It was killed by the empty-list half of
  the same test. The one-member half is therefore covered twice, by design.
- **B04** (`interval_band` not checking `alpha` itself) fails five of the six bad values; `alpha = 0.5` is
  still refused with the right message by `IntervalBand`'s own check, as predicted.

**Gates at this point**: `ruff check .`, `ruff format --check .`, `mypy --strict` (50 source files) and
`scripts/check_ids.py` clean; the six files of criterion 9 show no difference against `origin/main`;
`tests/test_metrics.py`, `tests/test_harness.py` and `tests/test_interval_band.py` together: 146 passed.
With `tests/test_perturbation.py` and `tests/test_interfaces.py`, run at `df7353b6` before the two
tightenings above: 202 passed.

**The full suite was not completed for this step.** A run of `python -m pytest tests/ -q -p no:cacheprovider`
started at `df7353b6` was still inside the slow archive test (`tests/test_feature_distribution.py`, one
`git show` per archived file) after 50 minutes, against about 5 minutes in the morning's runs, while
other processes on the laptop were running git at the same time. Its log is `suite-step4.log` in the
scratch evidence folder. Nothing in `metrics.py` is imported by a module outside the tests named above
and `scripts/resolution_measurement.py`, which uses the three older metrics only. The full suite on the
exact pins remains criterion 11's gate at step 7; the expected count there is 1211 + 75 for this step.

**Later the same day: that run finished.** `1272 passed in 7333.27s (2:02:13)`, at `df7353b6`. That is
1211 plus the 61 cases the test file had at that commit, as expected. It does not cover `ba675ec0`, which
added 14 cases and the negative-count refusal; those were run directly (75 passed). The two hours were
spent almost entirely in the archive test.

## Results, 2026-11-11: step 5, the `to_dict` guard (laptop, provisional)

| File | Change |
| --- | --- |
| `tests/test_aer_serialises_once.py` (new) | 13 test cases. No source file changes in this step. |

**What it guards.** ADR-002's invariant is that Aer has no per-shot Python hook: `NoiseModel.to_dict` runs
once at submission and the C++ controller takes over. Until now that was a sentence in
`integration/aer_factory.py`'s docstring. The test measures it.

**Measured first, asserted second** (`to_dict_probe.py`, qiskit 2.4.1, qiskit-aer 0.17.2). A spy on the
class attributes `NoiseModel.to_dict` and `QuantumError.to_dict` counts calls on any instance, including a
copy Aer might make:

| Case | `NoiseModel.to_dict` calls | `QuantumError.to_dict` calls |
| --- | --- | --- |
| a direct call (the spy fires) | 1 | 1 |
| one circuit, a one-error model, 1, 1024 and 8192 shots; automatic and density-matrix methods; model passed to `run` or to the constructor (12 runs) | 1 each | 1 each |
| the harness's state mode (`save_density_matrix`, `shots=1`) | 1 | 1 |
| no noise model, 1024 shots | 0 | 0 |

At 1024 shots the non-ideal outcome appeared 136 times, so the one serialised model acted in many shots.
The call sits in `qiskit_aer/backends/backend_utils.py::cpp_execute_circuits`.

**The tests.**

| Section | Tests | What they pin |
| --- | --- | --- |
| 1 The spy and the guard can fail | 3 | a direct call is counted; no noise model gives 0; a runner that serialises once per shot trips the guard's own assertion |
| 2 Aer itself (criterion 7) | 6 | one serialisation in a 1024-shot run, for both methods and both ways of passing the model, with the noise visible in the counts; the count is the same at 1, 1024 and 8192 shots |
| 3 The engine through the harness | 4 | three members and two circuits are six runs and six serialisations, in counts mode at 1 and 1024 shots and in density-matrix mode; the per-error count is the same at 1 and 1024 shots |

They pin the behaviour and not the version: nothing asserts `qiskit_aer.__version__`. Each run holds one
circuit, which is how the project runs Aer since the batching defect recorded as NC-097. (The probe also
ran two circuits in one `run()`: still one `to_dict` call. No test pins that.)

**Can the guard fail?** The thing under guard is Aer, so the mutants change Aer for one test session
through a pytest plugin (`aer_mutant_plugin.py`), replacing the name `cpp_execute_circuits` inside
`qiskit_aer.backends.aer_simulator`. No installed file is edited. Predictions were written first and both
held:

| Simulated Aer | `to_dict` calls in one 1024-shot run | Result |
| --- | --- | --- |
| unchanged | 1 | 13 pass |
| one more serialisation per run | 2 | 10 of 13 fail: all of sections 2 and 3. Section 1 passes, as predicted, because it never runs a noise model through Aer. |
| one more serialisation per shot | 1025 | the same 10 fail |

**A correction to the first run of this check.** The first version of the per-shot simulation took the
shot count from the assembled circuits, where it is 1, so it made one extra call per run and was the same
mutant as the row above it. It failed the same ten tests, and with tracebacks switched off the names
alone could not show that. An advisor pass asked for the counts; `mutate_step5_counts.py` printed 2 where
1025 was claimed. The plugin now reads the run's config, the count is 1025, and the ten tests fail as
before. The middle column above is from that corrected run.

**What this does not show.** It counts Python-level calls of `to_dict`. It says nothing about what the
C++ controller does with the serialised model per shot, which is ADR-002's point: sampling the error
happens there. A future Aer that reached the model through another Python method would not be seen by
this spy; the test would then still pass with one `to_dict` call.

**Gates at this point**: `ruff check .`, `ruff format --check .`, `mypy --strict` (50 source files) and
`scripts/check_ids.py` clean; the six files of criterion 9 show no difference against `origin/main`;
`tests/test_aer_serialises_once.py`, `tests/test_interval_band.py` and `tests/test_perturbation.py`
together: 120 passed. The full suite was not re-run for this step, which adds a test file and changes no
source; the expected count at step 7's gate is 1211 + 75 + 13 = 1299 before step 3's tests.

## Results, 2026-11-11: the parts of step 7 that do not wait on step 3

Step 7 has four parts. Three are done here; the fourth (the final gates and this record's last results)
comes after steps 3 and 6.

### D4's four dated notes (criterion 10), commit `1cc60374`

Bengisu's D4 keeps `per_qubit_spread` out of PR-A. Four places still said #64 adds it. Each now carries a
dated note under the original text, which is left as written; no value changes.

| Place | Note |
| --- | --- |
| `scripts/feature_distribution.py`, module docstring | #64 does not add `per_qubit_spread`; the function named there does not exist; the `ddof=1` statement stands |
| `scripts/feature_distribution.py`, the comment above the private import | there is nothing to import instead, so the private import stays |
| `tests/test_feature_distribution.py::test_compute_stats_uses_ddof_one_not_ddof_zero`, docstring | the pin stands on its own |
| `docs/numerical-claims.md`, NC-042's note | the same statement; the value and the "Last verified" date are unchanged |

`tests/test_feature_distribution.py` without its slow archive test: 27 passed. `scripts/check_ids.py` clean.

### D5's ownership row (criterion 10), commit `1cc60374`

`docs/team.md` names Bengisu as primary owner of `integration/perturbation.py` and Mert as secondary, in
the module-ownership table and in her list of primary modules.

### The evidence folder (criterion 11), commits `95c2d69f` and the one after it

`docs/evidence/issue-64-pr-a1-acceptance/` now holds the thirteen check scripts of steps 1, 2, 4 and 5 and
the outputs of their runs. The scripts went in first, at `95c2d69f`, with no output; every `*.out.txt`
comes from a run of the committed copy after that commit, because the first runs were made from a session
scratch folder and are not evidence. The folder's `README.md` lists each script, its command, what a pass
looks like and what it gave.

All of them reproduced the scratch results: the pin's values; 2 of 2, 16 of 16 and 32 of 32 mutants
behaving as recorded, plus C05b and the negative-count mutant; the three step 4 probes; one `to_dict` call
per run; and 1, 2 and 1025 calls under the two simulated Aer behaviours. One of the step 1 script's two
mutants (M2) edits the old `__iter__`, which step 2 replaced, so that script was run in a throwaway
checkout of `75b86dbb`; the other (M1) edits `_compute_crisp_params` and is not tied to that commit. No
source file was left modified.

**A correction, the same day.** The first version of two of D4's notes (the script's module docstring and
NC-042's note, both in `1cc60374`) added that the script "stays the only home of the statistic". That is
false: `training/dataset.py` computes the same `*_qubit_std` with `ddof=1` for the training set's rows. The
check behind the sentence had searched for the name `per_qubit_spread`, not for the statistic. The clause
is removed in the commit that carries this paragraph; the notes now say only what D4 decided.

Two things changed between scratch and folder, neither affecting a mutant or a prediction: the scripts
were renamed and made to pass ruff, and the step 4 mutation run is now on the test file's 75 cases (the
scratch run was on 61, before the negative-count refusal and the per-method min/max test).

The folder does not hold the acceptance run of criterion 8, which is step 6.

### Where the criteria stand after this

| # | Criterion | State |
| --- | --- | --- |
| 1 | identity pin | met, with the stated deviation (relational pin exact, literal at a relative `1e-9`) |
| 2 | `perturb` does not mutate, shapes kept | met for `IdentityPerturbation`; `InputVectorPerturbation` is step 3 |
| 3 | repeat iteration, `build(seed)` pure, `len()`, unseeded raise | met |
| 4 | `InputVectorPerturbation` | not built: waits on D6 |
| 5 | `interval_band` and `IntervalBand` | met |
| 6 | ADR-022's six properties for `IntervalCoverage` | met |
| 7 | the `to_dict` guard | met |
| 8 | the acceptance run | not run: needs step 3 |
| 9 | protected files untouched | holds against `origin/main` at every step so far |
| 10 | D4's notes, D5's row, docstrings with units and contracts | notes and row in; docstrings written for every new symbol so far |
| 11 | mutation checks and gates | mutation checks done for steps 1, 2, 4, 5; ruff, format, mypy and `check_ids` clean; full suite last run at `df7353b6` (1272 passed), to be run again at the end |


**The full suite at this point, 2026-11-11.** `python -m pytest tests/ -q -p no:cacheprovider` at `622fafd7`:
`1299 passed in 388.65s (0:06:28)`, laptop, exact pins. That is the expected 1211 + 75 + 13, and it covers
every commit of steps 1, 2, 4 and 5 and the edits to `scripts/feature_distribution.py` and its test, with the
slow archive test included. The commit that carries this paragraph changes this document only. Criterion 11
still needs the run repeated after steps 3 and 6.

## Plan, 2026-11-14: step 3 after D6

Written before any step 3 code. The branch first took `main` at `667972c5` (PR #137, which touches no
file of this plan) as merge `4557e4ae`.

**The answer.** D6 is option A (Bengisu, #64 comment 6863593077, 2026-11-13):
`InputVectorPerturbation(center, scale, *, bounds, max_redraws=64)`, with `relative(x, r, *,
feature_names)` setting `center = x` and `scale = r * abs(x)`. She adds one note: reject a non-finite
or out-of-bounds `center` in the constructor, so the error names its cause instead of arriving as
"redraws exhausted". Her measurement behind the answer (A and B give bit-identical members on 6,400 of
6,400 in ten cases) was made in a session on this laptop that she ran; that is how the math skill's
log of 2026-11-13 records it.

**Files.** Only `src/superconducted/integration/perturbation.py`, a new section 4 of
`tests/test_perturbation.py` (sections 1 to 3 untouched, because the committed mutation outputs name
their tests), one new mutation script in `docs/evidence/issue-64-pr-a1-acceptance/`, and this document.
No change to `interfaces.py` or `aer_factory.py`; if one turns out to be needed, the work stops for the
lead's word.

**What will be built.**

| Symbol | Contract |
| --- | --- |
| `FeatureBound(low, high, *, low_open, high_open)` | A frozen interval on one feature; `contains(v)` is false for a non-finite `v`, so an upper bound of `inf` never admits `inf`. |
| `POSITIVE`, `UNIT_INTERVAL` | `(0, inf)` open at 0, and `[0, 1]` closed, as D1 states them. |
| `bounds_for(feature_names)` | `mean_T1`, `mean_T2` to `POSITIVE`; `mean_readout_error` to `UNIT_INTERVAL`; any other name raises `ValueError`. The units do not matter to these bounds, so the vectorizer's SI vector and the archive's microsecond vector get the same ones. |
| `InputVectorPerturbation(center, scale, *, bounds, max_redraws=64)` | `center` and `scale` are copied and made read-only; `center` must be finite and inside its bounds (her note), `scale` finite and non-negative, one bound per feature, `max_redraws` an integer at least 0. No default for `scale`. |
| `InputVectorPerturbation.relative(x, r, *, feature_names)` | `r` finite and positive, no default; `center = x` (a copy), `scale = r * abs(x)`, bounds from `bounds_for`. Stores `r` and the names. |
| `perturb(index, rng, ...)` | Refuses an extractor whose `output_dim` differs from `len(center)`, or whose `feature_names` differ from the stored ones when `relative` stored them. Then up to `max_redraws + 1` attempts, each one `rng.standard_normal(d)`: `offset = scale * z`, and the attempt is kept when every component of `center + offset` is finite and inside its bound. The whole vector is redrawn on any violation, never clipped. After the last attempt, `ValueError` naming the member and the attempt count. Returns `(OffsetFeatureExtractor(...), rule_base, defuzzifier)`, the last two the inputs themselves. |
| `OffsetFeatureExtractor(wrapped, *, center, offset)` | Holds no state that `extract` changes, because `FuzzyNoiseModel` extracts twice. `extract` raises `ValueError` unless the wrapped output equals `center` exactly, then returns `wrapped output + offset`. `output_dim` and `feature_names` are the wrapped extractor's; `center` and `offset` are read-only. |

**Two choices the plan did not settle, for the owner.**

1. **The bound is tested on `center + offset`, not on `x_i`.** The plan wrote the offset as `x_i - x`. In
   floats `x + (x_i - x)` need not equal `x_i`, so a member could see a vector one ulp outside the
   bound that was checked. With `offset = scale * z` and the bound tested on `center + offset`, the
   vector tested is bit for bit the vector `extract` returns, because the guard makes the wrapped
   output equal `center`.
2. **`r` on an object built with an explicit `scale`.** `relative` sets `r`; the constructor has no `r`
   to take. The property then reads `None`. The alternative is a constructor argument, which would
   make `r` and `scale` two statements of one fact that can disagree.

**The draw pattern is pinned.** One `standard_normal(d)` per attempt, the whole vector redrawn: the
pattern D6's measurement modelled. A test replays a real seeded generator, including a seed whose
first draw is out of bounds.

**Tests, section 4** (criterion 4, and criterion 2 for this perturbation): no default for `scale` or
`r`; the centre checks; `relative`'s arithmetic and its refusals; the bounds table and an unknown name;
a scripted generator whose first draw breaks a bound gives the second draw unclipped, for each kind of
violation, with the open and closed edges both tested at the edge itself; a non-finite candidate
redrawn; `max_redraws` exhausted after exactly `max_redraws + 1` draws, including 0; the replay of a
real generator; read-only `center`, `scale`, `r`, `offset`, and copies that do not follow the caller's
array; the extractor guard on a different snapshot and its repeatability; no input mutated; the
returned shapes; and, through the ensemble on the fixture, members that differ, two passes that agree,
two constructions from one seed that agree, and an ensemble over another snapshot refused. One
statistical check: at `r = 1` the accepted `T1` draws follow the normal truncated at `-1`, whose mean
`phi(1) / Phi(1) = 0.2876` is the second route.

**Mutation check.** A new script, committed with its predictions before it runs; its output comes from
the committed copy. The step 2 script is re-run at the new head, because it asserts that each text it
replaces occurs exactly once in `perturbation.py`, and step 3 adds a second `perturb`.

## Results, 2026-11-14: step 3, the input-vector jitter (laptop, provisional)

Environment as in the 2026-11-11 results (Python 3.12.10, NumPy 2.4.4, Qiskit 2.4.1, qiskit-aer 0.17.2,
pytest 9.0.3, ruff 0.15.12, mypy 1.20.2, from the pins; `superconducted.__file__` printed from this
worktree before each run). Nothing below has run on Burak's desktop.

### What was built (commit `a2207ab2`, tests added at `d6251961`)

Everything in the step 3 plan above, as planned, in `src/superconducted/integration/perturbation.py`:
`FeatureBound`, `POSITIVE`, `UNIT_INTERVAL`, `bounds_for`, `OffsetFeatureExtractor` and
`InputVectorPerturbation` with `relative`. No other source file changed: `interfaces.py` and
`aer_factory.py` were not needed. The module's status list names the new classes.

### Tests: section 4 of `tests/test_perturbation.py`, 45 cases

Sections 1 to 3 are unchanged except for two import lines. Section 4 covers criterion 4 and, for this
perturbation, criterion 2:

| Criterion part | Tests |
| --- | --- |
| no default for `scale` or `r` | `test_the_scale_and_r_have_no_default` (signature and call) |
| a first draw outside a bound gives a redraw, not a clipped value | four violations (T1, T2, readout below 0, readout above 1), the open end at 0 itself, the closed ends at 0 and 1 kept, a non-finite draw (three cases); each asserts the draw count and that every component of the kept offset is the second draw's |
| `max_redraws` exhausted | `ValueError` after exactly `max_redraws + 1` draws, for 0 and 2 |
| offset, scale and `r` read-only | assignment refused, arrays not writeable, copies that do not follow the caller's array |
| the draw pattern D6 measured | a real seeded generator replayed on three seeds whose first draw is out of bounds and one whose first draw is kept: the offset is bit for bit the replayed draw, and the generator's state after `perturb` equals the replay's after `k + 1` draws |
| her D6 note | a centre outside its bounds refused at construction (six cases), the error naming the centre |
| criterion 2 | no input mutated; the rule base and defuzzifier returned as themselves; the member extractor keeps `output_dim` and `feature_names` |
| D6 option A's guard | the member extractor returns `x + offset` twice, equal and fresh, inside the bounds, and refuses a snapshot whose vector differs; an ensemble over another snapshot fails at iteration |
| the ensemble, through the fixture | four jittered members all differ; two passes and two constructions from one seed agree; another seed changes every member (`r = 0.05`, a smoke value) |

**The second route.** At `center = 1`, `scale = 1` on `mean_T1` and no jitter elsewhere, a kept `z` is a
standard normal truncated below at -1, whose mean is `phi(1) / Phi(1) = 0.28760` and standard
deviation 0.7935. 20,000 members from one fixed seed agree within five standard errors (0.028), and no
kept value reaches -1. Clipping would have piled 15.9% of the members on the bound.

### Mutation check (criterion 11)

`mutate_step3_input_jitter.py`, 25 mutants, predictions committed at `a46184eb` before the run: 23 of 23
predicted kills killed, each by its named tests; V18 (`r * x` without `abs`) and V21 (`extract` returning
`center + offset`) survived as predicted, and their controls show why: no admissible centre is negative,
and after the guard the wrapped vector equals the centre, so on 100,000 vectors neither changes a single
value (only the sign of some zeros), while both positive controls fire. V14 dies by its message only;
the refusal is kept by the member extractor's own check. Writing the predictions found two guards no
test reached (a closed infinite bound, the member extractor's own shape checks); their tests went in at
`d6251961`, before the script was committed. The step 2 script, re-run at the new head, still kills 16
of 16. Details in `docs/evidence/issue-64-pr-a1-acceptance/README.md`, section 6.

### Gates

`ruff check .`, `ruff format --check .` (138 files), `mypy --strict` (50 source files) and
`scripts/check_ids.py` clean. Criterion 9: `git diff --stat origin/main` is empty for the six protected
files at `origin/main` `667972c5`. Full suite at `ab42b8d3` (the branch with `main` `667972c5` merged in):
`python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider` collects 1370, and
`python -m pytest tests/ -q -p no:cacheprovider` gives 1370 passed in 439 s, no skip (the archive-backed
survey test ran). The value is the direct collection; it agrees with `main`'s 1203 plus this branch's
122 earlier tests plus 45.

### Where the criteria stand

| # | Criterion | State |
| --- | --- | --- |
| 1 | identity pin | met, with the stated deviation |
| 2 | `perturb` does not mutate, shapes kept | met, for both perturbations |
| 3 | repeat iteration, `build(seed)` pure, `len()`, unseeded raise | met |
| 4 | `InputVectorPerturbation` | met, with the two choices in the step 3 plan for the owner (the bound tested on `center + offset`; `r` reads `None` without `relative`) |
| 5 | `interval_band` and `IntervalBand` | met |
| 6 | ADR-022's six properties | met |
| 7 | the `to_dict` guard | met |
| 8 | the acceptance run | not run: step 6 |
| 9 | protected files untouched | holds against `origin/main` `667972c5` |
| 10 | D4's notes, D5's row, docstrings with units and contracts | met for every symbol so far |
| 11 | mutation checks and gates | done for steps 1 to 5; gates and the full suite clean at `ab42b8d3`; to be repeated after step 6 |

**Owed.** Step 6 (the acceptance run), then the final gates. Before merge, as the plan lists: the owner's
approval (Bengisu), Burak's read of `aer_factory.py`, the primary owner's read of `interfaces.py`, NC-021 at
the merge. D6's measurement was made in a session on this laptop that she ran, and this step was built in
another session here, so her review of the PR is owed as her own read.

## Corrections, 2026-11-14, after the step 3 results above

The section above is left as written. A review pass before the push found four things to correct:

1. **`relative` has a `max_redraws` keyword** (default 64, passed to the constructor unchanged), which
   D6's answer and the step 3 plan do not list. "As planned" above is wrong on that point. The docstring
   now says so (`3c9bbff0`), and it is a third choice for the owner, beside the two in the plan.
2. **"Four jittered members all differ"** was tested only against member 0; the test is now pairwise
   (`3c9bbff0`).
3. **The gates above were counted before the mutation script existed.** At `3c9bbff0`, on the whole
   tree: `ruff check .` clean, `ruff format --check .` 139 files, `mypy --strict` 50 source files,
   `scripts/check_ids.py` clean, `tests/test_perturbation.py` 77 passed.
4. **V14 measured, not read.** Run alone, the test fails with "Regex pattern did not match" while the
   member extractor raises "center has 3 entries but _Shifted returns 4": the kill is by the message.

The step 3 mutation script was re-run from its committed copy at `3c9bbff0`
(`mutate_step3_input_jitter.at-3c9bbff0.out.txt`): every kill line is identical to the first run,
timings aside, and so are both controls. The full suite's 1370 at `ab42b8d3` predates the docstring and
the one assertion; it is repeated after step 6, as criterion 11 asks.

## Plan, 2026-11-14: step 6, the acceptance run (criterion 8)

Written and committed before the run, with the script, on the lead's two choices of 2026-11-14 (asked
in the session's question dialog): the snapshot, and how `r_smoke` and the pass bar are fixed.

**Input.** `snapshots/2026-11/ibm_fez/20261113T162759000000Z.json` at `calibration-data`
`b0482277ad54bc910b98445f75e5206f9b5baf30` (blob `b13ffe3c4821aac7b0d0844155acc2746acd0daf`), read
with `git cat-file` and loaded through `CalibrationStorage.load`. It carries an `sx` gate length on
all 156 qubits, and it is not the test fixture, so the run does not re-test the fixture.

**Engine.** The ratified 3x3x3 Gaussian grid laid out as `tests/conftest.py` lays it out for #58, on
this snapshot's per-qubit values in the vectorizer's SI seconds (three centres evenly over each
feature's range, `sigma` a quarter of the range), random consequents seeded by `first_viable_seed`
(ADR-024), `WeightedAverageDefuzzifier`, `ProbabilityClip`, `KrausChannelProjector`, post-gate
fuzzification. `N = 32`.

**Sensitivity, measured first.** At the snapshot's vector `x`, the elasticity of each output
(`gamma`, `lambda`) with respect to each feature, `E[k][j] = d ln c_k / d ln x_j`, by central
differences at relative steps `1e-3` and `1e-4` (the two must agree; that is the second route). The
inputs reach the model through `OffsetFeatureExtractor`, so the measurement uses the step 3 code path.
Whether `ProbabilityClip` binds is reported from the raw defuzzified outputs.

**`r_smoke = 0.05`, a smoke value, not a fitted one.** It lies inside the range of `r` that #64's D1
to D5 work measured (0.030 to 0.127; comment 6706908485). To first order, a relative jitter `r` with
independent standard normals gives output `k` a relative spread `s_k = r * sqrt(sum_j E[k][j]^2)`.

**Pass bar, fixed now.** All of:

1. the identity ensemble's 32 members have bit-identical `crisp_params`;
2. the jittered ensemble's 32 members are pairwise distinct;
3. for each output, the observed relative spread across the 32 members (sample standard deviation over
   the mean) is between half and twice `s_k`;
4. two constructions from one seed agree bit for bit, and a second seed changes every member;
5. every member's vector is inside its bounds, with the number of redraws reported.

A control shows that bar 3 can fail: the same comparison at `r = 0.005` against the prediction for
0.05 must fall outside it. If a sensitivity comes out near zero, or bar 2 or 3 fails, the run stops
there and the cause is found (the consequents, the clip, or the jitter), as the PR-A plan asks.

**Script.** `docs/evidence/issue-64-pr-a1-acceptance/acceptance_run.py`, committed with this section;
its output comes from the committed copy. Laptop, provisional.

### Amendment 1 to the step 6 plan, 2026-11-14, after the first run and before the second

**What stopped the first run.** Run from `e62824dc` (output `acceptance_run.out.txt`, commit
`81f1717b`): `first_viable_seed` picked seed 0, and at the snapshot's vector the raw defuzzified
outputs are `(-0.0932, 0.0021)`. `ProbabilityClip` holds gamma at 0, so gamma's elasticity is
undefined and the jitter cannot move it. The plan's stop rule fired at its first check, and the cause
is the clip, acting on a seed whose consequents put gamma below 0 at `x`.

**Why the seed search allowed it.** `first_viable_seed` calls a model viable when it is not the
identity (`is_degenerate`), so a model with one output clipped to 0 passes. Over seeds 0 to 11 on this
snapshot, 7 have at least one output at or below 0 at `x` (seed 5 is the one degenerate model), and
seeds 1, 4, 6 and 9 have both inside `(0, 1)`. This is a finding for `aer_factory.py`'s owner (Burak,
ADR-024), recorded here and in the PR's description; nothing in his module is changed.

**The amendment, on the lead's choice.** The rule-base seed is the first seed, in order, whose model
is not degenerate and whose raw outputs at `x` are both strictly inside `(0, 1)`. Everything else in
the plan and the pass bar is unchanged. The first run's output stays as committed; the second run
writes `acceptance_run.amended.out.txt`.

## Results, 2026-11-14: step 6, the acceptance run (laptop, provisional)

Script `docs/evidence/issue-64-pr-a1-acceptance/acceptance_run.py`; two runs, both from committed copies;
details and both outputs in the evidence folder's README, section 7.

**First run** (`e62824dc`): stopped at its own check, as recorded in amendment 1 above.

**Second run** (`7c5c319c`, after amendment 1): seed 1, the first with both raw outputs inside `(0, 1)` at
`x`. Snapshot `20261113T162759Z` by blob `b13ffe3c` at `calibration-data` `b0482277`;
`x = (1.368e-4 s, 9.790e-5 s, 0.02774)`; `crisp_params` at `x` `(0.000810, 0.012044)`, clip not binding
there.

| Sensitivity at `x`, `d ln c / d ln x` (step `1e-4`; step `1e-3` agrees to 8.8e-4 relative) | `mean_T1` | `mean_T2` | `mean_readout_error` |
| --- | ---: | ---: | ---: |
| gamma | +50.59 | -14.87 | -9.99 |
| lambda | +4.188 | +1.786 | +0.042 |

| Bar | Result |
| --- | --- |
| 1, identity members bit-identical | pass: 1 distinct row of 32, equal to the model at `x` |
| 2, jittered members pairwise distinct | pass: 32 of 32 |
| 3, spread within `[0.5, 2]` of the first-order prediction at `r_smoke = 0.05` | pass: gamma 1.531 against 2.683 (ratio 0.57), lambda 0.305 against 0.228 (ratio 1.34); the control at `r = 0.005` gives 0.116 and 0.121, outside the bar as it must |
| 4, one seed twice bit-identical, another seed changes every member | pass: identical; 32 of 32 changed |
| 5, every member inside its bounds | pass: 32 of 32 replayed draws inside, 0 redraws, every replayed member equal to the ensemble's |

**What the gamma half of bar 3 does not show.** Seed 1 leaves gamma 0.00081 above the clip with an
elasticity near 50, so the first-order prediction (a relative spread of 2.68) is far outside its range,
and under the jitter the clip binds on gamma for 19 of the 32 members. The ratio passes near the edge of
the bar on a clipped distribution. The lambda half carries the check. Both sensitivities belong to
seeded random consequents (ADR-024), not to a fitted engine; `r_smoke` is a smoke value, not a fitted
one.

**For `aer_factory.py`'s owner (Burak, ADR-024).** `first_viable_seed` accepts a model whose gamma or
lambda is clipped to 0 at the operating point; on this snapshot 7 of seeds 0 to 11 do so. Recorded here
for the PR's description; nothing in his module is changed.

**Final gates** at `8d2c9c72`: `ruff check .` clean, `ruff format --check .` 140 files, `mypy --strict`
50 source files, `scripts/check_ids.py` clean, criterion 9's six files untouched against `origin/main`
`667972c5`. Full suite: 1370 collected, 1370 passed in 483 s, no skip (the commands of the step 3 gates).

### Where the criteria stand at the end of PR-A1's build

| # | Criterion | State |
| --- | --- | --- |
| 1 | identity pin | met, with the stated deviation |
| 2 | `perturb` does not mutate, shapes kept | met |
| 3 | repeat iteration, `build(seed)` pure, `len()`, unseeded raise | met |
| 4 | `InputVectorPerturbation` | met, with three choices for the owner |
| 5 | `interval_band` and `IntervalBand` | met |
| 6 | ADR-022's six properties | met |
| 7 | the `to_dict` guard | met |
| 8 | the acceptance run | met on the second run, under amendment 1, with the gamma caveat above |
| 9 | protected files untouched | holds |
| 10 | D4's notes, D5's row, docstrings | met |
| 11 | mutation checks and gates | met: steps 1 to 5 mutation-checked, gates and the full suite clean at `8d2c9c72` |

All on the laptop. Owed before merge, as the plan lists: Bengisu's own review (D6's measurement and
both build steps came from sessions on this laptop), Burak's read of `aer_factory.py`, the primary
owner's read of `interfaces.py`, NC-021 at the merge commit, and Burak's desktop run.
