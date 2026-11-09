from anvil import *

from ._anvil_designer import PlanTemplate
from ... import aa, router, state

TABS = [("level", 1), ("sprints", 2), ("quarter", 3), ("year", 4), ("epics", 1)]


class Plan(PlanTemplate):
    """#plan/<tab>: the maturity ladder and the checks for the next level (level up, force, step back), sprints
    (burndown, close + carry over, retro, velocity), the 3-month forecast (level 3), the year roadmap (level 4) and the
    epics. Locked tabs show a dimmed preview under a lock box."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        names = [t for t, _ in TABS]
        self.tab = args[0] if args and args[0] in names else "level"
        self._load()

    def _load(self):
        d = state.call("get_plan", self.crew["id"])
        if not d:
            return
        self.d = d
        lv = d["levels"][d["level"] - 1]
        self.sub.text = "%s // Level %d %s%s" % (d["crew"]["key"], d["level"], lv["name"],
                                               (" · %d%% of commitments finished" % d["predictability"]) if d["predictability"] is not None else "")
        self.demo_note.visible = bool(d["crew"].get("demo"))
        for (name, need), link, lab in zip(TABS, [self.t_level, self.t_sprints, self.t_quarter, self.t_year, self.t_epics],
                                           [None, self.tl_sprints, self.tl_quarter, self.tl_year, None]):
            link.classes["on"] = name == self.tab
            if lab is not None:
                base = {"sprints": "Sprints", "quarter": "3 months", "year": "Year"}[name]
                lab.text = base + (" 🔒" if d["level"] < need else "")
        boxes = {"level": self.level_box, "sprints": self.sprints_box, "quarter": self.quarter_box, "year": self.year_box, "epics": self.epics_box}
        for k, b in boxes.items():
            b.visible = k == self.tab
        need = dict(TABS)[self.tab]
        locked = d["level"] < need
        self.lockbox.visible = locked
        self.tab_area.classes["pl-locked"] = locked
        self.tab_body.classes["pl-preview"] = locked
        state.set_attr(self.tab_body, "aria-hidden", "true" if locked else None)
        state.set_attr(self.tab_body, "inert", "" if locked else None)
        if locked:
            L = d["levels"][need - 1]
            self.lock_title.text = "Locked // level %d" % need
            self.lock_text.text = "%s: %s. %s" % (L["name"], L["title"], L["blurb"])
            self.lock_level.text = ("Your crew is at level %d. Forecasts built on too little history are guesses dressed as plans, "
                                    "so this unlocks with your data." % d["level"])
        getattr(self, "_" + self.tab)()

    # ---------------------------------------------------------------- level
    def _level(self):
        d = self.d
        nx = d["maturity"]["next"]
        self.levels_panel.items = [dict(l, cur=d["level"]) for l in d["levels"]]
        self.checks_win.visible = bool(nx)
        self.top_win.visible = not nx
        if nx:
            self.checks_title.text = "Checks for level %d: %s" % (nx["n"], nx["name"])
            self.checks_extra.text = "%d/%d" % (nx["passed"], nx["total"])
            self.checks_win.classes["lime"] = bool(nx["eligible"])
            self.next_blurb.text = nx.get("blurb") or ""
            on = int(round(nx["pct"] / 100.0 * nx["total"]))
            self.meter_panel.items = [{"on": i < on} for i in range(nx["total"])]
            state.set_attr(self.meter, "aria-label", "%d%%" % nx["pct"])
            self.checks_panel.items = nx["checks"]
            self.levelup_button.visible = bool(nx["eligible"])
            self.levelup_button.text = "Level up to " + nx["name"]
            self.force_button.visible = not nx["eligible"]
            self.force_button.text = "Force level %d anyway" % nx["n"]
            self.force_note.visible = not nx["eligible"]
            self.force_note.text = "%d of %d checks pass." % (nx["passed"], nx["total"])
        self.levelinfo_panel.items = [dict(l, cur=d["level"]) for l in d["levels"]]
        self.down_button.visible = d["level"] > 1
        self.down_button.text = "Step back to level %d" % (d["level"] - 1)
        log = list(reversed(d["level_log"]))
        self.log_panel.items = [dict(l, lname=d["levels"][l["level"] - 1]["name"]) for l in log]
        self.log_empty.visible = not log

    def _set_level(self, n, force=False):
        r = state.call("set_level", self.crew["id"], n, bool(force))
        if not r:
            return
        if n > self.d["level"]:
            aa.rave("LEVEL UP!", "Level %s: %s%s" % (r["level"], r["info"]["name"], " (forced)" if r.get("forced") else ""))
        else:
            state.toast("Back to level %s" % r["level"], "ok")
        aa.load_crews(True)
        aa.set_crew(self.crew["id"])
        self._load()

    @handle("levelup_button", "click")
    def levelup_button_click(self, **event_args):
        self._set_level(self.d["maturity"]["next"]["n"])

    @handle("force_button", "click")
    def force_button_click(self, **event_args):
        n = self.d["maturity"]["next"]["n"]
        if confirm("Your crew hasn't passed every check. You can still try it, but forecasts will be guesswork until the data "
                   "catches up. It's recorded in the level history.", title="Force level %d?" % n,
                   buttons=[("Cancel", False), ("Force it", True)], role="app-dialog"):
            self._set_level(n, True)

    @handle("down_button", "click")
    def down_button_click(self, **event_args):
        n = self.d["level"] - 1
        if confirm("Nothing is deleted. Planning views above that level lock again until you level up.",
                   title="Step back to level %d?" % n, buttons=[("Cancel", False), ("Step back", True)], role="app-dialog"):
            self._set_level(n)

    # ---------------------------------------------------------------- sprints
    def _sprints(self):
        d = self.d
        a = d["active"]
        self.active_win.visible = bool(a)
        self.noactive_win.visible = not a
        if a:
            self.active_title.text = a["name"] + " · running"
            self.active_extra.text = "burndown"
            self.active_goal.text = a.get("goal") or "No goal set"
            self.active_meta.text = "%s – %s · %s of %s pts done · %s" % (state.short_date(a["start"]), state.short_date(a["end"]),
                                                                       a["done_points"], a["points"], state.plural(a["cards"], "card"))
            b = a["burndown"]
            self.burn.draw("lines", {"height": 220, "title": "Burndown", "x": [state.short_date(p["day"]) for p in b],
                                     "series": [{"name": "Ideal", "color": "var(--c-faint)", "values": [p["ideal"] for p in b], "dashed": True},
                                                {"name": "Points left", "color": "var(--ch-1)", "values": [p["remaining"] for p in b], "area": True}]},
                           ["Day", "Ideal", "Points left"], [[p["day"], p["ideal"], "" if p["remaining"] is None else p["remaining"]] for p in b])
        v = d["velocity"]
        self.vel_extra.text = ("%d%% predictable" % d["predictability"]) if d["predictability"] is not None else ""
        self.vel_chart.visible = bool(v)
        self.vel_empty.visible = not v
        if v:
            self.vel_chart.draw("grouped", {"height": 210, "title": "Velocity",
                                            "data": [{"label": "S%s" % x["number"], "head": x["name"], "values": [x["committed"], x["done"]]} for x in v],
                                            "series": [{"name": "Committed", "color": "var(--ch-3)"}, {"name": "Done", "color": "var(--ch-1)"}]},
                                ["Sprint", "Committed", "Done"], [[x["name"], x["committed"], x["done"]] for x in v])
        closed = [s for s in d["sprints"] if s["state"] == "closed"]
        self.past_panel.items = [dict(s, host=self) for s in closed]
        self.past_empty.visible = not closed

    @handle("goal_button", "click")
    def goal_button_click(self, **event_args):
        from ...Dialogs.TextDialog import TextDialog
        a = self.d["active"]
        v = alert(TextDialog(title="Sprint goal", value=a.get("goal") or ""), buttons=[], role="app-dialog")
        if v is not None and state.call("update_sprint", a["id"], {"goal": v}) is not None:
            self._load()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        from ...Dialogs.CloseSprint import CloseSprint
        a = self.d["active"]
        carry = alert(CloseSprint(sprint=a), buttons=[], role="app-dialog")
        if not carry:
            return
        r = state.call("close_sprint", a["id"], carry)
        if r:
            aa.rave("SPRINT DONE", "%s of %s points%s" % (r["done_points"], r["committed"], (", %s carried" % r["carried"]) if r.get("carried") else ""))
            sid = a["id"]
            if self.tab != "sprints":
                router.replace("plan", "sprints")
                self.tab = "sprints"
            self._load()
            self.open_retro(sid)

    def open_retro(self, sid):
        from ...Dialogs.RetroDialog import RetroDialog
        s = [x for x in self.d["sprints"] if x["id"] == sid][0]
        if alert(RetroDialog(sprint=s), buttons=[], role="app-dialog", large=True):
            state.toast("Retro saved", "ok")
            self._load()

    # ---------------------------------------------------------------- 3 months
    def _quarter(self):
        d = self.d
        q, cap = d["quarter"], d["capacity"]
        n = len(q["slots"])
        self.q_lcds.items = [{"value": "%s–%s" % (cap[0], cap[2]), "label": "Points per sprint (range)", "cls": "cyan"},
                             {"value": cap[1], "label": "Average velocity"},
                             {"value": q["capacity"][1], "unit": "pts", "label": "Capacity, next %d sprints" % n, "cls": "amber"},
                             {"value": q["load"], "unit": "pts", "label": "Planned epic work", "cls": "red" if q["load"] > q["capacity"][1] else "pink"}]
        self.q_extra.text = "%d sprints" % n
        self.q_note.text = ("Epics in rank order, filled into sprints at your measured velocity (%s). Bars end at the likely sprint; "
                            "whiskers run from the optimistic to the pessimistic finish. SAFE = done even at your slowest pace." % d["capacity_source"])
        state.set_attr(self.slot_lab, "style", "--n:%d" % n)
        self.slots_panel.items = q["slots"]
        self.gantt_panel.items = [dict(e, n=n) for e in q["epics"]]
        self.gantt_empty.visible = not q["epics"]

    # ---------------------------------------------------------------- year
    def _year(self):
        y = self.d["year"]
        tc = y["total_capacity"]
        self.y_lcds.items = [{"value": tc[1], "unit": "pts", "label": "Capacity this year (avg)", "cls": "cyan"},
                             {"value": "%s–%s" % (tc[0], tc[2]), "label": "Capacity range"},
                             {"value": y["total_load"], "unit": "pts", "label": "Booked epic work", "cls": "red" if y["total_load"] > tc[1] else "pink"},
                             {"value": len(y["later"]), "label": "Epics not scheduled", "cls": "amber"}]
        self.quarters_panel.items = [dict(q, qi=i, host=self) for i, q in enumerate(y["quarters"])]
        self.later_panel.items = [dict(e, host=self) for e in y["later"]]
        self.later_empty.visible = not y["later"]

    def move_epic(self, epic_id, direction):
        ep = [x for x in self.d["epics"] if x["id"] == epic_id][0]
        qs = self.d["quarters"]
        i = qs.index(ep["quarter"]) if ep.get("quarter") in qs else -1
        ni = (-1 if direction > 0 else len(qs) - 1) if i < 0 else i + direction
        nq = qs[ni] if 0 <= ni < len(qs) else ""
        if state.call("save_epic", self.crew["id"], epic_id, {"quarter": nq}) is not None:
            state.toast("%s → %s" % (ep["title"], nq or "later"), "ok")
            self._load()

    # ---------------------------------------------------------------- epics
    def _epics(self):
        e = self.d["epics"]
        self.epics_extra.text = str(len(e))
        self.epics_panel.items = [dict(x, host=self) for x in e]
        self.epics_empty.visible = not e

    def rank_epic(self, epic_id, direction):
        if state.call("rank_epic", epic_id, direction) is not None:
            self._load()

    def edit_epic(self, epic_id=None):
        from ...Dialogs.EpicDialog import EpicDialog
        d = self.d
        e = [x for x in d["epics"] if x["id"] == epic_id]
        r = alert(EpicDialog(epic=e[0] if e else None, crew_id=self.crew["id"], plan=d), buttons=[], role="app-dialog")
        if r:
            self._load()

    @handle("new_epic", "click")
    def new_epic_click(self, **event_args):
        self.edit_epic(None)
