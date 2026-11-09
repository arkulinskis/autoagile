from anvil import *
from anvil.js import window

from ._anvil_designer import InsightsTemplate
from ... import aa, state


class Insights(InsightsTemplate):
    """#insights: throughput, cycle time (agents vs humans), cumulative flow, velocity, gate accuracy, agents vs humans
    and aging work in progress. Charts come from the engine (Components/Chart) with tooltips and table views."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        d = state.call("get_insights", self.crew["id"])
        if not d:
            return
        sd = state.short_date
        self.sub.text = "%s // %d cards finished · flow measured from card timestamps" % (self.crew["key"], d["done_total"])
        self.demo_note.visible = bool(self.crew.get("demo"))
        vr = d.get("velocity_range")
        self.lcd_panel.items = [
            {"value": "--" if d["p50"] is None else d["p50"], "unit": "" if d["p50"] is None else "d", "label": "Cycle time, median"},
            {"value": "--" if d["p85"] is None else d["p85"], "unit": "" if d["p85"] is None else "d", "label": "85% finish within", "cls": "pink"},
            {"value": "--" if d["predictability"] is None else d["predictability"], "unit": "" if d["predictability"] is None else "%",
             "label": "Commitments finished", "cls": "cyan"},
            {"value": "%s–%s" % (vr[0], vr[2]) if vr else "--", "label": "Velocity range (pts)", "cls": "amber"}]
        tp = d["throughput"]
        self.tp_extra.text = "12 weeks"
        self.tp.draw("bars", {"title": "Throughput per week", "unit": "cards", "color": "var(--ch-1)", "labelEvery": 2,
                              "data": [{"label": sd(w["week"]), "head": "Week of " + sd(w["week"]), "value": w["count"]} for w in tp]},
                     ["Week of", "Cards", "Points"], [[w["week"], w["count"], w["points"]] for w in tp])
        self.cy_extra.text = "90 days"
        self.cy_note.text = "Each dot is a finished card: days from start to done. Dashed lines: half finish within %s days, 85%% within %s." % (
            d["p50"] or "?", d["p85"] or "?")
        refs = [r for r in [{"y": d["p50"], "name": "50%"} if d["p50"] is not None else None,
                            {"y": d["p85"], "name": "85%"} if d["p85"] is not None else None] if r]
        self.cy.draw("scatter", {"title": "Cycle time", "series": [{"name": "Humans", "color": "var(--ch-2)"}, {"name": "Agents", "color": "var(--ch-3)"}],
                                 "refs": refs,
                                 "points": [{"x": window.Date.parse(c["done"]), "y": c["days"], "s": 1 if c["agent"] else 0,
                                             "head": "%s · %s pts" % (c["key"], "?" if c["points"] is None else c["points"]), "label": c["title"]} for c in d["cycle"]]},
                     ["Card", "Days", "Points", "By"], [[c["key"], c["days"], "" if c["points"] is None else c["points"], "agent" if c["agent"] else "human"] for c in d["cycle"]])
        cfd = d["cfd"]
        self.cfd.draw("stack", {"title": "Cumulative flow", "x": [sd(p["date"]) for p in cfd],
                                "series": [{"name": "Done", "color": "var(--ch-1)", "values": [p["done"] for p in cfd]},
                                           {"name": "Doing", "color": "var(--ch-3)", "values": [p["doing"] for p in cfd]},
                                           {"name": "To do", "color": "var(--ch-4)", "values": [p["todo"] for p in cfd]}]},
                      ["Week ending", "To do", "Doing", "Done"], [[p["date"], p["todo"], p["doing"], p["done"]] for p in cfd])
        v = d["velocity"]
        self.vel_box.visible = bool(v)
        self.vel_empty.visible = not v
        if v:
            self.vel.draw("grouped", {"title": "Velocity", "data": [{"label": "S%s" % x["number"], "head": x["name"], "values": [x["committed"], x["done"]]} for x in v],
                                      "series": [{"name": "Committed", "color": "var(--ch-3)"}, {"name": "Done", "color": "var(--ch-1)"}]},
                          ["Sprint", "Committed", "Done"], [[x["name"], x["committed"], x["done"]] for x in v])
        g = d["gates"]
        self.gate_extra.text = ("%s%%" % g["score"]) if g["score"] is not None else ""
        self.gate_note.text = "Median days from start to done for each points value. If the gates work, bigger cards take longer." + (
            (" Bigger took longer in %s%% of steps." % g["score"]) if g["score"] is not None else "")
        self.gate.draw("bars", {"title": "Median days per points value", "unit": "days (median)", "color": "var(--ch-2)",
                                "data": [{"label": "%s pt" % r["points"], "head": "%s points · %s cards" % (r["points"], r["n"]), "value": r["median"]} for r in g["rows"]]},
                       ["Points", "Cards", "Median days"], [[r["points"], r["n"], r["median"]] for r in g["rows"]])
        sp = d["split"]
        tot = sp["agent_points"] + sp["human_points"]
        self.split_lcds.items = [{"value": sp["agent_points"], "unit": "pts", "label": "By agents", "cls": "cyan"},
                                 {"value": sp["human_points"], "unit": "pts", "label": "By humans", "cls": "pink"}]
        self.split_box.visible = bool(tot)
        if tot:
            ap = round(100.0 * sp["agent_points"] / tot)
            self.split_agent.style["width"] = "%s%%" % (100.0 * sp["agent_points"] / tot)
            state.set_attr(self.split_bar, "aria-label", "Agents %d%%, humans %d%%" % (ap, 100 - ap))
            self.agent_pct.text = "Agents %d%%" % ap
            self.human_pct.text = "Humans %d%%" % (100 - ap)
        ah, hh = sp["agent_review_hours"], sp["human_review_hours"]
        self.review_facts.text = "Agent work in review: %s\nHuman work in review: %s" % (
            "n/a" if ah is None else "%s hours on average" % ah, "n/a" if hh is None else "%s hours on average" % hh)
        self.review_warn.visible = ah is not None and hh is not None and ah > hh * 1.5
        self.age_extra.text = "oldest first"
        self.aging_panel.items = d["aging"]
        self.aging_empty.visible = not d["aging"]
