"""Unit tests for the issue #48 section 7.3 threshold evidence script.

These pin the properties a threshold row depends on being true. A percentile
that interpolates, a window that counts the ledger's own edge as a gap, or a
first sighting read from ``is_new_state`` would each move a published number
without failing anything, and the register rows built on this script would then
assert a firing rate nobody could reproduce.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.threshold_distributions import (
    WINDOW_HOURS,
    coverage_windows,
    percentile,
    poll_hours,
    share_above,
    share_below,
    state_intervals,
)

BASE = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)


def _hours(*offsets: int) -> set[datetime]:
    return {BASE + timedelta(hours=offset) for offset in offsets}


def _write_ledger(root: Path, stamps: list[str]) -> None:
    path = root / "ledger" / "2026-09.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(f"{s}\tibm_fez\t20260901T000000000000Z\tnew\n" for s in stamps)
    path.write_text("poll_time_utc\tbackend\tlast_update_date\tdecision\n" + rows, encoding="utf-8")


def _write_index(root: Path, rows: list[tuple[str, str, str, str]]) -> None:
    path = root / "health" / "state-index.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join("\t".join(row) + "\n" for row in rows)
    header = "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
    path.write_text(header + body, encoding="utf-8")


class TestPollHours:
    def test_several_polls_in_one_hour_count_once(self, tmp_path: Path) -> None:
        """Coverage is hours-with-a-poll, never polls; this is why 16/24 was a category error."""
        _write_ledger(
            tmp_path, ["2026-09-01T00:05:00Z", "2026-09-01T00:41:00Z", "2026-09-01T01:02:00Z"]
        )
        assert poll_hours(tmp_path) == _hours(0, 1)

    def test_offset_and_z_stamps_agree(self, tmp_path: Path) -> None:
        _write_ledger(tmp_path, ["2026-09-01T00:05:00Z", "2026-09-01T00:05:00+00:00"])
        assert poll_hours(tmp_path) == _hours(0)


class TestCoverageWindows:
    def test_a_fully_covered_span_reads_one(self) -> None:
        fired = _hours(*range(WINDOW_HOURS + 3))
        windows = coverage_windows(fired)
        # Span 0..74 h, so window ends run 72, 73, 74: three, not four.
        assert windows == [1.0, 1.0, 1.0]

    def test_window_count_is_span_minus_width_plus_one(self) -> None:
        """One window per hour boundary, and only those lying wholly inside the span."""
        fired = _hours(0, WINDOW_HOURS + 9)
        assert len(coverage_windows(fired)) == 10

    def test_a_span_shorter_than_the_window_yields_nothing(self) -> None:
        """Not zero coverage: too short to measure is a different statement from empty."""
        assert coverage_windows(_hours(0, 5)) == []

    def test_empty_ledger_yields_nothing(self) -> None:
        assert coverage_windows(set()) == []

    def test_coverage_is_the_fraction_of_covered_hours(self) -> None:
        # Span must reach 72 h for a window to exist at all, so end at hour 72.
        fired = _hours(*range(0, WINDOW_HOURS + 2, 2))
        assert coverage_windows(fired) == [pytest.approx(0.5)]


class TestPercentile:
    def test_returns_an_observed_value_never_an_interpolation(self) -> None:
        sample = [1.0, 2.0, 3.0, 4.0]
        assert all(percentile(sample, point) in sample for point in range(0, 101, 7))

    def test_nearest_rank_bounds(self) -> None:
        sample = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert percentile(sample, 0) == 10.0
        assert percentile(sample, 100) == 50.0
        assert percentile(sample, 50) == 30.0

    def test_unsorted_input_is_handled(self) -> None:
        assert percentile([5.0, 1.0, 3.0], 100) == 5.0

    def test_empty_sample_raises(self) -> None:
        with pytest.raises(ValueError):
            percentile([], 50)


class TestShares:
    def test_below_is_strict(self) -> None:
        assert share_below([0.15, 0.16], 0.15) == (0, 0.0)

    def test_above_is_strict(self) -> None:
        assert share_above([24.0, 24.1], 24.0) == (1, 0.5)

    def test_empty_sample_does_not_divide_by_zero(self) -> None:
        assert share_below([], 0.5) == (0, 0.0)
        assert share_above([], 0.5) == (0, 0.0)


class TestStateIntervals:
    def test_first_sighting_is_the_earliest_stamp_not_the_first_row(self, tmp_path: Path) -> None:
        """The property a sweep breaks: a later-appended older document owns the sighting."""
        _write_index(
            tmp_path,
            [
                ("b.json", "2026-09-01T10:00:00Z", "digest-a", "1"),
                ("a.json", "2026-09-01T04:00:00Z", "digest-a", "0"),
                ("c.json", "2026-09-01T12:00:00Z", "digest-b", "1"),
            ],
        )
        # digest-a is first seen at 04:00, not 10:00, so the gap to digest-b is 8 h.
        assert state_intervals(tmp_path) == [pytest.approx(8.0)]

    def test_repeated_digests_do_not_create_intervals(self, tmp_path: Path) -> None:
        _write_index(
            tmp_path,
            [
                ("a.json", "2026-09-01T00:00:00Z", "digest-a", "1"),
                ("b.json", "2026-09-01T01:00:00Z", "digest-a", "0"),
                ("c.json", "2026-09-01T02:00:00Z", "digest-a", "0"),
            ],
        )
        assert state_intervals(tmp_path) == []

    def test_intervals_are_reported_in_hours(self, tmp_path: Path) -> None:
        _write_index(
            tmp_path,
            [
                ("a.json", "2026-09-01T00:00:00Z", "digest-a", "1"),
                ("b.json", "2026-09-01T01:30:00Z", "digest-b", "1"),
            ],
        )
        assert state_intervals(tmp_path) == [pytest.approx(1.5)]

    def test_rows_missing_a_field_are_skipped(self, tmp_path: Path) -> None:
        _write_index(
            tmp_path,
            [
                ("a.json", "2026-09-01T00:00:00Z", "digest-a", "1"),
                ("b.json", "", "digest-b", "1"),
                ("c.json", "2026-09-01T03:00:00Z", "digest-c", "1"),
            ],
        )
        assert state_intervals(tmp_path) == [pytest.approx(3.0)]
