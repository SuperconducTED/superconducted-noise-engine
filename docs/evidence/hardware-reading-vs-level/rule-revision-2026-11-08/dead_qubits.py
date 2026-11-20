"""#125 rule revision, N8: how ``ibm_fez`` reports a dead qubit, from every archived capture.

Protocol: ``README.md`` in this folder, committed before this script produced a number. Reads
``calibration-data`` blobs by commit, so a checkout's line endings do not touch them. No project
code.

For each capture: the qubits absent from the ``target`` field's ``x``, ``sx`` or ``measure``; the
qubits whose ``x`` or ``sx`` ``gate_error`` is at least 1 while they stay in the target; and, as a
check that the reader sees errors at all, the ``cz`` pairs with ``gate_error`` at least 1.

Run from the repository root::

    python docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/dead_qubits.py
        --repo <clone> --ref <calibration-data commit> --out <folder>

(one command, split here for width)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

NAME = re.compile(r"snapshots/\d{4}-\d{2}/ibm_fez/(\d{8})T(\d{6})\d*Z\.json$")
SINGLE = ("x", "sx")
REQUIRED = ("x", "sx", "measure")


def captures(repo: str, ref: str) -> list[tuple[str, str, str]]:
    """``(stamp, path, blob)`` for every ``ibm_fez`` snapshot at ``ref``, sorted by stamp."""
    listing = subprocess.run(
        ["git", "-C", repo, "ls-tree", "-r", ref],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    out = []
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        match = NAME.search(path)
        if match:
            out.append((match.group(1) + match.group(2), path, meta.split()[2]))
    return sorted(out)


def read_blobs(repo: str, shas: list[str]) -> Any:
    """Yield each blob's bytes, streamed through one ``git cat-file --batch``."""
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    proc = subprocess.Popen(
        ["git", "-C", repo, "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for sha in shas:
            proc.stdin.write(sha.encode() + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) < 3 or header[1] != b"blob":
                raise SystemExit(f"error: blob {sha} not available: {header!r}")
            data = proc.stdout.read(int(header[2]))
            proc.stdout.read(1)
            yield data
    finally:
        proc.stdin.close()
        proc.wait()


def error_of(entry: dict[str, Any]) -> float | None:
    for parameter in entry.get("parameters", []):
        if parameter.get("name") == "gate_error":
            value = parameter.get("value")
            return None if value is None else float(value)
    return None


def inspect(doc: dict[str, Any]) -> tuple[set[int], set[int], int, dict[int, str | None]]:
    """Absent qubits, dead-marked qubits, dead ``cz`` pairs, and each qubit's ``T1`` date."""
    target = doc.get("target") or {}
    n = int(target.get("num_qubits") or 0)
    have: dict[str, set[int]] = defaultdict(set)
    for op in target.get("operations") or []:
        qargs = op.get("qargs")
        if op.get("name") in REQUIRED and qargs is not None and len(qargs) == 1:
            have[op["name"]].add(int(qargs[0]))
    absent = {q for q in range(n) if any(q not in have[name] for name in REQUIRED)}
    props = doc.get("properties") or {}
    dead: set[int] = set()
    dead_cz = 0
    for entry in props.get("gates") or []:
        err = error_of(entry)
        if err is None or err < 1.0:
            continue
        if entry.get("gate") in SINGLE and len(entry.get("qubits", [])) == 1:
            dead.add(int(entry["qubits"][0]))
        elif entry.get("gate") == "cz":
            dead_cz += 1
    t1_date: dict[int, str | None] = {}
    for q, params in enumerate(props.get("qubits") or []):
        for p in params:
            if p.get("name") == "T1":
                t1_date[q] = p.get("date")
    return absent, dead, dead_cz, t1_date


def spans(stamps: list[str], marked: dict[str, set[int]], qubit: int) -> list[list[Any]]:
    """Consecutive runs of captures in which ``qubit`` is marked: ``[first, last, captures]``."""
    out: list[list[Any]] = []
    for stamp in stamps:
        if qubit in marked[stamp]:
            if out and out[-1][3]:
                out[-1][1] = stamp
                out[-1][2] += 1
            else:
                out.append([stamp, stamp, 1, True])
        elif out:
            out[-1][3] = False
    return [span[:3] for span in out]


def write_json_lf(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    entries = captures(args.repo, args.ref)
    absent: dict[str, set[int]] = {}
    dead: dict[str, set[int]] = {}
    dead_cz_captures = 0
    t1_dates: dict[str, dict[int, str | None]] = {}
    no_target = 0
    for (stamp, _, _), raw in zip(
        entries, read_blobs(args.repo, [e[2] for e in entries]), strict=True
    ):
        doc = json.loads(raw)
        if not (doc.get("target") or {}).get("operations"):
            no_target += 1
        a, d, cz, dates = inspect(doc)
        absent[stamp] = absent.get(stamp, set()) | a
        dead[stamp] = dead.get(stamp, set()) | d
        dead_cz_captures += cz > 0
        t1_dates[stamp] = dates
    stamps = sorted(absent)
    days = sorted({s[:8] for s in stamps})
    qubits = sorted({q for s in stamps for q in dead[s]})
    per_qubit = {}
    for q in qubits:
        q_spans = spans(stamps, dead, q)
        per_qubit[str(q)] = {
            "captures": sum(span[2] for span in q_spans),
            "spans": [
                {
                    "first": first,
                    "last": last,
                    "captures": count,
                    "t1_date_at_first": t1_dates[first].get(q),
                    "t1_date_at_last": t1_dates[last].get(q),
                }
                for first, last, count in q_spans
            ],
        }
    payload = {
        "protocol": "docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/README.md",
        "ref": args.ref,
        "files": len(entries),
        "distinct_stamps": len(stamps),
        "utc_days": len(days),
        "first": stamps[0] if stamps else None,
        "last": stamps[-1] if stamps else None,
        "captures_without_target_operations": no_target,
        "captures_with_a_qubit_absent_from_target": sum(1 for s in stamps if absent[s]),
        "qubits_ever_absent": sorted({q for s in stamps for q in absent[s]}),
        "dead_marked_qubits": per_qubit,
        "utc_days_with_a_dead_marked_qubit": sum(
            1 for d in days if any(dead[s] for s in stamps if s.startswith(d))
        ),
        "captures_with_a_dead_cz_pair": dead_cz_captures,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_json_lf(args.out / "dead-qubits.json", payload)
    print(json.dumps({k: v for k, v in payload.items() if k != "dead_marked_qubits"}, indent=1))
    for q, info in per_qubit.items():
        print(f"qubit {q}: {info['captures']} captures in {len(info['spans'])} spans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
