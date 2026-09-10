"""Deterministic pipeline-health metrics and SVG for a ``calibration-data`` checkout.

The scheduled command reads only ``health/state-index.tsv`` and ``ledger/*.tsv``,
never traversing the snapshot archive (NFR-1). The module is stdlib-only and its
public functions are importable, so metrics can be computed without a subprocess.

Exit codes: **0** when the dashboard was written, **3** when the state index is
absent or holds no rows, so nothing was written and there is nothing to publish.
A dashboard reporting zero device states is worse than no dashboard: on the first
scheduled run after this lands, before the one-time backfill is dispatched, the
index does not exist yet, and publishing then would put `0 states` on a branch
that holds hundreds. Argparse keeps **2** for a bad invocation.

Rendering contract (NFR-3/FR-6): the SVG carries no clock reading. Every figure in
it is a function of the committed index and ledger, plus the position of the two
rolling windows FR-5 mandates. ``generated_at`` and the exact
``hours_since_last_new_state`` live in ``metrics.json`` only. Rendering a bare
elapsed-hours figure would change the bytes on every run and make the workflow's
commit-on-change guard unreachable.
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

STALENESS_BANDS: tuple[tuple[float, str], ...] = (
    (24.0, "under 24 h"),
    (72.0, "24 h to 3 days"),
    (168.0, "3 to 7 days"),
)
"""Upper bound in hours, paired with the label shown strictly below it."""

OVER_LAST_BAND = "over 7 days"

NOTHING_TO_PUBLISH = 3
"""Exit code for an index that names no documents. See the module docstring."""

FONT_PX: dict[str, int] = {"title": 24, "value": 22, "metric": 16, "label": 15, "tiny": 12}
"""Rendered size per text class, mirroring ``render_svg``'s ``<style>`` block.

Exported so the section 9.3 bounds check measures each text node at the size it
is actually drawn at instead of inventing its own model;
``test_font_sizes_match_the_style_block`` pins the two together.
"""

ADVANCE_RATIO = 0.62
"""Horizontal advance per character as a fraction of the font size.

A deliberate over-estimate for `sans-serif`, whose real advances are per-glyph
and per-renderer. Bounds work here is one-sided: over-estimating moves a label
inside the canvas and fails the conformance check early, while under-estimating
lets one escape, so the error belongs on this side.
"""


def text_span(x: float, text: str, font_px: float, anchor: str) -> tuple[float, float]:
    """Estimate the horizontal extent a text node occupies, as ``(left, right)``.

    Shared by the renderer, which uses it to choose an anchor, and by the
    section 9.3 conformance test, which uses it to assert nothing escapes the
    canvas. One estimator, so the guard cannot drift from the thing it guards.
    """
    width = len(text) * font_px * ADVANCE_RATIO
    if anchor == "end":
        return (x - width, x)
    if anchor == "middle":
        return (x - width / 2, x + width / 2)
    return (x, x + width)


def _anchor_for(x: float, text: str, font_px: float, canvas: float, margin: float = 8.0) -> str:
    """Choose the anchor that keeps a tick label inside ``canvas``.

    Keyed on where the tick actually sits, never on its position in the floor
    list. FR-7 makes floors free-form configuration and the workflow exposes a
    ``floors`` dispatch input, so "the last one supplied" and "the rightmost"
    are not the same tick. Anchoring the last-supplied label to its end put the
    rightmost label past the viewBox for any ordering but ascending, which no
    caller is obliged to use and none is checked for.
    """
    for anchor in ("middle", "end", "start"):
        left, right = text_span(x, text, font_px, anchor)
        if left >= margin and right <= canvas - margin:
            return anchor
    return "middle"


@dataclass(frozen=True)
class StateRow:
    """One append-only state-index record."""

    filename: str
    timestamp: datetime
    digest: str
    is_new: bool


@dataclass(frozen=True)
class PollRow:
    """One ADR-025 ledger record.

    ``document`` is the ledger's ``last_update_date`` column, which holds the
    archived document's *stem*, while the state index names the same document
    with its ``.json`` suffix. Carrying it is what lets a poll outcome be joined
    to the state it produced; see ``build_metrics``.
    """

    timestamp: datetime
    document: str
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


LEDGER_FIELDS = ("poll_time_utc", "last_update_date", "decision")
"""Ledger columns this module reads. ``backend`` is present but unused here."""


def read_ledger(directory: Path) -> list[PollRow]:
    """Read all monthly ADR-025 ledgers in ``directory``."""
    result: list[PollRow] = []
    for path in sorted(directory.glob("*.tsv")) if directory.exists() else []:
        with path.open(encoding="utf-8", newline="") as handle:
            for number, row in enumerate(csv.DictReader(handle, delimiter="\t"), 2):
                # A ledger missing `last_update_date` would silently give every
                # PollRow an empty document and quietly zero the join below, so
                # it is required here rather than defaulted.
                if any(not row.get(field) for field in LEDGER_FIELDS):
                    raise ValueError(f"{path}:{number}: malformed ledger row")
                result.append(
                    PollRow(
                        parse_time(row["poll_time_utc"]),
                        row["last_update_date"],
                        row["decision"],
                    )
                )
    return result


def staleness_band(hours: float | None) -> str:
    """Bucket ``hours_since_last_new_state`` into the band the SVG renders.

    The bounds are the two thresholds the dashboard already reasons in: 24 h is
    the staleness alarm proposed for issue #48 section 7.3, and 72 h is the
    poll-coverage window. Bucketing is what keeps the rendered bytes a function
    of the committed inputs: a bare elapsed-hours figure advances on every run,
    so the workflow would commit several KB to a 1.17 GB branch daily forever
    and FR-6's commit-on-change guard could never fire. The exact hours stay in
    ``metrics.json``, so nothing rendered is untraceable (UC-6).
    """
    if hours is None:
        return "never"
    for limit, label in STALENESS_BANDS:
        if hours < limit:
            return label
    return OVER_LAST_BAND


def _floor_values(values: Sequence[str]) -> list[tuple[str, int]]:
    """Parse ``label=value`` candidate floors."""
    result: list[tuple[str, int]] = []
    for value in values:
        label, separator, raw = value.partition("=")
        if not separator or not label or not raw.isdecimal() or int(raw) <= 0:
            raise ValueError(f"floor must be LABEL=POSITIVE_INTEGER, got {value!r}")
        result.append((label, int(raw)))
    return result


def first_sightings(states: Sequence[StateRow]) -> dict[str, datetime]:
    """Map each digest to the earliest ``last_update_date`` that carried it.

    Derived rather than read from the index's ``is_new_state`` column, because
    that column is decided by *append order* and the append order is not always
    chronological. The poll workflow supports historical sweeps
    (``IS_BACKFILL``, ``historical_start``), and a sweep files documents older
    than rows already in the index; each one whose digest is not yet present is
    recorded ``is_new_state=1`` even when a later-dated document already carried
    that state. Trusting the column would then over-report exactly the recovery
    the operator swept to achieve: a sweep run to fill a gap the 72-hour strip
    exposed lands rows *inside* the trailing windows, inflating
    ``states_added_24h`` and the acquisition rate that feeds every projection.

    Deriving it here costs one pass and makes every window below independent of
    append order, so no ``--rebuild`` is owed after a sweep. The column stays in
    the index because FR-2 fixes the schema, and it stays parsed and validated
    because a malformed one still means the file cannot be trusted.
    """
    earliest: dict[str, datetime] = {}
    for row in states:
        seen = earliest.get(row.digest)
        if seen is None or row.timestamp < seen:
            earliest[row.digest] = row.timestamp
    return earliest


def build_metrics(
    states: Sequence[StateRow],
    polls: Sequence[PollRow],
    floors: Sequence[tuple[str, int]],
    now: datetime,
) -> dict[str, Any]:
    """Calculate published metrics relative to a supplied UTC instant.

    Every state window below is keyed on ``last_update_date``, the device's own
    clock, never on when the archive happened to observe the document. That is
    the acquisition rate the floor projection needs: it measures how fast the
    backend produces distinct calibration states, so a sweep that *discovers*
    two hundred old states does not read as two hundred states acquired today.

    The two poll fields are the deliberate exception: they answer a question
    about *us* rather than about the device, so they are keyed on poll time.
    ``polls_yielding_new_state_24h`` therefore reads on both clocks at once, and
    the two can disagree without either being wrong. A sweep that recovers a
    state the device published a week ago counts there, because the poll did
    acquire something we did not hold, while ``states_added_24h`` correctly
    leaves it out, because the device did not produce it today. When they
    disagree, the archive gained by catching up rather than by keeping up.
    """
    now = now.astimezone(UTC)
    documents = len(states)
    acquired = first_sightings(states)
    states_total = len(acquired)
    last_new = max(acquired.values(), default=None)
    since = (now - last_new).total_seconds() / 3600 if last_new else None
    window24 = now - timedelta(hours=24)
    window7 = now - timedelta(days=7)
    states24 = sum(moment > window24 for moment in acquired.values())
    states7 = sum(moment > window7 for moment in acquired.values())
    # Thirty *complete* UTC days, ending with yesterday. Anchoring the window on
    # today put a partial day in the last bucket, and the scheduled render fires
    # at 03:17 UTC, so the rightmost bar of the acquisition sparkline was drawn
    # from 3 h 17 min of data, 13.7% of a day, on every scheduled run. FR-5's
    # panel is a *rate* read, and a systematically short final bar misreads it
    # in the one place a reader looks to ask whether the archive is still
    # accumulating. Today is not lost: `states_added_24h` and
    # `states_per_day_7d` both cover it, on rolling windows where a partial day
    # is not a distortion. Excluding it also makes these buckets change once a
    # day rather than continuously, which is one fewer reason for FR-6's
    # commit-on-change guard to fire on a day that gained nothing.
    start30 = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    daily_states = [
        sum(
            start30 + timedelta(days=day) <= moment < start30 + timedelta(days=day + 1)
            for moment in acquired.values()
        )
        for day in range(30)
    ]
    recent_polls = [row for row in polls if row.timestamp > window24]
    # FR-4 asks how many of those polls "produced a new state", so this is
    # decided against the state index and never against the ledger alone.
    # `decision=new` means the *stamp* was not already archived, which the
    # archive says is a different question: at NC-025's duplication two in five
    # newly filed documents carry a device state we already hold. Measured, not
    # reasoned: over `calibration-data` @ `cb7a8c2` rendered at the last ledger
    # instant, counting `decision=new` gave 6 of 6 polls "yielding a new state",
    # a flat 100% against an archive that is 43.4% duplicate; the join below
    # gives 3, which is exactly `states_added_24h` for that window. That is the
    # substitution issue #48 is built to refuse -- "it counts distinct device
    # states, not files" -- and the fixture published it too, carrying
    # `states_added_24h: 0` beside a 2 for a document its own README calls a
    # plain duplicate.
    #
    # Counted as digests rather than rows so a document indexed twice cannot
    # count twice, and resolved through `acquired` so the answer is independent
    # of index append order for the same reason every window above is.
    filed_new = {f"{row.document}.json" for row in recent_polls if row.decision == "new"}
    acquired_by_poll = {
        row.digest
        for row in states
        if row.filename in filed_new and acquired[row.digest] == row.timestamp
    }
    end72 = now.replace(minute=0, second=0, microsecond=0)
    start72 = end72 - timedelta(hours=72)
    hours = [start72 + timedelta(hours=offset) for offset in range(72)]
    fired = {row.timestamp.replace(minute=0, second=0, microsecond=0) for row in polls}
    hour_values = [hour in fired for hour in hours]
    index_head = None if not states else states[-1].filename
    floor_metrics: list[dict[str, Any]] = []
    rate = states7 / 7
    # `projected_days` and `projected_date` are a straight-line extrapolation of
    # a single seven-day count, and they are the two fields here that must never
    # be cited as a measurement. NC-R002 is retired in the register for being
    # exactly this: a projected floor date that passed with the gate unmet. The
    # arithmetic is auditable, the estimate is not stable -- a seven-day count of
    # k carries roughly Poisson dispersion, so a quiet week moves the date by
    # more than the whole projection is worth, and a date is rendered to the day
    # either way. `states_added_7d` is published beside them so a reader can see
    # how much evidence the number rests on. See ADR-025's amendment, which says
    # in as many words that these two are not registrable claims.
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
        "duplication_ratio": 0.0 if not documents else 1 - states_total / documents,
        "states_added_24h": states24,
        "states_added_7d": states7,
        "states_per_day_7d": rate,
        "new_states_per_day_30d": daily_states,
        "hours_since_last_new_state": since,
        "staleness_band": staleness_band(since),
        # Distinct poll instants, not ledger rows. FR-4's parenthetical says
        # "ledger rows in the trailing 24 h", which assumed one row per poll;
        # `file_snapshots.sh` writes one row per *staged document*, so a
        # dispatched historical sweep files a whole gap under a single
        # `POLL_TIME`. Measured on the live ledger at `cb7a8c2`: 129 rows from
        # 53 polls, with one sweep alone writing 52 of them. Left as rows, a
        # reader of UC-5 comparing this against #45's 22 to 23 runs/day would
        # read one sweep as a poller firing twice an hour. The name and UC-5
        # govern; the count of rows is recoverable from the ledger itself.
        "polls_fired_24h": len({row.timestamp for row in recent_polls}),
        "polls_yielding_new_state_24h": len(acquired_by_poll),
        "ledger_hour_coverage_72h": sum(hour_values) / 72,
        "poll_hours_72h": hour_values,
        "floors": floor_metrics,
    }


def render_svg(metrics: dict[str, Any]) -> str:
    """Render a self-contained, GitHub-safe SVG carrying no clock reading."""
    states = int(metrics["states_total"])
    documents = int(metrics["documents_total"])
    duplicate = float(metrics["duplication_ratio"]) * 100
    max_floor = max((int(floor["value"]) for floor in metrics["floors"]), default=max(states, 1))
    width = 900
    bar_x, bar_width = 55, 790
    progress = min(states / max_floor, 1) * bar_width
    stale_text = html.escape(str(metrics["staleness_band"]))
    coverage = float(metrics["ledger_hour_coverage_72h"]) * 100
    rate_text = float(metrics["states_per_day_7d"])
    labels = [
        '<text x="55" y="43" class="title">Calibration pipeline health</text>',
        f'<text x="55" y="76" class="value">{states} states</text>',
        f'<text x="300" y="76" class="metric">{documents} documents</text>',
        f'<text x="525" y="76" class="metric">{duplicate:.1f}% duplicate</text>',
        f'<text x="55" y="116" class="label">Time since last new state: {stale_text}</text>',
        '<text x="55" y="154" class="label">Distinct states against candidate floors</text>',
        f'<rect x="{bar_x}" y="165" width="{bar_width}" height="24" rx="4" fill="#d7e0ea"/>',
        f'<rect x="{bar_x}" y="165" width="{progress:.2f}" height="24" rx="4" fill="#166534"/>',
    ]
    # Draw ticks left to right whatever order the workflow supplied them in.
    # metrics.json keeps the operator's order; only the drawing is sorted, so
    # the baseline stagger below alternates between *neighbouring* ticks.
    ordered = sorted(
        metrics["floors"], key=lambda floor: (int(floor["value"]), str(floor["label"]))
    )
    for index, floor in enumerate(ordered):
        x = bar_x + min(int(floor["value"]) / max_floor, 1) * bar_width
        drawn = f"{floor['label']}: {floor['value']}"
        labels.append(f'<path d="M{x:.2f} 159v36" stroke="#9a3412" stroke-width="2"/>')
        # Three rows, not two: with two, the first and third tick share a
        # baseline and collide again as soon as a third floor is configured.
        baseline = (207, 222, 237)[index % 3]
        # Measure the glyphs that get drawn, not the escaped source, so the
        # anchor and the conformance check agree on the same string.
        anchor = _anchor_for(x, drawn, FONT_PX["tiny"], width)
        label = html.escape(drawn)
        labels.append(
            f'<text x="{x:.2f}" y="{baseline}" class="tiny" text-anchor="{anchor}">{label}</text>'
        )
    labels.append('<text x="55" y="252" class="label">Poll health — last 72 hours</text>')
    for index, fired in enumerate(metrics["poll_hours_72h"]):
        x = 55 + index * 11
        colour = "#166534" if fired else "#cbd5e1"
        labels.append(f'<rect x="{x}" y="263" width="8" height="20" rx="1" fill="{colour}"/>')
    labels.append(f'<text x="55" y="310" class="label">72-hour coverage: {coverage:.1f}%</text>')
    labels.append('<text x="55" y="350" class="label">New states per day — trailing 30 days</text>')
    daily_states = [int(value) for value in metrics["new_states_per_day_30d"]]
    peak = max(daily_states, default=0)
    for index, value in enumerate(daily_states):
        height = 0 if peak == 0 else value / peak * 70
        x = 55 + index * 25
        labels.append(
            f'<rect x="{x}" y="{445 - height:.2f}" width="18" '
            f'height="{height:.2f}" fill="#2563eb"/>'
        )
    labels.append(f'<text x="55" y="370" class="metric">{rate_text:.2f} states/day</text>')
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
    parser.add_argument("--root", type=Path, default=Path("."), help="Calibration-data checkout.")
    parser.add_argument(
        "--floor",
        action="append",
        required=True,
        metavar="LABEL=VALUE",
        help="Candidate floor, repeatable. Required: FR-7 makes floors configuration, "
        "so the workflow supplies them and no floor value is a literal in this module.",
    )
    parser.add_argument(
        "--now", type=parse_time, default=None, help="UTC render instant (for tests)."
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    now = args.now or datetime.now(UTC)
    root: Path = args.root
    states = read_index(root / "health/state-index.tsv")
    if not states:
        # Refuse rather than publish a zero. The poll workflow creates this file with
        # a header on its first run, so "absent" and "header only" are both just
        # "the backfill has not run yet", and both must decline.
        print(
            "::warning::health/state-index.tsv is absent or holds no rows, so no "
            "dashboard was written. Dispatch Calibration Pipeline Health with "
            "backfill=true, adding rebuild=true if the poller has already appended "
            "rows, then this job will publish."
        )
        return NOTHING_TO_PUBLISH
    metrics = build_metrics(
        states,
        read_ledger(root / "ledger"),
        _floor_values(args.floor),
        now,
    )
    health = root / "health"
    health.mkdir(parents=True, exist_ok=True)
    # newline="\n" explicitly: the default translates to os.linesep, so a render
    # from Windows wrote CRLF and the workflow's ubuntu runner wrote LF for the
    # same inputs. NFR-3 says identical inputs produce byte-identical artifacts,
    # and `calibration-data` carries no .gitattributes to normalise them away, so
    # alternating writers would rewrite all 8 KB of the SVG on a 1.17 GB branch
    # and fire FR-6's commit-on-change guard every time. The implementation doc
    # documents a local render, so this is a path someone is invited to take.
    (health / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (health / "progress.svg").write_text(render_svg(metrics), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
