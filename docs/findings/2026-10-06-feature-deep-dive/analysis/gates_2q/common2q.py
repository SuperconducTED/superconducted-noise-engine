"""Helpers shared by the two-qubit scope scripts (``analysis/gates_2q``).

Contract: every function here is read-only over the cache, deterministic for a fixed seed,
and returns plain Python or NumPy objects. The canonical coupler is the directed column
``[a, b]`` with ``a < b``: ``profile_2q.py`` shows that outside placeholder records the two
directions of a coupler carry the same value AND the same stamp, so one column per coupler
loses nothing and avoids counting each event twice.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

SCOPE = "gates_2q"
OUT_DIR = Path(__file__).resolve().parents[2] / "results" / SCOPE
ROUND_GAP_H = 0.25  # stamps more than 15 minutes apart start a new round (as P1 did)
QS = (0.0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0)
GATES = ("cz", "rzz")


def q(x: Any, qs: Sequence[float] = QS, nd: int = 6) -> list[float] | None:
    """Quantiles of the finite part of ``x`` (None when empty)."""
    a = np.asarray(x, dtype=np.float64).ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return [float(f"{v:.{nd}g}") for v in np.quantile(a, qs)]


def rnd(x: float, nd: int = 4) -> float | None:
    """Round to ``nd`` significant digits; None for NaN."""
    if x is None or not math.isfinite(x):
        return None
    return float(f"{x:.{nd}g}")


def canonical(dd: ddload.DD) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Couplers ``(a, b)`` with ``a < b``, their ``g2`` columns, and the reverse columns."""
    edges = [tuple(int(x) for x in e) for e in dd.entities("g2.cz.gate_error")]
    col = {e: i for i, e in enumerate(edges)}
    pairs = sorted(e for e in edges if e[0] < e[1])
    fwd = [col[e] for e in pairs]
    rev = [col[(e[1], e[0])] for e in pairs]
    return [(int(a), int(b)) for a, b in pairs], fwd, rev


def gen_columns(dd: ddload.DD, pairs: Sequence[tuple[int, int]]) -> list[int]:
    """Column of each canonical coupler in the ``gen.jq`` / ``gen.zz`` arrays."""
    gen = {tuple(sorted(int(x) for x in c)): i for i, c in enumerate(dd.entities("gen.zz"))}
    return [gen[(a, b)] for a, b in pairs]


def label(pair: Sequence[int]) -> str:
    return f"{int(pair[0])}-{int(pair[1])}"


def split_ms(dd: ddload.DD) -> float:
    """Time of the first historical fetch (``configuration: null``): the coverage split.

    Before it the archive holds only documents the hourly poller saw; from it on, historical
    fetches fill in documents the poller missed (01-data-layer.md section 6).
    """
    has_conf = dd.file("has_configuration").astype(bool)
    first_hist = int(np.flatnonzero(~has_conf)[0])
    return float(dd.file_ms[first_hist])


def stem_at(dd: ddload.DD, ms: float) -> str:
    """The stem of the first file whose ``last_update_date`` is at or after ``ms``."""
    i = int(np.searchsorted(dd.file_ms, ms, side="left"))
    return dd.stems[min(i, dd.n_files - 1)]


def iso(ms: float) -> str:
    return np.datetime64(int(ms), "ms").astype("datetime64[s]").astype(str) + "Z"


def gate_series(dd: ddload.DD, gate: str, fwd: Sequence[int]) -> dict[int, Any]:
    """Measured-rule events of ``g2.<gate>.gate_error`` on canonical columns, placeholders masked.

    Returns ``{column: Series}``; permanently faulty couplers have no series.
    """
    out = ddload.series(
        dd, f"g2.{gate}.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error
    )
    keep = set(fwd)
    return {s.entity: s for s in out if s.entity in keep}


def rounds(stamps_ms: np.ndarray, gap_h: float = ROUND_GAP_H) -> list[np.ndarray]:
    """Split sorted event stamps into rounds where consecutive stamps are > ``gap_h`` apart."""
    s = np.sort(np.asarray(stamps_ms, dtype=np.float64))
    if s.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(s) > gap_h * ddload.MS_PER_HOUR)
    return np.split(s, breaks + 1)


def spearman(x: Any, y: Any) -> dict[str, Any]:
    """Spearman rank correlation of the finite pairs, with n and the two-sided p-value."""
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    n = int(ok.sum())
    if n < 4:
        return {"rho": None, "p": None, "n": n}
    r = stats.spearmanr(a[ok], b[ok])
    return {"rho": rnd(float(r.statistic)), "p": rnd(float(r.pvalue), 3), "n": n}


def partial_spearman(x: Any, y: Any, z: Any) -> dict[str, Any]:
    """Rank partial correlation of x and y given z (Pearson of rank residuals)."""
    a, b, c = (np.asarray(v, dtype=np.float64) for v in (x, y, z))
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(c)
    n = int(ok.sum())
    if n < 5:
        return {"rho": None, "n": n}
    ra, rb, rc = (stats.rankdata(v[ok]) for v in (a, b, c))

    def resid(u: np.ndarray, w: np.ndarray) -> np.ndarray:
        beta = np.polyfit(w, u, 1)
        out: np.ndarray = u - np.polyval(beta, w)
        return out

    ea, eb = resid(ra, rc), resid(rb, rc)
    rho = float(np.corrcoef(ea, eb)[0, 1])
    t = rho * math.sqrt((n - 3) / max(1e-12, 1 - rho * rho))
    p = float(2 * stats.t.sf(abs(t), n - 3))
    return {"rho": rnd(rho), "p": rnd(p, 3), "n": n}


def bh(pvals: Sequence[float], alpha: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg: boolean array of discoveries at false-discovery rate ``alpha``."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    order = np.argsort(p)
    thresh = alpha * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    out = np.zeros(m, dtype=bool)
    if passed.any():
        k = int(np.max(np.flatnonzero(passed)))
        out[order[: k + 1]] = True
    return out


def kruskal_groups(values: np.ndarray, groups: np.ndarray, min_n: int = 30) -> dict[str, Any]:
    """Kruskal-Wallis over groups with at least ``min_n`` members, with epsilon squared.

    Epsilon squared ``(H - k + 1) / (n - k)`` is the rank-based share of variance the groups
    explain (0 = none). Groups below ``min_n`` are dropped and counted.
    """
    labels = np.unique(groups)
    kept = [g for g in labels if np.sum(groups == g) >= min_n]
    samples = [values[groups == g] for g in kept]
    n = int(sum(s.size for s in samples))
    k = len(samples)
    if k < 2:
        return {"groups": k, "n": n, "H": None, "p": None, "epsilon2": None}
    h, p = stats.kruskal(*samples)
    eps = (h - k + 1) / (n - k)
    return {
        "groups": k,
        "groups_dropped_lt_min_n": len(labels) - k,
        "n": n,
        "H": rnd(float(h)),
        "p": rnd(float(p), 3),
        "epsilon2": rnd(float(eps), 3),
        "median_by_group": {
            str(int(g)): rnd(float(np.median(s))) for g, s in zip(kept, samples, strict=True)
        },
        "n_by_group": {str(int(g)): int(s.size) for g, s in zip(kept, samples, strict=True)},
    }


def moving_median_deviation(z: np.ndarray, half: int = 3) -> np.ndarray:
    """``z_k`` minus the median of its neighbours ``k-half..k+half`` (``k`` itself excluded).

    A local detrend for seasonality tests: the slowly moving level is removed without letting
    the event itself set its own reference. Ends use the neighbours that exist.
    """
    n = z.size
    out = np.full(n, np.nan)
    for k in range(n):
        lo, hi = max(0, k - half), min(n, k + half + 1)
        nb = np.concatenate([z[lo:k], z[k + 1 : hi]])
        if nb.size >= 2:
            out[k] = z[k] - float(np.median(nb))
    return out


def hour_weekday(ms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """UTC hour (0-23) and weekday (0 = Monday) of epoch-ms stamps."""
    secs = (np.asarray(ms, dtype=np.float64) // 1000).astype(np.int64)
    hour = (secs // 3600) % 24
    day = secs // 86400
    weekday = (day + 3) % 7  # 1970-01-01 was a Thursday
    return hour, weekday


def write(name: str, script: str, payload: dict[str, Any]) -> Path:
    head = ddload.result_header(SCOPE, script)
    head.update(payload)
    path = OUT_DIR / name
    ddload.write_json(path, head)
    return path
