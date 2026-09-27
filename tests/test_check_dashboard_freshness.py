"""Guards on the dashboard heartbeat and the alarm that reads it.

The defect these pin is not in the renderer's arithmetic, it is in what the
workflow chose to keep. ``calibration-health.yml`` used to run
``git restore --staged health/metrics.json`` and exit whenever the rendered SVG
was unchanged, so a render that found nothing new committed nothing at all. A
quiet archive and a renderer that had stopped weeks ago then left byte-identical
state on ``calibration-data``, separable only from Actions run history, which
expires at ~90 days. ADR-025 records that same failure for the poller and fixes
it by writing a record on every run, including the no-ops.

So the invariants below are about *evidence*, and several of them read the
workflow files directly: no assertion about ``build_metrics`` can catch a commit
step that throws the result away.

Workflows are parsed with ``re`` rather than a YAML library for the reason
``tests/test_calibration_poll_workflow.py`` already gives: PyYAML is not a
declared dependency of this project, and adding one to assert a handful of lines
would be a poor trade.
"""

from __future__ import annotations

import ast
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.check_dashboard_freshness import (
    FUTURE_TOLERANCE_HOURS,
    UNDECIDABLE,
    evaluate,
    main,
    read_generated_at,
    validate_bound,
)
from scripts.pipeline_health import build_metrics

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
MAX_AGE = 48.0
ROOT = Path(__file__).resolve().parents[1]
HEALTH_WORKFLOW = ROOT / ".github/workflows/calibration-health.yml"
POLL_WORKFLOW = ROOT / ".github/workflows/calibration-poll.yml"
CHECKER = ROOT / "scripts" / "check_dashboard_freshness.py"


def _write_metrics(root: Path, payload: object) -> Path:
    """Put a metrics document where the checker looks for one."""
    health = root / "health"
    health.mkdir(parents=True, exist_ok=True)
    path = health / "metrics.json"
    body = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _run(root: Path, *, now: str = "2026-09-17T12:00:00Z", bound: str = "48") -> int:
    """Invoke the CLI the way both workflow steps do."""
    return main(["--root", str(root), "--max-age-hours", bound, "--now", now])


def _uncommented(text: str) -> str:
    """Drop whole-line comments.

    The workflow guards below look for shapes that the surrounding comments also
    *describe*, because each comment explains the defect being fixed by quoting
    the command that caused it. Without this, a guard would read its own
    explanation and pass, or fail, for the wrong reason.
    """
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _env_value(text: str, key: str) -> str:
    match = re.search(rf"^  {key}: '([^']*)'", text, re.MULTILINE)
    assert match, f"{key} is missing from the workflow's env block"
    return match.group(1)


class TestEvaluate:
    """The verdict itself, against a supplied instant so nothing reads a clock."""

    def test_a_recent_heartbeat_is_fresh(self) -> None:
        verdict = evaluate(NOW - timedelta(hours=5), NOW, MAX_AGE)
        assert verdict.is_fresh
        assert verdict.age_hours == pytest.approx(5.0)

    def test_a_heartbeat_older_than_the_bound_is_stale(self) -> None:
        verdict = evaluate(NOW - timedelta(hours=49), NOW, MAX_AGE)
        assert not verdict.is_fresh
        assert "has not completed a render since" in verdict.message()

    def test_the_bound_itself_is_still_fresh(self) -> None:
        """Inclusive on purpose: a render served exactly at the bound is not late."""
        assert evaluate(NOW - timedelta(hours=MAX_AGE), NOW, MAX_AGE).is_fresh

    def test_a_heartbeat_from_the_future_is_not_fresh(self) -> None:
        """Otherwise a bad clock reads as fresh forever and disables the alarm."""
        verdict = evaluate(NOW + timedelta(hours=6), NOW, MAX_AGE)
        assert not verdict.is_fresh
        assert "in the future" in verdict.message()
        assert "cannot be trusted" in verdict.message()

    def test_clock_skew_within_tolerance_is_not_an_alarm(self) -> None:
        ahead = timedelta(hours=FUTURE_TOLERANCE_HOURS / 2)
        assert evaluate(NOW + ahead, NOW, MAX_AGE).is_fresh

    def test_a_naive_instant_is_read_as_utc_not_local(self) -> None:
        """A local-time reading would move the verdict by the runner's offset."""
        naive = (NOW - timedelta(hours=5)).replace(tzinfo=None)
        assert evaluate(naive, NOW, MAX_AGE).age_hours == pytest.approx(5.0)

    def test_the_message_names_the_bound_it_was_judged_against(self) -> None:
        """UC-6: a reader must be able to tell what number produced the verdict."""
        assert "tolerance 48 h" in evaluate(NOW, NOW, MAX_AGE).message()

    @pytest.mark.parametrize("bound", [math.inf, math.nan, 0.0, -12.0])
    def test_a_bound_that_cannot_be_compared_honestly_is_refused(self, bound: float) -> None:
        """Refused where the verdict is built, not only at the CLI.

        ``inf`` calls every age fresh, so the alarm is off. ``nan`` makes every
        comparison false, so ``is_fresh`` says stale while ``message`` falls
        through to the "refreshed" wording. ``evaluate`` is a public entry
        point, so guarding only the CLI would leave both reachable.
        """
        with pytest.raises(ValueError, match="finite, positive"):
            evaluate(NOW - timedelta(hours=576), NOW, bound)


class TestReadGeneratedAt:
    """Every unreadable shape collapses to "cannot judge", never to "stopped"."""

    def test_an_absent_file_is_undecidable(self, tmp_path: Path) -> None:
        assert read_generated_at(tmp_path / "health" / "metrics.json") is None

    def test_malformed_json_is_undecidable(self, tmp_path: Path) -> None:
        assert read_generated_at(_write_metrics(tmp_path, "{not json")) is None

    def test_a_missing_field_is_undecidable(self, tmp_path: Path) -> None:
        assert read_generated_at(_write_metrics(tmp_path, {"states_total": 504})) is None

    def test_an_unparseable_timestamp_is_undecidable(self, tmp_path: Path) -> None:
        payload = {"generated_at": "last Tuesday"}
        assert read_generated_at(_write_metrics(tmp_path, payload)) is None

    def test_a_valid_heartbeat_comes_back_in_utc(self, tmp_path: Path) -> None:
        payload = {"generated_at": "2026-09-17T08:45:00.574976Z"}
        recovered = read_generated_at(_write_metrics(tmp_path, payload))
        assert recovered is not None
        assert recovered.utcoffset() == timedelta(0)


class TestProducerAndConsumerAgree:
    """The renderer writes this field and the alarm reads it; pin them together."""

    def test_the_renderers_own_metrics_document_is_readable(self, tmp_path: Path) -> None:
        """A change to ``generated_at``'s format must break here, loudly.

        Round-tripped through the same ``json`` serialisation
        ``pipeline_health.main`` uses, so this fails if either side of the
        contract moves without the other.
        """
        metrics = build_metrics([], [], [("NC-012", 1170)], NOW)
        path = _write_metrics(tmp_path, json.loads(json.dumps(metrics, sort_keys=True)))
        assert read_generated_at(path) == NOW

    def test_a_freshly_rendered_document_reads_as_fresh(self, tmp_path: Path) -> None:
        _write_metrics(tmp_path, build_metrics([], [], [("NC-012", 1170)], NOW))
        assert _run(tmp_path, now=NOW.isoformat()) == 0


class TestExitCodes:
    """The contract both workflow steps are written against."""

    def test_fresh_exits_zero(self, tmp_path: Path) -> None:
        _write_metrics(tmp_path, {"generated_at": "2026-09-17T08:00:00Z"})
        assert _run(tmp_path) == 0

    def test_stale_exits_one(self, tmp_path: Path) -> None:
        _write_metrics(tmp_path, {"generated_at": "2026-09-10T08:00:00Z"})
        assert _run(tmp_path) == 1

    def test_an_unreadable_dashboard_is_undecidable_not_stale(self, tmp_path: Path) -> None:
        """Exit 3 matches ``pipeline_health``'s "nothing to publish" convention."""
        assert _run(tmp_path) == UNDECIDABLE

    def test_the_bound_is_required(self, tmp_path: Path) -> None:
        """FR-7: the threshold is configuration, so there is no default to fall back on."""
        with pytest.raises(SystemExit) as excinfo:
            main(["--root", str(tmp_path)])
        assert excinfo.value.code == 2

    @pytest.mark.parametrize("bound", ["0", "-12"])
    def test_a_non_positive_bound_is_rejected(self, tmp_path: Path, bound: str) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--root", str(tmp_path), "--max-age-hours", bound])
        assert excinfo.value.code == 2

    @pytest.mark.parametrize("bound", ["inf", "Infinity", "1e999", "nan", "NaN"])
    def test_a_non_finite_bound_is_rejected(self, tmp_path: Path, bound: str) -> None:
        """Python's ``float`` parses every one of these, and all are positive or unordered.

        Before this guard, ``inf`` judged a 576 h old heartbeat fresh and exited
        0, and ``nan`` exited 1 under a message saying the dashboard was
        refreshed (raised in the PR #102 review). The stale heartbeat is written
        so that a regression shows up as a verdict instead of as exit 3.
        """
        _write_metrics(tmp_path, {"generated_at": "2026-09-01T00:00:00Z"})
        with pytest.raises(SystemExit) as excinfo:
            _run(tmp_path, now="2026-09-25T00:00:00Z", bound=bound)
        assert excinfo.value.code == 2


class TestWorkflowWiring:
    """The half no unit test can reach: what the workflows do with the result."""

    def test_the_renderer_no_longer_discards_its_heartbeat(self) -> None:
        """The defect itself. ``metrics.json`` must survive an unchanged render."""
        body = _uncommented(HEALTH_WORKFLOW.read_text(encoding="utf-8"))
        assert "git restore --staged" not in body, (
            "discarding metrics.json makes a stopped renderer indistinguishable "
            "from a quiet archive, which is the defect this change fixes"
        )

    def test_the_renderer_commits_whenever_anything_changed(self) -> None:
        """The other half: the guard may skip an empty commit and nothing more.

        The only ``exit 0`` left in the commit step must be the empty-stage one.
        The defect was an early exit taken while metrics.json *had* changed, so
        the count is the invariant worth pinning, not the wording.
        """
        body = _uncommented(HEALTH_WORKFLOW.read_text(encoding="utf-8"))
        step = body[body.index("- name: Commit the render") :]
        assert "if git diff --cached --quiet; then" in step
        assert step.count("exit 0") == 1

    def test_the_svg_is_still_only_committed_when_it_moved(self) -> None:
        """FR-6's churn budget survives: the 8.5 KB graphic keeps its own message."""
        body = _uncommented(HEALTH_WORKFLOW.read_text(encoding="utf-8"))
        assert "git diff --cached --quiet -- health/progress.svg" in body
        assert "health: refresh pipeline dashboard" in body
        assert "health: heartbeat, rendered dashboard unchanged" in body

    def test_the_poller_carries_the_alarm(self) -> None:
        """A renderer cannot report its own death, so the hourly job must."""
        body = _uncommented(POLL_WORKFLOW.read_text(encoding="utf-8"))
        assert "check_dashboard_freshness.py" in body

    def test_the_alarm_cannot_fail_the_poll(self) -> None:
        """A stale dashboard must never cost a poll or the ledger row it writes."""
        body = _uncommented(POLL_WORKFLOW.read_text(encoding="utf-8"))
        start = body.index("check_dashboard_freshness.py")
        assert "|| true" in body[start : start + 240]

    def test_both_workflows_carry_the_same_bound(self) -> None:
        """Two files, one number: NC-053. Actions cannot share an env across them."""
        health = _env_value(HEALTH_WORKFLOW.read_text(encoding="utf-8"), "DASHBOARD_MAX_AGE_HOURS")
        poll = _env_value(POLL_WORKFLOW.read_text(encoding="utf-8"), "DASHBOARD_MAX_AGE_HOURS")
        assert health == poll
        # The script's own check, so any value CI accepts is one the alarm
        # accepts. ``float(health) > 0`` alone accepted 'inf'.
        validate_bound(float(health))

    def test_the_bound_is_not_a_literal_in_the_checker(self) -> None:
        """FR-7, as ``TestFloorsAreConfiguration`` applies it to the floors.

        Asserted over the parsed numeric constants rather than by substring, as
        that test can afford to do with a floor of 1170. The bound is 48 and the
        issue this pipeline implements is #48, so a substring search matches the
        prose and proves nothing about the code.
        """
        bound = _env_value(HEALTH_WORKFLOW.read_text(encoding="utf-8"), "DASHBOARD_MAX_AGE_HOURS")
        tree = ast.parse(CHECKER.read_text(encoding="utf-8"))
        literals = {
            float(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, int | float)
            and not isinstance(node.value, bool)
        }
        assert float(bound) not in literals
