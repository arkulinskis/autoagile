"""Numbers about how a crew works: throughput, cycle time, flow (CFD), velocity, predictability,
gate accuracy, agents vs humans. maturity() turns them into the checks that unlock the next level.

Everything is computed from the cards' timestamps (created, started, review_at, done_at) and the closed
sprints, so there is nothing extra to keep in step."""
import datetime as dt
import math

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M


def mean(xs):
    return sum(xs) / float(len(xs)) if xs else 0.0


def cv(xs):
    """Coefficient of variation (spread relative to the average)."""
    if len(xs) < 2:
        return None
    m = mean(xs)
    if m == 0:
        return None
    var = sum((x - m) ** 2 for x in xs) / float(len(xs) - 1)
    return math.sqrt(var) / m


def percentile(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p
    f = int(math.floor(k))
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def cycle_days(c):
    if c["started"] is None or c["done_at"] is None:
        return None
    return max(0.05, (c["done_at"] - c["started"]).total_seconds() / 86400.0)


def week_start(d):
    d = M.as_date(d)
    return d - dt.timedelta(days=d.weekday())


def weekly(cards, weeks=12):
    """[{week, count, points}] for the last `weeks` weeks, oldest first (the current week last)."""
    this = week_start(C.now())
    starts = [this - dt.timedelta(weeks=weeks - 1 - i) for i in range(weeks)]
    out = {s: {"week": s.isoformat(), "count": 0, "points": 0} for s in starts}
    for c in cards:
        if c["done_at"] is None:
            continue
        s = week_start(c["done_at"])
        if s in out:
            out[s]["count"] += 1
            out[s]["points"] += c["points"] or 0
    return [out[s] for s in starts]


def closed_sprints(t):
    rows = [s for s in app_tables.sprints.search(team=t) if s["state"] == "closed"]
    rows.sort(key=lambda s: s["number"] or 0)
    return rows


def velocity(t):
    return [{"id": s.get_id(), "name": s["name"], "number": s["number"], "committed": s["committed"] or 0,
             "done": s["done_points"] or 0, "start": C.iso(s["start"]), "end": C.iso(s["end"])} for s in closed_sprints(t)]


def predictability(vel):
    ratios = [min(1.0, v["done"] / float(v["committed"])) for v in vel if v["committed"]]
    return mean(ratios) if ratios else None


def velocity_range(vel, n=6):
    """(low, average, high) points per sprint from the last n closed sprints."""
    last = [v["done"] for v in vel[-n:]]
    if not last:
        return None
    avg = mean(last)
    if len(last) < 3:
        return (avg * 0.7, avg, avg * 1.2)
    return (min(last), avg, max(last))


def _check(cid, label, value, target, ok, hint, fmt="{}"):
    return {"id": cid, "label": label, "value": value, "shown": fmt.format(value) if value is not None else "n/a",
            "target": target, "ok": bool(ok), "hint": hint}


def maturity(t):
    """The crew's level and the checks for the next one."""
    level = t["level"] or 1
    cards = list(app_tables.cards.search(team=t))
    done = [c for c in cards if c["status"] == "done" and c["done_at"] is not None]
    done.sort(key=lambda c: c["done_at"])
    vel = velocity(t)
    wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
    checks = []
    if level == 1:
        first = done[0]["done_at"] if done else None
        weeks_hist = round((C.now() - first).days / 7.0, 1) if first else 0
        wk = [w["count"] for w in weekly(done, 7)[:-1]]  # the last 6 full weeks
        while wk and wk[0] == 0:
            wk.pop(0)  # weeks before the crew finished anything don't count
        if len(wk) > 2:
            wk.pop(0)  # nor does its first, partial week
        flow_cv = cv(wk) if sum(wk) else None
        over = [col for col in ("doing", "review") if len([c for c in cards if c["status"] == col]) > wip[col]]
        cyc = [cycle_days(c) for c in done[-30:] if cycle_days(c) is not None]
        stale_after = max(7.0, 3 * (percentile(cyc, 0.5) or 3))
        stale = [c for c in cards if c["status"] == "doing" and (M.days_since(c["moved_at"]) or 0) > stale_after]
        recent = done[-20:]
        gated = len([c for c in recent if c["points"] is not None]) / float(len(recent)) if recent else 0
        checks = [
            _check("throughput", "Finish 25 cards", len(done), 25, len(done) >= 25, "Keep pulling cards through to Done."),
            _check("history", "6 weeks of flow history", weeks_hist, 6, weeks_hist >= 6, "Time builds the data a sprint plan needs.", "{} wk"),
            _check("steady", "Steady weekly throughput (spread 50% or less)", round(flow_cv * 100) if flow_cv is not None else None, 50,
                   flow_cv is not None and flow_cv <= 0.5, "Finish similar amounts each week: smaller cards help.", "{}%"),
            _check("wip", "WIP limits respected right now", len(over), 0, not over,
                   "Stop starting, start finishing: %s over the limit." % ", ".join(over) if over else "Doing and Review are within limits."),
            _check("stale", "Nothing stuck in Doing over %d days" % round(stale_after), len(stale), 0, not stale,
                   "Swarm on old cards or split them."),
            _check("gates", "70% of recent cards estimated with gates", round(gated * 100), 70, gated >= 0.7,
                   "Run the gates on cards before you start them.", "{}%"),
        ]
    elif level == 2:
        last3 = vel[-3:]
        dev = None
        if len(last3) >= 3:
            m = mean([v["done"] for v in last3])
            dev = max(abs(v["done"] - m) / m for v in last3) if m else None
        pred = predictability(last3)
        avg = mean([v["done"] for v in last3]) if last3 else 0
        groomed = sum(c["points"] or 0 for c in cards if c["status"] in ("backlog", "ready") and c["points"] is not None
                      and (c["sprint"] is None or c["sprint"]["state"] != "closed"))
        checks = [
            _check("sprints", "Close 3 sprints", len(vel), 3, len(vel) >= 3, "Run sprints end to end, with a review and a retro."),
            _check("velocity", "Velocity within 25% across the last 3 sprints", round(dev * 100) if dev is not None else None, 25,
                   dev is not None and dev <= 0.25, "Commit to what you finished last time, not what you hope.", "{}%"),
            _check("predictable", "Finish 75% of what you commit", round(pred * 100) if pred is not None else None, 75,
                   pred is not None and pred >= 0.75, "Commit less, finish more.", "{}%"),
            _check("groomed", "Two sprints of estimated backlog", groomed, round(avg * 2), avg > 0 and groomed >= avg * 2,
                   "Run an estimation session on the backlog.", "{} pts"),
        ]
    elif level == 3:
        last6 = vel[-6:]
        pred = predictability(last6)
        vcv = cv([v["done"] for v in last6]) if len(last6) >= 3 else None
        epics = [e for e in app_tables.epics.search(team=t) if e["status"] != "done"]
        sized = [e for e in epics if e["size"] or app_tables.cards.search(team=t, epic=e)]
        checks = [
            _check("sprints", "Close 6 sprints", len(vel), 6, len(vel) >= 6, "A quarter of sprints gives a real range."),
            _check("predictable", "Finish 80% of commitments (last 6)", round(pred * 100) if pred is not None else None, 80,
                   pred is not None and pred >= 0.8, "Protect the sprint: say no to mid-sprint surprises.", "{}%"),
            _check("velocity", "Velocity spread 20% or less (last 6)", round(vcv * 100) if vcv is not None else None, 20,
                   vcv is not None and vcv <= 0.2, "Stable crews forecast well.", "{}%"),
            _check("epics", "3 sized epics in the plan", len(sized), 3, len(sized) >= 3, "Give each epic a size or break it into cards."),
        ]
    nxt = None
    if level < 4:
        info = M.level_info(level + 1)
        passed = len([c for c in checks if c["ok"]])
        nxt = dict(info, checks=checks, passed=passed, total=len(checks), eligible=passed == len(checks),
                   pct=round(100.0 * passed / len(checks)) if checks else 100)
    return {"level": M.level_info(level), "next": nxt}


# ----------------------------------------------------------------------------------------- insights
def cfd(cards, weeks=10):
    this = week_start(C.now()) + dt.timedelta(days=6)
    out = []
    for i in range(weeks):
        day = this - dt.timedelta(weeks=weeks - 1 - i)
        end = dt.datetime(day.year, day.month, day.day, 23, 59, tzinfo=dt.timezone.utc)
        end = min(end, C.now())
        todo = doing = done = 0
        for c in cards:
            if c["created"] is None or c["created"] > end:
                continue
            if c["done_at"] is not None and c["done_at"] <= end:
                done += 1
            elif c["started"] is not None and c["started"] <= end:
                doing += 1
            else:
                todo += 1
        out.append({"date": day.isoformat(), "todo": todo, "doing": doing, "done": done})
    return out


def gate_accuracy(done):
    """Median cycle time per points value, and how often bigger cards really took longer."""
    groups = {}
    for c in done:
        d = cycle_days(c)
        if d is None or c["points"] is None:
            continue
        groups.setdefault(int(c["points"]), []).append(d)
    rows = [{"points": p, "n": len(v), "median": round(percentile(v, 0.5), 1)} for p, v in sorted(groups.items())]
    pairs = [(a, b) for a, b in zip(rows, rows[1:]) if a["n"] >= 2 and b["n"] >= 2]
    score = round(100.0 * len([1 for a, b in pairs if b["median"] >= a["median"]]) / len(pairs)) if pairs else None
    return {"rows": rows, "score": score}


@anvil.server.callable(require_user=True)
def get_insights(team_id):
    t, me, role = M.access(team_id)
    cards = list(app_tables.cards.search(team=t))
    done = [c for c in cards if c["status"] == "done" and c["done_at"] is not None]
    recent = [c for c in done if (C.now() - c["done_at"]).days <= 90]
    cyc = [{"key": M.card_key(c), "title": c["title"], "days": round(cycle_days(c), 1), "points": c["points"],
            "done": C.iso(c["done_at"]), "agent": c["assignee_agent"] is not None}
           for c in recent if cycle_days(c) is not None]
    days = [x["days"] for x in cyc]
    vel = velocity(t)
    last8 = [c for c in done if (C.now() - c["done_at"]).days <= 56]
    agent_pts = sum(c["points"] or 0 for c in last8 if c["assignee_agent"] is not None)
    human_pts = sum(c["points"] or 0 for c in last8 if c["assignee_agent"] is None)

    def review_wait(rows):
        w = [(c["done_at"] - c["review_at"]).total_seconds() / 3600.0 for c in rows if c["review_at"] and c["done_at"] and c["done_at"] >= c["review_at"]]
        return round(mean(w), 1) if w else None
    aging = [{"key": M.card_key(c), "id": c.get_id(), "title": c["title"], "status": c["status"], "age": M.days_since(c["moved_at"]),
              "agent": c["assignee_agent"] is not None} for c in cards if c["status"] in ("doing", "review")]
    aging.sort(key=lambda a: -float(a["age"] or 0))
    vr = velocity_range(vel)
    return {"level": t["level"] or 1, "throughput": weekly(done, 12), "cycle": cyc,
            "p50": round(percentile(days, 0.5), 1) if days else None, "p85": round(percentile(days, 0.85), 1) if days else None,
            "cfd": cfd(cards), "velocity": vel, "predictability": round(predictability(vel[-6:]) * 100) if predictability(vel[-6:]) is not None else None,
            "velocity_range": [round(x, 1) for x in vr] if vr else None, "gates": gate_accuracy(recent or done),
            "split": {"agent_points": agent_pts, "human_points": human_pts,
                      "agent_review_hours": review_wait([c for c in recent if c["assignee_agent"] is not None]),
                      "human_review_hours": review_wait([c for c in recent if c["assignee_agent"] is None])},
            "aging": aging[:12], "done_total": len(done)}
