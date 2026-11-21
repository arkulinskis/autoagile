"""The standup that writes itself, and the crew's public status link.

get_standup(team_id, days): per person and agent, what happened since the last workday (or the last 7 days):
shipped, waiting in review, in progress (stuck after 3 days), blocked, and their latest note. Also as markdown for
pasting into Slack or Teams, so nobody has to hold a status meeting.

The status link (#status/<code>) is opt-in per crew: anyone with the link sees card keys and titles of what shipped
this week, what is in progress, in review and blocked, with first names and agent names. Never descriptions,
comments, emails or requests. The codes live in app_settings ("status:<code>" -> team id, "status_of:<team id>" ->
code), so no table changed for this.
"""
import datetime as dt
import secrets

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Metrics

STUCK_DAYS = 3
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def window_start(days):
    """1 = since the last workday (Monday looks back to Friday morning), otherwise `days` days back."""
    now = C.now()
    if days == 1:
        back = 3 if now.weekday() == 0 else 2 if now.weekday() == 6 else 1
        return now - dt.timedelta(days=back)
    return now - dt.timedelta(days=days)


def _first(name):
    return (name or "Someone").split(" ")[0]


def _line(c):
    return {"key": M.card_key(c), "title": c["title"] or "", "points": c["points"],
            "age": M.days_since(c["moved_at"]), "blocked_reason": c["blocked_reason"] or ""}


def _who_key(user=None, agent=None):
    if agent is not None:
        return "a:" + agent.get_id()
    if user is not None:
        return "u:" + user.get_id()
    return None


def build(t, days):
    since = window_start(days)
    cards = list(app_tables.cards.search(team=t))
    people = {}

    def slot(user=None, agent=None):
        k = _who_key(user, agent)
        if k is None:
            return None
        if k not in people:
            people[k] = {"who": M.person(user, agent), "shipped": [], "review": [], "doing": [], "blocked": [], "note": None,
                         "events": 0, "stuck": 0}
        return people[k]

    for m in M.members_of(t):
        if m["user"] is not None:
            slot(user=m["user"])
    for a in app_tables.agents.search(team=t, active=True):
        slot(agent=a)
    unassigned = {"blocked": []}
    for c in cards:
        p = slot(c["assignee_user"], c["assignee_agent"])
        if c["status"] == "done":
            if c["done_at"] is not None and c["done_at"] >= since and p is not None:
                p["shipped"].append(_line(c))
            continue
        if c["blocked"]:
            (p or unassigned)["blocked"].append(_line(c))
        if p is None:
            continue
        if c["status"] == "review":
            p["review"].append(_line(c))
        elif c["status"] == "doing":
            ln = _line(c)
            ln["stuck"] = (ln["age"] or 0) >= STUCK_DAYS
            p["stuck"] += 1 if ln["stuck"] else 0
            p["doing"].append(ln)
    for e in app_tables.events.search(team=t):
        if e["created"] is None or e["created"] < since:
            continue
        p = slot(e["actor_user"], e["actor_agent"]) if (e["actor_user"] is not None or e["actor_agent"] is not None) else None
        if p is None:
            continue
        p["events"] += 1
        if e["kind"] in ("agent_log", "comment", "submit") and (p["note"] is None or e["created"] > p["note"]["at"]):
            p["note"] = {"at": e["created"], "text": C.text(e["text"], 220), "key": M.card_key(e["card"]) if e["card"] is not None else ""}
    out = []
    for p in people.values():
        if p["note"]:
            p["note"] = dict(p["note"], at=C.iso(p["note"]["at"]))
        busy = p["shipped"] or p["review"] or p["doing"] or p["blocked"] or p["events"]
        p["quiet"] = not busy
        out.append(p)
    out.sort(key=lambda p: (p["quiet"], p["who"]["kind"] != "user", -len(p["shipped"]), p["who"]["name"].lower()))
    totals = {"shipped": sum(len(p["shipped"]) for p in out),
              "points": sum((x["points"] or 0) for p in out for x in p["shipped"]),
              "review": sum(len(p["review"]) for p in out),
              "doing": sum(len(p["doing"]) for p in out),
              "stuck": sum(p["stuck"] for p in out),
              "blocked": sum(len(p["blocked"]) for p in out) + len(unassigned["blocked"])}
    return out, totals, unassigned["blocked"], since


def markdown(t, people, totals, unassigned, days):
    head = "since the last workday" if days == 1 else "the last %d days" % days
    lines = ["*%s standup* (%s, written by AutoAgile)" % (t["name"], head),
             "Shipped %d (%d pts) · In review %d · In progress %d · Blocked %d" %
             (totals["shipped"], totals["points"], totals["review"], totals["doing"], totals["blocked"]), ""]
    for p in people:
        if p["quiet"]:
            continue
        tag = " (AI)" if p["who"]["kind"] == "agent" else ""
        lines.append("*%s%s*" % (p["who"]["name"], tag))
        for label, key in (("Shipped", "shipped"), ("In review", "review"), ("Doing", "doing"), ("Blocked", "blocked")):
            for x in p[key]:
                extra = ""
                if key == "doing" and x.get("stuck"):
                    extra = " (stuck %sd)" % int(x["age"] or 0)
                if key == "blocked" and x["blocked_reason"]:
                    extra = ": " + x["blocked_reason"]
                lines.append("• %s %s %s%s" % (label + ":", x["key"], x["title"], extra))
        if p["note"]:
            lines.append("  _Latest note: %s_" % p["note"]["text"])
        lines.append("")
    for x in unassigned:
        lines.append("• Blocked, nobody on it: %s %s" % (x["key"], x["title"]))
    quiet = [p["who"]["name"] for p in people if p["quiet"]]
    if quiet:
        lines.append("Quiet: " + ", ".join(quiet))
    return "\n".join(lines).strip() + "\n"


def code_of(t):
    return C.get_setting("status_of:" + t.get_id())


@anvil.server.callable(require_user=True)
def get_standup(team_id, days=1):
    t, me, role = M.access(team_id)
    days = 7 if days == 7 else 1
    people, totals, unassigned, since = build(t, days)
    return {"crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "demo": bool(t["is_demo"]), "role": role},
            "days": days, "since": C.iso(since), "people": people, "totals": totals, "unassigned": unassigned,
            "markdown": markdown(t, people, totals, unassigned, days), "status_code": code_of(t)}


@anvil.server.callable(require_user=True)
def status_link(team_id, on=True):
    """Switch the crew's public status link on (a fresh code each time) or off. Any member; not in demo crews."""
    t, me, role = M.access(team_id)
    if t["is_demo"] and not C.is_admin(me):
        return C.fail("Demo crews keep their example link. Start your own crew to share yours.")
    old = code_of(t)
    if old:
        row = app_tables.app_settings.get(key="status:" + old)
        if row is not None:
            row.delete()
    if not on:
        C.set_setting("status_of:" + t.get_id(), None)
        M.log(t, "crew", "%s switched the public status link off." % C.name_of(me), user=me)
        return C.ok(code=None)
    code = "".join(secrets.choice(ALPHABET) for _ in range(10))
    C.set_setting("status:" + code, t.get_id())
    C.set_setting("status_of:" + t.get_id(), code)
    M.log(t, "crew", "%s switched the public status link on." % C.name_of(me), user=me)
    return C.ok(code=code)


def set_demo_code(t, code):
    """DemoData: a fixed example link for a demo crew."""
    C.set_setting("status:" + code, t.get_id())
    C.set_setting("status_of:" + t.get_id(), code)


@anvil.server.callable
def public_status(code):
    """What anyone with a status link sees (no sign-in). Titles and keys only."""
    code = C.text(code, 20).upper()
    if C.rate_limited("status", 60, 60):
        return C.fail("Too many looks in a minute. Try again shortly.")
    tid = C.get_setting("status:" + code) if code else None
    t = C.row_by_id(app_tables.teams, tid) if tid else None
    if t is None or code_of(t) != code:
        return C.fail("This status link is switched off or was replaced. Ask the crew for the new one.")
    week = C.now() - dt.timedelta(days=7)
    cards = list(app_tables.cards.search(team=t))

    def who(c):
        if c["assignee_agent"] is not None:
            return c["assignee_agent"]["name"] + " (AI)"
        if c["assignee_user"] is not None:
            return _first(C.name_of(c["assignee_user"]))
        return ""

    def item(c):
        return {"key": M.card_key(c), "title": c["title"] or "", "who": who(c), "age": M.days_since(c["moved_at"])}

    shipped = sorted([c for c in cards if c["status"] == "done" and c["done_at"] is not None and c["done_at"] >= week],
                     key=lambda c: c["done_at"], reverse=True)
    doing = sorted([c for c in cards if c["status"] == "doing"], key=lambda c: c["rank"] or 0)
    review = sorted([c for c in cards if c["status"] == "review"], key=lambda c: c["review_at"] or C.now())
    blocked = [c for c in cards if c["blocked"] and c["status"] != "done"]
    done_all = [c for c in cards if c["status"] == "done"]
    wk = Metrics.weekly(done_all, 8)
    agents = len(app_tables.agents.search(team=t, active=True))
    return C.ok(crew={"name": t["name"], "key": t["key"], "mission": t["mission"] or "", "level": M.level_info(t["level"] or 1),
                      "demo": bool(t["is_demo"]), "agents": agents},
                shipped=[item(c) for c in shipped[:20]], doing=[item(c) for c in doing[:20]],
                review=[item(c) for c in review[:20]], blocked=len(blocked),
                totals={"shipped": len(shipped), "points": sum(c["points"] or 0 for c in shipped), "doing": len(doing),
                        "review": len(review), "per_week": round(Metrics.mean([w["count"] for w in wk[:-1]]), 1)},
                updated=C.iso(C.now()))
