"""Layer fidelity ``lf_N``: values, cadence, chains, late stamps, variogram, and the chain link.

``gen.lf`` holds 97 names ``lf_4`` to ``lf_100``; each comes with the qubit chain it was
reported on (``gen.lf_chain`` into ``meta.json`` ``lf_chains``). All 97 names share one stamp
per file, so an **lf event** is a file whose ``lf`` stamp differs from the previous file's.

Definitions used here (McKay et al. 2023, arXiv:2311.05933, eqs. 1 to 3; IBM's QPU
information page, fetched 2026-10-06):

- ``EPLG_proc(N) = 1 - lf_N^(1/(N-1))``: process error per layered gate (McKay's form, a
  chain of N qubits has N - 1 two-qubit gates);
- ``EPLG_avg(N) = 4/5 * EPLG_proc(N)``: the average-gate-error form IBM's page uses for
  N = 100, comparable with ``gate_error``.

The assigned cross-family link compares ``lf_N`` with the product of its chain's isolated
gate fidelities: ``pred_N = prod_e (1 - 5/4 * cz_e)`` over the chain's N - 1 couplers
(average gate error to process fidelity, d = 4), optionally times ``(1 - 3/2 * sx_q)`` for the
two endpoint qubits (each idle in one of the two layers of a linear chain). ``cz_e`` is the
coupler's latest re-measurement stamped at or before the lf stamp (placeholders masked).

Writes ``results/device/layer_fidelity.json``.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

N_SHOW = (4, 5, 10, 20, 30, 50, 70, 80, 90, 100)
LONG_GAP_H = 48.0


def contained(a: list[int], b: list[int]) -> bool:
    """``a`` is a contiguous sub-path of ``b`` in either orientation."""
    sb = "," + ",".join(map(str, b)) + ","
    fa = "," + ",".join(map(str, a)) + ","
    ra = "," + ",".join(map(str, a[::-1])) + ","
    return fa in sb or ra in sb


class Current:
    """Latest event value of every coupler or qubit at or before a time (placeholders masked)."""

    def __init__(self, dd: ddload.DD, field: str, columns: list[int]) -> None:
        ser = ddload.series(dd, field, rule=ddload.MEASURED, mask=ddload.placeholder_error)
        by = {s.entity: s for s in ser}
        self.t = {c: by[c].t_ms if c in by else np.array([]) for c in columns}
        self.y = {c: by[c].y if c in by else np.array([]) for c in columns}

    def at(self, col: int, t_ms: float, after: bool = False) -> tuple[float, float]:
        """(value, age in hours) at ``t_ms``; with ``after``, the first event after instead."""
        t = self.t[col]
        if after:
            k = int(np.searchsorted(t, t_ms, side="right"))
            if k >= t.size:
                return np.nan, np.nan
            return float(self.y[col][k]), float((t[k] - t_ms) / ddload.MS_PER_HOUR)
        k = int(np.searchsorted(t, t_ms, side="right")) - 1
        if k < 0:
            return np.nan, np.nan
        return float(self.y[col][k]), float((t_ms - t[k]) / ddload.MS_PER_HOUR)


def spearman(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return {"n": int(ok.sum()), "rho": None, "p": None}
    r = stats.spearmanr(x[ok], y[ok])
    return {"n": int(ok.sum()), "rho": dc.r6(r.statistic), "p": dc.r6(r.pvalue)}


def mad_sd(x: np.ndarray) -> float | None:
    x = x[np.isfinite(x)]
    if x.size < 5:
        return None
    return dc.r6(1.4826 * np.median(np.abs(x - np.median(x))))


def paired_wilcoxon(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5:
        return {"n": int(ok.sum()), "p": None}
    r = stats.wilcoxon(np.abs(a[ok]), np.abs(b[ok]))
    return {
        "n": int(ok.sum()),
        "median_abs_lf": dc.r6(np.median(np.abs(a[ok]))),
        "median_abs_pred": dc.r6(np.median(np.abs(b[ok]))),
        "pairs_lf_smaller": int(np.sum(np.abs(a[ok]) < np.abs(b[ok]))),
        "p": dc.r6(r.pvalue),
    }


def nugget_ratio(vg: dict[str, Any]) -> dict[str, Any]:
    """Shortest non-empty lag bin over the 744 to 1488 h bin (classical and robust)."""
    bins = [b for b in vg["bins"] if b["pairs"]]
    first = bins[0]
    ref = next(b for b in vg["bins"] if b["lag_h_lo"] == 744.0)
    return {
        "short_bin_h": [first["lag_h_lo"], first["lag_h_hi"]],
        "short_pairs": first["pairs"],
        "ref_bin_h": [ref["lag_h_lo"], ref["lag_h_hi"]],
        "classical": dc.r6(first["semivariance"] / ref["semivariance"]),
        "robust": dc.r6(first["semivariance_robust"] / ref["semivariance_robust"]),
    }


def lag1(x: np.ndarray) -> float | None:
    d = np.diff(x[np.isfinite(x)])
    if d.size < 5:
        return None
    return dc.r6(np.corrcoef(d[:-1], d[1:])[0, 1])


def main() -> int:
    dd = ddload.DD()
    names = list(dd.meta["lf_names"])
    nq = np.array([int(n.split("_")[1]) for n in names])
    chains = dd.meta["lf_chains"]
    v = np.array(dd.v("gen.lf"))
    d = np.array(dd.d("gen.lf"))
    cid = np.array(np.load(dd.path / "gen.lf_chain__v.npy"))
    fms = dd.file_ms
    has_conf = dd.file("has_configuration").astype(bool)
    stamp = d[:, 0]
    one_stamp_per_file = bool(np.all(d == stamp[:, None]))
    ev = [0] + [i for i in range(1, dd.n_files) if stamp[i] != stamp[i - 1]]
    ev_arr = np.array(ev)
    ev_t = stamp[ev_arr]
    n_ev = len(ev)
    first_file_ms = float(fms[0])

    # Cadence ----------------------------------------------------------------------------
    gaps_h = np.diff(ev_t) / ddload.MS_PER_HOUR
    long_gaps = [
        {"from": dc.iso(ev_t[k]), "to": dc.iso(ev_t[k + 1]), "hours": dc.r6(gaps_h[k])}
        for k in np.flatnonzero(gaps_h > LONG_GAP_H)
    ]
    inside = ev_t >= first_file_ms
    cadence = {
        "events": n_ev,
        "events_stamped_before_first_file": int(np.sum(~inside)),
        "first_event": dc.iso(ev_t[0]),
        "first_event_inside_archive": dc.iso(ev_t[inside][0]),
        "last_event": dc.iso(ev_t[-1]),
        "gap_h_q_all": dc.quantiles(gaps_h),
        "gap_h_q_inside_archive": dc.quantiles(np.diff(ev_t[inside]) / ddload.MS_PER_HOUR),
        "gaps_over_48h": long_gaps,
        "one_stamp_for_all_names_in_every_file": one_stamp_per_file,
        "value_changes_without_stamp_change": int(
            sum(
                1
                for i in range(1, dd.n_files)
                if stamp[i] == stamp[i - 1] and np.any(v[i] != v[i - 1])
            )
        ),
        "chain_changes_without_stamp_change": int(
            sum(
                1
                for i in range(1, dd.n_files)
                if stamp[i] == stamp[i - 1] and np.any(cid[i] != cid[i - 1])
            )
        ),
    }

    # Late stamps: lf stamp later than the file's last_update_date -------------------------
    late = stamp > fms
    ph_stamp = np.array(dd.d("g1.sx.gate_error"))[:, 72]
    ph_ok = bool(np.all(np.array(dd.v("g1.sx.gate_error"))[:, 72] >= 1.0))
    months = Counter(dd.stems[i][:6] for i in np.flatnonzero(late))
    per_event = Counter(stamp[late])
    ledger_new = {}
    for row in dd.meta["ledger"]:
        if row["decision"] == "new":
            ledger_new.setdefault(row["last_update_date"], row["poll_time_utc"])
    poll_checked = 0
    poll_after_lf = 0
    poll_minus_lf_live: list[float] = []
    example_late: dict[str, str] = {}
    for i in np.flatnonzero(late):
        key = dd.stems[i].removesuffix(".json")
        if key in ledger_new:
            poll_checked += 1
            pt = datetime.fromisoformat(ledger_new[key].replace("Z", "+00:00")).timestamp() * 1000
            poll_after_lf += int(pt >= stamp[i])
            if has_conf[i]:
                poll_minus_lf_live.append(float((pt - stamp[i]) / ddload.MS_PER_HOUR))
                if pt < stamp[i] and not example_late:
                    example_late = {
                        "file": dd.stems[i],
                        "last_update": dc.iso(fms[i]),
                        "ledger_new_poll": ledger_new[key],
                        "lf_stamp": dc.iso(stamp[i]),
                    }
    first_file_of_event_late = int(np.sum(late[ev_arr]))
    late_out = {
        "files": int(late.sum()),
        "files_live": int(np.sum(late & has_conf)),
        "files_historical": int(np.sum(late & ~has_conf)),
        "by_month": dict(sorted(months.items())),
        "lag_h_q": dc.quantiles((stamp[late] - fms[late]) / ddload.MS_PER_HOUR),
        "events_with_a_late_file": len(per_event),
        "late_files_per_such_event": dict(sorted(Counter(per_event.values()).items())),
        "events_whose_first_file_is_late": first_file_of_event_late,
        "q72_sx_placeholder_present_in_every_file": ph_ok,
        "late_files_where_lf_stamp_after_placeholder_stamp": int(np.sum(late & (stamp > ph_stamp))),
        "placeholder_minus_last_update_h_q_live": dc.quantiles(
            (ph_stamp[has_conf] - fms[has_conf]) / ddload.MS_PER_HOUR
        ),
        "late_files_with_ledger_new_row": poll_checked,
        "of_those_poll_time_at_or_after_lf_stamp": poll_after_lf,
        "live_late_files_poll_minus_lf_stamp_h_q": dc.quantiles(poll_minus_lf_live),
        "live_late_files_with_poll_before_lf_stamp": int(np.sum(np.array(poll_minus_lf_live) < 0)),
        "live_late_files_checked": len(poll_minus_lf_live),
        "first_live_late_file_polled_before_lf_stamp": example_late,
        "ledger_first_poll_row": dd.meta["ledger"][0]["poll_time_utc"],
    }

    # Values and EPLG --------------------------------------------------------------------
    lf_ev = v[ev_arr]
    eplg_proc = 1.0 - lf_ev ** (1.0 / (nq - 1.0))
    eplg_avg = 0.8 * eplg_proc
    monotone = int(sum(1 for k in range(n_ev) if np.all(np.diff(lf_ev[k]) <= 0)))
    k100 = names.index("lf_100")
    values = {
        "per_N": {
            str(n): {
                "lf_q": dc.quantiles(lf_ev[:, names.index(f"lf_{n}")]),
                "eplg_avg_q": dc.quantiles(eplg_avg[:, names.index(f"lf_{n}")]),
            }
            for n in N_SHOW
        },
        "median_eplg_avg_by_N": [dc.r6(x) for x in np.median(eplg_avg, axis=0)],
        "median_lf_by_N": [dc.r6(x) for x in np.median(lf_ev, axis=0)],
        "N_order": nq.tolist(),
        "events_with_lf_nonincreasing_in_N": monotone,
        "eplg100_avg_by_event": [dc.r6(x) for x in eplg_avg[:, k100]],
        "event_stamps": [dc.iso(t) for t in ev_t],
        "eplg100_avg_lag1_autocorr_of_log_changes": lag1(np.log10(eplg_avg[:, k100])),
        "eplg100_avg_spearman_with_time": spearman(ev_t, eplg_avg[:, k100]),
        "eplg100_avg_first_half_median": dc.r6(np.median(eplg_avg[: n_ev // 2, k100])),
        "eplg100_avg_second_half_median": dc.r6(np.median(eplg_avg[n_ev // 2 :, k100])),
    }

    # Chains -----------------------------------------------------------------------------
    edges_set = {(int(a), int(b)) for a, b in dd.meta["coupling_map"]}
    valid = nested = contig = total = 0
    maximal: list[int] = []
    for i in ev:
        cs = [chains[int(cid[i, k])] for k in range(len(names))]
        c100 = cs[k100]
        for k, c in enumerate(cs):
            total += 1
            ok_path = len(set(c)) == len(c) and all(
                (c[j], c[j + 1]) in edges_set for j in range(len(c) - 1)
            )
            valid += int(ok_path)
            if k + 1 < len(cs):
                nested += int(set(c) <= set(cs[k + 1]))
            contig += int(contained(c, c100))
        maximal.append(
            sum(1 for c in cs if not any(len(o) > len(c) and contained(c, o) for o in cs))
        )
    c100_ids = cid[ev_arr, k100]
    sets100 = [set(chains[int(x)]) for x in c100_ids]
    jac = [len(a & b) / len(a | b) for a, b in pairwise(sets100)]
    incl = np.zeros(len(dd.meta["qubits"]))
    for s in sets100:
        for q in s:
            incl[q] += 1
    incl /= n_ev
    adj = dc.adjacency(dd)
    deg = np.array([len(a) for a in adj])
    coords = np.array(next(iter(dd.meta["config_values"]["coords"].values()))["value"], dtype=float)
    chain_out = {
        "chains_checked": total,
        "valid_simple_paths": valid,
        "subset_of_next_longer_chain": nested,
        "pairs_checked_for_nesting": total - n_ev,
        "contiguous_subpath_of_that_events_lf100_chain": contig,
        "distinct_chains_total": len(chains),
        "maximal_chains_per_event_counts": dict(sorted(Counter(maximal).items())),
        "distinct_lf100_chains": int(np.unique(c100_ids).size),
        "lf100_chain_jaccard_consecutive_q": dc.quantiles(jac),
        "lf100_chain_identical_to_previous_event": int(sum(1 for j in jac if j == 1.0)),
        "lf100_inclusion_share_by_qubit": [dc.r6(x) for x in incl],
        "qubits_never_in_lf100_chain": [int(q) for q in np.flatnonzero(incl == 0)],
        "qubits_in_every_lf100_chain": int(np.sum(incl == 1.0)),
        "inclusion_median_degree2": dc.r6(np.median(incl[deg == 2])),
        "inclusion_median_degree3": dc.r6(np.median(incl[deg == 3])),
        "inclusion_by_degree_mannwhitney_p": dc.r6(
            stats.mannwhitneyu(incl[deg == 2], incl[deg == 3]).pvalue
        ),
        "inclusion_median_degree1": dc.r6(np.median(incl[deg == 1])),
        "inclusion_mean_by_coord_row": {
            str(int(r)): dc.r6(incl[coords[:, 1] == r].mean()) for r in np.unique(coords[:, 1])
        },
        "inclusion_mean_by_coord_x_half": {
            "x_le_8": dc.r6(incl[coords[:, 0] <= 8].mean()),
            "x_gt_8": dc.r6(incl[coords[:, 0] > 8].mean()),
        },
        "never_included_coords": [coords[q].tolist() for q in np.flatnonzero(incl == 0)],
        "never_included_degree": [int(deg[q]) for q in np.flatnonzero(incl == 0)],
    }

    # The link: lf against its chain's isolated gate errors --------------------------------
    cols, und = dc.undirected_columns(dd)
    col_of = {e: c for c, e in zip(cols, und, strict=True)}
    cz = Current(dd, "g2.cz.gate_error", cols)
    rzz = Current(dd, "g2.rzz.gate_error", cols)
    sx = Current(dd, "g1.sx.gate_error", list(range(len(dd.meta["qubits"]))))
    cz_v = np.array(dd.v("g2.cz.gate_error"))
    cz_len = np.array(dd.v("g2.cz.gate_length"))
    sx_v = np.array(dd.v("g1.sx.gate_error"))
    pred_cz = np.full((n_ev, len(names)), np.nan)
    pred_cz_sx = np.full((n_ev, len(names)), np.nan)
    pred_rzz = np.full((n_ev, len(names)), np.nan)
    pred_cz_next = np.full((n_ev, len(names)), np.nan)
    ages: list[float] = []
    edge_ph = qubit_ph = long_gate_edges = missing = 0
    named: dict[str, Counter[str]] = {
        "cz_placeholder": Counter(),
        "cz_length_above_68ns": Counter(),
        "rzz_placeholder": Counter(),
    }
    rzz_v = np.array(dd.v("g2.rzz.gate_error"))
    chain_edge_pct: list[float] = []
    chain_vs_rest_lower = 0
    chain_vs_rest_n = 0
    edge_incl: Counter[int] = Counter()
    for k, i in enumerate(ev):
        t = float(stamp[i])
        for j in range(len(names)):
            c = chains[int(cid[i, j])]
            es = [col_of[(min(a, b), max(a, b))] for a, b in pairwise(c)]
            edge_ph += int(np.sum(cz_v[i, es] >= 1.0))
            for e in es:
                lab = "-".join(map(str, und[cols.index(e)]))
                if cz_v[i, e] >= 1.0:
                    named["cz_placeholder"][lab] += 1
                if cz_len[i, e] > 68.0:
                    named["cz_length_above_68ns"][lab] += 1
                if rzz_v[i, e] >= 1.0:
                    named["rzz_placeholder"][lab] += 1
            long_gate_edges += int(np.sum(cz_len[i, es] > 68.0))
            qubit_ph += int(np.sum(sx_v[i, c] >= 1.0))
            vals = [cz.at(e, t) for e in es]
            errs = np.array([x[0] for x in vals])
            if j == k100:
                ages.extend(x[1] for x in vals)
                for e in es:
                    edge_incl[e] += 1
            if np.any(~np.isfinite(errs)):
                missing += 1
                continue
            lp = float(np.sum(np.log1p(-1.25 * errs)))
            pred_cz[k, j] = lp
            ends = [sx.at(c[0], t)[0], sx.at(c[-1], t)[0]]
            pred_cz_sx[k, j] = lp + float(np.sum(np.log1p(-1.5 * np.array(ends))))
            rz = np.array([rzz.at(e, t)[0] for e in es])
            if np.all(np.isfinite(rz)):
                pred_rzz[k, j] = float(np.sum(np.log1p(-1.25 * rz)))
            nx = np.array([cz.at(e, t, after=True)[0] for e in es])
            if np.all(np.isfinite(nx)):
                pred_cz_next[k, j] = float(np.sum(np.log1p(-1.25 * nx)))
        # Chain edges against every other real coupler at the lf stamp (lf_100 chain).
        c = chains[int(cid[i, k100])]
        es100 = {col_of[(min(a, b), max(a, b))] for a, b in pairwise(c)}
        cur = np.array([cz.at(e, t)[0] for e in cols])
        ok = np.isfinite(cur)
        inchain = np.array([e in es100 for e in cols])
        ranks = stats.rankdata(cur[ok]) / ok.sum()
        chain_edge_pct.extend(ranks[inchain[ok]].tolist())
        a_in, a_out = cur[ok & inchain], cur[ok & ~inchain]
        if a_in.size and a_out.size:
            chain_vs_rest_n += 1
            chain_vs_rest_lower += int(np.median(a_in) < np.median(a_out))
    ln_lf = np.log(v[ev_arr])
    ratio = ln_lf / pred_cz
    resid_per_gate = (ln_lf - pred_cz) / (nq - 1.0)
    groups = {"4-10": (4, 10), "11-30": (11, 30), "31-60": (31, 60), "61-90": (61, 90)}
    groups["91-100"] = (91, 100)
    same_chain = np.array([False] + [j == 1.0 for j in jac])
    dl = np.diff(ln_lf[:, k100])
    dp = np.diff(pred_cz[:, k100])
    sc = same_chain[1:]
    chain_cz_med = []
    for i in ev:
        c = chains[int(cid[i, k100])]
        es = [col_of[(min(a, b), max(a, b))] for a, b in pairwise(c)]
        chain_cz_med.append(np.median([cz.at(e, float(stamp[i]))[0] for e in es]))
    chain_cz_med_arr = np.array(chain_cz_med)
    pred_eplg_avg100 = 0.8 * (1.0 - np.exp(pred_cz[:, k100] / 99.0))
    incl_cols = cols
    edge_share = np.array([edge_incl[e] / n_ev for e in incl_cols])
    edge_med_cz = np.array(
        [
            np.median(cz_v[cz_v[:, e] < 1.0, e]) if np.any(cz_v[:, e] < 1.0) else np.nan
            for e in incl_cols
        ]
    )
    link = {
        "cz_age_h_at_lf_stamp_q_lf100_edges": dc.quantiles(ages),
        "chain_edges_with_cz_placeholder_in_event_file": edge_ph,
        "chain_qubits_with_sx_placeholder_in_event_file": qubit_ph,
        "chain_edges_with_cz_length_above_68ns": long_gate_edges,
        "event_name_pairs_without_a_cz_value": missing,
        "lf100_chain_edge_cz_percentile_among_all_couplers_q": dc.quantiles(chain_edge_pct),
        "events_lf100_chain_median_cz_below_rest": chain_vs_rest_lower,
        "events_compared": chain_vs_rest_n,
        "coupler_lf100_inclusion_vs_time_median_cz": spearman(edge_share, edge_med_cz),
        "couplers_never_in_lf100_chain": int(np.sum(edge_share == 0)),
        "ratio_lnlf_over_lnpred_cz_q_by_N_group": {
            g: dc.quantiles(ratio[:, (nq >= lo) & (nq <= hi)].ravel())
            for g, (lo, hi) in groups.items()
        },
        "median_ratio_by_N": [dc.r6(x) for x in np.nanmedian(ratio, axis=0)],
        "residual_per_gate_q_by_N_group": {
            g: dc.quantiles(resid_per_gate[:, (nq >= lo) & (nq <= hi)].ravel())
            for g, (lo, hi) in groups.items()
        },
        "ratio_lf100_cz_q": dc.quantiles(ratio[:, k100]),
        "ratio_lf100_with_sx_endpoints_q": dc.quantiles(ln_lf[:, k100] / pred_cz_sx[:, k100]),
        "ratio_lf100_rzz_instead_of_cz_q": dc.quantiles(ln_lf[:, k100] / pred_rzz[:, k100]),
        "ratio_lf100_next_cz_round_q": dc.quantiles(ln_lf[:, k100] / pred_cz_next[:, k100]),
        "eplg100_avg_over_pred_eplg100_avg_q": dc.quantiles(eplg_avg[:, k100] / pred_eplg_avg100),
        "eplg100_avg_over_chain_median_cz_q": dc.quantiles(eplg_avg[:, k100] / chain_cz_med_arr),
        "spearman_events_lnlf100_vs_lnpred_cz": spearman(ln_lf[:, k100], pred_cz[:, k100]),
        "spearman_events_lnlf100_vs_lnpred_next_cz": spearman(
            ln_lf[:, k100], pred_cz_next[:, k100]
        ),
        "spearman_events_lnlf100_vs_lnpred_rzz": spearman(ln_lf[:, k100], pred_rzz[:, k100]),
        "spearman_events_lnlf50_vs_lnpred_cz": spearman(
            ln_lf[:, names.index("lf_50")], pred_cz[:, names.index("lf_50")]
        ),
        "spearman_events_lnlf10_vs_lnpred_cz": spearman(
            ln_lf[:, names.index("lf_10")], pred_cz[:, names.index("lf_10")]
        ),
        "consecutive_pairs_same_lf100_chain": int(sc.sum()),
        "spearman_changes_same_chain": spearman(dl[sc], dp[sc]),
        "spearman_changes_chain_changed": spearman(dl[~sc], dp[~sc]),
        "sd_change_lnlf100_same_chain": dc.r6(np.nanstd(dl[sc], ddof=1)) if sc.sum() > 2 else None,
        "sd_change_lnlf100_chain_changed": dc.r6(np.nanstd(dl[~sc], ddof=1)),
        "sd_change_lnpred100_same_chain": dc.r6(np.nanstd(dp[sc], ddof=1))
        if sc.sum() > 2
        else None,
        "changes_same_chain_finite": int(np.sum(np.isfinite(dl[sc]))),
        "changes_chain_changed_finite": int(np.sum(np.isfinite(dl[~sc]))),
        "mad_sd_change_lnlf100_same_chain": mad_sd(dl[sc]),
        "mad_sd_change_lnpred100_same_chain": mad_sd(dp[sc]),
        "mad_sd_change_lnlf100_chain_changed": mad_sd(dl[~sc]),
        "mad_sd_change_lnpred100_chain_changed": mad_sd(dp[~sc]),
        "wilcoxon_abs_change_lf_vs_pred_same_chain": paired_wilcoxon(dl[sc], dp[sc]),
        "chain_edge_instances_by_coupler": {k: dict(c) for k, c in named.items()},
        "couplers_never_in_lf100_chain_list": [
            "-".join(map(str, und[k])) for k in np.flatnonzero(edge_share == 0)
        ],
    }

    # Variogram of log10 EPLG_proc --------------------------------------------------------
    def eplg_series(cols_idx: list[int]) -> list[Any]:
        out = []
        for j in cols_idx:
            y = 1.0 - lf_ev[:, j] ** (1.0 / (nq[j] - 1.0))
            out.append(
                ddload.Series(entity=j, t_ms=ev_t.copy(), file_idx=ev_arr.astype(np.int64), y=y)
            )
        return out

    vario = {
        "transform": "log10 of EPLG_proc = 1 - lf_N^(1/(N-1)), per name, all 83 events",
        "lf_100": ddload.variogram(eplg_series([k100])),
        "lf_50": ddload.variogram(eplg_series([names.index("lf_50")])),
        "lf_10": ddload.variogram(eplg_series([names.index("lf_10")])),
        "pooled_all_97_names": ddload.variogram(eplg_series(list(range(len(names))))),
        "pooled_caveat": "names share events and overlapping chains, so pairs are not independent",
    }
    for key in ("lf_100", "lf_50", "lf_10", "pooled_all_97_names"):
        vario[f"{key}_nugget_ratio"] = nugget_ratio(vario[key])
    lag1_by_n = {str(n): lag1(np.log10(eplg_avg[:, names.index(f"lf_{n}")])) for n in N_SHOW}

    payload = {
        **dc.header("layer_fidelity.py"),
        "n_files": dd.n_files,
        "lf_names": len(names),
        "cadence": cadence,
        "late_stamps": late_out,
        "values": values,
        "lag1_autocorr_of_log_eplg_changes_by_N": lag1_by_n,
        "chains": chain_out,
        "link": link,
        "variogram": vario,
    }
    ddload.write_json(dc.RESULTS / "layer_fidelity.json", payload)
    print("wrote", dc.RESULTS / "layer_fidelity.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
