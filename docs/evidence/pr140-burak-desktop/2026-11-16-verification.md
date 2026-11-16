# PR #140 desktop verification after the Arm B band fix

Tested tree: `4cb01d19a078e54e282b0be37978e712ee9c3f2c`; merge base with `main`:
`5c98f264dee8292e4b07de4e9074e833c487d9cb`. This run tests the code after the band fix, unlike
the [2026-11-09 run](2026-11-09-verification.md). The reference is
[`dry-run-2026-11-16`](../hardware-reading-vs-level/dry-run-2026-11-16/).

## Environment

WSL2, Linux `6.18.58.1-microsoft-standard-WSL2`, AMD Ryzen 5 5500, 12 logical CPUs, Python
3.12.3, 7.7 GiB RAM and 6.0 GiB available at the start. Both pinned archive commits were already
available locally. The worktree was clean before and after the run, and the PR changes no `src`
files.

The existing environment had `python-dotenv` 1.1.1 instead of the required 1.2.2. A separate
session virtual environment supplied 1.2.2, with the existing environment's packages on
`PYTHONPATH`; the existing environment was not modified. All runtime and development pins in
`requirements-dev.txt` were checked individually and matched; `pip check` passed.

The run used a user-systemd scope with `MemoryMax=6G`, `MemorySwapMax=512M` and `nice -n 10`
to limit impact on the shared machine. These limits did not change the simulation inputs.
No QPU was contacted.

## Results

| Check | Result |
| --- | --- |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | Passed; 105 files already formatted |
| `python -m mypy --strict` | Passed; 49 source files |
| `python scripts/check_ids.py` | Passed |
| `python -m pytest -q` | 1,104 passed; no skips or failures |
| Controls | Exit 0 in 5m 26.90s; `controls.json` byte-identical to reference |
| Two-truth dry run | Exit 0 in 27m 30.57s; both truths pass all five criteria |
| Reference comparison | Exit 0; all 15 MUST MATCH rows hold |
| Arm B band | Independent calculation agrees with the new TSVs, criteria and reference within `1e-9` |

The controls file's SHA-256 is
`b90a2f7a8a985e5e8ae4abe14f2bffd31f16fafa398533abcdad867375b2fdcd`. The dry-run
process's maximum resident set size was 979,664 KiB, and `time` reported no swaps.

All four TSVs and `selection.json` are byte-identical to the Windows reference. `manifest.json`
differs only in `versions`. The criteria files differ in 13 floating-point values; recursive
comparison found all other values identical, with maximum absolute difference
`4.3520742565306136e-14`. No pass/fail, integer or other value differs.

The independent band calculation used `expected_band` from
[`band_rerun.py`](../hardware-reading-vs-level/band-arm-b-2026-11-16/band_rerun.py), which
does not import the implementation. It checked the four new per-layout TSV columns, the five
aggregate band scores and the empty `unpredictable.band` list against the desktop data, and
compared the aggregate scores to the reference:

| | Truth 1 | Truth 2 |
| --- | --- | --- |
| Band coverage | 5/6 | 6/6 |
| Midpoint Spearman | 0.3714285714 | 0.8285714286 |
| Best-pick hit | 0 | 0 |

## Commands and evidence

`$TREE` denotes the clean worktree at the tested SHA, `$PY` the session interpreter, and `$OUT`
a directory outside the worktree. The archive refs and times below are the reference inputs.
For both long commands, `$PY` was run under the resource-limited scope described above and
`/usr/bin/time -v`.

```bash
cd "$TREE"
"$PY" -m scripts.hardware_test_predictors --repo . \
  --ref 5828b4a29fabc245aa096e530852249a3496dc5b \
  --at 2026-10-23T09:34:56Z --mode controls --out "$OUT/freeze"
cp "$OUT/freeze/controls.json" "$OUT/dry-run/controls.json"
"$PY" -m scripts.hardware_reading_vs_level --repo . \
  --ref 5828b4a29fabc245aa096e530852249a3496dc5b \
  --at 2026-10-23T09:34:56Z \
  --execution-ref 84ba0230738c9ee2773616b4e4c7142ba91180e3 \
  --controls "$OUT/dry-run/controls.json" --out "$OUT/dry-run"
python3 docs/evidence/hardware-reading-vs-level/compare_dry_run.py \
  docs/evidence/hardware-reading-vs-level/dry-run-2026-11-16 "$OUT/dry-run"
```

Outputs and transcripts are in [2026-11-16-verification/](2026-11-16-verification/). The
machine-specific local paths in the test and timing logs have been omitted; the outputs and
timing figures are otherwise unchanged. The run is pipeline acceptance on Aer, not a device
measurement, and supports no claim about `ibm_fez` hardware performance.
