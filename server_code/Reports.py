"""Reports (web/pages/reports.html, drawn with d3): one call with the crew's raw history, compact.

The browser builds every report from it (burn-up with a forecast cone, Monte Carlo "when will it be done",
cumulative flow, the cycle-time control chart, the epic map, the work mix), so changing the date range or the
scope is instant and needs no second call. Cards are capped at MAX_CARDS (newest kept).
"""
import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Metrics

MAX_CARDS = 4000


@anvil.server.callable(require_user=True)
def get_reports(team_id):
    t, me, role = M.access(team_id)
    rows = sorted(app_tables.cards.search(team=t), key=lambda c: c["created"] or C.now())[-MAX_CARDS:]
    cols = M.columns_of(t)
    cards = []
    for c in rows:
        cards.append({"k": M.card_key(c), "t": c["title"], "y": c["type"] or "story", "s": c["status"], "p": c["points"],
                      "c": C.iso(c["created"]), "st": C.iso(c["started"]), "rv": C.iso(c["review_at"]), "d": C.iso(c["done_at"]),
                      "e": c["epic"].get_id() if c["epic"] else None, "sp": c["sprint"].get_id() if c["sprint"] else None,
                      "a": c["assignee_agent"] is not None, "w": (c["assignee_agent"]["name"] if c["assignee_agent"] is not None
                                                                 else C.name_of(c["assignee_user"]) if c["assignee_user"] is not None else None),
                      "col": M.column_name(cols, M.column_of(c, cols))})
    epics = sorted(app_tables.epics.search(team=t), key=lambda e: e["rank"] or 0)
    sprints = sorted(app_tables.sprints.search(team=t), key=lambda s: s["number"] or 0)
    vel = Metrics.velocity(t)
    return {"crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "level": t["level"] or 1, "demo": bool(t["is_demo"])},
            "now": C.iso(C.now()), "cards": cards,
            "epics": [{"id": e.get_id(), "title": e["title"], "color": e["color"], "size": e["size"], "status": e["status"],
                       "quarter": e["quarter"] or "", "budget": M.EPIC_SIZES.get(e["size"] or "")} for e in epics],
            "sprints": [{"id": s.get_id(), "name": s["name"], "number": s["number"], "state": s["state"], "start": C.iso(s["start"]),
                         "end": C.iso(s["end"]), "committed": s["committed"] or 0, "done": s["done_points"] or 0, "goal": s["goal"] or ""}
                        for s in sprints],
            "velocity": vel, "columns": cols}
