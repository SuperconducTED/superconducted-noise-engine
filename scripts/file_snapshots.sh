#!/usr/bin/env bash
# File freshly polled calibration snapshots onto the calibration-data branch.
#
# Called by .github/workflows/calibration-poll.yml from the SOURCE checkout,
# whose branch it never switches. The data branch is checked out into a
# separate worktree instead, so scripts/ -- including
# canonical_snapshot_digest.py, which this script runs -- stays on disk for the
# whole run. The previous in-place `git checkout -B calibration-data` removed
# scripts/ mid-step: the digest call exited 2 (file not found) and every
# genuine duplicate would have been recorded as `collision-unreadable`
# (PR #50 review, blocker). tests/test_file_snapshots.py runs this script
# end to end, real branch switch included, and asserts the ledger it writes.
#
# Two rules this script must not break, both learned the hard way:
#  - the destination month comes from the payload-derived FILENAME, never from
#    the run clock. The two disagree either side of a month boundary and
#    misfiled two June payloads under 2026-07 (#45 s4a).
#  - an already-archived path is NEVER overwritten. The filename is the
#    backend's own last_update_date, so a collision means IBM has not
#    republished; overwriting is what silently discarded five gate-level
#    versions (#46 s3c).
#
# Environment:
#   STAGING_DIR    directory holding $BACKEND/*.json payloads         (required)
#   DATA_WORKTREE  path at which to check the data branch out; must
#                  not exist yet                                       (required)
#   BACKEND        backend name                                        (default ibm_fez)
#   DATA_REMOTE    remote that owns the data branch                    (default origin)
#   DATA_BRANCH    the data branch                                     (default calibration-data)
#   POLL_TIME      ISO-8601 UTC instant of this poll                   (default now)
#   PYTHON         interpreter that runs the digest                    (default python)
#   IS_BACKFILL    "1" when this run swept a historical window; only then
#                  may a difference be explained as a lossy re-read  (default 0)
#
# Decisions (`new`, `duplicate`, `duplicate-partial`, `collision`,
# `collision-unreadable`) are ADR-025's vocabulary; each is appended to
# ledger/<poll month>.tsv and the result is pushed. Exits non-zero if the
# digest is missing or git fails.
set -euo pipefail
shopt -s nullglob

: "${STAGING_DIR:?STAGING_DIR is required}"
: "${DATA_WORKTREE:?DATA_WORKTREE is required}"
BACKEND=${BACKEND:-ibm_fez}
DATA_REMOTE=${DATA_REMOTE:-origin}
DATA_BRANCH=${DATA_BRANCH:-calibration-data}
POLL_TIME=${POLL_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}
PYTHON=${PYTHON:-python}
IS_BACKFILL=${IS_BACKFILL:-0}

# Both paths are resolved BEFORE the directory change below, and the digest is
# located by this script's own position rather than by the working directory,
# so neither depends on where the caller stands.
STAGING_DIR=$(cd "$STAGING_DIR" && pwd)
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
digest="$here/canonical_snapshot_digest.py"
if [ ! -f "$digest" ]; then
  echo "::error::$digest is missing; refusing to file anything without a comparator"
  exit 1
fi

git fetch "$DATA_REMOTE" "$DATA_BRANCH"
# -B resets the local branch to the remote tip, exactly as the old in-place
# checkout did -- but in its own directory, leaving this checkout untouched.
git worktree add -B "$DATA_BRANCH" "$DATA_WORKTREE" "$DATA_REMOTE/$DATA_BRANCH"
cd "$DATA_WORKTREE"

added=0

# The ledger is keyed by POLL time (unlike snapshots, which are keyed by
# payload time) because it records polling events, including the ones that
# observed nothing new. Without it a quiet stretch is indistinguishable from
# a stopped poller once the 90-day Actions run retention expires -- which is
# exactly what made #45 expensive.
ledger="ledger/${POLL_TIME:0:7}.tsv"
mkdir -p ledger collisions
if [ ! -e "$ledger" ]; then
  printf 'poll_time_utc\tbackend\tlast_update_date\tdecision\n' > "$ledger"
fi

for f in "$STAGING_DIR/$BACKEND"/*.json; do
  base=$(basename "$f")
  stem=${base%.json}
  dest="snapshots/${stem:0:4}-${stem:4:2}/$BACKEND"
  mkdir -p "$dest"
  if [ ! -e "$dest/$base" ]; then
    mv "$f" "$dest/"
    decision=new
    added=$((added + 1))
  else
    # A stamp collision does NOT prove the documents match -- #46 s3c lost
    # five gate-level versions under one stamp. But the comparison must be
    # CANONICAL, not bytewise: the archive predates the serialize_target
    # sort, so every pre-fix file holds target.operations unsorted and `cmp`
    # would call every duplicate a collision. See canonical_snapshot_digest.py.
    set +e
    "$PYTHON" "$digest" --compare "$f" "$dest/$base"
    same=$?
    set -e

    # Anything not canonically identical is preserved unless something
    # specific explains the difference. Default to the safe answer and let the
    # cases below narrow it.
    decision=collision
    if [ "$same" -eq 0 ]; then
      # Same document. IBM has not republished; a true no-op.
      decision=duplicate
    elif [ "$same" -eq 2 ]; then
      # Undecidable: one side could not be read or parsed. Never guess
      # `duplicate` -- that would drop data.
      decision=collision-unreadable
    elif [ "$IS_BACKFILL" = "1" ]; then
      # ONLY a backfill may explain a difference away, and only for a payload
      # carrying the structural signature of a lossy historical re-read: no
      # `configuration` of its own where the archived copy has one. A sweep
      # re-reads stamps we already hold (a query inside a gap is answered with
      # the document at the gap's opening) and `fetch_snapshot(historical_at=)`
      # never fetches `configuration`, so such a re-read is never byte-equal to
      # the live copy that archived it even when every measurement matches.
      #
      # Both guards are load-bearing. Comparing full-then-payload is NOT: full
      # equality implies payload equality, so that shape reduces to comparing
      # the payload alone and would discard a genuinely divergent live payload
      # whose `target` changed (PR #55 review, P1). Two live payloads both
      # carry a configuration, so they never reach this branch.
      set +e
      "$PYTHON" "$digest" --compare-reread "$f" "$dest/$base"
      reread=$?
      set -e
      if [ "$reread" -eq 0 ]; then
        decision=duplicate-partial
      fi
    fi

    if [ "$decision" = "collision" ] || [ "$decision" = "collision-unreadable" ]; then
      # Preserve: keep the archived copy AND the new payload beside it.
      sha=$(sha256sum "$f" | cut -c1-16)
      coll="collisions/${stem:0:4}-${stem:4:2}/$BACKEND"
      mkdir -p "$coll"
      mv "$f" "$coll/$stem.$sha.json"
      if [ "$decision" = "collision-unreadable" ]; then
        echo "::warning::$stem could not be compared with the archived copy; preserved at $coll/$stem.$sha.json"
      else
        echo "::warning::$stem differs from the archived copy under the same stamp; preserved at $coll/$stem.$sha.json"
      fi
    fi
  fi
  printf '%s\t%s\t%s\t%s\n' "$POLL_TIME" "$BACKEND" "$stem" "$decision" >> "$ledger"
  echo "$stem: $decision"
done

git add snapshots/ ledger/ collisions/
if git diff --cached --quiet; then
  echo '::warning::nothing staged - poller produced no payload'
elif [ "$added" -gt 0 ]; then
  git commit -m "calibration: $POLL_TIME $BACKEND (+$added)"
else
  git commit -m "poll: $POLL_TIME $BACKEND (no new document)"
fi
git push "$DATA_REMOTE" "$DATA_BRANCH"
