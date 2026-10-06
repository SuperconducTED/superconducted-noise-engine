"""Within-entity co-movement of the non-persistent components of two families on one qubit.

For every pair of families this scope owns (23 pairs, see ``xcommon.pair_owner``) plus two
positive controls owned elsewhere (``T1``-``T2``, owner 02, and ``RO``-``p10``, owner 03, an
arithmetic link), events of the sparser family A are paired with events of family B on the
same qubit (a coupler event is attached to both of its qubits). Statistics are Pearson
correlations of the pooled normal scores of the standardized residuals (``xresid``):

1. ``nearest``: each A event with the nearest B event within 3 h (12 h when ``zz`` is
   involved, because ``zz`` carries a file time, not a measurement time). Raw residuals, and
   residuals with each family's round common mode removed. Null: 1,000 circular shifts of
   B's events within each entity. Interval: 2,000-replicate cluster bootstrap over qubits.
   Nonlinear check: plug-in mutual information on 8 x 8 quantile bins against 200 shifts.
   Benjamini-Hochberg at 0.05 over the 23 pairs, separately for each statistic.
2. ``by_gap``: every A-B pair within 30 h, binned by the time between the two measurements
   (0-0.5, 0.5-2, 2-6, 6-18, 18-30 h), with a 200-shift null per bin. A shared fast physical
   fluctuation predicts a correlation that is largest at the shortest gaps and decays; purely
   independent estimation noise predicts zero at every gap.
3. Readout shot-noise ceiling: the share of each readout family's residual variance that
   binomial shot noise (4,096 shots) explains, and the implied ceiling on any correlation.
4. Period split: the nearest-pair correlation before and after 2026-08-01 (archive coverage
   changed when historical fetches began).

Writes ``results/cross/comovement.json``.
"""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc
import xresid as xr

OUT = xc.RESULTS / "comovement.json"
N_NULL = 1000
N_NULL_MI = 200
N_NULL_GAP = 200
N_BOOT = 2000
GAP_EDGES_H = (0.0, 0.5, 2.0, 6.0, 18.0, 30.0)
# Gap bins of the dense pairs (readout, zz) hold up to millions of pairs; each bin is capped at
# a seeded random subsample of this size (``pairs`` vs ``pairs_used`` in the JSON).
GAP_CAP = 30_000
PERIOD_CUT_MS = 1_785_542_400_000.0  # 2026-08-01T00:00:00Z
SHOTS = 4096.0

MINE = [
    ("T1", "init"),
    ("T2", "RO"),
    ("T2", "p01"),
    ("T2", "p10"),
    ("T2", "init"),
    ("T2", "m2"),
    ("sx", "RO"),
    ("sx", "p01"),
    ("sx", "p10"),
    ("sx", "init"),
    ("sx", "m2"),
    ("cz", "init"),
    ("cz", "m2"),
    ("rzz", "init"),
    ("rzz", "m2"),
    ("zz", "T1"),
    ("zz", "T2"),
    ("zz", "sx"),
    ("zz", "RO"),
    ("zz", "p01"),
    ("zz", "p10"),
    ("zz", "init"),
    ("zz", "m2"),
]
CONTROLS = [("T1", "T2"), ("RO", "p10")]


def p_two_sided(obs: float, null: np.ndarray) -> float:
    null = null[np.isfinite(null)]
    if not np.isfinite(obs) or null.size == 0:
        return math.nan
    return float((1 + np.sum(np.abs(null) >= abs(obs))) / (null.size + 1.0))


def shot_share(dd: ddload.DD, res: xr.Resid) -> dict[str, Any]:
    """Median over entities of (median shot variance of z) / (robust residual variance)."""
    p01 = np.array(dd.v("q.prob_meas1_prep0"), dtype=np.float64)
    p10 = np.array(dd.v("q.prob_meas0_prep1"), dtype=np.float64)
    a, b = p01[res.f, res.ent], p10[res.f, res.ent]
    ln10 = math.log(10.0)
    if res.name == "RO":
        y = 10.0**res.z
        var_z = (a * (1 - a) + b * (1 - b)) / (4.0 * SHOTS) / (y * ln10) ** 2
    else:
        p = a if res.name == "p01" else b
        var_z = p * (1 - p) / SHOTS / ((p + xc.P_OFFSET) * ln10) ** 2
    shares = []
    for e in np.flatnonzero(res.count > 0):
        sl = slice(res.base[e], res.base[e] + res.count[e])
        s2 = res.scale[e] ** 2
        if np.isfinite(s2) and s2 > 0:
            shares.append(float(np.nanmedian(var_z[sl])) / s2)
    sh = np.array(shares)
    return {
        "entities": int(sh.size),
        "shot_share_of_residual_variance_q10_25_50_75_90": xc.q_list(sh),
        "correlation_ceiling_at_median_share": xc.r6(
            math.sqrt(max(0.0, 1.0 - float(np.median(sh))))
        ),
    }


def analyse_pair(
    a_name: str,
    b_name: str,
    res: dict[str, xr.Resid],
    att: dict[str, list[np.ndarray]],
    rng: np.random.Generator,
) -> dict[str, Any]:
    fa, fb = res[a_name], res[b_name]
    window_h = 12.0 if "zz" in (a_name, b_name) else 3.0
    near = xr.match(fa, att[a_name], fb, att[b_name], window_h * 3.6e6, nearest=True)
    row: dict[str, Any] = {
        "anchor": a_name,
        "other": b_name,
        "owner": xc.pair_owner(
            "adj_" + a_name if a_name in xc.COUPLER_FAMS else a_name,
            "adj_" + b_name if b_name in xc.COUPLER_FAMS else b_name,
        ),
        "window_h": window_h,
        "nearest_pairs": int(near["i"].size),
        "nearest_qubits": int(np.unique(near["q"]).size),
        "nearest_abs_gap_h_q10_25_50_75_90": xc.q_list(np.abs(near["gap_h"])),
    }
    for label, xa_all, xb_all in (("raw", fa.ns, fb.ns), ("cm_removed", fa.ns_cm, fb.ns_cm)):
        xa, xb = xa_all[near["i"]], xb_all[near["j"]]
        obs = xr.corr(xa, xb)
        null = np.array(
            [xr.corr(xa, xb_all[xr.shifted(fb, near["j"], rng)]) for _ in range(N_NULL)]
        )
        mi = xr.binned_mi(xa, xb)
        mi_null = np.array(
            [xr.binned_mi(xa, xb_all[xr.shifted(fb, near["j"], rng)]) for _ in range(N_NULL_MI)]
        )
        early = fa.t[near["i"]] < PERIOD_CUT_MS
        row[label] = {
            "n": int(np.sum(np.isfinite(xa) & np.isfinite(xb))),
            "r": xc.r6(obs),
            "r_ci95_cluster_bootstrap": xr.cluster_boot_corr(xa, xb, near["q"], rng, N_BOOT),
            "null_mean": xc.r6(float(np.nanmean(null))),
            "null_q025_q975": [
                xc.r6(float(np.nanquantile(null, 0.025))),
                xc.r6(float(np.nanquantile(null, 0.975))),
            ],
            "p_shift": xc.r6(p_two_sided(obs - float(np.nanmean(null)), null - np.nanmean(null))),
            "mi_nats": xc.r6(mi),
            "mi_null_mean": xc.r6(float(np.nanmean(mi_null))),
            "mi_excess": xc.r6(mi - float(np.nanmean(mi_null))),
            "mi_p_shift": xc.r6(float((1 + np.sum(mi_null >= mi)) / (N_NULL_MI + 1.0))),
            "r_before_2026_08_01": xc.r6(xr.corr(xa[early], xb[early])),
            "n_before_2026_08_01": int(np.sum(early & np.isfinite(xa) & np.isfinite(xb))),
            "r_from_2026_08_01": xc.r6(xr.corr(xa[~early], xb[~early])),
            "n_from_2026_08_01": int(np.sum(~early & np.isfinite(xa) & np.isfinite(xb))),
        }
    allp = xr.match(fa, att[a_name], fb, att[b_name], GAP_EDGES_H[-1] * 3.6e6, nearest=False)
    ag = np.abs(allp["gap_h"])
    gap_rows = []
    for lo, hi in itertools.pairwise(GAP_EDGES_H):
        sel = (ag >= lo) & (ag < hi)
        cell: dict[str, Any] = {"gap_h_lo": lo, "gap_h_hi": hi, "pairs": int(sel.sum())}
        idx = np.flatnonzero(sel)
        if idx.size > GAP_CAP:
            idx = np.sort(rng.choice(idx, GAP_CAP, replace=False))
        cell["pairs_used"] = int(idx.size)
        if idx.size >= 100:
            i, j = allp["i"][idx], allp["j"][idx]
            for label, xa_all, xb_all in (
                ("raw", fa.ns, fb.ns),
                ("cm_removed", fa.ns_cm, fb.ns_cm),
            ):
                obs = xr.corr(xa_all[i], xb_all[j])
                null = np.array(
                    [xr.corr(xa_all[i], xb_all[xr.shifted(fb, j, rng)]) for _ in range(N_NULL_GAP)]
                )
                cell[label] = {
                    "r": xc.r6(obs),
                    "null_q025_q975": [
                        xc.r6(float(np.nanquantile(null, 0.025))),
                        xc.r6(float(np.nanquantile(null, 0.975))),
                    ],
                    "p_shift": xc.r6(
                        p_two_sided(obs - float(np.nanmean(null)), null - np.nanmean(null))
                    ),
                }
        gap_rows.append(cell)
    row["by_gap"] = gap_rows
    return row


def main() -> int:
    rng = np.random.default_rng(xc.SEED + 1)
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/comovement.py")
    payload["n_files"] = dd.n_files
    payload["method"] = {
        "residual": "log10 value minus the median of the same entity's other events within "
        "+-7 days, divided by 1.4826 x MAD of the entity's residuals",
        "common_mode": "median residual over entities in the family's round (stamps split at "
        f"gaps > 15 min), defined when >= {xr.MIN_ROUND} entities were re-measured",
        "statistic": "Pearson correlation of pooled normal scores of the residuals",
        "null": "circular shift of B's events within each entity, offset uniform on 10% to 90% "
        "of its event count",
        "nearest_null_reps": N_NULL,
        "mi_null_reps": N_NULL_MI,
        "gap_null_reps": N_NULL_GAP,
        "gap_bin_cap_pairs": GAP_CAP,
        "bootstrap_reps": N_BOOT,
        "bh_family_size": len(MINE),
    }
    res: dict[str, xr.Resid] = {}
    att: dict[str, list[np.ndarray]] = {}
    fam_info: dict[str, Any] = {}
    for f in xc.ALL_FAMS:
        fam = xc.load(dd, f)
        width = 156 if f in xc.QUBIT_FAMS else len(xc.coupler_pairs(dd, f))
        res[f] = xr.build(fam, width)
        att[f] = xr.qubit_events(res[f], None if f in xc.QUBIT_FAMS else xc.coupler_pairs(dd, f))
        r = res[f]
        n_rounds = int(r.round_id.max()) + 1
        rounds_cm = int(np.unique(r.round_id[np.isfinite(r.r_cm)]).size)
        fam_info[f] = {
            "events": int(r.t.size),
            "events_with_residual": int(np.isfinite(r.r).sum()),
            "events_with_cm_residual": int(np.isfinite(r.r_cm).sum()),
            "rounds": n_rounds,
            "rounds_with_common_mode": rounds_cm,
        }
    payload["families"] = fam_info
    payload["readout_shot_noise"] = {f: shot_share(dd, res[f]) for f in ("RO", "p01", "p10")}

    rows = []
    for a, b in MINE + CONTROLS:
        med_a = float(np.median(res[a].count[res[a].count > 0]))
        med_b = float(np.median(res[b].count[res[b].count > 0]))
        anchor, other = (a, b) if med_a <= med_b else (b, a)
        row = analyse_pair(anchor, other, res, att, rng)
        row["control"] = (a, b) in CONTROLS
        rows.append(row)
        print(a, b, row["raw"]["r"], row["cm_removed"]["r"], flush=True)
    mine_rows = [r for r in rows if not r["control"]]
    for label in ("raw", "cm_removed"):
        for stat, key in (("r", "p_shift"), ("mi", "mi_p_shift")):
            ps = [r[label][key] for r in mine_rows]
            ps = [p if p is not None else 1.0 for p in ps]
            for r, flag, q in zip(mine_rows, xc.bh(ps), xc.bh_adjusted(ps), strict=True):
                r[label][f"{stat}_bh_reject_q05"] = flag
                r[label][f"{stat}_bh_q"] = q
    payload["pairs"] = rows
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
