"""Mutation check of the 2026-11-23 changes (criterion 46): day 15 and the sealed folder.

    python docs/evidence/hardware-reading-vs-level/day-15-2026-11-23/mutate_day_15.py \
        --root <a throwaway checkout of the head> --python <interpreter> --out <file>

Each mutant replaces one piece of text, which must occur exactly once in its file, runs the two test
files that cover the change, and restores the file from the bytes read before the edit.

A mutant is `caught` only when pytest exits 1: tests were collected and at least one failed. Exit 0
is `survived`. Any other exit code (2 interrupted, 3 internal error, 4 usage error, 5 no tests
collected) is `harness error`: the tests did not judge the mutant, so it is not a catch, and the
script exits 1. It also exits 1 when an outcome differs from its prediction. The earlier scripts
here count any non-zero exit as a catch; this one does not (the lesson of the review of PR #143).

The predictions below were written before the first run and are committed before it. D07 was
replaced and D14 to D19 added for the second design of the same day (a closed run's mornings), again
before their run. `--selftest` runs one extra mutant that breaks collection and passes only when it
is reported as a harness error. `PYTEST_ADDOPTS` is removed from the environment of every run, so a
stray value cannot break or bend the judgment.
Run it in a throwaway checkout: it rewrites source files while it works.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUBMIT = "scripts/hardware_submit.py"
DAILY = "scripts/hardware_daily.py"
T1 = "scripts/hardware_t1_check.py"
TESTS = ("tests/test_hardware_day_15.py", "tests/test_hardware_daily.py")


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    prediction: str  # "caught" or "survived"
    why: str


SAME_OR_INSIDE = "if sealed == other or sealed.is_relative_to(other):"
UNSEAL_GUARD = "if target.resolve() == source or target.resolve().is_relative_to(source):"
MAIN_GUARD = "refuse_sealed_inside(args.sealed_dir, args.jobs_dir, args.repo)"

MUTANTS: tuple[Mutant, ...] = (
    # --- hardware_submit.py: the three relations -------------------------------------------------
    Mutant(
        "S01 a sealed folder that contains the other is accepted",
        SUBMIT,
        "        if other.is_relative_to(sealed):\n"
        '            raise RefusedError(f"the sealed folder {sealed_dir} contains {folder}")\n',
        "",
        "caught",
        "the review's second finding; the parent and ancestor cases, and all three entry points",
    ),
    Mutant(
        "S02 the equality test is dropped from the first relation",
        SUBMIT,
        SAME_OR_INSIDE,
        "if sealed.is_relative_to(other):",
        "survived",
        "equivalent: Path.is_relative_to is true for a path and itself, so equality is implied",
    ),
    Mutant(
        "S03 a sealed folder inside the other is accepted",
        SUBMIT,
        SAME_OR_INSIDE,
        "if sealed == other:",
        "caught",
        "the inside case; the second relation does not cover it",
    ),
    # --- hardware_submit.py: the closed run ------------------------------------------------------
    Mutant(
        "S04 a closed run is not refused",
        SUBMIT,
        "    if marker.exists():\n        closed_on = ",
        "    if False:\n        closed_on = ",
        "caught",
        "both scorers' refusal tests",
    ),
    Mutant(
        "S05 the main score does not ask whether the run is closed",
        SUBMIT,
        "            refuse_sealed_inside(args.sealed_dir, args.job_dir.parent, args.repo)\n"
        "            refuse_closed_run(args.job_dir.parent)\n",
        "            refuse_sealed_inside(args.sealed_dir, args.job_dir.parent, args.repo)\n",
        "caught",
        "the test replaces the archive fetch with a function that fails the test when reached",
    ),
    Mutant(
        "S06 the marker has another name",
        SUBMIT,
        'CLOSED_NAME = "closed.json"',
        'CLOSED_NAME = "closed.txt"',
        "caught",
        "the tests write and read closed.json by its literal name",
    ),
    # --- hardware_submit.py: what closed unscored ------------------------------------------------
    Mutant(
        "S07 days lists the checks",
        SUBMIT,
        '"days": [f.name for f in folders if awaits_score(f)],',
        '"days": [f.name for f in folders if check_awaits_score(f)],',
        "caught",
        "the test with the job scored and its check not",
    ),
    Mutant(
        "S08 t1_checks lists the jobs",
        SUBMIT,
        '"t1_checks": [f.name for f in folders if check_awaits_score(f)],',
        '"t1_checks": [f.name for f in folders if awaits_score(f)],',
        "caught",
        "the same test, from the other side",
    ),
    Mutant(
        "S09 a failed job counts as unscored",
        SUBMIT,
        '        and not (job_dir / "failed.json").exists()\n',
        "",
        "caught",
        "the test with failed.json; also the routine's existing tests on failed days",
    ),
    Mutant(
        "S10 a failed check counts as unscored",
        SUBMIT,
        '        and not (job_dir / "t1-failed.json").exists()\n',
        "",
        "caught",
        "the test with t1-failed.json",
    ),
    Mutant(
        "S11 the report lists unscored days while the run is open",
        SUBMIT,
        "closed_unscored(jobs_dir, calendar) if complete else None,",
        "closed_unscored(jobs_dir, calendar),",
        "caught",
        "before day 15 the field must be null",
    ),
    Mutant(
        "S12 the report gives null once the run is complete",
        SUBMIT,
        "closed_unscored(jobs_dir, calendar) if complete else None,",
        "closed_unscored(jobs_dir, calendar) if not complete else None,",
        "caught",
        "day 15's report must carry the two lists",
    ),
    Mutant(
        "S13 the days are not sorted",
        SUBMIT,
        "folders = [jobs_dir / day.isoformat() for day in sorted(days)]",
        "folders = [jobs_dir / day.isoformat() for day in days]",
        "survived",
        "equivalent for both callers: the report's calendar and the routine's run days ascend",
    ),
    # --- hardware_t1_check.py --------------------------------------------------------------------
    Mutant(
        "T01 the check's score does not ask whether the run is closed",
        T1,
        "            refuse_closed_run(args.job_dir.parent)\n",
        "",
        "caught",
        "the test replaces the device with a function that fails the test when reached",
    ),
    # --- hardware_daily.py: the entry check ------------------------------------------------------
    Mutant(
        "D01 the routine does not check the sealed folder",
        DAILY,
        f"        {MAIN_GUARD}\n",
        "        pass\n",
        "caught",
        "every refused layout, old and new",
    ),
    Mutant(
        "D02 the routine checks the jobs folder only",
        DAILY,
        MAIN_GUARD,
        "refuse_sealed_inside(args.sealed_dir, args.jobs_dir)",
        "caught",
        "the layouts that involve the clone alone",
    ),
    Mutant(
        "D03 the routine checks the clone only",
        DAILY,
        MAIN_GUARD,
        "refuse_sealed_inside(args.sealed_dir, args.repo)",
        "caught",
        "the layouts that involve the jobs folder alone",
    ),
    # --- hardware_daily.py: unseal ---------------------------------------------------------------
    Mutant(
        "D04 unseal does not refuse a copy into itself",
        DAILY,
        UNSEAL_GUARD,
        "if False:",
        "caught",
        "the copy recurses or copies a file onto itself, and the folder is no longer as it was",
    ),
    Mutant(
        "D05 unseal refuses only the identical folder",
        DAILY,
        UNSEAL_GUARD,
        "if target.resolve() == source:",
        "caught",
        "the parent layout, the review's second finding",
    ),
    Mutant(
        "D06 the equality test is dropped from unseal's refusal",
        DAILY,
        UNSEAL_GUARD,
        "if target.resolve().is_relative_to(source):",
        "survived",
        "equivalent, as S02: is_relative_to is true for a path and itself",
    ),
    # --- hardware_daily.py: closing the run ------------------------------------------------------
    Mutant(
        "D07 a marker before day 15 is not an error",
        DAILY,
        "    if already_closed and number <= N_JOBS:\n",
        "    if False:\n",
        "caught",
        "a morning before day 15 with the marker must run nothing and exit 1",
    ),
    Mutant(
        "D08 the closure looks at thirteen days",
        DAILY,
        "for i in range(N_JOBS)]",
        "for i in range(N_JOBS - 1)]",
        "caught",
        "the unscored day in the tests is the fourteenth",
    ),
    Mutant(
        "D09 closed.json lacks the lists",
        DAILY,
        'closed = {"closed_on": today.isoformat(), "closed_unscored": closure}',
        'closed = {"closed_on": today.isoformat()}',
        "caught",
        "the file's content is compared whole",
    ),
    Mutant(
        "D10 closed.json names the first day as the closing day",
        DAILY,
        'closed = {"closed_on": today.isoformat(), "closed_unscored": closure}',
        'closed = {"closed_on": morning.first_day.isoformat(), "closed_unscored": closure}',
        "caught",
        "the file's content is compared whole",
    ),
    Mutant(
        "D11 the morning's record lacks the lists",
        DAILY,
        '    if closure is not None:\n        status["closed_unscored"] = closure\n',
        "",
        "caught",
        "the record is read back on day 15",
    ),
    Mutant(
        "D12 every morning records a closure",
        DAILY,
        "    if closure is not None:\n",
        "    if True:\n",
        "caught",
        "before day 15 the record must not carry the key",
    ),
    Mutant(
        "D13 the days to score are chosen by the check's markers",
        DAILY,
        "if awaits_score(p)]",
        "if check_awaits_score(p)]",
        "caught",
        "the routine's existing tests on which days are scored",
    ),
    # --- hardware_daily.py: the second design of 2026-11-23, a closed run's mornings -------------
    Mutant(
        "D14 a marker before day 15 exits 0",
        DAILY,
        'before the run can be closed: nothing was run")\n        return 1\n',
        'before the run can be closed: nothing was run")\n        return 0\n',
        "caught",
        "a morning with no job must be seen in the task's last result",
    ),
    Mutant(
        "D15 a second day 15 scores the late job",
        DAILY,
        "late_jobs = [] if already_closed else days_to_score(morning.jobs_dir, today)",
        "late_jobs = days_to_score(morning.jobs_dir, today)",
        "caught",
        "the second pass must run the report only",
    ),
    Mutant(
        "D16 a second day 15 scores the late check",
        DAILY,
        "late_checks = [] if already_closed else t1_to_score(morning.jobs_dir, today)",
        "late_checks = t1_to_score(morning.jobs_dir, today)",
        "caught",
        "the second pass must run the report only; the test's late day has a check",
    ),
    Mutant(
        "D17 a second day 15 writes a new closure",
        DAILY,
        "        if already_closed:\n            # The first closure stands",
        "        if False:\n            # The first closure stands",
        "caught",
        "the test changes the late day's markers between the passes; the first closure must stand",
    ),
    Mutant(
        "D18 the marker is written after the unseal",
        DAILY,
        '            marker.write_text(json.dumps(closed, indent=2) + "\\n", encoding="utf-8", '
        'newline="\\n")\n'
        "        # Amendment 27: the run is over, so the sealed folder joins the data branch.\n"
        '        steps.append(("unseal", unseal(morning.sealed_dir, morning.jobs_dir)))\n',
        "            pass\n"
        "        # Amendment 27: the run is over, so the sealed folder joins the data branch.\n"
        '        steps.append(("unseal", unseal(morning.sealed_dir, morning.jobs_dir)))\n'
        "        if not already_closed:\n"
        '            marker.write_text(json.dumps(closed, indent=2) + "\\n", encoding="utf-8", '
        'newline="\\n")\n',
        "caught",
        "the test that watches unseal must see the marker already on disk",
    ),
    Mutant(
        "D19 a second day 15 does not unseal again",
        DAILY,
        '        steps.append(("unseal", unseal(morning.sealed_dir, morning.jobs_dir)))\n',
        "        if not already_closed:\n"
        '            steps.append(("unseal", unseal(morning.sealed_dir, morning.jobs_dir)))\n',
        "caught",
        "a failed unseal must be repeatable: the second pass copies the sealed folder",
    ),
)

# Not one of the mutants: it breaks the module so that pytest cannot collect, to exercise the
# harness-error path end to end. See --selftest.
SELFTEST = Mutant(
    "X00 the routine's module does not parse",
    DAILY,
    "def unseal(sealed_dir: Path, jobs_dir: Path) -> int:",
    "def unseal(sealed_dir: Path, jobs_dir: Path) -> int",
    "harness error",
    "a collection error is pytest exit 2, not a caught mutant",
)


def classify(code: int) -> str:
    if code == 0:
        return "survived"
    if code == 1:
        return "caught"
    return f"harness error (pytest exit {code})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run one mutant that breaks collection; pass when it is reported as a harness error",
    )
    args = parser.parse_args()
    mutants = (SELFTEST,) if args.selftest else MUTANTS

    env = {**os.environ, "PYTHONPATH": "src", "COLUMNS": "200"}
    env.pop("PYTEST_ADDOPTS", None)
    command = [args.python, "-m", "pytest", *TESTS, "-q", "-x", "-p", "no:cacheprovider"]
    command += ["-o", "addopts="]

    baseline = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
    if baseline.returncode != 0:
        print(f"the unmutated tests do not pass (pytest exit {baseline.returncode})")
        return 1

    lines = ["mutant\tfile\tprediction\toutcome\tmatches\tpytest\twhy"]
    outcomes: list[str] = []
    against = 0
    for mutant in mutants:
        target = args.root / mutant.path
        original = target.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        text = original.decode("utf-8")
        count = text.count(mutant.old)
        if count != 1:
            raise SystemExit(f"{mutant.name}: the text occurs {count} times in {mutant.path}")
        try:
            target.write_bytes(text.replace(mutant.old, mutant.new).encode("utf-8"))
            done = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True)
        finally:
            target.write_bytes(original)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{mutant.name}: {mutant.path} was not restored")
        outcome = classify(done.returncode)
        outcomes.append(outcome)
        matches = outcome.split(" (")[0] == mutant.prediction
        against += 0 if matches else 1
        tail = done.stdout.strip().splitlines()[-1].strip("= ") if done.stdout.strip() else ""
        lines.append(
            f"{mutant.name}\t{mutant.path}\t{mutant.prediction}\t{outcome}\t{matches}\t{tail}"
            f"\t{mutant.why}"
        )
        print(lines[-1], flush=True)

    caught = outcomes.count("caught")
    survived = outcomes.count("survived")
    errors = len(outcomes) - caught - survived
    summary = (
        f"{len(mutants)} mutants: {caught} caught, {survived} survived, {errors} harness errors, "
        f"{against} against the prediction"
    )
    lines.append(summary)
    print(summary)
    if args.selftest:
        seen = errors == 1 and outcomes[0].startswith("harness error")
        verdict = "self-test passes" if seen else "SELF-TEST FAILS"
        lines.append(f"{verdict}: a run pytest could not judge is not counted as caught")
        print(lines[-1])
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return 0 if seen else 1
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 1 if against or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
