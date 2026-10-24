"""Synthetic checks for generate.py's phase-4 plan rules: gates, lanes, owners, delivery.

    python check_plan.py [path to generate.py]

Exit 0 when every check holds, 1 with the failing check named otherwise. The generator
defaults to the one beside this file; a path lets a mutated copy be pointed at instead,
which is how each guard was shown to be load-bearing (README, "Verification"). Reads
nothing from GitHub and writes nothing outside a temporary folder.
"""
import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("gen_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = load(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / "generate.py")
checks = []
M, B, S, H = "mertefesensoy", "BurakOztekin", "bengisucvd", "BahaJarad"


def check(fn):
    checks.append(fn)
    return fn


def plan(tickets=(), gates=None, lanes=None, planned=()):
    return {
        "phase": {"name": "Phase X", "goal": "g", "repo": "r", "plan_doc": "d.md",
                  "plan_ref": "b", "plan_sha": "abc12345", "plan_written": "2026-10-23",
                  "start": "2026-11-01", "milestone": 2, "history_dir": "h"},
        "people": {M: {"name": "Mert"}, B: {"name": "Burak"}, S: {"name": "Bengisu"},
                   H: {"name": "Baha"},
                   "yigit-arda": {"name": "Yigit", "role": "was @yigit-arda until 2026-10-16"}},
        "lanes": lanes or [
            {"id": "1", "name": "one", "rank": 0},
            {"id": "2", "name": "two", "rank": 2, "rank_after": {"gate": "L1", "rank": 0},
             "held_note": "Held until L1."}],
        "gates": gates if gates is not None else [
            {"id": "L1", "lane": "1", "name": "g1", "text": "t",
             "conditions": [{"text": "c", "check": {"kind": "task_ticked", "issue": 1, "starts": "L1"}}]},
            {"id": "L2", "lane": "1", "name": "g2", "text": "t",
             "conditions": [{"text": "c", "check": {"kind": "issue_closed", "id": 1}}]}],
        "tickets": list(tickets), "planned": list(planned), "parked": [], "adr_watch": [], "risks": [],
    }


def ticket(n, owner, lane="1", **kw):
    return {"id": n, "short": f"t{n}", "owner": owner, "lane": lane, "hard_deps": [],
            "soft_deps": [], "extra_blockers": [], "why_now": f"why {n}", **kw}


def issue(n, state="OPEN", owner=None, prio=None):
    return {"number": n, "state": state, "title": f"issue {n}", "url": f"u{n}",
            "assignees": [{"login": owner}] if owner else [],
            "labels": [{"name": f"priority:{prio}"}] if prio else []}


def pr(n, author, closes, state="OPEN", merged=None):
    return {"number": n, "state": state, "title": f"pr {n}", "headRefName": f"b{n}",
            "updatedAt": "2026-10-23", "createdAt": "2026-10-01", "mergedAt": merged,
            "author": {"login": author}, "closingIssuesReferences": [{"number": closes}],
            "mergeable": "MERGEABLE", "isDraft": False, "reviewDecision": "REVIEW_REQUIRED",
            "latest_reviews": [], "url": f"p{n}"}


def ctx(body="", doc_sha="abc12345ffff", adr=None, milestones=None):
    return {"sha": "x", "date": "d", "adr": adr or {}, "adr_title": {}, "paths": {},
            "milestones": milestones or {}, "bodies": {1: body},
            "plan_doc": None if doc_sha is None else {"sha": doc_sha, "date": "2026-10-23", "ref": "b"}}


def model(p, issues, prs, c, asks=()):
    m = g.build(p, issues, prs, c)
    m["owed"] = {"asks": list(asks), "truncated": []}
    return m


def status(chk, c, issues=None, prs=None):
    return g.check_status(chk, issues or {}, prs or {}, c, {})[0]


@check
def a_split_adr_status_is_not_accepted():
    assert g.adr_met("Accepted", "Accepted")
    assert g.adr_met("Accepted (2026-10-21)", "Accepted")
    assert not g.adr_met("Accepted on the constraint · Open on variance-injection design", "Accepted")
    assert not g.adr_met("Open", "Accepted")


@check
def open_slash_deferred_has_not_left_deferred():
    assert not g.adr_left("Deferred", "Deferred")
    assert not g.adr_left("Open / Deferred", "Deferred")
    assert g.adr_left("Accepted", "Deferred")


@check
def an_adr_missing_from_the_ledger_never_passes_a_not_test():
    assert status({"kind": "adr_status", "id": "ADR-099", "not": "Deferred"}, ctx()) == g.UNKNOWN


@check
def task_ticked_reads_absent_unticked_ticked_and_ignores_fences():
    chk = {"kind": "task_ticked", "issue": 1, "starts": "L1"}
    assert status(chk, ctx("")) == g.UNKNOWN
    assert status(chk, ctx("- [ ] L1: job 1 read")) == g.NOT_DONE
    assert status(chk, ctx("- [x] L1: job 1 read")) == g.DONE
    assert status(chk, ctx("```\n- [x] L1: a template\n```")) == g.UNKNOWN
    assert status(chk, ctx("- [x] L10: another gate")) == g.UNKNOWN
    assert status(chk, ctx("- [x] L1")) == g.DONE


@check
def milestone_closed_reads_state_and_says_the_counts():
    chk = {"kind": "milestone_closed", "id": 1}
    c = ctx(milestones={1: {"title": "P3", "state": "open", "open": 13, "closed": 21}})
    st, note = g.check_status(chk, {}, {}, c, {})
    assert st == g.NOT_DONE and "13 open and 21 closed" in note, note
    c["milestones"][1]["state"] = "closed"
    assert status(chk, c) == g.DONE
    assert status({"kind": "milestone_closed", "id": 9}, c) == g.UNKNOWN


@check
def a_gate_of_unknowns_is_unknown_not_red():
    U, N, P, D = g.UNKNOWN, g.NOT_DONE, g.PARTIAL, g.DONE
    assert g.gate_status([U]) == U
    assert g.gate_status([U, N]) == N
    assert g.gate_status([P, U]) == P
    assert g.gate_status([D, U]) == P
    assert g.gate_status([D, D]) == D


@check
def done_by_delivers_a_ticket_whose_issue_stays_open():
    p = plan([ticket(63, H, done_by={"kind": "pr_merged", "id": 113})])
    issues = {1: issue(1), 63: issue(63, owner=H)}
    m = model(p, issues, {113: pr(113, H, 0, state="MERGED", merged="2026-10-23T17:45:20Z")}, ctx())
    t = m["tickets"][0]
    assert t["state"] == "done" and t["delivered_open"], t["state"]
    m = model(p, issues, {113: pr(113, H, 0)}, ctx())
    assert m["tickets"][0]["state"] != "done"


@check
def an_owner_off_the_team_refuses_to_render():
    for t in (ticket(5, "yigit-arda"),
              ticket(5, M, co_owners=[{"login": "yigit-arda", "action": "x", "why": "y"}])):
        try:
            g.lint_plan(plan([t]))
        except SystemExit:
            continue
        raise AssertionError(f"accepted {t}")


@check
def a_former_member_in_free_text_warns_but_the_people_table_does_not():
    assert g.lint_plan(plan([ticket(5, M)])) == []
    w = g.lint_plan(plan([ticket(5, M, why_now="@yigit-arda depends on the answer")]))
    assert len(w) == 1 and "yigit-arda" in w[0], w


@check
def an_owner_github_does_not_assign_is_a_warning():
    p = plan([ticket(5, M)])
    w = model(p, {1: issue(1), 5: issue(5, owner=B)}, {}, ctx())["warnings"]
    assert any("@mertefesensoy the owner of #5" in x for x in w), w
    w = model(p, {1: issue(1), 5: issue(5, owner=M)}, {}, ctx())["warnings"]
    assert not any("owner of #5" in x for x in w), w


@check
def lane_two_ranks_behind_lane_one_until_l1_is_met():
    p = plan([ticket(5, B, lane="1"), ticket(6, B, lane="2")])
    issues = {1: issue(1), 5: issue(5, owner=B, prio="low"), 6: issue(6, owner=B, prio="critical")}
    q = g.action_queue(model(p, issues, {}, ctx("- [ ] L1: x")), p)[B]
    assert [a["ticket"]["id"] for a in q] == [5, 6], [a["action"] for a in q]
    assert "Held until L1." in q[1]["why"], q[1]["why"]
    q = g.action_queue(model(p, issues, {}, ctx("- [x] L1: x")), p)[B]
    assert [a["ticket"]["id"] for a in q] == [6, 5], [a["action"] for a in q]
    assert "Held until L1." not in q[0]["why"]


@check
def a_co_owners_row_reads_their_own_pr_not_the_owners():
    co = [{"login": B, "action": "offline half", "why": "dry run gates it"}]
    p = plan([ticket(125, M, co_owners=co)])
    issues = {1: issue(1), 125: issue(125, owner=M)}
    q = g.action_queue(model(p, issues, {126: pr(126, M, 125)}, ctx()), p)
    assert q[M][0]["kind"] == "in_review" and "PR #126" in q[M][0]["action"]
    assert q[B][0]["kind"] == "ready", q[B][0]
    q = g.action_queue(model(p, issues, {126: pr(126, M, 125), 127: pr(127, B, 125)}, ctx()), p)
    assert "PR #127" in q[B][0]["action"] and "PR #126" in q[M][0]["action"], (q[B][0], q[M][0])


@check
def a_pending_review_on_a_pr_a_ticket_waits_on_becomes_the_reviewers_row():
    t = ticket(122, H, hard_deps=[{"kind": "pr", "id": 121, "what": "the draft"}])
    p = plan([t])
    issues = {1: issue(1), 122: issue(122, owner=H)}
    ask = {"who": S, "kind": "review", "since": "2026-10-23",
           "thread": {"kind": "PR", "number": 121, "title": "", "url": ""}}
    gone = {**ask, "who": "yigit-arda"}
    m = model(p, issues, {121: pr(121, M, 0)}, ctx(), asks=[ask, gone])
    assert m["tickets"][0]["state"] == "blocked"
    q = g.action_queue(m, p)
    assert q[S][0]["action"] == "Review PR #121: it holds #122", q[S]
    assert "yigit-arda" not in q and H not in q, q.keys()


@check
def a_later_gate_met_before_an_earlier_one_is_flagged():
    m = model(plan(), {1: issue(1, state="CLOSED")}, {}, ctx(""))
    assert any("L2 reads met while L1" in w for w in m["warnings"]), m["warnings"]
    m = model(plan(), {1: issue(1)}, {}, ctx(""))
    assert not any("reads met while" in w for w in m["warnings"]), m["warnings"]


@check
def a_moved_or_missing_plan_document_is_flagged():
    issues = {1: issue(1)}
    assert not any("plan" in w.lower() for w in model(plan(), issues, {}, ctx())["warnings"])
    w = model(plan(), issues, {}, ctx(doc_sha="ffff0000"))["warnings"]
    assert any("changed at ffff0000" in x for x in w), w
    w = model(plan(), issues, {}, ctx(doc_sha=None))["warnings"]
    assert any("was not found" in x for x in w), w


@check
def history_reads_only_its_own_phase_folder_and_records():
    p = plan()
    with tempfile.TemporaryDirectory() as tmp:
        here, g.HERE = g.HERE, Path(tmp)
        try:
            (Path(tmp) / "h").mkdir()
            (Path(tmp) / "2026-10-31.json").write_text(json.dumps({"date": "2026-10-31"}))
            (Path(tmp) / "h" / "2026-11-01.json").write_text(json.dumps({"phase": "Phase X", "date": "2026-11-01"}))
            (Path(tmp) / "h" / "2026-11-02.json").write_text(json.dumps({"phase": "Phase 3", "date": "2026-11-02"}))
            got = [r["date"] for r in g.load_history(p)]
        finally:
            g.HERE = here
    assert got == ["2026-11-01"], got


failed = 0
for fn in checks:
    try:
        fn()
    except Exception:
        failed += 1
        print(f"FAIL {fn.__name__}")
        traceback.print_exc(limit=1)
print(f"{len(checks) - failed}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
