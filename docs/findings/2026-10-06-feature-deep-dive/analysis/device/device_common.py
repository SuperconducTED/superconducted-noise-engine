"""Shared helpers of the device, time and topology scope (``06-device-time-topology.md``).

Imported by the scripts in this folder (Python puts a script's own folder first on
``sys.path``). Nothing here writes; every figure is written by the calling script.

Contracts:

- ``FAMILIES``: the measured families whose stamps define the calibration schedule, each
  with its cache field, its placeholder mask and whether its entities are couplers. Coupler
  fields keep only the ``[a, b]`` column with ``a < b``: for non-placeholder records the two
  directions carry identical values and dates (checked in ``batches.py``), so the other
  direction would only duplicate events.
- ``family_events``: re-measurement events (``ddload.MEASURED`` rule, placeholders masked
  before events are formed) as flat arrays, with events stamped before the first file's
  ``last_update_date`` dropped: those are values carried into the first document from before
  the archive starts, not rounds the archive observed.
- ``split_rounds``: a round is a maximal run of stamps with no gap above ``gap_min`` minutes.
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

RESULTS = Path(__file__).resolve().parents[2] / "results" / "device"
SCOPE = "device"
ROUND_GAP_MIN = 15.0
MS_PER_MIN = 6.0e4
MS_PER_DAY = 8.64e7


@dataclass(frozen=True)
class Family:
    name: str
    field: str
    placeholder: bool
    coupler: bool


FAMILIES: tuple[Family, ...] = (
    Family("readout", "q.readout_error", False, False),
    Family("init_error", "q.init_error", False, False),
    Family("measure_2", "g1.measure_2.gate_error", True, False),
    Family("T1", "q.T1", False, False),
    Family("T2", "q.T2", False, False),
    Family("sx", "g1.sx.gate_error", True, False),
    Family("xslow", "g1.xslow.gate_error", True, False),
    Family("cz", "g2.cz.gate_error", True, True),
    Family("rzz", "g2.rzz.gate_error", True, True),
    Family("lf", "gen.lf", False, False),
)


@dataclass
class Events:
    """Flat event arrays of one family, in no particular order."""

    t_ms: FloatArray
    entity: IntArray
    y: FloatArray
    file_idx: IntArray
    n_entities: int
    dropped_carried_in: int


def iso(ms: float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_index(ms: FloatArray | float) -> IntArray:
    out: IntArray = np.floor(np.asarray(ms, dtype=np.float64) / MS_PER_DAY).astype(np.int64)
    return out


def undirected_columns(dd: ddload.DD) -> tuple[list[int], list[tuple[int, int]]]:
    """Columns of the ``g2.*`` arrays whose directed edge has ``a < b``, and those edges."""
    cols, edges = [], []
    for k, (a, b) in enumerate(dd.meta["directed_edges"]):
        if a < b:
            cols.append(k)
            edges.append((int(a), int(b)))
    return cols, edges


def family_events(dd: ddload.DD, fam: Family) -> Events:
    mask = ddload.placeholder_error if fam.placeholder else None
    ser = ddload.series(dd, fam.field, rule=ddload.MEASURED, mask=mask)
    keep: set[int] | None = None
    n_entities = len(dd.entities(fam.field))
    if fam.coupler:
        cols, _ = undirected_columns(dd)
        keep = set(cols)
        n_entities = len(cols)
    first_ms = float(dd.file_ms[0])
    ts, es, ys, fs = [], [], [], []
    dropped = 0
    for s in ser:
        if keep is not None and s.entity not in keep:
            continue
        ok = s.t_ms >= first_ms
        dropped += int(np.sum(~ok))
        ts.append(s.t_ms[ok])
        es.append(np.full(int(ok.sum()), s.entity, dtype=np.int64))
        ys.append(s.y[ok])
        fs.append(s.file_idx[ok])
    return Events(
        t_ms=np.concatenate(ts) if ts else np.array([]),
        entity=np.concatenate(es) if es else np.array([], dtype=np.int64),
        y=np.concatenate(ys) if ys else np.array([]),
        file_idx=np.concatenate(fs) if fs else np.array([], dtype=np.int64),
        n_entities=n_entities,
        dropped_carried_in=dropped,
    )


def split_rounds(t_ms: FloatArray, gap_min: float = ROUND_GAP_MIN) -> IntArray:
    """Round label of every event: stamps sorted, split where two exceed ``gap_min`` apart."""
    order = np.argsort(t_ms, kind="stable")
    ts = t_ms[order]
    cut = np.r_[0, (np.diff(ts) > gap_min * MS_PER_MIN).astype(np.int64)]
    labels_sorted = np.cumsum(cut)
    out = np.empty_like(labels_sorted)
    out[order] = labels_sorted
    return out


def adjacency(dd: ddload.DD) -> list[list[int]]:
    n = len(dd.meta["qubits"])
    adj: list[set[int]] = [set() for _ in range(n)]
    for a, b in dd.meta["coupling_map"]:
        adj[int(a)].add(int(b))
        adj[int(b)].add(int(a))
    return [sorted(s) for s in adj]


def distances(adj: list[list[int]]) -> IntArray:
    """All-pairs hop distance by breadth-first search (-1 if unreachable)."""
    n = len(adj)
    dist = np.full((n, n), -1, dtype=np.int64)
    for s in range(n):
        dist[s, s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for w in adj[u]:
                if dist[s, w] < 0:
                    dist[s, w] = dist[s, u] + 1
                    queue.append(w)
    return dist


def quantiles(x: Any, qs: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)) -> Any:
    arr = np.asarray(x, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return [float(f"{v:.6g}") for v in np.quantile(arr, qs)]


def r6(x: float) -> float:
    return float(f"{float(x):.6g}")


def header(script: str) -> dict[str, Any]:
    return ddload.result_header(SCOPE, f"analysis/device/{script}")
