"""Day 15 is final, and the sealed folder stays apart (criteria 42 to 45 of the 2026-11-23 section).

Both defects of the review of `1ec698f8` are kept here as tests: a day 15 that closes on an
unscorable job, and a sealed folder that contains the jobs folder. The routine's steps are
recorded by a scripted runner; `run_report` and the three entry points are the real code.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import scripts.hardware_daily as daily
import scripts.hardware_submit as submit
import scripts.hardware_t1_check as t1

FIRST = date(2026, 11, 10)
LAST = FIRST + timedelta(days=submit.N_JOBS - 1)
DAY_15 = LAST + timedelta(days=1)


def _at(day: int) -> datetime:
    return datetime(2026, 11, 10, 3, 45, 5, tzinfo=UTC) + timedelta(days=day - 1)


class Runner:
    """Records each step's name; answers with a chosen exit code per step."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.codes = codes or {}
        self.names: list[str] = []

    def __call__(self, command: Sequence[str], log: Path, limit_s: float) -> int:
        del log, limit_s
        if command[0] == "git":
            name = f"git {command[3]}"
        else:
            name = f"{'t1 ' if 't1' in Path(command[1]).name else ''}{command[2]}"
        self.names.append(name)
        return self.codes.get(name, 0)


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


def _run(tmp_path: Path, day: int, runner: Runner, **changes: Any) -> int:
    return daily.run_morning(_morning(tmp_path, **changes), now=lambda: _at(day), run=runner)


def _day(tmp_path: Path, day: int, *names: str) -> Path:
    folder = tmp_path / "jobs" / (FIRST + timedelta(days=day - 1)).isoformat()
    folder.mkdir(parents=True)
    for name in names:
        (folder / name).write_text("{}", encoding="utf-8")
    return folder


def _run_of_fourteen(tmp_path: Path, *, last_scored: bool) -> None:
    """Fourteen submitted days; the first and the last carry a ``T1`` check."""
    _day(tmp_path, 1, "job_id.txt", "operations.json", "t1-job_id.txt", "t1-operations.json")
    for day in range(2, submit.N_JOBS):
        _day(tmp_path, day, "job_id.txt", "operations.json")
    done = ("operations.json", "t1-operations.json") if last_scored else ()
    _day(tmp_path, submit.N_JOBS, "job_id.txt", "t1-job_id.txt", *done)
    (tmp_path / "sealed").mkdir()


def _closed(tmp_path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((tmp_path / "jobs" / "closed.json").read_text("utf-8"))
    return loaded


def _report(tmp_path: Path, today: date) -> dict[str, Any]:
    return submit.run_report(
        tmp_path / "jobs", first_day=FIRST, today=today, scores_dir=tmp_path / "sealed"
    )


NOT_READY = {"score": daily.EXIT_NOT_YET, "t1 score": daily.EXIT_NOT_YET}


# --- criterion 43: day 15 closes the run and names what it could not score ---------------------


def test_day_fifteen_names_the_job_and_the_check_it_could_not_score(tmp_path: Path) -> None:
    """The review's first finding: at `1ec698f8` nothing named them, and the report said complete."""
    _run_of_fourteen(tmp_path, last_scored=False)
    runner = Runner(NOT_READY)
    assert _run(tmp_path, 15, runner) == 0  # a defined outcome, not a failure of the routine
    assert runner.names == ["score", "t1 score", "report"]
    unscored = {"days": [LAST.isoformat()], "t1_checks": [LAST.isoformat()]}
    assert _closed(tmp_path) == {"closed_on": DAY_15.isoformat(), "closed_unscored": unscored}
    record = json.loads(
        (tmp_path / "jobs" / f"routine-{DAY_15.isoformat()}.json").read_text("utf-8")
    )
    assert record["closed_unscored"] == unscored
    report = _report(tmp_path, DAY_15)
    assert report["complete"] is True
    assert report["closed_unscored"] == unscored
    assert report["days"][-1] == {"date": LAST.isoformat(), "status": "submitted, not scored"}


def test_day_fifteen_with_everything_scored_closes_with_two_empty_lists(tmp_path: Path) -> None:
    _run_of_fourteen(tmp_path, last_scored=True)
    runner = Runner()
    assert _run(tmp_path, 15, runner) == 0
    assert runner.names == ["report"]
    assert _closed(tmp_path)["closed_unscored"] == {"days": [], "t1_checks": []}
    assert _report(tmp_path, DAY_15)["closed_unscored"] == {"days": [], "t1_checks": []}


def test_a_failed_day_and_a_failed_check_are_outcomes_not_unscored(tmp_path: Path) -> None:
    _run_of_fourteen(tmp_path, last_scored=False)
    last = tmp_path / "jobs" / LAST.isoformat()
    (last / "failed.json").write_text("{}", encoding="utf-8")
    (last / "t1-failed.json").write_text("{}", encoding="utf-8")
    assert _report(tmp_path, DAY_15)["closed_unscored"] == {"days": [], "t1_checks": []}


def test_the_job_and_the_check_are_listed_separately(tmp_path: Path) -> None:
    _run_of_fourteen(tmp_path, last_scored=False)
    (tmp_path / "jobs" / LAST.isoformat() / "operations.json").write_text("{}", encoding="utf-8")
    listed = _report(tmp_path, DAY_15)["closed_unscored"]
    assert listed == {"days": [], "t1_checks": [LAST.isoformat()]}


@pytest.mark.parametrize("day", [1, 7, 14])
def test_before_day_fifteen_nothing_is_closed(tmp_path: Path, day: int) -> None:
    (tmp_path / "sealed").mkdir()
    today = FIRST + timedelta(days=day - 1)
    assert _run(tmp_path, day, Runner()) == 0
    assert not (tmp_path / "jobs" / "closed.json").exists()
    record = json.loads(
        (tmp_path / "jobs" / f"routine-{today.isoformat()}.json").read_text("utf-8")
    )
    assert "closed_unscored" not in record
    report = _report(tmp_path, today)
    assert report["complete"] is False
    assert report["closed_unscored"] is None


def test_the_run_is_closed_before_the_scores_are_opened(tmp_path: Path) -> None:
    """``closed.json`` is written even when there is no sealed folder to open."""
    _day(tmp_path, submit.N_JOBS, "job_id.txt")
    assert _run(tmp_path, 15, Runner(NOT_READY)) == 1  # the unseal found nothing: not clean
    assert _closed(tmp_path)["closed_unscored"]["days"] == [LAST.isoformat()]
    assert not (tmp_path / "jobs" / "sealed").exists()


# --- criterion 44: nothing is scored after the run is closed ------------------------------------


@pytest.mark.parametrize("day", [2, 15, 16])
def test_a_morning_with_the_run_closed_runs_no_step(tmp_path: Path, day: int) -> None:
    _run_of_fourteen(tmp_path, last_scored=False)
    (tmp_path / "jobs" / "closed.json").write_text('{"closed_on": "2026-11-24"}', encoding="utf-8")
    runner = Runner()
    assert _run(tmp_path, day, runner) == 0
    assert runner.names == []
    assert not list((tmp_path / "jobs").glob("routine-*.json"))


def test_day_sixteen_after_a_real_day_fifteen_scores_nothing(tmp_path: Path) -> None:
    """The review's first finding, second half: the late job is not picked up the next morning."""
    _run_of_fourteen(tmp_path, last_scored=False)
    assert _run(tmp_path, 15, Runner(NOT_READY)) == 0
    runner = Runner()
    assert _run(tmp_path, 16, runner) == 0
    assert runner.names == []
    assert daily.days_to_score(tmp_path / "jobs", DAY_15) != []  # still unscored, by rule


def _closed_run(tmp_path: Path) -> Path:
    job = _day(tmp_path, submit.N_JOBS, "job_id.txt", "t1-job_id.txt")
    (tmp_path / "jobs" / "closed.json").write_text('{"closed_on": "2026-11-24"}', encoding="utf-8")
    return job


def _no_network(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError(f"reached the network or the token: {args} {kwargs}")


def test_the_main_score_refuses_a_closed_run_before_any_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    job = _closed_run(tmp_path)
    monkeypatch.setattr(submit, "_fetch_archive", _no_network)
    monkeypatch.setattr(submit, "ibm_device", _no_network)
    argv = ["score", "--job-dir", str(job), "--sealed-dir", str(tmp_path / "sealed")]
    assert submit.main([*argv, "--repo", str(tmp_path / "clone")]) == submit.EXIT_REFUSED
    assert "the run was closed on 2026-11-24" in capsys.readouterr().err
    assert not (job / "operations.json").exists()


def test_the_check_score_refuses_a_closed_run_before_any_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    job = _closed_run(tmp_path)
    monkeypatch.setattr(t1, "ibm_device", _no_network)
    argv = ["score", "--job-dir", str(job), "--sealed-dir", str(tmp_path / "sealed")]
    assert t1.main([*argv, "--repo", str(tmp_path / "clone")]) == t1.EXIT_REFUSED
    assert "the run was closed on 2026-11-24" in capsys.readouterr().err
    assert not (job / "t1-operations.json").exists()


def test_an_open_run_is_not_refused_as_closed(tmp_path: Path) -> None:
    (tmp_path / "jobs").mkdir()
    submit.refuse_closed_run(tmp_path / "jobs")  # no marker: nothing raised


# --- criterion 42: the sealed folder is not, is not inside, and does not contain the others -----


@pytest.mark.parametrize(
    ("sealed", "other", "says"),
    [
        ("jobs", "jobs", "is inside"),
        ("jobs/sealed", "jobs", "is inside"),
        (".", "jobs", "contains"),
        ("data", "data/run/jobs", "contains"),
    ],
    ids=["same", "inside", "parent", "ancestor"],
)
def test_the_three_relations_are_refused(
    tmp_path: Path, sealed: str, other: str, says: str
) -> None:
    with pytest.raises(submit.RefusedError, match=says):
        submit.refuse_sealed_inside(tmp_path / sealed, tmp_path / "elsewhere", tmp_path / other)


def test_a_sibling_sealed_folder_is_accepted(tmp_path: Path) -> None:
    submit.refuse_sealed_inside(tmp_path / "sealed", tmp_path / "jobs", tmp_path / "clone")
    # A shared name prefix is not containment.
    submit.refuse_sealed_inside(tmp_path / "jobs-sealed", tmp_path / "jobs")


def _routine_argv(tmp_path: Path, *, jobs: str, sealed: str, clone: str) -> list[str]:
    return [
        *("--first-day", "2026-11-10", "--controls", str(tmp_path / "controls.json")),
        *("--t1-python", "t1-python", "--frozen-at", "f" * 40, "--prereg", "p.md"),
        *("--jobs-dir", str(tmp_path / jobs), "--sealed-dir", str(tmp_path / sealed)),
        *("--repo", str(tmp_path / clone)),
    ]


@pytest.mark.parametrize(
    ("jobs", "sealed", "clone"),
    [
        ("data/jobs", "data", "clone"),  # the sealed folder contains the jobs folder
        ("jobs", "work", "work/clone"),  # ... or the clone
        ("jobs", ".", "clone"),  # ... or both
    ],
    ids=["contains jobs", "contains clone", "contains both"],
)
def test_the_routine_refuses_a_sealed_folder_that_contains_the_jobs_folder_or_the_clone(
    tmp_path: Path, jobs: str, sealed: str, clone: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's second finding: at `1ec698f8` this was accepted."""
    ran: list[Any] = []
    monkeypatch.setattr(daily, "run_morning", lambda *a, **k: ran.append(a) or 0)
    with pytest.raises(SystemExit):
        daily.main(_routine_argv(tmp_path, jobs=jobs, sealed=sealed, clone=clone))
    assert ran == []


def test_the_routine_accepts_three_sibling_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[Any] = []
    monkeypatch.setattr(daily, "run_morning", lambda *a, **k: ran.append(a) or 0)
    monkeypatch.setattr(daily, "_stay_awake", lambda: None)
    assert daily.main(_routine_argv(tmp_path, jobs="jobs", sealed="sealed", clone="clone")) == 0
    assert len(ran) == 1


def test_both_scorers_and_the_report_refuse_a_sealed_folder_that_contains_the_jobs_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = tmp_path / "data" / "jobs" / LAST.isoformat()
    job.mkdir(parents=True)
    monkeypatch.setattr(submit, "_fetch_archive", _no_network)
    monkeypatch.setattr(submit, "ibm_device", _no_network)
    monkeypatch.setattr(t1, "ibm_device", _no_network)
    sealed, clone = str(tmp_path / "data"), str(tmp_path / "clone")
    score = ["score", "--job-dir", str(job), "--sealed-dir", sealed, "--repo", clone]
    assert submit.main(score) == submit.EXIT_REFUSED
    assert t1.main(score) == t1.EXIT_REFUSED
    report = ["report", "--jobs-dir", str(job.parent), "--first-day", FIRST.isoformat()]
    assert submit.main([*report, "--sealed-dir", sealed]) == submit.EXIT_REFUSED
    assert not (tmp_path / "data" / "report.json").exists()


@pytest.mark.parametrize("layout", ["parent", "same"])
def test_unseal_refuses_to_copy_the_sealed_folder_into_itself(tmp_path: Path, layout: str) -> None:
    """At `1ec698f8` the parent layout recursed until the path limit or the recursion limit."""
    sealed = tmp_path / "sealed"
    jobs = sealed / "jobs" if layout == "parent" else sealed.parent / "jobs"
    if layout == "same":
        sealed = jobs / "sealed"
    sealed.mkdir(parents=True)
    jobs.mkdir(parents=True, exist_ok=True)
    (sealed / "report.json").write_text("{}", encoding="utf-8")
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert daily.unseal(sealed, jobs) == daily.EXIT_REFUSED
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == before
