from anvil import *

from ._anvil_designer import MapRowTemplate
from ... import state


class MapRow(MapRowTemplate):
    """Which file column holds a card field. item = {id, label, headers, value}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.pick.items = [("(none)", "")] + [(h, h) for h in self.item["headers"]]
        self.pick.selected_value = self.item["value"] if self.item["value"] in self.item["headers"] else ""
        state.set_control_attr(self.pick, "aria-label", self.item["label"].replace(" *", ""))

    @handle("pick", "change")
    def pick_change(self, **event_args):
        self.parent.raise_event("x-map", field=self.item["id"], value=self.pick.selected_value or "")
