"""Mutation check for issue #148: does each line of the fix have a test that needs it?

    python docs/evidence/issue-148-freeze/mutate.py --python <python with the pins>

Each mutant is one textual change to ``src/superconducted/types.py``. The script never touches
the worktree: it unpacks ``git archive HEAD`` into a temporary folder, mutates the copy, and runs
the two test files that cover the fix against the copy's own ``src``.

Contract. Input: the repository this file sits in, at a commit that holds the fix, and an
interpreter with the repository's pins. Output: one line per mutant on stdout, then a summary.
Exit status 0 when every mutant does what its prediction says, 1 otherwise. No side effects
outside the temporary folder.

The predictions were written in ``docs/implementations/2026-11-20-issue-148-freeze-training-
results.md`` before this script ran. "caught" means the test run fails; "survives" means it
passes, which is predicted for M9 alone, an equivalent mutant.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

TARGET = "src/superconducted/types.py"
TESTS = ("tests/training/test_types.py", "tests/test_anfis.py")

SET_STANDARDIZATION = '        object.__setattr__(self, "standardization", standardization)\n'
SET_TRAIN = '        object.__setattr__(self, "train_rmse", train_rmse)\n'
SET_VALIDATION = '            object.__setattr__(self, "validation_rmse", validation_rmse)\n'
SET_LOSS = '        object.__setattr__(self, "loss_history", loss_history)\n'

# (id, what it does, prediction, [(old, new), ...])
MUTANTS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (
        "M1",
        "_frozen_copy does not copy float64 input",
        "caught",
        [
            (
                "copy = np.array(values, dtype=np.float64)",
                "copy = np.asarray(values, dtype=np.float64)",
            )
        ],
    ),
    (
        "M2",
        "_frozen_copy does not freeze",
        "caught",
        [("    copy.flags.writeable = False\n    return copy\n", "    return copy\n")],
    ),
    (
        "M3",
        "_frozen_copy keeps the input dtype",
        "caught",
        [("copy = np.array(values, dtype=np.float64)", "copy = np.array(values)")],
    ),
    (
        "M4",
        "standardization is built as a list",
        "caught",
        [
            (
                "standardization = tuple(_frozen_copy(values) for values in self.standardization)",
                "standardization = [_frozen_copy(values) for values in self.standardization]",
            )
        ],
    ),
    ("M5", "standardization is not stored", "caught", [(SET_STANDARDIZATION, "")]),
    ("M6", "train_rmse is not stored", "caught", [(SET_TRAIN, "")]),
    ("M7", "validation_rmse is not stored", "caught", [(SET_VALIDATION, "")]),
    ("M8", "loss_history is not stored as a tuple", "caught", [(SET_LOSS, "")]),
    (
        "M9",
        "finiteness is checked on the caller's values, not the copies",
        "survives",
        [
            (
                "for values in standardization):",
                "for values in self.standardization):",
            ),
            ("np.isfinite(train_rmse)", "np.isfinite(self.train_rmse)"),
            ("np.isfinite(validation_rmse)", "np.isfinite(self.validation_rmse)"),
        ],
    ),
]


def unpack_head(repo: Path, into: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", "HEAD"], capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")


def run_tests(python: str, root: Path) -> tuple[int, list[str]]:
    """Exit status and every failing test, each as ``test id: what was raised``.

    The run does not stop at the first failure, so a mutant's line shows every test that
    needs the mutated line, not only the first one pytest reaches.
    """
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            *TESTS,
            "-q",
            "--tb=no",
            "-rf",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    text = done.stdout + done.stderr
    # The short summary prints "FAILED <test id> - <what was raised>" once per failing test.
    failures = re.findall(r"^FAILED (\S+)(?: - (.*))?$", text, flags=re.MULTILINE)
    return done.returncode, [f"{test}: {how.strip()}"[:160] for test, how in failures]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]

    with tempfile.TemporaryDirectory(prefix="m148-") as tmp:
        root = Path(tmp)
        unpack_head(repo, root)
        target = root / TARGET
        pristine = target.read_text(encoding="utf-8")

        status, failures = run_tests(args.python, root)
        print(f"baseline, no mutant: {'passes' if status == 0 else 'FAILS'}")
        if status != 0:
            print("\n".join(f"    {line}" for line in failures))
            return 1

        against = 0
        caught = 0
        for name, what, prediction, edits in MUTANTS:
            mutated = pristine
            for old, new in edits:
                if mutated.count(old) != 1:
                    raise SystemExit(f"{name}: expected exactly one {old!r} in {TARGET}")
                mutated = mutated.replace(old, new)
            target.write_text(mutated, encoding="utf-8", newline="\n")
            try:
                status, failures = run_tests(args.python, root)
            finally:
                target.write_text(pristine, encoding="utf-8", newline="\n")
            outcome = "survives" if status == 0 else "caught"
            caught += outcome == "caught"
            agrees = outcome == prediction
            against += not agrees
            print(
                f"{name}  {what}: predicted {prediction}, {outcome}"
                f"{'' if agrees else '  AGAINST THE PREDICTION'}"
                f"{'' if outcome == 'survives' else f', {len(failures)} tests fail'}"
            )
            for line in failures:
                print(f"    {line}")

        status, failures = run_tests(args.python, root)
        print(f"baseline again, file restored: {'passes' if status == 0 else 'FAILS'}")
        print(
            f"{len(MUTANTS)} mutants: {caught} caught, {len(MUTANTS) - caught} survived,"
            f" {against} against the prediction"
        )
        return 0 if against == 0 and status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
