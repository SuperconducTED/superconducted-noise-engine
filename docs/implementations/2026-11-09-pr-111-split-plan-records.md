# 2026-11-09: pr-111-split-plan-records

## Problem / Motivation

PR #111 had been open since 2026-10-03. It carried two kinds of content:

- the three-engine plan and the records around it;
- a feature-pattern script and the 2026-10-06 deep dive built on it.

By 2026-11-09 three things had happened:

1. **Both reviews requested changes.** @bengisucvd (2026-10-28) and @BurakOztekin
   (2026-11-02) both reviewed the head, `f8a8d2e5`, and named the same three items:
   - `events()` drops fresh measurements whose value repeats;
   - `_spearman()` mishandles ties and constant input;
   - the evaluation protocol treats observations that share a calibration state as
     independent.
2. **The branch went DIRTY.** It conflicted with `main` on the NC-021 row, so `ci.yml` had not
   run on it since `5c65d06d`.
3. **`main` moved away from the plan.** It parked #110 (phase-4 plan §3) and recorded A7's
   premise as contradicted (strategy audit §3).

Meanwhile six records on `main` cite paths that existed only on the branch. The decisions
register still had no entry for the 2026-10-05 meeting with Dr. Akba.

The lead's decision of 2026-11-09 was to split the PR. The planning and meeting records land
on `main`. The code and the findings that depend on it stay on the kept branch, pinned by a
tag. The recommendation behind the decision is
`docs/audits/2026-11-09-pr-111-merge-close-or-split.md` on the lead's session branch, which
is not on `main`.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` | Lands from PR #111 as it stood at `f8a8d2e5`, with an appended section dated 2026-11-09: what landed and what stayed, why, the paths that exist only on the branch, the answer to both reviews' third item, and what changed since. |
| `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` | Lands as it stood at `f8a8d2e5`, with a one-line note dated 2026-11-09 withdrawing its Wilcoxon over epochs x circuits and its binomial coverage interval, pointing to the plan. |
| `docs/implementations/2026-10-04-three-engine-deep-model-plan.md` | Lands as it stood at `f8a8d2e5`, unchanged. |
| `docs/advisor/2026-10-04-uc-motor-ve-derin-model-ozeti.md` | Lands as it stood at `d9c04cb6`, unchanged. |
| `docs/advisor/2026-10-05-akba-meeting-deck/` (39 files) | Lands as it stood at `d9c04cb6`, unchanged: the deck shown to Dr. Akba on 2026-10-05. |
| `docs/implementations/2026-10-05-akba-meeting-deck.md` | Lands as it stood at `d9c04cb6`, unchanged. |
| `docs/implementations/2026-11-09-pr-111-split-plan-records.md` | This record. |

No test, script, ADR or `docs/numerical-claims.md` row changes.

## Implementation approach

The branch was cut from `main` at `d929424a` with no upstream. It has four commits:

1. **The 44 files**, taken with `git checkout d9c04cb6 -- <paths>`, one commit. `d9c04cb6` is
   the last PR #111 commit before @BurakOztekin's capstone commit. Every blob was checked
   against `d9c04cb6`. These files include his earlier `8d7965e2` (two research verdicts kept
   provisional), which lands inside this commit rather than as a commit of his own.
2. **`git cherry-pick f8a8d2e5`**, with no `-x`. He stays the author, and the message (his
   `Signed-off-by` and `Co-authored-by` trailers) and the diff are byte-identical to the
   original. After it, all 44 files match `f8a8d2e5` blob for blob.
3. **The plan's dated section and the research document's note**, appended at each file's
   foot. Nothing above them changes.
4. **This record.**

The branch PR #111 rests on is not rewritten. Its reviews and the 2026-10-05 runbook pin its
commits, and six records on `main` cite paths that exist only on it. The tag `archive/pr-111` points at `f8a8d2e5`, so those
commits stay reachable whatever happens to the branch.

## Mathematical / Statistical details

The answer to the reviews' third item changes the planned statistics of the three-engine
comparison (T11). It does so as a rule for the protocol, not as a fitted method.

**What is withdrawn.** A paired Wilcoxon signed-rank test with independent replicates. Over
`n` replicates `i`, with paired score differences `d_i`, the statistic

    W = sum_i sgn(d_i) R_i,    where R_i is the rank of |d_i|,

has its stated null distribution only if the `d_i` are independent (and symmetric about zero
under the null). Rows that share one day's device state (all circuits run against one
calibration snapshot, all qubits of one round) are not independent. Neither are consecutive
days, whose levels share most of their window. The same holds for a coverage share
`c = (1/n) sum_i 1[y_i in band_i]` reported with a binomial interval such as
`c ± z sqrt(c(1 - c)/n)`: when the indicators are serially correlated, that interval is too
narrow.

**What replaces it.**

- **Unit.** Index the evaluation by UTC calendar day `t = 1..T`, with day `t` carrying every
  observation made that day. Days with no observations stay on the axis with zero rows.
- **Resampling.** Pick a block length `L`, fixed with its reason in the protocol commit before
  any score is seen. Draw ceil(`T/L`) starting days uniformly. Take `L` consecutive days
  circularly from each, concatenate them, and cut the result to length `T`.
- **Score.** Recompute the row-weighted score difference, or the coverage, on each draw. The
  interval is the draws' quantiles at the stated level.

This keeps within-day dependence intact (a day is never split) and keeps dependence across
days up to lag `L - 1`. `main` already applies it with `L = 6`, where the floor came from the
successor-event count and the autocorrelation check (`docs/evidence/pattern-detector/README.md`
§12.4), and with `L = 3`, a stated judgment (`docs/roadmap/2026-10-24-issue-125-preregistration.md`
§3.7, item 8). This record fixes no `L` for #110. That belongs in the protocol commit of the
comparison, if #110 is unparked.

## Design decisions

- **A split, not a merge after fixes.** A merge would need both reviewers' first two
  findings fixed in `scripts/feature_patterns.py`. The fix would then cascade through the deep
  dive, which imports the event rule, and both re-reviews would follow. All of that to land a
  plan for an engine `main` has parked.
- **A split, not a plain close.** A plain close would leave six `main` records citing paths on
  a closed PR's branch, and the only record of the 2026-10-05 meeting off `main`.
- **The literature survey stays on the branch** (the lead's choice). Its lines 36 and 47 cite
  the script and the lag-1 range that R1 moves.
- **@BurakOztekin's capstone commit is cherry-picked** (the lead's choice), so he stays its
  author. Taking his text under the lead's commit was the alternative.
- **R3 is answered in text and not by fixing a block length.** No comparison exists to
  resample. A block length chosen now would be chosen without the series it must fit.

## Verification

From the branch's worktree, with `main` fetched:

```bash
git diff --stat origin/main -- tests scripts src docs/numerical-claims.md docs/decisions.md
```

Expected: empty.

```bash
git diff --name-status origin/main | cut -f1 | sort | uniq -c
```

Expected: 45 added. These are the 44 files and this record.

```bash
for f in $(git diff --name-only origin/main | grep -v 2026-11-09-pr-111-split-plan-records.md); do
  [ "$(git rev-parse HEAD~2:"$f")" = "$(git rev-parse f8a8d2e5:"$f")" ] || echo "DIFF $f"
done
```

Expected: no output. Before the appended section and note, every file equals PR #111's head.

```bash
git diff HEAD~2 HEAD~1 --stat
```

Expected: two files, insertions only.

```bash
git log -1 --format='%an%n%B' HEAD~2
git log -1 --format='%an%n%B' f8a8d2e5
```

Expected: identical author and message.

```bash
python scripts/check_ids.py
```

Expected: `No duplicate or colliding ADR / NC identifiers.`

```bash
git ls-remote origin refs/tags/archive/pr-111
```

Expected: the tag's object. `git rev-parse 'archive/pr-111^{commit}'` gives `f8a8d2e5e78c092d7ab2fa0a85b82689242ac709`.

## Related docs

- PR #111 and its reviews 5407321749, 5682132551, 5742601502; Issue #110 (comment
  6412965244); PR #98; PR #128
- `docs/roadmap/2026-10-23-phase-4-plan.md` §3, §4, §4.1, §8.3
- `docs/findings/2026-10-23-strategy-audit.md` §3
- `docs/evidence/pattern-detector/README.md` §7 (amendment 8) and §12.4
- `docs/roadmap/2026-10-24-issue-125-preregistration.md` §3.7
- `docs/advisor/2026-09-03-decisions-from-akba.md`
