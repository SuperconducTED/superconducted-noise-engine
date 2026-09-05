"""
Create deterministic pipeline health metrics using the check out of calibration data.
The scheduled command reads only ``health/state-index.tsv`` and ``ledger/*.tsv``,
never traversing the entire snapshots archive.  The module is stdlib-only and can
be used directly for metrics computation without creating a subprocess
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StateRow:
    """One append-only state-index record."""

    filename: str
    timestamp: datetime
    digest: str
    is_new: bool


@dataclass(frozen=True)
class PollRow:
    """One ADR-025 ledger record."""

    timestamp: datetime
    decision: str


def parse_time(value: str) -> datetime:
    """Parse ISO-8601 timestamps and normalize them to UTC."""
    value = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_index(path: Path) -> list[StateRow]:
    """Read a state index, rejecting malformed rows rather than guessing."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if set(reader.fieldnames or ()) != {
            "snapshot_filename",
            "last_update_date",
            "qubit_digest",
            "is_new_state",
        }:
            raise ValueError(f"{path} has an unexpected header")
        rows = list(reader)
    required = {"snapshot_filename", "last_update_date", "qubit_digest", "is_new_state"}
    result: list[StateRow] = []
    for number, row in enumerate(rows, 2):
        if None in row or any(not row[key] for key in required - {"is_new_state"}):
            raise ValueError(f"{path}:{number}: malformed index row")
        if row["is_new_state"] not in {"0", "1"}:
            raise ValueError(f"{path}:{number}: is_new_state must be 0 or 1")
        result.append(
            StateRow(
                row["snapshot_filename"],
                parse_time(row["last_update_date"]),
                row["qubit_digest"],
                row["is_new_state"] == "1",
            )
        )
    return result


def read_ledger(directory: Path) -> list[PollRow]:
    """Read all monthly ADR-025 ledgers in ``directory``."""
    result: list[PollRow] = []
    for path in sorted(directory.glob("*.tsv")) if directory.exists() else []:
        with path.open(encoding="utf-8", newline="") as handle:
            for number, row in enumerate(csv.DictReader(handle, delimiter="\t"), 2):
                if row.get("poll_time_utc") is None or row.get("decision") is None:
                    raise ValueError(f"{path}:{number}: malformed ledger row")
                result.append(PollRow(parse_time(row["poll_time_utc"]), row["decision"]))
    return result


def _floor_values(values: Sequence[str]) -> list[tuple[str, int]]:
    """Parse ``label=value`` candidate floors."""
    result: list[tuple[str, int]] = []
    for value in values:
        label, separator, raw = value.partition("=")
        if not separator or not label or not raw.isdecimal() or int(raw) <= 0:
            raise ValueError(f"floor must be LABEL=POSITIVE_INTEGER, got {value!r}")
        result.append((label, int(raw)))
    return result


def build_metrics(
    states: Sequence[StateRow],
    polls: Sequence[PollRow],
    floors: Sequence[tuple[str, int]],
    now: datetime,
) -> dict[str, Any]:
    """Calculate published metrics relative to a supplied UTC instant."""
    now = now.astimezone(UTC)
    documents = len(states)
    digests = {row.digest for row in states}
    states_total = len(digests)
    new_rows = [row for row in states if row.is_new]
    last_new = max((row.timestamp for row in new_rows), default=None)
    since = (now - last_new).total_seconds() / 3600 if last_new else None
    window24 = now - timedelta(hours=24)
    window7 = now - timedelta(days=7)
    states24 = sum(row.is_new and row.timestamp > window24 for row in states)
    states7 = sum(row.is_new and row.timestamp > window7 for row in states)
    start30 = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
    daily_states = [
        sum(
            row.is_new
            and start30 + timedelta(days=day) <= row.timestamp < start30 + timedelta(days=day + 1)
            for row in states
        )
        for day in range(30)
    ]
    recent_polls = [row for row in polls if row.timestamp > window24]
    start72 = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=71)
    hours = [start72 + timedelta(hours=offset) for offset in range(72)]
    fired = {row.timestamp.replace(minute=0, second=0, microsecond=0) for row in polls}
    hour_values = [hour in fired for hour in hours]
    index_head = None if not states else states[-1].filename
    floor_metrics: list[dict[str, Any]] = []
    rate = states7 / 7
    for label, value in floors:
        remaining = max(value - states_total, 0)
        projected_days = remaining / rate if rate > 0 else None
        projected_date = (
            (now + timedelta(days=projected_days)).date().isoformat()
            if projected_days
            else (now.date().isoformat() if remaining == 0 else None)
        )
        floor_metrics.append(
            {
                "label": label,
                "value": value,
                "states_remaining": remaining,
                "projected_days": projected_days,
                "projected_date": projected_date,
            }
        )
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "index_head": index_head,
        "documents_total": documents,
        "states_total": states_total,
        "duplication_ratio": 0 if not documents else 1 - states_total / documents,
        "states_added_24h": states24,
        "states_added_7d": states7,
        "states_per_day_7d": rate,
        "states_per_day_30d": daily_states,
        "hours_since_last_new_state": since,
        "polls_fired_24h": len(recent_polls),
        "polls_yielding_new_state_24h": sum(row.decision == "new" for row in recent_polls),
        "ledger_hour_coverage_72h": sum(hour_values) / 72,
        "poll_hours_72h": hour_values,
        "floors": floor_metrics,
    }


def render_svg(metrics: dict[str, Any]) -> str:
    """Render a self-contained, GitHub-safe SVG with no time-varying content."""
    states = int(metrics["states_total"])
    documents = int(metrics["documents_total"])
    duplicate = float(metrics["duplication_ratio"]) * 100
    stale = metrics["hours_since_last_new_state"]
    max_floor = max((int(floor["value"]) for floor in metrics["floors"]), default=max(states, 1))
    width = 900
    bar_x, bar_width = 55, 790
    progress = min(states / max_floor, 1) * bar_width
    stale_text = "—" if stale is None else f"{float(stale):.1f}"
    coverage = float(metrics["ledger_hour_coverage_72h"]) * 100
    rate_text = float(metrics["states_per_day_7d"])
    labels = [
        '<text x="55" y="43" class="title">Calibration pipeline health</text>',
        f'<text x="55" y="76" class="value">{states} states</text>',
        f'<text x="300" y="76" class="metric">{documents} documents</text>',
        f'<text x="525" y="76" class="metric">{duplicate:.1f}% duplicate</text>',
        f'<text x="55" y="116" class="label">Hours since last new state: {stale_text}</text>',
        '<text x="55" y="154" class="label">Distinct states against candidate floors</text>',
        f'<rect x="{bar_x}" y="165" width="{bar_width}" height="24" rx="4" fill="#d7e0ea"/>',
        f'<rect x="{bar_x}" y="165" width="{progress:.2f}" height="24" rx="4" fill="#166534"/>',
    ]
    for floor in metrics["floors"]:
        x = bar_x + min(int(floor["value"]) / max_floor, 1) * bar_width
        label = html.escape(f"{floor['label']}: {floor['value']}")
        labels.append(f'<path d="M{x:.2f} 159v36" stroke="#9a3412" stroke-width="2"/>')
        labels.append(f'<text x="{x:.2f}" y="207" class="tiny" text-anchor="middle">{label}</text>')
    labels.append('<text x="55" y="252" class="label">Poll health — last 72 hours</text>')
    for index, fired in enumerate(metrics["poll_hours_72h"]):
        x = 55 + index * 11
        colour = "#166534" if fired else "#cbd5e1"
        labels.append(f'<rect x="{x}" y="263" width="8" height="20" rx="1" fill="{colour}"/>')
    labels.append(f'<text x="55" y="310" class="label">72-hour coverage: {coverage:.1f}%</text>')
    labels.append('<text x="55" y="350" class="label">New states per day — trailing 30 days</text>')
    daily_states = [int(value) for value in metrics["states_per_day_30d"]]
    peak = max(daily_states, default=0)
    for index, value in enumerate(daily_states):
        height = 0 if peak == 0 else value / peak * 70
        x = 55 + index * 25
        labels.append(f'<rect x="{x}" y="{445 - height:.2f}" width="18" height="{height:.2f}"')
        labels.append(' fill="#2563eb"/>')
    labels.append(f'<text x="285" y="438" class="metric">{rate_text:.2f} states/day</text>')
    body = "".join(labels)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 480" role="img" '
        'aria-label="Calibration pipeline health dashboard">\n'
        "<style>.title{font:700 24px sans-serif;fill:#0f172a}.value{font:700 22px sans-serif;"
        "fill:#166534}.metric{font:16px sans-serif;fill:#1e293b}.label{font:15px sans-serif;"
        "fill:#334155}.tiny{font:12px sans-serif;fill:#7c2d12}</style>\n"
        f'<rect width="100%" height="100%" fill="#f8fafc"/>{body}</svg>\n'
    )


def main(argv: Iterable[str] | None = None) -> int:
    """Write ``metrics.json`` and ``progress.svg`` below a data-branch root."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--floor", action="append", default=None)
    parser.add_argument(
        "--now", type=parse_time, default=None, help="UTC render instant (for tests)."
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    now = args.now or datetime.now(UTC)
    root: Path = args.root
    metrics = build_metrics(
        read_index(root / "health/state-index.tsv"),
        read_ledger(root / "ledger"),
        _floor_values(args.floor or ["NC-012=630", "TanhBellMF=675"]),
        now,
    )
    health = root / "health"
    health.mkdir(parents=True, exist_ok=True)
    (health / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (health / "progress.svg").write_text(render_svg(metrics), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
