"""Synthetic checks for generate.py's "who owes an answer" derivation.

    python check_owed.py [path to generate.py]

Exit 0 when every check holds, 1 with the failing check named otherwise. The generator
defaults to the one beside this file; a path lets a mutated copy be pointed at instead,
which is how each guard was shown to be load-bearing (README, "Verification"). Reads
nothing from GitHub and writes nothing.
"""
import importlib.util
import sys
import traceback
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("gen_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = load(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / "generate.py")
checks = []


def check(fn):
    checks.append(fn)
    return fn


def user(login):
    return {"__typename": "User", "login": login}


def post(login, at, body, url, edited=None, bot=False, **kw):
    return {"author": {"__typename": "Bot" if bot else "User", "login": login},
            "createdAt": at, "lastEditedAt": edited, "body": body, "url": url, **kw}


# ---- task_items -----------------------------------------------------------

@check
def task_list_forms():
    body = "- [ ] @A one\n* [x] two\n+ [X] three\n1. [ ] four\n  - [ ] nested\n-[ ] not a task\n- [ ]\n"
    assert g.task_items(body) == [(False, "@A one"), (True, "two"), (True, "three"),
                                  (False, "four"), (False, "nested")], g.task_items(body)


@check
def fences_quotes_and_comments_are_skipped():
    body = ("```\n- [ ] @A in code\n```\n"
            "~~~\n```\n- [ ] @A still in the tilde fence\n~~~\n"
            "> - [ ] @A quoted\n"
            "<!-- - [ ] @A hidden\n- [ ] @A hidden too -->\n"
            "- [ ] @A live\n")
    assert g.task_items(body) == [(False, "@A live")], g.task_items(body)


# ---- addressees -----------------------------------------------------------

@check
def leading_mentions_are_the_addressees():
    cases = {
        "@BurakOztekin runs the desktop runbook": (["BurakOztekin"], "runs the desktop runbook"),
        "@A and @B confirm": (["A", "B"], "confirm"),
        "@A, @B: do X": (["A", "B"], "do X"),
        "@A ve @B onaylar": (["A", "B"], "onaylar"),
        "@A @B confirm": (["A", "B"], "confirm"),
        "@A/@B & @C check": (["A", "B", "C"], "check"),
        "@A: the cell stays": (["A"], "the cell stays"),
    }
    for text, want in cases.items():
        assert g.addressees(text) == want, (text, g.addressees(text))


@check
def suffixed_or_mid_sentence_mentions_address_nobody():
    for text in ("@bengisucvd's skip-rule outcome is known",
                 "@BurakOztekin'ın onayı",
                 "@A’s review is landed",
                 "@A and @B's review",
                 "Runbook for @A posted",
                 "Owner reviews: @A, @B"):
        assert g.addressees(text)[0] == [], (text, g.addressees(text))


# ---- owed_answers ---------------------------------------------------------

M, B, Be = "mertefesensoy", "BurakOztekin", "bengisucvd"


def conv():
    issue = {
        "number": 1, "title": "An issue", "url": "https://x/issues/1",
        **post(M, "2026-10-01T10:00:00Z",
               "- [ ] @BurakOztekin runs X on [the desktop](https://x/y)\n"
               "- [x] @BurakOztekin did Y\n- [ ] @stranger does Z\n"
               "- [ ] @yigit-arda writes W\n- [ ] @mertefesensoy sends it\n"
               "- [ ] @bengisucvd and @BurakOztekin confirm V\n",
               "https://x/issues/1", edited="2026-10-20T09:00:00Z"),
        "comments": {"totalCount": 3, "nodes": [
            post("github-actions", "2026-10-02T00:00:00Z", "- [ ] @BurakOztekin bot ask",
                 "https://x/issues/1#c1", bot=True),
            post(B, "2026-10-21T08:00:00Z", "on it", "https://x/issues/1#c2"),
            post(Be, "2026-10-03T08:00:00Z", "- [ ] @mertefesensoy answers this\n",
                 "https://x/issues/1#c3", edited="2026-10-03T09:00:00Z"),
        ]},
    }
    big = {"number": 3, "title": "Long thread", "url": "https://x/issues/3",
           **post(M, "2026-10-01T00:00:00Z", "", "https://x/issues/3"),
           "comments": {"totalCount": 150, "nodes": []}}
    pr = {
        "number": 2, "title": "A PR", "url": "https://x/pull/2", "isDraft": False,
        **post(Be, "2026-10-01T00:00:00Z", "", "https://x/pull/2"),
        "comments": {"totalCount": 0, "nodes": []},
        "reviews": {"totalCount": 2, "nodes": [
            post(B, "2026-10-08T00:00:00Z", "", "https://x/pull/2#r1",
                 state="CHANGES_REQUESTED", submittedAt="2026-10-08T00:00:00Z"),
            post(M, "2026-10-09T00:00:00Z", "", "https://x/pull/2#r2",
                 state="PENDING", submittedAt=None),
        ]},
        "reviewRequests": {"nodes": [
            {"requestedReviewer": user(B)}, {"requestedReviewer": user(M)},
            {"requestedReviewer": {"__typename": "Team"}},
            {"requestedReviewer": user("Copilot")},
        ]},
        "timelineItems": {"nodes": [
            {"createdAt": "2026-10-05T00:00:00Z", "actor": {"login": M}, "requestedReviewer": {"login": B}},
            {"createdAt": "2026-10-10T00:00:00Z", "actor": {"login": Be}, "requestedReviewer": {"login": B}},
            {"createdAt": "2026-10-12T00:00:00Z", "actor": {"login": M}, "requestedReviewer": {"login": M}},
            {},
        ]},
    }
    return {"issues": [issue, big], "prs": [pr]}


def owed():
    return g.owed_answers(conv(), "2026-10-23")


def find(who, kind, contains=""):
    hits = [x for x in owed()["asks"] if x["who"] == who and x["kind"] == kind and contains in x["text"]]
    assert len(hits) == 1, (who, kind, contains, [(x["who"], x["kind"], x["text"]) for x in owed()["asks"]])
    return hits[0]


@check
def checkbox_ask_dates_from_the_edit_and_sees_later_posts():
    x = find(B, "checkbox", "runs X")
    assert x["text"] == "runs X on the desktop", x["text"]
    assert (x["since"], x["posted"], x["lower_bound"], x["days"]) == ("2026-10-20", "2026-10-01", True, 3), x
    assert x["by"] == M and x["last_here"] == "2026-10-21", x
    assert "has posted there since, on 2026-10-21" in g.ask_line(x), g.ask_line(x)
    assert "since 2026-10-20 or earlier (3 days or more)" in g.ask_line(x), g.ask_line(x)


@check
def same_day_edit_is_not_a_lower_bound():
    x = find(M, "checkbox", "answers this")
    assert (x["since"], x["lower_bound"]) == ("2026-10-03", False), x


@check
def ticked_stranger_and_bot_items_are_not_asks():
    texts = [x["text"] for x in owed()["asks"]]
    assert "did Y" not in texts and "does Z" not in texts and "bot ask" not in texts, texts


@check
def former_member_ask_is_kept_and_flagged():
    x = find("yigit-arda", "checkbox", "writes W")
    assert x["former"] is True


@check
def self_addressed_item_is_an_own_checklist():
    x = find(M, "checkbox", "sends it")
    assert g.ask_parts(x)["by"] == "own checklist"


@check
def co_addressed_item_owed_by_each():
    a, b = find(Be, "checkbox", "confirm V"), find(B, "checkbox", "confirm V")
    assert a["others"] == [B] and b["others"] == [Be], (a["others"], b["others"])


@check
def standing_changes_requested_is_a_re_review_from_the_latest_request():
    x = find(B, "re-review")
    assert x["since"] == "2026-10-10" and x["by"] == Be, x
    assert "CHANGES_REQUESTED from 2026-10-08 still stands" in x["text"], x["text"]


@check
def pending_draft_review_does_not_count_as_a_review():
    x = find(M, "review")
    assert x["text"] == "Review PR #2" and x["since"] == "2026-10-12", x
    assert g.ask_parts(x)["by"] == "self-requested"


@check
def teams_and_outsiders_are_not_tracked():
    assert {x["who"] for x in owed()["asks"]} <= {M, B, Be, "yigit-arda"}


@check
def truncated_thread_is_reported():
    assert owed()["truncated"] == ["issue #3: 0 of 150 comments read"], owed()["truncated"]


@check
def ordering_is_team_order_then_oldest():
    who = [x["who"] for x in owed()["asks"]]
    order = [*g.TEAM_ORDER, "yigit-arda"]
    assert who == sorted(who, key=order.index), who
    mine = [x["since"] for x in owed()["asks"] if x["who"] == B]
    assert mine == sorted(mine), mine


# ---- history ----------------------------------------------------------------

@check
def owed_counts_move_in_day_by_day_only_when_both_days_measured():
    plan = {"tickets": [], "people": {B: {"name": "Burak"}}}
    base = {"gates_done": 1, "gates_total": 2, "milestones": {}, "tickets": {}, "adr": {},
            "main_sha": "x"}
    old = dict(base)
    cur = {**base, "owed": {B: 2}}
    assert g.day_events(old, cur, plan) == [], g.day_events(old, cur, plan)
    prev = {**base, "owed": {B: 4}}
    assert g.day_events(prev, cur, plan) == ["Burak owes 2 answers (was 4)"], g.day_events(prev, cur, plan)


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
