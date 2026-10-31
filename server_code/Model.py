"""Shared building blocks for AutoAgile's server modules (no callables here).

- access(team_id): who may touch a crew. Members of a crew may do everything with its cards, sprints,
  epics and agents; only the owner renames it, removes people or deletes it. Demo crews (is_demo) are an
  open sandbox: every signed-in person can use them, nobody but an admin can rename or delete them.
- card_dict / agent_dict / event_dict: rows -> plain dicts for the browser and the agent API.
- log(): the activity timeline (moves, comments, agent run logs).
- columns_of(team): the crew's board columns. Every column belongs to one of the four stages (ready, doing,
  review, done) that the metrics, levels and agent API understand; a crew can split a stage into several
  columns (Doing -> Build + Test) with their own WIP limits. card["column"] is a column id or None (= the
  first column of the card's stage).
"""
import re

import datetime as dt

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Gates

STATUSES = ["backlog", "ready", "doing", "review", "done"]
STATUS_LABEL = {"backlog": "Backlog", "ready": "Ready", "doing": "Doing", "review": "Review", "done": "Done"}
BOARD = ["ready", "doing", "review", "done"]
TYPES = ["story", "bug", "task", "spike", "chore"]
PRIORITIES = [0, 1, 2, 3]
DEFAULT_WIP = {"ready": 8, "doing": 4, "review": 3}
DEFAULT_DOD = ["Acceptance criteria all ticked", "Tests written and passing", "Reviewed by a human",
               "Deployed or merged to main"]
DEFAULT_AGENT_RULES = ("Work on one card at a time. Keep changes small and on topic. Run the tests before you submit. "
                       "Never change secrets, payments or database migrations without a human. "
                       "Log what you did and what you were unsure about.")
EPIC_SIZES = {"S": 8, "M": 21, "L": 55, "XL": 120}
COLORS = ["#b4ff1f", "#ff2bd6", "#00e5ff", "#ffd60a", "#ff7a1a", "#8a5cff", "#39ff88", "#ff3b5c"]

LEVELS = [
    {"n": 1, "key": "kanban", "name": "KANBAN", "title": "Flow",
     "blurb": "Pull work from a ranked backlog, keep WIP limits, and learn your crew's rhythm."},
    {"n": 2, "key": "scrum", "name": "SCRUM", "title": "Sprints",
     "blurb": "Commit to sprints with a goal, plan to your real velocity, run retros."},
    {"n": 3, "key": "quarter", "name": "QUARTER", "title": "3-month plan",
     "blurb": "Forecast epics across the next six sprints with a confidence range."},
    {"n": 4, "key": "year", "name": "YEAR", "title": "Roadmap",
     "blurb": "Plan a year in quarters and estimate it from your measured capacity."},
]


MAX_COLUMNS = 12


def default_columns():
    return [{"id": s, "name": STATUS_LABEL[s], "stage": s, "wip": None} for s in BOARD]


def clean_columns(cols):
    """A safe list of columns: known stages, in stage order, each stage at least once, unique ids."""
    out, seen = [], set()
    for c in (cols or [])[:MAX_COLUMNS]:
        if not isinstance(c, dict) or c.get("stage") not in BOARD:
            continue
        cid = str(c.get("id") or "")
        if not re.match(r"^[a-z0-9_]{1,24}$", cid) or cid in seen:
            continue
        name = C.text(c.get("name"), 20) or STATUS_LABEL[c["stage"]]
        try:
            wip = int(c.get("wip")) if c.get("wip") not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            wip = None
        if wip is not None and not 1 <= wip <= 50:
            wip = None
        seen.add(cid)
        out.append({"id": cid, "name": name, "stage": c["stage"], "wip": wip})
    for d in default_columns():
        if not any(c["stage"] == d["stage"] for c in out):
            if d["id"] in seen:
                d["id"] = d["id"] + "_1"
            out.append(d)
    out.sort(key=lambda c: BOARD.index(c["stage"]))  # stable: keeps the crew's order inside a stage
    return out


def columns_of(t):
    return clean_columns(t["columns"]) if t["columns"] else default_columns()


def column_of(c, cols):
    """The column id a card sits in."""
    stage = "ready" if c["status"] == "backlog" else c["status"]
    ids = [x["id"] for x in cols if x["stage"] == stage]
    return c["column"] if c["column"] in ids else (ids[0] if ids else stage)


def column_name(cols, cid):
    for x in cols:
        if x["id"] == cid:
            return x["name"]
    return cid


def level_info(n):
    n = max(1, min(4, int(n or 1)))
    return dict(LEVELS[n - 1])


# ------------------------------------------------------------------------------------------- access
def access(team_id, owner=False):
    """(team row, me, role). role: owner | member | sandbox. Raises PermissionDenied otherwise."""
    me = C.require_user()
    t = C.row_by_id(app_tables.teams, team_id)
    if t is None:
        raise anvil.server.PermissionDenied("That crew doesn't exist any more.")
    m = app_tables.members.get(team=t, user=me)
    if m is not None:
        role = m["role"] or "member"
    elif t["is_demo"]:
        role = "sandbox"
    else:
        raise anvil.server.PermissionDenied("You're not in that crew.")
    if owner and role != "owner" and not (t["is_demo"] and C.is_admin(me)):
        raise anvil.server.PermissionDenied("Only the crew's owner can do that." if not t["is_demo"]
                                            else "Demo crews can't be changed like that. Start your own crew.")
    return t, me, role


def card_access(card_id):
    c = C.row_by_id(app_tables.cards, card_id)
    if c is None:
        raise anvil.server.PermissionDenied("That card doesn't exist any more.")
    t, me, role = access(c["team"].get_id())
    return c, t, me, role


def card_by_key(team, key):
    """'NOVA-12' or '12' -> the card row in this team, or None."""
    s = str(key or "").strip().upper()
    if "-" in s:
        prefix, _, num = s.rpartition("-")
        if prefix != (team["key"] or "").upper():
            return None
        s = num
    try:
        n = int(s)
    except ValueError:
        return None
    return app_tables.cards.get(team=team, number=n)


# ------------------------------------------------------------------------------------------- dicts
def person(user=None, agent=None):
    if agent is not None:
        return {"kind": "agent", "id": agent.get_id(), "name": agent["name"], "color": agent["color"] or COLORS[2],
                "agent_kind": agent["kind"] or "Agent"}
    if user is not None:
        return {"kind": "user", "id": user.get_id(), "name": C.name_of(user)}
    return None


def days_since(when):
    if when is None:
        return None
    return round((C.now() - when).total_seconds() / 86400.0, 1)


def card_key(c):
    return "%s-%d" % (c["team"]["key"], c["number"])


def card_dict(c, full=False):
    acc = c["acceptance"] or []
    a = Gates.clean(c["gates"] or {})
    gate = Gates.score(a) if a else {"complete": False, "answered": 0, "points": None}
    base = {"body": c["body"] or "", "acceptance": acc, "gates": a, "points": c["points"], "blocked": bool(c["blocked"])}
    ready = Gates.readiness(base)
    d = {"id": c.get_id(), "key": card_key(c), "number": c["number"], "title": c["title"], "type": c["type"] or "story",
         "status": c["status"], "priority": c["priority"] if c["priority"] is not None else 2, "points": c["points"],
         "points_src": c["points_src"] or ("gates" if gate.get("complete") else None), "rank": c["rank"] or 0,
         "assignee": person(c["assignee_user"], c["assignee_agent"]),
         "epic": {"id": c["epic"].get_id(), "title": c["epic"]["title"], "color": c["epic"]["color"]} if c["epic"] else None,
         "sprint": {"id": c["sprint"].get_id(), "name": c["sprint"]["name"], "state": c["sprint"]["state"]} if c["sprint"] else None,
         "labels": c["labels"] or [], "blocked": bool(c["blocked"]), "blocked_reason": c["blocked_reason"] or "",
         "fit": gate.get("fit"), "verdict": gate.get("verdict"), "ready": ready["passed"], "ready_total": ready["total"],
         "agent_ready": ready["ready"], "acc_done": sum(1 for x in acc if x.get("done")), "acc_total": len(acc),
         "age": days_since(c["moved_at"]), "created": C.iso(c["created"]), "started": C.iso(c["started"]),
         "done_at": C.iso(c["done_at"]), "review_at": C.iso(c["review_at"]), "column": c["column"], "source": c["source"] or "",
         "demo": bool(c["is_demo"])}
    if full:
        d.update(body=c["body"] or "", acceptance=acc, gates=a, gate=gate, readiness=ready, links=c["links"] or [],
                 updated=C.iso(c["updated"]), created_by=C.name_of(c["created_by"]) if c["created_by"] else "An agent")
    return d


def agent_dict(a):
    doing = [c for c in app_tables.cards.search(assignee_agent=a) if c["status"] in ("doing", "review")]
    done = len(app_tables.cards.search(assignee_agent=a, status="done"))
    working = [c for c in doing if c["status"] == "doing"]
    if not a["active"]:
        state = "paused"
    elif working:
        state = "working"
    elif any(c["status"] == "review" for c in doing):
        state = "waiting"
    else:
        state = "idle"
    return {"id": a.get_id(), "name": a["name"], "kind": a["kind"] or "Agent", "color": a["color"] or COLORS[2],
            "max_wip": a["max_wip"] or 1, "active": bool(a["active"]), "state": state, "token_hint": a["token_hint"] or "",
            "has_token": bool(a["token_hash"]), "last_seen": C.iso(a["last_seen"]), "created": C.iso(a["created"]),
            "wip": len(working), "in_review": len(doing) - len(working), "done": done,
            "current": [{"id": c.get_id(), "key": card_key(c), "title": c["title"], "status": c["status"]} for c in doing][:4],
            "demo": bool(a["is_demo"])}


def event_dict(e):
    who = person(e["actor_user"], e["actor_agent"]) or {"kind": "system", "name": "AutoAgile"}
    out = {"id": e.get_id(), "kind": e["kind"], "text": e["text"] or "", "created": C.iso(e["created"]), "who": who}
    if e["card"] is not None:
        out["card"] = {"id": e["card"].get_id(), "key": card_key(e["card"]), "title": e["card"]["title"]}
    return out


def log(team, kind, text, card=None, user=None, agent=None, when=None, demo=False):
    return app_tables.events.add_row(team=team, card=card, actor_user=user, actor_agent=agent, kind=kind,
                                     text=C.text(text, 2000, multiline=True), created=when or C.now(), is_demo=demo)


def delete_team_rows(t):
    """Delete a crew and everything in it (children first)."""
    for table in ("alerts", "requests", "events", "cards", "sprints", "epics", "agents", "members"):
        for r in getattr(app_tables, table).search(team=t):
            r.delete()
    t.delete()


def members_of(t):
    return [m for m in app_tables.members.search(team=t)]


def next_rank(team, status=None):
    rows = app_tables.cards.search(team=team)
    ranks = [r["rank"] or 0 for r in rows]
    return (max(ranks) if ranks else 0) + 1000


def team_today():
    return C.now().date()


def quarter_of(d):
    return "%d-Q%d" % (d.year, (d.month - 1) // 3 + 1)


def quarters_from(d, n=4):
    y, q = d.year, (d.month - 1) // 3 + 1
    out = []
    for _ in range(n):
        out.append("%d-Q%d" % (y, q))
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return out


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    return v
