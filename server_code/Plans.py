"""The Plan page: maturity level, sprints, epics, the 3-month forecast (level 3) and the year roadmap (level 4).

Forecasts use the crew's measured velocity range (low / average / high points per sprint over the last
six closed sprints). Before any sprint has closed, Kanban throughput (points per week) stands in for it.
Epic size: the points of its open cards (unestimated cards count as the crew's average card), or what is
left of its T-shirt size (S 8, M 21, L 55, XL 120) when that is bigger (not fully broken down yet)."""
import datetime as dt
import math

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Metrics
from . import Cards
from . import Sprints

EPIC_STATUSES = ["idea", "planned", "active", "done"]


def _capacity(t, vel):
    """(low, avg, high) points per sprint, and where it came from."""
    vr = Metrics.velocity_range(vel)
    if vr and vr[1] > 0:
        return vr, "velocity of the last %d sprint%s" % (min(6, len(vel)), "" if len(vel) == 1 else "s")
    done = [c for c in app_tables.cards.search(team=t, status="done") if c["done_at"] is not None]
    wk = [w["points"] for w in Metrics.weekly(done, 7)[:-1]]
    per_week = Metrics.mean(wk)
    days = t["sprint_days"] or 14
    avg = per_week * days / 7.0
    if avg <= 0:
        return (5.0, 8.0, 10.0), "a starter guess (no history yet)"
    return (avg * 0.7, avg, avg * 1.25), "Kanban throughput (no closed sprints yet)"


def avg_card_points(t):
    pts = [c["points"] for c in app_tables.cards.search(team=t) if c["points"] is not None]
    return Metrics.mean(pts) if pts else 3.0


def epic_dict(e, avg_pts):
    cards = list(app_tables.cards.search(epic=e))
    done = sum(c["points"] or 0 for c in cards if c["status"] == "done")
    open_cards = [c for c in cards if c["status"] != "done"]
    rem = sum(c["points"] for c in open_cards if c["points"] is not None) + avg_pts * len([c for c in open_cards if c["points"] is None])
    sized_by = "cards"
    budget = M.EPIC_SIZES.get(e["size"] or "M", 21) - done
    if not cards or budget > rem:
        # Not broken down yet (or only partly): the T-shirt size is the better guess.
        rem, sized_by = max(budget, 0) if cards else M.EPIC_SIZES.get(e["size"] or "M", 21), "size"
    if e["status"] == "done":
        rem = 0
    total = done + rem
    return {"id": e.get_id(), "title": e["title"], "body": e["body"] or "", "color": e["color"] or M.COLORS[0],
            "size": e["size"] or "M", "quarter": e["quarter"] or "", "status": e["status"] or "idea", "rank": e["rank"] or 0,
            "cards": len(cards), "open_cards": len(open_cards), "done_points": done, "remaining": round(rem, 1),
            "progress": round(100.0 * done / total) if total else (100 if e["status"] == "done" else 0), "sized_by": sized_by}


def _epics(t):
    avg = avg_card_points(t)
    rows = list(app_tables.epics.search(team=t))
    rows.sort(key=lambda e: (e["rank"] or 0))
    return [epic_dict(e, avg) for e in rows]


def quarter_forecast(t, epics, cap, sprints_ahead):
    low, avg, high = cap
    horizon = M.quarter_of(M.team_today() + dt.timedelta(days=sprints_ahead * (t["sprint_days"] or 14)))
    plan = [e for e in epics if e["status"] != "done" and (e["status"] == "active" or (e["quarter"] and e["quarter"] <= horizon))]
    plan.sort(key=lambda e: (e["status"] != "active", e["quarter"] or "9999", e["rank"]))
    cum, out = 0.0, []
    for e in plan:
        start = cum
        cum += e["remaining"]
        f_avg = max(1, int(math.ceil(cum / avg))) if avg else 99
        f_opt = max(1, int(math.ceil(cum / high))) if high else 99
        f_pes = max(1, int(math.ceil(cum / low))) if low else 99
        if f_pes <= sprints_ahead:
            conf = "safe"
        elif f_avg <= sprints_ahead:
            conf = "likely"
        elif f_opt <= sprints_ahead:
            conf = "stretch"
        else:
            conf = "nofit"
        out.append(dict(e, start=round(start / avg, 2) if avg else 0, finish_opt=f_opt, finish_avg=f_avg, finish_pes=f_pes,
                        confidence=conf))
    return {"epics": out, "load": round(cum, 1), "capacity": [round(x * sprints_ahead) for x in cap]}


def sprint_slots(t, n):
    """Labels and dates for the next n sprints (the running one first)."""
    days = t["sprint_days"] or 14
    act = Cards.active_sprint(t)
    rows = list(app_tables.sprints.search(team=t))
    num = (act["number"] if act else max([s["number"] or 0 for s in rows] + [0]) + 1)
    start = M.as_date(act["start"]) if act else M.team_today()
    out = []
    for i in range(n):
        s = start + dt.timedelta(days=days * i)
        out.append({"label": "S%d" % (num + i), "start": s.isoformat(), "end": (s + dt.timedelta(days=days - 1)).isoformat(),
                    "current": bool(act) and i == 0})
    return out


def year_roadmap(t, epics, cap):
    days = t["sprint_days"] or 14
    today = M.team_today()
    qs = M.quarters_from(today, 4)
    per_q = 91.0 / days
    q_start = dt.date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
    left_frac = max(0.15, 1 - (today - q_start).days / 91.0)
    buckets: list = []
    for i, q in enumerate(qs):
        f = left_frac if i == 0 else 1.0
        buckets.append({"label": q, "capacity": [round(x * per_q * f) for x in cap], "epics": [], "load": 0})
    later = []
    for e in epics:
        if e["status"] == "done":
            continue
        q = e["quarter"]
        if q and q < qs[0]:
            q = qs[0]
        if q in qs:
            b = buckets[qs.index(q)]
            b["epics"].append(e)
            b["load"] += e["remaining"]
        else:
            later.append(e)
    cum = 0.0
    caps_avg = [b["capacity"][1] for b in buckets]
    caps_low = [b["capacity"][0] for b in buckets]
    for i, b in enumerate(buckets):
        b["epics"].sort(key=lambda e: (e["status"] != "active", e["rank"]))
        for e in b["epics"]:
            cum += e["remaining"]
            fa = _which_quarter(cum, caps_avg)
            fp = _which_quarter(cum, caps_low)
            e["forecast_q"] = qs[fa] if fa < len(qs) else "later"
            e["forecast_pes"] = qs[fp] if fp < len(qs) else "later"
            e["late"] = fa > i
            e["risky"] = fp > i
        b["load"] = round(b["load"], 1)
        b["over"] = b["load"] > b["capacity"][1]
    return {"quarters": buckets, "later": later, "total_load": round(sum(b["load"] for b in buckets), 1),
            "total_capacity": [sum(b["capacity"][k] for b in buckets) for k in range(3)]}


def _which_quarter(cum, caps):
    acc = 0.0
    for i, c in enumerate(caps):
        acc += c
        if cum <= acc + 0.01:
            return i
    return len(caps)


@anvil.server.callable(require_user=True)
def get_plan(team_id):
    t, me, role = M.access(team_id)
    level = t["level"] or 1
    vel = Metrics.velocity(t)
    cap, cap_src = _capacity(t, vel)
    epics = _epics(t)
    days = t["sprint_days"] or 14
    ahead = max(1, int(round(91.0 / days)))
    sprints = sorted(app_tables.sprints.search(team=t), key=lambda s: s["number"] or 0)
    act = Cards.active_sprint(t)
    return {"crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "sprint_days": days, "demo": bool(t["is_demo"])},
            "level": level, "maturity": Metrics.maturity(t), "levels": M.LEVELS, "level_log": t["level_log"] or [],
            "sprints": [Sprints.sprint_full(s) for s in reversed(sprints)],
            "active": dict(Sprints.sprint_full(act), burndown=Sprints.burndown(act)) if act else None,
            "velocity": vel, "capacity": [round(x, 1) for x in cap], "capacity_source": cap_src,
            "predictability": round(Metrics.predictability(vel[-6:]) * 100) if Metrics.predictability(vel[-6:]) is not None else None,
            "epics": epics, "quarters": M.quarters_from(M.team_today(), 4),
            "quarter": dict(quarter_forecast(t, epics, cap, ahead), slots=sprint_slots(t, ahead)),
            "year": year_roadmap(t, epics, cap), "sizes": M.EPIC_SIZES, "colors": M.COLORS}


@anvil.server.callable(require_user=True)
def save_epic(team_id, epic_id, fields):
    t, me, role = M.access(team_id)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    e = None
    if epic_id:
        e = C.row_by_id(app_tables.epics, epic_id)
        if e is None or e["team"] != t:
            return C.fail("That epic isn't in this crew.")
    upd = {}
    if "title" in fields or e is None:
        title = C.text(fields.get("title"), 80)
        if len(title) < 2:
            return C.fail("Give the epic a name (2 characters or more).")
        upd["title"] = title
    if "body" in fields:
        upd["body"] = C.text(fields["body"], 1000, multiline=True)
    if "size" in fields:
        if fields["size"] not in M.EPIC_SIZES:
            return C.fail("Sizes are S, M, L or XL.")
        upd["size"] = fields["size"]
    if "status" in fields:
        if fields["status"] not in EPIC_STATUSES:
            return C.fail("Unknown epic status.")
        upd["status"] = fields["status"]
    if "quarter" in fields:
        q = C.text(fields["quarter"], 7)
        if q and not (len(q) == 7 and q[4:6] == "-Q" and q[:4].isdigit() and q[6] in "1234"):
            return C.fail("Quarters look like 2027-Q1.")
        upd["quarter"] = q
    if "color" in fields:
        if fields["color"] not in M.COLORS:
            return C.fail("Pick one of the colours.")
        upd["color"] = fields["color"]
    if e is None:
        n = len(app_tables.epics.search(team=t))
        e = app_tables.epics.add_row(team=t, title=upd.pop("title"), body=upd.pop("body", ""), size=upd.pop("size", "M"),
                                     status=upd.pop("status", "planned"), quarter=upd.pop("quarter", M.quarter_of(M.team_today())),
                                     color=upd.pop("color", M.COLORS[n % len(M.COLORS)]),
                                     rank=max([x["rank"] or 0 for x in app_tables.epics.search(team=t)] + [0]) + 1000,
                                     created=C.now(), is_demo=False)
        M.log(t, "epic", "%s added the epic %s" % (C.name_of(me), e["title"]), user=me)
    if upd:
        e.update(**upd)
    return C.ok(epic=epic_dict(e, avg_card_points(t)))


@anvil.server.callable(require_user=True)
def rank_epic(epic_id, direction):
    e = C.row_by_id(app_tables.epics, epic_id)
    if e is None:
        return C.fail("That epic doesn't exist any more.")
    t, me, role = M.access(e["team"].get_id())
    rows = sorted(app_tables.epics.search(team=t), key=lambda x: x["rank"] or 0)
    i = rows.index(e)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(rows):
        a, b = rows[i]["rank"] or 0, rows[j]["rank"] or 0
        if a == b:
            b = a + (1 if j > i else -1)
        rows[i]["rank"], rows[j]["rank"] = b, a
    return C.ok()


@anvil.server.callable(require_user=True)
def delete_epic(epic_id):
    e = C.row_by_id(app_tables.epics, epic_id)
    if e is None:
        return C.ok()
    t, me, role = M.access(e["team"].get_id())
    for c in app_tables.cards.search(epic=e):
        c["epic"] = None
    M.log(t, "epic", "%s removed the epic %s" % (C.name_of(me), e["title"]), user=me)
    e.delete()
    return C.ok()
