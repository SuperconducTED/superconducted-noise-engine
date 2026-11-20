# ruff: noqa: E501
"""Mutation check of #64 PR-A1 step 3 (InputVectorPerturbation, OffsetFeatureExtractor).

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step3_input_jitter.py <python exe> <backup dir>      (cwd: the worktree)

Every mutant is one exact, asserted text replacement in
src/superconducted/integration/perturbation.py. The file is copied to
<backup dir> first and restored from there after each mutant, never with git.
The test command is tests/test_perturbation.py only. Two controls at the end
compute, without pytest, the arithmetic behind the two mutants predicted
equivalent.

Predictions, written before the run (K = killed, the named tests fail; E = equivalent, survives):
  V01 clip into the bounds and keep the first attempt ...................... K: redrawn-not-clipped, open end, real generator, truncated normal
  V02 one attempt fewer ..................................................... K: exhausted redraws (both cases)
  V03 one attempt more ...................................................... K: exhausted redraws (draw not scripted)
  V04 an open low end treated as closed ..................................... K: bound edges, open end, centre t1_zero
  V05 a closed high end treated as open ..................................... K: bound edges, open end (closed edge kept)
  V06 the finiteness rule in contains removed ............................... K: bound edges (closed infinite end); the shipped bounds alone would not see it
  V07 the centre check removed .............................................. K: centre refused (all six)
  V08 the member extractor's equality guard removed ......................... K: refuses another snapshot, ensemble over another snapshot
  V09 offset as (center + scale z) - center, the plan's x_i - x ............. K: redrawn-not-clipped, real generator (offset no longer bit for bit scale z)
  V10 only the out-of-bounds components redrawn ............................. K: redrawn-not-clipped, real generator
  V11 the r <= 0 refusal removed ............................................ K: relative refuses r (0, 0.0, -0.1)
  V12 an unknown feature name accepted in bounds_for ......................... K: bounds table, relative needs known names (KeyError, not ValueError)
  V13 the feature-name check in perturb removed ............................. K: perturb refuses names
  V14 the output_dim check in perturb removed ............................... K: perturb refuses shape, but only by its message; the member extractor's own check still refuses
  V15 centre and scale no longer copied ..................................... K: copies and read-only
  V16 the arrays left writeable ............................................. K: copies and read-only, member extractor read-only
  V17 a negative scale accepted ............................................. K: constructor refuses (negative)
  V18 relative's scale as r * x, without abs ................................ E: every admissible centre is >= 0 (control 1)
  V19 low <= high not checked ............................................... K: bound edges (FeatureBound(1, 0))
  V20 max_redraws not validated ............................................. K: constructor refuses (three redraw cases)
  V21 extract returns center + offset, ignoring the wrapped output .......... E: the guard has already made them equal (control 2)
  V22 the member extractor's size check removed ............................. K: directly built member extractor
  V23 the member extractor's offset shape check removed ..................... K: directly built member extractor
  V24 relative's type and finiteness check on r removed ...................... K: relative refuses r (nan, inf, True, "0.1")
  V25 the base extractor returned instead of the member ..................... K: every test through _jitter, members differ
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

py, backup_dir = sys.argv[1], Path(sys.argv[2])
PER = Path("src/superconducted/integration/perturbation.py")
backup = backup_dir / (PER.name + ".step3.backup")
shutil.copyfile(PER, backup)
orig = backup.read_text(encoding="utf-8")

LOOP = "        for _ in range(self._max_redraws + 1):\n"
DRAW = "            offset = self._scale * rng.standard_normal(d)\n"
CAND = "            candidate = self._center + offset\n"
TEST = "            if all(self._bounds[j].contains(float(candidate[j])) for j in range(d)):\n"
MUTANTS: dict[str, list[tuple[str, str]]] = {
    "V01": [
        (
            CAND + TEST,
            "            candidate = np.clip(\n"
            "                self._center + offset,\n"
            "                [b.low for b in self._bounds],\n"
            "                [b.high for b in self._bounds],\n"
            "            )\n"
            "            offset = candidate - self._center\n"
            "            if True:\n",
        )
    ],
    "V02": [(LOOP, "        for _ in range(self._max_redraws):\n")],
    "V03": [(LOOP, "        for _ in range(self._max_redraws + 2):\n")],
    "V04": [
        (
            "        above_low = value > self.low if self.low_open else value >= self.low\n",
            "        above_low = value >= self.low\n",
        )
    ],
    "V05": [
        (
            "        below_high = value < self.high if self.high_open else value <= self.high\n",
            "        below_high = value < self.high\n",
        )
    ],
    "V06": [
        (
            "        if not math.isfinite(value):\n            return False\n",
            "        if False:\n            return False\n",
        )
    ],
    "V07": [("        if outside:\n", "        if False:\n")],
    "V08": [
        (
            "        if values.shape != self._center.shape or not np.array_equal(values, self._center):\n",
            "        if False:\n",
        )
    ],
    "V09": [
        (
            DRAW + CAND,
            "            candidate = self._center + self._scale * rng.standard_normal(d)\n"
            "            offset = candidate - self._center\n",
        )
    ],
    "V10": [
        (
            LOOP + DRAW + CAND + TEST,
            "        z = rng.standard_normal(d)\n"
            + LOOP
            + "            offset = self._scale * z\n"
            + CAND
            + "            bad = [j for j in range(d) if not self._bounds[j].contains(float(candidate[j]))]\n"
            "            if bad:\n"
            "                z[bad] = rng.standard_normal(len(bad))\n"
            "            if not bad:\n",
        )
    ],
    "V11": [("        if r <= 0:\n", "        if False:\n")],
    "V12": [("    if unknown:\n", "    if False:\n")],
    "V13": [
        (
            "            self._feature_names is not None\n            and tuple",
            "            False\n            and tuple",
        )
    ],
    "V14": [("        if feature_extractor.output_dim != d:\n", "        if False:\n")],
    "V15": [
        (
            "    array = np.array(values, dtype=np.float64, copy=True)\n",
            "    array = np.asarray(values, dtype=np.float64)\n",
        )
    ],
    "V16": [("    array.flags.writeable = False\n", "    array.flags.writeable = True\n")],
    "V17": [
        (
            "        if not np.all(np.isfinite(self._scale)) or np.any(self._scale < 0):\n",
            "        if not np.all(np.isfinite(self._scale)):\n",
        )
    ],
    "V18": [("            float(r) * np.abs(center),\n", "            float(r) * center,\n")],
    "V19": [
        (
            "        if math.isnan(self.low) or math.isnan(self.high) or not self.low <= self.high:\n",
            "        if math.isnan(self.low) or math.isnan(self.high):\n",
        )
    ],
    "V20": [
        (
            "        if isinstance(max_redraws, bool) or not isinstance(max_redraws, int) or max_redraws < 0:\n",
            "        if False:\n",
        )
    ],
    "V21": [
        ("        return values + self._offset\n", "        return self._center + self._offset\n")
    ],
    "V22": [("        if self._center.size != wrapped.output_dim:\n", "        if False:\n")],
    "V23": [("        if self._offset.shape != self._center.shape:\n", "        if False:\n")],
    "V24": [
        (
            "        if isinstance(r, bool) or not isinstance(r, (int, float)) or not math.isfinite(r):\n",
            "        if False:\n",
        )
    ],
    "V25": [
        (
            "                return member, rule_base, defuzzifier\n",
            "                return feature_extractor, rule_base, defuzzifier\n",
        )
    ],
}

env = {**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
cmd = [py, "-m", "pytest", "tests/test_perturbation.py", "-q", "-p", "no:cacheprovider", "--tb=no"]
try:
    base = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print("baseline:", base.stdout.strip().splitlines()[-1])
    for name, edits in MUTANTS.items():
        text = orig
        for old, new in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
            text = text.replace(old, new, 1)
        PER.write_text(text, encoding="utf-8", newline="\n")
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
            f"{name}: {'KILLED' if out.returncode != 0 else 'SURVIVED'} | {tail.strip('= ')} | {sorted({f.split('[')[0] for f in failed})}"
        )
        shutil.copyfile(backup, PER)
finally:
    shutil.copyfile(backup, PER)
print("restored:", PER.read_text(encoding="utf-8") == orig)

# Control 1 (V18). relative's centre is checked against bounds_for's bounds, whose low ends
# are all 0, so every admissible component is >= 0 and r * |x| equals r * x, up to the sign
# of a zero. Measured on 100,000 admissible vectors, with a positive control: the same
# comparison on vectors with one negative component (which no bound admits) must differ.
rng = np.random.default_rng(64)
n = 100_000
x = np.column_stack(
    [
        10.0 ** rng.uniform(-6, -3, n),
        10.0 ** rng.uniform(-6, -3, n),
        np.where(rng.random(n) < 0.01, rng.choice([0.0, -0.0, 1.0], n), rng.random(n)),
    ]
)
r = 10.0 ** rng.uniform(-3, 1, n)[:, None]
a, b = r * np.abs(x), r * x
print("control 1: admissible vectors where r*|x| and r*x differ as values:", int(np.sum(a != b)))
print(
    "control 1: of those that differ only in the sign of a zero:",
    int(np.sum((a == b) & (np.signbit(a) != np.signbit(b)))),
)
z = rng.standard_normal(x.shape)
print(
    "control 1: members (center + scale z) that differ as values:",
    int(np.sum((x + a * z) != (x + b * z))),
)
neg = x.copy()
neg[:, 0] = -neg[:, 0]
print(
    "control 1, positive: vectors with a negative T1 where they differ (must be > 0):",
    int(np.sum(r * np.abs(neg) != r * neg)),
)

# Control 2 (V21). After the guard, the wrapped vector equals the centre element for element,
# so values + offset and center + offset are equal as values; the only possible difference is
# -0.0 against 0.0 in a component whose offset is also a zero. Positive control: a wrapped
# vector one ulp away, which the guard refuses, does give a different sum.
values = np.where(x == 0.0, -x, x)  # equal to x element for element; every zero has the other sign
assert np.array_equal(values, x)
offset = a * z
print(
    "control 2: wrapped vectors equal to the centre with a flipped zero:",
    int(np.sum(np.signbit(values) != np.signbit(x))),
)
print("control 2: members that differ as values:", int(np.sum((values + offset) != (x + offset))))
nudged = np.nextafter(x, np.inf)
print(
    "control 2, positive: one ulp away, differing sums (must be > 0):",
    int(np.sum((nudged + offset) != (x + offset))),
)
