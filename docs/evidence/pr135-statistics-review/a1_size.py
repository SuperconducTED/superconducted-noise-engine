"""A1's actual false-pass rate under the PR's AR(1) null, re-derived with a separate implementation.

Adds: the closed form at phi=0, block=1; truncated (null_values.py) against untruncated (PR #140's
calendar_block_bootstrap) resamples; a grid of block lengths and interval levels; batch-means t alternatives;
non-Gaussian day effects. Only day means matter, because resampling is by whole days.
"""

import math

import numpy as np
import scipy
from scipy import stats

ND = 14
RUNS, RES = 6000, 2000
BATCH = 200
LEVELS = {"90": 0.05, "95": 0.025, "98": 0.01, "99": 0.005}
print("numpy", np.__version__, "scipy", scipy.__version__)
z = stats.norm.ppf(0.95)
closed = float(stats.t.sf(z * math.sqrt(13 / 14), 13))
print(
    f"closed form, phi=0, block=1: P(t13 > z95*sqrt(13/14)) = {closed:.4f} (committed MC 0.0675, se 0.0056)"
)


def days(rng, n, phi, dist):
    if dist == "normal":
        e = rng.standard_normal((n, ND))
    elif dist == "t3":
        e = rng.standard_t(3, (n, ND)) / math.sqrt(3.0)
    elif dist == "skewL":  # centred exponential with its long tail on the level-wins side
        e = 1.0 - rng.exponential(1.0, (n, ND))
    elif dist == "skewR":
        e = rng.exponential(1.0, (n, ND)) - 1.0
    else:
        raise ValueError(dist)
    u = np.empty((n, ND))
    u[:, 0] = e[:, 0]
    for t in range(1, ND):
        u[:, t] = phi * u[:, t - 1] + math.sqrt(1 - phi * phi) * e[:, t]
    return u


def idx(rng, block, trunc):
    nb = -(-ND // block)
    st = rng.integers(0, ND, (RES, nb))
    a = ((st[:, :, None] + np.arange(block)[None, None, :]) % ND).reshape(RES, nb * block)
    return a[:, :ND] if trunc else a


def rates(seed, phi, block, trunc, dist="normal"):
    rng = np.random.default_rng(seed)
    hit = dict.fromkeys(LEVELS, 0)
    done = 0
    while done < RUNS:
        d = days(rng, BATCH, phi, dist)
        i = idx(rng, block, trunc)
        boot = d[:, i].mean(axis=2)
        for k, a in LEVELS.items():
            hit[k] += int((np.quantile(boot, 1 - a, axis=1) < 0).sum())
        done += BATCH
    return {k: hit[k] / RUNS for k in LEVELS}


def batch_t(seed, phi, q, dist="normal", a=0.05):
    rng = np.random.default_rng(seed)
    d = days(rng, RUNS * 5, phi, dist)
    groups = np.array_split(np.arange(ND), q)
    m = np.stack([d[:, g].mean(axis=1) for g in groups], axis=1)
    t = m.mean(axis=1) / (m.std(axis=1, ddof=1) / math.sqrt(q))
    return float((t < -stats.t.ppf(1 - a, q - 1)).mean())


kids = iter(np.random.SeedSequence(1351107).spawn(400))
print(
    "\nA. truncated to 14 days (null_values.py) vs all blocks' days (PR #140 calendar_block_bootstrap), 90% interval"
)
print(f"phi   block  trunc14  untrunc   (mc se about {math.sqrt(0.1 * 0.9 / RUNS):.4f})")
for phi in (0.0, 0.5):
    for b in (3, 5):
        a = rates(next(kids), phi, b, True)["90"]
        c = rates(next(kids), phi, b, False)["90"]
        print(f"{phi:<5} {b:<6} {a:<8.4f} {c:<8.4f}")
print(
    "\nB. percentile block bootstrap, truncated, false-pass by phi, block, two-sided interval level (one-sided a)"
)
print("phi   block | 90(5%)  95(2.5%) 98(1%)  99(.5%)")
for phi in (0.0, 0.2, 0.3, 0.5, 0.7):
    for b in (1, 2, 3, 5, 7):
        r = rates(next(kids), phi, b, True)
        print(f"{phi:<5} {b:<5} | {r['90']:.4f}  {r['95']:.4f}   {r['98']:.4f}  {r['99']:.4f}")
print("\nC. batch-means t (q consecutive batches, df q-1, one-sided 5%), no resampling")
print("phi   | q=3     q=4     q=5     q=7")
for phi in (0.0, 0.2, 0.3, 0.5, 0.7):
    print(f"{phi:<5} | " + "  ".join(f"{batch_t(next(kids), phi, q):.4f}" for q in (3, 4, 5, 7)))
print("\nD. non-Gaussian day effects: percentile 90% and 98% at block 3; batch-means q=4 at 5%")
print("dist    phi  | b3_90   b3_98   batch4")
for dist in ("normal", "t3", "skewL", "skewR"):
    for phi in (0.0, 0.5):
        r = rates(next(kids), phi, 3, True, dist)
        print(
            f"{dist:7s} {phi:<4} | {r['90']:.4f}  {r['98']:.4f}  {batch_t(next(kids), phi, 4, dist):.4f}"
        )
print("\nMutation: a real edge must pass. Mean shift -1 day-SD, phi=0.5:")
rng = np.random.default_rng(next(kids))
d = days(rng, 200, 0.5, "normal") - 1.0
boot = d[:, idx(rng, 3, True)].mean(axis=2)
print("  percentile 90 block 3 pass:", float((np.quantile(boot, 0.95, axis=1) < 0).mean()))
