from anvil import *
import anvil.js

from ._anvil_designer import BoardTemplate
from ... import aa, state

LANES = [("No lanes", "none"), ("Lanes: people", "people"), ("Lanes: epics", "epic"), ("Lanes: priority", "priority"), ("Lanes: type", "type")]
PRIO = ["P0 · critical", "P1 · high", "P2 · normal", "P3 · low"]
FILTERS = ["all", "mine", "humans", "agents"]


def lane_of(mode, c):
    if mode == "people":
        a = c.get("assignee")
        return (("a:" if a["kind"] == "agent" else "u:") + a["id"]) if a else "none"
    if mode == "epic":
        return c["epic"]["id"] if c.get("epic") else "none"
    if mode == "priority":
        return str(c["priority"])
    if mode == "type":
        return c["type"]
    return "all"


def lane_fields(mode, key):
    if mode == "people":
        return {"assignee": None if key == "none" else {"kind": "agent" if key[0] == "a" else "user", "id": key[2:]}}
    if mode == "epic":
        return {"epic_id": None if key == "none" else key}
    if mode == "priority":
        return {"priority": int(key)}
    if mode == "type":
        return {"type": key}
    return None


class Board(BoardTemplate):
    """#board: the crew's columns (Crew settings can split a stage), swimlanes by person / epic / priority / type, the
    filter language, WIP limits that ask before you break them. Drag cards between columns and lanes (desktop: the
    engine's AA.dnd calls _drop); on a phone, tabs pick the column and you open a card to move it."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self.filter = state.store_get("bd.filter", "all")
        self.lanes = state.store_get("bd.lanes", "none")
        self.phone_col = state.store_get("bd.pcol", None)
        self.lanes_box.items = LANES
        self.lanes_box.selected_value = self.lanes if self.lanes in [v for _, v in LANES] else "none"
        state.set_control_attr(self.lanes_box, "aria-label", "Swimlanes")
        state.set_control_attr(self.query, "aria-label", "Filter cards")
        state.set_attr(self.query, "title", aa.QUERY_HELP)
        self.phone_panel.add_event_handler("x-pcol", self._pcol)
        aa.AA.dnd(anvil.js.get_dom_node(self.scroller), anvil.js.report_exceptions(self._drop))
        self._load()

    def _load(self):
        d = state.call("get_board", self.crew["id"])
        if not d:
            return
        self.d = d
        self.title.text = d["crew"]["name"]
        state.heading(self.title, 1)
        sp = d["sprint"]
        if sp:
            head = "%s · %s/%s pts · ends %s" % (sp["name"], sp["done_points"], sp["points"], state.short_date(sp["end"]))
        else:
            head = "No sprint running" if d["level"] >= 2 else "Kanban flow · pull, don't push"
        self.sub.text = d["crew"]["key"] + " // " + head
        self.demo_note.visible = bool(d["crew"]["demo"])
        self.banner_nosprint.visible = d["level"] >= 2 and not sp
        self.banner_goal.visible = bool(sp and sp.get("goal"))
        self.goal.text = (sp or {}).get("goal") or ""
        self.banner_kanban.visible = d["level"] == 1 and not sp
        self._draw()

    def _visible(self, c):
        me = self.d["me"]
        a = c.get("assignee")
        if self.filter == "mine" and not (a and a["kind"] == "user" and a["id"] == me):
            return False
        if self.filter == "agents" and not (a and a["kind"] == "agent"):
            return False
        if self.filter == "humans" and a and a["kind"] == "agent":
            return False
        return aa.matches(c, self.query.text or "", me)

    def _lanes_for(self, cards):
        mode, d = self.lanes, self.d
        if mode == "none":
            return [{"key": "all", "name": None}]
        out = []
        if mode == "people":
            out = [{"key": ("a:" if p["kind"] == "agent" else "u:") + p["id"], "name": p["name"], "who": p} for p in d["people"]]
            out.append({"key": "none", "name": "Unassigned"})
        elif mode == "epic":
            out = [{"key": e["id"], "name": e["title"], "color": e["color"]} for e in d["epics"]]
            out.append({"key": "none", "name": "No epic"})
        elif mode == "priority":
            out = [{"key": str(p), "name": PRIO[p]} for p in range(4)]
        else:
            out = [{"key": t, "name": t} for t in aa.TYPES]
        used = set(lane_of(mode, c) for c in cards)
        return [l for l in out if l["key"] in used]

    def _draw(self):
        cols = self.d["board_columns"]
        if not any(c["id"] == self.phone_col for c in cols):
            doing = [c for c in cols if c["stage"] == "doing"]
            self.phone_col = (doing[0] if doing else cols[0])["id"]
        for f, b in zip(FILTERS, [self.f_all, self.f_mine, self.f_humans, self.f_agents]):
            b.role = ["seg", "on"] if f == self.filter else ["seg"]
        all_cards = [x for c in cols for x in c["cards"]]
        shown = [x for x in all_cards if self._visible(x)]
        q = self.query.text or ""
        if q:
            self.hint.text = "%d of %d cards match" % (len(shown), len(all_cards))
        else:
            self.hint.text = "Ctrl K jumps anywhere · " + ("drop a card in another lane to re-assign it" if self.lanes != "none"
                                                           else "lanes group the board by person, epic, priority or type")
        n = len(cols)
        state.set_attr(self.head_grid, "style", "--n:%d" % n)
        self.heads_panel.items = [dict(c, show=c["id"] == self.phone_col) for c in cols]
        self.phone_panel.items = [{"id": c["id"], "name": c["name"], "n": len(c["cards"]), "on": c["id"] == self.phone_col} for c in cols]
        lanes = self._lanes_for(shown)
        items = []
        for lane in lanes:
            bodies = []
            for c in cols:
                cards = [dict(x, drag=True) for x in c["cards"] if self._visible(x) and (lane["key"] == "all" or lane_of(self.lanes, x) == lane["key"])]
                bodies.append({"col": c, "lane": lane["key"], "cards": cards, "show": c["id"] == self.phone_col})
            count = len([x for x in shown if lane["key"] == "all" or lane_of(self.lanes, x) == lane["key"]])
            items.append(dict(lane, bodies=bodies, n=count, cols=n))
        self.lanes_panel.items = items
        self.no_match.visible = not lanes

    # ---- tools
    def _set_filter(self, f):
        self.filter = f
        state.store_set("bd.filter", f)
        self._draw()

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    @handle("f_mine", "click")
    def f_mine_click(self, **event_args):
        self._set_filter("mine")

    @handle("f_humans", "click")
    def f_humans_click(self, **event_args):
        self._set_filter("humans")

    @handle("f_agents", "click")
    def f_agents_click(self, **event_args):
        self._set_filter("agents")

    @handle("query", "change")
    def query_change(self, **event_args):
        self._draw()

    @handle("lanes_box", "change")
    def lanes_box_change(self, **event_args):
        self.lanes = self.lanes_box.selected_value
        state.store_set("bd.lanes", self.lanes)
        self._draw()

    def _pcol(self, col_id, **event_args):
        self.phone_col = col_id
        state.store_set("bd.pcol", col_id)
        self._draw()

    # ---- drag and drop (called by the engine)
    def _drop(self, card_id, to, lane, before_id):
        cols = self.d["board_columns"]
        found = [(x, c) for c in cols for x in c["cards"] if x["id"] == card_id]
        if not found:
            return
        card, src = found[0]
        target = [c for c in cols if c["id"] == to][0]
        count = len(target["cards"]) + (0 if src["id"] == to else 1)
        if src["id"] != to and target.get("limit") and count > target["limit"]:
            if not confirm("%s allows %d cards. Stop starting, start finishing: are you sure?" % (target["name"], target["limit"]),
                           title="Over the WIP limit", buttons=[("Cancel", False), ("Move it anyway", True)], role="app-dialog"):
                self._draw()
                return
        fields = lane_fields(self.lanes, lane) if lane not in (None, "all") and lane != lane_of(self.lanes, card) else None
        r = state.call("move_card", card_id, to, before_id)
        if r is not None and src["id"] != to:
            state.toast(card["key"] + " → " + target["name"] + (" (approved)" if target["stage"] == "done" and src["stage"] == "review" else ""), "ok")
        if r is not None and fields:
            if state.call("update_card", card_id, fields) is not None:
                state.toast(card["key"] + " moved to another lane", "ok")
        self._load()
