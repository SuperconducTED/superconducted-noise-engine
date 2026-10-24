#!/usr/bin/env python3
"""Generate the status dashboard for the phase that ``plan.json`` describes.

Reads two things and joins them:

  1. ``plan.json``: the static, hand-curated model of the phase plan. Lanes, the
     ordered gates and their conditions, owners and co-owners, and every
     dependency edge, quoted from a ticket's own "Depends on" row or from the
     plan. This changes only when the plan, a ticket or an owner changes.
  2. Live GitHub state, via the ``gh`` CLI: issue open/closed and priority
     labels, PR review decision, mergeability, check-run conclusions, the ADR
     ledger on main, the milestones, the plan document's own history, and the
     conversations on every open issue and PR (for who owes an answer).

and writes ``index.html``, ``STATUS.md``, ``snapshot.json``, ``last_run.md``,
today's history record and the generated block of ``README.md``.

The point of the join is the derived column nobody maintains by hand: for every
ticket, whether its *upstream* dependencies are met and (separately) what
else is standing between it and closure once they are. Those are different
questions and the plan conflates them; this does not.

Contract
--------
inputs   : plan.json (beside this file), a working ``gh`` on PATH authenticated
           to the repo, network access to github.com.
outputs  : the files above, written beside this file. Idempotent: running twice
           with unchanged upstream state produces identical files except for
           the generated-at timestamp.
exit code: 0 on success, 1 if ``gh`` fails, plan.json is unreadable, or plan.json
           names an owner who is not on the team. It never writes a partial
           file: everything is rendered in memory first.
side effects: none beyond those files. It does not commit, push, or touch the
           project's own branches.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "SuperconducTED/superconducted-noise-engine"

# Status vocabulary. The emoji are the user-facing contract of this dashboard:
# green means done and verified against live state, red means not done, amber
# means in flight. Nothing is amber merely because it is uncertain; an unknown
# renders as its own grey marker so it cannot be mistaken for progress.
DONE, NOT_DONE, PARTIAL, UNKNOWN = "done", "not_done", "partial", "unknown"
MARK = {DONE: "✅", NOT_DONE: "❌", PARTIAL: "🟡", UNKNOWN: "⬜"}

# The team, in the order every per-person list renders. One list, so a change of
# membership is one edit: Yiğit's departure on 2026-10-16 had to be made in three
# copies of it. FORMER holds logins that were on the team: an ask still addressed
# to one of them is shown flagged for reassignment rather than dropped, because
# dropping it would silently lose the work it asks for.
TEAM_ORDER = ["mertefesensoy", "BurakOztekin", "bengisucvd", "BahaJarad"]
FORMER = {"yigit-arda"}


# --------------------------------------------------------------------------
# GitHub reads
# --------------------------------------------------------------------------

def gh(*args: str) -> object:
    """Run a gh command that emits JSON and return the parsed value.

    Raises SystemExit rather than returning partial data: a dashboard built on
    a half-failed read is worse than no dashboard, because it looks fine.
    """
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        sys.stderr.write(f"gh {' '.join(args)} failed:\n{proc.stderr}\n")
        raise SystemExit(1)
    return json.loads(proc.stdout or "null")


def fetch_issues() -> dict[int, dict]:
    rows = gh(
        "issue", "list", "--repo", REPO, "--state", "all", "--limit", "200",
        "--json", "number,title,state,assignees,labels,milestone,updatedAt,url",
    )
    return {r["number"]: r for r in rows}


def fetch_prs() -> dict[int, dict]:
    rows = gh(
        "pr", "list", "--repo", REPO, "--state", "all", "--limit", "150",
        "--json", "number,title,state,isDraft,mergeable,reviewDecision,headRefName,"
                  "url,updatedAt,createdAt,mergedAt,author,closingIssuesReferences",
    )
    return {r["number"]: r for r in rows}


def enrich_open_prs(prs: dict[int, dict]) -> None:
    """Add reviews and check-run detail to open PRs, in place.

    Only open PRs are enriched: this costs one API round-trip each and merged
    PRs never change. ``checks_stale_vs_main`` is the important derived field:
    a CONFLICTING PR's checks ran against a main that has since moved, so a
    green tick there is not evidence about the merge result.
    """
    for pr in prs.values():
        if pr["state"] != "OPEN":
            continue
        detail = gh(
            "pr", "view", str(pr["number"]), "--repo", REPO,
            "--json", "reviews,statusCheckRollup,headRefOid,additions,deletions,files",
        )
        pr["headRefOid"] = detail.get("headRefOid", "")
        pr["additions"] = detail.get("additions", 0)
        pr["deletions"] = detail.get("deletions", 0)
        pr["file_count"] = len(detail.get("files") or [])

        # A reviewer's *blocking* state, which is not the same as their latest
        # review. On GitHub a later COMMENTED review does not dismiss an earlier
        # CHANGES_REQUESTED; only an APPROVED or an explicit dismissal does. So
        # only those three states move the needle; COMMENTED is tracked purely
        # so the dashboard can say when the reviewer last looked. Getting this
        # wrong hides exactly the reviews that are holding the phase up.
        DECISIVE = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
        blocking: dict[str, dict] = {}
        last_seen: dict[str, str] = {}
        for rev in detail.get("reviews") or []:
            who = (rev.get("author") or {}).get("login", "?")
            if who.endswith("code-quality") or who.endswith("[bot]"):
                continue
            when = (rev.get("submittedAt") or "")
            last_seen[who] = max(last_seen.get(who, ""), when)
            if rev.get("state") not in DECISIVE:
                continue
            prev = blocking.get(who)
            if prev is None or when >= (prev.get("submittedAt") or ""):
                blocking[who] = rev
        pr["latest_reviews"] = [
            {"who": w, "state": r.get("state"), "at": (r.get("submittedAt") or "")[:10],
             "last_activity": last_seen.get(w, "")[:10]}
            for w, r in sorted(blocking.items())
        ]
        # Reviewers who have looked since but never lifted their block.
        pr["looked_since"] = [
            {"who": r["who"], "at": r["last_activity"]}
            for r in pr["latest_reviews"]
            if r["state"] == "CHANGES_REQUESTED" and r["last_activity"] > r["at"]
        ]

        checks, newest = [], ""
        for c in detail.get("statusCheckRollup") or []:
            name = c.get("name") or c.get("context") or "?"
            concl = (c.get("conclusion") or c.get("state") or "?").upper()
            started = c.get("startedAt") or ""
            newest = max(newest, started)
            checks.append({"name": name, "conclusion": concl, "started": started[:16]})
        pr["checks"] = checks
        pr["checks_newest"] = newest[:16]
        pr["checks_failing"] = [c for c in checks if c["conclusion"] not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
        # A conflicting PR cannot have been tested against the tree that would
        # merge, whatever its checks say.
        pr["checks_stale_vs_main"] = pr.get("mergeable") == "CONFLICTING" and bool(checks)


def plan_checks(plan: dict) -> list[dict]:
    """Every check object plan.json names: gate conditions and ticket ``done_by``."""
    out = [c["check"] for g in plan["gates"] for c in g["conditions"]]
    out += [t["done_by"] for t in plan["tickets"] if t.get("done_by")]
    return out


def last_commit_on(path: str, ref: str) -> dict | None:
    """The latest commit touching ``path`` on ``ref``, or None if the ref or path is absent.

    A 404 or 422 means the ref is gone (a merged branch is often deleted) or never
    existed, which is an expected answer here; any other failure is a broken read
    and exits 1 like every other read.
    """
    proc = subprocess.run(
        ["gh", "api", f"repos/{REPO}/commits?path={path}&sha={ref}&per_page=1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        if "HTTP 404" in proc.stderr or "HTTP 422" in proc.stderr:
            return None
        sys.stderr.write(f"gh api commits?path={path}&sha={ref} failed:\n{proc.stderr}\n")
        raise SystemExit(1)
    rows = json.loads(proc.stdout or "[]")
    if not rows:
        return None
    c = rows[0]
    return {"sha": c["sha"], "date": c["commit"]["committer"]["date"][:10], "ref": ref}


def fetch_context(plan: dict) -> dict:
    """Read every fact besides issues, PRs and threads that the page asserts.

    main's head and its ADR ledger (status and title per ADR), whether each path a
    ``file_on_main`` check names exists on main, every milestone, the plan document's
    latest commit on the plan's ref (then on main), whether that document is on main
    yet, and the body of each issue a ``task_ticked`` check reads. plan.json says
    which of these to read; every value comes from GitHub.
    """
    commit = gh("api", f"repos/{REPO}/commits/main",
                "--jq", '{sha: .sha, date: .commit.committer.date, msg: .commit.message}')
    state = {"sha": commit["sha"][:8], "date": commit["date"][:10],
             "msg": commit["msg"].splitlines()[0]}

    # ADR statuses, read out of the ledger on main rather than from a local
    # checkout, so the dashboard describes what merged and not what is staged.
    try:
        ledger = subprocess.run(
            ["gh", "api", f"repos/{REPO}/contents/docs/decisions.md",
             "-H", "Accept: application/vnd.github.raw"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        text = ledger.stdout if ledger.returncode == 0 else ""
    except OSError:
        text = ""

    adr: dict[str, str] = {}
    adr_title: dict[str, str] = {}
    for m in re.finditer(r"^## (ADR-\d{3}) — (.+?)$", text, re.M):
        tail = text[m.end():m.end() + 1200]
        s = re.search(r"\*\*Status\*\*:\s*([^\n.]+)", tail)
        adr[m.group(1)] = s.group(1).strip().rstrip(".") if s else "?"
        adr_title[m.group(1)] = m.group(2).strip()
    state["adr"] = adr
    state["adr_title"] = adr_title

    p = plan["phase"]
    paths = {c["path"] for c in plan_checks(plan) if c["kind"] == "file_on_main"}
    paths.add(p["plan_doc"])
    state["paths"] = {}
    for path in sorted(paths):
        probe = subprocess.run(["gh", "api", f"repos/{REPO}/contents/{path}"],
                               capture_output=True, text=True)
        state["paths"][path] = probe.returncode == 0

    state["milestones"] = {
        m["number"]: {"title": m["title"], "state": m["state"], "due": (m.get("due_on") or "")[:10],
                      "open": m["open_issues"], "closed": m["closed_issues"], "url": m["html_url"]}
        for m in gh("api", f"repos/{REPO}/milestones?state=all&per_page=100")
    }

    # The plan document's freshness. plan.json is quoted from one commit of it; if
    # the document has moved since, every hand-curated row here may be stale, which
    # is exactly how the phase-3 action block went stale. Read it on the plan's own
    # ref first, then on main, because the ref may be deleted once its PR merges.
    state["plan_doc"] = None
    for ref in [p.get("plan_ref"), "main"]:
        if ref and state["plan_doc"] is None:
            state["plan_doc"] = last_commit_on(p["plan_doc"], ref)

    state["bodies"] = {}
    for n in sorted({c["issue"] for c in plan_checks(plan) if c["kind"] == "task_ticked"}):
        state["bodies"][n] = gh("issue", "view", str(n), "--repo", REPO,
                                "--json", "body")["body"] or ""
    return state


# Every post's author, both timestamps and body. ``lastEditedAt`` matters: a
# checkbox added to a post by a later edit is only as old as that edit, not as
# old as the post.
POST_FIELDS = "author { __typename login } createdAt lastEditedAt body url"

ISSUE_THREADS = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { number title POST_FIELDS
              comments(first: 100) { totalCount nodes { POST_FIELDS } } }
    }
  }
}""".replace("POST_FIELDS", POST_FIELDS)

PR_THREADS = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 20, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title isDraft POST_FIELDS
        comments(first: 100) { totalCount nodes { POST_FIELDS } }
        reviews(first: 100) { totalCount nodes { POST_FIELDS state submittedAt } }
        reviewRequests(first: 20) {
          nodes { requestedReviewer { __typename ... on User { login } } }
        }
        timelineItems(itemTypes: [REVIEW_REQUESTED_EVENT], last: 100) {
          nodes { ... on ReviewRequestedEvent {
            createdAt actor { login } requestedReviewer { ... on User { login } } } }
        }
      }
    }
  }
}""".replace("POST_FIELDS", POST_FIELDS)


def fetch_conversations() -> dict[str, list[dict]]:
    """Every open issue and open PR with its posts, reviews and pending review requests.

    Two paged GraphQL reads instead of one ``gh`` call per thread. Both go through
    ``gh()``, so a failed read exits 1 like every other read here: an empty result
    would render as "nobody owes anything", which is the most misleading thing this
    section could say. Closed and merged threads are not read at all, because an
    ask on a closed thread is no longer owed to anyone.
    """
    owner, name = REPO.split("/")
    out: dict[str, list[dict]] = {}
    for key, query in (("issues", ISSUE_THREADS), ("pullRequests", PR_THREADS)):
        nodes, cursor = [], None
        while True:
            args = ["api", "graphql", "-f", f"query={query}",
                    "-f", f"owner={owner}", "-f", f"name={name}"]
            if cursor:
                args += ["-f", f"cursor={cursor}"]
            page = gh(*args)["data"]["repository"][key]
            nodes += page["nodes"]
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
        out["prs" if key == "pullRequests" else "issues"] = nodes
    return out


# --------------------------------------------------------------------------
# Join and derive
# --------------------------------------------------------------------------

def prs_for_issue(issue_no: int, prs: dict[int, dict], hints: list[int] | None = None) -> list[dict]:
    """Every open PR that would close an issue, newest first.

    Three sources, in descending trustworthiness: an explicit ``pr_hint`` in
    plan.json (for branches opened without a closing keyword and without the
    number in the name), GitHub's own ``closingIssuesReferences``, then the
    branch name and title. An issue can legitimately have more than one open PR
    (#53 has two), so this returns a list; taking only the first would hide a
    blocked one behind a clean one.
    """
    open_prs = [p for p in prs.values() if p["state"] == "OPEN"]
    found: dict[int, dict] = {}
    for n in hints or []:
        if n in prs and prs[n]["state"] == "OPEN":
            found[n] = prs[n]
    for p in open_prs:
        for ref in p.get("closingIssuesReferences") or []:
            if ref.get("number") == issue_no:
                found[p["number"]] = p
    pat = re.compile(rf"(?:issue[-_ ]?|#)0*{issue_no}\b", re.I)
    for p in open_prs:
        if pat.search(p.get("headRefName", "")) or pat.search(p.get("title", "")):
            found[p["number"]] = p
    return sorted(found.values(), key=lambda p: p["updatedAt"], reverse=True)


def pr_for_issue(issue_no: int, prs: dict[int, dict], hints: list[int] | None = None) -> dict | None:
    """The PR to *show* for an issue: the one furthest from merging.

    When an issue has several open PRs, the honest headline is the one that is
    stuck, not the one that happens to be tidiest.
    """
    candidates = prs_for_issue(issue_no, prs, hints)
    if not candidates:
        return None
    def stuckness(p: dict) -> tuple:
        return (
            0 if p.get("mergeable") == "CONFLICTING" else 1,
            0 if p.get("isDraft") else 1,
            0 if p.get("reviewDecision") == "CHANGES_REQUESTED" else 1,
        )
    return min(candidates, key=stuckness)


def merged_pr_for_issue(issue_no: int, prs: dict[int, dict]) -> dict | None:
    pat = re.compile(rf"(?:issue[-_ ]?|#)0*{issue_no}\b", re.I)
    hits = [p for p in prs.values() if p["state"] == "MERGED"
            and (pat.search(p.get("headRefName", "")) or pat.search(p.get("title", "")))]
    return max(hits, key=lambda p: p.get("mergedAt") or "") if hits else None


def dep_met(dep: dict, issues: dict, prs: dict, milestone_state: dict) -> bool:
    """Is this dependency satisfied?

    ``satisfied_by`` matters more than it looks. A downstream ticket almost
    never depends on an *issue*; it depends on an artifact that issue produces.
    #57's issue is still open because its advisor half is outstanding, but the
    contract #59, #60, #61 and #63 actually consume merged in PR #69. Keying
    those edges on issue closure would paint the entire trainer track blocked
    when nothing is stopping it, which is the single most expensive mistake
    this dashboard could make. So a dep may name the artifact that discharges
    it, and issue closure is only the default when nothing more precise exists.
    """
    sat = dep.get("satisfied_by")
    if sat:
        return artifact_met(sat, issues, prs)

    kind = dep["kind"]
    if kind == "issue":
        return issues.get(dep["id"], {}).get("state") == "CLOSED"
    if kind == "pr":
        return prs.get(dep["id"], {}).get("state") == "MERGED"
    if kind == "gate":
        return milestone_state.get(dep["id"], {}).get("status") == DONE
    return False


def artifact_met(sat: dict, issues: dict, prs: dict) -> bool:
    """Has the artifact a ``satisfied_by`` or ``done_by`` names landed?"""
    if sat["kind"] == "pr_merged":
        return prs.get(sat["id"], {}).get("state") == "MERGED"
    if sat["kind"] == "issue_closed":
        return issues.get(sat["id"], {}).get("state") == "CLOSED"
    return False


def check_status(chk: dict, issues: dict, prs: dict, ctx: dict,
                 hint_map: dict[int, list[int]]) -> tuple[str, str | None]:
    """One gate condition's status and the note to show with it, from live state.

    Every kind reads GitHub except ``manual``, whose status is whatever plan.json
    states, and ⬜ when it states none: an unknown must never read as progress.
    Two kinds exist because of phase 4's gates. ``milestone_closed`` reads a
    milestone's state (gate L5 is "the phase-3 milestone closed"). ``task_ticked``
    reads a task-list item on an issue's body whose text starts with a marker, so a
    gate GitHub cannot otherwise see (L1, job 1's report) is closed the way the team
    already closes asks: by someone ticking a box. A box that is not there yet is ⬜
    with a note naming where to add it, never ❌, because no one has said "not done".
    """
    note = chk.get("note")
    kind = chk["kind"]
    if kind == "issue_closed":
        st = DONE if issues.get(chk["id"], {}).get("state") == "CLOSED" else NOT_DONE
        if st == NOT_DONE and pr_for_issue(chk["id"], prs, hint_map.get(chk["id"])):
            st = PARTIAL
    elif kind == "pr_merged":
        p = prs.get(chk["id"], {})
        st = DONE if p.get("state") == "MERGED" else (PARTIAL if p.get("state") == "OPEN" else NOT_DONE)
    elif kind == "adr_status":
        cur = ctx["adr"].get(chk["id"])
        if cur is None:
            # A missing ADR must not pass a "not Deferred" test by being absent.
            st, note = UNKNOWN, f"{chk['id']} is not in the ledger on main."
        elif chk.get("not"):
            st = DONE if adr_left(cur, chk["not"]) else NOT_DONE
            note = f"Ledger on main reads: {cur}."
        else:
            st = DONE if adr_met(cur, chk["want"]) else NOT_DONE
            note = f"Ledger on main reads: {cur}."
    elif kind == "file_on_main":
        st = DONE if ctx["paths"].get(chk["path"]) else NOT_DONE
    elif kind == "milestone_closed":
        ms = ctx["milestones"].get(chk["id"])
        if ms is None:
            st, note = UNKNOWN, f"Milestone {chk['id']} was not found on GitHub."
        else:
            st = DONE if ms["state"] == "closed" else NOT_DONE
            note = (f"Milestone {chk['id']} ({ms['title']}) is {ms['state']}: "
                    f"{ms['open']} open and {ms['closed']} closed issues.")
    elif kind == "task_ticked":
        mark = chk["starts"]
        # The marker must end at a word boundary, so "L1" never matches "L10: ...".
        items = [(ticked, text) for ticked, text in task_items(ctx["bodies"].get(chk["issue"], ""))
                 if text.startswith(mark) and not text[len(mark):len(mark) + 1].isalnum()]
        if not items:
            st = UNKNOWN
            note = (f"#{chk['issue']} carries no task item starting \"{chk['starts']}\" yet, so "
                    f"GitHub cannot say. Add \"- [ ] {chk['starts']}: ...\" to its body and tick it "
                    f"when this is done.")
        elif any(ticked for ticked, _ in items):
            st, note = DONE, f"Ticked on #{chk['issue']}'s body."
        else:
            st, note = NOT_DONE, f"Unticked on #{chk['issue']}'s body."
    else:  # manual
        st = {"done": DONE, "not_done": NOT_DONE, "partial": PARTIAL}.get(chk.get("state", ""), UNKNOWN)
    return st, note


def adr_met(status: str, want: str) -> bool:
    """Does a ledger status read as ``want``, and only that?

    Equal, or ``want`` followed by a parenthetical. A prefix test is not enough:
    ADR-021 reads "Accepted on the constraint · Open on variance-injection design",
    which starts with "Accepted" and is half open, and the phase-3 prefix test
    would have drawn it ✅.
    """
    s, w = status.strip().lower(), want.strip().lower()
    return s == w or s.startswith(w + " (")


def adr_left(status: str, word: str) -> bool:
    """Has a ledger status left ``word`` entirely? "Open / Deferred" has not left Deferred."""
    return word.strip().lower() not in status.lower()


def gate_status(statuses: list[str]) -> str:
    """A gate's mark from its conditions'.

    Met only when every condition is; ⬜ when no condition can be read at all, so a
    gate made only of unknowns never reads as "not done" on GitHub's say-so; amber
    once anything is met or in flight; otherwise not done.
    """
    if statuses and all(s == DONE for s in statuses):
        return DONE
    if statuses and all(s == UNKNOWN for s in statuses):
        return UNKNOWN
    if any(s in (DONE, PARTIAL) for s in statuses):
        return PARTIAL
    return NOT_DONE


def live_priority(issue: dict) -> str:
    """The ticket's ``priority:*`` label on GitHub, or "unset"."""
    for lab in issue.get("labels") or []:
        name = lab.get("name", "")
        if name.startswith("priority:"):
            return name.split(":", 1)[1]
    return "unset"


def pr_author(pr: dict) -> str:
    return (pr.get("author") or {}).get("login") or ""


def co_owners(t: dict) -> list[dict]:
    """A ticket's co-owners with a named piece of their own, as {login, action, why}.

    ``co_owners`` is a list because #125 has three roles (QPU side, offline half,
    statistics review). The older single ``co_owner`` / ``co_owner_action`` form is
    still read. A co-owner without an action gets no row of their own, as before.
    """
    if t.get("co_owners"):
        return t["co_owners"]
    if t.get("co_owner") and t.get("co_owner_action"):
        return [{"login": t["co_owner"], "action": t["co_owner_action"],
                 "why": t.get("co_owner_why")}]
    return []


def stuckest(candidates: list[dict]) -> dict | None:
    """Of several open PRs, the one furthest from merging (see ``pr_for_issue``)."""
    if not candidates:
        return None
    return min(candidates, key=lambda p: (
        0 if p.get("mergeable") == "CONFLICTING" else 1,
        0 if p.get("isDraft") else 1,
        0 if p.get("reviewDecision") == "CHANGES_REQUESTED" else 1,
    ))


def review_blockers(pr: dict) -> list[dict]:
    """Why this PR is not merging, in the order that matters.

    Ordered deliberately: a conflict must be fixed before a review is worth
    asking for, and a draft will not be reviewed at all. main's ruleset requires
    one approval and does *not* dismiss stale reviews on push, so a standing
    CHANGES_REQUESTED needs an explicit re-review; pushing a fix does not clear it.
    """
    out: list[dict] = []
    if pr.get("isDraft"):
        out.append({"severity": "high", "text": "Still a draft: CI and reviewers will not treat it as ready."})
    if pr.get("mergeable") == "CONFLICTING":
        out.append({"severity": "critical", "text": "Conflicts with main: needs a rebase before it can merge, and ci.yml will not re-run until it is clean."})
    if pr.get("checks_stale_vs_main"):
        out.append({"severity": "high", "text": f"Its green checks last ran {pr.get('checks_newest') or 'earlier'} against a main that has moved since; they are not evidence about the merge result."})
    if pr.get("checks_failing"):
        names = ", ".join(c["name"] for c in pr["checks_failing"][:4])
        out.append({"severity": "critical", "text": f"Failing checks: {names}."})
    decision = pr.get("reviewDecision")
    changes = [r for r in pr.get("latest_reviews") or [] if r["state"] == "CHANGES_REQUESTED"]
    if decision == "CHANGES_REQUESTED" or changes:
        who = ", ".join(f"@{r['who']} ({r['at']})" for r in changes) or "a reviewer"
        out.append({"severity": "critical", "text": f"CHANGES_REQUESTED standing from {who}. Stale reviews are not dismissed on push, so it needs an explicit re-review, not just a fix."})
    elif decision == "REVIEW_REQUIRED" or not pr.get("latest_reviews"):
        out.append({"severity": "high", "text": "No approving review yet: main's ruleset requires one."})
    return out


def lint_plan(plan: dict) -> list[str]:
    """Refuse a plan.json that assigns work to someone off the team; warn on stale names.

    An owner, co-owner or planned-item owner outside ``TEAM_ORDER`` is a hard error:
    work assigned to nobody is exactly how an ask goes unanswered, and a daily run
    that fails loudly gets fixed the same morning. A former member named in free
    text is a warning on the page instead, because the text may be quoting a ticket
    that still names them: phase 3's board told Bengisu that "@yigit-arda depends on
    the answer" for a week after he left, copied from #58's own body.
    """
    team = set(TEAM_ORDER)
    for t in plan["tickets"]:
        for who in [t["owner"], *(c["login"] for c in co_owners(t))]:
            if who not in team:
                raise SystemExit(f"plan.json: #{t['id']} is assigned to @{who}, who is not in "
                                 f"TEAM_ORDER. Reassign it before the dashboard can render.")
    for item in plan.get("planned") or []:
        for who in [*item.get("owners", []), *([item["actor"]] if item.get("actor") else [])]:
            if who not in team:
                raise SystemExit(f"plan.json: planned item {item['key']} names @{who}, who is "
                                 f"not in TEAM_ORDER.")

    warnings: list[str] = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        elif isinstance(node, str):
            for login in sorted(FORMER):
                if login.lower() in node.lower():
                    warnings.append(f"plan.json {where} names @{login}, who has left the team.")

    for key, value in plan.items():
        if key != "people":   # the people table keeps former members' names on purpose
            walk(value, key)
    return warnings


def build(plan: dict, issues: dict, prs: dict, ctx: dict) -> dict:
    tickets = []
    gate_state: dict[str, dict] = {}
    hint_map = {t["id"]: t.get("pr_hint") or [] for t in plan["tickets"]}
    warnings = lint_plan(plan)

    # Gates first, so a "gate" dependency and a lane's rank can be resolved
    # against them. Phase 4's gates are ordered, not dated (plan §6): a gate has
    # no target unless plan.json gives one, and nothing here invents a pace.
    for g in plan["gates"]:
        conds = []
        for c in g["conditions"]:
            st, note = check_status(c["check"], issues, prs, ctx, hint_map)
            conds.append({"text": c["text"], "status": st, "note": note})
        n_done = sum(1 for c in conds if c["status"] == DONE)
        gate_state[g["id"]] = {
            **g, "conditions": conds, "done": n_done, "total": len(conds),
            "status": gate_status([c["status"] for c in conds]),
            "days_left": days_between(plan_today(), g["target"]) if g.get("target") else None,
        }

    # Lanes: the gates in each lane are in the plan's order, so the first one not
    # met is that lane's next gate. A later gate reading met while an earlier one
    # does not is a contradiction between the plan's order and GitHub; it is shown,
    # never silently resolved, because either reading could be the wrong one.
    lanes = []
    for lane in plan["lanes"]:
        ids = [g["id"] for g in plan["gates"] if g["lane"] == lane["id"]]
        nxt = next((i for i in ids if gate_state[i]["status"] != DONE), None)
        for i, gid in enumerate(ids):
            if gate_state[gid]["status"] == DONE:
                for earlier in ids[:i]:
                    if gate_state[earlier]["status"] != DONE:
                        warnings.append(f"Gate {gid} reads met while {earlier}, which comes before "
                                        f"it in lane {lane['id']}, does not. Check {earlier}'s source.")
        held = lane.get("rank_after")
        rank = (held["rank"] if held and gate_state[held["gate"]]["status"] == DONE
                else lane["rank"])
        lanes.append({**lane, "gate_ids": ids, "next": nxt, "rank_now": rank,
                      "held": bool(held) and rank != held["rank"]})
    lane_by_id = {lane["id"]: lane for lane in lanes}

    # The plan document itself. A phase plan on an unmerged branch is still the
    # plan, but the page must say where it is read from, and must say when the
    # document has moved past the commit plan.json was quoted from.
    p = plan["phase"]
    doc = ctx.get("plan_doc")
    if doc is None:
        warnings.append(f"{p['plan_doc']} was not found on {p.get('plan_ref') or 'main'} or on "
                        f"main, so plan.json cannot be checked against it.")
    elif not doc["sha"].startswith(p["plan_sha"]):
        warnings.append(f"The plan document changed at {doc['sha'][:8]} ({doc['date']}) on "
                        f"{doc['ref']}, after the {p['plan_sha']} plan.json was quoted from. "
                        f"Re-read it and update plan.json.")

    # Tickets.
    for t in plan["tickets"]:
        issue = issues.get(t["id"], {})
        closed = issue.get("state") == "CLOSED"
        hints = t.get("pr_hint") or []
        all_prs = prs_for_issue(t["id"], prs, hints)
        pr = pr_for_issue(t["id"], prs, hints)
        merged = merged_pr_for_issue(t["id"], prs) if not pr else None
        assignees = {a.get("login") for a in issue.get("assignees") or []}
        if issue and t["owner"] not in assignees:
            warnings.append(f"plan.json makes @{t['owner']} the owner of #{t['id']}, but GitHub "
                            f"assigns it to " + (", ".join(f"@{a}" for a in sorted(assignees))
                                                 or "nobody") + ".")

        # "Delivered" is not "closed". The plan can say what done looks like for
        # its own purpose (#63: "merged"), and that artifact can land while the
        # issue stays open for residue. Reading only issue closure told Baha to
        # "finish #63" the morning after PR #113 merged it. So a ticket may name
        # the artifact that delivers it (``done_by``), read live; the open issue is
        # then reported as such, never hidden and never closed by the dashboard.
        delivered = bool(t.get("done_by")) and artifact_met(t["done_by"], issues, prs)

        # A hard dependency carrying a "part" gates only that part of the
        # ticket, not the ticket. #60's dependency on #63 is for the first
        # archive fit alone; its LSE stage (the M2 gate, and the whole reason
        # the trainer is called the long pole) needs nothing from #63. Treating a
        # partial dep as blocking would park the phase's critical path behind
        # a data ticket for no reason, so partial deps become scope notes.
        unmet_all = [d for d in t.get("hard_deps", []) if not dep_met(d, issues, prs, gate_state)]
        unmet = [d for d in unmet_all if not d.get("part")]
        partial = [d for d in unmet_all if d.get("part")]
        soft_unmet = [d for d in t.get("soft_deps", []) if not dep_met(d, issues, prs, gate_state)]

        blockers: list[dict] = []
        if pr:
            blockers += review_blockers(pr)
        blockers += [b for b in t.get("extra_blockers", []) if b.get("severity") != "info"]

        if closed or delivered:
            state = "done"
        elif unmet:
            state = "blocked"
        elif pr:
            state = "in_review"
        else:
            state = "ready"

        tickets.append({
            **t,
            "title": issue.get("title", t["short"]),
            "url": issue.get("url", f"https://github.com/{REPO}/issues/{t['id']}"),
            "issue_state": issue.get("state", "?"),
            "priority": live_priority(issue),
            "lane_info": lane_by_id.get(t.get("lane")),
            "delivered_open": delivered and not closed,
            "delivered_pr": prs.get(t["done_by"]["id"]) if delivered and t["done_by"]["kind"] == "pr_merged" else None,
            "state": state,
            "pr": pr, "all_prs": all_prs, "merged_pr": merged,
            "unmet_hard": unmet, "unmet_partial": partial, "unmet_soft": soft_unmet,
            "blockers": blockers,
            "declared_unblocks": t.get("unblocks") or [],
            "notes_info": [b for b in t.get("extra_blockers", []) if b.get("severity") == "info"],
        })

    # Live fan-out: how many tickets this one is *still* holding up, counted from
    # the unmet dependency edges that actually point at it. The declared
    # "unblocks" list in plan.json describes the ticket in the abstract and goes
    # stale the moment an artifact discharges those edges: #57 declares four
    # downstreams, but the contract they consume merged in PR #69, so a
    # follow-up PR on #57 now releases nobody. Ranking on the declared list put
    # a docs cleanup above the trainer, which is exactly backwards. A PR that a
    # ticket waits on (#122 on PR #121) is counted the same way, keyed by PR, so
    # its pending reviewers can be told what their review releases.
    holding: dict[int, set[int]] = defaultdict(set)
    holding_pr: dict[int, set[int]] = defaultdict(set)
    for t in tickets:
        for dep in t["unmet_hard"] + t["unmet_partial"]:
            if dep["kind"] == "issue":
                holding[dep["id"]].add(t["id"])
            elif dep["kind"] == "pr":
                holding_pr[dep["id"]].add(t["id"])
    for t in tickets:
        t["unblocks"] = sorted(holding.get(t["id"], set()))

    parked = []
    for x in plan.get("parked") or []:
        issue = issues.get(x["id"], {})
        parked.append({**x, "title": issue.get("title", "?"), "state": issue.get("state", "?"),
                       "url": issue.get("url", f"https://github.com/{REPO}/issues/{x['id']}"),
                       "milestone": (issue.get("milestone") or {}).get("title")})

    planned = [{**x, "opens_status": gate_state[x["opens_after"]]["status"] if x.get("opens_after") else None}
               for x in plan.get("planned") or []]

    # A risk the plan names is quoted as written; where it names a PR, the PR's
    # live state is shown beside it, so "in review since September" carries its
    # measured age instead of the plan's adjective.
    risk_live: dict[str, str] = {}
    for r in plan.get("risks") or []:
        live = r.get("live") or {}
        if live.get("kind") == "pr_open":
            pr = prs.get(live["id"], {})
            made = (pr.get("createdAt") or "")[:10]
            if pr.get("state") == "OPEN" and made:
                risk_live[r["text"]] = (f"PR #{live['id']} is open, created {made} "
                                        f"({days_between(made, plan_today())} days).")
            elif pr.get("state") == "MERGED":
                risk_live[r["text"]] = f"PR #{live['id']} merged on {(pr.get('mergedAt') or '')[:10]}."
            elif pr:
                risk_live[r["text"]] = f"PR #{live['id']} is {pr.get('state', '?').lower()}."

    plan_pr = prs.get(p.get("plan_pr")) if p.get("plan_pr") else None
    return {"gates": list(gate_state.values()), "lanes": lanes, "tickets": tickets,
            "holding_pr": {k: sorted(v) for k, v in holding_pr.items()},
            "prs_by_number": {n: prs[n] for n in holding_pr if n in prs},
            "parked": parked, "planned": planned, "warnings": warnings, "risk_live": risk_live,
            "plan_pr": {"number": plan_pr["number"], "state": plan_pr["state"],
                        "url": plan_pr["url"]} if plan_pr else None}


def plan_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def days_between(a: str, b: str) -> int:
    fmt = "%Y-%m-%d"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).days


# --------------------------------------------------------------------------
# Who owes an answer
# --------------------------------------------------------------------------
#
# Two signals only, because they are the two that GitHub itself closes:
#
#   1. a pending review request: GitHub drops the request the moment the
#      reviewer submits any review, so "still requested" means "not answered";
#   2. an unticked task-list item that *starts* with a teammate's @mention,
#      "- [ ] @BurakOztekin runs the desktop runbook": it is owed until someone
#      ticks the box, which is a deliberate act by a person who read the thread.
#
# A bare @mention is not an ask. Measured on the open threads on 2026-10-23, 98 of
# 147 mention pairs had no later post by the person mentioned, and nearly every
# one was descriptive ("@BurakOztekin authored #69"). A question mark next to a
# mention found 2, and the one real question among them had been answered in a
# PR's checklist rather than in the thread, which free text cannot see. Either
# rule would bury the real asks under noise, so neither is used.

TASK_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[([ xX])\][ \t]+(\S.*)$")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
LEAD_MENTION = re.compile(r"@([A-Za-z0-9][A-Za-z0-9-]{0,38})")
# Between two addressees: a comma, &, /, "and", Turkish "ve", or only a space.
MENTION_SEP = re.compile(r"[ \t]*(?:(?:,|&|/|\band\b|\bve\b)[ \t]*)?", re.I)
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def is_bot(author: dict | None) -> bool:
    login = (author or {}).get("login") or ""
    return ((author or {}).get("__typename") == "Bot" or login.endswith("[bot]")
            or login.endswith("code-quality"))


def task_items(body: str) -> list[tuple[bool, str]]:
    """Every task-list item GitHub would render as a checkbox, as (ticked, text).

    Lines inside fenced code and inside HTML comments are skipped: those are
    templates or hidden text, and neither renders as a live checkbox anyone can
    tick. A blockquoted item ("> - [ ] ...", someone quoting another list) needs
    no rule of its own: TASK_ITEM requires the list marker at the start of the
    line, so it never matches.
    """
    out: list[tuple[bool, str]] = []
    fence: str | None = None
    for line in HTML_COMMENT.sub("", body or "").splitlines():
        f = FENCE.match(line)
        if f:
            # Open on a marker, close only on the same marker.
            fence = None if fence == f.group(1) else (fence or f.group(1))
            continue
        if fence:
            continue
        m = TASK_ITEM.match(line)
        if m:
            out.append((m.group(1) != " ", m.group(2).strip()))
    return out


def addressees(text: str) -> tuple[list[str], str]:
    """The logins a task item is addressed to, and the item's text without them.

    An item is addressed to the @mentions it *opens* with: "@A runs X", "@A and
    @B confirm", "@A, @B: ...". A mention anywhere later in the sentence is not an
    address ("Runbook for @A posted" asks something of whoever posts it, not of A).
    An opening mention followed by an apostrophe is a suffix, English "@A's
    review is landed" or Turkish "@A'nın", and makes the item a statement about A
    rather than an ask of A, so the item is addressed to nobody.
    """
    who: list[str] = []
    pos = 0
    while True:
        m = LEAD_MENTION.match(text, pos)
        if not m:
            break
        if text[m.end():m.end() + 1] in ("'", "’"):
            return [], text
        who.append(m.group(1))
        pos = m.end()
        sep = MENTION_SEP.match(text, pos)
        if not text.startswith("@", sep.end()):
            break
        pos = sep.end()
    rest = text[pos:].lstrip(" \t:,-") if who else text
    return who, rest


def thread_posts(th: dict) -> list[dict]:
    """The human posts on one issue or PR: opening post, comments, submitted reviews."""
    raw = [th, *th["comments"]["nodes"],
           *[r for r in (th.get("reviews") or {}).get("nodes", []) if r.get("state") != "PENDING"]]
    out = []
    for p in raw:
        if is_bot(p.get("author")):
            continue
        out.append({
            "who": (p.get("author") or {}).get("login") or "ghost",
            "at": p.get("submittedAt") or p["createdAt"],
            "edited": p.get("lastEditedAt") or "",
            "body": p.get("body") or "",
            "url": p["url"],
            "state": p.get("state"),
        })
    return out


def owed_answers(conv: dict[str, list[dict]], today: str) -> dict:
    """Who owes what on open issues and PRs, oldest first.

    Contract: ``conv`` is ``fetch_conversations()``'s result; ``today`` is a
    YYYY-MM-DD date, used only for ages. Returns ``{"asks": [...], "truncated":
    [...]}``. Each ask names who owes it, what it is, where (thread and the post's
    own URL), who asked, ``since`` (a date), and ``last_here``, the owed person's
    latest post on that thread, so a reader can tell "forgot" from "working on it"
    without opening the thread. ``truncated`` lists every thread whose posts were
    not all read, so a missing ask shows up as a visible warning, never as silence.

    ``since`` never overstates a wait. A review request dates from its latest
    ReviewRequestedEvent. A checkbox dates from its post, unless the post was
    edited later, in which case it dates from that edit (``lower_bound`` true):
    the box may have been added by the edit, and GitHub does not say which edit
    added it, so the latest edit is the only date that cannot accuse anyone of a
    wait longer than the true one.
    """
    canon = {l.lower(): l for l in [*TEAM_ORDER, *sorted(FORMER)]}
    asks: list[dict] = []
    truncated: list[str] = []

    for kind, threads in (("issue", conv["issues"]), ("PR", conv["prs"])):
        for th in threads:
            ref = {"kind": kind, "number": th["number"], "title": th["title"], "url": th["url"]}
            for part in ("comments", "reviews"):
                block = th.get(part)
                if block and block["totalCount"] > len(block["nodes"]):
                    truncated.append(f"{kind} #{th['number']}: {len(block['nodes'])} of "
                                     f"{block['totalCount']} {part} read")
            posts = thread_posts(th)
            last: dict[str, str] = {}
            for p in posts:
                last[p["who"]] = max(last.get(p["who"], ""), p["at"])

            def ask(who: str, **kw) -> dict:
                since = kw["since"]
                return {"who": who, "thread": ref, "former": who in FORMER,
                        "days": days_between(since, today) if since else None,
                        "last_here": last.get(who, "")[:10], **kw}

            seen: set[tuple] = set()
            for p in posts:
                for ticked, text in task_items(p["body"]):
                    if ticked:
                        continue
                    names, rest = addressees(text)
                    team = [canon[n.lower()] for n in names if n.lower() in canon]
                    for who in team:
                        key = (who, p["url"], rest)
                        if key in seen:
                            continue
                        seen.add(key)
                        edited = bool(p["edited"]) and p["edited"][:10] > p["at"][:10]
                        asks.append(ask(
                            who, kind="checkbox", text=MD_LINK.sub(r"\1", rest),
                            url=p["url"], by=p["who"],
                            since=(p["edited"] if edited else p["at"])[:10],
                            posted=p["at"][:10], lower_bound=edited,
                            others=[o for o in team if o != who]))

            if kind != "PR":
                continue
            requested: dict[str, tuple[str, str]] = {}
            for ev in th["timelineItems"]["nodes"]:
                rv = ((ev.get("requestedReviewer") or {}).get("login") or "").lower()
                if rv and ev.get("createdAt", "") >= requested.get(rv, ("", ""))[0]:
                    requested[rv] = (ev["createdAt"], (ev.get("actor") or {}).get("login") or "?")
            for rr in th["reviewRequests"]["nodes"]:
                who = canon.get(((rr.get("requestedReviewer") or {}).get("login") or "").lower())
                if not who:
                    continue  # a team, a bot, or someone outside the team
                at, by = requested.get(who.lower(), ("", "?"))
                mine = [p for p in posts if p["who"] == who and p["state"]]
                standing = max((p for p in mine if p["state"] in ("APPROVED", "CHANGES_REQUESTED")),
                               key=lambda p: p["at"], default=None)
                if standing and standing["state"] == "CHANGES_REQUESTED":
                    text = (f"Re-review PR #{th['number']}: your CHANGES_REQUESTED from "
                            f"{standing['at'][:10]} still stands")
                elif standing:
                    text = (f"Re-review PR #{th['number']}: you approved on "
                            f"{standing['at'][:10]} and were asked again")
                elif mine:
                    text = (f"Re-review PR #{th['number']}: asked again after your review of "
                            f"{max(p['at'] for p in mine)[:10]}")
                else:
                    text = f"Review PR #{th['number']}"
                asks.append(ask(who, kind="re-review" if mine else "review", text=text,
                                url=th["url"], by=by, since=at[:10], posted=at[:10],
                                lower_bound=False, others=[]))

    order = {l: i for i, l in enumerate([*TEAM_ORDER, *sorted(FORMER)])}
    asks.sort(key=lambda x: (order.get(x["who"], 99), x["since"] or "9999", x["thread"]["number"]))
    return {"asks": asks, "truncated": truncated}


def owed_by_person(owed: dict) -> dict[str, list[dict]]:
    """``owed_answers()``'s asks grouped per login, keeping its oldest-first order."""
    out: dict[str, list[dict]] = defaultdict(list)
    for x in owed["asks"]:
        out[x["who"]].append(x)
    return dict(out)


ASK_KIND = {"review": "review requested", "re-review": "re-review requested",
            "checkbox": "checkbox"}


def clip(s: str, n: int = 150) -> str:
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def ask_parts(x: dict) -> dict[str, str]:
    """The pieces every rendering of an ask shares, as plain text."""
    t = x["thread"]
    where = f"{t['kind']} #{t['number']}"
    if x["kind"] == "checkbox":
        what = clip(x["text"])
        by = "own checklist" if x["by"] == x["who"] else f"asked by @{x['by']}"
        if x["others"]:
            by += ", with " + ", ".join(f"@{o}" for o in x["others"])
    else:
        what = x["text"]
        by = "self-requested" if x["by"] == x["who"] else f"requested by @{x['by']}"
    if not x["since"]:
        age = when = "date unknown"
    else:
        d = x["days"]
        age = f"{d} {'day' if d == 1 else 'days'}{' or more' if x['lower_bound'] else ''}"
        when = f"since {x['since']}{' or earlier' if x['lower_bound'] else ''} ({age})"
    if x["since"] and x["last_here"] > x["since"]:
        seen = f"has posted there since, on {x['last_here']}"
    else:
        seen = "no post there since"
    return {"where": where, "what": what, "by": by, "when": when, "age": age, "seen": seen}


def ask_line(x: dict) -> str:
    """One plain-text line for an ask, for STATUS.md and the run report."""
    p = ask_parts(x)
    lead = f"{p['what']} ({p['where']})" if x["kind"] == "checkbox" else p["what"]
    return f"{lead}: {p['by']}, {p['when']}; {p['seen']}"


# --------------------------------------------------------------------------
# "Work on this now": the ranked queue
# --------------------------------------------------------------------------

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# --------------------------------------------------------------------------
# History: one small record per day, so the phase can be read as a trend
# --------------------------------------------------------------------------

def history_dir(plan: dict) -> Path:
    """This phase's own history folder.

    Each phase writes its own folder (phase 4: ``history/phase-4/``) and reads only
    that one. A phase-3 record counts 28 gates across M0 to M4 and phase-3 tickets;
    diffing the first phase-4 record against it would report every gate and ticket
    as having moved. A separate folder also means a phase-4 run on a date a phase-3
    record already has can never overwrite that record: the phase-3 files stay
    byte-identical, as a dated record should.
    """
    return HERE / plan["phase"]["history_dir"]


def summarise(model: dict, ctx: dict, now: str, plan: dict) -> dict:
    """The compact daily record. Deliberately small and derived only.

    It holds counts and per-ticket states, never prose: the day-over-day story
    is *computed* by diffing two of these, so it cannot drift from what the
    dashboard says. One file per day, overwritten by later runs on the same
    day, so the record is "where the phase stood at the end of that day"
    rather than a log of every refresh. ``phase`` names the phase that wrote
    it, so a record copied into the wrong folder is skipped rather than diffed.
    """
    conds = [c for g in model["gates"] for c in g["conditions"]]
    counts: dict[str, int] = defaultdict(int)
    for t in model["tickets"]:
        counts[t["state"]] += 1
    ms = ctx["milestones"].get(plan["phase"]["milestone"]) or {}
    return {
        "phase": plan["phase"]["name"],
        "date": plan_today(),
        "generated": now,
        "main_sha": ctx["sha"],
        "gates_done": sum(1 for g in model["gates"] if g["status"] == DONE),
        "gates_total": len(model["gates"]),
        "conditions_done": sum(1 for c in conds if c["status"] == DONE),
        "conditions_total": len(conds),
        "gates": {g["id"]: {"done": g["done"], "total": g["total"], "status": g["status"]}
                  for g in model["gates"]},
        "milestone": {"open": ms.get("open"), "closed": ms.get("closed"), "state": ms.get("state")},
        "counts": dict(counts),
        "tickets": {str(t["id"]): t["state"] for t in model["tickets"]},
        "adr": dict(ctx["adr"]),
        "owed": {who: len(xs) for who, xs in owed_by_person(model["owed"]).items()},
    }


def load_history(plan: dict) -> list[dict]:
    folder = history_dir(plan)
    if not folder.is_dir():
        return []
    out = []
    for f in sorted(folder.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # a corrupt day must not take the whole dashboard down
        if rec.get("phase") == plan["phase"]["name"]:
            out.append(rec)
    return sorted(out, key=lambda d: d.get("date", ""))


STATE_WORD = {"ready": "ready to start", "in_review": "in review",
              "blocked": "blocked upstream", "done": "done"}
GATE_WORD = {DONE: "met", NOT_DONE: "not met", PARTIAL: "in flight", UNKNOWN: "unreadable"}


def day_events(prev: dict, cur: dict, plan: dict) -> list[str]:
    """What changed between two daily records, in plain language.

    Only transitions are reported. A ticket that sat blocked all week produces
    no line, which is the point: the list should read as "what moved", not as
    a re-statement of the board.
    """
    ev: list[str] = []
    short = {str(t["id"]): t["short"] for t in plan["tickets"]}

    dg = cur["gates_done"] - prev["gates_done"]
    if dg:
        ev.append(f"{'+' if dg > 0 else ''}{dg} {'gate' if abs(dg) == 1 else 'gates'} met "
                  f"({prev['gates_done']} to {cur['gates_done']} of {cur['gates_total']})")

    for gid, g in cur["gates"].items():
        p = prev["gates"].get(gid)
        if p and (p["status"] != g["status"] or p["done"] != g["done"]):
            ev.append(f"{gid} {GATE_WORD.get(p['status'], p['status'])} to "
                      f"{GATE_WORD.get(g['status'], g['status'])} "
                      f"({p['done']}/{p['total']} to {g['done']}/{g['total']} conditions)")

    pm, cm = prev.get("milestone") or {}, cur.get("milestone") or {}
    if pm.get("open") is not None and (pm.get("open"), pm.get("closed")) != (cm.get("open"), cm.get("closed")):
        ev.append(f"milestone {plan['phase']['milestone']}: {cm.get('open')} open and "
                  f"{cm.get('closed')} closed (was {pm.get('open')} and {pm.get('closed')})")

    for tid, state in cur["tickets"].items():
        was = prev["tickets"].get(tid)
        if was and was != state:
            ev.append(f"#{tid} {short.get(tid, '')}: {STATE_WORD.get(was, was)} "
                      f"to {STATE_WORD.get(state, state)}")

    for adr, status in cur["adr"].items():
        was = prev["adr"].get(adr)
        if was and was != status:
            ev.append(f"{adr}: {was} to {status}")

    # Records written before 2026-10-23 carry no "owed" key; a missing key is
    # "not measured", never zero, so no line is reported against such a day.
    if "owed" in prev and "owed" in cur:
        for who in sorted(set(prev["owed"]) | set(cur["owed"])):
            was, now = prev["owed"].get(who, 0), cur["owed"].get(who, 0)
            if was != now:
                name = plan["people"].get(who, {}).get("name", who)
                ev.append(f"{name} owes {now} {'answer' if now == 1 else 'answers'} "
                          f"(was {was})")

    if prev.get("main_sha") != cur.get("main_sha"):
        ev.append(f"main moved to {cur['main_sha']}")
    return ev


def person_colour(value: str) -> str:
    """The CSS value for a person's identity colour, from plan.json's ``colour``.

    ``series-1`` .. ``series-6`` name the brand's categorical sequence (``--s1`` ..
    ``--s6``, defined per light and dark mode, fixed order: colour follows the person,
    never their rank), ``idle`` the neutral for someone outside the team's rotation. Any
    other value, such as a ``#rrggbb`` hex, passes through unchanged, so an unmapped
    entry still renders.
    """
    if value.startswith("series-") and value[7:].isdigit() and 1 <= int(value[7:]) <= 6:
        return f"var(--s{value[7:]})"
    if value == "idle":
        return "var(--idle)"
    return value


def action_queue(model: dict, plan: dict) -> dict[str, list[dict]]:
    """One ranked action list per person.

    Ranking is by *lane first*, then by consequence. Sorted on:
      1. the lane's rank right now. The phase-4 plan states the order itself
         (§5.1: everyone on lane 1 first, lane 3 beside it, lane 2 resuming at
         gate L1), where the phase-3 plan stated only dependencies and the order
         had to be derived. A rank that contradicted the lead's written decision
         would make the board argue with the plan, so the plan's order leads and
         the lane's rank is recomputed from the live gate on every run.
      2. external latency: work waiting on someone outside the team.
      3. fan-out: how many other tickets this releases.
      4. the ticket's live priority label.
      5. kind, as a tiebreak only: a review you alone can clear, then in-flight
         work, then a fresh start.

    A ticket blocked on an upstream dependency is never listed against its own
    owner. It surfaces instead against whoever can clear the blocker: the owner
    of a blocking ticket, or the requested reviewers of a blocking PR.
    """
    by_person: dict[str, list[dict]] = defaultdict(list)
    prio = {"critical": 0, "high": 1, "medium-high": 2, "medium": 3, "low": 4, "unset": 5}
    KIND_TIE = {"review": 0, "in_review": 1, "ready": 2}

    def lane_rank(t: dict) -> int:
        return (t.get("lane_info") or {}).get("rank_now", 9)

    def rank(kind: str, fanout: int, t: dict) -> tuple:
        # The kind tiebreak is conditional on fan-out for a reason. Putting a
        # review first is only justified because it releases somebody else
        # cheaply; a review that frees nobody is just work, so it sinks below
        # fresh work in its lane.
        tie = 3 if (kind == "review" and fanout == 0) else KIND_TIE[kind]
        return (lane_rank(t), 0 if t.get("external_latency") else 1,
                -fanout, prio.get(t.get("priority", "unset"), 5), t.get("order", 99), tie)

    def scope_note(t: dict) -> str:
        if not t.get("unmet_partial"):
            return ""
        bits = "; ".join(f"the {d['part']} part waits on {'PR ' if d['kind'] == 'pr' else ''}#{d['id']}"
                         for d in t["unmet_partial"])
        return f" Start the rest now: {bits}."

    def held_note(t: dict) -> str:
        lane = t.get("lane_info") or {}
        return f" {lane['held_note']}" if lane.get("held") and lane.get("held_note") else ""

    def row_for(t: dict, kind: str, pr: dict | None, label: str, why: str, fanout: int) -> dict:
        if kind == "in_review":
            blockers = review_blockers(pr) + [b for b in t.get("extra_blockers", [])
                                              if b.get("severity") != "info"]
            action = f"Unstick PR #{pr['number']} for #{t['id']}: {label}"
            why = blockers[0]["text"] if blockers else "Awaiting merge."
        else:
            verb = "Start" if not t.get("merged_pr") else "Finish"
            action = f"{verb} #{t['id']}: {label}"
        return {"rank": rank(kind, fanout, t), "kind": kind, "ticket": t, "action": action,
                "why": why + scope_note(t) + held_note(t), "fanout": fanout}

    for t in model["tickets"]:
        if t["state"] in ("done", "blocked"):
            continue
        fanout = len(t.get("unblocks") or [])
        cos = co_owners(t)
        co_logins = {c["login"] for c in cos}
        hints = set(t.get("pr_hint") or [])

        # The owner's row reads the ticket's PRs except those a co-owner opened for
        # their own piece: Mert's PR #126 is #125's QPU side, and must not make
        # Burak's offline half read "in review", nor Burak's future PR Mert's.
        own = stuckest([p for p in t.get("all_prs") or []
                        if pr_author(p) not in co_logins or p["number"] in hints])
        label = t["short"] + (f" ({t['owner_part']})" if t.get("owner_part") else "")
        if own:
            by_person[t["owner"]].append(row_for(t, "in_review", own, label, "", fanout))
        else:
            by_person[t["owner"]].append(row_for(
                t, "ready", None, label,
                t.get("why_now") or "All stated upstream dependencies are met.", fanout))

        # A co-owner with a named piece gets their own row, with their own PR if
        # they have one. #84 is why the row exists at all: its brief was one
        # person's to write and another's to send, and listing only the owner
        # left the send unassigned, which is exactly how it went unsent.
        for co in cos:
            theirs = stuckest([p for p in t.get("all_prs") or [] if pr_author(p) == co["login"]])
            if theirs:
                by_person[co["login"]].append(row_for(t, "in_review", theirs, co["action"], "", fanout))
            else:
                by_person[co["login"]].append({
                    "rank": rank("ready", fanout, t), "kind": "ready", "ticket": t,
                    "action": f"{co['action']} (#{t['id']})",
                    "why": (co.get("why") or t.get("why_now") or "") + held_note(t),
                    "fanout": fanout,
                })

    # Reviews a specific person owes, on any PR. These are listed against the
    # reviewer because the ruleset makes them the only person who can clear it.
    seen: set[tuple[str, int]] = set()
    for t in model["tickets"]:
        for pr in t.get("all_prs") or []:
            for rev in pr.get("latest_reviews") or []:
                if rev["state"] != "CHANGES_REQUESTED":
                    continue
                fanout = len(t.get("unblocks") or [])
                looked = next((l for l in pr.get("looked_since") or []
                               if l["who"] == rev["who"]), None)
                why = (f"Your CHANGES_REQUESTED from {rev['at']} is the standing block. "
                       f"main's ruleset does not dismiss it on push, so only you can clear it.")
                if looked:
                    why += (f" You commented again on {looked['at']} without lifting it; "
                            f"a COMMENTED review does not dismiss a CHANGES_REQUESTED.")
                seen.add((rev["who"], pr["number"]))
                by_person[rev["who"]].append({
                    "rank": rank("review", fanout, t), "kind": "review", "ticket": t,
                    "action": f"Re-review PR #{pr['number']} (#{t['id']}: {t['short']})",
                    "why": why, "fanout": fanout,
                })

    # A PR that a ticket waits on (#122 on PR #121) is cleared by a review, so each
    # reviewer GitHub still has a pending request for gets a row saying what their
    # review releases. Read from the owed-answers model, which already holds every
    # pending request, so the two sections cannot disagree about who was asked.
    by_id = {t["id"]: t for t in model["tickets"]}
    for x in (model.get("owed") or {}).get("asks", []):
        held = model["holding_pr"].get(x["thread"]["number"]) if x["thread"]["kind"] == "PR" else None
        if x["kind"] not in ("review", "re-review") or not held or x["who"] in FORMER:
            continue
        n = x["thread"]["number"]
        if (x["who"], n) in seen:
            continue
        seen.add((x["who"], n))
        first = min((by_id[i] for i in held), key=lane_rank)
        what = "; ".join(f"#{i} ({by_id[i]['short']}) waits on it for "
                         + next(d["what"] for d in by_id[i]["unmet_hard"] + by_id[i]["unmet_partial"]
                                if d["kind"] == "pr" and d["id"] == n)
                         for i in held)
        by_person[x["who"]].append({
            "rank": rank("review", len(held), first), "kind": "review", "ticket": first,
            "action": f"{'Re-review' if x['kind'] == 're-review' else 'Review'} PR #{n}: it holds "
                      + ", ".join(f"#{i}" for i in held),
            "why": f"Requested since {x['since']}. {what[0].upper()}{what[1:]}.",
            "fanout": len(held), "unblocks_override": held,
        })

    # Planned work with no issue yet. It enters a queue only once the gate that
    # opens it is met, and only for the person the plan names to open it.
    for item in model.get("planned") or []:
        if not item.get("action") or not item.get("actor"):
            continue
        if item.get("opens_after") and item["opens_status"] != DONE:
            continue
        lane = next((l for l in model["lanes"] if l["id"] == item["lane"]), {})
        pseudo = {"id": None, "short": item["short"], "lane": item["lane"], "lane_info": lane,
                  "priority": "unset", "unblocks": [], "order": item.get("order", 99)}
        by_person[item["actor"]].append({
            "rank": rank("ready", 0, pseudo), "kind": "ready", "ticket": pseudo,
            "action": item["action"], "why": item["why"], "fanout": 0,
        })

    for person in by_person:
        by_person[person].sort(key=lambda a: a["rank"])
    return dict(by_person)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def e(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def phase_facts(plan: dict, model: dict, ctx: dict) -> dict:
    """The phase's calendar and plan facts every rendering states, all from live reads.

    The phase-4 plan dates nothing but the phase start and the milestone (§6: the
    gates are "ordered, not dated"), so there is no "calendar burned" figure and no
    even-pace line here: comparing gates met with days elapsed would assert a pace
    the plan explicitly declines to set. The milestone's due date is read from
    GitHub, so moving it there moves it here.
    """
    p = plan["phase"]
    today = plan_today()
    ms = ctx["milestones"].get(p["milestone"]) or {}
    due = ms.get("due") or None
    since_start = days_between(p["start"], today)
    if since_start < 0:
        when = f"starts {p['start']} (in {-since_start} {'day' if since_start == -1 else 'days'})"
    else:
        when = f"day {since_start + 1} since {p['start']}"
    plan_pr = model.get("plan_pr") or {}
    on_main = ctx["paths"].get(p["plan_doc"])
    where = (f"plan of {p['plan_written']} at `{p['plan_sha']}` on `{p['plan_ref']}`"
             + (", on main" if on_main else
                (f", PR #{plan_pr['number']} {plan_pr['state'].lower()}, not on main yet"
                 if plan_pr else ", not on main yet")))
    return {
        "today": today, "when": when, "due": due,
        "days_to_due": days_between(today, due) if due else None,
        "ms": ms, "ms_no": p["milestone"], "where": where, "on_main": on_main,
    }


def gate_counts(model: dict) -> tuple[int, int, int, int]:
    conds = [c for g in model["gates"] for c in g["conditions"]]
    return (sum(1 for g in model["gates"] if g["status"] == DONE), len(model["gates"]),
            sum(1 for c in conds if c["status"] == DONE), len(conds))


def due_line(f: dict) -> str:
    if not f["due"]:
        return f"milestone {f['ms_no']} has no due date on GitHub"
    return (f"milestone {f['ms_no']} due {f['due']} ({f['days_to_due']} days), "
            f"{f['ms'].get('open', '?')} open and {f['ms'].get('closed', '?')} closed")


ITEM_MARK = {"done": DONE, "in_review": PARTIAL, "ready": NOT_DONE, "blocked": NOT_DONE}


def item_detail(t: dict, model: dict, plan: dict) -> str:
    """One lane item's live state, as the words after its name."""
    if t["state"] == "done":
        if t.get("delivered_open"):
            pr = t.get("delivered_pr") or {}
            asks = [x for x in model["owed"]["asks"]
                    if x["thread"]["kind"] == "issue" and x["thread"]["number"] == t["id"]]
            tail = ""
            if asks:
                names = ", ".join(plan["people"].get(w, {}).get("name", w) for w in sorted({x["who"] for x in asks}))
                tail = f" with {len(asks)} unticked {'ask' if len(asks) == 1 else 'asks'} ({names})"
            return (f"delivered by PR #{pr.get('number', t['done_by']['id'])} on "
                    f"{(pr.get('mergedAt') or '')[:10]}; the issue is still open{tail}")
        return "closed"
    if t["state"] == "in_review":
        return f"in review, PR #{t['pr']['number']}"
    if t["state"] == "blocked":
        return "waits on " + ", ".join(
            (f"PR #{d['id']}" if d["kind"] == "pr" else
             f"{d['id']} gate" if d["kind"] == "gate" else f"#{d['id']}") for d in t["unmet_hard"])
    return "ready to start" if not t.get("merged_pr") else "ready to finish"


def planned_detail(x: dict) -> str:
    if not x.get("opens_after"):
        return "no issue yet"
    if x["opens_status"] == DONE:
        return f"opens after {x['opens_after']}, which is met: its issue can be opened"
    return f"opens after {x['opens_after']}, not met yet"


def lane_items(model: dict, lane_id: str) -> list[tuple[str, dict]]:
    """A lane's tickets and planned items, in the plan's order."""
    rows = [("ticket", t) for t in model["tickets"] if t.get("lane") == lane_id]
    rows += [("planned", x) for x in model["planned"] if x["lane"] == lane_id]
    return sorted(rows, key=lambda r: r[1].get("order", 99))


def risk_now(r: dict, model: dict) -> str:
    live = model.get("risk_live", {}).get(r["text"])
    return live or ""


def render_markdown(plan: dict, model: dict, queue: dict, main: dict, now: str,
                    history: list[dict]) -> str:
    L: list[str] = []
    a = L.append
    f = phase_facts(plan, model, main)
    a(f"# {plan['phase']['name']}: {plan['phase']['goal']}\n")
    a(f"_Generated {now} · main at `{main['sha']}` ({main['date']}) · {f['when']} · "
      f"{due_line(f)}_\n")
    a(f"_Read against the {f['where']}. Gates are ordered, not dated (plan §6)._\n")

    if model["warnings"]:
        a("\n## Plan warnings\n")
        for w in model["warnings"]:
            a(f"- {w}")

    a("\n## Lanes and gates\n")
    for lane in model["lanes"]:
        a(f"\n### Lane {lane['id']} · {lane['name']}\n")
        a(f"_{lane.get('rank_note', '')}_\n")
        for gid in lane["gate_ids"]:
            g = next(x for x in model["gates"] if x["id"] == gid)
            nxt = " · **next**" if lane["next"] == gid else ""
            a(f"- {MARK[g['status']]} **{g['id']}** {g['name']}: {g['text']} "
              f"({g['done']}/{g['total']}){nxt}")
            for c in g["conditions"]:
                a(f"  - {MARK[c['status']]} {c['text']}")
                if c.get("note"):
                    a(f"    - _{c['note']}_")
        a("")
        for kind, x in lane_items(model, lane["id"]):
            if kind == "ticket":
                a(f"{x.get('order', '')}. {MARK[ITEM_MARK[x['state']]]} #{x['id']} {x['short']} "
                  f"(@{x['owner']}): {item_detail(x, model, plan)}")
            else:
                a(f"{x.get('order', '')}. {MARK[UNKNOWN]} new: {x['short']} "
                  f"({', '.join('@' + o for o in x['owners'])}): {planned_detail(x)}. {x['why']}")

    a("\n## Work on this right now\n")
    for login in TEAM_ORDER + [k for k in queue if k not in TEAM_ORDER]:
        actions = queue.get(login, [])
        who = plan["people"].get(login, {}).get("name", login)
        a(f"\n**{who}** (@{login})\n")
        if not actions:
            a("Nothing ready and nothing owed. Available for reviews.")
        for act in actions[:4]:
            a(f"1. {act['action']}")
            a(f"   - {act['why']}")

    a("\n## Waiting on an answer\n")
    a("_Review requests not yet answered with a review, and unticked checkboxes that start "
      "with the person (`- [ ] @login does X`), on every open issue and PR. Oldest first; "
      "\"or earlier\" marks a post edited after it was written, so the wait shown is the "
      "shortest it can be._\n")
    for warn in model["owed"]["truncated"]:
        a(f"- **Not fully read, asks may be missing:** {warn}")
    owed = owed_by_person(model["owed"])
    if not owed:
        a("\nNobody owes an answer on any open issue or PR.")
    for login in [*TEAM_ORDER, *[k for k in owed if k not in TEAM_ORDER]]:
        xs = owed.get(login)
        if not xs:
            continue
        who = plan["people"].get(login, {}).get("name", login)
        left = " · **left the team: reassign these**" if login in FORMER else ""
        a(f"\n**{who}** (@{login}), {len(xs)} owed{left}\n")
        for x in xs:
            a(f"- {ask_line(x)}")

    a("\n## Not blocked by anything upstream, so what is holding them?\n")
    for t in model["tickets"]:
        if t["state"] in ("done", "blocked") or not t["blockers"]:
            continue
        a(f"\n**#{t['id']}: {t['short']}** (@{t['owner']})\n")
        for b in sorted(t["blockers"], key=lambda x: SEV_RANK.get(x["severity"], 9)):
            a(f"- [{b['severity']}] {b['text']}")

    a("\n## Blocked upstream\n")
    blocked = [t for t in model["tickets"] if t["state"] == "blocked"]
    if not blocked:
        a("Nothing is blocked upstream.")
    for t in blocked:
        deps = "; ".join(
            (f"PR #{d['id']} ({d['what']})" if d["kind"] == "pr" else
             f"{d['id']} gate ({d['what']})" if d["kind"] == "gate" else
             f"#{d['id']} ({d['what']})") for d in t["unmet_hard"])
        a(f"- **#{t['id']}** {t['short']} (@{t['owner']}), waiting on {deps}")

    a("\n## Parked\n")
    for x in model["parked"]:
        where = f"{x['state'].lower()}, " + (f"milestone {x['milestone']}" if x["milestone"] else "no milestone")
        a(f"- **#{x['id']}** {x['title']} ({where}): {x['reason']}")

    a("\n## Day by day\n")
    if len(history) < 2:
        a(f"\nOnly {len(history)} {'day' if len(history) == 1 else 'days'} recorded so far. "
          f"The routine adds one per day.\n")
    else:
        a("\n| Date | Gates | Conditions | Ready | In review | Blocked | What moved |")
        a("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
        for i, h in enumerate(reversed(history)):
            j = len(history) - 1 - i
            ev = day_events(history[j - 1], h, plan) if j > 0 else ["first record"]
            c = h.get("counts", {})
            a(f"| {h['date']} | {h['gates_done']}/{h['gates_total']} "
              f"| {h['conditions_done']}/{h['conditions_total']} | {c.get('ready', 0)} "
              f"| {c.get('in_review', 0)} | {c.get('blocked', 0)} | "
              f"{'; '.join(ev) if ev else 'nothing moved'} |")

    a("\n## ADR ledger\n")
    for w in plan["adr_watch"]:
        cur = main["adr"].get(w["id"])
        name = main["adr_title"].get(w["id"]) or w.get("name", "")
        mk = MARK[DONE] if cur and adr_met(cur, w["want"]) else MARK[NOT_DONE]
        a(f"- {mk} **{w['id']}** {name}, on main: _{cur or 'not in the ledger'}_ · needs: {w['gate']}")

    a("\n## Risks the plan named\n")
    for r in plan["risks"]:
        now_txt = risk_now(r, model)
        a(f"- {r['text']}" + (f" _Now: {now_txt}_" if now_txt else ""))
    return "\n".join(L) + "\n"


def render_run_report(plan: dict, model: dict, queue: dict, main: dict, now: str,
                      history: list[dict]) -> str:
    """The report a run is entitled to make, written by the run itself.

    This exists so that reporting is not a thing anyone can do from memory or
    from leftover files. The daily routine's job is reduced to relaying this
    text; it composes no summary of its own. `update.sh` stamps a run token on
    top and `report.sh` refuses to print the file once it is stale, so a report
    that was never generated by an actual run cannot be produced at all.
    """
    f = phase_facts(plan, model, main)
    g_done, g_total, c_done, c_total = gate_counts(model)

    L: list[str] = []
    a = L.append
    a(f"**{plan['phase']['name']}: {plan['phase']['goal']}** · {f['when']} · {due_line(f)}.")
    nxt = ", ".join(f"{l['next']} (lane {l['id']})" for l in model["lanes"] if l["next"])
    a(f"**{g_done}/{g_total} gates met** ({c_done}/{c_total} conditions)"
      + (f". Next: {nxt}." if nxt else ". Every gate is met."))
    a("")

    if len(history) >= 2:
        ev = day_events(history[-2], history[-1], plan)
        a(f"**Since {history[-2]['date']}:** "
          + ("; ".join(ev) if ev else "nothing moved") + ".")
    else:
        a(f"**Day by day:** {len(history)} {'record' if len(history) == 1 else 'records'} so far, so there is nothing to "
          f"compare against yet.")
    a("")

    # Needs attention, computed fresh rather than remembered. Gates carry no dates,
    # so nothing here is "overdue"; what can need attention is a plan warning, a
    # PR that cannot merge, or ready work that others wait on.
    attention: list[str] = list(model["warnings"])
    seen: set[int] = set()
    for t in model["tickets"]:
        for pr in t.get("all_prs") or []:
            if pr["number"] in seen or pr.get("mergeable") != "CONFLICTING":
                continue
            seen.add(pr["number"])
            attention.append(f"PR #{pr['number']} (#{t['id']}) conflicts with main, so its "
                             f"checks are not evidence and it cannot merge")
    for t in model["tickets"]:
        if t["state"] == "ready" and t.get("unblocks"):
            who = plan["people"].get(t["owner"], {}).get("name", t["owner"])
            attention.append(f"#{t['id']} is ready and holds up "
                             + ", ".join(f"#{x}" for x in t["unblocks"])
                             + f" ({who})")
    if attention:
        a("**Needs attention**")
        for x in attention:
            a(f"- {x}")
    else:
        a("**Needs attention:** nothing.")
    a("")

    a("**Next action per person**")
    for login in TEAM_ORDER + [k for k in queue if k not in TEAM_ORDER]:
        who = plan["people"].get(login, {}).get("name", login)
        acts = queue.get(login, [])
        a(f"- {who}: " + (acts[0]["action"] if acts
                          else "nothing ready and nothing owed"))
    a("")

    # The oldest ask per person, because that is the one most likely forgotten.
    owed = owed_by_person(model["owed"])
    a("**Waiting on an answer**")
    for warn in model["owed"]["truncated"]:
        a(f"- Not fully read, asks may be missing: {warn}")
    for login in TEAM_ORDER + [k for k in owed if k not in TEAM_ORDER]:
        xs = owed.get(login, [])
        who = plan["people"].get(login, {}).get("name", login)
        if login in FORMER:
            who += " (left the team: reassign)"
        a(f"- {who}: " + (f"{len(xs)}, oldest: {ask_line(xs[0])}" if xs else "nothing owed"))
    return "\n".join(L) + "\n"


README_START = "<!-- DASHBOARD:START -->"
README_END = "<!-- DASHBOARD:END -->"


def render_readme_block(plan: dict, model: dict, queue: dict, main: dict, now: str,
                        history: list[dict]) -> str:
    """The at-a-glance status GitHub shows on the branch page.

    Deliberately not the whole of STATUS.md. Someone landing on the branch wants
    three things before they decide whether to open anything: where the phase
    stands, which gates are met, and what they personally should pick up.
    Anything more and the README stops being a front page and becomes a second
    copy of the board, which then has to be kept honest twice.
    """
    f = phase_facts(plan, model, main)
    g_done, g_total, c_done, c_total = gate_counts(model)
    counts: dict[str, int] = defaultdict(int)
    for t in model["tickets"]:
        counts[t["state"]] += 1

    L: list[str] = [README_START]
    a = L.append
    a(f"<!-- Generated by generate.py at {now}. Do not edit inside these markers. -->")
    a("")
    a(f"**{plan['phase']['name']}: {plan['phase']['goal']}** · {f['when']} · {due_line(f)} · "
      f"**{g_done}/{g_total} gates met** · {counts['ready']} ready · "
      f"{counts['in_review']} in review · {counts['blocked']} blocked")
    a("")
    a(f"Gates are ordered, not dated (plan §6), so there is no pace figure. Read at "
      f"`{main['sha']}` on `main`, against the {f['where']}.")
    a("")
    if model["warnings"]:
        a(f"**{len(model['warnings'])} plan "
          f"{'warning' if len(model['warnings']) == 1 else 'warnings'}:** "
          f"[see STATUS.md](STATUS.md#plan-warnings)")
        a("")
    a("| | Gate | Lane | Conditions met |")
    a("| --- | --- | --- | ---: |")
    nexts = {l["next"] for l in model["lanes"]}
    for g in model["gates"]:
        a(f"| {MARK[g['status']]} | **{g['id']}** {g['name']}{' (next)' if g['id'] in nexts else ''} "
          f"| {g['lane']} | {g['done']}/{g['total']} |")
    a("")
    a("### Do this next")
    a("")
    a("| Who | Next action | Why |")
    a("| --- | --- | --- |")
    for login in TEAM_ORDER + [k for k in queue if k not in TEAM_ORDER]:
        acts = queue.get(login, [])
        who = plan["people"].get(login, {}).get("name", login)
        if not acts:
            a(f"| {who} | Nothing ready and nothing owed | Available for reviews |")
            continue
        top = acts[0]
        why = top["why"]
        why = why[:158].rstrip() + "..." if len(why) > 160 else why
        a(f"| {who} | {top['action']} | {why} |")
    a("")
    owed = owed_by_person(model["owed"])
    tally = [f"{plan['people'].get(l, {}).get('name', l)} {len(owed[l])} "
             f"(oldest since {owed[l][0]['since'] or 'unknown'})"
             for l in [*TEAM_ORDER, *[k for k in owed if k not in TEAM_ORDER]] if owed.get(l)]
    a("**Waiting on an answer:** " + ("; ".join(tally) if tally else "nobody owes one")
      + ". [Who owes what](STATUS.md#waiting-on-an-answer)"
      + (" · **some threads were not fully read**" if model["owed"]["truncated"] else ""))
    a("")
    if len(history) >= 2:
        prev, cur = history[-2], history[-1]
        ev = day_events(prev, cur, plan)
        a(f"**Since {prev['date']}:** " + ("; ".join(ev) if ev else "nothing moved") + ".")
    else:
        a(f"**Day by day:** {len(history)} {'record' if len(history) == 1 else 'records'} so far. The routine adds one per day.")
    a("")
    art = plan["phase"].get("artifact_url")
    a("Full board: [STATUS.md](STATUS.md)" + (f" · [live page]({art})" if art else "")
      + " · [day by day](STATUS.md#day-by-day)")
    a(README_END)
    return "\n".join(L)


def splice_readme(block: str) -> bool:
    """Replace the generated block in README.md. Returns True if it changed.

    Only the region between the markers is touched, so the hand-written half of
    the README is never at risk from a generator run. A missing marker pair is a
    hard error rather than a silent append: appending would put a second status
    block below the first, and the stale one would still read as current.
    """
    path = HERE / "README.md"
    text = path.read_text(encoding="utf-8")
    i, j = text.find(README_START), text.find(README_END)
    if i == -1 or j == -1 or j < i:
        raise SystemExit("README.md is missing its DASHBOARD markers; refusing to guess "
                         "where the generated block belongs.")
    new = text[:i] + block + text[j + len(README_END):]
    if new == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    return True


def render_html(plan: dict, model: dict, queue: dict, main: dict, now: str,
                history: list[dict]) -> str:
    """Render the dashboard. Self-contained except the two Plex faces from Google Fonts."""
    p = plan["phase"]
    f = phase_facts(plan, model, main)
    g_done, g_total, c_done, c_total = gate_counts(model)

    O: list[str] = []
    a = O.append

    a(f"<title>SuperconducTED {e(p['name'])}</title>")
    # IBM Plex is not a neutral pick: this project reads IBM Quantum calibration
    # snapshots all day, and Plex is IBM's own type. Mono carries every figure
    # that has to line up: ticket numbers, SHAs, timestamps, counts.
    a('<link rel="preconnect" href="https://fonts.googleapis.com">')
    a('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
      'family=IBM+Plex+Mono:wght@400;500;600&'
      'family=IBM+Plex+Sans:wght@400;450;500;600;700&display=swap">')
    a("<style>")
    a("""
/* Palette: SuperconducTED Cryostat, the chart roles in SuperconducTED/.github
   brand/figures/roles.json at 06f1959. The brand's one colour rule is that the
   accent marks a range (the engine's interval) and nothing else; nothing on this
   page is a range, so the page has no accent token at all. Ink carries the data
   (progress, the burn-up), links and focus. --ink-2 and --sunk are ink laid over
   the ground (87/82 and 7 percent), the brand's own way of deriving neutrals;
   --muted, --axis and --line are its text_secondary, axis and grid. Page and
   cards share the ground because the series colours (--s1..--s6, per-person
   identity, fixed order) clear 3:1 on the ground exactly. The status colours
   (--ok, --warn, --bad) are this page's own: the brand defines none yet. */
:root{
  --bg:#EEF3F5; --panel:#EEF3F5; --sunk:#DEE4E6;
  --ink:#0A1B24; --ink-2:#28373F; --muted:#45535A; --line:#D3D9DC; --axis:#838D93;
  --ok:#146b3a; --ok-bg:#e2f2e8;
  --warn:#8f5406; --warn-bg:#faeedd;
  --bad:#a80f37; --bad-bg:#fbe6ec;
  --idle:#838D93; --idle-bg:#D3D9DC;
  --s1:#D36992; --s2:#008300; --s3:#4A3AA7; --s4:#BD7F00; --s5:#2D7BD9; --s6:#E6632F;
  --shadow:0 1px 1px rgba(10,27,36,.03), 0 12px 28px -20px rgba(10,27,36,.28);
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0A1B24; --panel:#0A1B24; --sunk:#1A2A33;
  --ink:#EEF3F5; --ink-2:#C5CCCF; --muted:#9CA5AA; --line:#25353D; --axis:#5A676D;
  --ok:#59c584; --ok-bg:#10291b;
  --warn:#d9a24f; --warn-bg:#2a2011;
  --bad:#f0708f; --bad-bg:#2c1219;
  --idle:#5A676D; --idle-bg:#25353D;
  --s1:#D55181; --s2:#008300; --s3:#9085E9; --s4:#C98500; --s5:#3987E5; --s6:#D95926;
  --shadow:0 1px 1px rgba(0,0,0,.4), 0 12px 28px -20px rgba(0,0,0,.8);
}}
:root[data-theme="dark"]{
  --bg:#0A1B24; --panel:#0A1B24; --sunk:#1A2A33;
  --ink:#EEF3F5; --ink-2:#C5CCCF; --muted:#9CA5AA; --line:#25353D; --axis:#5A676D;
  --ok:#59c584; --ok-bg:#10291b;
  --warn:#d9a24f; --warn-bg:#2a2011;
  --bad:#f0708f; --bad-bg:#2c1219;
  --idle:#5A676D; --idle-bg:#25353D;
  --s1:#D55181; --s2:#008300; --s3:#9085E9; --s4:#C98500; --s5:#3987E5; --s6:#D95926;
  --shadow:0 1px 1px rgba(0,0,0,.4), 0 12px 28px -20px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.62;-webkit-font-smoothing:antialiased;padding:0 0 88px}
.wrap{max-width:1200px;margin:0 auto;padding:0 26px}
a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--axis);
  text-underline-offset:2px}
a:hover{text-decoration-color:var(--ink)}
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--ink);outline-offset:2px;border-radius:3px}
code,.mono,.num,td.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
h1,h2,h3{text-wrap:balance}

/* ---- masthead: an instrument readout, not a marketing hero ---- */
header.hero{padding:40px 0 0}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--muted)}
h1{font-size:33px;line-height:1.14;letter-spacing:-.02em;margin:10px 0 5px;font-weight:600}
h1 .goal{color:var(--muted);font-weight:400}
.sub{color:var(--muted);font-size:13px;line-height:1.55}
.readout{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));
  gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;
  overflow:hidden;margin:26px 0 8px}
.readout > div{background:var(--panel);padding:15px 17px}
.readout .v{font-family:var(--mono);font-size:27px;font-weight:500;line-height:1;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.readout .v span{color:var(--muted);font-size:17px}
.readout .k{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);font-weight:600;margin-top:9px}
.readout .v.alarm{color:var(--bad)}
.bar{height:4px;border-radius:99px;background:var(--sunk);overflow:hidden;margin-top:12px}
.bar > i{display:block;height:100%;background:var(--ink);border-radius:99px}
.calendar{padding:15px 17px;background:var(--panel);grid-column:1/-1}

/* ---- section headings: hairline rule, no card ---- */
h2{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
  font-weight:600;margin:46px 0 6px;padding-bottom:10px;border-bottom:1px solid var(--line)}
.lede{color:var(--muted);font-size:13px;margin:0 0 18px;max-width:74ch;line-height:1.6}

/* ---- cards, spent only where an object really is separate ---- */
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;
  box-shadow:var(--shadow);padding:19px 21px}
.grid{display:grid;gap:13px}
@media(min-width:920px){.grid.two{grid-template-columns:1fr 1fr}}

/* ---- per-person action queue: the operating surface ---- */
.person{border-top:3px solid var(--pc,var(--idle))}
.person h3{margin:0;font-size:16px;font-weight:600;letter-spacing:-.008em}
.person .role{color:var(--muted);font-size:12px;margin:1px 0 13px;font-family:var(--mono)}
ol.acts{list-style:none;counter-reset:a;margin:0;padding:0;display:flex;
  flex-direction:column}
ol.acts li{counter-increment:a;position:relative;padding:12px 0 12px 30px;
  border-top:1px solid var(--line)}
ol.acts li:first-child{border-top:0;padding-top:2px}
ol.acts li::before{content:counter(a);position:absolute;left:0;top:13px;
  font-family:var(--mono);font-size:11px;font-weight:600;color:var(--muted)}
ol.acts li:first-child::before{top:3px}
ol.acts .act{font-weight:550;font-size:14.5px;display:block;margin-bottom:3px;
  letter-spacing:-.005em}
ol.acts .why{color:var(--ink-2);font-size:12.8px;line-height:1.55;display:block}
ol.acts .tags{margin-top:8px;display:flex;gap:5px;flex-wrap:wrap}

/* ---- milestone blocks ---- */
.ms{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start}
.ms h3{margin:0 0 2px;font-size:16px;font-weight:600;letter-spacing:-.008em}
.ms h3 .id{font-family:var(--mono);color:var(--muted);margin-right:7px}
.ms .when{text-align:right;white-space:nowrap}
.ms .when .d{font-family:var(--mono);font-size:14px;font-weight:500}
.ms .prog{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:3px}
.gates{list-style:none;margin:15px 0 0;padding:0;grid-column:1/-1}
.gates li{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:8px 0;
  border-top:1px solid var(--line);font-size:13.8px;line-height:1.5}
.gates .note{display:block;color:var(--muted);font-size:12.3px;margin-top:3px;line-height:1.5}
.gates li.cond{padding-left:26px;font-size:13.2px}
.lane{margin-top:13px}
.lane h3{margin:0 0 2px;font-size:16px;font-weight:600;letter-spacing:-.008em}
.lane h3 .id{font-family:var(--mono);color:var(--muted);margin-right:7px}
ol.items{list-style:none;margin:16px 0 0;padding:0}
ol.items li{display:grid;grid-template-columns:22px auto 1fr;gap:10px;padding:8px 0;
  border-top:1px solid var(--line);font-size:13.6px;line-height:1.5}
ol.items .ord{font-family:var(--mono);font-size:11px;color:var(--muted);padding-top:2px}
ol.items .note{display:block;color:var(--muted);font-size:12.3px;margin-top:2px;line-height:1.5}
.warnbox{border-left:3px solid var(--warn);padding:10px 14px;margin:18px 0 0;
  background:var(--warn-bg);color:var(--ink);font-size:13.2px;line-height:1.55}
.warnbox ul{margin:6px 0 0;padding-left:18px}

/* ---- pills: state at a glance ---- */
.pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;
  font-weight:600;letter-spacing:.02em;white-space:nowrap;font-family:var(--mono)}
.pill.ok{background:var(--ok-bg);color:var(--ok)}
.pill.warn{background:var(--warn-bg);color:var(--warn)}
.pill.bad{background:var(--bad-bg);color:var(--bad)}
.pill.idle{background:var(--idle-bg);color:var(--muted)}
.pill.ready{background:none;color:var(--ink);box-shadow:inset 0 0 0 1px var(--axis)}
a.pill.owes{text-decoration:none;margin:-5px 0 13px}

/* ---- who owes an answer: one group row per person, then their asks ---- */
tr.grp td{padding-top:18px;font-size:14px}
tr:first-child + tr.grp td{padding-top:4px}
.pdot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;
  vertical-align:baseline}
.ask{font-size:13.6px;line-height:1.5}

/* ---- tables: hairlines only, no card chrome competing with the data ---- */
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13.4px}
th{text-align:left;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);font-weight:600;padding:0 14px 9px 0;
  border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:12px 14px 12px 0;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
td.num{white-space:nowrap;font-size:13px}
td.num .cap{display:block;white-space:normal;font-family:var(--sans);
  font-size:12.3px;color:var(--muted);margin-top:2px;line-height:1.45;max-width:24ch}
/* Severity as form, not only as colour: a stripe on the row's first cell. */
tr.sev-critical td:first-child{box-shadow:inset 3px 0 0 var(--bad);padding-left:11px}
tr.sev-high td:first-child{box-shadow:inset 3px 0 0 var(--warn);padding-left:11px}
tr.sev-medium td:first-child{box-shadow:inset 3px 0 0 var(--idle);padding-left:11px}
.blockers{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.blockers li{font-size:12.9px;line-height:1.5;display:grid;
  grid-template-columns:auto 1fr;gap:9px;max-width:62ch}
.dot{width:6px;height:6px;border-radius:50%;margin-top:6px}
.dot.critical{background:var(--bad)} .dot.high{background:var(--warn)}
.dot.medium,.dot.low{background:var(--idle)}

/* ---- risks ---- */
.risk{display:grid;grid-template-columns:92px 1fr;gap:16px;padding:14px 0;
  border-top:1px solid var(--line)}
.risk:first-child{border-top:0;padding-top:0}
.risk .what{font-weight:550;font-size:13.8px;margin-bottom:4px;line-height:1.5}
.risk .ev{color:var(--muted);font-size:12.8px;line-height:1.55}
.risk .ev b{color:var(--ink-2);font-weight:600}

footer{margin-top:50px;padding-top:20px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12.3px;line-height:1.7}
.empty{color:var(--muted);font-size:13px}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
""")
    a("</style>")

    # ---- hero
    a('<div class="wrap"><header class="hero">')
    a(f'<div class="eyebrow">{e(p["repo"])}</div>')
    a(f'<h1>{e(p["name"])} <span class="goal">: {e(p["goal"])}</span></h1>')
    plan_pr = model.get("plan_pr")
    plan_where = (f'plan of {e(p["plan_written"])} at <code>{e(p["plan_sha"])}</code> on '
                  f'<code>{e(p["plan_ref"])}</code>')
    if f["on_main"]:
        plan_where += ", on main"
    elif plan_pr:
        plan_where += (f', <a href="{e(plan_pr["url"])}">PR #{plan_pr["number"]}</a> '
                       f'{e(plan_pr["state"].lower())}, not on main yet')
    else:
        plan_where += ", not on main yet"
    a(f'<div class="sub">Generated {e(now)} from live GitHub state · '
      f'main at <code>{e(main["sha"])}</code> ({e(main["date"])}) · {plan_where}</div>')
    ready_n = sum(1 for t in model["tickets"] if t["state"] == "ready")
    blocked_n = sum(1 for t in model["tickets"] if t["state"] == "blocked")
    review_n = sum(1 for t in model["tickets"] if t["state"] == "in_review")

    # The readout states where the phase is without inventing a pace. The plan
    # orders its gates and dates none of them (§6), so gates met sit beside the
    # milestone's live due date and issue counts, never against a calendar line.
    ms = f["ms"]
    ms_total = (ms.get("open") or 0) + (ms.get("closed") or 0)
    a('<div class="readout">')
    a(f'<div><div class="v">{f["days_to_due"] if f["due"] else "?"}</div>'
      f'<div class="k">days to {e(f["due"] or "no due date")}</div></div>')
    a(f'<div><div class="v">{g_done}<span>/{g_total}</span></div>'
      f'<div class="k">gates met</div></div>')
    a(f'<div><div class="v">{c_done}<span>/{c_total}</span></div>'
      f'<div class="k">conditions met</div></div>')
    a(f'<div><div class="v">{ready_n}</div><div class="k">ready to start</div></div>')
    a(f'<div><div class="v">{review_n}</div><div class="k">in review</div></div>')
    a(f'<div><div class="v">{blocked_n}</div><div class="k">blocked upstream</div></div>')
    a(f'<div><div class="v">{ms.get("closed", "?")}<span>/{ms_total}</span></div>'
      f'<div class="k">milestone {f["ms_no"]} closed</div></div>')
    nxt = " · ".join(
        (f'lane {e(l["id"])}: <b class="mono">{e(l["next"])}</b>' if l["next"]
         else f'lane {e(l["id"])}: every gate met') for l in model["lanes"])
    a('<div class="calendar">')
    a(f'<div class="sub">{e(p["name"])} {e(f["when"])}. Next gate per lane: {nxt}. '
      f'Gates are ordered, not dated (plan §6), so this page shows no pace figure.</div>')
    a('</div>')
    a('</div></header>')

    if model["warnings"]:
        a('<div class="warnbox"><b>Plan warnings.</b> plan.json and GitHub disagree, or '
          'plan.json may be stale. Each line says what to check.<ul>')
        for w in model["warnings"]:
            a(f'<li>{e(w)}</li>')
        a('</ul></div>')

    # ---- action queue
    a('<h2>Work on this right now</h2>')
    a('<div class="lede">Ranked per person, lane first, in the order the plan sets (each '
      'lane\'s rule is under Lanes and gates); then work that unblocks the most other tickets, '
      'reviews only that person can clear, and the live priority label. A ticket waiting on an '
      'upstream dependency is never listed against its own owner; it is listed against whoever '
      'can clear the blocker.</div>')
    a('<div class="grid two">')
    owed = owed_by_person(model["owed"])
    for login in TEAM_ORDER + [k for k in queue if k not in TEAM_ORDER]:
        acts = queue.get(login, [])
        meta = plan["people"].get(login, {"name": login, "role": "", "colour": "idle"})
        a(f'<div class="card person" style="--pc:{e(person_colour(meta["colour"]))}">')
        a(f'<h3>{e(meta["name"])}</h3><div class="role">@{e(login)} · {e(meta["role"])}</div>')
        if owed.get(login):
            xs = owed[login]
            a(f'<a class="pill warn owes" href="#owed-{e(login)}">owes {len(xs)} '
              f'{"answer" if len(xs) == 1 else "answers"} · oldest since '
              f'{e(xs[0]["since"] or "unknown")}</a>')
        if not acts:
            a('<div class="empty">Nothing ready and nothing owed. Available for reviews.</div>')
        else:
            a('<ol class="acts">')
            for act in acts[:4]:
                t = act["ticket"]
                lane = t.get("lane_info") or {}
                a('<li>')
                a(f'<span class="act">{e(act["action"])}</span>')
                a(f'<span class="why">{e(act["why"])}</span>')
                a('<span class="tags">')
                kind_pill = {"ready": ("ready", "ready to start"),
                             "review": ("bad", "you are the blocker"),
                             "in_review": ("warn", "in review")}[act["kind"]]
                a(f'<span class="pill {kind_pill[0]}">{kind_pill[1]}</span>')
                if act["fanout"]:
                    unl = ", ".join(f"#{x}" for x in (act.get("unblocks_override")
                                                       or t.get("unblocks") or []))
                    a(f'<span class="pill idle">unblocks {e(unl)}</span>')
                if t.get("priority") not in (None, "unset"):
                    a(f'<span class="pill idle">{e(t["priority"])}</span>')
                a(f'<span class="pill idle">lane {e(t.get("lane"))}</span>')
                if lane.get("held"):
                    a(f'<span class="pill idle">after {e(lane["rank_after"]["gate"])}</span>')
                a('</span></li>')
            a('</ol>')
        a('</div>')
    a('</div>')

    # ---- who owes an answer
    a('<h2 id="owed">Waiting on an answer</h2>')
    a('<div class="lede">Everything a teammate has been asked for on an open issue or PR '
      'and has not delivered yet, oldest first. Two sources, both closed by GitHub itself: '
      'a <b>review request</b> not yet answered with a review, and an <b>unticked checkbox '
      'that starts with the person</b>, such as <code>- [ ] @BurakOztekin runs the desktop '
      'runbook</code>, which stays here until someone ticks it. A plain @mention elsewhere '
      'in a sentence is not tracked. "Or earlier" marks a post edited after it was written: '
      'the box may have arrived with the edit, so the wait shown is the shortest it can be.</div>')
    for warn in model["owed"]["truncated"]:
        a(f'<div class="lede" style="color:var(--bad)"><b>Not fully read, so asks may be '
          f'missing:</b> {e(warn)}.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>What they were asked</th><th>Where</th><th>Waiting since</th></tr>')
    if not owed:
        a('<tr><td colspan="3" class="empty">Nobody owes an answer on any open issue or PR.</td></tr>')
    for login in TEAM_ORDER + [k for k in owed if k not in TEAM_ORDER]:
        xs = owed.get(login)
        if not xs:
            continue
        meta = plan["people"].get(login, {"name": login, "colour": "idle"})
        left = (' <span class="pill bad">left the team: reassign</span>'
                if login in FORMER else "")
        a(f'<tr class="grp" id="owed-{e(login)}"><td colspan="3">'
          f'<span class="pdot" style="background:{e(person_colour(meta["colour"]))}"></span>'
          f'<b>{e(meta["name"])}</b> <span class="sub">@{e(login)} · owes {len(xs)}</span>'
          f'{left}</td></tr>')
        for x in xs:
            parts, th = ask_parts(x), x["thread"]
            pill = {"review": "warn", "re-review": "bad", "checkbox": "idle"}[x["kind"]]
            a(f'<tr><td><span class="pill {pill}">{e(ASK_KIND[x["kind"]])}</span> '
              f'<span class="ask">{e(parts["what"])}</span>'
              f'<div class="sub">{e(parts["by"])}</div></td>')
            a(f'<td class="num"><a href="{e(x["url"])}">{e(th["kind"])} #{th["number"]}</a>'
              f'<span class="cap">{e(clip(th["title"], 64))}</span></td>')
            a(f'<td class="num">{e(x["since"] or "unknown")}'
              f'<span class="cap">{e(parts["age"])}'
              f'{" · posted " + e(x["posted"]) if x["lower_bound"] else ""}<br>'
              f'{e(parts["seen"])}</span></td></tr>')
    a('</table></div></div>')

    # ---- lanes and gates
    a('<h2>Lanes and gates</h2>')
    a('<div class="lede">Every gate and condition is the plan\'s own wording. ✅ verified against '
      'live GitHub or the ADR ledger on main · 🟡 in flight · ❌ not done · ⬜ no '
      'machine-checkable source, with a note saying what would make it one. Within a lane the '
      'gates come in the plan\'s order, and the first one not met is marked next. Below them, '
      'the lane\'s items in the plan\'s order, each with its live state.</div>')
    for lane in model["lanes"]:
        a('<div class="card lane">')
        a(f'<h3><span class="id">Lane {e(lane["id"])}</span>{e(lane["name"])}</h3>')
        a(f'<div class="sub">{e(lane.get("rank_note", ""))}</div>')
        a('<ul class="gates">')
        for gid in lane["gate_ids"]:
            g = next(x for x in model["gates"] if x["id"] == gid)
            tag = ' <span class="pill ready">next</span>' if lane["next"] == gid else ""
            a(f'<li><span>{MARK[g["status"]]}</span><span><b class="mono">{e(g["id"])}</b> '
              f'{e(g["name"])}{tag} <span class="sub">{g["done"]}/{g["total"]}</span>'
              f'<span class="note">{e(g["text"])}'
              + (f' Opens: {e(g["opens"])}' if g.get("opens") else "") + '</span></span></li>')
            for c in g["conditions"]:
                a(f'<li class="cond"><span>{MARK[c["status"]]}</span><span>{e(c["text"])}')
                if c.get("note"):
                    a(f'<span class="note">{e(c["note"])}</span>')
                a('</span></li>')
        a('</ul>')
        a('<ol class="items">')
        for kind, x in lane_items(model, lane["id"]):
            if kind == "ticket":
                a(f'<li><span class="ord">{x.get("order", "")}</span>'
                  f'<span>{MARK[ITEM_MARK[x["state"]]]}</span><span>'
                  f'<a href="{e(x["url"])}">#{x["id"]}</a> {e(x["short"])} '
                  f'<span class="sub">@{e(x["owner"])}</span>'
                  f'<span class="note">{e(item_detail(x, model, plan))}</span></span></li>')
            else:
                a(f'<li><span class="ord">{x.get("order", "")}</span><span>{MARK[UNKNOWN]}</span>'
                  f'<span>new: {e(x["short"])} '
                  f'<span class="sub">{e(", ".join("@" + o for o in x["owners"]))}</span>'
                  f'<span class="note">{e(planned_detail(x))}. {e(x["why"])}</span></span></li>')
        a('</ol></div>')

    # ---- unblocked but stuck
    a('<h2>Nothing upstream is blocking these, so what is?</h2>')
    a('<div class="lede">Tickets whose stated dependencies are all met, and which therefore '
      'cannot be excused by the critical path. Each row is the actual reason it has not closed.</div>')
    stuck = [t for t in model["tickets"] if t["state"] != "done" and t["state"] != "blocked" and t["blockers"]]
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Ticket</th><th>Owner</th><th>Where it is</th><th>What is actually blocking it</th></tr>')
    if not stuck:
        a('<tr><td colspan="4" class="empty">Nothing beyond its own work is holding any ticket.</td></tr>')
    for t in sorted(stuck, key=lambda x: (0 if x["state"] == "ready" else 1, -len(x.get("unblocks") or []))):
        pr = t.get("pr")
        where = (f'<a href="{e(pr["url"])}">PR #{pr["number"]}</a> '
                 f'<span class="pill {"idle" if not pr.get("isDraft") else "warn"}">'
                 f'{"draft" if pr.get("isDraft") else "open"}</span>'
                 f'<div class="sub">+{pr.get("additions",0)}/−{pr.get("deletions",0)} · '
                 f'{pr.get("file_count",0)} files</div>') if pr else \
                '<span class="pill ready">no branch yet</span>'
        ordered = sorted(t["blockers"], key=lambda x: SEV_RANK.get(x["severity"], 9))
        worst = ordered[0]["severity"] if ordered else "low"
        a(f'<tr class="sev-{e(worst)}"><td class="num"><a href="{e(t["url"])}">#{t["id"]}</a>'
          f'<span class="cap">{e(t["short"])}</span></td>')
        a(f'<td>@{e(t["owner"])}</td><td>{where}</td><td><ul class="blockers">')
        for b in ordered:
            a(f'<li><span class="dot {e(b["severity"])}"></span><span>{e(b["text"])}</span></li>')
        a('</ul></td></tr>')
    a('</table></div></div>')

    # ---- blocked
    a('<h2>Blocked upstream</h2>')
    a('<div class="lede">Waiting on another ticket or PR, quoted from this ticket\'s own '
      '<span class="mono">Depends on</span> row or, where it says so, from the plan. Do not '
      'start these; clear the blocker.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Ticket</th><th>Owner</th><th>Waiting on</th><th>Fallback</th></tr>')
    blocked = [t for t in model["tickets"] if t["state"] == "blocked"]
    if not blocked:
        a('<tr><td colspan="4" class="empty">Nothing is blocked upstream.</td></tr>')
    for t in blocked:
        deps = "".join(
            f'<li><span class="dot critical"></span><span><b>'
            + (f'PR #{d["id"]}' if d["kind"] == "pr" else
               f'{d["id"]} gate' if d["kind"] == "gate" else f'#{d["id"]}')
            + f'</b>: {e(d["what"])}</span></li>' for d in t["unmet_hard"])
        a(f'<tr class="sev-critical"><td class="num"><a href="{e(t["url"])}">#{t["id"]}</a>'
          f'<span class="cap">{e(t["short"])}</span></td>')
        a(f'<td>@{e(t["owner"])}</td><td><ul class="blockers">{deps}</ul></td>')
        a(f'<td class="sub">{e(t.get("fallback") or "not stated")}</td></tr>')
    a('</table></div></div>')

    # ---- open PRs
    a('<h2>Open pull requests</h2>')
    a('<div class="lede">A green tick on a CONFLICTING PR is not evidence: ci.yml does not '
      'dispatch while a PR is dirty, so those checks describe a main that has already moved.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>PR</th><th>Author</th><th>Mergeable</th><th>Review</th><th>Checks</th><th>Updated</th></tr>')
    # Every open PR the plan knows about, deduplicated: a ticket's own PRs, and the
    # PRs a ticket waits on (#122 on PR #121). An issue may have more than one PR
    # (#53 had two), which is why each row carries the ticket it belongs to.
    rows: dict[int, tuple[dict, dict, str]] = {}
    for t in model["tickets"]:
        for pr in t.get("all_prs") or []:
            rows.setdefault(pr["number"], (pr, t, "for"))
    by_id = {t["id"]: t for t in model["tickets"]}
    for n, held in model["holding_pr"].items():
        pr = next((p for t in model["tickets"] for p in [t.get("pr")] if p and p["number"] == n), None)
        pr = pr or model.get("prs_by_number", {}).get(n)
        if pr and pr.get("state") == "OPEN":
            rows.setdefault(n, (pr, by_id[held[0]], "holds"))

    if not rows:
        a('<tr><td colspan="6" class="empty">No open PR serves or holds a ticket in this plan.</td></tr>')
    for number in sorted(rows, reverse=True):
        pr, t, rel = rows[number]
        merge_pill = ('<span class="pill bad">conflicting</span>' if pr.get("mergeable") == "CONFLICTING"
                      else '<span class="pill ok">clean</span>')
        if pr.get("isDraft"):
            merge_pill += ' <span class="pill warn">draft</span>'
        revs = pr.get("latest_reviews") or []
        rev_html = "".join(
            f'<div><span class="pill {"bad" if r["state"]=="CHANGES_REQUESTED" else ("ok" if r["state"]=="APPROVED" else "idle")}">'
            f'{e(r["state"].lower().replace("_"," "))}</span> @{e(r["who"])} '
            f'<span class="sub">{e(r["at"])}</span></div>'
            for r in revs) or '<span class="pill warn">no review</span>'
        for l in pr.get("looked_since") or []:
            rev_html += (f'<div class="sub">@{e(l["who"])} looked again {e(l["at"])} '
                         f'without lifting it</div>')
        chk = ('<span class="pill bad">failing</span>' if pr.get("checks_failing")
               else ('<span class="pill warn">stale</span>' if pr.get("checks_stale_vs_main")
                     else '<span class="pill ok">green</span>'))
        chk += f'<div class="sub">{e(pr.get("checks_newest") or "none")}</div>'
        sev = ("critical" if pr.get("mergeable") == "CONFLICTING"
               or pr.get("reviewDecision") == "CHANGES_REQUESTED"
               else ("high" if pr.get("isDraft") else "medium"))
        a(f'<tr class="sev-{sev}"><td class="num"><a href="{e(pr["url"])}">#{number}</a>'
          f'<span class="cap">{e(pr["title"][:64])} · {rel} '
          f'<a href="{e(t["url"])}">#{t["id"]}</a></span></td>')
        a(f'<td>@{e((pr.get("author") or {}).get("login"))}</td><td>{merge_pill}</td>'
          f'<td>{rev_html}</td><td>{chk}</td><td class="sub">{e(pr["updatedAt"][:10])}</td></tr>')
    a('</table></div></div>')

    # ---- day by day
    a('<h2>Day by day</h2>')
    a('<div class="lede">One record per day, written by the routine and diffed against '
      'the day before. Every line below is computed from those records, so it cannot drift '
      'from what the rest of this page says. There is no burn-up chart: the gates are ordered, '
      'not dated, so an even-pace line would draw a pace the plan does not set.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Date</th><th>Gates</th><th>Conditions</th><th>Ready</th><th>In review</th>'
      '<th>Blocked</th><th>What moved</th></tr>')
    if not history:
        a('<tr><td colspan="7" class="empty">No records yet.</td></tr>')
    for i in range(len(history) - 1, -1, -1):
        h = history[i]
        ev = day_events(history[i - 1], h, plan) if i > 0 else []
        c = h.get("counts", {})
        if i == 0:
            moved = '<span class="pill idle">first record</span>'
        elif ev:
            moved = '<ul class="blockers">' + "".join(
                f'<li><span class="dot medium"></span><span>{e(x)}</span></li>' for x in ev
            ) + '</ul>'
        else:
            moved = '<span class="sub">nothing moved</span>'
        a(f'<tr><td class="num">{e(h["date"])}</td>'
          f'<td class="num">{h["gates_done"]}/{h["gates_total"]}</td>'
          f'<td class="num">{h["conditions_done"]}/{h["conditions_total"]}</td>'
          f'<td class="num">{c.get("ready", 0)}</td>'
          f'<td class="num">{c.get("in_review", 0)}</td>'
          f'<td class="num">{c.get("blocked", 0)}</td>'
          f'<td>{moved}</td></tr>')
    a('</table></div></div>')

    # ---- ADR ledger
    a('<h2>ADR ledger</h2>')
    a('<div class="lede">Status and title read from <span class="mono">docs/decisions.md</span> '
      'on main, not from any branch. "Not in the ledger" means the ADR exists at most as a '
      'draft somewhere else.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>ADR</th><th>On main</th><th>Needs</th></tr>')
    for w in plan["adr_watch"]:
        cur = main["adr"].get(w["id"])
        ok = bool(cur) and adr_met(cur, w["want"])
        name = main["adr_title"].get(w["id"]) or w.get("name", "")
        a(f'<tr><td class="num">{MARK[DONE if ok else NOT_DONE]} {e(w["id"])}'
          f'<span class="cap">{e(name)}</span></td>'
          f'<td><span class="pill {"ok" if ok else "idle"}">{e(cur or "not in the ledger")}</span></td>'
          f'<td class="sub">{e(w["gate"])}</td></tr>')
    a('</table></div></div>')

    # ---- parked
    a('<h2>Parked</h2>')
    a('<div class="lede">Out of every lane on purpose, with the plan\'s reason. Issue state and '
      'milestone are read live.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Ticket</th><th>On GitHub</th><th>Why it is parked</th></tr>')
    for x in model["parked"]:
        a(f'<tr><td class="num"><a href="{e(x["url"])}">#{x["id"]}</a>'
          f'<span class="cap">{e(clip(x["title"], 64))}</span></td>'
          f'<td class="sub">{e(x["state"].lower())} · {e(x["milestone"] or "no milestone")}</td>'
          f'<td class="sub">{e(x["reason"])}</td></tr>')
    a('</table></div></div>')

    # ---- risks
    a('<h2>Risks the plan named</h2>')
    a('<div class="lede">Quoted from plan §7 as written. Where a risk names a PR, its live state '
      'is shown beside it; nothing here is a hand-written status.</div>')
    a('<div class="card">')
    for r in plan["risks"]:
        now_txt = risk_now(r, model)
        a('<div class="risk">')
        a('<div><span class="pill warn">named</span></div>')
        a(f'<div><div class="what">{e(r["text"])}</div>'
          + (f'<div class="ev"><b>Now:</b> {e(now_txt)}</div>' if now_txt else "") + '</div>')
        a('</div>')
    a('</div>')

    prev = p.get("previous") or {}
    a('<footer>')
    a(f'Generated by <code>generate.py</code> on this dashboard\'s own branch, which shares no '
      f'history with main. Static plan model: <code>plan.json</code>. Live state read via '
      f'<code>gh</code> at {e(now)}.<br>'
      f'Nothing here is hand-maintained except <code>plan.json</code>, which changes only when '
      f'the plan, a ticket\'s stated dependency or an owner changes. Source of truth for the plan '
      f'itself: <code>{e(p["plan_doc"])}</code>, read at <code>{e(p["plan_sha"])}</code> on '
      f'<code>{e(p["plan_ref"])}</code>.'
      + (f' {e(prev["name"])} is recorded on the <code>{e(prev["branch"])}</code> branch.'
         if prev.get("branch") else ""))
    a('</footer></div>')
    return "\n".join(O)


def main() -> int:
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    lint_plan(plan)   # before any read: a plan assigning work off the team never renders
    issues = fetch_issues()
    prs = fetch_prs()
    enrich_open_prs(prs)
    main_state = fetch_context(plan)
    conversations = fetch_conversations()

    model = build(plan, issues, prs, main_state)
    model["owed"] = owed_answers(conversations, plan_today())
    queue = action_queue(model, plan)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # An explicit LF newline on every write: Python's text mode would otherwise
    # emit CRLF on Windows, and update.sh decides whether to commit by diffing
    # these files. A platform-dependent line ending would make every run on a
    # Windows host look like a change, and the routine would commit daily noise.
    def emit(name: str, text: str) -> None:
        with open(HERE / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    # Record today before rendering, so the page always includes the day it is
    # describing. A later run on the same date overwrites its own record rather
    # than appending, which keeps exactly one row per day however often it runs.
    folder = history_dir(plan)
    folder.mkdir(parents=True, exist_ok=True)
    today = summarise(model, main_state, now, plan)
    with open(folder / f"{today['date']}.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(today, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    history = load_history(plan)

    emit("index.html", render_html(plan, model, queue, main_state, now, history))
    emit("STATUS.md", render_markdown(plan, model, queue, main_state, now, history))
    splice_readme(render_readme_block(plan, model, queue, main_state, now, history))
    emit("last_run.md", render_run_report(plan, model, queue, main_state, now, history))
    emit("snapshot.json", json.dumps(
        {"generated": now, "main": {k: v for k, v in main_state.items() if k != "bodies"},
         "tickets": [{k: v for k, v in t.items() if k not in ("pr", "lane_info")} | {
             "pr": t["pr"]["number"] if t.get("pr") else None} for t in model["tickets"]],
         "gates": model["gates"], "lanes": model["lanes"], "warnings": model["warnings"],
         "owed": model["owed"]},
        indent=2, ensure_ascii=False, default=str))

    g_done, g_total, c_done, c_total = gate_counts(model)
    print(f"wrote index.html, STATUS.md, snapshot.json: {g_done}/{g_total} gates met "
          f"({c_done}/{c_total} conditions), "
          f"{sum(1 for t in model['tickets'] if t['state']=='ready')} ready, "
          f"{sum(1 for t in model['tickets'] if t['state']=='blocked')} blocked, "
          f"{len(model['warnings'])} plan warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
