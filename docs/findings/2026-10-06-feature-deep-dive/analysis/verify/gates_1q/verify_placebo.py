"""Own placebo scan of the known-date before/after test (claim in section 3 of the document)."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

DAY = 86.4e6
OUT = (
    Path(__file__).resolve().parents[3] / "results" / "verify" / "gates_1q" / "verify_placebo.json"
)


def ms(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp() * 1000


def test(sx, centre):
    d = []
    for s in sx:
        z = np.log10(s.y)
        b = z[(s.t_ms >= centre - 14 * DAY) & (s.t_ms < centre)]
        a = z[(s.t_ms >= centre) & (s.t_ms < centre + 14 * DAY)]
        if a.size >= 3 and b.size >= 3:
            d.append(np.median(a) - np.median(b))
    d = np.array(d)
    return float(np.median(d)), float(stats.wilcoxon(d).pvalue), d.size


def main():
    dd = ddload.DD()
    res = ddload.result_header("verify/gates_1q", "analysis/verify/gates_1q/verify_placebo.py")
    sx = ddload.series(dd, "g1.sx.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    known = {
        "2026-06-08T18:56:28Z": None,
        "2026-07-30T21:09:17Z": None,
        "2026-08-07T03:21:59Z": None,
        "2026-09-02T04:56:24Z": None,
        "2026-09-10T16:56:21Z": None,
    }
    for k in known:
        known[k] = test(sx, ms(k))
    res["known"] = {k: {"shift": v[0], "p": v[1], "n": v[2]} for k, v in known.items()}
    kn = [ms(k) for k in known]
    t0 = min(s.t_ms.min() for s in sx) + 14 * DAY
    t1 = max(s.t_ms.max() for s in sx) - 14 * DAY
    grid = np.arange(t0, t1, DAY)
    grid = [g for g in grid if min(abs(g - k) for k in kn) > 3 * DAY]
    rows = [test(sx, g) for g in grid]
    p = np.array([r[1] for r in rows])
    sh = np.array([abs(r[0]) for r in rows])
    res["placebo"] = {
        "n_dates": len(rows),
        "share_p_lt_0.01": float(np.mean(p < 0.01)),
        "share_p_lt_1e-3": float(np.mean(p < 1e-3)),
        "share_p_lt_1e-5": float(np.mean(p < 1e-5)),
        "min_p": float(p.min()),
        "share_p_le_6.5e-6": float(np.mean(p <= 6.52e-6)),
        "share_abs_shift_ge_0.0148": float(np.mean(sh >= 0.0148)),
        "max_abs_shift": float(sh.max()),
    }
    ddload.write_json(OUT, res)
    print("ok")


if __name__ == "__main__":
    main()
