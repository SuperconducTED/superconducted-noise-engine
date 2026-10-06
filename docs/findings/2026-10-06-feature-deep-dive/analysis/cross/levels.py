"""Between-entity structure: per-qubit levels of every informative field, and what they share.

For each qubit and family the LEVEL is the median of the family's ``log10`` event values over
its lifetime (sensitivity: the mean, and the median over the common window from 2026-08-07,
the ``measure_2`` schema start). Coupler families enter as the mean of the qubit's adjacent
coupler levels (``adj_cz``, ``adj_rzz``, ``adj_zz``).

Outputs (``results/cross/levels.json``):

- Spearman correlation of levels for every pair of fields, with a cluster bootstrap over
  qubits (95% interval) and a permutation p-value; Benjamini-Hochberg over THIS scope's pairs
  only (pairs owned elsewhere are reported with their owner id and not tested).
- Partial correlations from the inverse of the normal-score correlation matrix.
- Mutual information (KSG, k = 4, on ranks) minus its permutation-null mean, and the MI a
  Gaussian copula with the same normal-score correlation would carry.
- Moran's I of each field's level on the coupling graph (a check on effective sample size).
- PCA of the normal-score level matrix with parallel analysis and bootstrap loadings.
- Archetypes: Ward clustering for k = 2..6, silhouette against a column-permuted null, and
  stability as the adjusted Rand index under bootstrap resampling.
- Spatial pattern of the first component scores (Moran's I, Spearman against coordinates).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial import cKDTree
from scipy.special import digamma
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc

OUT = xc.RESULTS / "levels.json"
N_Q = 156
COMMON_START_MS = 1_786_060_800_000.0  # 2026-08-07T00:00:00Z
N_BOOT = 2000
N_PERM = 2000
N_MI_PERM = 1000
N_PA = 1000
N_CLUSTER_BOOT = 200
N_SIL_NULL = 200
KSG_K = 4


def levels(dd: ddload.DD, start_ms: float | None = None) -> dict[str, dict[str, np.ndarray]]:
    """Per-qubit median and mean of ``log10`` event values for every family in QUBIT_VIEW."""
    out: dict[str, dict[str, np.ndarray]] = {"median": {}, "mean": {}, "events": {}}
    for fam in xc.ALL_FAMS:
        f = xc.load(dd, fam)
        width = N_Q if fam in xc.QUBIT_FAMS else len(xc.coupler_pairs(dd, fam))
        med = np.full(width, np.nan)
        mean = np.full(width, np.nan)
        cnt = np.zeros(width)
        for e, t, z in zip(f.entity, f.t_ms, f.z, strict=True):
            zz = z if start_ms is None else z[t >= start_ms]
            if zz.size:
                med[e], mean[e], cnt[e] = np.median(zz), np.mean(zz), zz.size
        if fam in xc.QUBIT_FAMS:
            out["median"][fam], out["mean"][fam], out["events"][fam] = med, mean, cnt
        else:
            pairs = xc.coupler_pairs(dd, fam)
            key = f"adj_{fam}"
            out["median"][key] = xc.to_qubits(med[None, :], pairs)[0]
            out["mean"][key] = xc.to_qubits(mean[None, :], pairs)[0]
            out["events"][key] = xc.to_qubits(cnt[None, :], pairs)[0]
    return out


def normal_scores(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    r = xc.rankdata(x[ok])
    out[ok] = norm.ppf(r / (ok.sum() + 1.0))
    return out


def ksg_mi(x: np.ndarray, y: np.ndarray, k: int = KSG_K) -> float:
    """Kraskov-Stoegbauer-Grassberger estimator 1 (nats), max-norm, on the given values."""
    n = x.size
    pts = np.column_stack([x, y])
    tree = cKDTree(pts)
    dist, _ = tree.query(pts, k=k + 1, p=np.inf)
    eps = dist[:, k]
    xs, ys = np.sort(x), np.sort(y)
    nx = np.searchsorted(xs, x + eps, "left") - np.searchsorted(xs, x - eps, "right") - 1
    ny = np.searchsorted(ys, y + eps, "left") - np.searchsorted(ys, y - eps, "right") - 1
    nx, ny = np.maximum(nx, 0), np.maximum(ny, 0)
    return float(digamma(k) + digamma(n) - np.mean(digamma(nx + 1) + digamma(ny + 1)))


def rank_unit(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Ranks scaled to (0, 1) with tiny jitter to break ties (KSG needs distinct values)."""
    r = xc.rankdata(x) + rng.uniform(-1e-6, 1e-6, x.size)
    out: np.ndarray = r / (x.size + 1.0)
    return out


def morans_i(v: np.ndarray, edges: list[tuple[int, int]], rng: np.random.Generator) -> Any:
    ok = np.isfinite(v)
    e = [(a, b) for a, b in edges if ok[a] and ok[b]]
    if len(e) < 10:
        return None
    ia = np.array([a for a, _ in e])
    ib = np.array([b for _, b in e])
    idx = np.flatnonzero(ok)

    def stat(x: np.ndarray) -> float:
        m = x[idx].mean()
        dev = x - m
        num = float(np.sum(dev[ia] * dev[ib])) * 2.0
        den = float(np.sum(dev[idx] ** 2))
        return (idx.size / (2.0 * len(e))) * num / den

    obs = stat(v)
    null = np.empty(999)
    for r in range(999):
        x = v.copy()
        x[idx] = rng.permutation(v[idx])
        null[r] = stat(x)
    dev = np.abs(null - null.mean())
    return {
        "I": round(obs, 4),
        "null_mean": round(float(null.mean()), 4),
        "null_q025_q975": [
            round(float(np.quantile(null, 0.025)), 4),
            round(float(np.quantile(null, 0.975)), 4),
        ],
        "p_perm_greater": round(float((1 + np.sum(null >= obs)) / 1000.0), 4),
        "p_perm_two_sided": round(float((1 + np.sum(dev >= abs(obs - null.mean()))) / 1000.0), 4),
        "qubits": int(idx.size),
        "edges": len(e),
    }


def pca(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    c = np.corrcoef(z, rowvar=False)
    w, v = np.linalg.eigh(c)
    order = np.argsort(w)[::-1]
    return w[order], v[:, order]


def align_sign(v: np.ndarray, ref: np.ndarray) -> np.ndarray:
    out: np.ndarray = v * (1.0 if float(v @ ref) >= 0 else -1.0)
    return out


def ari(a: np.ndarray, b: np.ndarray) -> float:
    """Adjusted Rand index (Hubert and Arabie 1985) of two label vectors."""
    ua, ia = np.unique(a, return_inverse=True)
    ub, ib = np.unique(b, return_inverse=True)
    table = np.zeros((ua.size, ub.size))
    np.add.at(table, (ia, ib), 1)

    def c2(x: np.ndarray | float) -> np.ndarray | float:
        return x * (np.asarray(x) - 1) / 2.0

    sum_ij = float(np.sum(c2(table)))
    sum_a = float(np.sum(c2(table.sum(axis=1))))
    sum_b = float(np.sum(c2(table.sum(axis=0))))
    n = float(a.size)
    expected = sum_a * sum_b / (n * (n - 1) / 2.0)
    max_idx = (sum_a + sum_b) / 2.0
    return (sum_ij - expected) / (max_idx - expected) if max_idx != expected else 1.0


def silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    d = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(-1))
    s = np.zeros(x.shape[0])
    labs = np.unique(labels)
    for i in range(x.shape[0]):
        own = labels == labels[i]
        if own.sum() <= 1:
            s[i] = 0.0
            continue
        a = d[i, own].sum() / (own.sum() - 1)
        b = min(d[i, labels == m].mean() for m in labs if m != labels[i])
        s[i] = (b - a) / max(a, b)
    return float(s.mean())


def ward(x: np.ndarray, k: int) -> np.ndarray:
    out: np.ndarray = fcluster(linkage(x, method="ward"), k, criterion="maxclust")
    return out


def main() -> int:
    rng = np.random.default_rng(xc.SEED)
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/levels.py")
    payload["n_files"] = dd.n_files
    lv = levels(dd)
    lv_common = levels(dd, COMMON_START_MS)
    fields = list(xc.QUBIT_VIEW)
    med = np.column_stack([lv["median"][f] for f in fields])
    mean = np.column_stack([lv["mean"][f] for f in fields])
    medc = np.column_stack([lv_common["median"][f] for f in fields])
    payload["fields"] = fields
    payload["level_definition"] = (
        "median of the family's log10 event values per qubit over its lifetime; coupler "
        "families as the mean of the qubit's adjacent coupler levels"
    )
    payload["qubits_with_level"] = {
        f: int(np.isfinite(med[:, i]).sum()) for i, f in enumerate(fields)
    }
    payload["qubits_missing"] = {
        f: [int(q) for q in np.flatnonzero(~np.isfinite(med[:, i]))][:60]
        for i, f in enumerate(fields)
    }
    payload["events_per_qubit_median"] = {
        f: xc.r6(float(np.nanmedian(lv["events"][f]))) for f in fields
    }
    payload["level_quantiles_log10"] = {
        f: xc.q_list(med[:, i], (0.0, 0.1, 0.5, 0.9, 1.0)) for i, f in enumerate(fields)
    }

    # ---- pairwise Spearman with bootstrap and permutation; BH over this scope's pairs
    pair_rows: list[dict[str, Any]] = []
    for i, a in enumerate(fields):
        for j in range(i + 1, len(fields)):
            b = fields[j]
            owner = xc.pair_owner(a, b)
            x, y = med[:, i], med[:, j]
            ok = np.isfinite(x) & np.isfinite(y)
            xo, yo = x[ok], y[ok]
            n = int(ok.sum())
            rho = xc.spearman(xo, yo)
            row: dict[str, Any] = {
                "a": a,
                "b": b,
                "owner": owner,
                "n_qubits": n,
                "spearman": xc.r6(rho),
                "spearman_mean_levels": xc.r6(xc.spearman(mean[:, i], mean[:, j])),
                "spearman_common_window": xc.r6(xc.spearman(medc[:, i], medc[:, j])),
            }
            if owner == "07":
                rx, ry = xc.rankdata(xo), xc.rankdata(yo)
                boots = np.empty(N_BOOT)
                for r in range(N_BOOT):
                    k = rng.integers(0, n, n)
                    boots[r] = np.corrcoef(xc.rankdata(xo[k]), xc.rankdata(yo[k]))[0, 1]
                null = np.array([np.corrcoef(rx, rng.permutation(ry))[0, 1] for _ in range(N_PERM)])
                row["spearman_ci95"] = [
                    xc.r6(float(np.nanquantile(boots, 0.025))),
                    xc.r6(float(np.nanquantile(boots, 0.975))),
                ]
                row["p_perm_two_sided"] = float(
                    (1 + np.sum(np.abs(null) >= abs(rho))) / (N_PERM + 1.0)
                )
                ux, uy = rank_unit(xo, rng), rank_unit(yo, rng)
                mi = ksg_mi(ux, uy)
                mi_null = np.array([ksg_mi(ux, rng.permutation(uy)) for _ in range(N_MI_PERM)])
                ns_r = float(np.corrcoef(normal_scores(xo), normal_scores(yo))[0, 1])
                row["mi_ksg_nats"] = xc.r6(mi)
                row["mi_null_mean"] = xc.r6(float(mi_null.mean()))
                row["mi_null_q95"] = xc.r6(float(np.quantile(mi_null, 0.95)))
                row["mi_excess_over_null"] = xc.r6(mi - float(mi_null.mean()))
                row["mi_p_perm"] = float((1 + np.sum(mi_null >= mi)) / (N_MI_PERM + 1.0))
                row["normal_score_r"] = xc.r6(ns_r)
                row["mi_gaussian_copula_nats"] = xc.r6(-0.5 * math.log(1 - ns_r * ns_r))
            pair_rows.append(row)
    mine = [r for r in pair_rows if r["owner"] == "07"]
    rej = xc.bh([r["p_perm_two_sided"] for r in mine])
    qv = xc.bh_adjusted([r["p_perm_two_sided"] for r in mine])
    rej_mi = xc.bh([r["mi_p_perm"] for r in mine])
    for r, flag, q, fmi in zip(mine, rej, qv, rej_mi, strict=True):
        r["bh_reject_q05"] = flag
        r["bh_q"] = q
        r["mi_bh_reject_q05"] = fmi
    payload["pairs"] = pair_rows
    payload["bh_family_size_spearman"] = len(mine)
    payload["bh_family_size_mi"] = len(mine)
    payload["bootstrap_reps"] = N_BOOT
    payload["permutation_reps"] = N_PERM
    payload["mi_permutation_reps"] = N_MI_PERM

    # ---- Moran's I of each level on the coupling graph
    edges = [(int(a), int(b)) for a, b in xc.coupler_pairs(dd, "zz")]
    payload["morans_i_levels"] = {f: morans_i(med[:, i], edges, rng) for i, f in enumerate(fields)}

    # ---- complete-case sets for partial correlation, PCA and clustering
    sets = {
        "A_10_fields_no_init": [f for f in fields if f != "init"],
        "B_11_fields_with_init": fields,
        "C_9_fields_no_init_no_RO": [f for f in fields if f not in ("init", "RO")],
    }
    multi: dict[str, Any] = {}
    for name, fs in sets.items():
        cols = [fields.index(f) for f in fs]
        m = med[:, cols]
        okq = np.all(np.isfinite(m), axis=1)
        qubits = np.flatnonzero(okq)
        zmat = np.column_stack([normal_scores(m[okq, c]) for c in range(len(fs))])
        corr = np.corrcoef(zmat, rowvar=False)
        prec = np.linalg.inv(corr)
        dg = np.sqrt(np.diag(prec))
        pcor = -prec / np.outer(dg, dg)
        np.fill_diagonal(pcor, 1.0)
        boot_p = np.empty((N_BOOT // 4, len(fs), len(fs)))
        for r in range(boot_p.shape[0]):
            k = rng.integers(0, qubits.size, qubits.size)
            zb = np.column_stack([normal_scores(m[okq][k, c]) for c in range(len(fs))])
            pb = np.linalg.inv(np.corrcoef(zb, rowvar=False))
            db = np.sqrt(np.diag(pb))
            boot_p[r] = -pb / np.outer(db, db)
        partial_rows = []
        dof = qubits.size - 3 - (len(fs) - 2)
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                owner = xc.pair_owner(fs[i], fs[j])
                zf = math.atanh(float(np.clip(pcor[i, j], -0.999999, 0.999999))) * math.sqrt(dof)
                partial_rows.append(
                    {
                        "a": fs[i],
                        "b": fs[j],
                        "owner": owner,
                        "partial": xc.r6(float(pcor[i, j])),
                        "partial_ci95": [
                            xc.r6(float(np.quantile(boot_p[:, i, j], 0.025))),
                            xc.r6(float(np.quantile(boot_p[:, i, j], 0.975))),
                        ],
                        "p_fisher_z": xc.r6(float(2 * norm.sf(abs(zf)))),
                    }
                )
        mine_p = [r for r in partial_rows if r["owner"] == "07"]
        for r, flag, q in zip(
            mine_p,
            xc.bh([r["p_fisher_z"] for r in mine_p]),
            xc.bh_adjusted([r["p_fisher_z"] for r in mine_p]),
            strict=True,
        ):
            r["bh_reject_q05"] = flag
            r["bh_q"] = q
        w, v = pca(zmat)
        pa = np.empty((N_PA, len(fs)))
        for r in range(N_PA):
            zp = np.column_stack([rng.permutation(zmat[:, c]) for c in range(len(fs))])
            pa[r] = pca(zp)[0]
        boot_load = np.empty((N_BOOT // 4, 3, len(fs)))
        for r in range(boot_load.shape[0]):
            k = rng.integers(0, qubits.size, qubits.size)
            _, vb = pca(zmat[k])
            for c in range(3):
                boot_load[r, c] = align_sign(vb[:, c], v[:, c])
        scores = zmat @ v[:, :3]
        comp = []
        for c in range(min(4, len(fs))):
            comp.append(
                {
                    "component": c + 1,
                    "eigenvalue": xc.r6(float(w[c])),
                    "variance_share": xc.r6(float(w[c] / w.sum())),
                    "parallel_analysis_q95": xc.r6(float(np.quantile(pa[:, c], 0.95))),
                    "exceeds_parallel_analysis": bool(w[c] > np.quantile(pa[:, c], 0.95)),
                    "loadings": {f: xc.r6(float(v[i, c])) for i, f in enumerate(fs)},
                    "loadings_ci95": (
                        {
                            f: [
                                xc.r6(float(np.quantile(boot_load[:, c, i], 0.025))),
                                xc.r6(float(np.quantile(boot_load[:, c, i], 0.975))),
                            ]
                            for i, f in enumerate(fs)
                        }
                        if c < 3
                        else None
                    ),
                }
            )
        multi[name] = {
            "fields": fs,
            "qubits": int(qubits.size),
            "qubits_excluded": [int(q) for q in np.flatnonzero(~okq)][:60],
            "normal_score_corr": [[xc.r6(float(x)) for x in row] for row in corr],
            "partial_correlations": partial_rows,
            "pca": comp,
            "pca_bootstrap_reps": boot_load.shape[0],
            "parallel_analysis_reps": N_PA,
        }
        if name == "A_10_fields_no_init":
            coords = np.array(next(iter(dd.meta["config_values"]["coords"].values()))["value"])
            cx, cy = coords[qubits, 0].astype(float), coords[qubits, 1].astype(float)
            radial = np.hypot(cx - cx.mean(), cy - cy.mean())
            sp: dict[str, Any] = {}
            for c in range(3):
                full = np.full(N_Q, np.nan)
                full[qubits] = scores[:, c]
                sp[f"pc{c + 1}"] = {
                    "morans_i": morans_i(full, edges, rng),
                    "spearman_coord_x": xc.r6(xc.spearman(scores[:, c], cx)),
                    "spearman_coord_y": xc.r6(xc.spearman(scores[:, c], cy)),
                    "spearman_radial": xc.r6(xc.spearman(scores[:, c], radial)),
                }
            multi[name]["pc_spatial"] = sp
            pc1 = scores[:, 0]
            order = np.argsort(pc1)
            multi[name]["pc1_extreme_qubits"] = {
                "lowest_10": [int(qubits[i]) for i in order[:10]],
                "highest_10": [int(qubits[i]) for i in order[-10:][::-1]],
            }
            degree = np.zeros(N_Q)
            for a, b in edges:
                degree[a] += 1
                degree[b] += 1
            for c in range(3):
                sp[f"pc{c + 1}"]["spearman_degree"] = xc.r6(
                    xc.spearman(scores[:, c], degree[qubits])
                )
            # ---- archetypes (Ward on normal scores)
            # Two nulls: independent columns (destroys the correlation between fields) and a
            # Gaussian with the observed correlation matrix (keeps it; clusters beyond this
            # null are more than a correlated continuum).
            chol = np.linalg.cholesky(corr)
            arche: dict[str, Any] = {}
            for k in range(2, 7):
                lab = ward(zmat, k)
                sil = silhouette(zmat, lab)
                null_sil = []
                gauss_sil = []
                for _ in range(N_SIL_NULL):
                    zp = np.column_stack([rng.permutation(zmat[:, c]) for c in range(len(fs))])
                    null_sil.append(silhouette(zp, ward(zp, k)))
                    zg = rng.standard_normal(zmat.shape) @ chol.T
                    gauss_sil.append(silhouette(zg, ward(zg, k)))
                aris = []
                for _ in range(N_CLUSTER_BOOT):
                    kk = rng.integers(0, qubits.size, qubits.size)
                    zb = zmat[kk]
                    lb = ward(zb, k)
                    cents = np.array([zb[lb == m].mean(axis=0) for m in np.unique(lb)])
                    assign = np.argmin(((zmat[:, None, :] - cents[None]) ** 2).sum(-1), axis=1)
                    aris.append(ari(lab, assign))
                sizes = np.bincount(lab)[1:]
                prof = {
                    int(m): {
                        "size": int((lab == m).sum()),
                        "median_normal_score": {
                            f: xc.r6(float(np.median(zmat[lab == m, i]))) for i, f in enumerate(fs)
                        },
                        "qubits": [int(q) for q in qubits[lab == m]][:40],
                    }
                    for m in np.unique(lab)
                }
                lab_full = np.full(N_Q, -1)
                lab_full[qubits] = lab
                same = [
                    lab_full[a] == lab_full[b]
                    for a, b in edges
                    if lab_full[a] >= 0 and lab_full[b] >= 0
                ]
                same_null = []
                for _ in range(999):
                    perm = lab_full.copy()
                    perm[qubits] = rng.permutation(lab)
                    same_null.append(
                        np.mean(
                            [perm[a] == perm[b] for a, b in edges if perm[a] >= 0 and perm[b] >= 0]
                        )
                    )
                arche[f"k{k}"] = {
                    "silhouette": xc.r6(sil),
                    "silhouette_null_mean": xc.r6(float(np.mean(null_sil))),
                    "silhouette_null_q95": xc.r6(float(np.quantile(null_sil, 0.95))),
                    "exceeds_null_q95": bool(sil > np.quantile(null_sil, 0.95)),
                    "silhouette_gaussian_null_mean": xc.r6(float(np.mean(gauss_sil))),
                    "silhouette_gaussian_null_q95": xc.r6(float(np.quantile(gauss_sil, 0.95))),
                    "exceeds_gaussian_null_q95": bool(sil > np.quantile(gauss_sil, 0.95)),
                    "p_gaussian_null": xc.r6(
                        float((1 + np.sum(np.array(gauss_sil) >= sil)) / (N_SIL_NULL + 1.0))
                    ),
                    "bootstrap_ari_median": xc.r6(float(np.median(aris))),
                    "bootstrap_ari_q10_q90": [
                        xc.r6(float(np.quantile(aris, 0.1))),
                        xc.r6(float(np.quantile(aris, 0.9))),
                    ],
                    "sizes": sizes.tolist(),
                    "neighbour_same_label_share": xc.r6(float(np.mean(same))),
                    "neighbour_same_label_null_mean": xc.r6(float(np.mean(same_null))),
                    "neighbour_same_label_p": xc.r6(
                        float((1 + np.sum(np.array(same_null) >= np.mean(same))) / 1000.0)
                    ),
                    "profiles": prof,
                }
            multi[name]["archetypes_ward"] = arche
            multi[name]["archetype_method"] = (
                "Ward linkage on the normal-score level matrix; silhouette nulls from "
                f"{N_SIL_NULL} column-permuted matrices and {N_SIL_NULL} Gaussian draws with the "
                "observed correlation matrix; stability = ARI between the full-data labels and "
                f"nearest-centroid labels from {N_CLUSTER_BOOT} bootstrap refits"
            )
    payload["multivariate"] = multi
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
