from anvil import *

from ._anvil_designer import EpicRowTemplate
from ... import state


class EpicRow(EpicRowTemplate):
    """An epic on the Epics tab: progress, quarter, rank arrows, edit. item = epic + host (the Plan page)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        state.set_attr(self, "style", "--ec:%s" % e["color"])
        self.dot.style["background"] = e["color"]
        self.meta.text = "%s cards · %s pts done · %s left (%s)" % (e["cards"], e["done_points"], e["remaining"],
                                                                     "from size " + e["size"] if e.get("sized_by") == "size" else "from cards")
        self.fill.style["width"] = "%s%%" % e["progress"]
        state.set_attr(self.prog, "title", "%s%% done" % e["progress"])
        self.quarter.text = e.get("quarter") or "unscheduled"

    @handle("up", "click")
    def up_click(self, **event_args):
        self.item["host"].rank_epic(self.item["id"], "up")

    @handle("down", "click")
    def down_click(self, **event_args):
        self.item["host"].rank_epic(self.item["id"], "down")

    @handle("edit", "click")
    def edit_click(self, **event_args):
        self.item["host"].edit_epic(self.item["id"])
