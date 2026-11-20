# ruff: noqa: E501
"""Mutation check of the fixes for review 5928253730 on PR #155.

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_review_5928253730.py <python exe> <backup dir>      (cwd: the worktree)

Every mutant is one exact, asserted text replacement. The two source files are copied
to <backup dir> first and restored from there after each mutant, never with git. The
test command is tests/test_interval_band.py and tests/test_perturbation.py.

The fix also replaced the line that step 2's mutants W02 and W03 edit, so those two no
longer apply at this head; R05 to R07 below cover the new line.

Predictions, written before the run (K = killed, the named tests fail):
  R01 the finite-count check removed ....................................... K: non-finite count (both cases)
  R02 the diagonal finiteness check removed ................................ K: non-finite diagonal reference (all four);
                                                                               member nan_imaginary and inf_real (nan_real is
                                                                               still refused, by IntervalBand's own check,
                                                                               whose message also says "must be finite")
  R03 only the real part checked ........................................... K: nan_imaginary and inf_imaginary, member and reference
  R04 only the imaginary part checked ...................................... K: nan_real and inf_real, member and reference
                                                                               (nan_real member as R02)
  R05 the exemption back to isinstance ..................................... K: the identity-subclass test
  R06 the exemption removed (no rng ever required) ......................... K: unseeded refused, identity-subclass test
  R07 rng required even for the identity itself ............................ K: section 1 (no_keyword, none, identity), unseeded refused, identity-subclass test
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
MET = Path("src/superconducted/benchmarks/metrics.py")
AER = Path("src/superconducted/integration/aer_factory.py")
backups = {}
for path in (MET, AER):
    backups[path] = backup_dir / (path.name + ".review.backup")
    shutil.copyfile(path, backups[path])
orig = {path: backups[path].read_text(encoding="utf-8") for path in (MET, AER)}

COUNTS = "        if not np.all(np.isfinite(masses)):\n"
DIAG = "    if not (np.all(np.isfinite(np.real(diagonal))) and np.all(np.isfinite(np.imag(diagonal)))):\n"
EXEMPT = "        if rng is None and type(self._perturbation) is not IdentityPerturbation:\n"
MUTANTS = {
    "R01": (MET, [(COUNTS, "        if False:\n")]),
    "R02": (MET, [(DIAG, "    if False:\n")]),
    "R03": (MET, [(DIAG, "    if not np.all(np.isfinite(np.real(diagonal))):\n")]),
    "R04": (MET, [(DIAG, "    if not np.all(np.isfinite(np.imag(diagonal))):\n")]),
    "R05": (
        AER,
        [
            (
                EXEMPT,
                "        if rng is None and not isinstance(self._perturbation, IdentityPerturbation):\n",
            )
        ],
    ),
    "R06": (AER, [(EXEMPT, "        if False:\n")]),
    "R07": (AER, [(EXEMPT, "        if rng is None:\n")]),
}

env = {**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
cmd = [
    py,
    "-m",
    "pytest",
    "tests/test_interval_band.py",
    "tests/test_perturbation.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=no",
    "-rf",
]
try:
    base = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print("baseline:", base.stdout.strip().splitlines()[-1])
    for name, (path, edits) in MUTANTS.items():
        text = orig[path]
        for old, new in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8", newline="\n")
        out = subprocess.run(cmd, capture_output=True, text=True, env=env)
        failed = sorted(
            {
                line.split("::")[1].split(" ")[0]
                for line in out.stdout.splitlines()
                if line.startswith("FAILED")
            }
        )
        tail = (
            out.stdout.strip().splitlines()[-1]
            if out.stdout.strip()
            else out.stderr.strip().splitlines()[-1]
        )
        print(f"{name}: {'KILLED' if out.returncode != 0 else 'SURVIVED'} | {tail.strip('= ')}")
        for case in failed:
            print(f"    {case}")
        shutil.copyfile(backups[path], path)
finally:
    for path in (MET, AER):
        shutil.copyfile(backups[path], path)
print("restored:", all(path.read_text(encoding="utf-8") == orig[path] for path in (MET, AER)))
