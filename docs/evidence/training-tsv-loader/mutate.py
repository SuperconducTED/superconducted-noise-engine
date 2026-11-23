"""Mutation check of `load_training_tsv` (PR #163, review fixes of 2026-11-23).

    python docs/evidence/training-tsv-loader/mutate.py --root . --python <interpreter> --out <file>

Each mutant replaces one piece of text in `src/superconducted/training/dataset.py`, which must occur
exactly once, runs the loader's tests, and restores the file from the bytes read before the edit.

A mutant is `killed` only when pytest exits 1, which is "tests were collected and some failed".
Exit 0 is `survived`. Any other exit code (2 interrupted, 3 internal error, 4 usage error, 5 no
tests collected) is `harness error`: the tests did not judge the mutant, so it is not counted as
killed, and the script exits 1. It also exits 1 when an outcome differs from its prediction.

Reads and rewrites one source file, restores it, and writes `--out`. Nothing else.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from pathlib import Path

TARGET = "src/superconducted/training/dataset.py"
TESTS = ("tests/training/test_dataset.py", "-k", "training_tsv")

# (name, text to replace, replacement, prediction)
MUTANTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "M01 a header with no rows is accepted",
        '    if not features:\n        raise ValueError("TSV has no training rows")\n',
        "",
        "killed",
    ),
    (
        "M02 the weight column is always weight_uniform",
        'weight_column = f"weight_{weighting}"',
        'weight_column = "weight_uniform"',
        "killed",
    ),
    (
        "M03 a repeated header column is accepted",
        "reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames))",
        "reader.fieldnames is None",
        "killed",
    ),
    (
        "M04 targets read as (lambda, gamma)",
        "targets.append([float(row[name]) for name in target_names])",
        "targets.append([float(row[name]) for name in reversed(target_names)])",
        "killed",
    ),
    (
        "M05 features read as (T2, T1, readout)",
        "features.append([float(row[name]) for name in feature_names])",
        'features.append([float(row[n]) for n in ("mean_T2", "mean_T1", "mean_readout_error")])',
        "killed",
    ),
    (
        "M06 the ref length is not checked",
        "len(archive_ref) not in (40, 64) or any(",
        "any(",
        "killed",
    ),
    (
        "M07 the ref alphabet is not checked",
        'character not in "0123456789abcdef" for character in archive_ref',
        "False for character in archive_ref",
        "killed",
    ),
    (
        "M08 an unknown weighting is not refused by name",
        '        )\n    if weighting not in ("uniform", "hour_of_day"):\n'
        '        raise ValueError("Unknown weighting")\n    feature_names = ',
        "        )\n    feature_names = ",
        "killed",
    ),
    (
        "M09 provenance read from the stem column",
        'provenance.append(row["qubit_digest"])',
        'provenance.append(row["stem"] if "stem" in row else row["qubit_digest"])',
        "killed",
    ),
    (
        "M10 a 64-character ref is refused",
        "not in (40, 64)",
        "not in (40,)",
        "killed",
    ),
    (
        "M11 a naive timestamp is stamped UTC instead of refused",
        'datetime.fromisoformat(row["last_update_date"])',
        'datetime.fromisoformat(row["last_update_date"]).replace(tzinfo=UTC)',
        "killed",
    ),
    (
        "M12 a surplus cell is accepted",
        "if None in row or None in row.values():",
        "if None in row.values():",
        "killed",
    ),
    (
        "M13 a missing cell is accepted",
        "if None in row or None in row.values():",
        "if None in row:",
        "killed",
    ),
    (
        "M14 tied timestamps are accepted",
        "if any(later <= earlier for earlier, later in pairwise(data.timestamps)):",
        "if any(later < earlier for earlier, later in pairwise(data.timestamps)):",
        "killed",
    ),
    (
        "M15 the row order is not checked",
        "if any(later <= earlier for earlier, later in pairwise(data.timestamps)):",
        "if False:",
        "killed",
    ),
    (
        "M16 the file name is not checked",
        "if named is not None and not archive_ref.startswith(named.group(1)):",
        "if False:",
        "killed",
    ),
    (
        "M17 the file-name check is inverted",
        "if named is not None and not archive_ref.startswith(named.group(1)):",
        "if named is not None and archive_ref.startswith(named.group(1)):",
        "killed",
    ),
)


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
    command = [args.python, "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"]
    command += ["-o", "addopts="]

    baseline = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
    if baseline.returncode != 0:
        print(f"the unmutated tests do not pass (pytest exit {baseline.returncode})")
        return 1

    lines = ["mutant\tprediction\toutcome\tmatches\tpytest"]
    outcomes: list[str] = []
    bad = 0
    for name, old, new, prediction in MUTANTS:
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
        tail = done.stdout.strip().splitlines()[-1].strip("= ") if done.stdout.strip() else ""
        lines.append(f"{name}\t{prediction}\t{outcome}\t{matches}\t{tail}")
        print(lines[-1], flush=True)

    killed = outcomes.count("killed")
    survived = outcomes.count("survived")
    errors = len(outcomes) - killed - survived
    summary = (
        f"{len(MUTANTS)} mutants: {killed} killed, {survived} survived, {errors} harness errors, "
        f"{bad} against the prediction"
    )
    lines.append(summary)
    print(summary)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 1 if bad or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
