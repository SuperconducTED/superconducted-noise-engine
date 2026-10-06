"""cz against rzz on the same coupler: levels, timing of their rounds, and their changes.

Writes ``results/gates_2q/cz_vs_rzz.json``. Canonical direction, placeholders masked,
measured-rule events. Loads only ``g2.cz.*`` and ``g2.rzz.*``.

Matching: an rzz event is matched to a cz event of the same coupler when its stamp is the
nearest rzz stamp to the cz stamp and lies within ``MATCH_H`` hours. Changes are formed from
consecutive cz events whose two matched rzz events are distinct.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c
import ddload

SCRIPT = "analysis/gates_2q/cz_vs_rzz.py"
MATCH_H = 6.0


def nearest(t_ref: np.ndarray, t_other: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index of the nearest ``t_other`` stamp to each ``t_ref`` stamp, and the signed offset."""
    j = np.searchsorted(t_other, t_ref)
    j0 = np.clip(j - 1, 0, t_other.size - 1)
    j1 = np.clip(j, 0, t_other.size - 1)
    pick = np.where(np.abs(t_other[j0] - t_ref) <= np.abs(t_other[j1] - t_ref), j0, j1)
    return pick, (t_other[pick] - t_ref) / ddload.MS_PER_HOUR


def main() -> int:
    dd = ddload.DD()
    pairs, fwd, _ = c.canonical(dd)
    split = c.split_ms(dd)
    cz = c.gate_series(dd, "cz", fwd)
    rzz = c.gate_series(dd, "rzz", fwd)
    common = [col for col in fwd if col in cz and col in rzz]
    lab = {col: c.label(pairs[i]) for i, col in enumerate(fwd)}

    # Levels: per-coupler medians of event values.
    med_cz = np.array([np.median(np.log10(cz[col].y)) for col in common])
    med_rzz = np.array([np.median(np.log10(rzz[col].y)) for col in common])
    ratio = 10.0 ** (med_rzz - med_cz)
    order = np.argsort(ratio)
    extremes = [
        {
            "coupler": lab[common[k]],
            "rzz_over_cz": c.rnd(float(ratio[k])),
            "cz_median": c.rnd(float(10 ** med_cz[k])),
            "rzz_median": c.rnd(float(10 ** med_rzz[k])),
        }
        for k in list(order[:5]) + list(order[-8:])
    ]

    # Same-file comparison of the two current values.
    vcz = np.array(dd.v("g2.cz.gate_error"))[:, fwd]
    vrz = np.array(dd.v("g2.rzz.gate_error"))[:, fwd]
    both = (vcz < 1.0) & (vrz < 1.0)
    lr = np.log10(vrz[both] / vcz[both])

    # Timing and matched changes.
    offsets: list[float] = []
    offsets_p1: list[float] = []
    offsets_p2: list[float] = []
    d_cz: list[float] = []
    d_rz: list[float] = []
    lev_cz: list[float] = []
    lev_rz: list[float] = []
    round_key: list[float] = []
    per_coupler_rho: list[float] = []
    unmatched = 0
    for col in common:
        a, b = cz[col], rzz[col]
        pick, off = nearest(a.t_ms, b.t_ms)
        for t, o in zip(a.t_ms, off, strict=True):
            offsets.append(float(o))
            (offsets_p1 if t < split else offsets_p2).append(float(o))
        ok = np.abs(off) <= MATCH_H
        unmatched += int(np.sum(~ok))
        za, zb = np.log10(a.y), np.log10(b.y)
        lev_cz.extend((za[ok] - np.mean(za)).tolist())
        lev_rz.extend((zb[pick[ok]] - np.mean(zb)).tolist())
        dca: list[float] = []
        dcb: list[float] = []
        for k in range(1, a.y.size):
            if ok[k] and ok[k - 1] and pick[k] != pick[k - 1]:
                dca.append(float(za[k] - za[k - 1]))
                dcb.append(float(zb[pick[k]] - zb[pick[k - 1]]))
                round_key.append(float(a.t_ms[k]))
        d_cz.extend(dca)
        d_rz.extend(dcb)
        if len(dca) >= 20:
            r = c.spearman(dca, dcb)["rho"]
            if r is not None:
                per_coupler_rho.append(r)
    off_arr = np.array(offsets)
    dcz, drz = np.array(d_cz), np.array(d_rz)

    # Remove the round's common mode (median change of every coupler in that cz round).
    keys = np.array(round_key)
    rd = c.rounds(keys)
    starts = np.array([r[0] for r in rd])
    rid = np.searchsorted(starts, keys, side="right") - 1
    dcz_dm = dcz.copy()
    drz_dm = drz.copy()
    for r in np.unique(rid):
        m = rid == r
        dcz_dm[m] -= np.median(dcz[m])
        drz_dm[m] -= np.median(drz[m])

    # Null for the change correlation: pair each coupler's cz change with another coupler's
    # rzz change from the same cz round (cyclic shift within the round).
    rng = np.random.default_rng(20261006)
    null_rho: list[float] = []
    for _ in range(200):
        perm = np.arange(drz.size)
        for r in np.unique(rid):
            idx = np.flatnonzero(rid == r)
            if idx.size > 1:
                perm[idx] = idx[np.roll(np.arange(idx.size), int(rng.integers(1, idx.size)))]
        null_rho.append(float(c.spearman(dcz, drz[perm])["rho"] or 0.0))

    # Shared deviation from each gate's local level, against the time between the two events.
    # Each event's deviation is its log value minus the median of its 3 + 3 neighbours, so
    # the slowly moving level is removed; the nearest rzz event is used without a window.
    dev_rows: list[tuple[float, float, float, float]] = []
    for col in common:
        a, b = cz[col], rzz[col]
        if a.y.size < 8 or b.y.size < 8:
            continue
        da = c.moving_median_deviation(np.log10(a.y))
        db = c.moving_median_deviation(np.log10(b.y))
        pick, off = nearest(a.t_ms, b.t_ms)
        for k in range(a.y.size):
            dev_rows.append(
                (float(da[k]), float(db[pick[k]]), abs(float(off[k])), float(a.t_ms[k]))
            )
    dev = np.array(dev_rows)
    lag_edges = (0.0, 1.0, 2.0, 4.0, 6.0, 12.0, 24.0, 48.0, 168.0)
    by_offset = []
    for lo, hi in itertools.pairwise(lag_edges):
        m = (dev[:, 2] > lo) & (dev[:, 2] <= hi)
        r = c.spearman(dev[m, 0], dev[m, 1])
        before = m & (dev[:, 3] < split)
        after = m & (dev[:, 3] >= split)
        by_offset.append(
            {
                "abs_offset_h_lo": lo,
                "abs_offset_h_hi": hi,
                **r,
                "before_split": c.spearman(dev[before, 0], dev[before, 1]),
                "after_split": c.spearman(dev[after, 0], dev[after, 1]),
            }
        )

    # rzz length groups: the three 116 ns rzz couplers against the 68 ns ones.
    rlen = np.array(dd.v("g2.rzz.gate_length"))[-1, :]
    ratio_by_len: dict[str, Any] = {}
    for length in (68.0, 88.0, 116.0):
        m = np.array([rlen[col] == length for col in common])
        if m.any():
            ratio_by_len[str(int(length))] = {
                "couplers": [lab[common[k]] for k in np.flatnonzero(m)] if m.sum() < 6 else None,
                "n": int(m.sum()),
                "ratio_q": c.q(ratio[m], (0.0, 0.5, 1.0)),
            }

    # Faults on one gate only.
    vcz_all = np.array(dd.v("g2.cz.gate_error"))[:, fwd]
    vrz_all = np.array(dd.v("g2.rzz.gate_error"))[:, fwd]
    ph_cz, ph_rz = vcz_all >= 1.0, vrz_all >= 1.0
    payload: dict[str, Any] = {
        "n_files": dd.n_files,
        "couplers_with_both_series": len(common),
        "match_window_h": MATCH_H,
        "levels": {
            "per_coupler_median_ratio_rzz_over_cz_q": c.q(ratio),
            "share_couplers_rzz_median_below_cz": c.rnd(float(np.mean(ratio < 1.0))),
            "between_coupler_spearman_of_log_medians": c.spearman(med_cz, med_rzz),
            "extremes": extremes,
            "same_file_records_both_valid": int(both.sum()),
            "same_file_log10_rzz_over_cz_q": c.q(lr),
            "same_file_share_rzz_below_cz": c.rnd(float(np.mean(lr < 0))),
            "same_file_share_exactly_equal": c.rnd(float(np.mean(lr == 0))),
        },
        "timing": {
            "cz_events": int(off_arr.size),
            "offset_nearest_rzz_minus_cz_h_q": c.q(off_arr),
            "offset_q_before_split": c.q(offsets_p1),
            "offset_q_after_split": c.q(offsets_p2),
            "share_rzz_within_0_to_3h_after": c.rnd(float(np.mean((off_arr > 0) & (off_arr <= 3)))),
            "share_within_match_window": c.rnd(float(np.mean(np.abs(off_arr) <= MATCH_H))),
            "share_rzz_before_cz_within_window": c.rnd(
                float(np.mean((off_arr < 0) & (off_arr >= -MATCH_H)))
            ),
            "cz_events_unmatched": unmatched,
        },
        "changes": {
            "matched_change_pairs": int(dcz.size),
            "spearman_dlog_cz_vs_dlog_rzz": c.spearman(dcz, drz),
            "spearman_after_removing_round_median": c.spearman(dcz_dm, drz_dm),
            "null_other_coupler_same_round_rho_q": c.q(null_rho, (0.0, 0.025, 0.5, 0.975, 1.0)),
            "per_coupler_spearman_q": c.q(per_coupler_rho),
            "per_coupler_n": len(per_coupler_rho),
            "within_coupler_level_spearman_demeaned": c.spearman(lev_cz, lev_rz),
            "local_deviation_spearman_by_abs_offset": by_offset,
        },
        "ratio_by_rzz_length_ns_last_file": ratio_by_len,
        "faults": {
            "cz_placeholder_records": int(ph_cz.sum()),
            "rzz_placeholder_records": int(ph_rz.sum()),
            "both_placeholder_records": int(np.sum(ph_cz & ph_rz)),
            "cz_only_placeholder_records": int(np.sum(ph_cz & ~ph_rz)),
            "rzz_only_placeholder_records": int(np.sum(ph_rz & ~ph_cz)),
        },
    }
    path = c.write("cz_vs_rzz.json", SCRIPT, payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
