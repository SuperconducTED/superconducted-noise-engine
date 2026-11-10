"""#61, PR #143 review item 5: apply one mutant at a time, run the tests, restore.

Usage, from the repository root:
    PYTHONPATH=src python docs/evidence/adr-011-type-reduction/mutate.py all

Each mutant is an exact text replacement in scripts/type_reduction_discrepancy.py. The file
is copied to a backup first and restored from that copy after every run (never from git),
and its SHA-256 is checked against the original before the next mutant. A mutant is KILLED
when the test file fails, SURVIVED when it passes. A replacement that does not match exactly
once aborts the run: a mutant that was never applied must not be reported as a survivor.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

TARGET = Path("scripts/type_reduction_discrepancy.py")
TESTS = "tests/test_type_reduction.py"

MUTANTS: dict[str, tuple[str, str]] = {
    "M1 route_gap=0.0": (
        "route_gap=max(abs(km.y_l - exhaustive_l), abs(km.y_r - exhaustive_r)),",
        "route_gap=0.0,",
    ),
    "M2 output column 0": (
        "values = firing.consequent_outputs[:, o]",
        "values = firing.consequent_outputs[:, 0]",
    ),
    "M3 mean and median swapped": (
        "        repr(float(values.mean())),\n        repr(float(np.median(values))),",
        "        repr(float(np.median(values))),\n        repr(float(values.mean())),",
    ),
    "M4 p90 is the median": (
        "repr(float(np.percentile(values, 90))),",
        "repr(float(np.percentile(values, 50))),",
    ),
    "M5 Db clip removed": (
        "by_band.append(min(d / width, 0.5))",
        "by_band.append(d / width)",
    ),
    "M6 degenerate tolerance 0": (
        "if width <= m.tolerance:",
        "if width <= 0.0:",
    ),
    "M7 degenerate tolerance x1000": (
        "if width <= m.tolerance:",
        "if width <= 1000 * m.tolerance:",
    ),
    "M8 left guard returns the worse value": (
        "return y, passes, y_next > y",
        "return y_next, passes, y_next > y",
    ),
    "M8b right guard returns the worse value": (
        "return y, passes, y_next < y",
        "return y_next, passes, y_next < y",
    ),
    "M9 distances from the iterative route": (
        "y_l=exhaustive_l,\n        y_r=exhaustive_r,",
        "y_l=km.y_l,\n        y_r=km.y_r,",
    ),
    "M10 no rescale in _weighted_average": (
        "    scale = float(weights.max())\n",
        "    scale = 1.0\n",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(labels: list[str]) -> int:
    chosen = list(MUTANTS) if labels == ["all"] else labels
    original = sha(TARGET)
    backup = TARGET.with_suffix(".py.mutbak")
    shutil.copyfile(TARGET, backup)
    results = []
    try:
        for label in chosen:
            old, new = MUTANTS[label]
            text = TARGET.read_text(encoding="utf-8")
            if text.count(old) != 1:
                results.append((label, f"NOT APPLIED (pattern found {text.count(old)} times)"))
                continue
            TARGET.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
            run = subprocess.run(
                [sys.executable, "-m", "pytest", TESTS, "-q", "-x", "-p", "no:cacheprovider"],
                capture_output=True,
                text=True,
            )
            shutil.copyfile(backup, TARGET)
            if sha(TARGET) != original:
                raise RuntimeError(f"restore failed after {label}")
            last = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
            verdict = "KILLED" if run.returncode != 0 else "SURVIVED"
            results.append((label, f"{verdict}  ({last})"))
    finally:
        shutil.copyfile(backup, TARGET)
        backup.unlink()
    print(f"target {TARGET}, sha256 {original[:16]}, tests {TESTS}")
    for label, outcome in results:
        print(f"{label:42} {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
