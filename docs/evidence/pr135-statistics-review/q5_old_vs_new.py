"""Amendment 14's claim, run directly: old and new predictor_rows on the same cached records, no live document.

Old code is scripts/hardware_test_predictors.py at d62928fa; new is at 5c98f264. Both consume FileRecord lists,
so the old module gets a Collected built from the same records (skipped is empty at this ref, so _record's new
shape check rejected nothing, which is the only other archive-path change).
"""

import importlib.util
import math
import pickle
import sys
from datetime import UTC, datetime

sys.path.insert(0, "C:/t135/new")
import scripts.hardware_test_predictors as new

spec = importlib.util.spec_from_file_location(
    "pred_old", "C:/t135/old/scripts/hardware_test_predictors.py"
)
old = importlib.util.module_from_spec(spec)
sys.modules["pred_old"] = old
spec.loader.exec_module(old)

c = pickle.load(open("C:/t135/cache/collected.pkl", "rb"))
print("skipped at this ref:", dict(c.skipped), "files", len(c.files), "states", len(c.states))
conv = lambda rs: [old.FileRecord(r.path, r.time, r.digest, r.values) for r in rs]
c_old = old.Collected(files=conv(c.files), states=conv(c.states), skipped=c.skipped)
fields = [
    "qubit",
    "quantity",
    "reading",
    "level",
    "band_lo",
    "band_hi",
    "n_window",
    "n_distinct",
    "log_disagreement",
    "reading_time",
]
for at in (
    datetime(2026, 10, 28, 18, 40, 46, tzinfo=UTC),
    datetime(2026, 8, 15, 3, 45, tzinfo=UTC),
):
    a = old.predictor_rows(c_old, at=at, live=None)
    b = new.predictor_rows(c, at=at, live=None)
    assert len(a) == len(b)
    diffs = 0
    for x, y in zip(a, b, strict=True):
        for f in fields:
            u, v = getattr(x, f), getattr(y, f)
            if u != v and not (isinstance(u, float) and math.isnan(u) and math.isnan(v)):
                diffs += 1
    print(f"{at.isoformat()}: {len(a)} rows, {len(fields)} shared columns, differing cells {diffs}")
print("old columns:", list(old.PredictorRow.__dataclass_fields__))
print("new columns:", list(new.PredictorRow.__dataclass_fields__))
# Mutation: a value changed in one record must show up.
recs = conv(c.files)
# A copy: FileRecord holds a reference, and doubling in place would change both sides and hide the mutation.
last = recs[-1]
mutated = last.values.copy()
mutated[0, 0] = mutated[0, 0] * 2.0
recs[-1] = old.FileRecord(last.path, last.time, last.digest, mutated)
m = old.Collected(files=recs, states=conv(c.states), skipped=c.skipped)
at = datetime(2026, 10, 28, 18, 40, 46, tzinfo=UTC)
a = old.predictor_rows(m, at=at, live=None)
b = new.predictor_rows(c, at=at, live=None)
print(
    "mutation (one reading doubled): differing reading cells",
    sum(
        1
        for x, y in zip(a, b, strict=True)
        if x.reading != y.reading and not (math.isnan(x.reading) and math.isnan(y.reading))
    ),
)
