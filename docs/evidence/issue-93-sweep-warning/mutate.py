# ruff: noqa: E501
"""Mutation check for #93's two tests. Run from the repository root with PYTHONPATH=src:

    python docs/evidence/issue-93-sweep-warning/mutate.py <backup path outside the repository>

Each mutant is one exact replacement in scripts/file_snapshots.sh (asserted to match once), the
file is restored from a backup outside the repository after every run, never from git, and its
SHA-256 is checked. Predictions (the implementation doc's prediction 3): every mutant is KILLED,
M1 and M2 by the sweep test, M3 and M4 by the live test.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

TARGET = Path("scripts/file_snapshots.sh")
BACKUP = Path(sys.argv[1])
TESTS = [
    "tests/test_file_snapshots.py::TestFileSnapshots::"
    "test_a_sweep_behind_the_index_prints_one_line_and_owes_no_rebuild",
    "tests/test_file_snapshots.py::TestFileSnapshots::"
    "test_a_live_poll_behind_the_index_still_warns_without_a_rebuild",
]
MUTANTS = {
    "M1 summary printed per row": (
        '  echo "$stem: $decision"\ndone\n',
        '  echo "$stem: $decision"\n'
        '  if [ "$behind" -gt 0 ]; then echo "$behind filed behind the newest indexed row"; fi\n'
        "done\n",
    ),
    "M2 the sweep line is a warning": (
        '  echo "$behind $noun filed behind',
        '  echo "::warning::$behind $noun filed behind',
    ),
    "M3 the live warning dropped": (
        '          echo "::warning::$stem predates the newest indexed document ($index_max) on a live" \\\n'
        '               "poll, which should not happen; check what the endpoint served. Nothing to rebuild."\n',
        "          :\n",
    ),
    "M4 rebuild=true back in the live warning": (
        "check what the endpoint served. Nothing to rebuild.",
        "Dispatch Calibration Pipeline Health with backfill=true rebuild=true.",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


original = sha(TARGET)
shutil.copyfile(TARGET, BACKUP)
try:
    for label, (old, new) in MUTANTS.items():
        text = TARGET.read_text(encoding="utf-8")
        if text.count(old) != 1:
            print(f"{label}: NOT APPLIED (pattern found {text.count(old)} times)")
            continue
        TARGET.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        run = subprocess.run(
            [sys.executable, "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider", "-rf"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        shutil.copyfile(BACKUP, TARGET)
        if sha(TARGET) != original:
            raise RuntimeError(f"restore failed after {label}")
        failed = [
            ln.split("::")[-1].split(" ")[0]
            for ln in run.stdout.splitlines()
            if ln.startswith("FAILED")
        ]
        verdict = "KILLED" if run.returncode != 0 else "SURVIVED"
        print(f"{label}: {verdict} by {failed or '-'}")
finally:
    shutil.copyfile(BACKUP, TARGET)
print("restored:", sha(TARGET) == original)
