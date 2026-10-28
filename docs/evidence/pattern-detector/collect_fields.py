"""Collect the per-qubit fields the pattern detector's features need, once, into a pickle.

Reads every ``ibm_fez`` snapshot at a pinned ``calibration-data`` ref with ``git show`` (never a
checkout) and keeps, per file: time, ``qubit_digest``, ``T1`` dates, and per qubit the logs of
``T1``, ``T2``, ``readout_error``, the ``sx`` gate error and the smallest ``cz`` gate error on an
edge touching the qubit (NaN where absent or non-positive). The N0 script's walk is a subset of this
one; ``n1_baselines.py`` checks that the ``T1`` columns agree.

    PYTHONPATH=src;. python docs/evidence/pattern-detector/collect_fields.py \
        --repo . --ref <sha> --cache <scratch>/fields.pkl
"""

from __future__ import annotations

import argparse
import math
import pickle
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scripts.canonical_snapshot_digest import qubit_digest
from scripts.init_error_analysis import list_snapshots, read_snapshot

from superconducted.calibration.loader import parse_snapshot

BACKEND = "ibm_fez"
FIELDS = ("log_t1", "log_t2", "log_readout", "log_sx", "log_cz_best")


@dataclass(frozen=True)
class Fields:
    path: str
    time: float
    digest: str
    t1_dates: tuple[str | None, ...]
    values: np.ndarray  # (n_qubits, len(FIELDS)), NaN where missing


def _epoch(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).timestamp()


def _log(x: float | None) -> float:
    return math.log(x) if x is not None and math.isfinite(x) and x > 0 else math.nan


def fields_of(path: str, doc: dict[str, Any]) -> Fields:
    props = doc["properties"]
    parsed = parse_snapshot(doc, source=path)
    n_q = len(parsed.qubits)
    vals = np.full((n_q, len(FIELDS)), math.nan)
    for q in parsed.qubits:
        vals[q.index, 0] = _log(q.t1_seconds)
        vals[q.index, 1] = _log(q.t2_seconds)
        vals[q.index, 2] = _log(q.readout_error)
    cz_best = np.full(n_q, math.inf)
    for g in props.get("gates", []):
        err = next(
            (p.get("value") for p in g.get("parameters", []) if p.get("name") == "gate_error"), None
        )
        if err is None:
            continue
        if g.get("gate") == "sx" and len(g.get("qubits", [])) == 1:
            vals[g["qubits"][0], 3] = _log(err)
        elif g.get("gate") == "cz":
            for qi in g.get("qubits", []):
                if qi < n_q and err > 0:
                    cz_best[qi] = min(cz_best[qi], err)
    vals[:, 4] = np.where(
        np.isfinite(cz_best), np.log(np.where(np.isfinite(cz_best), cz_best, 1.0)), math.nan
    )
    t1_dates = tuple(
        next((p.get("date") for p in params if p.get("name") == "T1"), None)
        for params in props["qubits"]
    )
    return Fields(path, _epoch(props["last_update_date"]), qubit_digest(doc), t1_dates, vals)


def collect(repo: Path, ref: str) -> list[Fields]:
    paths = [p for p in list_snapshots(repo, ref, "snapshots") if f"/{BACKEND}/" in p]
    out: list[Fields] = []
    for i, path in enumerate(paths):
        out.append(fields_of(path, read_snapshot(repo, ref, path)))
        if (i + 1) % 250 == 0:
            print(f"  read {i + 1}/{len(paths)} files", file=sys.stderr)
    out.sort(key=lambda r: (r.time, r.path))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cache", type=Path, required=True)
    args = ap.parse_args()
    files = collect(args.repo, args.ref)
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_bytes(pickle.dumps(files))
    print(f"collected {len(files)} files at {args.ref} into {args.cache}")


if __name__ == "__main__":
    main()
