# 2026-09-09: deriving the ANFIS training floor from the rule base

## Problem / Motivation

Issue #56 FR-10. The project's training floor was a number nothing derived.

`docs/numerical-claims.md` NC-012 recorded the floor as `>= 630`, explained as "roughly 126
trainable parameters x 5". Nothing in the repository derived the 126. `git log -S'126'`
puts it into `docs/architecture.md` on **2026-05-07**, before the 27-rule grid existed, and
it then propagated into four documents. This is the same failure mode the register was
created to prevent: NC-R001 is the retirement of a fabricated benchmark figure that spread
across four documents before anyone checked it.

The input needed to fix it landed in cycle 2's closing weeks. `count_trainable_parameters`
merged in PR #69 (`src/superconducted/training/parameters.py`), so the rule base can now be
asked directly instead of recalled.

FR-10 asks for the count measured on the **ADR-009-decided** rule base. ADR-009 reads
`Open` at `5f935ea` and the memo that would decide it (#60, #62) has not landed, so this
work takes the escape hatch FR-15 explicitly provides: the floor is registered against the
configuration actually in use, with that caveat written into the row, and the per-shape
spread is registered beside it so the reader can see how far the answer could move.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | Adds **NC-045** (the measured count and the floor derived from it) and **NC-046** (the per-shape spread as one conclusion row); corrects **NC-012**'s value and date together per Rule 3; corrects the derived ratio in **NC-025**'s Notes. |
| `docs/architecture.md` | The `## Calibration polling` sentence now states `>= 1170` and cites NC-045 and NC-012, and records what it said from 2026-05-07 until today. Living document, so edited in place. |
| `docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md` | Appends `## Floor correction · as-of 2026-09-09`. Dated, so appended, not edited. |
| `docs/implementations/2026-09-02-pr50-review-fixes.md` | Appends `## Floor correction · as-of 2026-09-09`. Dated, so appended, not edited. |

Those are the four documents FR-10.3 names: two edited, two appended. No executable line
changed.

## Implementation approach

The rule base is asked, not reasoned about. `count_trainable_parameters` is run on
`TSKRuleBase.from_grid` for each implemented membership-function shape at the grid the
project actually ships, and the outputs are recorded verbatim.

```python
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.fuzzy.membership import GaussianMF
from superconducted.training.parameters import count_trainable_parameters

per_input = [[GaussianMF(center=c, sigma=0.15) for c in (0.2, 0.5, 0.8)] for _ in range(3)]
count_trainable_parameters(TSKRuleBase.from_grid(per_input, output_dim=2))
# ParameterCount(premise=18, consequent=216, total=234)
```

**The `GaussianMF` result is the control.** It must equal NC-037's registered 234, measured
independently at candidate `37e1ba0` by `tests/training/test_parameters.py`. It does. That
agreement is what licenses the other six rows: they were produced by the same procedure, on
the same commit, differing only in the shape passed in.

**Two rows, not eight.** NC-045 carries the conclusion that matters (the count in use and
the floor derived from it). NC-046 carries the seven-shape spread as **one row**, applying
the one-row-per-reported-conclusion rule that #56 FR-14 adds to `## Adding a claim` in
PR #85. Registering seven rows for one table is exactly the pattern that rule exists to
prevent; the per-shape table lives here, in the mathematics section, and NC-046 points at
it.

**NC-012 is corrected rather than retired.** Rule 5 sends a claim to the `Retired` section
when it is removed from public documents. The floor is not being removed; its value was
wrong. Rule 3 governs that case: update the value and the date together, which this does,
with the Notes recording what the row said until 2026-09-09 and why it changed.

**NC-025's measured value is untouched.** Its 504 distinct states, measured at
`calibration-data` `f0930b9`, is unaffected. Only the ratio derived from it in the Notes
changes, from `504/126 ~ 4.0` to `504/234 ~ 2.15`, and the note says so explicitly so a
reader does not mistake a corrected derivation for a re-measurement.

## Mathematical / Statistical details

**The count.** For a rule base built by `TSKRuleBase.from_grid` with `R` rules, input
dimension `d`, output dimension `k`, and `U` unique membership-function objects each
carrying `p` trainable parameters:

```
count = k * R * (d + 1)  +  U * p
        \___________/       \___/
         consequent         premise
```

The consequent term is the affine map per rule per output: one coefficient for each of the
`d` inputs plus a bias, hence `d + 1`, for each of `k` outputs, for each of `R` rules.

The premise term is the subtle one. `U` counts **unique membership-function objects**, not
antecedent references. `from_grid` iterates `product(*per_input_mfs)` and reuses one object
across every rule that names it, so a 3x3x3 grid has 27 rules and 81 antecedent references
over only **9** distinct objects. `count_trainable_parameters` enumerates them through
`premise_layout`, which deduplicates by `id`. Counting the 81 references instead would
inflate the premise term ninefold and, worse, would misdescribe training: setting one
object's parameters changes what all 27 rules using it compute.

**The configuration in use.** `R = 27`, `d = 3`, `k = 2`, `U = 9`, `p = 2` for `GaussianMF`:

```
consequent = 2 * 27 * (3 + 1) = 216
premise    = 9 * 2            =  18
count      = 216 + 18         = 234
```

**Per-shape totals**, measured at `main` @ `5f935ea`. The consequent term is fixed at 216
for every shape, so the entire spread comes from `p`:

| Shape | `p` | Premise `U*p` | Consequent | Total | Floor `x5` | IT2 |
| --- | --- | --- | --- | --- | --- | --- |
| `GaussianMF` | 2 | 18 | 216 | **234** | 1170 | no |
| `TanhSigmoidMF` | 2 | 18 | 216 | 234 | 1170 | no |
| `TriangularMF` | 3 | 27 | 216 | 243 | 1215 | no |
| `TanhBellMF` | 3 | 27 | 216 | 243 | 1215 | no |
| `IntervalGaussianMF` | 3 | 27 | 216 | 243 | 1215 | **yes** |
| `TrapezoidalMF` | 4 | 36 | 216 | 252 | 1260 | no |
| `TanhMF` | 4 | 36 | 216 | 252 | 1260 | no |

**The floor.** `floor = count * 5`, where 5 is NC-012's samples-per-parameter rule of
thumb, unchanged by this work. For the configuration in use, `234 * 5 = 1170`.

**Why the old 126 was wrong, precisely.** It is reproducible only as
`1 * 27 * (3 + 1) + 9 * 2 = 108 + 18 = 126`: the premise term is right, and the consequent
term is computed at `k = 1` for a model whose `output_dim` is 2. It counts half the
consequent parameters of the model it describes. It also predates the 27-rule grid, so at
the time it was written it did not describe any rule base that existed.

**What the corrected floor means for the archive.** NC-025 records 504 distinct device
states at `calibration-data` `f0930b9`:

```
504 / 234 = 2.15 samples per trainable parameter   (was reported as 504 / 126 = 4.0)
```

The direction matters more than the magnitude: every prior document said the gate was not
met, and the correction makes the shortfall **larger**, not smaller. Nothing that was
claimed becomes false; a claim that was true becomes more true.

**Two caveats that survive the correction unchanged.**

1. **This is a claim gate, not an implementation gate.** It decides what the results
   document may assert about training sufficiency. No code waits on it.
2. **Distinct states are an upper bound on independent samples.** Consecutive device states
   are temporally correlated (T1/T2 published roughly daily, readout roughly every 4 h), so
   the effective sample size is below the distinct-state count. Crossing 1170 would
   therefore still not prove training sufficiency. NC-012 has carried this caveat since
   2026-09-02 and it is not weakened by re-deriving the threshold.

**A consequence worth naming for ADR-009.** The standard objection to Interval Type-2 is
that it doubles the parameter count. On this rule base it does not:
`IntervalGaussianMF` costs `U * (3 - 2) = 9` parameters more than `GaussianMF`, which is
3.8% of 234 and moves the floor by 45. IT2 adds one parameter per unique MF object, and
there are only 9 of those, while the consequent term that dominates the total is
type-independent. The parameter-count argument against IT2 is therefore not available on
this configuration, which is a measured input the ADR-009 memo (#60, #62) did not have.

## Design decisions

**Why register the floor now rather than wait for ADR-009.** FR-15 states the fallback
explicitly: if the advisor has not answered by M3, ADR-009 stays `Open` and the floor is
registered against the configuration actually used with that caveat in the row. Waiting
would leave the underived 126 propagating across four documents for another two weeks, and
the 126 is wrong under every shape in the table, not only under the current one. NC-046
bounds the residual uncertainty: whatever ADR-009 decides, the floor lands between 1170 and
1260.

**Why NC-012 is corrected rather than retired and replaced.** Considered: retire NC-012 and
register the floor as a fresh row. Rejected because NC-012 is cited by name in several
documents and by ADR-014's context; retiring it would turn every one of those citations into
a dangling reference to the `Retired` section, and the claim itself ("there is a training
floor, expressed in distinct device states") did not become false. Rule 3 is the rule for a
value that changes.

**Why the two dated documents get appended sections rather than edited numbers.** They are
dated records of what was believed on 2026-08-29 and 2026-09-02, and both used the 126 to
support arguments that remain correct. Editing the number in place would make each document
appear to have known something it did not, and would erase the evidence that the project
reasoned from an unsourced figure for four months. The appended sections say what changed,
by how much, and that the document's own conclusions are unaffected.

**Why `docs/architecture.md` is edited in place instead.** It is a living document with no
date in its filename, describing the system as it currently is. A living document that
states a superseded floor is simply wrong, not historically accurate. The edited sentence
still records what it said until 2026-09-09, so the change is visible without needing the
git history.

**Identifier allocation.** NC-045 and NC-046 are the next free ids **beyond every id claimed
on an open branch**, checked at 2026-09-09: `main` reaches NC-040, PR #68 claims NC-041
through NC-044, and PR #70 claims NC-042. Taking the nominal next id, NC-041, would have
collided with PR #68 immediately. Per the rule PR #85 writes into `docs/team.md`, these are
re-checked at merge and renumbered if a concurrent branch has taken them.

> **NOTE · A collision already exists between two other open PRs.** PR #68 registers NC-042
> as "median per-qubit spread within a snapshot, by feature" and PR #70 registers NC-042 as
> "537 distinct states from 936 documents". Two different claims, one identifier, both open.
> Whichever merges second must renumber. `scripts/check_ids.py` catches this once the first
> is on `main`, but only if CI dispatches on the second. Flagged on both threads.

## Verification

```bash
# 1. The count reproduces, and the GaussianMF control matches NC-037.
python -c "
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.fuzzy.membership import (GaussianMF, TriangularMF, TrapezoidalMF,
    TanhMF, IntervalGaussianMF, TanhSigmoidMF, TanhBellMF)
from superconducted.training.parameters import count_trainable_parameters
def mk(cls, c):
    if cls is GaussianMF:         return cls(center=c, sigma=0.15)
    if cls is TriangularMF:       return cls(a=c-0.2, b=c, c=c+0.2)
    if cls is TrapezoidalMF:      return cls(a=c-0.25, b=c-0.08, c=c+0.08, d=c+0.25)
    if cls is TanhMF:             return cls(left=c-0.2, right=c+0.2, slope_left=6.0, slope_right=6.0)
    if cls is IntervalGaussianMF: return cls(center=c, sigma_low=0.12, sigma_high=0.18)
    if cls is TanhSigmoidMF:      return cls(center=c, slope=6.0)
    if cls is TanhBellMF:         return cls(left=c-0.2, right=c+0.2, slope=6.0)
for cls in (GaussianMF, TanhSigmoidMF, TriangularMF, TanhBellMF,
            IntervalGaussianMF, TrapezoidalMF, TanhMF):
    g = [[mk(cls, c) for c in (0.2, 0.5, 0.8)] for _ in range(3)]
    rb = TSKRuleBase.from_grid(g, output_dim=2)
    pc = count_trainable_parameters(rb)
    print(f'{cls.__name__:<20} premise={pc.premise:>3} consequent={pc.consequent} '
          f'total={pc.total} floor={pc.total*5} rules={rb.n_rules} it2={rb.is_interval_type2}')
"
# Expect GaussianMF total=234 (NC-037), the seven totals 234/234/243/243/243/252/252,
# rules=27 and consequent=216 on every row.

# 2. All four "126" documents are handled: two edited, two appended.
grep -rn '126' docs/architecture.md docs/numerical-claims.md \
  docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md \
  docs/implementations/2026-09-02-pr50-review-fixes.md
# Every remaining hit must be inside text that explains the 126 was wrong.

# 3. The two dated documents lost no line.
git diff main --numstat -- docs/implementations/2026-08-29-*.md \
  docs/implementations/2026-09-02-pr50-review-fixes.md
git diff main -- docs/implementations/ docs/roadmap/ docs/state-of-the-project/ \
  | grep '^-[^-]' || echo "append-only clean"

# 4. Identifiers do not collide on this tree.
python scripts/check_ids.py

# 5. Nothing executable moved.
git diff main --stat -- src/ scripts/            # expect empty
ruff check && ruff format --check
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1
```

The collection count is stated differentially against NC-021 in the PR description, citing
the row rather than recalling a number.

**This PR originates one number, and it is not canonically verified yet.** NC-045 and
NC-046 are provisional laptop measurements. Per NFR-9 and the convention PR #85 writes into
`docs/team.md`, they are verified by appearing in
`docs/verification/2026-09-XX-phase-3-batch-2-burak-desktop.md`, the batch record after M3.
**No per-PR verification record is filed for them**, and neither row should be described as
canonically verified until that batch record merges. Both rows say so in their Notes.

## Related docs

- Issue #56 FR-10 (the derivation), FR-14 (the conclusion-row rule NC-046 applies), FR-15 (the ADR-009-Open fallback this uses), NFR-3, NFR-4, NFR-9
- `docs/numerical-claims.md` — NC-012 (corrected), NC-025 (Notes corrected), NC-037 (the control), NC-045, NC-046, NC-R001 (why the register exists)
- `docs/decisions.md` — ADR-009 (`Open`; the shape and type are not yet decided), ADR-014 (the floor's context)
- `src/superconducted/training/parameters.py` — `count_trainable_parameters`, `premise_layout`
- `src/superconducted/fuzzy/tsk.py` — `TSKRuleBase.from_grid` and the shared-MF-object behaviour the premise term depends on
- `docs/architecture.md` — `## Calibration polling`
- `docs/state-of-the-project/2026-09-09-cycle-2-close.md` — goal 1, which reports this correction
- Issues #60 and #62 (the ADR-009 memo and its evidence), #63 (the distinct-state count at the current ref)
