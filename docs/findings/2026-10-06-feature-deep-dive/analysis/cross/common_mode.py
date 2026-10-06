"""Device-wide common mode across families, and the day-aligned change matrix.

1. ``device_daily``: per family and operational day (from 16:00 UTC), the device median of the
   entities' daily median ``log10`` values, kept when at least half of the family's entities
   were re-measured that day. Day-to-day changes of these medians are compared across every
   pair of families (Spearman over common days); null: 2,000 circular shifts of one family's
   day series; interval: 2,000-replicate moving-block bootstrap over days (block 7);
   Benjamini-Hochberg over all pairs. Days on which many families jump together are listed.
2. ``common_mode_share``: per family, the share of the residual variance (``xresid``) that the
   round's common mode accounts for, ``1 - var(r_cm) / var(r)``, plain and robust (MAD).
3. ``variograms``: ``ddload.variogram`` of each family's per-entity series and of its device
   series (per round with at least half the entities: the median over entities of the value
   minus the entity's own long-run median). If the non-persistent component were independent
   across entities, the device series' shortest-lag semivariance would be about
   ``(pi / 2) / N`` of the per-entity one (N entities per round); a shared component would not
   shrink.
4. ``change_matrix``: per qubit and day, the median residual of each family (coupler families
   as the mean over the qubit's adjacent couplers), raw and with the round common mode removed;
   its normal-score correlation matrix over qubit-days (pairwise complete), eigenvalues
   against 200 null matrices in which each family's day axis is circularly shifted per qubit,
   and the day-aligned correlation of this scope's 23 pairs with BH.

Writes ``results/cross/common_mode.json``.
"""

from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc
import xresid as xr

OUT = xc.RESULTS / "common_mode.json"
N_NULL = 2000
N_BOOT = 2000
BLOCK = 7
N_PCA_NULL = 200
JUMP_SD = 2.5


def day_label(day0: float, d: int) -> str:
    ms = day0 + d * xc.MS_PER_DAY
    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m-%dT%H:%MZ")


def spearman_pair(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return math.nan, int(ok.sum())
    return xc.spearman(x[ok], y[ok]), int(ok.sum())


def block_boot(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> list[float | None]:
    n = x.size
    starts_max = n - BLOCK
    out = np.empty(N_BOOT)
    for r in range(N_BOOT):
        starts = rng.integers(0, starts_max + 1, math.ceil(n / BLOCK))
        idx = (starts[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]
        out[r] = spearman_pair(x[idx], y[idx])[0]
    return [xc.r6(float(np.nanquantile(out, 0.025))), xc.r6(float(np.nanquantile(out, 0.975)))]


def normal_scores_col(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    out[ok] = norm.ppf(xc.rankdata(x[ok]) / (ok.sum() + 1.0))
    return out


def pairwise_corr(m: np.ndarray) -> np.ndarray:
    k = m.shape[1]
    c = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            ok = np.isfinite(m[:, i]) & np.isfinite(m[:, j])
            c[i, j] = c[j, i] = np.corrcoef(m[ok, i], m[ok, j])[0, 1] if ok.sum() > 50 else 0.0
    return c


def eig_desc(c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w, v = np.linalg.eigh(c)
    order = np.argsort(w)[::-1]
    return w[order], v[:, order]


MIN_PAIRS_ENTITY = 200
MIN_PAIRS_DEVICE = 10


def matched_bins(vg_e: dict[str, Any], vg_d: dict[str, Any]) -> dict[str, Any]:
    """Per-entity against device semivariance at the SAME lag bins (robust estimator).

    ``shortest``: the shortest bin with at least 200 per-entity pairs and 10 device pairs;
    ``long``: the 744 to 1,488 h bin. Each row gives both semivariances and their ratio.
    """

    def row(be: dict[str, Any], bd: dict[str, Any]) -> dict[str, Any]:
        se, sd = be["semivariance_robust"], bd["semivariance_robust"]
        return {
            "lag_h_lo": be["lag_h_lo"],
            "lag_h_hi": be["lag_h_hi"],
            "entity_pairs": be["pairs"],
            "device_pairs": bd["pairs"],
            "entity_semivariance_robust": se,
            "device_semivariance_robust": sd,
            "device_to_entity_ratio": xc.r6(sd / se) if se and sd is not None else None,
        }

    pairs = list(zip(vg_e["bins"], vg_d["bins"], strict=True))
    short = next(
        (
            (be, bd)
            for be, bd in pairs
            if be["pairs"] >= MIN_PAIRS_ENTITY and bd["pairs"] >= MIN_PAIRS_DEVICE
        ),
        None,
    )
    long = next(((be, bd) for be, bd in pairs if be["lag_h_lo"] == 744.0), None)
    return {
        "shortest": None if short is None else row(*short),
        "long": None if long is None else row(*long),
    }


def main() -> int:
    rng = np.random.default_rng(xc.SEED + 2)
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/common_mode.py")
    payload["n_files"] = dd.n_files
    day0 = xc.day_origin(dd)
    nd = xc.n_days(dd)
    payload["operational_day_start_utc_hour"] = xc.DAY_START_HOUR
    payload["first_day_start"] = day_label(day0, 0)
    payload["n_days"] = nd

    fams = {f: xc.load(dd, f) for f in xc.ALL_FAMS}
    widths = {f: 156 if f in xc.QUBIT_FAMS else len(xc.coupler_pairs(dd, f)) for f in xc.ALL_FAMS}
    daily = {f: xc.daily(fams[f], widths[f], day0, nd) for f in xc.ALL_FAMS}

    # ---- 1. device-wide daily medians and their changes
    dev: dict[str, np.ndarray] = {}
    dev_info: dict[str, Any] = {}
    for f in xc.ALL_FAMS:
        m = daily[f]
        n_series = len(fams[f].z)
        present = np.isfinite(m).sum(axis=1)
        med = np.full(nd, np.nan)
        keep = present >= 0.5 * n_series
        med[keep] = np.nanmedian(m[keep], axis=1)
        dev[f] = np.concatenate([[np.nan], np.diff(med)])
        dev_info[f] = {
            "days_with_device_median": int(np.isfinite(med).sum()),
            "days_with_change": int(np.isfinite(dev[f]).sum()),
            "abs_change_log10_q10_25_50_75_90": xc.q_list(np.abs(dev[f])),
        }
    payload["device_daily"] = {"families": dev_info}
    names = list(xc.ALL_FAMS)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            x, y = dev[a], dev[b]
            rho, n = spearman_pair(x, y)
            if n < 10:
                rows.append({"a": a, "b": b, "common_days": n, "spearman": None})
                continue
            null = np.empty(N_NULL)
            for r in range(N_NULL):
                k = int(rng.uniform(0.1, 0.9) * nd)
                null[r] = spearman_pair(x, np.roll(y, k))[0]
            ok = np.isfinite(x) & np.isfinite(y)
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "common_days": n,
                    "spearman": xc.r6(rho),
                    "ci95_block_bootstrap": block_boot(x[ok], y[ok], rng),
                    "null_q025_q975": [
                        xc.r6(float(np.nanquantile(null, 0.025))),
                        xc.r6(float(np.nanquantile(null, 0.975))),
                    ],
                    "p_shift": xc.r6(
                        float(
                            (1 + np.sum(np.abs(null[np.isfinite(null)]) >= abs(rho)))
                            / (np.isfinite(null).sum() + 1.0)
                        )
                    ),
                }
            )
    tested = [r for r in rows if r["spearman"] is not None]
    for r, flag, q in zip(
        tested,
        xc.bh([r["p_shift"] for r in tested]),
        xc.bh_adjusted([r["p_shift"] for r in tested]),
        strict=True,
    ):
        r["bh_reject_q05"] = flag
        r["bh_q"] = q
    payload["device_daily"]["pairs"] = rows
    payload["device_daily"]["bh_family_size"] = len(tested)
    # days on which several families jump together
    zjump = {}
    for f in names:
        d = dev[f]
        ok = np.isfinite(d)
        mad = 1.4826 * np.median(np.abs(d[ok] - np.median(d[ok])))
        zjump[f] = np.where(ok, (d - np.median(d[ok])) / mad, np.nan)
    stack = np.column_stack([zjump[f] for f in names])
    big = np.abs(stack) > JUMP_SD
    n_big = big.sum(axis=1)
    n_obs = np.isfinite(stack).sum(axis=1)
    order = np.argsort(-n_big)
    joint_days = []
    for d in order[:12]:
        if n_big[d] < 3:
            break
        joint_days.append(
            {
                "day_start": day_label(day0, int(d)),
                "families_jumping": [names[k] for k in np.flatnonzero(big[d])],
                "signed_robust_z": {
                    names[k]: xc.r6(float(stack[d, k])) for k in np.flatnonzero(big[d])
                },
                "families_observed": int(n_obs[d]),
            }
        )
    # null for the count of days with >= 3 families jumping: shift each family independently
    obs3 = int(np.sum(n_big >= 3))
    null3 = np.empty(N_NULL)
    for r in range(N_NULL):
        sh = np.column_stack(
            [np.roll(big[:, k], int(rng.uniform(0.1, 0.9) * nd)) for k in range(len(names))]
        )
        null3[r] = np.sum(sh.sum(axis=1) >= 3)
    payload["device_daily"]["joint_jumps"] = {
        "threshold_robust_sd": JUMP_SD,
        "days_with_ge3_families_jumping": obs3,
        "null_mean": xc.r6(float(null3.mean())),
        "null_q95": xc.r6(float(np.quantile(null3, 0.95))),
        "p_shift": xc.r6(float((1 + np.sum(null3 >= obs3)) / (N_NULL + 1.0))),
        "days": joint_days,
    }

    # ---- 2. common-mode share of the residual variance, and 3. variograms
    shares: dict[str, Any] = {}
    vgs: dict[str, Any] = {}
    res_all: dict[str, xr.Resid] = {}
    for f in names:
        res = xr.build(fams[f], widths[f])
        res_all[f] = res
        ok = np.isfinite(res.r) & np.isfinite(res.r_cm)
        r, rc = res.r[ok], res.r_cm[ok]

        def mad(x: np.ndarray) -> float:
            return float(1.4826 * np.median(np.abs(x - np.median(x))))

        shares[f] = {
            "events": int(ok.sum()),
            "share_plain": xc.r6(1.0 - float(np.var(rc)) / float(np.var(r))),
            "share_robust": xc.r6(1.0 - (mad(rc) / mad(r)) ** 2),
        }
        # per-entity series in log10 units, and the device series of entity-centred values
        ent_series = [
            ddload.Series(entity=int(e), t_ms=t, file_idx=fi, y=z)
            for e, t, fi, z in zip(
                fams[f].entity, fams[f].t_ms, fams[f].file_idx, fams[f].z, strict=True
            )
        ]
        vg_e = ddload.variogram(ent_series, transform="none")
        centred = res.z.copy()
        for e in np.flatnonzero(res.count > 0):
            sl = slice(res.base[e], res.base[e] + res.count[e])
            centred[sl] = res.z[sl] - np.median(res.z[sl])
        n_series = len(fams[f].z)
        rt, rv, rn = [], [], []
        for k in np.unique(res.round_id):
            sel = res.round_id == k
            if sel.sum() >= 0.5 * n_series:
                rt.append(float(np.median(res.t[sel])))
                rv.append(float(np.median(centred[sel])))
                rn.append(int(sel.sum()))
        dev_series = ddload.Series(
            entity=0,
            t_ms=np.array(rt),
            file_idx=np.zeros(len(rt), dtype=np.int64),
            y=np.array(rv),
        )
        vg_d = ddload.variogram([dev_series], transform="none")
        n_med = float(np.median(rn)) if rn else math.nan
        vgs[f] = {
            "matched_bins": matched_bins(vg_e, vg_d),
            "device_rounds": len(rt),
            "entities_per_device_round_median": n_med,
            "independent_noise_prediction_pi_over_2N": xc.r6(math.pi / 2.0 / n_med) if rn else None,
            "per_entity_bins": vg_e["bins"],
            "device_bins": vg_d["bins"],
        }
    payload["common_mode_share"] = shares
    payload["variograms"] = vgs

    # ---- 4. day-aligned change matrix (qubit view)
    out_cm: dict[str, Any] = {}
    for label in ("raw", "cm_removed"):
        cols = []
        for f in names:
            res = res_all[f]
            val = res.r if label == "raw" else res.r_cm
            mat = np.full((nd, widths[f]), np.nan)
            d = xc.day_index(res.t, day0)
            ok = np.isfinite(val) & (d >= 0) & (d < nd)
            # median per (day, entity): sort by key, split
            key = d[ok] * widths[f] + res.ent[ok]
            v = val[ok]
            order = np.argsort(key, kind="stable")
            key, v = key[order], v[order]
            bounds = np.flatnonzero(np.diff(key)) + 1
            for kk, vv in zip(np.split(key, bounds), np.split(v, bounds), strict=True):
                mat[int(kk[0]) // widths[f], int(kk[0]) % widths[f]] = np.median(vv)
            if f in xc.COUPLER_FAMS:
                mat = xc.to_qubits(mat, xc.coupler_pairs(dd, f))
            cols.append(mat)
        cube = np.stack(cols, axis=2)  # (nd, 156, n_fam)
        flat = cube.reshape(-1, len(names))
        z = np.column_stack([normal_scores_col(flat[:, k]) for k in range(len(names))])
        c = pairwise_corr(z)
        w, v = eig_desc(c)
        null_w = np.empty((N_PCA_NULL, len(names)))
        null_c = np.empty((N_PCA_NULL, len(names), len(names)))
        for r in range(N_PCA_NULL):
            sh = np.empty_like(cube)
            for k in range(len(names)):
                offs = (rng.uniform(0.1, 0.9, 156) * nd).astype(int)
                for q in range(156):
                    sh[:, q, k] = np.roll(cube[:, q, k], offs[q])
            zs = np.column_stack(
                [normal_scores_col(sh.reshape(-1, len(names))[:, k]) for k in range(len(names))]
            )
            cs = pairwise_corr(zs)
            null_c[r] = cs
            null_w[r] = eig_desc(cs)[0]
        view = [f if f in xc.QUBIT_FAMS else f"adj_{f}" for f in names]
        pair_rows = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                owner = xc.pair_owner(view[i], view[j])
                ok = np.isfinite(z[:, i]) & np.isfinite(z[:, j])
                row: dict[str, Any] = {
                    "a": view[i],
                    "b": view[j],
                    "owner": owner,
                    "qubit_days": int(ok.sum()),
                    "r": xc.r6(float(c[i, j])),
                }
                if owner == "07" or (owner == "02" and {view[i], view[j]} == {"T1", "T2"}):
                    nul = null_c[:, i, j]
                    row["null_q025_q975"] = [
                        xc.r6(float(np.quantile(nul, 0.025))),
                        xc.r6(float(np.quantile(nul, 0.975))),
                    ]
                    row["p_shift"] = xc.r6(
                        float(
                            (1 + np.sum(np.abs(nul - nul.mean()) >= abs(c[i, j] - nul.mean())))
                            / (N_PCA_NULL + 1.0)
                        )
                    )
                pair_rows.append(row)
        mine = [r for r in pair_rows if r["owner"] == "07"]
        for r, flag, q in zip(
            mine,
            xc.bh([r["p_shift"] for r in mine]),
            xc.bh_adjusted([r["p_shift"] for r in mine]),
            strict=True,
        ):
            r["bh_reject_q05"] = flag
            r["bh_q"] = q
        comps = []
        for k in range(4):
            comps.append(
                {
                    "component": k + 1,
                    "eigenvalue": xc.r6(float(w[k])),
                    "variance_share": xc.r6(float(w[k] / w.sum())),
                    "null_q95": xc.r6(float(np.quantile(null_w[:, k], 0.95))),
                    "exceeds_null": bool(w[k] > np.quantile(null_w[:, k], 0.95)),
                    "loadings": {view[i]: xc.r6(float(v[i, k])) for i in range(len(names))},
                }
            )
        out_cm[label] = {
            "fields": view,
            "qubit_days_per_field": {
                view[k]: int(np.isfinite(z[:, k]).sum()) for k in range(len(names))
            },
            "corr": [[xc.r6(float(x)) for x in row] for row in c],
            "pairs": pair_rows,
            "bh_family_size": len(mine),
            "pca": comps,
            "null_reps": N_PCA_NULL,
        }
    payload["change_matrix"] = out_cm
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
