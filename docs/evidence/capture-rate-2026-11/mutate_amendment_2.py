"""Mutation check for #104's amendment 2 (``capture_lifetimes.py --exclude-day``), criterion A4.

The runner is PR #142's stage 3 runner (``mutate_stage_3.py`` on that branch), unchanged: each
mutant replaces one text that must occur exactly once in its file, runs the tests that cover it
with ``-x``, and restores the file from the bytes read before the change; the restored file's
SHA-256 is checked against the original after every mutant. Run it in a plain copy of the branch
(``git archive``), never in a worktree with uncommitted work.

Each mutant carries its prediction, written and committed before the first run: ``caught`` (an
assertion, a crash or a timeout) or ``equivalent`` with the reason.

Usage::

    python docs/evidence/capture-rate-2026-11/mutate_amendment_2.py \\
        --root C:/t/mut104 --python C:/t/pin125/Scripts/python.exe --out results.tsv
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

SUBMIT = "docs/evidence/capture-rate-2026-11/capture_lifetimes.py"
REPORT_TESTS = ("tests/test_capture_lifetimes.py",)
PREDICTOR_TESTS: tuple[str, ...] = ()
TIMEOUT_S = 120
WEEK = "        if lo <= d <= hi and d not in excluded:"


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    prediction: str  # "caught" or "equivalent: <reason>"


MUTANTS: tuple[Mutant, ...] = (
    # Assertion: days listed in the order given (2026-11-24 first), and a repeat not refused.
    Mutant(
        "N01 exclusions neither sorted nor deduplicated",
        SUBMIT,
        "excluded = sorted(set(args.exclude))",
        "excluded = list(args.exclude)",
        "caught",
    ),
    Mutant(
        "N02 repeat check dropped",
        SUBMIT,
        "if len(excluded) != len(args.exclude):",
        "if False:",
        "caught",
    ),
    # Assertion: a legitimate end day is refused, so the edge test's exit code is not 0.
    Mutant(
        "N03 last day not excludable",
        SUBMIT,
        "if not lo <= d <= hi]",
        "if not lo <= d < hi]",
        "caught",
    ),
    Mutant(
        "N04 first day not excludable",
        SUBMIT,
        "if not lo <= d <= hi]",
        "if not lo < d <= hi]",
        "caught",
    ),
    Mutant("N05 outside check dropped", SUBMIT, "    if outside:", "    if False:", "caught"),
    # Assertion: 18 documents selected, P1 1 of 17.
    Mutant(
        "N06 excluded day kept in the selection",
        SUBMIT,
        " and when[stem].date() not in excluded",
        "",
        "caught",
    ),
    # Assertion: the line appears without the flag, or not with it.
    Mutant("N07 line always printed", SUBMIT, "    if excluded:", "    if True:", "caught"),
    Mutant("N08 line never printed", SUBMIT, "    if excluded:", "    if False:", "caught"),
    Mutant(
        "N09 days left count the excluded",
        SUBMIT,
        "kept = sum(lo <= d <= hi and d not in excluded for d in recorded)",
        "kept = sum(lo <= d <= hi for d in recorded)",
        "caught",
    ),
    # Assertion: week 47 shows 7 recorded days instead of 6.
    Mutant(
        "N10 excluded day kept in the week", SUBMIT, WEEK, "        if lo <= d <= hi:", "caught"
    ),
    # Assertion: the refusal messages are matched.
    Mutant(
        "N11 repeat message",
        SUBMIT,
        '"an --exclude-day is given twice"',
        '"an --exclude-day is repeated"',
        "caught",
    ),
    Mutant(
        "N12 outside message without the days",
        SUBMIT,
        "{lo} to {hi}: {', '.join(map(str, outside))}",
        "{lo} to {hi}",
        "caught",
    ),
    # Crash: a single date has no len().
    Mutant(
        "N13 the flag is not repeatable",
        SUBMIT,
        'action="append"',
        'action="store"',
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


def run(root: Path, python: str, only: str = "") -> list[tuple[Mutant, str, float, str]]:
    env = {**os.environ, "PYTHONPATH": "src", "COLUMNS": "1000"}
    results = []
    for mutant in MUTANTS:
        if not mutant.name.startswith(only):
            continue
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
    parser.add_argument("--only", default="", help="run only the mutants whose name starts so")
    args = parser.parse_args()
    results = run(args.root, args.python, args.only)
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
