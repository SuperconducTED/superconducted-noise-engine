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
