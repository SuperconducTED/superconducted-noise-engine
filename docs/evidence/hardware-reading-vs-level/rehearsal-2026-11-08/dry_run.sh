#!/usr/bin/env bash
# Criterion 10 of the amendment 20 plan: the dry run's outputs stay identical to dry-run-2026-11-05/.
# On Aer, from the full clone; spends nothing on the QPU.
#
#   bash dry_run.sh <commit> <output folder> <full clone> <python> [fetch source]
#
# The command is the one docs/implementations/2026-10-28-hardware-test-offline-half.md records, with
# the reference's controls.json taken from the commit's blob, so a checkout's line endings cannot
# change its hash. compare_dry_run.py decides (exit 0 when its MUST MATCH tier holds); every file is
# then also compared byte for byte, line endings normalised. Writes a status line per stage.

set -u
COMMIT=$1
OUT=$2
CLONE=$3
PY=$4
SOURCE=${5:-origin}
REF=docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05
SEP=$("$PY" -c "import os; print(os.pathsep)")
export PYTHONPATH=".${SEP}src" PYTHONIOENCODING=utf-8

mkdir -p "$OUT"
status() { echo "$(date -u +%H:%M:%S) $*" >> "$OUT.status.txt"; }

cd "$CLONE" || exit 1
git fetch -q "$SOURCE" mert/issue-125-submission || exit 1
git checkout -q --detach "$COMMIT" || exit 1
status "at $(git rev-parse HEAD), tree: [$(git status --porcelain | wc -l)] changed"
git show "HEAD:$REF/controls.json" > "$OUT/controls.json"
status "dry run start"
"$PY" -m scripts.hardware_reading_vs_level --repo . \
    --ref 5828b4a29fabc245aa096e530852249a3496dc5b --at 2026-10-23T09:34:56Z \
    --execution-ref 84ba0230738c9ee2773616b4e4c7142ba91180e3 \
    --controls "$OUT/controls.json" --out "$OUT" > "$OUT.log" 2>&1
status "dry run exit $?"
"$PY" docs/evidence/hardware-reading-vs-level/compare_dry_run.py "$REF" "$OUT" > "$OUT.compare.txt" 2>&1
status "compare_dry_run exit $?"
for f in $(git ls-tree --name-only "HEAD:$REF"); do
    if cmp -s <(git show "HEAD:$REF/$f" | tr -d '\r') <(tr -d '\r' < "$OUT/$f"); then
        echo "identical $f"
    else
        echo "DIFFERS   $f"
    fi
done >> "$OUT.compare.txt"
status "byte comparison: $(grep -c '^identical' "$OUT.compare.txt") identical, $(grep -c '^DIFFERS' "$OUT.compare.txt") differ"
status "tree after the run: [$(git status --porcelain | wc -l)] changed"
status "RUN END"
