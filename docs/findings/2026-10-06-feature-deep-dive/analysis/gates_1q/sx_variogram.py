"""The non-persistent component of log10(sx): variograms and the change autocorrelations.

Writes ``results/gates_1q/sx_variogram.json``. Unit: MEASURED events, placeholders masked.

- ``ddload.variogram`` (the shared instrument of ``01-data-layer.md`` section 7) over all
  series, and separately over the events stamped before and from 2026-08-01 (the archive's
  coverage changed in August; pairs that straddle the split are dropped);
- per qubit, the semivariance at daily lags (18 to 30 h) against lags above 744 h;
- pooled lag-1 and lag-2 autocorrelations of log changes with a bootstrap over qubits. Under
  "level plus a component that is uncorrelated between events", rho2 is 0; if the component
  had autocorrelation phi at one event spacing, rho2 / rho1 estimates phi (a model-based
  reading, stated as such in the document);
- per qubit, the robust size of the changes against the qubit's level (the reading rule:
  slope 0 in log-log means constant relative scatter, slope -1 constant absolute scatter).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import g1common as g
from scripts.feature_patterns import Series  # on sys.path via ddload

SCRIPT = "analysis/gates_1q/sx_variogram.py"
SPLIT_MS = g.ms_of("2026-08-01T00:00:00Z")
RNG = np.random.default_rng(20261006)
N_BOOT = 2000


def sub(series: list[Any], before: bool) -> list[Any]:
    out = []
    for s in series:
        sel = s.t_ms < SPLIT_MS if before else s.t_ms >= SPLIT_MS
        if sel.sum() >= 2:
            out.append(
                Series(entity=s.entity, t_ms=s.t_ms[sel], file_idx=s.file_idx[sel], y=s.y[sel])
            )
    return out


def bin_value(vg: dict[str, Any], lo: float, hi: float, key: str = "semivariance") -> Any:
    """Pair-weighted semivariance over the bins inside [lo, hi)."""
    num, den = 0.0, 0
    for b in vg["bins"]:
        if b["lag_h_lo"] >= lo and b["lag_h_hi"] <= hi and b["pairs"]:
            num += b[key] * b["pairs"]
            den += b["pairs"]
    return {"value": g.rnd(num / den, 6) if den else None, "pairs": den}


def summary(vg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("semivariance", "semivariance_robust"):
        short = bin_value(vg, 4.0, 12.0, key)
        daily = bin_value(vg, 18.0, 30.0, key)
        long_ = bin_value(vg, 744.0, 3624.0, key)
        out[key] = {
            "lag_4_to_12h": short,
            "lag_18_to_30h": daily,
            "lag_744_to_3624h": long_,
            "daily_over_long": g.rnd(daily["value"] / long_["value"], 4)
            if daily["value"] and long_["value"]
            else None,
            "short_over_long": g.rnd(short["value"] / long_["value"], 4)
            if short["value"] and long_["value"]
            else None,
        }
    return out


def per_entity(series: list[Any]) -> dict[str, Any]:
    ratios, daily, long_ = [], [], []
    for s in series:
        vg = ddload.variogram([s])
        d = bin_value(vg, 18.0, 30.0)
        lo = bin_value(vg, 744.0, 3624.0)
        if d["pairs"] >= 20 and lo["pairs"] >= 20:
            ratios.append(d["value"] / lo["value"])
            daily.append(d["value"])
            long_.append(lo["value"])
    r = np.array(ratios)
    return {
        "entities": int(r.size),
        "min_pairs_each": 20,
        "daily_over_long_q": g.q(r, nd=4),
        "share_ratio_ge_0.8": g.rnd(float(np.mean(r >= 0.8)), 3),
        "share_ratio_ge_0.5": g.rnd(float(np.mean(r >= 0.5)), 3),
        "daily_semivariance_q": g.q(daily, nd=6),
        "long_semivariance_q": g.q(long_, nd=6),
    }


BOOT_BINS = {
    "6_9h": (6.0, 9.0),
    "9_18h": (9.0, 18.0),
    "18_30h": (18.0, 30.0),
    "744_3624h": (744.0, 3624.0),
}


def boot_bins(series: list[Any]) -> dict[str, Any]:
    """Semivariance in a few lag ranges with a bootstrap over qubits (plain and robust)."""
    names = list(BOOT_BINS)
    acc = np.zeros((len(series), len(names), 3))  # sum half sq, count, sum sqrt|dz|
    for i, s in enumerate(series):
        z = np.log10(s.y)
        t = s.t_ms / g.HOUR_MS
        iu, ju = np.triu_indices(z.size, k=1)
        lag = np.abs(t[ju] - t[iu])
        dz = z[ju] - z[iu]
        for k, nm in enumerate(names):
            lo, hi = BOOT_BINS[nm]
            sel = (lag >= lo) & (lag < hi)
            acc[i, k] = (0.5 * np.sum(dz[sel] ** 2), sel.sum(), np.sum(np.sqrt(np.abs(dz[sel]))))

    def est(a: np.ndarray) -> np.ndarray:
        tot = a.sum(axis=0)
        c = np.maximum(tot[:, 1], 1.0)
        plain = tot[:, 0] / c
        robust = (tot[:, 2] / c) ** 4 / (2.0 * (0.457 + 0.494 / c))
        return np.concatenate([plain, robust])

    obs = est(acc)
    m = len(series)
    boots = np.array([est(acc[RNG.integers(0, m, m)]) for _ in range(N_BOOT)])
    nb = len(names)
    out: dict[str, Any] = {"bootstrap": f"{N_BOOT} resamples of qubits"}
    for k, nm in enumerate(names):
        out[nm] = {
            "pairs": int(acc[:, k, 1].sum()),
            "semivariance": g.rnd(float(obs[k]), 6),
            "ci95": [g.rnd(float(v), 6) for v in np.quantile(boots[:, k], [0.025, 0.975])],
            "semivariance_robust": g.rnd(float(obs[nb + k]), 6),
            "robust_ci95": [
                g.rnd(float(v), 6) for v in np.quantile(boots[:, nb + k], [0.025, 0.975])
            ],
        }
    il, i6, i24 = names.index("744_3624h"), names.index("6_9h"), names.index("18_30h")
    for lab, a, b in (
        ("6_9h_over_long", i6, il),
        ("18_30h_over_long", i24, il),
        ("6_9h_over_18_30h", i6, i24),
    ):
        rp = boots[:, a] / boots[:, b]
        rr = boots[:, nb + a] / boots[:, nb + b]
        out[lab] = {
            "plain": g.rnd(float(obs[a] / obs[b]), 4),
            "plain_ci95": [g.rnd(float(v), 4) for v in np.quantile(rp, [0.025, 0.975])],
            "robust": g.rnd(float(obs[nb + a] / obs[nb + b]), 4),
            "robust_ci95": [g.rnd(float(v), 4) for v in np.quantile(rr, [0.025, 0.975])],
        }
    return out


def autocorr(series: list[Any]) -> dict[str, Any]:
    stats1 = []
    stats2 = []
    var_parts = []
    for s in series:
        dz = np.diff(np.log10(s.y))
        x1, y1 = dz[:-1], dz[1:]
        x2, y2 = dz[:-2], dz[2:]
        stats1.append(
            [x1.size, x1.sum(), y1.sum(), (x1 * x1).sum(), (y1 * y1).sum(), (x1 * y1).sum()]
        )
        stats2.append(
            [x2.size, x2.sum(), y2.sum(), (x2 * x2).sum(), (y2 * y2).sum(), (x2 * y2).sum()]
        )
        var_parts.append([dz.size, dz.sum(), (dz * dz).sum()])
    a1 = np.array(stats1)
    a2 = np.array(stats2)
    vp = np.array(var_parts)

    def corr(a: np.ndarray) -> float:
        n, sx, sy, sxx, syy, sxy = a.sum(axis=0)
        cov = sxy / n - (sx / n) * (sy / n)
        vx = sxx / n - (sx / n) ** 2
        vy = syy / n - (sy / n) ** 2
        return float(cov / np.sqrt(vx * vy))

    def cov(a: np.ndarray) -> float:
        n, sx, sy, _, _, sxy = a.sum(axis=0)
        return float(sxy / n - (sx / n) * (sy / n))

    def var(v: np.ndarray) -> float:
        n, s1, s2 = v.sum(axis=0)
        return float(s2 / n - (s1 / n) ** 2)

    r1, r2 = corr(a1), corr(a2)
    boot = np.empty((N_BOOT, 3))
    m = a1.shape[0]
    for b in range(N_BOOT):
        idx = RNG.integers(0, m, m)
        b1, b2 = corr(a1[idx]), corr(a2[idx])
        boot[b] = (b1, b2, b2 / b1)
    lo, hi = np.quantile(boot, [0.025, 0.975], axis=0)
    c1 = cov(a1)
    vdz = var(vp)
    sigma_e2 = -c1
    sigma_w2 = vdz - 2.0 * sigma_e2
    return {
        "rho1": g.rnd(r1, 4),
        "rho1_ci95": [g.rnd(lo[0], 4), g.rnd(hi[0], 4)],
        "rho2": g.rnd(r2, 4),
        "rho2_ci95": [g.rnd(lo[1], 4), g.rnd(hi[1], 4)],
        "phi_rho2_over_rho1": g.rnd(r2 / r1, 4),
        "phi_ci95": [g.rnd(lo[2], 4), g.rnd(hi[2], 4)],
        "bootstrap": f"{N_BOOT} resamples of qubits",
        "var_change_log10": g.rnd(vdz, 6),
        "lag1_autocov_change": g.rnd(c1, 6),
        "level_plus_white_component": {
            "sigma_e2_nonpersistent": g.rnd(sigma_e2, 6),
            "sigma_e_decades": g.rnd(float(np.sqrt(sigma_e2)), 4),
            "sigma_w2_level_step_per_event": g.rnd(sigma_w2, 6),
            "share_of_change_variance_from_nonpersistent": g.rnd(2.0 * sigma_e2 / vdz, 4),
            "relative_scatter_factor_10_pow_sigma_e": g.rnd(float(10 ** np.sqrt(sigma_e2)), 4),
        },
    }


def level_dependence(series: list[Any]) -> dict[str, Any]:
    lvl, rsd, nonp = [], [], []
    for s in series:
        z = np.log10(s.y)
        dz = np.diff(z)
        mad = float(np.median(np.abs(dz - np.median(dz))))
        lvl.append(float(np.median(z)))
        rsd.append(1.4826 * mad / np.sqrt(2.0))
        c = float(np.mean((dz[:-1] - dz.mean()) * (dz[1:] - dz.mean())))
        nonp.append(np.sqrt(-c) if c < 0 else np.nan)
    lv, rs, nu = np.array(lvl), np.array(rsd), np.array(nonp)
    return {
        "robust_sd_definition": "1.4826 * MAD(log10 changes) / sqrt(2), per qubit (decades)",
        "robust_sd_q": g.q(rs, nd=4),
        "spearman_robust_sd_vs_level": g.spearman(lv, rs),
        "theil_sen_log10_robust_sd_vs_level": g.theil_sen(lv, np.log10(rs)),
        "sigma_e_per_qubit_q": g.q(nu, nd=4),
        "qubits_with_positive_lag1_autocov": int(np.sum(~np.isfinite(nu))),
        "spearman_sigma_e_vs_level": g.spearman(lv, nu),
        "theil_sen_log10_sigma_e_vs_level": g.theil_sen(lv, np.log10(nu)),
    }


def main() -> int:
    dd = ddload.DD()
    series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["field"] = g.SX_FIELD
    payload["series"] = len(series)
    payload["events"] = int(sum(s.y.size for s in series))
    vg_all = ddload.variogram(series)
    payload["variogram_all"] = vg_all
    payload["summary_all"] = summary(vg_all)
    before, after = sub(series, True), sub(series, False)
    vg_b, vg_a = ddload.variogram(before), ddload.variogram(after)
    payload["split"] = g.iso(SPLIT_MS)
    payload["variogram_before_split"] = {"series": len(before), **vg_b}
    payload["variogram_from_split"] = {"series": len(after), **vg_a}
    payload["summary_before_split"] = summary(vg_b)
    payload["summary_from_split"] = summary(vg_a)
    payload["bins_bootstrap"] = boot_bins(series)
    payload["per_entity"] = per_entity(series)
    payload["autocorrelation"] = autocorr(series)
    payload["level_dependence"] = level_dependence(series)
    ddload.write_json(g.RESULTS / "sx_variogram.json", payload)
    print("wrote", g.RESULTS / "sx_variogram.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
