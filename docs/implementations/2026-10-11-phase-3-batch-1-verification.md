# 2026-10-11: phase-3-batch-1-verification

## Problem / Motivation

Architect decision C2 and the `docs/team.md` rule "Verification is batched on
Burak's desktop" make a number canonical only once it appears in a batch record
from @BurakOztekin's desktop. Four register rows (NC-044 to NC-047) were waiting
on the first phase-3 batch, and Issue #59's step-9 acceptance run had been handed
to the same session. Issue #100 tracked that session. PR #106 lands its record
and promotes the four rows.

This document covers the whole PR: Burak's record and register edits, and the
review fixes added on 2026-10-11 so the PR could be approved without another
round trip.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/verification/2026-10-01-phase-3-batch-1-burak-desktop.md` | New canonical batch-1 record: machine, pinned gates and suite at `110cfad`, the four claim measurements, the #59 acceptance run, the 24 covered PRs and the NC-052/NC-055 deferral. |
| `docs/numerical-claims.md` | NC-044 to NC-047 lose their provisional marks and gain an appended batch-1 clause citing the record; NC-055 records its deferral to batch 2. |
| `docs/evidence/feature-distribution/README.md` | The Runtime paragraph now gives the canonical desktop figure and keeps the laptop range as history. |
| `docs/implementations/2026-09-15-pr68-m2-mapping-and-coverage.md` | Appended an as-of line naming the batch record its placeholder pointed to. |
| `docs/implementations/2026-10-11-phase-3-batch-1-verification.md` | This document. |

## Implementation approach

The record follows the shape of the earlier desktop records: measured commit
first, a Machine table, a gates table, a claims table, reproduction commands and
scope. The gates ran in a fresh clone at `110cfad` with dependencies installed
exactly as CI installs them (`requirements.txt` and `requirements-dev.txt`, then
`pip install -e . --no-deps`), and the installed versions were checked against
the pins.

The register edits are append-only, as the register's history convention and the
2026-10-06 review required. Each promoted row starts from `main`'s text, drops
only the words that marked it provisional, adds the canonical re-run to Source,
moves `Last verified` to 2026-10-01, and appends one clause of the form
"**Canonical, batch 1 (2026-10-01):** reproduced at `main` @ `110cfad` on
`DESKTOP-2CST637`, `<record path>`: <result>".

The 2026-10-11 review fixes, one per finding:

| Finding | Fix |
| --- | --- |
| Covered-PRs list said 21 and omitted #51, #52, #71 | The record lists all 24 and states the counting rule. |
| NC-045, NC-046, NC-047 clauses lacked the record path (Issue #100 done-criterion 2) | Path added to each clause. |
| NC-044 Source still described three laptop runs | Source now names the one canonical run and the record; the laptop runs stay in Notes. |
| NC-044 Value did not say which figure was `runtime_seconds` | Value labels both figures. |
| NC-055 compared itself to NC-044 "as NC-044 is" | Reworded to the batch-1 and batch-2 records. |
| Evidence README still said 55-64 s, provisional | Updated in place; it is an undated reference doc. |
| Double spaces left in NC-045 and NC-046 Notes | Removed. |
| Record had no trailing newline | Added. |
| Reproduction ran pytest without `-p no:cacheprovider` | Flag added, matching the gates as run. |
| "2026-09-05 batch record" | Renamed to the Issue #57 record, which is the per-PR shape. |
| PR #68 doc pointed at the `batch-N` placeholder | As-of line appended; the doc is dated, so it is not edited in place. |
| No implementation doc | This document. |

The review edits that Burak made inside merge commit `3f8f1ee` are left as they
are. Rewriting a pushed branch to split them out would cost more than it returns,
and the net diff against `main` is unaffected.

## Mathematical / Statistical details

**NC-045, training floor.** With $k = 2$ outputs, $R = 27$ rules and $d = 3$
inputs, the linear consequents carry $k R (d + 1) = 2 \times 27 \times 4 = 216$
parameters. `from_grid` shares $U = 9$ membership-function objects, each with
$p = 2$ parameters for `GaussianMF`, so the premise term is $U p = 18$. The total
is $216 + 18 = 234$, and NC-012's rule of five samples per parameter gives a
floor of $5 \times 234 = 1170$ distinct device states.

**NC-046, per-shape totals.** Only $p$ changes with shape: $p = 2$ gives 234
(floor 1170), $p = 3$ gives 243 (floor 1215), $p = 4$ gives 252 (floor 1260).

**NC-047, duplication.** With $N = 994$ documents and $S = 563$ distinct
`qubit_digest` states at `c63ce21`, the duplication ratio is
$(N - S) / N = 431 / 994 = 43.36016096579477\%$. The gap to the floor is
$1170 - 563 = 607$ states.

**NC-044 byte identity.** The regenerated survey TSV differs from the committed
one in 733 of 975 rows, only in `mean_T1` or `mean_T2`, with a maximum relative
difference of $4.33 \times 10^{-16}$, a few units in the last place of a float64.
NC-054 already registers this drift from Issue #66's change of computation order.
Burak, as the #100 owner, accepted reproduction at registered precision on
2026-10-04, and the 2026-10-06 review agreed.

**NC-044 runtime** is a single uncontended run, not a range. It is a timing on
one machine and carries no confidence interval.

## Design decisions

- **Fix on the author's branch, not in a follow-up PR.** Every finding was a
  documentation edit with no judgment left to the author, so a fast-forward on
  top of Burak's tip closes the review in one step and keeps his commits intact.
- **24 PRs, not 21.** `docs/team.md` says a batch covers every PR merged since the
  previous batch. #51 and #52 merged into `main` on 2026-09-06 and are inside
  `110cfad`. #71 merged into the Issue #57 feature branch and reached `main`
  through #69. Leaving them out would make batch 2's starting line wrong.
- **Evidence README edited in place, PR #68 doc appended.** The append-only rule
  applies to dated documents. The README is undated reference text, so a stale
  figure there is simply wrong. The PR #68 doc is dated, so it gets an as-of line.
- **Other dated docs that still say "provisional" are left alone.** The
  pipeline-health, training-floor and circulation implementation docs describe
  their own dates truthfully, and the register is where the current status lives.

## Verification

From a checkout of the PR branch:

```bash
python scripts/check_ids.py
ruff check . && ruff format --check .
python -m pytest tests/ -q -p no:cacheprovider
for id in NC-044 NC-045 NC-046 NC-047 NC-055; do
  printf '%s tabs=%s pipes=%s\n' "$id" \
    "$(grep -E "^\| $id " docs/numerical-claims.md | tr -cd '\t' | wc -c)" \
    "$(grep -E "^\| $id " docs/numerical-claims.md | sed 's/`[^`]*`//g' | tr -cd '|' | wc -c)"
done
git diff origin/main -- docs/numerical-claims.md | grep -c '^-|'
grep -c 'docs/verification/2026-10-01-phase-3-batch-1-burak-desktop.md' docs/numerical-claims.md
```

Expected: `check_ids.py` and both Ruff commands pass; the suite has no failures
and its count equals NC-021's value; every row prints `tabs=0 pipes=7`; the diff
count is 5 (NC-044 to NC-047 and NC-055); and the record path appears in at least
the five edited rows.

To re-derive the covered-PR set:

```bash
gh pr list --state merged --base main --limit 200 --json number,mergedAt,mergeCommit \
  --jq '.[] | select(.mergedAt >= "2026-09-05") | "\(.number) \(.mergeCommit.oid)"' |
  while read -r n c; do
    git merge-base --is-ancestor "$c" 110cfad87a11fe2dcf99daf0ccec8b5f82712238 && echo "#$n"
  done
```

It prints 23 PRs; #71 is the 24th, merged into `feature/issue-57-training-target`.

## Related docs

- Issue #100 (the batch-1 tracking issue) and PR #106
- `docs/team.md`, "Verification is batched on Burak's desktop"
- `docs/numerical-claims.md`, NC-012, NC-021, NC-037, NC-044 to NC-047, NC-054, NC-055
- `docs/implementations/2026-09-09-training-floor-derivation.md`
- `docs/verification/2026-09-05-issue-57-burak-desktop.md`, the previous desktop record
