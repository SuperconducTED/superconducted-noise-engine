"""If A4 stops being a gate, S1 is A1 and A3 alone. What then guards S1 near equal accuracy?

Pass rate of A1 and A3 together, and with A4 on tau > 0 rows, by interval, across positions a. Controls are the
rehearsal's four; A2 equals A1 (no sweep). Overlapping 14-day windows, descriptive.
"""

import numpy as np
from arm_a_worlds import SIGMA, batch_pass, boot_upper, is_disc, per_day, simulate, windows

kids = iter(np.random.SeedSequence(135110706).spawn(40))
print("world                    |  A1 and A3 together          |  with A4 on tau>0 kept as a gate")
print("                         |  b3_90   b3_98   bm4         |  b3_90   b3_98   bm4")
for world, label in (
    ((0.5, 0.0), "M a=.50 s=0"),
    ((0.5, SIGMA), "M a=.50 s=.289"),
    ((0.55, SIGMA), "M a=.55 s=.289"),
    ((0.6, SIGMA), "M a=.60 s=.289"),
    ((0.7, SIGMA), "M a=.70 s=.289"),
    ("F", "F next reading"),
    ("N", "N level is true"),
    ("S", "S reading persists"),
):
    rng = np.random.default_rng(next(kids))
    t = {k: [] for k in ("b390", "b398", "bm4", "b390g", "b398g", "bm4g")}
    for _ in range(20):
        s = simulate(world, rng)
        dd = per_day(s["d_row"], is_disc)
        dc = per_day(s["d_row"], ~is_disc)
        w, wc = windows(dd), windows(dc)
        a3 = wc.mean(axis=1) < 0
        cov = per_day(s["cov_wid"][:, 1:7].astype(float), is_disc)
        a4 = windows(cov).mean(axis=1) >= 0.80
        for name, passed in (
            ("b390", boot_upper(w, 3, 0.05, rng) < 0),
            ("b398", boot_upper(w, 3, 0.01, rng) < 0),
            ("bm4", batch_pass(w, 4)),
        ):
            t[name].append(passed & a3)
            t[name + "g"].append(passed & a3 & a4)
    m = {k: float(np.mean(v)) for k, v in t.items()}
    print(
        f"{label:24s} |  {m['b390']:.3f}   {m['b398']:.3f}   {m['bm4']:.3f}       |  {m['b390g']:.3f}   {m['b398g']:.3f}   {m['bm4g']:.3f}"
    )
