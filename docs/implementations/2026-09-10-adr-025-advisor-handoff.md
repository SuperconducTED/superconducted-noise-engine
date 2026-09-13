# 2026-09-10: adr-025-advisor-handoff

## Problem / Motivation

Issue #48's last open Definition-of-Done item is Dr. Akba's sign-off on the ADR-025
pipeline-health amendment. PR #70 merged without it and recorded the deviation honestly,
deferring the item to Issue #84 with a decision-by date of 2026-09-23. That record was
accurate about what had *not* happened and wrong about what had: it named three pieces of
machinery, and an audit on 2026-09-10 found that none of the three existed.

| PR #70 recorded | Live state on 2026-09-10 |
| --- | --- |
| Brief rides as `docs/advisor/2026-09-09-akba-brief/06-olcum-birimi.html` | The file had never been committed to any branch. The cluster's `index.html` linked only 01 through 05 |
| "Travels with item 2 of the register" | Register item 2 is PR #55's `duplicate-partial` amendment, a different ADR-025 item. No row existed for the pipeline-health one |
| "Owner: #84" | Neither #84's body nor any of its comments mentions ADR-025 |

The deferral was therefore a paper trail with nothing behind it: an item marked Open, owned
by a ticket that had not been told, riding in a brief that did not exist. It would have
reached its 2026-09-23 date with nobody having anything to answer. This change builds the
three pieces so the deferral describes something real.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-09-09-akba-brief/06-olcum-birimi.html` | New: the Turkish brief putting the device-state definition to Dr. Akba, two asks and one ratification, with the three withdrawn items and the reason each was withdrawn. |
| `docs/advisor/2026-09-09-akba-brief/index.html` | Adds the File 06 card and names the amendment in the 23 September row of the decision calendar. |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | Appends a dated `Outstanding items, as of 2026-09-10` section carrying item 14, below the file's append marker. |
| `docs/decisions.md` | Appends a dated status block under the ADR-025 amendment recording it as Open, with what was circulated, who owns it, and what reversal costs. |

## Implementation approach

**The brief joins the 2026-09-09 cluster rather than going out on its own.** The register
says that batch is "the single message that carries these", batched deliberately because
thirteen separate asks to someone with no GitHub account is how the 2026-05-25 set went
unanswered for three months. A standalone ADR-025 message would reproduce exactly the
failure the batching exists to prevent. The brief is also the sibling of File 04's first
question: both ask what a ledger row records, and they should be decided together.

**That placement is only defensible because the batch has not been sent.** Adding a file to
a dated cluster is otherwise a violation of the append-only discipline. The deciding fact
was checked rather than assumed: `docs/advisor/2026-09-03-decisions-from-akba.md` records
no decision at all, every one of its thirteen items is still Outstanding, and PR #70's own
table says "Circulated: Not yet". Nobody has received a version of this cluster that lacks
File 06, so nothing is being rewritten under a reader. Had the batch gone out, the honest
form would have been a separately dated file, and this document would say so.

**The register gets an appended section, not a fourteenth row.** The Outstanding items
table sits above the file's "Append one dated entry per decision below this line. Do not
edit anything above it." marker. Adding a row would have edited above it. The appended
section states in its first line that it is not a decision entry, so a reader is not misled
about what kind of record it is.

**The ADR carries its own status block.** A deviation recorded only on a pull request is
invisible to someone reading `docs/decisions.md`. The block names the circulated state, the
owner, the decision-by date and the reversal cost, and it says explicitly that it is
cleared only by appending an answer to the register, not by a review, a merge, or the date
passing.

## Mathematical / Statistical details

N/A for this change; it moves no number. The figures it repeats are measured elsewhere and
cited rather than recomputed: 894 documents to 504 states at `f0930b9`, 936 to 537 at
`46f93c8`, 994 to 563 at `cb7a8c2`, with zero states merged under `date` stripping at every
ref, and 100% of the 861,789 qubit parameter records at `f0930b9` carrying a `date`. The
source is the step-4 reconciliation table in
`docs/implementations/2026-09-05-pipeline-health-dashboard.md`.

The direction guarantee is the part a reader should be able to audit without the code:
stripping a field is a function, so the partition it induces is a coarsening of the
original. The new state count can therefore only fall or stay equal, never rise. The only
open quantity was how many states merged, and the answer is zero at all three refs.

## Design decisions

**Why not send the ADR-025 ask as its own message.** Faster, and it would have arrived
sooner. Rejected because the register's stated reason for batching is that unbatched asks
to this advisor go unanswered, with three months of precedent. Speed into a channel with a
zero-for-ten answer rate is not speed.

**Why not add row 14 to the existing table.** It reads better in one place. Rejected
because the file forbids it in as many words, and this is the file whose whole authority
rests on being append-only.

**Why write the status block into `docs/decisions.md` at all**, given PR #70 already
carries the deviation. Because pull request comments are not where anyone looks up whether
an ADR is ratified. A reader opening ADR-025 six months from now should not have to know
that PR #70 exists in order to learn that its amendment was never signed off.

**Why not simply close #48.** Considered, since seven of the eight DoD items are met. It
would have closed the issue on a criterion recorded as satisfied-by-deferral when the
deferral pointed nowhere. See Related docs for the four items still genuinely open.

## Verification

```bash
python scripts/check_ids.py
test -f docs/advisor/2026-09-09-akba-brief/06-olcum-birimi.html
grep -c "06-olcum-birimi" docs/advisor/2026-09-09-akba-brief/index.html
grep -n "Outstanding items, as of 2026-09-10" docs/advisor/2026-09-03-decisions-from-akba.md
grep -n "ADR-025 amendment status" docs/decisions.md
```

`check_ids.py` reports no duplicate or colliding identifiers. This change adds no ADR or NC
identifier: item 14 is a row in the advisor register, which `check_ids.py` does not police,
and no numerical claim is introduced, only citations of NC-025 and NC-047.

Documentation only, so no test count moves and NC-021 is untouched. The brief renders as a
self-contained page with no external references, consistent with the other five files in
the cluster.

## Related docs

- Issue #48 (the DoD this unblocks), Issue #84 (the advisor loop that now owns item 14),
  PR #70 (where the deviation was recorded), PR #55 (register item 2, which this travels
  with)
- ADR-025 and its 2026-09-05 pipeline-health amendment in `docs/decisions.md`
- `docs/advisor/2026-09-03-decisions-from-akba.md`, the register this appends to
- `docs/implementations/2026-09-05-pipeline-health-dashboard.md`, the source of every
  figure the brief quotes
- NC-025 (504 distinct states), NC-047 (563 states from 994 documents)

**Still open on #48 after this change**, so that the next reader does not mistake this for
closure: Baha's sign-off on the three section 7 decisions, which were answered as proposals
and never contested or accepted; the first scheduled health render, which has never fired
because #70 merged after the day's `17 3 * * *` cron; register rows for the four section
7.3 thresholds, which the decision itself notes are missing; and an explicit acceptance of
the section 10 screenshot clause, which was satisfied by a measured contrast table and a
commit-pinned embed instead of a screenshot.
