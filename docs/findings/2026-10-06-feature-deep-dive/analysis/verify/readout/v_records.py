"""Independent re-computation of the record-level readout facts of 03-readout-measurement.md.

Written from ddload only (the owner's code is not imported). Recomputes: stamp classes and
the mean rule, the stale P(0|1) records and their rotating groups, the 1/4096 grid test of
the recovered P(0|1) (and whether that test can fail), the reset length identity, and the
device-wide all-or-none threshold changes.

Writes ``results/verify/readout/records_check.json``.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

OUT = Path(__file__).resolve().parents[3] / "results" / "verify" / "readout" / "records_check.json"
WIN = 10 * 60e3


def main() -> None:
    dd = ddload.DD()
    ro = np.array(dd.v("q.readout_error"), float)
    a = np.array(dd.v("q.prob_meas0_prep1"), float)  # P(0|1)
    b = np.array(dd.v("q.prob_meas1_prep0"), float)  # P(1|0)
    dro = np.array(dd.d("q.readout_error"), float)
    da = np.array(dd.d("q.prob_meas0_prep1"), float)
    db = np.array(dd.d("q.prob_meas1_prep0"), float)
    present = np.isfinite(ro) & np.isfinite(a) & np.isfinite(b)
    same3 = present & (dro == da) & (dro == db)
    gap = np.maximum(np.abs(dro - da), np.abs(dro - db))
    stag = present & ~same3 & (gap <= WIN)
    stale = present & ((dro - da) > WIN)
    mean_ok = present & (np.abs(ro - (a + b) / 2) < 1e-12)
    fail = present & ~mean_ok
    out: dict = ddload.result_header("verify/readout", "v_records.py")
    out["records"] = int(present.sum())
    out["same3"] = int(same3.sum())
    out["same3_share"] = round(float(same3.sum() / present.sum()), 4)
    out["staggered"] = int(stag.sum())
    out["stale"] = int(stale.sum())
    out["mean_fail"] = int(fail.sum())
    out["mean_fail_and_stale"] = int((fail & stale).sum())
    out["mean_ok_within_same3_or_staggered"] = int((mean_ok & (same3 | stag)).sum())
    out["mean_fail_within_same3_or_staggered"] = int((fail & (same3 | stag)).sum())
    lag = (dro - da)[fail & stale] / 3.6e6
    out["stale_fail_lag_median_h"] = round(float(np.median(lag)), 3)

    # rotating group: qubits with stale records, by index mod 17, by file
    q = np.array(dd.meta["qubits"])
    stems = dd.stems
    grp = {}
    for r in (9, 10, 16):
        cols = np.flatnonzero(q % 17 == r)
        st = stale[:, cols]
        files = np.flatnonzero(st.any(axis=1))
        grp[str(r)] = {
            "qubits": int(cols.size),
            "stale_records": int(st.sum()),
            "first_file": stems[files[0]] if files.size else None,
            "last_file": stems[files[-1]] if files.size else None,
        }
    out["groups_mod17"] = grp
    out["stale_records_on_other_residues"] = int(stale[:, ~np.isin(q % 17, [9, 10, 16])].sum())
    out["stale_qubits"] = int(stale.any(axis=0).sum())

    # grid test of the recovered P(0|1); can it fail?
    rec = stale & (np.abs(dro - db) <= WIN)
    fresh = 2 * ro[rec] - b[rec]
    on_grid = np.abs(fresh * 4096 - np.round(fresh * 4096)) < 1e-6
    out["recoverable_records"] = int(rec.sum())
    out["recovered_on_4096_grid_share"] = round(float(on_grid.mean()), 5)
    ro_on_8192 = np.abs(ro[present] * 8192 - np.round(ro[present] * 8192)) < 1e-6
    b_on_4096 = np.abs(b[present] * 4096 - np.round(b[present] * 4096)) < 1e-6
    out["ro_on_8192_grid_share_all_records"] = round(float(ro_on_8192.mean()), 5)
    out["p1g0_on_4096_grid_share_all_records"] = round(float(b_on_4096.mean()), 5)
    out["recovered_in_unit_interval_share"] = round(float(((fresh >= 0) & (fresh <= 1)).mean()), 5)
    # does the recovered value look like the other (non-stale) P(0|1)? compare to stale one
    out["recovered_vs_published_stale_median_ratio"] = round(
        float(np.median(fresh[fresh > 0] / a[rec][fresh > 0])), 4
    )
    # same grid arithmetic would hold for ANY P(0|1) on the 4096 grid: shuffle placebo
    rng = np.random.default_rng(3)
    fake_a = rng.permutation(a[present])
    fake_ro = (fake_a + b[present]) / 2
    fr = 2 * fake_ro - b[present]
    out["placebo_shuffled_p0g1_recovered_on_grid"] = round(
        float((np.abs(fr * 4096 - np.round(fr * 4096)) < 1e-6).mean()), 5
    )

    # reset = readout length + 24 ns
    rl = np.array(dd.v("q.readout_length"), float)
    rs = np.array(dd.v("g1.reset.gate_length"), float)
    ok = np.isfinite(rl) & np.isfinite(rs)
    out["reset_minus_readout_unique"] = sorted({float(x) for x in np.unique((rs - rl)[ok])})
    out["reset_records"] = int(ok.sum())
    ml = np.array(dd.v("g1.measure.gate_length"), float)
    ok2 = np.isfinite(rl) & np.isfinite(ml)
    out["readout_len_equals_measure_len_all"] = bool(np.all(rl[ok2] == ml[ok2]))
    out["readout_length_values"] = {
        str(int(v)): int((rl[np.isfinite(rl)] == v).sum()) for v in np.unique(rl[np.isfinite(rl)])
    }
    ro_m = np.array(dd.v("g1.measure.gate_error"), float)
    ok3 = np.isfinite(ro_m) & np.isfinite(ro)
    out["measure_error_equals_ro_all"] = bool(np.all(ro_m[ok3] == ro[ok3]))
    out["measure_error_records"] = int(ok3.sum())

    # thresholds: change files and all-or-none
    th = np.array(dd.v("g1.measure.threshold"), float)
    nonnan = np.isfinite(th)
    first = int(np.flatnonzero(nonnan.any(axis=1))[0])
    ch_files = []
    nq_changed = []
    for f in range(first + 1, th.shape[0]):
        both = nonnan[f] & nonnan[f - 1]
        if both.sum() == 0:
            continue
        chg = both & (th[f] != th[f - 1])
        if chg.any():
            ch_files.append(f)
            nq_changed.append(int(chg.sum()))
    out["threshold_first_file"] = stems[first]
    out["threshold_change_files"] = len(ch_files)
    out["threshold_change_qubits_per_file_unique"] = sorted(set(nq_changed))
    mr = np.array(dd.v("g1.measure_reset.threshold"), float)
    both = np.isfinite(th) & np.isfinite(mr)
    out["measure_vs_measure_reset_threshold_shared"] = int(both.sum())
    out["measure_vs_measure_reset_threshold_equal_all"] = bool(np.all(th[both] == mr[both]))
    ddload.write_json(OUT, out)
    print("ok")


main()
