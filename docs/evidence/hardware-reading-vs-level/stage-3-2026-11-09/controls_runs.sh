#!/usr/bin/env bash
# Criterion 35 of the stage 3 plan (amendment 37's last clause): which controls the control test
# at the freeze changes, if any. Runs --mode controls with the code before the test (e639cf86) and
# with it (NEW), at the same --ref and --at, at two instants: the section 3.9 rehearsal's
# (calibration-data 7adda803, 2026-10-28T18:40:46Z) and the archive tip read on 2026-11-09. The
# predictions are in the stage 3 plan, committed (59ba1fd0) before this script ran.
#
#   bash controls_runs.sh <NEW commit> <out folder> <full clone> <python> <code source repo>
#
# The code runs from plain copies (git archive), so nothing is checked out in the full clone,
# which only supplies the archive's objects. Spends nothing on the QPU and reads no result.

set -u
NEW=$1
OUT=$2
CLONE=$3
PY=$4
CODE=$5
OLD=e639cf86b71dbefc3ee86a02a8945090ae35fa5e
SEP=$("$PY" -c "import os; print(os.pathsep)")
export PYTHONPATH=".${SEP}src" PYTHONIOENCODING=utf-8

mkdir -p "$OUT"
status() { echo "$(date -u +%H:%M:%S) $*" >> "$OUT/status.txt"; }

for which in old new; do
    commit=$OLD
    [ "$which" = new ] && commit=$NEW
    rm -rf "$OUT/code-$which"
    mkdir -p "$OUT/code-$which"
    git -C "$CODE" archive "$commit" scripts src | tar -x -C "$OUT/code-$which"
    status "code-$which from $(git -C "$CODE" rev-parse "$commit")"
done

run() {  # <label> <ref> <at>
    for which in old new; do
        status "$1 $which start (ref $2, at $3)"
        (cd "$OUT/code-$which" && "$PY" -m scripts.hardware_test_predictors --repo "$CLONE" \
            --ref "$2" --at "$3" --mode controls --out "$OUT/$1-$which" \
            > "$OUT/$1-$which.log" 2>&1)
        status "$1 $which exit $?"
    done
    "$PY" - "$OUT/$1-old/controls.json" "$OUT/$1-new/controls.json" > "$OUT/$1.compare.txt" <<'EOF'
import json, sys
old, new = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
q = lambda doc: [c["qubit"] for c in doc["controls"]]
print("old controls:", q(old))
print("new controls:", q(new))
print("controls identical (qubits and every field):", old["controls"] == new["controls"])
print("other keys identical:", {k: v for k, v in old.items() if k != "controls"}
      == {k: v for k, v in new.items() if k not in ("controls", "not_operational_at_freeze")})
print("not_operational_at_freeze:", json.dumps(new.get("not_operational_at_freeze")))
EOF
    status "$1 compared"
}

run rehearsal-2026-10-28 7adda803 2026-10-28T18:40:46Z
run tip-2026-11-09 60d082b0ea5f7b6678aec796357f7b7fcb99794e 2026-11-09T12:11:46Z
status "RUN END"
