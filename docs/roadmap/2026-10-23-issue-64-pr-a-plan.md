# Issue #64 PR-A under the File 03 decisions: the plan

**Date**: 2026-10-23 · **Author**: Mert Efe Şensoy (taking PR-A, as he took the File 03 research
on 2026-10-03) · **Reviewer and owner of the ticket**: @bengisucvd · **Measured against**:
`main` @ `6cf008da` · **Status**: approved by the lead on 2026-10-23 as written; the #64
comment carrying the stale-row corrections and D1 to D5 was posted the same day
([#64, 6366176028](https://github.com/SuperconducTED/superconducted-noise-engine/issues/64#issuecomment-6366176028));
nothing built until Bengisu answers D1 to D5

This plan is the documented plan the engineering standard requires before any code. It takes
Issue #64 as written on 2026-09-03, applies the File 03 decisions Bengisu posted on #84 on
2026-10-03 (comment 5970300012; approved by Dr. Akba as presented in person, ledger flips
pending the lead's approval session in #109), and says exactly what PR-A builds, what it
leaves out and why, and which five choices Bengisu has to confirm before the first commit.
The gates and traps behind it are in
`docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`.

---

## 1. What changed between the ticket and today

| | Ticket #64 (2026-09-03) | Today (2026-10-23) | Consequence for PR-A |
| --- | --- | --- | --- |
| Jitter scale | `factor * per_qubit_spread` (`s_q`), factor 1.0 | File 03 Q2a: the drift scale, one scalar per arm, fitted on the training period to 80% coverage; `s_q` is 0.8 to 2.0 times the archive mean's whole range and is the wrong size for a drift claim | `InputVectorPerturbation` takes an explicit scale. No `from_snapshot(factor * s_q)`. `per_qubit_spread` leaves PR-A. |
| NFR-8 | no code path adjusts the scale to a coverage target | File 03 Q3c amends it: the fit uses the training split only, test coverage is never used, the fitted factor ships with an NC row | PR-A ships **no default scale**: the argument is required, so nothing can be "turned up". The fit is a separate script with its own evidence folder. |
| Units | microseconds | SI seconds since #66 (`BasicCalibrationVectorizer` docstring) | Scale and bounds in SI seconds and dimensionless; stated in every docstring and record (skill rule, L-001 promoted). |
| Composition | `CompositePerturbation` deferred | one source, one mechanism, one scale; stacking jitter on the IT2 footprint at `s_q` double-counts (proven) | One perturbation per ensemble, enforced by the ABC's single slot. |
| IT2 arm | `IT2FootprintSampling`, σ uniform inside the footprint, conditional on ADR-009 | File 03 Q3d: the four Karnik-Mendel corners plus a 3×3 grid guard; 4 members, not 32 | Not sampling, and Karnik-Mendel exists nowhere in `src` (Issue #61, Bengisu's). Out of PR-A; the ABC's `(rule_base, defuzzifier)` return already carries it. |
| Harness | build against #58's signature (`basis_gates`, `mode`, `seed`) | PR #79 (#58) is open, `CHANGES_REQUESTED`, and `main`'s `simulate_engine(circuits, ensemble, *, shots)` has none of them | The harness half of PR-A **collides with an open PR by the reviewer**. Split: PR-A1 touches no harness file; PR-A2 lands after #79. |
| Coverage rows | not stated | not stated in File 03 either; T1/T2 repeat in about 92% of consecutive files (File 03 M2), so a zero-width band scores about 92% on consecutive files | New rule (L-026): coverage is scored on change events or distinct device states, never on consecutive files, with the row count beside it. Lives in the fit script and the evidence README, not in the metric. |
| Q1-B | not in the ticket | a half-day spike: a guard test that `NoiseModel.to_dict` is called once per multi-shot run | One test, in PR-A1. |

## 2. PR-A1: mechanism, seeding, band, coverage (no harness, no ADR text)

**Files.**

| File | Change | Owner on `docs/team.md` |
| --- | --- | --- |
| `src/superconducted/interfaces.py` | add `MemberPerturbation` ABC exactly as #64 FR-1 (`perturb(index, rng, *, feature_extractor, rule_base, defuzzifier) -> (extractor, rule_base, defuzzifier)`, pure, non-mutating) | cross-cutting: lead plus one of Burak or Bengisu. The advisor's primary-owner read of `interfaces.py` is to be recorded in the decisions register as the lead's read under the 2026-10-03 arrangement; whether that arrangement reaches primary-owner reads, and not only the brief files' decisions, is for Mert to confirm there |
| `src/superconducted/integration/perturbation.py` | new: `IdentityPerturbation`, `OffsetFeatureExtractor`, `InputVectorPerturbation` | new row: owner to be confirmed (ticket says Bengisu; see D5) |
| `src/superconducted/integration/aer_factory.py` | `FuzzyNoiseModelEnsemble(..., perturbation=None)`; child `SeedSequence`s spawned at construction (`rng.bit_generator.seed_seq.spawn(n)`, never `Generator.spawn`); fresh `default_rng(seed_seq[i])` per member in `__iter__`; `ValueError` when a non-identity perturbation is given without `rng`; docstring status updated | Burak (owner), reviews |
| `src/superconducted/benchmarks/metrics.py` | `IntervalBand`, `interval_band(members, *, alpha, method)`, `IntervalCoverage` (duck-typed, `name == "interval_coverage"`, mass-weighted, inclusive edges) with the six ADR-022 properties as named tests | Bengisu (owner), reviews |
| `tests/test_perturbation.py`, `tests/test_interval_band.py`, `tests/test_aer_serialises_once.py` | new | |
| `docs/team.md` | one ownership row for the new module | |
| `docs/implementations/2026-10-XX-issue-64-pr-a1-perturbation-and-band.md` | per template | |

**`InputVectorPerturbation`, as it will be written.**

- Constructor: `InputVectorPerturbation(scale, *, bounds, max_redraws=64)`. `scale` is a `(d,)`
  array in the extractor's units, required. `bounds` per feature: `(0, inf)` open at 0 for
  `mean_T1` and `mean_T2`, `[0, 1]` for `mean_readout_error`, derived from `feature_names`.
- Factory: `InputVectorPerturbation.relative(x, r, *, feature_names)` sets `scale = r * |x|`
  for one scalar `r` (the "single scale per arm" of File 03 Q2a). `r` has no default.
- `perturb(i, rng, ...)`: extracts `x` once, draws `z ~ N(0, I_d)`, forms `x_i = x + scale * z`,
  redraws on a bound violation (never clips; `ValueError` after `max_redraws`), returns
  `(OffsetFeatureExtractor(extractor, offset=x_i - x), rule_base, defuzzifier)`. Offset,
  scale and `r` are read-only properties so the harness can record them.
- The pipeline then runs once per member inside `FuzzyNoiseModel`, as ADR-021 requires;
  `FuzzyNoiseModel` itself is untouched.

**Band and coverage, as in #64 §6.3** with two fixed choices: mass-weighted coverage (the
GHZ argument), inclusive edges (pinned by the hand-derived 0.65 example). Band quantiles via
`np.quantile(..., method=...)` with the method stored. `alpha` is an argument with no hidden
default in any record; see D2 for the value.

**Tests first**, per the repo's reproduce-then-pin convention: the identity pin
(`perturbation=None` yields bit-identical `crisp_params`, today's behaviour, captured before
the wiring changes); repeat-iteration identity under a perturbation (the `SeedSequence` pin);
`build(seed)` purity for `first_viable_seed`; the unseeded raise; redraw-not-clip with an rng
whose first draw violates a bound; the six coverage properties; the `to_dict` once-per-run
guard (`shots=1024`, automatic and density-matrix methods). The guard passes on the pinned
qiskit-aer 0.17.2 and is meant to fail loudly on any upgrade that changes the call count; it
pins the behaviour, not the version.

**Acceptance for PR-A1** (adapted from #64 step 9, without the harness): the ratified 3×3×3
Gaussian grid on a real archived `ibm_fez` snapshot at a pinned `calibration-data` ref, in
SI-consistent units (the grid laid out on `BasicCalibrationVectorizer`'s seconds, not on the
archive's microseconds; L-001's second sighting was exactly this trap), N = 32,
`InputVectorPerturbation.relative(x, r_smoke)`, labelled a smoke value and never a fitted
one; the members' `crisp_params` must not all be equal; the identity ensemble's must; two
constructions with the same seed must agree bit for bit.

**Before choosing `r_smoke`, measure the engine's sensitivity** (the skill's L-004 check,
applied to the pipeline instead of a circuit): on one member, the change in `crisp_params`
per unit change in each feature at the snapshot's `x`. NC-041 puts the three `mean_T1`
centres about 28 µs apart across a 98.8 to 154.4 µs box, so a ±10% jitter at about 130 µs
moves the input by half an inter-centre spacing; whether that reaches the channel depends on
the consequents (zeros at bootstrap under ADR-014, a seeded draw under ADR-024's
`first_viable_seed`) and on whether `ProbabilityClip` (ADR-012) is binding. The acceptance
record states the measured sensitivity, the `r_smoke` chosen from it, and the threshold the
test pins. If the sensitivity is near zero, the run uses a seeded non-zero consequent and says
so; if every member's `crisp_params` is still identical, stop and find out which of the three
causes it is. That check is the point of the step.

## 3. PR-A2: harness interval mode, after PR #79 merges

`EnsembleSimulation(members, aggregate, member_metadata)`, `simulate_engine_members`,
`run_benchmark(..., aggregation="interval")`, the aggregate-inside-band invariant, the
shot-noise flag (#64 FR-7, FR-10, FR-11), built on #79's signature and modes. The default-path
regression pin is captured on the tree with #79 merged and PR-A2 not yet applied, as #64 NFR-2
says. Not planned in detail here, because its base does not exist on `main` yet.

## 4. PR-A′: the persistence baseline and the scoring rows (a script, no engine)

Separate small PR, can run in parallel with PR-A1 and needs no trained model: for horizon H and
a snapshot-boundary time split, the persistence band `y(t) ± r·y(t)` on the ADR-027 target,
its scale `r` fitted on the training period to 80% coverage, its test-period coverage, mean
width and interval score, **scored on change events (rows where the target at t + H differs
from the target at t) and separately on distinct device states**, with the row counts printed.
Evidence folder `docs/evidence/persistence-band/`, one NC row per conclusion. This is the bar
every fuzzy band is measured against (File 03 Q3c; novelty check §4 item 2). It also fixes the
fitting function the fuzzy arms reuse in gate 2.

## 5. Decisions Bengisu confirms before the first commit (D1 to D5)

1. **D1, jitter form.** Additive Gaussian with relative scale `r·|x|` and redraw (the ticket's
   form, the File 03 scale), or multiplicative log-normal `x·exp(r z)`, which keeps positivity
   without redraw and makes `r` a relative width directly. Recommendation: additive with
   relative scale, because the ticket's redraw-not-clip reasoning and tests carry over and the
   difference is second order at `r ≈ 0.1`.
2. **D2, band definition for the T1 arm, fixed together with the scale.** `alpha` defines the
   band (central `1 - 2·alpha` of the members per bin); `r` is then fitted, given `alpha`, so
   that the band's training-period coverage of the target is 80%. The two are one pair: a
   wider `alpha` simply yields a smaller fitted `r`, so choosing `alpha` moves the degree of
   freedom, it does not remove it. Reading the members as a sample from a calibrated predictive
   distribution, which would make `alpha = 0.1` "the 80% interval" by itself, is not justified
   for Gaussian feature jitter pushed through a nonlinear TSK base; the 80% is earned by the
   fit, not by `alpha`. Options: `alpha = 0.1` with N = 32 (recommendation, so that the
   reported band and the fitted band are the same object), or `alpha = 0` (min/max) as the
   ticket ships. This is a modelling choice with no mathematically preferred answer; Mert and
   Bengisu fix the pair together and both values are recorded on every band. The IT2 arm's
   four corners are a min/max band by construction and are reported as such.
3. **D3, scoring rows.** Change events, distinct device states, or both reported. Recommendation:
   both, with change events primary (L-026).
4. **D4, `per_qubit_spread`.** Out of PR-A (recommendation), or kept as a helper for the IT2
   footprint's statistic. It is #59 decision 3's scale and NC-042's statistic; nothing in the
   drift-scale arm reads it.
5. **D5, ownership of `integration/perturbation.py`.** The ticket names Bengisu as owner. With
   Mert authoring, the row can still name her (she reviews, owns the follow-ups) or name Mert.
   Recommendation: Bengisu owner, Mert secondary, since #64 stays hers.

Decisions 2 and 5 of the ticket's own §7 (no second ABC; the unseeded raise) are taken as
recommended. Decision 1 of §7 (spread or standard error) is dissolved by File 03: neither.

## 6. Order of work

1. Post the #64 comment (§7): the three stale rows corrected, L-026's scoring-row rule, D1 to
   D5, the PR split, Mert as author. Wait for Bengisu's answers.
2. Branch `mert/issue-64-pr-a1` from `main`. Until PR #121 merges, this plan and the gates
   record exist only on #121's branch, so PR-A1's description and implementation doc link
   PR #121 rather than citing the paths. Tests first (the identity pin before the wiring).
3. `MemberPerturbation`, `IdentityPerturbation`, ensemble seeding, the unseeded raise.
4. `OffsetFeatureExtractor`, `InputVectorPerturbation`, redraw tests.
5. `IntervalBand`, `interval_band`, `IntervalCoverage`, six properties.
6. The `to_dict` once-per-run guard test.
7. Acceptance run (§2) on the laptop, provisional; figures to Burak's next batch record, not a
   per-PR verification file.
8. Implementation doc, `docs/team.md` row, PR with Bengisu as approver and Burak's read on
   `aer_factory.py`; the `interfaces.py` read recorded in the decisions register.
9. PR-A′ in parallel from step 2 on; PR-A2 after #79.

## 7. The #64 comment

Drafted in Turkish with a collapsed English summary for Bengisu, at the path given in the
session; posted by Mert after she has seen the plan, not before.

## 8. What this plan does not do

No ADR status moves (PR-B). No IT2 members (Issue #61 first). No premise-MF perturbation
(no parameter covariance; `TrainingResult` carries RMSEs and a condition number). No
harness edits until #79 lands. No fitted scale: every `r` in PR-A1 is a smoke value and says
so. No hardware.

## 9. Verification, for the implementation doc that follows

`pytest tests/test_perturbation.py tests/test_interval_band.py tests/test_aer_serialises_once.py -v`;
`ruff check .`; `ruff format --check .`; `mypy --strict`; `git diff --stat main -- src/superconducted/fuzzy/tsk.py src/superconducted/channels/kraus.py` empty;
the acceptance run's command and seed in `docs/evidence/`; the test count added to NC-021
differentially at the merge commit.

## 10. Related

Issue #64 (body and sections 9 to 12 in its first comment), #84 comment 5970300012, #59
decision 3, #61, #79, #109; ADR-002, ADR-012, ADR-015, ADR-016, ADR-021, ADR-022, ADR-024,
ADR-027; `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md`;
`docs/findings/2026-10-23-novelty-check-q1-article.md` §4.
