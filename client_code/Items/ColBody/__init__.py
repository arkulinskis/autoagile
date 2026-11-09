from anvil import *

from ._anvil_designer import ColBodyTemplate
from ... import state


class ColBody(ColBodyTemplate):
    """One column's cards inside one lane: the drop target (data-drop = column id, data-lane = lane key) for the
    engine's drag and drop. item = {col, lane, cards, show}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        state.set_attr(self, "data-drop", it["col"]["id"])
        state.set_attr(self, "data-lane", it["lane"])
        state.set_attr(self, "aria-label", it["col"]["name"])
        self.classes["show"] = bool(it.get("show"))
        self.cards_panel.items = it["cards"]
        none = not it["cards"] and it["lane"] == "all"
        self.empty_ready.visible = none and it["col"]["stage"] == "ready"
        self.empty.visible = none and it["col"]["stage"] != "ready"
