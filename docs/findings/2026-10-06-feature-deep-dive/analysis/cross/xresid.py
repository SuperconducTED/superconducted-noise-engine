"""Residuals, rounds, common mode and matched event pairs, shared by the co-movement scripts.

Residual of an event: its ``log10`` value minus the median of the same entity's OTHER events
within +-7 days (a centred, leave-one-out local level), divided by the entity's robust scale
(1.4826 x MAD of its residuals). This isolates the non-persistent part of each series without
assuming a forecasting model; it is not used for forecasting (lead and lag uses a causal EWMA).

Rounds: a family's pooled event stamps split where two consecutive stamps are more than 15
minutes apart (the rule of ``scripts/feature_patterns.py``). The common mode of a round is the
median residual over the entities re-measured in it, defined when at least ``MIN_ROUND``
entities were; ``r_cm`` is the residual minus that common mode.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xcommon as xc
from scipy.stats import norm

HALF_WINDOW_MS = 7 * 86_400_000.0
ROUND_GAP_MS = 15 * 60_000.0
MIN_ROUND = 20


@dataclass
class Resid:
    """Flat event table of one family (all entities concatenated, entity-major, time order)."""

    name: str
    ent: np.ndarray  # entity column of each event
    t: np.ndarray  # event time, ms
    z: np.ndarray  # log10 value
    r: np.ndarray  # standardized residual (NaN if undefined)
    r_cm: np.ndarray  # residual minus its round's common mode (NaN if undefined)
    ns: np.ndarray  # normal scores of r (pooled over the family)
    ns_cm: np.ndarray  # normal scores of r_cm
    round_id: np.ndarray
    base: np.ndarray  # per entity column: first flat index (or -1)
    count: np.ndarray  # per entity column: number of events
    loc: np.ndarray  # index of each event within its entity
    f: np.ndarray  # first file carrying each event
    scale: np.ndarray  # per entity column: robust scale of the raw log10 residual (NaN if none)


def loo_level(t: np.ndarray, z: np.ndarray) -> np.ndarray:
    lo = np.searchsorted(t, t - HALF_WINDOW_MS, "left")
    hi = np.searchsorted(t, t + HALF_WINDOW_MS, "right")
    out = np.full(z.size, np.nan)
    for i in range(z.size):
        w = np.concatenate([z[lo[i] : i], z[i + 1 : hi[i]]])
        if w.size >= 3:
            out[i] = np.median(w)
    return out


def normal_scores(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    if ok.sum() == 0:
        return out
    out[ok] = norm.ppf(xc.rankdata(x[ok]) / (ok.sum() + 1.0))
    return out


def build(fam: xc.Fam, width: int) -> Resid:
    ents, ts, zs, rs, locs, fs = [], [], [], [], [], []
    scales = np.full(width, np.nan)
    for e, t, z, fi in zip(fam.entity, fam.t_ms, fam.z, fam.file_idx, strict=True):
        order = np.argsort(t, kind="stable")
        t, z, fi = t[order], z[order], fi[order]
        r = z - loo_level(t, z)
        ok = np.isfinite(r)
        scale = 1.4826 * np.median(np.abs(r[ok] - np.median(r[ok]))) if ok.sum() >= 5 else 0.0
        r = r / scale if scale > 0 else np.full(r.size, np.nan)
        if scale > 0:
            scales[int(e)] = scale
        fs.append(fi)
        ents.append(np.full(t.size, int(e)))
        ts.append(t)
        zs.append(z)
        rs.append(r)
        locs.append(np.arange(t.size))
    ent = np.concatenate(ents)
    t = np.concatenate(ts)
    z = np.concatenate(zs)
    r = np.concatenate(rs)
    loc = np.concatenate(locs)
    order = np.argsort(t, kind="stable")
    ts_sorted = t[order]
    rid_sorted = np.concatenate([[0], np.cumsum(np.diff(ts_sorted) > ROUND_GAP_MS)])
    round_id = np.empty(t.size, dtype=np.int64)
    round_id[order] = rid_sorted
    cm = np.full(int(round_id.max()) + 1, np.nan)
    okr = np.isfinite(r)
    for k in np.unique(round_id[okr]):
        sel = (round_id == k) & okr
        if sel.sum() >= MIN_ROUND:
            cm[k] = np.median(r[sel])
    r_cm = r - cm[round_id]
    base = np.full(width, -1, dtype=np.int64)
    count = np.zeros(width, dtype=np.int64)
    pos = 0
    for e_arr in ents:
        e = int(e_arr[0])
        base[e] = pos
        count[e] = e_arr.size
        pos += e_arr.size
    return Resid(
        name=fam.name,
        ent=ent,
        t=t,
        z=z,
        r=r,
        r_cm=r_cm,
        ns=normal_scores(r),
        ns_cm=normal_scores(r_cm),
        round_id=round_id,
        base=base,
        count=count,
        loc=loc,
        f=np.concatenate(fs),
        scale=scales,
    )


def qubit_events(res: Resid, pairs: list[tuple[int, int]] | None) -> list[np.ndarray]:
    """Flat event indices attached to each qubit (coupler events attach to both qubits)."""
    out: list[list[np.ndarray]] = [[] for _ in range(156)]
    for e in np.flatnonzero(res.count > 0):
        idx = np.arange(res.base[e], res.base[e] + res.count[e])
        if pairs is None:
            out[int(e)].append(idx)
        else:
            a, b = pairs[int(e)]
            out[a].append(idx)
            out[b].append(idx)
    flat = []
    for lst in out:
        if lst:
            idx = np.concatenate(lst)
            flat.append(idx[np.argsort(res.t[idx], kind="stable")])
        else:
            flat.append(np.empty(0, dtype=np.int64))
    return flat


def match(
    fa: Resid,
    qa: list[np.ndarray],
    fb: Resid,
    qb: list[np.ndarray],
    window_ms: float,
    nearest: bool,
) -> dict[str, np.ndarray]:
    """Pairs (i in A, j in B) on the same qubit with |t_j - t_i| <= window.

    ``nearest``: only the nearest B event per A event; otherwise every B event in the window.
    """
    ia, jb, gap, qq = [], [], [], []
    for q in range(156):
        a, b = qa[q], qb[q]
        if a.size == 0 or b.size == 0:
            continue
        ta, tb = fa.t[a], fb.t[b]
        if nearest:
            k = np.searchsorted(tb, ta)
            lo = np.clip(k - 1, 0, tb.size - 1)
            hi = np.clip(k, 0, tb.size - 1)
            pick = np.where(np.abs(tb[lo] - ta) <= np.abs(tb[hi] - ta), lo, hi)
            g = tb[pick] - ta
            ok = np.abs(g) <= window_ms
            ia.append(a[ok])
            jb.append(b[pick[ok]])
            gap.append(g[ok])
            qq.append(np.full(int(ok.sum()), q))
        else:
            lo = np.searchsorted(tb, ta - window_ms, "left")
            hi = np.searchsorted(tb, ta + window_ms, "right")
            n = hi - lo
            if n.sum() == 0:
                continue
            rep_a = np.repeat(np.arange(a.size), n)
            offs = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
            jj = lo[rep_a] + offs
            ia.append(a[rep_a])
            jb.append(b[jj])
            gap.append(tb[jj] - ta[rep_a])
            qq.append(np.full(int(n.sum()), q))
    if not ia:
        empty = np.empty(0, dtype=np.int64)
        return {"i": empty, "j": empty, "gap_h": np.empty(0), "q": empty}
    return {
        "i": np.concatenate(ia),
        "j": np.concatenate(jb),
        "gap_h": np.concatenate(gap) / 3.6e6,
        "q": np.concatenate(qq),
    }


def shifted(fb: Resid, j: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Circularly shift B's values within each entity: index map for one null replicate.

    Each entity's offset is uniform on [10%, 90%] of its event count, so B keeps its own
    autocorrelation and marginal while losing its alignment with A.
    """
    n = np.maximum(fb.count, 1)
    k = (rng.uniform(0.1, 0.9, n.size) * n).astype(np.int64)
    e = fb.ent[j]
    out: np.ndarray = fb.base[e] + (fb.loc[j] + k[e]) % n[e]
    return out


def corr(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 20:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def binned_mi(x: np.ndarray, y: np.ndarray, bins: int = 8) -> float:
    """Plug-in mutual information (nats) on quantile bins of both variables."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 100:
        return float("nan")
    ex = np.quantile(x, np.linspace(0, 1, bins + 1))
    ey = np.quantile(y, np.linspace(0, 1, bins + 1))
    bx = np.clip(np.searchsorted(ex, x, "right") - 1, 0, bins - 1)
    by = np.clip(np.searchsorted(ey, y, "right") - 1, 0, bins - 1)
    tab = np.zeros((bins, bins))
    np.add.at(tab, (bx, by), 1.0)
    p = tab / tab.sum()
    px = p.sum(axis=1, keepdims=True)
    py = p.sum(axis=0, keepdims=True)
    nz = p > 0
    return float(np.sum(p[nz] * np.log(p[nz] / (px @ py)[nz])))


def cluster_boot_corr(
    x: np.ndarray, y: np.ndarray, q: np.ndarray, rng: np.random.Generator, reps: int
) -> list[float | None]:
    """95% interval of the pooled Pearson correlation, resampling qubits with replacement."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, q = x[ok], y[ok], q[ok]
    if x.size < 20:
        return [None, None]
    stats = np.zeros((156, 6))
    np.add.at(stats[:, 0], q, 1.0)
    np.add.at(stats[:, 1], q, x)
    np.add.at(stats[:, 2], q, y)
    np.add.at(stats[:, 3], q, x * x)
    np.add.at(stats[:, 4], q, y * y)
    np.add.at(stats[:, 5], q, x * y)
    present = np.flatnonzero(stats[:, 0] > 0)
    s = stats[present]
    out = np.empty(reps)
    for r in range(reps):
        w = np.bincount(rng.integers(0, present.size, present.size), minlength=present.size)
        t = w @ s
        n, sx, sy, sxx, syy, sxy = t
        cov = sxy / n - (sx / n) * (sy / n)
        vx = sxx / n - (sx / n) ** 2
        vy = syy / n - (sy / n) ** 2
        out[r] = cov / np.sqrt(vx * vy) if vx > 0 and vy > 0 else np.nan
    return [xc.r6(float(np.nanquantile(out, 0.025))), xc.r6(float(np.nanquantile(out, 0.975)))]
