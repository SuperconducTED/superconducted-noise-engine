"""Can Arm A's own rows separate the worlds directly? Second route to the A4 finding, not using the band at all.

Per (day, qubit): fit log T1 by binomial maximum likelihood from the six tau > 0 rows, with the level's readout.
Then, per stratum: c = slope of (log T1_fit - log level) on d = log reading - log level (0 is N, 1 is S), and
s_res = robust spread of the residual (near fit noise in N, near the scatter in a fast physical world).
Also the band-coverage distribution across 14-day windows on tau > 0 rows, and thresholds between 80% and 100%.
"""

import math
import pickle

import numpy as np
from scipy import stats

D = pickle.load(open("C:/t135/cache/days.pkl", "rb"))
REC = D["records"]
ND = len(D["days"])
SHOTS = 2048
SIGMA = 0.37 / stats.norm.ppf(0.9)
rec = {k: np.array([r[k] for r in REC]) for k in REC[0] if k not in ("stratum", "reading_time")}
is_disc = np.array([r["stratum"] == "discriminating" for r in REC])
n = len(REC)
factors = np.array([0.5, 1.0, 2.0])
taus = np.zeros((n, 6))
taus[:, 0:3] = rec["t1_level"][:, None] * factors
taus[:, 3:6] = rec["t1_reading"][:, None] * factors
ok_next = np.isfinite(rec["t1_next"])
GRID = np.linspace(-3.0, 3.0, 1201)


def p1(tau, t1, e10, e01):
    s = np.exp(-tau / t1)
    return (1.0 - e10) * s + e01 * (1.0 - s)


def truth(world, rng):
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
    return (
        np.exp((1 - a) * lr + a * ll + s * z),
        (1 - a) * rec["e10_reading"] + a * rec["e10_level"],
        (1 - a) * rec["e01_reading"] + a * rec["e01_level"],
    )


def fit_log_t1(k):
    """Grid MLE of log(T1 / level) per record from six binomial rows, with the level's readout."""
    out = np.empty(n)
    for i in range(n):
        t1 = rec["t1_level"][i] * np.exp(GRID)
        p = np.clip(
            p1(taus[i][None, :], t1[:, None], rec["e10_level"][i], rec["e01_level"][i]),
            1e-9,
            1 - 1e-9,
        )
        ll = (k[i] * np.log(p) + (SHOTS - k[i]) * np.log1p(-p)).sum(axis=1)
        out[i] = GRID[int(np.argmax(ll))]
    return out


def robust_sd(x):
    q = np.percentile(x, [10, 90])
    return (q[1] - q[0]) / (2 * stats.norm.ppf(0.9))


def day_block_ci(est, x, y, mask, rng, n_boot=400):
    """90% circular 3-day block interval over the full series, days kept whole."""
    vals = []
    day = rec["day"]
    by_day = [np.where(mask & (day == k))[0] for k in range(ND)]
    nb = -(-ND // 3)
    for _ in range(n_boot):
        st = rng.integers(0, ND, nb)
        ds = ((st[:, None] + np.arange(3)[None, :]) % ND).reshape(-1)[:ND]
        ii = np.concatenate([by_day[int(d)] for d in ds])
        vals.append(est(x[ii], y[ii]))
    return np.percentile(vals, [5, 95])


def slope_res(x, y):
    b = float((x * y).sum() / (x * x).sum())
    return b


kids = iter(np.random.SeedSequence(135110703).spawn(50))
worlds = [
    ("N", "N level is true"),
    ("F", "F next reading"),
    ("S", "S reading persists"),
    ((0.5, 0.0), "M a=.50 s=0"),
    ((1.0, SIGMA), "M a=1 s=.289"),
    ((1.0, SIGMA / 2), "M a=1 s=.144 (half the scatter physical)"),
]
print("I. Direct fit from Arm A rows, one simulated run, whole series (137 days). c=0 N, c=1 S.")
print(f"{'world':42s} {'stratum':8s} {'c':>7s} {'90% CI':>18s} {'s_res':>7s} {'n':>5s}")
d = rec["d"]
results = {}
for w, label in worlds:
    rng = np.random.default_rng(next(kids))
    t, e10, e01 = truth(w, rng)
    p = p1(taus, t[:, None], e10[:, None], e01[:, None])
    k = rng.binomial(SHOTS, np.clip(p, 0, 1))
    y = fit_log_t1(k)
    results[label] = y
    for name, mask in (("disc", is_disc), ("ctrl", ~is_disc)):
        c = slope_res(d[mask], y[mask])
        lo, hi = day_block_ci(slope_res, d, y, mask, rng)
        res = y[mask] - c * d[mask]
        print(
            f"{label:42s} {name:8s} {c:7.3f} [{lo:7.3f},{hi:7.3f}] {robust_sd(res):7.3f} {mask.sum():5d}"
        )
print(
    "\nNB on the second route: c on world F should sit near 1 + b, with b the reversion slope of NC-084 (-0.83 on gamma)."
)
print(
    "\nII. The same two statistics on 14-day windows, per world (discriminating rows): median and 5th to 95th percentile."
)
print(
    f"{'world':42s} {'c med':>7s} {'c 5%':>7s} {'c 95%':>7s} {'s_res med':>9s} {'s 5%':>7s} {'s 95%':>7s}"
)
day = rec["day"]
for label, y in results.items():
    cs, ss = [], []
    for start in range(ND - 13):
        m = is_disc & (day >= start) & (day < start + 14)
        c = slope_res(d[m], y[m])
        cs.append(c)
        ss.append(robust_sd(y[m] - c * d[m]))
    print(
        f"{label:42s} {np.median(cs):7.3f} {np.percentile(cs, 5):7.3f} {np.percentile(cs, 95):7.3f} {np.median(ss):9.3f} {np.percentile(ss, 5):7.3f} {np.percentile(ss, 95):7.3f}"
    )

print(
    "\nIII. Band coverage on tau > 0 rows after the one-SE widening: per 14-day window, discriminating rows."
)
print(
    f"{'world':42s} {'median':>7s} {'5%':>7s} {'95%':>7s} {'P>=.80':>7s} {'P>=.90':>7s} {'P>=.95':>7s}"
)
for w, label in worlds:
    rng = np.random.default_rng(next(kids))
    rows = []
    for _ in range(8):
        t, e10, e01 = truth(w, rng)
        p = p1(taus, t[:, None], e10[:, None], e01[:, None])
        phat = rng.binomial(SHOTS, np.clip(p, 0, 1)) / SHOTS
        a = p1(taus, rec["t1_lo"][:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
        b = p1(taus, rec["t1_hi"][:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        se = np.sqrt(np.clip(phat * (1 - phat), 0, None) / SHOTS)
        cov = ((lo - se <= phat) & (phat <= hi + se)).astype(float)
        per_day = np.array([cov[is_disc & (day == k)].mean() for k in range(ND)])
        rows.append(np.lib.stride_tricks.sliding_window_view(per_day, 14).mean(axis=1))
    v = np.concatenate(rows)
    print(
        f"{label:42s} {np.median(v):7.3f} {np.percentile(v, 5):7.3f} {np.percentile(v, 95):7.3f} {(v >= 0.8).mean():7.3f} {(v >= 0.9).mean():7.3f} {(v >= 0.95).mean():7.3f}"
    )
print("\nMutation for the fit: a run with T1 x 2 must give a fit of about log 2.")
rng = np.random.default_rng(next(kids))
t = rec["t1_level"] * 2.0
p = p1(taus, t[:, None], rec["e10_level"][:, None], rec["e01_level"][:, None])
y = fit_log_t1(rng.binomial(SHOTS, np.clip(p, 0, 1)))
print(
    "  T1 x 2: median fit",
    round(float(np.median(y)), 3),
    "(log 2 =",
    round(math.log(2), 3),
    ")  robust sd",
    round(float(robust_sd(y)), 3),
)
