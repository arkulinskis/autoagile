from anvil import *

from ._anvil_designer import PaletteRowTemplate
from ... import state


class PaletteRow(PaletteRowTemplate):
    """A palette choice: a page (icon + chord), a card (its key) or an action. item = {label, icon|key, hint, i, on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        lead = it["key"] + "   " if it.get("key") else ""
        self.run.text = lead + it["label"] + ("   " + it["hint"] if it.get("hint") else "")
        roles = ["pal-item"] + ([] if it.get("key") else ["ic-" + (it.get("icon") or "zap")]) + (["on"] if it.get("on") else [])
        self.run.role = roles
        state.set_control_attr(self.run, "role", "option")
        state.set_control_attr(self.run, "aria-selected", "true" if it.get("on") else "false")

    @handle("run", "click")
    def run_click(self, **event_args):
        self.parent.raise_event("x-run", i=self.item["i"])
