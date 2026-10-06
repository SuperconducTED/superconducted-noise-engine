"""Device-wide change points on per-family device-median series, against the known events.

Series: one point per major round of each family (``schedule.py``'s definition: at least half
the entities re-measured), the median over the re-measured entities of ``log10(value)``;
for ``lf`` the point is ``log10(EPLG_proc(100))`` per lf event inside the archive. A second
set of series measures coverage: files per UTC day and readout major rounds per UTC day.

Method: PELT (Killick, Fearnhead and Eckley 2012) for changes in the mean with the squared
error cost, minimum segment length 3, penalty ``c * sigma^2 * ln(n)`` where ``sigma`` is the
noise scale estimated robustly from first differences (``1.4826 * MAD(diff) / sqrt(2)``),
for ``c`` in 2 (BIC-like), 4 and 8. Binary segmentation with the same cost and penalty is
run as a cross-check. Detected points are matched to a list of known events within +-36 h,
and the number expected by chance is the share of the archive's span within 36 h of any
known event times the number detected.

Writes ``results/device/changepoints.json``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

PENALTIES = (2.0, 4.0, 8.0)
MIN_SEG = 3
MATCH_H = 36.0
KNOWN = (
    ("2026-05-29T16:46:42Z", "xslow records disappear (01-data-layer)"),
    ("2026-06-08T18:56:28Z", "readout length 1560 to 1700 ns; measure.threshold appears"),
    ("2026-06-24T16:36:39Z", "clops_v serialisation changes (configuration only)"),
    ("2026-07-16T03:00:13Z", "configuration key mcps appears"),
    ("2026-07-30T21:09:17Z", "readout length 1700 to 1660 ns"),
    ("2026-08-05T23:45:31Z", "first historical file (coverage change)"),
    ("2026-08-07T03:21:59Z", "measure_2 enters target and properties; 82.7 h file gap follows"),
    ("2026-09-02T04:56:24Z", "measure_reset, measure_reset_2, reset_2 enter; ledger starts"),
    ("2026-09-05T17:51:36Z", "q72 couplers 68 to 84 ns"),
    ("2026-09-10T16:56:21Z", "xslow records return; basis_gates gains xslow"),
)


def to_ms(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000.0


def seg_cost(cs: np.ndarray, cs2: np.ndarray, s: int, e: int) -> float:
    """Squared-error cost of x[s:e] around its mean, from cumulative sums."""
    n = e - s
    tot = cs[e] - cs[s]
    return float((cs2[e] - cs2[s]) - tot * tot / n)


def pelt(x: np.ndarray, beta: float, min_seg: int = MIN_SEG) -> list[int]:
    n = x.size
    cs = np.r_[0.0, np.cumsum(x)]
    cs2 = np.r_[0.0, np.cumsum(x * x)]
    f = np.full(n + 1, np.inf)
    f[0] = -beta
    last = np.zeros(n + 1, dtype=np.int64)
    cand = [0]
    for t in range(min_seg, n + 1):
        vals = [(f[s] + seg_cost(cs, cs2, s, t) + beta, s) for s in cand if t - s >= min_seg]
        if not vals:
            cand.append(t - min_seg + 1)
            continue
        best, arg = min(vals)
        f[t] = best
        last[t] = arg
        cand = [s for s in cand if t - s < min_seg or f[s] + seg_cost(cs, cs2, s, t) <= f[t]]
        cand.append(t - min_seg + 1)
    cps = []
    t = n
    while t > 0:
        s = int(last[t])
        if s > 0:
            cps.append(s)
        t = s
    return sorted(cps)


def binseg(x: np.ndarray, beta: float, min_seg: int = MIN_SEG) -> list[int]:
    cs = np.r_[0.0, np.cumsum(x)]
    cs2 = np.r_[0.0, np.cumsum(x * x)]
    out: list[int] = []
    stack = [(0, x.size)]
    while stack:
        s, e = stack.pop()
        if e - s < 2 * min_seg:
            continue
        whole = seg_cost(cs, cs2, s, e)
        best, arg = 0.0, -1
        for k in range(s + min_seg, e - min_seg + 1):
            gain = whole - seg_cost(cs, cs2, s, k) - seg_cost(cs, cs2, k, e)
            if gain > best:
                best, arg = gain, k
        if arg > 0 and best > beta:
            out.append(arg)
            stack.extend([(s, arg), (arg, e)])
    return sorted(out)


def noise_sigma(x: np.ndarray) -> float:
    d = np.diff(x)
    return float(1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2.0))


def describe(
    x: np.ndarray, t: np.ndarray, known_ms: np.ndarray, span_share: float
) -> dict[str, Any]:
    sig = noise_sigma(x)
    out: dict[str, Any] = {"n": int(x.size), "noise_sigma": dc.r6(sig)}
    for c in PENALTIES:
        beta = c * sig * sig * np.log(x.size)
        cps = pelt(x, beta)
        bs = binseg(x, beta)
        rows = []
        bounds = [0, *cps, x.size]
        for k, cp in enumerate(cps):
            before = x[bounds[k] : cp]
            after = x[cp : bounds[k + 2]]
            tm = float(t[cp])
            near = np.abs(known_ms - tm) / ddload.MS_PER_HOUR
            j = int(np.argmin(near))
            rows.append(
                {
                    "at": dc.iso(tm),
                    "shift_log10": dc.r6(np.median(after) - np.median(before)),
                    "nearest_known": KNOWN[j][1],
                    "hours_to_nearest_known": dc.r6(near[j]),
                    "matched": bool(near[j] <= MATCH_H),
                }
            )
        out[f"c{int(c)}"] = {
            "beta": dc.r6(beta),
            "pelt_points": rows,
            "pelt_count": len(cps),
            "matched": int(sum(r["matched"] for r in rows)),
            "expected_by_chance": dc.r6(len(cps) * span_share),
            "binseg_count": len(bs),
            "binseg_points_shared_with_pelt_within_1": int(
                sum(1 for b in bs if any(abs(b - p) <= 1 for p in cps))
            ),
            "segment_medians_log10": [
                dc.r6(np.median(x[bounds[k] : bounds[k + 1]])) for k in range(len(bounds) - 1)
            ],
        }
    return out


def round_series(dd: ddload.DD, fam: dc.Family) -> tuple[np.ndarray, np.ndarray]:
    ev = dc.family_events(dd, fam)
    lab = dc.split_rounds(ev.t_ms)
    ts, xs = [], []
    for r in np.unique(lab):
        m = lab == r
        if np.unique(ev.entity[m]).size < 0.5 * ev.n_entities:
            continue
        ts.append(float(ev.t_ms[m].min()))
        xs.append(float(np.median(np.log10(ev.y[m]))))
    order = np.argsort(ts)
    return np.array(xs)[order], np.array(ts)[order]


def main() -> int:
    dd = ddload.DD()
    known_ms = np.array([to_ms(k[0]) for k in KNOWN])
    fms = dd.file_ms
    span = float(fms[-1] - fms[0])
    grid = np.linspace(float(fms[0]), float(fms[-1]), 20001)
    near_any = np.min(np.abs(grid[:, None] - known_ms[None, :]), axis=1) <= MATCH_H * 3.6e6
    span_share = float(np.mean(near_any))
    series: dict[str, Any] = {}
    for fam in dc.FAMILIES:
        if fam.name in ("xslow", "lf"):
            continue
        x, t = round_series(dd, fam)
        series[fam.name] = describe(x, t, known_ms, span_share)
    lf_v = np.array(dd.v("gen.lf"))
    lf_d = np.array(dd.d("gen.lf"))[:, 0]
    k100 = dd.meta["lf_names"].index("lf_100")
    ev = [0] + [i for i in range(1, dd.n_files) if lf_d[i] != lf_d[i - 1]]
    ev = [i for i in ev if lf_d[i] >= fms[0]]
    lf_t = lf_d[ev]
    lf_x = np.log10(1.0 - lf_v[ev, k100] ** (1.0 / 99.0))
    series["lf_eplg100"] = describe(lf_x, lf_t, known_ms, span_share)
    # Coverage series per UTC day.
    day = dc.day_index(fms)
    days = np.arange(day.min(), day.max() + 1)
    files_per_day = np.array([np.sum(day == k) for k in days], dtype=float)
    day_t = days.astype(float) * dc.MS_PER_DAY
    series["coverage_files_per_day"] = describe(files_per_day, day_t, known_ms, span_share)
    ro = dc.family_events(dd, dc.FAMILIES[0])
    lab = dc.split_rounds(ro.t_ms)
    starts = []
    for r in np.unique(lab):
        m = lab == r
        if np.unique(ro.entity[m]).size >= 0.5 * ro.n_entities:
            starts.append(float(ro.t_ms[m].min()))
    rday = dc.day_index(np.array(starts))
    ro_per_day = np.array([np.sum(rday == k) for k in days], dtype=float)
    series["coverage_readout_rounds_per_day"] = describe(ro_per_day, day_t, known_ms, span_share)
    value_keys = [k for k in series if not k.startswith("coverage")]
    summary = {
        f"c{int(c)}": {
            "series": len(value_keys),
            "detected": int(sum(series[k][f"c{int(c)}"]["pelt_count"] for k in value_keys)),
            "matched": int(sum(series[k][f"c{int(c)}"]["matched"] for k in value_keys)),
            "expected_by_chance": dc.r6(
                sum(series[k][f"c{int(c)}"]["expected_by_chance"] for k in value_keys)
            ),
        }
        for c in PENALTIES
    }
    payload = {
        **dc.header("changepoints.py"),
        "n_files": dd.n_files,
        "method": "PELT, squared-error cost, min segment 3, beta = c sigma^2 ln n; BinSeg check",
        "penalty_factors": list(PENALTIES),
        "match_window_h": MATCH_H,
        "known_events": [{"at": k[0], "what": k[1]} for k in KNOWN],
        "share_of_span_within_window_of_a_known_event": dc.r6(span_share),
        "span_days": dc.r6(span / dc.MS_PER_DAY),
        "first_utc_day": datetime.fromtimestamp(day_t[0] / 1000.0, UTC).strftime("%Y-%m-%d"),
        "series": series,
        "summary_value_series": summary,
    }
    ddload.write_json(dc.RESULTS / "changepoints.json", payload)
    print("wrote", dc.RESULTS / "changepoints.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
