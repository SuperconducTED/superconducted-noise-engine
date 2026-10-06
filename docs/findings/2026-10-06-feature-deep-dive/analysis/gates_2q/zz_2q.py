"""Static ZZ (``gen.zz``): units, distribution, signs and zeros, update bursts, relations.

Writes ``results/gates_2q/zz.json``. Loads ``gen.zz``, ``g2.cz.gate_error``,
``g2.rzz.gate_error`` and the per-file arrays for the coverage split. ``gen.zz`` is stamped
at document assembly, so its events follow the value-only rule (01-data-layer.md section 4).

"Burst": a file in which at least one coupler's ``zz`` differs from the previous file. The
evidence on whether ``zz`` is measured or derived is assembled only from in-scope fields:
burst synchrony and cadence, the alignment of bursts with cz and rzz rounds, value
resolution, the zeros, and the size of the changes. The alignment of bursts with qubit-level
rounds (readout, T1) belongs to 06 and 07 and is not computed here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/zz_2q.py"
KHZ = 1e6  # GHz to kHz


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    gcol = c.gen_columns(dd, pairs)
    split = c.split_ms(dd)
    fm = dd.file_ms
    zz = np.array(dd.v("gen.zz"))[:, gcol] * KHZ  # files x couplers (canonical order), kHz
    lab = [c.label(p) for p in pairs]
    n_files, n_c = zz.shape

    # Distribution.
    med = np.median(zz, axis=0)
    absmed = np.median(np.abs(zz), axis=0)
    neg = (zz < 0).sum(axis=0)
    zero = (zz == 0).sum(axis=0)
    sign_flips = np.sum(np.diff(np.sign(zz), axis=0) != 0, axis=0)
    # Couplers whose zz hardly ever changes (at most one value change in the archive).
    n_changes = np.sum(np.diff(zz, axis=0) != 0, axis=0)
    frozen = []
    for i in np.flatnonzero(n_changes <= 1):
        col = zz[:, i]
        k = np.flatnonzero(np.diff(col) != 0) + 1
        frozen.append(
            {
                "coupler": lab[i],
                "value_changes": int(n_changes[i]),
                "distinct_values_khz": [c.rnd(float(v)) for v in np.unique(col)],
                "change_file": dd.stems[int(k[0])] if k.size else None,
            }
        )
    zero_rows = []
    for i in np.flatnonzero(zero):
        f = np.flatnonzero(zz[:, i] == 0)
        zero_rows.append(
            {
                "coupler": c.label(pairs[i]),
                "zero_files": int(f.size),
                "first": dd.stems[f[0]],
                "last": dd.stems[f[-1]],
            }
        )
    neg_rows = [
        {
            "coupler": c.label(pairs[i]),
            "negative_files": int(neg[i]),
            "median_khz": c.rnd(float(med[i])),
            "min_khz": c.rnd(float(zz[:, i].min())),
            "max_khz": c.rnd(float(zz[:, i].max())),
            "sign_changes": int(sign_flips[i]),
        }
        for i in np.argsort(-neg)
        if neg[i] > 0
    ]
    distinct = np.unique(zz[np.isfinite(zz)])
    nz = np.sort(np.unique(np.abs(distinct[distinct != 0])))

    # Resolution: significant digits of the shortest round-trip decimal form of each
    # distinct value (in GHz, as IBM writes it).
    raw = np.unique(np.array(dd.v("gen.zz"))[:, gcol])
    sig = []
    for val in raw[raw != 0]:
        mant = repr(float(abs(val))).split("e")[0].replace(".", "").lstrip("0")
        sig.append(len(mant))
    sig_a = np.array(sig, dtype=np.float64)

    # Bursts.
    changed = np.diff(zz, axis=0) != 0  # (n_files - 1) x couplers
    per_file = changed.sum(axis=1)
    burst = np.flatnonzero(per_file > 0) + 1  # file index of each burst
    bt = fm[burst]
    bgap = np.diff(bt) / ddload.MS_PER_HOUR
    hour, _ = c.hour_weekday(bt)
    gap_file = np.diff(fm) / ddload.MS_PER_HOUR  # gap before each file

    # Bursts by the kind of the two consecutive files (live poll or historical fetch): if a
    # historical document carried a differently refreshed general section, transitions
    # between kinds would show more changes than transitions within a kind.
    live = dd.file("has_configuration").astype(bool)
    is_change = per_file > 0  # aligned with file pairs (k-1, k), k = 1..n-1
    kinds: dict[str, Any] = {}
    after = fm[1:] >= split
    for nm, a_live, b_live in (
        ("live_to_live", True, True),
        ("live_to_hist", True, False),
        ("hist_to_live", False, True),
        ("hist_to_hist", False, False),
    ):
        m = after & (live[:-1] == a_live) & (live[1:] == b_live)
        kinds[nm] = {
            "file_pairs_after_split": int(m.sum()),
            "share_with_change": c.rnd(float(np.mean(is_change[m]))) if m.any() else None,
        }
    days_before = (split - fm[0]) / (24 * ddload.MS_PER_HOUR)
    days_after = (fm[-1] - split) / (24 * ddload.MS_PER_HOUR)
    m_live_after = after & live[1:]
    burst_rate = {
        "bursts_per_day_before_split": c.rnd(float(np.sum(bt < split) / days_before)),
        "bursts_per_day_from_split": c.rnd(float(np.sum(bt >= split) / days_after)),
        "bursts_from_split_in_live_files": int(np.sum(is_change & m_live_after)),
        "bursts_from_split_in_historical_files": int(np.sum(is_change & after & ~live[1:])),
        "share_with_change_before_split_all_pairs": c.rnd(float(np.mean(is_change[~after]))),
        "by_file_kind_after_split": kinds,
        "bursts_by_month": {
            str(m): int(n)
            for m, n in zip(
                *np.unique(
                    bt.astype("datetime64[ms]").astype("datetime64[M]").astype(str),
                    return_counts=True,
                ),
                strict=True,
            )
        },
    }

    # Alignment with cz and rzz rounds: files in which at least one cz (rzz) event first
    # appears, against the share of all files that are bursts.
    align: dict[str, Any] = {}
    for gate in c.GATES:
        ser = c.gate_series(dd, gate, fwd)
        ev_files = np.zeros(n_files, dtype=bool)
        for s in ser.values():
            ev_files[s.file_idx[1:]] = True
        is_burst = np.zeros(n_files, dtype=bool)
        is_burst[burst] = True
        align[gate] = {
            "files_with_events": int(ev_files.sum()),
            "bursts_in_event_files": int(np.sum(is_burst & ev_files)),
            "event_files_that_are_bursts": c.rnd(float(np.mean(is_burst[ev_files]))),
            "share_of_all_files_that_are_bursts": c.rnd(float(np.mean(is_burst[1:]))),
        }

    # Change sizes at bursts: relative change of |zz| per coupler.
    rel = []
    for i in range(n_c):
        col = zz[:, i]
        k = np.flatnonzero(changed[:, i]) + 1
        prev = col[k - 1]
        cur = col[k]
        ok = (prev != 0) & (cur != 0) & (np.sign(prev) == np.sign(cur))
        rel.extend(np.log10(np.abs(cur[ok]) / np.abs(prev[ok])).tolist())
    rel_a = np.array(rel)

    # Lag-1 autocorrelation of log |zz| changes (events).
    zz_events = [
        s for s in ddload.series(dd, "gen.zz", rule=ddload.ASSEMBLY) if s.entity in set(gcol)
    ]
    x, y = [], []
    for s in zz_events:
        a = np.abs(s.y)
        if np.any(a == 0) or a.size < 4:
            continue
        dz = np.diff(np.log10(a))
        x.extend(dz[:-1].tolist())
        y.extend(dz[1:].tolist())
    lag1 = float(np.corrcoef(x, y)[0, 1])
    x2 = []
    y2 = []
    for s in zz_events:
        a = np.abs(s.y)
        if np.any(a == 0) or a.size < 5:
            continue
        dz = np.diff(np.log10(a))
        x2.extend(dz[:-2].tolist())
        y2.extend(dz[2:].tolist())
    lag2 = float(np.corrcoef(x2, y2)[0, 1])
    excluded_for_zeros = [
        c.label(pairs[gcol.index(s.entity)]) for s in zz_events if np.any(s.y == 0)
    ]

    # Seasonality of values: deviation of log |zz| from the median of its 3 + 3 neighbouring
    # value events, against the UTC hour and weekday of the file that first shows the value.
    dev_l, t_l = [], []
    for s in zz_events:
        a = np.abs(s.y)
        if np.any(a == 0) or a.size < 8:
            continue
        dev_l.append(c.moving_median_deviation(np.log10(a)))
        t_l.append(s.t_ms)
    dev_s = np.concatenate(dev_l)
    t_s = np.concatenate(t_l)
    okd = np.isfinite(dev_s)
    hr, wd = c.hour_weekday(t_s[okd])
    season = {
        "events": int(okd.sum()),
        "by_utc_4h_block": c.kruskal_groups(dev_s[okd], hr // 4, min_n=200),
        "by_weekday_mon0": c.kruskal_groups(dev_s[okd], wd, min_n=200),
    }

    # Relations with cz and rzz error, between couplers (medians) and within couplers.
    rel_out: dict[str, Any] = {}
    for gate in c.GATES:
        v = np.array(dd.v(f"g2.{gate}.gate_error"))[:, fwd]
        v = np.where(v < 1.0, v, np.nan)
        gmed = np.nanmedian(np.log10(v), axis=0)
        ok_c = np.isfinite(gmed) & (absmed > 0)
        # within: at each gate event, deviation of log err and of log|zz| (current value in
        # the same file) from the coupler's own means.
        ser = c.gate_series(dd, gate, fwd)
        de, dz_ = [], []
        for i, col in enumerate(fwd):
            if col not in ser:
                continue
            s = ser[col]
            zcur = np.abs(zz[s.file_idx, i])
            if np.any(zcur == 0):
                continue
            le = np.log10(s.y)
            lz = np.log10(zcur)
            de.extend((le - le.mean()).tolist())
            dz_.extend((lz - lz.mean()).tolist())
        rel_out[gate] = {
            "between_coupler_spearman_median_log_err_vs_median_abs_zz": c.spearman(
                gmed[ok_c], np.log10(absmed[ok_c])
            ),
            "within_coupler_spearman_demeaned": c.spearman(de, dz_),
        }

    # zz for the couplers with unusual gate lengths, as a percentile of all couplers.
    rank = np.argsort(np.argsort(absmed)) / (n_c - 1)
    special = ["102-103", "146-147", "68-69", "80-81", "106-107", "71-72", "72-73"]
    special += ["27-28", "32-33", "95-99", "99-115"]
    special_rows = {
        s: {
            "median_khz": c.rnd(float(med[lab.index(s)])),
            "abs_rank": c.rnd(float(rank[lab.index(s)])),
        }
        for s in special
    }

    # Gate placeholders on the couplers while their zz is exactly zero.
    vcz = np.array(dd.v("g2.cz.gate_error"))[:, fwd]
    vrz = np.array(dd.v("g2.rzz.gate_error"))[:, fwd]
    for row in zero_rows:
        i = lab.index(row["coupler"])
        zf = zz[:, i] == 0
        row["cz_placeholder_share_while_zero"] = c.rnd(float(np.mean(vcz[zf, i] >= 1.0)))
        row["rzz_placeholder_share_while_zero"] = c.rnd(float(np.mean(vrz[zf, i] >= 1.0)))
        row["cz_placeholder_share_otherwise"] = (
            c.rnd(float(np.mean(vcz[~zf, i] >= 1.0))) if (~zf).any() else None
        )

    # Do the couplers with a non-68 ns gate length sit low in |zz|? Mann-Whitney on the
    # time-median |zz| of the five couplers with 88 ns or 116 ns lengths against the rest
    # (71-72 and 72-73, whose length changed while faulty, and 32-33 are left out).
    odd = ["102-103", "146-147", "68-69", "80-81", "106-107"]
    drop = {"71-72", "72-73", "32-33"}
    grp = np.array([lab[i] in odd for i in range(n_c)])
    rest = np.array([(lab[i] not in odd) and (lab[i] not in drop) for i in range(n_c)])
    mw = stats.mannwhitneyu(absmed[grp], absmed[rest], alternative="less")
    length_test = {
        "couplers": odd,
        "abs_median_khz": [c.rnd(float(absmed[lab.index(x)])) for x in odd],
        "rest_n": int(rest.sum()),
        "rest_abs_median_khz_median": c.rnd(float(np.median(absmed[rest]))),
        "mannwhitney_less_p": c.rnd(float(mw.pvalue), 3),
        "auc_share_of_rest_below": c.rnd(float(mw.statistic / (grp.sum() * rest.sum())), 3),
    }

    payload: dict[str, Any] = {
        "n_files": n_files,
        "couplers": n_c,
        "unit_note": "IBM reports GHz; values here are multiplied by 1e6 (kHz)",
        "record_khz_q": c.q(zz),
        "per_coupler_median_khz_q": c.q(med),
        "per_coupler_abs_median_khz_q": c.q(absmed),
        "per_coupler_iqr_over_median_q": c.q(
            (np.quantile(zz, 0.75, axis=0) - np.quantile(zz, 0.25, axis=0))
            / np.where(med != 0, np.abs(med), np.nan)
        ),
        "negative_records": int((zz < 0).sum()),
        "zero_records": int((zz == 0).sum()),
        "couplers_ever_negative": int(np.sum(neg > 0)),
        "couplers_median_negative": int(np.sum(med < 0)),
        "negative_couplers": neg_rows[:20],
        "zero_couplers": zero_rows,
        "couplers_with_at_most_one_value_change": frozen,
        "distinct_values": int(distinct.size),
        "smallest_nonzero_abs_khz": c.rnd(float(nz[0])),
        "smallest_gap_between_distinct_abs_values_khz": c.rnd(float(np.min(np.diff(nz)))),
        "significant_digits_of_distinct_values_q": c.q(sig_a),
        "burst_rate_and_file_kind": burst_rate,
        "bursts": {
            "files_with_any_change": int(burst.size),
            "couplers_changing_per_burst_q": c.q(per_file[per_file > 0].astype(np.float64)),
            "bursts_with_ge_170_couplers": int(np.sum(per_file >= 170)),
            "gap_between_bursts_h_q": c.q(bgap),
            "gap_between_bursts_h_q_before_split": c.q(bgap[bt[1:] < split]),
            "gap_between_bursts_h_q_after_split": c.q(bgap[bt[1:] >= split]),
            "bursts_before_split": int(np.sum(bt < split)),
            "bursts_from_split": int(np.sum(bt >= split)),
            "file_gap_before_burst_h_q": c.q(gap_file[burst - 1]),
            "file_gap_before_nonburst_h_q": c.q(
                gap_file[np.setdiff1d(np.arange(1, n_files), burst) - 1]
            ),
            "burst_utc_hour_counts": np.bincount(hour, minlength=24).tolist(),
            "value_changes_per_coupler_q": c.q(changed.sum(axis=0).astype(np.float64)),
        },
        "alignment_with_gate_rounds": align,
        "burst_change_log10_abs_ratio_q": c.q(rel_a),
        "burst_change_share_above_factor_1p5": c.rnd(float(np.mean(np.abs(rel_a) > np.log10(1.5)))),
        "lag1_autocorr_dlog_abs_zz": c.rnd(lag1),
        "lag2_autocorr_dlog_abs_zz": c.rnd(lag2),
        "lag_pairs": len(x),
        "couplers_excluded_from_log_statistics_for_zeros": excluded_for_zeros,
        "value_seasonality_log_abs": season,
        "relations": rel_out,
        "special_couplers": special_rows,
        "non_68ns_length_vs_abs_zz": length_test,
    }
    path = c.write("zz.json", SCRIPT, payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
