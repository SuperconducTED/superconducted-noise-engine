# 2026-11-20: archive-timing evidence for the two pre-freeze questions on #125

## Problem / Motivation

Two comments on #125 on 2026-11-20 ask the team to settle rule gaps before the hardware test's
freeze: what happens to a job that cannot be scored on day 15's morning (7047051597), and which
archive state the `reading_at_execution` control is read from (7047937649). Both carry figures
measured on `calibration-data`, and both say their scripts were not committed. The figures came
from one-off commands in a session scratchpad, which a reboot clears. A figure nobody can re-run
is the failure the numerical-claims register exists to prevent, so the scripts and their outputs
are committed here, pinned to the data commit they read.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/archive_timing.py` | Measures gaps in file time, arrival lag and a 60-day scoring replay on `ibm_fez` at one pinned data commit. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/compare_readings.py` | Opens the replay's file pairs with the predictors' parser and counts the days on which a value differs. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/run.sh` | Runs both at `5d958ab2` and writes the three outputs with LF endings. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/archive_timing.out.txt` | The first script's output. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/pairs.tsv` | The replay's 43 day and delay rows whose held and tip files differ. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/compare_readings.out.txt` | The second script's output. |
| `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/README.md` | What is measured, the results, the limits, and where the run differs from the posted comments. |
| `docs/status/2026-11-20-status.md` | A dated section appended for the evening's later events. |

No file under `src/`, `tests/` or `scripts/` changes, so NC-021 is untouched.

## Implementation approach

The data branch is read through `git` at a full commit id, never checked out, so autocrlf cannot
touch it and the run does not depend on where the branch tip is.

Each file gets two clocks. Its *file time* is the time in its name, which is the document's
`last_update_date`. Its *arrival time* is the committer time of the first commit that adds it,
taken from `git log --diff-filter=A --name-only`. Everything else is arithmetic on those two.

`archive_timing.py` uses only the standard library and reads no file contents. It writes the
replay's differing pairs to a TSV. `compare_readings.py` reads that TSV and needs NumPy and the
package, because it calls `scripts/hardware_test_predictors.py::_record`, the same parser the
hardware test's predictors use. Splitting them keeps the timing claims reproducible without an
environment, and ties "a value differs" to the quantities the test actually reads.

## Mathematical / Statistical details

**Gap.** With file times sorted as `t_1 < t_2 < ...`, the gaps are `t_{i+1} - t_i`. The count
reported is of gaps of at least 24 hours.

**Arrival lag.** For a file with file time `t` and arrival time `a`, the lag is `a - t` in hours.
Only files with `t` on or after 2026-09-01 count, and a file whose adding commit is the earliest
adding commit in the clone is left out, because a shallow clone's root commit adds every older
file at once and its time is not an arrival.

**Replay.** For day `D` and queue delay `q`, `t_execute = D 03:45 UTC + q`. Let `M_k` be 04:00 UTC
on day `D + k`. The job is scored on the first `k >= 1` with `M_k > t_execute` such that some file
has `t > t_execute` and `a <= M_k`. That is the condition `score` waits for: a file in the archive
dated after `t_execute`. Then

- held `= max { t : t <= t_execute and a <= M_k }`,
- tip `= max { t : t <= t_execute }`,

and the day is counted when held and tip are different files. The 60 days end three days before
the newest arrival in the pinned commit, so that the last days' late files have arrived.

**A value differs.** For a counted day, the held and tip files are parsed into a
`(qubits, 5)` array over `T1`, `T2`, `readout_error`, `prob_meas0_prep1` and `prob_meas1_prep0`.
A cell is changed when both files hold a number and the numbers differ, or when exactly one holds
a number. Two files with equal qubit-block digests are the same device state and are not compared
cell by cell.

No test statistic, interval or threshold is computed. The counts describe the archive; they are
not estimates of a rate, and the four queue delays are a spread chosen because the real delay is
unknown until job 1.

## Design decisions

- **File names, not commit subjects, for file time.** A first attempt measured gaps between
  `calibration:` commit subjects and found 97.2 hours. The subject's stamp is the commit time, and
  one commit can add many files, so that measured arrivals, not documents. File names give 112.4
  hours for the same event and nine gaps where the subjects gave one.
- **The scoring condition copied from the code, not assumed.** The replay scores on the first
  morning a later-dated file is held, because that is what `run_score` checks. Scoring on the next
  morning unconditionally would have hidden the four days that slip.
- **A pinned commit id in `run.sh`.** The branch moves several times a day. A ref name would make
  every later run a different measurement.
- **Under `docs/evidence`, not `scripts/`.** These are one measurement's record, not tools the
  pipeline calls. `mypy --strict` covers `scripts/`; `ruff` covers this folder too, and both
  scripts pass it.
- **No register rows.** The figures support two open questions and are laptop readings. They
  become claims only if an amendment or the paper quotes them, and that is the moment to register
  them.
- **The posted comments are not edited.** Section 4 of the README lists three places where the
  committed run differs from them. Posting a correction is the lead's decision.

## Verification

```bash
bash docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/run.sh <repo> <python> <out dir>
diff -r <out dir> docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20 --exclude='*.py' --exclude='*.sh' --exclude='*.md'
ruff check docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20
ruff format --check docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20
```

Expected: `run.sh` ends with `rows written for compare_readings.py: 43` and
`files opened: 86; name time equal to last_update_date on 86`; `diff` prints nothing; both `ruff`
commands pass. Run on the laptop on 2026-11-20 with the exact-pin environment and
`PYTHONPATH=src`; Burak's desktop has not run it.

## Related docs

- `docs/evidence/hardware-reading-vs-level/archive-timing-2026-11-20/README.md`
- `docs/roadmap/2026-10-24-issue-125-preregistration.md`, amendments 18, 19, 25, 27 and 36, and
  section 2's row for `reading_at_execution`
- `docs/implementations/2026-11-05-hardware-test-submission.md`, "One edge recorded, not changed"
- Issue #125, comments 7047051597 and 7047937649; PR #142
- `docs/status/2026-11-20-status.md`
