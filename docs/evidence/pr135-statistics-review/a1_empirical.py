"""A1's false-pass rate on the real day series, with its mean removed: real selection, real dependence, real tails.

World F: truth is each selected qubit's next changed reading, so D_day has the only dependence the archive can
show. Removing the series mean imposes "equal accuracy" without assuming a shape. Overlapping 14-day windows, so
about nine independent windows: a rough check on the AR(1) table, not a replacement for it.
Also: how often the same qubit is selected on consecutive days, and how D_day splits by the sign of d.
"""

import math

import numpy as np
from arm_a_worlds import (
    ND,
    REC,
    D,
    acf,
    batch_pass,
    boot_upper,
    is_disc,
    per_day,
    rec,
    simulate,
    windows,
)
from scipy import stats

day_meta = D["day_meta"]
ov = [len(set(day_meta[i]["disc"]) & set(day_meta[i + 1]["disc"])) for i in range(ND - 1)]
print(
    "selected-qubit overlap with the next day: mean",
    round(float(np.mean(ov)), 2),
    "of 8; distribution",
    np.bincount(ov).tolist(),
)
same_reading = 0
tot = 0
byday = {}
for r in REC:
    if r["stratum"] == "discriminating":
        byday.setdefault(r["day"], {})[r["qubit"]] = r["t1_reading"]
for k in range(ND - 1):
    for q, v in byday[k].items():
        if q in byday[k + 1]:
            tot += 1
            same_reading += v == byday[k + 1][q]
print(
    f"qubits selected on consecutive days: {tot}; with the same reading both days: {same_reading}"
)

kids = iter(np.random.SeedSequence(135110704).spawn(20))
for world, label in (("F", "F next reading"), ("N", "N level is true")):
    rng = np.random.default_rng(next(kids))
    series = []
    tally = {k: [] for k in ("b1_90", "b3_90", "b3_95", "b3_98", "b3_99", "bm3", "bm4")}
    for _ in range(40):
        s = simulate(world, rng)
        dd = per_day(s["d_row"], is_disc)
        series.append(dd)
        w = windows(dd - dd.mean())
        tally["b1_90"].append(boot_upper(w, 1, 0.05, rng) < 0)
        tally["b3_90"].append(boot_upper(w, 3, 0.05, rng) < 0)
        tally["b3_95"].append(boot_upper(w, 3, 0.025, rng) < 0)
        tally["b3_98"].append(boot_upper(w, 3, 0.01, rng) < 0)
        tally["b3_99"].append(boot_upper(w, 3, 0.005, rng) < 0)
        tally["bm3"].append(batch_pass(w, 3))
        tally["bm4"].append(batch_pass(w, 4))
    arr = np.array(series)
    x = arr.mean(axis=0)
    acfs = [acf(x, k) for k in (1, 2, 3, 4)]
    print(
        f"\n{label}: mean {arr.mean():.4f}, day sd {arr.std(axis=1, ddof=1).mean():.4f}, skew {float(stats.skew(x)):.2f}, excess kurtosis {float(stats.kurtosis(x)):.2f}"
    )
    print(
        "   acf lag 1..4 of the series averaged over shot noise:",
        [round(a, 2) for a in acfs],
        f"(se about {1 / math.sqrt(ND):.2f})",
    )
    print(
        "   false-pass, mean removed, overlapping windows:",
        {k: round(float(np.mean(v)), 3) for k, v in tally.items()},
    )
    if label.startswith("F"):
        # a 3-day block bootstrap interval on lag-1 itself, over the 137 days
        vals = []
        nb = -(-ND // 3)
        for _ in range(4000):
            st = rng.integers(0, ND, nb)
            ids = ((st[:, None] + np.arange(3)[None, :]) % ND).reshape(-1)[:ND]
            # keep pairs inside a block by resampling (t, t+1) pairs from the same block draw
            a = x[ids[:-1]]
            b = x[(ids[:-1] + 1) % ND]
            vals.append(float(np.corrcoef(a, b)[0, 1]))
        print(
            "   lag-1, circular block bootstrap of pairs, 90%:",
            np.round(np.percentile(vals, [5, 95]), 2).tolist(),
        )
        for sign, name in ((-1, "below"), (1, "above")):
            m = is_disc & (np.sign(rec["d"]) == sign)
            s = simulate(world, rng)
            print(
                f"   rows with d {name} the level: mean score difference {s['d_row'][m].mean():.4f} over {m.sum() * 7} rows"
            )
