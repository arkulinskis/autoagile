from anvil import *

from ._anvil_designer import BacklogTemplate
from ... import aa, state

FILTERS = ["all", "unest", "agent", "bugs"]


class Backlog(BacklogTemplate):
    """#backlog: the ranked backlog, quick add with its tiny syntax (#bug !1 ~3 @claude +epic), filters, re-ranking,
    and from level 2 sprint planning against the crew's velocity. #backlog/party is Pages/Party."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self.filter = state.store_get("bl.filter", "all")
        state.set_control_attr(self.add_box, "aria-label", "New card")
        state.set_control_attr(self.add_sprint, "aria-label", "Add to")
        state.set_control_attr(self.query, "aria-label", "Filter cards")
        state.set_attr(self.query, "title", aa.QUERY_HELP)
        self.rows_panel.add_event_handler("x-rank", self._rank)
        self.rows_panel.add_event_handler("x-tosprint", self._to_sprint)
        self.rows_panel.add_event_handler("x-gate", self._gate)
        self.sprints_panel.add_event_handler("x-changed", self._load)
        self._load()

    def _load(self, **event_args):
        d = state.call("get_backlog", self.crew["id"])
        if not d:
            return
        self.d = d
        cards = d["cards"]
        unest = len([c for c in cards if c["points"] is None])
        ready = len([c for c in cards if c["agent_ready"]])
        self.sub.text = "%s // %s · %d estimated · %d agent-ready" % (d["crew"]["key"], state.plural(len(cards), "card"), len(cards) - unest, ready)
        self.party_text.text = "Estimation party" + (" (%d)" % unest if unest else "")
        self.party_link.classes["primary"] = bool(unest)
        self.demo_note.visible = bool(self.crew.get("demo"))
        sprints = d["sprints"]
        self.add_sprint.visible = bool(sprints) and d["level"] >= 2
        self.add_sprint.items = [("To the backlog", "")] + [(s["name"], s["id"]) for s in sprints]
        self.sprints_box.visible = d["level"] >= 2
        planned = [s for s in sprints if s["state"] == "planned"]
        active = any(s["state"] == "active" for s in sprints)
        self.sprints_panel.items = [{"s": s, "velocity": d.get("velocity") or 0, "active_exists": active} for s in sprints]
        self.next_win.visible = len(planned) < 3
        vr = d.get("velocity_range")
        self.velocity_text.text = "Velocity: %s%s. Plan to it, not to hope." % (
            ("%s pts" % d["velocity"]) if d.get("velocity") is not None else "unknown yet",
            (" (range %s–%s)" % (vr[0], vr[2])) if vr else "")
        self.planned = planned[0] if planned else None
        self.rank_hint.text = "Ranked: the top is next. " + (("The arrow adds a card to %s." % self.planned["name"]) if self.planned else "")
        self._draw()

    def _draw(self):
        for f, b in zip(FILTERS, [self.f_all, self.f_unest, self.f_agent, self.f_bugs]):
            b.role = ["seg", "on"] if f == self.filter else ["seg"]
        me = (state.me() or {}).get("id")
        q = self.query.text or ""

        def keep(c):
            if self.filter == "unest" and c["points"] is not None:
                return False
            if self.filter == "agent" and not c["agent_ready"]:
                return False
            if self.filter == "bugs" and c["type"] != "bug":
                return False
            return aa.matches(c, q, me)
        cards = [c for c in self.d["cards"] if keep(c)]
        self.rows_panel.items = [{"c": c, "i": i, "planned": self.planned} for i, c in enumerate(cards)]
        self.list_box.visible = bool(cards)
        self.empty.visible = not cards
        self.empty_title.text = "Nothing matches" if self.d["cards"] else "The backlog is empty"

    def _set_filter(self, f):
        self.filter = f
        state.store_set("bl.filter", f)
        self._draw()

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    @handle("f_unest", "click")
    def f_unest_click(self, **event_args):
        self._set_filter("unest")

    @handle("f_agent", "click")
    def f_agent_click(self, **event_args):
        self._set_filter("agent")

    @handle("f_bugs", "click")
    def f_bugs_click(self, **event_args):
        self._set_filter("bugs")

    @handle("query", "change")
    def query_change(self, **event_args):
        self._draw()

    # ---- quick add + sprints
    @handle("add_box", "pressed_enter")
    def add_box_pressed_enter(self, **event_args):
        self.add_button_click()

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        text = (self.add_box.text or "").strip()
        if not text:
            state.focus(self.add_box)
            return
        r = state.call("quick_add", self.crew["id"], text, self.add_sprint.selected_value or None if self.add_sprint.visible else None)
        if r:
            state.toast(r["card"]["key"] + " added", "ok")
            self.add_box.text = ""
            self._load()
            state.focus(self.add_box)

    @handle("plan_button", "click")
    def plan_button_click(self, **event_args):
        r = state.call("create_sprint", self.crew["id"], self.goal_box.text or "")
        if r:
            state.toast(r["sprint"]["name"] + " planned", "ok")
            self.goal_box.text = ""
            self._load()

    # ---- row actions
    def _rank(self, card_id, how, **event_args):
        ids = [c["id"] for c in self.d["cards"]]
        i = ids.index(card_id)
        before = None
        if how == "top":
            before = ids[0] if ids and ids[0] != card_id else None
        elif how == "up":
            before = ids[i - 1] if i > 0 else None
        else:
            before = ids[i + 2] if i + 2 < len(ids) else None
        if how in ("top", "up") and not before:
            return
        if how == "down" and i == len(ids) - 1:
            return
        if state.call("rank_card", card_id, before) is not None:
            self._load()

    def _to_sprint(self, card_id, sprint_id, **event_args):
        if state.call("update_card", card_id, {"sprint_id": sprint_id}) is not None:
            self._load()

    def _gate(self, card_id, **event_args):
        from ...Dialogs.GateDialog import GateDialog
        card = [c for c in self.d["cards"] if c["id"] == card_id][0]
        r = alert(GateDialog(card=card, cfg=self.d.get("gates")), buttons=[], role="app-dialog", large=True)
        if r:
            state.toast("%s: %s pts" % (card["key"], r["points"]), "ok")
            self._load()
