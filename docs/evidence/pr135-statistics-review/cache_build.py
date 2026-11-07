"""Build one pickled Collected from calibration-data at a pinned ref, read-only, without lazy fetch.
Same order and same invalid-JSON handling as training.dataset.iter_archive (path order, {} on bad JSON),
but through one `git cat-file --batch` instead of one `git show` per file."""

import json
import os
import pickle
import subprocess
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, "C:/t135/new")
from scripts.hardware_test_predictors import collect

REPO, REF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
paths = (
    subprocess.run(
        ["git", "-C", REPO, "ls-tree", "-r", "--name-only", REF, "--", "snapshots/"],
        check=True,
        capture_output=True,
        env=env,
    )
    .stdout.decode()
    .splitlines()
)
paths = sorted(p for p in paths if p.endswith(".json") and "/ibm_fez/" in p)
print("files", len(paths), flush=True)
proc = subprocess.Popen(
    ["git", "-C", REPO, "cat-file", "--batch"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    env=env,
)


def docs():
    for i, p in enumerate(paths):
        proc.stdin.write(f"{REF}:{p}\n".encode())
        proc.stdin.flush()
        head = proc.stdout.readline().split()
        if head[-1] == b"missing":
            raise SystemExit(f"missing blob {p}")
        size = int(head[2])
        body = proc.stdout.read(size)
        proc.stdout.read(1)
        if i % 400 == 0:
            print(i, p, round(time.time() - t0), flush=True)
        try:
            doc = json.loads(body)
        except (ValueError, UnicodeError):
            doc = {}
        yield p, doc if isinstance(doc, dict) else {}


t0 = time.time()
c = collect(docs(), backend="ibm_fez", until=datetime(2100, 1, 1, tzinfo=UTC))
proc.stdin.close()
proc.wait()
print(
    "files",
    len(c.files),
    "states",
    len(c.states),
    "skipped",
    dict(c.skipped),
    "secs",
    round(time.time() - t0),
)
with open(OUT, "wb") as fh:
    pickle.dump(c, fh, protocol=pickle.HIGHEST_PROTOCOL)
