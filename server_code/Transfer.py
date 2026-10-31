"""Import and export: your data comes in with its history and goes out whole, whenever you like.

import_cards: the Import page (web/pages/import.html) reads a Jira CSV, a Trello JSON or CSV, any CSV, or an
AutoAgile export in the browser, lets the person map fields and statuses, and sends the cards here in batches.
Dates are kept (created, started, resolved), so the crew's throughput, cycle times and level checks work from
day one. Every imported card remembers where it came from (source, like "jira:ABC-12"), so importing the same
file twice skips what is already there.
export_crew: everything about a crew in one JSON document (the Import page can read it back), plus a CSV of the
cards on the client side.
"""
import datetime as dt
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Gates

MAX_BATCH = 250
TYPE_MAP = {"bug": "bug", "defect": "bug", "incident": "bug", "problem": "bug", "story": "story", "user story": "story",
            "feature": "story", "new feature": "story", "improvement": "story", "enhancement": "story", "epic": "story",
            "task": "task", "sub-task": "task", "subtask": "task", "to-do": "task", "todo": "task", "spike": "spike",
            "research": "spike", "investigation": "spike", "chore": "chore", "technical task": "chore", "maintenance": "chore",
            "tech debt": "chore", "refactor": "chore"}


def parse_when(v):
    """ISO date or datetime string -> aware datetime (UTC), or None. Future dates are clamped to now."""
    if not v or not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s[:32])
    except ValueError:
        try:
            d = dt.datetime.fromisoformat(s[:10])
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    d = d.astimezone(dt.timezone.utc)
    if d.year < 1990:
        return None
    return min(d, C.now())


def snap_points(v):
    try:
        p = float(v)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return min(Gates.POINTS, key=lambda x: (abs(x - p), x))


def _match_person(t, name, members, agents):
    s = C.text(name, 120).lower()
    if not s:
        return None, None
    for a in agents:
        if a["name"].lower() == s:
            return None, a
    for u in members:
        if (u["email"] or "").lower() == s or C.name_of(u).lower() == s or (u["display_name"] or "").lower() == s:
            return u, None
    for u in members:
        first = C.name_of(u).lower().split(" ")[0]
        if first and s.split(" ")[0] == first and len(first) > 2:
            return u, None
    return None, None


@anvil.server.callable(require_user=True)
def import_cards(team_id, items, opts=None):
    t, me, role = M.access(team_id)
    if role == "sandbox":
        return C.fail("Demo crews are a shared sandbox. Start your own crew and import into it.")
    if not isinstance(items, list) or not items:
        return C.fail("Nothing to import.")
    if len(items) > MAX_BATCH:
        return C.fail("Send at most %d cards at a time." % MAX_BATCH)
    if C.rate_limited("import_cards", 60, 3600):
        return C.fail("That's a lot of imports this hour. Try again later.")
    opts = opts if isinstance(opts, dict) else {}
    history = opts.get("history", True) is not False
    make_epics = opts.get("epics", True) is not False
    label = C.text(opts.get("from"), 30) or "import"

    cols = M.columns_of(t)
    col_stage = {c["id"]: c["stage"] for c in cols}
    members = [m["user"] for m in M.members_of(t) if m["user"] is not None]
    agents = list(app_tables.agents.search(team=t))
    have = set(c["source"] for c in app_tables.cards.search(team=t) if c["source"])
    epics = {(e["title"] or "").lower(): e for e in app_tables.epics.search(team=t)}
    rank = M.next_rank(t)
    epic_rank = max([e["rank"] or 0 for e in epics.values()] + [0])
    out = {"created": 0, "duplicates": 0, "invalid": 0, "epics_created": 0, "comments": 0, "unmatched": [], "keys": []}
    now = C.now()

    for it in items:
        if not isinstance(it, dict):
            out["invalid"] += 1
            continue
        title = C.text(it.get("title"), 200)
        if len(title) < 2:
            out["invalid"] += 1
            continue
        source = C.text(it.get("source"), 120)
        if source and source in have:
            out["duplicates"] += 1
            continue
        status, column = "backlog", None
        st = it.get("status")
        if st in M.STATUSES:
            status = st
        elif st in col_stage:
            status, column = col_stage[st], st
        typ = TYPE_MAP.get(C.text(it.get("type"), 40).lower(), "story") if it.get("type") not in M.TYPES else it.get("type")
        try:
            prio = int(it.get("priority"))
            prio = prio if prio in M.PRIORITIES else 2
        except (TypeError, ValueError):
            prio = 2
        pts = snap_points(it.get("points"))
        gates = Gates.clean(it.get("gates") or {}) if isinstance(it.get("gates"), dict) else {}
        g = Gates.score(gates) if gates else {}
        if g.get("complete"):
            pts, src = g["points"], "gates"
        else:
            gates, src = {}, ("manual" if pts else None)
        labels = [C.text(x, 24) for x in (it.get("labels") or []) if C.text(x, 24)][:6] if isinstance(it.get("labels"), list) else []
        body = C.text(it.get("body"), 8000, multiline=True)
        u, a = _match_person(t, it.get("assignee"), members, agents) if it.get("assignee") else (None, None)
        if it.get("assignee") and u is None and a is None:
            who = C.text(it.get("assignee"), 60)
            if who not in out["unmatched"] and len(out["unmatched"]) < 20:
                out["unmatched"].append(who)
            body = (body + "\n\n" if body else "") + "Assignee in %s: %s" % (label, who)
        epic = None
        ename = C.text(it.get("epic"), 120)
        if ename:
            epic = epics.get(ename.lower())
            if epic is None and make_epics:
                epic_rank += 1000
                epic = app_tables.epics.add_row(team=t, title=ename, body="Imported from %s." % label,
                                                color=M.COLORS[len(epics) % len(M.COLORS)], size=None, quarter="", status="active",
                                                rank=epic_rank, created=now, is_demo=False)
                epics[ename.lower()] = epic
                out["epics_created"] += 1
        created = (parse_when(it.get("created")) if history else None) or now
        started = parse_when(it.get("started")) if history else None
        review_at = parse_when(it.get("review_at")) if history else None
        done_at = parse_when(it.get("done_at")) if history else None
        if status == "done" and done_at is None and history:
            done_at = parse_when(it.get("updated"))
        if status not in ("done",):
            done_at = None
        if status in ("doing", "review", "done") and started is not None and started < created:
            started = created
        links = []
        url = C.text(it.get("url"), 400)
        if re.match(r"^https?://", url):
            links.append({"label": (source.split(":", 1)[-1] if source else label)[:60], "url": url})
        acc = [{"text": C.text(x.get("text"), 200), "done": bool(x.get("done"))} for x in (it.get("acceptance") or [])
               if isinstance(x, dict) and C.text(x.get("text"), 200)][:20] if isinstance(it.get("acceptance"), list) else []
        n = t["next_number"] or 1
        t["next_number"] = n + 1
        rank += 1000
        c = app_tables.cards.add_row(team=t, number=n, title=title, body=body, type=typ, status=status, column=column, priority=prio,
                                     rank=rank, points=pts, points_src=src, gates=gates, acceptance=acc, labels=labels, links=links,
                                     blocked=False, blocked_reason="", assignee_user=u, assignee_agent=a, epic=epic, created=created,
                                     created_by=me, updated=now, moved_at=done_at or review_at or started or created, started=started,
                                     review_at=review_at if status in ("review", "done") else None, done_at=done_at,
                                     source=source or None, is_demo=False)
        if source:
            have.add(source)
        for cm in (it.get("comments") or [])[:50] if isinstance(it.get("comments"), list) else []:
            if not isinstance(cm, dict) or not C.text(cm.get("text"), 2000, multiline=True):
                continue
            who = C.text(cm.get("who"), 60) or "someone"
            M.log(t, "comment", "[%s] %s: %s" % (label, who, C.text(cm.get("text"), 1900, multiline=True)), card=c,
                  when=parse_when(cm.get("created")) or created)
            out["comments"] += 1
        out["created"] += 1
        out["keys"] = out["keys"][:1] + [M.card_key(c)]  # the first and the last new key
    if out["created"]:
        M.log(t, "import", "%s imported %d card%s from %s." % (C.name_of(me), out["created"], "" if out["created"] == 1 else "s", label), user=me)
    return C.ok(**out)


@anvil.server.callable(require_user=True)
def export_crew(team_id):
    """Everything about the crew as one JSON-able document (format autoagile-export v1)."""
    t, me, role = M.access(team_id)
    if C.rate_limited("export_crew", 20, 3600):
        return C.fail("That's a lot of exports this hour. Try again later.")
    cards = sorted(app_tables.cards.search(team=t), key=lambda c: c["number"] or 0)
    cols = M.columns_of(t)
    comments = {}
    events = sorted(app_tables.events.search(team=t), key=lambda e: e["created"])
    for e in events:
        if e["card"] is not None and e["kind"] in ("comment", "agent_log", "submit"):
            who = M.person(e["actor_user"], e["actor_agent"])
            comments.setdefault(e["card"].get_id(), []).append({"who": who["name"] if who else "AutoAgile", "kind": e["kind"],
                                                                "text": e["text"], "created": C.iso(e["created"])})
    out_cards = []
    for c in cards:
        d = M.card_dict(c, full=True)
        out_cards.append({"key": d["key"], "title": d["title"], "body": d["body"], "type": d["type"], "status": d["status"],
                          "column": M.column_name(cols, M.column_of(c, cols)), "column_id": M.column_of(c, cols),
                          "priority": d["priority"], "points": d["points"], "points_src": d["points_src"], "gates": d["gates"],
                          "acceptance": d["acceptance"], "labels": d["labels"], "links": d["links"],
                          "assignee": d["assignee"]["name"] if d["assignee"] else None,
                          "assignee_kind": d["assignee"]["kind"] if d["assignee"] else None,
                          "epic": d["epic"]["title"] if d["epic"] else None, "sprint": d["sprint"]["name"] if d["sprint"] else None,
                          "blocked": d["blocked"], "blocked_reason": d["blocked_reason"], "source": d["source"],
                          "created": d["created"], "started": d["started"], "review_at": d["review_at"], "done_at": d["done_at"],
                          "comments": comments.get(c.get_id(), [])})
    epics = sorted(app_tables.epics.search(team=t), key=lambda e: e["rank"] or 0)
    sprints = sorted(app_tables.sprints.search(team=t), key=lambda s: s["number"] or 0)
    reqs = sorted(app_tables.requests.search(team=t), key=lambda r: r["created"])
    return C.ok(export={
        "format": "autoagile-export", "version": 1, "exported": C.iso(C.now()), "exported_by": C.name_of(me),
        "crew": {"name": t["name"], "key": t["key"], "mission": t["mission"] or "", "level": t["level"] or 1,
                 "sprint_days": t["sprint_days"] or 14, "wip": dict(M.DEFAULT_WIP, **(t["wip"] or {})), "dod": t["dod"] or [],
                 "agent_rules": t["agent_rules"] or "", "columns": cols, "level_log": t["level_log"] or []},
        "epics": [{"title": e["title"], "body": e["body"] or "", "size": e["size"], "quarter": e["quarter"], "status": e["status"],
                   "color": e["color"]} for e in epics],
        "sprints": [{"number": s["number"], "name": s["name"], "goal": s["goal"] or "", "start": C.iso(s["start"]), "end": C.iso(s["end"]),
                     "state": s["state"], "committed": s["committed"] or 0, "done_points": s["done_points"] or 0, "retro": s["retro"] or {}}
                    for s in sprints],
        "agents": [{"name": a["name"], "kind": a["kind"], "max_wip": a["max_wip"] or 1, "active": bool(a["active"])}
                   for a in app_tables.agents.search(team=t)],
        "requests": [{"title": r["title"], "body": r["body"] or "", "by": C.name_of(r["by_user"]) if r["by_user"] else None,
                      "votes": len(r["votes"] or []), "status": r["status"], "answer": r["answer"] or "", "created": C.iso(r["created"]),
                      "answered_at": C.iso(r["answered_at"]), "card": M.card_key(r["card"]) if r["card"] is not None else None}
                     for r in reqs],
        "cards": out_cards,
        "activity": [{"kind": e["kind"], "text": e["text"], "created": C.iso(e["created"]),
                      "card": M.card_key(e["card"]) if e["card"] is not None else None} for e in events[-5000:]],
    })
