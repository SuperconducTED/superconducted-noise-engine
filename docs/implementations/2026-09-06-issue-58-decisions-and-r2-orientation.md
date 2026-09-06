# 2026-09-06: issue-58-decisions-and-r2-orientation

## Problem / Motivation

@bengisucvd opened work on #58 (`bengisu/issue-58-benchmark-certification`) and
posted three comments the same day: the eight §7 decisions restated for sign-off, a
**mathematical blocker** against §6.5's resolution rule, and a fixture-specific
conflict in decision 6 that she declined to resolve by imputing data. §8 step 3 lets
her build behind the recorded recommendations, but nothing counts as signed off until
its owner confirms, so the ticket was blocked on answers — three of the four requested
confirmations name the lead.

Nothing was taken on trust. Every number in her comments was re-measured from the
primary source before a reply was drafted, per the repo's re-measure-cited-evidence
convention (the precedent is the PR #50 review, where a check passed for the wrong
reason). All of her figures held. Two things her comments did **not** say were found
in the process, and both changed what happens next.

| Comment | Claim | Verified how | Outcome |
| --- | --- | --- | --- |
| Eight decisions | The eight items restate §7's recorded recommendations | Diffed item by item against §7 of the issue body and §9.1's `_try_compute` row | Faithful; agreed at lead level, owner sign-off explicitly **not** substituted |
| §6.5 R² blocker | `reference_value` is 1.0 for R², so `delta = R²_engine − 1`, and the rule's orientation is wrong for a similarity | Read `R2Score.compute` and `run_benchmark` at `7d39a2b`; re-ran the zero-effect case numerically | **Correct.** Confirmed `D_R2 = 1 − R²`. Two further findings below |
| Decision 6 / q72 | 10 dead directed `cz`, q72 sole qubit missing T1/T2, 4 dead entries touch q72 | Counted directly from PR #69's `ibm_fez_20260513T121322Z_with_gates.json` | **Exact**, all three. Endorsed at lead level; @BurakOztekin ratifies |

Two findings added to the thread that were not in her comments:

1. **At `n = 3` the raw-R² rule does not misfire — it cannot fire at all.** Her
   zero-effect counterexample is sound as algebra, but on the two circuits §6.5 names
   it does not reproduce: a reproduction test written that way would **pass** and hide
   the defect. The test must pin direction, not a single point.
2. **R² is unusable as a resolution metric on `qft_circuit(3)` in any sign
   convention**, because its denominator is shot noise there. The sign fix is necessary
   and does not repair this.

Also recorded: `gate_error == 1` is not confined to `cz` in that fixture — twelve
single-qubit entries carry it too, on qubits with **valid** T1/T2, so
`single_qubit_relaxation` will noise dead gates with no provenance record.

Both findings have since been confirmed on the real instrument by Bengisu's own FR-7
run; see *Confirmation on the real instrument* below. That run also surfaces a
consequence neither comment anticipated, recorded here as an open item.

## What changed

**No source file was modified by this work.** The deliverable was verification,
four issue comments, and this record. Between the start of the session and its end
@bengisucvd advanced her branch from `93e5d58` to `1ae6c3a` (four commits, including
FR-7's script and the untracked `docs/evidence/resolution-measurement/resolution.tsv`);
none of that is this record's, and none of it was touched.

| File | One-sentence description |
| --- | --- |
| `docs/implementations/2026-09-06-issue-58-decisions-and-r2-orientation.md` | This document: the verification record, the mathematics behind the §6.5 correction, and the four decisions taken. |

Artifacts outside the repository, listed so the record is complete. The first two and
Yiğit's ratification were posted outside this session and are included because the
decision record is not otherwise legible:

| Artifact | Content |
| --- | --- |
| [#58 comment 5560333414](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560333414) (15:45, other session) | The omitted `(gamma_0, lambda_0)` baseline derived from PR #69's fixture, and the correction that the May fixture basis is `cz,id,rx,rz,sx,x` with no `rzz`. |
| [#58 comment 5560336487](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560336487) (15:46, other session) | **The all-cells resolution quantifier proposed**, naming the cell set (QFT and GHZ × Hellinger and `1-R²` for counts) and pre-authorising `not resolved on ladder` as its honest outcome. |
| [#58 comment by @yigit-arda](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58) (16:54) | Ratifies items 7–8 as #62's caller, the `D_R2 = 1 − R²` orientation, and the all-cells quantifier. |
| [#58 comment 5560382401](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560382401) | Lead-level agreement on all eight §7 decisions; decision 1 confirmed as proposed; the records implications (NC id allocation, one row per conclusion, provisional-until-desktop, differential runbook expectations). |
| [#58 comment 5560382649](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560382649) | §6.5 correction confirmed as `D_R2 = 1 − R²`, with the reachability and QFT-denominator findings. |
| [#58 comment 5560382862](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560382862) | Decision 6 / q72 precedence endorsed at lead level with the fixture counts re-derived; the twelve single-qubit dead entries raised for @BurakOztekin. |
| [#58 comment 5560393356](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5560393356) | Correction: `NC-013` was wrongly described as never having existed. |
| [#58 comment 5561621562](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5561621562) | The findings confirmed against FR-7's real-Aer run, and the two aggregation consequences below. Written without sight of the 15:46 proposal, @yigit-arda's 16:54 ratification, or @bengisucvd's 19:28 report of the same finding — superseded by the retraction below. |
| [#58 comment 5561662119](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5561662119) | Retraction: withdraws the suggestion to drop `("qft_n3", "one_minus_r2")` from `_REQUIRED_CELLS` on @bengisucvd's post-hoc-selection argument, withdraws per-circuit reporting as contradicting the ratified quantifier, and narrows the surviving ask to Notes disclosure of the single blocking cell. |

## Implementation approach

**Verify first, then answer.** Each comment was treated as a claim to be reproduced,
not a report to be accepted:

- *Fixture claims* — `git fetch` of PR #69's branch, then the JSON parsed directly and
  the dead-`cz` entries, missing-T1/T2 qubits and `T2 > 2·T1` qubits counted in code
  rather than read off the comment.
- *Code claims* — `R2Score.compute`, `HellingerDistance.compute`, `run_benchmark` and
  `_try_compute` read at `7d39a2b`, the commit the ticket cites, not at the working
  tree, which was mid-edit throughout.
- *The mathematical claim* — reproduced numerically. `R2Score.compute` and
  `HellingerDistance.compute` were reimplemented verbatim in pure Python over
  multinomial samples at the ADR-019 shot count, because this machine has no working
  numpy/qiskit. That bounds what the numbers may be used for: **direction and order of
  magnitude only**, stated as such in the thread. They have since been superseded by
  Bengisu's real-Aer run, which agrees.
- *Register claims* — `NC-030`-is-last and PR #52's id range checked against
  `docs/numerical-claims.md` and `gh pr diff 52` rather than against the ticket's own
  assertion.

An intermediate result was wrong and was corrected publicly: the NC-0xx sequence has a
hole at 013, which was reported as "NC-013 never existed". It existed and was **retired
as NC-R002**; `docs/numerical-claims.md`'s "Retiring a claim" moves retired rows to a
separate section under an `NC-R` id. The operative rule was unaffected
(`max(NC-0xx) + 1`, never the row count), but the consequence inverts — a gap is *not*
an unallocated id, and reallocating 013 would make the citation in
`docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` ambiguous.

**Language.** Replies to @bengisucvd are written in Turkish with identifiers, paths and
decision names left in English, per the convention set on 2026-09-02 (PR #50 and
PR #55). Blocks addressed to @BurakOztekin and @yigit-arda are in English, per PR #44.
All three handles were resolved against the GitHub API before posting, because
`@bengisu` — a real, unrelated account — has silently swallowed mentions on this
project before.

## Mathematical / Statistical details

### The rule under discussion

§6.5 defines resolution in counts mode with `R` independent seeds, a same-model
baseline and a between-model value:

- `d0 = metric(A_seed_i, A_seed_j)`, `i ≠ j` — same model, **independent** seeds
- `d1 = metric(A_seed_i, B_seed_i)` — different models, **paired** seed

and calls a delta *resolved* when

```
mean(d1) > mean(d0) + 3 · sd(d0)
```

applying that single rule to both Hellinger and R².

### Why the orientation is wrong for R²

The rule encodes "the between-model discrepancy exceeds the same-model noise floor by
3σ". That reading is valid only for a **distance**, whose self-baseline is 0 and which
grows as the models diverge. Hellinger qualifies. R² does not: it is a **similarity**
with self-baseline 1 that *decreases* as the models diverge. Applied to R², the rule
literally asks whether the between-model pair is **more similar** than the same-model
baseline — anti-correlated with the quantity of interest.

The harness confirms the sign in code. `run_benchmark` computes
`reference_value = metric.compute(reference, reference)`, and for `R2Score` that is
exactly `1.0`: with identical inputs `ss_res` is exactly 0, and the `ss_tot == 0` guard
also returns `1.0`. Hence `delta = R²_engine − 1 ≤ 0`, decreasing as the engine departs
from the reference — Bengisu's reading, verified.

At `delta_gamma = 0` the two models are identical and the seeds are paired, so the
counts are **bit-identical**, `ss_res = 0`, and `d1 = 1.0` exactly — the maximum R² can
attain. The baseline `d0` compares independent seeds and is strictly below 1. So the
rule is closest to declaring "resolved" at exactly zero physical effect.

### When the raw rule actually fires — an exact condition

Because `R² ≤ 1`, `mean(d1) ≤ 1`, so the rule can fire **only if** its threshold lies
below 1:

```
mean(d0) + 3 · sd(d0) < 1
```

Substituting `D = 1 − R²` (so `mean(D0) = 1 − mean(d0)` and `sd(D0) = sd(d0)`) turns
this into a statement about the discrepancy alone:

```
mean(D0) > 3 · sd(D0)
```

**The raw rule is capable of firing only when the same-model discrepancy's mean exceeds
three times its own standard deviation.** Otherwise the threshold sits above 1, no
attainable R² can exceed it, and the rule returns "not resolved" for every delta —
including deltas a distance metric resolves easily.

Where that ratio sits is governed by the effective degrees of freedom of `ss_res`. For
a reference far from uniform, `ss_tot` is essentially a constant, `ss_res` is a weighted
sum of `ν` squared near-normal deviates, and `D0` is approximately a scaled chi-square,
for which `mean/sd = ν/√(2ν) = √(ν/2)`. Firing therefore needs `ν > 18` — around 20
well-populated bins, i.e. `n ≥ 5` qubits. At `n = 3` (`K = 8`, `ν ≈ 7`, `√3.5 ≈ 1.87`)
it is unreachable, and for a *concentrated* distribution the effective `ν` is smaller
still, because the same two bins dominate numerator and denominator alike.

### Measurements (synthetic, this session)

`R = 40` seeds, `S = 4096` shots, `eps` moving probability mass between two bins.
"Threshold" is `mean(d0) + 3·sd(d0)` on the raw-R² scale.

| Reference shape | bins | raw-R² floor `mean ± sd` | threshold | reachable? | measured `mean/sd` of `D0` | predicted `√(ν/2)` |
| --- | --- | --- | --- | --- | --- | --- |
| GHZ-like, concentrated | 8 | `0.999006 ± 0.001037` | `1.002118` | **no** | 0.96 | ≈1.4 (`ν_eff ≈ 2`) |
| QFT-like, near-uniform | 8 | `−0.824099 ± 1.149563` | `2.624589` | **no** | 1.59 | 1.87 (`ν = 7`) |
| uniform | 64 | `−0.994795 ± 0.365202` | `0.100812` | **yes** | 5.46 | 5.61 (`ν = 63`) |

The chi-square heuristic tracks the measurements across two orders of bin count.

**Direction, GHZ-like reference** (`eps` = 0, 1e-4, 1e-3, 1e-2, 1e-1):

| quantity | 0 | 1e-4 | 1e-3 | 1e-2 | 1e-1 |
| --- | --- | --- | --- | --- | --- |
| raw R² (between) | 1.000000 | 1.000000 | 0.999990 | 0.999322 | 0.916516 |
| `D_R2 = 1 − R²` | 0.000000 | 0.000000 | 0.000010 | 0.000678 | **0.083484** |
| Hellinger | 0.000000 | 0.000365 | 0.003444 | 0.028044 | **0.169523** |

Raw R² decreases monotonically as the physical difference grows — the rule moves
*further* from firing as the effect gets larger. `D_R2` and Hellinger both increase
monotonically and both declare resolved at `eps = 1e-1` and nowhere earlier.

**The false positive is real, where the threshold is reachable.** At 64 bins the
threshold is `0.100812 < 1`, and `eps = 0` gives `d1 = 1.0 > 0.100812` — a zero physical
difference classified as resolved, exactly as Bengisu describes.

**At `n = 3` the same defect presents as a vacuous column, not a false positive.** The
threshold exceeds 1 on both named shapes, so the raw rule declares "not resolved" at
every delta including `eps = 1e-1`, where Hellinger resolves cleanly. "The smallest
resolved delta for R²" would have no value to report. This is why a zero-effect
reproduction test at `n = 3` **passes on the broken rule**: the correct verdict at
`eps = 0` is "not resolved", and the broken rule returns it for the wrong reason. The
reproduction must pin the monotone direction of the sweep above.

### The second finding: R² has no usable denominator on QFT

`qft_circuit(n)` appends `QFTGate(n)` to `|0…0⟩`, and `QFT|0…0⟩ = N^{-1/2} Σ_k |k⟩`, so
every ideal outcome probability is exactly `1/K`. The R² denominator is

```
ss_tot = Σ_k (p_ref,k − mean(p_ref))²,    mean(p_ref) = 1/K identically
```

which is **exactly zero at the population level** for a uniform reference. The sampled
`ss_tot` is therefore pure shot noise, of the same order as `ss_res`:

```
E[ss_tot] ≈ (1 − 1/K)/S = 2.14e-4      E[ss_res] ≈ 2(1 − 1/K)/S = 4.27e-4
```

at `K = 8`, `S = 4096`, giving `E[D0] ≈ 2`. So R² on a uniform reference is a ratio of
one shot-noise quantity to another, with a spread larger than the metric's own identity
value. This is not repaired by the sign fix.

The caveat stated deliberately in the thread: the argument is exact for the *ideal* QFT
output, while the *noisy* reference is biased toward `|0…0⟩` by thermal relaxation and
so carries some genuine non-uniformity in `ss_tot`. How much was left as an empirical
question rather than ruled on. It has now been answered.

### Confirmation on the real instrument

Bengisu's FR-7 run at `1ae6c3a` (`scripts/resolution_measurement.py`, output in the
then-untracked `docs/evidence/resolution-measurement/resolution.tsv`, qiskit 2.4.1 /
qiskit-aer 0.17.2, 32 repeats, 4096 shots, seed 58) measures the same quantities
against the real circuits and the real reference model. She had already adopted
`D_R2 = 1 − R²` — `scripts/resolution_measurement.py:261` registers the metric as
`("one_minus_r2", R2Score(), lambda value: 1.0 - value)`.

Counts-mode baselines, and the `mean/sd` ratio that decides whether the **raw** rule
could ever have fired:

| cell | baseline mean | baseline sd | `mean/sd` | raw rule reachable? |
| --- | --- | --- | --- | --- |
| `ghz_n3` / `one_minus_r2` | 0.000527 | 0.000677 | **0.78** | no |
| `qft_n3` / `one_minus_r2` | 2.202 | 1.570 | **1.40** | no |

Both below 3, so **finding 1 is confirmed on the real circuits**: had the raw rule
shipped, it would have been unreachable on both, at every delta. The synthetic
estimates (0.96 and 1.59) sit in the same regime.

Finding 2 is confirmed more sharply still. The predicted `E[D0] ≈ 2` for a uniform
reference is measured at **2.202**, and the consequence predicted in the thread — that
`D_R2` fails to resolve a delta Hellinger resolves easily on QFT — is exactly what the
run reports:

| cell | delta | threshold | between-model mean | resolved |
| --- | --- | --- | --- | --- |
| `qft_n3` / `hellinger` | 1e-1 | 0.0363 | 0.1896 | **true** |
| `qft_n3` / `one_minus_r2` | 1e-1 | 6.912 | 1.012 | **false** |
| `ghz_n3` / `one_minus_r2` | 1e-2 | 0.002557 | 0.005587 | true |

On the non-uniform reference `one_minus_r2` behaves correctly and resolves at `1e-2`.
On the uniform one its threshold is `6.912` against a largest observed between-model
value of `1.012` — it cannot resolve anything on this ladder, or plausibly on any
ladder, because the obstruction is the denominator rather than the effect size.

### Two consequences of the run, and a withdrawn suggestion

Both were raised in [comment 5561621562](https://github.com/SuperconducTED/superconducted-noise-engine/issues/58#issuecomment-5561621562),
written without sight of three things posted outside this session. **The record below
supersedes the framing of that comment**, which presented the first item as newly
surfaced and open when it was neither:

- the all-cells quantifier was **proposed by the lead** at 15:46, with the cell set named
  explicitly and `not resolved on ladder` pre-authorised as its honest outcome;
- **@yigit-arda ratified** that quantifier at 16:54, together with items 7–8 and the
  `D_R2` orientation;
- **@bengisucvd reported the identical finding at 19:28**, three minutes earlier, with
  the same figures, escalated the QFT-cell question to @BurakOztekin, and recommended
  **retaining** the cell.

**1. One structurally unresolvable cell decides the counts-mode headline.**
`smallest_resolved_delta` (`scripts/resolution_measurement.py:436-457`) returns a delta
only when **every** cell in `_REQUIRED_CELLS[mode]` resolves it, and that frozenset
includes `("qft_n3", "one_minus_r2")`. Since that cell resolves at no delta, the
counts-mode headline evaluates to `None`, which `main` renders as
`"not resolved on ladder"`. Applying that rule to the run's own TSV:

| delta | cells resolving | not resolving |
| --- | --- | --- |
| 1e-4 | — | all four |
| 1e-3 | — | all four |
| 1e-2 | `ghz`/`hellinger`, `ghz`/`one_minus_r2` | `qft`/`hellinger`, `qft`/`one_minus_r2` |
| 1e-1 | `ghz`/`hellinger`, `ghz`/`one_minus_r2`, `qft`/`hellinger` | **only** `qft`/`one_minus_r2` |

So the registered counts-mode conclusion reads as "counts mode resolves nothing at 4096
shots" when what the data shows is "counts mode resolves `1e-2` on GHZ and `1e-1` on QFT
under Hellinger, and R² has no denominator on QFT". #62's first sign-off decision reads
that row, so the gap matters.

The suggestion that `("qft_n3", "one_minus_r2")` might be dropped from `_REQUIRED_CELLS`
is **withdrawn**. @bengisucvd's counter-argument is correct and decisive: excluding a
cell from a predeclared protocol *after observing it fail* is post-hoc selection, which
is precisely the failure mode `docs/numerical-claims.md` exists to prevent. A protocol
that can shed its inconvenient cells measures the analyst, not the instrument. Reporting
per-circuit instead is also rejected, because it contradicts a quantifier @yigit-arda
has already ratified.

What survives is the disclosure, which is compatible with retaining the cell: the NC row
must say **which single cell** drove the headline to `None`, so a reader of #62's
sign-off cannot mistake "one ill-conditioned metric on one circuit" for "the instrument
resolves nothing". Whether anything further changes is @BurakOztekin's, on
@bengisucvd's escalation.

**2. The density-matrix figure is ladder-limited, not instrument-limited.** Both
density-matrix cells resolve at **all four** rungs, so `smallest_resolved_delta` returns
the smallest rung on the ladder (`1e-4`). That is where the placeholder ladder stops,
not where the instrument stops — the true resolution is somewhere below `1e-4` and this
ladder does not bracket it. The NC row should therefore read `≤ 1e-4, ladder-limited`
rather than `= 1e-4`, which is a natural extension of the `provisional, placeholder
ladder` note §6.5 already requires, not a new caveat.

## Design decisions

**`D_R2 = 1 − R²` over reversing the comparison.** Both are algebraically equivalent.
The first was chosen because density-matrix mode already reports `1 − F`, so after the
change both reported discrepancies share one convention — identity at zero, increasing
with distance — and the §6.5 rule keeps a single statement for every metric. Reversing
the comparison instead leaves the two reported quantities with different identity values
and a rule that reads in two directions depending on which row you are looking at.

**Decision 1 confirmed with `raise` as the default.** The alternatives were raise-only
(drops #62's partial-table path, which crashes an ablation after twenty minutes of Aer)
and defaulting to `record` (restores a NaN row as the default output). Defaulting to
`raise` forces #62 to request a lossy table explicitly, which is the correct default
for the failure mode `docs/numerical-claims.md` exists to prevent. One test constraint
was added inside §9.1's existing `_try_compute` row rather than as new scope: pin that
`record`'s `failure` string is non-empty, since a NaN row with an empty `failure` is
defect 3 under a new name.

**All eight agreed at lead level, with owner sign-off explicitly not substituted.** The
alternative was answering only the item addressed to the lead. Recording agreement on
all eight tells Bengisu the recommendations are not going to be re-litigated, so §8
step 3's "build behind them" is safe; stating plainly that @BurakOztekin still owed 1–4
and 6–8 and @yigit-arda 7–8 keeps the ticket's ownership model intact and prevents a
lead opinion being counted as an owner confirmation. @yigit-arda has since discharged
7–8 (and the `D_R2` orientation, and the all-cells quantifier) at 16:54; @BurakOztekin's
ratification of 1–4 and 6–8 remains outstanding, as does the QFT-cell escalation.

**Decision 6 endorsed, `ReferenceReport` left alone.** Bengisu's precedence — report all
10 dead pairs, install relaxation on the 6 with usable endpoints, leave the 4 touching
q72 uninstalled under ADR-017 — is the only reading that satisfies decision 6, ADR-017
and §9.1's `expand` requirement simultaneously, and it imputes nothing. Extending
`ReferenceReport` to cover the twelve single-qubit dead entries was considered and
**not** taken: `dead_pairs` is `cz`-only per §2 and §9.1, the report's shape belongs to
`harness.py`'s owner, and expanding it from the lead's chair would pre-empt the
ratification being asked for. The fact was put in the thread instead, so decision 6 is
ratified with it visible.

**No NC rows registered for these numbers.** The register's Purpose scopes it to
public-facing documentation — flagship `README.md`, org profile, `docs/architecture.md`,
`docs/findings/`, `docs/state-of-the-project/`, papers and slides — and
`docs/implementations/` is not in that list. The synthetic figures are also from a
reimplementation, not the certified harness, so registering them would put a number in
the register that the instrument being certified did not produce. FR-7 registers the
resolution rows, at merge time, from the real script. Rule 1 still applies and is met
by the reproduction below.

**Not committed to Bengisu's branch.** `bengisu/issue-58-benchmark-certification` is
hers and was advancing throughout the session. This document is the lead's record of a
sign-off, not part of her certification PR, and committing it there would entangle the
two. It is left untracked for the lead to commit from a clean tree on a branch off
`main`. No `git checkout`, `stash` or `commit` was run at any point, because the branch
was in active use on this machine.

## Verification

Fixture counts (10 dead `cz`, q72 sole missing T1/T2, 4 touching q72, no `T2 > 2·T1`,
`sx` at 24 ns on all 156 qubits):

```bash
git fetch superconducted-noise-engine feature/issue-57-training-target
```

```bash
git show FETCH_HEAD:tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json > /tmp/wg.json
```

```bash
python -c "
import json
d=json.load(open('/tmp/wg.json'))['properties']
miss=[i for i,q in enumerate(d['qubits']) if {p['name']:p['value'] for p in q}.get('T1') is None or {p['name']:p['value'] for p in q}.get('T2') is None]
dead=[tuple(g['qubits']) for g in d['gates'] if g['gate']=='cz' and {p['name']:p['value'] for p in g['parameters']}.get('gate_error')==1]
sq=[(g['gate'],tuple(g['qubits'])) for g in d['gates'] if g['gate']!='cz' and {p['name']:p['value'] for p in g['parameters']}.get('gate_error',0)>=1]
print('missing T1/T2:',miss); print('dead cz:',len(dead),sorted(dead))
print('touching 72:',sorted(p for p in dead if 72 in p)); print('single-qubit gate_error>=1:',len(sq),sorted(sq))
"
```

Metric semantics at the cited commit (`reference_value` is exactly 1.0 for R²,
`_try_compute` swallows two exception types):

```bash
git show 7d39a2b:src/superconducted/benchmarks/harness.py | sed -n '125,155p'
```

NC id allocation (max is `NC-030`, 29 rows, the hole at 013 is `NC-R002`):

```bash
grep -oE "^\| NC-(R?)[0-9]+" docs/numerical-claims.md | sort -u | tail -8
```

The resolution-rule analysis. Self-contained, no third-party imports; reproduces every
figure in the synthetic Measurements tables:

```python
import math, random, statistics
from collections import Counter
SHOTS, R = 4096, 40
def probs(c, s):
    t = sum(c.values())
    return [c.get(k, 0)/t for k in s]
def r2(a, b):
    s = sorted(set(a) | set(b)); pe, pr = probs(a, s), probs(b, s)
    ss_res = sum((x-y)**2 for x, y in zip(pr, pe)); m = sum(pr)/len(pr)
    ss_tot = sum((x-m)**2 for x in pr)
    return (1.0 if ss_res == 0.0 else 0.0) if ss_tot == 0.0 else 1.0 - ss_res/ss_tot
def hell(a, b):
    s = sorted(set(a) | set(b)); pe, pr = probs(a, s), probs(b, s)
    return math.sqrt(sum((math.sqrt(x)-math.sqrt(y))**2 for x, y in zip(pe, pr)))/math.sqrt(2.0)
def mk(keys, p, seed):
    return Counter(random.Random(seed).choices(keys, weights=p, k=SHOTS))
def perturb(p, eps):
    q = list(p); m = min(eps, q[0]); q[0] -= m; q[1] += m
    return q
def study(label, keys, P):
    pairs = [(i, j) for i in range(R) for j in range(R) if i < j]
    d0 = [r2(mk(keys, P, 1000+i), mk(keys, P, 1000+j)) for i, j in pairs]
    h0 = [hell(mk(keys, P, 1000+i), mk(keys, P, 1000+j)) for i, j in pairs]
    m0, s0 = statistics.fmean(d0), statistics.stdev(d0)
    hm, hs = statistics.fmean(h0), statistics.stdev(h0)
    md, sd_ = statistics.fmean([1-v for v in d0]), statistics.stdev([1-v for v in d0])
    print(f"\n[{label}] bins={len(keys)} raw floor {m0:.6f}+-{s0:.6f} "
          f"threshold {m0+3*s0:.6f} reachable={m0+3*s0 <= 1.0} mean/sd(D0)={md/sd_:.2f}")
    for eps in (0.0, 1e-4, 1e-3, 1e-2, 1e-1):
        Q = perturb(P, eps)
        b = [r2(mk(keys, P, 1000+i), mk(keys, Q, 1000+i)) for i in range(R)]
        hb = [hell(mk(keys, P, 1000+i), mk(keys, Q, 1000+i)) for i in range(R)]
        mb, mh = statistics.fmean(b), statistics.fmean(hb)
        print(f"  eps={eps:<7g} rawR2={mb:.6f} rawFires={mb > m0+3*s0}  "
              f"D_R2={1-mb:.6f} fires={1-mb > md+3*sd_}  Hell={mh:.6f} fires={mh > hm+3*hs}")
K3 = [f"{i:03b}" for i in range(8)]
study("GHZ-like, concentrated", K3, [0.455,0.012,0.011,0.008,0.010,0.009,0.013,0.482])
study("QFT-like, near-uniform", K3, [0.130,0.128,0.124,0.122,0.125,0.121,0.126,0.124])
study("uniform, 64 bins", [f"{i:06b}" for i in range(64)], [1/64]*64)
```

Expected, as differentials rather than absolutes: the GHZ-like and QFT-like rows report
`reachable=False`; the 64-bin row reports `reachable=True` **and** `rawFires=True` at
`eps=0`; `D_R2` and Hellinger both fire only at `eps=1e-1` on the GHZ-like reference;
and on the QFT-like reference `D_R2` fires nowhere while Hellinger fires at `eps=1e-1`.

Against the real instrument, once FR-7's TSV is committed: the `qft_n3`/`one_minus_r2`
row's `resolved` column is `false` at every delta while `qft_n3`/`hellinger` is `true`
at `1e-1`, and both `ghz_n3` cells are `true` at `1e-2`. Stated as a differential —
the QFT R² cell resolves strictly fewer deltas than the QFT Hellinger cell — so the
expectation survives a re-run at a different seed.

## Related docs

- Issue #58 §6.5 (resolution measurement), §7 (the eight decisions), §9.1 (the
  `_try_compute` and `build_reference` pins), §8 step 14 (NC row allocation)
- Issue #62 (ablation; consumes FR-7's rows and decision 1's `on_error`), #57 / PR #69
  (owns the gates fixture verified here), #64 (builds on this signature)
- ADR-017 in `docs/decisions.md` (Skip: q72 is dropped, never imputed); ADR-019
  (4096-shot protocol); ADR-022 (validation criteria); ADR-008 (the multi-qubit gap
  `full_device` exposes)
- `docs/numerical-claims.md` — Purpose (scope of the register), "Adding a claim",
  "Retiring a claim"; NC-R002 is the retired `NC-013`
- `docs/implementations/2026-05-13-harness-metric-sanity-checks.md` — the metric
  formulas reimplemented for the analysis above
- `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` — the record
  that retires `NC-013` as `NC-R002`
- `docs/implementations/2026-09-02-pr50-review-fixes.md` — the reproduce-before-fixing
  precedent this session followed
- `docs/implementations/2026-08-31-adr-nc-collision-and-branch-reissue.md` — why NC ids
  are taken at merge time, never reserved while drafting
