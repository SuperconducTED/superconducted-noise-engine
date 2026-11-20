#!/usr/bin/env bash
# Re-run the archive-timing evidence at its pinned calibration-data commit.
#
#   bash run.sh <repo> <python> [<out dir>]
#
# <repo>   a clone holding the pinned commit and its history back to 2026-09-01
# <python> an interpreter with the repository's pins (compare_readings.py needs NumPy and the
#          package; archive_timing.py needs only the standard library)
# <out>    where the three outputs go; defaults to this folder, which overwrites the committed ones
#
# The outputs are written with LF line endings whatever the platform.
set -euo pipefail

REPO="$1"
PY="$2"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${3:-$HERE}"
DATA=5d958ab2af09a3c8ed8c7222ef823130fe6229f6

mkdir -p "$OUT"
git -C "$REPO" cat-file -e "$DATA^{commit}"

PYTHONIOENCODING=utf-8 "$PY" "$HERE/archive_timing.py" "$REPO" "$DATA" --pairs-out "$OUT/pairs.tsv" \
    | tr -d '\r' > "$OUT/archive_timing.out.txt"
PYTHONIOENCODING=utf-8 PYTHONPATH="$REPO/src" "$PY" "$HERE/compare_readings.py" "$REPO" "$DATA" "$OUT/pairs.tsv" \
    | tr -d '\r' > "$OUT/compare_readings.out.txt"

tail -n 1 "$OUT/archive_timing.out.txt"
tail -n 1 "$OUT/compare_readings.out.txt"
