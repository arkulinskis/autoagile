from anvil import *

from ._anvil_designer import AccRowTemplate


class AccRow(AccRowTemplate):
    """An acceptance criterion: tick it, or remove it. item = {text, done, i}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.classes["done"] = bool(self.item.get("done"))

    @handle("box", "change")
    def box_change(self, **event_args):
        self.parent.raise_event("x-tick", i=self.item["i"], done=self.box.checked)

    @handle("remove", "click")
    def remove_click(self, **event_args):
        self.parent.raise_event("x-remove", i=self.item["i"])
