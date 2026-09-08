#!/usr/bin/env bash
# Print the report from the most recent run, or refuse to print anything.
#
# This is the only thing entitled to describe the state of phase 3. The daily
# routine runs update.sh and then relays this script's output verbatim; it
# composes no summary of its own. That division exists because the alternative
# was tried and failed: told to "run the refresh, then report", a routine can
# skip the refresh, read the leftover STATUS.md, and produce a summary that
# looks completely normal while describing a moment that has passed. It did
# exactly that twice on 2026-09-08. An instruction not to could not prevent it;
# this can, because there is simply nothing fresh to print.
#
# Two things make that work. update.sh deletes last_run.md before it does
# anything and only writes it on the way out, so a run that never happened
# leaves no report. And every report carries the token of the run that produced
# it, which this script checks against the clock.
#
# Usage: report.sh [max-age-seconds]   (default 900, i.e. 15 minutes)
# Exit codes: 0 = a fresh report was printed, 1 = nothing fresh to print. In
# both cases what lands on stdout is safe to relay word for word.
set -uo pipefail

cd "$(dirname "$0")"
MAX_AGE="${1:-900}"

if [ ! -f last_run.md ]; then
  cat <<'EOF'
NO REPORT AVAILABLE.

update.sh has not run to completion in this working tree, so there is no report
to give. Nothing was committed and the dashboard was not refreshed.

Do not describe the state of phase 3 from any other file. STATUS.md, index.html,
README.md and history/ are all left over from an earlier run and describe a
moment that has passed. Report this message instead, along with the output of
the update.sh command that was attempted.
EOF
  exit 1
fi

token="$(sed -n 's/^run-token: //p' last_run.md | head -1)"
if [ -z "$token" ]; then
  echo "NO REPORT AVAILABLE: last_run.md carries no run token, so it cannot be"
  echo "attributed to a run. Treat it as stale and report this message instead."
  exit 1
fi

# The token's leading field is the run's start time in UTC.
stamp="${token%-*}"
if ! then_s="$(date -d "$stamp" +%s 2>/dev/null)"; then
  echo "NO REPORT AVAILABLE: run token '$token' is unparseable, so freshness"
  echo "cannot be established. Treat it as stale and report this message instead."
  exit 1
fi

now_s="$(date -u +%s)"
age=$(( now_s - then_s ))

if [ "$age" -gt "$MAX_AGE" ]; then
  cat <<EOF
STALE REPORT, NOT USABLE.

The most recent report was produced at $stamp, which is $(( age / 60 )) minutes
ago; anything older than $(( MAX_AGE / 60 )) minutes is treated as stale. That
means update.sh did not run just now, whatever else may have appeared to happen.

Do not relay any status numbers, and do not reconstruct them from STATUS.md,
index.html, README.md or history/. Report this message instead, along with the
output of the update.sh command that was attempted.
EOF
  exit 1
fi

# Fresh, but freshness is not success: a run that failed writes a report saying
# so, and that report is as fresh as any other. The outcome line decides the
# exit code, so a caller checking $? sees the difference between "here is the
# state of phase 3" and "the refresh broke". The content is printed either way,
# because in both cases it is the correct thing to relay.
outcome="$(sed -n 's/^outcome: //p' last_run.md | head -1)"

echo "Phase 3 refresh, ${age}s ago."
echo
cat last_run.md

case "$outcome" in
  ok:*) exit 0 ;;
  *)    exit 1 ;;
esac
