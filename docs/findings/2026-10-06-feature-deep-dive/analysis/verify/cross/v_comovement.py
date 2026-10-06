"""Independent re-computation and stress test of 07 sections 4.2 and 7.2 (co-movement).

Written from ddload only. Residual = log10 value minus the median of the same entity's other
events inside +-W days (leave-one-out), divided by 1.4826 MAD of the entity's residuals, then
pooled normal scores. For each pair: (a) nearest-event matching within 3 h (12 h for zz) as
in the document's 7.2, with a circular-shift null; (b) all pairs within 30 h binned by gap as
in 4.2. Stress tests the document does not run: the level window W (2, 7 and 14 days), a
split at 2026-08-01. If a correlation at short gaps came from shared
level steps, it would shrink when W shrinks (a +-12 h local level is infeasible: sx is daily).

Writes ``results/verify/cross/comovement_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, rankdata

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "cross" / "comovement_check.json"
OFFSET = 1.0 / 8192.0
H = 3.6e6
DAY = 24 * H
SPLIT_MS = np.datetime64("2026-08-01T00:00:00", "ms").astype("int64").astype(float)
BINS = [0.0, 0.5, 2.0, 6.0, 18.0, 30.0]

FIELD = {
    "T1": "q.T1",
    "T2": "q.T2",
    "RO": "q.readout_error",
    "p10": "q.prob_meas0_prep1",
    "sx": "g1.sx.gate_error",
    "init": "q.init_error",
}


def load_qubit_family(dd, name):
    mask = ddload.placeholder_error if name == "sx" else None
    ser = ddload.series(dd, FIELD[name], rule=ddload.MEASURED, mask=mask)
    out = {}
    for s in ser:
        y = np.asarray(s.y, float)
        t = np.asarray(s.t_ms, float)
        if name == "p10":
            z = np.log10(y + OFFSET)
        else:
            k = y > 0
            y, t = y[k], t[k]
            z = np.log10(y)
        if z.size:
            o = np.argsort(t, kind="stable")
            out[int(s.entity)] = (t[o], z[o])
    return out


def load_zz(dd):
    ents = dd.entities("gen.zz")
    ser = ddload.series(dd, "gen.zz", rule=ddload.ASSEMBLY, mask=ddload.zero_value)
    out = {}
    for s in ser:
        y = np.abs(np.asarray(s.y, float))
        k = y > 0
        if k.any():
            a, b = ents[int(s.entity)]
            out[(int(a), int(b))] = (np.asarray(s.t_ms, float)[k], np.log10(y[k]))
    return out


def loo(t, z, half_days):
    w = half_days * DAY
    lo = np.searchsorted(t, t - w, "left")
    hi = np.searchsorted(t, t + w, "right")
    out = np.full(z.size, np.nan)
    for i in range(z.size):
        win = np.concatenate([z[lo[i] : i], z[i + 1 : hi[i]]])
        if win.size >= 3:
            out[i] = np.median(win)
    return out


def day_demean(t, z):
    """Residual against the median of the same entity's OTHER events within +-12 h."""
    lo = np.searchsorted(t, t - 12 * H, "left")
    hi = np.searchsorted(t, t + 12 * H, "right")
    out = np.full(z.size, np.nan)
    for i in range(z.size):
        win = np.concatenate([z[lo[i] : i], z[i + 1 : hi[i]]])
        if win.size >= 2:
            out[i] = np.median(win)
    return out


def residuals(fam, half_days, mode="loo"):
    """Per entity (t, ns-ready residual); normal scores pooled over the family."""
    res = {}
    for e, (t, z) in fam.items():
        level = loo(t, z, half_days) if mode == "loo" else day_demean(t, z)
        r = z - level
        ok = np.isfinite(r)
        if ok.sum() < 5:
            continue
        sc = 1.4826 * np.median(np.abs(r[ok] - np.median(r[ok])))
        if sc <= 0:
            continue
        res[e] = (t, r / sc)
    allr = np.concatenate([v[1] for v in res.values()])
    fin = np.isfinite(allr)
    ns_all = np.full(allr.size, np.nan)
    ns_all[fin] = norm.ppf(rankdata(allr[fin]) / (fin.sum() + 1.0))
    out = {}
    pos = 0
    for e, (t, r) in res.items():
        out[e] = (t, ns_all[pos : pos + r.size])
        pos += r.size
    return out


def to_qubit_view(fam, coupler):
    if not coupler:
        return fam
    per = {}
    for (a, b), (t, r) in fam.items():
        for q in (a, b):
            per.setdefault(q, []).append((t, r))
    out = {}
    for q, lst in per.items():
        t = np.concatenate([x[0] for x in lst])
        r = np.concatenate([x[1] for x in lst])
        o = np.argsort(t, kind="stable")
        out[q] = (t[o], r[o])
    return out


def nearest_match(ea, eb, window_h, shift_rng=None):
    """Each event of ea to the nearest event of eb on the same qubit within the window."""
    xs, ys, ts = [], [], []
    for q, (ta, ra) in ea.items():
        if q not in eb:
            continue
        tb, rb = eb[q]
        if shift_rng is not None:
            k = int(shift_rng.integers(1, rb.size)) if rb.size > 1 else 0
            rb = np.roll(rb, k)
        i = (
            np.clip(np.searchsorted(tb, ta), 1, tb.size - 1)
            if tb.size > 1
            else np.zeros(ta.size, int)
        )
        if tb.size > 1:
            left = np.abs(tb[i - 1] - ta) <= np.abs(tb[i] - ta)
            j = np.where(left, i - 1, i)
        else:
            j = i
        gap = np.abs(tb[j] - ta) / H
        ok = (gap <= window_h) & np.isfinite(ra) & np.isfinite(rb[j])
        xs.append(ra[ok])
        ys.append(rb[j][ok])
        ts.append(ta[ok])
    x, y, t = np.concatenate(xs), np.concatenate(ys), np.concatenate(ts)
    return x, y, t


def corr(x, y):
    if x.size < 5:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def binned(ea, eb, rng, cap=30000):
    out = []
    xs, ys, gs = [], [], []
    for q, (ta, ra) in ea.items():
        if q not in eb:
            continue
        tb, rb = eb[q]
        lo = np.searchsorted(tb, ta - 30 * H, "left")
        hi = np.searchsorted(tb, ta + 30 * H, "right")
        for i in range(ta.size):
            if hi[i] > lo[i] and np.isfinite(ra[i]):
                xs.append(np.full(hi[i] - lo[i], ra[i]))
                ys.append(rb[lo[i] : hi[i]])
                gs.append(np.abs(tb[lo[i] : hi[i]] - ta[i]) / H)
    x, y, g = np.concatenate(xs), np.concatenate(ys), np.concatenate(gs)
    ok = np.isfinite(y)
    x, y, g = x[ok], y[ok], g[ok]
    for k in range(len(BINS) - 1):
        m = (g >= BINS[k]) & (g < BINS[k + 1])
        idx = np.flatnonzero(m)
        n = idx.size
        if n > cap:
            idx = rng.choice(idx, cap, replace=False)
        out.append(
            {"bin_h": [BINS[k], BINS[k + 1]], "pairs": int(n), "r": round(corr(x[idx], y[idx]), 4)}
        )
    return out


def shift_null(ea, eb, window_h, reps, rng, observed):
    vals = []
    for _ in range(reps):
        x, y, _ = nearest_match(ea, eb, window_h, shift_rng=rng)
        vals.append(corr(x, y))
    vals = np.array(vals)
    return {
        "null_mean": round(float(vals.mean()), 4),
        "null_sd": round(float(vals.std()), 4),
        "p_two_sided": float((np.sum(np.abs(vals) >= abs(observed)) + 1) / (reps + 1)),
    }


def main():
    dd = ddload.DD()
    rng = np.random.default_rng(11)
    fam = {k: load_qubit_family(dd, k) for k in ("T1", "T2", "sx", "p10", "RO", "init")}
    result = {"definitions": "see module docstring"}
    # (a) nearest-event matching, base window 7 d
    base = {k: residuals(v, 7) for k, v in fam.items()}
    table = {}
    for a, b in (
        ("sx", "p10"),
        ("sx", "RO"),
        ("T2", "RO"),
        ("T1", "T2"),
        ("T1", "init"),
        ("T2", "init"),
    ):
        ea, eb = base[a], base[b]
        sparse, dense = (
            (a, b)
            if sum(v[1].size for v in ea.values()) <= sum(v[1].size for v in eb.values())
            else (b, a)
        )
        x, y, t = nearest_match(base[sparse], base[dense], 3.0)
        r = corr(x, y)
        row = {"sparser": sparse, "n": int(x.size), "r": round(r, 4)}
        if (a, b) in (("sx", "p10"), ("T2", "RO")):
            row["shift_null"] = shift_null(base[sparse], base[dense], 3.0, 100, rng, r)
        pre = t < SPLIT_MS
        row["r_before_0801"] = round(corr(x[pre], y[pre]), 4) if pre.sum() > 5 else None
        row["n_before_0801"] = int(pre.sum())
        row["r_from_0801"] = round(corr(x[~pre], y[~pre]), 4)
        table[f"{a}-{b}"] = row
    result["nearest_within_3h_W7d"] = table
    # (b) gap bins for sx-p10 and T1-init, three window sizes + day-demeaned
    stress = {}
    for label, hd, mode in (("W2d", 2, "loo"), ("W7d", 7, "loo"), ("W14d", 14, "loo")):
        res = {}
        for k in ("sx", "p10"):
            res[k] = residuals(fam[k], hd, mode)
        stress[label] = {"sx-p10": binned(res["sx"], res["p10"], rng)}
    result["gap_bins_stress_sx_p10"] = stress
    # init-T1 bins (weak pair) W7
    result["gap_bins_W7d_T1_init"] = binned(base["T1"], base["init"], rng)
    result["gap_bins_W7d_T2_init"] = binned(base["T2"], base["init"], rng)
    result["gap_bins_W7d_T2_RO"] = binned(base["T2"], base["RO"], rng)
    # (c) zz against RO, nearest within 12 h, coupler attached to both qubits
    zz = load_zz(dd)
    zr = to_qubit_view(residuals(zz, 7), True)
    # per coupler residual attached to both qubits: matched events count
    x, y, t = nearest_match(zr, base["RO"], 12.0)
    r = corr(x, y)
    result["zz_RO_nearest_12h"] = {
        "n": int(x.size),
        "r": round(r, 4),
        "note": "attached to both qubits, as in the document; n counts event-qubit pairs",
    }
    # zz event-time structure: share of zz events whose stamp equals a file time
    ft = dd.file_ms
    stamped = np.concatenate([v[0] for v in zz.values()])
    result["zz_events_total"] = int(stamped.size)
    result["zz_event_time_is_file_time_share"] = round(float(np.isin(stamped, ft).mean()), 4)
    payload = ddload.result_header("verify/cross", "analysis/verify/cross/v_comovement.py")
    payload.update(result)
    ddload.write_json(OUT, payload)
    print(table)
    print(stress)
    print(result["zz_RO_nearest_12h"])


if __name__ == "__main__":
    main()
