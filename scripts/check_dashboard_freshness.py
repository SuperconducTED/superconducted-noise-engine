"""Report whether the published pipeline-health dashboard is still being refreshed.

Why this exists
---------------
``calibration-health.yml`` renders ``health/metrics.json`` and
``health/progress.svg`` once a day and, under FR-6, publishes the graphic only
when its bytes change. Until the companion change to that workflow, a render
that changed nothing also ran ``git restore --staged health/metrics.json`` and
committed nothing at all, so a quiet archive and a **stopped renderer** left
byte-identical state on ``calibration-data``. That is precisely the defect
ADR-025 records for the poller in its own Context -- "a quiet stretch looked
identical to a stopped poller, and the run history that could have told them
apart expires at ~90 days" -- reappearing in the branch's second writer, which
was added after that ADR was written.

``metrics.json`` now commits on every render, so ``generated_at`` is a truthful
heartbeat and the git history of that one file is a durable render log. This
script is the *reader* of that heartbeat. Issue #48's own summary is that #47
"lands the raw instrument -- ADR-024's poll ledger -- but nothing reads it"; a
heartbeat with no reader would repeat exactly the criticism this pipeline was
built to answer.

It is deliberately run by the **hourly poller** rather than only by the
renderer. A process cannot report its own death: the renderer can notice a gap
only once it is alive again, so the alarm has to come from somewhere that keeps
running while the renderer does not. The poller already materialises the data
branch, so this costs one file read and never touches the filing path.

Contract
--------
A pure comparison of ``generated_at`` against a supplied instant. No network and
no archive traversal (NFR-1); stdlib only.

``--max-age-hours`` is **required**. FR-7's rule that a bound is configuration
supplied by the workflow, and never a literal in code, applies to this threshold
for the same reason it applies to the candidate training floors: a number baked
in here could not be changed without a code review, and could not state its own
source. It must also be finite and positive (``validate_bound``): ``float``
parses ``inf`` and ``nan``, and either one would disable the alarm without
saying so.

Exit codes: **0** the dashboard is fresh, **1** it is stale or its heartbeat
cannot be trusted, **3** no dashboard could be read, so freshness is not
decidable rather than bad. Argparse keeps **2** for a bad invocation, matching
``pipeline_health``.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.pipeline_health import parse_time

UNDECIDABLE = 3
"""Exit code for a dashboard that could not be read. See the module docstring."""

FUTURE_TOLERANCE_HOURS = 1.0
"""How far ahead of ``now`` a heartbeat may sit before it is called broken.

A ``generated_at`` in the future would otherwise read as fresh forever, which
disables this alarm silently -- the same class of failure the script exists to
catch, so it is not left unguarded. Runner clocks are NTP-synced and the skew
between two runs is sub-second, so a gap approaching an hour is a fault and not
jitter.
"""


def validate_bound(max_age_hours: float) -> float:
    """Return ``max_age_hours`` unchanged, or raise ``ValueError`` if it cannot be a bound.

    A staleness bound has to be a finite, positive number of hours, and
    ``float`` accepts two values that are neither and would each switch the
    alarm off quietly. ``inf`` is greater than every age, so a heartbeat of any
    age reads as fresh. ``nan`` compares false against everything, so the
    verdict says stale while ``Freshness.message`` falls through to its
    "refreshed" wording. Zero and negatives were already refused by the CLI and
    are refused here as well, so there is one rule rather than two.

    There is deliberately no upper limit: one would be a number written into
    this module, which FR-7 rules out. A very large finite bound is still a
    visible, reviewable edit to the workflow's env block.
    """
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError(
            f"the staleness bound must be a finite, positive number of hours, not {max_age_hours!r}"
        )
    return max_age_hours


@dataclass(frozen=True)
class Freshness:
    """A freshness verdict together with the evidence it rests on."""

    generated_at: datetime
    age_hours: float
    max_age_hours: float

    def __post_init__(self) -> None:
        """Refuse a bound no verdict can honestly be reached against."""
        validate_bound(self.max_age_hours)

    @property
    def is_fresh(self) -> bool:
        """True when the heartbeat is recent and not implausibly ahead of ``now``."""
        return -FUTURE_TOLERANCE_HOURS <= self.age_hours <= self.max_age_hours

    def message(self) -> str:
        """One actionable line, naming the threshold the verdict was reached against."""
        stamp = self.generated_at.isoformat().replace("+00:00", "Z")
        tolerance = f"tolerance {self.max_age_hours:g} h"
        if self.age_hours < -FUTURE_TOLERANCE_HOURS:
            return (
                f"health/metrics.json is stamped {stamp}, {-self.age_hours:.1f} h in the "
                "future; the dashboard heartbeat cannot be trusted and the staleness "
                "alarm is not protecting anything until it is corrected"
            )
        if self.age_hours > self.max_age_hours:
            return (
                f"the pipeline-health dashboard was last refreshed {stamp}, "
                f"{self.age_hours:.1f} h ago ({tolerance}); Calibration Pipeline Health "
                "has not completed a render since, so the published SVG is not evidence "
                "about the archive as it stands now"
            )
        return (
            f"pipeline-health dashboard refreshed {stamp}, {self.age_hours:.1f} h ago ({tolerance})"
        )


def read_generated_at(path: Path) -> datetime | None:
    """Return the dashboard's heartbeat, or ``None`` when there is none to read.

    Absent, unparseable, and missing-or-malformed ``generated_at`` all collapse
    to ``None`` deliberately. Each means the same thing to the caller -- that
    freshness is not decidable from this file -- and none of them is evidence
    that the renderer stopped, which is the one conclusion this script must not
    reach without grounds.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return parse_time(str(payload["generated_at"]))
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
        return None


def _as_utc(moment: datetime) -> datetime:
    """Normalise an instant to UTC, reading a naive one as UTC rather than local.

    ``datetime.astimezone`` assumes a naive instant is in the *system's* local
    zone, so calling it alone would shift a verdict by the runner's offset and
    silently move the alarm by up to half a day. ``parse_time`` already applies
    this rule to everything it parses; this keeps the same rule on the public
    entry point, which callers may reach with a datetime of their own.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def evaluate(generated_at: datetime, now: datetime, max_age_hours: float) -> Freshness:
    """Judge one heartbeat against ``now``, in hours, on the UTC clock."""
    stamped, instant = _as_utc(generated_at), _as_utc(now)
    age = (instant - stamped).total_seconds() / 3600
    return Freshness(stamped, age, max_age_hours)


def main(argv: Iterable[str] | None = None) -> int:
    """Read the dashboard heartbeat below a data-branch root and report on it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="Calibration-data checkout.")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        required=True,
        metavar="HOURS",
        help="Staleness tolerance in hours. Required: the bound is configuration "
        "supplied by the workflow and never a literal in this module (FR-7).",
    )
    parser.add_argument(
        "--now", type=parse_time, default=None, help="UTC instant to judge against (for tests)."
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        validate_bound(args.max_age_hours)
    except ValueError as error:
        parser.error(f"--max-age-hours: {error}")
    generated_at = read_generated_at(args.root / "health" / "metrics.json")
    if generated_at is None:
        print(
            "::warning::health/metrics.json is absent or unreadable, so dashboard "
            "freshness could not be judged. Expected only before the one-time "
            "backfill has been dispatched; at any other time it is itself a fault."
        )
        return UNDECIDABLE
    verdict = evaluate(generated_at, args.now or datetime.now(UTC), args.max_age_hours)
    if verdict.is_fresh:
        print(f"::notice::{verdict.message()}")
        return 0
    print(f"::warning::{verdict.message()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
