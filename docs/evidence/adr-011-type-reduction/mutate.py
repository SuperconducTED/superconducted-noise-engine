"""#61, PR #143 review item 5: apply one mutant at a time, run the tests, restore.

Usage, from the repository root:
    PYTHONPATH=src python docs/evidence/adr-011-type-reduction/mutate.py all

Each mutant is an exact text replacement in scripts/type_reduction_discrepancy.py, or, since
2026-11-13, in the file OTHER_TARGETS names for it. The file is copied to a backup first and
restored from that copy after every run (never from git), and its SHA-256 is checked against
the original before the next mutant. A mutant is KILLED when the test file fails, SURVIVED
when it passes; a killed mutant's line names the first test that failed. A replacement that
does not match exactly once is reported as NOT APPLIED (until 2026-11-13 this said "aborts the
run", which the code never did): a mutant that was never applied must not be reported as a
survivor.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

TARGET = Path("scripts/type_reduction_discrepancy.py")
COMPARE = Path("docs/evidence/adr-011-type-reduction/compare_sweep.py")
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
    # Second review of 2026-11-11 (5854006318), items a and b.
    "M11 column reports the smallest gap": (
        "repr(max((_gap_over_tolerance(m) for m in kept), default=0.0)),",
        "repr(min((_gap_over_tolerance(m) for m in kept), default=0.0)),",
    ),
    "M12 compare_sweep back to 1b8f6089's filtered read": (
        '    missing = sum(a.get(GAP_OVER_TOLERANCE) in (None, "") for a in new)\n'
        "    if missing:\n"
        '        print(f"FAIL: {GAP_OVER_TOLERANCE} absent or empty in {missing} of {len(new)} rows'
        ' of the")\n'
        '        print("new file; it must come from a sweep that writes the column")\n'
        "        return 1\n"
        "    over = [float(a[GAP_OVER_TOLERANCE]) for a in new]\n",
        "    over = [\n"
        '        float(a[GAP_OVER_TOLERANCE]) for a in new if a.get(GAP_OVER_TOLERANCE, "") != ""\n'
        "    ]\n",
    ),
}

# Mutants of a file other than TARGET. M12 puts back the read of the column that 1b8f6089 had,
# which skipped rows without it (second review, item b), so a file without the column passes again.
OTHER_TARGETS: dict[str, Path] = {
    "M12 compare_sweep back to 1b8f6089's filtered read": COMPARE,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_failure(stdout: str) -> str:
    """The first test pytest's short summary reports as failed or in error."""
    for line in stdout.splitlines():
        if line.startswith(("FAILED ", "ERROR ")):
            return line.split()[1].split("::")[-1]
    return "?"


def main(labels: list[str]) -> int:
    chosen = list(MUTANTS) if labels == ["all"] else labels
    targets = sorted({OTHER_TARGETS.get(label, TARGET) for label in chosen}, key=str)
    original = {target: sha(target) for target in targets}
    backups = {target: target.with_suffix(".py.mutbak") for target in targets}
    for target in targets:
        shutil.copyfile(target, backups[target])
    results = []
    try:
        for label in chosen:
            old, new = MUTANTS[label]
            target = OTHER_TARGETS.get(label, TARGET)
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                results.append((label, f"NOT APPLIED (pattern found {text.count(old)} times)"))
                continue
            target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
            run = subprocess.run(
                [sys.executable, "-m", "pytest", TESTS, "-q", "-x", "-p", "no:cacheprovider"],
                capture_output=True,
                text=True,
            )
            shutil.copyfile(backups[target], target)
            if sha(target) != original[target]:
                raise RuntimeError(f"restore failed after {label}")
            last = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
            if run.returncode != 0:
                outcome = f"KILLED  ({last}) by {first_failure(run.stdout)}"
            else:
                outcome = f"SURVIVED  ({last})"
            results.append((label, outcome))
    finally:
        for target in targets:
            shutil.copyfile(backups[target], target)
            backups[target].unlink()
    for target in targets:
        print(f"target {target}, sha256 {original[target][:16]}")
    print(f"tests {TESTS}")
    for label, outcome in results:
        print(f"{label:52} {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
