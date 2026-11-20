# Archive timing: gaps, late files, and what a scoring morning would have read

**Date**: 2026-11-20 · **Author**: Mert Efe Şensoy · **Owner of the question**: Issue #125 ·
**Status**: laptop run, provisional; no register row; written after the figures were posted

This folder holds the scripts and outputs behind the figures in two comments on #125:

- the day-15 rule question, comment 7047051597 (2026-11-20 18:09 UTC);
- the addendum on `reading_at_execution`, comment 7047937649 (2026-11-20 18:52 UTC).

Both comments say their scripts were not committed. This folder holds them. The figures were
first produced by one-off commands; the scripts here were written afterwards to compute the same
quantities from one pinned commit, and section 4 lists where the committed run differs from what
was posted. The outputs were checked by a second run on the same laptop and the same clone, which
shows the scripts are deterministic and nothing more; no other machine has run them.

## 1. What is measured, and on what

**Data.** `calibration-data` at `5d958ab2af09a3c8ed8c7222ef823130fe6229f6`, `ibm_fez` only, read
through `git` and never checked out.

**Two clocks per file.**

- *File time*: the time in the file's name, `snapshots/YYYY-MM/ibm_fez/YYYYMMDDTHHMMSS...Z.json`.
  `compare_readings.py` checks it against the document's `properties.last_update_date` on every
  file it opens (86 of 86 equal).
- *Arrival time*: the committer time of the first commit that adds the file.

**Three measurements**, all in `archive_timing.py`:

- **A, gaps.** Consecutive files sorted by file time; a gap is the difference between neighbours.
- **B, arrival lag.** Arrival time minus file time, for files dated from 2026-09-01 whose adding
  commit is not the earliest adding commit in the clone (a shallow clone's root "adds" every older
  file at once).
- **C, replay.** For each of 60 days and each queue delay, take `t_execute` as 03:45 UTC plus the
  delay. The job is scored at 04:00 UTC on the first morning after `t_execute` on which the
  archive already holds a file dated after `t_execute`, which is the condition `run_score` waits
  for in `scripts/hardware_submit.py` (PR #142 at `1ec698f8`; the file is not on `main` yet, so it
  is absent from this tree). *Held* is the latest file at or before `t_execute` among files
  that had arrived by that morning; *tip* is the same among all files at the pinned commit. A day
  counts when the two are different files.

`compare_readings.py` then opens the held and tip files of each counted day with the predictors'
own parser and says whether any of the five quantities the predictors read differs.

## 2. Results

Every figure below is copied from `archive_timing.out.txt` or `compare_readings.out.txt`, except
the tip files' times in section C's closing paragraph, which are `pairs.tsv`'s `tip_time` column.

**A.** 2,980 files from 2026-05-13 to 2026-11-19, a span of 190 days. Median gap 0.94 hours. Nine
gaps of 24 hours or more, two of them starting in the last 60 days. The latest is 112.4 hours, from
2026-11-13 16:27:59 to 2026-11-18 08:49:20 UTC.

**B.** 2,042 files dated from 2026-09-01. Median lag 4.25 hours; 18.2% arrive more than 24 hours
after their own time and 2.1% more than 48 hours; the maximum is 386.9 hours. Of the 974 files
later than 6 hours, 971 came in a commit adding three or more files, and 66 of the 70 such commits
landed between 08:00 and 14:00 UTC. One file was archived 11 minutes before its own file time.

**C.**

| Queue delay | Days of 60 with a different file | Same device state | One of the five quantities differs |
| --- | --- | --- | --- |
| 0.02 h (about 1 minute) | 4 | 3 | 1 (readout) |
| 2 h | 5 | 4 | 0 |
| 6 h | 9 | 4 | 3 (`T1` and `T2` on 2026-09-20; readout on two days) |
| 12 h | 25 | 13 | 5 (readout) |

On the four days at the shortest delay the tip file is dated before 03:45 UTC. On 2026-10-11
`readout_error` differs on 155 of 156 qubits.

The four days from 2026-11-14 to 2026-11-17 are scored late at every delay (on the fifth, fourth,
third and second morning), because of the 112.4 hour gap.

## 3. What this does not show

- **Whether the device ran jobs during the gap.** A job that stays queued is failed by
  amendment 18 and never reaches the scoring condition.
- **Which way a stale control moves the test.** No score was computed.
- **The real queue delay.** Job 1 measures it. The four delays are a spread, not an estimate.
- **The live document.** The replay reads the archive only. It assumes the document current at
  03:45 UTC is the archive's latest file at or before that time at the pinned commit.
- **The future archive.** PR #156 changes the sweep step, which may change how many files arrive
  in the daily bulk commit.
- **Why eight of the nine gaps happened.** A gap in file time can be the device publishing nothing
  or the pipeline capturing nothing. For 2026-11-13 to 2026-11-18 the poll commits say
  `no new document` throughout (section 4).

## 4. Where the committed run differs from the posted comments

| Posted | The committed run | Effect |
| --- | --- | --- |
| "The first file after it reached the archive at 2026-11-18 13:25 UTC" (7047051597) | That is the first file after the gap *by file time* (08:49:20), which arrived at 13:25:31. A later-dated file (10:42:53) arrived first, at 12:56:49. | 29 minutes. Day 15's morning in the comment's example is 03:45 UTC, before both. |
| "The poller ran 57 times in between" (7047051597) | 57 is the count between the last `calibration:` commit before that arrival (2026-11-14 11:45:09) and the arrival. Counted from when the last file before the gap arrived (2026-11-13 18:00:29), it is 68. All of them say `no new document` either way. | The posted figure understates. |
| "Equal to `last_update_date` on eight files" (7047937649) | Checked on every file opened: 86 of 86. | Stronger. |

The comments were not edited. Whether a correcting line is posted on #125 is the lead's call.

## 5. Reproduce

```bash
bash docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/run.sh <repo> <python> <out dir>
diff -r <out dir> docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20 --exclude='*.py' --exclude='*.sh' --exclude='*.md'
```

`<python>` needs the repository's pins (NumPy and the package's dependencies). `<repo>` needs the
pinned commit and the data branch's history back to 2026-09-01. Expected: `diff` prints nothing.
`compare_readings.py` imports `scripts/hardware_test_predictors.py` from the checkout it is given
and prints its blob id, so a run from another checkout shows which parser it used. The committed
run used `aac828e6` (`main` at `b9fcddea`). PR #142's version (`7d10641d` at `1ec698f8`) differs
from it in three hunks: the module docstring, `freeze_controls` and `main`'s controls branch. None
of them is called here, so the comparison is the same under either, but that line of the output
will differ.

The clone used here is shallow: its `calibration-data` history starts on 2026-08-01. The scripts
print the clone's earliest adding commit to stderr, not to the output files, and stop if the
history starts after 2026-09-01. Section A needs only the tree; sections B and C need the history.
