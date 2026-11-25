"""Mutation check of F6 (2026-11-25): a submit that dies before its job id is written.

    python docs/evidence/hardware-reading-vs-level/day-15-2026-11-25/mutate_f6.py \
        --root . --python <interpreter> --out <file>

Each mutant replaces one piece of text in `scripts/hardware_submit.py`, which must occur exactly
once, runs the F6 tests and the day-15 tests, and restores the file from the bytes read before the
edit. The selection leaves out the tests that run Aer (on 2026-11-25 two of them died of an access
violation inside Aer on this laptop while an emulator held most of its memory); none of them reads
the lines mutated here.

A mutant is `killed` only when pytest exits 1 ("tests were collected and some failed"). Exit 0 is
`survived`. Any other exit is `harness error`. pytest runs without `-x`, so a module that does not
import exits 2 and cannot count as killed; the control `S00` shows that path. The output lists the
failing tests per mutant. The script exits 1 when any outcome differs from its prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
from pathlib import Path

TARGET = "scripts/hardware_submit.py"
TESTS = (
    "tests/test_hardware_day_15.py",
    "tests/test_hardware_t1_check.py::test_a_check_whose_submit_dies_is_named_by_the_closure",
    "tests/test_hardware_submit.py::test_a_submit_that_dies_leaves_a_day_the_report_calls_unconfirmed",
)

# (name, text to replace, replacement, prediction, why)
MUTANTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "S00 control: the module does not import",
        "import numpy as np\n",
        "import numpy as np\nimport no_such_module_f6\n",
        "harness error (pytest exit 2)",
        "collection fails; without -x pytest exits 2",
    ),
    (
        "U01 the report never says 'submit unconfirmed'",
        '    if submit_unconfirmed(job_dir):\n        return "submit unconfirmed"\n',
        "",
        "killed",
        "the no-id folder; the closure test's day list; the dying build",
    ),
    (
        "U02 the closure leaves out an unconfirmed day",
        "if awaits_score(f) or submit_unconfirmed(f)]",
        "if awaits_score(f)]",
        "killed",
        "the closure test; the dying build",
    ),
    (
        "U03 the closure leaves out an unconfirmed check",
        "if check_awaits_score(f) or check_submit_unconfirmed(f)",
        "if check_awaits_score(f)",
        "killed",
        "the closure test; the dying check",
    ),
    (
        "U04 a day is unconfirmed whenever it has submission.json",
        'return (job_dir / "submission.json").exists() and not (job_dir / "job_id.txt").exists()',
        'return (job_dir / "submission.json").exists()',
        "killed",
        "the guard test: scored days that keep their submission.json",
    ),
    (
        "U05 a check is unconfirmed whenever it has t1-sealed.json",
        'return (job_dir / "t1-sealed.json").exists() and not (job_dir / "t1-job_id.txt").exists()',
        'return (job_dir / "t1-sealed.json").exists()',
        "killed",
        "the guard test: scored checks that keep their t1-sealed.json",
    ),
    (
        "U06 keyed on sealed.json instead of submission.json",
        'return (job_dir / "submission.json").exists() and not',
        'return (job_dir / "sealed.json").exists() and not',
        "killed",
        "the folder tests write submission.json only",
    ),
    (
        "U07 unconfirmed tested before 'submitted, not scored'",
        '    if (job_dir / "job_id.txt").exists():\n        return "submitted, not scored"\n'
        '    if submit_unconfirmed(job_dir):\n        return "submit unconfirmed"\n',
        '    if submit_unconfirmed(job_dir):\n        return "submit unconfirmed"\n'
        '    if (job_dir / "job_id.txt").exists():\n        return "submitted, not scored"\n',
        "survived",
        "equivalent: submit_unconfirmed is false whenever job_id.txt exists, so the two branches "
        "never both hold and their order cannot change a status",
    ),
)

FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


def classify(code: int) -> str:
    if code == 0:
        return "survived"
    if code == 1:
        return "killed"
    return f"harness error (pytest exit {code})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    target = args.root / TARGET
    original = target.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    env = {**os.environ, "PYTHONPATH": "src", "COLUMNS": "200"}
    env.pop("PYTEST_ADDOPTS", None)
    command = [args.python, "-m", "pytest", *TESTS, "-q", "-rf", "-p", "no:cacheprovider"]
    command += ["-o", "addopts="]

    baseline = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
    if baseline.returncode != 0:
        print(f"the unmutated tests do not pass (pytest exit {baseline.returncode})")
        return 1
    lines = [f"baseline: {baseline.stdout.strip().splitlines()[-1].strip('= ')}"]
    lines.append("mutant\tprediction\toutcome\tmatches\tfailing tests")
    outcomes: list[str] = []
    bad = 0
    for name, old, new, prediction, _why in MUTANTS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{name}: the text occurs {count} times in {TARGET}")
        try:
            target.write_bytes(text.replace(old, new).encode("utf-8"))
            done = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
        finally:
            target.write_bytes(original)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name}: {TARGET} was not restored")
        outcome = classify(done.returncode)
        outcomes.append(outcome)
        matches = outcome == prediction
        bad += 0 if matches else 1
        failing = sorted({test.split("::", 1)[-1] for test in FAILED.findall(done.stdout)})
        lines.append(f"{name}\t{prediction}\t{outcome}\t{matches}\t{', '.join(failing) or '-'}")
        print(lines[-1], flush=True)

    mutants = outcomes[1:]
    killed = mutants.count("killed")
    survived = mutants.count("survived")
    errors = len(mutants) - killed - survived
    summary = (
        f"{len(mutants)} mutants and 1 control: {killed} killed, {survived} survived, "
        f"{errors} harness errors among the mutants; control {outcomes[0]}; "
        f"{bad} against the prediction"
    )
    lines.append(summary)
    print(summary)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 1 if bad or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
