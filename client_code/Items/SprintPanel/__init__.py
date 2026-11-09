from anvil import *

from ._anvil_designer import SprintPanelTemplate
from ... import aa, state


class SprintPanel(SprintPanelTemplate):
    """A planned or running sprint on the backlog: capacity against velocity, its cards, Start / Remove.
    item = {s: sprint with cards_list, velocity, active_exists}. Raises x-changed on the panel after a change."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s, vel = self.item["s"], self.item["velocity"] or 0
        pts = sum(c["points"] or 0 for c in s["cards_list"])
        unest = len([c for c in s["cards_list"] if c["points"] is None])
        mx = max(pts, vel * 1.3, 1)
        over = bool(vel and pts > vel * 1.1)
        self.classes["lime"] = s["state"] == "active"
        self.stitle.text = s["name"] + (" · running" if s["state"] == "active" else " · planned")
        self.dates.text = "%s–%s" % (state.short_date(s["start"]), state.short_date(s["end"]))
        self.goal.visible = bool(s.get("goal"))
        self.goal.text = s.get("goal") or ""
        self.cap.classes["over"] = over
        self.planned_pts.text = "%d pts planned" % pts
        self.vel.text = "velocity %s" % (vel or "?")
        self.fill.classes["over"] = over
        self.fill.style["width"] = "%d%%" % min(100, 100 * pts / mx)
        self.mark.visible = bool(vel)
        self.mark.style["left"] = "%d%%" % (100 * vel / mx)
        self.over_note.visible = over
        self.unest_note.visible = bool(unest)
        self.unest_note.text = state.plural(unest, "card") + " not estimated."
        self.cards_panel.items = [dict(c, planned=s["state"] == "planned") for c in s["cards_list"]]
        self.cards_panel.add_event_handler("x-out", self._out)
        self.empty.visible = not s["cards_list"]
        self.planned_acts.visible = s["state"] == "planned"
        self.running_link.visible = s["state"] != "planned"
        self.start_button.enabled = not self.item["active_exists"]
        if self.item["active_exists"]:
            self.start_button.tooltip = "Close the running sprint first"

    def _changed(self):
        if self.parent is not None:
            self.parent.raise_event("x-changed")

    def _out(self, card_id, **event_args):
        if state.call("update_card", card_id, {"sprint_id": None}) is not None:
            self._changed()

    @handle("start_button", "click")
    def start_button_click(self, **event_args):
        r = state.call("start_sprint", self.item["s"]["id"])
        if r:
            aa.rave("SPRINT ON", "%s: %s points%s" % (r["sprint"]["name"], r["sprint"]["points"],
                                                       (", %s unestimated" % r["unestimated"]) if r.get("unestimated") else ""))
            self._changed()

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        if confirm("Its cards go back to the backlog.", title="Remove this planned sprint?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("delete_sprint", self.item["s"]["id"]) is not None:
                self._changed()
