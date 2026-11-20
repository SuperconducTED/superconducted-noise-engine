# ruff: noqa: E501
"""Mutation check of #64 PR-A1 step 5 (the to_dict once-per-run guard).

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step5_guard.py <python exe> <dir holding aer_mutant_plugin.py>     (cwd: the worktree)

The thing under guard is Aer, not project code, so the mutants change Aer's
behaviour for one test session through a pytest plugin. No file is edited.

Predictions, written before the run:
  none      baseline: 13 passed.
  extra     one more serialisation per run. Killed by the four one-serialisation
            cases, the two shots-independence cases, the three harness cases and
            the harness error case (10 of 13). The three tests of section 1 pass:
            they do not run a noise model through Aer.
  per_shot  one more serialisation per shot. Killed by the same ten.
"""

import os
import subprocess
import sys

py, plugin_dir = sys.argv[1], sys.argv[2]
for mode in ("", "extra", "per_shot"):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(["src", plugin_dir]), "AER_MUTANT": mode}
    out = subprocess.run(
        [
            py,
            "-m",
            "pytest",
            "tests/test_aer_serialises_once.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "aer_mutant_plugin",
            "--no-header",
            "-rf",
            "--tb=no",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    failed = sorted(
        line.split("::")[1].split(" ")[0]
        for line in out.stdout.splitlines()
        if line.startswith("FAILED")
    )
    tail = (
        out.stdout.strip().splitlines()[-1].strip("= ")
        if out.stdout.strip()
        else out.stderr.strip()[-300:]
    )
    print(
        f"{mode or 'none':9s} {'KILLED' if out.returncode else 'passed'} | {tail} | {len(failed)} failed"
    )
    for name in failed:
        print("          ", name)
