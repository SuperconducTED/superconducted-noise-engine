"""One row per (day, qubit in Arm A) from the pinned predictors, on the archive at 7adda803.

Uses the pre-registered code itself (scripts/hardware_test_predictors.py at 5c98f264): predictor_rows and
select_balanced at 03:45 UTC every day, no live document, so selection, level and band are the rule's own.
Controls: the section 3.9 rehearsal's four (144, 110, 140, 77), named as not frozen.
Also records, per qubit-day, the next changed T1 after t_s (the archive's nearest thing to "the device later").
Output: C:/t135/cache/days.pkl
"""

import math
import pickle
import sys
from datetime import UTC, datetime, timedelta

import numpy as np

sys.path.insert(0, "C:/t135/new")
from scripts.hardware_test_predictors import (
    QUANTITIES,
    predictor_rows,
    select_balanced,
)

CONTROLS = {144, 110, 140, 77}
c = pickle.load(open("C:/t135/cache/collected.pkl", "rb"))
files = sorted(c.files, key=lambda r: (r.time, r.path))
times = [f.time for f in files]
iT1, iT2 = QUANTITIES.index("T1"), QUANTITIES.index("T2")
ie10, ie01 = QUANTITIES.index("prob_meas0_prep1"), QUANTITIES.index("prob_meas1_prep0")
print("files", len(files), "first", times[0], "last", times[-1])
start = datetime(2026, 6, 13, 3, 45, tzinfo=UTC)
last = datetime(2026, 10, 27, 3, 45, tzinfo=UTC)
days = []
t = start
while t <= last:
    days.append(t)
    t += timedelta(days=1)


def next_change(q, t_s, value):
    """First file after t_s whose T1 for qubit q is finite, positive and differs from value."""
    lo = np.searchsorted(np.array([x.timestamp() for x in times]), t_s.timestamp(), side="right")
    for f in files[lo:]:
        if q >= f.values.shape[0]:
            continue
        v = float(f.values[q, iT1])
        if math.isfinite(v) and v > 0 and v != value:
            return (
                v,
                float(f.values[q, ie10]),
                float(f.values[q, ie01]),
                (f.time - t_s).total_seconds() / 3600.0,
            )
    return math.nan, math.nan, math.nan, math.nan


records = []
day_meta = []
for k, t_s in enumerate(days):
    rows = predictor_rows(c, at=t_s, live=None)
    sel = select_balanced(rows, k=8, controls=CONTROLS)
    tab = {(r.qubit, r.quantity): r for r in rows}
    disc = [p["qubit"] for p in sel["discriminating"]]
    day_meta.append(
        {
            "t_s": t_s,
            "n_selected": sel["n_selected"],
            "short_side": sel["short_side"],
            "n_filled": sel["n_filled"],
            "below_floor": len(sel["below_window_floor"]),
            "admitted_below": sel["admitted"]["below"],
            "admitted_above": sel["admitted"]["above"],
            "disc": disc,
        }
    )
    for q, stratum in [(q, "discriminating") for q in disc] + [
        (q, "control") for q in sorted(CONTROLS)
    ]:
        r = tab[(q, "T1")]
        nv, ne10, ne01, gap = next_change(q, t_s, r.reading)
        records.append(
            {
                "day": k,
                "qubit": q,
                "stratum": stratum,
                "t1_reading": r.reading,
                "t1_level": r.level,
                "t1_lo": r.band_lo,
                "t1_hi": r.band_hi,
                "d": r.log_disagreement,
                "e10_reading": tab[(q, "prob_meas0_prep1")].reading,
                "e01_reading": tab[(q, "prob_meas1_prep0")].reading,
                "e10_level": tab[(q, "prob_meas0_prep1")].level,
                "e01_level": tab[(q, "prob_meas1_prep0")].level,
                "t1_next": nv,
                "e10_next": ne10,
                "e01_next": ne01,
                "gap_h": gap,
                "reading_time": r.reading_time,
            }
        )
    if k % 20 == 0:
        print(k, t_s.date(), disc, flush=True)
pickle.dump(
    {"days": days, "day_meta": day_meta, "records": records}, open("C:/t135/cache/days.pkl", "wb")
)
print("days", len(days), "records", len(records))
ns = [m["n_selected"] for m in day_meta]
print(
    "n_selected min",
    min(ns),
    "short-side days",
    sum(1 for m in day_meta if m["short_side"]),
    "below_floor max",
    max(m["below_floor"] for m in day_meta),
)
d = np.array(
    [
        [r["d"] for r in records if r["day"] == k and r["stratum"] == "discriminating"]
        for k in range(len(days))
    ]
)
print("|d| selected, median", float(np.median(np.abs(d))), "min", float(np.min(np.abs(d))))
gaps = np.array([r["gap_h"] for r in records])
print(
    "hours to next changed T1: median",
    float(np.nanmedian(gaps)),
    "p10",
    float(np.nanpercentile(gaps, 10)),
    "p90",
    float(np.nanpercentile(gaps, 90)),
    "nan",
    int(np.isnan(gaps).sum()),
)
