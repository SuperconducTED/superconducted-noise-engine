"""Arm B's conditions on real predicted rankings: how far from null (i) is the realistic null, and each world.

Input: C:/t135/cache/armb/*.pkl from arm_b_days.py (PR #140's build_job on archive days).
Null (i) in the PR treats predictors as independent; (ii) as identical. Here predictors keep their real joint
rankings, and only the truth is random (a uniform ranking per job), which is the realistic no-information case.
Worlds: F (next changed readings), N (truth = level's model), S (truth = reading's model), with 4,096 shots.
13 consecutive available days; overlapping windows, so rates are descriptive.
"""

import glob
import pickle

import numpy as np
from scipy import stats

GHZ = np.array([0.5, 0, 0, 0, 0, 0, 0, 0.5])
SHOTS = 4096
rows = []
for p in sorted(glob.glob("C:/t135/cache/armb/*.pkl")):
    d = pickle.load(open(p, "rb"))
    pr = d["predicted"]
    if (
        any(v is None for k in ("reading", "level", "band_lo", "band_hi") for v in pr[k])
        or len(pr["level"]) != 6
    ):
        continue
    rows.append(
        {
            "t": d["t_s"],
            "reading": np.array(pr["reading"]),
            "level": np.array(pr["level"]),
            "band": 0.5 * (np.array(pr["band_lo"]) + np.array(pr["band_hi"])),
            "F": d["truth_F"],
            "N": d["truth_level"],
            "S": d["truth_reading"],
            "triples": d["log"]["triples"],
        }
    )
print("days usable", len(rows), "first", rows[0]["t"].date(), "last", rows[-1]["t"].date())
ND = len(rows)
NAMES = ("reading", "level", "band")


def rk(x):
    return stats.rankdata(x, axis=-1)


def spear(a, b):
    ra, rb = rk(a), rk(b)
    ra = ra - ra.mean(axis=-1, keepdims=True)
    rb = rb - rb.mean(axis=-1, keepdims=True)
    return (ra * rb).sum(axis=-1) / np.sqrt((ra * ra).sum(axis=-1) * (rb * rb).sum(axis=-1))


print("\nI. How alike are the rankings the predictors actually produce?")
sl = np.array([float(spear(r["level"], r["reading"])) for r in rows])
sb = np.array([float(spear(r["level"], r["band"])) for r in rows])
same_rank = np.mean([np.all(np.argsort(r["level"]) == np.argsort(r["reading"])) for r in rows])
same_top = np.mean([np.argmax(r["level"]) == np.argmax(r["reading"]) for r in rows])
same_rank_b = np.mean([np.all(np.argsort(r["level"]) == np.argsort(r["band"])) for r in rows])
same_top_b = np.mean([np.argmax(r["level"]) == np.argmax(r["band"]) for r in rows])
print(
    f"level vs reading: Spearman median {np.median(sl):.3f} (10th pct {np.percentile(sl, 10):.3f}), identical ranking {same_rank:.3f}, same top pick {same_top:.3f}"
)
print(
    f"level vs band midpoint: Spearman median {np.median(sb):.3f} (10th pct {np.percentile(sb, 10):.3f}), identical ranking {same_rank_b:.3f}, same top pick {same_top_b:.3f}"
)
span = np.array([r["level"].max() - r["level"].min() for r in rows])
print(
    f"predicted fidelity span under level, median {np.median(span):.3f}; eligible triples per day, median {np.median([r['triples'] for r in rows]):.0f}"
)


def window_starts():
    return [i for i in range(ND - 12) if (rows[i + 12]["t"] - rows[i]["t"]).days == 12]


def evaluate(meas, label, quiet=False):
    """meas: reps x days x 6. Returns pass rates over consecutive 13-day windows."""
    out = {}
    W = window_starts()
    reps = meas.shape[0]
    preds = {n: np.stack([r[n] for r in rows]) for n in NAMES}
    sp = {n: spear(np.broadcast_to(preds[n], meas.shape), meas) for n in NAMES}  # reps x days
    best = meas.argmax(axis=2)  # reps x days
    hit = {n: (preds[n].argmax(axis=1)[None, :] == best) for n in NAMES}
    day_i = np.arange(ND)
    regret = {}
    for n in NAMES:
        pick = preds[n].argmax(axis=1)
        regret[n] = meas.max(axis=2) - meas[:, day_i, pick]
    tally = {
        k: []
        for k in (
            "B1",
            "B2",
            "B12_level",
            "B1s",
            "B2s",
            "B12s",
            "B1_or",
            "B2_or",
            "joint_one",
            "joint_each",
            "tieB1",
            "tieB2",
            "paired_rho",
            "paired_regret",
            "rho_level",
            "rho_reading",
            "hit_level",
            "hit_reading",
        )
    }
    for rep in range(reps):
        for i in W:
            s = {n: sp[n][rep, i : i + 13].mean() for n in NAMES}
            h = {n: hit[n][rep, i : i + 13].sum() for n in NAMES}
            b1l, b1b = s["level"] >= s["reading"], s["band"] >= s["reading"]
            b2l, b2b = h["level"] >= h["reading"], h["band"] >= h["reading"]
            tally["B1"].append(b1l)
            tally["B2"].append(b2l)
            tally["B12_level"].append(b1l and b2l)
            tally["B1s"].append(s["level"] > s["reading"])
            tally["B2s"].append(h["level"] > h["reading"])
            tally["B12s"].append(s["level"] > s["reading"] and h["level"] > h["reading"])
            tally["B1_or"].append(b1l or b1b)
            tally["B2_or"].append(b2l or b2b)
            tally["joint_one"].append((b1l and b2l) or (b1b and b2b))
            tally["joint_each"].append((b1l or b1b) and (b2l or b2b))
            tally["tieB1"].append(np.isclose(s["level"], s["reading"]))
            tally["tieB2"].append(h["level"] == h["reading"])
            tally["rho_level"].append(s["level"])
            tally["rho_reading"].append(s["reading"])
            tally["hit_level"].append(h["level"])
            tally["hit_reading"].append(h["reading"])
            # A paired rule: batch-means t on 4 consecutive batches, one-sided 5%
            for key, dv in (
                ("paired_rho", sp["level"][rep, i : i + 13] - sp["reading"][rep, i : i + 13]),
                (
                    "paired_regret",
                    regret["reading"][rep, i : i + 13] - regret["level"][rep, i : i + 13],
                ),
            ):
                gr = np.array_split(dv, 4)
                m = np.array([g.mean() for g in gr])
                sd = m.std(ddof=1)
                t = m.mean() / (sd / 2.0) if sd > 0 else 0.0
                tally[key].append(sd > 0 and t > stats.t.ppf(0.95, 3))
    out = {k: float(np.mean(v)) for k, v in tally.items()}
    if quiet:
        return out
    print(
        f"{label:30s} B1 {out['B1']:.3f} B2 {out['B2']:.3f} both {out['B12_level']:.3f} | strict B1 {out['B1s']:.3f} B2 {out['B2s']:.3f} both {out['B12s']:.3f} | or: B1 {out['B1_or']:.3f} B2 {out['B2_or']:.3f} one {out['joint_one']:.3f} each {out['joint_each']:.3f} | tie B1 {out['tieB1']:.3f} B2 {out['tieB2']:.3f} | paired rho {out['paired_rho']:.3f} regret {out['paired_regret']:.3f}"
    )
    print(
        f"{'':30s} mean rho level {out['rho_level']:.3f} reading {out['rho_reading']:.3f}; best-pick count of 13 level {out['hit_level']:.2f} reading {out['hit_reading']:.2f}"
    )
    return out


kids = iter(np.random.SeedSequence(135110705).spawn(10))
rng = np.random.default_rng(next(kids))
print(
    "\nII. Pass rates over consecutive 13-day windows (level alone unless named). Committed null (i): B1 0.505, B2 0.606, both 0.375; or-column 0.672, 0.758, 0.536 / 0.560."
)
print(
    "Mutation check of this code on independent random rankings for every predictor must reproduce null (i):"
)
save = {n: [r[n].copy() for r in rows] for n in NAMES}
ev = {}
draws = []
for _draw in range(40):
    for r in rows:
        for n in NAMES:
            r[n] = rng.random(6)
    draws.append(evaluate(rng.random((20, ND, 6)), "", quiet=True))
ev["i"] = {k: float(np.mean([d[k] for d in draws])) for k in draws[0]}
o = ev["i"]
print(
    f"{'independent, 40 draws':30s} B1 {o['B1']:.3f} B2 {o['B2']:.3f} both {o['B12_level']:.3f} | strict B1 {o['B1s']:.3f} B2 {o['B2s']:.3f} both {o['B12s']:.3f} | or: B1 {o['B1_or']:.3f} B2 {o['B2_or']:.3f} one {o['joint_one']:.3f} each {o['joint_each']:.3f} | tie B1 {o['tieB1']:.3f} B2 {o['tieB2']:.3f} | paired rho {o['paired_rho']:.3f} regret {o['paired_regret']:.3f}"
)
for j, r in enumerate(rows):
    for n in NAMES:
        r[n] = save[n][j]
print(
    "\nReal predictor rankings, truth a uniform random ranking per job (the realistic no-information case):"
)
ev["real"] = evaluate(rng.random((400, ND, 6)), "real rankings, random truth")


def measured(world, reps):
    out = np.empty((reps, ND, 6))
    for d, r in enumerate(rows):
        for k in range(6):
            dist = r[world][k]
            if dist is None:
                dist = r["N"][k]
            pv = np.clip(np.asarray(dist, dtype=float), 0, None)
            pv = pv / pv.sum()
            c = rng.multinomial(SHOTS, pv, size=reps) / SHOTS
            out[:, d, k] = np.sum(np.sqrt(c * GHZ), axis=1) ** 2
    return out


print("\nWorlds, with 4,096 shots per layout:")
sds = []
for world, label in (
    ("N", "N truth = level's model"),
    ("F", "F next changed readings"),
    ("S", "S truth = reading's model"),
):
    m = measured(world, 60)
    ev[world] = evaluate(m, label)
    sds.append(m.std(axis=0).mean())
    s = np.sort(m.mean(axis=0), axis=1)
    gap = s[:, -1] - s[:, -2]
    print(
        f"{'':30s} shot sd of a fidelity {m.std(axis=0).mean():.4f}; best minus second-best, median {np.median(gap):.4f}; share of jobs with gap < 2 shot sd {np.mean(gap < 2 * m.std(axis=0).mean()):.3f}"
    )
none_f = sum(1 for r in rows for x in r["F"] if x is None)
print(
    "layouts with no usable next-reading truth in world F (fell back to level's model):",
    none_f,
    "of",
    6 * ND,
)
pickle.dump(ev, open("C:/t135/cache/armb_eval.pkl", "wb"))
