# ruff: noqa: E501
"""One more mutant for step 4, after C05's prediction missed.

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step4_c05b.py <python exe> <backup dir>      (cwd: the worktree)

C05 summed the covered probabilities with Python's built-in ``sum``, which on
Python 3.12 is a compensated sum for floats, so seven sevenths still gave 1.0
and the "sevenths" identity case did not fail. C05b is the mutant that was
meant: a plain ``numpy.sum``. Prediction: killed by identity[sevenths].
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
SRC = Path("src/superconducted/benchmarks/metrics.py")
backup = backup_dir / "metrics.py.step4b.backup"
shutil.copyfile(SRC, backup)
orig = backup.read_text(encoding="utf-8")
edits = [
    ("                covered.append(mass)\n", "                covered.append(probability)\n"),
    (
        "        return math.fsum(covered) / math.fsum(masses.tolist())\n",
        "        return float(np.sum(covered))\n",
    ),
]
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
    text = orig
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    SRC.write_text(text, encoding="utf-8", newline="\n")
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    failed = [
        line.split("::")[1].split(" ")[0]
        for line in out.stdout.splitlines()
        if line.startswith("FAILED")
    ]
    print(
        "C05b:",
        "KILLED" if out.returncode else "SURVIVED",
        "|",
        out.stdout.strip().splitlines()[-1].strip("= "),
        "|",
        sorted(failed),
    )
finally:
    shutil.copyfile(backup, SRC)
print("restored:", SRC.read_text(encoding="utf-8") == orig)
