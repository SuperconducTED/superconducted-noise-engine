# ruff: noqa: E501
"""Mutation check of #64 PR-A1 step 4 (IntervalBand, interval_band, IntervalCoverage).

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step4_band_and_coverage.py <python exe> <backup dir>      (cwd: the worktree)

Every mutant is one exact, asserted text replacement in
src/superconducted/benchmarks/metrics.py. The file is copied to <backup dir>
first and restored from there after each mutant, never with git. The test
command is tests/test_interval_band.py only.

Predictions, written before the run (K = killed):
  C01 lower edge exclusive ............................ K: inclusive edges, identity, reference value (10 sits on its lower edge)
  C02 upper edge exclusive ............................ K: inclusive edges, identity
  C03 an unseen outcome counts as covered ............. K: unseen outcome
  C04 coverage counts outcomes instead of mass ........ K: reference value (0.75), unseen outcome
  C05 coverage sums normalised probabilities .......... K: identity (sevenths)
  C06 density reference compared after dividing by its trace ... K: identity (state_trace_off) only
  C07 key-length check removed ........................ K: another register
  B01 quantiles taken at (1 - alpha, alpha) ........... K: every central-band test (IntervalBand refuses lower > upper)
  B02 alpha ignored, always min/max ................... K: central band, counterexample, method
  B03 alpha = 0.5 accepted ............................ K: alpha parametrised tests (0.5), IntervalBand (0.5)
  B04 interval_band does not check alpha itself ....... K for some values (numpy or IntervalBand raise other messages); may survive for 0.5
  B05 interval_band's member-count check removed ...... SURVIVES for one member (IntervalBand carries the same check and message); unknown for none
  B06 mixed-mode check removed ........................ K: mixed modes
  B07 same-shape check removed ........................ K: number of qubits
  B08 density bit order reversed ...................... K: bit order
  B09 diagonal not clamped ............................ K: rounding-level negative
  B10 diagonal range check removed .................... K: rounding-level negative (the -1e-6 half)
  B11 imaginary-part check removed .................... K: complex diagonal
  B12 trace check removed ............................. K: trace
  B13 power-of-two check removed ...................... K: not a qubit register
  B14 empty-counts check removed ...................... K: empty member, empty reference
  V01 band arrays not copied .......................... K: copies and freezes
  V02 band arrays not frozen .......................... K: copies and freezes
  V03 lower <= upper check removed .................... K: invalid band
  V04 [0, 1] check removed ............................ K: invalid band
  V05 finite check removed ............................ K: invalid band
  V06 distinct check removed .......................... K: invalid band
  V07 length check removed ............................ K: invalid band
  V08 one-dimensional check removed ................... K: invalid band
  V09 IntervalBand's n_members check removed .......... K: invalid band (n_members = 1)
  V10 method check removed ............................ K: invalid band
  V11 IntervalBand's alpha check removed .............. K: invalid band (alpha)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
SRC = Path("src/superconducted/benchmarks/metrics.py")
backup = backup_dir / "metrics.py.step4.backup"
shutil.copyfile(SRC, backup)
orig = backup.read_text(encoding="utf-8")

QUANT = "    lower, upper = np.quantile(table, [alpha, 1.0 - alpha], axis=0, method=method)  # type: ignore[call-overload]\n"
MUTANTS = {
    "C01": [
        (
            "            if lower <= probability <= upper:\n",
            "            if lower < probability <= upper:\n",
        )
    ],
    "C02": [
        (
            "            if lower <= probability <= upper:\n",
            "            if lower <= probability < upper:\n",
        )
    ],
    "C03": [
        (
            "            upper = float(band.upper[position]) if position is not None else 0.0\n",
            "            upper = float(band.upper[position]) if position is not None else 1.0\n",
        )
    ],
    "C04": [
        (
            "        return math.fsum(covered) / math.fsum(masses.tolist())\n",
            "        return len(covered) / len(keys)\n",
        )
    ],
    "C05": [
        ("                covered.append(mass)\n", "                covered.append(probability)\n"),
        (
            "        return math.fsum(covered) / math.fsum(masses.tolist())\n",
            "        return float(sum(covered))\n",
        ),
    ],
    "C06": [
        (
            "            if lower <= probability <= upper:\n",
            "            if lower <= mass / math.fsum(masses.tolist()) <= upper:\n",
        )
    ],
    "C07": [
        (
            "        if len({len(key) for key in (*band.support, *keys)}) > 1:\n",
            "        if False:\n",
        )
    ],
    "B01": [(QUANT, QUANT.replace("[alpha, 1.0 - alpha]", "[1.0 - alpha, alpha]"))],
    "B02": [(QUANT, QUANT.replace("[alpha, 1.0 - alpha]", "[0.0, 1.0]"))],
    "B03": [("    if not 0.0 <= alpha < 0.5:\n", "    if not 0.0 <= alpha <= 0.5:\n")],
    "B04": [
        (
            "    _check_alpha(alpha)\n    if len({member.counts is not None for member in members}) != 1:\n",
            "    if len({member.counts is not None for member in members}) != 1:\n",
        )
    ],
    "B05": [("    if len(members) < 2:\n", "    if False:\n")],
    "B06": [
        ("    if len({member.counts is not None for member in members}) != 1:\n", "    if False:\n")
    ],
    "B07": [("    if len(shapes) > 1:\n", "    if False:\n")],
    "B08": [
        (
            '    keys = tuple(format(index, f"0{width}b") for index in range(dim))\n',
            '    keys = tuple(format(index, f"0{width}b")[::-1] for index in range(dim))\n',
        )
    ],
    "B09": [("    probabilities = np.clip(real, 0.0, 1.0)\n", "    probabilities = real\n")],
    "B10": [
        (
            "        or real.min() < -_DIAGONAL_TOLERANCE\n        or real.max() > 1.0 + _DIAGONAL_TOLERANCE\n",
            "",
        )
    ],
    "B11": [
        (
            "        np.max(np.abs(np.imag(diagonal))) > _DIAGONAL_TOLERANCE\n        or real.min() < -_DIAGONAL_TOLERANCE\n",
            "        real.min() < -_DIAGONAL_TOLERANCE\n",
        )
    ],
    "B12": [
        ("    if abs(math.fsum(real.tolist()) - 1.0) > _TRACE_TOLERANCE:\n", "    if False:\n")
    ],
    "B13": [("dim < 2 or dim & (dim - 1):\n", "dim < 2:\n")],
    "B14": [("        if total <= 0.0:\n", "        if False:\n")],
    "V01": [
        (
            "        lower = np.array(self.lower, dtype=np.float64)\n        upper = np.array(self.upper, dtype=np.float64)\n",
            "        lower = np.asarray(self.lower, dtype=np.float64)\n        upper = np.asarray(self.upper, dtype=np.float64)\n",
        )
    ],
    "V02": [("        lower.setflags(write=False)\n        upper.setflags(write=False)\n", "")],
    "V03": [("        if np.any(lower > upper):\n", "        if False:\n")],
    "V04": [
        (
            "        if lower.size and (lower.min() < 0.0 or upper.max() > 1.0 or upper.min() < 0.0):\n",
            "        if False:\n",
        )
    ],
    "V05": [
        (
            "        if not (np.all(np.isfinite(lower)) and np.all(np.isfinite(upper))):\n",
            "        if False:\n",
        )
    ],
    "V06": [("        if len(set(support)) != len(support):\n", "        if False:\n")],
    "V07": [("        if not len(support) == lower.size == upper.size:\n", "        if False:\n")],
    "V08": [("        if lower.ndim != 1 or upper.ndim != 1:\n", "        if False:\n")],
    "V09": [("        if self.n_members < 2:\n", "        if False:\n")],
    "V10": [("        if not self.method:\n", "        if False:\n")],
    "V11": [("        _check_alpha(self.alpha)\n", "")],
}

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
    print("baseline:", base.stdout.strip().splitlines()[-1], flush=True)
    for name, edits in MUTANTS.items():
        text = orig
        for old, new in edits:
            assert text.count(old) == 1, (name, old[:70], text.count(old))
            text = text.replace(old, new, 1)
        SRC.write_text(text, encoding="utf-8", newline="\n")
        out = subprocess.run(cmd, capture_output=True, text=True, env=env)
        failed = [
            line.split("::")[1].split(" ")[0]
            for line in out.stdout.splitlines()
            if line.startswith("FAILED")
        ]
        tail = (
            out.stdout.strip().splitlines()[-1]
            if out.stdout.strip()
            else out.stderr.strip().splitlines()[-1]
        )
        print(
            f"{name}: {'KILLED' if out.returncode != 0 else 'SURVIVED'} | {tail.strip('= ')} | {sorted(failed)}",
            flush=True,
        )
        shutil.copyfile(backup, SRC)
finally:
    shutil.copyfile(backup, SRC)
print("restored:", SRC.read_text(encoding="utf-8") == orig)
