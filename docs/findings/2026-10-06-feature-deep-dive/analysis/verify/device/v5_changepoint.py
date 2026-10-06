"""Verifier: readout step at the 2026-06-08 length change against controls and neighbours."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v5_changepoint.json"


def ms(text: str) -> float:
    return datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp() * 1000


def device_median_series(dd, field, mask, n_ent):
    ser = ddload.series(dd, field, rule=ddload.MEASURED, mask=mask, transform_ok=True)
    first = dd.file_ms[0]
    t = np.concatenate([s.t_ms[s.t_ms >= first] for s in ser])
    y = np.concatenate([np.log10(s.y[s.t_ms >= first]) for s in ser])
    o = np.argsort(t, kind="stable")
    t, y = t[o], y[o]
    cut = np.flatnonzero(np.diff(t) > 15 * 60e3) + 1
    ts, ys = [], []
    for gt, gy in zip(np.split(t, cut), np.split(y, cut), strict=True):
        if gt.size >= n_ent / 2:
            ts.append(gt[0])
            ys.append(np.median(gy))
    return np.array(ts), np.array(ys)


def main() -> None:
    dd = ddload.DD()
    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v5_changepoint.py")
    }
    ev = {"len1": ms("2026-06-08T18:56:28"), "len2": ms("2026-07-30T21:09:17")}
    specs = {
        "readout": ("q.readout_error", None, 156),
        "init_error": ("q.init_error", None, 156),
        "T1": ("q.T1", None, 156),
        "T2": ("q.T2", None, 156),
        "sx": ("g1.sx.gate_error", ddload.placeholder_error, 156),
    }
    for name, (fld, mask, n) in specs.items():
        t, y = device_median_series(dd, fld, mask, n)
        out = {"n_rounds": int(t.size)}
        for en, te in ev.items():
            for k in (5, 10, 20):
                pre = y[t < te][-k:]
                post = y[t >= te][:k]
                out[f"{en}_k{k}_post_minus_pre_median_decades"] = float(
                    np.median(post) - np.median(pre)
                )
            # MAD of round-to-round differences as scale
        d = np.diff(y)
        out["robust_sd_of_round_diffs"] = float(1.4826 * np.median(np.abs(d - np.median(d))))
        if name == "readout":
            # all steps: 10-round median windows, find the largest absolute step anywhere
            k = 10
            steps = []
            for i in range(k, len(y) - k):
                steps.append((float(np.median(y[i : i + k]) - np.median(y[i - k : i])), i))
            steps_sorted = sorted(steps, key=lambda s: s[0])
            out["largest_drops_k10"] = [
                (round(s, 4), datetime.fromtimestamp(t[i] / 1000, UTC).strftime("%Y-%m-%dT%H:%M"))
                for s, i in steps_sorted[:6]
            ]
            m = (t >= ms("2026-05-13T00:00:00")) & (t < ms("2026-06-08T00:00:00"))
            out["median_pre_May13_to_Jun07"] = float(np.median(y[m]))
            m2 = (t >= ms("2026-06-09T00:00:00")) & (t < ms("2026-07-30T00:00:00"))
            out["median_Jun09_to_Jul29"] = float(np.median(y[m2]))
            out["median_first10"] = float(np.median(y[:10]))
            out["median_last10_before_len1"] = float(np.median(y[t < ev["len1"]][-10:]))
        res[name] = out
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
