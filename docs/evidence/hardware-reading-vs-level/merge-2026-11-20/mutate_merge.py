"""Mutation check for PR #142 after PR #140's merge (the band's Arm B coverage), criterion 39.

The runner is stage 3's (``stage-3-2026-11-09/mutate_stage_3.py``), unchanged: each mutant
replaces one text that must occur exactly once in its file, runs the tests that cover it with
``-x``, and restores the file from the bytes read before the change; the restored file's SHA-256
is checked against the original after every mutant. Run it in a plain copy of the branch
(``git archive``), never in a worktree with uncommitted work.

Each mutant carries its prediction, written and committed before the first run: ``caught`` (an
assertion, a crash or a timeout) or ``equivalent`` with the reason. The comment above each says
which kind of catch is expected. The result table puts the prediction beside the outcome.

Usage::

    python docs/evidence/hardware-reading-vs-level/merge-2026-11-20/mutate_merge.py \\
        --root C:/t/mut20 --python C:/t/pin125/Scripts/python.exe --out results.tsv
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
# Every test that reaches _arm_b_report, directly or through run_report's Arm B path.
REPORT_TESTS = (
    "tests/test_hardware_submit.py",
    "-k",
    "arm_b or band or near_tie or correlation or job_one",
)
PREDICTOR_TESTS: tuple[str, ...] = ()
TIMEOUT_S = 120

SHARE = '"share": band_covered / band_layouts if band_layouts else None,'


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    prediction: str  # "caught" or "equivalent: <reason>"


MUTANTS: tuple[Mutant, ...] = (
    # Assertion: the pooled test expects 4 layouts and 3 covered.
    Mutant("B01 layouts start at 1", SUBMIT, "band_layouts = 0", "band_layouts = 1", "caught"),
    Mutant("B02 covered start at 1", SUBMIT, "band_covered = 0", "band_covered = 1", "caught"),
    # Crash: every job that has a band is refused, so the first Arm B test raises.
    Mutant(
        "B03 refusal negated",
        SUBMIT,
        'if "band" not in job:',
        'if "band" in job:',
        "caught",
    ),
    # Crash: without the check, the job with no band raises KeyError, not the expected ValueError.
    Mutant("B04 refusal dropped", SUBMIT, 'if "band" not in job:', "if False:", "caught"),
    # Assertion: pytest.raises' match on the day fails.
    Mutant(
        "B05 refusal does not name the day",
        SUBMIT,
        'f"{day}: arm-b.json has no band entry',
        'f"arm-b.json has no band entry',
        "caught",
    ),
    # Assertion: the counts swap fields or stop adding up over jobs.
    Mutant(
        "B06 layouts count the covered",
        SUBMIT,
        'band_layouts += job["band"]["n_predicted"]',
        'band_layouts += job["band"]["n_covered"]',
        "caught",
    ),
    Mutant(
        "B07 covered count the layouts",
        SUBMIT,
        'band_covered += job["band"]["n_covered"]',
        'band_covered += job["band"]["n_predicted"]',
        "caught",
    ),
    Mutant(
        "B08 layouts keep the last job only",
        SUBMIT,
        "band_layouts += job",
        "band_layouts = job",
        "caught",
    ),
    Mutant(
        "B09 covered keep the last job only",
        SUBMIT,
        "band_covered += job",
        "band_covered = job",
        "caught",
    ),
    # Assertion: the reported fields swap.
    Mutant(
        "B10 layouts field reports covered",
        SUBMIT,
        '"layouts": band_layouts,',
        '"layouts": band_covered,',
        "caught",
    ),
    Mutant(
        "B11 covered field reports layouts",
        SUBMIT,
        '"covered": band_covered,',
        '"covered": band_layouts,',
        "caught",
    ),
    # Assertion: the share is 1, 0.0 or None where the tests expect 0.75, None or 0.0.
    Mutant(
        "B12 share of layouts over layouts",
        SUBMIT,
        SHARE,
        '"share": band_layouts / band_layouts if band_layouts else None,',
        "caught",
    ),
    Mutant(
        "B13 share zero without a band",
        SUBMIT,
        SHARE,
        '"share": band_covered / band_layouts if band_layouts else 0.0,',
        "caught",
    ),
    # Crash: ZeroDivisionError on the report with no banded layout.
    Mutant(
        "B14 share without the guard",
        SUBMIT,
        SHARE,
        '"share": band_covered / band_layouts,',
        "caught",
    ),
    Mutant("B15 share always None", SUBMIT, SHARE, '"share": None,', "caught"),
    # Assertion: with nothing covered the share must be 0.0, not None (the decision test).
    Mutant(
        "B16 share guarded on covered",
        SUBMIT,
        SHARE,
        '"share": band_covered / band_layouts if band_covered else None,',
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
