"""Mutation check for PR #142's stage 3 (amendment 37's three code items), criterion 34.

Each mutant replaces one text that must occur exactly once in its file, runs the tests that
cover it with ``-x``, and restores the file from the bytes read before the change; the restored
file's SHA-256 is checked against the original after every mutant. Run it in a plain copy of
the branch (``git archive``), never in a worktree with uncommitted work.

Each mutant carries its prediction, written before the first run: ``caught`` (an assertion, a
crash or a timeout) or ``equivalent`` with the reason. The result table puts the prediction
beside the outcome.

Usage::

    python docs/evidence/hardware-reading-vs-level/stage-3-2026-11-09/mutate_stage_3.py \\
        --root C:/t/mut3 --python C:/t/pin125/Scripts/python.exe --out results.tsv
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SUBMIT = "scripts/hardware_submit.py"
PREDICTORS = "scripts/hardware_test_predictors.py"
REPORT_TESTS = (
    "tests/test_hardware_report_rule.py",
    "tests/test_hardware_submit.py::test_a_run_with_no_control_rows_does_not_meet_a3",
)
PREDICTOR_TESTS = ("tests/test_hardware_test_predictors.py",)
TIMEOUT_S = 120


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    prediction: str  # "caught" or "equivalent: <reason>"


MUTANTS: tuple[Mutant, ...] = (
    # c_block_interval
    Mutant(
        "H01 no interval at three days",
        SUBMIT,
        "if n_days <= BLOCK_DAYS or not points:",
        "if n_days < BLOCK_DAYS or not points:",
        "caught",
    ),
    Mutant(
        "H02 empty-points guard dropped",
        SUBMIT,
        "if n_days <= BLOCK_DAYS or not points:",
        "if n_days <= BLOCK_DAYS:",
        "equivalent: with no points every day's sum(x^2) is 0, and the next guard returns None",
    ),
    Mutant(
        "H03 numerator without x",
        SUBMIT,
        "sxy[(day - first).days] += x * y",
        "sxy[(day - first).days] += y",
        "caught",
    ),
    Mutant(
        "H04 denominator without the square",
        SUBMIT,
        "sxx[(day - first).days] += x * x",
        "sxx[(day - first).days] += x",
        "caught",
    ),
    Mutant(
        "H05 undefined-c guard dropped",
        SUBMIT,
        "    if sxx.sum() == 0.0:\n        return None\n    n_blocks",
        "    n_blocks",
        "caught",  # every draw then has a zero denominator and is drawn again for ever: timeout
    ),
    Mutant(
        "H06 floor instead of ceil blocks",
        SUBMIT,
        "n_blocks = math.ceil(n_days / BLOCK_DAYS)",
        "n_blocks = n_days // BLOCK_DAYS",
        "caught",
    ),
    Mutant(
        "H07 two-day blocks",
        SUBMIT,
        "offsets = np.arange(BLOCK_DAYS)",
        "offsets = np.arange(BLOCK_DAYS - 1)",
        "caught",
    ),
    Mutant(
        "H08 blocks not circular",
        SUBMIT,
        "% n_days).reshape(-1)",
        ").reshape(-1)",
        "caught",
    ),
    Mutant(
        "H09 empty draw not redrawn",
        SUBMIT,
        "        if denominator == 0.0:\n            continue\n",
        "",
        "caught",
    ),
    Mutant(
        "H10 80% instead of 90%",
        SUBMIT,
        "alpha = (1.0 - level) / 2.0\n    low, high",
        "alpha = 1.0 - level\n    low, high",
        "caught",
    ),
    Mutant(
        "H11 ends swapped",
        SUBMIT,
        "return [float(low), float(high)]",
        "return [float(high), float(low)]",
        "caught",
    ),
    Mutant(
        "H12 another seed",
        SUBMIT,
        "rng = np.random.default_rng(seed)\n    offsets = np.arange(BLOCK_DAYS)",
        "rng = np.random.default_rng(seed + 1)\n    offsets = np.arange(BLOCK_DAYS)",
        "caught",
    ),
    Mutant(
        "H13 starts miss the last day",
        SUBMIT,
        "starts = rng.integers(0, n_days, size=n_blocks)",
        "starts = rng.integers(0, n_days - 1, size=n_blocks)",
        "caught",
    ),
    # run_report wiring
    Mutant(
        "H14 two seed words",
        SUBMIT,
        "generate_state(3, dtype=np.uint32)",
        "generate_state(2, dtype=np.uint32)",
        "caught",
    ),
    Mutant(
        "H15 A1's seed for c",
        SUBMIT,
        "c_block_interval(points, span=span, seed=int(seeds[2]))",
        "c_block_interval(points, span=span, seed=int(seeds[0]))",
        "caught",
    ),
    Mutant(
        "H16 every point on the first day",
        SUBMIT,
        "fit, day))",
        "fit, first_day))",
        "caught",
    ),
    Mutant(
        "H17 block length reported wrong",
        SUBMIT,
        '"c_interval_block_days": BLOCK_DAYS,',
        '"c_interval_block_days": 2,',
        "caught",
    ),
    Mutant(
        "H18 x and y swapped for c",
        SUBMIT,
        "**slope_and_spread([(x, y) for x, y, _ in points]),",
        "**slope_and_spread([(y, x) for x, y, _ in points]),",
        "caught",
    ),
    # the reading texts
    Mutant(
        "H19 third row's old words",
        SUBMIT,
        '"S1 not supported: the controls disagree in sign, or the run has no control rows. The "',
        '"S1 not supported: the controls disagree in sign. The "',
        "caught",
    ),
    Mutant(
        "H20 last row's old key in the table",
        SUBMIT,
        '"S1 does not pass and Arm B does not": "Nothing is added.",',
        '"neither passes": "Nothing is added.",',
        "caught",
    ),
    Mutant(
        "H21 last row's old key in the chain",
        SUBMIT,
        'row = "S1 does not pass and Arm B does not"',
        'row = "neither passes"',
        "caught",
    ),
    # freeze_controls
    Mutant(
        "P01 no extra candidates",
        PREDICTORS,
        "k=k + len(marked), exclude=set(below)",
        "k=k, exclude=set(below)",
        "caught",
    ),
    Mutant(
        "P02 marked dropped before the median",
        PREDICTORS,
        "k=k + len(marked), exclude=set(below)",
        "k=k + len(marked), exclude=set(below) | marked",
        "caught",
    ),
    Mutant(
        "P03 no stop at k",
        PREDICTORS,
        "        if len(controls) == k:\n            break\n",
        "",
        "caught",
    ),
    Mutant(
        "P04 test inverted",
        PREDICTORS,
        'if candidate["qubit"] in marked:',
        'if candidate["qubit"] not in marked:',
        "caught",
    ),
    Mutant(
        "P05 skipped not recorded",
        PREDICTORS,
        'skipped.append(candidate["qubit"])',
        "pass",
        "caught",
    ),
    Mutant(
        "P06 skipped returned empty",
        PREDICTORS,
        '"controls": controls, "skipped": skipped}',
        '"controls": controls, "skipped": []}',
        "caught",
    ),
    # not_operational_in
    Mutant(
        "P07 always a configuration",
        PREDICTORS,
        'has_configuration = isinstance(doc.get("configuration"), dict)',
        "has_configuration = True",
        "caught",
    ),
    Mutant(
        "P08 never a configuration",
        PREDICTORS,
        'has_configuration = isinstance(doc.get("configuration"), dict)',
        "has_configuration = False",
        "caught",
    ),
    Mutant(
        "P09 the stand-in target has no measure",
        PREDICTORS,
        "for instruction in (XGate(), SXGate(), Measure()):",
        "for instruction in (XGate(), SXGate()):",
        "caught",
    ),
    Mutant(
        "P10 the stand-in target misses the last qubit",
        PREDICTORS,
        "{(q,): None for q in range(n_qubits)}",
        "{(q,): None for q in range(n_qubits - 1)}",
        "caught",
    ),
    Mutant(
        "P11 the stand-in target has one qubit too many",
        PREDICTORS,
        'n_qubits = len(doc["properties"]["qubits"])',
        'n_qubits = len(doc["properties"]["qubits"]) + 1',
        "equivalent: the extra index is in every gate of the stand-in and has no gate entry, "
        "so it is never marked",
    ),
    Mutant(
        "P12 nothing ever marked",
        PREDICTORS,
        'return has_configuration, not_operational_qubits(doc["properties"], target)',
        "return has_configuration, []",
        "caught",
    ),
    # _not_operational_at_freeze and main
    Mutant(
        "P13 no guard for no file",
        PREDICTORS,
        "    if record is None:\n        return {",
        "    if False:\n        return {",
        "caught",
    ),
    Mutant(
        "P14 path filter dropped",
        PREDICTORS,
        "found = [doc for path, doc in listed if path == record.path]",
        "found = [doc for path, doc in listed]",
        "equivalent: the listing is given the exact path, and archive paths end in .json",
    ),
    Mutant(
        "P15 one-file check dropped",
        PREDICTORS,
        "    if len(found) != 1:\n        raise ValueError",
        "    if False:\n        raise ValueError",
        "caught",
    ),
    Mutant(
        "P16 whole archive listed again",
        PREDICTORS,
        "listed = iter_archive(repo, sha, prefix=record.path)",
        "listed = iter_archive(repo, sha)",
        "equivalent: the path filter keeps the one file; only slower on the real archive",
    ),
    Mutant(
        "P17 time not recorded",
        PREDICTORS,
        '"time": record.time.isoformat(),',
        '"time": None,',
        "caught",
    ),
    Mutant(
        "P18 configuration flag recorded wrong",
        PREDICTORS,
        '"has_configuration": has_configuration,\n        "qubits": qubits,',
        '"has_configuration": True,\n        "qubits": qubits,',
        "caught",
    ),
    Mutant(
        "P19 the last collected file",
        PREDICTORS,
        "_not_operational_at_freeze(args.repo, sha, _latest_file(collected.files, at))",
        "_not_operational_at_freeze(args.repo, sha, collected.files[-1])",
        "equivalent: collect already drops every file after --at, so the last file is the latest "
        "at or before it",
    ),
    Mutant(
        "P20 marked set not passed",
        PREDICTORS,
        'not_operational=marked["qubits"]',
        "not_operational=()",
        "caught",
    ),
    Mutant(
        "P21 skipped not nested",
        PREDICTORS,
        'frozen["not_operational_at_freeze"] = {**marked, "skipped": frozen.pop("skipped")}',
        'frozen["not_operational_at_freeze"] = marked',
        "caught",
    ),
)


def _tests_for(path: str) -> tuple[str, ...]:
    return REPORT_TESTS if path == SUBMIT else PREDICTOR_TESTS


def _classify(code: int | None, output: str) -> str:
    if code is None:
        return "caught: timeout"
    if code == 0:
        return "survived"
    if "AssertionError" in output or re.search(r"^E\s+assert ", output, re.MULTILINE):
        return "caught: assertion"
    return "caught: crash"


def run(root: Path, python: str) -> list[tuple[Mutant, str, float, str]]:
    env = {**os.environ, "PYTHONPATH": "src", "COLUMNS": "1000"}
    results = []
    for mutant in MUTANTS:
        target = root / mutant.path
        original = target.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        text = original.decode("utf-8")
        count = text.count(mutant.old)
        if count != 1:
            raise SystemExit(f"{mutant.name}: the text occurs {count} times in {mutant.path}")
        try:
            target.write_bytes(text.replace(mutant.old, mutant.new).encode("utf-8"))
            started = time.monotonic()
            cmd = [python, "-m", "pytest", *_tests_for(mutant.path), "-x", "-q", "-p"]
            cmd += ["no:cacheprovider"]
            try:
                done = subprocess.run(
                    cmd, cwd=root, env=env, capture_output=True, text=True, timeout=TIMEOUT_S
                )
                code: int | None = done.returncode
                output = done.stdout + done.stderr
            except subprocess.TimeoutExpired:
                code, output = None, ""
            seconds = time.monotonic() - started
        finally:
            target.write_bytes(original)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{mutant.name}: {mutant.path} was not restored")
        summary = next(
            (ln.strip("= ")[:200] for ln in reversed(output.splitlines()) if " in " in ln), ""
        )
        outcome = _classify(code, output)
        results.append((mutant, outcome, seconds, summary))
        print(f"{mutant.name}\t{outcome}\t{mutant.prediction}", flush=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = run(args.root, args.python)
    lines = ["mutant\tfile\tprediction\toutcome\tmatches\tseconds\tpytest"]
    for mutant, outcome, seconds, summary in results:
        predicted_caught = mutant.prediction == "caught"
        matches = predicted_caught == outcome.startswith("caught")
        lines.append(
            f"{mutant.name}\t{mutant.path}\t{mutant.prediction}\t{outcome}\t{matches}\t"
            f"{seconds:.1f}\t{summary}"
        )
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    caught = sum(1 for _, o, _, _ in results if o.startswith("caught"))
    mismatched = sum(1 for line in lines[1:] if "\tFalse\t" in line)
    print(
        f"{len(results)} mutants: {caught} caught, {len(results) - caught} survived, "
        f"{mismatched} against the prediction"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
