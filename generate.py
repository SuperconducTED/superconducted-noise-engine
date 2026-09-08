#!/usr/bin/env python3
"""Generate the phase-3 status dashboard.

Reads two things and joins them:

  1. ``plan.json`` — the static, hand-curated model of the phase-3 plan. Owners,
     milestone gates, and every dependency edge quoted from a ticket's own
     "Depends on" row. This changes only when the plan or a ticket changes.
  2. Live GitHub state, via the ``gh`` CLI — issue open/closed, PR review
     decision, mergeability, check-run conclusions, and the ADR ledger on main.

and writes ``index.html``, ``STATUS.md`` and ``snapshot.json``.

The point of the join is the derived column nobody maintains by hand: for every
ticket, whether its *upstream* dependencies are met, and — separately — what
else is standing between it and closure once they are. Those are different
questions and the plan conflates them; this does not.

Contract
--------
inputs   : plan.json (cwd), a working ``gh`` on PATH authenticated to the repo,
           network access to github.com.
outputs  : index.html, STATUS.md, snapshot.json written into cwd. Idempotent —
           running twice with unchanged upstream state produces identical files
           except for the generated-at timestamp.
exit code: 0 on success, 1 if ``gh`` fails or plan.json is unreadable. It never
           writes a partial file: everything is rendered in memory first.
side effects: none beyond those three files. It does not commit, push, or touch
           the project's own branches.
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
# means in flight. Nothing is amber merely because it is uncertain — an unknown
# renders as its own grey marker so it cannot be mistaken for progress.
DONE, NOT_DONE, PARTIAL, UNKNOWN = "done", "not_done", "partial", "unknown"
MARK = {DONE: "✅", NOT_DONE: "❌", PARTIAL: "🟡", UNKNOWN: "⬜"}


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
        "--json", "number,title,state,assignees,labels,updatedAt,url",
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
    PRs never change. ``checks_stale_vs_main`` is the important derived field —
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
        # CHANGES_REQUESTED — only an APPROVED or an explicit dismissal does. So
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


def fetch_main_state() -> dict:
    """Read the few facts about main the dashboard asserts, from main itself."""
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
    for m in re.finditer(r"^## (ADR-\d{3}) — (.+?)$", text, re.M):
        tail = text[m.end():m.end() + 1200]
        s = re.search(r"\*\*Status\*\*:\s*([^\n.]+)", tail)
        adr[m.group(1)] = s.group(1).strip().rstrip(".") if s else "?"
    state["adr"] = adr

    # Does the feature-distribution evidence directory exist on main yet?
    probe = subprocess.run(
        ["gh", "api", f"repos/{REPO}/contents/docs/evidence/feature-distribution"],
        capture_output=True, text=True,
    )
    state["paths"] = {"docs/evidence/feature-distribution": probe.returncode == 0}
    return state


# --------------------------------------------------------------------------
# Join and derive
# --------------------------------------------------------------------------

def prs_for_issue(issue_no: int, prs: dict[int, dict], hints: list[int] | None = None) -> list[dict]:
    """Every open PR that would close an issue, newest first.

    Three sources, in descending trustworthiness: an explicit ``pr_hint`` in
    plan.json (for branches opened without a closing keyword and without the
    number in the name), GitHub's own ``closingIssuesReferences``, then the
    branch name and title. An issue can legitimately have more than one open PR
    — #53 has two — so this returns a list; taking only the first would hide a
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
    never depends on an *issue* — it depends on an artifact that issue produces.
    #57's issue is still open because its advisor half is outstanding, but the
    contract #59, #60, #61 and #63 actually consume merged in PR #69. Keying
    those edges on issue closure would paint the entire trainer track blocked
    when nothing is stopping it, which is the single most expensive mistake
    this dashboard could make. So a dep may name the artifact that discharges
    it, and issue closure is only the default when nothing more precise exists.
    """
    sat = dep.get("satisfied_by")
    if sat:
        if sat["kind"] == "pr_merged":
            return prs.get(sat["id"], {}).get("state") == "MERGED"
        if sat["kind"] == "issue_closed":
            return issues.get(sat["id"], {}).get("state") == "CLOSED"

    kind = dep["kind"]
    if kind == "issue":
        return issues.get(dep["id"], {}).get("state") == "CLOSED"
    if kind == "pr":
        return prs.get(dep["id"], {}).get("state") == "MERGED"
    if kind == "gate":
        return milestone_state.get(dep["id"], {}).get("status") == DONE
    return False


def review_blockers(pr: dict) -> list[dict]:
    """Why this PR is not merging, in the order that matters.

    Ordered deliberately: a conflict must be fixed before a review is worth
    asking for, and a draft will not be reviewed at all. main's ruleset requires
    one approval and does *not* dismiss stale reviews on push, so a standing
    CHANGES_REQUESTED needs an explicit re-review — pushing a fix does not clear it.
    """
    out: list[dict] = []
    if pr.get("isDraft"):
        out.append({"severity": "high", "text": "Still a draft — CI and reviewers will not treat it as ready."})
    if pr.get("mergeable") == "CONFLICTING":
        out.append({"severity": "critical", "text": "Conflicts with main — needs a rebase before it can merge, and ci.yml will not re-run until it is clean."})
    if pr.get("checks_stale_vs_main"):
        out.append({"severity": "high", "text": f"Its green checks last ran {pr.get('checks_newest') or 'earlier'} against a main that has moved since — they are not evidence about the merge result."})
    if pr.get("checks_failing"):
        names = ", ".join(c["name"] for c in pr["checks_failing"][:4])
        out.append({"severity": "critical", "text": f"Failing checks: {names}."})
    decision = pr.get("reviewDecision")
    changes = [r for r in pr.get("latest_reviews") or [] if r["state"] == "CHANGES_REQUESTED"]
    if decision == "CHANGES_REQUESTED" or changes:
        who = ", ".join(f"@{r['who']} ({r['at']})" for r in changes) or "a reviewer"
        out.append({"severity": "critical", "text": f"CHANGES_REQUESTED standing from {who}. Stale reviews are not dismissed on push, so it needs an explicit re-review, not just a fix."})
    elif decision == "REVIEW_REQUIRED" or not pr.get("latest_reviews"):
        out.append({"severity": "high", "text": "No approving review yet — main's ruleset requires one."})
    return out


def build(plan: dict, issues: dict, prs: dict, main: dict) -> dict:
    tickets = []
    milestone_state: dict[str, dict] = {}
    hint_map = {t["id"]: t.get("pr_hint") or [] for t in plan["tickets"]}

    # Milestones first, so a "gate" dependency can be resolved against them.
    for ms in plan["milestones"]:
        gates = []
        for g in ms["gates"]:
            chk, note = g["check"], g["check"].get("note")
            if chk["kind"] == "issue_closed":
                st = DONE if issues.get(chk["id"], {}).get("state") == "CLOSED" else NOT_DONE
                if st == NOT_DONE and pr_for_issue(chk["id"], prs, hint_map.get(chk["id"])):
                    st = PARTIAL
            elif chk["kind"] == "pr_merged":
                p = prs.get(chk["id"], {})
                st = DONE if p.get("state") == "MERGED" else (PARTIAL if p.get("state") == "OPEN" else NOT_DONE)
            elif chk["kind"] == "adr_status":
                cur = main["adr"].get(chk["id"], "?")
                st = DONE if cur.lower().startswith(chk["want"].lower()) else NOT_DONE
                note = f"Ledger on main reads: {cur}."
            elif chk["kind"] == "file_on_main":
                st = DONE if main["paths"].get(chk["path"]) else NOT_DONE
            else:  # manual
                st = {"done": DONE, "not_done": NOT_DONE, "partial": PARTIAL}.get(chk.get("state", ""), UNKNOWN)
            gates.append({"text": g["text"], "status": st, "note": note})

        n_done = sum(1 for g in gates if g["status"] == DONE)
        status = DONE if n_done == len(gates) else (NOT_DONE if n_done == 0 else PARTIAL)
        milestone_state[ms["id"]] = {
            **ms, "gates": gates, "done": n_done, "total": len(gates),
            "status": status, "days_left": days_between(plan_today(), ms["target"]),
        }

    # Tickets.
    for t in plan["tickets"]:
        issue = issues.get(t["id"], {})
        closed = issue.get("state") == "CLOSED"
        hints = t.get("pr_hint") or []
        all_prs = prs_for_issue(t["id"], prs, hints)
        pr = pr_for_issue(t["id"], prs, hints)
        merged = merged_pr_for_issue(t["id"], prs) if not pr else None

        # A hard dependency carrying a "part" gates only that part of the
        # ticket, not the ticket. #60's dependency on #63 is for the first
        # archive fit alone; its LSE stage — the M2 gate and the whole reason
        # the trainer is the long pole — needs nothing from #63. Treating a
        # partial dep as blocking would park the phase's critical path behind
        # a data ticket for no reason, so partial deps become scope notes.
        unmet_all = [d for d in t.get("hard_deps", []) if not dep_met(d, issues, prs, milestone_state)]
        unmet = [d for d in unmet_all if not d.get("part")]
        partial = [d for d in unmet_all if d.get("part")]
        soft_unmet = [d for d in t.get("soft_deps", []) if not dep_met(d, issues, prs, milestone_state)]

        blockers: list[dict] = []
        if pr:
            blockers += review_blockers(pr)
        blockers += [b for b in t.get("extra_blockers", []) if b.get("severity") != "info"]

        if closed:
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
            "state": state,
            "pr": pr, "all_prs": all_prs, "merged_pr": merged,
            "unmet_hard": unmet, "unmet_partial": partial, "unmet_soft": soft_unmet,
            "blockers": blockers,
            "notes_info": [b for b in t.get("extra_blockers", []) if b.get("severity") == "info"],
        })

    return {"milestones": list(milestone_state.values()), "tickets": tickets}


def plan_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def days_between(a: str, b: str) -> int:
    fmt = "%Y-%m-%d"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).days


# --------------------------------------------------------------------------
# "Work on this now" — the ranked queue
# --------------------------------------------------------------------------

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def action_queue(model: dict, plan: dict) -> dict[str, list[dict]]:
    """One ranked action list per person.

    Ranking is by *consequence*, not by activity type. Sorted on:
      1. fan-out — how many other tickets this releases. This is the whole
         reason the plan has a critical path, so it dominates. A re-review that
         frees three tickets outranks starting a defect that frees none, and an
         in-flight PR that four people are waiting on outranks fresh work.
      2. the ticket's own priority label.
      3. kind, as a tiebreak only: a review you alone can clear, then in-flight
         work, then a fresh start — cheapest-first among equals.

    A ticket blocked on an upstream dependency is never listed against its own
    owner. It surfaces instead against whoever owns the blocker, which is the
    only place an action can actually be taken.
    """
    by_person: dict[str, list[dict]] = defaultdict(list)
    prio = {"critical": 0, "high": 1, "medium-high": 2, "medium": 3, "low": 4, "unset": 5}
    KIND_TIE = {"review": 0, "in_review": 1, "ready": 2}

    def rank(kind: str, fanout: int, t: dict) -> tuple:
        # External latency comes first, ahead of even fan-out. Work whose
        # completion waits on somebody outside the team — an advisor answering
        # four questions — has a lead time the team cannot compress, so a day
        # of delay there costs a day of phase, while a day of delay on internal
        # work can still be absorbed. Everything else sorts on consequence.
        return (0 if t.get("external_latency") else 1,
                -fanout, prio.get(t.get("priority", "unset"), 5), KIND_TIE[kind])

    def scope_note(t: dict) -> str:
        if not t.get("unmet_partial"):
            return ""
        bits = "; ".join(f"the {d['part']} part waits on #{d['id']}" for d in t["unmet_partial"])
        return f" Start the rest now — {bits}."

    for t in model["tickets"]:
        if t["state"] == "done":
            continue
        fanout = len(t.get("unblocks") or [])
        if t["state"] == "ready":
            verb = "Start" if not t.get("merged_pr") else "Finish"
            act = {
                "rank": rank("ready", fanout, t), "kind": "ready", "ticket": t,
                "action": f"{verb} #{t['id']} — {t['short']}",
                "why": (t.get("why_now") or "All stated upstream dependencies are met.") + scope_note(t),
                "fanout": fanout,
            }
            by_person[t["owner"]].append(act)
        elif t["state"] == "in_review":
            pr = t["pr"]
            act = {
                "rank": rank("in_review", fanout, t), "kind": "in_review", "ticket": t,
                "action": f"Unstick PR #{pr['number']} for #{t['id']} — {t['short']}",
                "why": (t["blockers"][0]["text"] if t["blockers"] else "Awaiting merge.") + scope_note(t),
                "fanout": fanout,
            }
            by_person[t["owner"]].append(act)
        else:
            act = None

        # A co-owner with a named handoff gets their own row. #84's brief is
        # Yiğit's to write and Mert's to send; only listing the owner would
        # leave the send unassigned, which is exactly how it went unsent.
        if act and t.get("co_owner") and t.get("co_owner_action"):
            by_person[t["co_owner"]].append({
                **act, "kind": act["kind"],
                "action": f"{t['co_owner_action']} (#{t['id']})",
                "why": t.get("co_owner_why") or act["why"],
            })

    # Reviews a specific person owes, on any PR. These are listed against the
    # reviewer because the ruleset makes them the only person who can clear it.
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
                    why += (f" You commented again on {looked['at']} without lifting it — "
                            f"a COMMENTED review does not dismiss a CHANGES_REQUESTED.")
                by_person[rev["who"]].append({
                    "rank": rank("review", fanout, t), "kind": "review", "ticket": t,
                    "action": f"Re-review PR #{pr['number']} (#{t['id']} — {t['short']})",
                    "why": why, "fanout": fanout,
                })

    for person in by_person:
        by_person[person].sort(key=lambda a: a["rank"])
    return dict(by_person)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def e(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def render_markdown(plan: dict, model: dict, queue: dict, main: dict, now: str) -> str:
    L: list[str] = []
    a = L.append
    a(f"# Phase 3 — {plan['phase']['goal']}\n")
    a(f"_Generated {now} · main at `{main['sha']}` ({main['date']}) · "
      f"{days_between(plan_today(), plan['phase']['end'])} days to {plan['phase']['end']}_\n")

    a("\n## Milestones\n")
    for ms in model["milestones"]:
        a(f"\n### {MARK[ms['status']]} {ms['id']} · {ms['name']} — target {ms['target']} "
          f"({ms['done']}/{ms['total']})\n")
        for g in ms["gates"]:
            a(f"- {MARK[g['status']]} {g['text']}")
            if g.get("note"):
                a(f"  - _{g['note']}_")

    a("\n## Work on this right now\n")
    for login, actions in sorted(queue.items(), key=lambda kv: kv[0].lower()):
        who = plan["people"].get(login, {}).get("name", login)
        a(f"\n**{who}** (@{login})\n")
        for act in actions[:4]:
            a(f"1. {act['action']}")
            a(f"   - {act['why']}")

    a("\n## Not blocked by anything upstream — so what is holding them?\n")
    for t in model["tickets"]:
        if t["state"] in ("done", "blocked") or not t["blockers"]:
            continue
        a(f"\n**#{t['id']} — {t['short']}** (@{t['owner']})\n")
        for b in sorted(t["blockers"], key=lambda x: SEV_RANK.get(x["severity"], 9)):
            a(f"- [{b['severity']}] {b['text']}")

    a("\n## Blocked upstream\n")
    for t in model["tickets"]:
        if t["state"] != "blocked":
            continue
        deps = "; ".join(f"#{d['id']} ({d['what']})" if d["kind"] != "gate"
                         else f"{d['id']} gate ({d['what']})" for d in t["unmet_hard"])
        a(f"- **#{t['id']}** {t['short']} (@{t['owner']}) — waiting on {deps}")

    a("\n## ADR ledger\n")
    for w in plan["adr_watch"]:
        cur = main["adr"].get(w["id"], "?")
        mk = MARK[DONE] if cur.lower().startswith(w["want"].lower()) else MARK[NOT_DONE]
        a(f"- {mk} **{w['id']}** {w['name']} — on main: _{cur}_ · needs: {w['gate']}")
    return "\n".join(L) + "\n"


def render_html(plan: dict, model: dict, queue: dict, main: dict, now: str) -> str:
    """Render the dashboard. Self-contained: no external CSS, JS or fonts."""
    p = plan["phase"]
    days_left = days_between(plan_today(), p["end"])
    elapsed = days_between(p["start"], plan_today())
    total_days = days_between(p["start"], p["end"])
    pct = max(0, min(100, round(100 * elapsed / total_days)))

    all_gates = [g for ms in model["milestones"] for g in ms["gates"]]
    gates_done = sum(1 for g in all_gates if g["status"] == DONE)

    O: list[str] = []
    a = O.append

    a("<title>Phase 3 Tracker</title>")
    # IBM Plex is not a neutral pick: this project reads IBM Quantum calibration
    # snapshots all day, and Plex is IBM's own type. Mono carries every figure
    # that has to line up — ticket numbers, SHAs, timestamps, counts.
    a('<link rel="preconnect" href="https://fonts.googleapis.com">')
    a('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
      'family=IBM+Plex+Mono:wght@400;500;600&'
      'family=IBM+Plex+Sans:wght@400;450;500;600;700&display=swap">')
    a("<style>")
    a("""
/* Palette: a cryostat, not a cream document. The neutral carries a cool blue
   bias toward the accent, which is the teal of a dilution-fridge readout rather
   than a default indigo. Semantic colours (met / in flight / not done) are a
   separate axis from the accent and never borrow it. */
:root{
  --bg:#f4f6f8; --panel:#fff; --sunk:#eceff3;
  --ink:#101519; --ink-2:#39434d; --muted:#5f6b78; --line:#dde3e9;
  --accent:#00707f; --accent-bg:#dff1f3; --accent-ink:#00707f;
  --ok:#146b3a; --ok-bg:#e2f2e8;
  --warn:#8f5406; --warn-bg:#faeedd;
  --bad:#a80f37; --bad-bg:#fbe6ec;
  --idle:#6b7783; --idle-bg:#e7ebef;
  --shadow:0 1px 1px rgba(16,21,25,.03), 0 12px 28px -20px rgba(16,21,25,.28);
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0d1215; --panel:#141b20; --sunk:#101619;
  --ink:#e6edf1; --ink-2:#b9c5ce; --muted:#8b98a4; --line:#242e35;
  --accent:#4ecdd8; --accent-bg:#0d2f34; --accent-ink:#7fdde6;
  --ok:#59c584; --ok-bg:#10291b;
  --warn:#d9a24f; --warn-bg:#2a2011;
  --bad:#f0708f; --bad-bg:#2c1219;
  --idle:#7b8895; --idle-bg:#1a2126;
  --shadow:0 1px 1px rgba(0,0,0,.4), 0 12px 28px -20px rgba(0,0,0,.8);
}}
:root[data-theme="dark"]{
  --bg:#0d1215; --panel:#141b20; --sunk:#101619;
  --ink:#e6edf1; --ink-2:#b9c5ce; --muted:#8b98a4; --line:#242e35;
  --accent:#4ecdd8; --accent-bg:#0d2f34; --accent-ink:#7fdde6;
  --ok:#59c584; --ok-bg:#10291b;
  --warn:#d9a24f; --warn-bg:#2a2011;
  --bad:#f0708f; --bad-bg:#2c1219;
  --idle:#7b8895; --idle-bg:#1a2126;
  --shadow:0 1px 1px rgba(0,0,0,.4), 0 12px 28px -20px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.62;-webkit-font-smoothing:antialiased;padding:0 0 88px}
.wrap{max-width:1200px;margin:0 auto;padding:0 26px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
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
.bar > i{display:block;height:100%;background:var(--accent);border-radius:99px}
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
.person{border-top:3px solid var(--pc,var(--accent))}
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
.ms h3 .id{font-family:var(--mono);color:var(--accent);margin-right:7px}
.ms .when{text-align:right;white-space:nowrap}
.ms .when .d{font-family:var(--mono);font-size:14px;font-weight:500}
.ms .prog{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:3px}
.gates{list-style:none;margin:15px 0 0;padding:0;grid-column:1/-1}
.gates li{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:8px 0;
  border-top:1px solid var(--line);font-size:13.8px;line-height:1.5}
.gates .note{display:block;color:var(--muted);font-size:12.3px;margin-top:3px;line-height:1.5}

/* ---- pills: state at a glance ---- */
.pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;
  font-weight:600;letter-spacing:.02em;white-space:nowrap;font-family:var(--mono)}
.pill.ok{background:var(--ok-bg);color:var(--ok)}
.pill.warn{background:var(--warn-bg);color:var(--warn)}
.pill.bad{background:var(--bad-bg);color:var(--bad)}
.pill.idle{background:var(--idle-bg);color:var(--muted)}
.pill.accent{background:var(--accent-bg);color:var(--accent-ink)}

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
    a("</style>")

    # ---- hero
    a('<div class="wrap"><header class="hero">')
    a(f'<div class="eyebrow">{e(p["repo"])}</div>')
    a(f'<h1>{e(p["name"])} <span class="goal">— {e(p["goal"])}</span></h1>')
    a(f'<div class="sub">Generated {e(now)} from live GitHub state · '
      f'main at <code>{e(main["sha"])}</code> ({e(main["date"])}) · '
      f'plan of {e(p["plan_written"])} at <code>{e(p["plan_base_sha"])}</code></div>')
    ready_n = sum(1 for t in model["tickets"] if t["state"] == "ready")
    blocked_n = sum(1 for t in model["tickets"] if t["state"] == "blocked")
    review_n = sum(1 for t in model["tickets"] if t["state"] == "in_review")
    overdue_n = sum(1 for ms in model["milestones"]
                    if ms["days_left"] < 0 and ms["status"] != DONE)

    # The readout compares two rates: calendar burned against gates met. Those
    # two numbers side by side are the whole argument of the page.
    a('<div class="readout">')
    a(f'<div><div class="v">{days_left}</div><div class="k">days to {e(p["end"])}</div></div>')
    a(f'<div><div class="v">{gates_done}<span>/{len(all_gates)}</span></div>'
      f'<div class="k">gates met</div></div>')
    a(f'<div><div class="v">{ready_n}</div><div class="k">ready to start</div></div>')
    a(f'<div><div class="v">{review_n}</div><div class="k">in review</div></div>')
    a(f'<div><div class="v">{blocked_n}</div><div class="k">blocked upstream</div></div>')
    a(f'<div><div class="v{" alarm" if overdue_n else ""}">{overdue_n}</div>'
      f'<div class="k">milestones overdue</div></div>')
    gate_pct = round(100 * gates_done / len(all_gates)) if all_gates else 0
    a('<div class="calendar">')
    a(f'<div class="bar"><i style="width:{pct}%"></i></div>')
    a(f'<div class="sub" style="margin-top:7px">Calendar burned: day {elapsed} of '
      f'{total_days} (<span class="mono">{pct}%</span>) · gates met: '
      f'<span class="mono">{gate_pct}%</span>'
      + (f' — running <b>{pct - gate_pct} points</b> behind the calendar.'
         if pct > gate_pct else '.') + '</div>')
    a('</div>')
    a('</div></header>')

    # ---- action queue
    a('<h2>Work on this right now</h2>')
    a('<div class="lede">Ranked per person: work that is ready and unblocks the most other '
      'tickets first, then reviews only that person can clear, then everything else by priority. '
      'A ticket waiting on an upstream dependency is never listed against its own owner — it is '
      'listed as a review or a start against whoever owns the blocker.</div>')
    a('<div class="grid two">')
    order = ["mertefesensoy", "BurakOztekin", "yigit-arda", "bengisucvd", "BahaJarad"]
    for login in order + [k for k in queue if k not in order]:
        acts = queue.get(login, [])
        meta = plan["people"].get(login, {"name": login, "role": "", "colour": "#6b7280"})
        a(f'<div class="card person" style="--pc:{e(meta["colour"])}">')
        a(f'<h3>{e(meta["name"])}</h3><div class="role">@{e(login)} · {e(meta["role"])}</div>')
        if not acts:
            a('<div class="empty">Nothing ready and nothing owed. Available for reviews.</div>')
        else:
            a('<ol class="acts">')
            for act in acts[:4]:
                t = act["ticket"]
                a('<li>')
                a(f'<span class="act">{e(act["action"])}</span>')
                a(f'<span class="why">{e(act["why"])}</span>')
                a('<span class="tags">')
                kind_pill = {"ready": ("accent", "ready to start"),
                             "review": ("bad", "you are the blocker"),
                             "in_review": ("warn", "in review")}[act["kind"]]
                a(f'<span class="pill {kind_pill[0]}">{kind_pill[1]}</span>')
                if act["fanout"]:
                    unl = ", ".join(f"#{x}" for x in t.get("unblocks") or [])
                    a(f'<span class="pill idle">unblocks {e(unl)}</span>')
                if t.get("priority") not in (None, "unset"):
                    a(f'<span class="pill idle">{e(t["priority"])}</span>')
                a(f'<span class="pill idle">{e(t.get("milestone"))}</span>')
                a('</span></li>')
            a('</ol>')
        a('</div>')
    a('</div>')

    # ---- milestones
    a('<h2>Milestone gates</h2>')
    a('<div class="lede">Every gate is the plan\'s own wording. ✅ verified against live GitHub '
      'or the ADR ledger on main · 🟡 in flight · ❌ not done · ⬜ no machine-checkable source.</div>')
    a('<div class="grid" style="gap:13px">')
    for ms in model["milestones"]:
        overdue = ms["days_left"] < 0 and ms["status"] != DONE
        a('<div class="card"><div class="ms">')
        a(f'<div><h3><span class="id">{e(ms["id"])}</span>{MARK[ms["status"]]} {e(ms["name"])}</h3>'
          f'<div class="sub">{e(ms["unblocks"])}</div></div>')
        late = (f'<span class="pill bad">{abs(ms["days_left"])}d overdue</span>' if overdue else
                (f'<span class="pill ok">met</span>' if ms["status"] == DONE else
                 f'<span class="pill idle">in {ms["days_left"]}d</span>'))
        a(f'<div class="when"><div class="d">{e(ms["target"])}</div>{late}'
          f'<div class="prog">{ms["done"]}/{ms["total"]} gates</div></div>')
        a('<ul class="gates">')
        for g in ms["gates"]:
            a(f'<li><span>{MARK[g["status"]]}</span><span>{e(g["text"])}')
            if g.get("note"):
                a(f'<span class="note">{e(g["note"])}</span>')
            a('</span></li>')
        a('</ul></div></div>')
    a('</div>')

    # ---- unblocked but stuck
    a('<h2>Nothing upstream is blocking these — so what is?</h2>')
    a('<div class="lede">Tickets whose stated dependencies are all met, and which therefore '
      'cannot be excused by the critical path. Each row is the actual reason it has not closed.</div>')
    stuck = [t for t in model["tickets"] if t["state"] != "done" and t["state"] != "blocked" and t["blockers"]]
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Ticket</th><th>Owner</th><th>Where it is</th><th>What is actually blocking it</th></tr>')
    for t in sorted(stuck, key=lambda x: (0 if x["state"] == "ready" else 1, -len(x.get("unblocks") or []))):
        pr = t.get("pr")
        where = (f'<a href="{e(pr["url"])}">PR #{pr["number"]}</a> '
                 f'<span class="pill {"idle" if not pr.get("isDraft") else "warn"}">'
                 f'{"draft" if pr.get("isDraft") else "open"}</span>'
                 f'<div class="sub">+{pr.get("additions",0)}/−{pr.get("deletions",0)} · '
                 f'{pr.get("file_count",0)} files</div>') if pr else \
                '<span class="pill accent">no branch yet</span>'
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
    a('<div class="lede">Waiting on another ticket, quoted from this ticket\'s own '
      '<span class="mono">Depends on</span> row. Do not start these; clear the blocker.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>Ticket</th><th>Owner</th><th>Waiting on</th><th>Fallback</th></tr>')
    blocked = [t for t in model["tickets"] if t["state"] == "blocked"]
    if not blocked:
        a('<tr><td colspan="4" class="empty">Nothing is blocked upstream.</td></tr>')
    for t in blocked:
        deps = "".join(
            f'<li><span class="dot critical"></span><span><b>'
            + (f'#{d["id"]}' if d["kind"] != "gate" else f'{d["id"]} gate')
            + f'</b> — {e(d["what"])}</span></li>' for d in t["unmet_hard"])
        a(f'<tr class="sev-critical"><td class="num"><a href="{e(t["url"])}">#{t["id"]}</a>'
          f'<span class="cap">{e(t["short"])}</span></td>')
        a(f'<td>@{e(t["owner"])}</td><td><ul class="blockers">{deps}</ul></td>')
        a(f'<td class="sub">{e(t.get("fallback") or "—")}</td></tr>')
    a('</table></div></div>')

    # ---- open PRs
    a('<h2>Open pull requests</h2>')
    a('<div class="lede">A green tick on a CONFLICTING PR is not evidence: ci.yml does not '
      'dispatch while a PR is dirty, so those checks describe a main that has already moved.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>PR</th><th>Author</th><th>Mergeable</th><th>Review</th><th>Checks</th><th>Updated</th></tr>')
    # Every open PR the plan knows about, deduplicated. An issue may have more
    # than one (#53 has two), and a PR may serve an issue the plan does not
    # track, which is why the row carries the ticket it belongs to.
    rows: dict[int, tuple[dict, dict]] = {}
    for t in model["tickets"]:
        for pr in t.get("all_prs") or []:
            rows.setdefault(pr["number"], (pr, t))

    for number in sorted(rows, reverse=True):
        pr, t = rows[number]
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
        chk += f'<div class="sub">{e(pr.get("checks_newest") or "—")}</div>'
        stuck = ("critical" if pr.get("mergeable") == "CONFLICTING"
                 or pr.get("reviewDecision") == "CHANGES_REQUESTED"
                 else ("high" if pr.get("isDraft") else "medium"))
        a(f'<tr class="sev-{stuck}"><td class="num"><a href="{e(pr["url"])}">#{number}</a>'
          f'<span class="cap">{e(pr["title"][:64])} · for '
          f'<a href="{e(t["url"])}">#{t["id"]}</a></span></td>')
        a(f'<td>@{e((pr.get("author") or {}).get("login"))}</td><td>{merge_pill}</td>'
          f'<td>{rev_html}</td><td>{chk}</td><td class="sub">{e(pr["updatedAt"][:10])}</td></tr>')
    a('</table></div></div>')

    # ---- ADR ledger
    a('<h2>ADR ledger</h2>')
    a('<div class="lede">Status read from <span class="mono">docs/decisions.md</span> on main, '
      'not from any branch. Phase 3 ends with these decided.</div>')
    a('<div class="card"><div class="scroll"><table>')
    a('<tr><th>ADR</th><th>On main</th><th>Needs</th></tr>')
    for w in plan["adr_watch"]:
        cur = main["adr"].get(w["id"], "?")
        ok = cur.lower().startswith(w["want"].lower())
        a(f'<tr><td class="num">{MARK[DONE if ok else NOT_DONE]} {e(w["id"])}'
          f'<span class="cap">{e(w["name"])}</span></td>'
          f'<td><span class="pill {"ok" if ok else "idle"}">{e(cur)}</span></td>'
          f'<td class="sub">{e(w["gate"])}</td></tr>')
    a('</table></div></div>')

    # ---- risks
    a('<h2>Risks the plan named</h2>')
    a('<div class="lede">Straight from plan §7, with what has actually happened to each.</div>')
    a('<div class="card">')
    for r in sorted(plan["risks"], key=lambda x: 0 if x["status"] == "materialised" else 1):
        pill = ('<span class="pill bad">materialised</span>' if r["status"] == "materialised"
                else '<span class="pill warn">watch</span>')
        a('<div class="risk">')
        a(f'<div>{pill}</div>')
        a(f'<div><div class="what">{e(r["text"])}</div>'
          f'<div class="ev"><b>Now:</b> {e(r["evidence"])}<br>'
          f'<b>Mitigation:</b> {e(r["mitigation"])}</div></div>')
        a('</div>')
    a('</div>')

    a('<footer>')
    a(f'Generated by <code>generate.py</code> on the orphan <code>phase-3-dashboard</code> branch. '
      f'Static plan model: <code>plan.json</code>. Live state read via <code>gh</code> at {e(now)}.<br>'
      f'Nothing here is hand-maintained except <code>plan.json</code>, which changes only when the '
      f'plan or a ticket\'s stated dependency changes. Source of truth for the plan itself remains '
      f'<code>{e(p["plan_doc"])}</code> on main.')
    a('</footer></div>')
    return "\n".join(O)


def main() -> int:
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    issues = fetch_issues()
    prs = fetch_prs()
    enrich_open_prs(prs)
    main_state = fetch_main_state()

    model = build(plan, issues, prs, main_state)
    queue = action_queue(model, plan)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # An explicit LF newline on every write: Python's text mode would otherwise
    # emit CRLF on Windows, and update.sh decides whether to commit by diffing
    # these files. A platform-dependent line ending would make every run on a
    # Windows host look like a change, and the routine would commit daily noise.
    def emit(name: str, text: str) -> None:
        with open(HERE / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    emit("index.html", render_html(plan, model, queue, main_state, now))
    emit("STATUS.md", render_markdown(plan, model, queue, main_state, now))
    emit("snapshot.json", json.dumps(
        {"generated": now, "main": main_state,
         "tickets": [{k: v for k, v in t.items() if k != "pr"} | {
             "pr": t["pr"]["number"] if t.get("pr") else None} for t in model["tickets"]],
         "milestones": model["milestones"]},
        indent=2, ensure_ascii=False, default=str))

    done = sum(1 for ms in model["milestones"] for g in ms["gates"] if g["status"] == DONE)
    total = sum(len(ms["gates"]) for ms in model["milestones"])
    print(f"wrote index.html, STATUS.md, snapshot.json — {done}/{total} gates met, "
          f"{sum(1 for t in model['tickets'] if t['state']=='ready')} ready, "
          f"{sum(1 for t in model['tickets'] if t['state']=='blocked')} blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
