"""Lead and lag: does another family's recent movement on the same qubit predict the next value?

For every directed pair (predictor A, target B) of this scope's 23 pairs (46 directions):

- Target: each event ``k`` (from the sixth) of B on one entity; response ``y_k = z_k - L_{k-1}``,
  the deviation from B's own causal EWMA level. Baseline: the EWMA level (``y = 0``).
- Information set: A's events published in a file strictly before the file that first
  carried B's event (the rule of the prior linear test, P3). A coupler predictor on a qubit
  target is averaged over the qubit's adjacent couplers; a qubit predictor on a coupler target
  over its two qubits.
- A's signal at lag ``L``: the innovation ``z_j - L_{j-1}`` of A's ``L``-th most recent event.
  Forms: linear, absolute value, two jump indicators (beyond +-3 robust sd of A's training
  innovations) and quantile-bin dummies (5 bins on training quantiles).
- Models: ``lag1_all`` (every form at lag 1; the primary test), ``lags123_linear`` (linear at
  lags 1 to 3), ``strict_all`` (every form, using only A events stamped at least 3 h before B's
  stamp, so a measurement from B's own round is excluded).
- Out of time: per target family, the cut is the 70% quantile of its event times; the EWMA
  weights of A and B are chosen on events before the cut (grid 0.05 to 0.60, one-step MAE),
  ordinary least squares is fitted before it and mean absolute error is scored after it.
- Effect size: test MAE of the model over that of the INTERCEPT-ONLY reference (the EWMA
  level plus the training mean of the deviation), with a 2,000-replicate cluster bootstrap
  over target entities. Every model has an intercept, so against the bare level it would get
  a bias correction for free (a first run showed identical gains for unrelated predictors of
  the same target); ``ratio_vs_level`` and ``intercept_only_vs_level`` are reported too.
  Test: one-sided Wilcoxon signed-rank over target entities (each entity's mean improvement
  over the intercept-only reference, entities with >= 5 test events). BH at 0.05 over the
  directions that could be scored, separately for each model.

Writes ``results/cross/leadlag.json``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc
from comovement import MINE

OUT = xc.RESULTS / "leadlag.json"
WARMUP = 5
ALPHAS = np.round(np.arange(0.05, 0.601, 0.05), 2)
N_BOOT = 2000
JUMP_SD = 3.0
STRICT_GAP_MS = 3 * 3.6e6
N_BINS = 5


def ewma_innov(z: np.ndarray, alpha: float) -> np.ndarray:
    """``z_k - L_{k-1}`` for k >= 1 (NaN at k = 0), causal EWMA with ``L_0 = z_0``."""
    out = np.full(z.size, np.nan)
    lev = z[0]
    for k in range(1, z.size):
        out[k] = z[k] - lev
        lev = alpha * z[k] + (1 - alpha) * lev
    return out


def fit_alpha(fam: xc.Fam, cut_ms: float) -> float:
    best, best_mae = 0.3, np.inf
    for a in ALPHAS:
        errs = []
        for t, z in zip(fam.t_ms, fam.z, strict=True):
            inn = ewma_innov(z, float(a))
            sel = (np.arange(z.size) >= WARMUP) & (t <= cut_ms)
            errs.append(np.abs(inn[sel]))
        e = np.concatenate(errs)
        if e.size and float(np.mean(e)) < best_mae:
            best, best_mae = float(a), float(np.mean(e))
    return best


def family_cut(fam: xc.Fam) -> float:
    t = np.concatenate([t[WARMUP:] for t in fam.t_ms if t.size > WARMUP])
    return float(np.quantile(t, 0.7))


def attachments(dd: ddload.DD, b: str, a: str) -> dict[int, list[int]]:
    """For each entity of B, the entities of A whose signal is averaged."""
    b_q = b in xc.QUBIT_FAMS
    a_q = a in xc.QUBIT_FAMS
    if b_q and a_q:
        return {q: [q] for q in range(156)}
    if not b_q and a_q:
        return {k: [p[0], p[1]] for k, p in enumerate(xc.coupler_pairs(dd, b))}
    adj = xc.adjacency(xc.coupler_pairs(dd, a))
    return {q: adj[q] for q in range(156)}


def a_signal(
    fa: xc.Fam,
    inn_a: list[np.ndarray],
    targets: list[tuple[int, int, float, int]],
    att: dict[int, list[int]],
    lag: int,
    strict: bool,
) -> np.ndarray:
    """A's innovation at ``lag`` for each target event (row, B entity, B time, B file)."""
    by_ent = {int(e): i for i, e in enumerate(fa.entity)}
    sums = np.zeros(len(targets))
    cnts = np.zeros(len(targets))
    ents = np.array([e for _, e, _, _ in targets], dtype=np.int64)
    tb = np.array([t for _, _, t, _ in targets])
    fb = np.array([f for _, _, _, f in targets], dtype=np.int64)
    pairs_rows: dict[int, list[int]] = {}
    for idx, e in enumerate(ents):
        for ea in att.get(int(e), []):
            pairs_rows.setdefault(int(ea), []).append(idx)
    for ea, idxs in pairs_rows.items():
        if ea not in by_ent:
            continue
        s = by_ent[ea]
        ta, fia, ia = fa.t_ms[s], fa.file_idx[s], inn_a[s]
        ii = np.array(idxs, dtype=np.int64)
        j = np.searchsorted(fia, fb[ii] - 1, "right") - 1
        if strict:
            j = np.minimum(j, np.searchsorted(ta, tb[ii] - STRICT_GAP_MS, "left") - 1)
        j = j - (lag - 1)
        ok = j >= 1
        val = np.full(ii.size, np.nan)
        val[ok] = ia[j[ok]]
        good = np.isfinite(val)
        np.add.at(sums, ii[good], val[good])
        np.add.at(cnts, ii[good], 1.0)
    out = np.full(len(targets), np.nan)
    has = cnts > 0
    out[has] = sums[has] / cnts[has]
    return out


def design(sig: np.ndarray, train: np.ndarray, forms: str) -> np.ndarray:
    tr = sig[train & np.isfinite(sig)]
    cols = [np.ones(sig.size)]
    if forms == "linear":
        cols.append(sig)
        return np.column_stack(cols)
    s = 1.4826 * np.median(np.abs(tr - np.median(tr))) if tr.size else np.nan
    cols += [
        sig,
        np.abs(sig),
        (sig > JUMP_SD * s).astype(float),
        (sig < -JUMP_SD * s).astype(float),
    ]
    edges = np.quantile(tr, np.linspace(0, 1, N_BINS + 1))[1:-1] if tr.size else []
    b = np.searchsorted(edges, sig)
    for k in range(1, N_BINS):
        cols.append((b == k).astype(float))
    x = np.column_stack(cols)
    x[~np.isfinite(sig)] = np.nan
    return x


def score(
    x: np.ndarray,
    y: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    ent: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    ok = np.all(np.isfinite(x), axis=1) & np.isfinite(y)
    tr, te = ok & train, ok & test
    if tr.sum() < 200 or te.sum() < 100:
        return {"train_events": int(tr.sum()), "test_events": int(te.sum()), "ratio": None}
    beta, *_ = np.linalg.lstsq(x[tr], y[tr], rcond=None)
    e_m = np.abs(y[te] - x[te] @ beta)
    e_b = np.abs(y[te])
    # Intercept-only reference: the EWMA level plus the training mean of the deviation. Any
    # model with an intercept gets this bias correction for free, so the predictor's own
    # contribution is the model against THIS reference, not against the bare level.
    e_i = np.abs(y[te] - float(np.mean(y[tr])))
    ents = ent[te]
    uniq, inv = np.unique(ents, return_inverse=True)
    sm = np.bincount(inv, e_m)
    sb = np.bincount(inv, e_b)
    si = np.bincount(inv, e_i)
    cnt = np.bincount(inv)
    boots = np.empty(N_BOOT)
    boots_i = np.empty(N_BOOT)
    for r in range(N_BOOT):
        w = np.bincount(rng.integers(0, uniq.size, uniq.size), minlength=uniq.size)
        boots[r] = (w @ sm) / (w @ sb)
        boots_i[r] = (w @ sm) / (w @ si)
    keep = cnt >= 5
    diff = si[keep] / cnt[keep] - sm[keep] / cnt[keep]
    p = (
        float(wilcoxon(diff, alternative="greater").pvalue)
        if diff.size >= 10 and np.any(diff != 0)
        else np.nan
    )
    return {
        "train_events": int(tr.sum()),
        "test_events": int(te.sum()),
        "test_entities": int(uniq.size),
        "ratio_vs_level": xc.r6(float(e_m.sum() / e_b.sum())),
        "ratio_vs_level_ci95": [
            xc.r6(float(np.quantile(boots, 0.025))),
            xc.r6(float(np.quantile(boots, 0.975))),
        ],
        "intercept_only_vs_level": xc.r6(float(e_i.sum() / e_b.sum())),
        "ratio": xc.r6(float(e_m.sum() / e_i.sum())),
        "ratio_ci95": [
            xc.r6(float(np.quantile(boots_i, 0.025))),
            xc.r6(float(np.quantile(boots_i, 0.975))),
        ],
        "wilcoxon_p_greater": xc.r6(p),
        "entities_improved_share": xc.r6(float(np.mean(diff > 0))) if diff.size else None,
        "coef": [xc.r6(float(c)) for c in beta[:3]],
    }


def main() -> int:
    rng = np.random.default_rng(xc.SEED + 3)
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/leadlag.py")
    payload["n_files"] = dd.n_files
    fams = {f: xc.load(dd, f) for f in xc.ALL_FAMS}
    cuts = {f: family_cut(fams[f]) for f in xc.ALL_FAMS}
    payload["cuts_utc"] = {
        f: datetime.fromtimestamp(c / 1000.0, UTC).strftime("%Y-%m-%dT%H:%MZ")
        for f, c in cuts.items()
    }
    alpha_cache: dict[tuple[str, str], float] = {}

    def alpha(f: str, cut_of: str) -> float:
        key = (f, cut_of)
        if key not in alpha_cache:
            alpha_cache[key] = fit_alpha(fams[f], cuts[cut_of])
        return alpha_cache[key]

    directed = [(a, b) for a, b in MINE] + [(b, a) for a, b in MINE]
    rows = []
    for a, b in directed:
        fb, fa = fams[b], fams[a]
        al_b, al_a = alpha(b, b), alpha(a, b)
        inn_a = [ewma_innov(z, al_a) for z in fa.z]
        targets: list[tuple[int, int, float, int]] = []
        ys, ents, ts = [], [], []
        for e, t, fi, z in zip(fb.entity, fb.t_ms, fb.file_idx, fb.z, strict=True):
            inn = ewma_innov(z, al_b)
            for k in range(WARMUP, z.size):
                targets.append((len(ys), int(e), float(t[k]), int(fi[k])))
                ys.append(inn[k])
                ents.append(int(e))
                ts.append(float(t[k]))
        y = np.array(ys)
        ent = np.array(ents)
        tt = np.array(ts)
        train = tt <= cuts[b]
        test = ~train
        att = attachments(dd, b, a)
        sig = {
            (lag, strict): a_signal(fa, inn_a, targets, att, lag, strict)
            for lag, strict in ((1, False), (2, False), (3, False), (1, True))
        }
        x_all = design(sig[(1, False)], train, "all")
        x_lin = np.column_stack(
            [np.ones(y.size), sig[(1, False)], sig[(2, False)], sig[(3, False)]]
        )
        x_strict = design(sig[(1, True)], train, "all")
        okt = test & np.isfinite(sig[(1, False)])
        row = {
            "predictor": a,
            "target": b,
            "alpha_target": al_b,
            "alpha_predictor": al_a,
            "cut_utc": payload["cuts_utc"][b],
            "target_events": int(y.size),
            "events_with_signal": int(np.isfinite(sig[(1, False)]).sum()),
            "test_spearman_lag1": xc.r6(xc.spearman(sig[(1, False)][okt], y[okt])),
            "lag1_all": score(x_all, y, train, test, ent, rng),
            "lags123_linear": score(x_lin, y, train, test, ent, rng),
            "strict_all": score(x_strict, y, train, test, ent, rng),
        }
        rows.append(row)
        print(a, "->", b, row["lag1_all"].get("ratio"), row["strict_all"].get("ratio"), flush=True)
    for model in ("lag1_all", "lags123_linear", "strict_all"):
        tested = [
            r
            for r in rows
            if r[model].get("ratio") is not None and r[model].get("wilcoxon_p_greater") is not None
        ]
        ps = [r[model]["wilcoxon_p_greater"] for r in tested]
        for r, flag, q in zip(tested, xc.bh(ps), xc.bh_adjusted(ps), strict=True):
            r[model]["bh_reject_q05"] = flag
            r[model]["bh_q"] = q
        payload[f"bh_family_size_{model}"] = len(tested)
    payload["alphas"] = {f"{k[0]}|cut_of_{k[1]}": v for k, v in alpha_cache.items()}
    payload["pairs"] = rows
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
