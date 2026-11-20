#!/usr/bin/env bash
# Criteria 2, 3 and 4 of the 1d plan, on Aer, from the full clone. Spends nothing on the QPU.
#
#   bash rehearse_1d.sh <commit> <output root> <full clone> <python> <T1 python> [fetch source]
#
# <full clone> has the calibration-data branch fetched. <python> holds the project's exact pins and
# <T1 python> those pins plus qiskit-experiments==0.14.2. The fetch source defaults to origin.
#
# Criterion 2: build at the dry run's own instant and archive commit.
# Criteria 3 and 4: the morning routine on three consecutive days, the middle one absent. Each day's
# "live" document is the first configured archived file whose T1 values differ from those current at
# its 03:45 capture, so the live path sees a genuinely new state. Writes a status line per stage,
# because a hung stage looks like a working one.

set -u
COMMIT=$1
OUT=$2
CLONE=$3
PY=$4
T1PY=$5
SOURCE=${6:-origin}
EVIDENCE=docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05
DRY_REF=5828b4a29fabc245aa096e530852249a3496dc5b
DRY_FILE=snapshots/2026-10/ibm_fez/20261023T093456000000Z.json
TIP=b9279b99
SEP=$("$PY" -c "import os; print(os.pathsep)")
export PYTHONPATH=".${SEP}src" PYTHONIOENCODING=utf-8

mkdir -p "$OUT"
status() { echo "$(date -u +%H:%M:%S) $*" >> "$OUT/status.txt"; }

cd "$CLONE" || exit 1
git fetch -q "$SOURCE" mert/issue-125-submission || exit 1
git checkout -q --detach "$COMMIT" || exit 1
status "at $(git rev-parse HEAD), tree: [$(git status --porcelain | wc -l)] changed"

# --- criterion 2 ---------------------------------------------------------------------------------
git show "$DRY_REF:$DRY_FILE" > "$OUT/live-c2.json"
status "criterion 2 build start"
"$PY" scripts/hardware_submit.py build \
    --jobs-dir "$OUT/c2" --controls "$EVIDENCE/controls.json" --job-number 2 \
    --ref "$DRY_REF" --repo . --at 2026-10-23T09:34:56+00:00 \
    --local-live "$OUT/live-c2.json" --local-execute-at 2026-10-23T11:34:56+00:00 \
    > "$OUT/c2.log" 2>&1
status "criterion 2 build exit $?"

# --- criteria 3 and 4 ----------------------------------------------------------------------------
"$PY" - "$TIP" "$OUT" <<'PICK'
import datetime as dt, json, subprocess, sys
tip, out = sys.argv[1:]
def load(name):
    raw = subprocess.run(["git", "show", f"{tip}:{name}"], check=True, capture_output=True).stdout
    return json.loads(raw)
def t1s(doc):
    return [[e["value"] for e in entries if e["name"] == "T1"] for entries in doc["properties"]["qubits"]]
names = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", tip, "snapshots/"],
    check=True, capture_output=True, text=True,
).stdout.split()
stamps = sorted(
    (dt.datetime.strptime(n.rsplit("/", 1)[1][:15], "%Y%m%dT%H%M%S").replace(tzinfo=dt.UTC), n)
    for n in names if "/ibm_fez/" in n
)
last = stamps[-1][0].date()
first = last - dt.timedelta(days=3)
with open(f"{out}/days.txt", "w", encoding="utf-8", newline="\n") as handle:
    for offset in (0, 2):
        day = first + dt.timedelta(days=offset)
        t_s = dt.datetime.combine(day, dt.time(3, 45), dt.UTC)
        # The first configured file whose T1 values differ from everything current at t_s: a repeat
        # of the newest archived state would add nothing and leave the live path untested.
        before = t1s(load([n for t, n in stamps if t <= t_s][-1]))
        live = None
        for t, n in stamps:
            if t <= t_s:
                continue
            assert t <= t_s + dt.timedelta(hours=30), f"no new state within 30 h of {t_s}"
            doc = load(n)
            if doc.get("configuration") is not None and t1s(doc) != before:
                live = n
                break
        handle.write(f"{offset + 1} {t_s.isoformat()} {live}\n")
    handle.write(f"first {first.isoformat()}\n")
PICK
FIRST=$(grep '^first ' "$OUT/days.txt" | cut -d' ' -f2)
status "rehearsal days from $FIRST: $(grep -v '^first' "$OUT/days.txt" | tr '\n' ';')"

grep -v '^first' "$OUT/days.txt" | while read -r NUMBER T_S LIVE; do
    git show "$TIP:$LIVE" > "$OUT/live-$NUMBER.json"
    EXECUTE=$("$PY" -c "import datetime as d,sys; print((d.datetime.fromisoformat(sys.argv[1])+d.timedelta(hours=2)).isoformat())" "$T_S")
    status "morning of day $NUMBER start"
    "$PY" scripts/hardware_daily.py \
        --first-day "$FIRST" --jobs-dir "$OUT/jobs" --controls "$EVIDENCE/controls.json" \
        --repo . --t1-python "$T1PY" --ref "$TIP" --at "$T_S" \
        --local-live "$OUT/live-$NUMBER.json" --local-execute-at "$EXECUTE" \
        >> "$OUT/morning-$NUMBER.log" 2>&1
    status "morning of day $NUMBER exit $?"
done

# The last day is scored by hand the morning after, because no routine follows it here.
THIRD=$(grep '^3 ' "$OUT/days.txt" | cut -d' ' -f2)
NEXT=$("$PY" -c "import datetime as d,sys; print((d.datetime.fromisoformat(sys.argv[1])+d.timedelta(days=1)).isoformat())" "$THIRD")
EXECUTE=$("$PY" -c "import datetime as d,sys; print((d.datetime.fromisoformat(sys.argv[1])+d.timedelta(hours=2)).isoformat())" "$THIRD")
DAY3=$(echo "$THIRD" | cut -c1-10)
status "score day 3 start"
"$PY" scripts/hardware_submit.py score --job-dir "$OUT/jobs/$DAY3" --repo . --ref "$TIP" --at "$NEXT" \
    --local-live "$OUT/live-3.json" --local-execute-at "$EXECUTE" > "$OUT/score-3.log" 2>&1
status "score day 3 exit $?"
"$PY" scripts/hardware_submit.py report --jobs-dir "$OUT/jobs" --first-day "$FIRST" --today "$DAY3" \
    > "$OUT/report.log" 2>&1
status "report exit $?"
status "tree after the run: [$(git status --porcelain | wc -l)] changed"
status "RUN END"
