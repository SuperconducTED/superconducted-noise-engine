# 2026-10-04: the three-engine and deep-model plan

## Problem / Motivation

Between 2026-09-29 and 2026-10-02 Dr. Akba approved, in person, the team-decides process
and the six 2026-09-09 brief files, and set a direction: **three engine modes**, Type-1
fuzzy, Interval Type-2 fuzzy and a deep-learning model, to be planned in detail with him
in the week of 2026-10-05. That is what the decisions register holds (PR #98). The
method detail below comes from the lead's account of the conversation on 2026-10-04,
which the plan's task T0 records in the register. By that account, Dr. Akba described
the deep model's method: count our parameters and features, enumerate the scenarios
their combinations can produce, run the deep model according to that, then find the
important features, engineer them, and build the model on top as a second layer. He left
the architecture to the lead.

Nothing in the repository supported that conversation. File 02 (Issue #84) had proposed a
NumPy MLP baseline and said it "needs a ticket and an owner"; no ticket was filed. The
engine has no seam a non-fuzzy model can plug into. ADR-013, the feature-engineering
decision, is deferred until the training floor is met. And nobody had counted which
calibration fields the archive actually offers. This change puts a dated plan, a Turkish
summary for Dr. Akba and a tracking issue (#110) in place, built on the lead's
architecture decisions of 2026-10-04.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` | The dated plan: the three engines and what they share, the two-stage deep model, scenario enumeration and permutation importance, the parameter budget, the engine seam, the ledger tasks, a gated task list, risks, and the questions for Dr. Akba. |
| `docs/advisor/2026-10-04-uc-motor-ve-derin-model-ozeti.md` | A Turkish summary of the plan for the lead to walk Dr. Akba through, ending with the six decisions that are his. |
| `docs/implementations/2026-10-04-three-engine-deep-model-plan.md` | This record. |

No code, test, ADR or register row changes. The ledger changes the plan needs are tasks in
it (§6), not edits here.

## Implementation approach

**Questions before writing.** Several words in the direction have more than one reading:
"permutation", "scenarios", "second layer", and the sample unit. So the lead was asked to
choose between concrete readings, each priced with measured facts, before anything was
written. His answers are the plan's decisions A1 to A6.

**Orientation measurements, labelled as such.** Three read-only checks shaped the plan:

- **A field inventory** over 60 `ibm_fez` snapshot files taken by position at
  `calibration-data` `43607a2`.
- **A duplicate check** comparing per-qubit values between candidate duplicate fields.
- **A presence check** recording the first appearance of each field.

They are reported in the plan as **provisional** with their sample basis: 60 files, not 60
distinct states. Task T1 replaces them with a registered measurement. The archive size
(740 distinct states) is read from `health/metrics.json` at `43607a2` and is likewise
provisional until Issue #63 registers its own count.

**The plan defers every ledger edit.** ADR-005's scoping note, ADR-013's revisit note, the
seam ADR and the stage-B ADR are tasks with gates. The lead approves decisions in the
advisor role in a separate session, so this plan proposes and does not decide.

## Mathematical / Statistical details

**MLP parameter count.** A fully connected network with `d` inputs, one hidden layer of
`h` units and `k` outputs, with biases, has `(d + 1)h + (h + 1)k` parameters. With
`k = 2` outputs `(gamma, lambda)` that is `(d + 3)h + 2`. For `d = 3`: `6h + 2`, so 236 at
`h = 39` and 242 at `h = 40`. Exactly 234 or 243 would need `h = 38.67` or `h = 40.17`, so
exact matching to the fuzzy arms (NC-045, NC-046) is impossible here. The plan's rule is
the nearest count not exceeding 243, with both counts reported.

**Grid fuzzy parameter count.** From NC-045's formula, a grid rule base on `d` features
with `L` membership functions per feature has `R = L^d` rules and
`count = k * R * (d + 1) + sum_j p_j`, where the sum runs over the unique membership-function
objects. At `L = 3`, `d = 6`, `k = 2`: `R = 729` and the consequent term is
`2 * 729 * 7 = 10,206`. Under NC-012's five-samples-per-parameter rule, the floor exceeds
51,000 states. Arithmetic on registered formulas, not a measurement.

**Scenario enumeration.** Discretize each of `n` features into `L` levels using edges from
the training portion only. Theoretical cells: `L^n`. Occupied cells: the number of distinct
level-tuples among the archive's rows. Reported with samples per occupied cell. At `L = 3`
the cell count equals a grid fuzzy engine's rule count on the same features.

**Permutation feature importance.** For model `f`, held-out `(X, y)` and loss `L`:
`I_j = (1/R) * sum_r [L(f, X^(j,r)) - L(f, X)]`, where `X^(j,r)` is `X` with column `j`
shuffled by the `r`-th permutation. The grouped variant shuffles a set of correlated
columns jointly, which prevents a correlated partner from masking a feature's importance.

**Split conformal band.** For each output and a calibration slice of size `n`, the scores
are `s_i = |y_i - f(x_i)|`, `q_hat` is the `ceil((n + 1)(1 - alpha))`-th smallest score,
and the band is `f(x) +/- q_hat`. Under exchangeability, coverage is at least `1 - alpha`.
A time split breaks exchangeability, so measured coverage on later snapshots is a result,
not a guarantee.

## Design decisions

1. **Two-stage deep model (A1) over two alternatives.** One was the stage-1 ranking
   selecting every engine's inputs, which is fairer but changes E1 and E2. The other was a
   stacked neuro-fuzzy model, a new hybrid engine. The lead chose the two-stage reading of
   Dr. Akba's direction and recorded the other two as future work (A6).
2. **Both readings of "permutation" (A2).** Enumeration answers his first question, how
   many scenarios can occur; permutation importance answers his second, which features
   matter.
3. **Snapshot rows first, per-qubit second (A3).** Snapshot rows match today's engines and
   the existing target. Per-qubit rows have roughly 156 times as many rows and every
   per-qubit feature, but need the engine to emit per-qubit noise.
4. **NumPy by hand (A4) over scikit-learn or PyTorch.** No new dependency, consistent with
   ADR-005, and a custom loss stays possible. The cost is a gradient check as a gate.
5. **Split conformal (A5) over a deep ensemble or quantile outputs.** It is model-agnostic,
   costs one held-out slice, and gives a coverage statement. Its interaction with IT2's
   Karnik-Mendel band is left to Dr. Akba as plan §1.1 and question 2.
6. **A roadmap document, not an ADR.** The plan proposes; the ADRs follow as tasks once the
   decisions are approved and the evidence exists.

## Verification

Documentation only, so the suite is unchanged by construction. The gates are still run,
because tests and `scripts/check_ids.py` read `docs/`. These are provisional laptop runs:
`C:\pvci`, CPython 3.12.10, with `PYTHONPATH` set to this tree's `src`.

```bash
python -m ruff check
python -m ruff format --check
python scripts/check_ids.py
python -m mypy --strict
python -m pytest tests/ --collect-only -q -o addopts="" -p no:cacheprovider
python -m pytest tests/ -q -p no:cacheprovider
git diff origin/main --stat -- src/ tests/ scripts/   # empty: no code touched
```

| Check | Result |
| --- | --- |
| `ruff check` | `All checks passed!` |
| `ruff format --check` | `68 files already formatted` |
| `scripts/check_ids.py` | no duplicate or colliding ids |
| `mypy --strict` | `Success: no issues found in 38 source files` |
| `pytest --collect-only` | 701, equal to NC-021 |
| `pytest` | 701 passed |

NC-021 records 701 at `6630fca`; only `docs/` changed between it and `110cfad`, this
branch's base.

## Related docs

- Issue #110 (tracking), Issue #84 (File 02 Q1c, Q1d; File 05 Q1a), Issue #109 (the
  phase-3 residue), PR #98 (Dr. Akba's approval in the decisions register)
- ADR-005, ADR-013, ADR-017, ADR-021 and ADR-027 in `docs/decisions.md`
- `docs/roadmap/2026-09-03-phase-3-plan.md` §5 (gates are artifacts)
- `docs/implementations/2026-09-09-training-floor-derivation.md` (NC-045, NC-046)
