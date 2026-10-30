"""The Deck: the home page. One call with everything a crew member needs at a glance: their cards,
what needs a human (agent work in Review, blocked cards), alerts, agents, the live feed and the level."""
import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Metrics
from . import Cards
from . import Sprints


@anvil.server.callable(require_user=True)
def get_deck(team_id):
    t, me, role = M.access(team_id)
    level = t["level"] or 1
    cards = list(app_tables.cards.search(team=t))
    wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
    done = [c for c in cards if c["status"] == "done" and c["done_at"] is not None]
    wk = Metrics.weekly(done, 7)
    recent = [c for c in done if (C.now() - c["done_at"]).days <= 30]
    cyc = [Metrics.cycle_days(c) for c in recent if Metrics.cycle_days(c) is not None]
    count = {s: len([c for c in cards if c["status"] == s]) for s in M.STATUSES}

    mine = [c for c in cards if c["assignee_user"] == me and c["status"] != "done"]
    mine.sort(key=lambda c: (M.STATUSES.index(c["status"]) * -1, c["rank"] or 0))
    review = sorted([c for c in cards if c["status"] == "review"], key=lambda c: c["review_at"] or C.now())
    blocked = [c for c in cards if c["blocked"] and c["status"] != "done"]

    alerts = []
    for col in ("doing", "review"):
        if count[col] > wip[col]:
            alerts.append({"level": "bad", "text": "%s is over its WIP limit (%d of %d). Stop starting, start finishing." %
                           (M.STATUS_LABEL[col], count[col], wip[col]), "go": "board"})
    old = [c for c in cards if c["status"] == "doing" and (M.days_since(c["moved_at"]) or 0) > 5]
    if old:
        alerts.append({"level": "warn", "text": "%d card%s in Doing for more than 5 days (oldest: %s)." %
                       (len(old), "" if len(old) == 1 else "s", M.card_key(max(old, key=lambda c: M.days_since(c["moved_at"]) or 0))),
                       "go": "insights"})
    stale_review = [c for c in review if (M.days_since(c["review_at"] or c["moved_at"]) or 0) > 1]
    if stale_review:
        alerts.append({"level": "warn", "text": "%d card%s waiting over a day for review. Agents are blocked on you." %
                       (len(stale_review), "" if len(stale_review) == 1 else "s"), "go": "board"})
    unest = [c for c in cards if c["status"] == "ready" and c["points"] is None]
    if unest:
        alerts.append({"level": "info", "text": "%d Ready card%s not estimated yet. Run the gates." %
                       (len(unest), "" if len(unest) == 1 else "s"), "go": "backlog/party"})
    sprint = Cards.active_sprint(t) if level >= 2 else None
    if sprint is not None:
        left = (M.as_date(sprint["end"]) - M.team_today()).days
        if left < 0:
            alerts.append({"level": "bad", "text": "%s ended %d day%s ago. Close it and run the retro." %
                           (sprint["name"], -left, "" if left == -1 else "s"), "go": "plan"})
        elif left <= 2:
            alerts.append({"level": "warn", "text": "%s ends in %d day%s." % (sprint["name"], left, "" if left == 1 else "s"), "go": "plan"})
    elif level >= 2:
        alerts.append({"level": "info", "text": "No sprint is running. Plan one from the backlog.", "go": "backlog"})
    mat = Metrics.maturity(t)
    if mat["next"] and mat["next"]["eligible"]:
        alerts.insert(0, {"level": "good", "text": "Your crew is ready for level %d: %s. Level up on the Plan page." %
                          (mat["next"]["n"], mat["next"]["name"]), "go": "plan"})

    feed = list(app_tables.events.search(team=t))
    feed.sort(key=lambda e: e["created"], reverse=True)
    agents = sorted([M.agent_dict(a) for a in app_tables.agents.search(team=t)], key=lambda a: a["name"].lower())
    ticker = [M.event_dict(e) for e in feed if e["actor_agent"] is not None][:10]
    weeks = [w["count"] for w in wk[:-1]]
    return {"crew": {"id": t.get_id(), "name": t["name"], "key": t["key"], "mission": t["mission"] or "", "demo": bool(t["is_demo"]),
                     "role": role},
            "level": M.level_info(level), "maturity": mat,
            "stats": {"this_week": wk[-1]["count"], "per_week": round(Metrics.mean(weeks), 1) if weeks else 0,
                      "spark": [w["count"] for w in wk], "cycle": round(Metrics.percentile(cyc, 0.5), 1) if cyc else None,
                      "doing": count["doing"], "doing_limit": wip["doing"], "review": count["review"], "review_limit": wip["review"],
                      "backlog": count["backlog"] + count["ready"], "done": count["done"]},
            "mine": [M.card_dict(c) for c in mine[:12]], "review": [M.card_dict(c) for c in review[:12]],
            "blocked": [M.card_dict(c) for c in blocked[:8]], "alerts": alerts, "agents": agents,
            "feed": [M.event_dict(e) for e in feed[:16]], "ticker": ticker,
            "sprint": dict(Cards.sprint_brief(sprint), burndown=Sprints.burndown(sprint)) if sprint is not None else None}
