#!/usr/bin/env bash
# Regenerate the phase-3 dashboard, commit if anything moved, push.
#
# This is what the daily routine runs. It is deliberately boring and it is safe
# to run by hand at any time: it only ever touches the orphan `phase-3-dashboard`
# branch, never `main` and never the project's source tree.
#
# Exit codes: 0 = regenerated (whether or not anything changed), 1 = generation
# failed and nothing was committed. A failed generation never commits a partial
# dashboard, because a stale dashboard that looks current is worse than a
# missing one.
set -euo pipefail

cd "$(dirname "$0")"

# The Store-stub `python` on PATH is not reliable on this machine; prefer the
# real 3.12 install and fall back only if it is absent.
PY="/c/Users/senso/AppData/Local/Programs/Python/Python312/python.exe"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "phase-3-dashboard" ]; then
  echo "refusing to run: expected branch phase-3-dashboard, found $branch" >&2
  exit 1
fi

echo "==> regenerating"
"$PY" generate.py

if git diff --quiet -- index.html STATUS.md snapshot.json; then
  echo "==> no change since the last run"
  exit 0
fi

# Show what actually moved, so a routine's log is readable without opening the diff.
echo "==> changes"
git --no-pager diff --stat -- index.html STATUS.md snapshot.json

git add index.html STATUS.md snapshot.json plan.json
GIT_AUTHOR_NAME="Mert Efe Şensoy" \
GIT_AUTHOR_EMAIL="sensoymertefe@gmail.com" \
GIT_COMMITTER_NAME="Mert Efe Şensoy" \
GIT_COMMITTER_EMAIL="sensoymertefe@gmail.com" \
  git commit -q -m "chore: refresh phase-3 dashboard ($(date -u +%Y-%m-%d))"

echo "==> pushing"
git push -q superconducted-noise-engine phase-3-dashboard
echo "==> done"
