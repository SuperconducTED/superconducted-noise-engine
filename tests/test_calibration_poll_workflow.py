"""Guards on `.github/workflows/calibration-poll.yml` that CI can actually enforce.

The sweep cron string has to appear in three places, because GitHub will not let
it appear in one:

* the ``schedule:`` entry, which is what fires the run;
* ``env.SWEEP_CRON``, which the step compares ``github.event.schedule`` against;
* ``timeout-minutes``, because job-level keys cannot read the ``env`` context.

If those drift apart, nothing fails loudly. The sweep still runs, but silently
reverts to the ten-minute poll bound and dies mid-window, which is the defect
issue #49 section 2.2 was written about. A test is cheaper than rediscovering it.

Parsed with ``re`` rather than a YAML library on purpose: PyYAML is not a
declared dependency of this project, and adding one to assert four lines of a
workflow file would be a poor trade.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/calibration-poll.yml"


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _env_value(workflow: str, key: str) -> str:
    match = re.search(rf"^  {key}: '([^']*)'", workflow, re.MULTILINE)
    assert match, f"{key} is missing from the workflow's env block"
    return match.group(1)


def _schedule_crons(workflow: str) -> list[str]:
    block = re.search(r"^  schedule:\n(.*?)^  \w", workflow, re.MULTILINE | re.DOTALL)
    assert block, "no schedule: block"
    return re.findall(r"^    - cron: '([^']*)'", block.group(1), re.MULTILINE)


def test_the_sweep_cron_is_actually_scheduled(workflow: str) -> None:
    assert _env_value(workflow, "SWEEP_CRON") in _schedule_crons(workflow)


def test_the_hourly_poll_is_still_scheduled(workflow: str) -> None:
    """The sweep supplements the hourly sample; it does not replace it.

    PR #89 raised that sample from one entry per hour to four (:07, :22, :37,
    :52), because GitHub declines to dispatch about three quarters of the
    schedules it is asked for, and it shipped without a guard of its own. The
    count is asserted as a floor rather than as an exact set: retuning which
    minutes are used is a legitimate future change, whereas quietly collapsing
    back to a single entry would undo #89 without failing anything.

    ``:37`` is named because NC-008 registers it as the polling target, and #89
    kept it for exactly that reason.
    """
    crons = _schedule_crons(workflow)
    hourly = [c for c in crons if c.endswith("* * * *") and not c.split()[1].isdigit()]
    assert len(hourly) >= 4, (
        f"#89 spread the hourly sample across four entries per hour; {crons} carries "
        f"{len(hourly)}, so that mitigation has been undone"
    )
    assert "37 * * * *" in hourly, (
        f"NC-008 registers :37 as the polling target and it is missing from {crons}"
    )


def test_timeout_covers_the_sweep(workflow: str) -> None:
    """Section 2.2: `inputs` is empty on a schedule event, so the sweep needs its own arm."""
    match = re.search(r"^    timeout-minutes: (.+)$", workflow, re.MULTILINE)
    assert match, "no timeout-minutes"
    expression = match.group(1)
    assert _env_value(workflow, "SWEEP_CRON") in expression, (
        "timeout-minutes does not name the sweep cron, so a scheduled sweep would "
        "inherit the short poll bound and be killed mid-window"
    )
    assert "inputs.historical_start" in expression, (
        "a dispatched backfill still needs the long bound"
    )


def test_the_sweep_counts_as_a_backfill(workflow: str) -> None:
    """The same null-inputs trap as the timeout, with a quieter failure.

    With ``IS_BACKFILL=0`` a lossy historical re-read is classified ``collision``
    rather than ``duplicate-partial``, so every sweep would write junk into
    ``collisions/`` and warn. ADR-025 treats a non-empty ``collisions/`` as a
    signal precisely because it is normally empty.
    """
    match = re.search(r"^          IS_BACKFILL: (.+)$", workflow, re.MULTILINE)
    assert match, "no IS_BACKFILL"
    expression = match.group(1)
    # Step-level env CAN read the env context, unlike timeout-minutes, so
    # referencing SWEEP_CRON is preferred here over repeating the literal a
    # fourth time. Accept either, and require only that the two are bound.
    assert "env.SWEEP_CRON" in expression or _env_value(workflow, "SWEEP_CRON") in expression, (
        "IS_BACKFILL is not tied to the sweep cron, so a scheduled sweep would file "
        "every lossy re-read as a collision"
    )
    assert "inputs.historical_start" in expression, "a dispatched backfill is still a backfill"


def test_sweep_window_and_step_are_configuration(workflow: str) -> None:
    """Both are read from env in the step, so they are tunable without touching shell."""
    assert int(_env_value(workflow, "SWEEP_WINDOW_HOURS")) > 0
    assert float(_env_value(workflow, "SWEEP_STEP_HOURS")) > 0
    for key in ("SWEEP_WINDOW_HOURS", "SWEEP_STEP_HOURS"):
        assert f"${key}" in workflow, f"{key} is declared but never used"
