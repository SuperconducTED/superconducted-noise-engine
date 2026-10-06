"""The two device-wide readout-length changes as natural experiments.

Writes ``results/readout/length_changes.json``. For each change (1560 -> 1700 ns on
2026-06-08T18:56:28Z, 1700 -> 1660 ns on 2026-07-30T21:09:17Z) and each window length
(7 and 14 days, with a 6 h guard on each side of the change):

- per qubit, the median of each readout quantity before and after; the device summary is the
  median over qubits of ``log10(after / before)``, the share of qubits that went up, and a
  Wilcoxon signed-rank p-value over qubits;
- the same statistic at every other day of the archive (a placebo distribution, excluding
  days within one window of either change), so a change can be compared with the ordinary
  week-to-week movement;
- the decay expected from ``T1`` over the readout, ``1 - exp(-t / T1)``, with the full length
  and with half of it (Krantz et al. 2019, eq. 173, ``tau_ro = tau_rd + tau_s / 2``), before
  and after, holding each qubit's ``T1`` at its before-window median, so that the predicted
  change in P(0|1) from the length alone can be compared with the observed change.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc

GUARD_H = 6.0
CHANGES = ((rc.CHANGE_1, 1560.0, 1700.0), (rc.CHANGE_2, 1700.0, 1660.0))


def per_qubit(ns: rc.NoiseSeries, kinds: tuple[str, ...]) -> list[tuple[np.ndarray, np.ndarray]]:
    out = []
    for x, kind in zip(ns.series, ns.kind, strict=True):
        y = np.asarray(x.y)
        ok = np.isfinite(y) & np.isin(kind, kinds)
        out.append((x.t_ms[ok] / 3.6e6, y[ok]))
    return out


def window_medians(data: list[tuple[np.ndarray, np.ndarray]], lo: float, hi: float) -> np.ndarray:
    med = np.full(len(data), np.nan)
    for q, (t, y) in enumerate(data):
        a, b = np.searchsorted(t, lo), np.searchsorted(t, hi)
        if b - a >= 3:
            med[q] = float(np.median(y[a:b]))
    return med


def compare(data: list[tuple[np.ndarray, np.ndarray]], t0: float, w: float) -> dict[str, Any]:
    before = window_medians(data, t0 - w, t0 - GUARD_H)
    after = window_medians(data, t0 + GUARD_H, t0 + w)
    ok = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
    d = np.log10(after[ok] / before[ok])
    res: dict[str, Any] = {
        "qubits": int(ok.sum()),
        "median_log10_after_over_before": round(float(np.median(d)), 4),
        "share_qubits_up": round(float(np.mean(d > 0)), 4),
        "device_median_before": float(f"{np.median(before[ok]):.5g}"),
        "device_median_after": float(f"{np.median(after[ok]):.5g}"),
        "per_qubit_log10_change_q": rc.quantiles(d),
    }
    if ok.sum() >= 10 and np.any(d != 0):
        res["wilcoxon_p"] = float(f"{stats.wilcoxon(d).pvalue:.3g}")
    return res


def placebo(
    data: list[tuple[np.ndarray, np.ndarray]],
    t_lo: float,
    t_hi: float,
    w: float,
    avoid: list[float],
) -> np.ndarray:
    vals = []
    t = t_lo + w
    while t <= t_hi - w:
        if all(abs(t - a) > w for a in avoid):
            before = window_medians(data, t - w, t - GUARD_H)
            after = window_medians(data, t + GUARD_H, t + w)
            ok = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
            if ok.sum() >= 100:
                vals.append(float(np.median(np.log10(after[ok] / before[ok]))))
        t += 24.0
    return np.array(vals)


def main() -> None:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    ns = rc.noise_series(r, c, s)
    t1_ev = rc.stamp_events(np.array(dd.v("q.T1")), np.array(dd.d("q.T1")))
    t1_data: list[tuple[np.ndarray, np.ndarray]] = [(np.empty(0), np.empty(0)) for _ in range(156)]
    for x in t1_ev:
        t1_data[x.entity] = (x.t_ms / 3.6e6, np.asarray(x.y))
    t_lo = float(dd.file_ms[0]) / 3.6e6
    t_hi = float(dd.file_ms[-1]) / 3.6e6
    avoid = [rc.iso_ms(cg[0]) / 3.6e6 for cg in CHANGES]

    # Asymmetry series: P(0|1) - P(1|0) at each session (not log; may be negative).
    asym = rc.NoiseSeries([], [], [])
    for a, b in zip(ns["p0g1_fresh"].series, ns["p1g0"].series, strict=True):
        asym.series.append(
            ddload.Series(
                entity=a.entity,
                t_ms=a.t_ms,
                file_idx=a.file_idx,
                y=np.asarray(a.y) - np.asarray(b.y),
            )
        )
    asym.kind = ns["p0g1_fresh"].kind

    fields = {"ro": ns["ro"], "p0g1_fresh": ns["p0g1_fresh"], "p1g0": ns["p1g0"]}
    out: dict[str, Any] = {"n_files": dd.n_files, "guard_h": GUARD_H, "changes": []}
    for stamp, t_before, t_after in CHANGES:
        t0 = rc.iso_ms(stamp) / 3.6e6
        file_i = int(np.searchsorted(dd.file_ms, rc.iso_ms(stamp)))
        entry: dict[str, Any] = {
            "change": stamp,
            "file": dd.stems[file_i][:15],
            "length_ns": [t_before, t_after],
            "windows": {},
        }
        for w_days in (7, 14):
            w = 24.0 * w_days
            win: dict[str, Any] = {}
            for name, nsf in fields.items():
                for kinds_label, kinds in (
                    ("all_sessions", ("even", "mixed")),
                    ("mixed_only", ("mixed",)),
                ):
                    data = per_qubit(nsf, kinds)
                    obs = compare(data, t0, w)
                    pl = placebo(data, t_lo, t_hi, w, avoid)
                    obs["placebo_days"] = int(pl.size)
                    obs["placebo_q05_q50_q95"] = [
                        round(float(v), 4) for v in np.quantile(pl, [0.05, 0.5, 0.95])
                    ]
                    obs["placebo_share_abs_ge_observed"] = round(
                        float(np.mean(np.abs(pl) >= abs(obs["median_log10_after_over_before"]))), 4
                    )
                    win[f"{name}_{kinds_label}"] = obs
            # Asymmetry, linear difference of medians.
            ad = per_qubit(asym, ("even", "mixed"))
            b_ = window_medians(ad, t0 - w, t0 - GUARD_H)
            a_ = window_medians(ad, t0 + GUARD_H, t0 + w)
            ok = np.isfinite(a_) & np.isfinite(b_)
            win["asymmetry_p0g1_minus_p1g0"] = {
                "qubits": int(ok.sum()),
                "median_change": float(f"{np.median(a_[ok] - b_[ok]):.5g}"),
                "median_before": float(f"{np.median(b_[ok]):.5g}"),
                "median_after": float(f"{np.median(a_[ok]):.5g}"),
                "wilcoxon_p": float(f"{stats.wilcoxon(a_[ok] - b_[ok]).pvalue:.3g}"),
            }
            # T1 control and the decay the length change alone predicts.
            t1b = window_medians(t1_data, t0 - w, t0 - GUARD_H)
            t1a = window_medians(t1_data, t0 + GUARD_H, t0 + w)
            okt = np.isfinite(t1b) & np.isfinite(t1a) & (t1b > 0) & (t1a > 0)
            pl_t1 = placebo(t1_data, t_lo, t_hi, w, avoid)
            win["t1_control"] = {
                "qubits": int(okt.sum()),
                "median_log10_after_over_before": round(
                    float(np.median(np.log10(t1a[okt] / t1b[okt]))), 4
                ),
                "device_median_before_us": round(float(np.median(t1b[okt])), 2),
                "placebo_q05_q50_q95": [
                    round(float(v), 4) for v in np.quantile(pl_t1, [0.05, 0.5, 0.95])
                ],
            }
            pred: dict[str, Any] = {}
            for label, frac in (("full_length", 1.0), ("half_length", 0.5)):
                db = 1.0 - np.exp(-frac * t_before * 1e-3 / t1b[okt])
                da = 1.0 - np.exp(-frac * t_after * 1e-3 / t1b[okt])
                pred[label] = {
                    "median_decay_before": float(f"{np.median(db):.5g}"),
                    "median_predicted_change": float(f"{np.median(da - db):.5g}"),
                }
            p0b = window_medians(
                per_qubit(ns["p0g1_fresh"], ("even", "mixed")), t0 - w, t0 - GUARD_H
            )
            p0a = window_medians(
                per_qubit(ns["p0g1_fresh"], ("even", "mixed")), t0 + GUARD_H, t0 + w
            )
            okp = np.isfinite(p0b) & np.isfinite(p0a)
            pred["observed_median_change_p0g1"] = float(f"{np.median(p0a[okp] - p0b[okp]):.5g}")
            pred["observed_median_change_asymmetry"] = win["asymmetry_p0g1_minus_p1g0"][
                "median_change"
            ]
            win["decay_prediction_t1_held_at_before"] = pred
            # Sessions in each window.
            for side, lo, hi in (("before", t0 - w, t0 - GUARD_H), ("after", t0 + GUARD_H, t0 + w)):
                sel = (s.start_ms / 3.6e6 >= lo) & (s.start_ms / 3.6e6 < hi)
                win[f"sessions_{side}"] = {
                    k: int(np.sum(sel & (s.kind == k))) for k in ("even", "mixed")
                }
            entry["windows"][f"{w_days}d"] = win
        out["changes"].append(entry)
    th = np.array(dd.v("g1.measure.threshold"))
    out["measure_threshold_first_file"] = dd.stems[
        int(np.flatnonzero(np.isfinite(th).any(axis=1))[0])
    ][:15]
    rc.write("length_changes.json", "length_changes.py", out)


if __name__ == "__main__":
    main()
