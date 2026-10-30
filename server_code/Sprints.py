"""Sprints (level 2 and up): plan, start, close (carry unfinished cards over), burndown, and the retro
(LOUDER = keep doing, MUTE = stop doing, REMIX = try next, plus action items)."""
import datetime as dt

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Cards

RETRO_KEYS = ("louder", "mute", "remix")


def _need_scrum(t):
    if (t["level"] or 1) < 2:
        raise anvil.server.PermissionDenied("Sprints unlock at level 2 (SCRUM). Keep flowing in Kanban until then.")


def _sprint(sprint_id):
    s = C.row_by_id(app_tables.sprints, sprint_id)
    if s is None:
        raise anvil.server.PermissionDenied("That sprint doesn't exist any more.")
    t, me, role = M.access(s["team"].get_id())
    return s, t, me


def _parse_date(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def burndown(s):
    """[{day, remaining, ideal}] for a sprint; remaining is None for days still ahead."""
    cards = list(app_tables.cards.search(sprint=s))
    total = sum(c["points"] or 0 for c in cards)
    start, end = M.as_date(s["start"]), M.as_date(s["end"])
    if start is None or end is None or end < start:
        return []
    n = (end - start).days
    today = M.team_today()
    out = []
    for i in range(n + 1):
        day = start + dt.timedelta(days=i)
        cut = dt.datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=dt.timezone.utc)
        rem = None
        if day <= today or s["state"] == "closed":
            rem = total - sum(c["points"] or 0 for c in cards if c["done_at"] is not None and c["done_at"] <= cut)
        out.append({"day": day.isoformat(), "remaining": rem, "ideal": round(total * (1 - i / float(n or 1)), 1)})
    return out


def sprint_full(s):
    d = Cards.sprint_brief(s)
    d.update(retro=s["retro"] or {}, closed_at=C.iso(s["closed_at"]), done_final=s["done_points"])
    return d


@anvil.server.callable(require_user=True)
def create_sprint(team_id, goal="", start=None):
    t, me, role = M.access(team_id)
    _need_scrum(t)
    rows = list(app_tables.sprints.search(team=t))
    if len([s for s in rows if s["state"] == "planned"]) >= 3:
        return C.fail("Three sprints are already planned. Start or remove one first.")
    days = t["sprint_days"] or 14
    begin = _parse_date(start)
    if begin is None:
        ends = [M.as_date(s["end"]) for s in rows if s["end"] is not None]
        begin = max(ends) + dt.timedelta(days=1) if ends else M.team_today()
        begin = max(begin, M.team_today())
    n = max([s["number"] or 0 for s in rows] + [0]) + 1
    s = app_tables.sprints.add_row(team=t, number=n, name="Sprint %d" % n, goal=C.text(goal, 200), start=begin,
                                   end=begin + dt.timedelta(days=days - 1), state="planned", committed=0, done_points=0,
                                   retro={}, is_demo=False)
    return C.ok(sprint=Cards.sprint_brief(s))


@anvil.server.callable(require_user=True)
def update_sprint(sprint_id, fields):
    s, t, me = _sprint(sprint_id)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    if "goal" in fields:
        s["goal"] = C.text(fields["goal"], 200)
    if "name" in fields and C.text(fields["name"], 40):
        s["name"] = C.text(fields["name"], 40)
    return C.ok(sprint=Cards.sprint_brief(s))


@anvil.server.callable(require_user=True)
def start_sprint(sprint_id):
    s, t, me = _sprint(sprint_id)
    _need_scrum(t)
    if s["state"] != "planned":
        return C.fail("Only a planned sprint can start.")
    if Cards.active_sprint(t) is not None:
        return C.fail("Another sprint is running. Close it first.")
    cards = list(app_tables.cards.search(sprint=s))
    if not cards:
        return C.fail("Add some cards to the sprint first.")
    today = M.team_today()
    days = t["sprint_days"] or 14
    committed = sum(c["points"] or 0 for c in cards)
    s.update(state="active", start=today, end=today + dt.timedelta(days=days - 1), committed=committed)
    for c in cards:
        if c["status"] == "backlog":
            c.update(status="ready", moved_at=C.now())
    M.log(t, "sprint", "%s started %s: %d cards, %d points.%s" % (C.name_of(me), s["name"], len(cards), committed,
                                                                 (" Goal: " + s["goal"]) if s["goal"] else ""), user=me)
    unest = len([c for c in cards if c["points"] is None])
    return C.ok(sprint=Cards.sprint_brief(s), unestimated=unest)


@anvil.server.callable(require_user=True)
def close_sprint(sprint_id, carry="next"):
    s, t, me = _sprint(sprint_id)
    if s["state"] != "active":
        return C.fail("Only the running sprint can be closed.")
    cards = list(app_tables.cards.search(sprint=s))
    done = [c for c in cards if c["status"] == "done"]
    left = [c for c in cards if c["status"] != "done"]
    target = None
    if left and carry == "next":
        planned = sorted([x for x in app_tables.sprints.search(team=t, state="planned")], key=lambda x: x["number"])
        if planned:
            target = planned[0]
        else:
            r = create_sprint(t.get_id(), "")
            target = C.row_by_id(app_tables.sprints, r["sprint"]["id"])
    for c in left:
        c["sprint"] = target
        if target is None and c["status"] == "backlog":
            c["status"] = "ready"
    done_pts = sum(c["points"] or 0 for c in done)
    s.update(state="closed", closed_at=C.now(), done_points=done_pts)
    M.log(t, "sprint", "%s closed %s: %d of %d points done, %d card%s carried %s." % (
        C.name_of(me), s["name"], done_pts, s["committed"] or 0, len(left), "" if len(left) == 1 else "s",
        ("to " + target["name"]) if target else "to the backlog"), user=me)
    return C.ok(done_points=done_pts, committed=s["committed"] or 0, carried=len(left),
                carried_to=target["name"] if target else None)


@anvil.server.callable(require_user=True)
def delete_sprint(sprint_id):
    s, t, me = _sprint(sprint_id)
    if s["state"] != "planned":
        return C.fail("Only planned sprints can be removed.")
    for c in app_tables.cards.search(sprint=s):
        c["sprint"] = None
    s.delete()
    return C.ok()


@anvil.server.callable(require_user=True)
def save_retro(sprint_id, retro):
    s, t, me = _sprint(sprint_id)
    if s["state"] == "planned":
        return C.fail("Retros happen after a sprint has run.")
    if not isinstance(retro, dict):
        return C.fail("Nothing to save.")
    out = {}
    for k in RETRO_KEYS:
        out[k] = [C.text(x, 200) for x in (retro.get(k) or []) if C.text(x, 200)][:20]
    out["actions"] = []
    for a in (retro.get("actions") or [])[:12]:
        if isinstance(a, dict) and C.text(a.get("text"), 200):
            out["actions"].append({"text": C.text(a.get("text"), 200), "done": bool(a.get("done"))})
    s["retro"] = out
    return C.ok(retro=out)


@anvil.server.callable(require_user=True)
def get_sprint(sprint_id):
    s, t, me = _sprint(sprint_id)
    cards = sorted(app_tables.cards.search(sprint=s), key=lambda c: c["rank"] or 0)
    return {"sprint": sprint_full(s), "burndown": burndown(s), "cards": [M.card_dict(c) for c in cards]}
