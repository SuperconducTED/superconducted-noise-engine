# Sealed rehearsal of the #125 submission cycle and the dry run, 2026-11-09

**Pipeline acceptance on Aer, not a measurement of the device, and no NC row.** As on 2026-11-06, the simulator is
built from the same reading the rehearsal compares against, so `level` loses by construction; these files show the code
reaching its answers, nothing about which predictor is right on hardware. Laptop, provisional.

Record: `docs/implementations/2026-11-05-hardware-test-submission.md`, "Stage 2, phase 2d". Both runs are at
`55f05ea0`, from the full clone; the dry run and rehearsal scripts are in that commit, and the checker's second
version, which produced `check.out.txt`, is in the commit after it (`dce7414f`).

| Criterion | Result | Evidence |
| --- | --- | --- |
| 10 (amendment 20 plan): the dry run's outputs stay identical to `dry-run-2026-11-05/` | **Holds.** `compare_dry_run.py` exits 0 with every MUST MATCH row holding, and all 8 files are byte-identical, line endings normalised. 16 minutes. | `dry-run.status.txt`, `dry-run.compare.txt` |
| 11 (amendment 20 plan): the rehearsal's checks all hold | **Holds.** 66 of 66, with the checks of criteria 2, 3 and 4 read from the sealed folder. Selection, controls, slots and layouts are the dry run's. | `check.out.txt` |
| 26 (stage 2): criteria 10 and 11 re-run once, the checks updated for the sealed folder | **Holds**, with the checker changed once after its first run; see below. | all of the above |

## What ran

`rehearse_1d.sh`, an adapted copy of `rehearsal-2026-11-06/rehearse_1d.sh`: the same days (2026-11-02 and 04, with 03
absent), the same live documents and the same archive commit `b9279b99`. New: every score, `T1` score and report gets
`--sealed-dir`, outside the jobs folder and the clone; the jobs folder is a throwaway git repository that every morning
commits, never pushed; and a day-15 morning (2026-11-16) follows the interim report. Every stage exited 0
(`status.txt`): the criterion 2 build 3 min 22 s, day 1's morning 4 min 6 s, day 3's 6 min 1 s, day 3 scored by hand
2 min 15 s, the report 2 s, day 15 4 s; 15 min 53 s in all.

Where the 2026-11-06 figures can be compared, they are the same: the discriminating sets, the 112 discriminating and
56 control rows, the eight `T1` fits to the tenth of a microsecond, and 60 and 66 of 84 rows where the execution reading
differs. A1's and A2's means are `0.154` and `0.00797` where 2026-11-06 printed `-0.154` and `-0.00797`: amendment 25
turned `D` round, so negative now favours `level`. A4 counts 96 rows, the 112 less the 16 at `tau = 0` (two days, eight qubits), which it no longer counts.

## Sealing on the real path

The checker gathers 1,288 score-derived values from the sealed folder (`p_hat`, each error and log score as the TSV
writes them, Arm B's measured values, each summary figure, every `T1` fit number) and all 7,530 raw count entries of the
sealed results, then looks for each in every file the mornings left in the jobs folder, in the routine's logs and
records, in each command's stdout, and in every file of the commits before day 15. None is found, apart from the
coincidences in build files explained next. Day 15's commit adds
`sealed/`, equal to the sealed folder byte for byte, and its morning reported, unsealed and committed without building.

**The checker was changed after its first run, and this is why.** Its first output (`check.out.first.txt`) failed
three checks on values found in `live-properties.json`, `predictors.tsv` and `sealed.json`. Every one is a fraction of
shots, such as `0.0009765625` (2 of 2048): a `p_hat` is one, and so are the device's readout errors and the predictions
made from them, so the two collide. All three files are written by a day's build, and that day's counts are fetched on
a later morning, so a file whose bytes are those the build morning committed cannot hold a score. The second version
(`check.out.txt`) excuses a hit only in such a file (compared with line endings normalised, because `predictors.tsv` is
written with CRLF and git stores it with LF) and still fails on any other. It also adds the raw count entries. To show
it is not blind, `check.planted.out.txt` is the same checker on a copy with three planted leaks, a `p_hat` in a routine
log, a raw count entry in `operations.json` and a line added to a build's `predictors.tsv`: it reports all three.

Two things the rehearsal shows that the real run does not do:

- `jobs/local-jobs/` is the simulator's store, holding its raw counts, and the rehearsal's mornings committed it. It
  exists only with `--local-live`; in a real run the counts stay on IBM's service until `score` fetches them into the
  sealed folder. The checker keeps it apart from the scan and says so.
- `predictors.tsv` is the one file a build writes with CRLF; the others are LF. It is not hash-pinned in
  `submission.json`, so nothing breaks, but its bytes on the data branch differ from the file on disk.

## Files

| File | What it is |
| --- | --- |
| `rehearse_1d.sh`, `check_rehearsal.py` | The rehearsal and its checker. |
| `dry_run.sh` | Criterion 10: the dry run and its comparison. |
| `status.txt`, `days.txt` | The rehearsal's stages and the days and live documents chosen. |
| `check.out.txt`, `check.out.first.txt`, `check.planted.out.txt` | The checker's second and first runs, and the planted-leak run. |
| `report-interim.json`, `report-day-15.json` | The interim report after day 3 and day 15's complete one. |
| `t1-check.json`, `arm-b-day-3.json` | Day 1's `T1` fits and day 3's Arm B scores, from the sealed folder. |
| `dry-run.status.txt`, `dry-run.compare.txt` | The dry run's stages and comparison. |

To run them, from a clone that has `calibration-data` fetched, with the exact-pin interpreter and the `T1` interpreter
(the pins plus `qiskit-experiments==0.14.2`):

    bash dry_run.sh <commit> <output folder> <clone> <python> [fetch source]
    bash rehearse_1d.sh <commit> <output root> <clone> <python> <T1 python> [fetch source]
    python check_rehearsal.py <output root> <clone>

Run them one at a time; each takes about 16 minutes on the laptop, and the checker about 3.
