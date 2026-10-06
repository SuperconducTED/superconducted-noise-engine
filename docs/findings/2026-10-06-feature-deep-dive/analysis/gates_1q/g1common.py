"""Shared helpers for the single-qubit gate scope (``04-single-qubit-gates.md``).

Every script in this folder imports ``ddload`` (one level up) and this module. Nothing here
reads the archive: it only transforms arrays that ``ddload`` returns.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import stats

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

SCOPE = "gates_1q"
RESULTS = Path(__file__).resolve().parents[2] / "results" / SCOPE
HOUR_MS = 3.6e6
DAY_MS = 24.0 * HOUR_MS
LOG10_2 = math.log10(2.0)
ROUND_GAP_H = 0.25  # stamps more than 15 minutes apart start a new round (as P1)
SX_FIELD = "g1.sx.gate_error"


def q(x: Any, qs: Sequence[float] = (0.0, 0.01, 0.1, 0.5, 0.9, 0.99, 1.0), nd: int = 6) -> Any:
    """Quantiles of the finite part of ``x`` (None when empty)."""
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return [round(float(v), nd) for v in np.quantile(a, qs)]


def rnd(x: float, nd: int = 4) -> float | None:
    return None if x is None or not math.isfinite(x) else round(float(x), nd)


def spearman(x: Any, y: Any) -> dict[str, Any]:
    """Spearman rank correlation of the jointly finite part, with n and the two-sided p."""
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    n = int(ok.sum())
    if n < 4:
        return {"rho": None, "p": None, "n": n}
    r = stats.spearmanr(a[ok], b[ok])
    return {"rho": rnd(float(r.statistic)), "p": float(f"{float(r.pvalue):.3g}"), "n": n}


def running_level(z: FloatArray, half: int = 5, min_neighbours: int = 4) -> FloatArray:
    """Centred running median of ``z`` over up to ``half`` events each side, EXCLUDING self.

    Excluding the event itself keeps a single spike from pulling its own reference level.
    Returns NaN where fewer than ``min_neighbours`` finite neighbours exist.
    """
    n = z.size
    out = np.full(n, np.nan)
    for k in range(n):
        lo, hi = max(0, k - half), min(n, k + half + 1)
        nb = np.concatenate([z[lo:k], z[k + 1 : hi]])
        nb = nb[np.isfinite(nb)]
        if nb.size >= min_neighbours:
            out[k] = float(np.median(nb))
    return out


def rounds(stamps_ms: FloatArray, gap_h: float = ROUND_GAP_H) -> tuple[FloatArray, IntArray]:
    """Cluster sorted stamps into rounds; returns (round start ms, round id per stamp)."""
    order = np.argsort(stamps_ms, kind="stable")
    s = stamps_ms[order]
    new = np.concatenate([[True], np.diff(s) > gap_h * HOUR_MS])
    rid_sorted = np.cumsum(new) - 1
    rid = np.empty_like(rid_sorted)
    rid[order] = rid_sorted
    starts = s[new]
    return starts, rid.astype(np.int64)


def bh(pvals: Sequence[float], alpha: float = 0.05) -> npt.NDArray[np.bool_]:
    """Benjamini-Hochberg step-up: which hypotheses are rejected at FDR ``alpha``."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    order = np.argsort(p)
    thresh = alpha * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    out = np.zeros(m, dtype=bool)
    if passed.any():
        kmax = int(np.flatnonzero(passed).max())
        out[order[: kmax + 1]] = True
    return out


def month_of(ms: FloatArray) -> list[str]:
    return [datetime.fromtimestamp(float(t) / 1000.0, tz=UTC).strftime("%Y-%m") for t in ms]


def iso(ms: float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms_of(text: str) -> float:
    """``YYYY-MM-DDTHH:MM:SSZ`` to ms since the epoch."""
    dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return dt.timestamp() * 1000.0


def nearest(t_target: FloatArray, t_src: FloatArray) -> tuple[IntArray, FloatArray]:
    """For each target stamp, the index of the nearest source stamp and the signed offset (h).

    Offset is ``t_src - t_target`` in hours (negative: the source was stamped earlier).
    """
    j = np.searchsorted(t_src, t_target)
    lo = np.clip(j - 1, 0, t_src.size - 1)
    hi = np.clip(j, 0, t_src.size - 1)
    d_lo = t_src[lo] - t_target
    d_hi = t_src[hi] - t_target
    use_hi = np.abs(d_hi) < np.abs(d_lo)
    idx = np.where(use_hi, hi, lo).astype(np.int64)
    off = np.where(use_hi, d_hi, d_lo) / HOUR_MS
    return idx, off


def theil_sen(x: Any, y: Any) -> dict[str, Any]:
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 4:
        return {"slope": None, "lo95": None, "hi95": None, "n": int(ok.sum())}
    r = stats.theilslopes(b[ok], a[ok], alpha=0.95)
    return {
        "slope": rnd(float(r.slope)),
        "lo95": rnd(float(r.low_slope)),
        "hi95": rnd(float(r.high_slope)),
        "n": int(ok.sum()),
    }


def kruskal(groups: Sequence[FloatArray]) -> dict[str, Any]:
    """Kruskal-Wallis H with epsilon-squared effect size, over non-empty groups."""
    gs = [np.asarray(g, dtype=np.float64) for g in groups]
    gs = [g[np.isfinite(g)] for g in gs]
    gs = [g for g in gs if g.size > 0]
    n = int(sum(g.size for g in gs))
    if len(gs) < 2:
        return {"H": None, "p": None, "epsilon_sq": None, "n": n, "groups": len(gs)}
    r = stats.kruskal(*gs)
    eps = float(r.statistic) / ((n * n - 1) / (n + 1)) if n > 1 else math.nan
    return {
        "H": rnd(float(r.statistic), 3),
        "p": float(f"{float(r.pvalue):.3g}"),
        "epsilon_sq": rnd(eps, 5),
        "n": n,
        "groups": len(gs),
    }
