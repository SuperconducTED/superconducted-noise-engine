"""Order-insensitive digest of a calibration snapshot.

Why this exists instead of ``cmp``
----------------------------------
The archive on ``calibration-data`` predates the ``serialize_target`` sort
(#46), so every file written before that fix holds ``target.operations`` in
whatever order Qiskit's iteration happened to produce — 1600 entries, unsorted.
Every file written *after* it is sorted by ``(name, qargs)``.

A byte comparison between a freshly-serialised payload and its archived
counterpart therefore differs even when the calibration data is identical. In
the poll workflow that would report a *collision* on the first re-observed
stamp after the fix merges, and keep doing it on every duplicate poll — putting
routine churn on exactly the channel ADR-024 reserves for real divergence, and
writing a ``collisions/`` file plus a ``::warning::`` each time.

Sorting ``operations`` on both sides before hashing makes the comparison mean
what the workflow needs it to mean: *same calibration document*, regardless of
which serialisation order was in force when each side was written. Everything
else is already canonical — ``storage.py`` dumps with ``sort_keys=True``, and
the nested lists inside ``properties`` arrive from IBM in a fixed order.

Contract: reads only, prints only. ``--compare A B`` exits **0** when the two
snapshots are the same document, **1** when they differ, and **2** when either
side could not be read or parsed — so it can be used directly as a shell
condition, and "cannot tell" stays distinguishable from "they differ". That
distinction is load-bearing: the poll workflow preserves the payload for both,
but records `collision` for 1 and `collision-unreadable` for 2, so the ledger
never claims a divergence it did not observe.

With one or more paths and no ``--compare`` it prints ``<digest>  <path>`` per
file and exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def _operation_key(entry: Any) -> tuple[str, tuple[Any, ...]]:
    """Sort key matching ``serialize_target``'s, tolerant of malformed entries.

    A legacy or hand-edited file may carry an entry without ``name`` or
    ``qargs``; the digest must still be computable, because refusing to compare
    is strictly worse than comparing a slightly odd document.
    """
    if not isinstance(entry, dict):
        return ("", ())
    qargs = entry.get("qargs")
    return (
        str(entry.get("name", "")),
        tuple(qargs) if isinstance(qargs, list) else (),
    )


def canonical_digest(path: str | Path) -> str:
    """SHA-256 of the snapshot with ``target.operations`` put in a fixed order."""
    with Path(path).open(encoding="utf-8") as fh:
        doc = json.load(fh)

    target = doc.get("target")
    if isinstance(target, dict) and isinstance(target.get("operations"), list):
        target["operations"] = sorted(target["operations"], key=_operation_key)

    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main(argv: Iterable[str] | None = None) -> int:
    """Print digests, or compare two snapshots as a shell condition.

    Returns 0 when the compared snapshots match (or when simply printing
    digests), 1 when they differ, and 2 when a file could not be read or parsed
    — so a caller can tell "these differ" from "I could not tell".
    """
    parser = argparse.ArgumentParser(
        prog="canonical-snapshot-digest",
        description="Digest a calibration snapshot ignoring target.operations order.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Treat the two paths as a pair: exit 0 if same document, 1 if different, "
        "2 if either could not be read.",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.compare and len(args.paths) != 2:
        parser.error("--compare takes exactly two paths")

    try:
        digests = [canonical_digest(p) for p in args.paths]
    except (OSError, ValueError) as exc:
        # ValueError covers both json.JSONDecodeError and UnicodeDecodeError. The
        # latter matters: without it a non-UTF-8 payload escapes as a traceback,
        # the process exits 1, and the workflow reads that as "genuinely
        # different" -- recording `collision` and warning that the payload
        # differs from the archived copy when it was never compared at all.
        print(f"canonical-snapshot-digest: {exc}", file=sys.stderr)
        return 2

    if args.compare:
        return 0 if digests[0] == digests[1] else 1

    for digest, path in zip(digests, args.paths, strict=True):
        print(f"{digest}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
