"""Offline conformance tests for the calibration pipeline-health readout."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest
from scripts.pipeline_health import (
    PollRow,
    StateRow,
    build_metrics,
    main,
    read_index,
    render_svg,
    staleness_band,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def test_metrics_count_distinct_states_and_only_new_ledger_rows() -> None:
    states = [
        StateRow("a.json", NOW - timedelta(hours=2), "a", True),
        StateRow("b.json", NOW - timedelta(hours=1), "a", False),
        StateRow("c.json", NOW - timedelta(minutes=30), "b", True),
    ]
    polls = [
        PollRow(NOW - timedelta(hours=1), "new"),
        PollRow(NOW - timedelta(hours=2), "duplicate-partial"),
    ]
    metrics = build_metrics(states, polls, [("candidate", 4)], NOW)
    assert metrics["documents_total"] == 3
    assert metrics["states_total"] == 2
    assert metrics["polls_yielding_new_state_24h"] == 1
    assert metrics["floors"][0]["states_remaining"] == 2
    assert len(metrics["new_states_per_day_30d"]) == 30


def test_zero_rate_has_no_finite_projection_and_hour_boundary_is_included() -> None:
    old = StateRow("a.json", NOW - timedelta(days=8), "a", True)
    poll = PollRow(NOW.replace(minute=0), "duplicate")
    metrics = build_metrics([old], [poll], [("candidate", 2)], NOW)
    assert metrics["floors"][0]["projected_days"] is None
    assert metrics["ledger_hour_coverage_72h"] == 0
    assert metrics["poll_hours_72h"][-1] is False  # the current partial hour is excluded


def test_svg_is_deterministic_well_formed_and_safe() -> None:
    metrics = build_metrics([], [], [("first", 630), ("second", 675)], NOW)
    svg = render_svg(metrics)
    assert svg == render_svg(metrics)
    assert "<script" not in svg and "<foreignObject" not in svg and "href=" not in svg
    root = ElementTree.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 900 480"
    assert 'fill="#f8fafc"' in svg
    assert 'y="207"' in svg and 'y="222"' in svg


def test_cli_writes_deterministic_artifacts_from_index_and_ledger(tmp_path: Path) -> None:
    health = tmp_path / "health"
    ledger = tmp_path / "ledger"
    health.mkdir()
    ledger.mkdir()
    (health / "state-index.tsv").write_text(
        "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
        "a.json\t2026-09-04T10:00:00Z\ta\t1\n"
        "b.json\t2026-09-04T11:00:00Z\ta\t0\n",
        encoding="utf-8",
    )
    (ledger / "2026-09.tsv").write_text(
        "poll_time_utc\tbackend\tlast_update_date\tdecision\n"
        "2026-09-04T11:00:00Z\tibm_fez\t20260904T110000000000Z\tduplicate\n",
        encoding="utf-8",
    )
    args = ["--root", str(tmp_path), "--now", "2026-09-04T12:00:00Z", "--floor", "candidate=9"]
    assert main(args) == 0
    first_json = (health / "metrics.json").read_bytes()
    first_svg = (health / "progress.svg").read_bytes()
    assert main(args) == 0
    assert (health / "metrics.json").read_bytes() == first_json
    assert (health / "progress.svg").read_bytes() == first_svg


NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _text_nodes(svg: str) -> list[str]:
    """Every rendered text node, which is where a figure becomes a published claim."""
    return [node.text or "" for node in ElementTree.fromstring(svg).iter("{*}text")]


def _renderable_numbers(metrics: dict[str, Any]) -> set[str]:
    """Numbers metrics.json licenses the SVG to render, formatted as it renders them."""
    allowed = {
        str(metrics["states_total"]),
        str(metrics["documents_total"]),
        f"{float(metrics['duplication_ratio']) * 100:.1f}",
        f"{float(metrics['ledger_hour_coverage_72h']) * 100:.1f}",
        f"{float(metrics['states_per_day_7d']):.2f}",
        str(len(metrics["poll_hours_72h"])),
        str(len(metrics["new_states_per_day_30d"])),
    }
    allowed.update(NUMBER.findall(str(metrics["staleness_band"])))
    for floor in metrics["floors"]:
        allowed.add(str(floor["value"]))
        allowed.update(NUMBER.findall(str(floor["label"])))
    return allowed


class TestConformance:
    """Issue #48 section 9.3: assert the output is fit to publish, not merely correct."""

    def test_every_number_rendered_in_the_svg_is_traceable_to_metrics(self) -> None:
        """A rendered figure nothing can trace is the failure the NC register exists to stop."""
        states = [
            StateRow("a.json", NOW - timedelta(days=3), "a", True),
            StateRow("b.json", NOW - timedelta(days=2), "a", False),
            StateRow("c.json", NOW - timedelta(hours=5), "b", True),
        ]
        polls = [PollRow(NOW - timedelta(hours=hour), "new") for hour in range(1, 40)]
        metrics = build_metrics(states, polls, [("NC-012", 1170), ("TanhBellMF", 1215)], NOW)
        allowed = _renderable_numbers(metrics)
        for node in _text_nodes(render_svg(metrics)):
            unlicensed = set(NUMBER.findall(node)) - allowed
            assert not unlicensed, f"{node!r} renders {unlicensed}, absent from metrics.json"

    def test_no_foreground_colour_equals_the_background(self) -> None:
        """NFR-8: the SVG loads as an image, so ink on ground is invisible, not inherited."""
        svg = render_svg(build_metrics([], [], [("first", 630)], NOW))
        background = ElementTree.fromstring(svg)[1].attrib["fill"]
        assert svg.count(background) == 1, f"{background} is used as ink as well as ground"

    def test_progress_bar_clamps_when_states_exceed_every_floor(self) -> None:
        """Overshooting a candidate floor must not paint outside the bar."""
        states = [StateRow(f"{n}.json", NOW, str(n), True) for n in range(40)]
        svg = render_svg(build_metrics(states, [], [("small", 4)], NOW))
        assert '<rect x="55" y="165" width="790.00" height="24" rx="4" fill="#166534"/>' in svg
        assert '<path d="M845.00 159v36"' in svg


class TestCommitOnChange:
    """Issue #48 section 9.2 and FR-6: the guard the workflow churn budget rests on."""

    @staticmethod
    def _quiet_archive() -> list[StateRow]:
        """An archive whose last activity predates both rolling windows."""
        return [
            StateRow("a.json", NOW - timedelta(days=60), "a", True),
            StateRow("b.json", NOW - timedelta(days=59), "a", False),
        ]

    def test_unchanged_inputs_render_identical_bytes_a_day_apart(self) -> None:
        """The render instant must not reach the SVG; if it does the guard never fires."""
        states = self._quiet_archive()
        floors = [("NC-012", 1170)]
        first = render_svg(build_metrics(states, [], floors, NOW))
        second = render_svg(build_metrics(states, [], floors, NOW + timedelta(days=1)))
        assert first == second

    def test_one_new_state_changes_the_rendered_bytes(self) -> None:
        """The other half of FR-6: a material change must still produce a commit."""
        states = self._quiet_archive()
        floors = [("NC-012", 1170)]
        before = render_svg(build_metrics(states, [], floors, NOW))
        after = render_svg(
            build_metrics(
                [*states, StateRow("c.json", NOW - timedelta(hours=1), "b", True)],
                [],
                floors,
                NOW,
            )
        )
        assert before != after

    def test_staleness_is_rendered_as_a_band_not_a_clock_reading(self) -> None:
        """Bands are what make the two assertions above possible."""
        assert staleness_band(None) == "never"
        assert staleness_band(0.0) == staleness_band(23.9) == "under 24 h"
        assert staleness_band(24.0) == staleness_band(71.9) == "24 h to 3 days"
        assert staleness_band(72.0) == "3 to 7 days"
        assert staleness_band(168.0) == staleness_band(10_000.0) == "over 7 days"


def _shipped_floors() -> list[tuple[str, int]]:
    """The candidate floors the health workflow actually supplies.

    Read out of the workflow rather than restated here. Pinning literals in the
    test is what let the renderer keep shipping 630 and 675 for a day after
    #56 FR-10 corrected NC-012 to 1170: the guard passed while the dashboard
    published a floor no register row asserted.
    """
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/calibration-health.yml"
    text = workflow.read_text(encoding="utf-8")
    match = re.search(r"^\s*HEALTH_FLOORS:\s*'([^']*)'", text, re.MULTILINE)
    assert match, "HEALTH_FLOORS is the FR-7 configuration surface and must exist"
    floors = [item.partition("=") for item in match.group(1).split()]
    assert floors, "HEALTH_FLOORS must name at least one candidate floor"
    return [(label, int(value)) for label, _, value in floors]


class TestFloorsAreConfiguration:
    """FR-7: floors are a configuration input, never an assertion in code."""

    def test_no_shipped_floor_is_a_literal_in_the_renderer(self) -> None:
        source = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_health.py"
        body = source.read_text(encoding="utf-8")
        for label, value in _shipped_floors():
            assert str(value) not in body, f"{label}={value} leaked into the renderer"

    def test_the_shipped_floors_render_and_are_labelled(self) -> None:
        """FR-7's other half: UC-6 needs every tick to carry its source."""
        floors = _shipped_floors()
        svg = render_svg(build_metrics([], [], floors, NOW))
        for label, value in floors:
            assert f"{label}: {value}" in svg

    def test_the_cli_refuses_to_invent_a_floor(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--root", str(tmp_path)])
        assert excinfo.value.code == 2


class TestIndexParsing:
    """Issue #48 section 9.1: a malformed index must be rejected, never guessed at."""

    HEADER = "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"

    def _write(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "state-index.tsv"
        path.write_text(body, encoding="utf-8")
        return path

    def test_missing_file_is_an_empty_index(self, tmp_path: Path) -> None:
        assert read_index(tmp_path / "absent.tsv") == []

    def test_a_header_only_file_is_an_empty_index(self, tmp_path: Path) -> None:
        assert read_index(self._write(tmp_path, self.HEADER)) == []

    def test_an_empty_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unexpected header"):
            read_index(self._write(tmp_path, ""))

    def test_an_unexpected_header_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unexpected header"):
            read_index(self._write(tmp_path, "snapshot_filename\tqubit_digest\n"))

    def test_a_short_row_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="malformed index row"):
            read_index(self._write(tmp_path, self.HEADER + "a.json\t\tdigest\t1\n"))

    def test_a_long_row_is_rejected(self, tmp_path: Path) -> None:
        row = "a.json\t2026-09-04T10:00:00Z\tdigest\t1\textra\n"
        with pytest.raises(ValueError, match="malformed index row"):
            read_index(self._write(tmp_path, self.HEADER + row))

    def test_a_non_binary_is_new_state_is_rejected(self, tmp_path: Path) -> None:
        row = "a.json\t2026-09-04T10:00:00Z\tdigest\ttrue\n"
        with pytest.raises(ValueError, match="is_new_state must be 0 or 1"):
            read_index(self._write(tmp_path, self.HEADER + row))

    def test_states_total_is_order_independent(self) -> None:
        """Rows arrive in archive order, but a distinct count must not depend on it."""
        ordered = [
            StateRow("a.json", NOW - timedelta(hours=3), "a", True),
            StateRow("b.json", NOW - timedelta(hours=2), "b", True),
            StateRow("c.json", NOW - timedelta(hours=1), "a", False),
        ]
        shuffled = [ordered[2], ordered[0], ordered[1]]
        floors = [("candidate", 4)]
        assert (
            build_metrics(ordered, [], floors, NOW)["states_total"]
            == build_metrics(shuffled, [], floors, NOW)["states_total"]
            == 2
        )


def test_poll_hours_span_a_month_partition(tmp_path: Path) -> None:
    """The ledger is partitioned monthly, so a 72-hour window can straddle two files."""
    ledger = tmp_path / "ledger"
    health = tmp_path / "health"
    ledger.mkdir()
    health.mkdir()
    header = "poll_time_utc\tbackend\tlast_update_date\tdecision\n"
    (ledger / "2026-08.tsv").write_text(
        header + "2026-08-31T23:00:00Z\tibm_fez\t20260831T230000Z\tnew\n", encoding="utf-8"
    )
    (ledger / "2026-09.tsv").write_text(
        header + "2026-09-01T00:00:00Z\tibm_fez\t20260901T000000Z\tduplicate\n", encoding="utf-8"
    )
    (health / "state-index.tsv").write_text(
        "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n", encoding="utf-8"
    )
    args = ["--root", str(tmp_path), "--now", "2026-09-01T12:00:00Z", "--floor", "candidate=630"]
    assert main(args) == 0
    metrics = json.loads((health / "metrics.json").read_text(encoding="utf-8"))
    assert sum(metrics["poll_hours_72h"]) == 2, "one hour from each monthly ledger file"
    assert metrics["ledger_hour_coverage_72h"] == 2 / 72
