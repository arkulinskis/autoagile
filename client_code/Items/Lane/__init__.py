from anvil import *

from ._anvil_designer import LaneTemplate
from ... import state


class Lane(LaneTemplate):
    """A swimlane: its head (person, epic, priority or type) and one drop area per column. With no lanes there is
    one lane without a head. item = {key, name, who?, color?, bodies, n, cols}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        named = bool(it.get("name"))
        self.classes["bd-lane"] = named
        self.head.visible = named
        self.who.visible = bool(it.get("who"))
        self.who.person = it.get("who")
        self.dot.visible = bool(it.get("color"))
        if it.get("color"):
            self.dot.style["background"] = it["color"]
        self.lname.text = it.get("name") or ""
        self.count.text = str(it["n"])
        state.set_attr(self.grid, "style", "--n:%d" % it["cols"])
        self.bodies_panel.items = it["bodies"]
