"""Verifier: lf stamps later than last_update_date and than the filing poll; state-flag checks."""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "device" / "v7_lf_late.json"


def main() -> None:
    dd = ddload.DD()
    fms = dd.file_ms
    hc = dd.file("has_configuration").astype(bool)
    names = dd.meta["lf_names"]
    lfd = np.array(dd.d("gen.lf"))[:, names.index("lf_100")]
    res: dict = {
        "header": ddload.result_header("verify/device", "analysis/verify/device/v7_lf_late.py")
    }
    late = lfd > fms
    res["late_files"] = int(late.sum())
    res["late_live"] = int((late & hc).sum())
    res["late_hist"] = int((late & ~hc).sum())
    lag = (lfd - fms)[late] / 3.6e6
    res["lag_h_median"] = float(np.median(lag))
    res["lag_h_max"] = float(lag.max())
    res["lag_h_min"] = float(lag.min())
    # distribution of lf stamp minus last_update over ALL files (is it a constant offset?)
    allg = (lfd - fms) / 3.6e6
    res["all_files_lf_minus_last_update_h_quantiles"] = [
        float(x) for x in np.quantile(allg, [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1])
    ]
    # ledger
    newrow = {}
    for r in dd.meta["ledger"]:
        if r["decision"] == "new":
            newrow.setdefault(r["last_update_date"], r["poll_time_utc"])
    stems = dd.stems
    n_checked = 0
    n_before = 0
    diffs = []
    for i in np.flatnonzero(late & hc):
        key = stems[i].replace(".json", "")
        if key in newrow:
            n_checked += 1
            pt = datetime.fromisoformat(newrow[key].replace("Z", "+00:00")).timestamp() * 1000
            diffs.append((pt - lfd[i]) / 3.6e6)
            if pt < lfd[i]:
                n_before += 1
    res["live_late_with_ledger_new"] = n_checked
    res["poll_before_lf_stamp"] = n_before
    res["poll_minus_lf_h_median"] = float(np.median(diffs))
    res["poll_minus_lf_h_min"] = float(np.min(diffs))
    # states
    sid = dd.file("state_id")
    flag = dd.file("is_new_state")
    nf = {}
    for i in range(dd.n_files):
        if sid[i] >= 0:
            nf.setdefault(int(sid[i]), []).append(i)
    res["states"] = len(nf)
    res["states_with_exactly_one_flag"] = int(sum(1 for v in nf.values() if flag[v].sum() == 1))
    notfirst = [k for k, v in nf.items() if not flag[v[0]]]
    res["states_flag_not_on_first_file"] = len(notfirst)
    res["notfirst_first_is_hist"] = int(sum(1 for k in notfirst if not hc[nf[k][0]]))
    res["files_without_state"] = int(np.sum(sid < 0))
    ddload.write_json(OUT, res)
    print("done")


if __name__ == "__main__":
    main()
