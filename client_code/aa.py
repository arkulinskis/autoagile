"""AutoAgile's shared client helpers (the Python half of the old window.AA kit).

    aa.load_crews(force)   the crews this person can open (server my_crews), cached per person
    aa.current()           the crew being looked at (browser storage 'crew', else the first one)
    aa.set_crew(id)        switch crew (the header chip redraws)
    aa.need_crew(page)     the current crew, or None after sending people to #crew/new (page.redirected = True)
    aa.gate_score(a, cfg)  the complexity gates' points ladder, same rules as server_code/Gates.py
    aa.GATES_CFG           the gates config for visitors (the landing page can't call the server)
    aa.age_text / aa.short_date / aa.js(x)   small formatting + JSON-to-JS helpers
    aa.AA                  the JavaScript engine (theme/assets/aa-engine.js): charts, d3 reports, markdown, files, rave
Card chips, avatars and tags are Forms (Items/CardChip, Components/Who); only drawing stays JavaScript.
"""
import json

import anvil.server
from anvil.js import window

from . import router, state

AA = window.AA
TYPES = ["story", "bug", "task", "spike", "chore"]
STATUS = {"backlog": "Backlog", "ready": "Ready", "doing": "Doing", "review": "Review", "done": "Done"}
FIT = {"solo": "AGENT SOLO", "pair": "AGENT + HUMAN", "human": "HUMAN LED"}
_c: dict = {"crews": None, "for": None}


def js(x):
    """A Python value as a plain JavaScript object (for the engine)."""
    return window.JSON.parse(json.dumps(x))


def py(obj):
    """A JavaScript object back as plain Python (via JSON)."""
    return json.loads(window.JSON.stringify(obj))


# ---------------------------------------------------------------- crews
def forget():
    _c["crews"], _c["for"] = None, None


def crew_id():
    return state.store_get("crew")


def load_crews(force=False):
    me = state.me()
    if not me:
        return []
    if _c["crews"] is not None and not force and _c["for"] == me["id"]:
        return _c["crews"]
    r = anvil.server.call("my_crews")
    _c["crews"], _c["for"] = r["crews"], me["id"]
    c = current()
    if c:
        state.store_set("crew", c["id"])
    return _c["crews"]


def crews():
    return _c["crews"] or []


def current():
    me = state.me()
    if not _c["crews"] or not me or _c["for"] != me["id"]:
        return None
    cid = crew_id()
    for c in _c["crews"]:
        if c["id"] == cid:
            return c
    return _c["crews"][0] if _c["crews"] else None


def set_crew(cid):
    state.store_set("crew", cid)
    router.refresh_shell()


def need_crew(page):
    """The current crew for a crew page; with no crew at all, people go to #crew/new to make one."""
    load_crews()
    c = current()
    if not c:
        page.redirected = True
        router.go("crew", "new")
    return c


def update_crew_summary(cid, **fields):
    for c in _c["crews"] or []:
        if c["id"] == cid:
            c.update(fields)


# ---------------------------------------------------------------- small formatting
def short_date(iso):
    return state.short_date(iso)


def age_text(days):
    """'5h' / '3d' for the days a card has sat in its column."""
    if days is None:
        return ""
    if days < 1:
        return "%dh" % max(1, round(days * 24))
    return "%dd" % round(days)


def age_class(days):
    if days is None:
        return ""
    return "stale" if days > 5 else "old" if days > 2.5 else ""


def plural(n, one, many=None):
    return state.plural(n, one, many)


# ---------------------------------------------------------------- complexity gates (mirror of server_code/Gates.py)
GATES_CFG: dict = {
    "gates": [
        {"id": "scope", "name": "Scope", "q": "How much of the system does it touch?",
         "opts": ["One file or setting", "One module", "Several modules", "Across services or teams"]},
        {"id": "clarity", "name": "Clarity", "q": "How clear is what done looks like?",
         "opts": ["Crystal: criteria written", "Mostly clear", "Fuzzy: open questions", "Unknown: needs research"]},
        {"id": "novelty", "name": "Novelty", "q": "Have we done this before?",
         "opts": ["Routine", "Like past work", "New to this crew", "Nobody has done it"]},
        {"id": "deps", "name": "Dependencies", "q": "What must we wait on?",
         "opts": ["Nothing", "One thing we control", "Another team or API", "Several outside parties"]},
        {"id": "risk", "name": "Risk", "q": "What breaks if it goes wrong?",
         "opts": ["Nothing much", "A small feature", "User data or money", "Production or security"]},
        {"id": "verify", "name": "Verify", "q": "How do we prove it works?",
         "opts": ["Quick automated test", "Tests plus a look", "Manual QA needed", "Hard to test"]},
    ],
    "ladder": [{"min": 0, "points": 1, "name": "TICK"}, {"min": 2, "points": 2, "name": "PULSE"},
               {"min": 4, "points": 3, "name": "LOOP"}, {"min": 7, "points": 5, "name": "GROOVE"},
               {"min": 10, "points": 8, "name": "BUILD"}, {"min": 13, "points": 13, "name": "DROP"},
               {"min": 16, "points": 21, "name": "RAVE"}],
    "floors": {"2": 3, "3": 5}, "split_at": 13,
}


def gate_score(answers, cfg=None):
    cfg: dict = cfg or GATES_CFG
    a = {}
    for g in cfg["gates"]:
        v = (answers or {}).get(g["id"])
        if v in (0, 1, 2, 3) and not isinstance(v, bool):
            a[g["id"]] = int(v)
    n = len(a)
    if n < len(cfg["gates"]):
        return {"complete": False, "answered": n, "points": None}
    total = sum(a.values())
    points, rung = 1, "TICK"
    for r in cfg["ladder"]:
        if total >= r["min"]:
            points = r["points"]
    floor = 1
    for v in a.values():
        f = cfg["floors"].get(str(v))
        if f and f > floor:
            floor = f
    floored = floor > points
    points = max(points, floor)
    for r in cfg["ladder"]:
        if r["points"] == points:
            rung = r["name"]
    notes, verdict = [], "go"
    if floored:
        notes.append("A red answer raised the floor to %d points." % floor)
    if a.get("clarity") == 3:
        verdict = "spike"
        notes.append("Clarity is unknown: run a time-boxed spike before building.")
    elif points >= cfg["split_at"]:
        verdict = "split"
        notes.append("%d points will not fit one sprint comfortably: split it." % points)
    fit = "human"
    if a["clarity"] <= 1 and a["verify"] <= 1 and a["risk"] <= 1 and a["deps"] <= 1 and points <= 5:
        fit = "solo"
    elif a["clarity"] <= 2 and a["risk"] <= 2 and points <= 8:
        fit = "pair"
    return {"complete": True, "total": total, "points": points, "rung": rung, "floored": floored, "verdict": verdict,
            "fit": fit, "notes": notes}


# ---------------------------------------------------------------- filter language (board, backlog)
def parse_query(q):
    o = {"words": [], "who": [], "tags": [], "prio": [], "pts": [], "gt": None, "lt": None, "epic": [], "is": []}
    for w in str(q or "").lower().split():
        if w[0] == "@" and len(w) > 1:
            o["who"].append(w[1:])
        elif w[0] == "#" and len(w) > 1:
            o["tags"].append(w[1:])
        elif w[0] == "!" and w.lstrip("!p") in ("0", "1", "2", "3") and len(w) <= 3:
            o["prio"].append(int(w[-1]))
        elif w[0] == "~" and w[1:].isdigit() and len(w) <= 3:
            o["pts"].append(int(w[1:]))
        elif w[0] == ">" and w[1:].isdigit() and len(w) <= 3:
            o["gt"] = int(w[1:])
        elif w[0] == "<" and w[1:].isdigit() and len(w) <= 3:
            o["lt"] = int(w[1:])
        elif w[0] == "+" and len(w) > 1:
            o["epic"].append(w[1:])
        elif w.startswith("is:") and len(w) > 3:
            o["is"].append(w[3:])
        else:
            o["words"].append(w)
    o["empty"] = not any([o["words"], o["who"], o["tags"], o["prio"], o["pts"], o["gt"] is not None,
                          o["lt"] is not None, o["epic"], o["is"]])
    return o


def matches(c, q, me_id=None):
    o = parse_query(q) if isinstance(q, str) else q
    if o["empty"]:
        return True
    hay = (c["key"] + " " + c["title"]).lower()
    who = c.get("assignee")
    name = who["name"].lower().replace(" ", "") if who else ""
    labels = [x.lower() for x in (c.get("labels") or [])]
    epic = c["epic"]["title"].lower().replace(" ", "") if c.get("epic") else ""
    if not all(w in hay for w in o["words"]):
        return False
    for w in o["who"]:
        if w == "me":
            if not (who and who.get("id") == me_id):
                return False
        elif w == "none":
            if who:
                return False
        elif not name.startswith(w):
            return False
    if not all(c["type"] == t or t in labels for t in o["tags"]):
        return False
    if o["prio"] and c["priority"] not in o["prio"]:
        return False
    if o["pts"] and c["points"] not in o["pts"]:
        return False
    if o["gt"] is not None and not (c["points"] is not None and c["points"] > o["gt"]):
        return False
    if o["lt"] is not None and not (c["points"] is not None and c["points"] < o["lt"]):
        return False
    if not all(epic.startswith(e) for e in o["epic"]):
        return False
    for k in o["is"]:
        if k == "blocked" and not c["blocked"]:
            return False
        if k == "agent" and not (who and who.get("kind") == "agent"):
            return False
        if k == "human" and not (who and who.get("kind") == "user"):
            return False
        if k == "mine" and not (who and who.get("id") == me_id):
            return False
        if k == "unestimated" and c["points"] is not None:
            return False
        if k == "ready" and not c.get("agent_ready"):
            return False
    return True


QUERY_HELP = "Filter: words, @name, #bug or #label, !1, ~5, >3, +epic, is:blocked, is:agent, is:mine, is:unestimated"


# ---------------------------------------------------------------- engine calls
def copy(text, msg="Copied"):
    AA.copy(text, msg)


def rave(title, sub=""):
    AA.rave(title, sub)


def api_base():
    return window.location.origin + "/_/api"
