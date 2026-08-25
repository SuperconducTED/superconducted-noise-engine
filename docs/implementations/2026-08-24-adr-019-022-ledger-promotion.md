# 2026-08-24: Promote ADR-019 through ADR-022 into the ledger

## Problem / Motivation

`docs/decisions.md` held entries for ADR-001 through ADR-018 only. ADR-019,
ADR-020, ADR-021 and ADR-022 existed solely as standalone files under
`docs/decisions/drafts/`, yet the rest of the repository already cited them as
though they were ratified decisions:

- `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md` assigns all
  four a status in its `ADR Cycle Summary` table — ADR-020 and ADR-022 as
  `Accepted` — none of which the ledger recorded.
- Four rows in `docs/numerical-claims.md` (NC-006, NC-018, NC-019, NC-020)
  source their values to the draft files.
- `docs/decisions.md` itself leans on ADR-019: ADR-006 hands empirical-winner
  selection to it, and ADR-009 calls its own direction "provisional pending the
  ADR-019 MF-shape ablation".

So the project treated ADR-020 and ADR-022 as settled while the ledger — which
its own header designates as the record, with `Accepted` meaning "locked, do not
revisit" — had never recorded them. That is the drift the ledger exists to
prevent. Closes issue #37.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions.md` | Append ADR-019, ADR-020, ADR-021 and ADR-022 entries, and extend the header to define split statuses and to state that the ledger is canonical over `drafts/`. |
| `docs/implementations/2026-08-24-adr-019-022-ledger-promotion.md` | This record. |

No source files, tests, or draft files were modified.

## Implementation approach

Each promoted entry is a **character-identical copy** of its draft body, with
only the top-level `#` heading demoted to `##` to match the ledger's structure,
followed by a one-line note recording the promotion and naming the draft it came
from. The copies were produced by script rather than by hand so that no wording
could drift during transcription:

```
for n in 019 020 021 022; do
  draft=$(ls docs/decisions/drafts/ADR-$n-*.md)
  { printf '\n---\n\n'; sed '1s/^# /## /' "$draft"; printf '<promotion note>'; } \
    >> docs/decisions.md
done
```

Statuses carried over from the drafts unchanged:

| ADR | Status | Basis |
| --- | --- | --- |
| ADR-019 | Open | Ablation protocol is written but unrun; prerequisite (b), non-trivial MF parameters, is still pending. |
| ADR-020 | Accepted | Implemented and operational — PRs #7, #8, #17; the `calibration-data` orphan branch has been accumulating snapshots since bootstrap. |
| ADR-021 | Accepted on the constraint · Open on variance-injection design | The Aer no-per-shot-hook constraint and the DI contract are settled; the per-member variance mechanism waits on ADR-009 and ADR-014. |
| ADR-022 | Accepted | Implemented — PR #10, 15 property tests in `tests/test_metrics.py`. |

## Mathematical / Statistical details

N/A — purely structural. This change relocates decision records; it introduces
no formula, statistical test, or numeric algorithm. The ablation protocol
recorded in ADR-019 (fixed suite of four circuits, 4096 shots, ensemble N = 8,
Hellinger primary / fidelity secondary) is carried across verbatim and is not
altered here.

## Design decisions

**Promote all four rather than de-status any.** Issue #37 offered two exits:
promote, or stop assigning statuses. Promotion is right for all four because
each is already load-bearing — ADR-020 and ADR-022 describe shipped, operational
behavior, and ADR-019 is cited by two ledger entries as the gate on their own
open questions. De-statusing would have meant editing the ledger to remove
references to a decision the team demonstrably relies on.

**Verbatim copy over condensed summary.** ADR-017 set the precedent: its ledger
entry is character-for-character identical to its draft. A condensed entry would
create two texts that can disagree, which is the failure mode this ticket exists
to close.

**Drafts retained in place, unmarked.** Also the ADR-017 / ADR-018 precedent —
the draft files stay as the authoring record. Rather than editing six draft
files to point at the ledger, the canonicity rule is stated once in the ledger
header and once per promoted entry. Deleting the drafts was rejected: they carry
authorship and review history, and `docs/numerical-claims.md` cites four of them
as sources.

**ADR-021 keeps its split status.** Its two halves genuinely differ in maturity,
and `Accepted` in this ledger means "locked, do not revisit" — which would be
false for the variance-injection half that explicitly defers to ADR-009 and
ADR-014. Rather than flatten it to one word, the header now defines split
statuses, so the ledger's legend matches its contents. ADR-011 already carried a
qualified status (`Open (effectively chosen for each path)`), so this formalizes
existing practice rather than inventing a convention.

**`docs/architecture.md` deliberately untouched.** Its ADR table maps *swappable
axes* to ABCs and covers ADR-006 through ADR-016 only; ADR-017 and ADR-018 are
absent from it too. ADR-019 (methodology), ADR-020 (storage), ADR-021
(integration contract) and ADR-022 (validation criteria) are not swappable axes,
so adding rows would misrepresent what that table is.

**`docs/numerical-claims.md` deliberately untouched.** Issue #37 asks that
NC-006, NC-018, NC-019 and NC-020 be re-pointed *if their draft files move or
are superseded*. The drafts do neither, and the promoted ledger text is
identical, so both citations resolve to the same words. Re-pointing would be
churn against a register whose whole purpose is stable provenance.

## Verification

Documentation-only; no Python changed, so `ruff`, `mypy --strict` and `pytest`
are unaffected and CI covers them.

- Gate for issue #37 — every ADR ID referenced anywhere in the repository has a
  ledger entry. Prints nothing when the gate passes:

  ```
  comm -23 \
    <(grep -rhoE "ADR-[0-9]{3}" --include=*.md --include=*.py . | sort -u) \
    <(grep -oE "^## ADR-[0-9]{3}" docs/decisions.md | grep -oE "ADR-[0-9]{3}" | sort -u)
  ```

- The ledger now carries all 22 IDs:

  ```
  grep -oE "^## ADR-[0-9]{3}" docs/decisions.md | wc -l    # 22
  ```

- Each promoted entry is verbatim against its draft — compare body text ignoring
  the heading level and the trailing promotion note:

  ```
  sed -n '/^## ADR-020 /,/^> Promoted from draft/p' docs/decisions.md
  cat docs/decisions/drafts/ADR-020-calibration-snapshot-schema-and-storage.md
  ```

- Statuses landed as intended:

  ```
  grep -A2 -E "^## ADR-(019|020|021|022) " docs/decisions.md | grep "Status"
  ```

## Related docs

- `docs/decisions.md` — the ledger, now canonical for all 22 ADRs
- `docs/decisions/drafts/` — retained authoring records
- Issue #37 (this change) · issue #25 (the broader post-merge hygiene sweep)
- PR #29 (ADR-012 closure), which surfaced the gap

## Known follow-ups, deliberately not done here

- **The cycle-1 snapshot table still shows the pre-promotion statuses.** Its
  reconciliation belongs in the `Ledger reconciliation · as-of 2026-08-19`
  section that PR #29 adds to
  `docs/state-of-the-project/2026-05-25-bootstrap-to-cycle-1.md`. That section
  does not exist on `main` yet, so appending to it here would collide with an
  open PR. Sequence this after PR #29 merges.
- **No code comments reference ADR-019 through ADR-022.** The ledger header asks
  that decisions be referenced from relevant code; ADR-021 in particular
  documents the contract implemented by
  `src/superconducted/integration/aer_factory.py`. Adding those docstring
  references would put Python in a documentation PR and touch an owned module,
  so it is left for a separate change.
