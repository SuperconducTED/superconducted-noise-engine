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
from datetime import datetime
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


def _chronological_key(path: Path) -> tuple[datetime, str, str]:
    """Sort key for archive order: parsed instant, then filename, then backend.

    Parsed rather than compared as an ISO string. ``2026-09-01T00:00:00.123456Z``
    sorts *before* ``2026-09-01T00:00:00Z`` byte-wise, because ``.`` (0x2E)
    precedes ``Z`` (0x5A), while being the later instant. Two documents in the
    same second would then swap places and ``is_new_state`` would name the wrong
    one as the first sighting. Every filename in the archive today carries the
    six-digit fraction, so this is latent, but ``STAMP`` admits both shapes and
    this function's contract is reproducible chronological order.

    The backend key matters because two backends can publish one
    ``last_update_date``, which gives their files identical names; without it
    the order would fall through to the filesystem.
    """
    stamp = timestamp_from_name(path)
    return (datetime.fromisoformat(stamp.replace("Z", "+00:00")), path.name, path.parent.name)


def archived_snapshots(root: Path) -> list[Path]:
    """Every archived snapshot under ``root``, in chronological order.

    A file whose name is not a UTC timestamp is skipped with a warning rather
    than aborting the sweep, matching what the poll path does with a document it
    cannot digest. A one-shot rebuild over ~900 files should not die on one
    stray name after minutes of work, and the operator needs to know which file
    was left out, not just that something raised.
    """
    keep: list[Path] = []
    for path in (root / "snapshots").glob("*/*/*.json"):
        if STAMP.match(path.name):
            keep.append(path)
        else:
            print(f"::warning::{path} is not a UTC-timestamp snapshot name; not indexed")
    return sorted(keep, key=_chronological_key)


def index_rows(paths: Sequence[Path], seen: Iterable[str] = ()) -> list[tuple[str, str, str, int]]:
    """Digest ``paths`` in order, marking the first sighting of each digest.

    ``seen`` carries digests already recorded by earlier rows, so an append
    continues the chronology rather than restarting it. ``is_new_state`` is 1
    only for the first document that carried a given qubit-block digest.

    A document whose qubit block cannot be digested is warned about and left
    out, exactly as ``file_snapshots.sh`` leaves it "preserved but not
    indexed". The alternative, raising, throws away every row already computed
    and makes one malformed file in nine hundred a dead end for the whole
    dispatch.
    """
    known = set(seen)
    rows: list[tuple[str, str, str, int]] = []
    for path in paths:
        try:
            digest = canonical_digest(path, scope="qubits")
        except (OSError, ValueError) as exc:
            print(f"::warning::{path}: {exc}; preserved but not indexed")
            continue
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

    Idempotent in both modes (FR-3), including when the archive holds a document
    that cannot be digested: such a file is never indexed, so it must not be
    allowed to make the archive look permanently "partially indexed".
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
    # Digest before deciding, so the refusal below is about rows that would
    # actually be appended. A document the archive holds but nothing can digest
    # stays "missing" for the rest of the branch's life; testing `missing` here
    # would make one such file raise on every later run and send the operator to
    # --rebuild, which cannot fix it either. This costs one pass over the
    # unindexed set, which is the same work the append path does anyway.
    rows = index_rows(missing, seen)
    if existing and rows:
        raise ValueError(
            "state index is incomplete; refusing to append historical rows behind "
            "poll-side rows, which would mark long-known states as new. Re-run with "
            "--rebuild to regenerate the index in last_update_date order."
        )
    _write(index, rows, "a" if index.exists() else "w")
    # The rows written, not the files considered: a document that could not be
    # digested was warned about and skipped, and reporting it as written would
    # make the "second run appends zero" idempotency check read as a failure.
    return len(rows)


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
