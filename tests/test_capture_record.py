"""Tests for the daily capture record (#54).

Pinned here: which days count as settled, that a day is recorded once and only
once, that the day boundaries tile, that an empty day still leaves a row, what
counts as the pipeline's own retrieval, and that a measured day survives the job
being stopped. Each of these fails quietly if wrong: a fresh day reads low
because the sweep has not reached it, a re-recorded day counts twice, an
overlapping boundary counts one document on two days, an empty day is
re-enumerated forever, a manual backfill reads as capture, and a timeout throws
away a day already measured.
"""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest
from scripts import capture_record as cr
from scripts.capture_record import CaptureRow

TODAY = date(2026, 9, 29)
DAY = date(2026, 9, 26)
INDEX_HEADER = "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
LEDGER_HEADER = "poll_time_utc\tbackend\tlast_update_date\tdecision\n"
WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _root(
    tmp_path: Path,
    held: list[str],
    ledger: list[tuple[str, str, str]],
    dispatches: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """A data-branch root with an index, a ledger, and a dispatch listing."""
    (tmp_path / "health").mkdir(exist_ok=True)
    (tmp_path / "ledger").mkdir(exist_ok=True)
    body = "".join(f"{s}.json\t2026-09-26T00:00:00Z\td{n}\t1\n" for n, s in enumerate(held))
    (tmp_path / "health" / "state-index.tsv").write_text(INDEX_HEADER + body, encoding="utf-8")
    rows = "".join(f"{poll}\tibm_fez\t{stem}\t{decision}\n" for poll, stem, decision in ledger)
    (tmp_path / "ledger" / "2026-09.tsv").write_text(LEDGER_HEADER + rows, encoding="utf-8")
    listing = tmp_path / "dispatches.json"
    listing.write_text(json.dumps(dispatches), encoding="utf-8")
    return tmp_path, listing


A, B, C = "20260926T010000000000Z", "20260926T020000000000Z", "20260926T030000000000Z"
DISPATCH = {
    "databaseId": 1,
    "event": "workflow_dispatch",
    "status": "completed",
    "createdAt": "2026-09-27T04:00:00Z",
    "updatedAt": "2026-09-27T04:30:00Z",
}


class TestSettledDays:
    def test_the_newest_settled_day_is_three_days_back(self) -> None:
        span = cr.settled_span(TODAY)
        assert span[0] == date(2026, 9, 26)
        assert span[-1] == date(2026, 9, 20)
        assert len(span) == cr.SPAN_DAYS

    def test_pending_is_newest_first_capped_and_skips_recorded(self) -> None:
        recorded = {date(2026, 9, 25)}
        assert cr.pending_days(TODAY, recorded) == [
            date(2026, 9, 26),
            date(2026, 9, 24),
            date(2026, 9, 23),
        ]

    def test_nothing_pending_once_the_span_is_recorded(self) -> None:
        assert cr.pending_days(TODAY, cr.settled_span(TODAY)) == []


class TestDayRows:
    def test_statuses(self) -> None:
        rows = cr.day_rows(DAY, {A, B}, {A, C}, {A, C}, "0.25", "7")
        assert [(r.stem, r.status) for r in rows] == [
            (A, "captured"),
            (B, "MISSED"),
            (C, "archived_not_served"),
        ]

    def test_held_but_never_retrieved_by_a_scheduled_run_is_backfilled(self) -> None:
        """PR #105 review: the archive holds it only because a person recovered it."""
        rows = cr.day_rows(DAY, {A, B}, {A, B}, {A}, "0.25", "7")
        assert [(r.stem, r.status) for r in rows] == [(A, "captured"), (B, "backfilled")]

    def test_the_day_is_half_open_so_days_tile(self) -> None:
        """The probe window is closed; its midnight answer belongs to the next day."""
        served = {"20260926T000000000000Z", "20260927T000000000000Z"}
        rows = cr.day_rows(DAY, served, set(), set(), "0.25", "7")
        assert [r.stem for r in rows] == ["20260926T000000000000Z"]

    def test_an_empty_day_leaves_one_sentinel_row(self) -> None:
        rows = cr.day_rows(DAY, set(), set(), set(), "0.25", "7")
        assert rows == [CaptureRow(DAY, "-", False, False, False, cr.NO_DOCUMENTS, "0.25", "7")]


class TestScheduledRetrievals:
    POLLS: ClassVar[tuple[tuple[datetime, str], ...]] = (
        (_at("2026-09-26T05:07:00Z"), A),  # hourly, scheduled
        (_at("2026-09-27T04:20:00Z"), B),  # inside the dispatch window
        (_at("2026-09-27T09:30:00Z"), C),  # scheduled sweep, after the dispatch
    )

    def test_rows_filed_inside_a_dispatch_window_are_not_the_pipelines(self) -> None:
        windows = [(_at(DISPATCH["createdAt"]), _at(DISPATCH["updatedAt"]))]
        assert cr.scheduled_retrievals(self.POLLS, windows) == {A, C}

    def test_a_running_dispatch_owns_everything_after_its_start(self) -> None:
        windows: list[tuple[datetime, datetime | None]] = [(_at("2026-09-27T04:00:00Z"), None)]
        assert cr.scheduled_retrievals(self.POLLS, windows) == {A}

    def test_dispatch_listing_is_read_with_open_ends_for_running_runs(self, tmp_path: Path) -> None:
        listing = tmp_path / "d.json"
        running = {**DISPATCH, "status": "in_progress"}
        scheduled = {**DISPATCH, "event": "schedule"}
        listing.write_text(json.dumps([DISPATCH, running, scheduled]), encoding="utf-8")
        assert cr.read_dispatch_windows(listing) == [
            (_at(DISPATCH["createdAt"]), _at(DISPATCH["updatedAt"])),
            (_at(DISPATCH["createdAt"]), None),
        ]


class TestRecordCli:
    def _args(self, root: Path, listing: Path, served: Path) -> list[str]:
        return [
            "record",
            *("--root", str(root), "--day", "2026-09-26", "--served", str(served)),
            *("--dispatches", str(listing), "--step", "0.25", "--run-id", "42"),
        ]

    def test_a_manual_backfill_cannot_raise_the_figure(self, tmp_path: Path) -> None:
        """PR #105 review, reproduced: B was missed, then a dispatch filed it.

        The archive now holds A and B. Judged against the archive, B would be
        recorded as captured, permanently. Judged against the scheduled runs'
        retrievals it is `backfilled`, and counts as missed.
        """
        root, listing = _root(
            tmp_path,
            held=[A, B],
            ledger=[("2026-09-26T05:07:00Z", A, "new"), ("2026-09-27T04:20:00Z", B, "new")],
            dispatches=[DISPATCH],
        )
        served = tmp_path / "served.txt"
        served.write_text(f"{A}\n{B}\n", encoding="utf-8")
        assert cr.main(self._args(root, listing, served)) == 0
        rows = cr.read_capture(root / "health" / "capture.tsv")
        assert [(r.stem, r.status) for r in rows] == [(A, "captured"), (B, "backfilled")]
        summary = cr.summarise(rows, TODAY)
        assert (summary.held, summary.missed, summary.backfilled, summary.exist) == (1, 1, 1, 2)

    def test_a_dispatch_filing_later_retrieved_by_a_scheduled_run_is_captured(
        self, tmp_path: Path
    ) -> None:
        """Both review findings at once, as 20260929T031811 actually happened.

        A dispatch filed B first; a scheduled sweep then fetched B again as
        `duplicate-partial`. The pipeline did catch B, so it is captured, which
        neither "first filer" nor "exclude whatever a dispatch filed" gets right.
        """
        root, listing = _root(
            tmp_path,
            held=[B],
            ledger=[
                ("2026-09-27T04:20:00Z", B, "new"),
                ("2026-09-27T09:30:00Z", B, "duplicate-partial"),
            ],
            dispatches=[DISPATCH],
        )
        served = tmp_path / "served.txt"
        served.write_text(f"{B}\n", encoding="utf-8")
        assert cr.main(self._args(root, listing, served)) == 0
        rows = cr.read_capture(root / "health" / "capture.tsv")
        assert [(r.stem, r.status, r.retrieved) for r in rows] == [(B, "captured", True)]

    def test_record_appends_once_and_refuses_a_second_time(self, tmp_path: Path) -> None:
        root, listing = _root(
            tmp_path,
            held=[A, "20260925T230000000000Z"],
            ledger=[("2026-09-26T05:07:00Z", A, "new")],
            dispatches=[],
        )
        served = tmp_path / "served.txt"
        served.write_text(f"{A}\n{B}\n", encoding="utf-8")
        assert cr.main(self._args(root, listing, served)) == 0
        capture = root / "health" / "capture.tsv"
        first = capture.read_bytes()
        assert first.count(b"\n") == 3  # header, captured, MISSED
        assert b"\r" not in first
        assert cr.main(self._args(root, listing, served)) == 0
        assert capture.read_bytes() == first

    def test_the_dispatch_listing_is_required(self, tmp_path: Path) -> None:
        """Without it a healed day cannot be told from a captured one, so refuse."""
        with pytest.raises(SystemExit):
            cr.main(["record", "--root", str(tmp_path), "--day", "2026-09-26", "--served", "x"])

    def test_pending_reads_what_record_wrote(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "health").mkdir()
        cr.append_rows(
            tmp_path / "health" / "capture.tsv",
            cr.day_rows(DAY, set(), set(), set(), "0.25", "1"),
        )
        assert cr.main(["pending", "--root", str(tmp_path), "--today", "2026-09-29"]) == 0
        assert capsys.readouterr().out.split() == ["2026-09-25", "2026-09-24", "2026-09-23"]


class TestAtomicWrite:
    def test_a_write_interrupted_before_the_replace_leaves_the_record_whole(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PR #105 review: a job stopped mid-write must not leave a truncated row."""
        path = tmp_path / "capture.tsv"
        cr.append_rows(path, cr.day_rows(DAY, {A}, {A}, {A}, "0.25", "1"))
        before = path.read_bytes()

        def interrupted(*_: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(cr.os, "replace", interrupted)
        with pytest.raises(KeyboardInterrupt):
            cr.append_rows(path, cr.day_rows(date(2026, 9, 25), {B}, set(), set(), "0.25", "1"))
        assert path.read_bytes() == before
        assert not path.with_name(path.name + ".tmp").exists()
        assert len(cr.read_capture(path)) == 1


class TestReadCapture:
    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert cr.read_capture(tmp_path / "capture.tsv") == []

    @pytest.mark.parametrize(
        "row",
        [
            f"2026-09-26\t{A}\tyes\tyes\tyes\tcaught\t0.25\t1",
            f"2026-09-26\t{A}\tmaybe\tyes\tyes\tcaptured\t0.25\t1",
            f"2026-09-26\t{A}\tyes\tyes\tsometimes\tcaptured\t0.25\t1",
            f"2026-09-26\t{A}\tyes\tyes\tyes\tcaptured\t0.25",
        ],
        ids=["unknown-status", "non-binary-served", "non-binary-retrieved", "short-row"],
    )
    def test_rows_it_cannot_vouch_for_are_rejected(self, tmp_path: Path, row: str) -> None:
        path = tmp_path / "capture.tsv"
        path.write_text("\t".join(cr.CAPTURE_FIELDS) + "\n" + row + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            cr.read_capture(path)

    def test_an_unexpected_header_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "capture.tsv"
        path.write_text("day\tstamp\n", encoding="utf-8")
        with pytest.raises(ValueError, match="header"):
            cr.read_capture(path)


def _workflow_text(name: str) -> str:
    """Workflow source without whole-line comments, which quote what they explain."""
    lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _workflow_value(name: str, key: str) -> str:
    """A quoted env value at any indentation."""
    match = re.search(rf"^\s+{key}: '([^']*)'", _workflow_text(name), re.MULTILINE)
    assert match, f"{key} is missing from {name}"
    return match.group(1)


def _capture_job() -> str:
    text = _workflow_text("calibration-health.yml")
    return text.split("\n  capture:\n", 1)[1].split("\n  render:\n", 1)[0]


def _step(job: str, name: str) -> str:
    return job.split(f"- name: {name}\n", 1)[1].split("\n      - ", 1)[0]


class TestWorkflowPins:
    def test_the_capture_grid_is_strictly_finer_than_the_sweep(self) -> None:
        """At the sweep's own step the enumeration shares its blind spots.

        It would then report near-full capture while missing exactly the
        sub-step documents NC-058 found. Checked as the probe would parse them.
        """
        capture = float(_workflow_value("calibration-health.yml", "CAPTURE_STEP_HOURS"))
        sweep = float(_workflow_value("calibration-poll.yml", "SWEEP_STEP_HOURS"))
        assert math.isfinite(capture) and math.isfinite(sweep)
        assert 0 < capture < sweep

    def test_a_failed_capture_cannot_cost_the_render(self) -> None:
        """The render is NC-053's heartbeat; capture is listed in needs, never in if."""
        text = _workflow_text("calibration-health.yml")
        render = text.split("\n  render:\n", 1)[1].split("\n    runs-on:", 1)[0]
        condition = next(line for line in render.splitlines() if line.lstrip().startswith("if:"))
        assert "capture" in render.split("if:")[0]
        assert "capture" not in condition

    def test_a_measured_day_survives_the_enumeration_being_stopped(self) -> None:
        """PR #105 review, reproduced in run 36958446803: a job-level timeout

        cancelled the loop after day 1 was measured and skipped the commit. The
        enumeration now times out on its own, inside the job's bound, and the
        commit step runs whatever happened before it.
        """
        job = _capture_job()
        job_bound = int(re.search(r"^    timeout-minutes: (\d+)$", job, re.MULTILINE).group(1))
        step_bound = int(
            re.search(
                r"timeout-minutes: (\d+)", _step(job, "Enumerate settled days and record capture")
            ).group(1)
        )
        assert 0 < step_bound < job_bound
        assert "if: always()" in _step(job, "Commit the capture record")

    def test_the_job_can_tell_a_dispatch_from_a_scheduled_run(self) -> None:
        """Without the run history and the ledger, a healed day reads as captured."""
        job = _capture_job()
        assert re.search(r"^      actions: read$", job, re.MULTILINE)
        assert re.search(r"^            ledger$", job, re.MULTILINE)
        enumerate_step = _step(job, "Enumerate settled days and record capture")
        assert "--event workflow_dispatch" in enumerate_step
        assert "--dispatches dispatches.json" in enumerate_step


def test_summary_rate_is_an_upper_bound_ratio() -> None:
    rows = cr.day_rows(DAY, {A, B}, {A}, {A}, "0.25", "1")
    summary = cr.summarise(rows, TODAY)
    assert (summary.days, summary.exist, summary.held, summary.missed) == (1, 2, 1, 1)
    assert summary.rate == 0.5
