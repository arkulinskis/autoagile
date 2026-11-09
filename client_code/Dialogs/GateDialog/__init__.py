from anvil import *

from ._anvil_designer import GateDialogTemplate
from ... import state


class GateDialog(GateDialogTemplate):
    """Estimate one card through the gates (from a backlog row). Closes with the server's gate result, or None."""

    def __init__(self, **properties):
        card, cfg = properties.pop("card"), properties.pop("cfg", None)
        super().__init__(**properties)
        self.card = card
        self.key.text = card["key"]
        state.heading(self.key, 2)
        self.title.text = card["title"]
        self.gates.cfg = cfg
        self.gates.answers = card.get("gates") or {}
        self.save_button.enabled = self.gates.score()["complete"]

    @handle("gates", "gates_change")
    def gates_change(self, answers=None, score=None, **event_args):
        self.save_button.enabled = bool(score and score["complete"])

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        r = state.call("estimate_card", self.card["id"], self.gates.answers)
        if r:
            self.raise_event("x-close-alert", value=r["gate"])
