# 2026-08-28: One-time LF renormalization of tracked text files

## Problem / Motivation

`.gitattributes` landed in 3dc7515 (2026-06-13, "fix(repo): normalize line
endings to LF via .gitattributes") declaring:

```
* text=auto eol=lf
```

Its comment states the intent plainly: "Normalize all text files to LF in the
repository and on checkout." But `.gitattributes` only governs files as they are
*added or updated* from that point on. Blobs already committed with CRLF stay
CRLF in the object database until someone re-stages them. Nothing in the June
change rewrote history or re-added the existing tree, so any file committed
before 2026-06-13 with CRLF was left untouched.

This was flagged while auditing PR #29. That PR, and the follow-up PR #42,
deliberately matched whatever line-ending convention each file already used so
their diffs stayed reviewable (37 added / 8 removed on `docs/decisions.md`
rather than a whole-file rewrite). Renormalization was therefore deferred to its
own PR — this one — so that a mechanical, whole-file change never rides along
with a content change and buries it.

**Scope correction.** The audit that motivated this work reported that "several
tracked markdown files" were still CRLF, citing `docs/decisions.md` (915) and
`docs/numerical-claims.md` (113). Re-measuring at the byte level, both of those
files are already pure LF, and the true scope is a single file. The cited
figures came from a measurement bug, described under **Design decisions** below;
correcting the measurement is recorded here because the bad command is the kind
of thing that gets copied into the next audit.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/decisions/drafts/ADR-017-missing-per-qubit-calibration-fields-skip-strategy.md` | Line endings converted CRLF to LF; text content byte-identical otherwise. |
| `docs/implementations/2026-08-28-lf-renormalization.md` | This record. |

No source files, tests, ADR ledger entries, or numerical-claims rows were
modified. No binary file was rewritten.

The two commits are kept separate on purpose: `chore: renormalize tracked text
files to LF per .gitattributes` contains *only* the renormalization and can be
reviewed in isolation, and this document lands as its own follow-up commit.

## Implementation approach

The renormalization is the standard one-time Git operation:

```bash
git add --renormalize .
git commit -m "chore: renormalize tracked text files to LF per .gitattributes"
```

`--renormalize` re-runs the clean filter over every tracked path — reading each
file, applying the `text=auto eol=lf` attribute, and re-staging it — while
skipping paths whose resulting blob is unchanged. Two properties make this safe
to run repo-wide rather than file-by-file:

1. **`text=auto` auto-detects binary.** Git classifies a blob as binary when it
   finds a NUL byte early in the content, and binary blobs are exempt from EOL
   conversion. The 42 tracked PNGs under `docs/evidence/` and `evidence/`
   contain CR bytes as ordinary compressed image data; none of them were
   re-staged. `git diff --numstat` reports them as `-` / `-` (binary), and they
   do not appear in the commit.
2. **The operation is idempotent.** Files already stored as LF produce an
   identical blob and are skipped, which is why 131 of 132 tracked paths are
   absent from the diff.

Measured scope at the parent commit (4d005d4):

| Metric | Value |
| --- | --- |
| Tracked files scanned | 132 |
| Blobs containing at least one CR byte | 43 |
| ...of those, `.png` (binary, correctly skipped) | 42 |
| ...of those, text (renormalized) | 1 |

The single text file, `ADR-017-...-skip-strategy.md`, was added 2026-05-26 in
4409e93 — eighteen days before `.gitattributes` — and had not been touched
since, which is exactly the predicted signature. Every other ADR draft
(ADR-018 through ADR-022) was already LF.

## Mathematical / Statistical details

N/A — purely structural. No formula, statistical test, or numeric algorithm is
involved; the change alters only byte-level line terminators.

For completeness, the byte accounting on the one changed file is exact and
checkable: the blob held 51 CRLF pairs and 0 lone LFs, so removing one CR per
line predicts 3024 - 51 = 2973 bytes. The renormalized blob is 2973 bytes.

## Design decisions

**Renormalize rather than rewrite history.** Rewriting the CRLF out of past
commits with `filter-branch` / `filter-repo` would give a "clean" history but
invalidates every existing commit SHA, breaks the ADR and numerical-claims
cross-references that cite commits by hash, and forces every collaborator to
re-clone. A forward-only renormalization commit costs one 51-line diff and
breaks nothing.

**`git add --renormalize .` rather than `dos2unix` on the one known file.**
Targeting the file by hand would have worked here, but it encodes today's audit
result into the fix. `--renormalize` asks Git to apply the repository's declared
policy to everything it tracks, so the command stays correct if the audit
undercounted, and re-running it later is a no-op that doubles as a check.

**Two commits, not one.** The repository convention requires an implementation
doc per meaningful change, but adding that doc inside the renormalization commit
would make the commit no longer provably line-endings-only. Splitting them keeps
`git show <renormalization-sha> -w --ignore-cr-at-eol` empty, which is the
property a reviewer actually wants to check.

**The measurement bug worth recording.** The audit's scan was:

```
git cat-file blob main:docs/decisions.md | grep -c $'\r'
```

`$'\r'` is Bash ANSI-C quoting. Under a shell that does not implement it — POSIX
`sh`/dash, or a command assembled in PowerShell — it does not expand to a
carriage return, and the pattern degenerates into one that matches every line.
The reported counts are therefore just line counts, which is verifiable: piping
each blob into `grep -c ''` (a pattern that matches everything) yields 915 for
`docs/decisions.md` and 113 for `docs/numerical-claims.md` — both matching the
reported figures exactly, on files that contain zero CR bytes.

Two follow-on lessons:

- **Count bytes, not `grep` lines.** `tr -cd '\r' | wc -c` cannot degenerate
  this way, and neither can a `b.count(b'\r\n')` in Python.
- **Filter binaries before reporting.** Even a correct CR scan flags all 42
  PNGs, so a raw scan overstates the scope by 43x. `git ls-files` plus a binary
  check, or simply reading `git diff --numstat` for `-` markers, is the honest
  denominator.

This is the same failure mode `docs/numerical-claims.md` exists to prevent — a
specific-looking number with no verified derivation behind it — arriving via a
shell quoting bug rather than a citation. The corrected scan, which counts CR
bytes and reports the path, is:

```bash
git ls-tree -r --name-only -z HEAD | while IFS= read -r -d '' f; do
  n=$(git cat-file blob "HEAD:$f" | tr -cd '\r' | wc -c)
  [ "$n" -gt 0 ] && echo "$n  $f"
done
```

...with binary paths excluded from the result before it is quoted anywhere.

## Verification

**1. The diff is line-endings-only.** This is the load-bearing check. The
renormalization commit shows a real diff normally, and an empty one once
carriage returns and whitespace are ignored:

```bash
git show <renormalization-sha> --stat
```

reports `1 file changed, 51 insertions(+), 51 deletions(-)`, while

```bash
git show <renormalization-sha> -w --ignore-cr-at-eol --format=""
```

produces no output at all.

Byte-level confirmation that no character other than CR moved:

```bash
python -c "import subprocess; f='docs/decisions/drafts/ADR-017-missing-per-qubit-calibration-fields-skip-strategy.md'; old=subprocess.run(['git','cat-file','blob','HEAD~1:'+f],capture_output=True).stdout; new=subprocess.run(['git','cat-file','blob','HEAD:'+f],capture_output=True).stdout; assert old.replace(b'\r\n',b'\n')==new; print(len(old),'->',len(new))"
```

prints `3024 -> 2973` and raises nothing.

**2. Re-running the operation is a no-op**, confirming convergence:

```bash
git add --renormalize . && git diff --cached --stat
```

produces no output.

**3. The four gates.** Run from the repository root with the project venv
active. All four pass on the renormalization commit:

| Gate | Command | Result |
| --- | --- | --- |
| Lint | `ruff check .` | `All checks passed!` |
| Format | `ruff format --check .` | `35 files already formatted` |
| Types | `mypy --strict src/superconducted` | `Success: no issues found in 22 source files` |
| Tests | `python -m pytest tests/ -q` | `166 passed` |

These four values are unchanged from the parent commit by construction — the
change touches one markdown file under `docs/`, which none of the four gates
read — so they are a regression check, not evidence about the change itself.
Check (1) is what proves the change correct.

## Related docs

- `.gitattributes` — the policy this commit brings the existing tree into line
  with; added in 3dc7515.
- `docs/decisions/drafts/ADR-017-missing-per-qubit-calibration-fields-skip-strategy.md`
  — the only file touched; content unchanged.
- `docs/numerical-claims.md` — the register whose discipline the scope
  correction above applies to. No rows added: per its Purpose section the
  register governs public-facing documents, and `docs/implementations/` is not
  in that set. Every figure in this document is reproducible from a command
  quoted alongside it.
- PR #29 and PR #42 — the reviews during which this cleanup was identified and
  deliberately deferred.
