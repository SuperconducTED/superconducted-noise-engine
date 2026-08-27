# 2026-08-26: issues-40-41-ledger-label-and-stale-claim

## Problem / Motivation

Re-verifying PR #29 after a `NOT VERIFIED` desktop report surfaced two defects
that were not in the PR under review, and one of them was being actively
concealed by a check that passed.

**Issue #41 — locked entries carrying provisional wording.** `docs/decisions.md:8`
defines `Accepted` as "locked, do not revisit". ADR-006 and ADR-010 were marked
`Accepted` while their decision text was still labelled `**Decision (current)**`,
the provisional form reserved for `Open` and `Deferred` entries. This is the same
defect PR #29 fixes for ADR-012; it had already been repeated twice.

**Issue #40 — a stale claim that produced a false regression report.**
`docs/numerical-claims.md` registered NC-021 (full test-suite size) as `149`,
measured at `981f324`. PR #33 (`768cd86`) and PR #34 (`07fd9ec`) added 17 tests
between them and neither updated the register. The PR #29 verification runbook
then pinned one row to NC-021's absolute `149` while requiring another row to
match `main`. Once `main` reached 166 those two expectations became mutually
unsatisfiable, and a correct verification run reported a regression that did not
exist.

The register exists precisely to prevent unsourced numbers — it was created after
a fabricated benchmark figure propagated across four documents. NC-021 failed in
the adjacent mode: the number was sourced, but the source rotted and nothing
required the PRs that moved it to say so.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | ADR-006 and ADR-010 decision labels normalized to `**Decision**`, each with an `Editorial` note recording that the decision text is unchanged. |
| `docs/numerical-claims.md` | NC-021 corrected `149` → `166` and re-sourced; NC-022's note updated for the now-closed issue #37; new Rule 6 requires repo-measured claims to be updated by the PR that moves them. |
| `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` | New `as-of 2026-08-26` section appended, superseding the claim that ADR-019–022 have no ledger entry. |
| `docs/implementations/2026-08-26-issues-40-41-ledger-label-and-stale-claim.md` | This document. |

No `.py` files were touched. The PR remains documentation-only.

## Implementation approach

**#41** is a label-only edit. Both decision texts were already normative — ADR-006
("Bootstrap ships the T1 shapes …") and ADR-010 ("The baseline rule grid is 3×3×3
…") assert rather than hedge — so the fix changes the label and nothing else. The
replacement is scoped per ADR section rather than applied file-wide, because the
same string legitimately appears in nine `Open`/`Deferred` entries.

Each edited entry gains a note in the ledger's existing blockquote style:

```
> Editorial · 2026-08-26 · The decision label here was normalized to
> **Decision** …  The decision text itself is unchanged — this records
> the label fix only, not a revisit. See issue #41.
```

The note deliberately avoids containing the literal string `Decision (current)`.
A first attempt quoted the old label verbatim, which left the file's occurrence
count unchanged at 11 and would have defeated the invariant check below. The
count now falls 11 → 9, and all nine survivors are `Open` or `Deferred`.

`Editorial` is a new note verb, chosen over the existing `Revisited`/`Ratified`.
Labelling a locked entry "Revisited" would assert the very thing the status
forbids; the change is editorial, and the note says so.

**#40** corrects the NC-021 row (value, source command, source commit, date) and
adds Rule 6 to the register, which makes the maintenance obligation explicit:
a claim sourced from a command run against this repository is invalidated by any
PR that changes what the command returns, and that PR updates the row in the same
commit. Rule 3 already implied this; it is restated because two PRs passed review
without anyone noticing the obligation.

## Mathematical / Statistical details

N/A — purely structural. The one number that changed is a measured count, not a
derived quantity: `python -m pytest tests/ --collect-only -q -o addopts=""`
reports 166 on `main` at `1873625` and on this branch. The `-o addopts=""`
override is needed because the project sets `addopts = "-v"`, which otherwise
renders the collection tree instead of the compact summary.

The delta decomposes exactly, and is purely additive — no test was removed:

| Source | File | Before → after |
| --- | --- | --- |
| `768cd86` (PR #33) | `tests/test_membership.py` | 34 → 37 |
| `07fd9ec` (PR #34) | `tests/test_first_ensemble_run.py` | 4 → 18 |

149 + 3 + 14 = 166.

## Design decisions

**The optional CI guard from issue #41 was deliberately not implemented here.**
Issue #41 proposes a check asserting that no `Accepted` entry contains
`Decision (current)`. That check is worth having, but adding it to this PR would
convert a documentation-only change into a code change — bringing `ruff`, `mypy`,
and test-count obligations with it, and destroying the "zero `.py` files"
property that makes this PR cheap to verify by differential comparison against
`main`. The invariant is instead asserted inline in the verification runbook,
which gets the coverage without the coupling. The guard remains open in #41 as
follow-up work.

**The dated snapshot was reconciled by appending, not editing.** Merging `main`
falsified a statement in the existing `as-of 2026-08-19` section — ADR-019
through ADR-022 are now ledger-backed via `d7ee18b`. Per the dated-document
convention (issue #25), the original section is left untouched and a second
`as-of 2026-08-26` section records the change. This keeps the `removed`-lines
count on that file at zero, which the runbook checks directly.

**NC-022 was refined rather than restated.** Its value (drift = 4) is pinned to
`dfee09c` and remains true at that commit, so the value is unchanged; only the
note's reference to the then-open issue #37 was updated. Restating a pinned
historical measurement for a later commit would break the same convention.

## Verification

```
# #41 — invariant: no Accepted entry carries provisional wording
python - <<'PY'
import re
txt = open('docs/decisions.md', encoding='utf-8').read()
parts = re.split(r'^## (ADR-\d+)[^\n]*$', txt, flags=re.M)
bad = [parts[i] for i in range(1, len(parts), 2)
       if 'Decision (current)' in parts[i+1]
       and re.search(r'\*\*Status\*\*:\s*Accepted', parts[i+1])]
print('Accepted AND provisional:', bad)   # must be []
PY

# #40 — the register matches reality
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1   # 166
grep -n '^| NC-021' docs/numerical-claims.md                        # 166

# append-only invariant on the dated snapshot (removed column must be 0)
git diff --numstat main -- docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md

# unchanged code gates — must match main exactly
ruff check . && ruff format --check . && mypy --strict src/superconducted
python -m pytest tests/ -q
```

## Related docs

- ADR-006, ADR-010, ADR-012 in `docs/decisions.md`
- `docs/numerical-claims.md` — NC-021, NC-022, Rule 6
- Issues #40, #41 · closed issue #37 · open issue #25 (Phase 0 Hygiene Sweep)
- PR #29 and its desktop verification thread
- `docs/implementations/2026-08-19-adr-012-closure.md`
