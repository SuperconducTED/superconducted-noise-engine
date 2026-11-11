# ruff: noqa: E501
"""Mutation check of #64 PR-A1 step 2 (interface, identity, ensemble seeding).

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step2_seeding.py <python exe> <backup dir>      (cwd: the worktree)

Every mutant is one exact, asserted text replacement. The two source files are
copied to <backup dir> first and restored from there after each mutant, never
with git. The test command is tests/test_perturbation.py only.

Predictions, written before the run (K = killed, the named test fails):
  W01 stored Generators (Generator.spawn) instead of seed sequences ...... K: iterating twice
  W02 the unseeded raise removed .......................................... K: unseeded refused
  W03 the unseeded raise also fires for the identity ...................... K: section 1, no_keyword
  W04 member i perturbed from member i-1's extractor ...................... K: base objects
  W05 the returned tuple ignored, members built from the base ............. K: members differ
  W06 the caller's generator handed to perturb ............................ K: spawned children, stream untouched
  W07 every member seeded from child 0 .................................... K: own stream
  W08 feature_names check removed ......................................... K: contract (feature_names)
  W09 extractor output_dim check removed .................................. K: contract (extractor_output_dim)
  W10 rule base input_dim check removed ................................... unknown: tsk.py may raise its own
                                                                            ValueError naming input_dim
  W11 rule base output_dim check removed .................................. K: contract (rule_base_output_dim)
  W12 children spawned from a fresh unseeded generator .................... K: spawned children, two constructions
  W13 index 0 passed for every member ..................................... K: index
  W14 the identity draws once from rng .................................... K: identity draws nothing
  W15 one child too many spawned and the first skipped .................... K: spawned children
  W16 the no-spawn check removed .......................................... K: no-spawn refused
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

py, backup_dir = sys.argv[1], Path(sys.argv[2])
AER = Path("src/superconducted/integration/aer_factory.py")
PER = Path("src/superconducted/integration/perturbation.py")
backups = {}
for path in (AER, PER):
    backups[path] = backup_dir / (path.name + ".step2.backup")
    shutil.copyfile(path, backups[path])
orig = {path: backups[path].read_text(encoding="utf-8") for path in (AER, PER)}

SPAWN = "        self._seed_seqs: tuple[np.random.SeedSequence, ...] = tuple(seed_seq.spawn(self._size))\n"
FRESH = "            np.random.default_rng(self._seed_seqs[index]),\n"
MUTANTS = {
    "W01": (
        AER,
        [
            (
                SPAWN,
                "        self._seed_seqs = tuple(self._rng.spawn(self._size))  # type: ignore[assignment]\n",
            ),
            (FRESH, "            self._seed_seqs[index],  # type: ignore[arg-type]\n"),
        ],
    ),
    "W02": (
        AER,
        [
            (
                "        if rng is None and not isinstance(self._perturbation, IdentityPerturbation):\n",
                "        if False and rng is None and not isinstance(self._perturbation, IdentityPerturbation):\n",
            )
        ],
    ),
    "W03": (
        AER,
        [
            (
                "        if rng is None and not isinstance(self._perturbation, IdentityPerturbation):\n",
                "        if rng is None:\n",
            )
        ],
    ),
    "W04": (
        AER,
        [
            (
                "            feature_extractor=self._feature_extractor,\n            rule_base=self._rule_base,\n            defuzzifier=self._defuzzifier,\n        )\n        name = type(self._perturbation).__name__\n",
                "            feature_extractor=getattr(self, '_previous', self._feature_extractor),\n            rule_base=self._rule_base,\n            defuzzifier=self._defuzzifier,\n        )\n        self._previous = extractor\n        name = type(self._perturbation).__name__\n",
            )
        ],
    ),
    "W05": (
        AER,
        [
            (
                "                feature_extractor=feature_extractor,\n",
                "                feature_extractor=self._feature_extractor,\n",
            )
        ],
    ),
    "W06": (AER, [(FRESH, "            self._rng,\n")]),
    "W07": (AER, [(FRESH, "            np.random.default_rng(self._seed_seqs[0]),\n")]),
    "W08": (
        AER,
        [
            (
                "        if extractor.feature_names != self._feature_extractor.feature_names:\n",
                "        if False:\n",
            )
        ],
    ),
    "W09": (
        AER,
        [
            (
                "        if extractor.output_dim != self._feature_extractor.output_dim:\n",
                "        if False:\n",
            )
        ],
    ),
    "W10": (
        AER,
        [("        if rule_base.input_dim != self._rule_base.input_dim:\n", "        if False:\n")],
    ),
    "W11": (
        AER,
        [
            (
                "        if rule_base.output_dim != self._rule_base.output_dim:\n",
                "        if False:\n",
            )
        ],
    ),
    "W12": (
        AER,
        [
            (
                SPAWN,
                "        self._seed_seqs: tuple[np.random.SeedSequence, ...] = tuple(np.random.default_rng().bit_generator.seed_seq.spawn(self._size))\n",
            )
        ],
    ),
    "W13": (
        AER,
        [
            (
                "            index,\n            np.random.default_rng(self._seed_seqs[index]),\n",
                "            0,\n            np.random.default_rng(self._seed_seqs[index]),\n",
            )
        ],
    ),
    "W14": (
        PER,
        [
            (
                "        return feature_extractor, rule_base, defuzzifier\n",
                "        rng.standard_normal()\n        return feature_extractor, rule_base, defuzzifier\n",
            )
        ],
    ),
    "W15": (
        AER,
        [
            (
                SPAWN,
                "        self._seed_seqs: tuple[np.random.SeedSequence, ...] = tuple(seed_seq.spawn(self._size + 1))[1:]\n",
            )
        ],
    ),
    "W16": (AER, [('        if not hasattr(seed_seq, "spawn"):\n', "        if False:\n")]),
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
    print("baseline:", base.stdout.strip().splitlines()[-1])
    for name, (path, edits) in MUTANTS.items():
        text = orig[path]
        for old, new in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8", newline="\n")
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
        shutil.copyfile(backups[path], path)
finally:
    for path in (AER, PER):
        shutil.copyfile(backups[path], path)
print("restored:", all(path.read_text(encoding="utf-8") == orig[path] for path in (AER, PER)))
