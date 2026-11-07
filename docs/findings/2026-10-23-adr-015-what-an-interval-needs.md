# What it takes for an interval to exist: ADR-015, ADR-016 and the three gates behind them

**Date**: 2026-10-23 · **Measured against**: `main` @ `6cf008da`, Issue #64 as posted, Bengisu's
File 03 decisions on #84 (comment 5970300012, 2026-10-03), and the three derivation logs behind
them · **Requested by**: Mert Efe Şensoy · **Status**: assessment, no code changed

The novelty check (`2026-10-23-novelty-check-q1-article.md` §1, claim 3) says the engine's
headline claim is unverified because the ensemble is degenerate. Its first "what flips the
verdict" item reads "non-identical members and an interval aggregation, so an interval exists
at all". That sentence folds three gates into one. This record separates them, says which is
open today and why, and names the two traps that make a passing interval meaningless.

Every drift figure below is Bengisu's, measured once on a laptop at `main` @ `110cfad` and
`calibration-data` @ `41ebadc`, not registered, canonical verification on Burak's desktop
still owed. They are cited for scale, not as results.

---

## 1. Where the code is

`FuzzyNoiseModelEnsemble.__iter__` (`integration/aer_factory.py`) constructs the same
`FuzzyNoiseModel` from the same seven dependencies `ensemble_size` times (default 32). The
stored `rng` is never read. `simulate_engine` sums member counts with `Counter.update()` and
records `shots * len(members)`, which is the member mean in probability (ADR-016, aligned
2026-09-07). `grep -rn MemberPerturbation src tests` returns nothing. No open PR touches
perturbation. ADR-015 and ADR-016 read `Deferred` on the ledger.

So today: N identical members, one point estimate, zero-width band. Nothing has changed
since the advisor brief of 2026-09-09 said so.

## 2. Gate 1: a mechanism that makes members differ (PR-A of #64)

**What exists.** Issue #64 (Bengisu's, opened 2026-09-03) specifies it to the function
signature: a `MemberPerturbation` ABC in `interfaces.py`; `IdentityPerturbation`;
`InputVectorPerturbation` (jitter the three features, redraw rather than clip, wrap the
extractor in an `OffsetFeatureExtractor`); per-member `SeedSequence` spawning so that
iterating the ensemble twice yields the same members; an `interval` aggregation in the
harness; an `IntervalCoverage` metric. The ticket says PR-A is "not gated on ADR-009 or on
the trainer", and that is true of the code.

**What the ticket gets wrong against the recorded decisions.** The ticket sizes the jitter
by `per_qubit_spread`, the cross-qubit standard deviation `s_q`, and its NFR-8 forbids any
code path that adjusts the scale to a coverage target. Bengisu's File 03 post, three months
later, decides otherwise:

| Question | Ticket #64 (2026-09-03) | File 03 decision (2026-10-03) |
| --- | --- | --- |
| Scale of the jitter | `factor * s_q`, factor 1.0 | the drift scale, fitted on the training period to 80% coverage; measured 24 h persistence half-widths are the size it should land near (gamma ±11.2%, lambda ±10.0%) |
| Why not `s_q` | (it is the recommended default) | `s_q` is a heterogeneity scale, 0.8 to 2.0 times the whole p1..p99 range of the archive mean; jitter at `s_q` moves `mean_T1` by about ±46 us, nearly the archive's whole range |
| Composition | `CompositePerturbation` deferred | one source, one mechanism, one scale; the IT2 footprint is already nonsingleton fuzzification at `s_q`, so stacking input jitter on it at `s_q` gives effective variance `sigma_low^2 + 2 s_q^2`, an exact double count (proven) |
| NFR-8 | no tuning to coverage | amended: the fit uses the training split only, test coverage is never used, the factor ships with an NC row |
| IT2 members | `IT2FootprintSampling`, conditional | the four Karnik-Mendel corners plus a 3×3 grid guard; 4 members, not 32 copies |
| Units of `per_qubit_spread` | microseconds | stale since #66: `extract` emits SI seconds (skill lesson L-001) |

Dr. Akba approved the six brief files "as presented in person", not the posted text, and the
ledger still waits for the lead's approval session (#109) before any status line moves. So
neither text is settled. Anyone who starts PR-A must first correct the ticket's scale, NFR-8
and unit rows to the posted decisions, or record that they are building the ticket as written
and why. Bengisu's own #59 decision 3 (`s_q` is the footprint's scale, for heterogeneity) is
the one she said she would update "for the band's purpose"; that reconciliation is hers and
is still open.

**Verdict on gate 1.** Buildable this week by its owner. It produces members that differ. It
does not by itself produce a band anyone can defend, because the scale it needs comes from
gate 2.

## 3. Gate 2: a scale, which means a fit and a time split

The File 03 protocol fixes the band's one free parameter by fitting it on the training period
to 80% coverage of the ADR-027 target at horizon H, then reports coverage, mean width and the
interval score (Gneiting and Raftery 2007, §6.2) on the test period against a persistence
baseline fitted the same way. That needs:

- a trained model to put a band around (ADR-014; the trainer merged in PR #114, no archive
  fit exists on `main`);
- the training set in NC-012's unit (PR #113, approved 2026-10-21, not merged);
- the snapshot-boundary time split (ADR-027's rule; the test is File 02's decision, not yet a
  script);
- the public-archive rows, if ADR-029 is adopted, with their source column, so the fit and
  the band can be reported with and without them.

**The cheapest honest first result lives here, not in gate 3.** The target-space test asks
whether the band issued at `t` contains the ADR-027 target at `t + H`. No circuits, no shots,
no Aer. It is where the persistence baseline already has a number: a ±10% band covers the
next-day gamma target 77% of the time (provisional). That baseline is the novelty check's §4
item 2, the percentile band over recent snapshots, and it is measured before any model is.
The fuzzy band's first real test is to be narrower than it at the same coverage.

## 4. Gate 3: resolution, or whether the interval can be seen at all

Bengisu's Q3 log measured the outcome-space width of a drift-sized band: at the 24 h box it is
**below one shot standard error at 8,192 shots on every circuit of the n = 4 suite** (largest:
random Clifford at 0.61 standard errors). Only idle-heavy circuits resolve it (`sx^100` at
2.4, `sx^1000` at 6.5). Four box corners bracket the outcome band exactly on 7 circuits at the
two measured box sizes, mutation-checked.

Consequences:

- In counts mode on the ablation circuits, an interval can exist and be invisible. A
  coverage figure computed there says nothing about the engine.
- Outcome-space coverage needs density-matrix mode (members give exact `rho_i`, no shot
  noise). That mode exists only on PR #79, which is `CHANGES_REQUESTED` and blocked as of
  2026-10-23, and `grep density_matrix src/superconducted/benchmarks/harness.py` on `main`
  returns nothing.
- Any hardware comparison of the band is restricted to idle-heavy circuits and must carry a
  shot-noise flag, as File 03 Q3b already says.
- Per-qubit channels (ADR-013) turn the snapshot-global box into a per-qubit box; Q3's "Not
  established" names this. It is the novelty check's spatial-uniformity finding meeting
  ADR-015: the band is as uniform across the chip as the channel is.

## 5. Two traps that pass a coverage test without an engine

**Vacuous coverage from a slow clock.** T1 and T2 change about once a day (median 24.7 h
between changes; 127 changes in 1,538 consecutive steps, so about 92% of consecutive files
repeat them). A zero-width band from identical members therefore scores about 92% coverage
if it is scored on consecutive files, and a substantial fraction even at a 24 h horizon,
since half the 24 h-ahead pairs have not seen a T1 change yet. That is the failure #64 was
opened to prevent, in a form a coverage number does not catch. Neither #64's FR-9 nor the
File 03 Q3c protocol says what the scoring rows are. The deep-engine research
(`docs/roadmap/2026-10-04-deep-engine-architecture-research.md`, recommendation recorded and
not adopted) proposed epochs as rows and coverage scored on change events. **This is the one
addition this record raises for #64**: score coverage on change events, or on distinct device
states in NC-012's unit, never on consecutive files, and report the number of scoring rows
next to every coverage figure.

**A band beaten by persistence is not a result.** The persistence baseline is a non-fuzzy
percentile band and it already has a provisional number (77% at ±10%, 24 h). If the fuzzy
band is wider at equal coverage, or no better at equal width, the article has a system
description and a negative result. That is worth knowing in a day, not in review, and it is
why gate 2's target-space test comes before any Aer run.

## 6. Ownership, so nobody "just builds it"

| Piece | Owner | Review |
| --- | --- | --- |
| #64, `integration/perturbation.py`, `benchmarks/metrics.py` | @bengisucvd | @BurakOztekin, @mertefesensoy |
| `integration/aer_factory.py`, `benchmarks/harness.py` | @BurakOztekin | |
| `MemberPerturbation` in `interfaces.py` | cross-cutting: lead's read, advisor's primary ownership exercised by the lead since 2026-10-03 | |
| Karnik-Mendel (the IT2 arm's four corners) | @bengisucvd, Issue #61; exists nowhere in `src` | |
| #59 decision 3 (`s_q` for the band's purpose) | @bengisucvd | |
| training set, time split | @BahaJarad (#63, PR #113) | |

The lead can take PR-A as he took #84's research on 2026-10-03, with Bengisu reviewing and
posting; that is a decision, not a default.

## 7. Order that produces a defensible interval soonest

1. Correct #64's three stale rows (scale, NFR-8, units) to the posted decisions, or record
   the choice to build as written. One comment on #64, by its owner.
2. Add the scoring-row rule (change events or distinct states) to #64 FR-9 and to the Q3c
   protocol. One comment.
3. Merge PR #113; produce the first archive fit at a pinned ref with the snapshot-boundary
   split (#60, Burak).
4. Fit the persistence baseline's scale on the training period and register its test-period
   coverage and width. This is the bar, measured first.
5. PR-A of #64: mechanism, seeding, band, coverage metric. Scale from step 3, not from `s_q`.
6. Target-space coverage of the fuzzy band versus step 4. This is the first number the
   article can carry.
7. Outcome-space coverage only after PR #79 lands density-matrix mode, on idle-heavy
   circuits, with the resolution figure beside it.

Nothing in steps 1 to 4 is this record's to execute: each belongs to a named owner.

## 8. Sources

Issue #64 body and section 7; #84 comment 5970300012 and its English summary; the skill's
derivation logs `2026-10-03-q1-ensemble-vs-per-shot.md`,
`2026-10-03-q2-footprint-vs-input-perturbation.md`,
`2026-10-03-q3-band-space-and-resolution.md` (on the lead's machine, not in the repository);
`docs/decisions.md` ADR-002, ADR-013, ADR-014, ADR-015, ADR-016, ADR-021, ADR-027;
`docs/advisor/2026-09-03-decisions-from-akba.md` (2026-10-03 entry);
`src/superconducted/integration/aer_factory.py`, `src/superconducted/training/anfis.py`,
`src/superconducted/types.py`; PR #79, PR #113, PR #114; Issues #59, #60, #61, #63, #109.

## 9. Review amendment, 2026-10-26: the two baseline gates

Section 3 incorrectly equates the relative-persistence band `y(t) +/- r*abs(y(t))` with
novelty-check section 4 item 2's rolling empirical-percentile interval. That identification
is withdrawn. The persistence band is symmetric about the current target; a rolling
percentile interval is determined by the recent target history and can have a different
centre and unequal distances from the current target. A fitted persistence scale does not
make these the same estimator.

The provisional persistence measurement in section 3 remains evidence for relative
persistence only. It establishes no result for the empirical-percentile comparator. Gate 2
and the order of work in section 7 now require both baselines: PR-A' implements each, and the
fuzzy arm is evaluated against each on the same horizon, split and held-out scoring rows.
All history-window choices, tail probabilities and fitted scales are fixed using training
data only; histories at test origins may use observations already available at the origin,
never the future target. Apply one common history-ready scoring mask and report excluded
origins, so coverage and width are compared on the same examples. Coverage and width alone
must not be described as matched-coverage results unless the training calibration for that
comparison is explicitly defined and recorded.

The authoritative amendment to the implementation plan is
[`2026-10-23-issue-64-pr-a-plan.md`, section 12](../roadmap/2026-10-23-issue-64-pr-a-plan.md#12-review-amendment-2026-10-26-separate-baselines-and-fix-alpha-before-fitting).
The required empirical-percentile comparator remains in the novelty record, section 4 item 2;
its section 10 now names relative persistence as an additional comparator. No baseline has
been measured by this amendment.
