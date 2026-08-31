# 2026-08-27: pr29-verification-record

## Problem / Motivation

PR #29 merged as `4d005d4` with two gaps in its durable record, both introduced
by `adfbece` ("docs: add visual evidence for PR 29"), which landed after Burak's
desktop verification and before the merge.

1. Its screenshots went to `evidence/PR-29-Evidence/` — a new top-level
   directory. Every prior run stores evidence under `docs/evidence/`.
2. No verification document was committed. PR #33 and PR #34 each have one under
   `docs/verification/`; PR #32's equivalent lives at
   `docs/evidence/pr-32-burak-desktop/2026-08-20-verification.md`. PR #29's
   `VERIFIED` run existed only as a GitHub comment.

Gap 2 is the substantive one. PR #29 is the PR whose entire history is about
verification integrity — it exists partly because a runbook produced a false
`NOT VERIFIED`, and partly because a passing row concealed a real defect. Leaving
its verification outside the repository, in a comment, is the one place that
record should not live.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pr29-burak-desktop/*.png` (8 files) | Screenshots moved from `evidence/PR-29-Evidence/` via `git mv`, so history is preserved as renames. |
| `docs/verification/2026-08-27-pr29-burak-desktop.md` | New verification record: machine, all eleven result rows, the verified-versus-merged gap, and two runbook friction points. |
| `docs/implementations/2026-08-27-pr29-verification-record.md` | This document. |

No `.py` files touched; no tracked file content changed. The move is a pure
rename and the two new files are documentation.

## Implementation approach

`git mv` rather than delete-and-add, so the eight PNGs are recorded as renames
(`R`) and their history survives. Burak's original filenames are kept — the
existing evidence directories use inconsistent step-naming already, and renaming
the files would break the correspondence with the transcript he attached.

The directory name `pr29-burak-desktop` follows the two most recent precedents
(`pr33-burak-desktop`, `pr34-burak-desktop`) rather than the older
`pr-32-burak-desktop`, and drops the capitalisation of `PR-29-Evidence`.

The verification document follows the PR #34 template — commit tested, branch,
verdict, machine table, results table, notes, transcript pointer — with the
observed column populated from the attached PowerShell transcript rather than
from the summary table in the PR comment, so the record traces to the primary
source.

## Mathematical / Statistical details

N/A — purely structural. No numbers are computed here. The counts reproduced in
the verification document (`166 passed`, `35 files`, `22 source files`, `0`) are
transcribed from the transcript, not recalculated.

## Design decisions

**CPU and RAM are omitted from the machine table.** The PR #34 record lists
`AMD Ryzen 5 5500` / `15.9`, and the OS build in this run matches PR #34's
exactly, so it is almost certainly the same desktop. `Start-Transcript` does not
capture either field and this run did not query them, so copying them across
would put an unverified value into a verification document — precisely the
failure mode `docs/numerical-claims.md` was created to prevent. The document says
why the fields are blank instead.

**The verified-versus-merged gap is recorded, not smoothed over.** `adfbece` is
inert (`0 insertions(+), 0 deletions(-)` on tracked text), so the verdict stands
for the merged content. It is still written down, because a commit landing
between verification and merge is the shape by which unverified content reaches
`main`.

**The two runbook friction points are recorded as notes.** Neither is a defect in
PR #29, and both are actionable for the next runbook: multi-command paste blocks
get mangled by the PowerShell console, and the `python -c` one-liners emitted
`SyntaxWarning` because they reached the comment with single backslashes.

## Verification

```
# the top-level evidence directory is gone and nothing is tracked under it
git ls-files | grep -c '^evidence/'          # 0

# evidence sits with its siblings
ls docs/evidence/

# the moves are renames, not delete+add
git log --follow --oneline -- "docs/evidence/pr29-burak-desktop/Step 4.png"

# still documentation-only
git diff --name-only main -- "*.py" | wc -l  # 0
```

## Related docs

- `docs/verification/2026-08-27-pr29-burak-desktop.md`
- `docs/verification/2026-08-20-pr33-burak-desktop.md`, `...pr34-burak-desktop.md`
- `docs/implementations/2026-08-26-issues-40-41-ledger-label-and-stale-claim.md`
- PR #29 · issues #40, #41
