"""Verifier: does the fall of readout rounds per day survive other round definitions?"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = (
    Path(__file__).resolve().parents[3]
    / "results"
    / "verify"
    / "device"
    / "v6_readout_cadence.json"
)


def main() -> None:
    dd = ddload.DD()
    fms = dd.file_ms
    res: dict = {
        "header": ddload.result_header(
            "verify/device", "analysis/verify/device/v6_readout_cadence.py"
        )
    }
    ser = ddload.series(dd, "q.readout_error", rule=ddload.MEASURED)
    first = fms[0]
    t = np.sort(np.concatenate([s.t_ms[s.t_ms >= first] for s in ser]))
    month = lambda x: datetime.fromtimestamp(x / 1000, UTC).strftime("%Y-%m")  # noqa: E731
    days = {}
    for m in sorted({month(x) for x in fms}):
        sel = np.array([month(x) == m for x in fms])
        idx = np.flatnonzero(sel)
        days[m] = (fms[idx[-1]] - fms[idx[0]]) / 8.64e7
    # use calendar days covered as the document does: first to last file of the month
    for gap_min in (15, 60, 180):
        cut = np.flatnonzero(np.diff(t) > gap_min * 60e3) + 1
        groups = np.split(t, cut)
        starts = np.array([g[0] for g in groups if g.size >= 78])
        per = {}
        for m in sorted(days):
            n = sum(1 for s in starts if month(s) == m)
            per[m] = {"rounds": n, "per_day": n / days[m] if days[m] > 0 else None}
        res[f"gap{gap_min}"] = per
    # number of distinct stamped moments per month, regardless of rounds (events per day)
    ev = {}
    for m in sorted(days):
        n = int(sum(1 for x in t if month(x) == m))
        ev[m] = n / days[m]
    res["readout_events_per_day"] = ev
    res["days_covered_by_my_definition"] = days
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
