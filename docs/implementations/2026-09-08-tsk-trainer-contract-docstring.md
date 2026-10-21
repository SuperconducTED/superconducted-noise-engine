# 2026-09-08: `TSKTrainer` contract in its docstring

## Problem / Motivation

Issue #57 FR-2 requires the `TSKTrainer` ABC to carry its full contract in its
docstring, and the ticket's definition of done names it explicitly: "`TSKTrainer`
in `interfaces.py` **with the immutability and finiteness contract in its
docstring**". The shipped docstring stated the non-mutation obligation in two
sentences but omitted the parts that make it actionable: the `isinstance` /
`TypeError` rule, the three concrete aliasing hazards in the LOCKED
`fuzzy/tsk.py` that make invariant (a) the *trainer's* job rather than the rule
base's, and the ADR-024 clause 5 warm-start obligation.

This matters more after PR #69's review than before it. The `HybridANFISTrainer`
implementation was removed from that PR as Issue #60 work, so this docstring is
now the **only** place in the repository where the obligation is recorded. An
implementer reading it before this change would not learn that
`rule.consequent_params` returns the live internal array.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/interfaces.py` | `TSKTrainer` docstring now states inputs, output, side effects, invariants (a)–(c), the three aliasing hazards with the mitigations they imply, and the warm-start rule. |
| `docs/implementations/2026-09-08-tsk-trainer-contract-docstring.md` | This record. |

No behaviour changes: the ABC's signature, module imports and every other
symbol are untouched, so the test count is unchanged at 356.

## Implementation approach

The docstring is organised as FR-2 specifies — *Inputs*, *Output*, *Side
effects*, *Invariants*, then the justification for invariant (a), then *Warm
start*.

The annotation stays `RuleBase` rather than `TSKRuleBase` because `fuzzy/tsk.py`
imports `interfaces.py`; the reverse import would be circular. That is why the
type narrowing has to happen at runtime in each implementation, and the
docstring now says so rather than leaving a reader to infer it from the
signature.

## Mathematical / Statistical details

N/A — purely structural. One counting claim appears in the prose and was
measured rather than quoted: a 3×3×3 Gaussian grid built through
`TSKRuleBase.from_grid` yields 27 rules and 81 antecedent references over 9
distinct `MembershipFunction` objects.

## Design decisions

**Why the three hazards are named concretely rather than summarised.** The
previous wording ("must not mutate caller-owned consequent arrays or
membership-function parameter arrays") is correct but not falsifiable by a
reader — it does not say *how* a well-intentioned implementation would mutate
them by accident. All three mechanisms were re-verified against the LOCKED
module on 2026-09-08 before being written down:

- `rb.rules[0].consequent_params[0, -1] = 42.0` changed `consequent()` output
  from `[0. 0.]` to `[42. 0.]`, so the property returns the live array.
- `TSKRule(mfs, arr)` followed by `arr[0, 0] = 7.0` left
  `rule.consequent_params[0, 0] == 7.0`, so `__init__` aliases the caller's
  float64 array rather than copying.
- The 27 / 81 / 9 counts above show `from_grid` sharing objects across rules,
  which `set_parameters` then mutates in place.

**Why the warm-start clause carries an escape.** ADR-024 clause 5 offers exactly
two mechanisms — `first_viable_seed`, or an everywhere-nonzero-gradient
squashing strategy with its own viability predicate. Issue #59's anchored
consequents take neither: they are evaluated at each rule's centre and are not
drawn at all, so they satisfy the clause's intent while falling outside its
letter. Writing the clause as a hard two-way choice would make a correct design
look non-compliant, so the docstring requires satisfying clause 5 **or**
recording the mechanism used instead. The obligation to document is retained;
the false dichotomy is not.

**Why no test was added here.** The §9.2 immutability round-trip — build via
`from_grid`, copy every `consequent_params` and `mf.parameters()`, run a stub
trainer, assert `np.array_equal` — is a separate outstanding item from the PR
#69 review and is tracked there. A docstring change alone does not warrant one,
and the round-trip belongs with the stub-trainer test in
`tests/test_interfaces.py` rather than here.

## Verification

```bash
ruff check . && ruff format --check .     # clean
mypy --strict                             # no issues in 32 source files
python scripts/check_ids.py               # no colliding identifiers
pytest tests/ -q                          # 356 passed, unchanged
```

Contract completeness was checked directly against the loaded class rather than
by eye:

```python
d = TSKTrainer.__doc__
all(k in d for k in ["isinstance", "TypeError", "deepcopy", "freshly allocated",
                     "never write through", "ADR-024 clause 5", "first_viable_seed"])
```

Issue #57 §9.3 also requires `MembershipFunction.__doc__` to no longer name
`superconducted.fuzzy.tsk`; re-confirmed True.

## Related docs

- Issue #57 FR-2 (the contract), §9.3 (the docstring conformance check), and the
  definition-of-done line this closes
- ADR-024 clause 5 in `docs/decisions.md` — the warm-start obligation
- ADR-012 — `SigmoidSquashing`, the everywhere-nonzero-gradient alternative
- ADR-014 — Deferred; the trainer that will implement this contract is Issue #60
- `docs/implementations/2026-09-05-issue-57-training-target-contract.md`
