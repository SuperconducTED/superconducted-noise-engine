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

# Leave a trace on disk before doing anything, and record the outcome on the way
# out however the script exits. Without this a failed scheduled run leaves no
# evidence at all: no commit, no push, nothing to inspect afterwards, so "did it
# run and fail" and "did it never run" look identical from here. A failure line
# stays local until the next successful run commits it, which is fine; the point
# is that it exists to be read.
LOG="run.log"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
outcome="started"
log_exit() {
  local code=$?
  [ "$outcome" = "started" ] && outcome="FAILED (exit $code)"
  printf '%s  %s\n' "$started" "$outcome" >> "$LOG"
  return $code
}
trap log_exit EXIT
printf '%s  --- run begins (pid %s) ---\n' "$started" "$$" >> "$LOG"

# The Store-stub `python` on PATH is not reliable on this machine; prefer the
# real 3.12 install and fall back only if it is absent.
PY="/c/Users/senso/AppData/Local/Programs/Python/Python312/python.exe"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "phase-3-dashboard" ]; then
  echo "refusing to run: expected branch phase-3-dashboard, found $branch" >&2
  outcome="refused: on branch $branch"
  exit 1
fi

echo "==> regenerating"
"$PY" generate.py

# A brand-new day's record is untracked rather than modified, and git diff does
# not see untracked files at all, so both questions have to be asked.
if git diff --quiet -- index.html STATUS.md snapshot.json plan.json README.md history/ &&
   [ -z "$(git ls-files --others --exclude-standard history/)" ]; then
  echo "==> byte-identical to the last run, nothing to commit"
  outcome="ok: byte-identical, no commit"
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
files="index.html STATUS.md snapshot.json plan.json README.md $(ls history/*.json 2>/dev/null)"
for f in $files; do
  git show "HEAD:$f" 2>/dev/null | strip_stamps > /tmp/.p3-old.$$ || : > /tmp/.p3-old.$$
  strip_stamps < "$f" > /tmp/.p3-new.$$
  if ! cmp -s /tmp/.p3-old.$$ /tmp/.p3-new.$$; then substantive=1; fi
done
rm -f /tmp/.p3-old.$$ /tmp/.p3-new.$$

echo "==> changes"
git --no-pager diff --stat -- index.html STATUS.md snapshot.json plan.json README.md history/
git ls-files --others --exclude-standard history/ | sed "s/^/ new  /"

if [ "$substantive" -eq 1 ]; then
  subject="chore: phase-3 dashboard: state moved ($(date -u +%Y-%m-%d))"
else
  subject="chore: phase-3 dashboard: no change ($(date -u +%Y-%m-%d))"
fi

git add index.html STATUS.md snapshot.json plan.json README.md history/ run.log
GIT_AUTHOR_NAME="Mert Efe Şensoy" \
GIT_AUTHOR_EMAIL="sensoymertefe@gmail.com" \
GIT_COMMITTER_NAME="Mert Efe Şensoy" \
GIT_COMMITTER_EMAIL="sensoymertefe@gmail.com" \
  git commit -q -m "$subject"

echo "==> pushing"
git push -q superconducted-noise-engine phase-3-dashboard
outcome="ok: $subject"
echo "==> done: $subject"
