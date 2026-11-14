"""Re-derive the Rule 7 anchors for the numerical-claims rows Issue #92 left unpinned.

Run from the repository root, in PowerShell or any shell:

    python docs/evidence/register-anchors-2026-11/anchors.py

It reads commits, trees and file names of the ``calibration-data`` branch through git and
never a file's contents, so it downloads nothing in a ``blob:none`` partial clone (it sets
``GIT_NO_LAZY_FETCH=1`` for every git call). It also reads the committed evidence TSVs on
the current checkout. Output is deterministic for a fixed ``calibration-data`` tip; the only
lines that move with the tip are the ones labelled ``tip``.

Each section names the row, the immutable ref that reproduces the row's value, and the
ref range over which the value holds. Written for Issue #92 on 2026-11-14.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

UTC = dt.UTC
ENV = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
DAY = 86400.0


def git(*args: str) -> str:
    """Run git with lazy fetch disabled and return stdout; raise on failure."""
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", env=ENV, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def last_before(branch: str, instant: str) -> str:
    """Full sha of the last commit on ``branch`` committed at or before ``instant``."""
    return git("rev-list", "-1", f"--before={instant}", branch).strip()


def short(sha: str) -> str:
    return sha[:8]


def commit_time(sha: str) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(git("log", "-1", "--format=%ct", sha).strip()), UTC)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def names(ref: str, path: str = "") -> list[str]:
    args = ["ls-tree", "-r", "--name-only", ref]
    if path:
        args.append(path)
    return git(*args).splitlines()


def snapshot_files(ref: str) -> list[str]:
    """Paths matching ``snapshots/*.json`` at ``ref`` (NC-011's filter)."""
    return [n for n in names(ref) if n.startswith("snapshots/") and n.endswith(".json")]


def stamps_in(ref: str, directory: str, lo: str, hi: str) -> list[str]:
    """File stamps (name without ``.json``) under ``directory`` with ``lo <= stamp <= hi``."""
    out = []
    for n in names(ref, directory):
        stamp = n.rsplit("/", 1)[1].removesuffix(".json")
        if lo <= stamp <= hi:
            out.append(stamp)
    return sorted(out)


def stamp_time(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)


def tsv_status_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def heading(text: str) -> None:
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def nc011(branch: str) -> str:
    heading("NC-011  Snapshot count, measured: 127")
    for instant in (
        "2026-05-25T00:00:00Z",
        "2026-05-25T12:00:00Z",
        "2026-05-25T23:59:59Z",
        "2026-05-26T16:28:34Z",
        "2026-05-26T19:03:25Z",
        "2026-05-26T19:03:26Z",
    ):
        sha = last_before(branch, instant)
        print(
            f"  last commit at or before {instant}: {short(sha)}  "
            f"snapshots/*.json = {len(snapshot_files(sha))}"
        )
    window = git(
        "rev-list",
        "--reverse",
        "--since=2026-05-25T00:00:00Z",
        "--until=2026-05-27T00:00:00Z",
        branch,
    ).split()
    first_127 = next(s for s in window if len(snapshot_files(s)) == 127)
    first_128 = next(s for s in window if len(snapshot_files(s)) == 128)
    print(f"  first commit holding 127: {short(first_127)} at {iso(commit_time(first_127))}")
    print(f"  first commit holding 128: {short(first_128)} at {iso(commit_time(first_128))}")
    return first_127


def nc009(branch: str, anchor: str) -> None:
    heading("NC-009  Calibration polling cadence, sustained measured: ~11.1 snapshots/day")
    files = sorted(snapshot_files(anchor))
    first_stamp = stamp_time(files[0].rsplit("/", 1)[1])
    t_anchor = commit_time(anchor)
    elapsed = (t_anchor - first_stamp).total_seconds() / DAY
    print(
        f"  first snapshot stamp {iso(first_stamp)}; "
        f"NC-011 anchor {short(anchor)} at {iso(t_anchor)}"
    )
    print(
        f"  same-instant rate at the anchor: {len(files)} / {elapsed:.3f} d "
        f"= {len(files) / elapsed:.2f} per day"
    )

    # Same-instant search: count and elapsed time taken at one instant t, every 5 minutes over
    # 2026-05-24..27, three elapsed-time origins, two counts. A hit is a rate that rounds to 11.1.
    adds: list[tuple[float, str]] = []
    log = git(
        "log",
        "--reverse",
        "--diff-filter=A",
        "--format=@%ct",
        "--name-only",
        "--before=2026-05-28T00:00:00Z",
        branch,
        "--",
        "snapshots/",
    )
    when = 0.0
    for line in log.splitlines():
        if line.startswith("@"):
            when = float(line[1:])
        elif line.endswith(".json"):
            adds.append((when, line))
    commits = [
        float(t)
        for t in git("log", "--format=%ct", "--before=2026-05-28T00:00:00Z", branch).split()
    ]
    root = min(commits)
    first_add = adds[0][0]

    def search(lo: float, hi: float) -> list[str]:
        hits = []
        start = dt.datetime(2026, 5, 24, tzinfo=UTC).timestamp()
        for k in range(4 * 24 * 12):
            t = start + 300 * k
            n_files = sum(1 for a, _ in adds if a <= t)
            n_commits = sum(1 for c in commits if c <= t)
            for count_name, count in (("files", n_files), ("commits", n_commits)):
                for origin_name, origin in (
                    ("first stamp", first_stamp.timestamp()),
                    ("first file commit", first_add),
                    ("branch root", root),
                ):
                    rate = count / ((t - origin) / DAY)
                    if lo <= rate < hi:
                        hits.append(
                            f"{iso(dt.datetime.fromtimestamp(t, UTC))} {count_name}={count} "
                            f"from {origin_name}: {rate:.3f}"
                        )
        return hits

    hits = search(11.05, 11.15)
    print(f"  same-instant search for a rate in [11.05, 11.15): {len(hits)} hits")
    control = search(9.60, 9.70)
    print(f"  control, the same search for [9.60, 9.70): {len(control)} hits (must be > 0)")
    if not control:
        raise SystemExit("control search did not fire; the search itself is broken")
    mixed_end = dt.datetime(2026, 5, 25, tzinfo=UTC)
    mixed = (mixed_end - first_stamp).total_seconds() / DAY
    print(
        f"  mixed instants: {len(files)} (counted at {short(anchor)}, 2026-05-26) / {mixed:.3f} d "
        f"(first stamp to {iso(mixed_end)}) = {len(files) / mixed:.3f} per day, "
        "which rounds to 11.1"
    )


def nc029_nc030(branch: str, root: Path) -> None:
    heading("NC-029 / NC-030  2026-08-27..30 outage enumeration: 11 held of >= 57")
    tsv = root / "docs/evidence/pr47-outage-enumeration/enumeration-2026-08-30.tsv"
    counts = tsv_status_counts(tsv)
    print(f"  {tsv.relative_to(root).as_posix()} statuses: {counts}; rows = {sum(counts.values())}")
    lo, hi = "20260827T081847000000Z", "20260830T081847000000Z"
    for label, ref in (
        ("at the run (2026-08-30T08:18:11Z)", last_before(branch, "2026-08-30T08:18:11Z")),
        ("tip", branch),
    ):
        sha = git("rev-parse", ref).strip()
        held = stamps_in(sha, "snapshots/2026-08/ibm_fez/", lo, hi)
        print(
            f"  {label}: calibration-data {short(sha)} holds {len(held)} files stamped {lo}..{hi}"
        )
    print(f"  NC-030 mean interval: 72 h / 57 = {72 / 57:.3f} h; 57 / 3 d = {57 / 3:.1f} per day")


def nc031(branch: str, root: Path) -> None:
    heading("NC-031  1 h sweep recall, 2026-08-12T06:00..08-14T20:00: 29 of 33")
    tsv = root / "docs/evidence/aug-gap-enumeration/control-2026-08-12_14.tsv"
    counts = tsv_status_counts(tsv)
    print(f"  {tsv.relative_to(root).as_posix()} statuses: {counts}")
    lo, hi = "20260812T060000000000Z", "20260814T200000000000Z"
    at_run = last_before(branch, "2026-09-02T18:51:00Z")
    held_run = stamps_in(at_run, "snapshots/2026-08/ibm_fez/", lo, hi)
    print(
        f"  at the run (2026-09-02T18:51:00Z): calibration-data {short(at_run)} "
        f"holds {len(held_run)}"
    )
    previous_n = len(held_run)
    for sha in git(
        "rev-list", "--reverse", f"{at_run}..{branch}", "--", "snapshots/2026-08/ibm_fez/"
    ).split():
        n = len(stamps_in(sha, "snapshots/2026-08/ibm_fez/", lo, hi))
        if n != previous_n:
            parent = git("rev-parse", f"{sha}^").strip()
            print(
                f"  the count first moves at {short(sha)} ({iso(commit_time(sha))}): "
                f"{previous_n} -> {n}; {previous_n} holds from {short(at_run)} "
                f"through its parent {short(parent)} ({iso(commit_time(parent))})"
            )
            break
    served = set()
    with tsv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["served_by_1h_sweep"] == "yes":
                served.add(row["last_update_date"])
    tip = git("rev-parse", branch).strip()
    held_tip = set(stamps_in(tip, "snapshots/2026-08/ibm_fez/", lo, hi))
    both = len(served & held_tip)
    print(
        f"  tip {short(tip)}: holds {len(held_tip)}; "
        f"the sweep's {len(served)} in-window stamps are held: {both}; "
        f"the row's method at the tip gives {both} / {len(held_tip)} "
        f"= {100 * both / len(held_tip):.1f}%"
    )


def blob_ids(refs: Iterable[str], paths: Iterable[str]) -> None:
    for path in paths:
        ids = {short(r): git("rev-parse", f"{r}:{path}").strip()[:10] for r in refs}
        same = "identical" if len(set(ids.values())) == 1 else "DIFFERENT"
        print(
            f"  {path.rsplit('/', 1)[1]}: "
            + ", ".join(f"{k}={v}" for k, v in ids.items())
            + f" ({same})"
        )


def nc033_nc034(branch: str) -> None:
    heading("NC-033 / NC-034  2026-08-07..17 gaps: rounds and live-path stability")
    # The evidence TSVs were committed to main at b16b8935, 2026-09-02T19:19:12Z.
    at_measure = last_before(branch, "2026-09-02T19:19:12Z")
    print(
        "  calibration-data at the evidence commit b16b8935 (2026-09-02T19:19:12Z): "
        f"{short(at_measure)}"
    )
    tip = git("rev-parse", branch).strip()
    windows = (
        ("W1", "2026-08-07T03:21:59Z", "2026-08-10T14:02:35Z", "20260807T032159000000Z"),
        ("W2", "2026-08-10T14:02:35Z", "2026-08-12T06:00:00Z", "20260810T140235000000Z"),
        ("W3", "2026-08-14T20:18:59Z", "2026-08-17T06:57:00Z", "20260814T201859000000Z"),
    )
    total = 0
    for name, since, until, edge in windows:
        path = f"snapshots/2026-08/ibm_fez/{edge}.json"
        row = []
        for ref in (at_measure, tip):
            commits = int(
                git("rev-list", "--count", f"--since={since}", f"--until={until}", ref).strip()
            )
            revisions = int(
                git(
                    "rev-list", "--count", f"--since={since}", f"--until={until}", ref, "--", path
                ).strip()
            )
            row.append(f"{short(ref)}: commits={commits} edge revisions={revisions}")
        total += revisions
        print(f"  {name} {since}..{until} edge {edge}: " + "; ".join(row))
    print(
        f"  edge revisions over the three windows: {total} (NC-034 says 154); "
        "the hashes need file contents and are not re-run here"
    )
    print(
        "  NC-033's three gap-closing snapshots and NC-034's edge files, "
        "blob ids at the measurement ref and the tip:"
    )
    blob_ids(
        (at_measure, tip),
        [
            f"snapshots/2026-08/ibm_fez/{s}.json"
            for s in (
                "20260810T140235000000Z",
                "20260812T055918000000Z",
                "20260817T065740000000Z",
                "20260807T032159000000Z",
                "20260814T201859000000Z",
            )
        ],
    )


def nc035(branch: str) -> None:
    heading("NC-035  sx gate length from two May snapshots at archive ref 1accf05")
    anchor = git("rev-parse", "1accf05").strip()
    blob_ids(
        (anchor, git("rev-parse", branch).strip()),
        [
            "snapshots/2026-05/ibm_fez/20260513T121322000000Z.json",
            "snapshots/2026-05/ibm_fez/20260513T143529000000Z.json",
        ],
    )


def nc026() -> None:
    heading("NC-026  Retention depth >= 60 days (Actions run 33260786341, 2026-08-29)")
    added = git(
        "log",
        "--diff-filter=A",
        "--format=%h %cI",
        "origin/main",
        "--",
        "docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md",
    ).split("\n")[-2]
    print(
        "  the ten-depth table lives in "
        "docs/implementations/2026-08-29-calibration-yield-and-poller-defects.md, "
        f"added at {added}"
    )
    for sha in ("a529bd564d4167d2568aec577cdd9b7a4189ab4c",):
        reachable = (
            subprocess.run(
                ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                capture_output=True,
                env=ENV,
                check=False,
            ).returncode
            == 0
        )
        print(
            f"  the run's head commit {short(sha)} (branch probe/historical-check, since deleted) "
            f"is present in this clone: {reachable}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--remote", default="origin", help="remote whose calibration-data branch to read"
    )
    args = parser.parse_args()
    root = Path(git("rev-parse", "--show-toplevel").strip())
    branch = f"{args.remote}/calibration-data"
    tip = git("rev-parse", branch).strip()
    print(f"calibration-data tip: {short(tip)} at {iso(commit_time(tip))}")
    anchor = nc011(branch)
    nc009(branch, anchor)
    nc026()
    nc029_nc030(branch, root)
    nc031(branch, root)
    nc033_nc034(branch)
    nc035(branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
