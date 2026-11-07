# Evidence for the statistics review of PR #135

Scripts and outputs behind the numbers in the statistics review of PR #135, the pre-registration of
the #125 hardware test. Record: `docs/implementations/2026-11-07-pr135-review-evidence.md`.

> **NOTE · What this is not.** No hardware result exists, and nothing here is a claim about the
> device. Every scenario below is a what-if for `T1` at execution. Laptop, provisional, no register
> row. These are review sensitivities, not Burak's desktop verification.

> **NOTE · Not meant for merge as it stands.** The branch is cited by commit. The scripts are
> formatted with `ruff format`, but `ruff check` still reports about 100 style items, mostly long
> lines in print tables and docstrings, and the paths are hard-coded (below).

## What was measured at

| Thing | Commit |
| --- | --- |
| PR #135, read as the rule under review | `51e9f425` |
| PR #140, read for the scoring code | `2aea1e18` |
| `main` | `43a2c9b0` |
| Predictors, the pinned code | `5c98f264` |
| Predictors, the old code amendment 14 compares | `d62928fa` |
| `calibration-data` | `7adda803` (2,398 `ibm_fez` files, 958 states) |

Python 3.12, numpy 2.4.4, scipy 1.17.1, qiskit 2.4.1, qiskit-aer 0.17.2.

## Scenarios

| Scenario | `T1` at execution | Stands for |
| --- | --- | --- |
| N | the level | all scatter is the reading's own noise |
| F | the qubit's next changed archived reading, median 17.5 h after `t_s` | fast physical scatter, or the archive's nearest proxy; it reverts about 83% toward the level (NC-084) and carries calibration noise, so it is not the device |
| S | the reading | the deviation persists to execution |
| `M(a, s)` | `(1 - a) log reading + a log level + s z`, `z` iid per qubit-day | position `a` between reading and level; `a = 0.5` is equal accuracy (NC-087); `s = 0.289` is `0.37 / z_0.9`, design section 1's scatter |

Pass rates come from overlapping 14-day (Arm B: 13-day) windows out of 137 days. About nine of them
are independent, so read the rates as descriptive.

## Set up

All paths use the short root `C:/t135` because of Windows' path limit. On another machine, replace it
in the scripts with one search and replace. `M` is a checkout holding the `calibration-data` blobs up to
`7adda803`. Set `GIT_NO_LAZY_FETCH=1` when reading the archive, or a partial clone quietly downloads blobs.

```bash
mkdir -p /c/t135/old /c/t135/new /c/t135/cache
```

```bash
git archive d62928fa src scripts | tar -x -C /c/t135/old
```

```bash
git archive 5c98f264 src scripts | tar -x -C /c/t135/new
```

```bash
git show 2aea1e1850de98b673e1b6c60bd0a5ac5c7d9aa6:scripts/hardware_reading_vs_level.py > /c/t135/new/scripts/hardware_reading_vs_level.py
```

```bash
git show 51e9f425:docs/evidence/hardware-reading-vs-level/null-values.json > /c/t135/null-values.json
```

## Run order

Run from this folder, with `PYTHONPATH=C:/t135/new/src`, `PYTHONUTF8=1` and `GIT_NO_LAZY_FETCH=1`.
`REF` is `7adda8035a5a76b93147ffc3171975a7684d239d`. Each output is committed beside its script.

| Step | Command | Output | Used for |
| --- | --- | --- | --- |
| 1 | `python cache_build.py M REF C:/t135/cache/collected.pkl` | cache, about 1 min | |
| 2 | `python arch_days.py` | `C:/t135/cache/days.pkl`, about 3 min | |
| 3 | `python config_scan.py M REF` | `config.out.txt` | note for PR #140 |
| 4 | `python arm_a_worlds.py 8` | `worlds.out.txt` | the rule in each scenario, A1, A4 |
| 5 | `python a1_a3_joint.py` | `joint.out.txt` | S1 with and without A4 as a gate |
| 6 | `python arm_a_fit.py` | `fit.out.txt` | direct `T1` fit: `c`, `s_res` |
| 7 | `python a1_empirical.py` | `empirical.out.txt` | A1's size on the real series |
| 8 | `python a1_size.py` | `a1_size.out.txt` | A1's size under AR(1), batch means |
| 9 | `python armb_exact.py C:/t135/null-values.json` | `armb_exact.out.txt` | Arm B null (i), exact |
| 10 | `python arm_b_days.py M REF 1` | `C:/t135/cache/armb/*.pkl`, about 40 min, resumes by file | Arm B on real days |
| 11 | `python arm_b_analysis.py` | `armb.out.txt` | Arm B conditions |
| 12 | `python harness_checks.py <clone> M` | `checks.out.txt` | cache check, no future data, live path |
| 13 | `python q5_old_vs_new.py` | `q5.out.txt` | amendment 14, old against new |
| 14 | `python astcmp2.py <old predictors> <new predictors>` | `astcmp.out.txt` | amendment 14's definition counts |

Steps 8 and 9 need neither the archive nor project code, so they are the quickest to re-run. Also, unchanged:
`python docs/evidence/hardware-reading-vs-level/null_values.py --out <dir>` at `51e9f425`, whose JSON must equal the
committed one byte for byte (it does).

Seeds are `SeedSequence` roots: 1351107 (`a1_size`), 135110701 and 135110702 (`arm_a_worlds`), 135110703
(`arm_a_fit`), 135110704 (`a1_empirical`), 135110705 (`arm_b_analysis`), 135110706 (`a1_a3_joint`).

## Known limits

- Controls are the PR's rehearsal four (144, 110, 140, 77), not the frozen ones.
- `reading_at_execution` equals `reading` here, the modal case (NC-091: a sweep within 3 h of 03:45 UTC on 9.3% of days).
- Shots are the only noise the simulation adds: no non-exponential decay, thermal population or readout-induced
  transition. On hardware `s_res` will sit above the 0.012 fit noise.
- `arm_b_days.py` takes `configuration` from the nearest earlier file when the current one has none, since
  `archived_backend` raises on a null one. That is the note for PR #140, not a fix for it.
- `dt` rounding of delays is ignored in the Arm A scenarios.
