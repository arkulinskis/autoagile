from anvil import *

from ._anvil_designer import DeckTemplate
from ... import aa, state


class Deck(DeckTemplate):
    """#deck, the home page: LCD stats, the agent ticker, what needs a human (Review + blocked), your cards, alerts,
    the level meter, requests, the running sprint's burndown, agents and the live feed. One call: get_deck."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        d = state.call("get_deck", self.crew["id"])
        if not d:
            return
        me = state.me() or {}
        st, nx, lv = d["stats"], d["maturity"]["next"], d["level"]
        self.hello.text = "Hi %s, welcome to %s" % ((me.get("name") or "there").split(" ")[0], d["crew"]["name"])
        state.heading(self.hello, 1)
        sp = d["sprint"]
        self.sub.text = "%s // LVL %d %s%s" % (d["crew"]["key"], lv["n"], lv["name"],
                                              (" · %s ends %s" % (sp["name"], state.short_date(sp["end"]))) if sp else "")
        self.demo_note.visible = bool(d["crew"]["demo"])
        tick = ["%s: %s%s" % (e["who"]["name"].upper(), (e["card"]["key"] + " ") if e.get("card") else "", e["text"]) for e in d["ticker"]]
        self.ticker.visible = bool(tick)
        self.ticker_text.text = "".join("+++ %s " % t for t in tick) + "+++"
        self.lcd_panel.items = [
            {"value": st["this_week"], "label": "Cards done this week"},
            {"value": st["per_week"], "label": "Avg per week (6 wk)", "cls": "cyan"},
            {"value": "--" if st["cycle"] is None else st["cycle"], "unit": "" if st["cycle"] is None else "d", "label": "Cycle time (median)", "cls": "pink"},
            {"value": st["doing"], "unit": "/%d" % st["doing_limit"], "label": "In Doing (WIP)", "cls": "red" if st["doing"] > st["doing_limit"] else ""},
            {"value": st["review"], "unit": "/%d" % st["review_limit"], "label": "Waiting for review", "cls": "red" if st["review"] > st["review_limit"] else "amber"},
        ]
        review_ids = [c["id"] for c in d["review"]]
        needs = d["review"] + [b for b in d["blocked"] if b["id"] not in review_ids]
        self.needs_panel.items = needs
        self.needs_empty.visible = not needs
        self.needs_extra.text = "%d waiting" % len(needs)
        self.mine_panel.items = d["mine"]
        self.mine_empty.visible = not d["mine"]
        self.mine_extra.text = str(len(d["mine"]))
        self.alerts_panel.items = d["alerts"]
        self.alerts_empty.visible = not d["alerts"]
        self.alerts_extra.text = str(len(d["alerts"]))
        # maturity
        self.lvl_now.text = "LVL %d %s" % (lv["n"], lv["name"])
        self.lvl_blurb.text = lv.get("blurb") or ""
        self.next_box.visible = bool(nx)
        self.top_box.visible = not nx
        self.levelup_link.visible = bool(nx and nx["eligible"])
        self.checks_link.visible = bool(nx and not nx["eligible"])
        if nx:
            self.next_name.text = "Next: %s (%s)" % (nx["name"], nx["title"])
            self.next_count.text = "%d/%d checks" % (nx["passed"], nx["total"])
            on = int(round(nx["pct"] / 100.0 * nx["total"]))
            self.meter_panel.items = [{"on": i < on} for i in range(nx["total"])]
            state.set_attr(self.meter, "aria-label", "%d%%" % nx["pct"])
        # requests
        rq = d.get("requests")
        self.req_win.visible = bool(rq)
        if rq:
            self.req_panel.items = rq["top"]
            self.req_empty.visible = not rq["top"]
            self.req_extra.text = "%d open%s" % (rq["open"], (" · %d late" % rq["late"]) if rq["late"] else "")
            self.req_win.classes["warn"] = bool(rq["late"])
        # sprint
        self.sprint_win.visible = bool(sp)
        if sp:
            self.sprint_title.text = sp["name"]
            self.sprint_extra.text = "burndown"
            self.sprint_goal.text = sp.get("goal") or "No goal set"
            self.sprint_pts.text = "%s / %s pts done · ends %s" % (sp["done_points"], sp["points"], state.short_date(sp["end"]))
            b = sp["burndown"]
            self.burn.draw("lines", {"height": 150, "title": "Sprint burndown", "x": [state.short_date(p["day"]) for p in b],
                                     "series": [{"name": "Ideal", "color": "var(--c-faint)", "values": [p["ideal"] for p in b], "dashed": True},
                                                {"name": "Points left", "color": "var(--ch-1)", "values": [p["remaining"] for p in b], "area": True}]})
        # agents + feed
        self.agents_panel.items = d["agents"]
        self.agents_empty.visible = not d["agents"]
        self.agents_extra.text = str(len(d["agents"]))
        self.feed_panel.items = d["feed"]
        self.feed_empty.visible = not d["feed"]
