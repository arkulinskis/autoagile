from anvil import *

from ._anvil_designer import SlotLabelTemplate


class SlotLabel(SlotLabelTemplate):
    """A sprint slot over the 3-month gantt. item = {label, start, end, current}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.classes["cur"] = bool(self.item.get("current"))
        self.lab.tooltip = "%s to %s" % (self.item.get("start"), self.item.get("end"))
