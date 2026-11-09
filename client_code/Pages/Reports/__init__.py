from anvil import *
import datetime
import json

import anvil.js
from anvil.js import window

from ._anvil_designer import ReportsTemplate
from ... import aa, state

TABS = [("burnup", "Burn-up"), ("forecast", "Forecast"), ("flow", "Flow"), ("cycle", "Cycle time"), ("epics", "Epic map"), ("mix", "Work mix")]
INTRO = {
    "burnup": "How much is done against how much there is, over time, and when the rest will likely land.",
    "forecast": "Forecasts from your real weekly throughput. No story points needed.",
    "flow": "Where work piles up: cards per stage, every day.",
    "cycle": "How long cards take from start to done, and which ones were outliers.",
    "epics": "All the work at a glance: epics, their cards, and what is done.",
    "mix": "What kind of work the crew finished each week, and who finished it.",
}


class Reports(ReportsTemplate):
    """#reports/<tab>: progress reports drawn with d3 by the engine (AA.report in aa-engine.js): burn-up with a forecast
    cone, Monte Carlo, cumulative flow with a brush, the cycle-time control chart, the epic treemap and the work mix.
    The page owns the controls (Forms) and the KPIs; the engine draws the chart, legend and table, and keeps the CSV."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        names = [t for t, _ in TABS]
        self.tab = args[0] if args and args[0] in names else "burnup"
        s = state.store_get("rp.st", {}) or {}
        self.st: dict = {"range": s.get("range") or "12", "unit": s.get("unit") or "cards", "scope": "crew", "fscope": "crew",
                   "mode": s.get("mode") or "when", "custom": 20, "by": s.get("by") or "type", "open": s.get("open") is not False,
                   "date": (datetime.date.today() + datetime.timedelta(days=42)).isoformat()}
        self._shown = False
        self._redraw_js = anvil.js.report_exceptions(self._on_resize)
        raw = state.call("get_reports", self.crew["id"])
        if not raw:
            return
        self.data = aa.AA.reportPrep(json.dumps(raw))
        self.scopes = json.loads(aa.AA.reportScopes(self.data))
        label = dict(TABS)[self.tab]
        self.title.text = label
        state.heading(self.title, 1)
        self.sub.text = "%s // %s" % (raw["crew"]["key"], INTRO[self.tab])
        self.win_title.text = "%s // %s" % (label, raw["crew"]["key"])
        self.win_extra.text = "d3"
        self.demo_note.visible = bool(self.crew.get("demo"))
        for name, link in zip(names, [self.t_burnup, self.t_forecast, self.t_flow, self.t_cycle, self.t_epics, self.t_mix]):
            link.classes["on"] = name == self.tab
        for box, label in ((self.scope_box, "Scope"), (self.fscope_box, "Cards to finish"), (self.custom_box, "Number of cards")):
            state.set_control_attr(box, "aria-label", label)
        self.date_box.min_date = datetime.date.today() + datetime.timedelta(days=7)
        self._controls()
        aa.AA.onResize(self._redraw_js)

    @handle("", "show")
    def form_show(self, **event_args):
        self._shown = True
        self._draw()

    @handle("", "hide")
    def form_hide(self, **event_args):
        self._shown = False
        aa.AA.hideTip()

    def _on_resize(self, *a):
        if not self._shown:
            return False
        self._draw()
        return True

    def _save_prefs(self):
        st = self.st
        state.store_set("rp.st", {"range": st["range"], "unit": st["unit"], "mode": st["mode"], "by": st["by"], "open": st["open"]})

    def _controls(self):
        t, st = self.tab, self.st

        def seg(pairs, cur):
            for value, b in pairs:
                b.role = ["seg", "on"] if value == cur else ["seg"]
                state.set_control_attr(b, "aria-pressed", "true" if value == cur else "false")
        self.scope_box.visible = t == "burnup"
        self.scope_box.items = [(o[1], o[0]) for o in self.scopes]
        self.scope_box.selected_value = st["scope"]
        self.mode_seg.visible = t == "forecast"
        seg([("when", self.m_when), ("howmany", self.m_howmany)], st["mode"])
        when = t == "forecast" and st["mode"] == "when"
        self.fscope_box.visible = when
        self.fscope_box.items = [(o[1] + " (open cards)", o[0]) for o in self.scopes] + [("A number of cards...", "custom")]
        self.fscope_box.selected_value = st["fscope"]
        self.custom_box.visible = when and st["fscope"] == "custom"
        self.custom_box.text = st["custom"]
        self.date_field.visible = t == "forecast" and st["mode"] == "howmany"
        y, m, dd = st["date"].split("-")
        self.date_box.date = datetime.date(int(y), int(m), int(dd))
        self.open_seg.visible = t == "epics"
        seg([(True, self.o_open), (False, self.o_all)], st["open"])
        self.by_seg.visible = t == "mix"
        seg([("type", self.b_type), ("who", self.b_who)], st["by"])
        self.range_seg.visible = (t == "burnup" and not st["scope"].startswith("s:")) or t in ("flow", "cycle", "mix")
        seg([("4", self.r_4), ("12", self.r_12), ("26", self.r_26), ("all", self.r_all)], st["range"])
        self.unit_seg.visible = t in ("burnup", "mix")
        seg([("cards", self.u_cards), ("points", self.u_points)], st["unit"])

    def _draw(self):
        if not self._shown:
            return
        els = aa.js({})
        els.chart, els.legend, els.table = self.dom_nodes["chart"], self.dom_nodes["legend"], self.dom_nodes["table"]
        try:
            out = json.loads(aa.AA.report(self.tab, els, self.data, json.dumps(self.st)))
        except Exception as e:
            self.dom_nodes["chart"].textContent = str(e)
            return
        self.kpi_panel.items = [{"value": k[0], "label": k[1], "cls": k[2] if len(k) > 2 else ""} for k in out["kpis"]]
        self.note.text = out["note"]

    def _set(self, key, value):
        self.st[key] = value
        self._save_prefs()
        self._controls()
        self._draw()

    @handle("scope_box", "change")
    def scope_box_change(self, **event_args):
        self._set("scope", self.scope_box.selected_value)

    @handle("fscope_box", "change")
    def fscope_box_change(self, **event_args):
        self._set("fscope", self.fscope_box.selected_value)

    @handle("custom_box", "change")
    def custom_box_change(self, **event_args):
        self._set("custom", self.custom_box.text or 1)

    @handle("date_box", "change")
    def date_box_change(self, **event_args):
        if self.date_box.date:
            self._set("date", self.date_box.date.isoformat())

    @handle("m_when", "click")
    def m_when_click(self, **event_args):
        self._set("mode", "when")

    @handle("m_howmany", "click")
    def m_howmany_click(self, **event_args):
        self._set("mode", "howmany")

    @handle("o_open", "click")
    def o_open_click(self, **event_args):
        self._set("open", True)

    @handle("o_all", "click")
    def o_all_click(self, **event_args):
        self._set("open", False)

    @handle("b_type", "click")
    def b_type_click(self, **event_args):
        self._set("by", "type")

    @handle("b_who", "click")
    def b_who_click(self, **event_args):
        self._set("by", "who")

    @handle("r_4", "click")
    def r_4_click(self, **event_args):
        self._set("range", "4")

    @handle("r_12", "click")
    def r_12_click(self, **event_args):
        self._set("range", "12")

    @handle("r_26", "click")
    def r_26_click(self, **event_args):
        self._set("range", "26")

    @handle("r_all", "click")
    def r_all_click(self, **event_args):
        self._set("range", "all")

    @handle("u_cards", "click")
    def u_cards_click(self, **event_args):
        self._set("unit", "cards")

    @handle("u_points", "click")
    def u_points_click(self, **event_args):
        self._set("unit", "points")

    @handle("csv_button", "click")
    def csv_button_click(self, **event_args):
        aa.AA.reportCSV()

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        aa.AA.printReport(anvil.js.get_dom_node(self))
