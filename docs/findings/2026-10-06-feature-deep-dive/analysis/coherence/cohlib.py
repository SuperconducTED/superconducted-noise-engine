"""Shared rules of the coherence scope (``02-coherence.md``): pairing, rounds, levels, periods.

Every threshold a coherence script uses is a constant here, and every script copies the
ones it used into its results JSON, so a reader can audit what produced each count.

Contracts:

- ``events(dd, field)`` returns the MEASURED-rule events of ``q.T1`` or ``q.T2`` (one
  ``Series`` per qubit that has any record), via ``ddload.series``; no placeholder mask is
  needed because neither field ever carries one (01-data-layer.md, section 3).
- ``paired(dd)`` returns, per qubit, the T2 events whose file carries a T1 record stamped
  within ``SYNC_WINDOW_H`` of the T2 stamp. Only these pairs feed the derived quantities that
  need both times (pure dephasing, T2/T1, lambda). gamma depends on T1 alone and uses T1's
  events.
- ``rounds(stamps_ms)`` clusters event stamps into device-wide rounds: sorted stamps split
  wherever two consecutive ones are more than ``ROUND_GAP_MIN`` minutes apart (the rule of
  P1 in docs/roadmap/2026-10-05-feature-patterns-and-method.md).
- ``rolling_level(z)`` is a centred running median over the ``LEVEL_WINDOW - 1`` events
  around each event, the event itself left out (fewer at the ends, never fewer than
  ``LEVEL_MIN``). Leaving the event out avoids exact-zero deviations and the shrinkage of a
  deviation toward its own level; a median of 14 neighbours is not moved by an isolated
  excursion of up to 6 events.
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

SCOPE = "coherence"
RESULTS = Path(__file__).resolve().parents[2] / "results" / SCOPE

# sx gate length used by ADR-027's gamma and lambda: 24 ns in every file
# (01-data-layer.md, section 3, row g1.sx.gate_length). Not loaded: another scope owns it.
SX_LENGTH_S = 24e-9
SYNC_WINDOW_H = 1.0
ROUND_GAP_MIN = 15.0
LEVEL_WINDOW = 15
LEVEL_MIN = 8
# The first file without a configuration section (a historical fetch) is
# 2026-08-05T23:45:31Z; before it the archive holds live polls only (01-data-layer.md, s. 6).
PERIOD_SPLIT_MS = 1785973531000.0
# Readout medians quoted from 01-data-layer.md, section 3 (prob_meas0_prep1 and
# prob_meas1_prep0), with the 99th percentiles as a pessimistic case.
P10_MEDIAN, P01_MEDIAN = 0.0137, 0.0061
P10_P99, P01_P99 = 0.185, 0.167


def constants() -> dict[str, Any]:
    return {
        "sx_length_s": SX_LENGTH_S,
        "sync_window_h": SYNC_WINDOW_H,
        "round_gap_min": ROUND_GAP_MIN,
        "level_window_events": LEVEL_WINDOW,
        "level_min_events": LEVEL_MIN,
        "period_split_utc": "2026-08-05T23:45:31Z",
    }


def header(script: str) -> dict[str, Any]:
    out = ddload.result_header(SCOPE, script)
    out["constants"] = constants()
    return out


def write(name: str, payload: dict[str, Any]) -> None:
    ddload.write_json(RESULTS / name, payload)


def check_period_split(dd: ddload.DD) -> None:
    """Fail loudly if the cache's first historical fetch is not the pinned split."""
    hist = np.flatnonzero(np.asarray(dd.file("has_configuration")) == 0)
    first = float(dd.file_ms[int(hist[0])])
    if first != PERIOD_SPLIT_MS:
        raise ValueError(f"first historical file at {first}, expected {PERIOD_SPLIT_MS}")


def events(dd: ddload.DD, field: str) -> list[Any]:
    return ddload.series(dd, field, rule=ddload.MEASURED)


@dataclass
class Pairs:
    """Paired T1/T2 events of one qubit (one row per T2 event with a synchronous T1)."""

    entity: int
    t_ms: FloatArray  # T2 stamp
    file_idx: npt.NDArray[np.int64]
    t1: FloatArray  # us
    t2: FloatArray  # us
    offset_s: FloatArray  # T2 stamp minus T1 stamp, seconds


def paired(dd: ddload.DD) -> tuple[list[Pairs], dict[str, int]]:
    t1v = np.array(dd.v("q.T1"), dtype=np.float64)
    t1d = np.array(dd.d("q.T1"), dtype=np.float64)
    s2 = events(dd, "q.T2")
    out: list[Pairs] = []
    counts = {"t2_events": 0, "paired": 0, "no_t1_record": 0, "outside_window": 0}
    for s in s2:
        e = s.entity
        fi = s.file_idx
        a = t1v[fi, e]
        ad = t1d[fi, e]
        off_h = (s.t_ms - ad) / ddload.MS_PER_HOUR
        has = np.isfinite(a) & np.isfinite(ad)
        ok = has & (np.abs(off_h) <= SYNC_WINDOW_H)
        counts["t2_events"] += int(s.y.size)
        counts["paired"] += int(ok.sum())
        counts["no_t1_record"] += int((~has).sum())
        counts["outside_window"] += int((has & ~ok).sum())
        if ok.any():
            out.append(
                Pairs(
                    entity=e,
                    t_ms=s.t_ms[ok],
                    file_idx=fi[ok],
                    t1=a[ok],
                    t2=s.y[ok],
                    offset_s=off_h[ok] * 3600.0,
                )
            )
    return out, counts


def gamma_phi(t1: FloatArray, t2: FloatArray) -> FloatArray:
    """Pure-dephasing rate 1/T2 - 1/(2 T1), in 1/us (Krantz et al. 2019, eq. 42)."""
    out: FloatArray = 1.0 / t2 - 0.5 / t1
    return out


def adr027_gamma(t1_us: FloatArray) -> FloatArray:
    out: FloatArray = 1.0 - np.exp(-SX_LENGTH_S / (t1_us * 1e-6))
    return out


def adr027_lambda(t1_us: FloatArray, t2_us: FloatArray) -> FloatArray:
    """ADR-027's lambda; NaN where ADR-027 rejects the row (T2 > 2 T1)."""
    rate = 2.0 / (t2_us * 1e-6) - 1.0 / (t1_us * 1e-6)
    out: FloatArray = np.where(t2_us <= 2.0 * t1_us, 1.0 - np.exp(-SX_LENGTH_S * rate), np.nan)
    return out


def rounds(stamps_ms: FloatArray) -> tuple[FloatArray, npt.NDArray[np.int64]]:
    """Round id of every stamp (input order) and the start stamp of every round."""
    order = np.argsort(stamps_ms, kind="stable")
    s = stamps_ms[order]
    new = np.empty(s.size, dtype=bool)
    new[0] = True
    new[1:] = np.diff(s) > ROUND_GAP_MIN * 60_000.0
    rid_sorted = np.cumsum(new) - 1
    rid = np.empty(s.size, dtype=np.int64)
    rid[order] = rid_sorted
    starts: FloatArray = s[new]
    return starts, rid


def rolling_level(z: FloatArray, window: int = LEVEL_WINDOW, min_n: int = LEVEL_MIN) -> FloatArray:
    """Centred running median of the neighbours of each point, the point itself left out."""
    n = z.size
    half = window // 2
    out = np.full(n, np.nan)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        w = np.concatenate([z[lo:i], z[i + 1 : hi]])
        w = w[np.isfinite(w)]
        if w.size >= min_n:
            out[i] = float(np.median(w))
    return out


def rolling_level_batch(
    z: FloatArray, window: int = LEVEL_WINDOW, min_n: int = LEVEL_MIN
) -> FloatArray:
    """``rolling_level`` applied to every row of a 2-D array at once (for shuffles)."""
    half = window // 2
    pad = np.full((z.shape[0], half), np.nan)
    zp = np.concatenate([pad, z, pad], axis=1)
    win = np.array(np.lib.stride_tricks.sliding_window_view(zp, window, axis=1))
    win[:, :, half] = np.nan  # leave the point itself out, as rolling_level does
    cnt = np.sum(np.isfinite(win), axis=2)
    with np.errstate(all="ignore"):
        med = np.nanmedian(win, axis=2)
    out: FloatArray = np.where(cnt >= min_n, med, np.nan)
    return out


def q(
    x: FloatArray, qs: tuple[float, ...] = (0.0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0)
) -> list[float] | None:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return [float(f"{v:.6g}") for v in np.quantile(x, qs)]


def r(x: float | np.floating[Any] | None, digits: int = 6) -> float | None:
    if x is None or not np.isfinite(x):
        return None
    return float(f"{float(x):.{digits}g}")


def bh(pvals: FloatArray, alpha: float = 0.05) -> npt.NDArray[np.bool_]:
    """Benjamini-Hochberg rejections at false-discovery rate ``alpha``."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    order = np.argsort(p)
    thresh = alpha * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    k = int(np.max(np.flatnonzero(passed))) + 1 if passed.any() else 0
    out = np.zeros(m, dtype=bool)
    out[order[:k]] = True
    return out
