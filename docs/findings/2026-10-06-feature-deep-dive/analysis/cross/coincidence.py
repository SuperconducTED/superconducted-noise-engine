"""Event coincidence: do large deviations of different families hit the same qubit together?

A large deviation is an event whose innovation ``z_k - L_{k-1}`` (causal EWMA, weight chosen on
the whole archive per family, grid 0.05 to 0.60; descriptive, not a forecast) exceeds 3
robust sd (1.4826 x MAD of the entity's innovations). "Adverse" deviations are the subset in
the harmful direction (``T1``, ``T2`` down; every error and ``|zz|`` up). Events are binned into
operational days (from 16:00 UTC); a coupler family flags a qubit-day when any adjacent coupler
does.

For each pair (A, B): ``c`` = qubit-days observed for both with both flagged, same day, and
next day (A on day d, B on day d + 1). Two nulls, 1,000 replicates each:

- ``time``: B's day series circularly shifted per qubit (offset 10% to 90% of the days);
  lift_time = c / mean null. Tests whether same-day alignment matters at all.
- ``qubit``: B's flags permuted among the qubits observed for B on the same day, which keeps
  each day's device-wide flag count; lift_qubit = c / mean null. Excess over this null is
  coincidence local to a qubit, beyond device-wide bad days.

Interval: 2,000-replicate cluster bootstrap over qubits of ``sum c / sum null mean``. BH at 0.05
over this scope's 23 pairs, per null and per alignment. Multi-family: qubit-days with >= 3
units flagged, against both nulls applied to every unit independently; the units are the 11
families (inflated by within-family links) and 7 physical groups (coherence = T1, T2;
readout = RO, p01, p10; init; m2; sx; two-qubit = cz, rzz; zz), a group flagged when any
member is.

Writes ``results/cross/coincidence.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc
from comovement import CONTROLS, MINE
from leadlag import ewma_innov, fit_alpha

OUT = xc.RESULTS / "coincidence.json"
N_NULL = 1000
N_BOOT = 2000
SD = 3.0
PERIOD_CUT_MS = 1_785_542_400_000.0  # 2026-08-01T00:00:00Z
BAD_UP = {"T1": False, "T2": False}


def flags(dd: ddload.DD, fam: xc.Fam, alpha: float, day0: float, nd: int) -> dict[str, np.ndarray]:
    width = 156 if fam.name in xc.QUBIT_FAMS else len(xc.coupler_pairs(dd, fam.name))
    obs = np.zeros((nd, width), dtype=bool)
    big = np.zeros((nd, width), dtype=bool)
    adv = np.zeros((nd, width), dtype=bool)
    up = BAD_UP.get(fam.name, True)
    for e, t, z in zip(fam.entity, fam.t_ms, fam.z, strict=True):
        inn = ewma_innov(z, alpha)
        ok = np.isfinite(inn)
        if ok.sum() < 10:
            continue
        s = 1.4826 * np.median(np.abs(inn[ok] - np.median(inn[ok])))
        if s <= 0:
            continue
        d = xc.day_index(t, day0)
        inside = ok & (d >= 0) & (d < nd)
        dd_, ii = d[inside], inn[inside] / s
        obs[dd_, e] = True
        np.logical_or.at(big[:, e], dd_, np.abs(ii) > SD)
        np.logical_or.at(adv[:, e], dd_, (ii > SD) if up else (ii < -SD))
    if fam.name in xc.COUPLER_FAMS:
        adj = xc.adjacency(xc.coupler_pairs(dd, fam.name))
        q_obs = np.zeros((nd, 156), dtype=bool)
        q_big = np.zeros((nd, 156), dtype=bool)
        q_adv = np.zeros((nd, 156), dtype=bool)
        for q in range(156):
            if adj[q]:
                q_obs[:, q] = obs[:, adj[q]].any(axis=1)
                q_big[:, q] = big[:, adj[q]].any(axis=1)
                q_adv[:, q] = adv[:, adj[q]].any(axis=1)
        obs, big, adv = q_obs, q_big, q_adv
    return {"obs": obs, "big": big, "adv": adv}


def shift_time(m: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return shift_time_both(m, m, rng)[0]


def shift_time_both(
    m1: np.ndarray, m2: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Circularly shift two (days, qubits) arrays per qubit with the SAME offsets."""
    nd = m1.shape[0]
    offs = (rng.uniform(0.1, 0.9, m1.shape[1]) * nd).astype(int)
    idx = (np.arange(nd)[:, None] + offs[None, :]) % nd
    cols = np.arange(m1.shape[1])[None, :]
    return m1[idx, cols], m2[idx, cols]


def permute_qubits(flag: np.ndarray, obs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    nd, nq = flag.shape
    n_obs = obs.sum(axis=1)
    obs_sorted = np.argsort(~obs, axis=1, kind="stable")
    keys = rng.random((nd, nq))
    keys[~obs] = np.inf
    rand_order = np.argsort(keys, axis=1)
    cols = np.arange(nq)[None, :] < n_obs[:, None]
    rows = np.broadcast_to(np.arange(nd)[:, None], (nd, nq))
    out = np.zeros_like(flag)
    out[rows[cols], obs_sorted[cols]] = flag[rows[cols], rand_order[cols]]
    return out


def lag_b(m: np.ndarray, lag: int) -> np.ndarray:
    """B aligned so that row d holds B's day d + lag (False past the end)."""
    if lag == 0:
        return m
    out = np.zeros_like(m)
    out[:-lag] = m[lag:]
    return out


def count_per_qubit(fa: np.ndarray, oa: np.ndarray, fb: np.ndarray, ob: np.ndarray) -> np.ndarray:
    out: np.ndarray = (fa & oa & fb & ob).sum(axis=0)
    return out


def pair_stats(
    a: dict[str, np.ndarray],
    b: dict[str, np.ndarray],
    key: str,
    lag: int,
    early: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    fa, oa = a[key], a["obs"]
    fb, ob = lag_b(b[key], lag), lag_b(b["obs"], lag)
    both = oa & ob
    c_q = count_per_qubit(fa, oa, fb, ob)
    c = int(c_q.sum())
    null_t = np.zeros((N_NULL, 156))
    null_q = np.zeros((N_NULL, 156))
    null_t_early = np.zeros(N_NULL)
    for r in range(N_NULL):
        sf, so = shift_time_both(b[key], b["obs"], rng)
        null_t[r] = count_per_qubit(fa, oa, lag_b(sf, lag), lag_b(so, lag))
        null_t_early[r] = float((fa & oa & lag_b(sf, lag) & lag_b(so, lag))[early].sum())
        pf = permute_qubits(b[key], b["obs"], rng)
        null_q[r] = count_per_qubit(fa, oa, lag_b(pf, lag), ob)
    out: dict[str, Any] = {
        "qubit_days_both_observed": int(both.sum()),
        "a_flag_rate": xc.r6(float((fa & both).sum() / max(both.sum(), 1))),
        "b_flag_rate": xc.r6(float((fb & both).sum() / max(both.sum(), 1))),
        "both_flagged": c,
    }
    for label, nul in (("time", null_t), ("qubit", null_q)):
        tot = nul.sum(axis=1)
        mean = float(tot.mean())
        per_q_mean = nul.mean(axis=0)
        boots = np.empty(N_BOOT)
        for k in range(N_BOOT):
            w = np.bincount(rng.integers(0, 156, 156), minlength=156)
            den = float(w @ per_q_mean)
            boots[k] = float(w @ c_q) / den if den > 0 else np.nan
        out[f"null_{label}_mean"] = xc.r6(mean)
        out[f"lift_{label}"] = xc.r6(c / mean) if mean > 0 else None
        out[f"lift_{label}_ci95"] = [
            xc.r6(float(np.nanquantile(boots, 0.025))),
            xc.r6(float(np.nanquantile(boots, 0.975))),
        ]
        out[f"p_{label}_greater"] = xc.r6(float((1 + np.sum(tot >= c)) / (N_NULL + 1.0)))
    c_early = int((fa & oa & fb & ob)[early].sum())
    out["both_flagged_before_2026_08_01"] = c_early
    out["lift_time_before_2026_08_01"] = (
        xc.r6(c_early / float(null_t_early.mean())) if null_t_early.mean() > 0 else None
    )
    late_mean = float(null_t.sum(axis=1).mean() - null_t_early.mean())
    out["lift_time_from_2026_08_01"] = xc.r6((c - c_early) / late_mean) if late_mean > 0 else None
    return out


GROUPS = {
    "coherence": ["T1", "T2"],
    "readout": ["RO", "p01", "p10"],
    "init": ["init"],
    "m2": ["m2"],
    "sx": ["sx"],
    "twoq": ["cz", "rzz"],
    "zz": ["zz"],
}


def multi_count(
    units: dict[str, tuple[np.ndarray, np.ndarray]], rng: np.random.Generator
) -> dict[str, Any]:
    """Qubit-days with >= 3 units flagged, against the time-shift and qubit-permutation nulls."""
    names = list(units)
    f_stack = np.stack([units[u][0] for u in names])
    o_stack = np.stack([units[u][1] for u in names])
    n_flag = f_stack.sum(axis=0)
    obs_ge3 = int(np.sum(n_flag >= 3))
    null_t = np.empty(N_NULL)
    null_q = np.empty(N_NULL)
    for r in range(N_NULL):
        st = np.stack([shift_time(units[u][0], rng) for u in names])
        null_t[r] = np.sum(st.sum(axis=0) >= 3)
        sq = np.stack([permute_qubits(units[u][0], units[u][1], rng) & units[u][1] for u in names])
        null_q[r] = np.sum(sq.sum(axis=0) >= 3)
    return {
        "units": names,
        "qubit_days_any_observed": int(o_stack.any(axis=0).sum()),
        "qubit_days_ge3_units": obs_ge3,
        "null_time_mean": xc.r6(float(null_t.mean())),
        "lift_time": xc.r6(obs_ge3 / float(null_t.mean())) if null_t.mean() > 0 else None,
        "p_time_greater": xc.r6(float((1 + np.sum(null_t >= obs_ge3)) / (N_NULL + 1.0))),
        "null_qubit_mean": xc.r6(float(null_q.mean())),
        "lift_qubit": xc.r6(obs_ge3 / float(null_q.mean())) if null_q.mean() > 0 else None,
        "p_qubit_greater": xc.r6(float((1 + np.sum(null_q >= obs_ge3)) / (N_NULL + 1.0))),
        "distribution_of_units_flagged": np.bincount(n_flag.ravel(), minlength=len(names) + 1)[
            : len(names) + 1
        ].tolist(),
    }


def main() -> int:
    rng = np.random.default_rng(xc.SEED + 4)
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/coincidence.py")
    payload["n_files"] = dd.n_files
    day0 = xc.day_origin(dd)
    nd = xc.n_days(dd)
    days_ms = day0 + np.arange(nd) * xc.MS_PER_DAY
    early = np.broadcast_to((days_ms < PERIOD_CUT_MS)[:, None], (nd, 156))
    fams = {f: xc.load(dd, f) for f in xc.ALL_FAMS}
    alphas = {f: fit_alpha(fams[f], np.inf) for f in xc.ALL_FAMS}
    fl = {f: flags(dd, fams[f], alphas[f], day0, nd) for f in xc.ALL_FAMS}
    payload["alphas_whole_archive"] = alphas
    payload["threshold_robust_sd"] = SD
    payload["families"] = {
        f: {
            "qubit_days_observed": int(fl[f]["obs"].sum()),
            "flag_rate": xc.r6(float(fl[f]["big"].sum() / max(fl[f]["obs"].sum(), 1))),
            "adverse_rate": xc.r6(float(fl[f]["adv"].sum() / max(fl[f]["obs"].sum(), 1))),
        }
        for f in xc.ALL_FAMS
    }
    rows = []
    for a, b in MINE + CONTROLS:
        row: dict[str, Any] = {
            "a": a,
            "b": b,
            "owner": xc.pair_owner(
                "adj_" + a if a in xc.COUPLER_FAMS else a, "adj_" + b if b in xc.COUPLER_FAMS else b
            ),
            "control": (a, b) in CONTROLS,
        }
        for key in ("big", "adv"):
            for lag in (0, 1):
                row[f"{key}_lag{lag}"] = pair_stats(fl[a], fl[b], key, lag, early, rng)
        rows.append(row)
        print(a, b, row["big_lag0"]["lift_time"], row["big_lag0"]["lift_qubit"], flush=True)
    mine = [r for r in rows if not r["control"]]
    for key in ("big_lag0", "big_lag1", "adv_lag0", "adv_lag1"):
        for label in ("time", "qubit"):
            ps = [r[key][f"p_{label}_greater"] for r in mine]
            for r, flag, q in zip(mine, xc.bh(ps), xc.bh_adjusted(ps), strict=True):
                r[key][f"bh_{label}_reject_q05"] = flag
                r[key][f"bh_{label}_q"] = q
    payload["pairs"] = rows
    payload["bh_family_size"] = len(mine)

    # multi-family coincidence: over all 11 families (inflated by the arithmetic and
    # same-experiment links inside a family: RO = (p01 + p10) / 2, T1 and T2 stamped seconds
    # apart), and over 7 physical groups, each flagged when any member is and shifted or
    # permuted as one unit
    multi: dict[str, Any] = {}
    for key in ("big", "adv"):
        units = {f: (fl[f][key] & fl[f]["obs"], fl[f]["obs"]) for f in xc.ALL_FAMS}
        multi[key] = multi_count(units, rng)
        grouped = {}
        for g, members in GROUPS.items():
            flag = np.any([fl[f][key] & fl[f]["obs"] for f in members], axis=0)
            obs = np.any([fl[f]["obs"] for f in members], axis=0)
            grouped[g] = (flag, obs)
        multi[f"{key}_grouped"] = multi_count(grouped, rng)
    payload["multi_family"] = multi
    payload["multi_family_groups"] = GROUPS
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
