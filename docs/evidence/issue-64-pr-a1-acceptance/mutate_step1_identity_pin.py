# ruff: noqa: E501
"""Mutation check of #64 PR-A1 step 1 (the identity pin), on the tree it was written for.

    python <path to this file> <python exe> <backup dir>
    (cwd: a checkout of commit 75b86dbb, where the ensemble's wiring is still main's)

The two mutants edit the old ``__iter__``, which step 2 replaced, so this
script cannot run on the branch's head. Each mutant is applied to
``src/superconducted/integration/aer_factory.py``; the file is copied to
<backup dir> first and restored from there after each run, never with git.

Predictions, written before the first run:
  M1 every model's crisp params scaled by 1 + 1e-6: the literal pin fails; the
     relational pin passes, because the change hits both sides of it.
  M2 members 1 and later scaled by 1 + 1e-6: the relational pin, the literal
     pin and the density-matrix pin fail; the two-pass test stays green.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
SRC = Path("src/superconducted/integration/aer_factory.py")
backup = backup_dir / "aer_factory.py.step1.backup"
shutil.copyfile(SRC, backup)
orig = backup.read_text(encoding="utf-8")

M2_TAIL = "                gate_eligibility_policy=self._gate_eligibility_policy,\n            )\n\n    def __len__"
MUTANTS = {
    "M1": [
        (
            "        return self._squashing.squash(raw)\n",
            "        return self._squashing.squash(raw) * (1.0 + 1e-6)\n",
        )
    ],
    "M2": [
        (
            "        for _ in range(self._size):\n            yield FuzzyNoiseModel(\n",
            "        for _i in range(self._size):\n            _m = FuzzyNoiseModel(\n",
        ),
        (
            M2_TAIL,
            "                gate_eligibility_policy=self._gate_eligibility_policy,\n            )\n"
            "            if _i > 0:\n                _m._crisp_params = _m._crisp_params * (1.0 + 1e-6)\n"
            "            yield _m\n\n    def __len__",
        ),
    ],
}

env = {**os.environ, "PYTHONPATH": "src"}
cmd = [
    py,
    "-m",
    "pytest",
    "tests/test_perturbation.py",
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
    for name, edits in MUTANTS.items():
        text = orig
        for old, new in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
            text = text.replace(old, new, 1)
        SRC.write_text(text, encoding="utf-8", newline="\n")
        out = subprocess.run(cmd, capture_output=True, text=True, env=env)
        failed = sorted(
            line.split("::")[1].split(" ")[0]
            for line in out.stdout.splitlines()
            if line.startswith("FAILED")
        )
        print(
            f"{name}: {'KILLED' if out.returncode else 'SURVIVED'} | {out.stdout.strip().splitlines()[-1].strip('= ')} | {failed}"
        )
        shutil.copyfile(backup, SRC)
finally:
    shutil.copyfile(backup, SRC)
print("restored:", SRC.read_text(encoding="utf-8") == orig)
