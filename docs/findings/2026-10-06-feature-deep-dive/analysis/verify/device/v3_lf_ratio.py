"""Verifier: lf_N against its chain's isolated cz errors, and chain re-selection effects."""

import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v3_lf_ratio.json"


def main() -> None:
    dd = ddload.DD()
    fms = dd.file_ms
    names = dd.meta["lf_names"]
    lf = np.array(dd.v("gen.lf"), dtype=np.float64)
    lfd = np.array(dd.d("gen.lf"), dtype=np.float64)
    edges = [tuple(int(x) for x in e) for e in dd.meta["directed_edges"]]
    col_of = {}
    for k, (a, b) in enumerate(edges):
        if a < b:
            col_of[(a, b)] = k
    ser = ddload.series(dd, "g2.cz.gate_error", rule=ddload.MEASURED, mask=ddload.placeholder_error)
    by = {s.entity: s for s in ser}

    def cz_at(pair: tuple[int, int], t: float) -> float:
        a, b = min(pair), max(pair)
        s = by.get(col_of[(a, b)])
        if s is None:
            return float("nan")
        i = np.searchsorted(s.t_ms, t, side="right") - 1
        return float("nan") if i < 0 else float(s.y[i])

    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v3_lf_ratio.py")
    }
    j100 = names.index("lf_100")
    stamp = lfd[:, j100]
    ev = np.flatnonzero(np.r_[True, stamp[1:] != stamp[:-1]])
    ratios: dict[int, list[float]] = {}
    ratio_by_ev = {}
    chains100 = []
    skipped = 0
    rows = []
    for fi in ev:
        t = stamp[fi]
        ch100 = dd.lf_chain(int(fi), j100)
        chains100.append(tuple(ch100) if ch100 else None)
        for n_len in (10, 50, 100):
            j = names.index(f"lf_{n_len}")
            ch = dd.lf_chain(int(fi), j)
            if ch is None or len(ch) != n_len:
                rows.append((n_len, "len", None if ch is None else len(ch)))
                continue
            lns = 0.0
            ok = True
            for a, b in pairwise(ch):
                e = cz_at((a, b), t)
                if not np.isfinite(e):
                    ok = False
                    break
                lns += np.log(1 - 1.25 * e)
            if not ok:
                skipped += 1
                continue
            r = np.log(lf[fi, j]) / lns
            ratios.setdefault(n_len, []).append(float(r))
            if n_len == 100:
                ratio_by_ev[int(fi)] = (float(np.log(lf[fi, j])), float(lns), float(r))
    for n_len, lst in ratios.items():
        res[f"ratio_lf{n_len}"] = {
            "n": len(lst),
            "median": float(np.median(lst)),
            "q25_q75": [float(x) for x in np.quantile(lst, [0.25, 0.75])],
        }
    res["skipped_event_name_pairs_placeholder_cz"] = skipped
    res["chain_len_mismatch_rows"] = len(rows)
    fis = sorted(ratio_by_ev)
    lnlf = np.array([ratio_by_ev[i][0] for i in fis])
    lnpred = np.array([ratio_by_ev[i][1] for i in fis])
    rho, p = stats.spearmanr(lnlf, lnpred)
    res["spearman_lnlf100_lnpred100"] = {"rho": float(rho), "p": float(p), "n": len(fis)}
    # Same-chain vs different-chain consecutive pairs, all events with lf_100 chain
    d_same, d_diff = [], []
    uniq = {c for c in chains100 if c}
    res["distinct_lf100_chains"] = len(uniq)
    res["n_events"] = len(ev)
    lflog = np.log(lf[ev, j100])
    for i in range(1, len(ev)):
        if stamp[ev[i - 1]] < fms[0]:
            continue
        (d_same if chains100[i] == chains100[i - 1] else d_diff).append(
            float(lflog[i] - lflog[i - 1])
        )
    res["consecutive_pairs_in_archive"] = {"same": len(d_same), "diff": len(d_diff)}

    def rsd(x):
        x = np.asarray(x)
        return float(1.4826 * np.median(np.abs(x - np.median(x))))

    res["robust_sd_dln_same"] = rsd(d_same)
    res["robust_sd_dln_diff"] = rsd(d_diff)
    res["rms_dln_same"] = float(np.sqrt(np.mean(np.square(d_same))))
    res["rms_dln_diff"] = float(np.sqrt(np.mean(np.square(d_diff))))
    # permutation test: robust SD difference
    rng = np.random.default_rng(1)
    allv = np.array(d_same + d_diff)
    ns = len(d_same)
    obs = rsd(d_diff) - rsd(d_same)
    cnt = 0
    for _ in range(5000):
        rng.shuffle(allv)
        if rsd(allv[ns:]) - rsd(allv[:ns]) >= obs:
            cnt += 1
    res["perm_p_sd_diff_ge_same"] = (cnt + 1) / 5001
    # Variance F-type test via Levene
    res["levene_p"] = float(stats.levene(d_same, d_diff).pvalue)
    # time gaps between pairs same vs diff (confound)
    gs, gd = [], []
    for i in range(1, len(ev)):
        if stamp[ev[i - 1]] < fms[0]:
            continue
        g = (stamp[ev[i]] - stamp[ev[i - 1]]) / 3.6e6
        (gs if chains100[i] == chains100[i - 1] else gd).append(float(g))
    res["median_gap_h_same"] = float(np.median(gs))
    res["median_gap_h_diff"] = float(np.median(gd))
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
