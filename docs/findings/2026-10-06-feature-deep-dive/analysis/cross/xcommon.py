"""Shared helpers for the cross-feature dependency scope (``07-cross-feature-dependency.md``).

Every family is reduced to re-measurement events through ``ddload.series`` (the rule the data
dictionary assigns), placeholders masked BEFORE events are formed, values moved to ``log10``.

Families (qubit level unless marked):

- ``T1``, ``T2``: ``q.T1``, ``q.T2`` (measured rule).
- ``RO``: ``q.readout_error`` (measured rule).
- ``p01``, ``p10``: ``q.prob_meas1_prep0``, ``q.prob_meas0_prep1`` (measured rule). Both are
  multiples of 1/4096 and ``p01`` is exactly 0 in some records, so their log uses a
  continuity offset of half a shot: ``log10(p + 1/8192)``. The same offset is applied to both.
- ``init``: ``q.init_error`` (measured rule; schema start 2026-08-04).
- ``m2``: ``g1.measure_2.gate_error`` (measured rule, placeholder ``>= 1`` masked; schema
  start 2026-08-07).
- ``sx``: ``g1.sx.gate_error`` (measured rule, placeholder masked).
- ``cz``, ``rzz`` (coupler): ``g2.cz.gate_error``, ``g2.rzz.gate_error`` on the directed
  column ``[a, b]`` with ``a < b`` (the two directions carry identical values), placeholder
  masked.
- ``zz`` (coupler): ``gen.zz`` (value-only rule), absolute value, exact zeros masked as a
  candidate placeholder (32-33 is 0 in every file).

Days: event stamps are binned into "operational days" that start at ``DAY_START_HOUR`` UTC,
the quietest hour of the daily families' measurement clock (measured in ``alignment.py``).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

SCOPE = "cross"
RESULTS = Path(__file__).resolve().parents[2] / "results" / SCOPE
MS_PER_DAY = 86_400_000.0
P_OFFSET = 1.0 / 8192.0
# Operational-day boundary (UTC hour): the quietest hour of the daily families' event clock,
# ``daily_families_quietest_hour_utc`` in results/cross/alignment.json (16).
DAY_START_HOUR = 16.0
SEED = 20261006

QUBIT_FAMS = ("T1", "T2", "RO", "p01", "p10", "init", "m2", "sx")
COUPLER_FAMS = ("cz", "rzz", "zz")
ALL_FAMS = (*QUBIT_FAMS, *COUPLER_FAMS)
# Qubit-level view of the coupler families: mean over the qubit's adjacent couplers.
QUBIT_VIEW = (*QUBIT_FAMS, "adj_cz", "adj_rzz", "adj_zz")

FIELD = {
    "T1": "q.T1",
    "T2": "q.T2",
    "RO": "q.readout_error",
    "p01": "q.prob_meas1_prep0",
    "p10": "q.prob_meas0_prep1",
    "init": "q.init_error",
    "m2": "g1.measure_2.gate_error",
    "sx": "g1.sx.gate_error",
    "cz": "g2.cz.gate_error",
    "rzz": "g2.rzz.gate_error",
    "zz": "gen.zz",
}

# Which owner document holds a family (for within-family pairs) and which cross-family links
# belong to another owner (the four excluded links of the scope brief).
OWNER = {
    "T1": "02",
    "T2": "02",
    "RO": "03",
    "p01": "03",
    "p10": "03",
    "init": "03",
    "m2": "03",
    "sx": "04",
    "adj_cz": "05",
    "adj_rzz": "05",
    "adj_zz": "05",
    "cz": "05",
    "rzz": "05",
    "zz": "05",
}
_READOUT_ERRORS = ("RO", "p01", "p10", "m2")
_TWOQ = ("adj_cz", "adj_rzz", "cz", "rzz")


def pair_owner(a: str, b: str) -> str:
    """``"07"`` when the pair is this scope's to analyse; otherwise the owner document id.

    Excluded links: readout errors against T1 (03); sx against T1 or T2 (04); cz or rzz
    against their qubits' T1, T2, sx and readout (05); lf against its chain (06, not used
    here). Pairs inside one family are the family owner's.
    """
    oa, ob = OWNER[a], OWNER[b]
    if oa == ob:
        return oa
    s = {a, b}
    if "T1" in s and s & set(_READOUT_ERRORS):
        return "03"
    if "sx" in s and s & {"T1", "T2"}:
        return "04"
    if s & set(_TWOQ) and s & {"T1", "T2", "sx", "RO", "p01", "p10"}:
        return "05"
    return "07"


@dataclass
class Fam:
    """Events of one family: one entry per entity that has events."""

    name: str
    entity: IntArray  # column index of each series
    t_ms: list[FloatArray]  # event time (stamped date, or first file for value-only)
    file_idx: list[IntArray]  # first file carrying each event
    z: list[FloatArray]  # log10 value at each event


def undirected_columns(dd: ddload.DD) -> tuple[IntArray, list[tuple[int, int]]]:
    """Directed ``g2`` columns with ``a < b``, and their ``(a, b)`` pairs, in column order."""
    cols: list[int] = []
    pairs: list[tuple[int, int]] = []
    for k, (a, b) in enumerate(dd.entities("g2.cz.gate_error")):
        if a < b:
            cols.append(k)
            pairs.append((int(a), int(b)))
    return np.array(cols, dtype=np.int64), pairs


def coupler_pairs(dd: ddload.DD, fam: str) -> list[tuple[int, int]]:
    """``(a, b)`` with ``a < b`` for each column of a coupler family as loaded by ``load``."""
    if fam == "zz":
        return [(int(min(a, b)), int(max(a, b))) for a, b in dd.entities("gen.zz")]
    return undirected_columns(dd)[1]


def _zero_or_placeholder(values: FloatArray) -> npt.NDArray[np.bool_]:
    out: npt.NDArray[np.bool_] = values == 0.0
    return out


def load(dd: ddload.DD, fam: str) -> Fam:
    """Events of ``fam`` with ``z = log10`` (offset for ``p01``/``p10``, ``|zz|`` for ``zz``)."""
    field = FIELD[fam]
    if fam == "zz":
        raw = ddload.series(dd, field, rule=ddload.ASSEMBLY, mask=_zero_or_placeholder)
        ser = [s for s in raw if s.y.size]
        zs = [np.log10(np.abs(s.y)) for s in ser]
    else:
        mask = ddload.placeholder_error if fam in ("m2", "sx", "cz", "rzz") else None
        ser = ddload.series(dd, field, rule=ddload.MEASURED, mask=mask)
        if fam in ("cz", "rzz"):
            cols = undirected_columns(dd)[0]
            remap = {int(c): i for i, c in enumerate(cols)}
            ser = [s for s in ser if int(s.entity) in remap]
            for s in ser:
                s.entity = remap[int(s.entity)]
        if fam in ("p01", "p10"):
            zs = [np.log10(s.y + P_OFFSET) for s in ser]
        else:
            keep = []
            zs = []
            for s in ser:
                ok = s.y > 0
                if not ok.all():
                    s.t_ms, s.file_idx, s.y = s.t_ms[ok], s.file_idx[ok], s.y[ok]
                if s.y.size:
                    keep.append(s)
                    zs.append(np.log10(s.y))
            ser = keep
    return Fam(
        name=fam,
        entity=np.array([int(s.entity) for s in ser], dtype=np.int64),
        t_ms=[np.asarray(s.t_ms, dtype=np.float64) for s in ser],
        file_idx=[np.asarray(s.file_idx, dtype=np.int64) for s in ser],
        z=zs,
    )


def day_index(t_ms: FloatArray, day0: float) -> IntArray:
    """Operational day of each stamp, counted from ``day0`` (ms of the first day start)."""
    out: IntArray = np.floor((t_ms - day0) / MS_PER_DAY).astype(np.int64)
    return out


def day_origin(dd: ddload.DD) -> float:
    """Start (ms) of the operational day that contains the first file."""
    first = float(dd.file_ms[0])
    start = math.floor((first - DAY_START_HOUR * 3.6e6) / MS_PER_DAY) * MS_PER_DAY
    return start + DAY_START_HOUR * 3.6e6


def n_days(dd: ddload.DD) -> int:
    return int(day_index(np.array([float(dd.file_ms[-1])]), day_origin(dd))[0]) + 2


def daily(fam: Fam, n_ent: int, day0: float, nd: int) -> FloatArray:
    """``(n_days, n_entities)`` median of the day's event ``z`` per entity (NaN if none)."""
    out = np.full((nd, n_ent), np.nan)
    for e, t, z in zip(fam.entity, fam.t_ms, fam.z, strict=True):
        d = day_index(t, day0)
        ok = (d >= 0) & (d < nd)
        d, zz = d[ok], z[ok]
        if d.size == 0:
            continue
        order = np.argsort(d, kind="stable")
        d, zz = d[order], zz[order]
        bounds = np.flatnonzero(np.diff(d)) + 1
        for chunk_d, chunk_z in zip(np.split(d, bounds), np.split(zz, bounds), strict=True):
            out[int(chunk_d[0]), int(e)] = float(np.median(chunk_z))
    return out


def adjacency(pairs: list[tuple[int, int]], n_q: int = 156) -> list[list[int]]:
    """For each qubit, the coupler columns it belongs to."""
    adj: list[list[int]] = [[] for _ in range(n_q)]
    for k, (a, b) in enumerate(pairs):
        adj[a].append(k)
        adj[b].append(k)
    return adj


def to_qubits(mat: FloatArray, pairs: list[tuple[int, int]], n_q: int = 156) -> FloatArray:
    """Coupler matrix ``(rows, couplers)`` to qubits: mean over adjacent couplers present."""
    adj = adjacency(pairs, n_q)
    out = np.full((mat.shape[0], n_q), np.nan)
    for q in range(n_q):
        if adj[q]:
            block = mat[:, adj[q]]
            cnt = np.isfinite(block).sum(axis=1)
            s = np.nansum(block, axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[:, q] = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)
    return out


def spearman(x: FloatArray, y: FloatArray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return math.nan
    rx = rankdata(x[ok])
    ry = rankdata(y[ok])
    return float(np.corrcoef(rx, ry)[0, 1])


def rankdata(x: FloatArray) -> FloatArray:
    """Average ranks (ties share the mean rank), 1-based."""
    from scipy.stats import rankdata as _rk

    out: FloatArray = np.asarray(_rk(x), dtype=np.float64)
    return out


def bh(pvals: list[float], q: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg step-up: True where the hypothesis is rejected at FDR ``q``."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p)
    thresh = q * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    k = int(np.max(np.flatnonzero(passed))) + 1 if passed.any() else 0
    out = np.zeros(m, dtype=bool)
    out[order[:k]] = True
    return [bool(v) for v in out]


def bh_adjusted(pvals: list[float]) -> list[float]:
    """BH-adjusted p-values (q-values), monotone, capped at 1."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return [round(float(v), 6) for v in out]


def q_list(x: FloatArray, qs: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)) -> Any:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return [round(float(v), 5) for v in np.quantile(x, qs)]


def r6(x: float) -> float | None:
    return None if not np.isfinite(x) else round(float(x), 6)
