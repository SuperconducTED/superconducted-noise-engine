# Rehearsal of the #125 submission cycle, 2026-11-06

**Pipeline acceptance on Aer, not a measurement of the device, and no NC row.** The simulator is built from
the same reading the rehearsal compares against, so `level` loses by construction. These files show the code
reaching its answers; they say nothing about which predictor is right on hardware. Laptop, provisional.

Record: `docs/implementations/2026-11-05-hardware-test-submission.md`, "Results".

| File | What it is |
| --- | --- |
| `rehearse_1d.sh` | The rehearsal: `build` at the dry run's instant, then the morning routine on days 1 and 3 with day 2 absent. |
| `check_rehearsal.py` | Compares its outputs with criteria 2, 3 and 4. |
| `check.out.txt` | That comparison, for the run at `9745583e`. |
| `status.txt` | The run's stages, with their times and exit codes. |
| `days.txt` | The days chosen and each day's live document. |
| `report.json` | The final `report`: the decision rule's code on the three-day calendar. |
| `t1-check.json` | Day 1's `T1` fits against the simulator's values. |
| `arm-b-day-3.json` | Day 3's Arm B scores. |
| `mutate_submit.py`, `mutate_routine.py` | Remove each guard in turn and require a test to fail. |
| `mutation.out.txt` | Both runs at `9745583e`, then the re-run of the four flagged and the one new mutant at `3f062d4f`. |

A full re-run prints 75 and 60 mutants. The committed output shows 74 and 60, because the 75th was added
with `3f062d4f` and is among the five re-run at its foot.

To run them, from a clone that has `calibration-data` fetched:

    bash rehearse_1d.sh <commit> <output root> <clone> <python> <T1 python> [fetch source]
    python check_rehearsal.py <output root> <clone>
    python mutate_submit.py <repo root>          # with <python>
    python mutate_routine.py <repo root>         # with <T1 python>, so the library's tests run

`<python>` holds the project's exact pins; `<T1 python>` those pins plus `qiskit-experiments==0.14.2`.
The mutation scripts rewrite the scripts in place while they run and restore them from memory, so leave that
tree alone until they end, and never run the two at once.
