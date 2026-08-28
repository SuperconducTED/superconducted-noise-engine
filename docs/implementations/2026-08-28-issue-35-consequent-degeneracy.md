# 2026-08-28: issue-35-consequent-degeneracy

## Problem / Motivation

Issue #35, raised while fixing Issue #31 (PR #34).
`TSKRuleBase.from_grid(consequent_init="random")` draws consequents from a
zero-mean Gaussian, so the sign of each defuzzified output is a property of
the draw rather than of the design. When both of the first two crisp
parameters come out non-positive, `ProbabilityClip` sends them to exactly
`[0, 0]`, and `KrausChannelProjector` builds amplitude damping at
`gamma = 0` composed with phase damping at `lambda = 0` — the identity
channel. The ensemble then runs to completion and measures nothing.

PR #34 worked around this at one call site: `first_ensemble_run.py` grew a
private `_is_degenerate` and a seed walk. That made the smoke script
self-healing but left every other caller of `consequent_init="random"`
exposed with no such search, and left the design question unanswered ahead
of the ADR-014 trainer, which would warm-start from exactly these draws.

Issue #35 asked three questions: should `from_grid` guarantee viability by
construction; or is degeneracy a documented caller responsibility; and is
"first two crisp parameters non-positive" even the right test. This change
answers all three, in ADR-024.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | New ADR-024 (**Status: Open**) settling the viability contract, with the 1/4 derivation and a warm-start constraint on the ADR-014 trainer. |
| `src/superconducted/integration/aer_factory.py` | Adds `is_identity_damping`, `FuzzyNoiseModel.is_degenerate`, `first_viable_seed`, and `DEFAULT_SEED_SEARCH_LIMIT` — the viability contract as importable code. |
| `scripts/first_ensemble_run.py` | Drops the private `_is_degenerate` and the inline seed walk; delegates to `first_viable_seed` while keeping every public signature and its selected seed. |
| `tests/test_channel_viability.py` | New. 21 tests: predicate truth table, physical grounding of "identity channel", model wiring, seed-search behavior, and the 1/4 invariance claim. |
| `docs/numerical-claims.md` | NC-023 (the 1/4 rate) and NC-024 (the seed limit) added; NC-021 moved 166 → 187 per Rule 6. |

`src/superconducted/fuzzy/tsk.py` and the whole `channels/` package are
LOCKED and are untouched — see Design decisions for why that is a technical
conclusion here, not just a procedural constraint.

## Implementation approach

The pipeline builds crisp parameters as
`features → rule_base.evaluate → defuzzify → squash`, and
`KrausChannelProjector` then reads `crisp[0]` as `gamma` and `crisp[1]` as
`lambda`. Degeneracy is therefore a joint property of the rule base, the
defuzzifier, the squashing strategy, and the projector. It is defined at the
layer that can see all four — `integration/aer_factory.py` — and nowhere
else.

Three pieces:

- **`is_identity_damping(crisp_params)`** — the predicate. Documents the
  parameter reading it encodes, and the squashing strategies it is valid for
  (`ProbabilityClip`, `IdentitySquashing`; explicitly *not* `SigmoidSquashing`,
  where nothing is ever exactly zero). It raises on a vector shorter than two
  entries rather than calling it degenerate: such a vector is one the
  projector cannot read at all, and reporting it as an identity channel would
  send the caller to inspect their RNG seed instead of their `output_dim`.
  This is a deliberate behavior change from the script's old
  `crisp.size < 2 or ...`, which conflated the two faults; it is unreachable
  from the script, which fixes `output_dim=2`.
- **`FuzzyNoiseModel.is_degenerate`** — the per-model form, so call sites
  read `if member.is_degenerate:` rather than re-deriving an index convention.
- **`first_viable_seed(build, seed_limit=64, context="")`** — deterministic
  rejection sampling. `build(seed)` must be a pure function of the seed;
  seeds are tried `0, 1, 2, ...` so the selected seed reproduces on any
  machine. `context` is prepended to the exhaustion message.

That `context` parameter exists to keep the smoke script's diagnostics
without message archaeology. The search sees only an opaque `build` callable
and cannot describe the grid, so the first version of this change had
`generate_safe_ensemble_with_seed` catch the library `ValueError` and
re-raise with the grid appended — which meant matching on message text to
tell "structural degeneracy" apart from "bad `seed_limit`", and would have
silently mislabelled an unrelated `ValueError` from
`FuzzyNoiseModelEnsemble`. Passing the caller's description down is smaller
and has one failure mode instead of three.
`CONSEQUENT_SEED_SEARCH_LIMIT` is now an alias of `DEFAULT_SEED_SEARCH_LIMIT`
so the two cannot drift.

## Mathematical / Statistical details

**Claim: the degeneracy rate is exactly 1/4, invariant to rule count,
membership-function placement, and input vector.**

Let rule `r` carry consequent matrix `A_r` of shape
`(output_dim, input_dim + 1)`, every entry an i.i.d. draw from
`N(0, sigma^2)` with `sigma = 0.1`. Let `x_aug = [x_1, ..., x_d, 1]`, and let
`w_r >= 0` be rule `r`'s firing strength — a product of membership degrees,
so a function of the antecedent MFs and `x` only, **never of the
consequents**. Weighted-average defuzzification gives, for output component
`k`:

```
out_k  =  sum_r  w_bar_r * (A_r[k, :] · x_aug),      w_bar_r = w_r / sum_s w_s
```

For fixed `x` the coefficients `w_bar_r` are constants, so `out_k` is a
linear functional of Gaussians and is itself Gaussian with

```
E[out_k]   = 0
Var[out_k] = sigma^2 * ||x_aug||^2 * sum_r w_bar_r^2
```

Rows `k = 0` and `k = 1` are *disjoint entries* of the draw, so `out_0` and
`out_1` are independent — and identically distributed, since the same
`w_bar_r` and the same `x_aug` multiply both. `ProbabilityClip` maps
`out_k <= 0` to exactly `0.0`; amplitude damping at `gamma = 0` and phase
damping at `lambda = 0` are each the identity, and the composition of two
identities is the identity. Therefore

```
P(identity channel) = P(out_0 <= 0) * P(out_1 <= 0) = 1/2 * 1/2 = 1/4
```

Rule count, MF placement, and input vector enter only through
`sum_r w_bar_r^2` and `||x_aug||^2`, both of which scale the **variance**.
Neither can change the **sign** of a zero-mean Gaussian, so neither can move
the rate. This is why Issue #35's reported spread was an artifact: at eight
samples, a binomial with `p = 0.25` has a standard error of 0.15, so 1/8 and
2/8 are both entirely ordinary outcomes of the same process.

**Empirical corroboration** (NC-023). Over seeds 0–1999 against the shipped
3×3×3 grid, `endpoint` and `interior` placement each give **0.2420**. The two
layouts disagree about *which* seeds fail — of the first 500 seeds, 117 fail
under `endpoint` and 122 under `interior`, sharing only 86 — exactly as the
derivation predicts: placement changes `w_bar`, hence the variance and hence
each individual draw, but not the rate. Rebuilt directly from the primitives,
grids of 8, 27, and 64 rules under two different input vectors all land in
[0.236, 0.261] (standard error at n = 2000 is 0.0097).

**Why the search limit is 64** (NC-024). At a 1/4 per-draw rejection rate,
all 64 failing has probability `4^-64 ≈ 2.9e-39`. Exhausting the search is
therefore never bad luck; it means the consequents are identically zero (the
`consequent_init="zeros"` bootstrap default per ADR-014), the feature vector
fires no rule, or the squashing strategy is not one this predicate describes.
The error message says so.

## Design decisions

**Rejected: a positive-biased or magnitude-only `consequent_init="random"`**
(Issue #35's question 1). `from_grid` receives `per_input_mfs` and
`output_dim` and holds no reference to the defuzzifier, the squashing
strategy, or the projector — the three components that jointly define
degeneracy. Biasing there would hard-code `KrausChannelProjector`'s reading of
`crisp[:2]` into a general TSK primitive, and would be wrong for any other
projector. Worse, it would be actively misleading under `SigmoidSquashing`:
no draw would ever look degenerate, yet a zero-mean draw gives
`gamma ≈ lambda ≈ 0.5`, a catastrophically strong channel. So `tsk.py` stays
untouched for a layering reason; the LOCKED status is a second, independent
reason rather than the primary one.

**Rejected: leaving it as per-caller responsibility with only a docstring**
(question 2). "Documented" is right; "every caller re-implements the seed
search" is not. The contract and the mechanism both ship in the library.

**Rejected: promoting the predicate to the `RuleBase` layer** (question 3).
The test is exact *here* — `test_is_degenerate_agrees_with_both_entries_zero`
shows "no positive entry" and "both exactly zero" cannot come apart under
`ProbabilityClip` across 60 draws, and
`test_degenerate_params_project_to_the_identity_channel` confirms via
`SuperOp` that `[0, 0]` is the identity channel exactly. But it is a property
of the (squashing, projector) pair, so it is scoped rather than generalized.

**Placement in `integration/` rather than `channels/`.** The predicate
belongs next to `KrausChannelProjector`, which owns the parameter contract.
`channels/` is a LOCKED zone (`channels/__init__.py`), so it lives in
`aer_factory.py` and both the code and ADR-024 record that it moves if the
`ChannelProjector` ABC ever grows a viability method.

**ADR-024 lands as `Status: Open`**, not Accepted — it answers a question
Issue #35 posed to the team, and ADR-010 set the precedent of landing Open on
`main` before ratification (PR #30).

One implementation detail worth flagging for reviewers: the Kraus
representation at `gamma = lambda = 0` is `-I`, not `+I`. The global phase is
physically unobservable, so the test compares `SuperOp`s (max `|diff|` is
exactly 0.0); a Kraus-level equality check would fail on a channel that is
genuinely the identity.

## Verification

### Provisional (Mert's laptop, Python 3.13, 2026-08-28)

```
python -m pytest tests/test_channel_viability.py -v      # 21 passed
python -m pytest -q                                      # 187 passed
python -m ruff check src/ scripts/ tests/                # All checks passed
python -m mypy                                           # Success: 22 source files
PYTHONPATH=src python scripts/first_ensemble_run.py      # endpoint, consequent_seed=1
```

All five were run on this branch. CI additionally passed on Python 3.11 and
3.12. The smoke script still selects seed 1 for `endpoint`, unchanged from
PR #34 — the refactor moved the definition without moving the behavior.

**These results are provisional.** Per project convention no laptop transcript
is authoritative; the desktop re-run below is the record that counts.

### Authoritative: desktop runbook

Posted in full, at first-year-student detail, as a second comment on PR #44
and repeated here so the durable record does not depend on GitHub. Run from a
**fresh clone into a new directory with a new venv**, in PowerShell, at commit
`5b36de0`.

Every expectation is **differential** or **self-consistent** rather than an
absolute count. That is deliberate: PR #29 pinned an absolute test count that
had gone stale, and a correct verifier reported a regression that did not
exist. An expectation that compares two values inside the same checkout cannot
rot that way.

| # | Command | Expected — the pass condition |
| --- | --- | --- |
| 1 | `git rev-parse HEAD` | `5b36de0f704fe0ac732f5cbe0459c270ed2cfe4b` |
| 2 | `python -m ruff check .` | `All checks passed!` |
| 3 | `python -m ruff format --check .` | no file listed as needing reformatting (**not** a file count — this PR adds a file) |
| 4 | `python -m mypy --strict src/superconducted` | `Success: no issues found in 22 source files` |
| 5 | `python -m pytest tests/ -q` | `0 failed` |
| 6 | `python -m pytest tests/ --collect-only -q -o addopts=""` vs `Select-String -Path docs
umerical-claims.md -Pattern "Full test-suite size"` | the two numbers **agree with each other**; the NC-021 prose names the commit it was measured at |
| 7 | `python -m pytest tests/test_channel_viability.py -v` | `0 failed` |
| 8 | `SuperOp` check of `project([0,0])` vs `project([0.2,0.1])` | `True` with `max|diff| = 0.0`, then `False` — exact arithmetic, so any difference is an environment finding |
| 9 | 2000-seed degeneracy sweep, `endpoint` and `interior` | the two printed rates **equal each other**, both near `0.25` (laptop printed `0.242` for both — context, not the pass condition) |
| 10 | `pytest ...::test_degeneracy_rate_is_one_quarter -v` | `0 failed` across 8-, 27-, and 64-rule grids plus a lopsided input vector |
| 11 | mutate `params.flat[:2] > 0.0` → `>= 0.0`, rerun the file | **10 failed**, including all four rate parametrizations — proves the rate test measures the claim rather than decorating it |
| 12 | `git checkout -- src/superconducted/integration/aer_factory.py` | `git status --short` prints nothing; suite returns to `0 failed` |
| 13 | smoke script, both placements | `consequent_seed=1` / `consequent_seed=0`, **identical to PR #34** — a changed seed means the refactor was not behavior-preserving |
| 14 | direct `n_rules` check | `27` (the ADR-010 gate, unchanged) |

Step 11 is the one that carries weight: a suite that passes proves nothing
unless it can fail, and the mutation is the one-character version of the bug
this PR exists to prevent.

The verification record lands at
`docs/evidence/pr44-adr-024-viability/`, per the path convention adopted
2026-08-24 — not the retired `docs/verification/` tree.

### Open, pending lead sign-off

ADR-024 is `Status: Open`. Clause 1 declines to modify `fuzzy/tsk.py`
(Burak's module) and clause 2 encodes `channels/kraus.py`'s parameter contract
from outside it (Bengisu's module), so both leads are asked to ratify or
object in the PR thread. This change adds no timing claims — only NC-023 and
NC-024, which are machine-independent — so the desktop run is a correctness
baseline rather than a performance one.

## Related docs

- ADR-024 in `docs/decisions.md` — the decision this implements
- ADR-010 (27-rule grid), ADR-012 (`ProbabilityClip` zero gradient),
  ADR-014 (the trainer ADR-024 clause 5 constrains)
- `docs/implementations/2026-08-20-issue-31-smoke-grid-27-rules.md` — PR #34,
  the local workaround this generalizes
- NC-021, NC-023, NC-024 in `docs/numerical-claims.md`
- Issue #35, Issue #31, PR #34
