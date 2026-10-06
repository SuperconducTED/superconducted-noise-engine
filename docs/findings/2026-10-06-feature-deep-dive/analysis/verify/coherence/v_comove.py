"""Independent test of the T1/T2 co-movement and dip claims of 02-coherence.md.

Written from ddload only. The level of an event is defined differently from the document's
(median of the same qubit's other events within +-7 days, not the 14 nearest neighbours), so
agreement is not a copy of the owner's rule. Computes the same-round deviation correlation,
the first-difference correlation (no level needed), placebo correlations (T2 of the next round;
T2 of another qubit in the same round), the correlation after removing each round's median
deviation, per-period splits, the dip rate and the expected number of consecutive dip pairs
under exchangeability.

Writes ``results/verify/coherence/comove_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "coherence" / "comove_check.json"
DAY = 24 * 3.6e6
SEED = 20261006
SPLIT_QUIET_END = np.datetime64("2026-05-28T00:00:00", "ms").astype("int64").astype(float)
SPLIT_0628 = np.datetime64("2026-06-28T00:00:00", "ms").astype("int64").astype(float)
SPLIT_0805 = 1785973531000.0


def level_days(t, z, w_days=7.0):
    out = np.full(z.size, np.nan)
    for i in range(z.size):
        m = (np.abs(t - t[i]) <= w_days * DAY) & (np.arange(z.size) != i)
        if m.sum() >= 8:
            out[i] = np.median(z[m])
    return out


def level_idx(z, half=7, min_n=8):
    out = np.full(z.size, np.nan)
    for i in range(z.size):
        w = np.r_[z[max(0, i - half) : i], z[i + 1 : i + half + 1]]
        if w.size >= min_n:
            out[i] = np.median(w)
    return out


def corr_pair(a, b):
    return float(np.corrcoef(a, b)[0, 1]), float(spearmanr(a, b).statistic)


def main():
    dd = ddload.DD()
    out = {
        "header": ddload.result_header("verify/coherence", "analysis/verify/coherence/v_comove.py")
    }
    s1 = ddload.series(dd, "q.T1", rule=ddload.MEASURED)
    s2 = ddload.series(dd, "q.T2", rule=ddload.MEASURED)
    v1, d1 = np.asarray(dd.v("q.T1")), np.asarray(dd.d("q.T1"))
    # paired events per qubit: T2 event with T1 stamped within 1 h in the same file
    rows = []  # (entity, t_ms, z1, z2)
    for s in s2:
        e, fi = s.entity, s.file_idx
        t1 = v1[fi, e]
        ok = np.isfinite(t1) & (np.abs(s.t_ms - d1[fi, e]) <= 3.6e6)
        ok[0] = False  # first event predates the archive
        for k in np.flatnonzero(ok):
            rows.append((e, s.t_ms[k], np.log10(t1[k]), np.log10(s.y[k])))
    arr = np.array(rows)
    ent, t, z1, z2 = arr[:, 0].astype(int), arr[:, 1], arr[:, 2], arr[:, 3]
    out["paired_events_used"] = int(arr.shape[0])

    # deviations with two level definitions
    for name, fn in (
        ("level_pm7_days", lambda tt, zz: level_days(tt, zz)),
        ("level_14_nearest_events", lambda tt, zz: level_idx(zz)),
    ):
        dev1 = np.full(z1.size, np.nan)
        dev2 = np.full(z2.size, np.nan)
        for e in np.unique(ent):
            m = np.flatnonzero(ent == e)
            m = m[np.argsort(t[m])]
            if m.size < 20:
                continue
            dev1[m] = z1[m] - fn(t[m], z1[m])
            dev2[m] = z2[m] - fn(t[m], z2[m])
        ok = np.isfinite(dev1) & np.isfinite(dev2)
        p, sp = corr_pair(dev1[ok], dev2[ok])
        res = {"n": int(ok.sum()), "pearson": p, "spearman": sp, "rho_sq": p * p}
        # by period
        for pname, lo, hi in (
            ("quiet_before_0528", -np.inf, SPLIT_QUIET_END),
            ("0528_to_0805", SPLIT_QUIET_END, SPLIT_0805),
            ("after_0805", SPLIT_0805, np.inf),
        ):
            mm = ok & (t >= lo) & (t < hi)
            res[pname] = {"n": int(mm.sum()), "pearson": corr_pair(dev1[mm], dev2[mm])[0]}
        # per-qubit sign
        pos, tot = 0, 0
        for e in np.unique(ent):
            mm = ok & (ent == e)
            if mm.sum() >= 20:
                tot += 1
                pos += int(np.corrcoef(dev1[mm], dev2[mm])[0, 1] > 0)
        res["qubits_positive"] = f"{pos} of {tot}"
        # remove each round's median deviation (device-wide common mode) from both
        order = np.argsort(t)
        ts = t[order]
        new = np.r_[True, np.diff(ts) > 15 * 60_000.0]
        rid = np.empty(t.size, dtype=int)
        rid[order] = np.cumsum(new) - 1
        d1c, d2c = dev1.copy(), dev2.copy()
        for r in np.unique(rid[ok]):
            mm = ok & (rid == r)
            if mm.sum() >= 30:
                d1c[mm] -= np.median(dev1[mm])
                d2c[mm] -= np.median(dev2[mm])
            else:
                d1c[mm] = np.nan
        okc = ok & np.isfinite(d1c)
        res["after_removing_round_median"] = {
            "n": int(okc.sum()),
            "pearson": corr_pair(d1c[okc], d2c[okc])[0],
        }
        # placebo 1: T2 deviation of the same qubit's next paired event
        a, b = [], []
        for e in np.unique(ent):
            m = np.flatnonzero((ent == e) & ok)
            m = m[np.argsort(t[m])]
            if m.size > 1:
                a.append(dev1[m[:-1]])
                b.append(dev2[m[1:]])
        a, b = np.concatenate(a), np.concatenate(b)
        res["placebo_T1_now_vs_T2_next_round"] = {"n": int(a.size), "pearson": corr_pair(a, b)[0]}
        # placebo 2: T1 of one qubit vs T2 of a different, random qubit in the same round
        rng = np.random.default_rng(SEED)
        cs = []
        for _ in range(200):
            xs, ys = [], []
            for r in np.unique(rid[ok]):
                idx = np.flatnonzero(ok & (rid == r))
                if idx.size < 30:
                    continue
                perm = rng.permutation(idx.size)
                xs.append(dev1[idx])
                ys.append(dev2[idx[perm]])
            cs.append(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])
        res["placebo_other_qubit_same_round_mean_pearson"] = float(np.mean(cs))
        out[name] = res

    # first differences of consecutive paired events (no level needed)
    da, db, dt = [], [], []
    for e in np.unique(ent):
        m = np.flatnonzero(ent == e)
        m = m[np.argsort(t[m])]
        if m.size > 2:
            da.append(np.diff(z1[m]))
            db.append(np.diff(z2[m]))
            dt.append(np.diff(t[m]) / 3.6e6)
            # keep period tag
    da, db, dt = np.concatenate(da), np.concatenate(db), np.concatenate(dt)
    tt = np.concatenate(
        [
            t[np.flatnonzero(ent == e)][np.argsort(t[ent == e])][1:]
            for e in np.unique(ent)
            if (ent == e).sum() > 2
        ]
    )
    ok = (dt > 18) & (dt < 30) & (tt >= SPLIT_0628)
    p, sp = corr_pair(da[ok], db[ok])
    out["first_difference_18_30h_from_0628"] = {"n": int(ok.sum()), "pearson": p, "spearman": sp}

    # dips of T1 (factor 2 below the running level, excluding first events)
    for name, fn in (
        ("level_14_nearest_events", lambda tt_, zz: level_idx(zz)),
        ("level_pm7_days", lambda tt_, zz: level_days(tt_, zz)),
    ):
        n_ev, n_dip, qs = 0, 0, set()
        exp_pairs, obs_pairs, n_dip_0628 = 0.0, 0, 0
        exp_pairs_0628, obs_pairs_0628 = 0.0, 0
        for s in s1:
            tt_, zz = s.t_ms[1:], np.log10(s.y[1:])
            if zz.size < 20:
                continue
            dev = zz - fn(tt_, zz)
            okd = np.isfinite(dev)
            dip = okd & (dev <= -np.log10(2.0))
            n_ev += int(okd.sum())
            n_dip += int(dip.sum())
            if n_dip and dip.any():
                qs.add(int(s.entity))
            # expected consecutive dip pairs if dips are exchangeable over the qubit's events
            k, n = int(dip.sum()), int(okd.sum())
            exp_pairs += k * (k - 1) / max(n, 1)
            obs_pairs += int(np.sum(dip[:-1] & dip[1:]))
            late = tt_ >= SPLIT_0628
            kl, nl = int((dip & late).sum()), int((okd & late).sum())
            n_dip_0628 += kl
            if nl > 0:
                exp_pairs_0628 += kl * (kl - 1) / nl
            obs_pairs_0628 += int(np.sum(dip[:-1] & dip[1:] & late[1:]))
        out["dips_" + name] = {
            "events": n_ev,
            "dips": n_dip,
            "qubits_with_dip": len(qs),
            "rate": n_dip / n_ev,
            "consecutive_pairs_observed": obs_pairs,
            "consecutive_pairs_expected_exchangeable": exp_pairs,
            "dips_from_0628": n_dip_0628,
            "pairs_from_0628_observed": obs_pairs_0628,
            "pairs_from_0628_expected": exp_pairs_0628,
        }

    ddload.write_json(OUT, out)
    print("ok")


if __name__ == "__main__":
    main()
