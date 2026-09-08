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

if git diff --quiet -- index.html STATUS.md snapshot.json plan.json; then
  echo "==> byte-identical to the last run, nothing to commit"
  exit 0
fi

# Every run stamps a fresh generated-at time, so "the files differ" is not the
# same question as "anything actually moved". Ask the second question by
# diffing with the timestamps filtered out. Both cases still get committed --
# a daily heartbeat is worth recording, because "checked, nothing moved" is
# real information about a phase with a deadline -- but the commit subject
# says which it was, so `git log --oneline` reads as a record of progress
# rather than a wall of identical refreshes.
strip_stamps() { sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} UTC/<stamp>/g'; }

substantive=0
for f in index.html STATUS.md snapshot.json plan.json; do
  git show "HEAD:$f" 2>/dev/null | strip_stamps > /tmp/.p3-old.$$ || : > /tmp/.p3-old.$$
  strip_stamps < "$f" > /tmp/.p3-new.$$
  if ! cmp -s /tmp/.p3-old.$$ /tmp/.p3-new.$$; then substantive=1; fi
done
rm -f /tmp/.p3-old.$$ /tmp/.p3-new.$$

echo "==> changes"
git --no-pager diff --stat -- index.html STATUS.md snapshot.json plan.json

if [ "$substantive" -eq 1 ]; then
  subject="chore: phase-3 dashboard — state moved ($(date -u +%Y-%m-%d))"
else
  subject="chore: phase-3 dashboard — no change ($(date -u +%Y-%m-%d))"
fi

git add index.html STATUS.md snapshot.json plan.json
GIT_AUTHOR_NAME="Mert Efe Şensoy" \
GIT_AUTHOR_EMAIL="sensoymertefe@gmail.com" \
GIT_COMMITTER_NAME="Mert Efe Şensoy" \
GIT_COMMITTER_EMAIL="sensoymertefe@gmail.com" \
  git commit -q -m "$subject"

echo "==> pushing"
git push -q superconducted-noise-engine phase-3-dashboard
echo "==> done: $subject"
