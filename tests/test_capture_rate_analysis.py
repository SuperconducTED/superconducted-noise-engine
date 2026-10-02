"""Tests for the #54 capture-rate reproduction script.

The registered figures are reproduced against the real archive (see the
implementation doc). What is pinned here is each *definition* a figure depends
on, because every one of them has a plausible-looking alternative that gives a
different number without failing anything: attributing a document to its last
filer instead of its first, counting a state lost when the hourly poll saw it
again later, or reading a truncated probe log as a list of documents missed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts import capture_rate_analysis as cra
from scripts.capture_rate_analysis import IndexRow, LedgerRow


def _stem(day: int, hour: int, minute: int = 0) -> str:
    return f"202609{day:02d}T{hour:02d}{minute:02d}00000000Z"


def _at(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=UTC)


def _row(poll: str, stem: str, decision: str = "new") -> LedgerRow:
    return LedgerRow(poll, "ibm_fez", stem, decision)


class TestAttribution:
    def test_one_row_is_hourly_and_many_rows_are_a_sweep(self) -> None:
        rows = [
            _row("2026-09-12T10:07:00Z", _stem(12, 9)),
            _row("2026-09-13T09:30:00Z", _stem(11, 20)),
            _row("2026-09-13T09:30:00Z", _stem(12, 9), "duplicate"),
        ]
        assert cra.classify_polls(rows) == {
            "2026-09-12T10:07:00Z": cra.HOURLY,
            "2026-09-13T09:30:00Z": cra.SWEEP,
        }

    def test_first_new_row_wins_and_duplicates_attribute_nothing(self) -> None:
        """A sweep re-reading a document the hourly poll filed must not claim it."""
        rows = [
            _row("2026-09-12T10:07:00Z", _stem(12, 9)),
            _row("2026-09-13T09:30:00Z", _stem(12, 9), "duplicate-partial"),
            _row("2026-09-13T09:30:00Z", _stem(12, 11)),
        ]
        assert cra.first_filed_by(rows) == {_stem(12, 9): cra.HOURLY, _stem(12, 11): cra.SWEEP}

    def test_ledger_window_is_half_open(self) -> None:
        first = {_stem(11, 0): cra.HOURLY, _stem(12, 0): cra.SWEEP}
        split = cra.ledger_split([_stem(11, 0), _stem(12, 0)], first, _at(11), _at(12))
        assert split == {cra.HOURLY: 1}

    def test_a_document_with_no_new_row_is_unledgered_not_hourly(self) -> None:
        split = cra.ledger_split([_stem(11, 5)], {}, _at(11), _at(12))
        assert split == {cra.UNLEDGERED: 1}


class TestStateCounterfactual:
    def test_state_seen_again_later_by_the_hourly_poll_was_not_lost(self) -> None:
        """Sweep recovers state X on the 12th; the hourly poll sees X again on the 20th."""
        index = [IndexRow(_stem(12, 3), "X"), IndexRow(_stem(20, 3), "X")]
        assert cra.state_counterfactual(index, {_stem(20, 3)}, _at(11), _at(13)) == (1, 1, 0)

    def test_state_carried_only_by_sweep_documents_is_sweep_only(self) -> None:
        index = [IndexRow(_stem(12, 3), "X"), IndexRow(_stem(12, 5), "Y")]
        assert cra.state_counterfactual(index, {_stem(12, 5)}, _at(11), _at(13)) == (2, 1, 1)

    def test_state_first_seen_before_the_window_is_not_new(self) -> None:
        """Earliest stamp decides, whatever order the index was appended in."""
        index = [IndexRow(_stem(12, 3), "X"), IndexRow(_stem(10, 3), "X")]
        assert cra.state_counterfactual(index, set(), _at(11), _at(13)) == (0, 0, 0)

    def test_an_hourly_duplicate_of_a_sweep_filing_is_a_retrieval(self) -> None:
        """PR #105 review: the sweep files X at 09:30, an hourly poll fetches X at 10:07.

        The hourly row is a `duplicate`, so X's first filer is the sweep, but the
        sampler did catch X: without the sweep that poll would have filed it. X's
        state is therefore reachable from the hourly path, not sweep-only.
        """
        rows = [
            _row("2026-09-12T09:30:00Z", _stem(12, 9)),
            _row("2026-09-12T09:30:00Z", _stem(11, 20)),
            _row("2026-09-12T10:07:00Z", _stem(12, 9), "duplicate"),
        ]
        assert cra.first_filed_by(rows)[_stem(12, 9)] == cra.SWEEP
        hourly = cra.hourly_retrieved(rows)
        assert hourly == {_stem(12, 9)}
        index = [IndexRow(_stem(12, 9), "X")]
        assert cra.state_counterfactual(index, hourly, _at(12), _at(13)) == (1, 1, 0)


_CLEAN_LOG = (
    "probe\tProbe historical properties\t2026-09-28T21:07:03Z window   : ...\n"
    "probe\tProbe historical properties\t2026-09-28T21:13:00Z distinct documents returned : 3\n"
    "probe\tProbe historical properties\t2026-09-28T21:13:00Z   20260913T012345000000Z"
    "   2026-09-13T01:23:45+00:00\n"
    "probe\tProbe historical properties\t2026-09-28T21:13:00Z   20260913T024500000000Z"
    "   2026-09-13T02:45:00+00:00\n"
)


class TestProbeLog:
    def test_stamps_are_read_through_the_gh_log_prefix(self) -> None:
        assert cra.parse_probe_log(_CLEAN_LOG) == {
            "20260913T012345000000Z",
            "20260913T024500000000Z",
        }

    def test_a_log_without_the_summary_line_is_refused(self) -> None:
        """A run killed by the timeout prints nothing; an empty set would read as all missed."""
        with pytest.raises(ValueError, match="did not finish"):
            cra.parse_probe_log("probe\tProbe historical properties\twindow : ...\n")

    def test_a_log_reporting_probe_failed_is_refused(self) -> None:
        with pytest.raises(ValueError, match="incomplete"):
            cra.parse_probe_log(_CLEAN_LOG + "PROBE FAILED at 2026-09-13T03:00:00+00:00\n")


class TestEnumerationDiff:
    def test_statuses_and_closed_window(self) -> None:
        start, end = _at(13), _at(14)
        served = {_stem(13, 0), _stem(13, 2), _stem(14, 0), _stem(14, 1)}
        archive = [_stem(13, 0), _stem(13, 4), _stem(12, 23)]
        first = {_stem(13, 0): cra.HOURLY, _stem(13, 4): cra.SWEEP}
        rows = cra.enumeration_rows(served, archive, first, start, end)
        assert rows == [
            (_stem(13, 0), "yes", "yes", cra.HOURLY, "captured"),
            (_stem(13, 2), "yes", "no", "none", "MISSED"),
            (_stem(13, 4), "no", "yes", cra.SWEEP, "archived_not_served"),
            (_stem(14, 0), "yes", "no", "none", "MISSED"),
        ]


def test_parse_stem_keeps_microseconds_and_utc() -> None:
    assert cra.parse_stem("20260913T012345123456Z") == datetime(
        2026, 9, 13, 1, 23, 45, 123456, tzinfo=UTC
    )
