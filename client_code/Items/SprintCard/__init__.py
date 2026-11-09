from anvil import *

from ._anvil_designer import SprintCardTemplate
from ... import router, state


class SprintCard(SprintCardTemplate):
    """A card inside a sprint panel. item = card + planned (only a planned sprint can give cards back)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        state.set_attr(self.link, "href", router.href("card", c["key"]))
        self.pts.text = "?" if c["points"] is None else str(c["points"])
        self.pts.role = ["aa-pts", "none"] if c["points"] is None else ["aa-pts"]
        self.out_button.visible = bool(c.get("planned"))

    @handle("out_button", "click")
    def out_button_click(self, **event_args):
        self.parent.raise_event("x-out", card_id=self.item["id"])
