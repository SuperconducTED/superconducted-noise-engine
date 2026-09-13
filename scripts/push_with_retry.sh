#!/usr/bin/env bash
# Push HEAD to a data branch, replaying over a concurrent update.
#
# The poll workflow (hourly, `calibration-poll`) and the health workflow (daily,
# `calibration-health`) both commit to calibration-data from SEPARATE
# concurrency groups. Separate groups are deliberate -- a shared one lets a
# health render cancel a queued poll, and a cancelled poll writes no ledger row,
# which is invisible in exactly the instrument this pipeline exists to provide.
# The cost of that choice is that the two pushes can race, and a plain
# `git push` loses the race as a non-fast-forward rejection that fails the job.
#
# Replay rather than merge: each workflow commits to a tree only it writes
# (`health/metrics.json` and `health/progress.svg` for the renderer;
# `snapshots/`, `ledger/`, `collisions/` and `health/state-index.tsv` for the
# poller), so a textual conflict means something unmodelled happened and the run
# must fail loudly rather than guess.
#
# Works on the shallow checkouts both workflows use: the replayed commit and its
# parent are both local, which is all `cherry-pick` needs.
#
# Usage: push_with_retry.sh <remote> <branch> [attempts]
set -euo pipefail

remote=${1:?remote is required}
branch=${2:?branch is required}
attempts=${3:-3}

for attempt in $(seq 1 "$attempts"); do
  if git push "$remote" "HEAD:$branch"; then
    exit 0
  fi
  if [ "$attempt" -eq "$attempts" ]; then
    break
  fi
  echo "::warning::push to $branch rejected (attempt $attempt/$attempts); replaying onto the new tip"
  replay=$(git rev-parse HEAD)
  git fetch --depth=1 "$remote" "$branch"
  git reset --hard FETCH_HEAD
  if ! git cherry-pick "$replay"; then
    git cherry-pick --abort || true
    echo "::error::replaying $replay onto $branch conflicted; refusing to guess"
    exit 1
  fi
done

echo "::error::could not push to $branch after $attempts attempts"
exit 1
