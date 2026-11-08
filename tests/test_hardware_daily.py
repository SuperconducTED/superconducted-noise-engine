"""Tests for one morning of the #125 run (scripts/hardware_daily.py).

The steps are recorded by a scripted runner, except the watchdog's own tests, which start real
processes because a time limit and a kill are what they check.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import scripts.hardware_daily as daily

FIRST = date(2026, 11, 10)
MORNING_TIME = (3, 45, 5)


def _at(day: int) -> datetime:
    return datetime(2026, 11, 10, *MORNING_TIME, tzinfo=UTC) + timedelta(days=day - 1)


class Runner:
    """Records each command; answers with a chosen exit code per step."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.codes = codes or {}
        self.commands: list[list[str]] = []
        self.limits: dict[str, float] = {}

    def __call__(self, command: Sequence[str], log: Path, limit_s: float) -> int:
        del log
        text = list(command)
        self.commands.append(text)
        name = _name(text)
        self.limits[name] = limit_s
        return self.codes.get(name, 0)

    @property
    def names(self) -> list[str]:
        return [_name(c) for c in self.commands]

    def one(self, name: str) -> list[str]:
        found = [c for c in self.commands if _name(c) == name]
        assert len(found) == 1, (name, self.names)
        return found[0]


def _name(command: Sequence[str]) -> str:
    if command[0] == "git":
        return f"git {command[3]}"
    script = Path(command[1]).name
    return f"{'t1 ' if 't1' in script else ''}{command[2]}"


def _morning(tmp_path: Path, **changes: Any) -> daily.Morning:
    values: dict[str, Any] = {
        "first_day": FIRST,
        "jobs_dir": tmp_path / "jobs",
        "controls": tmp_path / "controls.json",
        "frozen_at": "f" * 40,
        "prereg": Path("docs/prereg.md"),
        "repo": tmp_path / "clone",
        "env_file": tmp_path / "clone" / ".env",
        "python": "main-python",
        "t1_python": "t1-python",
        "sealed_dir": tmp_path / "sealed",
    }
    values.update(changes)
    return daily.Morning(**values)


def _run(morning: daily.Morning, day: int, runner: Runner, **kwargs: Any) -> int:
    return daily.run_morning(morning, now=lambda: _at(day), run=runner, **kwargs)


def _submitted(tmp_path: Path, day: int, *names: str) -> Path:
    folder = tmp_path / "jobs" / (FIRST + timedelta(days=day - 1)).isoformat()
    folder.mkdir(parents=True)
    for name in names:
        (folder / name).write_text("x", encoding="utf-8")
    return folder


def test_job_numbers_follow_the_calendar() -> None:
    assert daily.job_number_on(FIRST, FIRST) == 1
    assert daily.job_number_on(FIRST + timedelta(days=13), FIRST) == 14


def test_day_one_submits_the_main_job_then_the_check_then_reports(tmp_path: Path) -> None:
    runner = Runner()
    assert _run(_morning(tmp_path), 1, runner) == 0
    assert runner.names == ["build", "t1 submit", "report"]
    build = runner.one("build")
    assert build[0] == "main-python"
    assert build[build.index("--job-number") + 1] == "1"
    assert build[build.index("--frozen-at") + 1] == "f" * 40
    t1 = runner.one("t1 submit")
    assert t1[0] == "t1-python"
    assert t1[t1.index("--job-dir") + 1] == str(tmp_path / "jobs" / "2026-11-10")
    assert t1[t1.index("--frozen-at") + 1] == "f" * 40


@pytest.mark.parametrize(("day", "has_check"), [(2, False), (7, False), (13, False), (14, True)])
def test_only_the_first_and_last_jobs_have_a_check(
    tmp_path: Path, day: int, has_check: bool
) -> None:
    runner = Runner()
    _run(_morning(tmp_path), day, runner)
    assert ("t1 submit" in runner.names) is has_check
    build = runner.one("build")
    assert build[build.index("--job-number") + 1] == str(day)


def test_a_morning_submits_first_so_the_capture_stays_on_time(tmp_path: Path) -> None:
    """Scoring walks the archive for minutes; before ``build`` it would move every ``t_s``."""
    _submitted(tmp_path, 1, "job_id.txt")
    runner = Runner()
    _run(_morning(tmp_path), 2, runner)
    assert runner.names == ["build", "score", "report"]


def test_every_earlier_day_with_no_outcome_is_scored_oldest_first(tmp_path: Path) -> None:
    waiting_one = _submitted(tmp_path, 1, "job_id.txt")
    _submitted(tmp_path, 2, "job_id.txt", "operations.json")
    _submitted(tmp_path, 3, "job_id.txt", "failed.json")
    _submitted(tmp_path, 4, "missed.json")
    waiting_five = _submitted(tmp_path, 5, "job_id.txt")
    _submitted(tmp_path, 6, "job_id.txt")
    runner = Runner()
    _run(_morning(tmp_path), 6, runner)
    assert [c[c.index("--job-dir") + 1] for c in runner.commands if _name(c) == "score"] == [
        str(waiting_one),
        str(waiting_five),
    ]


def test_only_day_folders_are_scored(tmp_path: Path) -> None:
    """A stray folder that sorts before today, with a job id in it, is not a day of the run."""
    stray = tmp_path / "jobs" / "0-stray"
    stray.mkdir(parents=True)
    (stray / "job_id.txt").write_text("x", encoding="utf-8")
    (stray / "t1-job_id.txt").write_text("x", encoding="utf-8")
    runner = Runner()
    _run(_morning(tmp_path), 3, runner)
    assert "score" not in runner.names
    assert "t1 score" not in runner.names


def test_the_check_is_scored_on_a_later_morning(tmp_path: Path) -> None:
    folder = _submitted(tmp_path, 1, "job_id.txt", "operations.json", "t1-job_id.txt")
    _submitted(tmp_path, 2, "t1-job_id.txt", "t1-operations.json")
    _submitted(tmp_path, 3, "t1-job_id.txt", "t1-failed.json")
    runner = Runner()
    _run(_morning(tmp_path), 5, runner)
    command = runner.one("t1 score")
    assert command[0] == "t1-python"
    assert command[command.index("--job-dir") + 1] == str(folder)


def test_a_check_submitted_today_is_not_scored_today(tmp_path: Path) -> None:
    _submitted(tmp_path, 3, "t1-job_id.txt", "job_id.txt")
    runner = Runner()
    _run(_morning(tmp_path), 3, runner)
    assert "t1 score" not in runner.names
    assert "score" not in runner.names


def _sealed_scores(tmp_path: Path) -> Path:
    day = tmp_path / "sealed" / FIRST.isoformat()
    day.mkdir(parents=True)
    (day / "arm-a.tsv").write_text("scores", encoding="utf-8")
    (tmp_path / "sealed" / "report.json").write_text("{}", encoding="utf-8")
    return tmp_path / "sealed"


def test_day_fifteen_scores_and_reports_but_submits_nothing(tmp_path: Path) -> None:
    _submitted(tmp_path, 14, "job_id.txt", "t1-job_id.txt")
    _sealed_scores(tmp_path)
    runner = Runner()
    assert _run(_morning(tmp_path), 15, runner) == 0
    assert runner.names == ["score", "t1 score", "report"]


def test_day_fifteen_unseals_after_the_report_and_before_the_commit(tmp_path: Path) -> None:
    """Amendment 27: the scores join the data branch only once the run is over."""
    _submitted(tmp_path, 14, "job_id.txt", "t1-job_id.txt")
    _sealed_scores(tmp_path)
    runner = Runner()
    assert _run(_morning(tmp_path, commit_data=True), 15, runner) == 0
    assert runner.names == ["score", "t1 score", "report", "git add", "git commit"]
    written = json.loads((tmp_path / "jobs" / "routine-2026-11-24.json").read_text("utf-8"))
    assert [s["name"] for s in written["steps"]][-2:] == ["report", "unseal"]
    unsealed = tmp_path / "jobs" / "sealed"
    assert (unsealed / FIRST.isoformat() / "arm-a.tsv").read_text("utf-8") == "scores"
    assert (unsealed / "report.json").exists()


@pytest.mark.parametrize("day", [1, 2, 7, 14])
def test_no_day_before_fifteen_unseals(tmp_path: Path, day: int) -> None:
    _sealed_scores(tmp_path)
    runner = Runner()
    _run(_morning(tmp_path, commit_data=True), day, runner)
    assert not (tmp_path / "jobs" / "sealed").exists()
    written = json.loads(
        (
            tmp_path / "jobs" / f"routine-{(FIRST + timedelta(days=day - 1)).isoformat()}.json"
        ).read_text("utf-8")
    )
    assert "unseal" not in [s["name"] for s in written["steps"]]


def test_day_fifteen_without_a_sealed_folder_is_not_a_clean_morning(tmp_path: Path) -> None:
    _submitted(tmp_path, 14, "job_id.txt", "t1-job_id.txt")
    assert _run(_morning(tmp_path), 15, Runner()) == 1
    assert not (tmp_path / "jobs" / "sealed").exists()


@pytest.mark.parametrize("day", [0, -3, 16, 40])
def test_outside_the_run_nothing_happens_at_all(tmp_path: Path, day: int) -> None:
    runner = Runner()
    assert _run(_morning(tmp_path), day, runner) == 0
    assert runner.names == []
    assert not (tmp_path / "jobs").exists()


def test_a_refused_build_costs_no_scores_and_is_reported_as_a_failure(tmp_path: Path) -> None:
    _submitted(tmp_path, 1, "job_id.txt")
    runner = Runner({"build": daily.EXIT_REFUSED})
    assert _run(_morning(tmp_path), 2, runner) == 1
    assert runner.names == ["build", "score", "report"]


def test_a_check_is_not_submitted_when_the_main_job_was_refused(tmp_path: Path) -> None:
    runner = Runner({"build": daily.EXIT_REFUSED})
    _run(_morning(tmp_path), 1, runner)
    assert runner.names == ["build", "report"]


def test_a_step_that_hit_its_limit_is_a_failure_and_the_rest_still_run(tmp_path: Path) -> None:
    _submitted(tmp_path, 1, "job_id.txt")
    runner = Runner({"score": daily.EXIT_TIMED_OUT})
    assert _run(_morning(tmp_path), 2, runner) == 1
    assert runner.names[-1] == "report"


def test_a_job_not_ready_to_score_is_not_a_failure(tmp_path: Path) -> None:
    _submitted(tmp_path, 1, "job_id.txt", "t1-job_id.txt")
    runner = Runner({"score": daily.EXIT_NOT_YET, "t1 score": daily.EXIT_NOT_YET})
    assert _run(_morning(tmp_path), 2, runner) == 0


def test_a_report_that_fails_is_a_failure(tmp_path: Path) -> None:
    assert _run(_morning(tmp_path), 2, Runner({"report": 1})) == 1


def test_every_step_has_its_limit(tmp_path: Path) -> None:
    _submitted(tmp_path, 1, "job_id.txt", "t1-job_id.txt")
    runner = Runner()
    _run(_morning(tmp_path, commit_data=True, push_data=True), 2, runner)
    assert runner.limits == {
        "build": daily.BUILD_LIMIT_S,
        "score": daily.SCORE_LIMIT_S,
        "t1 score": daily.T1_LIMIT_S,
        "report": daily.REPORT_LIMIT_S,
        "git add": daily.GIT_LIMIT_S,
        "git commit": daily.GIT_LIMIT_S,
        "git push": daily.GIT_LIMIT_S,
    }


def test_the_report_gets_the_declared_first_day(tmp_path: Path) -> None:
    runner = Runner()
    _run(_morning(tmp_path), 3, runner)
    report = runner.one("report")
    assert report[report.index("--first-day") + 1] == "2026-11-10"
    assert report[report.index("--today") + 1] == "2026-11-12"


def test_the_morning_is_recorded(tmp_path: Path) -> None:
    runner = Runner({"build": 2})
    _run(_morning(tmp_path), 3, runner)
    written = json.loads(
        (tmp_path / "jobs" / "routine-2026-11-12.json").read_text(encoding="utf-8")
    )
    assert written["job_number"] == 3
    assert written["steps"] == [{"name": "build", "exit": 2}, {"name": "report", "exit": 0}]


def test_nothing_is_committed_or_pushed_unless_asked(tmp_path: Path) -> None:
    runner = Runner()
    _run(_morning(tmp_path), 2, runner)
    assert not [n for n in runner.names if n.startswith("git")]


def test_committing_does_not_push_unless_asked(tmp_path: Path) -> None:
    runner = Runner()
    _run(_morning(tmp_path, commit_data=True), 2, runner)
    assert runner.names[-2:] == ["git add", "git commit"]


def test_the_days_outputs_are_committed_and_pushed_last_when_asked(tmp_path: Path) -> None:
    runner = Runner()
    _run(_morning(tmp_path, commit_data=True, push_data=True), 2, runner)
    assert runner.names == ["build", "report", "git add", "git commit", "git push"]
    assert runner.one("git add")[2] == str(tmp_path / "jobs")


def test_a_rehearsal_passes_its_clock_and_skips_the_freeze_flags(tmp_path: Path) -> None:
    live = tmp_path / "live.json"
    execute = _at(1) + timedelta(hours=2)
    morning = _morning(
        tmp_path,
        frozen_at=None,
        prereg=None,
        rehearsal=daily.Rehearsal(_at(1), live, execute, "b" * 40),
    )
    runner = Runner()
    assert daily.run_morning(morning, now=lambda: _at(1), run=runner) == 0
    build = runner.one("build")
    assert "--frozen-at" not in build
    assert build[build.index("--local-live") + 1] == str(live)
    assert build[build.index("--at") + 1] == _at(1).isoformat()
    assert build[build.index("--ref") + 1] == "b" * 40
    check = runner.one("t1 submit")
    assert "--frozen-at" not in check
    assert check[check.index("--local-execute-at") + 1] == execute.isoformat()
    assert "--at" not in check
    assert "--ref" not in check


def test_a_rehearsal_never_waits_for_the_window(tmp_path: Path) -> None:
    early = datetime(2026, 11, 10, 3, 44, 30, tzinfo=UTC)  # a real morning would wait 30 s here
    morning = _morning(
        tmp_path, rehearsal=daily.Rehearsal(early, tmp_path / "l.json", early, "b" * 40)
    )
    waits: list[float] = []
    daily.run_morning(morning, now=lambda: early, run=Runner(), sleep=waits.append)
    assert waits == []


# --- the window ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "minute", "second", "expected"),
    [
        (3, 44, 30, [30.0]),
        (3, 30, 0, [900.0]),
        (3, 29, 59, []),
        (3, 45, 0, []),
        (3, 46, 0, []),
        (8, 0, 0, []),
    ],
)
def test_a_task_firing_a_moment_early_waits_for_the_window(
    hour: int, minute: int, second: int, expected: list[float]
) -> None:
    at = datetime(2026, 11, 10, hour, minute, second, tzinfo=UTC)
    waits: list[float] = []
    daily._wait_for_window(lambda: at, waits.append, daily.LONGEST_WAIT_FOR_WINDOW_S)
    assert waits == expected


# --- the watchdog, with real processes ----------------------------------------------------------


def test_a_step_past_its_limit_is_killed(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    code = daily.run_step(
        [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(120)"],
        log,
        3.0,
    )
    assert code == daily.EXIT_TIMED_OUT
    assert "started" in log.read_text(encoding="utf-8")


def test_a_steps_child_dies_with_it(tmp_path: Path) -> None:
    """The hang on 2026-11-05 was a waiting ``git``: the step's children must go too."""
    marker = tmp_path / "pid.txt"
    child = "import time; time.sleep(120)"
    parent = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', {child!r}])\n"
        f"open({str(marker)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(120)\n"
    )
    code = daily.run_step([sys.executable, "-c", parent], tmp_path / "log.txt", 4.0)
    assert code == daily.EXIT_TIMED_OUT
    pid = int(marker.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 10.0
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _alive(pid)


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        import subprocess

        listed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, check=True
        ).stdout
        return str(pid) in listed
    # A killed process stays listed as a zombie until something reaps it, so read its state.
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def test_a_finished_step_returns_its_own_exit_code(tmp_path: Path) -> None:
    assert daily.run_step([sys.executable, "-c", "raise SystemExit(7)"], tmp_path / "l", 30.0) == 7


def test_a_step_writing_a_lot_cannot_block_on_a_pipe(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    code = daily.run_step(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 5_000_000)"], log, 30.0
    )
    assert code == 0
    assert log.stat().st_size == 5_000_000


def test_each_step_adds_to_the_same_log(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    for word in ("one", "two"):
        daily.run_step([sys.executable, "-c", f"print({word!r})"], log, 30.0)
    assert log.read_text(encoding="utf-8").split() == ["one", "two"]


# --- the command line ---------------------------------------------------------------------------


def _argv(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "--first-day",
        "2026-11-10",
        "--jobs-dir",
        str(tmp_path / "jobs"),
        "--controls",
        str(tmp_path / "controls.json"),
        "--t1-python",
        "t1-python",
        "--sealed-dir",
        str(tmp_path / "sealed"),
        *extra,
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="the hold is a Windows call")
def test_the_morning_holds_the_machine_awake_before_anything_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[Any] = []

    class Kernel:
        def SetThreadExecutionState(self, flags: int) -> int:  # noqa: N802
            order.append(flags)
            return 0

    class Windll:
        kernel32 = Kernel()

    def morning(*args: Any, **kwargs: Any) -> int:
        del args, kwargs
        order.append("morning")
        return 0

    monkeypatch.setattr(daily.ctypes, "windll", Windll())
    monkeypatch.setattr(daily, "run_morning", morning)
    assert daily.main(_argv(tmp_path, "--frozen-at", "f" * 40, "--prereg", "p.md")) == 0
    assert order == [0x80000001, "morning"]


def test_a_real_morning_needs_the_frozen_commit(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        daily.main(_argv(tmp_path))


def test_a_partial_rehearsal_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        daily.main(_argv(tmp_path, "--at", "2026-11-10T03:45:00+00:00"))


@pytest.mark.parametrize("inside", ["jobs", "jobs/sealed", "clone", "clone/out/sealed"])
def test_a_sealed_folder_inside_the_jobs_folder_or_the_clone_is_refused(
    tmp_path: Path, inside: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[Any] = []
    monkeypatch.setattr(daily, "run_morning", lambda *a, **k: ran.append(a) or 0)
    argv = _argv(tmp_path, "--frozen-at", "f" * 40, "--prereg", "p.md")
    argv[argv.index("--sealed-dir") + 1] = str(tmp_path / inside)
    with pytest.raises(SystemExit):
        daily.main([*argv, "--repo", str(tmp_path / "clone")])
    assert ran == []


def test_pushing_needs_committing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        daily.main(_argv(tmp_path, "--frozen-at", "f" * 40, "--prereg", "p.md", "--push-data"))


def test_the_routine_never_opens_the_token_file(tmp_path: Path) -> None:
    runner = Runner()
    env = tmp_path / "clone" / ".env"
    _run(_morning(tmp_path, env_file=env), 2, runner)
    assert not env.exists()
    build = runner.one("build")
    assert build[build.index("--env-file") + 1] == str(env)
