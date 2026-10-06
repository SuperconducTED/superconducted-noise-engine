# ruff: noqa: B905
"""Compare the owner's results JSONs before and after a re-run (values only, no timestamps)."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

ROOT = Path(__file__).resolve().parents[3]
NEW = ROOT / "results" / "gates_2q"
OLD = Path("C:/t/vg2q_old")
SKIP = {"measured_utc"}


def walk(a, b, path, diffs, counter):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in SKIP:
                continue
            if k not in a or k not in b:
                diffs.append((path + "/" + str(k), "missing", None))
                continue
            walk(a[k], b[k], path + "/" + str(k), diffs, counter)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((path, "len", (len(a), len(b))))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, path + "[" + str(i) + "]", diffs, counter)
    else:
        counter[0] += 1
        same = a == b
        if (
            not same
            and isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and not isinstance(a, bool)
        ):
            same = math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        if not same:
            diffs.append((path, a, b))


def main():
    out = {"header": ddload.result_header("verify/gates_2q", "compare_reruns.py")}
    files = {}
    for f in sorted(NEW.glob("*.json")):
        old = json.loads((OLD / f.name).read_text(encoding="utf-8"))
        new = json.loads(f.read_text(encoding="utf-8"))
        diffs, counter = [], [0]
        walk(old, new, "", diffs, counter)
        files[f.name] = {
            "leaves_compared": counter[0],
            "n_diffs": len(diffs),
            "first_diffs": [list(map(str, d)) for d in diffs[:10]],
        }
    out["files"] = files
    print(json.dumps(files, indent=1))
    ddload.write_json(ROOT / "results" / "verify" / "gates_2q" / "compare_reruns.json", out)


if __name__ == "__main__":
    main()
