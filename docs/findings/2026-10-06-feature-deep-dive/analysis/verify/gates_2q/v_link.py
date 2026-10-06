# ruff: noqa: N806, N803
"""Independent check of the between-coupler link numbers (cz error vs sx and vs coherence limit).

Written from ddload only. Per-coupler median cz event error, per-qubit median sx error
(placeholders masked) and per-qubit median T1 and T2; the coherence limit is evaluated at each
coupler's own qubit medians and a 68 ns gate. Spearman and a rank-based partial correlation.

Writes ``results/verify/gates_2q/link_check.json``.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "verify" / "gates_2q" / "link_check.json"


def f(x, nd=3):
    return float(f"{x:.{nd}g}")


def partial(x, y, z):
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)

    def res(a, b):
        A = np.c_[np.ones_like(b), b]
        return a - A @ np.linalg.lstsq(A, a, rcond=None)[0]

    return float(np.corrcoef(res(rx, rz), res(ry, rz))[0, 1])


def limit(t_ns, t1a, t2a, t1b, t2b):
    t = t_ns * 1e-9

    def fk(t1, t2):
        t1, t2 = t1 * 1e-6, t2 * 1e-6
        return (1 + np.exp(-t / t1) + 2 * np.exp(-t / t2)) / 4

    return 1 - (4 * fk(t1a, t2a) * fk(t1b, t2b) + 1) / 5


def main():
    dd = ddload.DD()
    edges = [tuple(int(x) for x in e) for e in dd.entities("g2.cz.gate_error")]
    fwd = [i for i, (a, b) in enumerate(edges) if a < b]
    keep = set(fwd)
    ser = [
        s
        for s in ddload.series(
            dd, "g2.cz.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error
        )
        if s.entity in keep
    ]
    qs = [int(q) for q in dd.meta["qubits"]]
    qpos = {q: i for i, q in enumerate(qs)}

    def qmed(field, ph=False):
        v = np.array(dd.v(field), float)
        v[~np.isfinite(v)] = np.nan
        if ph:
            v[v >= 1] = np.nan
        v[v <= 0] = np.nan
        with np.errstate(all="ignore"):
            return np.nanmedian(v, axis=0)

    sx, ro = qmed("g1.sx.gate_error", True), qmed("q.readout_error")
    t1, t2 = qmed("q.T1"), qmed("q.T2")
    err, sxs, lims, ros = [], [], [], []
    for s in ser:
        a, b = edges[s.entity]
        ia, ib = qpos[a], qpos[b]
        vals = [sx[ia], sx[ib], t1[ia], t2[ia], t1[ib], t2[ib], ro[ia], ro[ib]]
        if not np.all(np.isfinite(vals)):
            continue
        err.append(float(np.median(np.asarray(s.y, float))))
        sxs.append(sx[ia] + sx[ib])
        lims.append(limit(68, t1[ia], t2[ia], t1[ib], t2[ib]))
        ros.append(ro[ia] + ro[ib])
    err, sxs, lims, ros = map(np.array, (err, sxs, lims, ros))
    out = {"header": ddload.result_header("verify/gates_2q", "v_link.py")}
    out["n_couplers"] = int(err.size)
    out["spearman_err_vs_limit"] = f(float(spearmanr(err, lims)[0]))
    out["spearman_err_vs_sx_sum"] = f(float(spearmanr(err, sxs)[0]))
    out["spearman_err_vs_ro_sum"] = f(float(spearmanr(err, ros)[0]))
    out["partial_err_sx_given_limit"] = f(partial(err, sxs, lims))
    out["partial_err_limit_given_sx"] = f(partial(err, lims, sxs))
    out["partial_err_ro_given_limit_sx"] = f(
        float(
            np.corrcoef(
                *[
                    (lambda a, B: a - B @ np.linalg.lstsq(B, a, rcond=None)[0])(
                        rankdata(v), np.c_[np.ones(err.size), rankdata(lims), rankdata(sxs)]
                    )
                    for v in (err, ros)
                ]
            )[0, 1]
        )
    )
    ddload.write_json(OUT, out)
    print(out)


if __name__ == "__main__":
    main()
