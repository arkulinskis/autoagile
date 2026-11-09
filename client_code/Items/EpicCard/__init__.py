from anvil import *

from ._anvil_designer import EpicCardTemplate
from ... import state


class EpicCard(EpicCardTemplate):
    """An epic on the year roadmap; arrows move it a quarter. item = epic + host (the Plan page)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        state.set_attr(self, "style", "--ec:%s" % e["color"])
        parts = [e.get("size") or "", "%s pts" % e["remaining"], e.get("status") or ""]
        if e.get("forecast_q"):
            parts.append(("LATE → " + e["forecast_q"]) if e.get("late") else "at risk" if e.get("risky") else "on track")
        self.meta.text = "   ".join(p for p in parts if p)
        self.meta.role = ["pl-em", "late"] if e.get("late") else ["pl-em"]

    @handle("earlier", "click")
    def earlier_click(self, **event_args):
        self.item["host"].move_epic(self.item["id"], -1)

    @handle("later", "click")
    def later_click(self, **event_args):
        self.item["host"].move_epic(self.item["id"], 1)

    @handle("edit", "click")
    def edit_click(self, **event_args):
        self.item["host"].edit_epic(self.item["id"])
