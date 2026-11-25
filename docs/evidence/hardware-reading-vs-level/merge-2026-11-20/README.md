# #125 step 1d after PR #140's merge, 2026-11-20

Laptop, Windows, exact pins (`C:/t/pin125`), provisional until Burak's desktop run. Every run was made at `20e7345d`,
whose `scripts/`, `tests/` and `src/` trees are the ones this folder's commit carries. Pipeline acceptance on Aer, not
a measurement of the device: no NC row, and no sentence about `ibm_fez`.

The plan and criteria 36 to 41 are in `docs/implementations/2026-11-05-hardware-test-submission.md`, section "After PR
#140's merge, 2026-11-20", committed at `dcf3c7a5` before the code (`3199e13a`). The mutation script and its
predictions were committed at `20e7345d`, before it ran.

| File | What it is |
| --- | --- |
| `dry_run.sh` | Criterion 37: `rehearsal-2026-11-08/dry_run.sh` with its reference moved to `dry-run-2026-11-16`. |
| `dry-run.status.txt`, `dry-run.compare.txt` | The dry run's stages, and its comparison: `compare_dry_run.py`'s output, then one line per reference file. |
| `mutate_merge.py`, `mutation.tsv` | Criterion 39: the 16 mutants with their predictions, and the result table. |
| `gates.txt` | Criterion 41: each gate's exit code and last line, and the import check. |
| `rehearsal.status.txt`, `rehearsal.check.out.txt` | Criterion 40: the rehearsal's stages (`rehearsal-2026-11-08/rehearse_1d.sh`, unchanged) and its checker's output (`check_rehearsal.py`, unchanged). |
| `rehearsal-report-interim.json`, `rehearsal-report-day-15.json`, `rehearsal-arm-b-day-3.json` | The interim report, day 15's report from the sealed folder, and day 3's sealed Arm B scores. |

The commands, from a full clone that has `calibration-data` fetched:

    bash merge-2026-11-20/dry_run.sh <commit> <output folder> <clone> <python> [fetch source]
    bash rehearsal-2026-11-08/rehearse_1d.sh <commit> <output root> <clone> <python> <T1 python> [fetch source]
    python rehearsal-2026-11-08/check_rehearsal.py <output root> <clone>
    python merge-2026-11-20/mutate_merge.py --root <git archive copy> --python <python> --out mutation.tsv

**Fetching from a partial clone.** The first attempt of the dry run and the rehearsal stopped at their first command.
The full clone could not fetch this branch from the worktree it was built in (fatal: "could not fetch ... from promisor
remote"), because that worktree belongs to a `blob:none` clone. Updating the full clone's `origin/main` and this
branch's ref from GitHub first made the fetch need only the new commits. Neither run had started, so that attempt left
no output; the gates in `gates.txt` come from the same driver run, before the fetch.
