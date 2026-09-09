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
routine churn on exactly the channel ADR-025 reserves for real divergence, and
writing a ``collisions/`` file plus a ``::warning::`` each time.

Sorting ``operations`` on both sides before hashing makes the comparison mean
what the workflow needs it to mean: *same calibration document*, regardless of
which serialisation order was in force when each side was written. Everything
else is already canonical — ``storage.py`` dumps with ``sort_keys=True``, and
the nested lists inside ``properties`` arrive from IBM in a fixed order.

The payload comparison used across fetch paths (``--payload-only``,
``--compare-reread``) normalises one more provenance-dependent field for the
same reason: each parameter's own ``date``. The history endpoint re-stamps the
entries it synthesises, so a backfilled re-read of a document already archived
differs in those stamps while every measurement matches. See ``_payload_body``.

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


def _load(path: str | Path) -> dict[str, Any]:
    """Parse a snapshot. Raises ``OSError`` or ``ValueError`` like ``json.load``."""
    with Path(path).open(encoding="utf-8") as fh:
        doc: dict[str, Any] = json.load(fh)
    return doc


def _strip_parameter_dates(node: Any) -> Any:
    """Return ``node`` with the ``date`` dropped from every parameter record.

    A parameter record is any dict carrying a ``value``. Inside ``properties``
    that is exactly the three places IBM puts them — ``qubits[][]``,
    ``gates[].parameters[]`` and ``general[]`` — each of shape
    ``{date, name, unit, value}``. Keying on ``value`` rather than on those
    three paths keeps the rule from touching anything else: ``last_update_date``
    is a different key on a dict that has no ``value``, and a gate's own
    ``name``/``gate``/``qubits`` survive untouched. It also survives IBM moving
    a parameter block, which a hard-coded path list would not.

    Pure: builds new containers rather than mutating the document, because the
    caller still has to write that document out with its dates intact.
    """
    if isinstance(node, list):
        return [_strip_parameter_dates(item) for item in node]
    if not isinstance(node, dict):
        return node
    is_parameter = "value" in node
    return {
        key: _strip_parameter_dates(value)
        for key, value in node.items()
        if not (is_parameter and key == "date")
    }


def _payload_body(doc: dict[str, Any]) -> str:
    """The canonical byte-string for the calibration payload alone.

    Per-parameter ``date`` is normalised away, for the same reason
    ``canonical_digest`` normalises ``target.operations`` order: it is decided
    by which endpoint answered, not by the measurement. The live properties
    endpoint returns IBM's stored document; the history endpoint reassembles
    one, and re-stamps the entries it synthesises. Backfill run 34058863047
    hit this on ``ibm_fez`` ``20260813T220506000000Z``: same
    ``last_update_date``, same 156/1952/449 shape, ``qubits`` and ``general``
    exactly equal, and 26 gate entries differing in nothing but a ``date``
    about 11 minutes apart. Those 26 were *exactly* the 26 entries carrying
    the ``gate_error = 1`` placeholder that means "not calibrated" — no
    measured entry differed. Hashing that stamp made a re-read of a document
    we already hold look like divergence and put a file in ``collisions/``,
    the channel ADR-025 reserves for the real thing.

    ``date`` is the only field dropped. Comparing values alone was the other
    candidate and is worse: it would call a ``T1`` in ``us`` equal to one in
    ``ns``, and a ``T1``/``T2`` swap equal to neither having moved. ``name``,
    ``unit`` and ``value`` are measurement; only ``date`` is provenance.
    """
    return json.dumps(
        {"properties": _strip_parameter_dates(doc.get("properties"))},
        sort_keys=True,
        separators=(",", ":"),
    )


def _payload_digest(doc: dict[str, Any]) -> str:
    """SHA-256 of the calibration payload alone."""
    return hashlib.sha256(_payload_body(doc).encode("utf-8")).hexdigest()


def qubit_digest(payload: dict[str, Any]) -> str:
    """Return the canonical SHA-256 digest of a snapshot's qubit block.

    This is the stable NC-025 definition of a device state. Invalid or missing
    qubit data is undecidable, never a shared phantom digest.
    """
    properties = payload.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get("qubits"), list):
        raise ValueError("snapshot properties.qubits must be a list")
    qubits = properties["qubits"]
    body = json.dumps(qubits, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def canonical_digest(
    path: str | Path, *, payload_only: bool = False, scope: str = "document"
) -> str:
    """SHA-256 of the snapshot with ``target.operations`` put in a fixed order.

    With ``payload_only``, digest **only** ``properties`` — the calibration
    payload — ignoring ``target`` and ``configuration``. Those two are
    provenance-dependent: a historical fetch
    (``poller.fetch_snapshot(historical_at=...)``) leaves ``configuration`` as
    ``None`` and sources ``target`` differently from a live poll, so the same
    document fetched two ways compares unequal in full while its measurements
    are identical. Comparing in full is right for two live payloads and wrong
    across fetch paths; this mode is what makes the difference visible.

    ``payload_only`` also drops each parameter's ``date`` — see
    ``_payload_body``. The full digest deliberately keeps it: that is the
    live-vs-live comparison, where the safe answer is ``collision`` and a
    difference of any kind belongs in front of a human.
    """
    with Path(path).open(encoding="utf-8") as fh:
        doc = json.load(fh)

    if scope == "qubits":
        return qubit_digest(doc)
    if scope != "document":
        raise ValueError(f"unknown digest scope: {scope}")
    if payload_only:
        # Same byte-string as `_payload_digest`, deliberately: `--payload-only`
        # and `--compare-reread` answer the same question about the same pair,
        # and two copies of this line is how the per-parameter `date` came to
        # be normalised in neither.
        payload = _payload_body(doc)
    else:
        target = doc.get("target")
        if isinstance(target, dict) and isinstance(target.get("operations"), list):
            target["operations"] = sorted(target["operations"], key=_operation_key)
        payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_lossy_reread(new_doc: dict[str, Any], archived_doc: dict[str, Any]) -> bool:
    """Does ``new_doc`` carry the structural signature of a historical re-read?

    ``fetch_snapshot(historical_at=...)`` never fetches ``configuration``, so a
    historical payload always has it as ``None``; a live poll archived one with
    it populated. That asymmetry — **incoming missing it, archived holding
    it** — is the only difference a backfill re-read is allowed to explain.

    Deliberately directional. Two live payloads both carry a configuration, so
    this is false for them and their difference stays a collision, which is the
    case PR #55's review showed the first attempt had broken: comparing full
    first and payload second reduces to comparing the payload alone, because
    full equality implies payload equality.
    """
    return new_doc.get("configuration") is None and archived_doc.get("configuration") is not None


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
    parser.add_argument(
        "--payload-only",
        action="store_true",
        help="Digest only the calibration payload (properties), ignoring target and "
        "configuration. Use to compare a historical fetch against a live one.",
    )
    parser.add_argument(
        "--scope",
        choices=("document", "qubits"),
        default="document",
        help="Digest the canonical document (default) or properties.qubits only.",
    )
    parser.add_argument(
        "--compare-reread",
        action="store_true",
        help="Two paths NEW ARCHIVED: exit 0 only if NEW is a lossy historical re-read "
        "of ARCHIVED (NEW has no configuration, ARCHIVED does) AND their calibration "
        "payloads match. Exit 1 otherwise, 2 if either could not be read.",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.compare and len(args.paths) != 2:
        parser.error("--compare takes exactly two paths")
    if args.compare_reread and len(args.paths) != 2:
        parser.error("--compare-reread takes exactly two paths")
    if args.compare and args.compare_reread:
        parser.error("--compare and --compare-reread are mutually exclusive")
    if args.compare_reread and args.scope != "document":
        parser.error("--compare-reread only supports --scope document")
    if args.payload_only and args.scope != "document":
        # Both flags narrow what is hashed, and --scope qubits is the narrower of
        # the two, so combining them silently ignored --payload-only. This module
        # exits 2 rather than guess anywhere else; it must not guess here either.
        parser.error("--payload-only only supports --scope document")

    if args.compare_reread:
        try:
            new_doc = _load(args.paths[0])
            archived_doc = _load(args.paths[1])
        except (OSError, ValueError) as exc:
            print(f"canonical-snapshot-digest: {exc}", file=sys.stderr)
            return 2
        if not is_lossy_reread(new_doc, archived_doc):
            return 1
        return 0 if _payload_digest(new_doc) == _payload_digest(archived_doc) else 1

    try:
        digests = [
            canonical_digest(p, payload_only=args.payload_only, scope=args.scope)
            for p in args.paths
        ]
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
