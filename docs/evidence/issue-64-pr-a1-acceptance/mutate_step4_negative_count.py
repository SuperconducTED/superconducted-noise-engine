# ruff: noqa: E501
"""Mutant N01 for step 4: the negative-count refusal removed.

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step4_negative_count.py <python exe> <backup dir>      (cwd: the worktree)

Prediction: killed by both negative-count tests. Without the refusal the band
test meets IntervalBand's [0, 1] error (another message) and the coverage test
gets 1.2 back with no error.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
SRC = Path("src/superconducted/benchmarks/metrics.py")
backup = backup_dir / "metrics.py.step4neg.backup"
shutil.copyfile(SRC, backup)
orig = backup.read_text(encoding="utf-8")
old = "        if masses.size and masses.min() < 0.0:\n"
env = {**os.environ, "PYTHONPATH": "src"}
cmd = [
    py,
    "-m",
    "pytest",
    "tests/test_interval_band.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--no-header",
    "-rf",
    "--tb=no",
]
try:
    base = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print("baseline:", base.stdout.strip().splitlines()[-1].strip("= "))
    assert orig.count(old) == 1
    SRC.write_text(orig.replace(old, "        if False:\n", 1), encoding="utf-8", newline="\n")
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    failed = [
        line.split("::")[1].split(" ")[0]
        for line in out.stdout.splitlines()
        if line.startswith("FAILED")
    ]
    print(
        "N01:",
        "KILLED" if out.returncode else "SURVIVED",
        "|",
        out.stdout.strip().splitlines()[-1].strip("= "),
        "|",
        sorted(failed),
    )
finally:
    shutil.copyfile(backup, SRC)
print("restored:", SRC.read_text(encoding="utf-8") == orig)
