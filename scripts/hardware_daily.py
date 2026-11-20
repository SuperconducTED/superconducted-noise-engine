"""One morning of the #125 run, fired by the scheduled task: submit, score earlier days, report.

    python scripts/hardware_daily.py --first-day 2026-MM-DD --jobs-dir <folder outside the clone> \\
        --controls <controls.json> --frozen-at <sha> --prereg <path> --t1-python <interpreter> \\
        --sealed-dir <folder outside the jobs folder and the clone>

**Order.** ``build`` runs first because its capture instant is the day's ``t_s``, and ``score``
walks the archive for minutes. The ``T1`` check of design section 6 follows on the first and
last jobs.
Earlier days are then scored, the report is rewritten, and the day's outputs are committed if asked.
A step that fails is logged and the later steps still run: a refused ``build`` must not cost
yesterday's scores.

**Watchdog.** Every step runs in its own process with a time limit, killed with its children when
the limit passes, because on 2026-11-05 a hung run looked exactly like a working one for two hours.
Output goes to a log file, never to a pipe: the same hang was a ``MemoryError`` in a pipe's reader
thread.

**Calendar.** Job ``n`` runs on the run's day ``n``, whatever happened on the days before. Day 15
only scores and reports, and from day 16 on the routine does nothing, so a task left registered
cannot extend the run.

**Sealed.** Scores, raw counts and ``T1`` fits go to ``--sealed-dir``, outside the jobs folder (the
data branch's worktree) and outside the clone, so nothing a morning commits or logs carries one
(amendment 27). The jobs folder gets each day's ``operations.json``: that the job ran, when, and
how many rows it scored. Day 15 copies the sealed folder into ``jobs/sealed`` before the commit.

The token stays in the ``.env`` the two scripts read: this one only passes on the file's path.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time as clock
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from scripts.hardware_submit import (
    EXIT_NOT_YET,
    EXIT_REFUSED,
    N_JOBS,
    SUBMISSION_TIME,
)

__all__ = [
    "EXIT_NOT_YET",
    "EXIT_REFUSED",
    "Morning",
    "Rehearsal",
    "main",
    "run_morning",
    "run_step",
]

SCRIPTS = Path(__file__).resolve().parent
BUILD_LIMIT_S = 40 * 60
SCORE_LIMIT_S = 40 * 60
T1_LIMIT_S = 15 * 60
REPORT_LIMIT_S = 5 * 60
GIT_LIMIT_S = 5 * 60
LONGEST_WAIT_FOR_WINDOW_S = 15 * 60
EXIT_TIMED_OUT = -1
T1_JOBS = frozenset({1, N_JOBS})
DAY_FOLDER = re.compile(r"\d{4}-\d{2}-\d{2}")
# A job not ready to score is the normal answer on some mornings. A refused build is not: it means
# no job today, and whoever reads the task's last result should see that.
ALLOWED = {
    "score": {0, EXIT_NOT_YET},
    "t1 score": {0, EXIT_NOT_YET},
}

Runner = Callable[[Sequence[str], Path, float], int]


@dataclass(frozen=True)
class Rehearsal:
    """The clock and the simulator of a run that spends nothing. ``ref`` pins the archive."""

    at: datetime
    live: Path
    execute_at: datetime
    ref: str


@dataclass(frozen=True)
class Morning:
    first_day: date
    jobs_dir: Path
    controls: Path
    frozen_at: str | None
    prereg: Path | None
    repo: Path
    env_file: Path
    python: str
    t1_python: str
    # Amendment 27: scores, counts and fits, outside the jobs folder and the clone; the jobs
    # folder is the data branch's worktree, and on day 15 this folder is copied into it.
    sealed_dir: Path
    commit_data: bool = False
    push_data: bool = False
    rehearsal: Rehearsal | None = None


def _stay_awake() -> None:
    """Hold the machine awake until this process ends.

    A wake timer wakes a sleeping laptop, but Windows puts an unattended machine back to sleep
    within minutes unless a process says it is working. The hold ends with the process.
    """
    if sys.platform == "win32":
        es_continuous, es_system_required = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    """A step's own children, ``git`` above all, must not outlive the limit."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # ``run_step`` made the step the leader of its own session, so its group is its children.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    process.kill()
    process.wait()


def run_step(command: Sequence[str], log: Path, limit_s: float) -> int:
    """Run one step with its output in ``log``. Returns its exit code, or ``EXIT_TIMED_OUT``."""
    with log.open("ab") as handle:
        process = subprocess.Popen(
            list(command),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=sys.platform != "win32",
        )
        try:
            return process.wait(timeout=limit_s)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            return EXIT_TIMED_OUT


def job_number_on(day: date, first_day: date) -> int:
    return (day - first_day).days + 1


def _earlier_days(jobs_dir: Path, today: date) -> list[Path]:
    if not jobs_dir.is_dir():
        return []
    return sorted(
        p
        for p in jobs_dir.iterdir()
        if p.is_dir() and DAY_FOLDER.fullmatch(p.name) and p.name < today.isoformat()
    )


def _awaits_score(job_dir: Path) -> bool:
    return (
        (job_dir / "job_id.txt").exists()
        and not (job_dir / "operations.json").exists()
        and not (job_dir / "failed.json").exists()
    )


def _check_awaits_score(job_dir: Path) -> bool:
    return (
        (job_dir / "t1-job_id.txt").exists()
        and not (job_dir / "t1-operations.json").exists()
        and not (job_dir / "t1-failed.json").exists()
    )


def days_to_score(jobs_dir: Path, today: date) -> list[Path]:
    """Earlier days with a submitted job and no outcome yet, oldest first."""
    return [p for p in _earlier_days(jobs_dir, today) if _awaits_score(p)]


def t1_to_score(jobs_dir: Path, today: date) -> list[Path]:
    return [p for p in _earlier_days(jobs_dir, today) if _check_awaits_score(p)]


def _rehearsal_flags(morning: Morning) -> list[str]:
    if morning.rehearsal is None:
        return []
    r = morning.rehearsal
    return [
        "--local-live",
        str(r.live),
        "--at",
        r.at.isoformat(),
        "--local-execute-at",
        r.execute_at.isoformat(),
        "--ref",
        r.ref,
    ]


def _t1_rehearsal_flags(morning: Morning) -> list[str]:
    if morning.rehearsal is None:
        return []
    r = morning.rehearsal
    return ["--local-live", str(r.live), "--local-execute-at", r.execute_at.isoformat()]


def _shared_flags(morning: Morning) -> list[str]:
    return ["--repo", str(morning.repo), "--env-file", str(morning.env_file)]


def _frozen_flags(morning: Morning) -> list[str]:
    if morning.rehearsal is not None:
        return []
    return ["--frozen-at", str(morning.frozen_at), "--prereg", str(morning.prereg)]


def _wait_for_window(
    now: Callable[[], datetime], sleep: Callable[[float], None], limit_s: float
) -> None:
    """The task can fire a moment early, and the guard refuses anything before the window."""
    current = now()
    opens = datetime.combine(current.astimezone(UTC).date(), SUBMISSION_TIME)
    wait = (opens - current).total_seconds()
    if 0.0 < wait <= limit_s:
        sleep(wait)


def unseal(sealed_dir: Path, jobs_dir: Path) -> int:
    """Copy the sealed folder into ``jobs_dir / sealed``; 0 when done, 1 when there is nothing."""
    if not sealed_dir.is_dir():
        return 1
    shutil.copytree(sealed_dir, jobs_dir / "sealed", dirs_exist_ok=True)
    return 0


def run_morning(
    morning: Morning,
    *,
    now: Callable[[], datetime],
    run: Runner = run_step,
    sleep: Callable[[float], None] = clock.sleep,
) -> int:
    """One morning. Returns 0 if every step ended in a way the rule allows, otherwise 1."""
    if morning.rehearsal is None:
        _wait_for_window(now, sleep, LONGEST_WAIT_FOR_WINDOW_S)
    started = now()
    today = started.astimezone(UTC).date()
    number = job_number_on(today, morning.first_day)
    if number < 1 or number > N_JOBS + 1:
        print(f"{today} is day {number} of a run of {N_JOBS}: nothing to do")
        return 0
    morning.jobs_dir.mkdir(parents=True, exist_ok=True)
    log = morning.jobs_dir / f"routine-{today.isoformat()}.log"
    submit = [morning.python, str(SCRIPTS / "hardware_submit.py")]
    t1_check = [morning.t1_python, str(SCRIPTS / "hardware_t1_check.py")]
    steps: list[tuple[str, int]] = []

    def step(name: str, command: Sequence[str], limit_s: float) -> int:
        code = run(command, log, limit_s)
        steps.append((name, code))
        return code

    if number <= N_JOBS:
        built = step(
            "build",
            [
                *submit,
                "build",
                "--jobs-dir",
                str(morning.jobs_dir),
                "--controls",
                str(morning.controls),
                "--job-number",
                str(number),
                *_frozen_flags(morning),
                *_shared_flags(morning),
                *_rehearsal_flags(morning),
            ],
            BUILD_LIMIT_S,
        )
        if built == 0 and number in T1_JOBS:
            step(
                "t1 submit",
                [
                    *t1_check,
                    "submit",
                    "--job-dir",
                    str(morning.jobs_dir / today.isoformat()),
                    *_frozen_flags(morning),
                    *_shared_flags(morning),
                    *_t1_rehearsal_flags(morning),
                ],
                T1_LIMIT_S,
            )
    for job_dir in days_to_score(morning.jobs_dir, today):
        step(
            "score",
            [
                *submit,
                "score",
                "--job-dir",
                str(job_dir),
                "--sealed-dir",
                str(morning.sealed_dir),
                *_shared_flags(morning),
                *_rehearsal_flags(morning),
            ],
            SCORE_LIMIT_S,
        )
    for job_dir in t1_to_score(morning.jobs_dir, today):
        step(
            "t1 score",
            [
                *t1_check,
                "score",
                "--job-dir",
                str(job_dir),
                "--sealed-dir",
                str(morning.sealed_dir),
                *_shared_flags(morning),
                *_t1_rehearsal_flags(morning),
            ],
            T1_LIMIT_S,
        )
    step(
        "report",
        [
            *submit,
            "report",
            "--jobs-dir",
            str(morning.jobs_dir),
            "--first-day",
            morning.first_day.isoformat(),
            "--today",
            today.isoformat(),
            "--sealed-dir",
            str(morning.sealed_dir),
        ],
        REPORT_LIMIT_S,
    )
    if number == N_JOBS + 1:
        # Day 15 (amendment 27): the run is over, so the sealed folder joins the data branch.
        steps.append(("unseal", unseal(morning.sealed_dir, morning.jobs_dir)))
    status = {
        "day": today.isoformat(),
        "job_number": number,
        "started": started.isoformat(),
        "steps": [{"name": name, "exit": code} for name, code in steps],
    }
    (morning.jobs_dir / f"routine-{today.isoformat()}.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if morning.commit_data:
        git = ["git", "-C", str(morning.jobs_dir)]
        step("git add", [*git, "add", "-A"], GIT_LIMIT_S)
        step(
            "git commit",
            [*git, "commit", "-m", f"data(issue-125): morning of {today.isoformat()}"],
            GIT_LIMIT_S,
        )
        if morning.push_data:
            step("git push", [*git, "push"], GIT_LIMIT_S)
    print(json.dumps(status))
    allowed_all = all(code in ALLOWED.get(name, {0}) for name, code in steps)
    return 0 if allowed_all else 1


def _parse_at(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("the time must carry a zone")
    return stamp.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--first-day", type=date.fromisoformat, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--frozen-at", default=None)
    parser.add_argument("--prereg", type=Path, default=None)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--t1-python", required=True)
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--commit-data", action="store_true")
    parser.add_argument("--push-data", action="store_true")
    parser.add_argument("--local-live", type=Path, default=None, help="rehearsal")
    parser.add_argument("--at", type=_parse_at, default=None, help="rehearsal")
    parser.add_argument("--local-execute-at", type=_parse_at, default=None, help="rehearsal")
    parser.add_argument("--ref", default=None, help="rehearsal")
    args = parser.parse_args(argv)

    flags = (args.local_live, args.at, args.local_execute_at, args.ref)
    if any(v is not None for v in flags) and any(v is None for v in flags):
        parser.error("a rehearsal needs --local-live, --at, --local-execute-at and --ref together")
    rehearsal = None
    if args.at is not None:
        rehearsal = Rehearsal(args.at, args.local_live, args.local_execute_at, args.ref)
    elif not args.frozen_at or args.prereg is None:
        parser.error("a real morning needs --frozen-at and --prereg")
    if args.push_data and not args.commit_data:
        parser.error("--push-data needs --commit-data")
    sealed = args.sealed_dir.resolve()
    for folder in (args.jobs_dir, args.repo):
        if sealed == folder.resolve() or sealed.is_relative_to(folder.resolve()):
            parser.error(f"--sealed-dir must be outside {folder}: a commit there would publish it")

    morning = Morning(
        first_day=args.first_day,
        jobs_dir=args.jobs_dir,
        controls=args.controls,
        frozen_at=args.frozen_at,
        prereg=args.prereg,
        repo=args.repo,
        env_file=args.env_file,
        python=sys.executable,
        t1_python=args.t1_python,
        sealed_dir=args.sealed_dir,
        commit_data=args.commit_data,
        push_data=args.push_data,
        rehearsal=rehearsal,
    )
    rehearsal_at = args.at
    _stay_awake()
    return run_morning(
        morning, now=(lambda: rehearsal_at) if rehearsal_at else (lambda: datetime.now(UTC))
    )


if __name__ == "__main__":
    raise SystemExit(main())
