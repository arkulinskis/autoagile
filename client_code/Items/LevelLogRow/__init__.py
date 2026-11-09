from anvil import *

from ._anvil_designer import LevelLogRowTemplate
from ... import state


class LevelLogRow(LevelLogRowTemplate):
    """A level change in the history. item = {level, lname, by, forced, at}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        l = self.item
        self.n.text = "LVL %s" % l["level"]
        self.what.text = "%s · by %s" % (l["lname"], l.get("by") or "")
        self.forced.visible = bool(l.get("forced"))
        self.at.text = state.long_date(l.get("at"))
