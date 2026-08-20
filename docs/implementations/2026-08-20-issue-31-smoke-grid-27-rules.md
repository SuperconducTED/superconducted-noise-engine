# 2026-08-20: issue-31-smoke-grid-27-rules

## Problem / Motivation

Issue #31, raised by Bengisu. `scripts/first_ensemble_run.py` is the only
in-repo runtime construction of the baseline rule grid, and it did not
build the baseline. `_default_mfs_for_feature` returned **two**
`GaussianMF` objects per feature; `BasicCalibrationVectorizer` has three
features; `TSKRuleBase.from_grid` builds `prod_i K_i` rules. So the
script instantiated 2 x 2 x 2 = **8 rules** while `docs/architecture.md`
line 160 states 27 (3x3x3).

Rule count drives the consequent-parameter budget — each rule carries an
`(output_dim x (input_dim + 1))` matrix — so an 8-rule run exercised
under a third of the parameter surface of the ratified baseline. Anyone
running the script to see "what the baseline is" got the wrong answer.

The same helper had a second defect: its two centers sat at `lo` and
`lo + span/2`, leaving the upper half of every feature range with no
membership function. Long T1/T2 and high readout error — the calibration
states the noise model most needs to discriminate — fired nothing
appreciable.

**Ledger status at time of writing:** ADR-010 is still `Open` on `main`.
The Accepted text ratifying 3x3x3 lives on PR #30, unmerged. The 27-rule
target on `main` therefore rests on `docs/architecture.md` line 160, not
on the ADR entry. This change deliberately does not touch
`docs/decisions.md`, both because ADR-010 is being rewritten in PR #30
and because the fix stands on its own.

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/first_ensemble_run.py` | Three MFs per feature instead of two (27 rules); two selectable center layouts; feature scales and MF count promoted to module constants; deterministic consequent-seed search replaces the hard-coded `default_rng(0)`; `--mf-placement` CLI flag. |
| `scripts/compare_mf_placement.py` | New. Reports four deterministic metrics for each candidate layout and prints the decision rule for choosing between them. |
| `tests/test_first_ensemble_run.py` | Nine new tests: rule count is 27, upper range is covered, layouts differ, placement validation, seed-search determinism, selected seed is non-degenerate, comparison metrics reproducible. |
| `docs/architecture.md` | Line 160 now names the smoke script as the executable instance of the 27-rule grid. |

## Implementation approach

### Rule count

`_default_mfs_for_feature` returns `MFS_PER_FEATURE` (3) Gaussians per
feature, so `from_grid` yields `3^3 = 27`. The count is a named module
constant rather than an implicit consequence of list length, and a test
asserts `rule_base.n_rules == 27` directly on the object the script
builds — the guard that was missing when this regressed.

`src/superconducted/fuzzy/tsk.py` (LOCKED) is untouched. `from_grid`
takes `per_input_mfs` as an argument, so this is entirely a call-site
change and the two-owner lock procedure does not apply.

### Two center layouts, kept side by side

Issue #31 proposed centers at `lo`, `lo + span/2`, `hi`. An alternative
places them at the midpoints of equal thirds. Rather than pick blind,
both ship behind a `placement` argument and
`scripts/compare_mf_placement.py` measures them. Sigma is identical
(`span * 0.25`) in both, so the comparison isolates placement.

### Consequent-seed search

Fixing the grid surfaced a latent problem. The script hard-coded
`rng=np.random.default_rng(0)` with `consequent_init="random"`. Those
consequents are drawn from a zero-mean Gaussian, so the sign of the
defuzzified output is a property of the draw. Seed 0 happened to give a
positive output with 8 rules and gives a **negative** one with 27,
tripping the script's own degeneracy guard:

```
endpoint seed=0 n_rules=27 crisp[:2]=[-0.083063 -0.029921] -> ValueError
```

Across seeds 0-7 the guard trips 2 of 8 times for `endpoint` and 1 of 8
for `interior`. The old behavior was one lucky draw, not a property of
the design.

`generate_safe_ensemble_with_seed` now walks seeds `0, 1, 2, ...` and
returns the first non-degenerate ensemble, capped at
`CONSEQUENT_SEED_SEARCH_LIMIT` (64). The search is deterministic, so the
chosen seed reproduces on any machine, and it self-heals the next time
the grid or feature set changes. Exhausting the limit raises with a
message saying the degeneracy is structural rather than a bad draw.
`generate_safe_ensemble` keeps its original signature and return type;
the seed-reporting variant is separate so existing callers are unaffected.

Selected seeds on this build: `endpoint` -> **1**, `interior` -> **0**.

## Mathematical / Statistical details

### Rule count

`from_grid` appends one rule per element of `itertools.product(*per_input_mfs)`:

```
n_rules = prod_i K_i
```

With `K_i = 2` on three inputs: 8. With `K_i = 3`: 27. Each rule holds an
`(output_dim x (input_dim + 1))` = `(2 x 4)` consequent matrix, so the
parameter budget goes from `8 x 8 = 64` to `27 x 8 = 216` values.

### Layout comparison metrics

All four are computed on the normalized range `[0, 1]` with
`sigma = 0.25`. Because both layouts scale with `span`, the normalized
numbers apply unchanged to all three features.

Let `mu_j(x) = exp(-(x - c_j)^2 / (2 sigma^2))` for centers `c_j`, and let
`top1(x) >= top2(x)` be the two largest memberships at `x`.

- **`min_coverage`** = `min_x top1(x)`. The worst-covered input in the
  range. Low values mean a dead zone where no rule fires strongly.
- **`coverage_at_lo` / `coverage_at_hi`** = `top1(lo)`, `top1(hi)`. The
  extremes Issue #31 singles out.
- **`mean_separation`** = mean over `x` of `top1(x) - top2(x)`. How
  decisively one MF wins at a typical input. Higher means crisper
  single-rule selection; lower means several rules blend.

Grid: 20001 points, enough for the reported minima to be stable to about
`1e-6`. No RNG anywhere, so the output is bit-identical across machines.

Measured (provisional — laptop; see Verification):

| metric | endpoint | interior | winner |
| --- | --- | --- | --- |
| `n_rules` | 27 | 27 | tie |
| `min_coverage` | 0.606531 | 0.800737 | interior |
| `coverage_at_lo` | 1.000000 | 0.800737 | endpoint |
| `coverage_at_hi` | 1.000000 | 0.800737 | endpoint |
| `mean_separation` | 0.514978 | 0.440549 | endpoint |

The endpoint minimum is analytic: at `x = 0.25`, equidistant from centers
`0` and `0.5`, `mu = exp(-(0.25)^2 / (2 * 0.0625)) = exp(-0.5) = 0.606531`.
The interior minimum, `exp(-(1/6)^2 / (2 * 0.0625)) = exp(-2/9) = 0.800737`,
is attained both at the range ends and between adjacent centers, which is
what uniform spacing buys.

### What the numbers mean going forward

1. **Reject** any layout with `n_rules != 27`. ADR-010's baseline is not
   negotiable by coverage argument.
2. **Reject** any layout with `min_coverage < 0.5` — some input would fire
   no rule above half strength. Both candidates pass.
3. Among survivors the choice is a **stated trade-off, not a computed
   one**. `interior` wins uniform coverage; `endpoint` wins discrimination
   at the extremes, which is the concern that opened the issue. The
   script prints this rather than declaring a winner.
4. `mean_separation` is context, not a tiebreak. Neither direction is
   right without a stated goal.

`DEFAULT_MF_PLACEMENT` ships as `endpoint`, matching Issue #31's Option A.
Changing it is a one-line edit to that constant.

## Design decisions

- **Option A over Option B.** Bengisu offered adding a third MF (A) or
  keeping 8 rules and documenting the reduction (B). A fixes both defects
  at once and needs no ledger edit. B would have required editing ADR-010,
  which PR #30 is actively rewriting, and would still have left the
  upper-range gap.
- **Both layouts shipped rather than one chosen.** The trade-off is real
  and the metrics split 1-3, so committing silently to either would have
  buried a judgement call in a bug fix.
- **Deterministic seed search over bumping the seed.** Changing `0` to `4`
  would have worked today and re-rolled the same dice at the next grid
  change. The search removes the failure mode rather than stepping around
  it.
- **No `docs/decisions.md` edit.** ADR-010 is mid-rewrite in PR #30 and
  `architecture.md` already carries the 27-rule statement on `main`.
- **Branched from `main`, not stacked.** This touches `scripts/`,
  `tests/`, and `architecture.md` only — no overlap with PR #30 (docs),
  #32, or #33 — so it merges in any order.

## Verification

```
python -m pytest tests/test_first_ensemble_run.py -q   # 18 passed
python -m pytest tests/ -q                             # 163 passed
python -m ruff check .                                 # All checks passed
python -m ruff format --check .                        # 35 files already formatted
python -m mypy --strict src/superconducted             # no issues in 22 source files
python -m scripts.compare_mf_placement                 # metrics table above
```

Regression evidence: before this change no test asserted rule count, so
the 8-versus-27 mismatch was invisible to CI. `test_grid_builds_27_rules`
now asserts it for both layouts.

**All numbers above are provisional — produced on Mert's laptop.** Per the
advisor's requirement they are authoritative only once re-run on Burak's
desktop. The full step-by-step runbook is posted as a comment on the PR,
and the comparison metrics are pure arithmetic with no RNG, so his run
should reproduce them exactly; any divergence is an environment problem,
not hardware variation.

## Related docs

- Issue #31 (raised by Bengisu, found while confirming ADR-010 for #24)
- ADR-010 in `docs/decisions.md`; PR #30 (its acceptance, unmerged)
- `docs/architecture.md` line 160
- `docs/audits/2026-05-25-followup-issues.md` item 9
- `src/superconducted/fuzzy/tsk.py` `from_grid` (LOCKED — read only)
