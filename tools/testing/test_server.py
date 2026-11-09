"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python tools/testing/test_server.py          -> prints ALL OK, or the first failure   (no -I: reads anvil.yaml)

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

C_row = M["common"].row_by_id

# ---------------------------------------------------------------------------------- gates (pure)
G = M["Gates"]
assert G.score({})["complete"] is False
assert G.score({g: 0 for g in G.GATE_IDS})["points"] == 1
assert G.score({g: 0 for g in G.GATE_IDS})["fit"] == "solo"
s = G.score(dict({g: 0 for g in G.GATE_IDS}, risk=3))
assert s["points"] == 5 and s["floored"], "a red answer raises the floor"
s = G.score(dict({g: 1 for g in G.GATE_IDS}, clarity=3))
assert s["verdict"] == "spike" and s["fit"] == "human"
assert G.score({g: 3 for g in G.GATE_IDS})["verdict"] == "spike", "unknown clarity beats size"
s = G.score(dict({g: 3 for g in G.GATE_IDS}, clarity=2))
assert s["points"] == 21 and s["verdict"] == "split"
assert G.clean({"scope": 7, "risk": True, "verify": 2, "bogus": 1}) == {"verify": 2}
for pts in (1, 2, 3, 5, 8, 13, 21):  # the demo generator can hit every rung
    a = M["DemoData"].gates_for(__import__("random").Random(pts), pts)
    assert G.score(a)["points"] == pts, pts

# ---------------------------------------------------------------------------------- demo data + crews
as_user(None)
assert denied("my_crews")
as_user(ana)
crews = call("my_crews")["crews"]
assert M["DemoData"].state() == "loaded", "demo loads on first visit"
keys = [c["key"] for c in crews]
assert keys == ["NOVA", "PIXL"] and all(c["demo"] and c["role"] == "sandbox" for c in crews), keys
nova = [c for c in crews if c["key"] == "NOVA"][0]["id"]
pixl = [c for c in crews if c["key"] == "PIXL"][0]["id"]
gc = call("get_crew", nova)
assert gc["crew"]["level"] == 4 and gc["maturity"]["next"] is None and gc["crew"]["join_code"] is None
assert len(gc["crew"]["agents"]) == 3 and gc["crew"]["can_admin"] is False
mp = call("get_crew", pixl)["maturity"]["next"]
assert mp["n"] == 2 and mp["passed"] == 4 and not mp["eligible"], mp
assert denied("update_crew", nova, {"name": "Hijacked"}), "sandbox guests can't rename demo crews"
ok(call("update_crew", pixl, {"wip": {"doing": 4}}))
assert denied("delete_crew", nova, "NOVA")

bad(call("create_crew", "x"))
bad(call("create_crew", "Rocket", "9X"))
mine = ok(call("create_crew", "Team Rocket", "rkt!", "Blast off", 3))["crew"]
assert mine["key"] == "RKT" and mine["level"] == 1 and mine["role"] == "owner", mine
rkt = mine["id"]
assert [c["key"] for c in call("my_crews")["crews"]][0] == "RKT", "own crews first"
code = call("get_crew", rkt)["crew"]["join_code"]
assert len(code) == 6
as_user(bob)
assert denied("get_board", rkt), "outsiders can't see a crew"
bad(call("join_crew", "NOPE00"))
ok(call("join_crew", code.lower()))
assert call("get_crew", rkt)["crew"]["role"] == "member"
assert denied("update_crew", rkt, {"name": "Bob's crew"}), "members can't rename"
ok(call("update_crew", rkt, {"sprint_days": 7, "dod": ["Tests pass", ""], "agent_rules": "Be nice."}))
bad(call("update_crew", rkt, {"sprint_days": 5}))
assert denied("new_join_code", rkt)
as_user(ana)
c2 = ok(call("new_join_code", rkt))["code"]
assert c2 != code
bad(call("leave_crew", rkt), "owners can't leave")

# ---------------------------------------------------------------------------------- cards
bad(call("quick_add", rkt, "x"))
r = ok(call("quick_add", rkt, "Fix login timeout #bug !1 ~3 @bob #auth"))["card"]
assert r["key"] == "RKT-1" and r["type"] == "bug" and r["priority"] == 1 and r["points"] == 3 and r["labels"] == ["auth"], r
assert r["assignee"]["name"] == "Bob Stone", r["assignee"]
c1 = r["id"]
r = ok(call("quick_add", rkt, "Write the onboarding guide @me"))["card"]
assert r["assignee"]["name"] == "Ana" and r["points"] is None
c2id = r["id"]
b = call("get_backlog", rkt)
assert [c["key"] for c in b["cards"]] == ["RKT-1", "RKT-2"] and b["sprints"] == [] and b["gates"]["gates"]
ok(call("rank_card", c2id, c1))
assert [c["key"] for c in call("get_backlog", rkt)["cards"]] == ["RKT-2", "RKT-1"], "re-ranked"
card = ok(call("get_card", rkt, "RKT-1"))["card"]
assert card["gate"]["complete"] is False and card["readiness"]["ready"] is False
bad(call("get_card", rkt, "NOVA-1"))
bad(call("update_card", c1, {"title": "x"}))
bad(call("update_card", c1, {"type": "epic"}))
bad(call("update_card", c1, {"points": 4}))
bad(call("update_card", c1, {"assignee": {"kind": "user", "id": admin.get_id()}}), "assignees must be in the crew")
long_body = "The login form times out after 30 seconds on slow networks. Raise it and show a retry button."
card = ok(call("update_card", c1, {"body": long_body, "acceptance": [{"text": "Timeout is 90 s"}, "Retry button shows", {"text": ""}],
                                   "links": [{"label": "Bad", "url": "javascript:alert(1)"}, {"url": "https://example.com/pr/1"}],
                                   "labels": ["auth", " ", "login"], "blocked": True, "blocked_reason": "Waiting for design"}))["card"]
assert len(card["acceptance"]) == 2 and len(card["links"]) == 1 and card["labels"] == ["auth", "login"] and card["blocked"]
bad(call("estimate_card", c1, {"scope": 1}))
est = ok(call("estimate_card", c1, {"scope": 1, "clarity": 0, "novelty": 0, "deps": 0, "risk": 1, "verify": 0}))
assert est["gate"]["points"] == 2 and est["card"]["points_src"] == "gates" and est["gate"]["fit"] == "solo"
assert est["card"]["readiness"]["passed"] == 5, "blocked is the only failing check"
ok(call("update_card", c1, {"blocked": False}))
assert ok(call("get_card", rkt, "1"))["card"]["agent_ready"] is True
ok(call("add_comment", c1, "Looks good"))
bad(call("add_comment", c1, "  "))
mv = ok(call("move_card", c1, "ready"))
bad(call("move_card", c1, "limbo"))
board = call("get_board", rkt)
assert [c["key"] for c in board["columns"]["ready"]] == ["RKT-1"] and board["sprint"] is None and board["wip"]["doing"] == 4
ok(call("move_card", c1, "doing"))
row = T.cards.get_by_id(c1)
assert row["started"] is not None and row["done_at"] is None
ok(call("move_card", c1, "done"))
assert T.cards.get_by_id(c1)["done_at"] is not None
ok(call("move_card", c1, "review"))
assert T.cards.get_by_id(c1)["done_at"] is None, "leaving Done clears done_at"
evs = ok(call("get_card", rkt, "RKT-1"))["events"]
assert any(e["kind"] == "comment" for e in evs) and any(e["kind"] == "move" for e in evs)
brief = ok(call("agent_brief", c1, "https://my.app/_/api"))["markdown"]
assert "# RKT-1" in brief and "Timeout is 90 s" in brief and "https://my.app/_/api/agent/submit" in brief and "Be nice." in brief and "Tests pass" in brief
as_user(admin)
assert denied("get_card", rkt, "RKT-1") and denied("update_card", c1, {"title": "Nope nope"}) and denied("move_card", c1, "done")
as_user(ana)

# ---------------------------------------------------------------------------------- levels
bad(call("set_level", rkt, 3), "one step at a time")
bad(call("set_level", rkt, 2), "not eligible without force")
lv = ok(call("set_level", rkt, 2, True))
assert lv["forced"] and call("get_crew", rkt)["crew"]["level_log"][-1]["forced"] is True
bad(call("set_level", rkt, 9))

# ---------------------------------------------------------------------------------- sprints
ok(call("move_card", c2id, "backlog"))
sp = ok(call("create_sprint", rkt, "Ship the login fix"))["sprint"]
assert sp["name"] == "Sprint 1" and sp["state"] == "planned"
bad(call("start_sprint", sp["id"]), "empty sprints can't start")
ok(call("update_card", c2id, {"sprint_id": sp["id"]}))
assert T.cards.get_by_id(c2id)["status"] == "ready", "adding to a sprint makes a card Ready"
ok(call("quick_add", rkt, "Polish the login copy ~2", sp["id"]))
started = ok(call("start_sprint", sp["id"]))
assert started["sprint"]["state"] == "active" and started["sprint"]["committed"] == 2 and started["unestimated"] == 1
bad(call("start_sprint", sp["id"]))
board = call("get_board", rkt)
assert board["sprint"]["name"] == "Sprint 1" and sum(len(v) for v in board["columns"].values()) == 2, "the board shows the sprint"
bl = call("get_backlog", rkt)
assert bl["sprints"][0]["state"] == "active" and len(bl["sprints"][0]["cards_list"]) == 2
polish = [c for c in bl["sprints"][0]["cards_list"] if c["points"] == 2][0]
ok(call("move_card", polish["id"], "done"))
planned2 = ok(call("create_sprint", rkt))["sprint"]
bad(call("save_retro", planned2["id"], {"louder": ["x"]}), "planned sprints have no retro")
closed = ok(call("close_sprint", sp["id"], "next"))
assert closed["done_points"] == 2 and closed["carried"] == 1 and closed["carried_to"] == "Sprint 2", closed
bad(call("close_sprint", sp["id"]))
retro = ok(call("save_retro", sp["id"], {"louder": ["Pairing", ""], "mute": ["Meetings"], "remix": [], "actions": [{"text": "Fewer meetings", "done": 1}, {"text": ""}]}))["retro"]
assert retro["louder"] == ["Pairing"] and retro["actions"] == [{"text": "Fewer meetings", "done": True}]
gs = call("get_sprint", sp["id"])
assert gs["sprint"]["retro"]["mute"] == ["Meetings"] and gs["burndown"]
s2 = [s for s in call("get_plan", rkt)["sprints"] if s["name"] == "Sprint 2"][0]
bad(call("delete_sprint", sp["id"]), "closed sprints stay")
ok(call("delete_sprint", s2["id"]))
assert T.cards.get_by_id(c2id)["sprint"] is None
as_user(bob)
ok(call("update_sprint", call("get_plan", rkt)["sprints"][0]["id"], {"goal": "Bob's goal"}))
as_user(admin)
assert denied("close_sprint", sp["id"]) and denied("create_sprint", rkt)
as_user(ana)

# ---------------------------------------------------------------------------------- plans + epics
plan = call("get_plan", nova)
assert plan["level"] == 4 and len(plan["velocity"]) == 8 and plan["active"]["name"] == "Sprint 9" and plan["active"]["burndown"]
assert len(plan["quarter"]["slots"]) == 6 and plan["quarter"]["epics"], "quarter forecast"
assert {e["confidence"] for e in plan["quarter"]["epics"]} >= {"safe", "nofit"}
assert len(plan["year"]["quarters"]) == 4 and any(q["over"] for q in plan["year"]["quarters"]), "an overbooked quarter in the demo"
pp = call("get_plan", pixl)
assert pp["capacity_source"].startswith("Kanban") and pp["velocity"] == []
bad(call("save_epic", rkt, None, {"title": "x"}))
bad(call("save_epic", rkt, None, {"title": "Login 2.0", "quarter": "2027-Q9"}))
bad(call("save_epic", rkt, None, {"title": "Login 2.0", "size": "XXL"}))
ep = ok(call("save_epic", rkt, None, {"title": "Login 2.0", "size": "L", "quarter": "2027-Q1"}))["epic"]
assert ep["remaining"] == 55 and ep["sized_by"] == "size"
ep2 = ok(call("save_epic", rkt, None, {"title": "Signup"}))["epic"]
ok(call("update_card", c1, {"epic_id": ep["id"]}))
ok(call("rank_epic", ep2["id"], "up"))
assert [e["title"] for e in call("get_plan", rkt)["epics"]] == ["Signup", "Login 2.0"]
ok(call("save_epic", rkt, ep["id"], {"status": "active", "color": M["Model"].COLORS[1]}))
bad(call("save_epic", rkt, ep["id"], {"color": "#123456"}))
bad(call("save_epic", nova, ep["id"], {"title": "Moved"}), "epics stay in their crew")
ok(call("delete_epic", ep2["id"]))
as_user(admin)
assert denied("get_plan", rkt) and denied("delete_epic", ep["id"]) and denied("save_epic", rkt, None, {"title": "Spy"})
as_user(ana)

# ---------------------------------------------------------------------------------- deck + insights
dk = call("get_deck", nova)
assert dk["sprint"]["name"] == "Sprint 9" and dk["ticker"] and dk["review"] and dk["stats"]["done"] > 50
assert any("review" in a["text"] for a in dk["alerts"]), dk["alerts"]
assert call("get_deck", pixl)["level"]["name"] == "KANBAN"
ins = call("get_insights", nova)
assert len(ins["throughput"]) == 12 and ins["p50"] and ins["p85"] >= ins["p50"] and len(ins["velocity"]) == 8 and len(ins["cfd"]) == 10
assert ins["gates"]["rows"] and ins["split"]["agent_points"] > 0
as_user(admin)
assert denied("get_deck", rkt) and denied("get_insights", rkt)
as_user(ana)

# ---------------------------------------------------------------------------------- agents
AG = M["Agents"]
bad(call("create_agent", rkt, "x"))
na = ok(call("create_agent", rkt, "Claude", "Claude Code", 1))
tok, aid = na["token"], na["agent"]["id"]
assert tok.startswith("aa_") and na["agent"]["token_hint"] == tok[-4:] and T.agents.get_by_id(aid)["token_hash"] != tok
bad(call("create_agent", rkt, "Claude"), "names are unique per crew")
assert call("get_agents", rkt)["agents"][0]["state"] == "idle"
# a card an agent can take: estimated solo, criteria, description, Ready
ready = ok(call("quick_add", rkt, "Add a remember-me checkbox"))["card"]["id"]
ok(call("update_card", ready, {"body": long_body, "acceptance": ["Checkbox shows", "Session lasts 30 days"]}))
ok(call("estimate_card", ready, {"scope": 1, "clarity": 0, "novelty": 1, "deps": 0, "risk": 0, "verify": 1}))
ok(call("move_card", ready, "ready"))
agent_row = T.agents.get_by_id(aid)
assert AG.agent_op(agent_row, "teleport")["ok"] is False
who = AG.agent_op(agent_row, "whoami")
assert who["crew"]["key"] == "RKT" and who["house_rules"] == "Be nice."
nx = AG.agent_op(agent_row, "next", base="https://x.app/_/api")
assert nx["card"]["key"] == "RKT-4" and "remember-me" in nx["card"]["brief"], nx
assert AG.agent_op(agent_row, "claim", {"key": "RKT-999"})["status"] == 404
assert AG.agent_op(agent_row, "claim", {"key": "RKT-2"})["status"] == 409, "only Ready cards"
cl = AG.agent_op(agent_row, "claim", {"key": "RKT-4"})
assert cl["ok"] and T.cards.get_by_id(ready)["status"] == "doing" and T.cards.get_by_id(ready)["assignee_agent"] == agent_row
ok(call("move_card", c2id, "ready"))
assert AG.agent_op(agent_row, "claim", {"key": "RKT-2"})["status"] == 409, "its own WIP limit"
assert AG.agent_op(agent_row, "log", {"key": "RKT-4", "text": ""})["ok"] is False
assert AG.agent_op(agent_row, "log", {"key": "RKT-4", "text": "Found the session code"})["ok"]
assert AG.agent_op(agent_row, "check", {"key": "RKT-4", "index": 5})["ok"] is False
assert AG.agent_op(agent_row, "check", {"key": "RKT-4", "index": 0})["acceptance"][0]["done"] is True
assert AG.agent_op(agent_row, "check", {"key": "RKT-2", "index": 0})["status"] == 403, "not its card"
assert AG.agent_op(agent_row, "submit", {"key": "RKT-4", "summary": "short"})["ok"] is False
sub = AG.agent_op(agent_row, "submit", {"key": "RKT-4", "summary": "Added the checkbox; tests pass.", "links": [{"label": "PR 7", "url": "https://example.com/pr/7"}]})
assert sub["ok"] and sub["warning"] and T.cards.get_by_id(ready)["status"] == "review" and T.cards.get_by_id(ready)["review_at"]
assert AG.agent_op(agent_row, "submit", {"key": "RKT-4", "summary": "Again and again"})["status"] == 409
pr = AG.agent_op(agent_row, "propose", {"title": "Rate-limit the login endpoint", "type": "task", "body": "Saw brute force risk."})
assert pr["ok"] and pr["card"]["labels"] == ["agent-proposed"] and pr["card"]["status"] == "backlog"
assert "RKT-4" in [c["key"] for c in AG.agent_op(agent_row, "cards", {"status": "review"})["cards"]]
assert AG.agent_op(agent_row, "cards", {"status": "nope"})["ok"] is False
assert call("get_agents", rkt)["review"][0]["key"] == "RKT-4"
ok(call("update_agent", aid, {"active": False}))
assert AG.agent_op(agent_row, "next")["status"] == 423, "paused agents can't work"
ok(call("update_agent", aid, {"active": True, "max_wip": 9, "name": "Claude Code"}))
assert T.agents.get_by_id(aid)["max_wip"] == 5
# the console runs the same operations by text
con = call("agent_console", aid, "help")
assert any(l.startswith("claim") for l in con["lines"])
con = call("agent_console", aid, "claim RKT-404")
assert con["result"]["ok"] is False and "No card" in con["result"]["error"]
con = call("agent_console", aid, "log RKT-4 waiting for review")
assert con["result"]["ok"]
# HTTP API with a real token
anvil.server.request.headers = {"Authorization": "Bearer " + tok}
anvil.server.request.body = None
resp = anvil.server.ENDPOINTS["/agent/whoami"]()
assert resp.status == 200 and json.loads(resp.body)["agent"]["name"] == "Claude Code"
anvil.server.request.headers = {"authorization": "Bearer aa_wrong"}
assert anvil.server.ENDPOINTS["/agent/next"]().status == 401
anvil.server.request.headers = {}
anvil.server.request.body = json.dumps({"key": "RKT-4", "text": "via http"})
resp = anvil.server.ENDPOINTS["/agent/log"](token=tok)
assert resp.status == 200, resp.body
anvil.server.request.body = json.dumps({"key": "RKT-404"})
assert anvil.server.ENDPOINTS["/agent/claim"](token=tok).status == 404
assert json.loads(anvil.server.ENDPOINTS["/agent/manifest"]().body)["ops"]
rot = ok(call("rotate_token", aid))
assert rot["token"] != tok and AG.agent_for_token(tok) is None and AG.agent_for_token(rot["token"]) is not None
# a human approves agent work
ok(call("move_card", ready, "done"))
assert T.cards.get_by_id(ready)["done_at"] is not None
as_user(admin)
assert denied("create_agent", rkt, "Spy") and denied("agent_console", aid, "next") and denied("rotate_token", aid) and denied("delete_agent", aid)
as_user(ana)
ok(call("move_card", c2id, "ready"))
ok(call("delete_agent", aid))
assert C_row(T.agents, aid) is None
assert any(e["text"].startswith("[Claude Code]") for e in T.events.search(actor_agent=None)), "the agent's events keep their text"
# demo agents work from the console too
claude_demo = [a for a in call("get_agents", nova)["agents"] if a["name"] == "Claude"][0]
assert call("agent_console", claude_demo["id"], "next")["result"]["ok"]

# ---------------------------------------------------------------------------------- board columns
as_user(ana)
team_row = T.teams.get_by_id(rkt)
cols = call("get_crew", rkt)["crew"]["columns"]
assert [c["id"] for c in cols] == ["ready", "doing", "review", "done"]
bad(call("save_columns", rkt, [{"id": "ready", "name": "Ready", "stage": "ready"}]), "every stage keeps a column")
bad(call("save_columns", rkt, [{"name": "", "stage": "ready"}] + cols[1:]))
bad(call("save_columns", rkt, "nope"))
newcols = ok(call("save_columns", rkt, cols[:1] + [{"id": "doing", "name": "Build", "stage": "doing"},
                                                   {"name": "Test", "stage": "doing", "wip": 1}] + cols[2:]))["columns"]
test_id = [c for c in newcols if c["name"] == "Test"][0]["id"]
assert [c["stage"] for c in newcols] == ["ready", "doing", "doing", "review", "done"] and test_id.startswith("c")
ok(call("move_card", c2id, "doing"))
assert T.cards.get_by_id(c2id)["column"] is None
bc = call("get_board", rkt)["board_columns"]
assert [len(c["cards"]) for c in bc if c["stage"] == "doing"] == [1, 0] and bc[1]["split"] and bc[2]["limit"] == 1, bc
ok(call("move_card", c2id, test_id))
assert T.cards.get_by_id(c2id)["column"] == test_id and T.cards.get_by_id(c2id)["status"] == "doing"
assert any("Build -> Test" in (e["text"] or "") for e in T.events.search(card=T.cards.get_by_id(c2id)))
assert ok(call("move_card", c1, test_id))["over_wip"] is True, "the column's own WIP limit counts"
bad(call("move_card", c2id, "nowhere"))
ok(call("save_columns", rkt, cols))
assert T.cards.get_by_id(c2id)["column"] is None, "cards of a removed column go to the stage's first column"
assert c2id in [c["id"] for c in call("get_board", rkt)["board_columns"][1]["cards"]]
ok(call("move_card", c2id, "ready"))
ok(call("move_card", c1, "review"))
as_user(admin)
assert denied("save_columns", rkt, cols)
as_user(ana)

# ---------------------------------------------------------------------------------- command palette search
assert call("search_cards", rkt, "rkt-2")["cards"][0]["key"] == "RKT-2"
assert call("search_cards", rkt, "remember")["cards"][0]["key"] == "RKT-4"
assert call("search_cards", rkt, "  ")["cards"] == []
as_user(admin)
assert denied("search_cards", rkt, "x")
as_user(ana)

# ---------------------------------------------------------------------------------- alerts
import anvil.email as EMAIL  # noqa: E402
import anvil.http as HTTP  # noqa: E402
assert len(T.alerts.search(team=team_row, kind="submitted")) == 1, "an agent's hand-in raised an alert"
al = call("get_alerts", rkt)
assert al["can_edit"] and al["member"] and al["settings"]["review_hours"] == 24 and al["history"]
for url in ("http://example.com/hook", "https://127.0.0.1/hook", "https://localhost/x", "https://box.internal/x", "https://10.0.0.8/x", "ftp://x.com"):
    bad(call("save_alerts", rkt, {"webhook": url}), url)
bad(call("save_alerts", rkt, {"review_hours": 0}))
bad(call("save_alerts", rkt, {"format": "fax"}))
bad(call("test_alerts", rkt), "no webhook yet")
ok(call("save_alerts", rkt, {"webhook": "https://hooks.example.com/T1/abc", "format": "slack", "review_hours": 2,
                             "kinds": {"wip": False}}))
HTTP.REPLIES["https://hooks.example.com/"] = "ok"
ok(call("test_alerts", rkt))
assert json.loads(HTTP.CALLS[-1]["data"])["text"].startswith("*AutoAgile // RKT")
ok(call("set_notify", rkt, True))
n_calls, n_mail = len(HTTP.CALLS), len(EMAIL.OUTBOX)
ok(call("update_card", c2id, {"blocked": True, "blocked_reason": "Waiting for the API key"}))
assert len(HTTP.CALLS) == n_calls + 1 and "blocked" in json.loads(HTTP.CALLS[-1]["data"])["text"]
assert len(EMAIL.OUTBOX) == n_mail + 1 and EMAIL.OUTBOX[-1]["to"] == "ana@example.com"
ok(call("update_card", c2id, {"blocked": False}))
T.cards.get_by_id(c1)["review_at"] = now - dt.timedelta(hours=5)
team_row["alerts_checked"] = None
call("get_deck", rkt)
waits = [a for a in call("get_alerts", rkt)["history"] if a["kind"] == "review_wait"]
assert len(waits) == 1 and waits[0]["card"]["key"] == "RKT-1" and waits[0]["sent"]["webhook"] == "sent", waits
assert M["Alerts"].sweep(team_row, force=True) == [], "a standing condition is announced once"
HTTP.REPLIES["https://hooks.example.com/"] = HTTP.HttpError(500)
fr = M["Alerts"].fire(team_row, "blocked", "blocked:test", "A test block")
assert fr["sent"]["webhook"].startswith("failed"), "a broken webhook never breaks the page"
bad(call("test_alerts", rkt))
HTTP.REPLIES["https://hooks.example.com/"] = "ok"
assert M["Alerts"].fire(team_row, "wip", "wip:x", "switched off") is None, "switched-off kinds are not recorded"
as_user(bob)
assert denied("save_alerts", rkt, {"review_hours": 5}) and denied("test_alerts", rkt)
assert call("get_alerts", rkt)["settings"]["webhook"] == "set", "members don't see the webhook address"
ok(call("set_notify", rkt, False))
as_user(ana)
assert denied("save_alerts", nova, {"review_hours": 5})
bad(call("set_notify", nova, True))
na_ = call("get_alerts", nova)
assert not na_["can_edit"] and len(na_["history"]) >= 3 and all(h["sent"].get("skipped") for h in na_["history"])
as_user(admin)
assert denied("get_alerts", rkt) and denied("set_notify", rkt, True)
bad(call("save_alerts", nova, {"webhook": "https://hooks.example.com/demo"}), "demo crews never send")
as_user(ana)

# ---------------------------------------------------------------------------------- requests
rq = call("get_requests", rkt)
code = rq["ask_code"]
assert len(code) == 8 and rq["requests"] == [] and rq["promise_days"] == 14 and rq["can_admin"]
as_user(admin)  # an outsider with the ask link
assert denied("get_requests", rkt)
bad(call("ask_page", "WRONGCOD"))
pg = ok(call("ask_page", code.lower()))
assert pg["crew"]["name"] == "Team Rocket" and pg["crew"]["id"] is None, "people with the link never get the crew id"
bad(call("submit_request", "Hi", "", None, code))
r1 = ok(call("submit_request", "Export the board as PDF", "For our weekly report.", None, code))["request"]
assert r1["votes"] == 1 and r1["voted"] and r1["mine"] and r1["due_in"] == 14 and not r1["overdue"]
bad(call("submit_request", "export the board as pdf", "", None, code), "a duplicate points to the open one")
assert denied("vote_request", r1["id"], True), "voting needs the link or the crew"
ok(call("vote_request", r1["id"], False, code))
assert T.requests.get_by_id(r1["id"])["votes"] == []
assert denied("answer_request", r1["id"], "accepted")
as_user(bob)
ok(call("vote_request", r1["id"], True))
bad(call("answer_request", r1["id"], "declined", "no"), "a no needs a reason")
bad(call("answer_request", r1["id"], "maybe"))
acc = ok(call("answer_request", r1["id"], "accepted", "Next sprint."))["request"]
assert acc["status"] == "accepted" and acc["card"]["status"] == "backlog" and acc["answered_by"] == "Bob Stone", acc
crd = M["Model"].card_by_key(team_row, acc["card"]["key"])
assert crd["source"].startswith("request:") and "request" in crd["labels"] and "Next sprint." in crd["body"]
ok(call("answer_request", r1["id"], "accepted"))
assert len([c for c in T.cards.search(team=team_row) if (c["source"] or "").startswith("request:")]) == 1, "no second card"
r2 = ok(call("submit_request", "Dark mode please", "", rkt))["request"]
T.requests.get_by_id(r2["id"])["created"] = now - dt.timedelta(days=20)
team_row["alerts_checked"] = None
deck = call("get_deck", rkt)
assert deck["requests"]["late"] == 1 and deck["requests"]["open"] == 1 and any(a["go"] == "requests" for a in deck["alerts"])
assert len(T.alerts.search(team=team_row, kind="request")) == 1
ok(call("update_crew", rkt, {"promise_days": 30}))
bad(call("update_crew", rkt, {"promise_days": 10}))
assert call("get_requests", rkt)["requests"][0]["overdue"] is False, "a longer promise moves the clock"
st = call("get_requests", rkt)["stats"]
assert st["answered"] == 1 and st["open"] == 1 and st["on_time"] == 100, st
assert denied("new_ask_code", rkt)
as_user(ana)
assert ok(call("new_ask_code", rkt))["code"] != code
bad(call("ask_page", code), "the old link stops working")
nr = call("get_requests", nova)
assert len(nr["requests"]) == 8 and nr["stats"]["shipped"] == 1 and nr["stats"]["overdue"] == 1, nr["stats"]
assert ok(call("ask_page", "NOVA4ASK"))["crew"]["id"] == nova
assert call("get_deck", nova)["requests"]["late"] == 1

# ---------------------------------------------------------------------------------- import + export
items = [{"title": "Login page", "type": "Story", "status": "done", "priority": 1, "points": 4, "labels": ["auth"],
          "assignee": "bob@example.com", "epic": "Accounts", "created": "2026-05-01T10:00:00Z", "started": "2026-05-02T10:00:00Z",
          "done_at": "2026-05-05", "source": "jira:OLD-1", "url": "https://acme.atlassian.net/browse/OLD-1",
          "comments": [{"who": "Zed", "text": "Ship it", "created": "2026-05-04"}]},
         {"title": "Crash on save", "type": "Bug", "status": "doing", "assignee": "Nobody Known", "source": "jira:OLD-2", "epic": "accounts"},
         {"title": "x"}, "junk",
         {"title": "Future thing", "status": "limbo", "created": "2999-01-01", "source": "jira:OLD-3", "points": 100}]
res = ok(call("import_cards", rkt, items, {"from": "Jira"}))
assert res["created"] == 3 and res["invalid"] == 2 and res["epics_created"] == 1 and res["unmatched"] == ["Nobody Known"] and res["comments"] == 1, res
again = ok(call("import_cards", rkt, items, {"from": "Jira"}))
assert again["created"] == 0 and again["duplicates"] == 3, "importing twice skips what is there"
login = [c for c in T.cards.search(team=team_row) if c["source"] == "jira:OLD-1"][0]
assert login["points"] == 3 and login["type"] == "story" and login["status"] == "done" and login["done_at"].date() == dt.date(2026, 5, 5)
assert login["assignee_user"] == bob and login["epic"]["title"] == "Accounts" and login["links"][0]["url"].endswith("OLD-1")
assert login["started"] is not None and 2.5 < M["Metrics"].cycle_days(login) < 2.7
crash = [c for c in T.cards.search(team=team_row) if c["source"] == "jira:OLD-2"][0]
assert crash["epic"] == login["epic"] and "Assignee in Jira: Nobody Known" in crash["body"] and crash["type"] == "bug"
fut = [c for c in T.cards.search(team=team_row) if c["source"] == "jira:OLD-3"][0]
assert fut["status"] == "backlog" and fut["created"] <= M["common"].now() and fut["points"] == 21
assert any(e["kind"] == "comment" and "Zed: Ship it" in e["text"] for e in T.events.search(card=login))
bad(call("import_cards", rkt, [], {}))
bad(call("import_cards", rkt, [{"title": "abc"}] * 251))
bad(call("import_cards", nova, items), "not into the shared demo")
as_user(admin)
assert denied("import_cards", rkt, items) and denied("export_crew", rkt)
as_user(ana)
ex = ok(call("export_crew", rkt))["export"]
assert ex["format"] == "autoagile-export" and ex["crew"]["key"] == "RKT" and len(ex["cards"]) == len(T.cards.search(team=team_row))
assert any(c["comments"] for c in ex["cards"]) and ex["requests"] and ex["crew"]["columns"]
nx = ok(call("export_crew", nova))["export"]
assert len(nx["cards"]) > 80 and any(c["column"] == "Test" for c in nx["cards"])
fresh = ok(call("create_crew", "Round Trip", "RTP"))["crew"]["id"]
keys = ("title", "body", "type", "status", "priority", "points", "gates", "acceptance", "labels", "epic", "created", "started",
        "review_at", "done_at")
rt = [dict({k: c[k] for k in keys}, source="autoagile:" + c["key"]) for c in nx["cards"]]
for i in range(0, len(rt), 250):
    ok(call("import_cards", fresh, rt[i:i + 250], {"from": "AutoAgile"}))
fresh_row = T.teams.get_by_id(fresh)
assert len(T.cards.search(team=fresh_row)) == len(nx["cards"]) and len(T.epics.search(team=fresh_row)) >= 3
done_n = len([c for c in nx["cards"] if c["status"] == "done"])
assert call("get_crew", fresh)["maturity"]["next"]["checks"][0]["value"] == done_n, "imported history counts for the level checks"
ok(call("delete_crew", fresh, "RTP"))

# ---------------------------------------------------------------------------------- reports
rp = call("get_reports", nova)
assert len(rp["cards"]) > 80 and rp["epics"] and rp["sprints"] and rp["velocity"] and rp["crew"]["key"] == "NOVA"
assert any(c["col"] == "Test" for c in rp["cards"]) and any(c["a"] for c in rp["cards"])
assert call("get_reports", rkt)["crew"]["key"] == "RKT"
as_user(admin)
assert denied("get_reports", rkt)
as_user(ana)

# ---------------------------------------------------------------------------------- members leaving, deleting
as_user(ana)
bad(call("remove_member", rkt, ana.get_id()))
ok(call("make_owner", rkt, bob.get_id()))
assert call("get_crew", rkt)["crew"]["role"] == "member"
ok(call("leave_crew", rkt))
assert denied("get_board", rkt)
as_user(bob)
bad(call("delete_crew", rkt, "NOPE"))
ok(call("delete_card", c1))
ok(call("delete_crew", rkt, "rkt"))
assert C_row(T.teams, rkt) is None

# ---------------------------------------------------------------------------------- admin + demo removal
as_user(admin)
ov = call("admin_overview")
assert ov["crews"] == 0 and ov["cards"] > 100 and ov["agents"] == 4
cr = call("admin_crews")["crews"]
assert len(cr) == 2 and all(c["demo"] for c in cr)
bad(call("admin_delete_crew", cr[0]["id"]))
as_user(ana)
assert denied("admin_crews")
x = ok(call("create_crew", "Scratch", "SCR"))["crew"]
ok(call("quick_add", nova, "A real card in a demo crew"))
as_user(admin)
ok(call("admin_delete_crew", x["id"]))
ok(call("demo_remove"))
assert M["DemoData"].state() == "removed" and not T.teams.search() and not T.cards.search() and not T.events.search()
assert not T.users.search(is_demo=True)
as_user(ana)
assert call("my_crews")["crews"] == [], "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert len(T.teams.search()) == 2, "reloading replaces the demo instead of doubling it"

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "legal_state", "legal_accept"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
