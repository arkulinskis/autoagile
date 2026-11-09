from anvil import *

from ._anvil_designer import StatusRowTemplate
from ... import state


class StatusRow(StatusRowTemplate):
    """A status found in the file and the column it goes to. item = {src, n, targets, value}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.n.text = str(self.item["n"])
        self.pick.items = self.item["targets"]
        vals = [v for _, v in self.item["targets"]]
        self.pick.selected_value = self.item["value"] if self.item["value"] in vals else "backlog"
        state.set_control_attr(self.pick, "aria-label", "Column for " + str(self.item["src"]))

    @handle("pick", "change")
    def pick_change(self, **event_args):
        self.parent.raise_event("x-smap", src=self.item["src"], value=self.pick.selected_value)
