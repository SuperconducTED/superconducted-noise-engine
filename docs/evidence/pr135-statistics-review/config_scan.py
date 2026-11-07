"""How often is an archived ibm_fez snapshot's configuration null, and on which days would a job meet one?

Reads every ibm_fez file at the pinned ref through one git cat-file --batch, without lazy fetch.
Writes C:/t135/cache/config_scan.pkl: path -> whether configuration is a dict.
"""

import json
import os
import pickle
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

REPO, REF = sys.argv[1], sys.argv[2]
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
proc = subprocess.Popen(
    ["git", "-C", REPO, "cat-file", "--batch"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    env=env,
)
scan = {}
schema = Counter()
for p in paths:
    proc.stdin.write(f"{REF}:{p}\n".encode())
    proc.stdin.flush()
    head = proc.stdout.readline().split()
    body = proc.stdout.read(int(head[2]))
    proc.stdout.read(1)
    d = json.loads(body)
    has = isinstance(d.get("configuration"), dict)
    scan[p] = has
    schema[(d.get("schema_version"), has)] += 1
proc.stdin.close()
proc.wait()
pickle.dump(scan, open("C:/t135/cache/config_scan.pkl", "wb"))
print(
    "files",
    len(scan),
    "configuration a dict",
    sum(scan.values()),
    "null",
    len(scan) - sum(scan.values()),
)
print("by (schema_version, has configuration):", dict(schema))
by_month = Counter()
for p, h in scan.items():
    by_month[(p.split("/")[1], h)] += 1
for k in sorted(by_month):
    print(k, by_month[k])
first_null = next((p for p in paths if not scan[p]), None)
print("first null:", first_null)
t = datetime(2026, 6, 13, 3, 45, tzinfo=UTC)
stamp = lambda p: datetime.strptime(p.rsplit("/", 1)[1][:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
times = [(stamp(p), p) for p in paths]
n, nn = 0, 0
nulldays = []
while t <= datetime(2026, 10, 28, 3, 45, tzinfo=UTC):
    latest = [p for ts, p in times if ts <= t][-1]
    n += 1
    if not scan[latest]:
        nn += 1
        nulldays.append(t.date().isoformat())
    t += timedelta(days=1)
print(f"days at 03:45 UTC whose latest file has configuration null: {nn} of {n}")
print("first and last such:", nulldays[:1], nulldays[-1:])
win = [
    sum(1 for d in nulldays if d >= (datetime(2026, 10, 28) - timedelta(days=k)).date().isoformat())
    for k in (14, 30, 60)
]
print("of the last 14, 30, 60 days:", win)
