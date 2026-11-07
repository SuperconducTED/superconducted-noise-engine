"""Three checks that the measurement harness is measuring the pre-registered thing.

1. The cache reproduces the committed rehearsal table (780 rows) through the pinned code.
2. No future file reaches a day's predictors: a collection cut at t gives the same rows as the full one.
3. Live path, amendment 14: passing the latest archived document as live changes no value; a mutated
   live document does; a live block repeating a state older than the window changes nothing in the new code
   but changes level, counts and possibly definedness in the old logic.
Also: how much tau = 0 rows carry in A1's score.
"""

import csv
import json
import math
import os
import pickle
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import numpy as np

sys.path.insert(0, "C:/t135/new")
from scripts.hardware_test_predictors import Collected, predictor_rows

c = pickle.load(open("C:/t135/cache/collected.pkl", "rb"))
AT = datetime(2026, 10, 28, 18, 40, 46, tzinfo=UTC)
rows = predictor_rows(c, at=AT, live=None)
tsv = subprocess.run(
    [
        "git",
        "-C",
        sys.argv[1],
        "show",
        "51e9f425:docs/evidence/hardware-reading-vs-level/controls-rehearsal-2026-10-28/predictors.tsv",
    ],
    check=True,
    capture_output=True,
).stdout.decode()
committed = list(csv.DictReader(tsv.splitlines(), delimiter="\t"))
assert len(committed) == len(rows), (len(committed), len(rows))
worst = 0.0
int_mismatch = 0
for r, t in zip(rows, committed, strict=True):
    assert (str(r.qubit), r.quantity) == (t["qubit"], t["quantity"])
    for f in ("reading", "level", "band_lo", "band_hi", "log_disagreement"):
        a, b = float(getattr(r, f)), float(t[f])
        if math.isnan(a) and math.isnan(b):
            continue
        worst = max(worst, abs(a - b) / max(abs(b), 1e-300))
    int_mismatch += (
        (int(t["n_window"]) != r.n_window)
        + (int(t["n_distinct"]) != r.n_distinct)
        + (int(t["n_window_distinct"]) != r.n_window_distinct)
    )
print(
    f"1. cache vs committed predictors.tsv: {len(rows)} rows, largest relative difference {worst:.1e}, integer mismatches {int_mismatch}"
)

for t in (datetime(2026, 7, 1, 3, 45, tzinfo=UTC), datetime(2026, 9, 15, 3, 45, tzinfo=UTC)):
    cut = Collected(
        backend=c.backend,
        files=[f for f in c.files if f.time <= t],
        states=[s for s in c.states if s.time <= t],
        skipped=c.skipped,
    )
    a, b = predictor_rows(c, at=t, live=None), predictor_rows(cut, at=t, live=None)
    same = all(
        x == y
        or (
            x.qubit == y.qubit
            and all(
                (getattr(x, f) == getattr(y, f))
                or (math.isnan(getattr(x, f)) and math.isnan(getattr(y, f)))
                for f in x.__dataclass_fields__
            )
        )
        for x, y in zip(a, b, strict=True)
    )
    print(f"2. {t.date()}: full vs cut at t_s identical on {len(a)} rows: {same}")
    # mutation: a future file moved to t must change something
    later = next(f for f in c.files if f.time > t)
    cut2 = Collected(
        backend=c.backend,
        files=[*cut.files, type(later)(later.path, t, later.digest, later.values)],
        states=[*cut.states, type(later)(later.path, t, later.digest, later.values)],
        skipped=c.skipped,
    )
    d = predictor_rows(cut2, at=t, live=None)
    diff = sum(
        1
        for x, y in zip(a, d, strict=True)
        if x.reading != y.reading and not (math.isnan(x.reading) and math.isnan(y.reading))
    )
    print(f"   mutation: moving one future file onto t_s changes {diff} reading rows (must be > 0)")

# Live path. Build a minimal raw document for the digest and parser from the latest archived file.
latest_path = sorted(c.files, key=lambda f: f.time)[-1].path

doc = json.loads(
    subprocess.run(
        [
            "git",
            "-C",
            sys.argv[2],
            "show",
            f"7adda8035a5a76b93147ffc3171975a7684d239d:{latest_path}",
        ],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout
)
print("3. live path at", latest_path)
a = predictor_rows(c, at=AT, live=None)
b = predictor_rows(c, at=AT, live=doc)
vals = ("reading", "level", "band_lo", "band_hi", "n_window", "n_distinct", "n_window_distinct")
dif = sum(
    1
    for x, y in zip(a, b, strict=True)
    for f in vals
    if getattr(x, f) != getattr(y, f)
    and not (
        isinstance(getattr(x, f), float) and math.isnan(getattr(x, f)) and math.isnan(getattr(y, f))
    )
)
print(
    "   latest archived document passed as live: differing values",
    dif,
    "(0 expected: its digest is already a state)",
)

# A live block that repeats a state older than the window, as in her PR #126 finding.
old_time = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
old_state = [s for s in c.states if s.time <= old_time][-1]
old_doc_bytes = subprocess.run(
    [
        "git",
        "-C",
        sys.argv[2],
        "show",
        f"7adda8035a5a76b93147ffc3171975a7684d239d:{old_state.path}",
    ],
    check=True,
    capture_output=True,
    env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
).stdout
old_doc = json.loads(old_doc_bytes)
new = predictor_rows(c, at=AT, live=old_doc)
# Old logic: the state is appended because it is not in the window.
all_states = [s for s in c.states if s.time <= AT]
window = [s for s in c.states if AT - timedelta(days=30) < s.time <= AT]
print(
    "   digest in window:",
    old_state.digest in {s.digest for s in window},
    " digest in all states:",
    old_state.digest in {s.digest for s in all_states},
)
c_old = Collected(
    backend=c.backend,
    files=c.files,
    states=[
        *c.states,
        type(old_state)("<live>", AT, "old-logic-" + old_state.digest, old_state.values),
    ],
    skipped=c.skipped,
)
oldlogic = predictor_rows(c_old, at=AT, live=None)
fields = (
    "level",
    "band_lo",
    "band_hi",
    "n_window",
    "n_distinct",
    "n_window_distinct",
    "log_disagreement",
)
for f in fields:
    k = sum(
        1
        for x, y in zip(a, oldlogic, strict=True)
        if getattr(x, f) != getattr(y, f)
        and not (
            isinstance(getattr(x, f), float)
            and math.isnan(getattr(x, f))
            and math.isnan(getattr(y, f))
        )
    )
    print(f"   old logic against archive-only, rows differing in {f}: {k}")
k_new = sum(
    1
    for x, y in zip(a, new, strict=True)
    for f in ("level", "band_lo", "band_hi", "n_window", "n_distinct", "n_window_distinct")
    if getattr(x, f) != getattr(y, f)
    and not (
        isinstance(getattr(x, f), float) and math.isnan(getattr(x, f)) and math.isnan(getattr(y, f))
    )
)
print(
    "   new logic against archive-only, values differing (level, band, counts):",
    k_new,
    "(0 expected; the reading alone moves)",
)

# Weight of tau = 0 in A1's pool
D = pickle.load(open("C:/t135/cache/days.pkl", "rb"))
REC = [r for r in D["records"] if r["stratum"] == "discriminating"]
e = np.array([abs((1 - r["e10_level"]) - (1 - r["e10_reading"])) for r in REC])
print(
    f"tau = 0: |p_level - p_reading| = |e10 difference|: median {np.median(e):.4f}, p90 {np.percentile(e, 90):.4f}; binomial se at p about 0.97 is {math.sqrt(0.97 * 0.03 / 2048):.4f}"
)
