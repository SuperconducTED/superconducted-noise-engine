"""What #125's Arm A rule does in each world, on the archive's real selected qubits. No QPU; laptop; provisional.

Each world says what the device's T1 is at execution, given the pre-registered selection at 03:45 UTC:
  N       the level (all scatter is the reading's own noise)
  F       the archive's next changed reading of that qubit (fast physical scatter, or its nearest proxy)
  S       the reading (the deviation persists to execution)
  M(a,s)  log T1 = (1-a) log reading + a log level + s z, z iid per qubit-day. a = 0.5 is equal accuracy
          (NC-087's tie point). s = 0.289 is 0.37 / z90, the scatter of design section 1.
p_hat ~ Binomial(2048, p_true) / 2048 on the union grid; p from the design's closed form.
Scored exactly as score_arm_a on PR #140 scores a row. Windows: all overlapping runs of 14 consecutive days,
so a pass rate has far fewer independent windows than its denominator; it is descriptive.
"""

import math
import pickle
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

D = pickle.load(open("C:/t135/cache/days.pkl", "rb"))
REC = D["records"]
ND = len(D["days"])
SHOTS = 2048
ND_WIN = 14
SIGMA = 0.37 / stats.norm.ppf(0.9)
print(f"days {ND}, records {len(REC)}, sigma {SIGMA:.4f}")


def p1(tau, t1, e10, e01):
    s = np.exp(-tau / t1)
    return (1.0 - e10) * s + e01 * (1.0 - s)


# Static arrays, one row per (record, delay slot). Slot 0 is tau = 0.
rec = {k: np.array([r[k] for r in REC]) for k in REC[0] if k not in ("stratum", "reading_time")}
is_disc = np.array([r["stratum"] == "discriminating" for r in REC])
n = len(REC)
factors = np.array([0.5, 1.0, 2.0])
taus = np.zeros((n, 7))
taus[:, 1:4] = rec["t1_level"][:, None] * factors
taus[:, 4:7] = rec["t1_reading"][:, None] * factors
ok_next = np.isfinite(rec["t1_next"])
print("records with no next change:", int((~ok_next).sum()))

# A random other qubit's level, for the mis-centred no-information band (same log width as the real one).
rng0 = np.random.default_rng(np.random.SeedSequence(135110701))
other = rng0.permutation(n)
same = rec["qubit"][other] == rec["qubit"]
other[same] = np.roll(other, 1)[same]


def world_truth(world, rng):
    lr, ll = np.log(rec["t1_reading"]), np.log(rec["t1_level"])
    if world == "N":
        return rec["t1_level"], rec["e10_level"], rec["e01_level"]
    if world == "S":
        return rec["t1_reading"], rec["e10_reading"], rec["e01_reading"]
    if world == "F":
        t = np.where(ok_next, rec["t1_next"], rec["t1_level"])
        return (
            t,
            np.where(ok_next, rec["e10_next"], rec["e10_level"]),
            np.where(ok_next, rec["e01_next"], rec["e01_level"]),
        )
    a, s = world
    z = rng.standard_normal(n)
    t = np.exp((1 - a) * lr + a * ll + s * z)
    return (
        t,
        (1 - a) * rec["e10_reading"] + a * rec["e10_level"],
        (1 - a) * rec["e01_reading"] + a * rec["e01_level"],
    )


def simulate(world, rng):
    t_true, e10t, e01t = world_truth(world, rng)
    p_true = p1(taus, t_true[:, None], e10t[:, None], e01t[:, None])
    p_hat = rng.binomial(SHOTS, np.clip(p_true, 0, 1)) / SHOTS
    p_l = p1(taus, rec["t1_level"][:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
    p_r = p1(
        taus, rec["t1_reading"][:, None], rec["e10_reading"][:, None], rec["e01_reading"][:, None]
    )
    d_row = np.abs(p_hat - p_l) - np.abs(p_hat - p_r)
    a = p1(taus, rec["t1_lo"][:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
    b = p1(taus, rec["t1_hi"][:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    se = np.sqrt(np.clip(p_hat * (1 - p_hat), 0, None) / SHOTS)
    cov_nom = (lo <= p_hat) & (p_hat <= hi)
    cov_wid = (lo - se <= p_hat) & (p_hat <= hi + se)
    # same log width, centred on the reading, and on another qubit's level
    ratio_lo, ratio_hi = rec["t1_lo"] / rec["t1_level"], rec["t1_hi"] / rec["t1_level"]
    alt = {}
    for name, centre, e10c, e01c in (
        ("reading_centred", rec["t1_reading"], rec["e10_level"], rec["e01_level"]),
        ("other_qubit", rec["t1_level"][other], rec["e10_level"], rec["e01_level"]),
    ):
        a2 = p1(taus, (centre * ratio_lo)[:, None], e10c[:, None], e01c[:, None])
        b2 = p1(taus, (centre * ratio_hi)[:, None], e10c[:, None], e01c[:, None])
        l2, h2 = np.minimum(a2, b2), np.maximum(a2, b2)
        alt[name] = (l2 - se <= p_hat) & (p_hat <= h2 + se)
        alt[name + "_is"] = (h2 - l2) + 10.0 * (
            np.clip(l2 - p_hat, 0, None) + np.clip(p_hat - h2, 0, None)
        )
    is_real = (hi - lo) + 10.0 * (np.clip(lo - p_hat, 0, None) + np.clip(p_hat - hi, 0, None))
    return {
        "d_row": d_row,
        "cov_nom": cov_nom,
        "cov_wid": cov_wid,
        "width": hi - lo,
        "p_hat": p_hat,
        "alt": alt,
        "is_real": is_real,
    }


days_idx = rec["day"]


def per_day(values, mask):
    """Row-weighted mean per day over rows in mask[record]. values has shape (n, slots)."""
    out = np.zeros(ND)
    cnt = np.zeros(ND)
    v = values[mask]
    dd = days_idx[mask]
    np.add.at(out, dd, v.sum(axis=1))
    np.add.at(cnt, dd, v.shape[1])
    return out / cnt


def windows(x):
    return np.lib.stride_tricks.sliding_window_view(x, ND_WIN)


RES = 2000


def boot_upper(win, block, a, rng, trunc=False):
    """Upper percentile of the circular block bootstrap of the mean, windows x resamples."""
    nb = -(-ND_WIN // block)
    st = rng.integers(0, ND_WIN, (RES, nb))
    i = ((st[:, :, None] + np.arange(block)[None, None, :]) % ND_WIN).reshape(RES, nb * block)
    if trunc:
        i = i[:, :ND_WIN]
    boot = win[:, i].mean(axis=2)
    return np.quantile(boot, 1 - a, axis=1)


def batch_pass(win, q, a=0.05):
    groups = np.array_split(np.arange(ND_WIN), q)
    m = np.stack([win[:, g].mean(axis=1) for g in groups], axis=1)
    t = m.mean(axis=1) / (m.std(axis=1, ddof=1) / math.sqrt(q))
    return t < -stats.t.ppf(1 - a, q - 1)


def acf(x, lag):
    x = x - x.mean()
    return float((x[:-lag] * x[lag:]).sum() / (x * x).sum())


def run_world(world, label, seed):
    rng = np.random.default_rng(seed)
    acc = defaultdict(list)
    acfs = []
    for _ in range(REPS):
        s = simulate(world, rng)
        dd = per_day(s["d_row"], is_disc)
        dc = per_day(s["d_row"], ~is_disc)
        acfs.append((dd.mean(), dd.std(ddof=1), acf(dd, 1), acf(dd, 2), acf(dd, 3), dc.mean()))
        w = windows(dd)
        wc = windows(dc)
        acc["A1_b3_90"].append(boot_upper(w, 3, 0.05, rng) < 0)
        acc["A1_b1_90"].append(boot_upper(w, 1, 0.05, rng) < 0)
        acc["A1_b3_98"].append(boot_upper(w, 3, 0.01, rng) < 0)
        acc["A1_bm3"].append(batch_pass(w, 3))
        acc["A1_bm4"].append(batch_pass(w, 4))
        a3 = wc.mean(axis=1) < 0
        acc["A3"].append(a3)
        # A4 variants: discriminating rows, widened band, with and without tau = 0
        for name, mask, slots in (
            ("A4_all7", is_disc, slice(None)),
            ("A4_no0", is_disc, slice(1, 7)),
            ("A4ctl_no0", ~is_disc, slice(1, 7)),
        ):
            cov = per_day(s["cov_wid"][:, slots].astype(float), mask)
            acc[name].append(windows(cov).mean(axis=1) >= 0.80)
            acc[name + "_val"].append(windows(cov).mean(axis=1))
        acc["cov_tau0"].append(
            np.array([per_day(s["cov_wid"][:, [0]].astype(float), is_disc).mean()])
        )
        acc["cov_nom_no0"].append(
            np.array([per_day(s["cov_nom"][:, 1:7].astype(float), is_disc).mean()])
        )
        for alt in ("reading_centred", "other_qubit"):
            acc["cov_" + alt].append(
                np.array([per_day(s["alt"][alt][:, 1:7].astype(float), is_disc).mean()])
            )
            acc["is_" + alt].append(
                np.array([per_day(s["alt"][alt + "_is"][:, 1:7], is_disc).mean()])
            )
        acc["is_real"].append(np.array([per_day(s["is_real"][:, 1:7], is_disc).mean()]))
        acc["width_no0"].append(np.array([per_day(s["width"][:, 1:7], is_disc).mean()]))
        # the rule as written: A1 and A2 (identical without a sweep), A3, A4 on all rows
        acc["S1_written"].append(acc["A1_b3_90"][-1] & a3 & acc["A4_all7"][-1])
        acc["S1_tau0_out"].append(acc["A1_b3_90"][-1] & a3 & acc["A4_no0"][-1])
    a = np.array(acfs)
    res = {k: float(np.mean(np.concatenate(v))) for k, v in acc.items()}
    res.update(
        mean_D=a[:, 0].mean(),
        sd_D=a[:, 1].mean(),
        acf1=a[:, 2].mean(),
        acf2=a[:, 3].mean(),
        acf3=a[:, 4].mean(),
        mean_Dctl=a[:, 5].mean(),
    )
    return res


if __name__ == "__main__":
    REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(f"reps {REPS}")
    kids = iter(np.random.SeedSequence(135110702).spawn(200))
    worlds = [
        ("N", "N level is true"),
        ("F", "F next reading"),
        ("S", "S reading persists"),
        ((0.5, 0.0), "M a=.50 s=0"),
        ((0.5, SIGMA), "M a=.50 s=.289"),
        ((1.0, SIGMA), "M a=1.0 s=.289 (fast, Gaussian)"),
    ]
    table = {}
    for w, label in worlds:
        table[label] = run_world(w, label, next(kids))
    print(
        "\nI. Day-level score difference D (level minus reading, discriminating rows). Negative: level wins."
    )
    print(
        f"{'world':34s} {'meanD':>8s} {'sdD':>7s} {'acf1':>6s} {'acf2':>6s} {'acf3':>6s} {'meanDctl':>9s}"
    )
    for k, r in table.items():
        print(
            f"{k:34s} {r['mean_D']:8.4f} {r['sd_D']:7.4f} {r['acf1']:6.2f} {r['acf2']:6.2f} {r['acf3']:6.2f} {r['mean_Dctl']:9.4f}"
        )
    print(
        f"   (one series of {ND} days: an autocorrelation has standard error about {1 / math.sqrt(ND):.2f})"
    )
    print(
        "\nII. Pass rate over overlapping 14-day windows. A2 equals A1 when no sweep falls before execution."
    )
    keys = [
        "A1_b1_90",
        "A1_b3_90",
        "A1_b3_98",
        "A1_bm3",
        "A1_bm4",
        "A3",
        "A4_all7",
        "A4_no0",
        "A4ctl_no0",
        "S1_written",
        "S1_tau0_out",
    ]
    print(f"{'world':34s} " + " ".join(f"{x[:10]:>10s}" for x in keys))
    for k, r in table.items():
        print(f"{k:34s} " + " ".join(f"{r[x]:10.3f}" for x in keys))
    print("\nIII. Band, discriminating rows, tau>0 unless named")
    keys2 = [
        "cov_tau0",
        "cov_nom_no0",
        "A4_no0_val",
        "A4_all7_val",
        "A4ctl_no0_val",
        "cov_reading_centred",
        "cov_other_qubit",
        "width_no0",
        "is_real",
        "is_reading_centred",
        "is_other_qubit",
    ]
    print(f"{'world':34s} " + " ".join(f"{x[:12]:>12s}" for x in keys2))
    for k, r in table.items():
        print(f"{k:34s} " + " ".join(f"{r[x]:12.3f}" for x in keys2))
    print(
        "\nIV. Power of A1: pass rate against the position a of the truth between reading (0) and level (1)"
    )
    print("    a     s    | b3_90  b1_90  b3_98  bm3    bm4    | meanD    sdD    acf1")
    for s_ in (0.0, SIGMA):
        for a_ in (0.0, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 0.9, 1.0):
            r = run_world((a_, s_), "", next(kids))
            print(
                f"   {a_:<5} {s_:<5.3f}| {r['A1_b3_90']:.3f}  {r['A1_b1_90']:.3f}  {r['A1_b3_98']:.3f}  {r['A1_bm3']:.3f}  {r['A1_bm4']:.3f}  | {r['mean_D']:8.4f} {r['sd_D']:.4f} {r['acf1']:6.2f}"
            )
    pickle.dump(table, open("C:/t135/cache/worlds_table.pkl", "wb"))
