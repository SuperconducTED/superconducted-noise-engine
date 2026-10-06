"""How the families' measurement times line up on one qubit (the clock every test relies on).

For each family: events, series, the hour-of-day (UTC) histogram of event times, and the
share of non-positive raw values. For each pair of families on the same qubit (a coupler
family is attached to both of its qubits): for every event of A, the time to the nearest
event of B on that qubit, and the share of A's events with a B event at the identical stamp
or within 0.25, 1, 3 and 12 hours. A pair of families measured minutes apart can share a
fast physical fluctuation; a pair measured hours apart cannot share one faster than that.

Writes ``results/cross/alignment.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc

OUT = xc.RESULTS / "alignment.json"
H = 3.6e6
WINDOWS_H = (0.25, 1.0, 3.0, 12.0)


def qubit_times(dd: ddload.DD, fam: xc.Fam) -> list[np.ndarray]:
    """Sorted event times per qubit (coupler families attach each event to both qubits)."""
    per_q: list[list[np.ndarray]] = [[] for _ in range(156)]
    if fam.name in xc.QUBIT_FAMS:
        for e, t in zip(fam.entity, fam.t_ms, strict=True):
            per_q[int(e)].append(t)
    else:
        pairs = xc.coupler_pairs(dd, fam.name)
        for e, t in zip(fam.entity, fam.t_ms, strict=True):
            a, b = pairs[int(e)]
            per_q[a].append(t)
            per_q[b].append(t)
    return [np.sort(np.concatenate(x)) if x else np.empty(0) for x in per_q]


def nearest_gaps(ta: np.ndarray, tb: np.ndarray) -> np.ndarray:
    """Signed gap (h) from each time in ``ta`` to the nearest time in ``tb`` (B minus A).

    Only A events inside B's lifetime on that qubit (first to last B event) are used, so a
    family with a later schema start (``init``, ``m2``) does not inflate the gaps.
    """
    if ta.size == 0 or tb.size == 0:
        return np.empty(0)
    ta = ta[(ta >= tb[0]) & (ta <= tb[-1])]
    if ta.size == 0:
        return np.empty(0)
    i = np.searchsorted(tb, ta)
    lo = np.clip(i - 1, 0, tb.size - 1)
    hi = np.clip(i, 0, tb.size - 1)
    d_lo = tb[lo] - ta
    d_hi = tb[hi] - ta
    out: np.ndarray = np.where(np.abs(d_lo) <= np.abs(d_hi), d_lo, d_hi) / H
    return out


def main() -> int:
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/alignment.py")
    payload["n_files"] = dd.n_files
    fams = {f: xc.load(dd, f) for f in xc.ALL_FAMS}
    per_fam: dict[str, Any] = {}
    for f, fam in fams.items():
        t = np.concatenate(fam.t_ms)
        hours = np.floor((t % 86_400_000.0) / H).astype(int)
        raw = np.array(dd.v(xc.FIELD[f]), dtype=np.float64)
        if f in ("cz", "rzz"):
            raw = raw[:, xc.undirected_columns(dd)[0]]
        present = np.isfinite(raw)
        if f in ("m2", "sx", "cz", "rzz"):
            present &= raw < 1.0
        per_fam[f] = {
            "field": xc.FIELD[f],
            "series": len(fam.z),
            "events": int(sum(z.size for z in fam.z)),
            "events_per_series_median": float(np.median([z.size for z in fam.z])),
            "hour_of_day_utc_counts": np.bincount(hours, minlength=24).tolist(),
            "raw_records_present": int(present.sum()),
            "raw_records_le_zero": int(np.sum(present & (raw <= 0))),
            "raw_records_lt_zero": int(np.sum(present & (raw < 0))),
        }
    payload["families"] = per_fam
    daily_fams = ("T1", "T2", "sx", "m2", "cz", "rzz")
    hod = np.sum([per_fam[f]["hour_of_day_utc_counts"] for f in daily_fams], axis=0)
    payload["daily_families_hour_of_day_utc_counts"] = hod.tolist()
    payload["daily_families_quietest_hour_utc"] = int(np.argmin(hod))
    fast = ("RO", "init", "zz")
    payload["fast_families_hour_of_day_utc_counts"] = np.sum(
        [per_fam[f]["hour_of_day_utc_counts"] for f in fast], axis=0
    ).tolist()

    times = {f: qubit_times(dd, fam) for f, fam in fams.items()}
    pairs_out: dict[str, Any] = {}
    names = list(xc.ALL_FAMS)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            gaps = [nearest_gaps(times[a][q], times[b][q]) for q in range(156)]
            g = np.concatenate([x for x in gaps if x.size])
            if g.size == 0:
                continue
            ag = np.abs(g)
            row: dict[str, Any] = {
                "a_events_with_b": int(g.size),
                "abs_gap_h_q10_25_50_75_90": xc.q_list(ag),
                "share_identical_stamp": round(float(np.mean(ag == 0.0)), 4),
                "b_after_a_share_of_nonzero": round(float(np.mean(g[g != 0] > 0)), 4)
                if np.any(g != 0)
                else None,
            }
            for w in WINDOWS_H:
                row[f"share_within_{w}h"] = round(float(np.mean(ag <= w)), 4)
            pairs_out[f"{a}|{b}"] = row
    payload["nearest_event_gap_same_qubit"] = pairs_out
    xc.RESULTS.mkdir(parents=True, exist_ok=True)
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
