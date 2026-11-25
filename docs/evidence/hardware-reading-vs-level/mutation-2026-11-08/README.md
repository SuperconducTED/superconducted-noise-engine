# Mutation pass over stage 2 of the #125 submission script, 2026-11-08 to 2026-11-09

**Criterion 25 of the stage 2 plan** (`docs/implementations/2026-11-05-hardware-test-submission.md`): every line
stage 2 added to the scripts is mutated, and a test must fail. No device measurement and no NC row. Laptop, on the
exact pins (`C:/t/pin125`), provisional until it is reproduced on Burak's desktop.

## The record

At `2514b260`, with the twelve mutants of its re-run at `5bafd1ba` (tests and this script changed between the two;
the scripts did not, so the numbering holds):

| | Mutants |
| --- | --- |
| Generated from `git diff 999acee9..2514b260` over `hardware_submit.py`, `hardware_daily.py`, `hardware_t1_check.py` | 598 |
| Caught by an assertion | 294 |
| Caught by a crash | 292 (224 deletions, 68 operator or constant mutants) |
| Survived | 12, each equivalent, below |
| Timed out | 0 |

The 598 are 528 in `hardware_submit.py`, 39 in `hardware_daily.py` and 31 in `hardware_t1_check.py`. 58 added lines
get no mutant: closing brackets, `def`, `try` and `except` lines, and lines inside a comprehension, none of which can
be deleted alone and still compile; the pass lists each at its head (`final.out.0.txt`). Two shards ran at once in plain
copies, 00:27 to 01:09.

A crash is a kill: the mutant made a test fail. It is recorded apart because it is weaker evidence than an assertion
about the value. Of the 68 operator and constant mutants caught by a crash (messages in `final.tsv`), the crash is the
code failing the way the mutant makes it fail:

- `TypeError` (31): 21 are a path join `a / b` turned into `a * b`, which Python refuses for paths; the other ten are a
  date, a list or a `None` reaching an operator the mutant changed;
- `IndexError` (10) from an index moved past the end; `AttributeError` (9), mostly a `None` the mutant let through;
- `FileNotFoundError` (5) and `FileExistsError` (4): a folder not made or made twice, or a scored file written where
  the test does not find it;
- `ValueError` (5): three Arm B items moved outside every batch, an unpacking and a math domain error;
- `KeyError` (2), an `AxisError` from a summed axis moved, and a `SystemExit` from a guard that refuses a valid
  command line.

## The twelve that survive, and why they are equivalent

Line numbers at `2514b260`, all in `scripts/hardware_submit.py`.

| # | Line | Mutant | Why no valid input can tell it apart |
| --- | --- | --- | --- |
| 68 | 840 | Arm B's fidelity clamp `1.0` to `1.01` | A measured value is a fraction of shots, never above 1, so `min(x, 1.01)` is `min(x, 1.0)`. |
| 162 | 944 | `zip(sums, counts, strict=True)` to `False` | Both lists are built with one entry per batch; their lengths always match. |
| 229 | 985 | the T1 fit's lower clip `1e-9` to `1.01e-9` | By argument, not proof: the bound changes the likelihood only at grid points where a row's `p` is within `1e-9` of 0, far from the maximum for any row with `0 < ones < shots`; where every row is clipped, every clipped point ties either way. |
| 230 | 985 | the upper clip's `1.0` to `1.01` | For a `tau > 0` row `p` is below 1 strictly: `exp(-tau / T1) < 1` because `tau / T1` is many orders above double precision for any slot and any grid `T1` (at most 20 times `level`), and `p` lies between `1 - e10` and `e01`; `p = 1` would need `e10 = 0` with no decay at all, or `e01 = 1` (a readout that always says 1) with complete decay. By argument: neither is a readout a calibration reports, so the upper clip does not act. |
| 231 | 985 | the upper clip's `-` to `+` | The same: the upper clip never acts. |
| 232 | 985 | the upper clip's `1e-9` to `1.01e-9` | The same: the upper clip never acts. |
| 242 | 993 | `slope_and_spread`'s early return removed | With no points the fall-through returns the same `{"c": None, "s_res": None, "qubit_days": 0}`. |
| 293 | 1033 | the `continue` after `if not others` removed | With no other qubit the loop below does nothing, `counted` stays 0 and nothing is appended. |
| 406 | 1189 | `generate_state(2)` to `generate_state(3)` | `SeedSequence.generate_state` returns a prefix of one stream: the first two words are the same (checked: `2237865376`, `3222017606` either way). |
| 436 | 1221 | A4's `tau_dt > 0` to `> 1` | A slot is 0.5, 1 or 2 times a qubit's T1, so `tau_dt = 1` (4 ns) needs a T1 of 8 ns or less; the dry run's smallest nonzero slot is 865 dt (`dry-run-2026-11-05/manifest.json`). |
| 466 | 1245 | `c`'s points `tau_dt > 0` to `>= 0` | A `tau = 0` row's `p` is `1 - e10` at every grid point, adding one constant to every point's log-likelihood; the maximum does not move. |
| 467 | 1245 | `c`'s points `tau_dt > 0` to `> 1` | As 436. |

## How it was reached

| Pass | At | What it found |
| --- | --- | --- |
| Discovery (`discovery.tsv`, `discovery.out.txt`) | `92f008ce` | 587 mutants: 493 caught, 92 survived, 2 timed out because the laptop slept for six hours mid-run. Its `how` column is empty: at pytest's default 80 columns the summary line drops the failure's message once the test id is long, so the pass named each killing test but not whether it was an assertion. The script now runs pytest at 1,000 columns. |
| Re-run of those 94 (`discovery-rerun.tsv`) | `1e434118` | After the tests that commit added: 24 survived. Fifteen were expected: eleven of the twelve above and four reading-text lines that `47acd745` replaced. One was a real gap (a mean `D` of exactly zero), fixed in `2514b260`; one more was equivalent (242); seven were in `main`, standing only because the script's score group did not run the two command-line tests `1e434118` added. |
| Final (`final.tsv`, `final.out.0.txt`, `final.out.1.txt`) | `2514b260` | 598 mutants: 586 caught, the 12 above survived. Ten kills had no message because a parametrized test id held spaces, and two guard mutants in `main` (502, 522) were caught only because the next step, a `git` call, crashed. |
| Re-run of those 12 (`final-rerun.tsv`, `final-rerun.out.txt`) | `5bafd1ba` | All 12 caught by an assertion, after the script read ids up to the first ` - ` and the refusal test made anything past the guard fail. |

What the discovery pass found untested, and the tests now cover: the no-information band's branches (an unmovable
band end, a missing band end, an unusable `level`, inclusive ends) and a fixture whose shares had all been 0.5, so a row
read against the wrong qubit went unseen; every field of an inconclusive batch-means result and the strict `t > t95`;
the T1 fit's grid and its equality with a direct likelihood; `s_res`'s exact definition and `c`'s per-day points; Arm
B's near ties and an undefined correlation; A4's fields, `minimum_days` and `arm_b_reading`; A3 at a control mean of
exactly zero; S1 inconclusive with every day completed; the score command passing its sealed folder; the routine
passing it to every step; and the reading texts, which paraphrased amendment 29 until `47acd745` made them its words.

## Running it

From the repository root, with the exact-pin interpreter and `PYTHONPATH` holding `.` and `src`:

    python mutate_stage_2.py <repo root> 999acee9 <out folder> --list
    python mutate_stage_2.py <repo root> 999acee9 <out folder> --run-root <copy 1> --shard 0/2
    python mutate_stage_2.py <repo root> 999acee9 <out folder> --run-root <copy 2> --shard 1/2
    python mutate_stage_2.py <repo root> 999acee9 <out folder> --merge 2
    python mutate_stage_2.py <repo root> 999acee9 <out folder> --only <n,n,...>

A copy is a plain folder (no `.git`) whose scripts and four hardware test files equal the repository's byte for byte;
the script refuses one that differs. Without `--run-root` it mutates the repository's own scripts and restores them from
memory, so leave that tree alone while it runs. Each pytest run has its own time limit and writes one status line;
start a stall watchdog beside a full pass. The home folder in failure messages is written `<home>`.
