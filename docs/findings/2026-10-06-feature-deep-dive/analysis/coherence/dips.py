"""Low-T1 episodes (dips): frequency, depth, duration, recovery, persistence, two-level shape,
the T2 response, and co-dipping across qubits.

Writes ``results/coherence/dips.json``.

A dip event is a T1 event whose log10 value lies at least ``DIP`` below the qubit's running
level (``cohlib.rolling_level``: centred median of up to 14 neighbouring events, the event
left out). ``DIP = log10 2`` (a factor of two) is the primary threshold and ``MILD =
log10 1.5`` the sensitivity threshold. An episode is a maximal run of consecutive dip
events. First events are excluded (their stamps predate the archive).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cohlib
import ddload

DIP = float(np.log10(2.0))
MILD = float(np.log10(1.5))
RECOVERED = float(np.log10(1.25))
N_SHUF = 500
N_SIM = 2000
BIG_ROUND = 78
SEED = 20261006
REGIME3 = 1782604800000.0  # 2026-06-28T00:00:00Z, the last regime of regime.json
GMM_MIN_W = 0.05
GMM_DBIC = 10.0
GMM_D = 2.0


def gmm2(x: np.ndarray, iters: int = 300) -> tuple[float, float, float, float, float, float]:
    """Two-component Gaussian mixture by EM: (w_low, mu_low, sd_low, mu_high, sd_high, loglik)."""
    mu = np.array([np.quantile(x, 0.05), np.median(x)])
    sd = np.array([np.std(x), np.std(x)]) + 1e-3
    w = np.array([0.1, 0.9])
    for _ in range(iters):
        pdf = w / (sd * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x[:, None] - mu) / sd) ** 2)
        tot = pdf.sum(axis=1, keepdims=True) + 1e-300
        g = pdf / tot
        nk = g.sum(axis=0) + 1e-12
        w = nk / x.size
        mu = (g * x[:, None]).sum(axis=0) / nk
        sd = np.sqrt((g * (x[:, None] - mu) ** 2).sum(axis=0) / nk)
        sd = np.maximum(sd, 0.01)
    pdf = w / (sd * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x[:, None] - mu) / sd) ** 2)
    ll = float(np.sum(np.log(pdf.sum(axis=1) + 1e-300)))
    lo = int(np.argmin(mu))
    hi = 1 - lo
    return float(w[lo]), float(mu[lo]), float(sd[lo]), float(mu[hi]), float(sd[hi]), ll


def consecutive_pairs(flags: np.ndarray) -> int:
    return int(np.sum(flags[:-1] & flags[1:]))


def codipping(
    per: dict[int, dict[str, np.ndarray]],
    t_lo: float,
    edges: set[tuple[int, ...]],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Dips per device-wide round against independent dips at each qubit's own rate (rates
    and rounds both taken from events at or after t_lo), and the share of co-dipping
    pairs that are coupled against within-round shuffles of the dip labels."""
    stamps = np.concatenate([d["t"] for d in per.values()])
    ents = np.concatenate([np.full(d["t"].size, e) for e, d in per.items()])
    flags = np.concatenate([np.isfinite(d["dev"]) & (d["dev"] <= -DIP) for d in per.values()])
    valid = np.concatenate([np.isfinite(d["dev"]) for d in per.values()]) & (stamps >= t_lo)
    _, rid = cohlib.rounds(stamps)
    rates = {}
    for e in per:
        m = valid & (ents == e)
        rates[e] = float(np.mean(flags[m])) if m.any() else 0.0
    obs_counts, members, dips = [], [], []
    for k in np.unique(rid[valid]):
        m = (rid == k) & valid
        if np.unique(ents[m]).size < BIG_ROUND:
            continue
        obs_counts.append(int(flags[m].sum()))
        members.append(ents[m])
        dips.append(ents[m][flags[m]])
    sims = np.zeros((N_SIM, len(members)))
    for j, mem in enumerate(members):
        pr = np.array([rates[int(e)] for e in mem])
        sims[:, j] = (rng.random((N_SIM, pr.size)) < pr).sum(axis=1)
    oc = np.array(obs_counts)
    sim_var = sims.var(axis=1)
    sim_max = sims.max(axis=1)
    sim_ge5 = (sims >= 5).sum(axis=1)
    obs_nb = obs_all = 0
    sh_nb = np.zeros(200)
    for mem, dip_q in zip(members, dips, strict=True):
        if dip_q.size < 2:
            continue
        prs = [(int(a_), int(b_)) for i_, a_ in enumerate(dip_q) for b_ in dip_q[i_ + 1 :]]
        obs_all += len(prs)
        obs_nb += sum(tuple(sorted(pq)) in edges for pq in prs)
        for r_ in range(200):
            pick = rng.choice(mem, size=dip_q.size, replace=False)
            sh_nb[r_] += sum(
                tuple(sorted((int(a_), int(b_)))) in edges
                for i_, a_ in enumerate(pick)
                for b_ in pick[i_ + 1 :]
            )
    return {
        "rounds": int(oc.size),
        "observed_count_quantiles": cohlib.q(oc.astype(float)),
        "observed_variance": cohlib.r(oc.var()),
        "independent_sim_variance_quantiles_5_50_95": [
            cohlib.r(v) for v in np.quantile(sim_var, (0.05, 0.5, 0.95))
        ],
        "observed_max": int(oc.max()),
        "independent_sim_max_quantiles_5_50_95": [
            cohlib.r(v) for v in np.quantile(sim_max, (0.05, 0.5, 0.95))
        ],
        "observed_rounds_with_5plus": int(np.sum(oc >= 5)),
        "independent_sim_rounds_with_5plus_quantiles_5_50_95": [
            cohlib.r(v) for v in np.quantile(sim_ge5, (0.05, 0.5, 0.95))
        ],
        "observed_rounds_with_0": int(np.sum(oc == 0)),
        "independent_sim_rounds_with_0_median": cohlib.r(np.median((sims == 0).sum(axis=1))),
        "codip_pairs": obs_all,
        "codip_pairs_coupled": obs_nb,
        "codip_pairs_coupled_shuffled_mean": cohlib.r(np.mean(sh_nb)),
        "codip_pairs_coupled_shuffled_quantiles_5_50_95": [
            cohlib.r(v) for v in np.quantile(sh_nb, (0.05, 0.5, 0.95))
        ],
        "codip_coupled_shuffles": 200,
    }


def main() -> None:
    dd = ddload.DD()
    cohlib.check_period_split(dd)
    rng = np.random.default_rng(SEED)
    out = cohlib.header("analysis/coherence/dips.py")
    out["n_files"] = dd.n_files
    out["thresholds"] = {
        "dip_decades": DIP,
        "mild_decades": MILD,
        "recovered_within_decades": RECOVERED,
        "shuffles": N_SHUF,
        "codip_simulations": N_SIM,
        "big_round_min_qubits": BIG_ROUND,
        "gmm_min_weight": GMM_MIN_W,
        "gmm_delta_bic": GMM_DBIC,
        "gmm_ashman_d": GMM_D,
        "seed": SEED,
        "regime3_start_utc": "2026-06-28T00:00:00Z",
    }
    s1 = cohlib.events(dd, "q.T1")
    per: dict[int, dict[str, np.ndarray]] = {}
    for s in s1:
        z = np.log10(s.y[1:])
        t = s.t_ms[1:]
        if z.size < 20:
            continue
        dev = z - cohlib.rolling_level(z)
        per[s.entity] = {"z": z, "t": t, "dev": dev}

    # ---- frequency, depth, duration, recovery
    res: dict[str, Any] = {}
    for lab, thr in (("factor_2", DIP), ("factor_1.5", MILD)):
        rate, n_dips, ep_len, ep_depth, ep_dur, ep_rec, censored = [], [], [], [], [], [], 0
        for _e, d in per.items():
            f = np.isfinite(d["dev"]) & (d["dev"] <= -thr)
            n_dips.append(int(f.sum()))
            rate.append(float(f.mean()))
            i = 0
            n = f.size
            while i < n:
                if not f[i]:
                    i += 1
                    continue
                j = i
                while j + 1 < n and f[j + 1]:
                    j += 1
                ep_len.append(j - i + 1)
                ep_depth.append(float(np.min(d["dev"][i : j + 1])))
                if j + 1 < n:
                    ep_dur.append(float((d["t"][j + 1] - d["t"][i]) / ddload.MS_PER_HOUR))
                    ep_rec.append(float(d["dev"][j + 1]))
                else:
                    censored += 1
                i = j + 1
        nd = np.array(n_dips)
        order = np.sort(nd)[::-1]
        top = round(0.1 * nd.size)
        lens = np.array(ep_len)
        rec = np.array(ep_rec)
        res[lab] = {
            "qubits": int(nd.size),
            "dip_events": int(nd.sum()),
            "events": int(sum(np.isfinite(d["dev"]).sum() for d in per.values())),
            "dip_share": cohlib.r(
                nd.sum() / sum(np.isfinite(d["dev"]).sum() for d in per.values())
            ),
            "qubits_with_any": int(np.sum(nd > 0)),
            "per_qubit_rate_quantiles": cohlib.q(np.array(rate)),
            "share_of_dips_in_top_10pct_qubits": cohlib.r(order[:top].sum() / max(nd.sum(), 1)),
            "top_10pct_count": top,
            "episodes": int(lens.size),
            "episode_length_events_counts_1_2_3_4plus": [
                int(np.sum(lens == 1)),
                int(np.sum(lens == 2)),
                int(np.sum(lens == 3)),
                int(np.sum(lens >= 4)),
            ],
            "episode_depth_decades_quantiles": cohlib.q(np.array(ep_depth)),
            "episode_duration_to_recovery_h_quantiles": cohlib.q(np.array(ep_dur)),
            "episodes_censored_at_end": censored,
            "first_post_episode_dev_quantiles": cohlib.q(rec),
            "first_post_episode_recovered_share": cohlib.r(np.mean(np.abs(rec) <= RECOVERED)),
        }
    top_q = sorted(
        ((e, int(np.sum(d["dev"] <= -DIP))) for e, d in per.items()), key=lambda x: -x[1]
    )[:10]
    res["most_dip_prone_qubits_factor_2"] = [{"qubit": e, "dips": n} for e, n in top_q]
    out["dips"] = res

    # ---- persistence: consecutive dip pairs, observed against within-qubit shuffles
    pers: dict[str, Any] = {}
    for lab, t_lo in (("all", -np.inf), ("from_2026-06-28", REGIME3)):
        obs = 0
        shuf = np.zeros(N_SHUF)
        n_dip_tot = 0
        for d in per.values():
            m = d["t"] >= t_lo
            z = d["z"][m]
            if z.size < 20:
                continue
            dev = z - cohlib.rolling_level(z)
            f = np.isfinite(dev) & (dev <= -DIP)
            obs += consecutive_pairs(f)
            n_dip_tot += int(f.sum())
            zz = np.array([rng.permutation(z) for _ in range(N_SHUF)])
            dv = zz - cohlib.rolling_level_batch(zz)
            ff = np.isfinite(dv) & (dv <= -DIP)
            shuf += np.sum(ff[:, :-1] & ff[:, 1:], axis=1)
        pers[lab] = {
            "dip_events": n_dip_tot,
            "observed_consecutive_dip_pairs": obs,
            "shuffled_mean": cohlib.r(np.mean(shuf)),
            "shuffled_quantiles_5_50_95": [
                cohlib.r(v) for v in np.quantile(shuf, (0.05, 0.5, 0.95))
            ],
            "p_shuffled_ge_observed": cohlib.r((np.sum(shuf >= obs) + 1) / (N_SHUF + 1)),
        }
    out["persistence"] = pers

    # ---- two-level shape of the deviations (per-qubit mixture)
    rows = []
    for e, d in per.items():
        x = d["dev"][np.isfinite(d["dev"])]
        if x.size < 40:
            continue
        ll1 = float(np.sum(stats.norm.logpdf(x, np.mean(x), np.std(x))))
        w_lo, mu_lo, sd_lo, mu_hi, sd_hi, ll2 = gmm2(x)
        dbic = (-2 * ll1 + 2 * np.log(x.size)) - (-2 * ll2 + 5 * np.log(x.size))
        dd_ = abs(mu_hi - mu_lo) / np.sqrt((sd_lo**2 + sd_hi**2) / 2)
        # low-state membership and its persistence
        p_lo = w_lo * stats.norm.pdf(x, mu_lo, sd_lo)
        p_hi = (1 - w_lo) * stats.norm.pdf(x, mu_hi, sd_hi)
        lo_flag = p_lo > p_hi
        rows.append(
            (e, x.size, dbic, dd_, w_lo, mu_lo, consecutive_pairs(lo_flag), int(lo_flag.sum()))
        )
    a = np.array([r_[2:] for r_ in rows])
    two = (a[:, 0] > GMM_DBIC) & (a[:, 1] > GMM_D) & (a[:, 2] >= GMM_MIN_W)
    n_ev = np.array([r_[1] for r_ in rows], dtype=float)
    # expected consecutive low-low pairs if low-state membership were independent in time
    exp_pairs = (a[:, 5] / n_ev) ** 2 * (n_ev - 1)
    out["two_level"] = {
        "qubits_fitted": len(rows),
        "delta_bic_gt_10": int(np.sum(a[:, 0] > GMM_DBIC)),
        "two_level_qubits": int(two.sum()),
        "two_level_list": [
            {
                "qubit": rows[i][0],
                "delta_bic": cohlib.r(a[i, 0], 4),
                "ashman_d": cohlib.r(a[i, 1], 4),
                "low_weight": cohlib.r(a[i, 2], 4),
                "low_mean_dev": cohlib.r(a[i, 3], 4),
                "low_low_consecutive": int(a[i, 4]),
                "low_low_expected_if_independent": cohlib.r(exp_pairs[i], 4),
            }
            for i in np.flatnonzero(two)
        ],
        "two_level_low_low_observed_total": int(a[two, 4].sum()),
        "two_level_low_low_expected_total": cohlib.r(exp_pairs[two].sum()),
    }

    # ---- T2 response during T1 dips (paired events)
    pairs, _ = cohlib.paired(dd)
    obs_d, pred_d, obs_n, t2only, t2dips = [], [], [], 0, 0
    for p in pairs:
        if p.t1.size < 20:
            continue
        z1, z2 = np.log10(p.t1), np.log10(p.t2)
        l1, l2 = cohlib.rolling_level(z1), cohlib.rolling_level(z2)
        d1, d2 = z1 - l1, z2 - l2
        ok = np.isfinite(d1) & np.isfinite(d2)
        g_lv = np.maximum(1.0 / 10**l2 - 0.5 / 10**l1, 0.0)
        t2_pred = 1.0 / (0.5 / p.t1 + g_lv)
        pd_ = np.log10(t2_pred) - l2
        dip = ok & (d1 <= -DIP)
        obs_d.append(d2[dip])
        pred_d.append(pd_[dip])
        obs_n.append(d2[ok & (d1 > -MILD)])
        t2d = ok & (d2 <= -DIP)
        t2dips += int(t2d.sum())
        t2only += int(np.sum(t2d & (d1 > -MILD)))
    od, pdd, on = np.concatenate(obs_d), np.concatenate(pred_d), np.concatenate(obs_n)
    out["t2_during_t1_dips"] = {
        "t1_dip_events_paired": int(od.size),
        "t2_dev_median_observed": cohlib.r(np.median(od)),
        "t2_dev_median_predicted_pure_t1": cohlib.r(np.median(pdd)),
        "spearman_observed_vs_predicted": cohlib.r(stats.spearmanr(od, pdd).statistic),
        "share_t2_dev_negative": cohlib.r(np.mean(od < 0)),
        "share_observed_below_predicted": cohlib.r(np.mean(od < pdd)),
        "t2_dev_median_when_t1_not_dipping": cohlib.r(np.median(on)),
        "t2_dip_events": t2dips,
        "t2_dips_with_t1_not_dipping_mild": t2only,
        "note": (
            "predicted: 1/T2 = 1/(2 T1_observed) + Gamma_phi at the running levels (floored at 0)"
        ),
    }

    # ---- co-dipping across qubits in device-wide rounds
    edges = {tuple(sorted(e)) for e in dd.meta["coupling_map"]}
    out["codipping"] = {
        "all": codipping(per, -np.inf, edges, rng),
        "from_2026-06-28": codipping(per, REGIME3, edges, rng),
    }
    cohlib.write("dips.json", out)


if __name__ == "__main__":
    main()
