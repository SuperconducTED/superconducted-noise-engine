"""Arm B null (i), exactly, in integer arithmetic: an independent route to null-values.json arm_b.exact.

Pure Python ints and dicts (no numpy, no floats until the final print), and it adds the strict-inequality
rows the PR does not state. Six layouts, 13 jobs, independent uniform rankings.
"""

import itertools
import json
import sys
from fractions import Fraction as F

N, J = 6, 13


def job_table():
    one = {}
    for perm in itertools.permutations(range(N)):
        key = (sum((p - i) ** 2 for i, p in enumerate(perm)), 1 if perm[0] == 0 else 0)
        one[key] = one.get(key, 0) + 1
    return one


def convolve(one, jobs):
    tot = {(0, 0): 1}
    for _ in range(jobs):
        nxt = {}
        for (s, h), c in tot.items():
            for (ds, dh), m in one.items():
                k = (s + ds, h + dh)
                nxt[k] = nxt.get(k, 0) + c * m
        tot = nxt
    return tot


one = job_table()
tot = convolve(one, J)
den = 720**J
assert sum(tot.values()) == den
Ss = sorted({k[0] for k in tot})
Hs = sorted({k[1] for k in tot})
ps, ph = {}, {}
for (s, h), c in tot.items():
    ps[s] = ps.get(s, 0) + c
    ph[h] = ph.get(h, 0) + c
cum_s_le, acc = {}, 0
for s in Ss:
    acc += ps[s]
    cum_s_le[s] = acc
cum_h_ge, acc = {}, 0
for h in reversed(Hs):
    acc += ph[h]
    cum_h_ge[h] = acc
rows = {s: {h: tot.get((s, h), 0) for h in Hs} for s in Ss}
both = {}
col_acc = dict.fromkeys(Hs, 0)
for s in Ss:
    run = 0
    for h in reversed(Hs):
        run += rows[s][h]
        col_acc[h] += run
        both[(s, h)] = col_acc[h]
strict_s = {s: cum_s_le[s] - ps[s] for s in Ss}
strict_h = {h: cum_h_ge[h] - ph[h] for h in Hs}
strict_both = {}
col = dict.fromkeys(Hs, 0)
for s in Ss:
    for h in Hs:
        strict_both[(s, h)] = sum(col[hh] for hh in Hs if hh > h)
    for h in Hs:
        col[h] += rows[s][h]
b1 = b2 = bj = b1o = b2o = jo = je = s1 = s2 = sj = 0
tie1 = sum(v * v for v in ps.values())
tie2 = sum(v * v for v in ph.values())
for (s, h), c in tot.items():
    q1, q2, qj = cum_s_le[s], cum_h_ge[h], both[(s, h)]
    b1 += c * q1
    b2 += c * q2
    bj += c * qj
    b1o += c * (den**2 - (den - q1) ** 2)
    b2o += c * (den**2 - (den - q2) ** 2)
    jo += c * (den**2 - (den - qj) ** 2)
    neither = den - q1 - q2 + qj
    je += c * (den**2 - (den - q1) ** 2 - (den - q2) ** 2 + neither**2)
    s1 += c * strict_s[s]
    s2 += c * strict_h[h]
    sj += c * strict_both[(s, h)]
res = {
    "b1_level": F(b1, den**2),
    "b2_level": F(b2, den**2),
    "b1_and_b2_level": F(bj, den**2),
    "b1_level_or_band": F(b1o, den**3),
    "b2_level_or_band": F(b2o, den**3),
    "joint_one_predictor_meets_both": F(jo, den**3),
    "joint_each_condition_by_either": F(je, den**3),
    "p_tie_b1_level": F(tie1, den**2),
    "p_tie_b2_level": F(tie2, den**2),
}
ref = json.load(open(sys.argv[1], encoding="utf-8"))["arm_b"]["exact"]
worst = 0.0
for k, v in res.items():
    d = abs(float(v) - ref[k])
    worst = max(worst, d)
    print(f"{k:36s} exact {float(v):.10f}  committed {ref[k]:.10f}  diff {d:.1e}")
print("largest |diff|:", worst)
print("strict B1 (level mean Spearman strictly higher):", round(float(F(s1, den**2)), 4))
print("strict B2 (level best-pick strictly more often):", round(float(F(s2, den**2)), 4))
print("strict B1 and strict B2, level alone:           ", round(float(F(sj, den**2)), 4))
# Mutation: a wrong job count must break the match.
tot12 = convolve(one, J - 1)
pp = {}
for (s, h), c in tot12.items():
    pp[h] = pp.get(h, 0) + c
t12 = float(F(sum(v * v for v in pp.values()), (720 ** (J - 1)) ** 2))
print(
    "mutation J=12: tie B2 =",
    round(t12, 4),
    "vs J=13",
    round(float(res["p_tie_b2_level"]), 4),
    "(must differ)",
)
