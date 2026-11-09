# Stage 3, 2026-11-09: amendment 37's three code items

PR #142's evidence for criteria 33 to 35 of the stage 3 plan in
`docs/implementations/2026-11-05-hardware-test-submission.md` ("Stage 3 plan, 2026-11-09"). Amendment 37 is in section
3.12 of the pre-registration on `main` (PR #135, merged as `d929424a`). Laptop, provisional: Burak's desktop is the source
of truth.

## What is here

| File | What it holds |
| --- | --- |
| `mutate_stage_3.py` | The 42 mutants of the new lines, each with its prediction, committed (`558732f8`) before the first run; `--only` added for the re-run (`78dbaf78`) |
| `mutation-first-run.tsv`, `.log` | First run: 37 caught, 5 survived, 2 against the prediction (H15 survived, P19 caught) |
| `mutation-rerun-H.tsv`, `.log` | The 21 report mutants again, after the report test was given the power to tell seed words apart: 20 caught, H02 survives as predicted |
| `controls_runs.sh` | Criterion 35: `--mode controls` with `e639cf86`'s code and with the new code, from plain copies, at the same `--ref` and `--at`, committed (`b611e312`) before it ran |
| `controls-rehearsal-2026-10-28*` | At section 3.9's instant (`7adda803`, 2026-10-28T18:40:46Z): both codes give 144, 110, 140, 77; qubit 72 marked; nothing skipped |
| `controls-tip-2026-11-09*` | At the archive tip read on 2026-11-09 (`60d082b0`, 2026-11-09T12:11:46Z): both give 45, 147, 42, 142; qubits 72, 148, 149 marked; nothing skipped |
| `controls-runs.status.txt` | The four runs' times and exit codes |
| `dry-run.status.txt`, `dry-run.compare.txt` | `rehearsal-2026-11-08/dry_run.sh` from the full clone at `14fbcf05`: 8 of 8 files identical, `compare_dry_run.py` exit 0 |

## How to reproduce

Mutation, in a plain copy (never a worktree with uncommitted work; the script restores each file and checks its hash):

```bash
mkdir C:/t/mut3 && git archive <commit> | tar -x -C C:/t/mut3
python C:/t/mut3/docs/evidence/hardware-reading-vs-level/stage-3-2026-11-09/mutate_stage_3.py \
    --root C:/t/mut3 --python <exact-pin python> --out results.tsv
```

Controls, with a full clone that holds both archive commits:

```bash
bash controls_runs.sh <new commit> <out folder> <full clone> <exact-pin python> <repository with both commits>
```

The dry run: `bash ../rehearsal-2026-11-08/dry_run.sh <commit> <out> <full clone> <python> <fetch source>`.

## What the runs found beyond the criteria

Qubits 148 and 149 carry `ibm_fez`'s dead marker (`x` and `sx` `gate_error` 1, still in the target) in the newest file of
2026-11-09, beside 72. The four controls at the tip are not section 3.9's, because the archive grew from 2,398 to 2,817
files; section 3.9's four were never the frozen ones, and the frozen four come from the freezing ref.
