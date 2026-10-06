"""Verifier of 06-device-time-topology.md: files, graph, lf level and trend, states.

Independent of analysis/device/ (written from ddload only).
"""

import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v1_basics.json"


def main() -> None:
    dd = ddload.DD()
    fms = dd.file_ms
    n = dd.n_files
    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v1_basics.py")
    }
    res["n_files"] = n
    hc = dd.file("has_configuration")
    res["n_live"] = int(hc.sum())
    res["n_hist"] = int(n - hc.sum())
    month = np.array([datetime.fromtimestamp(t / 1000, UTC).strftime("%Y-%m") for t in fms])
    pm = {}
    for m in sorted(set(month)):
        idx = np.flatnonzero(month == m)
        pm[m] = {"files": int(idx.size), "hist": int((hc[idx] == 0).sum())}
    res["per_month"] = pm
    gaps = np.diff(fms) / 3.6e6
    res["gap_median_h"] = float(np.median(gaps))
    live = np.flatnonzero(hc == 1)
    res["gap_live_median_h"] = float(np.median(np.diff(fms[live]) / 3.6e6))
    res["n_gaps_gt_12h"] = int((gaps > 12).sum())
    res["n_gaps_gt_12h_between_live"] = int(
        sum(1 for i in np.flatnonzero(gaps > 12) if hc[i] == 1 and hc[i + 1] == 1)
    )
    res["max_gap_h"] = float(gaps.max())
    # graph
    n_q = len(dd.meta["qubits"])
    edges = {tuple(sorted((int(a), int(b)))) for a, b in dd.meta["coupling_map"]}
    adj = [[] for _ in range(n_q)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    deg = np.array([len(x) for x in adj])
    res["n_q"] = n_q
    res["n_couplers"] = len(edges)
    res["degree_counts"] = {int(k): int((deg == k).sum()) for k in np.unique(deg)}
    # BFS: diameter, colouring, girth
    diam = 0
    colour = {0: 0}
    q = deque([0])
    bip = True
    while q:
        u = q.popleft()
        for w in adj[u]:
            if w not in colour:
                colour[w] = 1 - colour[u]
                q.append(w)
            elif colour[w] == colour[u]:
                bip = False
    res["connected"] = len(colour) == n_q
    res["bipartite"] = bip
    res["class_sizes"] = sorted([sum(1 for c in colour.values() if c == k) for k in (0, 1)])
    girth = 10**9
    tot = 0
    cnt = 0
    for s in range(n_q):
        dist = {s: 0}
        par = {s: -1}
        qq = deque([s])
        while qq:
            u = qq.popleft()
            for w in adj[u]:
                if w not in dist:
                    dist[w] = dist[u] + 1
                    par[w] = u
                    qq.append(w)
                elif par[u] != w:
                    girth = min(girth, dist[u] + dist[w] + 1)
        diam = max(diam, max(dist.values()))
        tot += sum(dist.values())
        cnt += n_q - 1
    res["diameter"] = diam
    res["girth"] = girth
    res["cycle_rank"] = len(edges) - n_q + 1
    res["mean_hop"] = tot / cnt
    # lf
    lf = np.array(dd.v("gen.lf"), dtype=np.float64)
    lfd = np.array(dd.d("gen.lf"), dtype=np.float64)
    names = dd.meta["lf_names"]
    j100 = names.index("lf_100")
    stamp = lfd[:, j100]
    ev = np.r_[True, stamp[1:] != stamp[:-1]]
    first_ms = fms[0]
    ev_idx = np.flatnonzero(ev)
    res["lf_events_all"] = int(ev.sum())
    res["lf_events_in_archive"] = int((stamp[ev_idx] >= first_ms).sum())
    res["lf_stamp_first"] = datetime.fromtimestamp(stamp[0] / 1000, UTC).isoformat()
    v100 = lf[ev_idx, j100]
    res["lf100_median"] = float(np.median(v100))
    res["lf100_min_max"] = [float(v100.min()), float(v100.max())]
    eplg = 0.8 * (1 - v100 ** (1 / 99))
    res["eplg100_avg_median"] = float(np.median(eplg))
    sel = stamp[ev_idx] >= first_ms
    t = stamp[ev_idx][sel]
    rho, p = stats.spearmanr(t, eplg[sel])
    res["eplg_spearman_in_archive"] = {"rho": float(rho), "p": float(p), "n": int(sel.sum())}
    # all events including carried-in
    rho3, p3 = stats.spearmanr(stamp[ev_idx], eplg)
    res["eplg_spearman_all_events"] = {"rho": float(rho3), "p": float(p3), "n": len(ev_idx)}
    # monotone lf_N within event
    arr = lf[ev_idx][:, :]
    res["lf_monotone_events"] = int(np.sum(np.all(np.diff(arr, axis=1) <= 1e-15, axis=1)))
    # lag-1 autocorrelation of changes of log EPLG for lf_100 (in-archive events)
    y = np.log(eplg[sel])
    dy = np.diff(y)
    res["lf100_lag1_acf_dlogeplg"] = float(np.corrcoef(dy[:-1], dy[1:])[0, 1])
    # states
    sid = dd.file("state_id")
    res["n_states"] = (
        len(np.unique(sid[sid >= 0])) if sid.dtype.kind in "iu" else len(np.unique(sid))
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
