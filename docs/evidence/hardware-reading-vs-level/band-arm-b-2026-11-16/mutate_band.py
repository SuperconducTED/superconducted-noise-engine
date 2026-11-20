"""Mutation check of the band in Arm B and criterion 4 (PR #140, 2026-11-16).

    python docs/evidence/hardware-reading-vs-level/band-arm-b-2026-11-16/mutate_band.py

Run from the repository root with the pinned interpreter and `PYTHONPATH=.;src` (POSIX: `.:src`).
Each mutant replaces one pattern in `scripts/hardware_reading_vs_level.py`, asserting the pattern
occurs exactly once, runs `tests/test_hardware_reading_vs_level.py`, and restores the file from a
backup copy taken before the first mutant (never from git). A mutant is killed when the tests fail.
Exit 0 when every mutant is killed and the restored file is byte-identical to the backup.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = Path("scripts/hardware_reading_vs_level.py")
TESTS = "tests/test_hardware_reading_vs_level.py"

MUTANTS: list[tuple[str, str, str]] = [
    (
        "ends unsorted",
        "None if a is None or b is None else sorted((float(a), float(b)))",
        "None if a is None or b is None else [float(a), float(b)]",
    ),
    (
        "open interval",
        "None if v is None else int(v[0] <= m <= v[1])",
        "None if v is None else int(v[0] < m < v[1])",
    ),
    (
        "midpoint is the bottom end",
        "None if v is None else (v[0] + v[1]) / 2.0",
        "None if v is None else v[0]",
    ),
    (
        "midpoint is the top end",
        "None if v is None else (v[0] + v[1]) / 2.0",
        "None if v is None else v[1]",
    ),
    (
        "a band built from one end",
        "None if a is None or b is None else sorted((float(a), float(b)))",
        "None if a is None and b is None else sorted((float(a or b or 0.0), float(b or a or 0.0)))",
    ),
    (
        "band dropped from unpredictable",
        '[list(t) for t, v in zip(job.layouts, band["interval"], strict=True) if v is None]',
        "[]",
    ),
    (
        "criterion 4 back to the isinstance check",
        "and all(_scored(arm_b.get(name)) for name in (*SOURCES, BAND))\n"
        "            and isinstance(band, Mapping)\n"
        '            and math.isfinite(float(band.get("coverage", math.nan)))',
        "and all(isinstance(arm_b[name], dict) for name in SOURCES)",
    ),
    (
        "criterion 4 skips the band",
        "for name in (*SOURCES, BAND))",
        "for name in SOURCES)",
    ),
    (
        "criterion 4 ignores the band's coverage",
        '            and math.isfinite(float(band.get("coverage", math.nan)))\n',
        "",
    ),
    (
        "criterion 4 accepts one predicted layout",
        'int(entry.get("n_predicted", 0)) >= 2',
        'int(entry.get("n_predicted", 0)) >= 1',
    ),
    (
        "criterion 4 accepts a NaN Spearman",
        '        and math.isfinite(float(entry.get("spearman", math.nan)))\n',
        "",
    ),
    (
        "coverage over N_LAYOUTS",
        "n_covered / len(mids) if mids else math.nan",
        "n_covered / N_LAYOUTS if mids else math.nan",
    ),
    (
        "best pick by the first layout with a band",
        "int(max(mids, key=lambda i: mids[i]) == best) if mids else None",
        "int(min(mids) == best) if mids else None",
    ),
]


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):  # UTF-8 and LF, as the repository stores text
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    original = TARGET.read_bytes()
    backup = Path(tempfile.mkdtemp()) / TARGET.name
    shutil.copyfile(TARGET, backup)
    text = original.decode("utf-8")
    survived = 0
    try:
        for name, pattern, replacement in MUTANTS:
            count = text.count(pattern)
            assert count == 1, f"{name}: pattern found {count} times"
            TARGET.write_bytes(text.replace(pattern, replacement).encode("utf-8"))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", TESTS, "-q", "-x", "-p", "no:cacheprovider"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            killed = result.returncode != 0
            survived += not killed
            failing = next(
                (line for line in result.stdout.splitlines() if line.startswith("FAILED")), ""
            )
            print(f"{'killed  ' if killed else 'SURVIVED'}  {name}  {failing}".rstrip())
            shutil.copyfile(backup, TARGET)
    finally:
        shutil.copyfile(backup, TARGET)
    restored = TARGET.read_bytes() == original
    print(f"{len(MUTANTS) - survived} of {len(MUTANTS)} killed; file restored: {restored}")
    return 0 if survived == 0 and restored else 1


if __name__ == "__main__":
    raise SystemExit(main())
