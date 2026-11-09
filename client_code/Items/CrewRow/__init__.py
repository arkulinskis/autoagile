from anvil import *

from ._anvil_designer import CrewRowTemplate
from ... import state


class CrewRow(CrewRowTemplate):
    """A crew in the switcher. The whole row is one button (it covers the row). item = crew summary + on."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        self.classes["on"] = bool(c.get("on"))
        self.sub.text = "Level %d · %s · %s · %s" % (c["level"], c["level_name"], state.plural(c["open"], "open card"),
                                                      "DEMO" if c["demo"] else c["role"])
        self.pick.text = "Open %s (%s)" % (c["name"], c["key"])

    @handle("pick", "click")
    def pick_click(self, **event_args):
        self.parent.raise_event("x-pick", crew_id=self.item["id"])
