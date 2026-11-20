#!/usr/bin/env bash
# Full test suite at the tree's commit with each arithmetic option patched into the two
# defuzzifiers (defuzz_variant_plugin.py, same folder). Git Bash, pinned interpreter.
#
#   bash <this folder>/defuzz_suite_by_variant.sh <tree>
#
# Writes defuzz_suite_<variant>.out.txt next to this script. No -I here: the plugin
# and src/ come in through PYTHONPATH, and the plugin prints the imported package's __file__.
set -u
TREE="$(cd "${1:?usage: defuzz_suite_by_variant.sh <tree>}" && pwd -W)"
HERE="$(cd "$(dirname "$0")" && pwd -W)"
PY=C:/pvci/Scripts/python.exe
echo "tree <arg> at $(git -C "$TREE" rev-parse --short HEAD)"
for v in shipped A B C D X12 X6; do
  (
    cd "$TREE" &&
    DEFUZZ_VARIANT="$v" PYTHONPATH="$TREE/src;$HERE" "$PY" -m pytest tests -q \
      -o addopts="" -p no:cacheprovider -p defuzz_variant_plugin \
      > "$HERE/defuzz_suite_$v.out.txt" 2>&1
    echo "variant $v exit $?" >> "$HERE/defuzz_suite_$v.out.txt"
  ) &
done
wait
for v in shipped A B C D X12 X6; do
  printf '%-8s ' "$v"; grep -E "^[0-9]+ (passed|failed)|passed|failed" "$HERE/defuzz_suite_$v.out.txt" | tail -1
  grep -E "patched calls|^variant" "$HERE/defuzz_suite_$v.out.txt" | tr '\n' ' '; echo
done
