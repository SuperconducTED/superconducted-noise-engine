"""Tests for the daily capture record (#54).

Pinned here: which days count as settled, that a day is recorded once and only
once, that the day boundaries tile, and that an empty day still leaves a row.
Each of these fails quietly if wrong: a fresh day reads low because the sweep
has not reached it, a re-recorded day counts twice, an overlapping boundary
counts one document on two days, and an empty day is re-enumerated forever.
"""

from __future__ import annotations

import math
import re
from datetime import date
from pathlib import Path

import pytest
from scripts import capture_record as cr
from scripts.capture_record import CaptureRow

TODAY = date(2026, 9, 29)
INDEX_HEADER = "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"


def _index(tmp_path: Path, *stems: str) -> Path:
    health = tmp_path / "health"
    health.mkdir(exist_ok=True)
    body = "".join(f"{s}.json\t2026-09-26T00:00:00Z\td{n}\t1\n" for n, s in enumerate(stems))
    (health / "state-index.tsv").write_text(INDEX_HEADER + body, encoding="utf-8")
    return health / "state-index.tsv"


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
    DAY = date(2026, 9, 26)

    def test_statuses(self) -> None:
        served = {"20260926T010000000000Z", "20260926T020000000000Z"}
        held = {"20260926T010000000000Z", "20260926T030000000000Z"}
        rows = cr.day_rows(self.DAY, served, held, "0.25", "7")
        assert [(r.stem, r.status) for r in rows] == [
            ("20260926T010000000000Z", "captured"),
            ("20260926T020000000000Z", "MISSED"),
            ("20260926T030000000000Z", "archived_not_served"),
        ]

    def test_the_day_is_half_open_so_days_tile(self) -> None:
        """The probe window is closed; its midnight answer belongs to the next day."""
        served = {"20260926T000000000000Z", "20260927T000000000000Z"}
        rows = cr.day_rows(self.DAY, served, set(), "0.25", "7")
        assert [r.stem for r in rows] == ["20260926T000000000000Z"]

    def test_an_empty_day_leaves_one_sentinel_row(self) -> None:
        rows = cr.day_rows(self.DAY, set(), set(), "0.25", "7")
        assert rows == [CaptureRow(self.DAY, "-", False, False, cr.NO_DOCUMENTS, "0.25", "7")]


class TestRecordCli:
    def test_record_appends_once_and_refuses_a_second_time(self, tmp_path: Path) -> None:
        _index(tmp_path, "20260926T010000000000Z", "20260925T230000000000Z")
        served = tmp_path / "served.txt"
        served.write_text("20260926T010000000000Z\n20260926T020000000000Z\n", encoding="utf-8")
        args = ["record", "--root", str(tmp_path), "--day", "2026-09-26", "--served", str(served)]
        args += ["--step", "0.25", "--run-id", "42"]
        assert cr.main(args) == 0
        capture = tmp_path / "health" / "capture.tsv"
        first = capture.read_bytes()
        assert first.count(b"\n") == 3  # header, captured, MISSED
        assert b"\r" not in first
        assert cr.main(args) == 0
        assert capture.read_bytes() == first

    def test_pending_reads_what_record_wrote(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _index(tmp_path)
        cr.append_rows(
            tmp_path / "health" / "capture.tsv",
            cr.day_rows(date(2026, 9, 26), set(), set(), "0.25", "1"),
        )
        assert cr.main(["pending", "--root", str(tmp_path), "--today", "2026-09-29"]) == 0
        assert capsys.readouterr().out.split() == ["2026-09-25", "2026-09-24", "2026-09-23"]


class TestReadCapture:
    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert cr.read_capture(tmp_path / "capture.tsv") == []

    @pytest.mark.parametrize(
        "row",
        [
            "2026-09-26\t20260926T010000000000Z\tyes\tyes\tcaught\t0.25\t1",
            "2026-09-26\t20260926T010000000000Z\tmaybe\tyes\tcaptured\t0.25\t1",
            "2026-09-26\t20260926T010000000000Z\tyes\tyes\tcaptured\t0.25",
        ],
        ids=["unknown-status", "non-binary-served", "short-row"],
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


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _workflow_value(name: str, key: str) -> str:
    """A quoted env value at any indentation, ignoring comment lines that quote it."""
    lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
    text = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    match = re.search(rf"^\s+{key}: '([^']*)'", text, re.MULTILINE)
    assert match, f"{key} is missing from {name}"
    return match.group(1)


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
        text = (WORKFLOWS / "calibration-health.yml").read_text(encoding="utf-8")
        render = text.split("\n  render:\n", 1)[1].split("\n    runs-on:", 1)[0]
        condition = next(line for line in render.splitlines() if line.lstrip().startswith("if:"))
        assert "capture" in render.split("if:")[0]
        assert "capture" not in condition


def test_summary_rate_is_an_upper_bound_ratio() -> None:
    day = date(2026, 9, 26)
    rows = cr.day_rows(
        day,
        {"20260926T010000000000Z", "20260926T020000000000Z"},
        {"20260926T010000000000Z"},
        "0.25",
        "1",
    )
    summary = cr.summarise(rows, TODAY)
    assert (summary.days, summary.exist, summary.held, summary.missed) == (1, 2, 1, 1)
    assert summary.rate == 0.5
