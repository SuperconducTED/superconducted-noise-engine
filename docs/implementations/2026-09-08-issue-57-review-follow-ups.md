# 2026-09-08: Issue #57 review follow-ups

## Problem / Motivation

The remaining non-blocking findings from the PR #69 approval review, all of
them gaps against Issue #57's own text rather than defects in shipped
behaviour:

- **ADR-027 was missing three FR-1 items**: the snapshot-boundary split rule
  with its NC-028 precedent, the explicit "Not the target" list, and the
  ADR-024 clause 5 citation.
- **The §9.2 immutability round trip was absent.** The ticket calls it "the
  template #60's real trainer test reuses", so its absence would have landed
  on the next ticket rather than this one.
- **The §9.1 unshared-membership case was absent** from
  `count_trainable_parameters` coverage — the case that distinguishes
  dedup-by-`id()` from a references-divided-by-rule-count shortcut.
- **`superconducted/__init__.py` had drifted.** Its docstring still claimed
  "nine ABCs" and "four frozen-dataclass value types" (now ten and eight), and
  `TSKTrainer` was the only one of the ten ABCs not re-exported from the
  package root — the earlier diff added the four value types to the import and
  `__all__` but left the interfaces block untouched.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | ADR-027 gains the snapshot-boundary split rule with NC-028, the "Not the target" list naming (B) and (C) as evaluation references, and an ADR-024 clause 5 citation in Source. |
| `src/superconducted/__init__.py` | Docstring counts corrected to ten ABCs and eight value types; `TSKTrainer` re-exported alongside the other nine. |
| `tests/test_interfaces.py` | Adds the §9.2 immutability round trip, a runtime-narrowing test for the `isinstance` rule, and a pin on the docstring's two counts. |
| `tests/training/test_parameters.py` | Adds the hand-built two-rule base with four distinct `GaussianMF`, asserting `premise == 8`. |
| `docs/numerical-claims.md` | NC-021 updated in place, 356 → 360. |

## Implementation approach

The ADR additions go in the ledger entry only, not in
`docs/decisions/drafts/ADR-027-...`. The ledger is canonical by its own stated
convention, and the draft is the authoring record of what was originally
written; ADR-018 already demonstrates the two drifting in wording while
describing one decision.

The round-trip test builds a `TSKRuleBase` through `from_grid`, snapshots every
`consequent_params` and `mf.parameters()` as copies, runs a minimal conforming
`TSKTrainer`, and compares **by value** with `np.array_equal`. Identity is
deliberately not the assertion: `TSKRule.consequent_params` returns the live
internal array and `from_grid` shares one MF object across every rule naming
it, so a mutating trainer leaves the same objects in place while changing what
they hold — an identity check would pass.

## Mathematical / Statistical details

N/A — purely structural. Two counting claims appear and were measured, not
quoted: a hand-built two-rule base over two inputs with four distinct
`GaussianMF` yields `premise == 8`, `consequent == 6`, `total == 14`; and the
exported surface is ten ABCs and eight frozen-dataclass value types.

## Design decisions

**Why the split rule cites NC-028 rather than restating a rule.** NC-028's
−0.585 R² was measured across a 20-day time split, and re-running it showed a
cut placed *inside* a snapshot is sensitive to that snapshot's row order, while
a cut *between* snapshots cannot be moved by any ordering. The ADR therefore
records the boundary rule together with the evidence for why it exists, rather
than as a bare convention a later reader might optimise away.

**Why the count pin was added rather than just fixing the numbers.** The
docstring said "nine ABCs" and "four value types" and had been wrong since
`TSKTrainer` and the training types landed — nothing detected it. Correcting
the prose without pinning it would leave the same silent-drift mechanism in
place for the next ABC. `test_package_docstring_counts_match_the_exported_surface`
now fails when the surface and the prose disagree.

**Why the round-trip test was verified against a mutating trainer.** A test
that cannot fail is worse than no test. Both mutation paths were exercised
before the test was accepted: writing through `consequent_params[...]` and
calling `set_parameters` on a shared MF each make the assertions fire. This
follows the same discipline that caught an earlier equality test which asserted
`value == value` and passed against broken code because tuple comparison
short-circuits on identity.

**Why `TSKTrainer` is now exported.** There was no evidence of a deliberate
choice to withhold it — the interfaces import block was simply not touched when
the value types were added. Exporting it makes the package root consistent with
its own docstring, which describes the ABCs as the package's public surface.

## Verification

```bash
ruff check . && ruff format --check .     # clean
mypy --strict                             # no issues in 32 source files
python scripts/check_ids.py               # no colliding identifiers
pytest tests/ -q                          # 360 passed
```

Test count moved 356 → 360 (three in `tests/test_interfaces.py`, one in
`tests/training/test_parameters.py`). NC-021 updated in place in the same
change, per register Rule 6.

The round-trip assertions were confirmed to fail against a deliberately
mutating trainer:

```
writes through consequent_params     -> test would FAIL: True
set_parameters on a shared MF        -> test would FAIL: True
```

## Related docs

- Issue #57 FR-1 (ADR contents), FR-8 (`count_trainable_parameters`), §9.1 and
  §9.2 (the two test tables)
- ADR-027 in `docs/decisions.md`; ADR-024 clause 5; NC-028
- `docs/implementations/2026-09-08-tsk-trainer-contract-docstring.md` — the
  other half of this review round
