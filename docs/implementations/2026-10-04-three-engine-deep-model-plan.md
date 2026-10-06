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
| `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` | The architecture research Dr. Akba asked for: four strategy families judged against the forecasting task, the T1/T2 epoch finding, a recommended first version (documented, not adopted), a fair test of supervised contrastive learning, and 68 sources, 67 of them with identifiers verified. |
| `docs/advisor/2026-10-04-uc-motor-ve-derin-model-ozeti.md` | A Turkish summary of the plan and the research for the lead to walk Dr. Akba through, ending with the ten decisions that are his. |
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
- `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` (the research, added the
  same day)

## Same-day amendment · 2026-10-04: the learning task, the research, and the SCL test

The first push of this PR (`2d840d7`) had a flaw the lead's next request exposed. Dr.
Akba also asked him to research which architectural strategy to follow, for example
supervised contrastive learning or reinforcement learning. Framing that question showed
the plan never said **what the deep model predicts**, and ADR-027's target is a
closed-form function of the same state's `T1`, `T2` and gate length. A same-snapshot
deep model would learn a known formula, its band would shrink to nothing, and stage 1's
ranking would rediscover `T1` and `T2`. The lead chose forecasting (decision A7), and the
plan now says so in its §2.0, with stage 1, the band and tasks T4 and T5 redefined for a
horizon `h` and two new measurement tasks (T12, T13) to choose it. The plan was edited in
place because it is unmerged and unreviewed; nothing on `main` changed.

**The research.** Four independent passes, one per family (contrastive and
representation, reinforcement learning, forecasting with drift-robust bands, structure and
physics), were each given the same problem statement and asked to argue fit against it.
Each citation had to carry an identifier the pass had fetched. Afterwards:

- all 62 arXiv IDs were resolved against the arXiv API and all 5 DOIs against Crossref,
  with every title matching;
- the load-bearing content claims were checked against each paper's abstract;
- one figure a pass took from a search snippet (an "80% to 94%" accuracy) was excluded by
  the pass itself;
- one detail that did not reproduce (the share of qubits on the modal `T1` date) was left
  out.

**The finding that changes the evaluation.** A research pass found, and an independent
script then re-measured over all 1,697 `ibm_fez` files at `calibration-data` `43607a2`,
that the archive holds only 132 distinct `T1` vectors (and 132 `T2`). The `T1` vector
changes in 131 of 1,696 consecutive file pairs, so 92.3% of consecutive files repeat it,
and the gap between re-measurements is 3.9 h at minimum, 24.7 h at the median and 134.2 h
at most. A split-conformal band calibrated on such rows can have zero width and still
report about 92% coverage. The research doc documents the remedy (epochs as rows, coverage
on change events). The lead kept it as a recommendation, not a decision, and flags it only
on Issue #110.

**The lead's decisions in this amendment.** A7 (forecasting) and A8 (test supervised
contrastive learning, because Dr. Akba raised it; task T14, with the fair-test design in
the research doc §2.1a). The research's other recommendations (adaptive conformal with
asymmetric scores, a grey-box residual forecaster, the epoch protocol) are documented and
not adopted; A1 to A6 stay as written until after the meeting.

**The epoch arithmetic, stated.** With `C` the number of consecutive pairs whose `T1`
vector changes and `P` the number of consecutive pairs, the zero-residual fraction under
one-step persistence is `f = 1 - C/P = 1 - 131/1696 = 0.923`. Split conformal's quantile
is the `ceil((n + 1)(1 - alpha))`-th smallest score, which is zero whenever at least that
many scores are zero, i.e. when `f >= 1 - alpha` (up to the `n + 1` correction). At
`alpha = 0.1` that holds.

**Verification of the amendment** (laptop, provisional, same environment as above):

- `ruff check`: `All checks passed!`
- `ruff format --check`: `68 files already formatted`
- `scripts/check_ids.py`: no duplicate or colliding ids
- `mypy --strict`: `Success: no issues found in 38 source files`
- `pytest`: 701 collected and 701 passed

Only line wrapping changed after the full run, and `ruff format --check` and
`check_ids.py` were re-run after it. The epoch script and the citation checks are scratch
tools, not committed. T12 registers the epoch count properly.
