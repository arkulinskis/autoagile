from anvil import *

from ._anvil_designer import ColorPickTemplate
from ... import state


class ColorPick(ColorPickTemplate):
    """A colour swatch in the epic dialog. item = {c, on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.pick.text = "Colour " + self.item["c"]
        self.pick.background = self.item["c"]
        self.pick.role = ["swatch", "on"] if self.item["on"] else ["swatch"]
        state.set_control_attr(self.pick, "aria-pressed", "true" if self.item["on"] else "false")
        state.set_control_attr(self.pick, "data-key", self.item["c"])

    @handle("pick", "click")
    def pick_click(self, **event_args):
        self.parent.raise_event("x-color", color=self.item["c"])
