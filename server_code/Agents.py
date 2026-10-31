"""AI developers as crew members.

An agent belongs to one crew, has a kind (Claude Code, Codex, a custom bot...), a WIP limit of its own and
an API token (shown once; only its SHA-256 is stored). It works through the HTTP API at <app>/_/api/agent/<op>
with `Authorization: Bearer <token>`:

  GET  whoami   the agent, its crew, house rules and Definition of Done
  GET  next     the best card for it now (Ready, unblocked, gated as agent-fit), with the markdown brief
  GET  cards    cards by ?status=ready|doing|review|backlog|done
  GET  card     ?key=NOVA-12 -> the card and its brief
  POST claim    {key}            assign to itself and move to Doing (respects its WIP and the column's)
  POST log      {key, text}      a progress note on the card's timeline
  POST check    {key, index, done}  tick an acceptance criterion
  POST submit   {key, summary, links}  hand in: moves to Review; only a human moves it to Done
  POST release  {key, reason}    give the card back (to Ready)
  POST propose  {title, body, type}  suggest a new card (lands in the Backlog, labelled agent-proposed)
  GET  manifest (no token)       this list as JSON

agent_console() runs the same operations from the Agents page, so people can try it without a token.
"""
import hashlib
import json
import secrets

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Gates
from . import Cards
from . import Alerts

KINDS = ["Claude Code", "Codex", "Cursor agent", "Copilot agent", "Devin", "Custom agent"]
OPS = {"whoami": "GET", "next": "GET", "cards": "GET", "card": "GET", "claim": "POST", "log": "POST", "check": "POST",
       "submit": "POST", "release": "POST", "propose": "POST"}
DOCS = {
    "whoami": "Who you are, your crew, its house rules and Definition of Done.",
    "next": "The best card for you right now, with its markdown brief. Claim it to start.",
    "cards": "Cards in a column: ?status=ready (default), doing, review, backlog or done.",
    "card": "One card and its brief: ?key=NOVA-12.",
    "claim": "Take a Ready card: {\"key\": \"NOVA-12\"}. Moves it to Doing.",
    "log": "Add a progress note: {\"key\", \"text\"}.",
    "check": "Tick an acceptance criterion: {\"key\", \"index\": 0, \"done\": true}.",
    "submit": "Hand in for human review: {\"key\", \"summary\", \"links\": [{\"label\", \"url\"}]}. Moves it to Review.",
    "release": "Give a card back to Ready: {\"key\", \"reason\"}.",
    "propose": "Suggest a new card: {\"title\", \"body\", \"type\": \"story|bug|task|spike|chore\"}. Lands in the Backlog.",
}


def _hash(tok):
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()


def _new_token():
    return "aa_" + secrets.token_urlsafe(24)


def _agent(agent_id):
    a = C.row_by_id(app_tables.agents, agent_id)
    if a is None:
        raise anvil.server.PermissionDenied("That agent doesn't exist any more.")
    t, me, role = M.access(a["team"].get_id())
    return a, t, me


# ------------------------------------------------------------------------------------------- managing agents
@anvil.server.callable(require_user=True)
def create_agent(team_id, name, kind="Claude Code", max_wip=1):
    t, me, role = M.access(team_id)
    name = C.text(name, 30)
    if len(name) < 2:
        return C.fail("Give the agent a name (2 characters or more).")
    if kind not in KINDS:
        kind = "Custom agent"
    try:
        max_wip = max(1, min(5, int(max_wip)))
    except (TypeError, ValueError):
        max_wip = 1
    if len(app_tables.agents.search(team=t)) >= 12:
        return C.fail("A crew can have up to 12 agents.")
    if app_tables.agents.get(team=t, name=name):
        return C.fail("This crew already has an agent called %s." % name)
    tok = _new_token()
    n = len(app_tables.agents.search(team=t))
    a = app_tables.agents.add_row(team=t, name=name, kind=kind, color=M.COLORS[(n + 2) % len(M.COLORS)], max_wip=max_wip,
                                  token_hash=_hash(tok), token_hint=tok[-4:], active=True, created=C.now(), created_by=me,
                                  last_seen=None, is_demo=False)
    M.log(t, "agent", "%s added the agent %s (%s)." % (C.name_of(me), name, kind), user=me)
    return C.ok(agent=M.agent_dict(a), token=tok)


@anvil.server.callable(require_user=True)
def update_agent(agent_id, fields):
    a, t, me = _agent(agent_id)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    upd = {}
    if "name" in fields:
        name = C.text(fields["name"], 30)
        if len(name) < 2:
            return C.fail("Agent names need 2 characters or more.")
        other = app_tables.agents.get(team=t, name=name)
        if other is not None and other != a:
            return C.fail("This crew already has an agent called %s." % name)
        upd["name"] = name
    if "kind" in fields and fields["kind"] in KINDS:
        upd["kind"] = fields["kind"]
    if "max_wip" in fields:
        try:
            upd["max_wip"] = max(1, min(5, int(fields["max_wip"])))
        except (TypeError, ValueError):
            return C.fail("WIP is a number from 1 to 5.")
    if "active" in fields:
        upd["active"] = bool(fields["active"])
        M.log(t, "agent", "%s %s %s." % (C.name_of(me), "resumed" if fields["active"] else "paused", a["name"]), user=me)
    if "color" in fields and fields["color"] in M.COLORS:
        upd["color"] = fields["color"]
    if upd:
        a.update(**upd)
    return C.ok(agent=M.agent_dict(a))


@anvil.server.callable(require_user=True)
def rotate_token(agent_id):
    a, t, me = _agent(agent_id)
    tok = _new_token()
    a.update(token_hash=_hash(tok), token_hint=tok[-4:])
    M.log(t, "agent", "%s issued a new token for %s (the old one stopped working)." % (C.name_of(me), a["name"]), user=me)
    return C.ok(token=tok, agent=M.agent_dict(a))


@anvil.server.callable(require_user=True)
def delete_agent(agent_id):
    a, t, me = _agent(agent_id)
    name = a["name"]
    for c in app_tables.cards.search(assignee_agent=a):
        c["assignee_agent"] = None
        if c["status"] == "doing":
            Cards.apply_move(c, "ready", user=me)
    for e in app_tables.events.search(actor_agent=a):
        e.update(actor_agent=None, text="[%s] %s" % (name, e["text"] or ""))
    a.delete()
    M.log(t, "agent", "%s removed the agent %s." % (C.name_of(me), name), user=me)
    return C.ok()


@anvil.server.callable(require_user=True)
def get_agents(team_id):
    t, me, role = M.access(team_id)
    agents = sorted([M.agent_dict(a) for a in app_tables.agents.search(team=t)], key=lambda a: a["name"].lower())
    feed = [e for e in app_tables.events.search(team=t) if e["actor_agent"] is not None]
    feed.sort(key=lambda e: e["created"], reverse=True)
    review = [c for c in app_tables.cards.search(team=t, status="review") if c["assignee_agent"] is not None]
    review.sort(key=lambda c: c["review_at"] or C.now())
    ready = [c for c in app_tables.cards.search(team=t, status="ready") if Gates.readiness(M.card_dict(c, full=True))["ready"]]
    return {"crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "demo": bool(t["is_demo"])},
            "agents": agents, "kinds": KINDS, "feed": [M.event_dict(e) for e in feed[:40]],
            "review": [M.card_dict(c) for c in review], "agent_ready": len(ready), "rules": t["agent_rules"] or "",
            "ops": [{"op": k, "method": v, "doc": DOCS[k]} for k, v in OPS.items()]}


# ------------------------------------------------------------------------------------------- the operations
def _err(msg, status=400):
    return {"ok": False, "error": msg, "status": status}


def _card(a, data):
    c = M.card_by_key(a["team"], (data or {}).get("key"))
    return c


def _brief_card(c, base):
    d = M.card_dict(c)
    return dict(d, brief=Cards.brief(c, base))


def _next(a):
    t = a["team"]
    sprint = Cards.active_sprint(t) if (t["level"] or 1) >= 2 else None
    cands = []
    for c in app_tables.cards.search(team=t, status="ready"):
        if c["blocked"] or (c["assignee_user"] is not None) or (c["assignee_agent"] is not None and c["assignee_agent"] != a):
            continue
        if sprint is not None and c["sprint"] != sprint:
            continue
        g = Gates.score(c["gates"] or {})
        if not g.get("complete") or g["fit"] not in ("solo", "pair"):
            continue
        cands.append((c["assignee_agent"] != a, g["fit"] != "solo", c["priority"] if c["priority"] is not None else 2, c["rank"] or 0, c))
    cands.sort(key=lambda x: x[:4])
    return cands[0][4] if cands else None


def agent_op(a, op, data=None, base=None):
    """Run one API operation as agent a. Returns a JSON-able dict (ok, ..., and status on errors)."""
    data = data if isinstance(data, dict) else {}
    t = a["team"]
    a["last_seen"] = C.now()
    if op not in OPS:
        return _err("Unknown operation %s. Try: %s." % (op, ", ".join(OPS)), 404)
    if op == "whoami":
        return {"ok": True, "agent": {"name": a["name"], "kind": a["kind"], "max_wip": a["max_wip"] or 1, "active": bool(a["active"])},
                "crew": {"name": t["name"], "key": t["key"], "level": t["level"] or 1, "mission": t["mission"] or ""},
                "house_rules": t["agent_rules"] or "", "definition_of_done": t["dod"] or [],
                "ops": {k: DOCS[k] for k in OPS}}
    if not a["active"]:
        return _err("%s is paused by the crew. Ask a human to resume it." % a["name"], 423)
    Alerts.sweep(t)
    if op == "next":
        c = _next(a)
        if c is None:
            return {"ok": True, "card": None, "message": "Nothing is ready for agents right now. Ready cards need gates that say AGENT SOLO or AGENT + HUMAN."}
        return {"ok": True, "card": _brief_card(c, base), "hint": "POST claim with {\"key\": \"%s\"} to start." % M.card_key(c)}
    if op == "cards":
        st = data.get("status") or "ready"
        if st not in M.STATUSES:
            return _err("status is one of %s." % ", ".join(M.STATUSES))
        rows = sorted(app_tables.cards.search(team=t, status=st), key=lambda c: c["rank"] or 0)[:50]
        return {"ok": True, "cards": [{k: d[k] for k in ("key", "title", "type", "priority", "points", "fit", "agent_ready", "assignee", "blocked")}
                                      for d in [M.card_dict(c) for c in rows]]}
    if op == "propose":
        title = C.text(data.get("title"), 200)
        if len(title) < 3:
            return _err("A proposal needs a title of 3 characters or more.")
        recent = [e for e in app_tables.events.search(actor_agent=a, kind="create") if (C.now() - e["created"]).total_seconds() < 3600]
        if len(recent) >= 20:
            return _err("That's 20 proposals this hour. Let the humans catch up.", 429)
        typ = data.get("type") if data.get("type") in M.TYPES else "task"
        c = Cards.new_card(t, title, agent=a, body=C.text(data.get("body"), 8000, multiline=True), type=typ,
                           labels=["agent-proposed"], acceptance=Cards.clean_acceptance(data.get("acceptance")))
        return {"ok": True, "card": M.card_dict(c), "message": "Proposed %s. A human will groom it." % M.card_key(c), "status": 201}
    c = _card(a, data)
    if c is None:
        return _err("No card %s in %s." % (C.text(data.get("key"), 20) or "(no key)", t["key"]), 404)
    key = M.card_key(c)
    if op == "card":
        return {"ok": True, "card": _brief_card(c, base)}
    if op == "claim":
        if c["status"] not in ("ready",):
            return _err("%s is in %s. Agents claim cards from Ready." % (key, M.STATUS_LABEL[c["status"]]), 409)
        if c["blocked"]:
            return _err("%s is blocked: %s" % (key, c["blocked_reason"] or "ask a human."), 409)
        if c["assignee_user"] is not None or (c["assignee_agent"] is not None and c["assignee_agent"] != a):
            return _err("%s belongs to someone else." % key, 409)
        mine = len(app_tables.cards.search(assignee_agent=a, status="doing"))
        if mine >= (a["max_wip"] or 1):
            return _err("You already have %d card%s in Doing (your limit). Submit or release one first." % (mine, "" if mine == 1 else "s"), 409)
        wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
        if len(app_tables.cards.search(team=t, status="doing")) >= wip["doing"]:
            return _err("Doing is at the crew's WIP limit (%d). Help finish something instead." % wip["doing"], 409)
        c.update(assignee_agent=a, assignee_user=None)
        Cards.apply_move(c, "doing", agent=a)
        return {"ok": True, "card": _brief_card(c, base), "message": "%s is yours. Go." % key}
    mine = c["assignee_agent"] == a
    if op == "log":
        text = C.text(data.get("text"), 2000, multiline=True)
        if not text:
            return _err("Send some text to log.")
        M.log(t, "agent_log", text, card=c, agent=a)
        return {"ok": True, "message": "Logged on %s." % key}
    if not mine:
        return _err("%s isn't assigned to you. Claim it first." % key, 403)
    if op == "check":
        acc = list(c["acceptance"] or [])
        try:
            i = int(data.get("index"))
        except (TypeError, ValueError):
            return _err("index is the criterion's number, starting at 0.")
        if not 0 <= i < len(acc):
            return _err("%s has %d criteria (index 0 to %d)." % (key, len(acc), len(acc) - 1))
        acc[i] = dict(acc[i], done=data.get("done", True) is not False)
        c.update(acceptance=acc, updated=C.now())
        M.log(t, "agent_log", "%s criterion %d: %s" % ("Ticked" if acc[i]["done"] else "Unticked", i + 1, acc[i]["text"]), card=c, agent=a)
        return {"ok": True, "acceptance": acc}
    if op == "submit":
        if c["status"] != "doing":
            return _err("%s is in %s; submit from Doing." % (key, M.STATUS_LABEL[c["status"]]), 409)
        summary = C.text(data.get("summary"), 3000, multiline=True)
        if len(summary) < 10:
            return _err("Write a summary (10 characters or more): what changed and how you tested it.")
        links = Cards.clean_links(list(c["links"] or []) + list(data.get("links") or []))
        c.update(links=links, updated=C.now())
        Cards.apply_move(c, "review", agent=a)
        M.log(t, "submit", summary, card=c, agent=a)
        Alerts.fire(t, "submitted", "submitted:%s:%s" % (c.get_id(), C.iso(c["review_at"])),
                    "%s handed in %s for review: %s" % (a["name"], key, c["title"]), card=c)
        open_acc = len([x for x in (c["acceptance"] or []) if not x.get("done")])
        return {"ok": True, "message": "%s is in Review. A human approves it." % key,
                "warning": ("%d acceptance criteria are still unticked." % open_acc) if open_acc else None}
    if op == "release":
        reason = C.text(data.get("reason"), 500) or "no reason given"
        c["assignee_agent"] = None
        Cards.apply_move(c, "ready", agent=a)
        M.log(t, "agent_log", "Released the card: %s" % reason, card=c, agent=a)
        return {"ok": True, "message": "%s is back in Ready." % key}
    return _err("Unknown operation.", 404)


# ------------------------------------------------------------------------------------------- HTTP API
def _api_base():
    try:
        return anvil.server.get_api_origin()
    except Exception:
        return None


def _body():
    req = anvil.server.request
    b = getattr(req, "body", None)
    if b is None:
        return {}
    if hasattr(b, "get_bytes"):
        b = b.get_bytes()
    if isinstance(b, bytes):
        b = b.decode("utf-8", "replace")
    try:
        v = json.loads(b or "{}")
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _reply(status, data):
    return anvil.server.HttpResponse(status, json.dumps(data, indent=1), headers={"Content-Type": "application/json"})


def agent_for_token(tok):
    if not tok or not isinstance(tok, str) or not tok.startswith("aa_"):
        return None
    return app_tables.agents.get(token_hash=_hash(tok.strip()))


def handle_http(op, query):
    req = anvil.server.request
    headers = {str(k).lower(): v for k, v in (getattr(req, "headers", None) or {}).items()}
    auth = headers.get("authorization") or ""
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else (query or {}).get("token")
    data = {k: v for k, v in (query or {}).items() if k != "token"}
    data.update(_body())
    a = agent_for_token(tok)
    if a is None:
        return _reply(401, {"ok": False, "error": "Send your agent token: Authorization: Bearer aa_..."})
    r = agent_op(a, op, data, base=_api_base())
    status = r.pop("status", 200 if r.get("ok") else 400)
    return _reply(status, r)


def _register(op):
    def endpoint(**query):
        return handle_http(op, query)
    endpoint.__name__ = "agent_http_" + op
    anvil.server.http_endpoint("/agent/" + op, methods=["GET", "POST"])(endpoint)


for _op in OPS:
    _register(_op)


@anvil.server.http_endpoint("/agent/manifest", methods=["GET"])
def agent_manifest(**query):
    base = _api_base() or "<app>/_/api"
    return _reply(200, {"name": "AutoAgile agent API", "version": 1, "auth": "Authorization: Bearer <agent token>",
                        "base": base + "/agent",
                        "ops": [{"op": k, "method": v, "url": "%s/agent/%s" % (base, k), "doc": DOCS[k]} for k, v in OPS.items()],
                        "rules": "Agents never move cards to Done: a human approves in Review."})


# ------------------------------------------------------------------------------------------- console (in the app)
@anvil.server.callable(require_user=True)
def agent_console(agent_id, command, api_base=None):
    """Run an API operation as this agent from the Agents page: 'next', 'claim NOVA-12', 'log NOVA-12 text',
    'check NOVA-12 0', 'submit NOVA-12 summary', 'release NOVA-12 reason', 'propose Title', 'cards review', 'card NOVA-12'."""
    a, t, me = _agent(agent_id)
    parts = C.text(command, 2000).split(" ")
    op = (parts[0] or "").lower()
    rest = parts[1:]
    if op in ("", "help"):
        return {"ok": True, "lines": ["%-8s %s" % (k, DOCS[k]) for k in OPS]}
    data = {}
    if op in ("card", "claim", "log", "check", "submit", "release") and rest:
        data["key"] = rest[0]
        tail = " ".join(rest[1:])
        if op == "log":
            data["text"] = tail
        elif op == "check":
            data["index"] = rest[1] if len(rest) > 1 else None
            data["done"] = not (len(rest) > 2 and rest[2].lower() in ("off", "false", "no", "0"))
        elif op == "submit":
            data["summary"] = tail
        elif op == "release":
            data["reason"] = tail
    elif op == "cards" and rest:
        data["status"] = rest[0].lower()
    elif op == "propose":
        data["title"] = " ".join(rest)
    base = C.text(api_base, 200) if api_base and str(api_base).startswith("http") else None
    r = agent_op(a, op, data, base=base)
    r.pop("status", None)
    return {"ok": True, "result": r}
