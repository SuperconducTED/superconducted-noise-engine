# 2026-08-24: Reference ADR-021 (and ADR-002) from `aer_factory`

## Problem / Motivation

`docs/decisions.md` opens by asking that decisions be "referenced from the
relevant code via comments." Several modules do this — `fuzzification.py` cites
ADR-007, `loader.py` and `features.py` cite ADR-017, `kraus.py` cites ADR-008,
`harness.py` cites ADR-016.

`src/superconducted/integration/aer_factory.py` was the conspicuous exception.
Its module docstring *states* the Aer no-per-shot-hook invariant and *describes*
the injected-dependency pipeline and the `prepare()` contract — which is exactly
the content of ADR-002 and ADR-021 — while citing neither. The only ADR named in
the file was ADR-015, for deferred per-member sampling.

The practical cost: a reader who wanted the reasoning behind the strict DI
surface, or the rules governing `prepare()`, had no pointer from the code to the
decision that fixed them. This was flagged as a known follow-up in
`docs/implementations/2026-08-24-adr-019-022-ledger-promotion.md` and is now
done.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/integration/aer_factory.py` | Add ADR-002 and ADR-021 references to the module, class, `prepare()`, and ensemble docstrings, and document the `circuit.copy()` caller contract. |
| `docs/implementations/2026-08-24-adr-021-code-reference.md` | This record. |

**Docstrings only — no executable line changed.** No signature, no type hint, no
control flow, no test.

## Implementation approach

Four references were added, each placed where the docstring already stated the
corresponding decision rather than appended as a bare "see ADR-021" note:

1. **Module docstring** — the `ARCHITECTURAL INVARIANT` paragraph now names
   ADR-002 as the source of the invariant and the Factory/Ensemble response,
   including its "rejected on sight" clause, and names ADR-021 as the extension
   that fixes the DI contract.
2. **`FuzzyNoiseModel` class docstring** — cites ADR-021 for the six-dependency
   construction contract and records *why* the strict DI surface is deliberate
   (independent testability of each research axis, at the cost of non-trivial
   construction).
3. **`FuzzyNoiseModel.prepare`** — cites ADR-021 and spells out the two contract
   clauses that were previously implicit: idempotency, and caller-side circuit
   isolation.
4. **`FuzzyNoiseModelEnsemble` class docstring** — cites ADR-021 for the three
   variance plug-in points, and notes the choice among them additionally depends
   on ADR-009 and ADR-014, not ADR-015 alone.

## Mathematical / Statistical details

N/A — purely structural. Documentation-only change to docstrings; no formula,
statistical test, or numeric algorithm is introduced or altered.

## Design decisions

**The `circuit.copy()` contract is documented as forward-looking, not as a live
hazard.** ADR-021 states callers "MUST pass `circuit.copy()` to maintain
ensemble-member isolation." Read literally into today's code that would
overstate the risk, so the wording was checked against the implementation
before being written down:

- `PostGateFuzzification.install` (`fuzzy/fuzzification.py:56`) ends with
  `return circuit, noise_model`. It iterates `circuit.data` read-only and
  returns the *same object*, unmutated.
- `PreGateFuzzification.install` and `BetweenGatesFuzzification.install` — the
  two strategies that would transform the circuit — both raise
  `NotImplementedError` pending ADR-007.

So under the only implemented strategy there is currently no mutation and no
cross-member contamination. The docstring therefore says copying is required to
keep callers correct *when the pre/between strategies land*, and states plainly
that it is not a live hazard today. Documenting it as a present-tense bug would
have been wrong, and would likely have triggered someone to "fix" a
non-existent defect.

**References were placed at the decision they explain, not collected in a
footer.** This matches how `fuzzification.py` and `loader.py` cite their ADRs —
inline, at the sentence stating the decision — so a reader hits the pointer
exactly where the question occurs to them.

**ADR-002 was added alongside ADR-021.** ADR-021 explicitly extends ADR-002
rather than replacing it, and ADR-002 is the entry carrying the "rejected on
sight" prohibition that the module's invariant paragraph is enforcing. Citing
only ADR-021 would have hidden the locked constraint behind its extension.

**This branch is stacked on `mert/ledger-entry`, not on `main`.** ADR-021 does
not exist in `docs/decisions.md` on `main` — it lives only in
`docs/decisions/drafts/` until PR #38 merges. The ledger header rule that PR #38
introduces says an ID appearing only in `drafts/` "must not be cited elsewhere
as though it carried a status." Branching from `main` and citing ADR-021 from
code would have violated that rule in the same breath as introducing it.

## Verification

All four CI gates were run locally on this branch. No Python behavior changed,
so the expected result is that every gate matches `main` exactly:

```
python -m ruff check .                    # All checks passed!
python -m ruff format --check .           # 34 files already formatted
python -m mypy --strict src/superconducted  # Success: no issues found in 22 source files
python -m pytest tests/ -q                # 149 passed
```

Observed: all four as shown above. The test count matches `NC-021` (149) in
`docs/numerical-claims.md`, which is the registered, sourced value — this change
adds and removes no tests, so any other count would be a finding.

Local runs were on Python 3.13; CI covers the supported 3.11 and 3.12 matrix.

To confirm the references landed:

```
grep -n "ADR-0" src/superconducted/integration/aer_factory.py
```

## Related docs

- ADR-002 and ADR-021 in `docs/decisions.md`
- `docs/decisions/drafts/ADR-021-aer-integration-constraint-and-factory-ensemble.md`
- `docs/findings/aer-integration-walkthrough.md` — PR #13 findings that ADR-021 records
- `docs/implementations/2026-08-24-adr-019-022-ledger-promotion.md` — flagged this as a follow-up
- Issue #37 · PR #38 (ledger promotion, this branch's base)
