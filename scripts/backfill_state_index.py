"""Populate ``health/state-index.tsv`` from the archived calibration snapshots.

This is the one-time bootstrap for FR-3 and the only health operation permitted
to walk ``snapshots/``. It runs from an explicit ``workflow_dispatch``, never on
a schedule.

Two modes, because the poller does not wait for the operator:

``append`` (default)
    Digests only snapshots the index does not already name. It refuses to run
    when the index holds rows while snapshots remain unindexed, because
    appending history behind live poll rows marks long-known states as new and
    permanently skews every rate and projection derived from them.

``rebuild`` (``--rebuild``)
    Rewrites the whole index in ``last_update_date`` order. This is the escape
    hatch for the situation the refusal above describes: the poll workflow
    appends hourly, so once it has filed one new document the append path is
    closed for good, and chronology can only be restored by regenerating. It is
    deliberately opt-in -- the poll path stays append-only, as ADR-025's
    amendment records.

Both modes are idempotent: re-running either leaves an already-correct index
byte-identical.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.canonical_snapshot_digest import canonical_digest

STAMP = re.compile(r"^(\d{8}T\d{6}(?:\d{6})?Z)\.json$")
HEADER = ("snapshot_filename", "last_update_date", "qubit_digest", "is_new_state")


def timestamp_from_name(path: Path) -> str:
    """Return an ISO-8601 UTC stamp derived from an archive filename."""
    matched = STAMP.match(path.name)
    if not matched:
        raise ValueError(f"snapshot filename is not a UTC timestamp: {path}")
    stamp = matched.group(1)
    fraction = stamp[15:-1]
    decimal = f".{fraction}" if fraction else ""
    date = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    time = f"{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
    return f"{date}T{time}{decimal}Z"


def archived_snapshots(root: Path) -> list[Path]:
    """Every archived snapshot under ``root``, in chronological order.

    Sorted by payload timestamp, then filename, then backend directory. The
    last key matters because two backends can publish the same
    ``last_update_date``, which gives their files identical names; without it
    the order would depend on the filesystem and ``is_new_state`` would not be
    reproducible.
    """
    return sorted(
        (root / "snapshots").glob("*/*/*.json"),
        key=lambda path: (timestamp_from_name(path), path.name, path.parent.name),
    )


def index_rows(paths: Sequence[Path], seen: Iterable[str] = ()) -> list[tuple[str, str, str, int]]:
    """Digest ``paths`` in order, marking the first sighting of each digest.

    ``seen`` carries digests already recorded by earlier rows, so an append
    continues the chronology rather than restarting it. ``is_new_state`` is 1
    only for the first document that carried a given qubit-block digest.
    """
    known = set(seen)
    rows: list[tuple[str, str, str, int]] = []
    for path in paths:
        digest = canonical_digest(path, scope="qubits")
        rows.append((path.name, timestamp_from_name(path), digest, int(digest not in known)))
        known.add(digest)
    return rows


def _write(index: Path, rows: Sequence[tuple[str, str, str, int]], mode: str) -> None:
    """Write ``rows`` to ``index``, emitting the header when starting a new file."""
    with index.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        if mode == "w":
            writer.writerow(HEADER)
        writer.writerows(rows)


def backfill(root: Path, *, rebuild: bool = False) -> int:
    """Populate the state index under ``root`` and return the rows written.

    With ``rebuild`` the index is regenerated from the archive alone, so a
    malformed or chronologically skewed index is repaired rather than rejected.
    Without it, only unindexed snapshots are appended, and a partially indexed
    archive raises rather than corrupting ``is_new_state``.
    """
    index = root / "health/state-index.tsv"
    index.parent.mkdir(parents=True, exist_ok=True)
    snapshots = archived_snapshots(root)

    if rebuild:
        rows = index_rows(snapshots)
        _write(index, rows, "w")
        return len(rows)

    existing: set[str] = set()
    seen: set[str] = set()
    if index.exists():
        with index.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != HEADER:
                raise ValueError(f"{index} has an unexpected header")
            for row in reader:
                existing.add(row["snapshot_filename"])
                seen.add(row["qubit_digest"])
    missing = [path for path in snapshots if path.name not in existing]
    if existing and missing:
        raise ValueError(
            "state index is incomplete; refusing to append historical rows behind "
            "poll-side rows, which would mark long-known states as new. Re-run with "
            "--rebuild to regenerate the index in last_update_date order."
        )
    _write(index, index_rows(missing, seen), "a" if index.exists() else "w")
    return len(missing)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the backfill against a calibration-data checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="Calibration-data checkout.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rewrite the whole index in last_update_date order. Required once the "
        "poll workflow has appended rows; otherwise the append path refuses to run.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    written = backfill(args.root, rebuild=args.rebuild)
    print(f"{'rewrote' if args.rebuild else 'appended'} {written} state-index rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
