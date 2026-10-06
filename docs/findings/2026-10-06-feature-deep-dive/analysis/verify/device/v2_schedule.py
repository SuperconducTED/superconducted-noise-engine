"""Verifier: stamp semantics and the schedule of T1, cz, readout rounds (own round code)."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v2_schedule.json"
FIELDS = (
    "q.T1", "q.T2", "q.readout_error", "q.prob_meas0_prep1", "q.prob_meas1_prep0",
    "q.init_error", "g1.sx.gate_error", "g1.x.gate_error", "g1.id.gate_error",
    "g1.rx.gate_error", "g1.xslow.gate_error", "g1.measure_2.gate_error",
    "g2.cz.gate_error", "g2.rzz.gate_error",
)  # fmt: skip


def major_starts(dd: ddload.DD, field: str, n_ent: int, mask) -> np.ndarray:
    ser = ddload.series(dd, field, rule=ddload.MEASURED, mask=mask)
    first = dd.file_ms[0]
    t = np.concatenate([s.t_ms[s.t_ms >= first] for s in ser])
    t.sort()
    cut = np.flatnonzero(np.diff(t) > 15 * 60e3) + 1
    groups = np.split(t, cut)
    return np.array([g[0] for g in groups if g.size >= n_ent / 2])


def main() -> None:
    dd = ddload.DD()
    fms = dd.file_ms
    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v2_schedule.py")
    }
    newest = np.full(dd.n_files, -np.inf)
    for f in FIELDS:
        v = np.array(dd.v(f))
        d = np.array(dd.d(f))
        if f.endswith("gate_error"):
            d[v >= 1.0] = np.nan
        newest = np.fmax(newest, np.nanmax(np.where(np.isfinite(d), d, -np.inf), axis=1))
    gap = (fms - newest) / 3.6e6
    res["share_last_update_eq_newest"] = float(np.mean(gap == 0))
    res["last_update_minus_newest_h_median"] = float(np.median(gap))
    res["n_last_update_before_newest"] = int(np.sum(gap < 0))
    zz = np.array(dd.d("gen.zz"))
    res["zz_all_equal_last_update"] = bool(np.all(zz == fms[:, None]))
    # schedule
    starts = {}
    starts["T1"] = major_starts(dd, "q.T1", 156, None)
    starts["readout"] = major_starts(dd, "q.readout_error", 156, None)
    cz_cols = [k for k, (a, b) in enumerate(dd.meta["directed_edges"]) if a < b]
    # cz: restrict columns by masking others
    ser = ddload.series(dd, "g2.cz.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    keep = set(cz_cols)
    first = fms[0]
    t = np.concatenate([s.t_ms[s.t_ms >= first] for s in ser if s.entity in keep])
    t.sort()
    cut = np.flatnonzero(np.diff(t) > 15 * 60e3) + 1
    groups = np.split(t, cut)
    starts["cz"] = np.array([g[0] for g in groups if g.size >= 176 / 2])
    for k, s in starts.items():
        s = np.sort(s)
        g = np.diff(s) / 3.6e6
        out = {"n_major": int(s.size), "gap_median_h": float(np.median(g))}
        sel = g[(g >= 20) & (g <= 30)]
        out["daily_shift_median_h"] = float(np.median(sel - 24)) if sel.size else None
        hrs = np.array([datetime.fromtimestamp(x / 1000, UTC).hour for x in s])
        obs = np.bincount(hrs // 6, minlength=4)
        out["hour_bins_6h"] = [int(x) for x in obs]
        out["hour_bins_1h"] = [int(x) for x in np.bincount(hrs, minlength=24)]
        dow = np.array([datetime.fromtimestamp(x / 1000, UTC).weekday() for x in s])
        o7 = np.bincount(dow, minlength=7)
        out["dow_chi2_p"] = float(stats.chisquare(o7).pvalue)
        if k != "readout":
            o24 = np.bincount(hrs, minlength=24)
            out["hour24_chi2_p"] = float(stats.chisquare(o24).pvalue)
            o8 = np.bincount(hrs // 3, minlength=8)
            out["hour8_chi2_p"] = float(stats.chisquare(o8).pvalue)
        res[k] = out
    # order relative to T1
    t1 = np.sort(starts["T1"])
    for k in ("readout", "cz"):
        o = np.sort(starts[k])
        offs = []
        for a in t1:
            j = np.argmin(np.abs(o - a))
            if abs(o[j] - a) <= 12 * 3.6e6:
                offs.append((o[j] - a) / 3.6e6)
        res[k]["offset_from_T1_h_median"] = float(np.median(offs))
        res[k]["offset_n"] = len(offs)
        res[k]["offset_q25_q75"] = [float(x) for x in np.quantile(offs, [0.25, 0.75])]
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
