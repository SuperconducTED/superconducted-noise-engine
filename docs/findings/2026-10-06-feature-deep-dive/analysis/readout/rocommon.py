"""Shared helpers for the readout scope (``03-readout-measurement.md``).

Notation used in every readout script and in the document (the two older documents use
opposite meanings for "p01", so this scope avoids that name):

- ``p0g1`` is ``q.prob_meas0_prep1``, written P(0|1): prepared |1>, read 0.
- ``p1g0`` is ``q.prob_meas1_prep0``, written P(1|0): prepared |0>, read 1.
- ``ro`` is ``q.readout_error`` (identical, record by record, to ``g1.measure.gate_error``).

Readout events in this scope are **stamp events**: a file in which the stamped date of the
field is new, whatever the value. The shared measured rule (value AND date new) drops a
re-measurement that returned the identical quantized value, which removes exact zero changes
and biases every change statistic; ``readout/profiles.py`` counts how many it drops.

A **readout session** is a cluster of readout stamps across qubits, split where two
consecutive stamps are more than 15 minutes apart (the round rule of
``scripts/feature_patterns.py``). Its **kind** comes from the parity of its published counts
(``4096 * p``): ``even`` when every count is even (the values sit on the 1/2048 grid), ``mixed``
otherwise; sessions with fewer than ``MIN_SESSION_QUBITS`` qubits are ``small`` and are left
out of the shot-noise analysis. That an ``even`` session used 2,048 shots per prepared state
is an inference from the grid, tested in ``readout/noise.py``, not a documented fact.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]

SCOPE = "readout"
RESULTS = Path(__file__).resolve().parents[2] / "results" / "readout"
SAME_SESSION_MS = 600e3  # two stamps within 10 minutes belong to one readout session
SESSION_GAP_MS = 15 * 60e3  # a larger gap between consecutive stamps starts a new session
MIN_SESSION_QUBITS = 100
SHOTS = 4096
LN10 = float(np.log(10.0))
CHANGE_1 = "2026-06-08T18:56:28Z"  # readout length 1560 -> 1700 ns (01-data-layer.md section 5)
CHANGE_2 = "2026-07-30T21:09:17Z"  # readout length 1700 -> 1660 ns


@dataclass
class Readout:
    """The three readout fields and their stamps, ``(n_files, 156)``."""

    ro: FloatArray
    p0g1: FloatArray
    p1g0: FloatArray
    d_ro: FloatArray
    d_p0g1: FloatArray
    d_p1g0: FloatArray
    file_ms: FloatArray


def load(dd: ddload.DD) -> Readout:
    return Readout(
        ro=np.array(dd.v("q.readout_error"), dtype=np.float64),
        p0g1=np.array(dd.v("q.prob_meas0_prep1"), dtype=np.float64),
        p1g0=np.array(dd.v("q.prob_meas1_prep0"), dtype=np.float64),
        d_ro=np.array(dd.d("q.readout_error"), dtype=np.float64),
        d_p0g1=np.array(dd.d("q.prob_meas0_prep1"), dtype=np.float64),
        d_p1g0=np.array(dd.d("q.prob_meas1_prep0"), dtype=np.float64),
        file_ms=dd.file_ms,
    )


def record_classes(r: Readout) -> dict[str, BoolArray]:
    """Classify every qubit record by how its three stamps relate.

    ``same3``: identical stamps. ``staggered``: not identical, all within ``SAME_SESSION_MS``.
    ``stale_p0g1``: P(0|1) stamped more than ``SAME_SESSION_MS`` before ``ro``. ``other``: the
    rest. ``mean_ok``: ``ro == (P(0|1) + P(1|0)) / 2`` to 1e-12.
    """
    same3 = (r.d_ro == r.d_p0g1) & (r.d_ro == r.d_p1g0)
    gap = np.maximum(np.abs(r.d_ro - r.d_p0g1), np.abs(r.d_ro - r.d_p1g0))
    staggered = ~same3 & (gap <= SAME_SESSION_MS)
    stale = (r.d_ro - r.d_p0g1) > SAME_SESSION_MS
    present = np.isfinite(r.ro) & np.isfinite(r.p0g1) & np.isfinite(r.p1g0)
    return {
        "present": present,
        "same3": same3 & present,
        "staggered": staggered & present,
        "stale_p0g1": stale & present,
        "other": present & ~(same3 | staggered | stale),
        "p0g1_fresh": present & (np.abs(r.d_ro - r.d_p0g1) <= SAME_SESSION_MS),
        "p1g0_fresh": present & (np.abs(r.d_ro - r.d_p1g0) <= SAME_SESSION_MS),
        "mean_ok": present & (np.abs(r.ro - (r.p0g1 + r.p1g0) / 2.0) < 1e-12),
    }


def fresh_p0g1(r: Readout, classes: dict[str, BoolArray]) -> FloatArray:
    """P(0|1) of the session that produced ``ro``: published if fresh, else ``2 ro - P(1|0)``.

    NaN where neither is available (P(0|1) stale and P(1|0) not from the same session).
    """
    out = np.full(r.ro.shape, np.nan)
    f = classes["p0g1_fresh"]
    out[f] = r.p0g1[f]
    imp = classes["stale_p0g1"] & classes["p1g0_fresh"]
    out[imp] = 2.0 * r.ro[imp] - r.p1g0[imp]
    return out


def stamp_events(values: FloatArray, dates: FloatArray) -> list[ddload.Series]:
    """One event per new stamped date (value may repeat). Event time is the stamp."""
    out: list[ddload.Series] = []
    for e in range(values.shape[1]):
        v, d = values[:, e], dates[:, e]
        ok = np.flatnonzero(np.isfinite(v) & np.isfinite(d))
        if ok.size == 0:
            continue
        dd_ = d[ok]
        keep = np.concatenate([[True], dd_[1:] != dd_[:-1]])
        idx = ok[keep]
        out.append(ddload.Series(entity=e, t_ms=d[idx], file_idx=idx.astype(np.int64), y=v[idx]))
    return out


@dataclass
class Sessions:
    start_ms: FloatArray
    end_ms: FloatArray
    n_records: IntArray
    n_qubits: IntArray
    n_counts: IntArray
    even_share: FloatArray
    kind: npt.NDArray[np.str_]

    def index(self, t_ms: FloatArray) -> IntArray:
        """Session index of each stamp (-1 if outside every session)."""
        t = np.asarray(t_ms, dtype=np.float64)
        i = np.searchsorted(self.start_ms, t, side="right") - 1
        ok = (i >= 0) & (t <= self.end_ms[np.clip(i, 0, None)])
        out: IntArray = np.where(ok, i, -1).astype(np.int64)
        return out

    def shots(self, idx: IntArray) -> FloatArray:
        """Shots per prepared state implied by the session kind (NaN for small or none)."""
        out = np.full(idx.shape, np.nan)
        good = idx >= 0
        k = np.where(good, idx, 0)
        out[good & (self.kind[k] == "even")] = SHOTS / 2
        out[good & (self.kind[k] == "mixed")] = SHOTS
        return out


def sessions(r: Readout, classes: dict[str, BoolArray]) -> Sessions:
    """Cluster all readout stamp events across qubits into sessions and type them by parity."""
    ev = stamp_events(r.ro, r.d_ro)
    t_all, q_all, k_all, n_all = [], [], [], []
    for s in ev:
        f = s.file_idx
        t_all.append(s.t_ms)
        q_all.append(np.full(f.size, s.entity))
        k1 = np.where(classes["p1g0_fresh"][f, s.entity], r.p1g0[f, s.entity] * SHOTS, np.nan)
        k0 = np.where(classes["p0g1_fresh"][f, s.entity], r.p0g1[f, s.entity] * SHOTS, np.nan)
        k_all.append(np.stack([k0, k1], axis=1))
        n_all.append(np.ones(f.size))
    t = np.concatenate(t_all)
    q = np.concatenate(q_all)
    k = np.concatenate(k_all)
    order = np.argsort(t, kind="stable")
    t, q, k = t[order], q[order], k[order]
    br = np.flatnonzero(np.diff(t) > SESSION_GAP_MS)
    starts = np.concatenate([[0], br + 1])
    ends = np.concatenate([br + 1, [t.size]])
    n_rec, n_q, n_c, even, kind = [], [], [], [], []
    for a, b in zip(starts, ends, strict=True):
        kk = k[a:b].ravel()
        kk = kk[np.isfinite(kk)]
        kr = np.round(kk).astype(np.int64)
        nq = np.unique(q[a:b]).size
        es = float(np.mean(kr % 2 == 0)) if kr.size else float("nan")
        n_rec.append(b - a)
        n_q.append(nq)
        n_c.append(kr.size)
        even.append(es)
        if nq < MIN_SESSION_QUBITS:
            kind.append("small")
        elif es == 1.0:
            kind.append("even")
        else:
            kind.append("mixed")
    return Sessions(
        start_ms=t[starts],
        end_ms=t[ends - 1],
        n_records=np.array(n_rec, dtype=np.int64),
        n_qubits=np.array(n_q, dtype=np.int64),
        n_counts=np.array(n_c, dtype=np.int64),
        even_share=np.array(even),
        kind=np.array(kind),
    )


@dataclass
class NoiseSeries:
    """Readout-session events of one field with the binomial variance of each value."""

    series: list[ddload.Series]
    var: list[FloatArray]  # linear-scale variance of each event's value
    kind: list[npt.NDArray[np.str_]]  # session kind of each event
    restamps_within_session: int = 0


def noise_series(r: Readout, c: dict[str, BoolArray], s: Sessions) -> dict[str, NoiseSeries]:
    """``ro``, fresh P(0|1) and P(1|0) at every readout stamp event, with shot-noise variance.

    The event times are the ``ro`` stamps. A value is set to NaN (and so dropped by every
    consumer) when its session is ``small`` or outside every session, or when its P(1|0) is
    not from the same session; ``ro``'s variance needs both probabilities of its session.
    When one qubit carries several stamps inside one session (a re-stamp minutes apart), only
    the last is kept; ``restamps_within_session`` counts the ones dropped.
    """
    ev = stamp_events(r.ro, r.d_ro)
    p0f = fresh_p0g1(r, c)
    out: dict[str, NoiseSeries] = {k: NoiseSeries([], [], []) for k in ("ro", "p0g1_fresh", "p1g0")}
    restamps = 0
    for e0 in ev:
        idx0 = s.index(e0.t_ms)
        last_in_session = np.concatenate([idx0[1:] != idx0[:-1], [True]]) | (idx0 < 0)
        restamps += int(np.sum(~last_in_session))
        e = ddload.Series(
            entity=e0.entity,
            t_ms=e0.t_ms[last_in_session],
            file_idx=e0.file_idx[last_in_session],
            y=e0.y[last_in_session],
        )
        f, q = e.file_idx, e.entity
        idx = idx0[last_in_session]
        n = s.shots(idx)
        kind = np.where(idx >= 0, s.kind[np.clip(idx, 0, None)], "none")
        p0 = p0f[f, q]
        p1 = np.where(c["p1g0_fresh"][f, q], r.p1g0[f, q], np.nan)
        good = np.isfinite(n) & np.isfinite(p0) & np.isfinite(p1)
        v0 = binom_var(p0, n)
        v1 = binom_var(p1, n)
        for name, y, var in (
            ("ro", r.ro[f, q], (v0 + v1) / 4.0),
            ("p0g1_fresh", p0, v0),
            ("p1g0", p1, v1),
        ):
            yy = np.where(good, y, np.nan)
            out[name].series.append(ddload.Series(entity=q, t_ms=e.t_ms, file_idx=f, y=yy))
            out[name].var.append(np.where(good, var, np.nan))
            out[name].kind.append(kind)
    for v in out.values():
        v.restamps_within_session = restamps
    return out


def binom_var(p: FloatArray, n: FloatArray | float) -> FloatArray:
    """Plug-in binomial variance of an assignment probability estimated from ``n`` shots."""
    out: FloatArray = p * (1.0 - p) / n
    return out


def log10_var(y: FloatArray, var: FloatArray) -> FloatArray:
    """Delta-method variance of ``log10(y)`` (NaN where ``y <= 0``)."""
    out: FloatArray = np.where(y > 0, var / (np.where(y > 0, y, 1.0) * LN10) ** 2, np.nan)
    return out


def quantiles(x: Any, qs: tuple[float, ...] = (0.0, 0.01, 0.1, 0.5, 0.9, 0.99, 1.0)) -> Any:
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return [float(f"{v:.6g}") for v in np.quantile(a, qs)]


def iso_ms(stamp: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000.0


def iso(ms: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def spearman(x: Any, y: Any) -> dict[str, Any]:
    from scipy import stats

    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5:
        return {"n": int(ok.sum()), "rho": None, "p": None}
    res = stats.spearmanr(a[ok], b[ok])
    return {
        "n": int(ok.sum()),
        "rho": round(float(res.statistic), 4),
        "p": float(f"{res.pvalue:.3g}"),
    }


def write(name: str, script: str, payload: dict[str, Any]) -> None:
    out = ddload.result_header(SCOPE, f"analysis/readout/{script}")
    out.update(payload)
    ddload.write_json(RESULTS / name, out)
