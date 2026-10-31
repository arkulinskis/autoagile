"""Cards: the board, the backlog, quick add, editing, moving, the complexity gates, comments, and the
agent brief (one markdown spec an AI developer can work from)."""
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Gates
from . import Metrics
from . import Alerts


# ------------------------------------------------------------------------------------------- helpers
def people(t, me):
    out, seen = [], set()
    for m in M.members_of(t):
        if m["user"] is not None and m["user"].get_id() not in seen:
            seen.add(m["user"].get_id())
            out.append(M.person(user=m["user"]))
    if me is not None and me.get_id() not in seen:
        out.append(M.person(user=me))
    for a in app_tables.agents.search(team=t):
        out.append(dict(M.person(agent=a), active=bool(a["active"])))
    return out


def epics_list(t):
    rows = list(app_tables.epics.search(team=t))
    rows.sort(key=lambda e: e["rank"] or 0)
    return [{"id": e.get_id(), "title": e["title"], "color": e["color"], "status": e["status"]} for e in rows]


def open_sprints(t):
    rows = [s for s in app_tables.sprints.search(team=t) if s["state"] in ("planned", "active")]
    rows.sort(key=lambda s: s["number"] or 0)
    return rows


def active_sprint(t):
    for s in app_tables.sprints.search(team=t, state="active"):
        return s
    return None


def sprint_brief(s):
    if s is None:
        return None
    pts = [c["points"] or 0 for c in app_tables.cards.search(sprint=s)]
    done = [c["points"] or 0 for c in app_tables.cards.search(sprint=s, status="done")]
    return {"id": s.get_id(), "name": s["name"], "number": s["number"], "goal": s["goal"] or "", "state": s["state"],
            "start": C.iso(s["start"]), "end": C.iso(s["end"]), "points": sum(pts), "done_points": sum(done),
            "cards": len(pts), "committed": s["committed"] or 0}


def apply_move(c, status, user=None, agent=None, column=None):
    """Change a card's status (stage) and keep its timestamps right (started, review_at, done_at).
    column: a column id inside that stage (None = the stage's first column)."""
    old, old_col = c["status"], c["column"]
    who = C.name_of(user) if user is not None else (agent["name"] if agent is not None else "Someone")
    if old == status:
        if column is None or column == old_col:
            return False
        cols = M.columns_of(c["team"])
        before = M.column_name(cols, M.column_of(c, cols))
        c.update(column=column, moved_at=C.now(), updated=C.now())
        M.log(c["team"], "move", "%s moved %s: %s -> %s" % (who, M.card_key(c), before, M.column_name(cols, column)),
              card=c, user=user, agent=agent)
        return True
    now = C.now()
    upd = {"status": status, "moved_at": now, "updated": now, "column": column}
    if status in ("doing", "review", "done") and c["started"] is None:
        upd["started"] = now
    if status == "review":
        upd["review_at"] = now
    if status == "done":
        upd["done_at"] = now
    elif c["done_at"] is not None:
        upd["done_at"] = None
    c.update(**upd)
    verb = "approved" if (status == "done" and old == "review") else "moved"
    M.log(c["team"], "move", "%s %s %s: %s -> %s" % (who, verb, M.card_key(c), M.STATUS_LABEL.get(old, old), M.STATUS_LABEL[status]),
          card=c, user=user, agent=agent)
    return True


def set_rank(c, before_id):
    """Put card c just before the card before_id (team-wide ranking), or at the end if None."""
    t = c["team"]
    others = [r for r in app_tables.cards.search(team=t) if r != c]
    others.sort(key=lambda r: r["rank"] or 0)
    before = C.row_by_id(app_tables.cards, before_id) if before_id else None
    if before is None or before["team"] != t or before == c:
        c["rank"] = ((others[-1]["rank"] or 0) if others else 0) + 1000
        return
    i = others.index(before)
    lo = (others[i - 1]["rank"] or 0) if i > 0 else (before["rank"] or 0) - 2000
    c["rank"] = (lo + (before["rank"] or 0)) / 2.0


def clean_acceptance(items):
    out = []
    for x in (items or [])[:20]:
        if isinstance(x, dict):
            text, done = C.text(x.get("text"), 200), bool(x.get("done"))
        else:
            text, done = C.text(x, 200), False
        if text:
            out.append({"text": text, "done": done})
    return out


def clean_links(items):
    out = []
    for x in (items or [])[:10]:
        if not isinstance(x, dict):
            continue
        url = C.text(x.get("url"), 400)
        if not re.match(r"^https?://", url):
            continue
        out.append({"label": C.text(x.get("label"), 60) or url.split("//", 1)[1][:40], "url": url})
    return out


def resolve_assignee(t, me, who):
    """who: None or {"kind": "user"|"agent", "id"}. Returns (user, agent) or raises a readable failure."""
    if not who:
        return None, None
    if not isinstance(who, dict):
        raise ValueError("Pick someone from the list.")
    if who.get("kind") == "agent":
        a = C.row_by_id(app_tables.agents, who.get("id"))
        if a is None or a["team"] != t:
            raise ValueError("That agent isn't in this crew.")
        return None, a
    u = C.row_by_id(app_tables.users, who.get("id"))
    if u is None:
        raise ValueError("That person isn't in this crew.")
    if u != me and app_tables.members.get(team=t, user=u) is None:
        raise ValueError("That person isn't in this crew.")
    return u, None


# ------------------------------------------------------------------------------------------- board
@anvil.server.callable(require_user=True)
def get_board(team_id):
    t, me, role = M.access(team_id)
    level = t["level"] or 1
    sprint = active_sprint(t) if level >= 2 else None
    if sprint is not None:
        rows = [c for c in app_tables.cards.search(sprint=sprint)]
    else:
        rows = [c for c in app_tables.cards.search(team=t) if c["status"] in ("ready", "doing", "review", "done")]
    cols = {s: [] for s in M.BOARD}
    for c in rows:
        st = "ready" if c["status"] == "backlog" else c["status"]
        if st == "done" and sprint is None and (M.days_since(c["done_at"]) or 0) > 14:
            continue
        cols[st].append(c)
    out = {}
    for s, cs in cols.items():
        if s == "done":
            cs.sort(key=lambda c: c["done_at"] or C.now(), reverse=True)
            cs = cs[:40]
        else:
            cs.sort(key=lambda c: c["rank"] or 0)
        out[s] = [M.card_dict(c) for c in cs]
    wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
    board_cols = []
    custom = M.columns_of(t)
    for col in custom:
        same = [x for x in custom if x["stage"] == col["stage"]]
        ids = [x["id"] for x in same]
        lim = col["wip"] or (wip.get(col["stage"]) if len(same) == 1 else None)
        board_cols.append(dict(col, limit=lim, split=len(same) > 1,
                               cards=[d for d in out[col["stage"]] if (d["column"] if d["column"] in ids else ids[0]) == col["id"]]))
    return {"level": level, "crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "demo": bool(t["is_demo"])},
            "wip": wip, "columns": out, "board_columns": board_cols, "sprint": sprint_brief(sprint),
            "people": people(t, me), "epics": epics_list(t), "me": me.get_id()}


@anvil.server.callable(require_user=True)
def get_backlog(team_id):
    t, me, role = M.access(team_id)
    level = t["level"] or 1
    sprints = open_sprints(t) if level >= 2 else []
    sprint_ids = set(s.get_id() for s in sprints)
    rows = [c for c in app_tables.cards.search(team=t) if c["status"] in ("backlog", "ready")
            and (c["sprint"] is None or c["sprint"]["state"] == "closed" or c["sprint"].get_id() in sprint_ids)]
    rows.sort(key=lambda c: c["rank"] or 0)
    vel = Metrics.velocity(t)
    vr = Metrics.velocity_range(vel)
    return {"level": level, "crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "sprint_days": t["sprint_days"] or 14},
            "cards": [M.card_dict(c) for c in rows if c["sprint"] is None or c["sprint"]["state"] == "closed"],
            "sprints": [dict(sprint_brief(s), cards_list=[M.card_dict(c) for c in sorted(app_tables.cards.search(sprint=s), key=lambda c: c["rank"] or 0)])
                        for s in sprints],
            "velocity": round(vr[1], 1) if vr else None, "velocity_range": [round(x, 1) for x in vr] if vr else None,
            "gates": Gates.config(), "people": people(t, me), "epics": epics_list(t)}


# ------------------------------------------------------------------------------------------- quick add
TYPE_WORDS = {"bug": "bug", "story": "story", "task": "task", "spike": "spike", "chore": "chore", "feat": "story", "fix": "bug"}


def parse_quick(t, me, text):
    """'Fix login timeout #bug !1 ~3 @303 +Offline' -> fields. Unknown tokens stay in the title."""
    words, title = C.text(text, 300).split(" "), []
    f = {"type": "story", "priority": 2, "points": None, "user": None, "agent": None, "epic": None, "labels": []}
    for w in words:
        lw = w.lower()
        if lw.startswith("#") and len(lw) > 1:
            if lw[1:] in TYPE_WORDS:
                f["type"] = TYPE_WORDS[lw[1:]]
            else:
                f["labels"].append(C.text(w[1:], 24))
            continue
        m = re.match(r"^!p?([0-3])$", lw)
        if m:
            f["priority"] = int(m.group(1))
            continue
        m = re.match(r"^~(\d{1,2})$", lw)
        if m and int(m.group(1)) in Gates.POINTS:
            f["points"] = int(m.group(1))
            continue
        if lw.startswith("@") and len(lw) > 1:
            who = lw[1:]
            hit = None
            for a in app_tables.agents.search(team=t):
                if a["name"].lower().replace(" ", "").startswith(who):
                    hit = ("agent", a)
                    break
            if hit is None:
                if who == "me":
                    hit = ("user", me)
                for p in people(t, me):
                    if hit is None and p["kind"] == "user" and p["name"].lower().startswith(who):
                        hit = ("user", app_tables.users.get_by_id(p["id"]))
            if hit:
                f[hit[0]] = hit[1]
                continue
        if lw.startswith("+") and len(lw) > 1:
            hit = None
            for e in app_tables.epics.search(team=t):
                if e["title"].lower().replace(" ", "").startswith(lw[1:]):
                    hit = e
                    break
            if hit is not None:
                f["epic"] = hit
                continue
        title.append(w)
    f["title"] = " ".join(title).strip()
    f["labels"] = [x for x in f["labels"] if x][:6]
    return f


def new_card(t, title, user=None, agent=None, **kw):
    n = t["next_number"] or 1
    t["next_number"] = n + 1
    now = C.now()
    row = dict(team=t, number=n, title=title, body="", type="story", status="backlog", priority=2, rank=M.next_rank(t),
               points=None, points_src=None, gates={}, acceptance=[], labels=[], links=[], blocked=False, blocked_reason="",
               created=now, created_by=user, updated=now, moved_at=now, is_demo=False)
    row.update(kw)
    c = app_tables.cards.add_row(**row)
    M.log(t, "create", "%s added %s" % (C.name_of(user) if user is not None else (agent["name"] if agent else "Someone"), M.card_key(c)),
          card=c, user=user, agent=agent)
    return c


@anvil.server.callable(require_user=True)
def quick_add(team_id, text, sprint_id=None):
    t, me, role = M.access(team_id)
    f = parse_quick(t, me, text)
    if len(f["title"]) < 3:
        return C.fail("Give the card a title (3 characters or more).")
    if C.rate_limited("quick_add", 120, 3600):
        return C.fail("That's a lot of cards in one hour. Take a breather.")
    sprint = None
    if sprint_id:
        sprint = C.row_by_id(app_tables.sprints, sprint_id)
        if sprint is None or sprint["team"] != t or sprint["state"] == "closed":
            return C.fail("That sprint isn't open.")
    c = new_card(t, f["title"], user=me, type=f["type"], priority=f["priority"], points=f["points"],
                 points_src="manual" if f["points"] else None, assignee_user=f["user"], assignee_agent=f["agent"],
                 epic=f["epic"], labels=f["labels"], sprint=sprint, status="ready" if sprint is not None else "backlog")
    return C.ok(card=M.card_dict(c))


# ------------------------------------------------------------------------------------------- one card
@anvil.server.callable(require_user=True)
def get_card(team_id, key):
    t, me, role = M.access(team_id)
    c = M.card_by_key(t, key) or C.row_by_id(app_tables.cards, key)
    if c is None or c["team"] != t:
        return C.fail("No card %s in this crew." % C.text(key, 20))
    events = list(app_tables.events.search(card=c))
    events.sort(key=lambda e: e["created"], reverse=True)
    return C.ok(card=M.card_dict(c, full=True), events=[M.event_dict(e) for e in events[:80]], people=people(t, me),
                epics=epics_list(t), sprints=[sprint_brief(s) for s in open_sprints(t)], gates=Gates.config(),
                level=t["level"] or 1, crew={"id": t.get_id(), "key": t["key"], "name": t["name"]})


@anvil.server.callable(require_user=True)
def update_card(card_id, fields):
    c, t, me, role = M.card_access(card_id)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    upd, notes = {}, []
    if "title" in fields:
        title = C.text(fields["title"], 200)
        if len(title) < 3:
            return C.fail("Titles need 3 characters or more.")
        upd["title"] = title
    if "body" in fields:
        upd["body"] = C.text(fields["body"], 8000, multiline=True)
    if "type" in fields:
        if fields["type"] not in M.TYPES:
            return C.fail("Unknown card type.")
        upd["type"] = fields["type"]
    if "priority" in fields:
        try:
            p = int(fields["priority"])
        except (TypeError, ValueError):
            return C.fail("Priority is P0 to P3.")
        if p not in M.PRIORITIES:
            return C.fail("Priority is P0 to P3.")
        upd["priority"] = p
    if "assignee" in fields:
        try:
            u, a = resolve_assignee(t, me, fields["assignee"])
        except ValueError as e:
            return C.fail(str(e))
        upd["assignee_user"], upd["assignee_agent"] = u, a
        notes.append("assigned it to %s" % (C.name_of(u) if u else a["name"] if a else "nobody"))
    if "epic_id" in fields:
        e = C.row_by_id(app_tables.epics, fields["epic_id"]) if fields["epic_id"] else None
        if fields["epic_id"] and (e is None or e["team"] != t):
            return C.fail("That epic isn't in this crew.")
        upd["epic"] = e
    if "sprint_id" in fields:
        s = C.row_by_id(app_tables.sprints, fields["sprint_id"]) if fields["sprint_id"] else None
        if fields["sprint_id"] and (s is None or s["team"] != t or s["state"] == "closed"):
            return C.fail("That sprint isn't open.")
        upd["sprint"] = s
        if s is not None and c["status"] == "backlog":
            upd["status"] = "ready"
    if "labels" in fields:
        upd["labels"] = [C.text(x, 24) for x in (fields["labels"] or []) if C.text(x, 24)][:6]
    if "blocked" in fields:
        upd["blocked"] = bool(fields["blocked"])
        upd["blocked_reason"] = C.text(fields.get("blocked_reason"), 200) if fields["blocked"] else ""
        notes.append(("flagged it blocked: " + upd["blocked_reason"]) if fields["blocked"] else "cleared the block")
    newly_blocked = bool(upd.get("blocked")) and not c["blocked"]
    if "points" in fields:
        pts = fields["points"]
        if pts in (None, ""):
            upd["points"], upd["points_src"] = None, None
        else:
            try:
                pts = int(pts)
            except (TypeError, ValueError):
                return C.fail("Points are one of %s." % ", ".join(map(str, Gates.POINTS)))
            if pts not in Gates.POINTS:
                return C.fail("Points are one of %s." % ", ".join(map(str, Gates.POINTS)))
            upd["points"], upd["points_src"] = pts, "manual"
            notes.append("set %d points by hand" % pts)
    if "acceptance" in fields:
        upd["acceptance"] = clean_acceptance(fields["acceptance"])
    if "links" in fields:
        upd["links"] = clean_links(fields["links"])
    if upd:
        upd["updated"] = C.now()
        c.update(**upd)
        for n in notes:
            M.log(t, "edit", "%s %s" % (C.name_of(me), n), card=c, user=me)
        if newly_blocked:
            Alerts.fire(t, "blocked", "blocked:%s:%s" % (c.get_id(), C.iso(C.now())[:13]),
                        "%s is blocked: %s (%s)" % (M.card_key(c), c["title"], upd["blocked_reason"] or "no reason given"), card=c)
    return C.ok(card=M.card_dict(c, full=True))


@anvil.server.callable(require_user=True)
def move_card(card_id, status, before_id=None):
    """status: a stage (backlog, ready, doing, review, done) or one of the crew's column ids."""
    c, t, me, role = M.card_access(card_id)
    column, cols = None, M.columns_of(t)
    if status not in M.STATUSES:
        col = [x for x in cols if x["id"] == status]
        if not col:
            return C.fail("Unknown column.")
        status, column = col[0]["stage"], col[0]["id"]
    apply_move(c, status, user=me, column=column)
    if before_id is not False:
        set_rank(c, before_id)
    wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
    over = status in wip and len(app_tables.cards.search(team=t, status=status)) > wip[status]
    lim = [x["wip"] for x in cols if x["id"] == column and x["wip"]]
    if lim:
        over = over or len([x for x in app_tables.cards.search(team=t, status=status) if M.column_of(x, cols) == column]) > lim[0]
    return C.ok(card=M.card_dict(c), over_wip=over)


@anvil.server.callable(require_user=True)
def rank_card(card_id, before_id=None):
    c, t, me, role = M.card_access(card_id)
    set_rank(c, before_id)
    return C.ok()


@anvil.server.callable(require_user=True)
def estimate_card(card_id, answers):
    c, t, me, role = M.card_access(card_id)
    a = Gates.clean(answers)
    g = Gates.score(a)
    if not g["complete"]:
        return C.fail("Answer all %d gates (%d done)." % (len(Gates.GATES), g["answered"]))
    old = c["points"]
    c.update(gates=a, points=g["points"], points_src="gates", updated=C.now())
    M.log(t, "estimate", "%s ran the gates: %s pts (%s)%s" % (C.name_of(me), g["points"], g["rung"],
                                                               "" if old in (None, g["points"]) else ", was %s" % old), card=c, user=me)
    return C.ok(card=M.card_dict(c, full=True), gate=g)


@anvil.server.callable(require_user=True)
def add_comment(card_id, text):
    c, t, me, role = M.card_access(card_id)
    text = C.text(text, 2000, multiline=True)
    if len(text) < 1:
        return C.fail("Write something first.")
    if C.rate_limited("comment", 60, 3600):
        return C.fail("Lots of comments this hour. Try again in a bit.")
    e = M.log(t, "comment", text, card=c, user=me)
    return C.ok(event=M.event_dict(e))


@anvil.server.callable(require_user=True)
def delete_card(card_id):
    c, t, me, role = M.card_access(card_id)
    key = M.card_key(c)
    for e in app_tables.events.search(card=c):
        e.delete()
    for a in app_tables.alerts.search(card=c):
        a.delete()
    for r in app_tables.requests.search(card=c):
        r["card"] = None
    c.delete()
    M.log(t, "delete", "%s deleted %s" % (C.name_of(me), key), user=me)
    return C.ok()


@anvil.server.callable(require_user=True)
def search_cards(team_id, query):
    """The command palette: cards whose key or title match, best first (key hits, title starts, then the rest)."""
    t, me, role = M.access(team_id)
    q = C.text(query, 80).lower()
    if not q:
        return {"cards": []}
    num = q.lstrip("#").rpartition("-")[2]
    out = []
    for c in app_tables.cards.search(team=t):
        key, title = M.card_key(c).lower(), (c["title"] or "").lower()
        if key == q or str(c["number"]) == num:
            score = 0
        elif title.startswith(q):
            score = 1
        elif q in title or q in key or q in (c["source"] or "").lower():
            score = 2
        elif all(w in title for w in q.split()):
            score = 3
        else:
            continue
        out.append((score, c["status"] == "done", -(c["number"] or 0), c))
    out.sort(key=lambda x: x[:3])
    return {"cards": [{"key": M.card_key(c), "title": c["title"], "status": c["status"], "type": c["type"] or "story"}
                      for _, _, _, c in out[:12]]}


# ------------------------------------------------------------------------------------------- agent brief
FIT_TEXT = {"solo": "An agent can take this end to end. A human reviews before Done.",
            "pair": "An agent can do most of it; ask a human early when unsure.",
            "human": "Human-led. An agent may help, but a person owns it."}


def brief(c, api_base=None):
    """The markdown spec handed to an AI developer: goal, acceptance, gates, crew rules, how to report."""
    t = c["team"]
    d = M.card_dict(c, full=True)
    g = d["gate"]
    lines = ["# %s: %s" % (d["key"], d["title"]), ""]
    meta = ["Type: %s" % d["type"], "Priority: P%d" % d["priority"],
            "Points: %s" % ("%s (%s, %s)" % (d["points"], g.get("rung", ""), d["points_src"]) if d["points"] is not None else "not estimated")]
    if d["epic"]:
        meta.append("Epic: %s" % d["epic"]["title"])
    if d["sprint"]:
        meta.append("Sprint: %s" % d["sprint"]["name"])
    lines += ["- " + m for m in meta]
    if d["fit"]:
        lines += ["- Agent fit: %s. %s" % (Gates.FIT[d["fit"]], FIT_TEXT[d["fit"]])]
    lines += ["", "## Goal", "", d["body"].strip() or "_No description yet. Ask a human before you start._", ""]
    lines += ["## Acceptance criteria", ""]
    lines += ["- [%s] %s" % ("x" if a["done"] else " ", a["text"]) for a in d["acceptance"]] or ["- _None written. Do not start: ask for criteria._"]
    if d["gates"]:
        lines += ["", "## Complexity gates", ""]
        for gt in Gates.GATES:
            v = d["gates"].get(gt["id"])
            if v is not None:
                lines.append("- %s: %s" % (gt["name"], gt["opts"][v]))
        for n in g.get("notes", []):
            lines.append("- Note: %s" % n)
    if d["blocked"]:
        lines += ["", "## Blocked", "", d["blocked_reason"] or "Blocked. Check with a human."]
    if d["links"]:
        lines += ["", "## Links", ""] + ["- [%s](%s)" % (x["label"], x["url"]) for x in d["links"]]
    dod = t["dod"] or []
    if dod:
        lines += ["", "## Definition of Done (crew rules)", ""] + ["- %s" % x for x in dod]
    if (t["agent_rules"] or "").strip():
        lines += ["", "## House rules for agents", "", t["agent_rules"].strip()]
    base = api_base or "<app>/_/api"
    lines += ["", "## Report back", "",
              "- Log progress: `POST %s/agent/log` with `{\"key\": \"%s\", \"text\": \"...\"}`" % (base, d["key"]),
              "- Tick a criterion: `POST %s/agent/check` with `{\"key\": \"%s\", \"index\": 0, \"done\": true}`" % (base, d["key"]),
              "- Hand in for review: `POST %s/agent/submit` with `{\"key\": \"%s\", \"summary\": \"...\", \"links\": [{\"label\": \"PR\", \"url\": \"https://...\"}]}`" % (base, d["key"]),
              "- Agents never move cards to Done: a human approves in Review."]
    return "\n".join(lines) + "\n"


@anvil.server.callable(require_user=True)
def agent_brief(card_id, api_base=None):
    c, t, me, role = M.card_access(card_id)
    base = C.text(api_base, 200) if api_base and re.match(r"^https?://", str(api_base)) else None
    return C.ok(markdown=brief(c, base), key=M.card_key(c))
