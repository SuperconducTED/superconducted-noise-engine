"""Offline conformance tests for the calibration pipeline-health readout."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar
from xml.etree import ElementTree

import pytest
from scripts.backfill_state_index import main as backfill_main
from scripts.pipeline_health import (
    FONT_PX,
    NOTHING_TO_PUBLISH,
    PollRow,
    StateRow,
    build_metrics,
    main,
    read_index,
    read_ledger,
    render_svg,
    staleness_band,
    text_span,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def test_metrics_count_distinct_states_and_only_polls_that_produced_one() -> None:
    """`b` is filed as a new document but carries the state `a` already had.

    That is the ordinary case at NC-025's 43.6% duplication, not a corner: the
    stamp is new, the device state is not. `polls_yielding_new_state_24h` must
    therefore be 1 and not 2, or the field counts files while its name says
    states, which is the substitution issue #48 exists to refuse.
    """
    states = [
        StateRow("a.json", NOW - timedelta(hours=2), "a", True),
        StateRow("b.json", NOW - timedelta(hours=1), "a", False),
        StateRow("c.json", NOW - timedelta(minutes=30), "b", True),
    ]
    polls = [
        PollRow(NOW - timedelta(minutes=30), "c", "new"),
        PollRow(NOW - timedelta(hours=1), "b", "new"),
        PollRow(NOW - timedelta(hours=2), "a", "duplicate-partial"),
    ]
    metrics = build_metrics(states, polls, [("candidate", 4)], NOW)
    assert metrics["documents_total"] == 3
    assert metrics["states_total"] == 2
    assert metrics["polls_fired_24h"] == 3
    assert metrics["polls_yielding_new_state_24h"] == 1
    assert metrics["floors"][0]["states_remaining"] == 2
    assert len(metrics["new_states_per_day_30d"]) == 30


def test_zero_rate_has_no_finite_projection_and_hour_boundary_is_included() -> None:
    old = StateRow("a.json", NOW - timedelta(days=8), "a", True)
    poll = PollRow(NOW.replace(minute=0), "a", "duplicate")
    metrics = build_metrics([old], [poll], [("candidate", 2)], NOW)
    assert metrics["floors"][0]["projected_days"] is None
    assert metrics["ledger_hour_coverage_72h"] == 0
    assert metrics["poll_hours_72h"][-1] is False  # the current partial hour is excluded


class TestTrailingWindows:
    """The sparkline is a rate read, so every bucket in it must be a whole day."""

    RENDER: ClassVar[datetime] = datetime(2026, 9, 4, 3, 17, tzinfo=UTC)
    """The scheduled render instant, `cron: 17 3 * * *`, where this went wrong."""

    def _daily(self, states: list[StateRow]) -> list[int]:
        metrics = build_metrics(states, [], [("candidate", 4)], self.RENDER)
        return [int(value) for value in metrics["new_states_per_day_30d"]]

    def test_the_last_bucket_is_yesterday_not_a_fraction_of_today(self) -> None:
        """At 03:17 a today-anchored window drew its last bar from 13.7% of a day."""
        yesterday = StateRow("y.json", self.RENDER - timedelta(hours=6), "y", True)
        today = StateRow("t.json", self.RENDER - timedelta(hours=1), "t", True)
        daily = self._daily([yesterday, today])
        assert len(daily) == 30
        assert daily[-1] == 1, "the final bucket is 2026-09-03, a complete day"
        assert sum(daily) == 1, "today is not a bucket, because today is not over"

    def test_a_state_acquired_today_is_still_visible_on_a_rolling_window(self) -> None:
        """Excluding today from the buckets must not hide it from the archive."""
        today = StateRow("t.json", self.RENDER - timedelta(hours=1), "t", True)
        metrics = build_metrics([today], [], [("candidate", 4)], self.RENDER)
        assert metrics["states_added_24h"] == 1
        assert metrics["states_total"] == 1
        assert metrics["new_states_per_day_30d"][-1] == 0

    def test_the_window_spans_exactly_thirty_days_back_from_midnight(self) -> None:
        """The oldest bucket is inclusive and the day before it is out."""
        oldest = StateRow(
            "o.json", self.RENDER.replace(hour=0, minute=0) - timedelta(days=30), "o", True
        )
        older = StateRow("x.json", oldest.timestamp - timedelta(seconds=1), "x", True)
        assert self._daily([oldest])[0] == 1
        assert self._daily([older])[0] == 0
        assert sum(self._daily([older])) == 0


def test_polls_fired_counts_polls_not_ledger_rows() -> None:
    """A sweep files a whole gap under one POLL_TIME, one ledger row per document.

    Measured on the live ledger at `cb7a8c2`: 129 rows from 53 polls, one sweep
    writing 52 of them. Counting rows would read that sweep as a poller firing
    twice an hour, in the panel UC-5 exists to make scheduler health legible.
    """
    sweep = NOW - timedelta(hours=2)
    polls = [PollRow(sweep, f"swept{n}", "new") for n in range(52)]
    polls.append(PollRow(NOW - timedelta(hours=1), "live", "duplicate"))
    metrics = build_metrics([], polls, [("candidate", 4)], NOW)
    assert metrics["polls_fired_24h"] == 2


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


def _escapes_the_canvas(svg: str) -> list[str]:
    """Text nodes whose estimated span leaves the viewBox, described for the failure."""
    root = ElementTree.fromstring(svg)
    canvas = float(root.attrib["viewBox"].split()[2])
    offenders = []
    for node in root.iter("{*}text"):
        left, right = text_span(
            float(node.attrib["x"]),
            node.text or "",
            FONT_PX[node.attrib["class"]],
            node.attrib.get("text-anchor", "start"),
        )
        if left < 0:
            offenders.append(f"{node.text!r} starts at {left:.1f}, off the left edge")
        if right > canvas:
            offenders.append(f"{node.text!r} ends at {right:.1f}, past {canvas:.0f}")
    return offenders


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
        polls = [
            PollRow(NOW - timedelta(hours=hour), f"poll{hour}", "new") for hour in range(1, 40)
        ]
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

    def test_no_text_node_escapes_the_canvas(self) -> None:
        """Section 9.3 well-formedness: a clipped tick label loses its source (UC-6).

        Exercised against floors supplied in the order that used to break it,
        largest first, since `text-anchor` keyed off list position rather than
        tick position and centred the rightmost label past the viewBox.
        """
        floors = [("IntervalGaussianMF", 1260), ("NC-012", 1170), ("TanhBellMF", 1215)]
        assert not _escapes_the_canvas(render_svg(build_metrics([], [], floors, NOW)))

    def test_font_sizes_match_the_style_block(self) -> None:
        """FONT_PX is the bounds check's model of the SVG; pin it to the real thing."""
        style = ElementTree.fromstring(render_svg(build_metrics([], [], [("f", 9)], NOW)))[0]
        for name, size in FONT_PX.items():
            assert f".{name}{{font:" in (style.text or "")
            assert re.search(rf"\.{name}{{font:(?:\d+ )?{size}px ", style.text or ""), name

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


class TestEndToEndFixture:
    """Issue #48 section 9.2: a committed archive rendered whole, asserted whole.

    Everything else in this file exercises one function against synthetic rows.
    This walks the path the workflow actually walks, `backfill_state_index` then
    `pipeline_health`, over four committed snapshot documents and a committed
    ledger, and compares both published artifacts byte for byte.

    Golden files earn their maintenance cost here because `progress.svg` is
    *published*: it is embedded in the branch README, so an unintended rendering
    change is a change to something the team reads, and FR-6's commit-on-change
    guard rests on those bytes being a function of the inputs alone. When a
    rendering change is intended, regenerate rather than hand-edit:

        PIPELINE_HEALTH_REGOLD=1 python -m pytest tests/test_pipeline_health.py \\
            -k test_the_fixture_renders_the_committed_artifacts

    then read the diff before committing it. The fixture supplies its own floor
    rather than the workflow's, so the artifacts do not churn when a candidate
    floor is re-pointed at a new NC row.
    """

    FIXTURE: ClassVar[Path] = Path(__file__).resolve().parent / "fixtures" / "pipeline_health"
    NOW: ClassVar[str] = "2026-09-02T12:00:00Z"
    FLOOR: ClassVar[str] = "sample=8"

    def _render(self, tmp_path: Path) -> dict[str, bytes]:
        shutil.copytree(self.FIXTURE / "archive", tmp_path, dirs_exist_ok=True)
        assert backfill_main(["--root", str(tmp_path)]) == 0
        assert main(["--root", str(tmp_path), "--now", self.NOW, "--floor", self.FLOOR]) == 0
        health = tmp_path / "health"
        return {name: (health / name).read_bytes() for name in ("metrics.json", "progress.svg")}

    def test_the_fixture_renders_the_committed_artifacts(self, tmp_path: Path) -> None:
        for name, body in self._render(tmp_path).items():
            golden = self.FIXTURE / "expected" / name
            if os.environ.get("PIPELINE_HEALTH_REGOLD"):
                golden.write_bytes(body)
            assert body == golden.read_bytes(), (
                f"{name} differs from the committed artifact. If the change is intended, "
                "regenerate with PIPELINE_HEALTH_REGOLD=1 and review the diff."
            )

    def test_the_restamped_document_is_one_state_not_two(self, tmp_path: Path) -> None:
        """The round-3 blocker, proven over the real archive path.

        `20260901T060000000000Z` repeats the measurements of the document before
        it under a later parameter `date`, the way the history endpoint re-stamps
        the records it synthesises. Four documents, two device states.
        """
        metrics = json.loads(self._render(tmp_path)["metrics.json"])
        assert metrics["documents_total"] == 4
        assert metrics["states_total"] == 2
        assert metrics["duplication_ratio"] == 0.5

    def test_rendering_the_fixture_twice_is_byte_identical(self, tmp_path: Path) -> None:
        """NFR-3 over the CLI path, including the backfill's own idempotency."""
        assert self._render(tmp_path) == self._render(tmp_path)

    def test_the_artifacts_carry_no_platform_line_endings(self, tmp_path: Path) -> None:
        """NFR-3 across platforms, not just across runs on one of them.

        `write_text` translates to `os.linesep` by default, so a render from
        Windows wrote CRLF where the ubuntu runner wrote LF for identical
        inputs. `calibration-data` has no `.gitattributes` to normalise that, so
        two writers would rewrite the whole SVG on every alternation and fire
        FR-6's commit-on-change guard with nothing to report. The implementation
        doc documents a local render, so this is a reachable path, and on a
        Windows checkout it also silently broke the golden comparison above.
        """
        for name, body in self._render(tmp_path).items():
            assert b"\r\n" not in body, f"{name} was written with platform line endings"


class TestHistoricalSweep:
    """A sweep appends old documents behind live poll rows; no metric may move.

    This is the shape issue #48 §11 point 2 produces in practice: the 72-hour
    strip exposes a stall, the operator dispatches `historical_start` over the
    gap, and `file_snapshots.sh` files each missed document as `decision=new`.
    Those rows land *out of chronological order* and carry `is_new_state=1`
    whenever their digest is not already in the index, even for a state a
    later-dated row already recorded.
    """

    @staticmethod
    def _live() -> list[StateRow]:
        """What the poller recorded before the gap was noticed."""
        return [
            StateRow("live-a.json", NOW - timedelta(hours=30), "a", True),
            StateRow("live-b.json", NOW - timedelta(hours=2), "b", True),
        ]

    @staticmethod
    def _swept() -> list[StateRow]:
        """What a sweep appends afterwards: older documents, marked new.

        `swept-b` carries digest "b", which `live-b` already recorded two hours
        ago, but the poller only sees the document in front of it, so it writes
        `is_new_state=1`. Its timestamp sits inside the 24-hour window, which is
        what made this reach the published rate rather than staying harmless.
        """
        return [
            StateRow("swept-a.json", NOW - timedelta(hours=20), "a", True),
            StateRow("swept-b.json", NOW - timedelta(hours=6), "b", True),
        ]

    def test_a_sweep_does_not_inflate_the_acquisition_rate(self) -> None:
        floors = [("NC-012", 1170)]
        before = build_metrics(self._live(), [], floors, NOW)
        after = build_metrics([*self._live(), *self._swept()], [], floors, NOW)
        assert after["documents_total"] == 4, "the swept documents are still archived"
        assert after["states_total"] == before["states_total"] == 2
        for field in ("states_added_24h", "states_added_7d", "states_per_day_7d"):
            assert after[field] == before[field], f"{field} moved on a sweep that acquired nothing"
        assert after["new_states_per_day_30d"] == before["new_states_per_day_30d"]

    def test_a_sweep_moves_the_staleness_clock_back_not_forward(self) -> None:
        """Filling a gap can only make the archive look *staler*, never fresher.

        `live-b` looked like a state first seen two hours ago. The sweep shows
        the device was already in that state six hours ago and the poller simply
        missed it, so the honest reading of "time since the last new state" is
        six hours. The two-hour figure was an artefact of the gap.
        """
        floors = [("NC-012", 1170)]
        before = build_metrics(self._live(), [], floors, NOW)
        after = build_metrics([*self._live(), *self._swept()], [], floors, NOW)
        assert before["hours_since_last_new_state"] == 2.0
        assert after["hours_since_last_new_state"] == 6.0
        assert after["staleness_band"] == "under 24 h"

    def test_only_index_head_depends_on_index_order(self) -> None:
        """The index is append-only, so its order is a fact about polling, not data.

        `index_head` is the one field allowed to move with it: FR-4 defines it as
        the last row consumed, which is provenance for the render rather than a
        measurement of the archive.
        """
        rows = [*self._live(), *self._swept()]
        floors = [("NC-012", 1170)]
        ordered = build_metrics(sorted(rows, key=lambda row: row.timestamp), [], floors, NOW)
        appended = build_metrics(rows, [], floors, NOW)
        assert ordered.pop("index_head") == "live-b.json"
        assert appended.pop("index_head") == "swept-b.json"
        assert ordered == appended

    def test_a_state_first_seen_inside_the_window_still_counts(self) -> None:
        """The guard must not swallow a genuine acquisition (the other half)."""
        floors = [("NC-012", 1170)]
        before = build_metrics(self._live(), [], floors, NOW)
        fresh = StateRow("live-c.json", NOW - timedelta(hours=1), "c", True)
        after = build_metrics([*self._live(), fresh], [], floors, NOW)
        assert after["states_total"] == 3
        assert after["states_added_24h"] == before["states_added_24h"] + 1

    def test_a_recovered_state_counts_for_the_poll_but_not_for_the_device(self) -> None:
        """The two clocks may disagree here, and that disagreement is the reading.

        The sweep files a document the device published 30 hours ago carrying a
        state the archive never held. `states_added_24h` must leave it out: the
        device did not produce it today. `polls_yielding_new_state_24h` must
        count it: the poll did acquire something we did not have. Reading either
        field with the other's clock is what makes a recovery look like either a
        phantom acquisition or a wasted poll.
        """
        floors = [("NC-012", 1170)]
        recovered = StateRow("swept-c.json", NOW - timedelta(hours=30), "c", True)
        polls = [PollRow(NOW - timedelta(hours=1), "swept-c", "new")]
        metrics = build_metrics([*self._live(), recovered], polls, floors, NOW)
        assert metrics["states_total"] == 3
        assert metrics["states_added_24h"] == 1, "only live-b was produced inside the window"
        assert metrics["polls_yielding_new_state_24h"] == 1


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

    def test_every_shipped_label_names_a_register_row(self) -> None:
        """A shape name is not a source. FR-7 asks each tick to carry the row it traces to."""
        for label, value in _shipped_floors():
            assert re.match(r"NC-\d{3}\b", label), f"{label}={value} names no NC row"

    def test_the_shipped_floors_fit_the_canvas(self) -> None:
        """The bounds guard is worth little if it never runs on the real configuration.

        The shipped floors cluster in the last 60 px of an 845 px bar, so their
        labels are the ones with somewhere to escape to, and adding a candidate
        makes it tighter rather than looser.
        """
        svg = render_svg(build_metrics([], [], _shipped_floors(), NOW))
        assert not _escapes_the_canvas(svg)

    def test_the_shipped_floors_cover_the_registered_range(self) -> None:
        """NC-046 reports a range, and the bar's full scale is the largest candidate.

        Shipping only part of the bracket does not just omit a tick, it rescales
        the progress bar, so the dashboard reads fuller than the evidence allows.
        """
        values = [value for _, value in _shipped_floors()]
        claims = Path(__file__).resolve().parents[1] / "docs" / "numerical-claims.md"
        row = next(
            line for line in claims.read_text(encoding="utf-8").splitlines() if "| NC-046 |" in line
        )
        registered = re.search(r"floor (\d+) to (\d+)", row)
        assert registered, "NC-046 must state the floor range this configuration brackets"
        low, high = int(registered.group(1)), int(registered.group(2))
        assert min(values) == low, "the bottom of NC-046's range is not rendered"
        assert max(values) == high, "the top of NC-046's range is not rendered"

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
        "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
        "a.json\t2026-08-31T23:00:00Z\tdigest\t1\n",
        encoding="utf-8",
    )
    args = ["--root", str(tmp_path), "--now", "2026-09-01T12:00:00Z", "--floor", "candidate=630"]
    assert main(args) == 0
    metrics = json.loads((health / "metrics.json").read_text(encoding="utf-8"))
    assert sum(metrics["poll_hours_72h"]) == 2, "one hour from each monthly ledger file"
    assert metrics["ledger_hour_coverage_72h"] == 2 / 72


class TestLedgerParsing:
    """`last_update_date` is now load-bearing, so it is required rather than defaulted."""

    HEADER: ClassVar[str] = "poll_time_utc\tbackend\tlast_update_date\tdecision\n"

    @staticmethod
    def _read(tmp_path: Path, text: str) -> list[PollRow]:
        ledger = tmp_path / "ledger"
        ledger.mkdir()
        (ledger / "2026-09.tsv").write_text(text, encoding="utf-8")
        return read_ledger(ledger)

    def test_a_row_naming_its_document_is_read(self, tmp_path: Path) -> None:
        rows = self._read(
            tmp_path, self.HEADER + "2026-09-01T00:37:00Z\tibm_fez\t20260901T000000Z\tnew\n"
        )
        assert [row.document for row in rows] == ["20260901T000000Z"]

    def test_a_row_without_a_document_is_rejected(self, tmp_path: Path) -> None:
        """Silently defaulting it would zero the join and read as "no polls yielded"."""
        with pytest.raises(ValueError, match="malformed ledger row"):
            self._read(tmp_path, self.HEADER + "2026-09-01T00:37:00Z\tibm_fez\t\tnew\n")

    def test_a_ledger_without_the_column_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="malformed ledger row"):
            self._read(
                tmp_path,
                "poll_time_utc\tbackend\tdecision\n2026-09-01T00:37:00Z\tibm_fez\tnew\n",
            )


class TestRefusesToPublishAZero:
    """A dashboard reporting zero device states is worse than no dashboard."""

    FLOORS: ClassVar[list[str]] = ["--floor", "NC-012=1170"]

    @staticmethod
    def _with_ledger(tmp_path: Path) -> None:
        ledger = tmp_path / "ledger"
        ledger.mkdir()
        (ledger / "2026-09.tsv").write_text(
            "poll_time_utc\tbackend\tlast_update_date\tdecision\n"
            "2026-09-09T18:00:00Z\tibm_fez\t20260909T180000Z\tnew\n",
            encoding="utf-8",
        )

    def test_an_absent_index_publishes_nothing(self, tmp_path: Path) -> None:
        """The state of calibration-data on the first scheduled run after merge."""
        self._with_ledger(tmp_path)
        assert main(["--root", str(tmp_path), *self.FLOORS]) == NOTHING_TO_PUBLISH
        assert not (tmp_path / "health").exists()

    def test_a_header_only_index_publishes_nothing(self, tmp_path: Path) -> None:
        """What the poll workflow leaves behind before the backfill is dispatched."""
        self._with_ledger(tmp_path)
        health = tmp_path / "health"
        health.mkdir()
        (health / "state-index.tsv").write_text(
            "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n", encoding="utf-8"
        )
        assert main(["--root", str(tmp_path), *self.FLOORS]) == NOTHING_TO_PUBLISH
        assert not (health / "metrics.json").exists()
        assert not (health / "progress.svg").exists()

    def test_one_indexed_document_is_enough_to_publish(self, tmp_path: Path) -> None:
        """The guard must not swallow a small but real archive."""
        self._with_ledger(tmp_path)
        health = tmp_path / "health"
        health.mkdir()
        (health / "state-index.tsv").write_text(
            "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
            "a.json\t2026-09-09T17:00:00Z\tdigest\t1\n",
            encoding="utf-8",
        )
        assert main(["--root", str(tmp_path), *self.FLOORS]) == 0
        assert (health / "progress.svg").exists()
        metrics = json.loads((health / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["documents_total"] == 1 and metrics["states_total"] == 1
