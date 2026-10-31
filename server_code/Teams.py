"""Crews (teams): create, join with a code, settings (WIP limits, sprint length, Definition of Done,
agent house rules), members, and the maturity level (Kanban -> Scrum -> Quarter -> Year)."""
import random
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Metrics
from . import DemoData

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _code():
    return "".join(random.choice(CODE_CHARS) for _ in range(6))


def crew_summary(t, role):
    cards = app_tables.cards.search(team=t)
    return {"id": t.get_id(), "name": t["name"], "key": t["key"], "level": t["level"] or 1,
            "level_name": M.level_info(t["level"])["name"], "role": role, "demo": bool(t["is_demo"]),
            "mission": t["mission"] or "", "members": len(app_tables.members.search(team=t)),
            "cards": len(cards), "open": len([c for c in cards if c["status"] != "done"])}


@anvil.server.callable(require_user=True)
def my_crews():
    """The crews this person can open: their own, then the demo sandbox crews."""
    DemoData.ensure_loaded()
    me = C.require_user()
    out = []
    seen = set()
    for m in app_tables.members.search(user=me):
        t = m["team"]
        if t is None:
            continue
        seen.add(t.get_id())
        out.append(crew_summary(t, m["role"] or "member"))
    for t in app_tables.teams.search(is_demo=True):
        if t.get_id() not in seen:
            out.append(crew_summary(t, "sandbox"))
    out.sort(key=lambda c: (c["demo"], c["name"].lower()))
    return {"crews": out}


def _clean_key(key, name):
    k = re.sub(r"[^A-Z0-9]", "", C.text(key, 10).upper())
    if not k:
        k = re.sub(r"[^A-Z]", "", (name or "").upper())[:4]
    return k[:5]


@anvil.server.callable(require_user=True)
def create_crew(name, key=None, mission="", level=1):
    me = C.require_user()
    name = C.text(name, 60)
    if len(name) < 2:
        return C.fail("Give your crew a name (2 characters or more).")
    key = _clean_key(key, name)
    if len(key) < 2 or not key[0].isalpha():
        return C.fail("The card prefix needs 2 to 5 letters or digits, starting with a letter (like NOVA).")
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 1
    level = 2 if level == 2 else 1
    if C.rate_limited("create_crew", 10, 3600):
        return C.fail("That's a lot of new crews in one hour. Try again later.")
    t = app_tables.teams.add_row(name=name, key=key, mission=C.text(mission, 300), level=level, join_code=_code(), owner=me,
                                 created=C.now(), next_number=1, sprint_days=14, wip=dict(M.DEFAULT_WIP),
                                 dod=list(M.DEFAULT_DOD), agent_rules=M.DEFAULT_AGENT_RULES,
                                 level_log=[{"level": level, "at": C.iso(C.now()), "by": C.name_of(me), "forced": False}],
                                 is_demo=False)
    app_tables.members.add_row(team=t, user=me, role="owner", joined=C.now(), is_demo=False)
    M.log(t, "crew", "%s started the crew at level %d (%s)." % (C.name_of(me), level, M.level_info(level)["name"]), user=me)
    return C.ok(crew=crew_summary(t, "owner"))


@anvil.server.callable(require_user=True)
def join_crew(code):
    me = C.require_user()
    code = re.sub(r"[^A-Z0-9]", "", C.text(code, 20).upper())
    if C.rate_limited("join_crew", 12, 3600):
        return C.fail("Too many tries. Wait a while and try again.")
    t = app_tables.teams.get(join_code=code) if len(code) == 6 else None
    if t is None or t["is_demo"]:
        return C.fail("No crew has that code. Check it with whoever sent it.")
    m = app_tables.members.get(team=t, user=me)
    if m is None:
        app_tables.members.add_row(team=t, user=me, role="member", joined=C.now(), is_demo=False)
        M.log(t, "crew", "%s joined the crew." % C.name_of(me), user=me)
    return C.ok(crew=crew_summary(t, m["role"] if m else "member"))


def crew_dict(t, me, role):
    members = []
    for m in M.members_of(t):
        u = m["user"]
        if u is None:
            continue
        members.append({"id": u.get_id(), "name": C.name_of(u), "role": m["role"] or "member", "me": u == me,
                        "joined": C.iso(m["joined"])})
    members.sort(key=lambda x: (x["role"] != "owner", x["name"].lower()))
    agents = [M.agent_dict(a) for a in app_tables.agents.search(team=t)]
    agents.sort(key=lambda a: a["name"].lower())
    lvl = M.level_info(t["level"])
    return {"id": t.get_id(), "name": t["name"], "key": t["key"], "mission": t["mission"] or "", "level": lvl["n"],
            "level_info": lvl, "levels": M.LEVELS, "role": role, "demo": bool(t["is_demo"]),
            "can_admin": role == "owner" or (t["is_demo"] and C.is_admin(me)),
            "join_code": t["join_code"] if role in ("owner", "member") else None,
            "sprint_days": t["sprint_days"] or 14, "wip": dict(M.DEFAULT_WIP, **(t["wip"] or {})), "dod": t["dod"] or [],
            "agent_rules": t["agent_rules"] or "", "members": members, "agents": agents,
            "level_log": t["level_log"] or [], "created": C.iso(t["created"]), "columns": M.columns_of(t),
            "promise_days": t["promise_days"] or 14}


@anvil.server.callable(require_user=True)
def get_crew(team_id):
    t, me, role = M.access(team_id)
    return {"crew": crew_dict(t, me, role), "maturity": Metrics.maturity(t)}


@anvil.server.callable(require_user=True)
def update_crew(team_id, fields):
    """Settings. Name and mission: owner only. WIP, sprint length, DoD, agent rules: any member."""
    t, me, role = M.access(team_id)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    changes = {}
    if "name" in fields or "mission" in fields:
        M.access(team_id, owner=True)
        if "name" in fields:
            name = C.text(fields["name"], 60)
            if len(name) < 2:
                return C.fail("The crew's name needs 2 characters or more.")
            changes["name"] = name
        if "mission" in fields:
            changes["mission"] = C.text(fields["mission"], 300)
    if "wip" in fields:
        wip = {}
        for col in ("ready", "doing", "review"):
            try:
                v = int((fields["wip"] or {}).get(col))
            except (TypeError, ValueError, AttributeError):
                continue
            if 1 <= v <= 50:
                wip[col] = v
        changes["wip"] = dict(M.DEFAULT_WIP, **wip)
    if "sprint_days" in fields:
        try:
            d = int(fields["sprint_days"])
        except (TypeError, ValueError):
            return C.fail("Sprint length is a number of days.")
        if d not in (7, 14, 21, 28):
            return C.fail("Sprints can be 1, 2, 3 or 4 weeks long.")
        changes["sprint_days"] = d
    if "dod" in fields:
        items = [C.text(x, 140) for x in (fields["dod"] or []) if C.text(x, 140)]
        changes["dod"] = items[:12]
    if "agent_rules" in fields:
        changes["agent_rules"] = C.text(fields["agent_rules"], 3000, multiline=True)
    if "promise_days" in fields:
        try:
            pd = int(fields["promise_days"])
        except (TypeError, ValueError):
            return C.fail("The answer promise is 7, 14 or 30 days.")
        if pd not in (7, 14, 30):
            return C.fail("The answer promise is 7, 14 or 30 days.")
        changes["promise_days"] = pd
    if changes:
        t.update(**changes)
    return C.ok(crew=crew_dict(t, me, role))


@anvil.server.callable(require_user=True)
def save_columns(team_id, columns):
    """The board's columns. Each belongs to a stage (ready, doing, review, done); a stage can have several
    (Doing -> Build, Test) with their own WIP limits. Cards in a removed column go to their stage's first column."""
    t, me, role = M.access(team_id)
    if not isinstance(columns, list) or not columns:
        return C.fail("Send the list of columns.")
    if len(columns) > M.MAX_COLUMNS:
        return C.fail("A board can have up to %d columns." % M.MAX_COLUMNS)
    incoming = []
    for c in columns:
        if not isinstance(c, dict):
            continue
        name = C.text(c.get("name"), 20)
        if not name:
            return C.fail("Every column needs a name.")
        cid = str(c.get("id") or "")
        if not re.match(r"^[a-z0-9_]{1,24}$", cid):
            cid = "c" + "".join(random.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(6))
        incoming.append(dict(c, id=cid, name=name))
    for st in M.BOARD:
        if not any(c.get("stage") == st for c in incoming):
            return C.fail("Keep at least one %s column: agents, levels and reports rely on it." % M.STATUS_LABEL[st])
    cols = M.clean_columns(incoming)
    ids = set(c["id"] for c in cols)
    for card in app_tables.cards.search(team=t):
        if card["column"] and card["column"] not in ids:
            card["column"] = None
    t["columns"] = cols
    M.log(t, "crew", "%s changed the board columns: %s." % (C.name_of(me), ", ".join(c["name"] for c in cols)), user=me,
          demo=bool(t["is_demo"]))
    return C.ok(columns=cols)


@anvil.server.callable(require_user=True)
def new_join_code(team_id):
    t, me, role = M.access(team_id, owner=True)
    if t["is_demo"]:
        return C.fail("Demo crews don't have a join code.")
    t["join_code"] = _code()
    return C.ok(code=t["join_code"])


@anvil.server.callable(require_user=True)
def remove_member(team_id, user_id):
    t, me, role = M.access(team_id, owner=True)
    u = C.row_by_id(app_tables.users, user_id)
    m = app_tables.members.get(team=t, user=u) if u is not None else None
    if m is None:
        return C.ok()
    if u == me:
        return C.fail("You can't remove yourself. Delete the crew instead, or hand it over first.")
    for c in app_tables.cards.search(team=t, assignee_user=u):
        c["assignee_user"] = None
    m.delete()
    M.log(t, "crew", "%s removed %s from the crew." % (C.name_of(me), C.name_of(u)), user=me)
    return C.ok()


@anvil.server.callable(require_user=True)
def make_owner(team_id, user_id):
    t, me, role = M.access(team_id, owner=True)
    u = C.row_by_id(app_tables.users, user_id)
    m = app_tables.members.get(team=t, user=u) if u is not None else None
    if m is None or t["is_demo"]:
        return C.fail("That person isn't in this crew.")
    m["role"] = "owner"
    mine = app_tables.members.get(team=t, user=me)
    if mine is not None and u != me:
        mine["role"] = "member"
    t["owner"] = u
    M.log(t, "crew", "%s handed the crew to %s." % (C.name_of(me), C.name_of(u)), user=me)
    return C.ok()


@anvil.server.callable(require_user=True)
def leave_crew(team_id):
    t, me, role = M.access(team_id)
    if role == "sandbox":
        return C.ok()
    if role == "owner":
        return C.fail("Owners can't leave. Hand the crew to someone else first, or delete it.")
    for c in app_tables.cards.search(team=t, assignee_user=me):
        c["assignee_user"] = None
    app_tables.members.get(team=t, user=me).delete()
    M.log(t, "crew", "%s left the crew." % C.name_of(me), user=me)
    return C.ok()


@anvil.server.callable(require_user=True)
def delete_crew(team_id, confirm_key):
    t, me, role = M.access(team_id, owner=True)
    if t["is_demo"]:
        return C.fail("Demo crews are removed from Admin -> Demo data.")
    if C.text(confirm_key, 10).upper() != t["key"]:
        return C.fail("Type the crew's card prefix (%s) to confirm." % t["key"])
    M.delete_team_rows(t)
    return C.ok()


@anvil.server.callable(require_user=True)
def set_level(team_id, level, force=False):
    """Move the crew to another maturity level. Going up needs the criteria met (or force=True,
    which is recorded); going down is always allowed."""
    t, me, role = M.access(team_id)
    try:
        level = int(level)
    except (TypeError, ValueError):
        return C.fail("Pick a level from 1 to 4.")
    if not 1 <= level <= 4:
        return C.fail("Pick a level from 1 to 4.")
    cur = t["level"] or 1
    if level == cur:
        return C.ok(level=cur)
    forced = False
    if level > cur:
        if level > cur + 1:
            return C.fail("Level up one step at a time.")
        mat = Metrics.maturity(t)
        if not mat["next"] or not mat["next"]["eligible"]:
            if not force:
                return C.fail("Not there yet: %d of %d checks pass. You can force it, but forecasts will be guesswork."
                              % (mat["next"]["passed"], mat["next"]["total"]) if mat["next"] else "Already at the top level.")
            forced = True
    log = list(t["level_log"] or [])
    log.append({"level": level, "at": C.iso(C.now()), "by": C.name_of(me), "forced": forced})
    t.update(level=level, level_log=log[-30:])
    info = M.level_info(level)
    M.log(t, "level", "%s moved the crew to level %d: %s%s." % (C.name_of(me), level, info["name"], " (forced)" if forced else ""),
          user=me, demo=bool(t["is_demo"]))
    return C.ok(level=level, forced=forced, info=info)
