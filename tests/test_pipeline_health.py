"""Offline conformance tests for the calibration pipeline-health readout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

from scripts.pipeline_health import PollRow, StateRow, build_metrics, main, render_svg

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
    assert len(metrics["states_per_day_30d"]) == 30


def test_zero_rate_has_no_finite_projection_and_hour_boundary_is_included() -> None:
    old = StateRow("a.json", NOW - timedelta(days=8), "a", True)
    poll = PollRow(NOW.replace(minute=0), "duplicate")
    metrics = build_metrics([old], [poll], [("candidate", 2)], NOW)
    assert metrics["floors"][0]["projected_days"] is None
    assert metrics["ledger_hour_coverage_72h"] == 1 / 72


def test_svg_is_deterministic_well_formed_and_safe() -> None:
    metrics = build_metrics([], [], [("candidate", 630)], NOW)
    svg = render_svg(metrics)
    assert svg == render_svg(metrics)
    assert "<script" not in svg and "<foreignObject" not in svg and "href=" not in svg
    root = ElementTree.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 900 480"
    assert 'fill="#f8fafc"' in svg


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
    args = ["--root", str(tmp_path), "--now", "2026-09-04T12:00:00Z"]
    assert main(args) == 0
    first_json = (health / "metrics.json").read_bytes()
    first_svg = (health / "progress.svg").read_bytes()
    assert main(args) == 0
    assert (health / "metrics.json").read_bytes() == first_json
    assert (health / "progress.svg").read_bytes() == first_svg
