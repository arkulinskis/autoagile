from anvil import *

from ._anvil_designer import KindCheckTemplate


class KindCheck(KindCheckTemplate):
    """An alert kind to switch on or off. item = {id, label, on, host (the Crew page)}."""

    def __init__(self, **properties):
        super().__init__(**properties)

    @handle("box", "change")
    def box_change(self, **event_args):
        self.item["host"].set_kind(self.item["id"], self.box.checked)
