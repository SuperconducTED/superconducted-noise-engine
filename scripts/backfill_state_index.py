"""
Add missing calibration snapshots to ``health/state-index.tsv``.
The following single-use utility is idempotent, as existing records
will be retained and any files that have already been indexed by
filename will be skipped.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterable
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


def backfill(root: Path) -> int:
    """Append unindexed snapshots in timestamp order and return their count."""
    index = root / "health/state-index.tsv"
    index.parent.mkdir(parents=True, exist_ok=True)
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
    snapshots = sorted((root / "snapshots").glob("*/*/*.json"), key=lambda path: path.name)
    missing = [path for path in snapshots if path.name not in existing]
    mode = "a" if index.exists() else "w"
    with index.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        if mode == "w":
            writer.writerow(HEADER)
        for path in missing:
            digest = canonical_digest(path, scope="qubits")
            writer.writerow((path.name, timestamp_from_name(path), digest, int(digest not in seen)))
            seen.add(digest)
    return len(missing)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the idempotent backfill against a calibration-data checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(f"appended {backfill(args.root)} state-index rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
