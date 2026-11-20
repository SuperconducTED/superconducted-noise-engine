"""When do ``ibm_fez`` files reach ``calibration-data``, and what would a morning's scoring see?

    python archive_timing.py <repo> <calibration-data commit> --pairs-out pairs.tsv

Standard library only. It reads the data branch through ``git`` at one pinned commit and prints
three things, each behind a figure in the two #125 comments of 2026-11-20:

A. Gaps in file time (the document time in each file's name), and the 2026-11 gap in detail.
B. Arrival lag: the commit time of the commit that added a file, minus the file's own time.
C. A replay of recent days: for a job executing at ``t_execute``, the latest file at or before
   ``t_execute`` among the files the archive held on the scoring morning, against the same
   question asked of the whole archive at the pinned commit.

Contract. Inputs: a clone holding the pinned commit and its history back to 2026-09-01 at least.
Output: text on stdout and, with ``--pairs-out``, one TSV row per replayed day on which the two
answers of C name different files. No side effects on the repository. It relies on file names of
the form ``snapshots/YYYY-MM/ibm_fez/YYYYMMDDTHHMMSS...Z.json`` carrying the document's
``last_update_date`` (``compare_readings.py`` checks that on the files it opens).

It does not read any file's contents, so it cannot say whether two different files carry
different calibration values. ``compare_readings.py`` does that for the rows written here.
"""

from __future__ import annotations

import argparse
import itertools
import re
import statistics
import subprocess
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

NAME = re.compile(r"snapshots/\d{4}-\d{2}/ibm_fez/(\d{8}T\d{6})\d*Z\.json$")
NO_NEW = re.compile(r"^poll: \S+ ibm_fez \(no new document\)")
CALIBRATION = re.compile(r"^calibration: \S+ ibm_fez")

# B and C use files dated from here on, so that a shallow clone's root commit, which "adds" every
# older file at once, cannot pass for an arrival.
LAG_START = datetime(2026, 9, 1, tzinfo=UTC)
LATE_HOURS = 6.0
BULK_FILES = 3

# C: the run's clock. Submission at 03:45 UTC (pre-registration section 3.6); the morning routine
# scores earlier days after its own build, taken here as 04:00 UTC.
SUBMISSION = time(3, 45)
SCORING = time(4, 0)
QUEUE_HOURS = (0.02, 2.0, 6.0, 12.0)
REPLAY_DAYS = 60
LOOKAHEAD_MORNINGS = 7
# The replay stops three days before the newest arrival, so the last days' late files are in.
SETTLE_DAYS = 3


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True, encoding="utf-8"
    )
    return done.stdout


def file_time(path: str) -> datetime | None:
    m = NAME.match(path)
    if m is None:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)


def hours(delta: timedelta) -> float:
    return delta.total_seconds() / 3600.0


def read_archive(
    repo: Path, sha: str
) -> tuple[dict[datetime, str], dict[datetime, datetime], Counter[datetime]]:
    """File time to path at ``sha``; file time to first add time; files added per commit time."""
    paths: dict[datetime, str] = {}
    for line in git(repo, "ls-tree", "-r", "--name-only", sha, "--", "snapshots").splitlines():
        t = file_time(line)
        if t is not None:
            paths[t] = line
    added: dict[datetime, datetime] = {}
    per_commit: Counter[datetime] = Counter()
    commit_time: datetime | None = None
    log = git(
        repo, "log", "--diff-filter=A", "--name-only", "--format=@%cI", sha, "--", "snapshots"
    )
    for line in log.splitlines():
        if line.startswith("@"):
            commit_time = datetime.fromisoformat(line[1:]).astimezone(UTC)
            continue
        t = file_time(line)
        if t is None or commit_time is None or t not in paths:
            continue
        per_commit[commit_time] += 1
        if t not in added or commit_time < added[t]:
            added[t] = commit_time
    return paths, added, per_commit


def part_a(repo: Path, sha: str, times: list[datetime], added: dict[datetime, datetime]) -> None:
    print("A. Gaps in file time")
    span = times[-1] - times[0]
    print(f"files {len(times)}, {times[0]:%Y-%m-%d %H:%M:%S} to {times[-1]:%Y-%m-%d %H:%M:%S} UTC,")
    print(f"span {span.days} days")
    gaps = [(b - a, a, b) for a, b in itertools.pairwise(times)]
    median_gap = statistics.median(hours(g) for g, _, _ in gaps)
    print(f"median gap between consecutive files: {median_gap:.2f} h")
    long_gaps = [g for g in gaps if g[0] >= timedelta(hours=24)]
    recent = [g for g in long_gaps if g[1] >= times[-1] - timedelta(days=60)]
    print(f"gaps of 24 h or more: {len(long_gaps)}; starting in the last 60 days: {len(recent)}")
    for gap, a, b in long_gaps:
        print(f"  {hours(gap):6.1f} h  {a:%Y-%m-%d %H:%M:%S} -> {b:%Y-%m-%d %H:%M:%S}")

    gap, before, after = long_gaps[-1]
    print(
        f"\nthe latest of them: {hours(gap):.1f} h,"
        f" {before:%Y-%m-%d %H:%M:%S} to {after:%Y-%m-%d %H:%M:%S}"
    )
    print(f"  last file before it entered the archive at {added[before]:%Y-%m-%d %H:%M:%S}")
    print(f"  first file after it, by file time, entered at {added[after]:%Y-%m-%d %H:%M:%S}")
    first_time, first_added = min(
        ((t, added[t]) for t in times if t > before), key=lambda pair: pair[1]
    )
    print(
        f"  first file dated after it to enter the archive: {first_time:%Y-%m-%d %H:%M:%S},"
        f" at {first_added:%Y-%m-%d %H:%M:%S}"
    )
    commits = []
    for line in git(repo, "log", "--format=%cI%x09%s", sha).splitlines():
        stamp, _, subject = line.partition("\t")
        commits.append((datetime.fromisoformat(stamp).astimezone(UTC), subject))
    last_calibration = max(
        when for when, subject in commits if CALIBRATION.match(subject) and when < first_added
    )
    for label, start in (
        ("the last file before the gap entered", added[before]),
        ("the last calibration commit before that arrival", last_calibration),
    ):
        polls = [s for when, s in commits if start < when < first_added and s.startswith("poll:")]
        empty = sum(1 for s in polls if NO_NEW.match(s))
        print(
            f"  polls between {label} ({start:%m-%d %H:%M:%S}) and that arrival:"
            f" {len(polls)}, of which 'no new document': {empty}"
        )


def part_b(
    times: list[datetime], added: dict[datetime, datetime], per_commit: Counter[datetime]
) -> list[datetime]:
    print("\nB. Arrival lag (add commit time minus file time)")
    root = min(added.values())
    live = [t for t in times if t >= LAG_START and added[t] > root]
    lags = [hours(added[t] - t) for t in live]
    ordered = sorted(lags)
    print(f"files dated from {LAG_START:%Y-%m-%d}: {len(live)}")
    print(
        f"lag in hours: median {statistics.median(lags):.2f},"
        f" 90th percentile {ordered[int(0.9 * len(ordered))]:.1f}, max {ordered[-1]:.1f}"
    )
    for edge in (1, 3, 6, 12, 24, 48):
        n = sum(1 for x in lags if x <= edge)
        print(f"  within {edge:>2} h: {n} ({n / len(lags):.1%})")
    over_24 = sum(1 for x in lags if x > 24)
    over_48 = sum(1 for x in lags if x > 48)
    print(
        f"  over 24 h: {over_24} ({over_24 / len(lags):.1%});"
        f" over 48 h: {over_48} ({over_48 / len(lags):.1%})"
    )
    for t in live:
        if added[t] < t:
            print(
                f"  archived before its own file time: {t:%Y-%m-%d %H:%M:%S},"
                f" added {added[t]:%H:%M:%S}"
            )

    late = [t for t in live if hours(added[t] - t) > LATE_HOURS]
    in_bulk = sum(1 for t in late if per_commit[added[t]] >= BULK_FILES)
    print(
        f"files later than {LATE_HOURS:.0f} h: {len(late)};"
        f" in a commit adding {BULK_FILES} or more files: {in_bulk}"
    )
    print("  by add hour (UTC):", dict(sorted(Counter(added[t].hour for t in late).items())))
    bulk = [when for when, n in per_commit.items() if n >= BULK_FILES and when > LAG_START]
    by_hour = Counter(when.hour for when in bulk)
    daytime = sum(n for hour, n in by_hour.items() if 8 <= hour < 14)
    print(f"commits adding {BULK_FILES} or more files since {LAG_START:%Y-%m-%d}: {len(bulk)};")
    print(f"  landing 08:00 to 14:00 UTC: {daytime}; by hour: {dict(sorted(by_hour.items()))}")
    return live


def latest_at(
    times: list[datetime], added: dict[datetime, datetime], at: datetime, held_by: datetime | None
) -> datetime | None:
    best = None
    for t in times:
        if t > at:
            break
        if held_by is None or added[t] <= held_by:
            best = t
    return best


def part_c(
    times: list[datetime],
    added: dict[datetime, datetime],
    paths: dict[datetime, str],
    pairs_out: Path | None,
) -> None:
    newest = max(added.values())
    end = (newest - timedelta(days=SETTLE_DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
    first = end - timedelta(days=REPLAY_DAYS - 1)
    print(f"\nC. Replay of {REPLAY_DAYS} days, {first:%Y-%m-%d} to {end:%Y-%m-%d}")
    print(
        f"t_execute = {SUBMISSION:%H:%M} UTC plus the queue delay;"
        f" scored at {SCORING:%H:%M} UTC on the first morning"
    )
    print("after t_execute on which the archive holds a file dated after t_execute")
    rows: list[str] = []
    for queue in QUEUE_HOURS:
        differ = slipped = unscored = 0
        newer: list[float] = []
        slipped_days: list[str] = []
        for i in range(REPLAY_DAYS):
            day = (first + timedelta(days=i)).date()
            t_execute = datetime.combine(day, SUBMISSION, UTC) + timedelta(hours=queue)
            scored_at = None
            for k in range(1, LOOKAHEAD_MORNINGS + 1):
                morning = datetime.combine(day, SCORING, UTC) + timedelta(days=k)
                if morning > t_execute and any(
                    t > t_execute and added[t] <= morning for t in times
                ):
                    scored_at = (k, morning)
                    break
            if scored_at is None:
                unscored += 1
                continue
            k, morning = scored_at
            if k > 1:
                slipped += 1
                slipped_days.append(f"{day} (+{k})")
            held = latest_at(times, added, t_execute, morning)
            tip = latest_at(times, added, t_execute, None)
            if held is None or tip is None or held == tip:
                continue
            differ += 1
            newer.append(hours(tip - held))
            rows.append(
                "\t".join(
                    (
                        f"{queue}",
                        f"{day}",
                        paths[held],
                        paths[tip],
                        f"{held:%Y-%m-%dT%H:%M:%SZ}",
                        f"{tip:%Y-%m-%dT%H:%M:%SZ}",
                        f"{added[tip]:%Y-%m-%dT%H:%M:%SZ}",
                    )
                )
            )
        tail = (
            f"; the newer file is later by median {statistics.median(newer):.1f} h,"
            f" max {max(newer):.1f} h"
            if newer
            else ""
        )
        print(
            f"  queue {queue:>5} h: a different file on {differ} of {REPLAY_DAYS} days;"
            f" scored later than the next morning on {slipped}; not within"
            f" {LOOKAHEAD_MORNINGS} mornings on {unscored}{tail}"
        )
        if slipped_days:
            print(f"      scored late: {', '.join(slipped_days)}")
    if pairs_out is not None:
        header = "queue_h\tday\theld_path\ttip_path\theld_time\ttip_time\ttip_added"
        pairs_out.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8", newline="\n")
        print(f"rows written for compare_readings.py: {len(rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("sha", help="the calibration-data commit to read, in full")
    parser.add_argument("--pairs-out", type=Path, default=None)
    args = parser.parse_args()

    print(f"calibration-data commit: {git(args.repo, 'rev-parse', args.sha).strip()}")
    paths, added, per_commit = read_archive(args.repo, args.sha)
    times = sorted(paths)
    missing = [t for t in times if t not in added]
    if missing:
        raise SystemExit(f"{len(missing)} files have no adding commit in this clone's history")
    print(
        "earliest commit that adds a file in this clone:"
        f" {min(added.values()):%Y-%m-%d %H:%M:%S} UTC\n"
    )
    part_a(args.repo, args.sha, times, added)
    part_b(times, added, per_commit)
    part_c(times, added, paths, args.pairs_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
